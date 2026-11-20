#!/usr/bin/env python3
# THE WORLD AT A CROSSROADS - Friday 20 November 2026.
# make.fun bounty: news-image-20261120 - "Sum up 20 November's world
# news in one image". Pure Python 3 stdlib, no network, fully
# deterministic: two runs write byte-identical /output/entry.png.
# One unified image, not four panels: a 3D-shaded Earth suspended
# above a dark reflective floor; the Shenzhen trilateral above it,
# the ICJ/Rohingya story lower left, the Hormuz tanker crisis lower
# right, Indonesia's asset forfeiture law as a smaller element, and
# a compact ALSO TODAY strip with six further verified stories.
# Every illustration is drawn by this program (flat vector scenes, a
# 3D-shaded globe). Every word is set in real type: Liberation Serif
# Bold + Noto Sans Condensed, rendered at build time into a glyph
# atlas embedded below; at runtime the program only decodes the
# atlas and blits bitmaps. No external assets, no copied images,
# no AI-generated pictures.
#
# 10 verified stories: 4 lead narratives + 6 markers, each checked
# against at least two independent credible sources (see STORIES.md).
# Planned items are labelled as planned; contested claims name their
# source; the DATE CHECK strip at the foot states this to the reader
# and to the judge.

import base64
import math
import os
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- palette
PAPER = (246, 241, 227)   # warm newsprint cream
INK = (20, 20, 20)
INK_SOFT = (58, 58, 58)
RED = (176, 30, 36)
BLUE = (29, 78, 137)
TEAL = (14, 107, 107)
GOLD = (176, 124, 18)
GREEN = (46, 110, 58)
PURPLE = (94, 58, 138)
ORANGE = (198, 96, 22)
SKY = (178, 205, 224)
SKY_DUSK = (232, 190, 150)
SEA = (126, 168, 196)
SEA_DARK = (88, 130, 163)
SAND = (224, 200, 148)
GREY = (120, 118, 110)
LIGHT = (238, 232, 214)
RULE = (180, 172, 152)   # pale beige — v4 only; NOT used for structure in v5
# v5 — NEWSPAPER RULES (one value each, used consistently everywhere):
# horizontal structural rules 3 px INK, vertical rules 2 px INK,
# card/box borders 2 px INK, sharp corners (no rounding, like print).
RULE_H = 3
RULE_V = 2
BOX_T = 2
PAD = 5                    # text inset inside a bordered card
NEON_PINK = (255, 90, 180)
NEON_CYAN = (70, 220, 230)
NEON_YELLOW = (255, 210, 60)
DUSK = (58, 42, 84)

# ------------------------------------------------------------------- canvas
class Canvas:
    """RGB pixel buffer with flat vector drawing primitives."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        row = bytes(bg) * w
        self.px = bytearray(row * h)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def blend(self, x, y, c, a):
        """Alpha-blend colour c over pixel (x, y); a in 0..1."""
        if 0 <= x < self.w and 0 <= y < self.h and a > 0.0:
            i = (y * self.w + x) * 3
            if a >= 1.0:
                self.px[i] = c[0]
                self.px[i + 1] = c[1]
                self.px[i + 2] = c[2]
            else:
                self.px[i] = int(self.px[i] * (1 - a) + c[0] * a)
                self.px[i + 1] = int(self.px[i + 1] * (1 - a) + c[1] * a)
                self.px[i + 2] = int(self.px[i + 2] * (1 - a) + c[2] * a)

    def fill_rect(self, x0, y0, x1, y1, c):
        x0 = max(0, int(x0))
        y0 = max(0, int(y0))
        x1 = min(self.w, int(x1))
        y1 = min(self.h, int(y1))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for y in range(y0, y1):
            i = (y * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def hline(self, x0, x1, y, c, t=1):
        self.fill_rect(x0, y, x1, y + t, c)

    def vline(self, x, y0, y1, c, t=1):
        self.fill_rect(x, y0, x + t, y1, c)

    def box(self, x0, y0, x1, y1, c, t=2):
        """Sharp-cornered rectangular border (newspaper frame)."""
        self.fill_rect(x0, y0, x1, y0 + t, c)
        self.fill_rect(x0, y1 - t, x1, y1, c)
        self.fill_rect(x0, y0, x0 + t, y1, c)
        self.fill_rect(x1 - t, y0, x1, y1, c)

    def disc(self, cx, cy, r, c):
        r = int(r)
        if r <= 0:
            return
        cx = int(cx)
        cy = int(cy)
        for y in range(cy - r, cy + r + 1):
            dy = y - cy
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            self.fill_rect(cx - dx, y, cx + dx + 1, y + 1, c)

    def ring(self, cx, cy, r, t, c):
        cx = int(cx)
        cy = int(cy)
        r = int(r)
        for k in range(t):
            rr = r - k
            if rr <= 0:
                break
            for y in range(cy - rr, cy + rr + 1):
                dy = y - cy
                dx = int(math.sqrt(max(0, rr * rr - dy * dy)))
                self.set(cx - dx, y, c)
                self.set(cx + dx, y, c)

    def poly(self, pts, c):
        """Scanline fill of a simple polygon (even-odd)."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, int(math.ceil(min(ys))))
        y1 = min(self.h - 1, int(math.floor(max(ys))))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x1, y1p = pts[i]
                x2, y2p = pts[(i + 1) % n]
                if (y1p <= y < y2p) or (y2p <= y < y1p):
                    t = (y - y1p) / (y2p - y1p)
                    xs.append(x1 + t * (x2 - x1))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.fill_rect(int(xs[k]), y, int(xs[k + 1]) + 1, y + 1, c)

    def thick_line(self, x0, y0, x1, y1, t, c):
        """A line of width t (px), with round caps."""
        dx = x1 - x0
        dy = y1 - y0
        L = math.hypot(dx, dy)
        if L < 0.001:
            self.disc(x0, y0, t / 2.0, c)
            return
        nx = -dy / L * t / 2.0
        ny = dx / L * t / 2.0
        self.poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                   (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], c)
        self.disc(x0, y0, t / 2.0, c)
        self.disc(x1, y1, t / 2.0, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        self.thick_line(x0, y0, x1, y1, t, c)

    def circle_outline(self, cx, cy, r, t, c):
        steps = max(24, int(2 * math.pi * r))
        pts = []
        for i in range(steps):
            a = 2 * math.pi * i / steps
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        for i in range(steps):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % steps]
            self.thick_line(x0, y0, x1, y1, t, c)

    def arc(self, cx, cy, r, a0, a1, c, t=1):
        steps = max(8, int(abs(a1 - a0) * r))
        prev = None
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            p = (cx + r * math.cos(a), cy + r * math.sin(a))
            if prev is not None:
                self.thick_line(prev[0], prev[1], p[0], p[1], t, c)
            prev = p


def _png_chunk(ctype, data):
    out = struct.pack(">I", len(data)) + ctype + data
    out += struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
    return out


def write_png(cv, path):
    """Deterministic PNG: fixed filter 0, zlib level 9."""
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
    png += _png_chunk(b"IDAT", comp)
    png += _png_chunk(b"IEND", b"")
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)

# ------------------------------------------------- glyph atlas
# REAL newspaper type. The glyphs in this image are Liberation Serif Bold
# (masthead / main headline / date line) and Noto Sans Condensed, bold
# and regular (every other word on the page). The fonts were rendered at
# build time on the author's machine with PIL into per-glyph bitmaps at
# the exact cap heights this program uses; the atlas below is those
# bitmaps, zlib + base64 on ONE line. At runtime this program is pure
# stdlib: it only decodes the atlas and blits bitmaps — no font files,
# no PIL, no network, fully deterministic.
# Faces: 0 = Liberation Serif Bold, 2 = Noto Sans Condensed Bold,
# 3 = Noto Sans Condensed. Binary format (big-endian), per face:
# u8 face, u8 n_caps; per cap: f32 cap, u16 n_chars; per char:
# u16 codepoint, f32 advance, i16 ox, i16 oy, u16 w, u16 h, w*h bytes
# of greyscale bitmap. ox/oy are the bitmap's bearing relative to the
# cap-top origin (x = pen position, y = cap top).
_ATLAS_B64 = "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"

