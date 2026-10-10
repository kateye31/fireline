"""The uplink packet contract. Keep in sync with docs/protocol.md and jetson/fireline_unit/packet.py."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Packet(BaseModel):
    v: int = 1
    id: str = Field(min_length=1, max_length=32)
    seq: int
    t: int
    typ: Literal["hb", "evt", "tmp"]
    st: Optional[Literal["sleep", "scan", "alert"]] = None
    risk: Optional[Literal["low", "elev", "crit"]] = None
    temp: Optional[float] = None
    rh: Optional[float] = None
    bat: Optional[float] = None
    up: Optional[int] = None
    # Event fields.
    cls: Optional[str] = None
    conf: Optional[float] = None
    int_: Optional[float] = Field(default=None, alias="int")
    fr: Optional[int] = None
    box: Optional[list[int]] = None
    # Location, sent on events and on the first heartbeat after an NFC relocation.
    lat: Optional[float] = None
    lon: Optional[float] = None
    loc: Optional[str] = None
    # 1 for units posted by tools/fake_fleet.py, so the UI can label them honestly.
    sim: Optional[int] = None

    model_config = {"populate_by_name": True}
