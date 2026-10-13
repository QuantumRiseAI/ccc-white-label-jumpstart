"""Build the GL Coding Review and P&L Flux consoles, version 2.0.0.

Chris's August page set, in Serif's design, from the runs. In a Claude Project,
from the folder holding the runs and the exports:

    python3 build_pages.py --only flux --flux-run out/sep2026/run.json \
        --gl netsuite_gl_*.xls --income-statement netsuite_income_statement_by_month_*.xls \
        --out out/sep2026

    python3 build_pages.py --only coding --coding-run out/sep2026/run.json \
        --gl netsuite_gl_*.xls --out out/sep2026

Each console reads its own run. In the repo, `make build PERIOD=aug2026` runs the
same commands from the packaged Project folders.

Each console is one self-contained HTML page. Decisions, commentary, entry edits,
sign-off and the audit log are kept in the browser, or, published as a claude.ai
Artifact with the db and user capabilities, in a review shared by everyone with
access. Every figure is computed here from the runs and the NetSuite exports.
"""
import argparse
from datetime import datetime
import calendar
import hashlib
import html
import json
import os
import re
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import serif_sources as SS  # noqa: E402
import serif_design as DS   # noqa: E402

VERSION = "2.0.0"
ap = argparse.ArgumentParser(description="Build the GL Coding Review and P&L Flux consoles.")
ap.add_argument("--only", choices=("coding", "flux"), help="build one console; both by default")
ap.add_argument("--coding-run", help="the GL Coding Review run.json, after serif_views.py --keep-names")
ap.add_argument("--flux-run", help="the P&L Flux run.json, after serif_views.py --keep-names --balance-sheet")
ap.add_argument("--gl", nargs="+", help="the NetSuite Custom General Ledger export(s), as NetSuite writes them")
ap.add_argument("--income-statement", help="the NetSuite Income Statement by month report, for the flux tie-outs")
ap.add_argument("--coding-record", help="the GL Coding Review decision record (JSON, format 3), with --coding-run: booked corrections adjust the P&L flux (--only flux)")
ap.add_argument("--coding-drafts", help="the GL Coding Review's drafts.json, with --coding-record: Journal Entries Claude drafted there, so a decision on one can be applied")
ap.add_argument("--drafts", help="Claude's drafts.json for the console being built (with --only)")
ap.add_argument("--out", help="output folder")
A = ap.parse_args()
WANT = [A.only] if A.only else ["flux", "coding"]
EMPTY = {"views": {}, "findings": [], "manifest": {}}
if "flux" in WANT and not A.flux_run:
    sys.exit("Pass the P&L Flux run with --flux-run, or build --only coding.")
if "coding" in WANT and not A.coding_run:
    sys.exit("Pass the GL Coding Review run with --coding-run, or build --only flux.")
if not A.gl:
    sys.exit("Pass the NetSuite GL export with --gl.")
PLR = json.load(open(A.flux_run)) if A.flux_run else EMPTY
GLR = json.load(open(A.coding_run)) if A.coding_run else EMPTY
GL_X, IS_X = A.gl, A.income_statement
CODING_REC = None
if A.coding_record:
    if A.only != "flux" or not A.flux_run or not A.coding_run:
        sys.exit("Pass --coding-record with --only flux, the flux run (--flux-run) and the coding run (--coding-run).")
    try:
        CODING_REC = json.load(open(A.coding_record, encoding="utf-8"))
    except (OSError, ValueError) as ex:
        sys.exit("--coding-record cannot be read as JSON: %s" % ex)
    if not isinstance(CODING_REC, dict) or CODING_REC.get("kind") != "serif-decision-record" or CODING_REC.get("console_kind") != "coding" or CODING_REC.get("format") != 3:
        sys.exit("--coding-record is not a GL Coding Review decision record (format 3).")
    if not all(isinstance(CODING_REC.get(k) or {}, dict) for k in ("dec", "notes", "je", "jh")):
        sys.exit("--coding-record is malformed: dec, notes, je and jh must each be an object.")
    if CODING_REC.get("period") != PLR["manifest"]["period"] or GLR["manifest"]["period"] != PLR["manifest"]["period"]:
        sys.exit("The coding run and decision record must be for the flux's period, " + PLR["manifest"]["period"] + ".")
M = (PLR if A.flux_run else GLR)["manifest"]
SLUG = M["period"].replace(" ", "").lower()
if A.drafts and not A.only:
    sys.exit("Pass --only with --drafts: drafts belong to one console.")
RAW_DRAFTS = json.load(open(A.drafts, encoding="utf-8")) if A.drafts else {}
CODING_DRAFTS = json.load(open(A.coding_drafts, encoding="utf-8")) if A.coding_drafts else {}
if A.coding_drafts and not A.coding_record:
    sys.exit("Pass --coding-drafts with --coding-record.")
o = A.out or os.path.dirname(os.path.abspath(A.flux_run or A.coding_run))
OUTS = {"flux": o, "coding": o}

PERIOD, PRIOR, PY = M["period"], M["prior_period"], M["prior_year_period"]
MON = PERIOD[:3]
YEAR_END = "Dec " + str(int(PERIOD[-4:]) - 1)
e = lambda s: html.escape("" if s is None else str(s))
ACC = {}
for r in (PLR, GLR):
    for k, v in (r["views"].get("accounts") or {}).items():
        ACC[k] = v.get("name") if isinstance(v, dict) else v
acct_name = lambda c: ACC.get(c) or ""
JE_SUBSIDIARY, JE_CURRENCY, JE_RATE = "Serif Biomedicines, Inc.", "USD", 1   # NetSuite subsidiary 97
PERIOD_END = "%s-%02d-%02d" % (PERIOD[-4:], list(calendar.month_abbr).index(PERIOD[:3]), calendar.monthrange(int(PERIOD[-4:]), list(calendar.month_abbr).index(PERIOD[:3]))[1])
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
for _ls in by_period.values():
    for _l in _ls:
        if not ACC.get(_l["account_code"]) and _l.get("account_leaf"):
            ACC[_l["account_code"]] = _l["account_leaf"]
for _r in ((PLR.get("views") or {}).get("balance_sheet") or {}).get("rows") or []:
    _m = re.match(r"(?:Total - )?(\d{7}) - (.+)", _r.get("name") or "")
    if _m and not ACC.get(_m.group(1)):
        ACC[_m.group(1)] = _m.group(2).strip()


def named(text):
    """Escaped text with each account number followed by its name, where it is not already."""
    def put(m):
        code, name = m.group(1), acct_name(m.group(1))
        if not name:
            return code
        after = m.string[m.end():m.end() + len(name) + 8].lstrip(" -&ndash;").lower()
        return code if after.startswith(e(name).lower()[:12]) else code + " " + e(name)
    return re.sub(r"(?<![\d#])\b([1-8]\d{6})\b(?!\d)", put, text)


en = lambda s: named(e(s))

# A flux row's name: the engine's leaf, or the chart's name where the leaf is only the number.
leaf_of = lambda r: (r.get("account_leaf") if r.get("account_leaf") not in (None, "", r.get("account_code")) else acct_name(r["account_code"])) or ""
acct_month = defaultdict(lambda: defaultdict(float))    # P&L account -> period -> net
for _p, _ls in by_period.items():
    for _l in _ls:
        if PNL(_l["account_code"]):
            acct_month[_l["account_code"]][_p] += _l["amount"]


def trailing(acct, n):
    """The account's average over the n months before the period, from the GL."""
    ms = [SS.shift(PERIOD, -k) for k in range(1, n + 1)]
    have = [m for m in ms if m in by_period]
    return sum(acct_month[acct].get(m, 0.0) for m in have) / len(have) if len(have) == n else None
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


def je_editor(iid, lines, when=None, label=None):
    """A proposed Journal Entry, filled in and editable. The page fills the values."""
    rows = "".join('<tr><td><input class="f mono" data-jef="%s|%d|account" list="accts" size="9" aria-label="Account, line %d"><small data-jean="%s|%d"></small></td>'
                   '<td><input class="f" data-jef="%s|%d|department" list="depts" aria-label="Department, line %d"></td>'
                   '<td class="n2"><input class="f num" data-jef="%s|%d|debit" inputmode="decimal" aria-label="Debit, line %d"></td>'
                   '<td class="n2"><input class="f num" data-jef="%s|%d|credit" inputmode="decimal" aria-label="Credit, line %d"></td>'
                   '<td><input class="f wide" data-jef="%s|%d|memo" aria-label="Line Memo, line %d"></td></tr>'
                   % (iid, i, i + 1, iid, i, iid, i, i + 1, iid, i, i + 1, iid, i, i + 1, iid, i, i + 1) for i in range(len(lines)))
    head = ('<div class="jf"><label>Subsidiary<span>%s</span></label><label>Currency<span>%s</span></label><label>Exchange Rate<span>%s</span></label>'
            '<label>Journal Date<input class="f" type="date" data-jeh="%s|date"></label><label>Posting Period<input class="f" data-jeh="%s|period"></label>'
            '<label>Reversing Entry<select class="f" data-jeh="%s|reversing"><option>N</option><option>Y</option></select></label>'
            '<label>Reversal Date<input class="f" type="date" data-jeh="%s|reversal_date"></label>'
            '<label class="memo">Memo<input class="f" data-jeh="%s|memo"></label></div>' % (e(JE_SUBSIDIARY), JE_CURRENCY, JE_RATE, iid, iid, iid, iid, iid))
    return ('<div class="jee" data-je="%s"%s%s><div class="jh"><span class="l">Journal Entry</span><span data-jebal></span>'
            '<button class="lk" data-jereset="%s" hidden>Reset</button></div>%s<div class="tw"><table><thead><tr><th>Account</th><th>Department</th>'
            '<th class="n2">Debit</th><th class="n2">Credit</th><th>Line Memo</th></tr></thead><tbody>%s</tbody></table></div></div>'
            % (iid, (' data-when="%s" hidden' % when) if when else "", (' data-label="%s"' % e(label)) if label else "", iid, head, rows))


_SEEN = set()


def sid(prefix, *parts):
    """An item's id, from what the item is, so the same item has the same id in
    every run of the close: a saved record, the shared review and an earlier run's
    decisions match on it."""
    h = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:8]
    k, n = prefix + "-" + h, 2
    while k in _SEEN:
        k, n = prefix + "-" + h + "-" + str(n), n + 1
    _SEEN.add(k)
    return k


DRAFTS, SKIPPED = {}, []   # key -> {note, target, item, v}; what was left out


def txt(v):
    return str(v).strip() if v is not None else ""


def draft(key, note, target, item=None, v=None, label=""):
    """Claude's draft beside the item it belongs to. It counts for nothing until
    the reviewer uses it, which copies it into the note (and the decision)."""
    DRAFTS[key] = {"note": note, "target": target, "item": item, "v": v}
    return ('<div class="draft" data-draft="%s"><span class="tag">Drafted by Claude</span>%s<span class="dt">%s</span>'
            '<button class="lk" data-use="%s">Use this</button></div>' % (e(key), (" <b>" + e(label) + "</b>") if label else "", e(note), e(key)))


def drafted_entries(fids_ok=None):
    """Drafted Journal Entries: each must balance and every line name an account."""
    out = []
    for i, x in enumerate(RAW_DRAFTS.get("entries") or [], 1):
        lines = [{"account": txt(l.get("account")), "department": txt(l.get("department")), "vendor": txt(l.get("vendor")),
                  "debit": round(float(l.get("debit") or 0), 2), "credit": round(float(l.get("credit") or 0), 2),
                  "documents": [txt(d) for d in (l.get("documents") or [])]} for l in x.get("lines") or []]
        dr, cr = round(sum(l["debit"] for l in lines), 2), round(sum(l["credit"] for l in lines), 2)
        if not lines or abs(dr - cr) >= 0.005 or not all(l["account"] for l in lines):
            SKIPPED.append("Journal Entry %d (%s): does not balance or has a line with no account" % (i, txt(x.get("memo"))[:60]))
            continue
        out.append({"entry_id": "SERIF-DRAFT-%d" % i, "finding_id": "draft-%d" % i, "kind": "Drafted by Claude", "date": txt(x.get("date")),
                    "memo": txt(x.get("memo")), "reverses": txt(x.get("reverses")), "support": txt(x.get("reason")), "lines": lines, "debits": dr, "credits": cr})
    return out


