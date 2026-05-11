# Execution Plan - Control Effectiveness, Second-Line Alignment, And Compliance Support Slice

As of `2026-04-14`

Purpose:
- turn the chosen `JPMorganChase` control-effectiveness slice into a concrete bounded execution order tied to the governed fraud run and the completed `A` and `B` slices
- keep the work evidence-first, adherence-first, and materialised in stages
- avoid broad exploratory loading or premature expansion into cloud-implementation rhetoric that belongs in later `C`

Execution substrate:
- [local_full_run-7](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\runs\local_full_run-7)
- [execution_fact_pack.json](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\artefacts\analytics_slices\data_scientist\jpmorganchase\01_fraud_strategy_and_rule_optimisation\metrics\execution_fact_pack.json)
- [execution_fact_pack.json](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\artefacts\analytics_slices\data_scientist\jpmorganchase\02_fraud_operations_and_product_impact_analytics\metrics\execution_fact_pack.json)
- [strategy_ready_base_v1.parquet](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\artefacts\analytics_slices\data_scientist\jpmorganchase\01_fraud_strategy_and_rule_optimisation\extracts\strategy_ready_base_v1.parquet)
- [ruleset_comparison_output_v1.parquet](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\artefacts\analytics_slices\data_scientist\jpmorganchase\01_fraud_strategy_and_rule_optimisation\extracts\ruleset_comparison_output_v1.parquet)
- [detection_effectiveness_output_v1.parquet](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\artefacts\analytics_slices\data_scientist\jpmorganchase\01_fraud_strategy_and_rule_optimisation\extracts\detection_effectiveness_output_v1.parquet)
- [impact_ready_base_v1.parquet](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\artefacts\analytics_slices\data_scientist\jpmorganchase\02_fraud_operations_and_product_impact_analytics\extracts\impact_ready_base_v1.parquet)
- [workload_prioritisation_output_v1.parquet](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\artefacts\analytics_slices\data_scientist\jpmorganchase\02_fraud_operations_and_product_impact_analytics\extracts\workload_prioritisation_output_v1.parquet)
- [decision_quality_output_v1.parquet](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\artefacts\analytics_slices\data_scientist\jpmorganchase\02_fraud_operations_and_product_impact_analytics\extracts\decision_quality_output_v1.parquet)

Primary rule:
- query first
- start from the completed `A` and `B` posture
- materialise bounded intermediate tables
- only pull small, already-shaped datasets into Python if a light rendered summary is genuinely needed

---

## 1. Confirmed Working Assumptions

This plan is built around the following already-confirmed facts:
- the governed fraud substrate exists in the bounded local run:
  - `local_full_run-7`
- the completed `A` slice already fixed the baseline and preferred fraud postures:
  - baseline: `bank_view_true`
  - preferred: `bank_view_true_amount_lt_50`
- the completed `B` slice already fixed the downstream operational reading over the same postures
- the aligned reporting window remains:
  - `Mar 2026`

Confirmed first-pass posture:
- the `D + E` slice should reuse the completed `A` and `B` pack instead of reopening raw rule search

Confirmed first-pass control question:
- can the preferred posture be defended as a bounded first-line control improvement with explicit burden reduction, explicit trade-off disclosure, and release-safe adherence evidence?

## 2. Evidence-First Working Posture

This slice must not begin by loading broad governed fraud surfaces into Python memory.

The correct posture is:
- use SQL over the already-shaped `A` and `B` artefacts first
- inspect only the control-relevant aggregates first
- materialise one control-effectiveness base in SQL
- materialise one second-line-alignment output in SQL
- materialise one compliance-adherence output in SQL
- only after that, export a small already-shaped table into Python if a light rendered summary is genuinely needed

This matters because the first proof burden is:
- effectiveness confirmation
- second-line alignment support
- compliance and audit adherence support

not:
- another broad strategy search
- another operations-impact build
- a simulated governance process

## 3. First-Pass Control Objective

The first-pass objective is:

`turn the completed fraud-strategy and operations-impact evidence into one bounded control-confirmation pack that makes improvement, burden reduction, and trade-off evidence explicit for second-line and compliance use`

The first pass should therefore prefer:
- reuse over rebuild
- explicit challenge dimensions over a broad governance story
- one adherence surface that stays close to pinned metrics and release-safe checks

If a broader governance narrative is later needed, that belongs in outward-facing reporting, not in the first-pass build here.

## 4. Candidate First-Pass Control Frame

The first-pass control frame should compare the inherited baseline and preferred postures on:
- fraud-truth yield
- fraud-truth capture
- selected-flow burden
- downstream case-event burden

Secondary challenge dimensions:
- dispute-flow concentration
- chargeback-flow concentration
- release checks already passed

This matters because the slice should answer:
- what evidence would a first-line team present to show that the preferred posture is both more efficient and still challenge-ready?

not:
- can another rule be found?

## 5. First-Pass Challenge And Adherence Family

The first-pass family should stay narrow and low-risk:
- baseline and preferred postures
- yield improvement
- burden reduction
- positive-capture trade-off
- case-event reduction
- dispute / chargeback concentration
- release-safe adherence checks

Important constraint:
- do not reopen broad raw fraud scope
- do not imply actual second-line sign-off workflow
- do not imply actual audit testing workflow

