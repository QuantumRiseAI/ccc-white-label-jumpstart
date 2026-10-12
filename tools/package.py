"""Assemble each Claude Project's upload folder from the repo.

    python3 tools/package.py            # writes out/dist/<project>/ and out/dist/<project>.zip

A Claude Project holds its files flat, so each Project gets one folder with every
file it needs side by side: the scripts from src/, its own docs from projects/,
the docs both Projects carry from projects/shared/, and the feed templates it reads
from templates/. Upload every file in the folder, and paste PROJECT_INSTRUCTIONS.md
into the Project's instructions. The repo keeps one copy of each file; this is the
only place they are combined.
"""
import os
import shutil
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = ["serif_uc2_flux.py", "serif_views.py", "serif_sources.py", "serif_design.py",
           "serif_fonts.py", "build_pages.py", "netsuite_link_ids.sql"]
SHARED = ["WHEN-DATA-BREAKS.md", "CONNECT-NETSUITE.md", "serif-accounts-and-departments.md",
          "serif-policy-rules.md"]
TEMPLATES = ["accruals_log.csv", "coupa_dept_code_mapping.csv", "fixed_asset_register.csv",
             "hris_headcount.csv", "open_purchase_commitments.csv", "payroll_register.csv",
             "prepaid_amortization_schedule.csv"]
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


def package(name, spec, dist):
    out = os.path.join(dist, name)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    files = ([os.path.join(ROOT, "src", f) for f in spec["scripts"]]
             + [os.path.join(ROOT, "projects", name, f) for f in spec["docs"]]
             + [os.path.join(ROOT, "projects", "shared", f) for f in SHARED]
             + [os.path.join(ROOT, "templates", f) for f in spec["templates"]])
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        sys.exit("Missing: " + ", ".join(os.path.relpath(f, ROOT) for f in missing))
    for f in files:
        shutil.copy2(f, out)
        os.chmod(os.path.join(out, os.path.basename(f)), 0o644)
    with zipfile.ZipFile(out + ".zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(out)):
            z.write(os.path.join(out, f), os.path.join(name, f))
    print("%s: %d files, %s" % (name, len(files), os.path.relpath(out, ROOT)))


if __name__ == "__main__":
    dist = os.path.join(ROOT, "out", "dist")
    for name, spec in PROJECTS.items():
        package(name, spec, dist)
