"""The updated-UI consoles: Chris's August page set, in Serif's design, from our runs.

In a Claude Project, or any folder holding the runs and the export:

    python3 build_pages.py --coding-run out/aug2026/coding/run.json \
        --flux-run out/aug2026/flux/run.json --gl netsuite_gl_*.xls --out out/aug2026

In the repo, after updated-ui/build_runs.sh:

    python3 updated-ui/build_pages.py aug2026

Writes two self-contained, interactive HTML consoles: decisions, commentary,
sign-off, an audit log and the NetSuite export are kept in the browser. Every
figure is computed here from the two runs and the NetSuite GL export.
"""
import argparse
import glob
import html
import json
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.abspath(os.path.join(HERE, ".."))
# Beside this file in a Project folder; the flux Project folder in the repo.
for d in (os.path.join(B, "pl-flux", "upload-to-project"), HERE):
    sys.path.insert(0, d)
import serif_sources as SS  # noqa: E402
import build_report as BR   # noqa: E402

VERSION = "v1"
ap = argparse.ArgumentParser(description="Build the updated-UI consoles.")
ap.add_argument("slug", nargs="?", help="period slug, eg aug2026, to read the repo's updated-ui/runs/<slug>/")
ap.add_argument("--coding-run", help="the GL Coding Review run.json, after serif_views.py --keep-names")
ap.add_argument("--flux-run", help="the P&L Flux run.json, after serif_views.py --keep-names --balance-sheet")
ap.add_argument("--gl", nargs="+", help="the NetSuite Custom General Ledger export(s), as NetSuite writes them")
ap.add_argument("--income-statement", help="the NetSuite Income Statement by month report, for the SOX tie-outs")
ap.add_argument("--out", help="output folder")
A = ap.parse_args()
SLUG = A.slug or "aug2026"
if A.coding_run and A.flux_run:
    GLR, PLR = json.load(open(A.coding_run)), json.load(open(A.flux_run))
    GL_X = A.gl or sys.exit("Pass the NetSuite GL export with --gl.")
    SLUG = PLR["manifest"]["period"].replace(" ", "").lower()
    OUT = A.out or os.path.dirname(os.path.abspath(A.flux_run))
    IS_X = A.income_statement
else:
    GLR = json.load(open(os.path.join(HERE, "runs", SLUG, "gl-coding-review", "run.json")))
    PLR = json.load(open(os.path.join(HERE, "runs", SLUG, "pl-flux", "run.json")))
    INP = os.path.join(B, "pl-flux", "monthly-inputs", SLUG)
    GL_X = A.gl or sorted(glob.glob(os.path.join(INP, "netsuite_gl_detail*")))
    OUT = A.out or os.path.join(HERE, "out", SLUG)
    IS_X = A.income_statement or next(iter(sorted(glob.glob(os.path.join(INP, "netsuite_income_statement_by_month*")))), None)

M = PLR["manifest"]
PERIOD, PRIOR, PY = M["period"], M["prior_period"], M["prior_year_period"]
MON = PERIOD[:3]
YEAR_END = "Dec " + str(int(PERIOD[-4:]) - 1)
e = lambda s: html.escape("" if s is None else str(s))
ACC = {}
for r in (PLR, GLR):
    for k, v in (r["views"].get("accounts") or {}).items():
        ACC[k] = v.get("name") if isinstance(v, dict) else v
acct_name = lambda c: ACC.get(c) or ""
LINKS = {}
for r in (PLR, GLR):
    LINKS.update((r["views"].get("links") or {}).get("docs") or {})
NS_ACCT = (GLR["views"].get("links") or {}).get("netsuite_account") or "5602907"


def money(v, cents=False):
    if v is None:
        return "&ndash;"
    v = round(v, 2)
    if (not cents and abs(v) < 0.5) or v == 0:
        return "$0"
    s = format(abs(v), ",.2f" if cents else ",.0f")
    return "($" + s + ")" if v < 0 else "$" + s


def short(v):
    a = abs(v or 0)
    s = ("$%.2fM" % (a / 1e6)) if a >= 1e6 else ("$%.1fK" % (a / 1e3)) if a >= 1e4 else ("$%.0f" % a)
    return "(" + s + ")" if (v or 0) < 0 else s


def pct(v, base):
    return ("+" if v > 0 else "") + format(100.0 * v / abs(base), ".1f") + "%" if base else "&ndash;"


def fav(v, text=None, cents=False):
    """A favorable variance (cost less) in ink, an unfavorable one in the accent."""
    t = text if text is not None else money(v, cents)
    return '<span class="unf">' + t + "</span>" if v is not None and round(v) < 0 else t


def doc_links(doc):
    d = LINKS.get(str(doc)) or {}
    out = []
    if d.get("ns"):
        out.append('<a class="xl" target="_blank" rel="noopener" href="https://%s.app.netsuite.com/app/accounting/transactions/transaction.nl?id=%s">NetSuite</a>' % (NS_ACCT, e(d["ns"])))
    if d.get("coupa"):
        out.append('<a class="xl" target="_blank" rel="noopener" href="%s">Coupa</a>' % e(d["coupa"]))
    return " ".join(out)


# ---------- the ledger, read as exported ----------
by_period, _ = SS.read_gl(GL_X)
PNL = lambda c: c[:1] in "678"
gl_now, gl_prior = by_period.get(PERIOD, []), by_period.get(PRIOR, [])
dept_acct_vendor = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
for i, lines in enumerate((gl_now, gl_prior)):
    for l in lines:
        if PNL(l["account_code"]):
            dept_acct_vendor[(l["department"] or "Non-Specific", l["account_code"])][(l.get("vendor_or_name") or "").strip() or "(blank)"][i] += l["amount"]
ytd = sum(l["amount"] for p, ls in by_period.items() if p.endswith(PERIOD[-4:]) and SS.period_key(p) <= SS.period_key(PERIOD)
          for l in ls if l["account_code"][:1] in "67")
gl_6x = sum(l["amount"] for l in gl_now if l["account_code"][:1] == "6")
pl_lines_now = sum(1 for l in gl_now if PNL(l["account_code"]))
DEPTS = sorted({l["department"] for ls in by_period.values() for l in ls if l.get("department")})
HIST_MONTHS = [SS.shift(PERIOD, -2), PRIOR, PERIOD]
vendor_lines = defaultdict(lambda: defaultdict(list))   # vendor -> month -> lines
for m in HIST_MONTHS:
    for l in by_period.get(m, []):
        if l["txn_type"] != "Journal" and (l.get("vendor_or_name") or "").strip() and (PNL(l["account_code"]) or l["account_code"][:2] in ("13", "15")):
            vendor_lines[l["vendor_or_name"].strip()][m].append(l)
desc = lambda l: (l.get("description") or l.get("memo") or "").strip()


def history(vendor):
    """The vendor's last three months by coding: amount and what the lines say."""
    out = []
    for m in HIST_MONTHS:
        ls = vendor_lines.get(vendor, {}).get(m) or []
        by = defaultdict(list)
        for l in ls:
            by[(l["account_code"], l["department"] or "")].append(l)
        if not by:
            out.append('<tr><td>%s</td><td class="note" colspan="3">No lines</td></tr>' % e(m))
            continue
        groups = sorted(by.items(), key=lambda kv: -abs(sum(l["amount"] for l in kv[1])))
        for n, ((a, d), g) in enumerate(groups[:3]):
            ds = []
            for l in sorted(g, key=lambda l: -abs(l["amount"])):
                if desc(l) and desc(l) not in ds:
                    ds.append(desc(l))
            more = len(ds) - 2
            out.append('<tr><td>%s</td><td>%s<small>%s%s</small></td><td class="n2">%s</td><td>%s%s</td></tr>'
                       % (e(m) if not n else "", e(a), e(acct_name(a)), (" / " + e(d)) if d else "", money(sum(l["amount"] for l in g), True),
                          "<br>".join(e(x) for x in ds[:2]) or "&ndash;", ('<small>%d more</small>' % more) if more > 0 else ""))
        if len(groups) > 3:
            out.append('<tr><td></td><td class="note" colspan="3">%d more codings</td></tr>' % (len(groups) - 3))
    return ('<div class="hist"><div class="l">Last three months</div><div class="tw"><table><thead><tr><th>Month</th><th>Account / Department</th>'
            '<th class="n2">Amount</th><th>Description</th></tr></thead><tbody>' + "".join(out) + "</tbody></table></div></div>")


def je_editor(iid, lines, when=None):
    """A proposed Journal Entry, filled in and editable. The page fills the values."""
    rows = "".join('<tr><td><input class="f mono" data-jef="%s|%d|account" list="accts" size="9" aria-label="Account"><small data-jean="%s|%d"></small></td>'
                   '<td><input class="f" data-jef="%s|%d|department" list="depts" aria-label="Department"></td>'
                   '<td class="n2"><input class="f num" data-jef="%s|%d|debit" inputmode="decimal" aria-label="Debit"></td>'
                   '<td class="n2"><input class="f num" data-jef="%s|%d|credit" inputmode="decimal" aria-label="Credit"></td></tr>'
                   % ((iid, i) * 5) for i in range(len(lines)))
    return ('<div class="jee" data-je="%s"%s><div class="jh"><span class="l">Journal Entry</span><span data-jebal></span>'
            '<button class="lk" data-jereset="%s" hidden>Reset</button></div><div class="tw"><table><thead><tr><th>Account</th><th>Department</th>'
            '<th class="n2">Debit</th><th class="n2">Credit</th></tr></thead><tbody>%s</tbody></table></div></div>'
            % (iid, (' data-when="%s" hidden' % when) if when else "", iid, rows))


