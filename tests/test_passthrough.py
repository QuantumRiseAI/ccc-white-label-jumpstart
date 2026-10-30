"""Plurality pass-through bills (CCC-148): the cost breakdown reader, the month's bills, and
a console build on the Aug 2026 exports with a breakdown made up for one of its bills. The
breakdowns here are synthetic, laid out as NetSuite's "FSM| Unbilled Cost by Customer Detail
w Acct V2" saved search exports them; no client data is kept in the repo.

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
import client_sources as S  # noqa: E402

FAILED = []


def ok(cond, label):
    print(("  PASS " if cond else "  FAIL ") + label)
    if not cond:
        FAILED.append(label)


HEAD = ["Customer", "Type", "Date", "Concur Script", "Account: Mask Detail", "Name", "Class", "Entity: Name", "Account (Line): Number",
        "Account (Line): Name (GL-style)", "Document Number", "Header Memo", "Line Item Memo", "Employee Name", "Department: Name",
        "Projects: Name", "Amount", "Plurality Company: Name", "Invoice"]


def breakdown(path, invoice, lines):
    """lines: (account number, account name, vendor, header memo, line memo, amount)."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        for t in ("Plurality Group, LLC", "PG ALL : Plurality Group, LLC : Plurality Labs LLC", "FSM| Unbilled Cost by Customer Detail w Acct V2", "From Jan 2020 to Aug 2026", "", ""):
            w.writerow([t])
        w.writerow(HEAD)
        for no, name, vendor, hm, lm, amt in lines:
            w.writerow(["", "Bill", "2026-08-01", "No", "No", "Unity Biomedicines, Inc.", "Origination", vendor, no, name, "D-1", hm, lm, "", "530 IT", "", amt, "Unity Biomedicines, Inc.", invoice])
        w.writerow(["Total - Unity Biomedicines, Inc."] + [""] * 15 + [round(sum(x[5] for x in lines), 2), "Unity Biomedicines, Inc.", invoice])


with tempfile.TemporaryDirectory() as d:
    print("The cost breakdown, as exported")
    p = os.path.join(d, "breakdown_INV1.csv")
    breakdown(p, "INV1", [(6100, "6100.01 - Consulting:6100 - Consultants", "Bay State IT Inc.", "Parking Aug 2026", "T&E", 163.54),
                          (6555, "6550.01 - Software:6555 - Software Costs", "Amazon Web Services Inc", "Notion Renewal 7/15/26-6/1/27", "1st Year", 13346.19)])
    b = S.read_passthrough_breakdown(p)
    ok(len(b) == 1 and b[0]["invoice"] == "INV1" and len(b[0]["lines"]) == 2 and b[0]["total"] == 13509.73 and b[0]["stated_total"] == 13509.73,
       "the title rows and the Total row are passed over; the items and the stated total are read")
    ok(b[0]["lines"][0]["acct_no"] == "6100" and b[0]["lines"][1]["header_memo"].startswith("Notion"), "each item keeps its Plurality account and memos")
    ok(S.read_passthrough_breakdowns([os.path.join(d, "*breakdown_INV*.xlsx")]) == {}, "a pattern that matched no file is passed over")
    bad = os.path.join(d, "x.csv"); open(bad, "w").write("a,b\n1,2\n")
    try:
        S.read_passthrough_breakdown(bad); ok(False, "a file that is not a breakdown stops")
    except SystemExit as stop:
        ok("not a pass-through cost breakdown" in str(stop), "a file that is not a breakdown stops, saying so")

    print("The month's pass-through bills")
    L = lambda vendor, doc, acct, amt, typ="Bill": {"vendor_or_name": vendor, "document_number": doc, "account_code": acct, "account_leaf": "", "department": "General G&A",
                                                     "amount": amt, "txn_type": typ, "date": "2026-08-31", "coupa_url": "", "internal_id": "1", "project": "", "program": ""}
    bp = {"Aug 2026": [L("Plurality Labs LLC", "INV1", "6201000", 100.0), L("Plurality Labs LLC", "INV1", "6816000", 50.0), L("Plurality Labs LLC", "INV1", "2000100", -150.0),
                       L("Plurality Labs LLC", "INV2", "6901000", 900.0), L("Plurality Group Labs TPC Inc", "INV3", "6410000", 20.0),
                       L("Plurality Labs Explorations Inc", "INV4", "6601000", 10000.0), L("Plurality Labs LLC", "JE9", "6201000", 5.0, "Journal")]}
    bills = S.passthrough_bills(bp, "Aug 2026")
    ok([b_["document"] for b_ in bills] == ["INV1", "INV3"] and bills[0]["amount"] == 150.0,
       "Plurality Labs LLC and TPC bills, expense lines only; the PG charges, other Plurality entities and journals are not pass-through")

# The review itself, on cases the code review found: its functions, taken from build_pages.py.
import ast, calendar  # noqa: E401
from collections import defaultdict
src = open(os.path.join(B, "src", "build_pages.py"), encoding="utf-8").read()
want = {"MONTHS", "T_AND_E", "service_end", "one_month", "_match_groups", "review_breakdown"}
ns = {"re": re, "calendar": calendar, "defaultdict": defaultdict, "money": lambda v, c=False: "$%s" % format(abs(v), ",.2f"),
      "ACC": {"6201000": "General Consulting", "6816000": "Office Non-Cap Software", "6603000": "Parking", "6704000": "Travel"}}
