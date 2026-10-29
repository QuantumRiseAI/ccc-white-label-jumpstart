# Data Manifest

Every file in this package, where it came from, and what is still missing.

Generated 2026-09-16 by Quantum Rise.

## Real Unity Data

All originals are Unity exports, unmodified in content.
They were renamed for consistency and kept in `data/real/` in OneDrive (not in Git). A close's
exports for the build go in `inputs/<period>/`.
Original names are recorded here so provenance survives the rename.

| Now | Originally | What it is |
|---|---|---|
| `netsuite_gl_detail_jan2025-aug2026.xls` | `CustomGeneralLedger-298.xls` | NetSuite Custom General Ledger, Jan 2025 – Aug 2026, 44,013 lines, ~58 MB |
| `netsuite_balance_sheet_monthly_sep2021-aug2026.xls` | `BalanceSheet889.xls` | Monthly balance sheet, 60 periods |
| `netsuite_income_statement_by_month_jan2025-aug2026.xls` | `IncomeStatement-585.xls` | P&L by month, 20 periods |
| `netsuite_income_statement_by_dept_jan-aug2026.xls` | `IncomeStatement-116.xls` | P&L by department, YTD Aug 2026 |
| `netsuite_income_statement_by_dept_jan-jul2026.xls` | `IncomeStatement631.xls` | P&L by department, YTD Jul 2026 |
| `netsuite_income_statement_by_dept_jan-jun2026.xls` | `IncomeStatement-681.xls` | P&L by department, YTD Jun 2026 |
| `rolling_forecast_2026-08.xlsx` | `2026-08 Rolling Forecast.xlsx` | 55-sheet rolling forecast workbook |
| `client_5yr_pl_reforecast_jun2026_dataroom.pptx` | `5 Year P&L_(Jun_Reforecast)_(Dataroom_Update)ii_AO_(20260622).pptx` | Board reforecast deck |
| `client_bod_forecast_jun2026_draft.pptx` | `Unity 2026.06-BOD_Forecast_(20260420.Draft.Review.w.Jake)_(4.Justine+Avak).pptx` | Board forecast deck |
| `ukg_full_roster_hrbp_2026-09-24.csv` | `Full Roster_HRBP a7fafe039.csv` | UKG full employee roster, 72 active employees, 32 columns including department, supervisor and job title |
| `netsuite_link_ids_aug2026.csv` | `netsuite_link_ids_aug2026.csv` | NetSuite SuiteQL result from `netsuite_link_ids.sql`, run through the NetSuite connector in Unity's Claude instance on 2026-09-30: 3,264 posting lines of Aug 2026 with internal IDs, Coupa invoice addresses and Coupa PO numbers. Ties to the GL export ($14,467,758.34 each side). Used for console links only; in `monthly-inputs/aug2026/` |

The UKG roster carries employee personal data (names, email addresses, gender, salary). It is a
client-confidential HR record: keep it out of any repository and out of any deliverable. It sits
in the two Unity Claude Projects, on Unity's own Claude instance, because the schedules need it. `client_views.py` reads it
only to resolve a person to a department, and writes no name, email address or salary.

UKG's `Department Code` is Coupa's department code with a letter prefix (`L9` is Coupa `9`), so
the roster also resolves the Coupa department codes. The schedules read that mapping from the
roster in memory.

The `.xls` files are SpreadsheetML, XML with an `.xls` extension, not binary Excel.
Any loader must parse them as XML.

### Derived

Neither engine reads these. Both read the exports in `data/real/` directly, through
`client_sources.py` and the coding engine's own readers. `data/real/derived/` holds the
per-period CSVs the tools in `tools/` produced, for reference.

From the GL export, via `tools/netsuite_gl_to_csv.py`:

* `netsuite_gl_aug2026.csv`, 2,713 lines, nets to $0.00
* `netsuite_gl_jul2026.csv`, 2,407 lines, nets to $0.00
* `netsuite_gl_aug2025.csv`, 2,667 lines, nets to $0.00
* `netsuite_gl_feb2026.csv` to `netsuite_gl_jun2026.csv`, 2,929, 2,381, 2,466, 2,117 and
  2,538 lines, each netting to $0.00. The trailing months the billing-pattern accrual,
  the prepaid and vendor tests and the three-month trend read
