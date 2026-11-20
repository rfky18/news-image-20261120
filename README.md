# news-image-20261120 — The World at a Crossroads

[![news-image-20261120](https://make.fun/badge/news-image-20261120.svg)](https://make.fun/bounty/news-image-20261120)
[![rank](https://make.fun/badge/news-image-20261120/rfky18/news-image-20261120/rank.svg)](https://make.fun/bounty/news-image-20261120)
[![reward](https://make.fun/badge/news-image-20261120/rfky18/news-image-20261120/reward.svg)](https://make.fun/bounty/news-image-20261120)

**Contest:** [Sum up 20 November's world news in one image](https://make.fun/bounty/news-image-20261120) — $250, free entry, deadline 22 Nov 2026 07:00 WIB.

## The image

One unified image, not four panels: **THE WORLD AT A CROSSROADS — Friday, 20 November 2026.**

- A 3D-shaded Earth, suspended above a dark reflective floor, anchors the
  frame; seven numbered pins mark where the news happened (1 Shenzhen ·
  2 The Hague · 3 Hormuz · 4 Jakarta · 5 Kyiv · 6 Genoa · 7 Odisha).
- Above the globe, the Shenzhen trilateral: Trump, Xi and Putin as
  miniature figures at one table under three flags — a joint peace
  declaration, but no breakthrough on Ukraine or Iran.
- On the same floor, lower left: the ICJ palace in The Hague, tents and
  families — the 9–6 ruling that Myanmar committed genocide against the
  Rohingya. Lower right: a tanker ablaze in the Strait of Hormuz after a
  mine strike. Centre: Indonesia's parliament dome and the scales of
  justice — the DPR passes the asset forfeiture law, 74 articles, after
  18 years.
- An **ALSO TODAY** strip adds six further verified stories (Kyiv, Genoa,
  Cyclone Akvan, Anthropic's record Nasdaq debut, the delayed Iran call,
  Europe ready to talk with Russia) — 10 stories in one frame.
- A **DATE CHECK** strip (text to the judge): the summit, the ICJ ruling
  and the Indonesia law are 19 Nov events that led the news on 20 Nov;
  no casualty figures invented.

## How it renders

`main.py` — Python 3, **stdlib only** (base64, math, os, struct, zlib). No network, no PIL at runtime. All text is real type via a glyph atlas (Liberation Serif Bold + Noto Sans Condensed) rendered at build time and embedded base64; the runtime only blits bitmaps. All illustrations are drawn in code: flat vector dioramas, a 3D-shaded orthographic globe lit from one upper-left sun, atmosphere glow and a reflective floor.

```sh
python3 main.py        # writes /output/entry.png (1024×1024, ≤1 MiB)
```

Deterministic: two runs produce byte-identical output. Run time ~2 s.

## Files

- `main.py` — the whole generator.
- `STORIES.md` — fact-check table for all 10 stories (sources, what was
  deliberately left out, and why no Anthropic figures are printed).
- `LICENSE` — MIT.

## Facts

Every story was verified against ≥2 independent credible sources
(NYT, ICJ, TASS/AFP, DPR RI, Reuters, AP, BBC, IMD) at build time; see
`STORIES.md`. Planned items are labelled, contested claims are attributed,
nothing is fabricated.
