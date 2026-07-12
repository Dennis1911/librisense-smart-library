"""LibriSense problem generator (Core node) — module 3.

Subscribes to library/state (the aggregated world state) and to
library/actuators/# (current actuator states, e.g. the lamp relay), maps
the continuous/discrete state into ground PDDL facts, renders a problem
instance from the Jinja2 template, and publishes it on library/problem for
the planner.

The discretisation thresholds below are the bridge between the continuous
sensor world and the classical PDDL domain. The *decision of which goal
atoms apply right now* lives here; the planner then decides how to reach
them cost-optimally.

Emits a new problem when the discretised facts change, or every HEARTBEAT_S
seconds, whichever comes first (the proposal's "on significant change or
every 30 s" rule).

Run on the Core Pi:
    .venv/bin/python modules/problem_generator/generator.py
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
import paho.mqtt.client as mqtt
from jinja2 import Environment, FileSystemLoader

REPO = Path(__file__).resolve().parents[2]
TOPICS = REPO / "config" / "topics.yaml"
TEMPLATES = REPO / "pddl" / "templates"

# --- discretisation thresholds (continuous sensor -> PDDL predicate) --------
# CO2 bands follow the team's window-control planning report (§8), demo-scaled:
#   ok < 800 ppm <= elevated < 1100 ppm <= high
DARK_BELOW_PCT = 40        # light below this % counts as "dark"
CO2_ELEVATED_PPM = 800     # middle band -> pulse ventilation suffices
CO2_HIGH_PPM = 1100        # high band -> full airing or two pulses
HEARTBEAT_S = 30           # re-emit at least this often even if unchanged

# --- weather-based ventilation costs (window-control report §9.2) ------------
# Heat-loss relation Q_loss ~ Qv x (Tin - Tout): the colder it is outside, the
# more a long airing costs. A short pulse is brief enough that its heat loss
# is roughly weather-independent at demo scale.
INDOOR_COMFORT_C = 22.0    # assumed indoor temperature (no indoor sensor)
DEFAULT_OUTDOOR_C = 15.0   # fallback when no weather data (e.g. hotspot mode)
PULSE_VENT_COST = 3        # constant: short pulse, negligible heat loss


def vent_costs(outdoor_temp_c: float | None) -> tuple[int, int]:
    """(pulse, full) action costs from outdoor temperature.

    full = 4 + dT/2 with dT = max(0, Tin - Tout). Crossover vs. two pulses
    (cost 6) sits around Tout ~ 18 C: warmer -> one full airing is optimal,
    colder -> the planner switches to the report's winter pulse strategy.
    """
    t_out = DEFAULT_OUTDOOR_C if outdoor_temp_c is None else float(outdoor_temp_c)
    delta_t = max(0.0, INDOOR_COMFORT_C - t_out)
    return PULSE_VENT_COST, 4 + int(delta_t / 2)


def co2_band(ppm: float) -> str:
    if ppm >= CO2_HIGH_PPM:
        return "high"
    if ppm >= CO2_ELEVATED_PPM:
        return "elevated"
    return "ok"


def discretise_zone(name: str, z: dict, lamp_on: bool) -> dict:
    """Map one zone's state dict to PDDL init facts + the active goal atoms."""
    occupied = bool(z.get("occupied"))
    dark = z.get("light_pct", 100) < DARK_BELOW_PCT
    band = co2_band(z.get("co2_ppm", 0))
    break_due = bool(z.get("break_due"))

    init: list[str] = []
    if occupied:
        init.append(f"(occupied {name})")
    if lamp_on:
        init.append(f"(lamp_on {name})")
    if dark:
        init.append(f"(dark {name})")
    if band == "elevated":
        init.append(f"(co2_elevated {name})")
    elif band == "high":
        init.append(f"(co2_high {name})")
    if break_due:
        init.append(f"(break_due {name})")

    # Active goals depend on the situation (this is the "policy"). A goal is
    # only set when an action can actually achieve it — otherwise the problem
    # would be unsolvable. In particular, "make it bright" is only pursued
    # when the lamp is OFF (turning it on is the remedy); if the lamp is
    # already on and the zone is still dark, we have done all we can.
    goal: list[str] = []
    if occupied:
        if dark and not lamp_on:
            goal.append(f"(not (dark {name}))")        # comfort: light it
        if band != "ok":
            # Air quality: clear BOTH bands, so that from "high" the planner
            # genuinely chooses between [full_ventilate] and two pulses.
            goal.append(f"(not (co2_high {name}))")
            goal.append(f"(not (co2_elevated {name}))")
        if break_due:
            goal.append(f"(break_suggested {name})")   # break hygiene: nudge
    else:
        if lamp_on:
            goal.append(f"(not (lamp_on {name}))")     # energy: switch off

    return {"name": name, "init": init, "goal": goal,
            "facts": {"occupied": occupied, "dark": dark,
                      "co2_band": band, "break_due": break_due,
                      "lamp_on": lamp_on}}


