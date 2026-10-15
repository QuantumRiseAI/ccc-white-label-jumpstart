"""The ledger tied to NetSuite's Income Statement by account, before a console is built
(SERIF-146). Synthetic files first; then, when the Aug 2026 exports and a build are on
disk, a console build on an Income Statement that does not tie.

    python3 tests/test_tie.py      (after `make build PERIOD=aug2026` for the build checks)
"""
import glob
import os
import re
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape

B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(B, "src"))
import serif_sources as S  # noqa: E402

FAILED = []


def ok(cond, label):
    print(("  PASS " if cond else "  FAIL ") + label)
    if not cond:
        FAILED.append(label)


def spreadsheetml(rows):
    out = ['<?xml version="1.0"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" '
           'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><Worksheet ss:Name="R"><Table>']
    for row in rows:
        out.append("<Row>" + "".join(f'<Cell><Data ss:Type="String">{escape(str(v))}</Data></Cell>' for v in row) + "</Row>")
    return "".join(out) + "</Table></Worksheet></Workbook>"


# An Income Statement by month: income shown positive, expense positive, headings blank.
IS_ROWS = [["Serif Biomedicines, Inc."], ["Income Statement"], ["Financial Row", "Jul 2026", "Aug 2026"], ["", "", ""],
           ["Ordinary Income/Expense", "", ""], ["Income", "", ""], ["4000000 - Revenue", "", ""],
           ["4001003 - Revenue - Cost Reimbursement", "0", "0"], ["Total - 4000000 - Revenue", "0", "0"], ["Total - Income", "0", "0"],
           ["Expense", "", ""], ["6400000 - Lab Expenses", "", ""], ["6410000 - Lab Supplies/Consumables", "100.50", "200.00"],
           ["Total - 6400000 - Lab Expenses", "100.50", "200.00"], ["Total - Expense", "100.50", "200.00"],
           ["Other Income and Expenses", "", ""], ["Other Income", "", ""], ["8111000 - Interest Income", "40.00", "25.00"],
           ["Total - Other Income", "40.00", "25.00"], ["Net Income", "-60.50", "-175.00"]]


def gl(aug_lab=200.0, extra=None, interest=True):
    line = lambda code, amt: {"account_code": code, "amount": amt, "account_leaf": ""}
    aug = [line("6410000", aug_lab), line("2000100", -aug_lab)] + ([line("8111000", -25.0)] if interest else []) + (extra or [])
    return {"Jul 2026": [line("6410000", 100.5), line("8111000", -40.0)], "Aug 2026": aug}


