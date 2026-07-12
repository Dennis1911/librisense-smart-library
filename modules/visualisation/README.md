# Module 6 — Visualisation

Browser dashboard. Renders live world-state on a floor-plan heatmap, 24 h trend charts, Pomodoro focus rings per learner, an energy tile, and — critically — the currently-executing plan as a Gantt-style timeline. Override drawer publishes user controls back to MQTT.

**Subscribes:** `library/state`, `library/plan`
**Publishes:** `library/overrides`

**Stack.** React + Recharts (frontend), FastAPI + socket.io (WebSocket bridge to MQTT).

**Owner:** _TBD_  ·  **Sprint:** 2 → 4 (continuous)
