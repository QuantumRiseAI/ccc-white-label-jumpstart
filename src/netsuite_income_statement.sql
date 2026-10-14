-- The Income Statement for subsidiary 97 (FL87 Serif Biomedicines, Inc.) by accounting
-- period: each P&L account's posted debits and credits, the month and the month before.
-- Replace Aug 2026 and Sep 2026 with the month before and the close month.
-- Save the result as netsuite_income_statement_by_period_<months>.csv (eg
-- netsuite_income_statement_by_period_aug-sep2026.csv), written with code straight from
-- the results, every row as returned. Grouped by accounting period, as NetSuite's
-- Income Statement is; a query grouped by transaction date does not tie.
SELECT ap.periodname AS period,
       a.acctnumber AS account_number,
       a.fullname AS account_name,
       a.accttype AS account_type,
       SUM(NVL(tal.debit, 0)) AS debit,
       SUM(NVL(tal.credit, 0)) AS credit,
       SUM(NVL(tal.debit, 0)) - SUM(NVL(tal.credit, 0)) AS amount
FROM transactionaccountingline tal
JOIN transaction t ON t.id = tal.transaction
JOIN transactionline tl ON tl.transaction = tal.transaction AND tl.id = tal.transactionline
JOIN account a ON a.id = tal.account
JOIN accountingperiod ap ON ap.id = t.postingperiod
WHERE tl.subsidiary = 97
  AND tal.posting = 'T'
  AND a.accttype IN ('Income', 'OthIncome', 'COGS', 'Expense', 'OthExpense')
  AND ap.periodname IN ('Aug 2026', 'Sep 2026')
GROUP BY ap.periodname, a.acctnumber, a.fullname, a.accttype
ORDER BY a.acctnumber, ap.periodname
