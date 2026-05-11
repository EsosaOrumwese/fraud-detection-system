# Execution Plan - Fraud Strategy And Rule Optimisation Slice

As of `2026-04-14`

Purpose:
- turn the chosen `JPMorganChase` fraud-strategy slice into a concrete bounded execution order tied to the local governed fraud run
- keep the work SQL-first, threshold-first, and materialised in stages
- avoid broad exploratory loading or premature expansion into cloud-implementation rhetoric that belongs in later slices

Execution substrate:
- [local_full_run-7](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\runs\local_full_run-7)

Primary rule:
- query first
- pin one decision grain and one strategy question
- materialise bounded intermediate tables
- only pull small, already-shaped datasets into Python for comparison logic or light optimisation

---

## 1. Confirmed Working Assumptions

This plan is built around the following already-confirmed local facts:
- the fraud substrate exists in the bounded governed run:
  - `local_full_run-7`
- the local run contains the core surfaces needed for a bounded fraud-strategy first pass:
  - `s2_flow_anchor_baseline_6B`
  - `s4_flow_truth_labels_6B`
  - `s4_flow_bank_view_6B`
  - `s4_case_timeline_6B`
- the working analytical grain can stay at:
  - `flow_id`

Confirmed first-pass join posture:
- `flow_id` is the cross-surface join key

Confirmed first-pass truth posture:
- the strategy slice should treat `s4_flow_truth_labels_6B` as the authoritative downstream truth surface unless local profiling shows it is unusable

## 2. SQL-First Working Posture

This slice must not begin by loading whole governed fraud surfaces into Python memory.

The correct posture is:
- use SQL over the parquet-backed local surfaces
- inspect only schema, key coverage, prevalence, and bounded aggregates first
- materialise one strategy-ready base table in SQL
- materialise one ruleset or threshold comparison table in SQL
- only after that, export a small already-shaped table into Python if light comparison logic or threshold-search support is genuinely needed

This matters because the first proof burden is:
- fraud-strategy and rule optimisation

not:
- full-model experimentation
- full-decision-engine simulation
- broad exploratory modelling

## 3. First-Pass Strategic Objective

The first-pass objective is:

`build one bounded fraud-strategy comparison slice that shows how a preferred threshold or ruleset posture improves fraud-truth capture while keeping review burden explicit`

The first pass should therefore prefer:
- rule or threshold tuning over net-new model-family expansion
- governed detection-effectiveness comparisons over broad modelling breadth
- a decision-ready output that reads like first-line strategy work

If a stronger model is later needed, that belongs in a later refinement or in the implementation slice, not in the first pass here.

## 4. Candidate First-Pass Target And Burden Frame

The first target candidate should be:
- `s4_flow_truth_labels_6B.is_fraud_truth`

Reason:
- it is the cleanest authoritative downstream fraud-truth outcome currently confirmed locally
- it aligns directly with the role wording around effective fraud strategies and rules
- it avoids inventing a weaker proxy target too early

The first-pass burden frame should be:
- compare strategy postures on:
  - fraud-truth capture
  - review or control burden
  - bounded case-follow-up implications where visible

Secondary comparison surface:
- `s4_flow_bank_view_6B`

This should be used for:
- bank-view comparison
- trust and interpretation checks
- explaining where the preferred strategy posture differs from a weaker or broader gate

It should not displace the authoritative fraud-truth target unless local profiling shows that the truth surface is unusable.

## 5. First-Pass Feature And Comparison Family

The first-pass comparison family should stay narrow and low-risk:
- flow timestamp
- amount
- merchant identifier
- party identifier
- account identifier
- instrument identifier
- device identifier
- IP identifier
- arrival sequence
- bounded bank-view and case-follow-up indicators only where they do not leak future truth

Important constraint:
- no feature may depend on downstream truth fields as an input
- no feature may depend on post-outcome case events that would leak the target

That means the first pass should prefer:
- anchor-derived fields
- existing bounded risk or burden indicators
- simple pre-outcome structural features
- simple thresholdable or bandable measures

The first pass should avoid:
- complex event-sequence reconstruction
- downstream label-state content as an input feature
- a broad new feature factory

## 6. Bounded SQL Build Order

### Step 1. Create a thin profiling layer in SQL

Build small aggregate queries only for:
- target prevalence
- count of distinct `flow_id`
- count of `flow_id` with bank-view matches
- count of `flow_id` with case-follow-up matches
- min and max timestamp in the anchor table
- null or missingness checks for first-pass anchor fields

Goal:
- confirm strategy-slice viability without scanning into Python

### Step 2. Materialise a strategy-ready base table in SQL

Create one bounded SQL output, for example:
- `fraud_strategy_base_v1`

This table should include:
- `flow_id`
- anchor fields needed for bounded strategy comparisons
- authoritative fraud-truth target
- bank-view comparison fields
- time split marker derived from timestamp

This table should be:
- explicit
- documented
- reusable

### Step 3. Materialise a ruleset or threshold comparison table in SQL

