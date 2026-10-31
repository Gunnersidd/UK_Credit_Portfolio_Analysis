#!/usr/bin/env python3
"""Validate T04 source coverage, exact month join, and scenario arithmetic."""

from __future__ import annotations

import argparse
import csv
from calendar import monthrange
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def months() -> list[str]:
    output = []
    for index in range(57):
        absolute = 2022 * 12 + index
        year, month = absolute // 12, absolute % 12 + 1
        output.append(f"{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}")
    return output


def money(value: str) -> Decimal:
    return Decimal(value)


def validate(root: Path) -> list[str]:
    failures = []
    context = read_rows(root / "data/boe_context_monthly.csv")
    source_register = read_rows(root / "data/boe_source_register.csv")
    portfolio = read_rows(root / "reports/t03/sql/monthly_portfolio.csv")
    joined = read_rows(root / "reports/t04/portfolio_context_joined.csv")
    assumptions = read_rows(root / "reports/t04/scenario_assumptions.csv")
    results = read_rows(root / "reports/t04/scenario_results.csv")
    sensitivity = read_rows(root / "reports/t04/scenario_sensitivity.csv")
    expected_months = months()

    if [row["month_end"] for row in context] != expected_months:
        failures.append("BoE context does not contain the exact 57 month ends from 2022-01 through 2026-09")
    if [row["snapshot_month"] for row in portfolio] != expected_months:
        failures.append("T03 monthly portfolio periods differ from the T04 expected month ends")
    if [row["month_end"] for row in joined] != expected_months:
        failures.append("Joined context has missing, duplicate, or misordered months")
    required_codes = {"IUMBEDR", "IUMCCTL", "CFMZ6IR"}
    if {row["series_code"] for row in source_register} != required_codes:
        failures.append("Source register series codes do not match the three selected indicators")
    if any(not row["source_url"].startswith("https://www.bankofengland.co.uk/") for row in source_register):
        failures.append("A series source URL is missing or is not an official Bank of England URL")
    if any(any(row[field] == "" for field in ["bank_rate_end_month_pct", "quoted_credit_card_rate_pct", "effective_rate_interest_charging_card_pct"]) for row in context):
        failures.append("BoE context contains missing series observations")

    context_by_month = {row["month_end"]: row for row in context}
    for port_row, join_row in zip(portfolio, joined):
        month = port_row["snapshot_month"]
        source_row = context_by_month.get(month)
        if source_row is None:
            failures.append(f"Missing BoE row for {month}")
            continue
        if join_row["boe_bank_rate_end_month_pct"] != source_row["bank_rate_end_month_pct"]:
            failures.append(f"Bank Rate join mismatch for {month}")
        if join_row["boe_quoted_credit_card_rate_pct"] != source_row["quoted_credit_card_rate_pct"]:
            failures.append(f"Quoted card-rate join mismatch for {month}")
        if join_row["boe_effective_interest_charging_card_rate_pct"] != source_row["effective_rate_interest_charging_card_pct"]:
            failures.append(f"Effective card-rate join mismatch for {month}")
        if join_row["synthetic_active_accounts"] != port_row["active_accounts"]:
            failures.append(f"Active-account join mismatch for {month}")
        expected_balance = f"{Decimal(port_row['active_balance_pence']) / 100:.2f}"
        if join_row["synthetic_active_balance_gbp"] != expected_balance:
            failures.append(f"Active-balance join mismatch for {month}")

    latest = context[-1]
    if latest["month_end"] != "2026-09-30" or latest["bank_rate_end_month_pct"] != "3.75" or latest["quoted_credit_card_rate_pct"] != "24.71" or latest["effective_rate_interest_charging_card_pct"] != "21.71":
        failures.append("Latest official anchor values do not match September 2026 source records")
    if len(results) != 3 or {row["scenario"] for row in results} != {"Baseline", "Moderate", "Severe"}:
        failures.append("Scenario output must contain Baseline, Moderate, and Severe once each")
    base = next((row for row in results if row["scenario"] == "Baseline"), None)
    if base is None:
        return failures + ["No baseline scenario row"]
    baseline_cost = money(base["annualized_interest_cost_proxy_gbp"])
    for row in results:
        balance = money(row["active_balance_gbp"])
        rate = money(row["scenario_effective_card_rate_pct"])
        expected_cost = (balance * rate / 100).quantize(Decimal("0.01"))
        if money(row["annualized_interest_cost_proxy_gbp"]) != expected_cost:
            failures.append(f"Scenario annualized-cost formula mismatch for {row['scenario']}")
        expected_delta = (expected_cost - baseline_cost).quantize(Decimal("0.01"))
        if money(row["change_vs_baseline_gbp"]) != expected_delta:
            failures.append(f"Scenario baseline delta mismatch for {row['scenario']}")
        if row["anchor_month"] != "2026-09-30":
            failures.append(f"Unexpected scenario anchor for {row['scenario']}")
    expected_sensitivity_count = 21
    if len(sensitivity) != expected_sensitivity_count:
        failures.append(f"Expected {expected_sensitivity_count} sensitivity rows, got {len(sensitivity)}")
    for row in sensitivity:
        balance = money(row["modeled_balance_gbp"])
        rate = money(row["scenario_effective_card_rate_pct"])
        cost = (balance * rate / 100).quantize(Decimal("0.01"))
        if money(row["annualized_interest_cost_proxy_gbp"]) != cost:
            failures.append(f"Sensitivity cost formula mismatch for {row['scenario']} {row['balance_factor']} {row['effective_card_rate_change_pp']}")
        expected_delta = (cost - (balance * Decimal("21.71") / 100).quantize(Decimal("0.01"))).quantize(Decimal("0.01"))
        if money(row["change_vs_same_balance_baseline_gbp"]) != expected_delta:
            failures.append(f"Sensitivity baseline delta mismatch for {row['scenario']} {row['balance_factor']} {row['effective_card_rate_change_pp']}")
    if len(assumptions) != 3:
        failures.append("Scenario assumption register does not contain three cases")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    failures = validate(args.root)
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)
    print("PASS: 57-month source coverage, exact joins, latest observations, and scenario/sensitivity arithmetic")


if __name__ == "__main__":
    main()
