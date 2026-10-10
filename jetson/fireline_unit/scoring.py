"""Confirm smoke over time and compute the interest score.

interest = c_bar * (n_smoke / 6) * w_risk
"""
from collections import deque
from dataclasses import dataclass

WINDOW = 6
MIN_FRAMES = 4
ALERT_AT = 0.5
KEEP_AWAKE_ABOVE = 0.2
RISK_WEIGHT = {"low": 0.6, "elev": 0.8, "crit": 1.0}


@dataclass
class Detection:
    conf: float
    box: tuple[int, int, int, int]  # x, y, w, h in pixels


class SmokeWindow:
    def __init__(self) -> None:
        self.frames: deque[Detection | None] = deque(maxlen=WINDOW)

    def push(self, det: Detection | None) -> None:
        self.frames.append(det)

    @property
    def hits(self) -> list[Detection]:
        return [d for d in self.frames if d is not None]

    def interest(self, risk: str) -> float:
        hits = self.hits
        if not hits:
            return 0.0
        c_bar = sum(d.conf for d in hits) / len(hits)
        return c_bar * (len(hits) / WINDOW) * RISK_WEIGHT.get(risk, 0.6)

    def confirmed(self, risk: str) -> bool:
        return len(self.hits) >= MIN_FRAMES and self.interest(risk) >= ALERT_AT

    def growing(self) -> bool:
        """A box that grows across frames adds confidence (smoke spreads; glare does not)."""
        hits = self.hits
        return len(hits) >= 2 and hits[-1].box[2] * hits[-1].box[3] > hits[0].box[2] * hits[0].box[3]

    def best(self) -> Detection | None:
        hits = self.hits
        return max(hits, key=lambda d: d.conf) if hits else None

    def avg_conf(self) -> float:
        hits = self.hits
        return sum(d.conf for d in hits) / len(hits) if hits else 0.0
