# Fireline setup, from zero

This guide assumes you have the repo and nothing else. Do the steps in order; each one ends with a check
so you know it worked before moving on.

## The big picture: what runs where

| Device | Code | What it does |
|---|---|---|
| **ESP32** (in the field box) | `firmware/fireline_sentry/` | Reads temp and humidity, decides the fire-risk tier, tells the Jetson when to scan, drives the LEDs and buzzer |
| **Jetson** (in the field box) | `jetson/` | Runs the MQTT broker the ESP32 talks to, runs the smoke model on the camera, and sends alert packets to the cloud |
| **Azure server** | `server/` + `web/` + `deploy/` | Receives packets (through the fake satellite link), stores them, runs Gemma, and hosts the website |
| **Your laptop** | nothing to install | Opens the website in a browser. Also used to flash the ESP32 |
| **Phone hotspot** | – | Wi-Fi for the field box, plus the internet the Jetson needs to reach the cloud |

```
ESP32 ──MQTT (local Wi-Fi)──► Jetson ──HTTPS (internet)──► Azure server ◄── browser on the laptop
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

## Step 2: the Azure server (30 min)

One small Linux VM runs everything: the website, the API, and Gemma (on CPU, through Ollama).
It costs about **$0.17–0.20 an hour**, so a whole hackathon weekend is roughly $10 of your $100.

### 2a. Create the VM

In https://portal.azure.com → **Virtual machines → Create → Azure virtual machine**:

| Setting | Value |
|---|---|
| Subscription | Azure for Students |
| Resource group | Create new: `fireline` |
| VM name | `fireline` |
| Region | **East US** (closest to Florida). If a size is unavailable, try East US 2 |
| Image | **Ubuntu Server 24.04 LTS – x64** |
| Size | **Standard_D4s_v5** (4 vCPU, 16 GB RAM). Alternatives: `D4as_v5`, or `B4ms` if those are blocked |
| Authentication | SSH public key (let Azure generate one and **download the .pem**), username `azureuser` |
| Inbound ports | Allow **SSH (22), HTTP (80), HTTPS (443)** |
| Disk (Disks tab) | OS disk **64 GB**, Standard SSD |

Click **Review + create → Create**. Download the key when asked.

Avoid the smallest B-series sizes (B1s, B2s): Gemma will be painfully slow or will not fit in memory.

### 2b. Point your domain at the VM

Throughout this guide, replace `yourdomain.com` with your real domain.

1. **Make the IP permanent.** In the portal, open the VM → click its **Public IP address** → **Configuration** →
   set **Assignment: Static** → **Save**. Otherwise the IP can change when you stop and start the VM, and the domain
   would point at nothing. Copy the IP, e.g. `20.121.5.6`.
2. **Add DNS records** at your domain registrar (Namecheap, GoDaddy, Cloudflare, Porkbun...) → DNS settings:

   | Type | Host / Name | Value |
   |---|---|---|
   | A | `@` | `20.121.5.6` (your VM's IP) |
   | A | `www` | `20.121.5.6` |

   Delete any existing "parking" A or CNAME records for `@` and `www` that the registrar added.
   **Using Cloudflare?** Set both records to **DNS only** (grey cloud) so the server can get its own certificate.
3. ✅ **Check:** after a few minutes, `nslookup yourdomain.com` on your laptop prints your VM's IP. It can take up to
   an hour, but it is usually under 10 minutes.

You don't need to buy a certificate: Caddy (part of the stack) gets a free HTTPS certificate for the domain
automatically on first start. HTTPS matters because browsers only allow desktop notifications on secure sites.

### 2c. Log in and install Docker

From your laptop (in the folder where the .pem downloaded):

```bash
ssh -i fireline_key.pem azureuser@20.121.5.6     # your VM's IP
```

On Windows, if ssh complains the key is "too open", use the Bash tool or WSL, or right-click the file →
Properties → Security and remove every user except yourself.

On the VM:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && exit      # log out so the group change applies
```

SSH back in. ✅ **Check:** `docker run --rm hello-world` prints "Hello from Docker!".

### 2d. Start the stack

```bash
git clone https://github.com/kateye31/jetsonyay.git
cd jetsonyay/deploy
cp ../.env.example .env
nano .env                         # set SITE_ADDRESS=yourdomain.com, www.yourdomain.com
docker compose up -d --build
docker compose ps                 # fireline, gemma and caddy should all be "running"
docker compose logs -f gemma      # first boot pulls gemma3:4b (~3 GB); Ctrl+C to stop watching
docker compose logs caddy         # look for "certificate obtained successfully" for your domain
```

Save in nano with Ctrl+O, Enter, then Ctrl+X to exit.

✅ **Check:**
- `https://yourdomain.com` loads the site. It works right away, even while Gemma is still downloading.
- `https://yourdomain.com/api/health` shows `"gemma": {"enabled": true, "ok": true}` once the model is pulled.
- From your laptop: `python tools/fake_fleet.py --url https://yourdomain.com fleet --interval 10` puts dots on the cloud map,
  and `python tools/fake_fleet.py --url https://yourdomain.com event --unit gw-14` makes an alert. The Gemma text
  replaces the template summary 15–60 s later.

**Gemma too slow?** Set `GEMMA_MODEL=gemma3:1b` in `.env` (text only, much faster), then run `docker compose up -d`.
Alert cards always show the instant template summary first, so slow Gemma never delays an alert.

**After changing code:** `cd ~/jetsonyay && git pull && cd deploy && docker compose up -d --build fireline`.

**Save credits:** when you are done for the day, **Stop** the VM in the portal (status must say "Stopped (deallocated)").
Start it again before the demo; with the static IP, your domain keeps working. Delete the `fireline` resource group after the hackathon.

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
FIRELINE_URL=https://yourdomain.com UNIT_ID=gw-03 UNIT_LAT=29.1800 UNIT_LON=-81.7800 \
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

### 4d. Make it start by itself on every boot

Two one-time scripts turn the Jetson into a plug-in-and-go unit:

```bash
cd ~/jetsonyay/jetson
sudo bash hotspot_only.sh "Your Hotspot Name" "hotspot-password"
bash install_service.sh
```

- `hotspot_only.sh` makes the Jetson join **only** your phone hotspot. It connects at boot before anyone logs in
  and keeps retrying if the hotspot is off. Every other saved Wi-Fi network stays saved but never auto-connects.
  Run it from the Jetson's own keyboard if you can, because the Wi-Fi reconnects and an SSH session may drop.
- `install_service.sh` builds the `fireline-unit` image (Ultralytics + MQTT client) and installs a boot service.
  The service waits for the camera, starts `scan.py`, and restarts it if it ever crashes.
- Settings (server URL, unit ID, location, model) are in `/etc/fireline-unit.env`. After editing, run
  `sudo systemctl restart fireline-unit`.

Stop any container you started by hand first (`sudo docker rm -f fireline`); two copies would fight over the camera.

✅ **Check:** `sudo reboot`, wait about a minute without touching anything, and gw-03 turns live on the map.
Logs: `journalctl -u fireline-unit -f`.

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
| Site does not load / certificate error | DNS not pointing at the VM yet (`nslookup yourdomain.com`), ports 80/443 not open in the VM's Networking tab, or Cloudflare proxy (orange cloud) on. Check `docker compose logs caddy` |
| No desktop notification | The site must be on HTTPS (`https://yourdomain.com`) and you must click **Enable alert sound** once |
| Alert cards have no Gemma text | `/api/health` shows why; Gemma may still be downloading. The template summary is the fallback |
