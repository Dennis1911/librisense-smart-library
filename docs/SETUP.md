# First-time setup — Edge Pi & Core Pi

Walk-through for the very first boots through to "every sensor publishes on MQTT". Estimated time: **2–3 h** including downloads. Do it once, document any deviations here.

We have **two physical machines** (see [HARDWARE.md](HARDWARE.md)):

- **Edge** = Pi **3 B+**, hostname `librisense-edge` — sensors + actuators
- **Core** = Pi **5**, hostname `librisense-core` — broker + brains + dashboard

You will flash both, but the GrovePi+ shield only goes on the Edge Pi.

## 0 · What you need next to you

- Raspberry Pi **3 B+** + its microSD + IAAS power supply
- Raspberry Pi **5** + microSD + 5 V/5 A USB-C power supply
- A laptop with an SD-card reader (just for flashing)
- Ethernet cable _or_ WLAN credentials for both Pis
- The **GrovePi+ Starter Kit** (verify against [HARDWARE.md](HARDWARE.md))
- USB keyboard + HDMI screen — _optional_, only needed if headless setup misbehaves

## 1 · Flash both Pis

Use **Raspberry Pi Imager** (<https://www.raspberrypi.com/software/>). The settings are nearly identical, just two differences (hostname + OS flavour).

### 1a · Edge Pi (3 B+) → headless Lite

1. Insert the Edge microSD
2. Choose Device → **Raspberry Pi 3**
3. Choose OS → **Raspberry Pi OS Lite (64-bit)** (no desktop, this is a sensor node)
4. Choose Storage → the microSD
5. Click the gear icon and pre-configure:
   - Hostname: **`librisense-edge`**
   - Enable SSH (paste your SSH key, or password auth)
   - Username: `librisense`, password: pick one
   - WLAN SSID + password + country (`DE`)
   - Locale: `Europe/Berlin`, keyboard `de`
6. Write — about 5 min

### 1b · Core Pi (5) → full desktop (doubles as demo kiosk)

1. Insert the Core microSD
2. Choose Device → **Raspberry Pi 5**
3. Choose OS → **Raspberry Pi OS (64-bit)** — _the full one with desktop_, so the Pi 5 can also drive the kiosk dashboard at the demo
4. Choose Storage → the microSD
5. Gear icon, same as above but:
   - Hostname: **`librisense-core`**
   - Same `librisense` user, same WLAN
6. Write

Eject each, slide into the respective Pi, power on. Wait ~90 s per Pi.

## 2 · SSH in and update — do both Pis

Open two terminals, one per Pi. Run the same base setup on both, plus a node-specific block.

**Both Pis (common base):**

```bash
ssh librisense@librisense-edge.local     # (and another tab for librisense-core.local)
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git python3-venv python3-pip mosquitto-clients
```

**Edge Pi only (GrovePi+ needs I²C):**

```bash
sudo apt install -y i2c-tools
sudo raspi-config nonint do_i2c 0     # enable I²C
sudo raspi-config nonint do_spi 0     # harmless, enable for future use
sudo reboot
```

**Core Pi only (this is where the broker, planner, and dashboard live):**

```bash
sudo apt install -y mosquitto nodejs npm
sudo systemctl enable --now mosquitto
# Allow LAN clients to connect (default config is loopback-only)
sudo tee /etc/mosquitto/conf.d/librisense.conf <<'EOF'
listener 1883 0.0.0.0
allow_anonymous true
EOF
sudo systemctl restart mosquitto
```

(In a real deployment you'd put auth on the broker. For the demo, LAN-only + anonymous is fine.)

Reconnect to the Edge Pi after its reboot.

## 3 · Clone the repo on both Pis

Same repo, different dependency sets per node.

**Edge Pi (3 B+):**

```bash
ssh librisense@librisense-edge.local
git clone https://github.com/Dennis1911/librisense.git
cd librisense
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install paho-mqtt grovepi smbus2 python-plugwise
```

**Core Pi (5):**

```bash
ssh librisense@librisense-core.local
git clone https://github.com/Dennis1911/librisense.git
cd librisense
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install paho-mqtt numpy jinja2 fastapi uvicorn[standard] websockets pyttsx3
# Fast Downward is built from source in Sprint 3 — leave it for later
```

> Note: `grovepi` is **only** installed on the Edge Pi (it pokes `/dev/i2c-*`). Don't install it on the Core Pi.

## 4 · Mount the GrovePi+ shield

1. Power off the Pi (`sudo shutdown -h now`)
2. Seat the GrovePi+ board on the Pi's 40-pin header
3. Plug each Grove sensor into its labelled socket:

| Sensor        | Socket (suggested) |
|---------------|--------------------|
| DHT (temp/hum)| D4                 |
| Light         | A0                 |
| Sound         | A2                 |
| Ultrasonic    | D8                 |
| Relay         | D2                 |
| LED           | D5                 |
| Buzzer        | D3                 |
| Button        | D6                 |
| LCD (I²C)     | any I²C socket     |

Update `config/devices.yaml` once finalised (template lands in Sprint 1 first commit).

Power on, SSH back in.

## 5 · Smoke-test one Grove sensor

```bash
source .venv/bin/activate
python3 - <<'PY'
import grovepi, time
LIGHT = 0   # A0
while True:
    print("light:", grovepi.analogRead(LIGHT))
    time.sleep(1)
PY
```

Cover the sensor with your hand — the number should drop. Ctrl-C.

## 6 · Mosquitto is already running on Core

You installed it in Step 2. Sanity check from any machine on the LAN:

```bash
# On the Core Pi itself
ssh librisense@librisense-core.local
mosquitto_sub -h localhost -t 'library/#' -v
```

Open a second terminal and pretend to be the Edge:

```bash
ssh librisense@librisense-edge.local
mosquitto_pub -h librisense-core.local \
  -t library/sensors/test \
  -m '{"hello":"world"}'
```

The subscriber on Core should print the message instantly.

## 7 · First end-to-end publish from the Edge Pi

Still on the Edge:

```bash
mosquitto_pub -h librisense-core.local \
  -t library/sensors/light \
  -m '{"ts":"2026-05-21T15:00:00Z","zone":"reading-1","value":340,"unit":"lux"}'
```

Core's subscriber sees it. If yes — congratulations, the **Edge → Broker → consumers** path works across two physical machines. The "≥ 2 machines" course requirement is hereby physically demonstrated, not just claimed on paper. From here it's "wire up real sensors", which is the Sprint 1 work.

## 8 · Pair the Plugwise Circles (Edge Pi, in parallel with sensor work)

Plug the Plugwise USB stick into the **Edge Pi**, then:

```bash
ls /dev/ttyUSB*    # should show ttyUSB0
# Pairing helper snippet will land in modules/iot/scripts/plugwise_pair.py during Sprint 1
```

Note the two Circle MACs and assign them to roles in `config/devices.yaml`:

- Circle A → reading lamp
- Circle B → space heater / fan

---

When you've reached the end of step 7, ping the team — that's the green light to split Sprint 1 work and start writing the proper driver code.

---

When you've reached the end of step 7, ping the team — that's the green light to split Sprint 1 work and start writing the proper driver code.
