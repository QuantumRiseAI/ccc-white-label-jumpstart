"""Assemble each Claude Project's upload folder from the repo.

    python3 tools/package.py            # writes out/dist/<project>/ and out/dist/<project>.zip,
                                        # and claude-projects/<Project name>/ in the repo
    python3 tools/package.py --check    # fails if claude-projects/ differs from the source

A Claude Project holds its files flat, so each Project gets one folder with every
file it needs side by side: the scripts from src/, its own docs from projects/,
the docs both Projects carry from projects/shared/, and the feed templates it reads
from templates/. Upload every file in the folder, and paste PROJECT_INSTRUCTIONS.md
into the Project's instructions. The repo keeps one copy of each file; this is the
only place they are combined.

claude-projects/<Project name>/ holds the same files in the repo as relative symlinks, with no
second copy of anything: PROJECT_INSTRUCTIONS.md, to paste, and upload/, every file to upload,
to select all and drag in. NetSuite's lists, Serif's data, are linked from inputs/reference/
(the OneDrive folder, not in Git), so the repo holds only the link. Do not edit it by hand: run
this script, and `make test` fails when it is out of date.
"""
import os
import shutil
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = ["serif_uc2_flux.py", "serif_views.py", "serif_sources.py", "serif_design.py",
           "serif_fonts.py", "build_pages.py", "netsuite_link_ids.sql",
           "netsuite_income_statement.sql", "netsuite_gl_detail.sql"]
SHARED = ["WHEN-DATA-BREAKS.md", "CONNECT-NETSUITE.md", "serif-accounts-and-departments.md",
          "serif-policy-rules.md", "WRITING-GUIDE.md"]
TEMPLATES = ["accruals_log.csv", "coupa_dept_code_mapping.csv", "fixed_asset_register.csv",
             "hris_headcount.csv", "open_purchase_commitments.csv", "payroll_register.csv",
             "prepaid_amortization_schedule.csv"]
# NetSuite's lists, for internal IDs in the import CSV. Serif's data, so they stay out of the repo:
# read from inputs/reference/ (the OneDrive folder) when it is there, and said when it is not.
NSREF = ["netsuite_ref_accounts.csv", "netsuite_ref_departments.csv", "netsuite_ref_programs.csv"]
# the committed folders, named as the Projects are in Claude and in OneDrive
NAMES = {"gl-coding-review": "GL Coding Review", "pl-flux": "P&L Flux"}
PROJECTS = {
    "gl-coding-review": {
        "scripts": ["serif_uc1_engine.py"] + SCRIPTS,
        "docs": ["PROJECT_INSTRUCTIONS.md", "HOW-TO-RUN.md", "GL_CODING_REVIEW_SKILL.md",
                 "serif-vendor-coding-baseline.md"],
        "templates": TEMPLATES + ["accepted_exceptions.csv", "ebitda_addback_mapping.csv",
                                  "netsuite_vendor_master.csv"],
    },
    "pl-flux": {
        "scripts": SCRIPTS,
        "docs": ["PROJECT_INSTRUCTIONS.md", "HOW-TO-RUN.md", "PL_FLUX_SKILL.md"],
        "templates": TEMPLATES + ["external_research_spend_detail.csv"],
    },
}


def sources(name, spec):
    files = ([os.path.join(ROOT, "src", f) for f in spec["scripts"]]
             + [os.path.join(ROOT, "projects", name, f) for f in spec["docs"]]
             + [os.path.join(ROOT, "projects", "shared", f) for f in SHARED]
             + [os.path.join(ROOT, "templates", f) for f in spec["templates"]])
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        sys.exit("Missing: " + ", ".join(os.path.relpath(f, ROOT) for f in missing))
    return files


def copy(files, out):
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    for f in files:
        shutil.copy2(f, out)
        os.chmod(os.path.join(out, os.path.basename(f)), 0o644)


def placed(name, spec):
    """Each committed link's path under claude-projects/, and the file it points to."""
    top = os.path.join(ROOT, "claude-projects", NAMES[name])
    files = sources(name, spec) + [os.path.join(ROOT, "inputs", "reference", f) for f in NSREF]
    return {os.path.join(top, "upload" if os.path.basename(f) != "PROJECT_INSTRUCTIONS.md" else "", os.path.basename(f)): f
            for f in files}


def link(name, spec):
    """One relative symlink per file, so the repo keeps one copy of each."""
    top = os.path.join(ROOT, "claude-projects", NAMES[name])
    shutil.rmtree(top, ignore_errors=True)
    os.makedirs(os.path.join(top, "upload"))
    for at, f in placed(name, spec).items():
        os.symlink(os.path.relpath(f, os.path.dirname(at)), at)


def package(name, spec, dist):
    out = os.path.join(dist, name)
    files = sources(name, spec)
    link(name, spec)
    ref = [os.path.join(ROOT, "inputs", "reference", f) for f in NSREF]
    if all(os.path.isfile(f) for f in ref):
        files += ref
    else:
        print("%s: NetSuite's lists not in inputs/reference/; add them to the Project by hand" % name)
    copy(files, out)
    with zipfile.ZipFile(out + ".zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(out)):
            z.write(os.path.join(out, f), os.path.join(name, f))
    print("%s: %d files, %s" % (name, len(files), os.path.relpath(out, ROOT)))


def check():
    """claude-projects/ against the source: one link per file, each to the file it names."""
    stale = []
    for name, spec in PROJECTS.items():
        want, top = placed(name, spec), os.path.join(ROOT, "claude-projects", NAMES[name])
        got = {os.path.join(d, f) for d, _, fs in os.walk(top) for f in fs if f != ".DS_Store"}
        got |= {os.path.join(d, x) for d, ds, _ in os.walk(top) for x in ds if os.path.islink(os.path.join(d, x))}
        rel = lambda p: os.path.relpath(p, os.path.join(ROOT, "claude-projects"))
        stale += ["%s missing" % rel(p) for p in sorted(set(want) - got)]
        stale += ["%s not in the source" % rel(p) for p in sorted(got - set(want))]
        stale += ["%s is not a link to %s" % (rel(p), os.path.relpath(want[p], ROOT)) for p in sorted(set(want) & got)
                  if not os.path.islink(p) or os.readlink(p) != os.path.relpath(want[p], os.path.dirname(p))]
    if stale:
        sys.exit("claude-projects/ is out of date; run `make package` and commit it:\n  " + "\n  ".join(stale))
    print("claude-projects/ matches the source")


if __name__ == "__main__":
    if sys.argv[1:] == ["--check"]:
        check()
        sys.exit()
    dist = os.path.join(ROOT, "out", "dist")
    for name, spec in PROJECTS.items():
        package(name, spec, dist)
