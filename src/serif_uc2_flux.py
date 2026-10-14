#!/usr/bin/env python3
"""Serif UC2, P&L Flux, deterministic core.

    python3 serif_uc2_flux.py --period "Sep 2026" --gl <NetSuite GL export.xls> [...]
                              [--coupa <Coupa PO export.csv>]
                              [--forecast <rolling forecast.xlsx>]
                              [--plan <rolling forecast.xlsx> --plan-vintage 2026-06]
                              [--pending <dir>] --out out

Every input is a system export as the system writes it, read by serif_sources.py.
The period's activity, the prior month, the same month last year and the six
months of history are all taken from the NetSuite exports in memory.

Stdlib only. No network. Python 3.9+.

WHAT THIS DOES AND DOES NOT DO
------------------------------
It computes variance arithmetic and identifies accrual candidates from evidence. That is
all. It writes no commentary: explaining a variance is a language model's job, and the
split is deliberate, an LLM that computes a variance produces a number that will not
reproduce next month.

Every finding is a proposal for an accountant, not a correction. Thresholds come from
Serif's own DRAFT policies and each finding carries that fact.

TWO POPULATIONS THAT MUST NOT BE CONFLATED
------------------------------------------
  received-not-invoiced   goods received, not yet billed. Expense belongs in this period.
                          THIS is the accrual population.
  open commitment         ordered, not yet received. Nothing has arrived, so nothing is
                          accruable. Reported as a disclosure only.

Mixing them overstates the period by roughly an order of magnitude.

The output artifact matches the UC1 shape; `serif_views.py` and `build_pages.py` turn it into the console.
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
from collections import defaultdict

import serif_sources as sources

ENGINE_VERSION = "0.8.0"
RULESET_VERSION = "2026.10-uc2-flux-serif-thresholds"
ENTITY = "FL87 Serif Biomedicines, Inc."

# THE TWO LAYERS
# --------------
# Review runs accounting first, then FP&A, because the questions are different and
# the second is not worth asking until the first is settled.
#
#   accounting  Does the ledger agree with itself and with the other systems of
#               record? Every finding here resolves to an entry booked or not.
#   fpa         Given a ledger the accountant has signed off, how does the period
#               compare to what was planned?
#
# A variance against budget computed on top of miscoded actuals measures the
# miscoding, so the order is load-bearing rather than presentational.
LAYER_ACCOUNTING = "accounting"
LAYER_FPA = "fpa"

# Serif policy thresholds. Every one is DRAFT and unapproved; findings say so.
PRE_CLOSE_ADJUSTMENT = 10_000.0   # Global Finance Threshold Policy
POST_CLOSE_QUARTERLY = 100_000.0  # Global Finance Threshold Policy
ACCRUAL_THRESHOLD = 5_000.0       # Global Accrued Expense Accounting Policy

# The engine emits every variance at or above this floor; the console then decides
# which of them belong in the working queue. The floor is deliberately below the
# policy threshold so the reviewer can lower the commentary threshold without
# rerunning the engine, and so the population sitting just under the threshold can
# be totalled instead of being invisible.
REPORTING_FLOOR = 2_500.0

# Serif's prepaid and PP&E thresholds, from Mike's write-up of 12 Oct 2026. They replace
# the $10,000 the draft prepaid policy was read as, and the draft asset policy's none.
PREPAID_THRESHOLD = 25_000.0      # aggregated per good or service
CAPITALIZATION_THRESHOLD = 5_000.0

POLICY_PREPAID = ("Global Prepaid Expense Policy (DRAFT, unapproved) "
                  ": $25,000 (Serif, 12 Oct 2026), related charges aggregated before testing")
POLICY_ASSET = ("Global Tangible & Intangible Asset Policy (DRAFT, unapproved) "
                ": $5,000 capitalization threshold (Serif, 12 Oct 2026); category and useful life decide")
POLICY_DATA_ENTRY = ("Global Data Entry Policy (DRAFT, unapproved) "
                     ": every entry names its counterparty")
POLICY_THRESHOLD = ("Global Finance Threshold Policy (DRAFT, unapproved) "
                    ": $10,000 pre-close adjustment threshold")
POLICY_ACCRUAL = ("Global Accrued Expense Accounting Policy (DRAFT, unapproved) "
                  ": $5,000 per vendor, per good or service, incurred but not invoiced")

PL_PREFIXES = ("6", "7", "8")
UNALLOCATED = "Non-Specific"

# Credit the matching accrual account under 2200000.
ACCRUAL_ACCOUNTS = [
    (("6410000", "6415000", "6416000", "6420000", "6425000", "6430000", "6435000",
      "6501000", "6501100", "6502000", "6502500", "6504000", "6508000", "6509000"),
     "2206000", "Accrued Lab Supplies and External Research"),
    (("6101000", "6102000", "6102500", "6103000", "6104000", "6104500", "6105000"),
     "2201000", "Accrued Payroll Benefits and Bonus"),
    (("6201000", "6203000", "6203500", "6204000", "6205000", "6206000", "6210000"),
     "2202000", "Accrued Consulting"),
    (("6601000", "6603000", "6604000", "6605000", "6606000", "6607000", "6608000", "6609000"),
     "2203000", "Accrued Facility Costs"),
    (("6311000", "6312000", "6321000", "6322000", "6323000", "6340000"),
     "2204000", "Accrued Legal Fees"),
    (("6901000", "6901100", "6901200"), "2206500", "Accrued FSP Charges"),
]


# Accounts whose charges are for a term rather than a moment, and the prepaid
# account each would sit in. Rent, insurance, software and licenses are paid ahead
# of the months they cover.
PREPAID_ACCOUNTS = {
    "6601000": ("1305000", "Prepaid Rent"),
    "6891000": ("1310000", "Prepaid Insurance"),
    "6416000": ("1320000", "Prepaid Software"),
    "6816000": ("1320000", "Prepaid Software"),
    "6890000": ("1315000", "Prepaid Other"),
    "6323000": ("1315000", "Prepaid Other"),
    "6435000": ("1315000", "Prepaid Other"),
}
# Wording on a bill that says it covers a term: a service contract, a subscription,
# a renewal. A date range counts separately, and only when it runs past a month.
TERM_WORDS = re.compile(
    r"service contract|subscription|renewal|annual|license|maintenance agreement|"
    r"support plan", re.IGNORECASE)
DATE_RANGE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})\s*-\s*(\d{1,2})/(\d{1,2})/(\d{2,4})")
TERM_DAYS = 45


def names_a_term(text):
    """True if the text names a service term: the words, or a date range longer
    than a month and a half. A two-week delivery window is not a term."""
    text = text or ""
    if TERM_WORDS.search(text):
        return True
    for m in DATE_RANGE.finditer(text):
        try:
            y1, y2 = int(m.group(3)), int(m.group(6))
            y1 += 2000 if y1 < 100 else 0
            y2 += 2000 if y2 < 100 else 0
            start = dt.date(y1, int(m.group(1)), int(m.group(2)))
            end = dt.date(y2, int(m.group(4)), int(m.group(5)))
        except ValueError:
            continue
        if (end - start).days > TERM_DAYS:
            return True
    return False

# The accounts the asset policy names for capitalization review: their names
# assert non-capital treatment, and the review is whether that holds. Each maps to
# the fixed asset account an asset in service goes to. Office furniture and
# equipment has none in Serif's chart: computers go to Computers & Software, and
# for the rest the entry holds the purchase in Capital in Process and asks.
CAPEX_REVIEW = {
    "6415000": ("1510000", "Lab Equipment - New"),
    # Repairs and maintenance: a repair is expense, a replacement unit is an asset.
    # Service contracts on this account are read by the prepaid rule instead.
    "6435000": ("1510000", "Lab Equipment - New"),
    "6815000": None,
    "6416000": ("1530000", "Computers & Software"),
    "6816000": ("1530000", "Computers & Software"),
}
CAPITAL_IN_PROCESS = ("1505000", "Capital in Process")
COMPUTER_WORDS = re.compile(
    r"laptop|notebook|macbook|computer|workstation|thinkstation|desktop|\bpc\b|"
    r"monitor|tablet|\bsurface\b|server|ipad", re.IGNORECASE)
# Capital in Process holds build-out work and assets bought but not yet placed in
# service. The policy places an asset in service at the invoice date or, for a
# build-out, when employees begin using the space. The ledger has no in-service
# date, so the reviewer is asked for it unless the line states one.
# An expansion counts only of a space ("Office Desk Expansion"): a lab buys cell
# expansion kits.
BUILDOUT_WORDS = re.compile(
    r"build[- ]?out|fit[- ]?out|construction|renovat\w*|tenant improvement|"
    r"leasehold improvement|(?:office|space|desk|floor|suite|facility)\s+(?:\w+\s+)?expansion|"
    r"\bphase\s*\d+", re.IGNORECASE)
NOT_IN_SERVICE_WORDS = re.compile(
    r"\bdeposit\b|down ?payment|progress (?:payment|billing)|milestone|"
    r"not yet (?:installed|delivered|in service)|pending install\w*", re.IGNORECASE)
IN_SERVICE_DATE = re.compile(
    r"(?:placed in service|in service|installed|go[- ]live)\s*(?:on\s*)?"
    r"(\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})", re.IGNORECASE)


def capex_placement(code, text, invoice_date=""):
    """Where a purchase on a capitalization-review account goes if it is capital,
    and why: Capital in Process for build-out work or an asset not yet in service,
    the fixed asset account for an asset in service. Returns {"to", "to_name",
    "kind" (buildout, not_in_service, in_service or no_account), "asset" (the fixed
    asset account it goes to once in service, or ""), "in_service" (the date the
    line states, or ""), "why", "ask"}."""
    text = text or ""
    asset = CAPEX_REVIEW.get(code)
    if code == "6815000" and COMPUTER_WORDS.search(text):
        asset = ("1530000", "Computers & Software")
    asset_s = "{} {}".format(*asset) if asset else ""
    then = asset_s or ("its fixed asset account. The chart has none for office furniture "
                       "and equipment: ask the Controller which account to use")
    m = IN_SERVICE_DATE.search(text)
    in_service = m.group(1) if m else ""
    cip = "{} {}".format(*CAPITAL_IN_PROCESS)
    b, n = BUILDOUT_WORDS.search(text), NOT_IN_SERVICE_WORDS.search(text)
    if b or n:
        kind = "buildout" if b else "not_in_service"
        why = ('The description names build-out work ("{}"). Build-out work stays in {} until '
               "employees begin using the space.".format(b.group(0), cip) if b else
               'The description says it is not yet in service ("{}"). An asset bought but not '
               "yet in service stays in {}.".format(n.group(0), cip))
        ask = ("The line says it went into service on {}: move it to {} at that date.".format(in_service, then)
               if in_service else
               "Ask the date {}, and put it in the note. On that date, move it to {}.".format(
                   "employees began, or will begin, using the space" if b else "it went, or will go, into use", then))
        return {"to": CAPITAL_IN_PROCESS[0], "to_name": CAPITAL_IN_PROCESS[1], "kind": kind,
                "asset": asset_s, "in_service": in_service, "why": why, "ask": ask}
    placed = ("on {}, as the line says".format(in_service) if in_service else
              "at the invoice date{}".format(", " + invoice_date if invoice_date else ""))
    ask = ("" if in_service else
           "The ledger has no in-service date. Ask when it went into use, and put the date in the "
           "note. If it is not in use yet, book it to {} instead.".format(cip))
    if not asset:
        return {"to": CAPITAL_IN_PROCESS[0], "to_name": CAPITAL_IN_PROCESS[1], "kind": "no_account",
                "asset": "", "in_service": in_service,
                "why": ("Nothing on the line says it is build-out work or not yet in service, so the "
                        "policy places it in service {}. An asset in service goes to its fixed asset "
                        "account, and the chart has none for office furniture and equipment, so the "
                        "entry holds it in {}.".format(placed, cip)),
                "ask": ("Ask the Controller which fixed asset account to use, and edit the entry. "
                        + ask).strip()}
    return {"to": asset[0], "to_name": asset[1], "kind": "in_service", "asset": asset_s,
            "in_service": in_service,
            "why": ("Nothing on the line says it is build-out work or not yet in service, so the "
                    "policy places it in service {}. An asset in service goes to its fixed asset "
                    "account, {}.".format(placed, asset_s)),
            "ask": ask}

# Documents a customer receives. Posted to an expense account, they net income
# against cost.
CUSTOMER_TYPES = ("Invoice", "Credit Memo", "Cash Sale", "Cash Refund")
REVENUE_REIMBURSEMENT = ("4001003", "Revenue - Cost Reimbursement")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def period_key(period):
    """'Aug 2026' -> (2026, 8), so periods sort as dates."""
    try:
        mon, year = period.split()
        return int(year), MONTHS.index(mon[:3]) + 1
    except (ValueError, AttributeError):
        return (0, 0)


def norm_vendor(name):
    tokens = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower()).split()
    drop = {"inc", "llc", "ltd", "corp", "corporation", "co", "company", "lp", "the"}
    return " ".join(t for t in tokens if t not in drop)


def gl_txn(t):
    return {"period": t.get("period", ""), "date": t.get("date", ""),
            "txn_type": t.get("txn_type", ""),
            "document_number": t.get("document_number", ""),
            "vendor_or_name": t.get("vendor_or_name", ""),
            "account_code": t["account_code"], "department": t["department"],
            "amount": num(t["amount"])}


def accrual_account(code):
    for codes, acct, name in ACCRUAL_ACCOUNTS:
        if code in codes:
            return acct, name
    return "2207000", "Accrued Other"


def num(value):
    text = str(value if value is not None else "").replace(",", "").replace("$", "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def money(value):
    """Negative amounts in brackets, the convention the console uses."""
    return "(${:,.2f})".format(-value) if value < 0 else "${:,.2f}".format(value)


def fold_departments(gl):
    """One spelling per department. NetSuite can hold the same department under two
    spellings that differ only by case (Platform / PLATFORM), and the plan carries
    one; keyed as written, the other spelling's lines drop out of every match. The
    spelling on the most lines is kept, and the map is returned so the plan and the
    forecast take the same spelling."""
    seen = defaultdict(lambda: defaultdict(int))
    for lines in gl.values():
        for t in lines:
            d = t.get("department") or ""
            seen[d.casefold()][d] += 1
    canon = {cf: max(sorted(sp), key=lambda d: sp[d]) for cf, sp in seen.items()}
    for lines in gl.values():
        for t in lines:
            t["department"] = canon[(t.get("department") or "").casefold()]
    return canon


def fold_book(book, canon):
    """Re-key a plan or forecast book onto the ledger's department spellings."""
    out = {}
    for (code, dept), value in book.items():
        key = (code, canon.get((dept or "").casefold(), dept))
        if isinstance(value, dict):
            slot = out.setdefault(key, {"amount": 0.0, "lines": []})
            slot["amount"] += value["amount"]
            slot["lines"] += value["lines"]
        else:
            out[key] = out.get(key, 0.0) + value
    return out


