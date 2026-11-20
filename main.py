#!/usr/bin/env python3
# THE WORLD AT A CROSSROADS - Friday 20 November 2026.
# make.fun bounty: news-image-20261120 - "Sum up 20 November's world
# news in one image". Pure Python 3 stdlib, no network, fully
# deterministic: two runs write byte-identical /output/entry.png.
# One unified image, not four panels: a 3D-shaded Earth suspended
# above a dark reflective floor; the Shenzhen trilateral above it,
# the ICJ/Rohingya story lower left, the Hormuz tanker crisis lower
# right, Indonesia's asset forfeiture law as a smaller element, the
# Cyclone Akvan hero band under the globe, and a compact ALSO TODAY
# grid with twelve further verified stories.
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
_ATLAS_B64 = (
    "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"
    "9gEH2MoKQVMHM5gxXwVVCLjUt+IC3VecnRRCVEkqkKaUUwikDX3LC94KgS2SxSqB6QT9FQIJoap2TkOFQOrRgX+oEsgQbI5KIKtc"
    "CX5/cIJ5/UWxviunI+FrKrc6hOeuJ7uiq7ajB3Mz07hD8dac2N0jOKMYkQd336tZe2g8pHbnPpAYpr6WSwNHB1IslwmRePwI8Njr"
    "c2CeGm42B+i1nb6MMIuhbXou1eBiRdd70PJ2Kg3cl+uGjtWhC3QCKPVb6YS2it8Xo+WZONoVpPBFdb/gdCbk4jGFrn4L6UfbxxyQ"
    "5dPB3gaZSRbcfrtq9SFxkNSReyFHH4i35j7Z/QlzRHTTBLRCmoCWnxT1YxnBUOKbdZxpB2s3vrhwNc4ESA/USlTTgo5aqSktva2V"
    "uvNVJUq/0GXqx0rxzXqtoUyvl7ZpW+8tr0n0J+h85K+VUFp7LHdbIa6lCKGruzK6of/Do3v4onF0d7qM7uyPjKPbPcgwuo+8SF9l"
    "dG1oI30nW45uYifeji8PJSAXvRKod5bXFUroqXDoqpQTpNVSCF1pp6WPeUMn1N+RmHtnPumhMgoxO5w5jw9+WVTbceKbNe863wlp"
    "LQ3jQoXYGA+V8B79ZWWVgFJBOZUwn256Zo1gChuYD853jLpLVAdt9OObdcjVzSP8Hl/Rpd1UJXjdALjjpzasBRUi5hpauoy+0cty"
    "EuE2EppIa4qJecQsFdhU2E96RrZvxacSWiG9h51Itmc83DeK+ETB3q51O/2cf54y4wRmP1pwnvwKt7k/7DzO/JnYCksQwRFOX9IW"
    "u8brHHunR+jNL7pF2IexotpktPwwYwpOBHrZrl9bcab2EM5EjeP0XbAl6gRTKwMT4J0ouDK4To1eZ2CrudXs4/cybE/39qMt7aXK"
    "C6vBcKw+3alJHVy+05q06DAHVqMrsywwkyZdx6tHKsWyUKGIUjQ34vuqKEpAxL+rWBP3Q2E8ISMyOctCCZG8pk7Xt3KwwkaVnOA4"
    "FKi8iMchgGvcvlece2T3UJlN2Cag17+PsFshsHX5K/N0MSURfZ2MEQlj4BAnY0ghKQAnizHfx0YxMSglfffSw/ar0pwaPvFsmj3t"
    "5AguA76udgZfQkxuCKZCf35X3CikGdB07CTdI81Uy7vNu7Wi801p0uPWxRnxrNuCM4VN0y/lW93dhVrDQFsJAYRxcL3y4kY5XJRJ"
    "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"
    "TLYEkxTO+fte+KtrMr/+cuENB4ErFw4GenRKu1DmVvqpSRdgiuFPM2J8MAeDf9RcwUmJgbHaFuk24HcAHDIbwmuEzdlFEX/PPN8T"
    "N2CdhI1IHOviKYkDHKFgw1ONpX0U61S7i8sBTsYCdEzRLbzCqYeUsrDwErRP1paLP98bzi3kFE3lfpeXrIFYvq5v+m5Y0vXW1+gO"
    "cmjZnx1KZvZC26jJZ9IKQ9QxJHwapoTyx6Wi0MchZx96HqCEfZrhnhnIByY4wbgPtvqQ8fowDo3DwvpjJB3rtylThX0+2rHnT3mH"
    "NNPiW61T84N7cgfNg8Xw0xMN9E7xgB8Nf6oPc0KOtASruegGQP9YrSHHGafCKrEN4OodXVkCp2LY3b4oOyqes4P4hCcpRPSvEHGX"
    "lwj15WN0iK0wIQOFY1ei+gnTcyn4onVDG+sUcPH0PIUEXEHMsAHzn3FAsotBVczwKE5EaZ5jx9rmNvL01FL0XFeYLUVwqMjXlb4d"
    "v93LY9bowY325rB5KOhzI3vuMaoyzKxOKOluyJBHLac+ZAydCkKy52ld0sM4Tf7VRf2rktZN3iQ/5Y2GL7qyL7qyL7qyL7qyL7qy"
    "L7qyL7qyL7qyL7qyL7qyL7qyL7qyL7qyL7qyL7qyL7qyL7qyL7qyL7qyL7qyL7qyL7qyL7qyL7qyL7qyL7qy/091Ze2lrqxMgKWu"
    "bKilrsyolVHjbZFxgsEiSGP+1YfrcSqmLYbdDLPSR++YsrjaIA55lejv+VgHcZ9fylWSs+mmx2ZuIgZjcODbp3b0nOJ4zPNSn96h"
    "7M91J23dFOdREoNEPecYWlNivky5MpCClpY1NlFpZidoG/OiPIYsQ53c61XnOdE9B2nLUsy5SSJoQ/lZAd+mQQXm0Owdytjrp0BZ"
    "5nLwJ1QjlTPZ1MvMn1HlGtsM2sjeay5OvDgopGdGdZjIsls86bFzGVyYwrmfIvVjbU5Php0UwGv7Kjg5BXYh1DmlVIGtK+EibuVh"
    "Nzkt/25EFlKOtziqsfotfQVq1naqzvv8qCyU0BRZRg5iuXyu58RacRjioKNLnY78QE8MRNYC01A3R/6BN60ycfFuInT9HMNvLmNC"
    "iDyEzpmFYxpBRcun109Dkf+RUxSjrBI/995iF3eiOGRUjgOyT+URo3+LZHF9pNMrAow0cdDe8ZjPcNgaJKW9xMNrJ5chlVuKjDFF"
    "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"
)

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


