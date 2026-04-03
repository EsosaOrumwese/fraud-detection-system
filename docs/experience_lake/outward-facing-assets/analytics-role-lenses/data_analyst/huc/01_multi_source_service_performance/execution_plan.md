# Execution Plan - Multi-Source Service Performance Slice

As of `2026-04-03`

Purpose:
- turn the chosen HUC multi-source service-performance slice into a concrete execution order tied to the local governed run
- keep the work trust-first, SQL-first, and bounded to one service-line review pack
- prove multi-source operational integration, imperfect-data handling, KPI logic, and decision-support reporting without drifting into a broad dashboard estate or a model-led slice

Execution substrate:
- [`runs/local_full_run-7`](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\runs\local_full_run-7)
- governed local artefacts already available in `artefacts/analytics_slices/`

Primary rule:
- define trusted source meaning first
- verify the join path before building KPI logic
- materialise one merged service-performance base
- derive one compact KPI layer and one compact reporting pack from that base

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- the local governed run contains the four source families needed for the bounded HUC analogue:
  - event truth
  - flow or context truth
  - case chronology
  - outcome or label truth
- those sources can be linked cleanly enough to support one service-line reading without a large reconstruction programme
- one bounded current-versus-prior review window can be defined honestly from the available timestamps
- the resulting combined slice can support a small KPI family covering:
  - volume or pressure
  - conversion into case work
  - backlog or aging
  - outcome quality

Candidate first-pass governed surfaces:
- `s2_event_stream_baseline_6B` or the closest event-level suspicious-entry surface available
- `s2_flow_anchor_baseline_6B`
- `s4_case_timeline_6B`
- `s4_flow_truth_labels_6B`
- optionally `s4_flow_bank_view_6B` where a comparison-only operational surface is needed for discrepancy reading

Working assumption about the unified service-line question:
- the slice will compare a current operational window to one prior window
- the main reading will be workflow pressure and conversion into case work
- backlog or aging pressure and outcome quality will explain what changed rather than being treated as separate programmes

Important warning:
- those assumptions must be tested rather than carried forward casually
- if the source chain or current-versus-prior window does not behave cleanly enough, the slice should adapt early rather than forcing a weak service-performance story

## 2. SQL-First Working Posture

This slice must not begin as exploratory Python analysis.

The correct posture is:
- inspect source meaning and schema in SQL first
- inspect join keys and coverage in SQL first
- define the bounded review window in SQL first
- materialise the merged service-performance base in SQL
- derive KPI and discrepancy outputs in SQL
- use Python only for compact summary shaping, tables, and figures after the governed slice already exists

This matters because the HUC requirement is partly about working confidently with imperfect operational data, not only about producing charts after the fact.

## 3. First-Pass Objective

The first-pass objective is:

`build one trusted multi-source service-performance slice that can compare a current period to a prior period, identify one operational problem, and package the result into a compact service-line reporting pack`

The proof object is:
- `multi_source_service_performance_v1`

The first-pass output family is:
- one source map and source-rule pack
- one reconciliation and discrepancy pack
- one merged service-performance base
- one KPI layer
- one compact three-page reporting pack
- one executive brief
- one operational action note

## 4. Early Trust Gate

Before building any KPI or reporting outputs, run a SQL-only trust gate.

The first profiling pass must answer:
- what exactly are the four operational surfaces being combined?
- what grain does each source live at?
- which keys are trustworthy for joining them?
- do the joins create duplication, dropped rows, or conflicting field meaning?
- are the timestamps sufficient to create a current-versus-prior comparison window?
- which source should be authoritative for each KPI family?

Required SQL checks:
- distinct key counts by source
- key availability rates
- event-to-flow linkage rates
- flow-to-case linkage rates
- case-to-outcome linkage rates
- null-rate checks for critical fields
- duplicate-row creation risk across the proposed join path
- timestamp boundary and window-coverage checks

Decision rule:
- if the linked path and source meaning are stable enough, proceed with the bounded service-line base
- if not, adapt the service-line question or simplify the source chain before building KPI outputs

## 5. Candidate Source Chain

The first-pass source chain should stay bounded and explicit.

Each source should have one stated contribution:
- event surface
  - incoming suspicious or workflow-entry pressure
  - event timing
  - first operational signal for the slice
