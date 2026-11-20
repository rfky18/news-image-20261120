#!/usr/bin/env python3
"""news-image-20261120 v4 engine — authored from scratch.

Renders "The World at a Crossroads - 20 November 2026" (1024x1024 PNG).
Pure Python stdlib only, no network, deterministic (two runs -> identical bytes).

Design notes (all original work for this version):
- Custom stroke font: glyphs are hand-authored polylines on a 14-unit
  cap-height grid, drawn as thick round-capped strokes at 2x supersampling
  and box-downsampled -> smooth anti-aliased type, no bitmap font.
- Continents are hand-authored lat/lon polygons projected orthographically
  (centre 60E/20N) from geographic knowledge; no embedded raster mask.
- Every illustration (summit, ICJ palace, parliament, tanker, cyclone) is
  drawn from primitive shapes in this file.
"""
import math
import os
import random
import struct
import zlib

W, H = 1024, 1024
SS = 2  # supersampling factor

OUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
OUT_PATH = os.path.join(OUT_DIR, "entry.png")

# ---------------------------------------------------------------- PNG writer
def _png_chunk(ctype, data):
    c = struct.pack(">I", len(data)) + ctype + data
    c += struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
    return c


def save_png(path, rgb, w, h):
    """rgb: bytes of w*h*3. Deterministic: fixed filters + zlib level 9."""
    raw = bytearray()
    stride = w * 3
    prev = bytearray(stride)
    for y in range(h):
        row = rgb[y * stride:(y + 1) * stride]
        if y == 0:
            raw.append(0)
            raw += row
        else:
            raw.append(2)  # Up filter
            raw += bytes((row[i] - prev[i]) & 0xFF for i in range(stride))
        prev = row
    comp = zlib.compress(bytes(raw), 9)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += _png_chunk(b"IDAT", comp)
    png += _png_chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------------- Canvas
class Canvas:
    """RGB canvas rendered at SSx supersampling, box-downsampled on output.
    All public coordinates are in final (1024) pixels; floats allowed."""

    def __init__(self, w=W, h=H, ss=SS):
        self.w, self.h, self.ss = w, h, ss
        self.W, self.H = w * ss, h * ss
        self.buf = bytearray(self.W * self.H * 3)

    # -- low level (buffer coords, ints) --------------------------------
    def _hspan(self, x0, x1, y, r, g, b):
        """Opaque horizontal span in buffer coords."""
        if y < 0 or y >= self.H or x1 < 0 or x0 >= self.W:
            return
        x0 = max(0, x0)
        x1 = min(self.W - 1, x1)
        if x1 < x0:
            return
        i0 = (y * self.W + x0) * 3
        n = x1 - x0 + 1
        self.buf[i0:i0 + n * 3] = bytes((r, g, b)) * n

    def _hspan_a(self, x0, x1, y, r, g, b, a):
        """Alpha horizontal span in buffer coords."""
        if y < 0 or y >= self.H or x1 < 0 or x0 >= self.W or a <= 0:
            return
        if a >= 255:
            self._hspan(x0, x1, y, r, g, b)
            return
        x0 = max(0, x0)
        x1 = min(self.W - 1, x1)
        if x1 < x0:
            return
        buf = self.buf
        inv = 255 - a
        i = (y * self.W + x0) * 3
        for _ in range(x1 - x0 + 1):
            buf[i] = (r * a + buf[i] * inv) // 255
            buf[i + 1] = (g * a + buf[i + 1] * inv) // 255
            buf[i + 2] = (b * a + buf[i + 2] * inv) // 255
            i += 3

    # -- public primitives (final coords) --------------------------------
    def fill_rect(self, x0, y0, x1, y1, color, alpha=255):
        r, g, b = color
        ss = self.ss
        bx0 = int(round(x0 * ss))
        bx1 = int(round(x1 * ss)) - 1
        by0 = int(round(y0 * ss))
        by1 = int(round(y1 * ss)) - 1
        if alpha >= 255:
            for y in range(by0, by1 + 1):
                self._hspan(bx0, bx1, y, r, g, b)
        else:
            for y in range(by0, by1 + 1):
                self._hspan_a(bx0, bx1, y, r, g, b, alpha)

    def fill_circle(self, cx, cy, rad, color, alpha=255, clip_disc=None):
        """Filled circle. clip_disc=(dcx,dcy,dR) in final px: intersect rows."""
        r, g, b = color
        ss = self.ss
        bcx, bcy, br = cx * ss, cy * ss, rad * ss
        y0 = int(math.floor(bcy - br))
        y1 = int(math.ceil(bcy + br))
        for y in range(y0, y1 + 1):
            dy = y + 0.5 - bcy
            rem = br * br - dy * dy
            if rem < 0:
                continue
            dx = math.sqrt(rem)
            x0 = int(math.ceil(bcx - dx))
            x1 = int(math.floor(bcx + dx))
            if clip_disc is not None:
                dcx, dcy, dR = clip_disc
                ddy = y / ss + 0.5 / ss - dcy
                rrem = dR * dR - ddy * ddy
                if rrem < 0:
                    continue
                ddx = math.sqrt(rrem) * ss
                cx0 = int(math.ceil(dcx * ss - ddx))
                cx1 = int(math.floor(dcx * ss + ddx))
                x0 = max(x0, cx0)
                x1 = min(x1, cx1)
            if alpha >= 255:
                self._hspan(x0, x1, y, r, g, b)
            else:
                self._hspan_a(x0, x1, y, r, g, b, alpha)

    def ring(self, cx, cy, rad, width, color, alpha=255):
        """Thin ring: for each row, draw the two side spans of the annulus."""
        r, g, b = color
        ss = self.ss
        bcx, bcy = cx * ss, cy * ss
        ro, ri = rad * ss, max(0.0, (rad - width) * ss)
        y0 = int(math.floor(bcy - ro))
        y1 = int(math.ceil(bcy + ro))
        for y in range(y0, y1 + 1):
            dy = y + 0.5 - bcy
            rem_o = ro * ro - dy * dy
            if rem_o < 0:
                continue
            dxo = math.sqrt(rem_o)
            rem_i = ri * ri - dy * dy
            dxi = math.sqrt(rem_i) if rem_i > 0 else 0.0
            for (x0, x1) in ((int(math.ceil(bcx - dxo)), int(math.floor(bcx - dxi))),
                             (int(math.ceil(bcx + dxi)), int(math.floor(bcx + dxo)))):
                if x1 < x0:
                    continue
                if alpha >= 255:
                    self._hspan(x0, x1, y, r, g, b)
                else:
                    self._hspan_a(x0, x1, y, r, g, b, alpha)

    def fill_polygon(self, pts, color, alpha=255):
        """Scanline fill (even-odd). pts: list of (x,y) in final px."""
        if len(pts) < 3:
            return
        r, g, b = color
        ss = self.ss
        P = [(x * ss, y * ss) for (x, y) in pts]
        ys = [p[1] for p in P]
        y0 = int(math.floor(min(ys)))
        y1 = int(math.ceil(max(ys)))
        n = len(P)
        for y in range(y0, y1 + 1):
            yc = y + 0.5
            xs = []
            for i in range(n):
                x0, y0p = P[i]
                x1, y1p = P[(i + 1) % n]
                if (y0p <= yc < y1p) or (y1p <= yc < y0p):
                    t = (yc - y0p) / (y1p - y0p)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                x0 = int(math.ceil(xs[k]))
                x1 = int(math.floor(xs[k + 1]))
                if alpha >= 255:
                    self._hspan(x0, x1, y, r, g, b)
                else:
                    self._hspan_a(x0, x1, y, r, g, b, alpha)

    def thick_line(self, x0, y0, x1, y1, width, color, alpha=255):
        """Line with round caps: quad + end circles."""
        ss = self.ss
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        hw = width / 2.0
        if L < 1e-6:
            self.fill_circle(x0, y0, hw, color, alpha)
            return
        px, py = -dy / L * hw, dx / L * hw
        self.fill_polygon([(x0 + px, y0 + py), (x1 + px, y1 + py),
                           (x1 - px, y1 - py), (x0 - px, y0 - py)],
                          color, alpha)
        self.fill_circle(x0, y0, hw, color, alpha)
        self.fill_circle(x1, y1, hw, color, alpha)

    def polyline(self, pts, width, color, alpha=255):
        if len(pts) == 1:
            self.fill_circle(pts[0][0], pts[0][1], width * 0.75, color, alpha)
            return
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            self.thick_line(x0, y0, x1, y1, width, color, alpha)

    def arc_polyline(self, cx, cy, rad, a0, a1, width, color, alpha=255, steps=36):
        pts = []
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
        self.polyline(pts, width, color, alpha)

    def downsample(self):
        """Box-average SSxSS -> final RGB bytes."""
        buf = self.buf
        W3 = self.W * 3
        out = bytearray(self.w * self.h * 3)
        for oy in range(self.h):
            i0 = (oy * 2) * W3
            i1 = i0 + W3
            base = oy * self.w * 3
            for ox in range(self.w):
                j = i0 + ox * 6
                k = i1 + ox * 6
                o = base + ox * 3
                out[o] = (buf[j] + buf[j + 3] + buf[k] + buf[k + 3] + 2) // 4
                out[o + 1] = (buf[j + 1] + buf[j + 4] + buf[k + 1] + buf[k + 4] + 2) // 4
                out[o + 2] = (buf[j + 2] + buf[j + 5] + buf[k + 2] + buf[k + 5] + 2) // 4
        return bytes(out)


