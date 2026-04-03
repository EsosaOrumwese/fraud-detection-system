# README - Service Line Reporting Regeneration

Regeneration entrypoint:
- `python artefacts/analytics_slices/data_analyst/huc/02_reporting_cycle_ownership/models/build_reporting_cycle_ownership.py`

Inputs:
- compact KPI output from HUC slice 1
- compact segment summary from HUC slice 1
- compact discrepancy summary from HUC slice 1

Regeneration posture:
- this slice does not read the full merged service-line base into memory
- it reuses compact reporting-ready outputs only

Outputs:
- reporting-cycle summary extract
- exception extract
- release-check extract
- recurring three-page reporting pack
- figures
- requirement, caveat, and rerun-control notes
