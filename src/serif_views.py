#!/usr/bin/env python3
"""Add the controller's tables to a run artifact, deterministically.

    python3 serif_views.py <run.json> --gl <NetSuite GL export.xls> [...]
        [--plan <rolling forecast.xlsx> --plan-vintage 2026-06]
        [--coupa <Coupa PO export.csv>] [--roster <UKG roster.csv>]
        [--balance-sheet <NetSuite Balance Sheet report.xls>]

Runs between the engine and the console. The engine decides what is an exception;
this step lays the period out the way a controller reads it, as schedules:

  vendors        GL coding: every vendor billed this month, three months by account
                 and by department, with what needs a look flagged on the row
  checks         GL coding: posting lag and tax findings, one line each
  payroll_hris   both: salaries by department against UKG
  dept_plan      P&L flux: plan against actual by department, then account
  model_tie      P&L flux: the forecast-vs-ledger reconciliation
  accrual        P&L flux: the accrual schedule
  prepaid        P&L flux: prepaids and capital
  reclass        P&L flux: entries in the wrong place
  entries        every proposed correction as Journal Entry lines

Beside the schedules, for the P&L flux: dept_months (spend by department, this
month and last, with its accounts), payroll (employee expense by department, a
with UKG headcount) and, with --balance-sheet,
balance_sheet (the NetSuite report, laid out for review; no test runs on it).

The vendor flags reuse the flux engine's prepaid and capital screens, imported
from serif_uc2_flux.py beside this file, so the two consoles apply one rule.

Every input is a system export as the system writes it. The month, the two
before it and the same month last year are taken from the NetSuite exports, and
the plan from the forecast workbook, by serif_sources.py.

Every figure is read from an input file or from a finding. Nothing is estimated,
and no row is produced for a comparison whose input was not supplied: the table
says which input it needs instead.

The console renders these tables and computes nothing from them.

Stdlib only. Python 3.9+. Idempotent: rerunning replaces the `views` block.

PERSONAL DATA. The UKG roster carries names, email addresses and salaries. It is
read here only to resolve a person to a department. No name, email address or
salary is written to the artifact, and nothing is printed.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import defaultdict

import serif_sources as sources

VIEWS_VERSION = "1.7.1"

# The flux engine's definition, so the two agree on what counts as P&L.
PL_PREFIXES = ("6", "7", "8")
# A vendor posting to a planned account with no vendor plan line is listed only
# above this. Matches the engines' reporting floor. Which rows need action is
# decided in the console, against the reviewer's own threshold.
FLOOR = 2500.0
# Serif's PP&E capitalization threshold (12 Oct 2026), the flux engine's
# CAPITALIZATION_THRESHOLD. A capital flag under it says so, and the P&L Flux
# proposes no Journal Entry for it.
CAPITALIZATION = 5000.0
# Serif's prepaid threshold (12 Oct 2026), the flux engine's PREPAID_THRESHOLD. The
# prepaid screen lists from the reporting floor; a flag under this says so, and the
# P&L Flux proposes no Journal Entry for it.
PREPAID = 25000.0

AP_ACCOUNT = "2000100"

# The ten department names the ledger uses.
GL_DEPARTMENTS = {"Non-Specific", "Platform", "General R&D", "Production", "General G&A",
                  "Biology", "Chemistry", "In Vivo", "Finance", "Computational Sciences"}
# A new balance sheet line on a proposed Journal Entry takes this department; only income
# statement lines carry one. A line that reverses the ledger line being corrected
# (`reverses_line`) keeps that line's. Balance sheet accounts are 1xxxxxx to 3xxxxxx.
BS_DEPARTMENT = "Non-Specific"


def is_bs(code):
    return bool(code) and code[0] in "123"


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Suffixes dropped before comparing a forecast vendor to a ledger vendor.
VENDOR_SUFFIXES = {"inc", "llc", "ltd", "corp", "corporation", "co", "company",
                   "lp", "llp", "plc", "gmbh", "ab", "sa", "ag", "bv", "the"}


def is_pl(code):
    return bool(code) and code[0] in PL_PREFIXES


def num(value):
    if value is None:
        return 0.0
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text or text in ("-", "None"):
        return 0.0
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        return float(text)
    except ValueError:
        return 0.0


def r2(value):
    return round(value + 0.0, 2)


def pct(delta, base):
    """Percent of the base's size, so the sign always follows the variance.
    Dividing by a negative base flips the sign and contradicts the subtotal."""
    return round(delta / abs(base) * 100, 1) if base else None


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def norm_vendor(name):
    text = (name or "").lower().replace("&", " and ")
    tokens = re.sub(r"[^a-z0-9 ]", " ", text).split()
    while tokens and tokens[-1] in VENDOR_SUFFIXES:
        tokens.pop()
    while tokens and tokens[0] == "the":
        tokens.pop(0)
    return " ".join(tokens)


def next_period_start(period):
    """'Aug 2026' -> '2026-09-01', the date an accrual reverses."""
    try:
        mon, year = period.split()
        index = MONTHS.index(mon[:3])
    except (ValueError, AttributeError):
        return ""
    year = int(year) + (1 if index == 11 else 0)
    return "%04d-%02d-01" % (year, (index + 1) % 12 + 1)


def period_end(period):
    try:
        mon, year = period.split()
        index = MONTHS.index(mon[:3])
    except (ValueError, AttributeError):
        return ""
    days = [31, 29 if int(year) % 4 == 0 else 28, 31, 30, 31, 30,
            31, 31, 30, 31, 30, 31][index]
    return "%s-%02d-%02d" % (year, index + 1, days)


# ---------------------------------------------------------------- inputs

class Inputs:
    """Every file read, fingerprinted, so the Build record can name it."""

    def __init__(self):
        self.files = []

    def add(self, role, path, rows):
        self.files.append({"role": role, "path": os.path.basename(path),
                           "rows": rows, "sha256": sha256(path)})


def load_gl(rows):
    out = []
    for row in rows:
        amount = num(row.get("amount"))
        if not amount:
            amount = num(row.get("debit")) - num(row.get("credit"))
        out.append({
            "period": row.get("period", ""),
            "date": row.get("date", ""),
            "txn_type": row.get("txn_type", ""),
            "document_number": row.get("document_number", ""),
            "vendor": (row.get("vendor_or_name") or "").strip(),
            "account_code": (row.get("account_code") or "").strip(),
            "account_leaf": (row.get("account_leaf") or "").strip(),
            "account_path": (row.get("account_path") or "").strip(),
            "department": (row.get("department") or "").strip(),
            "project": (row.get("project") or "").strip(),
            "program": (row.get("program") or "").strip(),
            "description": (row.get("description") or "").strip(),
            "memo": (row.get("memo") or "").strip(),
            "amount": amount,
            "internal_id": row.get("internal_id", ""),
            "coupa_url": row.get("coupa_url", ""),
            "coupa_po": row.get("coupa_po", ""),
        })
    return out


def account_book(*line_sets, extra=()):
    """code -> {name, parent}. The name is the leaf; the parent is the next level
    up the NetSuite path, which is what a controller reads the leaf under."""
    book = {}
    for lines in line_sets:
        for line in lines:
            code = line.get("account_code")
            if not code or code in book:
                continue
            leaf = line.get("account_leaf") or ""
            parent = ""
            parts = [p.strip() for p in (line.get("account_path") or "").split(":") if p.strip()]
            if len(parts) >= 2:
                parent = re.sub(r"^\d+\s*-\s*", "", parts[-2])
            if not leaf and parts:
                leaf = re.sub(r"^\d+\s*-\s*", "", parts[-1])
            book[code] = {"name": leaf, "parent": parent}
    for code, leaf in extra:
        if code and code not in book and leaf:
            book[code] = {"name": leaf, "parent": ""}
    return book


def load_roster(path, inputs):
    """-> ((first, last) -> department, Coupa code -> department, staff).
    Names and salaries stay in memory: the payroll check reduces staff to
    department totals, and nothing per person is written."""
    if not path:
        return {}, {}, []
    rows = read_csv(path)
    inputs.add("hris_roster", path, len(rows))
    people, codes = {}, {}
    staff = []
    for row in rows:
        dept = (row.get("Department") or "").strip()
        # Kept in memory for the payroll check and reduced to department totals
        # there; nothing per person leaves this function in the artifact.
        staff.append({"department": dept, "type": (row.get("Employee Type") or "").strip(),
                      "hired": (row.get("Last Hire Date") or "")[:10],
                      "salary": num(row.get("Annual Salary")),
                      # Written only with --keep-names, for the roster detail.
                      "name": " ".join(x for x in ((row.get("First Name") or "").strip(),
                                                   (row.get("Last Name") or "").strip()) if x),
                      "title": (row.get("Job Title") or "").strip(),
                      "bonus_pct": num(row.get("2025 Bonus %"))})
        first = (row.get("First Name") or "").strip().lower()
        last = (row.get("Last Name") or "").strip().lower()
        if first and last and dept:
            people[(first, last)] = dept
        code = (row.get("Department Code") or "").strip()
        match = re.match(r"^[A-Z]+(\d+)$", code)
        if match and dept:
            codes.setdefault(match.group(1), defaultdict(int))[dept] += 1
    # A code resolves only if every person carrying it sits in one department.
    mapping = {}
    for code, depts in codes.items():
        if len(depts) == 1:
            mapping[code] = {"department": next(iter(depts)),
                             "source": "UKG department code, numeric part"}
    return people, mapping, staff


def person_key(name):
    tokens = re.sub(r"[^a-z ]", " ", (name or "").lower()).split()
    return (tokens[0], tokens[-1]) if len(tokens) >= 2 else None


# ---------------------------------------------------------------- coding

def codings(lines):
    """vendor -> {(account, dept): [amount, lines]} over P&L lines carrying a vendor."""
    out = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
    for line in lines:
        if not line["vendor"] or not is_pl(line["account_code"]):
            continue
        # An expense report's "vendor" is the employee who submitted it. A person
        # is not a vendor with a coding convention, and the name stays out of a
        # vendor schedule. Expense reports are read by department instead, in the
        # requester schedule.
        if line["txn_type"] == "Expense Report":
            continue
        cell = out[line["vendor"]][(line["account_code"], line["department"])]
        cell[0] += line["amount"]
        cell[1] += 1
    return out


def coding_list(cells):
    """Largest first, so the vendor's usual coding leads."""
    items = sorted(cells.items(), key=lambda kv: -abs(kv[1][0]))
    return [{"account": k[0], "department": k[1], "amount": r2(v[0]), "lines": v[1]}
            for k, v in items if abs(v[0]) >= 0.005 or v[1]]


# The findings that sit on a vendor row: the ones about how a vendor's spend is
# coded. A posting-lag or tax finding on the same vendor is a different question
# and stays on Ledger checks.
CODING_RULES = ("T1.DEPT_INCONSISTENCY", "T4.PO_ACCOUNT_MISMATCH", "T2.UNALLOCATED")


def link_for(links, vendor, cells):
    """The coding finding behind any of a row's codings, or none."""
    for cell in cells:
        hit = links.get((vendor, cell["account"], cell["department"]))
        if hit:
            return hit
    return None


# Combining marks and zero-width characters count as part of an address, so one
# placed inside it does not split it and leave the rest behind. Each part is
# capped at the length an address allows, which keeps the match linear on long
# runs of text with no @ in them.
_EMAIL_MARKS = "\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f\u200b-\u200d\u2060\ufeff"
EMAIL = re.compile(r"[\w.+%s-]{1,64}@[%s]*[\w%s-]{1,63}(?:\.[\w%s-]{1,63}){1,8}"
                   % ((_EMAIL_MARKS,) * 4))


