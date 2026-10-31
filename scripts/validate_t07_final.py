#!/usr/bin/env python3
"""Run final stage validators and check T07 documentation/evidence completeness."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/t07"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[tuple[str, bool, str]] = []
    commands = [
        [sys.executable, "scripts/validate_portfolio.py"],
        [sys.executable, "scripts/validate_review_workbook.py"],
        [sys.executable, "scripts/validate_scenarios.py"],
        [sys.executable, "scripts/validate_t05_reporting.py"],
        [sys.executable, "scripts/validate_t06_commentary.py"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        name = Path(command[-1]).name
        output = (result.stdout + result.stderr).strip().replace("\n", "; ")
        checks.append((f"Stage validator: {name}", result.returncode == 0, output or f"exit {result.returncode}"))

    required = [
        "README.md", "plan.md", "execution.md", "method.md", "checks.md", "critic.md", "update_log.md",
        "data_specification.md", "data_dictionary.md", "generation_rules.md", "data/synthetic_portfolio.csv",
        "data/monthly_portfolio_control_totals.csv", "data/boe_context_monthly.csv", "data/boe_source_register.csv",
        "data/portfolio.sqlite", "reports/credit_portfolio_review.xlsx", "reports/t02_validation.md",
        "reports/t03_validation.md", "reports/t04_validation.md", "reports/t05/dashboard_preview.html",
        "reports/t05/monthly_credit_review.md", "reports/t05/source_to_output_map.md", "reports/t05/powerbi/README.md",
        "reports/t05/powerbi/measures.dax", "reports/t06/verified_metrics.json", "reports/t06/constrained_prompt.md",
        "reports/t06/raw_ai_draft.md", "reports/t06/audit_and_corrections.md", "reports/t06/approved_commentary.md",
        "reports/t05/validation.md", "reports/t06/validation.md", "reports/t07/final_review.md", "reports/t07/resume_evidence.md",
        "latex/README.md", "latex/compile.sh", "latex/src/common.tex", "latex/src/source_code_documentation.tex",
        "latex/src/technical_report.tex", "latex/src/powerbi_implementation_guide.tex",
        "latex/pdf/Source_Code_Documentation.pdf", "latex/pdf/Technical_Project_Report.pdf", "latex/pdf/PowerBI_Implementation_Guide.pdf",
    ]
    missing = [name for name in required if not (ROOT / name).is_file()]
    checks.append(("Required artifacts exist", not missing, "all listed project artifacts exist" if not missing else "missing: " + ", ".join(missing)))

    digest = hashlib.sha256((ROOT / "data/synthetic_portfolio.csv").read_bytes()).hexdigest()
    expected = "04dce168244871a60a66c62b9f538f86050d0e224b5bb7f9b62c8e6ae10f896e"
    checks.append(("Synthetic source reproducibility hash", digest == expected, f"SHA-256 {digest}"))

    pdf_names = ["Source_Code_Documentation.pdf", "Technical_Project_Report.pdf", "PowerBI_Implementation_Guide.pdf"]
    pdf_ok = all((ROOT / "latex/pdf" / name).read_bytes().startswith(b"%PDF-") and (ROOT / "latex/pdf" / name).stat().st_size > 15_000 for name in pdf_names)
    report_tex = (ROOT / "latex/src/technical_report.tex").read_text(encoding="utf-8")
    last_section = report_tex.rsplit("\\section{", 1)[-1]
    q_and_a_last = last_section.startswith("Questions and answers}") and "\\end{document}" in last_section
    pbi_tex = (ROOT / "latex/src/powerbi_implementation_guide.tex").read_text(encoding="utf-8")
    checks.append(("Three compiled LaTeX PDFs and their source files exist", pdf_ok and q_and_a_last and all(x in pbi_tex for x in ["https://learn.microsoft.com/en-us/power-query/connectors/text-csv", "https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-date-tables"]), "PDF signatures/sizes pass; technical report ends with Q&A; Power BI guide includes current official instructions"))

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    report = (OUT / "final_review.md").read_text(encoding="utf-8")
    resume_note = (OUT / "resume_evidence.md").read_text(encoding="utf-8")
    checks.append(("README documents synthetic scope and limitations", all(x in readme for x in ["Synthetic data", "55,145", "2,000", "Bank of England", "not forecasts", "no native `.pbix`"]), "scope, size, external context, scenario limits, and Power BI packaging disclosed"))
    checks.append(("Final review discloses native Power BI handoff", "overall project acceptance is pending" in report and "native `.pbix`" in report, "final report does not claim native Power BI completion"))
    checks.append(("Resume claims are deferred until project acceptance", "Do not add project claims to a resume yet" in resume_note and "deferred" in resume_note.lower(), "no resume-ready claim is published before project acceptance"))
    native_pbix = list(ROOT.rglob("*.pbix"))
    pbi_desktop = shutil.which("PBIDesktop") or shutil.which("powerbi") or shutil.which("pbi-tools")
    checks.append(("Native Power BI availability is represented accurately", (not native_pbix and not pbi_desktop and "no native `.pbix`" in readme), f"PBIX files={len(native_pbix)}; authoring executable={'available' if pbi_desktop else 'not found'}"))

    failures = [c for c in checks if not c[1]]
    outcome = "PASS — final audit complete; project acceptance pending native Power BI" if not failures else f"FAIL — {len(failures)} final checks failed"
    lines = ["# T07 Final validation", "", f"**Date:** {date.today().isoformat()}", f"**Result:** {outcome}", "", "| Check | Result | Evidence |", "|---|---|---|"]
    lines.extend(f"| {name} | {'PASS' if ok else 'FAIL'} | {evidence.replace('|', '\\|')} |" for name, ok, evidence in checks)
    lines += ["", "The stage validators can all pass while overall project acceptance remains pending: the project plan calls for a Power BI dashboard, and this environment has neither a native PBIX nor its authoring/render tool. See `final_review.md` for the handoff requirement.", ""]
    (OUT / "validation.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(f"{'PASS' if ok else 'FAIL'} — {name}: {evidence}" for name, ok, evidence in checks))
    print(outcome)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
