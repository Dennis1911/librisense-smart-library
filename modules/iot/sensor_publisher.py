"""LibriSense Edge GrovePi I/O service (sensors + break-nudge actuators).

Owns the GrovePi+ I2C connection and is therefore the single process that
both READS the sensors and DRIVES the GrovePi digital-output actuators
(break LED + buzzer). Keeping one owner of the GrovePi bus avoids
write/read interleaving corruption against the ATmega at 0x04; a lock
serialises the sensor-read loop against the action callbacks.

Sensors (config/devices.yaml -> grovepi.sensors) are sampled at sample_hz
and published to library/sensors/<name>.

Break nudge (config/devices.yaml -> grovepi.actuators):
  * the planner's suggest_break action (on library/actions) lights the LED
    and gives a short, quiet PWM buzzer beep, re-beeping every REBEEP_S while
    the break stays due (a gentle escalation);
  * when library/state reports break_due is over, the nudge clears.

Run on the Edge Pi:
    .venv/bin/python modules/iot/sensor_publisher.py
"""
from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
import paho.mqtt.client as mqtt

sys.path.insert(0, str(Path(__file__).parent))
from grovepi_io import GrovePi  # noqa: E402
from broker import pick_broker_host  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DEVICES = REPO / "config" / "devices.yaml"
TOPICS = REPO / "config" / "topics.yaml"

REBEEP_S = 20.0     # re-beep this often while a break stays due (escalation)
BEEP_S = 0.12       # length of one gentle beep


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def transform(raw: int, spec: dict) -> tuple[object, str]:
    """Map a raw 0..1023 ADC reading to a published value + unit."""
    kind = spec.get("transform", "raw")
    if kind == "motion":
        return (raw > spec.get("threshold", 100)), spec.get("unit", "bool")
    if kind == "level":
        return round(raw / 1023 * 100, 1), spec.get("unit", "pct")
    return raw, spec.get("unit", "raw")


class BreakNudge:
    """LED + buzzer break nudge, driven via the (locked) GrovePi."""

    def __init__(self, gp: GrovePi, lock: threading.Lock, cfg: list[dict]) -> None:
        self.gp, self.lock = gp, lock
        self.led = next((a for a in cfg if a["name"] == "break_led"), None)
        self.buzzer = next((a for a in cfg if a["name"] == "break_buzzer"), None)
        self.active = False
        self.last_beep = 0.0
        with self.lock:
            if self.led:
                gp.pin_mode(self.led["port"], "OUTPUT")
                gp.digital_write(self.led["port"], 0)
            if self.buzzer:
                gp.pin_mode(self.buzzer["port"], "OUTPUT")
                gp.analog_write(self.buzzer["port"], 0)

    def _beep(self) -> None:
        if not self.buzzer:
            return
        vol = self.buzzer.get("volume", 35)
        with self.lock:
            self.gp.analog_write(self.buzzer["port"], vol)
        time.sleep(BEEP_S)
        with self.lock:
            self.gp.analog_write(self.buzzer["port"], 0)

    def start(self) -> None:
        """Begin the nudge (planner asked to suggest a break)."""
        if self.led:
            with self.lock:
                self.gp.digital_write(self.led["port"], 1)
        if not self.active:
            self.active = True
            self._beep()
            self.last_beep = time.monotonic()

    def stop(self) -> None:
        if not self.active and self.led is None:
            return
        self.active = False
        if self.led:
            with self.lock:
                self.gp.digital_write(self.led["port"], 0)

    def tick(self) -> None:
        """Re-beep periodically while the break stays due."""
        if self.active and (time.monotonic() - self.last_beep) >= REBEEP_S:
            self._beep()
            self.last_beep = time.monotonic()


def main() -> None:
    devices = load_yaml(DEVICES)
    topics = load_yaml(TOPICS)
    broker = topics["broker"]
    zone = devices.get("zone", "reading-1")
    period = 1.0 / devices.get("sample_hz", 1)
    sensors = devices["grovepi"]["sensors"]
    actuators = devices["grovepi"].get("actuators", [])

    gp = GrovePi()
    lock = threading.Lock()
    nudge = BreakNudge(gp, lock, actuators)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"{broker.get('client_id_prefix','librisense')}-edge-grove")

    def on_connect(c, u, f, rc, p):
        c.subscribe("library/actions")
        c.subscribe("library/state")

    def on_message(c, u, msg):
        try:
            payload = json.loads(msg.payload)
        except ValueError:
            return
        if msg.topic == "library/actions":
            if payload.get("action") == "suggest_break":
                nudge.start()
        elif msg.topic == "library/state":
            z = payload.get("zones", {}).get(zone, {})
            if z and not z.get("break_due", False):
                nudge.stop()

    client.on_connect = on_connect
    client.on_message = on_message
    host, port = pick_broker_host(broker)   # mDNS at home, 10.42.0.1 on hotspot
    client.connect(host, port, 60)
    print(f"[grove] broker at {host}:{port}")
    client.loop_start()
    print(f"[grove] connected to {host}:{port}; {len(sensors)} sensors @ "
          f"{devices.get('sample_hz',1)} Hz, {len(actuators)} actuators")

    try:
        while True:
            ts = datetime.now(timezone.utc).isoformat()
            for s in sensors:
                try:
                    with lock:
                        raw = (gp.analog_read(s["port"]) if s["kind"] == "analog"
                               else gp.digital_read(s["port"]))
                except OSError as e:
                    print(f"[grove] read {s['name']} failed: {e}")
                    continue
                value, unit = transform(raw, s)
                client.publish(s["topic"], json.dumps(
                    {"ts": ts, "zone": zone, "sensor": s["name"],
                     "raw": raw, "value": value, "unit": unit}))
            nudge.tick()
            time.sleep(period)
    except KeyboardInterrupt:
        print("\n[grove] stopping")
    finally:
        nudge.stop()
        gp.close()
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