- `s2_flow_anchor_baseline_6B`
  - flow context
  - amount
  - anchor timestamp
  - compact segment dimensions
- `s4_case_timeline_6B`
  - case creation and progression
  - open and aged burden
  - conversion into case work
- `s4_flow_truth_labels_6B`
  - authoritative outcome quality or fraud-truth signal
- `s4_flow_bank_view_6B` only if needed
  - comparison-only operational reading
  - discrepancy interpretation, not KPI authority

If the bounded run does not support one of those surfaces cleanly, the plan should adapt by keeping the same service-line question but narrowing the comparison rather than inventing weak joins.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. source profiling and authoritative-source pinning
2. current-versus-prior review-window definition
3. merged event-to-flow-to-case-to-outcome service-performance base
4. KPI derivation
5. discrepancy and anomaly derivation
6. reporting-pack composition
7. audience-brief packaging

The transformations should not be hidden in notebook cells or ad hoc local reshaping.

## 7. Bounded SQL Build Order

### Step 1. Create a source map and profiling layer

Build small aggregate queries only for:
- distinct key counts
- linkage coverage across the candidate chain
- key null rates
- duplicate risk
- timestamp range and review-window coverage
- candidate segment availability

Goal:
- define the service-line review pack honestly
- prove the source chain before any KPI interpretation starts

### Step 2. Materialise a merged service-performance base

Create one bounded SQL output, for example:
- `service_line_performance_base_v1`

This output should include:
- review-window role such as `current` or `prior`
- bounded time grouping field such as day or week
- `flow_id`
- compact segment field such as campaign, cohort, or pathway slice
- case-open and aged-burden flags
- authoritative outcome field
- source-trust flags needed for discrepancy reading

### Step 3. Materialise KPI outputs

Create one bounded SQL output for the shared KPI layer:
- `service_line_kpis_v1`

This output should support the four KPI families only:
- volume or pressure
- suspicious-to-case conversion
- open or aged case burden
- case-to-outcome yield

The KPI output should support:
- current-versus-prior comparison
- one segment comparison
- one anomaly comparison where useful

### Step 4. Materialise discrepancy outputs

Create one bounded SQL output or query pack for:
- linkage discrepancies
- scope inconsistencies
- missing-key issues
- mismatched counts across related views
- any comparison-only versus authoritative-surface disagreement that affects KPI trust

This is important because the slice must show confidence with imperfect data rather than only consuming a merged base passively.

## 8. KPI Strategy

The KPI family must remain small and stable.

The first-pass KPI set should cover:
- suspicious-event or workflow-entry volume
- suspicious-to-case conversion
- open or aged case count
- case-to-outcome yield

The first-pass service-line reading should answer:
- is pressure up or down in the current window?
- is conversion into case work changing?
- is backlog or aging pressure accumulating?
- is outcome quality improving or deteriorating?
- which segment or period appears to be driving the shift?

Decision rule:
- every KPI must support the current-versus-prior service-line question
- if a metric does not help answer that question, drop it

## 9. Discrepancy and Fit-For-Use Strategy

This slice needs an explicit discrepancy pack because `03` is strong support, not a side note.

The first-pass validation set should cover:
- key availability
- event-to-flow linkage consistency
- flow-to-case linkage consistency
- case-to-outcome linkage consistency
- duplicate-row creation risk after joins
- current-versus-prior scope consistency
- KPI sensitivity to unresolved discrepancies

The discrepancy log should record:
- issue
- likely cause
- affected KPI
- severity
- immediate action

The authoritative-source rules should pin:
- which source defines pressure or entry activity
- which source defines conversion into case work
- which source defines open or aged burden
- which source defines authoritative outcome quality
- which source is comparison-only and must not override the authoritative KPI reading

## 10. Reporting-Pack Strategy

Once the source chain and KPI layer are stable, package the slice into one compact `3`-page reporting pack.

### Page 1. Executive overview

This page should answer:
- what changed?
- which KPI moved materially?
- what is the single issue leadership should know first?

Required components:
- headline KPIs
- current-versus-prior trend direction
- one short issue summary

### Page 2. Workflow health

This page should answer:
- is workflow pressure rising?
- is conversion holding?
- is backlog or aging worsening?

