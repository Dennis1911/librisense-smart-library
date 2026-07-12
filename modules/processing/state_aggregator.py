"""LibriSense processing module (Core node) — state aggregator.

Subscribes to all library/sensors/* streams, keeps a short sliding window
per sensor, derives higher-level quantities, and publishes a compact world
state on library/state at a fixed rate. This is the single source of truth
the problem generator (Sprint 3) turns into a PDDL problem.

Derived quantities:
  - occupancy:   motion sensor debounced over the window
  - co2_ppm:     SIMULATED proxy from occupancy x time (ASHRAE-style ramp),
                 since the kit has no CO2 sensor (per proposal)
  - comfort:     0..1 index from light + noise + (simulated) temp
  - sound/light: smoothed averages

Run on the Core Pi:
    .venv/bin/python modules/processing/state_aggregator.py

Published payload (topic library/state):
    {"ts", "zones": {<zone>: {...}}, "outdoor": {...}}
"""
from __future__ import annotations

import json
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import yaml
import paho.mqtt.client as mqtt

REPO = Path(__file__).resolve().parents[2]
TOPICS = REPO / "config" / "topics.yaml"

WINDOW_S = 10          # motion window (occupancy persistence)
DISPLAY_WINDOW_S = 3   # sound/light smoothing — short, so changes show fast
PUBLISH_HZ = 2         # world-state snapshots per second

# CO2 proxy parameters (ASHRAE-style): baseline outdoor ~420 ppm; an occupied
# zone ramps up toward a ceiling, decays back toward baseline when empty.
CO2_BASELINE = 420
CO2_CEILING = 1400
CO2_RAMP_PER_S = 4.0    # ppm/s rise while occupied
CO2_DECAY_PER_S = 2.0   # ppm/s fall while empty
# When a planner ventilation action fires, fresh air is modelled as a timed
# window of strong CO2 decay — this closes the CO2 control loop so the
# ventilation goal actually clears instead of lingering forever.
# Leveled per the window-control report: a full airing runs long, a pulse is
# a short burst (winter strategy), knocking CO2 down one band.
VENT_FULL_DURATION_S = 45
VENT_PULSE_DURATION_S = 12
VENT_DECAY_PER_S = 35.0

# Planner action name -> ventilation window length. "ventilate" kept for
# backwards compatibility with older plans/tools.
VENT_ACTION_DURATIONS = {
    "full_ventilate": VENT_FULL_DURATION_S,
    "ventilate": VENT_FULL_DURATION_S,
    "pulse_ventilate": VENT_PULSE_DURATION_S,
    "pulse_ventilate_step": VENT_PULSE_DURATION_S,
}

# Learner focus-session FSM (the Pomodoro objective from the proposal).
# Four states: idle → focused → break-due → on-break → (idle or focused)
# Real Pomodoro is 25 min of focus; demo threshold is shorter so the
# break-due transition is observable during a live demo.
FOCUS_THRESHOLD_S = 120   # occupied this long (continuously) => break-due
OCCUPANCY_GRACE_S = 15    # still "present" if motion seen within this window
BREAK_RESET_GAP_S = 30    # empty this long in any non-idle state => back to idle

# FSM state constants (match dashboard phase labels exactly)
PHASE_IDLE      = "idle"
PHASE_FOCUSED   = "focused"
PHASE_BREAK_DUE = "break-due"
PHASE_ON_BREAK  = "on-break"


class Window:
    """Time-bounded sample buffer."""

    def __init__(self, seconds: float = WINDOW_S) -> None:
        self.seconds = seconds
        self.buf: deque[tuple[float, float]] = deque()

    def add(self, ts: float, value: float) -> None:
        self.buf.append((ts, value))
        cutoff = ts - self.seconds
        while self.buf and self.buf[0][0] < cutoff:
            self.buf.popleft()

    def avg(self, default: float = 0.0) -> float:
        if not self.buf:
            return default
        return sum(v for _, v in self.buf) / len(self.buf)

    def max(self, default: float = 0.0) -> float:
        if not self.buf:
            return default
        return max(v for _, v in self.buf)


