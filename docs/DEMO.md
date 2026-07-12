# Demo runbook — running LibriSense with no WiFi, LAN, screen or keyboard

The two Pis form their **own private network**: the Core Pi (Pi 5) becomes a
WiFi access point, the Edge Pi (Pi 3 B+) auto-joins it, and your laptop joins
it to view the dashboard. No university WiFi/LAN, no external monitor, no
keyboard needed. Verified working 2026-06-23.

## How it works (automatic)

- **At home:** both Pis connect to the home WiFi (`<home-wifi>`, high
  autoconnect priority) — internet, weather, SSH all work as usual.
- **Away (no home WiFi):** NetworkManager falls back to the `librisense-ap`
  profile → the **Core becomes an access point** (SSID `LibriSense`,
  2.4 GHz, gateway `10.42.0.1`); the **Edge auto-joins** it.
- Edge services find the broker via `pick_broker_host`: `librisense-core.local`
  at home, **`10.42.0.1`** on the hotspot (mDNS/`.local` does not traverse the AP).

## Demo-day procedure

1. **Power on the Core Pi (Pi 5).** Wait ~60 s. With no home WiFi it starts the
   `LibriSense` hotspot. (Power LED on; give it a minute.)
2. **Power on the Edge Pi (Pi 3 B+).** It auto-joins the hotspot; sensors, LCD,
   lamp, LED/buzzer come alive. The **LCD** shows live status + the CO₂ traffic
   light even with no laptop.
3. **On your laptop:** join WiFi **`LibriSense`** (password `librisense2026`),
   then open **`http://10.42.0.1:8000`** in the browser → live dashboard
   (state + current AI plan).
4. **Demonstrate:**
   - Sit / wave at the desk + cover the light sensor (A2) → planner turns the
     **lamp on** (relay clicks, real lamp lights). Uncover / leave → lamp off.
   - Stay present ~2 min → focus session → **break LED + buzzer** nudge.
   - Watch CO₂ proxy climb while occupied; the planner ventilates → it drops.

## Optional: 6-seat floor-plan simulation (nice demo visual)

The dashboard heatmap can show a lively 6-seat reading room: the real
`reading-1` zone plus five simulated seats (`tools/mock_sensors.py`).
Simulated zones are marked `"simulated": true` and are **skipped by the
problem generator**, so the planner and the physical actuators only ever act
on the real seat — the simulation is display-only and safe to run live.

```bash
# start for the demo (on the Core Pi, e.g. via SSH over the hotspot):
ssh librisense@10.42.0.1 'sudo systemctl start librisense-mockseats'
# stop afterwards:
ssh librisense@10.42.0.1 'sudo systemctl stop librisense-mockseats'
```

Tip: start it at home before leaving — it survives reboots only if enabled;
started (not enabled) state is intentional so normal operation stays 1-zone.

## Important: POWER

The Pis need mains power. Confirm there is a **socket** at the demo location,
otherwise bring **power banks**: Pi 5 needs a strong USB-C PD bank (5 V/5 A),
Pi 3 a 5 V/2.5 A bank. This is the only hard prerequisite.

## Notes / caveats

- **No internet on the hotspot** → the weather software-sensor can't fetch;
  it degrades gracefully (outdoor data simply absent). The autonomous loop
  does not depend on it.
- **Broker host is chosen at service start.** A fresh boot in the active mode
  always picks the right host. If you switch modes *while the Pis are running*
  (e.g. testing at home), restart the Edge services so they re-pick:
  `ssh librisense-edge 'sudo systemctl restart librisense-sensors librisense-lcd librisense-actuator'`
- **WiFi stability:** on home WiFi the Pi 3 sits at ~−65 dBm (5 GHz) and drops
  occasionally. In hotspot mode the Pis are adjacent → short, strong link →
  stable. For absolute safety on demo day, place the Edge close to the Core.

## Quick pre-demo checklist (at home, before leaving)

```bash
# both reachable + all services active
ssh librisense-core 'for s in mosquitto; do systemctl is-active $s; done; for s in weather processing problemgen planner executor dashboard; do systemctl is-active librisense-$s; done'
ssh librisense-edge 'for s in sensors lcd actuator wifi-powersave-off; do systemctl is-active librisense-$s 2>/dev/null || systemctl is-active $s; done'
```

To rehearse the hotspot at home, drop home WiFi on both Pis briefly (they
auto-revert): see `scripts/` test snippets, or just take both Pis somewhere
without the home network and power them on.
