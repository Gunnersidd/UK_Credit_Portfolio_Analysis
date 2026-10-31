-- Monthly active population by generated delinquency-state proxy.
WITH buckets AS (
    SELECT snapshot_month, delinquency_status,
           COUNT(*) AS active_accounts,
           SUM(closing_balance_pence) AS active_balance_pence
    FROM account_month
    WHERE account_status = 'ACTIVE'
    GROUP BY snapshot_month, delinquency_status
)
SELECT snapshot_month, delinquency_status, active_accounts, active_balance_pence,
       SUM(active_accounts) OVER (PARTITION BY snapshot_month) AS monthly_active_accounts,
       SUM(active_balance_pence) OVER (PARTITION BY snapshot_month) AS monthly_active_balance_pence,
       1.0 * active_accounts / SUM(active_accounts) OVER (PARTITION BY snapshot_month) AS account_share,
       CASE WHEN SUM(active_balance_pence) OVER (PARTITION BY snapshot_month) > 0
            THEN 1.0 * active_balance_pence / SUM(active_balance_pence) OVER (PARTITION BY snapshot_month) END AS balance_share
FROM buckets
ORDER BY snapshot_month,
    CASE delinquency_status
        WHEN 'CURRENT' THEN 1 WHEN '1_29' THEN 2 WHEN '30_59' THEN 3
        WHEN '60_89' THEN 4 WHEN '90_PLUS' THEN 5 ELSE 6 END;
