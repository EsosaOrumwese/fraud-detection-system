# Execution Plan - Population Pathway Analysis Slice

As of `2026-04-03`

Purpose:
- turn the chosen linked population and pathway slice into an execution order tied to the local governed run
- keep the work trust-first, SQL-first, and bounded
- prove population-level cohort and pathway analysis over linked governed data without drifting into another modelling-first or analytical-product-first slice

Execution substrate:
- [`runs/local_full_run-7`](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\runs\local_full_run-7)

Primary rule:
- define trusted source meaning first
- verify the join path before building analytical summaries
- materialise a bounded linked population base
- derive compact cohort, pathway, and KPI outputs from that base

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- `flow_id` is still the right base analytical unit for the linked population
- the local governed run contains the core event, flow, case, and outcome surfaces needed for a bounded pathway reading
- suspicious-flow population can be defined cleanly enough to support cohort and pathway summaries without a large event reconstruction programme
- the required joins can be validated with bounded reconciliation queries before any analytical interpretation begins

Candidate first-pass governed surfaces:
- `s2_risk_event_stream_6B` or closest event-level suspicious-behaviour surface available in the bounded run
- `s2_flow_anchor_baseline_6B`
- `s4_case_timeline_6B`
- `s4_flow_truth_labels_6B`
- `s4_flow_bank_view_6B`

Working assumption about the linked path:
- event surface provides suspicious-entry context
- `flow_id` anchors the population and links flow context to downstream case and outcome surfaces
- `case_id` provides progression and pathway timing
- truth and bank-view surfaces provide outcome comparison

Important warning:
- those assumptions must be tested rather than carried forward casually
- if the bounded event surface is too noisy or the suspicious-entry definition is not stable enough, the slice should adapt early rather than forcing a weak population story

## 2. SQL-First Working Posture

This slice must not begin as exploratory Python analysis.

The correct posture is:
- inspect source meaning and schema in SQL first
- inspect join keys and coverage in SQL first
- define the suspicious-flow population in SQL first
- materialise the linked population base in SQL
- derive cohort, pathway, and KPI outputs in SQL
- use Python only for lightweight summary shaping or figures after the governed analytical slice already exists

This matters because the responsibility is partly about linked-data understanding and governance discipline, not only about producing descriptive outputs.

## 3. First-Pass Analytical Objective

The first-pass objective is:

`build one trusted linked population-and-pathway slice that can compare a small number of cohorts, surface one operating problem, and preserve one canonical set of definitions across outputs`

The proof object is:
- `population_pathway_analysis_v1`

The first-pass output family is:
- one linked population base
- one reconciliation and fit-for-use pack
- one cohort-definition pack
- one pathway and KPI summary pack
- one operating interpretation note
- one reusable reporting-ready analytical pack

## 4. Early Trust Gate

Before building any cohort or pathway outputs, run a SQL-only trust gate.

The first profiling pass must answer:
- what exactly is the suspicious-flow population in the bounded governed slice?
- which event surface or equivalent suspicious-entry surface is authoritative enough to define the population?
- can event, flow, case, and outcome surfaces be linked cleanly through the chosen keys?
- do the joins create duplication, dropped rows, or conflicting field meaning?
- are the key outcome and timing fields complete enough for pathway interpretation?

Required SQL checks:
- distinct `flow_id` counts by candidate source
- suspicious-entry coverage by source
- event-to-flow linkage rates
- flow-to-case linkage rates
- case-to-outcome linkage rates
- null-rate and missing-key checks for critical fields
- duplicate creation risk across the proposed join chain

Decision rule:
- if the linked path and source meaning are stable enough, proceed with the bounded population definition
- if not, pause and adapt the suspicious-population definition before building the slice

## 5. Candidate Source Chain

The first-pass source chain should stay bounded and explicit.

Each source should have one stated contribution:
- suspicious-entry event surface
  - entry pressure
  - suspicious behaviour marker
  - event timing for population definition
- `s2_flow_anchor_baseline_6B`
  - flow context
  - amount
  - anchor timestamp
  - core entity identifiers
- `s4_case_timeline_6B`
  - case creation and progression
  - pathway timing
  - case-to-flow linkage
- `s4_flow_truth_labels_6B`
  - authoritative fraud truth
- `s4_flow_bank_view_6B`
  - secondary operational outcome comparison

If the local bounded run does not contain a clean suspicious-entry event surface, the plan should adapt by defining the population from the earliest trustworthy suspicious-state surface rather than pretending an event source exists.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. source profiling and authoritative-source pinning
2. suspicious-population definition
3. linked event-to-flow-to-case-to-outcome base
4. cohort derivation
5. pathway and KPI summarisation
6. operating-problem interpretation
7. reporting-ready packaging

The transformations should not be hidden in notebook cells or ad hoc local reshaping.

## 7. Bounded SQL Build Order

### Step 1. Create a profiling and vocabulary layer in SQL

Build small aggregate queries only for:
- suspicious-entry coverage
- distinct `flow_id` and `case_id` counts
- event-to-flow linkage
- flow-to-case linkage
- case-to-outcome linkage
- critical null and duplication checks
- source-level timestamp boundaries

Goal:
- define the suspicious-flow population honestly
- prove the linked path before any analytical interpretation starts

### Step 2. Materialise a trusted linked population base

Create one bounded SQL output, for example:
- `population_pathway_base_v1`

This output should include:
- `flow_id`
- suspicious-entry timing or earliest suspicious-state timing
- flow context fields
- case-creation and progression markers
- outcome fields
- trusted flags needed for cohort and KPI derivation

### Step 3. Materialise cohort-ready outputs

Create one bounded SQL output that assigns the compact cohort framework:
- `population_cohort_metrics_v1`

