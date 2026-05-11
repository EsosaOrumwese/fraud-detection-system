# Model Lineage And Join Path v1

Join path:
- `s2_flow_anchor_baseline_6B` -> `s4_flow_truth_labels_6B` on `flow_id`
- `s2_flow_anchor_baseline_6B` -> `s4_flow_bank_view_6B` on `flow_id`
- `s2_flow_anchor_baseline_6B` -> bounded `CASE_OPENED` view from `s4_case_timeline_6B` on `flow_id`

Modelling posture:
- anchor supplies the feature backbone
- truth supplies the authoritative target
- bank view remains comparison-only
- case timeline supports bounded explanatory context and governance checks only
