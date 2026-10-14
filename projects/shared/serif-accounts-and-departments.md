# Serif Biomedicines: Chart of Accounts and Departments

Source: `data/real/netsuite_gl_detail_jan2025-aug2026.xls`, the NetSuite Custom General Ledger for
Jan 2025 through Aug 2026, 44,013 transaction lines.
Generated 2026-09-16 by Quantum Rise directly from the GL export, not hand-keyed.

This is the account and department reference for both Jumpstart agents.
It reflects one export covering Jan 2025 to Aug 2026; regenerate it if a later export adds accounts
or departments.

## Entity and Subsidiary

Only one subsidiary appears across all 44,013 lines:

| Subsidiary | Lines |
|---|---|
| `FL87 Serif Biomedicines, Inc.` | 44,013 (100%) |

Report header hierarchy is `Flagship : Labs : FL87 Serif Biomedicines, Inc.`, so Serif is a
Flagship Labs portfolio entity.
There is no second legal entity in this export and no EU subsidiary.
Cross-entity coding tests therefore cannot run against this data.
Intercompany activity shows up as related-party vendors instead.

## Departments

Departments are names, not numeric codes.

| Department | Lines | Net (Dr–Cr) |
|---|---:|---:|
| `Non-Specific` | 18,391 | -82,092,318 |
| `General R&D` | 7,736 | 29,684,179 |
| `Platform` | 6,246 | 7,604,435 |
| `Production` | 4,505 | 17,178,265 |
| `General G&A` | 2,738 | 16,476,030 |
| `In Vivo` | 1,528 | 6,882,617 |
| `Biology` | 1,419 | 1,291,675 |
| `Chemistry` | 1,065 | 1,481,422 |
| `Computational Sciences` | 208 | 350,915 |
| `Finance` | 177 | 1,142,781 |

* R&D side: `General R&D`, `Platform`, `Production`, `In Vivo`, `Biology`, `Chemistry`,
  `Computational Sciences`
* G&A side: `General G&A`, `Finance`
* Unallocated: `Non-Specific`

`Non-Specific` carries the largest line count of any department.
Coding-quality work should focus there.

## Other Coding Fields

| Field | Observed values | Note |
|---|---|---|
| `Program: Name` | `00 Non-Specific` (43,946), `- No Program -` (67) | Effectively unused |
| `ProjectID: Name` | `00 Non-Specific` (41,421), `Internal CMC` (2,570), `*Other`, blank | Only `Internal CMC` is a live project code |
| `Type` | Bill (32,506), Bill Payment (5,536), Journal (4,642), Expense Report (1,095), Bill Credit (145), Currency Revaluation (46), Deposit (19), Invoice (14), Payment (6), Credit Memo (4) | |

On a proposed Journal Entry, both sides carry the posted line's Project and Program, so a reclass
leaves no stray balance on either. A new balance sheet line (accounts 1xxxxxx to 3xxxxxx), such
as a debit to `1505000 Capital in Process` or an accrual's credit to `2206000`, takes the
`Non-Specific` department; only income statement lines carry one. The line that reverses the
ledger line being corrected keeps that line's department, on a balance sheet account too, so
it nets the original: a bill recoded off prepaid rent credits prepaid on `General R&D` when the
bill was booked there. In Aug 2026, 123 of the 1,260 ledger lines on balance sheet accounts
carry a department other than `Non-Specific`; whether those should be `Non-Specific` is an
open question to Serif.

The export contains two columns both named `ProjectID: Name`.
The second one, at index 13, holds the real values.
Any loader must address columns positionally, not by header name.

## Chart of Accounts

Accounts are 7-digit and stored as full colon-delimited hierarchy paths, for example
`6000000 - Operating Expenses:6400000 - Lab Expenses:6410000 - Lab Supplies/Consumables`.
139 distinct leaf accounts appear.
The last segment is the posting account.

