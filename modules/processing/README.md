# Module 2 — Processing

Aggregates raw sensor streams into a coherent world-state snapshot, runs the learner finite-state machine, computes the CO₂ proxy and comfort index, and persists 24 h of history.

**Subscribes:** `library/sensors/*`
**Publishes:** `library/state`

**Stack.** Python 3, `numpy`, SQLite or InfluxDB (decision pending — see [PLANNING.md §7](../../PLANNING.md#7--open-decisions-resolve-early)).

**Owner:** _TBD_  ·  **Sprint:** 2 (2026-05-21 → 2026-06-07)
