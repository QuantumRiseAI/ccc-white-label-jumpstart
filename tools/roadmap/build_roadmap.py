"""Build the Serif AI Jumpstarts roadmap as one self-contained HTML page.

    python3 tools/roadmap/build_roadmap.py [out.html]

Content lives in roadmap_content.py; this lays it out in Serif's design system
(src/serif_design.py and its inlined open fonts). Stdlib only.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
sys.path.insert(0, HERE)
import serif_design as DS  # noqa: E402
import roadmap_content as C  # noqa: E402

DEFAULT_OUT = os.path.join(HERE, "..", "..", "..", "..", "6-deliverables",
                           "2026-10-07 - Serif AI Jumpstarts - Roadmap.html")

STAGES = ["Crawl", "Walk", "Run"]

CSS = r"""
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--color-bg-primary);color:var(--color-fg-primary);font-family:var(--font-sans);
  font-size:var(--text-0);line-height:1.55}
.wrap{max-width:68rem;margin:0 auto;padding-inline:var(--spacing-sm-lg)}
header.mast{background:var(--color-bg-inverse);color:var(--color-fg-inverse);padding-block:var(--spacing-lg-xl) var(--spacing-xl)}
header.mast .logo{width:5.5rem;height:auto;color:var(--color-white);display:block;margin-bottom:var(--spacing-md)}
.eyebrow{font-size:var(--text--1);letter-spacing:.06em;text-transform:uppercase;color:var(--color-warm-gray);margin:0 0 var(--spacing-xs)}
h1{font-family:var(--font-serif);font-weight:400;font-size:var(--text-4);line-height:1.1;margin:0}
.sub{font-size:var(--text-1);margin:var(--spacing-2xs) 0 0;color:var(--color-light-gray)}
.meta{display:flex;flex-wrap:wrap;gap:var(--spacing-xs);align-items:center;margin-top:var(--spacing-md);font-size:var(--text--1);color:var(--color-warm-gray)}
.pill{display:inline-block;border:1px solid currentColor;border-radius:var(--radius-pill);padding:.1em .7em;font-size:var(--text--2);letter-spacing:.04em;text-transform:uppercase}
main{padding-block:var(--spacing-lg-xl)}
section{margin-bottom:var(--spacing-lg-xl)}
h2{font-family:var(--font-serif);font-weight:400;font-size:var(--text-3);line-height:1.2;margin:0 0 var(--spacing-sm)}
h3{font-size:var(--text-1);font-weight:600;line-height:1.3;margin:0}
p{margin:0 0 var(--spacing-xs)}
.card{background:var(--color-stark);border-radius:var(--radius-sm);padding:var(--spacing-sm-md)}
.two{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:var(--spacing-md)}
@media (max-width:52rem){.two{grid-template-columns:1fr}}
dl.rows{margin:0;display:grid;gap:var(--spacing-xs)}
dl.rows div{display:grid;grid-template-columns:minmax(7rem,10rem) 1fr;gap:var(--spacing-xs);padding-bottom:var(--spacing-xs);border-bottom:1px solid var(--color-hairline)}
dl.rows div:last-child{border-bottom:0;padding-bottom:0}
dl.rows dt{font-weight:600;font-size:var(--text--1)}
dl.rows dd{margin:0;font-size:var(--text--1);color:var(--color-fg-secondary)}
@media (max-width:30rem){dl.rows div{grid-template-columns:1fr;gap:.2em}}
.read{display:grid;grid-template-columns:repeat(auto-fit,minmax(13rem,1fr));gap:var(--spacing-xs)}
.read .card{padding:var(--spacing-sm)}
.read b{display:block;font-size:var(--text--1);margin-bottom:.25em}
.read span{font-size:var(--text--1);color:var(--color-fg-secondary)}
.lanes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--spacing-xs)}
@media (max-width:52rem){.lanes{grid-template-columns:1fr}}
.lane{background:var(--color-stark);border-radius:var(--radius-sm);padding:var(--spacing-sm);border-top:4px solid var(--color-mid-gray)}
.lane.crawl{border-top-color:var(--color-warm-gray)}
.lane.run{border-top-color:var(--color-red)}
.lane h3{font-family:var(--font-serif);font-weight:400;font-size:var(--text-2)}
.lane .what{font-size:var(--text--1);color:var(--color-fg-secondary);margin:.2em 0 var(--spacing-xs)}
.lane ul{margin:0;padding:0;list-style:none;display:grid;gap:.35em}
.lane li{font-size:var(--text--1)}
.lane li a{color:inherit;text-decoration:none;border-bottom:1px solid var(--color-hairline)}
.lane li a:hover{border-bottom-color:var(--color-red-text)}
.lane li small{color:var(--color-fg-secondary)}
.tw{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:var(--text--1)}
th{text-align:left;font-weight:600;color:var(--color-fg-secondary);font-size:var(--text--2);text-transform:uppercase;letter-spacing:.04em;
  padding:.5em .6em;border-bottom:1px solid var(--color-fg-primary);vertical-align:bottom}
