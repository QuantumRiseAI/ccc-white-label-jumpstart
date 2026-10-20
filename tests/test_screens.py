"""The prepaid and capital screens at Serif's thresholds of 12 Oct 2026 (SERIF-142), and
where a capital purchase goes, Capital in Process or its fixed asset account, and why
(SERIF-147). Synthetic ledger lines; no exports needed.

    python3 tests/test_screens.py
"""
import os
import sys

B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(B, "src"))
import serif_uc2_flux as F  # noqa: E402
import serif_views as V  # noqa: E402

FAILED = []


def ok(cond, label):
    print(("  PASS " if cond else "  FAIL ") + label)
    if not cond:
        FAILED.append(label)


def bill(vendor, account, amount, text, doc="B1", date="2026-08-12", dept="General R&D", memo=""):
    return {"period": "Aug 2026", "date": date, "txn_type": "Bill", "document_number": doc, "vendor_or_name": vendor,
            "account_code": account, "department": dept, "amount": amount, "description": text, "memo": memo}


LEAVES = {"6891000": "Package Insurance", "6435000": "Lab Equipment Repairs & Maintenance", "6415000": "Lab Non-Capital Equipment",
          "6815000": "Office Non-Cap Equipment/Furniture", "6816000": "Office Non-Cap Software"}

print("thresholds")
ok(F.PREPAID_THRESHOLD == 25_000 and F.CAPITALIZATION_THRESHOLD == 5_000 and V.CAPITALIZATION == F.CAPITALIZATION_THRESHOLD
   and V.PREPAID == F.PREPAID_THRESHOLD,
   "prepaid $25,000 and PP&E $5,000, the views agreeing with the engine")
ok("$25,000" in F.POLICY_PREPAID and "$5,000" in F.POLICY_ASSET and "no capitalization threshold" not in F.POLICY_ASSET,
   "the policy citations carry the new figures")
ok(F.RULESET_VERSION != "2026.09-uc2-flux-account-level", "the ruleset version moved")

print("prepaid: listed from $2,500, reviewed from $25,000")
pre = lambda amt: F.prepaid_findings([bill("Acme Insurance", "6891000", amt, "Annual policy renewal")], {}, LEAVES, "Aug 2026", [0])
ok(not pre(2_499.99) and len(pre(2_500)) == 1, "a term charge is listed from the $2,500 reporting floor, as capital is")
split = F.prepaid_findings([bill("Acme Insurance", "6891000", 15_000, "Annual policy renewal", doc="B1"),
                            bill("Acme Insurance", "6891000", 12_000, "Annual policy renewal", doc="B2")], {}, LEAVES, "Aug 2026", [0])
ok(len(split) == 1 and split[0]["amount_at_risk"] == 27_000, "related charges are aggregated into one finding")
small, big = pre(24_999.99)[0], pre(25_000)[0]
ok("under the $25,000 prepaid threshold" in V.explain(small, {}, "Aug 2026")["why"] and "under the $25,000" not in V.explain(big, {}, "Aug 2026")["why"],
   "a prepaid under $25,000 says it stays expense; one at $25,000 does not")
ok(not V.entries([small], "Aug 2026") and len(V.entries([big], "Aug 2026")) == 1 and len(V.entries(split, "Aug 2026")) == 1,
   "the P&L Flux proposes a prepaid entry only at or over $25,000, related charges together")

print("capital: where it goes")
p = F.capex_placement("6815000", "Office Desk Expansion (Phase 2)", "2026-08-25")
ok(p["to"] == "1505000" and p["kind"] == "buildout" and "until employees begin using the space" in p["why"]
   and "Ask the date employees began" in p["ask"], "build-out work goes to 1505000 Capital in Process, and asks when the space is in use")
ok(F.capex_placement("6415000", "T cell expansion kit", "2026-08-25")["kind"] == "in_service", "a cell expansion kit is not build-out work")
p = F.capex_placement("6415000", "Deposit on centrifuge, 50% down payment", "2026-08-25")
ok(p["to"] == "1505000" and p["kind"] == "not_in_service" and p["asset"] == "1510000 Lab Equipment - New"
   and "1510000 Lab Equipment - New" in p["ask"], "an asset not yet in service goes to Capital in Process, then to its fixed asset account")
p = F.capex_placement("6415000", "Benchtop centrifuge", "2026-08-25")
ok(p["to"] == "1510000" and p["kind"] == "in_service" and "2026-08-25" in p["why"] and "no in-service date" in p["ask"]
   and "1505000 Capital in Process instead" in p["ask"], "an asset in service goes to its fixed asset account, and the reviewer is asked the date")
