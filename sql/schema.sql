-- T03 SQLite storage. Monetary source values are loaded as integer pence
-- to avoid floating-point reconciliation drift.
DROP TABLE IF EXISTS monthly_control;
DROP TABLE IF EXISTS account_month;

CREATE TABLE account_month (
    account_id TEXT NOT NULL,
    snapshot_month TEXT NOT NULL,
    origination_month TEXT NOT NULL,
    account_status TEXT NOT NULL CHECK (account_status IN ('ACTIVE', 'CLOSED')),
    risk_segment TEXT NOT NULL CHECK (risk_segment IN ('LOWER', 'MIDDLE', 'HIGHER')),
    acquisition_channel TEXT NOT NULL CHECK (acquisition_channel IN ('DIRECT', 'PARTNER')),
    customer_age_band TEXT NOT NULL,
    credit_limit_pence INTEGER NOT NULL CHECK (credit_limit_pence > 0),
    opening_balance_pence INTEGER NOT NULL CHECK (opening_balance_pence >= 0),
    purchase_amount_pence INTEGER NOT NULL CHECK (purchase_amount_pence >= 0),
    interest_fee_amount_pence INTEGER NOT NULL CHECK (interest_fee_amount_pence >= 0),
    payment_due_pence INTEGER NOT NULL CHECK (payment_due_pence >= 0),
    payment_received_pence INTEGER NOT NULL CHECK (payment_received_pence >= 0),
    other_adjustment_pence INTEGER NOT NULL,
    closing_balance_pence INTEGER NOT NULL CHECK (closing_balance_pence >= 0),
    days_past_due INTEGER NOT NULL CHECK (days_past_due >= 0),
    delinquency_status TEXT NOT NULL,
    PRIMARY KEY (account_id, snapshot_month)
);

CREATE INDEX idx_account_month_date ON account_month(snapshot_month);
CREATE INDEX idx_account_month_segment ON account_month(risk_segment, snapshot_month);
CREATE INDEX idx_account_month_vintage ON account_month(origination_month, snapshot_month);

CREATE TABLE monthly_control (
    snapshot_month TEXT PRIMARY KEY,
    account_month_rows INTEGER NOT NULL,
    active_accounts INTEGER NOT NULL,
    closed_rows INTEGER NOT NULL,
    originations INTEGER NOT NULL,
    active_balance_pence INTEGER NOT NULL,
    active_limit_pence INTEGER NOT NULL,
    active_payment_due_pence INTEGER NOT NULL,
    active_payment_received_pence INTEGER NOT NULL
);
