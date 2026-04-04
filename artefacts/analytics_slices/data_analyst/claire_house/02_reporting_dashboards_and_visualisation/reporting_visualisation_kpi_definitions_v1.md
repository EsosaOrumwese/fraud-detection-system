
# Reporting And Visualisation KPI Definitions v1

Shared KPI family:
- `flow_rows`
  - bounded monthly intake for the reporting window
- `case_open_rate`
  - case-opened rows divided by bounded monthly flow rows
- `case_truth_rate`
  - truth rows divided by case-opened rows
- `burden_minus_yield_pp`
  - case-opened workload share minus truth-output share by amount band

Shared grouping dimension:
- `amount_band`
  - `<10`
  - `10-25`
  - `25-50`
  - `50+`

Summary-page overall readings:
- overall case-open rate: `9.63%`
- overall truth quality: `19.86%`

Top supporting-detail reading:
- band: `50+`
- burden-minus-yield gap: `+1.01 pp`
- case-open gap to overall: `+1.19 pp`
- truth-quality gap to overall: `-1.76 pp`
