# Feed Templates

The `.csv` files here are header-only templates for data Unity has not yet provided, except
`coupa_dept_code_mapping.csv`, which carries the Coupa department codes found so far. The
headers are the exact column names both agents expect. `tools/package.py` copies each Project
the templates it reads. To activate a feed, fill the file with real rows and keep the filename
and header unchanged.

Both agents are written to run with any subset of these present.
A missing file degrades one analysis stream; it does not block the run.
Each agent reports which feeds were absent and which findings were therefore suppressed.

## Do Not Invent Rows

Leave a file header-only until real data arrives.
An agent seeing a header-only file reports the stream as unavailable, which is correct.
An agent seeing plausible-looking fabricated rows reports findings that are not real, which is worse
than reporting nothing.

## What Each File Feeds

* `netsuite_vendor_master.csv`: vendor country, type, related-party flag, default coding
  - Feeds: GL Coding Review entity and department tests
  - Without it: vendor classification falls back to the most-used-coding baseline in each agent's
    `reference/client-vendor-coding-baseline.md`, at reduced confidence
* `budget_fy2026_by_account_dept_month.csv`: forecast by account, department, month
  - **POPULATED 2026-09-18.** 1,990 rows carrying the **June 2026** vintage, extracted from the
    `EXT$_R&D`, `EXT$_G&A`, `LAB` and `OH` tabs of `../real/rolling_forecast_2026-08.xlsx`
    by `../../tools/forecast_to_csv.py`
  - Feeds: budget variance in both agents
  - Read `../../../FORECAST-LAYER-FINDINGS.md` before relying on it. Four things matter:
    - It is a rolling forecast, not an approved budget, so `approved_by` and `approved_date` are empty
    - It is deliberately the JUNE cut, not August. The August vintage's closed months are the posted
      actuals, so a comparison against it is a model-to-ledger reconciliation rather than a budget
      test. June ties to only 1 of 32 comparable Aug 2026 accounts against August's 30 of 37
    - It covers external spend and overhead only. Payroll lives on `FTE$` and depreciation on
      `FA_CAP`, so 29% of Aug 2026 P&L actuals have no budget line
    - Neither engine has a budget rule yet. Verified by running UC2 with this feed populated and
      again emptied: output is identical apart from the absent-feed count
* `forecast_lines_2026-06.csv`: the June vintage before aggregation, 3,115 lines
* `forecast_lines_2026-08.csv`: the August vintage before aggregation, 3,067 lines
  - Both keep vendor, PO number, project and description, which is what makes a variance explainable
    without reopening the workbook
  - Neither is a feed either engine reads today
  - The August file is what surfaces the $4.47M `Claude Reclass: Labs to CMC` topside
* `unmapped_forecast_accounts.csv`: the 10 categories that could not be placed
  - A data ask for Unity, with `gl_account_code` and `gl_account_leaf` left blank to fill in
  - Carries a `reason` column separating unknown accounts from rows whose department or account is
    blank in the workbook
  - Largest is `FSP Charges – PBU` at $2.7M, a June name the August cut renamed to
    `FSP Charges - Origination`. Confirm rather than guess
* `payroll_register.csv`: batch-level gross, employer burden, and GL coding by employee
  - Feeds: payroll-to-GL tie-out, payroll cutoff accrual
  - Source system is ADP, which is confirmed present in the GL
* `hris_headcount.csv`: employee to department, org, FTE, salary
  - Feeds: headcount reconciliation, salary variance explanation, payroll department source of truth
  - The UKG roster is in `data/real/`. The schedules step reads it for department
    checks; this template, which asks for salary per person, stays empty.
* `fixed_asset_register.csv`: existing PP&E, useful lives, accumulated depreciation
  - Feeds: PP&E duplicate detection, depreciation continuity
  - Unity has live fixed asset accounts (`1510000`, `1530000`, `1590000`), so a register exists
* `prepaid_amortization_schedule.csv`: open prepaids and amortization
  - Feeds: prepaid recode proposals, prepaid rollforward
  - Unity has four live prepaid accounts (`1305000`, `1310000`, `1315000`, `1320000`)
* `accruals_log.csv`: posted and proposed accruals with reversal periods
  - Feeds: duplicate-accrual prevention in both agents
  - Unity has seven live accrual accounts under `2200000`
* `open_purchase_commitments.csv`: goods and services received, not yet invoiced
  - Feeds: accrual identification
  - **Largely superseded 2026-09-16.** Coupa is live and its PO export now supplies this directly:
    see `../real/coupa_po_lines_<period>.csv`, column `received_not_invoiced_value`. Keep this
    template only for non-PO commitments Coupa does not capture.
* `coupa_dept_code_mapping.csv`: the nine Coupa department codes mapped to GL department names
  - Feeds: attributing Coupa PO spend to a Unity department in both agents
  - Without it: Coupa comparisons work at account and supplier level only, not by department
  - Pre-filled with each code's CY2026 line count, spend, and most-used GL accounts so Unity has
    context to answer. Codes are `13`, `73`, `9`, `55`, `40`, `2`, `15`, `23`, `5`.
  - **Do not guess a mapping.** Volume correlation is not conclusive: `13` and `73` both point at
    Platform, and `9` and `55` sit near 50%.
* `external_research_spend_detail.csv`: sequencing, synthesis, in vivo, and CMC unbilled WIP
  - Feeds: external research accrual, the largest single accrual risk in Unity's P&L
  - Maps to accounts `6501000`, `6501100`, `6502000`, `6502500`, `6504000`
* `accepted_exceptions.csv`: findings a reviewer has accepted (vendor, account, reason, approver)
  - Feeds: GL Coding Review. A matching department or account finding (T1, T4) is kept, counted and marked excepted with its reason
  - Reviewer-maintained, header-only until the first row. It is data, not a rule change
  - Without it: nothing is excepted
* `ebitda_addback_mapping.csv`: credit agreement add-backs mapped to the NetSuite dimension
  - Feeds: adjusted EBITDA reporting and add-back tagging
  - The Data Entry Policy requires this dimension on qualifying transactions, so the mapping file
    it refers to is a live control document, not a nice-to-have

## Naming a Period

Where a feed is periodic, append the period to the filename when you drop it in:

```sh
payroll_register_aug2026.csv
accruals_log_aug2026.csv
```

Keep the base name and header row exactly as given so the agents still recognize the file.

See [`../docs/DATA-MANIFEST.md`](../docs/DATA-MANIFEST.md) for the full real-versus-pending picture and
the open questions for Unity.