# ---------------------------------------------------------------- Stroke font
# Glyphs are polylines on a 14-unit cap-height grid (baseline y=0, cap y=14,
# descender y=-4). Format: "advance|stroke1;stroke2" / stroke = "x,y x,y ...".
# A single-point stroke renders as a dot. Authored by hand for this engine.
_FONT_RAW = {
    "A": "12|0,0 6,14 12,0;3.5,5 8.5,5",
    "B": "11|0,0 0,14;0,14 8,14 11,11 8,8 0,8;0,8 9,8 12,4.5 9,0 0,0",
    "C": "11|11,12 8,14 3,14 0,10 0,4 3,0 8,0 11,2",
    "D": "12|0,0 0,14;0,14 8,14 12,10 12,4 8,0 0,0",
    "E": "11|11,14 0,14 0,0 11,0;0,7 8,7",
    "F": "10|0,0 0,14 11,14;0,7 8,7",
    "G": "12|11,12 9,14 3,14 0,11 0,3 3,0 9,0 11,2 11,6;11,6 6,6",
    "H": "12|0,0 0,14;12,0 12,14;0,7 12,7",
    "I": "6|6,0 6,14",
    "J": "10|12,14 12,3 9,0 4,0 2,2",
    "K": "12|0,0 0,14;11,14 0,6;5,8 12,0",
    "L": "11|0,14 0,0 11,0",
    "M": "14|0,0 0,14 7,4 14,14 14,0",
    "N": "12|0,0 0,14 12,0 12,14",
    "O": "12|6,14 2,13 0,10 0,4 2,1 6,0 10,1 12,4 12,10 10,13 6,14",
    "P": "11|0,0 0,14;0,14 8,14 11,11 8,7 0,7",
    "Q": "12|6,14 2,13 0,10 0,4 2,1 6,0 10,1 12,4 12,10 10,13 6,14;7,4 12,-1",
    "R": "11|0,0 0,14;0,14 8,14 11,11 8,7 0,7;6,8 12,0",
    "S": "11|11,12 8,14 3,14 1,12 1,9 4,7 8,7 11,5 11,2 8,0 3,0 0,2",
    "T": "11|0,14 11,14;5.5,14 5.5,0",
    "U": "12|0,14 0,3 3,0 9,0 12,3 12,14",
    "V": "12|0,14 6,0 12,14",
    "W": "15|0,14 3.5,0 7.5,7 11.5,0 15,14",
    "X": "12|0,14 12,0;12,14 0,0",
    "Y": "11|0,14 5.5,7 11,14;5.5,7 5.5,0",
    "Z": "11|0,14 11,14 0,0 11,0",
    "a": "11|10,10 10,0;3,10 1,8 1,3 3,0 8,0 10,2 10,8 8,10 3,10",
    "b": "11|1,14 1,0;1,10 5,10 9,8 10,5 9,2 5,0 1,0",
    "c": "10|10,8 8,10 3,10 1,8 1,3 3,0 8,0 10,2",
    "d": "11|11,14 11,0;11,10 7,10 3,8 2,5 3,2 7,0 11,0",
    "e": "10|10,2 8,0 3,0 1,3 1,7 4,10 8,10 10,8 10,5 1,5",
    "f": "7|4,0 4,11 5,14 8,14 10,13;2,10 8,10",
    "g": "11|3,10 1,8 1,3 3,0 8,0 10,2 10,8 8,10 3,10;10,8 10,-2 7,-4 3,-4 2,-3",
    "h": "11|1,14 1,0;1,10 4,10 8,10 10,8 10,0",
    "i": "5|5,10 5,0;5,13.5",
    "j": "6|8,10 8,-2 6,-4 3,-4 2,-3;8,13.5",
    "k": "11|1,14 1,0;10,10 1,4;5,6 10,0",
    "l": "5|5,14 5,0",
    "m": "16|1,10 1,0;1,10 4,10 6,8 6,0;6,10 9,10 11,8 11,0",
    "n": "11|1,10 1,0;1,10 4,10 8,10 10,8 10,0",
    "o": "11|5,10 2,9 1,7 1,3 2,1 5,0 8,1 10,3 10,7 8,9 5,10",
    "p": "11|1,10 1,-4;1,10 5,10 9,9 10,7 10,3 9,1 5,0 1,0",
    "q": "11|11,10 11,-4;11,10 7,10 3,9 2,7 2,3 3,1 7,0 11,0",
    "r": "7|1,10 1,0;1,10 4,10 7,10 9,8",
    "s": "10|9,8 6,10 3,10 1,8 1,6 4,5 7,5 9,3 9,1 6,0 3,0 1,2",
    "t": "7|5,13 5,2 7,0 9,0;2,10 8,10",
    "u": "11|1,10 1,3 3,0 7,0 9,2 9,10",
    "v": "11|0,10 5.5,0 11,10",
    "w": "15|0,10 3,0 7.5,6 12,0 15,10",
    "x": "11|0,10 11,0;11,10 0,0",
    "y": "11|0,10 5.5,0 11,10;5.5,0 5.5,-3 3.5,-4",
    "z": "10|0,10 10,10 0,0 10,0",
    "0": "12|6,14 2,13 0,10 0,4 2,1 6,0 10,1 12,4 12,10 10,13 6,14",
    "1": "9|3,10 7,14 7,0;4,0 10,0",
    "2": "11|2,11 4,14 9,14 11,11 11,8 6,4 1,0 11,0",
    "3": "11|2,12 4,14 8,14 11,12 11,10 8,8 4,8;8,8 11,6 11,3 8,0 4,0 2,2",
    "4": "11|9,14 1,5 10,5;9,14 9,0",
    "5": "11|11,14 2,14 2,8 8,8 11,6 11,3 8,0 3,0 1,2",
    "6": "11|10,13 8,14 4,14 2,12 1,9 1,4 3,0 8,0 11,2 11,6 8,9 4,9 1,7",
    "7": "10|1,14 10,14 5,0",
    "8": "11|6,14 3,13 1,11 1,8 3,7 6,7 9,7 11,8 11,11 9,13 6,14;6,7 3,7 1,5 1,2 3,0 6,0 9,0 11,2 11,5 9,7 6,7",
    "9": "11|2,1 4,0 8,0 10,2 11,5 11,10 9,14 4,14 1,12 1,8 4,5 8,5 11,7",
    ".": "5|6,1",
    ",": "5|6,1.5 6,-1 3.5,-3.5",
    ":": "5|6,10;6,3",
    ";": "5|6,10;6,3 6,1 4,-2",
    "!": "5|6,14 6,5;6,1",
    "?": "11|3,12 5,14 9,14 11,12 11,9 8,7 6,5 6,3.5;6,1",
    "'": "5|6.5,14 5,10.5",
    '"': "8|4,14 3,10.5;8,14 7,10.5",
    "—": "13|0,7 13,7",
    "–": "11|1,7 10,7",
    "·": "6|6,7",
    "/": "7|11,14 1,0",
    "(": "6|8,14 5,11 4,7 5,3 8,0",
    ")": "6|4,14 7,11 8,7 7,3 4,0",
    "%": "13|2,13 4,13 5,11 4,9 2,9 1,11 2,13;7,5 9,5 10,3 9,1 7,1 6,3 7,5;11,14 1,0",
    "+": "11|6,3 6,11;2,7 10,7",
    "=": "11|1,5 11,5;1,9 11,9",
    " ": "6|",
}

