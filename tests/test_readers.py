"""The export readers find columns by name, so a saved search or report with columns
added, moved or renamed reads the same. Synthetic files only: no Serif data.

    python3 tests/test_readers.py
"""
import os
import sys
import tempfile
import zipfile
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import serif_sources as S  # noqa: E402

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

    print("Income Statement, the connector's query result")
    q = os.path.join(d, "netsuite_income_statement_by_period_aug.csv")
    open(q, "w").write("period,account_number,account_name,account_type,debit,credit,amount\n"
                       "Aug 2026,6410000,6410000 - Lab Supplies/Consumables,Expense,100.5,0,100.5\n")
    ok(S.is_income_statement_query(q), "the query result is recognized by its columns")
    t = S.income_statement_tie(lines, q, ["Aug 2026"])
    ok(t["passed"] and t["accounts"] == 1, "the ledger ties to it by account, in the ledger's sign")
    ok(S.income_statement_totals(q, "Aug 2026")["Total - 6000000 - Operating Expenses"]["Aug 2026"] == 100.5,
       "its totals carry the report's names")
    try:
        S.income_statement_tie(lines, q, ["Sep 2026"])
        ok(False, "a month with no rows stops the tie")
    except SystemExit as e:
        ok("Sep 2026" in str(e), "a month with no rows stops the tie, naming it")

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

    print("GL, the NetSuite connector's result for netsuite_gl_detail.sql")
    conn = os.path.join(d, "netsuite_gl_detail_sep2026.csv")
    head = ("account_number,account_name,type,date,document_number,name,debit,credit,period,department,"
            "program,project,subsidiary,description,memo,internal_id,line_id,coupa_transaction_url,coupa_po_num\n")
    sub = '"FL87 Serif Biomedicines, Inc."'
    url = "https://" + S.COUPA_HOST + "/invoices/9"
    open(conn, "w").write(head
        + f"2000100,Accounts Payable : Accounts Payable 3rd party,Bill,2026-09-03,B-9,Abcam Inc,,150,Sep 2026,Non-Specific,00 Non-Specific,00 Non-Specific,{sub},,,77,0,{url},\n"
        + f"6410000,Operating Expenses : Lab Expenses : Lab Supplies/Consumables,Bill,2026-09-03,B-9,,75,,Sep 2026,Platform,00 Non-Specific,00 Non-Specific,{sub},Antibody,,77,1,{url},FL087030260-1\n"
        + f"6410000,Operating Expenses : Lab Expenses : Lab Supplies/Consumables,Bill,2026-09-03,B-9,,75,,Sep 2026,Platform,00 Non-Specific,00 Non-Specific,{sub},Antibody,,77,2,{url},FL087030260-1\n"
        + f"6410000,Operating Expenses : Lab Expenses : Lab Supplies/Consumables,Bill,2026-09-03,B-9,,,,Sep 2026,Platform,00 Non-Specific,00 Non-Specific,{sub},Freight,,77,3,{url},\n")
    c = S.read_gl([conn])[0]["Sep 2026"]
    exp = [l for l in c if l["account_code"] == "6410000"]
    ok(len(c) == 2 and len(exp) == 1 and exp[0]["amount"] == 150.0,
       "identical lines of one transaction add up into one, as the saved search shows them; a zero line is left out")
    ok(exp[0]["account_leaf"] == "Lab Supplies/Consumables", "the account is its number and the last part of its name")
    ok(exp[0]["vendor_or_name"] == "Abcam Inc", "an expense line takes the vendor from its bill's payable line")
    ok(exp[0]["internal_id"] == "77" and exp[0]["coupa_url"] == url and exp[0]["coupa_po"] == "FL087030260",
       "the internal ID and Coupa fields come with each line, for links")

    print("Is the month closed?")
    def je(m, day, code, amt):
        return {"txn_type": "Journal", "date": f"2026-{m:02d}-{day:02d}", "account_code": code,
                "account_leaf": "Acct " + code, "amount": amt}
    codes = ["6601000", "6609000", "7110000", "7160000", "6102000"]
    ends = {6: 30, 7: 31, 8: 31, 9: 30}
    led = {f"{S.MONTH_NAMES[m - 1]} 2026": [je(m, ends[m], c, 5000.0) for c in codes] for m in (6, 7, 8)}
    led["Sep 2026"] = [je(9, 15, "6101000", 9000.0)]
    gaps = S.month_end_gaps(led, "Sep 2026")
    ok([g["code"] for g in gaps] == sorted(codes), "five recurring month-end entries missing are listed")
    led["Sep 2026"] += [je(9, 30, c, 5000.0) for c in codes[:2]]
    ok(S.month_end_gaps(led, "Sep 2026") == [], "fewer than five missing is ordinary variation, not listed")

    print("Coupa, a report that stops at a row limit")
    capped = os.path.join(d, "coupa_capped.csv")
    open(capped, "w").write("PO Number,Order Date,Supplier,Amt\n" + "".join(f"FL0870{i:05d},9/3/2026,,1\n" for i in range(5000)))
    ok(S.coupa_row_limit(capped) == 5000, "a report of exactly 5,000 lines is flagged as capped")
    short = os.path.join(d, "coupa_short.csv")
    open(short, "w").write("PO Number,Order Date,Supplier,Amt\n" + "".join(f"FL0870{i:05d},9/3/2026,,1\n" for i in range(4999)))
    ok(S.coupa_row_limit(short) is None, "a report of another size is not")

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
