# Service Line Source Map v1

Review windows:
- prior week: `2026-03-16`
- current week: `2026-03-23`

Source purposes:
- `s2_event_stream_baseline_6B`: entry-event coverage and event-volume context for flows in the bounded service-line windows
- `s2_flow_anchor_baseline_6B`: anchor grain, amount, and review-window membership
- `s4_case_timeline_6B`: case opening, closure, pathway stage, and lifecycle burden
- `s4_flow_truth_labels_6B`: authoritative outcome-quality signal for the service-line KPIs
- `s4_flow_bank_view_6B`: comparison-only operational outcome surface used for discrepancy reading, not KPI authority

Grain note:
- the merged analytical base is at `flow_id`
- KPI outputs aggregate that base to `week_role` and `amount_band`

Fit-for-use note:
- event coverage is complete across the bounded windows
- truth and bank-view coverage are complete across the bounded windows
- case chronology is available for the bounded service-line slice
