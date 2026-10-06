# Serif Jumpstarts: Real Data Build

Two Claude Project agents adapted from the CrossCountry CrossCore AI Jumpstart to run on Serif
Biomedicines' actual NetSuite ledger instead of the synthetic dataset.

* Built: 2026-09-16 by Quantum Rise, last updated 2026-09-18
* Runs every month. Reference period: Aug 2026
* Status: runnable today on real GL and forecast data. Budget variance is live as of UC2 engine
  0.3.0, using the June forecast vintage extracted from the rolling forecast workbook

## Run Order: Coding Review First, Flux Last

These two sit at opposite ends of the close, and running them out of order wastes work.

1. **GL Coding Review** runs first, on the raw ledger.
   It tees up the corrections, so the accruals, prepaid and fixed-asset work in the middle of
   the close starts from a cleaner coding base.
2. The close proceeds: accruals booked, prepaids amortized, fixed assets recorded.
3. **P&L Flux** runs last, on the corrected ledger.
   It is the final check that the numbers are right, and it produces the commentary that goes
   to the senior leadership team.

Running flux on an uncorrected ledger surfaces variances that are really coding errors, so the
same item gets investigated twice. Coding Review first means fewer reclassifications to explain.

## Layout

```
serif-data-jumpstarts/
├── README.md                  you are here
├── DATA-MANIFEST.md           every file, its origin, and what is still missing
├── tools/                   cut the month's files; not uploaded to the Projects
│   ├── netsuite_gl_to_csv.py  slices the 58 MB GL export into per-period CSVs
│   ├── coupa_po_to_csv.py     slices the Coupa PO export, parsing its packed coding string
│   ├── forecast_to_csv.py     extracts a rolling forecast vintage into line and plan CSVs
│   ├── rebuild_views.sh       copies the shared scripts to gl-coding-review, rebuilds both consoles
│   ├── compare_runs.py        compares two run.json files field by field
│   └── test_*.js              console tests: shared mode, record save and load, run log
├── data/                      shared source of truth
│   ├── real/                  original Serif exports, renamed
│   │   └── derived/           per-period CSVs produced by the tool
│   └── pending/               header-only templates for data Serif still owes
├── gl-coding-review/          one Claude Project
│   ├── upload-to-project/     CONFIGURE ONCE: everything that goes in the Project, flat
│   ├── monthly-inputs/        EVERY MONTH: the period's data, dropped into a chat
│   │   └── aug2026/
│   └── out/                   where the run artifact and the console land
├── pl-flux/                   same shape
└── updated-ui/                both consoles laid out as Chris's August reports; see its README
    ├── upload-to-project/     one Claude Project for both: scripts, reference files, instructions
    ├── build_runs.sh, build_pages.py
    ├── runs/<period>/         the runs it reads (names and pay kept)
    └── out/<period>/          the two consoles
```

The split is the point. `upload-to-project/` is configured once and does not change month to
month. `monthly-inputs/<period>/` holds Serif's exports for a close, exactly as each system
writes them. Neither engine reads a sliced or derived file.

### In Git

The repo is private and holds only the scripts, instructions, skills, tests and the header-only
templates. `.gitignore` leaves out Serif's data and everything built from it, all of which stays
in OneDrive: `monthly-inputs/`, `data/real/`, `data/forecast-vintages/`, the forecast and budget
extracts in `data/pending/`, every `out/` folder and `updated-ui/runs/` (the runs and consoles
carry the ledger, names and pay), `status/`, and everything in `references/` except its README.
Office and export formats (`.xls`, `.xlsx`, `.pptx`, `.docx`, `.pdf`, `.eml`) are ignored
everywhere. To rebuild a month from a clone, put its exports back in `monthly-inputs/<period>/`
and in `data/real/`, then rerun the build.

## Setup

Two Projects, one per use case. They are not combined, because the two have different
instructions, different reference material and different run orders.

Configure once:

1. Create a Claude Project named `Serif Biomedicines, GL Coding Review` or
   `Serif Biomedicines, P&L Flux`.
2. Paste that folder's `upload-to-project/PROJECT_INSTRUCTIONS.md` into the Project Instructions
   field. It is instructions, not an upload.
3. Upload every other file in `upload-to-project/`.

Then each month:

4. Put Serif's exports for the month in `monthly-inputs/<period>/`, as each system wrote
   them. Each `HOW-TO-RUN.md` lists them under Each Month.
5. Start a fresh chat and attach them, or add them to the Project.
6. Prompt: `Run the GL coding review for Sep 2026.` or `Run the P&L flux for Sep 2026.`

Two things to know about Project uploads. They are **flat**, so the scripts are invoked by bare
filename. And the header-only template files must be uploaded, since their presence
is how each agent detects a missing feed and reports the gap instead of quietly skipping a test.

## What Changed From the Synthetic Package

