# Lens Module Review: Serif Dataset

**Prepared:** 2026-09-22 · **Status:** DRAFT, internal

Review of the Rapid Diagnostic Lens module output for Serif.
The arithmetic holds and the gap list is right.
The weaknesses are the evidence selection, the framing of the coverage score, and the absence of
any analysis that reads supplied files against each other.
The recommendations produce a build path where this client may need a remediation path first.

## What Holds Up

Every number reproducible from the raw exports came back exact.

| Claim | Verified |
|---|---|
| 44,013 GL lines | yes, 44,020 rows including headers |
| Bills 32,506 | yes |
| Bill Payment 5,536 | yes |
| Invoice 14 | yes |
| Payment 6 | yes |
| 139 distinct accounts | yes |
| 10 distinct departments | yes |
| `#REF!` present in the forecast workbook | yes, 595 occurrences |

The absent-feed list matches the gap list maintained independently for this engagement: no AP invoice
extract, no AR invoice extract, no vendor master, no payment-terms configuration.
The finding prose says those were not provided rather than that they do not exist, which is the
correct distinction to draw.

Lens undersold its own formula-error finding.
The 595 `#REF!` occurrences concentrate heavily: 557 sit in the quarterly reporting tab, and the
remaining 38 spread across the five-year P&L tab and two divisional reporting tabs.
Naming the tab turns a housekeeping note into an afternoon of work for a controller.

## Four Problems

### 1. The Transaction-Type Evidence Omits Five Types

Lens quotes four transaction types and drops five.
The full distribution:

| Type | Lines | Quoted |
|---|---|---|
| Bill | 32,506 | yes |
| Bill Payment | 5,536 | yes |
| Journal | 4,642 | no |
| Expense Report | 1,095 | no |
| Bill Credit | 145 | no |
| Currency Revaluation | 46 | no |
| Deposit | 19 | no |
| Invoice | 14 | yes |
| Payment | 6 | yes |

It kept the two smallest types and dropped the third-largest.
Recommendation two proposes a journal-entry risk-scoring agent, so nobody can size that build from the
numbers on screen.
The conclusion about thin AP and AR coverage still stands; the evidence needs the whole distribution,
or a stated selection rule.

### 2. The Coverage Score Reads as a Verdict on the Data Estate

`Data coverage 30/100 · low` scores a nine-file bundle, not Serif's systems.
The finding text handles this carefully, but a score sitting beside a conditional go/no-go will not be
read as carefully as it was written.
A client sees that number and concludes their data is poor, when the accurate reading is that they sent
nine files and most of what Lens wanted was not among them.

The remediation differs by an order of magnitude.
One version is an email asking for three saved searches.
The other is a data-quality project.
Scope the score to the bundle, or split what was supplied from what is known to exist.

### 3. Absent and Unreliable Need Separate Findings

Lens reports that no chart-of-accounts file was provided.
True as stated, and misleading in effect.
The forecast workbook it received contains a chart-of-accounts tab, and the GL export carries the full
account hierarchy on every line, so the bundle already holds one.

The sharper problem, which both inputs were present to catch, is that the tab disagrees with the live
ledger on 21 of the 65 account names appearing in both files.
NetSuite renumbered whole ranges:

| Account | Workbook tab | Live ledger |
|---|---|---|
| Rent or Lease of Buildings | 6501000 | 6601000 |
| Sequencing Costs | 6441000 | 6501000 |
| Building Operating Costs & CAM | 6509000 | 6609000 |
| Other External Research costs | 6446000 | 6509000 |
| Travel | 6610000 | 6702000 |
| Depreciation - Lab Equipment | 8010000 | 7110000 |

Rows one and two collide.
The code the tab assigns to rent is the code the ledger assigns to sequencing, so anyone who finds that
tab and trusts it compares rent against sequencing.
Calling the artifact missing sends someone off to build one.
Calling it stale tells them to distrust what they are about to find.

