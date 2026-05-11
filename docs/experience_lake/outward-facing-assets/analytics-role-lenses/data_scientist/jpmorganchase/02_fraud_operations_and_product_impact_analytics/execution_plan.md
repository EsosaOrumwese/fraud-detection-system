# Execution Plan - Fraud Operations And Product Impact Analytics Slice

As of `2026-04-14`

Purpose:
- turn the chosen `JPMorganChase` fraud-operations and product-impact slice into a concrete bounded execution order tied to the governed fraud run and the completed `A` slice
- keep the work SQL-first, impact-first, and materialised in stages
- avoid broad exploratory loading or premature expansion into second-line governance or cloud-implementation rhetoric that belongs in later slices

Execution substrate:
- [local_full_run-7](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\runs\local_full_run-7)
- [execution_fact_pack.json](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\artefacts\analytics_slices\data_scientist\jpmorganchase\01_fraud_strategy_and_rule_optimisation\metrics\execution_fact_pack.json)
- [strategy_ready_base_v1.parquet](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\artefacts\analytics_slices\data_scientist\jpmorganchase\01_fraud_strategy_and_rule_optimisation\extracts\strategy_ready_base_v1.parquet)
- [ruleset_comparison_output_v1.parquet](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\artefacts\analytics_slices\data_scientist\jpmorganchase\01_fraud_strategy_and_rule_optimisation\extracts\ruleset_comparison_output_v1.parquet)
- [detection_effectiveness_output_v1.parquet](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\artefacts\analytics_slices\data_scientist\jpmorganchase\01_fraud_strategy_and_rule_optimisation\extracts\detection_effectiveness_output_v1.parquet)

Primary rule:
- query first
- start from the completed `A` posture
- materialise bounded intermediate tables
- only pull small, already-shaped datasets into Python if a light comparison or note-building step genuinely needs it

---

## 1. Confirmed Working Assumptions

This plan is built around the following already-confirmed facts:
- the fraud substrate exists in the bounded governed run:
  - `local_full_run-7`
- the local run contains the core surfaces needed for a bounded operations-impact first pass:
  - `s2_flow_anchor_baseline_6B`
  - `s4_flow_truth_labels_6B`
  - `s4_flow_bank_view_6B`
  - `s4_case_timeline_6B`
- the working analytical grain can stay at:
  - `flow_id`
- the completed `A` slice already fixed the first-pass strategy posture:
  - baseline: `bank_view_true`
  - preferred: `bank_view_true_amount_lt_50`

Confirmed first-pass join posture:
- `flow_id` is the cross-surface join key

Confirmed first-pass time posture:
- `Mar 2026` remains the aligned reporting window unless a cheap profiling step shows a narrower operational window is required

## 2. SQL-First Working Posture

This slice must not begin by loading whole governed fraud surfaces into Python memory.

The correct posture is:
- use SQL over the parquet-backed local surfaces
- inspect only the impact-relevant aggregates first
- materialise one impact-ready base table in SQL
- materialise one workload-or-prioritisation table in SQL
- materialise one decision-quality table in SQL
- only after that, export a small already-shaped table into Python if a light comparison or rendered summary is genuinely needed

This matters because the first proof burden is:
- operational impact
- efficiency
- decision quality

not:
- another broad strategy search
- another broad model build
- a simulated operations platform

## 3. First-Pass Operational Objective

The first-pass objective is:

`show how the preferred fraud-strategy posture from A changes downstream workload, prioritisation, and decision-quality outcomes for fraud operations and product-support use`

The first pass should therefore prefer:
- translating the completed `A` comparison into operational consequences
- bounded workload and case-follow-up comparisons
- one decision-quality reading that sounds operational, not only strategic

If a broader product-analytics story is later needed, that belongs in a refinement, not in the first pass here.

## 4. Candidate First-Pass Impact Frame

The first-pass impact frame should be:
- compare the `A` baseline and preferred postures on:
  - selected-flow burden
  - selected-flow share
  - fraud-truth concentration
  - retained positives
  - case-follow-up concentration where honest

Primary inherited posture:
- `bank_view_true`

Preferred inherited posture:
- `bank_view_true_amount_lt_50`

This matters because the slice should answer:
- what changes for downstream fraud operations or product stakeholders when the tighter strategy is used?

not:
- can another better rule be found?

## 5. First-Pass Impact Family

The first-pass impact family should stay narrow and low-risk:
- selected flow counts
- selected flow shares
- fraud-truth counts
- fraud-truth yield
- fraud-truth capture
- case-follow-up or case-open concentration where honest
- amount-band or simple bounded composition summaries where needed for explanation

Important constraint:
- do not reopen a broad feature-engineering exercise
- do not rebuild the strategy search from scratch
- do not imply queue-management fields that do not exist in the governed run

That means the first pass should prefer:
- inherited `A` strategy postures
- simple downstream burden measures
- explicit before-versus-after comparisons

The first pass should avoid:
- large raw event reconstruction
- broad operations simulation
- generic product-language without a measurable impact surface behind it

## 6. Bounded SQL Build Order

### Step 1. Create a thin impact profiling layer in SQL

Build small aggregate queries only for:
- selected-flow counts under the inherited `A` postures
- fraud-truth counts and yields under the inherited `A` postures
- case-follow-up counts under the inherited `A` postures
- selected-flow shares and retained-positive shares

