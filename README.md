# Serif Jumpstarts: Real Data Build

Two Claude Project agents adapted from the CrossCountry CrossCore AI Jumpstart to run on Serif
Biomedicines' actual NetSuite ledger instead of the synthetic dataset.

* Built: 2026-09-16 by Quantum Rise, last updated 2026-10-06 (Console 2.0.0)
* Runs every month. Reference period: Aug 2026
* Status: runnable today on real GL and forecast data. Budget variance is live as of UC2 engine
  0.3.0, using the June forecast vintage extracted from the rolling forecast workbook

## Run Order: Coding Review First, Flux Last

These two sit at opposite ends of the close, and running them out of order wastes work.

1. **GL Coding Review** runs first, on the raw ledger.
   It tees up the corrections, so the accruals, prepaid and fixed-asset work in the middle of
   the close starts from a cleaner coding base.
2. The close proceeds: accruals booked, prepaids amortized, fixed assets recorded.
3. **P&L Flux** runs last, on the corrected ledger.
   It is the final check that the numbers are right, and it produces the commentary that goes
   to the senior leadership team.

Running flux on an uncorrected ledger surfaces variances that are really coding errors, so the
same item gets investigated twice. Coding Review first means fewer reclassifications to explain.

## Layout

```
serif-jumpstarts/
├── README.md
├── CHANGELOG.md               every console, engine and views version
├── Makefile                   make package | make build PERIOD=aug2026 | make test
├── claude-projects/           each Claude Project's instructions and upload/ folder, as links to the files below
├── src/                       the scripts, one copy each: engines, views, readers, console
├── projects/                  what is particular to each Claude Project
│   ├── gl-coding-review/      its instructions, how-to, skill and vendor baseline
│   ├── pl-flux/               its instructions, how-to, skill and status
│   └── shared/                docs both Projects carry: Serif context, data rules, NetSuite
├── templates/                 header-only feed templates the engines read when present
├── consoles/                  the current console for each Project; earlier versions are in Git history
├── design-system/             Serif's tokens, open fonts and brand references
├── docs/                      the data manifest, internal notes, and spec/ (Chris's August reports)
├── tests/                     test_console.js, the console tests
├── tools/                     build.sh, package.py, compare_runs.py, bundle_engine.py, cost-model/
├── inputs/<period>/           Serif's exports for a close, as each system wrote them (not in Git)
└── out/                       build output: dist/ (the Project folders) and <period>/ (not in Git)
```

Each file lives once. `claude-projects/GL Coding Review/` and `claude-projects/P&L Flux/` show
exactly what each Project takes: `PROJECT_INSTRUCTIONS.md` to paste, and `upload/`, every file to
upload, to select all and drag in. Each is a relative symlink to its copy in `src/`,
`projects/` or `templates/`, or for NetSuite's lists to `inputs/reference/` (see
[`claude-projects/README.md`](claude-projects/README.md)).
`tools/package.py` writes them, and `make test` fails when they are out of date. It also
assembles each Project's upload folder, flat, with real copies, in `out/dist/<project>/` (and a
`.zip`): the scripts from `src/`, the Project's docs, the shared
docs and its templates. The build runs from those folders, so what is tested is what is
uploaded. `inputs/<period>/` holds a close's exports exactly as each system writes them;
neither engine reads a sliced or derived file.

### The Console

Console 2.0.0 is laid out as Chris's August reports, in Serif's design: the GL review as
Overview, Review, Transparency and Documentation; the flux pack as Executive Overview,
Analysis and Close Workflow. `build_pages.py` builds it from the run, in each Project. Each
proposed Journal Entry is filled in and editable, every vendor card shows its last three
months, and the NetSuite CSV takes the entries as edited. Published as a claude.ai Artifact,
the console is shared by everyone with access. The decision record, the run log and Claude's
drafts work as they did in 1.8.

`consoles/` holds one file per Project, `serif-gl-coding-review.html` and `serif-pl-flux.html`,
and each console version is a commit to them, tagged `console-v<version>`: v1.8.3 to v1.8.8,
then v2.0.0. To see or diff a past version, use the tag:

```sh
git tag -l 'console-v*'
git show console-v1.8.8:consoles/serif-pl-flux.html > serif-pl-flux-v1.8.8.html
```

