# Population Pathway Data Dictionary v1

Purpose:
- define the canonical vocabulary for the bounded population-pathway slice
- keep the population, pathway, outcome, and cohort language stable across outputs

Population:
- bounded transaction-entry flow population from the selected `s2_event_stream_baseline_6B` parts
- base analytical unit: `flow_id`
- bounded population size: `3,455,613` flows

Suspicious-pathway subset:
- the case-linked subset of the bounded population
- operational definition: `is_case_selected = 1`, derived from presence of `CASE_OPENED` in `s4_case_timeline_6B`
- bounded suspicious-pathway size: `361,504` flows

Pathway:
- entry: first event timestamp in `s2_event_stream_baseline_6B`
- suspicious-pathway entry: `CASE_OPENED`
- downstream progression: case-event sequence and pathway-stage markers from `s4_case_timeline_6B`
- outcome surfaces: `s4_flow_truth_labels_6B` and `s4_flow_bank_view_6B`

Outcome:
- authoritative outcome: `target_is_fraud_truth` from `s4_flow_truth_labels_6B`
- comparison outcome: `is_fraud_bank_view` from `s4_flow_bank_view_6B`

Core fields:
- `flow_id`: base analytical unit and primary join key
- `case_id`: downstream case identifier where present
- `first_event_ts_utc`: entry timestamp for the bounded flow population
- `case_opened_ts_utc`: entry timestamp for the suspicious-pathway subset
- `lifecycle_hours`: bounded case duration from `CASE_OPENED` to `CASE_CLOSED` or last observed case event
- `pathway_stage`: highest observed downstream stage for the flow
- `split_role`: time-ordered split over `first_event_ts_utc`

Pathway stages:
- `no_case`
- `opened_only`
- `detection_event_attached`
- `customer_dispute`
- `chargeback_initiated`
- `chargeback_decision`

Cohorts:
- `fast_converting_high_yield`
- `slow_converting_high_yield`
- `high_burden_low_yield`
- `low_burden_low_yield`

Usage boundary:
- this dictionary applies only to the bounded slice described in `logs/bounded_file_selection.json`
- it is not a whole-platform data contract
