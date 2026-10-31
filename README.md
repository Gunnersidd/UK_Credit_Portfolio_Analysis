# UK Credit Portfolio Performance and Stress Analysis

A reproducible portfolio-monitoring project for credit and portfolio analyst practice. It builds a synthetic UK credit-card portfolio, checks monthly measures in SQL and Excel, joins official Bank of England context, and documents illustrative rate sensitivities.

> **Synthetic data:** all account records, balances, payment behavior, segments, and delinquency states are generated for this project. No customer, lender, or account is real. Results are not estimates of UK lender performance, customer outcomes, credit losses, or macroeconomic effects.

## Dataset used

The portfolio dataset is generated in this repository with Python's standard library using fixed seed `20261030`. It contains **55,145 account-month snapshots**, **2,000 synthetic accounts**, and **57 month-end periods from January 2022 through September 2026**. The SHA-256 of the accepted CSV is recorded in `reports/t02_validation.md`.

The only external context is three monthly Bank of England series, stored separately from the synthetic account data: end-month Bank Rate (`IUMBEDR`), representative quoted credit-card lending rate (`IUMCCTL`), and the effective rate on interest-charging card balances (`CFMZ6IR`). Their metadata, access date, coverage, source URLs, and the September 2026 Bank Rate treatment are in `data/boe_source_register.csv`. The values were checked on 30 October 2026. The BoE series describe UK market populations and are not portfolio-specific.

## Main outputs

- Data contract and definitions: `data_specification.md`, `data_dictionary.md`, `generation_rules.md`
- Synthetic source and monthly controls: `data/synthetic_portfolio.csv`, `data/monthly_portfolio_control_totals.csv`
- Repeatable SQL and Excel: `sql/`, `reports/t03/sql/`, `reports/credit_portfolio_review.xlsx`
- BoE context and sensitivities: `data/boe_context_monthly.csv`, `reports/t04/`
- Monthly review: `reports/t05/monthly_credit_review.md`
- Interactive dashboard preview: `reports/t05/dashboard_preview.html`
- Power BI handoff package: `reports/t05/powerbi/README.md`, `reports/t05/powerbi/measures.dax`
- Audited AI-assisted commentary: `reports/t06/approved_commentary.md`; its prompt, input metrics, raw draft, and corrections are in `reports/t06/`
- Final project review and evidence: `reports/t07/final_review.md`, `reports/t07/resume_evidence.md`
- LaTeX documents and compiled PDFs: `latex/README.md`, including source-code documentation, the technical report with end-of-report Q&A, and the Power BI implementation guide

## Reproduce the analytical outputs

Run commands from the project root. Python scripts use the standard library. Node.js is needed only for the dashboard JavaScript smoke check.

```sh
python3 scripts/generate_portfolio.py
python3 scripts/validate_portfolio.py
python3 scripts/run_sql_analysis.py
python3 scripts/build_review_workbook.py
python3 scripts/validate_review_workbook.py
python3 scripts/build_scenarios.py
python3 scripts/validate_scenarios.py
python3 scripts/build_t05_reporting.py
python3 scripts/validate_t05_reporting.py
python3 scripts/build_t06_commentary_inputs.py
python3 scripts/validate_t06_commentary.py
python3 scripts/validate_t07_final.py
```

The generator's observation window is frozen through September 2026. Do not extend the data window automatically. The T04 Bank of England source values are retained for reproducibility; refreshing external series requires reviewing their official metadata and updating the source register and scenario validations.

## Key definitions and limits

- Portfolio utilisation is active closing balance divided by active limits.
- Payment rate is active-account payments received divided by active-account amount due; final closure receipts are separate.
- Delinquency and 30+ measures are generated state proxies. The generator has no bill-due ledger, so these are not actual contractual arrears, default, or NPL measures.
- Closing balance is a portfolio balance proxy, not EAD or expected loss. Synthetic segment labels are not real score bands.
- T04 sensitivities hold the September 2026 synthetic balance static, assume every pound is interest-bearing and immediately repriced, and apply independent Bank Rate/card-rate shocks. They are not forecasts, actual lender income, customer costs, delinquency changes, or loss estimates.
- The dashboard uses the validated T03/T04 export tables. Power BI Desktop was unavailable during this build: the repository contains an interactive HTML preview and Power BI-ready sources, DAX, model relationships, and page instructions, but no native `.pbix`. Import and render in Power BI Desktop before describing it as a native Power BI report.

## Quality and project status

The execution, critic, and update records are `execution.md`, `critic.md`, and `update_log.md`. Stage validation records are under `reports/t02_validation.md`, `reports/t03_validation.md`, `reports/t04_validation.md`, `reports/t05/validation.md`, and `reports/t06/validation.md`.

The final audit found no open metric or narrative reconciliation issue. Overall project acceptance remains pending native Power BI authoring and render evidence; the preview and handoff package are available for that step.