# Extra serif ticks for the display masthead (same strokes + these ticks).
_SERIF_RAW = {
    "T": "3.5,0 8.5,0",
    "H": "-1.5,14 2,14;-1.5,0 2,0;10,14 13.5,14;10,0 13.5,0",
    "E": "-1.5,14 2,14;-1.5,0 2,0",
    "R": "-1.5,14 2,14;-1.5,0 2,0",
    "L": "-1.5,14 2,14",
    "D": "-1.5,14 2,14;-1.5,0 2,0",
    "A": "-1.5,0 2.5,0;9.5,0 13.5,0",
    "F": "-1.5,0 2,0",
    "I": "2,14 10,14;2,0 10,0",
    "N": "-1.5,14 2,14;-1.5,0 2,0;10,14 13.5,14;10,0 13.5,0",
    "M": "-1.5,14 2,14;-1.5,0 2,0;10,14 13.5,14;10,0 13.5,0",
    "B": "-1.5,14 2,14;-1.5,0 2,0",
}


def _parse_strokes(s):
    out = []
    if not s:
        return out
    for st in s.split(";"):
        pts = []
        for tok in st.split():
            x, y = tok.split(",")
            pts.append((float(x), float(y)))
        if pts:
            out.append(pts)
    return out


FONT = {}
for _ch, _raw in _FONT_RAW.items():
    _adv, _st = _raw.split("|", 1)
    FONT[_ch] = (float(_adv), _parse_strokes(_st))

SERIF = {ch: _parse_strokes(s) for ch, s in _SERIF_RAW.items()}

WEIGHTS = {"light": 1.15, "normal": 1.45, "bold": 1.8, "black": 2.2}
# Minimum stroke width in final px. At SS=2 a stroke narrower than 1.5px
# spans <3 buffer px, and fill_polygon's ceil/floor can split it across
# two final pixels at ~50% grey with no full-strength core pixel -- whole
# narrow glyphs (I/i/l, curved walls of a/o/u) read as holes at small
# sizes. 1.5px guarantees >=3 painted buffer cols -> >=1 core pixel at
# full strength for every vertical/horizontal stroke (1.6 gives the same
# guarantee plus a margin for diagonal strokes). Only small text is
# affected (normal <=14, bold <=11); larger text is unchanged.
MIN_STROKE = 1.6
GLYPH_SHRINK = 0.76  # horizontal glyph shrink inside its advance:
# adds side bearings so adjacent strokes never touch


def text_width(text, size, weight="normal", tracking=0.0, serif=False):
    """Width in final px of `text` at cap-height `size`."""
    scale = size / 14.0
    w = 0.0
    for ch in text:
        adv, _ = FONT.get(ch, FONT[" "])
        w += adv * scale
    if len(text) > 1:
        w += tracking * (len(text) - 1)
    return w


def draw_text(cv, x, y, text, size, color, weight="normal", align="left",
              tracking=0.0, serif=False, alpha=255):
    """Draw text; (x,y) is the baseline anchor per `align`."""
    scale = size / 14.0
    wdt = max(WEIGHTS[weight] * scale, MIN_STROKE)
    total = text_width(text, size, weight, tracking, serif)
    if align == "center":
        cx = x - total / 2.0
    elif align == "right":
        cx = x - total
    else:
        cx = x
    for ch in text:
        adv, strokes = FONT.get(ch, FONT[" "])
        if serif and ch in SERIF:
            strokes = strokes + SERIF[ch]
        for st in strokes:
            pts = []
            for (px, py) in st:
                # shrink glyph horizontally around its advance centre
                qx = (px - adv / 2.0) * GLYPH_SHRINK + adv / 2.0
                pts.append((cx + qx * scale, y - py * scale))
            cv.polyline(pts, wdt, color, alpha)
        cx += adv * scale + tracking
    return total


def wrap_balanced(text, size, weight, max_w, lines=2, tracking=0.0):
    """Split text into `lines` lines: every line fits, lengths balanced
    (avoids a lone short word on the last line)."""
    words = text.split(" ")
    if lines == 1:
        return [text]
    best = None
    # choose 1 break point (2 lines)
    for b in range(1, len(words)):
        l1 = " ".join(words[:b])
        l2 = " ".join(words[b:])
        w1 = text_width(l1, size, weight, tracking)
        w2 = text_width(l2, size, weight, tracking)
        if w1 > max_w or w2 > max_w:
            continue
        score = abs(w1 - w2)
        if best is None or score < best[0]:
            best = (score, [l1, l2])
    if best is None:  # fall back to greedy
        out, cur = [], ""
        for wd in words:
            t = (cur + " " + wd).strip()
            if text_width(t, size, weight, tracking) <= max_w or not cur:
                cur = t
            else:
                out.append(cur)
                cur = wd
        out.append(cur)
        return out[:lines]
    return best[1]