def load_activity(rows):
    """Activity rows -> {(account_code, department): amount}, leaf names and sections."""
    book = {}
    leaves = {}
    sections = {}
    for row in rows:
        key = (row["account_code"], row["department"])
        book[key] = book.get(key, 0.0) + num(row["period_activity"])
        leaves[row["account_code"]] = row["account_leaf"]
        # `6000000 - Operating Expenses:6100000 - Employee Expenses:6101000 - Salaries`
        # Level two is the rollup a flux pack subtotals on. Falls back to the leaf
        # itself for the other-income and other-expense accounts, which sit flat.
        parts = (row.get("account_path") or "").split(":")
        if len(parts) > 1:
            sections[row["account_code"]] = parts[1].strip()
        elif parts and parts[0].strip():
            sections[row["account_code"]] = parts[0].strip()
    return book, leaves, sections


def is_pl(code):
    return bool(code) and code[0] in PL_PREFIXES


def by_account(book):
    """{(account, department): amount} -> {account: amount}, P&L only."""
    out = defaultdict(float)
    for (code, _dept), value in book.items():
        if is_pl(code):
            out[code] += value
    return out


def txn_out(t):
    """A ledger line as a finding carries it. An expense report's name field is
    the employee who filed it, so it is replaced: a person is not a vendor."""
    person = t.get("txn_type") == "Expense Report"
    return {"period": t["period"], "date": t.get("date", ""),
            "txn_type": t.get("txn_type", ""),
            "document_number": t.get("document_number", ""),
            "vendor_or_name": "Expense report" if person else t.get("vendor_or_name", ""),
            "account_code": t["account_code"], "department": t["department"],
            "description": ((t.get("description") or t.get("memo") or "").strip())[:140],
            "amount": num(t["amount"])}


def payee(t):
    """Who a line is with, as a reviewer reads it."""
    if t.get("txn_type") == "Expense Report":
        return "Expense report"
    return (t.get("vendor_or_name") or "").strip() or "Journal, no vendor"


MOVERS = 10
MOVER_LINES = 4


def movers(code, cur_lines, prior_lines):
    """What moved inside one account: each department and vendor this month
    against the prior month, largest change first, with the lines behind each
    from both months. This is the drill a reviewer does by hand: account, then
    department, then vendor, then the line."""
    agg = defaultdict(lambda: [0.0, 0.0])
    lines = defaultdict(lambda: ([], []))
    for i, book in enumerate((prior_lines, cur_lines)):
        for t in book:
            if t["account_code"] != code:
                continue
            key = (t["department"] or "No department", payee(t))
            agg[key][i] += num(t["amount"])
            lines[key][i].append(t)
    rows = []
    for key, (was, now) in agg.items():
        if abs(now - was) < 0.005:
            continue
        both = []
        for i in (1, 0):
            picked = sorted(lines[key][i], key=lambda t: -abs(num(t["amount"])))[:MOVER_LINES]
            both += [txn_out(t) for t in picked]
        rows.append({"department": key[0], "vendor": key[1], "prior": round(was, 2),
                     "actual": round(now, 2), "change": round(now - was, 2), "lines": both})
    rows.sort(key=lambda r: -abs(r["change"]))
    return rows[:MOVERS]


def account_drivers(gl_lines, code):
    """The account's ledger lines, largest first, and its three largest vendors.
    Expense reports are left out of the vendor ranking."""
    drivers = sorted((t for t in gl_lines if t["account_code"] == code),
                     key=lambda t: -abs(num(t["amount"])))
    vendors = defaultdict(float)
    for t in drivers:
        if t.get("vendor_or_name") and t.get("txn_type") != "Expense Report":
            vendors[t["vendor_or_name"].strip()] += num(t["amount"])
    ranked = sorted(vendors.items(), key=lambda kv: -abs(kv[1]))[:3]
    return drivers, [[v, round(a, 2)] for v, a in ranked]


