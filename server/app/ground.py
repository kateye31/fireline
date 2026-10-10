"""Ground-station logic: what happens when a packet comes down from the satellite."""
import asyncio
import json
import logging
import math
import time

from . import config, gemma
from .db import db
from .live import hub
from .models import Packet

log = logging.getLogger("fireline.ground")

RISK_WORDS = {"low": "low fire weather", "elev": "elevated fire weather", "crit": "critical fire weather"}

# Strong references so fire-and-forget tasks are not garbage collected mid-flight.
_tasks: set[asyncio.Task] = set()


def spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


# ---------- views ----------

# A unit stays red while any incident on it is open, whatever its latest heartbeat says.
UNIT_SELECT = (
    "SELECT units.*, (SELECT COUNT(*) FROM incidents i WHERE i.unit_id=units.id AND i.status!='resolved') "
    "AS open_incidents FROM units"
)

def unit_status(u: dict) -> str:
    """Map colour key: offline > alert > crit > scan > sleep."""
    if not u.get("online"):
        return "offline"
    if u.get("open_incidents") or u.get("st") == "alert":
        return "alert"
    if u.get("risk") == "crit":
        return "critical"
    if u.get("st") == "scan":
        return "scan"
    return "sleep"


def unit_view(u: dict | None) -> dict | None:
    if u is None:
        return None
    return {**u, "status": unit_status(u)}


def get_unit(uid: str) -> dict | None:
    return unit_view(db.one(f"{UNIT_SELECT} WHERE id=?", (uid,)))


def event_view(e: dict) -> dict:
    return {**e, "box": json.loads(e["box"]) if e.get("box") else None}


def get_incident(iid: int) -> dict | None:
    return db.one("SELECT * FROM incidents WHERE id=?", (iid,))


def get_packet(pid: int) -> dict | None:
    return db.one("SELECT * FROM packets WHERE id=?", (pid,))


# ---------- helpers ----------

def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def nearest_unit(uid: str, lat: float | None, lon: float | None) -> str | None:
    if lat is None or lon is None:
        return None
    others = db.all("SELECT id, lat, lon FROM units WHERE id!=? AND lat IS NOT NULL AND lon IS NOT NULL", (uid,))
    if not others:
        return None
    best = min(others, key=lambda o: _km(lat, lon, o["lat"], o["lon"]))
    return f"{best['id']} ({_km(lat, lon, best['lat'], best['lon']):.1f} km)"


def template_summary(inc: dict, nearest: str | None) -> str:
    weather = RISK_WORDS.get(inc.get("risk") or "", "unknown fire weather")
    reading = []
    if inc.get("temp") is not None:
        reading.append(f"{inc['temp']:.0f} °C")
    if inc.get("rh") is not None:
        reading.append(f"{inc['rh']:.0f} % humidity")
    weather_txt = f"{weather} ({', '.join(reading)})" if reading else weather
    verdict = "Likely early wildfire." if (inc.get("peak_interest") or 0) >= 0.75 else "Possible smoke; verify."
    text = f"Smoke seen by {inc['unit_id']} in {inc.get('fr') or '?'} of 6 frames during {weather_txt}. {verdict}"
    if inc.get("event_count", 1) > 1:
        text += f" {inc['event_count']} detections so far."
    if nearest:
        text += f" Nearest other unit: {nearest}."
    return text


def latest_snapshot_id(uid: str) -> int | None:
    row = db.one(
        "SELECT id FROM snapshots WHERE unit_id=? AND received_at>=? ORDER BY id DESC LIMIT 1",
        (uid, time.time() - config.SNAPSHOT_MAX_AGE_S),
    )
    return row["id"] if row else None


# ---------- ingest ----------