# ---------------------------------------------------------------- Globe
# Continents as (lon, lat) polygons, authored from geographic knowledge.
# Orthographic projection, centre 60E/20N. Fitted to the reference render:
# globe centre (511,384), radius 151.
GLOBE_CX, GLOBE_CY, GLOBE_R = 511.0, 384.0, 151.0
LON0, LAT0 = 60.0, 20.0

AFRICA = [(-6, 35.8), (-9, 33), (-10, 31), (-13, 29), (-15, 27), (-17, 24),
          (-17, 21), (-17, 17), (-15, 12), (-12, 8), (-8, 5), (-4, 5),
          (0, 6), (4, 6), (6, 4), (9, 4), (9, 1), (9, -1), (12, -4),
          (13, -8), (12, -12), (13, -16), (14, -20), (15, -24), (16, -28),
          (18, -32), (20, -35), (25, -34), (28, -33), (32, -29), (35, -25),
          (36, -22), (40, -18), (40, -14), (40, -10), (39, -6), (41, -2),
          (41, 1), (46, 3), (51, 10), (51, 11), (47, 11), (44, 11),
          (42, 13), (40, 15), (39, 18), (38, 20), (37, 23), (36, 26),
          (34, 28), (34, 31), (32, 31), (30, 31), (27, 32), (24, 33),
          (20, 33), (16, 33), (12, 34), (11, 34), (10, 37), (8, 37),
          (5, 37), (2, 36.5), (0, 36), (-2, 35.5), (-4, 35.5), (-6, 35.8)]
MADAGASCAR = [(44, -16), (47, -15), (50, -16), (50, -18), (48, -21),
              (46, -24), (44, -25), (43, -22), (43, -19), (44, -16)]
EUROPE = [(-6, 36), (-9, 37), (-9, 39), (-9, 41), (-9, 43), (-4, 44),
          (-2, 43.5), (-1, 46), (-3, 47.5), (-5, 48.5), (-2, 49.5), (0, 50),
          (2, 51), (4, 52.5), (5, 53.5), (7, 54.5), (8, 56), (8, 57.5),
          (10, 58), (12, 56.5), (13, 55), (15, 54), (17, 55), (19, 56),
          (21, 58.5), (23, 59.5), (24, 61), (25, 64), (27, 67), (29, 69.5),
          (30, 70.5), (26, 71), (22, 70), (19, 69), (16, 67.5), (13, 65),
          (11, 62.5), (8, 61), (5, 60), (5, 58), (7, 57.5), (10, 57),
          (12, 56), (14, 55), (17, 54.5), (19, 54.5), (21, 54), (23, 55),
          (24, 56.5), (26, 58), (28, 59.5), (30, 60), (28, 45), (30, 45),
          (33, 44.5), (36, 44), (39, 44), (38, 42), (36, 41), (33, 41),
          (30, 41), (28, 41), (26, 40.5), (23, 40), (20, 40), (18, 42),
          (16, 43), (14, 45), (12, 45), (10, 44), (8, 44), (6, 43.5),
          (4, 43.5), (3, 43), (1, 42.5), (0, 42), (0, 40), (-1, 39),
          (-2, 38), (-3, 37.5), (-5, 36.5), (-6, 36)]
ITALY = [(9, 44), (10, 44), (12, 44.5), (13, 43.5), (14, 42.5), (15, 41.5),
         (16, 40.5), (18.7, 40.5), (18.7, 39.5), (17, 38.5), (16, 38),
         (16, 39.5), (15, 40.5), (14, 41.5), (13, 42.5), (12, 43.5),
         (11, 44), (9.5, 44)]
SICILY = [(13, 38), (15, 38), (15, 37), (13, 37)]
GREECE = [(22.2, 40), (23, 39.3), (23.2, 38.2), (22.8, 37.2), (22.3, 36.6),
          (21.8, 37.3), (22.1, 38.2), (21.6, 38.9), (21.8, 39.7)]
UK = [(-5, 50.7), (-4, 52.7), (-5, 54.7), (-4, 56.7), (-2, 58.2), (-1, 57.7),
      (0, 55.7), (1, 53.7), (1, 52.2), (0, 51.7), (-2, 51.2), (-4, 50.7),
      (-5, 50.7)]
IRELAND = [(-10, 52), (-9, 54), (-6, 55), (-6, 54), (-8, 52), (-10, 52)]
ICELAND = [(-22, 64), (-18, 66), (-14, 65), (-15, 63), (-19, 63), (-22, 64)]
CASPIAN = [(50, 47), (52, 46), (53.5, 44.5), (54, 42.5), (53.5, 40.5),
           (52.5, 38.5), (51, 37.2), (49.5, 37.5), (48, 39), (47, 41),
           (46.8, 43), (47.5, 45), (48.5, 46.5)]
ARABIA = [(33, 29), (35, 28), (37, 27), (39, 24), (39, 21), (40, 18),
          (42, 15), (43, 12.5), (44, 12.5), (46, 13.5), (48, 14),
          (50, 14.5), (52, 15.5), (54, 16.5), (56, 18), (58, 20),
          (59.5, 22), (59, 23.5), (58, 24.5), (56, 26), (54, 26.5),
          (52, 27.5), (51, 28.5), (50, 29.5), (49, 29), (48, 29),
          (47, 30), (45, 30), (43, 31), (41, 31.5), (39, 32), (37, 31.5),
          (35, 31), (34, 30), (33, 29)]
ASIA = [(28, 41), (33, 41), (38, 41), (41, 43), (44, 44), (47, 45),
        (50, 46), (53, 45), (55, 46), (58, 47), (60, 48), (63, 49),
        (66, 50), (68, 52), (70, 55), (72, 58), (72, 62), (70, 66),
        (68, 69), (68, 72), (70, 73), (73, 74), (76, 74), (80, 73),
        (84, 74), (88, 75), (92, 76), (96, 76), (100, 77), (104, 77),
        (108, 75), (112, 74), (116, 73), (120, 73), (124, 72), (128, 71),
        (132, 71), (136, 71), (140, 72), (144, 72), (148, 71), (152, 70),
        (156, 69), (160, 69), (164, 68), (168, 67), (172, 66), (176, 65),
        (178, 65), (178, 67), (172, 68), (168, 68), (164, 69), (160, 69),
        (156, 66), (152, 62), (148, 60), (144, 59), (141, 58), (138, 56),
        (136, 54), (134, 52), (132, 50), (131, 48), (130, 46), (129, 44),
        (128, 42), (127, 40), (126, 38), (126, 36), (128, 34), (129, 33),
        (127, 34), (126, 36), (124, 37), (122, 38), (121, 36), (120, 34),
        (119, 32), (120, 30), (121, 28), (120, 26), (118, 24), (116, 23),
        (114, 22), (112, 21), (110, 20), (109, 18), (108, 16), (107, 14),
        (106, 11), (105, 9), (104, 7), (102, 5), (100, 3), (99, 2),
        (98, 4), (98, 7), (97, 10), (96, 13), (95, 15), (94, 17),
        (93, 19), (92, 21), (91, 22), (89, 22), (87, 21), (86, 20),
        (84, 19), (82, 17), (81, 15), (80, 12), (79, 9), (77, 8),
        (76, 10), (75, 13), (74, 16), (73, 19), (72, 20), (70, 22),
        (68, 23), (66, 24), (63, 25), (60, 25), (57, 25.5), (55, 26.5),
        (53, 27.5), (51, 29), (50, 29.5), (48, 30), (46, 29.5), (44, 30),
        (42, 31), (40, 32), (38, 33), (36, 34), (35, 32), (34, 30.5),
        (33, 29), (35, 28.5), (36, 29.5), (38, 31), (40, 32), (42, 33),
        (44, 35), (46, 37), (44, 39), (42, 41), (40, 42), (37, 42),
        (34, 41.5), (31, 41), (28, 41)]
