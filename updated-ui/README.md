# Updated UI

The GL Coding Review and P&L Flux consoles laid out as Chris's August reports, in Serif's
design. They show the same figures as the standard consoles, which are unchanged, and are built
from the same exports by the same engines.

## Consoles

`out/aug2026/`:

- `serif-gl-coding-review-aug2026-updated-ui-v1.html`
- `serif-pl-flux-aug2026-updated-ui-v1.html`

Each is one self-contained page. Decisions, commentary, sign-off and the audit log are kept in
the browser. The NetSuite import is downloaded from Export (GL) or Adjustments (flux).

## Pages

| GL Coding Review | P&L Flux |
|---|---|
| Overview | Executive Overview |
| Review: CapEx Flags, Prepaid Flags, Dept & Entity | Analysis: Actual vs. Actual (MoM), Actual vs. Budget, By Department (MoM), Payroll Analytics |
| Transparency: Reviewed & Cleared, New This Period | Close Workflow: Balance Sheet Flux, Adjustments, SOX & GAAP |
| Documentation: Audit Log, SOX Documentation, Export | |

## Build

From `serif-data-jumpstarts/`, with the month's exports in `<jumpstart>/monthly-inputs/<period>/`:

```sh
bash updated-ui/build_runs.sh aug2026        # runs, to updated-ui/runs/aug2026/<jumpstart>/run.json
python3 updated-ui/build_pages.py aug2026    # consoles, to updated-ui/out/aug2026/
```

`build_runs.sh` runs each engine and `serif_views.py` with `--keep-names`, so names and pay are
not redacted, and, for the flux, `--balance-sheet` with the NetSuite Balance Sheet report.
`build_pages.py` reads those runs, the GL export and the Income Statement by month report, and
writes both consoles. Every figure is computed from them.

The runs hold employee names and pay.

## As a Claude Project

`upload-to-project/` is the Project folder: the engines, the views, `build_pages.py`, the design
files, the reference files, [`PROJECT_INSTRUCTIONS.md`](upload-to-project/PROJECT_INSTRUCTIONS.md)
and [`HOW-TO-RUN.md`](upload-to-project/HOW-TO-RUN.md). Upload every file in it. A run from that
folder on the Aug 2026 exports gives the same runs as the repo build.

`build_runs.sh` keeps the scripts in it the same as the jumpstarts' own: edit the shared scripts in
`pl-flux/upload-to-project/`, the coding engine in `gl-coding-review/upload-to-project/`, and
`build_pages.py` here.

## Tests

`tests/` holds the tests written for the earlier `--layout ui-update` console. They do not match
these pages yet.
