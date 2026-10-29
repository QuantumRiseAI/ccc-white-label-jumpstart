# Unity Biomedicines Design System: "Clinical teal"

The look of the Unity Biomedicines, Inc. close consoles (GL Coding Review and P&L Flux).
Unity Biomedicines is a fictional client used for demonstrations: NetSuite entity
"PL87 Unity Biomedicines, Inc.", a subsidiary of Plurality Group.

Machine-readable values live in [`tokens.css`](tokens.css). The console build carries the
same values inline in `src/client_design.py` (`TOKENS`, `MONOGRAM`, `LOGO`), and
`src/client_fonts.py` inlines the font, so a generated page is one self-contained file.

## The idea

A work paper for an accounting close at a life-sciences company. It should read as
biotech at a glance and then get out of the way of the numbers.

* **Clinical, not decorative.** White cards on a cool-gray page, deep slate ink, one deep
  teal for the rail and for every action. Nothing moves except on interaction.
* **One accent, used small.** Cyan marks focus rings, the monogram's atoms and chart
  highlights. It never carries text on a light ground.
* **Status stays apart from brand.** Ok, warn and error are green, amber and red, chosen so
  none of them can be mistaken for the teal.
* **Data first.** One sans with tabular figures, so every amount lines up in its column.
  Dense tables, hairline rules, a light card shadow instead of heavy borders.

## Palette

| Token | Value | Use |
|---|---|---|
| `--color-light-gray` | `#eef3f5` | Page ground |
| `--color-white` | `#ffffff` | Cards, tables |
| `--color-hairline` | `#d8e1e6` | Rules and table lines |
| `--color-surface-2` | `#dfe8ec` | Secondary ground, group rows |
| `--color-dark-gray` | `#0f2e36` | Ink: body text, figures |
| `--color-mid-gray` | `#4a5f68` | Secondary text, column heads |
| `--color-inactive` | `#7d9199` | Inactive, placeholders |
| `--color-teal` | `#0b6e75` | Primary: buttons, links, active tabs |
| `--color-teal-hover` | `#095a61` | Primary hover |
| `--color-teal-tint` | `#e6f3f4` | Selected rows, drafts |
| `--color-teal-deep` | `#0b3d47` | Header rail, heroes |
| `--color-teal-mid` | `#0f4c57` | Sub-navigation bar |
| `--color-warm-gray` | `#9cc0c8` | Secondary text on the rail |
| `--color-cyan` | `#0e9fac` | Accent marks, focus |
| `--color-cyan-light` | `#5fd4dd` | Accent on the rail |

The neutral slot names (light, warm, mid, dark gray; red) are kept because the console
CSS reads them; the values are the clinical-teal palette. `--color-red` now resolves to
the cyan accent, and `--color-red-text` to the error red.

### Contrast (WCAG 2.2)

| Pair | Ratio | Bar |
|---|---|---|
| Ink `#0f2e36` on white | 14.0:1 | AA text |
| Ink on the page `#eef3f5` | 12.5:1 | AA text |
| Secondary `#4a5f68` on white | 6.7:1 | AA text |
| Secondary on the page | 6.0:1 | AA text |
| White on teal `#0b6e75` | 6.0:1 | AA text |
| Teal on its tint `#e6f3f4` | 5.3:1 | AA text |
| Rail text `#9cc0c8` on the rail `#0b3d47` | 5.3:1 | AA text |
| Rail text on the sub bar `#0f4c57` | 4.9:1 | AA text |
| Light cyan `#5fd4dd` on the rail | 6.7:1 | AA text |
| Error on dark `#ffb4a8` on the rail | about 6:1 | AA text |
| Cyan `#0e9fac` on white | 3.2:1 | Non-text marks only |

## Status colors

| State | Token | Value | On white |
|---|---|---|---|
| Ok, tied, cleared | `--color-ok` | `#1e7a4a` | 5.3:1 |
| Warning, review | `--color-warn` | `#a15c00` | 5.2:1 |
| Error, critical, over | `--color-error` | `#b42318` | 6.6:1 |

Status is never carried by color alone: every mark also has a word or a count.

## Typography

* **Figtree** (SIL Open Font License) carries text, headings and numbers.
  It is a variable font; the consoles use 400 and 600, with 700 for the wordmark.
* **Hanken Grotesk** (OFL) is second in the stack, a close grotesque if Figtree does not load,
  then Helvetica Neue, Helvetica and Arial.
* Figures are tabular everywhere (`font-variant-numeric: tabular-nums` on `body`), so amounts
  align in columns without a monospace face. Codes and IDs use `--font-mono`.
* The type scale is fluid (`--text--2` to `--text-4`), from 12.5px table text to hero figures.

## The monogram

A hexagon ring holding three atoms bonded to one center: three parts made one, for "Unity".
It is drawn inline as a 32 by 32 SVG (`MONOGRAM` in `src/client_design.py`):

* the ring, the bonds and the center atom take `currentColor` (white on the rail);
* the three outer atoms take `--color-cyan-light`.

The lockup sets the monogram beside a two-line wordmark: **Unity** in Figtree 700, and
BIOMEDICINES below it in small spaced capitals in light cyan. On the 52px rail the monogram
is 28px. Keep clear space of at least half the monogram's width around the lockup; do not
recolor, rotate or outline it.

## Shape and depth

* Radii: 4px controls, 8px cards and tiles, 10px tab panels, pill for badges.
* Depth: one soft card shadow (`--shadow-card`), a 1px ring plus a 1px drop. No hover lift.
* Focus: a 2px cyan outline, offset 2px, on every interactive element.

## Components

* **Rail.** Deep teal header with the lockup, the console name and the period; a mid-teal
  sub-bar beneath it for navigation.
* **Hero.** Key figures on the deep teal; unfavorable or changed figures in `#ffb4a8`.
* **Cards and tiles.** White, 8px radius, card shadow, title in 600.
* **Tables.** Hairline rows, secondary-color column heads, right-aligned tabular figures,
  teal-tint for the selected row.
* **Buttons.** Solid teal primary; ghost buttons are teal on white and turn tint on hover.
* **Badges.** Status color text on a pale tint of the same hue, pill shaped.

`tokens.css` includes a minimal version of the card, badge, button and table rules.

## Motion

Short and functional: 0.15s presses, 0.2s hovers, 0.25s controls, `--ease-out`. All
transitions collapse under `prefers-reduced-motion`.

## Files

* [`tokens.css`](tokens.css): every custom property, base styles and a few components.
* [`fonts-open/`](fonts-open/): Figtree and Hanken Grotesk woff2 files, `fonts.css` with the
  `@font-face` rules, and their OFL license texts (`OFL-Figtree.txt`, `OFL-HankenGrotesk.txt`).