SUMATRA = [(95, 5.5), (97, 4), (99, 1), (101, -1), (103, -3), (105, -5),
           (104, -5.5), (102, -4), (100, -1), (98, 2), (95.5, 4.5)]
JAVA = [(105, -6), (108, -6.5), (110, -7), (112, -7.5), (114, -7.8),
        (114, -8.2), (111, -8), (108, -7.8), (105, -7)]
BORNEO = [(109, 1), (110, 2.5), (112, 4), (114, 5), (116, 6.5), (118, 5),
          (119, 2), (118, 0), (117, -2), (115, -3.5), (113, -3.5),
          (111, -2.5), (109, -0.5)]
SULAWESI = [(119, 0.5), (120, 1), (122, 0.5), (123, -0.5), (121, -1.5),
            (120, -3), (119, -5.5), (119, -3), (119.5, -1)]
NEW_GUINEA = [(131, -1), (133, -2), (136, -2.5), (139, -3), (141, -3.5),
              (141, -5), (138, -7), (135, -7), (132, -5), (131, -3)]
PHILIPPINES = [(120, 18), (121, 18.5), (122, 17), (122, 15), (121, 13.5),
               (122, 12), (121, 11), (120, 13), (119, 15), (120, 17)]
SRI_LANKA = [(79.8, 9.5), (81, 8.5), (81, 6.5), (80, 6), (79.8, 8)]
TAIWAN = [(120, 25), (121, 24), (121, 22.5), (120, 23.5)]
HAINAN = [(109, 20), (110.5, 20), (111, 19), (110, 18.5), (109, 19)]
JAPAN = [(130, 31), (131, 33), (133, 34), (135, 34.5), (137, 35),
         (139, 35.5), (140, 37), (141, 39), (141, 41), (140, 42),
         (139, 40), (138, 38), (136, 36), (134, 35), (132, 34), (130, 32)]
AUSTRALIA = [(113, -22), (114, -26), (115, -30), (115, -33), (117, -35),
             (120, -34), (123, -33), (126, -32), (129, -32), (131, -32),
             (133, -32), (135, -33), (137, -35), (139, -37), (140, -38),
             (139, -35), (137, -33), (135, -30), (133, -27), (131, -24),
             (129, -21), (127, -19), (124, -18), (121, -18), (118, -20),
             (115, -21), (113, -22)]

LANDS = [(AFRICA, (111, 127, 58)), (MADAGASCAR, (111, 127, 58)),
         (EUROPE, (122, 138, 68)), (ITALY, (122, 138, 68)),
         (SICILY, (122, 138, 68)), (GREECE, (122, 138, 68)),
         (UK, (122, 138, 68)), (IRELAND, (122, 138, 68)),
         (ICELAND, (122, 138, 68)), (ARABIA, (125, 138, 66)),
         (ASIA, (106, 122, 56)), (SUMATRA, (112, 128, 60)),
         (JAVA, (112, 128, 60)), (BORNEO, (112, 128, 60)),
         (SULAWESI, (112, 128, 60)), (NEW_GUINEA, (112, 128, 60)),
         (PHILIPPINES, (112, 128, 60)), (SRI_LANKA, (106, 122, 56)),
         (TAIWAN, (106, 122, 56)), (HAINAN, (106, 122, 56)),
         (JAPAN, (106, 122, 56)), (AUSTRALIA, (118, 130, 62))]

LAND_OUTLINE = (82, 98, 44)


def _project(lon, lat):
    """Orthographic projection -> (x, y) final px, or None if behind limb."""
    la0 = math.radians(LAT0)
    la = math.radians(lat)
    lo = math.radians(lon - LON0)
    c = math.sin(la0) * math.sin(la) + math.cos(la0) * math.cos(la) * math.cos(lo)
    if c <= 0.02:
        return None
    x = math.cos(la) * math.sin(lo)
    y = math.cos(la0) * math.sin(la) - math.sin(la0) * math.cos(la) * math.cos(lo)
    return (GLOBE_CX + GLOBE_R * x, GLOBE_CY - GLOBE_R * y)


def _densify(poly, step=1.5):
    """Insert interpolated points so limb clipping follows the circle."""
    out = []
    n = len(poly)
    for i in range(n):
        lon0, lat0 = poly[i]
        lon1, lat1 = poly[(i + 1) % n]
        d = max(abs(lon1 - lon0), abs(lat1 - lat0))
        k = max(1, int(d / step))
        for j in range(k):
            t = j / k
            out.append((lon0 + (lon1 - lon0) * t, lat0 + (lat1 - lat0) * t))
    return out


def _project_poly(poly):
    pts = []
    for lon, lat in _densify(poly):
        p = _project(lon, lat)
        if p is not None:
            pts.append(p)
    return pts


def _blend(c1, c2, t):
    return tuple(int(round(c1[i] + (c2[i] - c1[i]) * t)) for i in range(3))


def draw_globe(cv):
    disc = (GLOBE_CX, GLOBE_CY, GLOBE_R)
    # soft shadow under the globe
    cv.fill_circle(GLOBE_CX, GLOBE_CY + 6, GLOBE_R - 6, (0, 0, 0), 46)
    # ocean disc
    cv.fill_circle(GLOBE_CX, GLOBE_CY, GLOBE_R, (28, 64, 102))
    # radial ocean light: concentric discs, centre-light, pre-blended opaque.
    # Drawn largest (darkest) first, smallest (lightest) last.
    for i in range(0, 15):
        t = i / 14.0
        col = _blend((28, 64, 102), (58, 116, 184), t)
        cv.fill_circle(GLOBE_CX, GLOBE_CY, GLOBE_R * (1.0 - t * 0.55),
                       col, clip_disc=disc)
    # limb darkening (opaque pre-blended rings over ocean only)
    for i in range(6):
        t = i / 6.0
        r0 = GLOBE_R - i * 3.0
        col = _blend((16, 38, 66), (28, 64, 102), t)
        cv.ring(GLOBE_CX, GLOBE_CY, r0, 3.0, col)
    # land
    for poly, col in LANDS:
        pts = _project_poly(poly)
        if len(pts) < 3:
            continue
        cv.fill_polygon(pts, col)
        cv.polyline(pts + [pts[0]], 1.0, LAND_OUTLINE)
    # Caspian Sea: true elongated N-S outline, filled with the lightest
    # ocean-disc colour (58,116,184). The top-left light overlay drawn
    # afterwards lifts it to the local ocean tone (~74,124,182), so it
    # blends instead of reading as a dark patch.
    pts = _project_poly(CASPIAN)
    if len(pts) >= 3:
        cv.fill_polygon(pts, (58, 116, 184))
    # soft top-left light over land + ocean (real alpha, clipped to disc)
    for i in range(10, 0, -1):
        t = i / 10.0
        cv.fill_circle(462, 306, 40 + i * 26, (150, 190, 235), 7,
                       clip_disc=disc)
    # rim
    cv.ring(GLOBE_CX, GLOBE_CY, GLOBE_R, 2.0, (143, 184, 221))


