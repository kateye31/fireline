# Fireline

**Satellites see a wildfire once it is big. Fireline sees the first smoke.**

Fireline is a flock of tree-mounted camera units that spot wildfire smoke minutes after ignition, in places
with no grid, no internet and nobody watching. Each unit runs the smoke model on its own NVIDIA Jetson, wakes up
only when the weather says fire is likely, and sends tiny (≤ 340 B) alert packets over a satellite link to the
**Fireline web console**. The console runs on an Azure VM, where **Gemma** writes each incident up for the fire crew.

Knight Hacks IX · Oct 9–11, 2026.

## Architecture

```
 Field unit (no grid, no internet)                     Azure (one Linux VM, CPU only)
┌──────────────────────────────────────┐            ┌────────────────────────────────────────────┐
│ DHT11 ─► ESP32 sentry ─MQTT─► Jetson  │  ≤ 340 B   │  fireline (FastAPI)                         │
│          fire-risk tier      Pyronear │──uplink───►│   ├ simulated satellite link (size, delay)  │──WebSocket──► browsers
│          wakes the Jetson    YOLO     │  JSON      │   ├ units / incidents / link log (SQLite)   │              (fleet map,
│                              scoring  │            │   └ serves the React site                   │               alerts, unit
│                                       │──snapshot─►│  gemma (Ollama, CPU) ◄─ incident write-ups  │               detail)
└──────────────────────────────────────┘ side chan. └────────────────────────────────────────────┘
```

The old plan had a Raspberry Pi ground station plus an installed Tauri desktop app. Both are now this one website:
the server is where satellite messages land, and the console is a page anyone on the crew can open.

| Folder | What | Owner |
|---|---|---|
| `server/` | FastAPI: `/api/uplink` behind the satellite simulator, incidents, offline detection, Gemma summaries, WebSocket, serves `web/dist` | Backend |
| `web/` | React + Vite + Leaflet: fleet map, alert feed, unit detail, settings | App |
| `jetson/` | Packet builder, interest scoring, ordered uplink queue, scan loop (`scan.py`) | ML / Jetson |
| `firmware/fireline_sentry/` | ESP32 sentry (Arduino): DHT11, fire-risk tiers, scan requests and heartbeats over MQTT, LEDs and buzzer | Hardware |
| `tools/fake_fleet.py` | Simulated units in Ocala National Forest + hand-fired smoke events | Anyone |
| `deploy/` | Docker Compose for the Azure VM: app + Gemma on Ollama + Caddy HTTPS | Backend |
| `docs/protocol.md` | **The JSON contract.** Read this first | Everyone |
| `docs/SETUP.md` | **Step-by-step setup** for the laptop, Azure server, Jetson and ESP32 | Everyone |

**New here? Follow [docs/SETUP.md](docs/SETUP.md).** It walks through every device in order.

## Run it locally

You need Python 3.11+ and Node 20+.

```bash
# 1. server (http://localhost:8000)
cd server
python -m venv .venv
.venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# 2. web, hot reload on http://localhost:5173 (proxies /api and /ws to :8000)
cd web
npm install
npm run dev

# 3. simulated fleet + a fake smoke alert
python tools/fake_fleet.py fleet --interval 10
python tools/fake_fleet.py event --unit gw-14
```

`npm run build` puts the site in `web/dist`, and then the server alone serves everything on :8000.

Set `DEMO_MODE=1` (or flip it in Settings) to cut the satellite delay to 1–4 s for the judging table.

### Gemma

Summaries are optional. Without `GEMMA_BASE_URL` the site uses the template summary
("Smoke seen by gw-03 in 5 of 6 frames during critical fire weather…"). Point it at any OpenAI-compatible
server to turn Gemma on:

```bash
GEMMA_BASE_URL=http://localhost:11434/v1 GEMMA_MODEL=gemma3:4b uvicorn app.main:app   # with Ollama installed locally
```

Gemma gets the incident numbers and, when `GEMMA_VISION=1`, the smoke crop. That gives a second opinion
on whether the crop shows smoke, cloud, fog or dust.

## Deploy to Azure

One `Standard_D4s_v5` Ubuntu VM (about $0.19/h) runs the whole stack with `docker compose`.
See [docs/SETUP.md, step 2](docs/SETUP.md#step-2-the-azure-server-30-min) for the click-by-click version.

```bash
git clone https://github.com/kateye31/jetsonyay.git && cd jetsonyay/deploy
cp ../.env.example .env      # SITE_ADDRESS=yourdomain.com, www.yourdomain.com
docker compose up -d --build
```

Then point the Jetson at it: `FIRELINE_URL=https://<site> python jetson/scan.py`.

HTTPS matters because browsers only allow desktop notifications on secure origins.

## What is real vs simulated

- **Real:** the field unit (ESP32 + DHT11 + Jetson + camera), on-device smoke detection, packet sizes, the web console, and Gemma.
- **Simulated:** the satellite link (real 340 B limit, artificial 5–20 s delay and optional drops), and every unit tagged `SIM` on the map.

### Git Workflow for the Repo

Please **do not push directly to `1.0`**. `1.0` is protected and changes need to go through a PR.

For each assignment/change:

**1. Make sure you're up to date**

```bash
git checkout 1.0
git pull origin 1.0
```

**2. Create a new branch**
Use a descriptive name:

```bash
git checkout -b your-name/assignment-name
```

Example:

```bash
git checkout -b john/project-1
```

**3. Make your changes**

**4. Commit your changes**

```bash
git add .
git commit -m "Add project 1"
```

**5. Push your branch**

```bash
git push -u origin your-name/assignment-name
```

**6. Open a Pull Request**
On GitHub, create a PR from your branch → `1.0`.

I'll review the PR and merge it into `1.0`.

**7. After the PR is merged, update your local `1.0`**

```bash
git checkout 1.0
git pull origin 1.0
```

Then create a new branch for your next change.
