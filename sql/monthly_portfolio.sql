-- Monthly stock and flow measures. 30+ values are simulated delinquency-state
-- proxies, not arrears aged from dated bills.
SELECT
    snapshot_month,
    COUNT(*) AS account_month_rows,
    SUM(CASE WHEN snapshot_month = origination_month THEN 1 ELSE 0 END) AS originations,
    SUM(CASE WHEN account_status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_accounts,
    SUM(CASE WHEN account_status = 'CLOSED' THEN 1 ELSE 0 END) AS closed_accounts,
    SUM(CASE WHEN account_status = 'ACTIVE' THEN closing_balance_pence ELSE 0 END) AS active_balance_pence,
    SUM(CASE WHEN account_status = 'ACTIVE' THEN credit_limit_pence ELSE 0 END) AS active_limit_pence,
    SUM(CASE WHEN account_status = 'ACTIVE' THEN payment_due_pence ELSE 0 END) AS active_payment_due_pence,
    SUM(CASE WHEN account_status = 'ACTIVE' THEN payment_received_pence ELSE 0 END) AS active_payment_received_pence,
    SUM(CASE WHEN account_status = 'CLOSED' THEN payment_received_pence ELSE 0 END) AS closed_final_payment_received_pence,
    SUM(CASE WHEN account_status = 'ACTIVE' AND days_past_due >= 30 THEN 1 ELSE 0 END) AS simulated_30plus_accounts,
    SUM(CASE WHEN account_status = 'ACTIVE' AND days_past_due >= 30 THEN closing_balance_pence ELSE 0 END) AS simulated_30plus_balance_pence,
    CASE WHEN SUM(CASE WHEN account_status = 'ACTIVE' THEN credit_limit_pence ELSE 0 END) > 0
        THEN 1.0 * SUM(CASE WHEN account_status = 'ACTIVE' THEN closing_balance_pence ELSE 0 END)
             / SUM(CASE WHEN account_status = 'ACTIVE' THEN credit_limit_pence ELSE 0 END) END AS portfolio_utilisation,
    CASE WHEN SUM(CASE WHEN account_status = 'ACTIVE' THEN 1 ELSE 0 END) > 0
        THEN 1.0 * SUM(CASE WHEN account_status = 'ACTIVE' AND days_past_due >= 30 THEN 1 ELSE 0 END)
             / SUM(CASE WHEN account_status = 'ACTIVE' THEN 1 ELSE 0 END) END AS simulated_30plus_account_rate,
    CASE WHEN SUM(CASE WHEN account_status = 'ACTIVE' THEN closing_balance_pence ELSE 0 END) > 0
        THEN 1.0 * SUM(CASE WHEN account_status = 'ACTIVE' AND days_past_due >= 30 THEN closing_balance_pence ELSE 0 END)
             / SUM(CASE WHEN account_status = 'ACTIVE' THEN closing_balance_pence ELSE 0 END) END AS simulated_30plus_balance_rate,
    CASE WHEN SUM(CASE WHEN account_status = 'ACTIVE' THEN payment_due_pence ELSE 0 END) > 0
        THEN 1.0 * SUM(CASE WHEN account_status = 'ACTIVE' THEN payment_received_pence ELSE 0 END)
             / SUM(CASE WHEN account_status = 'ACTIVE' THEN payment_due_pence ELSE 0 END) END AS payment_rate
FROM account_month
GROUP BY snapshot_month
ORDER BY snapshot_month;