# Globe pins: (number, lon, lat, nudge_dx, nudge_dy). Nudges separate the
# dense Europe cluster, matching the reference render's legibility.
PINS = [(1, 114.1, 22.5, 0, 0), (2, 4.3, 52.0, 1, -6),
        (3, 106.8, -6.2, 0, 0), (4, 56.5, 26.5, 0, 0),
        (5, 84.9, 19.3, 0, 0), (6, 30.5, 50.4, 0, 0),
        (7, 8.9, 44.4, -11, 10), (8, 30.7, 36.9, 0, 0),
        (9, 46.7, 24.7, -4, 11)]


def draw_pins(cv):
    for num, lon, lat, dx, dy in PINS:
        p = _project(lon, lat)
        if p is None:
            continue
        x, y = p[0] + dx, p[1] + dy
        cv.fill_circle(x, y, 11.5, (255, 255, 255), 70)
        cv.fill_circle(x, y, 9.5, (178, 44, 44))
        cv.ring(x, y, 9.5, 1.6, (240, 240, 240))
        draw_text(cv, x, y + 4, str(num), 11, (255, 255, 255),
                  weight="bold", align="center")


# ---------------------------------------------------------------- Palette
BG = (7, 11, 23)
BG_GLOW = (12, 19, 34)
IVORY = (242, 234, 216)
GOLD = (217, 164, 65)
AMBER = (232, 179, 74)
WHITE = (238, 238, 238)
SOFT = (205, 210, 218)
DIM = (170, 175, 185)
NAVY_BLD = (22, 35, 61)
NAVY_BLD2 = (18, 29, 52)
WIN_AMBER = (217, 164, 65)
KICK_BLUE = (29, 78, 137)
KICK_GREEN = (46, 110, 58)
KICK_RED = (176, 30, 36)
PIN_RED = (178, 44, 44)
RULE_LIGHT = (140, 170, 200)
BAND_BG = (15, 29, 54)
TABLE = (107, 74, 42)
TABLE_TOP = (140, 100, 60)
SKIN = (232, 195, 154)
SUIT = (26, 42, 74)


def draw_background(cv):
    cv.fill_rect(0, 0, W, H, BG)
    # soft radial glow behind the globe (many small steps: no banding)
    for i in range(32, 0, -1):
        t = i / 32.0
        col = _blend(BG, BG_GLOW, t)
        cv.fill_circle(512, 430, 120 + i * 19, col)
    # stars (seeded, deterministic), kept out of content zones
    rng = random.Random(20261120)
    placed = 0
    tries = 0
    while placed < 110 and tries < 900:
        tries += 1
        x = rng.uniform(8, 1016)
        y = rng.uniform(6, 540)
        if (x - 511) ** 2 + (y - 384) ** 2 < 172 ** 2:
            continue
        if 540 < y < 650:
            continue
        if 100 < y < 235 and 200 < x < 830:
            continue  # keep the summit skyline clean
        r = rng.choice([0.7, 0.9, 1.2])
        a = rng.randint(50, 150)
        cv.fill_circle(x, y, r, (220, 228, 245), a)
        placed += 1


def draw_masthead(cv):
    draw_text(cv, 512, 46, "THE WORLD", 40, IVORY, weight="black",
              align="center", tracking=10, serif=True)
    draw_text(cv, 512, 71, "AT A CROSSROADS", 20, GOLD, weight="bold",
              align="center", tracking=3, serif=True)
    draw_text(cv, 512, 92, "FRIDAY, 20 NOVEMBER 2026", 15, IVORY,
              weight="bold", align="center", tracking=2)
    cv.fill_rect(30, 96, 994, 99, GOLD)


def _building(cv, x0, y0, x1, y1, windows=3):
    cv.fill_rect(x0, y0, x1, y1, NAVY_BLD)
    cv.fill_rect(x0, y0, x1, y0 + 2, (30, 46, 78))
    for i in range(windows):
        wy = y0 + 14 + i * 16
        if wy + 2 > y1 - 6:
            break
        cv.fill_rect(x0 + 8, wy, x1 - 8, wy + 2, WIN_AMBER)


def _flag(cv, px, py, kind):
    """Flag on a pole at (px, py) = pole base; flag hangs at top."""
    cv.thick_line(px, py, px, py - 78, 2.0, (200, 200, 200))
    fx0, fy0 = px + 2, py - 78
    if kind == "US":
        cv.fill_rect(fx0, fy0, fx0 + 30, fy0 + 18, (178, 52, 52))
        for i in range(4):
            cv.fill_rect(fx0, fy0 + i * 4.5, fx0 + 30, fy0 + i * 4.5 + 2.2,
                         WHITE)
        cv.fill_rect(fx0, fy0, fx0 + 13, fy0 + 9, (40, 60, 120))
    elif kind == "CN":
        cv.fill_rect(fx0, fy0, fx0 + 30, fy0 + 18, (200, 40, 40))
        cv.fill_circle(fx0 + 8, fy0 + 9, 3.2, (250, 220, 80))
    elif kind == "RU":
        cv.fill_rect(fx0, fy0, fx0 + 30, fy0 + 6, WHITE)
        cv.fill_rect(fx0, fy0 + 6, fx0 + 30, fy0 + 12, (40, 80, 170))
        cv.fill_rect(fx0, fy0 + 12, fx0 + 30, fy0 + 18, (200, 40, 40))


def _figure(cv, x, hair):
    # head + shoulders behind the table (table top y=186)
    cv.fill_circle(x, 168, 7.5, SKIN)
    cv.fill_circle(x, 165.5, 7.5, hair)  # hair cap over the top half
    cv.fill_circle(x, 168, 7.5, SKIN)    # redraw lower face
    cv.fill_rect(x - 5.5, 171, x + 5.5, 172.5, hair)
    cv.fill_rect(x - 10, 176, x + 10, 186, SUIT)
    cv.fill_polygon([(x - 3, 176), (x + 3, 176), (x, 184)], WHITE)
    cv.fill_rect(x - 1.2, 178, x + 1.2, 186, (178, 40, 40))


