# Programme Reporting Regeneration README

Regeneration posture:
- heavy work stays in `DuckDB`
- raw parquet is scanned only through bounded SQL
- Python reads only compact outputs after SQL reduction

Execution window:
- prior month: `Feb 2026`
- current month: `Mar 2026`

Regenerated outputs:
- `programme_month_band_agg_v1.parquet`
- `programme_monthly_summary_v1.parquet`
- `programme_ad_hoc_follow_up_v1.parquet`
- `programme_release_checks_v1.parquet`
