"""Toggle a Plugwise Circle+ relay to prove actuator control.

Connects to the USB stick, finds the Circle+ coordinator, reads the relay
state, switches it ON then OFF (with a pause), and reports each transition.
This is the smoke-test for the actuator half of the IoT layer.

Run on the Edge Pi:
    .venv/bin/python modules/iot/plugwise_relay.py
"""
import asyncio

from plugwise_usb import Stick

PORT = "/dev/ttyUSB0"
CIRCLE_PLUS = "000D6F0000729939"


async def main() -> None:
    stick = Stick(PORT)
    await stick.connect()
    await stick.initialize()
    print(f"coordinator: {stick.mac_coordinator}")
    try:
        await asyncio.wait_for(stick.discover_nodes(), timeout=75)
    except asyncio.TimeoutError:
        print("(discovery timed out — proceeding with known nodes)")

    # Make sure registered nodes are loaded before we touch the relay.
    try:
        await asyncio.wait_for(stick.load_nodes(), timeout=40)
    except Exception as e:  # noqa: BLE001
        print(f"(load_nodes: {e!r})")

    node = stick.nodes.get(CIRCLE_PLUS)
    if node is None:
        print(f"Circle+ {CIRCLE_PLUS} not found in {list(stick.nodes)}")
        await stick.disconnect()
        return

    # Load this node's state if it exposes a loader.
    if hasattr(node, "load"):
        try:
            await asyncio.wait_for(node.load(), timeout=30)
        except Exception as e:  # noqa: BLE001
            print(f"(node.load: {e!r})")

    print(f"relay before: {getattr(node, 'relay_state', '?')}")
    print("switching ON...")
    await node.set_relay(True)
    await asyncio.sleep(2)
    print(f"relay now: {getattr(node, 'relay_state', '?')}")
    print("switching OFF...")
    await node.set_relay(False)
    await asyncio.sleep(2)
    print(f"relay now: {getattr(node, 'relay_state', '?')}")
    print("switching back ON (leave powered)...")
    await node.set_relay(True)
    await asyncio.sleep(1)
    print(f"relay final: {getattr(node, 'relay_state', '?')}")
    await stick.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
