# Flow Quality Assurance Execution Slice - Midlands Data Scientist Requirement

As of `2026-04-03`

Purpose:
- capture the current execution decision for one bounded data-quality ownership slice
- anchor that decision to the Midlands Partnership NHS Foundation Trust `Data Scientist` requirement around data quality, anomaly detection, reconciliation, fit-for-use assurance, and trusted analytical inputs
- keep the work narrow enough to produce fast, defensible outward-facing evidence without drifting into a broad platform-wide quality programme

Boundary:
- this note is not an accomplishment record
- this note is not a claim that platform-wide quality governance has already been implemented
- this note captures the chosen slice, why it fits the requirement, what lenses it uses, and what would count as done
- execution should work from governed data extracts or local bounded views rather than broad platform reruns

Placement rule:
- this file lives under the role-shaped lens tree because it is execution-depth material, not a top-level lens definition
- the role folder should hold multiple employer or role-execution lanes over time
- the employer folder should hold one folder per targeted responsibility slice so repeated work stays grouped and readable

Primary source basis:
- [03_data-quality-governance-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\03_data-quality-governance-analytics.md)
- [09_analytical-delivery-operating-discipline.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\09_analytical-delivery-operating-discipline.md)
- [01_operational-performance-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\01_operational-performance-analytics.md)
- [04_analytics-engineering-data-product.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\04_analytics-engineering-data-product.md)
- [data-analytics-engineering-science.ideal-candidate-profiles.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.ideal-candidate-profiles.md)
- [data-analytics-engineering-science.job-ads.evidence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.job-ads.evidence.md)

---

## 1. Requirement Being Targeted

The requirement being targeted here is the Midlands `Data Scientist` expectation around:
- data quality ownership
- anomaly and inconsistency detection
- reconciliation and assurance work
- improving dataset fitness for downstream analytics
- contributing to trusted modelling and reporting inputs rather than only consuming data passively

This note exists because that requirement is not asking for a generic data-cleaning statement. It is asking for proof that analytical work can detect defects, explain them, show why they matter, and embed the checks into a repeatable workflow so trust does not depend on ad hoc manual correction.

## 2. Lens Mapping For This Requirement

The primary owner lens for this requirement is:
- `03 - Data Quality, Governance, and Trusted Information Stewardship`

This is the core owner because the responsibility is fundamentally about:
- fit-for-use validation
- reconciliation of connected surfaces
- anomaly and inconsistency detection
- authoritative-source rules
- protecting downstream reporting and modelling trust

The main support lens is:
- `09 - Analytical Delivery Operating Discipline`

That support matters because data-quality ownership is weak if the checks are only run once. `09` makes the assurance layer reproducible, versioned, and stable enough to rerun.

The operational support lens is:
- `01 - Operational Performance Analytics`

That lens matters because a quality issue only becomes compelling evidence when it can be shown to distort a real downstream KPI or operating interpretation.

The optional support lens is:
- `04 - Analytics Engineering and Analytical Data Product`

That lens only enters if the root cause points to a structural flaw in the analytical layer that should be hardened for safer downstream use.

The practical split is:
- `03` owns the quality problem itself
- `01` shows why the problem matters to operational reading
- `09` makes the checks repeatable and part of the workflow
- `04` optionally hardens one structural view if the defect requires it

Ownership order:
- `03 -> 09 -> 01 -> 04`

Execution order:
- `03 -> 01 -> 09 -> 04`

That execution order is deliberate. The quality problem should be found first, its analytical impact should be demonstrated second, the checks should be made rerunnable third, and only then should a structural view be refactored if needed.

## 3. Chosen Bounded Slice

The bounded slice chosen for this requirement is:

`data-quality assurance over one governed flow-centric analytical path used for risk, cohort, and KPI interpretation`

The proof object is:

`flow_quality_assurance_v1`

This slice is preferred because it is small enough to execute quickly but still gives room to prove:
- anomaly detection
- reconciliation across connected surfaces
- fit-for-use judgement
- one concrete operational distortion
- one repeatable quality-control pack