ns["acct_name"] = lambda c: ns["ACC"].get(c, "")
tree = ast.parse(src)
for node in tree.body:
    names = {node.name} if isinstance(node, ast.FunctionDef) else {t.id for t in getattr(node, "targets", []) if isinstance(t, ast.Name)}
    month_table = ast.unparse(node).startswith(("MONTHS[", "MONTHS.update("))
    if (names & want) or month_table:
        exec(compile(ast.Module([node], []), "build_pages", "exec"), ns)
se, rb = ns["service_end"], ns["review_breakdown"]
print("Reading a service period")
ok(se("Subscription - May 2026 - Apr 2027") == (2027, 4) and se("July 15, 2026 - June 30, 2027") == (2027, 6) and se("7/15/26-6/1/27") == (2027, 6)
   and se("11/1/2026 - 10/31/2027") == (2027, 10) and se("Aug 2026") is None and se("License - May 2026 - Apr 2027") == (2027, 4)
   and se("Software - Jan 2026 - Dec 2026") == (2026, 12), "a memo's service period is read in its common shapes, after a label word too")
ok(not ns["one_month"]("Subscription - May 2026 - Apr 2027") and ns["one_month"]("Help desk Aug 2026"), "a range is not a month's charge; a single month is")
BL = lambda acct, leaf, amt, dept="General G&A": {"account_code": acct, "account_leaf": leaf, "department": dept, "amount": amt, "project": "", "program": ""}
IT = lambda no, name, hm, amt: {"acct_no": no, "acct_name": name, "header_memo": hm, "memo": "", "amount": amt, "date": "", "vendor": "", "department": "", "document": ""}
print("Reading a breakdown against its bill")
bill = {"amount": 1000.0, "lines": [BL("6816000", "Office Non-Cap Software", 500.0), BL("6201000", "General Consulting", 500.0)]}
bd = {"total": 1000.0, "stated_total": 1000.0, "lines": [IT("6555", "Software Costs", "Notion renewal", 500.0), IT("6100", "Consultants", "Bay State IT - Parking", 500.0)]}
r = rb(bill, bd, 5000.0, 25000.0, "Sep 2026")
ok({i["header_memo"]: i["client_acct"] for i in r["items"]} == {"Notion renewal": "6816000", "Bay State IT - Parking": "6201000"} and r["ties"],
   "two activities of the same amount map by account, not by order")
bill = {"amount": 500.0, "lines": [BL("6201000", "General Consulting", 500.0)]}
r = rb(bill, {"total": 500.0, "stated_total": 500.0, "lines": [IT("6100", "Consultants", "Hotel parking", 500.0)]}, 5000.0, 25000.0, "Sep 2026")
ok(sum(l.get("debit") or 0 for l in r["reclass"]) == 500.0 and len(r["reclass"]) == 2, "an item that reads as two kinds of T&E is reclassed once")
bill = {"amount": 460.0, "lines": [BL("6201000", "General Consulting", 460.0)]}
r = rb(bill, {"total": 460.0, "stated_total": 460.0, "lines": [IT("6100", "Consultants", "Kyndryl", 500.0), IT("6100", "Consultants", "Parking refund", -40.0)]}, 5000.0, 25000.0, "Sep 2026")
ok(all((l.get("debit") or 0) >= 0 and (l.get("credit") or 0) >= 0 for l in r["reclass"]) and {(l["account"], l.get("credit")) for l in r["reclass"]} >= {("6603000", 40.0)},
   "a refund's reclass runs the other way, with no negative amounts")
bill = {"amount": 500.0, "lines": [BL("6201000", "General Consulting", 300.0), BL("6201000", "General Consulting", 200.0, "General R&D")]}
r = rb(bill, {"total": 500.0, "stated_total": 500.0, "lines": [IT("6100", "Consultants", "Kyndryl", 500.0)]}, 5000.0, 25000.0, "Sep 2026")
ok(r["ties"] and r["items"][0]["client_acct"] == "6201000", "an activity booked across departments still maps and ties")
r = rb(bill, {"total": 500.0, "stated_total": 500.0, "lines": [IT("6100", "Consultants", "Kyndryl", 400.0), IT("6100", "Consultants", "Parking", 100.0)]}, 5000.0, 25000.0, "Sep 2026")
ok({(l["department"], l.get("credit")) for l in r["reclass"] if l["account"] == "6201000"} == {("General G&A", 60.0), ("General R&D", 40.0)},
   "a reclass on an activity booked across departments moves in the shares it was booked")
r = rb({"amount": 500.0, "lines": [BL("6201000", "General Consulting", 500.0)]}, {"total": 500.0, "stated_total": 400.0, "lines": [IT("6100", "Consultants", "Kyndryl", 500.0)]},
       5000.0, 25000.0, "Sep 2026")
ok(not r["ties"] and "Total row" in r["why"], "a breakdown whose items do not add to its own Total row says so")

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
        p = os.path.join(d, "breakdown_INVtest.csv")
        items = [(6100, "6100 - Consultants", "Bay State IT Inc.", "Bay State IT - Parking Aug 2026", "BSIT T&E", 100.0),
                 (6100, "6100 - Consultants", "Kyndryl Inc", "Kyndryl Cloud Mgmt Aug 2026", "Monthly", round(cons["amount"] - 100.0, 2))]
        items += [(7000 + n, "%d - Other" % (7000 + n), "Vendor %d" % n, "Item %d" % n, "", l["amount"]) for n, l in enumerate(rest)]
        breakdown(p, bill["document"], items)
        out = os.path.join(d, "out")
        r = subprocess.run([sys.executable, "build_pages.py", "--only", "coding", "--coding-run", RUN, "--gl", *GL, "--parent-breakdown", p, "--out", out],
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
