# LibriSense — Project Report (submission draft)

**Purpose of this document.** Copy-paste-ready content for every field of the
official `Project_Report_Form.pdf` (due **14 July 2026**, ILIAS, non-editable
PDF export). Structure follows the form page by page. Each box has a tight
**Form text** (the form's boxes are small and the guidelines demand adhering to
character limits — shorten from the end if a box overflows), plus background
notes the team can use in the demo Q&A.

Everything below states only what is **implemented and verified** on the real
system (commit `1c762bb`, 2026-07-12). Grading criteria (course slides 36):
clarity, precision, compliance; extent of requirement satisfaction.

---

## Page 1 — Project Information

| Field | Value |
|---|---|
| Student 1 | Dennis Gunt — ID: **[fill in]** |
| Student 2 | Haoyang Chen — ID: **3854758** |
| Student 3 | Niclas **[surname]** — ID: **[fill in]** |
| Group ID | **[assigned by course — fill in]** |
| Project Title | **LibriSense — An Adaptive Smart Library** |
| Domain | ☑ **Smart building** |
| Code Repository Link | https://github.com/Dennis1911/librisense ⚠️ *repo is private — make it public before submission or invite the lecturer as collaborator!* |

**Type** (form text):

> Non-residential educational building: a university library reading room.
> One instrumented reading zone (desk scale) demonstrates the concept; the
> architecture is zone-generic and extends to multiple reading zones.

**Project Description — Monitoring** (form text):

> The system continuously monitors: (i) room occupancy via an analog motion
> sensor (2 Hz); (ii) illuminance via a light sensor (2 Hz); (iii) indoor air
> quality via a simulated CO₂ proxy driven by occupancy over time
> (ASHRAE-style ramp, coupled to ventilation actions); (iv) outdoor weather
> (temperature, humidity, cloud cover) via a web API; and (v) each learner's
> focus-session state through a four-state Pomodoro FSM
> (idle / focused / break-due / on-break) derived from continuous occupancy.

**Project Description — Automation** (form text):

> An AI planner (Fast Downward, cost-optimal) closes the loop and controls:
> (i) the reading lamp via a ZigBee smart-plug relay — switched on when the
> zone is occupied and dark, off when the zone empties (energy saving);
> (ii) leveled ventilation — a short pulse or a full airing chosen
> cost-optimally from live outdoor temperature (heat-loss model), lowering
> the CO₂ proxy; (iii) break reminders — LED plus quiet PWM buzzer nudges,
> escalating gently while a break stays due. A manual disturbance (lamp
> switched off while the zone is occupied and dark) is autonomously
> corrected in under one second.

**Project Description — Objective** (form text):

> Transform a library reading zone into an adaptive environment that
> autonomously balances four competing objectives: (1) learner focus and
> cognitive well-being — evidence-based break rhythms enforced by escalating
> nudges; (2) physical comfort — sufficient illuminance and acceptable air
> quality; (3) energy efficiency — lights off in empty zones, and
> weather-aware ventilation strategies that minimise heating losses
> (short pulses on cold days, one full airing on warm days); (4) transparency
> — the current world state and the currently executing plan are always
> visible on a live dashboard and an on-site LCD.

---

## Page 2 — System Design

**Checkboxes:** ☑ IoT · ☑ Context · ☑ Problem generation · ☑ Planning ·
☑ Execution · ☑ Broker · ☐ Knowledge base · ☑ Other: **Visualisation**

**Functionality texts** (one line per component, form text):

> **IoT:** Sensor drivers sample motion + light at 2 Hz and publish
> normalised JSON; actuator drivers switch the ZigBee lamp relay, LED,
> buzzer, LCD and virtual ventilation on planner actions, publishing their
> state back (retained) as feedback.

> **Context (processing):** Aggregates sensor streams over sliding windows
> into a world state (2 Hz): debounced occupancy, smoothed illuminance,
> simulated CO₂ proxy, comfort index, and a 4-state learner-session FSM.

> **Problem generation:** Discretises the world state (light < 40 %; CO₂
> bands 800/1100 ppm), derives the situationally active goals, computes
> weather-based ventilation action costs, and renders a ground PDDL problem
> on every state change (or 30 s heartbeat).

