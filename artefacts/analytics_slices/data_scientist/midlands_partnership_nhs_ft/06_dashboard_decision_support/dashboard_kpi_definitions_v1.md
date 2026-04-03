# Dashboard KPI Definitions v1

Core KPIs:
- `flows_in_scope`: total scored flows in the bounded reporting window
- `high_band_flows`: scored flows in the selected High band
- `medium_band_flows`: scored flows in the selected Medium band
- `fraud_truth_rate`: authoritative fraud-truth rate in the bounded slice
- `case_open_rate`: share of scored flows with opened cases
- `high_band_truth_rate`: authoritative fraud-truth rate inside the selected High band

Reuse rule:
- KPI names and meanings must stay consistent across executive, workflow, and drill-through pages

Audience rule:
- executive view gets headline volume, band, and trend metrics first
- workflow view gets stage, workload, and prioritisation metrics
- drill-through view gets detailed cohort and explanation context
