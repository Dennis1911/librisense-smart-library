"""LibriSense local LCD status display (Edge node).

Subscribes to library/state and renders a live 2-line summary on the Grove
LCD RGB Backlight (I2C 0x3e text + 0x62 RGB). The backlight doubles as an
air-quality traffic light driven by the (simulated) CO2 proxy:
    green  < 800 ppm    amber 800..1200    red > 1200

Line 1:  "<OCC> L:<light>%"        e.g.  "OCC   L:68%"
Line 2:  "CO2:<ppm> C:<comfort>%"  e.g.  "CO2:648 C:98%"

Run on the Edge Pi (LCD on an I2C port):
    .venv/bin/python modules/iot/lcd_display.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import yaml
import paho.mqtt.client as mqtt
from smbus2 import SMBus

import sys
sys.path.insert(0, str(Path(__file__).parent))
from broker import pick_broker_host  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
TOPICS = REPO / "config" / "topics.yaml"

TEXT_ADDR = 0x3e
RGB_ADDR = 0x62


class GroveLCD:
    def __init__(self, bus_no: int = 1) -> None:
        self.bus = SMBus(bus_no)
        self._last = ("", "")
        self._init_display()

    def _cmd(self, c: int) -> None:
        self.bus.write_byte_data(TEXT_ADDR, 0x80, c)

    def _init_display(self) -> None:
        time.sleep(0.05)
        self._cmd(0x28)   # function set: 2 lines, 5x8
        self._cmd(0x0c)   # display on, no cursor
        self._cmd(0x01)   # clear
        time.sleep(0.05)

    def set_rgb(self, r: int, g: int, b: int) -> None:
        self.bus.write_byte_data(RGB_ADDR, 0, 0)
        self.bus.write_byte_data(RGB_ADDR, 1, 0)
        self.bus.write_byte_data(RGB_ADDR, 0x08, 0xaa)
        self.bus.write_byte_data(RGB_ADDR, 4, r)
        self.bus.write_byte_data(RGB_ADDR, 3, g)
        self.bus.write_byte_data(RGB_ADDR, 2, b)

    def set_lines(self, line1: str, line2: str) -> None:
        # Skip the redraw (and its flicker) when nothing changed.
        if (line1, line2) == self._last:
            return
        self._last = (line1, line2)
        self._cmd(0x01)  # clear
        time.sleep(0.002)
        for ch in line1[:16]:
            self.bus.write_byte_data(TEXT_ADDR, 0x40, ord(ch))
        self._cmd(0xc0)  # move to line 2
        for ch in line2[:16]:
            self.bus.write_byte_data(TEXT_ADDR, 0x40, ord(ch))


def co2_color(ppm: float) -> tuple[int, int, int]:
    # High-luminance variants: the LCD characters are dark, so a bright
    # backlight maximises contrast/readability while still colour-coding CO2.
    if ppm < 800:
        return (40, 255, 110)   # bright green
    if ppm < 1200:
        return (255, 200, 0)    # bright amber/yellow (high luminance)
    return (255, 60, 40)        # bright red (alarm — colour is the message)


def render(lcd: GroveLCD, state: dict) -> None:
    zones = state.get("zones", {})
    if not zones:
        lcd.set_rgb(40, 40, 60)
        lcd.set_lines("LibriSense", "waiting...")
        return
    # Show the first (only) zone for now.
    name, z = next(iter(zones.items()))
    occ = "OCC  " if z.get("occupied") else "EMPTY"
    light = round(z.get("light_pct", 0))
    co2 = round(z.get("co2_ppm", 0))
    comfort = round(z.get("comfort", 0) * 100)
    lcd.set_rgb(*co2_color(co2))
    lcd.set_lines(f"{occ} L:{light}%", f"CO2:{co2} C:{comfort}%")


def main() -> None:
    broker = yaml.safe_load(open(TOPICS))["broker"]
    lcd = GroveLCD()
    lcd.set_rgb(40, 40, 60)
    lcd.set_lines("LibriSense", "connecting...")

    state_holder: dict = {}

    def on_connect(c, u, f, rc, p):
        c.subscribe("library/state")

    def on_message(c, u, msg):
        try:
            state_holder.clear()
            state_holder.update(json.loads(msg.payload))
        except ValueError:
            pass

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"{broker.get('client_id_prefix','librisense')}-lcd")
    client.on_connect = on_connect
    client.on_message = on_message
    host, port = pick_broker_host(broker)
    client.connect(host, port, 60)
    client.loop_start()
    print(f"[lcd] connected to {host}:{port}, displaying library/state")

    try:
        while True:
            if state_holder:
                render(lcd, state_holder)
            time.sleep(1)
    except KeyboardInterrupt:
        lcd.set_rgb(0, 0, 0)
        lcd.set_lines("", "")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