* `netsuite_account_activity_<period>.csv`, net movement by account and department

These activity files are not trial balances.
They sum only the transactions posted in that period.
For P&L accounts that equals the period's expense, which is what flux analysis needs.
For balance sheet accounts it is the period movement, not the ending balance, because no
prior-period carryforward is included.

From the Coupa PO export, via `tools/coupa_po_to_csv.py`:

* `coupa_po_lines_jan2026.csv` through `coupa_po_lines_sep2026.csv`, 9,571 lines, $21.1M total

The Coupa tool was written 2026-09-16 to make these files reproducible; the first set was produced
ad hoc without one. It reproduces the original 25 columns exactly and adds four:
`approved_invoiced`, `active_invoiced`, `received_not_invoiced_qty`, and
`received_not_invoiced_value`. Two deliberate departures from the original files: `need_by` is
normalized to ISO for consistency with `order_date`, and `item_name` is no longer truncated.

Traps the tool handles, each of which silently corrupts a naive read:

* The `Department` column is **empty on every row**. The real department code is the third segment
  of the packed `Account` string (`97-<account>-<dept>-<seg3>-<seg4>`).
* The `Period` column reads `None` on every row. Period comes from `Order Date`.
* Amounts carry thousands separators, so a bare `float()` returns 0.0 and understates totals
  roughly tenfold.
* `Received`, `Active Invoiced` and `Approved Invoiced` are **quantities, not amounts**. Quantity
  times `Price` is unreliable on bulk-price lines; pro-rating `Line Total` is not.

Two "open" populations that must never be conflated:

* `is_open_commitment`, ordered, live PO, not yet received. $7,989,306 for CY2026. **Not an
  accrual**; nothing has been received.
* `received_not_invoiced_value`, received, not yet invoiced. $401,845 for CY2026, $110,105 for
  Aug 2026. **This is the accrual population.** It is a floor: 279 lines have no quantity and
  cannot be pro-rated.

To add a period:

```sh
python3 tools/netsuite_gl_to_csv.py \
  data/real/netsuite_gl_detail_jan2025-aug2026.xls \
  --out data/real/derived \
  --period "Sep 2026"
```

Then copy the new files into whichever agent folder needs them.

### Distribution to Agent Folders

Each agent has its own copy so a Claude Project uploads from one place.

* `gl-coding-review/data/real/`, the three GL detail CSVs, the three activity files, and the
  Aug and Jul 2026 Coupa files
* `pl-flux/data/real/`, the three activity files, the three GL detail CSVs, both income statements,
  the balance sheet, the rolling forecast, and the Aug and Jul 2026 Coupa files

There is no Coupa file for Aug 2025, so the YoY comparative has no procurement data behind it.
The export covers calendar 2026 only.

The 58 MB GL export stays only in `data/real/`.
It is too large to upload and exists to be sliced, not loaded.

## Policies

Copied from `../synthetic-jumpstarts/Policies/` and renamed.
Originals are unchanged.

| Copy | Original | GL Coding | P&L Flux |
|---|---|---|---|
| `client-data-entry-policy-DRAFT.docx` | `DRAFT_Unity_Data_Entry_Policy_Sample.docx` | Yes, core rulebook | Yes |
| `client-finance-threshold-policy-DRAFT.docx` | `DRAFT_Unity_Finance_Threshold_Policy.docx` | Yes | Yes |
| `client-accrued-expense-policy-DRAFT.docx` | `DRAFT_Unity_Consolidated_Accrual_Policy.docx` | Yes | Yes, core policy |
| `client-prepaid-expense-policy-DRAFT.docx` | `DRAFT_Unity_Prepaid_Policy_Sample.docx` | Yes | Yes |
| `client-tangible-intangible-asset-policy-DRAFT.docx` | `DRAFT_Unity_Fixed_Asset_Policy_Sample.docx` | Yes | Yes |
| `client-intercompany-policy-DRAFT.docx` | `DRAFT_Unity_Intercompany_Policy.docx` | Yes | No |
| `client-severance-accounting-policy-DRAFT.docx` | `DRAFT_Unity Severance_Accounting_Policy.docx` | No | Yes |
| `client-ebitda-addback-dimension-DRAFT.xlsx` | `DRAFT Unity Potential EBITA Addbacks that Track.xlsx` | Yes | Yes |

