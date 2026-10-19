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
| `T1.DEPT_INCONSISTENCY` | Organization & Account, Coding Inconsistencies, vs. Vendor History ("Department") | A department other than the vendor's usual one in earlier months |
| `T4.PO_ACCOUNT_MISMATCH` | Organization & Account, Coding Inconsistencies, vs. Coupa PO ("Account vs. Coupa") | An account other than the one the vendor's Coupa POs were approved against. When it did not run, the tab shows a dash and the run's reason |
| `T4.ITEM_ACCOUNT_DRIFT` | Organization & Account, Coding Inconsistencies, vs. Coupa PO ("Account vs. Coupa") | A Coupa PO line in the close month on an account other than the one the same item had on earlier lines of the year (a tie in that history sets no expectation). Lines under the review threshold are a count and a total. Not run when the Coupa export has no Item column |
| `T3.IRC_274A_ENTERTAINMENT` | Run log | Entertainment, 0% deductible |
| `T3.IRC_274N_MEALS` | Run log | Meals, 50% deductible |
| `T3.IRC_274B_GIFTS` | Run log | Gifts, $25 per recipient |

A `T1` or `T4` finding with an `excepted` block is an accepted exception: a reviewer approved it
(`approved_by`, `reason`). Report it as excepted and counted, never as open and never as clean.

Duplicate vendor records: the engine reads a vendor name as one supplier. `VENDOR_PAIRS` in
the engine's policy module lists each pair a reviewer has decided: "confirmed" pairs are read
as one supplier before any check runs, "apart" pairs are never merged (Amazon Web Services
and Amazon Capital Services), "proposed" pairs are not applied (Thermo Fisher Scientific and
Fisher Scientific; neither the GL nor Coupa has a Thermo Fisher Scientific record). `vendor_pairs`
in `run.json` lists them. Names are never merged by similarity.

Checks shown on the run log are counted there, not laid out as cards; report them when
asked. Measures, in `metrics`, on no page: posting lag, missing project code, memo format, vendor
name variants, unallocated P&L spend, off-PO spend, open PO commitments, and the IRC §174
base. Report them when asked.

Flags the schedules step adds to vendor rows:

| Flag | What it means |
|---|---|
| New vendor | No bills from the vendor in the two prior months or the same month last year |
| Coding changed | An account and department the vendor did not use in those months. Codings an engine finding covers are left to that finding. A CODING card on Organization & Account, Coding Inconsistencies, vs. Vendor History |
| Coded off plan | The June forecast plans the vendor on other coding. A CODING card on Organization & Account, Coding Inconsistencies, vs. Forecast (a vendor also flagged Coding changed stays on vs. Vendor History) |
| Requested by a department | People in another department raised the vendor's Coupa POs, by UKG department |
| May be prepaid | Bills for one good or service that total $2,500 or more and name a service term, or sit on a term account the vendor does not bill most months. Under the $25,000 prepaid threshold it says it stays expense |
| May be capital | A bill of $2,500 or more on an account the asset policy names for review, or on repairs and maintenance, that does not name a service term. It says whether it goes to Capital in Process or to its fixed asset account, and why |

The build adds **Same item, two accounts** from the ledger alone: an item billed this month to
6410000 Lab Supplies/Consumables or 6415000 Lab Non-Capital Equipment that went only to the
other in the six months before. It shows on Organization & Account, Coding Inconsistencies,
Same Item, Different Accounts. A Journal Entry Claude drafted goes to the page its change
belongs to: CapEx for a debit to 15xxxxx, Prepaid for 13xxxxx, and otherwise Organization &
Account, vs. Vendor History.

The threshold that decides what needs a look is the reviewer's, in dollars, one per screen:
CapEx $5,000 (Serif's capitalization threshold), Prepaid $25,000 (Serif's prepaid threshold),
and $2,500 for the account recodes on Organization & Account and drafted entries. Department flags
have none: every line off Non-Specific is recoded, whatever its size. Both screens list from
$2,500, so a lower threshold shows more: a capital bill under $5,000, or a prepaid under
$25,000, is still listed, not marked Review, and says it is under the threshold.

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

Capital in Process or a fixed asset account. Every capital recommendation says which, and why:

* **`1505000 Capital in Process`** holds build-out work (the description names a build-out,
  fit-out, construction, renovation, tenant improvement, a phase, or an office or space
  expansion) and assets bought but not yet in service (a deposit, a down payment, a
  progress or milestone payment). It moves to the fixed asset account when the asset is
  placed in service; for a build-out, when employees begin using the space.
* **An asset in service** goes to its fixed asset account, below. The policy places it in
  service at the invoice date.
* The ledger has no in-service date. Unless the line states one, the card's Placed in
  service says it is not known, and the reviewer gives the date in the note.

| Expense account | Fixed asset account, in service |
|---|---|
| `6415000` Lab Non-Capital Equipment, `6435000` Lab Equipment Repairs & Maintenance | `1510000 Lab Equipment - New` |
| `6416000`, `6816000` software | `1530000 Computers & Software` |
| `6815000` Office Non-Cap Equipment/Furniture, a computer | `1530000 Computers & Software` |
| `6815000` Office Non-Cap Equipment/Furniture, anything else | None in the chart. The entry holds it in `1505000 Capital in Process`; ask the Controller which account to use |

Aug 2026: Red Thread Spaces, "Office Desk Expansion (Phase 2)", goes to Capital in Process as
build-out work, as Serif moved Phase 1 there on 31 Jul 2026. Ask when employees began, or
will begin, using the space.

## Reading Serif's Lines

* The line **description** says what was bought. The memo is filled on about 6% of P&L lines.
  A line with no description is where the invoice has to be read.
* Read the account by its name. `6410000 Lab Supplies/Consumables` holds reagents and
  consumables. `6504000 CMC` holds external chemistry, manufacturing and controls work.
  `6501100 Synthesis Costs` and `6501000 Sequencing Costs` hold outsourced synthesis and
  sequencing. `6415000 Lab Non-Capital Equipment` holds equipment under capital treatment.
* **Repairs and maintenance** raise a capital question: a repair is expense, a replacement
  unit or a new instrument may be an asset. A service contract on the account is a prepaid
  question once it reaches $25,000.
* A vendor split across departments needs a reason. Ask why the spend is not on the
  department that used it.
* Only the current month gets an entry. Earlier months are context.

## Load Summary

Print this after the month, the tie's result and any missing Coupa columns (the order in
[`PROJECT_INSTRUCTIONS.md`](PROJECT_INSTRUCTIONS.md), Each Month), before any finding:

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