def lines_for(lines, vendor=None, account=None, department=None, cap=12, blank=False):
    """The ledger lines behind a schedule row, largest first, so a reader can see
    what was bought without leaving the table. Email addresses are removed from
    memo text: expense-report memos carry the submitter's."""
    picked = [l for l in lines if is_pl(l["account_code"])
              and (vendor is None or l["vendor"] == vendor)
              and (account is None or l["account_code"] == account)
              and (department is None or l["department"] == department)
              and l["txn_type"] != "Expense Report"]
    picked.sort(key=lambda l: -abs(l["amount"]))
    out = {"count": len(picked), "items": [{
        "date": l["date"], "document": l["document_number"], "type": l["txn_type"],
        "vendor": l["vendor"], "account": l["account_code"], "department": l["department"],
        "project": l.get("project", ""), "program": l.get("program", ""),
        "text": EMAIL.sub("[email removed]", l.get("description") or l.get("memo") or "").strip()[:140],
        "amount": r2(l["amount"])} for l in picked[:cap]]}
    if blank:
        # A line with no description is where the invoice has to be read.
        out["blank"] = sum(1 for l in picked if not (l.get("description") or l.get("memo") or "").strip())
    return out


def plan_lines_for(plan_rows, period):
    """The forecast's vendor-level lines for the period, from the vintage supplied."""
    return [r for r in plan_rows if r.get("period") == period and is_pl(r.get("account_code", ""))]


def match_vendors(plan_names, ledger_names):
    """Forecast vendor text -> ledger vendor, on the normalized name. Exact, or
    one a whole-word prefix of the other. Anything ambiguous stays unmatched."""
    by_norm = defaultdict(list)
    for name in ledger_names:
        by_norm[norm_vendor(name)].append(name)
    out = {}
    for raw in plan_names:
        key = norm_vendor(raw)
        if not key:
            continue
        hits = by_norm.get(key, [])
        if len(hits) != 1:
            hits = [n for k, names in by_norm.items() if k and (
                k.startswith(key + " ") or key.startswith(k + " ")) for n in names]
        if len(set(hits)) == 1:
            out[raw] = hits[0]
    return out


def vendor_plan(current, plan_rows, period, vintage, links, universe=()):
    lines = plan_lines_for(plan_rows, period)
    cur = codings(current)
    planned = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
    plan_text = defaultdict(set)
    plan_names = sorted({(r.get("vendor") or "").strip() for r in lines if (r.get("vendor") or "").strip()})
    # Matched against every vendor the ledger knows, not only this month's, so a
    # planned vendor that posted nothing lands under 'planned, nothing posted'
    # rather than among the unmatched.
    matched = match_vendors(plan_names, sorted(set(cur) | set(universe)))
    unmatched_refs, unmatched_amt = [], 0.0
    for row in lines:
        raw = (row.get("vendor") or "").strip()
        amount = num(row.get("amount"))
        if raw and raw in matched:
            cell = planned[matched[raw]][(row["account_code"], row.get("department", ""))]
            cell[0] += amount
            cell[1] += 1
            plan_text[matched[raw]].add(raw)
        elif raw and amount:
            unmatched_refs.append(row.get("line_ref", ""))
            unmatched_amt += amount
    planned_accounts = {r["account_code"] for r in lines}
    rows = {"differs": [], "no_spend": [], "as_planned": [], "unplanned": []}
    for vendor in sorted(set(planned) | set(cur), key=str.lower):
        plan_cells = planned.get(vendor, {})
        act_cells = cur.get(vendor, {})
        plan_amt = sum(v[0] for v in plan_cells.values())
        act_amt = sum(v[0] for v in act_cells.values())
        if plan_cells:
            off = [k for k in act_cells if k not in plan_cells and abs(act_cells[k][0]) >= 0.005]
            if not act_cells:
                status = "no_spend"
            elif off:
                status = "differs"
            else:
                status = "as_planned"
            off_amt = sum(act_cells[k][0] for k in off)
        else:
            # A vendor posting to an account the forecast plans, with no line of its
            # own. The forecast covers external spend only, so this is a coverage
            # question, not an overspend.
            in_scope = {k: v for k, v in act_cells.items() if k[0] in planned_accounts}
            if not in_scope:
                continue
            act_cells = in_scope
            act_amt = sum(v[0] for v in act_cells.values())
            if abs(act_amt) < FLOOR:
                continue
            status, off_amt = "unplanned", act_amt
        rows[status].append({
            "vendor": vendor,
            # The forecast's own wording where it differs from the ledger's, so a
            # reviewer can judge a match made on the name rather than take it.
            "plan_vendor": sorted(t for t in plan_text.get(vendor, ()) if t != vendor),
            "planned": coding_list(plan_cells),
            "current": coding_list(act_cells),
            "plan": r2(plan_amt), "amount": r2(act_amt),
            "variance": r2(act_amt - plan_amt), "off_plan": r2(off_amt),
            "status": status,
            "detail": lines_for(current, vendor),
            "finding_id": link_for(links, vendor, coding_list(act_cells)),
        })
    for key in rows:
        rows[key].sort(key=lambda r: -max(abs(r["variance"]), abs(r["off_plan"])))
    labels = {"differs": "Coded differently from plan", "no_spend": "Planned, nothing posted",
              "as_planned": "Coded as planned",
              "unplanned": "Posted to a planned account with no vendor plan line"}
    return {
        "id": "vendor_plan", "kind": "vendor_plan",
        "title": "Vendor Coding vs. Plan",
        "periods": {"current": period, "plan": vintage},
        "sections": [{"id": k, "label": labels[k], "rows": rows[k],
                      "plan_total": r2(sum(r["plan"] for r in rows[k])),
                      "total": r2(sum(r["amount"] for r in rows[k]))}
                     for k in ("differs", "no_spend", "unplanned", "as_planned") if rows[k]],
        "unmatched": {"lines": len(unmatched_refs), "amount": r2(unmatched_amt),
                      "refs": unmatched_refs},
        "note": ("Plan from the %s forecast vintage's vendor lines. The forecast plans "
                 "external spend and overhead only, so payroll and depreciation have no "
                 "vendor line. Forecast vendors are matched to ledger vendors on the "
                 "normalized name; lines that do not match are counted below, by "
                 "workbook cell, rather than guessed." % vintage),
    }


def dept_plan(current, budget_rows, period, vintage):
    plan = defaultdict(float)
    for row in budget_rows:
        if row.get("period") == period and is_pl(row.get("account_code", "")):
            plan[(row.get("department", ""), row["account_code"])] += num(row.get("budget_amount"))
    actual = defaultdict(float)
    for line in current:
        if is_pl(line["account_code"]):
            actual[(line["department"], line["account_code"])] += line["amount"]
    depts = defaultdict(list)
    for key in sorted(set(plan) | set(actual)):
        dept, code = key
        has_plan = key in plan
        p, a = plan.get(key, 0.0), actual.get(key, 0.0)
        if not has_plan and abs(a) < 0.005:
            continue
        var = a - p if has_plan else None
        depts[dept or "No department"].append({
            "account": code, "plan": r2(p) if has_plan else None, "amount": r2(a),
            "detail": lines_for(current, None, code, dept),
            "variance": r2(var) if var is not None else None,
            "pct": pct(var, p) if has_plan else None,
            "status": ("no_plan" if not has_plan else
                       "no_spend" if abs(a) < 0.005 else "planned"),
        })
    sections = []
    for dept, rows in depts.items():
        rows.sort(key=lambda r: (r["plan"] is None, -abs(r["variance"] or r["amount"])))
        planned = [r for r in rows if r["plan"] is not None]
        p = sum(r["plan"] for r in planned)
        a = sum(r["amount"] for r in planned)
        sections.append({
            "id": dept, "label": dept, "rows": rows,
            "plan_total": r2(p), "total": r2(a), "variance": r2(a - p),
            "pct": pct(a - p, p),
            "unplanned_total": r2(sum(r["amount"] for r in rows if r["plan"] is None)),
        })
    sections.sort(key=lambda s: -abs(s["variance"]))
    return {
        "id": "dept_plan", "kind": "dept_plan",
        "title": "Department vs. Plan",
        "periods": {"current": period, "plan": vintage},
        "sections": sections,
        "note": ("Plan from the %s forecast vintage, which predates the month. A "
                 "department's plan, actual and variance cover its planned accounts. "
                 "Accounts the forecast does not plan are listed with no plan figure and "
                 "totalled separately, because a partial plan totalled against a full "
                 "actual would read as an overspend." % vintage),
    }


def requester(current, coupa_rows, period, people, dept_codes):
    """Who raised it, against where it was charged. Department level only."""
    po = defaultdict(lambda: [0.0, 0])
    unknown = [0.0, 0]
    for row in coupa_rows:
        if row.get("period") != period:
            continue
        name = row.get("requester") or ""
        dept = people.get(person_key(name))
        coded = dept_codes.get(row.get("dept_code", ""), {}).get("department", "")
        coded_label = coded or ("Coupa department %s (unmapped)" % row.get("dept_code", "")
                                if row.get("dept_code") else "")
        if not dept:
            unknown[0] += row["amount"]
            unknown[1] += 1
            continue
        cell = po[(row["supplier"], dept, coded_label, row.get("account", ""))]
        cell[0] += row["amount"]
        cell[1] += 1
    po_rows = []
    for (supplier, dept, coded, account), (amount, count) in po.items():
        po_rows.append({
            "vendor": supplier, "requester_department": dept, "coded_department": coded,
            "account": account, "amount": r2(amount), "lines": count,
            "status": "agrees" if dept == coded else "differs",
        })
    er = defaultdict(lambda: [0.0, 0])
    er_unknown = [0.0, 0]
    for line in current:
        if line["txn_type"] != "Expense Report" or not is_pl(line["account_code"]):
            continue
        dept = people.get(person_key(line["vendor"]))
        if not dept:
            er_unknown[0] += line["amount"]
            er_unknown[1] += 1
            continue
        cell = er[(dept, line["department"], line["account_code"])]
        cell[0] += line["amount"]
        cell[1] += 1
    er_rows = [{
        "vendor": "Expense reports", "requester_department": dept,
        "coded_department": coded, "account": account,
        "amount": r2(amount), "lines": count,
        "status": "agrees" if dept == coded else "differs",
    } for (dept, coded, account), (amount, count) in er.items()]
    for rows in (po_rows, er_rows):
        rows.sort(key=lambda r: (r["status"] != "differs", -abs(r["amount"])))
    sections = []
    if po_rows:
        sections.append({"id": "po", "label": "Purchase orders raised in %s" % period,
                         "rows": po_rows, "total": r2(sum(r["amount"] for r in po_rows))})
    if er_rows:
        sections.append({"id": "er", "label": "Expense reports posted in %s" % period,
                         "rows": er_rows, "total": r2(sum(r["amount"] for r in er_rows))})
    return {
        "id": "requester", "kind": "requester",
        "title": "Requester vs. Coding",
        "periods": {"current": period},
        "sections": sections,
        "unmatched": {"po_lines": unknown[1], "po_amount": r2(unknown[0]),
                      "er_lines": er_unknown[1], "er_amount": r2(er_unknown[0])},
        "note": ("The requester's department is the one UKG records today, which may "
                 "differ from the department at the time of purchase. A difference is "
                 "not an error on its own: people buy for other departments. It is where "
                 "to look first when a department's spend is in question. Coupa "
                 "department codes are read through UKG's department codes."),
    }


def load_coupa(path, inputs):
    """Coupa PO line export -> {period, supplier, requester, dept_code, account, amount}."""
    if not path:
        return []
    rows = sources.coupa_rows(path)[0]
    inputs.add("coupa", path, len(rows))
    out = []
    for row in rows:
        parts = (row.get("Account") or "").split("-")
        date = (row.get("Order Date (Header)") or "").strip()
        period = ""
        match = re.match(r"^(\d{4})-(\d{2})", date) or re.match(r"^(\d{1,2})/\d{1,2}/(\d{4})", date)
        if match:
            if "-" in date[:5]:
                period = "%s %s" % (MONTHS[int(match.group(2)) - 1], match.group(1))
            else:
                period = "%s %s" % (MONTHS[int(match.group(1)) - 1], match.group(2))
        out.append({
            "period": period,
            # The raw export appends "(name|id|type)" to the supplier name.
            "supplier": re.sub(r"\s*\([^()]*\|[^()]*\)\s*$", "",
                               (row.get("Supplier") or "").strip()),
            "requester": row.get("Requested By (Header)") or row.get("Created By") or "",
            "dept_code": parts[2].strip() if len(parts) > 2 else "",
            "account": parts[1].strip() if len(parts) > 1 else "",
            "amount": num(row.get("Line Total")),
            "po_number": (row.get("PO Number (Header)") or "").strip(),
            "po_id": (row.get("PO ID") or "").strip(),
        })
    return out