def departments_of(code, books, names):
    """One account's amount in each department, per book, largest move first."""
    depts = set()
    for book in books:
        depts |= {d for (c, d) in book if c == code}
    rows = []
    for d in depts:
        row = {"department": d or "No department"}
        for name, book in zip(names, books):
            row[name] = round(book.get((code, d), 0.0), 2)
        rows.append(row)
    rows.sort(key=lambda r: (-abs(r[names[0]] - r[names[1]]), r["department"]))
    return rows


def variance_findings(current, prior, prior_year, leaves, period, prior_period,
                      py_period, gl_lines, seq, prior_lines=()):
    """One finding per P&L account that moved against the prior month.

    Commentary is written per account, the line of the income statement, so the
    test is per account too. The departments behind the move ride on the finding,
    so a reader can see where it sits without a second finding per department.
    The prior year is carried for context and does not raise a finding on its own.
    """
    now_b, then_b = by_account(current), by_account(prior)
    year_b = by_account(prior_year) if prior_year else {}
    books, names = [current, prior], ["actual", "prior"]
    if prior_year:
        books.append(prior_year)
        names.append("prior_year")
    findings = []
    for code in sorted(set(now_b) | set(then_b)):
        now, was = now_b.get(code, 0.0), then_b.get(code, 0.0)
        mom = now - was
        if abs(mom) < REPORTING_FLOOR:
            continue
        yoy = (now - year_b.get(code, 0.0)) if prior_year else None
        leaf = leaves.get(code, code)
        drivers, ranked = account_drivers(gl_lines, code)
        observed = "{} {} · vs {} {} ({}{})".format(
            period, money(now), prior_period, money(was), "+" if mom >= 0 else "", money(mom))
        if yoy is not None:
            observed += " · vs {} {} ({}{})".format(
                py_period, money(year_b.get(code, 0.0)), "+" if yoy >= 0 else "", money(yoy))
        seq[0] += 1
        findings.append({
            "finding_id": "{}-{:04d}".format(period.replace(" ", "").lower(), seq[0]),
            "rule_id": "F1.VARIANCE",
            "rule_version": "3.0.0",
            "layer": LAYER_FPA,
            "title": "{}: {} {} on {}".format(leaf, "up" if mom >= 0 else "down",
                                              money(abs(mom)), prior_period),
            "severity": "high" if abs(mom) >= POST_CLOSE_QUARTERLY else "medium",
            "kind": "deterministic",
            "period": period,
            "policy_basis": POLICY_THRESHOLD,
            "policy_is_draft": True,
            "confidence": 1.0,
            "confidence_note": "",
            "amount_at_risk": round(abs(mom), 2),
            "account_code": code,
            "actual_amount": round(now, 2),
            "prior_amount": round(was, 2),
            "prior_year_amount": round(year_b.get(code, 0.0), 2) if prior_year else None,
            "mom_variance": round(mom, 2),
            "yoy_variance": round(yoy, 2) if yoy is not None else None,
            "departments": departments_of(code, books, names),
            "movers": movers(code, gl_lines, prior_lines) if prior_lines else [],
            "top_vendors": ranked,
            "recommendation": (
                "Name what drove the movement in {}. Book an entry only if the period "
                "is misstated; a real change in run rate is explained, not corrected. "
                "If expense fell, check accrual completeness first.".format(leaf)),
            "evidence": {
                "observed": observed,
                "expected": "",
                "basis": "Largest vendors: " + ("; ".join(v + " " + money(a) for v, a in ranked)
                                                 if ranked else "none, no vendor on these lines"),
            },
            "transaction_count": len(drivers),
            "transactions": [txn_out(t) for t in drivers[:8]],
            "transactions_truncated": len(drivers) > 8,
        })
    return findings

def accrual_findings(coupa_rows, leaves, period, seq):
    """Goods received but not yet invoiced, the accrual population."""
    groups = defaultdict(lambda: {"value": 0.0, "lines": 0, "pos": []})
    for row in coupa_rows:
        value = num(row.get("received_not_invoiced_value"))
        if value <= 0:
            continue
        key = (row["supplier"], row["gl_account_code"])
        bucket = groups[key]
        bucket["value"] += value
        bucket["lines"] += 1
        if row.get("po_number"):
            bucket["pos"].append(row["po_number"])

    findings = []
    for (supplier, code), bucket in sorted(groups.items(), key=lambda kv: -kv[1]["value"]):
        if bucket["value"] < ACCRUAL_THRESHOLD:
            continue
        acct, acct_name = accrual_account(code)
        leaf = leaves.get(code, code)
        pos = sorted(set(bucket["pos"]))[:6]
        seq[0] += 1
        findings.append({
            "finding_id": "{}-{:04d}".format(period.replace(" ", "").lower(), seq[0]),
            "rule_id": "F3.ACCRUAL_RECEIPT",
            "rule_version": "1.0.0",
            "layer": LAYER_ACCOUNTING,
            "title": "{}: {} received not invoiced".format(supplier, money(bucket["value"])),
            "severity": "high" if bucket["value"] >= PRE_CLOSE_ADJUSTMENT else "medium",
            "kind": "needs_judgement",
            "period": period,
            "policy_basis": POLICY_ACCRUAL,
            "policy_is_draft": True,
            "confidence": 0.85,
            "confidence_note": (
                "Receipt evidence from Coupa, which is stronger than a billing-pattern "
                "estimate. Capped at 85%: the value is pro-rated from the line total, and "
                "lines carrying no quantity cannot be pro-rated at all."),
            "amount_at_risk": round(bucket["value"], 2),
            "correction": {
                "dimension": "Cut-off",
                "subject": supplier + " / " + leaf,
                "current_label": "Booked",
                "current": money(0.0),
                "proposed_label": "Accrue",
                "proposed": money(bucket["value"]),
                "entry": "Dr {} {} / Cr {} {} for {}".format(
                    code, leaf, acct, acct_name, money(bucket["value"])),
                "pl_impact": round(bucket["value"], 2),
            },
            "recommendation": (
                "Propose an accrual: Dr {} {} / Cr {} {} for {}. Confirm with the requester "
                "that the goods or services were received in the period, then post. "
                "Reverses automatically next period per policy.".format(
                    code, leaf, acct, acct_name, money(bucket["value"]))),
            "evidence": {
                "observed": "{} PO line(s) received but not yet invoiced".format(bucket["lines"]),
                "expected": "an accrual, or an invoice, in the period the goods arrived",
                "basis": "Coupa PO " + (", ".join(pos) if pos else "n/a"),
            },
            "transaction_count": bucket["lines"],
            "transactions": [],
            "transactions_truncated": False,
        })
    return findings


def load_budget(rows, period):
    """Plan rows by account, department and month -> ({(account_code, department):
    amount}, vintage_label, rows_read) for the period under review."""
    book = {}
    vintages = set()
    hits = 0
    for row in rows:
        if (row.get("period") or "").strip() != period:
            continue
        hits += 1
        key = (row["account_code"], row["department"])
        book[key] = book.get(key, 0.0) + num(row["budget_amount"])
        if row.get("budget_version"):
            vintages.add(row["budget_version"].strip())
    return book, "; ".join(sorted(vintages)), hits


def load_model_lines(rows, period):
    """Forecast LINE items for one period, keyed by account and department.

    Line-level rather than aggregated because the description is the evidence: a
    line reading 'Claude Reclass: Labs to CMC' with no vendor and no PO is what
    turns an unexplained difference into a named entry somebody staged.
    """
    book = defaultdict(lambda: {"amount": 0.0, "lines": []})
    for row in rows:
        if (row.get("period") or "").strip() != period:
            continue
        key = (row["account_code"], row["department"])
        value = num(row["amount"])
        book[key]["amount"] += value
        if value:
            book[key]["lines"].append(row)
    return book


def budget_findings(current, budget, leaves, period, vintage, gl_lines, seq):
    """Actual against plan, per P&L account, the FP&A layer.

    ONLY for an account the forecast plans. An account the forecast never planned
    is a coverage gap, not an overspend, and reporting it as a variance would put
    the whole of payroll in the queue every month because payroll is built on a tab
    this feed does not read. The uncovered population is carried as a metric
    instead, so it stays visible without being mistaken for a finding.
    """
    plan_b, now_b = by_account(budget), by_account(current)
    findings = []
    for code in sorted(plan_b):
        planned = plan_b[code]
        actual = now_b.get(code, 0.0)
        delta = actual - planned
        if abs(delta) < REPORTING_FLOOR:
            continue
        leaf = leaves.get(code, code)
        over = delta > 0
        drivers, ranked = account_drivers(gl_lines, code)
        seq[0] += 1
        findings.append({
            "finding_id": "{}-{:04d}".format(period.replace(" ", "").lower(), seq[0]),
            "rule_id": "F2.BUDGET",
            "rule_version": "2.0.0",
            "layer": LAYER_FPA,
            "title": "{}: {} {} plan".format(leaf, money(abs(delta)), "over" if over else "under"),
            "severity": "high" if abs(delta) >= POST_CLOSE_QUARTERLY else "medium",
            "kind": "needs_judgement",
            "period": period,
            "policy_basis": POLICY_THRESHOLD,
            "policy_is_draft": True,
            "confidence": 1.0,
            "confidence_note": "",
            "amount_at_risk": round(abs(delta), 2),
            "account_code": code,
            "budget_amount": round(planned, 2),
            "actual_amount": round(actual, 2),
            "budget_variance": round(delta, 2),
            "departments": departments_of(code, [current, budget], ["actual", "budget"]),
            "movers": movers(code, gl_lines, []),
            "top_vendors": ranked,
            "recommendation": (
                "Actuals are {} against the {} plan for {}. Say what drove it. An entry "
                "is only needed if the spend is misstated or miscoded; a real change in "
                "run rate is explained, not corrected.".format(
                    money(abs(delta)) + (" over" if over else " under"), vintage or "prior", leaf)
                + (" The plan is a {} of {} and the ledger holds a {} of {}, so the sign "
                   "has flipped.".format("credit" if planned < 0 else "charge", money(abs(planned)),
                                         "credit" if actual < 0 else "charge", money(abs(actual)))
                   if planned * actual < 0 else "")),
            "evidence": {
                "observed": "{} actual {} against plan {} ({}{})".format(
                    period, money(actual), money(planned), "+" if delta >= 0 else "", money(delta)),
                "expected": "",
                "basis": ("Plan from the " + (vintage or "prior") + " forecast vintage. "
                          "Largest vendors: "
                          + ("; ".join(v + " " + money(a) for v, a in ranked)
                             if ranked else "none, no vendor on these lines")),
            },
            "transaction_count": len(drivers),
            "transactions": [txn_out(t) for t in drivers[:8]],
            "transactions_truncated": len(drivers) > 8,
        })
    return findings