This output should support:
- high-burden vs low-burden comparison
- fast vs slow conversion comparison
- high-yield vs low-yield comparison
- outcome and turnaround differences by cohort

### Step 4. Materialise pathway and KPI outputs

Create compact SQL outputs for:
- suspicious-flow volume
- suspicious-to-case conversion
- case progression counts
- turnaround and delay measures
- outcome mix by cohort

Example outputs:
- `population_pathway_kpis_v1`
- `population_pathway_reporting_v1`

### Step 5. Export only the compact analytical pack

After SQL shaping is complete:
- export only the compact linked base and summary outputs needed for the report
- keep the analytical consumer small
- use it only to package one population-level comparison and one operating note

## 8. Cohort Strategy

The cohort framework must remain small, computable, and operationally interpretable.

Preferred first-pass cohort family:
- `fast_converting_high_yield`
- `slow_converting_high_yield`
- `high_burden_low_yield`
- `low_burden_low_yield`

Working derivation strategy:
- `conversion_speed` from suspicious-entry to case or outcome timing
- `burden` from case volume, aged progression, or lifecycle duration
- `yield` from authoritative truth outcome or case-to-outcome conversion

Decision rule:
- if the bounded data cannot support all three dimensions cleanly, simplify the cohort rules rather than forcing artificial segmentation

## 9. Pathway and KPI Strategy

This slice needs a small, stable KPI family because `01` is a main support lens.

The first-pass KPI family should cover:
- suspicious-flow volume
- suspicious-to-case conversion
- case progression distribution
- aged or slow-moving case burden
- outcome yield by cohort
- turnaround by cohort

The first-pass pathway reading should answer:
- where pressure enters
- which cohorts convert into case work most heavily
- where delay or burden accumulates
- where downstream value concentrates

## 10. Trust And Fit-For-Use Strategy

This slice needs an explicit governance pack because `03` is a co-owner lens.

The first-pass validation set should cover:
- suspicious-population definition correctness
- event-to-flow linkage consistency
- flow-to-case linkage consistency
- case-to-outcome linkage consistency
- missing-key rate for `flow_id` and `case_id`
- duplicate-row creation risk after linkage
- consistency of cohort totals across derived outputs

The first-pass authoritative-source rules should pin:
- which source defines suspicious entry
- which source defines flow context
- which source defines case chronology
- which source defines authoritative fraud truth
- which source is comparison-only and should not override truth

## 11. Reproducibility Strategy

The slice is not complete unless its definitions can be reused consistently.

The first-pass reproducibility pack should include:
- versioned SQL build logic
- one compact notebook or script only if needed for the summary layer
- documented source vocabulary and join rules
- one lineage and usage-boundary note
- one fit-for-use and reconciliation note
- one cohort-definition note
- one product contract for the reporting-ready outputs

This should be strong enough that another analyst could:
- understand the population definition
- rebuild the linked slice from the same governed run
- reproduce the cohort and KPI outputs
- understand what the slice is and is not safe to claim

## 12. Planned Deliverables

SQL and shaped data:
- one profiling and reconciliation query pack
- one linked population base build query
- one cohort-metrics build query
- one KPI and pathway summary build query
- one reporting-ready summary build query

Documentation:
- population-pathway vocabulary note
- trusted-source rules note
- fit-for-use and reconciliation note
- lineage and usage-boundary note
- cohort-rules note
- operating interpretation note
- product contract note

Expected output bundle for the first pass:
- trusted linked population base
- compact cohort pack
- compact pathway and KPI pack
- one operating problem statement
- one reusable reporting-ready analytical pack

## 13. What To Measure For The Claim

For this requirement, the strongest measures are linkage, trust, cohort differentiation, and pathway insight rather than model metrics.

Primary measure categories:
- number of governed surfaces linked into one reusable population view
- reconciliation success across key joins
- missing-key or dropped-row rates
- number of cohorts defined and compared consistently
- size of outcome-yield or turnaround difference across key cohorts
- one canonical set of KPI and cohort definitions reused across outputs

Secondary measure categories:
- one clearly identified operating problem
- one completed lineage and source-rules pack
- one reusable reporting-ready output derived from the same linked base

## 14. Execution Order

1. Finalise the folder structure for this responsibility lane.
2. Run SQL-only source profiling and trust-gate queries.
3. Decide the authoritative suspicious-population definition.
4. Materialise the linked population base.
5. Define and materialise the compact cohort framework.
6. Materialise pathway and KPI summaries.
7. Run fit-for-use and reconciliation checks.
8. Package lineage, vocabulary, source rules, and product contract notes.
9. Write one operating interpretation note.
10. Write the execution report and claim surfaces only after the evidence is real.

## 15. Stop Conditions

Stop and reassess if any of the following happens:
- the suspicious-population definition is not stable enough to support a bounded linked slice
- event-to-flow or flow-to-case linkage creates uncontrolled duplication
- outcome fields cannot be attached cleanly enough for cohort and pathway interpretation
- the cohort framework becomes too weak or too artificial for the bounded data
- the slice starts drifting into a broad modelling programme or another analytical-product build

If one of those happens, the adaptation path is:
- keep the same responsibility lane
- name the actual blocker clearly
- narrow the proof object if needed
- preserve the population, pathway, and governance centre of gravity

## 16. What This Plan Is And Is Not

This is:
- a concrete execution plan for the third Midlands responsibility slice
- trust-first
- SQL-first
- bounded
- aligned to linked population, cohort, pathway, and governance analysis

This is not:
- the execution report
- a modelling-first plan
- permission to assume the suspicious-population definition works without checking

The first operational move after this plan should be:
- SQL-only trust-gate profiling of the suspicious-entry surface and the linked event-to-flow-to-case-to-outcome path
