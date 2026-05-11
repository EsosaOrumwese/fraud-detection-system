# Flow Quality Lineage - v1

As of `2026-04-03`

Lineage path:
1. `s2_event_stream_baseline_6B`
2. `s2_flow_anchor_baseline_6B`
3. `s4_case_timeline_6B`
4. `s4_flow_truth_labels_6B`
5. `s4_flow_bank_view_6B`

Transformation chain:
1. profile source coverage and critical keys
2. reconcile event -> flow -> case -> outcome linkage
3. compare authoritative truth to bank-view outcome semantics on the case-selected subset
4. quantify mismatch classes
5. build raw-versus-corrected KPI comparisons
6. package a safer reporting-ready output with explicit source-rule notes

Usage boundary:
- this slice is safe for claims about bounded data-quality ownership over one governed analytical path
- this slice is not safe for claims about platform-wide DQ monitoring or universal source-rule enforcement across every consumer
