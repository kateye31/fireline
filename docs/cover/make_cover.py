"""Builds the Fireline cover (docs/cover/cover.svg + cover.html) and the standalone wordmark.

Everything is drawn here, nothing is traced: the FIRELINE letterforms are hand-set polygons, and every
edge is run through rough() so it reads as cut lino rather than vector-perfect. To export, open cover.html
in a browser at 1500x1000 and screenshot the SVG (it loads IBM Plex Mono and Newsreader from Google Fonts).

    python docs/cover/make_cover.py
"""
import math
import random
from pathlib import Path

HERE = Path(__file__).parent
W, H = 1500, 1000

PAPER = "#ece2c9"
PAPER_LT = "#f5eedd"
INK = "#1b241e"
EMBER = "#d9532b"
OCHRE = "#d99a3a"
SAGE = "#7f9478"
PINE_BACK = "#456049"
PINE_FRONT = "#22362a"
FIRE_X = 470


# ---------- geometry helpers ----------

def cubic(p0, p1, p2, p3, n=10):
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append((
            u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
            u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
        ))
    return out


def wobble(seed):
    """Smooth 1-D noise: a few sines with random phases, so edges drift instead of fizzing."""
    r = random.Random(seed)
    waves = [(r.uniform(0.02, 0.05), r.uniform(0, 6.3), 0.55),
             (r.uniform(0.09, 0.16), r.uniform(0, 6.3), 0.3),
             (r.uniform(0.3, 0.5), r.uniform(0, 6.3), 0.15)]
    return lambda s: sum(a * math.sin(s * f + p) for f, p, a in waves)


def rough(points, amp=1.2, step=5.0, seed=0, closed=True):
    """Subdivide each edge and push points along the normal. Corners move less, like a knife turning."""
    n = wobble(seed)
    r = random.Random(seed + 99)
    pts = list(points) + ([points[0]] if closed else [])
    out, s = [], 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0) or 1e-6
        nx, ny = -(y1 - y0) / L, (x1 - x0) / L
        k = max(1, int(L / step))
        for i in range(k):
            t = i / k
            a = amp * (0.35 if i == 0 else 1.0)
            off = n(s + t * L) * a + r.uniform(-0.25, 0.25) * a
            out.append((x0 + (x1 - x0) * t + nx * off, y0 + (y1 - y0) * t + ny * off))
        s += L
    if not closed:
        out.append(pts[-1])
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in out)
    return d + (" Z" if closed else "")


def place(points, k, ox, oy):
    return [(ox + x * k, oy + y * k) for x, y in points]


# ---------- the FIRELINE letterforms ----------
# Cap height 170, stem 36. Crossbars tilt up to the right, like heat rising; the E's middle arm is
# short and the R's leg kicks out past the bowl. Units: glyph-local, y down.

S = 36
GLYPHS = {
    "F": (104, [[(0, 0), (104, 0), (100, 32), (S, 32), (S, 72), (86, 68), (83, 100), (S, 104), (S, 170), (0, 170)]]),
    "I": (S, [[(0, 0), (S, 0), (S + 1, 170), (-1, 170)]]),
    "R": (120, [
        [(0, 0), (72, 0)] + cubic((72, 0), (102, 0), (118, 20), (118, 49))
        + cubic((118, 49), (118, 72), (106, 88), (86, 95)) + [(121, 170), (82, 170), (52, 100), (S, 100), (S, 170), (0, 170)],
        [(S, 32), (68, 32)] + cubic((68, 32), (78, 32), (82, 40), (82, 50))
        + cubic((82, 50), (82, 61), (77, 68), (66, 68)) + [(S, 68)],
    ]),
    "E": (102, [[(0, 0), (100, 0), (97, 32), (S, 32), (S, 68), (80, 64), (77, 96), (S, 100), (S, 138), (100, 136), (102, 170), (0, 170)]]),
    "L": (98, [[(0, 0), (S, 0), (S, 138), (96, 136), (98, 170), (0, 170)]]),
    "N": (128, [[(0, 0), (36, 0), (92, 108), (92, 0), (128, 0), (128, 170), (93, 170), (36, 62), (36, 170), (0, 170)]]),
}
TRACK = 14