with tempfile.TemporaryDirectory() as d:
    isx = os.path.join(d, "netsuite_income_statement_by_month.xls")
    open(isx, "w").write(spreadsheetml(IS_ROWS))

    print("The tie, by account")
    t = S.income_statement_tie(gl(), isx, ["Aug 2026", "Jul 2026"])
    ok(t["passed"] and not t["failed"], "a ledger that matches the report ties, both months")
    ok(t["accounts"] == 3, "every P&L account on either side is counted, balance sheet lines are not")
    ok(t["totals"]["Aug 2026"] == {"ledger": 175.0, "report": 175.0}, "totals carry the ledger and the report, income turned")
    t = S.income_statement_tie(gl(aug_lab=199.99), isx, ["Aug 2026"])
    ok(not t["passed"] and [(f["code"], f["difference"]) for f in t["failed"]] == [("6410000", -0.01)], "a one-cent difference fails, on its account")
    t = S.income_statement_tie(gl(extra=[{"account_code": "6999999", "amount": 5.0, "account_leaf": "Misc"}]), isx, ["Aug 2026"])
    ok([(f["code"], f["ledger"], f["report"]) for f in t["failed"]] == [("6999999", 5.0, 0.0)], "an account only in the ledger fails")
    t = S.income_statement_tie(gl(interest=False), isx, ["Aug 2026"])
    ok([(f["code"], f["report"]) for f in t["failed"]] == [("8111000", -25.0)], "an account only in the report fails, income compared as a credit")
    t = S.income_statement_tie(gl(aug_lab=199.99), isx, ["Jul 2026"])
    ok(t["passed"], "only the months asked for are tied")
    lines = S.tie_lines(S.income_statement_tie(gl(aug_lab=199.99), isx, ["Aug 2026"]))
    ok(lines[0].startswith("Does NOT tie") and "6410000" in lines[1] and "-0.01" in lines[1], "the message names the account and the difference")

    print("The tie command")
    head = ["Account", "Type", "Date", "Document Number", "Name", "Debit", "Credit", "Balance", "Account: Name",
            "Accounting Period: Name", "Department: Name", "Program: Name", "ProjectID: Name", "ProjectID: Name",
            "Subsidiary: Name", "Description", "Memo"]
    row = lambda acct, per, dr, cr: [acct, "Journal", "2026-08-31T00:00:00.000", "J-1", "", dr, cr, "", "", per, "", "", "", "", "", "", ""]
    lab, ap, intr = ("6000000 - Operating Expenses:6410000 - Lab Supplies/Consumables", "2000000 - Accounts Payable:2000100 - Accounts Payable",
                     "8000000 - Other Income:8111000 - Interest Income")
    glx = os.path.join(d, "netsuite_gl.xls")
    open(glx, "w").write(spreadsheetml([["Custom General Ledger"], head,
        row(lab, "Jul 2026", "100.50", ""), row(intr, "Jul 2026", "", "40.00"), row(ap, "Jul 2026", "", "60.50"),
        row(lab, "Aug 2026", "200.00", ""), row(intr, "Aug 2026", "", "25.00"), row(ap, "Aug 2026", "", "175.00")]))
    run = lambda *a: subprocess.run([sys.executable, os.path.join(B, "src", "serif_sources.py"), "tie", "--period", "Aug 2026", "--gl", glx,
                                     "--income-statement", *a], capture_output=True, text=True)
    r = run(isx, "--prior")
    ok(r.returncode == 0 and "Aug 2026 and Jul 2026, 3 accounts, every account ties" in r.stdout, "exits 0 and says it ties")
    bad = os.path.join(d, "netsuite_income_statement_bad.xls")
    open(bad, "w").write(spreadsheetml([r_ if r_[0] != "6410000 - Lab Supplies/Consumables" else [r_[0], "100.50", "210.00"] for r_ in IS_ROWS]))
    r = run(bad)
    ok(r.returncode == 2 and "6410000" in r.stdout and "-10.00" in r.stdout, "exits 2 and names the account that does not tie")
    julx = os.path.join(d, "netsuite_income_statement_by_month_jul.xls")
    open(julx, "w").write(spreadsheetml([[c for c in r_[:2]] for r_ in IS_ROWS]))
    r = run(julx, isx)
    ok(r.returncode == 0 and "(netsuite_income_statement_by_month.xls)" in r.stdout,
       "given two reports, the one that holds the month is tied")
    r = run(julx)
    ok(r.returncode == 1 and "no column for Aug 2026" in r.stderr, "a report without the month stops, saying so")

# The console build, on the Aug exports, against an Income Statement missing an account.
I = os.path.join(B, "inputs", "aug2026")
RUN = os.path.join(B, "out", "aug2026", "gl-coding-review", "run.json")
DIST = os.path.join(B, "out", "dist", "gl-coding-review")
real_is = glob.glob(os.path.join(I, "netsuite_income_statement_by_month_*.xls"))
if not (real_is and os.path.exists(RUN) and os.path.isdir(DIST)):
    print("  SKIP the console build checks: run `make build PERIOD=aug2026` first")
else:
    print("The console build")
    for name in ("serif-gl-coding-review.html", "serif-pl-flux.html"):
        html = open(os.path.join(B, "consoles", name), encoding="utf-8").read()
        ok('data-tie="pass"' in html and html.index('data-tie="pass"') < html.index('id="p-', html.index('id="p-ov"') + 1),
           name + ": the tie leads the first page and passes")
    src = open(real_is[0], encoding="utf-8").read()
    cut = re.sub(r"<Row(?:(?!</Row>).)*?6410000 - Lab Supplies/Consumables(?:(?!</Row>).)*?</Row>", "", src, count=1, flags=re.S)
    with tempfile.TemporaryDirectory() as d:
        isx = os.path.join(d, os.path.basename(real_is[0]))
        open(isx, "w", encoding="utf-8").write(cut)
        args = [sys.executable, "build_pages.py", "--only", "coding", "--coding-run", RUN, "--gl",
                *glob.glob(os.path.join(I, "netsuite_gl_detail_*.xls*")), "--income-statement", isx, "--out", d]
        r = subprocess.run(args, cwd=DIST, capture_output=True, text=True)
        ok(cut != src and r.returncode != 0 and "6410000" in r.stderr and "no console was built" in r.stderr,
           "a failed tie stops the build and names the account")
        ok(not glob.glob(os.path.join(d, "*.html")), "no console is written")
        r = subprocess.run(args + ["--allow-tie-differences"], cwd=DIST, capture_output=True, text=True)
        out = glob.glob(os.path.join(d, "*.html"))
        html = open(out[0], encoding="utf-8").read() if out else ""
        ok(r.returncode == 0 and 'data-tie="fail"' in html and "6410000" in html[html.index('data-tie="fail"'):][:4000],
           "with --allow-tie-differences it builds, the differences at the top")

print("all passed" if not FAILED else "%d failed" % len(FAILED))
sys.exit(1 if FAILED else 0)
