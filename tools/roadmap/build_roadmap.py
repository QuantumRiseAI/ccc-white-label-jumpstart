"""Build the Serif AI Jumpstarts deployment brief: two printed pages for Scott.

    python3 tools/roadmap/build_roadmap.py [out.html]

What it says is written here; the layout uses Serif's design system
(src/serif_design.py and its inlined open fonts). Stdlib only.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
import serif_design as DS  # noqa: E402

DEFAULT_OUT = os.path.join(HERE, "..", "..", "..", "..", "6-deliverables",
                           "2026-10-09 - Serif AI Jumpstarts - Deployment Brief.html")

BODY = """
<header>
  <div class="mark">{logo}</div>
  <div>
    <p class="eyebrow">AI Jumpstarts &middot; GL Coding Review and P&amp;L Flux</p>
    <h1>Deploying the jumpstarts: what it would give Serif</h1>
    <p class="by">For Scott Keys &middot; October 9, 2026 &middot; Draft</p>
  </div>
</header>

<h2>Where things stand</h2>
<p>Both jumpstarts run as Claude Projects. Each close, the reviewer uploads the NetSuite, Coupa, UKG
and forecast exports; scripts build the review console; Claude drafts notes, commentary and Journal
Entries; the reviewer decides each item and downloads the approved entries as a NetSuite import.
The same exports always give the same findings. What a chat cannot do:</p>
<ul>
  <li><b>Remember across months.</b> Decisions live in a saved file or that month's shared console;
  a follow-up raised in September is not waiting in October.</li>
  <li><b>Fetch its own data or run on its own.</b> Every close starts with exports and uploads, and
  nothing runs until someone asks.</li>
  <li><b>Stay set up.</b> Each update is re-uploaded to each Project by hand.</li>
  <li><b>Check against NetSuite.</b> The import is checked to balance, not that every account is
  valid and the period open.</li>
</ul>

