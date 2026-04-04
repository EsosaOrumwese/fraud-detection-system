# Trend Risk Regeneration

Regeneration posture:
- heavy work stays in `DuckDB`
- bounded monthly raw scans only
- no broad raw-data pandas loads
- Python reads only compact shaped outputs after SQL reduction

Execution order:
1. build `trend_month_band_agg_v1.parquet`
2. build `monthly_trend_compare_v1.parquet`
3. build `monthly_risk_opportunity_focus_v1.parquet`
4. build `trend_release_checks_v1.parquet`
5. regenerate notes and figures

Current regeneration time:
- about `400.9` seconds
