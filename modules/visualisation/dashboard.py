"""LibriSense dashboard backend (Core node).

A small FastAPI app that bridges MQTT -> WebSocket and serves a live
single-page dashboard. It subscribes to library/state (the aggregated world
state) and library/sensors/# (raw streams), keeps the latest snapshot, and
pushes it to every connected browser over a WebSocket.

Run on the Core Pi:
    .venv/bin/uvicorn modules.visualisation.dashboard:app --host 0.0.0.0 --port 8000

Then open from any device on the LAN:
    http://librisense-core.local:8000
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import yaml
import paho.mqtt.client as mqtt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

REPO = Path(__file__).resolve().parents[2]
TOPICS = REPO / "config" / "topics.yaml"
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="LibriSense Dashboard")

# Latest data, updated by the MQTT thread, read by WebSocket handlers.
latest: dict = {"state": {}, "sensors": {}, "plan": {}, "actuators": {}}


def _on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)
    except ValueError:
        return
    if msg.topic == "library/state":
        latest["state"] = payload
    elif msg.topic == "library/plan":
        latest["plan"] = payload
    elif msg.topic.startswith("library/sensors/"):
        name = msg.topic.rsplit("/", 1)[-1]
        latest["sensors"][name] = payload
    elif msg.topic.startswith("library/actuators/"):
        name = msg.topic.rsplit("/", 1)[-1]
        latest["actuators"][name] = payload


def _start_mqtt() -> mqtt.Client:
    broker = yaml.safe_load(open(TOPICS))["broker"]
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"{broker.get('client_id_prefix','librisense')}-dashboard")
    client.on_connect = lambda c, u, f, rc, p: (
        c.subscribe("library/state"), c.subscribe("library/sensors/#"),
        c.subscribe("library/plan"), c.subscribe("library/actuators/#"))
    client.on_message = _on_message
    host = os.environ.get("MQTT_HOST", broker["host"])
    client.connect(host, broker.get("port", 1883), 60)
    client.loop_start()
    return client


@app.on_event("startup")
def startup() -> None:
    app.state.mqtt = _start_mqtt()


@app.on_event("shutdown")
def shutdown() -> None:
    app.state.mqtt.loop_stop()
    app.state.mqtt.disconnect()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_text(json.dumps(latest))
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass


# Serve any other static assets (none yet, but future-proof).
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