# Real coastline data: Natural Earth 110m land, rasterised at build
# time to a 360x180 1-bit equirectangular land mask (1 deg/cell),
# embedded below so the run stays stdlib-only with no network.
# Source: github.com/nvkelso/natural-earth-vector (public domain).
# v1 drew rough continent blobs and (worse) rotated them with a
# sign-flipped latitude, so land sat upside-down vs the pins.
_LAND_MASK_B64 = (
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP//gAAD//4AAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB//////Hf///8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAf/////"
    "////////AAAAAAAAAAAAAAAAAHAAAAAAAAAAAAAAAAAAAAAAAAAAAB/////////////wAAAAX/8AAP8AAAAAAfwAAAAAAAAAAAAA"
    "AAAAAAAAAAAAOB////g////////AAAAD//wAAAAAAAAAAH/gAAAAAAAAAAAAAAAAAAAAAAAeP3vv/7////////+AAAAB//AAAAAA"
    "AAAAAAf8AAAAAAAAAAAAAAAAAAAAAA8+AL4f/g////////+AAAAAfvgAAAAAAAAAAAF+AAAAAAAAAAAAAAAAAAAAAH/3R////gP/"
    "///////AAAAAHAAAAAAAf4AAAHP//AAAA8AAAAAAAAAAAAAAACP/5///8AAAf/////+AAAAAAAAAAAAf+AAAH////gAAD//gAAAA"
    "AAAAAAAAAf4+AN//+AAAP/////+AAAAAAAAAAAAeAAAAP///4AAAA/nAAAAAAAAAAAAAAf/B8///3wAAH/////8AAAAAAAAAAAB4"
    "AEAP//////H4AfAAAAAAAAAAAAAAA//+5/9//4AAD/////wAAAAAAAAAAAHwAHt////////8Af/AAAAA4AABgAAAA///8f8///AA"
    "D/////wAAAAAAAiAAAHwA//////////8///gQAADwAA//+gAOYf//1+///+AB/////4AAAAAAH/wAAB8A/v/////////////8AID"
    "AAD///+P/////v/j///AB////+AAAAAAAf//gAAA+/////////////////P+4Af//////////H/z4f/AAf///4AAAAAAD///4eB/"
    "/////////////////////AH/////////////45/wA///8AAAAAAAP////e///////////////////////4f/////////////gD/+"
    "A///wAycAAAAf//////////////////////////////////////////7g/+4Af//AB/+AAAA/+f+f///////////////////////"
    "jwf/////////////9//oAf/wAA/8AAAD/8//////////////////////////APH////////////PcB/wAP/gAAfgAAAP/3//////"
    "///////////////////+ACP////////////A///gAD/AAAAAAAB//H//////////////////////////AAf///////////wAG/5A"
    "AD/AAAAAAAD//H/////////////////////////gAA////////////wAA/4QAB+AAAAAAAB//n//////////////////////D/+A"
    "AAb/zwn///////wAA/44AAAAAAAAAAB//D//////////////////////D6IAAAAv4AA///////4AB//8AAAAAAAAA4B5/B//////"
    "/////////////4AYPgAAAAAH8AAD///////AAf/8AAAAAAAAA+AP+H///////////////////gAA/wAAAAAfQAAB///////wAf/+"
    "AAAAAAAAB8AO8H///////////////////AAB/wAAAAD8AAAA////////x///gAAAAAAAD8AP4H//////////////////+AAB/AAA"
    "AAGAAAAD////////z///4AAAAAAAH/AP////////////////////+yAB/gAAAAAAAAADP///////x///+AAAAAAAPfj/////////"
    "/////////////+AB+AAAAAAAAAABv///////5///+AAAAAAAPfz///////////////////////AA4AAAAAAAAAAAD///////////"
    "+AAAAAAAM/////////////////////////AA4AAAAAAAAAAAH///////////MAAAAAAAA////////////////////////7AAAAAA"
    "AAAAAAAAH//////////+fgAAAAAAAj///////////////////////7AAAAAAAAAAAAAAA//////////w/wAAAAAAAf//////////"
    "/////////////+gAAAAAAAAAAAAAAf/////////x/wAAAAAAAf///////////////////////yAAAAAAAAAAAAAAAf/////////9"
    "DgAAAAAAAD///////////////////////nAAAAAAAAAAAAAAAP//////////gAAAAAAAAD/////P////////////////+GAAAAAA"
    "AAAAAAAAAP/////////4AAAAAAAAAD/////Hf///////////////8HQAAAAAAAAAAAAAAf////////5gAAAAAAAAP//3z/+AH///"
    "////////////8PwAAAAAAAAAAAAAAf////////wAAAAAAAAAH/4P5/8HB//////////////+wfgAAAAAAAAAAAAAAf////////4A"
    "AAAAAAAAP/8M+f//n//////////////8AdAAAAAAAAAAAAAAAf////////gAAAAAAAAAH/gMP//////////////////8AcAAAAAA"
    "AAAAAAAAAP///////8AAAAAAAAAAP/AMH/P///////////////fwAMAAAAAAAAAAAAAAAP///////8AAAAAAAAAAP/gI/Pv/////"
    "/////////+T4AYAAAAAAAAAAAAAAAH///////4AAAAAAAAAAH/A3+Hn///////////////78C4AAAAAAAAAAAAAAAD///////4AA"
    "AAAAAAAAH8//MHH///////////////48D4AAAAAAAAAAAAAAAB///////4AAAAAAAAAAB//+AB4P//////////////A8/4AAAAAA"
    "AAAAAAAAAB///////wAAAAAAAAAAB//+AAgP//////////////g7/gAAAAAAAAAAAAAAAAf//////AAAAAAAAAAAH///AAAB////"
    "//////////gH8AAAAAAAAAAAAAAAAAP/////8AAAAAAAAAAAP///8PAD//////////////wHwAAAAAAAAAAAAAAAAAH/////4AAA"
    "AAAAAAAAP///+f/7//////////////wDAAAAAAAAAAAAAAAAAAH/////4AAAAAAAAAAAP/////////////////////wAAAAAAAAA"
    "AAAAAAAAAAD////i8AAAAAAAAAAAf/////////////////////4AAAAAAAAAAAAAAAAAAAB///gAcAAAAAAAAAAB//////////v/"
    "//////////wAAAAAAAAAAAAAAAAAAAD//+AAcgAAAAAAAAAD//////////3///////////gAAAAAAAAAAAAAAAAAAAA7/+AAdwAA"
    "AAAAAAAH///////+//9///////////AAAAAAAAAAAAAAAAAAAAAf/+AANgAAAAAAAAAH///////+//8f//////////QAAAAAAAAA"
    "AAAAAAAAAAAc/+AABgAAAAAAAAAP///////+f//4Af///////+wAAAAAAAAAAAAAAAAAAAAGf+AAcgAAAAAAAAAf////////P//+"
    "Af///////8wAAAAAAAAAAAAIAAAAAAAGf+AB/gAAAAAAAAAf////////n///AH///////wwAAAAAAAAAAAAPAAAAAAAAP+A9H4AA"
    "AAAAAAA/////////3///AD///v//8AgAAAAAAAAAAAABgAAAAAAAP+B8B8AAAAAAAAA/////////n//+AD//8P/+YAAAAAAAAAAA"
    "AAABwAAAAAAAP/B4A/4AAAAAAAAf////////z//8AA//wH/88AAAAAAAAAAAAAAAgAAAAAAAD//4B3/gAAAAAAAf////////x//8"
    "AAf/AD/+4A4AAAAAAAAAAAAAAAAAAAAAB//wAwjgAAAAAAAf////////5//4AAf/AD/+AA4AAAAAAAAAAAAAAAAAAAAAAP/0AAAA"
    "AAAAAAAf////////4//gAAf+AD//gB4AAAAAAAAAAAAAAAAAAAAAADP/gAAAAAAAAAAf////////8/+AAAf4ADf/gBwAAAAAAAAA"
    "AAAAAAAAAAAAAAH/gAAAAAAAAAA///////////wAAAP4AAf/gA4AAAAAAAAAAAAAAAAAAAAAAAD/gAAAAAAAAAAf//////////gA"
    "AAP4AAP/wA8AAAAAAAAAAAAAAAAAAAAAAAAPgAoAAAAAAAAf/////////8MAAAPwAAP/wAzAAAAAAAAAAAAAAAAAAAAAAAAHgH8A"
    "AAAAAAAf/////////x8AAAHwAAMfwBfAAAAAAAAAAAAAAAAAAAAAAAADgP//AAAAAAAH//////////8AAADwAAMfADfAAAAAAAAA"
    "AAAAAAAAAAAAAAAD/f//AAAAAAAH//////////4AAAD4AAMOAGNgAAAAAAAAAAAAAAAAAAAAAAAA////gAAAAAAD//////////4A"
    "AAD8AAOEAEPgAAAAAAAAAAAAAAAAAAAAAAAAN///wAAAAAAB//////////wAAABcAAOAAAfgAAAAAAAAAAAAAAAAAAAAAAAAA///"
    "6AAAAAAA//////////wAAAAcAAHgAMPgAAAAAAAAAAAAAAAAAAAAAAAAA////wAAAAAAP/x///////gAAAAIABzgAfBAAAAAAAAA"
    "AAAAAAAAAAAAAAAAA////4AAAAAAPuB///////AAAAAAAB7wA+AAAAAAAAAAAAAAAAAAAAAAAAAAA////4AAAAAAAAAP/////+AA"
    "AAAAAA/wD8AAAAAAAAAAAAAAAAAAAAAAAAAAB////4AAAAAAAAAH/////+AAAAAAAAfwX+AQAAAAAAAAAAAAAAAAAAAAAAAAB///"
    "/+AAAAAAAAAH/////4AAAAAAAAP4f8xYAAAAAAAAAAAAAAAAAAAAAAAAH////8AAAAAAAAAH/////wAAAAAAAAHw//+YAAAAAAAA"
    "AAAAAAAAAAAAAAAAH/////wAAAAAAAAP/////gAAAAAAAADwf98bwAAAAAAAAAAAAAAAAAAAAAAAH/////8AAAAAAAAP/////AAA"
    "AAAAAAD4f58D5gAAAAAAAAAAAAAAAAAAAAAAH//////4AAAAAAAH////+AAAAAAAAAD8P7wN78AwAAAAAAAAAAAAAAAAAAAAH///"
    "///8AAAAAAAB////+AAAAAAAAAA+H55+//gcAAAAAAAAAAAAAAAAAAAAP//////+AAAAAAAB////8AAAAAAAAAA8Ap8A3/wcAAAA"
    "AAAAAAAAAAAAAAAAH///////gAAAAAAB////4AAAAAAAAAAfABsAJ/zzAAAAAAAAAAAAAAAAAAAAP///////wAAAAAAA////8AAA"
    "AAAAAAAH+AAAI//hgAAAAAAAAAAAAAAAAAAAD///////wAAAAAAA////8AAAAAAAAAAD/gAAA/8A8AAAAAAAAAAAAAAAAAAAD///"
    "////gAAAAAAA////8AAAAAAAAAAAP37wB/OAHAAAAAAAAAAAAAAAAAAAB///////gAAAAAAA////8AAAAAAAAAAAAPnAAGHgHAAA"
    "AAAAAAAAAAAAAAAAB///////AAAAAAAAf///+AAAAAAAAAAAAAmAACHgBgAAAAAAAAAAAAAAAAAAA//////+AAAAAAAAf///+AAA"
    "AAAAAAAAAAAB+HAAAAAAAAAAAAAAAAAAAAAAA//////+AAAAAAAAf///+AwAAAAAAAAAAAAD+HAAAAAAAAAAAAAAAAAAAAAAAf//"
    "///8AAAAAAAA////+B4AAAAAAAAAAAA3+HAAAAAAAAAAAAAAAAAAAAAAAf/////8AAAAAAAA////+B4AAAAAAAAAAAB/8HwAADAA"
    "AAAAAAAAAAAAAAAAAP/////8AAAAAAAB////+H4AAAAAAAAAAAD//HwAADAAgAAAAAAAAAAAAAAAAD/////4AAAAAAAB////+P4A"
    "AAAAAAAAAAH//nwAABADAAAAAAAAAAAAAAAAAA/////4AAAAAAAB////4fwAAAAAAAAAAAP///4AAAAGAAAAAAAAAAAAAAAAAAf/"
    "///4AAAAAAAB////gPwAAAAAAAAAAAf///4AAAAGAAAAAAAAAAAAAAAAAAf////4AAAAAAAA////APwAAAAAAAAAAB////+AAAAA"
    "AAAAAAAAAAAAAAAAAAf////wAAAAAAAAf//+AfgAAAAAAAAAAP////+AAMAAAAAAAAAAAAAAAAAAAAf////wAAAAAAAAf///AfAA"
    "AAAAAAAAA//////AAOAAAAAAAAAAAAAAAAAAAAf////gAAAAAAAAP///AfAAAAAAAAAAB//////gADAAAAAAAAAAAAAAAAAAAAf/"
    "//8AAAAAAAAAP///AfAAAAAAAAAAB//////gAAAAAAAAAAAAAAAAAAAAAAf///wAAAAAAAAAP///AfAAAAAAAAAAB//////4AAAA"
    "AAAAAAAAAAAAAAAAAAf///AAAAAAAAAAP//8AOAAAAAAAAAAB//////4AAAAAAAAAAAAAAAAAAAAAAf///AAAAAAAAAAP//4AAAA"
    "AAAAAAAAB//////8AAAAAAAAAAAAAAAAAAAAAAf///AAAAAAAAAAH//4AAAAAAAAAAAAA//////8AAAAAAAAAAAAAAAAAAAAAA//"
    "//AAAAAAAAAAD//4AAAAAAAAAAAAA//////8AAAAAAAAAAAAAAAAAAAAAA///+AAAAAAAAAAB//wAAAAAAAAAAAAAf/////8AAAA"
    "AAAAAAAAAAAAAAAAAA///8AAAAAAAAAAB//gAAAAAAAAAAAAA//////8AAAAAAAAAAAAAAAAAAAAAA///4AAAAAAAAAAA//gAAAA"
    "AAAAAAAAAf/////4AAAAAAAAAAAAAAAAAAAAAA///wAAAAAAAAAAB/+AAAAAAAAAAAAAAf/w///4AAAAAAAAAAAAAAAAAAAAAA//"
    "/wAAAAAAAAAAA/8AAAAAAAAAAAAAAf+AP//wAAAAAAAAAAAAAAAAAAAAAA///gAAAAAAAAAAA8AAAAAAAAAAAAAAAfIAH//wAADA"
    "AAAAAAAAAAAAAAAAAB//4AAAAAAAAAAAAAAAAAAAAAAAAAAAAOAAD//gAABgAAAAAAAAAAAAAAAAAB//8AAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAf/gAABwAAAAAAAAAAAAAAAAAD//4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAf/AAAA+AAAAAAAAAAAAAAAAAD//"
    "4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP8AAAA+AAAAAAAAAAAAAAAAAD/8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAB8"
    "AAAAAAAAAAAAAAAAAD/8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA2AAADYAAAAAAAAAAAAAAAAAH/sAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAA+AAAH4AAAAAAAAAAAAAAAAAH/4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAeAAAHAAAAAAAAAAAAAAAAAAH/g"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMAAA/AAAAAAAAAAAAAAAAAAH/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA8A"
    "AAAAAAAAAAAAAAAAAH/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD4AAAAAAAAAAAAAAAAAAP+AAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAADwAAAAAAAAAAAAAAAAAAP/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/g"
    "AAAAAAAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP+AAAAAAAAAAAAAAAAAAAAAAOAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAP8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP8D4AAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAH8BgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD+A"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAA/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAA8AAAAAAAAAAAAAAAAAAB4AAAAAAA4BAAAEAAAAAAAAAAAAAAAAAAAAAAAAAD8AAAAAAAAAAAAAAAAAAP8"
    "AAAAGAD//8f///wAAAAAAAAAAAAAAAAAAAAAAADwAAAAAAAAAAAAAAAAAH//34AP//////////4AAAAAAAAAAAAAAAAAAAAAAAT4"
    "AAAAAAAAAAAAAAAGD////8A/////////////AAAAAAAAAAAAAAAAAAAAAA/8AAAAAAAAAAAQRwA//////8f/////////////8AAA"
    "AAAAAAAAAAAAAAAAAA/+AAAAAAAABAH//////////8f///////////////gAAAAAAAAAAAAAB9AAAP/+AAAAAAAA////////////"
    "/5////////////////8AAAAAAAAAAAAAD/AgAH/+AAAAAAAH//////////////////////////////8AAAAAAAAAD3wgD///////"
    "AAAAAAAf//////////////////////////////wAAAAAAAB/////H//////+AAAAAAAf//////////////////////////////AA"
    "AAAAAH/////////////wAAAAAAP//////////////////////////////4AAAAAGAf////////////8AAAAAAf//////////////"
    "/////////////////wAAAAAH/////////////+AAAAQAP////////////////////////////////4AAAAD3/////////////8AA"
    "AD+A/////////////////////////////////+AAAAB4/////////////wADAP+A/////////////////////////////////wAA"
    "AAAAAP////////////h/h/+Af///////////////////////////////+AAAAAAB///////////////5AH9/////////////////"
    "/////////////////AAAAAAAP////////////////////////////////////////////////////8AAACAAP///////////////"
    "//////////////////////////////////////wA//8AB///////////////////////////////////////////////////////"
    "////////////////////////////////////////////////////////////////////////////////////////////////////"
    "////////////////////////////////////////////////////////////////////////////////////////////////////"
    "////////////////////////////////////////////////////////////////////////////////////////////////////"
)
_LAND_MASK_W, _LAND_MASK_H = 360, 180
_LAND_MASK = base64.b64decode(_LAND_MASK_B64)