def model_tie_findings(current, model, leaves, period, vintage, seq):
    """Where the FP&A model and the ledger disagree, the accounting layer.

    The current forecast vintage's closed months are the posted actuals, so these
    two should agree. Where they do not, something has been staged in the model
    and not booked, or booked and not modelled. Either way it is an entry
    question, which is what makes it an accounting finding rather than a variance.

    This is the rule that surfaces the $4.47M 'Claude Reclass: Labs to CMC'
    topside: four monthly pairs sitting in the model with no vendor, no PO and a
    line number inserted out of sequence, against a ledger that never received it.
    """
    findings = []
    # ONLY where the model actually carries this account and department. The
    # build tabs do not plan payroll or depreciation at all, so comparing a
    # modelled zero against real salary expense would report the whole payroll
    # run as a difference every month and bury the two lines that matter.
    # Uncovered keys are counted in budget_coverage instead.
    keys = {k for k in model if is_pl(k[0])}
    for key in sorted(keys):
        code, dept = key
        modelled = model.get(key, {}).get("amount", 0.0)
        actual = current.get(key, 0.0)
        delta = modelled - actual
        if abs(delta) < REPORTING_FLOOR:
            continue

        leaf = leaves.get(code, code)
        lines = model.get(key, {}).get("lines", [])
        # A line with no vendor and no PO is a manual overlay rather than a real
        # commitment, which is the strongest available signal for an unbooked
        # topside.
        topsides = [x for x in lines
                    if not (x.get("vendor") or "").strip()
                    and not (x.get("po_number") or "").strip()
                    and (x.get("description") or "").strip()]
        notes = "; ".join(sorted({(x.get("description") or "").strip()
                                  for x in topsides}))[:240]

        seq[0] += 1
        findings.append({
            "finding_id": "{}-{:04d}".format(period.replace(" ", "").lower(), seq[0]),
            "rule_id": "F5.MODEL_TIE",
            "rule_version": "1.0.0",
            "layer": LAYER_ACCOUNTING,
            "title": "{} / {}: model and ledger differ by {}".format(
                leaf, dept, money(abs(delta))),
            "severity": "high" if abs(delta) >= PRE_CLOSE_ADJUSTMENT else "medium",
            "kind": "needs_judgement",
            "period": period,
            "policy_basis": POLICY_THRESHOLD,
            "policy_is_draft": True,
            "confidence": 1.0 if topsides else 0.8,
            "confidence_note": (
                "" if topsides else
                "No manual overlay identified on the model side, so the difference "
                "may be a modelling gap rather than an unbooked entry."),
            "amount_at_risk": round(abs(delta), 2),
            "model_amount": round(modelled, 2),
            "actual_amount": round(actual, 2),
            "correction": {
                "dimension": "",
                "subject": "{} {} / {}".format(code, leaf, dept),
                "current_label": "Ledger",
                "current": money(actual),
                "proposed_label": "Model",
                "proposed": money(modelled),
                "entry": ("Dr {} {} / {} for {}".format(code, leaf, dept, money(abs(delta)))
                          if topsides and delta > 0 else
                          "Cr {} {} / {} for {}".format(code, leaf, dept, money(abs(delta)))
                          if topsides else ""),
                # A reclass moves cost between accounts and nets to zero across the
                # pair. This rule sees one side at a time, so it cannot assert the
                # net effect without inventing the counter-account.
                "pl_impact": None,
            },
            "recommendation": (
                ("The model carries {} that the ledger does not"
                 if delta > 0 else
                 "The ledger carries {} that the model does not").format(money(abs(delta)))
                + " for {} / {}. ".format(leaf, dept)
                + ("Staged as: " + notes + ". Book it or reject it."
                   if notes else
                   "No manual overlay is identified, so confirm whether this is an "
                   "unbooked entry or a gap in the model.")),
            "evidence": {
                "observed": "model {} against ledger {} ({}{})".format(
                    money(modelled), money(actual),
                    "+" if delta >= 0 else "", money(delta)),
                "expected": ("the " + (vintage or "current") + " vintage's closed months "
                             "to equal the posted actuals"),
                "basis": (notes if notes else "no manual overlay identified")
                         + " · {} model line(s)".format(len(lines)),
            },
            "transaction_count": len(lines),
            "transactions": [],
            "transactions_truncated": False,
            "model_lines": [{
                "description": (x.get("description") or "").strip(),
                "vendor": (x.get("vendor") or "").strip(),
                "po_number": (x.get("po_number") or "").strip(),
                "amount": num(x.get("amount")),
                "line_ref": (x.get("line_ref") or "").strip(),
            } for x in lines[:8]],
        })
    return findings


def _finding(period, seq, rule, layer, title, kind, amount, policy, confidence,
             confidence_note, correction, recommendation, evidence, txns, **extra):
    seq[0] += 1
    out = {
        "finding_id": "{}-{:04d}".format(period.replace(" ", "").lower(), seq[0]),
        "rule_id": rule, "rule_version": "1.0.0", "layer": layer, "title": title,
        "severity": "high" if amount >= PRE_CLOSE_ADJUSTMENT else "medium",
        "kind": kind, "period": period, "policy_basis": policy, "policy_is_draft": True,
        "confidence": confidence, "confidence_note": confidence_note,
        "amount_at_risk": round(amount, 2), "correction": correction,
        "recommendation": recommendation, "evidence": evidence,
        "transaction_count": len(txns),
        "transactions": [gl_txn(t) for t in txns[:8]],
        "transactions_truncated": len(txns) > 8,
    }
    out.update(extra)
    return out


def bills_by_vendor(lines):
    """vendor -> {"amount", "docs", "by_key": {(account, dept): amount}, "lines"} over
    P&L bills. A bill is how a vendor's month shows up in the ledger."""
    out = defaultdict(lambda: {"amount": 0.0, "docs": set(),
                               "by_key": defaultdict(float), "lines": []})
    for t in lines:
        vendor = (t.get("vendor_or_name") or "").strip()
        if t.get("txn_type") not in ("Bill", "Bill Credit") or not vendor or not is_pl(t["account_code"]):
            continue
        b = out[vendor]
        value = num(t["amount"])
        b["amount"] += value
        b["docs"].add(t.get("document_number", ""))
        b["by_key"][(t["account_code"], t["department"])] += value
        b["lines"].append(t)
    return out


