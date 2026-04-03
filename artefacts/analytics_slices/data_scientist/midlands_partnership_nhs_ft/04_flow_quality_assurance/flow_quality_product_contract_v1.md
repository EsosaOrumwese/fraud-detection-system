# Flow Quality Product Contract - v1

As of `2026-04-03`

Product:
- `flow_quality_reporting_ready_v1`

Purpose:
- provide a safer reporting-ready output that keeps authoritative truth and bank-view comparison visible but separated

Grain:
- `split_role x pathway_stage`

Key fields:
- `case_selected_flows`
- `authoritative_outcome_rate`
- `comparison_outcome_rate`
- `mismatch_rate`
- `source_rule_note`

Authoritative-field rule:
- `authoritative_outcome_rate` is the field allowed for fraud-yield interpretation
- `comparison_outcome_rate` is comparison-only

Allowed downstream use:
- reporting and interpretation of bounded pathway-stage yield differences
- source-rule demonstration for the quality-assurance slice

Not for:
- live production monitoring claims
- replacement of full downstream reporting logic beyond this bounded slice