def wordmark_paths(word, k, ox, oy, seed=1):
    x, paths = 0.0, []
    for i, ch in enumerate(word):
        w, shapes = GLYPHS[ch]
        d = " ".join(rough(place(s, k, ox + x * k, oy), amp=1.1, step=4, seed=seed + i * 7 + j) for j, s in enumerate(shapes))
        paths.append(d)
        x += w + TRACK
    return paths, (x - TRACK) * k


def wordmark_width(word):
    return sum(GLYPHS[c][0] for c in word) + TRACK * (len(word) - 1)


# ---------- linocut pieces ----------

def pine(cx, base, h, w, seed, carve=False, trunk=0.12):
    r = random.Random(seed)
    parts, gouges = [], []
    tw = max(4, w * 0.11)
    parts.append(rough([(cx - tw / 2, base - h * (trunk + 0.06)), (cx + tw / 2, base - h * (trunk + 0.06)),
                        (cx + tw / 2 + 1, base + 4), (cx - tw / 2 - 1, base + 4)], amp=0.8, seed=seed))
    tiers = r.choice([4, 5, 5, 6])
    crown = h * (1 - trunk)
    for i in range(tiers):
        top = base - h + i * crown / (tiers + 0.6)
        bot = top + crown / tiers * 1.7
        hw = w / 2 * (0.32 + 0.68 * (i + 1) / tiers) * r.uniform(0.9, 1.08)
        lean = r.uniform(-2, 2)
        pts = [(cx + lean, top), (cx + hw * 0.62, bot - 7), (cx + hw, bot + r.uniform(-2, 2)),
               (cx + hw * 0.3, bot - 3), (cx - hw * 0.3, bot - 3), (cx - hw, bot + r.uniform(-2, 2)), (cx - hw * 0.62, bot - 7)]
        parts.append(rough(pts, amp=1.6, step=4, seed=seed * 13 + i))
        if carve:  # two gouge strokes down the lit (left) side of each tier
            for g in range(2):
                f0, f1 = 0.25 + g * 0.22, 0.55 + g * 0.2
                x0, y0 = cx + lean - hw * 0.15 * f0 - 3 - g * 4, top + (bot - top) * f0
                x1, y1 = cx - hw * 0.62 * f1, top + (bot - top) * f1 - 3
                gouges.append(rough([(x0, y0), (x1, y1)], amp=0.4, step=3, seed=seed + g + i * 5, closed=False))
    return parts, gouges


def blob(cx, cy, rad, seed, n=26):
    pts = [(cx + rad * math.cos(2 * math.pi * i / n), cy + rad * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return rough(pts, amp=rad * 0.06 + 0.6, step=5, seed=seed)


def arrow(p0, p1, bend, seed, color=EMBER, width=2.2):
    """A quick pen arrow: one bowed stroke, then two flicks for the head."""
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    cx, cy = mx - dy / L * bend, my + dx / L * bend
    pts = []
    for i in range(0, 25):
        t = i / 24
        pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * cx + t * t * p1[0],
                    (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * cy + t * t * p1[1]))
    shaft = rough(pts, amp=0.7, step=6, seed=seed, closed=False)
    ang = math.atan2(p1[1] - cy, p1[0] - cx)
    heads = []
    for side, length in ((1, 13), (-1, 11)):
        a = ang + math.pi + side * 0.48
        heads.append(rough([p1, (p1[0] + length * math.cos(a), p1[1] + length * math.sin(a))], amp=0.4, step=4,
                           seed=seed + side + 3, closed=False))
    return "".join(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'
                   for d in [shaft] + heads)


def tape(cx, cy, w, h, ang, seed):
    r = random.Random(seed)
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2)]
    pts += [(w / 2 + r.uniform(-3, 3), -h / 2 + h * i / 6) for i in range(1, 6)]
    pts += [(w / 2, h / 2), (-w / 2, h / 2)]
    pts += [(-w / 2 + r.uniform(-3, 3), h / 2 - h * i / 6) for i in range(1, 6)]
    d = rough(pts, amp=0.4, seed=seed)
    return f'<path d="{d}" transform="translate({cx},{cy}) rotate({ang})" fill="#d8c79c" fill-opacity=".72" stroke="#b9a676" stroke-opacity=".35"/>'


