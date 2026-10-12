# Coverage: the August 2026 review against the team's own review

What the coding review (and, where the reviewer's question was a flux question, the flux review) found for August 2026, set against
the finance team's manual review of the same ledger. Matched on vendor, account, department and amount. Aggregates and short item
references only; no data files.

## What was compared

| Side | Source | Scope |
|---|---|---|
| Engine | `make build PERIOD=aug2026`: coding run (56 findings, 5 rules) and flux run (99 findings) | Aug 2026 |
| Team | P&L by department pivot, balance sheet pivot, the ledger-review questions workbook (vendor-bill coding, P&L flux, AP and Coupa fix list tabs) | Jun to Sep 2026 |

Limits of the comparison:

* The team's GL detail export carries no reviewer marks (no comment column, no flag), so row-level "the team flagged this line" cannot be
  derived from it. Reviewer attention is taken from the written questions and pivot comments, 17 in the department pivot, 2 on the balance sheet,
  and 16 in the workbook.
* A finding with no reviewer comment is not a rejected finding. The reviewer worked from pivots, not from the engine's list.
* The department pivot and balance sheet comments were written on September data. Items that exist only in September are listed
  separately; August output cannot be tested against them.

## Caught by both

| Item | Reviewer's question | Engine finding | Amount |
|---|---|---|---|
| Fisher Scientific ELISA kits on Platform | Miscoded, should be lab supplies | T4 PO account mismatch, 6607000 vs approved 6410000 (all 6 lines) | $9,004.56 |
| VWR International, Facility Repairs | "Why these splits?" on the VWR fix list | T4, 6607000 vs 6410000; 6501100 vs 6410000 | $19,674.16; $924.06 |
| Agilent, two bills to General R&D | "New charge? Is this where budgeted?" | T1 department inconsistency, normally Platform | $1,118.38; $4,572.00 |
| Lab supplies on General R&D that belong to Production | "Nothing should be General R&D, this is Production" | T1 on Sartorius, Repligen (General R&D, normally Production) | $20,140 + $11,528 + $10,875 + smaller |
| Production Lab Non-Capital Equipment | "May not be the right place?" | T4, 6415000 vs 6410000 (Fisher) | $748.88 |
| Expedition Medicines negative in General Consulting | "What is the negative?" | F7 revenue in expense | $8,921.37 |
| No vendor on a Management Indirect Labor line | Vendor master issue? | F8 vendor dropped | $7,123.72 |
| Lab Non-Capital Equipment swings | "Why huge jumps up and down?" | F1 variance, down on July | $44,055.86 |
| Sequencing drop, Lab Supplies size | Why the drop; "account is a beast" | F1 and F2 on both accounts | $19,843.27; $1,262,568.25 |

For the last two the engine states the variance; the reviewer asked for the driver.

## Engine only (no reviewer comment)

| Rule | Findings | Amount | Note |
|---|---|---|---|
| T1 department inconsistency, under $1,000 | 19 of 34 | $5,148 of $101,955 | 11 vendors; MedChemExpress alone is 9 findings, almost all under $100 |
| T0 aberrant posting lag | 4 | $9,240 | Two 12-month-old lines, two 3-month-old |
| T3 IRC 274(n) meals and 274(b) gifts | 2 | $16,329 meals, $4,614 gifts | Tax add-backs, a different lens than the team's review |
| T4 mismatches under $3,000 | 12 | about $16,000 | Vendors not named in the reviewer's questions (Repligen, Life Technologies, VectorBuilder, Twist, Qiagen and others) |
| High-severity vendor items not in the questions | NEB $37,740, Neosome $19,624 | | NEB is the same 6501100 vs 6410000 pattern as the reviewer's synthesis uplift question |

## Reviewer only (engine missed)

| Reviewer question | Amount (Aug) | Why the engine is silent |
|---|---|---|
| Abcam on Platform only: "no allocation to the other 2 departments?" | $7,004.50 | T1 compares a vendor to its own history; Abcam is consistent with itself |
| Beckman Coulter Vi-Cell service contract: "capex or R&D expense?" | $7,540.00 | No rule reads a service-contract term; the Agilent TapeStation contract (8/19/2026 to 8/18/2027, $4,572) was caught for department only, not for the prepaid question |
| AWS on IT Consulting: "coded right? A prepaid?" | $14,292.90 | F9 prepaid fired once (Nova Biomedical) and not here |
| Stanford OTL IP license: "a prepaid? A license fee?" | $10,000.00 | Same |
| Flagship Pioneering Labs: "missing an accrual" | $962 vs $9,229 prior month | F6 accrual pattern fired for three other vendors, not this one; cause not investigated |
| Chemistry temp and contract labor: missed August accrual, double hit in September | $17,201.84 (Sep) | No Aug line in 6105000 for the department, and no rule looks for a missing recurring line |
| Insurance & Benefits negative in five departments, all three months | Jul to Sep | No sign check on an expense account by department |
| "No vendor bills went to prepaids or PP&E?" | | Coding review has no prepaid or capitalization rule; flux has F9 (1 finding) and F10 (3) |

## September only (not testable on the August output)

* Bonus missing in Biology, Chemistry, In Vivo, Production (four departments), with payroll tax following the bonus.
* IT Consulting $1,167.24 on Platform, "maybe office supplies".
* Balance sheet: LQ Clearing Account $386,795.01 ("what is this used for, a lease clearing?"); $41.97 in Computers & Software ("weird, should surface").
* Office Supplies negative year to date in Production.

## Proposed rule changes

1. **Service-contract and term detection (T-series or F9).** On repair, maintenance, license, subscription and hosting accounts, parse a
   service period from the description or memo ("service contract <start> - <end>", "annual") and, when the period runs past the month end,
   propose prepaid treatment. Covers Beckman, Agilent, Stanford OTL, and plausibly AWS.
2. **Department spread per vendor and account (T1 extension).** Flag a vendor whose Aug lines sit in one department when the Coupa
   requester departments show several. Needs the Coupa Requester Dept column, which the current export lacks; until then, list single-department
   vendors above a spend threshold for ratification.
3. **Roll T1 up by vendor and pair, and add a floor.** One finding per vendor and department pair instead of one per line, and drop pairs
   under $1,000 to the ratification worksheet. 34 findings become about 13, and the reviewer saw none of the small ones.
4. **Missing recurring line.** If an account and department posted in each of the prior two months and posts nothing (or less than half)
   this month, raise an accrual question. Covers Flagship, Chemistry temp labor, and the September bonus gaps. Extend F6 or add F6b.
5. **Sign check on expense accounts.** A department and account with a net credit in the month (Insurance & Benefits, Office Supplies YTD)
   gets a finding with the journal or credit memo behind it.
6. **Prepaid and PP&E presence check.** When a close month has bills over the capitalization threshold and none reach a prepaid or fixed asset
   account, say so once, instead of leaving the question to the reviewer.
7. **Balance sheet clearing accounts.** A clearing account with a large unexplained balance (LQ Clearing) is a flux-side rule on the balance sheet;
   the coding engine has no balance sheet input.

## Not done

* No engine rules were changed.
* The reviewer-flagged lines in the GL detail export cannot be identified; if the team marks the source file (highlight or a flag column), the
  same match can run at line level.
* The working session with the reviewer is still open; these proposals are for that conversation, not a ruling.
