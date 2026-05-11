# Flow Quality Definitions - v1

As of `2026-04-03`

Definitions used in this slice:
- `case-selected flow`
  - any `flow_id` with a linked `case_id`
- `authoritative outcome`
  - fraud outcome from `s4_flow_truth_labels_6B`
- `comparison outcome`
  - operational bank-view signal from `s4_flow_bank_view_6B`
- `raw bank-view reading`
  - KPI calculated with bank-view boolean where a careless consumer could use it as if it were authoritative
- `corrected truth reading`
  - KPI calculated with authoritative fraud truth
- `mismatch rate`
  - share of case-selected flows where authoritative truth and bank-view boolean disagree

Interpretive rule:
- a mismatch here is not proof of broken data ingestion
- it is proof that two outcome surfaces represent materially different meanings and must not be conflated in KPI logic
