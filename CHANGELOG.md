# Changelog

Three things version independently. A reader comparing two outputs needs all three
to know why a number moved.

| What | Where it lives | Shown |
|---|---|---|
| **Console** | `build_report.py` → `CONSOLE_VERSION` | Run log, filename |
| **Engine** | each engine → `ENGINE_VERSION` | Run log |
| **Ruleset** | each engine → `RULESET_VERSION` | Run log |
| **The run** | `run_id` + a sha256 per input file | Run log |

If a figure changed between two builds, the Run log says which layer moved: a
different input fingerprint means the data changed, a different ruleset means the rules
did, a different console means only the presentation did.

Output files carry the console version in the name, so successive builds do not
silently overwrite each other:

```
serif-gl-coding-review-aug2026-v1.8.2.html
serif-pl-flux-aug2026-v1.8.2.html
```

## Bumping a version

* **Console**, any change a reviewer would notice: a view, the decision vocabulary,
  the layout. If the decision vocabulary changes, bump `STORE_VERSION` in the JS too,
  or decisions recorded under the old verbs are restored against actions that no
  longer exist.
* **Engine**, a change to how a run artifact is produced.
* **Ruleset**, a change to what the rules test or the thresholds they apply. This is
  the one an accountant cares about: a ruleset bump invalidates a prior sign-off.

---

## Unreleased: finding reference IDs (SERIF-145)

