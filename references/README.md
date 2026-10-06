# References: Source Documents

**None of this is uploaded to a Claude Project, and only this README is in Git.** It is the
provenance layer, kept in OneDrive.

The operative rules from these documents are synthesized into
`serif-policy-rules.md`, which *is* uploaded, about 2,000 tokens instead of ~18,000 of
policy prose per conversation. If a rule is disputed, check it here, then change it in the
synthesized file and in the engine's `policy.py`.

## `serif-policies/`

Serif's eight draft accounting policies, as received. All are **DRAFT and unapproved**.

## `not-serif-documents/`

Two documents that arrived in the Serif policy pack but do not describe Serif. Kept so
the exclusion is auditable rather than invisible.

* `CCC-treasury-policy-NOT-SERIF.docx`: names CrossCountry Consulting as the company,
  Investcorp as PE sponsor, Sage Intacct as system of record, ~35 cost centers. This is
  CCC's own treasury policy. Feeding it to an agent would inject another company's
  thresholds.
* `foreign-currency-memo-INDIA-ENTITY.docx`: a functional currency memo whose only
  analyzed entity is India. Serif has one US subsidiary and no India entity. Revisit if a
  foreign entity appears; Serif does post to FX accounts `8231000` and `8232000`.

Their presence suggests the policy pack was assembled from a template set rather than from
Serif's own documents. Worth raising with CCC.

## `reviewer-feedback/`

Reviews of the jumpstarts' subject matter by the channel partner's accountants. Reference
only: nothing here is an engine input.

* `ccc-ledger-review-questions-jun-aug2026.xlsx`: the Jan 2025 to Aug 2026 GL export with
  five pivots (vendor by account and department, account by vendor, bills by account and
  by department, and bills to prepaid and fixed-asset accounts) across Jun to Aug 2026,
  with the reviewer's questions in yellow beside the lines they concern. The questions
  drove the Vendors page, the three-month trend, and flux rules F6 to F10; see
  `../CHANGELOG.md`. It carries the full ledger, so it is client-confidential.
* `chris-gl-review-aug2026.html` and `chris-pl-flux-aug2026-v4.html`, now in `docs/spec/`:
  Chris's own Aug 2026 GL coding review and P&L flux reports, received 2026-09-30, and the
  layout Console 2.0.0 follows. They are a source of ideas
  only. Their figures are unverified and some are wrong, so take no figure, rule or entry
  from them. The ideas drawn from them are listed in Impulsive AIJ-93.
* A manual close review in three tabs, saved from Excel as CSV (Windows-1252, not UTF-8),
  received 2026-10-01:
  * `ck-manual-review-pl-by-department-jul-sep2026.csv`: a pivot of P&L net by department
    and account for Jul, Aug and Sep 2026 (the columns run Aug, Jul, Sep), with the
    reviewer's comment beside 17 lines. The comments cover:
    * bonus not yet accrued, and its payroll tax;
    * negative Insurance & Benefits in every department;
    * a contractor billed twice in September after a missed August accrual;
    * three miscodings (lab reagents in Facility Repairs & Maintenance, a barcode scanner
      in IT Consulting, a small item in Lab Non-Capital Equipment);
    * a negative year-to-date Office Supplies balance.
  * `ck-manual-review-balance-sheet-sep2026.csv`: two September balance sheet questions.
    The first is $41.97 capitalized to 1530000 Computers & Software, which may belong in
    expense. The second is $386,795.01 in 1710001 LQ Clearing Account, which asks what the
    account is used for and whether it is lease accounting.
  * `ck-manual-review-gl-detail-jan-sep2026.csv`: the Custom General Ledger for Jan to
    Sep 2026 behind the pivots (22,110 lines), with no comments. Its PO Number and PO
    Line Id columns are present but empty. It carries employee and contractor names, so
    it is client-confidential. It is a re-saved copy rather than a raw export, so no
    engine reads it.

## `format-examples/`

Another client's dashboard, kept as a reference for layout. Not Serif data: none of its
figures, vendors or accounts describe Serif.

* `aura-vendor-coding-dashboard-2026-06-OTHER-CLIENT.html`: a vendor coding review for a
  different company. The period-over-period, budget-coding and reclass tables are the
  model for the Serif schedules; its charts and summary panels were deliberately not
  carried over.
