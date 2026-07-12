"""LibriSense actuator service (Edge node) — IoT layer, actuator half.

Owns the Plugwise USB stick and turns planner actions into physical effects.
Subscribes to library/actions and:
    turn_on_lamp   -> Plugwise Circle+ relay ON   (reading lamp)
    turn_off_lamp  -> Plugwise Circle+ relay OFF
    ventilate      -> publish ventilation state (no physical vent in our kit)
    suggest_break  -> publish a break nudge (shown on LCD/dashboard)

It publishes each actuator's resulting state (retained) on
library/actuators/<name>, which the problem generator consumes to know the
current lamp state — closing the loop.

Architecture: paho MQTT runs in its own thread and feeds an asyncio.Queue;
the asyncio main loop owns the (async) Plugwise stick and drains the queue.
If the stick is unavailable, actions are still acknowledged as state so the
control loop stays logically correct; physical failures are logged.

Run on the Edge Pi:
    .venv/bin/python modules/iot/actuator_service.py
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import sys
import yaml
import paho.mqtt.client as mqtt
from plugwise_usb import Stick

sys.path.insert(0, str(Path(__file__).parent))
from broker import pick_broker_host  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
TOPICS = REPO / "config" / "topics.yaml"

PORT = "/dev/ttyUSB0"
CIRCLE_PLUS = "000D6F0000729939"


def _silence_plugwise_scan_errors(loop: asyncio.AbstractEventLoop) -> None:
    """The Circle+ network scan for the (unjoined) 2nd Circle raises a
    background StickError we don't care about; keep it out of the logs."""
    def handler(_loop, context):
        exc = context.get("exception")
        if exc and "CirclePlusScanRequest" in str(exc):
            return
        _loop.default_exception_handler(context)
    loop.set_exception_handler(handler)


class PlugwiseLamp:
    """Wraps the Circle+ relay; degrades gracefully if the stick is absent."""

    def __init__(self) -> None:
        self.stick: Stick | None = None
        self.node = None

    async def connect(self) -> None:
        try:
            self.stick = Stick(PORT)
            await self.stick.connect()
            await self.stick.initialize()
            # discover_nodes() populates stick.nodes — without it the Circle+
            # is unknown and we'd silently fall back to log-only mode.
            try:
                await asyncio.wait_for(self.stick.discover_nodes(), timeout=75)
            except Exception:  # noqa: BLE001 - 2nd-circle scan may time out
                pass
            try:
                await asyncio.wait_for(self.stick.load_nodes(), timeout=40)
            except Exception:  # noqa: BLE001
                pass
            self.node = self.stick.nodes.get(CIRCLE_PLUS)
            if self.node is not None and hasattr(self.node, "load"):
                try:
                    await asyncio.wait_for(self.node.load(), timeout=30)
                except Exception:  # noqa: BLE001
                    pass
            print(f"[actuator] Plugwise ready, Circle+ "
                  f"{'loaded' if self.node else 'NOT found'}")
        except Exception as e:  # noqa: BLE001
            print(f"[actuator] Plugwise unavailable ({e!r}) — running in "
                  f"log-only mode for the lamp")

    async def set(self, on: bool) -> bool:
        if self.node is None:
            return False
        try:
            await self.node.set_relay(on)
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[actuator] relay switch failed: {e!r}")
            return False


async def main() -> None:
    broker = yaml.safe_load(open(TOPICS))["broker"]
    loop = asyncio.get_running_loop()
    _silence_plugwise_scan_errors(loop)
    queue: asyncio.Queue = asyncio.Queue()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"{broker.get('client_id_prefix','librisense')}-actuator")

    def on_connect(c, u, f, rc, p):
        c.subscribe("library/actions")
        print("[actuator] subscribed to library/actions")

    def on_message(c, u, msg):
        try:
            cmd = json.loads(msg.payload)
        except ValueError:
            return
        loop.call_soon_threadsafe(queue.put_nowait, cmd)

    client.on_connect = on_connect
    client.on_message = on_message
    host, port = pick_broker_host(broker)
    client.connect(host, port, 60)
    client.loop_start()
    print(f"[actuator] connected to {host}:{port}")

    def pub_state(topic: str, payload: dict) -> None:
        client.publish(topic, json.dumps(payload), retain=True)

    lamp = PlugwiseLamp()
    await lamp.connect()

    while True:
        cmd = await queue.get()
        action = cmd.get("action")
        args = cmd.get("args", [])
        zone = args[0] if args else "reading-1"
        ts = datetime.now(timezone.utc).isoformat()

        if action in ("turn_on_lamp", "turn_off_lamp"):
            on = action == "turn_on_lamp"
            ok = await lamp.set(on)
            pub_state("library/actuators/lamp",
                      {"ts": ts, "zone": zone, "on": on, "physical": ok})
            print(f"[actuator] lamp {'ON' if on else 'OFF'} "
                  f"({'relay switched' if ok else 'log-only'})")
        elif action in ("ventilate", "full_ventilate",
                        "pulse_ventilate", "pulse_ventilate_step"):
            mode = "pulse" if action.startswith("pulse") else "full"
            pub_state("library/actuators/ventilation",
                      {"ts": ts, "zone": zone, "on": True, "mode": mode})
            print(f"[actuator] ventilation engaged (virtual, {mode})")
        elif action == "suggest_break":
            pub_state("library/actuators/break",
                      {"ts": ts, "zone": zone, "suggested": True})
            print("[actuator] break suggested (nudge)")
        else:
            print(f"[actuator] unknown action: {action}")


if __name__ == "__main__":
    asyncio.run(main())
