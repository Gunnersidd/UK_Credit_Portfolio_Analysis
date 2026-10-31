#!/usr/bin/env python3
"""Reconcile T05 reporting artifacts to accepted T03/T04 source tables."""
from __future__ import annotations

import csv
from datetime import date
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/t05"


def rows(rel: str) -> list[dict[str, str]]:
    with (ROOT / rel).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def close(a: float, b: float, eps: float = 1e-10) -> bool:
    return abs(a - b) <= eps


class StructureParser(HTMLParser):
    pass


def main() -> None:
    checks: list[tuple[str, bool, str]] = []
    monthly = rows("reports/t03/sql/monthly_portfolio.csv")
    segment = rows("reports/t03/sql/risk_segment.csv")
    delinquency = rows("reports/t03/sql/delinquency_state.csv")
    scenarios = rows("reports/t04/scenario_results.csv")
    context = rows("reports/t04/portfolio_context_joined.csv")
    html = (OUT / "dashboard_preview.html").read_text(encoding="utf-8")
    memo = (OUT / "monthly_credit_review.md").read_text(encoding="utf-8")
    mapping = (OUT / "source_to_output_map.md").read_text(encoding="utf-8")

    match = re.search(r"const D=(.*?);\nconst n=", html, re.S)
    embedded = json.loads(match.group(1)) if match else {}
    parser = StructureParser()
    parser.feed(html)
    parser.close()

    checks.append(("Dashboard HTML parses and embeds JSON data", bool(match) and len(embedded.get("monthly", [])) == len(monthly), f"embedded monthly rows={len(embedded.get('monthly', []))}"))
    checks.append(("Dashboard contains all controlled source rows", all(len(embedded.get(k, [])) == len(src) for k, src in [("monthly", monthly), ("segment", segment), ("delinquency", delinquency), ("scenarios", scenarios), ("context", context)]), "monthly/risk/delinquency/context/scenario row counts compared to T03/T04"))

    latest = monthly[-1]
    latest_date = latest["snapshot_month"]
    c = next(x for x in context if x["month_end"] == latest_date)
    ds = [x for x in delinquency if x["snapshot_month"] == latest_date]
    seg = [x for x in segment if x["snapshot_month"] == latest_date]
    checks.append(("Latest month joins exactly across T03 and T04", latest_date == "2026-09-30" and len(ds) == 5 and len(seg) == 3 and c["month_end"] == latest_date, f"month={latest_date}, status rows={len(ds)}, segment rows={len(seg)}"))
    checks.append(("30+ proxy count reconciles to delinquency-state buckets", int(latest["simulated_30plus_accounts"]) == sum(int(x["active_accounts"]) for x in ds if x["delinquency_status"] in {"30_59", "60_89", "90_PLUS"}), f"monthly count={latest['simulated_30plus_accounts']}"))
    checks.append(("30+ proxy account rate reconciles to numerator/denominator", close(float(latest["simulated_30plus_account_rate"]), int(latest["simulated_30plus_accounts"]) / int(latest["active_accounts"])), "SQL rate equals simulated 30+ accounts / active accounts"))
    checks.append(("30+ proxy balance rate reconciles to numerator/denominator", close(float(latest["simulated_30plus_balance_rate"]), int(latest["simulated_30plus_balance_pence"]) / int(latest["active_balance_pence"])), "SQL rate equals simulated 30+ balance / active balance"))
    checks.append(("UK context fields map to selected month", c["boe_bank_rate_end_month_pct"] == "3.75" and c["boe_effective_interest_charging_card_rate_pct"] == "21.71", f"Bank Rate={c['boe_bank_rate_end_month_pct']}%, effective card rate={c['boe_effective_interest_charging_card_rate_pct']}%"))
    by_scenario = {x["scenario"]: x for x in scenarios}
    checks.append(("Scenario output controls match T04 source", set(by_scenario) == {"Baseline", "Moderate", "Severe"} and close(float(by_scenario["Baseline"]["annualized_interest_cost_proxy_gbp"]), 541259.06) and close(float(by_scenario["Moderate"]["annualized_interest_cost_proxy_gbp"]), 578656.05) and close(float(by_scenario["Severe"]["annualized_interest_cost_proxy_gbp"]), 616053.04), "three scenario values compared to accepted T04 CSV"))
    checks.append(("Memo carries September controls and synthetic limitations", all(s in memo for s in ["£2.493m", "1,833", "30.29%", "2.60%", "£5.1k to £64.9k", "synthetic", "not actual arrears"]) and "£51.3k" not in memo, "key headline figures, corrected £5.1k proxy-balance movement, and limitation language present"))
    checks.append(("Lineage map covers dashboard sources and control values", all(s in mapping for s in ["monthly_portfolio.csv", "risk_segment.csv", "delinquency_state.csv", "portfolio_context_joined.csv", "scenario_results.csv", "£2,493,132", "£541,259"]), "all major output/source mappings and anchor controls present"))
    checks.append(("Power BI DAX package has denominator-based rates", "DIVIDE(SUM(Monthly[simulated_30plus_accounts]), SUM(Monthly[active_accounts]))" in (OUT / "powerbi/measures.dax").read_text(encoding="utf-8"), "ratio measure uses summed numerator and denominator"))
    node = shutil.which("node")
    if node:
        run = subprocess.run([node, str(ROOT / "scripts/validate_t05_dashboard.js"), str(OUT / "dashboard_preview.html")], capture_output=True, text=True)
        checks.append(("Dashboard JavaScript smoke render", run.returncode == 0, (run.stdout + run.stderr).strip()))
    else:
        checks.append(("Dashboard JavaScript smoke render", False, "Node.js is required to run scripts/validate_t05_dashboard.js"))

    failures = [c for c in checks if not c[1]]
    report = ["# T05 reporting validation", "", f"**Date:** {date.today().isoformat()}", "**Result:** " + ("PASS" if not failures else f"FAIL ({len(failures)} failed checks)"), "", "| Check | Result | Evidence |", "|---|---|---|"]
    report.extend(f"| {name} | {'PASS' if ok else 'FAIL'} | {evidence} |" for name, ok, evidence in checks)
    report += ["", "## Scope note", "", "This validation checks data embedding, source joins, key controls, document labels, and DAX ratio construction. It does not render the page in Power BI Desktop or certify a native PBIX; no Power BI authoring tool is installed in this environment.", ""]
    (OUT / "validation.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(f"{'PASS' if ok else 'FAIL'} — {name}: {evidence}" for name, ok, evidence in checks))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
