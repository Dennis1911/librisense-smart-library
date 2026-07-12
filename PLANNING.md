# LibriSense — Project Planning

_Last updated: 2026-05-21_

This file is the **single source of truth** for what we are building, in what order, and who owns each piece. It maps the [proposal](docs/LibriSense_Proposal.docx) onto concrete sprint tasks, decisions, and open questions. Update it as we go — don't let it drift from reality.

---

## 1 · Project at a glance

**Goal.** Transform a traditional library reading room into an adaptive learning environment that autonomously optimises four competing objectives:

1. Learner focus & cognitive well-being (Pomodoro 25/5, long break every 4 cycles)
2. Physical comfort (illuminance, temperature, CO₂ in ergonomic ranges)
3. Energy efficiency (switch off in unoccupied zones, re-use daylight)
4. Privacy & user agency (every action overridable, no biometric data leaves edge)

**Six course requirements covered.**

| # | Requirement        | How we cover it                                                                 |
|---|--------------------|---------------------------------------------------------------------------------|
| 1 | System Design      | 6 strongly-decoupled modules, MQTT-only communication                           |
| 2 | System Integration | Mosquitto + MQTT pub/sub, namespaced topics, JSON schema                        |
| 3 | IoT                | ≥ 7 sensors + ≥ 6 actuators (physical + software + simulated)                   |
| 4 | AI Planning        | PDDL 2.1 with numeric fluents + durative actions, Fast Downward, auto-generated problems |
| 5 | Visualisation      | React + WebSocket dashboard: heatmap, trend charts, plan Gantt, overrides       |
| 6 | System Distribution| Edge Pi + Core node + optional kiosk, MQTT across LAN                           |

---

## 2 · Architecture in one sentence

Sensors publish to MQTT → **Processing** snapshots world state → **Problem Generator** materialises a PDDL problem → **Planner** solves it → **Execution** dispatches the next action → actuators react → **Dashboard** renders state + plan live.

See [docs/LibriSense_Architecture.png](docs/LibriSense_Architecture.png) for the full diagram.

### MQTT topic map (draft)

| Topic                          | Direction         | Payload (JSON)                                |
|--------------------------------|-------------------|-----------------------------------------------|
| `library/sensors/<type>`       | edge → broker     | `{ ts, zone, value, unit }`                   |
| `library/state`                | processing → all  | World-state snapshot (zones + users + env)   |
| `library/problem`              | gen → planner     | path or inline PDDL problem                   |
| `library/plan`                 | planner → all     | Ordered action list with start/end times      |
| `library/actions`              | execution → edge  | `{ action, params, deadline }`                |
| `library/overrides`            | dashboard → all   | User override → planner holds for ≥ 2 min     |

---

## 3 · Module ownership & deliverables

| Module                  | Lead           | Sprint window | Definition of done                                                |
|-------------------------|----------------|---------------|--------------------------------------------------------------------|
| 1 · IoT layer           | _TBD_          | Sprint 1      | All sensors publish at 1 Hz; all actuators react to test commands  |
| 2 · Processing          | _TBD_          | Sprint 2      | Stable world-state snapshot at 1 Hz, learner FSM unit-tested       |
| 3 · Problem generator   | Dennis         | Sprint 3      | Generates valid PDDL problem from any `library/state` snapshot     |
| 4 · Planner             | Dennis         | Sprint 3      | Fast Downward returns plan ≤ 2 s for nominal instance              |
| 5 · Execution           | _TBD_          | Sprint 4      | Closed-loop: drift > 10 % triggers re-plan within 3 s              |
| 6 · Visualisation       | _TBD_          | Sprint 2 → 4  | Heatmap + trends + plan Gantt + override drawer, ≤ 1 s lag         |

> **Assign module leads between Dennis, Haoyang and Niclas at the first stand-up.**

### Team

