"""LibriSense Mock Publisher — test the dashboard without any Raspberry Pi.

Publishes realistic fake data to a local MQTT broker every second.
Simulates: zone state, outdoor weather, AI planner output, actuator state,
and learner Pomodoro sessions.

Usage:
    pip install paho-mqtt pyyaml
    # Terminal 1 — broker
    & "C:\\Program Files\\mosquitto\\mosquitto.exe"
    # Terminal 2 — this script
    python tools/mock_publisher.py
    # Terminal 3 — dashboard
    $env:MQTT_HOST = "127.0.0.1"
    python -m uvicorn modules.visualisation.dashboard:app --port 8000 --reload
"""
import json
import math
import random
import time

import paho.mqtt.client as mqtt

# ── Config ────────────────────────────────────────────────────────────────────
BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883
TICK_S      = 1.0   # publish interval in seconds

# ── Seat definitions ─────────────────────────────────────────────────────────
# Each seat has a different occupancy cycle so the heatmap looks interesting.
# occ_period: how many ticks per occupancy cycle
# occ_duty:   fraction of the cycle the seat is occupied (0-1)
# occ_offset: tick offset so seats don't all flip together
SEATS = [
    {"name": "seat-1", "period": 32, "duty": 0.85, "offset": 0},
    {"name": "seat-2", "period": 28, "duty": 0.60, "offset": 7},
    {"name": "seat-3", "period": 40, "duty": 0.70, "offset": 14},
    {"name": "seat-4", "period": 22, "duty": 0.45, "offset": 4},
    {"name": "seat-5", "period": 36, "duty": 0.90, "offset": 19},
    {"name": "seat-6", "period": 30, "duty": 0.50, "offset": 11},
]

# ── Planner action pool ────────────────────────────────────────────────────────
PLAN_SCENARIOS = [
    [{"name": "turn_on_lamp",  "args": ["seat-1"]}],   # occupied + dim
    [{"name": "ventilate",     "args": ["seat-3"]}],   # high CO₂
    [{"name": "suggest_break", "args": ["seat-5"]}],   # break due
    [],                                                  # already optimal
]

# ── Pomodoro simulation ───────────────────────────────────────────────────────
# Demo speed: 1 tick = 1 second, but Pomodoro "minutes" advance faster
# Full cycle at demo speed: 40 s focused → 3 s break-due → 12 s on-break
# After 4 cycles: 15 s idle (long break), then repeat.
FOCUS_S     = 40
BREAK_DUE_S = 3
BREAK_S     = 12
FULL_CYCLE  = FOCUS_S + BREAK_DUE_S + BREAK_S   # 55 s per cycle
LONG_IDLE_S = 15
TOTAL_S     = FULL_CYCLE * 4 + LONG_IDLE_S      # 235 s full loop


def pomodoro_state(tick: int) -> tuple[str, int]:
    """Return (phase, session_minutes) at the given tick."""
    pos = tick % TOTAL_S
    for cycle in range(4):
        start = cycle * FULL_CYCLE
        if pos < start + FOCUS_S:
            elapsed = pos - start
            mins = round(elapsed * 25 / FOCUS_S)
            return "focused", mins
        if pos < start + FOCUS_S + BREAK_DUE_S:
            return "break-due", 25
        if pos < start + FULL_CYCLE:
            elapsed = pos - (start + FOCUS_S + BREAK_DUE_S)
            mins = round(elapsed * 5 / BREAK_S)
            return "on-break", mins
    return "idle", 0


# ── Helpers ────────────────────────────────────────────────────────────────────
def _sine(period_s: float, phase: float = 0.0, lo: float = 0, hi: float = 1) -> float:
    v = (math.sin(2 * math.pi * time.time() / period_s + phase) + 1) / 2
    return lo + v * (hi - lo)


# ── Payload builders ──────────────────────────────────────────────────────────
def make_state(tick: int) -> dict:
    zones = {}
    users = {}

    for i, seat in enumerate(SEATS):
        name      = seat["name"]
        occupied  = ((tick + seat["offset"]) % seat["period"]) < round(seat["period"] * seat["duty"])
        # Slightly different light and CO₂ per seat (phase offset for variety)
        light_pct = round(_sine(120, i * 0.8, 8, 98))
        co2_ppm   = round(400 + ((tick + seat["offset"]) % 60) * 7) if occupied else 420
        comfort   = round(_sine(90, i * 0.6, 0.50, 0.97), 2)

        # Independent Pomodoro state per seat (offset so they're not in sync)
        phase, mins = pomodoro_state(tick + seat["offset"] * 3)
        if not occupied:
            phase = "idle"
            mins  = 0

        zones[name] = {
            "occupied":  occupied,
            "light_pct": light_pct,
            "co2_ppm":   co2_ppm,
            "comfort":   comfort,
            "phase":     phase,
            "break_due": phase == "break-due",
        }
        users[name] = {
            "phase":           phase,
            "session_minutes": mins,
        }

    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "zones":   zones,
        "outdoor": {
            "outdoor_temp_c":  round(_sine(3600, 0, 12, 26), 1),
            "humidity_pct":    round(_sine(3600, 1, 35, 75)),
            "cloud_cover_pct": round(_sine(1800, 2, 0, 100)),
        },
        "users": users,
    }


def make_plan(tick: int) -> dict:
    idx     = (tick // 15) % len(PLAN_SCENARIOS)
    actions = PLAN_SCENARIOS[idx]
    return {
        "ts":       time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status":   "solved" if actions else "goal_already_met",
        "cost":     len(actions),
        "solve_ms": random.randint(80, 210),
        "actions":  actions,
    }


def make_actuators(tick: int) -> dict:
    # Lamp follows occupancy of seat-1 (the "main" zone the planner controls)
    seat1_occ = (tick % SEATS[0]["period"]) < round(SEATS[0]["period"] * SEATS[0]["duty"])
    return {"lamp": {"on": seat1_occ}}


# ── Main loop ──────────────────────────────────────────────────────────────────
def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="librisense-mock")
    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_start()
    print(f"Connected to {BROKER_HOST}:{BROKER_PORT}")
    print("Publishing mock data — open http://localhost:8000\n")

    tick = 0
    try:
        while True:
            state     = make_state(tick)
            plan      = make_plan(tick)
            actuators = make_actuators(tick)

            client.publish("library/state",          json.dumps(state),              retain=True)
            client.publish("library/plan",           json.dumps(plan),               retain=True)
            client.publish("library/actuators/lamp", json.dumps(actuators["lamp"]),  retain=True)

            # Publish raw sensor topics for each seat
            for seat_name, z in state["zones"].items():
                for sensor, value, unit in [
                    ("light",  z["light_pct"], "pct"),
                    ("motion", z["occupied"],  "bool"),
                    ("co2",    z["co2_ppm"],   "ppm"),
                ]:
                    client.publish(f"library/sensors/{sensor}", json.dumps({
                        "ts": state["ts"], "zone": seat_name, "value": value, "unit": unit,
                    }))

            occupied_seats = [n for n, z in state["zones"].items() if z["occupied"]]
            print(
                f"[{state['ts'][11:19]}] "
                f"occupied: {len(occupied_seats)}/{len(state['zones'])} seats "
                f"({', '.join(occupied_seats) or '—'}) | "
                f"plan: {plan['status']} ({len(plan['actions'])} actions)"
            )

            tick += 1
            time.sleep(TICK_S)

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
