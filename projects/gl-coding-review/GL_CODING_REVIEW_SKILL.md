# GL Coding Review: Reference

Pairs with [`PROJECT_INSTRUCTIONS.md`](PROJECT_INSTRUCTIONS.md). What each check tests, how an
entry is shaped, and how to read Serif's lines. The scripts apply all of it; use this file to
explain a result, not to reproduce one.

## What Each Check Tests

Engine findings, in `findings`:

| Check | Shows on | What it tests |
|---|---|---|
| `T0.TIE_OUT` | SOX Documentation, GL Tie-Out | Debits equal credits. A failure stops the run. |
| `T0.DUPLICATE_LINE` | Run log | One document posting the same account, amount, department and description more than once |
| `T0.ABERRANT_POSTING_LAG` | Run log | A line dated three or more months before its period, or after it |
| `T1.DEPT_INCONSISTENCY` | Dept & Entity, "Department" | A department other than the vendor's usual one in earlier months |
| `T4.PO_ACCOUNT_MISMATCH` | Dept & Entity, "Account vs. Coupa" | An account other than the one the vendor's Coupa POs were approved against |
| `T3.IRC_274A_ENTERTAINMENT` | Run log | Entertainment, 0% deductible |
| `T3.IRC_274N_MEALS` | Run log | Meals, 50% deductible |
| `T3.IRC_274B_GIFTS` | Run log | Gifts, $25 per recipient |

A `T1` or `T4` finding with an `excepted` block is an accepted exception: a reviewer approved it
(`approved_by`, `reason`). Report it as excepted and counted, never as open and never as clean.

Checks shown on the run log are counted there, not laid out as cards; report them when
asked. Measures, in `metrics`, on no page: posting lag, missing project code, memo format, vendor
name variants, unallocated P&L spend, off-PO spend, open PO commitments, and the IRC §174
base. Report them when asked.

Flags the schedules step adds to vendor rows:

| Flag | What it means |
|---|---|
| New vendor | No bills from the vendor in the two prior months or the same month last year |
| Coding changed | An account and department the vendor did not use in those months. Codings an engine finding covers are left to that finding. |
| Coded off plan | The June forecast plans the vendor on other coding |
| Requested by a department | People in another department raised the vendor's Coupa POs, by UKG department |
| May be prepaid | Bills for one good or service that total $10,000 or more and name a service term, or sit on a term account the vendor does not bill most months |
| May be capital | A bill of $2,500 or more on an account the asset policy names for review, or on repairs and maintenance, that does not name a service term |

The threshold that decides what needs a look is the reviewer's, $2,500 by default, in dollars.

## Entry Patterns

Department recode, one pair per posted line:

```
Dr [account] / [correct department]    [amount]
  Cr [account] / [posted department]   [amount]
P&L impact: none. Departmental presentation only.
```

Account recode:

```
Dr [correct account] / [department]    [amount]
  Cr [posted account] / [department]   [amount]
```

Prepaid, when the service runs past the period end:

```
Dr [prepaid account]                   [amount]
  Cr [expense account] / [department]  [amount]
Then amortize straight-line over the service term, to the account and department
where the spend was budgeted. Review above $50,000 quarterly for impairment.
```

| Expense account | Prepaid account |
|---|---|
| `6601000` Rent | `1305000 Prepaid Rent` |
| `6891000` Package Insurance | `1310000 Prepaid Insurance` |
| `6416000`, `6816000` software | `1320000 Prepaid Software` |
| Any other | `1315000 Prepaid Other` |

Capital, when the item lasts more than a year:

```
Dr [asset account]                     [amount]
  Cr [expense account] / [department]  [amount]
Placed in service at the invoice date, or first use if part of a buildout.
Office furniture, fixtures and equipment: five-year life.
```

| Expense account | Asset account |
|---|---|
| `6415000` Lab Non-Capital Equipment, `6435000` Lab Equipment Repairs & Maintenance | `1510000 Lab Equipment - New` |
| `6815000` Office Non-Cap Equipment/Furniture | `1505000 Capital in Process` |
| `6416000`, `6816000` software | `1530000 Computers & Software` |

## Reading Serif's Lines

* The line **description** says what was bought. The memo is filled on about 6% of P&L lines.
  A line with no description is where the invoice has to be read.
* Read the account by its name. `6410000 Lab Supplies/Consumables` holds reagents and
  consumables. `6504000 CMC` holds external chemistry, manufacturing and controls work.
  `6501100 Synthesis Costs` and `6501000 Sequencing Costs` hold outsourced synthesis and
  sequencing. `6415000 Lab Non-Capital Equipment` holds equipment under capital treatment.
* **Repairs and maintenance** raise a capital question: a repair is expense, a replacement
  unit or a new instrument may be an asset. A service contract on the account is a prepaid
  question once it reaches $10,000.
* A vendor split across departments needs a reason. Ask why the spend is not on the
  department that used it.
* Only the current month gets an entry. Earlier months are context.

## Load Summary

Print this before anything else:

```
GL CODING REVIEW, DATA LOAD
Period: [Mon YYYY] | Entity: FL87 Serif Biomedicines, Inc.
LOADED:    [file]  [N] lines   (one row per file)
TIE-OUT:   Dr [X] / Cr [Y] / net [Z]   [PASS or FAIL]
NOT RUN:   [check]  needs [feed]        (one row per check)
```

A failed tie-out stops the run. Report the difference and produce nothing else.

## When Something Is Off

| What you see | What to do |
|---|---|
| Debits do not equal credits | Stop. Report the difference. No findings. |
| A template is header-only | Expected. Name the checks it turns off and continue. |
| A template has rows under the wrong headers | Stop for that feed. Report the mismatch. Do not guess a mapping. |
| A vendor has no earlier coding | Say there is no history to compare against. Do not recommend a department. |
| `Non-Specific` on a balance sheet account | Not an exception. |
| `Currency Revaluation` lines | System-generated. Leave them out of coding review. |

## Limits

* Every Serif policy is a draft and unapproved.
* The vendor coding baseline records what Serif does, not what Serif should do.
* The IRC §174 base is preliminary and needs tax counsel before it reaches a return.