def count(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def je_lines(lines):
    return [{"account": l["account"], "department": l.get("department") or "", "debit": round(l.get("debit") or 0, 2), "credit": round(l.get("credit") or 0, 2)} for l in lines]

# ---------- the design ----------
ROOT = BR.CSS[BR.CSS.index(":root{"):]
ROOT = ROOT[:ROOT.index("\n}\n") + 3]
CSS = BR.FONT_CSS + ROOT + r"""
*{box-sizing:border-box}
body{margin:0;font-family:var(--font-sans);font-size:var(--text-0);line-height:1.35;color:var(--color-fg-primary);
  background-color:var(--color-bg-primary);-webkit-font-smoothing:antialiased;text-wrap:pretty}
button,input,textarea{font:inherit;color:inherit}
[hidden]{display:none!important}
a.xl{font-size:var(--text--2);color:var(--color-fg-secondary);text-decoration:underline;text-underline-offset:2px;margin-left:.4em}
.top{position:sticky;top:0;z-index:10;display:flex;align-items:center;gap:var(--spacing-2xs);height:52px;
  padding-inline:var(--spacing-md-lg);background-color:var(--color-bg-inverse);color:var(--color-fg-inverse);font-size:var(--text--1)}
.top .brand{display:flex;align-items:center;gap:var(--spacing-xs);padding-right:var(--spacing-sm);margin-right:var(--spacing-3xs);
  border-right:1px solid rgba(255,255,255,.14);flex:none}
.top .logo{width:52px;height:auto;color:#fff;display:block}
.top .brand b{font-weight:500;color:#fff;white-space:nowrap}
.top .brand span{color:var(--color-warm-gray);white-space:nowrap}
.top nav{display:flex;align-items:center;gap:var(--spacing-3xs);flex:1;min-width:0;overflow-x:auto;scrollbar-width:none}
.top nav::-webkit-scrollbar{display:none}
.tg{display:flex;align-items:center;flex:none;border-radius:var(--radius-pill);transition:background-color .25s}
.tg.open{background-color:rgba(255,255,255,.08)}
.tb{height:2.4em;display:inline-flex;align-items:center;gap:.45em;padding:0 .7em;border:0;border-radius:var(--radius-pill);
  background:none;color:var(--color-warm-gray);cursor:pointer;white-space:nowrap}
.tb:hover{color:#fff;background-color:rgba(255,255,255,.06)}
.tg.open > .sec{color:#fff;font-weight:600;background:none}
.tb.cur{background-color:var(--color-light-gray);color:var(--color-dark-gray)}
.tb.cur:hover{background-color:#fff;color:var(--color-dark-gray)}
.sub{display:inline-flex;align-items:center;gap:var(--spacing-3xs);overflow:hidden;max-width:60rem;opacity:1;
  transition:max-width .3s cubic-bezier(.165,.84,.44,1),opacity .3s}
.sub.shut{max-width:0;opacity:0;pointer-events:none}
.n{font-size:var(--text--2);background-color:var(--color-red-text);color:#fff;border-radius:var(--radius-pill);padding:.05em .5em;font-variant-numeric:tabular-nums}
.n:empty{display:none}
.tb.cur .n{background-color:var(--color-red-text)}
.icons{display:flex;gap:var(--spacing-3xs);margin-left:auto;flex:none}
.icons .tb{padding:0 .55em}
.icons svg{width:1.05em;height:1.05em}
#tip{position:fixed;z-index:30;pointer-events:none;background-color:var(--color-bg-inverse);color:var(--color-fg-inverse);
  font-size:var(--text--2);line-height:1.45;padding:.55em .75em;border-radius:var(--radius-xs);max-width:22rem;display:none}
#tip b{color:#fff}
main{max-width:96rem;margin:0 auto;padding:var(--spacing-md) var(--spacing-md-lg) var(--spacing-xl)}
.page[hidden]{display:none}
.hero{background-color:var(--color-bg-inverse);color:var(--color-fg-inverse);border-radius:var(--radius-sm);padding:var(--spacing-sm-md);margin-bottom:var(--spacing-sm)}
.hero h1{font-size:var(--text-2);font-weight:500;color:#fff;margin:0 0 .2em;letter-spacing:-0.01em}
.hero .sub2{color:var(--color-warm-gray);font-size:var(--text--1);margin:0 0 var(--spacing-xs)}
.hero .ht{display:grid;grid-template-columns:repeat(auto-fit,minmax(12rem,1fr));gap:var(--spacing-xs)}
.hero .ht > div{background-color:rgba(255,255,255,.07);border-radius:var(--radius-xs);padding:.7em .9em}
.hero .k{font-size:var(--text--2);text-transform:uppercase;letter-spacing:.04em;color:var(--color-warm-gray)}
.hero .v{font-size:var(--text-1);color:#fff;font-variant-numeric:tabular-nums;margin:.15em 0}
.hero .s{font-size:var(--text--2);color:var(--color-warm-gray)}
.hero .unf{color:#ff8a66}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));gap:var(--spacing-xs);margin-bottom:var(--spacing-sm)}
.tile{background-color:var(--color-stark);border-radius:var(--radius-sm);padding:var(--spacing-sm)}
.tile .k{font-size:var(--text--2);text-transform:uppercase;letter-spacing:.04em;color:var(--color-fg-secondary)}
.tile .v{font-size:var(--text-2);margin:.2em 0 .1em;font-variant-numeric:tabular-nums}
.tile .s{font-size:var(--text--2);color:var(--color-fg-secondary)}
.card{background-color:var(--color-stark);border-radius:var(--radius-sm);margin-bottom:var(--spacing-sm);overflow:hidden}
.card > h3,.card .ch{font-size:var(--text-0);font-weight:600;margin:0;padding:var(--spacing-sm) var(--spacing-sm-md);border-bottom:1px solid var(--color-hairline);
  display:flex;align-items:center;gap:var(--spacing-xs)}
.card .ch .r{margin-left:auto}
.pad{padding:var(--spacing-sm) var(--spacing-sm-md)}
.tabs{display:flex;gap:var(--spacing-3xs);padding:0 var(--spacing-sm);border-bottom:1px solid var(--color-hairline);overflow-x:auto}
.tabs button{border:0;background:none;padding:.8em .8em .7em;cursor:pointer;color:var(--color-fg-secondary);border-bottom:2px solid transparent;white-space:nowrap}
.tabs button:focus{outline:none}
.tabs button:focus-visible{outline:2px solid var(--color-vivid);outline-offset:-2px}
.tabs button.on{color:var(--color-fg-primary);font-weight:600;border-bottom-color:var(--color-red-text)}
.sumline{padding:.7em var(--spacing-sm-md);font-size:var(--text--1);color:var(--color-fg-secondary);border-bottom:1px solid var(--color-hairline);display:flex;gap:var(--spacing-sm);flex-wrap:wrap}
.sumline b{color:var(--color-fg-primary);font-variant-numeric:tabular-nums}
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:var(--text--1)}
th{font-size:var(--text--2);text-transform:uppercase;letter-spacing:.04em;color:var(--color-fg-secondary);font-weight:600;text-align:left;
  padding:.7em .8em;border-bottom:1px solid var(--color-hairline);white-space:nowrap;background-color:var(--color-stark)}
td{padding:.65em .8em;border-bottom:1px solid var(--color-hairline);vertical-align:top}
td.n2,th.n2{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.mono{font-family:var(--font-mono);font-size:.9em}
.code{display:block;font-family:var(--font-mono);font-size:var(--text--2);color:var(--color-fg-secondary)}
tr.grp td{background-color:var(--color-bg-primary);font-size:var(--text--2);font-weight:600;text-transform:uppercase;letter-spacing:.04em;text-align:left;color:var(--color-fg-primary)}
tr.grp.lv1 td{background-color:var(--color-stark);color:var(--color-fg-secondary)}
tr.grp.lv2 td{background-color:var(--color-stark);color:var(--color-fg-secondary);text-transform:none;letter-spacing:0;font-size:var(--text--1)}
tr.tot td{border-top:1px solid var(--color-mid-gray)}
table.cl tr.xp{cursor:pointer} table.cl tr.xp:hover td{background-color:var(--color-bg-primary)}
table.cl tr.open td:first-child{box-shadow:inset 3px 0 0 var(--color-red-text)}
tr.tot td{font-weight:600;background-color:var(--color-bg-primary)}
tr.crit td:first-child{box-shadow:inset 3px 0 0 var(--color-red-text)}
tr.mat td:first-child{box-shadow:inset 3px 0 0 var(--color-warm-gray)}
tr.crit td:first-child,tr.mat td:first-child{padding-left:1.1em}
.mk{display:block;margin-top:.3em}
.mk:empty{display:none}
.unf{color:var(--color-red-text)}
.cm{color:var(--color-fg-primary);line-height:1.45;margin-bottom:.35em}
textarea.c{width:100%;min-height:2.1em;resize:vertical;border:1px solid var(--color-hairline);border-radius:var(--radius-xs);padding:.35em .5em;font-size:var(--text--1);background:none}
textarea.c:focus,input.f:focus{outline:2px solid var(--color-vivid);outline-offset:1px}
input.f{border:1px solid var(--color-hairline);border-radius:var(--radius-xs);padding:.4em .55em;font-size:var(--text--1);background:none}
.pill{display:inline-flex;align-items:center;gap:.35em;border:1px solid var(--color-dark-gray);border-radius:var(--radius-pill);padding:.4em 1em;
  background:none;cursor:pointer;font-size:var(--text--1);white-space:nowrap}
.pill.solid{background-color:var(--color-dark-gray);color:#fff}
.pill.on{background-color:var(--color-dark-gray);color:#fff}
.pill:disabled{opacity:.4;cursor:default}
.tag{display:inline-block;font-size:var(--text--2);font-weight:600;letter-spacing:.03em;text-transform:uppercase;border-radius:var(--radius-xs);
  padding:.15em .5em;border:1px solid var(--color-hairline);color:var(--color-fg-secondary);white-space:nowrap}
.tag.hi{border-color:var(--color-red-text);color:var(--color-red-text)}
.tag.ink{background-color:var(--color-dark-gray);border-color:var(--color-dark-gray);color:#fff}
.stp{margin-left:auto;font-size:var(--text--2);font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:var(--color-fg-secondary)}
.stp.done{color:var(--color-dark-gray)}
.stp.rej{color:var(--color-red-text)}
.item{background-color:var(--color-stark);border-radius:var(--radius-sm);margin-bottom:var(--spacing-xs);border-left:3px solid var(--color-warm-gray)}
.item.hi{border-left-color:var(--color-red-text)}
.item.done{border-left-color:var(--color-dark-gray)}
.item .ih{display:flex;align-items:center;gap:var(--spacing-xs);padding:.8em var(--spacing-sm);border-bottom:1px solid var(--color-hairline);flex-wrap:wrap}
.item .ih b{font-weight:600}
.item .ib{padding:var(--spacing-xs) var(--spacing-sm) var(--spacing-sm)}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(12rem,1fr));gap:.8em var(--spacing-sm);margin-bottom:.8em}
.kv .l{font-size:var(--text--2);text-transform:uppercase;letter-spacing:.04em;color:var(--color-fg-secondary)}
.kv .x{font-size:var(--text--1);margin-top:.15em}
.kv .x small{display:block;color:var(--color-fg-secondary)}
.arrow{color:var(--color-fg-secondary)}
.why{background-color:var(--color-bg-primary);border-radius:var(--radius-xs);padding:.6em .8em;font-size:var(--text--1);line-height:1.5;margin-bottom:.6em}
.pol{font-size:var(--text--2);color:var(--color-fg-secondary);margin-bottom:.7em}
.drcr{display:grid;grid-template-columns:1fr 1fr;gap:var(--spacing-xs);margin-bottom:.8em}
.drcr > div{border:1px solid var(--color-hairline);border-radius:var(--radius-xs);padding:.5em .7em;font-size:var(--text--1)}
.drcr .l{font-size:var(--text--2);text-transform:uppercase;letter-spacing:.04em;color:var(--color-fg-secondary);margin-bottom:.3em}
.drcr .ln{display:flex;justify-content:space-between;gap:1em;font-family:var(--font-mono);font-size:.88em;padding:.15em 0}
.hist,.jee{margin:0 0 .8em;border:1px solid var(--color-hairline);border-radius:var(--radius-xs);overflow:hidden}
.hist > .l,.jee .jh{display:flex;align-items:center;gap:var(--spacing-xs);font-size:var(--text--2);text-transform:uppercase;letter-spacing:.04em;
  color:var(--color-fg-secondary);padding:.5em .8em;border-bottom:1px solid var(--color-hairline)}
.hist table,.jee table{font-size:var(--text--2)}
.hist td small,.jee td small,.ties td small{display:block;color:var(--color-fg-secondary);font-size:var(--text--2)}
.hist tr:last-child td,.jee tr:last-child td{border-bottom:0}
.jee td{padding:.35em .8em;vertical-align:middle}
.jee input.f{padding:.25em .4em;font-size:var(--text--2);width:100%;max-width:26ch}
.jee input.mono{max-width:12ch}
.jee input.num{text-align:right;font-variant-numeric:tabular-nums;max-width:12ch}
.jee .jh [data-jebal]{text-transform:none;letter-spacing:0}
.jee.edited{border-color:var(--color-dark-gray)}
.lk{margin-left:auto;border:0;background:none;padding:0;font-size:var(--text--2);color:var(--color-fg-secondary);text-decoration:underline;cursor:pointer}
.dh{font-size:var(--text-1);font-weight:500;margin:var(--spacing-md) 0 var(--spacing-3xs);display:flex;align-items:baseline;gap:var(--spacing-xs)}
.dh .note{font-size:var(--text--1)}
details.lines{margin:0 0 .8em}
details.lines summary{cursor:pointer;font-size:var(--text--1);color:var(--color-fg-secondary);padding:.2em 0}
details.lines table{font-size:var(--text--2)}
.acts{display:flex;gap:var(--spacing-2xs);flex-wrap:wrap;align-items:center}
.acts textarea{flex:1 1 20rem}
.bar{height:.5em;background-color:var(--color-bg-primary);border-radius:var(--radius-pill);overflow:hidden;margin:.6em 0}
.bar > i{display:block;height:100%;background-color:var(--color-dark-gray);border-radius:var(--radius-pill)}
.chips{display:flex;gap:var(--spacing-2xs);flex-wrap:wrap;font-size:var(--text--1)}
.chips span{border:1px solid var(--color-hairline);border-radius:var(--radius-pill);padding:.25em .8em}
.legend{display:flex;gap:var(--spacing-xs);flex-wrap:wrap;align-items:center;font-size:var(--text--1);color:var(--color-fg-secondary);margin-bottom:var(--spacing-xs)}
.grphead{display:flex;align-items:center;gap:var(--spacing-xs);margin:var(--spacing-sm) 0 var(--spacing-2xs);font-size:var(--text--1)}
.wfx{position:relative;padding:var(--spacing-md) var(--spacing-sm-md) 0 calc(var(--spacing-sm-md) + 4.5em)}
.wfx .axis{position:absolute;left:calc(var(--spacing-sm-md) + 4.5em);right:var(--spacing-sm-md);top:var(--spacing-md);height:16rem;pointer-events:none}
.wfx .gl{position:absolute;left:0;right:0;border-top:1px solid var(--color-hairline)}
.wfx .gy{position:absolute;right:calc(100% + .6em);transform:translateY(-50%);font-size:var(--text--2);color:var(--color-fg-secondary);font-variant-numeric:tabular-nums;white-space:nowrap}
.wf{position:relative;display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:0}
.wf .plot{height:16rem!important}
.wf .cn{position:absolute;left:78%;width:44%;border-top:1px dashed var(--color-mid-gray);z-index:1}
.wf .col{display:flex;flex-direction:column;min-width:0}
.wf .plot{position:relative;height:14rem}
.wf .z{position:absolute;left:-.3em;right:-.3em;border-top:1px solid var(--color-mid-gray)}
.wf .b{position:absolute;left:22%;right:22%;border-radius:2px}
.wf .b.f{background-color:var(--color-mid-gray)} .wf .b.u{background-color:var(--color-red-text)} .wf .b.t{background-color:var(--color-dark-gray)}
.wf .val{position:absolute;left:0;right:0;text-align:center;font-size:var(--text--2);font-variant-numeric:tabular-nums;white-space:nowrap}
.wf .lab{font-size:var(--text--2);color:var(--color-fg-secondary);text-align:center;margin-top:.5em;line-height:1.25}
.wflegend{display:flex;gap:var(--spacing-sm);font-size:var(--text--2);color:var(--color-fg-secondary);padding:var(--spacing-xs) var(--spacing-sm-md) var(--spacing-sm)}
.wflegend i{display:inline-block;width:.8em;height:.8em;border-radius:2px;margin-right:.35em;vertical-align:-.05em}
.split{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--spacing-sm)}
@media (max-width:1000px){.split{grid-template-columns:1fr}}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:.8em var(--spacing-sm);margin-bottom:var(--spacing-sm)}
.stats .l{font-size:var(--text--2);color:var(--color-fg-secondary)} .stats .x{font-variant-numeric:tabular-nums;font-weight:600}
.tax{font-size:var(--text--1)} .tax .row{display:flex;justify-content:space-between} .tax .bar{margin:.25em 0 .7em}
.sign{display:grid;grid-template-columns:10rem 1fr 9rem auto;gap:var(--spacing-2xs);align-items:center;padding:.5em 0;border-bottom:1px solid var(--color-hairline)}
.sign.done{color:var(--color-fg-secondary)}
.ck{display:grid;grid-template-columns:auto 1fr;gap:.2em var(--spacing-xs);padding:.8em var(--spacing-sm-md);border-bottom:1px solid var(--color-hairline)}
.ck .asc{font-family:var(--font-mono);font-size:var(--text--2);color:var(--color-fg-secondary)}
.ck b{display:block}
.ck .opts{display:flex;gap:var(--spacing-3xs);margin-top:.4em}
.ck .opts button{font-size:var(--text--2);padding:.25em .7em}
.note{font-size:var(--text--1);color:var(--color-fg-secondary);line-height:1.5}
.setcard{display:flex;align-items:center;gap:var(--spacing-xs)}
footer{font-size:var(--text--2);color:var(--color-fg-secondary);text-align:center;padding:var(--spacing-md)}
@media print{.top{position:static}.page{display:block!important}}
"""

ICON = {
    "ok": '<svg class="si" viewBox="0 0 16 16" fill="none" stroke="var(--color-mid-gray)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6.5"/><path d="M5 8.2l2 2 4-4.4"/></svg>',
    "mat": '<svg class="si" viewBox="0 0 16 16" fill="none" stroke="var(--color-red-text)" stroke-width="1.5" stroke-linejoin="round"><path d="M8 2.2l6.3 11H1.7z"/><path d="M8 6.6v3M8 11.4v.2" stroke-linecap="round"/></svg>',
    "crit": '<svg class="si" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="var(--color-red-text)"/></svg>',
    "dot": '<svg class="si" viewBox="0 0 16 16"><circle cx="8" cy="8" r="3" fill="var(--color-warm-gray)"/></svg>',
}
SETTINGS_SVG = ('<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round">'
                '<path d="M2.5 4.5h7M12.5 4.5h1M2.5 11.5h1M6.5 11.5h7"/><circle cx="11" cy="4.5" r="1.5"/><circle cx="5" cy="11.5" r="1.5"/></svg>')


def hero(title, sub, tiles):
    return ('<div class="hero"><h1>' + e(title) + "</h1>" + ('<p class="sub2">' + sub + "</p>" if sub else "")
            + '<div class="ht">' + "".join('<div><div class="k">%s</div><div class="v">%s</div><div class="s">%s</div></div>' % t for t in tiles) + "</div></div>")


CHECKLIST = ('<div class="card"><div class="ch">Close checklist</div><div class="tw"><table class="cl"><thead><tr><th>Page</th><th>Status</th>'
             '<th class="n2">Value left</th></tr></thead><tbody data-checklist></tbody></table></div></div>')


def tile(k, v, s=""):
    return '<div class="tile"><div class="k">%s</div><div class="v">%s</div><div class="s">%s</div></div>' % (k, v, s)


def page(pid, inner):
    return '<section class="page" id="p-%s" hidden>%s</section>' % (pid, inner)


def shell(title, product, sections, pages, data, js):
    nav = []
    for si, (stitle, items) in enumerate(sections):
        if len(items) == 1:
            pid, label = items[0][:2]
            nav.append('<div class="tg"><button class="tb pg" data-p="%s">%s<span class="n" data-c="%s"></span></button></div>' % (pid, e(label), pid))
        else:
            sub = "".join('<button class="tb pg" data-p="%s">%s<span class="n" data-c="%s"></span></button>' % (pid, e(label), pid) for pid, label in items)
            nav.append('<div class="tg" data-s="%d"><button class="tb sec" data-s="%d">%s<span class="n" data-cs="%d"></span></button>'
                       '<div class="sub shut" data-s="%d">%s</div></div>' % (si, si, e(stitle), si, si, sub))
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>" + e(title) + "</title><style>" + CSS + "</style></head><body>"
            '<header class="top"><div class="brand">' + BR.LOGO + "<b>" + e(product) + "</b><span>" + e(PERIOD) + "</span></div>"
            "<nav>" + "".join(nav) + '</nav><div class="icons"><button class="tb pg" data-p="settings" data-tip="Settings" aria-label="Settings">'
            + SETTINGS_SVG + "</button></div></header><div id=\"tip\"></div><main>" + "".join(pages)
            + page("settings", '<div class="card"><h3>Settings</h3><div class="pad setcard"><label for="thr">Review threshold</label>'
                   '<span>$</span><input class="f" id="thr" inputmode="numeric" style="width:9ch"></div></div>')
            + '<datalist id="accts">' + "".join('<option value="%s">%s</option>' % (e(k), e(v)) for k, v in sorted(ACC.items()) if v) + "</datalist>"
            + '<datalist id="depts">' + "".join('<option value="%s">' % e(d) for d in DEPTS) + "</datalist>"
            + "<footer>Serif Biomedicines, Inc. (FL87) &middot; " + e(product) + " &middot; " + e(PERIOD) + "</footer></main><script>window.DATA="
            + json.dumps(dict(data, acct={k: v for k, v in ACC.items() if v}), ensure_ascii=False).replace("</", "<\\/") + ";</script><script>" + COMMON_JS + js + "</script></body></html>")


