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
  --roster ukg_full_roster_hrbp_<date>.csv \
  --keep-names
```

The schedules add the month two back, for the three months on each vendor card. `--plan` is the
rolling forecast workbook whose prior cut is the plan; `--plan-vintage` names that cut.

```sh
python3 build_pages.py --only coding --coding-run out/sep2026/run.json \
  --gl netsuite_gl_*.xls --out out/sep2026
```

In the Claude Project, Claude then writes `drafts.json` and builds again with
`--drafts drafts.json`, which puts its drafts into the console beside the items they belong
to. The build checks each draft against the run and lists any it leaves out. The format is in
`PROJECT_INSTRUCTIONS.md`.

`serif_views.py` adds the schedules to the run artifact. It reads each input, lays it out
and decides nothing; rerunning it replaces what it added. Every input it reads is
fingerprinted in the Run log's Build record beside the engine's.

**The requester flag reads the UKG roster**, `--roster`. The roster carries names, email
addresses and salaries. With `--keep-names` the console keeps names, for the accounting team;
without it, the schedules step withholds them. Without the roster, the requester flag does not
run.

**`serif_uc2_flux.py` sits beside `serif_views.py`.** The CapEx and Prepaid flags are the
flux engine's own rules, imported from it.

In a Claude Project every uploaded file sits at the top level, so all of these are bare
filenames. In the repo, `make build PERIOD=sep2026` runs the same commands from the packaged
Project folder on the exports in `inputs/sep2026/`.

The last command writes `out/sep2026/serif-gl-coding-review-sep2026-v2.0.0.html`, one
self-contained file that opens in any browser. That is the deliverable.

The filename carries the period and the console version, so builds of different versions do
not overwrite each other. Inside, the **Run log** has a Build record listing the console,
engine and ruleset versions, the run id, and a fingerprint for every input file, so if a
figure moves between two builds you can see which layer changed.

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
2. **Work the console.** At the end of each session, save the decision record (**Save
   decision record** in Settings). The console keeps decisions against the run: in shared mode, in the artifact
   for everyone with access, and opened as a file, in your browser. The record is what
   carries them to the next run and into the close file.
3. **Run it again in the same chat**, for example on day 10, day 20 and day 30. Attach the
   newest NetSuite export of the month, the decision record and the console from your last
   run, and say when you last reviewed: `Run it again. Reviewed as of 20 Sep.` Claude says
   what is new since then, what changed, what is already decided and what no longer appears.
   A bill you fixed in NetSuite drops out once the export shows the fix: NetSuite is the
   record of what was fixed.
4. **Load the record** into the new console with **Load decision record** in Settings, or, in
   shared mode, **Bring in the earlier run's decisions**. A run on new exports opens with no
   decisions until you do. Each decision carries across to the same item, matched by what it
   is: the vendor, the accounts and the description. The console says what it brings in and
   what is not in this run, and Claude names the items that changed, so you can decide them
   again.
   Tell Claude when you have imported entries into NetSuite, so nothing is booked twice.
5. **Hand off in the chat.** At the end of the close, ask `Summarize the session.` Claude
   writes what was run, what is decided and what is left, the checks that did not run, and
   where the record is. Keep the decision record with the close file.
6. **Next month, a new chat.** A decision record loads only into a run of its own month.

Claude remembers what was said earlier in the chat, but not what you clicked in the console,
and the files an earlier run wrote may be gone from the chat days later. Attach the latest
decision record each time you ask for a rerun or a hand-off.

### What to Ask

| Ask | What Claude does |
|---|---|
| `Run the GL coding review for Sep 2026.` | The first run of the close: lists the exports, runs the scripts, drafts, publishes the console |
| `Run it again. Reviewed as of 20 Sep.` | Runs on the newest exports and says what is new since that review |
| `Draft the questions email.` | One email per owner department, from the questions in your decision record, for you to send |
| `Build the NetSuite import.` | Drafts any entry the console lacks, then checks the **Export to NetSuite, CSV** you download. A person imports it. |
| `Summarize the session.` | The hand-off: runs, decisions, what is left, checks not run, where the record is |
| `List the follow-ups.` | A checklist of everything waiting on someone, from your decision record, with an ID, owner, due date and status for each |
| `Check the posted entries.` | Compares what posted in NetSuite with the import you approved: Matches, Differences found or Not found, entry by entry |
| `What is the support for Journal Entry 1234?` | Finds the item, the decision, the note and who approved it, in the decision records you attach, or says there is none |
| `What came up again this month?` | With earlier months' decision records, lists what is corrected month after month, and a fix at the source |
| `Check this invoice against the SOW.` | Compares the bill with the contract terms you attach, proration included |
| Anything the console does not show | An ad hoc cut, labeled as one |

### Asking for Something New

The Project can answer what the console does not show, such as "Lab Supplies lines in
Chemistry over $5,000" or "Fisher Scientific by month this year". That is the reason the
review runs in a Claude Project and not in an app. Claude computes the answer with code, from
the run or from the exports through the scripts' own readers, and labels it **Ad hoc, not a
finding**, with the run and the filter. It never adds a finding and never settles an item. If
it bears on an item, Claude names the item and you decide it. If you want the same cut every
month, say so: it may belong in the console as a check.

Other cuts to ask for: who requested the PO behind a line, and that person's department;
how a vendor was coded by department, program and project over the last year; what a
$5,000 threshold would catch next to the current one.

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
console is in shared mode: decisions, notes, Journal Entry edits, the sign-off and the audit
log are kept in the Artifact's database, and everyone you share it with sees the same review
as it changes. A banner under the bar says so: "Shared review: decisions are visible to
everyone with access to this page." It works only in the published console. A console opened
as a file keeps the review in that browser.

* **Publishing** happens in the Claude.ai chat, not in Claude Code. Claude publishes the
  console as built, with these capabilities:

  ```json
  {"db": {"rules": [{"path": "", "read": "view", "write": "interact"},
                    {"path": "signoff", "read": "view", "write": "admin"}]},
   "user": {"scopes": ["profile"]},
   "downloads": true}
  ```

* **Who can do what.** Contributors and up decide, write notes and edit entries. Only Editors
  and up sign off. Viewers and Commenters read, and the console says their access
  does not let them change it.
* **Sharing** is yours. The artifact starts private to you; share it from the artifact menu,
  only with people inside the organization. Anyone given access sees every decision and
  note.
* **Who decided** is shown by name beside each decision and in the Audit Log. The shared state
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
4. Each of you decides a different flag and writes a note on it.
5. Confirm both decisions and both notes appear on both screens, each named for who made it.
6. Both of you decide the same flag at the same moment. One of you sees
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

The HTML is a working surface, not a report, laid out as the controller's August GL review.
The bar holds four section titles; clicking one opens its pages beside it, each with what is
left on it. Run log and Settings are the icons at the right.

* **Overview**: total period spend, the flags and their value as a share of spend, clean
  vendors, how many flags are resolved, and the close checklist: each page, what is open on it
  and what that is worth. A line of the checklist opens its page.
* **Review**: CapEx Flags, Prepaid Flags, and Dept & Entity.
* **Transparency**: Reviewed & Cleared, and New This Period.
* **Documentation**: Audit Log, SOX Documentation, and Export.

### A Card

Every flag and vendor is a card: its current coding (and the recommended one, on a flag), the
document with its NetSuite and Coupa links, the vendor's last three months by account and
department with the line descriptions, and its lines. Every account number shows its name. An
item at or over the threshold is marked Review.

### CapEx and Prepaid, Both Directions

Each page starts with the expense lines that may be capital or prepaid, then lists this
month's bills posted to fixed-asset (15xxxxx) or prepaid (13xxxxx) accounts. A bill there is
confirmed (it stays on the balance sheet) or recoded to expense, with a Journal Entry filled in
from the vendor's usual expense account and department.

### Settling an Item

* **A flag** (CapEx, Prepaid, Dept & Entity) shows its Journal Entry, filled in. **Approve
  Recode** books it as proposed. **Reject** leaves the coding as it is. Editing any account,
  department or amount marks it **Modified**, which needs a note. The entry shows whether it
  balances; **Reset** brings back the proposal.
* **A vendor** on Reviewed & Cleared or New This Period is **confirmed**, or **recoded**: the
  Journal Entry opens, filled in with its coding, to edit, with a note. A confirmed vendor
  folds to its name; click the name to open it again.

Reviewed & Cleared holds the vendors no check flagged. Each card says which checks it passed:
coded as in the two months before, account matching its Coupa PO, not a prepaid or capital
purchase, and coded as planned. A check with nothing to compare against says so (no bills in
the two months before, no Coupa PO, no plan line) rather than passing. Confirm each vendor, or
recode it if the coding is wrong, starting with those at $2,500 or more.

A draft from Claude sits on its card with **Use this**, which copies the note and sets the
recommended decision. Only the current month gets an entry.

### Export

**Export to NetSuite, CSV** on Documentation > Export holds every entry approved, modified or
recoded with a note, as edited: External ID, Date, Account, Department, Debit, Credit and Memo,
with the note in the memo. An entry out of balance, unchanged, or missing its note is left out,
and the Export page shows each entry's status.

### The Threshold

Nothing is graded high, medium and low. An item is either at or over the amount at which
Serif corrects an exception, or under it. The threshold defaults to **$2,500**, set in
Settings.

### The Run Log

**Run log**, at the right of the bar, holds:
- **Exports this month:** each export the month needs and the file supplied for it.
- **What each check found:** every check, what it found and whether it ran.
- **Estimated cost per close run:** one run through the API on Claude Sonnet at medium
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

Items match by what they are (vendor, accounts and description), so a decision carries to the
same item in a later run.

To compare a Project run with a local one, run
`python3 tools/compare_runs.py <project run.json> <local run.json>`.

## Reading the Output

The engine prints a load summary before any finding. Read it in this order:

1. **Tie-out.** Debits must equal credits. A fail halts the run, findings are not
   trustworthy until the ledger balances.
2. **Feeds absent.** Each one suppresses a test. A suppressed test is not a clean result,
   and the report says so on its own page.
3. **Findings**, grouped by the action they call for rather than by rule.

The Aug 2026 run is the reference: 56 findings (engine 0.2.4), tie-out PASS, 50 proposed Journal Entries,
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

## Accepted Exceptions

To stop a vendor being flagged, add a row to `accepted_exceptions.csv` (`vendor`, `account`, `reason`,
`approved_by`, `approved_on`; `account` may be blank for every account of that vendor) and upload it
with the other files. Save it as CSV (UTF-8 or Excel's Comma delimited). It is data, not a rule change,
and it covers only the department and account checks (`T1`, `T4`), not posting lag or tax. Matching
findings are kept and counted, marked excepted with the reason, and listed under Accepted Exceptions on
the Dept & Entity page. A row missing `vendor`, `reason` or `approved_by`, or with shifted columns, is
not applied; rejected rows (with their line numbers), rows that match nothing and an unreadable file are
printed in the load summary and shown on that page. The file is hashed into the run manifest when it has
rows; absent or header-only is recorded as such.

