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

From this project folder, for a close of Sep 2026:

```sh
python3 serif_uc2_flux.py --period "Sep 2026" \
  --gl       netsuite_gl_*.xls \
  --coupa    coupa_po_lines_2026.csv \
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
  --gl     netsuite_gl_*.xls \
  --plan   serif_rolling_forecast_2026-08.xlsx --plan-vintage 2026-06 \
  --coupa  coupa_po_lines_2026.csv \
  --roster ukg_full_roster_hrbp_<date>.csv
```

```sh
python3 build_report.py out/sep2026/run.json
```

In the Claude Project, Claude then writes `drafts.json` and builds again with
`--drafts drafts.json`, which puts its drafts into the console beside the items they belong
to. The build checks each draft against the run and lists any it leaves out. The format is in
`PROJECT_INSTRUCTIONS.md`.

`serif_views.py` adds the schedules to the run artifact. It reads each input, lays it out
and decides nothing; rerunning it replaces what it added.

`--roster` reads the UKG roster in memory so that employee names in ledger lines are
withheld from the console.

In a Claude Project every uploaded file sits at the top level, so all of these are bare
filenames. Running from this repo instead, prefix the data files with
`monthly-inputs/<period>/` and the scripts with `upload-to-project/`.

The console names itself with the period and its own version, so successive builds do
not overwrite each other:

```
serif-pl-flux-sep2026-v1.7.1.html
```

The filename carries the console version. Inside, the **Decisions** view has a Build
record listing the console, engine and ruleset versions, the run id, and a fingerprint
for every input file, so if a figure moves between two builds you can see which layer
changed.

## Requirements

Python 3.9 or newer. Nothing else. Check with `python3 --version`.

## Each Month

Serif sends four exports, uploaded as they are:

1. The NetSuite Custom General Ledger saved search, exported as `.xls`, named
   `netsuite_gl_<range>.xls`. Exporting a month at a time keeps each file small: the
   month's own export is then the only new one.
2. The Coupa PO line report with all available columns, for the calendar year, as `.csv`.
3. The rolling forecast workbook FP&A saved after the month closed, as `.xlsx`.
4. The newest UKG roster, as `.csv`.

Open the close's chat, below, and ask: `Run the P&L flux for Sep 2026.`

## The Close in One Chat

Each close has one chat in the Project. Run the flux in it as often as the end of the close
needs, and start a new chat for the next month.

1. **Open the close's chat.** Start a new chat in the Project and rename it for the close,
   such as "September close". Attach the month's exports and ask:
   `Run the P&L flux for Sep 2026.`
2. **Work the console.** At the end of each session, save **Decision record, JSON** on
   Decisions. The console keeps decisions and commentary against the run: in shared mode,
   in the artifact for everyone with access, and opened as a file, in your browser. The
   record is what carries them to the next run and into the close file.
3. **Run it again in the same chat**, for example on day 25 and day 30, as late bills and
   entries post. Attach the newest NetSuite export of the month, the decision record and the
   console from your last run, and say when you last reviewed: `Run it again. Reviewed as of 28 Sep.` Claude says what is new
   since then, what changed, what is already decided and what no longer appears, such as an
   accrual whose invoice has posted. NetSuite is the record of what was fixed.
4. **Load the record** into the new console with **Load a decision record** on Decisions. A
   run on new exports opens with no decisions until you do. Each decision carries across to
   the same finding, matched by rule and title, and commentary carries across by account.
   Flux titles carry the amount, so a finding whose amount moved does not match: Claude names
   each one, so you can decide it again, and says where commentary explains a move that has
   since changed.
   Tell Claude when you have imported entries into NetSuite, so nothing is booked twice.
5. **Hand off in the chat.** At the end of the close, ask `Summarize the session.` Claude
   writes what was run, what is decided and what is left, the commentary still to write, the
   checks that did not run, and where the record is. Save **Work paper, HTML** from Decisions
   and attach it to the entry in NetSuite.
6. **Next month, a new chat.** A decision record loads only into a run of its own month.

Claude remembers what was said earlier in the chat, but not what you clicked in the console,
and the files an earlier run wrote may be gone from the chat days later. The console from
your last run carries that run, so Claude can compare against it. Attach the latest decision
record each time you ask for a rerun, a summary or an email, and the last console with a
rerun.

### What to Ask

| Ask | What Claude does |
|---|---|
| `Run the P&L flux for Sep 2026.` | The first run of the close: lists the exports, runs the scripts, drafts, publishes the console |
| `Run it again. Reviewed as of 28 Sep.` | Runs on the newest exports and says what is new since that review |
| `Draft the commentary.` | Commentary for the accounts named, or every account still needing it, built into the console |
| `Draft the leadership summary.` | A draft for the controller, in the chat, from the commentary you have explained |
| `Draft the follow-up email.` | One email per department from the items marked Follow up, such as accrual confirmations, for you to send |
| `Build the NetSuite import.` | Puts every entry you want on Journal Entries, then checks the **NetSuite import, CSV** you export. A person imports it. |
| `Draft the forecast revisions.` | The changes to the rolling forecast a finding calls for, with who approves them |
| `Summarize the session.` | The hand-off: runs, decisions, commentary, what is left, checks not run, the work paper |
| Anything the console does not show | An ad hoc cut, labeled as one |

