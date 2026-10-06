# Serif P&L Flux: Claude Project

What this Project carries that the other does not: [`PROJECT_INSTRUCTIONS.md`](PROJECT_INSTRUCTIONS.md),
[`HOW-TO-RUN.md`](HOW-TO-RUN.md) and the files beside them. The scripts are in `../../src/`, the
docs both Projects carry in `../shared/`, and the feed templates in `../../templates/`.
`make package` puts them all in one flat folder, `out/dist/pl-flux/`, for the Project.

## Configure Once

Run `make package` from the repo root. Paste `out/dist/pl-flux/PROJECT_INSTRUCTIONS.md` into the
Project's Instructions field and upload every other file in `out/dist/pl-flux/`. The header-only
templates look empty on purpose: their presence is how the agent reports a feed Serif has not
sent.

## Each Month

Add the month's exports, as the systems write them:

| Export | What it is |
|---|---|
| `netsuite_gl_<range>.xls` | NetSuite Custom General Ledger saved search. Together the exports hold the month, the six before it and the same month last year. |
| `coupa_po_lines_<year>.csv` | Coupa PO line report with all available columns, for the calendar year |
| `serif_rolling_forecast_<vintage>.xlsx` | The workbook FP&A saved after the month closed, and the one whose prior cut is the plan |
| `ukg_full_roster_hrbp_<date>.csv` | The newest UKG roster |
| `netsuite_balance_sheet_*.xls` | The Balance Sheet report, monthly columns, for Balance Sheet Flux and the tie-outs |
| `netsuite_income_statement_by_month_*.xls` | The Income Statement by month, for the tie-outs |

Then say: *"Run the P&L flux for Sep 2026."*

## What Comes Out

`serif-pl-flux-<period>-v2.0.0.html`, in the Project or in `out/<period>/pl-flux/`: one
self-contained file, laid out as the controller's August flux pack. The current version is
`../../consoles/serif-pl-flux.html`; each earlier one is tagged `console-v<version>` in Git. See
[`../../CHANGELOG.md`](../../CHANGELOG.md).

Aug 2026 reference run: 99 findings, 14 proposed Journal Entries, every tie-out passing,
accrual population **$110,105**, open PO commitments **$1,369,533** reported as a disclosure and **not**
accrued.

## The Distinction That Matters Most

* **Received not invoiced**: goods arrived, no bill yet. Expense belongs in the period.
  This is the accrual population.
* **Open commitment**: ordered, nothing received. Nothing is accruable.

Confusing the two overstates August by more than 12x. The engine keeps them apart and the
report labels both.

## Requirements

Python 3.9+. Nothing else.

See [`HOW-TO-RUN.md`](HOW-TO-RUN.md) and
[`../shared/WHEN-DATA-BREAKS.md`](../shared/WHEN-DATA-BREAKS.md).