> **Planning:** Runs Fast Downward (A* + LM-Cut, cost-optimal) on each
> instance and publishes the plan; empty-goal short-circuit and
> unsolvable/timeout handling included.

> **Execution:** Dispatches the current plan's actions to the actuator
> topic, deduplicating unchanged plans; re-planning on every state change
> closes the loop.

> **Broker:** Eclipse Mosquitto; all inter-module communication is
> publish/subscribe over namespaced topics, latest-value topics retained.

> **Other — Visualisation:** Web dashboard (current state, latest plan with
> cost and solve time, seat heatmap, Pomodoro rings, 30-min trend charts)
> plus an on-site LCD with a CO₂ traffic-light backlight.

**System Architecture Diagram:** use `docs/architecture_asbuilt.svg`
(export to PNG for the form). Logical view, deployment-independent, shows all
seven components around the MQTT broker with their publish/subscribe topics
and the closed control loop. *(Do not reuse the proposal diagram — it shows
the originally planned Sense-HAT hardware, not the as-built system.)*

---

## Page 3 — System Distribution

**Checkbox:** ☑ 2+ machines

**Type** (form text):

> Machine 1 ("core"): Raspberry Pi 5. Machine 2 ("edge"): Raspberry Pi 3
> Model B+. Connected over Wi-Fi/LAN; for untethered demos the core Pi
> automatically becomes a Wi-Fi access point that the edge Pi and the
> dashboard client join (self-contained two-machine network).

**Components** (form text):

> Core (Pi 5): MQTT broker (Mosquitto), context/processing, problem
> generator, AI planner (Fast Downward), execution engine, weather
> software-sensor, dashboard backend — 7 services. Edge (Pi 3 B+): sensor
> drivers (motion, light), actuator drivers (lamp relay via Plugwise USB
> stick, LED, buzzer), local LCD display — 3 services. All ten run as
> auto-restarting systemd units and start on boot.

## Page 3 — IoT

**Sensors (4 rows + other):**

| Sensor | Classification |
|---|---|
| Occupancy / motion (Grove analog motion sensor) | **Physical** |
| Illuminance (Grove light sensor) | **Physical** |
| Indoor CO₂ concentration (proxy from occupancy × time, ASHRAE-style ramp; responds to ventilation actions) | **Simulated** |
| Outdoor weather: temperature, humidity, cloud cover (Open-Meteo REST API, 10-min polling) | **Software-based** |

**Other sensors** (form text):

> Learner focus-session state: a software-based sensor derived from
> continuous occupancy — a four-state FSM (idle / focused / break-due /
> on-break) with session timing, occupancy grace (15 s) and reset gap (30 s).
> Total: 5 sensors, 2 physical.

**Actuators (4 rows + other):**

| Actuator | Classification |
|---|---|
| Reading lamp (Plugwise Circle+ ZigBee smart-plug relay switching a real lamp) | **Physical** |
| Break-reminder LED (Grove LED) | **Physical** |
| Break-reminder buzzer (Grove buzzer, PWM volume-limited) | **Physical** |
| Status display (Grove LCD RGB: live state + CO₂ traffic-light backlight) | **Physical** |

**Other actuators** (form text):

> Ventilation: a virtual actuator (no window/fan hardware in the kit) with
> two levels — short pulse and full airing — that lower the simulated CO₂
> proxy for 12 s / 45 s respectively. Break banner: software actuator on the
> dashboard. Total: 6 actuators, 4 physical.

---

## Page 4 — System Integration

**Mechanism:** ☑ **Publish-subscribe** (☐ message queue, ☐ one-to-one)

**Messaging Middleware:** ☑ Other: **Eclipse Mosquitto**

**Protocol:** ☑ **MQTT**

**Indirect communication explanation** (form text):

