"""The P&L Flux does not apply a GL Coding Review correction twice: once it is imported from the
NetSuite CSV and in the GL the flux reads, it is in the ledger already. Built on Sep 2026: a
decision record approving three coding cards, and a copy of the month's GL with two of them
posted as NetSuite would import them, under a different reference ID (a later build can
renumber the cards). Needs `make build PERIOD=sep2026` and inputs/sep2026.

    python3 tests/test_imported.py
"""
import csv
import glob
import json
import os
import subprocess
import sys
import tempfile

B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
VERSION = open(os.path.join(B, "src", "build_pages.py"), encoding="utf-8").read().split('VERSION = "')[1].split('"')[0]
fails = 0


def ok(cond, msg):
    global fails
    print(("  PASS " if cond else "  FAIL ") + msg)
    fails += not cond


GLRUN, FLRUN = (os.path.join(B, "out", "sep2026", k, "run.json") for k in ("gl-coding-review", "pl-flux"))
CON = os.path.join(B, "out", "sep2026", "gl-coding-review", "serif-gl-coding-review-sep2026-v%s.html" % VERSION)
I = os.path.join(B, "inputs", "sep2026")
SEP = glob.glob(os.path.join(I, "netsuite_gl_detail_sep2026.csv"))
if not (os.path.exists(GLRUN) and os.path.exists(FLRUN) and os.path.exists(CON) and SEP):
    print("  SKIP imported corrections (needs out/sep2026 from make build, and inputs/sep2026)")
    sys.exit(0)
s = open(CON, encoding="utf-8").read()
D = json.JSONDecoder().raw_decode(s[s.find("DATA={") + 5:])[0]
def moving(i):
    """An entry that moves something: some account and department nets to other than zero."""
    net = {}
    for l in D["je"][i]["lines"]:
        k = (l["account"], l["department"])
        net[k] = net.get(k, 0) + (l.get("debit") or 0) - (l.get("credit") or 0)
    return any(abs(v) >= 0.01 for v in net.values())
picks = [next(i for i in D["je"] if i.startswith("VC-") and moving(i))] + [i for i in D["je"] if i.startswith("D-") and moving(i)][:2]
tmp = tempfile.mkdtemp(prefix="serif-imported-")
rec = {"kind": "serif-decision-record", "console_kind": "coding", "format": 3, "period": "Sep 2026",
       "run_id": json.load(open(GLRUN))["manifest"]["run_id"], "dec": {i: {"v": "approve"} for i in picks},
       "notes": {picks[0]: "Imported test note"}, "je": {}, "jh": {}}
json.dump(rec, open(os.path.join(tmp, "rec.json"), "w"))
# the GL with the first two posted, as the import writes them: the Memo with the note before
# the month, the Line Memo, and a reference ID other than the card's
with open(SEP[0], newline="", encoding="utf-8") as f:
    rows = list(csv.reader(f))
head = rows[0]
col = {k: head.index(k) for k in ("account_number", "type", "date", "document_number", "debit", "credit", "period", "department", "memo", "description")}
for n, i in enumerate(picks[:2]):
    j = D["je"][i]
    memo = "CODING-9%d | %s" % (n, j["memo"].split(" | ", 1)[1])
    if i in rec["notes"]:
        memo = memo.replace(" | Sep'26", " | %s | Sep'26" % rec["notes"][i], 1)
    for l in j["lines"]:
        r = [""] * len(head)
        r[col["account_number"]], r[col["type"]], r[col["date"]], r[col["document_number"]] = l["account"], "Journal", "2026-09-30", "JE90000%d" % n
        r[col["debit"]], r[col["credit"]] = (str(l["debit"]) if l.get("debit") else ""), (str(l["credit"]) if l.get("credit") else "")
        r[col["period"]], r[col["department"]], r[col["memo"]], r[col["description"]] = "Sep 2026", l["department"], memo, memo
        rows.append(r)
gl = os.path.join(tmp, "netsuite_gl_detail_sep2026.csv")
with open(gl, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows)
earlier = [p for p in glob.glob(os.path.join(I, "netsuite_gl_detail_*")) if not p.endswith("sep2026.csv")]
IS = glob.glob(os.path.join(I, "netsuite_income_statement_by_*"))
r = subprocess.run(["python3", "build_pages.py", "--only", "flux", "--flux-run", FLRUN, "--gl", *earlier, gl, "--income-statement", *IS,
                    "--coding-run", GLRUN, "--coding-record", os.path.join(tmp, "rec.json"), "--out", os.path.join(tmp, "out"),
                    "--allow-tie-differences"],   # the GL now holds the imports; this Income Statement predates them
                   cwd=os.path.join(B, "out", "dist", "pl-flux"), capture_output=True, text=True)
out = r.stdout + r.stderr
ok(r.returncode == 0, "the flux builds with the coding record and a GL holding two imported corrections")
ok("2 corrections already in this GL, imported from the NetSuite CSV, not applied again" in out,
   "the two imported corrections are found in the GL, under another reference ID, and not applied again")
ok(all(D["ref"].get(i, i) in out for i in picks[:2]) and D["ref"].get(picks[2], picks[2]) not in out.split("not applied again")[-1][:400],
   "the run log names the two imported, and the third, not imported, is applied")
sys.exit(1 if fails else 0)