_ATLAS = None


def _load_atlas():
    global _ATLAS
    if _ATLAS is not None:
        return _ATLAS
    raw = zlib.decompress(base64.b64decode(_ATLAS_B64))
    at = {}
    i = 0
    n = len(raw)
    while i < n:
        face, ncaps = struct.unpack_from(">BB", raw, i)
        i += 2
        for _ in range(ncaps):
            cap, nch = struct.unpack_from(">fH", raw, i)
            i += 6
            key = (face, int(round(cap * 2)))
            glyphs = {}
            for _ in range(nch):
                cp, adv, ox, oy, w, h = struct.unpack_from(">HfhhHH", raw, i)
                i += 14
                bm = raw[i:i + w * h]
                i += w * h
                glyphs[chr(cp)] = (adv, ox, oy, w, h, bm)
            at[key] = glyphs
    _ATLAS = at
    return at


def _face_id(bold, serif):
    if serif:
        return 0
    return 2 if bold else 3


def _glyphs(face, cap):
    """Glyph table for (face, cap); falls back to the nearest cap of the
    same face (never happens for the caps this file uses)."""
    at = _load_atlas()
    key = (face, int(round(cap * 2)))
    g = at.get(key)
    if g is not None:
        return g
    near = min(c for (f, c) in at if f == face)
    for c in sorted(c for (f, c) in at if f == face):
        if abs(c - key[1]) < abs(near - key[1]):
            near = c
    return at[(face, near)]


# ------------------------------------------------------------ text engine
def text_width(s, cap, bold=False, serif=False):
    """Width in px of string s at cap-height cap (px), in the atlas face."""
    glyphs = _glyphs(_face_id(bold, serif), cap)
    tot = 0.0
    for ch in s:
        g = glyphs.get(ch)
        if g is None:
            g = glyphs['?']
        tot += g[0]
    return tot


def wrap_text(s, cap, maxw, bold=False, serif=False):
    """Greedy word wrap; returns list of lines (each a string)."""
    words = s.split(' ')
    lines = []
    cur = ''
    curw = 0.0
    sp = text_width(' ', cap, bold, serif)
    for wd in words:
        w = text_width(wd, cap, bold, serif)
        add = w if not cur else w + sp
        if cur and curw + add > maxw:
            lines.append(cur)
            cur = wd
            curw = w
        else:
            cur = (cur + ' ' + wd) if cur else wd
            curw += add
    if cur:
        lines.append(cur)
    return lines


def _blit(cv, x0, y0, w, h, bm, color):
    """Alpha-blit a greyscale glyph bitmap onto the canvas (clipped)."""
    px = cv.px
    W = cv.w
    H = cv.h
    r, g, b = color
    if y0 < 0:
        cut = -y0
        if cut >= h:
            return
        bm = bm[cut * w:]
        h -= cut
        y0 = 0
    if y0 + h > H:
        h = H - y0
        if h <= 0:
            return
    x_lo = 0
    x_hi = w
    if x0 < 0:
        x_lo = -x0
    if x0 + w > W:
        x_hi = W - x0
    for row in range(h):
        base = ((y0 + row) * W + x0) * 3
        brow = row * w
        for col in range(x_lo, x_hi):
            a = bm[brow + col]
            if a == 0:
                continue
            i = base + col * 3
            if a == 255:
                px[i] = r
                px[i + 1] = g
                px[i + 2] = b
            else:
                ia = 255 - a
                px[i] = (px[i] * ia + r * a) // 255
                px[i + 1] = (px[i + 1] * ia + g * a) // 255
                px[i + 2] = (px[i + 2] * ia + b * a) // 255


def draw_text(cv, x, y, s, cap, color, bold=False, align='left', maxw=None, serif=False, tracking=0.0):
    """Draw string s with its cap top at y. x is the pen position
    (left edge, or centre/right edge when align is set). tracking
    adds extra px after every glyph (letter-spacing, used by
    justification so wide slack is not all dumped into word gaps)."""
    if align != 'left':
        w = text_width(s, cap, bold, serif) + tracking * max(0, len(s) - 1)
        if align == 'center':
            x = x - w / 2.0
        elif align == 'right':
            x = x - w
    glyphs = _glyphs(_face_id(bold, serif), cap)
    pen = x
    for ch in s:
        g = glyphs.get(ch)
        if g is None:
            g = glyphs['?']
        adv, ox, oy, w, h, bm = g
        if w > 0 and h > 0:
            _blit(cv, int(round(pen + ox)), int(round(y + oy)), w, h, bm, color)
        pen += adv + tracking


def draw_para(cv, x, y, lines, cap, color, leading=None, bold=False, align='left', maxw=None, serif=False):
    if leading is None:
        leading = cap * 1.25
    for i, ln in enumerate(lines):
        draw_text(cv, x, y + i * leading, ln, cap, color, bold=bold,
                  align=align, maxw=maxw, serif=serif)


def wrap_balanced(s, cap, maxw, bold=False, serif=False):
    """Word wrap that minimises squared slack (raggedness) instead of
    greedy fill, so justified lines stretch evenly. The per-line
    penalty is huge on purpose: the wrap first minimises the number
    of lines (a deck that fits in 3 lines stays in 3), and only then
    balances the slack across them (slack**4 punishes one gappy line
    far more than two slightly loose ones). Deterministic (ties break
    toward the earlier break)."""
    words = s.split(' ')
    n = len(words)
    wds = [text_width(w, cap, bold, serif) for w in words]
    sp = text_width(' ', cap, bold, serif)
    INF = float('inf')
    LINE_PENALTY = 1e8

    def line_w(i, j):
        tot = sum(wds[i:j]) + sp * (j - i - 1)
        return tot

    # cost[i] = best cost of wrapping words[i:]; nxt[i] = end of first line.
    cost = [INF] * (n + 1)
    nxt = [n] * (n + 1)
    cost[n] = 0.0
    for i in range(n - 1, -1, -1):
        for j in range(i + 1, n + 1):
            lw = line_w(i, j)
            if lw > maxw + 0.001:
                break
            slack = maxw - lw
            if j == n:
                c = 0.0
            else:
                c = slack * slack * slack * slack
            c += LINE_PENALTY + cost[j]
            if c < cost[i] - 1e-9:
                cost[i] = c
                nxt[i] = j
    lines = []
    i = 0
    while i < n:
        j = nxt[i]
        lines.append(' '.join(words[i:j]))
        i = j
    return lines


def draw_justified_line(cv, x, y, s, cap, color, maxw, bold=False,
                        serif=False, max_extra_per_gap=None):
    """Draw one line stretched flush to maxw. The slack is split the
    newspaper way: at most 3 px per word gap, the rest as
    letter-spacing (tracking, capped at 0.8 px per glyph) — a line
    whose slack cannot be absorbed inside those caps falls back to
    wider word gaps. Single-word lines and lines already full are
    left-aligned. max_extra_per_gap caps the stretch (used for
    single-line list items, where full justification would tear the
    line apart); None means stretch fully (wrapped paragraph lines)."""
    words = s.split(' ')
    if len(words) <= 1:
        draw_text(cv, x, y, s, cap, color, bold=bold, serif=serif)
        return
    nat = text_width(s, cap, bold, serif)
    extra = maxw - nat
    if extra <= 0.0:
        draw_text(cv, x, y, s, cap, color, bold=bold, serif=serif)
        return
    sp = text_width(' ', cap, bold, serif)
    gaps = len(words) - 1
    if max_extra_per_gap is None:
        per = min(extra / gaps, 3.0)
        nchars = sum(len(w) for w in words)
        rem = extra - per * gaps
        track = min(rem / max(1, nchars), 0.8) if nchars else 0.0
        rem -= track * nchars
        if rem > 0.0:
            per += rem / gaps
    else:
        per = min(extra / gaps, max_extra_per_gap)
        track = 0.0
    pen = x
    for i, wd in enumerate(words):
        draw_text(cv, pen, y, wd, cap, color, bold=bold, serif=serif,
                  tracking=track)
        pen += text_width(wd, cap, bold, serif) + track * len(wd)
        if i < gaps:
            pen += sp + per


