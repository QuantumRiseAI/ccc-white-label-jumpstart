# P&L Flux: How to Run

Three commands. The engine does the arithmetic, the schedules lay it out, and you and
Claude write the commentary.

## The Rule That Matters

**Claude never computes a variance.** The engine is deterministic, same inputs, same
numbers, every time. Claude's job is to run it and explain what moved and why. A variance
an LLM computes will not reproduce next month, which defeats the point.

Commentary is the model's work. Arithmetic is not.

## Run It

Every input is an export exactly as its system writes it. Nothing is sliced, converted
or summarized first: the scripts read the exports and take the months they need in memory.

From this project folder, for a close of Sep 2026, first tie the ledger to NetSuite's Income
Statement, account by account, for the month and the month before:

```sh
python3 serif_sources.py tie --period "Sep 2026" --prior \
  --gl netsuite_gl_* \
  --income-statement netsuite_income_statement_by_*
```

It prints that every account ties, or each account that does not, with the month, both figures
and the difference, and exits 2. A failed tie stops the close there: export the GL and the
Income Statement again. Then:

```sh
# Leave out --forecast when the month has no cut of its own (see Each Month).
python3 serif_uc2_flux.py --period "Sep 2026" \
  --gl       netsuite_gl_* \
  --coupa    coupa_po_lines_*.csv \
  --forecast serif_rolling_forecast_2026-09.xlsx \
  --plan     serif_rolling_forecast_2026-08.xlsx --plan-vintage 2026-06 \
  --pending  . \
  --out      out
```

* `--gl` takes one NetSuite Custom General Ledger export or several. Together they hold the
  month and the month before; the same month last year and the six months before feed the
  prior-year column, the billing-pattern accrual, the prepaid and vendor tests and the
  three-month trend. A month in two exports is refused.
* `--forecast` is the workbook FP&A saved after the month closed. Its current cut holds the
  month's actuals, so comparing it with the ledger is a reconciliation, F5.MODEL_TIE.
  Without it, that check does not run.
* `--plan` is the workbook whose prior cut is the plan; `--plan-vintage` names that cut.
  Without it, Actual vs. Budget does not run.

```sh
python3 serif_views.py out/sep2026/run.json \
  --gl     netsuite_gl_* \
  --plan   serif_rolling_forecast_2026-08.xlsx --plan-vintage 2026-06 \
  --coupa  coupa_po_lines_*.csv \
  --roster ukg_full_roster_*.csv \
  --balance-sheet netsuite_balance_sheet_*.xls \
  --keep-names
```

```sh
python3 build_pages.py --only flux --flux-run out/sep2026/run.json \
  --gl netsuite_gl_* \
  --income-statement netsuite_income_statement_by_* \
  --netsuite-ref netsuite_ref_*.csv --out out/sep2026
```

To carry the GL Coding Review's booked corrections into Actual vs. Actual (MoM), add the coding
run and its decision record to the build:
`--coding-run <coding run.json> --coding-record <coding decision record .json>`. Each account
shows the correction, the adjusted movement, and flags on the adjusted figure. A fix marked
Edited Manually in NetSuite counts as a correction, named apart, when the flux reads the coding run's own
GL export; on a later export, which may already hold the edit, it is left out and the run log
says so. Open coding findings are noted on the affected row, never applied. A coding `drafts.json` goes in with
`--coding-drafts`, so decisions on Journal Entries Claude drafted there apply too.

In the Claude Project, Claude then writes `drafts.json` and builds again with
`--drafts drafts.json`, which puts its drafts into the console beside the items they belong
to. The build checks each draft against the run and lists any it leaves out. The format is in
`PROJECT_INSTRUCTIONS.md`.

`serif_views.py` adds the schedules to the run artifact. It reads each input, lays it out
and decides nothing; rerunning it replaces what it added.

`--roster` reads the UKG roster for Payroll Analytics. With `--keep-names` the console keeps
names and pay, for the accounting team; without it, the schedules step withholds them.
`--balance-sheet` reads the NetSuite Balance Sheet report for Balance Sheet Flux and the
tie-outs, and `--income-statement` the Income Statement by month. The build ties the ledger to
it by account for the month and the month before, as the first command does, and stops when an
account does not tie; `--allow-tie-differences` builds anyway, with the differences at the top
of the Executive Overview. Without `--income-statement` the console says the ledger was not tied.