def billing_pattern_findings(gl_lines, history, coupa_rows, receipt_suppliers,
                             leaves, period, seq):
    """Step B of the accrual method: a vendor that bills every month and has not
    billed this one. Only where Coupa does not reach, and never for a supplier the
    receipt method already accrues.

    Per the Accrued Expense Policy's worked example: a vendor with at least three
    invoices in the trailing six periods, a trailing three-month average over the
    $5,000 threshold, and a current month that is nil or under a quarter of that
    average. The proposal is the average less what has been billed.
    """
    periods = sorted(history, key=period_key)[-6:]
    if len(periods) < 3:
        return []
    last3 = periods[-3:]
    by_period = {p: bills_by_vendor(history[p]) for p in periods}
    now = bills_by_vendor(gl_lines)
    in_coupa = {norm_vendor(r.get("supplier")) for r in coupa_rows} | {
        norm_vendor(s) for s in receipt_suppliers}

    findings = []
    vendors = sorted({v for p in periods for v in by_period[p]})
    for vendor in vendors:
        if norm_vendor(vendor) in in_coupa:
            continue
        invoices = sum(len(by_period[p][vendor]["docs"]) for p in periods if vendor in by_period[p])
        if invoices < 3:
            continue
        monthly = [by_period[p][vendor]["amount"] if vendor in by_period[p] else 0.0 for p in last3]
        avg = sum(monthly) / 3.0
        current = now[vendor]["amount"] if vendor in now else 0.0
        if avg <= ACCRUAL_THRESHOLD or not (current == 0 or current < 0.25 * avg):
            continue
        accrue = avg - max(current, 0.0)
        if accrue < ACCRUAL_THRESHOLD:
            continue
        # Where the average would be booked: the account and department the
        # vendor's trailing three months were mostly coded to.
        keys = defaultdict(float)
        for p in last3:
            for k, v in (by_period[p].get(vendor) or {"by_key": {}})["by_key"].items():
                keys[k] += v
        (code, dept), _ = max(keys.items(), key=lambda kv: abs(kv[1]))
        acct, acct_name = accrual_account(code)
        leaf = leaves.get(code, code)
        billed_months = sum(1 for m in monthly if m)
        lumpy = billed_months < 2
        history_lines = [t for p in last3 for t in (by_period[p].get(vendor) or {"lines": []})["lines"]]
        history_lines.sort(key=lambda t: -abs(num(t["amount"])))
        trail = ", ".join("{} {}".format(p, money(m)) for p, m in zip(last3, monthly))
        findings.append(_finding(
            period, seq, "F6.ACCRUAL_PATTERN", LAYER_ACCOUNTING,
            "{}: {} expected from billing pattern".format(vendor, money(accrue)),
            "needs_judgement", accrue, POLICY_ACCRUAL,
            0.4 if lumpy else 0.6,
            ("Pattern-derived, not receipt evidence. " +
             ("Billed in only {} of the last three months, so the average rests on a "
              "single invoice and may be a milestone rather than a run rate.".format(billed_months)
              if lumpy else
              "Billed in {} of the last three months.".format(billed_months))),
            {"dimension": "Cut-off", "subject": vendor + " / " + leaf,
             "current_label": "Billed in " + period, "current": money(current),
             "proposed_label": "Accrue", "proposed": money(accrue),
             "entry": "Dr {} {} / {} / Cr {} {} for {}".format(
                 code, leaf, dept, acct, acct_name, money(accrue)),
             "pl_impact": round(accrue, 2)},
            ("Confirm with the budget owner whether {} performed in {} and has not yet "
             "invoiced. If so, accrue Dr {} {} / Cr {} {} for {}, reversing next period. "
             "If the work stopped, no entry.".format(
                 vendor, period, code, leaf, acct, acct_name, money(accrue))),
            {"observed": "{} billed in {} against a trailing three-month average of {} ({})".format(
                money(current), period, money(avg), trail),
             "expected": "a bill, or an accrual, in a month the vendor normally bills",
             "basis": "{} invoice(s) in the trailing six periods; no Coupa line this period".format(invoices)},
            history_lines))
    return findings


def revenue_in_expense_findings(gl_lines, leaves, period, seq):
    """A customer document posted to an expense account. It nets income against
    cost, which understates both and turns an expense variance negative."""
    findings = []
    for t in gl_lines:
        if t.get("txn_type") not in CUSTOMER_TYPES or not is_pl(t["account_code"]):
            continue
        if not t["account_code"].startswith(("6", "7")):
            continue
        value = num(t["amount"])
        if abs(value) < REPORTING_FLOOR:
            continue
        code, dept = t["account_code"], t["department"]
        leaf = leaves.get(code, code)
        rev, rev_name = REVENUE_REIMBURSEMENT
        name = (t.get("vendor_or_name") or "").strip() or "No name"
        findings.append(_finding(
            period, seq, "F7.REVENUE_IN_EXPENSE", LAYER_ACCOUNTING,
            "{}: {} {} posted to {}".format(name, t.get("txn_type"), money(abs(value)), leaf),
            "needs_judgement", abs(value), POLICY_DATA_ENTRY, 0.8,
            "A recharge is sometimes netted against its cost on purpose. Confirm the "
            "treatment Serif intends before reclassing.",
            {"dimension": "Account", "subject": "{} {} / {}".format(code, leaf, dept),
             "current_label": "Posted to", "current": "{} {}".format(code, leaf),
             "proposed_label": "Should be", "proposed": "{} {}".format(rev, rev_name),
             "entry": "Dr {} {} / {} / Cr {} {} for {}".format(
                 code, leaf, dept, rev, rev_name, money(abs(value))),
             "pl_impact": None},
            ("{} {} is a customer document, and it credits {} {}. If it bills a "
             "cost back, it is income: Dr {} {} / Cr {} {} for {}.".format(
                 t.get("txn_type"), t.get("document_number", ""), code, leaf, code, leaf,
                 rev, rev_name, money(abs(value)))),
            {"observed": "{} {} {} to {} {}".format(
                t.get("txn_type"), t.get("document_number", ""), money(value), code, leaf),
             "expected": "customer documents posted to revenue or a receivable, not to expense",
             "basis": "Transaction type " + t.get("txn_type")},
            [t]))
    return findings


def vendor_dropped_findings(gl_lines, history, leaves, period, seq):
    """A journal with no counterparty whose account, department and amount match
    a line that named one earlier. The vendor fell off a recurring entry."""
    hist = [t for p in history for t in history[p]]
    # Bills to a prepaid account, now or earlier. A blank-vendor journal for the
    # same amount is most likely the monthly release of that prepaid.
    prepaid_bills = [h for h in hist + list(gl_lines)
                     if h.get("txn_type") == "Bill" and h["account_code"].startswith("13")
                     and (h.get("vendor_or_name") or "").strip()]
    findings = []
    for t in gl_lines:
        if (t.get("vendor_or_name") or "").strip() or t.get("txn_type") != "Journal":
            continue
        code, dept, value = t["account_code"], t["department"], num(t["amount"])
        if not is_pl(code) or abs(value) < REPORTING_FLOOR:
            continue
        named = sorted({(h.get("vendor_or_name") or "").strip() for h in hist
                        if h["account_code"] == code and h["department"] == dept
                        and abs(num(h["amount"]) - value) < 0.01
                        and (h.get("vendor_or_name") or "").strip()})
        if not named:
            continue
        seen = sorted({h.get("period", "") for h in hist
                       if h["account_code"] == code and h["department"] == dept
                       and abs(num(h["amount"]) - value) < 0.01
                       and (h.get("vendor_or_name") or "").strip()}, key=period_key)
        leaf = leaves.get(code, code)
        release = [b for b in prepaid_bills if abs(num(b["amount"]) - value) < 0.01]
        release_note = (
            " The same amount was billed by {} to {} in {}, so this is most likely that "
            "prepaid's monthly release, which should carry the vendor too.".format(
                release[0].get("vendor_or_name"), release[0]["account_code"],
                release[0].get("period", "")) if release else "")
        findings.append(_finding(
            period, seq, "F8.VENDOR_DROPPED", LAYER_ACCOUNTING,
            ("{} / {}: {} prepaid release with no vendor, billed by {}" if release else
             "{} / {}: {} journal with no vendor, previously {}").format(
                leaf, dept, money(abs(value)), named[0]),
            "needs_judgement", abs(value), POLICY_DATA_ENTRY, 0.6 if release else 0.9,
            "Matched on account, department and amount to the cent." + release_note,
            {"dimension": "Vendor", "subject": "{} {} / {}".format(code, leaf, dept),
             "current_label": "Vendor", "current": "none",
             "proposed_label": "Previously", "proposed": "; ".join(named),
             "entry": "", "pl_impact": None},
            ("Journal {} carries no vendor. The same amount on the same account and "
             "department named {} in {}. Add the vendor to the entry, or confirm why it "
             "changed.".format(t.get("document_number", ""), "; ".join(named), ", ".join(seen))),
            {"observed": "journal {} for {} with no vendor".format(
                t.get("document_number", ""), money(value)),
             "expected": "the counterparty named on every entry",
             "basis": "Same account, department and amount named {} in {}".format(
                 "; ".join(named), ", ".join(seen))},
            [t]))
    return findings


def prepaid_findings(gl_lines, history, leaves, period, seq):
    """A charge that pays for months ahead, expensed in one. Related charges for
    the same good or service are aggregated before the $25,000 test, per policy.

    A charge qualifies when its wording names a term (a service contract, a
    subscription, a renewal, a date range), or when it sits on a term account and
    the vendor does not bill that account most months, which is what separates an
    annual payment from a monthly one."""
    months = sorted(history, key=period_key)[-6:]
    groups = defaultdict(list)
    for t in gl_lines:
        if t.get("txn_type") != "Bill" or not is_pl(t["account_code"]):
            continue
        groups[((t.get("vendor_or_name") or "").strip(), t["account_code"])].append(t)
    findings = []
    for (vendor, code), lines in sorted(groups.items()):
        total = sum(num(t["amount"]) for t in lines)
        if total < PREPAID_THRESHOLD:
            continue
        worded = [t for t in lines if names_a_term(t.get("description"))
                  or names_a_term(t.get("memo"))]
        billed = sum(1 for p in months if any(
            (h.get("vendor_or_name") or "").strip() == vendor and h["account_code"] == code
            for h in history[p]))
        # A vendor billing this account most months is charging monthly for what is
        # consumed monthly. That is expense, however the invoice is worded.
        if months and billed > len(months) // 2:
            continue
        term_account = code in PREPAID_ACCOUNTS and code not in CAPEX_REVIEW
        if not worded and not term_account:
            continue
        prepaid, prepaid_name = PREPAID_ACCOUNTS.get(code, ("1315000", "Prepaid Other"))
        leaf = leaves.get(code, code)
        dept = max(defaultdict(float, {t["department"]: 0 for t in lines}),
                   key=lambda d: sum(abs(num(t["amount"])) for t in lines if t["department"] == d))
        text = "; ".join(sorted({(t.get("description") or "").strip() for t in worded or lines
                                 if (t.get("description") or "").strip()}))[:200]
        findings.append(_finding(
            period, seq, "F9.PREPAID", LAYER_ACCOUNTING,
            "{}: {} on {} may cover future months".format(vendor, money(total), leaf),
            "needs_judgement", total, POLICY_PREPAID, 0.7 if worded else 0.5,
            ("The wording names a term." if worded else
             "The vendor billed this account in {} of the last {} months, so this may "
             "be an advance payment rather than a monthly charge.".format(billed, len(months))),
            {"dimension": "Prepaid", "subject": "{} / {}".format(vendor, leaf),
             "current_label": "Expensed in " + period, "current": money(total),
             "proposed_label": "Prepaid, then amortized", "proposed": prepaid + " " + prepaid_name,
             "entry": "Dr {} {} / Cr {} {} / {} for {}".format(
                 prepaid, prepaid_name, code, leaf, dept, money(total)),
             "pl_impact": None},
            ("Read the invoice for the service period. If it runs past {}, move it to {} "
             "{} and amortize straight-line, booking this month's share back to {} {}. "
             "Dr {} {} / Cr {} {} for {}, then the amortization.".format(
                 period, prepaid, prepaid_name, code, leaf,
                 prepaid, prepaid_name, code, leaf, money(total))),
            {"observed": "{} across {} bill line(s){}".format(
                money(total), len(lines), (": " + text) if text else ""),
             "expected": "charges of $25,000 or more that cover future months recorded as prepaid",
             "basis": "Billed on this account in {} of the last {} months".format(billed, len(months))},
            sorted(lines, key=lambda t: -abs(num(t["amount"])))))
    return findings


