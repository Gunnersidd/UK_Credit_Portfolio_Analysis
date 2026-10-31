-- Month-by-month cuts by synthetic origination risk segment.
SELECT
    snapshot_month,
    risk_segment,
    COUNT(*) AS active_accounts,
    SUM(closing_balance_pence) AS active_balance_pence,
    SUM(credit_limit_pence) AS active_limit_pence,
    SUM(CASE WHEN days_past_due >= 30 THEN 1 ELSE 0 END) AS simulated_30plus_accounts,
    SUM(CASE WHEN days_past_due >= 30 THEN closing_balance_pence ELSE 0 END) AS simulated_30plus_balance_pence,
    SUM(payment_due_pence) AS active_payment_due_pence,
    SUM(payment_received_pence) AS active_payment_received_pence,
    1.0 * SUM(closing_balance_pence) / SUM(credit_limit_pence) AS portfolio_utilisation,
    1.0 * SUM(CASE WHEN days_past_due >= 30 THEN 1 ELSE 0 END) / COUNT(*) AS simulated_30plus_account_rate,
    CASE WHEN SUM(closing_balance_pence) > 0
        THEN 1.0 * SUM(CASE WHEN days_past_due >= 30 THEN closing_balance_pence ELSE 0 END) / SUM(closing_balance_pence) END AS simulated_30plus_balance_rate,
    CASE WHEN SUM(payment_due_pence) > 0 THEN 1.0 * SUM(payment_received_pence) / SUM(payment_due_pence) END AS payment_rate
FROM account_month
WHERE account_status = 'ACTIVE'
GROUP BY snapshot_month, risk_segment
ORDER BY snapshot_month, risk_segment;
