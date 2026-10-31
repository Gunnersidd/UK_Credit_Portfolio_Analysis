-- Each returned check should have failure_count = 0.
WITH ordered AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY snapshot_month) AS row_num,
           LAG(snapshot_month) OVER (PARTITION BY account_id ORDER BY snapshot_month) AS prior_month,
           LAG(closing_balance_pence) OVER (PARTITION BY account_id ORDER BY snapshot_month) AS prior_closing_pence,
           LAG(account_status) OVER (PARTITION BY account_id ORDER BY snapshot_month) AS prior_status
    FROM account_month
), monthly AS (
    SELECT snapshot_month,
           COUNT(*) AS account_month_rows,
           SUM(account_status = 'ACTIVE') AS active_accounts,
           SUM(account_status = 'CLOSED') AS closed_rows,
           SUM(snapshot_month = origination_month) AS originations,
           SUM(CASE WHEN account_status = 'ACTIVE' THEN closing_balance_pence ELSE 0 END) AS active_balance_pence,
           SUM(CASE WHEN account_status = 'ACTIVE' THEN credit_limit_pence ELSE 0 END) AS active_limit_pence,
           SUM(CASE WHEN account_status = 'ACTIVE' THEN payment_due_pence ELSE 0 END) AS active_payment_due_pence,
           SUM(CASE WHEN account_status = 'ACTIVE' THEN payment_received_pence ELSE 0 END) AS active_payment_received_pence
    FROM account_month GROUP BY snapshot_month
)
SELECT 'required_fields_null' AS check_name, COUNT(*) AS failure_count
FROM account_month WHERE account_id IS NULL OR snapshot_month IS NULL OR origination_month IS NULL
   OR account_status IS NULL OR risk_segment IS NULL OR credit_limit_pence IS NULL
   OR opening_balance_pence IS NULL OR closing_balance_pence IS NULL OR delinquency_status IS NULL
UNION ALL
SELECT 'balance_equation_mismatch', COUNT(*) FROM account_month
WHERE closing_balance_pence <> opening_balance_pence + purchase_amount_pence
    + interest_fee_amount_pence - payment_received_pence + other_adjustment_pence
UNION ALL
SELECT 'invalid_dpd_bucket', COUNT(*) FROM account_month
WHERE (account_status = 'ACTIVE' AND NOT (
       (days_past_due = 0 AND delinquency_status = 'CURRENT')
    OR (days_past_due BETWEEN 1 AND 29 AND delinquency_status = '1_29')
    OR (days_past_due BETWEEN 30 AND 59 AND delinquency_status = '30_59')
    OR (days_past_due BETWEEN 60 AND 89 AND delinquency_status = '60_89')
    OR (days_past_due >= 90 AND delinquency_status = '90_PLUS')))
    OR (account_status = 'CLOSED' AND (delinquency_status <> 'CLOSED' OR days_past_due <> 0 OR closing_balance_pence <> 0))
UNION ALL
SELECT 'account_month_continuity_or_lifecycle', COUNT(*) FROM ordered
WHERE row_num > 1 AND (
       date(snapshot_month, 'start of month') <> date(prior_month, 'start of month', '+1 month')
    OR opening_balance_pence <> prior_closing_pence
    OR prior_status = 'CLOSED')
UNION ALL
SELECT 'originations_not_zero_opening', COUNT(*) FROM account_month
WHERE snapshot_month = origination_month AND opening_balance_pence <> 0
UNION ALL
SELECT 'monthly_control_reconciliation', COUNT(*) FROM monthly AS m
LEFT JOIN monthly_control AS c USING (snapshot_month)
WHERE c.snapshot_month IS NULL
   OR m.account_month_rows <> c.account_month_rows
   OR m.active_accounts <> c.active_accounts
   OR m.closed_rows <> c.closed_rows
   OR m.originations <> c.originations
   OR m.active_balance_pence <> c.active_balance_pence
   OR m.active_limit_pence <> c.active_limit_pence
   OR m.active_payment_due_pence <> c.active_payment_due_pence
   OR m.active_payment_received_pence <> c.active_payment_received_pence
UNION ALL
SELECT 'control_month_missing_from_fact', COUNT(*) FROM monthly_control AS c
LEFT JOIN monthly AS m USING (snapshot_month)
WHERE m.snapshot_month IS NULL;