def count(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def je_lines(lines):
    return [{"account": l["account"], "department": l.get("department") or "", "debit": round(l.get("debit") or 0, 2), "credit": round(l.get("credit") or 0, 2)} for l in lines]


def je_finish(je):
    """The NetSuite Journal Entry fields the run can fill: the header (subsidiary,
    posting period, currency, exchange rate, reversal) and a Line Memo on each line."""
    for j in je.values():
        if "period" in j:   # already finished (the coding build hands the same entries to the flux)
            continue
        rev = j.pop("reverses", "") or ""
        was, j["date"] = j["date"], PERIOD_END   # corrections are booked in the open close month
        j.update({"subsidiary": JE_SUBSIDIARY, "period": PERIOD, "currency": JE_CURRENCY, "rate": JE_RATE,
                  "reversing": "Y" if rev else "N", "reversal_date": rev})
        for l in j["lines"]:
            l["memo"] = j["memo"] + ((" | Original date " + was) if was and was != PERIOD_END else "")
    return je


# The GL Coding Review's reference IDs: one prefix per screen, by the prefix of the item id.
REF_SCREENS = {"C": "CAPEX", "CB": "FA", "P": "PREPAID", "PB": "PPD", "D": "DEPT", "DR": "DRAFT", "R": "CLEAR", "N": "NEW"}
MEMO_MAX = 999   # NetSuite's limit on a Journal Entry Memo, body and line


def ref_memo(ref, memo):
    """An entry's Memo per the Data Entry Policy, `Specific description | Mon'YY`, with the
    reference ID in front. The description is cut so the Line Memo, which adds the original
    date, stays within NetSuite's limit."""
    m = " ".join(str(memo or "").split())
    end = re.search(r" \| [A-Z][a-z]{2}'\d{2}$", m)
    head, desc_, tail = (ref + " | ") if ref else "", m[:end.start()] if end else m, end.group(0) if end else " | %s'%s" % (MON, PERIOD[-2:])
    room = MEMO_MAX - len(" | Original date 2026-08-31") - len(head) - len(tail)
    return head + (desc_ if len(desc_) <= room else desc_[:room - 3].rstrip() + "...") + tail

# ---------- the design ----------
CSS = DS.FONT_CSS + DS.TOKENS + r"""
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
.top nav{display:flex;align-items:center;gap:var(--spacing-xs);flex:1;min-width:0;overflow-x:auto;scrollbar-width:none}
.top nav::-webkit-scrollbar{display:none}
.tg{display:flex;align-items:center;flex:none;border-radius:var(--radius-pill);transition:background-color .25s}
.tg.open{background-color:rgba(255,255,255,.12);box-shadow:inset 0 0 0 1px rgba(255,255,255,.28);padding-right:.2em}
.tb.sec::after{content:"";width:.38em;height:.38em;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;
  transform:rotate(-45deg);margin-left:.1em;opacity:.8;transition:transform .2s}
.tg.open > .tb.sec::after{transform:rotate(45deg);margin-bottom:.2em}
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
.tabs{display:flex;align-items:flex-end;gap:4px;padding:.7em var(--spacing-sm) 0;overflow-x:auto;scrollbar-width:none;
  background:linear-gradient(to top,var(--color-warm-gray) 1px,var(--color-bg-primary) 1px)}
.tabs::-webkit-scrollbar{display:none}
/* Folder tabs: each tab is its own shape, the current one opens into the panel below. */
.tabs button{flex:none;height:2.5em;padding:0 1.05em;cursor:pointer;white-space:nowrap;font-size:var(--text--1);color:var(--color-fg-secondary);
  background-color:rgba(255,255,255,.5);border:1px solid var(--color-hairline);border-bottom:0;border-radius:var(--radius-sm) var(--radius-sm) 0 0;
  transition:background-color .15s,color .15s}
.tabs button:hover{background-color:var(--color-stark);color:var(--color-fg-primary)}
.tabs button:focus{outline:none}
.tabs button:focus-visible{outline:2px solid var(--color-vivid);outline-offset:-2px}
.tabs button.on{background-color:var(--color-stark);color:var(--color-fg-primary);font-weight:600;border-color:var(--color-warm-gray);
  box-shadow:0 1px 0 0 var(--color-stark)}
.sumline{padding:.7em var(--spacing-sm-md);font-size:var(--text--1);color:var(--color-fg-secondary);border-bottom:1px solid var(--color-hairline);display:flex;gap:var(--spacing-sm);flex-wrap:wrap}
.sumline b{color:var(--color-fg-primary);font-variant-numeric:tabular-nums}
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:var(--text--1)}
th{font-size:var(--text--2);text-transform:uppercase;letter-spacing:.04em;color:var(--color-fg-secondary);font-weight:600;text-align:left;
  padding:.7em .8em;border-bottom:1px solid var(--color-hairline);background-color:var(--color-stark);vertical-align:bottom}
td{padding:.65em .8em;border-bottom:1px solid var(--color-hairline);vertical-align:top}
td.n2,th.n2{text-align:right;font-variant-numeric:tabular-nums}
td.n2{white-space:nowrap}
td.n2 small{display:block;color:var(--color-fg-secondary);font-size:var(--text--2)}
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
.item.folded > .ib{display:none}
.item.folded > .ih{border-bottom:0}
.item.foldable > .ih{cursor:pointer}
.item.foldable > .ih::after{content:"";width:.5em;height:.5em;border-right:1.5px solid var(--color-fg-secondary);border-bottom:1.5px solid var(--color-fg-secondary);
  transform:rotate(45deg);margin:0 .2em .2em .4em;transition:transform .2s}
.item.foldable:not(.folded) > .ih::after{transform:rotate(-135deg);margin-bottom:-.2em}
.item .ih{display:flex;align-items:center;gap:var(--spacing-xs);padding:.8em var(--spacing-sm);border-bottom:1px solid var(--color-hairline);flex-wrap:wrap}
.item .ih b{font-weight:600}
.item .ih .ref{font-weight:600;color:var(--color-fg-secondary);letter-spacing:.02em}
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
.jee .jf{display:flex;flex-wrap:wrap;gap:var(--spacing-xs) var(--spacing-sm);padding:.5em .8em;font-size:var(--text--2);border-bottom:1px solid var(--color-hairline)}
.jee .jf label{display:flex;flex-direction:column;gap:.15em;color:var(--color-fg-secondary)}
.jee .jf label span{color:var(--color-fg-primary);padding:.25em 0}
.jee .jf input.f,.jee .jf select.f{width:auto;max-width:14ch}
.jee .jf label.memo{flex:1 1 100%}
.jee .jf label.memo input.f{width:100%;max-width:none}
.jee input.wide{max-width:none}
tr.jr > td{padding:.4em .8em}
.jee input.num{text-align:right;font-variant-numeric:tabular-nums;max-width:12ch}
.jee .jh [data-jebal]{text-transform:none;letter-spacing:0}
.jee.edited{border-color:var(--color-dark-gray)}
.draft{display:flex;gap:var(--spacing-2xs);align-items:baseline;flex-wrap:wrap;background-color:var(--color-bg-primary);border-radius:var(--radius-xs);
  padding:.5em .7em;margin:0 0 .6em;font-size:var(--text--1);line-height:1.45}
.draft .dt{flex:1 1 16rem}
.esum{padding:var(--spacing-sm) var(--spacing-sm-md);display:grid;gap:var(--spacing-xs)}
.esum .dt{white-space:pre-line;line-height:1.5}
.esum textarea.c{font-size:var(--text-0);line-height:1.5}
.draft .lk{margin-left:0}
.lk{margin-left:auto;border:0;background:none;padding:0;font-size:var(--text--2);color:var(--color-fg-secondary);text-decoration:underline;cursor:pointer}
.dh{font-size:var(--text-1);font-weight:500;margin:var(--spacing-md) 0 var(--spacing-3xs);display:flex;align-items:baseline;gap:var(--spacing-xs)}
.dh .note{font-size:var(--text--1)}
details.lines{margin:0 0 .8em}
details.lines summary{cursor:pointer;font-size:var(--text--1);color:var(--color-fg-secondary);padding:.2em 0}
details.lines table{font-size:var(--text--2)}
details.lines td small{display:block;color:var(--color-fg-secondary)}
.acts{display:flex;gap:var(--spacing-2xs);flex-wrap:wrap;align-items:center}
.acts textarea{flex:1 1 20rem}
.bar{height:.5em;background-color:var(--color-bg-primary);border-radius:var(--radius-pill);overflow:hidden;margin:.6em 0}
.bar > i{display:block;height:100%;background-color:var(--color-dark-gray);border-radius:var(--radius-pill)}
.chips{display:flex;gap:var(--spacing-2xs);flex-wrap:wrap;font-size:var(--text--1)}
.chips span{border:1px solid var(--color-hairline);border-radius:var(--radius-pill);padding:.25em .8em}
.checks{display:flex;flex-wrap:wrap;align-items:baseline;gap:.35em var(--spacing-sm);font-size:var(--text--1);margin:0 0 .8em;padding:.55em .8em;
  border-radius:var(--radius-xs);background-color:var(--color-bg-primary)}
.checks .l{font-size:var(--text--2);text-transform:uppercase;letter-spacing:.04em;color:var(--color-fg-secondary);margin-right:.2em}
.checks .ok{color:var(--color-fg-primary)}
.checks .na{color:var(--color-fg-secondary)}
.tag.plain{display:none}
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
#sharedbar{background-color:var(--color-bg-inverse);color:var(--color-warm-gray);font-size:var(--text--1);padding:.45em var(--spacing-md-lg);border-top:1px solid rgba(255,255,255,.1)}
#toast{position:fixed;left:50%;bottom:var(--spacing-md);transform:translateX(-50%);z-index:40;background-color:var(--color-bg-inverse);color:#fff;
  font-size:var(--text--1);padding:.7em 1.1em;border-radius:var(--radius-xs);max-width:min(36rem,90vw)}
#ask{position:fixed;inset:0;z-index:50;background-color:rgba(30,28,24,.45);display:flex;align-items:center;justify-content:center;padding:var(--spacing-md)}
#ask .askbox{background-color:var(--color-stark);border-radius:var(--radius-sm);padding:var(--spacing-sm-md);max-width:34rem;width:100%}
#ask h3{margin:0 0 .6em;font-weight:600}
#ask .askbody{font-size:var(--text--1);line-height:1.5;margin-bottom:var(--spacing-sm)}
#ask ul{margin:.4em 0 0;padding-left:1.2em}
.tblwrap{overflow-x:auto}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.rid{font-family:var(--font-mono);font-size:var(--text--2);color:var(--color-fg-secondary)}
.expmiss{color:var(--color-red-text)}
.card > p.note{padding:var(--spacing-xs) var(--spacing-sm-md);margin:0}
.card h3 .r{margin-left:auto;font-weight:400}
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


RUNLOG_SVG = ('<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round">'
              '<path d="M3.5 2.5h9v11h-9z"/><path d="M5.8 5.5h4.4M5.8 8h4.4M5.8 10.5h2.6"/></svg>')


def runlog(run, kind, also=None, read=()):
    """The run log: the exports, what each check found, the estimated cost of a
    run, every input, and the build record."""
    m, views = run.get("manifest") or {}, run.get("views") or {}
    out = [DS.exports_card(m, views), DS.checks_card(run)]
    cost = DS.cost_estimate(HERE, run)
    if cost:
        main_ = cost["priced"][0]
        rows = "".join('<tr><td>%s</td><td class="n2">%s</td><td class="n2">$%s</td><td class="n2">$%s</td></tr>'
                       % (e(l), format(n, ","), format(r, ",.2f"), format(u, ",.2f")) for l, n, r, u in main_["lines"])
        out.append('<div class="card"><h3>Estimated cost per close run<span class="r note">$%s, %s tokens on %s, at list price</span></h3>'
                   '<div class="tw"><table><thead><tr><th>Tokens</th><th class="n2">Count</th><th class="n2">Per million</th><th class="n2">Cost</th></tr></thead><tbody>%s'
                   '<tr class="tot"><td>Total</td><td class="n2">%s</td><td></td><td class="n2">$%s</td></tr></tbody></table></div>'
                   '<p class="note pad">In a Claude Project the run is covered by the Claude seat; this is what the same run costs through the API. '
                   'The exports are read by the scripts, not by Claude, so their size adds no tokens.</p></div>'
                   % (format(main_["total"], ",.2f"), format(cost["tokens"], ","), e(main_["model"]), rows, format(cost["tokens"], ","), format(main_["total"], ",.2f")))
    files = {}
    for step, items in (("Engine", m.get("inputs", [])), ("Schedules", views.get("inputs", []))):
        for i in items:
            f = files.setdefault(i.get("sha256") or i.get("path"), {"path": i.get("path"), "rows": i.get("rows", 0), "sha": str(i.get("sha256", ""))[:16], "by": []})
            if step not in f["by"]:
                f["by"].append(step)
    out.append('<div class="card"><h3>Inputs</h3><div class="tw"><table><thead><tr><th>File</th><th>Read by</th><th class="n2">Rows</th><th>Fingerprint</th></tr></thead><tbody>'
               + "".join('<tr><td>%s</td><td>%s</td><td class="n2">%s</td><td class="mono">%s</td></tr>' % (e(os.path.basename(str(f["path"]))), e(" and ".join(f["by"])), format(f["rows"] or 0, ","), e(f["sha"]))
                         for f in files.values()) + "</tbody></table></div></div>")
    rec = [("Console", VERSION), ("Engine", m.get("engine_version")), ("Ruleset", m.get("ruleset_version")), ("Schedules", views.get("version") or "not added"),
           ("Run", m.get("run_id")), ("Period", m.get("period")), ("Generated", m.get("generated_at"))]
    if also:
        am = also.get("manifest") or {}
        rec.append(("Also read", "P&L Flux run %s, for the CapEx and Prepaid screens" % am.get("run_id")))
    rec.extend(read)
    out.append('<div class="card"><h3>Build record</h3><div class="tw"><table><tbody>'
               + "".join('<tr><td>%s</td><td class="mono">%s</td></tr>' % (e(a), e(b)) for a, b in rec) + "</tbody></table></div></div>")
    return page("runlog", "<h3>Run Log</h3>" + "".join(out))


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
            nav.append('<div class="tg" data-s="%d"><button class="tb sec" data-s="%d" aria-expanded="false" aria-controls="sub%d">%s<span class="n" data-cs="%d"></span></button>'
                       '<div class="sub shut" data-s="%d" id="sub%d" role="group" aria-label="%s">%s</div></div>' % (si, si, si, e(stitle), si, si, si, e(stitle), sub))
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>" + e(title) + "</title><style>" + CSS + "</style></head><body>"
            '<header class="top"><div class="brand">' + DS.LOGO + "<b>" + e(product) + "</b><span>" + e(PERIOD) + "</span></div>"
            "<nav>" + "".join(nav) + '</nav><div class="icons"><button class="tb pg" data-p="runlog" data-tip="Run log" aria-label="Run log">' + RUNLOG_SVG + "</button>"
            '<button class="tb pg" data-p="settings" data-tip="Settings" aria-label="Settings">'
            + SETTINGS_SVG + '</button></div></header><div id="sharedbar" hidden></div><div id="tip"></div><div id="toast" role="status" hidden></div>'
            '<div id="ask" hidden><div class="askbox" role="dialog" aria-modal="true"><h3></h3><div class="askbody"></div><div class="acts">'
            '<button class="pill solid" data-askok>OK</button><button class="pill" data-askno>Cancel</button></div></div></div><main>' + "".join(pages)
            + page("settings", '<div class="card"><h3>Settings</h3><div class="pad setcard"><label for="thr">Review threshold</label>'
                   '<span>$</span><input class="f" id="thr" inputmode="numeric" style="width:9ch"></div></div>'
                   '<div class="card"><h3>Decision record</h3><div class="pad acts"><button class="pill" data-recsave>Save decision record</button>'
                   '<button class="pill" data-recload>Load decision record</button><input type="file" id="recfile" accept=".json,application/json" hidden>'
                   '<button class="pill" data-carry hidden>Bring in the earlier run&rsquo;s decisions</button></div></div>')
            + '<datalist id="accts">' + "".join('<option value="%s">%s</option>' % (e(k), e(v)) for k, v in sorted(ACC.items()) if v) + "</datalist>"
            + '<datalist id="depts">' + "".join('<option value="%s">' % e(d) for d in DEPTS) + "</datalist>"
            + "<footer>Serif Biomedicines, Inc. (FL87) &middot; " + e(product) + " &middot; " + e(PERIOD) + "</footer></main><script>window.DATA="
            + json.dumps(dict(data, acct={k: v for k, v in ACC.items() if v}, period=PERIOD, version=VERSION), ensure_ascii=False).replace("</", "<\\/")
            + ";</script><script>" + COMMON_JS + js + "\nShared.start();</script></body></html>")


COMMON_JS = r"""
const $ = s => document.querySelector(s), $$ = s => Array.from(document.querySelectorAll(s));
const KEY = 'serif-console::' + DATA.kind + '::' + DATA.run;
/* The review's state. Each of STORES is a map of item to value: decisions,
   commentary and notes, entry edits, the GAAP checklist, sign-off and the audit
   log. The threshold is this browser's setting. */
const STORES = ['dec', 'notes', 'je', 'jh', 'ck', 'sign', 'log'];
const refOf = id => (DATA.ref || {})[id] || '';
let S = {dec: {}, notes: {}, sign: {}, ck: {}, je: {}, jh: {}, log: {}, thr: DATA.thr};
try { S = Object.assign(S, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch (e) {}
if (Array.isArray(S.log)){ const o = {}; S.log.forEach((l, i) => { o[String(l.at).replace(/[^0-9]/g, '') + i] = l; }); S.log = o; }
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = v => v == null ? '–' : (v < 0 ? '($' : '$') + Math.abs(Math.round(v)).toLocaleString('en-US') + (v < 0 ? ')' : '');
const plural = (n, w) => n + ' ' + w + (n === 1 ? '' : 's');
/* Escaped text with each account number followed by its name, where it is not already. */
const named = t => esc(t).replace(/\b([1-8]\d{6})\b(?!\d)/g, (c, code, at, all) => { const n = DATA.acct[code];
  if (!n) return c; const after = all.slice(at + c.length, at + c.length + n.length + 8).replace(/^[\s\-–]+/, '').toLowerCase();
  return after.startsWith(esc(n).toLowerCase().slice(0, 12)) ? c : c + ' ' + esc(n); });
function toast(msg, ms){ const t = $('#toast'); t.textContent = msg; t.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => { t.hidden = true; }, ms || 2600); }

/* ---------- shared mode ----------
   Opened as a file, the review is kept in this browser. Published as a claude.ai
   Artifact with the db and user capabilities, the Artifact's database is the
   record for everyone with access, and this browser keeps a copy. Each item is
   its own document, written only when it changes. Before a write the page reads
   the document again: if someone else changed it since this page last saw it,
   theirs stands and the reviewer is told, so no decision is overwritten unseen.
   Who decided is kept as a user id and named on screen, never stored as a name. */
const Shared = (function(){
  const st = {on: false, ro: false, stopped: false, uid: null, me: '', canWrite: null, db: null, user: null, runs: {}};
  const PER = String(DATA.period || 'period').toLowerCase().replace(/[^a-z0-9]+/g, '') || 'period';
  const RID = String(DATA.run || 'run').replace(/[^A-Za-z0-9]/g, '').slice(0, 16) || 'run';
  const HOME = 'review/' + DATA.kind + '-' + PER;
  /* The sign-off has its own root, so the Artifact's access rules can let only
     Editors sign while Contributors decide. */
  const runRoot = (rid, store) => (store === 'sign' ? 'signoff/' + DATA.kind + '-' + PER : HOME) + '/runs/' + rid;
  const MARK = 'serif-shared::' + runRoot(RID);
  const hash = s => { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0; return h.toString(16); };
  /* A document id takes letters, digits and _ - . : @ + only; anything else is
     written as ~ and its UTF-8 bytes in hex. The key is kept in the document. */
  function enc(k){
    let out = '';
    Array.from(new TextEncoder().encode(String(k))).forEach(b => { const c = String.fromCharCode(b);
      out += (b < 128 && /[A-Za-z0-9_\-.:@+]/.test(c)) ? c : '~' + b.toString(16).padStart(2, '0'); });
    if (out === '.' || out === '..') out = '~2e' + out.slice(1);
    return out.length > 180 ? out.slice(0, 150) + '~h' + hash(String(k)) : out;
  }
  const pathOf = (store, k, rid) => runRoot(rid || RID, store) + '/' + store + '/' + enc(k);
  const last = {}, ready = {}, base = {}, Q = {}, names = {};
  STORES.forEach(n => { last[n] = {}; });
  const rev = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  const nameOf = uid => !uid ? '' : uid === st.uid ? st.me : (names[uid] || 'Someone');
  function resolve(ids){
    if (!st.user || !ids.size) return;
    st.user.profiles(Array.from(ids)).then(ps => { let ch = false;
      Object.keys(ps).forEach(id => { const n = (ps[id] && ps[id].name) || 'Someone'; if (id !== st.uid && names[id] !== n){ names[id] = n; ch = true; } });
      if (ch) later(); }).catch(() => {});
  }
  const keep = () => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} };
  /* One item taken from the shared review into the page. */
  function take(store, k, body, ids){
    base[pathOf(store, k)] = body ? (body.rev || null) : null;
    if (!body){ delete S[store][k]; delete last[store][k]; return; }
    S[store][k] = body.v; last[store][k] = JSON.stringify(body.v);
    if (body.uid) ids.add(body.uid);
    if (body.v && body.v.by_uid) ids.add(body.v.by_uid);
  }
  function put(store, k, value){
    const p = pathOf(store, k);
    const body = value === null ? null : {k: k, v: value, uid: st.uid, at: new Date().toISOString(), rev: rev()};
    const w = Q[p] || (Q[p] = {busy: false, want: undefined, store: store, k: k});
    w.want = {body: body}; if (!w.busy) pump(p);
  }
  const busy = p => !!Q[p] && (Q[p].busy || Q[p].want !== undefined);
  async function pump(p){
    const w = Q[p]; w.busy = true;
    while (w.want !== undefined && st.on){
      const job = w.want; w.want = undefined;
      try {
        const ref = st.db.doc(p), cur = await ref.get();
        const curRev = cur.exists ? ((cur.data() || {}).rev || null) : null;
        const had = base[p] === undefined ? null : base[p];
        if (curRev !== had){ w.want = undefined; lost(w.store, w.k, cur); }
        else if (job.body === null){ if (cur.exists) await ref.delete(); base[p] = null; }
        else { await ref.set(job.body); base[p] = job.body.rev; }
      } catch (e){ await failed(e, w, job); }
    }
    w.busy = false;
  }
  function lost(store, k, cur){
    const body = cur.exists ? cur.data() : null, ids = new Set();
    take(store, k, body, ids); keep(); resolve(ids); later();
    toast(((body && nameOf(body.uid)) || 'Someone') + ' changed this a moment ago. Theirs is showing; make yours again if it still stands.', 4200);
  }
  async function failed(e, w, job){
    const code = (e && e.code) || 'unavailable';
    if (code === 'invalid_argument'){
      if (w.store === 'sign'){ toast('Only Editors can sign off in the shared review.', 3200); delete S.sign[w.k]; delete last.sign[w.k]; keep(); later(); return; }
      if (st.canWrite === true) toast('This change could not be saved to the shared review. It is kept in this browser.', 3200); else readOnly(); return; }
    if ((code === 'unavailable' || code === 'resource_exhausted') && !job.retried){
      job.retried = true; await new Promise(r => setTimeout(r, 800 + Math.random() * 1200)); if (w.want === undefined) w.want = job; return; }
    if (code === 'quota_exceeded'){ toast('The shared review is full and this change was not saved to it. It is kept in this browser.', 4200); return; }
    if (['revoked', 'not_granted', 'capability_disabled', 'capability_removed'].indexOf(code) > -1){ stop(); return; }
    toast('This change did not reach the shared review. It is kept in this browser.', 3200);
  }
  /* This person can read the review, not change it: the page shows the shared state. */
  function readOnly(){
    if (!st.ro){ st.ro = true; banner(); toast('Your access lets you view this review, not change it.', 3200); }
    STORES.forEach(n => { S[n] = {}; Object.keys(last[n]).forEach(k => { S[n][k] = JSON.parse(last[n][k]); }); });
    Object.keys(Q).forEach(p => { Q[p].want = undefined; }); keep(); later();
  }
  function stop(){ if (!st.on) return; st.on = false; st.stopped = true; banner(); }
  function subscribe(store){
    st.db.collection(runRoot(RID, store) + '/' + store).onSnapshot(snap => {
      const ids = new Set();
      if (!ready[store]){
        if (snap.metadata && snap.metadata.fromCache) return;
        const bodies = {}; snap.docs.forEach(d => { const b = d.data(); if (b && b.k !== undefined) bodies[b.k] = b; });
        let had = false; try { had = !!localStorage.getItem(MARK); } catch (e) {}
        /* The first time this browser joins, work it holds that the review does
           not is added to the review. After that the review is the record, and an
           item it no longer holds was cleared by someone. */
        if (had) Object.keys(S[store]).forEach(k => { if (bodies[k] === undefined) delete S[store][k]; });
        Object.keys(bodies).forEach(k => take(store, k, bodies[k], ids));
        ready[store] = true; keep(); resolve(ids);
        if (STORES.every(n => ready[n])){ try { localStorage.setItem(MARK, '1'); } catch (e) {} diffAll(); }
        later(); return;
      }
      let ch = false;
      snap.docChanges().forEach(c => { const b = c.doc.data(); if (!b || b.k === undefined) return;
        if (busy(pathOf(store, b.k))) return;
        const nb = c.type === 'removed' ? null : b;
        if (nb && last[store][b.k] === JSON.stringify(nb.v)){ base[pathOf(store, b.k)] = nb.rev || null; return; }
        take(store, b.k, nb, ids); ch = true; });
      if (ch){ keep(); resolve(ids); later(); }
    }, e => { if (e && (e.code === 'revoked' || e.code === 'not_granted')) stop(); });
  }
  let dt = null;
  function changed(){ if (!st.on) return; clearTimeout(dt); dt = setTimeout(diffAll, 450); }
  function diffAll(){
    dt = null; if (!st.on) return; if (st.ro){ readOnly(); return; }
    STORES.forEach(n => { if (!ready[n]) return;
      Object.keys(S[n]).forEach(k => { const j = JSON.stringify(S[n][k]); if (j !== last[n][k]){ last[n][k] = j; put(n, k, S[n][k]); } });
      Object.keys(last[n]).forEach(k => { if (S[n][k] === undefined){ delete last[n][k]; put(n, k, null); } }); });
  }
  let rt = null;
  function later(){ clearTimeout(rt); rt = setTimeout(() => { refresh(); showCarry(); }, 120); }
  function banner(){
    const b = $('#sharedbar'); if (!b) return;
    if (st.stopped){ b.hidden = false; b.textContent = 'Shared mode stopped: changes from here on are kept in this browser only.'; return; }
    b.hidden = !st.on;
    b.textContent = 'Shared review: decisions are visible to everyone with access to this page.' + (st.ro ? ' Your access lets you view it, not change it.' : '');
  }
  /* The runs of this close. A rerun is a new run with its own review; the
     earlier run's decisions can be brought in. */
  async function register(){
    try {
      const ref = st.db.doc(HOME), snap = await ref.get();
      st.runs = (snap.exists && (snap.data() || {}).runs) || {};
      if (!st.runs[RID] && !st.ro){
        const entry = {at: new Date().toISOString(), console: DATA.version};
        if (snap.exists) await ref.update({runs: Object.assign({}, st.runs, {[RID]: entry})}); else await ref.set({runs: {[RID]: entry}});
        st.runs[RID] = entry;
      }
    } catch (e) {}
    showCarry();
  }
  const earlier = () => Object.keys(st.runs).filter(r => r !== RID).sort((a, b) => String(st.runs[b].at).localeCompare(String(st.runs[a].at)))[0] || null;
  function showCarry(){ $$('[data-carry]').forEach(b => { b.hidden = !(st.on && !st.ro && earlier()); }); }
  async function earlierRecord(){
    const rid = earlier(); if (!rid) return null;
    const rec = {kind: 'serif-decision-record', console_kind: DATA.kind, run_id: rid, period: DATA.period, saved_at: st.runs[rid].at || ''};
    for (const n of STORES){ const q = await st.db.collection(runRoot(rid, n) + '/' + n).get(); rec[n] = {};
      q.docs.forEach(d => { const b = d.data(); if (b && b.k !== undefined) rec[n][b.k] = b.v; }); }
    return rec;
  }
  async function start(){
    banner();
    if (!window.claude || typeof window.claude.use !== 'function') return;
    let db = null, user = null;
    try { [db, user] = await Promise.all([window.claude.use('db'), window.claude.use('user')]); } catch (e) { return; }
    if (!db) return;
    st.db = db; st.user = user;
    if (user){ try { const me = await user.me(); st.uid = me.id || null; st.me = me.name || 'You';
      st.canWrite = await user.can('data.write'); if (st.canWrite === false) st.ro = true; } catch (e) {} }
    st.on = true; banner();
    STORES.forEach(subscribe);
    register();
  }
  /* A viewer cannot type into a field their access does not let them save. */
  document.addEventListener('beforeinput', ev => { if (!st.on || !st.ro) return; const t = ev.target;
    if (t && (t.tagName === 'TEXTAREA' || t.tagName === 'INPUT') && t.id !== 'thr') ev.preventDefault(); }, true);
  return {start: start, changed: changed, earlierRecord: earlierRecord,
          on: () => st.on, ro: () => st.on && st.ro, uid: () => st.on ? st.uid : null, name: nameOf};
})();
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} Shared.changed(); };
const logAdd = x => { const at = new Date().toISOString();
  S.log[at.replace(/[^0-9]/g, '') + Math.random().toString(36).slice(2, 6)] = Object.assign({at: at, by_uid: Shared.uid()}, x); };
