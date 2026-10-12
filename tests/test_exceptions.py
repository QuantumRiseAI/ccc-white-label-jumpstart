"""Accepted exceptions: marked, kept, counted, and recorded in the manifest.

Runs the coding engine on the real exports in inputs/aug2026 with a reviewer's list
in a scratch folder (the list is a reviewer's input, not Serif data), then builds the
console from that run. Header-only and absent lists must change nothing.
    python3 tests/test_exceptions.py
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

B = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
I = os.path.join(B, "inputs", "aug2026")
HEADER = "vendor,account,reason,approved_by,approved_on\n"
fails = 0


def ok(cond, msg):
    global fails
    print(("  PASS " if cond else "  FAIL ") + msg)
    fails += not cond


def engine(pending, out):
    subprocess.run([sys.executable, "serif_uc1_engine.py", "--period", "Aug 2026", "--gl",
                    *glob.glob(I + "/netsuite_gl_detail_*.xls"), "--coupa",
                    glob.glob(I + "/coupa_po_lines_*.csv")[0], "--pending", pending, "--out", out,
                    "--quiet"], cwd=pending, check=True)
    return json.load(open(os.path.join(out, "aug2026", "run.json")))


def main():
    subprocess.run([sys.executable, os.path.join(B, "tools", "package.py")], check=True,
                   stdout=subprocess.DEVNULL)
    src = os.path.join(B, "out", "dist", "gl-coding-review")
    tmp = tempfile.mkdtemp()
    pend = os.path.join(tmp, "pending")
    shutil.copytree(src, pend)
    ok(open(os.path.join(pend, "accepted_exceptions.csv")).read() == HEADER,
       "the packaged template is header-only")
    base = engine(pend, os.path.join(tmp, "o0"))
    ok(base["manifest"]["exceptions"]["status"] == "header_only", "header-only list recorded")
    ok(not any(f.get("excepted") for f in base["findings"]), "header-only list marks nothing")

    victim = next(f for f in base["findings"] if f["rule_id"] == "T1.DEPT_INCONSISTENCY")
    vendor, account = victim["transaction"]["vendor_or_name"], victim["transaction"]["account_code"]
    with open(os.path.join(pend, "accepted_exceptions.csv"), "w") as h:
        h.write(HEADER + "%s,%s,Intended split,A. Approver,2026-10-01\n" % (vendor.upper(), account))
        h.write("Someone Else,,Missing the approver,,\n")
    run = engine(pend, os.path.join(tmp, "o1"))
    again = engine(pend, os.path.join(tmp, "o2"))
    marked = [f for f in run["findings"] if f.get("excepted")]
    ok(victim["finding_id"] in {f["finding_id"] for f in marked}, "listed vendor and account is excepted")
    ok(all(f["excepted"]["reason"] == "Intended split" for f in marked), "the reason travels with the finding")
    ok(len(run["findings"]) == len(base["findings"]) and run["summary"]["finding_count"] == base["summary"]["finding_count"],
       "excepted findings are kept and counted")
    ok(run["summary"]["excepted_count"] == len(marked) > 0, "summary counts the excepted")
    ok(run["manifest"]["exceptions"]["rejected"][0]["missing"] == ["approved_by"], "a row without an approver is rejected, not applied")
    ok(any(i["path"] == "accepted_exceptions.csv" and i["sha256"] for i in run["manifest"]["inputs"]), "the list is hashed into the manifest")
    ok(run["manifest"]["run_id"] != base["manifest"]["run_id"], "a different list gives a different run")
    strip = lambda r: [{k: v for k, v in f.items()} for f in r["findings"]]
    ok(strip(run) == strip(again) and run["manifest"]["run_id"] == again["manifest"]["run_id"], "same inputs, same artifact")

    page = os.path.join(tmp, "page")
    path = os.path.join(tmp, "o1", "aug2026", "run.json")
    subprocess.run([sys.executable, "serif_views.py", path, "--gl", *glob.glob(I + "/netsuite_gl_detail_*.xls"),
                    "--coupa", glob.glob(I + "/coupa_po_lines_*.csv")[0], "--roster", glob.glob(I + "/ukg_full_roster_*.csv")[0],
                    "--keep-names"], cwd=pend, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, "build_pages.py", "--only", "coding", "--coding-run", path, "--gl",
                    *glob.glob(I + "/netsuite_gl_detail_*.xls"), "--out", page], cwd=pend, check=True,
                   stdout=subprocess.DEVNULL)
    html = open(glob.glob(page + "/serif-gl-coding-review-*.html")[0]).read()
    ok("Accepted Exceptions" in html and "Intended split" in html and "A. Approver" in html,
       "the console lists accepted exceptions with the reason and approver")
    shutil.rmtree(tmp)
    sys.exit(1 if fails else 0)


main()