# ---------------------------------------------------------------- flux schedules

def model_tie(findings):
    rows = []
    for f in findings:
        if f.get("rule_id") != "F5.MODEL_TIE":
            continue
        subject = (f.get("correction") or {}).get("subject", "")
        code = subject.split(" ")[0] if subject[:1].isdigit() else ""
        dept = (f.get("title") or "").split(":")[0].split(" / ")[-1].strip()
        lines = f.get("model_lines") or []
        overlay = [l for l in lines if not l.get("vendor") and not l.get("po_number")]
        rows.append({
            "finding_id": f["finding_id"], "account": code, "department": dept,
            "ledger": r2(f.get("actual_amount") or 0), "model": r2(f.get("model_amount") or 0),
            "difference": r2((f.get("model_amount") or 0) - (f.get("actual_amount") or 0)),
            "staged_as": "; ".join(sorted({l.get("description") for l in overlay
                                           if l.get("description")})),
            "overlay": bool(overlay),
            "model_lines": [{"ref": l.get("line_ref", ""), "vendor": l.get("vendor", ""),
                             "po": l.get("po_number", ""), "description": l.get("description", ""),
                             "amount": r2(l.get("amount") or 0)} for l in lines],
        })
    rows.sort(key=lambda r: -abs(r["difference"]))
    if not rows:
        return None
    return {"id": "model_tie", "kind": "model_tie", "title": "Forecast vs. Actual",
            "group": "model",
            "sections": [{"id": "all", "label": "Model and ledger disagree", "rows": rows,
                          "total": r2(sum(r["difference"] for r in rows))}],
            "note": ("The current forecast vintage against the ledger. Its closed months "
                     "hold the posted actuals, so the two should agree. A model line with "
                     "no vendor and no PO is a manual overlay.")}


def po_departments(coupa_rows, dept_codes):
    """PO number -> the department its lines were coded to in Coupa, read through
    UKG's department codes. A PO split across departments resolves to none."""
    seen = defaultdict(set)
    for row in coupa_rows:
        if row.get("po_number") and row.get("dept_code"):
            seen[row["po_number"]].add(row["dept_code"])
    out = {}
    for po, codes in seen.items():
        if len(codes) == 1:
            code = next(iter(codes))
            out[po] = (dept_codes.get(code) or {}).get("department") or (
                "Coupa department %s (unmapped)" % code)
    return out


def accrual_schedule(findings, period, po_depts=None):
    po_depts = po_depts or {}
    rows = []
    for f in findings:
        if f.get("rule_id") not in ("F3.ACCRUAL_RECEIPT", "F6.ACCRUAL_PATTERN"):
            continue
        entry = parse_entry((f.get("correction") or {}).get("entry", ""))
        debit = next((l for l in entry if l["debit"]), {})
        credit = next((l for l in entry if l["credit"]), {})
        supplier = (f.get("title") or "").split(":")[0].strip()
        subject = (f.get("correction") or {}).get("subject", "")
        pos = re.findall(r"FL\d+", (f.get("evidence") or {}).get("basis", ""))
        depts = {po_depts[p] for p in pos if p in po_depts}
        pattern = f["rule_id"] == "F6.ACCRUAL_PATTERN"
        rows.append({
            "finding_id": f["finding_id"], "vendor": supplier,
            "method": "pattern" if pattern else "receipt",
            "account": debit.get("account", ""), "credit_account": credit.get("account", ""),
            "department": debit.get("department", "") if pattern else (
                next(iter(depts)) if len(depts) == 1 else ""),
            "po_numbers": pos,
            "support": (f.get("evidence") or {}).get("basis", ""),
            "evidence": (f.get("evidence") or {}).get("observed", ""),
            "amount": r2(f.get("amount_at_risk") or 0),
            "reverses": next_period_start(period),
            "confidence": f.get("confidence"),
            "subject": subject,
        })
    rows.sort(key=lambda r: -abs(r["amount"]))
    if not rows:
        return None
    sections = []
    for method, label in (("receipt", "Received in %s, not yet invoiced" % period),
                          ("pattern", "Billed in recent months, not in %s" % period)):
        part = [r for r in rows if r["method"] == method]
        if part:
            sections.append({"id": method, "label": label, "rows": part,
                             "total": r2(sum(r["amount"] for r in part))})
    return {"id": "accrual", "kind": "accrual", "title": "Accrual Proposals", "group": "accrual",
            "sections": sections,
            "note": ("Goods received in Coupa and not yet invoiced. The value is pro-rated "
                     "from the PO line total, and lines with no quantity cannot be "
                     "pro-rated, so the total is a floor. Open commitments, ordered and not "
                     "received, are not accrued.")}


# Paid through AP, not payroll, so not in the salary line.
NOT_PAYROLL = ("Consultant (Contract)", "Contractor (Via Agency)")
# A department total over fewer people than this would disclose someone's pay.
MIN_CELL = 3


def payroll_hris(current, staff, period):
    """Salary expense by department in the ledger against what UKG says the
    department's people are paid, a month at a time. Payroll is booked by
    department in one journal, so this is where miscoded payroll shows: a
    department carrying pay for people UKG places elsewhere.

    UKG's figure is annual salary over twelve for everyone on payroll and hired
    by the period end. The roster is today's, so leavers since are missing and a
    raise since shows early. A department of fewer than three people shows its
    headcount only."""
    end = period_end(period)
    heads = defaultdict(lambda: [0, 0.0])
    for p in staff:
        if p["type"] in NOT_PAYROLL or not p["department"]:
            continue
        if p["hired"] and end and p["hired"] > end:
            continue
        heads[p["department"]][0] += 1
        heads[p["department"]][1] += p["salary"] / 12.0
    ledger = defaultdict(float)
    for l in current:
        if l["account_code"] == "6101000":
            ledger[l["department"] or "No department"] += l["amount"]
    rows = []
    for dept in sorted(set(heads) | set(ledger)):
        n, run = heads.get(dept, [0, 0.0])
        gl = ledger.get(dept, 0.0)
        small = 0 < n < MIN_CELL
        if not n:
            status = "not_in_hris"
        elif not gl:
            status = "not_in_ledger"
        elif small:
            status = "withheld"
        else:
            status = "compare"
        diff = None if (small or not n) else gl - run
        rows.append({"department": dept, "headcount": n,
                     "hris": None if (small or not n) else r2(run),
                     "amount": r2(gl), "variance": r2(diff) if diff is not None else None,
                     "pct": pct(diff, run) if diff is not None and run else None,
                     "status": status, "detail": lines_for(current, None, "6101000", dept)})
    rows.sort(key=lambda r: -abs(r["variance"] if r["variance"] is not None else r["amount"]))
    # No UKG subtotal: less the departments shown, it would give the combined pay
    # of the departments withheld for being small.
    return {"id": "payroll_hris", "kind": "payroll_hris", "title": "Payroll vs. HRIS",
            "periods": {"current": period},
            "sections": [{"id": "all", "label": "Salaries by department", "rows": rows,
                          "total": r2(sum(ledger.values()))}]}


def dept_months(current, prior, periods):
    """P&L spend by department, this month and last, with each department's
    accounts. Summed from the ledger lines, which carry the department."""
    book = defaultdict(lambda: {"actual": 0.0, "prior": 0.0, "accounts": defaultdict(lambda: [0.0, 0.0, ""])})
    for i, lines in enumerate((current, prior)):
        for l in lines:
            if not is_pl(l["account_code"]):
                continue
            d = book[l["department"] or "Non-Specific"]
            d["actual" if i == 0 else "prior"] += l["amount"]
            a = d["accounts"][l["account_code"]]
            a[i] += l["amount"]
            a[2] = a[2] or l["account_leaf"]
    rows = []
    for dept, d in book.items():
        accts = [{"account": c, "leaf": v[2], "actual": r2(v[0]), "prior": r2(v[1]), "change": r2(v[0] - v[1])}
                 for c, v in d["accounts"].items() if round(v[0], 2) or round(v[1], 2)]
        accts.sort(key=lambda a: -abs(a["change"]))
        rows.append({"department": dept, "actual": r2(d["actual"]), "prior": r2(d["prior"]),
                     "change": r2(d["actual"] - d["prior"]), "accounts": accts})
    rows.sort(key=lambda r: -r["actual"])
    return {"period": periods["current"], "prior_period": periods["prior"], "rows": rows}


# Employee expense accounts, as the ledger names them.
PAY_ACCOUNTS = [("6101000", "salaries"), ("6102000", "bonus"), ("6103000", "taxes"), ("6104000", "benefits")]


def payroll_analytics(current, prior, staff, period, names=False):
    """Employee expense by department from the ledger, with payroll tax and
    benefits as a share of salaries, and UKG headcount by type."""
    end = period_end(period)
    heads = defaultdict(int)
    types = defaultdict(int)
    for p in staff:
        if p["hired"] and end and p["hired"] > end:
            continue
        types[p["type"] or "Unknown"] += 1
        if p["type"] in NOT_PAYROLL or not p["department"]:
            continue
        heads[p["department"]] += 1
    sums = defaultdict(lambda: defaultdict(float))
    for i, lines in enumerate((current, prior)):
        for l in lines:
            code = l["account_code"]
            if code[:3] != "610":
                continue
            key = dict(PAY_ACCOUNTS).get(code, "other")
            sums[(l["department"] or "Non-Specific", i)][key] += l["amount"]
    depts = sorted({d for d, _ in sums} | set(heads))
    rows, totals = [], defaultdict(float)
    for dept in depts:
        cur, pri = sums.get((dept, 0), {}), sums.get((dept, 1), {})
        n = heads.get(dept, 0)
        for k, v in cur.items():
            totals[k] += v
        totals["prior"] += sum(pri.values())
        sal = cur.get("salaries", 0.0)
        rows.append({"department": dept, "headcount": n,
                     "salaries": r2(sal), "bonus": r2(cur.get("bonus", 0.0)), "taxes": r2(cur.get("taxes", 0.0)),
                     "benefits": r2(cur.get("benefits", 0.0)), "other": r2(cur.get("other", 0.0)),
                     "total": r2(sum(cur.values())), "prior_total": r2(sum(pri.values())),
                     "tax_pct": pct(cur.get("taxes", 0.0), sal) if sal else None,
                     "benefits_pct": pct(cur.get("benefits", 0.0), sal) if sal else None})
    if names:
        # The roster under each department, for the payroll detail: name, title,
        # type, annual salary and bonus target, as UKG holds them.
        for r in rows:
            r["people"] = sorted(({"name": p["name"], "title": p["title"], "type": p["type"],
                                   "salary": r2(p["salary"]), "bonus_pct": p["bonus_pct"]}
                                  for p in staff if p["department"] == r["department"]
                                  and not (p["hired"] and end and p["hired"] > end)),
                                 key=lambda x: (-x["salary"], x["name"]))
    rows.sort(key=lambda r: -(r.get("total") or 0))
    sal = totals.get("salaries", 0.0)
    total = {k: r2(totals.get(k, 0.0)) for k in ("salaries", "bonus", "taxes", "benefits", "other")}
    total.update({"total": r2(sum(totals[k] for k in ("salaries", "bonus", "taxes", "benefits", "other"))),
                  "prior_total": r2(totals.get("prior", 0.0)),
                  "tax_pct": pct(totals.get("taxes", 0.0), sal) if sal else None,
                  "benefits_pct": pct(totals.get("benefits", 0.0), sal) if sal else None})
    return {"period": period, "rows": rows, "total": total,
            "headcount": {"payroll": sum(heads.values()), "by_type": dict(sorted(types.items(), key=lambda x: -x[1]))}}