### Excluded, and Why

* `DRAFT_Global_Treasury_Cash_Management_Hedging_Policy_v1.docx`, **this is not a Unity document.**
  It names CrossCountry Consulting as the company, Investcorp as the PE sponsor, Sage Intacct as the
  system of record, and roughly 35 cost centers.
  It is CCC's own treasury policy, filed in the Unity policy folder.
  Excluded from both agents. Worth raising with CCC, since its presence here suggests the policy
  pack was assembled from a template set rather than from Unity's actual documents.
* `DRAFT_Unity Foreign_Currency_Conclusion.docx`, a functional currency memo whose only analyzed
  entity is India.
  Unity's export shows one US subsidiary and no India entity.
  Excluded pending confirmation of what it belongs to.
  Revisit if a foreign entity appears; Unity does post to FX accounts `8231000` and `8232000`.

## Correction to the Coupa Department Code Template

`coupa_dept_code_mapping.csv` was first written with the codes `13, 73, 9, 55, 40, 2, 15, 23, 68`.
Two of those are wrong.

* **`68` is not a department code.** It is segment 3 of the packed `Account` string, which appears
  on 324 lines. The department code is segment 2.
* **`5` was missing.** It is a real department code, appearing once, on a $6,500 DiFilippo Corporate
  Finance 409A valuation coded to `6340000`.

The corrected code set is `13, 73, 9, 55, 40, 2, 15, 23, 5`, verified against all 9,571 lines. The
template now carries each code's CY2026 line count, spend, and most-used GL accounts so Unity has
context to answer with.

Note that the parser behind the derived files had this right, its `coupa_dept_code` column is
correct, and only the template was wrong. Anything already produced from the derived files is
unaffected.

## Pending Data

Header-only templates in `templates/`, copied into each Project's folder by `tools/package.py`.
See [`../templates/README.md`](../templates/README.md) for per-file detail.

Ranked by impact:

* **Budget by account, department, month.** ~~The single largest gap.~~
  **Resolved 2026-09-18.** Extracted from `rolling_forecast_2026-08.xlsx` by
  `tools/forecast_to_csv.py`, which reads the `EXT$_R&D`, `EXT$_G&A`, `LAB` and `OH` line-item tabs.
  The workbook carries both the August and the June vintage side by side, and the feed uses **June**,
  because August's closed months hold the posted actuals rather than a forecast.
  Three caveats travel with it, set out in
  [`../FORECAST-LAYER-FINDINGS.md`](../FORECAST-LAYER-FINDINGS.md): it is a rolling forecast rather
  than an approved budget, it covers external spend and overhead only so 29% of a month's P&L actuals
  have no plan line, and neither engine had a budget rule until UC2 0.3.0.
  Do not map account names through the workbook's `COA` tab; it disagrees with the live ledger on 21
  of 65 shared names.
* **Payroll register and HRIS headcount**, blocks payroll tie-out, headcount reconciliation, and
  salary variance attribution. ADP is confirmed as the payroll system and UKG as the HRIS.
  **HRIS roster received 2026-09-24**, in `data/real/`. It feeds the requester-versus-coding
  schedule and the Coupa department mapping. It is not loaded into `hris_headcount.csv`, whose
  template asks for salary, and neither engine reads it. The payroll register is still pending.
* **Vendor master**, degrades coding confidence; the most-used-coding baseline is the fallback.
* **External research unbilled WIP**, Unity's largest accrual exposure given the volume in
  sequencing, synthesis, in vivo, and CMC.
* **Accruals log**, needed to prevent duplicate accrual proposals.
* **Prepaid schedule and fixed asset register**, needed for continuity and duplicate detection.
* **Open purchase commitments**, only if Unity has a procurement system, which is unconfirmed.
* **EBITDA add-back mapping**, the Data Entry Policy points at this file; it is a live control
  document, not optional.

