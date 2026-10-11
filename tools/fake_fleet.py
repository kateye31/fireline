"""Simulated Fireline fleet and hand-fired test packets. Standard library only.

    python tools/fake_fleet.py fleet                      # 8 simulated units in Ocala National Forest
    python tools/fake_fleet.py fleet --interval 10        # faster heartbeats for the demo
    python tools/fake_fleet.py event --unit gw-14         # one smoke event (opens an incident)
    python tools/fake_fleet.py event --unit gw-03 --snapshot smoke.jpg --real
    python tools/fake_fleet.py reset                      # before every rehearsal and judging slot
    python tools/fake_fleet.py reset --lat 29.21 --lon -81.80 --loc tree-01   # and put gw-01 back

Every simulated packet carries "sim":1 so the web app labels those units as simulated.
"""
import argparse
import json
import math
import random
import time
import urllib.error
import urllib.request

# Ocala National Forest, roughly the middle of the forest.
CENTER = (29.18, -81.78)
NAMES = ["Juniper Prairie", "Salt Springs", "Lake George", "Alexander Springs", "Farles Prairie",
         "Hopkins Prairie", "Lake Delancy", "Silver Glen", "Big Scrub", "Clearwater Lake"]


def post(base: str, path: str, body: bytes, ctype: str = "application/json") -> tuple[int, str]:
    req = urllib.request.Request(base.rstrip("/") + path, data=body, method="POST", headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except (urllib.error.URLError, OSError) as e:  # server down or restarting; keep going
        return 0, str(e)


def pack(d: dict) -> bytes:
    return json.dumps({k: v for k, v in d.items() if v is not None}, separators=(",", ":")).encode()


def tier(temp: float, rh: float) -> str:
    # Same starting thresholds as the ESP32 firmware (see docs/protocol.md).
    if rh < 30 and temp > 32:
        return "crit"
    if rh <= 50 or temp > 30:
        return "elev"
    return "low"


class SimUnit:
    def __init__(self, idx: int, rng: random.Random):
        self.id = f"gw-{11 + idx:02d}"
        self.loc = NAMES[idx % len(NAMES)]
        self.lat = round(CENTER[0] + rng.uniform(-0.13, 0.13), 4)
        self.lon = round(CENTER[1] + rng.uniform(-0.09, 0.09), 4)
        self.seq = 0
        self.up = rng.randint(1000, 90000)
        self.bat = rng.uniform(55, 98)
        self.dry = rng.uniform(-12, 12)  # some spots are drier than others
        self.rng = rng

    def heartbeat(self, now: float) -> dict:
        self.seq += 1
        # Slow day/night swing plus noise: hot and dry in the afternoon.
        phase = math.sin(now / 900 + self.dry)
        temp = 27 + 5 * phase + self.rng.uniform(-0.6, 0.6)
        rh = 52 - 16 * phase - self.dry + self.rng.uniform(-2, 2)
        rh = max(8, min(95, rh))
        risk = tier(temp, rh)
        st = "scan" if risk != "low" else "sleep"
        self.bat = max(5, self.bat - self.rng.uniform(0, 0.05))
        first = self.seq == 1 or self.seq % 5 == 0
        return {
            "v": 1, "id": self.id, "seq": self.seq, "t": int(now), "typ": "hb", "st": st, "risk": risk,
            "temp": round(temp, 1), "rh": round(rh), "bat": round(self.bat), "up": self.up + self.seq * 60,
            "lat": self.lat if first else None, "lon": self.lon if first else None,
            "loc": self.loc if self.seq == 1 else None, "sim": 1,
        }


def run_fleet(args) -> None:
    rng = random.Random(args.seed)
    units = [SimUnit(i, rng) for i in range(args.units)]
    print(f"Posting heartbeats for {len(units)} simulated units to {args.url} every {args.interval}s. Ctrl+C to stop.")
    while True:
        now = time.time()
        for u in units:
            body = pack(u.heartbeat(now))
            code, resp = post(args.url, "/api/uplink", body)
            print(f"{u.id} hb {len(body):>3} B -> {code} {resp[:80]}")
        time.sleep(args.interval)


def run_event(args) -> None:
    seq = int(time.time()) % 1_000_000  # unique enough for hand-fired packets
    if args.snapshot:
        with open(args.snapshot, "rb") as f:
            code, resp = post(args.url, f"/api/units/{args.unit}/snapshot", f.read(), "image/jpeg")
        print(f"snapshot -> {code} {resp}")
    pkt = {
        "v": 1, "id": args.unit, "seq": seq, "t": int(time.time()), "typ": "evt", "cls": "smoke",
        "conf": args.conf, "int": args.interest, "fr": args.frames, "risk": args.risk,
        "temp": args.temp, "rh": args.rh, "box": [412, 180, 96, 140],
        "lat": args.lat, "lon": args.lon, "bat": 71, "sim": None if args.real else 1,
    }
    body = pack(pkt)
    code, resp = post(args.url, "/api/uplink", body)
    print(f"{args.unit} evt {len(body)} B -> {code} {resp}")


def run_reset(args) -> None:
    # Clears incidents, events, snapshots and the link log; units and weather history stay.
    body = {"unit": args.unit, "lat": args.lat, "lon": args.lon, "loc": args.loc}
    code, resp = post(args.url, "/api/demo/reset", pack(body))
    print(f"reset -> {code} {resp}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="https://fire-line.tech", help="Fireline server base URL")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fleet", help="post heartbeats for simulated units forever")
    f.add_argument("--units", type=int, default=8)
    f.add_argument("--interval", type=float, default=60)
    f.add_argument("--seed", type=int, default=7, help="same seed, same unit positions")
    f.set_defaults(func=run_fleet)

    e = sub.add_parser("event", help="send one smoke event")
    e.add_argument("--unit", default="gw-14")
    e.add_argument("--conf", type=float, default=0.87)
    e.add_argument("--interest", type=float, default=0.82)
    e.add_argument("--frames", type=int, default=5)
    e.add_argument("--risk", default="crit", choices=["low", "elev", "crit"])
    e.add_argument("--temp", type=float, default=34.1)
    e.add_argument("--rh", type=float, default=22)
    e.add_argument("--lat", type=float, default=None)
    e.add_argument("--lon", type=float, default=None)
    e.add_argument("--snapshot", help="path to a JPEG crop to upload first")
    e.add_argument("--real", action="store_true", help="do not mark the unit as simulated")
    e.set_defaults(func=run_event)

    r = sub.add_parser("reset", help="clean slate before a rehearsal or judging slot")
    r.add_argument("--unit", default="gw-01", help="real unit to put back on its first tree")
    r.add_argument("--lat", type=float, default=None)
    r.add_argument("--lon", type=float, default=None)
    r.add_argument("--loc", default=None, help="tree name, e.g. tree-01")
    r.set_defaults(func=run_reset)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
