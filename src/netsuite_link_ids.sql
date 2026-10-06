-- NetSuite link IDs for one month: every posting line of subsidiary 97 (FL87 Serif
-- Biomedicines, Inc.), with its transaction's internal ID, the bill's Coupa invoice
-- address and the line's Coupa PO. Replace Sep 2026 with the close month.
-- Save the result as netsuite_link_ids_<month><year>.csv (eg netsuite_link_ids_sep2026.csv),
-- written with code straight from the results, every row as returned.
SELECT t.id AS internal_id, t.tranid AS document_number, t.type AS type,
       TO_CHAR(t.trandate, 'YYYY-MM-DD') AS trandate, ap.periodname AS period,
       tal.transactionline AS line_id, a.acctnumber AS account_number,
       tal.debit AS debit, tal.credit AS credit,
       t.custbody_coupa_transaction_url AS coupa_transaction_url,
       tl.custcol_coupa_po_num AS coupa_po_num
FROM transactionaccountingline tal
JOIN transaction t ON t.id = tal.transaction
JOIN transactionline tl ON tl.transaction = tal.transaction AND tl.id = tal.transactionline
JOIN account a ON a.id = tal.account
JOIN accountingperiod ap ON ap.id = t.postingperiod
WHERE tl.subsidiary = 97 AND tal.posting = 'T' AND ap.periodname = 'Sep 2026'
ORDER BY t.id, tal.transactionline