The 1.8 generator, `build_report.py`, and its tests are in the history before 2.0.0 (the
repo's first commit). The month a console shows is only the input data it was built from (Aug
2026 for all of these).

### Working in the Repo

Python 3.9 or newer, standard library only. The tests need Node and Playwright.

```sh
make package                  # claude-projects/ (links), and out/dist/<project>/ (copies) with .zip
make build PERIOD=aug2026     # both Projects' commands on inputs/aug2026/, from out/dist/
make test                     # claude-projects/ up to date, then the console and engine tests
```

`make build` writes `out/<period>/<project>/run.json` and the month's console, and copies the
console to `consoles/`. The console version is `VERSION` in `src/build_pages.py`. Mint a new one
only when it is agreed: add it to `CHANGELOG.md`, commit the rebuilt consoles, and tag the
commit `console-v<version>`.

### In Git

The repo is private. `.gitignore` leaves out Serif's data: `inputs/`, `out/` (the runs and
local builds), the local `data/` and `status/` folders, and everything in `references/` but
its README. Chris's two August reports are kept in `docs/spec/`. The consoles in `consoles/`
are committed, every version: they carry the ledger, names and pay, for the accounting team. To rebuild a
month from a clone, put its exports in `inputs/<period>/` and run `make build`. The simplest
way is to link into the engagement's OneDrive data, `7-technical-documentation/3-data/`, from
the repo root (`.gitignore` leaves out `inputs` whether it is a folder or a link):

```sh
D="$HOME/Library/CloudStorage/OneDrive-QuantumRise/Clients - Active - Documents/Serif Biomedicines (CCC)/1-Serif-FDE-Support/7-technical-documentation/3-data"
mkdir -p inputs
ln -s "$D/2026-08 exports" inputs/aug2026
ln -s "$D/2026-09 exports" inputs/sep2026
ln -s "$D/netsuite reference" inputs/reference
```

`inputs/reference/` is also where `claude-projects/*/upload/` finds NetSuite's lists.

## Setup

Two Projects, one per use case. They are not combined, because the two have different
instructions, different reference material and different run orders.

Configure once:

Step by step, including updating a Project that is already set up, in [`claude-projects/README.md`](claude-projects/README.md).

1. Create a Claude Project named `Serif Biomedicines, GL Coding Review` or
   `Serif Biomedicines, P&L Flux`.
2. Paste `PROJECT_INSTRUCTIONS.md` from `claude-projects/<Project>/` into the Project
   Instructions field. It is instructions, not an upload.
3. Open `claude-projects/<Project>/upload/`, select every file and drag them into the Project.
   NetSuite's three lists there link to the OneDrive data through `inputs/`, so set that up
   first. `make package` also puts every file, as real copies, in `out/dist/<project>/` and
   its `.zip`.

Then each month:

4. Start a fresh chat in the Project and attach the month's exports, as each system wrote
   them. Each `HOW-TO-RUN.md` lists them under Each Month.
5. Prompt: `Run the GL coding review for Sep 2026.` or `Run the P&L flux for Sep 2026.`

Two things to know about Project uploads. They are **flat**, so the scripts are invoked by bare
filename. And the header-only template files must be uploaded, since their presence
is how each agent detects a missing feed and reports the gap instead of quietly skipping a test.

## What Changed From the Synthetic Package

The synthetic package described a company that does not exist.
Reading the real GL export made that unmistakable.

* **Entities**, synthetic assumed a US and an EU entity with cross-entity miscoding as the top
  severity class. Serif has exactly one subsidiary, `FL87 Serif Biomedicines, Inc.`, across all
  44,013 lines. The entire entity test is removed.
* **Chart of accounts**, synthetic used invented 4-digit accounts. Serif uses 7-digit hierarchical
  NetSuite account paths with 139 leaf accounts.
* **Departments**, synthetic used numeric 200/300/400. Serif uses ten department names, and 42% of
  lines sit in `Non-Specific`.
* **Source systems**: Coupa (since about Sept 2025, Prendio before it), UKG as the HRIS, ADP
  and Expensify. Adaptive Planning is unconfirmed.