def draw_summit(cv):
    _building(cv, 218, 128, 256, 186, 3)
    _building(cv, 264, 112, 302, 186, 4)
    _building(cv, 310, 138, 342, 186, 2)
    _building(cv, 662, 118, 700, 186, 3)
    _building(cv, 708, 132, 746, 186, 3)
    _building(cv, 754, 148, 788, 186, 2)
    _flag(cv, 378, 186, "US")
    _flag(cv, 478, 186, "CN")
    _flag(cv, 608, 186, "RU")
    _figure(cv, 416, (232, 210, 122))   # Trump, blond
    _figure(cv, 510, (28, 24, 20))      # Xi, black
    _figure(cv, 607, (198, 192, 182))   # Putin, grey-blond
    cv.fill_rect(362, 186, 662, 189, TABLE_TOP)
    cv.fill_rect(362, 189, 662, 194, TABLE)
    draw_text(cv, 416, 206, "TRUMP", 10, WHITE, weight="bold", align="center")
    draw_text(cv, 510, 206, "XI JINPING", 10, WHITE, weight="bold",
              align="center")
    draw_text(cv, 607, 206, "PUTIN", 10, WHITE, weight="bold", align="center")
    draw_text(cv, 512, 231,
              "PEACE DECLARATION — BUT NO BREAKTHROUGH ON UKRAINE OR IRAN",
              12, WHITE, weight="normal", align="center", tracking=1)


def draw_cyclone(cv, cx, cy):
    col = (150, 190, 230)
    cv.arc_polyline(cx, cy, 34, 0.4, 4.6, 2.6, col)
    cv.arc_polyline(cx, cy, 24, 1.3, 5.4, 2.4, col)
    cv.arc_polyline(cx, cy, 14, 2.2, 6.0, 2.2, col)
    cv.fill_circle(cx, cy, 3.0, col)
    # rain slashes around the spiral
    for ang in (0.5, 1.4, 2.4, 3.4, 4.4, 5.5):
        x0 = cx + 42 * math.cos(ang)
        y0 = cy + 42 * math.sin(ang)
        cv.thick_line(x0, y0, x0 - 5, y0 + 8, 1.8, (120, 160, 200))


def draw_akvan(cv):
    cv.fill_rect(30, 544, 994, 648, BAND_BG)
    cv.fill_rect(30, 536, 994, 538, RULE_LIGHT)
    cv.fill_rect(30, 638, 994, 640, RULE_LIGHT)
    cv.fill_rect(30, 646, 994, 648, RULE_LIGHT)
    # pin 5
    cv.fill_circle(48, 578, 11.5, (255, 255, 255), 70)
    cv.fill_circle(48, 578, 9.5, PIN_RED)
    cv.ring(48, 578, 9.5, 1.6, (240, 240, 240))
    draw_text(cv, 48, 582, "5", 11, WHITE, weight="bold", align="center")
    draw_cyclone(cv, 130, 592)
    draw_text(cv, 200, 577, "CYCLONE AKVAN MAKES LANDFALL", 26, WHITE,
              weight="bold")
    draw_text(cv, 200, 609,
              "300,000 EVACUATED IN ODISHA — LANDFALL NEAR GOPALPUR, 90–100 KM/H",
              14, AMBER, weight="bold", tracking=-0.65)
    draw_text(cv, 200, 633,
              "Landfall 10–11 AM · 423 rescue teams · 69 trains cancelled",
              11, SOFT, weight="normal")


# ---------------------------------------------------------------- Strip scenes
COLS = [(30, 330), (350, 660), (680, 994)]


def _scene_icj(cv, x0, x1):
    # cream palace with pediment, columns, tents, tiny figures
    cv.fill_rect(x0 + 10, 672, x1 - 10, 703, (232, 221, 192))
    cv.fill_polygon([(150, 660), (210, 660), (180, 672)], (226, 212, 178))
    cv.fill_circle(180, 659, 2.5, GOLD)
    for cx in (70, 120, 170, 220, 270):
        cv.fill_rect(cx - 3, 676, cx + 3, 700, (250, 244, 224))
    cv.fill_rect(x0 + 10, 700, x1 - 10, 703, (200, 186, 152))
    cv.fill_rect(174, 688, 186, 703, (90, 70, 50))
    # tents + figures at the base
    for tx in (52, 252):
        cv.fill_polygon([(tx, 703), (tx + 15, 686), (tx + 30, 703)],
                        (120, 130, 150))
    for fx in (105, 135, 228):
        cv.fill_circle(fx, 693, 2.0, (60, 50, 45))
        cv.thick_line(fx, 695, fx, 702, 2.0, (60, 50, 45))


def _scene_jakarta(cv, x0, x1):
    # dark-blue parliament, gold dome, Indonesian flag on the roof,
    # gold scales of justice on the facade
    cv.fill_rect(x0 + 10, 668, x1 - 10, 703, (28, 47, 85))
    cv.fill_rect(x0 + 10, 668, x1 - 10, 673, (38, 62, 110))
    # gold dome (upper half-disc only)
    dome = [(505 + 22 * math.cos(math.pi + i * math.pi / 20),
             668 + 22 * math.sin(math.pi + i * math.pi / 20))
            for i in range(21)]
    cv.fill_polygon(dome, (200, 170, 80))
    cv.thick_line(505, 646, 505, 640, 2.0, GOLD)
    cv.fill_circle(505, 638, 2.5, GOLD)
    # columns + door
    for cx in (392, 432, 578, 618):
        cv.fill_rect(cx - 2, 676, cx + 2, 700, (58, 92, 140))
    cv.fill_rect(497, 684, 513, 703, (16, 26, 52))
    # Indonesian flag on the roof (pole foot touches the roof)
    cv.thick_line(382, 668, 382, 646, 2.0, (200, 200, 200))
    cv.fill_rect(384, 648, 404, 654, (200, 40, 40))
    cv.fill_rect(384, 654, 404, 660, (245, 245, 245))
    # gold scales on the facade
    sx, sy = 600, 678
    cv.thick_line(sx, sy, sx, sy + 20, 2.0, GOLD)
    cv.thick_line(sx - 12, sy + 4, sx + 12, sy + 4, 2.0, GOLD)
    cv.fill_circle(sx, sy + 4, 2.2, GOLD)
    for px in (sx - 12, sx + 12):
        cv.thick_line(px, sy + 4, px - 4, sy + 12, 1.6, GOLD)
        cv.thick_line(px, sy + 4, px + 4, sy + 12, 1.6, GOLD)
        cv.fill_polygon([(px - 5, sy + 12), (px + 5, sy + 12),
                         (px, sy + 17)], GOLD)


