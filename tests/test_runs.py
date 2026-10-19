"""The runs and consoles built by `make build`, read for what a reviewer could misread: a check
listed as run when it could not, and an item whose id depends on the order a run lists it in
(a numbered repeat, D-xxxxxxxx-2, which a later run could give to another item).

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
    gone_ = {x for x, v in off.items() if v.get("status") == "not_run"}
    ok(sorted(ran + list(gone_)) == sorted(every) and not set(ran) & gone_ and all(v.get("reason") for v in off.values()),
       "pl %s: every check is listed once, as run or not run, with a reason (%d run, %d not)" % (month, len(ran), len(gone_)))
    has = {i.get("role") for i in r["views"]["inputs"]} | {x for i in m["inputs"] for x in i.get("roles") or []}
    ok(("F5.MODEL_TIE" not in off) <= ("forecast" in has), "pl %s: Forecast vs. Actual is listed as run only with a forecast cut" % month)
    gone = set((m.get("coupa_coverage") or {}).get("columns_absent") or [])
    f3 = off.get("F3.ACCRUAL_RECEIPT") or {}
    ok((f3.get("status") == "not_run") == (not m["coupa_coverage"].get("supplied") or "Received" in gone or not m["coupa_coverage"].get("lines")),
       "pl %s: received-not-invoiced runs only with Coupa's Received column and lines for the month" % month)
    ok(not (gone & {"Supplier", "Approved Invoiced"}) or "Received" in gone or not m["coupa_coverage"].get("lines") or f3.get("status") == "degraded",
       "pl %s: received-not-invoiced without Supplier or Approved Invoiced is listed as run degraded" % month)
    found = {f["rule_id"] for f in r["findings"]}
    ok(not any(x in found for x, v in off.items() if v.get("status") == "not_run"), "pl %s: no check listed as not run has findings" % month)

for path in sorted(glob.glob(os.path.join(OUT, "*", "gl-coding-review", "run.json"))):
    month = path.split(os.sep)[-3]
    m = json.load(open(path, encoding="utf-8"))["manifest"]
    gone = set((m.get("coupa_coverage") or {}).get("columns_absent") or [])
    nr = {x["rule_id"]: x.get("status") for x in m.get("rules_not_run") or []}
    sup = m["coupa_coverage"].get("supplied")
    ok((nr.get("T4.OFF_PO_SPEND") == "not_run") == ("Supplier" in gone or not sup)
       and (nr.get("T4.OPEN_COMMITMENTS") == "not_run") == ("Order Status (Header)" in gone or not sup),
       "gl %s: Spend with no PO runs only with Coupa's Supplier, Open PO commitments only with its Order Status" % month)

# An id is what the item is, so the same item keeps its decision in every run: no card's id is a
# numbered repeat of another's (ADJ-xxxxxxxx-2), which would follow the order a run lists them in.
for path in sorted(glob.glob(os.path.join(OUT, "*", "*", "serif-*-v*.html"))):
    if "-v" + open(os.path.join(os.path.dirname(__file__), "..", "src", "build_pages.py"), encoding="utf-8").read().split('VERSION = "')[1].split('"')[0] + ".html" not in path:
        continue
    D = data(path)
    rep = sorted(k for k in set(D.get("je") or {}) | set(D.get("ref") or {}) if re.match(r"^[A-Z]+-[0-9a-f]{8}-\d+$", k))
    ok(not rep, "%s: no item's id depends on its order%s" % (os.path.basename(path), (" (" + ", ".join(rep[:8]) + ")") if rep else ""))

sys.exit(1 if fails else 0)
