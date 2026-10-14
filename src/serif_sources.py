#!/usr/bin/env python3
"""Read Serif's system exports exactly as the systems produce them.

    netsuite GL    the Custom General Ledger saved search, exported as .xls
                   (SpreadsheetML) or saved as .xlsx, columns found by name. One
                   export or several; each month is read from the one export that
                   holds it.
    coupa          a PO line report as a .csv: the export with all available
                   columns, or the Coupa Data Pull (PO Lines) report
    forecast       the rolling forecast workbook, as an .xlsx
    balance sheet  the NetSuite Balance Sheet report, monthly columns, exported as .xls
                   (SpreadsheetML)

    income stmt    the NetSuite Income Statement by month report, exported as .xls,
                   which the ledger is tied to account by account before a console
                   is built (python3 serif_sources.py tie --help)

Nothing is sliced, summarized or reshaped on disk. The engines and the schedules
call these readers and derive what they need in memory, so every figure traces to
a file a system produced.

Stdlib only. Python 3.9+.
"""

from __future__ import annotations

import csv
import datetime as dt
import os
import re
import sys
import zipfile
from collections import defaultdict
from xml.etree import ElementTree as ET

# Where the consoles' links open. NETSUITE_ACCOUNT is the account ID in the
# NetSuite address bar (1234567 in 1234567.app.netsuite.com); left blank, no
# NetSuite links are drawn.
COUPA_HOST = "aflagshipcompany.coupahost.com"
NETSUITE_ACCOUNT = "5602907"

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def period_key(period: str) -> tuple[int, int]:
    """'Aug 2026' -> (2026, 8), so periods sort as dates."""
    try:
        mon, year = period.split()
        return int(year), MONTH_NAMES.index(mon[:3]) + 1
    except (ValueError, AttributeError):
        return (0, 0)


def shift(period: str, months: int) -> str:
    """shift('Aug 2026', -1) -> 'Jul 2026'; shift('Aug 2026', -12) -> 'Aug 2025'."""
    year, month = period_key(period)
    if not year:
        raise SystemExit(f"Not a period: {period!r}. Write it as 'Sep 2026'.")
    index = year * 12 + (month - 1) + months
    return f"{MONTH_NAMES[index % 12]} {index // 12}"


def slug(period: str) -> str:
    return period.lower().replace(" ", "")


# ── NetSuite Custom General Ledger ──────────────────────────────────────────
#
# A few report-title rows, then the column header (its first cell is "Account"),
# then the data. NetSuite writes .xls (SpreadsheetML); an export opened and saved in
# Excel arrives as .xlsx. Both are read, and columns are found by header name, so a
# saved search with columns added or moved reads the same. Amounts arrive as
# separate Debit and Credit; `amount` is Debit - Credit.
#
# The export can carry TWO columns named "ProjectID: Name", and which one holds
# the project differs between saved searches. A line's project is the first of
# them naming a real project, else the first non-blank one.
#
# Optional columns, read when present: "Internal ID" (the NetSuite record a line
# belongs to), the bill's Coupa Transaction URL, and the line's Coupa PO number
# (custcol_coupa_po_num or "PO Number", eg FL087030260-1). A Coupa invoice address
# in any cell is carried as the line's link.

COUPA_INVOICE = "https://" + COUPA_HOST + "/invoices/"
SS = "{urn:schemas-microsoft-com:office:spreadsheet}"

# Field -> header names it is exported under, first match wins. Lower case.
GL_HEADERS = {
    "account_path": ("account",),
    "txn_type": ("type", "transaction type"),
    "date": ("date",),
    "document_number": ("document number",),
    "name": ("name",),
    "debit": ("debit", "amount (debit)"),
    "credit": ("credit", "amount (credit)"),
    "period": ("accounting period: name", "accounting period", "period"),
    "department": ("department: name", "department"),
    "program": ("program: name", "program"),
    "subsidiary": ("subsidiary: name", "subsidiary"),
    "description": ("description",),
    "memo": ("memo",),
}
GL_REQUIRED = ("account_path", "txn_type", "date", "document_number", "name", "debit",
               "credit", "period", "department")
PROJECT_HEADERS = ("projectid: name", "project: name", "projectid", "project")
NO_PROJECT = re.compile(r"^(|00 non-specific|non-specific|- no .* -)$", re.I)


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def split_account(path: str) -> tuple[str, str]:
    """'6000000 - Operating Expenses:6410000 - Lab Supplies' -> ('6410000', 'Lab Supplies')."""
    leaf = path.split(":")[-1]
    match = re.match(r"\s*(\d+)\s*-\s*(.*)", leaf)
    return (match.group(1), match.group(2).strip()) if match else ("", leaf.strip())


def _gl_sheet_rows(path: str):
    """Every row's cell values, as text, from either export format."""
    if zipfile.is_zipfile(path):
        zf = zipfile.ZipFile(path)
        part = next(iter(_sheet_map(zf).values()), "xl/worksheets/sheet1.xml")
        grid = _read_grid(zf, part, _shared_strings(zf))
        for number in sorted(grid):
            cells = grid[number]
            yield [cells.get(i, "") for i in range(max(cells) + 1)] if cells else []
        return
    try:
        for _, elem in ET.iterparse(path, events=("end",)):
            if elem.tag != SS + "Row":
                continue
            values, col = [], 0
            for cell in elem.findall(SS + "Cell"):
                # A cell may skip ahead with ss:Index (1-based) past empty cells.
                index = cell.get(SS + "Index")
                if index:
                    values.extend([""] * (int(index) - 1 - col))
                    col = int(index) - 1
                data = cell.find(SS + "Data")
                values.append("".join(data.itertext()).strip() if data is not None else "")
                col += 1
            yield values
            elem.clear()
    except ET.ParseError as error:
        raise SystemExit(f"{os.path.basename(path)} is not a NetSuite .xls or .xlsx export: {error}")