- **GL Coding Review**: each card's header starts with a reference ID, numbered by screen within
  the close: CAPEX, FA (booked to fixed assets), PREPAID, PPD (booked to prepaid), DEPT, DRAFT
  (Claude's drafted entries), CLEAR (Reviewed & Cleared) and NEW (New This Period), for example
  DEPT-01. Within a screen the largest amount is 01, and a tie goes by item id, so a rebuild of
  the same data numbers every card the same; a drafted entry takes a DRAFT number and moves no
  other. The IDs are per close; permanent IDs across closes stay on the roadmap (SERIF-128,
  SERIF-130). The page data carries them as `ref`, item id to ID.
- **Memo**: each proposed Journal Entry's Memo follows the Data Entry Policy with the card's ID in
  front, `DEPT-01 | Reclass VWR International LLC from 6607000 to 6410000 | Aug'26`, in the entry
  editor, the Export page, the NetSuite CSV (Memo and Line Memo) and the entries handed to the
  P&L Flux. The
  build's own memos had no `| Mon'YY`; they now end with the close month. NetSuite takes up to 999
  characters in a Memo; the build cuts a long description to keep every Memo and Line Memo within
  it. A reviewer's note added to the CSV Memo is not cut. Aug 2026: 105 cards, CAPEX 3,
  PREPAID 1, PPD 7, DEPT 53, CLEAR 24, NEW 17; the longest Memo is 118 characters.

## Unreleased: accepted exceptions (SERIF-64)

- **Accepted exceptions** (GL Coding Review): a reviewer-maintained `templates/accepted_exceptions.csv`
  (vendor, account, reason, approved_by, approved_on) is read by the coding engine as an input, hashed
  into the run manifest when it has rows. Matching department and account findings (T1, T4) are marked
  excepted, kept and counted, and listed with their reason on the Dept & Entity page; rejected and
  unmatched rows are shown there and in the load summary. Engine 0.2.4 (run.json gains `excepted`,
  `summary.excepted_*` and `manifest.exceptions`); no rule changes, so the ruleset version does not move.

## Unreleased: coding corrections in the P&L flux (SERIF-44)

- **P&L Flux with the GL Coding Review**: `build_pages.py --only flux` takes the coding run
  (`--coding-run`) and the coding decision record (`--coding-record`). Actual vs. Actual (MoM)
  shows each account's booked correction, the adjusted movement, and flags on the adjusted
  figure; open coding findings are noted on the affected row and never applied.

## Unreleased: Run log cost estimate

- The cost estimate prices Claude Sonnet 5.5 ($2 input, $0.20 cached, $10 output per million; was the Sonnet 4.6 $3 / $0.30 / $15) and assumes 500 tokens of output per script run (was 2,000); the scripts print at most about 300 tokens each. Aug 2026: coding about $0.62 (847K tokens), flux about $1.08 (1.77M tokens).

## Unreleased: Line Memo keeps the original date (SERIF-126)

- **Fix**: the coding build finished each proposed Journal Entry twice (once for the flux
  hand-off), and the second pass dropped the original transaction date from every Line Memo.
  Each entry is now finished once; 92 Line Memos carry the date again. The same second pass
  reset Claude-drafted reversing entries to Reversing N with no Reversal Date, and let the flux
  hand-off book an entry whose reversal date fell before its Journal Date; both now hold as the
  console does.
- **Docs**: the review corrects lines posted in the close period, so its corrections are
  in-period. An out-of-period adjustment (a line posted in a closed period) is drafted on
  request, dated in the close month, with the Memo naming the period, for the controller.

## Unreleased: Journal Entries from variances, NetSuite fields (SERIF-125, SERIF-126)

- **Propose entry** on each Actual vs. Actual (MoM) row (P&L Flux) opens an editable two-line
  Journal Entry that goes through the same approval gate and NetSuite CSV as the others; the NetSuite
  CSV and the entry editor now carry Subsidiary, Journal Date, Posting Period, Currency,
  Exchange Rate, Memo, Reversing Entry, Reversal Date and a Line Memo on each line. Entries are
  dated the last day of the close month, with the transaction date in the Line Memo.

## Unreleased: duplicate vendor records (SERIF-17)

- **GL Coding Review**: an explicit pair list, `VENDOR_PAIRS` in the engine's policy module,
  applied to the GL and Coupa vendor names before the vendor-pattern checks. Only "confirmed"
  pairs merge; Amazon Web Services and Amazon Capital Services are recorded as "apart"; the
  Thermo Fisher Scientific and Fisher Scientific pair is "proposed", so Aug 2026 findings are
  unchanged (the Fisher Scientific findings are real coding differences, not a duplicate
  record). A list that contradicts itself (a record confirmed into two names, or merges
  that would put an "apart" pair under one name) stops the run. Engine 0.2.3.

## Unreleased: item account drift (SERIF-26)

- **GL Coding Review**: `T4.ITEM_ACCOUNT_DRIFT` flags a Coupa PO line in the close month (by PO
  line date; later lines are never read) whose account differs from the account the same item
  had on earlier lines of the year. Item text is matched ignoring case and spacing; a tie in
  the history sets no expectation. The amount is that line's. It shows on Dept & Entity beside
  "Account vs. Coupa" with the supplier as the vendor; lines under the review threshold are
  a count and a total. Aug 2026: 3 cards ($35,435.15) and 220 lines under $2,500 ($29,409.46).
  Reported as not run when the Coupa export has no Item column. Engine 0.2.2, ruleset
  `2026.10-uc1-coding-only+coupa`, procurement rules 1.1.0. Its findings are numbered after the
  other findings, so no existing id moves.

## Unreleased: executive summary, payroll commentary, Project files (7 Oct)

- **Executive Summary** (P&L Flux, Executive Overview): Claude drafts it into `drafts.json`
  as `summary`, after the net loss bridge as in Chris's August report; the reviewer uses it
  and edits it in place. "Redraft the executive summary." rewrites it from the reviewed
  commentary. The GL coding review has none.
- **Commentary digs for the driver**: when `movers` does not explain a move, Claude reads
  the ledger lines, the Coupa lines and the UKG roster with code before calling a move
  unexplained. Payroll accounts are checked against the roster: hires by `Last Hire Date`,
  job changes by `Date In Job`, and department salary against the GL. The header-only payroll
  register and HRIS feeds no longer read as "no UKG data".
- **Project files**: both instructions say the scripts are always Project files, and Claude
  searches for one by name instead of telling the reviewer it is missing.

## Unreleased: checks from the reviewers' own work (AIJ-93)

The P&L Flux console adds what the August data supports from CK's manual review and Chris's
reports. Engines and ruleset are unchanged; everything is computed from the GL export in
`build_pages.py`. The console version is still 2.0.0 until a new one is minted.

- **Credits in expense accounts** (By Department): each account and department whose month or
  year to date nets below zero, with its largest credit lines and commentary. Aug 2026 has 12,
  mostly employee insurance contributions on 6104000.
- **Bonus accrual** (Payroll Analytics): the month's GL 6102000 against the pool at target ÷ 12,
  in total. Aug 2026: $132,181 against $125,344. Not by department, because the roster's
  departments are not the ledger's; the payroll tax piece needs the payroll register.
- **Billed twice after a gap** (Adjustments, Section C): two or more bills this month, none last
  month, billed in two of the four months before, at least 1.5 times the usual month and at or
  over the threshold. Aug 2026 has 4.
- **Related party: Flagship** (SOX & GAAP): Flagship-named vendors and journals, by account,
  over three months. Aug 2026: $430,605.
- **Trailing averages** (Actual vs. Actual, MoM): each account's 3- and 6-month averages.

Both consoles:

- **Reviewed & Cleared** (GL) says what was checked: each vendor lists the checks it passed and
  the ones that could not apply, and why. The Review and Routine tags are gone from it: nothing
  there was flagged, and $2,500 or more is a plain label. Account group headers are neutral.
- **A confirmed vendor folds** to its name; clicking the name opens and closes it.
- **Every account number shows its name**: in line tables, engine text, payroll labels, plan-only
  accounts and the Export page. Accounts the chart lacks take their name from the GL export or
  the Balance Sheet. `tests/audit_account_names.js`, run by `make test`, checks every page.
- **Navigation**: the open section is an outlined group, section titles carry a chevron and
  more space, and the bar is marked up for screen readers (expanded sections, the current
  page, each section's pages as a group).
- **Tabs** are folder tabs, the current one open into its panel, and are announced as tabs.
- **Tables** fit the card: headers wrap, so no table scrolls sideways at 1280px or wider.
  `tests/audit_table_width.js` checks it.

Not built, because the data does not support them: department-level bonus (the roster's
departments), the accrual roll-forward (the accruals log is not supplied), small amounts
capitalized below a threshold (Serif's asset policy sets none), reading prepaid terms from line
text (most lines carry none; the invoice is the source), and a prior-month forecast column
(the workbook holds the August cut and the June plan only).

---

## Console 2.0.0: 2026-10-06

The updated UI replaces the 1.8 console in both jumpstarts. It is laid out as Chris's August
reports, in Serif's design, and built by `build_pages.py` in each Project from that Project's
own run. Engine and ruleset versions are unchanged, and the runs are identical to the ones the
updated UI v1 read.

- **Pages:**
  - GL Coding Review: Overview; Review (CapEx Flags, Prepaid Flags, Dept & Entity);
    Transparency (Reviewed & Cleared, New This Period); Documentation (Audit Log, SOX
    Documentation, Export);
  - P&L Flux: Executive Overview; Analysis (Actual vs. Actual, MoM and YoY; Actual vs. Budget;
    By Department; Payroll Analytics); Close Workflow (Balance Sheet Flux, Adjustments, SOX &
    GAAP).
- **Carried over from 1.8.8:**
  - shared mode, as a claude.ai Artifact with the db, user and downloads capabilities:
    - every decision, note, entry edit, checklist mark, sign-off and audit log entry is its
      own document, written only when it changes;
    - a write reads the document again first, so a change made by someone else in the
      meantime stands and the reviewer is told;
    - who decided is kept as a user id and named on screen;
    - Viewers read only, and only Editors sign off (sign-off has its own `signoff/` root for
      the access rule);
    - a rerun registers as a new run, and **Bring in the earlier run's decisions** carries the
      earlier run's work across;
  - the decision record, saved and loaded from Settings, asking on the page before it loads;
  - the run log, the icon beside Settings: the exports, what each check found, the estimated
    cost of a run, the inputs and the build record;
  - Claude's drafts (`--drafts`), each beside its item with **Use this**:
    - commentary on Actual vs. Actual;
    - adjustment notes with a recommendation;
    - vendor notes on every card of the vendor;
    - drafted Journal Entries, on Adjustments (flux) and Dept & Entity (coding).

    A draft that does not match the run is left out and listed.
- **Item ids** are built from what the item is (vendor, accounts, description), so a decision
  matches the same item in a later run. Records from 1.8 do not load into 2.0.0.
- **The coding console reads only the coding run.** Its CapEx and Prepaid screens come from the
  flux engine's prepaid and capital rules, which `serif_views.py` already runs over the month
  for the vendor rows.
- **Not carried over from 1.8:**
  - the Follow up and Fixed in NetSuite outcomes, and line-level reclass;
  - the Questions, decision log and proposed-entries CSVs, and the work paper;
  - recording the NetSuite upload, and the Finish the close button;
  - the posting lag and tax findings, which are counted on the run log only.
- **Names and pay** are kept (`serif_views.py --keep-names`), for the accounting team.
- **Repo layout:** each file lives once.
  - `src/` holds the scripts, `projects/` what is particular to each Claude Project (with
    `projects/shared/` for the docs both carry), and `templates/` the feed templates.
  - `tools/package.py` (`make package`) assembles each Project's flat upload folder and zip in
    `out/dist/`. `tools/build.sh` (`make build`) runs both Projects' commands from those folders
    on `inputs/<period>/`, so what is tested is what is uploaded. `tests/test_console.js`
    (`make test`) tests the consoles, standalone and in shared mode.
  - `consoles/` holds the current console for each Project. Each version is a commit to it,
    tagged `console-v<version>`, from v1.8.3 on.
  - `serif_design.py` carries the design tokens, logo, fonts and the run log's cards.
    `build_report.py` and its tests are retired; they stay in Git history before 2.0.0.
  - The design system is in `design-system/`; the data manifest, internal notes and Chris's
    two August reports (`docs/spec/`) are in `docs/`.
  - The `gl-coding-review/`, `pl-flux/` and `updated-ui/` folders are gone: their upload
    folders are generated, and each close's exports go in one `inputs/<period>/`.

---

## Updated UI v1, Chris's 1 Oct comments: 2026-10-06

`updated-ui/build_pages.py`. The figures are unchanged; the runs are not rebuilt.

- **Journal Entries, filled in and editable:** every CapEx, Prepaid and Dept & Entity flag, and
  every flux adjustment, shows its proposed entry with the account, department, debit and credit
  editable. An edit marks the item Modified, which needs a note. On Reviewed & Cleared, New This
  Period and the booked lines, Recode opens the entry, filled in. The NetSuite CSV takes each
  entry as edited and leaves out any that is out of balance, unchanged or missing its note. The
  GL Export page shows each entry's status.
- **CapEx and Prepaid, both directions:** each page has its expense lines that may be capital or
  prepaid, then this month's bills posted to fixed-asset (15xxxxx) or prepaid (13xxxxx) accounts,
  to confirm or recode to expense. The recode is filled in with the vendor's usual expense account
  and department from the ledger. Aug 2026 has seven prepaid bills ($409,956.47) and no
  fixed-asset bills.
- **Vendor history:** every vendor card shows the vendor's last three months by account and
  department, with the amount and the line descriptions, from the GL export.
- **By department, then account:** Reviewed & Cleared and New This Period are grouped by the
  vendor's main department, then account.
- **Flux SOX tie-outs:** a Tie-Outs card on SOX & GAAP checks the ledger against the Income
  Statement by month and Balance Sheet reports: operating expenses, total expense, net income
  (Income Statement and the change in the Balance Sheet's Net Income), the balance sheet balancing,
  and the month's change in cash, prepaids, fixed assets, accumulated depreciation, AP and
  accruals against GL activity. All pass for Aug 2026. `--income-statement` takes the report; in
  the repo it is read from `pl-flux/monthly-inputs/<period>/`.
- **Resolved** on the GL Overview counts flags only.

---

## Console 1.8.8 UI update, views 1.6.4: 2026-10-06

A second layout of the same consoles, `build_report.py --layout ui-update`, written to
`...-ui-update.html`. The decisions, decision record, exports, sign-off and shared mode are the
same as the standard console's.

- **P&L Flux pages:**
  - Executive Overview: ten tiles (Total OpEx, Net Loss, YoY Net Loss, Adj Pending, R&D and G&A
    Spend, Interest Income, Total Headcount, Cash & Equiv. by bank account, Critical / Material
    Flags) and the Variance Waterfall, net loss month on month, with tooltips. Nothing else;
  - Actual vs. Actual (MoM);
  - Actual vs. Budget;
  - By Department (MoM), with the plan schedule below;
  - Payroll Analytics, with Payroll vs. HRIS below;
  - Balance Sheet Flux, with commentary on each line;
  - Adjustments: Section A holds the proposed entries and the lines without one, and Section B
    holds the forecast revisions;
  - SOX & GAAP: the finish step, source data, the tie-out, the policies applied, an AI
    disclosure and sign-off.
- **GL Coding Review pages:**
  - Overview;
  - CapEx Flags, Prepaid Flags, Dept & Entity (with the ledger checks), Reviewed & Cleared, and
    New This Period. The vendor schedule is split across these, with each vendor on one page;
  - Audit Log;
  - SOX Documentation;
  - Export to NetSuite, in the bar.
  - The ledger checks (posting lag and tax) are not in this layout.
- **The UI update's GL Overview:**
  - Total Flags, Flagged Amount (share of period spend) and Total period spend,
    with no Tick and tie;
  - the close checklist has one Status column, for example "3 open of 42" or "Done, 3 of 3",
    beside Value left.
- **Color:** red marks an unfavorable P&L move. Balance sheet moves over the threshold are
  bold, not red.
- **Moved to `updated-ui/` (v1):** the consoles are now built by `updated-ui/build_pages.py`
  from the runs that `updated-ui/build_runs.sh` writes to `updated-ui/runs/<period>/`. They are
  laid out as Chris's August reports, and are written to `updated-ui/out/<period>/` as
  `...-updated-ui-v1.html`. See `updated-ui/README.md`. The `--layout ui-update` option in
  `build_report.py` stays, but is no longer how they are built.
- **Views 1.6.4:**
  - `--balance-sheet` reads the NetSuite Balance Sheet report as NetSuite exports it
    (`serif_sources.read_balance_sheet`);
  - the flux run gains `dept_months`, `payroll` and Payroll vs. HRIS;
  - `--keep-names` keeps employee names and pay in the run and adds the roster to the payroll
    detail. The UI update is built with it.
- **Both layouts:**
  - Cleared settles on the click, and the row stops showing as open. A reason is optional.
    Follow up and Fixed in NetSuite still need one.
  - Schedules and the flux pack open with unflagged lines hidden, behind "Show unflagged
    lines".
  - A line that was flagged stays on screen once it is decided.
  - The switch is hidden where there are no unflagged lines.
  - Balance Sheet Flux has the same switch. A line is unflagged when its move is under the
    threshold and it has no commentary.
  - HOW-TO-RUN and PROJECT_INSTRUCTIONS say so.
- Apart from these, the standard consoles are unchanged. Their figures are unchanged, and the
  shared mode, record and run log tests pass.

## Console 1.8.8, shared mode: 2026-10-05

AIJ-116. Both consoles.

- **Shared mode.** Published as a claude.ai Artifact with `db` and `user`, the console keeps
  decisions, schedule rows, commentary, accepted drafts, raised entries, Journal Entry edits,
  the upload record and the sign-off in the Artifact's database. Everyone with access sees
  the same review as it changes; a banner says so. Opened as a file, nothing changes:
  localStorage, as before.
- **One adapter for saved state.** Every read and write goes through `Store`. In shared mode
  localStorage is a write-through cache, the page draws from it at once, and the shared
  state replaces it when it arrives. Writes go one at a time per document, item by item,
  only on change, once typing pauses.
- **Kept per close month and run**, under `review/<period>/runs/<run>/`, one document per
  finding, row, account or entry, so two people on different items never overwrite each
  other. The sign-off is under `signoff/`, which only Editors write.
- **Names stay out of the shared state.** Who decided is a user id, named on screen through
  the viewer's own profile lookup. The Reviewer field and the sign-off's name field are
  hidden in shared mode: you sign as yourself.
- **Two people on one item.** Each write re-reads its document first. If someone changed it
  since, theirs stands and the console says so.
- **Live, in place.** Another reviewer's change redraws the console where it stands. A field
  being typed in is not redrawn; its page catches up when the field is left.
- **Read-only access** shows as such, and nothing a Viewer types is kept.
- **A rerun starts fresh** in the same artifact. On Decisions, **Bring in the earlier run's
  decisions** carries them across, matched as a loaded record is.
- **Exports** use the `downloads` capability on a published page and the browser's save from
  a file. The decision record and every export include the shared state.
- **Claude's drafts stay in the page.** Commentary that is still the draft, not accepted, is
  never written to the shared state.
- The page title reads `Serif GL Coding Review - Aug 2026`, which names the artifact.
- **Project instructions:** Publishing the Console (publishing is the default delivery, one
  artifact per close month, capabilities and rules), Shared Mode, and rule 9 (11 in the
  flux): the console is published only as a private-by-default Artifact, the reviewer
  shares it inside the organization, and anything wider is Serif's decision. HOW-TO-RUN: Shared Mode and How to Test Shared Mode.
  WHEN-DATA-BREAKS: the console and shared state are never edited by hand.

## Console 1.8.7, Project docs: 2026-10-05

From the 1.8.6 hand-off review, AIJ-110, AIJ-115, AIJ-16 and AIJ-118.

- **A loaded record never turns a Claude draft into commentary.** The flux decision record
  saved Claude's unaccepted drafts as notes, and loading it marked the account Explained.
  Drafts are now kept apart, as `drafts`; only typed, edited or accepted commentary is a note.
  A record saved by 1.8.4 to 1.8.6 did not mark drafts, so its notes load as To review:
  Accept or edit.
- **Decisions is the finish step.** It opens on the NetSuite upload file, then what was
  decided (In the NetSuite import, Fixed in NetSuite, No action, Follow up) and what is still
  open, item by item, each opening its row. Finish the close turns on once nothing over the
  threshold is open. The other files are grouped for people, for systems and for handing
  over; Clear all decisions sits apart at the foot.
- **Every flagged line gets its own outcome.** A reclass no longer clears the rest of its
  row. Each line takes Reclass, Cleared, Follow up or Fixed in NetSuite with a reason, or the
  rest of the row takes one outcome. Rows reclassed under 1.8.6 keep the rest cleared,
  written down as their own outcome.
- **The NetSuite upload is recorded:** who, when, the reference and the file by its
  fingerprint, in this browser and in the decision record. A later change to the import shows.
- **Who decided.** Reviewer, in the bar, is recorded with each decision. An audit trail CSV
  sits beside the NetSuite import: each line by External ID, with who decided it, when, why,
  its confidence and any edit. The decision log adds `decided_by` and `netsuite_external_id`.
  The import's columns are unchanged.
- **An edited entry's memo follows the edit,** in the console and the NetSuite import, or is
  the memo the reviewer writes.
- **Save and load say what they carry,** before and after. Clear all clears everything it
  names, edits, commentary, accepted drafts, raised entries and the upload included, and
  lists them first.
- **Project instructions:** Finish the close, a new request in both Projects. The flux
  workaround that repeated an unaccepted draft word for word is gone; the record no longer
  needs it.
- **Connecting NetSuite, on one page.** `CONNECT-NETSUITE.md`, the same file in both
  Projects: connect with the AI read-only role, set read tools to Always allow and write and
  delete tools to Blocked, and what to do when the login fails with a role error. Each
  HOW-TO-RUN's Connectors section points to it. Some labels still need checking in the live
  connector settings.
- Page and outcome names live in one place, `LABELS` in `build_report.py`. The decision
  stores keep `v2`.

Console 1.8.6 is kept alongside, as `serif-<use case>-aug2026-v1.8.6.html`.

## Console 1.8.6, HOW-TO-RUN: 2026-10-04

From the review of 1.8.5 and the 2 Oct instructions.

- **Typing a reason no longer redraws the whole table.** 1.8.5 redrew every row on a
  schedule on each keystroke so the status words could follow the reason. Now only a row
  whose line changed is replaced. A reason can still settle a flag shown on another row, so
  every row is checked. Aug 2026, Vendors, 57 rows, a 28-letter reason: 1,596 rows replaced
  before, 1 now. Nothing a reviewer sees changes but the speed.
- **Attach the last console with a rerun.** The files an earlier run wrote may be gone from
  the chat days later. The console from the last run carries that run, so Claude can still
  compare against it. Both HOW-TO-RUN files now ask for it in The Close in One Chat.

Console 1.8.5 is kept alongside, as `serif-<use case>-aug2026-v1.8.5.html`.

## Console 1.8.5: 2026-10-02

From the second coding demo (AIJ-119): an edit to lab supplies with the reason "test save"
looked unsaved. Every edit was saved; the console did not show it, and one click was lost.
Engines, rulesets, figures and the decision stores are unchanged.

- **A click after typing a reason is no longer lost.** Leaving a row's reason redrew the
  page under the pointer, so clicking Reclass or another outcome straight after typing did
  nothing. The page on screen is no longer redrawn when a reason is left.
- **Status follows the reason as it is typed,** on Vendors and Payroll vs. HRIS rows, on
  Ledger checks and in a Journal Entry's evidence. "Cleared, needs a reason" used to stay
  until a reload.
- **A row settled while open stays on screen** with Hide unflagged lines on, until it is
  closed.
- **An edited Journal Entry says where it stands:** "Edited. Choose Entry booked to import
  it", "Edited, in the NetSuite import" or "Edited, not booked", under its status and in
  the toast. Saving an edit does not book the entry.
- **Journal Entry edits on Decisions:** each edited entry, the proposed and edited lines,
  the reason, whether it is booked, and when.
- **Line reclasses on Journal Entries:** the page lists each reclass that joins the
  NetSuite import, `RECLASS-001` and on, with its reason.

Console 1.8.4 is kept alongside, as `serif-<use case>-aug2026-v1.8.4.html`.

## Project instructions: 2026-10-02

- **One chat per close.** Both Projects now run a close in one chat, named for the month
  ("September close"), and run again in it as the month fills in: day 10, 20 and 30 for the
  coding review, day 25 and 30 for the flux. A new month is a new chat. HOW-TO-RUN has the
  steps under The Close in One Chat.
- **A later run says what is new.** On a rerun in the same chat, Claude keeps the earlier
  run.json, runs on the newest export of the month, and compares the two runs with code
  against the decision record the reviewer attaches. Each finding is new, changed, already
  decided, still open or no longer raised, matched by rule and title as Load a decision
  record does. "Reviewed as of 20 Sep" names the run and record to compare against. Claude
  names what the record will not carry cleanly: a flux finding whose amount moved, a decided
  vendor row that has since grown, commentary written for a move that has changed, and an
  entry booked earlier that could be booked twice. The console does not mark new items;
  Claude says it in the chat.
- **Requests.** Named recipes in each PROJECT_INSTRUCTIONS, with the phrasing in HOW-TO-RUN.
  Both: run the month, rerun since the last review, build the NetSuite import, summarize the
  session, and something the console does not show. Coding review: draft the questions
  email. P&L flux: draft the commentary, the leadership summary, the follow-up email and the
  forecast revisions. The leadership summary is written only on request, in the chat, from
  commentary the reviewer has explained. The console `summary` stays off.
- **Ad hoc cuts.** A cut the console does not have is computed with code from the run, or
  from the exports through `serif_sources`, and labeled "Ad hoc, not a finding" with the
  run id, the files and the filter. It never becomes a finding or settles an item. Names
  stay withheld.
- **Connectors are read-only.** Claude uses read tools only and never writes to NetSuite or
  Coupa. With NetSuite connected it pulls the link IDs and looks up a document, for example
  to see that a fix is in. The month's GL still comes from the saved search export until
  the scripts read the connector's results.
- **Hand-off in the chat.** "Summarize the session" gives the runs, what is decided and what
  is left, the checks that did not run, and where the Work paper and the decision record
  are.
- **Run log cost.** The Project files Claude reads grew by about 3,400 tokens on the coding
  review and 4,000 on the flux, so the estimated cost per run rises on the next build.

## Views 1.6.3: 2026-10-01

- **Names withheld on a first run.** The findings are redacted before the schedules are
  built from them, so an expense report's name field no longer reaches a vendor row or an
  explanation the first time the views run.
- **Every expense report filer is withheld,** whether or not the roster still lists them. A
  former employee paid by bill kept their name in finding titles and one metric; any name
  of two words or more that filed an expense report in the ledger is now withheld
  everywhere. Aug 2026: no filer's name in either console.

## Flux engine 0.7.1, views 1.6.2: 2026-10-01

- **Run id from the engine, ruleset, period and input fingerprints**, not from where the
  files sit. A Project run and a local run of the same exports now share one id, and a new
  engine version gives a new id. Each input also records the role it was read for
  (`roles`: netsuite_gl, coupa, forecast, plan). Aug 2026 flux run id `98494ea108c5f75d`.
- `tools/compare_runs.py` compares two run.json files field by field, apart from
  `generated_at` and `source_dir`. Two local runs of each engine on Aug 2026 are identical.
- **Department spellings fold.** A department the ledger holds under two spellings that
  differ only by case (Platform / PLATFORM) is read as one, under the spelling on the most
  lines, and the plan and the forecast are matched on that spelling. Before, the other
  spelling's lines dropped out of every match.
- **Sign flips said plainly.** When the plan and the actual have opposite signs, the
  Actual vs. Budget recommendation says the plan is a credit (or a charge) and the ledger
  holds the other.
- **Negative amounts in brackets** everywhere the flux engine writes a figure, matching the
  console: `($1,234.50)`, not `$-1,234.50`.
- **New vendors name the PO's account.** A new vendor's flag says which account its Coupa
  POs charge, and whether the lines are on it. A changed coding names where the vendor's
  bills went before.
- **Email redaction** is linear on long text (200,000 characters in 0.05s; 30,000 used to
  take 2.6s) and removes an address with a combining mark or zero-width character in it.

Aug 2026 flux: 99 findings, $7,893,172.90, unchanged. Coding: 56 findings, unchanged.

## Coding engine 0.2.1: 2026-09-30

- **Posting lag once per bill.** A stale bill is raised once, on its expense lines, and not
  again on its Accounts Payable line.
- **Meals:** the amount is the add-back, half the meals spend, named in the title: "$16,329
  in 6 lines, $8,165 to add back". Before, the row showed the tax effect, $1,715.
- **Gifts:** the amount is the gift spend, not $0.
- **Aug 2026 run:** 59 findings become 56. With meals and gifts over $2,500, two more items
  need a decision: 40 are open at $2,500.

## Console 1.8.4: 2026-09-30

**Exports this month** on Overview: each export the month needs, the file supplied or
**Not supplied**, and what it feeds. The Project instructions now have Claude list the same
exports as supplied or missing in its first reply, before it runs anything.

**What each check found** on Overview, a fold: every check the engine ran, its findings and
value, and whether it ran fully, ran with less to go on, or did not run. No check clears an
item; only a reviewer's decision does.

**Work paper, HTML** on Decisions: one page to attach to the entry in NetSuite as audit
support. It holds:
- the population and threshold;
- what is left on each page;
- every decision, with who decided it, why and when;
- the line reclasses;
- the booked Journal Entries;
- the sign-off.

**Decision record, JSON** and **Load a decision record** on Decisions. The record saves every
decision, row outcome, note, raised entry and entry edit. Loading it into a later run of the
same month carries each one across: a finding is matched by its rule and title, and what the
new run has already decided is kept.

**Run log.** The console version in the bar is now a **Run log** button. The page holds:
- **Exports this month:** each export the month needs, the file supplied or **Not supplied**,
  and what it feeds. The Project instructions have Claude list the same exports as supplied
  or missing in its first reply, before it runs anything.
- **What each check found:** every check the engine ran, its findings and value, and whether
  it ran fully, ran with less to go on, or did not run. No check clears an item; only a
  reviewer's decision does.
- **Estimated cost per close run:** one run through the API on Claude Sonnet at medium
  effort, at list price, with each input it is built from. The input token count covers the
  Project files Claude reads, claude.ai's system prompt, the run's own findings, which Claude
  reads to draft, and the scripts' output; output covers what Claude writes and thinks.
  Aug 2026: $0.92 for the coding review, $1.59 for the P&L flux. In a Claude Project the run
  is covered by the Claude seat. The assumptions sit at the top of `build_report.py`
  (`COST_*`).
- **Inputs** and the **Build record**, moved from Decisions.

**Clear all decisions** asks for the word "clear" to be typed before it clears anything.

**Same month last year, named once.** On Actual vs. Actual, the prior-year column's header
has a second line, "Aug 2025 actual", in the grey of the figure under each change.

**Follow up** replaces **Asked** as the outcome for an item that waits on its owner's
answer. The stored value is still `question`, so saved decisions load as before.

**Flux pack search.** Both comparisons now have the search field and **Hide unflagged lines**
that the schedules have, so By account can be filtered as By department can.

**Commentary wraps.** The flux pack's columns are fixed, the commentary column is wider, and
a long note wraps onto new lines instead of widening the table.

**Commentary on Decisions.** The flux pack's commentary is listed on Decisions (account, the
note, whether it was typed or drafted by Claude and accepted, and the account's changes), in
the decision log CSV and in the work paper.

**Clear all decisions** shows the word to type, `clear`, in monospace.

**Work paper, HTML** on Decisions: one page to attach to the entry in NetSuite as audit
support. It holds:
- the population and threshold;
- what is left on each page;
- every decision, with who decided it, why and when;
- the line reclasses;
- the booked Journal Entries;
- the sign-off.

**Decision record, JSON** and **Load a decision record** on Decisions. The record saves every
decision, row outcome, note, raised entry and entry edit. Loading it into a later run of the
same month carries each one across: a finding is matched by its rule and title, and what the
new run has already decided is kept.

**Cost.** A $ button at the right of the bar opens the estimated cost of one close run
through the API, on Claude Sonnet at medium effort at list price. It is built from:
- the Project files Claude reads;
- claude.ai's system prompt;
- the run's own findings, which Claude reads to draft;
- the scripts' output;
- what Claude writes and thinks.

Each input is listed under the figure. Aug 2026: $0.92 for the coding review, $1.59 for the
P&L flux. In a Claude Project the run is covered by the Claude seat. The assumptions sit at
the top of `build_report.py` (`COST_*`).

**A top bar in place of the left rail.** Tables take the full page width. The bar holds the
wordmark, the use case and period, then **Overview**, one button per group of pages
(**Review** on the coding review; **Adjustments** and **Flux pack** on the flux), and
**Decisions**. A group's count bubble is what is left across its pages. Every item in the bar
is one text size and is centered on one line, and every pill is one height in every state.

**A group's pages are tabs.** Under the page title, which names the group, its pages sit as
tabs, each with its count, so a reviewer moves between them without the bar. The current
tab opens into the page like a folder tab. A group's button in the bar opens its last tab.
Scrolled content fades out under the tabs.

**The review threshold sits in the bar,** as **Review over $2,500** (or $10,000 on the flux),
on every page, since it sets every page's counts. It shows the amount with separators.

**Lines: Flagged or All.** A row's lines open in one of two views, **Flagged** and **All**,
each with its count. In either, each line names the flag it falls under. Picking a coding
narrows the list and shows as a chip that clears back to Flagged. The flags no longer carry
line-count buttons, and no view shows only the largest lines.

**An opened row's evidence sits on its own white card,** inset in the row, and each flag is
marked by the status dot, so the row's edge is the one vertical rule.

**Documents read one per line.** Where a Journal Entry or a Ledger checks row lists its
documents, each sits on its own line with its links, and an entry lists them once rather
than on both its debit and credit lines.

**One set of outcomes.** Every row and every finding ends as **Cleared**, **Asked**, **Entry
booked** or **Fixed in NetSuite**; Question, Journal Entry, Manually resolved, Book the entry
and No entry are gone. Entry booked is offered only where a finding has a proposed entry, so
Ledger checks and most Forecast vs. Actual rows no longer offer a booking that exports nothing.
The flux pages and Ledger checks gain Asked and Fixed in NetSuite. Saved decisions carry over.

**A proposed entry can be edited.** **Edit** on a Journal Entry makes each line's account,
department and amount editable, with a running debits and credits total. Save needs the entry
in balance and a reason. The edited entry goes into the NetSuite import, marked as edited, and
the decision log carries the proposed and the booked lines. An accrual with no department
says to set it there.

**Every flag says what to do, in steps the reviewer can take.**
- Each rule's **What to do** ends in the outcome to choose.
- "Ask the requester" now says to open the line's PO in Coupa to see who it was.
- Account differs from PO no longer asks the reviewer to correct a Coupa PO.
- Posting lag works with closed periods.
- Meals and gifts go to the tax preparer.
- Payroll vs. HRIS gives each status its why and its step; "pay withheld" reads "Not compared".
- The Limit and Policy rows are gone from evidence panels.
- Gone: the accrual "floor" note, "1 model line, no note", the Actual vs. Budget no-plan note
  and the "suggested" band tag.
- Toasts say what to do.
- A stale bill is listed once, on its expense line, not again on its Accounts Payable line.
- A flag that merges findings quotes each one.
- A New vendor flag at $0 is not raised.
- Entry memos read "Reclass X from 6501100 to 6410000".
- The open count is the same in the bar, the tick-and-tie and on Decisions, and the Flux
  pack shows its count.

**Less to read, one way to say it.**
- A row's open flags are stacked in its status, in place of "+1".
- The count lines above each schedule ("11 lines · 2 to decide at $10,000") are gone; the tabs carry the counts.
- The close checklist says "N open" and "X of Y done" on every page, and its title sits inside its card.
- NetSuite import, CSV sits at the right of the Journal Entries bar.
- In a reclass, the picked value is one rounded block with its focus ring, and the reason row has room around it.
- The notices on the Decisions page about draft thresholds and client confidentiality are gone.

Console 1.8.3 is kept alongside, as `serif-<use case>-aug2026-v1.8.3.html`.

## Console 1.8.3, Schedules 1.6.1: 2026-09-30

**Reclass happens in the line itself.** Reclass replaces Flag on each line. The line keeps
its shape: its account and department read as before, with a caret, and open the chart's
choices. The reason, Save and Cancel sit below the line. A saved reclass shows the posted
coding struck through above the new one, with Edit and an undo button. Flag, the "lines
flagged" status and the Lines column of the Questions export are gone.

**A row opens on the lines that matter.** The schedules carry every line a vendor posted in
the month, and each flag says which of them it is about. A row opens on its flagged lines. A
flag's line count narrows the list to that flag, a coding narrows it to that account and
department, and **Show all** lists every line. A line that is reclassed is always listed.

**Links to NetSuite and Coupa.** Document numbers in line tables, transactions, Ledger checks
and Journal Entries open their NetSuite transaction, with **Invoice** and **PO** chips beside
them that open the bill's invoice and the line's PO in Coupa. The IDs come from
`netsuite_link_ids_<month>.csv`, one SuiteQL query (`netsuite_link_ids.sql`) run through the
NetSuite connector and passed to the schedules step with `--netsuite-ids`. It is used for links
only and set aside if it does not tie to the GL export. For Aug 2026 it links 1,032 document
numbers to NetSuite, 842 to a Coupa invoice and 797 to a PO. PO numbers in findings open the
PO in Coupa. Ledger checks rows now list their document numbers.

**One coding table.** A vendor's codings read as one table, each account and department
over the three months, in place of separate account and department tables.

**Evidence panels say each thing once.** A Now and Should be block that restates the finding
shows only where there is no written explanation. The decision buttons are compact, and the
note field carries its label as its placeholder.

**Nothing overlaps.** Schedule columns grow to fit what they hold, status words wrap, and a
table wider than its card scrolls inside the card. Checked on every page of both consoles at
1440, 1280, 1024 and 420 pixels wide, with rows and a reclass open: no text or control
overlaps another or spills from its cell.

**One control standard.** A button, choice or text field in a table row or a panel heading
is compact, at the row's text size and one height; pills are page-level actions only.
Controls that sit together, or beside text, share one flex row and one gap. Line tables pad
every cell the same on both sides. Evidence panels use the full width of their card.

**Less on the page.**
- The explanations under the tick-and-tie, the amount bands, the below-threshold card and a
  reclassed row are gone. So are the hints in the flux drill-down.
- The list of figures under the treemap is gone; each cell's tooltip carries them.
- **Hide unflagged lines** is the new name for the Vendors toggle.

## Project instructions: 2026-09-30

**P&L Flux no longer writes a leadership summary.** Like GL Coding Review, it says in the
chat what it drafted and which checks did not run. The Overview opens on the checklist and
the tick-and-tie. Console 1.8.2 still shows a `summary` if one is given, at the foot of
Overview.

## Console 1.8.2: 2026-09-30

**Each outcome on a row keeps its own note.** A row had one note shared by all its
outcomes, so a reason written under Cleared reappeared as the question under Question,
and would have gone out in the Questions export and onto the row's findings. Switching
outcomes now shows the note written for the outcome chosen, empty if none, and keeps the
others for when they are chosen again. A reclass starts with no note of its own, and a
Claude draft fills the note of the outcome it recommends. What the exports and the
findings record is always the note of the outcome in force. Rows saved under 1.8.1 or
earlier restore with their note under their current outcome.

## Console 1.8.1: 2026-09-30

**A band under the reporting floor is drawn when it holds an item.** 1.8.0 left out the
band wholly under the engine's reporting floor ($2,500 on the flux) whatever it held. An
item under the floor, which the engine does not emit today but an adjustment could, would
have counted in the tick-and-tie and shown in no band. The band is now left out only when
it is empty. The Aug 2026 builds look and count as in 1.8.0.

## Console 1.8.0: 2026-09-30

**The Overview opens on what is left to do, and a row can reclass one line.** From the
first coding demo: reviewers want to act first, see that the review covered everything, and
fix one miscoded line without booking the whole row. Engines, rulesets and figures are
unchanged; only the console and the Project instructions move.

* **Overview, both consoles.** The close checklist is first. A tick-and-tie follows: items
  and dollars over the threshold, split into settled and left to review, and under it,
  each as a percent of items and of value, footing to the total. **Items by amount**
  replaces Items by threshold: bands cut at the report's threshold presets (under $2,500,
  $2,500 to $10,000, $10,000 to $25,000, over $25,000, and for the flux $25,000 to $100,000
  and over $100,000), each with its count and dollars, adding up to the same whole. A band
  under the engine's reporting floor is not drawn. Clicking a band reviews from its lower
  edge up. The Left to review and Value to clear tiles are gone: the tick-and-tie carries
  both. The treemap is kept, below, as Value left by page. Claude's summary moves to the
  foot of the page.
* **Manually resolved**, a fourth outcome on Vendors and Payroll vs. HRIS rows, for a fix
  the reviewer made in NetSuite itself. It needs a note, what was changed, and it declines
  the engine's proposed entry on the row with that note.
* **Reclass one line and clear the rest.** Each line on a row has **Reclass**: pick the
  account from the chart (P&L accounts by group, then the balance sheet; never typed), the
  department if it changes too, and a reason. Saving settles the row as Reclass, rest
  cleared, and declines the engine's proposed entry on the row so the fix is not booked
  twice. The line shows its posted coding struck through with the new coding under it;
  **Remove** reopens the row.
* **Reclasses in the exports.** The NetSuite import adds one balanced entry per reclassed
  line, `RECLASS-001` and on: debit the new account, credit the posted one (flipped for a
  credit line), dated the period end, the reason as the memo with the `| Mon'YY` tag, and
  the line's own document and description as the line memo, marked `YES - reclass by a
  reviewer`. The decision log adds a row per reclassed line; Decisions lists the moves
  under their row.
* **Project instructions.** GL Coding Review no longer writes a `summary`; it says in the
  chat what it drafted and which checks did not run. P&L Flux still writes the leadership
  summary, now read at the foot of Overview. Neither recommends Manually resolved or a
  reclass: both are the reviewer's own calls.
* The decision stores keep their keys: the new outcomes add to the vocabulary and remove
  nothing, so decisions recorded under 1.7.x restore unchanged.

Verified on Aug 2026 against 1.7.2: the run embedded in each console is byte-identical, with
the same run ids, findings and Journal Entries. The tick-and-tie foots to the population the
1.7.2 Overview counted, 71 items and $1,730,200 for the coding review and 74 items and
$6,244,493 for the flux; the bands add up to the same totals.

## Console 1.7.2: 2026-09-29

**The console follows the Serif Brand Guide on Brandpad.** Colors, typefaces and their
usage match the guide. Layout, features and figures are the same: outside the stylesheet,
the Aug 2026 builds are identical to 1.7.1.

* Palette: Dark Gray `#2E2D29`, Mid Gray `#525046`, Warm Gray `#ADA990`, Light Gray
  `#E5E5E5` and Red `#FF3D00`. Secondary text and the under-threshold state are Mid Gray
  (8.09:1 on white). Rules, borders and rail text are Warm Gray.
* The wordmark on the rail is White. The brand allows the logo in Dark Gray or White only.
* Eliza is kept for headline highlights and the headline figures. Finding titles, evidence
  headings and treemap values are in Denim.
* Rail section headings are in sentence case, semibold, in Warm Gray (5.81:1 on Dark Gray).
* The font stacks fall back to the brand's alternatives, Helvetica or Arial and Georgia,
  after the open-licensed Figtree and PT Serif.
* `serif-design-system/` takes the brand guide as its primary source. `tokens.css` adds the
  five brand colors by name and points `fg-secondary` at Mid Gray and `bg-secondary` at Warm
  Gray. `README.md` labels each rule by source, adds Logo and Brand Graphics sections and the
  brand voice, and corrects the site rules the guide overrides. `reference/` holds the guide's
  sections as `brandpad-<topic>.png`. The console tokens match `tokens.css`.

## Console 1.7.1, Schedules 1.6.0, coding engine 0.2.0, flux engine 0.7.0: 2026-09-28

**Both engines read Serif's exports exactly as the systems write them.** No sliced, converted
or summarized file is an input. The NetSuite Custom General Ledger `.xls`, the Coupa PO line
`.csv`, the rolling forecast `.xlsx` and the UKG roster `.csv` go in as exported, and each
script takes what it needs in memory.

* `--gl` takes one NetSuite export or several, and `--period` names the close month. The
  scripts take the month, the months before it and the same month last year from whichever
  export holds each. A month held by two exports is refused, since the two may differ.
* The flux engine reads each month's activity by account and department from the GL, the
  Coupa export in place of the normalized slice, and the plan and the month's forecast from
  the workbooks: `--plan` with `--plan-vintage`, and `--forecast`.
* The schedules read the plan from the workbook and the Coupa department codes from the
  roster. `--write-dept-codes` and the normalized Coupa reader are gone.
* `serif_sources.py`, new in both Projects, holds the NetSuite, Coupa and forecast readers,
  moved unchanged from the three tools that used to cut the files. The coding engine reads
  NetSuite with its own bundled reader.
* Removed from both Projects: `forecast_lines_2026-06.csv`, `forecast_lines_2026-08.csv`,
  `budget_fy2026_by_account_dept_month.csv`, `unmapped_forecast_accounts.csv` and
  `coupa_dept_code_mapping_from_ukg.csv`. `monthly-inputs/aug2026` holds the exports
  themselves.
* `WHEN-DATA-BREAKS.md`: when an export does not fit, ask for it again. Claude no longer
  repairs an input.

**The commands are the same every month.** Only `--period`, the month's forecast workbook
and the output folder change. The Project instructions and `HOW-TO-RUN.md` show them for a
Sep 2026 close.

Verified on Aug 2026 against the previous build:

* Every GL line, every account activity row and every Coupa slice row the tools produced is
  reproduced exactly by the readers.
* Coding: findings, summary, metrics, schedules and Journal Entries are identical. 59
  findings, 50 Journal Entries.
* Flux: the same 99 findings and 14 Journal Entries. The plan reader places 32 more plan
  lines than the old CSV, about $90,000 across all periods, on accounts such as D&O
  Insurance and Phone & Network. The old CSV was built from four GL months, so the ledger
  knew fewer account names. Aug 2026 gains one planned account and department,
  6850000 Phone & Network, $100. The mapping from 13 months of GL matches the mapping from
  all 20.
* Two orderings depended on Python's set order and changed from run to run: departments
  with the same move on a flux finding, and accounts with the same amount on a vendor row.
  Both now break ties by name. Two runs under different hash seeds are identical.
* No employee name or email address in either console.

The console change is the absent-feed labels for the plan and the forecast.

## Console 1.7.0, Schedules 1.5.0, coding engine 0.1.1, flux engine 0.6.0: 2026-09-26

Built around how a reviewer works the month, from the 2026-09-25 CCC walkthrough: start
from vendor bills, compare three months by account and by department, read the line
description, then decide. Lines are fine until something flags them.

**GL Coding Review: six pages, down from thirteen.** Overview, Vendors, Ledger checks,
Payroll vs. HRIS, Journal Entries, Decisions.

* **Vendors** replaces Period over Period, Split Coding, Vendor vs. Plan, Requester vs.
  Coding and Coding Exceptions, which showed the same vendors four ways. One row per
  vendor: what was bought, where it was coded, Jun, Jul and Aug. The row opens to the
  three months by account and by department, the planned coding, and every line with its
  description first. Each reason to look is a flag on the row: new vendor, coding
  changed, unusual department, account differs from the Coupa PO, coded off plan,
  requested by another department, may be prepaid, may be capital. A reviewer can flag
  any line no rule caught. Vendors billed earlier and not this month are listed, folded,
  so the three months tie to the ledger.
* **Every flagged row ends as Cleared, Question or Journal Entry.** Cleared and Question
  need a note. The outcome settles the engine findings on the row: a Journal Entry books
  them, Cleared declines them with the same note, a question leaves them open.
* **Questions, CSV**: every question with its owner department, amount, flags and lines.
* **Ledger checks** holds posting lag and tax on one page.
* **Prepaid and capital flags in the coding review.** The rules are the flux engine's own,
  imported from `serif_uc2_flux.py`, which now ships in both Project folders.
* Department vs. Plan, Coding health and Not tested are off the rail.

**P&L Flux: nine pages, down from fourteen.** Actual vs. Actual carries the same month
last year as a column; its own page is gone. Actual vs. Budget reads by account or, on a
toggle, by department, which replaces Department vs. Plan. Payroll vs. HRIS moves to the
coding console. One commentary per account serves both comparisons.

**A flux account's evidence is the drill-down.** The departments behind the move; select
one to narrow the list. Then what changed inside them by vendor, Jul against Aug; open one
for its lines from both months, description first. **Draft commentary** writes the
figures as a first sentence for the reviewer to edit. The panel carries no title and no
general advice, because the row already states the figures.

**Proposed entries read as entries.** Debit and credit, each with account, department
and amount, in place of the one-line "Dr ... / Cr ..." string. Journal Entry memos say
what the entry does ("Move Nova Biomedical Corporation bill to prepaid, then amortize
over the service period").

**Overview reads one population.** The tiles, the threshold bars and the treemap by page
count the same items the checklist does. The below-threshold and not-tested folds are
gone. A treemap cell shows as much as fits; one that cannot show all its figures is
listed in full under the map. Every table opens its rows from a button column of its own. Journal Entries are
left out because each restates a finding elsewhere; a flux account counts once.

**Project instructions rewritten for both Claude Projects.** Each `PROJECT_INSTRUCTIONS.md`
says how to run the Project, what Claude writes, and the rules; each skill file is now a
reference: what every check tests, how account groups move, and entry patterns. Claude
drafts vendor notes, reasons for cleared rows, questions for owners, Journal Entries in the
NetSuite import layout, flux commentary per account from the drill-down data, notes on each
adjustment, and a leadership summary, all from the run's own figures.

**The UKG roster is a monthly input** for both Projects, which run on Serif's own Claude
instance. The requester flag on Vendors and Payroll vs. HRIS now run in the Project; every
employee name stays withheld from the console.

**Claude's drafts go into the console.** `build_report.py --drafts drafts.json` checks each
draft against the run and places it beside its item, marked "Drafted by Claude": commentary
in the account's field, which counts as explained only once accepted or edited; a suggested
outcome and note on vendor rows and adjustments, used with one click; drafted Journal Entries
on the Journal Entries page, which must balance and export marked `YES - drafted by Claude`;
and the summary at the top of Overview. The decision log records a note as drafted by Claude
until the reviewer edits it. Drafts that match nothing in the run are left out and listed.

**Personal data.** The schedules step now redacts the whole artifact, the engines'
findings included: an expense report's submitter reads "Expense report", email addresses
are removed, and with the roster every employee's full name is withheld. Before this, the
coding console carried six roster names and three email addresses from engine memos.

### Engine changes for the repo port

* **Raw exports, coding engine 0.2.0 and flux engine 0.7.0.** The runner takes
  `gl_paths` and `period` in place of three slice paths, and `coding_engine.loaders` gains
  `load_gl_exports`, which reads through `gl_extract.netsuite_gl_to_csv` and refuses a
  month held by two exports. The budget file leaves `PENDING_FEEDS`. The flux engine and
  the schedules read through `serif_sources.py`: the same parsing as `gl_extract`,
  `coupa_extract` and `forecast_to_csv`, returning rows in memory instead of writing files.
  The forecast reader maps account names through the GL lines supplied.

* **Coding engine 0.1.1, T0.DUPLICATE_LINE 1.2.0.** The duplicate signature adds the line
  description and memo. Aug 2026: 59 findings and 59 reversing entries fell to none. Every
  one of the 59 was different items at the same price on one invoice. Findings 118 to 59,
  proposed Journal Entries 109 to 50. Edited in the bundle; the repo has not been changed.
* **Flux engine 0.6.0, ruleset 2026.09-uc2-flux-account-level.**
  * F1.VARIANCE 3.0.0 tests each P&L account against the prior month. The prior year is
    carried for context and no longer raises a finding. Each finding carries its
    departments, top vendors, and the actual, prior and prior-year amounts.
  * F2.BUDGET 2.0.0 tests each planned account against plan, with its departments.
  * Aug 2026 at $10,000: 29 accounts to explain, down from 97 account and department
    lines.
  * F10.CAPITALIZE reads 6435000 Lab Equipment Repairs & Maintenance. A bill worded as
    a service term is left to F9.PREPAID, and an account F10 reads needs term wording
    before F9 treats it as prepaid, so one bill is not raised twice.
  * Expense report lines in F1 and F2 evidence read "Expense report" and are left out of
    the vendor ranking.
  * The flux table row carries `mom_finding` and `budget_finding`.
  * F1 and F2 findings carry `movers`: each department and vendor this month against
    the prior month (F1) or this month alone (F2), largest change first, with up to four
    lines from each month. F1 reads the prior month's GL from `--history`.

## Schedules 1.4.0: 2026-09-25

**Every finding explains itself in Simplified Technical English.** The evidence panel
shows three short parts written from the finding's own figures: why it was flagged, what
to do, and its limit where it has one. Short sentences, active voice, one fact each. They
replace the engines' basis, recommendation and confidence wording on schedule pages, which
described the rule in general terms rather than the finding. Written by the schedules step
from each finding's evidence, so the coding engine is unchanged; a run without the step
falls back to the engines' own text.

## Console 1.6.3 and Schedules 1.3.0: 2026-09-25

**Overview keeps its headline figures** above the close checklist: what is open over the
threshold and what it is worth, what each threshold would catch, and value by category as
a treemap, each cell sized by value, labeled with its figures, and opening its page.
Findings by basis and the tests-not-run tile are left off; the checklist note says which
feeds are missing.

**Payroll vs. HRIS**, on both consoles: salaries by department in the ledger against
UKG's monthly pay for the people it places there, hired by the period end. A department
of fewer than three people shows its headcount only, and there is no UKG subtotal,
because either would disclose someone's pay. Aug 2026: In Vivo carries $56,888 more than
its four people, Biology $55,261 less than its five, and Computational Sciences $14,953
with nobody in UKG.

**The HRIS roster counts as supplied** on Not tested, with the tests it feeds, and no
longer as missing. The engines' own pending-feed check still reads the empty template,
which asks for salary per person and stays empty.

**Not tested says what each missing feed is and what it would test, and nothing else.**
The console words these itself rather than printing the engines' notes, which carried
file mechanics and history. The dimension descriptions are cut the same way.

## Console 1.6.2 and Schedules 1.2.0: 2026-09-25

The console numbers stay in the 1.6 series here because the repo's console is already at
1.7.x; the two lines are different builds.

**Overview is the close checklist.** Every page in the rail, what is left on it at the
threshold, what that is worth, and what is done. The threshold is set here. There is no
grand total, because the pages overlap: the three flux comparisons read the same
accounts, and Journal Entries restates findings from other pages.

**All findings is gone from the rail** when a run carries schedules. Coding Exceptions,
Ledger Integrity and Tax & Deductibility are tables like every other page, one line per
finding, the decision in the panel under the row. A run without schedules keeps the old
queue, as its only way through.

**Split Coding**, on the coding console: the vendors the engine sets aside because their
coding has no settled pattern (24 contested, 18 with little history, 21 new in Aug 2026),
each with its spend by department for three months, how often its past lines agree, and
which departments raised its purchase orders. Fisher Scientific: coded mostly to General
R&D, requested mostly by Platform.

**Three months.** Period over Period and the flux pack's month-over-month page carry the
month before the prior one, so a swing that reverses reads as one. `serif_views.py` takes
`--prior2`; the flux engine derives it from `--history`.

**New Adjustments schedules**, from engine 0.5.0: Prepaids and Capital (with what was
already billed to prepaid and fixed-asset accounts beside it), Reclassifications, and a
billing-pattern section on Accrual Proposals.

**Journal Entries lists only entries that balance.** A difference the forecast tie sees
on one account only is a reconciliation item and stays on Forecast vs. Actual. Where a
manual forecast line nets to zero across two differences, the two are one entry: the
"Labs to CMC" reclass is Dr 6504000 CMC / Production, Cr 6410000 Lab Supplies /
Production, $739,899.48. Deciding it decides both differences.

## Console 1.6.1 and Schedules 1.1.0: 2026-09-25

**Evidence opens under its row, on every schedule.** Nothing on a schedule sends the reader
to another page. A click anywhere on a row opens it; the commentary field, the "more"
disclosures and the row's own buttons do not.

**A row with no finding opens to its ledger lines**, largest first: date, document,
vendor, what the line says was bought, account and department. That is the fastest answer
to "why this split?" on a vendor coded several ways.

**A schedule row links only to a coding finding about that row's coding.** Linking on the
vendor alone sent an Aldevron plan row to a duplicate-posting finding and offered to book
it. Rows now link to a department or account finding whose lines carry the row's own
account and department, or to nothing.

**The decision column shows where a row stands and one Evidence button.** Book the entry,
No entry and the reason field sit in the panel, beside the evidence they are taken on.

**No banding on schedules.** Their rows are ruled and their figures sit close together.
Banding stays on the plain tables, such as Inputs, where a label sits far from its figures.

**Caveats above the table, not under it.** Method notes are gone; the headings carry
them. What changes how a table reads is one line at the top: forecast lines matching no
ledger vendor, purchases by people not on the roster, the accrual floor, one-sided
Journal Entries.

**Show and hide**, in place of "Only lines needing a look": Hide lines with nothing to
review, then Show all lines.

**Forecast line notes are quoted and sourced to their cell.** The reconciliation's
staging text is the forecast workbook's own wording, for example
"Claude Reclass: Labs to CMC" at `LAB!29`. The console quotes it and names the cell, so it
cannot be read as a label this system applied. Nothing in either engine reclassifies.

**Inputs lists each file once**, with the step that read it.

**Names inside line descriptions are withheld** when the roster is supplied, as well as
names in vendor fields. Pass `--roster` to both consoles' schedules step to get this.

## Console 1.6.0 and Schedules 1.0.0: 2026-09-25

The period as schedules, in both consoles, and one table style for all of them.

**For the repo port.** No engine rule changed: both engines emit the same findings as
before, 118 and 135, on the same inputs. What is new is a step between engine and
console, `serif_views.py`, byte-identical in both `upload-to-project/` folders, which adds
a `views` block to `run.json`: account names, the schedules, and each proposed correction
as Journal Entry lines. The console renders that block and computes nothing from it. Its
inputs are fingerprinted under `views.inputs` and listed in the Build record, because the
engine's run id does not cover them.

**Every account carries its name.** A code alone means nothing to anyone who has not
memorized the chart. Names come from the ledger's own account paths. Every code the
console shows, including codes quoted inside an engine's titles, corrections and
recommendations, gets its name beside it unless the text already says it.

**Coding schedules.** Beside the exception queue, under Schedules:

* **Period over Period**, each vendor's account and department coding against the prior
  month and the same month last year: changed, new, billed last month and not this one,
  and coded as before.
* **Vendor vs. Plan**, the forecast's vendor lines against how the spend was coded. The
  forecast's wording shows where it names a vendor differently from the ledger, and lines
  that match no ledger vendor are counted by workbook cell.
* **Department vs. Plan**, by department, then account. Planned pairs with nothing posted
  are listed; F2.BUDGET does not raise those, so the table is the only place they appear.
* **Requester vs. Coding**, the UKG department of whoever raised the purchase order or
  expense report against the department charged. Department level only.
* **Journal Entries**, every proposed correction written as the entry that books it.

**Flux Adjustments as schedules.** Forecast vs. Actual is a reconciliation table and
Accrual Proposals an accrual schedule, each row carrying Book the entry, No entry and its
evidence. Both rail entries open on the schedule; the findings stay in All findings.
Department vs. Plan joins the flux pack.

**Journal Entries.** Grouped by kind with subtotals, one band per entry, the documents
behind each line, and a NetSuite import export. The import carries only entries marked
for booking and in balance. F5.MODEL_TIE names one side of each difference, so those
entries show as one-sided and stay out of the import until the offsetting line is chosen.

**One table style.** The striping was inconsistent because it counted rows: section
headings and opened evidence panels took a stripe like data, and every band after them
shifted. A band now belongs to a record and restarts at each section. A line needing
action takes an accent rule on its leading edge and an accent status word, never a tint,
so the flag cannot be mistaken for the band. Status and the row's buttons share one height
and sit on one line. Section rows are in sentence case.

**Lines needing action follow the reviewer's threshold** on every page, so the schedules,
the flux pack and the rail counts agree. An undecided item under the threshold reads
"Under $10,000" rather than taking the accent.

**Text fields fit their text.** Commentary and reason fields grow as they are typed into
and have no resize handle. On the flux pack the status beside the field turns from Needs
commentary to Explained as the commentary is typed.

**Decisions on a table row settle that row's finding only.** The queue decides a cluster
at once; a schedule lists findings one per line, and deciding one line must not settle
another two rows down.

**"Journal Entry" in full** everywhere a reviewer reads it. The proposed-entries export is
now Proposed Journal Entries.

**Personal data.** The UKG roster resolves a person to a department and nothing else. No
name, email address or salary is written to the artifact. Expense reports are left out of
the vendor schedules, because their vendor is the employee who submitted them. A vendor
that matches a person on the roster reads "Employee paid through AP (name withheld)", with
its document numbers kept.

**Coupa department codes are resolved through UKG.** UKG's department codes are Coupa's
with a letter prefix, so the numeric part maps each Coupa code to a department. The
mapping is written, with no personal data, to
`data/real/derived/coupa_dept_code_mapping_from_ukg.csv` and copied into both Projects.
Codes 1, 11, 23 and 56 resolve to UKG departments that are not ledger departments, and the
file says so. Serif has not confirmed the mapping.

**Percent variance follows the variance's sign** in the new tables: it is divided by the
size of the base, so a negative-base account no longer shows the opposite sign to its
subtotal. The flux pack's own percentages still come from the engine and still carry that
defect.

## Console 1.5.0: 2026-09-23

The flux pack as a table, alongside the findings queue rather than instead of it.

**Every P&L account line, not just the exceptions.** A findings queue answers "what needs a
decision". A flux pack answers "explain the period", and an account that did not move is
part of that answer: a flat line is a statement, and a reviewer who cannot see it cannot
confirm it. 72 account lines for Aug 2026 across 18 subtotalled sections, drawn from
Serif's own account hierarchy rather than an imposed one.

Three comparisons, each its own rail page under Flux pack: **Actual vs. Actual**, the same
year over year, and **Actual vs. Budget**. Both comparisons ride on every row, so following
an account does not mean changing view to see the other half of its story.

**The reviewer can act on a line, not only annotate it.** A row the engine already flagged
links through to its evidence in the queue. A row no rule flagged carries Raise entry, which
records a reviewer-raised adjustment. Both origins land in the proposed-entries export,
which now carries an `origin` column, because an accountant reading the close file needs to
know which the machine proposed and which a person did.

Commentary is typed per account and persists on its own key. The engine writes none:
seeding it from the recommendation text would be the engine writing commentary in
everything but name.

Flags follow the reviewer's own threshold rather than a number baked in at build time, so
moving the threshold moves the flags.

**The variance findings pages came off the rail.** F1.VARIANCE and F2.BUDGET are the same
rows the table now shows better, with every account rather than only the flagged ones and a
link through to the evidence. Both stay reachable from All findings. Nothing was removed
from the engine.

**Naming follows the Jumpstart demo**, since that is the vocabulary the reviewer already
has: the accounting layer is **Adjustments**, holding Forecast vs. Actual and Accrual
Proposals, and the FP&A layer is Variance review.

Engine 0.4.0 emits a `tables` block. The activity loader now carries `account_path` through
so the table can section on the hierarchy; that refactor was verified output-neutral against
0.3.0 before anything was built on it.

## Console 1.4.0: 2026-09-22

Each analysis gets its own page in the rail.

**The rail now lists the analyses, not just the views.** Under Overview sits "All findings",
and below it one entry per analysis: for GL Coding Review, Coding Exceptions, Ledger
Integrity and Tax & Deductibility; for P&L Flux, Forecast vs. Actual and Accrual Proposals
under Accounting review, then Actual vs. Actual and Actual vs. Budget under FP&A review.

Two pages compare a forecast to actuals and they are not the same test, so each says which
vintage it reads. **Forecast vs. Actual** takes the current cut, whose closed months hold
the posted actuals, and is a reconciliation. **Actual vs. Budget** takes the prior cut, made
before the month began, and is a measure of performance.

This follows how the work is actually done, consistency first, then plan, then tax, rather
than asking the reviewer to hold three questions at once in one queue. "All findings"
stays, because working one list top to bottom is a legitimate route and removing it would
trade one constraint for another.

Each entry carries its open count at the current threshold, and blanks at zero rather than
showing a nought.

Every entry lands on the review view with the group filter set, so one list implementation
serves the combined queue and every single-analysis page. The Overview category chart now
navigates to the matching page instead of only filtering in place.

Pages are built from the run's own groups, so a console shows the analyses its engine
produced and nothing else. A group with no findings this period is dropped rather than
rendered as an empty page. There is deliberately no Budget vs Actual page on GL Coding
Review: that engine has no budget rule, and an empty page would claim an analysis that does
not run.

**An engine that declares no groups now gets the coding defaults from the builder**, which
is the case for the bundled GL Coding Review engine. This resolves before the payload is
serialized. Doing it afterwards left the rail reading the builder's list while the findings
list read the JavaScript fallback, and the two carried different labels for the same group.

**Every group of pages carries a heading that names it.** Overview and All findings sit
ungrouped at the top, since both read the whole run. Below them each group says what its
pages have in common: Review on GL Coding Review, the layer names on P&L Flux, and Record
over the decision log and the two coverage views. A bare gap was tried instead and
discarded: it told the reader something had changed without saying what, which is the one
thing the section exists to do.

Item spacing tightened at the same time, since the old rhythm was set for a rail of six
entries.

**Rail counts show open items, and nothing else.** A tick on a cleared analysis was tried
and removed. It claimed the analysis was finished when all it knew was that nothing above
the current threshold was outstanding, so raising the threshold would have marked pages
complete without a single decision being made.

**One style for every rail entry.** The first cut set the analysis pages smaller and indented
them, which encoded a single level of nesting twice and left three type sizes in one rail,
with the two consoles disagreeing about whether section headings existed at all. Items now
share one size, one indent and the same current-page dot at any depth, and the section
heading is the only thing carrying the grouping.

Both rails now run Overview, All findings, the analysis section, then Record. Only the
middle section's headings differ, because the content does: a run with layers names them,
a run without gets one heading over its analyses.

**Analysis pages take the names accountants already use**, from the Jumpstart demo and from
how the work was described on the 22 Sep call: Coding Exceptions, Ledger Integrity and Tax &
Deductibility on GL Coding Review, and Actual vs. Actual and Actual vs. Budget on P&L Flux.
These are named analyses rather than sentences, so they carry Title Case; structural entries
such as Overview and All findings stay in sentence case.

## Console 1.3.0: 2026-09-18

Two layers, and one binary decision.

**Review runs accounting first, then FP&A.** Findings carry a `layer`, and the console
groups on it before grouping on category. A run whose findings all sit in one layer
renders exactly as before, so GL Coding Review is unchanged in appearance. The order is
load-bearing: a budget variance computed on miscoded actuals measures the miscoding.

**The decision vocabulary is now two words.** `Book the entry` or `No entry`, with a reason
required only on the second. This replaces `Accept recommendation` / `No change needed` /
`Different action` on coding findings and, more significantly, replaces the
timing / structural / coding / not-material classification on variances.

Classification was the wrong instrument. It is a taxonomy exercise, and it forced a choice
before the evidence was in: whether a movement is timing is often unanswerable at the
moment the line is reviewed, while whether an entry is being booked always has an answer.

The proposed-entries export now filters on the `book` verdict. Anyone editing the verdict
keys must keep that filter in step or the export silently empties.

**The correction is now its own block**, directly under the finding title in both the detail
pane and focus mode: the dimension being called out, the current value, an arrow, and what
it becomes, plus the debit and credit line where the engine computes one.

Engines that compute a correction supply `correction` outright. The coding engine does not
yet, but it already puts the same pair in `evidence.observed` and `evidence.expected`, so
those are read as a fallback, which covers 116 of its 118 Aug 2026 findings. The two that
get no block are tax deductibility flags, which propose no recode. When a correction is
derived this way, the `Observed` and `Expected` rows are dropped from the evidence list
below it, because they would otherwise print the same two strings twice on one card.

**Copy removed.** Four blocks of explanatory text that described the interface rather than
the data: the threshold chart's axis caption and click hint, the deterministic-versus-
proposal note under the basis chart, "every dimension is checked in the same pass" above the
coverage table, and the paragraph explaining the three version numbers in the build record.
The layer headings carry no open-item count, since in the default open queue every item
listed is open.

## Console 1.2.0: 2026-09-17

Severity tiers replaced by a threshold the reviewer sets.

* **Grading is by money, not by adjective.** High / medium / low are gone. A finding
  is either at or over the fix threshold, or under it. The question is binary, so the
  display is binary.
* **The threshold is a control, not a constant.** Default $2,500 for GL Coding Review,
  $10,000 for P&L Flux, adjustable in Review and settable from the Overview chart.
  Setting it to `0` shows everything.
* **Items by threshold** chart shows what each candidate threshold catches, so the cost
  of a looser number is visible. At $2,500 the coding queue is 21 items carrying 81% of
  the value; at $25,000 it is 2 items carrying 25%.
* **Items below threshold** card totals the sub-threshold population and breaks it down
  **by department**, because a threshold is set against the aggregate and errors
  concentrated in one department are not the same as the same value scattered.
  Collapsed by default.
* **Cluster totals now cover the whole cluster.** A cluster's amount summed only the
  members the active filter admitted, while one decision covers every member, so the
  row understated what was being decided. Rows now show the full total and disclose how
  many members sit under the threshold.
* **Proposed entries export fixed.** It filtered on the retired `approve` verdict and so
  was always empty. It now filters on `accept` and carries department.
* **Dimensions tested** table on Not tested: account, department, project and entity,
  each with its status and what is checked. Project and entity are recorded as not
  applicable, with the reason.
* Decision log export carries the band, the threshold in force, and department in place
  of severity.
* Serif's crossing-loop and hairline-curve motif replaces the cropped S, in the page
  background and in the rail. Use-case name in the rail set in the serif face at a
  readable size, since the two consoles get opened side by side.
* Focus mode separated to the right of the filter row with an eye icon, so it does not
  read as one more filter.

## Console 1.1.0: 2026-09-17

Findings grouped into decision units, and a faster way through them.

* **Grouped by decision unit.** Findings cluster on rule and subject, and one decision
  covers the whole cluster. GL Coding Review's 118 findings became **29 decisions** , 
  the 59 duplicate-posting findings are one row, MedChemExpress's 9 are one call.
* **Materiality line.** "29 decisions across 118 findings · the top 7 carry 80% of the
  value", so attention goes where the money is.
* **Focus mode.** Full-screen, one card at a time, sorted by value. `A`/`R`/`M` (coding)
  or `T`/`S`/`C`/`N` (flux) decides and auto-advances; `Space` skips; `Esc` returns.
* **Decision vocabulary made specific.** The old Approve / Reject / Modify and
  Explained / No action needed said nothing about what was decided.
  - Coding: **Accept recommendation · No change needed · Different action**
  - Flux: **Timing · Structural · Coding error · Not material**, a variance is
    classified, not dispositioned, because the classification drives what happens next
* **A written reason is required** where the reviewer overrides the engine, or where the
  commentary is the deliverable. A decision missing a required reason stays in the
  outstanding queue rather than counting as done.
* **Clear all decisions** control, for handing over a clean demo.
* Removed running tallies from the chrome. Counts live on Overview, where they are the
  content rather than decoration.
* `STORE_VERSION` → `v2`. Decisions recorded under the 1.0.0 verbs do not carry over,
  deliberately: those actions no longer exist.

## Console 1.0.0: 2026-09-17

First working surface rather than a report.

* Application shell: fixed rail, five views, master-detail findings workspace.
* Decisions persisted per run, with CSV and JSON export and a sign-off block.
* Adopted `serif-design-system`: Serif's own tokens, the wordmark, the cropped hairline
  S, open-licensed Figtree and PT Serif at the specified size-adjust. Nothing uppercase,
  no borders or shadows on cards, pills for actions, one vivid accent.

---

## P&L Flux engine

### Ruleset 2026.09-uc2-flux-adjustments: 2026-09-25

Engine 0.5.0. Five accounting-layer rules, drawn from a reviewer's pass over the Jun to
Aug ledger. The 135 findings of the previous ruleset are unchanged on the same inputs;
these add 10.

* **`F6.ACCRUAL_PATTERN`**, the Accrued Expense Policy's billing-pattern method: a vendor
  with at least three invoices in the trailing six periods, a trailing three-month
  average over $5,000, and a current month nil or under a quarter of it. Only for
  suppliers with no Coupa line this period, and never for one the receipt method already
  accrues. Proposes the average less what was billed. Confidence drops where the average
  rests on one invoice. Aug 2026: Mirai Bio, Altasciences, Miltenyi.
* **`F7.REVENUE_IN_EXPENSE`**, a customer document (invoice, credit memo, cash sale)
  posted to an expense account, proposing a reclass to 4001003 Revenue - Cost
  Reimbursement. Aug 2026: the credit that turned 6201000 General Consulting negative.
* **`F8.VENDOR_DROPPED`**, a journal with no vendor whose account, department and amount
  match a line that named one. Where the same amount was billed to a prepaid account, the
  journal is read as that prepaid's release. Aug 2026: three releases of prepaid rent,
  parking and management fees.
* **`F9.PREPAID`**, charges over the $10,000 prepaid threshold, aggregated per vendor and
  account, whose wording names a service term or which sit on a term account the vendor
  does not bill most months. A vendor billing an account most months is charging for
  what it consumes and is not flagged, whatever the invoice says.
* **`F10.CAPITALIZE`**, purchases on the four accounts the asset policy names for
  capitalization review. The policy sets no threshold, so every document from the
  reporting floor up is listed; service and support are left to the prepaid rule.

`--history` takes the GL detail for up to six earlier months. Every input that changes a
finding is now fingerprinted and moves the run id, including the `--model` file, which
was previously left out. `bills_to_balance_sheet` lists what was billed straight to
prepaid and fixed-asset accounts in the period.

Aug 2026: 145 findings, $10,891,294.23. 27 accounting, 118 FP&A.

### Ruleset 2026.09-uc2-flux-two-layer: 2026-09-18

Engine 0.3.0. Two new rules, and every finding now declares a layer.

* **`F5.MODEL_TIE`, accounting layer.** Reconciles the FP&A model to the ledger using the
  CURRENT forecast vintage, whose closed months are the posted actuals. Where they differ,
  an entry has been staged and not booked, or the reverse. Lines carrying no vendor and no
  PO are flagged as manual overlays.

  This is the rule that surfaces the `Claude Reclass: Labs to CMC` topside: $4,470,029.85
  across four months, sitting in the model with no vendor, no PO and line numbers inserted
  out of sequence, against a ledger that never received it. It is the top two findings of
  the Aug 2026 run. A second annotated overlay, `Lab Vendors that hit Facilities in error`,
  comes out alongside it.

  Runs only where the model carries that account and department. The build tabs do not plan
  payroll or depreciation, so comparing a modelled zero against real salary expense would
  report the whole payroll run as a difference every month and bury the lines that matter.

* **`F2.BUDGET`, FP&A layer.** Actual against plan, using the JUNE vintage, which predates
  the month. Only where a plan line exists: an account the forecast never planned is a
  coverage gap, not an overspend. The uncovered population is carried in
  `manifest.budget_coverage`, which for Aug 2026 is 48 keys worth $1,597,712.43.

* The budget feed is read from the `--pending` directory like any other supplied feed. The
  model file is an explicit `--model` flag, because reconciling to the ledger is a different
  question from measuring against plan and should be switched on deliberately.

* Findings sort by layer, then by amount, so the artifact order is the order of the work.

* The variance recommendation no longer asks for a timing / structural / coding call. It
  asks what drove the movement and whether the period is misstated.

Aug 2026: 135 findings, $10,415,498.03. 17 accounting, 118 FP&A.

### Ruleset 2026.09-uc2-flux-threshold: 2026-09-17

Engine 0.2.0.

> **Correction, 2026-10-01.** The "95 findings, $4,883,211.33" figure is the whole run:
> 90 F1.VARIANCE findings worth $4,783,473.76 plus 5 F3.ACCRUAL_RECEIPT findings worth
> $99,737.57. A note dated 2026-09-18 withdrew it as unreachable against a $4,825,047.03
> ceiling, but that ceiling covers the variance population only. The figure and the
> Project-versus-local comparison that relied on it stand.

* **Reporting floor lowered to $2,500** from the $10,000 policy threshold. The engine
  now emits every variance at or above $2,500 and the console decides which reach the
  queue, so the commentary threshold can move without rerunning the engine and the
  population just under it can be totalled instead of being invisible. 60 → 95 findings
  emitted; at the default $10,000 threshold the queue is still 59, with 36 items worth
  $196,923 totalled below it.
* Report block declares `fix_threshold`, `fix_threshold_presets`, `reporting_floor`,
  `band_labels` and `dimensions`.

### Ruleset 2026.09-uc2-flux-core: 2026-09-17

* **Month-over-month and year-over-year merged onto one finding.** 26 account and
  department pairs were being put in front of the reviewer twice for what is one
  conversation. **86 findings → 60.** A variance is a property of the line, not of the
  comparison.
* Receipt-based accrual identification from Coupa: $110,105 for Aug 2026.
* Open PO commitments ($1,369,533) reported as a disclosure and never accrued.

## GL Coding Review engine

### Ruleset 2026.09-uc1-coding-only+coupa

Coding intelligence only. Accrual, prepaid and fixed-asset tests are out of scope for this
version, pending a decision on where the use-case boundary sits.

---

## Not yet ratified

No rule in either engine has been signed off by an accountant. Every threshold comes
from Serif's DRAFT, unapproved policies, and every finding says so. A ruleset bump will
invalidate any sign-off obtained before it, see `../questions for chris.txt`.
