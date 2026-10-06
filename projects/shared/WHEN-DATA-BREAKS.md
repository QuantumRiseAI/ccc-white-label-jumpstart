# When the Data Does Not Fit

The scripts read each export exactly as its system writes it: the NetSuite Custom General
Ledger `.xls`, the Coupa PO line `.csv`, the rolling forecast `.xlsx` and the UKG roster
`.csv`. They are strict on purpose, so they stop rather than guess.

**Never build a file for the scripts to read. Ask for the export again.**

A sliced, converted, summarized or repaired copy of an export is a number nobody can trace
back to a system, and it will not be made the same way next month.

## What You May Do

* Rename a file so the command finds it, such as `netsuite_gl_sep2026.xls`. The contents
  stay exactly as exported.
* Leave out an export that holds nothing the run needs.

## Stop and Ask When a Script Stops

Say which file, and quote what the script said. Then say what to ask Serif for:

| The script says | Ask for |
|---|---|
| Row 6 is not the Custom General Ledger header | The saved search exported again as `.xls`, with the columns unchanged |
| A month is not in the NetSuite exports | The saved search for that month |
| A month is in two NetSuite exports | One export per date range, with no overlap |
| No `PO Number (Header)` column | The Coupa PO line report with all available columns |
| No forecast lines found | The rolling forecast workbook as FP&A saved it, with its build tabs |

Also stop when the tie-out fails. The export is incomplete; ask for a clean one.

## Never Touch These

* **The rules or thresholds.** If a threshold looks wrong, say so and stop.
* **The findings.** Do not add, remove, reword or re-rank one. Do not compute a finding
  yourself because a script would not run.
* **Rows and values.** Never drop a row, fill a blank or infer an amount.
* **The console.** Never edit the HTML, published or not. If it is wrong, the script changes
  and the console is built again.
* **Shared state.** In shared mode, decisions and notes live in the published artifact's
  database. Never copy them into `run.json` or an export, and never put the run, an export
  or the UKG roster into the artifact.

## Then Fold It Back

An export that changed shape once will arrive that way again. Flag it for Quantum Rise:
the reader in `serif_sources.py`, or in the coding engine, needs to learn the new shape, so
the next month runs on the export as it comes.
