# Patient-Level Dataset Source Map v1

Bounded stewardship window:
- `Mar 2026`

Maintained detailed dataset grain:
- one row per `flow_id` where the bounded monthly flow converted into a case-opened record

Source responsibilities:
- `s2_flow_anchor_baseline_6B`
  - authoritative for `flow_id`, `flow_ts_utc`, `amount`, `merchant_id`, `party_id`
- `s4_case_timeline_6B`
  - authoritative for `case_id`
  - not safe to join directly because it is event-grain rather than maintained reporting grain
- `s4_flow_truth_labels_6B`
  - authoritative for `is_fraud_truth` and `fraud_label`

Maintained join path:
- flow-month slice first
- case timeline rolled to one row per `flow_id`
- truth labels joined at `flow_id`
