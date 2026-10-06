#!/usr/bin/env python3
"""Turn a run artifact into one self-contained HTML close-review console.

    python3 build_report.py <run.json> [-o <out.html>]

Stdlib only. No Node, no build step, no network. Python 3.9+. The output is a
single file that opens from file:// and carries the run inlined.

It is a working surface, not a report. A controller opens it to DO something:
triage findings, disposition each one Approve / Reject / Modify with a note,
watch the outstanding count fall, and export a decision log and a proposed-entry
list for the close file. Decisions persist in the browser, keyed to the run id.

BRAND. Colors, typefaces and usage follow the Serif Brand Guide on Brandpad
(brandpad.io/serif, May 2026). Floods of Dark Gray and Light Gray carry the page;
Mid Gray and Warm Gray are the secondary neutrals; Red is a highlight and never
a fill behind text.

TYPEFACES. The brand faces are Denim (sans) and Eliza (serif), both licensed
commercial faces. They are NOT embedded here: redistributing a licensed font
inside a deliverable is a licensing decision, not a build step. The stacks below
name them first, so if Serif installs them they take effect with no code change.
Until then serif_fonts.py inlines open-licensed stand-ins (Figtree, PT Serif),
and after those come the fallbacks the brand names: Helvetica or Arial, and
Georgia. Denim sets headlines and all text; Eliza sets only a short highlight
inside a headline and the headline figures.

STATE COLOR is a status palette, not a series palette. It carries two states: at
or over the fix threshold, and under it. Both are rendered as text as well as as a
mark, so both clear WCAG AA for text on a white card -- #c72e00 at 5.50:1 and
Mid Gray #525046 at 8.09:1 -- and they stay apart in hue under every CVD
simulation. Every mark is directly labeled regardless, so color is
never the only carrier.

GRADING is by money, not by adjective. The question a finding has to answer is
whether it clears the amount at which an exception gets corrected, which is a
yes-or-no test, so the threshold is a control the reviewer sets rather than a
property each rule assigns. Confidence is reported separately, because how large
an exception is and how sure the engine is about it are different questions.

CONFIDENTIALITY: the output contains real Serif financials. Sending it anywhere
is a client-data decision, not a convenience. Route through CCC.
"""

import argparse
import json
import re
import os
import sys

# Three things version independently and a reader needs all three to know why an
# output changed:
#   CONSOLE_VERSION  this file, the views, the decision vocabulary, the layout
#   engine_version   the engine that produced run.json
#   ruleset_version  the rules that engine applied
# Plus the run itself: run_id and the sha256 of every input.
# Bump CONSOLE_VERSION on any change a reviewer would notice. If the decision
# vocabulary changes, bump STORE_VERSION in the JS too, or decisions recorded
# under the old verbs are restored against actions that no longer exist.
CONSOLE_VERSION = "1.8.8"

# Every name a reviewer reads for a page or an outcome lives here and nowhere else.
# The console reads them from the page (window.__SERIF_LABELS__), so renaming
# Review or Decisions, which waits on Scott (AIJ-110), is a change to this one
# dict. The stored values (clear, question, entry, manual, reclass; book,
# no_entry) never change with a label, so decisions saved under one name load
# under another. Prose that names an outcome ("choose Cleared") is written in the
# schedules' What to do text and would need its own sweep.
LABELS = {
    "pages": {"overview": "Overview", "all_findings": "All findings", "review": "Review",
              "adjustments": "Adjustments", "flux": "Flux pack", "entries": "Journal Entries",
              "decisions": "Decisions", "record": "Record"},
    "outcomes": {"clear": "Cleared", "question": "Follow up", "entry": "Entry booked",
                 "manual": "Fixed in NetSuite", "reclass": "Line by line"},
    # How Decisions groups what was decided, and what is left.
    "groups": {"import": "In the NetSuite import", "netsuite": "Fixed in NetSuite",
               "none": "No action", "follow": "Follow up", "open": "Still open",
               "check": "Check before the upload"},
}

# What one close run would cost through the API, priced at list. A Claude Project run
# is covered by the Claude seat, so this is an estimate built from the Project's files
# and the run itself; every input is shown on the Cost page. A run is agentic: Claude
# reads the instructions, runs the three scripts, reads the findings to draft, writes
# the drafts, rebuilds the console and reports back, one model turn per step.
COST_PRICES = [{"model": "Claude Sonnet at medium effort", "input": 3.00, "cached": 0.30,
                "output": 15.00}]
COST_THINKING_TOKENS = 1_500   # thinking per turn at medium effort, billed as output
COST_SYSTEM_TOKENS = 20_000    # claude.ai's own system prompt and tool definitions
COST_SCRIPT_TOKENS = 2_000     # what each script prints for Claude to read
COST_READ_CHUNK = 10           # findings Claude reads per turn
COST_DRAFT_TOKENS = 150        # written per finding: commentary, a note or an entry line
COST_SUMMARY_TOKENS = 3_000    # the summary in the chat
COST_READ = (".md", ".sql", ".csv")   # Project files Claude reads; the scripts are run
CHARS_PER_TOKEN = 4


def cost_estimate(folder, run):
    """Tokens and dollars for one run of this Project on this run's findings."""
    try:
        names = sorted(n for n in os.listdir(folder)
                       if n.lower().endswith(COST_READ) and os.path.isfile(os.path.join(folder, n)))
        size = sum(os.path.getsize(os.path.join(folder, n)) for n in names)
    except OSError:
        return None
    if not names:
        return None
    tok = lambda n: n // CHARS_PER_TOKEN
    findings = run.get("findings", [])
    files, read = tok(size), tok(len(json.dumps(findings)))
    chunks = max(1, -(-len(findings) // COST_READ_CHUNK))
    # New input each turn: the context, three script outputs, the findings in chunks,
    # the rebuild's output, then the summary turn. Output is spread over the turns.
    adds = ([COST_SYSTEM_TOKENS + files] + [COST_SCRIPT_TOKENS] * 3
            + [read // chunks] * chunks + [COST_SCRIPT_TOKENS, 0])
    turns = len(adds)
    written = COST_DRAFT_TOKENS * len(findings) + COST_SUMMARY_TOKENS
    outs = [written // turns] * turns
    # Thinking is billed as output but is not sent back on later turns.
    output = written + COST_THINKING_TOKENS * turns
    fresh = cached = 0
    for i in range(turns):
        new = adds[i] + (outs[i - 1] if i else 0)
        fresh += new
        cached += sum(adds[:i]) + sum(outs[:i - 1]) if i else 0
    tokens = [("New input", fresh, "input"), ("Cached input", cached, "cached"),
              ("Output", output, "output")]
    priced = []
    for price in COST_PRICES:
        lines = [(label, n, price[k], n * price[k] / 1_000_000) for label, n, k in tokens]
        priced.append({"model": price["model"], "lines": lines, "total": sum(l[3] for l in lines)})
    return {"files": len(names), "file_tokens": files, "findings": len(findings),
            "read_tokens": read, "turns": turns, "priced": priced,
            "tokens": sum(n for _, n, _ in tokens)}


# Two states now, not four tiers: over the threshold and under it.
STATE_PALETTE = "#c72e00,#525046"

# Serif's own wordmark, taken from serifbiomedicines.com. The brand allows it in
# Dark Gray or White only; on the rail it is White.
LOGO_PATH = 'M41.734 42.272c-1.773-1.67-4.026-3.274-6.752-4.809-2.729-1.535-5.934-3.221-9.616-5.062-4.91-2.456-8.815-4.773-11.711-6.958-2.9-2.182-4.348-5.249-4.348-9.207 0-3.958 1.364-7.125 4.09-9.31 2.726-2.182 6.343-3.273 10.843-3.273 1.364 0 2.71.103 4.039.306 1.33.206 2.61.512 3.836.92l8.39 17.083h2.864V4.985C40.98 3.691 38.1 2.548 34.725 1.558 31.352.57 27.82.074 24.14.074c-3.273 0-6.379.444-9.31 1.33-2.932.887-5.475 2.181-7.621 3.887a18.922 18.922 0 0 0-5.114 6.24C.83 13.986.202 16.783.202 19.918c0 3.135.58 5.645 1.738 7.927a21.047 21.047 0 0 0 4.503 5.985c1.84 1.706 3.92 3.222 6.24 4.551 2.317 1.33 4.591 2.629 6.854 3.836 3.122 1.665 5.848 3.122 8.133 4.451 2.285 1.33 4.142 2.645 5.574 3.939 1.432 1.297 2.507 2.694 3.221 4.194.718 1.5 1.075 3.24 1.075 5.216 0 4.297-1.432 7.537-4.296 9.72-2.864 2.181-6.649 3.272-11.354 3.272-7.396.217-14.62-2.463-19.34-7.039L.202 68.485c5.399 5.315 13.653 8.433 21.582 8.106 3.48 0 6.768-.46 9.873-1.38 3.103-.921 5.78-2.286 8.03-4.091 2.25-1.806 4.042-4.059 5.371-6.752 1.33-2.694 1.995-5.78 1.995-9.259 0-2.797-.444-5.217-1.329-7.263-.888-2.047-2.217-3.904-3.99-5.574ZM115.595 35.774l-1.635 2.659h-.615l1.944-14.424h-9.922v51.147h16.571v-3.273H115.8V41.706c.545-1.294 1.178-2.42 1.893-3.376a15.546 15.546 0 0 1 2.404-2.558h13.706V24.009c-3.819.682-7.298 2.098-10.433 4.245-3.138 2.15-5.729 4.653-7.775 7.518v.002ZM150.428 24.011h-10.436V75.16h16.574v-3.273h-6.138V24.01ZM150.426 1.506h-10.434v10.442h10.434V1.506ZM88.74 65.031c-2.73 2.114-5.9 3.173-9.514 3.173-2.659 0-5.014-.563-7.058-1.69a14.974 14.974 0 0 1-5.114-4.602c-1.364-1.944-2.404-4.26-3.118-6.954-.718-2.694-1.075-5.61-1.075-8.747v-1.535h34.677c0-3.136-.48-6.07-1.432-8.799-.956-2.726-2.337-5.062-4.143-7.006-1.808-1.944-4.006-3.479-6.597-4.602-2.594-1.127-5.49-1.687-8.696-1.687-3.205 0-6.359.715-9.258 2.15-2.9 1.432-5.423 3.41-7.57 5.934-2.15 2.523-3.852 5.509-5.114 8.95-1.261 3.443-1.892 7.176-1.892 11.202 0 3.614.512 6.99 1.535 10.128s2.507 5.866 4.45 8.184c1.945 2.32 4.349 4.145 7.213 5.474 2.864 1.329 6.102 1.995 9.719 1.995 2.864 0 5.487-.53 7.878-1.587a22.297 22.297 0 0 0 6.343-4.193c1.84-1.738 3.427-3.785 4.756-6.137 1.33-2.353 1.887-3.303 2.707-5.826l-2.867-1.23c-1.234 2.89-3.175 5.364-5.823 7.416l-.008-.011ZM67.36 30.609c2.182-2.967 5.114-4.45 8.799-4.45 3.34 0 5.796 1.466 7.363 4.398 1.568 2.932 2.388 6.481 2.456 10.64H63.167c.614-4.09 2.011-7.621 4.193-10.588ZM172.99 71.883h6.129v3.276h-16.57V20.903c0-6.278 1.859-11.735 5.579-15.25C171.848 2.14 176.472.28 182 .075v11.874h-14.741v1.229c0 2.732.769 5.715 2.304 7.762 1.535 2.046 3.804 3.07 6.806 3.07h5.617v4.737h-8.993V71.88l-.003.003Z'

LOGO = (
    '<svg class="logo" fill="currentColor" xmlns="http://www.w3.org/2000/svg" '
    'viewBox="0 0 182 77" role="img" aria-label="Serif Biomedicines">'
    '<path d="' + LOGO_PATH + '"/></svg>'
)

# Focus mode is an action, not a filter. The icon reinforces the separation.
EYE_ICON = (
    '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true" focusable="false">'
    '<path d="M1.8 12S5.8 5.2 12 5.2 22.2 12 22.2 12S18.2 18.8 12 18.8 1.8 12 1.8 12Z"/>'
    '<circle cx="12" cy="12" r="3.1"/></svg>'
)

# Page decoration, drawn from two motifs on serifbiomedicines.com: the crossing
# loops of their "modification cycle" diagram, and the hairline curve fields that
# sweep across their Warm Gray and Dark Gray cards. Strokes only -- the vivid accent
# is reserved for live state.
#
# Two separate fields rather than one shared artwork, so the rail and the content
# column read as different surfaces instead of one continuous drawing split by a
# boundary. Each is a crop of its own composition.
#
# Every stroke starts and ends outside its own viewBox. Combined with
# preserveAspectRatio slice, which scales the art to cover its box, that means a
# stroke always leaves through an edge and never terminates in open space. Apparent
# scale is set by how much the composition holds: the wide field below carries more
# and larger sweeps, so cover-scaling renders it calmly.
#
# non-scaling-stroke keeps hairlines at 1px however far the art is scaled.
_STROKE = ('<g fill="none" stroke="currentColor" stroke-width="1" '
           'vector-effect="non-scaling-stroke">')

# The content column: long sweeps with a single loop cropped into the far corner.
CURVE_FIELD = (
    '<svg class="motif" viewBox="0 0 1800 1000" preserveAspectRatio="xMaxYMax slice" '
    'aria-hidden="true" focusable="false">' + _STROKE +
    '<circle cx="1510" cy="830" r="330"/>'
    '<path d="M-40 300 C 300 140, 620 520, 940 460 S 1500 260, 1840 380"/>'
    '<path d="M-40 720 C 340 800, 480 400, 880 320 S 1420 180, 1840 120"/>'
    '<path d="M120 1040 C 320 700, 760 880, 1060 600 S 1480 300, 1840 430"/>'
    '<path d="M-40 940 C 420 990, 700 680, 1840 800"/>'
    '<path d="M560 -40 C 660 270, 1170 390, 1300 1040"/>'
    "</g></svg>"
)


# Open-licensed substitute webfonts, inlined when the module is present.
try:
    from serif_fonts import FONT_CSS
except ImportError:  # console still renders on the system stack
    FONT_CSS = ""

CSS = r"""
/* Serif Biomedicines design system, tokens from serif-design-system/tokens.css,
   which follows the Serif Brand Guide (brandpad.io/serif): Dark Gray, Mid Gray,
   Warm Gray, Light Gray, Red. */
:root{
  --color-white:#fff; --color-light-gray:#e5e5e5; --color-warm-gray:#ada990;
  --color-mid-gray:#525046; --color-dark-gray:#2e2d29; --color-red:#ff3d00;
  /* Two working tints the palette does not name. hairline is Light Gray taken
     one step toward Warm Gray, for rules and hover fills on a white card, where
     Light Gray itself (1.26:1) disappears. red-text is Red darkened for text:
     #ff3d00 is mid-luminance, so light text on it reaches only 2.82:1 and dark
     text 3.86:1, and Red itself never carries or backs text. red-text on white
     is 5.50:1 and white on it 5.50:1. Red stays for small marks on a light
     ground and on the dark rail, which clear the 3:1 non-text threshold. */
  --color-hairline:#d6d6d4; --color-red-text:#c72e00;
  --color-accent-text:var(--color-red-text);
  --color-vivid:var(--color-red); --color-stark:var(--color-white);
  --color-ghost:var(--color-warm-gray); --color-neutral:var(--color-light-gray);
  --color-bg-primary:var(--color-light-gray); --color-bg-secondary:var(--color-warm-gray);
  --color-bg-inverse:var(--color-dark-gray);
  --color-fg-primary:var(--color-dark-gray); --color-fg-secondary:var(--color-mid-gray);
  --color-fg-inactive:var(--color-warm-gray); --color-fg-inverse:var(--color-light-gray);

  --font-sans:"Denim","Figtree","Helvetica Neue",Helvetica,Arial,sans-serif;
  --font-serif:"Eliza","PT Serif",Georgia,"Times New Roman",serif;
  --font-mono:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;

  --text--2:12.5px;
  --text--1:clamp(0.8889rem,0.8867rem + 0.0111vw,0.9rem);
  --text-0:clamp(1rem,0.975rem + 0.125vw,1.125rem);
  --text-1:clamp(1.125rem,1.0688rem + 0.2813vw,1.4063rem);
  --text-2:clamp(1.2656rem,1.1672rem + 0.4922vw,1.7578rem);
  --text-3:clamp(1.4238rem,1.2691rem + 0.7734vw,2.1973rem);
  --text-4:clamp(1.6018rem,1.3729rem + 1.1448vw,2.7466rem);

  --spacing-3xs:clamp(0.25rem,0.2375rem + 0.0625vw,0.3125rem);
  --spacing-2xs:clamp(0.5rem,0.4875rem + 0.0625vw,0.5625rem);
  --spacing-xs:clamp(0.75rem,0.725rem + 0.125vw,0.875rem);
  --spacing-sm:clamp(1rem,0.975rem + 0.125vw,1.125rem);
  --spacing-md:clamp(1.5rem,1.4625rem + 0.1875vw,1.6875rem);
  --spacing-lg:clamp(2rem,1.95rem + 0.25vw,2.25rem);
  --spacing-xl:clamp(3rem,2.925rem + 0.375vw,3.375rem);
  --spacing-sm-md:clamp(1rem,0.8625rem + 0.6875vw,1.6875rem);
  --spacing-sm-lg:clamp(1rem,0.75rem + 1.25vw,2.25rem);
  --spacing-md-lg:clamp(1.5rem,1.35rem + 0.75vw,2.25rem);
  --spacing-lg-xl:clamp(2rem,1.725rem + 1.375vw,3.375rem);

  --radius-xs:var(--spacing-3xs); --radius-sm:var(--spacing-sm);
  --radius-md:var(--spacing-sm-md); --radius-lg:var(--spacing-lg-xl); --radius-pill:999px;

  --ease-out:cubic-bezier(0,0,0.2,1); --ease-out-quartic:cubic-bezier(0.165,0.84,0.44,1);
  --duration-press:0.15s; --duration-hover:0.2s; --duration-control:0.25s; --duration-card:0.3s;

  --state-over:var(--color-accent-text); --state-under:var(--color-fg-secondary);
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;font-family:var(--font-sans);font-size:var(--text-0);line-height:1.15;
  color:var(--color-fg-primary);background-color:var(--color-bg-primary);
  font-feature-settings:"dlig" on;-webkit-font-smoothing:antialiased;
  hanging-punctuation:first allow-end;overflow:hidden;text-wrap:pretty}
button,textarea,input{font:inherit;color:inherit}
/* [hidden] is an attribute selector, so any id-level rule that sets `display`
   outranks it and the element stays on screen. Hidden must win outright. */
[hidden]{display:none!important}
::selection{background-color:var(--color-accent-text);color:#fff}
:focus-visible{outline:2px solid var(--color-vivid);outline-offset:0.35rem}
/* A 0.35rem ring reads well around a pill, which has air on every side, but a
   full-width field sits tight against the chip row above and the count below,
   so the ring collides. Fields get the ring on their own edge instead. */
input:focus-visible,textarea:focus-visible{outline-offset:2px}
.mono{font-family:var(--font-mono)}
.secondary{color:var(--color-fg-secondary)}

/* headline: sans with one serif swap, regular weight, full stop */
h2{font-family:var(--font-sans);font-size:var(--text-3);font-weight:400;line-height:1.04;
  letter-spacing:-0.01em;margin:0 0 var(--spacing-md);text-wrap:balance}
h2 .font-serif{font-family:var(--font-serif);font-size:var(--text-3);letter-spacing:-0.02em}
h3{font-family:var(--font-sans);font-size:var(--text-0);font-weight:600;line-height:1.1;
  margin:0 0 var(--spacing-sm)}

.app{display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:auto minmax(0,1fr);height:100vh}

/* The top bar. One text size across it; the wordmark is the only thing sized
   apart. Every item is centered on one line, and every pill has one height in
   every state, so a count or a hover never changes its size. */
.tnav{--tn-h:2.4em;display:flex;align-items:center;flex-wrap:wrap;
  gap:var(--spacing-2xs) var(--spacing-sm);padding-block:var(--spacing-2xs);
  padding-inline:var(--spacing-md-lg);background-color:var(--color-bg-inverse);
  color:var(--color-fg-inverse);font-size:var(--text--1);line-height:1.2;position:relative;z-index:5}
.tnav .tb{display:flex;align-items:center;gap:var(--spacing-xs);padding-right:var(--spacing-sm);
  border-right:1px solid rgba(255,255,255,.14)}
.tnav .tb .logo{width:52px;height:auto;color:var(--color-white);display:block}
.tnav .tb b{font-weight:500;color:var(--color-white);white-space:nowrap}
.tnav .tb span{color:var(--color-warm-gray);white-space:nowrap}
.tnav .nav{display:flex;align-items:center;gap:var(--spacing-3xs);flex-wrap:wrap}
.tnav .tg{position:relative;display:flex;align-items:center}
.tnav .tbtn{display:inline-flex;align-items:center;gap:var(--spacing-2xs);height:var(--tn-h);
  box-sizing:border-box;padding:0 var(--spacing-xs);border-radius:var(--radius-pill);
  background:none;border:0;cursor:pointer;font:inherit;color:var(--color-warm-gray);white-space:nowrap;
  transition:color var(--duration-hover) var(--ease-out),background-color var(--duration-hover) var(--ease-out)}
.tnav .tbtn:hover{color:var(--color-white);background-color:rgba(255,255,255,.06)}
.tnav .tbtn.cur,.tnav .tbtn[aria-current="true"]{color:var(--color-white);background-color:rgba(255,255,255,.1)}
/* An open count is a bubble, not loose text. */
.navct{display:inline-flex;align-items:center;justify-content:center;min-width:1.6em;height:1.6em;
  padding:0 0.45em;box-sizing:border-box;border-radius:var(--radius-pill);font-size:var(--text--2);
  font-weight:600;line-height:1;font-variant-numeric:tabular-nums;
  background-color:var(--color-vivid);color:var(--color-white)}
.navct:empty{display:none}
/* A group's pages are tabs under the page title. The strip's rule is drawn behind
   the tabs, so the current tab covers it and opens into the page like a folder. */
.topbar{flex-direction:column;align-items:stretch;gap:var(--spacing-xs);position:relative;z-index:1}
.stabs{display:flex;align-items:flex-end;gap:var(--spacing-3xs);flex-wrap:nowrap;overflow-x:auto;
  scrollbar-width:none;margin:0 calc(-1 * var(--spacing-3xs));
  background:linear-gradient(to top,var(--color-warm-gray) 1px,transparent 1px)}
.topbar .stabs{align-self:stretch}
/* Scrolled content fades out under the page title rather than being cut off. */
.view.scrolled{-webkit-mask-image:linear-gradient(to bottom,transparent 0,#000 var(--spacing-sm));
  mask-image:linear-gradient(to bottom,transparent 0,#000 var(--spacing-sm))}
.stabs[hidden]{display:none}
/* --layout ui-update: a section's pages slide in beside its title. */
.tnav .tsub{display:inline-flex;align-items:center;gap:var(--spacing-3xs);overflow:hidden;white-space:nowrap;
  max-width:60rem;opacity:1;margin-left:var(--spacing-3xs);padding-left:var(--spacing-2xs);
  border-left:1px solid rgba(255,255,255,.14);
  transition:max-width var(--duration-card) var(--ease-out-quartic),opacity var(--duration-card) var(--ease-out)}
.tnav .tsub[hidden]{display:inline-flex!important;max-width:0;opacity:0;margin-left:0;padding-left:0;border-left:0;pointer-events:none}
.tnav .tsub{background:none;margin-top:0;margin-bottom:0;margin-right:0;flex-wrap:nowrap;border-left:0}
/* The open section sits in one lighter pill, its title and its pages together. */
.tnav .tg{transition:background-color var(--duration-card) var(--ease-out)}
.tnav .tg.open{background-color:rgba(255,255,255,.08);border-radius:var(--radius-pill)}
.tnav .tg.open > .tgt{background:none;color:var(--color-white);font-weight:600}
.tnav .tg.open .tsub .tbtn:not([aria-current="true"]):hover{background-color:rgba(255,255,255,.08)}
body.uiupd .tnav .tbtn[aria-current="true"]:hover{background-color:var(--color-white);color:var(--color-dark-gray)}
/* The page on screen is the one light chip in the bar. */
body.uiupd .tnav .tbtn[aria-current="true"]{background-color:var(--color-light-gray);color:var(--color-dark-gray)}
/* The import and audit trail are offered on Export, once. */
body.uiupd #v-entries .vtbar > .inl{display:none}
/* One row that keeps its height: the pages scroll inside the bar before anything wraps. */
body.uiupd .tnav{flex-wrap:nowrap}
body.uiupd .tnav .tb{flex:none}
body.uiupd .tnav > nav.nav{flex:1 1 auto;min-width:0;flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none}
body.uiupd .tnav > nav.nav::-webkit-scrollbar{display:none}
body.uiupd .tnav .tg{flex:none}
body.uiupd .tnav .tthr,body.uiupd .tnav .trun{flex:none}
body.uiupd .tnav .tset{margin-left:auto}
/* Tighter in the updated UI, so every section title fits beside an open section. */
body.uiupd .tnav{column-gap:var(--spacing-2xs)}
body.uiupd .tnav .tbtn{padding:0 .6em}
body.uiupd .tnav .tb{padding-right:var(--spacing-2xs)}
body.uiupd .tnav .trun .tbtn span{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
@media (max-width:1380px){body.uiupd .tnav .tb span{display:none}}
.setfix{display:inline-flex;align-items:center;gap:var(--spacing-xs);font-size:var(--text-0)}
.setfix .fx{display:inline-flex;align-items:center;border:1px solid var(--color-hairline);border-radius:var(--radius-pill);
  padding:.35em .9em;font-variant-numeric:tabular-nums}
.setfix .fx:focus-within{box-shadow:0 0 0 2px var(--color-vivid)}
.setfix input{font:inherit;border:0;outline:0;background:none;width:8ch}
.tnav .tsub .tbtn{font-size:inherit;white-space:nowrap;flex:none}
/* The page list is also a .nav, whose wrapping rule would otherwise win. */
.tnav div.tsub,.tnav div.tsub[hidden]{display:inline-flex!important;flex-wrap:nowrap;height:2.4em;align-self:center}
.tnav .tg.open > .tgt{color:var(--color-white)}
.tnav .tg.open > .tgt .navct{display:none}
@media (prefers-reduced-motion:reduce){.tnav .tsub{transition:none}}
.stabs::-webkit-scrollbar{display:none}
.stabs button{flex:none;display:inline-flex;align-items:center;gap:var(--spacing-2xs);
  height:2.6em;box-sizing:border-box;padding:0 var(--spacing-sm);
  font:inherit;font-size:var(--text--1);color:var(--color-fg-secondary);cursor:pointer;
  background:none;border:1px solid transparent;border-bottom:0;
  border-radius:var(--radius-sm) var(--radius-sm) 0 0;white-space:nowrap;
  transition:color var(--duration-hover) var(--ease-out),background-color var(--duration-hover) var(--ease-out)}
.stabs button:hover{color:var(--color-fg-primary);background-color:rgba(0,0,0,.035)}
.stabs button[aria-current="true"]{color:var(--color-fg-primary);font-weight:600;
  background-color:var(--color-bg-primary);border-color:var(--color-warm-gray)}
/* The review threshold: a compact field, the bar's text size and pill height. */
.tnav .tthr{margin-left:auto;display:inline-flex;align-items:center;gap:var(--spacing-2xs);
  height:var(--tn-h);box-sizing:border-box;padding:0 var(--spacing-3xs) 0 var(--spacing-xs);
  border-radius:var(--radius-pill);background-color:rgba(255,255,255,.06);color:var(--color-warm-gray)}
.tnav .tthr label{white-space:nowrap;cursor:text}
.tnav .tthr .fx{display:inline-flex;align-items:center;height:calc(var(--tn-h) - 8px);
  padding:0 var(--spacing-2xs);border-radius:var(--radius-pill);background-color:rgba(255,255,255,.1);
  color:var(--color-white)}
.tnav .tthr input{font:inherit;color:inherit;background:none;border:0;outline:0;width:6ch;
  padding:0 0 0 0.1em;font-variant-numeric:tabular-nums}
.tnav .tthr .fx:focus-within{box-shadow:0 0 0 2px var(--color-vivid)}
.tnav .tthr + .trun{margin-left:var(--spacing-xs)}
.tnav .nav + .trun{margin-left:auto}
.tnav .trun .ico{width:1.05em;height:1.05em;display:block;flex:none}
#v-runlog .costgrid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--spacing-md-lg);align-items:start}
@media (max-width:900px){#v-runlog .costgrid{grid-template-columns:1fr}}
.expmiss{color:var(--color-vivid);font-weight:600}
dialog.ask .asktype{display:flex;flex-direction:column;gap:var(--spacing-3xs);margin-top:var(--spacing-sm);font-size:var(--text--1);color:var(--color-fg-secondary)}
dialog.ask .asktype code{font-family:var(--font-mono);color:var(--color-fg-primary);background-color:var(--color-stark);
  padding:0.05em 0.35em;border-radius:var(--radius-xs)}
dialog.ask .asktype input{font:inherit;font-family:var(--font-mono);color:var(--color-fg-primary);height:var(--ctl-h);padding:0 var(--spacing-xs);
  border:1px solid var(--color-warm-gray);border-radius:var(--radius-xs);background:var(--color-white)}
dialog.ask .asktype input:focus{outline:0;box-shadow:0 0 0 2px var(--color-vivid)}
dialog.ask .pill:disabled{opacity:.4;cursor:not-allowed}
td .rid{font-size:var(--text--2);color:var(--color-fg-secondary);margin-left:0.4em;white-space:nowrap}
.costtbl tr.tot td{font-weight:600;border-top:1px solid var(--color-warm-gray)}
.costbasis{margin:0;padding-left:1.1em;display:grid;gap:var(--spacing-3xs)}
@media (max-width:700px){.tnav .tb{border-right:0;padding-right:0}}

/* Schedules. Every table a controller reads line by line, the flux pack
   included, shares this one style, so a band, a flag and a subtotal mean the
   same thing on every page.
   The column widths are starting points: a column grows to fit what it holds, so
   no figure, status or button runs into its neighbour. A table wider than its
   card scrolls sideways inside the card. */
.schedwrap{overflow-x:auto;padding:0;border-radius:var(--radius-sm)}
.tblwrap{overflow-x:auto}
.tblwrap .mono{font-size:var(--text--1)}
.sched{min-width:48rem;table-layout:auto;width:100%}
.sched.fluxtbl{min-width:56rem}
.sched th,.sched td{padding:var(--spacing-2xs) var(--spacing-sm);vertical-align:top}
.sched thead th{position:sticky;top:0;background-color:var(--color-stark);z-index:2;
  border-bottom:1px solid var(--color-warm-gray);vertical-align:bottom;line-height:1.25}
.sched .num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.sched td b{font-weight:600;overflow-wrap:anywhere}
.sched .sub2{display:block;font-size:var(--text--2);color:var(--color-fg-secondary);
  margin-top:2px;line-height:1.35;overflow-wrap:anywhere}
.sched td.ltext{overflow-wrap:anywhere}
/* No banding on a schedule. Its rows are ruled, sectioned and carry their own
   figures close together, so a band adds noise rather than guidance. Banding is
   kept for the plain tables further down, where a label sits far from its
   figures and the eye needs help across the gap. The generic zebra counts
   children, so it is outranked here rather than removed. */
table.sched tbody tr:nth-child(n) > td{background-color:transparent;
  border-bottom:1px solid var(--color-hairline)}
table.sched tbody tr.evrow:nth-child(n) > td{background-color:var(--color-bg-primary)}
/* A row that opens is a row you can click. */
.sched tbody tr.xp{cursor:pointer}
.sched tbody tr.xp:hover > td{background-color:rgba(173,169,144,0.10)}
.sched tbody tr.xp.open > td{background-color:rgba(173,169,144,0.16)}
/* Needs action: an accent rule on the row's leading edge and an accent status
   word. It never tints the row, so it cannot be confused with the band. */
.sched tr.needs > td:first-child{box-shadow:inset 3px 0 0 var(--color-vivid)}
/* A section is structure, not data: a heading with its count and subtotals.
   Sentence case, like everything else in the system. */
.sched tr.sec > th{background-color:var(--color-bg-primary);color:var(--color-fg-primary);
  font-weight:600;position:static;border-bottom:0;
  padding-top:var(--spacing-xs);padding-bottom:var(--spacing-xs)}
.sched tr.sec > th .n{font-weight:400;color:var(--color-fg-secondary);margin-left:var(--spacing-2xs)}
.sched tr.sec button.secbtn{font:inherit;font-weight:600;background:none;border:0;padding:0;
  cursor:pointer;color:inherit;display:inline-flex;align-items:baseline;gap:var(--spacing-3xs);
  text-align:left}
.sched tr.sec .caret{display:inline-block;color:var(--color-fg-secondary);
  transition:transform 200ms var(--ease-out)}
.sched tr.sec button[aria-expanded="true"] .caret{transform:rotate(90deg)}
.sched tr.subnote > td{font-size:var(--text--2);color:var(--color-fg-secondary);
  background-color:transparent;padding-block:var(--spacing-xs)}
/* An account is always its code and its name; a code alone means nothing to
   anyone who has not memorized the chart. */
.ac{display:block;overflow-wrap:break-word;line-height:1.3}
.ac .mono{font-size:var(--text--1);color:var(--color-fg-secondary)}
.cd{margin-bottom:var(--spacing-2xs)}
.cd:last-child{margin-bottom:0}
.more > summary{cursor:pointer;list-style:none;font-size:var(--text--2);
  color:var(--color-fg-secondary);margin-top:var(--spacing-3xs)}
.more > summary::-webkit-details-marker{display:none}
.more > summary:hover{color:var(--color-fg-primary)}
.more[open] > summary{margin-bottom:var(--spacing-2xs)}
.olay{display:inline-block;font-size:var(--text--2);color:var(--color-accent-text);
  margin-top:2px}

/* Status and the row's actions sit on one line. The status word and every
   button share one height and one type size, so nothing sits higher than its
   neighbour, and the gap between them is the only spacing. */
.stc{display:flex;flex-wrap:wrap;align-items:center;gap:var(--spacing-3xs) var(--spacing-2xs)}
.st{display:inline-flex;align-items:center;gap:0.45em;min-height:1.9em;
  font-size:var(--text--2);line-height:1.2;color:var(--color-fg-secondary)}
.st.needs{color:var(--color-accent-text)}
.st.needs::before{content:"";width:7px;height:7px;border-radius:999px;flex:none;
  background-color:var(--color-vivid)}
.st.done{color:var(--color-fg-primary)}
/* A row with several open flags lists each one, stacked. */
.ststack{display:flex;flex-direction:column;align-items:flex-start;gap:2px}
/* A status slot of fixed width, rendered empty where there is no status, so the
   buttons after it line up down the column instead of jumping left. */
.stc .st.slot{min-width:9.6em}
.stc .brk{flex-basis:100%;height:0}
.sched .nowrap{white-space:nowrap}
/* Controls. A compact control sits in a table row or a panel heading: a button
   (.fxact), a choice or a text field (.fld), all at the row's text size and one
   height. A pill (.pill) is a page-level action only. Controls that sit together,
   or beside text, go in one flex row (.inl) spaced by one gap, never by typed
   spaces or one-off margins. */
:root{--ctl-h:2em;--ctl-gap:var(--spacing-2xs)}
.inl{display:flex;flex-wrap:wrap;align-items:center;gap:var(--ctl-gap)}
/* A link out: the text it labels, with a small arrow that says it leaves the
   console. Underlined only on hover, so a column of them stays quiet. */
a.xl{color:inherit;text-decoration:none;white-space:nowrap}
a.xl:hover,a.xl:focus-visible{text-decoration:underline;text-underline-offset:0.2em}
a.xl .xa{display:inline-block;width:0.7em;height:0.7em;margin-left:0.15em;vertical-align:0.05em;
  color:var(--color-fg-secondary)}
/* The Coupa invoice and PO beside a document number: compact chips on one line. */
.xls{display:inline-flex;flex-wrap:nowrap;align-items:center;gap:var(--ctl-gap)}
.xdocs{display:flex;flex-direction:column;align-items:flex-start;gap:var(--spacing-3xs);
  margin-top:var(--spacing-3xs);font-size:var(--text--1);color:var(--color-fg-secondary)}
a.xl.xc{font-family:var(--font-sans);font-size:var(--text--2);line-height:1.2;
  padding:0.15em var(--spacing-2xs);border:1px solid var(--color-warm-gray);
  border-radius:var(--radius-pill);color:var(--color-fg-secondary)}
a.xl.xc:hover,a.xl.xc:focus-visible{text-decoration:none;border-color:var(--color-fg-primary);
  color:var(--color-fg-primary)}
.fld{font:inherit;font-size:var(--text--2);line-height:1.2;color:var(--color-fg-primary);
  min-height:var(--ctl-h);padding:0 var(--spacing-2xs);border:1px solid var(--color-warm-gray);
  border-radius:var(--radius-xs);background-color:var(--color-stark);box-sizing:border-box}
.fld:focus-visible{outline:2px solid var(--color-vivid);outline-offset:1px}
.fchip,.fxact{display:inline-flex;align-items:center;gap:var(--spacing-3xs);min-height:var(--ctl-h);
  font:inherit;font-size:var(--text--2);line-height:1.2;white-space:nowrap;box-sizing:border-box;
  padding:0 var(--spacing-xs);border-radius:var(--radius-pill);border:1px solid transparent}
.fchip{background-color:var(--color-bg-primary);color:var(--color-fg-primary)}
/* Every action in a row is the same kind of thing, so they look alike: a small
   knockout pill, matching the decision buttons elsewhere. */
.fxact{background:transparent;border-color:var(--color-warm-gray);
  color:var(--color-fg-primary);cursor:pointer;text-decoration:none;
  transition:border-color var(--duration-hover) var(--ease-out),
             background-color var(--duration-hover) var(--ease-out)}
.fxact:hover,.fxact:focus-visible{border-color:var(--color-fg-primary);
  background-color:var(--color-stark)}
.fxact:active{transform:scale(0.97)}
.fxact.on,.fxact.primary{background-color:var(--color-bg-inverse);border-color:var(--color-bg-inverse);
  color:var(--color-fg-inverse)}
.fxact.primary:hover,.fxact.primary:focus-visible{background-color:var(--color-fg-secondary);
  border-color:var(--color-fg-secondary)}
/* The caret turns as the panel opens, the same gesture the collapsible cards
   on Overview already use. */
.fxact .caret{transition:transform 200ms var(--ease-out);display:inline-block}
.fxact[aria-expanded="true"] .caret{transform:rotate(90deg)}

/* The flux pack's own columns. */
.sched.fluxtbl{table-layout:fixed}
.fluxtbl col.c-acct{width:17%}
.fluxtbl col.c-num{width:9%}
.fluxtbl col.c-pct{width:6%}
.fluxtbl col.c-act{width:12%}
.fluxtbl col.c-btn{width:10%}
.fluxtbl col.c-cmt{width:28%}
.fluxtbl.trend col.c-acct{width:14%}
.fluxtbl.trend col.c-num{width:7.5%}
.fluxtbl.trend col.c-pct{width:5%}
.fluxtbl.trend col.c-yoy{width:9%}
.fluxtbl.trend col.c-act{width:10%}
.fluxtbl.trend col.c-btn{width:8%}
.fluxtbl.trend col.c-cmt{width:24%}
.fluxtbl td{overflow-wrap:anywhere}
.fluxtbl .cmt{display:block;max-width:100%;box-sizing:border-box;white-space:pre-wrap;overflow-wrap:anywhere}

/* The evidence panel sits under its row and inside the table, so the row keeps
   its place and its neighbours stay visible above and below. */
.sched tr.evrow > td{padding:0;background-color:var(--color-bg-primary)}
.evbox{padding:var(--spacing-md) var(--spacing-md-lg)}
/* In a schedule an opened row's evidence sits on its own white card, inset in the
   row's band, so it reads as one piece belonging to the row above. */
.sched tr.evrow > td{padding:var(--spacing-2xs) var(--spacing-sm) var(--spacing-sm)}
.sched tr.evrow .evbox{background-color:var(--color-stark);border-radius:var(--radius-sm)}
.evbox h4{margin:0 0 var(--spacing-2xs);font-family:var(--font-sans);
  font-size:var(--text-1);font-weight:400;line-height:1.1}
.evbox .kv{margin-top:var(--spacing-sm)}
.evbox .fix{background-color:var(--color-stark)}
.evtxn{margin-top:var(--spacing-sm);width:100%;min-width:0}
.evtxn td{padding:var(--spacing-3xs) var(--spacing-xs);
  border-bottom:0;font-size:var(--text--2);color:var(--color-fg-secondary);
  background-color:transparent !important}
.evtxn td.mono,.evtxn td.num{white-space:nowrap}
.evbox .acts{margin-top:var(--spacing-md);align-items:center}
.evbox .cmt{margin-top:var(--spacing-sm)}
.evstate{font-size:var(--text--2);color:var(--color-fg-secondary)}

/* Journal Entries. An entry is one record, so its heading and its lines share
   one band, and the heading carries the entry's totals in the money columns. */
.sched tr.jeh > td{border-top:1px solid var(--color-warm-gray);padding-top:var(--spacing-xs)}
.sched tr.jeh b{font-weight:600}
.sched tr.jel > td{padding-top:var(--spacing-3xs);padding-bottom:var(--spacing-3xs)}
table.sched tbody tr.jel:nth-child(n) > td{border-bottom:0}
.sched tr.jel > td:first-child{padding-left:var(--spacing-md)}
.sched tr.jewarn > td{font-size:var(--text--2);color:var(--color-accent-text);border-bottom:0}

/* A caveat that changes how a schedule is read sits above it as one line, not
   under it as a footnote nobody reaches. */
.vtalert{display:flex;gap:var(--spacing-2xs);align-items:baseline;
  background-color:var(--color-stark);border-radius:var(--radius-sm);
  padding:var(--spacing-xs) var(--spacing-md);margin-bottom:var(--spacing-xs);
  font-size:var(--text--1);max-width:none}
.vtalert::before{content:"";flex:none;width:7px;height:7px;border-radius:999px;
  background-color:var(--color-vivid);transform:translateY(-0.1em)}
.vtalert details{display:inline}
.vtalert summary{display:inline;cursor:pointer;color:var(--color-fg-secondary);
  margin-left:var(--spacing-2xs);list-style:none}
.vtalert summary::-webkit-details-marker{display:none}
.vtalert .refs{display:block;margin-top:var(--spacing-3xs);font-family:var(--font-mono);
  font-size:var(--text--2);color:var(--color-fg-secondary)}
/* The vendor panel: why each flag was raised, the three months by account and
   by department, the lines with what each says was bought, and the outcome. */
.vflags{display:flex;flex-direction:column;gap:var(--spacing-xs)}
/* A flag is marked by the status dot, not a rule: the row's own edge is the one
   vertical line. */
.vflag{padding:0}
.vflag .vfh b{display:inline-flex;align-items:center;gap:0.45em}
.vflag.needs .vfh b::before{content:"";width:7px;height:7px;border-radius:999px;flex:none;
  background-color:var(--color-vivid)}
.vflag .vfh{display:flex;flex-wrap:wrap;align-items:baseline;gap:var(--spacing-2xs) var(--spacing-sm)}
.vflag .vfh b{font-weight:600}
.vflag .vfh .num{font-variant-numeric:tabular-nums}
.vflag p{margin:var(--spacing-3xs) 0 0;font-size:var(--text--1);line-height:1.4}
.vgrids{display:grid;grid-template-columns:repeat(auto-fit,minmax(20rem,1fr));
  gap:var(--spacing-sm) var(--spacing-lg);margin-top:var(--spacing-md)}
/* A table inside a panel is a figure, not a schedule: no sticky white header. */
.sched .evtxn th,.evtxn th{font-size:var(--text--2);font-weight:600;color:var(--color-fg-secondary);
  padding:0 var(--spacing-xs) var(--spacing-3xs);border-bottom:1px solid var(--color-warm-gray);
  background:transparent;position:static;vertical-align:bottom}
table.sched .evtxn tbody tr:nth-child(n) > td{border-bottom:1px solid var(--color-hairline);
  padding:var(--spacing-3xs) var(--spacing-xs);vertical-align:baseline}
.evtxn th.num{text-align:right}
.evtxn td.over{color:var(--color-accent-text)}
.evbox h5{margin:var(--spacing-md) 0 var(--spacing-2xs);font-size:var(--text--1);font-weight:600}
.evtxn td.ltext{color:var(--color-fg-primary);white-space:normal;min-width:16rem}
.evtxn .blank{color:var(--color-accent-text)}
/* A reclassed line: the posted coding struck through, the new coding under it. */
.evtxn tr.lrc td{background-color:rgba(173,169,144,0.16) !important}
.evtxn td.lacts .inl{flex-wrap:nowrap}
.fxact.ico{width:var(--ctl-h);padding:0;justify-content:center}
/* A narrowing filter on a row's lines: what it is, how many lines, and a clear. */
.evtxn .lflag{display:block;margin-top:2px;font-size:var(--text--2);color:var(--color-accent-text)}
.lfilt{display:inline-flex;align-items:center;gap:var(--spacing-3xs);min-height:var(--ctl-h);
  box-sizing:border-box;padding:0 var(--spacing-3xs) 0 var(--spacing-xs);border-radius:var(--radius-pill);
  background-color:var(--color-bg-primary);font-size:var(--text--2);font-weight:400}
.lfx{display:inline-flex;align-items:center;justify-content:center;width:1.6em;height:1.6em;
  border:0;border-radius:var(--radius-pill);background:none;cursor:pointer;font:inherit;
  font-size:1.1em;line-height:1;color:var(--color-fg-secondary)}
.lfx:hover,.lfx:focus-visible{background-color:var(--color-stark);color:var(--color-fg-primary)}
.evtxn .rcto{display:block;color:var(--color-fg-primary)}
/* A cell being reclassed keeps its shape: the text as it reads, a caret, and a
   native choice laid over the whole cell. */
:is(.evtxn,#jetbl) td.rcpick{position:relative;cursor:pointer}
:is(.evtxn,#jetbl) td.rcpick .rcshow{color:var(--color-fg-primary);border-bottom:1px dotted var(--color-fg-secondary)}
:is(.evtxn,#jetbl) td.rcpick .caret{margin-left:var(--spacing-3xs);color:var(--color-fg-secondary)}
:is(.evtxn,#jetbl) td.rcpick select{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer;
  font:inherit;font-size:var(--text--2)}
/* The value being picked is one rounded block, so its hover and focus ring wrap
   the whole value however many lines it takes. */
:is(.evtxn,#jetbl) td.rcpick .rcval{display:inline-block;padding:2px var(--spacing-3xs);margin:-2px calc(-1 * var(--spacing-3xs));
  border-radius:var(--radius-xs);transition:background-color var(--duration-hover) var(--ease-out)}
:is(.evtxn,#jetbl) td.rcpick:hover .rcval{background-color:var(--color-bg-primary)}
:is(.evtxn,#jetbl) td.rcpick:has(select:focus-visible) .rcval{box-shadow:0 0 0 2px var(--color-vivid)}
:is(.evtxn,#jetbl) tr.rcon > td,:is(.evtxn,#jetbl) tr.rcedit > td{background-color:var(--color-stark) !important}
table.sched .evtxn tbody tr.rcon > td{border-bottom:0}
table.sched .evtxn tbody tr.rcedit > td{padding-top:var(--spacing-xs);padding-bottom:var(--spacing-sm)}

.rcform{display:flex;flex-wrap:wrap;align-items:flex-end;gap:var(--ctl-gap) var(--spacing-sm)}
.rcform label{display:flex;flex-direction:column;gap:var(--spacing-2xs);font-size:var(--text--2);
  font-weight:600;color:var(--color-fg-secondary)}
.rcform .rcwhy{flex:1 1 18rem}
.rcform .rcwhy .fld{width:100%;font-weight:400}
.sched .jeamt{width:9em;text-align:right;font-variant-numeric:tabular-nums}
.jetot{font-size:var(--text--2);color:var(--color-fg-secondary);white-space:nowrap}
.jetot.reqd{color:var(--color-accent-text)}
.sched .jeed{color:var(--color-fg-primary)}
.fxact:disabled{opacity:.45;cursor:not-allowed}
.rcsum{font-size:var(--text--1)}
.rcsum .mono{font-size:0.9em}
.rcsum ul{margin:var(--spacing-2xs) 0 0;padding-left:var(--spacing-md)}
.rcsum li{margin-bottom:var(--spacing-3xs)}
.rcsum .note{margin-top:var(--spacing-2xs);font-size:var(--text--2)}
/* Claude's drafts: set apart, labeled, and one click from being used. */
.dblock{background-color:var(--color-stark);border-radius:var(--radius-sm);
  padding:var(--spacing-sm) var(--spacing-md);margin-top:var(--spacing-md)}
.dblock .dh{display:flex;flex-wrap:wrap;align-items:baseline;gap:var(--spacing-2xs) var(--spacing-sm);
  font-size:var(--text--1)}
.dblock .dh b{font-weight:600}
.dblock p{margin:var(--spacing-2xs) 0 0;font-size:var(--text--1);line-height:1.45}
.drafted{display:flex;align-items:center;gap:var(--spacing-2xs);margin-top:var(--spacing-3xs);
  font-size:var(--text--2);color:var(--color-fg-secondary)}
.stc .sub2{flex-basis:100%;margin-top:0}
.summary p{margin:var(--spacing-2xs) 0 0;font-size:var(--text-0);line-height:1.5}
.summary ul{margin:var(--spacing-2xs) 0 0;padding-left:1.2em}
.summary li{margin-bottom:var(--spacing-3xs);line-height:1.45}

/* Rows in a panel that narrow or open what is below them. */
.evtxn tr.pick{cursor:pointer}
.evtxn tr.pick:hover td{color:var(--color-fg-primary)}
.evtxn tr.sel td{color:var(--color-fg-primary);font-weight:600}
.evtxn tr.sub td{font-size:var(--text--2);padding-left:var(--spacing-sm)}
.evtxn .per{display:inline-block;min-width:4.2em;color:var(--color-fg-secondary)}
.evbox .hint{font-size:var(--text--2);color:var(--color-fg-secondary);font-weight:400;margin-left:var(--spacing-2xs)}
/* A Journal Entry as it is booked: side, account, department, amount. */
.fx-e.jtab{font-family:inherit;margin-top:0;padding-top:0;border-top:0}
.fx-e table{width:auto;min-width:0}
.fx-e td{border:0;padding:2px var(--spacing-md) 2px 0;font-size:var(--text--1);background:transparent !important}
.fx-e td.side{color:var(--color-fg-secondary);white-space:nowrap}
.evbox .plan{margin-top:var(--spacing-sm);font-size:var(--text--1);color:var(--color-fg-secondary)}
/* Two ways to read one comparison, side by side above the table. */
.seg{display:inline-flex;gap:2px;background-color:var(--color-hairline);padding:2px;
  border-radius:var(--radius-pill)}
.seg button{font:inherit;font-size:var(--text--1);border:0;background:transparent;cursor:pointer;
  padding:var(--spacing-3xs) var(--spacing-sm);border-radius:var(--radius-pill);
  color:var(--color-fg-secondary);transition:background-color var(--duration-hover) var(--ease-out)}
.seg button[aria-pressed="true"]{background-color:var(--color-stark);color:var(--color-fg-primary)}
.fold ul.feeds{margin:0;padding-left:1.1em}
.fold ul.feeds li{font-size:var(--text--1);margin-bottom:var(--spacing-xs)}
.fold ul.feeds li small{display:block;color:var(--color-fg-secondary);margin-top:2px;font-size:var(--text--1)}

/* Page controls for a schedule: a search, one toggle, and the counts. */
.vtbar{display:flex;flex-wrap:wrap;align-items:center;gap:var(--spacing-2xs) var(--spacing-sm);
  margin-bottom:var(--spacing-xs)}
.vtbar input[type=search]{min-width:min(100%,22em)}

/* Text fields grow with what is typed. There is no resize handle, because a
   field that fits its text never needs one. `field-sizing` does it natively
   where supported; the script sets the height everywhere else. */
.cmt,.dispo textarea,#focus-card textarea{resize:none;overflow:hidden;field-sizing:content}
.cmt{width:100%;font:inherit;font-size:var(--text--1);min-height:2.3em;line-height:1.35;
  font-family:var(--font-sans);padding:var(--spacing-3xs) var(--spacing-2xs);
  border:1px solid var(--color-hairline);border-radius:var(--radius-xs);
  background-color:var(--color-stark);
  transition:border-color var(--duration-hover) var(--ease-out)}
.cmt:focus{outline:0;border-color:var(--color-vivid)}
.cmt::placeholder{color:var(--color-fg-inactive)}
/* A variance takes the accent only when it breaches the threshold, so the color
   is tied to the same rule as the status beside it. It never carries meaning alone. */
.sched .over{color:var(--color-accent-text)}

/* The section heading is the only break in the rail. It opens a group of pages
   and names what they have in common, so the space above it and the label are
   one gesture rather than two. Its size and weight set it apart from the items,
   so it groups without competing with the destinations it introduces. */
/* topbar */
.main{display:flex;flex-direction:column;min-width:0;overflow:hidden}
.topbar{display:flex;align-items:baseline;padding:var(--spacing-sm) var(--spacing-md-lg) 0;
  font-size:var(--text-1);flex:0 0 auto}
.view{flex:1 1 auto;overflow-y:auto;padding:var(--spacing-sm) var(--spacing-md-lg) var(--spacing-xl)}
.view[hidden]{display:none}
/* cropped hairline S, anchored top-left of the page head, purely decorative */
/* Serif's crossing-loop and hairline-curve motif, anchored bottom-right and
   bled off both edges so it reads as a crop. Decoration only: no pointer events,
   never over content, and it carries no information. */
/* Decoration in the content column only. The rail carries the wordmark, the
   use-case name and the nav, and a curve running behind those competes with them.
   The field fills .main exactly and is clipped by its overflow:hidden. The SVG is
   preserveAspectRatio slice and every stroke is drawn beyond the viewBox, so a
   stroke always leaves through an edge rather than stopping in open space. */
.motif{position:absolute;inset:0;width:100%;height:100%;
  color:var(--color-warm-gray);pointer-events:none;z-index:0;opacity:.7}
.main{position:relative}
.view{position:relative;z-index:1}
/* Switching views swaps the whole surface, which is jarring without a transition
   and sluggish with a long one. 200ms on an ease-out curve: the movement is
   visible immediately, which is the moment the eye is on it. `backwards` rather
   than `both` so no transform declaration survives the animation -- a lingering
   transform would become the containing block for the fixed-position focus
   overlay. Under reduced motion the rise is dropped and only opacity remains. */
.view:not([hidden]){animation:view-in var(--duration-control) var(--ease-out-quartic) backwards}
@keyframes view-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){
  .view:not([hidden]){animation:view-fade var(--duration-hover) var(--ease-out) backwards}
}
@keyframes view-fade{from{opacity:0}to{opacity:1}}
/* Pressable things acknowledge the press. */
.tnav .tbtn:active,.pill:active{transform:scale(0.97)}
.pill{transition:transform var(--duration-press) var(--ease-out)}
@media (prefers-reduced-motion:no-preference){
  .motif{animation:motif-in 1.1s var(--ease-out-quartic) both}
}
@keyframes motif-in{from{opacity:0}}

/* cards: stark surface, soft corners, no border, no shadow */
.grid{display:grid;gap:var(--spacing-sm)}
.g3{grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.g2{grid-template-columns:repeat(auto-fit,minmax(340px,1fr));align-items:start}
.card{background-color:var(--color-stark);padding:var(--spacing-md-lg);
  border-radius:var(--radius-sm)}
.kpi .v{font-family:var(--font-serif);font-size:var(--text-4);line-height:1.04;
  letter-spacing:-0.01em;margin-top:var(--spacing-3xs)}
/* Display size on a white card is large text, where 3:1 applies and #ff3d00
   reaches 3.55:1 -- so brand Red is kept for the headline figure. */
.kpi .v.accent{color:var(--color-vivid)}
.kpi .n{font-size:var(--text--1);color:var(--color-fg-secondary);margin-top:var(--spacing-2xs)}

/* charts */
.stack{display:flex;height:28px;gap:2px;margin-bottom:var(--spacing-sm)}
.stack span:first-child{border-radius:var(--radius-xs) 0 0 var(--radius-xs)}
.stack span:last-child{border-radius:0 var(--radius-xs) var(--radius-xs) 0}
.legend{display:flex;flex-wrap:wrap;gap:var(--spacing-sm);font-size:var(--text--1)}
.legend i{width:10px;height:10px;display:inline-block;margin-right:var(--spacing-3xs);
  border-radius:999px;vertical-align:-1px}
.legend b{font-weight:400;color:var(--color-fg-secondary);margin-left:var(--spacing-3xs)}
.bars{display:flex;flex-direction:column;gap:var(--spacing-xs)}
.bar{display:grid;grid-template-columns:1fr auto auto;
  gap:var(--spacing-3xs) var(--spacing-2xs);align-items:baseline;width:100%;
  background:none;border:0;padding:0;text-align:left;cursor:pointer;
  border-radius:var(--radius-xs);transition:opacity var(--duration-hover) var(--ease-out)}
.bar:hover{opacity:.72}
.bar .lab{font-size:var(--text--1)}
.bar .val{font-size:var(--text--1);text-align:right;font-variant-numeric:tabular-nums}
.bar .shr{font-size:var(--text--2);color:var(--color-fg-secondary);min-width:3.2em;
  text-align:right;font-variant-numeric:tabular-nums}
.bar .track{grid-column:1/-1;height:6px;background-color:var(--color-hairline);
  border-radius:999px;overflow:hidden;margin-top:var(--spacing-3xs)}
.bar .fill{display:block;height:100%;background-color:var(--color-mid-gray);border-radius:999px;
  width:0;transition:width 600ms var(--ease-out)}
/* A bar is a graphic carrying its own label and value, and the hue difference
   from the track is large, so brand Red is kept here too. */
.bar .fill.accent{background-color:var(--color-vivid)}
/* Equal-height cards in one band, but content sits under its heading rather than
   floating in the middle of whatever height the tallest card sets. */
.charts{grid-template-columns:repeat(auto-fit,minmax(310px,1fr));align-items:stretch}
.charts .card{display:flex;flex-direction:column}
.charts .card > h3{margin-bottom:var(--spacing-sm)}
/* The tick-and-tie: the two parts foot to the total, so the total is ruled. */
table.tie td,table.tie th{padding:var(--spacing-3xs) var(--spacing-2xs)}
table.tie .num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
table.tie th{font-size:var(--text--2);font-weight:600;color:var(--color-fg-secondary)}
table.tie tr.tsub td{font-weight:600}
table.tie .tind{display:inline-block;width:var(--spacing-sm)}
table.tie tr.tleft td{color:var(--color-accent-text)}
table.tie tr.ttot td{font-weight:600;border-top:1px solid var(--color-fg-primary)}
table.tie + .note{margin-top:var(--spacing-xs);font-size:var(--text--2)}
.bars + .note{margin-top:var(--spacing-xs);font-size:var(--text--2)}
.tmap{position:relative;width:100%}
.tcell{position:absolute;display:flex;flex-direction:column;justify-content:flex-start;
  gap:2px;overflow:hidden;text-align:left;padding:var(--spacing-2xs) var(--spacing-xs);
  border:0;border-radius:4px;cursor:pointer;font:inherit;color:var(--color-fg-primary);
  background-color:var(--color-bg-primary);
  /* The 2px gap between fills, drawn in the card's own surface so it holds at
     any scale. */
  box-shadow:inset 0 0 0 1px var(--color-stark);
  transition:background-color var(--duration-hover) var(--ease-out)}
.tcell:hover,.tcell:focus-visible{background-color:var(--color-hairline)}
.tcell .tl{font-size:var(--text--1);line-height:1.2;overflow-wrap:normal}
.tcell .tv,.tcell .tn{white-space:nowrap}
.tcell .tv{font-size:var(--text-0);line-height:1.1;
  font-variant-numeric:tabular-nums}
.tcell .tn{font-size:var(--text--2);color:var(--color-fg-secondary)}

/* pills: the site's cta-link */
.pill{display:inline-flex;align-items:center;gap:var(--spacing-2xs);
  padding-inline:var(--spacing-sm);padding-block:var(--spacing-2xs);font-size:var(--text--1);
  line-height:1.15;border:1px solid transparent;border-radius:var(--radius-pill);cursor:pointer;
  background-color:var(--color-bg-inverse);color:var(--color-fg-inverse);
  transition:border-color var(--duration-hover) var(--ease-out),
             background-color var(--duration-hover) var(--ease-out),
             color var(--duration-hover) var(--ease-out)}
/* Hover marks the border, not the fill: filling with the accent would put the
   light label on Red. */
.pill:hover,.pill:focus-visible{border-color:var(--color-vivid)}
/* The vivid pill marks the one action worth taking next. There is never more
   than one on a view, so the color keeps meaning "go here". */
/* The primary action keeps brand Red as a ring rather than a fill.
   #ff3d00 cannot carry light text (2.82:1) or dark text (3.86:1) at body size,
   so the fill is Dark Gray -- white on it is 13.8:1 -- and Red does what
   the brand asks of it: highlight the call to action. */
.pill--go{background-color:var(--color-bg-inverse);color:#fff;
  border:2px solid var(--color-vivid);padding-block:calc(var(--spacing-2xs) - 1px)}
.pill--go:hover,.pill--go:focus-visible{background-color:var(--color-bg-inverse);
  border-color:var(--color-vivid);border-radius:var(--radius-md)}
.pill--go .arw{transition:transform var(--duration-hover) var(--ease-out)}
.pill--go:hover .arw{transform:translateX(3px)}
/* Sits at the end of a view, so finishing the content puts the next move in
   front of you rather than sending you back to the rail to guess. */
/* Left-aligned: the eye returns to the left margin at the end of a block, so
   the next move sits where the next line would start. */
.nextstep{display:flex;justify-content:flex-start;margin-top:var(--spacing-md)}
.nextstep:empty{display:none}
.pill:active{transform:scale(0.97)}
.pill--knockout{background-color:var(--color-bg-primary);border-color:var(--color-fg-primary);
  color:var(--color-fg-primary)}
.pill--knockout:not(.active):hover,.pill--knockout:not(.active):focus-visible{
  background-color:var(--color-stark);border-color:var(--color-stark)}
.pill--knockout.active{background-color:var(--color-bg-inverse);border-color:var(--color-bg-inverse);
  color:var(--color-fg-inverse)}
.pill .dot{width:8px;height:8px;border-radius:999px;display:inline-block}

/* The threshold row: a setting, deliberately styled unlike the filter chips.
   The currency sign lives inside the field so the control reads as one object
   rather than a stray glyph beside a box. */
.throw{display:flex;flex-wrap:wrap;align-items:center;gap:var(--spacing-2xs);
  margin-bottom:var(--spacing-sm)}
.throw label{font-size:var(--text-0);color:var(--color-fg-primary)}
.fixfield{display:inline-flex;align-items:baseline;gap:1px;
  background-color:var(--color-stark);border-radius:var(--radius-xs);
  padding:0.34em 0.7em;transition:border-radius var(--duration,.2s) ease}
.fixfield:focus-within{border-radius:var(--radius-sm)}
.fixfield .cur{font-size:var(--text--1);color:var(--color-fg-secondary)}
.fixfield input{width:5.4em;font:inherit;font-size:var(--text-0);
  font-variant-numeric:tabular-nums;color:var(--color-fg-primary);
  background:none;border:0;border-radius:0;padding:0 0 0 1px;text-align:left}
.fixfield input:focus{outline:0}
.fixfield input::-webkit-outer-spin-button,
.fixfield input::-webkit-inner-spin-button{opacity:.35}
.throw .thnote{flex:1 1 100%;font-size:var(--text--1);
  color:var(--color-fg-secondary);margin-top:calc(-1 * var(--spacing-3xs))}
/* Collapsible card: shut by default so the queue is what you see first.
   The card's own padding moves onto the summary, so the whole white strip is the
   click target rather than just the run of text inside it.
   Hover does NOT tint the surface: the only tint dark enough to register is the
   page ground itself, which would read as the card disappearing. The design
   system's own affordance is the corner radius opening up, so that is what moves,
   along with the caret. */
.fold{padding:0}
.fold > summary{cursor:pointer;list-style:none;display:flex;align-items:baseline;
  gap:var(--spacing-2xs);padding:var(--spacing-md-lg);
  border-radius:var(--radius-sm);
  transition:border-radius 200ms var(--ease-out),transform 160ms var(--ease-out)}
.fold > summary::-webkit-details-marker{display:none}
@media (hover:hover) and (pointer:fine){
  .fold > summary:hover{border-radius:var(--radius-lg)}
  .fold > summary:hover .caret{transform:translateX(3px)}
  .fold[open] > summary:hover .caret{transform:rotate(90deg) translateX(3px)}
}
.fold > summary:active{transform:scale(0.995)}
.fold > summary h3{margin:0}
.fold > summary .sub{font-size:var(--text--1);color:var(--color-fg-secondary)}
/* Say what the click does. A lone chevron is not an instruction. */
.fold > summary .cue{margin-left:auto;display:inline-flex;align-items:center;
  gap:var(--spacing-3xs);font-size:var(--text--1);color:var(--color-fg-secondary)}
.fold > summary .cue-close{display:none}
.fold[open] > summary .cue-open{display:none}
.fold[open] > summary .cue-close{display:inline}
@media (hover:hover) and (pointer:fine){
  .fold > summary:hover .cue{color:var(--color-fg-primary)}
}
.fold > summary .caret{font-size:var(--text--1);
  color:var(--color-fg-secondary);transition:transform 200ms var(--ease-out)}
.fold[open] > summary .caret{transform:rotate(90deg)}
.fold[open] > summary{border-radius:var(--radius-sm) var(--radius-sm) 0 0}
.fold > summary:focus-visible{outline:2px solid var(--color-vivid);
  outline-offset:-3px}
.fold .foldbody{padding:0 var(--spacing-md-lg) var(--spacing-md-lg)}
/* Settings row: the threshold on the left, Focus mode hard right. Neither is a
   filter, so neither sits in the filter grid. */
.setrow{display:flex;flex-wrap:wrap;align-items:center;gap:var(--spacing-sm);
  margin-bottom:var(--spacing-sm)}
.setrow .throw{margin-bottom:0}
.belowline{font:inherit;font-size:var(--text--1);color:var(--color-fg-secondary);
  background:none;border:0;padding:0;cursor:pointer;text-align:left;
  transition:color var(--duration-hover) var(--ease-out)}
.belowline:hover{color:var(--color-fg-primary)}
.setrow .act{margin-left:auto;display:inline-flex;align-items:center;
  gap:var(--spacing-3xs)}
.setrow .act .ic{width:1.05em;height:1.05em;flex:none}
/* Filters on labeled rows. Three unlabeled rows of chips give no clue which
   control does what; a label column makes each row self-describing and lets the
   chips themselves lose their redundant prefixes. */
.filters{display:grid;grid-template-columns:auto minmax(0,1fr);
  gap:var(--spacing-2xs) var(--spacing-sm);align-items:center;
  margin-bottom:var(--spacing-sm)}
.flabel{font-size:var(--text--1);color:var(--color-fg-secondary);white-space:nowrap}
.fchips{display:flex;flex-wrap:wrap;gap:var(--spacing-2xs);align-items:center}
.fchips #q{width:min(100%,27em)}
@media (max-width:760px){
  .filters{grid-template-columns:minmax(0,1fr);gap:var(--spacing-3xs)}
  .flabel:not(:first-child){margin-top:var(--spacing-2xs)}
}
/* The selected threshold row reads as chosen, not just hovered. */
.bar.on .lab{color:var(--color-fg-primary)}
.bar .lab .tag{font-style:normal;font-size:var(--text--2);color:var(--color-accent-text);
  margin-left:var(--spacing-3xs)}
.controls{display:flex;flex-wrap:wrap;gap:var(--spacing-2xs);align-items:center;
  margin-bottom:var(--spacing-2xs)}
.controls:last-of-type{margin-bottom:var(--spacing-xs)}
input[type=search]{padding:var(--spacing-2xs) var(--spacing-sm);border:1px solid var(--color-warm-gray);
  background-color:var(--color-stark);border-radius:var(--radius-pill);min-width:250px;
  font-size:var(--text--1)}

/* workspace */
/* Review is an app pane, not a document: the view itself does not scroll, and
   the two columns divide the leftover height between them. Previously the view
   scrolled as well as both columns, which put three scrollbars on one screen and
   made the inner ones read as accidental. min-height:0 is what lets a grid child
   shrink below its content so its own overflow engages. */
#v-review:not([hidden]){display:flex;flex-direction:column;overflow:hidden;
  padding-bottom:var(--spacing-md-lg)}
#v-review .work{flex:1 1 auto;min-height:0}
.work{display:grid;grid-template-columns:minmax(310px,430px) 1fr;gap:var(--spacing-sm);
  align-items:stretch}
.work > *{min-height:0}
.list{background-color:var(--color-stark);border-radius:var(--radius-sm);
  overflow-y:auto;padding:var(--spacing-2xs)}
.ghead{padding:var(--spacing-sm) var(--spacing-sm) var(--spacing-2xs);
  font-size:var(--text--1);color:var(--color-fg-secondary);position:sticky;top:0;
  background-color:var(--color-stark);z-index:2}
/* The layer heading sits above the group headings and carries the step number,
   so the order of the work is legible without a written instruction. It is not
   sticky: two stacked sticky headers leave almost no room for the list itself. */
.lhead{display:flex;align-items:center;gap:var(--spacing-xs);
  padding:var(--spacing-md) var(--spacing-sm) var(--spacing-3xs);
  border-top:1px solid var(--color-hairline);margin-top:var(--spacing-xs)}
.lhead:first-child{border-top:0;margin-top:0;padding-top:var(--spacing-sm)}
.ltxt{font-weight:600;font-size:var(--text-0)}
/* The correction. Two values and an arrow, because that is the whole question.
   The target is the only thing on the card carrying the accent, so the eye lands
   on what the ledger becomes rather than on what it currently says. */
.fix{margin:var(--spacing-sm) 0;padding:var(--spacing-sm);border-radius:var(--radius-sm);
  background-color:var(--color-bg-primary)}
.fx-h{font-size:var(--text--2);color:var(--color-fg-secondary);
  margin-bottom:var(--spacing-2xs)}
.fx-p{display:flex;align-items:stretch;gap:var(--spacing-sm);flex-wrap:wrap}
.fx-c{display:flex;flex-direction:column;gap:2px;min-width:0;flex:1 1 14rem}
.fx-c span{font-size:var(--text--2);color:var(--color-fg-secondary)}
.fx-c b{font-size:var(--text-0);font-weight:600;overflow-wrap:anywhere}
.fx-t b{color:var(--color-accent-text)}
.fx-a{align-self:center;color:var(--color-fg-secondary);font-size:var(--text-1);flex:none}
.fx-e{margin-top:var(--spacing-xs);padding-top:var(--spacing-xs);
  border-top:1px solid var(--color-hairline);font-family:var(--font-mono);
  font-size:var(--text--1);overflow-wrap:anywhere}
/* Stacked on a phone: a horizontal arrow between two stacked values reads wrong. */
@media (max-width:30rem){.fx-a{transform:rotate(90deg);align-self:flex-start}}
.row{display:grid;grid-template-columns:auto 1fr auto;gap:var(--spacing-2xs);align-items:baseline;
  padding:var(--spacing-xs) var(--spacing-sm);cursor:pointer;border-radius:var(--radius-xs);
  transition:background-color var(--duration-card) var(--ease-out),
             border-radius var(--duration-card) var(--ease-out)}
.row:hover{background-color:var(--color-bg-primary);border-radius:var(--radius-sm)}
.row[aria-selected="true"]{background-color:var(--color-hairline);border-radius:var(--radius-sm)}
.row.done .ti,.row.done .am{color:var(--color-fg-inactive)}
.row .sv{width:8px;height:8px;border-radius:999px;transform:translateY(-0.15em)}
.row .ti{font-size:var(--text--1);line-height:1.3;min-width:0;overflow-wrap:anywhere}
.row .am{font-size:var(--text--1);color:var(--color-fg-secondary);white-space:nowrap}
.row .meta{grid-column:2/-1;font-size:var(--text--2);color:var(--color-fg-secondary);
  margin-top:var(--spacing-3xs);display:flex;gap:var(--spacing-2xs);flex-wrap:wrap}
.row .vd{color:var(--color-red-text)}
.detail{background-color:var(--color-stark);border-radius:var(--radius-sm);
  padding:var(--spacing-md-lg);overflow-y:auto}
.detail .sev{display:inline-block;font-size:var(--text--2);
  padding:var(--spacing-3xs) var(--spacing-xs);border-radius:var(--radius-pill);
  background-color:var(--color-bg-primary)}
.detail .dt{font-family:var(--font-sans);font-size:var(--text-2);font-weight:400;line-height:1.04;
  margin:var(--spacing-sm) 0 0;text-wrap:balance}
.kv{display:grid;grid-template-columns:104px minmax(0,1fr);
  gap:var(--spacing-xs) var(--spacing-md);
  margin-top:var(--spacing-md);font-size:var(--text--1)}
.kv dt{color:var(--color-fg-secondary)}
.kv dd{margin:0}
.rec{background-color:var(--color-bg-primary);padding:var(--spacing-sm) var(--spacing-md);
  margin-top:var(--spacing-md);font-size:var(--text--1);border-radius:var(--radius-sm)}
.conf{margin-top:var(--spacing-sm);font-size:var(--text--1);color:var(--color-fg-secondary)}
.confbar{height:4px;background-color:var(--color-hairline);border-radius:999px;
  margin-top:var(--spacing-3xs);max-width:190px}
.confbar i{display:block;height:100%;background-color:var(--color-mid-gray);border-radius:999px}

/* decision */
.dispo{margin-top:var(--spacing-md);padding-top:var(--spacing-md);
  border-top:1px solid var(--color-hairline)}
.acts{display:flex;flex-wrap:wrap;gap:var(--spacing-2xs)}
.dispo textarea{width:100%;margin-top:var(--spacing-sm);min-height:62px;
  padding:var(--spacing-2xs) var(--spacing-sm);border:1px solid var(--color-warm-gray);
  background-color:var(--color-stark);border-radius:var(--radius-sm);font-size:var(--text--1);
  font-family:var(--font-sans);line-height:1.4}
.dispo .stamp{font-size:var(--text--2);color:var(--color-fg-secondary);margin-top:var(--spacing-2xs)}
.hints{display:grid;grid-template-columns:auto 1fr;gap:var(--spacing-3xs) var(--spacing-sm);
  margin:var(--spacing-sm) 0 0;font-size:var(--text--2);color:var(--color-fg-secondary)}
.hints dt{color:var(--color-fg-primary)}
.hints dd{margin:0}
.hints em{font-style:normal;color:var(--color-red-text)}
.notelab{display:block;margin-top:var(--spacing-sm);font-size:var(--text--2);
  color:var(--color-fg-secondary)}
.incomplete{color:var(--color-red-text)}
.reqd{color:var(--color-red-text)}

/* tables */
table{width:100%;border-collapse:collapse;font-size:var(--text--1)}
th{text-align:left;font-weight:600;color:var(--color-fg-secondary);
  padding:0 var(--spacing-sm) var(--spacing-2xs) 0;border-bottom:1px solid var(--color-hairline)}
td{padding:var(--spacing-2xs) var(--spacing-sm) var(--spacing-2xs) 0;
  border-bottom:1px solid var(--color-hairline);vertical-align:top}
td:last-child,th:last-child{padding-right:0}
td.num,th.num{text-align:right;white-space:nowrap}
/* Zebra banding, so a row's department, count and value stay tied together when
   the eye travels across a wide table. The tint is Warm Gray at low alpha
   rather than a grey, so it stays in the palette, and it is deliberately faint --
   enough to group a row, not enough to read as a state. The cells are banded, not
   the row, because a row background would paint under the border and break the
   rules between rows. */
tbody tr:nth-child(even) td{background-color:rgba(173,169,144,0.13)}

/* Dimension status: a word, never a color on its own. */
.dimyes,.dimno{font-size:var(--text--1);white-space:nowrap}
.dimyes{color:var(--color-accent-text)}
.dimno{color:var(--color-fg-secondary)}
.cov ul{margin:0;padding-left:1.1em}
.cov li{font-size:var(--text--1);margin-bottom:var(--spacing-sm)}
.cov li small{color:var(--color-fg-secondary);display:block;margin-top:var(--spacing-3xs);
  font-size:var(--text--1)}
.exp{display:flex;flex-wrap:wrap;gap:var(--spacing-2xs);margin-bottom:var(--spacing-md)}
/* Decisions, the finish step. The next thing to do leads, on its own card; the
   summary of outcomes follows as one row of counts; each group is a plain table. */
.dnext h3{margin-bottom:var(--spacing-2xs)}
.dnext .dline{display:flex;flex-wrap:wrap;align-items:center;gap:var(--spacing-2xs) var(--spacing-sm);
  margin-top:var(--spacing-sm)}
.dnext .dline .pill--go{margin-left:auto}
.dnext .pill:disabled{opacity:.4;cursor:not-allowed;border-color:transparent}
.dnext .why{flex-basis:100%;font-size:var(--text--2);color:var(--color-fg-secondary);text-align:right}
.dtiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:var(--spacing-2xs)}
.dtile{display:flex;flex-direction:column;gap:var(--spacing-3xs);text-align:left;font:inherit;cursor:pointer;
  background-color:var(--color-bg-primary);border:0;border-radius:var(--radius-xs);padding:var(--spacing-xs) var(--spacing-sm);
  color:var(--color-fg-primary);transition:background-color var(--duration-hover) var(--ease-out)}
.dtile:hover,.dtile:focus-visible{background-color:var(--color-hairline)}
.dtile .dv{font-family:var(--font-serif);font-size:var(--text-3);line-height:1.04;font-variant-numeric:tabular-nums}
.dtile .dl{font-size:var(--text--1)}
.dtile .dn{font-size:var(--text--2);color:var(--color-fg-secondary)}
.dtile.open .dv{color:var(--color-vivid)}
.dtile.zero .dv{color:var(--color-fg-secondary)}
.dgroup h3,.dfinish h3{display:flex;flex-wrap:wrap;align-items:baseline;gap:var(--spacing-2xs) var(--spacing-sm)}
.dgroup h3 .n,.dfinish h3 .n{font-weight:400;color:var(--color-fg-secondary);font-size:var(--text--1)}
.dgroup table td{font-size:var(--text--1)}
.dgroup td .sub2,.dfinish .sub2{display:block;font-size:var(--text--2);color:var(--color-fg-secondary);margin-top:2px}
.dgroup td.when{font-family:var(--font-mono);font-size:11px;white-space:nowrap}
.dgroup tr.xp{cursor:pointer}
.dgroup tr.xp:hover td{background-color:rgba(173,169,144,0.16)}
.dgroup.isopen h3::before{content:"";width:7px;height:7px;border-radius:999px;background-color:var(--color-vivid);
  align-self:center}
.dfinish ol{margin:0;padding-left:1.3em;display:grid;gap:var(--spacing-md)}
.dfinish li > b{display:block;margin-bottom:var(--spacing-3xs)}
.dfinish li p{margin:var(--spacing-3xs) 0 var(--spacing-2xs);font-size:var(--text--1);color:var(--color-fg-secondary);line-height:1.45}
.dfinish .uprow{display:flex;flex-wrap:wrap;align-items:flex-end;gap:var(--spacing-2xs) var(--spacing-sm)}
.dfinish .uprow label{display:flex;flex-direction:column;gap:var(--spacing-3xs);font-size:var(--text--2);
  font-weight:600;color:var(--color-fg-secondary)}
.dfinish .uprow .fld{min-width:14rem;font-weight:400;font-size:var(--text--1)}
.dfinish .done{color:var(--color-fg-primary);font-size:var(--text--1)}
.dfinish.flash{animation:dflash 1.2s var(--ease-out)}
@keyframes dflash{from{box-shadow:0 0 0 3px var(--color-vivid)}to{box-shadow:0 0 0 0 transparent}}
.dfiles .fgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));gap:var(--spacing-sm) var(--spacing-lg)}
.dfiles h4{margin:0;font-size:var(--text--1);font-weight:600}
.dfiles .note{margin:var(--spacing-3xs) 0 var(--spacing-2xs);font-size:var(--text--2)}
.dfiles .exp,.dreset .exp{margin-bottom:0}
.dreset{background-color:transparent;border:1px dashed var(--color-warm-gray)}
.dreset .note{margin:0 0 var(--spacing-xs)}
.loadsum{border-left:3px solid var(--color-vivid)}
.loadsum ul{margin:var(--spacing-2xs) 0 0;padding-left:1.2em;font-size:var(--text--1)}
.loadsum li{margin-bottom:var(--spacing-3xs)}
#ask-body{white-space:pre-line}
/* Who is reviewing, beside the threshold in the bar. */
.tnav .tthr.twho{margin-left:var(--spacing-2xs)}
.tnav .tthr.twho input{width:11ch;font-variant-numeric:normal}
.tnav .tthr.twho input::placeholder{color:var(--color-warm-gray)}
/* A line's own outcome, in the row's line table. */
.evtxn select.lout{font:inherit;font-size:var(--text--2);min-height:var(--ctl-h);padding:0 var(--spacing-2xs);
  border:1px solid var(--color-warm-gray);border-radius:var(--radius-pill);background-color:transparent;
  color:var(--color-fg-primary);cursor:pointer}
.evtxn select.lout:hover{border-color:var(--color-fg-primary);background-color:var(--color-stark)}
.evtxn tr.lout-on td{background-color:rgba(173,169,144,0.10) !important}
.evtxn .lstate{display:block;margin-top:2px;font-size:var(--text--2);color:var(--color-fg-primary)}
.evtxn .lstate.needs{color:var(--color-accent-text)}
.restbox{margin-top:var(--spacing-md)}
.restbox .rh{font-size:var(--text--1);margin-bottom:var(--spacing-2xs)}
.restbox .rh b{font-weight:600}
/* Native confirm() is chrome-styled, says "This page says", and cannot be
   themed. A <dialog> keeps the destructive confirmation inside the design system
   and lets the consequence be stated in the app's own words. */
dialog.ask{border:0;padding:0;background:none;max-width:min(92vw,46ch)}
dialog.ask::backdrop{background-color:rgba(46,45,41,0.55)}
dialog.ask .inner{background-color:var(--color-stark);
  border-radius:var(--radius-md);padding:var(--spacing-md-lg)}
dialog.ask h3{margin:0 0 var(--spacing-2xs)}
dialog.ask p{margin:0;font-size:var(--text--1);color:var(--color-fg-secondary);
  line-height:1.5}
dialog.ask .acts{display:flex;gap:var(--spacing-2xs);justify-content:flex-end;
  margin-top:var(--spacing-md)}
dialog.ask[open]{animation:ask-in 160ms var(--ease-out-quartic) backwards}
@keyframes ask-in{from{opacity:0;transform:scale(0.97)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){
  dialog.ask[open]{animation:none}
}
.sharedbar{flex:none;position:relative;z-index:2;background-color:var(--color-stark);padding:var(--spacing-xs) var(--spacing-md-lg);
  font-size:var(--text--1);color:var(--color-fg-primary)}
body.shared .twho,body.shared .uprow label:first-child{display:none}
body.shared .dreset .note{display:none}
/* --layout ui-update */
.chtiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(12.5rem,1fr));gap:var(--spacing-xs);margin-bottom:var(--spacing-sm)}
.chtile{background-color:var(--color-stark);border-radius:var(--radius-sm);padding:var(--spacing-sm)}
.chtile .k{font-size:var(--text--1);color:var(--color-fg-secondary)}
.chtile .v{font-size:var(--text-2);margin:.2em 0 .15em;font-variant-numeric:tabular-nums;letter-spacing:-0.01em}
.chtile .s{font-size:var(--text--2);color:var(--color-fg-secondary);line-height:1.4}
.unfav{color:var(--color-accent-text)}
.chgrid{margin-bottom:var(--spacing-sm)}
.chbars{display:grid;gap:.1em;font-size:var(--text--1)}
.chbar{display:grid;grid-template-columns:minmax(8rem,14rem) 1fr 7rem;gap:.8em;align-items:center;padding:.15em .3em;border-radius:4px}
.chbar:hover{background-color:var(--color-bg-primary)}
.chbar .lab{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chbar .trk{position:relative;height:1em}
.chbar .mid{position:absolute;left:50%;top:-.2em;bottom:-.2em;border-left:1px solid var(--color-mid-gray)}
.chbar .b{position:absolute;top:0;height:100%;border-radius:4px}
.chbar .b.inc{left:50%;background-color:var(--color-red-text)}
.chbar .b.dec{right:50%;background-color:var(--color-mid-gray)}
.chbar .val{text-align:right;font-variant-numeric:tabular-nums}
.chlegend{display:flex;gap:var(--spacing-sm);font-size:var(--text--2);color:var(--color-fg-secondary);margin-top:var(--spacing-xs)}
.chlegend i{display:inline-block;width:.8em;height:.8em;border-radius:2px;margin-right:.35em;vertical-align:-.05em}
.chlegend i.inc{background-color:var(--color-red-text)} .chlegend i.dec{background-color:var(--color-mid-gray)}
/* A balance sheet move has no favorable direction: over the threshold is weight, not color. */
.bsover{font-weight:600}
.wf{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:var(--spacing-2xs);margin-top:var(--spacing-xs)}
.wf-col{display:flex;flex-direction:column;min-width:0}
.wf-plot{position:relative;height:15rem}
.wf-zero{position:absolute;left:-.3em;right:-.3em;border-top:1px solid var(--color-mid-gray)}
.wf-bar{position:absolute;left:12%;right:12%;border-radius:4px}
.wf-bar.fav{background-color:var(--color-mid-gray)}
.wf-bar.unf{background-color:var(--color-red-text)}
.wf-bar.net{background-color:var(--color-dark-gray)}
.wf-val{position:absolute;left:0;right:0;text-align:center;font-size:var(--text--2);font-variant-numeric:tabular-nums;white-space:nowrap}
.wf-lab{font-size:var(--text--2);color:var(--color-fg-secondary);text-align:center;margin-top:.5em;line-height:1.25;overflow-wrap:anywhere}
.chlegend i.netk{background-color:var(--color-dark-gray)}
.chsub{display:block;color:var(--color-fg-secondary);font-size:var(--text--2);margin-top:.15em}
.chfacts{margin:0;padding-left:1.1em;line-height:1.5;font-size:var(--text--1)} .chfacts li{margin-bottom:.4em}
.chsec{margin-bottom:var(--spacing-sm)}
.chsech{margin:var(--spacing-md) 0 var(--spacing-xs)}
.chdept{border-bottom:1px solid var(--color-hairline);font-size:var(--text--1)}
.chdept summary,.chdept.chhead{display:grid;grid-template-columns:1fr 8rem 8rem 8rem;gap:.8em;padding:.5em .3em;cursor:pointer}
.chdept.chhead{cursor:default;color:var(--color-fg-secondary);font-size:var(--text--2);font-weight:600}
.chdept .n{text-align:right;font-variant-numeric:tabular-nums}
.chdept table{margin:0 0 .6em 1em;width:calc(100% - 1em)}
body.uiupd .kpi .v,body.uiupd .dtile .dv{font-family:var(--font-sans)}
.tnsx .navct:empty{display:none}
.warnbox{background-color:var(--color-stark);padding:var(--spacing-sm) var(--spacing-md);
  border-radius:var(--radius-sm);font-size:var(--text--1);margin-bottom:var(--spacing-sm)}
.empty{color:var(--color-fg-secondary);padding:var(--spacing-xl) 0;text-align:center;
  font-size:var(--text--1)}
.note{font-size:var(--text--1);color:var(--color-fg-secondary);line-height:1.5}
.note b{color:var(--color-fg-primary);font-weight:600}
/* A recorded default reads as secondary, and says so, so it cannot pass for a
   reason somebody wrote. */
.implied{color:var(--color-fg-secondary)}
.implied em{font-style:normal;display:block;font-size:var(--text--2);
  color:var(--color-fg-inactive);margin-top:2px}
.sign{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
  gap:var(--spacing-lg)}
.sign .role{font-size:var(--text--1);color:var(--color-fg-secondary)}
.sign .line{display:flex;align-items:center;gap:var(--spacing-2xs);
  margin-top:var(--spacing-2xs);border-bottom:1px solid var(--color-warm-gray);
  padding-bottom:var(--spacing-3xs)}
.sign .line input{flex:1 1 auto;min-width:0;font:inherit;font-size:var(--text--1);
  background:none;border:0;padding:var(--spacing-3xs) 0;color:var(--color-fg-primary)}
.sign .line input:focus{outline:0}
.sign .signed{font-size:var(--text--1);color:var(--color-fg-primary);
  padding:var(--spacing-3xs) 0}
.sign .when{font-size:var(--text--2);color:var(--color-fg-secondary);
  margin-top:var(--spacing-3xs);display:block}
.sign .mini{font:inherit;font-size:var(--text--2);background:none;border:0;padding:0;
  cursor:pointer;color:var(--color-fg-secondary);white-space:nowrap;
  transition:color var(--duration-hover) var(--ease-out)}
.sign .mini:hover{color:var(--color-accent-text)}
.sign .blocked{font-size:var(--text--2);color:var(--color-red-text);
  margin-top:var(--spacing-3xs);display:block}

#tip{position:fixed;z-index:60;background-color:var(--color-bg-inverse);
  color:var(--color-fg-inverse);font-size:var(--text--2);padding:var(--spacing-3xs) var(--spacing-2xs);
  pointer-events:none;border-radius:var(--radius-xs);opacity:0;
  transition:opacity var(--duration-hover) var(--ease-out);max-width:260px}
#tip.on{opacity:1}
#toast{position:fixed;bottom:var(--spacing-md);left:50%;transform:translateX(-50%);
  background-color:var(--color-bg-inverse);color:var(--color-fg-inverse);font-size:var(--text--1);
  padding:var(--spacing-2xs) var(--spacing-md);border-radius:var(--radius-pill);opacity:0;
  pointer-events:none;transition:opacity var(--duration-control) var(--ease-out);z-index:70}
#toast.on{opacity:1}

.tiefail{background-color:var(--color-accent-text);color:#fff;
  padding:var(--spacing-2xs) var(--spacing-md-lg);font-size:var(--text--1)}
.coverage{font-size:var(--text--1);color:var(--color-fg-secondary);
  margin:var(--spacing-2xs) 0 var(--spacing-sm)}
.cluster{padding:var(--spacing-xs) var(--spacing-sm);cursor:pointer;
  border-radius:var(--radius-xs);transition:background-color var(--duration-card) var(--ease-out)}
.cluster:hover{background-color:var(--color-bg-primary);border-radius:var(--radius-sm)}
.cluster[aria-selected="true"]{background-color:var(--color-hairline);border-radius:var(--radius-sm)}
.cluster .n{font-size:var(--text--2);color:var(--color-fg-secondary)}
.members{margin-top:var(--spacing-sm);border-top:1px solid var(--color-hairline)}
.members .m{display:flex;gap:var(--spacing-sm);justify-content:space-between;
  padding:var(--spacing-2xs) 0;border-bottom:1px solid var(--color-hairline);
  font-size:var(--text--1)}
.members .m span:last-child{white-space:nowrap;color:var(--color-fg-secondary)}
#focus{position:fixed;inset:0;z-index:80;background-color:var(--color-bg-primary);
  overflow-y:auto;padding:var(--spacing-lg)}
.focus-inner{max-width:74ch;margin:0 auto}
.focus-bar{display:flex;align-items:center;justify-content:space-between;
  margin-bottom:var(--spacing-lg);font-size:var(--text--1)}
/* The shortcuts are the whole point of focus mode, so they sit above the card
   where they are read before the first decision rather than discovered after it.
   The accent at low alpha ties them to the one vivid color without filling a
   large area with it. */
.focus-keys{margin:0 auto var(--spacing-md);font-size:var(--text--1);
  text-align:center;background-color:rgba(255,61,0,0.09);
  color:var(--color-fg-primary);padding:var(--spacing-2xs) var(--spacing-md);
  border-radius:var(--radius-pill);display:table;line-height:1.7}
.focus-keys b{font-weight:600;color:var(--color-accent-text);
  font-variant-numeric:tabular-nums}
@media (max-width:640px){.focus-keys{display:block;border-radius:var(--radius-sm)}}
#focus-card .dt{font-size:var(--text-3)}
#focus-card .card{margin-bottom:var(--spacing-sm)}
#focus-card textarea{width:100%;margin-top:var(--spacing-sm);min-height:76px;
  padding:var(--spacing-2xs) var(--spacing-sm);border:1px solid var(--color-warm-gray);
  background-color:var(--color-stark);border-radius:var(--radius-sm);
  font-size:var(--text--1);font-family:var(--font-sans);line-height:1.4}
#focus-card textarea:focus{outline:2px solid var(--color-vivid);outline-offset:-2px}
@media(min-width:1500px){
  .work{grid-template-columns:minmax(360px,480px) 1fr}
}
@media(min-width:1900px){.g2{grid-template-columns:repeat(auto-fit,minmax(460px,1fr))}}
@media(max-width:900px){
  body{overflow:auto}
  .app{height:auto}
  .work{grid-template-columns:1fr} .list,.detail{max-height:none} .view{overflow:visible}
}
@media print{
  body{overflow:visible;background:#fff}
  .app{display:block} .tnav,.topbar,.controls,.exp,.acts{display:none}
  .view{display:block!important;overflow:visible;padding:0} .view[hidden]{display:block!important}
  .work{grid-template-columns:1fr} .list{display:none}
  .detail,.card{max-height:none;page-break-inside:avoid}
}
@media screen and (prefers-reduced-motion:reduce),(update:slow){
  *{transition-duration:0.001ms!important;animation-duration:0.001ms!important;
    animation-iteration-count:1!important;scroll-behavior:auto!important}
}
"""

JS = r"""
const D = window.__SERIF_RUN__;
/* Findings the schedules answer together with another, such as a stale bill's
   Accounts Payable line, which goes with its expense line. */
D.findings = D.findings.filter(f => ((D.views||{}).answered_with||[]).indexOf(f.finding_id) < 0);
const M = D.manifest, S = D.summary;
const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));
/* ---------- where the console keeps its state ----------
   Every read and write of saved state goes through Store. Opened as a file, Store
   is this browser's localStorage, as before. Published as a claude.ai Artifact
   with the db capability (shared mode), the Artifact's shared database is the
   record for everyone with access, and localStorage is a write-through cache: the
   page draws from the cache at once and takes the shared state when it arrives.
   Shared documents hold decisions, notes, entry edits and user ids. A name is
   never written to them: who decided is kept as a user id and named on screen. */
const Store = (function(){
  const binds = {};
  let live = null;
  return {
    getItem(k){ return localStorage.getItem(k); },
    /* In shared mode the shared database is the record, so a browser that will
       not store anything does not stop the work being saved. */
    setItem(k, v){
      if (live && binds[k]){ live.changed(binds[k]); try { localStorage.setItem(k, v); } catch(e){} return; }
      localStorage.setItem(k, v);
    },
    cache(k, v){ try { localStorage.setItem(k, v); } catch(e){} },
    bind(name, key, opts){ binds[key] = Object.assign({name: name, key: key, kind: 'map'}, opts); },
    all(){ return Object.values(binds); },
    attach(l){ live = l; },
  };
})();

const Shared = (function(){
  const S = {on: false, ro: false, uid: null, me: '', canEdit: false, db: null, user: null,
             runs: {}, stopped: false};
  const RID = String(M.run_id || 'unknown').replace(/[^A-Za-z0-9]/g, '').slice(0, 16) || 'unknown';
  const PER = String(M.period || 'period').toLowerCase().replace(/[^a-z0-9]+/g, '') || 'period';
  const runRoot = rid => 'review/' + PER + '/runs/' + rid;
  const ROOT = runRoot(RID);
  const MARK = 'serif-shared::' + ROOT;
  /* A document id takes letters, digits and _ - . : @ + only. Anything else, a
     space in a vendor's name, is written as ~ and its UTF-8 bytes in hex. The
     key itself is kept in the document, so the id is never read back. */
  function enc(k){
    let out = '';
    Array.from(new TextEncoder().encode(String(k))).forEach(b => {
      const c = String.fromCharCode(b);
      out += (b < 128 && /[A-Za-z0-9_\-.:@+]/.test(c)) ? c : '~' + b.toString(16).padStart(2, '0');
    });
    if (out === '.' || out === '..') out = '~2e' + out.slice(1);
    return out.length > 180 ? out.slice(0, 150) + '~h' + fingerprint(String(k)) : out;
  }
  const pathOf = (st, k) => st.kind === 'doc' ? st.path(RID) : runRoot(RID) + '/' + st.name + '/' + enc(k);
  const ONE = '__doc';
  const per = {};   // per store: last (what this page last wrote or took, as JSON), seen (the shared value)
  const base = {};  // per document: the revision this page last saw
  const Q = {};     // per document: the write in flight and the one waiting
  let inflight = 0; const waiting = [];
  const names = {};

  const rev = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  const nameOf = uid => !uid ? '' : uid === S.uid ? S.me : (names[uid] || 'Someone');
  /* The shared form of a value: every name taken out, who decided kept as an id. */
  function strip(v, st){
    if (Array.isArray(v)) return v.map(x => strip(x, st));
    if (!v || typeof v !== 'object') return v;
    const o = {};
    Object.keys(v).forEach(k => {
      if (k === 'by' || k === 'saved_by' || (st.names && k === 'name')) return;
      if (v[k] !== undefined) o[k] = strip(v[k], st);
    });
    if ('by' in v || (st.names && 'name' in v)){
      const who = v.by || (st.names ? v.name : '');
      o.by_uid = who && S.uid && who === S.me ? S.uid : (v.by_uid || null);
    }
    return o;
  }
  /* The local form: the id named as this viewer sees it, now. */
  function hydrate(v, st, ids){
    if (Array.isArray(v)) return v.map(x => hydrate(x, st, ids));
    if (!v || typeof v !== 'object') return v;
    const o = {};
    Object.keys(v).forEach(k => { o[k] = hydrate(v[k], st, ids); });
    if ('by_uid' in v){ if (v.by_uid) ids.add(v.by_uid);
      o.by = nameOf(v.by_uid); if (st.names) o.name = o.by; }
    return o;
  }
  function rename(v, st){
    if (Array.isArray(v)){ v.forEach(x => rename(x, st)); return; }
    if (!v || typeof v !== 'object') return;
    Object.keys(v).forEach(k => rename(v[k], st));
    if (v.by_uid){ v.by = nameOf(v.by_uid); if (st.names) v.name = v.by; }
  }
  function resolve(ids){
    if (!S.user || !ids.size) return;
    S.user.profiles(Array.from(ids)).then(ps => {
      let changed = false;
      Object.keys(ps).forEach(id => { const n = ps[id].name || 'Someone';
        if (id !== S.uid && names[id] !== n){ names[id] = n; changed = true; } });
      if (!changed) return;
      Store.all().forEach(st => { rename(st.get(), st); cacheOf(st); });
      later();
    }).catch(() => {});
  }
  const cacheOf = st => Store.cache(st.key, JSON.stringify(st.get()));

  /* What a store holds now, item by item, as it would be written. */
  function items(st){
    const cur = st.get() || {}, out = {};
    if (st.kind === 'doc'){ const sv = strip(cur, st);
      /* An empty record is no record: nothing is written for it. */
      if (Object.keys(sv).some(k => sv[k] != null && !(typeof sv[k] === 'object' && !Array.isArray(sv[k]) && !Object.keys(sv[k]).length)))
        out[ONE] = JSON.stringify(sv);
      return out; }
    Object.keys(cur).forEach(k => { if (cur[k] === undefined || (st.omit && st.omit(k, cur[k]))) return;
      out[k] = JSON.stringify(strip(cur[k], st)); });
    return out;
  }
  function put(st, k, value){
    const path = pathOf(st, k);
    const body = value === null ? null : {k: k, v: value, uid: S.uid, at: new Date().toISOString(), rev: rev()};
    if (body && st.ref){ const r = st.ref(k); if (r) body.ref = r; }
    const w = Q[path] || (Q[path] = {busy: false, want: undefined, st: st, k: k});
    w.want = {body: body}; if (!w.busy) pump(path);
  }
  const busy = path => !!Q[path] && (Q[path].busy || Q[path].want !== undefined);
  async function slot(){ if (inflight < 4){ inflight++; return; } await new Promise(r => waiting.push(r)); inflight++; }
  function release(){ inflight--; const n = waiting.shift(); if (n) n(); }
  async function pump(path){
    const w = Q[path]; w.busy = true;
    while (w.want !== undefined && S.on){
      const job = w.want; w.want = undefined;
      await slot();
      try {
        const ref = S.db.doc(path), cur = await ref.get();
        const curRev = cur.exists ? ((cur.data() || {}).rev || null) : null;
        const had = base[path] === undefined ? null : base[path];
        if (curRev !== had){ w.want = undefined; lost(w.st, w.k, path, cur); }
        else if (job.body === null){ if (cur.exists) await ref.delete(); base[path] = null; }
        else { await ref.set(job.body); base[path] = job.body.rev; }
      } catch(e){ await failed(e, w, job, path); }
      finally { release(); }
    }
    /* A change from someone else that arrived while this write was in flight. */
    if (w.skipped && S.on){ w.skipped = false;
      try { const cur = await S.db.doc(path).get();
        const r = cur.exists ? ((cur.data() || {}).rev || null) : null;
        if (r !== (base[path] === undefined ? null : base[path]) && w.want === undefined){
          const ids = new Set(); take(w.st, w.k, path, cur.exists ? cur.data() : null, ids);
          cacheOf(w.st); resolve(ids); later(); } } catch(e){} }
    w.busy = false; settle();
  }
  /* Someone else wrote this item since this page last saw it. Theirs stands, and
     the reviewer is told, so a decision is never overwritten unseen. */
  function lost(st, k, path, cur){
    const body = cur.exists ? cur.data() : null, ids = new Set();
    take(st, k, path, body, ids); resolve(ids); cacheOf(st); later();
    const who = body ? nameOf(body.uid) : '';
    toast(st.kind === 'doc' && st.name === 'signoff'
      ? (who || 'Someone') + ' changed the sign-off a moment ago. Theirs is showing; sign again if yours still stands.'
      : (who || 'Someone') + ' changed this a moment ago. Their decision is showing; make yours again if it still stands.', 4200);
  }
  async function failed(e, w, job, path){
    const code = (e && e.code) || 'unavailable';
    /* Refused: no access to write, or, for someone who has it, a change the
       store cannot take. */
    if (code === 'invalid_argument'){ if (S.canWrite === true) toast('This change could not be saved to the shared review. It is kept in this browser.', 3200); else readOnly(); return; }
    if ((code === 'unavailable' || code === 'resource_exhausted') && !job.retried){
      job.retried = true; await new Promise(r => setTimeout(r, 800 + Math.random() * 1200));
      if (w.want === undefined) w.want = job; return;
    }
    if (code === 'quota_exceeded'){ toast('The shared review is full and this change was not saved to it. It is kept in this browser.', 4200); return; }
    if (code === 'revoked' || code === 'not_granted' || code === 'capability_disabled' || code === 'capability_removed'){ stop(); return; }
    toast('This change did not reach the shared review. It is kept in this browser.', 3200);
  }
  /* Writes are refused: this person can read the review, not change it. */
  function readOnly(){
    if (!S.ro){ S.ro = true; banner(); toast('Your access lets you view this review, not change it.', 3200); }
    Store.all().forEach(st => { const v = per[st.name]; if (!v) return;
      const ids = new Set(), cur = {};
      Object.keys(v.seen).forEach(k => { cur[k] = hydrate(v.seen[k], st, ids); });
      v.last = {}; Object.keys(v.seen).forEach(k => { v.last[k] = JSON.stringify(v.seen[k]); });
      if (st.kind === 'doc') st.set(cur[ONE] || st.empty()); else { if (st.fill) st.fill(cur); st.set(cur); }
      cacheOf(st); resolve(ids); });
    Object.keys(Q).forEach(p => { Q[p].want = undefined; });
    later();
  }
  function stop(){ if (!S.on) return; S.on = false; S.stopped = true; banner(); }

  /* One item taken from the shared database into the page. */
  function take(st, k, path, body, ids){
    const v = per[st.name], obj = st.get() || {};
    base[path] = body ? (body.rev || null) : null;
    if (!body){ delete v.seen[k]; delete v.last[k];
      if (st.kind === 'doc') st.set(st.empty()); else { delete obj[k]; if (st.fill) st.fill(obj, k); }
      return true; }
    const s = JSON.stringify(body.v); v.seen[k] = body.v;
    if (body.uid) ids.add(body.uid);
    if (v.last[k] === s) return false;
    v.last[k] = s;
    if (st.kind === 'doc') st.set(hydrate(body.v, st, ids)); else obj[k] = hydrate(body.v, st, ids);
    return true;
  }
  function first(st, bodies){
    const v = per[st.name], had = (() => { try { return !!localStorage.getItem(MARK); } catch(e){ return false; } })();
    const ids = new Set(), local = items(st), obj = st.get() || {};
    Object.keys(bodies).forEach(k => { const b = bodies[k];
      base[pathOf(st, k)] = b.rev || null; v.seen[k] = b.v; v.last[k] = JSON.stringify(b.v);
      if (b.uid) ids.add(b.uid);
      if (st.kind === 'doc') st.set(hydrate(b.v, st, ids)); else obj[k] = hydrate(b.v, st, ids); });
    /* The first time this browser joins the review, work it holds that the
       review does not is added to it. After that the shared review is the record,
       and an item it no longer holds was cleared by someone. */
    if (had) Object.keys(local).forEach(k => { if (bodies[k] !== undefined) return;
      if (st.kind === 'doc') st.set(st.empty()); else { delete obj[k]; if (st.fill) st.fill(obj, k); } });
    v.ready = true; cacheOf(st); resolve(ids);
  }
  function subscribe(st){
    per[st.name] = {last: {}, seen: {}, ready: false};
    const err = e => { if (e && (e.code === 'revoked' || e.code === 'not_granted')) stop(); };
    if (st.kind === 'doc'){
      const path = st.path(RID);
      S.db.doc(path).onSnapshot(snap => {
        if (busy(path)){ Q[path].skipped = true; return; }
        const body = snap.exists ? snap.data() : null;
        if (!per[st.name].ready){ if (snap.metadata && snap.metadata.fromCache) return;
          first(st, body ? {[ONE]: body} : {}); ready(); return; }
        const ids = new Set();
        if (take(st, ONE, path, body, ids)){ cacheOf(st); resolve(ids); later(); }
      }, err);
      return;
    }
    S.db.collection(runRoot(RID) + '/' + st.name).onSnapshot(snap => {
      if (!per[st.name].ready){ if (snap.metadata && snap.metadata.fromCache) return;
        const bodies = {}; snap.docs.forEach(d => { const b = d.data(); if (b && b.k !== undefined) bodies[b.k] = b; });
        first(st, bodies); ready(); return; }
      const ids = new Set(); let changed = false;
      snap.docChanges().forEach(ch => { const b = ch.doc.data(); if (!b || b.k === undefined) return;
        const path = pathOf(st, b.k); if (busy(path)){ Q[path].skipped = true; return; }
        if (take(st, b.k, path, ch.type === 'removed' ? null : b, ids)) changed = true; });
      if (changed){ cacheOf(st); resolve(ids); later(); }
    }, err);
  }
  function ready(){
    if (!Store.all().every(st => per[st.name] && per[st.name].ready)) return;
    try { localStorage.setItem(MARK, '1'); } catch(e){}
    diffAll(); later();
  }

  /* A change made on this page: written once the typing pauses, item by item,
     only where something changed. */
  let dt = null;
  function changed(){ clearTimeout(dt); dt = setTimeout(diffAll, 450); }
  function diffAll(){
    dt = null;
    if (!S.on) return;
    if (S.ro){ readOnly(); return; }
    Store.all().forEach(st => { const v = per[st.name]; if (!v || !v.ready) return;
      if (st.admin && !S.canEdit) return;
      const now = items(st);
      Object.keys(now).forEach(k => { if (now[k] !== v.last[k]){ v.last[k] = now[k]; put(st, k, JSON.parse(now[k])); } });
      Object.keys(v.last).forEach(k => { if (now[k] === undefined){ delete v.last[k]; put(st, k, null); } });
    });
    settle();
  }
  let idle = [];
  function settle(){
    if (dt || Object.keys(Q).some(busy)) return;
    const w = idle; idle = []; w.forEach(r => r());
  }
  function flush(){
    if (!S.on) return Promise.resolve();
    if (dt){ clearTimeout(dt); diffAll(); }
    return new Promise(r => { idle.push(r); settle(); });
  }

  /* Another reviewer's change redraws the console where it stands: scroll, open
     rows and panels are kept, and a field being typed in is never redrawn under
     the cursor. Its page catches up when the field is left. */
  let rt = null, behind = false;
  function later(){ clearTimeout(rt); rt = setTimeout(redraw, 120); }
  function typing(){ const a = document.activeElement;
    return !!a && (a.tagName === 'TEXTAREA' || (a.tagName === 'INPUT' && a.type === 'text' &&
      ['q', 'vtq', 'fxq', 'fixinput'].indexOf(a.id) < 0)); }
  function redraw(){
    const keep = $$('.view').map(v => [v, v.scrollTop]), y = window.scrollY;
    if (typing()){ behind = true; renderOffscreen(); }
    else { behind = false; renderAll(); }
    keep.forEach(x => { x[0].scrollTop = x[1]; }); window.scrollTo(0, y);
    showCarry();
  }
  document.addEventListener('focusout', () => { if (behind) setTimeout(() => { if (behind) redraw(); }, 0); });
  /* A viewer cannot type into a field their access does not let them save. */
  document.addEventListener('beforeinput', e => {
    if (!S.on || !S.ro) return; const t = e.target;
    if (t && (t.tagName === 'TEXTAREA' || t.tagName === 'INPUT') && ['q', 'vtq', 'fxq', 'fixinput'].indexOf(t.id) < 0) e.preventDefault();
  }, true);

  function banner(){
    const b = $('#sharedbar'); if (!b) return;
    document.body.classList.toggle('shared', S.on); document.body.classList.toggle('ro', S.on && S.ro);
    if (S.stopped){ b.hidden = false; b.textContent = 'Shared mode stopped: changes from here on are kept in this browser only.'; return; }
    b.hidden = !S.on;
    b.textContent = 'Shared mode: decisions are visible to everyone with access to this page.' +
      (S.ro ? ' Your access lets you view this review, not change it.' : '');
  }

  /* The runs of this close. A rerun in the same close is a new run with fresh
     state; the earlier run's decisions can be brought in, matched as a decision
     record is. */
  async function register(){
    try {
      const ref = S.db.doc('review/' + PER), snap = await ref.get();
      S.runs = (snap.exists && (snap.data() || {}).runs) || {};
      if (!S.runs[RID] && !S.ro){
        const entry = {at: new Date().toISOString(), console: window.__SERIF_CONSOLE__ || ''};
        if (snap.exists) await ref.update({runs: {[RID]: entry}}); else await ref.set({runs: {[RID]: entry}});
        S.runs[RID] = entry;
      }
    } catch(e){}
    showCarry();
  }
  function earlier(){
    return Object.keys(S.runs).filter(r => r !== RID)
      .sort((a, b) => String(S.runs[b].at).localeCompare(String(S.runs[a].at)))[0] || null;
  }
  function showCarry(){
    const b = $('#carryrun'); if (!b) return;
    b.hidden = !(S.on && !S.ro && earlier());
  }
  async function earlierRecord(){
    const rid = earlier(); if (!rid) return null;
    const rec = {kind: 'serif-decision-record', format: 2, run_id: rid, period: M.period,
      saved_at: S.runs[rid].at || '', findings: {}, drafts: {}};
    const field = {decisions: 'decisions', rows: 'rows', notes: 'notes', accepted: 'accepted',
      pending: 'pending_notes', raised: 'raised', edits: 'entry_edits'};
    for (const st of Store.all()){
      const ids = new Set();
      if (st.kind === 'doc'){
        if (st.name !== 'upload') continue;
        const s = await S.db.doc(st.path(rid)).get();
        if (s.exists){ const v = hydrate((s.data() || {}).v || {}, st, ids); rec.upload = v.upload || null; rec.netsuite_export = v.export || null; }
        continue;
      }
      const q = await S.db.collection(runRoot(rid) + '/' + st.name).get(), out = {};
      q.docs.forEach(d => { const b = d.data(); if (!b || b.k === undefined) return;
        out[b.k] = hydrate(b.v, st, ids); if (b.ref) rec.findings[b.k] = b.ref; });
      rec[field[st.name]] = out;
    }
    return rec;
  }

  /* Exports. A published page cannot start a download itself; it offers the
     file through the downloads capability and the viewer confirms the save.
     Opened as a file, the browser saves it as before (null here). */
  const DL = (window.claude && typeof window.claude.use === 'function') ? window.claude.use('downloads').catch(() => null) : Promise.resolve(null);
  async function save(filename, data){
    const dl = await DL; if (!dl) return null;
    try { await dl.save({filename: filename, data: data}); return true; }
    catch(e){
      const code = (e && e.code) || '';
      toast(code === 'declined' ? 'Not saved' : code === 'rate_limited' ? 'A save is already waiting for an answer'
        : 'Files cannot be saved from this page here', 2600);
      return false;
    }
  }

  async function start(){
    banner();
    if (!window.claude || typeof window.claude.use !== 'function') return;
    let db = null, user = null;
    try { [db, user] = await Promise.all([window.claude.use('db'), window.claude.use('user')]); } catch(e){ return; }
    if (!db) return;
    S.db = db; S.user = user;
    if (user){
      try { const me = await user.me(); S.uid = me.id || null; S.me = me.name || 'You';
        S.canEdit = !!(await user.canEdit());
        S.canWrite = await user.can('data.write');
        if (S.canWrite === false) S.ro = true; } catch(e){}
    }
    S.on = true; Store.attach({changed: changed});
    banner();
    Store.all().forEach(subscribe);
    register();
  }

  return {
    start: start, flush: flush, save: save, earlierRecord: earlierRecord, showCarry: showCarry,
    on: () => S.on, ro: () => S.on && S.ro, me: () => S.me, canEdit: () => S.on && S.canEdit && !S.ro,
    signPath: rid => 'signoff/' + PER + '-' + rid,
    uploadPath: rid => runRoot(rid) + '/meta/upload',
    _state: S,
  };
})();

/* Over the threshold takes the accent because it is the thing to act on; under it
   stays neutral because it is context. */
/* Both values are rendered as TEXT as well as as a dot, so both must clear the
   4.5:1 text threshold. Warm Gray reaches only 2.37:1 on a white card; Mid Gray
   is the secondary ink at 8.09:1 and is the right semantic for "not the live
   thing" anyway. */
const SEV_COLOR = {above:'var(--color-accent-text)', below:'var(--color-fg-secondary)'};
/* Every finding resolves to the same question: does this become an entry or not?

   An earlier version asked the reviewer to classify a variance as timing,
   structural or coding before deciding anything. That is a taxonomy exercise, and
   the accountant's actual decision is binary. Classification also forced a choice
   before the evidence was in: "is it timing" is often unanswerable at the moment
   the line is reviewed, while "am I booking this" always has an answer.

   So there are two verdicts and one optional note. A reason is required only when
   declining, because a decision to leave the ledger alone is the one that has to
   survive review later. */
/* One set of outcomes for every finding, the same words as a schedule row's.
   Entry booked is offered only where the finding has a proposed entry to book. */
/* The names live in LABELS in build_report.py, read here from the page; the
   stored values (book, no_entry, question, manual) never change with a name. */
const L = window.__SERIF_LABELS__ || {pages:{}, outcomes:{}, groups:{}};
const LO = L.outcomes, LP = L.pages, LG = L.groups;
const VERDICTS = {book:LO.entry, no_entry:LO.clear, question:LO.question, manual:LO.manual};
const DECISION_ACTIONS = [
  ['book',LO.entry,'B',false, 'Book the proposed entry. It goes into the NetSuite import.'],
  /* Cleared settles on the click; a reason is optional. */
  ['no_entry',LO.clear,'C',false, 'The ledger is correct.'],
  ['question',LO.question,'Q',true, 'Someone must answer first. Say who and what you asked.'],
  ['manual',LO.manual,'M',true, 'You corrected it in NetSuite. Say what you changed.'],
];
/* Who is reviewing, set in the bar and recorded with each decision, so the
   audit trail says who decided what and when. A setting of this browser, not of
   the run. Empty means the decision records no name. */
const WHO_KEY = 'serif-reviewer';
let reviewerName = (function(){ try { return Store.getItem(WHO_KEY) || ''; } catch(e){ return ''; } })();
/* In shared mode the reviewer is the person signed in, named as they see
   themselves; the shared record keeps their user id, not the name. */
const byWho = () => Shared.on() ? Shared.me() : String(reviewerName || '').trim();
const hasEntry = id => (V.entries||[]).some(e => e.finding_id === id || (e.finding_ids||[]).indexOf(id) > -1);
const ACTIONS = f => f ? DECISION_ACTIONS.filter(o => o[0] !== 'book' || hasEntry(f.finding_id)) : DECISION_ACTIONS;
const isVariance = f => f.rule_id.indexOf('VARIANCE') > -1 || f.rule_id.indexOf('BUDGET') > -1;
const noteRequired = (f,v) => (DECISION_ACTIONS.find(o=>o[0]===v)||[])[3] === true;
const noteLabel = f => isVariance(f)
  ? 'Commentary for the flux pack'
  : 'Why, for the close file';

/* ---------- the fix threshold ----------
   Severity tiers were the wrong instrument. A controller's question is binary:
   is this over the number at which we fix things? So the threshold is a CONTROL,
   not a constant baked into each rule, the reviewer sets it and the queue
   re-partitions live. Everything under it is still counted and still shown in
   aggregate, because thresholds are set against the aggregate, and a population
   of small errors concentrated in one department is a different problem from the
   same value scattered. */
const FIX_AT = (D.report && D.report.fix_threshold) || 2500;
const FIX_PRESETS = (D.report && D.report.fix_threshold_presets) || [0, 2500, 10000, 25000];
/* Below this the engine emitted nothing, so the rollup would understate. */
const ENGINE_FLOOR = (D.report && D.report.reporting_floor) || 0;
const BAND_LABEL = (D.report && D.report.band_labels) ||
  ['Needs fixing', 'Below the fix threshold'];
let fixAt = FIX_AT;
let band='above', kind='all', q='', queue='open', selected=null, groupFilter=null;
let layerFilter=null;

const amtOf = f => Math.abs(f.amount_at_risk || 0);
const isAbove = f => amtOf(f) >= fixAt;
const bandOf = f => isAbove(f) ? 'above' : 'below';
/* Department is only knowable where the finding carries its lines. Anything else
   is reported as unattributed rather than guessed at. */
function deptOf(f){
  const ds = new Set((f.transactions||[]).map(t=>(t.department||'').trim()).filter(Boolean));
  if (ds.size === 1) return Array.from(ds)[0];
  if (ds.size > 1) return 'Multiple departments';
  const m = /\s\/\s([^:]+):/.exec(f.title||'');
  return m ? m[1].trim() : 'Not attributed';
}

const money = n => (n==null||n==='') ? '-'
  : '$'+Number(n).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const money0 = n => (n==null) ? '-' : '$'+Math.round(Number(n)).toLocaleString('en-US');
const pct = v => (v==null) ? '-' : (v*100).toFixed(1)+'%';
/* needs_judgement is the artifact's field spelling and is part of the engine
   contract, so it is never renamed. Only the displayed label is localized. */
const KIND_LABEL = k => String(k).replace(/_/g,' ').replace('judgement','judgment');
const esc = s => String(s==null?'':s).replace(/[&<>"']/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

/* ---------- accounts by name ----------
   A bare code tells a reader nothing unless they have memorized the chart. Every
   account the console shows carries its name, and every code quoted in an
   engine's text gets its name beside it where the text does not already say it.
   The names come from the ledger's own account paths, carried in the run. */
const V = D.views || {};
const ACCTS = Object.assign({}, V.accounts || {});
(D.tables||[]).forEach(t=>(t.sections||[]).forEach(s=>(s.rows||[]).forEach(r=>{
  if(r.account_code && !ACCTS[r.account_code]) ACCTS[r.account_code]={name:r.account_leaf||'',parent:''};
})));
D.findings.forEach(f=>(f.transactions||(f.transaction?[f.transaction]:[])).forEach(t=>{
  if(t.account_code && t.account_leaf && !ACCTS[t.account_code])
    ACCTS[t.account_code]={name:t.account_leaf,parent:''};
}));
const acctName = code => (ACCTS[code]||{}).name || '';
const acctText = code => code ? (acctName(code) ? code+' '+acctName(code) : code) : '';
function named(text){
  return String(text==null?'':text).replace(/\b(\d{7})\b/g, (m, code, off, str) => {
    const n = acctName(code);
    if (!n) return m;
    const rest = str.slice(off + m.length).replace(/^[\s:-]+/, '');
    return rest.indexOf(n) === 0 ? m : code + ' ' + n;
  });
}
const escn = s => esc(named(s));

/* ---------- links out ----------
   A document number the ledger holds opens its NetSuite record when the export
   carries its internal ID. NetSuite's search results page cannot be opened from a
   link (its criteria live in the session), so without the ID the number is text. A Coupa invoice
   link sits beside it when the export carries one, and a PO number opens the PO in
   Coupa. Every ID comes from an export; none is guessed. */
const LK = V.links || {};
const NS_HOST = LK.netsuite_account
  ? 'https://'+String(LK.netsuite_account).toLowerCase().replace(/_/g,'-')+'.app.netsuite.com' : '';
const XA = '<svg class="xa" viewBox="0 0 10 10" aria-hidden="true" fill="none" stroke="currentColor" '+
  'stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 1.5h5v5M8.5 1.5 1.5 8.5"/></svg>';
const xl = (href, html, title, cls) => '<a class="xl'+(cls?' '+cls:'')+'" href="'+esc(href)+
  '" target="_blank" rel="noopener" title="'+esc(title)+'" aria-label="'+esc(title)+'">'+html+XA+'</a>';
function docHTML(doc){
  doc = String(doc==null?'':doc).trim();
  if (!doc || !Object.prototype.hasOwnProperty.call(LK.docs||{}, doc)) return esc(doc);
  const known = LK.docs[doc];
  const ns = NS_HOST && known.ns
    ? NS_HOST+'/app/accounting/transactions/transaction.nl?id='+encodeURIComponent(known.ns) : '';
  const main = ns ? xl(ns, esc(doc), 'Open '+doc+' in NetSuite') : esc(doc);
  const more = (known.coupa ? xl(known.coupa, 'Invoice', 'Open invoice '+doc+' in Coupa', 'xc') : '')+
    (known.po && poURL(known.po) ? xl(poURL(known.po), 'PO', 'Open PO '+known.po+' in Coupa', 'xc') : '');
  return more ? '<span class="xls">'+main+more+'</span>' : main;
}
const poURL = po => (LK.po_ids||{})[po] && LK.coupa_host
  ? 'https://'+LK.coupa_host+'/order_headers/'+encodeURIComponent(LK.po_ids[po]) : '';
const poHTML = po => poURL(po) ? xl(poURL(po), esc(po), 'Open the PO in Coupa') : esc(po);
/* A short list of documents, one per line; a longer one is its count. */
const docsHTML = docs => !(docs||[]).length ? '' : docs.length > 3
  ? '<span class="sub2">'+docs.length+' documents</span>'
  : '<span class="xdocs">'+docs.map(d => '<span>'+docHTML(d)+'</span>').join('')+'</span>';
/* Engine text that quotes a PO number links it. The pattern holds no character
   esc() rewrites, so it is found in the escaped text. */
const poify = html => html.replace(/\bFL\d{9}\b/g, po => poHTML(po));
const escl = s => poify(escn(s));
function acctHTML(code, parent){
  if(!code) return '<span class="secondary">-</span>';
  const a = ACCTS[code] || {};
  return '<span class="ac"><span class="mono">'+esc(code)+'</span> '+esc(a.name||'')+'</span>'+
    (parent && a.parent ? '<span class="sub2">'+esc(a.parent)+'</span>' : '');
}

/* ---------- decisions: persisted per run, degrading to memory ---------- */
/* Bump STORE_VERSION whenever the decision vocabulary changes: decisions taken
   under the old verbs would otherwise be restored against actions that no longer
   exist. */
/* 1.8.7 keeps v2. It adds fields (who decided, a line's own outcome, the rest of
   a row, an edited memo, the upload) and renames nothing, and the one meaning
   that moved, a reclass clearing the rest of its row, is written down for each
   row stored that way when it loads (upgradeRow). Bumping would have dropped
   every decision a reviewer had in progress. */
const STORE_VERSION = 'v2';
const KEY = 'serif-review::' + STORE_VERSION + '::' + (M.run_id || 'unknown');
let storageOK = true;
function load(){
  try { return JSON.parse(Store.getItem(KEY) || '{}'); }
  catch(e){ storageOK = false; return {}; }
}
let decisions = load();
function persist(){
  try { Store.setItem(KEY, JSON.stringify(decisions)); }
  catch(e){
    if (storageOK){
      storageOK = false;
      $('#storewarn').hidden = false;
    }
  }
}
/* A decision whose action requires a written reason is not complete until the
   reason exists, so it stays in the outstanding queue rather than quietly
   counting as done. */
function decided(id){
  const d = decisions[id];
  if (!d || !d.verdict) return false;
  const f = D.findings.find(x => x.finding_id === id);
  if (f && noteRequired(f, d.verdict) && !(d.note||'').trim()) return false;
  return true;
}
const openCount = () => D.findings.filter(f => !decided(f.finding_id)).length;
const openAbove = () => D.findings.filter(f => isAbove(f) && !decided(f.finding_id)).length;

function decide(id, verdict){
  /* One decision covers the whole cluster, that is the point of grouping. */
  const anchor = D.findings.find(f => f.finding_id === id);
  const members = anchor ? D.findings.filter(f => clusterKey(f) === clusterKey(anchor)) : [];
  const clearing = (decisions[id] || {}).verdict === verdict;
  members.forEach(f => {
    const cur = decisions[f.finding_id] || {};
    if (clearing) delete decisions[f.finding_id];
    else decisions[f.finding_id] = {verdict, note: cur.note || '',
                                    at: new Date().toISOString(), by: byWho()};
  });
  persist(); renderAll();
  const n = members.length;
  toast(clearing ? 'Decision cleared'
    : VERDICTS[verdict] + (n > 1 ? ' · ' + n + ' findings' : ''));
  if (focusOn) focusNext();
}
function setClusterNote(id, text){
  const anchor = D.findings.find(f => f.finding_id === id);
  if (!anchor) return;
  D.findings.filter(f => clusterKey(f) === clusterKey(anchor)).forEach(f => {
    decisions[f.finding_id] = decisions[f.finding_id] || {verdict:null, at:new Date().toISOString()};
    decisions[f.finding_id].note = text; decisions[f.finding_id].by = byWho();
  });
  persist(); renderDecisions();
}
function setNote(id, text){
  decisions[id] = decisions[id] || {verdict:null, at:new Date().toISOString()};
  decisions[id].note = text; decisions[id].by = byWho(); delete decisions[id].src; persist(); renderRail(); renderDecisions();
}

/* Resolves true only when the confirming button is chosen. Falls back to the
   native confirm where <dialog> is unavailable, so the guard never disappears. */
/* With `word`, the reviewer has to type it before the action is allowed, for the
   actions that cannot be undone. */
function ask(title, body, okLabel, word){
  const dlg = $('#ask');
  if (!dlg || typeof dlg.showModal !== 'function'){
    if (word) return Promise.resolve((window.prompt(title + '\n\n' + body + '\n\nType ' + word + ' to confirm.') || '').trim().toLowerCase() === word);
    return Promise.resolve(window.confirm(title + '\n\n' + body));
  }
  $('#ask-title').textContent = title;
  $('#ask-body').textContent = body;
  $('#ask-ok').textContent = okLabel || 'Confirm';
  const wrap = $('#ask-typewrap'), typed = $('#ask-type'), ok = $('#ask-ok');
  wrap.hidden = !word; typed.value = ''; ok.disabled = !!word;
  if (word){
    $('#ask-typelab').innerHTML = 'Type <code>' + esc(word) + '</code> to confirm';
    typed.oninput = () => { ok.disabled = typed.value.trim().toLowerCase() !== word; };
    typed.onkeydown = ev => { if (ev.key === 'Enter'){ ev.preventDefault(); if (!ok.disabled) dlg.close('ok'); } };
  }
  dlg.returnValue = 'cancel';
  dlg.showModal();
  if (word) typed.focus();
  return new Promise(resolve => {
    dlg.addEventListener('close', function once(){
      dlg.removeEventListener('close', once);
      resolve(dlg.returnValue === 'ok');
    });
  });
}

let toastT;
function toast(msg, ms){
  const el = $('#toast'); el.textContent = msg; el.classList.add('on');
  clearTimeout(toastT); toastT = setTimeout(()=>el.classList.remove('on'), ms || 1400);
}

/* ---------- grouping ---------- */
const GROUPS = (D.report && D.report.groups && D.report.groups.length) ? D.report.groups : [
  {id:'tieout',label:'Blocks the close',rules:['T0.TIE_OUT'],
   why:'The ledger does not balance. Nothing else is trustworthy until it does.'},
  {id:'recode',label:'Proposed recodes',
   rules:['T1.DEPT_INCONSISTENCY','T4.PO_ACCOUNT_MISMATCH','T2.UNALLOCATED'],
   why:'Coding differs from the established pattern, or from the account a purchase order was approved against.'},
  {id:'integrity',label:'Ledger integrity',rules:['T0.DUPLICATE_LINE','T0.ABERRANT_POSTING_LAG'],
   why:'Possible duplicates and transactions posted well outside their period.'},
  {id:'tax',label:'Tax treatment',
   rules:['T3.IRC_274A_ENTERTAINMENT','T3.IRC_274N_MEALS','T3.IRC_274B_GIFTS','T3.IRC_174_BASE'],
   why:'Deductibility flags for the add-back schedule. Tax counsel signs these off.'},
];
const groupOf = f => (GROUPS.find(g=>g.rules.includes(f.rule_id))||{id:'review'}).id;

/* ---------- the two layers ----------
   Accounting settles the ledger, then FP&A reads it against plan. Review runs in
   that order because a budget variance computed on miscoded actuals measures the
   miscoding. A finding carries its own layer; the group's layer is the fallback,
   and anything unlabeled sits in accounting so it is never hidden behind work
   the reviewer has not reached yet. */
const LAYERS = (D.report && D.report.layers && D.report.layers.length)
  ? D.report.layers.slice().sort((a,b)=>(a.order||0)-(b.order||0)) : [];
const layerOf = f => f.layer
  || (GROUPS.find(g=>g.rules.includes(f.rule_id))||{}).layer
  || (LAYERS.length ? LAYERS[0].id : 'accounting');
const layerLabel = id => (LAYERS.find(l=>l.id===id)||{label:''}).label
  || (id==='fpa' ? 'FP&A review' : 'Accounting review');
const layerRank = id => {
  const i = LAYERS.findIndex(l=>l.id===id);
  return i < 0 ? 99 : i;
};
/* Layers present in this run, in order. A run with no layered findings yields an
   empty list and every layer-aware surface falls back to a single flat list. */
const activeLayers = () => {
  const seen = [];
  D.findings.forEach(f => { const l = layerOf(f); if (seen.indexOf(l) < 0) seen.push(l); });
  return seen.sort((a,b)=>layerRank(a)-layerRank(b));
};

/* Findings repeat heavily per subject: one vendor can raise the same rule a dozen
   times, and the reviewer makes a single call about that vendor. Grouping on
   (rule, subject) means one decision covers the whole set, which is what collapses
   a long finding list into a short decision list. */
function subjectOf(f){
  const t = f.title;
  for (const sep of [': ', ' coded to', ', dated ', ' vs ']){
    const i = t.indexOf(sep);
    if (i > 0) return t.slice(0, i);
  }
  return t;
}
const clusterKey = f => f.rule_id + '||' + subjectOf(f);
function clusters(list){
  const map = new Map();
  list.forEach(f => {
    const k = clusterKey(f);
    if (!map.has(k)) map.set(k, {key:k, subject:subjectOf(f), rule:f.rule_id,
                                group:groupOf(f), layer:layerOf(f), items:[], amt:0});
    map.get(k).items.push(f);
  });
  /* A decision covers every finding sharing the key, including any the current
     filter is hiding, so the amount shown has to be the whole cluster's. Summing
     only the visible members would understate what the reviewer is deciding on,
     and would make the same subject show different totals under different
     filters. `items` is what the filter admits; `all` is what the decision
     reaches. */
  map.forEach(c => {
    c.all = D.findings.filter(f => clusterKey(f) === c.key);
    c.amt = c.all.reduce((s, f) => s + amtOf(f), 0);
    c.hidden = c.all.length - c.items.length;
  });
  return Array.from(map.values());
}
const groupLabel = id => (GROUPS.find(g=>g.id===id)||{label:'Other review items'}).label;
const groupWhy = id => (GROUPS.find(g=>g.id===id)||{}).why || '';

/* ---------- the correction ----------
   The reviewer's question is "what is wrong and what does it become". That was
   previously only answerable by reading the recommendation paragraph and the
   evidence pairs. It is now a block of its own, directly under the title, because
   it is the thing being decided.

   Engines that compute a correction supply `correction` outright. The coding
   engine does not yet, but it already puts the same pair in `evidence.observed`
   and `evidence.expected`, which are parallel by construction, so those are read
   as a fallback rather than leaving the block empty on the console where
   corrections matter most.

   Nothing is inferred beyond that. A rule with no structured correction and no
   observed/expected pair renders no block at all, which is correct: a variance
   has no proposed correction until a person decides there is one. */
const DIMENSION_BY_RULE = {
  'T1.DEPT_INCONSISTENCY':'Department', 'T2.UNALLOCATED':'Department',
  'T4.PO_ACCOUNT_MISMATCH':'Account', 'T0.DUPLICATE_LINE':'Duplicate',
  'T0.ABERRANT_POSTING_LAG':'Posting date',
};
function correctionOf(f){
  const c = f.correction;
  if (c && (c.current || c.proposed)) return c;
  const ev = f.evidence || {};
  const dim = DIMENSION_BY_RULE[f.rule_id];
  if (!dim || !ev.observed || !ev.expected) return null;
  return {dimension:dim, subject:'', current_label:'Now', current:ev.observed,
          proposed_label:'Should be', proposed:ev.expected, entry:'', pl_impact:null};
}
function correctionHTML(f){
  const c = correctionOf(f);
  if (!c) return '';
  /* The subject is the card title, directly above. The amount is already in the
     evidence list. Neither is repeated here. */
  if (c.entry) return '<div class="fix"><div class="fx-h">Proposed Journal Entry</div>'+entryHTML(f, c.entry)+'</div>';
  return '<div class="fix">'+
    (c.dimension?'<div class="fx-h">'+esc(c.dimension)+'</div>':'')+
    '<div class="fx-p">'+
      '<div class="fx-c"><span>'+esc(c.current_label||'Now')+'</span><b>'+escn(c.current||'')+'</b></div>'+
      '<div class="fx-a" aria-hidden="true">&rarr;</div>'+
      '<div class="fx-c fx-t"><span>'+esc(c.proposed_label||'Should be')+'</span><b>'+
        escn(c.proposed||'')+'</b></div>'+
    '</div>'+
    (c.entry?entryHTML(f, c.entry):'')+'</div>';
}

/* The proposed entry as it would be booked, one line per side, rather than the
   engine's one-line "Dr ... / Cr ..." string. */
function entryHTML(f, text){
  const je = (V.entries||[]).find(x => x.finding_id === f.finding_id);
  let lines = je ? je.lines : [];
  if (!lines.length){
    const amt = /for\s+\$([\d,.]+)/.exec(text), a = amt ? Number(amt[1].replace(/,/g,'')) : 0;
    const re = /(Dr|Cr)\s+(\d{7})\s+(.*?)(?=\s*\/\s*(?:Dr|Cr)\s+\d{7}|\s+for\s+\$|$)/g;
    let m;
    while ((m = re.exec(text))){
      const rest = m[3].split(' / ');
      lines.push({account:m[2], department: rest.length > 1 ? rest[rest.length-1] : '',
                  debit: m[1]==='Dr' ? a : 0, credit: m[1]==='Cr' ? a : 0});
    }
  }
  if (!lines.length) return '<div class="fx-e">'+escn(text)+'</div>';
  return '<div class="fx-e jtab"><table><tbody>'+lines.map(l =>
    '<tr><td class="side">'+(l.debit ? 'Debit' : 'Credit')+'</td><td>'+esc(acctText(l.account))+'</td>'+
    '<td class="secondary">'+esc(l.department||'')+'</td><td class="num">'+money(l.debit||l.credit)+'</td></tr>').join('')+
    '</tbody></table></div>';
}

/* When the correction was DERIVED from observed and expected, those two rows
   would otherwise print the same strings again a few lines below it. The
   correction block is the better presentation of that pair, so the evidence list
   drops them and keeps only what the block does not already say. */
const correctionIsDerived = f => !(f.correction && (f.correction.current || f.correction.proposed))
                                 && !!correctionOf(f);

function visible(){
  const needle = q.trim().toLowerCase();
  return D.findings
    .filter(f => (band==='all'||bandOf(f)===band)
              && (kind==='all'||f.kind===kind)
              && (queue==='all' || (queue==='open' ? !decided(f.finding_id) : decided(f.finding_id)))
              && (!groupFilter || groupOf(f)===groupFilter)
              && (!layerFilter || layerOf(f)===layerFilter)
              && (!needle || JSON.stringify(f).toLowerCase().includes(needle)))
    .sort((a,b)=>amtOf(b)-amtOf(a));
}

/* The population under the threshold, summarized rather than listed. A threshold
   is set against the aggregate, so the aggregate has to be visible before anyone
   can judge whether the threshold is right. */
function belowRollup(){
  const items = D.findings.filter(f => !isAbove(f));
  const byDept = new Map();
  items.forEach(f => {
    const d = deptOf(f);
    if (!byDept.has(d)) byDept.set(d, {dept:d, n:0, amt:0});
    const r = byDept.get(d); r.n++; r.amt += amtOf(f);
  });
  return {
    n: items.length,
    amt: items.reduce((s,f)=>s+amtOf(f), 0),
    depts: Array.from(byDept.values()).sort((a,b)=>b.amt-a.amt),
  };
}

/* A row selected near the top or bottom edge of the list sits half-clipped, so
   it is brought to the middle. Rows already in the comfortable middle band are
   left alone: scrolling on every click would make the list feel restless. */
function centerSelected(){
  const el = $('.cluster[aria-selected="true"]'), box = $('#list');
  if (!el || !box) return;
  const r = el.getBoundingClientRect(), b = box.getBoundingClientRect();
  const mid = r.top + r.height / 2, band = b.height * 0.25;
  if (mid > b.top + band && mid < b.bottom - band) return;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  el.scrollIntoView({block: 'center', behavior: reduce ? 'auto' : 'smooth'});
}

/* ---------- tooltip ---------- */
const tip = $('#tip');
function showTip(e,html){
  tip.innerHTML=html; tip.classList.add('on');
  const r=tip.getBoundingClientRect();
  let x=e.clientX+14,y=e.clientY+14;
  if(x+r.width>innerWidth-8) x=e.clientX-r.width-14;
  if(y+r.height>innerHeight-8) y=e.clientY-r.height-14;
  tip.style.left=x+'px'; tip.style.top=y+'px';
}
document.addEventListener('mouseover',e=>{
  const t=e.target.closest('[data-tip]');
  if(t) showTip(e,t.dataset.tip); else tip.classList.remove('on');
});
document.addEventListener('mousemove',e=>{
  const t=e.target.closest('[data-tip]'); if(t) showTip(e,t.dataset.tip);
});

/* ---------- rail ---------- */
function renderRail(){
  const open = openCount(), total = D.findings.length, done = total-open;
  /* progress lives on Overview and Decisions, never in the chrome */
}

/* ---------- overview ----------
   One population behind every figure on the page: each thing a review page
   asks the reviewer to settle, with its amount and whether it is settled. The
   tiles, the threshold bars, the map and the fold below all read it, so they
   cannot disagree with each other or with the checklist. Journal Entries are
   left out because each restates a finding on another page; a flux account
   counts once however many comparisons flag it. */
/* What is left over the threshold, counted once: the number the tick-and-tie,
   the bar and the Decisions page all show. */
const openWork = () => workItems().filter(i => i.amt >= fixAt && !i.done).length;
function workItems(){
  const out = [];
  $$('.nav button[data-view]').forEach(b => {
    if (b.dataset.view !== 'vtable') return;
    const t = VTABLES.find(x => x.id === b.dataset.vt); if (!t) return;
    const label = b.dataset.label;
    const gs = t.groups || (t.group ? [t.group] : null);
    if (gs){
      D.findings.filter(f => gs.indexOf(groupOf(f)) > -1)
        .forEach(f => out.push({page:label, amt:amtOf(f), done:decided(f.finding_id)}));
      return;
    }
    const spec = VT[t.kind](t);
    if (!spec.size) return;
    t.sections.forEach(s => s.rows.forEach(r => {
      if (b.dataset.vf && !inVf(r, b.dataset.vf)) return;
      const a = spec.size(r);
      if (a > 0) out.push({page:label, amt:a, done: spec.done ? spec.done(r) : false});
    }));
  });
  chExtra().forEach(x => x.cnt.forEach(id => { const f = D.findings.find(y => y.finding_id === id); if (!f) return;
    out.push({page:x.page, amt:amtOf(f), done:decided(id)}); }));
  if (TABLE){
    const cs = TABLE.comparisons.filter(c => c.id !== 'yoy');
    TABLE.sections.forEach(s => s.rows.forEach(r => {
      const a = Math.max.apply(null, cs.map(c => Math.abs(r[c.var] || 0)));
      if (a > 0 && a >= ENGINE_FLOOR)
        out.push({page:'Flux pack', amt:a, done:explained(r.account_code)});
    }));
  }
  return out;
}
function renderSummary(){
  const host = $('#summarycard'); if (!host) return;
  host.hidden = !DR.summary;
  if (!DR.summary) return;
  /* Paragraphs split on blank lines; lines that start with "- " are a list. */
  const blocks = DR.summary.split(/\n\s*\n/).map(b => {
    const ls = b.split('\n').filter(l => l.trim());
    return ls.every(l => /^\s*- /.test(l))
      ? '<ul>'+ls.map(l => '<li>'+escn(l.replace(/^\s*- /,''))+'</li>').join('')+'</ul>'
      : '<p>'+escn(ls.join(' '))+'</p>';
  }).join('');
  host.innerHTML = '<div class="dh" style="display:flex;gap:var(--spacing-sm);align-items:baseline">'+
    '<h3 style="margin:0">Summary</h3><span class="secondary" style="font-size:var(--text--2)">Drafted by Claude</span></div>'+blocks;
}
/* The amount bands: the report's threshold presets cut the population into
   bands that add up to the whole, so no item is counted twice and none is
   missed. The first band runs from zero; the last is open-ended. */
function amountBands(){
  const edges = FIX_PRESETS.filter(t => t > 0).slice().sort((a, b) => a - b)
    .filter((t, i, xs) => xs.indexOf(t) === i);
  return [0].concat(edges).map((lo, i, xs) => ({lo: lo, hi: i + 1 < xs.length ? xs[i + 1] : null}));
}
const bandName = b => b.lo === 0 ? 'Under ' + money0(b.hi)
  : b.hi == null ? 'Over ' + money0(b.lo) : money0(b.lo) + ' to ' + money0(b.hi);
const shareOf = (v, of) => of ? (v / of * 100) : 0;
const pct1 = v => (Math.round(v * 10) / 10).toFixed(1) + '%';
/* The tick-and-tie: every item a review page raises is either over the
   threshold, and settled or still open, or under it and counted. The rows
   foot to the total, in items and in dollars, so the reviewer can see the
   review covers the whole population and nothing was skipped. */
function tieHTML(items){
  const tot = {n: items.length, v: items.reduce((s, i) => s + i.amt, 0)};
  const part = f => { const xs = items.filter(f); return {n: xs.length, v: xs.reduce((s, i) => s + i.amt, 0)}; };
  const over = part(i => i.amt >= fixAt), under = part(i => i.amt < fixAt);
  const settled = part(i => i.amt >= fixAt && i.done), left = part(i => i.amt >= fixAt && !i.done);
  const row = (label, p, cls, lead) => '<tr'+(cls?' class="'+cls+'"':'')+'><td>'+(lead?'<span class="tind"></span>':'')+label+'</td>'+
    '<td class="num">'+p.n+'</td><td class="num">'+pct1(shareOf(p.n, tot.n))+'</td>'+
    '<td class="num">'+money0(p.v)+'</td><td class="num">'+pct1(shareOf(p.v, tot.v))+'</td></tr>';
  const ties = over.n + under.n === tot.n && Math.abs(over.v + under.v - tot.v) < 0.005;
  return '<table class="tie"><thead><tr><th></th><th class="num">Items</th><th class="num">% of items</th>'+
      '<th class="num">Value</th><th class="num">% of value</th></tr></thead><tbody>'+
    row('Over ' + money0(fixAt), over, 'tsub') +
    row('Settled', settled, '', true) +
    row('Left to review', left, left.n ? 'tleft' : '', true) +
    row('Under ' + money0(fixAt) + ', counted', under, 'tsub') +
    row('Total', tot, 'ttot') + '</tbody></table>'+
    (ties ? '' : '<p class="note"><span class="reqd">Over and under do not foot to the total.</span></p>');
}
function bandsHTML(items){
  const all = items.reduce((s, i) => s + i.amt, 0);
  /* A band wholly under the engine's reporting floor is drawn only when an item
     sits in it: empty, it would read as a clean result for amounts the engine
     never reports; holding one, leaving it out would drop that item. */
  return '<div class="bars">'+amountBands().map(b => ({b: b,
    xs: items.filter(i => i.amt >= b.lo && (b.hi == null || i.amt < b.hi))}))
  .filter(x => x.xs.length || !(ENGINE_FLOOR && x.b.hi != null && x.b.hi <= ENGINE_FLOOR))
  .map(({b, xs}) => {
    const v = xs.reduce((s, i) => s + i.amt, 0), share = shareOf(v, all);
    const work = b.lo >= fixAt;
    return '<button class="bar'+(b.lo===fixAt?' on':'')+'" type="button" data-setfix="'+b.lo+'"'+
      ' data-tip="'+esc(bandName(b)+': '+xs.length+' item'+(xs.length===1?'':'s')+', '+money0(v)+' of '+money0(all)+
        '. Select to review from '+(b.lo ? money0(b.lo) : 'zero')+' up')+'">'+
      '<span class="lab">'+esc(bandName(b))+'</span>'+
      '<span class="val">'+xs.length+' item'+(xs.length===1?'':'s')+' · '+money0(v)+'</span>'+
      '<span class="shr">'+Math.round(share)+'%</span>'+
      '<span class="track"><i class="fill'+(work?' accent':'')+'" data-w="'+share.toFixed(1)+'"></i></span></button>';
  }).join('')+'</div>';
}
function renderOverviewViews(){
  renderSummary();
  const items = workItems();
  const open = items.filter(i => i.amt >= fixAt && !i.done);
  if ($('#tietbl')) $('#tietbl').innerHTML = tieHTML(items);
  $('#thchart').innerHTML = bandsHTML(items);
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    $('#thchart').querySelectorAll('.fill[data-w]').forEach(i=>{ i.style.width = i.dataset.w+'%'; });
  }));
  /* Where the open value sits, by page. Every cell carries its name and figures,
     all in one neutral fill, so the accent stays for what needs action. */
  const byPage = {};
  open.forEach(i => { const p = byPage[i.page] = byPage[i.page] || {v:0, n:0}; p.v += i.amt; p.n++; });
  const cells = Object.keys(byPage).map(k => ({id:k, v:byPage[k].v, n:byPage[k].n}));
  const tot = cells.reduce((s, c) => s + c.v, 0) || 1, W = 520, H = 240;
  const pc = (v, of) => (v/of*100).toFixed(3)+'%';
  $('#groupchart').innerHTML = cells.length ? '<div class="tmap" style="height:'+H+'px">'+
    squarify(cells, 0, 0, W, H).map(c => {
      const share = Math.max(1, Math.round(c.v/tot*100));
      const lab = c.id+' · '+money0(c.v)+' · '+share+'% · '+c.n+' item'+(c.n===1?'':'s');
      return '<button class="tcell" type="button" data-page="'+esc(c.id)+'" style="left:'+pc(c.x,W)+
        ';top:'+pc(c.y,H)+';width:'+pc(c.w,W)+';height:'+pc(c.h,H)+'" data-tip="'+esc(lab)+'">'+
        '<span class="tl">'+esc(c.id)+'</span><span class="tv">'+money0(c.v)+'</span><span class="tn">'+
        share+'% · '+c.n+' item'+(c.n===1?'':'s')+'</span></button>';
    }).join('')+'</div>'
    : '<p class="note">Nothing left over '+money0(fixAt)+'.</p>';
  requestAnimationFrame(fitTreemap);
}
/* Each cell shows as much as fits in it, measured once it is on screen: the
   name, value and share, then the name and value, then the name. A cell that
   cannot show all three is listed in full under the map, so every figure is
   readable. */
function fitTreemap(){
  const host = $('#groupchart'); if (!host || !host.offsetWidth) return;
  /* A cell too small for its figures drops them; its tooltip carries them all. */
  host.querySelectorAll('.tcell').forEach(c => {
    const over = () => c.scrollHeight > c.clientHeight + 1 || c.scrollWidth > c.clientWidth + 1;
    ['.tn', '.tv', '.tl'].forEach(sel => { const x = c.querySelector(sel); if (x && over()) x.remove(); });
  });
}
addEventListener('resize', () => { if (!$('#v-overview').hidden) renderOverview(); });
function renderOverview(){
  renderChecklist();
  if (VTABLES.length){ if ($('#thchart')) renderOverviewViews(); return; }
  if(!$('#kpis')) return;
  const kd = S.by_kind||{};
  const openAb = D.findings.filter(f=>isAbove(f) && !decided(f.finding_id));
  const openAmt = openAb.reduce((s,f)=>s+amtOf(f), 0);
  const rollup = belowRollup();
  const tiles = [
    [BAND_LABEL[0], openAb.length,
     'Over ' + money0(fixAt) + ' and not yet decided', openAb.length>0],
    ['Value to clear', money0(openAmt), 'Across those items', false],
  ];
  $('#kpis').innerHTML = tiles.map(t =>
    '<div class="card kpi"><h3>'+t[0]+'</h3><div class="v'+(t[3]?' accent':'')+'">'+t[1]+
    '</div><div class="n">'+t[2]+'</div></div>').join('');

  /* Where the threshold falls. A threshold is a judgment, so show what each
     candidate actually catches rather than asserting one is correct. Flagship
     runs $25,000; that number's cost is visible here rather than argued. */
  const rowsT = FIX_PRESETS.map(t => {
    const ab = D.findings.filter(f => amtOf(f) >= t);
    return {t:t, n:ab.length, amt:ab.reduce((s,f)=>s+amtOf(f),0)};
  });
  const allAmt = D.findings.reduce((s,f)=>s+amtOf(f),0) || 1;
  $('#thchart').innerHTML = '<div class="bars">'+rowsT.map(r=>
    '<button class="bar'+(r.t===fixAt?' on':'')+'" type="button" data-setfix="'+r.t+'"'+
      ' data-tip="At '+esc(money0(r.t))+': '+r.n+' items to work, '+esc(money(r.amt))+
      ' covered of '+esc(money(allAmt))+'">'+
      '<span class="lab">'+(r.t===0?'Everything':'Over '+money0(r.t))+
        +'</span>'+
      '<span class="val">'+r.n+' items</span>'+
      '<span class="shr">'+Math.round((r.amt/allAmt)*100)+'%</span>'+
      '<span class="track"><i class="fill'+(r.t===fixAt?' accent':'')+
        '" data-w="'+((r.amt/allAmt)*100).toFixed(1)+'"></i></span></button>').join('')+
    '</div>';
  animate($('#thchart'));

  /* The population under the line: counted, valued, and broken out by department,
     because concentration in one department changes what it means. */
  $('#belowsum').textContent = rollup.n
    ? rollup.n + ' items · ' + money(rollup.amt)
    : 'none';
  const bh = $('#belowhead');
  if (bh) bh.textContent = 'Items below ' + money0(fixAt);
  $('#belowcard').innerHTML = rollup.n
    ? '<table><thead><tr><th>Department</th><th class="num">Items</th>'+
      '<th class="num">Value</th></tr></thead><tbody>'+
      rollup.depts.map(d=>'<tr><td>'+esc(d.dept)+'</td><td class="num">'+d.n+
        '</td><td class="num">'+money(d.amt)+'</td></tr>').join('')+
      '</tbody></table>'
    : '<p class="note">No items fall under '+money0(fixAt)+'.</p>';

  /* Both bar charts are filters, not decoration: selecting a bar opens Review
     already narrowed to that slice. Widths animate from zero on render so the
     proportions are read rather than just seen. */
  function barRow(opts){
    return '<button class="bar" type="button"' +
      (opts.filter ? ' data-chart="'+opts.filter[0]+'" data-chartval="'+opts.filter[1]+'"' : '') +
      ' data-tip="'+esc(opts.tip)+'">' +
      '<span class="lab">'+esc(opts.label)+'</span>' +
      '<span class="val">'+opts.value+'</span>' +
      '<span class="shr">'+opts.share+'</span>' +
      '<span class="track"><i class="fill'+(opts.accent?' accent':'')+
      '" data-w="'+opts.pct.toFixed(1)+'"></i></span></button>';
  }
  function animate(el){
    requestAnimationFrame(()=>requestAnimationFrame(()=>{
      el.querySelectorAll('.fill[data-w]').forEach(i=>{ i.style.width = i.dataset.w+'%'; });
    }));
  }

  const byGroup={};
  D.findings.forEach(f=>{const g=groupOf(f);byGroup[g]=byGroup[g]||{n:0,amt:0};
    byGroup[g].n++;byGroup[g].amt+=(f.amount_at_risk||0);});
  const rows=Object.entries(byGroup).sort((a,b)=>b[1].amt-a[1].amt);
  const gTotal=rows.reduce((s,r)=>s+r[1].amt,0)||1;
  /* A treemap: each category's area is its share of the value, so where the
     money sits reads at a glance. Every cell is labeled with its name and
     figures, so identity never rests on color, and all cells share one neutral
     fill: the accent stays reserved for what needs action. A cell too small for
     its label carries it in the tooltip. */
  const cells = rows.filter(r=>r[1].amt>0).map(r=>({id:r[0], v:r[1].amt, n:r[1].n}));
  /* Laid out in a fixed 520 by 240 box and placed in percentages, so the map
     fills the card at any width without measuring it (the page may be hidden
     when this draws). Cells stay proportional to value. */
  const host = $('#groupchart');
  const W = 520, H = 240;
  const rects = squarify(cells, 0, 0, W, H);
  const pc = (v, of) => (v/of*100).toFixed(3)+'%';
  host.innerHTML = '<div class="tmap" style="height:'+H+'px">'+rects.map(c=>{
    const share = Math.round(c.v/gTotal*100);
    const roomy = c.w >= 95 && c.h >= 64, snug = c.w >= 60 && c.h >= 30;
    return '<button class="tcell" type="button" data-chart="group" data-chartval="'+esc(c.id)+'"'+
      ' style="left:'+pc(c.x,W)+';top:'+pc(c.y,H)+';width:'+pc(c.w,W)+';height:'+pc(c.h,H)+'"'+
      ' data-tip="'+esc(groupLabel(c.id)+' · '+money0(c.v)+' · '+share+'% · '+c.n+' finding'+(c.n===1?'':'s'))+'">'+
      (snug ? '<span class="tl">'+esc(groupLabel(c.id))+'</span>' : '')+
      (roomy ? '<span class="tv">'+money0(c.v)+'</span><span class="tn">'+share+'% · '+c.n+
        ' finding'+(c.n===1?'':'s')+'</span>' : '')+'</button>';
  }).join('')+'</div>';

  if($('#kindchart')){
  const kinds=Object.entries(kd).filter(e=>e[1]>0).sort((a,b)=>b[1]-a[1]);
  const kTotal=kinds.reduce((s,k)=>s+k[1],0)||1;
  $('#kindchart').innerHTML='<div class="bars">'+kinds.map(k=>barRow({
    label: KIND_LABEL(k[0]),
    value: k[1],
    share: Math.round((k[1]/kTotal)*100)+'%',
    pct: (k[1]/kTotal)*100,
    accent: k[0]==='needs_judgement',
    filter: ['kind', k[0]],
    tip: KIND_LABEL(k[0])+' · '+k[1]+' of '+kTotal+' findings',
  })).join('')+'</div>';
  animate($('#kindchart'));
  }
}

/* The threshold is the whole grading scheme now, so it is stated in one place and
   in money rather than in an adjective. Confidence is reported separately, per
   finding, because "how big" and "how sure" are different questions. */
function bandNote(f){
  return isAbove(f)
    ? 'At or over ' + money0(fixAt) + ', in the queue to clear'
    : 'Under ' + money0(fixAt) + ', counted in the aggregate and not queued';
}

/* ---------- review workspace ---------- */
function renderList(){
  if(!$('#list')) return;
  const list = visible();
  const cl = clusters(list).sort((a,b) =>
    (layerRank(a.layer) - layerRank(b.layer)) || (b.amt - a.amt));

  /* Value is concentrated: say how few decisions carry most of it, so the
     reviewer knows where attention belongs and what can go in bulk. */
  const totalAmt = cl.reduce((s,c) => s + c.amt, 0);
  let run = 0, need = 0;
  for (const c of cl){ run += c.amt; need++; if (run >= totalAmt * 0.8) break; }
  /* The threshold control sits here, so the consequence of moving it belongs
     here too -- the full department breakdown stays on Overview, where it is
     read as assurance rather than as part of working the queue. */
  /* The same control reverses itself: it opens the sub-threshold items, and once
     you are in them it is the way back out. Hiding it left no exit from the
     filter it had just applied. */
  const bl = $('#belowline'), ro = belowRollup();
  if (bl){
    if (band === 'below'){
      bl.textContent = '\u2190 Back to items over ' + money0(fixAt);
      bl.dataset.mode = 'reset';
      bl.hidden = false;
    } else {
      bl.textContent = ro.n
        ? ro.n + ' item' + (ro.n===1?'':'s') + ' \u00b7 ' + money(ro.amt) + ' below the line'
        : 'Nothing below the line';
      bl.dataset.mode = 'show';
      bl.hidden = !ro.n;
    }
  }

  $('#matline').textContent = cl.length
    ? cl.length + (cl.length===1?' decision':' decisions') +
      (list.length !== cl.length ? ' across ' + list.length + ' findings' : '') +
      (totalAmt ? ' · the top ' + need + ' carry 80% of the value' : '')
    : '';

  if(!cl.length){
    $('#list').innerHTML='<p class="empty">'+
      (queue==='open'?'Nothing outstanding in this filter.':'No findings match.')+'</p>';
    $('#detail').innerHTML='<p class="empty">Nothing selected.</p>'; return;
  }
  if(!selected || !list.some(f=>f.finding_id===selected)) selected=cl[0].items[0].finding_id;

  /* Nested layer, then group. The layer heading only appears when a run actually
     carries more than one, so a single-layer artifact renders exactly as before
     rather than gaining a heading that explains nothing. */
  const byLayer = {};
  cl.forEach(c => { (byLayer[c.layer] = byLayer[c.layer] || []).push(c); });
  const layerKeys = Object.keys(byLayer).sort((a,b)=>layerRank(a)-layerRank(b));
  const showLayers = layerKeys.length > 1;

  let html='';
  layerKeys.forEach((L, li) => {
    if (showLayers){
      html += '<div class="lhead"><span class="ltxt">'+esc(layerLabel(L))+'</span></div>';
    }
    const byGroup = {};
    byLayer[L].forEach(c => { (byGroup[c.group] = byGroup[c.group] || []).push(c); });
    Object.keys(byGroup).forEach(g=>{
    html+='<div class="ghead">'+esc(groupLabel(g))+'</div>';
    byGroup[g].forEach(c=>{
      const lead=c.items[0], d=decisions[lead.finding_id]||{};
      const sel=c.items.some(f=>f.finding_id===selected);
      const anyAbove=c.items.some(isAbove);
      html+='<div class="cluster'+(d.verdict?' done':'')+'" data-id="'+esc(lead.finding_id)+'"'+
        ' role="option" aria-selected="'+sel+'">'+
        '<div class="row" style="padding:0;background:none">'+
        '<span class="sv" style="background:'+SEV_COLOR[anyAbove?'above':'below']+'"></span>'+
        '<span class="ti">'+escn(c.subject)+'</span>'+
        '<span class="am">'+(c.amt?money0(c.amt):'')+'</span>'+
        '<span class="meta"><span>'+
        (c.all.length>1 ? c.all.length+' findings'
                        : esc(Math.round((lead.confidence||0)*100)+'% confident'))+
        (c.hidden ? ' · '+c.hidden+' under '+money0(fixAt) : '')+'</span>'+
        (d.verdict?'<span class="vd'+(decided(lead.finding_id)?'':' incomplete')+'">'+
          VERDICTS[d.verdict]+(decided(lead.finding_id)?'':' · needs a reason')+'</span>':'')+
        '</span></div></div>';
    });
    });
  });
  $('#list').innerHTML=html;
  renderDetail();
}

function renderDetail(){
  if(!$('#detail')) return;
  const f=D.findings.find(x=>x.finding_id===selected);
  if(!f){ $('#detail').innerHTML='<p class="empty">Nothing selected.</p>'; return; }
  const ev=f.evidence||{}, d=decisions[f.finding_id]||{};
  /* Several evidence strings are several facts joined by a middle dot, which on
     one line reads as a run-on. Each part gets its own line. */
  const kv=(k,v)=>{
    if(!v) return '';
    const parts=String(v).split(' \u00b7 ');
    return '<dt>'+k+'</dt><dd>'+parts.map(escl).join('<br>')+'</dd>';
  };
  let txn='';
  if((f.transactions||[]).length){
    txn='<h3 style="margin-top:var(--spacing-md)">Transactions ('+
      (f.transaction_count||f.transactions.length)+')</h3>'+
      '<table><thead><tr><th>Date</th><th>Document</th><th>Vendor</th><th>Account</th>'+
      '<th>Department</th><th class="num">Amount</th></tr></thead><tbody>'+
      f.transactions.map(t=>'<tr><td class="mono">'+esc(t.date)+'</td><td class="mono">'+
        docHTML(t.document_number)+'</td><td>'+esc(t.txn_type==='Expense Report'?'Expense report':t.vendor_or_name)+'</td><td>'+
        acctHTML(t.account_code)+'</td><td>'+esc(t.department)+'</td><td class="num">'+
        money(t.amount)+'</td></tr>').join('')+'</tbody></table>';
  }
  const act=(o)=>'<button class="pill pill--knockout'+(d.verdict===o[0]?' active':'')+
    '" data-decide="'+o[0]+'" aria-pressed="'+(d.verdict===o[0])+'" title="'+esc(o[4])+
    '">'+o[1]+'</button>';
  const hints='<dl class="hints">'+ACTIONS(f).map(o=>'<dt>'+o[1]+'</dt><dd>'+esc(o[4])+
    (o[3]?' <em>Written reason required.</em>':'')+'</dd>').join('')+'</dl>';
  const siblings=D.findings.filter(x=>clusterKey(x)===clusterKey(f));
  const memberList = siblings.length>1
    ? '<div class="members"><p class="secondary" style="margin:var(--spacing-2xs) 0">'+
      'One decision covers all '+siblings.length+' findings in this group.</p>'+
      siblings.map(s=>'<div class="m"><span>'+escn(s.title)+'</span><span>'+
        (s.amount_at_risk?money(s.amount_at_risk):'')+'</span></div>').join('')+'</div>'
    : '';

  $('#detail').innerHTML=
    '<span class="sev" style="color:'+SEV_COLOR[bandOf(f)]+'">'+
      esc(isAbove(f)?BAND_LABEL[0]:BAND_LABEL[1])+'</span>'+
    '<h3 class="dt">'+escn(f.title)+'</h3>'+
    '<div class="conf">Confidence '+Math.round((f.confidence||0)*100)+'% · '+
      esc(KIND_LABEL(f.kind))+
      (f.policy_is_draft?' · <span class="reqd">draft policy</span>':'')+
      '<div class="confbar"><i style="width:'+Math.round((f.confidence||0)*100)+'%"></i></div>'+
      (f.confidence_note?'<div style="margin-top:var(--spacing-2xs)">'+esc(f.confidence_note)+'</div>':'')+
    '</div>'+
    correctionHTML(f)+
    '<dl class="kv">'+
      (correctionIsDerived(f)?'':kv('Observed',ev.observed)+kv('Expected',ev.expected))+
      kv('Basis',ev.basis)+
      kv('Amount',f.amount_at_risk?money(f.amount_at_risk):null)+
      kv('Department',deptOf(f))+
      kv('Threshold',bandNote(f))+
      kv('Rule',f.rule_id)+'</dl>'+
    (f.recommendation?'<div class="rec"><b>Recommended</b><br>'+escl(f.recommendation)+'</div>':'')+
    '<div class="dispo"><h4>Your decision</h4><div class="acts">'+
      ACTIONS(f).map(act).join('')+'</div>'+hints+
      '<label class="notelab" for="note">'+noteLabel(f)+
        (noteRequired(f,d.verdict)?' <span class="reqd">· required</span>':'')+'</label>'+
      '<textarea id="note" placeholder="'+esc(noteLabel(f))+'">'+esc(d.note||'')+'</textarea>'+
      (d.verdict?'<div class="stamp">'+VERDICTS[d.verdict]+' · '+esc((d.at||'').slice(0,16).replace('T',' '))+
        (noteRequired(f,d.verdict)&&!(d.note||'').trim()?' · <span class="reqd">still needs a written reason</span>':'')+
        '</div>':'')+
    '</div>'+memberList+txn;
  growAll($('#detail'));
}

/* A blank rationale in an audit log is unexplained, even where the action needed
   no written comment. Where the reviewer typed nothing, the action's own standard
   basis is recorded in its place and marked as standard, so a default is never
   mistaken for something a person wrote. */
function rationaleOf(f, d){
  const typed = ((d && d.note) || '').trim();
  if (typed) return {text: typed, source: d.src === 'claude' ? 'drafted by Claude' : 'typed'};
  const verdict = d && d.verdict;
  const act = (ACTIONS(f).find(o => o[0] === verdict) || [])[4];
  return {text: act || '', source: act ? 'standard' : 'none'};
}

/* ---------- decisions & export ---------- */
/* The flux pack's commentary, one row per account that has some: the text, where
   it came from, and the account's changes. A Claude draft counts once accepted. */
function commentaryRows(){
  const t = (D.tables || [])[0]; if (!t) return [];
  const out = [];
  t.sections.forEach(sec => sec.rows.forEach(r => {
    const text = (fluxNotes[r.account_code] || '').trim(); if (!text) return;
    const draft = (DR.commentary||{})[r.account_code] && fluxNotes[r.account_code] === DR.commentary[r.account_code];
    const pend = pendingNotes[r.account_code] !== undefined && fluxNotes[r.account_code] === pendingNotes[r.account_code];
    out.push({r, text, src: draft ? (accepted[r.account_code] ? 'drafted by Claude, accepted' : 'drafted by Claude, not yet accepted')
      : pend ? (accepted[r.account_code] ? 'from an older record, accepted' : 'from an older record, not yet accepted') : 'typed'});
  }));
  return out;
}
/* ---------- Decisions: the finish step ----------
   What was decided, grouped by outcome as Scott reads it: fixed in NetSuite, in
   the NetSuite import, no action, and the follow ups still waiting. Under the
   threshold is counted, not listed as open, as on every other page. What is still
   open over the threshold is listed item by item, a row decided line by line with
   its open lines, so nothing missed hides inside a total. The finish step opens
   once nothing is open. */
/* The findings a schedule row settles. They are listed with their row, not twice. */
let ROW_FINDINGS = null;
function rowFindings(){
  if (!ROW_FINDINGS){ ROW_FINDINGS = new Set();
    VTABLES.forEach(t => { const sp = VT[t.kind] && VT[t.kind](t); if (!sp || !sp.done) return;
      t.sections.forEach(s => s.rows.forEach(r => (r.finding_ids||[]).forEach(id => ROW_FINDINGS.add(id)))); }); }
  return ROW_FINDINGS;
}
/* The pages in the bar, each with how to reach a row on it. */
function navPages(){
  return $$('.nav button[data-view]').map(b => ({b, view: b.dataset.view, vt: b.dataset.vt, cmp: b.dataset.cmpPage,
    label: b.dataset.label, vf: b.dataset.vf || null, t: b.dataset.vt ? VTABLES.find(x => x.id === b.dataset.vt) : null}));
}
function pageOfFinding(f){
  const ex = chExtra().find(x => x.ids.indexOf(f.finding_id) > -1);
  if (ex) return {label: ex.page, go: {ex: f.finding_id, page: ex.page}};
  const g = groupOf(f);
  const p = navPages().find(x => x.t && (x.t.groups || (x.t.group ? [x.t.group] : [])).indexOf(g) > -1);
  if (p) return {label: p.label, go: {vt: p.t.id, fid: f.finding_id}};
  if (hasEntry(f.finding_id)) return {label: LP.entries, go: {je: f.finding_id}};
  return {label: LP.review || 'Review', go: null};
}
/* The row's place on its schedule, as the schedule keys it when drawn. */
function rowPlace(t, r){
  const vf = t.id === 'vendors' && LAYOUT === 'ui-update' ? VF_OF(r) : undefined;
  for (const s of t.sections){ const i = s.rows.indexOf(r); if (i > -1) return {vt: t.id, vf, k: t.id+':'+s.id+':'+i, sec: s.id}; }
  return {vt: t.id};
}
const pageLabelOf = (t, r) => (navPages().find(x => x.vt === t.id && (!x.vf || !r || inVf(r, x.vf))) || {}).label || t.title;
const whenTxt = s => String(s||'').slice(0,16).replace('T',' ');
/* Every decided item, each in one group. */
function decidedItems(){
  const out = [], ns = netsuiteRows();
  /* A finding a row's own outcome settled is listed with the row, not again. */
  const covered = new Set();
  const GRP = {clear: 'none', question: 'follow', manual: 'netsuite', entry: 'import'};
  settledRows().forEach(x => {
    const page = pageLabelOf(x.t, x.r), go = rowPlace(x.t, x.r), name = x.r.vendor || x.r.department || '';
    if (x.d.outcome === 'reclass'){
      if (rowDone(x.key)) (x.r.finding_ids||[]).forEach(id => covered.add(id));
      const items = (x.r.detail||{}).items || [];
      lineScope(x.r, x.key).forEach(i => { const lo = lineOutcome(x.key, i), l = items[i];
        if (!lineDone(lo)) return;
        const rc = lo.outcome === 'reclass' ? ns.rcs.find(e => e.row.key === x.key && e.rc.i === i) : null;
        out.push({g: rc ? 'import' : GRP[lo.outcome], page, go, what: name+' '+(l.document||''),
          sub: rc ? rc.id+': '+acctText(lo.rc.from_account)+' to '+acctText(lo.rc.to_account) : (l.text || ''),
          amount: l.amount, outcome: rc ? 'Reclass' : OUT_LABEL[lo.outcome]+(lo.rest ? ', with the rest of the row' : ''),
          note: lo.note || '', from: lo.legacy ? 'recorded by Console 1.8.6' : '', by: lo.by, at: lo.at}); });
      return;
    }
    /* A row booked is listed by its entries, below, which are what the import holds. */
    if (!rowDone(x.key) || x.d.outcome === 'entry') return;
    (x.r.finding_ids||[]).forEach(id => covered.add(id));
    out.push({g: GRP[x.d.outcome], page, go, what: name, sub: (x.r.flags||[]).map(f => f.label).join(' · '),
      amount: x.r.amount, outcome: OUT_LABEL[x.d.outcome]+(x.d.outcome === 'question' && x.r.owner ? ' · '+x.r.owner : ''),
      note: x.d.note || '', from: x.d.src === 'claude' ? 'drafted by Claude' : '', by: x.d.by, at: x.d.at});
  });
  /* Every entry in the import, however it was booked: on its row, on its page or
     on Journal Entries. */
  ns.ok.forEach(e => {
    const f = D.findings.find(x => x.finding_id === e.finding_id) || {}, d = decisions[e.finding_id] || {};
    const r = rationaleOf(f, d), hit = settledRows().find(x => (x.r.finding_ids||[]).indexOf(e.finding_id) > -1);
    const p = hit ? {label: pageLabelOf(hit.t, hit.r), go: rowPlace(hit.t, hit.r)} : pageOfFinding(f);
    out.push({g: 'import', page: p.label, go: {je: e.finding_id}, what: memoOf(e),
      sub: e.entry_id+(jeEdits[e.finding_id] ? ', edited: '+jeEdits[e.finding_id].note : ''),
      amount: sumOf(linesOf(e), 'debit'), outcome: VERDICTS.book, note: r.text, from: r.source === 'typed' ? '' : r.source, by: d.by, at: d.at});
  });
  D.findings.forEach(f => {
    const d = decisions[f.finding_id]; if (!d || !d.verdict || d.verdict === 'book' || covered.has(f.finding_id) || !decided(f.finding_id)) return;
    const p = pageOfFinding(f), r = rationaleOf(f, d);
    out.push({g: {no_entry: 'none', question: 'follow', manual: 'netsuite'}[d.verdict], page: p.label, go: p.go,
      what: f.title, sub: f.finding_id, amount: f.amount_at_risk, outcome: VERDICTS[d.verdict], note: r.text,
      from: r.source === 'typed' ? '' : r.source, by: d.by, at: d.at});
  });
  if (TABLE) TABLE.sections.forEach(s => s.rows.forEach(r => {
    const code = r.account_code; if (!explained(code)) return;
    out.push({g: 'none', page: LP.flux, go: {cmp: 'mom', code}, what: acctText(code), sub: 'Commentary',
      amount: r.mom_var, outcome: 'Explained', note: fluxNotes[code],
      from: (DR.commentary||{})[code] === fluxNotes[code] ? 'drafted by Claude, accepted' : '', by: '', at: ''});
  }));
  return out;
}
/* What is still open over the threshold, item by item. Each says what it needs. */
function openItems(){
  const out = [], ns = netsuiteRows(), inImport = new Set(ns.ok.map(e => e.finding_id)), seen = new Set();
  navPages().forEach(p => {
    if (!p.t) return;
    const t = p.t, spec = VT[t.kind] && VT[t.kind](t); if (!spec) return;
    const gs = t.groups || (t.group ? [t.group] : null);
    if (gs){
      D.findings.filter(f => gs.indexOf(groupOf(f)) > -1 && openAt(f.finding_id)).forEach(f => { seen.add(f.finding_id);
        const d = decisions[f.finding_id] || {};
        out.push({page: p.label, go: {vt: t.id, fid: f.finding_id}, what: f.title, amount: amtOf(f),
          need: d.verdict ? VERDICTS[d.verdict]+', needs a reason' : 'Needs a decision'}); });
      return;
    }
    if (!spec.done) return;
    t.sections.forEach(s => s.rows.forEach(r => {
      if (p.vf && !inVf(r, p.vf)) return;
      const key = rowKeyOf(t, r), d = rowDec[key] || {}, name = r.vendor || r.department || '';
      if (spec.needs(r)){
        let need;
        if (d.outcome === 'reclass'){
          const items = (r.detail||{}).items || [], ol = openLines(key);
          need = plural(ol.length, 'line')+' without an outcome: '+ol.slice(0, 4).map(i => (items[i].document||'line '+(i+1))+' '+money(items[i].amount)).join(', ')+
            (ol.length > 4 ? ', and '+(ol.length-4)+' more' : '');
        } else need = d.outcome ? OUT_LABEL[d.outcome]+', needs a reason' : 'Needs an outcome';
        out.push({page: p.label, go: rowPlace(t, r), what: name, amount: spec.size(r), need});
      } else if (d.outcome === 'entry' && rowDone(key) && !(r.finding_ids||[]).some(id => inImport.has(id))){
        out.push({page: p.label, go: rowPlace(t, r), what: name, amount: r.amount,
          need: LO.entry+' on the row, but no proposed entry covers it, so nothing goes into the import. Choose another outcome, or ask Claude to draft the entry'});
      }
    }));
  });
  chExtra().forEach(x => x.ids.forEach(id => { const f = D.findings.find(y => y.finding_id === id);
    if (!f || !openAt(id) || seen.has(id)) return; seen.add(id); const d = decisions[id] || {};
    out.push({page: x.page, go: {ex: id, page: x.page}, what: f.title, amount: amtOf(f),
      need: d.verdict ? VERDICTS[d.verdict]+', needs a reason' : 'Needs a decision'}); }));
  /* An entry with no page of its own, such as one Claude drafted. */
  const onRows = rowFindings();
  ENTRIES.forEach(e => { if (!openAt(e.finding_id) || seen.has(e.finding_id) || onRows.has(e.finding_id)) return;
    const f = D.findings.find(x => x.finding_id === e.finding_id) || {}, d = decisions[e.finding_id] || {};
    out.push({page: LP.entries, go: {je: e.finding_id}, what: (e.rule_id === 'DRAFT' ? e.entry_id+' ' : '')+memoOf(e), amount: e.debits,
      need: d.verdict ? VERDICTS[d.verdict]+', needs a reason' : 'Needs a decision'}); });
  /* Booked, but kept out of the import because it does not balance. */
  ns.book.filter(e => !balancedOf(e)).forEach(e => out.push({page: LP.entries, go: {je: e.finding_id}, what: memoOf(e),
    amount: sumOf(linesOf(e), 'debit'), need: LO.entry+', but its lines do not balance, so it is not in the import. Edit it'}));
  if (TABLE){
    const cs = TABLE.comparisons.filter(c => c.id !== 'yoy');
    TABLE.sections.forEach(s => s.rows.forEach(r => {
      const hit = cs.filter(c => Math.abs(r[c.var]||0) >= fixAt); if (!hit.length || explained(r.account_code)) return;
      out.push({page: LP.flux, go: {cmp: hit[0].id, code: r.account_code}, what: acctText(r.account_code),
        amount: Math.max.apply(null, hit.map(c => Math.abs(r[c.var]||0))),
        need: isPendingNote(r.account_code) ? 'Commentary from a record saved before Console 1.8.7, which did not mark Claude’s drafts. Accept it or write your own'
          : isDraftNote(r.account_code) ? 'Claude drafted the commentary. Accept it or write your own' : 'Needs commentary'});
    }));
  }
  return out;
}
/* Worth a look before the upload; none of it stops the finish. */
function checkItems(){
  const out = [];
  Object.values(raised).forEach(x => out.push({page: LP.flux, go: {cmp: 'mom', code: x.account}, what: acctText(x.account),
    need: 'Entry raised on the flux pack. It has no lines yet, so it is not in the NetSuite import. Ask Claude to draft it, then book it'}));
  VTABLES.forEach(t => { const spec = VT[t.kind] && VT[t.kind](t); if (!spec || !spec.done) return;
    t.sections.forEach(s => s.rows.forEach(r => { const key = rowKeyOf(t, r), d = rowDec[key] || {};
      if (d.outcome === 'reclass' && !spec.needs(r) && openLines(key).length)
        out.push({page: pageLabelOf(t, r), go: rowPlace(t, r), what: r.vendor || r.department || '',
          need: 'Under '+money0(fixAt)+', started line by line: '+plural(openLines(key).length, 'line')+' without an outcome'}); })); });
  const ns = netsuiteRows();
  if (upload && !uploadFor(ns)) out.push({page: LP.decisions, go: {finish: true}, what: 'NetSuite upload',
    need: 'The import has changed since the upload was recorded. What was booked or removed since is not in NetSuite'});
  /* A row and the findings it settles are one decision, counted once. */
  const onRows = rowFindings();
  const unnamed = Object.keys(decisions).filter(id => decisions[id] && decisions[id].verdict && !decisions[id].by && !onRows.has(id)).length +
    Object.values(rowDec).filter(d => d && d.outcome && !d.by).length;
  if (unnamed) out.push({page: LP.decisions, go: null, what: plural(unnamed, 'decision')+' with no reviewer name',
    need: byWho() ? 'Taken before a name was set in the bar. Decisions from now on record '+byWho()
                  : 'Set Reviewer in the bar, so each decision records who took it'});
  return out;
}
let DGO = [], finishShown = false, loadedNote = null;
const goAttr = go => go ? ' data-dgo="'+(DGO.push(go) - 1)+'"' : '';
/* Reach an item on its page, opened. */
function goItem(go){
  if (!go) return;
  if (go.finish){ showFinish(); return; }
  if (go.ex){ const b = navPages().find(x => x.label === go.page); if (!b) return; b.b.click();
    const tr = $('[data-exk="'+go.ex+'"]'); if (tr) tr.scrollIntoView({block: 'center'}); return; }
  if (go.vt){ const b = $('.nav button[data-vt="'+go.vt+'"]'+(go.vf ? '[data-vf="'+go.vf+'"]' : '')) || $('.nav button[data-vt="'+go.vt+'"]'); if (!b) return; b.click();
    const t = VTABLES.find(x => x.id === go.vt), st = vtS(go.vt); let k = go.k;
    if (!k && go.fid) t.sections.forEach(s => s.rows.forEach((r, i) => { if (r.finding_id === go.fid) k = t.id+':'+s.id+':'+i; }));
    if (!k) return;
    const sec = k.split(':')[1]; if (st.shut) st.shut.delete(sec);
    st.open = k; renderVT();
    const tr = $('tr[data-xk="'+k+'"]'); if (tr) tr.scrollIntoView({block: 'center'}); return; }
  if (go.cmp){ const b = $('.nav button[data-cmp-page="'+go.cmp+'"]') || $('.nav button[data-cmp-page]'); if (!b) return; b.click();
    fxQ = ''; fxOnly = false; const q = $('#fxq'); if (q) q.value = '';
    openRow = go.code; renderTable(); const tr = $('tr[data-fx="'+go.code+'"]') || $('[data-cmt="'+go.code+'"]');
    if (tr) tr.scrollIntoView({block: 'center'}); return; }
  if (go.je){ const b = $('.nav button[data-view="entries"]'); if (!b) return; b.click();
    jeFilter = 'all'; jeOpen = go.je; renderEntries(); const tr = $('tr.jeh[data-je="'+go.je+'"]');
    if (tr) tr.scrollIntoView({block: 'center'}); }
}
function showFinish(){
  finishShown = true; renderDecisions();
  const f = $('#finish'); if (!f) return;
  const fv = f.closest('.view'); if (fv && fv.hidden) show(fv.id.slice(2));
  f.scrollIntoView({block: 'start'}); f.classList.remove('flash'); void f.offsetWidth; f.classList.add('flash');
}
function itemTable(xs, head, row){
  return '<div class="tblwrap"><table><thead><tr>'+head.map(h => '<th'+(/Amount/.test(h)?' class="num"':'')+'>'+h+'</th>').join('')+
    '</tr></thead><tbody>'+xs.map(row).join('')+'</tbody></table></div>';
}
function renderDecisions(){
  const view = $('#v-decisions'); if (!view || !$('#dnext')) return;
  /* Drawn when it shows: typing a reason elsewhere does not redraw it. The
     finish step can sit on its own page (Export, in the updated UI). */
  const fin = $('#dnext').closest('.view');
  if (view.hidden && (!fin || fin.hidden)) return;
  DGO = [];
  const ns = netsuiteRows(), open = openItems(), check = checkItems(), dec = decidedItems();
  const up = uploadFor(ns), exported = nsExport && nsExport.hash === ns.hash ? nsExport : null;
  const by = {}; dec.forEach(x => { (by[x.g] = by[x.g] || []).push(x); });
  const thr = money0(fixAt);
  /* The next thing to do: the NetSuite upload file, and the finish once nothing is open. */
  const holds = ns.entries ? plural(ns.entries, 'entry', 'entries')+', '+plural(ns.lines, 'line')+': '+
      plural(ns.ok.length, 'Journal Entry', 'Journal Entries')+' booked'+
      (ns.rcs.length ? ' and '+plural(ns.rcs.length, 'line reclass', 'line reclasses') : '') : 'Nothing booked yet, so the import is empty';
  const fileState = !ns.entries ? '' : up ? 'Uploaded to NetSuite by '+up.by+', '+whenTxt(up.at)
    : exported ? 'Downloaded '+whenTxt(exported.at)+'. Not yet recorded as uploaded'
    : nsExport ? 'Changed since it was downloaded '+whenTxt(nsExport.at)+'. Download it again' : 'Not downloaded yet';
  const lead = open.length
    ? plural(open.length, 'item')+' over '+thr+(open.length===1?' is':' are')+' still open, listed '+(LAYOUT === 'ui-update' ? 'on '+LP.decisions : 'below')+'. Settle '+(open.length===1?'it':'them')+', then finish.'
    : up ? 'Nothing over '+thr+' is open, and the upload is recorded. Save the decision record to hand over.'
    : 'Nothing over '+thr+' is open. Download the import, upload it to NetSuite, then record the upload.';
  $('#dnext').innerHTML = '<h3>Next: the NetSuite upload file</h3><p class="note">'+esc(lead)+'</p>'+
    '<div class="dline"><button class="pill" data-export="netsuite"'+(ns.entries?'':' disabled')+'>NetSuite import, CSV</button>'+
      '<button class="pill pill--knockout" data-export="audit"'+(ns.entries?'':' disabled')+'>Audit trail, CSV</button>'+
      '<span class="note">'+esc(holds)+(fileState ? '. '+esc(fileState) : '')+'</span>'+
      '<button class="pill pill--go" id="finish-go"'+(open.length ? ' disabled aria-disabled="true"' : '')+'>Finish the close '+
        '<span class="arw" aria-hidden="true">&rarr;</span></button>'+
      (open.length ? '<span class="why">Turns on when nothing over '+esc(thr)+' is open: '+plural(open.length, 'item')+' left.</span>' : '')+
    '</div>';
  /* What was decided, as one row of counts. */
  const tile = (g, n, note, cls) => '<button class="dtile'+(cls?' '+cls:'')+(n?'':' zero')+'" type="button" data-dtile="'+g+'">'+
    '<span class="dv">'+n+'</span><span class="dl">'+esc(LG[g])+'</span><span class="dn">'+esc(note)+'</span></button>';
  const sumAmt = xs => money0((xs||[]).reduce((s, x) => s + Math.abs(Number(x.amount)||0), 0));
  $('#decsum').innerHTML = '<h3>What was decided</h3><div class="dtiles">'+
    tile('import', (by.import||[]).length, sumAmt(by.import)+' · Entry booked and line reclasses')+
    tile('netsuite', (by.netsuite||[]).length, sumAmt(by.netsuite)+' · corrected in NetSuite')+
    tile('none', (by.none||[]).length, sumAmt(by.none)+' · Cleared'+(TABLE ? ' and commentary' : ''))+
    tile('follow', (by.follow||[]).length, sumAmt(by.follow)+' · waiting on an answer')+
    tile('open', open.length, open.length ? sumAmt(open)+' over '+thr : 'Nothing over '+thr, open.length ? 'open' : '')+
    '</div>';
  /* Still open, item by item, each a link to its row. */
  const oh = $('#dopen');
  oh.classList.toggle('isopen', !!open.length);
  oh.innerHTML = '<h3>'+esc(LG.open)+'<span class="n">'+plural(open.length, 'item')+' over '+esc(thr)+'</span></h3>'+
    (open.length ? itemTable(open, ['Page', 'Item', 'Amount', 'What it needs'], x =>
      '<tr class="xp"'+goAttr(x.go)+'><td>'+esc(x.page)+'</td><td>'+escn(x.what)+'</td><td class="num">'+
      (x.amount != null ? acct0(x.amount) : '')+'</td><td class="reqd">'+esc(x.need)+'</td></tr>')
      : '<p class="note">Nothing over '+esc(thr)+' is open. Items under it are counted on Overview, not listed.</p>');
  const ch = $('#dcheck');
  ch.hidden = !check.length;
  ch.innerHTML = '<h3>'+esc(LG.check)+'<span class="n">does not stop the finish</span></h3>'+
    itemTable(check, ['Page', 'Item', 'What to check'], x =>
      '<tr'+(x.go?' class="xp"':'')+goAttr(x.go)+'><td>'+esc(x.page)+'</td><td>'+escn(x.what)+'</td><td>'+esc(x.need)+'</td></tr>');
  /* Each outcome's items. */
  $('#dgroups').innerHTML = ['import', 'netsuite', 'none', 'follow'].filter(g => (by[g]||[]).length).map(g =>
    '<div class="card dgroup" id="dg-'+g+'" style="margin-top:var(--spacing-sm)"><h3>'+esc(LG[g])+
      '<span class="n">'+plural(by[g].length, 'item')+', '+sumAmt(by[g])+'</span></h3>'+
    itemTable(by[g].slice().sort((a, b) => a.page.localeCompare(b.page) || Math.abs(b.amount||0) - Math.abs(a.amount||0)),
      ['Item', 'Page', 'Amount', 'Outcome', 'Reason', 'By', 'When'], x =>
      '<tr class="'+(x.go?'xp':'')+'"'+goAttr(x.go)+'><td>'+escn(x.what)+(x.sub ? '<span class="sub2">'+escn(x.sub)+'</span>' : '')+'</td>'+
      '<td>'+esc(x.page)+'</td><td class="num">'+(x.amount != null && x.amount !== '' ? acct0(x.amount) : '')+'</td><td>'+esc(x.outcome)+'</td>'+
      '<td>'+(x.from && x.from !== 'drafted by Claude, accepted' && x.from !== 'drafted by Claude'
        ? '<span class="implied">'+esc(x.note)+'<em>'+esc(x.from === 'standard' ? 'standard basis' : x.from)+'</em></span>'
        : esc(x.note)+(x.from ? '<span class="sub2">'+esc(x.from)+'</span>' : ''))+'</td>'+
      '<td>'+esc(x.by || '')+'</td><td class="when">'+esc(whenTxt(x.at))+'</td></tr>')+'</div>').join('');
  /* An edited Journal Entry, booked or not, with the lines proposed and the lines
     it was edited to. */
  const et = $('#edittable');
  if (et){
    const eds = ENTRIES.filter(en => jeEdits[en.finding_id]);
    et.hidden = !eds.length;
    const sm = s => '<td class="mono" style="font-size:11px">'+esc(s)+'</td>';
    et.innerHTML = '<h3>Journal Entry edits</h3><div class="tblwrap"><table><thead><tr><th>Entry</th><th>Proposed</th><th>Edited to</th>'+
      '<th>Why it changed</th><th>Booked</th><th>By</th><th>When</th></tr></thead><tbody>'+eds.map(en => {
        const ed = jeEdits[en.finding_id], s = jeState(en), m = memoOf(en);
        return '<tr><td>'+esc(en.rule_id==='DRAFT' ? en.entry_id : en.finding_id)+'<span class="sub2">'+escn(m)+'</span>'+
          (m !== en.memo ? '<span class="sub2">Proposed memo: '+escn(en.memo)+'</span>' : '')+'</td>'+
          sm(entryText(en.lines))+sm(entryText(ed.lines))+'<td>'+esc(ed.note)+'</td>'+
          '<td>'+(s === 'book' ? LO.entry+', in the import' : s === 'no_entry' ? LO.clear+', not booked'
                  : '<span class="reqd">Not yet. Choose '+esc(LO.entry)+' to import it</span>')+'</td>'+
          '<td>'+esc(ed.by || '')+'</td>'+sm(whenTxt(ed.at))+'</tr>';
      }).join('')+'</tbody></table></div>';
  }
  renderFinish(ns, open, up, exported);
  const ld = $('#dloaded');
  if (ld){ ld.hidden = !loadedNote;
    if (loadedNote) ld.innerHTML = '<h3 style="display:flex;gap:var(--spacing-sm);align-items:baseline">Decision record loaded'+
      '<button class="fxact" id="dloaded-x" style="margin-left:auto">Dismiss</button></h3><p class="note">'+esc(loadedNote.from||'')+'</p>'+
      '<ul>'+(loadedNote.lines||[]).map(l => '<li>'+esc(l)+'</li>').join('')+'</ul>'+
      ((loadedNote.missed||[]).length ? '<p class="note">Not matched in this run: '+loadedNote.missed.map(escn).join('; ')+'</p>' : ''); }
}
/* The finish step: download, upload, record the upload, hand over. Shown once
   Finish the close is chosen, and from then on once the upload is recorded. */
function renderFinish(ns, open, up, exported){
  const host = $('#finish'); if (!host) return;
  host.hidden = !(finishShown || upload);
  if (host.hidden) return;
  const name = byWho();
  const step = (title, body) => '<li><b>'+title+'</b>'+body+'</li>';
  host.innerHTML = '<h3>Finish the close<span class="n">'+esc(M.period||'')+'</span></h3>'+
    (open.length ? '<p class="note reqd">'+plural(open.length, 'item')+' over '+esc(money0(fixAt))+' still open. The file below leaves '+(open.length===1?'it':'them')+' out.</p>' : '')+
    '<ol>'+
    step('Download the NetSuite import', '<p>'+esc(ns.entries ? plural(ns.entries, 'entry', 'entries')+', '+plural(ns.lines, 'line')+
        ', fingerprint '+ns.hash+'. ' : 'Nothing is booked, so the import is empty. ')+
        esc(exported ? 'Downloaded '+whenTxt(exported.at)+' as '+exported.file+'.' : nsExport ? 'The import has changed since it was downloaded; download it again.' : 'Not downloaded yet.')+
        ' Keep the audit trail with it: it says who decided each line, when and why.</p>'+
      '<div class="inl"><button class="pill" data-export="netsuite"'+(ns.entries?'':' disabled')+'>NetSuite import, CSV</button>'+
      '<button class="pill pill--knockout" data-export="audit"'+(ns.entries?'':' disabled')+'>Audit trail, CSV</button></div>')+
    step('Upload it to NetSuite', '<p>A person imports the file into NetSuite. Neither the console nor Claude posts to NetSuite.</p>')+
    step('Record the upload', up
      ? '<p class="done">Uploaded by <b>'+esc(up.by)+'</b>, '+esc(whenTxt(up.at))+'. '+esc(up.file)+', '+esc(plural(up.entries, 'entry', 'entries'))+', '+
          esc(plural(up.lines, 'line'))+', fingerprint <span class="mono">'+esc(up.hash)+'</span>'+(up.reference ? '. NetSuite reference: '+esc(up.reference) : '')+'.</p>'+
        '<div class="inl"><button class="fxact" id="up-clear">Clear the upload record</button></div>'
      : (upload ? '<p class="reqd">An upload was recorded by '+esc(upload.by)+', '+esc(whenTxt(upload.at))+', of '+esc(plural(upload.entries||0, 'entry', 'entries'))+
          ' (fingerprint '+esc(upload.hash||'')+'). The import has changed since: what was booked or removed since is not in NetSuite. Download it again, upload what is new, and record it.</p>' : '')+
        (Shared.on() ? '<p>Once the file is in NetSuite, record that you uploaded it. It is kept in the shared review and in the decision record.</p>'
          : '<p>Once the file is in NetSuite, say who uploaded it. It is kept in this browser and in the decision record.</p>')+
        '<div class="uprow"><label>Uploaded by<input type="text" class="fld" id="up-name" value="'+esc(name)+'" placeholder="Name"></label>'+
        '<label>NetSuite reference, if any<input type="text" class="fld" id="up-ref" placeholder="Import job or journal numbers"></label>'+
        '<button class="pill" id="up-record"'+(exported ? '' : ' disabled')+'>Record the upload</button></div>'+
        (exported ? '' : '<p class="note">Download the import first. The upload is recorded against that file.</p>'))+
    step('Hand over', '<p>Save the decision record: it carries every decision and the upload, for the close file and the next run. '+
        'The work paper is the same record for people, to attach to the entry in NetSuite. In the chat, Claude can summarize the session '+
        'and check the import against the record.</p>'+
      '<div class="inl"><button class="pill pill--knockout" data-export="record">Save the decision record, JSON</button>'+
      '<button class="pill pill--knockout" data-export="paper">Work paper, HTML</button></div>')+
    '</ol>';
}

/* ---------- sign-off ----------
   A drawn line on a page is decoration. A sign-off is a control: it records who
   attested to what and when, it survives a reload, and it does not let the final
   approval be given while work over the threshold is still outstanding. Stored
   beside the decisions, under the same run id. */
const ROLES = [['prepared','Prepared by'],['reviewed','Reviewed by'],
               ['approved','Approved by']];
/* The flux pack is a different object from the findings queue: every account
   line, not just the ones needing a decision, because "nothing moved here" is
   part of explaining a period. Commentary is the deliverable on this view, so it
   persists on its own key rather than riding on a decision the row may not have. */
const NOTE_KEY = 'serif-flux-notes::' + STORE_VERSION + '::' + (M.run_id || 'unknown');
let fluxNotes = (function(){ try { return JSON.parse(Store.getItem(NOTE_KEY)) || {}; }
                             catch(e){ return {}; } })();
function persistNotes(){
  try { Store.setItem(NOTE_KEY, JSON.stringify(fluxNotes)); } catch(e){}
}

/* ---------- Claude's drafts ----------
   Written in the Project from this run and checked against it at build time.
   A drafted commentary fills an empty field once; the reviewer's own text
   always wins. A draft counts as explained only once the reviewer accepts it
   or edits it, so nothing Claude wrote passes as reviewed. */
const DR = D.drafts || {};
const ACCEPT_KEY = 'serif-flux-accepted::' + STORE_VERSION + '::' + (M.run_id || 'unknown');
let accepted = (function(){ try { return JSON.parse(Store.getItem(ACCEPT_KEY)) || {}; }
                            catch(e){ return {}; } })();
function persistAccepted(){ try { Store.setItem(ACCEPT_KEY, JSON.stringify(accepted)); } catch(e){} }
Object.keys(DR.commentary || {}).forEach(c => { if (fluxNotes[c] === undefined) fluxNotes[c] = DR.commentary[c]; });
/* Commentary loaded from a record saved before Console 1.8.7, which did not mark
   Claude's drafts: it may be one, so it waits to be accepted or edited, as a
   draft does, and never counts as explained on loading alone. */
const PEND_KEY = 'serif-flux-pending::' + STORE_VERSION + '::' + (M.run_id || 'unknown');
let pendingNotes = (function(){ try { return JSON.parse(Store.getItem(PEND_KEY)) || {}; } catch(e){ return {}; } })();
function persistPending(){ try { Store.setItem(PEND_KEY, JSON.stringify(pendingNotes)); } catch(e){} }
const isPendingNote = code => pendingNotes[code] !== undefined && fluxNotes[code] === pendingNotes[code] && !accepted[code];
const isDraftNote = code => (!!(DR.commentary||{})[code] && fluxNotes[code] === DR.commentary[code] && !accepted[code]) || isPendingNote(code);
const explained = code => !!(fluxNotes[code]||'').trim() && !isDraftNote(code);
function draftBlock(title, body, action){
  return '<div class="dblock"><div class="dh"><b>'+esc(title)+'</b><span class="secondary">Drafted by Claude</span>'+
    (action || '')+'</div>'+(body ? '<p>'+String(body).split('\n').map(escn).join('<br>')+'</p>' : '')+'</div>';
}

/* Entries the reviewer raises off the pack, on lines no rule flagged. They join
   the engine's proposals in the same export, marked by origin, because an
   accountant reading the close file needs to know which the machine proposed and
   which a person did. */
const RAISE_KEY = 'serif-flux-raised::' + STORE_VERSION + '::' + (M.run_id || 'unknown');
let raised = (function(){ try { return JSON.parse(Store.getItem(RAISE_KEY)) || {}; }
                          catch(e){ return {}; } })();
function persistRaised(){
  try { Store.setItem(RAISE_KEY, JSON.stringify(raised)); } catch(e){}
}
function toggleRaise(code){
  const row = (TABLE.sections.reduce((a,s)=>a.concat(s.rows),[]))
              .find(r=>r.account_code===code);
  if(!row) return;
  if(raised[code]) delete raised[code];
  else {
    const c = TABLE.comparisons.find(x=>x.id===cmp);
    raised[code] = {account: code, leaf: row.account_leaf, basis: c.label,
                    amount: row[c.var], at: new Date().toISOString(), by: byWho()};
  }
  persistRaised(); renderTable(); renderDecisions();
  toast(raised[code] ? 'Entry raised for ' + row.account_leaf : 'Entry withdrawn');
}
const TABLE = (D.tables && D.tables.length) ? D.tables[0] : null;
let cmp = TABLE ? TABLE.comparisons[0].id : null;
let openRow = null;

/* A decision taken on a table row settles that row's finding only. The queue
   decides a whole cluster at once because a cluster is one call about one
   subject; a schedule lists findings one per line, and clicking one line must
   not silently settle another line two rows down. */
function decideOne(id, verdict){
  const cur = decisions[id] || {};
  /* A reclass the forecast staged is one entry over two findings, one on each
     account it moves between. Deciding the entry decides both. */
  const pair = (V.entries||[]).find(x => (x.finding_ids||[]).indexOf(id) > -1);
  const ids = pair ? pair.finding_ids : [id];
  const clearing = cur.verdict === verdict;
  ids.forEach(k => {
    if (clearing) delete decisions[k];
    else decisions[k] = {verdict, note: (decisions[k]||{}).note || cur.note || '',
                         at: new Date().toISOString(), by: byWho()};
  });
  persist(); renderAll();
  toast(decisions[id] ? VERDICTS[verdict] : 'Decision cleared');
}

/* ---------- schedule rows the reviewer settles ----------
   A line is fine until something flags it. A flagged row ends one of three
   ways: cleared, a question to its owner, or a Journal Entry.
   A reviewer can also reclass one line and clear the rest. Kept per run, beside the
   decisions, because an engine finding on the row is settled by the same call. */
const ROW_KEY = 'serif-rows::v1::' + (M.run_id || 'unknown');
let rowDec = (function(){ try { return JSON.parse(Store.getItem(ROW_KEY)) || {}; }
                          catch(e){ return {}; } })();
function persistRows(){
  try { Store.setItem(ROW_KEY, JSON.stringify(rowDec)); }
  catch(e){ if (storageOK){ storageOK = false; const w=$('#storewarn'); if(w) w.hidden = false; } }
}
/* Manually resolved is for a fix the reviewer made in NetSuite itself, a bill
   recoded while AP is open: the console books nothing, and the note says what
   was changed. Reclass is not a button: it is the outcome a row takes when the
   reviewer moves single lines and clears the rest (see the reclass section). */
const OUTCOMES = [['clear',LO.clear],['question',LO.question],['entry',LO.entry],['manual',LO.manual]];
/* `reclass` is the stored value for a row decided line by line: a reclass on
   some lines, an outcome of its own on others, and the rest of the row. */
const OUT_LABEL = {clear:LO.clear, question:LO.question, entry:LO.entry, manual:LO.manual, reclass:LO.reclass};
/* A line decided on its own takes one of these; Entry booked is a row's. */
const LINE_OUTCOMES = OUTCOMES.filter(o => o[0] !== 'entry');
const rowKeyOf = (t, r) => t.id + ':' + (r.vendor || r.department || '');
/* Follow up and Fixed in NetSuite need a reason; Cleared settles on the click. */
const noteNeeded = o => o === 'question' || o === 'manual';
/* The reclassed lines count only while the row is decided line by line. */
const rowReclass = key => { const d = rowDec[key] || {};
  return d.outcome === 'reclass' ? (d.reclass || []) : []; };
/* The row a stored key names, and the key of a row, found once. */
let ROWS_BY_KEY = null;
const KEY_OF_ROW = new Map();
function rowByKey(key){
  if (!ROWS_BY_KEY){ ROWS_BY_KEY = {};
    VTABLES.forEach(t => t.sections.forEach(s => s.rows.forEach(r => { const k = rowKeyOf(t, r);
      if (!(k in ROWS_BY_KEY)) ROWS_BY_KEY[k] = {t, r}; KEY_OF_ROW.set(r, k); }))); }
  return ROWS_BY_KEY[key] || null;
}
const keyOfRow = r => { rowByKey(''); return KEY_OF_ROW.get(r); };
/* Decided line by line (AIJ-110). Every line the row flags needs an outcome of
   its own: a reclass, Cleared, Follow up or Fixed in NetSuite, or the outcome the
   reviewer chose for the rest of the row. Nothing clears by default. A line is
   fine until something flags it, so a row whose flags name no lines asks for
   every line. A line given an outcome is always counted. */
function lineScope(r, key){
  const items = (r.detail||{}).items || [];
  const fl = lineSel(r, key, {kind: 'flags'});
  const out = new Set(fl ? Array.from(fl.hit) : items.map((l, i) => i));
  const d = rowDec[key] || {};
  rowReclass(key).forEach(x => out.add(x.i));
  if (d.outcome === 'reclass') Object.keys(d.lines || {}).forEach(i => out.add(Number(i)));
  return Array.from(out).filter(i => items[i]).sort((a, b) => a - b);
}
/* What one line ended as: its reclass, its own outcome, or the rest of the row's. */
function lineOutcome(key, i){
  const d = rowDec[key] || {};
  if (d.outcome !== 'reclass') return null;
  const rc = (d.reclass || []).find(x => x.i === i);
  if (rc) return {outcome: 'reclass', note: rc.note, at: rc.at, by: rc.by, rc: rc, own: true};
  const own = (d.lines || {})[i];
  if (own && own.outcome) return Object.assign({own: true}, own);
  if (d.rest && d.rest.outcome) return Object.assign({rest: true}, d.rest);
  return null;
}
const lineDone = lo => !!lo && (lo.outcome === 'reclass' || !noteNeeded(lo.outcome) || !!(lo.note||'').trim());
/* The lines of a row decided line by line that still need an outcome or a reason. */
function openLines(key){
  const hit = rowByKey(key); if (!hit) return [];
  return lineScope(hit.r, key).filter(i => !lineDone(lineOutcome(key, i)));
}
/* Lines in the row's scope with neither a reclass nor an outcome of their own:
   what an outcome for the rest of the row covers. */
function restLines(key){
  const hit = rowByKey(key), d = rowDec[key] || {}; if (!hit) return [];
  return lineScope(hit.r, key).filter(i => !(d.reclass||[]).some(x => x.i === i) && !((d.lines||{})[i]||{}).outcome);
}
function rowDone(key){
  const d = rowDec[key];
  if (d && d.outcome === 'reclass'){
    const hit = rowByKey(key);
    return !!hit && lineScope(hit.r, key).length > 0 && openLines(key).length === 0;
  }
  return !!(d && d.outcome && (!noteNeeded(d.outcome) || (d.note||'').trim()));
}
/* A row reclassed under Console 1.8.6 or earlier had the rest of the row cleared
   with the reclass. It keeps that outcome, now written down as the rest of the
   row's own, so it reads as a choice the reviewer can change, not as a default. */
const LEGACY_REST = 'Cleared with the line reclass, as Console 1.8.6 and earlier did.';
function upgradeRow(d){
  if (!d || d.outcome !== 'reclass' || d.lines || d.rest) return false;
  d.lines = {}; d.rest = {outcome: 'clear', note: LEGACY_REST, at: d.at, legacy: true};
  return true;
}
/* Each line names what it was decided as, for the exports and the summary. */
function lineSummary(key){
  const hit = rowByKey(key); if (!hit) return '';
  const items = (hit.r.detail||{}).items || [], parts = [];
  lineScope(hit.r, key).forEach(i => { const lo = lineOutcome(key, i), l = items[i]; if (!lo) return;
    parts.push((l.document||'line '+(i+1))+' '+money(l.amount)+': '+(lo.outcome === 'reclass'
      ? 'reclassed to '+acctText(lo.rc.to_account)+(lo.rc.to_department ? ' / '+lo.rc.to_department : '')
      : OUT_LABEL[lo.outcome]+(lo.rest ? ' with the rest of the row' : ''))+((lo.note||'').trim() ? ', '+lo.note.trim() : '')); });
  return 'Decided line by line. '+parts.join('; ')+'.';
}
/* A flag backed by engine findings is settled once all of them are decided,
   wherever that happened. */
const flagHandled = x => (x.finding_ids||[]).length > 0 && x.finding_ids.every(decided);
const openFlags = r => (r.flags||[]).filter(x => !flagHandled(x));
/* How much a row puts at stake: its largest open flag. The threshold is tested
   against this. */
function rowSize(t, r){
  const f = openFlags(r);
  return f.length ? Math.max.apply(null, f.map(x => x.amount)) : 0;
}
function rowNeeds(t, r){
  const key = rowKeyOf(t, r);
  if (rowDone(key)) return false;
  return rowSize(t, r) >= fixAt;
}
/* Each outcome keeps its own note. A reason for clearing is not a question for
   the owner, so switching outcomes shows the note written for the one chosen,
   and the one left is kept for when it is chosen again. `note` is always the
   note of the outcome in force: it is what the exports and the findings read. */
function stashNote(d){
  const notes = Object.assign({}, d.notes || {});
  if (d.outcome && d.outcome !== 'reclass') notes[d.outcome] = d.note || '';
  const srcFor = d.src ? (d.srcFor || d.outcome) : d.srcFor;
  return {notes: notes, srcFor: srcFor};
}
function setOutcome(t, r, outcome){
  const key = rowKeyOf(t, r), cur = rowDec[key] || {};
  const clearing = cur.outcome === outcome;
  const next = clearing ? null : outcome, kept = stashNote(cur);
  rowDec[key] = Object.assign({}, cur, {outcome: next, notes: kept.notes, srcFor: kept.srcFor,
                                        note: next ? (kept.notes[next] || '') : '',
                                        at: new Date().toISOString(), by: byWho()});
  if (kept.srcFor && kept.srcFor === next) rowDec[key].src = 'claude'; else delete rowDec[key].src;
  syncFindings(r, rowDec[key], key);
  persistRows(); persist(); renderAll();
  toast(clearing ? 'Outcome cleared' : OUT_LABEL[outcome]);
}
/* The row's outcome settles the engine findings on it: a Journal Entry books
   them, Cleared declines them with the same reason, and a question leaves them
   open until it is answered. Manually resolved and a reclass also decline the
   engine's proposed entry, since the fix is made elsewhere: in NetSuite, or by
   the reviewer's own reclass, which must not be booked twice. */
/* Decided line by line, the findings settle once every line has its outcome,
   and stay open while any line waits on a Follow up, as a row's Follow up does. */
function syncFindings(r, d, key){
  const note = (d.note||'').trim();
  const k = key || keyOfRow(r);
  const lineMode = d.outcome === 'reclass';
  const lineSettled = lineMode && rowDone(k) &&
    !lineScope(r, k).some(i => (lineOutcome(k, i)||{}).outcome === 'question');
  (r.finding_ids||[]).forEach(id => {
    if (d.outcome === 'entry') decisions[id] = {verdict:'book', note:d.note||'', at:d.at, by:d.by};
    else if (d.outcome === 'clear') decisions[id] = {verdict:'no_entry', note:d.note||'', at:d.at, by:d.by};
    else if (d.outcome === 'manual') decisions[id] = {verdict:'no_entry',
      note: note ? 'Resolved directly in NetSuite. ' + note : '', at:d.at, by:d.by};
    else if (lineSettled) decisions[id] = {verdict:'no_entry', note: lineSummary(k), at:d.at, by:d.by};
    else delete decisions[id];
  });
}
/* A line's own outcome. Choosing one starts deciding the row line by line;
   removing the last one ends it and reopens the row. Each outcome keeps its
   own note, as a row's does. */
function enterLineMode(d){
  if (d.outcome === 'reclass') return;
  const kept = stashNote(d); d.notes = kept.notes; d.srcFor = kept.srcFor;
  d.note = ''; delete d.src; d.reclass = []; d.lines = {}; delete d.rest; d.outcome = 'reclass';
}
function leaveLineModeIfEmpty(d){
  if (d.outcome === 'reclass' && !(d.reclass||[]).length && !Object.keys(d.lines||{}).length){
    d.outcome = null; delete d.reclass; delete d.lines; delete d.rest; }
}
function setLineOutcome(t, r, i, o){
  const key = rowKeyOf(t, r), d = rowDec[key] = rowDec[key] || {}, at = new Date().toISOString();
  if (!o && d.outcome !== 'reclass') return;
  enterLineMode(d);
  d.lines = d.lines || {};
  const cur = d.lines[i] || {}, notes = Object.assign({}, cur.notes || {});
  if (cur.outcome) notes[cur.outcome] = cur.note || '';
  if (o) d.lines[i] = {outcome: o, note: notes[o] || '', notes: notes, at: at, by: byWho()};
  else delete d.lines[i];
  leaveLineModeIfEmpty(d);
  d.at = at; d.by = byWho();
  syncFindings(r, d, key); persistRows(); persist(); renderAll();
  const left = d.outcome === 'reclass' ? openLines(key).length : 0;
  toast(!o ? 'Line outcome removed' : OUT_LABEL[o]+' for this line'+(left ? '. '+left+' line'+(left===1?'':'s')+' still open' : ''));
}
/* One outcome for every line in the row's scope that has none of its own. */
function setRestOutcome(t, r, o){
  const key = rowKeyOf(t, r), d = rowDec[key]; if (!d || d.outcome !== 'reclass') return;
  const cur = d.rest || {}, notes = Object.assign({}, cur.notes || {});
  if (cur.outcome && !cur.legacy) notes[cur.outcome] = cur.note || '';
  if (cur.outcome === o) delete d.rest;
  else d.rest = {outcome: o, note: notes[o] || '', notes: notes, at: new Date().toISOString(), by: byWho()};
  d.at = new Date().toISOString(); d.by = byWho();
  syncFindings(r, d, key); persistRows(); persist(); renderAll();
  toast(d.rest ? OUT_LABEL[o]+' for the rest of the row' : 'Outcome for the rest of the row removed');
}
const lineNoteLabel = (o, owner) => o === 'question' ? 'Question for ' + (owner || 'the owner')
  : o === 'manual' ? 'What was changed in NetSuite' : 'Why it is right';
function outcomeHTML(t, r, owner, bookable){
  const key = rowKeyOf(t, r), d = rowDec[key] || {};
  if (d.outcome === 'reclass'){
    /* Decided line by line: the reclasses, then the lines left, which take an
       outcome each in the table above or one outcome together here. */
    const rc = rowReclass(key), rest = restLines(key), open = openLines(key), rs = d.rest || {};
    return (rc.length ? '<div class="rcsum"><b>Reclass '+rc.length+' line'+(rc.length===1?'':'s')+', '+
        money(rc.reduce((s, x) => s + x.amount, 0))+'</b>'+
      '<ul>'+rc.map(x => '<li><span class="mono">'+docHTML(x.document)+'</span> '+money(x.amount)+': '+
        esc(acctText(x.from_account))+(x.from_department?' / '+esc(x.from_department):'')+' to <b>'+
        esc(acctText(x.to_account))+(x.to_department?' / '+esc(x.to_department):'')+'</b>. '+esc(x.note)+'</li>').join('')+
      '</ul></div>' : '')+
      (rest.length || rs.outcome
        ? '<div class="restbox"><div class="rh"><b>'+(rest.length ? 'The other '+rest.length+' flagged line'+(rest.length===1?'':'s')
              : 'The rest of the row')+'</b>'+
            (rs.outcome ? '' : ': give each an outcome in the table above, or one outcome for all of '+(rest.length===1?'it':'them')+' here.')+
            (open.length && rs.outcome ? ' <span class="reqd">'+open.length+' line'+(open.length===1?'':'s')+' still open</span>' : '')+'</div>'+
          '<div class="acts">'+LINE_OUTCOMES.map(o =>
            '<button class="fxact'+(rs.outcome===o[0]?' on':'')+'" data-rest="'+esc(key)+'" data-o="'+o[0]+'" aria-pressed="'+
            (rs.outcome===o[0])+'">'+o[1]+'</button>').join('')+'</div>'+
          (rs.outcome ? '<textarea class="cmt" data-restnote="'+esc(key)+'" rows="1" aria-label="'+esc(lineNoteLabel(rs.outcome, owner))+
            '" placeholder="'+esc(lineNoteLabel(rs.outcome, owner)+(noteNeeded(rs.outcome)?' (required)':''))+'">'+esc(rs.note||'')+'</textarea>'
            : '')+'</div>'
        : '');
  }
  const lab = d.outcome === 'question' ? 'Question for ' + (owner || 'the owner')
            : d.outcome === 'entry' ? 'What the entry should do'
            : d.outcome === 'manual' ? 'What was changed in NetSuite' : 'Why it is right';
  return '<div class="acts">'+OUTCOMES.map(o =>
      '<button class="fxact'+(d.outcome===o[0]?' on':'')+'" data-outcome="'+
      esc(key)+'" data-o="'+o[0]+'" aria-pressed="'+(d.outcome===o[0])+'">'+o[1]+'</button>').join('')+
    '</div>'+
    (d.outcome
      ? '<textarea class="cmt" data-rowkey="'+esc(key)+'" rows="1" aria-label="'+esc(lab)+'" placeholder="'+
        esc(lab+(noteNeeded(d.outcome)?' (required)':''))+'">'+
        esc(d.note||'')+'</textarea>'
      : '')+
    '';
}
/* A row shows its flagged lines or all of them, largest first. A line being
   reclassed, or already reclassed, is always listed. */
const UNDO_ICON = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" fill="none" '+
  'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'+
  '<path d="M5.5 3.5 2.5 6.5l3 3"/><path d="M2.5 6.5h7a3.5 3.5 0 0 1 0 7H7"/></svg>';
/* Which lines a flag, or a coding, is about. */
function lineHits(m, l){
  if (m.all) return true;
  if (m.not) return !m.not.some(c => c.account === l.account && (c.department||'') === (l.department||''));
  if (m.document) return (l.document||'') === m.document && (!m.account || l.account === m.account);
  return l.account === m.account && (m.department == null || (l.department||'') === m.department);
}
/* The lines a set of matches selects. A coding with no line on it, as when a
   Coupa PO charges a department the ledger never used, selects the lines on its
   account instead. */
function matchLines(items, ms){
  const hit = new Set();
  ms.forEach(m => {
    let any = false;
    items.forEach((l, i) => { if (lineHits(m, l)){ hit.add(i); any = true; } });
    if (!any && m.account && m.department != null && !m.document)
      items.forEach((l, i) => { if (l.account === m.account) hit.add(i); });
  });
  return hit;
}
/* A row opens on its flagged lines. A coding narrows them; All lists every line,
   the largest first. */
const lineView = {};
function lineSel(r, key, view){
  const items = (r.detail||{}).items || [], v = view || lineView[key] || {kind: 'flags'};
  const flags = (r.flags||[]).filter(x => (x.match||[]).length);
  let ms = null, label = '';
  if (v.kind === 'coding'){ ms = [{account: v.account, department: v.department}];
    label = acctText(v.account)+' / '+(v.department || 'No department'); }
  else if (v.kind === 'flags' && flags.length){ ms = [].concat.apply([], flags.map(x => x.match)); label = 'Flagged lines'; }
  if (!ms) return null;
  const hit = matchLines(items, ms);
  if (!hit.size && v.kind === 'flags') return null;
  return {hit: hit, label: label};
}
function linesHTML(t, r, title){
  const key = rowKeyOf(t, r), dt = r.detail || {}, all = dt.items || [];
  if (!all.length) return '';
  const rcBy = {}; rowReclass(key).forEach(x => { rcBy[x.i] = x; });
  const dRow = rowDec[key] || {}, lineMode = dRow.outcome === 'reclass';
  const ownOf = i => lineMode ? (dRow.lines||{})[i] : null;
  const inScope = lineMode ? new Set(lineScope(r, key)) : null;
  const keep = i => rcBy[i] || (ownOf(i)||{}).outcome || (rcEdit && rcEdit.key === key && rcEdit.i === i);
  const idx = all.map((l, i) => i), v = lineView[key] || {kind: 'flags'};
  /* Two views, Flagged and All. A coding picked in the coding table narrows the
     list further, and shows as a chip that clears back to Flagged. */
  const flagged = lineSel(r, key, {kind: 'flags'});
  const narrow = v.kind === 'coding' ? lineSel(r, key) : null;
  /* Each line names the flags it falls under, where the row has more than one or
     every line is listed. */
  const fl = (r.flags||[]).filter(x => (x.match||[]).length)
    .map(x => ({label: x.label, hit: matchLines(all, x.match)}));
  const flagsOf = i => fl.filter(f => f.hit.has(i)).map(f => f.label);
  const showAll = !narrow && (v.kind === 'all' || !flagged);
  const shown = narrow ? idx.filter(i => narrow.hit.has(i) || keep(i))
              : showAll ? idx : idx.filter(i => flagged.hit.has(i) || keep(i));
  const seg = (kind, label, n, on) => '<button class="fxact'+(on?' on':'')+'" aria-pressed="'+on+
    '" data-lview="'+esc(key)+'" data-kind="'+kind+'">'+label+' '+n+'</button>';
  let ctl = flagged
    ? '<span class="inl">'+seg('flags', 'Flagged', flagged.hit.size, !narrow && !showAll)+
        seg('all', 'All', all.length, showAll)+'</span>'
    : '<span class="secondary">'+all.length+'</span>';
  if (narrow) ctl += '<span class="lfilt">'+esc(narrow.label)+' · '+shown.length+
    '<button class="lfx" data-lview="'+esc(key)+'" data-kind="flags" aria-label="Clear this filter" '+
    'title="Clear this filter">&times;</button></span>';
  return '<h5 class="inl"><span>'+esc(title)+'</span>'+ctl+'</h5>'+
    '<table class="evtxn"><thead><tr><th>Date</th><th>Document</th><th>What was bought</th><th>Account</th>'+
    '<th>Department</th><th class="num">Amount</th><th></th></tr></thead><tbody>'+
    shown.map(i => {
      const l = all[i], rc = rcBy[i], editing = rcEdit && rcEdit.key === key && rcEdit.i === i;
      const moved = (from, to, txt) => rc && from !== to
        ? '<s class="secondary">'+esc(txt(from))+'</s><span class="sub2 rcto">to '+esc(txt(to))+'</span>'
        : esc(txt(from));
      const own = ownOf(i) || {};
      /* A line takes its own outcome from a compact choice beside Reclass. */
      const pickOut = '<select class="lout" data-lout="'+esc(key)+'" data-li="'+i+'" aria-label="Outcome for this line">'+
        '<option value=""'+(own.outcome?'':' selected')+'>'+(own.outcome ? 'No outcome' : 'Outcome')+'</option>'+
        LINE_OUTCOMES.map(o => '<option value="'+o[0]+'"'+(own.outcome===o[0]?' selected':'')+'>'+esc(o[1])+'</option>').join('')+'</select>';
      const acts = editing ? ''
        : '<div class="inl">'+(rc ? '<button class="fxact" data-rcopen="'+esc(key)+'" data-li="'+i+'">Edit</button>'+
               '<button class="fxact ico" data-rcremove="'+esc(key)+'" data-li="'+i+'" aria-label="Undo reclass" title="Undo reclass">'+UNDO_ICON+'</button>'
             : '<button class="fxact" data-rcopen="'+esc(key)+'" data-li="'+i+'">Reclass</button>'+pickOut)+'</div>';
      const f = editing ? reclassFields(key, i, l) : null;
      /* Where the row is decided line by line, each line says where it stands. */
      const lo = lineMode && (inScope.has(i) || rc) ? lineOutcome(key, i) : null;
      const lst = !lineMode || !(inScope.has(i) || rc) ? ''
        : '<span class="lstate'+(lineDone(lo)?'':' needs')+'" data-lst="'+esc(key)+'|'+i+'">'+esc(lineStateText(lo))+'</span>';
      return '<tr class="'+(rc?'lrc':'')+(own.outcome?' lout-on':'')+(editing?' rcon':'')+'"><td class="mono">'+esc(l.date)+'</td><td class="mono">'+docHTML(l.document)+'</td>'+
        '<td class="ltext">'+(l.text ? esc(l.text) : '<span class="blank">No description. Open the invoice.</span>')+
          ((fl.length > 1 || showAll) && flagsOf(i).length ? '<span class="sub2 lflag">'+esc(flagsOf(i).join(' · '))+'</span>' : '')+lst+'</td>'+
        (f ? f.acct : '<td>'+moved(l.account, rc && rc.to_account, acctText)+'</td>')+
        (f ? f.dept : '<td>'+moved(l.department||'', rc && rc.to_department, x => x || 'No department')+'</td>')+
        '<td class="num">'+money(l.amount)+'</td><td class="lacts">'+acts+'</td></tr>'+
        (editing ? reclassWhy(key, i) : '')+
        (!editing && !rc && own.outcome ? '<tr class="rcedit lnote"><td colspan="7"><div class="rcform">'+
          '<label class="rcwhy">'+esc(lineNoteLabel(own.outcome, r.owner || r.department))+
          (noteNeeded(own.outcome) ? ' (required)' : '')+'<input type="text" class="fld" data-lnote="'+esc(key)+'" data-li="'+i+
          '" value="'+esc(own.note||'')+'" placeholder="'+esc(lineNoteLabel(own.outcome, r.owner || r.department))+'"></label></div></td></tr>' : '');
    }).join('')+'</tbody></table>';
}
function lineStateText(lo){
  if (!lo) return 'Needs an outcome';
  if (lo.outcome === 'reclass') return 'Reclassed';
  const lab = OUT_LABEL[lo.outcome] + (lo.rest ? ', with the rest of the row' : '');
  return lineDone(lo) ? lab : lab + ', needs a reason';
}

/* ---------- a reclass on one line ----------
   Most lines on a row can be right while one is miscoded. The reviewer moves
   that line to an account from the chart, never typed, says why, and the rest
   of the row is cleared in the same pass. The move joins the NetSuite import as
   its own entry, and the line keeps its own description, so the original entry
   stays intact and the change is documented beside it. */
const lineIdOf = (l, i) => (l.document||'') + '|' + l.amount + '|' + i;
let rcEdit = null;
function deptChoices(){
  const s = new Set();
  VTABLES.forEach(t => t.sections.forEach(sec => sec.rows.forEach(r => {
    (r.by_department||[]).forEach(g => { if (g.department) s.add(g.department); });
    ((r.detail||{}).items||[]).forEach(l => { if (l.department) s.add(l.department); });
  })));
  return Array.from(s).sort();
}
/* P&L accounts by their group in the chart, then the balance sheet. */
function accountOptions(sel){
  const groups = {}, order = [];
  Object.keys(ACCTS).sort().forEach(c => {
    const g = /^[5-9]/.test(c) ? ((ACCTS[c]||{}).parent || 'Other income and expense') : 'Balance sheet';
    if (!groups[g]){ groups[g] = []; order.push(g); }
    groups[g].push(c);
  });
  order.sort((a, b) => (a === 'Balance sheet') - (b === 'Balance sheet') || groups[a][0].localeCompare(groups[b][0]));
  return order.map(g => '<optgroup label="'+esc(g)+'">'+groups[g].map(c =>
    '<option value="'+esc(c)+'"'+(c===sel?' selected':'')+'>'+esc(acctText(c))+'</option>').join('')+'</optgroup>').join('');
}
/* The line's own account and department cells become choices; the reason sits
   below the line. */
function reclassFields(key, i, l){
  const cur = rowReclass(key).find(x => x.i === i) || {};
  const acct = cur.to_account || l.account;
  const dep = cur.to_department != null ? cur.to_department : (l.department || '');
  const deps = deptChoices(); if (dep && deps.indexOf(dep) < 0) deps.push(dep);
  const pick = (label, text, sel) => '<td class="rcpick"><span class="rcval"><span class="rcshow">'+esc(text)+'</span>'+
    '<span class="caret" aria-hidden="true">▾</span></span>'+sel+'</td>';
  return {
    acct: pick('Account', acctText(acct), '<select id="rc-acct" aria-label="Account">'+accountOptions(acct)+'</select>'),
    dept: pick('Department', dep || 'No department', '<select id="rc-dept" aria-label="Department"><option value=""'+
      (dep?'':' selected')+'>No department</option>'+
      deps.map(x => '<option'+(x===dep?' selected':'')+'>'+esc(x)+'</option>').join('')+'</select>')};
}
function reclassWhy(key, i){
  const cur = rowReclass(key).find(x => x.i === i) || {};
  return '<tr class="rcedit"><td colspan="7"><div class="rcform">'+
    '<label class="rcwhy">Why it moves<input type="text" class="fld" id="rc-note" value="'+esc(cur.note||'')+
      '" placeholder="What the line is, and where it belongs"></label>'+
    '<span class="inl"><button class="fxact primary" data-rcsave="'+esc(key)+'" data-li="'+i+'">Save</button>'+
    '<button class="fxact" data-rccancel="1">Cancel</button></span></div></td></tr>';
}
function saveReclass(t, r, i){
  const key = rowKeyOf(t, r), l = ((r.detail||{}).items||[])[i];
  if (!l) return;
  const to = ($('#rc-acct')||{}).value, dep = ($('#rc-dept')||{}).value || '';
  const note = (($('#rc-note')||{}).value || '').trim();
  if (!ACCTS[to]){ toast('Choose an account from the chart'); return; }
  if (to === l.account && dep === (l.department || '')){ toast('Choose a different account or department'); return; }
  if (!note){ toast('Say why the line moves'); const n = $('#rc-note'); if (n) n.focus(); return; }
  const d = rowDec[key] = rowDec[key] || {}, at = new Date().toISOString();
  /* A reclass starts deciding the row line by line. The other lines are not
     cleared with it: each takes its own outcome, or the rest of the row's. */
  enterLineMode(d);
  d.reclass = (d.reclass || []).filter(x => x.i !== i);
  d.reclass.push({i: i, id: lineIdOf(l, i), date: l.date, document: l.document || '', text: l.text || '',
    amount: l.amount, vendor: l.vendor || r.vendor || '', from_account: l.account,
    from_department: l.department || '', to_account: to, to_department: dep, note: note, at: at, by: byWho()});
  d.reclass.sort((a, b) => a.i - b.i);
  if (d.lines) delete d.lines[i];
  d.at = at; d.by = byWho(); rcEdit = null;
  syncFindings(r, d, key); persistRows(); persist(); renderAll();
  const left = openLines(key).length;
  toast(left ? 'Line reclassed. '+left+' other line'+(left===1?' needs':'s need')+' an outcome' : 'Line reclassed', left ? 3000 : 1400);
}
function removeReclass(t, r, i){
  const key = rowKeyOf(t, r), d = rowDec[key];
  if (!d || d.outcome !== 'reclass') return;
  d.reclass = (d.reclass || []).filter(x => x.i !== i);
  leaveLineModeIfEmpty(d);
  d.at = new Date().toISOString(); d.by = byWho(); rcEdit = null;
  syncFindings(r, d, key); persistRows(); persist(); renderAll();
  toast('Reclass undone');
}
/* The row's reclasses as NetSuite import rows: one balanced entry per line,
   debit where it belongs and credit where it was posted, flipped for a credit
   line. The line memo keeps the line's own document and description. */
function periodEnd(){
  const m = /^([A-Za-z]{3})\w*\s+(\d{4})$/.exec(M.period || '');
  const mi = m ? ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'].indexOf(m[1].toLowerCase()) : -1;
  if (mi < 0) return '';
  const d = new Date(Date.UTC(Number(m[2]), mi + 1, 0));
  return d.toISOString().slice(0, 10);
}
function memoTag(){
  const m = /^([A-Za-z]{3})\w*\s+\d{2}(\d{2})$/.exec(M.period || '');
  return m ? m[1] + "'" + m[2] : '';
}
function reclassEntries(){
  const out = [];
  settledRows().filter(x => x.d.outcome === 'reclass').forEach(x => (x.d.reclass || []).forEach(rc => {
    const amt = Math.abs(rc.amount || 0), pos = (rc.amount || 0) >= 0;
    const memo = rc.note.indexOf('|') > -1 ? rc.note : rc.note + (memoTag() ? ' | ' + memoTag() : '');
    const lineMemo = (rc.document + ' ' + (rc.text || '')).trim();
    out.push({id: 'RECLASS-' + String(out.length + 1).padStart(3, '0'), date: periodEnd(), memo: memo,
      vendor: rc.vendor || x.r.vendor || '', row: x, rc: rc,
      lines: [
        {account: pos ? rc.to_account : rc.from_account, department: pos ? rc.to_department : rc.from_department,
         debit: amt, credit: '', memo: lineMemo},
        {account: pos ? rc.from_account : rc.to_account, department: pos ? rc.from_department : rc.to_department,
         debit: '', credit: amt, memo: lineMemo},
      ]});
  }));
  return out;
}
function gridHTML(rows, name, P){
  const cols = [['prior2', P.prior2], ['prior', P.prior], ['current', P.current]].filter(c => c[1]);
  const shown = (rows||[]).filter(g => cols.some(c => Math.abs(g[c[0]]||0) >= 0.005));
  if (!shown.length) return '';
  return '<table class="evtxn"><thead><tr><th>'+(name==='account'?'Account':'Department')+'</th>'+
    cols.map(c => '<th class="num">'+esc(c[1])+'</th>').join('')+'</tr></thead><tbody>'+
    shown.map(g => {
      const fresh = g.current && !g.prior && !g.prior2;
      return '<tr><td>'+esc(name==='account' ? acctText(g.account) : g.department)+'</td>'+
        cols.map(c => '<td class="num'+(c[0]==='current' && fresh ? ' over' : '')+'">'+
          (Math.abs(g[c[0]]||0) >= 0.005 ? acct0(g[c[0]]) : '<span class="secondary">-</span>')+'</td>').join('')+'</tr>';
    }).join('')+'</tbody></table>';
}
/* One table of the vendor's codings, account and department together, over the
   three months. A row narrows the lines below to that coding. */
function codingTable(t, r, P){
  const key = rowKeyOf(t, r), v = lineView[key] || {};
  const cols = [['prior2', P.prior2], ['prior', P.prior], ['current', P.current]].filter(c => c[1]);
  const rows = (r.by_coding||[]).filter(g => cols.some(c => Math.abs(g[c[0]]||0) >= 0.005));
  if (!rows.length) return '';
  return '<table class="evtxn"><thead><tr><th>Account</th><th>Department</th>'+
    cols.map(c => '<th class="num">'+esc(c[1])+'</th>').join('')+'</tr></thead><tbody>'+
    rows.map(g => {
      const fresh = g.current && !g.prior && !g.prior2;
      const on = v.kind === 'coding' && v.account === g.account && v.department === g.department;
      return '<tr class="pick'+(on?' sel':'')+'" data-lview="'+esc(key)+'" data-kind="coding" data-a="'+esc(g.account)+
        '" data-d="'+esc(g.department)+'"><td>'+esc(acctText(g.account))+'</td><td>'+esc(g.department || 'No department')+'</td>'+
        cols.map(c => '<td class="num'+(c[0]==='current' && fresh ? ' over' : '')+'">'+
          (Math.abs(g[c[0]]||0) >= 0.005 ? acct0(g[c[0]]) : '<span class="secondary">-</span>')+'</td>').join('')+'</tr>';
    }).join('')+'</tbody></table>';
}
function vendorPanel(t, r, span){
  const P = t.periods, key = rowKeyOf(t, r), v = lineView[key] || {};
  const flags = (r.flags||[]).map(x => {
    let why = x.why, todo = x.do;
    if ((x.finding_ids||[]).length){
      /* A flag that merges several findings quotes each one's figures. */
      const exs = x.finding_ids.map(id => (V.explain||{})[id] || {});
      why = exs.map(e => e.why || '').filter(Boolean).join(' '); todo = (exs[0] || {}).do || '';
    }
    const done = flagHandled(x);
    return '<div class="vflag'+(!done && x.amount >= fixAt ? ' needs' : '')+'"><div class="vfh"><b>'+esc(x.label)+'</b>'+
      '<span class="num">'+acct0(x.amount)+'</span>'+
      (x.finding_ids.length > 1 ? '<span class="secondary">'+x.finding_ids.length+' findings</span>' : '')+
      (done ? '<span class="st done">Decided on Journal Entries</span>' : '')+'</div>'+
      (why ? '<p>'+escl(why)+'</p>' : '')+(todo ? '<p class="secondary">'+escl(todo)+'</p>' : '')+'</div>';
  }).join('');
  const plan = (r.planned||[]).length
    ? '<p class="plan">Plan ('+esc(t.plan_vintage||'forecast')+'): '+r.planned.map(c =>
        esc(acctText(c.account))+' / '+esc(c.department||'no department')+' '+acct0(c.amount)).join('; ')+'</p>' : '';
  const bookable = (r.finding_ids||[]).filter(id => ENTRIES.some(x => x.finding_id === id)).length;
  return '<tr class="evrow"><td colspan="'+span+'"><div class="evbox" style="max-width:none">'+
    (flags ? '<div class="vflags">'+flags+'</div>' : '')+
    ((r.by_coding||[]).length ? codingTable(t, r, P)
      : '<div class="vgrids">'+gridHTML(r.by_account, 'account', P)+gridHTML(r.by_department, 'department', P)+'</div>')+
    plan+linesHTML(t, r, (r.lines_period || P.current)+' lines')+
    vendorDraft(t, r)+
    '<div style="margin-top:var(--spacing-md)">'+outcomeHTML(t, r, r.owner, bookable)+'</div>'+
    '</div></td></tr>';
}
function vendorDraft(t, r){
  const v = (DR.vendors||{})[r.vendor]; if (!v) return '';
  const key = rowKeyOf(t, r), d = rowDec[key] || {};
  const used = d.outcome === v.recommend && d.note === v.text;
  if (d.outcome === 'reclass') return draftBlock('Suggests '+OUT_LABEL[v.recommend],
    v.note + (v.text ? '\n' + v.text : ''), '<span class="secondary">The row is decided line by line</span>');
  return draftBlock('Suggests '+OUT_LABEL[v.recommend],
    v.note + (v.text ? '\n' + (v.recommend==='question' ? 'Question: ' : v.recommend==='entry' ? 'Entry: ' : 'Reason: ') + v.text : ''),
    used ? '<span class="st done">In use</span>'
         : '<button class="fxact" data-usevdraft="'+esc(key)+'">Use this</button>');
}
/* A payroll row settles the same way: read the lines, then clear it, ask, or
   record the entry. */
/* Why a department is flagged against UKG and what to do, in its own figures. */
function payrollWhy(t, r){
  const P = t.periods.current, n = r.headcount || 0, ppl = n+' '+(n===1?'person':'people');
  const big = r.variance != null && Math.abs(r.variance) >= fixAt;
  if (r.status === 'not_in_hris') return {label:'No one in UKG',
    why:r.department+' has '+money(r.amount)+' of '+P+' salaries. UKG places no one in it.',
    do:'Ask payroll which department these people belong to. Reclass the lines to that department.'};
  if (r.status === 'not_in_ledger') return {label:'No salary booked',
    why:'UKG places '+ppl+' in '+r.department+'. The ledger has no '+P+' salary for it.',
    do:'Ask payroll where their pay is booked, and choose Follow up.'};
  if (r.status === 'withheld') return {label:'Not compared',
    why:'UKG places fewer than 3 people in '+r.department+', so their pay is not shown here.',
    do:'Ask payroll to confirm the total, and choose Cleared.'};
  if (!big) return null;
  const hi = r.variance > 0;
  return {label: hi ? 'Ledger higher than UKG' : 'Ledger lower than UKG',
    why:P+' salaries for '+r.department+' are '+money(r.amount)+'. UKG monthly pay for its '+ppl+' is '+
      money(r.hris)+'. The ledger is '+money(Math.abs(r.variance))+(hi?' higher.':' lower.'),
    do: hi ? 'Read the salary lines. If a line belongs to another department, reclass it. '+
             'If the difference is real, such as a bonus or back pay, choose Cleared and say why.'
           : 'Check whether some of this pay is booked to another department. If it is, reclass it there. '+
             'If the difference is real, choose Cleared and say why.'};
}
function payrollPanel(t, r, span){
  const w = payrollWhy(t, r);
  return '<tr class="evrow"><td colspan="'+span+'"><div class="evbox">'+
    (w ? '<div class="vflags"><div class="vflag needs"><div class="vfh"><b>'+esc(w.label)+'</b></div>'+
      '<p>'+esc(w.why)+'</p><p class="secondary">'+esc(w.do)+'</p></div></div>' : '')+
    linesHTML(t, r, 'Salary lines')+
    '<div style="margin-top:var(--spacing-md)">'+outcomeHTML(t, r, r.department, 0)+'</div>'+
    '</div></td></tr>';
}
function rowStatus(t, r, n){
  const key = rowKeyOf(t, r), d = rowDec[key] || {};
  if (d.outcome === 'reclass'){
    /* Each kind of line outcome once, with its count, and what is still open. */
    const los = lineScope(r, key).map(i => lineOutcome(key, i));
    const nrc = rowReclass(key).length, open = los.filter(x => !lineDone(x)).length;
    const parts = nrc ? [nrc+' line'+(nrc===1?'':'s')+' reclassed'] : [];
    LINE_OUTCOMES.forEach(o => { const c = los.filter(x => x && x.outcome === o[0] && lineDone(x)).length;
      if (c) parts.push(o[1]+' '+c); });
    if (open) parts.push(open+' line'+(open===1?'':'s')+' open');
    return '<span class="st slot '+(open?'needs':'done')+'">'+esc(parts.join(' · '))+'</span>';
  }
  if (rowDone(key)) return '<span class="st slot done">'+esc(OUT_LABEL[d.outcome]+
    (d.outcome === 'question' && r.owner ? ' · '+r.owner : ''))+'</span>';
  if (d.outcome) return '<span class="st slot needs">'+esc(OUT_LABEL[d.outcome])+', needs a note</span>';
  return null;
}

/* Text fields fit their text. `field-sizing:content` does this natively; this
   covers every browser that does not support it yet. */
function grow(el){
  if(!el || !el.offsetParent) return;
  el.style.height = 'auto';
  el.style.height = (el.scrollHeight + el.offsetHeight - el.clientHeight) + 'px';
}
const growAll = root => (root || document).querySelectorAll('textarea').forEach(grow);

/* The status word and the row's actions, one line, one height. */
function stateOf(f){
  const d = decisions[f.finding_id] || {};
  /* Undecided and under the threshold is counted, not queued: the same rule the
     queue and the rail apply, so every count on the page agrees. */
  if (!d.verdict) return isAbove(f) ? {cls:'needs', text:'Decision needed'}
                                    : {cls:'', text:'Under '+money0(fixAt)};
  if (!decided(f.finding_id)) return {cls:'needs', text: VERDICTS[d.verdict]+', needs a reason'};
  return {cls:'done', text: VERDICTS[d.verdict]};
}

/* The evidence panel, under its row. The same fields the detail pane shows,
   plus the decision and its reason, so a line can be settled from the table
   without going anywhere. Decisions land in the same store as the queue's,
   because they are the same decision reached by a different route. */
/* A row with no finding still opens: to the ledger lines behind it, largest
   first, with what each line says was bought. */
function linesRow(r, span){
  const dt = r.detail || {};
  const items = dt.items || [];
  if(!items.length) return '';
  return '<tr class="evrow"><td colspan="'+span+'"><div class="evbox">'+
    '<h3 style="margin:0 0 var(--spacing-2xs)">Ledger lines'+
      (dt.count>items.length?' <span class="secondary">· largest '+items.length+' of '+dt.count+'</span>':'')+'</h3>'+
    '<table class="evtxn"><tbody>'+items.map(l=>
      '<tr><td class="mono">'+esc(l.date)+'</td><td class="mono">'+docHTML(l.document)+'</td>'+
      '<td>'+esc(l.vendor)+'</td><td>'+esc(l.text||'')+'</td>'+
      '<td>'+esc(acctText(l.account))+'</td><td>'+esc(l.department||'')+'</td>'+
      '<td class="num">'+money(l.amount)+'</td></tr>').join('')+'</tbody></table>'+
    '</div></td></tr>';
}

/* A variance, drilled the way a reviewer does it by hand: the departments
   behind the move, then what changed inside them by vendor, then the lines
   from both months. Clicking a department narrows the list; clicking a change
   opens its lines. The draft states those figures, for the reviewer to edit. */
const fluxDrill = {};
function drillOf(code){ return fluxDrill[code] = fluxDrill[code] || {dept:null, open:null}; }
function varianceDraft(f){
  const mv = f.movers || [], top = mv.slice(0, 3);
  const dir = v => v >= 0 ? 'up' : 'down';
  if (f.rule_id === 'F1.VARIANCE'){
    const d = f.mom_variance || 0;
    return (d >= 0 ? 'Up ' : 'Down ')+money0(Math.abs(d))+' from '+(M.prior_period||'the prior month')+'. '+
      (top.length ? top.map(m => m.vendor+' ('+m.department+') '+dir(m.change)+' '+money0(Math.abs(m.change))).join('; ')+'.' : '');
  }
  const d = f.budget_variance || 0;
  const deps = (f.departments||[]).map(x => [x.department, x.actual - x.budget])
    .filter(x => Math.abs(x[1]) >= 0.005).sort((a,b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 2);
  return (d >= 0 ? 'Over plan by ' : 'Under plan by ')+money0(Math.abs(d))+'. '+
    deps.map(x => x[0]+' '+(x[1] >= 0 ? 'over' : 'under')+' by '+money0(Math.abs(x[1]))).join('; ')+
    (top.length ? '. Largest vendors this month: '+top.map(m => m.vendor+' '+money0(m.actual)).join('; ')+'.' : '.');
}
function variancePanel(f){
  const code = f.account_code, st = drillOf(code), F1 = f.rule_id === 'F1.VARIANCE';
  const deps = (f.departments||[]).filter(x => Object.keys(x).some(k => k!=='department' && Math.abs(x[k]||0) >= 0.005));
  const cols = F1 ? [['prior', M.prior_period || 'Prior'], ['actual', M.period]] : [['actual', M.period], ['budget', 'Plan']];
  const chg = x => F1 ? x.actual - x.prior : x.actual - x.budget;
  const depTbl = deps.length > 1
    ? '<h5>By department</h5>'+
      '<table class="evtxn"><thead><tr><th>Department</th>'+cols.map(c=>'<th class="num">'+esc(c[1])+'</th>').join('')+
      '<th class="num">'+(F1?'Change':'Against plan')+'</th></tr></thead><tbody>'+
      deps.slice(0, 10).map(x => '<tr class="pick'+(st.dept===x.department?' sel':'')+'" data-fdep="'+esc(code)+'" data-d="'+
        esc(x.department)+'"><td>'+esc(x.department)+'</td>'+cols.map(c=>'<td class="num">'+acct0(x[c[0]]||0)+'</td>').join('')+
        '<td class="num'+(Math.abs(chg(x)) >= fixAt ? ' over' : '')+'">'+acct0(chg(x))+'</td></tr>').join('')+'</tbody></table>'
    : '';
  const mv = (f.movers||[]).map((m, i) => Object.assign({i:i}, m)).filter(m => !st.dept || m.department === st.dept);
  const mvTbl = mv.length
    ? '<h5>'+(F1 ? 'What changed' : 'Vendors this month')+(st.dept ? ' in '+esc(st.dept) : '')+
      '</h5><table class="evtxn"><thead><tr>'+
      (st.dept ? '' : '<th>Department</th>')+'<th>Vendor</th>'+
      (F1 ? '<th class="num">'+esc(M.prior_period||'Prior')+'</th><th class="num">'+esc(M.period)+'</th><th class="num">Change</th>'
          : '<th class="num">'+esc(M.period)+'</th>')+'</tr></thead><tbody>'+
      mv.map(m => {
        const open = st.open === m.i;
        let h = '<tr class="pick'+(open?' sel':'')+'" data-fmov="'+esc(code)+'" data-i="'+m.i+'">'+
          (st.dept ? '' : '<td>'+esc(m.department)+'</td>')+'<td>'+esc(m.vendor)+'</td>'+
          (F1 ? '<td class="num">'+acct0(m.prior)+'</td><td class="num">'+acct0(m.actual)+'</td>'+
                '<td class="num'+(Math.abs(m.change) >= fixAt ? ' over' : '')+'">'+acct0(m.change)+'</td>'
              : '<td class="num">'+acct0(m.actual)+'</td>')+'</tr>';
        const span = (st.dept ? 1 : 2) + (F1 ? 2 : 0);
        if (open) h += (m.lines||[]).map(l => '<tr class="sub"><td colspan="'+span+'" class="ltext"><span class="per">'+
          esc((l.period||'').replace(/ \d{4}$/,''))+'</span>'+
          (l.description ? esc(l.description) : '<span class="blank">No description. Open the invoice.</span>')+
          ' <span class="secondary">'+esc(l.date)+' · '+docHTML(l.document_number)+'</span></td>'+
          '<td class="num">'+money(l.amount)+'</td></tr>').join('');
        return h;
      }).join('')+'</tbody></table>'
    : '';
  const hasNote = !!(fluxNotes[code]||'').trim();
  return depTbl + mvTbl + '<div class="acts">'+
    (hasNote ? '' : '<button class="fxact" data-draft="'+esc(f.finding_id)+'">Draft commentary</button>')+
    '<button class="fxact'+(raised[code]?' on':'')+'" data-raise="'+esc(code)+'">'+(raised[code]?'Entry raised':'Raise entry')+'</button></div>';
}

function adjustmentDraft(f){
  const v = (DR.adjustments||{})[f.finding_id]; if (!v) return '';
  const d = decisions[f.finding_id] || {};
  const used = d.verdict === v.recommend && d.note === v.note;
  return draftBlock('Suggests '+VERDICTS[v.recommend], v.note,
    used ? '<span class="st done">In use</span>'
         : '<button class="fxact" data-useadraft="'+esc(f.finding_id)+'">Use this</button>');
}
function evidenceRow(r, span){
  const f = D.findings.find(x=>x.finding_id===r.finding_id);
  if(!f) return linesRow(r, span);
  const ev = f.evidence||{}, d = decisions[f.finding_id]||{};
  const kv = (k,v)=> v ? '<dt>'+k+'</dt><dd>'+escl(String(v).split(' · ').join('. '))+'</dd>' : '';
  const txns = f.transactions || (f.transaction ? [f.transaction] : []);
  /* The departments behind an account's move, largest first. */
  const deps = (f.departments||[]).filter(x => Object.keys(x).some(k => k!=='department' && Math.abs(x[k]||0) >= 0.005));
  const depCols = f.rule_id === 'F2.BUDGET' ? [['actual', M.period], ['budget', 'Plan']]
    : [['prior', M.prior_period || 'Prior'], ['actual', M.period]];
  const depTbl = deps.length > 1
    ? '<h5>By department</h5><table class="evtxn"><thead><tr><th>Department</th>'+
      depCols.map(c=>'<th class="num">'+esc(c[1])+'</th>').join('')+'<th class="num">Change</th></tr></thead><tbody>'+
      deps.slice(0, 8).map(x => {
        const ch = f.rule_id === 'F2.BUDGET' ? x.actual - x.budget : x.actual - x.prior;
        return '<tr><td>'+esc(x.department)+'</td>'+depCols.map(c=>'<td class="num">'+acct0(x[c[0]]||0)+'</td>').join('')+
          '<td class="num'+(Math.abs(ch) >= fixAt ? ' over' : '')+'">'+acct0(ch)+'</td></tr>';
      }).join('')+'</tbody></table>'
    : '';
  /* An expense report's name field is the employee who filed it. */
  const who = t => t.txn_type === 'Expense Report' ? 'Expense report' : (t.vendor_or_name || '');
  const txn = txns.slice(0,6).map(t=>
    '<tr><td class="mono">'+esc(t.date)+'</td><td>'+esc(who(t))+'</td>'+
    '<td>'+esc(acctText(t.account_code))+'</td><td>'+esc(t.department||'')+'</td>'+
    '<td class="num">'+money(t.amount)+'</td></tr>').join('');
  const ml = (r.model_lines||[]).map(l=>
    '<tr><td class="mono">'+esc(l.ref)+'</td><td>'+(l.vendor ? esc(l.vendor) : l.po ? poHTML(l.po) : 'No vendor, no PO')+'</td>'+
    '<td>'+esc(l.description||'')+'</td><td class="num">'+money(l.amount)+'</td></tr>').join('');
  const acts = ACTIONS(f).map(o=>
    '<button class="fxact'+(d.verdict===o[0]?' on':'')+'" aria-pressed="'+(d.verdict===o[0])+'" '+
    'data-decide-row="'+esc(f.finding_id)+'" data-verdict="'+o[0]+'">'+o[1]+'</button>').join('');
  const need = noteRequired(f, d.verdict);
  return '<tr class="evrow"><td colspan="'+span+'"><div class="evbox">'+
    /* No title: the row above already names the vendor, account and amount. */
    /* A block derived from the finding's own wording repeats the row and the
       explanation below, so it shows only where there is no explanation. */
    (isVariance(f) || (correctionIsDerived(f) && (V.explain||{})[f.finding_id]) ? '' : correctionHTML(f))+
    /* Why it was raised, what to do, and its limit, in plain sentences with this
       finding's own figures. The engines' own wording is the fallback for a run
       whose schedules step did not write one. */
    (f.drafted ? draftBlock('Why this entry', f.recommendation, '') :
     isVariance(f) ? '' : (V.explain||{})[f.finding_id]
      ? '<dl class="kv">'+kv('Why flagged',V.explain[f.finding_id].why)+
          kv('What to do',V.explain[f.finding_id].do)+'</dl>'
      : '<dl class="kv">'+(correctionIsDerived(f)?'':kv('Observed',ev.observed)+kv('Expected',ev.expected))+
          kv('Basis',ev.basis)+kv('Proposed',f.recommendation)+'</dl>')+
    (ml?'<h5>Model lines</h5>'+
      '<table class="evtxn"><tbody>'+ml+'</tbody></table>':'')+
    (isVariance(f) && (f.movers||[]).length ? '' : depTbl+
      (txns.length > 1 ? '<h5>Largest lines</h5><table class="evtxn"><tbody>'+txn+'</tbody></table>' : ''))+
    (isVariance(f)
      /* A variance is explained in the row's commentary, so the panel carries
         the drill-down, a draft, and the way to raise an entry. */
      ? variancePanel(f)
      : adjustmentDraft(f)+'<div class="acts">'+acts+
          (d.verdict?'<span class="evstate">'+VERDICTS[d.verdict]+'</span>':'')+'</div>'+
        '<textarea class="cmt" data-rownote="'+esc(f.finding_id)+'" rows="1" aria-label="'+esc(noteLabel(f))+'" '+
          'placeholder="'+esc(noteLabel(f)+(need?' (required)':''))+'">'+esc(d.note||'')+'</textarea>')+
    '</div></td></tr>';
}

/* Accounting format: whole dollars, negatives in parentheses. */
const acct0 = v => (v==null) ? '' :
  (v<0?'(':'')+'$'+Math.abs(Math.round(v)).toLocaleString('en-US')+(v<0?')':'');
const acct2 = v => (v==null||v===0) ? '' :
  (v<0?'(':'')+'$'+Math.abs(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})+(v<0?')':'');

/* The flux pack's own search and flagged-only switch, shared by both comparisons. */
/* Unflagged lines start hidden; the button shows them. */
let fxQ = '', fxOnly = true;
function renderTable(){
  if(!TABLE) return;
  const fo = $('#fxonly');
  if (fo){ fo.setAttribute('aria-pressed', String(fxOnly)); fo.textContent = fxOnly ? 'Show unflagged lines' : 'Hide unflagged lines'; }
  const c = TABLE.comparisons.find(x=>x.id===cmp) || TABLE.comparisons[0];
  /* No unflagged lines, no switch. */
  if (fo) fo.hidden = !TABLE.sections.some(sec => sec.rows.some(r => r[c.var] != null && Math.abs(r[c.var]||0) < fixAt));
  const mom = c.id === 'mom';
  /* Month over month reads as three months, so a swing that reverses shows as
     one, and the same month last year sits beside it for context. */
  const trend = mom && !!TABLE.trend_period;
  const yoy = mom && TABLE.comparisons.find(x => x.id === 'yoy');
  /* Under each change, the same month last year, named once in the header. */
  const yoyPeriod = yoy ? yoy.label.replace(/^vs /, '') : '';
  const vint = /\(([^)]+)\)/.exec(c.label);
  const baseHead = c.id==='budget'
    ? 'Plan'+(vint?'<span class="sub2">'+esc(vint[1])+'</span>':'')
    : esc(c.label.replace(/^vs /,''));
  const span = 8 + (trend?1:0) + (yoy?1:0);
  $('#fluxtbl').innerHTML =
    '<colgroup><col class="c-acct">'+(trend?'<col class="c-num">':'')+
    '<col class="c-num"><col class="c-num"><col class="c-num"><col class="c-pct">'+
    (yoy?'<col class="c-yoy">':'')+'<col class="c-act"><col class="c-btn"><col class="c-cmt"></colgroup>'+
    '<thead><tr><th>Account</th>'+(trend?'<th class="num">'+esc(TABLE.trend_period)+'</th>':'')+
    (mom ? '<th class="num">'+baseHead+'</th><th class="num">'+esc(M.period)+'</th>'
         : '<th class="num">'+esc(M.period)+'</th><th class="num">'+baseHead+'</th>')+
    '<th class="num">$ var</th><th class="num">% var</th>'+
    (yoy?'<th class="num">'+esc(yoy.label)+'<span class="sub2">'+esc(yoyPeriod)+' actual</span></th>':'')+'<th>Status</th><th></th><th>Commentary</th>'+
    '</tr></thead><tbody id="fluxbody"></tbody>';
  $('#fluxtbl').classList.toggle('trend', !!(trend || yoy));
  let html='';
  TABLE.sections.forEach(sec=>{
    const rows = sec.rows.filter(r=>r[c.var]!==null && r[c.var]!==undefined)
      .filter(r => !fxOnly || Math.abs(r[c.var]||0) >= fixAt)
      .filter(r => !fxQ || (r.account_code+' '+acctText(r.account_code)+' '+(r.account_leaf||'')+' '+sec.label)
                            .toLowerCase().indexOf(fxQ.toLowerCase()) > -1);
    if(!rows.length) return;
    const sum = k => rows.reduce((s,r)=>s+(r[k]||0),0);
    const pair = mom
      ? '<th class="num">'+acct0(sum(c.base))+'</th><th class="num">'+acct0(sum('actual'))+'</th>'
      : '<th class="num">'+acct0(sum('actual'))+'</th><th class="num">'+acct0(sum(c.base))+'</th>';
    html += '<tr class="sec"><th>'+esc(sec.label)+'<span class="n">'+rows.length+'</span></th>'+
      (trend?'<th class="num">'+acct0(sum('prior2'))+'</th>':'')+pair+
      '<th class="num">'+acct0(sum(c.var))+'</th><th></th>'+
      (yoy?'<th class="num">'+acct0(sum('yoy_var'))+'</th>':'')+'<th colspan="3"></th></tr>';
    rows.forEach(r=>{
      const v = r[c.var], pctv = r[c.pct];
      const fid = c.id==='budget' ? r.budget_finding : r.mom_finding;
      /* Over the reviewer's own threshold, so the flag moves when they move it. */
      const flag = Math.abs(v) >= fixAt;
      const explained_ = explained(r.account_code), drafted = isDraftNote(r.account_code);
      const isOpen = openRow === r.account_code;
      const act = fid
        ? '<button class="fxact'+(isOpen?' on':'')+'" data-expand="'+esc(r.account_code)+'" '+
          'aria-expanded="'+isOpen+'">Evidence <span class="caret" aria-hidden="true">&rsaquo;</span></button>'
        : '<button class="fxact'+(raised[r.account_code]?' on':'')+'" data-raise="'+
          esc(r.account_code)+'">'+(raised[r.account_code]?'Entry raised':'Raise entry')+'</button>';
      const st = '<span class="st slot'+(flag?(explained_?' done':' needs'):'')+'" data-st="'+
          esc(r.account_code)+'"'+(flag?'':' data-noflag="1"')+'>'+
          (flag?(explained_?'Explained':drafted?'Draft to review':'Needs commentary'):'')+'</span>';
      html += '<tr class="'+(flag&&!explained_?'needs ':'')+(fid?'xp ':'')+(isOpen?'open':'')+'"'+
        (fid?' data-fx="'+esc(r.account_code)+'"':'')+'>'+
        '<td>'+acctHTML(r.account_code)+'</td>'+
        (trend?'<td class="num">'+acct0(r.prior2||0)+'</td>':'')+
        (mom
          ? '<td class="num">'+acct0(r[c.base]||0)+'</td><td class="num">'+acct0(r.actual)+'</td>'
          : '<td class="num">'+acct0(r.actual)+'</td><td class="num">'+acct0(r[c.base]||0)+'</td>')+
        '<td class="num'+(flag?' over':'')+'">'+acct0(v)+'</td>'+
        '<td class="num">'+(pctv===null||pctv===undefined?'':pctv+'%')+'</td>'+
        (yoy?'<td class="num">'+acct0(r.yoy_var||0)+'<span class="sub2">'+esc(acct0(r.prior_year||0))+'</span></td>':'')+
        '<td>'+st+'</td><td>'+act+'</td>'+
        '<td><textarea class="cmt" data-cmt="'+esc(r.account_code)+'" rows="1" '+
          'placeholder="Explain the movement">'+esc(fluxNotes[r.account_code]||'')+'</textarea>'+
          (drafted ? '<span class="drafted">'+(isPendingNote(r.account_code) ? 'From a record saved before 1.8.7' : 'Drafted by Claude')+' <button class="fxact" data-accept="'+
            esc(r.account_code)+'">Accept</button></span>' : '')+'</td>'+
        '</tr>';
      if (isOpen) html += evidenceRow({finding_id: fid}, span);
    });
  });
  $('#fluxbody').innerHTML = html;
  const all = TABLE.sections.reduce((a,s)=>a.concat(s.rows),[]);
  const flagged = all.filter(r=>Math.abs(r[c.var]||0) >= fixAt);
  /* Plan against actual reads two ways: by account here, by department on the
     schedule beside it. Accounts the forecast does not plan are named once. */
  const seg = $('#fluxseg'); if (seg) seg.hidden = c.id !== 'budget';
  const al = $('#fluxalert');
  if (al){
    const none = all.filter(r => r.budget==null && Math.abs(r.actual||0) >= 0.005)
                    .sort((a,b)=>Math.abs(b.actual)-Math.abs(a.actual));
    al.hidden = true;
  }
  growAll($('#fluxbody'));
}

/* ---------- schedules ----------
   The period laid out as a controller reads it: every line, sectioned, with
   subtotals, and the lines needing action marked against the reviewer's own
   threshold. The tables arrive in the run; this only lays them out. */
const VTABLES = (V.tables || []);
let vt = VTABLES.length ? VTABLES[0].id : null;
const vtState = {};
const vtS = id => (vtState[id] = vtState[id] || {q:'', only:true, blank:false, shut:null, open:null});

/* ---------- the updated UI ----------
   Built with --layout ui-update: the updated page set over the same decisions.
   The GL vendors split across his pages, each vendor on one page only, so no row
   is counted twice. Findings with no page of their own sit under the page that
   holds them: the forecast tie-out and dropped vendors on Adjustments. The
   ledger checks are not in the updated UI. */
const LAYOUT = window.__SERIF_LAYOUT__ || 'standard';
const CH = window.__SERIF_UPDATE__ || {pre: {}, extra: []};
let vtf = null;
function VF_OF(r){
  const ids = (r.flags||[]).map(f => f.id);
  if (ids.indexOf('capital') > -1) return 'capex';
  if (ids.indexOf('prepaid') > -1) return 'prepaid';
  if (ids.some(i => i !== 'new')) return 'coding';
  if (ids.indexOf('new') > -1) return 'new';
  return 'clear';
}
const inVf = (r, vf) => !vf || VF_OF(r) === vf;
/* The findings a page carries below its own table, as {page, ids, table}. */
function chExtra(){
  if (LAYOUT !== 'ui-update') return [];
  return (CH.extra || []).map(x => {
    const t = VTABLES.find(v => v.id === x.table); if (!t) return null;
    const ids = [];
    t.sections.forEach(s => s.rows.forEach(r => { if (r.finding_id && ids.indexOf(r.finding_id) < 0 &&
      (!x.no_entry || !hasEntry(r.finding_id))) ids.push(r.finding_id); }));
    /* A line with a proposed entry is counted with the entries, once. */
    return {page: x.page, title: x.title, table: t, ids, cnt: ids.filter(id => !hasEntry(id)), host: x.host};
  }).filter(Boolean);
}
const chExtraOf = label => chExtra().filter(x => x.page === label);
function chExtraHTML(host){
  return chExtra().filter(x => x.host === host).map(x => {
    const rows = [];
    x.table.sections.forEach(s => s.rows.forEach(r => { if (x.ids.indexOf(r.finding_id) < 0) return;
      const f = D.findings.find(y => y.finding_id === r.finding_id) || {};
      rows.push('<tr class="chxh" data-exk="'+esc(r.finding_id)+'"><td><b>'+esc(f.title || r.finding_id)+'</b></td>'+
        '<td class="num">'+acct0(amtOf(f))+'</td><td>'+rowStatus2(f)+'</td></tr>'+evidenceRow(r, 3)); }));
    if (!rows.length) return '';
    return '<h3 class="chsech">'+esc(x.title)+'</h3><div class="card schedwrap"><table class="sched"><colgroup><col style="width:62%">'+
      '<col style="width:14%"><col style="width:24%"></colgroup><tbody>'+rows.join('')+'</tbody></table></div>';
  }).join('');
}
function rowStatus2(f){
  const d = decisions[f.finding_id] || {};
  return decided(f.finding_id) ? '<span class="st done">'+esc(VERDICTS[d.verdict]||'Decided')+'</span>'
    : '<span class="st needs">'+(d.verdict ? esc(VERDICTS[d.verdict])+', needs a reason' : 'Needs a decision')+'</span>';
}
function renderChExtras(){
  const a = $('#adjextra'); if (a) a.innerHTML = chExtraHTML('adjextra');
  const v = $('#vtpost'); if (v) v.innerHTML = (vt === 'vendors' && vtf === 'coding') ? chExtraHTML('vtpost') : '';
}

/* The audit log: every decision recorded, newest first. */
function renderAudit(){
  const host = $('#audittbl'); if (!host) return;
  const items = decidedItems().filter(x => x.at || x.by).sort((a, b) => String(b.at||'').localeCompare(String(a.at||'')));
  $('#auditn').textContent = items.length ? plural(items.length, 'decision') : '';
  host.innerHTML = items.length ? '<thead><tr><th>Time</th><th>Reviewer</th><th>Page</th><th>Item</th><th>Decision</th><th>Detail</th></tr></thead><tbody>'+
    items.map(x => '<tr'+goAttr(x.go)+' class="xp"><td class="mono">'+esc(whenTxt(x.at))+'</td><td>'+esc(x.by||'')+'</td><td>'+esc(x.page||'')+
      '</td><td><b>'+esc(x.what||'')+'</b><span class="sub2">'+esc(x.sub||'')+'</span></td><td>'+esc(x.outcome||'')+'</td><td>'+esc(x.note||'')+'</td></tr>').join('')+'</tbody>'
    : '<tbody><tr><td class="secondary">No decisions recorded yet.</td></tr></tbody>';
}

/* The balance sheet flux: the NetSuite report, with commentary on each line. */
/* Unflagged is a move under the threshold that had no commentary when the page
   opened; a line given commentary stays on screen. */
let bsOnly = true;
const bsKept = new Set();
function renderBS(){
  const host = $('#bstbl'), B = CH.bs; if (!host || !B) return;
  const P = [B.period, B.prior, B.year_end, B.prior_year];
  const q = (($('#bsq')||{}).value || '').trim().toLowerCase();
  const keyOf = r => 'bs:'+(r.code ? r.code+(r.kind==='total'?':total':'') : r.name);
  const live = r => { const v = P.map(p => r.values[p] || 0); return v.some(x => Math.round(x)); };
  const flaggedBS = r => Math.abs((r.values[P[0]]||0) - (r.values[P[1]]||0)) >= fixAt || bsKept.has(keyOf(r)) || !!(fluxNotes[keyOf(r)]||'').trim();
  B.rows.forEach(r => { if ((fluxNotes[keyOf(r)]||'').trim()) bsKept.add(keyOf(r)); });
  const quiet = B.rows.filter(r => r.kind !== 'head' && live(r) && !flaggedBS(r)).length;
  const sw = $('#bsonly'); if (sw){ sw.hidden = !quiet; sw.textContent = bsOnly ? 'Show unflagged lines' : 'Hide unflagged lines';
    sw.classList.toggle('active', bsOnly); sw.setAttribute('aria-pressed', String(bsOnly)); }
  /* A heading shows only over lines that show: held until a line under it is drawn. */
  const shows = r => r.kind !== 'head' && live(r) && (!q || r.name.toLowerCase().indexOf(q) > -1) && (!bsOnly || flaggedBS(r));
  let pending = [];
  let html = '<colgroup><col style="width:26%"><col style="width:10%"><col style="width:10%"><col style="width:10%"><col style="width:10%"><col style="width:10%"><col style="width:24%"></colgroup>'+
    '<thead><tr><th>Account</th><th class="num">'+esc(B.period)+'</th><th class="num">'+esc(B.prior)+'</th><th class="num">Change</th>'+
    '<th class="num">vs. '+esc(B.year_end)+'</th><th class="num">vs. '+esc(B.prior_year)+'</th><th>Commentary</th></tr></thead><tbody>';
  B.rows.forEach((r, i) => {
    const pad = 'padding-left:calc(var(--spacing-sm) + '+(r.depth*0.9)+'em)';
    if (r.kind === 'head'){ pending = pending.filter(h => h.depth < r.depth); pending.push(r); return; }
    if (r.kind === 'total') pending = pending.filter(h => h.depth < r.depth);
    if (!shows(r)) return;
    pending.forEach(h => { html += '<tr class="sec"><th colspan="7" style="padding-left:calc(var(--spacing-sm) + '+(h.depth*0.9)+'em)">'+esc(h.name)+'</th></tr>'; });
    pending = [];
    const v = P.map(p => r.values[p] || 0);
    const ch = v[0]-v[1], key = 'bs:'+(r.code ? r.code+(r.kind==='total'?':total':'') : r.name);
    html += '<tr'+(r.kind==='total'?' class="tot"':'')+'><td style="'+pad+'">'+(r.kind==='total'?'<b>'+esc(r.name)+'</b>':esc(r.name))+'</td>'+
      '<td class="num">'+acct0(v[0])+'</td><td class="num">'+acct0(v[1])+'</td>'+
      '<td class="num'+(Math.abs(ch) >= fixAt ? ' bsover' : '')+'">'+acct0(ch)+'</td><td class="num">'+acct0(v[0]-v[2])+'</td><td class="num">'+acct0(v[0]-v[3])+'</td>'+
      '<td><textarea class="cmt" rows="1" data-bsn="'+esc(key)+'" aria-label="Commentary on '+esc(r.name)+'" placeholder="Commentary">'+esc(fluxNotes[key]||'')+'</textarea></td></tr>';
  });
  host.innerHTML = html+'</tbody>';
  growAll(host);
}

/* Sections that are context rather than work start folded, so the page opens
   on the lines needing a look. They are one click away and still totalled. */
const FOLDED = {vendors:['clear', 'stopped']};

function codingHTML(list, max){
  if(!list || !list.length) return '<span class="secondary">-</span>';
  const one = c => '<div class="cd">'+acctHTML(c.account)+
    '<span class="sub2">'+esc(c.department||'No department')+
    (c.amount!=null?' · '+acct0(c.amount):'')+
    (c.lines?' · '+c.lines+' line'+(c.lines===1?'':'s'):'')+'</span></div>';
  max = max || 2;
  if(list.length <= max) return list.map(one).join('');
  return list.slice(0,max).map(one).join('')+
    '<details class="more"><summary>'+(list.length-max)+' more</summary>'+
    list.slice(max).map(one).join('')+'</details>';
}
const stHTML = (text, needs) => '<span class="st slot'+(needs?' needs':'')+'">'+esc(text||'')+'</span>';
/* Evidence opens under its row, never on another page: the reader keeps their
   place in the schedule. */
const opens = r => !!r && (!!r.finding_id || !!((r.detail||{}).items||[]).length || !!(r.flags||[]).length);
const xpBtn = (r, label) => {
  if(!opens(r)) return '';
  const open = vtS(vt).open === r._k;
  return '<button class="fxact'+(open?' on':'')+'" data-xk="'+esc(r._k)+'" aria-expanded="'+open+'">'+
    (label || (r.finding_id?'Evidence':'Lines'))+' <span class="caret" aria-hidden="true">&rsaquo;</span></button>';
};

/* Per schedule: its columns, which rows need action at the current threshold,
   and the status word. Each column says how to draw a row and, where it carries
   money, how to total a section. */
const VT = {
  /* One row per vendor billed this month: what it was, where it was coded, the
     three months, and the first reason to look. Everything else opens under it. */
  vendors: t => {
    const P = t.periods;
    return {
    btn: 'Details',
    needs: r => rowNeeds(t, r),
    size: r => rowSize(t, r),
    done: r => rowDone(rowKeyOf(t, r)),
    panel: (r, span) => vendorPanel(t, r, span),
    cols: [
      {h:'Vendor', w:'23%', td:r=>{
        const top = ((r.detail||{}).items||[]).find(l => l.text);
        const blank = (r.detail||{}).blank || 0;
        return '<b>'+esc(r.vendor)+'</b>'+
          (top ? '<span class="sub2">'+esc(top.text.length > 72 ? top.text.slice(0, 70)+'…' : top.text)+'</span>' : '')+
          (blank ? '<span class="sub2 reqd">'+blank+' line'+(blank===1?'':'s')+' with no description</span>' : '');
      }},
      {h:'Coded to in '+P.current, w:'23%', td:r=>{
        const acc = (r.by_account||[]).filter(a => Math.abs(a.current||0) >= 0.005);
        const dep = (r.by_department||[]).filter(a => Math.abs(a.current||0) >= 0.005).map(a => a.department);
        if (!acc.length) return '<span class="secondary">Nothing this month</span>';
        return acc.slice(0, 2).map(a => acctHTML(a.account)).join('')+
          (acc.length > 2 ? '<span class="sub2">'+(acc.length-2)+' more account'+(acc.length===3?'':'s')+'</span>' : '')+
          '<span class="sub2">'+esc(dep.slice(0, 3).join(', ')+(dep.length > 3 ? ', '+(dep.length-3)+' more' : ''))+'</span>';
      }},
    ].concat(P.prior2 ? [{h:P.prior2, w:'9%', num:true, td:r=>acct0(r.prior2), sub:s=>acct0(s.prior2_total)}] : []).concat([
      {h:P.prior, w:P.prior2?'9%':'13%', num:true, td:r=>acct0(r.prior), sub:s=>acct0(s.prior_total)},
      {h:P.current, w:P.prior2?'9%':'14%', num:true, td:r=>acct0(r.amount), sub:s=>acct0(s.total)},
      {h:'Status', w:'27%', td:(r,n)=>{
        const of = openFlags(r);
        const st = rowStatus(t, r, n) || (of.length
          ? '<span class="ststack">'+of.map(x => '<span class="st'+(n?' needs':'')+'" data-tip="'+
              esc(x.label+' '+acct0(x.amount))+'">'+esc(x.label)+'</span>').join('')+'</span>'
          : '<span class="st slot">'+((r.flags||[]).length ? 'Decided' : '')+'</span>');
        const sug = !rowDone(rowKeyOf(t, r)) && (DR.vendors||{})[r.vendor];
        return '<div class="stc">'+st+(sug ? '<span class="sub2">Claude suggests '+
          esc(OUT_LABEL[sug.recommend])+'</span>' : '')+'</div>';
      }},
    ])};
  },
  dept_plan: t => ({
    needs: r => r.plan!=null && Math.abs(r.variance) >= fixAt,
    size: r => r.plan!=null ? Math.abs(r.variance) : 0,
    cols: [
      {h:'Account', w:'30%', td:r=>acctHTML(r.account, true)},
      {h:'Plan ('+t.periods.plan+')', w:'13%', num:true,
       td:r=>r.plan==null?'<span class="secondary">-</span>':acct0(r.plan), sub:s=>acct0(s.plan_total)},
      {h:t.periods.current+' actual', w:'13%', num:true, td:r=>acct0(r.amount), sub:s=>acct0(s.total)},
      {h:'Variance', w:'13%', num:true,
       td:(r,n)=>r.variance==null?'<span class="secondary">-</span>':'<span class="'+(n?'over':'')+'">'+acct0(r.variance)+'</span>',
       sub:s=>acct0(s.variance)},
      {h:'% var', w:'8%', num:true, td:r=>r.pct==null?'':r.pct+'%', sub:s=>s.pct==null?'':s.pct+'%'},
      {h:'Status', w:'23%', td:(r,n)=>'<div class="stc">'+stHTML(
        r.status==='no_plan'?'No plan line': r.status==='no_spend'?'Planned, nothing posted':
        n ? (r.variance>0?'Over plan':'Under plan') : 'Within '+money0(fixAt), n)+'</div>'},
    ]}),
  model_tie: t => ({
    needs: r => openAt(r.finding_id), evidence:true,
    cols: [
      {h:'Account', w:'20%', td:r=>acctHTML(r.account, true)},
      {h:'Department', w:'10%', td:r=>esc(r.department)},
      {h:'Ledger', w:'9%', num:true, td:r=>acct0(r.ledger), sub:s=>acct0(s.rows.reduce((a,r)=>a+r.ledger,0))},
      {h:'Model', w:'9%', num:true, td:r=>acct0(r.model), sub:s=>acct0(s.rows.reduce((a,r)=>a+r.model,0))},
      {h:'Difference', w:'9%', num:true, td:(r,n)=>'<span class="over">'+acct0(r.difference)+'</span>',
       sub:s=>acct0(s.total)},
      /* The forecast workbook's own wording, quoted and sourced to its cell, so it
         cannot be read as a label this console applied. */
      {h:'Forecast line note', w:'19%', td:r=>{
        const notes = (r.model_lines||[]).filter(l=>l.description);
        return (notes.length
          ? notes.map(l=>'&ldquo;'+esc(l.description)+'&rdquo;<span class="sub2">Forecast workbook, '+
              esc(l.ref)+'</span>').join('')
          : '')+
          (r.overlay?'<span class="olay">Manual overlay, no vendor or PO</span>':'');
      }},
      {h:'Decision', w:'24%', td:(r)=>decisionCell(r)},
    ]}),
  accrual: t => ({
    needs: r => openAt(r.finding_id), evidence:true,
    cols: [
      {h:'Supplier', w:'15%', td:r=>'<b>'+esc(r.vendor)+'</b><span class="sub2">'+
        (r.method==='pattern' ? 'From the billing pattern' : (r.po_numbers||[]).map(poHTML).join(', '))+'</span>'},
      {h:'Debit', w:'17%', td:r=>acctHTML(r.account)},
      {h:'Credit', w:'16%', td:r=>acctHTML(r.credit_account)},
      {h:'Department', w:'10%', td:r=>r.department?esc(r.department):(((jeEdits[r.finding_id]||{}).lines||[]).find(l=>Number(l.debit)>0&&l.department)||{}).department
          ? esc(((jeEdits[r.finding_id]||{}).lines||[]).find(l=>Number(l.debit)>0&&l.department).department)
          : '<span class="st needs">Set the department in Journal Entries</span>'},
      {h:'Accrue', w:'9%', num:true, td:r=>acct2(r.amount), sub:s=>acct2(s.total)},
      {h:'Reverses', w:'9%', td:r=>'<span class="nowrap">'+esc(r.reverses)+'</span>'},
      {h:'Decision', w:'24%', td:(r)=>decisionCell(r)},
    ]}),
  /* One line per finding, sectioned by what the rule tests. */
  findings: t => ({
    needs: r => openAt(r.finding_id), evidence:true,
    cols: [
      {h:'Vendor', w:'16%', td:r=>'<b>'+esc(r.vendor||'')+'</b>'+docsHTML(r.documents)},
      {h:'Finding', w:'30%', td:r=>escn(r.what)},
      {h:'Account', w:'17%', td:r=>r.account?acctHTML(r.account):
        '<span class="secondary">'+(r.accounts?r.accounts+' accounts':'-')+'</span>'},
      {h:'Department', w:'11%', td:r=>esc(r.department||'')},
      {h:'Amount', w:'10%', num:true, td:r=>acct0(r.amount)+'<span class="sub2">'+r.lines+
        ' line'+(r.lines===1?'':'s')+'</span>', sub:s=>acct0(s.total)},
      {h:'Decision', w:'16%', td:r=>decisionCell(r)},
    ]}),
  payroll_hris: t => {
    /* A department whose booked salaries sit well away from UKG's pay for its
       people: over the threshold and more than 15% apart. */
    const gap = r => r.variance!=null &&
      Math.abs(r.variance) >= 0.15*Math.max(Math.abs(r.hris||0), Math.abs(r.amount||0))
      ? Math.abs(r.variance) : (r.status==='not_in_hris' ? Math.abs(r.amount||0) : 0);
    return {
    btn: 'Details',
    needs: r => !rowDone(rowKeyOf(t, r)) && gap(r) >= fixAt && gap(r) > 0,
    size: r => gap(r),
    done: r => rowDone(rowKeyOf(t, r)),
    panel: (r, span) => payrollPanel(t, r, span),
    cols: [
      {h:'Department', w:'22%', td:r=>'<b>'+esc(r.department)+'</b>'},
      {h:'People in UKG', w:'12%', num:true, td:r=>r.headcount?String(r.headcount):'<span class="secondary">None</span>'},
      {h:'UKG monthly pay', w:'14%', num:true, td:r=>r.hris==null?'<span class="secondary">-</span>':acct0(r.hris)},
      {h:t.periods.current+' salaries', w:'14%', num:true, td:r=>acct0(r.amount), sub:s=>acct0(s.total)},
      {h:'Difference', w:'12%', num:true, td:(r,n)=>r.variance==null?'<span class="secondary">-</span>':
        '<span class="'+(n?'over':'')+'">'+acct0(r.variance)+'</span>'},
      {h:'Status', w:'26%', td:(r,n)=>'<div class="stc">'+(rowStatus(t, r, n) || stHTML(
        r.status==='not_in_hris'?'No one in UKG':r.status==='not_in_ledger'?'No salary booked':
        r.status==='withheld'?'Not compared':
        gap(r)>=fixAt?(r.variance>0?'Ledger higher than UKG':'Ledger lower than UKG'):'In line', n))+
        '</div>'},
    ]};
  },
  prepaid: t => ({
    needs: r => !r.context && openAt(r.finding_id), evidence:true,
    cols: [
      {h:'Vendor', w:'15%', td:r=>'<b>'+esc(r.vendor)+'</b>'},
      {h:'What it was', w:'23%', td:r=>esc(r.what||'')},
      {h:'Expensed to', w:'16%', td:r=>r.from_account?acctHTML(r.from_account):'<span class="secondary">-</span>'},
      {h:'Would move to', w:'16%', td:r=>acctHTML(r.to_account)},
      {h:'Amount', w:'10%', num:true, td:r=>acct2(r.amount), sub:s=>acct2(s.total)},
      {h:'Decision', w:'20%', td:r=>r.context?'<span class="st">On the balance sheet</span>':decisionCell(r)},
    ]}),
  reclass: t => ({
    needs: r => openAt(r.finding_id), evidence:true,
    cols: [
      {h:'Issue', w:'18%', td:r=>'<b>'+esc(r.issue)+'</b>'+(r.vendor?'<span class="sub2">'+esc(r.vendor)+'</span>':'')},
      {h:'Account', w:'18%', td:r=>acctHTML(r.account)},
      {h:'Department', w:'10%', td:r=>esc(r.department||'')},
      {h:'Now', w:'12%', td:r=>escn(r.now)},
      {h:'Should be', w:'14%', td:r=>escn(r.should_be)},
      {h:'Amount', w:'10%', num:true, td:r=>acct2(r.amount), sub:s=>acct2(s.total)},
      {h:'Decision', w:'18%', td:r=>decisionCell(r)},
    ]}),
};

function deptList(list, max){
  if(!list || !list.length) return '<span class="secondary">-</span>';
  const one = c => '<div class="cd">'+esc(c.department)+'<span class="sub2">'+acct0(c.amount)+
    ' · '+c.lines+' line'+(c.lines===1?'':'s')+'</span></div>';
  if(list.length <= max) return list.map(one).join('');
  return list.slice(0,max).map(one).join('')+'<details class="more"><summary>'+(list.length-max)+
    ' more</summary>'+list.slice(max).map(one).join('')+'</details>';
}

/* Squarified treemap layout: fills rows along the shorter side and keeps each
   cell as close to square as the values allow, so areas compare fairly. */
function squarify(items, x, y, w, h){
  const total = items.reduce((s,i)=>s+i.v,0);
  if(!total) return [];
  const scale = (w*h)/total;
  const list = items.map(i=>Object.assign({}, i, {a:i.v*scale})).sort((p,q)=>q.a-p.a);
  const out = [];
  const worst = (row, side) => {
    const sum = row.reduce((s,r)=>s+r.a,0);
    const mx = Math.max.apply(null,row.map(r=>r.a)), mn = Math.min.apply(null,row.map(r=>r.a));
    return Math.max(side*side*mx/(sum*sum), (sum*sum)/(side*side*mn));
  };
  let row = [], rx = x, ry = y, rw = w, rh = h;
  const lay = (r) => {
    const sum = r.reduce((s,c)=>s+c.a,0);
    if(rw >= rh){
      const cw = sum/rh; let cy = ry;
      r.forEach(c=>{ const ch = c.a/cw; out.push(Object.assign(c,{x:rx,y:cy,w:cw,h:ch})); cy += ch; });
      rx += cw; rw -= cw;
    } else {
      const ch = sum/rw; let cx = rx;
      r.forEach(c=>{ const cw = c.a/ch; out.push(Object.assign(c,{x:cx,y:ry,w:cw,h:ch})); cx += cw; });
      ry += ch; rh -= ch;
    }
  };
  list.forEach(c=>{
    const side = Math.min(rw, rh);
    if(!row.length || worst(row.concat([c]), side) <= worst(row, side)) row.push(c);
    else { lay(row); row = [c]; }
  });
  if(row.length) lay(row);
  return out;
}

/* ---------- the close checklist ----------
   Every page in the rail, what is left on it at the current threshold, and what
   that is worth. It reads the same counts the pages do, so the two never
   disagree. */
function pageStatus(b){
  const view = b.dataset.view;
  if(view==='vtable'){
    const t = VTABLES.find(x=>x.id===b.dataset.vt); if(!t) return null;
    const spec = VT[t.kind](t);
    const rows = t.sections.reduce((a,s)=>a.concat(s.rows),[]).filter(r => !b.dataset.vf || inVf(r, b.dataset.vf));
    const gs = t.groups || (t.group ? [t.group] : null);
    if(gs){
      const fs = D.findings.filter(f=>gs.indexOf(groupOf(f)) > -1);
      const open = fs.filter(f=>openAt(f.finding_id));
      return {left:open.length, verb:'open', value:open.reduce((s,f)=>s+amtOf(f),0),
              done:fs.filter(f=>decided(f.finding_id)).length+' of '+fs.length+' done'};
    }
    if(spec.done){
      const cand = rows.filter(r => spec.size(r) > 0);
      const need = rows.filter(spec.needs);
      const ex = chExtraOf(b.dataset.label).reduce((a, x) => a.concat(x.cnt), []);
      const exOpen = ex.filter(openAt), exF = id => amtOf(D.findings.find(y => y.finding_id === id) || {});
      return {left:need.length+exOpen.length, verb:'open', value:need.reduce((s,r)=>s+spec.size(r),0)+exOpen.reduce((s,id)=>s+exF(id),0),
              done:(cand.filter(spec.done).length+ex.filter(decided).length)+' of '+(cand.length+ex.length)+' done'};
    }
    const need = rows.filter(spec.needs);
    const size = r => Math.abs(r.variance!=null ? r.variance : r.off_plan!=null && r.status==='differs'
                     ? r.off_plan : (r.plan!=null && r.status==='no_spend' ? r.plan : r.amount||0));
    return {left:need.length, verb:'open', value:need.reduce((s,r)=>s+size(r),0), done:''};
  }
  if(view==='entries'){
    const open = ENTRIES.filter(e=>openAt(e.finding_id));
    const booked = ENTRIES.filter(e=>jeState(e)==='book').length;
    const ex = chExtraOf(b.dataset.label).reduce((a, x) => a.concat(x.cnt), []);
    const exOpen = ex.filter(openAt), exF = id => amtOf(D.findings.find(y => y.finding_id === id) || {});
    return {left:open.length+exOpen.length, verb:'open', value:open.reduce((s,e)=>s+e.debits,0)+exOpen.reduce((s,id)=>s+exF(id),0),
            done:(booked+ex.filter(decided).length)+' of '+(ENTRIES.length+ex.length)+' done'};
  }
  if(view==='table' && TABLE){
    const c = TABLE.comparisons.find(x=>x.id===b.dataset.cmpPage) || TABLE.comparisons[0];
    const all = TABLE.sections.reduce((a,s)=>a.concat(s.rows),[]);
    const flagged = all.filter(r=>Math.abs(r[c.var]||0) >= fixAt);
    const open = flagged.filter(r=>!explained(r.account_code));
    return {left:open.length, verb:'open', value:open.reduce((s,r)=>s+Math.abs(r[c.var]||0),0),
            done:(flagged.length-open.length)+' of '+flagged.length+' done'};
  }
  return null;
}
function renderChecklist(){
  const host = $('#checklist'); if(!host) return;
  const btns = $$('.nav button[data-view]');
  const one = LAYOUT === 'ui-update';
  let html = one
    ? '<colgroup><col style="width:40%"><col style="width:36%"><col style="width:24%"></colgroup>'+
      '<thead><tr><th>Page</th><th>Status</th><th class="num">Value left</th></tr></thead><tbody>'
    : '<colgroup><col style="width:30%"><col style="width:22%"><col style="width:16%">'+
    '<col style="width:32%"></colgroup><thead><tr><th>Page</th><th>Left to do</th>'+
    '<th class="num">Value</th><th>Done</th></tr></thead><tbody>';
  let head = null;
  btns.forEach((b,i)=>{
    const st = pageStatus(b); if(!st) return;
    const heading = b.dataset.head || '';
    if(heading !== head){
      head = heading;
      /* A page that is its own group needs no heading over it. */
      if (heading !== b.dataset.label) html += '<tr class="sec"><th colspan="4">'+esc(heading)+'</th></tr>';
    }
    if (one){
      /* One status: what is open of the whole, or done. */
      const of = (/ of (\d+) done/.exec(st.done || '') || [])[1];
      html += '<tr class="xp'+(st.left?' needs':'')+'" data-navi="'+i+'"><td><b>'+esc(b.dataset.label)+'</b></td><td>'+
        (st.left ? '<span class="st needs">'+st.left+' open'+(of ? ' of '+of : '')+'</span>'
                 : '<span class="st done">'+(of && of !== '0' ? 'Done, '+of+' of '+of : 'Nothing over '+money0(fixAt))+'</span>')+
        '</td><td class="num">'+(st.left?acct0(st.value):'')+'</td></tr>';
      return;
    }
    html += '<tr class="xp'+(st.left?' needs':'')+'" data-navi="'+i+'"><td><b>'+esc(b.dataset.label)+'</b></td>'+
      '<td>'+(st.left ? '<span class="st needs">'+st.left+' '+st.verb+'</span>'
                      : '<span class="st done">Nothing over '+money0(fixAt)+'</span>')+'</td>'+
      '<td class="num">'+(st.left?acct0(st.value):'')+'</td>'+
      '<td class="secondary">'+esc(st.done)+'</td></tr>';
  });
  host.innerHTML = html + '</tbody>';
  /* No grand total: the flux pack's comparisons read the same accounts, and
     Journal Entries restates findings from other pages, so a sum across pages
     would count the same money more than once. The tiles above count each item
     once. */
}

/* Undecided and at or over the threshold: what the rail counts as open. */
function openAt(id){
  const f = D.findings.find(x=>x.finding_id===id);
  return !!f && isAbove(f) && !decided(id);
}

/* The decision column says where the row stands and nothing else. The two
   decisions and the reason field live in the panel that opens under the row,
   beside the evidence they are taken on. */
function decisionCell(r){
  const f = D.findings.find(x=>x.finding_id===r.finding_id);
  if(!f) return '';
  const st = stateOf(f);
  return '<div class="stc"><span class="st '+st.cls+'">'+esc(st.text)+'</span></div>';
}

const rowText = r => JSON.stringify(r).toLowerCase() + ' ' +
  [r.account, r.credit_account].concat([].concat(r.by_account||[], r.planned||[])
    .map(c=>c.account)).filter(Boolean).map(acctText).join(' ').toLowerCase();

/* One line above the table for a caveat that changes how it reads. Method
   notes are not repeated here: the column headings already carry them. */
function vtAlert(t){
  const um = t.unmatched || {};
  if(t.kind==='vendor_plan' && um.lines){
    return um.lines+' forecast line'+(um.lines===1?'':'s')+' worth '+acct0(um.amount)+
      ' name a vendor the ledger does not have, so they are not in this table.'+
      '<details><summary>Which lines</summary><span class="refs">'+esc(um.refs.join(', '))+'</span></details>';
  }
  if(t.kind==='requester' && (um.po_lines || um.er_lines)){
    return esc(um.po_lines+' PO line'+(um.po_lines===1?'':'s')+' worth '+acct0(um.po_amount)+
      (um.er_lines ? ' and '+um.er_lines+' expense report line'+(um.er_lines===1?'':'s')+' worth '+
        acct0(um.er_amount) : '')+
      ' were raised by people not on the UKG roster, so they are not attributed.');
  }
  return '';
}

/* The button that opens a row sits in a column of its own, so every status
   word and every button line up down the page. */
function vtCols(spec){
  const last = spec.cols[spec.cols.length-1];
  return spec.cols.slice(0, -1).concat([Object.assign({}, last, {w:(parseFloat(last.w)-10)+'%'}),
    {h:'', w:'10%', td:r=>xpBtn(r, spec.btn)}]);
}
/* Each row's line as last drawn, so a refresh can leave unchanged rows alone. */
const vtHeadDrawn = {};
function vtHead(spec, cols, r, st){
  const can = opens(r), n = spec.needs(r), open = can && st.open===r._k;
  return vtHeadDrawn[r._k] = '<tr class="'+(n?'needs ':'')+(can?'xp ':'')+(open?'open':'')+'"'+
    (can?' data-xk="'+esc(r._k)+'"':'')+'>'+
    cols.map(c=>'<td'+(c.num?' class="num"':'')+'>'+c.td(r,n)+'</td>').join('')+'</tr>';
}
/* A reason is saved as it is typed, and the status words follow it in place.
   Redrawing the table instead would take the cursor out of the field, and a
   redraw when the field is left replaces the button the reviewer is clicking,
   so that click is lost. Only the rows' own lines are redrawn; the open panel,
   which holds the field and its buttons, is left as it is. A reason can settle
   a flag shown on another row, so every row is checked, but only a row whose
   line changed is replaced: on a long table, replacing every row on every
   keystroke makes typing lag. */
function refreshVTHeads(){
  const t = VTABLES.find(x=>x.id===vt), host = $('#vttbl');
  if(!t || !host || $('#v-vtable').hidden) return;
  const spec = VT[t.kind](t), cols = vtCols(spec), st = vtS(t.id), byKey = {};
  t.sections.forEach(sec => sec.rows.forEach(r => { byKey[r._k] = r; }));
  $$('#vttbl tr[data-xk]').forEach(tr => {
    const row = byKey[tr.dataset.xk];
    if (!row) return;
    const was = vtHeadDrawn[row._k], html = vtHead(spec, cols, row, st);
    if (html !== was) tr.outerHTML = html;
  });
}
/* The same on Journal Entries: each entry's status word. */
function refreshJEStatus(){
  if ($('#v-entries') && $('#v-entries').hidden) return;
  $$('#jetbl tr.jeh[data-je]').forEach(tr => {
    const f = D.findings.find(x => x.finding_id === tr.dataset.je), el = tr.querySelector('.st');
    if (!f || !el) return;
    const st = stateOf(f);
    el.className = 'st ' + st.cls; el.textContent = st.text;
    tr.classList.toggle('needs', st.cls === 'needs');
  });
}
function renderVT(){
  const t = VTABLES.find(x=>x.id===vt);
  const host = $('#vttbl');
  if(!t || !host) return;
  const spec = VT[t.kind](t), st = vtS(t.id);
  const cols = vtCols(spec);
  if(st.shut===null) st.shut = new Set(FOLDED[t.kind]||[]);
  const needle = st.q.trim().toLowerCase();
  let html = '<colgroup>'+cols.map(c=>'<col style="width:'+c.w+'">').join('')+'</colgroup>'+
    '<thead><tr>'+cols.map(c=>'<th'+(c.num?' class="num"':'')+'>'+esc(c.h)+'</th>').join('')+'</tr></thead><tbody>';
  let shown=0, needN=0, total=0;
  /* Reviewed & Cleared holds only unflagged vendors, so it shows them. */
  const onlyOn = st.only && !(t.id === 'vendors' && vtf === 'clear');
  /* Flagged is what needed a look: open over the threshold, or already decided.
     A line cleared stays on screen; the switch hides only lines with nothing
     to act on. */
  const flagged = r => spec.needs(r) || (spec.done ? spec.done(r) : false) ||
    !!(r.finding_id && (decisions[r.finding_id]||{}).verdict) || !!(rowDec[rowKeyOf(t, r)]||{}).outcome;
  const quiet = t.sections.reduce((n, sec) => n + sec.rows.filter(r => (t.id !== 'vendors' || inVf(r, vtf)) && !flagged(r)).length, 0);
  t.sections.forEach(sec=>{
    sec.rows.forEach((r,i)=>{ r._k = t.id+':'+sec.id+':'+i; });
    /* With unflagged lines hidden, a row settled while it is open stays listed
       until it is closed, so the reviewer sees what the save did. */
    const mine = r => t.id !== 'vendors' || inVf(r, vtf);
    /* On a vendor page the subtotals are the page's own vendors. */
    const secOf = x => t.id !== 'vendors' || !vtf ? x : Object.assign({}, x, (() => { const rs = x.rows.filter(mine),
      sum = k => rs.reduce((a, r) => a + (r[k] || 0), 0); return {total: sum('amount'), prior_total: sum('prior'), prior2_total: sum('prior2')}; })());
    const rows = sec.rows.filter(r => mine(r) && (!needle || rowText(r).indexOf(needle)>-1) && (!onlyOn || flagged(r) || r._k === st.open)
                                      && (!st.blank || ((r.detail||{}).blank||0) > 0));
    total += sec.rows.filter(mine).length;
    needN += sec.rows.filter(mine).filter(spec.needs).length;
    if(!rows.length) return;
    const shut = st.shut.has(sec.id) && !needle && !onlyOn && !st.blank && !(t.id === 'vendors' && vtf && sec.id !== 'stopped');
    /* The label runs across every column up to the first subtotal, so a long
       section name reads on one line instead of wrapping in the first column. */
    const lead = Math.max(1, cols.findIndex(c=>c.sub));
    html += '<tr class="sec"><th colspan="'+lead+'"><button class="secbtn" data-vsec="'+esc(sec.id)+
        '" aria-expanded="'+(!shut)+'"><span class="caret" aria-hidden="true">&rsaquo;</span>'+
        esc(sec.label)+'</button><span class="n">'+rows.length+'</span></th>'+
      cols.slice(lead).map(c=>'<th'+(c.num?' class="num"':'')+'>'+(c.sub?c.sub(secOf(sec)):'')+'</th>').join('')+'</tr>';
    if(t.kind==='dept_plan' && sec.unplanned_total && !shut){
      html += '<tr class="subnote"><td colspan="'+cols.length+'">Plus '+acct0(sec.unplanned_total)+
        ' on accounts the forecast does not plan, listed without a plan figure.</td></tr>';
    }
    if(shut) return;
    rows.forEach(r=>{
      const open = opens(r) && st.open===r._k;
      shown++;
      html += vtHead(spec, cols, r, st);
      if(open) html += spec.panel ? spec.panel(r, cols.length) : evidenceRow(r, cols.length);
    });
  });
  html += '</tbody>';
  $('#vttbl').innerHTML = html;
  /* Vendors only: the lines with no description, which is where the invoice has
     to be read, and the question list for the owners. */
  const vend = t.kind === 'vendors';
  const nb = vend ? t.sections.reduce((s, sec) => s + sec.rows.filter(r => ((r.detail||{}).blank||0) > 0).length, 0) : 0;
  const bb = $('#vtblank');
  bb.hidden = !nb;
  bb.textContent = 'Blank descriptions · ' + nb;
  bb.classList.toggle('active', st.blank); bb.setAttribute('aria-pressed', String(st.blank));
  $('#vtq-export').hidden = !vend;
  const seg = $('#vtseg'); if (seg) seg.hidden = t.id !== 'dept_plan';
  const al = vtAlert(t), box = $('#vtalert');
  box.innerHTML = al; box.hidden = !al;
  const tog = $('#vtonly');
  tog.textContent = st.only ? 'Show unflagged lines' : 'Hide unflagged lines';
  /* No unflagged lines, no switch. */
  tog.hidden = !quiet || (!onlyOn && st.only);
  tog.classList.toggle('active', st.only);
  tog.setAttribute('aria-pressed', String(st.only));
  if($('#vtq').value !== st.q) $('#vtq').value = st.q;
  const pre = $('#vtpre'); if (pre) pre.innerHTML = (CH.pre||{})[t.id + (t.id === 'vendors' && vtf ? '|'+vtf : '')] || '';
  renderChExtras();
  growAll($('#vttbl'));
}

/* ---------- Journal Entries ----------
   Every correction the engine proposes, written as the entry that books it:
   account and name, department, vendor, debit, credit, and the documents behind
   each line. Decided here or in the queue, it is the same decision. */
const ENTRIES = V.entries || [];

/* ---------- editing a proposed entry ----------
   A reviewer can change a proposed entry's accounts, departments and amounts
   before booking it. It must balance and the change needs a reason. The edited
   entry is what goes into the NetSuite import; the log keeps both. */
const EDIT_KEY = 'serif-jeedit::v1::' + (M.run_id || 'unknown');
let jeEdits = (function(){ try { return JSON.parse(Store.getItem(EDIT_KEY)) || {}; }
                           catch(e){ return {}; } })();
function persistEdits(){ try { Store.setItem(EDIT_KEY, JSON.stringify(jeEdits)); } catch(e){} }
let jeEditing = null;
const linesOf = e => (jeEdits[e.finding_id] || {}).lines || e.lines;
const cents = v => Math.round((Number(v) || 0) * 100) / 100;
const sumOf = (ls, k) => cents(ls.reduce((s, l) => s + (Number(l[k]) || 0), 0));
const balancedOf = e => { const ls = linesOf(e), d = sumOf(ls, 'debit'); return d > 0 && d === sumOf(ls, 'credit'); };
const entryText = ls => ls.map(l => acctText(l.account)+(l.department ? ' / '+l.department : '')+' '+
  (Number(l.debit) ? 'Dr '+cents(l.debit) : 'Cr '+cents(l.credit))).join('; ');
const parseAmt = v => cents(String(v == null ? '' : v).replace(/[^0-9.\-]/g, ''));
/* An edited entry's memo follows the edit (AIJ-16). The proposed memo names the
   accounts and departments it moves between, so where the edit changes one, the
   memo names the new one. Where one posted value was edited to two different
   ones, the memo cannot say which, and is left for the reviewer, who can write
   the memo in the edit form in any case. A memo the reviewer wrote is kept. */
function autoMemo(e, lines){
  /* A reclass memo, "Reclass <vendor> from <coding> to <coding>", is written
     again from the edited lines: credits are where it was, debits where it goes,
     naming the account, the department or both, whichever the lines move. */
  const rm = /^Reclass (.+?) from (.+) to (.+?)(\s\|\s.*)?$/.exec(e.memo || '');
  if (rm && (lines || []).length){
    const side = k => (lines || []).filter(l => Number(l[k]) > 0);
    const dr = side('debit'), cr = side('credit');
    const set = (ls, k) => Array.from(new Set(ls.map(l => String(l[k]||'')))).sort().join('|');
    const showA = set(dr, 'account') !== set(cr, 'account'), showD = set(dr, 'department') !== set(cr, 'department');
    if (dr.length && cr.length && (showA || showD)){
      const say = ls => Array.from(new Set(ls.map(l => [showA ? l.account : '', showD ? (l.department || 'no department') : '']
        .filter(Boolean).join(' / ')))).join(', ');
      const vendor = ((e.lines || []).find(l => l.vendor) || {}).vendor || rm[1];
      return {memo: 'Reclass '+vendor+' from '+say(cr)+' to '+say(dr)+(rm[4] || ''), clash: false};
    }
  }
  const swap = {}, clash = new Set();
  (e.lines || []).forEach((l, i) => { const n = (lines || [])[i]; if (!n) return;
    ['account', 'department'].forEach(k => { const a = String(l[k]||''), b = String(n[k]||'');
      if (!a || !b || a === b) return;
      if (swap[a] !== undefined && swap[a] !== b) clash.add(a); else swap[a] = b; }); });
  const keys = Object.keys(swap).filter(a => !clash.has(a)).sort((x, y) => y.length - x.length);
  if (!keys.length) return {memo: e.memo || '', clash: clash.size > 0};
  const re = new RegExp('(^|[^\\w])(' + keys.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')(?![\\w])', 'g');
  return {memo: String(e.memo || '').replace(re, (m, pre, k) => pre + swap[k]), clash: clash.size > 0};
}
const memoOf = e => { const ed = jeEdits[e.finding_id];
  return !ed ? (e.memo || '') : (ed.memo || autoMemo(e, ed.lines).memo); };
function jeDeptChoices(sel){
  const s = new Set(deptChoices());
  ENTRIES.forEach(e => e.lines.forEach(l => { if (l.department) s.add(l.department); }));
  if (sel) s.add(sel);
  return Array.from(s).sort();
}
function jeEditRows(e){
  const pick = (text, sel) => '<td class="rcpick"><span class="rcval"><span class="rcshow">'+esc(text)+'</span>'+
    '<span class="caret" aria-hidden="true">▾</span></span>'+sel+'</td>';
  return linesOf(e).map((l, i) => {
    const side = Number(l.credit) > 0 && !(Number(l.debit) > 0) ? 'credit' : 'debit';
    const amt = '<input type="text" inputmode="decimal" class="fld jeamt" data-li="'+i+'" data-side="'+side+
      '" value="'+cents(l[side]).toFixed(2)+'" aria-label="'+(side === 'debit' ? 'Debit' : 'Credit')+' amount">';
    return '<tr class="jel rcon">'+
      pick(acctText(l.account), '<select class="jeacct" data-li="'+i+'" aria-label="Account">'+accountOptions(l.account)+'</select>')+
      pick(l.department || 'No department', '<select class="jedept" data-li="'+i+'" aria-label="Department">'+
        '<option value=""'+(l.department ? '' : ' selected')+'>No department</option>'+
        jeDeptChoices(l.department).map(x => '<option'+(x === l.department ? ' selected' : '')+'>'+esc(x)+'</option>').join('')+
        '</select>')+
      '<td>'+esc(l.vendor || '')+'</td>'+
      '<td class="num">'+(side === 'debit' ? amt : '')+'</td><td class="num">'+(side === 'credit' ? amt : '')+'</td>'+
      '<td colspan="2"></td></tr>';
  }).join('')+
  '<tr class="rcedit"><td colspan="7"><div class="rcform">'+
    '<label class="rcwhy">Memo<input type="text" class="fld" id="je-memo" data-auto="'+
      ((jeEdits[e.finding_id] || {}).memo ? '0' : '1')+'" value="'+esc(memoOf(e))+'" placeholder="What the entry does"></label>'+
    '<label class="rcwhy">Why it changed<input type="text" class="fld" id="je-note" value="'+
      esc((jeEdits[e.finding_id] || {}).note || '')+'" placeholder="What you changed, and why"></label>'+
    '<span class="inl"><span class="jetot" id="je-tot"></span>'+
    '<button class="fxact primary" data-jesave="'+esc(e.finding_id)+'">Save</button>'+
    '<button class="fxact" data-jecancel="1">Cancel</button></span></div></td></tr>';
}
function jeTotals(){
  const sum = side => cents($$('.jeamt[data-side="'+side+'"]').reduce((s, i) => s + parseAmt(i.value), 0));
  const d = sum('debit'), c = sum('credit'), el = $('#je-tot'), btn = $('[data-jesave]');
  if (el){ el.textContent = 'Debits '+money(d)+' · Credits '+money(c)+(d === c ? '' : ' · off by '+money(Math.abs(d - c)));
    el.classList.toggle('reqd', d !== c); }
  if (btn) btn.disabled = !(d > 0 && d === c);
}
function saveJeEdit(id){
  const e = ENTRIES.find(x => x.finding_id === id); if (!e) return;
  const noteEl = $('#je-note'), note = ((noteEl || {}).value || '').trim();
  if (!note){ toast('Say why it changed'); if (noteEl) noteEl.focus(); return; }
  const lines = linesOf(e).map((l, i) => {
    const m = $('.jeamt[data-li="'+i+'"]'), v = parseAmt(m.value);
    return Object.assign({}, l, {account: $('.jeacct[data-li="'+i+'"]').value,
      department: $('.jedept[data-li="'+i+'"]').value,
      debit: m.dataset.side === 'debit' ? v : 0, credit: m.dataset.side === 'credit' ? v : 0});
  });
  const d = sumOf(lines, 'debit');
  if (!(d > 0 && d === sumOf(lines, 'credit'))){ toast('Debits and credits must be equal'); return; }
  const mEl = $('#je-memo'), auto = autoMemo(e, lines).memo;
  const memo = ((mEl || {}).value || '').trim() || auto;
  jeEdits[id] = {lines: lines, note: note, memo: memo, memo_from: memo === auto ? 'follows the edit' : 'typed',
                 at: new Date().toISOString(), by: byWho()};
  persistEdits(); jeEditing = null; renderEntries(); renderDecisions();
  toast(jeEditNote(e).replace(/^Edited/, 'Entry edited'), 3000);
}
/* Saving an edit does not book the entry: the status says where the edit stands. */
const jeEditNote = e => jeState(e) === 'book' ? 'Edited, in the NetSuite import'
  : jeState(e) === 'no_entry' ? 'Edited, not booked' : 'Edited. Choose Entry booked to import it';
let jeFilter = 'all', jeOpen = null;
const jeState = e => {
  const d = decisions[e.finding_id]||{};
  return !d.verdict || d.verdict==='question' ? 'open' : d.verdict==='book' ? 'book' : 'no_entry';
};
function renderEntries(){
  const host = $('#jetbl'); if(!host) return;
  const list = ENTRIES.filter(e => jeFilter==='all' || jeState(e)===jeFilter);
  const byKind = {};
  list.forEach(e => (byKind[e.kind] = byKind[e.kind] || []).push(e));
  let html = '<colgroup><col style="width:28%"><col style="width:13%"><col style="width:17%">'+
    '<col style="width:11%"><col style="width:11%"><col style="width:10%"><col style="width:10%"></colgroup>'+
    '<thead><tr><th>Account</th><th>Department</th><th>Vendor</th><th class="num">Debit</th>'+
    '<th class="num">Credit</th><th>Decision</th><th></th></tr></thead><tbody>';
  Object.keys(byKind).forEach(kind=>{
    const es = byKind[kind].slice().sort((a,b)=>b.debits-a.debits);
    const dr = es.reduce((s,e)=>s+sumOf(linesOf(e),'debit'),0), cr = es.reduce((s,e)=>s+sumOf(linesOf(e),'credit'),0);
    html += '<tr class="sec"><th colspan="3">'+esc(kind)+'<span class="n">'+es.length+'</span></th>'+
      '<th class="num">'+acct2(dr)+'</th><th class="num">'+acct2(cr)+'</th><th colspan="2"></th></tr>';
    es.forEach(e=>{
      const f = D.findings.find(x=>x.finding_id===e.finding_id);
      const st = f ? stateOf(f) : {cls:'',text:''};
      const open = jeOpen === e.finding_id, ed = jeEdits[e.finding_id], editing = jeEditing === e.finding_id;
      html += '<tr class="jeh xp'+(st.cls==='needs'?' needs':'')+(open?' open':'')+'" data-je="'+
        esc(e.finding_id)+'"><td colspan="3">'+
        '<b>Journal Entry '+esc(e.rule_id==='DRAFT' ? e.entry_id : e.finding_id)+'</b> <span class="secondary">'+
        esc(e.date)+(e.reverses?' · reverses '+esc(e.reverses):'')+'</span>'+
        '<span class="sub2">'+escn(editing ? e.memo : memoOf(e))+'</span>'+
        (ed && !editing && memoOf(e) !== e.memo ? '<span class="sub2">Proposed memo: '+escn(e.memo)+'</span>' : '')+
        (ed && !editing ? '<span class="sub2 jeed">Edited: '+esc(ed.note)+'</span>' : '')+'</td>'+
        '<td class="num">'+acct2(sumOf(linesOf(e),'debit'))+'</td><td class="num">'+acct2(sumOf(linesOf(e),'credit'))+'</td>'+
        '<td><span class="st '+st.cls+'">'+esc(st.text)+'</span>'+
          (ed && !editing ? '<span class="sub2 jeed">'+esc(jeEditNote(e))+'</span>' : '')+'</td>'+
        '<td><div class="inl">'+(editing ? '' : '<button class="fxact" data-jeedit="'+esc(e.finding_id)+'">Edit</button>'+
          (ed ? '<button class="fxact ico" data-jeundo="'+esc(e.finding_id)+'" aria-label="Undo the edit" title="Undo the edit">'+UNDO_ICON+'</button>' : ''))+
        '<button class="fxact'+(open?' on':'')+'" data-je="'+esc(e.finding_id)+'" aria-expanded="'+open+'">'+
        'Evidence <span class="caret" aria-hidden="true">&rsaquo;</span></button></div></td></tr>';
      /* A credit line usually carries the same documents as its debit line; they
         are listed once per entry. */
      const shownDocs = new Set();
      if (editing) html += jeEditRows(e);
      else linesOf(e).forEach(l=>{
        const dkey = (l.documents||[]).join('|'), docs = dkey && !shownDocs.has(dkey) ? l.documents : [];
        if (dkey) shownDocs.add(dkey);
        html += '<tr class="jel"><td>'+acctHTML(l.account)+'</td><td>'+esc(l.department||'')+'</td>'+
          '<td>'+esc(l.vendor||'')+docsHTML(docs)+'</td>'+
          '<td class="num">'+acct2(l.debit)+'</td><td class="num">'+acct2(l.credit)+'</td><td colspan="2"></td></tr>';
      });
      if(!editing && !balancedOf(e)) html += '<tr class="jewarn"><td colspan="7">Debits and credits are not equal. Edit the entry.</td></tr>';
      if(open) html += evidenceRow({finding_id:e.finding_id}, 7);
    });
  });
  html += '</tbody>';
  host.innerHTML = list.length ? html : '<tbody><tr><td class="empty">No entries in this filter.</td></tr></tbody>';
  const n = s => ENTRIES.filter(e=>jeState(e)===s).length;
  /* A line reclassed on a schedule is booked as its own entry. It is listed here,
     where a reviewer looks for what goes into the import. */
  const rcs = reclassEntries(), box = $('#jealert');
  box.innerHTML = rcs.length ? esc(rcs.length+' line reclass'+(rcs.length===1?' joins':'es join')+
      ' the NetSuite import, each as its own entry. Undo one on its row.')+
    rcs.map(x => '<br><span class="mono">'+esc(x.id)+'</span> '+esc((x.vendor ? x.vendor+' ' : '')+x.rc.document+' '+
      money(Math.abs(x.rc.amount||0))+' to '+acctText(x.rc.to_account)+
      (x.rc.to_department && x.rc.to_department !== x.rc.from_department ? ' / '+x.rc.to_department : '')+': '+x.rc.note)).join('') : '';
  box.hidden = !rcs.length;
  $$('[data-jef]').forEach(b=>{ const on=b.dataset.jef===jeFilter;
    b.classList.toggle('active',on); b.setAttribute('aria-pressed',String(on)); });
  growAll(host);
  if (jeEditing) jeTotals();
}

/* NetSuite's journal import, one row per line. Only entries marked for booking
   and in balance: an entry NetSuite would reject has no place in the file. The
   external id groups the lines of one entry. */
/* The import's rows, as one function, so the file, its fingerprint, its audit
   trail and the Decisions page all read the same entries. The column layout is
   the one NetSuite has taken since 1.8.0; it will be read from NetSuite through
   the connector later, so it is not changed here. */
function netsuiteRows(){
  const book = ENTRIES.filter(e=>jeState(e)==='book');
  const ok = book.filter(balancedOf);
  const rcs = reclassEntries();
  const rows=[['External ID','Date','Reversal Date','Memo','Account','Account Name','Department',
               'Name','Debit','Credit','Line Memo','Finding','Requires Ratification']];
  ok.forEach(e=>{
    const f = D.findings.find(x=>x.finding_id===e.finding_id) || {};
    const ed = jeEdits[e.finding_id];
    linesOf(e).forEach(l=>rows.push([e.entry_id, e.date, e.reverses||'', named(memoOf(e)), l.account,
      acctName(l.account), l.department||'', l.vendor||'', Number(l.debit)||'', Number(l.credit)||'',
      (l.documents||[]).join(' '), e.finding_id,
      ed ? 'YES - edited by a reviewer: '+ed.note
         : f.drafted ? 'YES - drafted by Claude' : f.kind==='deterministic' ? 'no' : 'YES - '+KIND_LABEL(f.kind||'')]));
  });
  rcs.forEach(e => e.lines.forEach(l => rows.push([e.id, e.date, '', e.memo, l.account, acctName(l.account),
    l.department||'', e.vendor, l.debit, l.credit, l.memo, '', 'YES - reclass by a reviewer'])));
  const text = csv(rows);
  return {rows, text, book, ok, rcs, entries: ok.length + rcs.length, lines: rows.length - 1,
          hash: rows.length > 1 ? fingerprint(text) : ''};
}
/* A short fingerprint of a file's text, so a recorded upload names the exact
   file, and a later change to the import shows. cyrb53, not a security hash. */
function fingerprint(str){
  let h1 = 0xdeadbeef, h2 = 0x41c6ce57;
  for (let i = 0; i < str.length; i++){ const c = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 2654435761); h2 = Math.imul(h2 ^ c, 1597334677); }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (h2 >>> 0).toString(16).padStart(8, '0') + (h1 >>> 0).toString(16).padStart(8, '0');
}
const nsFile = () => 'serif-journal-entries-netsuite-'+stamp()+'.csv';
function exportNetSuite(){
  const ns = netsuiteRows();
  if(!ns.entries){ toast(ns.book.length ? 'The booked entries do not balance. Edit their lines first.' : 'Choose Entry booked on an entry first.'); return; }
  download(nsFile(), ns.text).then(ok => {
    if (!ok) return;
    /* What was downloaded, so the upload can be recorded against this file. */
    nsExport = {file: nsFile(), at: new Date().toISOString(), by: byWho(), hash: ns.hash,
                entries: ns.entries, lines: ns.lines};
    persistUpload(); renderDecisions();
    if(ns.ok.length < ns.book.length) toast((ns.book.length-ns.ok.length)+' booked entr'+
      ((ns.book.length-ns.ok.length)===1?'y does':'ies do')+' not balance and stayed out. Edit their lines.');
  });
}
/* The audit trail beside the import (AIJ-16): one row for each line of the
   import, by External ID and line, with who decided it, when and why, and any
   edit. The import itself keeps NetSuite's layout; this file carries the rest. */
function auditRows(){
  const ns = netsuiteRows(), up = uploadFor(ns);
  const rows = [['External ID','Line','Date','Account','Account Name','Department','Debit','Credit',
    'Memo','Proposed memo','Source','Finding or row','Outcome','Decided by','Decided at','Rationale',
    'Rationale source','Confidence','Edited by','Edited at','Edit reason','Proposed lines',
    'Uploaded by','Uploaded at','Import fingerprint']];
  const tail = [up ? up.by : '', up ? up.at : '', ns.hash];
  ns.ok.forEach(e => {
    const f = D.findings.find(x => x.finding_id === e.finding_id) || {}, d = decisions[e.finding_id] || {};
    const r = rationaleOf(f, d), ed = jeEdits[e.finding_id];
    linesOf(e).forEach((l, j) => rows.push([e.entry_id, j + 1, e.date, l.account, acctName(l.account), l.department||'',
      Number(l.debit)||'', Number(l.credit)||'', named(memoOf(e)), named(e.memo),
      f.drafted ? 'Drafted by Claude' : 'Proposed by rule '+(f.rule_id||''), (e.finding_id||'')+' '+(f.title||''),
      VERDICTS[d.verdict] || '', d.by || 'Not recorded', d.at || '', r.text, r.source,
      f.confidence != null ? Math.round(f.confidence*100)+'%' : '',
      ed ? (ed.by || 'Not recorded') : '', ed ? ed.at || '' : '', ed ? ed.note : '', ed ? entryText(e.lines) : ''].concat(tail)));
  });
  ns.rcs.forEach(e => e.lines.forEach((l, j) => rows.push([e.id, j + 1, e.date, l.account, acctName(l.account), l.department||'',
    l.debit, l.credit, e.memo, '', 'Line reclass by a reviewer',
    e.row.t.title+': '+(e.vendor||e.row.r.department||'')+' '+e.rc.document, 'Reclass',
    e.rc.by || 'Not recorded', e.rc.at || '', e.rc.note, 'typed', '', '', '', '', ''].concat(tail))));
  return {rows, ns};
}
function exportAudit(){
  const a = auditRows();
  if (!a.ns.entries){ toast('Nothing is in the NetSuite import yet.'); return; }
  download('serif-journal-entries-netsuite-'+stamp()+'-audit.csv', csv(a.rows));
}
/* The NetSuite upload, recorded by the person who made it (AIJ-110): who, when,
   and which file, by its fingerprint. Kept beside the decisions and in the
   decision record. The console never posts to NetSuite. */
const UPLOAD_KEY = 'serif-upload::' + STORE_VERSION + '::' + (M.run_id || 'unknown');
let upload = null, nsExport = null;
(function(){ try { const o = JSON.parse(Store.getItem(UPLOAD_KEY)) || {};
  upload = o.upload || null; nsExport = o.export || null; } catch(e){} })();
function persistUpload(){ try { Store.setItem(UPLOAD_KEY, JSON.stringify({upload, export: nsExport})); } catch(e){} }
/* The upload, if it is of the import as it stands. */
const uploadFor = ns => upload && upload.hash && upload.hash === ns.hash ? upload : null;
function recordUpload(){
  const name = Shared.on() ? byWho() : ((($('#up-name')||{}).value) || '').trim(), ref = ((($('#up-ref')||{}).value) || '').trim();
  const ns = netsuiteRows();
  if (!ns.entries){ toast('Nothing is in the NetSuite import yet.'); return; }
  if (!nsExport || nsExport.hash !== ns.hash){ toast('Download the NetSuite import first: the file you upload is the one recorded.', 3000); return; }
  if (!name){ toast('Enter who uploaded it'); const f = $('#up-name'); if (f) f.focus(); return; }
  upload = {by: name, at: new Date().toISOString(), reference: ref, file: nsExport.file, hash: ns.hash,
            entries: ns.entries, lines: ns.lines, exported_at: nsExport.at, run_id: M.run_id};
  persistUpload(); renderDecisions(); toast('Upload recorded');
}

const SIGN_KEY = 'serif-signoff::' + STORE_VERSION + '::' + (M.run_id || 'unknown');
let signoff = (function(){
  try { return JSON.parse(Store.getItem(SIGN_KEY) || '{}'); }
  catch(e){ return {}; }
})();
function persistSign(){
  try { Store.setItem(SIGN_KEY, JSON.stringify(signoff)); }
  catch(e){ if (storageOK){ storageOK = false; $('#storewarn').hidden = false; } }
}
function renderSign(){
  const host = $('#signoff'); if (!host) return;
  host.innerHTML = ROLES.map(function(r){
    const key = r[0], sig = signoff[key];
    if (sig && sig.name){
      return '<div><div class="role">'+r[1]+'</div>'+
        '<div class="line"><span class="signed">'+esc(sig.name)+'</span>'+
        (!Shared.on() || Shared.canEdit() ? '<button class="mini" data-unsign="'+key+'">Clear</button>' : '')+'</div>'+
        '<span class="when">'+esc((sig.at||'').slice(0,16).replace('T',' '))+'</span></div>';
    }
    /* The approver is the control point, so the queue state is stated on that
       row rather than left for them to remember. */
    const open = (key === 'approved') ? openItems().length : 0;
    if (Shared.on()) return '<div><div class="role">'+r[1]+'</div>'+
      '<div class="line">'+(Shared.canEdit() ? '<button class="mini" data-signbtn="'+key+'">Sign as '+esc(byWho())+'</button>'
        : '<span class="when">Editors of this page sign off</span>')+'</div>'+
      (open ? '<span class="blocked">'+open+' item'+(open===1?'':'s')+' over '+
              money0(fixAt)+' still open</span>' : '')+'</div>';
    return '<div><div class="role">'+r[1]+'</div>'+
      '<div class="line"><input type="text" data-sign="'+key+'" placeholder="Name" '+
      'aria-label="'+esc(r[1])+'"><button class="mini" data-signbtn="'+key+'">Sign</button></div>'+
      (open ? '<span class="blocked">'+open+' item'+(open===1?'':'s')+' over '+
              money0(fixAt)+' still open</span>' : '')+'</div>';
  }).join('');
}
function doSign(key){
  const field = $('[data-sign="'+key+'"]');
  const name = Shared.on() ? byWho() : (field && field.value || '').trim();
  if (!name){ toast('Enter a name first'); if (field) field.focus(); return; }
  const commit = () => {
    signoff[key] = {name: name, at: new Date().toISOString(), by: byWho()};
    persistSign(); renderSign(); toast('Signed');
  };
  const openN = openItems().length;
  if (key === 'approved' && openN){
    ask('Approve with items open?',
        openN+' item'+(openN===1?'':'s')+' over '+money0(fixAt)+
        ' have not been decided. Approving now records your name against a run '+
        'that is not fully worked.',
        'Approve anyway').then(yes => { if (yes) commit(); });
    return;
  }
  commit();
}

function csv(rows){
  return rows.map(r=>r.map(c=>{
    const s=String(c==null?'':c);
    return /[",\n]/.test(s) ? '"'+s.replace(/"/g,'""')+'"' : s;
  }).join(',')).join('\n');
}
function download(name, text, type){
  /* Resolves true once the file is saved or offered, false when it was not. */
  /* Excel decides a local file's encoding from its opening bytes, not from the
     Blob's declared charset, and falls back to the system legacy codepage. A
     UTF-8 byte-order mark is what makes it read the file as UTF-8; without it an
     em dash arrives as three mojibake characters. Applies to CSV only -- a BOM in
     JSON breaks strict parsers. */
  const isCsv = !type || type.indexOf('csv') > -1;
  const data = (isCsv ? '\uFEFF' : '') + text;
  return Shared.save(name, data).then(r => {
    if (r !== null){ if (r) toast('Saved '+name); return r; }
    const blob=new Blob([data], {type:type||'text/csv;charset=utf-8'});
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob); a.download=name;
    document.body.appendChild(a); a.click();
    setTimeout(()=>{URL.revokeObjectURL(a.href); a.remove();},0);
    toast('Downloaded '+name);
    return true;
  });
}
const stamp = () => (M.period||'period').replace(/\s+/g,'').toLowerCase();

/* The row a stored key belongs to, on whichever schedule holds it. */
function findRow(key){ return rowByKey(key); }
function settledRows(){
  const out = [];
  VTABLES.forEach(t => t.sections.forEach(s => s.rows.forEach(r => {
    const key = rowKeyOf(t, r), d = rowDec[key];
    if (d && d.outcome) out.push({t, r, key, d});
  })));
  return out;
}
/* The questions for owners, one row each, grouped by the department that owns
   the answer, ready to send. */
/* Every Follow up: a row's, a line's and a finding's, so the list is the same
   one Decisions shows. */
function followUps(){
  const out = [];
  settledRows().forEach(x => {
    if (x.d.outcome === 'question') out.push({owner: x.r.owner || x.r.department || '', what: x.r.vendor || x.r.department || '',
      q: (x.d.note||'').trim(), amount: x.r.amount || '', why: openFlags(x.r).map(f => f.label).join('; '), at: x.d.at, by: x.d.by});
    if (x.d.outcome === 'reclass'){ const items = (x.r.detail||{}).items || [];
      lineScope(x.r, x.key).forEach(i => { const lo = lineOutcome(x.key, i), l = items[i];
        if (lo && lo.outcome === 'question') out.push({owner: x.r.owner || x.r.department || '',
          what: (x.r.vendor || x.r.department || '')+' '+(l.document||''), q: (lo.note||'').trim(), amount: l.amount,
          why: (l.text||'')+(lo.rest ? ' (with the rest of the row)' : ''), at: lo.at, by: lo.by}); }); }
  });
  /* A row's own Follow up leaves its findings undecided, so a finding on Follow
     up was decided on its own page and is listed on its own. */
  D.findings.forEach(f => { const d = decisions[f.finding_id];
    if (d && d.verdict === 'question') out.push({owner: deptOf(f), what: subjectOf(f),
      q: (d.note||'').trim(), amount: f.amount_at_risk || '', why: f.title, at: d.at, by: d.by}); });
  return out.sort((a, b) => a.owner.localeCompare(b.owner) || Math.abs(b.amount||0) - Math.abs(a.amount||0));
}
function exportQuestions(){
  const qs = followUps();
  if (!qs.length){ toast('No questions recorded'); return; }
  const rows = [['Owner department','Vendor','Question','Amount this month','Why it was flagged','Raised']];
  qs.forEach(x => rows.push([x.owner, x.what, x.q, x.amount, x.why, (x.at||'').slice(0,16).replace('T',' ')]));
  download('serif-questions-'+stamp()+'.csv', csv(rows));
}
function exportLog(){
  /* decided_by and netsuite_external_id close each row, so a line of the import
     and its audit trail are found here by External ID. */
  const rows=[['finding_id','rule_id','band','fix_threshold','department','kind','title',
               'amount_at_risk','decision','rationale','rationale_source','decided_at',
               'confidence','policy_basis','policy_is_draft','proposed_entry','booked_entry','entry_edit_reason',
               'decided_by','netsuite_external_id']];
  const ns = netsuiteRows(), inImport = new Set(ns.ok.map(e => e.finding_id));
  const pad = (r, by, xid) => r.concat(Array(Math.max(0, 18 - r.length)).fill('')).concat([by || '', xid || '']);
  D.findings.forEach(f=>{
    const d=decisions[f.finding_id]||{};
    const r=rationaleOf(f,d);
    const en = ENTRIES.find(e => e.finding_id === f.finding_id), ed = jeEdits[f.finding_id];
    rows.push(pad([f.finding_id,f.rule_id,isAbove(f)?'over threshold':'under threshold',fixAt,
      deptOf(f),f.kind,f.title,f.amount_at_risk||'',
      d.verdict?VERDICTS[d.verdict]:'Outstanding',
      d.verdict?r.text:'', d.verdict?r.source:'',
      d.at||'',
      Math.round((f.confidence||0)*100)+'%',f.policy_basis||'',f.policy_is_draft?'DRAFT':'',
      en ? entryText(en.lines) : '', en ? entryText(linesOf(en)) : '', ed ? ed.note : ''],
      d.verdict ? d.by : '', en && inImport.has(f.finding_id) ? en.entry_id : ''));
  });
  settledRows().forEach(x => {
    rows.push(pad(['', x.t.title, '', fixAt, x.r.owner || x.r.department || '', '',
      x.r.vendor || x.r.department || '', x.r.amount || '', OUT_LABEL[x.d.outcome],
      x.d.outcome === 'reclass' ? lineSummary(x.key) : (x.d.note||'').trim(),
      x.d.src === 'claude' ? 'drafted by Claude' : (x.d.note||'').trim() ? 'typed' : 'none',
      x.d.at || ''], x.d.by));
    /* A line decided on its own, or with the rest of the row; a reclass has its own row below. */
    if (x.d.outcome === 'reclass'){ const items = (x.r.detail||{}).items || [];
      lineScope(x.r, x.key).forEach(i => { const lo = lineOutcome(x.key, i), l = items[i];
        if (!lo || lo.outcome === 'reclass') return;
        rows.push(pad(['', 'Line outcome', '', fixAt, x.r.owner || x.r.department || '', '',
          (x.r.vendor || x.r.department || '')+' '+(l.document||''), l.amount,
          OUT_LABEL[lo.outcome]+(lo.rest ? ', with the rest of the row' : ''), (lo.note||'').trim(),
          lo.legacy ? 'standard' : (lo.note||'').trim() ? 'typed' : 'none', lo.at || ''], lo.by)); }); }
  });
  reclassEntries().forEach(e => rows.push(pad(['', 'Line reclass', '', fixAt, e.row.r.owner || e.row.r.department || '', '',
    e.vendor + ' ' + e.rc.document, e.rc.amount, 'Reclass ' + acctText(e.rc.from_account) +
      (e.rc.from_department ? ' / ' + e.rc.from_department : '') + ' to ' + acctText(e.rc.to_account) +
      (e.rc.to_department ? ' / ' + e.rc.to_department : ''),
    e.rc.note, 'typed', e.rc.at || ''], e.rc.by, e.id)));
  commentaryRows().forEach(x => rows.push(pad(['', 'Commentary', '', fixAt, '', '', acctText(x.r.account_code), x.r.mom_var||'',
    'Commentary', x.text, x.src], '')));
  download('serif-decision-log-'+stamp()+'.csv', csv(rows));
}
/* The work paper: one page to attach to the entry in NetSuite as audit support.
   What was reviewed, what is left, each decision with who and why, the reclasses,
   the booked Journal Entries and the sign-off. */
function exportWorkPaper(){
  const e = s => esc(s == null ? '' : String(s));
  const when = s => e(String(s||'').slice(0,16).replace('T',' '));
  const tbl = (head, rows) => rows.length ? '<table><thead><tr>'+head.map((h,i)=>'<th'+(typeof rows[0][i]==='number'?' class="n"':'')+'>'+e(h)+'</th>').join('')+
    '</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map((c,i)=>'<td'+(typeof c==='number'?' class="n"':'')+'>'+
    (typeof c==='number'?e(money(c)):c)+'</td>').join('')+'</tr>').join('')+'</tbody></table>' : '<p class="m">None.</p>';
  const pages = $$('.nav button[data-view]').map(b => [b, pageStatus(b)]).filter(x => x[1])
    .map(([b, st]) => [e(b.dataset.label), e(st.left+' '+st.verb), st.value, e(st.done||'')]);
  const found = D.findings.filter(f => decisions[f.finding_id] && decisions[f.finding_id].verdict)
    .map(f => { const d = decisions[f.finding_id], r = rationaleOf(f, d);
      return [e(f.title), amtOf(f), e(VERDICTS[d.verdict]), e(r.text), e(r.source), e(d.by || ''), when(d.at)]; });
  const rows = settledRows().map(x => [e(x.t.title), e(x.r.vendor || x.r.department || ''), Math.abs(x.r.amount||0),
    e(OUT_LABEL[x.d.outcome]), e(x.d.outcome === 'reclass' ? lineSummary(x.key) : (x.d.note||'').trim()),
    e(x.d.src === 'claude' ? 'drafted by Claude' : (x.d.note||'').trim() ? 'typed' : ''), e(x.d.by || ''), when(x.d.at)]);
  const lineRows = [];
  settledRows().filter(x => x.d.outcome === 'reclass').forEach(x => { const items = (x.r.detail||{}).items || [];
    lineScope(x.r, x.key).forEach(i => { const lo = lineOutcome(x.key, i), l = items[i];
      lineRows.push([e((x.r.vendor || x.r.department || '')+' '+(l.document||'')), Math.abs(l.amount||0),
        lo ? e(lo.outcome === 'reclass' ? 'Reclass' : OUT_LABEL[lo.outcome]+(lo.rest ? ', with the rest of the row' : ''))
           : '<span class="m">No outcome</span>', e((lo && lo.note) || ''), e((lo && lo.by) || ''), when(lo && lo.at)]); }); });
  const rcs = reclassEntries().map(x => [e(x.id), e(x.vendor+' '+x.rc.document), Math.abs(x.rc.amount||0),
    e(acctText(x.rc.from_account)+(x.rc.from_department?' / '+x.rc.from_department:'')),
    e(acctText(x.rc.to_account)+(x.rc.to_department?' / '+x.rc.to_department:'')), e(x.rc.note), e(x.rc.by || ''), when(x.rc.at)]);
  const booked = ENTRIES.filter(en => decisions[en.finding_id] && decisions[en.finding_id].verdict === 'book')
    .map(en => { const ed = jeEdits[en.finding_id], d = decisions[en.finding_id];
      return [e(en.entry_id), e(named(memoOf(en)) || en.title || en.finding_id), '<span class="mono">'+e(entryText(linesOf(en)))+'</span>',
              e(ed ? 'Edited: '+ed.note+(ed.by ? ' ('+ed.by+')' : '') : 'As proposed'), e(d.by || ''), when(d.at)]; });
  const signs = ROLES.map(r => [e(r[1]), signoff[r[0]] && signoff[r[0]].name ? e(signoff[r[0]].name) : '<span class="m">Not signed</span>',
    signoff[r[0]] ? when(signoff[r[0]].at) : '']);
  const openList = openItems().map(x => [e(x.page), e(x.what), x.amount != null ? Math.abs(x.amount) : '', e(x.need)]);
  const ns = netsuiteRows(), up = upload;
  const upRows = up ? [[e(up.by), when(up.at), e(up.file||''), e(up.entries+' entries, '+up.lines+' lines'), '<span class="mono">'+e(up.hash||'')+'</span>',
    e(up.reference||''), e(up.hash === ns.hash ? 'Matches the import as it stands' : 'The import has changed since this upload')]] : [];
  const open = openItems().length, title = document.title;
  const html = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>'+e(title)+' work paper</title><style>'+
    'body{font:13px/1.45 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#2c2a26;margin:32px;max-width:1100px}'+
    'h1{font-size:20px;margin:0 0 4px}h2{font-size:14px;margin:28px 0 8px}p{margin:4px 0}.m{color:#6b6860}'+
    'table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:5px 8px;border-bottom:1px solid #ddd8cf;vertical-align:top}'+
    'th{font-weight:600;font-size:12px}td.n,th.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.mono{font-family:ui-monospace,Menlo,monospace;font-size:12px}'+
    '@media print{body{margin:12mm}}</style></head><body>'+
    '<h1>'+e(title)+'</h1>'+
    '<p>'+e(M.entity||'')+' · '+e(M.period||'')+' · run '+e(M.run_id||'')+' · engine '+e(M.engine_version||'')+
      ' · ruleset '+e(M.ruleset_version||'')+'</p>'+
    '<p>Population: '+e((M.tie_out||{}).note||'')+'. Review threshold '+e(money0(fixAt))+'; '+
      (open ? e(open+' item'+(open===1?'':'s')+' over it still open') : 'nothing over it open')+'. Exported '+when(new Date().toISOString())+'.</p>'+
    '<h2>By page</h2>'+tbl(['Page','Left to do','Value','Done'], pages)+
    '<h2>Still open</h2>'+tbl(['Page','Item','Amount','What it needs'], openList)+
    '<h2>Findings decided</h2>'+tbl(['Finding','Amount','Outcome','Reason','Reason from','By','Decided'], found)+
    '<h2>Rows decided</h2>'+tbl(['Page','Vendor or department','Amount','Outcome','Note','Note from','By','Decided'], rows)+
    (lineRows.length ? '<h2>Lines decided one by one</h2>'+tbl(['Line','Amount','Outcome','Note','By','Decided'], lineRows) : '')+
    (D.tables && D.tables.length ? '<h2>Commentary</h2>'+tbl(['Account','Change on prior month','Commentary','From'],
      commentaryRows().map(x => [e(acctText(x.r.account_code)), Math.abs(x.r.mom_var||0), e(x.text), e(x.src)])) : '')+
    '<h2>Line reclasses</h2>'+tbl(['External ID','Line','Amount','From','To','Reason','By','Made'], rcs)+
    '<h2>Journal Entries booked</h2>'+tbl(['External ID','Memo','Lines','Edits','By','Decided'], booked)+
    '<h2>NetSuite upload</h2>'+(upRows.length ? tbl(['Uploaded by','When','File','Holds','Fingerprint','NetSuite reference','Now'], upRows)
      : '<p class="m">Not recorded.'+(ns.entries ? ' The import holds '+e(ns.entries+' entries, '+ns.lines+' lines')+', fingerprint <span class="mono">'+e(ns.hash)+'</span>.' : '')+'</p>')+
    '<h2>Sign-off</h2>'+tbl(['Role','Name','Signed'], signs)+
    '</body></html>';
  const slug = title.replace(M.period||'', '').replace(/&/g, '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  download(slug+'-work-paper-'+stamp()+'.html', html, 'text/html;charset=utf-8');
}
/* The decision record: every decision, row outcome, note, raised entry and entry
   edit, with the run it came from. Loading it into a later run of the same month
   carries each one across to the finding or row it was about. A finding is matched
   by its rule and title, not its number, since numbers can move between runs; what
   this run has already decided is kept. */
/* Format 2 (Console 1.8.7) adds the drafts the record was saved beside, the
   upload and the summary, and the reviewer on each decision. A record with no
   format was saved by 1.8.4 to 1.8.6 and loads as before. */
const RECORD_FORMAT = 2;
const plural = (n, one, many) => n + ' ' + (n === 1 ? one : (many || one + 's'));
/* Commentary the reviewer has explained: typed, edited, or a draft accepted. A
   Claude draft not accepted is not commentary, so it never goes in the record as
   a note; the drafts go beside the notes, so a later load can tell them apart. */
function typedNotes(){
  const out = {};
  Object.keys(fluxNotes).forEach(k => { const t = fluxNotes[k];
    if ((t||'').trim() && !isDraftNote(k)) out[k] = t; });
  return out;
}
/* What a record holds, said in words, before it is saved and after it is loaded. */
function holdsText(c){
  const parts = [];
  if (c.decisions) parts.push(plural(c.decisions, 'finding decision'));
  if (c.rows) parts.push(plural(c.rows, 'schedule row'));
  if (c.lines) parts.push(plural(c.lines, 'line decided on its own', 'lines decided on their own'));
  if (c.reclass) parts.push(plural(c.reclass, 'line reclass', 'line reclasses'));
  if (c.edits) parts.push(plural(c.edits, 'Journal Entry edit'));
  if (c.notes) parts.push(plural(c.notes, 'commentary note'));
  if (c.raised) parts.push(plural(c.raised, 'raised entry', 'raised entries'));
  return parts;
}
function recordCounts(){
  const c = {decisions: Object.values(decisions).filter(d => d && d.verdict).length,
    rows: Object.values(rowDec).filter(d => d && d.outcome).length, lines: 0, reclass: 0,
    edits: Object.keys(jeEdits).length, notes: Object.keys(typedNotes()).length,
    drafts: Object.keys(DR.commentary||{}).filter(isDraftNote).length + Object.keys(pendingNotes).filter(isPendingNote).length,
    raised: Object.keys(raised).length};
  Object.values(rowDec).forEach(d => { if (d && d.outcome === 'reclass'){
    c.reclass += (d.reclass||[]).length; c.lines += Object.keys(d.lines||{}).length; } });
  return c;
}
/* The state of the review at the moment it is saved, for Claude to read in the
   chat: what is open, what was decided by outcome, the import and its upload. */
function recordSummary(){
  const ns = netsuiteRows(), groups = {};
  decidedItems().forEach(x => { groups[x.g] = (groups[x.g] || 0) + 1; });
  return {threshold: fixAt, open: openItems().map(x => ({page: x.page, item: x.what, amount: x.amount, needs: x.need})),
    check: checkItems().map(x => ({page: x.page, item: x.what, needs: x.need})),
    decided: Object.keys(LG).filter(k => groups[k]).reduce((o, k) => (o[LG[k]] = groups[k], o), {}),
    follow_ups: followUps().length,
    netsuite_import: {file: nsFile(), entries: ns.entries, lines: ns.lines, fingerprint: ns.hash,
                      uploaded: !!uploadFor(ns), changed_since_upload: !!upload && !uploadFor(ns)}};
}
function exportRecord(){
  const c = recordCounts(), holds = holdsText(c), ns = netsuiteRows(), up = uploadFor(ns), open = openItems().length;
  const body = 'For '+M.period+', run '+String(M.run_id||'').slice(0, 12)+', it holds:\n'+
    (holds.length ? holds.map(x => '• '+x).join('\n') : '• No decisions yet')+
    (c.drafts ? '\n\n'+plural(c.drafts, 'Claude draft')+' not accepted '+(c.drafts===1?'goes':'go')+
      ' in as '+(c.drafts===1?'a draft':'drafts')+', and will not count as explained when the record is loaded.' : '')+
    '\n\nNetSuite upload: '+(up ? 'recorded by '+up.by+', '+String(up.at).slice(0,16).replace('T',' ')
      : upload ? 'recorded, but the import has changed since' : 'not recorded')+'.'+
    '\nStill open: '+(open ? plural(open, 'item')+' over '+money0(fixAt) : 'nothing over '+money0(fixAt))+'.';
  ask('Save the decision record?', body, 'Save the record').then(yes => {
    if (!yes) return;
    const named = {};
    Object.keys(decisions).forEach(id => { const f = D.findings.find(x => x.finding_id === id);
      if (f) named[id] = {rule_id: f.rule_id, title: f.title}; });
    Object.keys(jeEdits).forEach(id => { const f = D.findings.find(x => x.finding_id === id);
      if (f) named[id] = {rule_id: f.rule_id, title: f.title}; });
    const rec = {kind: 'serif-decision-record', format: RECORD_FORMAT, console: window.__SERIF_CONSOLE__ || '',
      run_id: M.run_id, period: M.period, saved_at: new Date().toISOString(), saved_by: byWho(),
      findings: named, decisions, rows: rowDec, notes: typedNotes(), drafts: DR.commentary || {},
      pending_notes: Object.keys(pendingNotes).filter(isPendingNote).reduce((o, k) => (o[k] = pendingNotes[k], o), {}),
      accepted, raised, entry_edits: jeEdits, signoff, upload, netsuite_export: nsExport,
      summary: recordSummary()};
    download('serif-decision-record-'+stamp()+'.json', JSON.stringify(rec, null, 1), 'application/json');
  });
}
/* What loading a record would carry across, worked out before anything changes,
   so the reviewer sees it first. A finding is matched by its rule and title; what
   this run has already decided is kept. */
function planLoad(rec){
  const here = id => { const n = (rec.findings||{})[id]; if (!n) return null;
    const same = D.findings.find(f => f.finding_id === id && f.rule_id === n.rule_id && f.title === n.title);
    if (same) return same.finding_id;
    const by = D.findings.filter(f => f.rule_id === n.rule_id && f.title === n.title);
    return by.length === 1 ? by[0].finding_id : null; };
  const p = {decisions: [], edits: [], rows: [], notes: [], accepted: [], raised: [], kept: 0, missed: [],
             rowsMissed: 0, draftsSkipped: 0, legacyNotes: 0, upload: null, nsExport: null};
  Object.entries(rec.decisions||{}).forEach(([id, d]) => { if (!d || !d.verdict) return; const to = here(id);
    if (!to){ p.missed.push(((rec.findings||{})[id]||{}).title || id); return; }
    if (!decisions[to] || !decisions[to].verdict) p.decisions.push([to, d]); else p.kept++; });
  Object.entries(rec.entry_edits||{}).forEach(([id, d]) => { const to = here(id);
    if (to && !jeEdits[to]) p.edits.push([to, d]); });
  Object.entries(rec.rows||{}).forEach(([k, d]) => { if (!d || !d.outcome) return;
    if (!rowByKey(k)){ p.rowsMissed++; return; }
    if (!rowDec[k]){ const c = JSON.parse(JSON.stringify(d)); upgradeRow(c); p.rows.push([k, c]); } else p.kept++; });
  /* Commentary. A Claude draft the reviewer never accepted is not carried as an
     explanation. A record from 1.8.7 on names its drafts; an older one did not,
     so its notes are compared with this run's own drafts, and any other note is
     taken as the reviewer's and named in the summary for checking. The
     reviewer's own note replaces a draft this run holds, never their own. */
  const legacy = !rec.drafts;
  Object.entries(rec.notes||{}).forEach(([k, text]) => {
    if (!String(text||'').trim()) return;
    const wasAccepted = !!(rec.accepted||{})[k];
    const draft = legacy ? (DR.commentary||{})[k] : (rec.drafts||{})[k];
    if (draft !== undefined && text === draft && !wasAccepted){ p.draftsSkipped++; return; }
    if ((fluxNotes[k]||'').trim() && !isDraftNote(k)){ if (fluxNotes[k] !== text) p.kept++; return; }
    /* From an older record, a note not accepted may be a draft: it loads to review. */
    const pend = legacy && !wasAccepted;
    p.notes.push([k, text, wasAccepted && (DR.commentary||{})[k] === text, pend]);
    if (pend) p.legacyNotes++;
  });
  /* Notes still waiting to be reviewed when the record was saved stay waiting. */
  Object.entries(rec.pending_notes||{}).forEach(([k, text]) => {
    if (!String(text||'').trim() || ((fluxNotes[k]||'').trim() && !isDraftNote(k))) return;
    p.notes.push([k, text, false, true]); p.legacyNotes++; });
  /* An acceptance carries only to the same draft text. */
  Object.keys(rec.accepted||{}).forEach(k => { if (!rec.accepted[k] || accepted[k]) return;
    const was = legacy ? (rec.notes||{})[k] : (rec.drafts||{})[k];
    if ((DR.commentary||{})[k] !== undefined && was === DR.commentary[k]) p.accepted.push(k); });
  Object.entries(rec.raised||{}).forEach(([k, d]) => { if (!raised[k]) p.raised.push([k, d]); });
  if (rec.upload && !upload) p.upload = rec.upload;
  if (rec.netsuite_export && !nsExport) p.nsExport = rec.netsuite_export;
  return p;
}
function planText(rec, p){
  const c = {decisions: p.decisions.length, rows: p.rows.length, edits: p.edits.length, notes: p.notes.length,
             raised: p.raised.length, lines: 0, reclass: 0};
  p.rows.forEach(([k, d]) => { if (d.outcome === 'reclass'){ c.reclass += (d.reclass||[]).length;
    c.lines += Object.keys(d.lines||{}).length; } });
  const lines = holdsText(c).map(x => 'Carries '+x);
  if (p.accepted.length) lines.push('Carries '+plural(p.accepted.length, 'accepted Claude draft'));
  if (p.upload) lines.push('Carries the NetSuite upload recorded by '+p.upload.by+', '+String(p.upload.at).slice(0,16).replace('T',' '));
  if (p.kept) lines.push('Keeps '+plural(p.kept, 'decision')+' this run already holds');
  if (p.missed.length) lines.push(plural(p.missed.length, 'decision')+' did not match a finding in this run');
  if (p.rowsMissed) lines.push(plural(p.rowsMissed, 'row')+' are not in this run');
  if (p.draftsSkipped) lines.push(plural(p.draftsSkipped, 'Claude draft')+' never accepted, left as drafts');
  if (p.legacyNotes) lines.push(plural(p.legacyNotes, 'commentary note')+' from a record saved before Console 1.8.7, which did not mark Claude’s drafts. '+
    (p.legacyNotes === 1 ? 'It loads' : 'They load')+' to review, as a draft does: accept or edit each on the flux pack');
  return lines;
}
function loadRecord(file){
  const rd = new FileReader();
  rd.onload = () => {
    let rec; try { rec = JSON.parse(rd.result); } catch(e){ toast('That file is not a decision record'); return; }
    if (!rec || rec.kind !== 'serif-decision-record'){ toast('That file is not a decision record'); return; }
    if (rec.period && rec.period !== M.period){ toast('That record is for '+rec.period+', not '+M.period); return; }
    applyRecord(rec, 'Load this decision record?', 'Load the record');
  };
  rd.readAsText(file);
}
/* In shared mode, a rerun in the same close starts fresh; the earlier run's
   decisions come in through the same matching as a saved record. */
function carryRun(){
  Shared.earlierRecord().then(rec => {
    if (!rec){ toast('No earlier run of this close'); return; }
    applyRecord(rec, 'Bring in the earlier run’s decisions?', 'Bring them in');
  }).catch(() => toast('The earlier run could not be read'));
}
function applyRecord(rec, title, okLabel){
    const p = planLoad(rec), lines = planText(rec, p);
    const n = p.decisions.length + p.rows.length + p.notes.length;
    const from = 'Saved '+String(rec.saved_at||'').slice(0,16).replace('T',' ')+(rec.saved_by ? ' by '+rec.saved_by : '')+
      ', run '+String(rec.run_id||'').slice(0,12)+(rec.run_id === M.run_id ? ', this run' : ', an earlier run')+'.';
    ask(title, from+'\n\n'+(lines.length ? lines.map(x => '• '+x).join('\n') : '• Nothing new for this run'),
        okLabel).then(yes => {
      if (!yes) return;
      p.decisions.forEach(([to, d]) => { decisions[to] = d; });
      p.edits.forEach(([to, d]) => { jeEdits[to] = d; });
      p.rows.forEach(([k, d]) => { rowDec[k] = d; });
      p.notes.forEach(([k, text, acc, pend]) => { fluxNotes[k] = text; if (acc) accepted[k] = true;
        if (pend) pendingNotes[k] = text; else delete pendingNotes[k]; });
      p.accepted.forEach(k => { accepted[k] = true; });
      p.raised.forEach(([k, d]) => { raised[k] = d; });
      if (p.upload) upload = p.upload;
      if (p.nsExport) nsExport = p.nsExport;
      persist(); persistRows(); persistNotes(); persistAccepted(); persistRaised(); persistEdits(); persistUpload(); persistPending();
      const note = {
        toast: 'Loaded '+n+' decision'+(n===1?'':'s')+(p.missed.length ? '; '+p.missed.length+' did not match a finding in this run' : ''),
        from: from, lines: lines, missed: p.missed.slice(0, 20)};
      /* Shared: the review is already written through; the page redraws in place. */
      if (Shared.on()){
        Object.values(rowDec).forEach(upgradeRow); persistRows();
        loadedNote = note; renderAll(); show('decisions'); toast(note.toast, 2600);
        return;
      }
      try { sessionStorage.setItem('serif-loaded', JSON.stringify(note)); } catch(e){}
      location.reload();
    });
}
/* Only accepted items become proposed entries, so the verdict tested here must
   match the key in DECISION_ACTIONS exactly; any drift silently empties the export.
   The column order is generic. NetSuite's journal-entry import template is
   per-tenant, so adopting Serif's own template is a change to this function. */
function exportEntries(){
  const app=D.findings.filter(f=>decisions[f.finding_id]&&decisions[f.finding_id].verdict==='book');
  const rz=Object.values(raised);
  if(!app.length && !rz.length){ toast('Nothing to export yet'); return; }
  const rows=[['origin','finding_id','rule_id','title','amount','department','recommended_action',
               'rationale','rationale_source','policy_basis','accepted_at',
               'requires_accountant_ratification']];
  app.forEach(f=>{
    const d=decisions[f.finding_id];
    const r=rationaleOf(f,d);
    rows.push(['engine',f.finding_id,f.rule_id,f.title,f.amount_at_risk||'',deptOf(f),
      f.recommendation||'',r.text,r.source,f.policy_basis||'',d.at||'',
      f.kind==='deterministic'?'no':'YES - '+KIND_LABEL(f.kind)]);
  });
  rz.forEach(x=>{
    rows.push(['reviewer','flux-'+x.account,'','Raised from the flux pack: '+x.leaf+' '+x.basis,
      x.amount||'','',(fluxNotes[x.account]||'').trim(),
      (fluxNotes[x.account]||'').trim()?'typed':'none','','',x.at||'',
      'YES - raised by a reviewer, not proposed by a rule']);
  });
  download('serif-proposed-entries-'+stamp()+'.csv', csv(rows));
}

/* ---------- static views ---------- */
/* Which coding dimensions the run actually examines. A reviewer checking one
   dimension at a time in a pivot table cannot see a line that is right on account
   and wrong on department, so saying plainly which dimensions are covered, and
   which are not, and why, is part of the result rather than a footnote. */
const DIMENSIONS = (D.report && D.report.dimensions) || [
  ['Account', 'tested',
   'Every P&L line against the vendor’s usual account and against the account its '
   + 'Coupa purchase order was approved under.'],
  ['Department', 'tested', 'Every P&L line against the vendor’s usual department.'],
  ['Project', 'not applicable', 'Serif does not code projects.'],
  ['Entity', 'not applicable', 'The ledger has one legal entity.'],
];
/* Each missing feed in the console's own words: what it is and what it would
   test. The engines' notes carry file mechanics and history a reviewer has no
   use for, so they are shown only for a feed this list does not know. */
const FEED_TEXT = {
  'netsuite_vendor_master.csv': ['Vendor master',
    'Vendor name, type and country checks. Coding expectations use each vendor\u2019s own history instead.'],
  'payroll_register.csv': ['Payroll register',
    'Payroll tie-out, the payroll cutoff accrual, and payroll department coding person by person.'],
  'hris_headcount.csv': ['HRIS roster', 'Payroll department coding and salary variance by department.'],
  'ebitda_addback_mapping.csv': ['EBITDA add-back mapping', 'Add-back dimension checks.'],
  'coupa_dept_code_mapping.csv': ['Coupa department mapping, confirmed by Serif',
    'Department comparison between Coupa and the ledger in the coding rules.'],
  'fixed_asset_register.csv': ['Fixed asset register', 'Duplicate asset checks and depreciation continuity.'],
  'prepaid_amortization_schedule.csv': ['Prepaid schedule',
    'Prepaid rollforward, and checking prepaid proposals against what is already carried.'],
  'accruals_log.csv': ['Accruals log', 'Stops an accrual being proposed twice.'],
  'external_research_spend_detail.csv': ['External research WIP',
    'Unbilled research work that Coupa receipts do not show.'],
  'open_purchase_commitments.csv': ['Non-PO commitments', 'Commitments made outside Coupa.'],
  'plan': ['Plan, the rolling forecast workbook', 'Actual against plan.'],
  'forecast': ['Forecast cut after the month closed', 'Forecast vs. Actual, the model against the ledger.'],
};
const feedLabel = f => (FEED_TEXT[f.feed]||[f.feed])[0];
const feedText = f => FEED_TEXT[f.feed] ? FEED_TEXT[f.feed][1]
  : String(f.suppresses||'').replace(/\s*A template exists[^.]*\.[^.]*\.?/g,'').trim();

function renderCoverage(){
  if(!$('#coverage')) return;
  const supplied = V.feeds_supplied || [];
  const given = new Set(supplied.map(s=>s.feed));
  const absent=(M.absent_feeds||[]).filter(f=>f.in_uc1_scope && !given.has(f.feed));
  const oos=(M.absent_feeds||[]).filter(f=>!f.in_uc1_scope && !given.has(f.feed));
  const li=f=>'<li>'+esc(feedLabel(f))+'<small>'+esc(feedText(f))+'</small></li>';
  $('#coverage').innerHTML=
    '<div class="card"><h3>Dimensions tested</h3>'+

    '<table><thead><tr><th>Dimension</th><th>Status</th><th>What is checked</th>'+
    '</tr></thead><tbody>'+
    DIMENSIONS.map(d=>'<tr><td>'+esc(d[0])+'</td><td>'+
      (d[1]==='tested'
        ? '<span class="dimyes">tested</span>'
        : '<span class="dimno">'+esc(d[1])+'</span>')+
      '</td><td>'+esc(d[2])+'</td></tr>').join('')+
    '</tbody></table></div>'+
    (supplied.length?'<div class="card cov" style="margin-top:16px"><h3>Supplied to the schedules</h3><ul>'+
      supplied.map(s=>'<li>'+esc(s.label)+s.tests.map(t=>'<small>'+esc(t)+'</small>').join('')+'</li>').join('')+
      '</ul></div>':'')+
    '<div class="card cov" style="margin-top:16px">'+
    '<h3>Not supplied: these tests did not run</h3><ul>'+
    absent.map(li).join('')+'</ul></div>'+
    (oos.length?'<div class="card cov" style="margin-top:16px"><h3>Out of scope this version</h3><ul>'+
      oos.map(li).join('')+'</ul></div>':'')+
    ((V.not_built||[]).length?'<div class="card cov" style="margin-top:16px"><h3>Schedules not built</h3><ul>'+
      V.not_built.map(n=>'<li>'+esc(n.title)+'<small>Needs '+esc(n.needs)+'</small></li>').join('')+
      '</ul></div>':'');
}
function renderHealth(){
  if(!$('#health')) return;
  $('#health').innerHTML='<table><thead><tr><th>Measure</th><th class="num">Value</th>'+
    '<th class="num">Share</th><th class="num">Prior</th></tr></thead><tbody>'+
    (D.metrics||[]).map(x=>'<tr><td>'+esc(x.title)+
      (x.note?'<div style="color:var(--fg-2);font-size:11.5px;margin-top:4px">'+esc(x.note)+'</div>':'')+
      '</td><td class="num">'+(x.unit==='usd'?money(x.value):esc(x.value))+'</td>'+
      '<td class="num">'+pct(x.share)+'</td><td class="num">'+pct(x.prior_share)+'</td></tr>'
    ).join('')+'</tbody></table>';
}

/* Focus mode: one decision at a time, keyboard only, auto-advancing.
   118 findings is daunting as a list; ~29 cards at a few seconds each is not. */
let focusOn = false;
function focusQueue(){
  return clusters(D.findings.filter(f =>
    (band==='all'||bandOf(f)===band) && (kind==='all'||f.kind===kind) && !decided(f.finding_id)))
    .sort((a,b)=>b.amt-a.amt);
}
function focusStart(){
  const q = focusQueue();
  if (!q.length){ toast('Nothing outstanding'); return; }
  selected = q[0].items[0].finding_id;
  focusOn = true; $('#focus').hidden = false; renderFocus();
}
function focusExit(){ focusOn = false; $('#focus').hidden = true; renderList(); }
function focusNext(){
  const q = focusQueue();
  if (!q.length){ focusExit(); toast('Queue clear'); return; }
  selected = q[0].items[0].finding_id;
  renderFocus();
}
function renderFocus(){
  const f = D.findings.find(x=>x.finding_id===selected);
  if (!f){ focusExit(); return; }
  const q = focusQueue();
  const ev = f.evidence||{}, d = decisions[f.finding_id]||{};
  const siblings = D.findings.filter(x=>clusterKey(x)===clusterKey(f));
  $('#focus-pos').textContent = q.length + (q.length===1?' decision left':' decisions left');
  const kv=(k,v)=>v?'<dt>'+k+'</dt><dd>'+poify(esc(v))+'</dd>':'';
  $('#focus-card').innerHTML =
    '<div class="card">'+
      '<span class="sev" style="color:'+SEV_COLOR[bandOf(f)]+'">'+
        esc(isAbove(f)?BAND_LABEL[0]:BAND_LABEL[1])+'</span>'+
      '<h3 class="dt">'+escn(subjectOf(f))+'</h3>'+
      (siblings.length>1
        ? '<p class="secondary" style="margin-top:var(--spacing-2xs)">'+siblings.length+
          ' findings · '+money(siblings.reduce((s,x)=>s+(x.amount_at_risk||0),0))+
          ' · one decision covers them all</p>'
        : '<p class="secondary" style="margin-top:var(--spacing-2xs)">'+
          (f.amount_at_risk?money(f.amount_at_risk):'')+'</p>')+
      correctionHTML(f)+
      '<dl class="kv">'+
        (correctionIsDerived(f)?'':kv('Observed',ev.observed)+kv('Expected',ev.expected))+
        kv('Basis',ev.basis)+'</dl>'+
      (f.recommendation?'<div class="rec"><b>Recommended</b><br>'+escl(f.recommendation)+'</div>':'')+
    '</div>'+
    '<div class="card"><div class="acts">'+
      ACTIONS(f).map(o=>'<button class="pill pill--knockout'+(d.verdict===o[0]?' active':'')+
        '" data-decide="'+o[0]+'">'+o[1]+'</button>').join('')+'</div>'+
      '<dl class="hints">'+ACTIONS(f).map(o=>'<dt>'+o[1]+'</dt><dd>'+esc(o[4])+
        (o[3]?' <em>Written reason required.</em>':'')+'</dd>').join('')+'</dl>'+
      '<label class="notelab" for="note">'+noteLabel(f)+'</label>'+
      '<textarea id="note" placeholder="'+esc(noteLabel(f))+'">'+esc(d.note||'')+'</textarea>'+
    '</div>';
  $('#focus-keys').innerHTML = ACTIONS(f).map(o=>'<b>'+o[2]+'</b> '+o[1]).join(' &nbsp;·&nbsp; ') +
    ' &nbsp;·&nbsp; <b>Space</b> skip &nbsp;·&nbsp; <b>Esc</b> back to the list';
  growAll($('#focus-card'));
}

/* A single forward action per view, labeled with what it does and how much is
   waiting. No instructions: the path is the interface. */
function renderNext(){
  const openAb = openAbove(), open = openCount(), decided_ = D.findings.length - open;
  const go = (view,label) => '<button class="pill pill--go" data-goto="'+view+'">'+
    esc(label)+' <span class="arw" aria-hidden="true">&rarr;</span></button>';
  const set = (id,html) => { const el=$(id); if (el) el.innerHTML = html || ''; };

  set('#next-overview', openAb
    ? go('review','Review '+openAb+' item'+(openAb===1?'':'s')+' over '+money0(fixAt))
    : (decided_ ? go('decisions','Go to decisions')
                : go('review','Open the queue')));
  /* On Review the next move is to keep working, and Focus mode already is that
     button, so the slot only fills once the queue is clear. */
  set('#next-review', open ? '' : go('decisions','Nothing outstanding, record decisions'));
  set('#next-health', go('review','Back to review'));
  set('#next-coverage', go('review','Back to review'));
}

function renderAll(){ renderRail(); renderNavCounts(); renderOverview(); renderList();
  renderTable(); renderVT(); renderEntries(); renderDecisions(); renderSign(); renderNext();
  renderBS(); renderAudit(); renderChExtras();
  if (focusOn) renderFocus(); }
/* Every page but the one holding a reason field on screen. */
function renderOffscreen(){
  const off = id => { const v = $('#v-'+id); return !v || v.hidden; };
  renderRail(); renderNavCounts(); renderOverview(); if (off('review')) renderList();
  if (off('table')) renderTable(); if (off('vtable')) renderVT(); if (off('entries')) renderEntries();
  renderDecisions(); renderSign(); renderNext();
  if (off('bsflux')) renderBS(); renderAudit(); if (off('entries') && off('vtable')) renderChExtras();
}

/* A rail entry is a view plus, for the per-analysis entries, the group it pins.
   Those entries all land on the review view with `groupFilter` set, so one list
   implementation serves both the combined queue and every single-analysis page.
   Passing `undefined` leaves the current filter alone, which is what the
   non-review entries want; passing `null` clears it. */
function show(v, group, sub){
  if (group !== undefined){ groupFilter = group; selected = null; }
  if (v==='vtable' && sub) vt = sub;
  if (v==='table' && sub) cmp = sub;
  $$('.view').forEach(x=>x.hidden=(x.id!=='v-'+v));
  /* One entry is current. Pages that share a view are told apart by what they
     pin: the queue by its group, a schedule by its table, the flux pack by its
     comparison. */
  /* Plan by department is the budget page read another way, so the budget
     page stays current in the rail while it shows. */
  const byDept = v==='vtable' && vt==='dept_plan' && !$('.nav button[data-vt="dept_plan"]');
  const isCurrent = b => byDept ? b.dataset.cmpPage==='budget' : b.dataset.view===v && (
    v==='review' ? (b.dataset.group||null)===(groupFilter||null) :
    v==='vtable' ? b.dataset.vt===vt && (b.dataset.vf||null)===(vt==='vendors' ? vtf : null) :
    v==='table' ? b.dataset.cmpPage===cmp : true);
  $$('[data-seg]').forEach(s => s.setAttribute('aria-pressed', String((s.dataset.seg==='dept') === byDept)));
  $$('.nav button[data-view]').forEach(b=>b.setAttribute('aria-current', String(isCurrent(b))));
  /* The current page's group shows its tabs, and the page title is the group. */
  let strip = null;
  $$('.stabs').forEach(s=>{ const on = !!s.querySelector('[aria-current="true"]'); s.hidden = !on; if(on) strip = s; });
  $$('.tnav .tgt').forEach(t=>t.classList.toggle('cur', !!strip && t.dataset.grp===strip.dataset.grp));
  if (strip) lastTab[strip.dataset.grp] = strip.querySelector('[aria-current="true"]');
  const b=$$('.nav button[data-view]').find(isCurrent);
  if(b) $('#crumb').textContent = strip && LAYOUT !== 'ui-update' ? b.dataset.head : b.dataset.label;
  $$('.tnav .tg').forEach(g => g.classList.toggle('open', !!g.querySelector('.tsub [aria-current="true"]')));
  if(v==='review') renderList();
  if(v==='overview'){ renderOverview(); renderNavCounts(); }
  if(v==='vtable') renderVT();
  if(v==='table') renderTable();
  if(v==='entries') renderEntries();
  if(v==='decisions') renderDecisions();
  if(v==='bsflux') renderBS();
  if(v==='audit') renderAudit();
  if(v==='export' || v==='entries') renderDecisions();
  if(v==='entries') renderChExtras();
  growAll($('#v-'+v));
}

/* Open count per analysis, so the rail says where work remains without the
   reviewer opening each page to find out. Hidden at zero rather than shown as
   "0", since a page with nothing outstanding needs no number. */
function renderNavCounts(){
  $$('[data-navct]').forEach(el=>{
    const g = el.dataset.navct;
    let open;
    if (g.indexOf('vt:') === 0){ const st = pageStatus(el.closest('button')); open = st ? st.left : 0; }
    else if (g === '__entries') open = ENTRIES.filter(e=>openAt(e.finding_id)).length +
      chExtraOf(el.closest('button').dataset.label).reduce((n, x) => n + x.cnt.filter(openAt).length, 0);
    else open = D.findings.filter(f => groupOf(f)===g && isAbove(f) && !decided(f.finding_id)).length;
    el.textContent = open ? open : '';
  });
  /* A group's count is what is left across its pages. */
  $$('[data-grpct]').forEach(el=>{
    const strip = $('.stabs[data-grp="'+el.closest('.tgt').dataset.grp+'"]');
    /* Journal Entries restate findings counted on the other tabs, so they are
       not counted twice. */
    const cts = strip ? [...strip.querySelectorAll('button:not([data-view="entries"]) [data-navct]')] : [];
    /* A group whose pages carry no counts of their own, the flux pack, counts its
       open work the way the tick-and-tie does. */
    const n = cts.length ? cts.reduce((s, c) => s + (Number(c.textContent) || 0), 0)
      : strip ? workItems().filter(i => i.page === strip.getAttribute('aria-label') && i.amt >= fixAt && !i.done).length : 0;
    el.textContent = n ? n : '';
  });
}

/* A loaded decision record reloads the page; say what it carried across, on
   Decisions, where it was loaded. */
(function(){ try { const m = sessionStorage.getItem('serif-loaded'); if (!m) return;
  sessionStorage.removeItem('serif-loaded');
  let o; try { o = JSON.parse(m); } catch(e){ o = {toast: m}; }
  if (o && typeof o === 'object' && o.lines) loadedNote = o;
  setTimeout(() => toast((o && o.toast) || m, 2600), 300); } catch(e){} })();

/* ---------- the stores, as the adapter shares them ----------
   One shared document per item where two reviewers work on different items at
   once (a finding, a row, an account's commentary, an entry), one for the upload
   and one for the sign-off. Claude's drafts stay in the page: commentary that is
   still the draft, not accepted, is not written to the shared review. The
   reviewer's name in the bar and the note after a record loads stay in this
   browser. */
const refOf = id => { const f = D.findings.find(x => x.finding_id === id);
  return f ? {rule_id: f.rule_id, title: f.title} : null; };
const fillDrafts = (o, only) => (only !== undefined ? [only] : Object.keys(DR.commentary || {})).forEach(c => {
  if (o[c] === undefined && (DR.commentary || {})[c] !== undefined) o[c] = DR.commentary[c]; });
Store.bind('decisions', KEY, {get: () => decisions, set: v => { decisions = v; }, ref: refOf});
Store.bind('rows', ROW_KEY, {get: () => rowDec, set: v => { rowDec = v; }});
Store.bind('notes', NOTE_KEY, {get: () => fluxNotes, set: v => { fluxNotes = v; }, fill: fillDrafts,
  omit: (k, v) => (DR.commentary || {})[k] === v && !accepted[k]});
Store.bind('accepted', ACCEPT_KEY, {get: () => accepted, set: v => { accepted = v; }});
Store.bind('pending', PEND_KEY, {get: () => pendingNotes, set: v => { pendingNotes = v; }});
Store.bind('raised', RAISE_KEY, {get: () => raised, set: v => { raised = v; }});
Store.bind('edits', EDIT_KEY, {get: () => jeEdits, set: v => { jeEdits = v; }, ref: refOf});
Store.bind('upload', UPLOAD_KEY, {kind: 'doc', path: Shared.uploadPath, empty: () => ({}),
  get: () => ({upload: upload, export: nsExport}), set: v => { upload = v.upload || null; nsExport = v.export || null; }});
Store.bind('signoff', SIGN_KEY, {kind: 'doc', path: Shared.signPath, names: true, admin: true, empty: () => ({}),
  get: () => signoff, set: v => { signoff = v || {}; }});

/* ---------- events ---------- */
document.addEventListener('scroll', e => {
  const v = e.target; if (v.classList && v.classList.contains('view')) v.classList.toggle('scrolled', v.scrollTop > 0);
}, true);
/* A group's button in the bar opens the group's last page, or its first. */
const lastTab = {};
document.addEventListener('click',e=>{
  if (e.target.closest('a.xl')) return;
  const tgt=e.target.closest('.tnav .tgt');
  if(tgt){ const g=tgt.dataset.grp, strip=$('.stabs[data-grp="'+g+'"]');
    const b=(LAYOUT === 'ui-update' ? null : lastTab[g]) || (strip && strip.querySelector('button[data-view]')); if(b) b.click(); return; }
  const nav=e.target.closest('.nav button[data-view]');
  if(nav){
    vtf = nav.dataset.vf || null;
    show(nav.dataset.view, nav.dataset.group || null, nav.dataset.vt || nav.dataset.cmpPage);
    return; }
  /* Decisions: an item opens on its page; a count goes to its list. */
  const dgo=e.target.closest('[data-dgo]');
  if(dgo){ goItem(DGO[Number(dgo.dataset.dgo)]); return; }
  const dtile=e.target.closest('[data-dtile]');
  if(dtile){ const g=dtile.dataset.dtile, el=$(g==='open' ? '#dopen' : '#dg-'+g); if(el) el.scrollIntoView({block:'start', behavior:'smooth'}); return; }
  if(e.target.closest('#finish-go')){ showFinish(); return; }
  if(e.target.closest('#up-record')){ recordUpload(); return; }
  if(e.target.closest('#up-clear')){
    ask('Clear the upload record?', 'The record that '+(upload||{}).by+' uploaded the import on '+whenTxt((upload||{}).at)+
        (Shared.on() ? ' is removed for everyone with access to this page.' : ' is removed from this browser.')+' NetSuite is not changed.', 'Clear it').then(yes => {
      if(!yes) return; upload=null; persistUpload(); renderDecisions(); toast('Upload record cleared'); });
    return; }
  if(e.target.closest('#dloaded-x')){ loadedNote=null; renderDecisions(); return; }
  const rst=e.target.closest('[data-rest]');
  if(rst){ const hit=findRow(rst.dataset.rest); if(hit) setRestOutcome(hit.t, hit.r, rst.dataset.o); return; }
  const vsec=e.target.closest('[data-vsec]');
  if(vsec){ const st=vtS(vt); const id=vsec.dataset.vsec;
    if(st.shut.has(id)) st.shut.delete(id); else st.shut.add(id); renderVT(); return; }
  /* A row with evidence opens under itself on a click anywhere in it, except on
     the controls it carries: the commentary field, a disclosure, a raise. */
  const inert = e.target.closest('textarea,input,summary,details,[data-raise],[data-decide-row],[data-outcome],[data-lview],[data-rcopen],[data-rcsave],[data-rccancel],[data-rcremove],select,[data-fdep],[data-fmov],[data-draft],[data-accept],[data-usevdraft],[data-useadraft],[data-rest],.secbtn');
  const xk = !inert && e.target.closest('[data-xk]');
  if(xk){ const st=vtS(vt); st.open = st.open===xk.dataset.xk ? null : xk.dataset.xk;
    renderVT(); return; }
  const jed=e.target.closest('[data-jeedit]');
  if(jed){ jeEditing=jed.dataset.jeedit; renderEntries(); const sel=$('.jeacct'); if(sel) sel.focus(); return; }
  const jeu=e.target.closest('[data-jeundo]');
  if(jeu){ delete jeEdits[jeu.dataset.jeundo]; persistEdits(); renderEntries(); renderDecisions(); toast('Edit undone'); return; }
  if(e.target.closest('[data-jecancel]')){ jeEditing=null; renderEntries(); return; }
  const jes=e.target.closest('[data-jesave]');
  if(jes){ saveJeEdit(jes.dataset.jesave); return; }
  const je = !inert && e.target.closest('[data-je]');
  if(je){ jeOpen = jeOpen===je.dataset.je ? null : je.dataset.je; renderEntries(); return; }
  const fx = !inert && !e.target.closest('[data-expand]') && e.target.closest('[data-fx]');
  if(fx){ openRow = (openRow===fx.dataset.fx) ? null : fx.dataset.fx; renderTable(); return; }
  const ac=e.target.closest('[data-accept]');
  if(ac){ accepted[ac.dataset.accept]=true; persistAccepted(); renderAll(); toast('Commentary accepted'); return; }
  const uv=e.target.closest('[data-usevdraft]');
  if(uv){ const hit=findRow(uv.dataset.usevdraft); const v=hit && (DR.vendors||{})[hit.r.vendor];
    if(v){ rowDec[uv.dataset.usevdraft] = Object.assign({}, rowDec[uv.dataset.usevdraft]||{},
        {outcome:v.recommend, note:v.text, src:'claude', srcFor:v.recommend,
         notes:Object.assign({}, stashNote(rowDec[uv.dataset.usevdraft]||{}).notes, {[v.recommend]: v.text}),
         at:new Date().toISOString(), by:byWho()});
      syncFindings(hit.r, rowDec[uv.dataset.usevdraft], uv.dataset.usevdraft); persistRows(); persist(); renderAll();
      toast(OUT_LABEL[v.recommend]+', from Claude\'s draft'); } return; }
  const ua=e.target.closest('[data-useadraft]');
  if(ua){ const id=ua.dataset.useadraft, v=(DR.adjustments||{})[id];
    if(v){ if((decisions[id]||{}).verdict !== v.recommend) decideOne(id, v.recommend);
      const pair=(V.entries||[]).find(x=>(x.finding_ids||[]).indexOf(id)>-1);
      (pair?pair.finding_ids:[id]).forEach(k=>{ if(decisions[k]){ decisions[k].note=v.note; decisions[k].src='claude'; } });
      persist(); renderAll(); toast(VERDICTS[v.recommend]+', from Claude\'s draft'); } return; }
  const fd=e.target.closest('[data-fdep]');
  if(fd){ const s=drillOf(fd.dataset.fdep); s.dept = s.dept===fd.dataset.d ? null : fd.dataset.d; s.open=null; renderTable(); return; }
  const fm=e.target.closest('[data-fmov]');
  if(fm){ const s=drillOf(fm.dataset.fmov), i=Number(fm.dataset.i); s.open = s.open===i ? null : i; renderTable(); return; }
  const dr_=e.target.closest('[data-draft]');
  if(dr_){ const f=D.findings.find(x=>x.finding_id===dr_.dataset.draft);
    if(f){ fluxNotes[f.account_code]=varianceDraft(f); persistNotes(); renderTable(); renderNavCounts();
      toast('Draft written. Edit it in Commentary'); } return; }
  const oc=e.target.closest('[data-outcome]');
  if(oc){ const hit=findRow(oc.dataset.outcome); if(hit) setOutcome(hit.t, hit.r, oc.dataset.o); return; }
  const lv=e.target.closest('[data-lview]');
  if(lv){ const k=lv.dataset.lview, kind=lv.dataset.kind, cur=lineView[k]||{kind:'flags'};
    const same = kind==='coding' && cur.kind==='coding' && cur.account===lv.dataset.a && cur.department===lv.dataset.d;
    lineView[k] = same ? {kind:'flags'} : {kind:kind, id:lv.dataset.id, account:lv.dataset.a, department:lv.dataset.d};
    renderVT(); return; }
  const rco=e.target.closest('[data-rcopen]');
  if(rco){ const i=Number(rco.dataset.li), k=rco.dataset.rcopen;
    rcEdit = (rcEdit && rcEdit.key===k && rcEdit.i===i) ? null : {key:k, i:i};
    renderVT(); const s=$('#rc-acct'); if(s) s.focus(); return; }
  if(e.target.closest('[data-rccancel]')){ rcEdit=null; renderVT(); return; }
  const rcs=e.target.closest('[data-rcsave]');
  if(rcs){ const hit=findRow(rcs.dataset.rcsave); if(hit) saveReclass(hit.t, hit.r, Number(rcs.dataset.li)); return; }
  const rcr=e.target.closest('[data-rcremove]');
  if(rcr){ const hit=findRow(rcr.dataset.rcremove); if(hit) removeReclass(hit.t, hit.r, Number(rcr.dataset.li)); return; }
  if(e.target.closest('#vtblank')){ const st=vtS(vt); st.blank=!st.blank; renderVT(); return; }
  const sg=e.target.closest('[data-seg]');
  if(sg){ if(sg.dataset.seg==='dept') show('vtable', undefined, 'dept_plan'); else show('table', undefined, 'budget'); return; }
  const tc=e.target.closest('[data-page]');
  if(tc){ const b=$$('.nav button[data-view]').find(x=>x.dataset.label===tc.dataset.page) ||
      (tc.dataset.page==='Flux pack' && $('.nav button[data-cmp-page="mom"]'));
    if(b) b.click(); return; }
  const navi=e.target.closest('[data-navi]');
  if(navi){ const b=$$('.nav button[data-view]')[Number(navi.dataset.navi)]; if(b) b.click(); return; }
  const jef=e.target.closest('[data-jef]');
  if(jef){ jeFilter=jef.dataset.jef; renderEntries(); return; }
  if(e.target.closest('#vtonly')){ const st=vtS(vt); st.only=!st.only; renderVT(); return; }
  const ct=e.target.closest('[data-cmp]');
  if(ct){ cmp = ct.dataset.cmp; renderTable(); return; }
  const rz=e.target.closest('[data-raise]');
  if(rz){ toggleRaise(rz.dataset.raise); return; }
  const xp=e.target.closest('[data-expand]');
  if(xp){ openRow = (openRow===xp.dataset.expand) ? null : xp.dataset.expand;
          renderTable(); return; }
  const dr=e.target.closest('[data-decide-row]');
  if(dr){ decideOne(dr.dataset.decideRow, dr.dataset.verdict); return; }
  const dec=e.target.closest('[data-decide]');
  if(dec){ decide(selected, dec.dataset.decide); return; }
  const row=e.target.closest('.cluster');
  if(row){ selected=row.dataset.id; renderList(); centerSelected(); return; }
  if(e.target.id==='reset'){
    /* Everything the console keeps for this run, said before it goes. */
    const parts = holdsText(recordCounts());
    const nAcc = Object.keys(accepted).filter(k => accepted[k]).length;
    const nSig = ROLES.filter(r => signoff[r[0]] && signoff[r[0]].name).length;
    const nNotes = Object.values(decisions).filter(d => d && !d.verdict && (d.note||'').trim()).length;
    if (nNotes) parts.push(plural(nNotes, 'reason', 'reasons')+' typed before an outcome was chosen');
    if (nAcc) parts.push(plural(nAcc, 'accepted Claude draft'));
    const nPend = Object.keys(pendingNotes).filter(isPendingNote).length;
    if (nPend) parts.push(plural(nPend, 'commentary note')+' from an older record, still to review');
    if (nSig) parts.push(plural(nSig, 'signature'));
    if (upload) parts.push('the NetSuite upload record');
    if (nsExport) parts.push('the note of the last NetSuite import download');
    if(!parts.length){ toast('Nothing recorded'); return; }
    if(Shared.on() && !Shared.canEdit()){ toast('Only Editors of this page can clear the shared review', 2600); return; }
    ask('Clear all decisions?',
        (Shared.on() ? 'This removes for everyone with access to this page:\n' : 'This removes from this browser:\n')+parts.map(x => '• '+x).join('\n')+
        '\n\nClaude’s drafts stay, as drafts to review. Files already downloaded are not affected. This cannot be undone.',
        'Clear everything', 'clear').then(yes => {
      if(!yes) return;
      decisions={}; persist(); rowDec={}; persistRows(); signoff={}; persistSign();
      jeEdits={}; persistEdits(); accepted={}; persistAccepted(); raised={}; persistRaised();
      fluxNotes={}; persistNotes(); pendingNotes={}; persistPending();
      Object.keys(DR.commentary || {}).forEach(c => { fluxNotes[c] = DR.commentary[c]; });
      upload=null; nsExport=null; persistUpload();
      selected=null; rcEdit=null; jeEditing=null; finishShown=false; renderAll(); toast('Everything cleared');
    });
    return;
  }
  if(e.target.id==='fxonly'){ fxOnly=!fxOnly; renderTable(); return; }
  if(e.target.id==='bsonly'){ bsOnly=!bsOnly; renderBS(); return; }
  if(e.target.id==='focus-start'){ focusStart(); return; }
  if(e.target.id==='focus-exit'){ focusExit(); return; }
  const ex=e.target.closest('[data-export]');
  if(ex){ ({log:exportLog,paper:exportWorkPaper,record:exportRecord,entries:exportEntries,netsuite:exportNetSuite,audit:exportAudit,questions:exportQuestions})[ex.dataset.export](); return; }
  if(e.target.id==='loadrec'){ $('#recfile').click(); return; }
  if(e.target.id==='carryrun'){ carryRun(); return; }
  /* Setting the threshold from the Overview chart re-partitions everything. */
  const goto_=e.target.closest('[data-goto]');
  if(goto_){ show(goto_.dataset.goto); return; }
  const sgn=e.target.closest('[data-signbtn]');
  if(sgn){ doSign(sgn.dataset.signbtn); return; }
  const uns=e.target.closest('[data-unsign]');
  if(uns){ delete signoff[uns.dataset.unsign]; persistSign(); renderSign();
           toast('Signature cleared'); return; }
  if(e.target.id==='belowline'){
    const reset = e.target.dataset.mode === 'reset';
    band = reset ? 'above' : 'below';
    queue = reset ? 'open' : 'all';
    groupFilter=null; layerFilter=null; selected=null;
    $$('[data-group="band"]').forEach(c=>{
      const on=c.dataset.value===band;
      c.setAttribute('aria-pressed',String(on)); c.classList.toggle('active',on);});
    $$('[data-group="queue"]').forEach(c=>{
      const on=c.dataset.value===queue;
      c.setAttribute('aria-pressed',String(on)); c.classList.toggle('active',on);});
    renderList(); return;
  }
  const setfix=e.target.closest('[data-setfix]');
  if(setfix){ applyThreshold(Number(setfix.dataset.setfix)); return; }
  const bar=e.target.closest('[data-chart]');
  if(bar){
    const which=bar.dataset.chart, val=bar.dataset.chartval;
    queue='all'; band='all'; kind='all'; selected=null;
    if(which==='kind') kind=val;
    $$('[data-group="kind"]').forEach(c=>{
      const on = (which==='kind') ? c.dataset.value===val : c.dataset.value==='all';
      c.setAttribute('aria-pressed',String(on)); c.classList.toggle('active',on);});
    $$('[data-group="queue"]').forEach(c=>{
      const on=c.dataset.value==='all';
      c.setAttribute('aria-pressed',String(on)); c.classList.toggle('active',on);});
    $$('[data-group="band"]').forEach(c=>{
      const on=c.dataset.value==='all';
      c.setAttribute('aria-pressed',String(on)); c.classList.toggle('active',on);});
    /* A run worked on schedules has no queue to filter: the bar opens the page
       that holds the category. */
    if (which==='group' && VTABLES.length){
      const t = VTABLES.find(x=>x.group===val);
      const page = (t && $('.nav button[data-vt="'+t.id+'"]')) ||
        $('.nav button[data-cmp-page="'+({variance:'mom', budget:'budget'}[val]||'')+'"]');
      if (page) page.click();
      return;
    }
    groupFilter = (which==='group') ? val : null;
    layerFilter = (which==='layer') ? val : null;
    if (which==='group'){ show('review', val); return; }
    show('review'); renderList(); return;
  }
  const chip=e.target.closest('.pill--knockout');
  if(chip&&chip.dataset.group){
    $$('[data-group="'+chip.dataset.group+'"]').forEach(c=>{
      c.setAttribute('aria-pressed',String(c===chip)); c.classList.toggle('active',c===chip);});
    const g=chip.dataset.group;
    if(g==='band') band=chip.dataset.value; else if(g==='kind') kind=chip.dataset.value;
    else queue=chip.dataset.value;
    groupFilter=null; layerFilter=null;
    selected=null; renderList();
  }
});

/* The threshold field shows the dollar amount with separators, sized to fit it. A
   text field rather than a number one, so the separators can show. */
function showFix(){
  const input=$('#fixinput'); if(!input) return;
  if(document.activeElement!==input) input.value = input.type==='text' ? fixAt.toLocaleString('en-US') : fixAt;
  fitFix();
}
function fitFix(){
  const input=$('#fixinput'); if(input && input.type==='text')
    input.style.width = (Math.max(input.value.length, 2) + 0.1)+'ch';
}
/* One place where the threshold changes, so every dependent surface is refreshed
   together and the band labels never drift out of sync with the number. */
function applyThreshold(v){
  if(!isFinite(v) || v < 0) return;
  fixAt = v;
  $$('[data-setfix]').forEach(b=>b.classList.toggle('on', Number(b.dataset.setfix)===fixAt));
  showFix();
  /* Relabel the band chips in place. textContent would drop the color dot, so
     only the trailing text node is replaced. */
  $$('[data-group="band"]').forEach(c=>{
    const lab=c.dataset.value==='above' ? 'Over '+money0(fixAt)
            : c.dataset.value==='below' ? 'Under '+money0(fixAt) : 'Everything';
    c.lastChild.nodeValue=lab;
  });
  selected=null; renderAll(); toast('Threshold set to '+money0(fixAt));
}
document.addEventListener('focusin',e=>{
  if(e.target.id==='fixinput' && e.target.type==='text'){ e.target.value=String(fixAt); fitFix(); e.target.select(); }
});
document.addEventListener('focusout',e=>{ if(e.target.id==='fixinput') setTimeout(showFix, 0); });
document.addEventListener('input',e=>{
  if(e.target.dataset && e.target.dataset.bsn !== undefined){ fluxNotes[e.target.dataset.bsn] = e.target.value; persistNotes(); return; }
  if(e.target.id==='bsq'){ renderBS(); $('#bsq').focus(); return; }
  if(e.target.tagName==='TEXTAREA') grow(e.target);
  if(e.target.id==='fixinput') fitFix();
  if(e.target.classList && e.target.classList.contains('jeamt')) jeTotals();
  if(e.target.dataset && e.target.dataset.cmt !== undefined){
    const code = e.target.dataset.cmt;
    fluxNotes[code] = e.target.value;
    persistNotes();
    /* The status beside the field follows the commentary as it is typed. The
       row is not redrawn, which would take the cursor out of the field. */
    const st = $('[data-st="'+code+'"]');
    if(st && !st.dataset.noflag){
      const done = explained(code);
      st.textContent = done ? 'Explained' : 'Needs commentary';
      st.classList.toggle('done', done); st.classList.toggle('needs', !done);
      const tr = st.closest('tr'); if(tr) tr.classList.toggle('needs', !done);
    }
    return;
  }
  if(e.target.id==='whoinput'){
    reviewerName = e.target.value; try { Store.setItem(WHO_KEY, reviewerName); } catch(err){} return;
  }
  if(e.target.id==='je-memo'){ e.target.dataset.auto = '0'; return; }
  if(e.target.dataset && e.target.dataset.rowkey !== undefined){
    /* Saved as typed; the row is not redrawn, which would take the cursor away. */
    const hit = findRow(e.target.dataset.rowkey);
    const d = rowDec[e.target.dataset.rowkey] = rowDec[e.target.dataset.rowkey] || {};
    d.note = e.target.value; d.by = byWho(); delete d.src;
    if (d.outcome && d.outcome !== 'reclass'){ d.notes = d.notes || {}; d.notes[d.outcome] = d.note; }
    if (d.srcFor === d.outcome) delete d.srcFor;
    if (hit) syncFindings(hit.r, d, e.target.dataset.rowkey);
    persistRows(); persist(); renderNavCounts(); refreshVTHeads(); return;
  }
  /* A line's own reason, and the reason for the rest of the row, saved as typed.
     The line states follow in place, as a row's status does. */
  if(e.target.dataset && (e.target.dataset.lnote !== undefined || e.target.dataset.restnote !== undefined)){
    const key = e.target.dataset.lnote !== undefined ? e.target.dataset.lnote : e.target.dataset.restnote;
    const hit = findRow(key), d = rowDec[key];
    if (!hit || !d || d.outcome !== 'reclass') return;
    const o = e.target.dataset.lnote !== undefined ? (d.lines||{})[Number(e.target.dataset.li)] : d.rest;
    if (!o) return;
    o.note = e.target.value; o.notes = o.notes || {}; o.notes[o.outcome] = o.note; o.by = byWho();
    delete o.legacy; d.by = byWho();
    syncFindings(hit.r, d, key); persistRows(); persist(); renderNavCounts(); refreshVTHeads();
    $$('[data-lst]').forEach(el => { const p = el.dataset.lst.split('|'); if (p[0] !== key) return;
      const lo = lineOutcome(key, Number(p[1])); el.textContent = lineStateText(lo); el.classList.toggle('needs', !lineDone(lo)); });
    return;
  }
  if(e.target.dataset && e.target.dataset.rownote !== undefined){
    setNote(e.target.dataset.rownote, e.target.value); renderNavCounts(); refreshVTHeads(); refreshJEStatus(); return;
  }
  if(e.target.id==='vtq'){ vtS(vt).q=e.target.value; renderVT();
    const i=$('#vtq'); i.focus(); return; }
  if(e.target.id==='fxq'){ fxQ=e.target.value; renderTable(); $('#fxq').focus(); return; }
  if(e.target.id==='q'){ q=e.target.value; selected=null; renderList(); }
  if(e.target.id==='note'){ setClusterNote(selected, e.target.value); }
});
document.addEventListener('keydown',e=>{
  if(e.target.id==='fixinput' && e.key==='Enter'){ e.preventDefault(); e.target.blur(); }
  if(e.target.id==='fixinput' && e.key==='Escape'){ e.target.blur(); showFix(); }
  if(e.key==='Enter' && e.target.dataset && e.target.dataset.sign){
    e.preventDefault(); doSign(e.target.dataset.sign);
  }
  if(e.key==='Enter' && (e.target.id==='up-name' || e.target.id==='up-ref')){ e.preventDefault(); recordUpload(); }
  if(e.key==='Enter' && e.target.id==='rc-note'){
    e.preventDefault(); const b=$('[data-rcsave]'); if(b) b.click();
  }
  if(e.key==='Escape' && rcEdit && e.target.closest && e.target.closest('.rcform')){
    rcEdit=null; renderVT();
  }
},true);
document.addEventListener('change',e=>{
  if(e.target.id==='recfile'){ const f=e.target.files[0]; e.target.value=''; if(f) loadRecord(f); return; }
  if(e.target.id==='fixinput') applyThreshold(Number(String(e.target.value).replace(/[^0-9.]/g,'')));
  if(e.target.classList && e.target.classList.contains('lout')){
    const hit=findRow(e.target.dataset.lout); if(hit) setLineOutcome(hit.t, hit.r, Number(e.target.dataset.li), e.target.value || null); return; }
  /* While an entry is edited, its memo follows the accounts and departments
     chosen, until the reviewer writes the memo. */
  if(e.target.classList && (e.target.classList.contains('jeacct') || e.target.classList.contains('jedept')) && jeEditing){
    const m=$('#je-memo'), en=ENTRIES.find(x => x.finding_id === jeEditing);
    if(m && en && m.dataset.auto === '1') m.value = autoMemo(en, linesOf(en).map((l, i) => Object.assign({}, l, {
      account: ($('.jeacct[data-li="'+i+'"]')||{}).value || l.account,
      department: ($('.jedept[data-li="'+i+'"]')||{value: l.department}).value}))).memo;
  }
  /* A reclass choice shows what was picked, in the cell's own text. */
  if(e.target.id==='rc-acct' || e.target.id==='rc-dept' ||
     (e.target.classList && (e.target.classList.contains('jeacct') || e.target.classList.contains('jedept')))){
    const show = e.target.parentNode.querySelector('.rcshow'), o = e.target.selectedOptions[0];
    if(show && o) show.textContent = o.textContent; }
  /* Leaving a reason settles its status on every other page. The page on screen
     already follows it as it is typed, and is not redrawn: the click that took
     the cursor out of the field would land on a button the redraw replaced. */
  if(e.target.dataset && (e.target.dataset.rowkey !== undefined || e.target.dataset.rownote !== undefined ||
     e.target.dataset.lnote !== undefined || e.target.dataset.restnote !== undefined)) renderOffscreen();
});
/* Single-letter shortcuts fire ONLY in focus mode. Bound anywhere else they
   hijack ordinary typing -- a plain "c" while reading the list recorded a coding
   error, and any shortcut sharing a letter with a browser command turned Cmd+C
   into a decision. Modifier chords are therefore never ours to handle, and
   outside focus mode only the arrow keys move the selection. */
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='TEXTAREA'||e.target.tagName==='INPUT') return;
  if(e.metaKey||e.ctrlKey||e.altKey) return;
  const k=e.key.toLowerCase();
  if(focusOn){
    if(e.key==='Escape'){ focusExit(); return; }
    if(e.key===' '){ e.preventDefault();
      const q=focusQueue(); const i=q.findIndex(c=>c.items[0].finding_id===selected);
      if(q.length>1){ selected=q[(i+1)%q.length].items[0].finding_id; renderFocus(); }
      return; }
    const f=D.findings.find(x=>x.finding_id===selected);
    const hit=f && ACTIONS(f).find(o=>o[2].toLowerCase()===k);
    if(hit){ e.preventDefault(); decide(selected,hit[0]); }
    return;
  }
  if(!['arrowdown','arrowup'].includes(k) || !$('#list')) return;
  const cl=clusters(visible()).sort((a,b)=>b.amt-a.amt); if(!cl.length) return;
  e.preventDefault();
  const i=cl.findIndex(c=>c.items.some(f=>f.finding_id===selected));
  const nx=(k==='arrowdown')?Math.min(i+1,cl.length-1):Math.max(i-1,0);
  selected=cl[nx].items[0].finding_id;
  renderList();
  const el=$('.cluster[aria-selected="true"]'); if(el) el.scrollIntoView({block:'nearest'});
});

/* ---------- boot ---------- */
(function(){
  const kd=S.by_kind||{};
  const chips=(g,opts)=>opts.map(o=>'<button class="pill pill--knockout'+(o[2]===true?' active':'')+
    '" data-group="'+g+'" data-value="'+o[0]+'" aria-pressed="'+(o[2]===true)+'">'+
    (o[3]?'<i class="dot" style="background:'+o[3]+'"></i>':'')+o[1]+'</button>').join('');
  if($('#queueChips')){
  $('#queueChips').innerHTML=chips('queue',[['open','Outstanding',true],
    ['done','Decided',false],['all','All',false]]);
  /* Over the threshold, under it, or everything. 'Everything' exists so the
     threshold can be ignored entirely without editing the run. */
  $('#bandChips').innerHTML=chips('band',[
    ['above','Over '+money0(fixAt),true,SEV_COLOR.above],
    ['below','Under '+money0(fixAt),false,SEV_COLOR.below],
    ['all','Everything',false]]);
  const cap=s=>s.charAt(0).toUpperCase()+s.slice(1);
  $('#kindChips').innerHTML=chips('kind',[['all','Any',true]].concat(
    Object.keys(kd).filter(k=>kd[k]).map(k=>[k,cap(KIND_LABEL(k)),false])));
  }
  showFix();
  if(!storageOK) $('#storewarn').hidden=false;
  /* Rows reclassed under 1.8.6 or earlier keep the rest of the row cleared, now
     written down as the rest of the row's own outcome. */
  if (Object.values(rowDec).map(upgradeRow).some(Boolean)) persistRows();
  const wi = $('#whoinput'); if (wi) wi.value = reviewerName;
  renderCoverage(); renderHealth(); renderAll(); show(loadedNote ? 'decisions' : 'overview');
  Shared.start();
})();
"""


# The flux pack's comparisons, named as an accountant names them rather than as
# the engine keys them.
TABLE_PAGE_LABELS = {"mom": "Actual vs. Actual",
                     "yoy": "Actual vs. Actual (YoY)",
                     "budget": "Actual vs. Budget"}

# The schedules serif_views.py adds, named as a controller names them.
VIEW_PAGE_LABELS = {"vendors": "Vendors",
                    "checks": "Ledger checks",
                    "prepaid": "Prepaids and Capital",
                    "reclass": "Reclassifications",
                    "payroll_hris": "Payroll vs. HRIS",
                    "dept_plan": "Department vs. Plan",
                    "model_tie": "Forecast vs. Actual",
                    "accrual": "Accrual Proposals"}


def esc(value):
    text = str(value if value is not None else "")
    for old, new in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ('"', "&quot;")):
        text = text.replace(old, new)
    return text


# Used when a run declares no groups of its own. The coding engine is bundled
# from the repo and does not yet emit a report block, so without this its console
# would show one undifferentiated queue and no per-analysis pages.
#
# There is no budget group here because the coding engine has no budget rule. An
# empty "Budget vs Actual" page would claim an analysis that does not run.
DEFAULT_GROUPS = [
    {"id": "tieout", "label": "Blocks the Close", "rules": ["T0.TIE_OUT"],
     "why": "The ledger does not balance. Nothing else is trustworthy until it does."},
    {"id": "recode", "label": "Coding Exceptions",
     "rules": ["T1.DEPT_INCONSISTENCY", "T4.PO_ACCOUNT_MISMATCH", "T2.UNALLOCATED"],
     "why": ("Coding differs from the established pattern, or from the account a "
             "purchase order was approved against.")},
    {"id": "integrity", "label": "Ledger Integrity",
     "rules": ["T0.DUPLICATE_LINE", "T0.ABERRANT_POSTING_LAG"],
     "why": "Possible duplicates and transactions posted well outside their period."},
    {"id": "tax", "label": "Tax & Deductibility",
     "rules": ["T3.IRC_274A_ENTERTAINMENT", "T3.IRC_274N_MEALS",
               "T3.IRC_274B_GIFTS", "T3.IRC_174_BASE"],
     "why": "Deductibility flags for the add-back schedule. Tax counsel signs these off."},
]


def load_drafts(run, path):
    """Claude's drafts, written in the Project from this run, go into the console
    beside the items they belong to. Each one is checked against the run first:
    commentary must name a flux account, a vendor note a vendor row, an
    adjustment note a finding, and a drafted Journal Entry must balance. Anything
    that fails is left out and listed, so a draft never attaches to the wrong
    item. Returns the drafts to embed and the list of what was left out."""
    with open(path, encoding="utf-8") as h:
        raw = json.load(h)
    views = run.get("views") or {}
    tbl = (run.get("tables") or [None])[0] or {}
    accounts = {r["account_code"] for s in tbl.get("sections", []) for r in s.get("rows", [])}
    vendors = {r.get("vendor") for t in views.get("tables", []) if t.get("kind") == "vendors"
               for s in t["sections"] for r in s["rows"]}
    fids = {f["finding_id"] for f in run.get("findings", [])}
    out, skipped = {}, []

    def text(v):
        return str(v).strip() if v is not None else ""

    com = {}
    for code, v in (raw.get("commentary") or {}).items():
        if code in accounts and text(v):
            com[code] = text(v)
        else:
            skipped.append("commentary for " + str(code))
    ven = {}
    for name, v in (raw.get("vendors") or {}).items():
        v = v or {}
        rec = v.get("recommend")
        if name in vendors and rec in ("clear", "question", "entry"):
            ven[name] = {"note": text(v.get("note")), "recommend": rec, "text": text(v.get("text"))}
        else:
            skipped.append("vendor note for " + str(name))
    adj = {}
    for fid, v in (raw.get("adjustments") or {}).items():
        v = v or {}
        if fid in fids and v.get("recommend") in ("book", "no_entry"):
            adj[fid] = {"recommend": v["recommend"], "note": text(v.get("note"))}
        else:
            skipped.append("adjustment note for " + str(fid))
    ents = []
    for i, e in enumerate(raw.get("entries") or [], start=1):
        lines = [{"account": text(l.get("account")), "department": text(l.get("department")),
                  "vendor": text(l.get("vendor")),
                  "debit": round(float(l.get("debit") or 0), 2), "credit": round(float(l.get("credit") or 0), 2),
                  "documents": [text(d) for d in (l.get("documents") or [])]}
                 for l in e.get("lines") or []]
        dr = round(sum(l["debit"] for l in lines), 2)
        cr = round(sum(l["credit"] for l in lines), 2)
        if not lines or abs(dr - cr) >= 0.005 or not all(l["account"] for l in lines):
            skipped.append("Journal Entry %d (%s): does not balance or has a line with no account"
                           % (i, text(e.get("memo"))[:60]))
            continue
        ents.append({"entry_id": "SERIF-DRAFT-%d" % i, "finding_id": "draft-%d" % i,
                     "rule_id": "DRAFT", "kind": "Drafted by Claude",
                     "date": text(e.get("date")) or next(
                         (x.get("date") for x in views.get("entries", []) if x.get("date")), ""),
                     "reverses": text(e.get("reverses")),
                     "memo": text(e.get("memo")), "support": text(e.get("reason")),
                     "vendor_row": text(e.get("vendor")),
                     "lines": lines, "debits": dr, "credits": cr, "balanced": True})
    for key, v in (("commentary", com), ("vendors", ven), ("adjustments", adj), ("entries", ents)):
        if v:
            out[key] = v
    if text(raw.get("summary")):
        out["summary"] = text(raw["summary"])
    return out, skipped


def attach_drafts(run, drafts):
    """A drafted Journal Entry is decided like any other, so it enters the run as
    a finding of its own and as an entry on the Journal Entries page."""
    run = dict(run)
    run["drafts"] = drafts
    ents = drafts.get("entries") or []
    if ents:
        run["findings"] = list(run.get("findings", [])) + [{
            "finding_id": e["finding_id"], "rule_id": "DRAFT", "title": e["memo"] or e["entry_id"],
            "severity": "medium", "kind": "needs_judgement", "period": run["manifest"].get("period"),
            "policy_basis": "", "policy_is_draft": False, "confidence": 0, "confidence_note": "",
            "amount_at_risk": e["debits"], "recommendation": e["support"],
            "evidence": {"observed": "", "expected": "", "basis": e["support"]},
            "drafted": True} for e in ents]
        views = dict(run.get("views") or {})
        views["entries"] = list(views.get("entries") or []) + ents
        run["views"] = views
    return run


# The exports a month needs, in the order Serif pulls them, and what each one feeds.
# A file counts as supplied when the engine or the schedules read it.
MONTHLY_EXPORTS = [
    ("netsuite_gl", "NetSuite Custom General Ledger saved search", "Every check"),
    ("coupa", "Coupa PO line report", "PO accounts, accruals and requesters"),
    ("forecast", "Rolling forecast, the month's cut", "Forecast vs. Actual"),
    ("plan", "Rolling forecast, the plan", "Actual vs. plan and planned coding"),
    ("hris_roster", "UKG roster", "Requester departments and withheld names"),
    ("netsuite_link_ids", "NetSuite link IDs, from the connector", "Links to NetSuite records"),
]


def exports_card(m, views):
    flux = "uc2" in str(m.get("ruleset_version", ""))
    got = {}
    for item in m.get("inputs", []):
        roles = item.get("roles") or (["netsuite_gl"] if str(item.get("path", "")).startswith("netsuite_gl")
                                      else ["coupa"] if str(item.get("path", "")).startswith("coupa") else [])
        for r in roles:
            got.setdefault(r, item)
    for item in views.get("inputs", []):
        role = {"forecast_workbook": "plan"}.get(item.get("role"), item.get("role"))
        got.setdefault(role, item)
    rows = []
    for role, label, feeds in MONTHLY_EXPORTS:
        if role == "forecast" and not flux:
            continue
        item = got.get(role)
        rows.append("<tr><td>" + esc(label) + "</td><td>"
                    + ('<span class="mono">' + esc(os.path.basename(str(item.get("path")))) + "</span>"
                       if item else '<span class="expmiss">Not supplied</span>')
                    + "</td><td>" + esc(feeds) + "</td></tr>")
    return ('<div class="card"><h3>Exports this month</h3>'
            '<div class="tblwrap"><table><thead><tr><th>Export</th><th>File</th>'
            '<th>Feeds</th></tr></thead><tbody>' + "".join(rows)
            + "</tbody></table></div></div>")


# A plain name for each check, for the list of what every check found.
CHECK_NAMES = {
    "T0.TIE_OUT": "Debits equal credits", "T0.DUPLICATE_LINE": "Duplicate postings",
    "T0.POSTING_LAG": "Posting lag", "T0.ABERRANT_POSTING_LAG": "Posting lag",
    "T1.DEPT_INCONSISTENCY": "Department against the vendor's usual coding",
    "T1.MISSING_PROJECT_CODE": "Missing project code", "T1.MEMO_FORMAT": "Memo format",
    "T1.VENDOR_NAME_VARIANTS": "Vendor name variants", "T1B.UNALLOCATED_SPEND": "Unallocated spend",
    "T4.PO_ACCOUNT_MISMATCH": "Account against the Coupa PO", "T4.OFF_PO_SPEND": "Spend with no PO",
    "T4.OPEN_COMMITMENTS": "Open PO commitments",
    "T3.IRC_274A_ENTERTAINMENT": "Entertainment, IRC 274(a)", "T3.IRC_274N_MEALS": "Meals, IRC 274(n)",
    "T3.IRC_274B_GIFTS": "Gifts, IRC 274(b)", "T3.IRC_174_BASE": "R&D base, IRC 174",
    "F1.VARIANCE": "Change on the prior month", "F2.BUDGET": "Actual against plan",
    "F3.ACCRUAL_RECEIPT": "Received, not invoiced", "F5.MODEL_TIE": "Forecast against the ledger",
    "F6.ACCRUAL_PATTERN": "Billing pattern accruals", "F7.REVENUE_IN_EXPENSE": "Customer documents in expense",
    "F8.VENDOR_DROPPED": "Vendor billing stopped", "F9.PREPAID": "May be prepaid",
    "F10.CAPITALIZE": "May be capital",
}


def checks_card(run):
    """Every check the engine ran, what it found and what it could not do. A check
    with no findings found nothing at or above its floor; none of them clears an
    item, which only a reviewer's decision does."""
    m = run.get("manifest", {})
    found, value = {}, {}
    # The posting lag check reports its measure and its stale bills under two ids.
    same = {"T0.ABERRANT_POSTING_LAG": "T0.POSTING_LAG"}
    for f in run.get("findings", []):
        r = same.get(f.get("rule_id"), f.get("rule_id"))
        found[r] = found.get(r, 0) + 1
        value[r] = value.get(r, 0) + abs(f.get("amount_at_risk") or 0)
    ran = list(m.get("rules_run") or [])
    if not ran:
        for g in (run.get("report") or {}).get("groups") or []:
            ran += [r for r in g.get("rules", []) if r not in ran]
    for r in found:
        if r not in ran:
            ran.append(r)
    notes = {x.get("rule_id"): x for x in m.get("rules_not_run") or []}
    if not ran:
        return ""
    rows = []
    for r in ran:
        n = notes.get(r)
        status = ("Ran with less to go on: " + str(n.get("reason", "")) if n and n.get("status") == "degraded"
                  else "Did not run: " + str(n.get("reason", "")) if n else "Ran")
        rows.append("<tr><td>" + esc(CHECK_NAMES.get(r, r)) + ' <span class="rid">' + esc(r)
                    + '</span></td><td class="num">' + format(found.get(r, 0), ",")
                    + '</td><td class="num">' + ("$" + format(value[r], ",.2f") if r in value else "")
                    + "</td><td>" + esc(status) + "</td></tr>")
    tie = (m.get("tie_out") or {}).get("note", "")
    return ('<div class="card" style="margin-top:var(--spacing-sm)"><h3>What each check found</h3>'
            '<p class="note">' + format(len(ran)) + " checks on " + esc(m.get("period", ""))
            + (", " + esc(tie) if tie else "") + ". A check with no findings found nothing at or above its "
            "floor. No check clears an item; only a reviewer's decision does.</p>"
            '<div class="tblwrap"><table><thead><tr><th>Check</th><th class="num">Findings</th>'
            '<th class="num">Value</th><th>Status</th></tr></thead><tbody>' + "".join(rows)
            + "</tbody></table></div></div>")


# ---------- the updated UI ----------
# `--layout ui-update` builds the same console with the updated page set: the
# executive overview, Actual vs. Actual (MoM), By Department (MoM), Payroll
# Analytics, Balance Sheet Flux, Adjustments and SOX & GAAP for the flux; CapEx,
# Prepaid, Dept & Entity, Reviewed & Cleared, New This Period, Audit Log and SOX
# Documentation for coding. The same decisions, records, exports and shared mode
# sit underneath. Every figure comes from the run and its views.

G_A_DEPARTMENTS = {"General G&A", "Finance"}


def _a0(v):
    """Accounting format, whole dollars, negatives in brackets."""
    if v is None:
        return "-"
    v = round(v)
    return ("($" + format(abs(v), ",") + ")") if v < 0 else "$" + format(v, ",")


def _sg(v):
    if v is None:
        return "-"
    return ("+" if round(v) > 0 else "") + _a0(v)


def _pc(v, base):
    return ("+" if v > 0 else "") + format(100.0 * v / abs(base), ".1f") + "%" if base else ""


def _fav(v, text=None):
    """An expense-signed move: a rise costs more, so it takes the accent."""
    text = text if text is not None else _sg(v)
    return '<span class="unfav">' + text + "</span>" if v is not None and round(v) > 0 else text


def _tile(k, v, s="", tip=""):
    return ('<div class="chtile"' + (' data-tip="' + esc(tip) + '"' if tip else "") + '><div class="k">' + k
            + '</div><div class="v">' + v + '</div><div class="s">' + s + "</div></div>")


def upd_vf(row):
    """Which vendor page a vendor row sits on in the updated UI. Each row is on one."""
    ids = [f.get("id") for f in row.get("flags") or []]
    if "capital" in ids:
        return "capex"
    if "prepaid" in ids:
        return "prepaid"
    if any(i not in ("new",) for i in ids):
        return "coding"
    if "new" in ids:
        return "new"
    return "clear"


def _bars(items, period, prior):
    """Diverging bars of expense-signed moves, with a tooltip on each."""
    top = max([abs(v) for _, v, _, _ in items] or [1]) or 1
    out = []
    for label, v, now, before in items:
        if round(v) == 0:
            continue
        tip = ("<b>" + esc(label) + "</b><br>" + esc(period) + " " + _a0(now) + "<br>" + esc(prior) + " "
               + _a0(before) + "<br>Change " + _sg(v) + ((" (" + _pc(v, before) + ")") if before else "")
               + "<br>" + ("Unfavorable: costs more" if v > 0 else "Favorable: costs less"))
        out.append('<div class="chbar" data-tip="' + esc(tip) + '"><span class="lab">' + esc(label.split(" - ", 1)[-1])
                   + '</span><span class="trk"><i class="mid"></i><i class="b ' + ("inc" if v > 0 else "dec")
                   + '" style="width:' + format(max(50.0 * abs(v) / top, 0.4), ".2f") + '%"></i></span><span class="val">'
                   + _sg(v) + "</span></div>")
    return ('<div class="chbars">' + "".join(out) + '</div><div class="chlegend"><span><i class="inc"></i>Unfavorable</span>'
            '<span><i class="dec"></i>Favorable</span></div>')


def _short(v):
    a = abs(v)
    s = ("$%.2fM" % (a / 1e6)) if a >= 1e6 else ("$%.0fK" % (a / 1e3)) if a >= 1e3 else "$%.0f" % a
    return s


def _waterfall(steps, total_label):
    """Net loss bridge: each step's reduction in the loss rises, an increase falls,
    and the last bar is the net. Favorable in grey, unfavorable in the accent."""
    run, bars = 0.0, []
    for label, delta, tip in steps:
        lo, hi = sorted((run, run + delta))
        bars.append((label, delta, lo, hi, tip, "fav" if delta > 0 else "unf"))
        run += delta
    lo, hi = sorted((0.0, run))
    bars.append((total_label, run, lo, hi, "<b>" + esc(total_label) + "</b><br>" + ("Net loss lower by " if run > 0 else "Net loss higher by ") + _a0(abs(run)), "net"))
    top = max([0.0] + [b[3] for b in bars]); bot = min([0.0] + [b[2] for b in bars])
    span = (top - bot) or 1.0
    pct = lambda v: 100.0 * (top - v) / span
    cols = []
    for label, delta, lo, hi, tip, cls in bars:
        cols.append('<div class="wf-col" data-tip="' + esc(tip) + '"><div class="wf-plot"><i class="wf-zero" style="top:' + format(pct(0), ".2f") + '%"></i>'
                    '<i class="wf-bar ' + cls + '" style="top:' + format(pct(hi), ".2f") + '%;height:' + format(max(pct(lo) - pct(hi), 0.6), ".2f") + '%"></i>'
                    '<span class="wf-val" style="top:calc(' + format(pct(hi), ".2f") + '% - 1.3em)">' + ("+" if delta > 0 else "-") + _short(delta) + '</span></div>'
                    '<div class="wf-lab">' + esc(label) + "</div></div>")
    return ('<div class="wf">' + "".join(cols) + '</div><div class="chlegend"><span><i class="dec"></i>Favorable: lowers the loss</span>'
            '<span><i class="inc"></i>Unfavorable: raises the loss</span><span><i class="netk"></i>Net change</span></div>')


def upd_flux_overview(run):
    m, views = run["manifest"], run.get("views") or {}
    tbl = (run.get("tables") or [None])[0]
    if not tbl:
        return ""
    secs = tbl["sections"]
    tot = lambda pre, k: sum((s["total"].get(k) or 0) for s in secs if s["label"][:1] in pre)
    opex = {k: tot("67", k) for k in ("actual", "prior", "prior_year")}
    net = {k: tot("678", k) for k in ("actual", "prior", "prior_year")}
    period = tbl.get("period") or m.get("period")
    prior = tbl.get("prior_period") or m.get("prior_period")
    py = m.get("prior_year_period") or "prior year"
    rows = [r for s in secs for r in s["rows"]]
    interest = next((s["total"] for s in secs if s["label"].startswith("8110000")), None)
    dm = views.get("dept_months") or {}
    opx = lambda r, k: sum(a[k] for a in r["accounts"] if a["account"][:1] in "67")
    ga_set = lambda r: r["department"] in G_A_DEPARTMENTS
    rd_set = lambda r: r["department"] not in G_A_DEPARTMENTS | {"Non-Specific"}
    ga = sum(opx(r, "actual") for r in dm.get("rows", []) if ga_set(r)); ga_p = sum(opx(r, "prior") for r in dm.get("rows", []) if ga_set(r))
    rd = sum(opx(r, "actual") for r in dm.get("rows", []) if rd_set(r)); rd_p = sum(opx(r, "prior") for r in dm.get("rows", []) if rd_set(r))
    hc = (views.get("payroll") or {}).get("headcount") or {}
    bs = views.get("balance_sheet") or {}
    brows = bs.get("rows", [])
    cash = next((r for r in brows if r["name"] == "Total Bank"), None)
    banks = []
    if cash:
        i = next(i for i, r in enumerate(brows) if r["name"] == "Bank")
        j = brows.index(cash)
        banks = [r for r in brows[i:j] if r["kind"] == "account" and round(r["values"].get(bs["period"]) or 0)]
    ent = views.get("entries") or []
    sev = (run.get("summary") or {}).get("by_severity") or {}
    F = {f["finding_id"]: f for f in run["findings"]}
    crit = sorted({(r["account_code"], r["account_leaf"]) for r in rows
                   if (F.get(r.get("mom_finding") or "") or {}).get("severity") == "high"}, key=lambda x: x[0])
    ch = lambda now, before: _fav(now - before) + " vs. " + esc(prior)
    tiles = [
        _tile("Total OpEx", _a0(opex["actual"]), ch(opex["actual"], opex["prior"])),
        _tile("Net Loss", _a0(net["actual"]), ch(net["actual"], net["prior"])),
        _tile("YoY Net Loss", _a0(net["actual"]), _fav(net["actual"] - net["prior_year"]) + " vs. " + esc(py)),
        _tile("Adj Pending", str(len(ent)), "Proposed Journal Entries"),
        _tile("R&amp;D Spend (" + esc(period[:3]) + ")", _a0(rd), ch(rd, rd_p),
              "<b>R&amp;D departments</b><br>" + "<br>".join(esc(r["department"]) for r in dm.get("rows", []) if rd_set(r))) if dm else "",
        _tile("G&amp;A Spend (" + esc(period[:3]) + ")", _a0(ga), ch(ga, ga_p),
              "<b>G&amp;A departments</b><br>" + "<br>".join(esc(d) for d in sorted(G_A_DEPARTMENTS))) if dm else "",
        _tile("Interest Income", _a0(-interest["actual"]), _fav(interest.get("mom_var") or 0, _sg(-(interest.get("mom_var") or 0)))
              + " vs. " + esc(prior)) if interest else "",
        _tile("Total Headcount", format(sum((hc.get("by_type") or {}).values()), ","),
              " &middot; ".join(esc(str(n) + " " + t) for t, n in (hc.get("by_type") or {}).items())) if hc else "",
        _tile("Cash &amp; Equiv. (" + esc(period[:3]) + " BS)", _a0(cash["values"].get(bs["period"])),
              " &middot; ".join(esc(re.sub(r"^\d{7} - (Serif - )?", "", r["name"])) + ": " + _short(r["values"][bs["period"]]) for r in banks)) if cash else "",
        _tile("Critical / Material Flags", str(sev.get("high", 0)) + " / " + str(sev.get("medium", 0)),
              ("Critical: " + ", ".join(esc(l) for _, l in crit[:4]) + ("" if len(crit) <= 4 else ", and " + str(len(crit) - 4) + " more")) if crit else "",
              "<b>Engine severity</b><br>Critical is high, material is medium"),
    ]
    movers = sorted([r for r in rows if round(r.get("mom_var") or 0)], key=lambda r: -abs(r["mom_var"]))
    top, rest = movers[:7], movers[7:]
    steps = []
    for r in top:
        d = -r["mom_var"]
        steps.append((r["account_leaf"], d, "<b>" + esc(r["account_code"] + " " + r["account_leaf"]) + "</b><br>" + esc(period) + " " + _a0(r["actual"])
                      + "<br>" + esc(prior) + " " + _a0(r["prior"]) + "<br>" + ("Lowers the loss by " if d > 0 else "Raises the loss by ") + _a0(abs(d))))
    if rest:
        d = -sum(r["mom_var"] for r in rest)
        steps.append(("Other", d, "<b>Other accounts</b><br>" + str(len(rest)) + " accounts<br>" + ("Lowers the loss by " if d > 0 else "Raises the loss by ") + _a0(abs(d))))
    wf = _waterfall(steps, "Net change")
    return ('<div class="chtiles">' + "".join(t for t in tiles if t) + "</div>"
            '<div class="card chsec"><h3>Variance Waterfall: Net Loss MoM (' + esc(period[:3]) + " vs. " + esc(prior[:3]) + " " + esc(period[-4:]) + ")</h3>" + wf + "</div>")


def upd_gl_overview(run):
    views = run.get("views") or {}
    vend = next((t for t in views.get("tables") or [] if t["id"] == "vendors"), None)
    if not vend:
        return ""
    rows = [r for s in vend["sections"] for r in s["rows"] if round(r.get("amount") or 0)]
    by = {}
    for r in rows:
        by.setdefault(upd_vf(r), []).append(r)
    amt = lambda k: sum(r.get("amount") or 0 for r in by.get(k, []))
    billed = [r for r in rows if round(r.get("amount") or 0)]
    tie = run["manifest"].get("tie_out") or {}
    coupa = next((i for i in run["manifest"].get("inputs", [])
                  if "coupa" in (i.get("roles") or []) or "coupa" in (i.get("path") or "").lower()), {})
    spend = sum(r.get("amount") or 0 for r in billed)
    sev = (run.get("summary") or {}).get("by_severity") or {}
    at_risk = sum(f.get("amount_at_risk") or 0 for f in run["findings"])
    tiles = [_tile("Total Flags", format(len(run["findings"]), ","), "Findings this month"),
             _tile("Flagged Amount", _a0(at_risk), (format(100.0 * at_risk / spend, ".1f") + "% of period spend") if spend else ""),
             _tile("Total period spend", _a0(spend), str(len(billed)) + " vendors billed")]
    return '<div class="chtiles">' + "".join(tiles) + "</div>"


def upd_pre(run):
    """What sits above a schedule in the updated UI."""
    views, pre = run.get("views") or {}, {}
    dm = views.get("dept_months")
    if dm:
        rows = "".join(
            '<details class="chdept"><summary><span class="d">' + esc(r["department"]) + '</span><span class="n">'
            + _a0(r["actual"]) + '</span><span class="n">' + _a0(r["prior"]) + '</span><span class="n">' + _fav(r["change"])
            + "</span></summary><table class=\"evtxn\"><tbody>"
            + "".join("<tr><td>" + esc(a["account"] + " " + (a["leaf"] or "")) + '</td><td class="num">' + _a0(a["actual"])
                      + '</td><td class="num">' + _a0(a["prior"]) + '</td><td class="num">' + _fav(a["change"]) + "</td></tr>"
                      for a in r["accounts"]) + "</tbody></table></details>" for r in dm["rows"])
        pre["dept_plan"] = ('<div class="card chsec"><h3>By department, ' + esc(dm["prior_period"]) + " to " + esc(dm["period"])
                            + '</h3><div class="chdept chhead"><span class="d">Department</span><span class="n">' + esc(dm["period"])
                            + '</span><span class="n">' + esc(dm["prior_period"]) + '</span><span class="n">Change</span></div>'
                            + rows + "</div>")
    pa = views.get("payroll")
    if pa:
        t = pa["total"]
        tiles = ('<div class="chtiles">' + _tile("Employee expense", _a0(t["total"]), _fav(t["total"] - t["prior_total"]) + " vs. prior month")
                 + _tile("Salaries", _a0(t["salaries"]), "Bonus " + _a0(t["bonus"]))
                 + _tile("Payroll tax rate", (format(t["tax_pct"], ".1f") + "%") if t.get("tax_pct") is not None else "-", "Of salaries")
                 + _tile("Benefits rate", (format(t["benefits_pct"], ".1f") + "%") if t.get("benefits_pct") is not None else "-", "Of salaries")
                 + _tile("On payroll", format(pa["headcount"]["payroll"], ","), " &middot; ".join(
                     esc(str(n) + " " + k) for k, n in pa["headcount"]["by_type"].items())) + "</div>")
        head = ("<thead><tr><th>Department</th><th class=\"num\">People</th><th class=\"num\">Salaries</th><th class=\"num\">Bonus</th>"
                "<th class=\"num\">Payroll tax</th><th class=\"num\">Benefits</th><th class=\"num\">Total</th><th class=\"num\">Prior month</th>"
                "<th class=\"num\">Tax rate</th></tr></thead>")
        body = "".join("<tr><td><b>" + esc(r["department"]) + '</b></td><td class="num">' + str(r["headcount"]) + "</td>"
                       + "".join('<td class="num">' + _a0(r.get(k)) + "</td>" for k in ("salaries", "bonus", "taxes", "benefits", "total", "prior_total"))
                       + '<td class="num">' + ((format(r["tax_pct"], ".1f") + "%") if r.get("tax_pct") is not None else "-") + "</td></tr>"
                       for r in pa["rows"])
        body += ('<tr class="tot"><td><b>Total</b></td><td class="num">' + str(pa["headcount"]["payroll"]) + "</td>"
                 + "".join('<td class="num"><b>' + _a0(t.get(k)) + "</b></td>" for k in ("salaries", "bonus", "taxes", "benefits", "total", "prior_total"))
                 + '<td class="num">' + ((format(t["tax_pct"], ".1f") + "%") if t.get("tax_pct") is not None else "-") + "</td></tr>")
        roster = "".join(
            '<details class="chdept"><summary><span class="d">' + esc(r["department"]) + '</span><span class="n">'
            + str(len(r.get("people") or [])) + " people</span></summary><table class=\"evtxn\"><thead><tr><th>Name</th><th>Title</th>"
            "<th>Type</th><th class=\"num\">Annual salary</th><th class=\"num\">Monthly</th><th class=\"num\">Bonus target</th></tr></thead><tbody>"
            + "".join("<tr><td>" + esc(p["name"]) + "</td><td>" + esc(p["title"]) + "</td><td>" + esc(p["type"]) + '</td><td class="num">'
                      + _a0(p["salary"]) + '</td><td class="num">' + _a0((p["salary"] or 0) / 12.0) + '</td><td class="num">'
                      + ((format(p["bonus_pct"], ".0f") + "%") if p.get("bonus_pct") else "-") + "</td></tr>"
                      for p in r.get("people") or []) + "</tbody></table></details>"
            for r in pa["rows"] if r.get("people"))
        pre["payroll_hris"] = (tiles + '<div class="card chsec"><h3>Compensation by department, ' + esc(pa["period"]) + "</h3>"
                               '<div class="tblwrap"><table class="sched">' + head + "<tbody>" + body + "</tbody></table></div></div>"
                               + ('<div class="card chsec"><h3>Department detail</h3>' + roster + "</div>" if roster else "")
                               + '<h3 class="chsech">Payroll vs. HRIS</h3>')
    vend = next((t for t in views.get("tables") or [] if t["id"] == "vendors"), None)
    if vend:
        rows = [r for s in vend["sections"] for r in s["rows"]]
        for key, label in (("capex", "CapEx Flags"), ("prepaid", "Prepaid Flags"), ("coding", "Dept &amp; Entity"),
                           ("clear", "Reviewed &amp; Cleared"), ("new", "New This Period")):
            mine = [r for r in rows if upd_vf(r) == key and round(r.get("amount") or 0)]
            pre["vendors|" + key] = ('<div class="chtiles">' + _tile(label, str(len(mine)) + " vendors",
                                     _a0(sum(r.get("amount") or 0 for r in mine)) + " this month") + "</div>")
    return pre


def upd_sox(run):
    """The SOX page: source data, the tie-out, the policies applied."""
    m = run["manifest"]
    inputs = "".join("<tr><td>" + esc(i.get("path")) + "</td><td>" + esc(", ".join(i.get("roles") or [])) + '</td><td class="num">'
                     + format(i.get("rows") or 0, ",") + '</td><td class="mono">' + esc((i.get("sha256") or "")[:16]) + "</td></tr>"
                     for i in m.get("inputs", []))
    vin = "".join("<tr><td>" + esc(i.get("path")) + "</td><td>" + esc(i.get("role") or "") + '</td><td class="num">'
                  + format(i.get("rows") or 0, ",") + "</td><td></td></tr>" for i in (run.get("views") or {}).get("inputs", [])
                  if i.get("path") not in {x.get("path") for x in m.get("inputs", [])})
    tie = m.get("tie_out") or {}
    counts, amounts, basis = {}, {}, {}
    for f in run["findings"]:
        r = f.get("rule_id")
        counts[r] = counts.get(r, 0) + 1
        amounts[r] = amounts.get(r, 0) + abs(f.get("amount_at_risk") or 0)
        basis.setdefault(r, f.get("policy_basis") or "")
    rules = list(m.get("rules_run") or []) or sorted(counts)
    pol = "".join("<tr><td>" + esc(CHECK_NAMES.get(r, r)) + '</td><td class="mono">' + esc(r) + '</td><td class="num">'
                  + str(counts.get(r, 0)) + '</td><td class="num">' + _a0(amounts.get(r, 0)) + "</td><td>" + esc(basis.get(r, "")) + "</td></tr>"
                  for r in rules)
    notrun = "".join("<li>" + esc((x.get("rule_id") or "") + ": " + (x.get("reason") or "")) + "</li>" for x in m.get("rules_not_run") or [])
    absent = "".join("<li>" + esc(a.get("feed") + ": " + a.get("suppresses", "")) + "</li>" for a in m.get("absent_feeds") or [])
    drafts = (run.get("drafts") or {})
    nd = sum(len(v) if isinstance(v, (list, dict)) else 1 for v in drafts.values())
    return ('<div class="card chsec"><h3>Source Data Validation</h3><div class="tblwrap"><table class="sched"><thead><tr><th>File</th>'
            '<th>Read as</th><th class="num">Rows</th><th>Fingerprint</th></tr></thead><tbody>' + inputs + vin + "</tbody></table></div></div>"
            '<div class="card chsec"><h3>GL Tie-Out</h3><p class="note">' + ("Pass. " if tie.get("passed") else "Fail. ") + esc(tie.get("note") or "")
            + "</p></div>"
            '<div class="card chsec"><h3>Policy Application Summary</h3><div class="tblwrap"><table class="sched"><thead><tr><th>Check</th>'
            '<th>Rule</th><th class="num">Findings</th><th class="num">Amount</th><th>Policy</th></tr></thead><tbody>' + pol + "</tbody></table></div>"
            + ("<h4>Ran with less to go on</h4><ul class=\"chfacts\">" + notrun + "</ul>" if notrun else "")
            + ("<h4>Feeds not supplied</h4><ul class=\"chfacts\">" + absent + "</ul>" if absent else "") + "</div>"
            '<div class="card chsec"><h3>AI Disclosure</h3><p class="note">Findings, figures and entries are computed by the '
            + esc(m.get("engine_version") and ("engine " + m["engine_version"]) or "engine") + " from the exports. Claude drafted "
            + str(nd) + " item" + ("" if nd == 1 else "s") + ", each marked Drafted by Claude. The reviewer decides every item.</p></div>")


def build(run, source_name, layout="standard"):
    m = run["manifest"]
    tie = m.get("tie_out", {})
    passed = bool(tie.get("passed"))
    upd = layout == "ui-update"
    report = run.get("report") or {}
    title = report.get("title") or "GL Coding Review"
    inputs = ", ".join(i.get("path", "") for i in m.get("inputs", []))

    # An engine that declares no groups gets the coding defaults, which is the
    # case for the bundled GL Coding Review engine. This has to happen BEFORE the
    # payload is serialized: the page reads its groups from the payload, so a
    # later mutation would leave the rail and the list working from different
    # lists with different labels.
    if not report.get("groups"):
        report = dict(report)
        report["groups"] = DEFAULT_GROUPS
        run["report"] = report

    payload = json.dumps(run, ensure_ascii=False).replace("</", "<\\/")

    absent = [f for f in m.get("absent_feeds", []) if f.get("in_uc1_scope")]

    # Each analysis type gets its own rail entry, because that is how the work is
    # actually done: consistency first, then plan, then tax. A single combined
    # queue asks the reviewer to hold all three questions at once.
    #
    # "All findings" stays at the top of that block. Working one list top to bottom
    # is a legitimate way through, and losing it would trade one constraint for
    # another. The rail offers both rather than picking for the reviewer.
    #
    # Built from the run's own groups, so a console shows the analyses its engine
    # produced and nothing else. A group with no findings this period is dropped
    # rather than rendered as an empty page.
    rule_counts = {}
    for finding in run.get("findings", []):
        rule_counts[finding.get("rule_id")] = rule_counts.get(finding.get("rule_id"), 0) + 1

    groups = [g for g in (report.get("groups") or [])
              if any(rule_counts.get(r) for r in (g.get("rules") or []))]
    layers = sorted((report.get("layers") or []), key=lambda l: l.get("order", 0))
    layer_order = {l.get("id"): i for i, l in enumerate(layers)}
    groups.sort(key=lambda g: layer_order.get(g.get("layer"), 99))

    # Every rail entry is one page, so every rail entry gets one style. Hierarchy
    # is carried by the section headings alone, never by indenting an item or
    # shrinking its type. Encoding one level of nesting three ways produced three
    # sizes in one rail and two consoles that disagreed with each other.
    #
    # The sections are the same in both consoles: the overview, the review work,
    # then the record of the run. Only the middle section's headings differ, and
    # they differ because the content does. A run with layers names them; a run
    # without gets one heading over its analyses.
    # (view, label, group, heading)
    #
    # Overview and All findings sit ungrouped at the top: both read the whole run,
    # so no heading describes them better than their own labels. Everything below
    # is a group of pages with something in common, and each says what that is.
    # A run with layers names them; a run without gets one heading over its
    # analyses.
    views = run.get("views") or {}
    vtables = {t["id"]: t for t in (views.get("tables") or [])}
    entries = views.get("entries") or []

    def page(view, label, group=None, heading=None, cmp=None, vt=None, count=None, vf=None):
        return {"view": view, "label": label, "group": group, "heading": heading,
                "cmp": cmp, "vt": vt, "count": count, "vf": vf}

    # A run carrying schedules is worked on its schedules, one page per job, in
    # the order of the close. A run without them keeps the combined queue.
    tbl = (run.get("tables") or [None])[0]
    PG = LABELS["pages"]
    if vtables:
        nav = [page("overview", PG["overview"])]
        vt_page = lambda tid, heading=None: page("vtable", VIEW_PAGE_LABELS.get(tid, vtables[tid]["title"]),
                                                  heading=heading, vt=tid, count="vt:" + tid)
        if tbl:
            adj = [t for t in ("model_tie", "accrual", "prepaid", "reclass") if t in vtables]
            nav += [vt_page(t, PG["adjustments"] if i == 0 else None) for i, t in enumerate(adj)]
            if entries:
                nav.append(page("entries", PG["entries"], heading=None if adj else PG["adjustments"],
                                count="__entries"))
            # The prior year shows as a column on Actual vs. Actual; it does not
            # need commentary of its own.
            cmps = [c["id"] for c in tbl.get("comparisons", []) if c["id"] != "yoy"]
            nav += [page("table", TABLE_PAGE_LABELS.get(c, c), heading=PG["flux"] if i == 0 else None, cmp=c)
                    for i, c in enumerate(cmps)]
        else:
            rev = [t for t in ("vendors", "checks", "payroll_hris") if t in vtables]
            nav += [vt_page(t, PG["review"] if i == 0 else None) for i, t in enumerate(rev)]
            if entries:
                nav.append(page("entries", PG["entries"], heading=None if rev else PG["review"],
                                count="__entries"))
        nav.append(page("decisions", PG["decisions"], heading=PG["record"]))
        groups = []
        if upd:
            # Sections in the bar; a section's pages open beside its title.
            def section(title, items):
                for i, it in enumerate(items):
                    it["heading"] = title if i == 0 else None
                return items
            pg = lambda view, label, **kw: page(view, label, **kw)
            if tbl:
                analysis = [pg("table", "Actual vs. Actual (MoM)", cmp="mom"), pg("table", "Actual vs. Budget", cmp="budget")]
                if "dept_plan" in vtables:
                    analysis.append(pg("vtable", "By Department (MoM)", vt="dept_plan", count="vt:dept_plan"))
                if "payroll_hris" in vtables:
                    analysis.append(pg("vtable", "Payroll Analytics", vt="payroll_hris", count="vt:payroll_hris"))
                close = []
                if views.get("balance_sheet"):
                    close.append(pg("bsflux", "Balance Sheet Flux"))
                if entries:
                    close.append(pg("entries", "Adjustments", count="__entries"))
                close.append(pg("decisions", "SOX & GAAP"))
                if entries:
                    close.append(pg("export", "Export"))
                nav = (section("Executive Overview", [pg("overview", "Executive Overview")])
                       + section("Analysis", analysis) + section("Close Workflow", close))
            else:
                vfp = lambda key, label: pg("vtable", label, vt="vendors", count="vt:vendors", vf=key)
                nav = (section("Overview", [pg("overview", "Overview")])
                       + section("Review", [vfp("capex", "CapEx Flags"), vfp("prepaid", "Prepaid Flags"), vfp("coding", "Dept & Entity")])
                       + section("Transparency", [vfp("clear", "Reviewed & Cleared"), vfp("new", "New This Period")])
                       + section("Documentation", [pg("audit", "Audit Log"), pg("decisions", "SOX Documentation")]
                                 + ([pg("entries", "Export", count="__entries")] if entries else [])))
    else:
        nav = [page("overview", PG["overview"]), page("review", PG["all_findings"])]
    seen_layer = object()
    for i, g in enumerate(groups):
        heading = None
        if len(layers) > 1:
            if g.get("layer") != seen_layer:
                seen_layer = g.get("layer")
                heading = next((l.get("label") for l in layers
                                if l.get("id") == seen_layer), None)
        elif i == 0:
            heading = PG["review"]
        # A group whose findings the views step laid out as a schedule opens on the
        # schedule: an accrual list or a reconciliation is read as a table, the way
        # it sits in the close binder. The findings stay in All findings.
        table = next((t for t in vtables.values() if t.get("group") == g.get("id")), None)
        if table:
            nav.append(page("vtable", VIEW_PAGE_LABELS.get(table["id"], table["title"]),
                            heading=heading, vt=table["id"], count=g.get("id")))
        else:
            nav.append(page("review", g.get("label") or g.get("id"), group=g.get("id"),
                            heading=heading, count=g.get("id")))
    # The Journal Entries page closes the adjustments: every correction as the
    # entry that books it. It sits with the accounting layer where there is one.
    je_page = page("entries", PG["entries"], count="__entries") if entries and not vtables else None
    if je_page and len(layers) > 1:
        last_acct = max((i for i, e in enumerate(nav)
                         if e["view"] == "vtable" or (e["group"] and any(
                             g.get("id") == e["group"] and g.get("layer") == layers[0].get("id")
                             for g in groups))), default=None)
        if last_acct is not None:
            nav.insert(last_acct + 1, je_page)
            je_page = None
    # Each comparison in the pack becomes its own rail entry. The variance
    # findings behind them come off the rail, because the table is the better
    # route to the same rows: it shows every account rather than only the flagged
    # ones, and each flagged row links through to its evidence. They stay
    # reachable from All findings.
    if tbl and not vtables:
        nav = [e for e in nav if e["group"] not in ("variance", "budget")]
        for i, c in enumerate(tbl.get("comparisons", [])):
            nav.append(page("table", TABLE_PAGE_LABELS.get(c["id"], c["label"]),
                            heading=PG["flux"] if i == 0 else None, cmp=c["id"]))
        for tid in ("dept_plan", "payroll_hris"):
            if tid in vtables:
                nav.append(page("vtable", VIEW_PAGE_LABELS[tid], vt=tid))
    # The coding schedules: the period laid out by vendor and by department,
    # beside the exception queue rather than instead of it.
    if je_page:
        nav.append(je_page)
    if not vtables:
        nav += [page("decisions", PG["decisions"], heading=PG["record"]),
                page("health", "Coding health"),
                page("coverage", "Not tested")]

    p = []
    a = p.append
    a("<!doctype html>")
    a('<html lang="en"><head><meta charset="utf-8">')
    a('<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">')
    # The title names a published Artifact in the gallery: one per close month.
    a("<title>Serif " + esc(title) + " - " + esc(m.get("period")) + "</title>")
    a('<meta name="generator" content="Serif review console ' + esc(CONSOLE_VERSION)
      + "; engine " + esc(m.get("engine_version"))
      + "; ruleset " + esc(m.get("ruleset_version"))
      + "; run " + esc(m.get("run_id")) + '">')
    a("<style>" + FONT_CSS + CSS + "</style></head>")
    a('<body data-palette="' + STATE_PALETTE + '"' + (' class="uiupd"' if upd else "") + ">")
    a('<div id="tip"></div><div id="toast"></div>')
    a('<dialog class="ask" id="ask"><form method="dialog" class="inner">'
      '<h3 id="ask-title"></h3><p id="ask-body"></p>'
      '<label class="asktype" id="ask-typewrap" hidden><span id="ask-typelab"></span>'
      '<input type="text" id="ask-type" autocomplete="off" spellcheck="false"></label>'
      '<div class="acts">'
      '<button class="pill pill--knockout" value="cancel">Cancel</button>'
      '<button class="pill" value="ok" id="ask-ok"></button>'
      "</div></form></dialog>")
    a('<div class="app">')

    # The top bar: the wordmark and run, then the pages and the groups of pages, the
    # review threshold, and the version. A group's pages are tabs under the page
    # title, so a reviewer moves between them without the bar; the group's button in
    # the bar opens its last page. A group with one page is a plain page button.
    # Every page button carries its group heading, which the close checklist reads.
    groups = []
    for item in nav:
        if item["heading"] or not groups:
            groups.append({"heading": item["heading"], "items": []})
        groups[-1]["items"].append(item)

    def page_button(item, heading, cls=""):
        attrs = ('<button' + (' class="' + cls + '"' if cls else "") + ' data-view="' + item["view"]
                 + '" data-label="' + esc(item["label"]) + '" data-head="' + esc(heading or "") + '"')
        if item["group"]:
            attrs += ' data-group="' + esc(item["group"]) + '"'
        if item["cmp"]:
            attrs += ' data-cmp-page="' + esc(item["cmp"]) + '"'
        if item["vt"]:
            attrs += ' data-vt="' + esc(item["vt"]) + '"'
        if item.get("vf"):
            attrs += ' data-vf="' + esc(item["vf"]) + '"'
        return (attrs + "><span>" + esc(item["label"]) + "</span>"
                + ('<b class="navct" data-navct="' + esc(item["count"]) + '"></b>'
                   if item["count"] else "")
                + "</button>")

    a('<header class="tnav">')
    a('<div class="tb">' + LOGO + "<b>" + esc(title) + "</b><span>" + esc(m.get("period"))
      + "</span></div>")
    a('<nav class="nav" aria-label="Pages">')
    for k, g in enumerate(groups):
        a('<div class="tg">')
        if not g["heading"] or len(g["items"]) == 1:
            for item in g["items"]:
                a(page_button(item, g["heading"], "tbtn"))
        else:
            a('<button class="tbtn tgt" type="button" data-grp="' + str(k) + '"><span>'
              + esc(g["heading"]) + '</span><b class="navct" data-grpct></b></button>')
            if upd:
                # The section's pages, beside its title, shown while it is open.
                a('<div class="stabs nav tsub" data-grp="' + str(k) + '" aria-label="' + esc(g["heading"]) + '" hidden>')
                for item in g["items"]:
                    a(page_button(item, g["heading"], "tbtn"))
                a("</div>")
        a("</div>")
    a("</nav>")
    if upd:
        # Settings holds the threshold.
        a('<div class="nav trun tset"><button class="tbtn" type="button" data-view="settings" data-label="Settings" data-tip="Settings" aria-label="Settings">'
          '<svg class="ico" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.4"'
          ' stroke-linecap="round"><path d="M2.5 4.5h7M12.5 4.5h1M2.5 11.5h1M6.5 11.5h7"/><circle cx="11" cy="4.5" r="1.5"/>'
          '<circle cx="5" cy="11.5" r="1.5"/></svg><span>Settings</span></button></div>')
    if vtables and not upd:
        # One setting decides every page's counts, so it sits on every page.
        a('<div class="tthr"><label for="fixinput">Review over</label><span class="fx">$'
          '<input type="text" inputmode="numeric" id="fixinput" autocomplete="off" '
          'aria-label="Review threshold in dollars"></span></div>')
        # Who is reviewing, recorded with each decision for the audit trail. A
        # setting of this browser, like the threshold, so it sits in the bar.
        a('<div class="tthr twho"><label for="whoinput">Reviewer</label><span class="fx">'
          '<input type="text" id="whoinput" autocomplete="name" spellcheck="false" placeholder="Your name"'
          ' aria-label="Your name, recorded with each decision"></span></div>')
    cost = cost_estimate(os.path.dirname(os.path.abspath(__file__)), run)
    # The run log holds what went in, what each check found, the cost and the build
    # record; the versions are on it, not in the bar.
    a('<div class="nav trun"><button class="tbtn" type="button" data-view="runlog" data-label="Run log"'
      + (' data-tip="Run log" aria-label="Run log">' if upd else
         ' title="Console ' + esc(CONSOLE_VERSION) + " · Engine " + esc(m.get("engine_version"))
         + " · Run " + esc(str(m.get("run_id", ""))[:12]) + '">')
      + '<svg class="ico" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor"'
      ' stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">'
      '<rect x="3" y="1.75" width="10" height="12.5" rx="1.5"/><path d="M5.75 5.5h4.5M5.75 8h4.5M5.75 10.5h2.5"/>'
      '</svg><span>Run log</span></button></div>')
    a("</header>")

    a('<div class="main">' + CURVE_FIELD)
    # Shown only when the page runs as a published Artifact with a shared database.
    a('<div class="sharedbar" id="sharedbar" role="status" hidden></div>')
    a('<div class="topbar"><span id="crumb">Overview</span>')
    for k, g in enumerate(groups):
        if g["heading"] and len(g["items"]) > 1 and not upd:
            a('<div class="stabs nav" data-grp="' + str(k) + '" aria-label="' + esc(g["heading"])
              + '" hidden>')
            for item in g["items"]:
                a(page_button(item, g["heading"]))
            a("</div>")
    a("</div>")
    if not passed:
        a('<div class="tiefail">Tie-out failed: ' + esc(tie.get("note"))
          + ". Findings are not trustworthy until the ledger balances.</div>")

    # overview
    a('<section class="view" id="v-overview">')
    if vtables:
        # The close as a checklist: every page, what is left on it, and what that
        # is worth.
        a('<div class="warnbox" id="storewarn" hidden><b>Decisions are not being saved.</b> '
          "This browser will not store them for a file opened from disk, so your work is held "
          "in memory only. Export before you close the tab.</div>")
        # What is left to do comes first. Then the tick-and-tie that shows every
        # item is either worked or counted under the threshold, and the amount
        # bands that add up to the same whole. Claude's summary sits last: it
        # restates, and the reviewer came here to act.
        if upd:
            a(upd_flux_overview(run) if tbl else upd_gl_overview(run))
        if not (upd and tbl):
            a('<div class="card"><h3>Close checklist</h3>'
              '<div class="tblwrap"><table class="sched" id="checklist"></table></div></div>')
            if upd:
                a('<div class="card" style="margin-top:var(--spacing-sm)"><h3>Items by amount</h3><div id="thchart"></div></div>')
            else:
                a('<div class="grid charts" style="margin-top:var(--spacing-sm)">')
                a('<div class="card"><h3>Tick and tie</h3><div id="tietbl"></div></div>')
                a('<div class="card"><h3>Items by amount</h3><div id="thchart"></div></div>')
                a("</div>")
            a('<div class="card" style="margin-top:var(--spacing-sm)"><h3>Value left by page</h3>'
              '<div id="groupchart"></div></div>')
            a('<div class="card summary" id="summarycard" style="margin-top:var(--spacing-sm)" hidden></div>')
        a("</section>")
    else:
        a('<div class="grid g3" id="kpis"></div>')
        a('<div class="grid charts" style="margin-top:var(--spacing-sm)">')
        a('<div class="card"><h3>Items by threshold</h3><div id="thchart"></div></div>')
        a('<div class="card"><h3>Value by category</h3><div id="groupchart"></div></div>')
        a('<div class="card"><h3>Findings by basis</h3><div id="kindchart"></div></div>')
        a("</div>")
        # Collapsed by default: the total is the point, the department breakdown is
        # there for anyone asking whether the threshold is set right.
        a('<details class="card fold" style="margin-top:var(--spacing-sm)">'
          '<summary><h3 id="belowhead">Items below threshold</h3>'
          '<span class="sub" id="belowsum"></span>'
          '<span class="cue"><span class="cue-open">Show breakdown</span>'
          '<span class="cue-close">Hide breakdown</span>'
          '<span class="caret" aria-hidden="true">&rsaquo;</span></span></summary>'
          '<div class="foldbody" id="belowcard"></div></details>')
        a('<div class="nextstep" id="next-overview"></div>')
        a("</section>")

    # review: the combined queue, for a run that carries no schedules
    if not vtables:
        a('<section class="view" id="v-review" hidden>')
        a('<div class="warnbox" id="storewarn" hidden><b>Decisions are not being saved.</b> '
          "This browser will not store them for a file opened from disk, so your work is held in "
          "memory only. Export before you close the tab.</div>")
        # Two bands, because these are two different kinds of thing. The top row holds
        # the setting that changes what the run means and the action that changes how
        # you work it. Below that, the filters, each on a labeled row -- unlabeled
        # stacked chip rows give no clue which control does what.
        a('<div class="setrow">'
          '<div class="throw"><label for="fixinput">Fix anything over</label>'
          '<span class="fixfield"><span class="cur">$</span>'
          '<input type="number" id="fixinput" min="0" step="500" '
          'aria-label="Fix threshold in dollars"></span></div>'
          '<button class="belowline" id="belowline" type="button"></button>'
          '<button class="pill pill--go act" id="focus-start">' + EYE_ICON + "Focus mode</button>"
          "</div>")
        a('<div class="filters" role="group" aria-label="Filter findings">')
        for label, target in (("Decision", "queueChips"), ("Amount", "bandChips"),
                              ("Basis", "kindChips")):
            a('<span class="flabel" id="lab-' + target + '">' + label + "</span>")
            a('<div class="fchips" id="' + target + '" aria-labelledby="lab-' + target
              + '"></div>')
        a('<label class="flabel" for="q">Search</label>')
        a('<div class="fchips"><input type="search" id="q" '
          'placeholder="Vendor, account, memo…" aria-label="Search findings"></div>')
        a("</div>")
        a('<p class="coverage" id="matline"></p>')
        a('<div class="work"><div class="list" id="list" role="listbox" aria-label="Findings"></div>'
          '<div class="detail" id="detail"></div></div>')
        a('<div id="focus" hidden><div class="focus-inner">'
          '<div class="focus-bar"><span id="focus-pos" class="secondary"></span>'
          '<button class="pill pill--knockout" id="focus-exit">Back to the list</button></div>'
          '<div class="focus-keys" id="focus-keys"></div>'
          '<div id="focus-card"></div>'
          "</div></div>")
        a('<div class="nextstep" id="next-review"></div>')
        a("</section>")

    # decisions
    if run.get("tables"):
        a('<section class="view" id="v-table" hidden>')
        a('<div class="vtbar">' + '<span class="seg" id="fluxseg" role="group" aria-label="Read the plan by" hidden>'
          '<button type="button" data-seg="acct">By account</button>'
          '<button type="button" data-seg="dept">By department</button></span>'
          '<input type="search" id="fxq" placeholder="Account or section" aria-label="Search the flux pack">'
          '<button class="pill pill--knockout active" id="fxonly" aria-pressed="true">Show unflagged lines</button></div>')
        a('<div class="vtalert" id="fluxalert" role="note" hidden></div>')
        a('<div class="card schedwrap"><table class="sched fluxtbl" id="fluxtbl"></table></div>')
        a("</section>")
    if views.get("tables"):
        a('<section class="view" id="v-vtable" hidden>')
        a('<div id="vtpre"></div>')
        a('<div class="vtbar">' + '<span class="seg" id="vtseg" role="group" aria-label="Read the plan by" hidden>'
          '<button type="button" data-seg="acct">By account</button>'
          '<button type="button" data-seg="dept">By department</button></span>' +
          '<input type="search" id="vtq" placeholder="Vendor, account, department"'
          ' aria-label="Search this schedule">'
          '<button class="pill pill--knockout" id="vtonly" aria-pressed="false">'
          'Show unflagged lines</button>'
          '<button class="pill pill--knockout" id="vtblank" aria-pressed="false" hidden></button>'
          ''
          '<button class="pill pill--knockout" data-export="questions" id="vtq-export" hidden '
          'style="margin-left:auto">Questions, CSV</button></div>')
        a('<div class="vtalert" id="vtalert" role="note" hidden></div>')
        a('<div class="card schedwrap"><table class="sched" id="vttbl"></table></div>')
        a('<div id="vtpost"></div>')
        a("</section>")
    if entries:
        a('<section class="view" id="v-entries" hidden>')
        a('<div class="vtbar"><span class="fchips">'
          + "".join('<button class="pill pill--knockout" data-jef="' + k + '">' + lab + "</button>"
                    for k, lab in (("all", "All"), ("open", "Open"), ("book", LABELS["outcomes"]["entry"]),
                                   ("no_entry", LABELS["outcomes"]["clear"])))
          + '</span><span class="inl" style="margin-left:auto">'
          '<button class="pill pill--knockout" data-export="audit">Audit trail, CSV</button>'
          '<button class="pill" data-export="netsuite">NetSuite import, CSV</button></span></div>')
        a('<div class="vtalert" id="jealert" role="note" hidden></div>')
        if upd and not tbl:
            # Export: the NetSuite file and the finish step, then the entries it holds.
            a('<div class="card dnext" id="dnext"></div>')
            a('<div class="card dfinish" id="finish" style="margin-top:var(--spacing-sm)" hidden></div>')
            a('<h3 class="chsech">Journal Entries</h3>')
        if upd and tbl:
            a('<h3 class="chsech">Section A: Accounting Adjustments</h3>')
        a('<div class="card schedwrap"><table class="sched" id="jetbl"></table></div>')
        a('<div id="adjextra"></div>')
        a("</section>")
    if upd and views.get("balance_sheet"):
        a('<section class="view" id="v-bsflux" hidden>')
        a('<div class="vtbar"><input type="search" id="bsq" placeholder="Account" aria-label="Search the balance sheet">'
          '<button class="pill pill--knockout active" id="bsonly" aria-pressed="true">Show unflagged lines</button></div>')
        a('<div class="card schedwrap"><table class="sched" id="bstbl"></table></div>')
        a("</section>")
    if upd and tbl:
        a('<section class="view" id="v-export" hidden>')
        a('<div class="card dnext" id="dnext"></div>')
        a('<div class="card dfinish" id="finish" style="margin-top:var(--spacing-sm)" hidden></div>')
        a("</section>")
    if upd:
        a('<section class="view" id="v-audit" hidden>')
        a('<div class="vtbar"><span class="secondary" id="auditn"></span>'
          '<button class="pill pill--knockout" data-export="log" style="margin-left:auto">Decision log, CSV</button></div>')
        a('<div class="card schedwrap"><table class="sched" id="audittbl"></table></div>')
        a("</section>")
    # Decisions is the finish step (AIJ-110, AIJ-115). It leads with the one thing
    # to do next, the NetSuite upload file, then what was decided, grouped by
    # outcome, with what is still open listed so a missed line shows. The finish
    # step opens once nothing is open. The other files follow, grouped by who uses
    # them, and clearing everything sits apart at the foot.
    a('<section class="view" id="v-decisions" hidden>')
    a('<div class="card loadsum" id="dloaded" style="margin-bottom:var(--spacing-sm)" hidden></div>')
    if not upd:
        a('<div class="card dnext" id="dnext"></div>')
    a('<div class="card" id="decsum" style="margin-top:var(--spacing-sm)"></div>')
    a('<div class="card dgroup" id="dopen" style="margin-top:var(--spacing-sm)"></div>')
    a('<div class="card dgroup" id="dcheck" style="margin-top:var(--spacing-sm)" hidden></div>')
    a('<div id="dgroups"></div>')
    a('<div class="card" style="margin-top:var(--spacing-sm)" id="edittable" hidden></div>')
    if not upd:
        a('<div class="card dfinish" id="finish" style="margin-top:var(--spacing-sm)" hidden></div>')
    if upd:
        a(upd_sox(run))
    a('<div class="card" style="margin-top:var(--spacing-sm)"><h3>Sign-off</h3>'
      '<div class="sign" id="signoff"></div></div>')
    a('<div class="card dfiles" style="margin-top:var(--spacing-sm)"><h3>Other files</h3>'
      '<div class="fgrid">'
      '<div><h4>For people</h4><p class="note">To read and attach.</p><div class="exp">'
      '<button class="pill pill--knockout" data-export="paper">Work paper, HTML</button>'
      + ('<button class="pill pill--knockout" data-export="questions">Questions, CSV</button>'
         if views.get("tables") else "")
      + '</div></div>'
      '<div><h4>For systems</h4><p class="note">The same decisions, for a spreadsheet or another tool.</p>'
      '<div class="exp">'
      '<button class="pill pill--knockout" data-export="log">Decision log, CSV</button>'
      '<button class="pill pill--knockout" data-export="entries">Proposed Journal Entries, CSV</button>'
      '</div></div>'
      '<div><h4>For handing over</h4><p class="note">Keep it with the close file, and load it into the next run.'
      '</p><div class="exp">'
      '<button class="pill pill--knockout" data-export="record">Save the decision record, JSON</button>'
      '<button class="pill pill--knockout" id="loadrec">Load a decision record</button>'
      '<button class="pill pill--knockout" id="carryrun" hidden>Bring in the earlier run’s decisions</button>'
      '<input type="file" id="recfile" accept=".json,application/json" hidden>'
      '</div></div>'
      '</div></div>')
    a('<div class="card dreset" style="margin-top:var(--spacing-sm)"><h3>Start over</h3>'
      '<p class="note">Removes every decision, note, edit, raised entry, signature and upload record'
      ' from this browser. Files already downloaded are not affected.</p>'
      '<div class="exp"><button class="pill pill--knockout" id="reset">Clear all decisions</button></div></div>')
    a("</section>")

    if upd and vtables:
        a('<section class="view" id="v-settings" hidden>')
        a('<div class="card setcard"><h3>Review threshold</h3><label class="setfix" for="fixinput">'
          '<span class="secondary">Items at or over</span><span class="fx">$<input type="text" inputmode="numeric" id="fixinput"'
          ' autocomplete="off" aria-label="Review threshold in dollars"></span></label></div>')
        a("</section>")
    # The run log: what went in, what each check found, what the run costs, and the
    # build record.
    a('<section class="view" id="v-runlog" hidden>')
    a(exports_card(m, views))
    a(checks_card(run))
    if cost:
        main_, alt = cost["priced"][0], cost["priced"][1:]
        a('<div class="card kpi" style="margin-top:var(--spacing-sm)"><h3>Estimated cost per close run</h3>'
          '<div class="v">$' + format(main_["total"], ",.2f") + '</div>'
          '<div class="n">' + format(cost["tokens"], ",") + " tokens on " + esc(main_["model"])
          + ", at list price" + "".join("; $" + format(x["total"], ",.2f") + " on " + esc(x["model"])
                                        for x in alt) + ".</div></div>")
        a('<div class="card" style="margin-top:var(--spacing-sm)"><h3>How it is built</h3>'
          '<div class="costgrid"><table class="costtbl"><thead><tr><th>Tokens</th><th class="num">Count</th>'
          '<th class="num">Per million</th><th class="num">Cost</th></tr></thead><tbody>')
        for label, n, rate, usd in main_["lines"]:
            a("<tr><td>" + esc(label) + '</td><td class="num">' + format(n, ",")
              + '</td><td class="num">$' + format(rate, ",.2f") + '</td><td class="num">$'
              + format(usd, ",.2f") + "</td></tr>")
        a('<tr class="tot"><td>Total</td><td class="num">' + format(cost["tokens"], ",")
          + '</td><td></td><td class="num">$' + format(main_["total"], ",.2f") + "</td></tr>")
        a("</tbody></table>")
        a('<ul class="note costbasis">'
          "<li>In context on every turn: claude.ai's system prompt and tools, about "
          + format(COST_SYSTEM_TOKENS, ",") + " tokens, and the " + format(cost["files"])
          + " Project files Claude reads, about " + format(cost["file_tokens"], ",") + ".</li>"
          "<li>Claude reads the run's " + format(cost["findings"]) + " findings, about "
          + format(cost["read_tokens"], ",") + " tokens, " + format(COST_READ_CHUNK)
          + " at a time, and the output of the three scripts and the rebuild.</li>"
          "<li>" + format(cost["turns"]) + " model turns; each resends the turns before it, read from cache.</li>"
          "<li>Claude writes about " + format(COST_DRAFT_TOKENS) + " tokens per finding, plus a "
          + format(COST_SUMMARY_TOKENS, ",") + "-token summary, and thinks about "
          + format(COST_THINKING_TOKENS, ",") + " tokens a turn.</li>"
          "<li>The NetSuite, Coupa and forecast exports are read by the scripts, not by Claude, so their size adds no tokens.</li>"
          "<li>In a Claude Project the run is covered by the Claude seat; this is what the same run costs through the API.</li>"
          "</ul></div></div>")
    # Inputs first: what went in is the question a reviewer asks before which
    # version processed it.
    a('<div class="card" style="margin-top:var(--spacing-sm)"><h3>Inputs</h3>')
    a('<table><thead><tr><th>File</th><th>Read by</th>'
      '<th class="num">Rows</th><th>Fingerprint</th></tr></thead><tbody>')
    # One row per file. The schedules read files of their own, which the engine's
    # run id does not cover, so each file says which step read it.
    files = {}
    for step, items in (("Engine", m.get("inputs", [])), ("Schedules", views.get("inputs", []))):
        for item in items:
            key = item.get("sha256") or item.get("path")
            entry = files.setdefault(key, {"path": item.get("path"), "rows": item.get("rows", 0),
                                           "sha": str(item.get("sha256", ""))[:16], "by": []})
            if step not in entry["by"]:
                entry["by"].append(step)
    for entry in files.values():
        a("<tr><td>" + esc(os.path.basename(str(entry["path"]))) + "</td><td>"
          + esc(" and ".join(entry["by"])) + '</td><td class="num">'
          + format(entry["rows"] or 0, ",") + '</td><td class="mono">' + esc(entry["sha"])
          + "</td></tr>")
    a("</tbody></table>")
    a('<h3 style="margin-top:var(--spacing-md)">Build record</h3><table><tbody>')
    for label, value in (("Console", CONSOLE_VERSION),
                         ("Engine", m.get("engine_version")),
                         ("Ruleset", m.get("ruleset_version")),
                         ("Schedules", views.get("version") or "not added"),
                         ("Run", m.get("run_id")),
                         ("Period", m.get("period")),
                         ("Generated", m.get("generated_at")),
                         ("Artifact", source_name)):
        a("<tr><td>" + esc(label) + '</td><td class="mono">' + esc(value) + "</td></tr>")
    a("</tbody></table>")
    a("</div>")
    a("</section>")

    # health and coverage: pages of their own only for a run with no schedules.
    # With schedules, what did not run is a fold on Overview.
    if not views.get("tables"):
        a('<section class="view" id="v-health" hidden>')
        a('<div class="card" id="health"></div>')
        a('<div class="nextstep" id="next-health"></div>')
        a("</section>")
        a('<section class="view" id="v-coverage" hidden>')
        a('<div id="coverage"></div>')
        a('<div class="nextstep" id="next-coverage"></div>')
        a("</section>")

    a("</div></div>")
    labels = LABELS
    ch = {}
    if upd:
        labels = json.loads(json.dumps(LABELS))
        labels["pages"].update({"overview": "Executive Overview" if tbl else "Overview",
                                "entries": "Adjustments" if tbl else "Export",
                                "decisions": "SOX & GAAP" if tbl else "SOX Documentation",
                                "flux": "Actual vs. Actual (MoM)"})
        extra = ([{"page": "Adjustments", "title": "Section A: Without a proposed entry", "table": t, "no_entry": True,
                   "host": "adjextra"} for t in ("accrual", "prepaid", "reclass")]
                 + [{"page": "Adjustments", "title": "Section B: Forecast / Budget Revisions", "table": "model_tie",
                     "host": "adjextra"}]) if tbl else []
        ch = {"pre": upd_pre(run), "extra": extra, "bs": views.get("balance_sheet")}
    a("<script>window.__SERIF_LAYOUT__ = " + json.dumps(layout) + ";window.__SERIF_UPDATE__ = "
      + json.dumps(ch, ensure_ascii=False).replace("</", "<\\/") + ";</script>")
    a("<script>window.__SERIF_RUN__ = " + payload + ";window.__SERIF_LABELS__ = "
      + json.dumps(labels, ensure_ascii=False).replace("</", "<\\/") + ";window.__SERIF_CONSOLE__ = "
      + json.dumps(CONSOLE_VERSION) + ";</script>")
    a("<script>" + JS + "</script>")
    a("</body></html>")
    return "\n".join(p)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the Serif close-review console.")
    ap.add_argument("run_json", help="run.json produced by an engine")
    ap.add_argument("-o", "--out", help="output .html (default: beside run.json)")
    ap.add_argument("--drafts", help="drafts.json written by Claude in the Project: commentary, "
                                     "vendor and adjustment notes, Journal Entries, a summary")
    ap.add_argument("--layout", choices=("standard", "ui-update"), default="standard",
                    help="ui-update: the updated page set and overview, over the same decisions")
    args = ap.parse_args(argv)

    if not os.path.exists(args.run_json):
        sys.exit("Run artifact not found: " + args.run_json
                 + "\n  Run the engine first, then point this at its run.json.")
    with open(args.run_json, encoding="utf-8") as h:
        try:
            run = json.load(h)
        except json.JSONDecodeError as exc:
            sys.exit("Could not read " + args.run_json + " as JSON: " + str(exc))
    for key in ("manifest", "summary", "findings"):
        if key not in run:
            sys.exit(args.run_json + " has no '" + key + "'. Is it a run artifact?")

    period = str(run["manifest"].get("period", "period")).replace(" ", "").lower()
    # an engine may name its own output; otherwise slugify the title
    report = run.get("report") or {}
    name = report.get("slug")
    if not name:
        name = "".join(c if c.isalnum() else "-"
                       for c in (report.get("title") or "gl-coding-review").lower())
        while "--" in name:
            name = name.replace("--", "-")
        name = name.strip("-")
    out = args.out or os.path.join(
        os.path.dirname(os.path.abspath(args.run_json)),
        "serif-" + name + "-" + period + "-v" + CONSOLE_VERSION + ("-ui-update" if args.layout == "ui-update" else "") + ".html")
    drafts, skipped = None, []
    if args.drafts:
        if not os.path.exists(args.drafts):
            sys.exit("Drafts not found: " + args.drafts)
        try:
            drafts, skipped = load_drafts(run, args.drafts)
        except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as exc:
            sys.exit("Could not read " + args.drafts + ": " + str(exc))
        run = attach_drafts(run, drafts)
    with open(out, "w", encoding="utf-8") as h:
        h.write(build(run, os.path.basename(args.run_json), args.layout))
    if drafts is not None:
        print("  drafts: " + ", ".join("%d %s" % (len(v) if isinstance(v, (list, dict)) else 1, k)
                                       for k, v in drafts.items()) + (
              "" if not skipped else "\n  left out, not in this run:\n    " + "\n    ".join(skipped)))
    print("Wrote " + out + "  (" + format(os.path.getsize(out) // 1024, ",") + " KB)")
    print("  console v" + CONSOLE_VERSION
          + " · engine " + str(run["manifest"].get("engine_version"))
          + " · ruleset " + str(run["manifest"].get("ruleset_version")))
    print("  " + str(run["summary"].get("finding_count", 0)) + " findings · "
          + str(run["manifest"].get("period")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