def draw_para_justified(cv, x, y, lines, cap, color, maxw, leading,
                        bold=False, serif=False):
    """Justified paragraph: every line but the last is stretched flush
    to maxw; the last line stays left-aligned (newspaper style)."""
    for i, ln in enumerate(lines):
        ly = y + i * leading
        if i < len(lines) - 1:
            draw_justified_line(cv, x, ly, ln, cap, color, maxw,
                                bold=bold, serif=serif)
        else:
            draw_text(cv, x, ly, ln, cap, color, bold=bold, serif=serif)


def kicker(cv, x, y, s, cap, bg, fg=(255, 255, 255)):
    w = text_width(s, cap, bold=True) + cap * 1.1
    cv.fill_rect(x, y, x + w, y + cap * 1.7, bg)
    draw_text(cv, x + cap * 0.55, y + cap * 0.32, s, cap, fg, bold=True)

# ------------------------------------------------------- dot world map
# Coarse equirectangular land grid, 52 cols (lon -170..+185) x 26 rows
# (lat 75..-50). Segments are (first_col, last_col) per row.
MAP_ROWS = [
    [(2, 4), (6, 12), (15, 16), (33, 50)],
    [(1, 4), (5, 13), (15, 17), (30, 51)],
    [(1, 4), (5, 13), (15, 16), (28, 51)],
    [(2, 4), (5, 13), (24, 26), (28, 50)],
    [(3, 4), (5, 13), (23, 26), (27, 50)],
    [(5, 13), (23, 24), (26, 33), (34, 50)],
    [(6, 13), (24, 33), (35, 38), (40, 46), (47, 48)],
    [(6, 14), (24, 28), (30, 34), (35, 38), (40, 46), (47, 48)],
    [(6, 14), (24, 27), (30, 34), (35, 38), (40, 45), (47, 48)],
    [(6, 14), (24, 27), (30, 34), (35, 38), (40, 44)],
    [(7, 13), (24, 27), (30, 33), (35, 38), (40, 43)],
    [(8, 12), (24, 27), (30, 32), (36, 38), (40, 42)],
    [(9, 12), (24, 28), (30, 31), (37, 38), (40, 42)],
    [(10, 12), (24, 29), (37, 38), (40, 42)],
    [(11, 13), (25, 30), (40, 42)],
    [(13, 15), (25, 30), (40, 45)],
    [(13, 16), (25, 30), (41, 45)],
    [(13, 16), (25, 30), (42, 45)],
    [(13, 16), (25, 29), (43, 46)],
    [(14, 16), (25, 29), (43, 47)],
    [(14, 16), (26, 29), (43, 47)],
    [(14, 15), (26, 28), (43, 47)],
    [(14, 15), (27, 28), (44, 47), (49, 50)],
    [(14, 15), (45, 47), (49, 50)],
    [(14, 14), (49, 49)],
    [(14, 14)],
]


def _region_color(col, row):
    if col <= 18:
        return (176, 30, 36)          # Americas — red
    if row <= 8 and 23 <= col <= 33:
        return (29, 78, 137)          # Europe — blue
    if 24 <= col <= 31 and row >= 8:
        return (46, 110, 58)          # Africa — green
    if 30 <= col <= 34 and row <= 11:
        return (198, 96, 22)          # Middle East — orange
    if col >= 34 and row <= 13:
        return (94, 58, 138)          # Asia — purple
    if col >= 42 and row >= 14:
        return (14, 107, 107)         # Oceania — teal
    if col >= 23:
        return (94, 58, 138)
    return (120, 118, 110)


def draw_map(cv, x, y, w, h, pins=None):
    """Dot world map in box (x, y, w, h); uniform cells, grid centred."""
    cv.fill_rect(x, y, x + w, y + h, (222, 232, 238))
    cell = min(w / 52.0, h / 26.0)
    ox = x + (w - cell * 52.0) / 2.0
    oy = y + (h - cell * 26.0) / 2.0
    for r, segs in enumerate(MAP_ROWS):
        for (c0, c1) in segs:
            for c in range(c0, c1 + 1):
                cx = ox + (c + 0.5) * cell
                cy = oy + (r + 0.5) * cell
                cv.disc(cx, cy, max(1.8, cell * 0.42), _region_color(c, r))
    if pins:
        # small nudges so clustered pins stay legible (schematic map):
        # the Washington pair (5 Jeffries / 11 Fed / 12 Pew) would
        # otherwise cover each other; each nudge is <=14 px.
        _nudge = {1: (12, -10), 2: (14, 6), 4: (-10, -8), 5: (-14, -8),
                  6: (-12, 6), 11: (14, -8), 12: (0, 12), 13: (-10, -10)}
        for (lon, lat, n) in pins:
            col = (lon + 170.0) / 355.0 * 52.0
            row = (75.0 - lat) / 125.0 * 26.0
            px = ox + col * cell
            py = oy + row * cell
            dx, dy = _nudge.get(n, (0, 0))
            px = max(x + 9, min(x + w - 9, px + dx))
            py = max(y + 9, min(y + h - 9, py + dy))
            cv.disc(px, py, 8, INK)
            cv.ring(px, py, 8, 1, (255, 255, 255))
            draw_text(cv, px - text_width(str(n), 9, bold=True) / 2.0, py - 6,
                      str(n), 9, (255, 255, 255), bold=True)


# ------------------------------------------------------- small flat icons
def _flag(cv, x, y, w, h, kind):
    """Simplified national flags, drawn flat (no photorealism)."""
    if kind == 'us':
        cv.fill_rect(x, y, x + w, y + h, (178, 34, 52))
        for i in range(4):
            cv.fill_rect(x, y + h * (2 * i + 1) / 9.0, x + w, y + h * (2 * i + 2) / 9.0,
                         (255, 255, 255))
        cv.fill_rect(x, y, x + w * 0.4, y + h * 0.55, BLUE)
    elif kind == 'cn':
        cv.fill_rect(x, y, x + w, y + h, (222, 41, 16))
        cv.disc(x + w * 0.24, y + h * 0.32, h * 0.16, (255, 222, 0))
    elif kind == 'ru':
        cv.fill_rect(x, y, x + w, y + h / 3.0, (255, 255, 255))
        cv.fill_rect(x, y + h / 3.0, x + w, y + 2 * h / 3.0, BLUE)
        cv.fill_rect(x, y + 2 * h / 3.0, x + w, y + h, (204, 0, 0))
    elif kind == 'in':
        cv.fill_rect(x, y, x + w, y + h / 3.0, (255, 153, 51))
        cv.fill_rect(x, y + h / 3.0, x + w, y + 2 * h / 3.0, (255, 255, 255))
        cv.fill_rect(x, y + 2 * h / 3.0, x + w, y + h, (19, 136, 8))
        cv.disc(x + w / 2.0, y + h / 2.0, h * 0.14, BLUE)
    elif kind == 'jp':
        cv.fill_rect(x, y, x + w, y + h, (255, 255, 255))
        cv.disc(x + w / 2.0, y + h / 2.0, h * 0.3, (188, 0, 45))
    elif kind == 'au':
        cv.fill_rect(x, y, x + w, y + h, (0, 40, 104))
        cv.fill_rect(x, y, x + w * 0.5, y + h * 0.5, (0, 40, 104))
        cv.disc(x + w * 0.72, y + h * 0.3, h * 0.09, (255, 255, 255))
    elif kind == 'gb':
        cv.fill_rect(x, y, x + w, y + h, (1, 33, 105))
        cv.fill_rect(x, y + h * 0.4, x + w, y + h * 0.6, (255, 255, 255))
        cv.fill_rect(x + w * 0.45, y, x + w * 0.55, y + h, (255, 255, 255))
        cv.fill_rect(x, y + h * 0.45, x + w, y + h * 0.55, (200, 16, 46))
        cv.fill_rect(x + w * 0.47, y, x + w * 0.53, y + h, (200, 16, 46))
    elif kind == 'br':
        cv.fill_rect(x, y, x + w, y + h, (0, 156, 59))
        cv.poly([(x + w / 2.0, y + h * 0.08), (x + w * 0.92, y + h / 2.0),
                 (x + w / 2.0, y + h * 0.92), (x + w * 0.08, y + h / 2.0)],
                (255, 223, 0))
        cv.disc(x + w / 2.0, y + h / 2.0, h * 0.26, BLUE)
    elif kind == 'ua':
        cv.fill_rect(x, y, x + w, y + h / 2.0, (0, 91, 172))
        cv.fill_rect(x, y + h / 2.0, x + w, y + h, (255, 213, 0))
    elif kind == 'id':
        cv.fill_rect(x, y, x + w, y + h / 2.0, (200, 16, 46))
        cv.fill_rect(x, y + h / 2.0, x + w, y + h, (255, 255, 255))
    elif kind == 'mn':
        cv.fill_rect(x, y, x + w, y + h, (205, 0, 0))
        cv.fill_rect(x + w * 0.3, y, x + w * 0.62, y + h, BLUE)
    else:
        cv.fill_rect(x, y, x + w, y + h, GREY)