In a Claude Project every uploaded file sits at the top level, so all of these are bare
filenames. In the repo, `make build PERIOD=sep2026` runs the same commands from the packaged
Project folder on the exports in `inputs/sep2026/`.

The last command writes `out/sep2026/serif-pl-flux-sep2026-v2.1.0.html`, one self-contained
file that opens in any browser. The filename carries the period and the console version.
Inside, the **Run log** has a Build record listing the console, engine and ruleset versions,
the run id, and a fingerprint for every input file, so if a figure moves between two builds
you can see which layer changed.

## Requirements

Python 3.9 or newer. Nothing else. Check with `python3 --version`.

## Each Month

Serif sends these exports, uploaded as they are:

1. The NetSuite Custom General Ledger saved search, exported as `.xls` (an `.xlsx` saved
   from it also reads), named `netsuite_gl_<range>.xls`. Columns are found by name, so a
   search with columns added or moved reads the same. Exporting a month at a time keeps each file small: the
   month's own export is then the only new one.
   Claude can also pull the month through the NetSuite connector with `netsuite_gl_detail.sql`
   and `netsuite_income_statement.sql`; the scripts read the saved results as they are.
2. The Coupa PO line report with all available columns, for the calendar year, as `.csv`.
3. The rolling forecast workbook FP&A saved after the month closed, as `.xlsx`.
4. The newest UKG roster, as `.csv`.
5. The NetSuite Balance Sheet report with monthly columns, and the Income Statement by month,
   as `.xls`.

Open the close's chat, below, and ask: `Run the P&L flux for Sep 2026.`

## The Close in One Chat

Each close has one chat in the Project. Run the flux in it as often as the end of the close
needs, and start a new chat for the next month.

1. **Open the close's chat.** Start a new chat in the Project and rename it for the close,
   such as "September close". Attach the month's exports and ask:
   `Run the P&L flux for Sep 2026.`
2. **Work the console.** At the end of each session, save the decision record (**Save
   decision record** in Settings). The console keeps decisions and commentary against the run: in shared mode,
   in the artifact for everyone with access, and opened as a file, in your browser. The
   record is what carries them to the next run and into the close file.
3. **Run it again in the same chat**, for example on day 25 and day 30, as late bills and
   entries post. Attach the newest NetSuite export of the month and the decision record, and
   say when you last reviewed: `Run it again. Reviewed as of 28 Sep.` Claude says what is new
   since then, what changed, what is already decided and what no longer appears, such as an
   accrual whose invoice has posted. NetSuite is the record of what was fixed.
4. **Load the record** into the new console with **Load decision record** in Settings, or,
   in shared mode, **Bring in the earlier run's decisions**. A run on new exports opens with no
   decisions until you do. Each decision carries across to the same item, matched by what it
   is, and commentary carries across by account. Claude names the items that changed, so you
   can decide them again, and says where commentary explains a move that has since changed.
   Tell Claude when you have imported entries into NetSuite, so nothing is booked twice.
5. **Hand off in the chat.** At the end of the close, ask `Summarize the session.` Claude
   writes what was run, what is decided and what is left, the commentary still to write, the
   checks that did not run, and where the record is. Keep the decision record with the close
   file.
6. **Next month, a new chat.** A decision record loads only into a run of its own month.

Claude remembers what was said earlier in the chat, but not what you clicked in the console,
and the files an earlier run wrote may be gone from the chat days later. Attach the latest
decision record each time you ask for a rerun, a summary or an email.

### What to Ask

