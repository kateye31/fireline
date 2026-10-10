"""Fireline web server: ground station API, simulated satellite link, live WebSocket, and the built web app."""
import asyncio
import json
import logging
import random
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from . import config, gemma, ground
from .db import db
from .live import hub
from .models import Packet

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

MAX_SNAPSHOT_BYTES = 256 * 1024

# Runtime-adjustable from the Settings page; starts from env config.
link = {
    "max_bytes": config.SAT_MAX_BYTES,
    "delay_min": config.SAT_DELAY_MIN,
    "delay_max": config.SAT_DELAY_MAX,
    "drop_rate": config.SAT_DROP_RATE,
    "demo_mode": config.DEMO_MODE,
}
if config.DEMO_MODE:
    link.update(delay_min=1.0, delay_max=4.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    watcher = asyncio.create_task(ground.offline_watch())
    yield
    watcher.cancel()


app = FastAPI(title="Fireline", lifespan=lifespan)


# ---------- simulated satellite uplink ----------

def _log_packet(unit_id, seq, t, typ, nbytes, status, error=None) -> int:
    return db.execute(
        "INSERT INTO packets (unit_id, seq, t, typ, bytes, accepted_at, status, error) VALUES (?,?,?,?,?,?,?,?)",
        (unit_id, seq, t, typ, nbytes, time.time(), status, error),
    )


@app.post("/api/uplink")
async def uplink(request: Request):
    """Stands in for the satellite network: size cap, random delay, optional drops."""
    raw = await request.body()
    n = len(raw)
    try:
        peek = json.loads(raw)
        peek = peek if isinstance(peek, dict) else {}
    except ValueError:
        peek = {}
    uid, seq, t, typ = peek.get("id"), peek.get("seq"), peek.get("t"), peek.get("typ")

    if n > link["max_bytes"]:
        err = f"packet is {n} B, satellite limit is {link['max_bytes']} B"
        pid = _log_packet(uid, seq, t, typ, n, "rejected", err)
        await hub.broadcast("packet", ground.get_packet(pid))
        return JSONResponse({"ok": False, "error": err}, status_code=413)

    try:
        pkt = Packet.model_validate_json(raw)
    except ValidationError as e:
        err = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
        pid = _log_packet(uid, seq, t, typ, n, "invalid", err)
        await hub.broadcast("packet", ground.get_packet(pid))
        return JSONResponse({"ok": False, "error": err}, status_code=422)

    if random.random() < link["drop_rate"]:
        pid = _log_packet(pkt.id, pkt.seq, pkt.t, pkt.typ, n, "dropped", "simulated link drop")
        await hub.broadcast("packet", ground.get_packet(pid))
        return JSONResponse({"ok": False, "error": "satellite link dropped the message; retry"}, status_code=503)

    pid = _log_packet(pkt.id, pkt.seq, pkt.t, pkt.typ, n, "in_flight")
    accepted_at = time.time()
    delay = random.uniform(link["delay_min"], max(link["delay_min"], link["delay_max"]))
    await hub.broadcast("packet", ground.get_packet(pid))

    async def later():
        await asyncio.sleep(delay)
        await ground.deliver(pkt, pid, accepted_at, n)

    ground.spawn(later())
    return JSONResponse({"ok": True, "packet": pid, "bytes": n, "delay_s": round(delay, 1)}, status_code=202)


# ---------- snapshots (side channel, not satellite) ----------

@app.post("/api/units/{uid}/snapshot")
async def upload_snapshot(uid: str, request: Request):
    """Small smoke crop pushed by the Jetson over a faster link when one exists. Too big for satellite."""
    data = await request.body()
    if not data:
        raise HTTPException(400, "empty body")
    if len(data) > MAX_SNAPSHOT_BYTES:
        raise HTTPException(413, f"snapshot over {MAX_SNAPSHOT_BYTES} B")
    ctype = request.headers.get("content-type", "image/jpeg").split(";")[0]
    sid = db.execute(
        "INSERT INTO snapshots (unit_id, received_at, content_type, data) VALUES (?,?,?,?)",
        (uid, time.time(), ctype, data),
    )
    await ground.attach_snapshot(uid, sid)
    return {"ok": True, "snapshot": sid}


@app.get("/api/snapshots/{sid}")
def get_snapshot(sid: int):
    s = db.one("SELECT data, content_type FROM snapshots WHERE id=?", (sid,))
    if not s:
        raise HTTPException(404)
    return Response(s["data"], media_type=s["content_type"] or "image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400"})


# ---------- read API ----------

@app.get("/api/health")
async def health():
    return {"ok": True, "gemma": await gemma.health(), "link": link}


@app.get("/api/units")
def list_units():
    return [ground.unit_view(u) for u in db.all(f"{ground.UNIT_SELECT} ORDER BY id")]


@app.get("/api/units/{uid}")
def unit_detail(uid: str, hours: float = 6):
    unit = ground.get_unit(uid)
    if not unit:
        raise HTTPException(404, "unknown unit")
    since = time.time() - hours * 3600
    return {
        "unit": unit,
        "heartbeats": db.all(
            "SELECT t, received_at, st, risk, temp, rh, bat FROM heartbeats WHERE unit_id=? AND received_at>=? "
            "ORDER BY t", (uid, since)),
        "events": [ground.event_view(e) for e in db.all(
            "SELECT * FROM events WHERE unit_id=? ORDER BY id DESC LIMIT 100", (uid,))],
        "packets": db.all("SELECT * FROM packets WHERE unit_id=? ORDER BY id DESC LIMIT 100", (uid,)),
    }