### 4. Nothing Reconciles Two Files Against Each Other

Lens profiles each artifact and then describes their relationship only in general terms, noting that the
forecast workbook "is not obviously reconciled to the GL extract."

Joining the workbook to the ledger on account, department and period gives this for August 2026:

| Account | Forecast | Ledger | Difference |
|---|---|---|---|
| 6410000 Lab Supplies/Consumables | 815,352.53 | 1,555,252.01 | -739,899.48 |
| 6504000 CMC | 911,230.59 | 171,331.11 | +739,899.48 |

The differences offset to the cent.
The pattern repeats May through August and totals **$4,470,029.85**.
On the workbook side the line describes itself as a reclass from labs to CMC, carries no vendor and no
purchase order, and sits on a line number inserted out of sequence.
Somebody staged that entry in the model and never booked it in the ledger.

Whether that was deliberate is Serif's question to answer.
Either way it attaches a specific dollar figure to a specific decision, it is the highest-value item in
the bundle, and it required no feeds beyond the two files Lens already had.

## The Recommendations Are Not Yet a Path

Lens produces five scored use cases, a delivery sequence, and a fee band.
That is more structure than most diagnostics manage.
It still does not resolve to a decision.

**Four of the five use cases share one gate.**
Scores of 65, 63, 56, 53 and 52, and everything except the first carries the same Conditional badge
blocked on the same three extracts.
The real decision tree has two branches: send the extracts, or build use case one and stop.
One question is presented as five scored options.

**The scores do not change what anyone does.**
Value 85, Effort 35, Data fit 48, SOX fit 40, with deltas of +34, +13, +12 and +6 against a baseline
the page never shows.
Four precise dimensions per use case, and the Strong or Conditional badge has already decided the
outcome.
Precision without discrimination.

**The deliverables stay abstract.**
"Deliver P&L variance commentary workflow" names an output type, not a deliverable.
Which period, which departments, what the artifact looks like, who reviews it, and what counts as done
all go unstated.
The contrast with the data-corrections section is stark, because that section is properly actionable:
"Export NetSuite AP invoices (full lines) for the entity FL87 with the exact columns listed; include
historic 12 months at minimum" is something a controller can act on the same day.

**The sequence carries no dependencies or owners.**
Week 1, Week 3, then three Phase 2 items, each waiting on client data with no date and no owner.
The calendar is unconditioned.
Nothing reads "Phase 2 starts three weeks after the vendor master lands."

**No use case addresses what is actually broken.**
The unbooked reclass and the stale account mapping both sit in the files Serif sent, and both will
corrupt any agent built on top of them, including the two Lens wants to build first.
Neither appears as a use case.
Use case five, the canonical chart-of-accounts and vendor master build, comes closest, scores lowest at
52, and lands in Phase 2.
That ordering is backwards: fixing the account mapping is cheap, it is a prerequisite for the rest of
the list, and Lens already holds the evidence to justify it.

Diagnose, remediate, then automate.
The module currently diagnoses and jumps to automate.

## Suggested Improvements

1. Show the full transaction-type distribution, or state the selection rule.
2. Scope the coverage score to the bundle, and separate "not supplied" from "does not exist."
3. Split absent artifacts from present-but-unreliable ones. They need different actions.
4. Add pairwise reconciliation for any two artifacts sharing a key. Forecast against GL on account,
   department and period would have surfaced the reclass automatically.
5. Give every use case one named deliverable with an acceptance test, at the resolution the
   data-corrections section already achieves.
6. Collapse the conditional use cases into the single gate they share, and price that gate.
7. Put remediation ahead of build, and let findings drive it.
8. Attach dependencies and owners to the delivery sequence.
9. Drop the four-dimension scores, or make them change an outcome.
10. Quantify findings where the number is cheap. "Includes `#REF!`" became far more useful as 595
    occurrences with 557 in one named tab.