class ZoneState:
    """Sensor buffers + CO₂ proxy + 4-state learner FSM for one zone.

    FSM states
    ----------
    idle       No one present (or session fully reset after a long absence).
    focused    Learner is present and within their focus window.
    break-due  Focus threshold reached; break has been triggered but learner
               hasn't stepped away yet.
    on-break   Learner stepped away after break-due; actively resting.
               Returns to focused on re-entry, or to idle after BREAK_RESET_GAP_S.
    """

    def __init__(self) -> None:
        # Short window for light so changes react quickly; the motion window
        # stays longer for stable occupancy. (Sound sensor removed — the
        # GrovePi can't sample fast enough to measure loudness.)
        self.light  = Window(DISPLAY_WINDOW_S)
        self.motion = Window(WINDOW_S)
        self.co2    = float(CO2_BASELINE)

        # FSM state
        self._fsm             = PHASE_IDLE
        self.session_s        = 0.0   # seconds of current focus/on-break interval
        self._empty_s         = 0.0   # seconds without presence in current state
        self._last_motion_age = OCCUPANCY_GRACE_S + 1
        self._vent_remaining  = 0.0   # seconds of active ventilation left

    def is_occupied(self) -> bool:
        """Present if a motion hit landed within the occupancy-grace window."""
        return self._last_motion_age <= OCCUPANCY_GRACE_S

    def start_ventilation(self, duration_s: float = VENT_FULL_DURATION_S) -> None:
        # Extend rather than overwrite, so a pulse during a running full
        # airing never shortens it.
        self._vent_remaining = max(self._vent_remaining, duration_s)

    @property
    def ventilating(self) -> bool:
        return self._vent_remaining > 0

    def update(self, dt: float) -> None:
        # ── Motion tracking ──────────────────────────────────────────────────
        if self.motion.max() >= 0.5:
            self._last_motion_age = 0.0
        else:
            self._last_motion_age += dt

        occupied = self.is_occupied()

        # ── Learner FSM ───────────────────────────────────────────────────────
        if self._fsm == PHASE_IDLE:
            if occupied:
                self._fsm      = PHASE_FOCUSED
                self.session_s = 0.0
                self._empty_s  = 0.0

        elif self._fsm == PHASE_FOCUSED:
            if occupied:
                self.session_s += dt
                self._empty_s   = 0.0
                if self.session_s >= FOCUS_THRESHOLD_S:
                    self._fsm = PHASE_BREAK_DUE
            else:
                self._empty_s += dt
                if self._empty_s >= BREAK_RESET_GAP_S:
                    # Left without a break — reset to idle
                    self._fsm      = PHASE_IDLE
                    self.session_s = 0.0
                    self._empty_s  = 0.0

        elif self._fsm == PHASE_BREAK_DUE:
            if occupied:
                self.session_s += dt   # keep timing; planner still nudging
                self._empty_s   = 0.0
            else:
                # Learner stepped away → they're taking the break
                self._fsm      = PHASE_ON_BREAK
                self.session_s = 0.0
                self._empty_s  = 0.0

        elif self._fsm == PHASE_ON_BREAK:
            if occupied:
                # Back from break → fresh focus session
                self._fsm      = PHASE_FOCUSED
                self.session_s = 0.0
                self._empty_s  = 0.0
            else:
                self._empty_s += dt
                if self._empty_s >= BREAK_RESET_GAP_S:
                    # Long absence after break → full reset
                    self._fsm     = PHASE_IDLE
                    self._empty_s = 0.0

        # ── CO₂ dynamics ─────────────────────────────────────────────────────
        # Ventilation (timed) wins; then occupancy ramp/decay.
        if self._vent_remaining > 0:
            self._vent_remaining = max(0.0, self._vent_remaining - dt)
            self.co2 = max(CO2_BASELINE, self.co2 - VENT_DECAY_PER_S * dt)
        elif occupied:
            self.co2 = min(CO2_CEILING, self.co2 + CO2_RAMP_PER_S * dt)
        else:
            self.co2 = max(CO2_BASELINE, self.co2 - CO2_DECAY_PER_S * dt)

    def snapshot(self) -> dict:
        occupied = self.is_occupied()
        light    = round(self.light.avg(), 1)
        # Comfort 0..1 from the two reliable signals: enough light + fresh air.
        light_ok = min(light / 60.0, 1.0)
        air_ok   = max(0.0, min(1.0, (1200 - self.co2) / (1200 - CO2_BASELINE)))
        comfort  = round(0.5 * light_ok + 0.5 * air_ok, 2)
        return {
            "occupied":    occupied,
            "light_pct":   light,
            "co2_ppm":     round(self.co2),
            "comfort":     comfort,
            "session_min": round(self.session_s / 60.0, 1),
            "phase":       self._fsm,
            "break_due":   self._fsm == PHASE_BREAK_DUE,  # kept for problem_generator
            "ventilating": self.ventilating,
        }


