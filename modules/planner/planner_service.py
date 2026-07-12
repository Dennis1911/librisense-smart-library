"""LibriSense planner wrapper (Core node) — module 4.

Subscribes to library/problem, runs Fast Downward on each instance, parses
the resulting plan, and publishes a structured plan on library/plan.

Planner config: A* with the LM-cut heuristic — Fast Downward's optimal
classical search for tasks with action costs. Our problems are tiny (one
zone, a handful of actions) so optimal planning returns in milliseconds.

Robustness:
  * empty goal (nothing to do)  -> publish an empty plan, skip Fast Downward
    (lmcut returns SEARCH_UNSUPPORTED on an empty goal)
  * unsolvable / timeout / error -> publish a plan with the matching status
  * each run uses its own temp dir (no output.sas races between instances)

Run on the Core Pi:
    .venv/bin/python modules/planner/planner_service.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
import paho.mqtt.client as mqtt

REPO = Path(__file__).resolve().parents[2]
TOPICS = REPO / "config" / "topics.yaml"
DOMAIN = REPO / "pddl" / "domain" / "librisense.pddl"
FAST_DOWNWARD = Path.home() / "fast-downward" / "fast-downward.py"

SEARCH = "astar(lmcut())"   # optimal classical search with action costs
PLAN_TIMEOUT_S = 20

# A plan step "(turn_on_lamp reading-1)" -> name + args.
_STEP_RE = re.compile(r"\(([^)]+)\)")


def parse_plan(plan_dir: Path) -> tuple[list[dict], int | None]:
    """Read sas_plan -> list of {name, args} + total cost (None if absent)."""
    plan_file = plan_dir / "sas_plan"
    if not plan_file.exists():
        return [], None
    actions: list[dict] = []
    cost: int | None = None
    for line in plan_file.read_text().splitlines():
        line = line.strip()
        if line.startswith(";"):
            m = re.search(r"cost\s*=\s*(\d+)", line)
            if m:
                cost = int(m.group(1))
            continue
        m = _STEP_RE.match(line)
        if m:
            tokens = m.group(1).split()
            actions.append({"name": tokens[0], "args": tokens[1:]})
    return actions, cost


def run_fast_downward(problem_text: str) -> dict:
    """Run Fast Downward on the problem; return a plan dict with status."""
    work = Path(tempfile.mkdtemp(prefix="librisense-plan-"))
    try:
        prob = work / "problem.pddl"
        prob.write_text(problem_text)
        proc = subprocess.run(
            ["python3", str(FAST_DOWNWARD), "--plan-file", str(work / "sas_plan"),
             str(DOMAIN), str(prob), "--search", SEARCH],
            cwd=work, capture_output=True, text=True, timeout=PLAN_TIMEOUT_S)
        # Fast Downward driver exit codes: 0 = plan found; 11/12 = proved
        # unsolvable / no solution; others = error.
        if (work / "sas_plan").exists() or "Solution found" in proc.stdout:
            actions, cost = parse_plan(work)
            return {"status": "solved", "actions": actions, "cost": cost}
        if proc.returncode in (11, 12) or "exhausted" in proc.stdout \
                or "unsolvable" in proc.stdout.lower():
            return {"status": "unsolvable", "actions": [], "cost": None}
        return {"status": "error", "actions": [], "cost": None,
                "detail": (proc.stdout + proc.stderr)[-300:]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "actions": [], "cost": None}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    broker = yaml.safe_load(open(TOPICS))["broker"]

    def on_connect(c, u, f, rc, p):
        c.subscribe("library/problem")
        print("[planner] subscribed to library/problem")

    def on_message(c, u, msg):
        try:
            req = json.loads(msg.payload)
        except ValueError:
            return
        goals = req.get("goals", [])
        if not goals:
            plan = {"status": "empty", "actions": [], "cost": 0}
        else:
            t0 = time.perf_counter()
            plan = run_fast_downward(req["problem"])
            plan["solve_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        plan["ts"] = datetime.now(timezone.utc).isoformat()
        plan["goals"] = goals
        # Retained: the dashboard shows the current plan immediately on load.
        c.publish("library/plan", json.dumps(plan), retain=True)
        steps = " -> ".join(f"{a['name']}({','.join(a['args'])})"
                            for a in plan["actions"]) or "(no actions)"
        print(f"[planner] {plan['status']}: {steps}"
              + (f"  cost={plan['cost']}" if plan.get("cost") is not None else ""))

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"{broker.get('client_id_prefix','librisense')}-planner")
    client.on_connect = on_connect
    client.on_message = on_message
    host, port = broker["host"], broker.get("port", 1883)
    while True:
        try:
            client.connect(host, port, 60)
            break
        except OSError:
            time.sleep(5)
    print(f"[planner] connected to {host}:{port}; Fast Downward = {FAST_DOWNWARD}")
    client.loop_forever()


if __name__ == "__main__":
    main()