def capex_findings(gl_lines, leaves, period, seq):
    """Purchases on the accounts the asset policy names for capitalization review.
    Every document on those accounts from the reporting floor up is listed, and the
    reviewer's CapEx threshold (the $5,000 capitalization threshold by default)
    decides the queue. Each says whether it goes to Capital in Process or to its
    fixed asset account, and why (capex_placement)."""
    docs = defaultdict(list)
    for t in gl_lines:
        if t.get("txn_type") == "Bill" and t["account_code"] in CAPEX_REVIEW:
            docs[((t.get("vendor_or_name") or "").strip(), t.get("document_number", ""),
                  t["account_code"])].append(t)
    findings = []
    for (vendor, doc, code), lines in sorted(docs.items()):
        total = sum(num(t["amount"]) for t in lines)
        if total < REPORTING_FLOOR:
            continue
        # Service and support are consumed, not owned; the prepaid rule reads those.
        text = "; ".join(sorted({(t.get("description") or "").strip() for t in lines
                                 if (t.get("description") or "").strip()}))[:200]
        if names_a_term(text):
            continue
        words = " ".join((t.get("description") or "") + " " + (t.get("memo") or "") for t in lines)
        place = capex_placement(code, words, lines[0].get("date", ""))
        asset, asset_name = place["to"], place["to_name"]
        leaf = leaves.get(code, code)
        dept = lines[0]["department"]
        findings.append(_finding(
            period, seq, "F10.CAPITALIZE", LAYER_ACCOUNTING,
            "{}: {} on {} may be a capital asset".format(vendor, money(total), leaf),
            "needs_judgement", total, POLICY_ASSET, 0.5,
            "Capitalization turns on what was bought and how long it lasts, which the "
            "invoice says and the ledger does not.",
            {"dimension": "Capitalize", "subject": "{} / {}".format(vendor, leaf),
             "current_label": "Expensed to", "current": "{} {}".format(code, leaf),
             "proposed_label": "If capital", "proposed": "{} {}".format(asset, asset_name),
             "entry": "Dr {} {} / Cr {} {} / {} for {}".format(
                 asset, asset_name, code, leaf, dept, money(total)),
             "placement": place, "pl_impact": None},
            ("Read bill {}. If it buys equipment or furniture with a useful life past a "
             "year, capitalize it to {} {} and depreciate from the date it is placed in service "
             "(office furniture and equipment: five years). {} {}".format(
                 doc, asset, asset_name, place["why"], place["ask"]).strip()),
            {"observed": "bill {} for {}{}".format(doc, money(total), (": " + text) if text else ""),
             "expected": "a capitalization decision recorded for each purchase on this account",
             "basis": "The account name asserts non-capital treatment; the policy asks whether that holds"},
            lines))
    return findings


def bills_to_balance_sheet(gl_lines):
    """Bills posted straight to prepaid and fixed-asset accounts this period, so
    the reviewer can see what is already capitalized or prepaid beside what the
    rules propose."""
    out = []
    for t in gl_lines:
        if t.get("txn_type") in ("Bill", "Bill Credit") and t["account_code"][:2] in ("13", "15"):
            out.append({"vendor": t.get("vendor_or_name", ""), "account": t["account_code"],
                        "document": t.get("document_number", ""), "date": t.get("date", ""),
                        "amount": round(num(t["amount"]), 2),
                        "description": (t.get("description") or "").strip()[:140]})
    return sorted(out, key=lambda r: -abs(r["amount"]))


def flux_table(cur, prior, prior_year, budget, leaves, sections,
               period, prior_period, py_period, vintage, findings,
               prior2=None, prior2_period=None):
    """The flux pack as a table: every P&L account, not just the exceptions.

    THIS IS A DIFFERENT OBJECT FROM A FINDING AND IT IS NOT FILTERED.
    A findings queue answers "what needs a decision". A flux pack answers "explain
    the period", and an account that did not move is part of that answer: a flat
    line is a statement, and a reviewer who cannot see it cannot confirm it.
    So every account with activity in any of the periods appears, including the
    ones sitting at zero variance.

    Both comparisons ride on one row, for the same reason the variance finding
    carries both: a reader following an account should not have to change view to
    see the other half of its story.

    Commentary is deliberately absent. The engine computes arithmetic and writes
    no prose, so the column comes back empty and is filled by a reviewer or a
    model. Seeding it from the recommendation text would be the engine writing
    commentary in everything but name.
    """
    def by_account(book):
        out = {}
        for (code, _dept), value in book.items():
            if is_pl(code):
                out[code] = out.get(code, 0.0) + value
        return out

    now, then, year = by_account(cur), by_account(prior), by_account(prior_year)
    # Two months back, so the pack reads as a three-month run the way a reviewer
    # reads the ledger: a swing that reverses next month shows as one.
    back2 = by_account(prior2 or {})
    plan = {}
    for (code, _dept), value in (budget or {}).items():
        if is_pl(code):
            plan[code] = plan.get(code, 0.0) + value

    # Each comparison's finding for the account, so a row opens the evidence for
    # the comparison it is read under.
    mom_finding = {f["account_code"]: f["finding_id"] for f in findings
                   if f.get("rule_id") == "F1.VARIANCE"}
    budget_finding = {f["account_code"]: f["finding_id"] for f in findings
                      if f.get("rule_id") == "F2.BUDGET"}

    def pct(delta, base):
        return round(delta / base * 100, 1) if base else None

    grouped = {}
    for code in sorted(set(now) | set(then) | set(year) | set(plan)):
        a, b, y = now.get(code, 0.0), then.get(code, 0.0), year.get(code, 0.0)
        p_ = plan.get(code)
        row = {
            "account_code": code,
            "account_leaf": leaves.get(code, code),
            "actual": round(a, 2),
            "prior": round(b, 2),
            "prior2": round(back2.get(code, 0.0), 2) if prior2 is not None else None,
            "prior_year": round(y, 2),
            "budget": round(p_, 2) if p_ is not None else None,
            "mom_var": round(a - b, 2), "mom_pct": pct(a - b, b),
            "yoy_var": round(a - y, 2) if year else None,
            "yoy_pct": pct(a - y, y) if year else None,
            "budget_var": round(a - p_, 2) if p_ is not None else None,
            "budget_pct": pct(a - p_, p_) if p_ is not None else None,
            "finding_id": mom_finding.get(code),
            "mom_finding": mom_finding.get(code),
            "budget_finding": budget_finding.get(code),
            "commentary": "",
        }
        grouped.setdefault(sections.get(code, "Other"), []).append(row)

    out = []
    for name in sorted(grouped):
        rows = sorted(grouped[name], key=lambda r: -abs(r["actual"]))
        out.append({
            "label": name,
            "rows": rows,
            "total": {k: round(sum(r[k] or 0 for r in rows), 2)
                      for k in ("actual", "prior", "prior_year", "mom_var", "yoy_var")},
        })
    return {
        "id": "flux",
        "title": "Flux",
        "period": period,
        "trend_period": prior2_period if prior2 is not None else None,
        "prior_period": prior_period,
        "comparisons": [
            {"id": "mom", "label": "vs " + prior_period,
             "base": "prior", "var": "mom_var", "pct": "mom_pct"},
            {"id": "yoy", "label": "vs " + (py_period or "prior year"),
             "base": "prior_year", "var": "yoy_var", "pct": "yoy_pct"},
        ] + ([{"id": "budget", "label": "vs plan (" + (vintage or "prior") + ")",
               "base": "budget", "var": "budget_var", "pct": "budget_pct"}] if plan else []),
        "sections": out,
    }


