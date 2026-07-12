# Module 3 — Problem generator

Materialises a PDDL problem instance from the current world-state snapshot using Jinja2 templates. Fires whenever a significant state change happens, or every 30 s as a fallback.

**Subscribes:** `library/state`
**Publishes:** `library/problem` (path or inline PDDL)

**Stack.** Python 3, `jinja2`.
**Templates:** `pddl/templates/`.

**Owner:** Dennis  ·  **Sprint:** 3 (2026-06-08 → 2026-06-24)
