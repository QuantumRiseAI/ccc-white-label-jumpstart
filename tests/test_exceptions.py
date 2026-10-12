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
    # Vendors of findings that are not coding findings, listed with a blank account
    # (every account): the list must not touch posting-lag, cutoff or tax findings.
    other = [f for f in base["findings"] if not f["rule_id"].startswith(("T1.", "T4."))]
    other_vendors = sorted({(f.get("transaction") or {}).get("vendor_or_name", "") for f in other} - {""})
    ok(bool(other), "the real run has posting-lag or tax findings to test against")
    path_list = os.path.join(pend, "accepted_exceptions.csv")
    with open(path_list, "w") as h:
        h.write(HEADER + "%s,97-%s-9--4,Intended split,A. Approver,2026-10-01\n" % (vendor.upper(), account))
        h.write("Someone Else,,Missing the approver,,\n")
        h.write("Shifted, Comma,6410000,Reason,Approver,2026-10-01\n")
        h.write("Nobody At All,,Matches nothing,A. Approver,2026-10-01\n")
        for v in other_vendors:
            h.write('"%s",,No lag or tax,A. Approver,2026-10-01\n' % v)
    run = engine(pend, os.path.join(tmp, "o1"))
    again = engine(pend, os.path.join(tmp, "o2"))
    marked = [f for f in run["findings"] if f.get("excepted")]
    ex = run["manifest"]["exceptions"]
    ok(victim["finding_id"] in {f["finding_id"] for f in marked}, "listed vendor and account is excepted (account read from 97-6410000-9--4)")
    ok(all(f["excepted"]["reason"] == "Intended split" or f["excepted"]["reason"] == "No lag or tax" for f in marked), "the reason travels with the finding")
    ok(all(f["rule_id"] in ("T1.DEPT_INCONSISTENCY", "T4.PO_ACCOUNT_MISMATCH") for f in marked),
       "only coding findings are excepted, never posting lag or tax")
    ok(all(not f.get("excepted") for f in run["findings"] if not f["rule_id"].startswith(("T1.", "T4."))), "posting-lag and tax findings stay open")
    ok(len(run["findings"]) == len(base["findings"]) and run["summary"]["finding_count"] == base["summary"]["finding_count"],
       "excepted findings are kept and counted")
    ok(run["summary"]["excepted_count"] == len(marked) > 0, "summary counts the excepted")
    ok([r["row"] for r in ex["rejected"]] == [3, 4], "rejected rows carry the file's line numbers: %s" % ex["rejected"])
    ok(ex["rejected"][0]["problems"] == ["approved_by"] and "extra columns" in ex["rejected"][1]["problems"][0],
       "a missing approver and a comma-shifted row are rejected, not applied")
    ok(any(u["vendor"] == "Nobody At All" and u["row"] == 5 for u in ex["unmatched"]), "a row that matches nothing is listed")
    ok(any(i["path"] == "accepted_exceptions.csv" and i["sha256"] for i in run["manifest"]["inputs"]), "the list is hashed into the manifest")
    ok(run["manifest"]["run_id"] != base["manifest"]["run_id"], "a different list gives a different run")
    ok(run["manifest"]["engine_version"] == "0.3.0", "engine version bumped")
    ok(run["findings"] == again["findings"] and run["manifest"]["run_id"] == again["manifest"]["run_id"], "same inputs, same artifact")

    # Unreadable files are reported, never fatal.
    for label, data in (("cp1252 file", ("%s,%s,Caf\xe9 split,A. Approver,\n" % (vendor, account)).encode("cp1252")),
                        ("zero-byte file", b"")):
        with open(path_list, "wb") as h:
            h.write(HEADER.encode() + data if data else b"")
        r = engine(pend, os.path.join(tmp, "o3"))
        e3 = r["manifest"]["exceptions"]
        if label == "cp1252 file":
            ok(e3["status"] == "applied" and any(f.get("excepted") for f in r["findings"]), "a cp1252 (Excel CSV) file is read")
        else:
            ok(e3["status"] == "malformed" and not any(f.get("excepted") for f in r["findings"]), "a zero-byte file is malformed, not header-only")
    with open(path_list, "w") as h:
        h.write(HEADER + "%s,%s,Intended split,A. Approver,2026-10-01\n" % (vendor, account))
        h.write("Nobody At All,,Matches nothing,A. Approver,2026-10-01\n")
        h.write("Someone Else,,Missing the approver,,\n")
    run = engine(pend, os.path.join(tmp, "o1"))

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
    ok("Rows Not Applied" in html and "Matched nothing, line 3" in html and "Rejected, line 4" in html,
       "the console shows rejected and unmatched rows with their lines")
    n = sum(1 for f in run["findings"] if f.get("excepted"))
    amt = sum(f["amount_at_risk"] for f in run["findings"] if f.get("excepted"))
    ok("Of which accepted exceptions</td><td class=\"mono\" style=\"text-align:right\">%d items, $%s" % (n, format(amt, ",.2f")) in html,
       "SOX page shows the excepted count and amount beside the totals")
    ok("plus %d accepted exception" % n in html and "not counted here" not in html, "hero counts only what is excepted, consistently worded")
    ok(("Accepted exceptions</td><td class=\"mono\" style=\"text-align:right\">%d items" % n) in html, "SOX page keeps accepted exceptions beside the department and account flags")
    shutil.rmtree(tmp)
    sys.exit(1 if fails else 0)


main()