COMMON_JS = r"""
const $ = s => document.querySelector(s), $$ = s => Array.from(document.querySelectorAll(s));
const KEY = 'serif-ui::' + DATA.kind + '::' + DATA.run;
let S = {dec: {}, notes: {}, sign: {}, ck: {}, je: {}, log: [], thr: DATA.thr};
try { S = Object.assign(S, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch (e) {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} };
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = v => v == null ? '–' : (v < 0 ? '($' : '$') + Math.abs(Math.round(v)).toLocaleString('en-US') + (v < 0 ? ')' : '');
/* navigation: a section's pages open beside its title */
function show(pid){
  $$('.page').forEach(p => p.hidden = p.id !== 'p-' + pid);
  $$('.tb.pg').forEach(b => b.classList.toggle('cur', b.dataset.p === pid));
  $$('.tg[data-s]').forEach(g => { const on = !!g.querySelector('.tb.pg.cur');
    g.classList.toggle('open', on); g.querySelector('.sub').classList.toggle('shut', !on); });
  window.scrollTo(0, 0); refresh();
}
document.addEventListener('click', ev => {
  const s = ev.target.closest('.tb.sec');
  if (s){ const f = $('.sub[data-s="' + s.dataset.s + '"] .tb.pg'); if (f) show(f.dataset.p); return; }
  const p = ev.target.closest('.tb.pg'); if (p){ show(p.dataset.p); return; }
  const t = ev.target.closest('.tabs button');
  if (t){ const box = t.closest('[data-tabbox]');
    box.querySelectorAll(':scope > .tabs button').forEach(b => b.classList.toggle('on', b === t));
    box.querySelectorAll(':scope > [data-pane]').forEach(x => x.hidden = x.dataset.pane !== t.dataset.tab); return; }
  const d = ev.target.closest('[data-d]');
  if (d){ decide(d.dataset.d, d.dataset.v, d.dataset.label); return; }
  const sg = ev.target.closest('[data-signbtn]');
  if (sg){ const r = sg.dataset.signbtn, n = $('[data-sname="' + r + '"]'), dt = $('[data-sdate="' + r + '"]');
    if (!n.value.trim()){ n.focus(); return; }
    S.sign[r] = {name: n.value.trim(), date: dt.value.trim() || new Date().toISOString().slice(0, 10), at: new Date().toISOString()};
    save(); refresh(); return; }
  const ck = ev.target.closest('[data-ck]');
  if (ck){ S.ck[ck.dataset.ck] = ck.dataset.v; save(); refresh(); return; }
  const x = ev.target.closest('[data-export]'); if (x){ exportCSV(); return; }
  const rs = ev.target.closest('[data-jereset]'); if (rs){ delete S.je[rs.dataset.jereset]; save(); refresh(); return; }
});
document.addEventListener('input', ev => {
  const t = ev.target;
  if (t.dataset.note !== undefined){ S.notes[t.dataset.note] = t.value; save(); return; }
  if (t.dataset.jef){ editJE(t); return; }
  if (t.id === 'thr'){ const v = Number(String(t.value).replace(/[^0-9.]/g, '')); if (isFinite(v) && v > 0){ S.thr = v; save(); refresh(); } }
});
/* tooltips */
const tip = $('#tip');
document.addEventListener('mousemove', ev => { const t = ev.target.closest('[data-tip]');
  if (!t){ tip.style.display = 'none'; return; }
  tip.innerHTML = t.dataset.tip; tip.style.display = 'block';
  tip.style.left = Math.min(ev.clientX + 14, innerWidth - tip.offsetWidth - 8) + 'px';
  tip.style.top = Math.min(ev.clientY + 14, innerHeight - tip.offsetHeight - 8) + 'px'; });
/* decisions */
const LABEL = {approve:'Approved', reject:'Rejected', modify:'Modified', confirm:'Confirmed', recode:'Recode', ack:'Acknowledged & flagged', none:'No action'};
function decide(id, v, label){
  const cur = S.dec[id];
  if (cur && cur.v === v) delete S.dec[id];
  else S.dec[id] = {v, at: new Date().toISOString()};
  S.log.unshift({at: new Date().toISOString(), id, label: label || id, v: S.dec[id] ? v : 'cleared', note: S.notes[id] || ''});
  save(); refresh();
}
const decided = id => !!S.dec[id] && (['modify', 'recode'].indexOf(S.dec[id].v) < 0 || !!(S.notes[id] || '').trim());
function paintItems(){
  $$('[data-item]').forEach(el => { const id = el.dataset.item, d = S.dec[id];
    el.classList.toggle('done', !!d);
    const st = el.querySelector('.stp'); if (st){ st.textContent = d ? LABEL[d.v] + ((['modify','recode'].indexOf(d.v) > -1 && !(S.notes[id]||'').trim()) ? ', add a note' : '') : 'Pending';
      st.className = 'stp' + (d ? (d.v === 'reject' || d.v === 'none' ? ' rej' : ' done') : ''); }
    el.querySelectorAll('[data-d]').forEach(b => b.classList.toggle('on', !!d && d.v === b.dataset.v));
    const nt = el.querySelector('textarea[data-note]'); if (nt){ nt.hidden = !(d && ['modify','recode','reject','none'].indexOf(d.v) > -1) && !(S.notes[id]||'').trim();
      if (document.activeElement !== nt) nt.value = S.notes[id] || ''; } });
  $$('textarea.c[data-note]').forEach(t => { if (!t.closest('[data-item]') && document.activeElement !== t) t.value = S.notes[t.dataset.note] || ''; });
  paintJE();
}
/* counts: what is open on each page, and in each section */
function counts(){
  $$('[data-c]').forEach(el => { const items = $$('#p-' + el.dataset.c + ' [data-item]');
    const open = items.filter(x => !decided(x.dataset.item)).length; el.textContent = open || ''; });
  $$('[data-cs]').forEach(el => { const n = $$('.sub[data-s="' + el.dataset.cs + '"] [data-c]').reduce((a, x) => a + (Number(x.textContent) || 0), 0);
    el.textContent = n || ''; });
}
function signs(){
  $$('[data-sname]').forEach(n => { const r = n.dataset.sname, s = S.sign[r], row = n.closest('.sign');
    if (s){ n.value = s.name; $('[data-sdate="' + r + '"]').value = s.date; }
    row.classList.toggle('done', !!s); const b = row.querySelector('[data-signbtn]'); if (b) b.textContent = s ? 'Signed' : 'Sign'; });
  $$('[data-ckrow]').forEach(r => { const v = S.ck[r.dataset.ckrow]; r.querySelectorAll('[data-ck]').forEach(b => b.classList.toggle('on', b.dataset.v === v)); });
}
function download(name, text){
  const blob = new Blob(['﻿' + text], {type: 'text/csv;charset=utf-8'});
  const go = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0); };
  if (window.claude && claude.use) claude.use('downloads').then(dl => dl ? dl.save({filename: name, data: blob}) : go()).catch(go); else go();
}
const csv = rows => rows.map(r => r.map(c => { const s = String(c == null ? '' : c); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }).join(',')).join('\n');
/* Proposed Journal Entries: filled in from the run, edited in place. An edit
   is kept in S.je and marks the item Modified (Recode on a vendor line). */
const jeOf = id => S.je[id] ? Object.assign({}, DATA.je[id], {lines: S.je[id]}) : DATA.je[id];
const jeBal = j => Math.round(j.lines.reduce((a, l) => a + (Number(l.debit) || 0) - (Number(l.credit) || 0), 0) * 100) / 100;
const jeNoop = j => { const m = {}; j.lines.forEach(l => { const k = (l.account || '') + '|' + (l.department || ''); m[k] = (m[k] || 0) + (Number(l.debit) || 0) - (Number(l.credit) || 0); });
  return Object.values(m).every(v => Math.abs(v) < 0.005); };
const jeLive = id => { const d = S.dec[id]; return !!d && ['approve', 'modify', 'recode'].indexOf(d.v) > -1 && !!DATA.je[id]; };
const jeReady = id => { const j = jeOf(id); return jeLive(id) && decided(id) && !jeBal(j) && !jeNoop(j) && j.lines.every(l => (l.account || '').trim()); };
function editJE(t){
  const [id, i, f] = t.dataset.jef.split('|');
  if (!S.je[id]) S.je[id] = JSON.parse(JSON.stringify(DATA.je[id].lines));
  S.je[id][i][f] = f === 'debit' || f === 'credit' ? (Number(String(t.value).replace(/[^0-9.]/g, '')) || 0) : t.value.trim();
  const box = t.closest('[data-je]'), v = box.dataset.when || 'modify', d = S.dec[id];
  if (!d || d.v !== v){ const lb = t.closest('[data-item]').querySelector('[data-d]');
    S.dec[id] = {v, at: new Date().toISOString()}; S.log.unshift({at: new Date().toISOString(), id, label: lb ? lb.dataset.label : id, v, note: S.notes[id] || ''}); }
  save(); refresh();
}
function paintJE(){
  const m2 = v => (v < 0 ? '($' : '$') + Math.abs(v).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + (v < 0 ? ')' : '');
  $$('[data-je]').forEach(box => { const id = box.dataset.je, d = S.dec[id], j = jeOf(id);
    if (box.dataset.when) box.hidden = !(d && d.v === box.dataset.when);
    box.classList.toggle('edited', !!S.je[id]);
    box.querySelectorAll('[data-jef]').forEach(inp => { if (inp === document.activeElement) return; const [, i, f] = inp.dataset.jef.split('|'), v = j.lines[i][f];
      inp.value = f === 'debit' || f === 'credit' ? (Number(v) ? Number(v).toFixed(2) : '') : (v || ''); });
    box.querySelectorAll('[data-jean]').forEach(s => { const i = s.dataset.jean.split('|')[1]; s.textContent = DATA.acct[(j.lines[i].account || '').trim()] || ''; });
    const b = jeBal(j), st = box.querySelector('[data-jebal]');
    st.innerHTML = b ? '<span class="unf">Out of balance by ' + m2(b) + '</span>' : jeNoop(j) ? 'No change yet' : 'Balanced';
    box.querySelector('[data-jereset]').hidden = !S.je[id]; });
}
function exportCSV(){
  const rows = [['External ID', 'Date', 'Account', 'Department', 'Debit', 'Credit', 'Memo']];
  const held = Object.keys(DATA.je).filter(id => jeLive(id) && !jeReady(id)).length;
  Object.keys(DATA.je).forEach(id => { if (!jeReady(id)) return;
    const j = jeOf(id); j.lines.forEach(l => rows.push([j.id, j.date, l.account, l.department || '', l.debit || '', l.credit || '', j.memo + (S.notes[id] ? ' | ' + S.notes[id] : '')])); });
  if (rows.length === 1){ alertBox(held ? held + ' entries are out of balance, unchanged or missing a note.' : 'Approve an entry first: only approved entries go into the import.'); return; }
  if (held) alertBox(held + ' entries left out: out of balance, unchanged or missing a note.');
  download('serif-' + DATA.kind + '-netsuite-' + DATA.slug + '.csv', csv(rows));
}
function alertBox(msg){ const t = $('#tip'); t.innerHTML = esc(msg); t.style.display = 'block'; t.style.left = '40%'; t.style.top = '80px'; setTimeout(() => t.style.display = 'none', 2200); }
/* The close checklist: each page, what is open on it, and what that is worth.
   Open is a flag with no decision, or a line at or over the threshold with no
   commentary. */
function checklist(){
  const host = $('[data-checklist]'); if (!host) return;
  const thr = S.thr || DATA.thr, rows = [];
  $$('.tb.pg').forEach(b => { const pid = b.dataset.p, pg = $('#p-' + pid); if (!pg || pid === 'ov' || pid === 'settings') return;
    let total = 0, open = 0, value = 0;
    pg.querySelectorAll('[data-item]').forEach(x => { total++; if (!decided(x.dataset.item)){ open++; value += Number(x.dataset.amt) || 0; } });
    /* A page's other comparisons (year on year, year to date) restate its lines; they count once, on the first. */
    pg.querySelectorAll('tr[data-var]').forEach(tr => { if (tr.closest('[data-alt]')) return; const a = Math.abs(Number(tr.dataset.var) || 0); if (a < thr) return;
      total++; const t = tr.querySelector('textarea[data-note]'); if (!t || !(S.notes[t.dataset.note] || '').trim()){ open++; value += a; } });
    if (!total) return;
    rows.push('<tr class="xp' + (open ? ' open' : '') + '" data-go="' + pid + '"><td><b>' + esc(b.textContent.replace(/\d+$/, '').trim()) + '</b></td><td>' +
      (open ? '<span class="unf">' + open + ' open of ' + total + '</span>' : 'Done, ' + total + ' of ' + total) + '</td><td class="n2">' + (open ? money(value) : '') + '</td></tr>'); });
  host.innerHTML = rows.join('');
}
document.addEventListener('click', ev => { const r = ev.target.closest('tr[data-go]'); if (r) show(r.dataset.go); });
/* a line at or over the threshold is marked for review */
function marks(){
  const thr = S.thr || DATA.thr;
  $$('tr[data-var]').forEach(tr => { const a = Math.abs(Number(tr.dataset.var) || 0);
    const k = a >= thr ? 'rev' : 'ok';
    tr.classList.toggle('crit', k === 'rev'); tr.classList.remove('mat');
    const td = tr.cells[0]; let m = td.querySelector('.mk');
    if (!m){ m = document.createElement('span'); m.className = 'mk'; td.appendChild(m); }
    m.innerHTML = k === 'rev' ? '<span class="tag hi">Review</span>' : ''; });
  const t = $('#thr'); if (t && document.activeElement !== t) t.value = (S.thr || DATA.thr).toLocaleString('en-US');
}
"""


