-- Cohort/MOB view. Observed accounts includes a final CLOSED row; active stocks
-- and delinquency rates use active rows only. MOB 0 is origination month.
WITH observations AS (
    SELECT
        origination_month,
        snapshot_month,
        ((CAST(strftime('%Y', snapshot_month) AS INTEGER) - CAST(strftime('%Y', origination_month) AS INTEGER)) * 12
          + CAST(strftime('%m', snapshot_month) AS INTEGER) - CAST(strftime('%m', origination_month) AS INTEGER)) AS mob,
        account_id,
        account_status,
        closing_balance_pence,
        credit_limit_pence,
        days_past_due,
        payment_due_pence,
        payment_received_pence
    FROM account_month
)
SELECT
    origination_month,
    mob,
    COUNT(DISTINCT account_id) AS observed_accounts,
    SUM(CASE WHEN account_status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_accounts,
    SUM(CASE WHEN account_status = 'CLOSED' THEN 1 ELSE 0 END) AS closed_accounts,
    SUM(CASE WHEN account_status = 'ACTIVE' THEN closing_balance_pence ELSE 0 END) AS active_balance_pence,
    SUM(CASE WHEN account_status = 'ACTIVE' THEN credit_limit_pence ELSE 0 END) AS active_limit_pence,
    SUM(CASE WHEN account_status = 'ACTIVE' AND days_past_due >= 30 THEN 1 ELSE 0 END) AS simulated_30plus_accounts,
    SUM(CASE WHEN account_status = 'ACTIVE' AND days_past_due >= 30 THEN closing_balance_pence ELSE 0 END) AS simulated_30plus_balance_pence,
    SUM(CASE WHEN account_status = 'ACTIVE' THEN payment_due_pence ELSE 0 END) AS active_payment_due_pence,
    SUM(CASE WHEN account_status = 'ACTIVE' THEN payment_received_pence ELSE 0 END) AS active_payment_received_pence,
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
FROM observations
GROUP BY origination_month, mob
ORDER BY origination_month, mob;
