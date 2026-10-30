#!/usr/bin/env python3
"""Slice the client's Coupa PO line export into per-period CSVs with parsed coding segments.

The raw export is one wide CSV (103 columns, 9,571 lines for calendar 2026). Most columns
are empty or irrelevant, two are actively misleading, and the GL coding lives packed inside
a single string. This normalizes it.

Usage:
    python3 coupa_po_to_csv.py <coupa_export.csv> --out <dir> [--period "Aug 2026" ...]

With no --period, every period present is written.

Output per period: coupa_po_lines_<period>.csv

Traps in the raw export, all handled here:

  * The `Department` column is EMPTY on every row. The real department code is the third
    segment of the `Account` string. Reading `Department` gives nothing.
  * The `Period` column reads 'None' on every row. Period is derived from `Order Date`.
  * `Account` is a packed segment string: 97-<gl account>-<dept>-<seg3>-<seg4>, with an
    occasional 6th segment. Segment 3 is blank or '68'; segment 4 is '4' or '66'. Neither
    is a department code, see the note in the mapping template.
  * Amount fields carry thousands separators ("2,772.80"), so a bare float() silently
    returns 0.0 and understates totals by roughly 10x.
  * `Received`, `Active Invoiced` and `Approved Invoiced` are QUANTITIES, not amounts.
    Multiplying a quantity by `Price` does not give a reliable value, because some lines
    use bulk-price units; pro-rating `Line Total` does.

Two different "open" populations, which must not be confused:

  * is_open_commitment      ordered but not yet fully received. A PO backlog. NOT an accrual.
  * received_not_invoiced_* received but not yet invoiced. THIS is the accrual population,
                           since expense belongs in the period goods or services arrive.
"""

import argparse
import csv
import os
import re
import sys
from collections import defaultdict

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Column order matches the files produced on 2026-09-16 so existing agent instructions
# stay valid. Everything from approved_invoiced onward is additive.
OUT_FIELDS = [
    "period", "order_date", "po_number", "line", "supplier", "supplier_id",
    "order_status", "line_status", "item_name", "line_total", "currency",
    "gl_account_code", "coupa_dept_code", "coupa_seg3", "coupa_seg4", "account_raw",
    "qty", "received", "price", "commodity", "uom", "line_owner", "created_by",
    "need_by", "is_open_commitment",
    "approved_invoiced", "active_invoiced",
    "received_not_invoiced_qty", "received_not_invoiced_value",
]


