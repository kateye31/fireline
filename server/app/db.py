"""SQLite storage. One connection guarded by a lock is plenty for a hackathon fleet."""
import sqlite3
import threading
from typing import Any

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS units (
    id TEXT PRIMARY KEY,
    name TEXT,
    lat REAL,
    lon REAL,
    loc TEXT,
    sim INTEGER NOT NULL DEFAULT 0,
    online INTEGER NOT NULL DEFAULT 1,
    last_seen REAL,
    last_t INTEGER,
    st TEXT,
    risk TEXT,
    temp REAL,
    rh REAL,
    bat REAL,
    up INTEGER,
    created_at REAL
);

CREATE TABLE IF NOT EXISTS heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id TEXT NOT NULL,
    seq INTEGER,
    t INTEGER,
    received_at REAL,
    st TEXT,
    risk TEXT,
    temp REAL,
    rh REAL,
    bat REAL
);
CREATE INDEX IF NOT EXISTS ix_hb_unit ON heartbeats(unit_id, t);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id TEXT NOT NULL,
    seq INTEGER,
    t INTEGER,
    received_at REAL,
    typ TEXT,
    cls TEXT,
    conf REAL,
    interest REAL,
    fr INTEGER,
    risk TEXT,
    temp REAL,
    rh REAL,
    box TEXT,
    lat REAL,
    lon REAL,
    bytes INTEGER,
    delay REAL,
    incident_id INTEGER
);
CREATE INDEX IF NOT EXISTS ix_evt_unit ON events(unit_id, t);

CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    opened_at REAL,
    updated_at REAL,
    last_event_at REAL,
    event_count INTEGER NOT NULL DEFAULT 1,
    peak_interest REAL,
    conf REAL,
    fr INTEGER,
    risk TEXT,
    temp REAL,
    rh REAL,
    lat REAL,
    lon REAL,
    snapshot_id INTEGER,
    summary TEXT,
    ai_summary TEXT,
    ai_model TEXT
);

-- Every uplink attempt, delivered or not: the link log in the unit page.
CREATE TABLE IF NOT EXISTS packets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id TEXT,
    seq INTEGER,
    t INTEGER,
    typ TEXT,
    bytes INTEGER,
    accepted_at REAL,
    delivered_at REAL,
    delay REAL,
    status TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS ix_pkt_unit ON packets(unit_id, seq, t);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id TEXT NOT NULL,
    received_at REAL,
    content_type TEXT,
    data BLOB
);
CREATE INDEX IF NOT EXISTS ix_snap_unit ON snapshots(unit_id, received_at);
"""


class Database:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(SCHEMA)

    def execute(self, sql: str, params: tuple | dict = ()) -> int:
        """Run a write and return lastrowid."""
        with self._lock:
            return self._conn.execute(sql, params).lastrowid

    def all(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row else None


db = Database(config.DB_PATH)