def _gl_rows(path: str, header=None):
    """Yield each data row's cell values, streaming an .xls so a large export fits in
    memory. The column header row is copied into `header` when one is passed."""
    seen = None
    for index, values in enumerate(_gl_sheet_rows(path)):
        if seen is None:
            if values and values[0].strip().lower() == "account":
                seen = values
                if header is not None:
                    header[:] = values
            elif index >= 30:
                break
            continue
        if any(values):
            yield values
    if seen is None:
        raise SystemExit(
            f"{os.path.basename(path)} has no column header starting with 'Account' in its "
            "first 30 rows: it is not the NetSuite Custom General Ledger export.")


def _gl_columns(path, header) -> dict:
    """Field -> column index, from the header names. Missing required columns stop the
    run with their names, rather than reading another column in their place."""
    names = [h.strip().lower() for h in header]
    cols = {}
    for field, options in GL_HEADERS.items():
        cols[field] = next((names.index(o) for o in options if o in names), None)
    missing = [GL_HEADERS[f][0] for f in GL_REQUIRED if cols[f] is None]
    if missing:
        raise SystemExit(
            f"{os.path.basename(path)} has no column for: {', '.join(missing)}. "
            f"Its columns are: {', '.join(h for h in header if h)}.")
    cols["projects"] = [i for i, h in enumerate(names) if h in PROJECT_HEADERS]
    cols["internal_id"] = next((i for i, h in enumerate(names) if h == "internal id"), None)
    cols["coupa_po"] = [i for i, h in enumerate(names)
                        if ("coupa" in h and re.search(r"\bpo\b", h)) or h == "po number"]
    cols["date_serial"] = zipfile.is_zipfile(path)
    return cols


def _gl_date(value: str, serial: bool) -> str:
    if serial and re.fullmatch(r"\d+(\.\d+)?", value or ""):
        return (EXCEL_EPOCH + dt.timedelta(days=int(float(value)))).isoformat()
    return (value or "")[:10]


def _gl_line(values, cols):
    get = lambda key: (values[cols[key]] if cols[key] is not None and cols[key] < len(values)
                       else "").strip()
    code, leaf = split_account(get("account_path"))
    debit, credit = _float(get("debit")), _float(get("credit"))
    projects = [values[i].strip() for i in cols["projects"] if i < len(values)]
    po = next((m.group(1) for i in cols["coupa_po"] if i < len(values)
               for m in [re.match(r"(FL\d{9})", values[i].strip())] if m), "")
    return {
        "period": get("period"), "date": _gl_date(get("date"), cols["date_serial"]),
        "txn_type": get("txn_type"),
        "document_number": get("document_number"), "vendor_or_name": get("name"),
        "account_path": get("account_path"), "account_code": code, "account_leaf": leaf,
        "amount": round(debit - credit, 2), "debit": debit, "credit": credit,
        "department": get("department"),
        "project": next((p for p in projects if not NO_PROJECT.match(p)),
                        next((p for p in projects if p), "")),
        "program": get("program"), "subsidiary": get("subsidiary"),
        "description": get("description"), "memo": get("memo"),
        "internal_id": (values[cols["internal_id"]].strip()
                        if cols["internal_id"] is not None and cols["internal_id"] < len(values)
                        else ""),
        "coupa_url": next((v.strip() for v in values if v.strip().startswith(COUPA_INVOICE)), ""),
        # 'FL087030260-1' is PO FL087030260, line 1; 'No PO' is none.
        "coupa_po": po,
    }


def read_gl(paths) -> tuple[dict, list[dict]]:
    """-> ({period: [line, ...]}, [{path, periods, rows}, ...]).

    A month held by two exports is refused rather than read twice or picked
    between: the two may differ, and a silent choice would change the findings.
    """
    by_period: dict[str, list[dict]] = {}
    owner: dict[str, str] = {}
    files = []
    for path in paths:
        if not os.path.exists(path):
            raise SystemExit(f"Not found: {path}")
        mine = defaultdict(list)
        header: list = []
        cols = None
        for values in _gl_rows(path, header):
            if cols is None:
                cols = _gl_columns(path, header)
            line = _gl_line(values, cols)
            if line["period"]:
                mine[line["period"]].append(line)
        for period, lines in mine.items():
            if period in owner:
                raise SystemExit(
                    f"{period} is in two NetSuite exports: {os.path.basename(owner[period])} "
                    f"and {os.path.basename(path)}. Pass exports that do not overlap.")
            owner[period] = path
            by_period[period] = lines
        files.append({"path": path, "periods": sorted(mine, key=period_key),
                      "rows": sum(len(v) for v in mine.values())})
    return by_period, files


def activity(lines) -> list[dict]:
    """Net movement by account and department for one period's lines.

    Not a trial balance: for P&L accounts it is the period's expense or income,
    which is what a flux reads; for balance sheet accounts it is the movement.
    """
    totals = defaultdict(float)
    for line in lines:
        totals[(line["account_code"], line["account_leaf"], line["account_path"],
                line["department"])] += line["amount"]
    return [{"period": lines[0]["period"] if lines else "", "account_code": code,
             "account_leaf": leaf, "account_path": path, "department": dept,
             "period_activity": round(total, 2)}
            for (code, leaf, path, dept), total in sorted(totals.items())]


# ── Coupa PO line export ────────────────────────────────────────────────────
#
# Traps in the raw export:
#   * `Department` is empty on every row. The department code is the third segment
#     of the packed `Account` string, 97-<gl account>-<dept>-<seg3>-<seg4>.
#   * `Period` reads 'None' on every row. The period comes from `Order Date`.
#   * Amounts carry thousands separators ("2,772.80").
#   * `Received`, `Active Invoiced` and `Approved Invoiced` are QUANTITIES. The
#     received-not-invoiced value pro-rates `Line Total`; Quantity x Price is
#     unreliable on bulk-price lines.
#
# Two populations that must not be confused:
#   is_open_commitment           ordered, not yet fully received. NOT an accrual.
#   received_not_invoiced_value  received, not yet invoiced. The accrual population.