p = F.capex_placement("6415000", "Benchtop centrifuge, installed 8/20/2026", "2026-08-25")
ok(p["to"] == "1510000" and p["in_service"] == "8/20/2026" and not p["ask"], "a date the line states is used, and nothing is asked")
p = F.capex_placement("6815000", "Lenovo ThinkStation P3 Tower", "2026-08-25")
ok(p["to"] == "1530000" and p["kind"] == "in_service", "a computer on office equipment goes to 1530000 Computers & Software")
p = F.capex_placement("6815000", "Conference room chairs", "2026-08-25")
ok(p["to"] == "1505000" and p["kind"] == "no_account" and "Controller" in p["ask"] and "no fixed asset account for office furniture" in p["why"],
   "office furniture in service: the chart has no account for it, so the entry holds it in Capital in Process and asks")
ok("2026-08-25" in p.get("basis", ""), "office furniture's placement keeps its in-service basis, for the P&L Flux, which has no Placed in service field")
chart = open(os.path.join(B, "projects", "shared", "serif-accounts-and-departments.md"), encoding="utf-8").read()
targets = {F.CAPITAL_IN_PROCESS} | {a for a in F.CAPEX_REVIEW.values() if a} | {("1530000", "Computers & Software")}
ok(all("%s - %s" % t in chart for t in targets), "every target is an account in Serif's chart, by its name")

print("capital findings")
fs = F.capex_findings([bill("Red Thread Spaces LLC", "6815000", 38_590.70, "Office Desk Expansion (Phase 2)", doc="18171"),
                       bill("Repligen Corporation", "6435000", 2_823.39, "MIDIKROS 20CM 500K MPES", doc="90424778")],
                      LEAVES, "Aug 2026", [0])
by = {f["title"].split(":")[0]: f for f in fs}
rt, rp = by.get("Red Thread Spaces LLC") or {}, by.get("Repligen Corporation") or {}
ok(len(fs) == 2 and (rt.get("correction") or {}).get("placement", {}).get("kind") == "buildout"
   and rt["correction"]["entry"].startswith("Dr 1505000 Capital in Process") and "Build-out work stays in" in rt["recommendation"],
   "the finding carries where it goes and why, in its entry and its recommendation")
ok(rp["correction"]["entry"].startswith("Dr 1510000 Lab Equipment - New"), "listed from the reporting floor; an asset in service is debited to its account")
x = V.explain(rp, {}, "Aug 2026")
ok("under the $5,000 capitalization threshold" in x["why"] and "no in-service date" in x["do"], "under $5,000 it says so, and asks the in-service date")
x = V.explain(rt, {}, "Aug 2026")
ok("under the $5,000" not in x["why"] and "build-out work" in x["why"] and x["do"].startswith("Read the bill."), "over $5,000, the build-out reason and the question")
cap = lambda amt: F.capex_findings([bill("Fisher Scientific", "6415000", amt / 2, "Benchtop centrifuge", doc="9001"),
                                    bill("Fisher Scientific", "6415000", amt / 2, "Centrifuge rotor", doc="9001")], LEAVES, "Aug 2026", [0])
ok(not V.entries(cap(4_999.98), "Aug 2026") and len(V.entries(cap(5_000), "Aug 2026")) == 1
   and not V.entries([rp], "Aug 2026") and len(V.entries([rt], "Aug 2026")) == 1,
   "the P&L Flux proposes a capital entry only at or over $5,000, the bill's lines together")
ok(V.capitalize_memo("Red Thread", rt["correction"]["placement"]).endswith("until it is placed in service")
   and V.capitalize_memo("Repligen", rp["correction"]["placement"]) == "Capitalize Repligen purchase as a fixed asset",
   "the flux entry's memo says Capital in Process or fixed asset; an asset in service keeps the memo it had")

print("a bill a Journal Entry in the month already moves")
def jline(account, amount, text, dept="General R&D"):
    return {"period": "Aug 2026", "date": "2026-08-31", "txn_type": "Journal", "document_number": "JE1", "vendor_or_name": "",
            "account_code": account, "department": dept, "amount": amount, "description": text, "memo": "Capitalize Freezers Posted to Expense"}