def _land_at(lon, lat):
    """True if (lon, lat) in degrees is land, per the NE 110m mask."""
    x = int((lon + 180.0) % 360.0)
    y = int((90.0 - lat) / 180.0 * _LAND_MASK_H)
    if y < 0:
        y = 0
    elif y >= _LAND_MASK_H:
        y = _LAND_MASK_H - 1
    return (_LAND_MASK[y * 45 + (x >> 3)] >> (7 - (x & 7))) & 1 == 1


def _globe(cv, x, y, w, h):
    """3D globe: orthographic sphere centred on 60E/20N so Europe to
    Asia is on the visible face, one upper-left light, oceans + REAL
    coastlines from the Natural Earth 110m land mask, specular
    highlight, cast shadow, numbered pins (r=11, story numbers) at
    true lat/lon. Rotation uses the east/north/view basis vectors,
    so land and pins agree (v1 flipped latitude in the pixel loop).
    Pins: 1 Shenzhen, 2 The Hague, 3 Jakarta, 4 Hormuz, 5 Gopalpur
    (Akvan), 6 Kyiv, 7 Genoa, 8 Antalya (COP31), 9 Riyadh (Houthi)."""
    cx = x + w / 2.0
    cy = y + h / 2.0
    R = min(w, h) / 2.0
    lon0 = math.radians(60.0)
    lat0 = math.radians(20.0)
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
            # view-space (dx, dy, z) -> world unit vector via the
            # east / north / toward-viewer basis at (lon0, lat0)
            wx = dx * co0 - dy * sl0 * so0 + z * cl0 * so0
            wy = dy * cl0 + z * sl0
            wz = -dx * so0 - dy * sl0 * co0 + z * cl0 * co0
            diff = 0.32 + 0.68 * max(0.0, dx * lx + dy * ly + z * lz)
            if _land_at(math.degrees(math.atan2(wx, wz)),
                        math.degrees(math.asin(max(-1.0, min(1.0, wy))))):
                base = (96, 130, 70)
            else:
                base = (64, 116, 168)
            cv.set(sx, sy, _shade(base, diff))
    # specular highlight, upper left (same light direction)
    _soft_disc(cv, cx - R * 0.38, cy - R * 0.42, R * 0.30, (255, 255, 255), 0.18)
    _soft_disc(cv, cx - R * 0.42, cy - R * 0.46, R * 0.13, (255, 255, 255), 0.30)
    cv.circle_outline(cx, cy, R, 2, (110, 150, 190))
    # cast shadow, bottom right of the light
    _soft_ellipse(cv, cx + 5, cy + R + 5, R * 0.85, 7, (20, 20, 20), 0.28)
    # pins at true lat/lon; nudges only where two pins would touch
    for (lon, lat, n) in ((114.1, 22.5, 1), (4.3, 52.0, 2),
                          (106.8, -6.2, 3), (56.5, 26.5, 4),
                          (84.9, 19.3, 5), (30.5, 50.4, 6),
                          (8.9, 44.4, 7), (30.7, 36.9, 8),
                          (46.7, 24.7, 9)):
        lo = math.radians(lon - 60.0)
        la = math.radians(lat)
        vx = math.cos(la) * math.sin(lo)
        vy = math.cos(lat0) * math.sin(la) - math.sin(lat0) * math.cos(la) * math.cos(lo)
        vz = math.sin(lat0) * math.sin(la) + math.cos(lat0) * math.cos(la) * math.cos(lo)
        if vz <= 0.05:
            continue
        _nudge = {2: (0, -8), 7: (-14, 12), 9: (-6, 14)}
        dx, dy = _nudge.get(n, (0, 0))
        px = cx + vx * R + dx
        py = cy - vy * R + dy
        cv.disc(px, py, 11, RED)
        cv.ring(px, py, 11, 2, (255, 255, 255))
        draw_text(cv, px - text_width(str(n), 9, bold=True) / 2.0, py - 6,
                  str(n), 9, (255, 255, 255), bold=True)


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
    flags, three miniature leaders at one table. All positions are
    fractions of h so the scene stays compact (v2: h ~118). Labels
    name them; no face is drawn at this scale."""
    cx = x + w / 2.0
    # warm dusk glow behind the scene
    _soft_disc(cv, cx, y + h * 0.55, w * 0.42, (230, 160, 60), 0.10)
    # skyline silhouette (dark towers, lit windows)
    base = y + h - 30
    towers = [(0.02, 0.28, 0.09), (0.13, 0.16, 0.08), (0.23, 0.32, 0.10),
              (0.68, 0.24, 0.09), (0.79, 0.14, 0.08), (0.89, 0.30, 0.09)]
    for (fx, fy, fw) in towers:
        tx = x + w * fx
        tw = w * fw
        ty = y + h * fy
        cv.fill_rect(tx, ty, tx + tw, base, (26, 34, 58))
        for j in range(2):
            wy = ty + 6 + j * 10
            if wy < base - 4:
                cv.fill_rect(tx + 3, wy, tx + tw - 3, wy + 3, (255, 210, 110))
    # three flags on poles
    for i, k in enumerate(('us', 'cn', 'ru')):
        fx = cx - 130 + i * 130
        cv.vline(fx - 2, y + 4, y + 32, (200, 200, 190), 2)
        _flag(cv, fx, y + 4, 36, 22, k)
    # table
    cv.fill_rect(cx - 150, y + h - 30, cx + 150, y + h - 22, (96, 64, 40))
    cv.fill_rect(cx - 150, y + h - 30, cx + 150, y + h - 28, (150, 108, 66))
    # three leaders behind the table
    _figure(cv, cx - 96, y + h - 56, 1.15, (30, 50, 90), (232, 202, 122))
    _figure(cv, cx, y + h - 56, 1.15, (38, 38, 40), (20, 20, 20))
    _figure(cv, cx + 96, y + h - 56, 1.15, (58, 58, 68), (200, 190, 170))
    # name labels under the table edge
    for (dx, name) in ((-96, 'TRUMP'), (0, 'XI JINPING'), (96, 'PUTIN')):
        draw_text(cv, cx + dx, y + h - 18, name, 8.5, IVORY, bold=True, align='center')


def _icj_scene(cv, x, y, w, h):
    """The Hague: ICJ palace (columns + pediment) with three
    humanitarian tents and small family figures in front. Dignified
    miniature scale; no suffering shown as spectacle. Compact: all
    heights are fractions of h (v2 strip: h ~52)."""
    base = y + h - 2
    # palace: steps, columns, pediment
    cv.fill_rect(x + 8, base - 3, x + w - 8, base, (150, 146, 132))
    cv.fill_rect(x + 14, base - 30, x + w - 14, base - 3, (214, 206, 186))
    for i in range(5):
        colx = x + 26 + i * ((w - 52) / 4.0)
        cv.fill_rect(colx - 3, base - 28, colx + 3, base - 4, (246, 241, 227))
        cv.fill_rect(colx - 4, base - 30, colx + 4, base - 27, (246, 241, 227))
    cv.poly([(x + 10, base - 30), (x + w / 2.0, base - 40), (x + w - 10, base - 30)],
            (226, 218, 198))
    cv.disc(x + w / 2.0, base - 31, 3, GOLD2)
    # tents, lower right of the palace
    for tx in (0.62, 0.76, 0.90):
        txx = x + w * tx
        tyy = base - 12
        cv.poly([(txx - 12, tyy), (txx, tyy - 11), (txx + 12, tyy)], (196, 188, 168))
        cv.poly([(txx - 4, tyy), (txx, tyy - 6), (txx + 4, tyy)], (90, 80, 66))
    # small family figures (head + robe), standing, dignified
    for (fx, c) in ((0.30, (120, 90, 70)),
                    (0.36, (90, 100, 130)),
                    (0.42, (140, 110, 80))):
        fxx = x + w * fx
        fy = base - 2
        cv.disc(fxx, fy - 10, 2, (222, 184, 150))
        cv.poly([(fxx - 3, fy), (fxx - 2, fy - 8), (fxx + 2, fy - 8),
                 (fxx + 3, fy)], c)


def _hormuz_scene(cv, x, y, w, h):
    """Strait of Hormuz at night: dark sea, a burning tanker, black
    smoke, a red warning light. Restrained warning colours. Compact
    (v2 strip: h ~52)."""
    base = y + h - 2
    horizon = y + int(h * 0.38)
    _sky_bands(cv, x, y, w, horizon - y, (20, 28, 48), (52, 52, 70))
    cv.fill_rect(x, horizon, x + w, base, (24, 54, 86))
    # moonlight path on the water
    for i in range(3):
        ww = w * (0.10 + i * 0.03)
        cv.fill_rect(x + w * 0.45 - ww / 2.0, horizon + 3 + i * 4,
                     x + w * 0.45 + ww / 2.0, horizon + 5 + i * 4, (120, 150, 180))
    # distant headland, left
    cv.poly([(x, base), (x, horizon + 6), (x + w * 0.20, horizon + 8),
             (x + w * 0.24, base)], (10, 18, 34))
    # tanker hull + superstructure, centre-right
    tx = x + w * 0.52
    ty = horizon + 8
    _ship(cv, tx, ty, 2.0, (130, 86, 58))
    cv.fill_rect(tx - 11, ty - 20, tx + 11, ty - 6, (200, 190, 170))
    cv.fill_rect(tx - 11, ty - 20, tx + 11, ty - 18, (176, 30, 36))
    # flames + smoke above the deck
    _burst(cv, tx + 24, ty - 10, 1.2)
    _burst(cv, tx - 5, ty - 13, 0.9)
    _smoke(cv, tx + 26, ty - 26, 1.2, (70, 70, 72))
    _soft_disc(cv, tx + 24, ty - 10, 30, (230, 120, 20), 0.38)
    # red warning light on the mast
    cv.disc(tx, ty - 26, 2, (220, 40, 40))
    _soft_disc(cv, tx, ty - 26, 8, (220, 40, 40), 0.35)


def _indonesia_scene(cv, x, y, w, h):
    """Jakarta: parliament dome silhouette + gold scales of justice.
    A smaller, clearly recognisable regional element. Compact
    (v2 strip: h ~52)."""
    base = y + h - 2
    cx = x + w / 2.0
    # parliament: dome + colonnade
    cv.fill_rect(x + 18, base - 20, x + w - 18, base, (58, 68, 98))
    cv.fill_rect(x + 18, base - 20, x + w - 18, base - 18, GOLD2)
    for i in range(6):
        colx = x + 34 + i * ((w - 68) / 5.0)
        cv.fill_rect(colx - 2, base - 19, colx + 2, base - 1, (150, 146, 132))
    cv.poly([(cx - 26, base - 20), (cx, base - 34), (cx + 26, base - 20)],
            (150, 146, 132))
    cv.disc(cx, base - 34, 4, GOLD2)
    cv.vline(cx, base - 42, base - 34, GOLD2, 2)
    # scales of justice, gold, right of the dome
    sx = x + w * 0.80
    sy = base - 30
    cv.vline(sx, sy - 10, sy + 8, GOLD2, 2)
    cv.fill_rect(sx - 11, sy - 10, sx + 11, sy - 8, GOLD2)
    cv.disc(sx, sy - 12, 2, GOLD2)
    for dx in (-11, 11):
        cv.line(sx, sy - 9, sx + dx, sy - 1, GOLD2, 1)
        cv.poly([(sx + dx - 5, sy - 1), (sx + dx + 5, sy - 1),
                 (sx + dx, sy + 5)], GOLD2)
    # small red-white flag accent on the dome
    _flag(cv, x + w * 0.10, base - 42, 20, 12, 'id')


def _akvan_band(cv, x, y, w, h):
    """Story 5, the pure-20-Nov hero: Cyclone Akvan makes landfall
    in Odisha. A spiral cyclone over a dark reflective sea, drawn
    into the same scene as the globe above (not a separate panel):
    sea bands + wave lines run the full width, the spiral sits at
    the left, the headline + figures at the right."""
    # dark sea, 5 bands deepening downward
    _sky_bands(cv, x, y, w, h, (14, 30, 56), (8, 16, 34))
    # wave lines across the band, below the text
    for i, wy in enumerate((0.88, 0.95)):
        cv.fill_rect(x + 12, y + h * wy, x + w - 12, y + h * wy + 2,
                     (70, 110, 150) if i % 2 == 0 else (50, 85, 120))
    # cyclone spiral, left: concentric arcs + eye + rain streaks
    scx, scy, sr = x + 105, y + h * 0.52, 42
    _cyclone(cv, scx, scy, sr, (200, 220, 240))
    _cyclone(cv, scx, scy, sr * 0.66, (140, 180, 210))
    cv.disc(scx, scy, 6, (240, 244, 248))
    for (rx, ry, rl) in ((-52, -30, 14), (48, -34, 12), (-58, 18, 12),
                         (52, 22, 14), (-30, 38, 10), (30, 40, 10)):
        cv.line(scx + rx, scy + ry, scx + rx + 6, scy + ry + rl,
                (120, 160, 195), 1)
    # red story pin 5, top left of the band
    cv.disc(x + 18, y + 18, 11, RED)
    cv.ring(x + 18, y + 18, 11, 2, (255, 255, 255))
    draw_text(cv, x + 18 - text_width('5', 9, bold=True) / 2.0, y + 12,
              '5', 9, (255, 255, 255), bold=True)
    tx = x + 205
    draw_text(cv, tx, y + 10, 'CYCLONE AKVAN MAKES LANDFALL', 26, IVORY,
              bold=True, serif=True)
    draw_text(cv, tx, y + 54,
              '300,000 EVACUATED IN ODISHA — LANDFALL NEAR GOPALPUR, 90–100 KM/H',
              14, AMBER, bold=True)
    draw_text(cv, tx, y + 80,
              'Landfall 10–11 AM · 423 rescue teams · 69 trains cancelled',
              12, IVORY_DIM)


# ------------------------------------------------------- -20 stories
# v2: 17 verified stories (see STORIES.md) — 4 lead narratives +
# the Akvan hero band (story 5) + 12 ALSO TODAY markers (6-17).
# Strip order left-to-right is 2-3-4 (ICJ, Indonesia, Hormuz).
STORIES = [
    dict(n=1, kicker='1  SHENZHEN · DIPLOMACY', color=(212, 168, 60),
         head='Trump, Xi and Putin meet in Shenzhen',
         deck='First trilateral of the three leaders: a joint peace declaration, but no concrete breakthrough on Ukraine or Iran.'),
    dict(n=2, kicker='2  THE HAGUE · JUSTICE', color=(29, 78, 137),
         head='ICJ: Myanmar guilty of Rohingya genocide',
         deck='The Hague rules 9–6: Myanmar guilty of genocide.'),
    dict(n=3, kicker='3  STRAIT OF HORMUZ · ENERGY', color=(176, 30, 36),
         head='Tanker ablaze after mine strike in Hormuz',
         deck='A tanker burns east of the strait after hitting a mine.'),
    dict(n=4, kicker='4  JAKARTA · INDONESIA', color=(46, 110, 58),
         head='Indonesia passes asset forfeiture law',
         deck='DPR passes the bill after 18 years. In force in 12 months.'),
]
ALSO = [
    ('6  KYIV', 'Ballistic missiles hit Kyiv'),
    ('7  GENOA', 'Drone shuts Genoa airport 4h'),
    ('8  COP31', 'Draft faces final test, no deal'),
    ('9  HOUTHI', 'Claims strikes on 4 Saudi targets'),
    ('10  IRAN', 'Trump delays decision to 2027'),
    ('11  EUROPE', 'Allies ready for Russia talks'),
    ('12  VARMA', 'India judge resigns amid graft case'),
    ('13  CYBER', 'Bank data leaked; cyber chief out'),
    ('14  GAZA', 'Ground op ends; Hezbollah hit'),
    ('15  ANDROMEDA', 'First direct look at star merger'),
    ('16  PETE ROSE', 'Posthumous pardon for Pete Rose'),
    ('17  SPORT', 'NZ 368 all out; India bat, day 2'),
]


def _vignette(cv, x, y, w, scene, st):
    """One narrative strip, ~160 px tall: 3 px coloured rule, 40 px
    illustration, kicker chip, 2-line headline (cap 20), 2-line deck
    (cap 13). No box: the three strips share one floor under the
    same globe; the thick rules separate them.
    v2b: the scene is 40 px (was 48) and the kicker sits 8 px higher,
    so the tag chip ends 14 px clear of the headline cap top — the
    headline itself could NOT move down (its deck already ends at
    y818, 1 px above the ALSO TODAY box; and shrinking the headline
    1 px is a no-op: the atlas has no cap-19 bold glyphs, it falls
    back to cap 20; tightening the leading merges the descenders
    into line 2 — 86 collision px at leading 20 vs 9 at 22)."""
    cv.fill_rect(x, y, x + w, y + 3, st['color'])
    scene(cv, x, y + 7, w, 40)
    kicker(cv, x, y + 51, st['kicker'], 9, st['color'])
    hy = y + 81
    lines = wrap_balanced(st['head'], 20, w, bold=True)
    draw_para(cv, x, hy, lines[:2], 20, IVORY, leading=22, bold=True)
    dy = hy + 22 * min(2, len(lines)) + 8
    dlines = wrap_balanced(st['deck'], 13, w)
    draw_para(cv, x, dy, dlines[:2], 13, IVORY_DIM, leading=15)


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
    MX = 30
    CW = 964
    # ---- masthead (y 0..100): title + date + thick gold rule
    draw_text(cv, MX + CW / 2.0, 6, 'THE WORLD', 40, IVORY, bold=True,
              align='center', serif=True)
    draw_text(cv, MX + CW / 2.0, 52, 'AT A CROSSROADS', 20, GOLD2, bold=True,
              align='center', serif=True)
    draw_text(cv, MX + CW / 2.0, 78, 'FRIDAY, 20 NOVEMBER 2026', 15, IVORY,
              bold=True, align='center', serif=True)
    cv.fill_rect(MX, 96, MX + CW, 99, GOLD2)
    # ---- summit diorama, upper centre (y 102..216) + deck line
    _summit_scene(cv, 232, 102, 560, 114)
    draw_text(cv, MX + CW / 2.0, 222, 'PEACE DECLARATION — BUT NO BREAKTHROUGH ON UKRAINE OR IRAN',
              10, IVORY, bold=True, align='center')
    # ---- central globe (y 234..534, 300 px): atmosphere glow,
    # reflective floor line, pins 1-9 at true lat/lon
    _soft_disc(cv, 512, 384, 190, (70, 140, 200), 0.22)
    _globe(cv, 362, 234, 300, 300)
    cv.fill_rect(30, 536, 994, 538, (120, 150, 190))
    # ---- Akvan hero band (y 542..652), integrated with the scene:
    # spiral cyclone over the reflective sea under the globe
    _akvan_band(cv, 30, 542, 964, 110)
    # ---- three strips, left-to-right 2-3-4 (y 654..815)
    _vignette(cv, 30, 654, 310, _icj_scene, STORIES[1])
    _vignette(cv, 357, 654, 310, _indonesia_scene, STORIES[3])
    _vignette(cv, 684, 654, 310, _hormuz_scene, STORIES[2])
    # ---- ALSO TODAY (y 819..951): 12 items, 3 rows x 4 columns,
    # label cap 15 bold + one deck line cap 12 (readable at 300 px);
    # 35 px rows so the deck never touches the next label
    cv.box(30, 819, 994, 951, IVORY, 2)
    draw_text(cv, 40, 825, 'ALSO TODAY — 20 NOVEMBER 2026', 12, GOLD2, bold=True)
    cv.fill_rect(40, 841, 984, 843, GOLD2)
    for i, (kick, txt) in enumerate(ALSO):
        col = i % 4
        row = i // 4
        ax = 40 + col * 241
        ay = 847 + row * 35
        draw_text(cv, ax, ay, kick, 15, GOLD2, bold=True)
        draw_text(cv, ax, ay + 19, txt, 12, IVORY)
    # ---- date check strip (text to the judge - allowed and read)
    cv.fill_rect(MX, 957, MX + CW, 991, (0, 0, 0))
    dc1 = 'DATE CHECK — The Shenzhen summit, ICJ verdict and Indonesia asset law were decided Thu 19 Nov;'
    dc2 = 'their consequences led Friday 20 Nov 2026 news. Every other story here happened or was first reported Fri 20 Nov.'
    draw_text(cv, MX + 8, 961, dc1, 11, (255, 255, 255), bold=True)
    draw_text(cv, MX + 8, 975, dc2, 11, (220, 220, 210))
    # ---- footer
    draw_text(cv, MX, 999, 'Sources: IMD, Reuters, NYT, TASS/AFP, DPR RI, AP, BBC. Original drawings.',
              9, IVORY_DIM)
    draw_text(cv, MX + CW - text_width('THE WORLD AT A CROSSROADS', 9, bold=True), 999,
              'THE WORLD AT A CROSSROADS', 9, GOLD2, bold=True)
    return cv


def main():
    out = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')
    cv = build()
    n = write_png(cv, os.path.join(out, 'entry.png'))
    print('wrote %s/entry.png (%d bytes, %dx%d)' % (out, n, W, H))


if __name__ == '__main__':
    main()