Create one downstream-ready SQL output, for example:
- `fraud_ruleset_comparison_v1`

This table should be designed for:
- baseline versus preferred threshold comparisons
- capture versus burden comparisons
- stakeholder-facing strategy interpretation

It should make the strategy comparison explicit enough that the slice reads like:
- fraud-strategy optimisation

not merely:
- model scoring

### Step 4. Materialise an effectiveness table in SQL

Create one explicit effectiveness output, for example:
- `fraud_detection_effectiveness_v1`

This table should summarise:
- fraud-truth yield by strategy posture
- positive-outcome capture by strategy posture
- review-load or selection-share by strategy posture

### Step 5. Export only the bounded comparison slice

After SQL shaping is complete:
- export only the columns required for light threshold-search or light visual inspection
- keep Python working on the already-shaped strategy tables, not the raw governed surfaces

## 7. Split Strategy

The split strategy should be time-based, not random.

Reason:
- the slice needs to support a real first-line strategy claim
- time-based validation is closer to future decision use
- random splits are easier but less defensible in this role

First-pass split posture:
- earliest window: training or historical calibration
- middle window: validation
- latest bounded window: test or holdout

The exact date boundaries should be set only after a small SQL timestamp profile confirms coverage.

## 8. Strategy Comparison Posture

The first-pass strategy-comparison posture should stay minimal:
- one baseline ruleset or threshold posture
- one preferred challenger posture
- optionally one more conservative posture if it materially sharpens the trade-off

Recommended baseline:
- inherited broad gate or current broad selection posture from the governed fraud lane

Recommended challenger:
- a tighter threshold or more selective ruleset posture that improves positive-yield concentration

The point of the first pass is not strategy maximisation.

The point is to prove:
- a governed target
- a usable strategy-ready base
- a meaningful ruleset or threshold comparison
- a visible detection-versus-burden trade-off

## 9. Evaluation Strategy

The first-pass metric set should remain compact.

Primary metrics:
- fraud-truth yield under the preferred posture
- share of all positive outcomes captured under the preferred posture
- review-load or selection-share under the preferred posture

Secondary metrics:
- bank-view comparison delta
- concentration of positives in the preferred band or gate
- time-split stability across validation and test windows

Do not overbuild metrics in the first pass.
The output needs to be claimable and strategy-interpretable, not academically exhaustive.

## 10. Thresholds, Rulesets, And Trade-Off Reading

The first-pass output must produce:
- one baseline strategy posture
- one preferred strategy posture
- one explicit trade-off note

These should not be arbitrary threshold variants if the resulting comparison is meaningless.

Comparison rule:
- choose postures based on operational usefulness and yield separation
- document why the preferred posture is better
- document what burden remains or shifts

First-pass interpretation outputs should show:
- selected share under each posture
- fraud-truth yield under each posture
- share of all positives captured
- what happens to burden or review load

## 11. Planned Deliverables

SQL and shaped data:
- one profiling query pack
- one `fraud_strategy_base_v1` build query
- one `fraud_ruleset_comparison_v1` build query
- one `fraud_detection_effectiveness_v1` build query

Python or light comparison support:
- one bounded comparison notebook or script only if SQL alone is not enough

Documentation:
- fraud-strategy scope note
- strategy-ready base note
- ruleset-comparison note
- detection-effectiveness note
- trade-off note
- caveats note
- regeneration README

Expected output bundle for the first pass:
- reusable strategy-ready base
- one ruleset or threshold comparison surface
- one detection-effectiveness summary
- one short action-oriented strategy interpretation note

## 12. Execution Order

1. Finalise the folder structure for this responsibility lane.
2. Run SQL-only profiling queries over the local fraud surfaces.
3. Pin the exact target and time split.
4. Materialise the strategy-ready base in SQL.
5. Define the baseline and preferred strategy postures.
6. Materialise the ruleset or threshold comparison output.
7. Materialise the detection-effectiveness output.
8. Decide whether light Python support is still worth using.
9. Write the trade-off note and documentation pack.
10. Prepare the outward-facing execution report inputs.

## 13. Stop Conditions

Stop and reassess if any of the following happens:
- the fraud-truth target is too sparse for a bounded first-pass strategy comparison
- the required joins are not stable enough for a clean strategy-ready base
- the slice requires heavy raw event expansion before any ruleset comparison is meaningful
- the strategy question collapses into generic model-building rather than explicit rule optimisation

If one of those conditions occurs, the adaptation path is:
- keep the same responsibility lane
- narrow the slice further
- preserve the strategy and threshold comparison core
- defer broader model-building or implementation language

## 14. What This Plan Is And Is Not

This is:
- a concrete execution plan for the first `JPMorganChase` fraud-strategy slice
- SQL-first
- threshold-first
- bounded
- aligned to the actual scale constraint of the local governed run

This is not:
- the execution report
- a results note
- permission to start loading whole datasets into memory
- permission to broaden into cloud-native solution-delivery claims

The first operational move after this plan should be:
- SQL profiling queries only
