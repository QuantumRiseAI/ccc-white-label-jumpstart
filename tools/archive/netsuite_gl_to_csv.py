#!/usr/bin/env python3
"""Slice Serif's NetSuite Custom General Ledger export into per-period CSVs.

The raw export is SpreadsheetML (XML with an `.xls` extension), ~58 MB and ~44k rows.
That is too large to upload to a Claude Project, so this splits it into one CSV per
accounting period plus a per-period account activity summary.

Usage:
    python3 netsuite_gl_to_csv.py <gl_export.xls> --out <dir> [--period "Aug 2026" ...]

With no --period, every period in the file is written.

Outputs, per period:
    netsuite_gl_<period>.csv                transaction detail, normalized columns
    netsuite_account_activity_<period>.csv   net movement by account and department

The activity file is NOT a trial balance. It sums only the transactions posted in that
period, so for P&L accounts it equals the period's expense or income, which is what flux
analysis needs. For balance sheet accounts it is the period movement, not the ending
balance, because no prior-period carryforward is included.

Notes on the source format:
  * Rows 0-5 are report headers; row 6 is the column header; data starts at row 7.
  * The export contains TWO columns named "ProjectID: Name". The second one holds the
    real values, so columns are read positionally, never by header name.
  * Amounts arrive as separate Debit and Credit strings; `amount` below is Debit - Credit.
"""

import argparse
import csv
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict

NS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
HEADER_ROW = 6

# Positional map of the source export. Update here if NetSuite's saved search changes.
COLS = {
    "account_path": 0,
    "txn_type": 1,
    "date": 2,
    "document_number": 3,
    "name": 4,
    "debit": 5,
    "credit": 6,
    "balance": 7,
    "account_name": 8,
    "period": 9,
    "department": 10,
    "program": 11,
    "project_unused": 12,
    "project": 13,
    "subsidiary": 14,
    "description": 15,
    "memo": 16,
}

OUT_FIELDS = [
    "period", "date", "txn_type", "document_number", "vendor_or_name",
    "account_path", "account_code", "account_leaf", "amount", "debit", "credit",
    "department", "project", "program", "subsidiary", "description", "memo",
]


def cell_values(row):
    out = []
    for cell in row.findall("ss:Cell", NS):
        data = cell.find("ss:Data", NS)
        out.append("".join(data.itertext()).strip() if data is not None else "")
    return out


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def split_account(path):
    """'6000000 - Operating Expenses:6410000 - Lab Supplies' -> ('6410000', 'Lab Supplies')."""
    leaf = path.split(":")[-1]
    match = re.match(r"\s*(\d+)\s*-\s*(.*)", leaf)
    return (match.group(1), match.group(2).strip()) if match else ("", leaf.strip())


def read_rows(path):
    root = ET.fromstring(open(path, encoding="utf-8", errors="replace").read())
    worksheet = root.find(".//ss:Worksheet", NS)
    if worksheet is None:
        raise SystemExit(f"No worksheet found in {path}")
    rows = worksheet.findall(".//ss:Row", NS)
    header = cell_values(rows[HEADER_ROW])
    if header[0] != "Account":
        raise SystemExit(
            f"Unexpected header at row {HEADER_ROW}: {header[:3]}. "
            "The saved search layout changed, update COLS before rerunning."
        )
    for row in rows[HEADER_ROW + 1:]:
        values = cell_values(row)
        if len(values) < len(COLS):
            continue  # subtotal / blank / footer row
        yield values


def normalize(values):
    get = lambda key: values[COLS[key]]
    code, leaf = split_account(get("account_path"))
    debit, credit = to_float(get("debit")), to_float(get("credit"))
    return {
        "period": get("period"),
        "date": get("date")[:10],
        "txn_type": get("txn_type"),
        "document_number": get("document_number"),
        "vendor_or_name": get("name"),
        "account_path": get("account_path"),
        "account_code": code,
        "account_leaf": leaf,
        "amount": round(debit - credit, 2),
        "debit": debit,
        "credit": credit,
        "department": get("department"),
        "project": get("project"),
        "program": get("program"),
        "subsidiary": get("subsidiary"),
        "description": get("description"),
        "memo": get("memo"),
    }


def slug(period):
    return period.lower().replace(" ", "")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gl_export", help="NetSuite Custom General Ledger .xls (SpreadsheetML)")
    parser.add_argument("--out", default=".", help="output directory")
    parser.add_argument("--period", action="append", default=[],
                        help='accounting period to extract, e.g. "Aug 2026"; repeatable')
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    wanted = set(args.period)

    by_period = defaultdict(list)
    skipped = 0
    for values in read_rows(args.gl_export):
        record = normalize(values)
        if not record["period"]:
            skipped += 1
            continue
        if wanted and record["period"] not in wanted:
            continue
        by_period[record["period"]].append(record)

    if not by_period:
        raise SystemExit(f"No rows matched. Requested periods: {sorted(wanted) or 'all'}")

    for period, records in sorted(by_period.items()):
        detail_path = os.path.join(args.out, f"netsuite_gl_{slug(period)}.csv")
        with open(detail_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=OUT_FIELDS)
            writer.writeheader()
            writer.writerows(records)

        activity = defaultdict(float)
        for record in records:
            key = (record["account_code"], record["account_leaf"],
                   record["account_path"], record["department"])
            activity[key] += record["amount"]

        activity_path = os.path.join(
            args.out, f"netsuite_account_activity_{slug(period)}.csv")
        with open(activity_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["period", "account_code", "account_leaf",
                             "account_path", "department", "period_activity"])
            for (code, leaf, path, dept), total in sorted(activity.items()):
                writer.writerow([period, code, leaf, path, dept, round(total, 2)])

        total = sum(r["amount"] for r in records)
        print(f"{period:>9}  {len(records):>6,} lines  net {total:>15,.2f}  "
              f"-> {os.path.basename(detail_path)}, {os.path.basename(activity_path)}")

    if skipped:
        print(f"\nSkipped {skipped} rows with no accounting period.")


if __name__ == "__main__":
    main()
