-- Account-count transitions between consecutive month-end states.
-- Closed is an explicit destination. Accounts without a next-month observation
-- (including right-censored final-month survivors) are outside the denominator.
WITH transitions AS (
    SELECT a.snapshot_month AS opening_month,
           a.delinquency_status AS opening_state,
           b.delinquency_status AS destination_state,
           COUNT(*) AS transitioned_accounts
    FROM account_month AS a
    JOIN account_month AS b
      ON b.account_id = a.account_id
     AND date(b.snapshot_month, 'start of month') = date(a.snapshot_month, 'start of month', '+1 month')
    WHERE a.account_status = 'ACTIVE'
    GROUP BY a.snapshot_month, a.delinquency_status, b.delinquency_status
), denominators AS (
    SELECT opening_month, opening_state, SUM(transitioned_accounts) AS opening_accounts_with_outcome
    FROM transitions
    GROUP BY opening_month, opening_state
)
SELECT t.opening_month, t.opening_state, t.destination_state,
       t.transitioned_accounts, d.opening_accounts_with_outcome,
       1.0 * t.transitioned_accounts / d.opening_accounts_with_outcome AS roll_rate
FROM transitions AS t
JOIN denominators AS d USING (opening_month, opening_state)
ORDER BY t.opening_month, t.opening_state,
    CASE t.destination_state WHEN 'CURRENT' THEN 1 WHEN '1_29' THEN 2
        WHEN '30_59' THEN 3 WHEN '60_89' THEN 4 WHEN '90_PLUS' THEN 5
        WHEN 'CLOSED' THEN 6 ELSE 7 END;