## Systems: What Unity Actually Runs

Absence from the general ledger is not absence from the company. A procurement system sits
upstream of the ledger and leaves no vendor record in it, so the ledger alone cannot establish
which systems Unity runs.

| System | Status | Evidence |
|---|---|---|
| NetSuite | Confirmed | Source of every export |
| ADP | Confirmed | `ADP Inc` vendor record, `6845000 - Payroll Service`, recurring "ADP Payroll Fees" journals |
| Expensify | Confirmed | 1,095 `Expense Report` lines carrying Expensify report URLs in the memo |
| **Coupa** | **Confirmed, live since ~Sept 2025** | Client confirmation, with a 9,571-line PO export for calendar 2026 |
| **Prendio** | **Confirmed, Coupa's predecessor** | Client confirmation: used before Coupa; only a limited set of POs was migrated manually, under a different PO numbering convention |
| **UKG** | **Confirmed, this is the HRIS** | Client confirmation. Roster export received 2026-09-24 |
| Adaptive Planning | Absent from the ledger, **unconfirmed with Unity** | No vendor; budget appears to live in the Excel rolling forecast |

**A system being invisible in the general ledger is not evidence it is not in use.** The Adaptive
Planning row rests on exactly that weak inference and should be put to Unity directly rather than
carried forward.

[`../REAL_DATA_GAPS.md`](../REAL_DATA_GAPS.md) is **superseded** by this manifest and
carries a banner saying so.

## Coupa PO Data: Received 2026-09-16

Source: `Coupa_Data_Pull_(PO_Lines)_(20260916-1000).csv`, a custom Coupa report built with all
available columns and supplied by Unity on 2026-09-16.

| File | What it is |
|---|---|
| `data/real/coupa_po_lines_2026.csv` | Raw export as received. 9,571 PO lines, 103 columns, calendar 2026, $21.1M |
| `data/real/derived/coupa_po_lines_<period>.csv` | Normalized per-period slices, 9 periods Jan–Sep 2026 |
| `gl-coding-review/data/real/coupa_po_lines_{aug,jul}2026.csv` | The two periods the GL agent uses |

Produced with `packages/coupa_extract` in the `ccc-client-jumpstarts` repo:

```sh
py -m coupa_extract data/real/coupa_po_lines_2026.csv --out data/real/derived
```

### Why this matters to the coding review

Coupa's `Account` field (`97-6410000-9--4`) carries the **NetSuite GL account a requisition was
approved against**. That is a *normative* coding expectation, recorded before anyone coded the
bill, categorically stronger evidence than the vendor coding baseline, which only records what
Unity habitually does. Comparing the two on Aug 2026 finds 61 suppliers in agreement and **10 in
disagreement**, including New England BioLabs (GL `6501100` Synthesis vs Coupa-approved `6410000`
Lab Supplies across 44 GL lines).

### Known limits: carry these into any readout

* **This is one of three tabs.** The source report covers 2025, 2026 and Open; only 2026 was
  supplied. The 2025 tab and the Open PO report have not arrived.
* **No line-level join to the GL.** The export has no `NetSuite PO Ref`, and none of the 3,664 PO
  numbers appear among the GL document numbers. Every comparison is at **supplier** level.
* **Coupa went live ~Sept 2025**, with Prendio before it and a partial manual migration. Absence of
  a PO before that date proves nothing about off-PO spend.
* **Department codes are mapped through UKG, not confirmed by Unity.** UKG's department codes
  are Coupa's with a letter prefix, which resolves all nine: 2 General G&A, 5 Finance, 9 General
  R&D, 13 Platform, 15 In Vivo, 23 "502 Finance - Fund", 40 Chemistry, 55 Biology, 73
  Production. Inference from the ledger alone had put 13 and 73 both at Platform; UKG puts 73 at
  Production. Code 23 names no ledger department. The file is
  `derived/coupa_dept_code_mapping_from_ukg.csv`; the template for Unity to confirm is still
  `data/pending/coupa_dept_code_mapping.csv`.