| Ask | What Claude does |
|---|---|
| `Run the P&L flux for Sep 2026.` | The first run of the close: lists the exports, runs the scripts, drafts, publishes the console |
| `Run it again. Reviewed as of 28 Sep.` | Runs on the newest exports and says what is new since that review |
| `Draft the commentary.` | Commentary for the accounts named, or every account still needing it, built into the console |
| `Redraft the executive summary.` | Rewrites the executive summary on the Executive Overview from the commentary you have explained |
| `Draft the follow-up email.` | One email per department from the questions in your notes, such as accrual confirmations, for you to send |
| `Build the NetSuite import.` | Puts every entry you want on Adjustments, then checks the **Export to NetSuite, CSV** you export, with its support file. A person imports it. |
| `Draft the forecast revisions.` | The changes to the rolling forecast a finding calls for, with who approves them |
| `Summarize the session.` | The hand-off: runs, decisions, commentary, what is left, checks not run, the flux pack |
| `List the follow-ups.` | A checklist of everything waiting on someone, from your decision record, with an ID, owner, due date and status for each |
| `Check the posted entries.` | Compares what posted in NetSuite with the import you approved: Matches, Differences found or Not found, entry by entry |
| `What is the support for Journal Entry 1234?` | Finds the item, the decision, the note and who approved it, in the decision records you attach, or says there is none |
| `What came up again this month?` | With earlier months' decision records, lists what is corrected month after month, and a fix at the source |
| `Check this invoice against the SOW.` | Compares the bill with the contract terms you attach, proration included |
| Anything the console does not show | An ad hoc cut, labeled as one |

### Asking for Something New

The Project can answer what the console does not show, such as "External Research by vendor
for the last six months" or "Lab Supplies in Production, week by week". That is the reason
the flux runs in a Claude Project and not in an app. Claude computes the answer with code,
from the run or from the exports through the scripts' own readers, and labels it **Ad hoc,
not a finding**, with the run and the filter. It never adds a variance or a finding and never
settles an item. If it bears on an item, Claude names the item and you decide it. If you
want the same cut every month, say so: it may belong in the console as a check.

Other cuts to ask for: who requested the PO behind a line, and that person's department;
how a vendor was coded by department, program and project over the last year; what a
$5,000 threshold would catch next to the current one.

### Connectors

The NetSuite connector runs on a read-only role, and Claude uses only its read tools. Claude
never writes to NetSuite. Entries reach it through the NetSuite import, which a person
imports.

* Today the connector pulls the month's link IDs (below), and Claude can look up a document
  as NetSuite holds it now, for example to see that an accrual is posted.
* The month's GL and Income Statement can come from the connector: Claude runs
  `netsuite_gl_detail.sql` and `netsuite_income_statement.sql` and the scripts read the saved
  results, in place of uploading those two exports.
* Coupa has no connector yet. When it has one, it is read-only too.

To connect the NetSuite connector and set its tool permissions, see [`CONNECT-NETSUITE.md`](CONNECT-NETSUITE.md).

## Shared Mode

Claude publishes the console as a claude.ai Artifact in the close's chat. Published, the
console is in shared mode: decisions, commentary, notes, Journal Entry edits, the GAAP
checklist, the sign-off and the audit log are kept in the Artifact's database, and everyone you
share it with sees the same review as it changes. A banner under the bar says so: "Shared
review: decisions are visible to everyone with access to this page." It works only in the
published console. A console opened as a file keeps the review in that browser.

* **Publishing** happens in the Claude.ai chat, not in Claude Code. Claude publishes the
  console as built, with these capabilities:

  ```json
  {"db": {"rules": [{"path": "", "read": "view", "write": "interact"},
                    {"path": "signoff", "read": "view", "write": "admin"}]},
   "user": {"scopes": ["profile"]},
   "downloads": true}
  ```

* **Who can do what.** Contributors and up decide, write commentary and notes, and edit
  entries. Only Editors and up sign off. Viewers and Commenters read, and the console says their access
  does not let them change it.
* **Sharing** is yours. The artifact starts private to you; share it from the artifact menu,
  only with people inside the organization. Anyone given access sees every decision and
  note.
* **Who decided** is shown by name beside each decision. The shared state
  keeps a user id, never a name or an email.
* **Two people on one item.** When someone changes an item while you are changing it, theirs
  stands, and the console says so. Make your change again if it still stands.
* **The HTML is never edited by hand.** Shared state lives in the Artifact's database, not
  in `run.json` or the exports, and the run, the exports and the UKG roster never go into the
  artifact.
* **Each close.** One artifact per close month. A rerun in the same close is republished to
  the same artifact and starts fresh, as a new run; **Bring in the earlier run's decisions**
  in Settings carries them across. Next month is a new artifact with fresh state, and the
  earlier month's stays readable.
