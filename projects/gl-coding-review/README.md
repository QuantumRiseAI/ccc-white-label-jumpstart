# Serif GL Coding Review: Claude Project

What this Project carries that the other does not: [`PROJECT_INSTRUCTIONS.md`](PROJECT_INSTRUCTIONS.md),
[`HOW-TO-RUN.md`](HOW-TO-RUN.md) and the files beside them. The scripts are in `../../src/`, the
docs both Projects carry in `../shared/`, and the feed templates in `../../templates/`.
`make package` puts them all in one flat folder, `out/dist/gl-coding-review/`, for the Project.

## Configure Once

Run `make package` from the repo root. Paste `out/dist/gl-coding-review/PROJECT_INSTRUCTIONS.md` into the
Project's Instructions field and upload every other file in `out/dist/gl-coding-review/`. The header-only
templates look empty on purpose: their presence is how the agent reports a feed Serif has not
sent.

## Each Month

Add the month's exports, as the systems write them:

| Export | What it is |
|---|---|
| `netsuite_gl_detail_<range>.xls` | NetSuite Custom General Ledger saved search. Together the exports hold the month, the two before it and the same month last year. |
| `coupa_po_lines_<year>.csv` | Coupa PO line report with all available columns, for the calendar year |
| `netsuite_income_statement_by_month_<range>.xls` | NetSuite Income Statement by month, through the month. The ledger is tied to it by account before the review is built. |
| `serif_rolling_forecast_2026-08.xlsx` | The workbook whose prior cut is the plan, until Serif sets a new one |
| `ukg_full_roster_hrbp_<date>.csv` | The newest UKG roster |

Then say: *"Run the GL coding review for Sep 2026."*

## What Comes Out

`serif-gl-coding-review-<period>-v2.0.0.html`, in the Project or in
`out/<period>/gl-coding-review/`: one self-contained file, laid out as the controller's August
GL review, that opens in any browser with no server. That is the deliverable. The current
version is `../../consoles/serif-gl-coding-review.html`; each earlier one is tagged
`console-v<version>` in Git. See [`../../CHANGELOG.md`](../../CHANGELOG.md).

Aug 2026 reference run: 56 findings, 50 proposed Journal Entries, tie-out PASS (engine 0.2.4).

## Requirements

Python 3.9+. Nothing else: no `pip install`, no Node, no network.

See [`HOW-TO-RUN.md`](HOW-TO-RUN.md) for the commands
and [`../shared/WHEN-DATA-BREAKS.md`](../shared/WHEN-DATA-BREAKS.md) for
what to do when an export arrives in the wrong shape.
