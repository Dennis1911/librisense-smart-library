# Hardware inventory & device map

_Picked up 2026-05-21 from IAAS, Universität Stuttgart (Dr. Ilche Georgievski).
Loan ends 2026-05-19._

This file replaces §5 of the proposal where the device bid was speculative. Update it whenever a physical device is added, swapped, or returned.

## What we got

| # | Item                     | Detail                                                        | Bid                     |
|---|--------------------------|---------------------------------------------------------------|-------------------------|
| 1 | Raspberry Pi 3 set       | Pi 3 Model B+, microSD card + adapter, Goobay power adapter   | (mandatory)             |
| 2 | **GrovePi+ Starter Kit** | GrovePi+ board + Grove sensors (see §"GrovePi+ contents")     | 2nd preference (Sensor) |
| 3 | **Plugwise set**         | 2 × Circle smart-switch + 1 × USB Stick (ZigBee)              | 1st preference (Actuator) |
| 4 | Raspberry Pi 5           | Personally owned by Dennis — used as the Core node            | (private)               |

## Compute topology

Two physical machines, talking over the LAN via MQTT — this satisfies the course's _≥ 2 machines_ distribution requirement cleanly, no laptop in the loop.

| Node     | Hostname          | Hardware    | Modules deployed                                                                 | Why                                                                                  |
|----------|-------------------|-------------|----------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| **Edge** | `librisense-edge` | Pi 3 B+     | IoT layer only                                                                   | GrovePi+ Python stack uses legacy `RPi.GPIO`; cleanest on the older Pi               |
| **Core** | `librisense-core` | Pi 5        | Mosquitto · Processing · Problem-Generator · Fast Downward · Execution · Dashboard | CPU horsepower for the planner + React build; can drive a kiosk display in the demo |

If you plug an HDMI screen into the Pi 5 for the demo, it _also_ serves as the kiosk — that retires the "optional third machine" from the proposal and keeps the architecture honest.

### Network constraint (discovered during setup)

The home router (Vodafone Kabelbox at 192.168.0.1) has **WLAN client isolation enabled**: wireless clients can reach the internet but not each other. Wired LAN ports do not have this restriction.

**Consequence:** both Pis must be on Ethernet to talk to each other. The Core Pi 5 is permanently wired in. The Edge Pi 3 B+ should also be wired wherever physically possible; if WLAN is unavoidable, we'd need router-side configuration changes that we don't control.

Live network inventory: [`config/network.yaml`](../config/network.yaml).

## What we did NOT get (and the impact)

| Wanted                         | Why it matters                  | Replacement                                                      |
|--------------------------------|---------------------------------|------------------------------------------------------------------|
| Aeon MultiSensor 6 + Z-Wave    | Was 1st Sensor preference       | GrovePi DHT + light + sound + ultrasonic cover the same variables |
| Grove PIR Motion Sensor        | Per-zone occupancy detection    | Grove **Ultrasonic Ranger** (distance < threshold ⇒ occupied)   |
| Raspberry Pi Relay Shield      | Was 2nd Actuator preference     | Grove **Relay** from the GrovePi kit drives the ventilation     |

The Sense HAT mentioned in the proposal is **not in our pool** — temperature and humidity come from the **Grove DHT** in the GrovePi kit instead. PDDL domain doesn't care.

## GrovePi+ Starter Kit contents (verify on unboxing — TODO)

Standard kit usually contains:

- [ ] GrovePi+ shield (mounts on the Pi GPIO)
- [ ] Grove DHT — temperature + humidity (digital)
- [ ] Grove Light Sensor (analog)
- [ ] Grove Sound Sensor (analog)
- [ ] Grove Ultrasonic Ranger (digital) — **used as PIR replacement**
- [ ] Grove Relay (digital) — **used for ventilation**
- [ ] Grove LED (digital) — break reminder visual
- [ ] Grove Buzzer (digital) — break reminder audible
- [ ] Grove Button (digital) — manual override input
- [ ] Grove LCD RGB Backlight (I²C) — bonus local display
- [ ] Grove Rotary Angle Sensor (analog) — optional comfort tuner
- [ ] Set of Grove cables

> **Action:** tick each item once you've physically confirmed it. If anything from the "used as …" lines is missing, ping the team immediately — that's a planning blocker.

## Plugwise pairing

The two Circle switches need to be paired with the USB Stick first. Steps:

1. Plug the USB Stick into the Core node (laptop or Pi)
2. Install the Python `plugwise` library
3. Run the pairing utility, follow Circle by Circle
4. Note the MAC of each Circle and assign roles in `config/devices.yaml`:
   - Circle A → reading lamp
   - Circle B → space heater / fan

## Updated IoT map (final, post-collection)

### Sensors (8 — well above the ≥ 4 requirement)

| Variable     | Source                        | Type      | Planner usage                |
|--------------|-------------------------------|-----------|------------------------------|
| Temperature  | Grove DHT                     | physical  | Heating / fan action         |
| Humidity     | Grove DHT                     | physical  | Comfort index                |
| Illuminance  | Grove Light (A2)              | physical  | Lamp on/off decision         |
| ~~Sound~~    | ~~Grove Sound (A1)~~ removed  | —         | GrovePi I2C too slow (~10-200 Hz) to measure loudness from the raw waveform; loud == quiet in tests. A1 freed. |
| Occupancy    | Grove motion sensor (A0)      | physical  | Gates the reading lamp        |
| CO₂          | Software (occ × time, ASHRAE) | simulated | Ventilation                  |
| Session state| Software (REST → dashboard)   | software  | Break actions                |
| Weather      | Software (OpenWeather)        | software  | Heating pre-conditioning     |

### Actuators — AS BUILT (6 total, 4 physical — comfortably ≥ 4 with ≥ 2 physical)

| Effect             | Source                         | Type      | Planner action  | Status |
|--------------------|--------------------------------|-----------|-----------------|--------|
| Reading lamp       | Plugwise Circle+ relay         | physical  | `turn_on/off_lamp` | ✅ switches |
| Break alert (vis)  | Grove LED (D2)                 | physical  | `suggest_break` | ✅ lights |
| Break alert (aud)  | Grove buzzer (D3, PWM quiet)   | physical  | `suggest_break` | ✅ beeps |
| Local status       | Grove LCD RGB (I2C-3)          | physical  | (status display)| ✅ text + CO2 traffic light |
| Ventilation        | software / virtual (no relay)  | simulated | `ventilate`     | ✅ lowers CO2 proxy |
| Break banner       | software (library/actuators/break → dashboard) | software | `suggest_break` | ✅ |

**4 physical actuators** (lamp, LED, buzzer, LCD) + 2 software/simulated.
The break LED + buzzer are driven by the GrovePi-owning process
(sensor_publisher) to avoid I2C bus contention. The proposal's heater
(2nd Circle) and a physical ventilation relay were not realised — see the
honest IoT inventory above.