async def deliver(pkt: Packet, packet_id: int, accepted_at: float, nbytes: int) -> None:
    """Called once the simulated satellite delay has elapsed."""
    now = time.time()
    delay = round(now - accepted_at, 2)

    # A resend repeats both seq and t; a rebooted unit restarts seq but not t, so it is not a duplicate.
    dup = db.one(
        "SELECT id FROM packets WHERE unit_id=? AND seq=? AND t=? AND status='delivered' AND id!=?",
        (pkt.id, pkt.seq, pkt.t, packet_id),
    )
    status = "duplicate" if dup else "delivered"
    db.execute("UPDATE packets SET status=?, delivered_at=?, delay=? WHERE id=?", (status, now, delay, packet_id))
    await hub.broadcast("packet", get_packet(packet_id))
    if dup:
        return

    _upsert_unit(pkt, now)

    if pkt.typ == "hb":
        db.execute(
            "INSERT INTO heartbeats (unit_id, seq, t, received_at, st, risk, temp, rh, bat) VALUES (?,?,?,?,?,?,?,?,?)",
            (pkt.id, pkt.seq, pkt.t, now, pkt.st, pkt.risk, pkt.temp, pkt.rh, pkt.bat),
        )
        await hub.broadcast("heartbeat", {"unit_id": pkt.id, "t": pkt.t, "temp": pkt.temp, "rh": pkt.rh,
                                          "risk": pkt.risk, "st": pkt.st, "bat": pkt.bat})
    else:
        cls = pkt.cls or ("tamper" if pkt.typ == "tmp" else None)
        eid = db.execute(
            """INSERT INTO events (unit_id, seq, t, received_at, typ, cls, conf, interest, fr, risk, temp, rh,
                                   box, lat, lon, bytes, delay)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pkt.id, pkt.seq, pkt.t, now, pkt.typ, cls, pkt.conf, pkt.int_, pkt.fr, pkt.risk, pkt.temp, pkt.rh,
             json.dumps(pkt.box) if pkt.box else None, pkt.lat, pkt.lon, nbytes, delay),
        )
        await _maybe_incident(pkt, eid, now)
        await hub.broadcast("event", event_view(db.one("SELECT * FROM events WHERE id=?", (eid,))))

    await hub.broadcast("unit", get_unit(pkt.id))


def _upsert_unit(pkt: Packet, now: float) -> None:
    existing = db.one("SELECT last_t FROM units WHERE id=?", (pkt.id,))
    if existing is None:
        db.execute(
            "INSERT INTO units (id, name, sim, online, created_at) VALUES (?,?,?,1,?)",
            (pkt.id, pkt.loc or pkt.id, pkt.sim or 0, now),
        )
        existing = {"last_t": None}

    db.execute("UPDATE units SET last_seen=?, online=1, sim=COALESCE(?, sim) WHERE id=?", (now, pkt.sim, pkt.id))

    # Packets can arrive out of order through the satellite delay; only the newest one sets state.
    if existing["last_t"] is not None and pkt.t < existing["last_t"]:
        return
    is_alert = pkt.typ == "evt" and (pkt.int_ or 0) >= config.INCIDENT_THRESHOLD
    db.execute(
        """UPDATE units SET last_t=?, st=COALESCE(?, st), risk=COALESCE(?, risk), temp=COALESCE(?, temp),
                  rh=COALESCE(?, rh), bat=COALESCE(?, bat), up=COALESCE(?, up) WHERE id=?""",
        (pkt.t, "alert" if is_alert else pkt.st, pkt.risk, pkt.temp, pkt.rh, pkt.bat, pkt.up, pkt.id),
    )
    if pkt.lat is not None and pkt.lon is not None:
        db.execute("UPDATE units SET lat=?, lon=?, loc=COALESCE(?, loc) WHERE id=?", (pkt.lat, pkt.lon, pkt.loc, pkt.id))


async def _maybe_incident(pkt: Packet, event_id: int, now: float) -> None:
    if pkt.typ != "evt" or (pkt.int_ or 0) < config.INCIDENT_THRESHOLD:
        return
    unit = db.one("SELECT lat, lon FROM units WHERE id=?", (pkt.id,)) or {}
    lat = pkt.lat if pkt.lat is not None else unit.get("lat")
    lon = pkt.lon if pkt.lon is not None else unit.get("lon")

    inc = db.one(
        "SELECT * FROM incidents WHERE unit_id=? AND status!='resolved' AND last_event_at>=? ORDER BY id DESC LIMIT 1",
        (pkt.id, now - config.INCIDENT_WINDOW_S),
    )
    is_new = inc is None
    if is_new:
        iid = db.execute(
            """INSERT INTO incidents (unit_id, status, opened_at, updated_at, last_event_at, event_count,
                                      peak_interest, conf, fr, risk, temp, rh, lat, lon)
               VALUES (?, 'new', ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pkt.id, now, now, now, pkt.int_, pkt.conf, pkt.fr, pkt.risk, pkt.temp, pkt.rh, lat, lon),
        )
    else:
        iid = inc["id"]
        db.execute(
            """UPDATE incidents SET updated_at=?, last_event_at=?, event_count=event_count+1,
                      peak_interest=MAX(COALESCE(peak_interest, 0), ?), conf=COALESCE(?, conf), fr=COALESCE(?, fr),
                      risk=COALESCE(?, risk), temp=COALESCE(?, temp), rh=COALESCE(?, rh),
                      lat=COALESCE(?, lat), lon=COALESCE(?, lon) WHERE id=?""",
            (now, now, pkt.int_, pkt.conf, pkt.fr, pkt.risk, pkt.temp, pkt.rh, lat, lon, iid),
        )

    db.execute("UPDATE events SET incident_id=? WHERE id=?", (iid, event_id))
    snap = latest_snapshot_id(pkt.id)
    if snap:
        db.execute("UPDATE incidents SET snapshot_id=COALESCE(snapshot_id, ?) WHERE id=?", (snap, iid))

    inc = get_incident(iid)
    db.execute("UPDATE incidents SET summary=? WHERE id=?", (template_summary(inc, nearest_unit(pkt.id, lat, lon)), iid))
    await hub.broadcast("incident", {**get_incident(iid), "is_new": is_new})
    if is_new:
        spawn(ai_summary(iid))


