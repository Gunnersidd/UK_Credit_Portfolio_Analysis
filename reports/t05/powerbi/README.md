# Power BI import package

## Tables to load

Use **Get Data → Text/CSV** and load the controlled outputs below. Do not load `synthetic_portfolio.csv` for this summary report; it is unnecessary at 55,145 rows and has a different grain.

| Model table | CSV |
|---|---|
| `Monthly` | `reports/t03/sql/monthly_portfolio.csv` |
| `RiskSegment` | `reports/t03/sql/risk_segment.csv` |
| `DelinquencyState` | `reports/t03/sql/delinquency_state.csv` |
| `VintageMOB` | `reports/t03/sql/vintage_mob.csv` |
| `RollRates` | `reports/t03/sql/roll_rates.csv` |
| `Context` | `reports/t04/portfolio_context_joined.csv` |
| `Scenarios` | `reports/t04/scenario_results.csv` |
| `Sensitivity` | `reports/t04/scenario_sensitivity.csv` |

All CSVs are UTF-8. Parse month fields as Date. The T03 monetary columns are integer pence; convert to pounds in Power Query or measures by dividing by 100. T04 scenario monetary columns are already GBP. T04 rate values are percent points (for example, 21.71 means 21.71%), not decimal fractions.

## Relationships

Create a calendar table with one row per month-end and relate `Calendar[Date]` one-to-many to `Monthly[snapshot_month]`, `RiskSegment[snapshot_month]`, `DelinquencyState[snapshot_month]`, `Context[month_end]`, and `RollRates[opening_month]`. `VintageMOB[origination_month]` is a cohort axis, not a snapshot axis; keep it disconnected from the snapshot calendar or use a separate origination calendar. `Scenarios` and `Sensitivity` are scenario tables anchored to September 2026; keep disconnected from snapshot-date slicers. Use single-direction calendar filtering.

## Report pages

1. **Portfolio overview:** month selector; cards for active balance, active accounts, utilisation, payment rate, and both simulated 30+ proxy rates; 12-month balance/limit line chart; 12-month proxy-rate line chart; selected-month status mix.
2. **Segment & vintage:** segment balances and proxy rates over time; MOB curves for utilisation and proxy rate, with observed/active populations clearly distinguished.
3. **Roll rates:** matrix of opening state × destination state, filtered by opening month; include account counts with percentages because small denominators can make rates volatile.
4. **UK context & scenarios:** BoE context trend beside synthetic balance; scenario cards and sensitivity grid. Label scenario values as annualized mechanical proxies and keep them independent of month slicers.

Set page titles/subtitles to say **Synthetic / illustrative portfolio**. Distinguish the generated delinquency state proxy from actual contractual arrears. Source lineage and control values are in `../source_to_output_map.md`.
