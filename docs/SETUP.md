# Fireline setup, from zero

This guide assumes you have the repo and nothing else. Do the steps in order; each one ends with a check
so you know it worked before moving on.

## The big picture: what runs where

| Device | Code | What it does |
|---|---|---|
| **ESP32** (in the field box) | `firmware/fireline_sentry/` | Reads temp and humidity, decides the fire-risk tier, tells the Jetson when to scan, drives the LEDs and buzzer |
| **Jetson** (in the field box) | `jetson/` | Runs the MQTT broker the ESP32 talks to, runs the smoke model on the camera, and sends alert packets to the cloud |
| **AMD cloud server** | `server/` + `web/` + `deploy/` | Receives packets (through the fake satellite link), stores them, runs Gemma, and hosts the website |
| **Your laptop** | nothing to install | Opens the website in a browser. Also used to flash the ESP32 |
| **Phone hotspot** | – | Wi-Fi for the field box, plus the internet the Jetson needs to reach the cloud |

```
ESP32 ──MQTT (local Wi-Fi)──► Jetson ──HTTPS (internet)──► AMD server ◄── browser on the laptop
```

The ESP32 never talks to the internet. Only the Jetson does, and only with tiny packets.

## Step 1: run everything on your laptop first (10 min)

This proves the code works before any hardware or cloud is involved. You need **Python 3.11+** and **Node 20+**.

Open one terminal for the server:

```bash
cd server
python -m venv .venv
.venv\Scripts\activate          # Windows. macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cd ../web && npm install && npm run build && cd ../server
uvicorn app.main:app --port 8000
```

Open a second terminal for the fake fleet, from the repo root:

```bash
python tools/fake_fleet.py fleet --interval 10
```

Then open http://localhost:8000. ✅ **Check:** 8 dots appear over Ocala National Forest.

In a third terminal, fake a fire:

```bash
python tools/fake_fleet.py event --unit gw-14
```

✅ **Check:** a few seconds later a red toast appears, the map flies to gw-14, and the Alerts tab shows the incident.

## Step 2: the AMD cloud server (30–60 min, mostly waiting on downloads)

### 2a. Get a machine

1. Sign in to **AMD Developer Cloud** with your hackathon credits.
2. Create a **GPU droplet** (MI300X). Pick an image that comes with **ROCm and Docker**; the vLLM / ROCm quick-start images do.
3. Add your SSH key when it asks (or use the password it gives you).
4. Note the droplet's **public IP**, e.g. `129.212.1.2`.

From your laptop:

```bash
ssh root@129.212.1.2
```

✅ **Check:** `docker --version` and `rocm-smi` both print something. If `docker` is missing, install it with
`curl -fsSL https://get.docker.com | sh`.

### 2b. Get Gemma access

1. Make a Hugging Face account, open https://huggingface.co/google/gemma-3-27b-it and accept the license.
2. Go to Settings → Access Tokens and create a **Read** token.

### 2c. Start the stack

On the droplet:

```bash
git clone https://github.com/kateye31/jetsonyay.git
cd jetsonyay/deploy
cp ../.env.example .env
nano .env
```

In `.env`, set:
- `HF_TOKEN=` your token
- `SITE_ADDRESS=129-212-1-2.sslip.io`: your IP **with dashes**, plus `.sslip.io`. That gives you free HTTPS
  with no domain. You need HTTPS because browsers block desktop notifications on plain HTTP.

Save (Ctrl+O, Enter, Ctrl+X), then:

```bash
docker compose up -d --build
docker compose ps                 # all three services should be "running"
docker compose logs -f gemma      # first start downloads ~55 GB; wait for "Application startup complete"
```

Open the port if the droplet has a firewall: `ufw allow 80,443/tcp`.

✅ **Check:**
- `https://129-212-1-2.sslip.io` loads the site. It works right away, even while Gemma is still downloading.
- `https://129-212-1-2.sslip.io/api/health` shows `"gemma": {"enabled": true, "ok": true}` once Gemma is up.
- From your laptop, `python tools/fake_fleet.py --url https://129-212-1-2.sslip.io fleet --interval 10` puts dots on the cloud map.

**If Gemma will not start:** the site still works and alert cards fall back to the template summary.
The fast fix is a smaller model: set `GEMMA_MODEL=google/gemma-3-4b-it` in `.env`, then run `docker compose up -d gemma`.
If the `rocm/vllm` image itself fails, check `docker compose logs gemma` and try a specific tag from
https://hub.docker.com/r/rocm/vllm/tags in `docker-compose.yml`.

**After changing code:** `git pull && docker compose up -d --build fireline`.

## Step 3: the phone hotspot (5 min)

- Turn on the hotspot. **iPhone: turn on "Maximize Compatibility"**, because the ESP32 only speaks 2.4 GHz.
- Write down the network name and password; the ESP32 and Jetson both need them.
- The Jetson needs internet through this hotspot to reach the cloud server.

## Step 4: the Jetson (1–2 h; the model install is the slow part)

Plug a monitor and keyboard into the Jetson (or SSH into it), then join the hotspot Wi-Fi.

### 4a. Name it and install the MQTT broker

```bash
sudo hostnamectl set-hostname gw-jetson          # the ESP32 finds it as gw-jetson.local
sudo apt update && sudo apt install -y mosquitto mosquitto-clients git
git clone https://github.com/kateye31/jetsonyay.git ~/jetsonyay
sudo cp ~/jetsonyay/jetson/mosquitto.conf /etc/mosquitto/conf.d/fireline.conf
sudo systemctl restart mosquitto
sudo reboot
```

✅ **Check:** after the reboot, `mosquitto_sub -t 'unit/#' -v` runs and waits (leave it open for step 5).
`hostname -I` shows its IP; write it down as the ESP32's fallback.