class Aggregator:
    def __init__(self) -> None:
        self.zones: dict[str, ZoneState] = {}
        self.outdoor: dict = {}
        self._last_tick = time.monotonic()

    def zone(self, name: str) -> ZoneState:
        return self.zones.setdefault(name, ZoneState())

    def on_sensor(self, msg: dict) -> None:
        now = time.monotonic()
        sensor = msg.get("sensor")
        if sensor == "weather":
            self.outdoor = {k: msg.get(k) for k in
                            ("outdoor_temp_c", "humidity_pct", "cloud_cover_pct")}
            return
        z = self.zone(msg.get("zone", "reading-1"))
        val = msg.get("value")
        if sensor == "motion":
            z.motion.add(now, 1.0 if val else 0.0)
        elif sensor == "light":
            z.light.add(now, float(val))

    def on_action(self, cmd: dict) -> None:
        # Ventilation actions open a timed window of strong CO2 decay,
        # closing the air-quality control loop in the simulation. Pulse
        # actions open a short window, full airing a long one. Only zones we
        # actually track are affected (guards against phantom zone names).
        duration = VENT_ACTION_DURATIONS.get(cmd.get("action"))
        if duration is not None:
            args = cmd.get("args", [])
            name = args[0] if args else "reading-1"
            if name in self.zones:
                self.zones[name].start_ventilation(duration)

    def tick(self) -> None:
        now = time.monotonic()
        dt = now - self._last_tick
        self._last_tick = now
        for z in self.zones.values():
            z.update(dt)

    def snapshot(self) -> dict:
        zones_snap = {name: z.snapshot() for name, z in self.zones.items()}
        # Expose learner state as a top-level users dict so the dashboard
        # Pomodoro rings have data without parsing zone internals.
        # One learner per zone for now; extend when multi-seat tracking is added.
        users = {
            name: {
                "phase":           s["phase"],
                "session_minutes": s["session_min"],
            }
            for name, s in zones_snap.items()
        }
        return {
            "ts":      datetime.now(timezone.utc).isoformat(),
            "zones":   zones_snap,
            "outdoor": self.outdoor,
            "users":   users,
        }


def main() -> None:
    topics = yaml.safe_load(open(TOPICS))
    broker = topics["broker"]
    agg = Aggregator()

    def on_connect(client, userdata, flags, reason_code, properties):
        client.subscribe("library/sensors/#")
        client.subscribe("library/actions")
        print("[processing] subscribed to library/sensors/# + library/actions")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload)
            if msg.topic == "library/actions":
                agg.on_action(payload)
            else:
                agg.on_sensor(payload)
        except (ValueError, KeyError) as e:
            print(f"[processing] bad message on {msg.topic}: {e}")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"{broker.get('client_id_prefix','librisense')}-processing")
    client.on_connect = on_connect
    client.on_message = on_message
    host, port = broker["host"], broker.get("port", 1883)
    while True:
        try:
            client.connect(host, port, 60)
            break
        except OSError as e:
            print(f"[processing] broker {host}:{port} not reachable ({e}); retry in 5s")
            time.sleep(5)
    client.loop_start()
    print(f"[processing] connected to {host}:{port}; publishing library/state @ {PUBLISH_HZ} Hz")

    period = 1.0 / PUBLISH_HZ
    try:
        while True:
            agg.tick()
            snap = agg.snapshot()
            if snap["zones"]:
                # Retained: late subscribers (dashboard, problem gen) get the
                # latest world state immediately on connect.
                client.publish("library/state", json.dumps(snap), retain=True)
            time.sleep(period)
    except KeyboardInterrupt:
        print("\n[processing] stopping")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