def balance_sheet(path, period, inputs):
    """The NetSuite balance sheet report: this month, last month, the year end and
    the same month last year, line by line. No test runs on it; it is laid out for
    review and commentary."""
    months = [period, sources.shift(period, -1), "Dec " + str(int(period[-4:]) - 1), sources.shift(period, -12)]
    rows = sources.read_balance_sheet(path, months)
    inputs.add("netsuite_balance_sheet", path, len(rows))
    return {"period": months[0], "prior": months[1], "year_end": months[2], "prior_year": months[3], "rows": rows}


# ---------------------------------------------------------------- more schedules

# The coding engine declares no groups of its own; these match the console's
# defaults. The coding findings (T1, T4, T2) sit on the vendor rows instead.
CHECK_GROUPS = ["tieout", "integrity", "tax"]
CHECK_RULES = ["T0.TIE_OUT", "T0.DUPLICATE_LINE", "T0.ABERRANT_POSTING_LAG",
               "T3.IRC_274A_ENTERTAINMENT", "T3.IRC_274N_MEALS",
               "T3.IRC_274B_GIFTS", "T3.IRC_174_BASE"]
RULE_LABELS = {
    "T1.DEPT_INCONSISTENCY": "Department differs from the vendor's usual",
    "T4.PO_ACCOUNT_MISMATCH": "Account differs from the Coupa PO",
    "T2.UNALLOCATED": "Coded to no department",
    "T0.TIE_OUT": "Ledger does not balance",
    "T0.DUPLICATE_LINE": "Possible duplicate postings",
    "T0.ABERRANT_POSTING_LAG": "Posted well outside the period",
    "T3.IRC_274A_ENTERTAINMENT": "Entertainment",
    "T3.IRC_274N_MEALS": "Meals",
    "T3.IRC_274B_GIFTS": "Gifts",
    "T3.IRC_174_BASE": "Research and experimental costs",
}


def lag_twins(findings):
    """A stale bill is flagged on its Accounts Payable line and on its expense lines.
    The Accounts Payable side is the same question, so it is answered with the
    expense side: these are the finding ids to leave out."""
    lag = [f for f in findings if f.get("rule_id") == "T0.ABERRANT_POSTING_LAG"]
    doc = lambda f: ((txns_of(f) or [{}])[0].get("document_number") or "").strip()
    pl_docs = {doc(f) for f in lag if is_pl((txns_of(f) or [{}])[0].get("account_code", ""))}
    return sorted(f["finding_id"] for f in lag
                  if doc(f) and doc(f) in pl_docs
                  and not is_pl((txns_of(f) or [{}])[0].get("account_code", "")))


def ledger_checks(findings):
    """The integrity and tax findings as one table: one line per finding,
    sectioned by what the rule tests, with the decision under the row."""
    sections = []
    twins = set(lag_twins(findings))
    for rule in CHECK_RULES:
        rows = []
        for f in findings:
            if f.get("rule_id") != rule or f["finding_id"] in twins:
                continue
            txns = txns_of(f)
            accounts = sorted({t.get("account_code", "") for t in txns if t.get("account_code")})
            depts = sorted({(t.get("department") or "").strip() for t in txns} - {""})
            vendors = sorted({(t.get("vendor_or_name") or "").strip() for t in txns} - {""})
            rows.append({
                "finding_id": f["finding_id"],
                "vendor": vendors[0] if len(vendors) == 1 else (
                    "%d vendors" % len(vendors) if vendors else ""),
                "what": f.get("title", ""),
                "account": accounts[0] if len(accounts) == 1 else "",
                "accounts": len(accounts),
                "department": depts[0] if len(depts) == 1 else (
                    "%d departments" % len(depts) if depts else ""),
                "lines": f.get("transaction_count") or len(txns),
                "documents": sorted({(t.get("document_number") or "").strip() for t in txns} - {""}),
                "amount": r2(f.get("amount_at_risk") or 0),
            })
        if rows:
            rows.sort(key=lambda r: -abs(r["amount"]))
            sections.append({"id": rule, "label": RULE_LABELS.get(rule, rule), "rows": rows,
                             "total": r2(sum(r["amount"] for r in rows))})
    if not sections:
        return None
    return {"id": "checks", "kind": "findings", "title": "Ledger checks",
            "group": CHECK_GROUPS[0], "groups": CHECK_GROUPS, "sections": sections}


# ---------------------------------------------------------------- vendors

# Short names for the coding findings when they sit on a vendor row.
FLAG_LABELS = {"T1.DEPT_INCONSISTENCY": "Unusual department",
               "T4.PO_ACCOUNT_MISMATCH": "Account differs from PO",
               "T2.UNALLOCATED": "No department"}


def screens(current, prior, prior2, accounts, period):
    """The flux engine's prepaid and capital screens over this month's lines, so
    the coding review asks the same two questions earlier in the close. Returns
    None when serif_uc2_flux.py is not beside this file."""
    try:
        import serif_uc2_flux as flux
    except ImportError:
        return None
    as_gl = lambda ls: [dict(l, vendor_or_name=l["vendor"]) for l in ls]
    history = {}
    for ls in (prior, prior2):
        if ls:
            history.setdefault(ls[0]["period"], []).extend(as_gl(ls))
    leaves = {c: a.get("name") or c for c, a in accounts.items()}
    seq = [0]
    out = flux.prepaid_findings(as_gl(current), history, leaves, period, seq)
    out += flux.capex_findings(as_gl(current), leaves, period, seq)
    return out


def _flag(fid, label, amount, why=(), do=(), finding_id=None, match=None):
    """`match` says which of the row's lines the flag is about, so the console can
    list them: {"all": true}, {"account", "department"} for a coding, {"document"}
    (with "account") for a line an engine finding names, or {"not": [codings]} for
    the lines off a planned coding."""
    return {"id": fid, "label": label, "amount": r2(abs(amount)),
            "finding_ids": [finding_id] if finding_id else [],
            "why": " ".join(why), "do": " ".join(do), "match": list(match or [])}


def _doc_match(f):
    return [{"document": (t.get("document_number") or "").strip(), "account": t.get("account_code", "")}
            for t in txns_of(f) if (t.get("document_number") or "").strip()]


def _either(labels):
    labels = [l for l in labels if l]
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " or " + labels[-1]


def vendors_table(current, prior, prior2, prior_year, periods, findings, accounts,
                  plan_table=None, requester_table=None, screen_findings=None,
                  requested=None, vintage="", po_accounts=None):
    """Every vendor billed this month, one row each: three months by account and
    by department, the lines behind them, and a flag for each reason to look.
    A vendor with no flag is coded as before and needs nothing."""
    cur, pri, pr2, py = codings(current), codings(prior), codings(prior2), codings(prior_year)
    books = [("prior2", pr2), ("prior", pri), ("current", cur)]
    where = _either([periods.get("prior2"), periods.get("prior"), periods.get("prior_year")])
    A = lambda c: _acct(accounts, c)

    by_finding = defaultdict(list)
    for f in findings:
        if f.get("rule_id") in CODING_RULES:
            for v in {(t.get("vendor_or_name") or "").strip() for t in txns_of(f)} - {""}:
                by_finding[v].append(f)
    plan_rows = {r["vendor"]: r for s in (plan_table or {}).get("sections", []) for r in s["rows"]}
    asked = defaultdict(list)
    for s in (requester_table or {}).get("sections", []):
        if s["id"] == "po":
            for r in s["rows"]:
                asked[norm_vendor(r["vendor"])].append(r)
    screened = defaultdict(list)
    for f in screen_findings or []:
        screened[(f.get("title") or "").split(":")[0].strip()].append(f)

    def grid(vendor, i, name):
        keys = set()
        for _, book in books:
            keys |= {k[i] for k in book.get(vendor, {})}
        out = []
        for key in keys:
            row = {name: key or ("No department" if i else "")}
            for label, book in books:
                row[label] = r2(sum(v[0] for k, v in book.get(vendor, {}).items() if k[i] == key))
            out.append(row)
        out.sort(key=lambda r: (-abs(r["current"]), -abs(r["prior"]), -abs(r["prior2"]), r[name]))
        return out

    def coding_grid(vendor):
        """Each account and department pair the vendor used, over the three months."""
        keys = set()
        for _, book in books:
            keys |= set(book.get(vendor, {}))
        out = []
        for acct, dept in keys:
            row = {"account": acct, "department": dept}
            for label, book in books:
                row[label] = r2(book.get(vendor, {}).get((acct, dept), [0.0])[0])
            out.append(row)
        out.sort(key=lambda r: (-abs(r["current"]), -abs(r["prior"]), -abs(r["prior2"]),
                                r["account"], r["department"]))
        return out

    sections = {"flagged": [], "clear": [], "stopped": []}
    for vendor in sorted(set(cur) | set(by_finding) | set(pri) | set(pr2), key=str.lower):
        cells = cur.get(vendor, {})
        total = sum(v[0] for v in cells.values())
        known = set(pri.get(vendor, {})) | set(pr2.get(vendor, {})) | set(py.get(vendor, {}))
        # A coding the engine already raised a finding on is left to that finding.
        covered = {(t.get("account_code", ""), (t.get("department") or "").strip())
                   for f in by_finding.get(vendor, []) for t in txns_of(f)}
        flags = []
        if not known and abs(total) >= 0.005:
            # The account the vendor's Coupa POs were approved against is the one
            # suggestion with evidence behind it; with no PO there is none to make.
            po = (po_accounts or {}).get(norm_vendor(vendor), {})
            po_acct = max(sorted(po), key=lambda a: po[a]) if po else ""
            coded = sorted({k[0] for k in cells}, key=lambda a: -abs(sum(v[0] for k, v in cells.items() if k[0] == a)))
            why = ["No bills from %s in %s." % (vendor, where)]
            do = ["Read what was bought."]
            if po_acct and po_acct not in coded:
                why.append("Its Coupa POs charge %s; the lines are on %s." % (A(po_acct), " and ".join(A(c) for c in coded)))
                do += ["If it belongs on %s, as the PO says, reclass the lines." % A(po_acct),
                       "If the account on the lines is right, choose Cleared."]
            else:
                if po_acct:
                    why.append("The lines are on %s, the account its Coupa POs charge." % A(po_acct))
                do += ["If the account or the department is wrong, reclass the lines.",
                       "If both are right, choose Cleared."]
            flags.append(_flag("new", "New vendor", total, why, do, match=[{"all": True}]))
        else:
            fresh = sorted(((k, v) for k, v in cells.items()
                            if k not in known and k not in covered and abs(v[0]) >= 0.005),
                           key=lambda kv: -abs(kv[1][0]))
            if fresh:
                why = ["%s / %s has %s this month." % (A(k[0]), k[1] or "no department", _m(v[0]))
                       for k, v in fresh[:2]]
                if len(fresh) > 2:
                    why.append("%d more coding%s new." % (len(fresh) - 2, " is" if len(fresh) == 3 else "s are"))
                why.append("%s did not use %s in %s." % (
                    vendor, "this coding" if len(fresh) == 1 else "these codings", where))
                before = defaultdict(float)
                for book in (pri, pr2, py):
                    for k, v in book.get(vendor, {}).items():
                        before[k] += abs(v[0])
                usual = None
                if before:
                    usual = max(sorted(before), key=lambda c: before[c])
                    why.append("Its bills before went to %s / %s." % (A(usual[0]), usual[1] or "no department"))
                flags.append(_flag("changed", "Coding changed", sum(abs(v[0]) for _, v in fresh), why,
                                   ["Read the lines on the new coding.",
                                    "If the coding is wrong, reclass the lines.",
                                    "If it is right, choose Cleared."],
                                   match=[{"account": k[0], "department": k[1]} for k, _ in fresh]))
                if usual:
                    # Where a recode would send the lines back to.
                    flags[-1]["before"] = {"account": usual[0], "department": usual[1]}
        for f in by_finding.get(vendor, []):
            flags.append(_flag(f["rule_id"], FLAG_LABELS.get(f["rule_id"], f["rule_id"]),
                               f.get("amount_at_risk") or 0, finding_id=f["finding_id"],
                               match=_doc_match(f)))
        plan = plan_rows.get(vendor)
        if plan and plan["status"] == "differs":
            p = plan["planned"][0] if plan["planned"] else {}
            flags.append(_flag("plan", "Coded off plan", plan["off_plan"],
                               ["The %s forecast plans %s on %s / %s." % (
                                   vintage, vendor, A(p.get("account")), p.get("department") or "no department"),
                                "%s this month is on other coding." % _m(plan["off_plan"])],
                               ["Read the lines.",
                                "If the coding is wrong, reclass the lines.",
                                "If the plan is wrong, choose Cleared and tell FP&A."],
                               match=[{"not": [{"account": q.get("account"), "department": q.get("department") or ""}
                                               for q in plan["planned"]]}]))
        other = [r for r in asked.get(norm_vendor(vendor), []) if r["status"] == "differs"]
        if other:
            amt = sum(r["amount"] for r in other)
            depts = sorted({r["requester_department"] for r in other})
            coded = sorted({r["coded_department"] or "no department" for r in other})
            flags.append(_flag("requester", "Requested by " + depts[0] if len(depts) == 1
                               else "Requested elsewhere", amt,
                               ["People in %s raised Coupa POs for %s." % (_either(depts), _m(amt)),
                                "The POs charge %s." % _either(coded)],
                               ["Open a line's PO in Coupa to see who requested it.",
                                "Ask them which department used the purchase.",
                                "If it is not the department on the line, reclass the line.",
                                "If it is, choose Cleared."],
                               match=[dict({"account": r["account"]},
                                           **({"department": r["coded_department"]}
                                              if r["coded_department"] in GL_DEPARTMENTS else {}))
                                      for r in other if r.get("account")]))
        for f in screened.get(vendor, []):
            x = explain(f, accounts, periods["current"]) or {}
            flags.append(_flag("prepaid" if f["rule_id"] == "F9.PREPAID" else "capital",
                               "May be prepaid" if f["rule_id"] == "F9.PREPAID" else "May be capital",
                               f.get("amount_at_risk") or 0, [x.get("why", "")], [x.get("do", "")],
                               match=_doc_match(f)))
            # One flag holds every finding of the vendor's, so each line of the match
            # carries its own finding's total, which the screen's threshold tests (a
            # prepaid's related charges together), and, for a capital bill, where it
            # goes (Capital in Process or its fixed asset account) and why.
            place = (f.get("correction") or {}).get("placement")
            for m in flags[-1]["match"]:
                m["total"] = r2(abs(f.get("amount_at_risk") or 0))
                if place:
                    m.update(to=place["to"], placement=place)
        # One flag per reason: three findings of one rule on one vendor are one
        # question about that vendor.
        merged = {}
        for x in flags:
            if x["id"] in merged:
                m = merged[x["id"]]
                m["amount"] = r2(m["amount"] + x["amount"])
                m["finding_ids"] += x["finding_ids"]
                m["match"] += x["match"]
            else:
                merged[x["id"]] = x
        flags = list(merged.values())
        who = requested.get(norm_vendor(vendor), {}) if requested else {}
        by_dept = grid(vendor, 1, "department")
        owner = (max(who, key=who.get) if who else
                 (by_dept[0]["department"] if by_dept else ""))
        row = {
            "vendor": vendor,
            "amount": r2(total),
            "prior": r2(sum(v[0] for v in pri.get(vendor, {}).values())),
            "prior2": r2(sum(v[0] for v in pr2.get(vendor, {}).values())),
            "by_account": grid(vendor, 0, "account"),
            "by_department": by_dept,
            "by_coding": coding_grid(vendor),
            "planned": plan["planned"] if plan else [],
            "flags": sorted(flags, key=lambda x: -x["amount"]),
            "finding_ids": [i for x in flags for i in x["finding_ids"]],
            "owner": owner,
            "detail": lines_for(current, vendor, cap=None, blank=True),
            "lines_period": periods["current"],
            "status": "flagged" if flags else "clear",
        }
        # Billed before and not this month: no coding to review, but a gap a
        # reviewer reads when an invoice may be missing. Its lines are last seen.
        if not cells and not flags:
            last = prior if vendor in pri else prior2
            row.update(status="stopped", detail=lines_for(last, vendor, cap=None),
                       lines_period=periods["prior"] if vendor in pri else periods.get("prior2"))
        sections[row["status"]].append(row)
    sections["flagged"].sort(key=lambda r: -max(x["amount"] for x in r["flags"]))
    sections["clear"].sort(key=lambda r: -abs(r["amount"]))
    sections["stopped"].sort(key=lambda r: -abs(r["prior"] or r["prior2"]))
    labels = {"flagged": "Flagged", "clear": "No flags",
              "stopped": "Nothing in " + periods["current"]}
    return {"id": "vendors", "kind": "vendors", "title": "Vendors", "periods": periods,
            "plan_vintage": vintage,
            "sections": [{"id": k, "label": labels[k], "rows": sections[k],
                          "total": r2(sum(r["amount"] for r in sections[k])),
                          "prior_total": r2(sum(r["prior"] for r in sections[k])),
                          "prior2_total": r2(sum(r["prior2"] for r in sections[k]))}
                         for k in ("flagged", "clear", "stopped") if sections[k]]}


