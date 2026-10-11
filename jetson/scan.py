"""Field-unit main loop on the Jetson.

Listens to the ESP32 sentry over MQTT (broker on this Jetson), forwards its heartbeats uplink,
and when told to scan runs the Pyronear smoke model until things stay quiet.

    FIRELINE_URL=https://<your-site> UNIT_ID=gw-03 UNIT_LAT=28.6024 UNIT_LON=-81.2001 python scan.py
"""
import json
import logging
import os
import threading
import time

import cv2
import paho.mqtt.client as mqtt
from ultralytics import YOLO

from fireline_unit.packet import PacketBuilder
from fireline_unit.scoring import KEEP_AWAKE_ABOVE, Detection, SmokeWindow
from fireline_unit.uplink import Uplink

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("fireline.scan")

DEMO = os.getenv("DEMO_MODE", "1") == "1"
UNIT_ID = os.getenv("UNIT_ID", "gw-03")
SERVER = os.getenv("FIRELINE_URL", "http://localhost:8000")
MODEL = os.getenv("MODEL", "best.engine")  # TensorRT export of pyronear/yolov8s; a .pt or .onnx also loads
CAMERA = int(os.getenv("CAMERA", "0"))
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
CONF = float(os.getenv("CONF", "0.25"))
FRAME_EVERY_S = 2.0 if DEMO else 2.5
QUIET_S = 30 if DEMO else 300
EVENT_EVERY_S = 10 if DEMO else 30  # while smoke persists, keep updating the open incident

state = {
    "st": "sleep", "risk": "low", "temp": 0.0, "rh": 0.0, "bat": 100.0, "up": 0,
    "lat": float(os.getenv("UNIT_LAT", "29.18")), "lon": float(os.getenv("UNIT_LON", "-81.78")),
    "loc": os.getenv("UNIT_LOC"), "relocated": True,  # report location on the first heartbeat
}
scan_now = threading.Event()
builder = PacketBuilder(UNIT_ID)
uplink = Uplink(SERVER)
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"jetson-{UNIT_ID}")


def set_state(st: str) -> None:
    state["st"] = st
    client.publish("unit/state", st, retain=True)  # ESP32 drives the LED from this


def on_message(_c, _u, msg) -> None:
    try:
        data = json.loads(msg.payload or b"{}")
    except ValueError:
        log.warning("bad MQTT payload on %s", msg.topic)
        return
    for k in ("risk", "temp", "rh", "bat", "up"):
        if k in data:
            state[k] = data[k]

    if msg.topic == "unit/hb":
        loc = state["relocated"]
        uplink.send(builder.heartbeat(state["st"], state["risk"], state["temp"], state["rh"], state["bat"],
                                      state["up"], state["lat"] if loc else None, state["lon"] if loc else None,
                                      state["loc"] if loc else None))
        state["relocated"] = False
    elif msg.topic == "unit/scan":
        scan_now.set()
    elif msg.topic == "unit/tamper":
        uplink.send(builder.tamper(state["risk"], state["bat"]))
    elif msg.topic == "unit/loc":  # NFC tag tapped: new mounting spot
        state.update(lat=data["lat"], lon=data["lon"], loc=data.get("loc"), relocated=True)
        log.info("relocated to %s (%s, %s)", state["loc"], state["lat"], state["lon"])


def detect(model: YOLO, frame) -> Detection | None:
    r = model.predict(frame, conf=CONF, verbose=False)[0]
    if r.boxes is None or len(r.boxes) == 0:
        return None
    i = int(r.boxes.conf.argmax())
    x1, y1, x2, y2 = (int(v) for v in r.boxes.xyxy[i].tolist())
    return Detection(conf=float(r.boxes.conf[i]), box=(x1, y1, x2 - x1, y2 - y1))


def crop_jpeg(frame, box: tuple[int, int, int, int], width: int = 160) -> bytes:
    x, y, w, h = box
    pad = max(w, h) // 2
    H, W = frame.shape[:2]
    crop = frame[max(0, y - pad):min(H, y + h + pad), max(0, x - pad):min(W, x + w + pad)]
    scale = width / max(1, crop.shape[1])
    crop = cv2.resize(crop, (width, max(1, int(crop.shape[0] * scale))))
    ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 60])
    return buf.tobytes() if ok else b""


def scan_session(model: YOLO, cam: cv2.VideoCapture) -> None:
    set_state("scan")
    window = SmokeWindow()
    quiet_since = time.time()
    last_event = 0.0
    while True:
        cam.grab()  # drop the buffered frame so we analyse "now"
        ok, frame = cam.read()
        if not ok:
            log.error("camera read failed")
            time.sleep(1)
            continue
        window.push(detect(model, frame))
        interest = window.interest(state["risk"])
        log.info("frames %d/6 interest %.2f", len(window.hits), interest)

        now = time.time()
        if window.confirmed(state["risk"]) and now - last_event >= EVENT_EVERY_S:
            best = window.best()
            uplink.snapshot(UNIT_ID, crop_jpeg(frame, best.box))  # first, so it is there when the event lands
            uplink.send(builder.smoke_event(window.avg_conf(), interest, len(window.hits), state["risk"],
                                            state["temp"], state["rh"], list(best.box),
                                            state["lat"], state["lon"], state["bat"]))
            set_state("alert")
            last_event = now
        if interest > KEEP_AWAKE_ABOVE:
            quiet_since = now
        elif now - quiet_since > QUIET_S:
            break
        time.sleep(FRAME_EVERY_S)
    set_state("sleep")
    client.publish("unit/idle", "1")


def main() -> None:
    client.on_message = on_message
    client.connect(MQTT_HOST, 1883)
    client.subscribe([("unit/hb", 0), ("unit/scan", 0), ("unit/tamper", 0), ("unit/loc", 0)])
    client.loop_start()

    log.info("loading %s", MODEL)
    model = YOLO(MODEL, task="detect")  # loaded once and kept warm; the Jetson idles between scans
    cam = cv2.VideoCapture(CAMERA)
    if not cam.isOpened():
        # Exit so the systemd service restarts us once the camera shows up.
        log.error("camera %s did not open", CAMERA)
        raise SystemExit(1)
    cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    set_state("sleep")
    log.info("unit %s ready, uplink %s, demo=%s", UNIT_ID, SERVER, DEMO)

    while True:
        scan_now.wait()
        scan_now.clear()
        scan_session(model, cam)


if __name__ == "__main__":
    main()