const logList = () => Object.values(S.log).sort((a, b) => String(b.at).localeCompare(String(a.at)));
const blocked = () => { if (Shared.ro()){ toast('Your access lets you view this review, not change it.'); return true; } return false; };

/* ---------- the decision record ----------
   Everything decided on this page, saved as a file and loaded back: to hand the
   review to someone else, or to carry it into a later run of the same close.
   Items match by id, which is built from what the item is, so it is the same in
   every run. What the page already holds is kept. */
function recordOf(){
  const rec = {kind: 'serif-decision-record', format: 3, console: DATA.version, console_kind: DATA.kind,
               run_id: DATA.run, period: DATA.period, saved_at: new Date().toISOString(), saved_by: Shared.on() ? Shared.name(Shared.uid()) : ''};
  STORES.forEach(n => { rec[n] = S[n]; });
  rec.fixes = fixesOf();
  return rec;
}
/* Every agreed fix and the path it took: a reclass booked through the NetSuite CSV,
   or the original bill or Journal Entry edited in NetSuite, which stays out of the CSV.
   With the reference ID and the document, a change seen in the GL or in NetSuite's
   system notes ties back to its decision here. */
function fixesOf(){
  const out = {};
  Object.keys(S.dec).forEach(id => { const d = S.dec[id], ns = !!d && d.v === 'netsuite';
    if (!d || (!ns && ['approve', 'modify', 'recode'].indexOf(d.v) < 0) || !(DATA.je[id] || $('[data-item="' + id + '"]'))) return;
    out[id] = {ref: refOf(id), path: ns ? 'Edited in NetSuite' : 'Reclass', decision: LABEL[d.v], document: (DATA.docs || {})[id] || '',
               external_id: !ns && DATA.je[id] ? DATA.je[id].id : '', in_import: !ns && jeReady(id), held: ns || jeReady(id) ? '' : DATA.je[id] ? jeWhy(id) : 'no entry',
               note: S.notes[id] || '', at: d.at || '', by: d.by_uid ? Shared.name(d.by_uid) : ''}; });
  return out;
}
function saveRecord(){
  download('serif-' + DATA.kind + '-decision-record-' + DATA.slug + '-' + new Date().toISOString().slice(0, 16).replace(/[^0-9]/g, '') + '.json',
           JSON.stringify(recordOf(), null, 1), 'application/json');
}
function planRecord(rec){
  const here = {dec: new Set($$('[data-item],[data-jerow]').map(x => x.dataset.item || x.dataset.jerow)), ck: new Set($$('[data-ckrow]').map(x => x.dataset.ckrow)),
                sign: new Set($$('[data-sname]').map(x => x.dataset.sname)), notes: new Set($$('[data-note]').map(x => x.dataset.note))};
  here.je = new Set(Object.keys(DATA.je)); here.jh = here.je; here.log = null;
  const p = {take: {}, add: 0, kept: 0, missed: 0};
  STORES.forEach(n => { p.take[n] = [];
    Object.keys(rec[n] || {}).forEach(k => { const v = rec[n][k];
      if (v == null || (n === 'notes' && !String(v).trim())) return;
      if (here[n] && !here[n].has(k)){ p.missed++; return; }
      if (S[n][k] !== undefined && (n !== 'notes' || String(S[n][k]).trim())){ if (n !== 'log') p.kept++; return; }
      p.take[n].push([k, v]); if (n !== 'log') p.add++; }); });
  return p;
}
function applyRecord(rec, title, okLabel){
  const p = planRecord(rec);
  const from = 'Saved ' + String(rec.saved_at || '').slice(0, 16).replace('T', ' ') + (rec.saved_by ? ' by ' + rec.saved_by : '') +
               (rec.run_id === DATA.run ? ', this run.' : ', an earlier run.');
  const lines = ['Brings in ' + plural(p.add, 'decision, note or edit')];
  if (p.kept) lines.push('Keeps ' + plural(p.kept, 'item') + ' this page already holds');
  if (p.missed) lines.push(plural(p.missed, 'item') + ' not in this run');
  ask(title, from, lines, okLabel).then(yes => { if (!yes) return;
    STORES.forEach(n => p.take[n].forEach(([k, v]) => { S[n][k] = v; }));
    save(); refresh(); toast('Brought in ' + plural(p.add, 'item'), 2600); });
}
function loadRecord(file){
  const rd = new FileReader();
  rd.onload = () => { let rec; try { rec = JSON.parse(rd.result); } catch (e) { toast('That file is not a decision record'); return; }
    if (!rec || rec.kind !== 'serif-decision-record'){ toast('That file is not a decision record'); return; }
    if (rec.console_kind && rec.console_kind !== DATA.kind){ toast('That record is for the other console'); return; }
    if (!rec.console_kind || !rec.dec){ toast('That record is from a console before 2.0.0 and cannot be loaded here'); return; }
    if (rec.period && rec.period !== DATA.period){ toast('That record is for ' + rec.period + ', not ' + DATA.period); return; }
    applyRecord(rec, 'Load this decision record?', 'Load the record'); };
  rd.readAsText(file);
}
function carryRun(){
  Shared.earlierRecord().then(rec => { if (!rec){ toast('No earlier run of this close'); return; }
    applyRecord(rec, 'Bring in the earlier run’s decisions?', 'Bring them in'); }).catch(() => toast('The earlier run could not be read'));
}
/* A question asked on the page: the viewer may not show browser dialogs. */
function ask(title, sub, lines, okLabel){
  const box = $('#ask');
  box.querySelector('h3').textContent = title;
  box.querySelector('.askbody').innerHTML = '<p>' + esc(sub) + '</p><ul>' + lines.map(l => '<li>' + esc(l) + '</li>').join('') + '</ul>';
  box.querySelector('[data-askok]').textContent = okLabel; box.hidden = false;
  return new Promise(r => { ask.done = v => { box.hidden = true; r(v); }; });
}
/* navigation: a section's pages open beside its title */
function show(pid){
  $$('.page').forEach(p => p.hidden = p.id !== 'p-' + pid);
  $$('.tb.pg').forEach(b => { const on = b.dataset.p === pid; b.classList.toggle('cur', on); if (on) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current'); });
  $$('.tg[data-s]').forEach(g => { const on = !!g.querySelector('.tb.pg.cur');
    g.classList.toggle('open', on); g.querySelector('.sub').classList.toggle('shut', !on);
    g.querySelector('.tb.sec').setAttribute('aria-expanded', on ? 'true' : 'false'); });
  window.scrollTo(0, 0); refresh();
}
document.addEventListener('click', ev => {
  const s = ev.target.closest('.tb.sec');
  if (s){ const f = $('.sub[data-s="' + s.dataset.s + '"] .tb.pg'); if (f) show(f.dataset.p); return; }
  const p = ev.target.closest('.tb.pg'); if (p){ show(p.dataset.p); return; }
  const t = ev.target.closest('.tabs button');
  if (t){ const box = t.closest('[data-tabbox]');
    box.querySelectorAll(':scope > .tabs button').forEach(b => { b.classList.toggle('on', b === t); b.setAttribute('aria-selected', b === t ? 'true' : 'false'); });
    box.querySelectorAll(':scope > [data-pane]').forEach(x => x.hidden = x.dataset.pane !== t.dataset.tab); return; }
  const d = ev.target.closest('[data-d]');
  if (d){ decide(d.dataset.d, d.dataset.v, d.dataset.label); return; }
  const sg = ev.target.closest('[data-signbtn]');
  if (sg){ if (blocked()) return; const r = sg.dataset.signbtn, n = $('[data-sname="' + r + '"]'), dt = $('[data-sdate="' + r + '"]');
    if (!n.value.trim()){ n.focus(); return; }
    S.sign[r] = {name: n.value.trim(), date: dt.value.trim() || new Date().toISOString().slice(0, 10), at: new Date().toISOString(), by_uid: Shared.uid()};
    logAdd({id: 'sign:' + r, label: 'Sign-off', v: 'signed', note: n.value.trim()}); save(); refresh(); return; }
  const ck = ev.target.closest('[data-ck]');
  if (ck){ if (blocked()) return; S.ck[ck.dataset.ck] = ck.dataset.v; save(); refresh(); return; }
  const x = ev.target.closest('[data-export]'); if (x){ exportCSV(); return; }
  const pr = ev.target.closest('[data-propose]');
  if (pr){ const row = $('[data-jerow="' + pr.dataset.propose + '"]'); row.hidden = !row.hidden && !S.dec[pr.dataset.propose]; refresh(); return; }
  const rs = ev.target.closest('[data-jereset]'); if (rs){ if (blocked()) return; const id = rs.dataset.jereset; delete S.je[id]; delete S.jh[id];
    if (DATA.je[id].proposal){ delete S.dec[id]; delete S.notes[id]; logAdd({id, label: 'Propose entry', v: 'cleared', note: ''}); }
    save(); refresh(); return; }
  const u = ev.target.closest('[data-use]');
  if (u){ if (blocked()) return; const d = DATA.drafts[u.dataset.use]; S.notes[d.target] = d.note;
    if (d.item && d.v) S.dec[d.item] = {v: d.v, at: new Date().toISOString(), by_uid: Shared.uid()};
    logAdd({id: d.item || d.target, label: 'Claude draft used', v: d.v || 'used', note: d.note}); save(); refresh(); return; }
  if (ev.target.closest('[data-recsave]')){ saveRecord(); return; }
  if (ev.target.closest('[data-recload]')){ if (!blocked()) $('#recfile').click(); return; }
  if (ev.target.closest('[data-carry]')){ if (!blocked()) carryRun(); return; }
  if (ev.target.closest('[data-askok]')){ ask.done(true); return; }
  if (ev.target.closest('[data-askno]')){ ask.done(false); return; }
});
document.addEventListener('change', ev => { if (ev.target.id === 'recfile' && ev.target.files[0]){ loadRecord(ev.target.files[0]); ev.target.value = ''; } });
document.addEventListener('input', ev => {
  const t = ev.target;
  if (t.dataset.note !== undefined){ S.notes[t.dataset.note] = t.value; save(); return; }
  if (t.dataset.jef || t.dataset.jeh){ editJE(t); return; }
  if (t.id === 'thr'){ const v = Number(String(t.value).replace(/[^0-9.]/g, '')); if (isFinite(v) && v > 0){ S.thr = v; save(); refresh(); } }
});
/* tabs are announced as tabs, the selected one marked */
$$('.tabs').forEach(tl => { tl.setAttribute('role', 'tablist');
  tl.querySelectorAll('button').forEach(b => { b.setAttribute('role', 'tab'); b.setAttribute('aria-selected', b.classList.contains('on') ? 'true' : 'false'); }); });
$$('[data-tabbox] > [data-pane]').forEach(x => x.setAttribute('role', 'tabpanel'));
/* tooltips */
const tip = $('#tip');
document.addEventListener('mousemove', ev => { const t = ev.target.closest('[data-tip]');
  if (!t){ tip.style.display = 'none'; return; }
  tip.innerHTML = t.dataset.tip; tip.style.display = 'block';
  tip.style.left = Math.min(ev.clientX + 14, innerWidth - tip.offsetWidth - 8) + 'px';
  tip.style.top = Math.min(ev.clientY + 14, innerHeight - tip.offsetHeight - 8) + 'px'; });
/* decisions */
const LABEL = {used:'Draft used', approve:'Approved', reject:'Rejected', modify:'Modified', confirm:'Confirmed', recode:'Recode', netsuite:'Edited in NetSuite', ack:'Acknowledged & flagged', none:'No action', signed:'Signed', cleared:'Cleared'};
function decide(id, v, label){
  if (blocked()) return;
  const cur = S.dec[id];
  if (cur && cur.v === v) delete S.dec[id];
  else S.dec[id] = {v, at: new Date().toISOString(), by_uid: Shared.uid()};
  logAdd({id, label: label || id, v: S.dec[id] ? v : 'cleared', note: S.notes[id] || ''});
  save(); refresh();
}
const decided = id => !!S.dec[id] && (['modify', 'recode'].indexOf(S.dec[id].v) < 0 || !!(S.notes[id] || '').trim());
function paintItems(){
  $$('[data-item]').forEach(el => { const id = el.dataset.item, d = S.dec[id];
    el.classList.toggle('done', !!d);
    const fold = !!d && d.v === 'confirm';
    if (!fold) el.classList.remove('unfold');
    el.classList.toggle('folded', fold && !el.classList.contains('unfold'));
    el.classList.toggle('foldable', fold);
    const st = el.querySelector('.stp'); if (st){ st.textContent = d ? (LABEL[d.v] || d.v) + ((['modify','recode'].indexOf(d.v) > -1 && !(S.notes[id]||'').trim()) ? ', add a note' : '')
      + (d.by_uid ? ' · ' + Shared.name(d.by_uid) : '') : 'Pending';
      st.className = 'stp' + (d ? (d.v === 'reject' || d.v === 'none' ? ' rej' : ' done') : ''); }
    el.querySelectorAll('[data-d]').forEach(b => b.classList.toggle('on', !!d && d.v === b.dataset.v));
    const nt = el.querySelector('textarea[data-note]'); if (nt){ nt.hidden = !(d && ['modify','recode','netsuite','reject','none'].indexOf(d.v) > -1) && !(S.notes[id]||'').trim();
      if (document.activeElement !== nt) nt.value = S.notes[id] || ''; } });
  $$('textarea.c[data-note]').forEach(t => { if (!t.closest('[data-item]') && document.activeElement !== t) t.value = S.notes[t.dataset.note] || ''; });
  paintJE();
  $$('[data-draft]').forEach(x => { const d = (DATA.drafts || {})[x.dataset.draft]; if (d) x.hidden = !!String(S.notes[d.target] || '').trim(); });
}
/* counts: what is open on each page, and in each section */
function counts(){
  $$('[data-c]').forEach(el => { const items = $$('#p-' + el.dataset.c + ' [data-item]');
    const open = items.filter(x => !decided(x.dataset.item)).length + jeOpen(el.dataset.c).length; el.textContent = open || ''; });
  $$('[data-cs]').forEach(el => { const n = $$('.sub[data-s="' + el.dataset.cs + '"] [data-c]').reduce((a, x) => a + (Number(x.textContent) || 0), 0);
    el.textContent = n || ''; });
}
function signs(){
  $$('[data-sname]').forEach(n => { const r = n.dataset.sname, s = S.sign[r], row = n.closest('.sign');
    if (s){ n.value = s.name; $('[data-sdate="' + r + '"]').value = s.date; }
    row.classList.toggle('done', !!s); const b = row.querySelector('[data-signbtn]'); if (b) b.textContent = s ? 'Signed' : 'Sign'; });
  $$('[data-ckrow]').forEach(r => { const v = S.ck[r.dataset.ckrow]; r.querySelectorAll('[data-ck]').forEach(b => b.classList.toggle('on', b.dataset.v === v)); });
}
/* A published page cannot start a download; it offers the file through the
   downloads capability and the viewer confirms the save. Opened as a file, the
   browser saves it. */
function download(name, text, type){
  const blob = new Blob([(type ? '' : '\ufeff') + text], {type: type || 'text/csv;charset=utf-8'});
  const go = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0); };
  if (!(window.claude && typeof window.claude.use === 'function')){ go(); return; }
  window.claude.use('downloads').then(dl => { if (!dl){ go(); return; }
    dl.save({filename: name, data: blob}).catch(e => { const c = (e && e.code) || '';
      toast(c === 'declined' ? 'Not saved' : c === 'rate_limited' ? 'A save is already waiting for an answer' : 'Files cannot be saved from this page here'); }); }).catch(go);
}
const csv = rows => rows.map(r => r.map(c => { const s = String(c == null ? '' : c); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }).join(',')).join('\n');
/* Proposed Journal Entries: filled in from the run, edited in place. An edit
   is kept in S.je and marks the item Modified (Recode on a vendor line). */