frz = bill("VWR International LLC", "6415000", 17_729.41, "UPRIGHT FREEZER 729L", doc="8822578887")
ok(len(F.capex_findings([frz], LEAVES, "Aug 2026", [0])) == 1, "a freezer on Lab Non-Capital Equipment is flagged")
ok(not F.capex_findings([frz, jline("6415000", -17_729.41, "Capitalize freezer VWR International LLC bill 8822578887 moved from 6415000")], LEAVES, "Aug 2026", [0]),
   "a freezer a month-end Journal Entry already capitalizes, naming the bill, is not flagged again")
ok(len(F.capex_findings([frz, jline("6415000", -17_729.41, "Capitalize freezer bill 88225788870")], LEAVES, "Aug 2026", [0])) == 1
   and len(F.capex_findings([frz, jline("6415000", -10_000, "Capitalize freezer bill 8822578887")], LEAVES, "Aug 2026", [0])) == 1
   and len(F.capex_findings([frz, jline("6410000", -17_729.41, "Capitalize freezer bill 8822578887")], LEAVES, "Aug 2026", [0])) == 1,
   "a journal naming another document, moving another amount or on another account does not clear the bill")
two = [bill("Fisher Scientific", "6415000", 6_000, "Centrifuge", doc="9001"), bill("Fisher Scientific", "6415000", 4_000, "Rotor", doc="9001")]
ok(not F.capex_findings(two + [jline("6415000", -10_000, "Reclass bill 9001 to CIP")], LEAVES, "Aug 2026", [0]),
   "a journal moving a document's whole total on the account clears every line of it")
ok(len(F.capex_findings([frz, jline("6415000", -17_729.41, "Move bill 8822578887 to Production"), jline("6415000", 17_729.41, "Move bill 8822578887 to Production", dept="Production")], LEAVES, "Aug 2026", [0])) == 1
   and len(F.capex_findings([frz, jline("6415000", -17_729.41, "Capitalize bill 8822578887"), jline("6415000", 17_729.41, "Reverse capitalization of bill 8822578887")], LEAVES, "Aug 2026", [0])) == 1,
   "a move between departments on the account, or a capitalization reversed in the month, leaves the bill flagged")
eq = [bill("Fisher Scientific", "6415000", 6_000, "Centrifuge", doc="9002"), bill("Fisher Scientific", "6415000", 6_000, "Centrifuge", doc="9002")]
ok(len(F.capex_findings(eq + [jline("6415000", -6_000, "Reclass part of bill 9002")], LEAVES, "Aug 2026", [0])) == 1
   and len(F.capex_findings([frz, jline("6415000", -17_729.41, "Capitalize bill 8822578887-2")], LEAVES, "Aug 2026", [0])) == 1,
   "one journal line clears one bill line, not two; a document number inside a longer one does not match")
sub = bill("Acme Insurance", "6891000", 30_000, "Annual policy renewal", doc="INS-77")
ok(len(F.prepaid_findings([sub], {}, LEAVES, "Aug 2026", [0])) == 1
   and not F.prepaid_findings([sub, jline("6891000", -30_000, "To record prepaid insurance INS-77")], {}, LEAVES, "Aug 2026", [0]),
   "the prepaid screen skips a bill a journal already moves to prepaid")

# a capital bill with lines in two departments: the entry takes each department's lines off it, and
# the finding names each line, so the console makes a card per department and no other
split2 = F.capex_findings([bill("Flagship Labs LLC", "6815000", 2_000, "Non-Capital Equipment", doc="INV1", dept="General G&A"),
                           bill("Flagship Labs LLC", "6815000", 3_280.67, "Non-Capital Equipment", doc="INV1", dept="Finance")], LEAVES, "Aug 2026", [0])
e2 = V.entries(split2, "Aug 2026")
rev = sorted((l["department"], l["credit"]) for l in (e2[0]["lines"] if e2 else []) if l.get("reverses_line"))
ok(len(e2) == 1 and rev == [("Finance", 3280.67), ("General G&A", 2000.0)]
   and abs(sum(l["debit"] for l in e2[0]["lines"]) - sum(l["credit"] for l in e2[0]["lines"])) < 0.01,
   "a capital bill split across departments is taken off each department, and the entry balances")
ok(sorted((m["department"], m["amount"]) for m in V._doc_match(split2[0])) == [("Finance", 3280.67), ("General G&A", 2000.0)],
   "the finding names each of its lines, with its department and amount, for the console's cards")

if FAILED:
    print("%d failed" % len(FAILED))
    sys.exit(1)
print("all passed")
