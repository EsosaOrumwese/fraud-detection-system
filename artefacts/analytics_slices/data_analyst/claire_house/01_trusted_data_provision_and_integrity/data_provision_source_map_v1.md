
# Data Provision Source Map v1

Provision window:
- `Mar 2026`

Source surfaces mapped into the lane:
- `s2_flow_anchor_baseline_6B`
  - provision backbone for `flow_id`, `flow_ts_utc`, `amount`, `merchant_id`, `party_id`
- `s4_case_timeline_6B`
  - contributes `case_id`
  - requires rolling because raw rows are event-grain and not safe for direct downstream provision
- `s4_flow_truth_labels_6B`
  - contributes `is_fraud_truth` and `fraud_label`

Controlled provision path:
- monthly flow base fixed first
- case timeline rolled to one maintained row per `flow_id`
- truth labels joined at `flow_id`
- protected downstream summary released only from the controlled maintained lane

Control consequence:
- `81,360,532` monthly flow rows remain the bounded provision intake
- `20,581,909` raw linked case-event rows are treated as an unsafe control surface
- `7,835,199` maintained `flow_id`-grain rows form the trusted release-safe lane