class Generator:
    def __init__(self) -> None:
        env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                          trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
        self.template = env.get_template("problem.pddl.j2")
        self.serial = 0

    def render(self, state: dict, lamp_states: dict) -> tuple[str, dict, list, dict]:
        # Simulated zones (added by tools/mock_sensors.py for the dashboard
        # floor plan) are display-only: they never enter planning, so the
        # physical actuators only ever act on real zones.
        zones = {name: z for name, z in state.get("zones", {}).items()
                 if not z.get("simulated")}
        zone_facts = [discretise_zone(name, z, lamp_states.get(name, False))
                      for name, z in zones.items()]

        # Ventilation action costs from live outdoor temperature (weather
        # sensor); falls back to a mild default when absent (hotspot mode).
        outdoor_t = state.get("outdoor", {}).get("outdoor_temp_c")
        pulse_cost, full_cost = vent_costs(outdoor_t)
        costs = {"pulse_vent": pulse_cost, "full_vent": full_cost,
                 "outdoor_temp_c": outdoor_t}

        # Build the init/goal blocks as plain text (one atom per line, 4-space
        # indent) so PDDL line-comments never collide with facts.
        init_lines: list[str] = [
            "    ;; ventilation costs (weather-based, window-control report)",
            f"    (= (pulse-vent-cost) {pulse_cost})",
            f"    (= (full-vent-cost) {full_cost})",
        ]
        goal_lines: list[str] = []
        for z in zone_facts:
            init_lines.append(f"    ;; {z['name']}")
            init_lines.extend(f"    {fact}" for fact in z["init"])
            goal_lines.extend(f"    {g}" for g in z["goal"])

        self.serial += 1
        problem = self.template.render(
            serial=self.serial,
            stamp=datetime.now(timezone.utc).isoformat(),
            zones=list(zones.keys()) or ["reading-1"],
            init_block="\n".join(init_lines),
            goal_block="\n".join(goal_lines),
        )
        digest = {z["name"]: z["facts"] for z in zone_facts}
        goals = [g.strip() for z in zone_facts for g in z["goal"]]
        return problem, digest, goals, costs


def main() -> None:
    broker = yaml.safe_load(open(TOPICS))["broker"]
    gen = Generator()
    state_holder: dict = {}
    lamp_states: dict = {}
    last_digest: dict | None = None
    last_emit = 0.0

    def on_connect(c, u, f, rc, p):
        c.subscribe("library/state")
        c.subscribe("library/actuators/#")
        print("[problem_gen] subscribed to library/state + library/actuators/#")

    def on_message(c, u, msg):
        try:
            payload = json.loads(msg.payload)
        except ValueError:
            return
        if msg.topic == "library/state":
            state_holder.clear()
            state_holder.update(payload)
        elif msg.topic.startswith("library/actuators/"):
            # e.g. library/actuators/lamp -> {"zone": "reading-1", "on": true}
            zone = payload.get("zone")
            if zone is not None and "on" in payload:
                lamp_states[zone] = bool(payload["on"])

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"{broker.get('client_id_prefix','librisense')}-problemgen")
    client.on_connect = on_connect
    client.on_message = on_message
    host, port = broker["host"], broker.get("port", 1883)
    while True:
        try:
            client.connect(host, port, 60)
            break
        except OSError:
            time.sleep(5)
    client.loop_start()
    print(f"[problem_gen] connected to {host}:{port}")

    try:
        while True:
            now = time.monotonic()
            if state_holder.get("zones"):
                problem, digest, goals, costs = gen.render(state_holder, lamp_states)
                signature = (digest, costs["pulse_vent"], costs["full_vent"])
                changed = signature != last_digest
                if changed or (now - last_emit) >= HEARTBEAT_S:
                    msg = {"ts": datetime.now(timezone.utc).isoformat(),
                           "facts": digest, "goals": goals, "costs": costs,
                           "problem": problem}
                    client.publish("library/problem", json.dumps(msg))
                    last_digest = signature
                    last_emit = now
                    if changed:
                        print(f"[problem_gen] emitted problem (changed): "
                              f"goals={goals or '[] (nothing to do)'} "
                              f"costs={costs}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[problem_gen] stopping")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
