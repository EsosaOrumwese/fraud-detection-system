# Population Pathway Product Contract v1

Purpose:
- describe the reusable outputs produced by the bounded population-pathway slice

Primary product:
- `population_pathway_base_v1`

Grain:
- one row per `flow_id`

Purpose:
- reusable linked base for population, pathway, and outcome analysis

Downstream outputs:
- `population_cohort_metrics_v1`
  - cohort-level comparison output
- `population_pathway_reporting_v1`
  - pathway-stage reporting output
- `population_pathway_kpis_v1`
  - split-level KPI output
- `population_pathway_problem_summary_v1`
  - compact operating-problem surface

Key fields:
- `flow_id`
- `first_event_ts_utc`
- `case_id`
- `is_case_selected`
- `pathway_stage`
- `lifecycle_hours`
- `target_is_fraud_truth`
- `is_fraud_bank_view`
- `split_role`

Authoritative-source rules:
- event timing from `s2_event_stream_baseline_6B`
- case progression from `s4_case_timeline_6B`
- authoritative fraud truth from `s4_flow_truth_labels_6B`
- bank-view outcome is comparison-only

Downstream consumers:
- cohort comparison
- pathway reporting
- KPI summaries
- operating interpretation notes

Usage boundary:
- this contract applies only to the bounded 20-part slice
- it is not a platform-wide production contract