def adjustment_rows(findings, rules):
    for f in findings:
        if f.get("rule_id") in rules:
            yield f, parse_entry((f.get("correction") or {}).get("entry", ""))


def prepaid_schedule(findings, run):
    rows = {"prepaid": [], "capital": []}
    for f, entry in adjustment_rows(findings, ("F9.PREPAID", "F10.CAPITALIZE")):
        dr = next((l for l in entry if l["debit"]), {})
        cr = next((l for l in entry if l["credit"]), {})
        what = (f.get("evidence") or {}).get("observed", "")
        rows["prepaid" if f["rule_id"] == "F9.PREPAID" else "capital"].append({
            "finding_id": f["finding_id"], "vendor": (f.get("title") or "").split(":")[0],
            "from_account": cr.get("account", ""), "to_account": dr.get("account", ""),
            "department": cr.get("department", ""),
            "what": what.split(": ", 1)[1] if ": " in what else what,
            "amount": r2(f.get("amount_at_risk") or 0)})
    booked = [{"vendor": b["vendor"], "from_account": "", "to_account": b["account"],
               "department": "", "what": b["description"], "amount": b["amount"],
               "finding_id": None, "context": True}
              for b in run.get("bills_to_balance_sheet") or []]
    sections = []
    if rows["prepaid"]:
        sections.append({"id": "prepaid", "label": "May cover future months", "rows": rows["prepaid"],
                         "total": r2(sum(r["amount"] for r in rows["prepaid"]))})
    if rows["capital"]:
        sections.append({"id": "capital", "label": "May be a capital asset", "rows": rows["capital"],
                         "total": r2(sum(r["amount"] for r in rows["capital"]))})
    if booked:
        sections.append({"id": "booked", "label": "Already billed to prepaid or fixed-asset accounts",
                         "rows": booked, "total": r2(sum(r["amount"] for r in booked))})
    if not sections:
        return None
    return {"id": "prepaid", "kind": "prepaid", "title": "Prepaids and Capital",
            "group": "prepaid", "sections": sections}


def reclass_schedule(findings):
    rows = []
    for f, entry in adjustment_rows(findings, ("F7.REVENUE_IN_EXPENSE", "F8.VENDOR_DROPPED")):
        c = f.get("correction") or {}
        subject = c.get("subject", "")
        code = subject.split(" ")[0] if subject[:1].isdigit() else ""
        dept = subject.rsplit(" / ", 1)[-1] if " / " in subject else ""
        rows.append({
            "finding_id": f["finding_id"],
            "issue": "Customer document in expense" if f["rule_id"] == "F7.REVENUE_IN_EXPENSE"
                     else "Vendor missing from a prepaid release" if "prepaid release" in f.get("title", "")
                     else "Vendor missing from a recurring journal",
            "vendor": (f.get("title") or "").split(":")[0] if f["rule_id"] == "F7.REVENUE_IN_EXPENSE" else "",
            "account": code, "department": dept,
            "now": c.get("current", ""), "should_be": c.get("proposed", ""),
            "amount": r2(f.get("amount_at_risk") or 0)})
    if not rows:
        return None
    rows.sort(key=lambda r: -abs(r["amount"]))
    return {"id": "reclass", "kind": "reclass", "title": "Reclassifications", "group": "reclass",
            "sections": [{"id": "all", "label": "Entries in the wrong place", "rows": rows,
                          "total": r2(sum(r["amount"] for r in rows))}]}


def forecast_pairs(findings, period):
    """A reclass staged in the forecast shows up as two differences, one on each
    account it moves between. Where the same manual line nets to zero across two
    differences, the two are one entry, and it balances."""
    by_note = defaultdict(list)
    for f in findings:
        if f.get("rule_id") != "F5.MODEL_TIE":
            continue
        subject = (f.get("correction") or {}).get("subject", "")
        code = subject.split(" ")[0] if subject[:1].isdigit() else ""
        dept = (f.get("title") or "").split(":")[0].split(" / ")[-1].strip()
        for l in f.get("model_lines") or []:
            if l.get("description") and not l.get("vendor") and not l.get("po_number"):
                by_note[l["description"]].append((f["finding_id"], code, dept, num(l.get("amount")),
                                                  l.get("line_ref", "")))
    out = []
    for note, parts in sorted(by_note.items()):
        dr = [p for p in parts if p[3] > 0]
        cr = [p for p in parts if p[3] < 0]
        if not dr or not cr or abs(sum(p[3] for p in parts)) >= 0.005:
            continue
        lines = [{"account": p[1], "department": p[2], "vendor": "", "debit": r2(p[3]),
                  "credit": 0.0, "documents": [p[4]]} for p in dr] + \
                [{"account": p[1], "department": p[2], "vendor": "", "debit": 0.0,
                  "credit": r2(-p[3]), "documents": [p[4]]} for p in cr]
        total = r2(sum(p[3] for p in dr))
        out.append({
            "entry_id": "SERIF-" + dr[0][0], "finding_id": dr[0][0],
            "finding_ids": sorted({p[0] for p in parts}), "rule_id": "F5.MODEL_TIE",
            "kind": "Forecast reclass", "date": period_end(period), "reverses": "",
            "memo": 'Reclass staged in the forecast as "%s" (%s)' % (
                note, ", ".join(p[4] for p in parts)),
            "lines": lines, "debits": total, "credits": total, "balanced": True,
            "support": "Forecast workbook " + ", ".join(p[4] for p in parts)})
    return out


# ---------------------------------------------------------------- Journal Entries

ENTRY_SIDE = re.compile(r"(Dr|Cr)\s+(\d{7})\s+(.*?)(?=\s*/\s*(?:Dr|Cr)\s+\d{7}|\s+for\s+\$|$)")
ENTRY_AMOUNT = re.compile(r"for\s+\$(-?[\d,]+\.?\d*)")


def parse_entry(text):
    """'Dr 6410000 X / Cr 2206000 Y for $1.00' -> lines. Each side's department,
    when the engine names one, follows the account name after ' / '."""
    if not text:
        return []
    amount_match = ENTRY_AMOUNT.search(text)
    amount = num(amount_match.group(1)) if amount_match else 0.0
    lines = []
    for side, code, rest in ENTRY_SIDE.findall(text):
        rest = rest.strip()
        dept = ""
        if " / " in rest:
            rest, dept = rest.rsplit(" / ", 1)
        lines.append({"account": code, "department": dept.strip(),
                      "debit": r2(amount) if side == "Dr" else 0.0,
                      "credit": r2(amount) if side == "Cr" else 0.0})
    return lines


def quoted(text, word):
    match = re.search(word + r"\s+'([^']+)'", text or "")
    return match.group(1) if match else ""


def txns_of(f):
    return f.get("transactions") or ([f["transaction"]] if f.get("transaction") else [])


def gl_dims(lines):
    """(document, account) -> (Project, Program) from the ledger lines, for a finding
    whose transactions do not carry them. A document whose lines on one account
    disagree gives blanks, for the reviewer to fill."""
    out = {}
    for l in lines:
        k = ((l.get("document_number") or "").strip(), (l.get("account_code") or "").strip())
        v = ((l.get("project") or "").strip(), (l.get("program") or "").strip())
        out[k] = v if out.get(k, v) == v else ("", "")
    return out