# Shared filters: paper stain + grain, the ink plate's bleed and speckle, and a pen wobble.
DEFS = """<defs>
  <filter id="paper" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency=".011 .016" numOctaves="3" seed="8" result="blotch"/>
    <feColorMatrix in="blotch" type="matrix" values="0 0 0 0 .45  0 0 0 0 .36  0 0 0 0 .22  1.1 0 0 0 -.52" result="stain"/>
    <feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" seed="2" result="fine"/>
    <feColorMatrix in="fine" type="matrix" values="0 0 0 0 .2  0 0 0 0 .17  0 0 0 0 .12  0 0 0 -1.4 .78" result="grain"/>
    <feMerge><feMergeNode in="SourceGraphic"/><feMergeNode in="stain"/><feMergeNode in="grain"/></feMerge>
  </filter>
  <filter id="print" x="-2%" y="-2%" width="104%" height="104%">
    <feTurbulence type="fractalNoise" baseFrequency=".035" numOctaves="2" seed="4" result="warp"/>
    <feDisplacementMap in="SourceGraphic" in2="warp" scale="2.2" xChannelSelector="R" yChannelSelector="G" result="bled"/>
    <feTurbulence type="fractalNoise" baseFrequency=".5" numOctaves="2" seed="11" result="speck"/>
    <feColorMatrix in="speck" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  -11 0 0 0 8.6" result="holes"/>
    <feComposite in="bled" in2="holes" operator="in"/>
  </filter>
  <filter id="pen"><feTurbulence type="fractalNoise" baseFrequency=".06" numOctaves="1" seed="5" result="w"/>
    <feDisplacementMap in="SourceGraphic" in2="w" scale="1.6" xChannelSelector="R" yChannelSelector="G"/></filter>
  <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="9"/></filter>
</defs>"""


# ---------- the cover ----------