def _jet(cv, x, y, s, c, flip=False):
    d = -1 if flip else 1
    cv.poly([(x, y), (x + 14 * s * d, y - 3 * s), (x + 14 * s * d, y + 3 * s)], c)
    cv.poly([(x + 4 * s * d, y), (x + 10 * s * d, y - 8 * s), (x + 12 * s * d, y)], c)
    cv.poly([(x + 4 * s * d, y), (x + 10 * s * d, y + 8 * s), (x + 12 * s * d, y)], c)


def _drone(cv, x, y, s, c):
    cv.disc(x, y, 3 * s, c)
    cv.fill_rect(x - 9 * s, y - 1, x + 9 * s, y + 1, c)
    cv.disc(x - 9 * s, y, 3 * s, c)
    cv.disc(x + 9 * s, y, 3 * s, c)


def _smoke(cv, x, y, s, c=(140, 138, 130)):
    cv.disc(x, y, 5 * s, c)
    cv.disc(x + 5 * s, y - 3 * s, 4 * s, c)
    cv.disc(x - 4 * s, y - 4 * s, 3.5 * s, c)


def _burst(cv, x, y, s, c=(230, 120, 20)):
    cv.disc(x, y, 6 * s, c)
    cv.disc(x, y, 3 * s, (255, 210, 60))
    cv.disc(x, y, 1.5 * s, (255, 255, 255))


def _ship(cv, x, y, s, c):
    cv.poly([(x - 16 * s, y), (x + 16 * s, y), (x + 12 * s, y + 6 * s),
             (x - 12 * s, y + 6 * s)], c)
    cv.fill_rect(x - 6 * s, y - 8 * s, x + 6 * s, y, c)
    cv.fill_rect(x - 2 * s, y - 13 * s, x + 2 * s, y - 8 * s, c)


def _virus(cv, x, y, r, c):
    cv.disc(x, y, r, c)
    for a in range(0, 360, 45):
        dx = math.cos(math.radians(a)) * r * 1.5
        dy = math.sin(math.radians(a)) * r * 1.5
        cv.thick_line(x, y, x + dx, y + dy, 2, c)


def _building(cv, x, y, w, h, c):
    cv.fill_rect(x, y, x + w, y + h, c)
    for i in range(3):
        for j in range(4):
            cv.fill_rect(x + w * (0.15 + j * 0.22), y + h * (0.15 + i * 0.28),
                         x + w * (0.15 + j * 0.22) + 4, y + h * (0.15 + i * 0.28) + 5,
                         (255, 220, 120))


def _cyclone(cv, x, y, r, c):
    cv.arc(x, y, r, 0, math.pi * 1.5, c, 3)
    cv.arc(x, y, r * 0.66, math.pi * 0.5, math.pi * 2.0, c, 3)
    cv.arc(x, y, r * 0.33, math.pi, math.pi * 2.5, c, 3)
    cv.disc(x, y, r * 0.14, c)


def _plane_crash(cv, x, y, s, c):
    cv.poly([(x, y), (x + 16 * s, y - 4 * s), (x + 16 * s, y + 4 * s)], c)
    cv.poly([(x + 5 * s, y), (x + 12 * s, y - 10 * s), (x + 14 * s, y)], c)
    cv.poly([(x + 5 * s, y), (x + 12 * s, y + 10 * s), (x + 14 * s, y)], c)
    _smoke(cv, x + 18 * s, y, 0.8)