The slice is defined as:
- `Base analytical unit`: `flow_id`
- `Governed path`: event -> flow -> case -> outcome
- `Primary downstream consumers`: flow-level risk/prioritisation work, cohort summaries, and KPI reporting
- `Deployment meaning for this slice`: not a platform-wide DQ service; instead, one bounded quality-assurance layer with checks, issue logging, source rules, rerun steps, and corrected interpretation surfaces

## 4. Why This Slice Was Chosen

This slice fits the requirement strongly because it gives direct room for:
- quality-scoping one governed analytical path
- detecting at least one real anomaly class rather than writing abstract controls
- reconciling inconsistencies across related surfaces
- showing how an issue changes a KPI or downstream interpretation
- documenting trusted-source and lineage rules
- making the checks part of a controlled workflow

Just as importantly, it avoids drift.

The intention is not to:
- audit the whole platform at once
- write a quality policy pack with no concrete defect pattern
- rerun the earlier modelling, product, or pathway slices under a new label
- turn this into a full redesign of the analytical preparation layer

The intention is to prove one sharper statement:
- I can own data quality inside a real analytical slice by finding a defect, reconciling it, explaining its impact, and embedding the control into repeatable analytical work

## 5. Execution Posture

The default execution stack for this slice is:
- `SQL` for source mapping, reconciliation, anomaly checks, before/after KPI comparisons, and any structural hardening view
- `Python` only where useful for a compact rerun wrapper or a small fact-pack generator
- notes and SQL-backed outputs as the main reproducibility surface

The execution substrate should be:
- governed local extracts
- bounded local views
- materialised quality-control outputs derived from the governed world

The default local working assumption is that execution can begin from a bounded run such as:
- `runs/local_full_run-7`

That should still be treated as:
- a bounded governed extract
- not the whole world
- not permission to overclaim platform-wide quality ownership

## 6. Lens-by-Lens Execution Checklist

### 6.1 Lens 03 - Data Quality, Governance, and Trusted Information Stewardship

1. Define the quality-critical slice:
- one bounded window
- one analytical grain: `flow_id`
- one governed path: event -> flow -> case -> outcome
2. Pin authoritative sources for event, flow, case, outcome, and any comparison-only fields.
3. Write source rules for which surface is allowed to define which KPI or downstream field.
4. Run fit-for-use checks for granularity, time boundary, completeness, and downstream suitability.
5. Build reconciliation checks across event-to-flow, flow-to-case, case-to-outcome, and KPI-total consistency.
6. Detect at least one real anomaly class:
- missing keys
- duplicate relationships
- inconsistent totals
- mismatched outcome logic
- broken consumer scope
7. Create one issue log with root-cause notes and severity.

### 6.2 Lens 01 - Operational Performance Analytics

1. Define a small KPI family only:
- suspicious-to-case conversion
- aged or open case burden
- case-to-outcome yield
- turnaround or timing lag
2. Test whether the quality issue changes one or more of those KPI readings.
3. Produce one raw-versus-corrected comparison.
4. Write one operational impact note stating which decision would have been distorted if the issue were ignored.

### 6.3 Lens 09 - Analytical Delivery Operating Discipline

1. Stabilise definitions for KPI meaning, cohort meaning if used, outcome meaning, and time scope.
2. Version the SQL quality checks, reconciliation logic, and source-rule notes.
3. Write rerun steps:
- required inputs
- required outputs
- pass/fail review points
4. Add drift-control notes for what should trigger re-review.
5. Package the whole quality workflow so another analyst could rerun it and understand the result.

### 6.4 Lens 04 - Analytics Engineering and Analytical Data Product

1. Only if the defect is structural, identify one friction point in the analytical layer.
2. Refactor one base or reporting view so the downstream consumer becomes safer.
3. Separate base logic from consumer logic if that reduces repeated ambiguity.
4. Write one lightweight product contract for the hardened view.

