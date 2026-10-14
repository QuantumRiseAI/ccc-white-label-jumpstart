# Serif Policy Rules: Operative Extract

Every threshold and coding rule the engines apply, in one place, with its source document.

**All source policies are DRAFT and unapproved.** Any finding citing one must say so.
Full source documents live outside the Project, in `references/serif-policies/`. This
extract exists so a Project carries the rules without carrying ~18,000 tokens of policy
prose it does not need.

If a number here is disputed, change it here and in the engine script that carries it
(`serif_uc1_engine.py` or `serif_uc2_flux.py`), and say so. Do not
change it silently in one place.

## Thresholds

| Rule | Value | Source |
|---|---|---|
| Pre-close adjustment, Day 5 or earlier | **$10,000** | Global Finance Threshold Policy |
| Post-close monthly adjustment | **none recorded** | Global Finance Threshold Policy |
| Post-close quarterly adjustment | **$100,000** | Global Finance Threshold Policy |
| Accrual, per vendor per good or service | **$5,000** | Global Accrued Expense Policy |
| Payroll accrual, per liability | **$5,000** | Global Accrued Expense Policy |
| Prepaid, aggregated per good or service | **$25,000** | Serif, Mike's write-up of 12 Oct 2026 |
| Prepaid impairment review, quarterly | **$50,000** | Global Prepaid Expense Policy |
| Fixed asset (PP&E) capitalization | **$5,000** | Serif, Mike's write-up of 12 Oct 2026 |

The prepaid and PP&E figures are Serif's own, from Mike's write-up of 12 Oct 2026. They
replace the $10,000 the draft Global Prepaid Expense Policy had been read as, and the draft
Tangible & Intangible Asset Policy's "no threshold, by design". The flux engine carries
both (`PREPAID_THRESHOLD`, `CAPITALIZATION_THRESHOLD`); the coding engine's constants of the
same names are not used, because prepaid and fixed-asset tests are outside its scope. The
prepaid and capital screens list from the **$2,500** reporting floor, so a reviewer can look
below the line; a flag under its threshold says it stays expense, and the P&L Flux proposes
no prepaid entry under $25,000.

The GL Coding Review gives each review screen its own threshold, in Settings: CapEx at
**$5,000**, Prepaid at **$25,000**, the others at **$2,500**. Department flags have none:
every line off Non-Specific is recoded, whatever its size. The P&L Flux commentary threshold
is a separate question, still open with Serif.

## Data Entry Policy: the Coding Rulebook

* **Subsidiary**, must match the entity on the vendor bill or contract. A wrong
  subsidiary is corrected at source (new invoice, credit memo), not by reclass alone.
* **Department / cost center**, must match how the spend was budgeted, assessed against
  the nature of the work. Not simply copied from the vendor's history.
* **Account**, must reflect the operational nature of the expense. The policy's own
  examples: catering for an event belongs in catering, not events; consulting belongs in
  consulting, while backfills and temporary help belong in contractors/temp help.
* **Vendor field**, must match the NetSuite vendor master exactly: spelling, case, all of it.
* **Project**, required on *all* transactions. Where spend is not project-specific, the
  appropriate overhead project is used.
* **Memo / description**, format is `Specific description | Date of good or service`,
  e.g. `Office, Kitchen Supplies, & Drinks & Snacks | Mar'25`. Entries spanning months are
  split by month so they align with reversals.
* **EBITDA add-back dimension**, populated where the credit agreement's add-back
  definition applies, per the mapping file.

Testing note: `memo` is populated on only ~6% of P&L lines; `description` carries the
narrative on ~96%. Test both. Only ~1% of lines contain a `|` at all, so the honest
finding is that the convention is not in use, a process question for Serif, not a
correction queue for the controller.

## Accrued Expense Policy

* Accrue monthly where expense is incurred but no invoice is recorded, above **$5,000**
  at the vendor level for a specific good or service.
* Prior-month accruals **reverse automatically**; re-accrue if the invoice still has not
  arrived.
* Estimation method, per the policy's worked examples: **trailing three-month average**.
* Coding on the accrual must match where the spend was budgeted, and where the invoice
  will ultimately land, subsidiary, department, project, account.
* Journal entries for payroll accruals must contain **no personally identifying
  information**: no names, no employee IDs. Payroll reconciliations and entries are kept
  in a password-protected location.
* Classify accrued liabilities current vs non-current by expected settlement timing.

Accrual accounts under `2200000`:

| Spend | Credit |
|---|---|
| Lab supplies, external research | `2206000` Accrued Lab Supplies and External Research |
| Payroll, benefits, bonus | `2201000` Accrued Payroll Benefits and Bonus |
| Consulting | `2202000` Accrued Consulting |
| Facilities | `2203000` Accrued Facility Costs |
| Legal | `2204000` Accrued Legal Fees |
| FSP charges | `2206500` Accrued FSP Charges |
| Anything else | `2207000` Accrued Other |