Goal:
- confirm that the operational-impact question is answerable without reopening scope

### Step 2. Materialise an impact-ready base table in SQL

Create one bounded SQL output, for example:
- `fraud_operations_impact_base_v1`

This table should include:
- `flow_id`
- aligned reporting month
- inherited strategy-posture flags
- fraud-truth target
- bank-view flag
- case-follow-up flag where available
- simple bounded attributes needed for compact explanation

This table should be:
- explicit
- documented
- reusable

### Step 3. Materialise a workload-or-prioritisation table in SQL

Create one downstream-ready SQL output, for example:
- `fraud_workload_prioritisation_output_v1`

This table should be designed for:
- selected-flow burden comparisons
- selected-share comparisons
- simple case-follow-up concentration comparisons
- prioritisation-readiness interpretation

### Step 4. Materialise a decision-quality table in SQL

Create one explicit decision-quality output, for example:
- `fraud_decision_quality_output_v1`

This table should summarise:
- fraud-truth yield by posture
- fraud-truth capture by posture
- positive-retention trade-off
- one bounded operational reading that explains why the preferred posture is more useful

### Step 5. Export only the bounded impact slice

After SQL shaping is complete:
- export only the columns required for light rendered summaries
- keep Python working on the already-shaped impact tables, not the raw governed surfaces

## 7. Time And Comparison Strategy

The comparison strategy should remain:
- same month
- same grain
- same governed truth
- different strategy posture

Reason:
- this slice is about translation into operational impact
- not about changing both the strategy and the evaluation frame at the same time

The first-pass comparison should therefore stay on:
- `Mar 2026`
- `flow_id`
- baseline versus preferred inherited `A` postures

## 8. Impact Comparison Posture

The first-pass impact-comparison posture should stay minimal:
- one baseline operational posture
- one preferred operational posture
- one explicit trade-off reading

Recommended baseline:
- inherited broad bank-view gate

Recommended preferred posture:
- inherited tighter amount-gated bank-view posture

The point of the first pass is not impact maximisation.

The point is to prove:
- a governed impact-ready base
- a measurable workload difference
- a measurable decision-quality difference
- one compact operational or product-use reading

## 9. Evaluation Strategy

The first-pass metric set should remain compact.

Primary metrics:
- selected-flow reduction versus baseline
- selected-flow share versus baseline
- fraud-truth yield under each posture
- fraud-truth capture under each posture

Secondary metrics:
- retained-positive share
- case-follow-up share where honest
- one concentration or composition cut if it materially helps explanation

Do not overbuild metrics in the first pass.
The output needs to be claimable and operationally interpretable, not academically exhaustive.

## 10. Product-And-Operations Reading Rule

The first-pass output must produce:
- one baseline operational reading
- one preferred operational reading
- one explicit impact note

Interpretation rule:
- state what becomes easier or more efficient under the preferred posture
- state what decision-quality improvement is gained
- state what is given up in retained positives or case-follow-up coverage

This note should sound like:
- a fraud-operations and product-impact reading

not:
- another abstract strategy explanation

## 11. Planned Deliverables

SQL and shaped data:
- one profiling query pack
- one `fraud_operations_impact_base_v1` build query
- one `fraud_workload_prioritisation_output_v1` build query
- one `fraud_decision_quality_output_v1` build query

Python or light rendering support:
- one bounded comparison notebook or script only if SQL alone is not enough

Documentation:
- operational-impact scope note
- impact-ready base note
- workload-prioritisation note
- decision-quality note
- product-and-operations impact note
- caveats note
- regeneration README

Expected output bundle for the first pass:
- reusable impact-ready base
- one workload-or-prioritisation surface
- one decision-quality surface
- one short action-oriented operational-impact interpretation note

## 12. Execution Order

1. Finalise the folder structure for this responsibility lane.
2. Run SQL-only profiling queries over the local fraud surfaces and inherited `A` posture.
3. Pin the exact impact comparison definitions.
4. Materialise the impact-ready base in SQL.
5. Materialise the workload-or-prioritisation output.
6. Materialise the decision-quality output.
7. Decide whether light Python support is still worth using.
8. Write the product-and-operations impact note and documentation pack.
9. Prepare the outward-facing execution-report inputs.

## 13. Stop Conditions

Stop and reassess if any of the following happens:
- the impact question collapses into another strategy-search question
- the required joins are not stable enough for a clean impact-ready base
- the slice requires heavy raw event expansion before any bounded operational reading is meaningful
- the product-and-operations reading cannot be supported with measured workload or decision-quality changes

If one of those conditions occurs, the adaptation path is:
- keep the same responsibility lane
- narrow the slice further
- preserve the workload and decision-quality comparison core
- defer broader product wording

## 14. What This Plan Is And Is Not

This is:
- a concrete execution plan for the `JPMorganChase B` operations-impact slice
- SQL-first
- impact-first
- bounded
- aligned to the governed fraud run and the completed `A` posture

This is not:
- the execution report
- a results note
- permission to start loading whole datasets into memory
- permission to broaden into second-line governance or cloud-native implementation claims

The first operational move after this plan should be:
- SQL profiling queries only