def build_metrics(cur, prior, prior_year, period, prior_period, coupa_rows):
    def opex(book):
        return sum(v for (c, _), v in book.items() if is_pl(c))

    def unalloc(book):
        return sum(v for (c, d), v in book.items() if is_pl(c) and d == UNALLOCATED)

    now, then, year = opex(cur), opex(prior), opex(prior_year)
    metrics = [
        {"metric_id": "F0.OPEX", "title": "Total operating expense", "period": period,
         "value": round(now, 2), "unit": "usd", "population": round(now, 2), "share": None,
         "policy_basis": "Population measure, not a policy test",
         "prior_value": round(then, 2), "prior_share": None,
         "note": "vs {} {} ({}), vs prior year {}".format(
             prior_period, money(then),
             ("+" if now >= then else "") + money(now - then), money(year)),
         "top_contributors": []},
        {"metric_id": "F1.UNALLOCATED", "title": "P&L spend coded to 'Non-Specific'",
         "period": period, "value": round(unalloc(cur), 2), "unit": "usd",
         "population": round(now, 2),
         "share": (unalloc(cur) / now) if now else None,
         "policy_basis": "Global Data Entry Policy (DRAFT), department must match budget",
         "prior_value": round(unalloc(prior), 2),
         "prior_share": (unalloc(prior) / then) if then else None,
         "note": "Departmental coding is only meaningful on P&L accounts.",
         "top_contributors": []},
    ]

    if coupa_rows:
        rni = sum(num(r.get("received_not_invoiced_value")) for r in coupa_rows)
        openc = sum(num(r.get("line_total")) for r in coupa_rows
                    if str(r.get("is_open_commitment")).strip() == "1")
        no_qty = sum(1 for r in coupa_rows if num(r.get("qty")) <= 0)
        metrics.append(
            {"metric_id": "F3.RECEIVED_NOT_INVOICED",
             "title": "Received not invoiced (accrual population)", "period": period,
             "value": round(rni, 2), "unit": "usd", "population": round(now, 2),
             "share": (rni / now) if now else None,
             "policy_basis": POLICY_ACCRUAL, "prior_value": None, "prior_share": None,
             "note": ("A floor, not a total: {} PO lines carry no quantity, so their value "
                      "cannot be pro-rated.".format(no_qty)),
             "top_contributors": []})
        metrics.append(
            {"metric_id": "F4.OPEN_COMMITMENT",
             "title": "Open PO commitments (disclosure, NOT accrued)", "period": period,
             "value": round(openc, 2), "unit": "usd", "population": None, "share": None,
             "policy_basis": "Disclosure only, nothing has been received",
             "prior_value": None, "prior_share": None,
             "note": "Ordered but not yet received. No expense belongs in the period.",
             "top_contributors": []})
    return metrics


PENDING_FEEDS = {
    "accruals_log.csv": "Duplicate-accrual prevention; proposals may restate an existing accrual.",
    "prepaid_amortization_schedule.csv": "Prepaid rollforward and recode continuity.",
    "external_research_spend_detail.csv": "Unbilled WIP beyond what Coupa receipts capture.",
    "open_purchase_commitments.csv": "Non-PO commitments Coupa does not carry.",
    "payroll_register.csv": "Payroll cutoff accrual.",
    "hris_headcount.csv": "Headcount attribution for salary variances.",
    "fixed_asset_register.csv": "Depreciation continuity.",
}
FEED_VALUE_COLUMN = {
    "payroll_register.csv": "employee_id",
    "hris_headcount.csv": "employee_id",
}