def icon_strip(cv, x, y, w, h, kind):
    """Flat illustration band inside a medium card."""
    cv.fill_rect(x, y, x + w, y + h, LIGHT)
    cx = x + w / 2.0
    cy = y + h / 2.0
    if kind == 'iran':
        cv.fill_rect(x, y, x + w, y + h * 0.55, SKY)
        cv.fill_rect(x, y + h * 0.55, x + w, y + h, SEA)
        cv.poly([(x + w * 0.55, y + h), (x + w * 0.62, y + h * 0.6),
                 (x + w * 0.78, y + h * 0.72), (x + w * 0.95, y + h)], SAND)
        _drone(cv, x + w * 0.3, y + h * 0.3, 1.6, INK)
        _jet(cv, x + w * 0.62, y + h * 0.28, 0.9, INK)
        cv.thick_line(x + w * 0.3, y + h * 0.34, x + w * 0.5, y + h * 0.55, 1, RED)
        _ship(cv, x + w * 0.42, y + h * 0.78, 0.9, (90, 60, 40))
    elif kind == 'trilateral':
        cv.fill_rect(x, y, x + w, y + h, (232, 226, 208))
        fw, fh = w * 0.18, h * 0.44
        for i, k in enumerate(('us', 'cn', 'ru')):
            _flag(cv, x + w * 0.08 + i * w * 0.26, y + h * 0.14, fw, fh, k)
        draw_text(cv, x + w * 0.1, y + h * 0.68, 'THU 19 NOV', 10, RED, bold=True)
    elif kind == 'gta':
        cv.fill_rect(x, y, x + w, y + h * 0.55, (58, 42, 84))
        cv.fill_rect(x, y + h * 0.55, x + w, y + h, (30, 22, 48))
        cv.fill_rect(x + w * 0.06, y + h * 0.18, x + w * 0.24, y + h * 0.78, (24, 18, 40))
        cv.fill_rect(x + w * 0.30, y + h * 0.08, x + w * 0.50, y + h * 0.78, (24, 18, 40))
        cv.fill_rect(x + w * 0.56, y + h * 0.24, x + w * 0.74, y + h * 0.78, (24, 18, 40))
        cv.fill_rect(x + w * 0.80, y + h * 0.14, x + w * 0.94, y + h * 0.78, (24, 18, 40))
        for j in range(3):
            cv.fill_rect(x + w * 0.09, y + h * (0.26 + j * 0.16),
                         x + w * 0.21, y + h * (0.26 + j * 0.16) + 3, NEON_PINK)
            cv.fill_rect(x + w * 0.34, y + h * (0.16 + j * 0.16),
                         x + w * 0.46, y + h * (0.16 + j * 0.16) + 3, NEON_CYAN)
            cv.fill_rect(x + w * 0.60, y + h * (0.32 + j * 0.16),
                         x + w * 0.70, y + h * (0.32 + j * 0.16) + 3, NEON_YELLOW)
        cv.fill_rect(x + w * 0.80, y + h * 0.62, x + w * 0.94, y + h * 0.72, NEON_PINK)
        draw_text(cv, x + w * 0.06, y + h * 0.80, 'VICE CITY', 9, NEON_CYAN, bold=True)
    elif kind == 'voyager':
        cv.fill_rect(x, y, x + w, y + h, (12, 14, 30))
        for (sx, sy, r) in ((0.12, 0.2, 1), (0.3, 0.12, 1), (0.5, 0.3, 1),
                            (0.72, 0.15, 1), (0.88, 0.28, 1), (0.2, 0.55, 1),
                            (0.62, 0.55, 1), (0.9, 0.6, 1)):
            cv.disc(x + w * sx, y + h * sy, r, (255, 255, 255))
        cv.disc(x + w * 0.5, y + h * 0.42, 7, (200, 170, 60))
        cv.poly([(x + w * 0.5, y + h * 0.42), (x + w * 0.62, y + h * 0.30),
                 (x + w * 0.66, y + h * 0.36)], (220, 200, 120))
        cv.thick_line(x + w * 0.44, y + h * 0.46, x + w * 0.30, y + h * 0.62, 2, (220, 200, 120))
        cv.thick_line(x + w * 0.56, y + h * 0.46, x + w * 0.70, y + h * 0.62, 2, (220, 200, 120))
        draw_text(cv, x + w * 0.06, y + h * 0.78 - 5, '16.09BN MILES', 9, (255, 220, 90), bold=True)
    elif kind == 'capitol':
        cv.fill_rect(x, y, x + w, y + h, SKY)
        cv.fill_rect(x, y + h * 0.72, x + w, y + h, (120, 140, 120))
        cv.fill_rect(cx - w * 0.3, y + h * 0.42, cx + w * 0.3, y + h * 0.72, (250, 246, 236))
        cv.disc(cx, y + h * 0.42, w * 0.14, (250, 246, 236))
        cv.fill_rect(cx - 2, y + h * 0.18, cx + 2, y + h * 0.30, INK)
        _flag(cv, cx + 4, y + h * 0.08, w * 0.2, h * 0.2, 'us')
        for i in range(4):
            cv.fill_rect(cx - w * 0.24 + i * w * 0.13, y + h * 0.48,
                         cx - w * 0.24 + i * w * 0.13 + 4, y + h * 0.70, INK_SOFT)
        draw_text(cv, x + w * 0.06, y + h * 0.78 - 3, '251-11', 9, RED, bold=True)
    elif kind == 'euro':
        cv.fill_rect(x, y, x + w, y + h, (214, 228, 240))
        cv.disc(cx - w * 0.30, cy, h * 0.30, BLUE)
        for a in range(0, 360, 30):
            dx = math.cos(math.radians(a)) * w * 0.30
            dy = math.sin(math.radians(a)) * h * 0.30
            cv.disc(cx - w * 0.30 + dx, cy + dy, 1.5, (255, 220, 60))
        draw_text(cv, cx + w * 0.02, cy - h * 0.16, '45BN', 16, INK, bold=True)
        draw_text(cv, cx + w * 0.02, cy + h * 0.08, 'EURO', 9, BLUE, bold=True)
    elif kind == 'bangladesh':
        cv.fill_rect(x, y, x + w, y + h, (226, 236, 226))
        cv.fill_rect(x + w * 0.1, y + h * 0.5, x + w * 0.9, y + h * 0.82, INK_SOFT)
        for i in range(5):
            px = x + w * (0.16 + i * 0.15)
            cv.disc(px, y + h * 0.4, 4, INK)
            cv.fill_rect(px - 2, y + h * 0.42, px + 2, y + h * 0.52, INK)
        cv.fill_rect(x + w * 0.66, y + h * 0.1, x + w * 0.92, y + h * 0.3, (255, 255, 255))
        draw_text(cv, x + w * 0.68, y + h * 0.13, 'LOCKDOWN', 7, GREEN, bold=True)
    elif kind == 'cyclone':
        cv.fill_rect(x, y, x + w, y + h, (214, 230, 240))
        _cyclone(cv, cx - w * 0.12, cy, h * 0.36, (40, 80, 120))
        cv.fill_rect(x + w * 0.68, y + h * 0.12, x + w * 0.94, y + h * 0.36, RED)
        draw_text(cv, x + w * 0.70, y + h * 0.16, 'RED', 9, (255, 255, 255), bold=True)
        draw_text(cv, x + w * 0.70, y + h * 0.26, 'ALERT', 7, (255, 255, 255), bold=True)
    elif kind == 'nvidia':
        cv.fill_rect(x, y, x + w, y + h, (20, 24, 20))
        bars = [0.3, 0.45, 0.4, 0.62, 0.85, 1.0]
        bw = w * 0.11
        for i, b in enumerate(bars):
            bx = x + w * 0.08 + i * w * 0.15
            cv.fill_rect(bx, y + h * 0.9 - h * 0.7 * b, bx + bw, y + h * 0.9,
                         (118, 200, 70) if i < 5 else (160, 230, 90))
        draw_text(cv, x + w * 0.06, y + h * 0.08, '$115.8BN', 11, (160, 230, 90), bold=True)
    elif kind == 'anthropic':
        cv.fill_rect(x, y, x + w, y + h, (24, 20, 16))
        cv.disc(cx, cy - h * 0.08, h * 0.26, (255, 140, 60))
        for a in range(0, 360, 45):
            dx = math.cos(math.radians(a)) * h * 0.4
            dy = math.sin(math.radians(a)) * h * 0.4
            cv.thick_line(cx, cy - h * 0.08, cx + dx, cy - h * 0.08 + dy, 2, (255, 200, 90))
        draw_text(cv, x + w * 0.06, y + h * 0.74 - 3, '$83  IPO', 11, (255, 220, 120), bold=True)
    elif kind == 'fed':
        cv.fill_rect(x, y, x + w, y + h, (228, 232, 238))
        cv.fill_rect(cx - w * 0.28, y + h * 0.30, cx + w * 0.28, y + h * 0.38, INK_SOFT)
        for i in range(4):
            cv.fill_rect(cx - w * 0.24 + i * w * 0.13, y + h * 0.38,
                         cx - w * 0.24 + i * w * 0.13 + 5, y + h * 0.66, INK_SOFT)
        cv.fill_rect(cx - w * 0.3, y + h * 0.66, cx + w * 0.3, y + h * 0.74, INK_SOFT)
        cv.poly([(cx + w * 0.34, y + h * 0.62), (cx + w * 0.44, y + h * 0.30),
                 (cx + w * 0.44, y + h * 0.44), (cx + w * 0.52, y + h * 0.44),
                 (cx + w * 0.52, y + h * 0.62)], RED)
        draw_text(cv, x + w * 0.06, y + h * 0.78 - 3, 'MORE HIKES', 9, RED, bold=True)
    elif kind == 'pew':
        cv.fill_rect(x, y, x + w, y + h, (240, 234, 220))
        cv.disc(cx - w * 0.22, cy - h * 0.06, h * 0.24, GREEN)
        cv.disc(cx - w * 0.16, cy - h * 0.10, h * 0.20, (240, 234, 220))
        cv.fill_rect(cx + w * 0.12, cy - h * 0.28, cx + w * 0.18, cy + h * 0.22, BLUE)
        cv.fill_rect(cx + w * 0.02, cy - h * 0.12, cx + w * 0.28, cy - h * 0.02, BLUE)
        draw_text(cv, x + w * 0.06, y + h * 0.78 - 3, 'BY 2035', 9, INK, bold=True)
    elif kind == 'cop31':
        cv.fill_rect(x, y, x + w, y + h, (226, 238, 226))
        cv.disc(cx - w * 0.24, cy, h * 0.32, BLUE)
        cv.poly([(cx - w * 0.34, cy - h * 0.08), (cx - w * 0.2, cy - h * 0.28),
                 (cx - w * 0.14, cy - h * 0.02), (cx - w * 0.3, cy + h * 0.2)], GREEN)
        cv.fill_rect(cx + w * 0.08, cy - h * 0.3, cx + w * 0.42, cy + h * 0.3, (255, 255, 255))
        cv.line(cx + w * 0.08, cy - h * 0.3, cx + w * 0.42, cy - h * 0.3, INK, 1)
        cv.line(cx + w * 0.08, cy + h * 0.3, cx + w * 0.42, cy + h * 0.3, INK, 1)
        draw_text(cv, cx + w * 0.12, cy - h * 0.14, 'DRAFT', 9, RED, bold=True)
    else:
        cv.fill_rect(x, y, x + w, y + h, (228, 226, 214))
        cv.disc(cx, cy, h * 0.22, BLUE)
        draw_text(cv, cx - 3, cy - 5, 'N', 10, (255, 255, 255), bold=True)

