# Flow Quality Source Rules - v1

As of `2026-04-03`

Purpose:
- pin which governed source is allowed to define which downstream field in this slice

Authoritative rules:
- `s2_event_stream_baseline_6B`
  - defines entry participation and event timing only
- `s2_flow_anchor_baseline_6B`
  - defines canonical `flow_id` and flow-level context
- `s4_case_timeline_6B`
  - defines case linkage and pathway progression fields
- `s4_flow_truth_labels_6B`
  - defines authoritative fraud outcome for yield-style KPI logic
- `s4_flow_bank_view_6B`
  - defines comparison-only operational outcome surface
  - must not replace truth when calculating fraud-yield KPIs

Quality rule introduced by this slice:
- `authoritative_outcome_rate` must always be calculated from `s4_flow_truth_labels_6B`
- `comparison_outcome_rate` from `s4_flow_bank_view_6B` may be shown alongside truth for operational comparison, but it must be labelled as comparison-only

Reason:
- the bounded slice shows large semantic divergence between bank view and authoritative truth
- if bank view is treated as authoritative, downstream yield interpretation becomes materially distorted