const jeOf = id => { const b = DATA.je[id], j = Object.assign({}, b, S.jh[id] || {});   // S.je holds the lines, S.jh the header fields edited
  j.lines = (S.je[id] || b.lines).map(l => l.memo == null ? Object.assign({}, l, {memo: j.memo}) : l); return j; };
const jeBal = j => Math.round(j.lines.reduce((a, l) => a + (Number(l.debit) || 0) - (Number(l.credit) || 0), 0) * 100) / 100;
const jeNoop = j => { const m = {}; j.lines.forEach(l => { const k = (l.account || '') + '|' + (l.department || ''); m[k] = (m[k] || 0) + (Number(l.debit) || 0) - (Number(l.credit) || 0); });
  return Object.values(m).every(v => Math.abs(v) < 0.005); };
const jeEdited = id => !!(S.je[id] || S.jh[id]);
const jeLive = id => { const d = S.dec[id]; return !!d && ['approve', 'modify', 'recode'].indexOf(d.v) > -1 && !!DATA.je[id] && (!DATA.je[id].proposal || jeEdited(id)); };
const nsIds = () => $$('[data-item]').map(x => x.dataset.item).filter(id => (S.dec[id] || {}).v === 'netsuite');   // fixed in NetSuite: resolved, never in the import
const isoOk = s => /^\d{4}-\d{2}-\d{2}$/.test(s || '') && !isNaN(Date.parse(s)) && new Date(s).toISOString().slice(0, 10) === s;
/* why an entry cannot go into the import yet, or '' */
const jeWhy = id => { const j = jeOf(id);
  return jeBal(j) ? 'out of balance' : jeNoop(j) ? 'unchanged' : !decided(id) ? 'missing note' : !j.lines.every(l => (l.account || '').trim()) ? 'missing account'
    : !isoOk(j.date) ? 'Journal Date is not a valid date' : !/^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4}$/.test(j.period || '') ? 'Posting Period is not Mon YYYY'
    : j.reversing === 'Y' && !(j.reversal_date || '').trim() ? 'reversal date missing' : j.reversing === 'Y' && !(isoOk(j.reversal_date) && j.reversal_date > j.date) ? 'Reversal Date is not a date after the Journal Date' : ''; };
const jeReady = id => jeLive(id) && decided(id) && !jeWhy(id);
const jeOpen = pg => $$('#p-' + pg + ' [data-jerow]').filter(r => jeEdited(r.dataset.jerow) && !(jeLive(r.dataset.jerow) && jeReady(r.dataset.jerow)));   // proposals begun and not ready
function editJE(t){
  if (Shared.ro()) return;
  const [id, i, f] = (t.dataset.jeh || t.dataset.jef).split('|');
  if (t.dataset.jeh){ const H = S.jh[id] || (S.jh[id] = {}), old = jeOf(id).memo; H[i] = t.value.trim();
    if (i === 'memo'){ if (!S.je[id]) S.je[id] = JSON.parse(JSON.stringify(jeOf(id).lines)); S.je[id].forEach(l => { if (l.memo == null || l.memo === old) l.memo = H.memo; }); } }
  else { if (!S.je[id]) S.je[id] = JSON.parse(JSON.stringify(DATA.je[id].lines));
    S.je[id][i][f] = f === 'debit' || f === 'credit' ? (Number(String(t.value).replace(/[^0-9.]/g, '')) || 0) : t.value.trim(); }
  const box = t.closest('[data-je]'), v = box.dataset.when || 'modify', d = S.dec[id];
  /* an item edited in NetSuite stays so: its entry then shows what was changed there */
  if (!d || (d.v !== v && d.v !== 'netsuite')){ const it = t.closest('[data-item]'), lb = it && it.querySelector('[data-d]');
    S.dec[id] = {v, at: new Date().toISOString(), by_uid: Shared.uid()}; logAdd({id, label: lb ? lb.dataset.label : box.dataset.label || id, v, note: S.notes[id] || ''}); }
  save(); refresh();
}
function paintJE(){
  const m2 = v => (v < 0 ? '($' : '$') + Math.abs(v).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + (v < 0 ? ')' : '');
  $$('[data-je]').forEach(box => { const id = box.dataset.je, d = S.dec[id], j = jeOf(id);
    if (box.dataset.when) box.hidden = !(d && (d.v === box.dataset.when || d.v === 'netsuite'));
    box.classList.toggle('edited', jeEdited(id));
    const jr = box.closest('[data-jerow]'); if (jr && d) jr.hidden = false;
    box.querySelectorAll('[data-jeh]').forEach(inp => { if (inp !== document.activeElement) inp.value = j[inp.dataset.jeh.split('|')[1]] || ''; });
    const rd = box.querySelector('[data-jeh$="|reversal_date"]'); if (rd) rd.disabled = j.reversing !== 'Y';
    box.querySelectorAll('[data-jef]').forEach(inp => { if (inp === document.activeElement) return; const [, i, f] = inp.dataset.jef.split('|'), v = j.lines[i][f];
      inp.value = f === 'debit' || f === 'credit' ? (Number(v) ? Number(v).toFixed(2) : '') : (v || ''); });
    box.querySelectorAll('[data-jean]').forEach(s => { const i = s.dataset.jean.split('|')[1]; s.textContent = DATA.acct[(j.lines[i].account || '').trim()] || ''; });
    const b = jeBal(j), st = box.querySelector('[data-jebal]');
    st.innerHTML = b ? '<span class="unf">Out of balance by ' + m2(b) + '</span>' : jeNoop(j) ? 'No change yet' : 'Balanced';
    box.querySelector('[data-jereset]').hidden = !jeEdited(id); });
  $$('[data-propose]').forEach(b => { const r = $('[data-jerow="' + b.dataset.propose + '"]'); b.setAttribute('aria-expanded', r && !r.hidden ? 'true' : 'false'); });
}
/* NetSuite rejects a Memo over 999 characters; a reviewer's note or edit can take one past it */
const memoCut = m => m.length > 999 ? m.slice(0, 996).trimEnd() + '...' : m;
function exportCSV(){
  const rows = [['External ID', 'Subsidiary', 'Journal Date', 'Posting Period', 'Currency', 'Exchange Rate', 'Memo', 'Reversing Entry', 'Reversal Date', 'Account', 'Department', 'Debit', 'Credit', 'Line Memo']];
  const held = Object.keys(DATA.je).filter(id => jeLive(id) && !jeReady(id)).map(id => jeOf(id).memo.slice(0, 60) + ': ' + jeWhy(id)).join('; ');
  Object.keys(DATA.je).forEach(id => { if (!jeReady(id)) return;
    const j = jeOf(id); j.lines.forEach(l => rows.push([j.id, j.subsidiary, j.date, j.period, j.currency, j.rate, memoCut(j.memo + (S.notes[id] ? ' | ' + S.notes[id] : '')), j.reversing,
      j.reversing === 'Y' ? j.reversal_date : '', l.account, l.department || '', l.debit || '', l.credit || '', memoCut(l.memo || '')])); });
  const ns = nsIds().length, edited = ns ? plural(ns, 'item') + ' edited in NetSuite, not in the import: the CSV holds only the reclasses to book' : '';
  const said = [held ? 'Left out: ' + held : '', edited].filter(Boolean).join('. ');
  if (rows.length === 1){ alertBox(said ? said + '.' : 'Approve an entry first: only approved entries go into the import.'); return; }
  if (said) alertBox(said + '.');
  download('serif-' + DATA.kind + '-netsuite-' + DATA.slug + '.csv', csv(rows));
}
function alertBox(msg){ const t = $('#tip'); t.innerHTML = esc(msg); t.style.display = 'block'; t.style.left = '40%'; t.style.top = '80px'; setTimeout(() => t.style.display = 'none', Math.max(2200, msg.length * 45)); }
/* The close checklist: each page, what is open on it, and what that is worth.
   Open is a flag with no decision, or a line at or over the threshold with no
   commentary. */
function checklist(){
  const host = $('[data-checklist]'); if (!host) return;
  const thr = S.thr || DATA.thr, rows = [];
  $$('.tb.pg').forEach(b => { const pid = b.dataset.p, pg = $('#p-' + pid); if (!pg || pid === 'ov' || pid === 'settings' || pid === 'runlog') return;
    let total = 0, open = 0, value = 0;
    pg.querySelectorAll('[data-item]').forEach(x => { total++; if (!decided(x.dataset.item)){ open++; value += Number(x.dataset.amt) || 0; } });
    /* A page's other comparisons (year on year, year to date) restate its lines; they count once, on the first. */
    pg.querySelectorAll('tr[data-var]').forEach(tr => { if (tr.closest('[data-alt]')) return; const a = Math.abs(Number(tr.dataset.var) || 0); if (a < thr) return;
      total++; const t = tr.querySelector('textarea[data-note]'); if (!t || !(S.notes[t.dataset.note] || '').trim()){ open++; value += a; } });
    $$('#p-' + pid + ' [data-jerow]').filter(r => jeEdited(r.dataset.jerow)).forEach(r => { total++; });
    jeOpen(pid).forEach(r => { open++; value += jeOf(r.dataset.jerow).lines.reduce((a, l) => a + (Number(l.debit) || 0), 0); });
    if (!total) return;
    rows.push('<tr class="xp' + (open ? ' open' : '') + '" data-go="' + pid + '"><td><b>' + esc(b.textContent.replace(/\d+$/, '').trim()) + '</b></td><td>' +
      (open ? '<span class="unf">' + open + ' open of ' + total + '</span>' : 'Done, ' + total + ' of ' + total) + '</td><td class="n2">' + (open ? money(value) : '') + '</td></tr>'); });
  host.innerHTML = rows.join('');
}
document.addEventListener('click', ev => { const r = ev.target.closest('tr[data-go]'); if (r) show(r.dataset.go); });
document.addEventListener('click', ev => { const h = ev.target.closest('.item.foldable > .ih'); if (!h || ev.target.closest('a,button')) return;
  const el = h.parentElement; el.classList.toggle('unfold', el.classList.contains('folded')); paintItems(); });
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
CODING_BUILT = {}