* **Vendors**, the synthetic vendor table was largely fictional. Serif's real top vendors are
  Flagship Labs LLC, Fisher Scientific, Mirai Bio, New England BioLabs, and Aldevron. Corporate
  counsel is K&L Gates, not Cooley or Gunderson.
* **Business narrative**, the synthetic P&L Flux agent hard-coded an IRB dosing pause, a VP Legal
  hire, a Series B, and a $62.4K CRO accrual. All fictional. All removed.
* **Thresholds**, synthetic invented $25K and $50K materiality and a $5K PP&E threshold. Serif's
  own draft policies set $10,000 pre-close, $100,000 quarterly post-close, $5,000 accrual, $10,000
  prepaid, and **no fixed asset threshold at all**, deliberately. On 12 Oct 2026 Serif set its own
  (Mike's write-up): **$5,000** PP&E capitalization and **$25,000** prepaid, which the engines and
  the GL Coding Review's CapEx and Prepaid screens now apply.

The change log is [`CHANGELOG.md`](CHANGELOG.md).

## Two Additions Driven by the Real Data

* **Unallocated spend review**, in GL Coding. `Non-Specific` carries 18,391 of 44,013 lines. This is
  Serif's largest actual coding-quality issue and has no synthetic analogue.
* **Receipt-based accrual completeness**, in both agents. Coupa records goods receipts, so accruals
  are identified from what was received but not yet invoiced, roughly **$110K for Aug 2026** and
  **$402K for calendar 2026 to date**. A billing-pattern method (trailing three-month average, per
  Serif's Accrued Expense Policy) is the fallback for suppliers and periods Coupa does not reach.
  Open PO commitments, ordered but *not* received, about $1.37M in Aug 2026, are reported as a
  disclosure and never accrued.

## Honest Status

Real and working now:

* The NetSuite Custom General Ledger export, Jan 2025 to Aug 2026, read as NetSuite wrote it
* Every period ties out: debits equal credits to exactly $0.00
* Coupa PO lines for calendar 2026, 9,571 lines, $21.1M, read as Coupa wrote them
* The rolling forecast workbook, read for the plan and for Forecast vs. Actual
* Reported income statements and balance sheets for cross-checking
* Serif's real chart of accounts, department list, and how its top vendors are actually coded
* Serif's draft accounting policies as the threshold source

Not yet available, with placeholders in `templates/`:

* Payroll register (access request in flight). This is now the largest remaining gap: it
  blocks payroll tie-out. The UKG roster arrived 2026-09-24 and runs the
  requisitioner-versus-coding department check, as the requester flag
* Vendor master, fixed asset register, prepaid schedule, accruals log
* Coupa invoice-level data, without which there is no three-way match
* The 2025 and Open tabs of the Coupa pull; only calendar 2026 arrived
* Serif's confirmation of the Coupa department code mapping, which is now read through UKG's
  department codes
* External research unbilled WIP detail
* The EBITDA add-back mapping the Data Entry Policy refers to

Both agents run with any subset present, name every absent feed in their load summary, and state
which findings are suppressed.
Nothing is fabricated to fill a gap.

## Caveats Worth Carrying Into the Readout

* All policies in `references/` are DRAFT and unapproved. Every threshold in both agents
  rests on unapproved documents.
* The vendor coding baseline is descriptive. It records what Serif does, which is not necessarily
  what Serif should do. It is evidence, not policy.
* The Treasury policy found in the Serif policy folder is CrossCountry Consulting's own policy, not
  Serif's. It is excluded from both agents. See [`docs/DATA-MANIFEST.md`](docs/DATA-MANIFEST.md).
* Accrual estimates are pattern-derived and need controller confirmation before anything posts.
* IRC §174 output is preliminary and needs tax counsel sign-off.

## Related

* [`docs/DATA-MANIFEST.md`](docs/DATA-MANIFEST.md), file origins, name mapping, and the full gap list
* [`docs/SERIF_REAL_DATA_GAPS.md`](docs/SERIF_REAL_DATA_GAPS.md), the earlier gap analysis prepared for
  the latest client confirmation, now superseded by the manifest.
* `synthetic-jumpstarts/`, the original CCC mock package, kept beside this folder in OneDrive
  for reference
