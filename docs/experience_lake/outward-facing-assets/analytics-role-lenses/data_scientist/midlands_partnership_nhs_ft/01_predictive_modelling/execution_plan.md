# Execution Plan - Predictive Modelling Slice

As of `2026-04-03`

Purpose:
- turn the chosen predictive-modelling slice into an execution order tied to the local governed run
- keep the work SQL-first, bounded, and materialised in stages
- avoid full-memory reads or broad exploratory loading against large local surfaces

Execution substrate:
- [`runs/local_full_run-7`](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\runs\local_full_run-7)

Primary rule:
- query first
- materialise bounded intermediate tables
- only pull small, already-shaped datasets into Python for modelling

---

## 1. Confirmed Working Assumptions

This plan is built around the following already-confirmed local facts:
- the slice grain is `flow_id`
- `flow_id` exists across the core local surfaces needed for the slice
- the local governed run contains the main target and workflow surfaces needed for a bounded first pass

Confirmed local surfaces for first-pass planning:
- `s2_flow_anchor_baseline_6B`
- `s4_flow_truth_labels_6B`
- `s4_flow_bank_view_6B`
- `s4_case_timeline_6B`

Confirmed first-pass join posture:
- `flow_id` is the cross-surface join key

## 2. SQL-First Working Posture

This slice must not begin by loading whole parquet datasets into Python memory.

The correct posture is:
- use SQL over parquet-backed local surfaces
- inspect only schema, key coverage, and bounded aggregates first
- materialise a modelling base table in SQL
- materialise a reporting or cohort table in SQL
- only after that, export a bounded training slice for Python

This matters because the local run is large enough that naive in-memory loading is the wrong operating method and does not match the analytical-delivery story we are trying to build.

## 3. First-Pass Analytical Objective

The first-pass objective is:

`build a bounded flow-level risk stratification slice that predicts authoritative fraud truth and produces operationally usable high / medium / low cohorts`

The forecast component remains secondary.

The forecast should only be executed if:
- the demand surface can be built cheaply from SQL aggregation
- it does not delay the main scoring and cohort work

If the forecast becomes a drag on the slice, it should be dropped from the first pass and revisited later.

## 4. Candidate First-Pass Target

The first target candidate should be:
- `s4_flow_truth_labels_6B.is_fraud_truth`

Reason:
- it is the cleanest authoritative flow-level outcome currently confirmed locally
- it aligns directly with the bounded fraud-yield question
- it avoids inventing a weaker proxy target too early

Secondary comparison surface:
- `s4_flow_bank_view_6B`

This should be used for:
- bank-view comparison
- trust and interpretation checks
- possible cohort explanation

It should not displace the first-pass target unless the local evidence shows that `is_fraud_truth` is unusable for the slice.

## 5. First-Pass Feature Family

The first-pass feature family should stay narrow and low-risk:
- flow timestamp
- amount
- merchant identifier
- party identifier
- account identifier
- instrument identifier
- device identifier
- IP identifier
- arrival sequence
- bounded case-derived aggregates joined back by `flow_id` only where they do not leak future truth

Important constraint:
- no feature may depend on downstream truth fields
- no feature may depend on post-outcome case events that would leak the target

That means the first pass should prefer:
- anchor-derived features
- pre-outcome structural features
- simple time features derived from anchor timestamps

The first pass should avoid:
- complex event-sequence reconstruction
- downstream case-event counts computed beyond the scoring boundary
- anything that uses label-state content as a feature

## 6. Bounded SQL Build Order

### Step 1. Create a thin profiling layer in SQL

Build small aggregate queries only for:
- target prevalence
- count of distinct `flow_id`
- count of `flow_id` with matching case records
- min and max timestamp in the anchor table
- null or missingness checks for first-pass anchor fields

Goal:
- confirm viability without scanning into Python

### Step 2. Materialise a model-base table in SQL

Create one bounded SQL output, for example:
- `flow_model_base_v1`

This table should include:
- `flow_id`
- anchor features
- target flag from flow truth
- train / validation / test split marker derived from time

This table should be:
- explicit
- documented
- reusable

### Step 3. Materialise a cohort / reporting base table in SQL

Create one downstream-ready SQL output, for example:
- `flow_priority_reporting_v1`