* **Downloads** ask you to confirm each save. The decision record holds the shared state.

### How to Test Shared Mode

1. Ask Claude to publish the console, and check the reply says shared mode is on.
2. Share the artifact with one colleague in the organization, as a Contributor.
3. Each of you opens it and checks for the shared mode banner.
4. Each of you writes commentary on a different account on Actual vs. Actual (MoM), and
   decides a different adjustment.
5. Confirm both appear on both screens, each adjustment named for who decided it.
6. Both of you decide the same adjustment at the same moment. One of you sees that the other
   changed it a moment ago, and the console shows the other's decision.
7. Save the decision record and check it holds both people's commentary.

## Links to NetSuite and Coupa

Serif's NetSuite is account 5602907, set as `NETSUITE_ACCOUNT` at the top of
`serif_sources.py`. It is one Flagship-wide instance, so one document number can belong to
bills of several Flagship companies; the links use internal IDs, never the number.

* **Document numbers** open the transaction in NetSuite. Without its internal ID a number
  is plain text: NetSuite's search results cannot be opened from a link.
* **Invoice** opens the bill's invoice in Coupa, and **PO** the line's PO.
* **PO numbers** in findings open the PO in Coupa. Its ID comes from the Coupa export's
  `PO ID`, or for a PO not in the export, from the number after `FL087`: every one of the
  3,664 POs in the 2026 export follows that rule.
* A number with two internal IDs, two invoices or two POs gets no link of that kind, so a
  link never opens the wrong record.

### Pulling the link IDs with the NetSuite connector

The IDs come from one SuiteQL query, `netsuite_link_ids.sql`, run through the NetSuite
connector in Serif's Claude instance:

1. Open a chat in Serif's instance, with the NetSuite connector on, and paste
   `netsuite_link_ids.sql` with the close month in place of `Sep 2026`. Ask Claude to run it,
   page through every row, and save the rows with code, exactly as returned, as
   `netsuite_link_ids_<month>.csv`.
2. Ask it for the row count, total debits, total credits and the number of distinct document
   numbers. Total debits must equal the GL export's for the month. For Aug 2026: 3,264 rows,
   $14,467,758.34 each side, 1,033 document numbers. The row count is not the export's
   (2,713 for Aug 2026): the query lists every posting line, 372 of them zero-amount lines on
   bills. The totals are what must agree.
3. Put the file with the month's exports and pass it to the schedules step:

```sh
python3 serif_views.py out/sep2026/run.json ... --netsuite-ids netsuite_link_ids_sep2026.csv
```

The file is read for links only, and no figure or finding comes from it. The schedules step
sets it aside, and says so, if its debits do not tie to the GL export for the month, and it
is listed in the Run log's Build record with its fingerprint. It carries no names.

Adding `Internal ID`, `custbody_coupa_transaction_url` and `custcol_coupa_po_num` to the
Custom General Ledger saved search, after Memo, gives the same links with no query. The
reader finds those columns by header.

## The Distinction That Matters Most

The engine reads two populations from each Coupa PO line:

| Population | Meaning | Accruable? |
|---|---|---|
| Received, not invoiced | goods received, not yet billed: `Received` less `Approved Invoiced`, pro-rated on `Line Total` | **Yes**, expense belongs in the period |
| Open commitment | ordered, nothing received yet, on an issued PO | **No**, disclosure only |

Aug 2026: $110,105 received-not-invoiced against $1,369,533 of open commitments.
Treating commitments as accruals would overstate August by more than 12x.

The received-not-invoiced figure is a **floor**: PO lines carrying no quantity cannot be
pro-rated and read as zero. Say so when reporting it.

## Design

The console follows the Serif Brand Guide on Brandpad (brandpad.io/serif), through the
tokens in `design-system/tokens.css` in the repo, carried in `serif_design.py`. The page is
Light Gray, cards are white, and the top bar is Dark Gray with the wordmark in White. Text is
Dark Gray, secondary text is Mid Gray, and rules are Warm Gray.

