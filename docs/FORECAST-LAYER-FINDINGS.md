# Forecast Layer: What the `EXT$_` Tabs Gave Us

**Prepared:** 2026-09-18 · **Status:** DRAFT, independently verified

Response to the 2026-09-18 feedback asking for a two-layer workflow, accounting first and FP&A second,
with the budget comparison driven off the `ext$_` tabs of `2026-08 Rolling Forecast.xlsx`.

The short version.
Both forecast vintages are inside that one workbook, so the second layer is unblocked from the file we
already hold.
Three findings came out of the extraction that matter more than the feed does: the workbook's own
chart-of-accounts tab is behind NetSuite on 21 codes in a way that would compare rent against
sequencing; a $4.47M reclass is staged in the model and not booked in the ledger; and the current
vintage's closed months are the posted actuals rather than a forecast, which changes what can honestly
be measured against them.

Every figure below was reproduced by a second reviewer working independently from the same raw files.

## What Was Extracted

Four tabs share one grid: `EXT$_R&D`, `EXT$_G&A`, `LAB` and `OH`.
Each holds one row per commitment with department, account, project, vendor, PO number, two notes and
a description, followed by month columns.

Each tab carries that grid **three times side by side**:

| Columns | Block | Contents |
|---|---|---|
| 0 to 44 | current | Aug 2026 vintage, labels 0-8, months 9-44 |
| 51 to 95 | prior | **June vintage**, labels 51-59, months 60-95 |
| 98 to 133 | delta | current less prior, computed by the workbook |

Cell `AZ18` is labelled `PRIOR` on all four tabs.
That block is the June cut, confirmed rather than assumed: it reconciles to the workbook's own
`Jun FCST` column on all 235 populated rows and to each tab's total.

`tools/forecast_to_csv.py` writes four files into `data/pending/`:

* `budget_fy2026_by_account_dept_month.csv`: 1,990 rows, from the **June** vintage by default
* `forecast_lines_2026-06.csv`: 3,115 un-aggregated June lines
* `forecast_lines_2026-08.csv`: 3,067 un-aggregated August lines
* `unmapped_forecast_accounts.csv`: 10 categories that could not be placed, for Unity to complete

Only the `EXT$_` tabs were named in the feedback.
`LAB` and `OH` are the same shape and carry lab supplies and overhead, so excluding them would report a
budget of zero on accounts that are in fact budgeted.

The June extraction reconciles exactly to the workbook: extracted $110,197,496.17 plus dropped
$2,871,559.75 equals the workbook's own $113,069,055.92, to the cent, with every dropped dollar
attributed to a named reason.

## Finding 1: The Workbook's COA Tab Is Behind NetSuite

The forecast tabs name accounts in prose while the ledger carries codes, so something has to bridge
them, and the workbook's `COA` tab looks like exactly that bridge.
It is stale.

Of the 65 account names appearing both on the COA tab and in the Aug 2026, Jul 2026 and Aug 2025
ledger slices, **21 carry a different code on the COA tab**. Whole ranges have been renumbered:

| Account | COA tab says | NetSuite says |
|---|---|---|
| Rent or Lease of Buildings | 6501000 | 6601000 |
| Building Operating Costs & CAM | 6509000 | 6609000 |
| Sequencing Costs | 6441000 | 6501000 |
| Other External Research costs | 6446000 | 6509000 |
| Travel | 6610000 | 6702000 |
| Depreciation - Lab Equipment | 8010000 | 7110000 |

Rows one and three are the dangerous pair. The old rent code is the new sequencing code, so mapping
through the COA tab puts the rent forecast onto the sequencing account and reports a large variance on
both, which is worse than reporting nothing.

The extractor maps through the **live ledger** and falls back to the COA tab only where the name never
posts to the GL and the COA code is not already occupied by a different ledger account.
That second condition matters: `Moving Expenses` is absent from the GL and the COA tab assigns it
6508000, which the ledger uses for **Partnered Research**. Six such fallbacks are refused and reported
rather than accepted.