> Every component communicates exclusively via the Mosquitto broker — no
> module calls another directly, none knows another's address. Namespaced
> topics form the pipeline: library/sensors/# → library/state →
> library/problem → library/plan → library/actions → library/actuators/#
> (actuator feedback re-enters problem generation, closing the loop).
> Latest-value topics (state, plan, weather, actuator states) are published
> retained, so late-joining or restarting modules synchronise immediately.
> This decoupling let us develop, restart and even replace modules
> independently (e.g. dashboard development against a mock publisher,
> without any hardware).

## Page 4 — Visualisation

**What is displayed:** ☑ Latest plan generated · ☑ Current state ·
☐ User control · ☑ Other

**Current state — briefly specify** (form text):

> Live web dashboard (WebSocket, 2 Hz): per-zone occupancy, illuminance,
> CO₂ proxy with colour coding, comfort index, learner-session phase and
> minutes (Pomodoro rings), seat heatmap, 30-minute trend charts
> (light / CO₂ / comfort), outdoor weather, and current lamp state.

**Other — briefly explain** (form text):

> The latest plan card shows the planner's status, the optimal action
> sequence with human-readable labels, plan cost and solve time. An on-site
> Grove LCD additionally displays occupancy, light, CO₂ and comfort with a
> traffic-light backlight (green/amber/red by CO₂ band) directly in the
> reading zone — visualisation without any client device.

---

## Page 5 — AI Planning

**AI Planning Technique:** ☑ **Classical planning** *(with action costs;
continuous quantities are discretised in the processing/problem-generation
layers — see Domain Model)*

**AI Planner — name and link** (form text):

> Fast Downward (A* search with the admissible LM-Cut heuristic,
> configuration `astar(lmcut())`) — https://www.fast-downward.org

**Why appropriate** (form text):

> Fast Downward is the de-facto reference system for classical planning:
> sound, complete, and with A*+LM-Cut provably cost-optimal. Our world
> model is naturally discretisable (occupancy, light comfort, CO₂ bands,
> break state), so classical planning with action costs fits exactly, and
> optimality matters: ventilation costs are injected per problem instance
> from live outdoor temperature, and the planner genuinely decides between
> strategies (one full airing vs. two short pulses) by cost. Verified: at
> 25 °C outdoors the optimal plan is [full_ventilate] (cost 4); at 5 °C it
> switches to [pulse_ventilate_step, pulse_ventilate] (cost 6 vs. 12) — the
> classic winter-airing recommendation, derived by optimisation instead of
> hand-written rules. Solved in ~130 ms per instance on a Raspberry Pi 5,
> fast enough to re-plan on every state change.

**Domain Model — main components** (form text):

> One type (zone). Eight predicates model the discretised environment and
> learner state: occupied, lamp_on, dark, co2_elevated, co2_high,
> ventilating, break_due, break_suggested. Six actions with costs encode
> the objectives: turn_on_lamp (comfort, 2), turn_off_lamp (energy, 1),
> suggest_break (break hygiene, 1), pulse_ventilate /
> pulse_ventilate_step / full_ventilate (air quality). Ventilation costs
> are numeric fluents (pulse-vent-cost, full-vent-cost) set per problem
> instance from outdoor temperature using the heat-loss relation
> Q_loss ∝ Q_v · (T_in − T_out), so cold weather makes long airing
> expensive. Metric: minimize total-cost.

**Problem Instance — initial state** (form text):

> Ground atoms from the discretised live world state: occupancy (motion,
> debounced), dark iff illuminance < 40 %, exactly one CO₂ band atom
> (elevated ≥ 800 ppm, high ≥ 1100 ppm), lamp_on from retained actuator
> feedback, break_due from the learner FSM — plus (= total-cost 0) and the
> two weather-derived ventilation cost fluents.

**Problem Instance — goal** (form text):

> Goals are situational: if the zone is occupied — not dark (only when the
> lamp is off, i.e. an achieving action exists), CO₂ cleared to the ok band,
> and break_suggested when a break is due; if the zone is empty — lamp off
> (energy). The generator only emits achievable goals, so instances are
> always solvable; an empty goal set means "environment optimal" and skips
> the planner call.

**Problem instances are generated:** ☑ **Other** (form text):

> Whenever the discretised world state or the weather-based action costs
> change, plus a 30-second heartbeat re-emission as a safety net.

---

