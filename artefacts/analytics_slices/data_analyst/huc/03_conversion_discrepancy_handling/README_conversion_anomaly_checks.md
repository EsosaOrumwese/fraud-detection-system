# README - Conversion Anomaly Checks

Regeneration entrypoint:
- `python artefacts/analytics_slices/data_analyst/huc/03_conversion_discrepancy_handling/models/build_conversion_discrepancy_handling.py`

Inputs:
- compact weekly KPI output from HUC slice 1

Regeneration posture:
- this slice does not read the full merged service-line base into memory
- it derives the discrepancy from compact reporting-ready KPI inputs only

Outputs:
- discrepancy summary
- before-and-after KPI view
- release checks
- compact two-page exception pack
- figures
- issue, caveat, and rerun-control notes