def build():
    out = []
    add = out.append

    # wordmark
    k = 720 / wordmark_width("FIRELINE")
    word_paths, word_w = wordmark_paths("FIRELINE", k, 70, 112)

    # photo placement: 860x1149 source, shown 452 wide, tilted 2.6 degrees about its centre
    PW = 452
    PH = PW * 1149 / 860
    px, py, rot = 952, 58, 2.6
    pad, pad_b = 12, 44
    pcx, pcy = px + PW / 2, py + PH / 2

    def photo_pt(x, y):
        """Source-photo pixel to canvas, through the same scale and tilt as the print."""
        X, Y = px + x * PW / 860, py + y * PW / 860
        a = math.radians(rot)
        dx, dy = X - pcx, Y - pcy
        return (pcx + dx * math.cos(a) - dy * math.sin(a), pcy + dx * math.sin(a) + dy * math.cos(a))

    add(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
    add(DEFS)
    add(f'<style>.mono{{font-family:"IBM Plex Mono",Consolas,monospace;}} .serif{{font-family:"Newsreader",Georgia,serif;}}</style>')

    # paper
    add(f'<rect width="{W}" height="{H}" fill="{PAPER}" filter="url(#paper)"/>')

    # top meta line
    add(f'<text x="72" y="70" class="mono" font-size="14" letter-spacing="3.2" fill="{INK}" fill-opacity=".72">KNIGHT HACKS IX · FIELD NOTES · OCT 2026</text>')
    add(f'<path d="{rough([(72, 84), (470, 84)], amp=0.6, step=8, seed=4, closed=False)}" stroke="{INK}" stroke-opacity=".5" stroke-width="1.4" fill="none"/>')

    # wordmark: ember plate a hair off register, then the ink plate on top
    add('<g filter="url(#print)">')
    add(f'<g transform="translate(5,4)" style="mix-blend-mode:multiply">' + "".join(f'<path d="{d}" fill="{EMBER}" fill-rule="evenodd"/>' for d in word_paths) + "</g>")
    add('<g style="mix-blend-mode:multiply">' + "".join(f'<path d="{d}" fill="{INK}" fill-rule="evenodd"/>' for d in word_paths) + "</g>")
    add("</g>")

    # tagline + a pen underline under "first smoke"
    add(f'<text x="72" y="356" class="serif" font-size="35" font-style="italic" fill="{INK}">Satellites see a wildfire once it\'s big.</text>')
    add(f'<text x="72" y="402" class="serif" font-size="35" font-style="italic" fill="{INK}">Fireline sees the <tspan fill="{EMBER}">first smoke.</tspan></text>')
    und = [(352 + i * 8, 416 + 2.4 * math.sin(i * 0.9)) for i in range(25)]
    add(f'<path d="{rough(und, amp=0.6, step=6, seed=21, closed=False)}" stroke="{EMBER}" stroke-width="2.4" fill="none" stroke-linecap="round" filter="url(#pen)"/>')

    # ---- forest band ----
    ridge = [(0, 1000), (0, 860)] + [(x, 838 - 22 * math.sin(x / 210 + 1.2) - 10 * math.sin(x / 63)) for x in range(0, W + 30, 30)] + [(W, 1000)]
    add(f'<path d="{rough(ridge, amp=1.4, step=8, seed=31)}" fill="{SAGE}" fill-opacity=".55"/>')

    r = random.Random(7)
    add(f'<g fill="{PINE_BACK}">')
    x = -10
    while x < W + 20:
        h = r.uniform(70, 125)
        parts, _ = pine(x, 905, h, h * 0.5, seed=int(x * 3) + 1)
        add("".join(f'<path d="{d}"/>' for d in parts))
        x += r.uniform(30, 52)
    add("</g>")

    # the first smoke: a small ember fire low in the back row, and a thin plume of puffs drifting left
    fx = FIRE_X
    flame = [(fx - 16, 905), (fx - 10, 884), (fx - 4, 893), (fx + 1, 872), (fx + 6, 890), (fx + 12, 879), (fx + 17, 905)]
    add(f'<path d="{rough(flame, amp=1.2, step=3, seed=77)}" fill="{EMBER}"/>')
    add(f'<path d="{rough([(fx - 7, 905), (fx - 2, 889), (fx + 3, 897), (fx + 8, 905)], amp=0.8, step=3, seed=78)}" fill="{OCHRE}"/>')
    # Puffs cluster along a leaning S-curve and widen as they rise. Every outline is drawn first and
    # every fill on top, so overlaps merge into one billowing silhouette instead of a stack of rings.
    pr = random.Random(12)
    puffs = []
    for i in range(30):
        t = (i / 29) ** 0.85
        cx = fx - 210 * t ** 1.3 + 30 * math.sin(t * 4.2) + pr.uniform(-8, 8) * (0.4 + t)
        cy = 878 - 365 * t + pr.uniform(-6, 6)
        rad = 5 + 36 * t ** 1.2 * pr.uniform(0.75, 1.15)
        puffs.append((cx, cy, rad, t, int(cx * 7 + cy)))
        if t > 0.35:  # a side bulge, so the top billows sideways
            side = pr.choice([-1, 1])
            puffs.append((cx + side * rad * pr.uniform(0.55, 0.85), cy + pr.uniform(-4, 10), rad * pr.uniform(0.55, 0.8), t, int(cy * 3 + i)))
    shapes = [(blob(cx, cy, rad, seed), t) for cx, cy, rad, t, seed in puffs]
    add('<g>' + "".join(f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="4.4" stroke-linejoin="round"/>' for d, _ in shapes) + "</g>")
    add('<g>' + "".join(f'<path d="{d}" fill="{PAPER_LT}"/>' for d, _ in shapes) + "</g>")
    for cx, cy, rad, t, seed in puffs[::3]:  # a few curls cut inside the bigger puffs
        if rad < 20:
            continue
        a0 = pr.uniform(2.6, 3.8)
        curl = [(cx + rad * 0.55 * math.cos(a0 + j * 0.3), cy + rad * 0.55 * math.sin(a0 + j * 0.3)) for j in range(6)]
        add(f'<path d="{rough(curl, amp=0.4, step=4, seed=seed, closed=False)}" fill="none" stroke="{INK}" stroke-opacity=".55" stroke-width="1.6" stroke-linecap="round"/>')

    # front row, carved; one tree carries the unit
    add('<g>')
    x = -20
    unit_tree = 770
    while x < W + 30:
        if abs(x - unit_tree) < 40:
            x = unit_tree
        h = r.uniform(130, 205) if x != unit_tree else 200
        parts, gouges = pine(x, 975, h, h * 0.48, seed=int(x * 5) + 3, carve=True, trunk=0.3 if x == unit_tree else 0.12)
        add(f'<g fill="{PINE_FRONT}">' + "".join(f'<path d="{d}"/>' for d in parts) + "</g>")
        add("".join(f'<path d="{d}" stroke="{SAGE}" stroke-width="1.7" fill="none" stroke-linecap="round"/>' for d in gouges))
        x += r.uniform(46, 78) if abs(x - FIRE_X) > 90 else r.uniform(120, 150)  # leave a gap so the fire shows
    add("</g>")

    # ground, with gouge marks carved out of it
    ground = [(0, 1000), (0, 958)] + [(xx, 952 + 5 * math.sin(xx / 90)) for xx in range(0, W + 25, 25)] + [(W, 1000)]
    add(f'<path d="{rough(ground, amp=1.6, step=6, seed=41)}" fill="{INK}"/>')
    for i in range(60):
        gx, gy = r.uniform(10, W - 40), r.uniform(968, 992)
        gl = r.uniform(8, 36)
        add(f'<path d="{rough([(gx, gy), (gx + gl, gy + r.uniform(-1.5, 1.5))], amp=0.5, step=4, seed=i, closed=False)}" stroke="{PAPER}" stroke-opacity=".55" stroke-width="{r.uniform(1.2, 2.2):.1f}" stroke-linecap="round"/>')
    add(f'<text x="{W - 72}" y="986" text-anchor="end" class="mono" font-size="13" letter-spacing="3.6" fill="{PAPER}" fill-opacity=".8">EDGE WILDFIRE DETECTION</text>')

    # the unit on its tree, and its one small packet climbing to the satellite
    ux, uy = unit_tree, 905
    add(f'<path d="{rough([(ux - 13, uy - 5), (ux + 13, uy - 5)], amp=0.4, seed=5, closed=False)}" stroke="{OCHRE}" stroke-width="2.4"/>')
    add(f'<path d="{rough([(ux - 9, uy - 14), (ux + 9, uy - 14), (ux + 9, uy + 8), (ux - 9, uy + 8)], amp=0.6, seed=6)}" fill="{INK}" stroke="{PAPER}" stroke-width="1.4"/>')
    add(f'<circle cx="{ux + 3}" cy="{uy - 7}" r="2.6" fill="{EMBER}"/>')
    sx, sy = 690, 520
    # little square "packets" climbing from the unit to the satellite on a gentle S-curve
    path = [(ux + (sx - ux) * t + 22 * math.sin(t * math.pi * 1.6), 762 - (762 - sy - 30) * t) for t in [i / 13 for i in range(14)]]
    for qx, qy in path[1:-1]:
        add(f'<rect x="{qx - 2.6:.1f}" y="{qy - 2.6:.1f}" width="5.2" height="5.2" fill="{EMBER}" transform="rotate({r.uniform(-20, 20):.0f} {qx:.1f} {qy:.1f})"/>')
    add(f'<text x="{path[3][0] + 18:.0f}" y="{path[3][1] + 4:.0f}" class="mono" font-size="13" fill="{INK}" fill-opacity=".8">≤ 340 bytes</text>')

    # satellite, pen line
    sat = []
    sat.append(rough([(-13, -9), (13, -9), (13, 9), (-13, 9)], amp=0.5, seed=60))
    for side in (-1, 1):
        x0, x1 = (16, 50) if side > 0 else (-50, -16)
        sat.append(rough([(x0, -7), (x1, -7), (x1, 7), (x0, 7)], amp=0.5, seed=61 + side))
        for gx in range(1, 4):
            xx = x0 + (x1 - x0) * gx / 4
            sat.append(rough([(xx, -7), (xx, 7)], amp=0.2, seed=62 + gx + side, closed=False))
        sat.append(rough([(13 * side, 0), (16 * side, 0)], amp=0.1, seed=70 + side, closed=False))
    sat.append(rough([(0, 9), (0, 18)], amp=0.2, seed=72, closed=False))
    add(f'<g transform="translate({sx},{sy}) rotate(-18)" filter="url(#pen)">'
        + "".join(f'<path d="{d}" fill="{PAPER_LT if d.endswith("Z") else "none"}" stroke="{INK}" stroke-width="1.9" stroke-linejoin="round"/>' for d in sat)
        + f'<circle cx="0" cy="21" r="3" fill="{INK}"/></g>')

    # ---- the taped print ----
    add(f'<g transform="rotate({rot} {pcx} {pcy})">')
    add(f'<rect x="{px - pad + 7}" y="{py - pad + 12}" width="{PW + 2 * pad}" height="{PH + pad + pad_b}" fill="#3a2d1c" fill-opacity=".28" filter="url(#shadow)"/>')
    add(f'<rect x="{px - pad}" y="{py - pad}" width="{PW + 2 * pad}" height="{PH + pad + pad_b}" fill="#f7f2e6"/>')
    add(f'<image href="prototype.jpg" x="{px}" y="{py}" width="{PW}" height="{PH:.1f}" preserveAspectRatio="none"/>')
    add(f'<text x="{px + 2}" y="{py + PH + 29:.0f}" class="mono" font-size="12.5" fill="{INK}" fill-opacity=".78">fig. 1 — unit gw-01, on the box the Jetson came in</text>')
    add("</g>")
    add(tape(px + 40, py - 6, 110, 30, -24, 81))
    add(tape(px + PW - 30, py - 4, 100, 28, 19, 82))
    add(tape(px + PW + 2, py + PH + 18, 96, 28, -12, 83))

    # hand labels and arrows into the photo
    lab = dict(cls="mono", size=13.5)

    def label(x, y, lines, anchor="start"):
        for j, t in enumerate(lines):
            weight = 600 if j == 0 else 400
            op = 1 if j == 0 else .72
            add(f'<text x="{x}" y="{y + j * 17}" text-anchor="{anchor}" class="mono" font-size="{lab["size"]}" font-weight="{weight}" fill="{INK}" fill-opacity="{op}">{t}</text>')

    label(800, 168, ["WEBCAM", "looks out", "for smoke"])
    add(arrow((866, 152), photo_pt(70, 168), -22, 101))
    label(800, 262, ["JETSON", "ORIN NANO", "runs the model"])
    add(arrow((900, 275), photo_pt(470, 240), 30, 102))
    label(800, 560, ["DHT11", "reads the air"])
    add(arrow((860, 548), photo_pt(392, 925), -22, 103))
    label(800, 636, ["ESP32", "always on,", "wakes the", "Jetson"])
    add(arrow((852, 624), photo_pt(540, 1020), 34, 104))

    add("</svg>")
    return "\n".join(out), (word_paths, word_w)


def build_thumb():
    """Devpost card version. The card shows it about 400 px wide with the tagline printed underneath,
    so this keeps only what survives that size: a bigger wordmark, a bigger print, the smoke and the satellite."""
    TW, TH = 1200, 800
    out = []
    add = out.append
    r = random.Random(17)

    add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {TW} {TH}" width="{TW}" height="{TH}">')
    add(DEFS)
    add(f'<rect width="{TW}" height="{TH}" fill="{PAPER}" filter="url(#paper)"/>')

    k = 700 / wordmark_width("FIRELINE")
    word_paths, _ = wordmark_paths("FIRELINE", k, 50, 74, seed=3)
    add('<g filter="url(#print)">')
    add(f'<g transform="translate(6,5)" style="mix-blend-mode:multiply">' + "".join(f'<path d="{d}" fill="{EMBER}" fill-rule="evenodd"/>' for d in word_paths) + "</g>")
    add('<g style="mix-blend-mode:multiply">' + "".join(f'<path d="{d}" fill="{INK}" fill-rule="evenodd"/>' for d in word_paths) + "</g>")
    add("</g>")

    # forest
    ridge = [(0, TH), (0, 672)] + [(x, 652 - 18 * math.sin(x / 190 + 0.4) - 8 * math.sin(x / 57)) for x in range(0, TW + 30, 30)] + [(TW, TH)]
    add(f'<path d="{rough(ridge, amp=1.3, step=8, seed=32)}" fill="{SAGE}" fill-opacity=".55"/>')
    add(f'<g fill="{PINE_BACK}">')
    x = -10
    while x < TW + 20:
        h = r.uniform(58, 98)
        parts, _ = pine(x, 714, h, h * 0.5, seed=int(x * 3) + 5)
        add("".join(f'<path d="{d}"/>' for d in parts))
        x += r.uniform(26, 44)
    add("</g>")

    # fire and plume (outlines first, fills on top, so the puffs merge into one shape)
    fx = 330
    flame = [(fx - 15, 716), (fx - 9, 696), (fx - 3, 705), (fx + 1, 684), (fx + 6, 702), (fx + 11, 691), (fx + 16, 716)]
    add(f'<path d="{rough(flame, amp=1.1, step=3, seed=79)}" fill="{EMBER}"/>')
    add(f'<path d="{rough([(fx - 7, 716), (fx - 2, 701), (fx + 3, 709), (fx + 8, 716)], amp=0.7, step=3, seed=80)}" fill="{OCHRE}"/>')
    pr = random.Random(14)
    puffs = []
    for i in range(26):
        t = (i / 25) ** 0.85
        cx = fx - 175 * t ** 1.3 + 26 * math.sin(t * 4.2) + pr.uniform(-7, 7) * (0.4 + t)
        cy = 690 - 330 * t + pr.uniform(-5, 5)
        rad = 5 + 34 * t ** 1.2 * pr.uniform(0.75, 1.15)
        puffs.append((cx, cy, rad, int(cx * 7 + cy)))
        if t > 0.35:
            side = pr.choice([-1, 1])
            puffs.append((cx + side * rad * pr.uniform(0.55, 0.85), cy + pr.uniform(-4, 9), rad * pr.uniform(0.55, 0.8), int(cy * 3 + i)))
    shapes = [blob(cx, cy, rad, seed) for cx, cy, rad, seed in puffs]
    add("".join(f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="4.6" stroke-linejoin="round"/>' for d in shapes))
    add("".join(f'<path d="{d}" fill="{PAPER_LT}"/>' for d in shapes))
    for cx, cy, rad, seed in puffs[::3]:
        if rad < 18:
            continue
        a0 = pr.uniform(2.6, 3.8)
        curl = [(cx + rad * 0.55 * math.cos(a0 + j * 0.3), cy + rad * 0.55 * math.sin(a0 + j * 0.3)) for j in range(6)]
        add(f'<path d="{rough(curl, amp=0.4, step=4, seed=seed, closed=False)}" fill="none" stroke="{INK}" stroke-opacity=".55" stroke-width="1.8" stroke-linecap="round"/>')

    # front row, with a gap for the fire and one tree carrying the unit
    unit_tree = 640
    x = -20
    while x < TW + 30:
        if abs(x - unit_tree) < 36:
            x = unit_tree
        h = r.uniform(112, 170) if x != unit_tree else 168
        parts, gouges = pine(x, 782, h, h * 0.48, seed=int(x * 5) + 9, carve=True, trunk=0.3 if x == unit_tree else 0.12)
        add(f'<g fill="{PINE_FRONT}">' + "".join(f'<path d="{d}"/>' for d in parts) + "</g>")
        add("".join(f'<path d="{d}" stroke="{SAGE}" stroke-width="1.7" fill="none" stroke-linecap="round"/>' for d in gouges))
        x += r.uniform(42, 68) if abs(x - fx) > 80 else r.uniform(105, 130)
    ground = [(0, TH), (0, 768)] + [(xx, 763 + 4 * math.sin(xx / 80)) for xx in range(0, TW + 25, 25)] + [(TW, TH)]
    add(f'<path d="{rough(ground, amp=1.5, step=6, seed=42)}" fill="{INK}"/>')
    for i in range(36):
        gx, gy = r.uniform(10, TW - 40), r.uniform(776, 794)
        gl = r.uniform(8, 30)
        add(f'<path d="{rough([(gx, gy), (gx + gl, gy + r.uniform(-1.2, 1.2))], amp=0.5, step=4, seed=i + 200, closed=False)}" stroke="{PAPER}" stroke-opacity=".5" stroke-width="{r.uniform(1.2, 2.2):.1f}" stroke-linecap="round"/>')

    # unit, packets, satellite
    ux, uy = unit_tree, 734
    add(f'<path d="{rough([(ux - 12, uy - 4), (ux + 12, uy - 4)], amp=0.4, seed=7, closed=False)}" stroke="{OCHRE}" stroke-width="2.6"/>')
    add(f'<path d="{rough([(ux - 10, uy - 14), (ux + 10, uy - 14), (ux + 10, uy + 9), (ux - 10, uy + 9)], amp=0.6, seed=8)}" fill="{INK}" stroke="{PAPER}" stroke-width="1.6"/>')
    add(f'<circle cx="{ux + 3}" cy="{uy - 6}" r="3" fill="{EMBER}"/>')
    sx, sy = 575, 330
    trail = [(ux + (sx - ux) * t + 18 * math.sin(t * math.pi * 1.6), 602 - (602 - sy - 32) * t) for t in [i / 11 for i in range(12)]]
    for qx, qy in trail[:-1]:
        add(f'<rect x="{qx - 3.2:.1f}" y="{qy - 3.2:.1f}" width="6.4" height="6.4" fill="{EMBER}" transform="rotate({r.uniform(-20, 20):.0f} {qx:.1f} {qy:.1f})"/>')
    sat = [rough([(-13, -9), (13, -9), (13, 9), (-13, 9)], amp=0.5, seed=60)]
    for side in (-1, 1):
        x0, x1 = (16, 50) if side > 0 else (-50, -16)
        sat.append(rough([(x0, -7), (x1, -7), (x1, 7), (x0, 7)], amp=0.5, seed=61 + side))
        for gx in range(1, 4):
            xx = x0 + (x1 - x0) * gx / 4
            sat.append(rough([(xx, -7), (xx, 7)], amp=0.2, seed=62 + gx + side, closed=False))
        sat.append(rough([(13 * side, 0), (16 * side, 0)], amp=0.1, seed=70 + side, closed=False))
    sat.append(rough([(0, 9), (0, 18)], amp=0.2, seed=72, closed=False))
    add(f'<g transform="translate({sx},{sy}) rotate(-18) scale(1.35)" filter="url(#pen)">'
        + "".join(f'<path d="{d}" fill="{PAPER_LT if d.endswith("Z") else "none"}" stroke="{INK}" stroke-width="1.9" stroke-linejoin="round"/>' for d in sat)
        + f'<circle cx="0" cy="21" r="3" fill="{INK}"/></g>')

    # the print: larger than on the cover, no caption (it would be 4 px tall on the card)
    PW = 372
    PH = PW * 1149 / 860
    px, py, rot = 792, 46, 3.2
    pad = 12
    pcx, pcy = px + PW / 2, py + PH / 2
    add(f'<g transform="rotate({rot} {pcx} {pcy})">')
    add(f'<rect x="{px - pad + 7}" y="{py - pad + 12}" width="{PW + 2 * pad}" height="{PH + 2 * pad + 14}" fill="#3a2d1c" fill-opacity=".28" filter="url(#shadow)"/>')
    add(f'<rect x="{px - pad}" y="{py - pad}" width="{PW + 2 * pad}" height="{PH + 2 * pad + 14}" fill="#f7f2e6"/>')
    add(f'<image href="prototype.jpg" x="{px}" y="{py}" width="{PW}" height="{PH:.1f}" preserveAspectRatio="none"/>')
    add("</g>")
    add(tape(px + 34, py - 6, 104, 30, -24, 91))
    add(tape(px + PW - 26, py - 2, 96, 28, 20, 92))

    add("</svg>")
    return "\n".join(out)


def wordmark_svg():
    k = 1.0
    paths, w = wordmark_paths("FIRELINE", k, 24, 24)
    body = "".join(f'<path d="{d}" fill="{INK}" fill-rule="evenodd"/>' for d in paths)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w + 56:.0f} 224" width="{w + 56:.0f}" height="224">'
            f'<g transform="translate(5,4)" opacity=".9">' + "".join(f'<path d="{d}" fill="{EMBER}" fill-rule="evenodd"/>' for d in paths)
            + f'</g>{body}</svg>')


if __name__ == "__main__":
    svg, _ = build()
    fonts = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?'
             'family=IBM+Plex+Mono:wght@400;600&family=Newsreader:ital,opsz,wght@1,6..72,400&display=swap" rel="stylesheet">')
    (HERE / "cover.svg").write_text(svg, encoding="utf-8")
    (HERE / "cover.html").write_text(f'<!doctype html><meta charset="utf-8">{fonts}'
                                     f'<style>html,body{{margin:0;background:{PAPER}}}svg{{display:block}}</style>{svg}', encoding="utf-8")
    (HERE / "wordmark.svg").write_text(wordmark_svg(), encoding="utf-8")
    thumb = build_thumb()
    (HERE / "thumb.svg").write_text(thumb, encoding="utf-8")
    (HERE / "thumb.html").write_text(f'<!doctype html><meta charset="utf-8">'
                                     f'<style>html,body{{margin:0;background:{PAPER}}}svg{{display:block}}</style>{thumb}', encoding="utf-8")
    print("wrote cover.svg, cover.html, wordmark.svg, thumb.svg, thumb.html")
