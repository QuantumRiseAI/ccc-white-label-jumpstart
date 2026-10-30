# P&L Flux: Status

## What Is Deterministic

Computed by `client_uc2_flux.py`, reproducible run to run:

* **Month-over-month variance** per P&L account, with its departments and largest vendors
  on the finding and the prior year for context. Every move at or above $2,500 is
  emitted; the console's commentary threshold, default $10,000, decides which need
  commentary
* **Receipt-based accrual candidates** from Coupa, goods received but not yet invoiced,
  grouped by supplier and account, above the $5,000 accrual threshold
* **Population metrics**, total opex and its movement, unallocated P&L share,
  received-not-invoiced, open commitments

* **Budget variance** per planned account against the June forecast vintage
* **Forecast-to-ledger reconciliation** against the cut FP&A saved after the month closed,
  when `--forecast` is passed
* **Billing-pattern accruals**, the policy's Step B, for suppliers Coupa does not reach
* **Prepaid candidates** from $2,500, proposed for booking at or over Unity's $25,000 prepaid
  threshold, and **capitalization review** of the accounts the asset policy names plus
  repairs and maintenance, from $2,500, proposed for booking at or over the $5,000
  capitalization threshold, each saying whether it goes to Capital in Process or its fixed
  asset account, and why
* **Customer documents posted to expense**, and **journals that lost their vendor**

Aug 2026: **101 findings, $7,905,284.90**. 30 in Adjustments: 12 forecast-to-ledger
differences, 8 accruals (5 from Coupa receipts, 3 from the billing pattern), 3 prepaid
candidates, 3 capitalization reviews, 1 customer document in expense, 3 prepaid releases
with no vendor. The three prepaid candidates (service contracts of $16,746, $7,540 and
$4,572) are under $25,000, and two of the capitalization reviews (Bay State IT $3,240.63,
Repligen $2,823.39) are under $5,000, so none of those is proposed for booking: 11 proposed
Journal Entries. 71
in variance review: 39 accounts against the prior month, 32 against plan. Accrual population **$110,105**; open PO commitments
**$1,369,533** reported as a disclosure and not accrued.

Every input is a system export as the system wrote it, read by `client_sources.py`.

`client_views.py` lays the Adjustments out as schedules, adds plan by department, and
writes each proposed correction as a Journal Entry. It reads the same inputs and decides
nothing.

## What Is Still Judgment

The engine writes **no commentary**. It names the largest vendor contributors behind a
variance and stops there. Naming what drove a movement, deciding whether the period is
misstated, and drafting the narrative for the board pack are all human or model judgment.

That split is deliberate. A variance an LLM computes will not reproduce next month.

## What Is Not Built

* **Budget coverage.** The forecast plans external spend and overhead only, so payroll
  and depreciation have no plan line and no budget variance. F2.BUDGET also skips
  accounts that were planned and posted nothing; Actual vs. Budget by department lists
  them.
* **The other side of a forecast difference.** F5.MODEL_TIE sees one account at a time.
  Where a manual forecast line nets to zero across two differences, the schedules pair
  them into one balanced entry; any other difference stays on Forecast vs. Actual as a
  reconciliation item, not a Journal Entry.
* **Prepaid amortization and fixed-asset continuity.** The prepaid schedule and the asset
  register are still pending, so proposals cannot be checked against what is already
  carried.
* **Payroll cutoff accrual.** Needs the payroll register.
* **Derived-to-reported tie-out.** Done (UNITY-146): the ledger is tied to the Income
  Statement by month report, account by account, for the month and the month before, before
  the console is built.

## Accounting Review Still Outstanding

No rule here has been ratified by an accountant. The thresholds come from Unity's own
DRAFT, unapproved policies, except the prepaid ($25,000) and capitalization ($5,000)
thresholds, which are Unity's, from Mike's write-up of 12 Oct 2026. Two calls in particular
deserve a second opinion:

* The commentary rule: **$10,000**, dollars only, against the prior month and plan, one
  commentary per account. CCC prefers dollar thresholds with no percent test; the account
  level and the prior year as context only are to confirm with CCC.
* Whether the **accrual estimate basis**, pro-rating a PO line total by uninvoiced
  quantity, is acceptable support for posting.

The GL Coding Review project carries the equivalent pattern in its own `HOW-TO-RUN.md`.