Red marks what needs action: an item over the threshold, the current page, the one
primary button. It never fills behind text. Where red is text it is a darker red,
`#c72e00`, which passes WCAG AA on white. The one other color the palette does not name is
`#d6d6d4`, for rules and hover fills on a white card.

Everything is in sentence case. Cards have soft corners and no borders or shadows, and
buttons are pills.

Headlines and all text are set in Denim. Eliza appears only as a short highlight in a
headline. Denim and Eliza are licensed and are
not redistributed, so `serif_fonts.py` inlines open-licensed stand-ins: Figtree for Denim
at `size-adjust: 96%` and PT Serif for Eliza at `104%`. After those come the alternatives
the brand names, Helvetica or Arial and Georgia. If `serif_fonts.py` is missing, the
console renders in those.

## Working the Console

The HTML is a working surface, not a report, laid out as the controller's August flux pack.
The bar holds three section titles; clicking one opens its pages in a bar under the header,
each with what is left on it. Run log and Settings are the icons at the right.

* **Executive Overview**: total operating expense, the adjustments still to decide, cash and headcount, the tie to
  NetSuite's Income Statement (every account for the month and the month before, or the ones
  that differ), the cards,
  the executive summary Claude drafts (**Accept**, or **Edit** to change it), the net loss
  bridge from the prior month (hover a bar for its figures), and the close
  checklist: each page, what is open on it and what that is worth. A line of the checklist
  opens its page.
* **Analysis**: Actual vs. Actual (MoM, with a YoY tab), Actual vs. Budget, By Department
  (MoM), and Payroll Analytics.
* **Close Workflow**: Balance Sheet Flux, Adjustments, and SOX & GAAP.

### Commentary

Commentary is the deliverable. A line at or over the threshold is marked Review and needs
commentary; the Review Checklist counts it open until it has some. Actual vs. Actual, Actual
vs. Budget, By Department and Balance Sheet Flux each take commentary on their lines. A draft
from Claude sits on its line with **Accept**, which copies it into the field, and **Edit**, which
copies it to change; a long draft shows its first lines, with Show all. Written commentary, the
summary and every note are saved with **Save** (or Cmd+Enter) and then read as finished text, with
who saved them and when; until then they are marked Not saved. Edit opens a saved note again, and
Cancel brings back what was saved. A line's commentary counts as written once it is saved. The review threshold shows beside the
title of each page that applies it; click its value to change it, and Reset returns the default.

**Export flux pack**, on the Executive Summary and the **Sign-Off & Export** card at the foot of SOX & GAAP, saves the close as a read-only
HTML file to hand on: Final, or Draft with what is still open; the saved executive summary; Actual vs.
Actual with each line's saved commentary; the adjustments and their decisions; the Journal Entries
for the import; and the sign-offs. Only saved writing goes in. **Commentary, CSV** saves the
commentary alone, for Excel.

Actual vs. Actual (MoM) also shows each account's average over the 3 and 6 months before.
By Department ends with **Credits in Expense Accounts**: every account and department whose
month or year to date nets below zero, with the largest credit lines and a commentary field.

### Payroll Analytics

Each department's GL salary, bonus, benefits and payroll tax for the month against the UKG
roster: headcount, salaries, the theoretical monthly salary and payroll tax, and the bonus
pool at target. The roster itself is listed by department. **Bonus Accrual** compares the
month's GL bonus with the pool at target ÷ 12, in total only: the roster's departments are
not the ledger's. Payroll tax on the bonus needs the payroll register.

### Adjustments

* **Section A, accounting adjustments**: every proposed Journal Entry, with its P&L and
  balance sheet impact, the evidence and the policy. The entry is filled in and editable:
  **Add to NetSuite CSV** books it as proposed and **Reject** leaves the ledger as it is; the
  buttons sit under the card's folds, and the card opens folded to its header. There is no
  Modify button: editing any account, department, Project, Program, Vendor, Coupa PO or amount
  marks it **Added to NetSuite CSV, edited**, which needs a note. The
  entry shows whether it balances; **Reset** brings back the proposal. Entries Claude drafted are
  here too. Both sides of an entry carry the Project and Program of the bill it corrects; an
  accrual from Coupa receipts or a reclass staged in the forecast has no bill behind it and
  leaves them to fill. A new balance sheet line (accounts 1xxxxxx to 3xxxxxx) takes the
  `Non-Specific` department, as does a line moved to one; only income statement lines carry one.
  The line that reverses the posted line keeps its department, so it nets the original.
