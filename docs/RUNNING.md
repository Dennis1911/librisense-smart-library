# Running system — live services & data flow

_Last verified: 2026-06-10_

LibriSense currently runs as a set of **systemd services** across the two Pis,
all auto-starting on boot and restarting on failure. Reach both Pis by mDNS
(`ssh librisense-core`, `ssh librisense-edge`).

## Live data flow — the full autonomous loop

```
[Edge: Pi 3 B+]                          [Core: Pi 5]
 motion A0 ─┐                              mosquitto (broker :1883)
 light  A2 ─┴─► sensor_publisher ─MQTT──► library/sensors/*
                (2 Hz)                       │   (A1 sound removed — see below)
                                             ▼
 (Open-Meteo) ─► weather_sensor ─MQTT──► state_aggregator
                 (/600s)                  └─► library/state (occupancy, CO2
                                              proxy, comfort, session FSM)
                                             │
                                             ▼
                                          problem_generator ─► library/problem
                                          (discretise + situational goal)
                                             │
                                             ▼
                                          planner (Fast Downward, A* lmcut)
                                          └─► library/plan (optimal actions)
                                             │
                                             ▼
                                          executor ─► library/actions
                                             │
   Plugwise relay ◄── actuator_service ◄─────┘
   (reading lamp)     └─► library/actuators/* (retained, feeds problem gen)
                                             │
   Grove LCD ◄── lcd_display      dashboard ◄┘  (http://librisense-core.local:8000)
   (CO2 traffic light)            (state + plan, live WebSocket)
```

Verified closed loop: a manual lamp-off disturbance is autonomously corrected
in < 1 s (occupied+dark → planner picks `turn_on_lamp` → relay switches on).

## Services

| Node | Service | Unit | Role |
|------|---------|------|------|
| Edge | sensor_publisher | `librisense-sensors`   | motion + light → `library/sensors/*` @ 2 Hz |
| Edge | lcd_display       | `librisense-lcd`       | `library/state` → Grove LCD + CO2 traffic light |
| Edge | actuator_service  | `librisense-actuator`  | `library/actions` → Plugwise relay (physical) |
| Core | mosquitto         | `mosquitto`            | MQTT broker |
| Core | weather_sensor    | `librisense-weather`   | Open-Meteo → `library/sensors/weather` (retained) |
| Core | state_aggregator  | `librisense-processing`| `library/sensors/*` → `library/state` (retained) |
| Core | problem_generator | `librisense-problemgen`| `library/state` → `library/problem` |
| Core | planner           | `librisense-planner`   | `library/problem` → Fast Downward → `library/plan` (retained) |
| Core | executor          | `librisense-executor`  | `library/plan` → `library/actions` |
| Core | dashboard         | `librisense-dashboard` | FastAPI WS bridge, port 8000 |

Units live in `config/systemd/` (all with `PYTHONUNBUFFERED=1` for logs).
Deploy with:

```bash
sudo cp config/systemd/<unit>.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now <unit>
```

## Handy commands

```bash
# Watch the aggregated world state
ssh librisense-core 'mosquitto_sub -h localhost -t library/state -v'

# Watch raw sensors
ssh librisense-core 'mosquitto_sub -h localhost -t "library/sensors/#" -v'

# Service status / logs
ssh librisense-edge 'systemctl status librisense-sensors'
ssh librisense-core 'journalctl -u librisense-processing -f'
```

## Demo handles

```bash
# Watch the autonomous loop think + act
ssh librisense-core 'mosquitto_sub -h localhost -t "library/plan" -v'
ssh librisense-core 'mosquitto_sub -h localhost -t "library/actions" -v'

# Inject a disturbance (turn the lamp off) and watch it self-correct
ssh librisense-core 'mosquitto_pub -h localhost -t library/actions \
  -m "{\"action\":\"turn_off_lamp\",\"args\":[\"reading-1\"]}"'
```

## Next up (polish, not blockers)

- Drift detection / explicit re-plan on observed divergence (basic loop already
  re-plans on every state change)
- Break-reminder escalation (banner → LED → buzzer → TTS)
- Second Plugwise Circle (heater) — needs joining to the network
- Dashboard: 24 h trend charts, override drawer, energy tile
- Report write-up using the verified architecture + the design notes here
