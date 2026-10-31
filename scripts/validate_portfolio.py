#!/usr/bin/env python3
"""Validate the synthetic portfolio CSV using only Python's standard library."""

from __future__ import annotations

import argparse
import calendar
import csv
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

EXPECTED_FIELDS = [
    "account_id", "snapshot_month", "origination_month", "account_status",
    "risk_segment", "acquisition_channel", "customer_age_band",
    "credit_limit_gbp", "opening_balance_gbp", "purchase_amount_gbp",
    "interest_fee_amount_gbp", "payment_due_gbp", "payment_received_gbp",
    "other_adjustment_gbp", "closing_balance_gbp", "days_past_due",
    "delinquency_status",
]
MONEY_FIELDS = [
    "credit_limit_gbp", "opening_balance_gbp", "purchase_amount_gbp",
    "interest_fee_amount_gbp", "payment_due_gbp", "payment_received_gbp",
    "other_adjustment_gbp", "closing_balance_gbp",
]
BUCKETS = [(0, 0, "CURRENT"), (1, 29, "1_29"), (30, 59, "30_59"), (60, 89, "60_89"), (90, 10**9, "90_PLUS")]
ALLOWED_TRANSITIONS = {
    "CURRENT": {"CURRENT", "1_29"},
    "1_29": {"CURRENT", "1_29", "30_59"},
    "30_59": {"CURRENT", "1_29", "30_59", "60_89"},
    "60_89": {"CURRENT", "1_29", "30_59", "60_89", "90_PLUS"},
    "90_PLUS": {"CURRENT", "1_29", "30_59", "60_89", "90_PLUS"},
}
ALLOWED_SEGMENTS = {"LOWER", "MIDDLE", "HIGHER"}
ALLOWED_CHANNELS = {"DIRECT", "PARTNER"}
ALLOWED_AGES = {"18-24", "25-34", "35-49", "50-64", "65+"}
LIMIT_BOUNDS = {"LOWER": (Decimal("500.00"), Decimal("10000.00")), "MIDDLE": (Decimal("500.00"), Decimal("7500.00")), "HIGHER": (Decimal("500.00"), Decimal("5000.00"))}


def money(value: str) -> Decimal:
    return Decimal(value)


def expected_bucket(dpd: int) -> str:
    for low, high, label in BUCKETS:
        if low <= dpd <= high:
            return label
    raise ValueError(f"Invalid DPD value: {dpd}")


