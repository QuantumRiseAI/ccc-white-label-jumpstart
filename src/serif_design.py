"""Serif's design system for the consoles, and the run log's building blocks.

The tokens follow design-system/tokens.css, from the Serif Brand Guide
(brandpad.io/serif) and serifbiomedicines.com: Dark Gray and Light Gray carry the
page, Mid Gray and Warm Gray are the secondary neutrals, and Red marks the live
thing. The brand faces, Denim and Eliza, are licensed and not embedded;
serif_fonts.py inlines the open-licensed stand-ins (Figtree, PT Serif), and the
stacks name the brand faces first so an installed copy takes effect.

Stdlib only. Read by build_pages.py.
"""
import json
import os

try:
    from serif_fonts import FONT_CSS
except ImportError:  # the console still renders on the system stack
    FONT_CSS = ""

# The design tokens: colors, type scale, spacing and radii.
TOKENS = r""":root{
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
"""

# Serif's own wordmark, from serifbiomedicines.com. The brand allows it in Dark Gray
# or White only.
LOGO_PATH = 'M41.734 42.272c-1.773-1.67-4.026-3.274-6.752-4.809-2.729-1.535-5.934-3.221-9.616-5.062-4.91-2.456-8.815-4.773-11.711-6.958-2.9-2.182-4.348-5.249-4.348-9.207 0-3.958 1.364-7.125 4.09-9.31 2.726-2.182 6.343-3.273 10.843-3.273 1.364 0 2.71.103 4.039.306 1.33.206 2.61.512 3.836.92l8.39 17.083h2.864V4.985C40.98 3.691 38.1 2.548 34.725 1.558 31.352.57 27.82.074 24.14.074c-3.273 0-6.379.444-9.31 1.33-2.932.887-5.475 2.181-7.621 3.887a18.922 18.922 0 0 0-5.114 6.24C.83 13.986.202 16.783.202 19.918c0 3.135.58 5.645 1.738 7.927a21.047 21.047 0 0 0 4.503 5.985c1.84 1.706 3.92 3.222 6.24 4.551 2.317 1.33 4.591 2.629 6.854 3.836 3.122 1.665 5.848 3.122 8.133 4.451 2.285 1.33 4.142 2.645 5.574 3.939 1.432 1.297 2.507 2.694 3.221 4.194.718 1.5 1.075 3.24 1.075 5.216 0 4.297-1.432 7.537-4.296 9.72-2.864 2.181-6.649 3.272-11.354 3.272-7.396.217-14.62-2.463-19.34-7.039L.202 68.485c5.399 5.315 13.653 8.433 21.582 8.106 3.48 0 6.768-.46 9.873-1.38 3.103-.921 5.78-2.286 8.03-4.091 2.25-1.806 4.042-4.059 5.371-6.752 1.33-2.694 1.995-5.78 1.995-9.259 0-2.797-.444-5.217-1.329-7.263-.888-2.047-2.217-3.904-3.99-5.574ZM115.595 35.774l-1.635 2.659h-.615l1.944-14.424h-9.922v51.147h16.571v-3.273H115.8V41.706c.545-1.294 1.178-2.42 1.893-3.376a15.546 15.546 0 0 1 2.404-2.558h13.706V24.009c-3.819.682-7.298 2.098-10.433 4.245-3.138 2.15-5.729 4.653-7.775 7.518v.002ZM150.428 24.011h-10.436V75.16h16.574v-3.273h-6.138V24.01ZM150.426 1.506h-10.434v10.442h10.434V1.506ZM88.74 65.031c-2.73 2.114-5.9 3.173-9.514 3.173-2.659 0-5.014-.563-7.058-1.69a14.974 14.974 0 0 1-5.114-4.602c-1.364-1.944-2.404-4.26-3.118-6.954-.718-2.694-1.075-5.61-1.075-8.747v-1.535h34.677c0-3.136-.48-6.07-1.432-8.799-.956-2.726-2.337-5.062-4.143-7.006-1.808-1.944-4.006-3.479-6.597-4.602-2.594-1.127-5.49-1.687-8.696-1.687-3.205 0-6.359.715-9.258 2.15-2.9 1.432-5.423 3.41-7.57 5.934-2.15 2.523-3.852 5.509-5.114 8.95-1.261 3.443-1.892 7.176-1.892 11.202 0 3.614.512 6.99 1.535 10.128s2.507 5.866 4.45 8.184c1.945 2.32 4.349 4.145 7.213 5.474 2.864 1.329 6.102 1.995 9.719 1.995 2.864 0 5.487-.53 7.878-1.587a22.297 22.297 0 0 0 6.343-4.193c1.84-1.738 3.427-3.785 4.756-6.137 1.33-2.353 1.887-3.303 2.707-5.826l-2.867-1.23c-1.234 2.89-3.175 5.364-5.823 7.416l-.008-.011ZM67.36 30.609c2.182-2.967 5.114-4.45 8.799-4.45 3.34 0 5.796 1.466 7.363 4.398 1.568 2.932 2.388 6.481 2.456 10.64H63.167c.614-4.09 2.011-7.621 4.193-10.588ZM172.99 71.883h6.129v3.276h-16.57V20.903c0-6.278 1.859-11.735 5.579-15.25C171.848 2.14 176.472.28 182 .075v11.874h-14.741v1.229c0 2.732.769 5.715 2.304 7.762 1.535 2.046 3.804 3.07 6.806 3.07h5.617v4.737h-8.993V71.88l-.003.003Z'

LOGO = (
    '<svg class="logo" fill="currentColor" xmlns="http://www.w3.org/2000/svg" '
    'viewBox="0 0 182 77" role="img" aria-label="Serif Biomedicines">'
    '<path d="' + LOGO_PATH + '"/></svg>'
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


# The exports a month needs, in the order Serif pulls them, and what each one feeds.
MONTHLY_EXPORTS = [
    ("netsuite_gl", "NetSuite Custom General Ledger saved search", "Every check"),
    ("coupa", "Coupa PO line report", "PO accounts, accruals and requesters"),
    ("forecast", "Rolling forecast, the month's cut", "Forecast vs. Actual"),
    ("plan", "Rolling forecast, the plan", "Actual vs. plan and planned coding"),
    ("hris_roster", "UKG roster", "Requester departments, names and pay"),
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
