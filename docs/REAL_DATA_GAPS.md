# Unity Jumpstarts — Real Data We Still Need

**Purpose:** Talking points for the call with **Scott & Chris** — what real Unity data
we'd need to collect so both Jumpstarts run on **actual client data**, not the
synthetic/mock dataset Chris originally built.

**Prepared:** 2026-09-15 · **For call:** next AM · **Status:** SUPERSEDED, kept as a record of what
was asked for on 2026-09-15

---

> **Read this before using anything below.**
> This was talking points for a specific call and several of its premises have since been answered.
> The body is preserved as a record of the asks rather than as current state.
>
> * **Coupa arrived 2026-09-16.** The 9,571-line CY2026 PO export is in hand. Its line-level item
>   descriptions are populated on 100% of lines, and the requisitioner name likewise. What it lacks
>   is listed in [`client-data-jumpstarts/DATA-MANIFEST.md`](client-data-jumpstarts/DATA-MANIFEST.md).
> * **The budget gap is closed.** The rolling forecast workbook is described below as summary-level.
>   It is not. Four tabs carry line-item detail with department, account, project, vendor, PO number
>   and description across 36 months, and both the August and June vintages sit in the same file.
>   See [`FORECAST-LAYER-FINDINGS.md`](FORECAST-LAYER-FINDINGS.md).
> * **Adaptive Planning is not in use.** Unity budgets in the Excel rolling forecast. The ask below
>   for a board-approved Adaptive budget has no counterpart at Unity.
> * **The HRIS is UKG, not Workday.** Access remains outstanding, and it is the one gap that still
>   blocks a named requirement, the requisitioner-versus-coding department check.
> * **Unity does not use project coding**, so project-dimension asks below are moot.
>
> Current state lives in [`client-data-jumpstarts/DATA-MANIFEST.md`](client-data-jumpstarts/DATA-MANIFEST.md)
> and [`client-data-jumpstarts/data/pending/README.md`](client-data-jumpstarts/data/pending/README.md).

## The core issue in one line

The two agents were designed around **transaction-level system exports** (NetSuite GL
detail, Coupa procurement, ADP/Workday payroll, Adaptive budget). The real Unity data we
have on hand is **statement-level** (finished Balance Sheet / Income Statements / forecast
decks). To retire the synthetic data, we need Unity to pull the **underlying system
extracts**, not just the reported financials.

---

## What real Unity data we already have

From `client-data-jumpstarts/data/`:

| File | What it is | Granularity |
|---|---|---|
| `CustomGeneralLedger-298.xls` | NetSuite GL export | **Transaction-level** (most useful) |
| `BalanceSheet889.xls` | Balance sheet | Statement-level |
| `IncomeStatement-116 / -585 / -681 / 631.xls` | 4 income statements (periods TBD) | Statement-level |
| `2026-08 Rolling Forecast.xlsx` | Rolling forecast | Summary-level |
| `5 Year P&L (Jun Reforecast) … .pptx` | Board reforecast deck | Presentation (charts, not data) |
| `Unity 2026.06 BOD_Forecast … .pptx` | Board forecast deck | Presentation (charts, not data) |

**Note:** The one rich real file is the **GL export**. Everything else is
reported output, not the raw feeds the agents reason over.

---

## What's still missing — by system

Ranked: **[BLOCKER]** = agent can't do its core job without it · **[HIGH]** = a whole
analysis stream stays dark · **[NICE]** = improves quality but not gating.

### NetSuite (GL / TB)
- **[BLOCKER] Trial Balance exports — 3 periods:** current month, prior month (MoM), and
  same-month-prior-year (YoY). *P&L Flux is entirely a TB-vs-TB-vs-budget comparison; with
  no real TBs it can't run on real data at all.* → confirm we have (or can pull) a real
  monthly TB for the target close period + the two comparatives.
- **[HIGH] Prior-period GL detail:** we appear to have one GL export — confirm which period
  it covers and whether a **prior month** GL is available for period-over-period coding
  consistency (GL Coding Task 1).
