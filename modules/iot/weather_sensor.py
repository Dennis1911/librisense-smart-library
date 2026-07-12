"""LibriSense weather software-sensor (runs on the Core node).

Polls Open-Meteo (free, no API key) for outdoor conditions and publishes
them to library/sensors/weather. The planner uses this to pre-condition
heating (e.g. don't heat if it's warm outside, expect heat loss if cold).

Open-Meteo: https://open-meteo.com/  — keyless, generous free tier.

Run on the Core Pi:
    .venv/bin/python modules/iot/weather_sensor.py

Payload (topic library/sensors/weather):
    {"ts", "zone": "outdoor", "sensor": "weather",
     "outdoor_temp_c", "humidity_pct", "cloud_cover_pct", "unit": "mixed"}
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml
import paho.mqtt.client as mqtt

REPO = Path(__file__).resolve().parents[2]
TOPICS = REPO / "config" / "topics.yaml"

# Universität Stuttgart (Vaihingen campus). Override via config/location.yaml.
DEFAULT_LAT, DEFAULT_LON = 48.7457, 9.1068
POLL_SECONDS = 600  # weather changes slowly; every 10 min is plenty
API = ("https://api.open-meteo.com/v1/forecast"
       "?latitude={lat}&longitude={lon}"
       "&current=temperature_2m,relative_humidity_2m,cloud_cover")


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def fetch_weather(lat: float, lon: float) -> dict | None:
    url = API.format(lat=lat, lon=lon)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.load(r)
        cur = data["current"]
        return {
            "outdoor_temp_c": cur.get("temperature_2m"),
            "humidity_pct": cur.get("relative_humidity_2m"),
            "cloud_cover_pct": cur.get("cloud_cover"),
        }
    except Exception as e:  # noqa: BLE001 - network is best-effort
        print(f"[weather] fetch failed: {e}")
        return None


def main() -> None:
    topics = load_yaml(TOPICS)
    broker = topics["broker"]
    loc_file = REPO / "config" / "location.yaml"
    lat, lon = DEFAULT_LAT, DEFAULT_LON
    if loc_file.exists():
        loc = load_yaml(loc_file)
        lat, lon = loc.get("latitude", lat), loc.get("longitude", lon)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"{broker.get('client_id_prefix','librisense')}-weather")
    host, port = broker["host"], broker.get("port", 1883)
    while True:
        try:
            client.connect(host, port, 60)
            break
        except OSError as e:
            print(f"[weather] broker {host}:{port} not reachable ({e}); retry in 5s")
            time.sleep(5)
    client.loop_start()
    print(f"[weather] connected to {host}:{port}; polling Open-Meteo "
          f"@ ({lat},{lon}) every {POLL_SECONDS}s")

    try:
        while True:
            w = fetch_weather(lat, lon)
            if w:
                payload = {"ts": datetime.now(timezone.utc).isoformat(),
                           "zone": "outdoor", "sensor": "weather",
                           "unit": "mixed", **w}
                # Retained: weather changes slowly; late subscribers get the
                # last reading immediately instead of waiting up to 10 min.
                client.publish("library/sensors/weather", json.dumps(payload), retain=True)
                print(f"[weather] {w['outdoor_temp_c']}°C, "
                      f"{w['cloud_cover_pct']}% cloud, {w['humidity_pct']}% RH")
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("\n[weather] stopping")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
