# Execution Plan - Flow Quality Assurance Slice

As of `2026-04-03`

Purpose:
- turn the chosen data-quality ownership slice into an execution order tied to the local governed run
- keep the work anomaly-first, SQL-first, and bounded
- prove one real data-quality problem, one measurable analytical impact, and one repeatable assurance workflow without drifting into platform-wide quality governance

Execution substrate:
- [`runs/local_full_run-7`](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\runs\local_full_run-7)

Primary rule:
- quality-scope one governed path first
- search for a real defect pattern before writing a large control pack
- prove the downstream KPI impact of the defect
- only then package the checks into a repeatable workflow

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- `flow_id` is the right analytical grain for the chosen quality-critical path
- the local governed run contains enough event, flow, case, and outcome surfaces to support reconciliation over one bounded path
- at least one meaningful anomaly class exists in the bounded slice, rather than every issue being trivial or purely hypothetical
- the downstream consumer family is narrow enough that raw-versus-corrected KPI comparison can be shown clearly

Candidate first-pass governed surfaces:
- `s2_event_stream_baseline_6B`
- `s2_flow_anchor_baseline_6B`
- `s4_case_timeline_6B`
- `s4_flow_truth_labels_6B`
- `s4_flow_bank_view_6B`

Working assumption about the quality-critical path:
- event surface provides entry-level activity and timing
- flow anchor provides the main analytical grain and context
- case timeline provides workflow progression and timing
- truth labels provide authoritative outcome
- bank-view fields provide comparison-only operational signals that must not silently override truth

Important warning:
- those assumptions must be tested rather than carried forward casually
- if the bounded path proves unusually clean and no real defect pattern is found, the slice should adapt early rather than forcing a weak accomplishment

## 2. SQL-First Working Posture

This slice must not begin as broad Python exploration.

The correct posture is:
- inspect source meaning and key fields in SQL first
- inspect join coverage and reconciliation risk in SQL first
- inspect KPI definitions and outcome-field conflicts in SQL first
- materialise anomaly and before/after comparison outputs in SQL
- use Python only for a compact rerun wrapper or a small fact-pack if needed after the governed evidence already exists

This matters because the responsibility is about data quality ownership inside analytical work, not notebook-led data inspection.

## 3. First-Pass Analytical Objective

The first-pass objective is:

`build one repeatable flow-quality assurance layer that finds at least one real defect pattern, shows how it distorts a downstream KPI or analytical reading, and preserves a corrected interpretation path`

The proof object is:
- `flow_quality_assurance_v1`

The first-pass output family is:
- one source-rules and fit-for-use pack
- one reconciliation pack
- one anomaly-check pack
- one raw-versus-corrected KPI comparison
- one issue log with root-cause notes
- one rerunnable quality-workflow pack
- optionally one hardened analytical view if the defect is structural

## 4. Early Quality Gate

Before claiming ownership of a quality problem, run a SQL-only gate to establish whether a real defect pattern exists.

The first profiling pass must answer:
- which fields and joins are quality-critical for the downstream risk, cohort, and KPI consumers?
- are there mismatches between authoritative truth and comparison-only fields?
- do linked surfaces produce dropped rows, duplicates, or contradictory counts?
- do raw KPI totals disagree across closely related outputs?
- is there one anomaly class strong enough to anchor the slice?

Required SQL checks:
- distinct `flow_id` counts by source
- event-to-flow coverage
- flow-to-case coverage
- case-to-outcome coverage
- null-rate checks for critical fields
- duplicate creation risk across the join chain
- raw KPI totals by split or window
- comparison of truth-driven versus comparison-surface-driven KPI readings

Decision rule:
- if at least one concrete anomaly class and one meaningful KPI distortion are found, proceed with the slice as planned
- if the path is clean, document that result briefly and switch to a different bounded quality target instead of stretching the evidence

## 5. Candidate Source Chain

The first-pass source chain should stay bounded and explicit.

Each source should have one stated contribution:
- `s2_event_stream_baseline_6B`
  - entry activity
  - event timing
  - upstream participation counts