@app.get("/api/events")
def list_events(limit: int = 100):
    return [ground.event_view(e) for e in db.all("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))]


@app.get("/api/incidents")
def list_incidents(status: str | None = None, limit: int = 100):
    if status:
        return db.all("SELECT * FROM incidents WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit))
    return db.all("SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,))


@app.get("/api/packets")
def list_packets(limit: int = 100):
    return db.all("SELECT * FROM packets ORDER BY id DESC LIMIT ?", (limit,))


# ---------- operator actions ----------

async def _set_incident_status(iid: int, status: str):
    if not ground.get_incident(iid):
        raise HTTPException(404)
    db.execute("UPDATE incidents SET status=?, updated_at=? WHERE id=?", (status, time.time(), iid))
    inc = ground.get_incident(iid)
    if status == "resolved":
        # Drop the event-driven alert flag; the unit's next heartbeat reports its real state.
        db.execute("UPDATE units SET st='scan' WHERE id=? AND st='alert'", (inc["unit_id"],))
    await hub.broadcast("incident", inc)
    await hub.broadcast("unit", ground.get_unit(inc["unit_id"]))
    return inc


@app.post("/api/incidents/{iid}/ack")
async def ack_incident(iid: int):
    return await _set_incident_status(iid, "acknowledged")


@app.post("/api/incidents/{iid}/resolve")
async def resolve_incident(iid: int):
    return await _set_incident_status(iid, "resolved")


@app.post("/api/incidents/{iid}/summarize")
async def resummarize(iid: int):
    if not ground.get_incident(iid):
        raise HTTPException(404)
    if not gemma.enabled():
        raise HTTPException(503, "Gemma is not configured (set GEMMA_BASE_URL)")
    await ground.ai_summary(iid)
    return ground.get_incident(iid)


class NewUnit(BaseModel):
    id: str
    name: str | None = None
    lat: float
    lon: float


@app.post("/api/units")
async def add_unit(u: NewUnit):
    if db.one("SELECT id FROM units WHERE id=?", (u.id,)):
        raise HTTPException(409, "unit already exists")
    # Starts offline until its first heartbeat lands.
    db.execute(
        "INSERT INTO units (id, name, lat, lon, online, created_at) VALUES (?,?,?,?,0,?)",
        (u.id, u.name or u.id, u.lat, u.lon, time.time()),
    )
    unit = ground.get_unit(u.id)
    await hub.broadcast("unit", unit)
    return unit


@app.delete("/api/units/{uid}")
async def delete_unit(uid: str):
    db.execute("DELETE FROM units WHERE id=?", (uid,))
    await hub.broadcast("unit_removed", {"id": uid})
    return {"ok": True}


class DemoReset(BaseModel):
    # Optionally put the real unit back on its first tree.
    unit: str | None = None
    lat: float | None = None
    lon: float | None = None
    loc: str | None = None


@app.post("/api/demo/reset")
async def reset_demo(r: DemoReset | None = None):
    """Clean slate before a rehearsal or judging slot: no incidents, events, snapshots or link log.
    Units and their weather history stay so the map and charts are full from the first second."""
    for table in ("incidents", "events", "snapshots", "packets"):
        db.execute(f"DELETE FROM {table}")
    db.execute("UPDATE units SET st='sleep' WHERE st='alert'")
    if r and r.unit and r.lat is not None and r.lon is not None:
        db.execute("UPDATE units SET lat=?, lon=?, loc=COALESCE(?, loc) WHERE id=?", (r.lat, r.lon, r.loc, r.unit))
    await hub.broadcast("reset", {})
    return {"ok": True}


class LinkSettings(BaseModel):
    max_bytes: int | None = None
    delay_min: float | None = None
    delay_max: float | None = None
    drop_rate: float | None = None
    demo_mode: bool | None = None


@app.get("/api/settings")
def get_settings():
    return {**link, "offline_after_s": config.OFFLINE_AFTER_S, "incident_threshold": config.INCIDENT_THRESHOLD,
            "gemma_model": config.GEMMA_MODEL if gemma.enabled() else None}


@app.put("/api/settings")
async def put_settings(s: LinkSettings):
    for k, v in s.model_dump(exclude_none=True).items():
        link[k] = v
    if s.demo_mode is True and s.delay_max is None:
        link.update(delay_min=1.0, delay_max=4.0)
    elif s.demo_mode is False and s.delay_max is None:
        link.update(delay_min=config.SAT_DELAY_MIN, delay_max=config.SAT_DELAY_MAX)
    await hub.broadcast("settings", get_settings())
    return get_settings()


# ---------- live ----------

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # clients only listen; this keeps the socket open
    except WebSocketDisconnect:
        hub.disconnect(websocket)


# ---------- web app ----------

if config.WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = config.WEB_DIST / path
        if path and f.is_file() and config.WEB_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(config.WEB_DIST / "index.html")