def _scene_hormuz(cv, x0, x1):
    # dark sea, distant ship silhouette, tanker sitting in the water,
    # fire + smoke that stays inside the scene (below the red rule)
    cv.fill_rect(x0, 668, x1, 703, (20, 45, 80))
    for wy in (678, 688, 698):
        cv.thick_line(x0 + 6, wy, x1 - 6, wy, 1.4, (60, 110, 170), 160)
    # distant ship silhouette
    cv.fill_rect(700, 678, 745, 686, (60, 70, 90))
    cv.fill_rect(720, 672, 728, 678, (60, 70, 90))
    # tanker hull (bow to the right, sitting deep in the water)
    cv.fill_polygon([(800, 686), (950, 686), (962, 692), (956, 702),
                     (800, 702)], (120, 50, 40))
    cv.fill_rect(800, 686, 956, 689, (150, 66, 52))
    # portholes
    for px in (820, 845, 870):
        cv.fill_circle(px, 694, 1.8, (40, 25, 20))
    # superstructure + funnel (sits on the hull top at y=686)
    cv.fill_rect(905, 672, 945, 686, (235, 235, 235))
    cv.fill_rect(915, 666, 925, 672, (90, 90, 95))
    # fire above the tanker (peaks stay clear of the red rule at 654-656)
    cv.fill_polygon([(910, 672), (918, 658), (926, 672)], (230, 120, 30))
    cv.fill_polygon([(914, 672), (919, 663), (924, 672)], (240, 200, 60))
    cv.fill_polygon([(880, 672), (886, 661), (892, 672)], (230, 120, 30))
    # smoke puffs drifting right from the fire — tops stay below y=657
    for (sx, sy, sr) in ((924, 664, 4), (934, 662, 3.5), (914, 666, 3.5)):
        cv.fill_circle(sx, sy, sr, (140, 140, 145), 220)
    # small red flag at the stern
    cv.thick_line(958, 684, 958, 664, 1.6, (200, 200, 200))
    cv.fill_rect(948, 664, 958, 670, (200, 40, 40))
    # wake under the hull (hull sits in the water, bottom edge y=702)
    cv.thick_line(795, 700, 832, 700, 1.6, (150, 190, 230), 200)
    cv.thick_line(845, 701, 880, 701, 1.6, (150, 190, 230), 200)


def draw_strips(cv):
    rules = [KICK_BLUE, KICK_GREEN, KICK_RED]
    scenes = [_scene_icj, _scene_jakarta, _scene_hormuz]
    for (x0, x1), rule, scene in zip(COLS, rules, scenes):
        cv.fill_rect(x0, 654, x1, 657, rule)
        scene(cv, x0, x1)
    # kicker bars (width = text + padding)
    kickers = [("2 THE HAGUE · JUSTICE", KICK_BLUE),
               ("3 JAKARTA · INDONESIA", KICK_GREEN),
               ("4 STRAIT OF HORMUZ · ENERGY", KICK_RED)]
    for (x0, x1), (txt, col) in zip(COLS, kickers):
        tw = text_width(txt, 11, "bold")
        bw = tw + 16
        cv.fill_rect(x0, 705, x0 + bw, 720, col)
        draw_text(cv, x0 + 8, 716, txt, 11, WHITE, weight="bold")
    # headlines (2 lines, balanced wrap) + decks (2 lines)
    heads = ["ICJ — Myanmar guilty of Rohingya genocide",
             "Indonesia passes asset forfeiture law",
             "Tanker ablaze after mine strike in Hormuz"]
    decks = ["The Hague rules 9–6: Myanmar guilty of genocide.",
             "DPR passes the bill after 18 years. In force in 12 months.",
             "A tanker burns east of the strait after hitting a mine."]
    for (x0, x1), head, deck in zip(COLS, heads, decks):
        lines = wrap_balanced(head, 20, "bold", x1 - x0 - 4)
        draw_text(cv, x0, 754, lines[0], 20, WHITE, weight="bold")
        if len(lines) > 1:
            draw_text(cv, x0, 776, lines[1], 20, WHITE, weight="bold")
        dlines = wrap_balanced(deck, 12, "normal", x1 - x0 - 4)
        draw_text(cv, x0, 799, dlines[0], 12, SOFT, weight="normal")
        if len(dlines) > 1:
            draw_text(cv, x0, 812, dlines[1], 12, SOFT, weight="normal")
    cv.fill_rect(30, 819, 994, 821, WHITE)


# ---------------------------------------------------------------- ALSO TODAY
ALSO_COLS = [40, 282, 523, 764]
ALSO_ITEMS = [
    [("6 KYIV", "Ballistic missiles hit Kyiv"),
     ("7 GENOA", "Drone shuts Genoa airport 4h"),
     ("8 COP31", "Draft faces final test, no deal"),
     ("9 HOUTHI", "Claims strikes on 4 Saudi targets")],
    [("10 IRAN", "Trump delays decision to 2027"),
     ("11 EUROPE", "Allies ready for Russia talks"),
     ("12 VARMA", "India judge resigns amid graft case"),
     ("13 CYBER", "Bank data leaked; cyber chief out")],
    [("14 GAZA", "Ground op ends; Hezbollah hit"),
     ("15 ANDROMEDA", "First direct look at star merger"),
     ("16 PETE ROSE", "Posthumous pardon for Pete Rose"),
     ("17 SPORT", "NZ 368 all out; India bat, day 2")],
]


def draw_also(cv):
    cv.fill_rect(30, 819, 32, 951, WHITE)     # left border
    cv.fill_rect(992, 819, 994, 951, WHITE)   # right border
    cv.fill_rect(30, 949, 994, 951, WHITE)    # bottom border
    draw_text(cv, 40, 836, "ALSO TODAY — 20 NOVEMBER 2026", 14, GOLD,
              weight="bold")
    cv.fill_rect(30, 841, 994, 843, GOLD)
    for row, (kbase, dbase) in enumerate(((860, 875), (895, 910),
                                         (930, 945))):
        for (kick, deck), cx in zip(ALSO_ITEMS[row], ALSO_COLS):
            draw_text(cv, cx, kbase, kick, 14, GOLD, weight="bold")
            draw_text(cv, cx, dbase, deck, 10.5, WHITE, weight="normal")


def draw_datecheck(cv):
    cv.fill_rect(30, 957, 994, 996, (0, 0, 0))
    x = 40
    w1 = draw_text(cv, x, 973, "DATE CHECK — ", 11, AMBER, weight="bold")
    draw_text(cv, x + w1, 973,
              "The Shenzhen summit, ICJ verdict and Indonesia asset law "
              "were decided Thu 19 Nov;", 11, WHITE, weight="normal")
    draw_text(cv, x, 987,
              "their consequences led Friday 20 Nov 2026 news. Every other "
              "story here happened or was first reported Fri 20 Nov.",
              11, WHITE, weight="normal")


def draw_footer(cv):
    draw_text(cv, 30, 1007,
              "Sources: IMD, Reuters, NYT, TASS/AFP, DPR RI, AP, BBC. "
              "Original drawings.", 9, DIM, weight="normal")
    draw_text(cv, 994, 1007, "THE WORLD AT A CROSSROADS", 9, GOLD,
              weight="bold", align="right")


def add_grain(cv):
    rng = random.Random(777)
    for _ in range(2600):
        x = rng.uniform(0, W)
        y = rng.uniform(0, H)
        a = rng.randint(5, 16)
        col = (255, 255, 255) if rng.random() < 0.5 else (0, 0, 0)
        cv.fill_circle(x, y, 0.55, col, a)


def main():
    cv = Canvas()
    draw_background(cv)
    draw_masthead(cv)
    draw_summit(cv)
    draw_globe(cv)
    draw_pins(cv)
    draw_akvan(cv)
    draw_strips(cv)
    draw_also(cv)
    draw_datecheck(cv)
    draw_footer(cv)
    add_grain(cv)
    rgb = cv.downsample()
    save_png(OUT_PATH, rgb, W, H)


if __name__ == "__main__":
    main()
