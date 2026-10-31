#!/usr/bin/env python3
"""Load the synthetic CSV into SQLite, run T03 queries, and export results."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FIELDS = [
    "account_id", "snapshot_month", "origination_month", "account_status",
    "risk_segment", "acquisition_channel", "customer_age_band",
    "credit_limit_gbp", "opening_balance_gbp", "purchase_amount_gbp",
    "interest_fee_amount_gbp", "payment_due_gbp", "payment_received_gbp",
    "other_adjustment_gbp", "closing_balance_gbp", "days_past_due",
    "delinquency_status",
]
MONEY_TO_PENCE = {
    "credit_limit_gbp": "credit_limit_pence",
    "opening_balance_gbp": "opening_balance_pence",
    "purchase_amount_gbp": "purchase_amount_pence",
    "interest_fee_amount_gbp": "interest_fee_amount_pence",
    "payment_due_gbp": "payment_due_pence",
    "payment_received_gbp": "payment_received_pence",
    "other_adjustment_gbp": "other_adjustment_pence",
    "closing_balance_gbp": "closing_balance_pence",
}
DB_FIELDS = [
    "account_id", "snapshot_month", "origination_month", "account_status",
    "risk_segment", "acquisition_channel", "customer_age_band",
    "credit_limit_pence", "opening_balance_pence", "purchase_amount_pence",
    "interest_fee_amount_pence", "payment_due_pence", "payment_received_pence",
    "other_adjustment_pence", "closing_balance_pence", "days_past_due",
    "delinquency_status",
]
CONTROL_MAP = {
    "active_balance_gbp": "active_balance_pence",
    "active_limit_gbp": "active_limit_pence",
    "active_payment_due_gbp": "active_payment_due_pence",
    "active_payment_received_gbp": "active_payment_received_pence",
}
QUERIES = {
    "monthly_portfolio": "monthly_portfolio.sql",
    "risk_segment": "risk_segment.sql",
    "vintage_mob": "vintage_mob.sql",
    "delinquency_state": "delinquency_state.sql",
    "roll_rates": "roll_rates.sql",
}


def to_pence(value: str) -> int:
    return int(Decimal(value) * 100)


def load_source(connection: sqlite3.Connection, source: Path) -> int:
    fields = [MONEY_TO_PENCE.get(field, field) for field in SOURCE_FIELDS]
    placeholders = ",".join("?" for _ in fields)
    insert_sql = f"INSERT INTO account_month ({','.join(fields)}) VALUES ({placeholders})"
    count = 0
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != SOURCE_FIELDS:
            raise ValueError(f"Unexpected source columns: {reader.fieldnames}")
        batch = []
        for row in reader:
            values = []
            for field in SOURCE_FIELDS:
                values.append(to_pence(row[field]) if field in MONEY_TO_PENCE else row[field])
            batch.append(values)
            if len(batch) >= 5_000:
                connection.executemany(insert_sql, batch)
                count += len(batch)
                batch.clear()
        if batch:
            connection.executemany(insert_sql, batch)
            count += len(batch)
    return count


def load_controls(connection: sqlite3.Connection, path: Path) -> int:
    fields = [
        "snapshot_month", "account_month_rows", "active_accounts", "closed_rows",
        "originations", "active_balance_pence", "active_limit_pence",
        "active_payment_due_pence", "active_payment_received_pence",
    ]
    count = 0
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        batch = []
        for row in reader:
            values = []
            for field in fields:
                source_field = next((name for name, target in CONTROL_MAP.items() if target == field), field)
                raw = row[source_field]
                values.append(to_pence(raw) if source_field in CONTROL_MAP else int(raw) if field != "snapshot_month" else raw)
            batch.append(values)
        connection.executemany(f"INSERT INTO monthly_control ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", batch)
        count = len(batch)
    return count


def export_query(connection: sqlite3.Connection, sql_path: Path, output_path: Path) -> int:
    cursor = connection.execute(sql_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow([column[0] for column in cursor.description])
        rows = cursor.fetchall()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "data/synthetic_portfolio.csv")
    parser.add_argument("--controls", type=Path, default=ROOT / "data/monthly_portfolio_control_totals.csv")
    parser.add_argument("--database", type=Path, default=ROOT / "data/portfolio.sqlite")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/t03/sql")
    args = parser.parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(args.database)
    try:
        connection.executescript((ROOT / "sql/schema.sql").read_text(encoding="utf-8"))
        fact_rows = load_source(connection, args.source)
        control_rows = load_controls(connection, args.controls)
        connection.commit()

        audit_cursor = connection.execute((ROOT / "sql/reconciliation_checks.sql").read_text(encoding="utf-8"))
        audit_rows = audit_cursor.fetchall()
        with (args.output_dir / "reconciliation_checks.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["check_name", "failure_count"])
            writer.writerows(audit_rows)
        failures = [(name, count) for name, count in audit_rows if count != 0]
        if failures:
            raise RuntimeError(f"SQL reconciliation checks failed: {failures}")

        output_counts = {}
        for name, sql_file in QUERIES.items():
            output_counts[name] = export_query(connection, ROOT / "sql" / sql_file, args.output_dir / f"{name}.csv")
        roll_rows = []
        with (args.output_dir / "roll_rates.csv").open(newline="", encoding="utf-8") as handle:
            roll_rows = list(csv.DictReader(handle))
        roll_groups: dict[tuple[str, str], tuple[int, int]] = {}
        for row in roll_rows:
            key = (row["opening_month"], row["opening_state"])
            transitions, denominator = roll_groups.get(key, (0, int(row["opening_accounts_with_outcome"])))
            if denominator != int(row["opening_accounts_with_outcome"]):
                raise RuntimeError(f"Inconsistent roll-rate denominator for {key}")
            roll_groups[key] = (transitions + int(row["transitioned_accounts"]), denominator)
        roll_failures = sum(transitions != denominator for transitions, denominator in roll_groups.values())
        with (args.output_dir / "reconciliation_checks.csv").open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(["roll_rate_destinations_sum_to_denominator", roll_failures])
        if roll_failures:
            raise RuntimeError(f"Roll-rate destinations fail to sum to denominators for {roll_failures} state-months")
        db_rows = connection.execute("SELECT COUNT(*) FROM account_month").fetchone()[0]
        if db_rows != fact_rows:
            raise RuntimeError(f"Loaded row count {db_rows} differs from CSV row count {fact_rows}")
        print(f"Loaded {fact_rows:,} fact rows and {control_rows} monthly control rows into {args.database}")
        print(f"Reconciliation checks: {len(audit_rows) + 1} passed with zero failures")
        print(f"Query exports: {output_counts}")
        print(f"SQL outputs: {args.output_dir}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