* **Section B, forecast revisions**: where the month's forecast and the ledger differ.
  **Acknowledge & Flag** sends it to FP&A; **No Action** leaves it.
* **Section C, billed twice after a gap**: a vendor with two or more bills this month and none
  last month, billed in at least two of the four months before, whose month is at least 1.5
  times its usual month and at or over the threshold. It may be a missed accrual coming back,
  so the commentary says whether last month needed one.

**Export to NetSuite, CSV** holds every entry added to the NetSuite CSV (an edited one with a note), as edited: External ID, Subsidiary, Journal Date, Posting Period, Memo (with the note), Reversal Date, Account, Department, Project, Program, Name (the vendor, NetSuite's entity), Coupa PO Number, Debit, Credit and Line Memo, then, for the reviewer, Account Number, Department Name, Program Name and Reversing Entry. With NetSuite's lists, Subsidiary, Account, Department and Program carry NetSuite's internal IDs.
An entry out of balance or unchanged is left out. The same export saves the support file beside it (`...-support.html`): every entry in the import, by External ID, with its reason, the decision and who made it, the note and its lines, to attach in NetSuite with the import.

### SOX & GAAP

The tie-outs come first: the ledger against the Income Statement account by account, for the
month and the month before; GL debits against credits; operating expenses, total expense and net
income against the Income Statement; net income against the change in the Balance Sheet's Net
Income; the balance sheet balancing; and the month's change in cash, prepaid expenses, fixed
assets, accumulated depreciation, accounts payable and accrued expenses against GL activity.
Each shows both figures and Pass, or the difference. Then **Related Party: Flagship**, the
Flagship-named vendors and the journals whose memo names Flagship, by account over three
months; the intercompany policy is a draft. Then the GAAP checklist, the source data, and the
sign-off: Prepared by, Controller Review and CFO Approval.

### The Threshold

Variances are not graded high and medium. Each one is either at or over the amount that
earns commentary, or under it. The threshold defaults to **$10,000**, the pre-close adjustment
threshold, in dollars only, set in Settings. Change it and every page is marked again.

The engine reports every variance at or above **$2,500**, below which nothing is emitted.

### The Run Log

**Run log**, at the right of the bar, holds:
- **Exports this month:** each export the month needs and the file supplied for it.
- **What each check found:** every check, what it found and whether it ran.
- **Estimated cost per close run:** one run through the API on Claude Sonnet 5.5 at medium
  effort, at list price. A run in the Claude Project is covered by the Claude seat.
- **Inputs** and the **Build record:** the files, their fingerprints and the versions that
  made the console.

### The Record

Settings has the decision record:
- **Save decision record** saves the review as JSON, for the close file and the next run.
- **Load decision record** brings one into this console. It says what it brings in, what it
  keeps and what is not in this run, and asks first.
- **Bring in the earlier run's decisions**, in shared mode, does the same from the earlier run
  of this close.

Opened as a file, the review is saved in the browser against this run's id. A run on new
exports has a new id, so its console opens with no decisions until you load the record.

To compare a Project run with a local one, run
`python3 tools/compare_runs.py <project run.json> <local run.json>`.

## Reading the Output

1. **Tie-out**, debits equal credits on the GL detail. A fail means the export is
   incomplete; stop.
2. **Feeds absent**, each suppresses an analysis. The plan is the big one: without
   `--plan`, **no conclusion about budget performance can be drawn at all**.
3. **Findings**, Adjustments first, then variance review.

The Aug 2026 run is the reference: 99 findings, tie-out PASS: 39 accounts against the prior
month and 32 against plan, and 14 proposed Journal Entries on Adjustments, all in balance.
Every tie-out on SOX & GAAP passes. After any change to a script, run Aug 2026 again. If
its numbers move, the script changed what it finds; say so rather than explaining the new
figure as though it were expected.

## If Something Breaks

See [`WHEN-DATA-BREAKS.md`](WHEN-DATA-BREAKS.md). Short version: ask for the export again,
never reshape it.
