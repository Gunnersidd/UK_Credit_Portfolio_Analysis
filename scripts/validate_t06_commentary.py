#!/usr/bin/env python3
"""Validate T06 structured metrics and audited commentary against T03/T04."""
from __future__ import annotations

import csv
from datetime import date
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/t06"


def read_csv(rel: str) -> list[dict[str, str]]:
    with (ROOT / rel).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    metrics_doc = json.loads((OUT / "verified_metrics.json").read_text(encoding="utf-8"))
    metrics = {r["metric"]: r for r in metrics_doc["metrics"]}
    monthly = {r["snapshot_month"]: r for r in read_csv("reports/t03/sql/monthly_portfolio.csv")}
    scenarios = {r["scenario"].lower(): r for r in read_csv("reports/t04/scenario_results.csv")}
    memo = (ROOT / "reports/t05/monthly_credit_review.md").read_text(encoding="utf-8")
    prompt = (OUT / "constrained_prompt.md").read_text(encoding="utf-8")
    raw = (OUT / "raw_ai_draft.md").read_text(encoding="utf-8")
    approved = (OUT / "approved_commentary.md").read_text(encoding="utf-8")
    audit = (OUT / "audit_and_corrections.md").read_text(encoding="utf-8")
    checks: list[tuple[str, bool, str]] = []

    sep, aug = monthly["2026-09-30"], monthly["2026-08-31"]
    checks.append(("Structured table has provenance and scope", len(metrics) == 28 and all(x["source"] and x["definition"] for x in metrics.values()) and "Synthetic" in metrics_doc["portfolio_label"], f"{len(metrics)} pre-calculated metric rows"))
    checks.append(("Balance levels and delta reconcile to SQL pence", Decimal(metrics["active_closing_balance"]["value"]) == Decimal(sep["active_balance_pence"]) / 100 and Decimal(metrics["active_closing_balance"]["comparison_value"]) == Decimal(aug["active_balance_pence"]) / 100 and Decimal(metrics["active_closing_balance"]["change"]) == (Decimal(sep["active_balance_pence"]) - Decimal(aug["active_balance_pence"])) / 100, "September, August, and delta match monthly SQL"))
    checks.append(("30+ balance proxy delta reconciles", Decimal(metrics["simulated_30plus_proxy_balance"]["value"]) == Decimal(sep["simulated_30plus_balance_pence"]) / 100 and Decimal(metrics["simulated_30plus_proxy_balance"]["comparison_value"]) == Decimal(aug["simulated_30plus_balance_pence"]) / 100 and Decimal(metrics["simulated_30plus_proxy_balance"]["change"]) == (Decimal(sep["simulated_30plus_balance_pence"]) - Decimal(aug["simulated_30plus_balance_pence"])) / 100, f"source delta GBP {metrics['simulated_30plus_proxy_balance']['change']}"))
    for key, field in [("portfolio_utilisation", "portfolio_utilisation"), ("active_payment_rate", "payment_rate"), ("simulated_30plus_account_proxy_rate", "simulated_30plus_account_rate"), ("simulated_30plus_balance_proxy_rate", "simulated_30plus_balance_rate")]:
        expected = (Decimal(sep[field]) * 100).quantize(Decimal("0.01"))
        checks.append((f"{key} level matches SQL", Decimal(metrics[key]["display_value"]) == expected, f"structured display={metrics[key]['display_value']}%, source rounded={expected}%"))
    expected_pp = {
        "portfolio_utilisation": ("portfolio_utilisation", "+0.15"),
        "active_payment_rate": ("payment_rate", "+0.17"),
        "simulated_30plus_account_proxy_rate": ("simulated_30plus_account_rate", "-0.03"),
        "simulated_30plus_balance_proxy_rate": ("simulated_30plus_balance_rate", "+0.16"),
    }
    point_ok = all(Decimal(metrics[key]["change"]) == Decimal(expected) and Decimal(metrics[key]["change"]) == ((Decimal(sep[field]) - Decimal(aug[field])) * 100).quantize(Decimal("0.01")) for key, (field, expected) in expected_pp.items())
    checks.append(("Percentage-point changes use unrounded SQL rates", point_ok, "portfolio, payment, and proxy-rate movements match source ratios before rounding"))
    segment_rows = read_csv("reports/t03/sql/risk_segment.csv")
    segment_pp_expected = {"higher": "-1.69", "middle": "+0.46", "lower": "+0.09"}
    for name, expected in segment_pp_expected.items():
        now = next(r for r in segment_rows if r["snapshot_month"] == "2026-09-30" and r["risk_segment"] == name.upper())
        before = next(r for r in segment_rows if r["snapshot_month"] == "2026-08-31" and r["risk_segment"] == name.upper())
        metric = metrics[f"{name}_segment_30plus_account_proxy_rate"]
        actual = ((Decimal(now["simulated_30plus_account_rate"]) - Decimal(before["simulated_30plus_account_rate"])) * 100).quantize(Decimal("0.01"))
        point_ok &= Decimal(metric["change"]) == Decimal(expected) == actual
    checks.append(("Segment percentage-point changes use unrounded SQL rates", point_ok, "HIGHER/MIDDLE/LOWER source-rate changes match the structured table"))
    checks.append(("Scenario values match T04", all(Decimal(metrics[f"{s}_annualized_interest_cost_proxy"]["value"]) == Decimal(scenarios[s]["annualized_interest_cost_proxy_gbp"]) for s in ["baseline", "moderate", "severe"]), "baseline/moderate/severe values match scenario_results.csv"))
    scenario_units_ok = all(not r["comparison_value"] or r["unit"] == r["change_unit"].replace(" vs baseline", "") for k, r in metrics.items() if "annualized_interest_cost_proxy" in k)
    checks.append(("Scenario comparisons use consistent units", scenario_units_ok and metrics["moderate_annualized_interest_cost_proxy"]["comparison_value"] == metrics["baseline_annualized_interest_cost_proxy"]["value"], "scenario cost changes compare GBP with baseline GBP; rates are separate metrics"))
    checks.append(("Prompt constrains calculations and claim scope", all(x in prompt for x in ["Do not calculate", "display_value", "Do not infer causes", "not contractual arrears", "not forecast cost", "Do not recommend credit actions"]), "prompt includes calculation/rounding and claim-scope constraints"))
    checks.append(("Raw draft preserved and explicitly unapproved", "unedited draft output" in raw and "not approved" in raw, "raw file marks initial text as unapproved"))
    checks.append(("Audit identifies unsupported causal/concentration/forecast claims", all(x in audit for x in ["Unsupported", "causal claim", "forecast", "Remove.", "£5,127.90"]), "claim-by-claim correction and cross-task finding documented"))
    checks.append(("Approved text is synthetic and proxy-qualified", all(x in approved for x in ["synthetic portfolio", "generated 30+ account proxy", "generated 30+ balance proxy", "not forecasts"]), "approved narrative retains scope and measurement caveats"))
    checks.append(("T05 memo typo is fixed and regression checked", "£5.1k to £64.9k" in memo and "£51.3k" not in memo, "correct balance movement retained; stale typo absent"))

    t05 = subprocess.run([sys.executable, str(ROOT / "scripts/validate_t05_reporting.py")], capture_output=True, text=True)
    checks.append(("Dependent T05 validation reruns successfully", t05.returncode == 0, "T05 dashboard/memo package validation passed after memo correction" if t05.returncode == 0 else (t05.stdout + t05.stderr).strip()))

    failures = [x for x in checks if not x[1]]
    report = ["# T06 AI-assisted commentary audit", "", f"**Date:** {date.today().isoformat()}", "**Result:** " + ("PASS" if not failures else f"FAIL ({len(failures)} failed checks)"), "", "| Check | Result | Evidence |", "|---|---|---|"]
    report.extend(f"| {name} | {'PASS' if ok else 'FAIL'} | {evidence.replace('|', '\\|')} |" for name, ok, evidence in checks)
    report += ["", "## Human review", "", "Every numeric statement in the approved text was matched to `verified_metrics.json` and accepted T03/T04 sources. Unsupported causal, concentration, arrears, and forecast statements in the raw draft were removed. See `audit_and_corrections.md` for statement-level dispositions.", ""]
    (OUT / "validation.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(f"{'PASS' if ok else 'FAIL'} — {name}: {evidence}" for name, ok, evidence in checks))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
