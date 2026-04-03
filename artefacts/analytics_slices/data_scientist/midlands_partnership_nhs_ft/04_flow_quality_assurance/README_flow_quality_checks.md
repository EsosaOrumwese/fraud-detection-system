# README - Flow Quality Checks

As of `2026-04-03`

Purpose:
- rerun the bounded quality-assurance pack for the Midlands `04_flow_quality_assurance` slice

Inputs:
- bounded file selection in `logs/bounded_file_selection.json`
- governed local parquet surfaces from `runs/local_full_run-7`

Runner:
- `python models/build_flow_quality_assurance.py`

What it produces:
- source-scope metrics
- reconciliation checks
- anomaly and mismatch summaries
- label crosswalk summaries
- KPI before/after comparisons
- `flow_quality_reporting_ready_v1.parquet`
- `execution_fact_pack.json`

What to review first:
1. `metrics/02_flow_quality_reconciliation_checks.csv`
2. `metrics/03_flow_quality_anomaly_checks.csv`
3. `metrics/05_flow_quality_kpi_before_after.csv`
4. `metrics/execution_fact_pack.json`

Pass condition for this slice:
- linkage remains clean enough to isolate a semantic/source-governance issue
- the anomaly class remains visible
- raw-versus-corrected KPI distortion remains quantifiable

Failure condition:
- no material anomaly class remains
- the bounded path changes enough that the chosen issue no longer anchors the slice cleanly