def _num(value):
    text = (value or "").replace(",", "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _coupa_date(value):
    """'9/10/2026' -> ('2026-09-10', 'Sep 2026'), or ('', '')."""
    match = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", value or "")
    if not match:
        return "", ""
    month, day, year = (int(g) for g in match.groups())
    if not 1 <= month <= 12:
        return "", ""
    return f"{year:04d}-{month:02d}-{day:02d}", f"{MONTH_NAMES[month - 1]} {year}"


def _coupa_line(row):
    order_date, period = _coupa_date(row.get("Order Date (Header)", ""))
    account_raw = (row.get("Account") or "").strip()
    parts = account_raw.split("-")
    seg = lambda i: parts[i].strip() if len(parts) > i else ""
    qty, received = _num(row.get("Qty")), _num(row.get("Received"))
    approved_invoiced = _num(row.get("Approved Invoiced"))
    line_total = _num(row.get("Line Total"))
    line_status = (row.get("Line Status") or "").strip()
    order_status = (row.get("Order Status (Header)") or "").strip()
    # A cancelled or soft-closed header is not an open commitment even if the line
    # never got a receipt.
    is_open = 1 if (line_status in ("created", "partially_received")
                    and order_status == "Issued") else 0
    open_qty = max(received - approved_invoiced, 0.0)
    open_value = round(line_total * min(open_qty, qty) / qty, 2) if qty > 0 and open_qty > 0 else 0.0
    return {
        "period": period, "order_date": order_date,
        "po_number": (row.get("PO Number (Header)") or "").strip(),
        # Coupa's own record ID, the one its PO addresses use.
        "po_id": (row.get("PO ID") or "").strip(),
        "line": (row.get("Line") or "").strip(),
        # The id inside 'Name (Name|496|Labs)' is a site id, not the supplier id.
        "supplier": (row.get("Supplier") or "").strip().split(" (")[0].strip(),
        "supplier_id": (row.get("Supplier id") or "").strip(),
        "order_status": order_status, "line_status": line_status,
        "item_name": (row.get("Item") or "").strip(),
        "line_total": line_total, "currency": (row.get("Currency") or "").strip(),
        "gl_account_code": seg(1), "coupa_dept_code": seg(2),
        "coupa_seg3": seg(3), "coupa_seg4": seg(4), "account_raw": account_raw,
        "qty": qty, "received": received, "price": _num(row.get("Price")),
        "commodity": (row.get("Commodity") or "").strip(),
        "uom": (row.get("UOM") or "").strip(),
        "line_owner": (row.get("Line Owner") or "").strip(),
        "created_by": (row.get("Created By") or "").strip(),
        "requested_by": (row.get("Requested By (Header)") or "").strip(),
        "need_by": _coupa_date(row.get("Need By", ""))[0],
        "is_open_commitment": is_open,
        "approved_invoiced": approved_invoiced,
        "active_invoiced": _num(row.get("Active Invoiced")),
        "received_not_invoiced_qty": open_qty,
        "received_not_invoiced_value": open_value,
    }


# Coupa reports differ by who builds them. The full PO line export ("all available
# columns") and the shorter "Coupa Data Pull (PO Lines)" report name the same
# fields differently. Each is read under the full export's names; a field neither
# carries reads empty, and is listed so a check that needs it says it could not run.
COUPA_NAMES = {
    "PO Number (Header)": ("PO Number",),
    "Order Date (Header)": ("Order Date",),
    "Requested By (Header)": ("Requestor", "Requested By", "Requester"),
    "Line Total": ("Order Line Amount", "Amt", "Line Amount"),
    "Price": ("Unit Price",),
    "UOM": ("U/M", "Unit of Measure"),
    "Item": ("Item Name", "Description"),
}
# The fields the scripts read. Absent or empty in a pull, they are reported.
COUPA_USED = ("PO Number (Header)", "Order Date (Header)", "Supplier", "Account", "Line",
              "Line Total", "Item", "Qty", "Received", "Approved Invoiced", "Line Status",
              "Order Status (Header)", "Commodity", "Requested By (Header)", "PO ID")
_coupa_cache: dict = {}


def coupa_rows(path) -> tuple[list[dict], list[str]]:
    """-> (rows keyed by the full export's column names, the used fields this pull lacks
    or leaves empty). Stops when the file has no PO number or order date column."""
    if not os.path.exists(path):
        raise SystemExit(f"Not found: {path}")
    stamp = (os.path.abspath(path), os.path.getmtime(path))
    if stamp in _coupa_cache:
        return _coupa_cache[stamp]
    csv.field_size_limit(10_000_000)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = [(f or "").strip() for f in (reader.fieldnames or [])]
        raw = list(reader)
    rename = {}
    for name, others in COUPA_NAMES.items():
        if name not in fields:
            found = next((o for o in others if o in fields), None)
            if found:
                rename[name] = found
    for need in ("PO Number (Header)", "Order Date (Header)"):
        if need not in fields and need not in rename:
            raise SystemExit(
                f"{os.path.basename(path)} is not a Coupa PO line report: it has no "
                f"'{need}' column (or {', '.join(repr(o) for o in COUPA_NAMES[need])}). "
                f"Its columns are: {', '.join(f for f in fields if f)}.")
    rows = []
    for r in raw:
        row = {(k or "").strip(): v for k, v in r.items()}
        for name, found in rename.items():
            row[name] = row.get(found, "")
        # A report's closing totals row carries amounts but no PO number.
        if (row.get("PO Number (Header)") or "").strip():
            rows.append(row)
    absent = [f for f in COUPA_USED
              if not any((row.get(f) or "").strip() for row in rows)]
    _coupa_cache[stamp] = (rows, absent)
    return rows, absent


def read_coupa(path) -> list[dict]:
    """Every PO line in the report, with the period taken from its order date."""
    return [_coupa_line(row) for row in coupa_rows(path)[0]]


# ── Rolling forecast workbook ───────────────────────────────────────────────
#
# The workbook carries four tabs built on one grid: `EXT$_R&D`, `EXT$_G&A`, `LAB`
# and `OH`. Each holds the grid twice side by side: the CURRENT cut in columns
# 0-44 and the PRIOR cut in columns 51-95. The current cut's closed months are the
# posted actuals, so it reconciles the model to the ledger; the prior cut predates
# the month and is the plan.

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Excel's serial-date origin. 1899-12-30 rather than 12-31 absorbs the
# deliberate 1900 leap-year bug, so month-ends land on the right day.
EXCEL_EPOCH = dt.date(1899, 12, 30)

# Any number will convert to a date, so a header scan with no plausibility window
# reads money as dates: a cell holding 1,389,370 yields a date in the year 5704.
# Only serials inside this window are treated as month headers.
SERIAL_MIN = int((dt.date(1990, 1, 1) - EXCEL_EPOCH).days)
SERIAL_MAX = int((dt.date(2100, 1, 1) - EXCEL_EPOCH).days)

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# The line-item build tabs. All four share one grid. Only the two `EXT$_` tabs
# were named in the request; LAB and OH are the same shape and carry lab supplies
# and overhead, which together are most of R&D spend, so excluding them would
# report a budget of zero on accounts that are in fact budgeted.
DETAIL_SHEETS = ("EXT$_R&D", "EXT$_G&A", "LAB", "OH")

# Row 19 is the detail header, detail begins at row 20. Rows above it are a
# summary block that aggregates the detail, and including them would double count.
HEADER_ROW = 19
LABEL_FIELDS = ("num", "dept", "acct", "proj", "vendor", "po", "note1", "note2", "desc")
MONTHS_PER_BLOCK = 36


class Block:
    """One horizontal copy of the detail grid.

    `first_label` is the column of its `#` cell and `first_month` the column of
    its first month, so the nine label fields run from `first_label` and the
    months run from `first_month` for MONTHS_PER_BLOCK columns.
    """

    def __init__(self, key: str, first_label: int, first_month: int, trust_header: bool):
        self.key = key
        self.first_label = first_label
        self.first_month = first_month
        # Whether this block's own header row can be believed. See BLOCKS below.
        self.trust_header = trust_header

    def col(self, field: str) -> int:
        return self.first_label + LABEL_FIELDS.index(field)


# The current block's header is correct on all four tabs and is the only one that
# can be read directly.
#
# THE PRIOR BLOCK'S HEADER IS STALE AND MUST NOT BE READ. On `EXT$_R&D` it is
# correct, but on `EXT$_G&A`, `LAB` and `OH` it carries only 24 dates, running Jan
# 2024 to Dec 2025, which is a leftover from an older cut of the template. Reading
# it literally would misdate every prior-vintage number by twelve months, and the
# twelve unlabelled columns beyond it hold $24,589,211.80 of real values that
# would be dropped.
#
# The months are therefore taken POSITIONALLY from the current block, so column
# `first_month + k` carries the same period in both. That is verifiable rather
# than assumed: 2025 is closed and actualized in both vintages, so entity-aligned
# rows must agree on 2025 months, and the positional reading matches 100% of cells
# across all four tabs where the year-shifted reading matches as little as 69%.
# The workbook's own delta block also computes positionally.
BLOCKS = (
    Block("current", first_label=0, first_month=9, trust_header=True),
    Block("prior", first_label=51, first_month=60, trust_header=False),
)

BUDGET_FIELDS = ["fiscal_year", "period", "account_code", "account_leaf",
                 "department", "budget_amount", "budget_version",
                 "approved_by", "approved_date"]

LINE_FIELDS = ["fiscal_year", "period", "account_code", "account_leaf",
               "department", "project", "vendor", "po_number", "description",
               "note_1", "note_2", "amount", "source_tab", "line_ref",
               "budget_version", "vintage_block", "account_source"]

UNMAPPED_FIELDS = ["forecast_account", "reason", "source_tabs", "vintage_blocks",
                   "departments", "forecast_lines", "total_all_periods",
                   "gl_account_code", "gl_account_leaf"]

# Accounts outside the expense ranges. The build tabs are expense planning, so a
# revenue line here is unexpected and its sign convention cannot be checked
# against the ledger, which carries no revenue rows on these accounts. Carried
# through but called out rather than silently mixed into an expense budget.
EXPENSE_PREFIXES = ("6", "7", "8")


def _period_key(label: str) -> tuple[int, int]:
    """Chronological ordering for 'Aug 2026' style labels, which sort alphabetically."""
    month, _, year = label.partition(" ")
    return (int(year or 0), MONTHS.index(month) if month in MONTHS else 0)


# ── Reading the workbook ────────────────────────────────────────────────────

def _col_index(ref: str) -> int:
    """'BC12' -> 54. Column letters are base-26 with no zero digit."""
    letters = re.match(r"([A-Z]+)", ref).group(1)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.iter(NS + "t"))
            for si in root.findall(NS + "si")]