def dims(t, lookup):
    """A transaction's Project and Program: its own, else the ledger line's."""
    if "project" in t or "program" in t:
        return {"project": (t.get("project") or "").strip(), "program": (t.get("program") or "").strip()}
    p = lookup.get(((t.get("document_number") or "").strip(), (t.get("account_code") or "").strip()), ("", ""))
    return {"project": p[0], "program": p[1]}


def bs_department(lines):
    """A new balance sheet line takes Non-Specific: a recode to Capital in Process does
    not keep the expense's department. A line that reverses the ledger line being
    corrected (`reverses_line`) keeps that line's department, so the reversal nets the
    original. Income statement lines keep theirs."""
    for l in lines:
        l.setdefault("project", "")
        l.setdefault("program", "")
        if is_bs(l.get("account")) and not l.get("reverses_line"):
            l["department"] = BS_DEPARTMENT
    return lines


def collapse(lines):
    """One line per account, department, Project, Program, vendor and side, carrying
    the documents it covers. A 26-line reclass reads as two lines, with its support
    attached."""
    out, order = {}, []
    for line in lines:
        side = "Dr" if line["debit"] else "Cr"
        key = (line["account"], line["department"], line.get("project", ""), line.get("program", ""),
               line.get("vendor", ""), side)
        if key not in out:
            out[key] = dict(line, documents=[], debit=0.0, credit=0.0)
            out[key].pop("document", None)
            order.append(key)
        out[key]["debit"] += line["debit"]
        out[key]["credit"] += line["credit"]
        doc = line.get("document")
        if doc and doc not in out[key]["documents"]:
            out[key]["documents"].append(doc)
    result = []
    for key in order:
        line = out[key]
        line["debit"], line["credit"] = r2(line["debit"]), r2(line["credit"])
        result.append(line)
    # Debits first, the order a Journal Entry is read in.
    return sorted(result, key=lambda l: 0 if l["debit"] else 1)


def capitalize_memo(vendor, place):
    """A capital entry's memo says where the purchase goes and, for Capital in
    Process, until when. The P&L Flux keys an adjustment by its memo, so the memo of
    an asset in service is the one it always had, and a decision on it carries over."""
    kind = (place or {}).get("kind", "in_service")
    if kind in ("buildout", "not_in_service"):
        return "Capitalize %s purchase to Capital in Process until it is placed in service" % vendor
    if kind == "no_account":
        return "Capitalize %s purchase to Capital in Process until its fixed asset account is named" % vendor
    return "Capitalize %s purchase as a fixed asset" % vendor


def entries(findings, period, accrual_depts=None, lookup=None):
    """One proposed Journal Entry per finding that proposes a correction. Rules
    that ask for a confirmation rather than a correction (posting lag, tax
    screens, variances) produce none. Both sides of a reclass carry the original
    line's Project and Program (from `lookup`, the ledger's, when the finding's
    transactions do not carry them); an entry with no ledger line behind it (an
    accrual from Coupa receipts, a reclass staged in the forecast) leaves them blank.
    The side that reverses a posted line is marked `reverses_line` and keeps its
    department, on a balance sheet account too; a new balance sheet line takes
    Non-Specific."""
    accrual_depts = accrual_depts or {}
    lookup = lookup or {}
    out = []
    date = period_end(period)
    for f in findings:
        rule = f.get("rule_id", "")
        ev = f.get("evidence") or {}
        lines, kind, memo = [], "", ""
        # A prepaid or capital purchase under Serif's threshold is listed for the reviewer,
        # not proposed for booking: the policy leaves it in expense.
        if (rule == "F9.PREPAID" and (f.get("amount_at_risk") or 0) < PREPAID
                or rule == "F10.CAPITALIZE" and (f.get("amount_at_risk") or 0) < CAPITALIZATION):
            continue
        if rule == "T1.DEPT_INCONSISTENCY":
            to_dept = quoted(ev.get("expected"), "department")
            kind = "Department reclass"
            for t in txns_of(f):
                amt = num(t.get("amount"))
                lines.append(dict({"account": t.get("account_code", ""), "department": to_dept,
                                   "vendor": t.get("vendor_or_name", ""),
                                   "debit": r2(max(amt, 0)), "credit": r2(max(-amt, 0)),
                                   "document": t.get("document_number", "")}, **dims(t, lookup)))
                lines.append(dict({"account": t.get("account_code", ""),
                                   "department": t.get("department", ""),
                                   "vendor": t.get("vendor_or_name", ""),
                                   "debit": r2(max(-amt, 0)), "credit": r2(max(amt, 0)),
                                   "document": t.get("document_number", ""), "reverses_line": True}, **dims(t, lookup)))
            vendor = (txns_of(f) or [{}])[0].get("vendor_or_name", "")
            memo = "Reclass %s from %s to %s" % (vendor, (txns_of(f) or [{}])[0].get("department", ""), to_dept)
        elif rule == "T4.PO_ACCOUNT_MISMATCH":
            match = re.search(r"account\s+(\d{7})", ev.get("expected", ""))
            to_acct = match.group(1) if match else ""
            kind = "Account reclass to the PO-approved account"
            for t in txns_of(f):
                amt = num(t.get("amount"))
                lines.append(dict({"account": to_acct, "department": t.get("department", ""),
                                   "vendor": t.get("vendor_or_name", ""),
                                   "debit": r2(max(amt, 0)), "credit": r2(max(-amt, 0)),
                                   "document": t.get("document_number", "")}, **dims(t, lookup)))
                lines.append(dict({"account": t.get("account_code", ""),
                                   "department": t.get("department", ""),
                                   "vendor": t.get("vendor_or_name", ""),
                                   "debit": r2(max(-amt, 0)), "credit": r2(max(amt, 0)),
                                   "document": t.get("document_number", ""), "reverses_line": True}, **dims(t, lookup)))
            vendor = (txns_of(f) or [{}])[0].get("vendor_or_name", "")
            froms = sorted({t.get("account_code", "") for t in txns_of(f)} - {""})
            memo = "Reclass %s from %s to %s" % (vendor, ", ".join(froms), to_acct)
        elif rule == "T0.DUPLICATE_LINE":
            txns = txns_of(f)
            if len(txns) < 2:
                continue
            kind = "Reverse duplicate posting"
            first = txns[0]
            repeat = sum(num(t.get("amount")) for t in txns[1:])
            lines.append(dict({"account": first.get("account_code", ""),
                               "department": first.get("department", ""),
                               "vendor": first.get("vendor_or_name", ""),
                               "debit": r2(max(-repeat, 0)), "credit": r2(max(repeat, 0)),
                               "document": first.get("document_number", ""), "reverses_line": True},
                              **dims(first, lookup)))
            if first.get("txn_type") == "Bill":
                lines.append(dict({"account": AP_ACCOUNT, "department": "",
                                   "vendor": first.get("vendor_or_name", ""),
                                   "debit": r2(max(repeat, 0)), "credit": r2(max(-repeat, 0)),
                                   "document": first.get("document_number", "")}, **dims(first, lookup)))
            memo = "Reverse %d repeat posting(s) of %s" % (len(txns) - 1,
                                                             first.get("document_number", ""))
        elif rule == "F5.MODEL_TIE":
            continue
        elif (f.get("correction") or {}).get("entry"):
            parsed = parse_entry(f["correction"]["entry"])
            if not parsed:
                continue
            kind = {"F3.ACCRUAL_RECEIPT": "Accrual", "F6.ACCRUAL_PATTERN": "Accrual",
                    "F7.REVENUE_IN_EXPENSE": "Reclass", "F9.PREPAID": "Prepaid",
                    "F10.CAPITALIZE": "Capitalize"}.get(rule, "Correction")
            vendor = (f.get("title") or "").split(":")[0].strip() if rule in (
                "F3.ACCRUAL_RECEIPT", "F6.ACCRUAL_PATTERN", "F7.REVENUE_IN_EXPENSE",
                "F9.PREPAID", "F10.CAPITALIZE") else ""
            # One Project and Program for the entry: its lines' own when they agree,
            # else blank, for the reviewer to fill.
            both = {tuple(dims(t, lookup).values()) for t in txns_of(f)}
            pp = both.pop() if len(both) == 1 else ("", "")
            posted = {(t.get("account_code") or "").strip() for t in txns_of(f)} - {""}
            for line in parsed:
                line["vendor"] = vendor
                line["document"] = ""
                line["project"], line["program"] = pp
                if line["account"] in posted:
                    line["reverses_line"] = True
                if line["debit"] and not line["department"]:
                    line["department"] = accrual_depts.get(f["finding_id"], "")
            # NetSuite requires a department on every line. A P&L line still without one takes
            # the department of the ledger lines behind the finding, when they share one.
            depts = {(t.get("department") or "").strip() for t in txns_of(f)} - {""}
            for line in parsed:
                if not line["department"] and line["account"][:1] in ("4", "5", "6", "7", "8") and len(depts) == 1:
                    line["department"] = next(iter(depts))
            lines = parsed
            # The memo says what the entry does, in words. The lines carry the
            # accounts and amounts, so the memo does not repeat them.
            memo = {"F3.ACCRUAL_RECEIPT": "Accrue %s for goods received in %s" % (vendor, period),
                    "F6.ACCRUAL_PATTERN": "Accrue %s for %s, from its billing pattern" % (vendor, period),
                    "F7.REVENUE_IN_EXPENSE": "Move %s customer invoice from expense to revenue" % vendor,
                    "F9.PREPAID": "Move %s bill to prepaid, then amortize over the service period" % vendor,
                    "F10.CAPITALIZE": capitalize_memo(vendor, (f.get("correction") or {}).get("placement")),
                    }.get(rule, "Correction proposed by " + rule)
        else:
            continue
        lines = collapse(bs_department([l for l in lines if l["debit"] or l["credit"]]))
        if not lines:
            continue
        debits = r2(sum(l["debit"] for l in lines))
        credits = r2(sum(l["credit"] for l in lines))
        # An entry that does not balance cannot be booked, so it is not listed as
        # one. Its finding stays on its own schedule.
        if abs(debits - credits) >= 0.005:
            continue
        out.append({
            "entry_id": "SERIF-" + f["finding_id"],
            "finding_id": f["finding_id"], "rule_id": rule, "kind": kind,
            "date": date,
            "reverses": next_period_start(period) if rule in ("F3.ACCRUAL_RECEIPT",
                                                              "F6.ACCRUAL_PATTERN") else "",
            "memo": memo, "lines": lines,
            "debits": debits, "credits": credits,
            "balanced": abs(debits - credits) < 0.005,
            "support": ev.get("basis", ""),
        })
    pairs = forecast_pairs(findings, period)
    for x in pairs:
        bs_department(x["lines"])
    return out + pairs


WITHHELD = "Employee paid through AP (name withheld)"


def withhold(tables, entry_list, people):
    """A vendor that is a person on the UKG roster is an employee paid through
    AP. The schedules name the line, not the person: the document numbers on
    the line are enough to find it in NetSuite."""
    # A roster name can also sit inside a line's description: a bill that says
    # who ordered it. Those are replaced in place.
    names = sorted({"%s %s" % key for key in people}, key=len, reverse=True)
    inline = re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b",
                        re.IGNORECASE) if names else None

    def scrub_text(text):
        return inline.sub("[name withheld]", text) if inline and text else text

    def scrub(name):
        key = person_key(name)
        if key in people and " ".join(key) == " ".join(
                re.sub(r"[^a-z ]", " ", (name or "").lower()).split()):
            return WITHHELD
        return name
    for table in tables:
        for sec in table.get("sections", []):
            for row in sec.get("rows", []):
                if "vendor" in row:
                    original = row["vendor"]
                    row["vendor"] = scrub(original)
                    for flag in row.get("flags", []):
                        for k in ("why", "do"):
                            text = flag[k].replace(original, row["vendor"]) if original else flag[k]
                            flag[k] = scrub_text(text)
                for item in (row.get("detail") or {}).get("items", []):
                    item["vendor"] = scrub(item.get("vendor", ""))
                    item["text"] = scrub_text(item.get("text", ""))
    for entry in entry_list:
        for line in entry["lines"]:
            original = line.get("vendor", "")
            line["vendor"] = scrub(original)
            if original and line["vendor"] != original:
                entry["memo"] = entry["memo"].replace(original, WITHHELD)


