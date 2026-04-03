# Service Line KPI Definitions v1

Core KPI families:
- `flow_rows`: bounded workflow-entry pressure at `flow_id` grain
- `case_open_rate`: share of flows converting into case work
- `long_lifecycle_share`: share of case-opened flows taking at least 168 hours from flow to closure or horizon
- `case_truth_rate`: authoritative outcome quality among case-opened flows

Supporting trust KPI:
- `truth_bank_mismatch_rate`: share of case-opened flows where bank-view outcome disagrees with authoritative truth