def validate(path: Path) -> dict[str, object]:
    failures: list[str] = []
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_FIELDS:
            failures.append(f"Header mismatch: {reader.fieldnames}")
        for line_number, row in enumerate(reader, start=2):
            if None in row or any(value is None or value == "" for value in row.values()):
                failures.append(f"Missing/extra field at CSV line {line_number}")
            try:
                date.fromisoformat(row["snapshot_month"])
                origination = date.fromisoformat(row["origination_month"])
                observed = date.fromisoformat(row["snapshot_month"])
                if observed.day != calendar.monthrange(observed.year, observed.month)[1]:
                    failures.append(f"Non-month-end snapshot at line {line_number}")
                if origination > observed:
                    failures.append(f"Origination after observation at line {line_number}")
                for field in MONEY_FIELDS:
                    money(row[field])
                dpd = int(row["days_past_due"])
            except Exception as exc:  # Report malformed rows and continue collecting evidence.
                failures.append(f"Malformed value at line {line_number}: {exc}")
                continue
            if any(money(row[field]) < 0 for field in ["credit_limit_gbp", "opening_balance_gbp", "purchase_amount_gbp", "interest_fee_amount_gbp", "payment_due_gbp", "payment_received_gbp", "closing_balance_gbp"]):
                failures.append(f"Negative non-negative money field at line {line_number}")
            if money(row["credit_limit_gbp"]) <= 0:
                failures.append(f"Non-positive limit at line {line_number}")
            if dpd < 0:
                failures.append(f"Negative DPD at line {line_number}")
            if row["delinquency_status"] == "CLOSED":
                if row["account_status"] != "CLOSED" or dpd != 0 or money(row["closing_balance_gbp"]) != 0:
                    failures.append(f"Invalid CLOSED row at line {line_number}")
            elif row["delinquency_status"] != expected_bucket(dpd):
                failures.append(f"DPD bucket mismatch at line {line_number}")
            if row["account_status"] not in {"ACTIVE", "CLOSED"}:
                failures.append(f"Invalid account status at line {line_number}")
            if row["risk_segment"] not in ALLOWED_SEGMENTS:
                failures.append(f"Invalid risk segment at line {line_number}")
            elif not (LIMIT_BOUNDS[row["risk_segment"]][0] <= money(row["credit_limit_gbp"]) <= LIMIT_BOUNDS[row["risk_segment"]][1]):
                failures.append(f"Limit outside risk-segment generation range at line {line_number}")
            elif (money(row["credit_limit_gbp"]) * 100) % 5_000 != 0:
                failures.append(f"Limit is not rounded to GBP 50 at line {line_number}")
            if row["acquisition_channel"] not in ALLOWED_CHANNELS:
                failures.append(f"Invalid acquisition channel at line {line_number}")
            if row["customer_age_band"] not in ALLOWED_AGES:
                failures.append(f"Invalid age band at line {line_number}")
            if money(row["payment_received_gbp"]) > money(row["payment_due_gbp"]):
                failures.append(f"Payment exceeds due amount at line {line_number}")
            balance_rhs = (
                money(row["opening_balance_gbp"]) + money(row["purchase_amount_gbp"])
                + money(row["interest_fee_amount_gbp"]) - money(row["payment_received_gbp"])
                + money(row["other_adjustment_gbp"])
            )
            if balance_rhs != money(row["closing_balance_gbp"]):
                failures.append(f"Balance equation mismatch at line {line_number}")
            if row["account_status"] == "CLOSED" and (money(row["purchase_amount_gbp"]) != 0 or money(row["interest_fee_amount_gbp"]) != 0):
                failures.append(f"Closed row has purchases/charges at line {line_number}")
            if row["account_status"] == "CLOSED" and not (
                money(row["payment_due_gbp"]) == money(row["opening_balance_gbp"])
                and money(row["payment_received_gbp"]) == money(row["opening_balance_gbp"])
            ):
                failures.append(f"Closed row does not clear opening balance at line {line_number}")
            rows.append(row)

    keys = [(r["account_id"], r["snapshot_month"]) for r in rows]
    if len(keys) != len(set(keys)):
        failures.append("Duplicate account-month key(s)")
    by_account: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_month: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_account[row["account_id"]].append(row)
        by_month[row["snapshot_month"]].append(row)
    for account_id, history in by_account.items():
        history.sort(key=lambda r: r["snapshot_month"])
        for field in ["origination_month", "risk_segment", "acquisition_channel", "customer_age_band", "credit_limit_gbp"]:
            if len({row[field] for row in history}) != 1:
                failures.append(f"Static attribute {field} changes for {account_id}")
        closed_indices = [i for i, row in enumerate(history) if row["account_status"] == "CLOSED"]
        if len(closed_indices) > 1 or (closed_indices and closed_indices[0] != len(history) - 1):
            failures.append(f"Invalid closure lifecycle for {account_id}")
        if history[0]["snapshot_month"] != history[0]["origination_month"]:
            failures.append(f"History does not begin at origination for {account_id}")
        for prior, current in zip(history, history[1:]):
            p = date.fromisoformat(prior["snapshot_month"])
            c = date.fromisoformat(current["snapshot_month"])
            next_month_first = (p.replace(day=28) + timedelta(days=4)).replace(day=1)
            expected_next = next_month_first.replace(day=calendar.monthrange(next_month_first.year, next_month_first.month)[1])
            if c != expected_next:
                failures.append(f"Monthly gap for {account_id}: {p} to {c}")
            if money(current["opening_balance_gbp"]) != money(prior["closing_balance_gbp"]):
                failures.append(f"Balance continuity failure for {account_id} at {c}")
            if current["account_status"] != "CLOSED" and current["delinquency_status"] not in ALLOWED_TRANSITIONS.get(prior["delinquency_status"], set()):
                failures.append(f"Invalid delinquency-state transition for {account_id} at {c}")
            if prior["account_status"] == "CLOSED":
                failures.append(f"Row after closure for {account_id}")
        if money(history[0]["opening_balance_gbp"]) != 0:
            failures.append(f"Non-zero origination opening balance for {account_id}")
        if history[0]["delinquency_status"] != "CURRENT":
            failures.append(f"Non-current state at origination for {account_id}")

    monthly = {}
    originations_by_month = Counter(r["origination_month"] for r in rows if r["snapshot_month"] == r["origination_month"])
    for month, month_rows in sorted(by_month.items()):
        active = [r for r in month_rows if r["account_status"] == "ACTIVE"]
        active_balance = sum((money(r["closing_balance_gbp"]) for r in active), Decimal("0.00"))
        active_limits = sum((money(r["credit_limit_gbp"]) for r in active), Decimal("0.00"))
        monthly[month] = {
            "account_month_rows": len(month_rows),
            "active_accounts": len(active),
            "closed_rows": sum(r["account_status"] == "CLOSED" for r in month_rows),
            "originations": originations_by_month[month],
            "active_balance_gbp": f"{active_balance:.2f}",
            "active_limit_gbp": f"{active_limits:.2f}",
            "active_payment_due_gbp": f"{sum((money(r['payment_due_gbp']) for r in active), Decimal('0.00')):.2f}",
            "active_payment_received_gbp": f"{sum((money(r['payment_received_gbp']) for r in active), Decimal('0.00')):.2f}",
        }

    account_count = len(by_account)
    if account_count != 2_000:
        failures.append(f"Account count {account_count}; expected 2000")
    if not by_month or len(by_month) != 57:
        failures.append(f"Month coverage {len(by_month)}; expected 57")
    expected_months = []
    for i in range(57):
        absolute = 2022 * 12 + i
        year, month = absolute // 12, absolute % 12 + 1
        expected_months.append(f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}")
    if sorted(by_month) != expected_months:
        failures.append("Portfolio month-end coverage does not match Jan-2022 through Sep-2026")
    expected_cohorts = {month: (36 if i < 5 else 35) for i, month in enumerate(expected_months)}
    if dict(originations_by_month) != expected_cohorts:
        failures.append(f"Origination cohort counts do not match specification: {dict(originations_by_month)}")

    segment_counts = Counter(r["risk_segment"] for r in (history[0] for history in by_account.values()))
    if segment_counts != Counter({"LOWER": 1_000, "MIDDLE": 700, "HIGHER": 300}):
        failures.append(f"Risk segment quota mismatch: {segment_counts}")
    channel_counts = Counter(r["acquisition_channel"] for r in (history[0] for history in by_account.values()))
    if channel_counts != Counter({"DIRECT": 1_400, "PARTNER": 600}):
        failures.append(f"Acquisition channel quota mismatch: {channel_counts}")
    age_counts = Counter(r["customer_age_band"] for r in (history[0] for history in by_account.values()))
    if age_counts != Counter({"18-24": 240, "25-34": 560, "35-49": 600, "50-64": 440, "65+": 160}):
        failures.append(f"Age-band quota mismatch: {age_counts}")
    return {
        "rows": len(rows),
        "accounts": account_count,
        "months": len(by_month),
        "closed_accounts": sum(bool([r for r in hist if r["account_status"] == "CLOSED"]) for hist in by_account.values()),
        "failures": failures,
        "monthly": monthly,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=Path("data/synthetic_portfolio.csv"))
    parser.add_argument("--controls-output", type=Path, default=Path("data/monthly_portfolio_control_totals.csv"))
    args = parser.parse_args()
    result = validate(args.input)
    controls = result["monthly"]
    args.controls_output.parent.mkdir(parents=True, exist_ok=True)
    control_fields = ["snapshot_month", "account_month_rows", "active_accounts", "closed_rows", "originations", "active_balance_gbp", "active_limit_gbp", "active_payment_due_gbp", "active_payment_received_gbp"]
    with args.controls_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=control_fields, lineterminator="\n")
        writer.writeheader()
        for month, totals in controls.items():
            writer.writerow({"snapshot_month": month, **totals})
    print(f"Rows: {result['rows']:,}; accounts: {result['accounts']:,}; months: {result['months']}; closed accounts: {result['closed_accounts']}")
    print(f"Monthly control totals: {args.controls_output}")
    if result["failures"]:
        print("FAILURES:")
        for failure in result["failures"]:
            print(f"- {failure}")
        raise SystemExit(1)
    print("PASS: all validation checks passed")


if __name__ == "__main__":
    main()