# =====================================================================
# P&L Flux
# =====================================================================
def flux():
    T = PLR["tables"][0]
    secs = T["sections"]
    V = PLR["views"]
    F = {f["finding_id"]: f for f in PLR["findings"]}
    thr = (PLR.get("report") or {}).get("fix_threshold") or 10000
    rows = [(s, r) for s in secs for r in s["rows"]]
    tot = lambda pre, k: sum((s["total"].get(k) or 0) for s in secs if s["label"][:1] in pre)
    opex = {k: tot("67", k) for k in ("actual", "prior", "prior_year")}
    net = {k: tot("678", k) for k in ("actual", "prior", "prior_year")}
    dm = V.get("dept_months") or {"rows": []}
    GA = {"General G&A", "Finance"}
    opx = lambda r, k: sum(a[k] for a in r["accounts"] if a["account"][:1] in "67")
    rd = [sum(opx(r, k) for r in dm["rows"] if r["department"] not in GA | {"Non-Specific"}) for k in ("actual", "prior")]
    ga = [sum(opx(r, k) for r in dm["rows"] if r["department"] in GA) for k in ("actual", "prior")]
    interest = next((s["total"] for s in secs if s["label"].startswith("8110000")), {"actual": 0, "mom_var": 0})
    pay = V.get("payroll") or {}
    bs = V.get("balance_sheet") or {"rows": []}
    bsv = lambda name, m: next((r["values"].get(m) or 0 for r in bs["rows"] if r["name"] == name), 0)
    cash_now, cash_prior = bsv("Total Bank", PERIOD), bsv("Total Bank", PRIOR)
    banks = []
    if bs["rows"]:
        i = next(i for i, r in enumerate(bs["rows"]) if r["name"] == "Bank")
        j = next(i for i, r in enumerate(bs["rows"]) if r["name"] == "Total Bank")
        banks = [r for r in bs["rows"][i:j] if r["kind"] == "account" and round(r["values"].get(PERIOD) or 0)]
    ent = V.get("entries") or []
    mt = next((t for t in V["tables"] if t["id"] == "model_tie"), {"sections": []})
    revs = [r for s in mt["sections"] for r in s["rows"]]
    pages, je = [], {}

    def basis(fid):
        b = ((F.get(fid) or {}).get("evidence") or {}).get("basis") or ""
        v = b.replace("Largest vendors: ", "") if b.startswith("Largest vendors") else ""
        return "" if v.lower().startswith("none") else v

    # ----- Executive Overview
    movers = sorted([r for s, r in rows if round(r.get("mom_var") or 0)], key=lambda r: r["mom_var"])
    favs = [r for r in movers if r["mom_var"] < 0 and not r["account_code"].startswith("811")]
    unfs = [r for r in reversed(movers) if r["mom_var"] > 0 and not r["account_code"].startswith("811")]
    steps = [(r["account_leaf"], -r["mom_var"], r) for r in favs[:3]]
    if favs[3:]:
        steps.append(("Other favorable", -sum(r["mom_var"] for r in favs[3:]), None))
    steps += [(r["account_leaf"], -r["mom_var"], r) for r in unfs[:2]]
    if unfs[2:]:
        steps.append(("Other unfavorable", -sum(r["mom_var"] for r in unfs[2:]), None))
    if round(interest.get("mom_var") or 0):
        steps.append(("Interest", -(interest.get("mom_var") or 0), None))
    # A bridge: July's net loss, each driver stepping it up (unfavorable) or down
    # (favorable), August's net loss. Expense-signed, so a rise raises the loss.
    start, end = net["prior"], net["actual"]
    bsteps = [(lb, -d, r) for lb, d, r in steps]
    run, cols = start, [("July net loss".replace("July", PRIOR[:3]), 0, start, "t", "<b>" + e(PRIOR) + " net loss</b><br>" + money(start))]
    for lb, d, r in bsteps:
        tipx = ("<b>" + e(r["account_code"] + " " + r["account_leaf"]) + "</b><br>" + e(PERIOD) + " " + money(r["actual"]) + "<br>" + e(PRIOR) + " " + money(r["prior"]) + "<br>"
                if r else "<b>" + e(lb) + "</b><br>") + ("Raises the loss by " if d > 0 else "Lowers the loss by ") + money(abs(d))
        cols.append((lb, min(run, run + d), max(run, run + d), "u" if d > 0 else "f", tipx, d))
        run += d
    cols.append((MON + " net loss", 0, end, "t", "<b>" + e(PERIOD) + " net loss</b><br>" + money(end)))
    top_ = max(c[2] for c in cols) * 1.08
    step_ = 10 ** (len(str(int(top_ / 5))) - 1)
    step_ = next(m * step_ for m in (1, 2, 2.5, 5, 10) if top_ / (m * step_) <= 6)
    ticks = [k * step_ for k in range(int(top_ // step_) + 1)]
    y = lambda v: 100.0 * (1 - v / top_)
    grid = "".join('<i class="gl" style="top:%.2f%%"></i><span class="gy" style="top:%.2f%%">%s</span>' % (y(t), y(t), short(t) if t else "$0") for t in ticks)
    body = []
    for n_, c in enumerate(cols):
        lb, lo, hi, cls, tipx = c[0], c[1], c[2], c[3], c[4]
        val = short(hi) if cls == "t" else ("+" if c[5] > 0 else "&minus;") + short(abs(c[5])).strip("()")
        nxt = hi if (cls == "t" or c[5] > 0) else lo
        cn = ('<i class="cn" style="top:%.2f%%"></i>' % y(nxt)) if n_ < len(cols) - 1 else ""
        body.append('<div class="col" data-tip="%s"><div class="plot"><i class="b %s" style="top:%.2f%%;height:%.2f%%"></i>%s'
                    '<span class="val" style="top:calc(%.2f%% - 1.3em)">%s</span></div><div class="lab">%s</div></div>'
                    % (e(tipx), cls, y(hi), max(y(lo) - y(hi), .5), cn, y(hi), val, e(lb)))
    wf = '<div class="wfx"><div class="axis">' + grid + '</div><div class="wf">' + "".join(body) + "</div></div>"
    tiles = [("Total OpEx", short(opex["actual"]), fav(-(opex["actual"] - opex["prior"]), ("&#9660; " if opex["actual"] < opex["prior"] else "&#9650; ") + short(abs(opex["actual"] - opex["prior"]))) + " vs. " + e(PRIOR)),
             ("Net Loss", short(-net["actual"]), fav(-(net["actual"] - net["prior"]), short(abs(net["actual"] - net["prior"])) + (" favorable" if net["actual"] < net["prior"] else " unfavorable")) + " MoM"),
             ("YoY Net Loss", short(-net["actual"]), fav(-(net["actual"] - net["prior_year"]), short(abs(net["actual"] - net["prior_year"])) + (" favorable" if net["actual"] < net["prior_year"] else " unfavorable")) + " vs. " + e(PY)),
             ("Adj Pending", '<span data-pending>' + str(len(ent) + len(revs)) + "</span>", "Review before close")]
    cards = [tile("R&amp;D Spend (" + MON + ")", short(rd[0]), fav(-(rd[0] - rd[1]), short(abs(rd[0] - rd[1]))) + " vs. " + e(PRIOR[:3])),
             tile("G&amp;A Spend (" + MON + ")", short(ga[0]), fav(-(ga[0] - ga[1]), short(abs(ga[0] - ga[1]))) + " vs. " + e(PRIOR[:3])),
             tile("Interest Income", short(-interest["actual"]), fav(-(interest.get("mom_var") or 0), short(abs(interest.get("mom_var") or 0))) + " vs. " + e(PRIOR[:3])),
             tile("Total Headcount", str(sum((pay.get("headcount") or {}).get("by_type", {}).values())),
                  " &middot; ".join(e(str(n) + " " + k) for k, n in ((pay.get("headcount") or {}).get("by_type") or {}).items())),
             tile("Cash &amp; Equiv. (" + MON + " BS)", short(cash_now),
                  " &middot; ".join(e(r["name"].split(" - ", 1)[-1].replace("Serif - ", "")) + ": " + short(r["values"][PERIOD]) for r in banks)),
             tile("Flags to Review", '<span data-cm></span>', '<span data-cmn></span>')]
    pages.append(page("ov", hero("P&L Flux Analysis, " + PERIOD, "", tiles) + '<div class="grid">' + "".join(cards) + "</div>"
                      + '<div class="card"><div class="ch">Net Loss Bridge, ' + e(PRIOR) + ' to ' + e(PERIOD) + '</div>' + wf
                      + '<div class="wflegend"><span><i style="background:var(--color-dark-gray)"></i>Net loss</span><span><i style="background:var(--color-red-text)"></i>Raises the loss</span>'
                        '<span><i style="background:var(--color-mid-gray)"></i>Lowers the loss</span></div></div>' + CHECKLIST))

    # ----- Actual vs. Actual
    def var_table(kind):
        base, label = ("prior", PRIOR) if kind == "mom" else ("prior_year", PY)
        out, fv, uf = [], 0.0, 0.0
        for s in secs:
            live = [r for r in s["rows"] if round(r.get("actual") or 0) or round(r.get(base) or 0)]
            if not live:
                continue
            out.append('<tr class="grp"><td colspan="6">' + e(s["label"].split(" - ", 1)[-1]) + "</td></tr>")
            for r in live:
                v = (r.get(base) or 0) - (r.get("actual") or 0)       # favorable positive
                fv += v if v > 0 else 0
                uf += v if v < 0 else 0
                fid = r.get("mom_finding") if kind == "mom" else None
                vend = basis(fid) if fid else ""
                line = (money(abs(v)) + (" favorable " if v > 0 else " unfavorable ") + ("MoM" if kind == "mom" else "YoY")
                        + (" (" + format(abs(100 * v / r[base]), ".1f") + "%)" if r.get(base) else "") + "." + (" Largest vendors: " + e(vend) + "." if vend else ""))
                key = kind + ":" + r["account_code"]
                out.append('<tr data-var="%s"><td><span class="code">%s</span>%s</td><td class="n2">%s</td><td class="n2">%s</td>'
                           '<td class="n2">%s</td><td class="n2">%s</td><td><div class="cm">%s</div><textarea class="c" rows="1" data-note="%s" placeholder="Commentary"></textarea></td></tr>'
                           % (round(v, 2), e(r["account_code"]), e(r["account_leaf"]), money(r["actual"]), money(r.get(base)), fav(v), fav(v, pct(v, r.get(base))) if r.get(base) else "&ndash;",
                              line if round(v) else "No change.", key))
        head = ("<thead><tr><th>Account</th><th class=\"n2\">" + e(PERIOD) + "</th><th class=\"n2\">" + e(label) + "</th><th class=\"n2\">$ Var</th>"
                "<th class=\"n2\">% Var</th><th style=\"width:42%\">Commentary</th></tr></thead>")
        sm = ('<div class="sumline">Favorable: <b>' + money(fv) + "</b> Unfavorable: <b class=\"unf\">" + money(uf) + "</b> To review: <b data-ccount></b></div>")
        return sm + '<div class="tw"><table>' + head + "<tbody>" + "".join(out) + "</tbody></table></div>"
    ch = opex["actual"] - opex["prior"]
    chy = opex["actual"] - opex["prior_year"]
    pages.append(page("ava", hero("Actual vs. Actual, MoM &amp; YoY".replace("&amp;", "&"), "", [
        ("Total OpEx " + MON, short(opex["actual"]), ""),
        ("vs. " + PRIOR, fav(-ch, ("&#9660; " if ch < 0 else "&#9650; ") + short(abs(ch))), fav(-ch, pct(-ch, opex["prior"]).lstrip("+") + (" favorable" if ch < 0 else " unfavorable"))),
        ("vs. " + PY, fav(-chy, ("&#9660; " if chy < 0 else "&#9650; ") + short(abs(chy))), fav(-chy, pct(-chy, opex["prior_year"]).lstrip("+-") + (" favorable YoY" if chy < 0 else " unfavorable YoY"))),
        ("To Review (MoM)", '<span data-cm></span>', '<span data-cmn></span>')])
        + '<div class="card" data-tabbox><div class="tabs"><button class="on" data-tab="mom">MoM: ' + e(MON + " vs. " + PRIOR) + '</button><button data-tab="yoy">YoY: '
        + e(MON + " " + PERIOD[-2:] + " vs. " + PY) + '</button></div><div data-pane="mom">' + var_table("mom") + '</div><div data-pane="yoy" data-alt hidden>' + var_table("yoy") + "</div></div>"))

    # ----- Actual vs. Budget
    bud_rows = [(s, r) for s, r in rows if r.get("budget") is not None]
    act_p = sum(r["actual"] or 0 for s, r in bud_rows)
    bud = sum(r["budget"] or 0 for s, r in bud_rows)
    out = []
    for s in secs:
        live = [r for r in s["rows"] if r.get("budget") is not None or round(r.get("actual") or 0)]
        if not live:
            continue
        out.append('<tr class="grp"><td colspan="6">' + e(s["label"].split(" - ", 1)[-1]) + "</td></tr>")
        for r in live:
            if r.get("budget") is None:
                out.append('<tr data-var="0" data-mark="dot"><td><span class="code">%s</span>%s</td><td class="n2">%s</td><td class="n2">&ndash;</td><td class="n2">&ndash;</td><td class="n2">&ndash;</td>'
                           '<td><div class="cm">No plan line for this account.</div><textarea class="c" rows="1" data-note="avb:%s" placeholder="Commentary"></textarea></td></tr>'
                           % (e(r["account_code"]), e(r["account_leaf"]), money(r["actual"]), e(r["account_code"])))
                continue
            v = (r["budget"] or 0) - (r["actual"] or 0)
            line = money(abs(v)) + (" under plan" if v > 0 else " over plan") + (" (" + format(abs(100 * v / r["budget"]), ".1f") + "%)." if r["budget"] else ".")
            out.append('<tr data-var="%s"><td><span class="code">%s</span>%s</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td>'
                       '<td><div class="cm">%s</div><textarea class="c" rows="1" data-note="avb:%s" placeholder="Commentary"></textarea></td></tr>'
                       % (round(v, 2), e(r["account_code"]), e(r["account_leaf"]), money(r["actual"]), money(r["budget"]), fav(v), fav(v, pct(v, r["budget"])) if r["budget"] else "&ndash;",
                          line if round(v) else "On plan.", e(r["account_code"])))
    pages.append(page("avb", hero("Actual vs. Budget, " + PERIOD, "Plan: the " + e(PLR["views"]["tables"][[t["id"] for t in PLR["views"]["tables"]].index("dept_plan")].get("vintage") or "2026-06") + " vintage of the rolling forecast", [
        (MON + " Actual OpEx", short(act_p), "Accounts with a plan line"),
        ("Plan " + MON, short(bud), ""),
        (MON + " vs. Plan", fav(bud - act_p, ("&#9660; " if act_p < bud else "&#9650; ") + short(abs(bud - act_p))), fav(bud - act_p, "Under plan" if act_p < bud else "Over plan")),
        ("YTD Burn", short(ytd), "Jan&ndash;" + MON + " " + PERIOD[-4:] + " operating expense")])
        + '<div class="card"><div class="ch">Actual vs. Plan, ' + e(PERIOD) + '</div><div class="tw"><table><thead><tr><th>Account</th><th class="n2">' + e(PERIOD)
        + ' Actual</th><th class="n2">Plan</th><th class="n2">$ vs. Plan</th><th class="n2">% vs. Plan</th><th style="width:40%">Commentary</th></tr></thead><tbody>' + "".join(out) + "</tbody></table></div></div>"))

    # ----- By Department (MoM)
    staff = {r["department"]: r for r in (pay.get("rows") or [])}
    drows = [r for r in dm["rows"] if r["department"] != "Non-Specific" and (round(r["actual"]) or round(r["prior"]))]
    big = max(drows, key=lambda r: r["actual"])
    swing = max(drows, key=lambda r: abs(r["change"]))
    tabs_, panes = [], []
    for k, r in enumerate(drows):
        reg = [p for p in (staff.get(r["department"], {}).get("people") or []) if p["type"] == "Regular"]
        avg = statistics.mean([p["salary"] for p in reg]) if reg else None
        v = -(r["change"])
        trs = []
        for a in r["accounts"]:
            av = -(a["change"])
            vend = dept_acct_vendor.get((r["department"], a["account"])) or {}
            top3 = sorted(vend.items(), key=lambda kv: -abs(kv[1][0] - kv[1][1]))[:3]
            gl = "; ".join("%s %s (%s%s vs. %s)" % (e(n), money(x[0]), "&#9660;" if x[0] < x[1] else "&#9650;", money(abs(x[0] - x[1])), e(PRIOR[:3])) for n, x in top3 if round(x[0]) or round(x[1]))
            line = (money(abs(av)) + (" favorable" if av > 0 else " unfavorable") + " MoM" + (" (" + format(abs(100 * av / a["prior"]), ".0f") + "%)" if a["prior"] else "") + ". " if round(av) else "No change. ") + ("GL: " + gl + "." if gl else "")
            trs.append('<tr data-var="%s"><td><span class="code">%s</span>%s</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td>'
                       '<td><div class="cm">%s</div><textarea class="c" rows="1" data-note="dept:%s:%s" placeholder="Commentary"></textarea></td></tr>'
                       % (round(av, 2), e(a["account"]), e(a["leaf"] or acct_name(a["account"])), money(a["actual"]), money(a["prior"]), fav(av), fav(av, pct(av, a["prior"])) if a["prior"] else "&ndash;",
                          line, e(r["department"]), e(a["account"])))
        trs.append('<tr class="tot"><td>Department total</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td><td></td></tr>'
                   % (money(r["actual"]), money(r["prior"]), fav(v), fav(v, pct(v, r["prior"])) if r["prior"] else "&ndash;"))
        tabs_.append('<button%s data-tab="d%d">%s</button>' % (' class="on"' if k == 0 else "", k, e(r["department"])))
        panes.append('<div data-pane="d%d"%s><div class="pad"><div class="grid" style="margin:0">%s%s%s%s</div></div><div class="tw"><table><thead><tr><th>Account</th><th class="n2">%s</th>'
                     '<th class="n2">%s</th><th class="n2">$ Var</th><th class="n2">%% Var</th><th style="width:42%%">Commentary</th></tr></thead><tbody>%s</tbody></table></div></div>'
                     % (k, "" if k == 0 else " hidden", tile(e(PERIOD) + " Total", money(r["actual"])), tile(e(PRIOR) + " Total", money(r["prior"])),
                        tile("MoM Variance", fav(v, ("&#9660; " if v > 0 else "&#9650; ") + money(abs(v))), fav(v, (pct(v, r["prior"]).lstrip("+-") + (" favorable" if v > 0 else " unfavorable")) if r["prior"] else "")),
                        tile("Reg. Headcount", str(len(reg)), ("Avg salary " + short(avg)) if avg else ""), e(PERIOD), e(PRIOR), "".join(trs)))
    pages.append(page("dept", hero("By Department, " + MON + " vs. " + PRIOR + " (Month-over-Month)", "", [
        ("Departments", str(len(drows)), ""), ("Largest (" + MON + ")", e(big["department"]), short(big["actual"]) + " " + MON + " spend"),
        ("Biggest Swing", e(swing["department"]), fav(-swing["change"], ("&#9660; " if swing["change"] < 0 else "&#9650; ") + short(abs(swing["change"])))),
        ("Total P&amp;L (" + MON + ")", short(sum(r["actual"] for r in dm["rows"])), "")])
        + '<div class="card" data-tabbox><div class="tabs">' + "".join(tabs_) + "</div>" + "".join(panes) + "</div>"))

    # ----- Payroll Analytics
    SS_CAP, SS_R, MED_R, SUI_R, SUI_CAP = 176100, .062, .0145, .03, 15000
    comp, ptabs, ppanes, tot = [], [], [], defaultdict(float)
    prows = [r for r in (pay.get("rows") or []) if r.get("people")]
    prows.sort(key=lambda r: r["department"])
    for k, r in enumerate(sorted(prows, key=lambda r: -len([p for p in r["people"] if p["type"] == "Regular"]))):
        reg = [p for p in r["people"] if p["type"] == "Regular" and p["salary"]]
        if not reg:
            continue
        sal = [p["salary"] for p in reg]
        mon = sum(sal) / 12
        ss = sum(min(s, SS_CAP) * SS_R for s in sal) / 12
        med = sum(s * MED_R for s in sal) / 12
        sui = sum(min(s, SUI_CAP) * SUI_R for s in sal) / 12
        tax = ss + med + sui
        bon = sum(p["salary"] * (p["bonus_pct"] or 0) / 100 for p in reg)
        avgb = statistics.mean([p["bonus_pct"] or 0 for p in reg])
        glt = r.get("taxes") or 0
        for kk, vv in (("hc", len(reg)), ("mon", mon), ("tax", tax), ("bon", bon), ("sal", sum(sal))):
            tot[kk] += vv
        comp.append('<tr><td><b>%s</b></td><td class="n2">%d</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td>'
                    '<td class="n2">%s</td><td class="n2">%.1f%%</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%.1f%%</td><td class="n2">%s</td></tr>'
                    % (e(r["department"]), len(reg), short(statistics.mean(sal)), money(mon), money(ss), money(med), money(sui), money(tax), 100 * tax / mon, money(glt),
                       fav(-(glt - tax), ("+" if glt > tax else "") + money(glt - tax)), avgb, money(bon)))
        others = [p for p in r["people"] if p not in reg]
        roster = "".join('<tr><td>%s</td><td>%s</td><td>%s</td><td class="n2">%s</td><td class="n2">%s</td></tr>'
                         % (e(p["name"]), e(p["title"]), e(p["type"]), money(p["salary"]) if p["salary"] else "&ndash;", (format(p["bonus_pct"], ".2f") + "%") if p.get("bonus_pct") else "&ndash;")
                         for p in reg + others)
        mx = max(ss, med, sui) or 1
        taxbars = "".join('<div class="row"><span>%s</span><span>%s</span></div><div class="bar"><i style="width:%.1f%%"></i></div>' % (lab, money(v), 100 * v / mx)
                          for lab, v in (("Social Security (6.2%, cap $176,100)", ss), ("Medicare (1.45%, uncapped)", med), ("MA SUI (~3%, first $15K)", sui)))
        ptabs.append('<button%s data-tab="pd%d">%s</button>' % (' class="on"' if not ptabs else "", k, e(r["department"])))
        ppanes.append('<div data-pane="pd%d"%s><div class="pad split"><div><h3 style="margin:0 0 .8em">%s, Payroll Analytics</h3><div class="stats">'
                      '<div><div class="l">Headcount (roster)</div><div class="x">%d</div></div><div><div class="l">Avg annual salary</div><div class="x">%s</div></div>'
                      '<div><div class="l">Median salary</div><div class="x">%s</div></div><div><div class="l">Theoretical monthly salary</div><div class="x">%s</div></div>'
                      '<div><div class="l">GL salary %s (6101000)</div><div class="x">%s</div></div><div><div class="l">Salary variance</div><div class="x">%s</div></div>'
                      '<div><div class="l">GL bonus %s (6102000)</div><div class="x">%s</div></div><div><div class="l">GL benefits %s (6104000)</div><div class="x">%s</div></div>'
                      '<div><div class="l">Avg bonus target</div><div class="x">%.1f%%</div></div></div><h4 style="margin:.4em 0">Payroll Tax Breakdown</h4><div class="tax">%s'
                      '<div class="row"><b>Total theoretical payroll tax</b><b>%s (%.1f%% of wages)</b></div><div class="row"><span>GL payroll tax (6103000 %s actual)</span><span>%s</span></div>'
                      '<div class="row"><span>Variance (GL vs. theoretical)</span><span>%s</span></div><div class="row"><span>Est. annual bonus pool (at target)</span><span>%s</span></div></div></div>'
                      '<div><h3 style="margin:0 0 .8em">Roster, %s</h3><div class="tw"><table><thead><tr><th>Name</th><th>Title</th><th>Type</th><th class="n2">Annual salary</th><th class="n2">Bonus %%</th></tr></thead>'
                      '<tbody>%s</tbody></table></div></div></div></div>'
                      % (k, "" if len(ptabs) == 1 else " hidden", e(r["department"]), len(r["people"]), short(statistics.mean(sal)), short(statistics.median(sal)), money(mon), MON, money(r.get("salaries")),
                         fav(-((r.get("salaries") or 0) - mon), money((r.get("salaries") or 0) - mon)), MON, money(r.get("bonus")), MON, money(r.get("benefits")), avgb, taxbars, money(tax), 100 * tax / mon,
                         MON, money(glt), fav(-(glt - tax), ("+" if glt > tax else "") + money(glt - tax)), money(bon), e(r["department"]), roster))
    t = pay.get("total") or {}
    comp.append('<tr class="tot"><td>Total</td><td class="n2">%d</td><td class="n2">&ndash;</td><td class="n2">%s</td><td class="n2">&ndash;</td><td class="n2">&ndash;</td><td class="n2">&ndash;</td>'
                '<td class="n2">%s</td><td class="n2">%.1f%%</td><td class="n2">%s</td><td class="n2">&ndash;</td><td class="n2">&ndash;</td><td class="n2">%s</td></tr>'
                % (tot["hc"], money(tot["mon"]), money(tot["tax"]), 100 * tot["tax"] / (tot["mon"] or 1), money(t.get("taxes")), money(tot["bon"])))
    pages.append(page("pay", hero("Payroll Analytics, Compensation &amp; Benefits by Department".replace("&amp;", "&"), "", [
        ("Total Annual Salary", short(tot["sal"]), "%d Regular FTE" % tot["hc"]), ("Monthly Run Rate", short(tot["mon"]), "Excl. Co-Op &amp; consultants"),
        ("Avg Payroll Tax Rate", "%.1f%%" % (100 * tot["tax"] / (tot["mon"] or 1)), "SS 6.2% + Med 1.45% + SUI ~3%"), ("Est. Annual Bonus Pool", short(tot["bon"]), "At target % per roster")])
        + '<div class="card"><div class="ch">Compensation Summary, All Departments (Monthly, Regular Employees)</div><div class="tw"><table><thead><tr><th>Department</th><th class="n2">HC</th>'
          '<th class="n2">Avg Salary</th><th class="n2">Monthly Salary</th><th class="n2">SS (6.2%)</th><th class="n2">Medicare (1.45%)</th><th class="n2">SUI (~3%)</th><th class="n2">Total Tax</th>'
          '<th class="n2">PT % Wages</th><th class="n2">GL 6103000 ' + MON + '</th><th class="n2">GL vs. Theoretical</th><th class="n2">Avg Bonus %</th><th class="n2">Est. Bonus Pool</th></tr></thead><tbody>'
        + "".join(comp) + '</tbody></table></div></div><div class="card" data-tabbox><div class="ch">Department Detail, Payroll Breakdown &amp; Roster</div><div class="tabs">' + "".join(ptabs) + "</div>" + "".join(ppanes) + "</div>"))

    # ----- Balance Sheet Flux
    def bs_table(cmpm, word):
        """The report as NetSuite lays it out: headings and totals by level, the
        account lines carry the review and the commentary. A heading shows only
        over lines that show; a total over a single line repeats it and is left out."""
        out, sums = [], {}
        rows_ = bs["rows"]
        live = lambda r: round(r["values"].get(PERIOD) or 0) or round(r["values"].get(cmpm) or 0)
        # lines under each heading, so a total over one line, and an empty heading, can be left out
        under, stack = {}, []
        for k, r in enumerate(rows_):
            if r["kind"] == "head":
                while stack and rows_[stack[-1]]["depth"] >= r["depth"]:
                    stack.pop()
                stack.append(k); under[k] = 0
            elif r["kind"] == "account":
                if live(r):
                    for h in stack:
                        under[h] += 1
            else:
                while stack and rows_[stack[-1]]["depth"] > r["depth"]:
                    stack.pop()
                h = stack.pop() if stack and rows_[stack[-1]]["depth"] == r["depth"] else None
                under[k] = under.get(h, 0) if h is not None else 2
        pad = lambda d: ' style="padding-left:calc(.8em + %.1fem)"' % (d * 1.1)
        for k, r in enumerate(rows_):
            name = r["name"].replace("Total - ", "Total ")
            if r["kind"] == "head":
                if under.get(k, 0) >= (1 if r["depth"] < 2 else 2):
                    out.append('<tr class="grp lv%d"><td colspan="6"%s>%s</td></tr>' % (min(r["depth"], 2), pad(r["depth"]), e(name)))
                continue
            if not live(r):
                continue
            a, b = r["values"].get(PERIOD) or 0, r["values"].get(cmpm) or 0
            ch = a - b
            sums[r["name"]] = ch
            if r["kind"] == "total":
                if under.get(k, 2) <= 1 and not r["name"] in ("Total ASSETS", "Total Bank", "Total Equity", "Total Liabilities & Equity"):
                    continue
                out.append('<tr class="tot"><td%s>%s</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td><td></td></tr>'
                           % (pad(r["depth"]), e(name), money(a), money(b), money(ch), pct(ch, b) if b else "&ndash;"))
                continue
            nm = r["name"].split(" - ", 1)
            label = ('<span class="code">%s</span>%s' % (e(nm[0]), e(nm[1]))) if r["code"] and len(nm) == 2 else e(r["name"])
            line = ("Flat " + word + "." if not round(ch) else money(abs(ch)) + (" increase " if ch > 0 else " decrease ") + word + ".")
            out.append('<tr data-var="%s"><td%s>%s</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td>'
                       '<td><div class="cm">%s</div><textarea class="c" rows="1" data-note="bs:%s:%s" placeholder="Commentary"></textarea></td></tr>'
                       % (round(ch, 2), pad(r["depth"]), label, money(a), money(b), money(ch), pct(ch, b) if b else "&ndash;", line, e(cmpm), e(r["name"])))
        g = lambda n: sums.get(n, 0)
        sm = ('<div class="sumline">Total assets change: <b>%s</b> Cash change: <b>%s</b> Liabilities change: <b>%s</b> Equity change: <b>%s</b></div>'
              % (money(g("Total ASSETS")), money(g("Total Bank")), money(g("Total Current Liabilities") + g("Total Long Term Liabilities")), money(g("Total Equity"))))
        return sm + ('<div class="tw"><table><thead><tr><th>Account</th><th class="n2">%s</th><th class="n2">%s</th><th class="n2">$ Change</th><th class="n2">%% Change</th>'
                     '<th style="width:40%%">Commentary</th></tr></thead><tbody>%s</tbody></table></div>' % (e(PERIOD), e(cmpm), "".join(out)))
    if bs["rows"]:
        tl = lambda m: bsv("Total Current Liabilities", m) + bsv("Total Long Term Liabilities", m)
        d = lambda n, f=bsv: f(n, PERIOD) - f(n, PRIOR)
        pages.append(page("bs", hero("Balance Sheet Flux, " + PERIOD + " vs. " + PRIOR + " vs. " + YEAR_END, "", [
            ("Total Assets " + MON, short(bsv("Total ASSETS", PERIOD)), money(d("Total ASSETS")) + " vs. " + e(PRIOR[:3])),
            ("Cash &amp; Equiv.", short(cash_now), money(cash_now - cash_prior) + " vs. " + e(PRIOR[:3])),
            ("Total Liabilities", short(tl(PERIOD)), money(tl(PERIOD) - tl(PRIOR)) + " vs. " + e(PRIOR[:3])),
            ("Total Equity", short(bsv("Total Equity", PERIOD)), money(d("Total Equity")) + " vs. " + e(PRIOR[:3]))])
            + '<div class="card" data-tabbox><div class="tabs"><button class="on" data-tab="b1">' + e(MON + " vs. " + PRIOR) + '</button><button data-tab="b2">' + e(MON + " vs. " + YEAR_END + " (YTD)")
            + '</button><button data-tab="b3">' + e(PERIOD + " vs. " + PY) + '</button></div><div data-pane="b1">' + bs_table(PRIOR, "MoM") + '</div><div data-pane="b2" data-alt hidden>'
            + bs_table(YEAR_END, "YTD") + '</div><div data-pane="b3" data-alt hidden>' + bs_table(PY, "YoY") + "</div></div>"))

    # ----- Adjustments
    cards_a, cards_b, impact = [], [], 0.0
    for n, x in enumerate(ent, 1):
        f = F.get(x["finding_id"]) or {}
        aid = "ADJ-%03d" % n
        pl = [l for l in x["lines"] if PNL(l["account"])]
        bsl = [l for l in x["lines"] if not PNL(l["account"])]
        imp = sum((l.get("credit") or 0) - (l.get("debit") or 0) for l in pl)
        impact += imp
        acct = pl[0] if pl else x["lines"][0]
        vend = sorted({l.get("vendor") for l in x["lines"] if l.get("vendor")})
        hi = x["debits"] >= thr
        je[aid] = {"id": x["entry_id"], "date": x["date"], "memo": x["memo"], "lines": je_lines(x["lines"])}
        dr = "".join('<div class="ln"><span>%s %s%s</span><span>%s</span></div>' % (e(l["account"]), e(acct_name(l["account"])), (" / " + e(l["department"])) if l.get("department") else "", money(l["debit"], True)) for l in x["lines"] if l.get("debit"))
        cr = "".join('<div class="ln"><span>%s %s%s</span><span>%s</span></div>' % (e(l["account"]), e(acct_name(l["account"])), (" / " + e(l["department"])) if l.get("department") else "", money(l["credit"], True)) for l in x["lines"] if l.get("credit"))
        docs = sorted({d for l in x["lines"] for d in (l.get("documents") or [])})[:4]
        cards_a.append('<div class="item%s" data-item="%s" data-amt="%s"><div class="ih"><span class="tag ink">%s</span><b>%s</b>%s<span class="stp">Pending</span></div><div class="ib"><div class="kv">'
                       '<div><div class="l">Account</div><div class="x">%s %s</div></div><div><div class="l">Amount</div><div class="x">%s</div></div><div><div class="l">P&amp;L impact</div><div class="x">%s</div></div>'
                       '<div><div class="l">Vendor (GL)</div><div class="x">%s</div></div><div><div class="l">BS impact</div><div class="x">%s</div></div><div><div class="l">Dept</div><div class="x">%s</div></div></div>'
                       '<div class="why">%s%s</div><div class="pol">%s</div>%s'
                       '<div class="acts"><button class="pill" data-d="%s" data-v="approve" data-label="%s">Approve</button><button class="pill" data-d="%s" data-v="reject" data-label="%s">Reject</button>'
                       '<button class="pill" data-d="%s" data-v="modify" data-label="%s">Modify</button><textarea class="c" rows="1" data-note="%s" placeholder="Note" hidden></textarea></div></div></div>'
                       % (" hi" if hi else "", aid, round(x["debits"], 2), e(x.get("kind") or ""), e(x["memo"]), "", e(acct["account"]), e(acct_name(acct["account"])), money(x["debits"], True),
                          fav(imp, ("&#9660; Favorable " if imp > 0 else "&#9650; Unfavorable " if imp < 0 else "No P&amp;L impact") + (money(abs(imp), True) if round(imp) else "")),
                          e(", ".join(vend) or "&ndash;"), e(", ".join("%s %s %s" % (l["account"], acct_name(l["account"]), money((l.get("debit") or 0) - (l.get("credit") or 0), True).replace("&ndash;", "-")) for l in bsl)) or "&ndash;",
                          e(", ".join(sorted({l.get("department") for l in x["lines"] if l.get("department")})) or "&ndash;"),
                          e(f.get("recommendation") or x.get("support") or x["memo"]), (" " + " ".join(doc_links(d) for d in docs)) if docs else "", e(f.get("policy_basis") or ""), je_editor(aid, je[aid]["lines"]),
                          aid, e(x["memo"]), aid, e(x["memo"]), aid, e(x["memo"]), aid))
    for n, r in enumerate(revs, 1):
        rid = "REV-%03d" % n
        f = F.get(r["finding_id"]) or {}
        v = r.get("difference") or 0
        cards_b.append('<div class="item" data-item="%s" data-amt="%s"><div class="ih"><span class="tag hi">Forecast revision</span><b>%s</b><span class="stp">Pending</span></div><div class="ib"><div class="kv">'
                       '<div><div class="l">Account</div><div class="x">%s %s%s</div></div><div><div class="l">Variance (ledger vs. forecast)</div><div class="x">%s</div></div>'
                       '<div><div class="l">Impact</div><div class="x">Forecast only, no Journal Entry</div></div></div><div class="why">%s</div>'
                       '<div class="acts"><button class="pill" data-d="%s" data-v="ack" data-label="%s">Acknowledge &amp; Flag</button><button class="pill" data-d="%s" data-v="none" data-label="%s">No Action</button>'
                       '<textarea class="c" rows="1" data-note="%s" placeholder="Note" hidden></textarea></div></div></div>'
                       % (rid, round(abs(v), 2), e(r["account"] + " " + acct_name(r["account"]) + ((" / " + r["department"]) if r.get("department") else "")), e(r["account"]), e(acct_name(r["account"])), (" / " + e(r["department"])) if r.get("department") else "",
                          "Ledger %s, forecast %s, difference %s" % (money(r.get("ledger")), money(r.get("model")), money(v)), e(f.get("recommendation") or f.get("title") or ""), rid, "Forecast revision " + e(r["account"]), rid, "Forecast revision " + e(r["account"]), rid))
    pages.append(page("adj", hero("Accounting Adjustments &amp; Forecast Revisions, ".replace("&amp;", "&") + PERIOD, "", [
        ("Accounting Adj", str(len(ent)), "Affect P&amp;L / BS"), ("Forecast Revisions", str(len(revs)), "No Journal Entry required"),
        ("P&amp;L Impact (if all approved)", fav(impact, ("&#9660; " if impact > 0 else "&#9650; ") + short(abs(impact))), "Favorable" if impact > 0 else "Unfavorable"),
        ("Reviewed", '<span data-prog>0%</span>', '<span data-progn></span>')])
        + '<div class="card"><div class="ch">NetSuite Journal Entries<button class="pill solid r" data-export>Download NetSuite JE CSV</button></div></div><h3 style="margin:var(--spacing-md) 0 var(--spacing-xs)">Section A: Accounting Adjustments</h3>' + "".join(cards_a)
        + '<h3 style="margin:var(--spacing-md) 0 var(--spacing-xs)">Section B: Forecast / Budget Revisions</h3>' + "".join(cards_b)))

    # ----- SOX & GAAP
    asc = [("ASC 225-10", "Income Statement Presentation"), ("ASC 250-10", "Consistent Accounting Periods"), ("ASC 280-10", "Segment / Department Reporting"),
           ("ASC 718-10", "Stock-Based Compensation"), ("ASC 842", "Lease Classification"), ("ASC 350-40", "Internal-Use Software Capitalization"),
           ("ASC 330-10", "Lab Supplies / Inventory"), ("ASC 420", "Exit / Disposal Costs")]
    ck = "".join('<div class="ck" data-ckrow="%s"><span class="asc">%s</span><div><b>%s</b><div class="opts"><button class="pill" data-ck="%s" data-v="ok">Reviewed</button>'
                 '<button class="pill" data-ck="%s" data-v="flag">Needs follow-up</button></div><textarea class="c" rows="1" data-note="asc:%s" placeholder="Note" style="margin-top:.4em"></textarea></div></div>'
                 % (k, k, e(t), k, k, k) for k, t in asc)
    src = "".join('<tr><td>%s</td><td class="mono">%s</td><td class="n2">%s rows</td></tr>' % (e(", ".join(i.get("roles") or [i.get("role") or ""])), e(i["path"]), format(i.get("rows") or 0, ","))
                  for i in M["inputs"] + [x for x in V.get("inputs", []) if x.get("path") not in {y["path"] for y in M["inputs"]}])
    # Tie-outs: the ledger against NetSuite's own reports
    gsum = lambda pre, m=PERIOD: sum(l["amount"] for l in by_period.get(m, []) if l["account_code"].startswith(pre))
    ties = []

    def tie(what, a, b, la, lb):
        ok = abs(round(a - b, 2)) < 0.01
        ties.append('<tr><td>%s</td><td class="n2">%s<small>%s</small></td><td class="n2">%s<small>%s</small></td><td>%s</td></tr>'
                    % (e(what), money(a, True), e(la), money(b, True), e(lb), "Pass" if ok else '<span class="unf">Difference %s</span>' % money(a - b, True)))
    tl = M.get("tie_out") or {}
    ties.append('<tr><td>GL debits equal credits</td><td class="n2" colspan="2">%s</td><td>%s</td></tr>' % (e(tl.get("note") or ""), "Pass" if tl.get("passed") else '<span class="unf">Fail</span>'))
    ISR = {}
    if IS_X:
        ISR = {r["name"].strip(): r["values"] for r in SS.read_balance_sheet(IS_X, [PERIOD])}
    isv = lambda n: (ISR.get(n) or {}).get(PERIOD) or 0
    gl_ni = -sum(l["amount"] for l in by_period.get(PERIOD, []) if l["account_code"][:1] in "45678")
    if ISR:
        tie("Operating expenses", gsum("6"), isv("Total - 6000000 - Operating Expenses"), "GL 6xxxxxx", "Income Statement")
        tie("Total expense", gsum("6") + gsum("7"), isv("Total - Expense"), "GL 6xxxxxx and 7xxxxxx", "Income Statement")
        tie("Net income", gl_ni, isv("Total - Income") - isv("Total - Expense") + isv("Total - Other Income") - isv("Total - Other Expense"), "GL", "Income Statement")
    if bs["rows"]:
        tie("Net income", gl_ni, bsv("Net Income", PERIOD) - bsv("Net Income", PRIOR), "GL", "Balance Sheet, change in Net Income")
        tie("Balance sheet balances", bsv("Total ASSETS", PERIOD), bsv("Total Liabilities & Equity", PERIOD), "Total assets", "Total liabilities and equity")
        for what, name, pre, sg in (("Cash", "Total Bank", "10", 1), ("Prepaid expenses", "Total - 1300000 - Prepaid Expenses", "13", 1),
                                    ("Fixed assets", "Total - 1500000 - Fixed Assets", "15", 1), ("Accumulated depreciation", "Total - 1600000 - Accumulated Depreciation", "16", 1),
                                    ("Accounts payable", "Total - 2000000 - Accounts Payable", "200", -1), ("Accrued expenses", "Total - 2200000 - Accrued Expenses", "22", -1)):
            tie(what + ", change in " + MON, bsv(name, PERIOD) - bsv(name, PRIOR), sg * gsum(pre), "Balance Sheet", "GL activity")
    unbal = [x for x in ent if abs(round(sum((l.get("debit") or 0) - (l.get("credit") or 0) for l in x["lines"]), 2)) >= 0.01]
    ties.append('<tr><td>Proposed Journal Entries balance</td><td class="n2" colspan="2">%d of %d</td><td>%s</td></tr>' % (len(ent) - len(unbal), len(ent), "Pass" if not unbal else '<span class="unf">Fail</span>'))
    tie_note = "" if ISR else '<p class="note pad">Income Statement tie-outs did not run: they need the NetSuite Income Statement by month report.</p>'
    roles = [("prep", "Prepared by"), ("ctrl", "Controller Review"), ("cfo", "CFO Approval")]
    sign = "".join('<div class="sign"><b>%s</b><input class="f" data-sname="%s" placeholder="Name"><input class="f" data-sdate="%s" placeholder="Date"><button class="pill" data-signbtn="%s">Sign</button></div>'
                   % (lab, k, k, k) for k, lab in roles)
    pages.append(page("sox", hero("SOX &amp; GAAP Compliance, ".replace("&amp;", "&") + PERIOD + " Close", "", [
        ("GAAP Items", str(len(asc)), '<span data-ckdone></span>'), ("Sources", str(len(M["inputs"]) + len([x for x in V.get("inputs", []) if x.get("path") not in {y["path"] for y in M["inputs"]}])), "Read as exported"),
        ("Sign-offs", '<span data-signs></span>', ""), ("AI Disclosed", "Yes", "")])
        + '<div class="card"><div class="ch">Tie-Outs</div><div class="tw"><table class="ties"><thead><tr><th>Check</th><th class="n2">Amount</th><th class="n2">Against</th><th>Result</th></tr></thead><tbody>'
        + "".join(ties) + "</tbody></table></div>" + tie_note + "</div>"
        + '<div class="split"><div class="card"><div class="ch">GAAP Compliance Checklist</div>' + ck + '</div><div><div class="card"><div class="ch">Source Data Validation</div><div class="tw"><table>'
          '<thead><tr><th>Report</th><th>File</th><th class="n2">Status</th></tr></thead><tbody>' + src + '</tbody></table></div></div><div class="card"><div class="ch">Management Sign-Off</div><div class="pad">'
        + sign + '</div></div><div class="card"><div class="pad note"><b>AI disclosure.</b> Figures, variances and proposed entries are computed by the flux engine from the exports listed. '
          'Commentary and every decision are the reviewer\'s.</div></div></div></div>'))

    sections = [("Executive Overview", [("ov", "Executive Overview")]),
                ("Analysis", [("ava", "Actual vs. Actual (MoM)"), ("avb", "Actual vs. Budget"), ("dept", "By Department (MoM)"), ("pay", "Payroll Analytics")]),
                ("Close Workflow", ([("bs", "Balance Sheet Flux")] if bs["rows"] else []) + [("adj", "Adjustments"), ("sox", "SOX & GAAP")])]
    data = {"kind": "flux", "run": M["run_id"], "slug": SLUG, "thr": thr, "je": je, "icons": {}}
    js = r"""
function refresh(){
  marks(); paintItems(); counts(); signs(); checklist();
  const thr = S.thr || DATA.thr, over = vs => vs.filter(t => Math.abs(t.dataset.var) >= thr);
  const mom = over($$('#p-ava [data-pane="mom"] tr[data-var]'));
  $$('[data-cm]').forEach(x => x.textContent = mom.length);
  $$('[data-cmn]').forEach(x => x.textContent = 'Over ' + money(thr) + ' MoM');
  $$('[data-pane]').forEach(p => { const cc = p.querySelector('[data-ccount]'); if (cc) cc.textContent = over(Array.from(p.querySelectorAll('tr[data-var]'))).length; });
  const items = $$('#p-adj [data-item]'), done = items.filter(x => decided(x.dataset.item));
  const ap = done.filter(x => ['approve','modify','ack'].indexOf(S.dec[x.dataset.item].v) > -1).length, rj = done.length - ap;
  const pc = items.length ? Math.round(100 * done.length / items.length) : 0;
  $$('[data-prog]').forEach(x => x.textContent = pc + '%'); $$('[data-progn]').forEach(x => x.textContent = done.length + ' of ' + items.length + ' reviewed');
  $$('[data-progbar]').forEach(x => x.style.width = pc + '%'); $$('[data-progtxt]').forEach(x => x.textContent = ap + ' approved · ' + rj + ' rejected or no action · ' + (items.length - done.length) + ' pending');
  $$('[data-pending]').forEach(x => x.textContent = items.length - done.length);
  $$('[data-ckdone]').forEach(x => { const v = Object.values(S.ck); x.textContent = v.filter(y => y === 'ok').length + ' reviewed · ' + v.filter(y => y === 'flag').length + ' to follow up'; });
  $$('[data-signs]').forEach(x => x.textContent = Object.keys(S.sign).filter(k => k !== 'prep').length + ' / 2');
}
show('ov');
"""
    return shell("Serif P&L Flux - " + PERIOD, "P&L Flux", sections, pages, data, js)


# =====================================================================
# GL Coding Review
# =====================================================================
def coding():
    V = GLR["views"]
    G = {f["finding_id"]: f for f in GLR["findings"]}
    PF = {f["finding_id"]: f for f in PLR["findings"]}
    thr = 2500.0
    vend = next(t for t in V["tables"] if t["id"] == "vendors")
    vrows = [r for s in vend["sections"] for r in s["rows"]]
    billed = [r for r in vrows if round(r.get("amount") or 0)]
    spend = sum(r["amount"] for r in billed)
    pp = next(t for t in PLR["views"]["tables"] if t["id"] == "prepaid")
    je, items = {}, []   # items: (page, id, type, vendor, what, amount, current, recommended)

    def line_doc(vname, account=None):
        r = next((x for x in vrows if x["vendor"] == vname), None)
        if not r:
            return None
        its = [i for i in (r.get("detail") or {}).get("items") or [] if not account or i["account"] == account]
        return max(its, key=lambda i: abs(i["amount"])) if its else None

    def lines_html(vname, account=None, docs=None):
        r = next((x for x in vrows if x["vendor"] == vname), None)
        its = [i for i in ((r or {}).get("detail") or {}).get("items") or []
               if (not account or i["account"] == account) and (not docs or i["document"] in docs)]
        if not its:
            return ""
        rows = "".join('<tr><td class="mono">%s</td><td>%s %s%s</td><td>%s</td><td class="mono">%s</td><td>%s</td><td class="n2">%s</td></tr>'
                       % (e(i["date"]), e(i["type"]), e(i["document"]), doc_links(i["document"]), e(i["text"]), e(i["account"]), e(i.get("department") or ""), money(i["amount"], True))
                       for i in sorted(its, key=lambda i: -abs(i["amount"])))
        more = (((r or {}).get("detail") or {}).get("count") or len(its)) - len(its) if not account and not docs else 0
        return ('<details class="lines"><summary>Lines (%d)</summary><div class="tw"><table><thead><tr><th>Date</th><th>Document</th><th>Description</th><th>Account</th><th>Department</th>'
                '<th class="n2">Amount</th></tr></thead><tbody>%s</tbody></table></div>%s</details>' % (len(its), rows, ('<p class="note">%d more lines in NetSuite.</p>' % more) if more > 0 else ""))

    def acts(iid, label, actions):
        return "".join('<button class="pill" data-d="%s" data-v="%s" data-label="%s">%s</button>' % (iid, v, e(label), lab) for v, lab in actions)

    def card(iid, vendor, amount, hi, cur, rec, doc, extra, why, pol, actions, lines="", more="", flag=True):
        dl = doc_links(doc["document"]) if doc else ""
        return ('<div class="item%s" data-item="%s" data-amt="%s"%s><div class="ih"><b>%s</b><span class="stp">Pending</span><span class="mono">%s</span>%s</div><div class="ib"><div class="kv">'
                '<div><div class="l">Current coding</div><div class="x">%s</div></div><div><div class="l">Recommended</div><div class="x">%s</div></div>'
                '<div><div class="l">Document / item</div><div class="x">%s%s</div></div>%s</div>%s%s%s%s<div class="acts">%s<textarea class="c" rows="1" data-note="%s" placeholder="Note" hidden></textarea></div></div></div>'
                % (" hi" if hi else "", iid, round(amount or 0, 2), " data-flag" if flag else "", e(vendor), money(amount, True), '<span class="tag hi">Review</span>' if hi else "", cur, rec,
                   (e(doc["type"] + " " + doc["document"]) + "<small>" + e(doc["text"]) + "</small>") if doc else "&ndash;", dl, extra,
                   ('<div class="why">' + why + "</div>") if why else "", ('<div class="pol">' + e(pol) + "</div>") if pol else "", more, lines,
                   acts(iid, vendor, actions), iid))
    coding_ = lambda a, d=None: "%s<small>%s%s</small>" % (e(a), e(acct_name(a)), (" / " + e(d)) if d else "")
    FLAG_ACTS = (("approve", "Approve Recode"), ("reject", "Reject"), ("modify", "Modify"))

    # CapEx and Prepaid flags: expense that may belong on the balance sheet
    cap_cards, pre_cards = [], []
    for sec_id, prefix, bucket, typ in (("capital", "C", cap_cards, "CapEx missed"), ("prepaid", "P", pre_cards, "Prepaid missed")):
        rows = next((s["rows"] for s in pp["sections"] if s["id"] == sec_id), [])
        for n, r in enumerate(rows, 1):
            iid = prefix + str(n)
            f = PF.get(r["finding_id"]) or {}
            doc = line_doc(r["vendor"], r["from_account"])
            je[iid] = {"id": "SERIF-" + SLUG + "-" + iid, "date": doc["date"] if doc else "", "memo": "Recode %s %s from %s to %s" % (r["vendor"], r.get("what") or "", r["from_account"], r["to_account"]),
                       "lines": je_lines([{"account": r["to_account"], "department": r["department"], "debit": r["amount"]}, {"account": r["from_account"], "department": r["department"], "credit": r["amount"]}])}
            items.append(("capex" if prefix == "C" else "prepaid", iid, typ, r["vendor"], r.get("what") or "", r["amount"], r["from_account"], r["to_account"]))
            bucket.append(card(iid, r["vendor"], r["amount"], True, coding_(r["from_account"], r["department"]), '<span class="arrow">&rarr;</span> ' + coding_(r["to_account"], r["department"]),
                               doc, '<div><div class="l">Department</div><div class="x">' + e(r["department"]) + "</div></div>", e(f.get("recommendation") or ""), f.get("policy_basis"),
                               FLAG_ACTS, lines_html(r["vendor"], r["from_account"]), je_editor(iid, je[iid]["lines"]) + history(r["vendor"])))

    # The other direction: bills posted to prepaid or fixed-asset accounts this month
    def usual_expense(vendor, dept):
        tally = defaultdict(float)
        for m, ls in by_period.items():
            for l in ls:
                if (l.get("vendor_or_name") or "").strip() == vendor and PNL(l["account_code"]):
                    tally[(l["account_code"], l["department"] or dept)] += abs(l["amount"])
        return max(tally, key=tally.get) if tally else ("", dept)

    def booked(prefixes, tag):
        out = []
        ls = sorted([l for l in gl_now if l["account_code"][:2] in prefixes and l["txn_type"] != "Journal" and round(l["amount"])], key=lambda l: -abs(l["amount"]))
        for n, l in enumerate(ls, 1):
            iid = tag + str(n)
            v = (l.get("vendor_or_name") or "").strip() or "(no vendor)"
            ea, ed = usual_expense(v, l["department"] or "")
            amt = round(l["amount"], 2)
            je[iid] = {"id": "SERIF-" + SLUG + "-" + iid, "date": l["date"], "memo": "Recode %s %s from %s to expense" % (v, desc(l), l["account_code"]),
                       "lines": je_lines([{"account": ea, "department": ed, "debit": amt}, {"account": l["account_code"], "department": l["department"], "credit": amt}]), "when": "recode"}
            doc = {"type": l["txn_type"], "document": l["document_number"], "text": desc(l), "date": l["date"]}
            out.append(card(iid, v, amt, amt >= thr, coding_(l["account_code"], l["department"]), "&ndash;", doc,
                            '<div><div class="l">Department</div><div class="x">' + e(l["department"] or "&ndash;") + "</div></div>", "", "",
                            (("confirm", "Confirm, Stays on Balance Sheet"), ("recode", "Recode to Expense")), "",
                            je_editor(iid, je[iid]["lines"], "recode") + history(v), flag=False))
        return out
    cap_booked, pre_booked = booked(("15",), "CB"), booked(("13",), "PB")

    # Dept & Entity: department and account recodes, from the coding findings and their entries
    dcards = []
    ents = {x["finding_id"]: x for x in V.get("entries") or []}
    dfind = sorted([f for f in GLR["findings"] if f["rule_id"] in ("T1.DEPT_INCONSISTENCY", "T4.PO_ACCOUNT_MISMATCH")], key=lambda f: -(f.get("amount_at_risk") or 0))
    for n, f in enumerate(dfind, 1):
        iid = "D" + str(n)
        x = ents.get(f["finding_id"])
        vname = (f.get("transaction") or {}).get("vendor_or_name") or f["title"].split(":")[0].split(" coded to ")[0]
        if x:
            crl = [l for l in x["lines"] if l.get("credit")]
            drl = [l for l in x["lines"] if l.get("debit")]
            cur = "<br>".join(sorted({coding_(l["account"], l.get("department")) for l in crl}))
            rec = '<span class="arrow">&rarr;</span> ' + "<br>".join(sorted({coding_(l["account"], l.get("department")) for l in drl}))
            je[iid] = {"id": x["entry_id"], "date": x["date"], "memo": x["memo"], "lines": je_lines(x["lines"])}
            docs = sorted({d for l in x["lines"] for d in (l.get("documents") or [])})
            doc = line_doc(vname)
            if docs:
                doc = next((i for r in vrows if r["vendor"] == vname for i in (r.get("detail") or {}).get("items") or [] if i["document"] in docs), doc)
        else:
            ev = f.get("evidence") or {}
            cur, rec, doc = e(ev.get("observed") or ""), '<span class="arrow">&rarr;</span> ' + e(ev.get("expected") or ""), line_doc(vname)
        typ = "Department" if f["rule_id"].startswith("T1") else "Account vs. Coupa"
        items.append(("dept", iid, typ, vname, (doc or {}).get("text") or "", f.get("amount_at_risk") or 0, "", ""))
        dcards.append(card(iid, vname, f.get("amount_at_risk") or 0, (f.get("amount_at_risk") or 0) >= thr, cur, rec, doc,
                           '<div><div class="l">Type</div><div class="x">' + e(typ) + "</div></div>", e(f.get("recommendation") or ""), "", FLAG_ACTS,
                           lines_html(vname, docs=set(d for l in (x or {}).get("lines", []) for d in (l.get("documents") or [])) or None),
                           (je_editor(iid, je[iid]["lines"]) if iid in je else "") + history(vname)))

    # Reviewed & Cleared and New This Period: by department, then account
    def coding_of(r):
        c = max(r.get("by_coding") or [{"account": "", "department": "", "current": 0}], key=lambda x: abs(x.get("current") or 0))
        return c.get("department") or "Non-Specific", c["account"], c.get("current") or r["amount"]

    def vcard(iid, r, tag, why, actions):
        dept, a, camt = coding_of(r)
        doc = line_doc(r["vendor"])
        cur = "<br>".join(coding_(c["account"], c.get("department")) for c in (r.get("by_coding") or []) if round(c.get("current") or 0)) or coding_(a)
        je[iid] = {"id": "SERIF-" + SLUG + "-" + iid, "date": (doc or {}).get("date") or "", "memo": "Recode %s from %s %s" % (r["vendor"], a, dept),
                   "lines": je_lines([{"account": a, "department": dept, "debit": camt}, {"account": a, "department": dept, "credit": camt}]), "when": "recode"}
        return ('<div class="item" data-item="%s" data-amt="%s"><div class="ih"><b>%s</b><span class="stp">Pending</span><span class="mono">%s</span><span class="tag%s">%s</span></div>'
                '<div class="ib"><div class="kv"><div><div class="l">Current coding</div><div class="x">%s</div></div><div><div class="l">Document / item</div><div class="x">%s%s</div></div>'
                '<div><div class="l">%s</div><div class="x">%s</div></div></div>%s%s%s%s<div class="acts">%s<textarea class="c" rows="1" data-note="%s" placeholder="Note" hidden></textarea></div></div></div>'
                % (iid, round(r["amount"] or 0, 2), e(r["vendor"]), money(r["amount"], True), " hi" if tag == "Review" else "", tag, cur,
                   (e(doc["type"] + " " + doc["document"]) + "<small>" + e(doc["text"]) + "</small>") if doc else "&ndash;", doc_links(doc["document"]) if doc else "",
                   "Lines this month", str(((r.get("detail") or {}).get("count") or 0)), ('<div class="why">' + why + "</div>") if why else "",
                   history(r["vendor"]), je_editor(iid, je[iid]["lines"], "recode"), lines_html(r["vendor"]), acts(iid, r["vendor"], actions), iid))

    def by_dept(rs, make):
        tree = defaultdict(lambda: defaultdict(list))
        for r in rs:
            d, a, _ = coding_of(r)
            tree[d][a].append(r)
        out = []
        for d, accts in sorted(tree.items(), key=lambda kv: -sum(r["amount"] for v in kv[1].values() for r in v)):
            n = sum(len(v) for v in accts.values())
            out.append('<h4 class="dh">%s<span class="note">%s &middot; %s</span></h4>' % (e(d), count(n, "vendor"), money(sum(r["amount"] for v in accts.values() for r in v), True)))
            for a, vs in sorted(accts.items(), key=lambda kv: -sum(r["amount"] for r in kv[1])):
                out.append('<div class="grphead"><span class="tag hi">%s %s</span>%s &middot; %s</div>' % (e(a), e(acct_name(a)), count(len(vs), "vendor"), money(sum(r["amount"] for r in vs), True)))
                out.extend(make(r) for r in sorted(vs, key=lambda r: -r["amount"]))
        return out

    clear = [r for r in vrows if not r.get("flags") and round(r.get("amount") or 0)]
    k = [0]

    def clear_card(r):
        k[0] += 1
        return vcard("R%d" % k[0], r, "Review" if r["amount"] >= thr else "Routine", "", (("confirm", "Confirm, No Recode"), ("recode", "Recode This Line")))
    ccards = by_dept(clear, clear_card)
    news = sorted([r for r in vrows if any(f.get("id") == "new" for f in r.get("flags") or []) and round(r.get("amount") or 0)], key=lambda r: -r["amount"])
    kn = [0]

    def new_card(r):
        kn[0] += 1
        fl = next(f for f in r["flags"] if f.get("id") == "new")
        return vcard("N%d" % kn[0], r, "Review" if r["amount"] >= thr else "Routine",
                     "<b>Assessment:</b> " + e(fl.get("why") or "") + ((" <b>Action:</b> " + e(fl.get("do"))) if fl.get("do") else ""),
                     (("confirm", "Confirm Vendor &amp; Coding"), ("recode", "Recode This Line")))
    ncards = by_dept(news, new_card)

    flagged = [i for i in items]
    famt = sum(i[5] for i in flagged)
    by_type = [("CapEx missed", [i for i in items if i[0] == "capex"]), ("Prepaid missed", [i for i in items if i[0] == "prepaid"]), ("Dept / account mismatch", [i for i in items if i[0] == "dept"])]
    mx = max(sum(i[5] for i in x) for _, x in by_type) or 1
    breakdown = "".join('<div class="row" style="display:grid;grid-template-columns:14rem 1fr 12rem;gap:1em;align-items:center;margin:.35em 0"><span>%s</span><div class="bar" style="margin:0"><i style="width:%.1f%%"></i></div>'
                        '<span class="n2" style="text-align:right">%d flags &middot; %s</span></div>' % (lab, 100 * sum(i[5] for i in x) / mx, len(x), money(sum(i[5] for i in x)))
                        for lab, x in by_type)
    summ = "".join('<tr><td><span class="tag ink">%s</span></td><td>%s</td><td>%s</td><td>%s</td><td class="n2">%s</td><td class="mono">%s</td><td class="mono">%s</td><td><span data-sti="%s">Pending</span></td></tr>'
                   % (i[1], e(i[2]), e(i[3]), e(i[4]), money(i[5], True), e(i[6]), e(i[7]), i[1]) for i in items)
    clean_lines = sum(((r.get("detail") or {}).get("count") or 0) for r in clear)
    hero_ = hero("GL Coding Review, " + PERIOD, "Serif Biomedicines, Inc. &middot; NetSuite Subsidiary 97", [
        ("Total Period Spend", money(spend), "%d vendors billed" % len(billed)),
        ("Flags Identified", str(len(flagged)), "%s &middot; %.1f%% of period spend" % (money(famt), 100 * famt / spend)),
        ("Clean Vendors", str(len(clear)), money(sum(r["amount"] for r in clear)) + " &middot; no flags"),
        ("Resolved", '<span data-resolved></span>', "Flags decided")])
    pages = []
    pages.append(page("ov", hero_ + CHECKLIST))
    def two_way(word, flags, booked_, kind, accts):
        none = lambda what: '<p class="note">%s</p>' % what
        return ('<h4 class="dh">Expensed, May Be %s<span class="note">%s &middot; %s</span></h4>' % (word, count(len(flags), "item"), money(sum(i[5] for i in items if i[0] == kind), True))
                + ("".join(flags) or none("No expense lines flagged in " + PERIOD + "."))
                + '<h4 class="dh">Booked to %s<span class="note">%s &middot; %s</span></h4>' % (accts, count(len(booked_), "line"), money(sum(float(x.split('data-amt="')[1].split('"')[0]) for x in booked_), True))
                + ("".join(booked_) or none("No bills posted to " + accts.lower() + " accounts in " + PERIOD + ".")))
    pages.append(page("capex", "<h3>CapEx Flags</h3>" + two_way("Capital", cap_cards, cap_booked, "capex", "Fixed Assets")))
    pages.append(page("prepaid", "<h3>Prepaid Flags</h3>" + two_way("Prepaid", pre_cards, pre_booked, "prepaid", "Prepaid")))
    pages.append(page("dept", '<h3>Dept &amp; Entity Flags <span class="note">%d items &middot; %s total</span></h3>' % (len(dcards), money(sum(i[5] for i in items if i[0] == "dept"), True)) + "".join(dcards)))
    pages.append(page("clear", '<h3>Reviewed &amp; Cleared <span class="note">%d vendors &middot; %s</span></h3><div class="legend"><span class="tag">Routine</span>Correctly coded, confirm and close'
                      '<span class="tag hi">Review</span>$2,500 or more, confirm the coding</div>' % (len(clear), money(sum(r["amount"] for r in clear), True)) + "".join(ccards)))
    pages.append(page("new", '<h3>New This Period <span class="note">%d vendors &middot; first appearance in the ledger</span></h3><div class="legend">'
                      '<span class="tag hi">Review</span>$2,500 or more<span class="tag">Routine</span>Under $2,500</div>' % len(news) + "".join(ncards)))
    pages.append(page("audit", '<h3>Audit Log</h3><div class="card"><div class="tw"><table><thead><tr><th>Timestamp</th><th>Item</th><th>Decision</th><th>Detail</th></tr></thead>'
                      '<tbody data-audit></tbody></table></div></div>'))
    srcs = "".join('<tr><td>%s</td><td class="mono" style="text-align:right">%s</td></tr>' % (e(a), e(b)) for a, b in
                   [(", ".join(i.get("roles") or ["input"]).replace("_", " ").title(), i["path"]) for i in GLR["manifest"]["inputs"]]
                   + [("Policy", p) for p in sorted({f.get("policy_basis") for f in list(GLR["findings"]) + [PF[x] for x in PF if PF[x]["rule_id"] in ("F9.PREPAID", "F10.CAPITALIZE")] if f.get("policy_basis")})]
                   + [("Review period", PERIOD), ("NetSuite subsidiary", "Serif Biomedicines, Inc. (FL87, subsidiary 97)")])
    tie = GLR["manifest"].get("tie_out") or {}
    tie_rows = "".join('<tr><td>%s</td><td class="mono" style="text-align:right">%s</td></tr>' % (a, b) for a, b in [
        (e(MON + " GL expense total (6xxxxxx)"), money(gl_6x, True)), ("Total flagged amount", money(famt, True)), ("Flagged as % of GL total", "%.2f%%" % (100 * famt / gl_6x)),
        ("Ledger balances", ("Pass: " if tie.get("passed") else "Fail: ") + e(tie.get("note") or "")), ("Flags as subset of GL", "Pass: every flag is drawn from posted GL lines")])
    pol_rows = "".join('<tr><td>%s</td><td class="mono" style="text-align:right">%s</td></tr>' % (a, b) for a, b in [
        ("Vendors billed this month", str(len(billed))), ("P&amp;L lines this month", format(pl_lines_now, ",")), ("CapEx flags", str(len(cap_cards))), ("Prepaid flags", str(len(pre_cards))),
        ("Department and account flags", str(len(dcards))), ("Vendors with no flags", str(len(clear))), ("New vendors", str(len(news)))])
    sign = "".join('<div class="sign"><b>%s</b><input class="f" data-sname="%s" placeholder="Name, title"><input class="f" data-sdate="%s" placeholder="Date"><button class="pill" data-signbtn="%s">Sign</button></div>'
                   % (lab, k, k, k) for k, lab in (("prep", "Prepared by"), ("rev", "Reviewed by"), ("appr", "Approved by")))
    pages.append(page("sox", '<h3>SOX Documentation</h3><div class="card"><div class="ch">Source Citations</div><div class="tw"><table><tbody>' + srcs + "</tbody></table></div></div>"
                      + '<div class="card"><div class="ch">GL Tie-Out</div><div class="tw"><table><tbody>' + tie_rows + "</tbody></table></div></div>"
                      + '<div class="card"><div class="ch">Policy Application Summary</div><div class="tw"><table><tbody>' + pol_rows + "</tbody></table></div></div>"
                      + '<div class="card"><div class="ch">Management Review &amp; Sign-Off</div><div class="pad">' + sign + "</div></div>"))
    pages.append(page("export", '<div class="card"><div class="ch">Export to NetSuite<button class="pill solid r" data-export>Export to NetSuite, CSV</button></div>'
                      '<div class="tw"><table><thead><tr><th>Memo</th><th>Account</th><th>Department</th><th class="n2">Debit</th><th class="n2">Credit</th><th>Status</th></tr></thead><tbody data-exportrows></tbody></table></div></div>'))
    sections = [("Overview", [("ov", "Overview")]),
                ("Review", [("capex", "CapEx Flags"), ("prepaid", "Prepaid Flags"), ("dept", "Dept & Entity")]),
                ("Transparency", [("clear", "Reviewed & Cleared"), ("new", "New This Period")]),
                ("Documentation", [("audit", "Audit Log"), ("sox", "SOX Documentation"), ("export", "Export")])]
    data = {"kind": "coding", "run": GLR["manifest"]["run_id"], "slug": SLUG, "thr": thr, "je": je, "icons": {}}
    js = r"""
function refresh(){
  marks(); paintItems(); counts(); signs(); checklist();
  const flags = $$('[data-flag]'), ids = flags.map(x => x.dataset.item);
  const done = ids.filter(decided), v = k => ids.filter(i => S.dec[i] && S.dec[i].v === k).length;
  $$('[data-resolved]').forEach(x => x.textContent = done.length + ' / ' + ids.length);
  const pc = ids.length ? Math.round(100 * done.length / ids.length) : 0;
  $$('[data-progpct]').forEach(x => x.textContent = pc + '%'); $$('[data-progbar]').forEach(x => x.style.width = pc + '%');
  $$('[data-chips]').forEach(x => x.innerHTML = '<span>Pending: ' + (ids.length - done.length) + '</span><span>Approved: ' + v('approve') + '</span><span>Rejected: ' + v('reject') + '</span><span>Modified: ' + v('modify') + '</span>');
  $$('[data-sti]').forEach(x => { const d = S.dec[x.dataset.sti]; x.textContent = d ? LABEL[d.v] : 'Pending'; });
  const a = $('[data-audit]'); if (a) a.innerHTML = S.log.length ? S.log.map(l => '<tr><td class="mono">' + esc(l.at.slice(0, 16).replace('T', ' ')) + '</td><td>' + esc(l.label) +
    '</td><td>' + esc(LABEL[l.v] || 'Cleared') + '</td><td>' + esc(l.note || '') + '</td></tr>').join('') : '<tr><td colspan="4" class="note">No decisions recorded yet.</td></tr>';
  const ex = $('[data-exportrows]'); if (ex){ const r = [];
    Object.keys(DATA.je).forEach(id => { if (!jeLive(id)) return; const j = jeOf(id), ok = jeReady(id);
      j.lines.forEach((l, i) => r.push('<tr><td>' + (i ? '' : esc(j.memo)) + '</td><td class="mono">' + esc(l.account) + '</td><td>' + esc(l.department || '') + '</td><td class="n2">' + (Number(l.debit) ? money(l.debit) : '') +
        '</td><td class="n2">' + (Number(l.credit) ? money(l.credit) : '') + '</td><td>' + (i ? '' : ok ? 'Ready' : '<span class="unf">' + (jeBal(j) ? 'Out of balance' : jeNoop(j) ? 'No change' : !decided(id) ? 'Add a note' : 'Missing account') + '</span>') + '</td></tr>')); });
    ex.innerHTML = r.length ? r.join('') : '<tr><td colspan="6" class="note">No approved entries yet.</td></tr>'; }
}
show('ov');
"""
    return shell("Serif GL Coding Review - " + PERIOD, "GL Coding Review", sections, pages, data, js)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("serif-pl-flux-" + SLUG + "-updated-ui-" + VERSION + ".html", flux), ("serif-gl-coding-review-" + SLUG + "-updated-ui-" + VERSION + ".html", coding)):
        p = os.path.join(OUT, name)
        open(p, "w", encoding="utf-8").write(fn())
        print("Wrote", p, os.path.getsize(p) // 1024, "KB")
