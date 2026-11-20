#!/usr/bin/env python3
"""news-image-20261120 -- THE WORLD AT A CROSSROADS.

One 1024x1024 PNG summing up Friday 20 November 2026 world news:
Shenzhen trilateral summit, ICJ Rohingya verdict, Indonesia asset
forfeiture law, Cyclone Akvan landfall, Hormuz tanker fire, plus
12 ALSO TODAY items. Drawn from scratch with stdlib only: a raw
RGB canvas, a hand-made 5x7 bitmap font, an orthographic globe
built from hand-approximated continent polygons, and a manual PNG
encoder (zlib). No network, no files read, fully deterministic.
"""

import math
import os
import struct
import sys
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- palette
BG = (9, 13, 32)          # midnight blue page
BG2 = (13, 19, 44)        # slightly lighter panel
PANEL = (17, 26, 56)      # band background
PANEL2 = (22, 32, 66)
IVORY = (238, 232, 212)   # warm ivory text
WHITE = (246, 246, 240)
MUTED = (170, 178, 198)   # secondary text
AMBER = (232, 178, 62)    # gold accent
GOLD = (205, 158, 58)
DARKGOLD = (150, 110, 40)
RED = (182, 44, 44)       # pin red
DARKRED = (128, 26, 26)
KBLUE = (44, 84, 152)     # kicker blue
KGREEN = (38, 122, 80)    # kicker green
KRED = (160, 44, 44)      # kicker red
OCEAN_HI = (46, 96, 140)  # globe ocean, lit centre
OCEAN_LO = (18, 44, 84)   # globe ocean, limb
LAND = (99, 124, 60)      # globe land olive
LAND_HI = (116, 142, 74)
RIM = (150, 180, 215)     # globe rim
RULE = (120, 142, 182)    # thin rules
SKIN = (232, 195, 154)
SKIN2 = (214, 172, 128)
SUIT = (24, 30, 52)
SUIT2 = (34, 40, 66)
STEEL = (28, 38, 68)      # skyline buildings
CREAM = (230, 222, 196)
INK = (20, 22, 30)

# ---------------------------------------------------------------- canvas
PIX = bytearray(W * H * 3)


def _set(x, y, c):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        PIX[i] = c[0]
        PIX[i + 1] = c[1]
        PIX[i + 2] = c[2]


def fill_rect(x0, y0, x1, y1, c):
    """Fill [x0,x1) x [y0,y1) with colour c (clipped)."""
    if x0 < 0:
        x0 = 0
    if y0 < 0:
        y0 = 0
    if x1 > W:
        x1 = W
    if y1 > H:
        y1 = H
    if x1 <= x0 or y1 <= y0:
        return
    r, g, b = c
    for y in range(y0, y1):
        base = (y * W + x0) * 3
        for x in range(x1 - x0):
            i = base + x * 3
            PIX[i] = r
            PIX[i + 1] = g
            PIX[i + 2] = b


def hline(x0, x1, y, c, w=1):
    for k in range(w):
        fill_rect(x0, y + k, x1, y + k + 1, c)


def vline(x, y0, y1, c, w=1):
    for k in range(w):
        fill_rect(x + k, y0, x + k + 1, y1, c)


