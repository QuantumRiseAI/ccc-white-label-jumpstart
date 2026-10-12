# Coverage: the August 2026 review against the team's own review

What the coding review (and, where the reviewer's question was a flux question, the flux review) found for August 2026, set against
the finance team's manual review of the same ledger. Matched on vendor, account, department and amount. Aggregates and short item
references only; no data files.

## What was compared

| Side | Source | Scope |
|---|---|---|
| Engine | `make build PERIOD=aug2026`: coding run (56 findings, 5 rules) and flux run (99 findings) | Aug 2026 |
| Team | P&L by department pivot (Jul to Sep), balance sheet pivot (Sep), the ledger-review questions workbook (vendor-bill coding, P&L flux, AP and Coupa fix list tabs; Jun to Aug) | Jun to Sep 2026 |

Limits of the comparison:

* The team's GL detail export carries no reviewer marks (no comment column, no flag), so row-level "the team flagged this line" cannot be
  derived from it. Reviewer attention is taken from the written questions and pivot comments, 17 in the department pivot, 2 on the balance sheet,
  and 17 in the workbook.
* A finding with no reviewer comment is not a rejected finding. The reviewer worked from pivots, not from the engine's list.
* Most department pivot and balance sheet comments are on September values. Those are listed separately; August output cannot be tested
  against them. Three pivot comments are on August values and are compared below (Facility Repairs on Platform $9,004.56, Lab Non-Capital
  Equipment on Production $748.88, Insurance & Benefits negatives), as is the Chemistry Salaries drop.
* "Caught" means the engine surfaced the item in some finding. A variance finding (F1, F2) on the account counts, as for the sequencing
  and legal fee questions, even when it states the movement and not the driver.

## Caught by both

| Item | Reviewer's question | Engine finding | Amount |
|---|---|---|---|
| Fisher Scientific ELISA kits on Platform | Miscoded, should be lab supplies | T4 PO account mismatch, 6607000 vs approved 6410000 (all 6 lines) | $9,004.56 |
| VWR International, Facility Repairs | "Why these splits?" on the VWR fix list | T4, 6607000 vs 6410000; 6501100 vs 6410000 | $19,674.16; $924.06 |
| Agilent, two bills to General R&D | "New charge? Is this where budgeted?" | T1 department inconsistency, normally Platform | $1,118.38; $4,572.00 |
| Production Lab Non-Capital Equipment | "May not be the right place?" | T4, 6415000 vs 6410000 (Fisher; the finding also holds $1,222.27 of other lines) | $748.88 |
| Expedition Medicines negative in General Consulting | "What is the negative?" | F7 revenue in expense | $8,921.37 |
| No vendor on a Management Indirect Labor line | Vendor master issue? | F8 vendor dropped | $7,123.72 |
| Lab Non-Capital Equipment swings | "Why huge jumps up and down?" | F1 variance, down on July | $44,055.86 |
| Azenta sequencing drop and synthesis uplift | "Why the drop in sequencing?", "Why uplift in synthesis?" ($19,229 Aug vs $11,166 Jul) | F1 on Sequencing Costs (down) and Synthesis Costs (up $3,828.38); F5 model tie on Sequencing Costs / Platform | $19,843.27; $3,828.38 |
| Lab Supplies/Consumables is "a beast" | A more insightful breakdown | F1 and F2 on the account | $1,262,568.25 |
| Corporate legal fees | Aug $39,690.50 against Jul $65.73 | F1 up on July; F2 against plan | $39,624.77; $43,642.83 |
| AWS on IT Consulting | "Coded right? A prepaid?" | F1 IT Consulting up; F2 over plan; AWS is the largest vendor in the account | $14,310.95; $12,392.75 |
| Stanford OTL option payment | "A prepaid? A license fee?" | F1 IP License Fees, down $10,000 in August (the payment posted in July) | $10,000.00 |

For the Azenta, lab supplies, legal, AWS and Stanford rows the engine states the movement; the reviewer asked for the driver or the
treatment.

## Engine only (no reviewer comment)

| Rule | Findings | Amount | Note |
|---|---|---|---|
| T1 department inconsistency, under $1,000 | 19 of 34 | $5,148 of $101,955 | 5 vendors; MedChemExpress alone is 9 findings, almost all under $100 |
| T1 on lab vendors coded to General R&D that normally code to Production | Sartorius (3), Repligen (4) | $33,340; $24,057 | The reviewer's "nothing should be General R&D" comment is about Boston BioProducts in July, not these |
| T0 aberrant posting lag | 4 | $9,240 | Two 12-month-old lines, two 3-month-old; the two Global Life Sciences lines ($8,998) are also T1 findings, so the T0 and T1 totals overlap |
| T3 IRC 274(n) meals and 274(b) gifts | 2 | $16,329 meals, $4,614 gifts | Tax add-backs, a different lens than the team's review |
| T4 mismatches under $3,000 | 11 of 13 | $14,006.97 of $16,902.18 | Excludes VWR $924.06 and Fisher $1,971.15, counted above; vendors not named in the reviewer's questions (Repligen, Life Technologies, VectorBuilder, Twist, Qiagen and others) |
| High-severity vendor items not in the questions | NEB $37,740, Neosome $19,624 | | Lab reagents posted to a synthesis account (NEB) and a vendor split across departments (Neosome) |

## Reviewer only (engine missed)

| Reviewer question | Amount (Aug) | Why the engine is silent |
|---|---|---|
| Abcam on Platform: "no allocation to the other 2 departments?" | $7,004.50 Platform, $520.50 Biology | T1 compares a vendor to its own history; Abcam is consistent with itself |
| Boston BioProducts on General R&D: "nothing should be General R&D, this is Production" | $21,891.19 General R&D in July (August is all Production, $20,820) | No engine finding on Boston in the August run; the spend is July's |
| Beckman Coulter Vi-Cell service contract: "capex or R&D expense?" | $7,540.00 | No rule reads a service-contract term; the Agilent TapeStation contract (8/19/2026 to 8/18/2027, $4,572) was caught for department only, not for the prepaid question |
| Flagship Pioneering Labs: "missing an accrual" | $962 vs $9,229 prior month | F6 accrual pattern fired for three other vendors, not this one; cause not investigated |
| Chemistry Salaries: "dropped a lot" | $17,903.67 vs $22,087.00 in July | F1 states Salaries up $15,379.58 across the company; no department-level variance on payroll accounts |
| Insurance & Benefits negative in five departments, all three months | Jul to Sep | No sign check on an expense account by department |
| "No vendor bills went to prepaids or PP&E?" | | Coding review has no prepaid or capitalization rule; flux has F9 (1 finding) and F10 (3) |

## September only (not testable on the August output)

* Bonus missing in Biology, Chemistry, In Vivo, Production (four departments), with payroll tax following the bonus.
* Chemistry temp and contract labor (6105000): the department has no lines from January to August; the first are two September
  Beacon Hill invoices ($17,201.84), and the reviewer asks whether an August accrual was missed.
* IT Consulting $1,167.24 on Platform, "maybe office supplies".
* Balance sheet: LQ Clearing Account $386,795.01 ("what is this used for, a lease clearing?"); $41.97 in Computers & Software ("weird, should surface").
* Office Supplies negative year to date in Production.

## Proposed rule changes

1. **Service-contract and term detection (T-series or F9).** On repair, maintenance, license, subscription and hosting accounts, parse a
   service period from the description or memo ("service contract <start> - <end>", "annual") and, when the period runs past the month end,
   propose prepaid treatment. Covers Beckman and Agilent.
2. **Department spread per vendor and account (T1 extension).** Flag a vendor whose Aug lines sit in one department when the Coupa
   requester departments show several. Needs the Coupa Requester Dept column, which the current export lacks; until then, list single-department
   vendors above a spend threshold for ratification.
3. **Roll T1 up by vendor and pair, and add a floor.** One finding per vendor and department pair instead of one per line, and drop pairs
   under $1,000 to the ratification worksheet. The 34 findings group into 15 vendor and department pairs, 10 after the floor.
4. **Missing recurring line.** If an account and department posted in each of the prior two months and posts nothing (or less than half)
   this month, raise an accrual question. Covers Flagship and the September bonus gaps. Extend F6 or add F6b. It cannot cover Chemistry temp
   labor, which has no earlier lines.
5. **Department-level variance on payroll accounts.** F1 compares the account in total; a department that drops 19% (Chemistry Salaries)
   is invisible. Add a department cut for Salaries, Bonus and Payroll Taxes.
6. **Late-posting by service month.** AWS posted May, June and July services in August. Read the service month from the description and
   flag a line whose service month is earlier than the posting period; T0 today keys on document dates.
7. **Sign check on expense accounts.** A department and account with a net credit in the month (Insurance & Benefits, Office Supplies YTD)
   gets a finding with the journal or credit memo behind it.
8. **Prepaid and PP&E presence check.** When a close month has bills over the capitalization threshold and none reach a prepaid or fixed asset
   account, say so once, instead of leaving the question to the reviewer.
9. **Balance sheet clearing accounts.** A clearing account with a large unexplained balance (LQ Clearing) is a flux-side rule on the balance sheet;
   the coding engine has no balance sheet input.

## Not done

* No engine rules were changed.
* The reviewer-flagged lines in the GL detail export cannot be identified; if the team marks the source file (highlight or a flag column), the
  same match can run at line level.
* These proposals are rule changes to consider, not a ruling.
