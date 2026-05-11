# Process Efficiency Regeneration

Regeneration posture:
- compact `3.D` outputs reused first
- heavy raw rescans not required for this slice
- heavy work stays in `DuckDB`
- Python reads only compact shaped outputs after SQL reduction

Execution order:
1. build `efficiency_support_compare_v1.parquet`
2. build `targeted_review_support_v1.parquet`
3. build `improvement_release_checks_v1.parquet`
4. regenerate notes and figures

Current regeneration time:
- about `0.1` seconds