def line(x0, y0, x1, y1, c, w=1):
    """Bresenham line with square brush of width w."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    half = w // 2
    while True:
        fill_rect(x - half, y - half, x - half + w, y - half + w, c)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def circle(cx, cy, r, c):
    """Filled circle."""
    if r <= 0:
        return
    for dy in range(-r, r + 1):
        dx = int(math.sqrt(r * r - dy * dy))
        fill_rect(cx - dx, cy + dy, cx + dx + 1, cy + dy + 1, c)


def ring(cx, cy, r0, r1, c):
    """Filled ring r0 <= d < r1."""
    for dy in range(-r1, r1 + 1):
        dx1 = int(math.sqrt(r1 * r1 - dy * dy))
        if abs(dy) < r0:
            dx0 = int(math.sqrt(r0 * r0 - dy * dy))
            fill_rect(cx - dx1, cy + dy, cx - dx0, cy + dy + 1, c)
            fill_rect(cx + dx0 + 1, cy + dy, cx + dx1 + 1, cy + dy + 1, c)
        else:
            fill_rect(cx - dx1, cy + dy, cx + dx1 + 1, cy + dy + 1, c)


def ellipse(cx, cy, rx, ry, c):
    if rx <= 0 or ry <= 0:
        return
    for dy in range(-ry, ry + 1):
        t = 1.0 - (dy * dy) / float(ry * ry)
        dx = int(rx * math.sqrt(t)) if t > 0 else 0
        fill_rect(cx - dx, cy + dy, cx + dx + 1, cy + dy + 1, c)


def poly_fill(pts, c):
    """Scanline even-odd fill of a polygon [(x,y), ...]."""
    if len(pts) < 3:
        return
    ys = [p[1] for p in pts]
    y0, y1 = min(ys), max(ys)
    n = len(pts)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            if (ay <= y < by) or (by <= y < ay):
                t = (y - ay) / float(by - ay)
                xs.append(ax + t * (bx - ax))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            fill_rect(int(xs[k]), y, int(xs[k + 1]) + 1, y + 1, c)


def arc(cx, cy, r, a0, a1, c, w=2):
    """Arc from angle a0 to a1 (radians, 0 = east, ccw positive in
    math sense, y down so visually clockwise)."""
    steps = max(4, int(abs(a1 - a0) * r))
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        x = int(cx + r * math.cos(a))
        y = int(cy - r * math.sin(a))
        fill_rect(x - w // 2, y - w // 2, x - w // 2 + w, y - w // 2 + w, c)


def blend(c1, c2, t):
    """Linear blend c1->c2, t in [0,1]."""
    return (int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


def _r(v):
    """Round-half-up to int (deterministic, unlike banker's round)."""
    return int(v + 0.5)


# ---------------------------------------------------------------- PNG out
def _chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def encode_png():
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += PIX[y * W * 3:(y + 1) * W * 3]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += _chunk(b"IEND", b"")
    return png

# ---------------------------------------------------------------- font
# Hand-made 5x7 bitmap font. Each glyph is 7 rows of 5 bits.
# Uppercase, lowercase, digits and the punctuation this page needs.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "a": ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    "b": ("10000", "10000", "11110", "10001", "10001", "10001", "11110"),
    "c": ("00000", "00000", "01110", "10000", "10000", "10001", "01110"),
    "d": ("00001", "00001", "01111", "10001", "10001", "10001", "01111"),
    "e": ("00000", "00000", "01110", "10001", "11111", "10000", "01110"),
    "f": ("00110", "01001", "01000", "11110", "01000", "01000", "01000"),
    "g": ("00000", "01111", "10001", "10001", "01111", "00001", "01110"),
    "h": ("10000", "10000", "11110", "10001", "10001", "10001", "10001"),
    "i": ("00000", "00100", "00000", "01100", "00100", "00100", "01110"),
    "j": ("00010", "00000", "00110", "00010", "00010", "10010", "01100"),
    "k": ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    "l": ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    "m": ("00000", "00000", "11010", "10101", "10101", "10101", "10101"),
    "n": ("00000", "00000", "11110", "10001", "10001", "10001", "10001"),
    "o": ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    "p": ("00000", "11110", "10001", "10001", "11110", "10000", "10000"),
    "q": ("00000", "01111", "10001", "10001", "01111", "00001", "00001"),
    "r": ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    "s": ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    "t": ("01000", "01000", "11110", "01000", "01000", "01000", "00100"),
    "u": ("00000", "00000", "10001", "10001", "10001", "10011", "01101"),
    "v": ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    "w": ("00000", "00000", "10001", "10001", "10101", "10101", "01010"),
    "x": ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    "y": ("00000", "00000", "10001", "10001", "01111", "00001", "01110"),
    "z": ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ";": ("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '"': ("01010", "01010", "01010", "00000", "00000", "00000", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "*": ("00000", "00100", "10101", "01110", "10101", "00100", "00000"),
    "#": ("01010", "01010", "11111", "01010", "11111", "01010", "01010"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
}

# Em dash and middle dot are full-cell marks of their own.
FONT["\u2014"] = ("00000", "00000", "00000", "11111", "11111", "00000", "00000")
FONT["\u00b7"] = ("00000", "00000", "00000", "01100", "01100", "00000", "00000")

# Normalise lookalike punctuation onto the glyphs above.
_NORM = {
    "\u2013": "-",   # en dash
    "\u2019": "'",   # right single quote
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00a0": " ",
    "\u2026": ".",
}


def _adv(px, tr):
    return _r(6 * px) + tr


def text_w(s, px, tr=0):
    """Pixel width of s at horizontal glyph scale px."""
    s = "".join(_NORM.get(ch, ch) for ch in s)
    if not s:
        return 0
    return len(s) * _adv(px, tr) - tr


def _glyph(x, y, gl, px, py, c):
    for r in range(7):
        row = gl[r]
        if "1" not in row:
            continue
        y0 = y + _r(r * py)
        y1 = y + _r((r + 1) * py)
        if y1 <= y0:
            continue
        for col in range(5):
            if row[col] == "1":
                x0 = x + _r(col * px)
                x1 = x + _r((col + 1) * px)
                if x1 > x0:
                    fill_rect(x0, y0, x1, y1, c)


def text(x, y, s, px, py, c, tr=0, bold=False, align=None):
    """Draw s with top-left (x, y). align: None/left, 'center', 'right'
    positions x as the anchor instead."""
    s = "".join(_NORM.get(ch, ch) for ch in s)
    if align == "center":
        x -= text_w(s, px, tr) // 2
    elif align == "right":
        x -= text_w(s, px, tr)
    adv = _adv(px, tr)
    cx = x
    for ch in s:
        gl = FONT.get(ch)
        if gl is not None:
            _glyph(cx, y, gl, px, py, c)
            if bold:
                _glyph(cx + 1, y, gl, px, py, c)
        cx += adv
    return cx

# ---------------------------------------------------------------- globe
# Hand-approximated continent outlines in (lat, lon). Coarse on purpose:
# at globe scale 1 degree is under 3 px, so these read clearly as
# Europe, Africa, the Middle East, India, SE Asia and East Asia.
# They were sketched from memory of a world map, not traced from data.
AFRICA = [
    (35, -6), (37, 10), (34, 11), (32, 20), (31, 30), (31, 32),
    (27, 33), (22, 36), (18, 38), (15, 40), (11, 43), (11, 48),
    (10, 51), (5, 46), (2, 41), (-1, 40), (-4, 39), (-10, 40),
    (-15, 40), (-18, 36), (-22, 35), (-26, 33), (-29, 32), (-33, 27),
    (-34, 20), (-32, 18), (-29, 17), (-25, 15), (-20, 13), (-17, 12),
    (-12, 13), (-8, 13), (-4, 12), (0, 9), (4, 9), (6, 5), (6, 2),
    (5, -3), (4, -8), (7, -11), (10, -14), (12, -16), (15, -16),
    (17, -16), (20, -17), (24, -16), (27, -13), (30, -10), (33, -8),
]
EUROPE = [
    (43, -9), (37, -9), (36, -6), (38, -1), (40, 0), (42, 3),
    (43, 7), (44, 8), (45, 12), (44, 15), (42, 16), (40, 16),
    (39, 16), (40, 19), (42, 19), (44, 19), (45, 20), (46, 23),
    (44, 29), (46, 30), (47, 32), (50, 30), (52, 33), (55, 33),
    (58, 30), (60, 28), (62, 30), (65, 30), (68, 32), (70, 30),
    (68, 28), (65, 25), (62, 22), (60, 19), (58, 18), (56, 16),
    (55, 13), (54, 10), (55, 8), (57, 8), (58, 6), (60, 5),
    (62, 6), (60, 8), (58, 10), (57, 12), (55, 12), (54, 8),
    (52, 5), (51, 3), (50, 1), (49, -1), (48, -4), (47, -2),
    (46, -1), (44, -1), (43, -2),
]
BRITAIN = [
    (50, -5), (51, -3), (53, -3), (55, -2), (57, -2), (58, -4),
    (57, -6), (54, -6), (52, -6), (50, -5),
]
ARABIA = [
    (30, 35), (29, 39), (27, 42), (24, 46), (22, 48), (19, 50),
    (17, 54), (16, 53), (15, 50), (13, 48), (12, 44), (13, 43),
    (16, 42), (18, 41), (21, 39), (24, 38), (27, 36), (29, 35),
]
TURKEY_IRAN = [
    (36, 26), (36, 30), (36, 36), (38, 39), (39, 41), (41, 41),
    (42, 44), (41, 46), (39, 48), (38, 48), (36, 50), (36, 54),
    (37, 54), (38, 56), (35, 57), (31, 57), (28, 57), (26, 57),
    (25, 58), (25, 61), (27, 63), (29, 66), (30, 62), (31, 58),
    (32, 54), (33, 50), (34, 47), (35, 44), (36, 41), (36, 36),
    (36, 30),
]
INDIA = [
    (25, 66), (24, 68), (22, 69), (20, 72), (18, 73), (15, 74),
    (13, 75), (10, 77), (8, 77), (9, 79), (11, 80), (13, 80),
    (15, 80), (17, 83), (19, 85), (21, 87), (22, 89), (23, 89),
    (24, 88), (26, 88), (28, 88), (28, 84), (28, 80), (27, 77),
    (28, 74), (27, 70), (26, 68),
]
SEASIA = [
    (28, 88), (24, 93), (20, 93), (16, 94), (12, 93), (9, 96),
    (8, 98), (6, 100), (3, 101), (1, 103), (1, 104), (5, 103),
    (8, 101), (10, 99), (12, 100), (14, 101), (17, 102), (20, 105),
    (22, 107), (21, 109), (18, 109), (14, 109), (11, 109), (10, 106),
    (12, 103), (15, 101), (18, 100), (21, 98), (24, 94), (27, 90),
]
SIBERIA = [
    (50, 30), (52, 33), (55, 35), (58, 40), (60, 45), (62, 50),
    (64, 55), (66, 60), (68, 65), (70, 70), (72, 75), (73, 80),
    (73, 90), (74, 100), (73, 110), (72, 120), (71, 130), (70, 140),
    (69, 150), (68, 160), (66, 170), (65, 178), (64, 175), (62, 170),
    (60, 165), (58, 162), (55, 158), (52, 155), (50, 150), (48, 145),
    (46, 140), (44, 135), (42, 130), (40, 125), (38, 122), (36, 120),
    (34, 118), (32, 116), (30, 114), (28, 112), (26, 110), (24, 108),
    (23, 106), (24, 104), (26, 102), (28, 100), (30, 98), (32, 96),
    (34, 94), (36, 92), (38, 90), (40, 88), (42, 86), (44, 84),
    (46, 82), (48, 80), (50, 78), (52, 75), (54, 72), (55, 68),
    (54, 65), (53, 62), (52, 58), (51, 55), (50, 50), (49, 45),
    (48, 40), (47, 35), (46, 32), (48, 30),
]
EASTASIA = [
    (22, 108), (23, 110), (22, 112), (21, 113), (23, 116), (25, 118),
    (27, 120), (29, 121), (31, 121), (33, 120), (35, 119), (37, 120),
    (38, 122), (39, 122), (40, 122), (41, 123), (42, 124), (43, 126),
    (44, 128), (45, 130), (46, 132), (47, 134), (48, 135), (50, 137),
    (52, 138), (53, 140), (54, 141), (55, 141), (56, 140), (58, 140),
    (60, 142), (62, 144), (64, 146), (66, 148), (68, 150), (70, 152),
    (70, 155), (68, 158), (66, 160), (64, 162), (62, 163), (60, 162),
    (58, 160), (56, 158), (54, 156), (52, 154), (50, 152), (48, 150),
    (46, 148), (44, 146), (42, 144), (40, 142), (38, 140), (36, 138),
    (34, 136), (32, 134), (30, 132), (28, 130), (26, 128), (24, 126),
    (22, 124), (20, 122), (20, 120), (22, 118), (23, 116),
]
SUMATRA = [
    (6, 95), (3, 97), (0, 100), (-3, 103), (-5, 105), (-6, 106),
    (-4, 105), (-2, 102), (1, 99), (4, 96),
]
JAVA = [
    (-6, 106), (-7, 108), (-7, 110), (-8, 112), (-8, 114), (-7, 114),
    (-6, 111), (-6, 108),
]
BORNEO = [
    (4, 117), (2, 115), (1, 110), (-1, 111), (-3, 114), (-4, 116),
    (-2, 117), (0, 118), (2, 118),
]
NEWGUINEA = [
    (0, 131), (-1, 133), (-2, 136), (-4, 138), (-6, 140), (-8, 140),
    (-8, 137), (-6, 134), (-4, 132), (-2, 131),
]
JAPAN = [
    (31, 130), (33, 132), (34, 134), (35, 136), (37, 139), (39, 141),
    (41, 141), (43, 143), (44, 144), (42, 143), (39, 140), (36, 137),
    (34, 133), (32, 131),
]
AUSTRALIA_NW = [
    (-12, 130), (-14, 129), (-16, 128), (-19, 127), (-22, 126),
    (-25, 124), (-25, 120), (-22, 117), (-19, 116), (-16, 118),
    (-14, 121), (-12, 125), (-11, 128),
]
LAND_POLYS = [AFRICA, EUROPE, BRITAIN, ARABIA, TURKEY_IRAN, INDIA,
              SEASIA, SIBERIA, EASTASIA, SUMATRA, JAVA, BORNEO,
              NEWGUINEA, JAPAN, AUSTRALIA_NW]

# 1-degree land mask over lat -60..86, lon -180..180.
LAT0, LAT1, LON0, LON1 = -60, 86, -180, 181
_GW = LON1 - LON0
_GH = LAT1 - LAT0


def _build_land_mask():
    mask = bytearray(_GW * _GH)
    for poly in LAND_POLYS:
        for r in range(_GH):
            y = LAT0 + r + 0.5
            xs = []
            n = len(poly)
            for i in range(n):
                alat, alon = poly[i]
                blat, blon = poly[(i + 1) % n]
                if (alat <= y < blat) or (blat <= y < alat):
                    t = (y - alat) / float(blat - alat)
                    xs.append(alon + t * (blon - alon))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                c0 = _r(xs[k] - LON0)
                c1 = _r(xs[k + 1] - LON0)
                for c in range(max(0, c0), min(_GW, c1 + 1)):
                    mask[r * _GW + c] = 1
    return mask


LAND_MASK = _build_land_mask()


def _is_land(lat, lon):
    r = int(lat - LAT0)
    c = int(lon - LON0)
    if r < 0:
        r = 0
    if r >= _GH:
        r = _GH - 1
    c %= _GW
    return LAND_MASK[r * _GW + c] == 1


# Orthographic projection, centre 60E / 20N.
C_LAT = 20.0
C_LON = 60.0
_SIN0 = math.sin(math.radians(C_LAT))
_COS0 = math.cos(math.radians(C_LAT))
GCX, GCY, GR = 512, 366, 148


def project(lat, lon):
    """lat/lon -> globe pixel (x, y) or None if on the far side."""
    phi = math.radians(lat)
    dlam = math.radians(lon - C_LON)
    cosc = _SIN0 * math.sin(phi) + _COS0 * math.cos(phi) * math.cos(dlam)
    if cosc <= 0:
        return None
    x = GCX + GR * math.cos(phi) * math.sin(dlam)
    y = GCY - GR * (_COS0 * math.sin(phi) - _SIN0 * math.cos(phi) * math.cos(dlam))
    return (int(x + 0.5), int(y + 0.5))


def draw_globe():
    for py in range(GCY - GR, GCY + GR + 1):
        dy = py - GCY
        for px in range(GCX - GR, GCX + GR + 1):
            dx = px - GCX
            d2 = dx * dx + dy * dy
            if d2 > GR * GR:
                continue
            rho = math.sqrt(d2) / GR
            cc = math.asin(min(1.0, rho))
            cosc = math.cos(cc)
            yn = -dy / float(GR)  # north, -1..1
            sinphi = cosc * _SIN0 + yn * _COS0
            if sinphi > 1.0:
                sinphi = 1.0
            if sinphi < -1.0:
                sinphi = -1.0
            phi = math.asin(sinphi)
            denom = cosc * _COS0 - yn * _SIN0
            dlam = math.atan2(dx / float(GR), denom)
            lat = math.degrees(phi)
            lon = C_LON + math.degrees(dlam)
            # ocean: brighter toward the lit centre, darker at the limb
            t = 1.0 - rho * rho
            ocean = blend(OCEAN_LO, OCEAN_HI, 0.25 + 0.75 * t)
            if _is_land(lat, lon):
                # subtle patchiness so land is not one flat slab
                v = ((px * 31 + py * 17) % 11)
                land = LAND_HI if v < 3 else LAND
                _set(px, py, blend(land, OCEAN_LO, 0.18 * (1.0 - t)))
            else:
                _set(px, py, ocean)
    # top-left sheen arc and rim
    arc(GCX, GCY, GR - 4, 0.55, 2.35, (120, 170, 220), 3)
    ring(GCX, GCY, GR - 1, GR + 1, RIM)


PINS = [
    (1, 22.5, 114.1), (2, 52.0, 4.3), (3, -6.2, 106.8),
    (4, 26.5, 56.5), (5, 19.3, 84.9), (6, 50.4, 30.5),
    (7, 44.4, 8.9), (8, 36.9, 30.7), (9, 24.7, 46.7),
]


def draw_pin(x, y, num, r=11):
    circle(x, y, r, DARKRED)
    circle(x, y, r - 2, RED)
    ring(x, y, r - 2, r, (240, 240, 235))
    text(x, y - 7, str(num), 1.5, 2, WHITE, bold=True, align="center")


def draw_pins():
    for num, lat, lon in PINS:
        p = project(lat, lon)
        if p is not None:
            draw_pin(p[0], p[1], num)

# ---------------------------------------------------------------- scenes
def draw_stars():
    # deterministic sparse stars, kept out of the text bands
    for i in range(90):
        x = (i * 173 + 41) % W
        y = (i * 97 + 13) % H
        if y < 96 or (y > 210 and y < 500 and (x < 320 or x > 700)):
            if (i % 3) == 0:
                _set(x, y, (150, 160, 190))
            elif (i % 3) == 1:
                _set(x, y, (110, 122, 155))


def draw_masthead():
    text(512, 4, "THE WORLD", 8, 7, IVORY, tr=2, bold=True, align="center")
    text(512, 56, "AT A CROSSROADS", 4, 3, AMBER, tr=1, bold=True,
         align="center")
    text(512, 79, "FRIDAY, 20 NOVEMBER 2026", 2, 2.5, IVORY, tr=1,
         align="center")
    hline(28, 996, 101, GOLD, 3)


def _flag_us(x, y):
    fill_rect(x, y, x + 30, y + 18, (178, 34, 34))
    for k in range(3):
        fill_rect(x, y + 2 + k * 6, x + 30, y + 4 + k * 6, WHITE)
    fill_rect(x, y, x + 13, y + 9, (36, 54, 120))
    for fy in (y + 2, y + 5):
        for fx in (x + 2, x + 6, x + 10):
            _set(fx, fy, WHITE)


def _flag_cn(x, y):
    fill_rect(x, y, x + 30, y + 18, (196, 30, 30))
    fill_rect(x + 3, y + 3, x + 8, y + 8, (240, 210, 60))
    for fx, fy in ((x + 12, y + 2), (x + 14, y + 6), (x + 12, y + 10),
                   (x + 9, y + 12)):
        _set(fx, fy, (240, 210, 60))
        _set(fx + 1, fy, (240, 210, 60))


def _flag_ru(x, y):
    fill_rect(x, y, x + 30, y + 6, WHITE)
    fill_rect(x, y + 6, x + 30, y + 12, (30, 80, 180))
    fill_rect(x, y + 12, x + 30, y + 18, (178, 34, 34))


def _figure(cx, hair, tie):
    # head, hair cap, suit torso; stands behind the podium bar
    circle(cx, 148, 9, SKIN)
    # hair
    for dx in range(-9, 10):
        dy = int(math.sqrt(max(0, 81 - dx * dx)))
        fill_rect(cx + dx, 148 - dy, cx + dx + 1, 148 - dy + 4, hair)
    fill_rect(cx - 13, 158, cx + 14, 173, SUIT)
    fill_rect(cx - 4, 158, cx + 5, 173, WHITE)
    poly_fill([(cx - 3, 159), (cx + 4, 159), (cx, 172)], tie)
    fill_rect(cx - 13, 158, cx + 14, 160, SUIT2)


def draw_summit():
    # night skyline behind the leaders
    for (bx, by, bw, bh) in ((208, 128, 42, 52), (262, 112, 44, 68),
                             (318, 134, 34, 46), (672, 118, 46, 62),
                             (730, 130, 40, 50), (790, 140, 30, 40)):
        fill_rect(bx, by, bx + bw, by + bh, STEEL)
        for wy in range(by + 8, by + bh - 6, 12):
            fill_rect(bx + 6, wy, bx + bw - 6, wy + 2, (200, 170, 90))
    # flags on poles above each leader
    for (cx, fn) in ((390, _flag_us), (512, _flag_cn), (634, _flag_ru)):
        vline(cx + 32, 106, 152, (150, 150, 150), 2)
        fn(cx + 2, 108)
    # three leaders
    _figure(390, (210, 180, 110), (178, 40, 40))
    _figure(512, (30, 28, 26), (178, 40, 40))
    _figure(634, (190, 180, 165), (40, 40, 60))
    # podium bar
    fill_rect(300, 172, 724, 179, (96, 72, 40))
    hline(300, 724, 172, GOLD, 1)
    text(390, 184, "TRUMP", 1.5, 2, WHITE, bold=True, align="center")
    text(512, 184, "XI JINPING", 1.5, 2, WHITE, bold=True, align="center")
    text(634, 184, "PUTIN", 1.5, 2, WHITE, bold=True, align="center")
    text(512, 200, "PEACE DECLARATION \u2014 BUT NO BREAKTHROUGH "
         "ON UKRAINE OR IRAN", 1.7, 2, IVORY, align="center")


def draw_cyclone(cx, cy):
    # spiral: three broken arcs + rain slashes
    arc(cx, cy, 38, 0.3, 4.4, (150, 190, 225), 3)
    arc(cx, cy, 27, 1.2, 5.6, (180, 210, 235), 3)
    arc(cx, cy, 16, 2.0, 6.0, (220, 235, 245), 3)
    circle(cx, cy, 5, (220, 235, 245))
    for (sx, sy) in ((cx - 46, cy - 22), (cx + 40, cy - 30),
                     (cx - 42, cy + 26), (cx + 46, cy + 20)):
        line(sx, sy, sx - 6, sy + 12, (140, 175, 215), 2)


def draw_akvan():
    fill_rect(28, 520, 996, 616, PANEL)
    hline(28, 996, 520, (90, 140, 200), 2)
    hline(28, 996, 614, (90, 140, 200), 2)
    # pin 5 sits at the band's left edge, as in the reference
    draw_pin(30, 568, 5, r=12)
    draw_cyclone(108, 568)
    text(180, 530, "CYCLONE AKVAN MAKES LANDFALL", 3, 4, WHITE,
         tr=3, bold=True)
    text(180, 568, "300,000 EVACUATED IN ODISHA \u2014 LANDFALL "
         "NEAR GOPALPUR, 90\u2013100 KM/H", 1.5, 2, AMBER, bold=True)
    text(180, 594, "Landfall 10\u201311 AM \u00b7 423 rescue teams "
         "\u00b7 69 trains cancelled", 1, 2, IVORY)

STRIP_X = (28, 356, 684)
STRIP_W = 312


def _vignette_icj(x0):
    y0 = 622
    fill_rect(x0, y0, x0 + STRIP_W, y0 + 48, (206, 198, 172))
    # ICJ palace: cream block, pediments, columns
    fill_rect(x0 + 8, y0 + 22, x0 + STRIP_W - 8, y0 + 48, CREAM)
    fill_rect(x0 + 8, y0 + 18, x0 + STRIP_W - 8, y0 + 23, (196, 186, 158))
    poly_fill([(x0 + 120, y0 + 2), (x0 + 160, y0 + 18),
               (x0 + 200, y0 + 2)], (214, 204, 176))
    poly_fill([(x0 + 30, y0 + 10), (x0 + 58, y0 + 18),
               (x0 + 86, y0 + 10)], (214, 204, 176))
    poly_fill([(x0 + 234, y0 + 10), (x0 + 262, y0 + 18),
               (x0 + 290, y0 + 10)], (214, 204, 176))
    for cx in (x0 + 40, x0 + 76, x0 + 112, x0 + 148, x0 + 184,
               x0 + 220, x0 + 256, x0 + 292):
        fill_rect(cx - 3, y0 + 24, cx + 3, y0 + 48, (196, 186, 158))
    # two small tents + figures in front, with dignity
    poly_fill([(x0 + 96, y0 + 40), (x0 + 106, y0 + 28),
               (x0 + 116, y0 + 40)], (120, 128, 140))
    poly_fill([(x0 + 196, y0 + 40), (x0 + 206, y0 + 28),
               (x0 + 216, y0 + 40)], (120, 128, 140))
    for fx in (x0 + 130, x0 + 140, x0 + 180):
        circle(fx, y0 + 34, 2, (90, 70, 55))
        fill_rect(fx - 2, y0 + 36, fx + 3, y0 + 44, (70, 80, 110))


def _scales(cx, y0):
    # gold scales of justice
    vline(cx, y0 + 4, y0 + 40, GOLD, 2)
    hline(cx - 16, cx + 17, y0 + 8, GOLD, 2)
    circle(cx, y0 + 4, 2, GOLD)
    line(cx - 16, y0 + 8, cx - 16, y0 + 20, GOLD, 1)
    line(cx + 16, y0 + 8, cx + 16, y0 + 20, GOLD, 1)
    poly_fill([(cx - 22, y0 + 20), (cx - 10, y0 + 20), (cx - 16, y0 + 28)],
              GOLD)
    poly_fill([(cx + 10, y0 + 20), (cx + 22, y0 + 20), (cx + 16, y0 + 28)],
              GOLD)
    fill_rect(cx - 14, y0 + 38, cx + 15, y0 + 40, GOLD)


def _vignette_jakarta(x0):
    y0 = 622
    fill_rect(x0, y0, x0 + STRIP_W, y0 + 48, (24, 36, 72))
    # parliament block with gold dome
    fill_rect(x0 + 20, y0 + 26, x0 + 220, y0 + 48, (40, 56, 104))
    fill_rect(x0 + 20, y0 + 22, x0 + 220, y0 + 26, (52, 70, 122))
    ellipse(x0 + 120, y0 + 24, 22, 11, GOLD)
    fill_rect(x0 + 118, y0 + 10, x0 + 122, y0 + 15, GOLD)
    for cx in (x0 + 48, x0 + 88, x0 + 152, x0 + 192):
        fill_rect(cx - 3, y0 + 28, cx + 3, y0 + 48, (120, 140, 190))
    # Indonesian flag on a pole at the left
    vline(x0 + 8, y0 + 8, y0 + 44, (200, 200, 200), 2)
    fill_rect(x0 + 10, y0 + 8, x0 + 34, y0 + 15, (200, 40, 40))
    fill_rect(x0 + 10, y0 + 15, x0 + 34, y0 + 22, WHITE)
    _scales(x0 + 268, y0 + 4)


def _vignette_hormuz(x0):
    y0 = 622
    fill_rect(x0, y0, x0 + STRIP_W, y0 + 48, (14, 34, 66))
    fill_rect(x0, y0 + 30, x0 + STRIP_W, y0 + 48, (20, 52, 92))
    # distant ship on the horizon
    fill_rect(x0 + 36, y0 + 24, x0 + 66, y0 + 30, (60, 76, 100))
    fill_rect(x0 + 44, y0 + 18, x0 + 52, y0 + 24, (60, 76, 100))
    # burning tanker, right of centre
    fill_rect(x0 + 150, y0 + 28, x0 + 268, y0 + 40, (52, 44, 40))
    fill_rect(x0 + 210, y0 + 16, x0 + 238, y0 + 28, (70, 60, 52))
    fill_rect(x0 + 214, y0 + 8, x0 + 220, y0 + 16, (90, 78, 66))
    # flame
    poly_fill([(x0 + 196, y0 + 18), (x0 + 206, y0 + 2),
               (x0 + 214, y0 + 12), (x0 + 222, y0 + 4),
               (x0 + 230, y0 + 18)], (232, 130, 40))
    poly_fill([(x0 + 204, y0 + 18), (x0 + 210, y0 + 8),
               (x0 + 218, y0 + 18)], (245, 200, 80))
    # smoke drifting up-right, clear of the deck
    circle(x0 + 232, y0 + 2, 7, (110, 112, 118))
    circle(x0 + 246, y0 + 6, 9, (96, 98, 104))
    circle(x0 + 262, y0 + 2, 7, (84, 86, 92))
    # waves
    for wy in (y0 + 42, y0 + 46):
        for wx in range(x0 + 6, x0 + STRIP_W - 6, 18):
            hline(wx, wx + 10, wy, (90, 140, 190), 1)


STRIPS = [
    (KBLUE, "2 THE HAGUE \u00b7 JUSTICE",
     ("ICJ \u2014 Myanmar guilty", "of Rohingya genocide"),
     ("The Hague rules 9\u20136:", "Myanmar guilty of genocide."),
     _vignette_icj),
    (KGREEN, "3 JAKARTA \u00b7 INDONESIA",
     ("Indonesia passes", "asset forfeiture law"),
     ("DPR passes the bill after 18", "years. In force in 12 months."),
     _vignette_jakarta),
    (KRED, "4 STRAIT OF HORMUZ \u00b7 ENERGY",
     ("Tanker ablaze after", "mine strike in Hormuz"),
     ("A tanker burns east of the", "strait after hitting a mine."),
     _vignette_hormuz),
]


def draw_strips():
    for i, (bar, kicker, head, deck, scene) in enumerate(STRIPS):
        x0 = STRIP_X[i]
        scene(x0)
        fill_rect(x0, 674, x0 + STRIP_W, 692, bar)
        text(x0 + 8, 678, kicker, 1.5, 2, WHITE, bold=True)
        text(x0, 698, head[0], 2, 3, WHITE, tr=1, bold=True)
        text(x0, 722, head[1], 2, 3, WHITE, tr=1, bold=True)
        text(x0, 756, deck[0], 1.3, 2, IVORY)
        text(x0, 774, deck[1], 1.3, 2, IVORY)


ALSO = [
    ("6 KYIV", "Ballistic missiles hit Kyiv"),
    ("7 GENOA", "Drone shuts Genoa airport 4h"),
    ("8 COP31", "Draft faces final test, no deal"),
    ("9 HOUTHI", "Claims strikes on 4 Saudi targets"),
    ("10 IRAN", "Trump delays decision to 2027"),
    ("11 EUROPE", "Allies ready for Russia talks"),
    ("12 VARMA", "India judge resigns amid graft case"),
    ("13 CYBER", "Bank data leaked; cyber chief out"),
    ("14 GAZA", "Ground op ends; Hezbollah hit"),
    ("15 ANDROMEDA", "First direct look at star merger"),
    ("16 PETE ROSE", "Posthumous pardon for Pete Rose"),
    ("17 SPORT", "NZ 368 all out; India bat, day 2"),
]


def draw_also():
    fill_rect(28, 812, 996, 814, IVORY)
    fill_rect(28, 950, 996, 952, IVORY)
    fill_rect(28, 812, 30, 952, IVORY)
    fill_rect(994, 812, 996, 952, IVORY)
    text(40, 820, "ALSO TODAY \u2014 20 NOVEMBER 2026", 1.8, 2, AMBER,
         bold=True)
    hline(40, 984, 842, GOLD, 2)
    colx = (40, 280, 520, 760)
    rowy = (850, 882, 914)
    for idx, (kick, deck) in enumerate(ALSO):
        col = idx % 4
        row = idx // 4
        y = rowy[row]
        text(colx[col], y, kick, 2, 2, AMBER, bold=True)
        text(colx[col], y + 16, deck, 1, 2, IVORY)


def draw_datecheck_footer():
    text(28, 958, "DATE CHECK \u2014 ", 1.3, 2, AMBER, bold=True)
    x = 28 + text_w("DATE CHECK \u2014 ", 1.3)
    text(x, 958, "The Shenzhen summit, ICJ verdict and Indonesia "
         "asset law were decided Thu 19 Nov;", 1.3, 2, IVORY)
    text(28, 974, "their consequences led Friday 20 Nov 2026 news. "
         "Every other story here happened or was first reported "
         "Fri 20 Nov.", 1.3, 2, IVORY)
    text(28, 996, "Sources: IMD, Reuters, NYT, TASS/AFP, DPR RI, "
         "AP, BBC. Original drawings.", 1, 2, MUTED)
    text(996, 996, "THE WORLD AT A CROSSROADS", 1.5, 2, AMBER,
         bold=True, align="right")


def render():
    fill_rect(0, 0, W, H, BG)
    draw_stars()
    draw_masthead()
    draw_summit()
    draw_globe()
    draw_pins()
    draw_akvan()
    draw_strips()
    draw_also()
    draw_datecheck_footer()
    return encode_png()


def main():
    if len(sys.argv) > 1:
        out = sys.argv[1]
    elif os.environ.get("MAKEFUN_OUTPUT_DIR"):
        out = os.path.join(os.environ["MAKEFUN_OUTPUT_DIR"], "entry.png")
    else:
        out = "/output/entry.png"
    parent = os.path.dirname(out)
    if parent:
        os.makedirs(parent, exist_ok=True)
    data = render()
    with open(out, "wb") as f:
        f.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
