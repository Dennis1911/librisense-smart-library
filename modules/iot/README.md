# Module 1 — IoT layer

Drives every physical and software sensor/actuator and bridges them to MQTT. The rest of the system never touches hardware directly.

**Publishes:** `library/sensors/<type>`
**Subscribes:** `library/actions`

**Stack.** Python 3, `paho-mqtt`, `sense-hat`, `grovepi`, `plugwise`.

**Owner:** _TBD_  ·  **Sprint:** 1 (2026-05-06 → 2026-05-20)
