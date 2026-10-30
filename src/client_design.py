"""Unity Biomedicines' design system for the consoles, and the run log's building blocks.

The tokens follow design-system/tokens.css ("Clinical teal"): white cards on a
cool-gray page, deep-slate ink, a deep teal rail and action color, a cyan accent
kept to small marks, and ok / warn / error status colors chosen to stay apart
from the teal. Every text pair clears WCAG AA (4.5:1). One open-licensed sans,
Figtree, carries text and numbers (tabular figures); client_fonts.py inlines it.

Stdlib only. Read by build_pages.py.
"""
import json
import os

try:
    from client_fonts import FONT_CSS
except ImportError:  # the console still renders on the system stack
    FONT_CSS = ""

# The design tokens: colors, type scale, spacing and radii. The neutral names
# (light / warm / mid / dark gray, red) are the console CSS's slots; the values
# are the clinical-teal palette. Contrast, measured:
#   ink #0f2e36 on white 14.0:1, on the page #eef3f5 12.5:1
#   secondary #4a5f68 on white 6.7:1, on the page 6.0:1
#   rail text #9cc0c8 on the rail #0b3d47 5.3:1, on the sub bar #0f4c57 4.9:1
#   white on teal #0b6e75 6.0:1; teal on its tint #e6f3f4 5.3:1
#   error #b42318 on white 6.6:1; warn #a15c00 5.2:1; ok #1e7a4a 5.3:1
#   cyan #0e9fac is a mark color only (3.2:1 on white, past the 3:1 non-text bar)
TOKENS = r""":root{
  --color-white:#fff; --color-light-gray:#eef3f5; --color-warm-gray:#9cc0c8;
  --color-mid-gray:#4a5f68; --color-dark-gray:#0f2e36; --color-red:#0e9fac;
  --color-hairline:#d8e1e6; --color-red-text:#b42318;
  --color-teal:#0b6e75; --color-teal-deep:#0b3d47; --color-teal-mid:#0f4c57;
  --color-cyan:#0e9fac; --color-cyan-light:#5fd4dd;
  --color-ok:#1e7a4a; --color-warn:#a15c00; --color-error:#b42318;
  --color-accent-text:var(--color-teal);
  --color-vivid:var(--color-cyan); --color-stark:var(--color-white);
  --color-ghost:var(--color-warm-gray); --color-neutral:var(--color-light-gray);
  --color-bg-primary:var(--color-light-gray); --color-bg-secondary:#dfe8ec;
  --color-bg-inverse:var(--color-teal-deep);
  --color-fg-primary:var(--color-dark-gray); --color-fg-secondary:var(--color-mid-gray);
  --color-fg-inactive:#7d9199; --color-fg-inverse:#e6f0f2;

  --font-sans:"Figtree","Hanken Grotesk","Helvetica Neue",Helvetica,Arial,sans-serif;
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

  --radius-xs:4px; --radius-sm:8px; --radius-md:10px; --radius-lg:14px; --radius-pill:999px;
  --shadow-card:0 1px 2px rgba(15,46,54,.06),0 0 0 1px rgba(15,46,54,.05);

  --ease-out:cubic-bezier(0,0,0.2,1); --ease-out-quartic:cubic-bezier(0.165,0.84,0.44,1);
  --duration-press:0.15s; --duration-hover:0.2s; --duration-control:0.25s; --duration-card:0.3s;

  --state-over:var(--color-error); --state-under:var(--color-fg-secondary);
}
"""

# Unity's monogram: a hexagon (the ring) holding three atoms bonded to one
# center, the "unity" of three parts. Strokes take currentColor; the atoms take
# the cyan accent. Beside it, the wordmark set in the console's sans.
MONOGRAM = (
    '<svg class="mono-mark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" aria-hidden="true">'
    '<path d="M16 2.5 27.7 9.25v13.5L16 29.5 4.3 22.75V9.25z" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linejoin="round"/>'
    '<path d="M16 16V8.2M16 16l6.75 3.9M16 16l-6.75 3.9" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round"/>'
    '<g fill="var(--color-cyan-light,#5fd4dd)"><circle cx="16" cy="8.2" r="2.3"/>'
    '<circle cx="22.75" cy="19.9" r="2.3"/><circle cx="9.25" cy="19.9" r="2.3"/></g>'
    '<circle cx="16" cy="16" r="2.6" fill="currentColor"/></svg>'
)

LOGO = (
    '<span class="logo" role="img" aria-label="Unity Biomedicines">' + MONOGRAM
    + '<span class="wm" aria-hidden="true"><b>Unity</b><i>Biomedicines</i></span></span>'
)


def esc(value):
    text = str(value if value is not None else "")
    for old, new in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ('"', "&quot;")):
        text = text.replace(old, new)
    return text


# What one close run would cost through the API, priced at list. A Claude Project run
# is covered by the Claude seat, so this is an estimate built from the Project's files
# and the run itself. A run is agentic: Claude reads the instructions, runs the
# scripts, reads the findings, writes the summary and builds the console, one model
# turn per step.
COST_PRICES = [{"model": "Claude Sonnet 5.5 at medium effort", "input": 2.00, "cached": 0.20,
                "output": 10.00}]
