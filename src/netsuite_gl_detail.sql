-- The general ledger for one month: every posted line of subsidiary 97 (FL87 Serif
-- Biomedicines, Inc.), with the columns the scripts read. Program is the class field and
-- ProjectID the custcol_cseg_sik_project segment. Replace Sep 2026 with the close month.
-- Save the result as netsuite_gl_detail_<month><year>.csv (eg netsuite_gl_detail_sep2026.csv),
-- written with code straight from the results, every row as returned. Run it at the same
-- time as netsuite_income_statement.sql, so an entry posted in between is in both.
SELECT a.acctnumber AS account_number,
       a.fullname AS account_name,
       BUILTIN.DF(t.type) AS type,
       TO_CHAR(t.trandate, 'YYYY-MM-DD') AS date,
       t.tranid AS document_number,
       BUILTIN.DF(tl.entity) AS name,
       tal.debit AS debit,
       tal.credit AS credit,
       ap.periodname AS period,
       BUILTIN.DF(tl.department) AS department,
       BUILTIN.DF(tl.class) AS program,
       BUILTIN.DF(tl.custcol_cseg_sik_project) AS project,
       BUILTIN.DF(tl.subsidiary) AS subsidiary,
       tl.memo AS description,
       t.memo AS memo,
       t.id AS internal_id,
       tal.transactionline AS line_id,
       t.custbody_coupa_transaction_url AS coupa_transaction_url,
       tl.custcol_coupa_po_num AS coupa_po_num
FROM transactionaccountingline tal
JOIN transaction t ON t.id = tal.transaction
JOIN transactionline tl ON tl.transaction = tal.transaction AND tl.id = tal.transactionline
JOIN account a ON a.id = tal.account
JOIN accountingperiod ap ON ap.id = t.postingperiod
WHERE tl.subsidiary = 97
  AND tal.posting = 'T'
  AND ap.periodname = 'Sep 2026'
ORDER BY t.id, tal.transactionline