## Implementation (report section / Q&A backup)

**Languages & stack.** Python 3.13 throughout (paho-mqtt 2.x, Jinja2,
FastAPI + uvicorn + WebSockets, smbus2, plugwise-usb); vanilla-JS dashboard
with a locally bundled Chart.js (fully offline-capable); Fast Downward built
from source (C++) on the Pi 5; Eclipse Mosquitto 2.0.21.

**Deployment.** Ten systemd services (7 core, 3 edge), all enabled at boot
with restart-on-failure — the whole system survives power cycles unattended.
Broker addressing is resilient: mDNS hostname at home, automatic fallback to
the access-point gateway IP (10.42.0.1) in hotspot demo mode.

**Noteworthy engineering (honest lessons).**
- *GrovePi clock-stretching:* the vendor Python library is broken on
  current kernels; we wrote a minimal raw-I²C driver (i2c_rdwr transactions,
  50 kHz bus) — analog reads became reliable.
- *Sound sensor removed:* the GrovePi's I²C path samples at ~10–200 Hz —
  far too slow to estimate loudness from a raw microphone waveform. Measured
  loud ≈ quiet, so we removed the sensor rather than publish noise as data;
  acoustic control from the preliminary window-control study remains
  design-only.
- *Unsatisfiable goals:* an early bug set "not dark" as goal while the lamp
  was already on (no achieving action). The generator now only emits goals
  an action can achieve — planner instances are solvable by construction.
- *Retained topics:* late joiners (dashboard, generator after restart) get
  the current state/plan/actuator facts instantly.
- *Ventilation realism:* planner ventilation actions open a timed decay
  window on the CO₂ proxy (12 s pulse / 45 s full), so the simulated air
  quality actually responds to decisions and goals clear.

**Verified results (measurements on the real system).**
- End-to-end closed loop across two machines: sensor → state → PDDL →
  optimal plan → MQTT → physical relay switching a real lamp.
- Disturbance rejection: lamp manually switched off while occupied+dark →
  re-planned and physically re-lit in **< 1 s** (0.7 s plan, 0.1 s actuation).
- Planner: ~**130 ms** per invocation on the Pi 5 (search itself < 2 ms).
- Weather-dependent strategy switch (see AI Planning) validated with both
  hand-written and generator-emitted instances.
- Untethered demo mode: core Pi auto-becomes Wi-Fi AP, edge auto-joins,
  sensor data verified flowing over the AP; automatic revert at home.

**Team integration.** The dashboard (heatmap, Pomodoro rings, trends, mock
tooling) and the 4-state learner FSM were contributed via feature branch and
merged after review; the preliminary window-control planning study
(`docs/Window_Control_Preliminary_Report.pdf`) was realised as the CO₂
banding + leveled-ventilation cost model inside the planning pipeline.

---

## SHORT versions (use these where a box overflows / text gets tiny)

Compact texts for the small form boxes. No em-dashes, plain sentences.

**Type:**
> Non-residential educational building: a university library reading room.
> One instrumented reading zone at desk scale; the architecture is
> zone-generic.

**Monitoring:**
> Occupancy (motion sensor, 2 Hz), illuminance (light sensor, 2 Hz),
> indoor CO2 as a simulated proxy driven by occupancy and ventilation,
> outdoor weather via web API, and each learner's focus-session state
> (4-state Pomodoro FSM derived from occupancy).

**Automation:**
> A cost-optimal AI planner controls the reading lamp (ZigBee relay: on
> when occupied and dark, off when empty), leveled ventilation (short
> pulse or full airing, chosen by weather-based cost), and escalating
> break reminders (LED and quiet buzzer). A manual disturbance is
> corrected autonomously in under one second.

**Objective:**
> Autonomously balance four objectives in a library reading zone: learner
> focus (enforced break rhythm), physical comfort (light and air quality),
> energy efficiency (lights off when empty, weather-aware ventilation),
> and transparency (live dashboard and on-site LCD always show state and
> current plan).