COST_THINKING_TOKENS = 1_500
COST_SYSTEM_TOKENS = 20_000
COST_SCRIPT_TOKENS = 500
COST_READ_CHUNK = 10
COST_DRAFT_TOKENS = 150
COST_SUMMARY_TOKENS = 3_000
COST_READ = (".md", ".sql", ".csv")
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


# The exports a month needs, in the order Unity pulls them, and what each one feeds.
MONTHLY_EXPORTS = [
    ("netsuite_gl", "NetSuite Custom General Ledger saved search", "Every check"),
    ("coupa", "Coupa PO line report", "PO accounts, accruals and requesters"),
    ("forecast", "Rolling forecast, the month's cut", "Forecast vs. Actual"),
    ("plan", "Rolling forecast, the plan", "Actual vs. plan and planned coding"),
    ("hris_roster", "UKG roster", "Requester departments, names and pay"),
    ("netsuite_link_ids", "NetSuite link IDs, from the connector", "Links to NetSuite records"),
    ("netsuite_income_statement", "NetSuite Income Statement", "The tie to NetSuite, account by account"),
    ("netsuite_balance_sheet", "NetSuite Balance Sheet", "Balance Sheet Flux and its tie-outs"),
    ("netsuite_ref", "NetSuite lists: accounts, departments, programs", "NetSuite internal IDs in the import CSV"),
]
FLUX_ONLY = ("forecast", "netsuite_balance_sheet")


def exports_card(m, views, extra=None):
    """The month's exports, each file read or Not supplied, and what each feeds. extra adds
    the reports the console build reads itself, {role: [paths]}. A Coupa report that stops at a
    row limit, or lacks columns the checks read, says so on its row."""
    flux = "uc2" in str(m.get("ruleset_version", ""))
    got, many = {}, {}
    for item in m.get("inputs", []):
        roles = item.get("roles") or (["netsuite_gl"] if str(item.get("path", "")).startswith("netsuite_gl")
                                      else ["coupa"] if str(item.get("path", "")).startswith("coupa") else [])
        for r in roles:
            got.setdefault(r, item)
            # every file a role was read from: a GL can come in more than one
            if item.get("path") not in [x.get("path") for x in many.get(r, [])]:
                many.setdefault(r, []).append(item)
    for item in views.get("inputs", []):
        role = {"forecast_workbook": "plan"}.get(item.get("role"), item.get("role"))
        got.setdefault(role, item)
    for role, paths in (extra or {}).items():
        if paths:
            many[role] = [{"path": x} for x in paths]
            got.setdefault(role, many[role][0])
    cc = m.get("coupa_coverage") or {}
    limits = []
    if cc.get("report_lines") is not None:
        limits.append("%s lines for the month, of %s in the report." % (format(cc.get("lines") or 0, ","), format(cc["report_lines"], ",")))
    if cc.get("row_limit"):
        limits.append("It stops at the %s-row limit, so it may not hold every line for the months it covers." % format(cc["row_limit"], ","))
    if cc.get("columns_absent"):
        limits.append("It lacks or leaves empty: %s. What each check found, below, says which checks did not run or ran degraded." % ", ".join(cc["columns_absent"]))
    rows = []
    for role, label, feeds in MONTHLY_EXPORTS:
        if role in FLUX_ONLY and not flux:
            continue
        item = got.get(role)
        note = (' <span class="expmiss">' + esc(" ".join(limits)) + "</span>") if role == "coupa" and item and limits else ""
        rows.append("<tr><td>" + esc(label) + "</td><td>"
                    + ("<br>".join('<span class="mono">' + esc(os.path.basename(str(x.get("path")))) + "</span>" for x in (many.get(role) or [item]))
                       if item else '<span class="expmiss">Not supplied</span>')
                    + "</td><td>" + esc(feeds) + note + "</td></tr>")
    return ('<div class="card"><h3>Exports this month</h3>'
            '<div class="tblwrap"><table><thead><tr><th>Export</th><th>File</th>'
            '<th>Feeds</th></tr></thead><tbody>' + "".join(rows)
            + "</tbody></table></div></div>")


# A plain name for each check, for the list of what every check found.
CHECK_NAMES = {
    "T0.TIE_OUT": "Debits equal credits", "T0.DUPLICATE_LINE": "Duplicate postings",
    "T0.POSTING_LAG": "Posting lag", "T0.ABERRANT_POSTING_LAG": "Posting lag",
    "V.REQUESTER": "Requester's department against the coding",
    "F4.OPEN_COMMITMENT": "Open PO commitments, a disclosure",
    "T1.DEPT_INCONSISTENCY": "Department against the vendor's usual coding",
    "T1.MISSING_PROJECT_CODE": "Missing project code", "T1.MEMO_FORMAT": "Memo format",
    "T1.VENDOR_NAME_VARIANTS": "Vendor name variants", "T1B.UNALLOCATED_SPEND": "Unallocated spend",
    "T4.PO_ACCOUNT_MISMATCH": "Account against the Coupa PO", "T4.ITEM_ACCOUNT_DRIFT": "Item on an account other than its usual one",
    "T4.OFF_PO_SPEND": "Spend with no PO",
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
    ran += [r for r in notes if r not in ran]
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