def num(value):
    """Parse an amount or quantity, tolerating thousands separators and blanks."""
    text = (value or "").replace(",", "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def parse_date(value):
    """'9/10/2026' -> ('2026-09-10', 'Sep 2026'). Returns ('', '') if unparseable."""
    match = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", value or "")
    if not match:
        return "", ""
    month, day, year = (int(g) for g in match.groups())
    if not 1 <= month <= 12:
        return "", ""
    return f"{year:04d}-{month:02d}-{day:02d}", f"{MONTHS[month - 1]} {year}"


def split_account(raw):
    """97-6410000-73--4 -> ('6410000', '73', '', '4'). Positional; never by header name."""
    parts = (raw or "").split("-")
    get = lambda i: parts[i].strip() if len(parts) > i else ""
    return get(1), get(2), get(3), get(4)


def clean_supplier(raw):
    """'Fisher Scientific (Fisher Scientific|496|Labs)' -> 'Fisher Scientific'.

    The id embedded in this string is a site or address id, not the supplier id. Take the
    supplier id from the dedicated `Supplier id` column instead.
    """
    return (raw or "").strip().split(" (")[0].strip()


def normalize(row):
    order_date, period = parse_date(row.get("Order Date (Header)", ""))
    account_raw = (row.get("Account") or "").strip()
    gl_account, dept, seg3, seg4 = split_account(account_raw)
    supplier = clean_supplier(row.get("Supplier", ""))

    qty = num(row.get("Qty"))
    received = num(row.get("Received"))
    approved_invoiced = num(row.get("Approved Invoiced"))
    line_total = num(row.get("Line Total"))
    line_status = (row.get("Line Status") or "").strip()

    # Ordered but not yet fully received, on a PO that is still live. A commitment,
    # not an accrual. A cancelled or soft-closed header is not an open commitment even
    # if the line never got a receipt.
    order_status = (row.get("Order Status (Header)") or "").strip()
    is_open = 1 if (line_status in ("created", "partially_received")
                    and order_status == "Issued") else 0

    # Received but not yet invoiced. The accrual population.
    open_qty = max(received - approved_invoiced, 0.0)
    if qty > 0 and open_qty > 0:
        # Pro-rate the line total. Quantity x Price is unreliable on bulk-price lines.
        open_value = round(line_total * min(open_qty, qty) / qty, 2)
    else:
        open_value = 0.0

    return {
        "period": period,
        "order_date": order_date,
        "po_number": (row.get("PO Number (Header)") or "").strip(),
        "line": (row.get("Line") or "").strip(),
        "supplier": supplier,
        "supplier_id": (row.get("Supplier id") or "").strip(),
        "order_status": order_status,
        "line_status": line_status,
        "item_name": (row.get("Item") or "").strip(),
        "line_total": line_total,
        "currency": (row.get("Currency") or "").strip(),
        "gl_account_code": gl_account,
        "coupa_dept_code": dept,
        "coupa_seg3": seg3,
        "coupa_seg4": seg4,
        "account_raw": account_raw,
        "qty": qty,
        "received": received,
        "price": num(row.get("Price")),
        "commodity": (row.get("Commodity") or "").strip(),
        "uom": (row.get("UOM") or "").strip(),
        "line_owner": (row.get("Line Owner") or "").strip(),
        "created_by": (row.get("Created By") or "").strip(),
        "need_by": parse_date(row.get("Need By", ""))[0],
        "is_open_commitment": is_open,
        "approved_invoiced": approved_invoiced,
        "active_invoiced": num(row.get("Active Invoiced")),
        "received_not_invoiced_qty": open_qty,
        "received_not_invoiced_value": open_value,
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("coupa_export", help="raw Coupa PO line export (.csv)")
    parser.add_argument("--out", default=".", help="output directory")
    parser.add_argument("--period", action="append", default=[],
                        help='period to extract, e.g. "Aug 2026"; repeatable')
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    wanted = set(args.period)

    with open(args.coupa_export, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if "Account" not in (reader.fieldnames or []):
            sys.exit("No 'Account' column found. This does not look like the Coupa PO export.")
        records = [normalize(row) for row in reader]

    undated = sum(1 for r in records if not r["period"])
    by_period = defaultdict(list)
    for record in records:
        if record["period"] and (not wanted or record["period"] in wanted):
            by_period[record["period"]].append(record)

    if not by_period:
        sys.exit(f"No rows matched. Requested: {sorted(wanted) or 'all'}")

    grand = defaultdict(float)
    for period, rows in sorted(by_period.items(), key=lambda kv: kv[1][0]["order_date"]):
        path = os.path.join(args.out, f"coupa_po_lines_{period.replace(' ', '').lower()}.csv")
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=OUT_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

        total = sum(r["line_total"] for r in rows)
        commitment = sum(r["line_total"] for r in rows if r["is_open_commitment"])
        accrual = sum(r["received_not_invoiced_value"] for r in rows)
        grand["lines"] += len(rows)
        grand["total"] += total
        grand["commitment"] += commitment
        grand["accrual"] += accrual
        print(f"{period:>9}  {len(rows):>5,} lines  "
              f"total ${total:>12,.0f}  open commit ${commitment:>11,.0f}  "
              f"recd-not-invcd ${accrual:>10,.0f}")

    print(f"{'TOTAL':>9}  {int(grand['lines']):>5,} lines  "
          f"total ${grand['total']:>12,.0f}  open commit ${grand['commitment']:>11,.0f}  "
          f"recd-not-invcd ${grand['accrual']:>10,.0f}")

    no_qty = sum(1 for r in records if r["qty"] <= 0)
    if no_qty:
        print(f"\n{no_qty} lines have no quantity; their received-not-invoiced value "
              f"cannot be pro-rated and is reported as 0.")
    if undated:
        print(f"{undated} lines have no parseable order date and were written to no period.")


if __name__ == "__main__":
    main()
