# How LibriSense is controlled — team catch-up

A one-page mental model of the running system. For the operational details
(services, IPs, demo procedure) see [RUNNING.md](RUNNING.md) and
[DEMO.md](DEMO.md).

## The idea in one sentence

LibriSense is a **closed control loop**: it senses the room, builds a world
state, an **AI planner (PDDL + Fast Downward)** decides which actions are
cost-optimal right now, and those actions become **physical effects** — then
the sensors see the result and the loop repeats. Nothing is hard-coded
if-then; the *what we want* (goals + costs) is declared and the planner works
out the *how*.

## The control loop (who talks to whom)

Everything communicates **only over MQTT** (Mosquitto broker on the Core Pi).
No module calls another directly — they publish/subscribe to topics. This is
the "indirect communication" + "modularity" the course requires.

```
   SENSE                     THINK                          ACT
 ┌────────┐   sensors/*   ┌────────────┐  state   ┌──────────────┐ problem
 │  IoT   │ ───────────▶  │ Processing │ ───────▶ │ Problem-Gen  │ ──────┐
 │ (Edge) │               │  (Core)    │          │   (Core)     │       │
 └────────┘               └────────────┘          └──────────────┘       ▼
     ▲                     world state:                            ┌────────────┐
     │ actions             occupancy, light,                       │  Planner   │
     │                     CO2 proxy, comfort,                      │ Fast Downw.│
 ┌────────┐   actions     focus-session phase                      │  (Core)    │
 │Executor│ ◀───────────────────────────────────── plan ───────────└────────────┘
 │ (Core) │ ──▶ actions ──▶ Actuators (Edge): lamp relay, LED, buzzer
 └────────┘                 + LCD shows state, Dashboard shows state+plan
```

### Step by step

1. **IoT layer (Edge Pi)** reads the GrovePi sensors at 2 Hz and publishes to
   `library/sensors/*`: motion (occupancy), light (%). Software/simulated
   sensors add weather (Open-Meteo, Core) and a CO₂ proxy.
2. **Processing (Core)** subscribes to all sensors, smooths them, and computes
   the **world state** → `library/state` (2 Hz, retained):
   occupancy, light %, CO₂ proxy (rises while occupied, drops when ventilated),
   a comfort index (light + air), and the **focus-session phase**
   (idle → focusing → break_due, the Pomodoro learner FSM).
3. **Problem generator (Core)** turns the world state into a **ground PDDL
   problem** → `library/problem`. It discretises the numbers (dark = light
   < 40 %, CO₂ high > 1000 ppm) and picks the *active goals* for the situation
   (only goals an action can actually achieve).
4. **Planner (Core)** runs **Fast Downward** (A*, LM-cut, optimal) on the
   problem and publishes the cost-optimal action sequence → `library/plan`
   (retained). Typically solves in ~130 ms.
5. **Executor (Core)** dispatches the plan's actions → `library/actions`.
6. **Actuators (Edge)** carry them out physically and report state back, which
   feeds the next planning cycle (e.g. lamp state → problem generator).

## What actually controls what (the decisions)

The planner's domain has four actions with **costs** (energy/comfort
trade-off). Which it picks depends on the live state:

| Situation (world state)                    | Planner decides        | Physical effect |
|--------------------------------------------|------------------------|-----------------|
| occupied **and** dark **and** lamp off     | `turn_on_lamp`         | Plugwise relay → reading lamp ON |
| **not** occupied **and** lamp on           | `turn_off_lamp`        | relay → lamp OFF (energy saving) |
| occupied **and** CO₂ high                  | `ventilate`            | (virtual) → CO₂ proxy drops |
| occupied **and** focus-session ≥ 2 min     | `suggest_break`        | break LED on + quiet buzzer beep (re-beeps every 20 s) |
| environment already fine                   | empty plan             | nothing — energy-optimal |

Edge cases are handled honestly: if the lamp is already on but it's still dark
(lamp doesn't brighten the sensor), no impossible goal is set. When occupancy
clears for ~30 s the focus session resets (break taken / person left).

## Where it runs

- **Edge Pi (Pi 3 B+):** IoT layer — sensor reads + GrovePi actuators
  (LED, buzzer) + Plugwise lamp relay + local LCD. Services: `librisense-sensors`,
  `librisense-lcd`, `librisense-actuator`.
- **Core Pi (Pi 5):** broker + brains. Services: `mosquitto`,
  `librisense-weather`, `-processing`, `-problemgen`, `-planner`, `-executor`,
  `-dashboard`.
- Two physical machines, MQTT over WiFi (or the Core's own hotspot at the demo).
  All services auto-start on boot (systemd).

## How to see it

- **Dashboard:** `http://librisense-core.local:8000` (home) /
  `http://10.42.0.1:8000` (hotspot) — live world state **and** the current AI
  plan (satisfies the "current state + latest plan" visualisation requirement).
- **LCD on the Edge:** 2-line live status + CO₂ traffic-light backlight
  (green/amber/red) — visible with no laptop.

## Why a planner and not just rules? (honest note for the report)

For this small, reactive domain, rule-based control would also work — we say
so openly. AI planning is a **course requirement**, and its genuine advantage
(optimal trade-offs under shared constraints, multi-step reasoning) would only
become decisive with more zones/actuators and a shared energy budget. The
declarative goals+costs design is clean and the planner is correct and fast;
the critical reflection on *when* planning beats rules goes in the report.