<h2>What deploying it would mean, and where</h2>
<p>The same scripts and console as a small web app: Serif's team signs in and the review is
waiting. Behind it, a database that remembers decisions and follow-ups between closes, a scheduled
job, read-only connections to NetSuite (and Coupa once Flagship IT's connector exists), and Claude,
called by the app to draft as it does today. The rules do not change, and people still approve
every entry.</p>
<p><b>Our view:</b> host it in Flagship's own cloud (Azure, if that is where Flagship runs), behind
the sign-in Serif already uses. The console carries ledger detail, names and pay; keeping it inside
Flagship's environment means no new vendor holds Serif's data and the security review is one
Flagship already runs. Vercel works too, but only on its Enterprise plan, which is where company
sign-in and audit logs are, and it adds a vendor. Flagship IT sets the timing: they have to agree to
host it, and they named separating each portfolio company's data as the blocker for anything hosted.</p>

<h2>Why it would be worth it</h2>
<ul class="two">
  <li><b>No monthly uploads.</b> The ledger read from NetSuite through the connector Serif already
  has; Coupa once its connector lands.</li>
  <li><b>Follow-ups that last.</b> A permanent ID, owner, status and links to related items, open
  across closes until fixed, closed against the entry that fixed it.</li>
  <li><b>One live review.</b> Preparer and reviewer on the same decisions, sign-off in the app, the
  invoice beside the line, Claude on hand for a question about any finding.</li>
  <li><b>Ready before anyone opens it.</b> Runs weekly, then each close day.</li>
  <li><b>Cleaner entries.</b> Coded like similar past entries, checked against NetSuite before upload,
  and reclasses reversed on every dimension the original hit.</li>
  <li><b>Fixed at the source.</b> Recurring issues flagged with what they have cost; each PO shows its
  requester's department; Coupa guides account choices.</li>
  <li><b>Bills checked against contracts.</b> Key terms per contract, so a bill that does not match
  its SOW is caught.</li>
  <li><b>An audit trail and room to grow.</b> Every change traced to its review and approver; later
  jumpstarts and other Flagship companies on the same build.</li>
</ul>

<h2 class="pb">Cost of ownership</h2>
<table>
<thead><tr><th></th><th>Claude Projects, ongoing</th><th>Hosted app in Azure</th></tr></thead>
<tbody>
<tr><td>Claude</td><td>Six Team seats, about $180 a month</td><td>Usage through the API, about $10 to $110 a month</td></tr>
<tr><td>Hosting</td><td>None</td><td>App, database, key store and monitoring, about $260 a month</td></tr>
<tr><td>Upkeep</td><td>About 4 hours a month: updates, file uploads, run checks</td><td>About 16 hours a month: changes, monitoring, patching</td></tr>
<tr class="tot"><td>Running cost</td><td>About $580 a month, $7,000 a year</td><td>About $1,870 a month, $22,500 a year</td></tr>
<tr><td>One-time</td><td>None</td><td>The build, scoped and estimated separately</td></tr>
</tbody></table>
<p class="note">List prices, October 2026, to confirm against Serif's and Flagship's contracts; upkeep at
$100 an hour; six users, three analyses a close day. Serif's Claude seats stay either way. Vercel's
hosting costs about the same, plus its Enterprise plan, which is priced by negotiation. Upkeep, not
hosting, is most of the difference, and it needs an owner: maintenance is outside the current SOW.
Against it sit the hours the deployment saves each close, and the decision to post entries to
NetSuite, which we would leave read-only until the checked import has run cleanly for a few closes.</p>

<h2>Next steps</h2>
<table class="steps">
<thead><tr><th>When</th><th>Step</th><th>Depends on</th></tr></thead>
<tbody>
<tr><td>October close</td><td>Run the Projects on the September close, with our support; agree the
  review thresholds.</td><td>Nothing</td></tr>
<tr><td>October</td><td>Decide with Flagship IT where it would be hosted, and whether the ledger comes
  through the NetSuite connector.</td><td>Flagship IT</td></tr>
<tr><td>November close</td><td>Pull the ledger through the connector, read-only, and compare it line
  by line with the saved search export.</td><td>The connector decision</td></tr>
<tr><td>Once hosting is agreed</td><td>Build the hosted review: shared decisions, follow-ups across
  closes, the checked NetSuite import.</td><td>Flagship IT; a scope and estimate</td></tr>
<tr><td>After a few closes</td><td>Scheduled runs; Coupa, the payroll register, Expensify and the
  sub-ledgers; posting approved entries.</td><td>Coupa connector; Serif's sign-off</td></tr>
</tbody></table>
<p class="note">Each step is scoped and estimated before it starts. Nothing past the October close is
committed.</p>
"""

CSS = r"""
*{box-sizing:border-box}
body{margin:0;background:var(--color-bg-primary);color:var(--color-fg-primary);font-family:var(--font-sans);
  font-size:15px;line-height:1.5}
.page{max-width:50rem;margin:var(--spacing-lg) auto;background:var(--color-stark);border-radius:var(--radius-sm);
  padding:var(--spacing-lg) var(--spacing-lg-xl)}
@media (max-width:40rem){.page{margin:0;border-radius:0;padding:var(--spacing-md) var(--spacing-sm)}}
header{display:flex;gap:var(--spacing-md);align-items:flex-start;padding-bottom:var(--spacing-sm);
  border-bottom:2px solid var(--color-fg-primary);margin-bottom:var(--spacing-sm)}
header .logo{width:4.2rem;height:auto;color:var(--color-dark-gray);margin-top:.35rem}
.eyebrow{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--color-fg-secondary);margin:0 0 .3em}
h1{font-family:var(--font-serif);font-weight:400;font-size:28px;line-height:1.15;margin:0}
.by{margin:.4em 0 0;font-size:13px;color:var(--color-fg-secondary)}
h2{font-size:15px;font-weight:600;margin:1.15em 0 .35em;padding-left:.6em;border-left:3px solid var(--color-red)}
p{margin:0 0 .55em}
ul{margin:.2em 0 .6em;padding-left:1.1em}
li{margin-bottom:.25em}
ul.two{display:grid;grid-template-columns:1fr 1fr;column-gap:var(--spacing-md);padding-left:1.1em}
@media (max-width:40rem){ul.two{grid-template-columns:1fr} header{flex-direction:column;gap:var(--spacing-xs)}}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:.3em 0 .5em}
th{text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--color-fg-secondary);
  font-weight:600;padding:.35em .5em;border-bottom:1px solid var(--color-fg-primary)}
td{padding:.45em .5em;border-bottom:1px solid var(--color-hairline);vertical-align:top}
td:first-child{width:26%}
td small{color:var(--color-fg-secondary)}
table.steps td:first-child{width:19%;font-weight:600}
tr.tot td{font-weight:600;border-bottom:1px solid var(--color-fg-primary)}
table.steps td:last-child{width:22%;color:var(--color-fg-secondary)}
.note{font-size:13px;color:var(--color-fg-secondary)}
.tw{overflow-x:auto}
@page{size:letter;margin:.5in .55in}
@media print{
  body{background:#fff;font-size:9.8pt}
  .page{margin:0;padding:0;max-width:none;border-radius:0}
  h1{font-size:19pt} table{font-size:9pt} th{font-size:8pt} .note{font-size:9pt}
  h2{break-after:avoid} h2.pb{break-before:page;margin-top:0} tr,li{break-inside:avoid}
}
"""


def page():
    body = BODY.replace("{logo}", DS.LOGO)
    body = body.replace("<table>", '<div class="tw"><table>').replace('<table class="steps">', '<div class="tw"><table class="steps">')
    body = body.replace("</table>", "</table></div>")
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Serif AI Jumpstarts Deployment Brief</title><style>' + DS.FONT_CSS + DS.TOKENS + CSS
            + '</style></head><body><main class="page">' + body + '</main></body></html>')


if __name__ == "__main__":
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(page())
    print("Wrote %s (%d KB)" % (out, os.path.getsize(out) // 1024))
