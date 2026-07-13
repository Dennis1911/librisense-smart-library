# LibriSense — An Adaptive Smart Library

> Smart Cities and the Internet of Things · Practical Project 2026
> M.Sc. Autonomous Systems · Universität Stuttgart
> Domain: **Smart Building** · Functionality: **Monitoring + Automation**

LibriSense turns an ordinary reading room into an environment that actively collaborates with its learners. It continuously monitors illuminance, occupancy and a CO₂ proxy, fuses those streams with each learner's Pomodoro focus-session state, and lets an **AI planner (PDDL, Fast Downward)** decide which actuator to move next — from switching a reading lamp to escalating a break reminder.

---

## Repository layout

```
librisense/
├── docs/                  # Proposal, architecture diagram, course forms
├── modules/
│   ├── iot/               # (1) Sensor drivers + actuator service + MQTT
│   ├── processing/        # (2) State aggregation, learner FSM, CO₂ proxy
│   ├── problem_generator/ # (3) State → PDDL problem (Jinja2)
│   ├── planner/           # (4) Fast Downward wrapper
│   ├── execution/         # (5) Plan dispatch
│   └── visualisation/     # (6) Live dashboard (FastAPI + WebSocket + HTML)
├── pddl/
│   ├── domain/            # librisense.pddl
│   ├── templates/         # Jinja2 problem template
│   └── problems/          # Generated problem instances (gitignored)
├── config/                # MQTT topics, device map, systemd units
├── tools/                 # Development helpers (mock publishers)
└── docs/                  # RUNNING.md, HARDWARE.md, SETUP.md, …
```

---

## Local development

### Scenario A — No hardware, full simulation

Everything runs locally, no Pi needed. Open four terminals in `librisense/`:

```powershell
# Terminal 1 — MQTT broker
& "C:\Program Files\mosquitto\mosquitto.exe"

# Terminal 2 — Mock data (6 simulated seats)
.venv\Scripts\Activate.ps1
python tools/mock_simulate.py

# Terminal 3 — Dashboard
.venv\Scripts\Activate.ps1
$env:MQTT_HOST = "127.0.0.1"
python -m uvicorn modules.visualisation.dashboard:app --port 8000 --reload
```

Open **http://localhost:8000**.

---

### Scenario B — Pi connected, multi-seat heatmap for demo

Start the normal pipeline on the Pis as usual (see [docs/RUNNING.md](docs/RUNNING.md)), then run this **on top** on your laptop or the Core Pi:

```powershell
.venv\Scripts\Activate.ps1
python tools/mock_sensors.py
```

That's it. `mock_sensors.py` subscribes to `library/state` from the real `state_aggregator`, adds `seat-2` through `seat-6` as simulated zones, and republishes — `reading-1` stays real (real motion, real light, real Pomodoro FSM). Nothing else needs to change.

Dashboard is already running on the Core Pi at **http://librisense-core.local:8000**.

---

## Live system (on the Pis)

See [docs/RUNNING.md](docs/RUNNING.md) for the full systemd setup, service table, and handy `mosquitto_sub` debug commands.

### Data flow

```
[Edge: Pi 3 B+]                          [Core: Pi 5]
 motion A0 ─┐                              mosquitto (broker :1883)
 light  A2 ─┴─► sensor_publisher ─MQTT──► library/sensors/*
                (2 Hz)                       │
 Open-Meteo ──► weather_sensor ─MQTT────►   ▼
                                          state_aggregator  ──► library/state
                                          (occupancy, CO₂ proxy, comfort,
                                           Pomodoro FSM: idle→focused→
                                           break-due→on-break)
                                             │
                                             ▼
                                          problem_generator ──► library/problem
                                             │
                                             ▼
                                          planner (Fast Downward, A* lmcut)
                                                          ──► library/plan
                                             │
                                             ▼
                                          executor ──► library/actions
                                             │
   Plugwise relay ◄── actuator_service ◄─────┘   (lamp on/off)
   Grove LCD     ◄── lcd_display               (CO₂ traffic light)
   LED + Buzzer  ◄── actuator_service          (break reminder)
                                             │
                                          dashboard ◄── library/state + plan
                                          http://librisense-core.local:8000
```

---

## Dashboard features

| Section | What it shows |
|---------|--------------|
| **Seat Heatmap** | Floor plan with one cell per zone — colour = comfort (green/yellow/red), person icon = occupied, CO₂ badge per seat |
| **Pomodoro rings** | SVG ring per learner showing phase (focused / break-due / on-break / idle) and session minutes |
| **Trend charts** | Last ~30 min of Light %, CO₂ ppm, and Comfort index (sampled every 10 s) |
| **Zone cards** | Per-zone occupancy, light, CO₂, comfort |
| **Outdoor weather** | Temperature, humidity, cloud cover (Open-Meteo) |
| **AI Planner** | Current plan: action queue, status, cost, solve time |

---

## Quick links

- **Planning & sprints:** [PLANNING.md](PLANNING.md)
- **Hardware inventory:** [docs/HARDWARE.md](docs/HARDWARE.md)
- **Running services:** [docs/RUNNING.md](docs/RUNNING.md)
- **Architecture diagram:** [docs/LibriSense_Architecture.png](docs/LibriSense_Architecture.png)
- **Full proposal:** [docs/LibriSense_Proposal.docx](docs/LibriSense_Proposal.docx)

---

## Key dates

| Date       | Milestone                            |
|------------|--------------------------------------|
| 2026-05-01 | Proposal submission + device bidding |
| 2026-05-21 | IoT kit collection                   |
| 2026-07-14 | Report submission                    |
| 2026-07-20 | Project demo                         |

---

## Team

| Name         | Student ID | GitHub                                             |
|--------------|------------|----------------------------------------------------|
| Dennis Gunt  | _TBD_      | [@Dennis1911](https://github.com/Dennis1911)       |
| Haoyang Chen | 3854758    | [@wandering2025](https://github.com/wandering2025) |
| Niclas       | _TBD_      | [@niclmit](https://github.com/niclmit)             |
