<!--
Devpost draft for Fireline. Paste each section into the matching Devpost field.
Before submitting, resolve every TODO and delete these comments.
Upload, in this order: docs/img/console-alert.png (hero), docs/img/architecture.png,
docs/img/console-alerts.png, a photo of the unit on its tree mount, and 1-2 more real screenshots.
The console screenshots use simulated units; swap in captures from the real gw-01 alert once the full chain passes.
"178 bytes" was measured on a simulated event; replace it with the real gw-01 event size from the link log.
-->

# Fireline

**Tagline:** Satellites see a wildfire once it is big. Fireline sees the first smoke.

## Inspiration

From January 1 to April 13, 2025, the Florida Forest Service counted **1,300 wildfires and 57,025 acres burned** ([FOX 35](https://www.fox35orlando.com/news/florida-wildfire-map-2025)). Much of that land is remote: no power lines, no cell signal, nobody watching.

Satellites can't close that gap on their own. The ones sharp enough to see a small fire pass over a few times a day: VIIRS has about **375 m pixels and 3 to 4 looks a day** at mid-latitudes ([NASA Earthdata](https://www.earthdata.nasa.gov/data/instruments/viirs/viirs-i-band-375-m-active-fire-data)). Clouds and tree canopy hide early smoke from orbit. Ground cameras see smoke sooner, but they need a tower, grid power and an internet connection.

We wanted a camera box you can strap to a tree in the middle of nowhere that decides on its own whether it is seeing smoke, and that sends only what matters.

## What it does

Fireline is a flock of tree-mounted camera units and a live console for the crew that manages them. Each unit runs a smoke detection model on its own NVIDIA Jetson, wakes up only when the weather says fire is likely, and sends a single alert packet of 340 bytes or less over a satellite link. The console puts every unit on a map and sounds the alarm the moment one of them confirms smoke.

- **Smoke detection on the device:** Pyronear's open YOLO smoke model runs on the Jetson's GPU. Smoke must appear in at least 4 of the last 6 frames, which filters out clouds, fog and dust.
- **Weather-gated wake-up:** a cheap humidity sensor on an ESP32 sets a fire-risk tier. The Jetson scans every 30 minutes when it's humid, every 5 minutes when it's drying out, and continuously in critical fire weather.
- **Satellite-sized alerts:** every message fits the 340-byte limit of an Iridium short burst data message. A smoke event is 178 bytes. Images never cross the satellite link.
- **A live console:** a fleet map with markers colored by state, an alarm and desktop notification that fly the map to the unit, weather charts for each unit, and a link log showing each packet's size and satellite delay.
- **Plain-language write-ups:** each incident gets an instant summary ("Smoke seen by gw-14 in 5 of 6 frames during critical fire weather (34 °C, 22 % humidity). Likely early wildfire."), which Gemma 3 then rewrites for the crew. Gemma also gives a second opinion on the smoke crop.

**The demo:** we point a hair dryer at the sensor. Humidity drops, the status LED goes from green to orange, and the Jetson starts scanning. We hold a smoke video up to the camera. A few seconds later the console sounds an alarm, the map flies to the unit, and the alert card shows the packet that crossed the simulated satellite link.

## How we built it

![Fireline architecture](https://raw.githubusercontent.com/kateye31/jetsonyay/1.0/docs/img/architecture.png)

**DHT11 → ESP32 sets the fire-risk tier → MQTT wakes the Jetson → smoke model + 4-of-6 frame check → interest score → 340-byte packet over the simulated satellite link → FastAPI on Azure → WebSocket → every open console**

**Field unit (hardware)**
- **NVIDIA Jetson Orin Nano** runs the smoke model on its GPU with **TensorRT**, through **Ultralytics**. It stays warm in low-power mode until the ESP32 asks for a scan.
- **ESP32** (Arduino) is the always-on sentry. It reads a **DHT11**, averages 3 readings, changes tier only after 3 agreeing readings, and drives the status LED and buzzer.
- **MQTT** with a **Mosquitto** broker on the Jetson connects the two inside the box.

**AI/ML**
- **Pyronear's YOLO wildfire smoke model** from **Hugging Face** (Apache 2.0), trained on Pyro-SDIS, a dataset of labelled smoke images from fixed ground cameras. No training needed.
- An interest score: `average confidence × (frames with smoke / 6) × fire-weather weight`. Smoke in critical weather outranks a faint blob on a humid day. An alert fires at 0.5.
- **Gemma 3 (4B)** served by **Ollama** writes each incident up and checks the smoke crop.

**Backend and infrastructure**
- **FastAPI** + **SQLite** ground station: a satellite simulator (340-byte limit, 5–20 s delay, optional drops), incident grouping, offline detection, and a WebSocket for live updates.
- **Azure** VM running **Docker Compose**: the app, Gemma on Ollama, and **Caddy** for automatic HTTPS (browsers only allow notifications on secure sites).

**Frontend**
- **React**, **TypeScript** and **Vite**, with **Leaflet** for the map on Esri satellite imagery.

## Challenges we ran into

<!-- TODO: these are drawn from the code. Keep the ones that actually slowed you down, and add any we can't see
     from the repo (for example the Jetson PyTorch install, the hotspot, or the camera). -->

- **A satellite link delivers out of order.** With a 5–20 s random delay, an older heartbeat can land after a newer one. The ground station only lets the newest packet set a unit's state. It treats a packet as a duplicate only when the unit, counter and timestamp all match, because a rebooted unit restarts its counter.
- **340 bytes is a tight budget.** We used short keys and rounded numbers, and kept images off the satellite link entirely. The unit refuses to send anything over the limit.
- **A Jetson is slow to boot.** Power-cycling it for every scan wasn't practical, so the cheap ESP32 does the always-on watching and the Jetson stays idle with the model loaded until it's needed.
- **AI write-ups on a CPU-only server.** Gemma on a CPU VM can take a while. The console shows a template summary instantly, and Gemma's version replaces it when it arrives. If Gemma never answers, the alert still works.
- **We changed the architecture mid-build.** We started with a Raspberry Pi ground station and an installed desktop app, and merged them into one hosted website. That meant fewer devices at the judging table, and anyone on the crew can open the console.

## Accomplishments that we're proud of

- **Detection never leaves the forest.** The decision "is this smoke?" happens on the box. Only a 178-byte verdict crosses the satellite link, which answers the reason ground cameras need towers and internet today.
- **The whole chain works end to end:** weather sensor, wake-up, on-device detection, satellite-sized uplink, live alert on the map.
- **Honest about what's real.** The satellite link and most of the fleet are simulated, and the console labels every simulated unit on screen.

<!-- TODO: add one measured number from the Jetson, e.g. "the smoke model runs at N frames per second with TensorRT"
     and "smoke to alert on screen in N seconds". Only use numbers you measured. -->

## What we learned

<!-- TODO: edit to match what each of you actually learned. -->

- How to deploy a YOLO model to a Jetson and export it to TensorRT
- How to design a message format around a hard 340-byte limit
- How to keep state consistent when messages arrive late, out of order or twice
- How to split work across embedded, ML, backend and frontend lanes by agreeing on a packet contract in the first hour

## What's next for Fireline

- **Tap to place:** an NFC tag on each tree holds its name and coordinates, so a crew sets a unit's location with one tap.
- **Locate the fire:** two units seeing the same smoke from different angles can triangulate where it is.
- **One modem per flock:** units relay to each other over LoRa radio, so only one carries the satellite modem.
- **Field-ready power:** cut the Jetson's power completely between scans, with solar and a LiFePO4 battery.
- **Test on Florida scenery:** Pyronear's model was trained on other regions' landscapes, so it needs testing against local false alarms like dust and prescribed burns.

## Built with

nvidia-jetson, tensorrt, ultralytics, yolo, hugging-face, pyronear, esp32, arduino, dht11, mqtt, mosquitto, python, fastapi, sqlite, websockets, gemma, ollama, azure, docker, caddy, react, typescript, vite, leaflet

## Try it out

- GitHub: https://github.com/kateye31/jetsonyay
<!-- TODO: live console URL, if the Azure site is up: https://... -->
<!-- TODO: demo video (YouTube), 60-90 seconds -->
