# Fireline

**Satellites see a wildfire once it is big. Fireline sees the first smoke.**

Fireline is a flock of tree-mounted camera units that spot wildfire smoke minutes after ignition, in places
with no grid, no internet and nobody watching. Each unit runs the smoke model on its own NVIDIA Jetson, wakes up
only when the weather says fire is likely, and sends tiny (≤ 340 B) alert packets over a satellite link to the
**Fireline web console**. The console runs on AMD Developer Cloud, where **Gemma** writes each incident up for the fire crew.

Knight Hacks IX · Oct 9–11, 2026.

## Architecture

```
 Field unit (no grid, no internet)                     AMD Developer Cloud (one MI300X droplet)
┌──────────────────────────────────────┐            ┌────────────────────────────────────────────┐
│ DHT11 ─► ESP32 sentry ─MQTT─► Jetson  │  ≤ 340 B   │  fireline (FastAPI)                         │
│          fire-risk tier      Pyronear │──uplink───►│   ├ simulated satellite link (size, delay)  │──WebSocket──► browsers
│          wakes the Jetson    YOLO     │  JSON      │   ├ units / incidents / link log (SQLite)   │              (fleet map,
│                              scoring  │            │   └ serves the React site                   │               alerts, unit
│                                       │──snapshot─►│  gemma (vLLM, ROCm) ◄─ incident write-ups   │               detail)
└──────────────────────────────────────┘ side chan. └────────────────────────────────────────────┘
```

The old plan had a Raspberry Pi ground station plus an installed Tauri desktop app. Both are now this one website:
the server is where satellite messages land, and the console is a page anyone on the crew can open.

| Folder | What | Owner |
|---|---|---|
| `server/` | FastAPI: `/api/uplink` behind the satellite simulator, incidents, offline detection, Gemma summaries, WebSocket, serves `web/dist` | Backend |
| `web/` | React + Vite + Leaflet: fleet map, alert feed, unit detail, settings | App |
| `jetson/` | Packet builder, interest scoring, ordered uplink queue, scan loop (`scan.py`) | ML / Jetson |
| `firmware/` | ESP32 sentry (DHT11, tiers, MQTT, LEDs); not started yet | Hardware |
| `tools/fake_fleet.py` | Simulated units in Ocala National Forest + hand-fired smoke events | Anyone |
| `deploy/` | Docker Compose for the AMD droplet: app + Gemma on vLLM + Caddy HTTPS | Backend |
| `docs/protocol.md` | **The JSON contract.** Read this first | Everyone |

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
GEMMA_BASE_URL=http://<droplet>:8001/v1 GEMMA_MODEL=google/gemma-3-27b-it uvicorn app.main:app
```

Gemma gets the incident numbers and, when `GEMMA_VISION=1`, the smoke crop. That gives a second opinion
on whether the crop shows smoke, cloud, fog or dust.

## Deploy to AMD Developer Cloud

1. Create a GPU droplet (MI300X) with a ROCm image, and open ports 80 and 443.
2. Accept the Gemma license on Hugging Face and create a read token.
3. On the droplet:
   ```bash
   git clone https://github.com/kateye31/jetsonyay.git && cd jetsonyay/deploy
   cp ../.env.example .env      # set HF_TOKEN; SITE_ADDRESS=<ip-with-dashes>.sslip.io for free HTTPS
   docker compose up -d --build
   docker compose logs -f gemma  # first start downloads the model
   ```
4. Point the Jetson at it: `FIRELINE_URL=https://<site> python jetson/scan.py`.

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
