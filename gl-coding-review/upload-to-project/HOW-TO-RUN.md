# GL Coding Review: How to Run

Three commands. The engine finds the exceptions, the schedules lay the period out, and you
and Claude explain them.

## The Rule That Matters

**Claude never computes a finding.** The engine is deterministic and reproducible, same
inputs, same findings, every time. Claude's job is to run it, read the output, and explain
it in plain English. If Claude starts totting up ledger lines itself, something has gone
wrong: stop and run the script.

## Run It

Every input is an export exactly as its system writes it. Nothing is sliced, converted
or summarized first: the scripts read the exports and take the months they need in memory.

From this folder, for a close of Sep 2026:

```sh
python3 serif_uc1_engine.py --period "Sep 2026" \
  --gl      netsuite_gl_*.xls \
  --coupa   coupa_po_lines_2026.csv \
  --pending . \
  --out     out
```

`--gl` takes one NetSuite Custom General Ledger export or several. Together they hold the
month; the month before and the same month last year set each vendor's usual coding. A
month in two exports is refused.

```sh
python3 serif_views.py out/sep2026/run.json \
  --gl     netsuite_gl_*.xls \
  --plan   serif_rolling_forecast_2026-08.xlsx --plan-vintage 2026-06 \
  --coupa  coupa_po_lines_2026.csv \
  --roster ukg_full_roster_hrbp_<date>.csv
```

The schedules add the month two back, for the three months on Vendors. `--plan` is the
rolling forecast workbook whose prior cut is the plan; `--plan-vintage` names that cut.

```sh
python3 build_report.py out/sep2026/run.json
```

In the Claude Project, Claude then writes `drafts.json` and builds again with
`--drafts drafts.json`, which puts its drafts into the console beside the items they belong
to. The build checks each draft against the run and lists any it leaves out. The format is in
`PROJECT_INSTRUCTIONS.md`.

`serif_views.py` adds the schedules to the run artifact. It reads each input, lays it out
and decides nothing; rerunning it replaces what it added. Every input it reads is
fingerprinted in the Run log's Build record beside the engine's.

**The requester flag and Payroll vs. HRIS read the UKG roster**, `--roster`. The roster
carries names, email addresses and salaries; the schedules step reads it in memory and
withholds every employee name from the console. Without it, those two checks do not run.

**`serif_uc2_flux.py` sits beside `serif_views.py`.** The prepaid and capital flags on
Vendors are the flux engine's own rules, imported from it.

In a Claude Project every uploaded file sits at the top level, so all of these are bare
filenames. Running from this repo instead, prefix the data files with
`monthly-inputs/<period>/` and the scripts with `upload-to-project/`.

The last command writes `out/sep2026/serif-gl-coding-review-sep2026-v<version>.html`, one
self-contained file that opens in any browser. That is the deliverable. It fills the
window at any width and collapses to a single column on a narrow screen.

The console names itself with the period and its own version, so successive builds do
not overwrite each other:

```
serif-gl-coding-review-sep2026-v1.7.1.html
```

The filename carries the console version. Inside, the **Decisions** view has a Build
record listing the console, engine and ruleset versions, the run id, and a fingerprint
for every input file, so if a figure moves between two builds you can see which layer
changed.

## Requirements

Python 3.9 or newer. Nothing else, no `pip install`, no Node, no network.
Check with `python3 --version`.

If Python is missing, ask Claude to install it. On Windows that is usually
`winget install Python.Python.3.12`; on macOS, `xcode-select --install`.

## Each Month

Serif sends three exports, uploaded as they are:

1. The NetSuite Custom General Ledger saved search, exported as `.xls`, named
   `netsuite_gl_<range>.xls`. Exporting a month at a time keeps each file small: the
   month's own export is then the only new one.
2. The Coupa PO line report with all available columns, for the calendar year, as `.csv`.
   First column `PO Number (Header)`.
3. The newest UKG roster, as `.csv`.

The plan workbook stays in the Project until Serif sets a new plan. Open the close's chat,
below, and ask: `Run the GL coding review for Sep 2026.`

## The Close in One Chat

Each close has one chat in the Project. Run the review in it as often as the month needs,
and start a new chat for the next month.

1. **Open the close's chat.** Start a new chat in the Project and rename it for the close,
   such as "September close". Attach the month's exports and ask:
   `Run the GL coding review for Sep 2026.`