- `s2_flow_anchor_baseline_6B`
  - canonical `flow_id`
  - flow context
  - anchor timestamps and dimensions
- `s4_case_timeline_6B`
  - case linkage
  - case states
  - pathway and timing fields
- `s4_flow_truth_labels_6B`
  - authoritative fraud truth and related outcome flags
- `s4_flow_bank_view_6B`
  - secondary operational comparison surface

Authoritative-source rule expected at plan stage:
- truth labels define authoritative fraud outcome
- bank view is comparison-only unless a specific KPI explicitly calls for that surface

That rule should be tested and, if needed, refined during the first quality gate.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. source profiling and source-rule pinning
2. fit-for-use gate
3. reconciliation checks across the governed path
4. anomaly and inconsistency detection
5. raw-versus-corrected KPI comparison
6. issue logging and root-cause capture
7. rerun-pack and drift-control documentation
8. optional hardening view if the defect is structural

The transformations should not be hidden in notebook cells or ad hoc local reshaping.

## 7. Bounded SQL Build Order

### Step 1. Create a source-rules and fit-for-use layer in SQL

Build small aggregate queries only for:
- distinct `flow_id` and `case_id` counts by source
- key coverage by source
- critical null checks
- timestamp boundary checks
- field-meaning comparison for outcome and KPI-driving fields

Goal:
- confirm the chosen path is appropriate for downstream risk, cohort, and KPI interpretation
- pin the initial authoritative-source rules before deeper checks begin

### Step 2. Build reconciliation checks across the path

Create one bounded SQL pack for:
- event-to-flow consistency
- flow-to-case consistency
- case-to-outcome consistency
- KPI-total consistency across related outputs

This pack should make it obvious whether the defect pattern is:
- a linkage defect
- a completeness defect
- a duplicate inflation defect
- an outcome-definition defect
- or a consumer-scope defect

### Step 3. Build anomaly and exception outputs

Create one bounded SQL output, for example:
- `flow_quality_anomaly_checks_v1`

This output should surface:
- missing keys
- duplicate relationships
- mismatched outcome logic
- broken consumer scope
- raw-versus-corrected row deltas by defect class

### Step 4. Build raw-versus-corrected KPI comparisons

Create one bounded SQL output, for example:
- `flow_quality_kpi_before_after_v1`

This output should compare a small KPI family only:
- suspicious-to-case conversion
- aged or open case burden
- case-to-outcome yield
- turnaround or lag if relevant to the anomaly

Decision rule:
- the comparison should show exactly how the detected issue would have distorted interpretation
- if the anomaly does not move a KPI or downstream reading materially, it is probably the wrong anchor for this slice

### Step 5. Export only the compact quality pack

After SQL shaping is complete:
- export the anomaly summaries
- export the before/after KPI comparisons
- export the fact pack and issue log inputs
- avoid dumping broad intermediate data unless needed for reproducibility

## 8. Anomaly Search Strategy

The anomaly search must stay concrete.

Preferred first-pass anomaly classes:
- missing or null keys on critical linkage paths
- duplicate case attachment to a flow where one-to-one behaviour is expected
- mismatched truth-versus-bank-view outcome interpretations
- inconsistent KPI totals across related reporting outputs
- broken scope where a reporting-ready surface excludes or double-counts part of the bounded population

Selection rule:
- choose the anomaly class that is both real and easiest to connect to a downstream interpretation error
- do not choose a defect only because it sounds severe if it does not materially affect analytical reading

## 9. KPI Impact Strategy

This slice needs a narrow, defensible KPI family because `01` is support, not the owner.

The first-pass KPI family should cover:
- suspicious-to-case conversion
- case-selected volume
- aged or open case burden
- case-to-outcome yield

The first-pass impact reading should answer:
- what was the raw KPI reading?
- what is the corrected trusted KPI reading?
- what decision or interpretation would have been wrong if the defect were ignored?

