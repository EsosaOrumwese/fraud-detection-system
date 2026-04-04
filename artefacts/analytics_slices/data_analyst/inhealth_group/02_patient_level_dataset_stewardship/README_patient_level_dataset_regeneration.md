# Patient-Level Dataset Regeneration README

Regeneration posture:
- heavy work stays in `DuckDB`
- raw parquet is scanned only through bounded SQL
- Python reads only compact outputs after SQL reduction

Bounded window:
- `Mar 2026`

Regenerated outputs:
- `patient_level_source_profile_v1.parquet`
- `patient_level_reporting_dataset_v1.parquet`
- `patient_level_validation_checks_v1.parquet`
- `patient_level_reporting_safe_summary_v1.parquet`
- `patient_level_reconciliation_checks_v1.parquet`
