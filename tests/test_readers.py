"""The export readers find columns by name, so a saved search or report with columns
added, moved or renamed reads the same, and the GL's Project and Program reach the
console's lines and both sides of a proposed Journal Entry. Synthetic files only: no
Serif data.

    python3 tests/test_readers.py
"""
import os
import sys
import tempfile
import zipfile
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import serif_sources as S  # noqa: E402
import serif_views as V  # noqa: E402

FAILED = []


def ok(cond, label):
    print(("  PASS " if cond else "  FAIL ") + label)
    if not cond:
        FAILED.append(label)


TITLE = [["Flagship Labs"], ["Custom General Ledger"], ["From Jan 2026 to Sep 2026"], [""]]
AUG = ["Account", "Type", "Date", "Document Number", "Name", "Debit", "Credit", "Balance",
       "Account: Name", "Accounting Period: Name", "Department: Name", "Program: Name",
       "ProjectID: Name", "ProjectID: Name", "Subsidiary: Name", "Description", "Memo"]
SEP = ["Account", "Type", "Date", "Document Number", "Name", "Debit", "Credit", "Balance",
       "Account: Name", "Accounting Period: Name", "Department: Name", "Entity",
       "Subsidiary: Name", "Program: Name", "ProjectID: Name", "ProjectID: Name",
       "Description", "Memo", "PO Number", "PO Line Id"]
ACCT = "6000000 - Operating Expenses:6410000 - Lab Supplies/Consumables"
AP = "2000000 - Accounts Payable:2000100 - Accounts Payable"


def spreadsheetml(rows, skip_cell=None):
    """An .xls as NetSuite writes it. skip_cell=(row, col) drops that cell and gives the
    next one an ss:Index, as NetSuite does for empty cells."""
    out = ['<?xml version="1.0"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" '
           'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><Worksheet ss:Name="GL"><Table>']
    for r, row in enumerate(rows):
        out.append("<Row>")
        jump = False
        for c, value in enumerate(row):
            if skip_cell == (r, c):
                jump = True
                continue
            index = f' ss:Index="{c + 1}"' if jump else ""
            jump = False
            out.append(f'<Cell{index}><Data ss:Type="String">{escape(str(value))}</Data></Cell>')
        out.append("</Row>")
    out.append("</Table></Worksheet></Workbook>")
    return "".join(out)


def xlsx(rows):
    """A minimal .xlsx: inline strings, numbers as numbers, dates as serials."""
    def col(i):
        s = ""
        i += 1
        while i:
            i, rem = divmod(i - 1, 26)
            s = chr(65 + rem) + s
        return s
    sheet = ['<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/'
             'spreadsheetml/2006/main"><sheetData>']
    for r, row in enumerate(rows, start=1):
        sheet.append(f'<row r="{r}">')
        for c, value in enumerate(row):
            ref = f"{col(c)}{r}"
            if isinstance(value, (int, float)):
                sheet.append(f'<c r="{ref}"><v>{value}</v></c>')
            elif value != "":
                sheet.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
        sheet.append("</row>")
    sheet.append("</sheetData></worksheet>")
    book = ('<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/'
            '2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Custom General Ledger" sheetId="1" r:id="rId1"/></sheets></workbook>')
    rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/'
            '2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>')
    return {"xl/workbook.xml": book, "xl/_rels/workbook.xml.rels": rels,
            "xl/worksheets/sheet1.xml": "".join(sheet)}