### 4b. Get the smoke model running

Use Ultralytics' Jetson Docker image so you don't have to install PyTorch by hand, the classic time sink.
Pick the tag that matches your JetPack (`cat /etc/nv_tegra_release`; JetPack 6 uses `latest-jetson-jetpack6`):

```bash
sudo docker run -it --ipc=host --runtime=nvidia --network host --device /dev/video0 \
  -v ~/jetsonyay:/work -w /work/jetson ultralytics/ultralytics:latest-jetson-jetpack6
```

Then, inside the container:

```bash
pip install paho-mqtt huggingface_hub
huggingface-cli download pyronear/yolov8s yolov8s.pt --local-dir .
yolo export model=yolov8s.pt format=engine half=True      # TensorRT; takes several minutes, done once
```

✅ **Check:** point the camera at a printed smoke photo, then run
`yolo predict model=yolov8s.engine source=0 show=False` and watch the output for detections.

### 4c. Run the field unit

Still inside the container (use the real cloud address and this unit's coordinates):

```bash
FIRELINE_URL=https://129-212-1-2.sslip.io UNIT_ID=gw-03 UNIT_LAT=29.1800 UNIT_LON=-81.7800 \
UNIT_LOC="Juniper Prairie" MODEL=yolov8s.engine DEMO_MODE=1 python scan.py
```

✅ **Check:** it prints `unit gw-03 ready`. To test without the ESP32, open a second shell on the Jetson and
pretend to be it:

```bash
mosquitto_pub -t unit/hb -m '{"risk":"elev","temp":31.2,"rh":38,"bat":100,"up":60}'
mosquitto_pub -t unit/scan -m '{"risk":"crit","temp":34.1,"rh":22}'
```

The first command makes gw-03 appear on the cloud map tagged **REAL**. The second starts a scan; hold smoke in front of the camera.

**Fallback if TensorRT export fails:** use `MODEL=yolov8s.pt` (slower but works), or export ONNX on a laptop.

## Step 5: the ESP32 (30 min)

### 5a. Wire it

| Part | ESP32 pin | Notes |
|---|---|---|
| DHT11 data | GPIO 4 | VCC → 3.3V, GND → GND (3-pin modules have the resistor built in) |
| Green LED | GPIO 25 | through a 220 Ω resistor to GND (kit LED modules usually have one) |
| Yellow LED | GPIO 26 | same |
| Red LED | GPIO 27 | same |
| Buzzer (active) | GPIO 14 | other leg to GND |
| Lid switch (optional) | any free GPIO → GND | set `PIN_TAMPER` |
| Test button (optional) | any free GPIO → GND | set `PIN_TEST_BTN` |

Wired differently? Change the pin numbers at the top of the sketch.

### 5b. Flash it

1. Install the **Arduino IDE** on your laptop.
2. File → Preferences → "Additional boards manager URLs": add
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
3. Tools → Board → Boards Manager → install **esp32** by Espressif.
4. Sketch → Include Library → Manage Libraries → install **PubSubClient** (Nick O'Leary), **DHT sensor library**
   (Adafruit), and **Adafruit Unified Sensor**.
5. Open `firmware/fireline_sentry/fireline_sentry.ino`. Fill in `WIFI_SSID`, `WIFI_PASS`, and
   `JETSON_FALLBACK_IP` (the IP from step 4a).
6. Plug in the ESP32. Pick Tools → Board → **ESP32 Dev Module** and Tools → Port → the new COM port, then click **Upload**.
   If it hangs on "Connecting...", hold the **BOOT** button on the board until upload starts.
7. Tools → Serial Monitor, **115200 baud**.

✅ **Check:** the serial monitor shows `wifi ok`, `connecting to MQTT ... ok`, and a reading every 2 s.
On the Jetson, `mosquitto_sub` shows `unit/hb` messages, and the cloud map shows gw-03 updating.

## Step 6: the whole chain (the demo)

1. Laptop: open the site, click **Enable alert sound**, and turn on **Demo mode** in Settings.
2. Hair dryer on the DHT11, about 30 cm away in short bursts. The serial monitor shows the tier going `low → elev → crit`, the LED goes
   yellow then orange, and the ESP32 sends `scan`.
3. Smoke video or photo in front of the camera. The Jetson log counts `frames 4/6` and sends the event.
4. A few seconds later the site plays the chirp, shows the toast, flies the map to gw-03, and adds an alert card with
   the snapshot and Gemma's write-up. The ESP32 LED goes red and the buzzer chirps.

No hair dryer, or the sensor won't move? Type `fake 35 20` in the serial monitor.
Want to show a relocation? Type `loc 29.2200 -81.7400 Salt Springs` and the marker jumps on its next heartbeat.

## Troubleshooting

| Symptom | Fix |
|---|---|
| ESP32 never says `wifi ok` | Hotspot must be 2.4 GHz (iPhone: Maximize Compatibility). Check the password |
| ESP32 says `mDNS could not find` | Fine if the fallback IP is right. Otherwise set `JETSON_FALLBACK_IP` from `hostname -I` on the Jetson |
| ESP32 MQTT `failed (state -2)` | Mosquitto is not listening on the network. Redo the `mosquitto.conf` step and restart it |
| Some Android hotspots block device-to-device traffic | Use another phone |
| Unit shows grey on the map | No heartbeat for 120 s. Is `scan.py` running, and is the ESP32 connected? |
| Jetson log says `uplink failed` | The Jetson has no internet, or `FIRELINE_URL` is wrong. Try `curl https://<site>/api/health` on the Jetson |
| No desktop notification | The site must be on HTTPS (the sslip.io address) and you must click **Enable alert sound** once |
| Alert cards have no Gemma text | `/api/health` shows why; Gemma may still be downloading. The template summary is the fallback |
