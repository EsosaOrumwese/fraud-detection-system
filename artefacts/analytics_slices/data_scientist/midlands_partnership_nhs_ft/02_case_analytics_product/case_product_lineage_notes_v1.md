# Case Product Lineage Notes v1

Product:
- `case_analytics_product_v1`

Natural grain:
- `case_id`

Bounded source chain:
- `s4_case_timeline_6B`
  - case chronology
  - case-to-flow bridge
  - event-stage flags
- `s2_flow_anchor_baseline_6B`
  - flow context
  - amount
  - anchor timestamp
  - entity identifiers
- `s4_flow_truth_labels_6B`
  - authoritative fraud truth
- `s4_flow_bank_view_6B`
  - secondary operational comparison surface

Transformation path:
1. case timeline events are profiled and rolled up to one case record
2. one flow is attached to each case through the bounded chronology bridge
3. flow anchor context is added
4. truth and bank-view outcomes are added
5. the analytical base is split into:
- `case_model_ready_v1`
- `case_reporting_ready_v1`

Observed bounded-slice shape:
- `361,504` distinct cases
- `361,504` distinct linked flows
- one flow per case within the bounded slice
- no flows linked to multiple cases within the bounded slice

Authoritative-source rules:
- chronology authority: `s4_case_timeline_6B`
- fraud-truth authority: `s4_flow_truth_labels_6B.is_fraud_truth`
- bank-view comparison authority: `s4_flow_bank_view_6B.is_fraud_bank_view`

Downstream-safe usage:
- `case_model_ready_v1`
  - bounded analytical consumer
  - case-level feature and target use
- `case_reporting_ready_v1`
  - stage, lifecycle, amount-band, and case-summary reporting use

Usage boundaries:
- this product is only validated for the bounded slice documented in `logs/bounded_file_selection.json`
- the observed one-to-one case/flow relationship is a bounded-slice fact, not a whole-world claim
- downstream consumers should not assume this product is a live production service