## Prepaid Expense Policy

* A prepaid is cash paid in advance of the good or service being received.
* Threshold **$25,000** (Mike's write-up, 12 Oct 2026; the draft policy had been read as
  $10,000), with related charges for the same good or service **aggregated before**
  testing.
* Amortize as the benefit is received: straight-line for subscriptions and
  support/maintenance; events expensed when the event occurs; collateral as distributed.
* Amortization is coded to the subsidiary, department, project and account where the
  spend was budgeted.
* Review prepaids over **$50,000** quarterly for impairment; write off where the benefit
  is no longer expected.
* Classify current vs non-current by benefit period. Where an amount sits in both AP and
  prepaid, gross down the balance sheet.

Prepaid accounts: `1305000` Rent · `1310000` Insurance · `1315000` Other · `1320000` Software.

## Tangible and Intangible Asset Policy

* Capitalization threshold **$5,000** (Mike's write-up, 12 Oct 2026). The draft policy set
  none, by design; Serif's figure replaces that. Below it a purchase is expense, unless it
  is part of a larger asset. Above it, asset category and useful life decide.
* Office furniture, fixtures and equipment: **5-year** useful life, **7-year** retirement
  and disposal life.
* Placed in service: the invoice date, unless tied to a buildout, in which case it is the
  date employees begin using the space.
* Location is tracked by city, for personal property tax and impairment analysis.
* Disposal with no intent to sell goes to depreciation expense; with intent to sell,
  consider held-for-sale guidance.

Asset accounts: `1505000` Capital in Process · `1510000` Lab Equipment - New ·
`1530000` Computers & Software · `1550000` Leasehold Improvements · `1590000` Finance Lease
Right of Use Asset.
Candidate source accounts to review for capitalization: `6415000`, `6815000`, `6416000`,
`6816000`, their names assert non-capital treatment, and the review is whether that holds.

**Capital in Process or a fixed asset account.** `1505000` Capital in Process holds
build-out work and assets bought but not yet placed in service. An asset in service goes to
its fixed asset account: lab equipment to `1510000` Lab Equipment - New, computers and
software to `1530000` Computers & Software. When it is placed in service, Capital in Process
moves to that account (Serif did this for the KR2i TFF system in Nov 2025). The chart has
no fixed asset account for office furniture and equipment; until Serif names one, a
furniture purchase in service is held in Capital in Process and the Controller is asked.
Every capital recommendation says which applies and why, and asks for the in-service date,
which the ledger does not carry, unless the line states it.

## Intercompany Policy: Applies to Flagship Counterparties

Serif has one subsidiary in the ledger, so there are no cross-entity postings to test.
Intercompany activity appears instead as **Flagship-named vendors**, `Flagship Labs LLC`
is the single largest counterparty by net expense.

* The sender provides compliant invoices and audit-ready support; the receiver reviews
  and books them.
* Calendar: prior-month actual invoicing by **Day −7**, estimated cross-charges and
  transfer-pricing by **Day 2**, reconciliation **Day 2**, settlement **Day 12**.
* Recharges are made in the currency incurred wherever possible.

Flag Flagship-named counterparties that lack the documentation this policy requires.

## Severance: P&L Flux Only

Serif posts to `6110000 Severance Expenses`. Which standard applies depends on the nature
of the separation, and it changes the recognition timing:

| Standard | Applies when | Recognize |
|---|---|---|
| **ASC 712** | Ongoing arrangement, standing HR policy or employment contract | When probable and estimable |
| **ASC 450** | Individual negotiated separation agreement | When probable and estimable; needs at minimum a term sheet or written HR authorization |
| **ASC 420** | One-time benefits under a formally approved exit, disposal or RIF plan | When management commits and communicates; ratably over any required service period |

Measure at total expected payout: salary continuation, pro-rated bonus, benefits
continuation at COBRA rates, and any equity modification under ASC 718.

Where the applicable standard is unclear, the policy requires consulting VP Finance
before recording a liability.

## Deliberately Excluded

* **Global Treasury, Cash Management & Hedging Policy**, not a Serif document. It names
  CrossCountry Consulting as the company, Investcorp as PE sponsor, and Sage Intacct as
  the system of record. Feeding it to an agent would inject another company's thresholds.
* **Foreign Currency Conclusion**, a functional currency memo whose only analyzed entity
  is India. Serif has one US subsidiary and no India entity. Revisit if a foreign entity
  appears; Serif does post to FX accounts `8231000` and `8232000`.