The synthetic package described a company that does not exist.
Reading the real GL export made that unmistakable.

* **Entities**, synthetic assumed a US and an EU entity with cross-entity miscoding as the top
  severity class. Serif has exactly one subsidiary, `FL87 Serif Biomedicines, Inc.`, across all
  44,013 lines. The entire entity test is removed.
* **Chart of accounts**, synthetic used invented 4-digit accounts. Serif uses 7-digit hierarchical
  NetSuite account paths with 139 leaf accounts.
* **Departments**, synthetic used numeric 200/300/400. Serif uses ten department names, and 42% of
  lines sit in `Non-Specific`.
* **Source systems**: Coupa (since about Sept 2025, Prendio before it), UKG as the HRIS, ADP
  and Expensify. Adaptive Planning is unconfirmed.
* **Vendors**, the synthetic vendor table was largely fictional. Serif's real top vendors are
  Flagship Labs LLC, Fisher Scientific, Mirai Bio, New England BioLabs, and Aldevron. Corporate
  counsel is K&L Gates, not Cooley or Gunderson.
* **Business narrative**, the synthetic P&L Flux agent hard-coded an IRB dosing pause, a VP Legal
  hire, a Series B, and a $62.4K CRO accrual. All fictional. All removed.
* **Thresholds**, synthetic invented $25K and $50K materiality and a $5K PP&E threshold. Serif's
  own draft policies set $10,000 pre-close, $100,000 quarterly post-close, $5,000 accrual, $10,000
  prepaid, and **no fixed asset threshold at all**, deliberately.

The change log is [`CHANGELOG.md`](CHANGELOG.md).

## Two Additions Driven by the Real Data

* **Unallocated spend review**, in GL Coding. `Non-Specific` carries 18,391 of 44,013 lines. This is
  Serif's largest actual coding-quality issue and has no synthetic analogue.
* **Receipt-based accrual completeness**, in both agents. Coupa records goods receipts, so accruals
  are identified from what was received but not yet invoiced, roughly **$110K for Aug 2026** and
  **$402K for calendar 2026 to date**. A billing-pattern method (trailing three-month average, per
  Serif's Accrued Expense Policy) is the fallback for suppliers and periods Coupa does not reach.
  Open PO commitments, ordered but *not* received, about $1.37M in Aug 2026, are reported as a
  disclosure and never accrued.

## Honest Status

Real and working now:

* The NetSuite Custom General Ledger export, Jan 2025 to Aug 2026, read as NetSuite wrote it
* Every period ties out: debits equal credits to exactly $0.00
* Coupa PO lines for calendar 2026, 9,571 lines, $21.1M, read as Coupa wrote them
* The rolling forecast workbook, read for the plan and for Forecast vs. Actual
* Reported income statements and balance sheets for cross-checking
* Serif's real chart of accounts, department list, and how its top vendors are actually coded
* Serif's draft accounting policies as the threshold source

Not yet available, with placeholders in `data/pending/`:

* Payroll register (access request in flight). This is now the largest remaining gap: it
  blocks payroll tie-out. The UKG roster arrived 2026-09-24 and runs the
  requisitioner-versus-coding department check, as the requester flag on Vendors
* Vendor master, fixed asset register, prepaid schedule, accruals log
* Coupa invoice-level data, without which there is no three-way match
* The 2025 and Open tabs of the Coupa pull; only calendar 2026 arrived
* Serif's confirmation of the Coupa department code mapping, which is now read through UKG's
  department codes
* External research unbilled WIP detail
* The EBITDA add-back mapping the Data Entry Policy refers to

Both agents run with any subset present, name every absent feed in their load summary, and state
which findings are suppressed.
Nothing is fabricated to fill a gap.

## Caveats Worth Carrying Into the Readout

* All policies in the `reference/` folders are DRAFT and unapproved. Every threshold in both agents
  rests on unapproved documents.
* The vendor coding baseline is descriptive. It records what Serif does, which is not necessarily
  what Serif should do. It is evidence, not policy.
* The Treasury policy found in the Serif policy folder is CrossCountry Consulting's own policy, not
  Serif's. It is excluded from both agents. See [`DATA-MANIFEST.md`](DATA-MANIFEST.md).
* Accrual estimates are pattern-derived and need controller confirmation before anything posts.
* IRC §174 output is preliminary and needs tax counsel sign-off.

## Related

* [`DATA-MANIFEST.md`](DATA-MANIFEST.md), file origins, name mapping, and the full gap list
* [`../SERIF_REAL_DATA_GAPS.md`](../SERIF_REAL_DATA_GAPS.md), the earlier gap analysis prepared for
  the latest client confirmation, now superseded by the manifest.
* [`../synthetic-jumpstarts/`](../synthetic-jumpstarts/), the original CCC mock package, kept for
  reference