This table should be designed for:
- score band summaries
- cohort comparisons
- stakeholder-facing interpretation

### Step 4. Export only the bounded modelling slice

After SQL shaping is complete:
- export only the required columns
- export only the chosen bounded window
- keep Python working on the already-shaped table, not the raw governed surfaces

## 7. Split Strategy

The split strategy should be time-based, not random.

Reason:
- the slice needs to support a real-delivery claim
- time-based validation is closer to the operational framing of future use
- random splits are easier but less defensible here

First-pass split posture:
- earliest window: training
- middle window: validation
- latest bounded window: test

The exact date boundaries should be set only after a small SQL timestamp profile confirms coverage.

## 8. Model Strategy

The first-pass modelling strategy should stay minimal:
- one explainable baseline model
- optionally one stronger challenger if the baseline underperforms materially

Recommended baseline:
- logistic regression or another simple linear probabilistic model

Recommended challenger:
- gradient boosting or light tree-based classifier

The point of the first pass is not model maximisation.

The point is to prove:
- a governed target
- a usable feature slice
- stable risk ranking
- operational cohort separation

## 9. Evaluation Strategy

The first-pass metric set should remain compact.

Primary metrics:
- positive-yield lift in the high-risk band versus overall baseline
- capture rate of positive outcomes in top-ranked flows
- time-split stability across validation and test windows

Secondary metrics:
- precision in the high-risk band
- score distribution and class separation checks

Do not overbuild metrics in the first pass.
The output needs to be claimable and operationally interpretable, not academically exhaustive.

## 10. Risk Bands And Cohorts

The first-pass output must produce:
- `High`
- `Medium`
- `Low`

These should not be arbitrary equal-size bins if the score distribution makes them meaningless.

Banding rule:
- choose thresholds based on operational usefulness and yield separation
- document the thresholds and why they were chosen

First-pass cohort outputs should show:
- band size
- fraud-truth yield by band
- share of all positive outcomes captured by band
- major merchant or amount concentration where useful

## 11. Forecast Decision Rule

The forecast remains conditional.

Proceed only if a case-demand surface can be built cheaply from SQL as:
- daily or weekly count of distinct `case_id`
- optionally daily or weekly count of distinct case-opening `flow_id`

If that surface is easy to materialise:
- build one lightweight next-window demand forecast

If not:
- stop the forecasting part for this slice
- keep the first-pass claim on risk scoring and cohort prioritisation only

This is deliberate scope control, not incompleteness.

## 12. Planned Deliverables

SQL and shaped data:
- one profiling query pack
- one `flow_model_base_v1` build query
- one `flow_priority_reporting_v1` build query

Python modelling:
- one modelling notebook or script against the bounded model-base table
- one scored output file or table

Documentation:
- target and feature definition note
- lineage and join note
- usage caveats note
- short decision brief

Expected output bundle for the first pass:
- reusable scored table
- high / medium / low cohort summary
- one short action-oriented interpretation note

## 13. Execution Order

1. Finalise the folder structure for this responsibility lane.
2. Run SQL-only profiling queries over the local surfaces.
3. Pin the exact target and time split.
4. Materialise the model-base table in SQL.
5. Export the bounded modelling table.
6. Train the baseline model in Python.
7. Score the validation and test windows.
8. Define the risk bands.
9. Materialise the reporting-ready cohort summary.
10. Decide whether the forecast is still worth doing.
11. Write the decision brief and documentation pack.

## 14. Stop Conditions

Stop and reassess if any of the following happens:
- the target is too sparse for the first-pass bounded slice
- the required joins are not stable enough for a clean model base
- feature construction requires heavy raw event expansion to become useful
- the forecast work starts to dominate the slice

If one of those conditions occurs, the adaptation path is:
- keep the same responsibility lane
- narrow the slice further
- preserve the scoring and cohort work
- defer the forecast

## 15. What This Plan Is And Is Not

This is:
- a concrete execution plan for the first predictive-modelling slice
- SQL-first
- bounded
- aligned to the actual scale constraint of the local governed run

This is not:
- the execution report
- a results note
- permission to start loading whole datasets into memory

The first operational move after this plan should be:
- SQL profiling queries only