**Component functionality (one-liners):**
> IoT: samples motion and light at 2 Hz, drives lamp relay, LED, buzzer,
> LCD and virtual ventilation, reports actuator state back (retained).
> Context: aggregates sensors into a world state at 2 Hz with occupancy,
> CO2 proxy, comfort index and a 4-state learner FSM.
> Problem generation: discretises the state, picks the active goals,
> computes weather-based action costs, renders ground PDDL on change.
> Planning: Fast Downward (A* with LM-Cut) returns cost-optimal plans.
> Execution: dispatches plan actions, deduplicates unchanged plans.
> Broker: Mosquitto; all communication is publish/subscribe.
> Visualisation: web dashboard (state, plan, heatmap, trends) and LCD.

**Machines (Type):**
> Machine 1: Raspberry Pi 5 (core). Machine 2: Raspberry Pi 3 B+ (edge).
> Networked via WiFi/LAN; for untethered demos the core Pi becomes a WiFi
> access point that the edge Pi and the dashboard client join.

**Machines (Components):**
> Core Pi 5: broker, context, problem generator, planner, execution,
> weather sensor, dashboard (7 services). Edge Pi 3 B+: sensor drivers,
> actuator drivers, LCD (3 services). All run as auto-restarting systemd
> units.

**Indirect communication:**
> All modules communicate only via the Mosquitto broker over namespaced
> topics (sensors, state, problem, plan, actions, actuators). No module
> knows another's address. Latest-value topics are retained so restarting
> modules resynchronise instantly. Actuator feedback re-enters problem
> generation, closing the loop.

**Visualisation, current state:**
> Live dashboard (WebSocket, 2 Hz): occupancy, light, CO2, comfort,
> session phase per zone, seat heatmap, 30-minute trend charts, outdoor
> weather and lamp state.

**Visualisation, other:**
> Plan card with the optimal action sequence, plan cost and solve time.
> An on-site LCD shows state plus a CO2 traffic-light backlight directly
> in the reading zone.

**AI planner name/link:**
> Fast Downward, A* with LM-Cut heuristic, cost-optimal.
> https://www.fast-downward.org

**Why appropriate:**
> Reference system for classical planning: sound, complete, cost-optimal
> with A* and LM-Cut. Our discretised world model fits classical planning
> with action costs exactly. Optimality matters: ventilation costs come
> from live outdoor temperature, and the planner chooses between one full
> airing (warm) and two short pulses (cold) purely by cost. About 130 ms
> per instance on a Pi 5, fast enough to re-plan on every state change.

**Domain model:**
> One type (zone); 8 predicates for the discretised environment and
> learner state; 6 cost-annotated actions (lamp on/off, suggest break,
> pulse/full ventilation). Ventilation costs are fluents set per instance
> from outdoor temperature (heat-loss model). Metric: minimize total-cost.

**Initial state:**
> Ground atoms from the discretised live state: occupancy, dark (below
> 40 percent light), one CO2 band atom (800/1100 ppm thresholds), lamp
> state from retained actuator feedback, break_due from the learner FSM,
> plus the two weather-derived cost fluents.

**Goal:**
> Situational: when occupied, brightness (only if the lamp is off), CO2
> cleared to the ok band, and a break suggestion when due; when empty,
> lamp off. Only achievable goals are emitted, so instances are always
> solvable; an empty goal set skips the planner.

**Problem instances generated (Other):**
> Whenever the discretised state or the weather-based action costs
> change, plus a 30-second heartbeat as a safety net.

---

## Submission checklist

- [ ] Fill in: Dennis's + Niclas's student IDs, Niclas's surname, Group ID
- [ ] **Repo access:** make https://github.com/Dennis1911/librisense public
      (or invite the lecturer) — the form links to it!
- [ ] Export `docs/architecture_asbuilt.svg` → PNG (open in browser,
      screenshot or `rsvg-convert`), insert into the diagram box
- [ ] Paste the **Form text** blocks into the PDF form; check each box's
      character limit and trim from the end if needed
- [ ] Export as **non-editable PDF**, upload to ILIAS **by 14 July**
- [ ] (Parallel, 5 min when Pis reachable): deploy commit `1c762bb` — core:
      `git pull` + restart problemgen/processing/planner; edge: `git pull` +
      restart actuator
