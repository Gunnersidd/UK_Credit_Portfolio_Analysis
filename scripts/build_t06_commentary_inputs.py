#!/usr/bin/env python3
"""Prepare a structured, pre-calculated metric table for T06 commentary audit."""
from __future__ import annotations

import csv
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/t06"


def load(name: str) -> list[dict[str, str]]:
    with (ROOT / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def dec(value: str | int) -> Decimal:
    return Decimal(str(value))


def money_pence(pence: str | int) -> str:
    return f"{(dec(pence) / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def pct_from_ratio(value: str | Decimal) -> str:
    return f"{(dec(value) * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def pct_precise(value: str | Decimal) -> str:
    return f"{(dec(value) * 100).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP):.4f}"


def pp(new: str, old: str) -> str:
    return f"{(dec(new) - dec(old)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):+.2f}"


def pp_from_ratios(new: str, old: str) -> str:
    value = ((dec(new) - dec(old)) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{value:+.2f}"


def change(new: str, old: str) -> str:
    return f"{(dec(new) - dec(old)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):+.2f}"


def record(metric: str, period: str, value: str, unit: str, source: str,
           definition: str, compare_period: str = "", compare_value: str = "",
           change_value: str = "", change_unit: str = "", display_value: str = "",
           compare_display_value: str = "") -> dict[str, str]:
    return {"metric": metric, "period": period, "value": value,
            "display_value": display_value or value, "unit": unit,
            "comparison_period": compare_period, "comparison_value": compare_value,
            "comparison_display_value": compare_display_value or compare_value,
            "change": change_value, "change_unit": change_unit,
            "definition": definition, "source": source}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    monthly = {r["snapshot_month"]: r for r in load("reports/t03/sql/monthly_portfolio.csv")}
    segments = load("reports/t03/sql/risk_segment.csv")
    states = load("reports/t03/sql/delinquency_state.csv")
    context = {r["month_end"]: r for r in load("reports/t04/portfolio_context_joined.csv")}
    scenarios = load("reports/t04/scenario_results.csv")
    now, prev = monthly["2026-09-30"], monthly["2026-08-31"]
    records: list[dict[str, str]] = []

    def money_metric(metric: str, field: str, definition: str) -> None:
        a, b = money_pence(now[field]), money_pence(prev[field])
        records.append(record(metric, "2026-09-30", a, "GBP", "reports/t03/sql/monthly_portfolio.csv",
                              definition, "2026-08-31", b, change(a, b), "GBP"))

    def count_metric(metric: str, field: str, definition: str) -> None:
        a, b = int(now[field]), int(prev[field])
        records.append(record(metric, "2026-09-30", str(a), "accounts", "reports/t03/sql/monthly_portfolio.csv",
                              definition, "2026-08-31", str(b), f"{a-b:+d}", "accounts"))

    def rate_metric(metric: str, field: str, definition: str) -> None:
        a, b = pct_from_ratio(now[field]), pct_from_ratio(prev[field])
        records.append(record(metric, "2026-09-30", pct_precise(now[field]), "percent", "reports/t03/sql/monthly_portfolio.csv",
                              definition, "2026-08-31", pct_precise(prev[field]), pp_from_ratios(now[field], prev[field]), "percentage points", a, b))

    money_metric("active_closing_balance", "active_balance_pence", "Sum of active-account closing balances; GBP converted from SQL pence.")
    count_metric("active_accounts", "active_accounts", "Count of active accounts at month end.")
    rate_metric("portfolio_utilisation", "portfolio_utilisation", "Active closing balance divided by active credit limits.")
    rate_metric("active_payment_rate", "payment_rate", "Active payment received divided by active payment due; closure receipts excluded.")
    count_metric("simulated_30plus_account_count", "simulated_30plus_accounts", "Count of active accounts in generated 30+ proxy states.")
    rate_metric("simulated_30plus_account_proxy_rate", "simulated_30plus_account_rate", "Generated 30+ proxy accounts divided by active accounts; not contractual arrears/default.")
    rate_metric("simulated_30plus_balance_proxy_rate", "simulated_30plus_balance_rate", "Generated 30+ proxy balance divided by active balance; not arrears/loss.")
    money_metric("simulated_30plus_proxy_balance", "simulated_30plus_balance_pence", "Balance in generated 30+ proxy states; GBP converted from SQL pence.")

    for seg_name in ["HIGHER", "MIDDLE", "LOWER"]:
        a = next(r for r in segments if r["snapshot_month"] == "2026-09-30" and r["risk_segment"] == seg_name)
        b = next(r for r in segments if r["snapshot_month"] == "2026-08-31" and r["risk_segment"] == seg_name)
        av, bv = pct_from_ratio(a["simulated_30plus_account_rate"]), pct_from_ratio(b["simulated_30plus_account_rate"])
        records.append(record(f"{seg_name.lower()}_segment_active_accounts", "2026-09-30", a["active_accounts"], "accounts",
                              "reports/t03/sql/risk_segment.csv", "Active accounts in the generator-defined segment."))
        records.append(record(f"{seg_name.lower()}_segment_30plus_account_proxy_rate", "2026-09-30", pct_precise(a["simulated_30plus_account_rate"]), "percent",
                              "reports/t03/sql/risk_segment.csv", "Generated 30+ proxy account rate within the generator-defined segment; not a real score band.",
                              "2026-08-31", pct_precise(b["simulated_30plus_account_rate"]), pp_from_ratios(a["simulated_30plus_account_rate"], b["simulated_30plus_account_rate"]), "percentage points", av, bv))

    for state in ["CURRENT", "1_29", "30_59", "60_89", "90_PLUS"]:
        row = next(r for r in states if r["snapshot_month"] == "2026-09-30" and r["delinquency_status"] == state)
        records.append(record(f"status_proxy_{state.lower()}_accounts", "2026-09-30", row["active_accounts"], "accounts",
                              "reports/t03/sql/delinquency_state.csv", "Count of active accounts in this generated status proxy bucket."))

    c = context["2026-09-30"]
    for metric, field, definition in [
        ("boe_bank_rate_end_month", "boe_bank_rate_end_month_pct", "Official UK Bank Rate at month end; external market context."),
        ("boe_quoted_card_rate", "boe_quoted_credit_card_rate_pct", "Representative UK quoted card lending rate; external market context."),
        ("boe_effective_interest_charging_card_rate", "boe_effective_interest_charging_card_rate_pct", "Effective rate on interest-charging UK credit-card balances; external market context."),
    ]:
        records.append(record(metric, "2026-09-30", c[field], "percent", "reports/t04/portfolio_context_joined.csv", definition))

    for row in scenarios:
        scenario_key = row["scenario"].lower()
        baseline_cost = next(x["annualized_interest_cost_proxy_gbp"] for x in scenarios if x["scenario"] == "Baseline")
        comparison_period = "" if scenario_key == "baseline" else "Baseline scenario"
        comparison_cost = "" if scenario_key == "baseline" else baseline_cost
        records.append(record(f"{scenario_key}_annualized_interest_cost_proxy", row["anchor_month"],
                              row["annualized_interest_cost_proxy_gbp"], "GBP", "reports/t04/scenario_results.csv",
                              "Static 12-month annualized mechanical proxy: full synthetic active balance held constant, all assumed interest-bearing and immediately repriced; not forecast/portfolio income/customer cost.",
                              comparison_period, comparison_cost, row["change_vs_baseline_gbp"], "GBP vs baseline"))
        records.append(record(f"{scenario_key}_effective_card_rate", row["anchor_month"],
                              row["scenario_effective_card_rate_pct"], "percent", "reports/t04/scenario_results.csv",
                              "Assumed effective card rate used in the corresponding 12-month illustrative scenario."))

    output = {
        "as_of_date": "2026-10-30",
        "portfolio_label": "Synthetic UK consumer credit card portfolio; illustrative, no actual lender/customer outcomes.",
        "permitted_comparisons": ["September 2026 vs August 2026", "September 2026 segment cross-section", "September 2026 T04 scenario comparison only"],
        "metrics": records,
    }
    (OUT / "verified_metrics.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT / 'verified_metrics.json'} ({len(records)} pre-calculated metrics)")


if __name__ == "__main__":
    main()