The intended result is one clear statement such as:
- a duplicate join inflated burden by `[X]%`
- a mismatched outcome surface overstated yield by `[Y]` points
- a broken scope understated conversion by `[Z]` points

## 10. Trust And Fit-For-Use Strategy

This slice needs an explicit trust pack because `03` is the owner lens.

The first-pass validation set should cover:
- grain correctness for `flow_id`
- completeness and linkage of critical fields
- authoritative-source rules for downstream KPIs
- consistency of totals across anomaly, KPI, and consumer outputs
- allowed-use and non-use notes for each outcome surface

The first-pass authoritative-source rules should pin:
- which source defines entry participation
- which source defines case linkage
- which source defines authoritative fraud outcome
- which source is comparison-only
- which fields should not be reused casually in KPI logic

## 11. Reproducibility Strategy

The slice is not complete unless the checks can be rerun by someone else.

The first-pass reproducibility pack should include:
- versioned SQL quality checks
- one compact rerun script only if needed
- one definitions note
- one source-rules note
- one lineage note
- one issue log
- one README with rerun steps and pass/fail review points
- one caveat note if the correction has scope boundaries

This should be strong enough that another analyst could:
- understand the defect
- rerun the checks
- verify the corrected KPI reading
- understand what the pack is and is not safe to claim

## 12. Planned Deliverables

SQL and shaped data:
- one source-profile and fit-for-use query pack
- one reconciliation query pack
- one anomaly-check query pack
- one KPI before/after comparison query pack
- optionally one hardened analytical base or reporting view

Documentation:
- source-rules note
- fit-for-use note
- lineage note
- issue log with root-cause and severity
- operational impact note
- definitions note
- rerun README
- caveat note
- optional product contract note for a hardened view

Expected output bundle for the first pass:
- one real anomaly class
- one corrected KPI comparison
- one repeatable quality workflow pack
- one issue log and root-cause summary
- one safer downstream analytical interpretation path

## 13. What To Measure For The Claim

For this requirement, the strongest measures are discrepancy reduction, validated joins, anomaly coverage, and rerun repeatability rather than model metrics.

Primary measure categories:
- reconciliation discrepancy before versus after
- number of critical joins or KPI families validated
- missing-key or mismatch rate
- number of anomaly classes detected and resolved
- rerun time for the quality pack
- difference between raw and corrected KPI readings

Secondary measure categories:
- one clearly documented root cause
- one completed source-rules and lineage pack
- one safer downstream consumer or reporting view

## 14. Execution Order

1. Finalise the folder structure for this responsibility lane.
2. Run SQL-only source profiling, fit-for-use, and authoritative-source checks.
3. Run SQL-only reconciliation and anomaly queries.
4. Select the strongest real anomaly class for the slice.
5. Build raw-versus-corrected KPI comparisons around that anomaly.
6. Capture issue log, source rules, lineage, and operational impact notes.
7. Package the rerun workflow and drift-control notes.
8. Apply one structural hardening view only if the defect requires it.
9. Write the execution report and claim surfaces only after the evidence is real.

## 15. Stop Conditions

Stop and reassess if any of the following happens:
- no real anomaly class is found in the bounded path
- the chosen defect does not materially change downstream interpretation
- the slice starts expanding into broad platform-wide quality review
- the structural fix becomes larger than a bounded analytical hardening task
- the evidence starts looking like generic checks rather than ownership of a real quality problem

If one of those happens, the adaptation path is:
- keep the same responsibility lane
- name the blocker clearly
- either narrow to a stronger anomaly or switch the bounded target path
- preserve the data-quality ownership center of gravity

## 16. What This Plan Is And Is Not

This is:
- a concrete execution plan for the fourth Midlands responsibility slice
- anomaly-first
- SQL-first
- bounded
- aligned to data quality ownership, operational impact, and repeatable assurance

This is not:
- the execution report
- a platform-wide DQ programme
- permission to write a large control pack before finding a real defect

The first operational move after this plan should be:
- SQL-only profiling and anomaly search over the bounded event -> flow -> case -> outcome path
