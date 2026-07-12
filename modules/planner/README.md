# Module 4 — AI Planner

Solves the PDDL problem and emits a plan. Primary planner is **Fast Downward** (`seq-opt-lmcut`); fallback is **ENHSP** for numeric-heavy instances.

**Subscribes:** `library/problem`
**Publishes:** `library/plan`

**Stack.** Fast Downward (C++ binary) wrapped by a Python subprocess; ENHSP as fallback.

**Owner:** Dennis  ·  **Sprint:** 3 (2026-06-08 → 2026-06-24)

## Deployment (Core Pi)

Fast Downward is cloned + built on the Core Pi at `~/fast-downward` (built 2026-05-30, `builds/release/bin/downward`). Build was a plain `./build.py` (cmake 3.31, g++ 14.2, ~4 min on the Pi 5).

Working invocation (verified against a trivial domain):

```bash
python3 ~/fast-downward/fast-downward.py domain.pddl problem.pddl \
        --search "astar(blind())"
# → writes sas_plan in the cwd
```

For LibriSense's numeric domain we'll switch the search to a numeric-capable
config (e.g. `--evaluator "hff=ff()" --search "lazy_greedy([hff])"`), and add
ENHSP as a fallback for heavy numeric fluents per the proposal.

The Python wrapper (this module) will: render cwd, call `fast-downward.py`,
parse `sas_plan`, and publish the plan JSON on `library/plan`.