async def ai_summary(iid: int) -> None:
    inc = get_incident(iid)
    if inc is None or not gemma.enabled():
        return
    image = None
    if inc.get("snapshot_id"):
        s = db.one("SELECT data, content_type FROM snapshots WHERE id=?", (inc["snapshot_id"],))
        if s:
            image = (s["data"], s["content_type"] or "image/jpeg")
    text = await gemma.summarize(inc, nearest_unit(inc["unit_id"], inc.get("lat"), inc.get("lon")), image)
    if text:
        db.execute("UPDATE incidents SET ai_summary=?, ai_model=?, updated_at=? WHERE id=?",
                   (text, config.GEMMA_MODEL,time.time(), iid))
        await hub.broadcast("incident", get_incident(iid))


async def attach_snapshot(uid: str, snapshot_id: int) -> None:
    """A crop that arrives after its incident opened still gets shown on the alert card."""
    inc = db.one(
        "SELECT id FROM incidents WHERE unit_id=? AND status!='resolved' AND snapshot_id IS NULL "
        "AND last_event_at>=? ORDER BY id DESC LIMIT 1",
        (uid, time.time() - config.INCIDENT_WINDOW_S),
    )
    if inc:
        db.execute("UPDATE incidents SET snapshot_id=? WHERE id=?", (snapshot_id, inc["id"]))
        await hub.broadcast("incident", get_incident(inc["id"]))


async def offline_watch() -> None:
    """A unit that misses two heartbeats (120 s of silence) turns grey."""
    while True:
        await asyncio.sleep(5)
        cutoff = time.time() - config.OFFLINE_AFTER_S
        for row in db.all("SELECT id FROM units WHERE online=1 AND last_seen IS NOT NULL AND last_seen<?", (cutoff,)):
            db.execute("UPDATE units SET online=0 WHERE id=?", (row["id"],))
            await hub.broadcast("unit", get_unit(row["id"]))