### Asking for Something New

The Project can answer what the console does not show, such as "External Research by vendor
for the last six months" or "Lab Supplies in Production, week by week". That is the reason
the flux runs in a Claude Project and not in an app. Claude computes the answer with code,
from the run or from the exports through the scripts' own readers, and labels it **Ad hoc,
not a finding**, with the run and the filter. It never adds a variance or a finding and never
settles an item. If it bears on an item, Claude names the item and you decide it. Names stay
withheld. If you want the same cut every month, say so: it may belong in the console as a
check.

### Connectors

The NetSuite connector runs on a read-only role, and Claude uses only its read tools. Claude
never writes to NetSuite. Entries reach it through the NetSuite import, which a person
imports.

* Today the connector pulls the month's link IDs (below), and Claude can look up a document
  as NetSuite holds it now, for example to see that an accrual is posted.
* The month's GL still comes from the saved search export. Once the scripts read the
  connector's results, Claude pulls the month itself and the uploads stop. Until then,
  attach the exports.
* Coupa has no connector yet. When it has one, it is read-only too.

To connect the NetSuite connector and set its tool permissions, see [`CONNECT-NETSUITE.md`](CONNECT-NETSUITE.md).

## Shared Mode

Claude publishes the console as a claude.ai Artifact in the close's chat. Published, the
console is in shared mode: decisions, notes, Journal Entry edits, the upload record and the
sign-off are kept in the Artifact's database, and everyone you share it with sees the same
review as it changes. A banner at the top says so: "Shared mode: decisions are visible to
everyone with access to this page." It works only in the published console. A console opened
as a file keeps decisions in that browser, as before.

* **Publishing** happens in the Claude.ai chat, not in Claude Code. Claude publishes the
  console as built, with these capabilities:

  ```json
  {"db": {"rules": [{"path": "", "read": "view", "write": "interact"},
                    {"path": "signoff", "read": "view", "write": "admin"}]},
   "user": {"scopes": ["profile"]},
   "downloads": true}
  ```

* **Who can do what.** Contributors and up decide and write notes. Only Editors and up sign
  off and clear the review. Viewers and Commenters read, and the console says their access
  does not let them change it.
* **Sharing** is yours. The artifact starts private to you; share it from the artifact menu,
  only with people inside the organization. Anyone given access sees every decision and
  note.
* **Who decided** is shown by name beside each decision and on the sign-off. The shared state
  keeps a user id, never a name or an email.
* **Two people on one item.** When someone changes an item while you are changing it, theirs
  stands, and the console says so. Make your change again if it still stands.
* **The HTML is never edited by hand.** Shared state lives in the Artifact's database, not
  in `run.json` or the exports, and the run, the exports and the UKG roster never go into the
  artifact.
* **Each close.** One artifact per close month. A rerun in the same close is republished to
  the same artifact and starts fresh, as a new run; **Bring in the earlier run's decisions**
  on Decisions carries them across. Next month is a new artifact with fresh state, and the
  earlier month's stays readable.
* **Exports** ask you to confirm each save. The decision record and every export include the
  shared state.

### How to Test Shared Mode

1. Ask Claude to publish the console, and check the reply says shared mode is on.
2. Share the artifact with one colleague in the organization, as a Contributor.
3. Each of you opens it and checks for the shared mode banner.
4. Each of you writes commentary on a different account on the flux pack.
5. Confirm both notes appear on both screens, and on Decisions each is named for who wrote it.
6. Both of you change the same account's commentary at the same moment. One of you sees
   that the other changed it a moment ago, and the console shows the other's version.
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
tokens in `serif-design-system/tokens.css`. The page is
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

The HTML is a working surface, not a report. The top bar holds every page, the review
threshold and the console version:

* **Overview**: the close checklist first. Then the tick-and-tie: items and dollars over
  the threshold, settled and left to review, and under it, each as a percent of items and
  of value, footing to the total. Then the amount bands, which add up to the same whole,
  and where the open value sits.
* **Adjustments** (tabs): the forecast reconciliation, accruals, prepaids and capital,
  reclassifications, and the Journal Entries
* **Flux pack** (tabs): Actual vs. Actual and Actual vs. Budget, one line per P&L account
* **Decisions**: the log, the export buttons, and the sign-off block
* **Run log**, at the right of the bar: the exports supplied, what each check found, the
  estimated cost of a run, the inputs and the build record

### Adjustments, as Schedules

The accounting layer reads the way the close binder does: one line per item, in columns.

* **Forecast vs. Actual**, the reconciliation: account, department, ledger, model,
  difference, and what the model line is staged as. A model line with no vendor and no PO
  is marked as a manual overlay.
