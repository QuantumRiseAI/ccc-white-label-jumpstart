"""Flagship pass-through bills (SERIF-148): the cost breakdown reader, the month's bills, and
a console build on the Aug 2026 exports with a breakdown made up for one of its bills. The
breakdowns here are synthetic, laid out as NetSuite's "FSM| Unbilled Cost by Customer Detail
w Acct V2" saved search exports them; no Serif data is kept in the repo.

    python3 tests/test_passthrough.py      (after `make build PERIOD=aug2026` for the build checks)
"""
import csv
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(B, "src"))
import serif_sources as S  # noqa: E402

FAILED = []


def ok(cond, label):
    print(("  PASS " if cond else "  FAIL ") + label)
    if not cond:
        FAILED.append(label)


HEAD = ["Customer", "Type", "Date", "Concur Script", "Account: Mask Detail", "Name", "Class", "Entity: Name", "Account (Line): Number",
        "Account (Line): Name (GL-style)", "Document Number", "Header Memo", "Line Item Memo", "Employee Name", "Department: Name",
        "Projects: Name", "Amount", "Flagship Company: Name", "Invoice"]


def breakdown(path, invoice, lines):
    """lines: (account number, account name, vendor, header memo, line memo, amount)."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        for t in ("Flagship Pioneering, LLC", "FSP ALL : Flagship Labs LLC", "FSM| Unbilled Cost by Customer Detail w Acct V2", "From Jan 2020 to Aug 2026", "", ""):
            w.writerow([t])
        w.writerow(HEAD)
        for no, name, vendor, hm, lm, amt in lines:
            w.writerow(["", "Bill", "2026-08-01", "No", "No", "Serif Biomedicines, Inc.", "Origination", vendor, no, name, "D-1", hm, lm, "", "530 IT", "", amt, "Serif Biomedicines, Inc.", invoice])
        w.writerow(["Total - Serif Biomedicines, Inc."] + [""] * 15 + [round(sum(x[5] for x in lines), 2), "Serif Biomedicines, Inc.", invoice])


with tempfile.TemporaryDirectory() as d:
    print("The cost breakdown, as exported")
    p = os.path.join(d, "flagship_breakdown_INV1.csv")
    breakdown(p, "INV1", [(6100, "6100.01 - Consulting:6100 - Consultants", "Bay State IT Inc.", "Parking Aug 2026", "T&E", 163.54),
                          (6555, "6550.01 - Software:6555 - Software Costs", "Amazon Web Services Inc", "Notion Renewal 7/15/26-6/1/27", "1st Year", 13346.19)])
    b = S.read_flagship_breakdown(p)
    ok(len(b) == 1 and b[0]["invoice"] == "INV1" and len(b[0]["lines"]) == 2 and b[0]["total"] == 13509.73 and b[0]["stated_total"] == 13509.73,
       "the title rows and the Total row are passed over; the items and the stated total are read")
    ok(b[0]["lines"][0]["acct_no"] == "6100" and b[0]["lines"][1]["header_memo"].startswith("Notion"), "each item keeps its Flagship account and memos")
    ok(S.read_flagship_breakdowns([os.path.join(d, "flagship_breakdown_*.xlsx")]) == {}, "a pattern that matched no file is passed over")
    bad = os.path.join(d, "x.csv"); open(bad, "w").write("a,b\n1,2\n")
    try:
        S.read_flagship_breakdown(bad); ok(False, "a file that is not a breakdown stops")
    except SystemExit as stop:
        ok("not a Flagship cost breakdown" in str(stop), "a file that is not a breakdown stops, saying so")

    print("The month's pass-through bills")
    L = lambda vendor, doc, acct, amt, typ="Bill": {"vendor_or_name": vendor, "document_number": doc, "account_code": acct, "account_leaf": "", "department": "General G&A",
                                                     "amount": amt, "txn_type": typ, "date": "2026-08-31", "coupa_url": "", "internal_id": "1", "project": "", "program": ""}
    bp = {"Aug 2026": [L("Flagship Labs LLC", "INV1", "6201000", 100.0), L("Flagship Labs LLC", "INV1", "6816000", 50.0), L("Flagship Labs LLC", "INV1", "2000100", -150.0),
                       L("Flagship Labs LLC", "INV2", "6901000", 900.0), L("Flagship Pioneering Labs TPC Inc", "INV3", "6410000", 20.0),
                       L("Flagship Labs Explorations Inc", "INV4", "6601000", 10000.0), L("Flagship Labs LLC", "JE9", "6201000", 5.0, "Journal")]}
    bills = S.passthrough_bills(bp, "Aug 2026")
    ok([b_["document"] for b_ in bills] == ["INV1", "INV3"] and bills[0]["amount"] == 150.0,
       "Flagship Labs LLC and TPC bills, expense lines only; the FSP charges, other Flagship entities and journals are not pass-through")

# The console, on the Aug exports, with a breakdown made up for one of its bills.
I = os.path.join(B, "inputs", "aug2026")
RUN = os.path.join(B, "out", "aug2026", "gl-coding-review", "run.json")
DIST = os.path.join(B, "out", "dist", "gl-coding-review")
GL = sorted(glob.glob(os.path.join(I, "netsuite_gl_detail_*.xls*")))
if not (GL and os.path.exists(RUN) and os.path.isdir(DIST)):
    print("  SKIP the console build checks: run `make build PERIOD=aug2026` first")
else:
    sys.argv = ["x"]
    bills = S.passthrough_bills(S.read_gl(GL)[0], "Aug 2026")
    bill = next(b_ for b_ in bills if any(l["account_code"] == "6201000" for l in b_["lines"]))
    cons = next(l for l in bill["lines"] if l["account_code"] == "6201000")
    rest = [l for l in bill["lines"] if l is not cons]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "flagship_breakdown_test.csv")
        items = [(6100, "6100 - Consultants", "Bay State IT Inc.", "Bay State IT - Parking Aug 2026", "BSIT T&E", 100.0),
                 (6100, "6100 - Consultants", "Kyndryl Inc", "Kyndryl Cloud Mgmt Aug 2026", "Monthly", round(cons["amount"] - 100.0, 2))]
        items += [(7000 + n, "%d - Other" % (7000 + n), "Vendor %d" % n, "Item %d" % n, "", l["amount"]) for n, l in enumerate(rest)]
        breakdown(p, bill["document"], items)
        out = os.path.join(d, "out")
        r = subprocess.run([sys.executable, "build_pages.py", "--only", "coding", "--coding-run", RUN, "--gl", *GL, "--flagship-breakdown", p, "--out", out],
                           cwd=DIST, capture_output=True, text=True)
        html = open(glob.glob(os.path.join(out, "*.html"))[0], encoding="utf-8").read() if r.returncode == 0 else ""
        ok(r.returncode == 0 and 'id="p-pass"' in html, "the console builds with a breakdown, and has a Pass-Through Bills page")
        data = json.loads(re.search(r"<script>window\.DATA=(\{.*?\});</script>", html, re.S).group(1).replace("<\\/", "</")) if html else {}
        pt = [k for k in data.get("je", {}) if k.startswith("PT-")]
        lines = data["je"][pt[0]]["lines"] if pt else []
        ok(len(pt) == 1 and {(l["account"], l["debit"], l["credit"]) for l in lines} == {("6603000", 100.0, 0), ("6201000", 0, 100.0)},
           "the parking item booked to consulting is reclassed to Parking, from the breakdown")
        ok("tie to the bill, each activity to its booked line" in html, "the breakdown ties to the bill, each activity to its booked line")
        ok(html.count("Reviewed in Coupa") == len(bills) - 1, "every other bill, with no breakdown, is reviewed in Coupa and blocks nothing")
        other = "".join(m.group(0) for m in re.finditer(r'<section class="page" id="p-(?!pass")[^"]*".*?</section>', html, re.S))
        on = [b_["document"] for b_ in bills if re.search(r"\bBill %s\b" % re.escape(b_["document"]), other)]
        ok(other.count('class="ptflag"') >= len(on), "cards on other screens for a pass-through bill say so (%d this month)" % len(on))

print("all passed" if not FAILED else "%d failed" % len(FAILED))
sys.exit(1 if FAILED else 0)
