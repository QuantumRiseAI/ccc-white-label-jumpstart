# Serif P&L Flux: Claude Project

Same shape as the GL Coding Review project.

* **`upload-to-project/`**: configure once. Upload all of it.
* **`monthly-inputs/`**: Serif's exports for a close, exactly as each system writes them.
* `out/`: what the run produces. Not uploaded.

## Configure Once

Paste `upload-to-project/PROJECT_INSTRUCTIONS.md` into the Instructions field and upload
every other file in `upload-to-project/` except `STATUS.md`.

## Each Month

Add the month's exports, as the systems write them:

| Export | What it is |
|---|---|
| `netsuite_gl_<range>.xls` | NetSuite Custom General Ledger saved search. Together the exports hold the month, the six before it and the same month last year. |
| `coupa_po_lines_<year>.csv` | Coupa PO line report with all available columns, for the calendar year |
| `serif_rolling_forecast_<vintage>.xlsx` | The workbook FP&A saved after the month closed, and the one whose prior cut is the plan |
| `ukg_full_roster_hrbp_<date>.csv` | The newest UKG roster |
| `netsuite_income_statement_*.xls`, `netsuite_balance_sheet_*.xls` | Reported statements, for reference |

Then say: *"Run the P&L flux for Sep 2026."*

## What Comes Out

`out/<period>/serif-pl-flux-<period>-v<version>.html`.
The filename carries the console version; see [`../CHANGELOG.md`](../CHANGELOG.md).

Aug 2026 reference run: 99 findings, 14 proposed Journal Entries, accrual population
**$110,105**, open PO commitments **$1,369,533** reported as a disclosure and **not**
accrued.

## The Distinction That Matters Most

* **Received not invoiced**: goods arrived, no bill yet. Expense belongs in the period.
  This is the accrual population.
* **Open commitment**: ordered, nothing received. Nothing is accruable.

Confusing the two overstates August by more than 12x. The engine keeps them apart and the
report labels both.

## Requirements

Python 3.9+. Nothing else.

See [`upload-to-project/HOW-TO-RUN.md`](upload-to-project/HOW-TO-RUN.md) and
[`upload-to-project/WHEN-DATA-BREAKS.md`](upload-to-project/WHEN-DATA-BREAKS.md).