td{padding:.6em;border-bottom:1px solid var(--color-hairline);vertical-align:top}
td.c{text-align:center}
td a{color:inherit}
.theme{background:var(--color-stark);border-radius:var(--radius-md);padding:var(--spacing-md-lg);margin-bottom:var(--spacing-md);break-inside:avoid}
.theme .top{display:flex;flex-wrap:wrap;gap:var(--spacing-2xs);align-items:center;margin-bottom:var(--spacing-xs)}
.num{font-family:var(--font-serif);font-size:var(--text-2);color:var(--color-red-text);margin-right:var(--spacing-3xs)}
.tag{font-size:var(--text--2);letter-spacing:.04em;text-transform:uppercase;border-radius:var(--radius-pill);padding:.15em .7em;background:var(--color-bg-primary);color:var(--color-fg-secondary)}
.tag.stage{background:var(--color-bg-inverse);color:var(--color-fg-inverse)}
.theme h2{margin-bottom:.15em}
.stand{font-family:var(--font-serif);font-style:italic;font-size:var(--text-1);color:var(--color-fg-secondary);margin:0 0 var(--spacing-sm)}
.clusters{list-style:none;margin:var(--spacing-sm) 0 0;padding:0;display:grid;gap:var(--spacing-xs)}
.clusters li{display:grid;grid-template-columns:1.2rem 1fr;gap:.4em;padding-top:var(--spacing-xs);border-top:1px solid var(--color-hairline)}
.clusters .mk{color:var(--color-red-text);font-size:var(--text--1);line-height:1.9}
.clusters b{display:block}
.clusters span.t{color:var(--color-fg-secondary);font-size:var(--text--1)}
.today{margin-top:var(--spacing-sm);background:var(--color-bg-primary);border-radius:var(--radius-xs);padding:var(--spacing-xs) var(--spacing-sm);font-size:var(--text--1)}
.today b{margin-right:.4em}
.closing{background:var(--color-bg-inverse);color:var(--color-fg-inverse);border-radius:var(--radius-md);padding:var(--spacing-md-lg)}
.closing p{color:var(--color-light-gray)}
footer{font-size:var(--text--2);color:var(--color-fg-secondary);padding-block:0 var(--spacing-lg)}
footer .wrap{display:flex;flex-wrap:wrap;justify-content:space-between;gap:var(--spacing-xs);border-top:1px solid var(--color-hairline);padding-top:var(--spacing-sm)}
@media print{
  body{background:#fff;font-size:10.5pt}
  header.mast{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .closing,.tag.stage,.lane{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .theme,.card,.lane{border:1px solid var(--color-hairline)}
  section,.theme{break-inside:avoid}
}
"""


def slug(n, name):
    return "theme-%d" % n


def stage_key(stage):
    return stage.split()[0]


def page():
    e = lambda s: s  # content is authored HTML-safe in roadmap_content.py
    themes = C.THEMES
    decides = lambda t: sum(1 for c in t["clusters"] if c[2])

    head = ('<header class="mast"><div class="wrap">' + DS.LOGO
            + '<p class="eyebrow">' + C.DOC["eyebrow"] + '</p><h1>' + C.DOC["title"] + '</h1>'
            + '<p class="sub">' + C.DOC["subtitle"] + '</p>'
            + '<div class="meta"><span>' + C.DOC["date_line"] + '</span><span class="pill">'
            + C.DOC["status"] + '</span></div></div></header>')

    intro = ('<section class="two"><div><h2>What this is</h2>'
             + "".join("<p>" + p + "</p>" for p in C.INTRO) + '</div>'
             + '<div class="card"><h3 style="margin-bottom:var(--spacing-xs)">' + C.TODAY["heading"] + '</h3><dl class="rows">'
             + "".join("<div><dt>%s</dt><dd>%s</dd></div>" % r for r in C.TODAY["rows"])
             + '</dl></div></section>')

    read = ('<section><h2>How to read it</h2><div class="read">'
            + "".join('<div class="card"><b>%s</b><span>%s</span></div>' % r for r in C.HOW_TO_READ)
            + '</div></section>')

    lanes_what = {
        "Crawl": "The two Claude Projects, as delivered: run each close by an analyst, from exports.",
        "Walk": "A deployed solution: data that arrives on its own, state that lasts across closes, controls.",
        "Run": "Agents working the close, with people approving what they propose.",
    }
    by_stage = {s: [] for s in STAGES}
    for n, t in enumerate(themes, 1):
        for s in STAGES:
            if s in t["stage"].split():
                by_stage[s].append((n, t))
    lanes = '<section><h2>Crawl, Walk, Run</h2><div class="lanes">'
    for s in STAGES:
        items = by_stage[s]
        lis = ("".join('<li><a href="#%s">%s</a> <small>&middot; %s</small></li>' % (slug(n, t["name"]), t["name"], t["dimension"])
                       for n, t in items)
               if items else "<li>GL Coding Review and P&amp;L Flux, in Serif's Claude organization</li>")
        lanes += ('<div class="lane %s"><h3>%s</h3><p class="what">%s</p><ul>%s</ul></div>'
                  % (s.lower(), s, lanes_what[s], lis))
    lanes += "</div></section>"

    rows = "".join(
        '<tr><td><a href="#%s">%s</a></td><td>%s</td><td>%s</td><td class="c">%s</td><td class="c">%s</td></tr>'
        % (slug(n, t["name"]), t["name"], t["dimension"], t["stage"], decides(t) or "&ndash;",
           "&#10003;" if t.get("today") else "&ndash;")
        for n, t in enumerate(themes, 1))
    glance = ('<section><h2>At a glance</h2><div class="card tw"><table><thead><tr><th>Theme</th><th>Dimension</th>'
              '<th>Stage</th><th style="text-align:center">&#9670; Serif decides</th><th style="text-align:center">Try it today</th></tr></thead>'
              '<tbody>' + rows + '</tbody></table></div></section>')

    blocks = []
    for n, t in enumerate(themes, 1):
        cl = "".join('<li><span class="mk">%s</span><div><b>%s</b><span class="t">%s</span></div></li>'
                     % ("&#9670;" if d else "", lab, txt) for lab, txt, d in t["clusters"])
        today = ('<div class="today"><b>Try it today</b>' + t["today"] + '</div>') if t.get("today") else ""
        blocks.append('<article class="theme" id="%s"><div class="top"><span class="num">%02d</span>'
                      '<span class="tag">%s</span><span class="tag stage">%s</span></div>'
                      '<h2>%s</h2><p class="stand">%s</p><p>%s</p><ul class="clusters">%s</ul>%s</article>'
                      % (slug(n, t["name"]), n, t["dimension"], t["stage"], t["name"], t["standfirst"], t["lead"], cl, today))
    body_themes = '<section><h2>The themes</h2>' + "".join(blocks) + "</section>"

    closing = ('<section class="closing"><h2>' + C.CLOSING["heading"] + '</h2>'
               + "".join("<p>" + p + "</p>" for p in C.CLOSING["paragraphs"]) + "</section>")

    foot = ('<footer><div class="wrap"><span>Serif Biomedicines &middot; ' + C.DOC["title"] + '</span>'
            '<span>' + C.DOC["date_line"] + ' &middot; ' + C.DOC["status"] + '</span></div></footer>')

    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Serif AI Jumpstarts Roadmap</title><style>' + DS.FONT_CSS + DS.TOKENS + CSS + '</style></head>'
            '<body>' + head + '<main><div class="wrap">' + intro + read + lanes + glance + body_themes + closing
            + '</div></main>' + foot + '</body></html>')


if __name__ == "__main__":
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(page())
    print("Wrote %s (%d KB)" % (out, os.path.getsize(out) // 1024))