- **[NICE] Vendor master export:** vendor → entity/country/type. Drives entity-mismatch and
  CRO-classification flags. Can be partially inferred from GL, but the master is cleaner.

### Coupa (procurement) — **entire subsystem missing in real form**
- **[HIGH] PO register** (open + closed, budget-check results)
- **[HIGH] AP register** (invoice-to-PO match status, discrepancy flags)
- **[HIGH] Open PO commitments** (accrual requirements)
- **[HIGH] Payments** (method, FX, on-hold status)

  *Both agents lean heavily on Coupa — three-way match, budget-check-failed flags,
  on-hold payments, accrual identification. None of this exists in the real data set.
  Ask: does Unity use Coupa, and can they export these four registers for the period?*

### ADP + Workday (payroll & HRIS) — **missing; this is the biggest gap by finding count**
- **[BLOCKER] ADP payroll detail** (batch-level: gross + employer burden by employee, GL
  cost-center coding)
- **[BLOCKER] Workday HRIS export** (employee → department, org hierarchy, headcount by
  period — the department **source of truth**)

  *These two power: GL payroll reconciliation (ADP↔Workday dept mismatch, batch→GL tie-out)
  and Flux headcount reconciliation. Without them, the payroll-miscoding findings and the
  headcount-driven salary variance simply don't fire. Ask: can Unity provide a period
  payroll register + an HRIS headcount/department extract?*

### Adaptive Planning (budget)
- **[BLOCKER] FY approved budget by account / department / month.** *Every "vs. budget"
  variance in both agents needs this. Confirm we can get the real board-approved budget
  export (not the synthetic one).*

### Supporting schedules
- **[HIGH] Accruals log** — existing + proposed accruals for the period (Flux accrual
  matching; legal-estimate accrual finding).
- **[HIGH] CRO spend detail** — CRO invoice + unbilled/WIP breakdown (Flux CRO accrual;
  the unbilled-accrual finding).
- **[NICE] Prepaid amortization schedule** — current prepaids + amortization (prepaid
  recode proposals).
- **[NICE] Fixed asset register** — existing PP&E, useful lives, depreciation (PP&E
  duplicate check + capitalization proposals).

---

## The 4 that were also missing from the *synthetic* set

Worth naming on the call — even Chris's synthetic package never shipped these four, so
they're a gap in **both** the mock and real paths:

- `adp_payroll_[period].csv`
- `workday_hris_[period].csv`
- `accruals_log_[period].csv`
- `cro_spend_detail_[period].csv`

If Unity can provide the **real** versions of these, we solve the synthetic gap and the
real-data goal in one move.

---

## Questions to put to Scott & Chris

1. **Systems of record:** Does Unity actually run **Coupa** (procurement), **ADP**
   (payroll), **Workday** (HRIS), and **Adaptive Planning** (budget)? The agents assume all
   four — if Unity's stack differs, we re-scope the data asks.
2. **Extract feasibility:** For each system above, can Unity produce a **period export**
   (target close month + the two comparatives for TB)?
3. **Target period:** Which close period do we run the *real* Jumpstart against? That fixes
   exactly which monthly extracts to request.
4. **Sensitivity / authorization:** Real financials are client-confidential — confirm we're
   cleared to load them into a Claude Project, and whether any file needs PII/redaction
   review first.
5. **Scope for v1:** Do we run **both** Jumpstarts on real data, or prove the concept on
   **GL Coding first** (we already have a real GL export) and add P&L Flux once TBs + budget
   are in hand?

---

## Fastest path to a real-data run (suggested)

**GL Coding Review** is the closest to runnable on real data — we already have a real GL
export. If Scott/Chris can add a **real vendor master + Adaptive budget** (and Coupa if they
use it), that Project could go real first. **P&L Flux** needs the **3 real TBs + real
budget** before it can run at all — that's the critical path to watch.

---

*Drafting note (QR): this is analysis + a data-ask list for the call. No Projects created,
nothing uploaded, no external sends. Real financials stay gated on sensitivity sign-off.*
