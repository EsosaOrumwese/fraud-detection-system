# Population Pathway Lineage v1

Product:
- `population_pathway_analysis_v1`

Base grain:
- `flow_id`

Bounded source chain:
- `s2_event_stream_baseline_6B`
  - transaction-entry population
  - event timing
- `s2_flow_anchor_baseline_6B`
  - flow context
  - amount
  - entity identifiers
- `s4_case_timeline_6B`
  - suspicious-pathway entry
  - case progression
  - pathway stage
- `s4_flow_truth_labels_6B`
  - authoritative fraud truth
- `s4_flow_bank_view_6B`
  - operational comparison surface

Transformation path:
1. build flow-level event-entry population from `s2_event_stream_baseline_6B`
2. attach flow context from `s2_flow_anchor_baseline_6B`
3. roll case chronology to one flow-level pathway summary from `s4_case_timeline_6B`
4. attach authoritative truth and comparison outcomes
5. derive split markers, pathway stages, and case-selection flag
6. derive cohort summaries, pathway summaries, KPI summaries, and problem summary outputs

Observed bounded-slice shape:
- `3,455,613` bounded population flows
- `361,504` case-linked suspicious-pathway flows
- one case per linked flow in the bounded slice

Usage boundaries:
- this lineage is valid only for the bounded 20-part slice
- the case-linked subset is a trusted suspicious-pathway analogue, not a claim about all possible fraud-detection populations in the full platform
