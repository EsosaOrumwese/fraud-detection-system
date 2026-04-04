# Interface Handoff Map v1

Producer:
- `maintained_processing_layer`

Consumer:
- `workflow_regeneration_path`

Boundary purpose:
- hand the governed band-level KPI surface into the reusable regeneration path without field, grain, or baseline drift

Required interface fields:
- `18` fields

Downstream outputs depending on the boundary:
- `scheduled_summary, ad_hoc_supporting_detail, leadership_summary, external_oversight_cut`
