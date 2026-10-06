# Serif GL Coding Review: Claude Project

Two folders. The names are the instructions.

* **`upload-to-project/`**: configure once. Upload all of it to the Claude Project.
* **`monthly-inputs/`**: Serif's exports for a close, exactly as each system writes them.
* `out/`: what the run produces. Not uploaded; regenerated every time.

## Configure Once

Paste `upload-to-project/PROJECT_INSTRUCTIONS.md` into the Project's Instructions field and
upload every other file in `upload-to-project/`. The header-only templates look empty
because they are: that is how the engine detects which feeds have not arrived and reports
the gap instead of quietly skipping a test.

## Each Month

Add the month's exports, as the systems write them:

| Export | What it is |
|---|---|
| `netsuite_gl_<range>.xls` | NetSuite Custom General Ledger saved search. Together the exports hold the month, the two before it and the same month last year. |
| `coupa_po_lines_<year>.csv` | Coupa PO line report with all available columns, for the calendar year |
| `serif_rolling_forecast_2026-08.xlsx` | The workbook whose prior cut is the plan, until Serif sets a new one |
| `ukg_full_roster_hrbp_<date>.csv` | The newest UKG roster |

Then say: *"Run the GL coding review for Sep 2026."*

## What Comes Out

`out/<period>/serif-gl-coding-review-<period>-v<version>.html`: one self-contained file,
opens in any browser, no server. That is the deliverable. The filename carries the console
version; see [`../CHANGELOG.md`](../CHANGELOG.md).

Aug 2026 reference run: 56 findings, 50 proposed Journal Entries, tie-out PASS (engine 0.2.1).

## Requirements

Python 3.9+. Nothing else — no `pip install`, no Node, no network.

See [`upload-to-project/HOW-TO-RUN.md`](upload-to-project/HOW-TO-RUN.md) for the commands
and [`upload-to-project/WHEN-DATA-BREAKS.md`](upload-to-project/WHEN-DATA-BREAKS.md) for
what to do when an export arrives in the wrong shape.