2. **Work the console.** At the end of each session, save **Decision record, JSON** on
   Decisions. The console keeps decisions against the run: in shared mode, in the artifact
   for everyone with access, and opened as a file, in your browser. The record is what
   carries them to the next run and into the close file.
3. **Run it again in the same chat**, for example on day 10, day 20 and day 30. Attach the
   newest NetSuite export of the month, the decision record and the console from your last
   run, and say when you last reviewed: `Run it again. Reviewed as of 20 Sep.` Claude says what is new since then, what
   changed, what is already decided and what no longer appears. A bill you fixed in NetSuite
   drops out once the export shows the fix: NetSuite is the record of what was fixed.
4. **Load the record** into the new console with **Load a decision record** on Decisions. A
   run on new exports opens with no decisions until you do. Each decision carries across to
   the same finding, matched by rule and title, and to the same vendor row. The console says
   how many it loaded and how many did not match, and Claude names the ones that will not,
   so you can decide them again.
   Tell Claude when you have imported entries into NetSuite, so nothing is booked twice.
5. **Hand off in the chat.** At the end of the close, ask `Summarize the session.` Claude
   writes what was run, what is decided and what is left, the checks that did not run, and
   where the record is. Save **Work paper, HTML** from Decisions and attach it to the entry in
   NetSuite.
6. **Next month, a new chat.** A decision record loads only into a run of its own month.

Claude remembers what was said earlier in the chat, but not what you clicked in the console,
and the files an earlier run wrote may be gone from the chat days later. The console from
your last run carries that run, so Claude can compare against it. Attach the latest decision
record each time you ask for a rerun or a hand-off, and the last console with a rerun.

### What to Ask

| Ask | What Claude does |
|---|---|
| `Run the GL coding review for Sep 2026.` | The first run of the close: lists the exports, runs the scripts, drafts, publishes the console |
| `Run it again. Reviewed as of 20 Sep.` | Runs on the newest exports and says what is new since that review |
| `Draft the questions email.` | One email per owner department, from the console's **Questions, CSV**, for you to send |
| `Build the NetSuite import.` | Puts every entry you want on Journal Entries, then checks the **NetSuite import, CSV** you export. A person imports it. |
| `Summarize the session.` | The hand-off: runs, decisions, what is left, checks not run, the work paper |
| Anything the console does not show | An ad hoc cut, labeled as one |

### Asking for Something New

The Project can answer what the console does not show, such as "Lab Supplies lines in
Chemistry over $5,000" or "Fisher Scientific by month this year". That is the reason the
review runs in a Claude Project and not in an app. Claude computes the answer with code, from
the run or from the exports through the scripts' own readers, and labels it **Ad hoc, not a
finding**, with the run and the filter. It never adds a finding and never settles an item. If
it bears on an item, Claude names the item and you decide it. Names stay withheld. If you
want the same cut every month, say so: it may belong in the console as a check.

### Connectors

The NetSuite connector runs on a read-only role, and Claude uses only its read tools. Claude
never writes to NetSuite. Entries reach it through the NetSuite import, which a person
imports.

* Today the connector pulls the month's link IDs (below), and Claude can look up a document
  as NetSuite holds it now, for example to see that a fix you made is there.
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
4. Each of you decides a different vendor row and writes a note on it.
5. Confirm both decisions and both notes appear on both screens, each named for who made it.
6. Both of you open the same row and change its note at the same moment. One of you sees
   that the other changed it a moment ago, and the console shows the other's version.
7. Save the decision record and check it holds both people's decisions.

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

The HTML is a working surface, not a report. A line is fine until something flags it.

The top bar holds **Overview**, **Review** and **Decisions**, then the review threshold and
the console version. The review pages are tabs under the Review title, each with what is
left on it.

* **Overview**: the close checklist first, one line per page with what is left and its value.
  Then the tick-and-tie: items and dollars over the threshold, settled and left to review,
  and under it, each as a percent of items and of value, footing to the total. Then the
  amount bands, which add up to the same whole, and where the open value sits.
* **Vendors**: every vendor billed this month.
* **Ledger checks**: posting lag and tax, one line per finding.
* **Payroll vs. HRIS**: salaries by department in the ledger against UKG's monthly pay for
  the people it places there. A department of fewer than three people shows headcount
  only.
* **Journal Entries**: every proposed correction as the entry that books it.
* **Decisions**: the record, the exports and the sign-off.
* **Run log**, at the right of the bar: the exports supplied, what each check found, the
  estimated cost of a run, the inputs and the build record.

### Vendors