* **Accrual Proposals**, the accrual schedule in two parts: goods received in Coupa and not
  invoiced, then vendors that bill every month and billed nothing this month (the
  policy's billing-pattern method, for suppliers Coupa does not reach). Debit and credit
  account, department, amount, reversal date.
* **Prepaids and Capital**, charges over the $10,000 prepaid threshold that pay for future
  months, purchases on the accounts the asset policy names for capitalization review, and
  what was already billed straight to prepaid and fixed-asset accounts this month.
* **Reclassifications**, customer documents posted to expense, and journals that lost the
  vendor they used to carry, including prepaid releases.
* **Journal Entries**, every proposed correction as the entry that books it. Only entries
  that balance are listed. A reclass the forecast staged across two accounts becomes one
  entry, and deciding it decides both differences.

Click a row to open its evidence under it, with its outcomes and a field for the reason. It is the same decision wherever it is taken.

### The Flux Pack

One line per P&L account, the line commentary is written on. One commentary serves both
pages.

* **Actual vs. Actual** reads as three months, so a swing that reverses shows as one. The
  same month last year sits beside it for context; it does not need commentary of its own.
* **Actual vs. Budget** reads by account, or by department on the toggle above the table.
  Accounts the forecast does not plan are named once above the table.

Open an account for the drill-down: its departments, then what changed by vendor, then
the lines from both months. Select a department to narrow the changes; open a change for
its lines. **Draft commentary** writes the figures as a first sentence to edit.

### The Commentary Threshold

Variances are not graded high and medium. Each one is either at or over the amount that
earns commentary, or under it.

The threshold sits in the top bar, under **Review over**, and defaults to **$10,000**, the
pre-close adjustment threshold, in dollars only. An account needs commentary when its move
against the prior month or against plan reaches it. Change it and every page re-partitions. Overview's
**Items by amount** cuts the items into bands at the threshold presets, each with its count
and dollars, and clicking a band reviews from its lower edge up.

The engine reports every variance at or above **$2,500**, below which nothing is emitted.

### Deciding

Each adjustment ends as **Entry booked** (offered only where it has a proposed entry),
**Cleared**, **Follow up** or **Fixed in NetSuite**. Cleared settles on the click, with a reason
if you want one; Follow up and Fixed in NetSuite need a reason. Each adjustment's
**What to do** says which to choose.

**Edit** on a Journal Entry turns each line's account and department into choices from the
chart, and its amount into a field. A running total shows debits against credits, and **Save**
needs them equal and a reason. The edited entry is what goes into the NetSuite import, marked
as edited, and the decision log keeps the proposed and the booked lines side by side. The undo
button brings back the proposal. An accrual with no department says so, and the department is
set here.


On the flux pack, commentary is the deliverable. Every line over the threshold reads
**Needs commentary** until it is explained, and then **Explained**. The field grows with
what is typed.

Three exports:

* **Decision log (CSV)**, on Decisions: every finding with its verdict, rationale and
  timestamp. Outstanding items appear too, marked as such.
* **Proposed Journal Entries (CSV)**, on Decisions: items marked for booking and entries
  raised from the pack, each carrying a flag for whether it still needs accountant
  ratification.
* **NetSuite import (CSV)**, on Journal Entries: one row per line of every entry marked
  for booking and in balance.

Decisions are saved in the browser against this run's id. Some browsers refuse storage for
a file opened from disk; when that happens the console says so at the top of Review and
you should export before closing the tab. A run on new exports has a new id, so its console
opens with no decisions until you load the decision record.

### The Run Log

**Run log**, at the right of the bar, holds:
- **Exports this month:** each export the month needs and the file supplied for it.
- **What each check found:** every check, what it found and whether it ran.
- **Estimated cost per close run:** one run through the API on Claude Sonnet at medium
  effort, at list price, with each input it is built from. A run in the Claude Project is
  covered by the Claude seat.
- **Inputs** and the **Build record:** the files, their fingerprints and the versions that
  made the console.

### The Record

Decisions has the exports for the record:
- **Work paper, HTML** is the audit support to attach to the entry in NetSuite.
- **Decision record, JSON** saves the review. **Load a decision record** brings it into a
  later run of the same month. See The Close in One Chat.

**Clear all decisions** asks for "clear" to be typed first.

To compare a Project run with a local one, run
`python3 tools/compare_runs.py <project run.json> <local run.json>`.

## Reading the Output

1. **Tie-out**, debits equal credits on the GL detail. A fail means the export is
   incomplete; stop.
2. **Feeds absent**, each suppresses an analysis. The plan is the big one: without
   `--plan`, **no conclusion about budget performance can be drawn at all**.
3. **Findings**, Adjustments first, then variance review.

The Aug 2026 run is the reference: 99 findings, tie-out PASS. 28 sit in Adjustments and
71 in the flux pack: 39 accounts against the prior month and 32 against plan. The Journal
Entries page lists 14, all in balance. After any change to a script, run Aug 2026 again. If
its numbers move, the script changed what it finds; say so rather than explaining the new
figure as though it were expected.

## If Something Breaks

See [`WHEN-DATA-BREAKS.md`](WHEN-DATA-BREAKS.md). Short version: ask for the export again,
never reshape it.
