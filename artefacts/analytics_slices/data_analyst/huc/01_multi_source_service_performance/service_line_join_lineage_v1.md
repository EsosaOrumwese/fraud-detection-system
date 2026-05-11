# Service Line Join Lineage v1

Join path:
- start from `s2_flow_anchor_baseline_6B` at `flow_id` grain for the bounded current and prior review weeks
- attach event coverage from `s2_event_stream_baseline_6B` by `flow_id`
- attach case chronology from `s4_case_timeline_6B` by `flow_id`
- attach authoritative truth from `s4_flow_truth_labels_6B` by `flow_id`
- attach comparison-only bank view from `s4_flow_bank_view_6B` by `flow_id`

Usage boundary:
- this slice is for bounded service-line performance comparison and discrepancy-aware reporting
- it is not a full operational estate and not a whole-platform throughput claim