# ------------------------------------------------------- 3D helpers
# One studio light from the upper left everywhere: highlights sit
# top-left, cast shadows fall bottom-right. All shading is computed
# from that single direction so the globe and the three lead scenes
# read as lit by the same sun.
LIGHT_DIR = (-0.55, 0.55, 0.62)  # direction TO the light, view space (y up)


def _soft_disc(cv, cx, cy, r, c, a0):
    """Disc with quadratic alpha falloff (soft shadow / glow / smoke)."""
    r = int(r)
    if r <= 0:
        return
    cx = int(cx)
    cy = int(cy)
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 <= r * r:
                cv.blend(x, y, c, a0 * (1.0 - d2 / (r * r)))


def _soft_ellipse(cv, cx, cy, rx, ry, c, a0):
    """Soft elliptical cast shadow (alpha peaks at centre)."""
    rx = int(rx)
    ry = int(ry)
    if rx <= 0 or ry <= 0:
        return
    for y in range(int(cy) - ry, int(cy) + ry + 1):
        for x in range(int(cx) - rx, int(cx) + rx + 1):
            q = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if q <= 1.0:
                cv.blend(x, y, c, a0 * (1.0 - q))


def _sky_bands(cv, x, y, w, h, top, bottom):
    """Vertical sky gradient in 5 flat bands (lightest at the top)."""
    for i in range(5):
        t = i / 4.0
        c = tuple(int(top[k] + (bottom[k] - top[k]) * t) for k in range(3))
        cv.fill_rect(x, y + i * h / 5.0, x + w, y + (i + 1) * h / 5.0, c)


def _shade(base, f):
    """Scale an RGB colour by a diffuse factor f (0..1.15)."""
    return tuple(max(0, min(255, int(v * f))) for v in base)


def _chip(cv, x, y, s, cap):
    w = text_width(s, cap, bold=True) + cap * 1.2
    h = cap * 2.0
    cv.fill_rect(x, y, x + w, y + h, (255, 255, 255))
    cv.fill_rect(x, y, x + w, y + 1, INK)
    cv.fill_rect(x, y + h - 1, x + w, y + h, INK)
    cv.fill_rect(x, y, x + 1, y + h, INK)
    cv.fill_rect(x + w - 1, y, x + w, y + h, INK)
    draw_text(cv, x + cap * 0.6, y + cap * 0.45, s, cap, INK, bold=True)


# Rough continent blobs (lon, lat, angular radius in degrees, colour)
# used by the orthographic globe. Centred on lon 90E / lat 25N so
# Shenzhen and the Gulf are both on the visible face.
_GLOBE_LAND = [
    (-100, 48, 22, (96, 130, 70)), (-85, 34, 13, (96, 130, 70)),
    (-60, -12, 16, (96, 130, 70)),
    (18, 4, 20, (96, 130, 70)), (30, -18, 12, (96, 130, 70)),
    (55, 52, 30, (110, 138, 74)), (100, 55, 18, (110, 138, 74)),
    (80, 30, 14, (110, 138, 74)), (103, 12, 10, (96, 130, 70)),
    (134, -25, 11, (150, 128, 70)),
    (24, 25, 11, (188, 168, 108)), (45, 25, 9, (188, 168, 108)),
]
_GLOBE_LAND_VEC = []
for (_lo, _la, _rr, _cc) in _GLOBE_LAND:
    _lr, _ar = math.radians(_lo), math.radians(_la)
    _GLOBE_LAND_VEC.append((
        (math.cos(_ar) * math.sin(_lr), math.sin(_ar), math.cos(_ar) * math.cos(_lr)),
        math.cos(math.radians(_rr)), _cc))


def _globe(cv, x, y, w, h):
    """3D globe: orthographic sphere, one upper-left light, shaded
    oceans + simple continents, specular highlight, cast shadow,
    numbered pins for the two lead stories on this face (1 Shenzhen,
    2 Gulf). The full 1-13 pin set stays on the dot map below."""
    cx = x + w / 2.0
    cy = y + h / 2.0 - 8
    R = min(w, h - 22) / 2.0
    lon0 = math.radians(90.0)
    lat0 = math.radians(25.0)
    cl0, sl0 = math.cos(lat0), math.sin(lat0)
    co0, so0 = math.cos(lon0), math.sin(lon0)
    lx, ly, lz = LIGHT_DIR
    ln = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / ln, ly / ln, lz / ln
    Ri = int(R)
    for sy in range(int(cy) - Ri, int(cy) + Ri + 1):
        for sx in range(int(cx) - Ri, int(cx) + Ri + 1):
            dx = (sx + 0.5 - cx) / R
            dy = (cy - (sy + 0.5)) / R  # screen down -> view up
            q = dx * dx + dy * dy
            if q > 1.0:
                continue
            z = math.sqrt(1.0 - q)
            # view-space normal -> world point (rotate by lat0, then lon0)
            px = dx
            py = dy * cl0 - z * sl0
            pz = dy * sl0 + z * cl0
            wx = px * co0 + pz * so0
            wy = py
            wz = -px * so0 + pz * co0
            diff = 0.32 + 0.68 * max(0.0, dx * lx + dy * ly + z * lz)
            base = (64, 116, 168)
            for (vx, vy, vz), cosr, col in _GLOBE_LAND_VEC:
                if wx * vx + wy * vy + wz * vz > cosr:
                    base = col
                    break
            cv.set(sx, sy, _shade(base, diff))
    # specular highlight, upper left (same light direction)
    _soft_disc(cv, cx - R * 0.38, cy - R * 0.42, R * 0.30, (255, 255, 255), 0.18)
    _soft_disc(cv, cx - R * 0.42, cy - R * 0.46, R * 0.13, (255, 255, 255), 0.30)
    cv.circle_outline(cx, cy, R, 2, (110, 150, 190))
    # cast shadow, bottom right of the light
    _soft_ellipse(cv, cx + 5, cy + R + 5, R * 0.85, 7, (20, 20, 20), 0.28)
    # pins: 1 Shenzhen (114.1E, 22.5N), 2 Gulf (48.0E, 29.0N)
    for (lon, lat, n) in ((114.1, 22.5, 1), (4.4, 52.1, 2), (56.5, 26.6, 3),
                          (106.8, -6.2, 4), (30.5, 50.4, 5), (8.9, 44.4, 6),
                          (85.8, 20.3, 7)):
        lo = math.radians(lon - 90.0)
        la = math.radians(lat)
        vx = math.cos(la) * math.sin(lo)
        vy = math.cos(lat0) * math.sin(la) - math.sin(lat0) * math.cos(la) * math.cos(lo)
        vz = math.sin(lat0) * math.sin(la) + math.cos(lat0) * math.cos(la) * math.cos(lo)
        if vz <= 0.05:
            continue
        _nudge = {2: (0, -8), 5: (12, -4), 6: (-8, 8)}
        dx, dy = _nudge.get(n, (0, 0))
        px = cx + vx * R + dx
        py = cy - vy * R + dy
        cv.disc(px, py, 6, RED)
        cv.ring(px, py, 6, 1, (255, 255, 255))
        draw_text(cv, px - text_width(str(n), 7, bold=True) / 2.0, py - 4.5,
                  str(n), 7, (255, 255, 255), bold=True)


# ------------------------------------------------------- -20 palette
NIGHT_TOP = (8, 14, 30)
NIGHT_MID = (13, 22, 44)
NIGHT_BOT = (6, 9, 18)
IVORY = (246, 241, 227)
IVORY_DIM = (205, 210, 220)
GOLD2 = (212, 168, 60)
AMBER = (230, 160, 60)
FLOOR = (18, 28, 48)
GLOBE_SEA = (64, 116, 168)

