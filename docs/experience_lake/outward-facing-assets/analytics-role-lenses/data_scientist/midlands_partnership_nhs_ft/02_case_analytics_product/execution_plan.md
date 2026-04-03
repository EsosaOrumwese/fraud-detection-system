# Execution Plan - Case Analytics Product Slice

As of `2026-04-03`

Purpose:
- turn the chosen case-centric analytical-product slice into an execution order tied to the local governed run
- keep the work SQL-first, bounded, and materialised in stages
- prove analytical-product design, reproducibility, and trust before broadening into downstream analytical use

Execution substrate:
- [`runs/local_full_run-7`](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\runs\local_full_run-7)

Primary rule:
- query first
- verify the grain early
- materialise bounded intermediate products
- use Python only for light downstream consumer proof or compact validation helpers

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- `case_id` is the intended natural grain for this analytical-product slice
- the local governed run contains the core surfaces needed to build a case-centric product
- the necessary source relationships can be established without expanding into an unbounded event reconstruction exercise

Candidate first-pass governed surfaces:
- `s4_case_timeline_6B`
- `s4_flow_truth_labels_6B`
- `s4_flow_bank_view_6B`
- `s2_flow_anchor_baseline_6B`

Working assumption about join posture:
- `case_id` anchors chronology and case-level rollups
- `flow_id` provides the bridge between case chronology and flow-level context or outcome surfaces

Important warning:
- this assumption must be validated first
- if the local evidence shows that `case_id` is too noisy, duplicated, or incomplete for a stable product grain, the plan should adapt before any large build begins

## 2. SQL-First Working Posture

This slice must not begin by loading large parquet surfaces into Python memory.

The correct posture is:
- inspect case-grain viability in SQL first
- inspect source coverage, key relationships, and bounded aggregates first
- materialise the analytical base in SQL
- materialise the model-ready and reporting-ready outputs in SQL
- only after that, use a light analytical consumer to prove downstream usability

This matters because the slice is about analytical-product design and reproducible preparation, not about exploratory notebook work.

## 3. First-Pass Analytical Objective

The first-pass objective is:

`build a stable case-centric analytical preparation layer that can feed one model-ready consumer and one reporting-ready consumer from the same governed transformation chain`

The product contract is:
- `case_analytics_product_v1`: stable analytical base at intended case grain
- `case_model_ready_v1`: feature and target-ready case-level output for a bounded analytical consumer
- `case_reporting_ready_v1`: interpretable case-level or case-summary reporting output for downstream operational use

This is the core proof object for the requirement.

## 4. Early Grain-Verification Gate

Before building anything substantial, run a SQL-only grain-verification gate.

The first profiling pass must answer:
- does `case_id` behave as a stable intended grain in the candidate case surface?
- what is the case-to-flow cardinality?
- do multiple chronology rows per case collapse cleanly into one case-level record?
- can authoritative outcome truth be attached to case-level records through the chosen bridge?
- do the candidate joins create duplication or record loss that would undermine a stable product?

Required SQL checks:
- distinct `case_id` count by source
- chronology-row count per `case_id`
- distinct `flow_id` count per `case_id`
- case coverage for linked truth and bank-view surfaces
- null-rate and missing-key checks for critical join fields

Decision rule:
- if the case-grain checks are stable enough, proceed with `case_id` as planned
- if not, pause and adapt the slice before building the product chain

## 5. Candidate Source Chain

The first-pass source chain should stay bounded and explicit.

Each source should have one stated contribution:
- `s4_case_timeline_6B`
  - chronology, event timing, case activity sequence, case-to-flow bridge
- `s2_flow_anchor_baseline_6B`
  - flow context, amount, entity identifiers, anchor timestamp
- `s4_flow_truth_labels_6B`
  - authoritative downstream fraud truth
- `s4_flow_bank_view_6B`
  - secondary operational comparison surface

The source map should avoid unnecessary expansion into every possible governed surface.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. source profiling and key verification
2. case chronology rollup
3. case-to-flow linkage
4. flow context and outcome enrichment
5. stable case-grain analytical base
6. split into model-ready and reporting-ready downstream outputs

The transformations should not be hidden in notebook cells or one-off local manipulations.

## 7. Bounded SQL Build Order

### Step 1. Create a thin profiling layer in SQL

Build small aggregate queries only for:
- `case_id` distinct counts
- chronology rows per case
- flow linkage counts per case
- linked outcome coverage
- min and max timestamps
- missingness checks on join keys and downstream-critical fields

Goal:
- prove or reject the intended grain without dragging the whole slice forward blindly

### Step 2. Materialise a case chronology rollup

Create one bounded SQL output, for example:
- `case_chronology_rollup_v1`

This output should collapse chronology into case-level facts such as:
- first and last chronology timestamps
- chronology row counts
- distinct linked flows
- stable stage or event-summary fields where defensible

### Step 3. Materialise the analytical base