Worth raising with Unity: this is a live FP&A model maintained against a stale account map.

## Finding 2: A $4.47M Reclass Is Staged in the Model and Not Booked

Eight lines form one paired entry repeated across four months, moving Production spend out of Lab
Supplies/Consumables and into CMC:

| Period | 6410000 Lab Supplies | 6504000 CMC |
|---|---|---|
| May 2026 | -1,080,283.01 | +1,080,283.01 |
| Jun 2026 | -1,777,915.27 | +1,777,915.27 |
| Jul 2026 | -871,932.09 | +871,932.09 |
| Aug 2026 | -739,899.48 | +739,899.48 |

**Total $4,470,029.85**, described on the line itself as `Claude Reclass: Labs to CMC`.

These are real workbook rows, not an extraction artifact: `LAB` rows 28 and 29 hold those values as
hardcoded numbers rather than formulas, and the workbook's own total column reads -4,470,029.85 and
+4,470,029.85.

Three things mark it as a manual topside. The rows are numbered `#102` and `#103`, out of sequence,
inserted between `#8` and `#9`. They carry no vendor and no PO. And they **do not exist in the June
vintage**, so they were added in this cut.

The decisive evidence is what happens when the reclass is backed out:

| | 6410000 | 6504000 |
|---|---|---|
| August vintage as extracted | 815,352.53 | 911,230.59 |
| August vintage less the reclass | 1,555,252.01 | 171,331.11 |
| **GL actual** | **1,555,252.01** | **171,331.11** |

Both land on the posted actuals exactly, in July as well as August.
So the August vintage for these accounts is the ledger with a manual reclass laid on top.

Two further lines on 6509000 are annotated `needs reclass to R&D`, totalling $2,147.59.

This is a question for Unity rather than a conclusion from us, since the model may be staging a
reclass that is deliberately not yet booked. It is also exactly the shape of output the feedback asked
for: a dimension called out, an amount, a reason carried on the line, and a correction that is either
booked or not.

## Finding 3: The Two Vintages Support Two Different Tests

Comparing each vintage's Aug 2026 figures to the Aug 2026 ledger:

| Vintage | Accounts in both | Tie to the cent |
|---|---|---|
| August (current) | 37 | **30** |
| June (prior) | 32 | **1** |

The current vintage's closed months are the posted actuals, so agreement there is definitional rather
than a measure of accuracy. An actual-versus-current-vintage comparison is a **reconciliation between
the FP&A model and the ledger**. It is a useful tie-out, it belongs in the first layer beside the other
consistency checks, and it is what surfaced the reclass above.

The June vintage is a real pre-month baseline. One account in thirty ties, seven of its account totals
are exact thousands against none in the August cut, and its largest gaps land where a June forecast
should be wrong about August. That is the **budget-versus-actual test**, and it is what the budget feed
is now built from.

An earlier draft of this document recommended requesting the June workbook from Unity. That was wrong.
It is block 2 of the file we already have.

One point on naming. This is a forecast re-cut monthly, not an approved budget. The extract records the
vintage on every row and leaves `approved_by` and `approved_date` empty, because the workbook records
no approval.

## Finding 4: The Rule Does Not Exist Yet

The budget feed now reads as present and both engines stop suppressing budget analysis.
Neither engine has a budget rule to run.

Verified by a controlled test: running UC2 with the feed populated and again with it emptied produces
**identical output**, 90 findings and $4,783,473.76 both times, with a full recursive diff showing only
the absent-feed roster changing from 8 entries to 7. Every finding, metric and amount is unchanged.

UC2 defines two emittable rules, `F1.VARIANCE` and `F3.ACCRUAL_RECEIPT`, neither of which reads a
budget value. `budget_amount` appears in the UC2 source exactly once, in the table that decides whether
a feed has arrived.

So the data side of the second layer is done and the rule side is the remaining work.