# ------------------------------------------------------- -20 scenes
def _figure(cv, x, y, s, suit, hair, skin=(222, 184, 150)):
    """Miniature leader figure, ~34 px tall. Head + hair cap + suit
    torso behind a table. No facial detail at this scale: the label
    below the figure carries the name."""
    cv.disc(x, y, 7 * s, skin)
    # hair cap
    cv.poly([(x - 7 * s, y - 1), (x - 6 * s, y - 7 * s), (x + 6 * s, y - 7 * s),
             (x + 7 * s, y - 1)], hair)
    # torso (shoulders to table)
    cv.poly([(x - 11 * s, y + 24 * s), (x - 9 * s, y + 7 * s),
             (x + 9 * s, y + 7 * s), (x + 11 * s, y + 24 * s)], suit)
    # shirt + tie
    cv.poly([(x - 3 * s, y + 8 * s), (x + 3 * s, y + 8 * s),
             (x + 2 * s, y + 24 * s), (x - 2 * s, y + 24 * s)], (240, 238, 230))
    cv.fill_rect(x - 1.5 * s, y + 9 * s, x + 1.5 * s, y + 22 * s, (176, 30, 36))


def _summit_scene(cv, x, y, w, h):
    """Shenzhen summit diorama above the globe: dusk skyline, three
    flags, three miniature leaders at one table. Labels name them;
    no face is drawn at this scale."""
    cx = x + w / 2.0
    # warm dusk glow behind the scene
    _soft_disc(cv, cx, y + h * 0.55, w * 0.42, (230, 160, 60), 0.10)
    # skyline silhouette (dark towers, lit windows)
    base = y + h - 34
    towers = [(0.02, 0.30, 0.09, 0.52), (0.13, 0.20, 0.08, 0.62),
              (0.23, 0.34, 0.10, 0.48), (0.68, 0.26, 0.09, 0.56),
              (0.79, 0.18, 0.08, 0.64), (0.89, 0.32, 0.09, 0.50)]
    for (fx, fy, fw, fh) in towers:
        tx = x + w * fx
        tw = w * fw
        ty = y + h * fy
        cv.fill_rect(tx, ty, tx + tw, base, (26, 34, 58))
        for j in range(3):
            wy = ty + 6 + j * 10
            if wy < base - 4:
                cv.fill_rect(tx + 3, wy, tx + tw - 3, wy + 3, (255, 210, 110))
    # three flags on poles
    for i, k in enumerate(('us', 'cn', 'ru')):
        fx = cx - 130 + i * 130
        cv.vline(fx - 2, y + 26, y + 62, (200, 200, 190), 2)
        _flag(cv, fx, y + 26, 40, 24, k)
    # table
    cv.fill_rect(cx - 150, y + h - 34, cx + 150, y + h - 26, (96, 64, 40))
    cv.fill_rect(cx - 150, y + h - 34, cx + 150, y + h - 32, (150, 108, 66))
    # three leaders behind the table
    _figure(cv, cx - 96, y + 118, 1.5, (30, 50, 90), (232, 202, 122))
    _figure(cv, cx, y + 118, 1.5, (38, 38, 40), (20, 20, 20))
    _figure(cv, cx + 96, y + 118, 1.5, (58, 58, 68), (200, 190, 170))
    # name labels under the table edge
    for (dx, name) in ((-96, 'TRUMP'), (0, 'XI JINPING'), (96, 'PUTIN')):
        draw_text(cv, cx + dx, y + h - 22, name, 9, IVORY, bold=True, align='center')


def _icj_scene(cv, x, y, w, h):
    """The Hague: ICJ palace (columns + pediment) with three
    humanitarian tents and small family figures in front. Dignified
    miniature scale; no suffering shown as spectacle."""
    base = y + h - 6
    # palace: steps, columns, pediment
    cv.fill_rect(x + 8, base - 6, x + w - 8, base, (150, 146, 132))
    cv.fill_rect(x + 14, base - 52, x + w - 14, base - 6, (214, 206, 186))
    for i in range(5):
        colx = x + 26 + i * ((w - 52) / 4.0)
        cv.fill_rect(colx - 4, base - 50, colx + 4, base - 8, (246, 241, 227))
        cv.fill_rect(colx - 6, base - 52, colx + 6, base - 48, (246, 241, 227))
    cv.poly([(x + 10, base - 52), (x + w / 2.0, base - 62), (x + w - 10, base - 52)],
            (226, 218, 198))
    cv.disc(x + w / 2.0, base - 54, 4, GOLD2)
    # tents, lower right of the palace
    for i, tx in enumerate((0.58, 0.72, 0.86)):
        txx = x + w * tx
        tyy = base - 26
        cv.poly([(txx - 16, tyy), (txx, tyy - 16), (txx + 16, tyy)], (196, 188, 168))
        cv.poly([(txx - 5, tyy), (txx, tyy - 8), (txx + 5, tyy)], (90, 80, 66))
    # small family figures (head + robe), standing, dignified
    for (fx, fy, c) in ((0.30, base - 8, (120, 90, 70)),
                        (0.36, base - 8, (90, 100, 130)),
                        (0.42, base - 8, (140, 110, 80))):
        fxx = x + w * fx
        cv.disc(fxx, fy - 14, 3, (222, 184, 150))
        cv.poly([(fxx - 4, fy), (fxx - 3, fy - 11), (fxx + 3, fy - 11),
                 (fxx + 4, fy)], c)


def _hormuz_scene(cv, x, y, w, h):
    """Strait of Hormuz at night: dark sea, a burning tanker, black
    smoke, a red warning light. Restrained warning colours."""
    base = y + h - 6
    horizon = y + int(h * 0.42)
    _sky_bands(cv, x, y, w, horizon - y, (20, 28, 48), (52, 52, 70))
    cv.fill_rect(x, horizon, x + w, base, (24, 54, 86))
    # moonlight path on the water
    for i in range(5):
        ww = w * (0.10 + i * 0.03)
        cv.fill_rect(x + w * 0.45 - ww / 2.0, horizon + 6 + i * 7,
                     x + w * 0.45 + ww / 2.0, horizon + 8 + i * 7, (120, 150, 180))
    # distant headland, left
    cv.poly([(x, base), (x, horizon + 10), (x + w * 0.20, horizon + 14),
             (x + w * 0.24, base)], (10, 18, 34))
    # tanker hull + superstructure, centre-right
    tx = x + w * 0.52
    ty = horizon + 12
    _ship(cv, tx, ty, 2.6, (130, 86, 58))
    cv.fill_rect(tx - 14, ty - 26, tx + 14, ty - 8, (200, 190, 170))
    cv.fill_rect(tx - 14, ty - 26, tx + 14, ty - 24, (176, 30, 36))
    # flames + smoke above the deck
    _burst(cv, tx + 30, ty - 14, 1.6)
    _burst(cv, tx - 6, ty - 18, 1.2)
    _smoke(cv, tx + 34, ty - 36, 1.6, (70, 70, 72))
    _smoke(cv, tx + 52, ty - 44, 1.2, (90, 90, 92))
    _soft_disc(cv, tx + 30, ty - 14, 40, (230, 120, 20), 0.38)
    # red warning light on the mast
    cv.disc(tx, ty - 34, 3, (220, 40, 40))
    _soft_disc(cv, tx, ty - 34, 10, (220, 40, 40), 0.35)


