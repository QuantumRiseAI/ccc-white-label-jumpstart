#!/usr/bin/env python3
"""Extract the rolling forecast's line-item build tabs into long-format CSVs.

    python3 forecast_to_csv.py <rolling_forecast.xlsx> <out_dir> [options]

The workbook carries four tabs built on an identical grid: `EXT$_R&D`, `EXT$_G&A`,
`LAB` and `OH`. Each holds one row per commitment with the dimensions a variance
test needs (department, account, project, vendor, PO number, description) and 36
month columns.

Each of those tabs carries the grid THREE TIMES side by side:

    columns   0-44   the current vintage      (labels 0-8,  months 9-44)
    columns  51-95   the PRIOR vintage        (labels 51-59, months 60-95)
    columns  98-133  the delta, current less prior

Cell AZ18 is labelled `PRIOR` on all four tabs. The prior block reconciles to the
workbook's own `Jun FCST` column on all 235 populated rows and to its per-tab
totals, so it is the June cut.

This matters because the two vintages support completely different tests, and
only one of them is a budget variance. See ON READING THE CURRENT VINTAGE below.

Files produced:

  budget_fy2026_by_account_dept_month.csv
      The aggregated feed both engines look for, from the PRIOR vintage by
      default. One row per account / department / period.
  forecast_lines_<vintage>.csv
      Un-aggregated lines for each vintage, keeping vendor, PO number and
      description, which is what makes a variance explainable.
  unmapped_forecast_accounts.csv
      Planning categories with no ledger account, for the client to complete.

Stdlib only, so it runs in the same places the engines do.

ON THE WORD "BUDGET"
--------------------
This is a rolling forecast re-cut monthly, not an approved annual budget. The
`budget_version` column records which vintage a number came from, and
`approved_by` and `approved_date` are left empty because the workbook records no
approval.

ON READING THE CURRENT VINTAGE
------------------------------
The current vintage's closed months are the posted actuals, not a forecast.
Verified two ways for Aug 2026: 30 of its 37 comparable accounts tie to the GL to
the cent, and for the two accounts carrying a manual reclass, backing that reclass
out lands both on the GL actual exactly, in both July and August.

So an actual-versus-current-vintage comparison is a reconciliation between the
FP&A model and the ledger. It is a useful tie-out and it is how the $4.47M
unbooked reclass was found, but it is not a measure of budget performance, and
reporting it as one would be reporting a definition as an accuracy result.

The prior vintage is the genuine pre-month baseline: only 1 of its 30 comparable
accounts ties to the Aug 2026 ledger, and 7 of 38 of its account totals are exact
thousands, which is what planning numbers look like. That is why it is the default
source for the budget feed.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import zipfile
from xml.etree import ElementTree as ET

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
# against the GL slices, which carry no revenue rows. Carried through but called
# out rather than silently mixed into an expense budget.
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


def load_gl_accounts(paths: list[str]) -> dict[str, tuple[str, str]]:
    """Account name -> (code, name) as the ledger currently uses them.

    A name carrying more than one code in the ledger is left out, because a
    forecast line naming it cannot be assigned to one code without guessing.
    """
    seen: dict[str, set[tuple[str, str]]] = {}
    for path in paths:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                code = (row.get("account_code") or "").strip()
                leaf = (row.get("account_leaf") or "").strip()
                if code and leaf:
                    seen.setdefault(_norm(leaf), set()).add((code, leaf))
    return {name: sorted(pairs)[0] for name, pairs in seen.items() if len(pairs) == 1}


def load_account_map(gl_paths: list[str], coa: dict[str, tuple[str, str]]):
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
    gl = load_gl_accounts(gl_paths) if gl_paths else {}
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


def extract(path: str, vintage_label: str, prior_label: str, gl_paths: list[str]):
    """Read every detail tab and block into long-format line rows."""
    zf = zipfile.ZipFile(path)
    strings = _shared_strings(zf)
    sheets = _sheet_map(zf)
    coa = load_coa(zf, sheets, strings)
    accounts, conflicts, collisions = load_account_map(gl_paths, coa)
    if not accounts:
        raise SystemExit(
            "No account mapping is available. Pass --gl with at least one GL slice, "
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


def _write(path: str, fields: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("workbook")
    parser.add_argument("out_dir")
    parser.add_argument("--vintage", default="",
                        help="label for the current cut, eg 2026-08 "
                             "(default: inferred from the filename)")
    parser.add_argument("--prior-vintage", default="prior",
                        help="label for the PRIOR block, eg 2026-06 (default: prior)")
    parser.add_argument("--budget-from", choices=("prior", "current"), default="prior",
                        help="which vintage fills the budget feed. Default prior, "
                             "because the current vintage's closed months are the "
                             "posted actuals rather than a forecast.")
    parser.add_argument("--gl", action="append", default=[], metavar="CSV",
                        help="a normalized GL slice, used as the authoritative "
                             "account name to code mapping. Repeatable. Strongly "
                             "recommended: the workbook's COA tab is behind the "
                             "ledger on 21 account codes.")
    args = parser.parse_args(argv)

    vintage = args.vintage
    if not vintage:
        found = re.search(r"(20\d\d)[-_]?(\d\d)", os.path.basename(args.workbook))
        vintage = f"{found.group(1)}-{found.group(2)}" if found else "unknown"

    lines, unmapped, notes, conflicts, collisions = extract(
        args.workbook, vintage, args.prior_vintage, args.gl)
    if not lines:
        raise SystemExit("No forecast lines were extracted. The workbook layout has changed.")

    os.makedirs(args.out_dir, exist_ok=True)
    by_block = {b.key: [r for r in lines if r["vintage_block"] == b.key] for b in BLOCKS}
    label = {"current": vintage, "prior": args.prior_vintage}

    budget = aggregate(by_block[args.budget_from])
    budget_path = os.path.join(args.out_dir, "budget_fy2026_by_account_dept_month.csv")
    _write(budget_path, BUDGET_FIELDS, budget)
    unmapped_path = os.path.join(args.out_dir, "unmapped_forecast_accounts.csv")
    _write(unmapped_path, UNMAPPED_FIELDS, unmapped)

    print(f"Workbook {os.path.basename(args.workbook)}")
    for block in BLOCKS:
        block_lines = by_block[block.key]
        if not block_lines:
            continue
        path = os.path.join(args.out_dir, f"forecast_lines_{label[block.key]}.csv")
        _write(path, LINE_FIELDS, block_lines)
        periods = sorted({r["period"] for r in block_lines}, key=_period_key)
        total = sum(r["amount"] for r in block_lines)
        print(f"  {block.key:8s} vintage {label[block.key]:10s} "
              f"{len(block_lines):>6,} lines  ${total:>16,.2f}  "
              f"{periods[0]} to {periods[-1]}")
        print(f"           {path}")

    print(f"\n  budget feed from the {args.budget_from} vintage: "
          f"{len(budget):,} rows -> {budget_path}")

    revenue = sorted({(r["account_code"], r["account_leaf"]) for r in lines
                      if not r["account_code"].startswith(EXPENSE_PREFIXES)})
    if revenue:
        amount = sum(r["amount"] for r in lines
                     if not r["account_code"].startswith(EXPENSE_PREFIXES))
        print(f"\n  {len(revenue)} non-expense account(s) in the build tabs, "
              f"${amount:,.2f} total. These are expense planning tabs, and the GL "
              "slices carry no revenue rows, so the sign convention is unverified.")
        for code, leaf in revenue:
            print(f"    {code}  {leaf}")

    for note in notes:
        print(f"  {note}")

    if conflicts:
        print(f"\n  {len(conflicts)} account codes where the COA tab disagrees with "
              "the ledger. The ledger was used.")
        for leaf, coa_code, gl_code in sorted(conflicts)[:6]:
            print(f"    {leaf[:44]:46s} COA {coa_code} -> GL {gl_code}")
        if len(conflicts) > 6:
            print(f"    and {len(conflicts) - 6} more")

    if collisions:
        print(f"\n  {len(collisions)} COA fallbacks refused because the code is "
              "already a different ledger account.")
        for leaf, code, gl_leaf in sorted(collisions):
            print(f"    {leaf[:36]:38s} COA {code}, which the GL uses for {gl_leaf}")

    if unmapped:
        total = sum(r["total_all_periods"] for r in unmapped)
        print(f"\n  {len(unmapped)} unplaceable forecast categories, ${total:,.2f} "
              f"across all periods. Listed in {unmapped_path}.")
        for row in unmapped[:8]:
            print(f"    {row['forecast_account'][:34]:36s} "
                  f"{row['total_all_periods']:>15,.2f}  {row['reason']}")
        if len(unmapped) > 8:
            print(f"    and {len(unmapped) - 8} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
