"""LibriSense — Full simulation mock  (tools/mock_simulate.py)

Publishes completely fake data for ALL zones. No Raspberry Pi needed.
6 seats with staggered occupancy cycles — use this to test the full
dashboard (heatmap, Pomodoro rings, trend charts, plan card) without
any hardware connected.

Usage (all in separate terminals, librisense/ as cwd):
    & "C:\\Program Files\\mosquitto\\mosquitto.exe"          # broker
    .venv\\Scripts\\Activate.ps1
    python tools/mock_simulate.py                            # this script
    $env:MQTT_HOST = "127.0.0.1"
    python -m uvicorn modules.visualisation.dashboard:app --port 8000 --reload
"""
import json
import math
import random
import time

import paho.mqtt.client as mqtt

BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883
TICK_S      = 1.0

# ── Seat definitions ──────────────────────────────────────────────────────────
SEATS = [
    {"name": "seat-1", "period": 32, "duty": 0.85, "offset": 0},
    {"name": "seat-2", "period": 28, "duty": 0.60, "offset": 7},
    {"name": "seat-3", "period": 40, "duty": 0.70, "offset": 14},
    {"name": "seat-4", "period": 22, "duty": 0.45, "offset": 4},
    {"name": "seat-5", "period": 36, "duty": 0.90, "offset": 19},
    {"name": "seat-6", "period": 30, "duty": 0.50, "offset": 11},
]

PLAN_SCENARIOS = [
    [{"name": "turn_on_lamp",  "args": ["seat-1"]}],
    [{"name": "ventilate",     "args": ["seat-3"]}],
    [{"name": "suggest_break", "args": ["seat-5"]}],
    [],
]

# ── Pomodoro simulation ───────────────────────────────────────────────────────
FOCUS_S    = 40
BREAK_DUE_S = 3
BREAK_S    = 12
FULL_CYCLE = FOCUS_S + BREAK_DUE_S + BREAK_S
TOTAL_S    = FULL_CYCLE * 4 + 15


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


def make_state(tick: int) -> dict:
    zones, users = {}, {}
    for i, seat in enumerate(SEATS):
        name     = seat["name"]
        occupied = ((tick + seat["offset"]) % seat["period"]) < round(seat["period"] * seat["duty"])
        light    = round(_sine(120, i * 0.8, 8, 98))
        co2      = round(400 + ((tick + seat["offset"]) % 60) * 7) if occupied else 420
        comfort  = round(_sine(90, i * 0.6, 0.50, 0.97), 2)
        phase, mins = pomodoro_state(tick + seat["offset"] * 3)
        if not occupied:
            phase, mins = "idle", 0
        zones[name] = {"occupied": occupied, "light_pct": light, "co2_ppm": co2,
                       "comfort": comfort, "phase": phase, "break_due": phase == "break-due"}
        users[name] = {"phase": phase, "session_minutes": mins}

    return {
        "ts":      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "zones":   zones,
        "outdoor": {
            "outdoor_temp_c":   round(_sine(3600, 0, 12, 26), 1),
            "humidity_pct":     round(_sine(3600, 1, 35, 75)),
            "cloud_cover_pct":  round(_sine(1800, 2, 0, 100)),
        },
        "users": users,
    }


def make_plan(tick: int) -> dict:
    actions = PLAN_SCENARIOS[(tick // 15) % len(PLAN_SCENARIOS)]
    return {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "solved" if actions else "goal_already_met",
            "cost": len(actions), "solve_ms": random.randint(80, 210), "actions": actions}


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="librisense-simulate")
    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_start()
    print(f"[simulate] connected to {BROKER_HOST}:{BROKER_PORT}")
    print("[simulate] publishing 6 simulated seats — open http://localhost:8000\n")

    tick = 0
    try:
        while True:
            state = make_state(tick)
            plan  = make_plan(tick)
            lamp_on = state["zones"]["seat-1"]["occupied"]

            client.publish("library/state",          json.dumps(state), retain=True)
            client.publish("library/plan",           json.dumps(plan),  retain=True)
            client.publish("library/actuators/lamp", json.dumps({"on": lamp_on}), retain=True)

            occ = [n for n, z in state["zones"].items() if z["occupied"]]
            print(f"[{state['ts'][11:19]}] occupied {len(occ)}/6: {', '.join(occ) or '—'}"
                  f" | plan: {plan['status']}")
            tick += 1
            time.sleep(TICK_S)
    except KeyboardInterrupt:
        print("\n[simulate] stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