One row per vendor: what was bought, where it was coded this month, and the month with
the two before it. Every account shows its code and name.

Each reason to look is a flag on the row: new vendor, coding changed, unusual
department, account differs from the Coupa PO, coded off plan, requested by another
department, may be prepaid, may be capital. A row needs a look when a flag clears the
threshold. Rows with no flag, and vendors billed earlier with nothing this month, are
folded; with them, the three months tie to the ledger.

Open a row for why each flag was raised, the vendor's codings (each account and department
over the three months), the planned coding, and its lines with the description first. The
row opens on its lines in one of two views: **Flagged** (the lines its flags are about, each
naming its flag) or **All**. Picking a coding in the coding table narrows the list to that
coding, shown as a chip that clears back to Flagged. A line with no description says to
open the invoice.

### Settling a Row

Each flagged row ends one of these ways:

* **Cleared**, with why the coding is right.
* **Follow up**, with the question for the owner department.
* **Entry booked**, with what the entry should do.
* **Fixed in NetSuite**, with what was changed there, for a bill the reviewer recoded
  directly while AP is open.
* **Reclass, rest cleared**: when one line on the row is miscoded and the rest are fine,
  **Reclass** on that line turns its account and department into choices from the chart,
  with the reason below. **Save** settles the row: the line is reclassed and the other
  lines are cleared. **Cancel** leaves the line as it was, and the undo button takes a saved
  reclass off so the row can be settled another way.

Cleared, Follow up and Fixed in NetSuite need a note. The outcome settles the engine findings
on the row: Entry booked marks their proposed entries for booking, Cleared declines them
with the same note, and Follow up leaves them open. Fixed in NetSuite and a
reclass also decline the engine's proposed entry, since the fix is made in NetSuite or by
the reviewer's reclass, and must not be booked twice. Only the current month gets an entry.

Findings on Ledger checks and Journal Entries end the same four ways. **Entry booked** is
offered only where the finding has a proposed entry. Cleared settles on the click; Follow up
and Fixed in NetSuite need a reason. Each
finding's **What to do** says which to choose.

**Edit** on a Journal Entry turns each line's account and department into choices from the
chart, and its amount into a field. A running total shows debits against credits, and **Save**
needs them equal and a reason. The edited entry is what goes into the NetSuite import, marked
as edited, and the decision log keeps the proposed and the booked lines side by side. The undo
button brings back the proposal. An accrual with no department says so, and the department is
set here.

Four exports:

* **Questions (CSV)**, on Vendors and Decisions: each question with its owner department,
  amount and flags.
* **Decision log (CSV)**, on Decisions: every finding and every settled row.
* **Proposed Journal Entries (CSV)**, on Decisions, each flagged for whether it still
  needs accountant ratification.
* **NetSuite import (CSV)**, on Journal Entries: every entry marked for booking and in
  balance, and every line reclass as its own entry (`RECLASS-001` and on): debit the new
  account, credit the posted one, dated the period end, the reason as the memo with the
  `| Mon'YY` tag, and the line's own document and description as the line memo.

### The Fix Threshold

Nothing is graded high, medium and low. An item is either at or over the amount at which
Serif corrects an exception, or under it. The threshold defaults to **$2,500**, set in the
top bar under **Review over**; `0` works everything.

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

The engine prints a load summary before any finding. Read it in this order:

1. **Tie-out.** Debits must equal credits. A fail halts the run, findings are not
   trustworthy until the ledger balances.
2. **Feeds absent.** Each one suppresses a test. A suppressed test is not a clean result,
   and the report says so on its own page.
3. **Findings**, grouped by the action they call for rather than by rule.

The Aug 2026 run is the reference: 56 findings (engine 0.2.1), tie-out PASS, 50 proposed Journal Entries,
all in balance. After any change to a script, run Aug 2026 again. If its numbers move, the
script changed what it finds; say so rather than explaining the new figure as though it
were expected.

## If Something Breaks

See [`WHEN-DATA-BREAKS.md`](WHEN-DATA-BREAKS.md): ask for the export again, never reshape it.

| Symptom | What it means |
|---|---|
| `Aug 2026 is not in the NetSuite exports supplied` | That month's export is missing. Ask for it. |
| Tie-out FAIL | The GL export is incomplete. Re-export; do not proceed. |
| `0 findings` | Almost certainly the wrong file. Check the period in the load summary. |
| A pending feed shows as absent | Expected. Its template exists but has no data yet. |