| Account path | Lines | Net (Dr–Cr) |
|---|---:|---:|
| `1000000 - Operating Cash:1001000 - Checking - SVB:1001054 - Serif - SVB Checking 6800` | 2 | 0 |
| `1000000 - Operating Cash:1004100 - Checking - JPM:1004118 - Serif - JPM Checking 1858` | 3,165 | 1,202,484 |
| `1000000 - Operating Cash:1004500 - Checking - Bridge Bank:1004554 - Serif - Checking BridgeBank 0818` | 26 | -207,573 |
| `1010000 - Restricted Cash - Short Term:1012000 - Credit Card Collateral:1012200 - Credit Card Collateral - Bridge Bank:1012206 - Serif - Bridge Bank Credit Card Collateral 8600` | 26 | 159 |
| `1020000 - Cash Equivalents:1025013 - Serif - JPM Money Market` | 14 | 22,371,962 |
| `1200000 - Accounts Receivable:1210000 - Accounts Receivable 3rd party` | 1 | 8,921 |
| `1200000 - Accounts Receivable:1220000 - Related Party Accounts Receivable` | 11 | 3,000 |
| `1300000 - Prepaid Expenses:1305000 - Prepaid Rent` | 57 | 384,801 |
| `1300000 - Prepaid Expenses:1310000 - Prepaid Insurance` | 11 | -24,790 |
| `1300000 - Prepaid Expenses:1315000 - Prepaid Other` | 82 | 111,093 |
| `1300000 - Prepaid Expenses:1320000 - Prepaid Software` | 66 | 111,685 |
| `1400000 - Other Current Assets:1400001 - Other Current Assets` | 8 | -310,690 |
| `1500000 - Fixed Assets:1505000 - Capital in Process` | 6 | -181,414 |
| `1500000 - Fixed Assets:1510000 - Lab Equipment - New` | 35 | 252,442 |
| `1500000 - Fixed Assets:1530000 - Computers & Software` | 2 | 0 |
| `1500000 - Fixed Assets:1590000 - Finance Lease Right of Use Asset` | 10 | 1,359,797 |
| `1600000 - Accumulated Depreciation:1610000 - Lab Equipment New - A/D` | 24 | -655,567 |
| `1600000 - Accumulated Depreciation:1630000 - Computers & Software - A/D` | 17 | -5,162 |
| `1600000 - Accumulated Depreciation:1650000 - Leasehold Improvements - A/D` | 22 | -71,370 |
| `1600000 - Accumulated Depreciation:1690000 - Finance Lease Right of Use Asset - A/D` | 21 | -507,669 |
| `1700000 - Other Long Term Assets:1710001 - LQ Clearing Account` | 525 | 68,367 |
| `1700000 - Other Long Term Assets:1710004 - Deposits - Other` | 1 | 450,000 |
| `2000000 - Accounts Payable:2000100 - Accounts Payable 3rd party` | 15,685 | -110,373 |
| `2010000 - Notes Payable and Other Debt - Current:2012000 - Notes Payable, Current - Venture Debt` | 17 | -3,166,667 |
| `2010000 - Notes Payable and Other Debt - Current:2012001 - Venture Debt - Principal Repayment` | 8 | 1,333,333 |
| `2010000 - Notes Payable and Other Debt - Current:2013000 - Financing Costs - Current` | 1 | 2,635 |
| `2010000 - Notes Payable and Other Debt - Current:2015000 - Accrued Interest - Venture Debt` | 22 | 10,017 |
| `2010000 - Notes Payable and Other Debt - Current:2065000 - Finance Lease Liabilities - Current` | 247 | -1,005,072 |
| `2020000 - Other Current Liabilities:2050000 - Restricted Stock Liability - Current` | 2 | 76 |
| `2100000 - Credit Card Payable:2101000 - Credit Card - SVB:2101040 - Serif Credit Card - SVB5496` | 2 | 0 |
| `2100000 - Credit Card Payable:2104800 - Credit Card - JPM:2104803 - FL87-Credit Card JPM 9423` | 64 | -14,606 |
| `2200000 - Accrued Expenses:2201000 - Accrued Payroll Benefits and Bonus` | 32 | -357,630 |
| `2200000 - Accrued Expenses:2202000 - Accrued Consulting` | 6 | 0 |
| `2200000 - Accrued Expenses:2203000 - Accrued Facility Costs` | 12 | 0 |
| `2200000 - Accrued Expenses:2204000 - Accrued Legal Fees` | 14 | 29,712 |
| `2200000 - Accrued Expenses:2206000 - Accrued Lab Supplies and External Research` | 48 | -42,831 |
| `2200000 - Accrued Expenses:2206500 - Accrued FSP Charges` | 14 | -288,684 |
| `2200000 - Accrued Expenses:2207000 - Accrued Other` | 6 | 14,498 |
| `2400000 - Notes Payable and Other Debt - Long Term:2410000 - Notes Payable, Long Term - Venture Debt` | 17 | 3,166,667 |
| `2400000 - Notes Payable and Other Debt - Long Term:2415000 - Deferred Debt Financing Costs` | 18 | 56,076 |
| `2400000 - Notes Payable and Other Debt - Long Term:2800000 - Finance Lease Liabilities - Long Term` | 183 | -288,564 |
| `2500000 - Other Long Term Liabilities:2600000 - Warrant Liability` | 6 | -151,859 |
| `2500000 - Other Long Term Liabilities:2700000 - Restricted Stock Liability` | 4 | 151 |
| `3100000 - Common Stock` | 12 | -294 |
| `3200000 - APIC` | 13 | -1,089,592 |
| `3300000 - Preferred Stock:3350001 - Preferred Stock - Series A-2` | 4 | -28,999,995 |
| `3300000 - Preferred Stock:3350100 - Preferred Stock - Series B` | 6 | -89,000,000 |
| `3400000 - Preferred Stock - Issuance Cost:3400003 - Preferred Stock - Series A-2 Issuance Cost` | 2 | 29,454 |
| `3400000 - Preferred Stock - Issuance Cost:3400006 - Preferred Stock - Series B Issuance Cost` | 7 | 190,572 |
| `3500000 - SAFE - Equity` | 5 | 15,000,000 |
| `4000000 - Revenue:4001003 - Revenue - Cost Reimbursement` | 2 | -430,750 |
| `6000000 - Operating Expenses:6100000 - Employee Expenses:6101000 - Salaries` | 349 | 12,048,073 |
| `6000000 - Operating Expenses:6100000 - Employee Expenses:6102000 - Bonus` | 231 | 1,919,562 |
| `6000000 - Operating Expenses:6100000 - Employee Expenses:6102500 - Sign-on Bonus` | 8 | 51,500 |
| `6000000 - Operating Expenses:6100000 - Employee Expenses:6103000 - Payroll Taxes` | 427 | 1,053,518 |
| `6000000 - Operating Expenses:6100000 - Employee Expenses:6104000 - Insurance & Benefits` | 668 | 993,571 |
| `6000000 - Operating Expenses:6100000 - Employee Expenses:6104500 - Commuter Costs` | 20 | 3,890 |
| `6000000 - Operating Expenses:6100000 - Employee Expenses:6105000 - Temp/Contract Employees` | 2 | 8,496 |
| `6000000 - Operating Expenses:6100000 - Employee Expenses:6106000 - Recruiting Fees - Executive` | 9 | 98,432 |
| `6000000 - Operating Expenses:6100000 - Employee Expenses:6106500 - Recruiting Fees - Non-Executive` | 4 | 37,920 |
| `6000000 - Operating Expenses:6100000 - Employee Expenses:6107000 - Relocation Costs` | 1 | 7,500 |
| `6000000 - Operating Expenses:6100000 - Employee Expenses:6109000 - Recruiting Reimbursements` | 2 | 3,372 |
| `6000000 - Operating Expenses:6100000 - Employee Expenses:6110000 - Severance Expenses` | 14 | 89,378 |
| `6000000 - Operating Expenses:6200000 - Consulting:6201000 - General Consulting` | 129 | 811,871 |
| `6000000 - Operating Expenses:6200000 - Consulting:6203000 - SAB Consulting` | 9 | 112,500 |
| `6000000 - Operating Expenses:6200000 - Consulting:6203500 - Management - Indirect Labor` | 12 | 63,076 |
| `6000000 - Operating Expenses:6200000 - Consulting:6204000 - IT Consulting` | 27 | 74,643 |
| `6000000 - Operating Expenses:6200000 - Consulting:6205000 - PR & Marketing Consulting` | 13 | 57,234 |
| `6000000 - Operating Expenses:6200000 - Consulting:6206000 - Procurement` | 13 | 45,000 |
| `6000000 - Operating Expenses:6200000 - Consulting:6210000 - Consultant Reimbursable Expenses` | 5 | 17,458 |
| `6000000 - Operating Expenses:6300000 - Legal & Professional Fees:6311000 - Corporate Legal Fees` | 122 | 981,453 |
| `6000000 - Operating Expenses:6300000 - Legal & Professional Fees:6312000 - Corporate Legal Disbursements` | 40 | 223,490 |
| `6000000 - Operating Expenses:6300000 - Legal & Professional Fees:6321000 - IP Legal Fees` | 22 | 409,424 |
| `6000000 - Operating Expenses:6300000 - Legal & Professional Fees:6322000 - IP Legal Disbursements` | 10 | 194,053 |
| `6000000 - Operating Expenses:6300000 - Legal & Professional Fees:6323000 - IP License Fees` | 2 | 10,234 |
| `6000000 - Operating Expenses:6300000 - Legal & Professional Fees:6340000 - Audit, Tax and Valuations` | 10 | 19,469 |
| `6000000 - Operating Expenses:6400000 - Lab Expenses:6410000 - Lab Supplies/Consumables` | 10,910 | 22,379,177 |
| `6000000 - Operating Expenses:6400000 - Lab Expenses:6415000 - Lab Non-Capital Equipment` | 519 | 589,764 |
| `6000000 - Operating Expenses:6400000 - Lab Expenses:6416000 - Lab Non-Capital Software` | 64 | 238,816 |
| `6000000 - Operating Expenses:6400000 - Lab Expenses:6420000 - Lab Services (Inc. Waste Removal)` | 461 | 455,675 |
| `6000000 - Operating Expenses:6400000 - Lab Expenses:6425000 - Lab Permits and Licenses` | 2 | 2,826 |
| `6000000 - Operating Expenses:6400000 - Lab Expenses:6430000 - Lab Equipment Lease or Rental` | 1 | 3,520 |
| `6000000 - Operating Expenses:6400000 - Lab Expenses:6435000 - Lab Equipment Repairs & Maintenance` | 133 | 358,945 |
| `6000000 - Operating Expenses:6500000 - External Research:6501000 - Sequencing Costs` | 2,454 | 334,059 |
| `6000000 - Operating Expenses:6500000 - External Research:6501100 - Synthesis Costs` | 844 | 530,322 |
| `6000000 - Operating Expenses:6500000 - External Research:6502000 - In Vivo Studies` | 208 | 4,342,018 |
| `6000000 - Operating Expenses:6500000 - External Research:6502500 - In Vitro Studies` | 25 | 35,747 |
| `6000000 - Operating Expenses:6500000 - External Research:6504000 - CMC` | 2,475 | 5,351,139 |
| `6000000 - Operating Expenses:6500000 - External Research:6508000 - Partnered Research` | 40 | 5,094,981 |
| `6000000 - Operating Expenses:6500000 - External Research:6509000 - Other External Research costs` | 91 | 525,676 |
| `6000000 - Operating Expenses:6500000 - External Research:6550000 - Intercompany Research` | 2 | 0 |
| `6000000 - Operating Expenses:6600000 - Facilities Expense:6601000 - Rent or Lease of Buildings` | 62 | 5,245,917 |
| `6000000 - Operating Expenses:6600000 - Facilities Expense:6603000 - Parking` | 245 | 239,270 |
| `6000000 - Operating Expenses:6600000 - Facilities Expense:6604000 - Utilities` | 5 | 134 |
| `6000000 - Operating Expenses:6600000 - Facilities Expense:6605000 - Cleaning` | 53 | 67,626 |
| `6000000 - Operating Expenses:6600000 - Facilities Expense:6606000 - Real Estate Taxes` | 12 | 27,717 |
| `6000000 - Operating Expenses:6600000 - Facilities Expense:6607000 - Facility Repairs & Maintenance` | 101 | 180,348 |
| `6000000 - Operating Expenses:6600000 - Facilities Expense:6608000 - Moving Expenses` | 4 | 3,906 |
| `6000000 - Operating Expenses:6600000 - Facilities Expense:6609000 - Building Operating Costs & CAM Expenses` | 78 | 2,014,594 |
| `6000000 - Operating Expenses:6700000 - Travel & Entertainment:6701000 - Conference/Seminars/Courses` | 35 | 77,623 |
| `6000000 - Operating Expenses:6700000 - Travel & Entertainment:6702000 - Travel` | 235 | 188,114 |
| `6000000 - Operating Expenses:6700000 - Travel & Entertainment:6703000 - Meals & Entertainment` | 167 | 46,672 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6810000 - Office Supplies/Expense` | 715 | 150,264 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6815000 - Office Non-Cap Equipment/Furniture` | 66 | 115,067 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6816000 - Office Non-Cap Software` | 277 | 882,321 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6820000 - Office Meetings (Inc. Food)` | 109 | 240,657 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6825000 - Office Functions` | 24 | 64,894 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6830000 - Office Equipment Lease/Rental` | 6 | 507 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6835000 - Postage/Shipping/Delivery` | 87 | 78,512 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6845000 - Payroll Service` | 27 | 30,050 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6850000 - Phone & Network` | 8 | 11,871 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6860000 - Research Books/Articles` | 3 | 263 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6865000 - Non-Income Taxes` | 15 | 44,621 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6870000 - Bank fees` | 27 | 7,762 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6885000 - Website` | 12 | 133,389 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6888000 - Marketing / Company Branded Swag` | 11 | 39,966 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6890000 - Dues & Subscriptions` | 21 | 18,734 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6891000 - Package Insurance` | 15 | 73,544 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6892000 - D&O Insurance` | 1 | 24,425 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6893000 - Commercial Insurance` | 1 | 724 |
| `6000000 - Operating Expenses:6800000 - Administrative Expenses:6895000 - Donations` | 1 | 13 |
| `6000000 - Operating Expenses:6900000 - FSP Operating Charges:6901000 - FSP Charges - Origination` | 34 | 2,407,407 |
| `6000000 - Operating Expenses:6900000 - FSP Operating Charges:6901100 - FSP Charges - Functions` | 34 | 2,415,863 |
| `6000000 - Operating Expenses:6900000 - FSP Operating Charges:6901200 - FSP Charges - OH allocation` | 34 | 3,465,522 |
| `7000000 - Non-Cash Operating Expense:7100000 - Depreciation & Amortization:7110000 - Depreciation - Lab Equipment` | 20 | 661,795 |
| `7000000 - Non-Cash Operating Expense:7100000 - Depreciation & Amortization:7130000 - Depreciation - Computers & Software` | 17 | 5,162 |
| `7000000 - Non-Cash Operating Expense:7100000 - Depreciation & Amortization:7150000 - Depreciation - Leasehold Improvements` | 20 | 71,370 |
| `7000000 - Non-Cash Operating Expense:7100000 - Depreciation & Amortization:7160000 - Depreciation - Finance Lease Right of Use Asset` | 20 | 507,669 |
| `7000000 - Non-Cash Operating Expense:7300000 - Other Non-Cash Operating Expenses:7301000 - Stock Compensation` | 7 | 1,063,156 |
| `8100000 - Other Income:8110000 - Interest Income:8111000 - Interest Income` | 25 | -472,121 |
| `8100000 - Other Income:8122000 - Research and Development Tax Credit` | 3 | -500,000 |
| `8100000 - Other Income:8124000 - Unrealized Gain/Loss on Investments` | 4 | 0 |
| `8200000 - Other Expense:8210000 - Interest Expense:8201000 - Interest - Deferred Financing Costs` | 17 | 51,515 |
| `8200000 - Other Expense:8210000 - Interest Expense:8202000 - Interest Expense - Cash` | 333 | 1,436,952 |
| `8200000 - Other Expense:8220000 - Other Expense:8223000 - Gain or Loss of Fixed Asset` | 3 | 8,145 |
| `8200000 - Other Expense:8220000 - Other Expense:8224000 - Change in FMV warrant liability` | 5 | 41,632 |
| `8200000 - Other Expense:8220000 - Other Expense:8229000 - Rounding Gain/Loss DO NOT USE` | 11 | 132 |
| `8231000 - Foreign Exchange Realized Gain/Loss` | 27 | 1,758 |
| `8232000 - Foreign Exchange Unrealized Gain/Loss` | 7 | 2 |
