"""Discover Plugwise nodes on the USB stick and report each node's API.

Run on the Edge Pi (stick at /dev/ttyUSB0):
    .venv/bin/python modules/iot/plugwise_discover.py

ZigBee discovery can take 30-75 s. Prints each joined node's MAC, type,
and the relay/power-related attributes so we know how to switch it.
"""
import asyncio

from plugwise_usb import Stick

PORT = "/dev/ttyUSB0"


async def main() -> None:
    stick = Stick(PORT)
    print("connect...")
    await stick.connect()
    print("initialize...")
    await stick.initialize()
    print(f"stick MAC: {stick.mac_stick}  coordinator: {stick.mac_coordinator}")

    print("discover nodes (may take a while)...")
    try:
        await asyncio.wait_for(stick.discover_nodes(), timeout=75)
    except asyncio.TimeoutError:
        print("(discovery timed out — showing what was found so far)")

    nodes = stick.nodes
    print(f"=== {len(nodes)} node(s) ===")
    for mac, node in nodes.items():
        keys = ("relay", "switch", "power", "energy", "turn", "on", "off")
        attrs = [m for m in dir(node)
                 if not m.startswith("_") and any(k in m.lower() for k in keys)]
        print(f"  MAC={mac}  type={type(node).__name__}")
        print(f"    relay/power attrs: {attrs}")
    await stick.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
