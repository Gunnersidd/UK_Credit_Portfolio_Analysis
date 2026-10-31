#!/usr/bin/env python3
"""Join official BoE monthly context to the portfolio and build illustrative sensitivities."""

from __future__ import annotations

import argparse
import csv
from calendar import monthrange
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTEXT_FIELDS = [
    "month_end", "bank_rate_end_month_pct", "quoted_credit_card_rate_pct",
    "effective_rate_interest_charging_card_pct",
]
SCENARIOS = [
    {
        "scenario": "Baseline", "bank_rate_change_pp": Decimal("0.00"),
        "effective_card_rate_change_pp": Decimal("0.00"),
        "sensitivity_low_change_pp": Decimal("0.00"), "sensitivity_high_change_pp": Decimal("0.00"),
        "explanation": "Hold the September 2026 observed Bank Rate and effective credit-card rate constant for 12 months.",
    },
    {
        "scenario": "Moderate", "bank_rate_change_pp": Decimal("0.75"),
        "effective_card_rate_change_pp": Decimal("1.50"),
        "sensitivity_low_change_pp": Decimal("1.00"), "sensitivity_high_change_pp": Decimal("2.00"),
        "explanation": "Assume separate illustrative increases of 0.75pp in Bank Rate and 1.50pp in the effective card rate; no pass-through is estimated.",
    },
    {
        "scenario": "Severe", "bank_rate_change_pp": Decimal("1.50"),
        "effective_card_rate_change_pp": Decimal("3.00"),
        "sensitivity_low_change_pp": Decimal("2.00"), "sensitivity_high_change_pp": Decimal("4.00"),
        "explanation": "Assume separate illustrative increases of 1.50pp in Bank Rate and 3.00pp in the effective card rate; no pass-through is estimated.",
    },
]


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def currency(pence: str) -> Decimal:
    return Decimal(pence) / Decimal(100)


def cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def expected_month_ends() -> list[str]:
    months = []
    for index in range(57):
        absolute = 2022 * 12 + index
        year, month = absolute // 12, absolute % 12 + 1
        months.append(f"{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}")
    return months