That means the first pass should prefer:
- inherited strategy and impact evidence
- compact explicit challenge dimensions
- explicit adherence rows over prose-only governance claims

## 6. Bounded SQL Build Order

### Step 1. Create a thin control profiling layer in SQL

Build small aggregate queries only for:
- baseline versus preferred yield
- baseline versus preferred burden
- baseline versus preferred capture
- dispute and chargeback concentration
- release-check totals from the prior packs

Goal:
- confirm that the control-confirmation question is answerable without reopening scope

### Step 2. Materialise a control-effectiveness base in SQL

Create one bounded SQL output:
- `control_effectiveness_base_v1`

This table should include:
- reporting window
- baseline and preferred postures
- selected-flow burden
- fraud-truth counts
- fraud-truth yield
- fraud-truth capture
- case-event burden
- dispute / chargeback concentration

This table should be:
- explicit
- documented
- reusable

### Step 3. Materialise a second-line-alignment output in SQL

Create one challenge-ready SQL output:
- `second_line_alignment_output_v1`

This table should be designed for:
- effectiveness gain
- burden reduction
- trade-off disclosure
- explicit challenge dimensions that a second-line audience could test

### Step 4. Materialise a compliance-adherence output in SQL

Create one adherence-focused SQL output:
- `compliance_adherence_output_v1`

This table should summarise:
- authoritative fraud truth is pinned
- baseline and preferred postures are pinned
- trade-off disclosure is explicit
- release checks already passed

### Step 5. Export only the bounded control slice

After SQL shaping is complete:
- export only the rows required for compact rendered summaries
- keep Python working on the already-shaped control tables, not raw governed surfaces

## 7. Time And Comparison Strategy

The comparison strategy should remain:
- same month
- same governed postures
- same governed truth
- different control interpretation layer

Reason:
- this slice is about control confirmation
- not about changing both the strategy and the evaluation frame at the same time

The first-pass comparison should therefore stay on:
- `Mar 2026`
- baseline `bank_view_true`
- preferred `bank_view_true_amount_lt_50`

## 8. Control Comparison Posture

The first-pass control-comparison posture should stay minimal:
- one baseline control posture
- one preferred control posture
- one explicit alignment surface
- one explicit adherence surface

The point of the first pass is not governance maximisation.

The point is to prove:
- one control-effectiveness base
- one challenge-ready second-line alignment surface
- one adherence-ready compliance surface
- one compact first-line control-confirmation note

## 9. Evaluation Strategy

The first-pass metric set should remain compact.

Primary metrics:
- selected-flow reduction versus baseline
- case-event reduction versus baseline
- fraud-truth yield under each posture
- fraud-truth capture under each posture

Secondary metrics:
- positive-retention share
- dispute-flow concentration delta
- chargeback-flow concentration delta
- combined release checks passed from prior packs

Do not overbuild metrics in the first pass.
The output needs to be claimable and challenge-ready, not procedurally exhaustive.

## 10. Second-Line And Compliance Reading Rule

The first-pass output must produce:
- one baseline control reading
- one preferred control reading
- one explicit confirmation note

Interpretation rule:
- state what became more effective
- state what burden fell
- state what capture trade-off remained
- state why the pack is still suitable for bounded second-line or compliance challenge

This note should sound like:
- a first-line control-confirmation reading

not:
- a claim of second-line ownership

## 11. Planned Deliverables

SQL and shaped data:
- one `control_effectiveness_base_v1` build query
- one `second_line_alignment_output_v1` build query
- one `compliance_adherence_output_v1` build query
- one release-check table

Python or light rendering support:
- one bounded summary script only if SQL alone is not enough

Documentation:
- control-effectiveness scope note
- control-effectiveness note
- second-line alignment note
- compliance-adherence note
- control-confirmation note

Expected output bundle for the first pass:
- reusable control-effectiveness base
- one second-line alignment surface
- one compliance-adherence surface
- one short action-oriented control-confirmation note

## 12. Execution Order

1. Finalise the folder structure for this responsibility lane.
2. Read the completed `A` and `B` fact packs and shaped outputs.
3. Pin the exact control-comparison definitions.
4. Materialise the control-effectiveness base.
5. Materialise the second-line-alignment output.
6. Materialise the compliance-adherence output.
7. Materialise the release-check output.
8. Decide whether light Python support is still worth using.
9. Write the control-confirmation documentation pack.
10. Prepare the outward-facing execution-report inputs.

## 13. Stop Conditions

Stop and reassess if any of the following happens:
- the control question collapses into another strategy-search question
- the alignment surface cannot keep improvement and trade-off visible at the same time
- the compliance surface cannot stay evidence-led without inventing a governance process that does not exist
- the slice requires raw-surface rebuild before any challenge-ready reading is meaningful

If one of those conditions occurs, the adaptation path is:
- keep the same responsibility lane
- narrow the slice further
- preserve the control-effectiveness and adherence core
- defer broader governance rhetoric

## 14. What This Plan Is And Is Not

This is:
- a concrete execution plan for the `JPMorganChase D + E` control-effectiveness slice
- evidence-first
- adherence-first
- bounded
- aligned to the governed fraud run and the completed `A` and `B` packs

This is not:
- the execution report
- a results note
- permission to start loading whole datasets into memory
- permission to broaden into cloud-native implementation claims

The first operational move after this plan should be:
- read the completed `A` and `B` fact packs and shaped outputs only
