"""LibriSense execution engine (Core node) — module 5.

Subscribes to library/plan and dispatches the plan's actions onto
library/actions for the IoT layer to carry out. Because the upstream loop
re-plans on every significant state change, dispatching the current plan's
actions each time yields a stable closed-loop controller: plan -> act ->
state changes -> re-plan -> act ...

To avoid spamming the actuators, an action is only re-dispatched when the
plan actually changes (deduplicated against the last dispatched set).

Run on the Core Pi:
    .venv/bin/python modules/execution/executor.py
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import yaml
import paho.mqtt.client as mqtt
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOPICS = REPO / "config" / "topics.yaml"


def main() -> None:
    broker = yaml.safe_load(open(TOPICS))["broker"]
    last_dispatched: list | None = None

    def on_connect(c, u, f, rc, p):
        c.subscribe("library/plan")
        print("[executor] subscribed to library/plan")

    def on_message(c, u, msg):
        nonlocal last_dispatched
        try:
            plan = json.loads(msg.payload)
        except ValueError:
            return
        actions = plan.get("actions", [])
        signature = [(a["name"], tuple(a["args"])) for a in actions]
        if signature == last_dispatched:
            return  # unchanged plan — nothing new to dispatch
        last_dispatched = signature

        if not actions:
            print(f"[executor] plan '{plan.get('status')}' — no actions to dispatch")
            return
        for a in actions:
            cmd = {"ts": datetime.now(timezone.utc).isoformat(),
                   "action": a["name"], "args": a["args"]}
            c.publish("library/actions", json.dumps(cmd))
        steps = " -> ".join(f"{a['name']}({','.join(a['args'])})" for a in actions)
        print(f"[executor] dispatched: {steps}")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"{broker.get('client_id_prefix','librisense')}-executor")
    client.on_connect = on_connect
    client.on_message = on_message
    host, port = broker["host"], broker.get("port", 1883)
    while True:
        try:
            client.connect(host, port, 60)
            break
        except OSError:
            time.sleep(5)
    print(f"[executor] connected to {host}:{port}")
    client.loop_forever()


if __name__ == "__main__":
    main()