Required components:
- conversion view
- backlog or aging view
- one anomaly or discrepancy comparison

### Page 3. Drill-through or detail

This page should answer:
- which segment or slice is driving the issue?
- what discrepancy caveat matters?
- what should the reader conclude from the combined view?

Required components:
- segment comparison
- discrepancy note
- short interpretation note

Create:
- `service_line_reporting_pack_v1`
- `service_line_kpi_definitions_v1.md`
- `service_line_page_notes_v1.md`

## 11. Audience-Translation Strategy

The reporting pack is not complete unless it can travel without oral explanation.

Create:
- `service_line_exec_brief_v1.md`
- `service_line_action_note_v1.md`
- `service_line_challenge_response_v1.md`

The executive brief should answer:
- what changed
- why it matters
- what leadership should monitor next

The action note should answer:
- which segment or period needs attention
- what the likely issue is
- what follow-up is justified

The challenge-response note should answer:
- why trust this number?
- what does the KPI include?
- what discrepancy caveat applies?
- what should not be overread from the slice?

## 12. Reproducibility Strategy

This slice is not complete unless its logic can be reused consistently.

The first-pass reproducibility pack should include:
- versioned SQL build logic
- one compact Python script only if needed for the reporting-pack render
- documented source vocabulary and join rules
- one fit-for-use and discrepancy note
- one KPI definitions note
- one product contract for the reporting pack

That should be strong enough that another analyst could:
- understand the source chain
- rebuild the merged slice
- reproduce the KPI layer
- understand what the pack is and is not safe to claim

## 13. Planned Deliverables

SQL and shaped data:
- one source profiling and reconciliation query pack
- one merged service-performance base build query
- one KPI build query
- one discrepancy or anomaly query pack
- one reporting-ready summary build query

Documentation:
- source map
- authoritative-source rules note
- discrepancy log
- join-lineage note
- KPI definitions note
- page notes
- executive brief
- action note
- challenge-response note

Expected output bundle for the first pass:
- trusted merged service-performance base
- compact KPI pack
- discrepancy and anomaly pack
- one identified service-line problem statement
- one compact service-line reporting pack

## 14. What To Measure For The Claim

For this requirement, the strongest measures are integration, discrepancy control, KPI consistency, and reporting usability rather than advanced-model metrics.

Primary measure categories:
- number of operational sources integrated into one analytical slice
- reconciliation success across key joins
- missing-key or dropped-row rates
- number of KPI families defined and reused consistently
- number of discrepancy classes identified and investigated
- number of audience-specific outputs produced

Secondary measure categories:
- one clearly identified operational problem
- one completed source-rules and discrepancy pack
- one reusable reporting-ready output derived from the same merged base

## 15. Execution Order

1. Finalise the folder structure for this HUC responsibility lane.
2. Run SQL-only source profiling and trust-gate queries.
3. Decide the authoritative source rule for each KPI family.
4. Define the current-versus-prior review windows.
5. Materialise the merged service-performance base.
6. Materialise KPI outputs.
7. Materialise discrepancy outputs.
8. Package the three-page reporting pack.
9. Write the executive, action, and challenge-response notes.
10. Write the execution report and claim surfaces only after the evidence is real.

## 16. Stop Conditions

Stop and reassess if any of the following happens:
- one of the four source families is not stable enough to support the merged slice
- the join path creates uncontrolled duplication
- the current-versus-prior comparison window is too weak or too artificial
- the KPI family becomes too large or too diffuse for one service-line question
- the slice starts drifting into a broad reporting estate or a model-led programme

If one of those happens, the adaptation path is:
- keep the same responsibility lane
- name the actual blocker clearly
- narrow the service-line question if needed
- preserve the multi-source, imperfect-data, service-performance center of gravity

## 17. What This Plan Is And Is Not

This is:
- a concrete execution plan for the first HUC responsibility slice
- trust-first
- SQL-first
- bounded
- aligned to multi-source operational integration, KPI reading, discrepancy handling, and reporting output

This is not:
- the execution report
- a broad BI programme
- a generic data quality exercise without an operational question
- permission to assume the source chain works without checking

The first operational move after this plan should be:
- run the SQL-only source-profiling and reconciliation gate and decide whether the planned service-line question is fully supportable on the bounded governed surfaces
