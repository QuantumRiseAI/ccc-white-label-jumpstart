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
ok(F.PREPAID_THRESHOLD == 25_000 and F.CAPITALIZATION_THRESHOLD == 5_000 and V.CAPITALIZATION == F.CAPITALIZATION_THRESHOLD,
   "prepaid $25,000 and PP&E $5,000, the views agreeing with the engine")
ok("$25,000" in F.POLICY_PREPAID and "$5,000" in F.POLICY_ASSET and "no capitalization threshold" not in F.POLICY_ASSET,
   "the policy citations carry the new figures")
ok(F.RULESET_VERSION != "2026.09-uc2-flux-account-level", "the ruleset version moved")

print("prepaid at $25,000")
pre = lambda amt: F.prepaid_findings([bill("Acme Insurance", "6891000", amt, "Annual policy renewal")], {}, LEAVES, "Aug 2026", [0])
ok(not pre(24_999.99), "a term charge under $25,000 is not flagged")
ok(len(pre(25_000)) == 1, "a term charge of $25,000 is flagged")
split = F.prepaid_findings([bill("Acme Insurance", "6891000", 15_000, "Annual policy renewal", doc="B1"),
                            bill("Acme Insurance", "6891000", 12_000, "Annual policy renewal", doc="B2")], {}, LEAVES, "Aug 2026", [0])
ok(len(split) == 1 and split[0]["amount_at_risk"] == 27_000, "related charges are aggregated before the test")
ok(not F.prepaid_findings([bill("Nova", "6435000", 16_746, "Osmotech Pro Service Contract")], {}, LEAVES, "Aug 2026", [0]),
   "the Aug 2026 Osmotech service contract ($16,746) is under the threshold")

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
ok(p["to"] == "1505000" and p["kind"] == "no_account" and "Controller" in p["ask"] and "chart has none" in p["why"],
   "office furniture in service: the chart has no account for it, so the entry holds it in Capital in Process and asks")
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
ok(V.capitalize_memo("Red Thread", rt["correction"]["placement"]).endswith("until it is placed in service")
   and V.capitalize_memo("Repligen", rp["correction"]["placement"]) == "Capitalize Repligen purchase as a fixed asset",
   "the flux entry's memo says Capital in Process or fixed asset; an asset in service keeps the memo it had")

if FAILED:
    print("%d failed" % len(FAILED))
    sys.exit(1)
print("all passed")
