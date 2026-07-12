# Module 5 — Execution

Pops the next action from the current plan, dispatches it to the IoT layer, watches for divergence between expected and observed effects, and asks the planner for a fresh plan if drift exceeds 10 %.

**Subscribes:** `library/plan`, `library/state`, `library/overrides`
**Publishes:** `library/actions`

**Stack.** Python 3, `asyncio`.

**Owner:** _TBD_  ·  **Sprint:** 4 (2026-06-25 → 2026-07-06)