* **`Department` and `Period` columns are empty** on all 9,571 rows.
* **Open commitment is derived**, not read: order still `Issued`, not cancelled, not fully
  received. 900 lines, $7.99M.

### Line-Level Description Is Present, Under Other Names

The export carries no column called `Description`, but three fields hold line-level
descriptive text and all are populated on every one of the 9,571 rows:

| Column | Populated | Example |
|---|---|---|
| `Item` | 100% | `Lipofectamine 3000 Transfection Reagent, 1.5 mL` |
| `Detailed Item` | 100% | `1 Each of Lipofectamine 3000 Transfection Reagent, 1.5 mL` |
| `Commodity` | 100% | `Other Lab Supplies`, `Other Custom Services` |

`Comments` is populated on 6.7% of rows and is approval chatter rather than description.
`Item Name`, `Line Owner`, `Source Details` and `Form Response` are empty throughout.

`Item` and `Commodity` are usable evidence for coding tests, `Commodity` in particular is
a categorization Coupa already applies, and is an independent expectation to test account
coding against. Neither is currently used by either engine.

### Projects Are Not Used

Unity does not use project coding. Project-dimension tests are therefore recorded as **not
applicable** in both consoles rather than suppressed silently or filled with a placeholder
value. The rule logic covers the dimension and will apply with no change if projects are
adopted later.

### Journal Entry Import Template

NetSuite's journal-entry import format is per-tenant. Unity's own CSV template has not
been supplied, so the NetSuite CSV uses a generic column order: External ID, Date, Account,
Department, Debit, Credit, Memo. Adopting the real template is a change to `exportCSV()` in
`build_pages.py` and nothing else.

### Columns CCC asked for that this export does not contain

The PO Register field list requested from Unity is not fully covered by the "all available
columns" report. Each missing column keeps a test dark:

| Column | What stays unavailable |
|---|---|
| `NetSuite PO Ref` | Line-level PO-to-GL join |
| `Budget Check Status` | Budget-check-failure test |
| `Open Commitment` | Read rather than derived |
| `Amount Invoiced` | Three-way match |
| `Amount Paid` | Payment status and on-hold tests |
| `Requisition ID` | Requisition-to-PO traceability |
| `Requester Dept` | Requester-vs-coding department mismatch |
| `Project Code` | PO-level project validation |

**Correction, 2026-09-18.** This table previously listed `Requester` alongside `Requester Dept` as
absent. The requester is present.
`Requested By (Header)` carries a person's name on 100% of the 9,571 lines, across 62 distinct names,
as do `Created By` and `Line Owner`.
Only that person's department is missing, and it has to come from UKG rather than from Coupa.
A column named `Department` does ship in the export, but it is empty on all 9,571 rows, as are 25
other columns, so checking column names alone will mislead.

The same correction applies to the engine source, where `COUPA_MISSING_COLUMNS` bundles both halves
behind one key and the normalization docstring lists `Requester` flatly among absent columns.
Both overstate the gap.

Worth raising on the next call: the remaining columns may be available as additional Coupa report
fields, or may require broader Coupa reporting access, which Unity has requested internally.

## Filename Cleanup in the Synthetic Package

Download-artifact suffixes were removed from `../synthetic-jumpstarts/`:

* `Flux/Instrutions and Skills/` renamed to `Instructions and Skills/`, typo corrected
* `PROJECT_INSTRUCTIONS (16).md` and `GL_CODING_REVIEW_SKILL (2).md`, suffixes dropped
* `client_econtroller_command_center (3).html` and `gl-coding-review (3).html`, suffixes dropped
* Twelve `… (1).csv` duplicates, removed where byte-identical to their twin, renamed otherwise

One pair was not identical and both were kept:

* `GL Coding/Synthetic Inputs/adaptive_budget_fy2025.csv`, 17 rows, includes a `Source` column and
  an interest expense row
* `GL Coding/Synthetic Inputs/adaptive_budget_fy2025_variant-no-source-column.csv`, 16 rows, no
  `Source` column, byte-identical to the Flux folder's copy

No file content was modified anywhere in the synthetic package.
