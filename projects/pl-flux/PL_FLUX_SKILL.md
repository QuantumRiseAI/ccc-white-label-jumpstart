# P&L Flux: Reference

Pairs with [`PROJECT_INSTRUCTIONS.md`](PROJECT_INSTRUCTIONS.md). What each check tests, how
each account group moves, and how an entry is shaped. The scripts apply all of it; use this
file to explain a result, not to reproduce one.

## What Each Check Tests

| Check | Shows on | What it tests |
|---|---|---|
| `F1.VARIANCE` | Actual vs. Actual | Each P&L account against the prior month, from $2,500. The prior year rides along for context. |
| `F2.BUDGET` | Actual vs. Budget | Each account the June plan covers, against plan, from $2,500 |
| `F5.MODEL_TIE` | Forecast vs. Actual | The closed months of the forecast cut after the month closed, against the ledger. A difference is an entry staged in one and not the other. |
| `F3.ACCRUAL_RECEIPT` | Accrual Proposals | Goods received in Coupa and not invoiced, $5,000 or more per supplier and account |
| `F6.ACCRUAL_PATTERN` | Accrual Proposals | A vendor that bills every month and billed nothing this month, at its three-month average |
| `F9.PREPAID` | Prepaids and Capital | Bills for one good or service of $2,500 or more that name a service term, or sit on a term account the vendor does not bill most months. Only those of $25,000 or more (Unity's prepaid threshold, related charges together) get a proposed Journal Entry; the rest stay expense |
| `F10.CAPITALIZE` | Prepaids and Capital | Bills of $2,500 or more on an account the asset policy names for review, or on repairs and maintenance, that do not name a service term. Each says whether it goes to Capital in Process or its fixed asset account, and why. Only a bill of $5,000 or more (Unity's capitalization threshold, the bill's lines together) gets a proposed Journal Entry; under it, it says it stays expense |
| `F7.REVENUE_IN_EXPENSE` | Reclassifications | A customer document posted to an expense account |
| `F8.VENDOR_DROPPED` | Reclassifications | A journal with no vendor where the same account, department and amount carried one before, including prepaid releases |

The threshold that decides what needs commentary or a decision is the reviewer's, $10,000 by
default, in dollars.

## How Each Account Group Moves

| Account group | What drives it | In commentary |
|---|---|---|
| `6100000` Employee Expenses | Headcount, bonus cycle, benefits | Explain the move from the UKG roster: hires, job and pay changes, and each department's roster salary against its GL (see [`PROJECT_INSTRUCTIONS.md`](PROJECT_INSTRUCTIONS.md), Payroll accounts). The payroll register adds the cutoff accrual and the payroll tax on the bonus. |
| `6200000` Consulting | `Plurality Labs LLC`, about $9.1M net | Related party. Keep Plurality apart from other consulting. |
| `6300000` Legal & Professional | `K&L Gates LLP` corporate, IP legal apart | Milestone driven. Check for unbilled legal against `2204000`. |
| `6400000` Lab Expenses | Fisher Scientific, New England BioLabs, Life Technologies | Explain by vendor and order cycle, not one line. |
| `6500000` External Research | Sequencing, synthesis, in vivo, in vitro, CMC | Moves in steps with milestones and batches. A drop is often a missing invoice. Check accruals first. |
| `6600000` Facilities | Rent, CAM, parking | Largely fixed. Explain any move. |
| `6700000` Travel & Entertainment | Conferences, travel, meals | Follows the conference calendar. |
| `6800000` Administrative | Office supplies, software, insurance | Many small lines. Comment in aggregate. |
| `6900000` FSP Operating Charges | Plurality shared-platform allocation | A move means the allocation changed, not Unity's activity. Related party. |
| `7100000` Depreciation | Fixed asset schedule | Moves only with additions and disposals. Flag any other move. |
| `7301000` Stock Compensation | Grant schedule | Rarely adjusted. Flag any move. |
| `8202000` Interest Expense - Cash | Debt schedule | Tie to principal and rate, not operations. |
| `8231000`, `8232000` FX | Realized and unrealized FX | Non-operating. Report apart from operating commentary. |

## Journal Entry Patterns

Accrual, reversing on the first day of the next month:

```
Dr [expense account] / [department]    [amount]
  Cr [accrual account]                 [amount]
```

| Expense | Accrual account |
|---|---|
| Lab supplies and external research | `2206000 Accrued Lab Supplies and External Research` |
| Payroll, benefits and bonus | `2201000 Accrued Payroll Benefits and Bonus` |
| Consulting | `2202000 Accrued Consulting` |
| Facilities | `2203000 Accrued Facility Costs` |
| Legal | `2204000 Accrued Legal Fees` |
| FSP charges | `2206500 Accrued FSP Charges` |
| Anything else | `2207000 Accrued Other` |

Prepaid, when the service runs past the period end, then amortized straight-line over the
term to the account and department where the spend was budgeted:

```
Dr [prepaid account]                   [amount]
  Cr [expense account] / [department]  [amount]
```

| Expense account | Prepaid account |
|---|---|
| `6601000` Rent | `1305000 Prepaid Rent` |
| `6891000` Package Insurance | `1310000 Prepaid Insurance` |
| `6416000`, `6816000` software | `1320000 Prepaid Software` |
| Any other | `1315000 Prepaid Other` |

Capital, when the item lasts more than a year and costs $5,000 or more, placed in service at
the invoice date, or for a build-out when employees begin using the space:

```
Dr [asset account]                     [amount]
  Cr [expense account] / [department]  [amount]
```

`1505000 Capital in Process` holds build-out work and an asset bought but not yet in service,
until it is placed in service. An asset in service goes to its fixed asset account:

| Expense account | Fixed asset account, in service |
|---|---|
| `6415000` Lab Non-Capital Equipment, `6435000` Lab Equipment Repairs & Maintenance | `1510000 Lab Equipment - New` |
| `6416000`, `6816000` software; a computer on `6815000` | `1530000 Computers & Software` |
| `6815000` Office Non-Cap Equipment/Furniture, anything else | None in the chart: held in `1505000 Capital in Process`; ask the Controller |

The ledger has no in-service date. Each capital finding says which applies and why, and asks
for the date unless the line states it.

Customer document in expense:

```
Dr [expense account] / [department]    [amount]
  Cr 4001003 Revenue - Cost Reimbursement  [amount]
```

Department recode, one pair per posted line, with no P&L effect:

```
Dr [account] / [correct department]    [amount]
  Cr [account] / [posted department]   [amount]
```

## Load Summary

Print this after the month, the tie's result and any missing exports or columns (the order
in [`PROJECT_INSTRUCTIONS.md`](PROJECT_INSTRUCTIONS.md), Each Month), before any finding:

```
P&L FLUX, DATA LOAD
Period: [Mon YYYY] | Prior month: [Mon YYYY] | Same month last year: [Mon YYYY]
LOADED:    [file]  [N] rows             (one row per file)
TIE-OUT:   Dr [X] / Cr [Y] / net [Z]    [PASS or FAIL]
NOT RUN:   [check]  needs [feed]         (one row per check)
DEGRADED:  [check]  without [column or feed]   (one row per check run on partial input)
COUPA:     [N] lines, [months]; at its row limit: [yes or no]
```

The tie-out row restates the tie's result already given; keep it, so the block stands on its own.
A failed tie-out stops the run. Report the difference and produce nothing else.

## When Something Is Off

| What you see | What to do |
|---|---|
| Debits do not equal credits | Stop. Report the difference. No findings. |
| A prior value is zero | Give the dollar change. The percent is not meaningful. |
| A template is header-only | Expected. Name the checks it turns off and continue. |
| A template has rows under the wrong headers | Stop for that feed. Report the mismatch. Do not guess a mapping. |
| An expense fell and a regular vendor billed nothing | Not a saving until the accrual question is answered. |
| A Coupa PO line has no quantity | It counts as zero, so the accrual total is a floor. Say so. |
| `Currency Revaluation` lines | Report under FX, not in operating commentary. |

## Limits

* Every Unity policy is a draft and unapproved.
* Receipt accruals are pro-rated from the PO line total; the count of PO lines with no
  quantity is in F3.RECEIVED_NOT_INVOICED's note. Billing-pattern accruals are estimates that the budget owner confirms.
* No Coupa invoice data, so a receipt cannot be matched to a later bill.
* The plan does not cover payroll or depreciation.