Create one bounded SQL output:
- `case_analytics_product_v1`

This should include:
- `case_id`
- chosen chronology summaries
- linked flow context aggregates
- outcome attachment
- reporting-safe dimensions
- a documented time marker for downstream split or partition use

### Step 4. Split into two downstream outputs

Create two downstream SQL outputs:
- `case_model_ready_v1`
- `case_reporting_ready_v1`

The split should be explicit:
- model-ready output carries features, target flags, and any split markers
- reporting-ready output carries interpretable fields, stage labels, summary fields, and consumer-facing dimensions

### Step 5. Export only the bounded consumer slice

After SQL shaping is complete:
- export only the fields needed for one light downstream consumer
- keep the consumer small
- use it only to prove the product feeds real analysis

## 8. Split Strategy

If the model-ready output needs a train/validation/test posture, the split should be time-based.

Reason:
- the slice still needs to support a real-delivery analytical story
- time-split logic is more defensible than random splitting for downstream reuse

The exact split boundary should be set only after the chronology and time-coverage profile is confirmed.

## 9. Trust And Fit-For-Use Strategy

This slice needs an explicit trust pack because `03` is one of the owner-support lenses.

The first-pass validation set should cover:
- missing-key rate for `case_id` and `flow_id`
- dropped-case rate across major joins
- duplicate-case creation risk after rollup and enrichment
- case-to-outcome coherence
- case-to-reporting-output coherence
- consistency of totals between analytical base and downstream outputs

The first-pass source authority rules should pin:
- which source defines chronology
- which source defines authoritative fraud truth
- which fields are safe for reporting use
- which fields are safe for model use
- which fields should not be reused casually without revalidation

## 10. Reproducibility Strategy

The product is not complete unless it is handover-safe.

The first-pass reproducibility pack should include:
- versioned SQL build logic
- one light downstream consumer script
- documented join keys and transformation rules
- one regeneration note
- one lineage and assumptions note
- one fit-for-use and reconciliation note

This should be strong enough that another analyst could:
- understand what the product is
- rebuild it from the same governed run
- know what downstream uses are supported
- know what caveats travel with it

## 11. Downstream Consumer Strategy

The downstream consumer remains intentionally light.

The goal is only to prove that `case_model_ready_v1` is analytically useful.

Acceptable first-pass consumers:
- a simple case-yield ranking
- a case-cohort segmentation summary
- a bounded prioritisation summary

Do not let this become:
- a second full modelling programme
- a large dashboard build
- an expansion that overwhelms the analytical-product responsibility itself

## 12. Planned Deliverables

SQL and shaped data:
- one profiling query pack
- one chronology-rollup build query
- one `case_analytics_product_v1` build query
- one `case_model_ready_v1` build query
- one `case_reporting_ready_v1` build query

Documentation:
- source map
- lineage note
- fit-for-use and reconciliation note
- regeneration guide
- one short downstream-consumer summary

Expected output bundle for the first pass:
- stable case-grain analytical base
- model-ready case output
- reporting-ready case output
- trust and reproducibility pack
- one light analytical consumer result

## 13. What To Measure For The Claim

For this requirement, the strongest measures are operability and trust rather than pure model quality.

Primary measure categories:
- reuse across model-ready and reporting-ready outputs
- reconciliation success across critical joins and totals
- documented critical joins and transformations
- reproducible regeneration from versioned logic
- one completed lineage and usage-boundary pack

Secondary measure categories:
- bounded regeneration runtime
- missing-key or dropped-record rates
- one successful downstream analytical consumer

## 14. Execution Order

1. Finalise the folder structure for this responsibility lane.
2. Run SQL-only case-grain verification queries.
3. Decide whether `case_id` remains the stable intended grain.
4. Materialise the chronology rollup.
5. Materialise the analytical base.
6. Materialise the model-ready and reporting-ready outputs.
7. Run fit-for-use and reconciliation checks.
8. Package lineage, assumptions, and regeneration notes.
9. Run one light downstream analytical consumer.
10. Write the execution report and claim surfaces only after the evidence is real.

## 15. Stop Conditions

Stop and reassess if any of the following happens:
- `case_id` does not behave as a stable product grain
- the chosen source chain creates uncontrolled duplication
- outcome truth cannot be attached cleanly enough for downstream use
- building the product would require unbounded event reconstruction
- the downstream consumer starts dragging the slice into a modelling-first programme

If one of those happens, the adaptation path is:
- keep the same responsibility lane
- name the actual blocker clearly
- narrow the proof object if needed
- preserve the analytical-product centre of gravity

## 16. What This Plan Is And Is Not

This is:
- a concrete execution plan for the second Midlands responsibility slice
- analytical-product first
- SQL-first
- bounded
- aligned to the scale constraint of the local governed run

This is not:
- the execution report
- a modelling-first plan
- permission to assume the case grain works without checking

The first operational move after this plan should be:
- SQL-only case-grain verification queries