def coding_corrections():
    """What the GL Coding Review's decision record did to this period's P&L accounts: the net
    of every booked Journal Entry (approved, or modified or recoded with a note, balanced and
    changing something) by account, as the console's own rules read them, and of every item
    edited in NetSuite, by its entry. Open findings, and decisions held for a note or a
    balanced entry, are listed by account and never applied. Returns the corrections, the part
    of them edited in NetSuite, the open lines, the counts, and the lines for the run log."""
    global RAW_DRAFTS
    keep, seen, kept_drafts, kept_skipped = RAW_DRAFTS, set(_SEEN), dict(DRAFTS), len(SKIPPED)
    RAW_DRAFTS = CODING_DRAFTS
    _SEEN.clear()
    try:
        coding()
    finally:
        RAW_DRAFTS = keep
        _SEEN.clear()
        _SEEN.update(seen)
        DRAFTS.clear()
        DRAFTS.update(kept_drafts)
        del SKIPPED[kept_skipped:]
    je, items = CODING_BUILT["je"], CODING_BUILT["items"]
    known = {it[1]: it[3] for it in items}
    dec, notes, edits, heads = (CODING_REC.get(k) or {} for k in ("dec", "notes", "je", "jh"))

    def iso_ok(t):
        try:
            return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", t or "")) and bool(datetime.strptime(t, "%Y-%m-%d"))
        except ValueError:
            return False

    def amt(v, iid):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            sys.exit("--coding-record: Journal Entry %s has an amount that is not a number: %r" % (iid, v))
    # An item edited in NetSuite is a correction made on the bill or Journal Entry itself. Its
    # entry says what changed. It is applied only when this flux reads the GL export the coding
    # run read, which predates the edit; a later export may already hold it, counted twice.
    gl_sha = lambda r: {i.get("sha256") for i in r["manifest"].get("inputs") or []
                        if "netsuite_gl" in (i.get("roles") or []) or os.path.basename(str(i.get("path") or "")).startswith("netsuite_gl")}
    same_gl = bool(gl_sha(PLR)) and gl_sha(PLR) == gl_sha(GLR)
    booked, held, missing, corr, opened = [], [], [], defaultdict(float), defaultdict(list)
    edited, ns_corr, ns_blank, ns_later = [], defaultdict(float), [], []
    for iid, d in dec.items():
        if iid not in je and iid not in known:
            missing.append(iid)
            continue
        if not isinstance(d, dict) or d.get("v") not in ("approve", "modify", "recode", "netsuite") or iid not in je:
            continue
        ns = d["v"] == "netsuite"
        lines = edits[iid] if iid in edits else je[iid]["lines"]
        head = dict(je[iid], **(heads.get(iid) or {}))        # the console's jeOf: the run's header, then the header fields edited
        by, net = defaultdict(float), defaultdict(float)
        for l in lines:
            dr_cr = amt(l.get("debit"), iid) - amt(l.get("credit"), iid)
            by[((l.get("account") or "").strip(), l.get("department") or "")] += dr_cr
            net[(l.get("account") or "").strip()] += dr_cr
        # the console's jeWhy, in its order; the note rule is decided()
        why = ("out of balance" if round(sum(by.values()), 2) else "unchanged" if all(abs(v) < 0.005 for v in by.values())
               else "no note" if d["v"] in ("modify", "recode") and not str(notes.get(iid) or "").strip() else "an account missing" if not all(a for a, _ in by)
               else "" if ns else "Journal Date is not a valid date" if not iso_ok(head.get("date")) else "Posting Period is not Mon YYYY" if not re.fullmatch(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{4}", head.get("period") or "")
               else "reversal date missing" if head.get("reversing") == "Y" and not (head.get("reversal_date") or "").strip()
               else "Reversal Date is not a date after the Journal Date" if head.get("reversing") == "Y" and not (iso_ok(head.get("reversal_date")) and head["reversal_date"] > head["date"]) else "")
        vendor = known.get(iid) or je[iid]["memo"]
        if ns and why == "unchanged":                         # resolved, with nothing recorded to apply
            ns_blank.append(vendor)
            continue
        if why:
            held.append((iid, vendor, why))
            for a, v in net.items():
                if PNL(a) and round(v):
                    opened[a].append((vendor, v))
            continue
        if ns and not same_gl:
            ns_later.append(vendor)
            continue
        (edited if ns else booked).append(iid)
        for a, v in net.items():
            if PNL(a):
                corr[a] += v
                if ns:
                    ns_corr[a] += v
    for it in items:
        if it[1] in dec:
            continue
        net = defaultdict(float)
        for l in je[it[1]]["lines"] if it[1] in je else []:
            net[l["account"]] += (l.get("debit") or 0) - (l.get("credit") or 0)
        for a, v in net.items():
            if PNL(a) and round(v):
                opened[a].append((it[3], v))
    notes_out = []
    if CODING_REC.get("run_id") != GLR["manifest"]["run_id"]:
        notes_out.append("The record was saved against coding run %s, not %s; entries match by what they are" % (CODING_REC.get("run_id"), GLR["manifest"]["run_id"]))
    if missing:
        drafted = [i for i in missing if i.startswith("DR-")]
        notes_out.append("%s not in this run, not applied%s" % (count(len(missing), "decision"),
                         (" (%d on Journal Entries Claude drafted: pass --coding-drafts)" % len(drafted)) if drafted and not CODING_DRAFTS else ""))
    if held:
        notes_out.append("%s held, not applied: %s" % (count(len(held), "decision"), "; ".join("%s (%s)" % (v, w) for _, v, w in held[:5]) + (" and %d more" % (len(held) - 5) if len(held) > 5 else "")))
    few = lambda vs: "; ".join(vs[:5]) + (" and %d more" % (len(vs) - 5) if len(vs) > 5 else "")
    if edited:
        notes_out.append("%s edited in NetSuite, applied: this flux reads the coding run's GL export, from before the edits" % count(len(edited), "item"))
    if ns_later:
        notes_out.append("%s edited in NetSuite, not applied: this flux reads a GL export other than the coding run's, which may already hold the edit: %s"
                         % (count(len(ns_later), "item"), few(ns_later)))
    if ns_blank:
        notes_out.append("%s edited in NetSuite with no change on the entry, nothing to apply: %s" % (count(len(ns_blank), "item"), few(ns_blank)))
    return ({a: round(v, 2) for a, v in corr.items() if round(v)}, {a: round(v, 2) for a, v in ns_corr.items() if round(v)}, dict(opened), len(booked), len(edited), notes_out,
            sum(1 for it in items if it[1] not in dec))


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
    ent = (V.get("entries") or []) + drafted_entries()
    used_com = set()
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
    # The executive summary for the controller: Claude's draft, used and edited by the reviewer.
    sd = txt(RAW_DRAFTS.get("summary"))
    exec_summary = ('<div class="card"><div class="ch">Executive Summary</div><div class="esum">' + (draft("sum:exec", sd, "exec:summary") if sd else "")
                    + '<textarea class="c" rows="8" data-note="exec:summary" placeholder="Executive summary for the controller"></textarea></div></div>')
    pages.append(page("ov", hero("P&L Flux Analysis, " + PERIOD, "", tiles) + '<div class="grid">' + "".join(cards) + "</div>"
                      + '<div class="card"><div class="ch">Net Loss Bridge, ' + e(PRIOR) + ' to ' + e(PERIOD) + '</div>' + wf
                      + '<div class="wflegend"><span><i style="background:var(--color-dark-gray)"></i>Net loss</span><span><i style="background:var(--color-red-text)"></i>Raises the loss</span>'
                        '<span><i style="background:var(--color-mid-gray)"></i>Lowers the loss</span></div></div>' + exec_summary + CHECKLIST))

    # ----- Actual vs. Actual
    corr, ns_corr, opened, n_booked, n_edited, coding_notes, n_open = coding_corrections() if CODING_REC else ({}, {}, {}, 0, 0, [], 0)
    placed = set()

    def var_table(kind):
        base, label = ("prior", PRIOR) if kind == "mom" else ("prior_year", PY)
        adj = kind == "mom" and CODING_REC is not None
        out, fv, uf = [], 0.0, 0.0
        for s in secs:
            live = [r for r in s["rows"] if round(r.get("actual") or 0) or round(r.get(base) or 0) or (adj and r["account_code"] in corr)]
            if not live:
                continue
            out.append('<tr class="grp"><td colspan="%d">' % ((10 if adj else 8) if kind == "mom" else 6) + e(s["label"].split(" - ", 1)[-1]) + "</td></tr>")
            for r in live:
                v = vr = (r.get(base) or 0) - (r.get("actual") or 0)       # favorable positive
                cv = corr.get(r["account_code"], 0.0) if adj else 0.0
                if cv:
                    v = vr - cv                                            # the movement after the booked corrections
                    placed.add(r["account_code"])
                avgs = "".join('<td class="n2">%s</td>' % money(trailing(r["account_code"], n)) for n in (3, 6)) if kind == "mom" else ""
                fv += v if v > 0 else 0
                uf += v if v < 0 else 0
                fid = r.get("mom_finding") if kind == "mom" else None
                vend = basis(fid) if fid else ""
                line = (money(abs(v)) + (" favorable " if v > 0 else " unfavorable ") + ("MoM" if kind == "mom" else "YoY") + (" adjusted" if cv else "")
                        + (" (" + format(abs(100 * v / r[base]), ".1f") + "%)" if r.get(base) else "") + "." + (" Largest vendors" + (" (before coding corrections)" if cv else "") + ": " + e(vend) + "." if vend else ""))
                if cv:
                    nv = ns_corr.get(r["account_code"], 0.0)
                    how = ("by booked coding corrections" if not round(nv) else "by coding corrections edited in NetSuite" if not round(cv - nv)
                           else "by coding corrections (%s booked, %s edited in NetSuite)" % (money(abs(cv - nv)), money(abs(nv))))
                    line += " Reported " + money(abs(vr)) + (" favorable" if vr > 0 else " unfavorable") + ", " + money(abs(cv)) + (" moved out" if cv < 0 else " moved in") + " " + how + "."
                ops = opened.get(r["account_code"]) if adj else None
                if not round(v):
                    line = "No change" + (" adjusted." if cv else ".") + line[line.index(" Reported"):] if cv else "No change."
                if ops:
                    line += "<div class=\"note\">Open coding findings, not applied: " + "; ".join(
                        e(vn) + " " + money(abs(ov)) + (" out" if ov < 0 else " in") for vn, ov in ops[:3]) + (" and %d more" % (len(ops) - 3) if len(ops) > 3 else "") + ".</div>"
                key = kind + ":" + r["account_code"]
                pj = jr = ""
                if kind == "mom" and round(v):
                    pid = sid("PROP", key)
                    usd = lambda x: ("($" if x < 0 else "$") + format(abs(x), ",.0f") + (")" if x < 0 else "")
                    why = "P&L flux reclass, %s %s, %s: %s %s MoM" % (r["account_code"], leaf_of(r), PERIOD, usd(abs(v)), "favorable" if v > 0 else "unfavorable")
                    je[pid] = {"id": "SERIF-" + SLUG + "-" + pid, "date": PERIOD_END, "memo": why, "proposal": True,
                               "lines": je_lines([{"account": r["account_code"]}, {"account": ""}])}
                    pj = '<button class="lk" data-propose="%s" aria-expanded="false" aria-controls="jr-%s">Propose entry</button>' % (pid, pid)
                    jr = ('<tr class="jr" id="jr-%s" data-jerow="%s" hidden><td colspan="%d">%s<textarea class="c" rows="1" data-note="%s" placeholder="Note"></textarea></td></tr>'
                          % (pid, pid, 10 if adj else 8, je_editor(pid, je[pid]["lines"], label="Propose entry " + r["account_code"]), pid))
                dn = txt((RAW_DRAFTS.get("commentary") or {}).get(r["account_code"])) if kind == "mom" else ""
                if dn:
                    used_com.add(r["account_code"])
                cols = ('<td class="n2">%s</td><td class="n2">%s</td>' % (fav(-cv) if cv else "", fav(v))) if adj else ""
                out.append('<tr data-var="%s"><td><span class="code">%s</span>%s</td><td class="n2">%s</td><td class="n2">%s</td>'
                           '<td class="n2">%s</td>%s<td class="n2">%s</td>%s<td><div class="cm">%s</div>%s<textarea class="c" rows="1" data-note="%s" placeholder="Commentary"></textarea>%s</td></tr>'
                           % (round(v, 2), e(r["account_code"]), e(leaf_of(r)), money(r["actual"]), money(r.get(base)), fav(vr), cols, fav(v, pct(v, r.get(base))) if r.get(base) else "&ndash;",
                              avgs, line, draft("com:" + key, dn, key) if dn else "", key, pj))
                out.append(jr)
        head = ("<thead><tr><th>Account</th><th class=\"n2\">" + e(PERIOD) + "</th><th class=\"n2\">" + e(label) + "</th><th class=\"n2\">$ Var</th>"
                + ('<th class="n2">Corrections</th><th class="n2">Adj. $ Var</th>' if adj else "") + "<th class=\"n2\">" + ("Adj. % Var" if adj else "% Var") + "</th>" + ('<th class="n2">3-mo avg</th><th class="n2">6-mo avg</th>' if kind == "mom" else "")
                + "<th style=\"width:%s\">Commentary</th></tr></thead>" % ("34%" if kind == "mom" else "42%"))
        sm = ('<div class="sumline">Favorable: <b>' + money(fv) + "</b> Unfavorable: <b class=\"unf\">" + money(uf) + "</b> To review: <b data-ccount></b>" + (" Corrections booked: <b>" + str(n_booked) + "</b> Journal Entries" if adj else "")
              + (" Edited in NetSuite: <b>" + str(n_edited) + "</b>" if adj and n_edited else "") + "</div>")
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

    if CODING_REC:
        lost = sorted(set(corr) - placed)
        if lost:
            coding_notes.append("No flux row for " + ", ".join(a + " " + acct_name(a) + " " + money(corr[a]) for a in lost))
        print("Coding corrections: %d booked Journal Entries%s move %d accounts; %d open findings noted, not applied."
              % (n_booked, " and %s edited in NetSuite" % count(n_edited, "item") if n_edited else "", len(corr), n_open))
        for x in coding_notes:
            print("  " + x + ".")
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
                           % (e(r["account_code"]), e(leaf_of(r)), money(r["actual"]), e(r["account_code"])))
                continue
            v = (r["budget"] or 0) - (r["actual"] or 0)
            line = money(abs(v)) + (" under plan" if v > 0 else " over plan") + (" (" + format(abs(100 * v / r["budget"]), ".1f") + "%)." if r["budget"] else ".")
            out.append('<tr data-var="%s"><td><span class="code">%s</span>%s</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td>'
                       '<td><div class="cm">%s</div><textarea class="c" rows="1" data-note="avb:%s" placeholder="Commentary"></textarea></td></tr>'
                       % (round(v, 2), e(r["account_code"]), e(leaf_of(r)), money(r["actual"]), money(r["budget"]), fav(v), fav(v, pct(v, r["budget"])) if r["budget"] else "&ndash;",
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
    # Credits in expense accounts: an account and department whose month or year to date
    # nets below zero, with the credit lines behind it.
    yr = [m for m in by_period if m.endswith(PERIOD[-4:]) and SS.period_key(m) <= SS.period_key(PERIOD)]
    cnet = defaultdict(lambda: [0.0, 0.0])
    for m in yr:
        for l in by_period[m]:
            if l["account_code"][:1] in "67":
                k_ = (l["account_code"], l["department"] or "Non-Specific")
                cnet[k_][1] += l["amount"]
                if m == PERIOD:
                    cnet[k_][0] += l["amount"]
    credits = sorted([(k_, v_) for k_, v_ in cnet.items() if round(v_[0]) < 0 or round(v_[1]) < 0], key=lambda kv: min(kv[1]))
    crows = []
    for (a, d), (mnet, ynet) in credits:
        ls = sorted([l for l in by_period.get(PERIOD, []) if l["account_code"] == a and (l["department"] or "Non-Specific") == d and l["amount"] < 0], key=lambda l: l["amount"])[:2]
        why = "; ".join("%s %s%s, %s, %s" % (e(l["txn_type"]), e(l["document_number"]), doc_links(l["document_number"]), e((l.get("vendor_or_name") or "").strip() or desc(l) or "no description"), money(l["amount"], True)) for l in ls)
        crows.append('<tr data-var="%s"><td><span class="code">%s</span>%s</td><td>%s</td><td class="n2">%s</td><td class="n2">%s</td><td><div class="cm">%s</div>'
                     '<textarea class="c" rows="1" data-note="cr:%s:%s" placeholder="Commentary"></textarea></td></tr>'
                     % (round(min(mnet, ynet), 2), e(a), e(acct_name(a)), e(d), money(mnet), money(ynet),
                        ("Largest credits in " + MON + ": " + why + ".") if why else "No credit lines in " + e(MON) + "; the year to date nets below zero.", e(a), e(d)))
    credits_card = ('<div class="card"><div class="ch">Credits in Expense Accounts<span class="r note">%s</span></div><div class="tw"><table><thead><tr><th>Account</th><th>Department</th>'
                    '<th class="n2">%s</th><th class="n2">YTD</th><th style="width:42%%">Commentary</th></tr></thead><tbody>%s</tbody></table></div></div>'
                    % (count(len(crows), "account") + " netting below zero", e(PERIOD), "".join(crows) or '<tr><td colspan="5" class="note">None this month or year to date.</td></tr>'))
    pages.append(page("dept", hero("By Department, " + MON + " vs. " + PRIOR + " (Month-over-Month)", "", [
        ("Departments", str(len(drows)), ""), ("Largest (" + MON + ")", e(big["department"]), short(big["actual"]) + " " + MON + " spend"),
        ("Biggest Swing", e(swing["department"]), fav(-swing["change"], ("&#9660; " if swing["change"] < 0 else "&#9650; ") + short(abs(swing["change"])))),
        ("Total P&amp;L (" + MON + ")", short(sum(r["actual"] for r in dm["rows"])), "")])
        + '<div class="card" data-tabbox><div class="tabs">' + "".join(tabs_) + "</div>" + "".join(panes) + "</div>" + credits_card))

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
        ppanes.append(('<div data-pane="pd%d"%s><div class="pad split"><div><h3 style="margin:0 0 .8em">%s, Payroll Analytics</h3><div class="stats">'
                      '<div><div class="l">Headcount (roster)</div><div class="x">%d</div></div><div><div class="l">Avg annual salary</div><div class="x">%s</div></div>'
                      '<div><div class="l">Median salary</div><div class="x">%s</div></div><div><div class="l">Theoretical monthly salary</div><div class="x">%s</div></div>'
                      '<div><div class="l">GL 6101000 ' + e(acct_name("6101000")) + ', %s</div><div class="x">%s</div></div><div><div class="l">Salary variance</div><div class="x">%s</div></div>'
                      '<div><div class="l">GL 6102000 ' + e(acct_name("6102000")) + ', %s</div><div class="x">%s</div></div><div><div class="l">GL 6104000 ' + e(acct_name("6104000")) + ', %s</div><div class="x">%s</div></div>'
                      '<div><div class="l">Avg bonus target</div><div class="x">%.1f%%</div></div></div><h4 style="margin:.4em 0">Payroll Tax Breakdown</h4><div class="tax">%s'
                      '<div class="row"><b>Total theoretical payroll tax</b><b>%s (%.1f%% of wages)</b></div><div class="row"><span>GL 6103000 ' + e(acct_name("6103000")) + ', %s actual</span><span>%s</span></div>'
                      '<div class="row"><span>Variance (GL vs. theoretical)</span><span>%s</span></div><div class="row"><span>Est. annual bonus pool (at target)</span><span>%s</span></div></div></div>'
                      '<div><h3 style="margin:0 0 .8em">Roster, %s</h3><div class="tw"><table><thead><tr><th>Name</th><th>Title</th><th>Type</th><th class="n2">Annual salary</th><th class="n2">Bonus %%</th></tr></thead>'
                      '<tbody>%s</tbody></table></div></div></div></div>')
                      % (k, "" if len(ptabs) == 1 else " hidden", e(r["department"]), len(r["people"]), short(statistics.mean(sal)), short(statistics.median(sal)), money(mon), MON, money(r.get("salaries")),
                         fav(-((r.get("salaries") or 0) - mon), money((r.get("salaries") or 0) - mon)), MON, money(r.get("bonus")), MON, money(r.get("benefits")), avgb, taxbars, money(tax), 100 * tax / mon,
                         MON, money(glt), fav(-(glt - tax), ("+" if glt > tax else "") + money(glt - tax)), money(bon), e(r["department"]), roster))
    t = pay.get("total") or {}
    # The bonus accrual against the pool at target, in total. The roster's departments
    # are not the ledger's, so it is not compared department by department.
    gl_bon = sum(r.get("bonus") or 0 for r in (pay.get("rows") or []))
    bdiff = gl_bon - tot["bon"] / 12
    bonus_card = (('<div class="card"><div class="ch">Bonus Accrual, All Departments</div><div class="tw"><table><thead><tr><th>Check</th><th class="n2">GL 6102000 ' + e(acct_name("6102000")) + ', %s</th>'
                  '<th class="n2">Pool at target &divide; 12</th><th class="n2">Difference</th><th style="width:40%%">Commentary</th></tr></thead><tbody>'
                  '<tr data-var="%s"><td>Bonus accrued this month</td><td class="n2">%s</td><td class="n2">%s</td><td class="n2">%s</td><td><div class="cm">Total only: the roster&rsquo;s '
                  'departments differ from the ledger&rsquo;s. Payroll tax on the bonus needs the payroll register.</div><textarea class="c" rows="1" data-note="bonus:total" placeholder="Commentary">'
                  '</textarea></td></tr></tbody></table></div></div>')
                  % (MON, round(abs(bdiff), 2), money(gl_bon), money(tot["bon"] / 12), fav(-bdiff, ("+" if bdiff > 0 else "") + money(bdiff))))
    comp.append('<tr class="tot"><td>Total</td><td class="n2">%d</td><td class="n2">&ndash;</td><td class="n2">%s</td><td class="n2">&ndash;</td><td class="n2">&ndash;</td><td class="n2">&ndash;</td>'
                '<td class="n2">%s</td><td class="n2">%.1f%%</td><td class="n2">%s</td><td class="n2">&ndash;</td><td class="n2">&ndash;</td><td class="n2">%s</td></tr>'
                % (tot["hc"], money(tot["mon"]), money(tot["tax"]), 100 * tot["tax"] / (tot["mon"] or 1), money(t.get("taxes")), money(tot["bon"])))
    pages.append(page("pay", hero("Payroll Analytics, Compensation &amp; Benefits by Department".replace("&amp;", "&"), "", [
        ("Total Annual Salary", short(tot["sal"]), "%d Regular FTE" % tot["hc"]), ("Monthly Run Rate", short(tot["mon"]), "Excl. Co-Op &amp; consultants"),
        ("Avg Payroll Tax Rate", "%.1f%%" % (100 * tot["tax"] / (tot["mon"] or 1)), "SS 6.2% + Med 1.45% + SUI ~3%"), ("Est. Annual Bonus Pool", short(tot["bon"]), "At target % per roster")])
        + '<div class="card"><div class="ch">Compensation Summary, All Departments (Monthly, Regular Employees)</div><div class="tw"><table><thead><tr><th>Department</th><th class="n2">HC</th>'
          '<th class="n2">Avg Salary</th><th class="n2">Monthly Salary</th><th class="n2">SS (6.2%)</th><th class="n2">Medicare (1.45%)</th><th class="n2">SUI (~3%)</th><th class="n2">Total Tax</th>'
          '<th class="n2">PT % Wages</th><th class="n2">GL 6103000 ' + e(acct_name("6103000")) + ', ' + MON + '</th><th class="n2">GL vs. Theoretical</th><th class="n2">Avg Bonus %</th><th class="n2">Est. Bonus Pool</th></tr></thead><tbody>'
        + "".join(comp) + '</tbody></table></div></div>' + bonus_card + '<div class="card" data-tabbox><div class="ch">Department Detail, Payroll Breakdown &amp; Roster</div><div class="tabs">' + "".join(ptabs) + "</div>" + "".join(ppanes) + "</div>"))

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
    cards_a, cards_b, impact, used_adj = [], [], 0.0, set()
    for x in ent:
        f = F.get(x["finding_id"]) or {}
        aid = sid("ADJ", x.get("kind"), x["memo"])
        pl = [l for l in x["lines"] if PNL(l["account"])]
        bsl = [l for l in x["lines"] if not PNL(l["account"])]
        imp = sum((l.get("credit") or 0) - (l.get("debit") or 0) for l in pl)
        impact += imp
        acct = pl[0] if pl else x["lines"][0]
        vend = sorted({l.get("vendor") for l in x["lines"] if l.get("vendor")})
        hi = x["debits"] >= thr
        je[aid] = {"id": x["entry_id"], "date": x["date"], "memo": x["memo"], "lines": je_lines(x["lines"]), "reverses": x.get("reverses")}
        dr = "".join('<div class="ln"><span>%s %s%s</span><span>%s</span></div>' % (e(l["account"]), e(acct_name(l["account"])), (" / " + e(l["department"])) if l.get("department") else "", money(l["debit"], True)) for l in x["lines"] if l.get("debit"))
        cr = "".join('<div class="ln"><span>%s %s%s</span><span>%s</span></div>' % (e(l["account"]), e(acct_name(l["account"])), (" / " + e(l["department"])) if l.get("department") else "", money(l["credit"], True)) for l in x["lines"] if l.get("credit"))
        docs = sorted({d for l in x["lines"] for d in (l.get("documents") or [])})[:4]
        da = (RAW_DRAFTS.get("adjustments") or {}).get(x["finding_id"]) or {}
        dhtml = ""
        if da.get("recommend") in ("book", "no_entry"):
            used_adj.add(x["finding_id"])
            v_ = "approve" if da["recommend"] == "book" else "reject"
            dhtml = draft("adj:" + aid, txt(da.get("note")), aid, aid, v_, "Approve." if v_ == "approve" else "Reject.")
        cards_a.append('<div class="item%s" data-item="%s" data-amt="%s"><div class="ih"><span class="tag ink">%s</span><b>%s</b>%s<span class="stp">Pending</span></div><div class="ib"><div class="kv">'
                       '<div><div class="l">Account</div><div class="x">%s %s</div></div><div><div class="l">Amount</div><div class="x">%s</div></div><div><div class="l">P&amp;L impact</div><div class="x">%s</div></div>'
                       '<div><div class="l">Vendor (GL)</div><div class="x">%s</div></div><div><div class="l">BS impact</div><div class="x">%s</div></div><div><div class="l">Dept</div><div class="x">%s</div></div></div>'
                       '<div class="why">%s%s</div><div class="pol">%s</div>%s'
                       '<div class="acts"><button class="pill" data-d="%s" data-v="approve" data-label="%s">Approve</button><button class="pill" data-d="%s" data-v="reject" data-label="%s">Reject</button>'
                       '<button class="pill" data-d="%s" data-v="modify" data-label="%s">Modify</button><textarea class="c" rows="1" data-note="%s" placeholder="Note" hidden></textarea></div></div></div>'
                       % (" hi" if hi else "", aid, round(x["debits"], 2), e(x.get("kind") or ""), en(x["memo"]), "", e(acct["account"]), e(acct_name(acct["account"])), money(x["debits"], True),
                          fav(imp, ("&#9660; Favorable " if imp > 0 else "&#9650; Unfavorable " if imp < 0 else "No P&amp;L impact") + (money(abs(imp), True) if round(imp) else "")),
                          e(", ".join(vend) or "&ndash;"), e(", ".join("%s %s %s" % (l["account"], acct_name(l["account"]), money((l.get("debit") or 0) - (l.get("credit") or 0), True).replace("&ndash;", "-")) for l in bsl)) or "&ndash;",
                          e(", ".join(sorted({l.get("department") for l in x["lines"] if l.get("department")})) or "&ndash;"),
                          en(f.get("recommendation") or x.get("support") or x["memo"]), (" " + " ".join(doc_links(d) for d in docs)) if docs else "", en(f.get("policy_basis") or ""), je_editor(aid, je[aid]["lines"]) + dhtml,
                          aid, e(x["memo"]), aid, e(x["memo"]), aid, e(x["memo"]), aid))
    for r in revs:
        rid = sid("REV", r["account"], r.get("department"))
        f = F.get(r["finding_id"]) or {}
        v = r.get("difference") or 0
        cards_b.append('<div class="item" data-item="%s" data-amt="%s"><div class="ih"><span class="tag hi">Forecast revision</span><b>%s</b><span class="stp">Pending</span></div><div class="ib"><div class="kv">'
                       '<div><div class="l">Account</div><div class="x">%s %s%s</div></div><div><div class="l">Variance (ledger vs. forecast)</div><div class="x">%s</div></div>'
                       '<div><div class="l">Impact</div><div class="x">Forecast only, no Journal Entry</div></div></div><div class="why">%s</div>'
                       '<div class="acts"><button class="pill" data-d="%s" data-v="ack" data-label="%s">Acknowledge &amp; Flag</button><button class="pill" data-d="%s" data-v="none" data-label="%s">No Action</button>'
                       '<textarea class="c" rows="1" data-note="%s" placeholder="Note" hidden></textarea></div></div></div>'
                       % (rid, round(abs(v), 2), e(r["account"] + " " + acct_name(r["account"]) + ((" / " + r["department"]) if r.get("department") else "")), e(r["account"]), e(acct_name(r["account"])), (" / " + e(r["department"])) if r.get("department") else "",
                          "Ledger %s, forecast %s, difference %s" % (money(r.get("ledger")), money(r.get("model")), money(v)), en(f.get("recommendation") or f.get("title") or ""), rid, "Forecast revision " + e(r["account"]), rid, "Forecast revision " + e(r["account"]), rid))
    # Billed twice after a gap: two or more bills this month, none last month, billed in
    # at least two of the four months before, and this month at least 1.5 times the usual
    # month and at or over the threshold. It may be a missed accrual coming back.
    hist = [SS.shift(PERIOD, -k) for k in range(2, 6)]
    vb = defaultdict(lambda: defaultdict(list))
    for m in [PERIOD, PRIOR] + hist:
        for l in by_period.get(m, []):
            if l["txn_type"] == "Bill" and PNL(l["account_code"]) and (l.get("vendor_or_name") or "").strip():
                vb[l["vendor_or_name"].strip()][m].append(l)
    dbl = []
    for vname, ms in vb.items():
        now = ms.get(PERIOD) or []
        billed = [m for m in hist if ms.get(m)]
        if len({l["document_number"] for l in now}) < 2 or ms.get(PRIOR) or len(billed) < 2:
            continue
        amt, usual = sum(l["amount"] for l in now), sum(sum(l["amount"] for l in ms[m]) for m in billed) / len(billed)
        if amt >= thr and amt >= 1.5 * usual:
            dbl.append((vname, amt, usual, billed, now))
    dbl.sort(key=lambda x: -x[1])
    drows_ = []
    for vname, amt, usual, billed, now in dbl:
        bydoc = defaultdict(list)
        for l in now:
            bydoc[l["document_number"]].append(l)
        docs_ = "; ".join("%s%s %s, %s" % (e(d_), doc_links(d_), money(sum(l["amount"] for l in ls_), True), e(desc(ls_[0]) or "no description"))
                          for d_, ls_ in sorted(bydoc.items(), key=lambda kv: -sum(l["amount"] for l in kv[1]))[:3])
        drows_.append('<tr data-var="%s"><td><b>%s</b></td><td class="n2">%s<small>%s</small></td><td class="n2">%s</td><td>%s</td><td><div class="cm">%s.</div>'
                      '<textarea class="c" rows="1" data-note="dbl:%s" placeholder="Commentary"></textarea></td></tr>'
                      % (round(amt, 2), e(vname), money(amt, True), count(len(bydoc), "bill"), money(usual), e(", ".join(m[:3] for m in sorted(billed, key=SS.period_key))),
                         "None in " + e(PRIOR[:3]) + ". " + docs_, e(vname)))
    dbl_section = ('<h3 style="margin:var(--spacing-md) 0 var(--spacing-xs)">Section C: Billed Twice After a Gap</h3><div class="card"><div class="tw"><table><thead><tr><th>Vendor</th>'
                   '<th class="n2">%s</th><th class="n2">Usual month</th><th>Billed in</th><th style="width:40%%">Commentary</th></tr></thead><tbody>%s</tbody></table></div></div>'
                   % (e(PERIOD), "".join(drows_) or '<tr><td colspan="5" class="note">None this month.</td></tr>'))
    pages.append(page("adj", hero("Accounting Adjustments &amp; Forecast Revisions, ".replace("&amp;", "&") + PERIOD, "", [
        ("Accounting Adj", str(len(ent)), "Affect P&amp;L / BS"), ("Forecast Revisions", str(len(revs)), "No Journal Entry required"),
        ("P&amp;L Impact (if all approved)", fav(impact, ("&#9660; " if impact > 0 else "&#9650; ") + short(abs(impact))), "Favorable" if impact > 0 else "Unfavorable"),
        ("Reviewed", '<span data-prog>0%</span>', '<span data-progn></span>')])
        + '<div class="card"><div class="ch">NetSuite Journal Entries<button class="pill solid r" data-export>Download NetSuite JE CSV</button></div></div><h3 style="margin:var(--spacing-md) 0 var(--spacing-xs)">Section A: Accounting Adjustments</h3>' + "".join(cards_a)
        + '<h3 style="margin:var(--spacing-md) 0 var(--spacing-xs)">Section B: Forecast / Budget Revisions</h3>' + "".join(cards_b) + dbl_section))

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
    # Related party: Flagship-named vendors, and journals whose memo names Flagship.
    m3 = [SS.shift(PERIOD, -2), PRIOR, PERIOD]
    rp = defaultdict(lambda: defaultdict(float))
    for m in m3:
        for l in by_period.get(m, []):
            who = (l.get("vendor_or_name") or "").strip()
            if PNL(l["account_code"]) and ("flagship" in who.lower() or "flagship" in (l.get("memo") or "").lower()):
                rp[(who or "Journal: " + (l.get("memo") or "").strip()[:60], l["account_code"])][m] += l["amount"]
    rp_rows = sorted(rp.items(), key=lambda kv: -abs(kv[1].get(PERIOD, 0)))
    rp_html = "".join('<tr><td>%s</td><td><span class="code">%s</span>%s</td>%s<td class="n2">%s</td></tr>'
                      % (e(who), e(a), e(acct_name(a)), "".join('<td class="n2">%s</td>' % money(v_.get(m)) for m in m3), fav(v_.get(PRIOR, 0) - v_.get(PERIOD, 0), money(v_.get(PERIOD, 0) - v_.get(PRIOR, 0))))
                      for (who, a), v_ in rp_rows)
    rp_tot = [sum(v_.get(m, 0) for _, v_ in rp_rows) for m in m3]
    rp_card = ('<div class="card"><div class="ch">Related Party: Flagship<span class="r note">Flagship-named vendors and journals; the intercompany policy is a draft</span></div>'
               '<div class="tw"><table><thead><tr><th>Vendor or journal</th><th>Account</th>' + "".join('<th class="n2">%s</th>' % e(m) for m in m3) + '<th class="n2">Change</th></tr></thead><tbody>'
               + (rp_html or '<tr><td colspan="6" class="note">None.</td></tr>')
               + ('<tr class="tot"><td>Total</td><td></td>' + "".join('<td class="n2">%s</td>' % money(x) for x in rp_tot) + '<td class="n2">%s</td></tr>' % money(rp_tot[2] - rp_tot[1]) if rp_rows else "")
               + "</tbody></table></div></div>")
    roles = [("prep", "Prepared by"), ("ctrl", "Controller Review"), ("cfo", "CFO Approval")]
    sign = "".join('<div class="sign"><b>%s</b><input class="f" data-sname="%s" placeholder="Name"><input class="f" data-sdate="%s" placeholder="Date"><button class="pill" data-signbtn="%s">Sign</button></div>'
                   % (lab, k, k, k) for k, lab in roles)
    pages.append(page("sox", hero("SOX &amp; GAAP Compliance, ".replace("&amp;", "&") + PERIOD + " Close", "", [
        ("GAAP Items", str(len(asc)), '<span data-ckdone></span>'), ("Sources", str(len(M["inputs"]) + len([x for x in V.get("inputs", []) if x.get("path") not in {y["path"] for y in M["inputs"]}])), "Read as exported"),
        ("Sign-offs", '<span data-signs></span>', ""), ("AI Disclosed", "Yes", "")])
        + '<div class="card"><div class="ch">Tie-Outs</div><div class="tw"><table class="ties"><thead><tr><th>Check</th><th class="n2">Amount</th><th class="n2">Against</th><th>Result</th></tr></thead><tbody>'
        + "".join(ties) + "</tbody></table></div>" + tie_note + "</div>" + rp_card
        + '<div class="split"><div class="card"><div class="ch">GAAP Compliance Checklist</div>' + ck + '</div><div><div class="card"><div class="ch">Source Data Validation</div><div class="tw"><table>'
          '<thead><tr><th>Report</th><th>File</th><th class="n2">Status</th></tr></thead><tbody>' + src + '</tbody></table></div></div><div class="card"><div class="ch">Management Sign-Off</div><div class="pad">'
        + sign + '</div></div><div class="card"><div class="pad note"><b>AI disclosure.</b> Figures, variances and proposed entries are computed by the flux engine from the exports listed. '
          'Commentary and every decision are the reviewer\'s.</div></div></div></div>'))

    sections = [("Executive Overview", [("ov", "Executive Overview")]),
                ("Analysis", [("ava", "Actual vs. Actual (MoM)"), ("avb", "Actual vs. Budget"), ("dept", "By Department (MoM)"), ("pay", "Payroll Analytics")]),
                ("Close Workflow", ([("bs", "Balance Sheet Flux")] if bs["rows"] else []) + [("adj", "Adjustments"), ("sox", "SOX & GAAP")])]
    SKIPPED.extend("commentary for " + k for k in (RAW_DRAFTS.get("commentary") or {}) if k not in used_com)
    SKIPPED.extend("adjustment note for " + k for k in (RAW_DRAFTS.get("adjustments") or {}) if k not in used_adj)
    data = {"kind": "flux", "run": M["run_id"], "slug": SLUG, "thr": thr, "je": je_finish(je), "icons": {}, "drafts": DRAFTS}
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
    pages.append(runlog(PLR, "flux", read=[("Also read", "GL Coding Review run %s and its decision record %s, saved %s" % (
        GLR["manifest"]["run_id"], hashlib.sha256(open(A.coding_record, "rb").read()).hexdigest()[:16], str(CODING_REC.get("saved_at") or "")[:16].replace("T", " ")))]
        + [("Coding corrections", x) for x in coding_notes] if CODING_REC else ()))
    return shell("Serif P&L Flux - " + PERIOD, "P&L Flux", sections, pages, data, js)


# =====================================================================
# GL Coding Review
# =====================================================================
def coding():
    V = GLR["views"]
    G = {f["finding_id"]: f for f in GLR["findings"]}
    thr = 2500.0
    vend = next(t for t in V["tables"] if t["id"] == "vendors")
    vrows = [r for s in vend["sections"] for r in s["rows"]]
    billed = [r for r in vrows if round(r.get("amount") or 0)]
    spend = sum(r["amount"] for r in billed)
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
        rows = "".join('<tr><td class="mono">%s</td><td>%s %s%s</td><td>%s</td><td><span class="mono">%s</span><small>%s</small></td><td>%s</td><td class="n2">%s</td></tr>'
                       % (e(i["date"]), e(i["type"]), e(i["document"]), doc_links(i["document"]), e(i["text"]), e(i["account"]), e(acct_name(i["account"])), e(i.get("department") or ""), money(i["amount"], True))
                       for i in sorted(its, key=lambda i: -abs(i["amount"])))
        more = (((r or {}).get("detail") or {}).get("count") or len(its)) - len(its) if not account and not docs else 0
        return ('<details class="lines"><summary>Lines (%d)</summary><div class="tw"><table><thead><tr><th>Date</th><th>Document</th><th>Description</th><th>Account</th><th>Department</th>'
                '<th class="n2">Amount</th></tr></thead><tbody>%s</tbody></table></div>%s</details>' % (len(its), rows, ('<p class="note">%d more lines in NetSuite.</p>' % more) if more > 0 else ""))

    def acts(iid, label, actions):
        return "".join('<button class="pill" data-d="%s" data-v="%s" data-label="%s">%s</button>' % (iid, v, e(label), lab) for v, lab in actions)

    used_ven, amts = set(), {}   # amts: each card's amount, for its reference ID
    nsdoc = {}   # item -> the document the fix changes, recorded with an Edited in NetSuite decision

    def doc_of(vname, d):
        i = next((i for r in vrows if r["vendor"] == vname for i in (r.get("detail") or {}).get("items") or [] if i["document"] == d), None)
        return (i["type"] + " " + d) if i else d

    def card(iid, vendor, amount, hi, cur, rec, doc, extra, why, pol, actions, lines="", more="", flag=True):
        dl = doc_links(doc["document"]) if doc else ""
        if doc:
            nsdoc.setdefault(iid, doc["type"] + " " + doc["document"])
        dv = (RAW_DRAFTS.get("vendors") or {}).get(vendor) or {}
        if flag and dv.get("recommend") in ("clear", "question", "entry"):
            used_ven.add(vendor)
            v_ = {"clear": "reject", "entry": "approve"}.get(dv["recommend"])
            more = draft("ven:" + iid, txt(dv.get("note")), iid, iid if v_ else None, v_,
                         {"reject": "Coding stands: reject the recode.", "approve": "Approve the recode."}.get(v_, "Ask the owner.")) + more
        amts[iid] = amount or 0
        return ('<div class="item%s" data-item="%s" data-amt="%s"%s><div class="ih">{ref:%s}<b>%s</b><span class="stp">Pending</span><span class="mono">%s</span>%s</div><div class="ib"><div class="kv">'
                '<div><div class="l">Current coding</div><div class="x">%s</div></div><div><div class="l">Recommended</div><div class="x">%s</div></div>'
                '<div><div class="l">Document / item</div><div class="x">%s%s</div></div>%s</div>%s%s%s%s<div class="acts">%s<textarea class="c" rows="1" data-note="%s" placeholder="Note" hidden></textarea></div></div></div>'
                % (" hi" if hi else "", iid, round(amount or 0, 2), " data-flag" if flag else "", iid, e(vendor), money(amount, True), '<span class="tag hi">Review</span>' if hi else "", cur, rec,
                   (e(doc["type"] + " " + doc["document"]) + "<small>" + e(doc["text"]) + "</small>") if doc else "&ndash;", dl, extra,
                   ('<div class="why">' + why + "</div>") if why else "", ('<div class="pol">' + e(pol) + "</div>") if pol else "", more, lines,
                   acts(iid, vendor, actions), iid))
    coding_ = lambda a, d=None: "%s<small>%s%s</small>" % (e(a), e(acct_name(a)), (" / " + e(d)) if d else "")
    # A fix to an existing transaction is booked as a reclass (the CSV) or made by editing
    # the bill or Journal Entry in NetSuite while the period is open. An entry Claude
    # drafted has no one transaction to edit, so it is approved or not.
    FLAG_ACTS = (("approve", "Approve Recode"), ("netsuite", "Edited in NetSuite"), ("reject", "Reject"), ("modify", "Modify"))
    DRAFT_ACTS = (("approve", "Approve Recode"), ("reject", "Reject"), ("modify", "Modify"))

    # CapEx and Prepaid flags: expense that may belong on the balance sheet. These
    # are the flux engine's prepaid and capital screens, which serif_views.py runs
    # over the month's lines and puts on the vendor rows.
    screen = {"capital": [], "prepaid": []}
    for r in vrows:
        its = (r.get("detail") or {}).get("items") or []
        for fl in r.get("flags") or []:
            if fl.get("id") not in screen:
                continue
            ms = fl.get("match") or [{}]
            for m in ms:
                it = next((i for i in its if i["document"] == m.get("document") and i["account"] == m.get("account")), None)
                to = re.search(r"\b(1\d{6})\b", fl.get("do") or "")
                screen[fl["id"]].append({"vendor": r["vendor"], "from_account": m.get("account") or (it or {}).get("account") or "",
                                         "to_account": to.group(1) if to else "", "department": (it or {}).get("department") or "",
                                         "what": (it or {}).get("text") or "", "amount": (it or {}).get("amount") if len(ms) > 1 and it else fl["amount"],
                                         "why": fl.get("why") or "", "do": fl.get("do") or "", "doc": it})
    for k in screen:
        screen[k].sort(key=lambda x: -(x["amount"] or 0))
    cap_cards, pre_cards = [], []
    for sec_id, prefix, bucket, typ in (("capital", "C", cap_cards, "CapEx missed"), ("prepaid", "P", pre_cards, "Prepaid missed")):
        for r in screen[sec_id]:
            iid = sid(prefix, r["vendor"], r["from_account"], r["to_account"], r.get("what"), r.get("department"))
            doc = r["doc"] or line_doc(r["vendor"], r["from_account"])
            je[iid] = {"id": "SERIF-" + SLUG + "-" + iid, "date": doc["date"] if doc else "", "memo": "Recode %s %s from %s to %s" % (r["vendor"], r.get("what") or "", r["from_account"], r["to_account"]),
                       "lines": je_lines([{"account": r["to_account"], "department": r["department"], "debit": r["amount"]}, {"account": r["from_account"], "department": r["department"], "credit": r["amount"]}])}
            items.append(("capex" if prefix == "C" else "prepaid", iid, typ, r["vendor"], r.get("what") or "", r["amount"], r["from_account"], r["to_account"]))
            bucket.append(card(iid, r["vendor"], r["amount"], True, coding_(r["from_account"], r["department"]), '<span class="arrow">&rarr;</span> ' + coding_(r["to_account"], r["department"]),
                               doc, '<div><div class="l">Department</div><div class="x">' + e(r["department"]) + "</div></div>", en(r["why"]) + (" " + en(r["do"]) if r["do"] else ""), "",
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
        for l in ls:
            iid = sid(tag, l.get("vendor_or_name"), l["account_code"], l["document_number"], desc(l), round(l["amount"], 2))
            v = (l.get("vendor_or_name") or "").strip() or "(no vendor)"
            ea, ed = usual_expense(v, l["department"] or "")
            amt = round(l["amount"], 2)
            je[iid] = {"id": "SERIF-" + SLUG + "-" + iid, "date": l["date"], "memo": "Recode %s %s from %s to expense" % (v, desc(l), l["account_code"]),
                       "lines": je_lines([{"account": ea, "department": ed, "debit": amt}, {"account": l["account_code"], "department": l["department"], "credit": amt}]), "when": "recode"}
            doc = {"type": l["txn_type"], "document": l["document_number"], "text": desc(l), "date": l["date"]}
            out.append(card(iid, v, amt, amt >= thr, coding_(l["account_code"], l["department"]), "&ndash;", doc,
                            '<div><div class="l">Department</div><div class="x">' + e(l["department"] or "&ndash;") + "</div></div>", "", "",
                            (("confirm", "Confirm, Stays on Balance Sheet"), ("recode", "Recode to Expense"), ("netsuite", "Edited in NetSuite")), "",
                            je_editor(iid, je[iid]["lines"], "recode") + history(v), flag=False))
        return out
    cap_booked, pre_booked = booked(("15",), "CB"), booked(("13",), "PB")

    # Dept & Entity: department and account recodes, from the coding findings and their entries
    dcards = []
    for x in drafted_entries():
        iid = sid("DR", x["memo"], x["debits"])
        je[iid] = {"id": x["entry_id"], "date": x["date"], "memo": x["memo"], "lines": je_lines(x["lines"]), "reverses": x.get("reverses")}
        items.append(("dept", iid, "Drafted by Claude", ", ".join(sorted({l["vendor"] for l in x["lines"] if l["vendor"]})) or x["memo"], x["memo"], x["debits"], "", ""))
        dcards.append(card(iid, x["memo"] or "Drafted Journal Entry", x["debits"], x["debits"] >= thr, "&ndash;", "&ndash;", None,
                           '<div><div class="l">Type</div><div class="x">Drafted by Claude</div></div>', e(x["support"]), "", DRAFT_ACTS, "", je_editor(iid, je[iid]["lines"])))
    ents = {x["finding_id"]: x for x in V.get("entries") or []}
    drift = [f for f in GLR["findings"] if f["rule_id"] == "T4.ITEM_ACCOUNT_DRIFT"]
    COVER = ("T1.DEPT_INCONSISTENCY", "T4.PO_ACCOUNT_MISMATCH")
    excepted = [f for f in GLR["findings"] if f.get("excepted") and f["rule_id"] in COVER]
    exc_amt = sum(f.get("amount_at_risk") or 0 for f in excepted)
    exc_run = (GLR["manifest"].get("exceptions") or {})
    # Item drift under the review threshold is a count and a total, not cards.
    small = [f for f in drift if (f.get("amount_at_risk") or 0) < thr and f not in excepted]
    dfind = sorted([f for f in GLR["findings"] if f["rule_id"] in ("T1.DEPT_INCONSISTENCY", "T4.PO_ACCOUNT_MISMATCH")]
                   + [f for f in drift if f not in small], key=lambda f: -(f.get("amount_at_risk") or 0))
    for f in dfind:
        if f in excepted:
            continue
        sc = (f.get("evidence") or {}).get("supporting_counts") or {}
        isdrift = f["rule_id"] == "T4.ITEM_ACCOUNT_DRIFT"
        iid = (sid("D", f["rule_id"], " ".join(sc["item"].split()).casefold(), sc["po_number"], sc["po_line"]) if isdrift
               else sid("D", f["rule_id"], f.get("title")))
        x = ents.get(f["finding_id"])
        vname = sc["supplier"] if isdrift else (f.get("transaction") or {}).get("vendor_or_name") or f["title"].split(":")[0].split(" coded to ")[0]
        if x:
            crl = [l for l in x["lines"] if l.get("credit")]
            drl = [l for l in x["lines"] if l.get("debit")]
            cur = "<br>".join(sorted({coding_(l["account"], l.get("department")) for l in crl}))
            rec = '<span class="arrow">&rarr;</span> ' + "<br>".join(sorted({coding_(l["account"], l.get("department")) for l in drl}))
            je[iid] = {"id": x["entry_id"], "date": x["date"], "memo": x["memo"], "lines": je_lines(x["lines"]), "reverses": x.get("reverses")}
            docs = sorted({d for l in x["lines"] for d in (l.get("documents") or [])})
            doc = line_doc(vname)
            if docs:
                doc = next((i for r in vrows if r["vendor"] == vname for i in (r.get("detail") or {}).get("items") or [] if i["document"] in docs), doc)
        else:
            ev = f.get("evidence") or {}
            cur, rec, doc = en(ev.get("observed") or ""), '<span class="arrow">&rarr;</span> ' + en(ev.get("expected") or ""), line_doc(vname)
            if isdrift:
                cur, rec = coding_(sc["account"]), '<span class="arrow">&rarr;</span> ' + coding_(sc["usual_account"])
                doc = {"type": "Coupa PO", "document": sc["po_number"], "text": "line %s, %s: %s" % (sc["po_line"], sc["order_date"], sc["item"])}
        if x and docs:
            nsdoc[iid] = ", ".join(doc_of(vname, d) for d in docs)
        typ = "Department" if f["rule_id"].startswith("T1") else "Account vs. Coupa"
        items.append(("dept", iid, typ, vname, (doc or {}).get("text") or "", f.get("amount_at_risk") or 0, "", ""))
        dcards.append(card(iid, vname, f.get("amount_at_risk") or 0, (f.get("amount_at_risk") or 0) >= thr, cur, rec, doc,
                           '<div><div class="l">Type</div><div class="x">' + e(typ) + "</div></div>", en(f.get("recommendation") or ""), "", FLAG_ACTS,
                           lines_html(vname, docs=set(d for l in (x or {}).get("lines", []) for d in (l.get("documents") or [])) or None),
                           (je_editor(iid, je[iid]["lines"]) if iid in je else "") + history(vname)))

    # Reviewed & Cleared and New This Period: by department, then account
    def coding_of(r):
        c = max(r.get("by_coding") or [{"account": "", "department": "", "current": 0}], key=lambda x: abs(x.get("current") or 0))
        return c.get("department") or "Non-Specific", c["account"], c.get("current") or r["amount"]

    def vcard(iid, r, tag, why, actions, checks=False):
        dept, a, camt = coding_of(r)
        dv = (RAW_DRAFTS.get("vendors") or {}).get(r["vendor"]) or {}
        dh = ""
        if dv.get("recommend") in ("clear", "question", "entry"):
            used_ven.add(r["vendor"])
            v_ = {"clear": "confirm", "entry": "recode"}.get(dv["recommend"])
            dh = draft("ven:" + iid, txt(dv.get("note")), iid, iid if v_ else None, v_,
                       {"confirm": "Confirm.", "recode": "Recode."}.get(v_, "Ask the owner."))
        doc = line_doc(r["vendor"])
        if doc:
            nsdoc[iid] = doc["type"] + " " + doc["document"]
        cur = "<br>".join(coding_(c["account"], c.get("department")) for c in (r.get("by_coding") or []) if round(c.get("current") or 0)) or coding_(a)
        je[iid] = {"id": "SERIF-" + SLUG + "-" + iid, "date": (doc or {}).get("date") or "", "memo": "Recode %s from %s %s" % (r["vendor"], a, dept),
                   "lines": je_lines([{"account": a, "department": dept, "debit": camt}, {"account": a, "department": dept, "credit": camt}]), "when": "recode"}
        amts[iid] = r["amount"] or 0
        return ('<div class="item" data-item="%s" data-amt="%s"><div class="ih">{ref:%s}<b>%s</b><span class="stp">Pending</span><span class="mono">%s</span><span class="tag%s">%s</span></div>'
                '<div class="ib"><div class="kv"><div><div class="l">Current coding</div><div class="x">%s</div></div><div><div class="l">Document / item</div><div class="x">%s%s</div></div>'
                '<div><div class="l">%s</div><div class="x">%s</div></div></div>%s%s%s%s<div class="acts">%s<textarea class="c" rows="1" data-note="%s" placeholder="Note" hidden></textarea></div></div></div>'
                % (iid, round(r["amount"] or 0, 2), iid, e(r["vendor"]), money(r["amount"], True), " hi" if tag == "Review" else (" plain" if not tag else ""), tag, cur,
                   (e(doc["type"] + " " + doc["document"]) + "<small>" + e(doc["text"]) + "</small>") if doc else "&ndash;", doc_links(doc["document"]) if doc else "",
                   "Lines this month", str(((r.get("detail") or {}).get("count") or 0)), (why if checks else '<div class="why">' + why + "</div>") if why else "",
                   dh + history(r["vendor"]), je_editor(iid, je[iid]["lines"], "recode"), lines_html(r["vendor"]), acts(iid, r["vendor"], actions), iid))

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
                out.append('<div class="grphead"><span class="tag">%s %s</span>%s &middot; %s</div>' % (e(a), e(acct_name(a)), count(len(vs), "vendor"), money(sum(r["amount"] for r in vs), True)))
                out.extend(make(r) for r in sorted(vs, key=lambda r: -r["amount"]))
        return out

    clear = [r for r in vrows if not r.get("flags") and round(r.get("amount") or 0)]
    P2 = SS.shift(PERIOD, -2)

    def passed(r):
        """What was checked on a vendor no check flagged, and what each found. A check
        with nothing to compare against says so, and is not counted as passed."""
        cur = {(c["account"], c.get("department")) for c in (r.get("by_coding") or []) if round(c.get("current") or 0)}
        hist = {(c["account"], c.get("department")) for c in (r.get("by_coding") or []) if round(c.get("prior") or 0) or round(c.get("prior2") or 0)}
        coupa = any((LINKS.get(str(i["document"])) or {}).get("coupa") for i in ((r.get("detail") or {}).get("items") or []))
        out = [("ok", "Coded as in %s and %s" % (P2[:3], PRIOR[:3])) if hist and cur <= hist else
               ("ok", "Department is the vendor's usual") if hist else ("na", "No bills in %s or %s to compare" % (P2[:3], PRIOR[:3])),
               ("ok", "Account matches its Coupa PO") if coupa else ("na", "No Coupa PO to compare"),
               ("ok", "Not a prepaid or capital purchase"),
               ("ok", "Coded as planned") if r.get("planned") else ("na", "No plan line for this vendor")]
        return ('<div class="checks"><span class="l">Checks</span>' + "".join(
            '<span class="%s">%s%s</span>' % (k, "&#10003; " if k == "ok" else "&ndash; ", e(t)) for k, t in out) + "</div>")

    def clear_card(r):
        return vcard(sid("R", r["vendor"]), r, "$2,500 or more" if r["amount"] >= thr else "", passed(r),
                     (("confirm", "Confirm, No Recode"), ("recode", "Recode This Line"), ("netsuite", "Edited in NetSuite")), checks=True)
    ccards = by_dept(clear, clear_card)
    news = sorted([r for r in vrows if any(f.get("id") == "new" for f in r.get("flags") or []) and round(r.get("amount") or 0)], key=lambda r: -r["amount"])
    def new_card(r):
        fl = next(f for f in r["flags"] if f.get("id") == "new")
        return vcard(sid("N", r["vendor"]), r, "Review" if r["amount"] >= thr else "Routine",
                     "<b>Assessment:</b> " + en(fl.get("why") or "") + ((" <b>Action:</b> " + en(fl.get("do"))) if fl.get("do") else ""),
                     (("confirm", "Confirm Vendor &amp; Coding"), ("recode", "Recode This Line"), ("netsuite", "Edited in NetSuite")))
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
        ("Flags Identified", str(len(flagged)), "%s &middot; %.1f%% of period spend" % (money(famt), 100 * famt / spend)
         + (" &middot; plus %s, %s" % (count(len(excepted), "accepted exception"), money(exc_amt)) if excepted else "")),
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
    exc_html = ""
    issues = ([("Not applied", "the file is malformed: " + exc_run.get("error", ""))] if exc_run.get("status") == "malformed" else []) \
        + [("Rejected, line %s" % r["row"], "%s: %s" % (r["vendor"] or "no vendor", "; ".join(r["problems"]))) for r in exc_run.get("rejected") or []] \
        + [("Matched nothing, line %s" % r["row"], r["vendor"]) for r in exc_run.get("unmatched") or []]
    if issues:
        exc_html += ('<h4 class="dh">Accepted Exceptions: Rows Not Applied<span class="note">%s</span></h4><div class="card"><div class="tw"><table><tbody>%s</tbody></table></div></div>'
                     % (count(len(issues), "problem"), "".join("<tr><td>%s</td><td>%s</td></tr>" % (e(a), e(b)) for a, b in issues)))
    if excepted:
        exc_html += ('<h4 class="dh">Accepted Exceptions<span class="note">%s &middot; %s &middot; kept and counted, not for review</span></h4>'
                    '<div class="card"><div class="tw"><table><thead><tr><th>Finding</th><th>Vendor</th><th class="n2">Amount</th><th>Reason</th><th>Approved by</th></tr></thead><tbody>%s</tbody></table></div></div>'
                    % (count(len(excepted), "item"), money(sum(f.get("amount_at_risk") or 0 for f in excepted), True),
                       "".join('<tr><td>%s<small>%s</small></td><td>%s</td><td class="n2">%s</td><td>%s</td><td>%s</td></tr>' % (
                           e(f["title"]), e(f["finding_id"]), e(f["excepted"]["vendor"]), money(f.get("amount_at_risk") or 0, True),
                           e(f["excepted"]["reason"]), e(f["excepted"]["approved_by"] + (", " + f["excepted"]["approved_on"] if f["excepted"].get("approved_on") else "")))
                               for f in excepted)))
    pages.append(page("dept", '<h3>Dept &amp; Entity Flags <span class="note">%d items &middot; %s total</span></h3>' % (len(dcards), money(sum(i[5] for i in items if i[0] == "dept"), True))
                      + ('<p class="note">%s on an account other than the item\'s usual one, under %s: %s in all, not listed.</p>' % (count(len(small), "Coupa PO line"), money(thr), money(sum(f["amount_at_risk"] for f in small), True)) if small else "")
                      + "".join(dcards) + exc_html))
    pages.append(page("clear", '<h3>Reviewed &amp; Cleared <span class="note">%d vendors &middot; %s</span></h3><div class="legend">No check flagged these vendors. '
                      'Confirm each one, or recode it if the coding is wrong. Start with those at $2,500 or more.</div>' % (len(clear), money(sum(r["amount"] for r in clear), True)) + "".join(ccards)))
    pages.append(page("new", '<h3>New This Period <span class="note">%d vendors &middot; first appearance in the ledger</span></h3><div class="legend">'
                      '<span class="tag hi">Review</span>$2,500 or more<span class="tag">Routine</span>Under $2,500</div>' % len(news) + "".join(ncards)))
    pages.append(page("audit", '<h3>Audit Log</h3><div class="card"><div class="tw"><table><thead><tr><th>Timestamp</th><th>Item</th><th>Decision</th><th>By</th><th>Detail</th></tr></thead>'
                      '<tbody data-audit></tbody></table></div></div>'))
    srcs = "".join('<tr><td>%s</td><td class="mono" style="text-align:right">%s</td></tr>' % (e(a), e(b)) for a, b in
                   [(", ".join(i.get("roles") or ["input"]).replace("_", " ").title(), i["path"]) for i in GLR["manifest"]["inputs"]]
                   + [("Policy", p) for p in sorted({f.get("policy_basis") for f in GLR["findings"] if f.get("policy_basis")})]
                   + [("Review period", PERIOD), ("NetSuite subsidiary", "Serif Biomedicines, Inc. (FL87, subsidiary 97)")])
    tie = GLR["manifest"].get("tie_out") or {}
    tie_rows = "".join('<tr><td>%s</td><td class="mono" style="text-align:right">%s</td></tr>' % (a, b) for a, b in [
        (e(MON + " GL expense total (6xxxxxx)"), money(gl_6x, True)), ("Total flagged amount", money(famt + exc_amt, True)), ("Flagged as % of GL total", "%.2f%%" % (100 * (famt + exc_amt) / gl_6x)),
        *([("Of which accepted exceptions", "%d items, %s" % (len(excepted), money(exc_amt, True)))] if excepted else []),
        ("Ledger balances", ("Pass: " if tie.get("passed") else "Fail: ") + e(tie.get("note") or "")), ("Flags as subset of GL", "Pass: every flag is drawn from posted GL lines")])
    pol_rows = "".join('<tr><td>%s</td><td class="mono" style="text-align:right">%s</td></tr>' % (a, b) for a, b in [
        ("Vendors billed this month", str(len(billed))), ("P&amp;L lines this month", format(pl_lines_now, ",")), ("CapEx flags", str(len(cap_cards))), ("Prepaid flags", str(len(pre_cards))),
        ("Department and account flags", str(len(dcards))), *([("Accepted exceptions", "%d items, %s" % (len(excepted), money(exc_amt, True)))] if excepted else []), ("Vendors with no flags", str(len(clear))), ("New vendors", str(len(news)))])
    sign = "".join('<div class="sign"><b>%s</b><input class="f" data-sname="%s" placeholder="Name, title"><input class="f" data-sdate="%s" placeholder="Date"><button class="pill" data-signbtn="%s">Sign</button></div>'
                   % (lab, k, k, k) for k, lab in (("prep", "Prepared by"), ("rev", "Reviewed by"), ("appr", "Approved by")))
    pages.append(page("sox", '<h3>SOX Documentation</h3><div class="card"><div class="ch">Source Citations</div><div class="tw"><table><tbody>' + srcs + "</tbody></table></div></div>"
                      + '<div class="card"><div class="ch">GL Tie-Out</div><div class="tw"><table><tbody>' + tie_rows + "</tbody></table></div></div>"
                      + '<div class="card"><div class="ch">Policy Application Summary</div><div class="tw"><table><tbody>' + pol_rows + "</tbody></table></div></div>"
                      + '<div class="card"><div class="ch">Management Review &amp; Sign-Off</div><div class="pad">' + sign + "</div></div>"))
    pages.append(page("export", '<div class="card"><div class="ch">Export to NetSuite<button class="pill r" data-wpsave>Work paper, HTML</button><button class="pill solid" data-export>Export to NetSuite, CSV</button></div>'
                      '<div class="sumline" data-fixsum></div>'
                      '<div class="tw"><table><thead><tr><th>Memo</th><th>Account</th><th>Department</th><th class="n2">Debit</th><th class="n2">Credit</th><th>Status</th></tr></thead><tbody data-exportrows></tbody></table></div></div>'
                      '<div class="card"><div class="ch">Edited in NetSuite<span class="r note">Fixed on the bill or Journal Entry itself; resolved, and not in the CSV</span></div>'
                      '<div class="tw"><table><thead><tr><th>Ref ID</th><th>Item</th><th>Document</th><th class="n2">Amount</th><th>Note</th><th>Decided</th></tr></thead><tbody data-nsrows></tbody></table></div></div>'))
    sections = [("Overview", [("ov", "Overview")]),
                ("Review", [("capex", "CapEx Flags"), ("prepaid", "Prepaid Flags"), ("dept", "Dept & Entity")]),
                ("Transparency", [("clear", "Reviewed & Cleared"), ("new", "New This Period")]),
                ("Documentation", [("audit", "Audit Log"), ("sox", "SOX Documentation"), ("export", "Export")])]
    SKIPPED.extend("vendor note for " + k for k in (RAW_DRAFTS.get("vendors") or {}) if k not in used_ven)
    # Reference IDs: numbered by screen within the close, largest first, then by item id, so a
    # rebuild of the same data numbers them the same. Each entry's Memo starts with its card's.
    ref, n = {}, defaultdict(int)
    for iid in sorted(amts, key=lambda i: (-abs(round(amts[i], 2)), i)):
        k = REF_SCREENS[iid.split("-")[0]]
        n[k] += 1
        ref[iid] = "%s-%02d" % (k, n[k])
    for iid, j in je.items():
        j["memo"] = ref_memo(ref.get(iid), j["memo"])
    pages = [re.sub(r"\{ref:([\w-]+)\}", lambda m: '<span class="ref mono">%s</span>' % ref[m.group(1)] if m.group(1) in ref else m.group(0), x) for x in pages]
    CODING_BUILT.update(je=je_finish(je), items=items)
    data = {"kind": "coding", "run": GLR["manifest"]["run_id"], "slug": SLUG, "thr": thr, "je": je_finish(je), "ref": ref, "icons": {}, "drafts": DRAFTS}
    js = r"""
function refresh(){
  marks(); paintItems(); counts(); signs(); checklist();
  const flags = $$('[data-flag]'), ids = flags.map(x => x.dataset.item);
  const done = ids.filter(decided), v = k => ids.filter(i => S.dec[i] && S.dec[i].v === k).length;
  $$('[data-resolved]').forEach(x => x.textContent = done.length + ' / ' + ids.length);
  const pc = ids.length ? Math.round(100 * done.length / ids.length) : 0;
  $$('[data-progpct]').forEach(x => x.textContent = pc + '%'); $$('[data-progbar]').forEach(x => x.style.width = pc + '%');
  $$('[data-chips]').forEach(x => x.innerHTML = '<span>Pending: ' + (ids.length - done.length) + '</span><span>Approved: ' + v('approve') + '</span><span>Edited in NetSuite: ' + v('netsuite') + '</span><span>Rejected: ' + v('reject') + '</span><span>Modified: ' + v('modify') + '</span>');
  $$('[data-sti]').forEach(x => { const d = S.dec[x.dataset.sti]; x.textContent = d ? LABEL[d.v] : 'Pending'; });
  const F = Object.values(fixesOf()), rc = F.filter(f => f.path === 'Reclass'), N = nsIds();
  $$('[data-fixsum]').forEach(x => x.innerHTML = '<span>Agreed fixes: <b>' + F.length + '</b></span><span>Reclasses: <b>' + rc.length + '</b>, ' + rc.filter(f => f.in_import).length +
    ' ready for the import</span><span>Edited in NetSuite: <b>' + N.length + '</b>, not in the import</span>');
  const nr = $('[data-nsrows]'); if (nr) nr.innerHTML = N.length ? N.map(id => { const x = $('[data-item="' + id + '"]'), d = S.dec[id];
    return '<tr><td class="mono">' + esc(refOf(id)) + '</td><td>' + esc(x.querySelector('.ih b').textContent) + '</td><td>' + esc((DATA.docs || {})[id] || '') + '</td><td class="n2">' + money(Number(x.dataset.amt)) +
      '</td><td>' + esc(S.notes[id] || '') + '</td><td>' + esc((d.by_uid ? Shared.name(d.by_uid) + ', ' : '') + String(d.at || '').slice(0, 10)) + '</td></tr>'; }).join('')
    : '<tr><td colspan="6" class="note">Nothing marked Edited in NetSuite.</td></tr>';
  const a = $('[data-audit]'), L = logList(); if (a) a.innerHTML = L.length ? L.map(l => '<tr><td class="mono">' + esc(String(l.at).slice(0, 16).replace('T', ' ')) + '</td><td>' + esc(l.label) +
    '</td><td>' + esc(LABEL[l.v] || 'Cleared') + '</td><td>' + esc(l.by_uid ? Shared.name(l.by_uid) : '') + '</td><td>' + esc(l.note || '') + '</td></tr>').join('') : '<tr><td colspan="5" class="note">No decisions recorded yet.</td></tr>';
  const ex = $('[data-exportrows]'); if (ex){ const r = [];
    Object.keys(DATA.je).forEach(id => { if (!jeLive(id)) return; const j = jeOf(id), ok = jeReady(id);
      j.lines.forEach((l, i) => r.push('<tr><td>' + (i ? '' : named(j.memo)) + '</td><td><span class="mono">' + esc(l.account) + '</span><small>' + esc(DATA.acct[(l.account || '').trim()] || '') + '</small></td><td>' + esc(l.department || '') + '</td><td class="n2">' + (Number(l.debit) ? money(l.debit) : '') +
        '</td><td class="n2">' + (Number(l.credit) ? money(l.credit) : '') + '</td><td>' + (i ? '' : ok ? 'Ready' : '<span class="unf">' + jeWhy(id).replace(/^./, c => c.toUpperCase()) + '</span>') + '</td></tr>')); });
    ex.innerHTML = r.length ? r.join('') : '<tr><td colspan="6" class="note">No approved entries yet.</td></tr>'; }
}
/* The work paper: every decision, with its reference ID, the path an agreed fix took and
   the document it changed; the reclasses in the import; the sign-off. One page for the
   close file, to read beside the GL and NetSuite's system notes. */
function workPaper(){
  const F = fixesOf(), td = (v, c) => '<td' + (c ? ' class="' + c + '"' : '') + '>' + esc(v) + '</td>';
  const usd = v => (Number(v) || 0).toLocaleString('en-US', {style: 'currency', currency: 'USD'});
  const pageOf = x => { const p = x.closest('.page'), b = p && $('.tb.pg[data-p="' + p.id.slice(2) + '"]'); return b ? b.textContent.replace(/\d+$/, '').trim() : ''; };
  const change = id => { if (!DATA.je[id]) return ''; const j = jeOf(id); if (jeNoop(j)) return '';
    const side = k => Array.from(new Set(j.lines.filter(l => Number(l[k])).map(l => (l.account || '') + (l.department ? ' / ' + l.department : '')))).join(', ');
    return side('credit') + ' → ' + side('debit'); };
  const items = $$('[data-item]'), open = items.filter(x => !decided(x.dataset.item)), fx = Object.values(F), rc = fx.filter(f => f.path === 'Reclass');
  const dec = items.filter(x => S.dec[x.dataset.item]).map(x => { const id = x.dataset.item, d = S.dec[id], f = F[id] || {};
    return '<tr>' + td(refOf(id), 'm') + td(pageOf(x)) + td(x.querySelector('.ih b').textContent) + td(usd(x.dataset.amt), 'n') + td(LABEL[d.v] || d.v)
      + td(f.path ? f.path + (f.in_import ? ', in the import' : f.held ? ', held: ' + f.held : '') : '') + td((DATA.docs || {})[id] || '') + td(f.external_id || '', 'm') + td(change(id))
      + td(S.notes[id] || '') + td(d.by_uid ? Shared.name(d.by_uid) : '') + td(String(d.at || '').slice(0, 16).replace('T', ' '), 'm') + '</tr>'; });
  const lines = [];
  Object.keys(DATA.je).filter(jeReady).forEach(id => { const j = jeOf(id);
    j.lines.forEach((l, i) => lines.push('<tr>' + td(i ? '' : refOf(id), 'm') + td(i ? '' : j.id, 'm') + td(i ? '' : j.memo) + td(l.account, 'm') + td(l.department || '')
      + td(Number(l.debit) ? usd(l.debit) : '', 'n') + td(Number(l.credit) ? usd(l.credit) : '', 'n') + '</tr>')); });
  const signs = Object.keys(S.sign).map(r => { const s = S.sign[r], lb = $('[data-sname="' + r + '"]'); return '<tr>' + td(lb ? lb.closest('.sign').querySelector('b').textContent : r) + td(s.name) + td(s.date) + '</tr>'; });
  const table = (head, rows, none) => '<table><thead><tr>' + head.map(h => '<th>' + h + '</th>').join('') + '</tr></thead><tbody>' + (rows.join('') || '<tr><td colspan="' + head.length + '">' + none + '</td></tr>') + '</tbody></table>';
  const html = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>GL Coding Review work paper, ' + esc(DATA.period) + '</title><style>'
    + 'body{font:13px/1.4 system-ui,sans-serif;margin:24px;color:#111}h1{font-size:18px;margin:0 0 4px}h2{font-size:14px;margin:22px 0 6px}p{margin:2px 0;color:#444}'
    + 'table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:3px 6px;text-align:left;vertical-align:top}th{background:#f2f2f2}.n{text-align:right;white-space:nowrap}.m{font-family:ui-monospace,monospace;white-space:nowrap}</style></head><body>'
    + '<h1>Serif Biomedicines, Inc. &middot; GL Coding Review work paper &middot; ' + esc(DATA.period) + '</h1>'
    + '<p>Run ' + esc(DATA.run) + ', console ' + esc(DATA.version) + '. Saved ' + esc(new Date().toISOString().slice(0, 16).replace('T', ' ')) + ' UTC' + (Shared.on() ? ' by ' + esc(Shared.name(Shared.uid())) : '') + '.</p>'
    + '<p>' + items.length + ' items, ' + (items.length - open.length) + ' decided, ' + open.length + ' open. Agreed fixes: ' + fx.length + '; ' + rc.length + ' booked as reclasses (' + rc.filter(f => f.in_import).length
    + ' in the import), ' + (fx.length - rc.length) + ' edited in NetSuite, not in the import.</p>'
    + '<h2>Decisions</h2>' + table(['Ref ID', 'Page', 'Item', 'Amount', 'Decision', 'Path', 'Document', 'External ID', 'Change', 'Note', 'Decided by', 'When (UTC)'], dec, 'No decisions recorded.')
    + '<h2>Reclasses in the NetSuite import</h2>' + table(['Ref ID', 'External ID', 'Memo', 'Account', 'Department', 'Debit', 'Credit'], lines, 'None ready.')
    + '<h2>Sign-off</h2>' + table(['Role', 'Name', 'Date'], signs, 'Not signed.') + '</body></html>';
  download('serif-' + DATA.kind + '-work-paper-' + DATA.slug + '.html', html, 'text/html');
}
document.addEventListener('click', ev => { if (ev.target.closest('[data-wpsave]')) workPaper(); });
show('ov');
"""
    pages.append(runlog(GLR, "coding"))
    return shell("Serif GL Coding Review - " + PERIOD, "GL Coding Review", sections, pages, dict(data, docs=nsdoc), js)


if __name__ == "__main__":
    for kind in WANT:
        name, fn = {"flux": ("serif-pl-flux-", flux), "coding": ("serif-gl-coding-review-", coding)}[kind]
        os.makedirs(OUTS[kind], exist_ok=True)
        p = os.path.join(OUTS[kind], name + SLUG + "-v" + VERSION + ".html")
        open(p, "w", encoding="utf-8").write(fn())
        print("Wrote", p, os.path.getsize(p) // 1024, "KB")
    if RAW_DRAFTS:
        print("Drafts in the console: %d." % len(DRAFTS))
        for x in SKIPPED:
            print("Left out, does not match this run: " + x)
