"""Broker host resolution with fallbacks.

The Core's MQTT broker is reachable under different addresses depending on
the network mode:
  * home WiFi  -> librisense-core.local (mDNS, IP-independent)
  * hotspot    -> 10.42.0.1 (Core is the access point; .local/mDNS does not
                  traverse the AP, so the Edge needs the fixed AP gateway IP)
  * core-local -> 127.0.0.1

`pick_broker_host` probes each candidate with a quick TCP connect and returns
the first that answers, so every node connects in whichever mode is active.
"""
from __future__ import annotations

import socket
import time


def candidates(broker: dict) -> tuple[list[str], int]:
    hosts = [broker["host"], *broker.get("fallback_hosts", [])]
    return hosts, broker.get("port", 1883)


def pick_broker_host(broker: dict, probe_timeout: float = 3.0) -> tuple[str, int]:
    """Return (host, port) of the first reachable broker candidate.

    Blocks (retrying the full candidate list every 5 s) until one answers, so
    callers can use it in place of a bare connect with built-in resilience.
    """
    hosts, port = candidates(broker)
    while True:
        for host in hosts:
            try:
                with socket.create_connection((host, port), timeout=probe_timeout):
                    return host, port
            except OSError:
                continue
        print(f"[broker] none of {hosts}:{port} reachable; retry in 5s")
        time.sleep(5)
