# Model Source Rules v1

Authoritative target source:
- `s4_flow_truth_labels_6B`

Comparison-only operational source:
- `s4_flow_bank_view_6B`

Feature-allowed first-pass source:
- `s2_flow_anchor_baseline_6B`

Restricted source:
- `s4_case_timeline_6B` is allowed only for bounded explanatory context and not for post-outcome feature leakage

Safe-use rule:
- comparison-only bank-view fields may support explanation or assurance, but they must not override authoritative fraud truth in target logic