def survey_pending(pending_dir):
    absent = []
    for feed, suppresses in PENDING_FEEDS.items():
        path = os.path.join(pending_dir, feed) if pending_dir else ""
        present = False
        if path and os.path.exists(path):
            column = FEED_VALUE_COLUMN.get(feed)
            with open(path, newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                if column and reader.fieldnames and column in reader.fieldnames:
                    present = any((r.get(column) or "").strip() for r in reader)
                elif not column:
                    present = any(any((c or "").strip() for c in r.values()) for r in reader)
        if not present:
            absent.append({"feed": feed, "suppresses": suppresses, "in_uc1_scope": True})
    return absent


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serif UC2 P&L flux, deterministic core.")
    parser.add_argument("--period", required=True, help='the close month, e.g. "Sep 2026"')
    parser.add_argument("--gl", nargs="+", required=True, metavar="EXPORT",
                        help="NetSuite Custom General Ledger exports (.xls), as NetSuite writes "
                             "them. Together they hold the month and the month before; the same "
                             "month last year and the six months before feed more tests")
    parser.add_argument("--coupa", help="Coupa PO line export (.csv), as Coupa writes it")
    parser.add_argument("--forecast", help="the rolling forecast workbook cut after the month "
                                           "closed (.xlsx), to reconcile the model to the ledger")
    parser.add_argument("--plan", help="the rolling forecast workbook whose PRIOR cut is the "
                                       "plan (.xlsx), for actual versus budget")
    parser.add_argument("--plan-vintage", dest="plan_vintage", default="plan",
                        help="label for the plan cut, eg 2026-06")
    parser.add_argument("--pending", help="directory of pending feed templates")
    parser.add_argument("--out", default="out", help="artifact output directory")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    period = sources.shift(args.period.strip().title(), 0)
    prior_period = sources.shift(period, -1)
    gl, gl_files = sources.read_gl(args.gl)
    canon = fold_departments(gl)
    for needed in (period, prior_period):
        if needed not in gl:
            sys.exit("{} is not in the NetSuite exports supplied. They hold: {}.".format(
                needed, ", ".join(sorted(gl, key=period_key)) or "nothing"))
    every_line = [t for lines in gl.values() for t in lines]

    cur, leaves, sections = load_activity(sources.activity(gl[period]))
    prior, leaves2, sections2 = load_activity(sources.activity(gl[prior_period]))
    leaves.update(leaves2)
    sections.update(sections2)
    py_period = sources.shift(period, -12)
    if py_period in gl:
        prior_year, leaves3, sections3 = load_activity(sources.activity(gl[py_period]))
        leaves.update(leaves3)
        sections.update(sections3)
    else:
        prior_year, py_period = {}, None

    gl_lines = gl[period]
    debit = sum(num(t["amount"]) for t in gl_lines if num(t["amount"]) > 0)
    credit = -sum(num(t["amount"]) for t in gl_lines if num(t["amount"]) < 0)
    net = debit - credit
    tie = {"passed": abs(net) < 0.01,
           "note": "Dr {} / Cr {} / net {}".format(money(debit), money(credit), money(net))}

    # PO lines ordered in the month: the receipts that may need an accrual.
    coupa_rows = []
    coupa_coverage = {"supplied": False}
    if args.coupa:
        coupa_rows = [r for r in sources.read_coupa(args.coupa) if r["period"] == period]
        coupa_coverage = {
            "supplied": True, "lines": len(coupa_rows),
            # Columns this pull lacks or leaves empty: what reads them finds nothing.
            "columns_absent": sources.coupa_rows(args.coupa)[1],
            "join_key": "supplier_name",
            "join_caveat": ("Coupa carries no NetSuite PO reference, so accrual proposals "
                            "are supplier-level. Never assert a line-level match."),
        }

    # The two cuts answer different questions. The plan is the cut made before the
    # month; the forecast cut after the month closed holds its actuals, so comparing
    # the ledger with it is a reconciliation, switched on deliberately.
    workbooks = {}

    def workbook(path, label="prior"):
        if path not in workbooks:
            workbooks[path] = sources.read_forecast(path, every_line, label)
        return workbooks[path]

    budget, budget_vintage, budget_rows = {}, "", 0
    if args.plan:
        plan_lines = workbook(args.plan, args.plan_vintage)[1]["prior"]
        budget, budget_vintage, budget_rows = load_budget(sources.aggregate(plan_lines), period)
        budget = fold_book(budget, canon)

    model, model_vintage = {}, ""
    if args.forecast:
        model_vintage, blocks = workbook(args.forecast, args.plan_vintage)
        model = fold_book(load_model_lines(blocks["current"], period), canon)

    history = {}
    for back in range(6, 0, -1):
        month = sources.shift(period, -back)
        if month in gl:
            history[month] = gl[month]

    absent_feeds = survey_pending(args.pending)
    if not args.forecast:
        absent_feeds.insert(0, {"feed": "forecast",
                                "suppresses": "Forecast vs. Actual, the model-to-ledger "
                                              "reconciliation.", "in_uc1_scope": True})
    if not args.plan:
        absent_feeds.insert(0, {"feed": "plan",
                                "suppresses": "All actual-versus-budget analysis. No conclusion "
                                              "about budget performance can be drawn.",
                                "in_uc1_scope": True})

    seq = [0]
    findings = []
    if model:
        findings += model_tie_findings(cur, model, leaves, period,
                                       model_vintage, seq)
    receipts = []
    if coupa_rows:
        receipts = accrual_findings(coupa_rows, leaves, period, seq)
        findings += receipts
    if gl_lines and history:
        findings += billing_pattern_findings(
            gl_lines, history, coupa_rows,
            [f["title"].split(":")[0] for f in receipts], leaves, period, seq)
        findings += vendor_dropped_findings(gl_lines, history, leaves, period, seq)
        findings += prepaid_findings(gl_lines, history, leaves, period, seq)
    if gl_lines:
        findings += revenue_in_expense_findings(gl_lines, leaves, period, seq)
        findings += capex_findings(gl_lines, leaves, period, seq)
    findings += variance_findings(cur, prior, prior_year, leaves, period,
                                  prior_period, py_period, gl_lines, seq,
                                  history.get(prior_period, []))
    if budget:
        findings += budget_findings(cur, budget, leaves, period,
                                    budget_vintage, gl_lines, seq)

    # Accounting before FP&A, then by size within each layer. The reviewer works
    # top to bottom, so the order in the artifact is the order of the work.
    layer_rank = {LAYER_ACCOUNTING: 0, LAYER_FPA: 1}
    findings.sort(key=lambda f: (layer_rank.get(f.get("layer"), 9),
                                 -f["amount_at_risk"]))

    # The month before the prior one, from the history, for the trend column.
    back = [p for p in sorted(history, key=period_key) if period_key(p) < period_key(prior_period)]
    prior2_period = back[-1] if back else None
    prior2 = None
    if prior2_period:
        prior2 = defaultdict(float)
        for t in history[prior2_period]:
            prior2[(t["account_code"], t["department"])] += num(t["amount"])
    flux = flux_table(cur, prior, prior_year, budget, leaves, sections,
                      period, prior_period, py_period, budget_vintage, findings,
                      prior2, prior2_period)

    # What the budget feed does not reach. Payroll and depreciation are built on
    # workbook tabs this feed does not read, so a silent absence would read as
    # "on plan" for 29% of the month.
    uncovered = {k: v for k, v in cur.items()
                 if is_pl(k[0]) and k not in budget and abs(v) >= REPORTING_FLOOR}
    budget_coverage = {
        "supplied": bool(budget),
        "vintage": budget_vintage,
        "rows_for_period": budget_rows,
        "keys_planned": len(budget),
        "keys_actual": len([k for k in cur if is_pl(k[0])]),
        "keys_unplanned": len(uncovered),
        "amount_unplanned": round(sum(uncovered.values()), 2),
        "note": ("Accounts with no plan line are NOT reported as variances. They are "
                 "uncovered by the forecast tabs this feed reads, mostly payroll and "
                 "depreciation, which are built on other tabs."),
    }

    by_sev = defaultdict(int)
    by_kind = defaultdict(int)
    for f in findings:
        by_sev[f["severity"]] += 1
        by_kind[f["kind"]] += 1

    # Every file that changes a finding is fingerprinted, so it moves the run id.
    inputs = []
    files = [(f["path"], f["rows"], ["netsuite_gl"]) for f in gl_files]
    if args.coupa:
        files.append((args.coupa, len(coupa_rows), ["coupa"]))
    for path in workbooks:
        roles = [r for r, given in (("forecast", args.forecast), ("plan", args.plan)) if given == path]
        files.append((path, sum(len(v) for v in workbooks[path][1].values()), roles))
    for path, rows, roles in files:
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        inputs.append({"path": os.path.basename(path), "rows": rows, "roles": roles,
                       "sha256": digest, "bytes": os.path.getsize(path),
                       "source_dir": os.path.dirname(os.path.abspath(path))})

    run = {
        "manifest": {
            # The engine, the ruleset, the period and the input fingerprints, and not
            # where the files sit, so a Project run and a local run of the same
            # exports share one id.
            "run_id": hashlib.sha256("|".join(
                [ENGINE_VERSION, RULESET_VERSION, period]
                + sorted(i["sha256"] for i in inputs)).encode()).hexdigest()[:16],
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "engine_version": ENGINE_VERSION,
            "ruleset_version": RULESET_VERSION,
            "period": period, "prior_period": prior_period, "prior_year_period": py_period,
            "entity": ENTITY, "inputs": inputs,
            "absent_feeds": absent_feeds,
            "tie_out": tie,
            "coupa_coverage": coupa_coverage,
            "budget_coverage": budget_coverage,
        },
        "summary": {
            "finding_count": len(findings),
            "by_severity": {k: by_sev.get(k, 0) for k in ("high", "medium", "low", "info")},
            "by_kind": dict(by_kind),
            "amount_at_risk": round(sum(f["amount_at_risk"] for f in findings), 2),
            "metric_count": 0,
            "feeds_absent": len(absent_feeds),
            "vendors_needing_ratification": 0,
        },
        "findings": findings,
        "tables": [flux],
        "bills_to_balance_sheet": bills_to_balance_sheet(gl_lines),
        "metrics": build_metrics(cur, prior, prior_year, period, prior_period, coupa_rows),
        "report": {
            "title": "P&L Flux",
            "slug": "pl-flux",
            # A variance is graded by size alone. The default is the policy's
            # pre-close adjustment threshold; the presets bracket it so the
            # reviewer can see what a tighter or looser number would catch.
            "fix_threshold": PRE_CLOSE_ADJUSTMENT,
            "fix_threshold_presets": [REPORTING_FLOOR, PRE_CLOSE_ADJUSTMENT,
                                      25_000.0, POST_CLOSE_QUARTERLY],
            "reporting_floor": REPORTING_FLOOR,
            "band_labels": ["Needs commentary", "Below the commentary threshold"],
            # Variance is tested per account, the line commentary is written on.
            # Its evidence breaks the move out by department.
            "dimensions": [
                ["Account", "tested",
                 "Every P&L account against the prior month, the prior year and plan."],
                ["Department", "tested",
                 "Each account's move broken out by department in its evidence."],
                ["Project", "not applicable", "Serif does not code projects."],
                ["Entity", "not applicable", "The ledger has one legal entity."],
            ],
            "subtitle": ("Variance arithmetic and accrual evidence, computed deterministically "
                         "from Serif's period activity and Coupa receipts. Commentary on any "
                         "line is a human or model judgment and is not produced here."),
            # Review runs in two passes. Accounting settles the ledger, then FP&A
            # reads it against plan. Each group declares its layer so the console
            # can order the work rather than presenting one undifferentiated list.
            "layers": [
                {"id": LAYER_ACCOUNTING, "label": "Adjustments", "order": 1,
                 "why": ("Does the ledger agree with itself and with the other systems "
                         "of record? Everything here ends in an entry booked or not.")},
                {"id": LAYER_FPA, "label": "Variance review", "order": 2,
                 "why": ("With the ledger settled, how does the period compare to what "
                         "was planned?")},
            ],
            "groups": [
                {"id": "model", "label": "Forecast vs. Actual", "layer": LAYER_ACCOUNTING,
                 "rules": ["F5.MODEL_TIE"],
                 "why": ("The CURRENT forecast vintage against the ledger. Its closed "
                         "months hold the posted actuals, so the two should agree; where "
                         "they do not, an entry sits in the model that the ledger never "
                         "received, or the reverse. Lines carrying no vendor and no PO "
                         "are manual overlays. This is a reconciliation, not a measure of "
                         "performance against plan.")},
                {"id": "accrual", "label": "Accrual Proposals", "layer": LAYER_ACCOUNTING,
                 "rules": ["F3.ACCRUAL_RECEIPT", "F6.ACCRUAL_PATTERN"],
                 "why": ("Goods received but not yet invoiced. Expense belongs in this period. "
                         "Open PO commitments are NOT included, nothing has been received "
                         "against them.")},
                {"id": "prepaid", "label": "Prepaids and Capital", "layer": LAYER_ACCOUNTING,
                 "rules": ["F9.PREPAID", "F10.CAPITALIZE"],
                 "why": ("Charges expensed in the month that pay for future months, and "
                         "purchases on the accounts the asset policy names for "
                         "capitalization review.")},
                {"id": "reclass", "label": "Reclassifications", "layer": LAYER_ACCOUNTING,
                 "rules": ["F7.REVENUE_IN_EXPENSE", "F8.VENDOR_DROPPED"],
                 "why": ("Entries in the wrong kind of account, and recurring entries that "
                         "lost their vendor.")},
                {"id": "variance", "label": "Actual vs. Actual", "layer": LAYER_FPA,
                 "rules": ["F1.VARIANCE"],
                 "why": ("Movement against the prior month, per account. The prior year "
                         "shows for context. Name the driver. An entry is only needed if the "
                         "period is misstated.")},
                {"id": "budget", "label": "Actual vs. Budget", "layer": LAYER_FPA,
                 "rules": ["F2.BUDGET"],
                 "why": ("Actuals against the PRIOR forecast vintage, cut before the month "
                         "began, which is what makes it a measure of performance rather "
                         "than a reconciliation. Accounts the forecast never planned are "
                         "excluded rather than reported as overspend; see budget coverage "
                         "in the run record.")},
            ],
        },
    }
    run["summary"]["metric_count"] = len(run["metrics"])

    out_dir = os.path.join(args.out, period.replace(" ", "").lower())
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "run.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(run, handle, indent=2, ensure_ascii=False)

    if not args.quiet:
        bar = "-" * 72
        print(bar)
        print("SERIF UC2 P&L FLUX - " + period)
        print("Entity: " + ENTITY)
        print(bar)
        for item in inputs:
            print("  {:<46}{:>8,} rows".format(item["path"], item["rows"]))
        print("\nTIE-OUT  {}   {}".format("PASS" if tie["passed"] else "FAIL", tie["note"]))
        absent = run["manifest"]["absent_feeds"]
        if absent:
            print("\nFEEDS ABSENT ({}) - their analysis is suppressed, not clean:".format(len(absent)))
            for feed in absent:
                print("    " + feed["feed"])
        print("\nFINDINGS  {}   High {} - Medium {}".format(
            len(findings), by_sev.get("high", 0), by_sev.get("medium", 0)))
        print("AMOUNT AT RISK  " + money(run["summary"]["amount_at_risk"]))
        if coupa_rows:
            rni = sum(num(r.get("received_not_invoiced_value")) for r in coupa_rows)
            openc = sum(num(r.get("line_total")) for r in coupa_rows
                        if str(r.get("is_open_commitment")).strip() == "1")
            print("\nACCRUAL POPULATION  {}   (open commitments {}, NOT accrued)".format(
                money(rni), money(openc)))
        print("\nWrote " + path)
        print("Next: python3 serif_views.py " + path + ", then build_pages.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
