# Claude Projects: What to Upload

One folder per Claude Project:

| Folder | Claude Project |
|---|---|
| `GL Coding Review/` | GL Coding Review, run first in the close, on the raw ledger |
| `P&L Flux/` | P&L Flux, run last, on the corrected ledger |

Each holds two things:

* `PROJECT_INSTRUCTIONS.md`, to paste into the Project's instructions field. It is not an upload.
* `upload/`, every file the Project needs and nothing else (31 for GL Coding Review, 27 for P&L
  Flux). Select all, and drag them into the Project's files.

## Loading a Project

1. Paste `PROJECT_INSTRUCTIONS.md` into the Project's instructions field.
2. Delete the Project's old files.
3. Open `upload/`, select every file, and drag them into the Project.
4. Start a new chat for the close and attach the month's exports.

## How the Folders Are Made

Every file here is a relative symlink to its one copy in the repo (`src/`, `projects/`,
`templates/`), so nothing is stored twice and the folders cannot drift from the code.
`tools/package.py` writes them (`make package`), and `make test` fails when they are out of
date. Do not edit them by hand.

NetSuite's three lists in `upload/` (`netsuite_ref_accounts.csv`, `netsuite_ref_departments.csv`,
`netsuite_ref_programs.csv`) are Serif's data, so the repo holds only the links. They point to
`inputs/reference/`, which links to the engagement's OneDrive,
`7-technical-documentation/3-data/netsuite reference/`. Without that link set up, those three show
as broken: point `inputs/` at the OneDrive data first (the repo README, In Git, says how).

On Windows, clone with `git clone -c core.symlinks=true`. GitHub's web view shows each link as
the path it points to; use a clone, or `out/dist/<project>.zip` from `make package`, which holds
real copies of every file.
