# Fireline message contract

This is the contract between every role. Change it here first, then in
`server/app/models.py` and `jetson/fireline_unit/packet.py`.

## Uplink packets (Jetson → satellite → web server)

`POST /api/uplink` with a compact JSON body (no spaces). **Max 340 bytes**: that's the
Iridium short-burst-data size, and the simulated link rejects anything bigger with `413`.

**Heartbeat**: sent every 60 s, proves the unit is alive:

```json
{"v":1,"id":"gw-03","seq":117,"t":1760061540,"typ":"hb","st":"scan","risk":"elev","temp":31.2,"rh":38,"bat":72,"up":5421}
```

**Event**: sent immediately, never waits for the next heartbeat:

```json
{"v":1,"id":"gw-03","seq":118,"t":1760061600,"typ":"evt","cls":"smoke","conf":0.87,"int":0.82,"fr":5,"risk":"crit","temp":34.1,"rh":22,"box":[412,180,96,140],"lat":28.6024,"lon":-81.2001,"bat":71}
```

| Field | Meaning |
|---|---|
| `v` | Schema version (1) |
| `id`, `seq` | Unit id and counter. The server drops a packet as a duplicate when `id`, `seq` **and** `t` all match an earlier delivered packet (a reboot restarts `seq` but not `t`) |
| `t` | Unix time in seconds, set on the unit |
| `typ` | `hb` heartbeat, `evt` event, `tmp` tamper |
| `st` | Unit state: `sleep`, `scan`, `alert` |
| `risk` | Fire-risk tier: `low`, `elev`, `crit` |
| `cls`, `conf`, `int`, `fr` | Detected class, average confidence, interest score, frames with smoke out of 6 |
| `box` | Smoke box in the frame: x, y, width, height in pixels |
| `temp`, `rh`, `bat` | °C, % humidity, % battery |
| `up` | Uptime in seconds (optional) |
| `lat`, `lon`, `loc` | Position and mounting-spot name. Always on events; on heartbeats only the first one after an NFC relocation |
| `sim` | `1` only for units from `tools/fake_fleet.py`, so the site labels them as simulated |

**Responses:** `202` means the satellite accepted the packet, and it's delivered 5–20 s later
(1–4 s in demo mode). `413` means the packet is too big and `422` means it's malformed; don't
retry either. `503` is a simulated link drop, so retry in order.

## Snapshot side channel (not satellite)

`POST /api/units/{id}/snapshot` with raw `image/jpeg` (about 160 px wide, ≤ 256 KB). A crop is far too big for a
satellite message; in the pitch, a real unit sends images only on request or over a faster link. The
Jetson uploads the crop *before* sending the event so it is attached when the incident opens.

## Field-unit MQTT (ESP32 ↔ Jetson, broker on the Jetson, port 1883)

| Topic | From → To | Payload |
|---|---|---|
| `unit/hb` | ESP32 → Jetson | `{"risk":"elev","temp":31.2,"rh":38,"bat":72,"up":5421}` every 60 s; the Jetson wraps it in an uplink heartbeat |
| `unit/scan` | ESP32 → Jetson | `{"risk":"crit","temp":34.1,"rh":22}` when a scan is due for the tier |
| `unit/tamper` | ESP32 → Jetson | `{}`, lid switch opened |
| `unit/loc` | ESP32 → Jetson | `{"lat":28.6024,"lon":-81.2001,"loc":"Juniper Prairie"}` from an NFC tag tap |
| `unit/state` | Jetson → ESP32 | `sleep` / `scan` / `alert` (retained), which drives the LED and buzzer |
| `unit/idle` | Jetson → ESP32 | `1` after 5 quiet minutes (30 s in demo mode) |

## Fire-risk tiers (computed on the ESP32)

These are starting thresholds for the demo, not an official fire-danger formula.

| Tier | Condition | Jetson scans | LED |
|---|---|---|---|
| `low` | Humidity above 50 % | Every 30 min | Green |
| `elev` | Humidity 30–50 %, or temp above 30 °C | Every 5 min | Yellow |
| `crit` | Humidity below 30 % and temp above 32 °C | Continuously | Orange |
| alert | Smoke confirmed by the Jetson | Continuously | Red + buzzer |

Only change tiers after 3 readings in a row agree (hysteresis).

## Interest score (Jetson)

`interest = c_bar * (n_smoke / 6) * w_risk`, with `w_risk` = 0.6 / 0.8 / 1.0 for low / elev / crit.
Smoke must be in at least 4 of the last 6 frames. The unit alerts at 0.5 and stays awake while the score is above 0.2.

## Web API (browser ↔ server)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/units`, `/api/units/{id}` | Fleet, or one unit with heartbeats, events and link log |
| GET | `/api/incidents`, `/api/events`, `/api/packets` | History |
| POST | `/api/incidents/{id}/ack` · `/resolve` · `/summarize` | Operator actions; `summarize` re-asks Gemma |
| POST / DELETE | `/api/units` · `/api/units/{id}` | Pre-place or remove a unit |
| GET / PUT | `/api/settings` | Satellite-link sim and demo mode |
| GET | `/api/health` | Server and Gemma status |
| WS | `/ws` | Live `unit`, `incident`, `event`, `packet`, `heartbeat`, `settings` messages |
