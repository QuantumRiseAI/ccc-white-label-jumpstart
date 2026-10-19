"""The runs and consoles built by `make build`, read for what a reviewer could misread: a check
listed as run when it could not, and an item whose id depends on the order a run lists it in.

    python3 tests/test_runs.py
"""
import glob
import json
import os
import re
import sys

OUT = os.path.join(os.path.dirname(__file__), "..", "out")
fails = 0


def ok(cond, msg):
    global fails
    print(("  PASS " if cond else "  FAIL ") + msg)
    fails += not cond


def data(path):
    s = open(path, encoding="utf-8").read()
    return json.JSONDecoder().raw_decode(s[s.find("DATA={") + 5:])[0]


runs = sorted(glob.glob(os.path.join(OUT, "*", "pl-flux", "run.json")))
if not runs:
    print("  SKIP no P&L Flux run in out/: run `make build` first")
for path in runs:
    month = path.split(os.sep)[-3]
    r = json.load(open(path, encoding="utf-8"))
    m = r["manifest"]
    every = [x for g in r["report"]["groups"] for x in g["rules"]]
    ran, off = m.get("rules_run") or [], {x["rule_id"]: x for x in m.get("rules_not_run") or []}
    ok(sorted(ran + list(off)) == sorted(every) and not set(ran) & set(off),
       "pl %s: every check is listed once, as run or not run, with a reason (%d run, %d not)" % (month, len(ran), len(off)))
    has = {i.get("role") for i in r["views"]["inputs"]} | {x for i in m["inputs"] for x in i.get("roles") or []}
    ok(("F5.MODEL_TIE" in off) == ("forecast" not in has), "pl %s: Forecast vs. Actual runs only with the month's forecast cut" % month)
    gone = set((m.get("coupa_coverage") or {}).get("columns_absent") or [])
    ok(("F3.ACCRUAL_RECEIPT" in off) == (not m["coupa_coverage"].get("supplied") or bool(gone & {"Received", "Supplier"})),
       "pl %s: received-not-invoiced runs only with Coupa's Received and Supplier columns" % month)

for path in sorted(glob.glob(os.path.join(OUT, "*", "gl-coding-review", "run.json"))):
    month = path.split(os.sep)[-3]
    m = json.load(open(path, encoding="utf-8"))["manifest"]
    gone, off = set((m.get("coupa_coverage") or {}).get("columns_absent") or []), {x["rule_id"] for x in m.get("rules_not_run") or []}
    ok(("T4.OPEN_COMMITMENTS" in off) == ("Received" in gone or not m["coupa_coverage"].get("supplied"))
       and ("T4.OFF_PO_SPEND" in off) == ("Supplier" in gone or not m["coupa_coverage"].get("supplied")),
       "gl %s: Spend with no PO and Open PO commitments run only with Coupa's Supplier and Received columns" % month)

# An id is what the item is, so the same item keeps its decision in every run: no card's id is a
# numbered repeat of another's (ADJ-xxxxxxxx-2), which would follow the order a run lists them in.
for path in sorted(glob.glob(os.path.join(OUT, "*", "*", "serif-*-v*.html"))):
    if "-v" + open(os.path.join(os.path.dirname(__file__), "..", "src", "build_pages.py"), encoding="utf-8").read().split('VERSION = "')[1].split('"')[0] + ".html" not in path:
        continue
    D = data(path)
    rep = sorted(k for k in D.get("je") or {} if re.match(r"^(ADJ|C|P)-[0-9a-f]{8}-\d+$", k))
    ok(not rep, "%s: no adjustment, CapEx or Prepaid id depends on its order%s" % (os.path.basename(path), (" (" + ", ".join(rep) + ")") if rep else ""))

sys.exit(1 if fails else 0)