with tempfile.TemporaryDirectory() as d:
    print("GL, the August saved search (.xls)")
    rows = TITLE + [AUG,
        [ACCT, "Bill", "2026-08-12T00:00:00.000", "B-1", "Fisher Scientific", "100.50", "", "",
         "Lab Supplies/Consumables", "Aug 2026", "Production", "00 Non-Specific", "", "Internal CMC",
         "FL87 Serif Biomedicines, Inc.", "Pipettes", "Aug order"],
        [AP, "Bill", "2026-08-12T00:00:00.000", "B-1", "Fisher Scientific", "", "100.50", "",
         "Accounts Payable", "Aug 2026", "Non-Specific", "00 Non-Specific", "00 Non-Specific",
         "00 Non-Specific", "FL87 Serif Biomedicines, Inc.", "", ""]]
    aug = os.path.join(d, "netsuite_gl_aug.xls")
    open(aug, "w").write(spreadsheetml(rows, skip_cell=(len(TITLE) + 1, 12)))
    lines, files = S.read_gl([aug])
    a = lines["Aug 2026"]
    ok(len(a) == 2 and files[0]["rows"] == 2, "both lines read, title rows skipped")
    ok(a[0]["account_code"] == "6410000" and a[0]["amount"] == 100.5, "account and amount")
    ok(a[0]["date"] == "2026-08-12" and a[0]["department"] == "Production", "date and department")
    ok(a[0]["project"] == "Internal CMC", "the project from whichever ProjectID column names one")
    ok(a[0]["memo"] == "Aug order" and a[0]["subsidiary"].startswith("FL87"),
       "a skipped cell (ss:Index) does not shift the columns after it")

    print("GL, a different saved search saved as .xlsx")
    serial = (S.dt.date(2026, 9, 3) - S.EXCEL_EPOCH).days
    rows = TITLE + [SEP,
        [ACCT, "Bill", serial, "B-2", "VWR International LLC", 250, "", "", "Lab Supplies/Consumables",
         "Sep 2026", "Platform", "VWR International LLC", "FL87 Serif Biomedicines, Inc.",
         "00 Non-Specific", "Internal CMC", "00 Non-Specific", "Tips", "Sep order",
         "FL087030260-1", "1"],
        [AP, "Bill", serial, "B-2", "VWR International LLC", "", 250, "", "Accounts Payable",
         "Sep 2026", "Non-Specific", "VWR International LLC", "FL87 Serif Biomedicines, Inc.",
         "00 Non-Specific", "00 Non-Specific", "00 Non-Specific", "", "", "", ""]]
    sep = os.path.join(d, "netsuite_gl_sep.xlsx")
    with zipfile.ZipFile(sep, "w") as z:
        for name, body in xlsx(rows).items():
            z.writestr(name, body)
    s = S.read_gl([sep])[0]["Sep 2026"]
    ok(len(s) == 2 and s[0]["date"] == "2026-09-03", "an .xlsx reads, its date serials as dates")
    ok(s[0]["department"] == "Platform" and s[0]["subsidiary"].startswith("FL87"),
       "an added Entity column does not shift Department or Subsidiary")
    ok(s[0]["program"] == "00 Non-Specific" and s[0]["project"] == "Internal CMC",
       "Program and Project found by name")
    ok(s[0]["description"] == "Tips" and s[0]["memo"] == "Sep order", "Description and Memo found by name")
    ok(s[0]["coupa_po"] == "FL087030260", "a PO Number column gives the line's Coupa PO")
    ok(round(sum(x["amount"] for x in s), 2) == 0, "debits equal credits")

    print("Project and Program, from the reader to a proposed Journal Entry")
    cur = V.load_gl(a + s)
    item = V.lines_for(cur, vendor="Fisher Scientific")["items"][0]
    ok(item["project"] == "Internal CMC" and item["program"] == "00 Non-Specific",
       "a line in the console carries its Project and Program")
    t1 = dict(a[0], vendor_or_name="Fisher Scientific")
    t2 = dict(s[0], vendor_or_name="Fisher Scientific", project="00 Non-Specific")
    dept = {"finding_id": "x1", "rule_id": "T1.DEPT_INCONSISTENCY", "transactions": [t1, t2],
            "evidence": {"expected": "department 'General R&D'"}}
    e1 = V.entries([dept], "Aug 2026")[0]["lines"]
    ok(len(e1) == 4 and all(sum(l["debit"] - l["credit"] for l in e1 if l["project"] == p) == 0
                            for p in ("Internal CMC", "00 Non-Specific")),
       "both sides of a reclass carry each line's Project, a line per Project")
    cap = {"finding_id": "x2", "rule_id": "F10.CAPITALIZE", "title": "Fisher Scientific: may be capital",
           "transactions": [{"document_number": "B-1", "account_code": "6410000", "amount": 100.5}],
           "correction": {"entry": "Dr 1505000 Capital in Process / Cr 6410000 Lab Supplies/Consumables"
                                   " / Production for $100.50"}, "evidence": {}}
    e2 = V.entries([cap], "Aug 2026", lookup=V.gl_dims(cur))[0]["lines"]
    bs, pl = [l for l in e2 if l["account"] == "1505000"], [l for l in e2 if l["account"] == "6410000"]
    ok(bs and bs[0]["department"] == "Non-Specific" and pl and pl[0]["department"] == "Production",
       "a balance sheet line takes Non-Specific; the income statement line keeps its department")
    ok(all(l["project"] == "Internal CMC" and l["program"] == "00 Non-Specific" for l in e2),
       "a finding's lines with no Project of their own take the ledger line's, on both sides")

    print("GL, a file that is not the ledger")
    bad = os.path.join(d, "netsuite_gl_bad.xls")
    open(bad, "w").write(spreadsheetml(TITLE + [["Account", "Type", "Debit", "Credit"],
                                                [ACCT, "Bill", "1", ""]]))
    try:
        S.read_gl([bad])
        ok(False, "a missing column stops the run")
    except SystemExit as e:
        ok("date" in str(e) and "accounting period" in str(e), "a missing column stops the run, naming it")

    print("Coupa, the Data Pull (PO Lines) report")
    pull = os.path.join(d, "coupa_pull.csv")
    open(pull, "w", encoding="utf-8").write(
        ",PO Number,Supplier,Line,Order Date,Description,Unit Price,U/M,Qty,Amt,Requestor,"
        "Department,GL Account,Order Line Amount,Invoiced Amount\n"
        '1,FL087030260,,1,9/3/2026,Pipette tips,10,Each,5,50,Renée Solly,R&D : Platform,'
        "Lab Supplies/Consumables,50,50\n"
        ",,,,,,,,,,,,,50,50\n")
    rows, absent = S.coupa_rows(pull)
    ok(len(rows) == 1, "the closing totals row is not read as a PO line")
    line = S.read_coupa(pull)[0]
    ok(line["po_number"] == "FL087030260" and line["period"] == "Sep 2026", "PO number and order date")
    ok(line["line_total"] == 50 and line["item_name"] == "Pipette tips", "amount and item")
    ok(line["requested_by"] == "Renée Solly", "requester, accents intact")
    ok("Supplier" in absent and "Account" in absent and "Received" in absent,
       "an empty Supplier column and the missing Account and Received are listed as absent")

    print("Coupa, the export with all available columns")
    full = os.path.join(d, "coupa_full.csv")
    open(full, "w", encoding="utf-8").write(
        "PO Number (Header),PO ID,Line,Supplier,Order Date (Header),Account,Item,Line Total,Qty,"
        "Received,Approved Invoiced,Line Status,Order Status (Header),Commodity,Requested By (Header)\n"
        'FL087030260,30260,1,"Abcam Inc (Abcam Inc|149|Labs)",9/3/2026,97-6410000-9--4,Antibody,'
        "\"1,250.00\",1,1,0,received,Issued,Antibodies,Peter Grzesik\n")
    rows, absent = S.coupa_rows(full)
    line = S.read_coupa(full)[0]
    ok(absent == [], "nothing absent from the full export")
    ok(line["supplier"] == "Abcam Inc" and line["gl_account_code"] == "6410000"
       and line["line_total"] == 1250.0, "supplier, account and amount as before")

    print("Coupa, a file that is not a PO report")
    other = os.path.join(d, "other.csv")
    open(other, "w").write("Vendor,Amount\nX,1\n")
    try:
        S.coupa_rows(other)
        ok(False, "a non-PO file stops the run")
    except SystemExit as e:
        ok("PO Number" in str(e), "a non-PO file stops the run, naming the column")

print("\n%d failed" % len(FAILED) if FAILED else "\nall passed")
sys.exit(1 if FAILED else 0)
