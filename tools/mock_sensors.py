"""LibriSense — Hybrid seat enricher  (tools/mock_sensors.py)

Subscribes to library/state (published by the real state_aggregator on the
Core Pi), adds 5 simulated seats, and republishes the enriched state — so the
dashboard shows a lively 6-seat floor plan while ONE seat stays fully real.

Safety by design (display-only simulation):
  * every simulated zone/user carries "simulated": true — the problem
    generator SKIPS simulated zones, so the planner/actuators never act on
    fake seats (the real lamp/LED/buzzer only ever follow reading-1);
  * enriched messages carry a top-level "sim_enriched" marker and are
    ignored by our own subscriber — no feedback loop;
  * enrichment is event-driven: each real aggregator message is immediately
    followed by its enriched version, so subscribers effectively always see
    the 6-zone state (no 1-zone/6-zone flicker).

Run on the Core Pi alongside the normal pipeline (nothing needs stopping):
    .venv/bin/python tools/mock_sensors.py
or as the optional demo service:
    sudo systemctl start librisense-mockseats   # stop again after the demo
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
import yaml

REPO        = Path(__file__).resolve().parents[1]
TOPICS_FILE = REPO / "config" / "topics.yaml"

sys.path.insert(0, str(REPO / "modules" / "iot"))
from broker import pick_broker_host  # noqa: E402

# ── 5 simulated seats ─────────────────────────────────────────────────────────
SIM_SEATS = [
    {"name": "seat-2", "period": 28, "duty": 0.60, "offset": 7},
    {"name": "seat-3", "period": 40, "duty": 0.70, "offset": 14},
    {"name": "seat-4", "period": 22, "duty": 0.45, "offset": 4},
    {"name": "seat-5", "period": 36, "duty": 0.90, "offset": 19},
    {"name": "seat-6", "period": 30, "duty": 0.50, "offset": 11},
]

# ── Pomodoro simulation for simulated seats ───────────────────────────────────
FOCUS_S     = 40
BREAK_DUE_S = 3
BREAK_S     = 12
FULL_CYCLE  = FOCUS_S + BREAK_DUE_S + BREAK_S
TOTAL_S     = FULL_CYCLE * 4 + 15


def pomodoro_state(tick: int) -> tuple[str, int]:
    pos = tick % TOTAL_S
    for cycle in range(4):
        start = cycle * FULL_CYCLE
        if pos < start + FOCUS_S:
            return "focused", round((pos - start) * 25 / FOCUS_S)
        if pos < start + FOCUS_S + BREAK_DUE_S:
            return "break-due", 25
        if pos < start + FULL_CYCLE:
            return "on-break", round((pos - start - FOCUS_S - BREAK_DUE_S) * 5 / BREAK_S)
    return "idle", 0


def _sine(period_s: float, phase: float = 0.0, lo: float = 0, hi: float = 1) -> float:
    v = (math.sin(2 * math.pi * time.time() / period_s + phase) + 1) / 2
    return lo + v * (hi - lo)


def sim_seat(seat: dict, tick: int) -> tuple[dict, dict]:
    i        = SIM_SEATS.index(seat)
    occupied = ((tick + seat["offset"]) % seat["period"]) < round(seat["period"] * seat["duty"])
    light    = round(_sine(120, i * 0.8, 8, 98))
    co2      = round(400 + ((tick + seat["offset"]) % 60) * 7) if occupied else 420
    comfort  = round(_sine(90, i * 0.6, 0.50, 0.97), 2)
    phase, mins = pomodoro_state(tick + seat["offset"] * 3)
    if not occupied:
        phase, mins = "idle", 0
    zone = {"occupied": occupied, "light_pct": light, "co2_ppm": co2,
            "comfort": comfort, "phase": phase, "break_due": phase == "break-due",
            "session_min": mins,
            "simulated": True}   # problem generator skips simulated zones
    user = {"phase": phase, "session_minutes": mins, "simulated": True}
    return zone, user


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    broker = yaml.safe_load(open(TOPICS_FILE))["broker"]

    def enrich_and_publish(client: mqtt.Client, real_state: dict) -> None:
        # Simulated dynamics advance on the wall clock (2 ticks/s, matching
        # the original 0.5 s loop semantics).
        tick = int(time.time() * 2)
        enriched = dict(real_state)
        enriched["zones"] = dict(real_state.get("zones", {}))
        enriched["users"] = dict(real_state.get("users", {}))
        for seat in SIM_SEATS:
            z, u = sim_seat(seat, tick)
            enriched["zones"][seat["name"]] = z
            enriched["users"][seat["name"]] = u
        enriched["ts"] = datetime.now(timezone.utc).isoformat()
        enriched["sim_enriched"] = True   # our subscriber ignores this echo
        client.publish("library/state", json.dumps(enriched), retain=True)

    def on_connect(c, u, f, rc, p):
        c.subscribe("library/state")
        print("[mock_sensors] subscribed to library/state")

    def on_message(c, u, msg):
        try:
            payload = json.loads(msg.payload)
        except ValueError:
            return
        if payload.get("sim_enriched"):
            return                      # our own echo — never re-enrich it
        # Event-driven: every real aggregator state is immediately followed
        # by its enriched 6-zone version.
        enrich_and_publish(c, payload)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id="librisense-mock-sensors")
    client.on_connect = on_connect
    client.on_message = on_message

    host, port = pick_broker_host(broker)   # mDNS at home, 10.42.0.1 on hotspot
    client.connect(host, port, 60)
    print(f"[mock_sensors] connected to {host}:{port} — enriching library/state "
          f"with seat-2 … seat-6 (display-only; planner ignores simulated zones)")
    client.loop_forever()


if __name__ == "__main__":
    main()