## 7. Real-Problem Standard For This Slice

This slice should not be treated as complete if it only produces generic checks.

The expected standard is:
- at least one concrete anomaly class is found
- the likely root cause can be explained
- one downstream KPI or interpretation changes because of the correction
- the quality logic can be rerun from versioned files

If no real defect pattern is found, the slice should not be stretched into a weak accomplishment. In that case the correct response would be to say the chosen path proved clean and then select a different bounded quality target.

## 8. Minimum Artifact Pack

The smallest useful proof pack for this requirement is:
- one fit-for-use note
- one reconciliation SQL pack
- one anomaly or exception SQL pack
- one KPI before/after comparison
- one issue log with root-cause notes
- one definitions, lineage, and source-rules note
- one README for rerunning the checks
- optionally one hardened base or reporting view

Suggested artefact names:
- `flow_quality_fit_for_use_v1.md`
- `flow_quality_reconciliation_v1.sql`
- `flow_quality_anomaly_checks_v1.sql`
- `flow_quality_kpi_before_after_v1.sql`
- `flow_quality_issue_log_v1.md`
- `flow_quality_source_rules_v1.md`
- `flow_quality_lineage_v1.md`
- `README_flow_quality_checks.md`
- `vw_flow_quality_base_v1.sql`
- `vw_flow_quality_reporting_ready_v1.sql`

## 9. Definition Of Done

This slice should be treated as complete only when all of the following are true:
- one bounded analytical slice has been quality-scoped
- authoritative sources are pinned
- critical joins are reconciled
- at least one real anomaly class has been detected and logged
- at least one KPI distortion has been shown and corrected
- stable definitions and source rules are written down
- the checks can be rerun from versioned logic
- at least one downstream analytical or reporting consumer is safer because of the fix

## 10. Truth Boundary

As of this note, the correct claim is:
- the slice has been selected
- the lens mapping is clear
- the proof object is distinct from the earlier slices
- the quality, reconciliation, and operational-impact posture are defined
- the execution path is defined

The correct claim is not:
- that a real anomaly class has already been found
- that discrepancy rates have already been reduced
- that the downstream consumer is already corrected
- that the full quality-governance requirement has already been exhausted across the platform
- that a platform-wide DQ monitoring framework has already been deployed

This note therefore exists to protect against overclaiming while preserving momentum toward a fast, defensible claim.

## 11. XYZ Claim Surfaces This Slice Is Aiming Toward

The strongest eventual claim shape for this slice is:

> Improved the trustworthiness of downstream fraud analytics and reporting, as measured by reducing reconciliation discrepancy from `[X]%` to `[Y]%`, validating `[N]` critical joins or KPI families, and identifying `[K]` anomaly classes that were distorting operational interpretation, by building a repeatable data-quality assurance layer over governed event, flow, case, and outcome data using reconciliations, fit-for-use checks, lineage rules, versioned SQL, and before-and-after KPI comparisons.

A shorter recruiter-readable version is:

> Improved analytical data quality and reporting trust, as measured by validated joins, reduced discrepancy rates, and repeatable quality checks over critical KPI views, by detecting anomalies, reconciling inconsistencies, documenting source and lineage rules, and embedding validation logic into controlled SQL-based workflows.

A closer direct-response version is:

> Strengthened dataset fitness for use and trusted modelling and reporting inputs, as measured by reconciliation accuracy, anomaly detection coverage, and reproducible rerun of quality controls, by treating data quality as part of the analytical job and building validation, monitoring, and root-cause checks directly into the workflow.

## 12. Immediate Next-Step Order

The correct build order remains:
1. `03` source rules, fit-for-use gate, reconciliation, and anomaly search
2. `01` before/after KPI comparison and operational impact note
3. `09` rerun pack, stable definitions, and drift-control notes
4. `04` optional hardening view if the defect is structural

That order matters because it keeps the slice centered on a real quality problem instead of turning it into generic documentation or unnecessary refactoring.