## Coverage: What the Feed Does Not Budget

The four build tabs plan external spend and overhead. Payroll is built on `FTE$` and depreciation on
`FA_CAP`, with further spend on `IN.VIVO+CMC`, `FSP`, `NHP`, `RODENT` and `CMC_BATCH`.

For Aug 2026, **16 P&L account codes totalling $1,241,861.44, or 29% of the month's $4,284,307.25 in
actuals, have no forecast line at all.** That is mostly payroll at $1.04M plus depreciation, interest
and FX.

This is worth stating plainly because the tie-out rates above are computed only over accounts the feed
covers. Extending coverage means reading `FTE$` and `FA_CAP`, which are differently shaped and are a
separate piece of work.

## On the Coupa and UKG Checks

Checked against the 9,571-line Coupa export.

**Line-level descriptions are there.** `Item` and `Detailed Item` are populated on 100% of lines with
real text, for instance `1 Each of Lipofectamine 3000 Transfection Reagent, 1.5 mL`. `Commodity` is
populated on 99.98%. About 97% of `Detailed Item` values carry a quantity prefix; the rest are free
text such as `SOW26.4 hCD34-NSG in vivo study at Umass`.

**The requisitioner is there. Their department is not.**
`Requested By (Header)` is populated on 100% of lines across 62 distinct names, as are `Created By` and
`Line Owner`.
A column named `Department` does ship in the export, but it is empty on all 9,571 rows, as are 25
other columns. So there is no usable requester-department data anywhere in the file.

That department has to come from UKG, and the access request is still in flight.

One correction to our own code while we are here. The UC1 engine records
`"Requester / Requester Dept"` as absent from the Coupa export, and the `coupa_extract.normalize`
docstring lists `Requester` flatly among absent columns. The requester name is present on every line.
Only the department is missing. This is the same class of defect as the department-code table already
corrected, and it should be fixed the same way.

## What Is Needed

1. **A view on the $4.47M reclass**: staged deliberately, or missed.
2. **Ten account mappings**, listed in `data/pending/unmapped_forecast_accounts.csv`. The largest is
   `FSP Charges – PBU` at $2.7M, which is a June-vintage name the August cut renamed to
   `FSP Charges - Origination`, so it needs confirming rather than guessing. Two rows carrying
   $3.5M have a blank department in the workbook.
3. **Confirmation on the COA tab**, which is a Unity-side maintenance issue in a live model.
4. **UKG access**, unchanged, and the only thing standing between us and the requisitioner check.

## Reproducing This

```sh
cd client-data-jumpstarts
python3 tools/forecast_to_csv.py \
    data/real/rolling_forecast_2026-08.xlsx \
    data/pending \
    --prior-vintage 2026-06 \
    --gl data/real/derived/netsuite_gl_aug2026.csv \
    --gl data/real/derived/netsuite_gl_jul2026.csv \
    --gl data/real/derived/netsuite_gl_aug2025.csv
```

Stdlib only, no dependencies, same as the engines.
Passing `--gl` is what makes the account mapping correct; without it the extractor falls back to the
stale COA tab and says so.
`--budget-from current` switches the feed to the August vintage for the reconciliation test described
in Finding 3.

## A Note on the Prior Block's Header

The prior block's month header **cannot be read** and the extractor deliberately ignores it.
On `EXT$_R&D` it is correct. On `EXT$_G&A`, `LAB` and `OH` it carries only 24 dates running Jan 2024 to
Dec 2025, a leftover from an older template, and the twelve unlabelled columns past it hold
$24,589,211.80 of real values.

Reading it literally would misdate every prior-vintage number by twelve months.
The months are therefore taken by position from the current block, which is verifiable rather than
assumed: 2025 is closed in both vintages, so entity-aligned rows must agree on 2025 months, and the
positional reading matches 100% of cells across all four tabs where the year-shifted reading matches as
little as 69%.

Anyone tempted to "fix" the extractor by reading that header should read this section first.
