# Service Line Authoritative Source Rules v1

KPI authority:
- workflow-entry volume: `s2_flow_anchor_baseline_6B`
- event-entry volume context: `s2_event_stream_baseline_6B`
- conversion into case work: `s4_case_timeline_6B`
- lifecycle burden and pathway stage: `s4_case_timeline_6B`
- outcome quality: `s4_flow_truth_labels_6B`

Comparison-only rule:
- `s4_flow_bank_view_6B` is used only to identify discrepancy between operational comparison labels and authoritative truth
- it must not override the authoritative outcome-quality KPI

Current bounded discrepancy:
- current truth-versus-bank mismatch on case-opened flows is 58.6%
- current bank-view case rate is 51.1%
- current authoritative truth case rate is 19.9%