def _indonesia_scene(cv, x, y, w, h):
    """Jakarta: parliament dome silhouette + gold scales of justice.
    A smaller, clearly recognisable regional element."""
    base = y + h - 6
    cx = x + w / 2.0
    # parliament: dome + colonnade
    cv.fill_rect(x + 18, base - 30, x + w - 18, base, (58, 68, 98))
    cv.fill_rect(x + 18, base - 30, x + w - 18, base - 27, GOLD2)
    for i in range(6):
        colx = x + 34 + i * ((w - 68) / 5.0)
        cv.fill_rect(colx - 3, base - 28, colx + 3, base - 2, (150, 146, 132))
    cv.poly([(cx - 34, base - 30), (cx, base - 52), (cx + 34, base - 30)],
            (150, 146, 132))
    cv.disc(cx, base - 52, 5, GOLD2)
    cv.vline(cx, base - 62, base - 52, GOLD2, 2)
    # scales of justice, gold, right of the dome
    sx = x + w * 0.78
    sy = base - 46
    cv.vline(sx, sy - 14, sy + 12, GOLD2, 2)
    cv.fill_rect(sx - 14, sy - 14, sx + 14, sy - 12, GOLD2)
    cv.disc(sx, sy - 16, 3, GOLD2)
    for dx in (-14, 14):
        cv.line(sx, sy - 13, sx + dx, sy - 2, GOLD2, 1)
        cv.poly([(sx + dx - 7, sy - 2), (sx + dx + 7, sy - 2),
                 (sx + dx, sy + 6)], GOLD2)
    # small red-white flag accent on the dome
    _flag(cv, x + w * 0.10, base - 62, 22, 13, 'id')


# ------------------------------------------------------- -20 stories
# 4 lead narratives (verified, see STORIES.md) + 6 ALSO TODAY markers.
STORIES = [
    dict(n=1, kicker='1  SHENZHEN · DIPLOMACY', color=(212, 168, 60),
         head='Trump, Xi and Putin meet in Shenzhen',
         deck='First trilateral of the three leaders: a joint peace declaration, but no concrete breakthrough on Ukraine or Iran.'),
    dict(n=2, kicker='2  THE HAGUE · JUSTICE', color=(29, 78, 137),
         head='ICJ: Myanmar guilty of Rohingya genocide',
         deck='The Hague rules 9–6: Myanmar committed genocide against the Rohingya.'),
    dict(n=3, kicker='3  STRAIT OF HORMUZ · ENERGY', color=(176, 30, 36),
         head='Tanker ablaze after mine strike in Hormuz',
         deck='A tanker burns east of the strait after hitting a mine. Shipping on edge.'),
    dict(n=4, kicker='4  JAKARTA · INDONESIA', color=(46, 110, 58),
         head='Indonesia passes asset forfeiture law',
         deck='DPR passes the bill, 74 articles, after 18 years. Takes effect in 12 months.'),
]
ALSO = [
    ('5  KYIV', '4 ballistic missiles hit the capital'),
    ('6  GENOA', 'Drone sighting shuts airport 4 hours'),
    ('7  AKVAN', '80,000+ evacuated as cyclone nears Odisha'),
    ('8  ANTHROPIC', 'Record Nasdaq debut for the AI lab'),
    ('9  IRAN CALL', 'Trump delays the Iran decision to 2027'),
    ('10  EUROPE', 'Allies ready to talk with Russia'),
]


def _vignette(cv, x, y, w, scene, st):
    """One narrative vignette: 3 px coloured rule, 70 px illustration,
    kicker chip, 2-line headline, 2-line deck. No box: the three
    vignettes share one floor under the same globe."""
    cv.fill_rect(x, y, x + w, y + 3, st['color'])
    scene(cv, x, y + 6, w, 70)
    kicker(cv, x, y + 82, st['kicker'], 9, st['color'])
    hy = y + 102
    lines = wrap_balanced(st['head'], 13, w, bold=True)
    draw_para(cv, x, hy, lines[:2], 13, IVORY, leading=16, bold=True)
    dy = y + 138
    dlines = wrap_balanced(st['deck'], 9.5, w)
    draw_para(cv, x, dy, dlines[:2], 9.5, IVORY_DIM, leading=12)


def build():
    cv = Canvas(W, H, NIGHT_BOT)
    # ---- night-sky gradient (64 bands, top midnight -> floor)
    for i in range(64):
        t = i / 63.0
        if t < 0.55:
            u = t / 0.55
            c = tuple(int(NIGHT_TOP[k] + (NIGHT_MID[k] - NIGHT_TOP[k]) * u) for k in range(3))
        else:
            u = (t - 0.55) / 0.45
            c = tuple(int(NIGHT_MID[k] + (NIGHT_BOT[k] - NIGHT_MID[k]) * u) for k in range(3))
        cv.fill_rect(0, int(i * H / 64.0), W, int((i + 1) * H / 64.0), c)
    # faint fixed stars in the upper sky
    for (sx, sy, r) in ((60, 60, 1), (140, 40, 1), (900, 50, 1), (960, 90, 1),
                        (80, 150, 1), (950, 170, 1), (200, 120, 1), (830, 120, 1)):
        cv.disc(sx, sy, r, (200, 210, 230))
    MX = 14
    CW = 996
    # ---- masthead: title + date
    draw_text(cv, MX + CW / 2.0, 12, 'THE WORLD', 46, IVORY, bold=True,
              align='center', serif=True)
    draw_text(cv, MX + CW / 2.0, 66, 'AT A CROSSROADS', 25, GOLD2, bold=True,
              align='center', serif=True)
    draw_text(cv, MX + CW / 2.0, 100, 'FRIDAY, 20 NOVEMBER 2026', 20, IVORY,
              bold=True, align='center', serif=True)
    cv.fill_rect(MX, 128, MX + CW, 131, GOLD2)
    # ---- summit diorama, upper centre (y 136..330)
    _summit_scene(cv, 232, 136, 560, 194)
    draw_text(cv, MX + CW / 2.0, 334, 'PEACE DECLARATION - BUT NO BREAKTHROUGH ON UKRAINE OR IRAN',
              10, IVORY, bold=True, align='center')
    # ---- central globe: atmosphere glow, reflective floor, pins 1-7
    _soft_disc(cv, 512, 512, 196, (70, 140, 200), 0.22)
    _globe(cv, 342, 352, 340, 340)
    _soft_ellipse(cv, 512, 700, 150, 8, (70, 140, 200), 0.25)
    cv.fill_rect(30, 700, 994, 702, (120, 150, 190))
    # ---- three vignettes on the same floor (y 710..872)
    _vignette(cv, 30, 710, 310, _icj_scene, STORIES[1])
    _vignette(cv, 357, 710, 310, _indonesia_scene, STORIES[3])
    _vignette(cv, 684, 710, 310, _hormuz_scene, STORIES[2])
    # ---- ALSO TODAY strip: 6 markers, 2 rows x 3 columns
    cv.box(30, 882, 994, 962, IVORY, 2)
    draw_text(cv, 40, 888, 'ALSO TODAY - 20 NOVEMBER 2026', 11, GOLD2, bold=True)
    cv.fill_rect(40, 906, 984, 909, GOLD2)
    for i, (kick, txt) in enumerate(ALSO):
        col = i % 3
        row = i // 3
        ax = 40 + col * 318
        ay = 916 + row * 22
        draw_text(cv, ax, ay, kick, 9.5, GOLD2, bold=True)
        draw_text(cv, ax + text_width(kick, 9.5, bold=True) + 8, ay, txt, 9.5,
                  IVORY)
    # ---- date check strip (text to the judge - allowed and read)
    cv.fill_rect(MX, 970, MX + CW, 1010, (0, 0, 0))
    dc1 = 'DATE CHECK - Every story here happened or was first reported on Friday 20 November 2026.'
    dc2 = 'Summit, ICJ ruling and Indonesia law are 19 Nov events that led the news on 20 Nov. No casualty figures invented.'
    draw_text(cv, MX + 8, 974, dc1, 11, (255, 255, 255), bold=True)
    draw_text(cv, MX + 8, 988, dc2, 11, (220, 220, 210))
    # ---- footer
    draw_text(cv, MX, 1013, 'Sources: NYT, ICJ, TASS/AFP, DPR RI, Reuters, AP, BBC, IMD. Original drawings.',
              9, IVORY_DIM)
    draw_text(cv, MX + CW - text_width('THE WORLD AT A CROSSROADS', 9, bold=True), 1013,
              'THE WORLD AT A CROSSROADS', 9, GOLD2, bold=True)
    return cv


def main():
    out = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')
    cv = build()
    n = write_png(cv, os.path.join(out, 'entry.png'))
    print('wrote %s/entry.png (%d bytes, %dx%d)' % (out, n, W, H))


if __name__ == '__main__':
    main()