def filer_names(gl):
    """Everyone who filed an expense report is an employee, whether or not the
    roster still lists them. A name of two words or more, so a one-letter
    placeholder in the name field is not withheld from every text."""
    return {(t.get("vendor_or_name") or t.get("vendor") or "").strip()
            for lines in gl.values() for t in lines
            if t.get("txn_type") == "Expense Report"
            and len((t.get("vendor_or_name") or t.get("vendor") or "").split()) >= 2}


def redact_run(run, people, filers=()):
    """The engine's own output rides in the console too: finding lines, metric
    contributors, the ratification worksheet. An expense report's name field is
    the employee who filed it, memos can carry email addresses, and with the
    roster any employee's full name is withheld wherever it appears, the
    schedules and their explanations included. Only text is changed; no figure
    is."""
    names = sorted({"%s %s" % key for key in people} | set(filers), key=len, reverse=True)
    inline = re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b",
                        re.IGNORECASE) if names else None

    def text(s):
        s = EMAIL.sub("[email removed]", s)
        return inline.sub("[name withheld]", s) if inline else s

    def walk(o):
        if isinstance(o, dict):
            if o.get("txn_type") == "Expense Report" and "vendor_or_name" in o:
                o["vendor_or_name"] = "Expense report"
            for k, v in o.items():
                if isinstance(v, str):
                    o[k] = text(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                if isinstance(v, str):
                    o[i] = text(v)
                else:
                    walk(v)
    for key, value in run.items():
        if key != "manifest":
            walk(value)


# ---------------------------------------------------------------- explanations

def _m(value):
    """$1,234.56, negatives in parentheses."""
    v = float(value or 0)
    s = "${:,.2f}".format(abs(v))
    return "(" + s + ")" if v < 0 else s


def _acct(accounts, code):
    name = (accounts.get(code) or {}).get("name", "")
    return (code + " " + name).strip() if code else ""


def _signed(v):
    return ("up " if v >= 0 else "down ") + _m(abs(v))


def explain(f, accounts, period):
    """Why a finding was raised, what to do, and its limit, in Simplified
    Technical English: short sentences, active voice, one fact each, and the
    figures of this finding rather than a description of the rule."""
    rule = f.get("rule_id", "")
    ev = f.get("evidence") or {}
    sc = ev.get("supporting_counts") or {}
    txns = txns_of(f)
    t0 = txns[0] if txns else {}
    amt = f.get("amount_at_risk") or 0
    vendor = (t0.get("vendor_or_name") or "").strip()
    A = lambda c: _acct(accounts, c)
    why, do, limit = [], [], []

    if rule == "T0.DUPLICATE_LINE":
        n = sc.get("occurrences") or len(txns)
        doc = t0.get("document_number", "")
        each = abs(num(t0.get("amount")))
        why = ["The ledger has %d lines with the same document number, account, department, "
               "amount and description." % n,
               "Document %s, %s, %s, %s each." % (doc, A(t0.get("account_code")),
                                                  t0.get("department") or "no department", _m(each))]
        do = ["Open document %s in NetSuite." % doc,
              "If the bill has one line for %s, delete the %d extra line%s in NetSuite and choose "
              "Fixed in NetSuite." % (_m(each), n - 1, "" if n == 2 else "s"),
              "If the vendor charged %d times, choose Cleared." % n]
    elif rule == "T0.ABERRANT_POSTING_LAG":
        lag = sc.get("lag_months")
        why = ["The transaction date is %s." % t0.get("date", ""),
               "The line is posted to %s, %s months later." % (f.get("period", period), lag),
               "Most bills post within one month."]
        do = ["Open the bill and read the service date.",
              "If the service was in %s, choose Cleared." % f.get("period", period),
              "If it was earlier, choose Cleared and write the service month in the note."]
    elif rule == "T1.DEPT_INCONSISTENCY":
        prior = sum(sc.values()) if sc else 0
        exp = quoted(ev.get("expected"), "department")
        obs = quoted(ev.get("observed"), "department")
        share = round(max(sc.values()) / prior * 100) if prior else None
        why = ["%s has %d earlier P&L line%s." % (vendor, prior, "" if prior == 1 else "s"),
               "%s%% of them are coded to %s." % (share, exp),
               "This month, %s is coded to %s." % (_m(amt), obs)]
        do = ["Open a line's PO in Coupa to see who requested it.",
              "Ask them which department used the purchase.",
              "If it was %s, reclass the lines to %s." % (exp, exp),
              "If it was %s, choose Cleared." % obs]
    elif rule == "T4.PO_ACCOUNT_MISMATCH":
        m = re.search(r"(\d+)% approved against account (\d{7})", ev.get("basis", ""))
        pct_, acct = (m.group(1), m.group(2)) if m else ("", "")
        posted = t0.get("account_code", "")
        why = ["%s has %s Coupa PO lines." % (vendor, sc.get("coupa_po_lines", "")),
               "%s%% of them use account %s." % (pct_, A(acct)),
               "The ledger has %s lines for %s on account %s." % (
                   sc.get("gl_lines", len(txns)), _m(sc.get("gl_exposure", amt)), A(posted))]
        do = ["Open a line's invoice in Coupa and read its account.",
              "If the ledger account is wrong, reclass the lines.",
              "If the ledger account is right, choose Cleared and tell procurement to correct the PO."]
    elif rule == "T3.IRC_274N_MEALS":
        total = re.search(r"\$[\d,.]+", ev.get("observed", ""))
        half = re.search(r"\$[\d,.]+", ev.get("expected", ""))
        why = ["The meals accounts have %s in %s lines." % (total.group(0) if total else "", sc.get("lines", "")),
               "The tax rule allows a deduction for 50% of business meals."]
        do = ["Read the lines. Take out any line that is not a business meal.",
              "Send the add-back, %s for these lines, to the tax preparer." % (half.group(0) if half else "half"),
              "Choose Cleared."]
    elif rule.startswith("T3.IRC_274B"):
        total = re.search(r"\$[\d,.]+", ev.get("observed", ""))
        n = sc.get("lines") or len(txns)
        why = ["%d line%s for %s %s gifts or branded items." % (
                   n, "" if n == 1 else "s", total.group(0) if total else "", "is" if n == 1 else "are"),
               "The tax rule allows $25 for each recipient."]
        do = ["Open the line's PO in Coupa to see who requested it.",
              "Ask them how many people got the items.",
              "Send the count to the tax preparer, and choose Cleared."]
    elif rule == "F3.ACCRUAL_RECEIPT":
        pos = re.findall(r"FL\d+", ev.get("basis", ""))
        why = ["Coupa shows goods received and not invoiced for %s." % _m(amt),
               ("The PO is %s." % pos[0]) if len(pos) == 1 else ("The POs are %s." % ", ".join(pos))]
        do = ["Open the PO in Coupa to see who requested it.",
              "Ask them if the goods arrived in %s." % period,
              "If yes, choose Entry booked. The accrual reverses on %s." % next_period_start(period),
              "If no, choose Cleared."]
    elif rule == "F5.MODEL_TIE":
        leaf_dept = f.get("title", "").split(":")[0]
        why = ["The forecast has %s for %s. The ledger has %s." % (
                   _m(f.get("model_amount")), leaf_dept, _m(f.get("actual_amount"))),
               "The difference is %s." % _m((f.get("model_amount") or 0) - (f.get("actual_amount") or 0))]
        for l in f.get("model_lines") or []:
            if l.get("description") and not l.get("vendor") and not l.get("po_number"):
                why.append('Forecast line %s, "%s", is %s and has no vendor and no PO.' % (
                    l.get("line_ref"), l["description"], _m(l.get("amount"))))
        booked = bool((f.get("correction") or {}).get("entry"))
        do = ["Open the forecast line in the workbook.",
              ("If the ledger is missing this spend, choose Entry booked." if booked else
               "If the ledger is missing this spend, choose Follow up and ask the preparer for the entry."),
              "If the forecast is wrong, choose Cleared and tell FP&A."]
    elif rule == "F6.ACCRUAL_PATTERN":
        obs = ev.get("observed", "")
        mm = re.search(r"average of (\$[\d,.]+) \((.+)\)", obs)
        why = ["%s billed %s in %s." % ((f.get("title") or "").split(":")[0],
                                         _m((f.get("correction") or {}).get("current", "0").replace("$", "").replace(",", "")),
                                         period)]
        if mm:
            why.append("The average of the last three months is %s: %s." % (mm.group(1), mm.group(2)))
        why.append("Coupa has no line for this vendor this month.")
        do = ["Ask the budget owner if the vendor did work in %s." % period,
              "If yes, choose Entry booked. It accrues %s and reverses next month." % _m(amt),
              "If no, choose Cleared."]
        if (f.get("confidence") or 0) < 0.5:
            do.insert(1, "The average comes from one invoice, so also ask if that invoice was a one-time charge.")
    elif rule == "F7.REVENUE_IN_EXPENSE":
        why = ["%s %s is a customer invoice." % (t0.get("txn_type", ""), t0.get("document_number", "")),
               "It credits %s by %s." % (A(t0.get("account_code")), _m(abs(num(t0.get("amount"))))),
               "Customer invoices go to revenue or receivables, not to expense."]
        do = ["If the invoice charges a cost back to a customer, choose Entry booked. It moves the credit "
              "to 4001003 Revenue - Cost Reimbursement.",
              "If Serif nets this charge against the cost on purpose, choose Cleared."]
    elif rule == "F8.VENDOR_DROPPED":
        prev = (f.get("correction") or {}).get("proposed", "")
        why = ["Journal %s for %s has no vendor." % (t0.get("document_number", ""), _m(abs(num(t0.get("amount")))))]
        cn = f.get("confidence_note", "")
        mm = re.search(r"billed by (.+?) to (\d{7}) in (\w+ \d{4})", cn)
        if mm:
            why.append("%s billed the same amount to prepaid account %s in %s." % (
                mm.group(1), A(mm.group(2)), mm.group(3)))
            why.append("This journal looks like the monthly release of that prepaid.")
        else:
            why.append("Earlier lines with the same account, department and amount name %s." % prev)
        do = ["Ask the preparer of journal %s to add %s as the name, and choose Follow up." % (
                  t0.get("document_number", ""), prev),
              "If the journal needs no name, choose Cleared."]
    elif rule == "F9.PREPAID":
        c = f.get("correction") or {}
        why = []
        mm = re.search(r"in (\d+) of the last (\d+) months", ev.get("basis", ""))
        if mm:
            why.append("The vendor did not bill this account in the last %s months." % mm.group(2)
                       if mm.group(1) == "0" else
                       "The vendor billed this account in %s of the last %s months." % (mm.group(1), mm.group(2)))
        if amt < PREPAID:
            why.append("It is under the %s prepaid threshold, so it stays expense unless related "
                       "charges for the same service bring it over." % "${:,.0f}".format(PREPAID))
        do = ["Read the invoice for the service period.",
              "If the service continues after %s, move the bill to %s and release it monthly over "
              "the service period." % (period, c.get("proposed", "")),
              "If it does not, choose Cleared."]
    elif rule == "F10.CAPITALIZE":
        c = f.get("correction") or {}
        why = ["%s is an account the asset policy reviews for capital purchases." % c.get("current", "")]
        place = c.get("placement") or {}
        if amt < CAPITALIZATION:
            why.append("It is under the %s capitalization threshold, so it stays expense "
                       "unless it is part of a larger asset." % "${:,.0f}".format(CAPITALIZATION))
        if place.get("kind") != "in_service":
            why.append(place.get("why", ""))
        do = ["Read the bill.",
              "If it buys an item that lasts more than one year, capitalize it to %s." % c.get("proposed", ""),
              "If it does not, choose Cleared.",
              place.get("ask", "")]
        do = [x for x in do if x]
    else:
        return None
    return {"why": " ".join(x for x in why if x), "do": " ".join(do), "limit": " ".join(limit)}


# ---------------------------------------------------------------- main

def build_views(run, args):
    inputs = Inputs()
    manifest = run["manifest"]
    period = manifest.get("period", "")
    findings = run.get("findings", [])

    gl, gl_files = sources.read_gl(args.gl or [])
    for f in gl_files:
        inputs.add("netsuite_gl", f["path"], f["rows"])
    month = lambda back: gl.get(sources.shift(period, -back), []) if period else []
    current, prior, prior2, prior_year = (load_gl(month(b)) for b in (0, 1, 2, 12))
    plan_rows, budget_rows = [], []
    if args.plan:
        every_line = [t for lines in gl.values() for t in lines]
        plan_rows = sources.read_forecast(args.plan, every_line, args.plan_vintage)[1]["prior"]
        budget_rows = sources.aggregate(plan_rows)
        inputs.add("forecast_workbook", args.plan, len(plan_rows))
    coupa = load_coupa(args.coupa, inputs)
    people, dept_codes, staff = load_roster(args.roster, inputs)
    # The code mapping on its own carries no personal data, so it can be supplied
    # without the roster. The roster's own reading wins where both are given.
    if args.dept_codes:
        rows = read_csv(args.dept_codes)
        inputs.add("coupa_dept_codes", args.dept_codes, len(rows))
        for row in rows:
            code = (row.get("coupa_dept_code") or "").strip()
            name = (row.get("gl_department_name") or "").strip()
            if code and name and code not in dept_codes:
                dept_codes[code] = {"department": name,
                                    "source": row.get("source") or "mapping file"}

    vintage = ""
    for rows, key in ((plan_rows, "budget_version"), (budget_rows, "budget_version")):
        if rows and rows[0].get(key):
            vintage = rows[0][key]
            break

    extra = [(r.get("account_code"), r.get("account_leaf")) for r in plan_rows + budget_rows]
    for t in (run.get("tables") or []):
        for sec in t.get("sections", []):
            for row in sec.get("rows", []):
                extra.append((row.get("account_code"), row.get("account_leaf")))
    for f in findings:
        for t in txns_of(f):
            extra.append((t.get("account_code"), t.get("account_leaf")))
        subject = (f.get("correction") or {}).get("subject", "")
        match = re.match(r"^(\d{7})\s+(.+?)(?:\s+/\s+.+)?$", subject)
        if match:
            extra.append((match.group(1), match.group(2)))
        for code, name in re.findall(r"(?:Dr|Cr)\s+(\d{7})\s+([^/]+?)(?=\s*/|\s+for\s)",
                                     (f.get("correction") or {}).get("entry", "")):
            extra.append((code, name.strip()))
    accounts = account_book(current, prior, prior_year, extra=extra)

    periods = {"current": period,
               "prior": manifest.get("prior_period") or (prior[0]["period"] if prior else ""),
               "prior_year": manifest.get("prior_year_period")
               or (prior_year[0]["period"] if prior_year else ""),
               "prior2": prior2[0]["period"] if prior2 else ""}

    tables, dark = [], []
    uc = "flux" if any(f.get("rule_id", "").startswith("F") for f in findings) else "coding"

    if uc == "flux":
        po_depts = po_departments(coupa, dept_codes)
        for table in (model_tie(findings), accrual_schedule(findings, period, po_depts),
                      prepaid_schedule(findings, run), reclass_schedule(findings)):
            if table:
                tables.append(table)
        if current and budget_rows:
            tables.append(dept_plan(current, budget_rows, period, vintage))
        else:
            dark.append({"id": "dept_plan", "title": "Actual vs. Budget by department",
                         "needs": "the GL detail and the budget feed"})
        if staff and current:
            tables.append(payroll_hris(current, staff, period))
    supplied = []

    if uc == "coding":
        if current and (prior or prior_year):
            universe = {l["vendor"] for l in current + prior + prior_year if l["vendor"]}
            plan_tbl = (vendor_plan(current, plan_rows, period, vintage, {}, universe)
                        if plan_rows else None)
            req_tbl = requester(current, coupa, period, people, dept_codes) if people and coupa else None
            requested = defaultdict(lambda: defaultdict(int))
            for row in coupa:
                dept = people.get(person_key(row.get("requester") or "")) if row.get("period") == period else None
                if dept:
                    requested[norm_vendor(row["supplier"])][dept] += 1
            po_accounts = defaultdict(lambda: defaultdict(float))
            for row in coupa:
                if row.get("account"):
                    po_accounts[norm_vendor(row["supplier"])][row["account"]] += abs(row.get("amount") or 0)
            scr = screens(current, prior, prior2, accounts, period)
            tables.append(vendors_table(current, prior, prior2, prior_year, periods, findings,
                                        accounts, plan_tbl, req_tbl, scr, requested, vintage,
                                        po_accounts))
            if scr is None:
                dark.append({"id": "screens", "title": "Prepaid and capital flags on vendors",
                             "needs": "serif_uc2_flux.py beside serif_views.py"})
            if not plan_rows:
                dark.append({"id": "vendor_plan", "title": "Planned coding on vendors",
                             "needs": "the forecast's vendor lines"})
            if not req_tbl:
                dark.append({"id": "requester", "title": "Requester department on vendors",
                             "needs": "the UKG roster and the Coupa export"})
        else:
            dark.append({"id": "vendors", "title": "Vendors",
                         "needs": "the current and prior-period GL detail"})
        checks = ledger_checks(findings)
        if checks:
            tables.append(checks)
        if staff and current:
            tables.append(payroll_hris(current, staff, period))
            supplied.append({"feed": "hris_headcount.csv", "label": "HRIS roster",
                             "tests": ["Payroll vs. HRIS", "Requester department on vendors"]})
        elif not staff:
            dark.append({"id": "payroll_hris", "title": "Payroll vs. HRIS",
                         "needs": "the UKG roster"})
    elif staff:
        supplied.append({"feed": "hris_headcount.csv", "label": "HRIS roster",
                         "tests": ["Names withheld from line descriptions"]})

    js_entries = entries(findings, period, {
        r["finding_id"]: r["department"]
        for t in tables if t["id"] == "accrual"
        for s in t["sections"] for r in s["rows"] if r["department"]},
        gl_dims(t for lines in gl.values() for t in lines))
    if people and not getattr(args, "keep_names", False):
        withhold(tables, js_entries, people)

    shown = {(t.get("document_number") or "").strip() for f in findings for t in txns_of(f)}
    shown |= {l["document_number"] for l in current + prior + prior2 + prior_year}
    doc_lines = [t for lines in gl.values() for t in lines
                 if (t.get("document_number") or "").strip() in shown]
    pos = set(re.findall(r"\bFL\d{9}\b", json.dumps([findings, tables])))
    link_ids = sources.read_link_ids(args.netsuite_ids)
    if link_ids:
        off = sources.link_ids_tie(link_ids, gl)
        if off:
            print("NetSuite link IDs set aside: their debits do not tie to the GL export for "
                  + ", ".join(off) + ". Run the query again for the same period.")
            link_ids = []
        else:
            for path in args.netsuite_ids:
                inputs.add("netsuite_link_ids", path, sum(1 for _ in open(path, encoding="utf-8-sig")) - 1)

    extra_views = {}
    if uc == "flux" and current:
        extra_views["dept_months"] = dept_months(current, prior, periods)
        if staff:
            extra_views["payroll"] = payroll_analytics(current, prior, staff, period,
                                                       names=getattr(args, "keep_names", False))
    if getattr(args, "balance_sheet", None):
        # A report that ends before the month (last month's, say) leaves the view out
        # rather than stopping the run.
        try:
            extra_views["balance_sheet"] = balance_sheet(args.balance_sheet, period, inputs)
        except SystemExit as stop:
            if "no column for" not in str(stop):
                raise                      # a report that cannot be read says why
            dark.append({"id": "balance_sheet", "title": "Balance sheet",
                         "needs": f"the NetSuite Balance Sheet report through {period} "
                                  f"({os.path.basename(args.balance_sheet)} ends before it)"})
    elif uc == "flux":
        dark.append({"id": "balance_sheet", "title": "Balance sheet",
                     "needs": "the NetSuite Balance Sheet report (--balance-sheet)"})

    return {
        **extra_views,
        "version": VIEWS_VERSION,
        "inputs": inputs.files,
        "links": sources.links(doc_lines, coupa, pos, link_ids),
        "answered_with": lag_twins(findings),
        "accounts": accounts,
        "coupa_departments": dept_codes,
        "fix_floor": FLOOR,
        "tables": tables,
        "not_built": dark,
        "feeds_supplied": supplied,
        "explain": {f["finding_id"]: x for f in findings
                    for x in [explain(f, accounts, period)] if x},
        "entries": js_entries,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Add controller tables to a Serif run artifact.")
    ap.add_argument("run_json")
    ap.add_argument("--gl", nargs="+", metavar="EXPORT",
                    help="NetSuite Custom General Ledger exports (.xls), as NetSuite writes them")
    ap.add_argument("--plan", help="rolling forecast workbook whose PRIOR cut is the plan (.xlsx)")
    ap.add_argument("--plan-vintage", dest="plan_vintage", default="plan",
                    help="label for the plan cut, eg 2026-06")
    ap.add_argument("--coupa", help="Coupa PO line export (.csv), as Coupa writes it")
    ap.add_argument("--netsuite-ids", dest="netsuite_ids", nargs="+", metavar="CSV",
                    help="NetSuite link IDs query results (netsuite_link_ids_<period>.csv), for links only")
    ap.add_argument("--roster", help="UKG full roster export (.csv)")
    ap.add_argument("--keep-names", dest="keep_names", action="store_true",
                    help="keep employee names and pay in the run: no redaction, and the roster "
                         "under each department in the payroll detail. For the console layout "
                         "Serif's accounting team reads in full (--layout ui-update)")
    ap.add_argument("--balance-sheet", dest="balance_sheet",
                    help="NetSuite Balance Sheet report, monthly columns (.xls), as NetSuite writes it")
    ap.add_argument("--dept-codes", dest="dept_codes",
                    help="Serif's confirmed Coupa department code mapping, coupa_dept_code_mapping.csv")
    args = ap.parse_args(argv)
    # An optional report given as a pattern the shell found no file for
    # (netsuite_balance_sheet_*.xls) was not supplied: its view says so.
    if args.balance_sheet and "*" in args.balance_sheet and not os.path.exists(args.balance_sheet):
        args.balance_sheet = None

    for path in [args.run_json] + (args.gl or []) + [p for p in (args.plan, args.coupa, args.roster,
                                                                  args.dept_codes, args.balance_sheet) if p]:
        if not os.path.exists(path):
            sys.exit("Not found: " + path)
    with open(args.run_json, encoding="utf-8") as handle:
        run = json.load(handle)
    people = load_roster(args.roster, Inputs())[0] if args.roster else {}
    filers = filer_names(sources.read_gl(args.gl)[0]) if args.gl else set()
    # The schedules are built from the findings, so the findings are redacted first:
    # an expense report's name field would otherwise reach a vendor row or an
    # explanation on a first run. The finished run is redacted again.
    # --keep-names: the team reading the console sees the ledger in full, names
    # and emails included, so nothing is redacted.
    if not args.keep_names:
        redact_run(run, people, filers)
    run["views"] = build_views(run, args)
    if not args.keep_names:
        redact_run(run, people, filers)
    with open(args.run_json, "w", encoding="utf-8") as handle:
        json.dump(run, handle, indent=2)
    views = run["views"]
    print("Views " + VIEWS_VERSION + " added to " + args.run_json)
    for table in views["tables"]:
        count = sum(len(s["rows"]) for s in table["sections"])
        print("  %-36s %5d rows" % (table["title"], count))
    for table in views["not_built"]:
        print("  %-36s not built: needs %s" % (table["title"], table["needs"]))
    balanced = sum(1 for e in views["entries"] if e["balanced"])
    print("  %-36s %5d (%d balanced)" % ("Proposed Journal Entries", len(views["entries"]), balanced))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