| Name           | Student ID  | GitHub                                              |
|----------------|-------------|-----------------------------------------------------|
| Dennis Gunt    | _TBD_       | [@Dennis1911](https://github.com/Dennis1911)        |
| Haoyang Chen   | 3854758     | [@wandering2025](https://github.com/wandering2025)  |
| Niclas _TBD_   | _TBD_       | [@niclmit](https://github.com/niclmit)              |

---

## 4 · Sprint plan

Two-week sprints, Monday stand-up + Friday demo to the group. All code on GitHub with Actions running per-module tests on push.

### Sprint 0 — Setup (now → 2026-05-05)

- [x] Repo scaffolded with module skeleton
- [x] Reference docs committed to `docs/`
- [x] Pushed to GitHub: <https://github.com/Dennis1911/librisense> (private)
- [x] Collaborators invited: [@wandering2025](https://github.com/wandering2025), [@niclmit](https://github.com/niclmit)
- [x] Device-preference bid submitted by **2026-05-01**
- [x] **IoT kit collected on 2026-05-21** — see [docs/HARDWARE.md](docs/HARDWARE.md)
- [x] **Both Pis provisioned (2026-05-30)** — Pi 5 Core + Pi 3 B+ Edge, both on Ethernet, see [config/network.yaml](config/network.yaml)
  - Core: Mosquitto broker, Python venv, Node 20, Fast Downward built + tested
  - Edge: I2C/SPI on, Python venv, grovepi + plugwise installed
- [x] **End-to-end MQTT Edge → Core verified** — Sprint 0 exit criterion met
- [ ] Verify GrovePi+ kit contents against checklist in [docs/HARDWARE.md](docs/HARDWARE.md)
- [ ] Mount GrovePi+ shield on Edge (I2C 0x04 not yet detected)
- [ ] Add `LICENSE` (MIT or similar) and basic CI workflow
- [ ] Pick comms channel (Discord / Teams / Signal) and pin repo link

### Sprint 1 — IoT layer (2026-05-06 → 2026-05-20)

- [x] Bring up Mosquitto on Core node, topic schema in `config/topics.yaml`
- [x] Python-3-safe GrovePi I/O layer (`modules/iot/grovepi_io.py`) — works around
      the BCM2835 clock-stretching bug via raw `i2c_rdwr` + `i2c_arm_baudrate=50000`
- [x] GrovePi sensor drivers: **A0 motion, A1 sound, A2 light** — live, publishing
      to `library/sensors/*` at 1 Hz (`modules/iot/sensor_publisher.py`)
- [x] Grove LCD RGB display on I2C-3 (0x3e/0x62) — text + colour verified
- [x] Device map in `config/devices.yaml` (live-verified ports)
- [ ] Software sensors: weather API client, CO₂ proxy formula (ASHRAE)
- [ ] Plugwise smart-switch driver: on/off (1 Circle plugged in, USB stick at /dev/ttyUSB0)
- [ ] LED + buzzer + relay drivers (if present in kit — verify)
- [ ] Smoke-test script: round-trip command → actuator → sensor effect

**Note:** no DHT (temp/humidity) and no physical light→lux calibration in our kit.
Temp/humidity will be software/simulated; light published as raw + 0..100 %.

**Exit criterion.** A `make smoke` shows every sensor publishing and every actuator reacting via MQTT.

### Sprint 2 — Processing + Dashboard v1 (2026-05-21 → 2026-06-07)

- [x] State aggregator: sliding-window per zone (`modules/processing/state_aggregator.py`),
      publishes `library/state` @ 1 Hz — **live on Core as a systemd service**
- [x] CO₂ proxy from occupancy × time (ASHRAE-style ramp/decay) — working
- [x] Comfort index (light + noise weighted) — working
- [ ] Learner FSM: `idle → focused → break-due → on-break`
- [ ] Persist 24 h of samples (SQLite or InfluxDB — **decision needed**)
- [ ] Dashboard v1: floor-plan heatmap + trend charts via WebSocket
- [ ] Override drawer (publishes to `library/overrides`)

**Exit criterion.** Dashboard renders live state with ≤ 1 s lag; learner FSM survives a 1 h replay fixture without drift.

### Sprint 3 — AI Planning (2026-06-08 → 2026-06-24)  ✅ DONE (2026-06-10)

- [x] PDDL domain (`pddl/domain/librisense.pddl`) — classical + action costs.
      **Design note:** classical-with-costs (not PDDL 2.1 numeric/durative),
      because Fast Downward `seq-opt-lmcut`/`astar(lmcut())` is an optimal
      *classical* planner. Continuous values are discretised in processing.
- [x] Jinja2 problem template (`pddl/templates/problem.pddl.j2`)
- [x] Problem generator service: `library/state` → ground PDDL → `library/problem`,
      situational goal selection, on change or every 30 s
- [x] Fast Downward subprocess wrapper → `library/plan`, empty-goal short-circuit,
      unsolvable/timeout/error handling
- [x] Domain validation: positive (feasible → plan) + negative (unsatisfiable
      goal handled — see the lamp-already-on bug we caught + fixed)
- [x] Current plan rendered in the dashboard (action queue + status + cost)

**Exit criterion MET.** Planner emits a plan in ~130 ms; dashboard shows the
current plan + state live.

### Sprint 4 — Execution + closed loop (2026-06-25 → 2026-07-06)

- [x] Execution engine: dispatch plan actions on `library/actions` (dedup unchanged)
- [x] Actuator service: `library/actions` → Plugwise Circle+ relay (physical),
      publishes retained `library/actuators/*` state (feeds the problem generator)
- [x] **Closed loop verified**: manual lamp-off disturbance → system autonomously
      re-lit the lamp in < 1 s (occupied+dark → plan turn_on_lamp → physical switch)
- [ ] Drift detection / re-plan on observed divergence (basic loop works via re-plan-on-change)
- [x] Break-reminder nudge: physical **LED (D2) + quiet PWM buzzer (D3)**, re-beep
      every 20 s while break due, auto-clear when occupancy resets. Dashboard
      banner via `library/actuators/break`. (TTS optional — needs a speaker.)
- [x] **4 physical actuators** (lamp, LCD, LED, buzzer) → IoT requirement comfortably met
- [x] **Window-control report integrated (2026-07-12)** — teammate's preliminary
      planning report ([docs/Window_Control_Preliminary_Report.pdf](docs/Window_Control_Preliminary_Report.pdf))
      realised in the planning pipeline: CO₂ bands ok/elevated/high (§8),
      pulse vs. full ventilation as PDDL actions (§9.2), and **weather-based
      action costs** from the heat-loss relation Q_loss ~ Qv·(Tin−Tout).
      Verified with Fast Downward: cold outdoors → optimal plan = two pulses
      (winter strategy), warm → one full airing. This makes the planner's
      cost optimisation genuinely decision-relevant (planning > rules evidence
      for the report). Not realisable with our hardware (documented as design):
      noise-based control (sound sensor removed), physical window actuators,
      people counting, indoor temperature sensor.
- [ ] Drift detector: compare expected vs. observed effects; re-plan if Δ > 10 %
- [ ] Break-reminder escalation policy (t+0 banner, t+60s LED, t+2m buzzer, t+3m TTS)
- [ ] Override grace window (≥ 2 min planner hold)
- [ ] End-to-end demo scenario script

**Exit criterion.** Full pipeline runs hands-off for 30 min including one injected sensor fault and one user override.

### Sprint 5 — Hardening & demo (2026-07-07 → 2026-07-20)

- [ ] 48 h soak test (uptime target ≥ 95 %)
- [ ] Energy-saving benchmark vs. always-on baseline (target ≥ 25 %)
- [ ] Break-reminder compliance log (target ≥ 60 %)
- [ ] Report writing: fill `docs/Project_Report_Form.pdf` and the longer write-up
- [ ] Demo rehearsal (twice), with kiosk setup
- [ ] **2026-07-14:** Report submission
- [ ] **2026-07-20:** Live demo

---

## 5 · IoT inventory

> **Live inventory:** see [docs/HARDWARE.md](docs/HARDWARE.md) — written after the 2026-05-21 collection. The tables below are the original proposal version, kept here for diff reference; trust HARDWARE.md if they disagree.

### Sensors (≥ 4 required — 8 provided)

| Sensor                | Source / bus                | Variable             | Used by planner for                |
|-----------------------|-----------------------------|----------------------|------------------------------------|
| Temperature           | Sense HAT (I²C, physical)   | °C                   | Heating / fan action               |
| Humidity              | Sense HAT (I²C, physical)   | % RH                 | Comfort index                      |
| Pressure              | Sense HAT (I²C, physical)   | hPa                  | Comfort / weather correlation      |
| Illuminance           | GrovePi light (physical)    | lux                  | Lamp dim / on                      |
| Sound level           | GrovePi sound (physical)    | dB(A) proxy          | Disturbance → ventilate / dim      |
| Motion / occupancy    | Grove PIR (physical)        | bool presence        | Gates all actuators per zone       |
| CO₂                   | **Simulated** (occ × time)  | ppm proxy            | Ventilation                        |
| Learner-session state | **Software** (REST to UI)   | focus-minutes, phase | Break actions                      |
| Weather               | **Software** (OpenWeather)  | outdoor °C, cloud    | Pre-conditioning heating           |

### Actuators (≥ 4 required — 6 provided)

| Actuator         | Interface                         | Effect                          | Planner action            |
|------------------|-----------------------------------|---------------------------------|---------------------------|
| Reading lamp     | Plugwise smart switch (ZigBee)    | On/off + PWM dim                | `adjust_light(zone, lvl)` |
| Space heater/fan | Plugwise smart switch (ZigBee)    | Heating on/off                  | `adjust_heating(zone, ±)` |
| Ventilation      | Grove Relay (I²C)                 | Window/fan toggle               | `ventilate(zone)`         |
| Break LED+buzzer | GrovePi LED + buzzer              | Visual + audible alert          | `suggest_short_break(u)`  |
| TTS audio        | **Software** (pyttsx3 / Piper)    | Spoken reminder                 | `suggest_long_break(u)`   |
| Dashboard banner | **Software** (WebSocket → UI)     | Visual on-screen nudge          | `nudge(u, message)`       |

---

## 6 · PDDL design sketch

Domain: `pddl/domain/librisense.pddl` (to be written in Sprint 3).
PDDL 2.1, requirements: `:typing :numeric-fluents :durative-actions`.

**Types.** `zone`, `user`, `device`.
**Predicates.** `(occupied ?z)`, `(lights-on ?z)`, `(heating-on ?z)`, `(ventilating ?z)`, `(session-active ?u)`, `(break-due ?u)`.
**Fluents.** `(temperature ?z)`, `(illuminance ?z)`, `(co2 ?z)`, `(session-minutes ?u)`, `(energy-used)`.
**Actions.** `adjust_light`, `adjust_heating`, `ventilate`, `suggest_short_break`, `suggest_long_break`, `enable_focus_mode`.

**Goal template.**

```lisp
(and (forall (?u - user) (not (break-due ?u)))
     (forall (?z - zone)
        (and (>= (illuminance ?z) 300)
             (<= (temperature ?z) 24)
             (>= (temperature ?z) 20))))
```

**Metric.** `(minimize (+ (* 0.4 (energy-used)) (* 0.6 (total-time))))`.
**Re-plan triggers.** (i) goal violation, (ii) 30 s timer, (iii) drift > 10 %.

---

## 7 · Open decisions (resolve early)

| # | Question                                        | Options                              | Deadline       |
|---|-------------------------------------------------|--------------------------------------|----------------|
| 1 | Remote hosting                                  | GitHub / uni GitLab                  | Before push    |
| 2 | Time-series store                               | SQLite (simple) / InfluxDB (proper)  | Sprint 2 start |
| 3 | Dashboard backend framework                     | FastAPI + socket.io / pure FastAPI WS| Sprint 2 start |
| 4 | TTS engine                                      | pyttsx3 (offline) / Piper (better)   | Sprint 4       |
| 5 | Fallback if Plugwise bid lost                   | Grove Relay + contactor on bench bulb| Bid result day |
| 6 | Floor-plan source for heatmap                   | Hand-drawn SVG / actual library map  | Sprint 2       |

---

## 8 · Risks & mitigations

(Copied from proposal §8 — update if the situation changes.)

| Risk                                  | Likelihood | Impact                                    | Mitigation                                                |
|---------------------------------------|------------|-------------------------------------------|-----------------------------------------------------------|
| Plugwise bid loss                     | Medium     | Lose smart-switch kit                     | Grove Relay + 230 V contactor on bench bulb               |
| No physical CO₂ sensor                | High       | Course pool has none                      | Simulate via occupancy × time (ASHRAE), label as simulated |
| PDDL solver timeout                   | Medium     | Fast Downward chokes on numeric fluents   | Cap horizon at 10 min, coarsen fluents, fall back to ENHSP |
| MQTT broker is SPOF                   | Medium     | Broker crash halts system                 | Persistent queue + systemd auto-restart; edge buffers 60 s |
| Break-reminder annoyance              | Low        | Users disable reminders                   | Escalation + snooze + override, log compliance            |
| Team-member illness near demo         | Low        | Single point of human failure             | Pair-programming, every module has secondary owner        |

---

## 9 · Success criteria (graded at demo)

- Hardware uptime ≥ **95 %** over 48 h soak test
- End-to-end latency (sensor → actuator) < **3 s** for 90 % of events
- Energy saving ≥ **25 %** vs. always-on baseline
- Break-reminder compliance ≥ **60 %** over 2 h session
- Dashboard live state + current plan rendered with ≤ **1 s** lag
- Full demo script runs reproducibly, including a sensor-fault recovery

---

## 10 · References

- Cirillo, F. — _The Pomodoro Technique_ (1988)
- ASHRAE Standard 62.1 — Ventilation for Acceptable Indoor Air Quality
- Fast Downward Planner — <https://www.fast-downward.org>
- ENHSP — Expressive Numeric Heuristic Search Planner
- Eclipse Mosquitto — <https://mosquitto.org>
- PDDL 2.1 — Fox & Long (2003), JAIR