def build(context_path: Path, monthly_path: Path, outdir: Path) -> dict[str, object]:
    context = load_rows(context_path)
    monthly = load_rows(monthly_path)
    if list(context[0]) != CONTEXT_FIELDS:
        raise ValueError(f"Unexpected context columns: {list(context[0])}")
    expected_months = expected_month_ends()
    context_months = [row["month_end"] for row in context]
    portfolio_months = [row["snapshot_month"] for row in monthly]
    if context_months != expected_months:
        raise ValueError("BoE context must contain each month end from Jan-2022 through Sep-2026 exactly once and in order")
    if portfolio_months != expected_months:
        raise ValueError("Portfolio/BoE periods do not match exactly")
    if any(any(row[field] == "" for field in CONTEXT_FIELDS[1:]) for row in context):
        raise ValueError("BoE context contains missing series values")
    if len({row["month_end"] for row in context}) != len(context):
        raise ValueError("Duplicate BoE context month")

    joined = []
    for p, b in zip(monthly, context):
        joined.append({
            "month_end": p["snapshot_month"],
            "synthetic_active_accounts": p["active_accounts"],
            "synthetic_active_balance_gbp": f"{currency(p['active_balance_pence']):.2f}",
            "synthetic_active_limits_gbp": f"{currency(p['active_limit_pence']):.2f}",
            "synthetic_utilisation": p["portfolio_utilisation"],
            "synthetic_30plus_delinquency_proxy_account_rate": p["simulated_30plus_account_rate"],
            "synthetic_30plus_delinquency_proxy_balance_rate": p["simulated_30plus_balance_rate"],
            "boe_bank_rate_end_month_pct": b["bank_rate_end_month_pct"],
            "boe_quoted_credit_card_rate_pct": b["quoted_credit_card_rate_pct"],
            "boe_effective_interest_charging_card_rate_pct": b["effective_rate_interest_charging_card_pct"],
        })

    latest_context = context[-1]
    latest_monthly = monthly[-1]
    if latest_context["month_end"] != "2026-09-30":
        raise ValueError("Scenario anchor must be the latest complete portfolio/context month, Sep-2026")
    base_balance = currency(latest_monthly["active_balance_pence"])
    observed_bank_rate = Decimal(latest_context["bank_rate_end_month_pct"])
    observed_effective_rate = Decimal(latest_context["effective_rate_interest_charging_card_pct"])
    observed_quoted_rate = Decimal(latest_context["quoted_credit_card_rate_pct"])
    base_annual_cost = cents(base_balance * observed_effective_rate / Decimal(100))

    assumptions = []
    results = []
    sensitivities = []
    for scenario in SCENARIOS:
        central_bank_rate = observed_bank_rate + scenario["bank_rate_change_pp"]
        central_card_rate = observed_effective_rate + scenario["effective_card_rate_change_pp"]
        assumptions.append({
            "scenario": scenario["scenario"],
            "horizon_months": 12,
            "observed_anchor_month": latest_context["month_end"],
            "observed_bank_rate_pct": f"{observed_bank_rate:.2f}",
            "assumed_bank_rate_change_pp": f"{scenario['bank_rate_change_pp']:.2f}",
            "scenario_bank_rate_pct": f"{central_bank_rate:.2f}",
            "observed_effective_card_rate_pct": f"{observed_effective_rate:.2f}",
            "observed_quoted_card_rate_pct": f"{observed_quoted_rate:.2f}",
            "assumed_effective_card_rate_change_pp": f"{scenario['effective_card_rate_change_pp']:.2f}",
            "scenario_effective_card_rate_pct": f"{central_card_rate:.2f}",
            "interpretation": scenario["explanation"] + " A static portfolio balance is used; this is not a forecast or fitted causal estimate.",
        })
        central_cost = cents(base_balance * central_card_rate / Decimal(100))
        results.append({
            "scenario": scenario["scenario"],
            "anchor_month": latest_context["month_end"],
            "active_balance_gbp": f"{base_balance:.2f}",
            "scenario_bank_rate_pct": f"{central_bank_rate:.2f}",
            "scenario_effective_card_rate_pct": f"{central_card_rate:.2f}",
            "annualized_interest_cost_proxy_gbp": f"{cents(central_cost):.2f}",
            "change_vs_baseline_gbp": f"{cents(central_cost - base_annual_cost):.2f}",
            "balance_assumption": "Sep-2026 synthetic active closing balance held constant; all of it assumed interest-bearing and repriced immediately.",
        })

        low_delta = scenario["sensitivity_low_change_pp"]
        high_delta = scenario["sensitivity_high_change_pp"]
        delta_levels = sorted({low_delta, scenario["effective_card_rate_change_pp"], high_delta})
        balance_factors = [Decimal("0.90"), Decimal("1.00"), Decimal("1.10")]
        for delta in delta_levels:
            for factor in balance_factors:
                sensitivity_balance = cents(base_balance * factor)
                sensitivity_rate = observed_effective_rate + delta
                cost = cents(sensitivity_balance * sensitivity_rate / Decimal(100))
                baseline_at_factor = cents(sensitivity_balance * observed_effective_rate / Decimal(100))
                sensitivities.append({
                    "scenario": scenario["scenario"],
                    "effective_card_rate_change_pp": f"{delta:.2f}",
                    "scenario_effective_card_rate_pct": f"{sensitivity_rate:.2f}",
                    "balance_factor": f"{factor:.2f}",
                    "modeled_balance_gbp": f"{sensitivity_balance:.2f}",
                    "annualized_interest_cost_proxy_gbp": f"{cost:.2f}",
                    "change_vs_same_balance_baseline_gbp": f"{cents(cost - baseline_at_factor):.2f}",
                })

    write_csv(outdir / "portfolio_context_joined.csv", list(joined[0]), joined)
    assumption_fields = list(assumptions[0])
    result_fields = list(results[0])
    sensitivity_fields = list(sensitivities[0])
    write_csv(outdir / "scenario_assumptions.csv", assumption_fields, assumptions)
    write_csv(outdir / "scenario_results.csv", result_fields, results)
    write_csv(outdir / "scenario_sensitivity.csv", sensitivity_fields, sensitivities)
    return {
        "joined_rows": len(joined), "anchor_month": latest_context["month_end"],
        "active_balance_gbp": f"{base_balance:.2f}", "observed_bank_rate_pct": f"{observed_bank_rate:.2f}",
        "observed_quoted_card_rate_pct": f"{observed_quoted_rate:.2f}",
        "observed_effective_card_rate_pct": f"{observed_effective_rate:.2f}",
        "scenario_rows": len(results), "sensitivity_rows": len(sensitivities),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, default=ROOT / "data/boe_context_monthly.csv")
    parser.add_argument("--monthly-sql", type=Path, default=ROOT / "reports/t03/sql/monthly_portfolio.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/t04")
    args = parser.parse_args()
    print(build(args.context, args.monthly_sql, args.output_dir))


if __name__ == "__main__":
    main()