def _sheet_map(zf: zipfile.ZipFile) -> dict[str, str]:
    """Sheet display name -> its part name inside the archive."""
    rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    targets = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]*)"', rels))
    book = zf.read("xl/workbook.xml").decode("utf-8")
    out = {}
    for m in re.finditer(r'<sheet[^>]*?name="([^"]*)"[^>]*?r:id="(rId\d+)"', book):
        name = (m.group(1).replace("&amp;", "&").replace("&lt;", "<")
                .replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'"))
        target = targets.get(m.group(2), "")
        if target:
            out[name] = "xl/" + target.lstrip("/")
    return out


def _read_grid(zf: zipfile.ZipFile, part: str, strings: list[str]) -> dict[int, dict[int, str]]:
    """{row_number: {col_index: cell_text}}, cached values only.

    Formula cells are read through their cached `<v>`, which is what Excel last
    computed. A file saved with formulas but no cached results would read as empty
    here rather than wrong, and the account tie-out would catch that immediately.
    """
    root = ET.fromstring(zf.read(part))
    grid: dict[int, dict[int, str]] = {}
    for row in root.iter(NS + "row"):
        cells: dict[int, str] = {}
        for c in row.findall(NS + "c"):
            ref = c.get("r")
            if not ref:
                continue
            kind = c.get("t")
            if kind == "inlineStr":
                text = "".join(t.text or "" for t in c.iter(NS + "t"))
            else:
                v = c.find(NS + "v")
                if v is None or v.text is None:
                    continue
                text = strings[int(v.text)] if kind == "s" else v.text
            text = text.strip()
            if text:
                cells[_col_index(ref)] = text
        grid[int(row.get("r"))] = cells
    return grid


def _serial_to_period(serial: str) -> tuple[str, int] | None:
    """Excel serial -> ('Aug 2026', 2026), or None if it is not a plausible date."""
    try:
        value = int(float(serial))
    except (TypeError, ValueError):
        return None
    if not SERIAL_MIN <= value <= SERIAL_MAX:
        return None
    date = EXCEL_EPOCH + dt.timedelta(days=value)
    return f"{MONTHS[date.month - 1]} {date.year}", date.year


def _number(text: str) -> float | None:
    try:
        return float(text.replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None


def _norm(text: str) -> str:
    """Normalized account-name key.

    Dashes are folded because the prior vintage spells three G&A accounts with an
    en dash where the current vintage uses an ASCII hyphen ('FSP Charges – PBU'
    against 'FSP Charges - Origination'). Without this, $13.87M of prior-vintage
    spend matches nothing and is silently stranded.
    """
    text = (text or "").replace("–", "-").replace("—", "-")
    text = re.sub(r"\s*-\s*", " - ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


# ── Account mapping ─────────────────────────────────────────────────────────

def load_coa(zf, sheets, strings) -> dict[str, tuple[str, str]]:
    """Account name -> (code, name) as recorded on the workbook's COA tab."""
    part = sheets.get("COA")
    if not part:
        return {}
    lookup: dict[str, tuple[str, str]] = {}
    for cells in _read_grid(zf, part, strings).values():
        name, code = cells.get(1, ""), cells.get(2, "")
        if name and re.fullmatch(r"\d{7}", code):
            lookup.setdefault(_norm(name), (code, name))
    return lookup


def load_gl_accounts(lines) -> dict[str, tuple[str, str]]:
    """Account name -> (code, name) as the ledger currently uses them.

    A name carrying more than one code in the ledger is left out, because a
    forecast line naming it cannot be assigned to one code without guessing.
    """
    seen: dict[str, set[tuple[str, str]]] = {}
    for row in lines:
        code = (row.get("account_code") or "").strip()
        leaf = (row.get("account_leaf") or "").strip()
        if code and leaf:
            seen.setdefault(_norm(leaf), set()).add((code, leaf))
    return {name: sorted(pairs)[0] for name, pairs in seen.items() if len(pairs) == 1}


def load_account_map(gl_lines, coa: dict[str, tuple[str, str]]):
    """name -> (code, name, source), preferring the ledger over the workbook.

    THE WORKBOOK'S COA TAB IS BEHIND THE LEDGER. Of the 65 account names that
    appear in both, 21 carry a different code on the COA tab. Whole ranges have
    been renumbered:

        Rent or Lease of Buildings          COA 6501000 -> GL 6601000
        Building Operating Costs & CAM      COA 6509000 -> GL 6609000
        Sequencing Costs                    COA 6441000 -> GL 6501000
        Other External Research costs       COA 6446000 -> GL 6509000
        Travel                              COA 6610000 -> GL 6702000
        Depreciation - Lab Equipment        COA 8010000 -> GL 7110000

    The old rent code is the new sequencing code, so mapping through the COA tab
    would compare the rent forecast against sequencing actuals and report a large
    variance on both, which is worse than reporting nothing.

    The ledger therefore wins wherever it knows a name. The COA tab fills gaps,
    but ONLY where its code is not already occupied by a different ledger account:
    'Moving Expenses' is absent from the GL and the COA tab assigns it 6508000,
    which the ledger uses for Partnered Research, so accepting that fallback would
    post moving costs to Partnered Research and give one code two names. Those are
    refused and reported as unmapped instead.
    """
    gl = load_gl_accounts(gl_lines) if gl_lines else {}
    mapping = {name: (code, leaf, "gl") for name, (code, leaf) in gl.items()}
    occupied = {code: leaf for code, leaf in gl.values()}

    conflicts, collisions = [], []
    for name, (code, leaf) in coa.items():
        if name in mapping:
            if mapping[name][0] != code:
                conflicts.append((leaf, code, mapping[name][0]))
            continue
        if code in occupied:
            collisions.append((leaf, code, occupied[code]))
            continue
        mapping[name] = (code, leaf, "coa")
    return mapping, conflicts, collisions


# ── Extraction ──────────────────────────────────────────────────────────────

def _months_for(header: dict[int, str], block: Block, reference: list[tuple[str, int]] | None):
    """Period labels for each of a block's month columns.

    The current block reads its own header. Every other block takes the reference
    block's periods by position, because its header cannot be trusted.
    """
    if block.trust_header:
        periods = []
        idx = block.first_month
        while True:
            parsed = _serial_to_period(header.get(idx, ""))
            if not parsed:
                break
            periods.append(parsed)
            idx += 1
        return periods
    return list(reference or [])


def extract(path: str, vintage_label: str, prior_label: str, gl_lines):
    """Read every detail tab and block into long-format line rows."""
    zf = zipfile.ZipFile(path)
    strings = _shared_strings(zf)
    sheets = _sheet_map(zf)
    coa = load_coa(zf, sheets, strings)
    accounts, conflicts, collisions = load_account_map(gl_lines, coa)
    if not accounts:
        raise SystemExit(
            "No account mapping is available: pass the NetSuite GL export, "
            "or supply a workbook whose COA tab is readable.")

    labels = {"current": vintage_label, "prior": prior_label}
    rows: list[dict] = []
    notes: list[str] = []
    unmapped: dict[tuple, dict] = {}

    def drop(acct: str, reason: str, tab: str, block: Block, dept: str, total: float):
        bucket = unmapped.setdefault((_norm(acct), reason), {
            "forecast_account": acct or "(blank)", "reason": reason,
            "tabs": set(), "blocks": set(), "departments": set(),
            "lines": 0, "total_all_periods": 0.0})
        bucket["tabs"].add(tab)
        bucket["blocks"].add(block.key)
        if dept:
            bucket["departments"].add(dept)
        bucket["lines"] += 1
        bucket["total_all_periods"] += total

    for tab in DETAIL_SHEETS:
        part = sheets.get(tab)
        if not part:
            notes.append(f"Tab {tab!r} is not in this workbook and was skipped.")
            continue
        grid = _read_grid(zf, part, strings)
        header = grid.get(HEADER_ROW, {})
        reference: list[tuple[str, int]] | None = None

        for block in BLOCKS:
            if header.get(block.col("dept"), "").upper() != "DEPT":
                notes.append(
                    f"{tab}/{block.key}: column {block.col('dept')} of row {HEADER_ROW} "
                    "is not DEPT, so the layout has changed. Skipped rather than "
                    "read at the wrong offsets.")
                continue

            periods = _months_for(header, block, reference)
            if block.trust_header:
                if len(periods) != MONTHS_PER_BLOCK:
                    notes.append(
                        f"{tab}/{block.key}: found {len(periods)} month columns, "
                        f"expected {MONTHS_PER_BLOCK}. Skipped, and every later block "
                        "on this tab with it, because they are read by position.")
                    break
                reference = periods
            if not periods:
                notes.append(f"{tab}/{block.key}: no periods available. Skipped.")
                continue

            source = "own header" if block.trust_header else "position"
            notes.append(f"{tab}/{block.key}: {len(periods)} months "
                         f"({periods[0][0]} to {periods[-1][0]}) read by {source}, "
                         f"columns {block.first_month}-{block.first_month + len(periods) - 1}.")

            for rnum in sorted(r for r in grid if r > HEADER_ROW):
                cells = grid[rnum]
                dept = cells.get(block.col("dept"), "")
                acct = cells.get(block.col("acct"), "")
                amounts = {}
                for offset, (period, year) in enumerate(periods):
                    value = _number(cells.get(block.first_month + offset, ""))
                    # Zero is a real forecast value but adds ~90% volume for no
                    # signal; an account with no row for a period reads as zero.
                    if value:
                        amounts[offset] = (period, year, value)
                if not amounts:
                    continue

                total = sum(abs(v) for _, _, v in amounts.values())
                # A row carrying money but missing a dimension cannot be placed.
                # It is reported rather than skipped: a line that vanishes with no
                # trace is the failure this whole pipeline exists to prevent.
                if not acct:
                    drop(acct, "blank account on a row carrying values",
                         tab, block, dept, total)
                    continue
                if not dept:
                    drop(acct, "blank department on a row carrying values",
                         tab, block, dept, total)
                    continue

                mapped = accounts.get(_norm(acct))
                if not mapped:
                    drop(acct, "no matching ledger or COA account",
                         tab, block, dept, total)
                    continue
                code, leaf, src = mapped

                for period, year, value in amounts.values():
                    rows.append({
                        "fiscal_year": year, "period": period,
                        "account_code": code, "account_leaf": leaf,
                        "department": dept,
                        "project": cells.get(block.col("proj"), ""),
                        "vendor": cells.get(block.col("vendor"), ""),
                        "po_number": cells.get(block.col("po"), ""),
                        "description": cells.get(block.col("desc"), ""),
                        "note_1": cells.get(block.col("note1"), ""),
                        "note_2": cells.get(block.col("note2"), ""),
                        "amount": round(value, 2),
                        "source_tab": tab,
                        "line_ref": f"{tab}!{rnum}",
                        "budget_version": labels[block.key],
                        "vintage_block": block.key,
                        "account_source": src,
                    })

    unmapped_rows = []
    for bucket in sorted(unmapped.values(), key=lambda b: -b["total_all_periods"]):
        unmapped_rows.append({
            "forecast_account": bucket["forecast_account"],
            "reason": bucket["reason"],
            "source_tabs": "; ".join(sorted(bucket["tabs"])),
            "vintage_blocks": "; ".join(sorted(bucket["blocks"])),
            "departments": "; ".join(sorted(bucket["departments"])),
            "forecast_lines": bucket["lines"],
            "total_all_periods": round(bucket["total_all_periods"], 2),
            "gl_account_code": "", "gl_account_leaf": "",
        })
    return rows, unmapped_rows, notes, conflicts, collisions


def aggregate(lines: list[dict]) -> list[dict]:
    """Roll line items up to the account / department / period feed."""
    totals: dict[tuple, dict] = {}
    for line in lines:
        key = (line["fiscal_year"], line["period"], line["account_code"],
               line["department"], line["budget_version"])
        bucket = totals.setdefault(key, {
            "fiscal_year": line["fiscal_year"], "period": line["period"],
            "account_code": line["account_code"], "account_leaf": line["account_leaf"],
            "department": line["department"], "budget_amount": 0.0,
            "budget_version": line["budget_version"],
            # The workbook records no approval for these numbers. Leaving these
            # empty is the honest reading; filling them would assert a control
            # that does not exist.
            "approved_by": "", "approved_date": "",
        })
        bucket["budget_amount"] += line["amount"]

    out = []
    for bucket in totals.values():
        bucket["budget_amount"] = round(bucket["budget_amount"], 2)
        out.append(bucket)
    out.sort(key=lambda r: (_period_key(r["period"]), r["account_code"], r["department"]))
    return out


def read_forecast(path, gl_lines, prior_label="prior"):
    """-> (vintage, {"current": [line, ...], "prior": [line, ...]}).

    The vintage is read from the file name, as Serif names it:
    serif_rolling_forecast_2026-08.xlsx is the 2026-08 cut. Account names are
    mapped to codes through the ledger lines supplied.
    """
    if not os.path.exists(path):
        raise SystemExit(f"Not found: {path}")
    found = re.search(r"(20\d\d)[-_]?(\d\d)", os.path.basename(path))
    vintage = f"{found.group(1)}-{found.group(2)}" if found else "current"
    try:
        lines, _, _, _, _ = extract(path, vintage, prior_label, gl_lines)
    except zipfile.BadZipFile:
        raise SystemExit(f"{os.path.basename(path)} is not an .xlsx workbook.")
    if not lines:
        raise SystemExit(f"{os.path.basename(path)}: no forecast lines found. "
                         "The workbook layout has changed.")
    blocks = {"current": [], "prior": []}
    for line in lines:
        blocks[line["vintage_block"]].append(line)
    return vintage, blocks


# ── Links ───────────────────────────────────────────────────────────────────
#
# The NetSuite link IDs file is the result of one SuiteQL query, saved as the
# connector returns it (netsuite_link_ids_<period>.csv; the query is in
# HOW-TO-RUN). It carries each posting line's internal ID, the bill's Coupa
# invoice address and the line's Coupa PO. It is read for links only: no figure
# or finding comes from it, and a file whose totals do not tie to the GL month is
# set aside.

LINK_ID_COLS = ("internal_id", "document_number", "period", "debit", "credit",
                "coupa_transaction_url", "coupa_po_num")


# ── NetSuite balance sheet report ───────────────────────────────────────────
#
# The Balance Sheet report with one column per month, exported as .xls. It is
# SpreadsheetML: title rows, then a "Financial Row" header naming the months, a
# row of "Amount" labels, then the report's rows. A heading row has no figures; a
# subtotal row starts "Total"; an account row is "<code> - <name>". Blank cells are
# zero balances. The report is read as NetSuite wrote it, for the months asked.

_SS = "{urn:schemas-microsoft-com:office:spreadsheet}"


def read_balance_sheet(path, months) -> list[dict]:
    """-> [{name, code, depth, kind, values: {month: amount}}] in report order.

    `kind` is head, account or total. `depth` is the row's level under its
    headings, for laying the report out as NetSuite does."""
    if not os.path.exists(path):
        raise SystemExit(f"Not found: {path}")
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        raise SystemExit(f"{os.path.basename(path)} is not a NetSuite .xls export (SpreadsheetML). "
                         "Run the report in NetSuite with one column per month, by accounting period, "
                         "and export it again as .xls.")
    sheet = root.find(_SS + "Worksheet")
    table = sheet.find(_SS + "Table") if sheet is not None else None
    if table is None:
        raise SystemExit(f"{os.path.basename(path)} holds no worksheet table.")
    grid = []
    for row in table.findall(_SS + "Row"):
        cells = []
        for cell in row.findall(_SS + "Cell"):
            data = cell.find(_SS + "Data")
            cells.append(data.text if data is not None and data.text is not None else "")
        grid.append(cells)
    head = next((i for i, c in enumerate(grid) if c and (c[0] or "").strip() == "Financial Row"), None)
    if head is None:
        raise SystemExit(f"{os.path.basename(path)}: no 'Financial Row' header. Export the "
                         "NetSuite report with one column per month.")
    col = {(m or "").strip(): i for i, m in enumerate(grid[head]) if i}
    missing = [m for m in months if m and m not in col]
    if missing:
        raise SystemExit(f"{os.path.basename(path)} has no column for " + ", ".join(missing)
                         + ". Export the report through the period.")
    out, depth = [], 0
    for cells in grid[head + 2:]:
        name = (cells[0] if cells else "").replace("\xa0", " ").strip()
        if not name:
            continue
        values = {}
        for m in months:
            if not m:
                continue
            i = col[m]
            text = cells[i] if i < len(cells) else ""
            values[m] = round(float(text), 2) if text not in ("", None) else None
        is_total = name.startswith("Total")
        if is_total:
            depth = max(depth - 1, 0)
        kind = "total" if is_total else ("head" if all(v is None for v in values.values()) else "account")
        match = re.match(r"^(?:Total - )?(\d{7}) - (.+)$", name)
        out.append({"name": name, "code": match.group(1) if match else "", "depth": depth, "kind": kind,
                    "values": {m: (v if v is not None else 0.0) for m, v in values.items()}})
        if kind == "head":
            depth += 1
    return out


# ── Tie to the Income Statement ─────────────────────────────────────────────
#
# Before a console is built on the ledger, the ledger has to tie back to NetSuite's own
# Income Statement by month report, account by account. The report shows income as a
# positive figure and the ledger as a credit, so accounts under the Income and Other
# Income headings are compared with their sign turned.

INCOME_HEADS = ("income", "other income")


def income_statement_tie(by_period, path, months) -> dict:
    """-> {report, months, accounts, passed, failed: [{month, code, name, ledger, report,
    difference}], totals: {month: {ledger, report}}}. An account in either the ledger or
    the report that differs by a cent or more fails."""
    sign, names, report = 1, {}, defaultdict(float)
    for row in read_balance_sheet(path, months):
        if row["kind"] == "head" and not row["code"]:
            sign = -1 if row["name"].lower() in INCOME_HEADS else 1
        elif row["code"] and row["kind"] == "account":
            names[row["code"]] = row["name"].split(" - ", 1)[-1]
            for m in months:
                report[(row["code"], m)] += sign * (row["values"].get(m) or 0)
    failed, totals, codes = [], {}, set(names)
    for m in months:
        ledger = defaultdict(float)
        for line in by_period.get(m, []):
            if line["account_code"][:1] in "45678":
                ledger[line["account_code"]] += line["amount"]
                names.setdefault(line["account_code"], line.get("account_leaf") or "")
        codes |= set(ledger)
        totals[m] = {"ledger": round(sum(ledger.values()), 2),
                     "report": round(sum(v for (c, mm), v in report.items() if mm == m), 2)}
        for code in sorted(set(ledger) | {c for c, mm in report if mm == m}):
            a, b = round(ledger.get(code, 0), 2), round(report.get((code, m), 0), 2)
            if abs(round(a - b, 2)) >= 0.01:
                failed.append({"month": m, "code": code, "name": names.get(code, ""),
                               "ledger": a, "report": b, "difference": round(a - b, 2)})
    return {"report": os.path.basename(path), "months": list(months), "accounts": len(codes),
            "passed": not failed, "failed": failed, "totals": totals}


def tie_lines(tie) -> list[str]:
    """The tie as plain lines, for a script's output and the chat."""
    months = " and ".join(tie["months"])
    if tie["passed"]:
        return [f"Ties to the Income Statement ({tie['report']}): {months}, "
                f"{tie['accounts']} accounts, every account ties."]
    out = [f"Does NOT tie to the Income Statement ({tie['report']}): "
           f"{len(tie['failed'])} account-month(s) differ in {months}."]
    out += [f"  {f['month']}  {f['code']} {f['name']}: ledger {f['ledger']:,.2f}, "
            f"Income Statement {f['report']:,.2f}, difference {f['difference']:,.2f}"
            for f in tie["failed"]]
    return out


def read_link_ids(paths) -> list[dict]:
    rows = []
    for path in paths or []:
        if not os.path.exists(path):
            raise SystemExit(f"Not found: {path}")
        with open(path, encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = [c for c in LINK_ID_COLS if c not in (reader.fieldnames or [])]
            if missing:
                raise SystemExit(f"{os.path.basename(path)} is not the NetSuite link IDs query "
                                 f"result: it has no {', '.join(missing)} column. Run the query "
                                 "in HOW-TO-RUN again.")
            for row in reader:
                po = re.match(r"(FL\d{9})", (row.get("coupa_po_num") or "").strip())
                url = (row.get("coupa_transaction_url") or "").strip()
                rows.append({
                    "document_number": (row.get("document_number") or "").strip(),
                    "internal_id": (row.get("internal_id") or "").strip(),
                    "period": (row.get("period") or "").strip(),
                    "debit": _num(row.get("debit")), "credit": _num(row.get("credit")),
                    "coupa_url": url if url.startswith(COUPA_INVOICE) else "",
                    "coupa_po": po.group(1) if po else "",
                })
    return rows


def link_ids_tie(id_rows, gl_by_period) -> list[str]:
    """Periods where the link IDs file and the GL export disagree on total debits."""
    totals = defaultdict(float)
    for row in id_rows:
        totals[row["period"]] += row["debit"]
    return [p for p, t in sorted(totals.items())
            if round(t, 2) != round(sum(l["debit"] for l in gl_by_period.get(p, [])), 2)]


def po_id(po_number, coupa_ids):
    """Coupa's record ID for a PO number. The export's PO ID is used when the PO
    is in it; otherwise the ID is the number after FL087, the rule every one of the
    3,664 POs in the 2026 export follows."""
    if po_number in coupa_ids:
        return coupa_ids[po_number]
    match = re.fullmatch(r"FL087(\d{6})", po_number)
    return str(int(match.group(1))) if match else ""


def links(gl_lines, coupa_rows, po_numbers=(), id_rows=()) -> dict:
    """What the consoles need to open a document in NetSuite or Coupa.

    Only IDs the exports carry are used. Every document number in `gl_lines` is
    listed, so the consoles link a number only when the ledger holds it. A number
    that belongs to two NetSuite records, two Coupa invoices or two POs gets no link
    of that kind, so a link never opens the wrong one.
    """
    ns, coupa, po = defaultdict(set), defaultdict(set), defaultdict(set)
    seen = {(l.get("document_number") or "").strip() for l in gl_lines} - {""}
    for line in list(gl_lines) + list(id_rows):
        doc = (line.get("document_number") or "").strip()
        if not doc:
            continue
        if line.get("internal_id"):
            ns[doc].add(line["internal_id"])
        if line.get("coupa_url"):
            coupa[doc].add(line["coupa_url"])
        if line.get("coupa_po"):
            po[doc].add(line["coupa_po"])
    docs = {}
    for doc in sorted(seen):
        entry = {}
        if len(ns.get(doc, ())) == 1:
            entry["ns"] = next(iter(ns[doc]))
        if len(coupa.get(doc, ())) == 1:
            entry["coupa"] = next(iter(coupa[doc]))
        if len(po.get(doc, ())) == 1:
            entry["po"] = next(iter(po[doc]))
        docs[doc] = entry
    coupa_ids = {r.get("po_number", ""): r.get("po_id", "") for r in coupa_rows
                 if r.get("po_number") and r.get("po_id")}
    wanted = set(po_numbers) | {e["po"] for e in docs.values() if "po" in e}
    po_ids = {p: po_id(p, coupa_ids) for p in sorted(wanted) if po_id(p, coupa_ids)}
    return {"netsuite_account": NETSUITE_ACCOUNT, "coupa_host": COUPA_HOST,
            "docs": docs, "po_ids": po_ids}


def main(argv=None):
    """`python3 serif_sources.py tie`: the Income Statement tie, run before either console."""
    import argparse
    ap = argparse.ArgumentParser(description="Tie the NetSuite ledger to the Income Statement by month "
                                 "report, account by account. Exits 2 when an account does not tie.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tie", help="tie the close month (and with --prior, the month before)")
    t.add_argument("--period", required=True, help='the close month, eg "Sep 2026"')
    t.add_argument("--gl", nargs="+", required=True, help="the NetSuite Custom General Ledger export(s)")
    t.add_argument("--income-statement", required=True, help="the NetSuite Income Statement by month report")
    t.add_argument("--prior", action="store_true", help="tie the month before as well (the P&L Flux)")
    args = ap.parse_args(argv)
    period = shift(args.period.strip(), 0)
    months = [period, shift(period, -1)] if args.prior else [period]
    by_period, _ = read_gl(args.gl)
    absent = [m for m in months if not by_period.get(m)]
    if absent:
        raise SystemExit(f"The NetSuite exports hold no lines for {', '.join(absent)}.")
    tie = income_statement_tie(by_period, args.income_statement, months)
    print("\n".join(tie_lines(tie)))
    return 0 if tie["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
