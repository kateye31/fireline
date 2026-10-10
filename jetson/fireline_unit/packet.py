"""Builds the uplink packets. This is the contract in docs/protocol.md; the server validates the same shape."""
import json
import time

MAX_BYTES = 340  # Iridium short-burst-data sized; the satellite link rejects anything larger.


class PacketTooBig(ValueError):
    pass


class PacketBuilder:
    def __init__(self, unit_id: str, start_seq: int = 0):
        self.unit_id = unit_id
        self.seq = start_seq

    def _base(self, typ: str) -> dict:
        self.seq += 1
        return {"v": 1, "id": self.unit_id, "seq": self.seq, "t": int(time.time()), "typ": typ}

    def heartbeat(self, st: str, risk: str, temp: float, rh: float, bat: float, up: int,
                  lat: float | None = None, lon: float | None = None, loc: str | None = None) -> bytes:
        """lat/lon/loc only on the first heartbeat after an NFC relocation."""
        d = self._base("hb")
        d.update(st=st, risk=risk, temp=round(temp, 1), rh=round(rh), bat=round(bat), up=up)
        if lat is not None and lon is not None:
            d.update(lat=round(lat, 4), lon=round(lon, 4))
        if loc:
            d["loc"] = loc
        return encode(d)

    def smoke_event(self, conf: float, interest: float, frames: int, risk: str, temp: float, rh: float,
                    box: list[int], lat: float, lon: float, bat: float) -> bytes:
        d = self._base("evt")
        d.update(cls="smoke", conf=round(conf, 2), int=round(interest, 2), fr=frames, risk=risk,
                 temp=round(temp, 1), rh=round(rh), box=[int(v) for v in box],
                 lat=round(lat, 4), lon=round(lon, 4), bat=round(bat))
        return encode(d)

    def tamper(self, risk: str, bat: float) -> bytes:
        d = self._base("tmp")
        d.update(risk=risk, bat=round(bat))
        return encode(d)


def encode(d: dict) -> bytes:
    raw = json.dumps(d, separators=(",", ":")).encode()
    if len(raw) > MAX_BYTES:
        raise PacketTooBig(f"{len(raw)} B > {MAX_BYTES} B: {raw[:80]!r}...")
    return raw
