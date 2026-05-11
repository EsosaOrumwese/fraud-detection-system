# Conversion Discrepancy Handling Execution Slice - HUC Data Analyst Requirement

As of `2026-04-03`

Purpose:
- capture the chosen bounded slice for the HUC requirement around anomaly detection and discrepancy handling
- keep the note aligned to the actual HUC responsibility rather than drifting into generic data quality work, generic KPI reporting, or a broad quality programme
- preserve the distinction between this slice and the earlier HUC slices by making this one about one concrete reporting-view discrepancy taken through detection, investigation, correction, and repeatable control

Boundary:
- this note is not an accomplishment record
- this note is not a claim that a broad anomaly-management programme has already been implemented
- this note captures the chosen slice, why it fits the requirement, which lenses own it, and what the proof burden should be
- execution should work from governed reporting-ready outputs and bounded local analytical views rather than broad platform reruns

Placement rule:
- this file lives under the role-shaped lens tree because it is execution-depth material, not a top-level lens definition
- the role folder should hold multiple employer lanes over time
- the employer folder should hold one folder per targeted responsibility slice so repeated work stays grouped and readable

Primary source basis:
- [03_data-quality-governance-trusted-information-stewardship.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\03_data-quality-governance-trusted-information-stewardship.md)
- [01_operational-performance-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\01_operational-performance-analytics.md)
- [02_bi-insight-reporting-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\02_bi-insight-reporting-analytics.md)
- [09_analytical-delivery-operating-discipline.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\09_analytical-delivery-operating-discipline.md)
- [data-analytics-engineering-science.ideal-candidate-profiles.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.ideal-candidate-profiles.md)
- [data-analytics-engineering-science.job-ads.evidence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.job-ads.evidence.md)

---

## 1. Requirement Being Targeted

The requirement being targeted here is the HUC `Data Analyst` expectation around:
- noticing when reported outputs do not align
- investigating anomalies rather than accepting the numbers at face value
- assisting with discrepancy resolution
- protecting reporting quality and decision-making when multiple sources or views disagree

This maps directly to the HUC candidate-profile requirement that the analyst should be able to describe:
- spotting when something looks wrong
- investigating why it is wrong
- working through the source path rather than only reporting the anomaly
- resolving or controlling the discrepancy before it damages reporting quality or decision use

This note exists because that requirement is broad enough to produce drift if attacked as a whole quality programme, but narrow enough to support one bounded proof slice that can later become a truthful `X by Y by Z` claim.

## 2. Lens Stack For This Requirement

The cleanest lens stack for this HUC `3D` requirement is:

**Primary**
- `03 - Data Quality, Governance, and Trusted Information Stewardship`

**Strong support**
- `01 - Operational Performance Analytics`

**Secondary support**
- `02 - BI, Insight, and Reporting Analytics`

**Delivery-control support**
- `09 - Analytical Delivery Operating Discipline`

Why this stack fits:

`03` is the main owner because the HUC profile says the analyst should not accept source data at face value, but should notice when something looks wrong, investigate why, and work with others to resolve it before it damages reporting quality or decision-making. The HUC job ad itself says the role must:
- highlight and investigate anomalies
- assist with resolving discrepancies
- identify where outputs from multiple sources do not align

That is directly `03` territory:
- validation
- reconciliation
- anomaly detection
- fit-for-use checks
- source logic
- protecting reporting trust

`01` is the next lens because the anomaly here is not meant to stay an abstract data-quality defect. It matters because it distorts operational performance interpretation. `01` owns:
- KPI logic
- workflow diagnosis
- throughput, backlog, and outcome tracking
- anomaly investigation
- explaining what changed and why it matters

`02` comes after that because once the anomaly is identified and understood, it still has to be surfaced properly. `02` owns:
- anomaly drill-through pages
- exception and trend reporting
- summary-pack communication
- keeping KPI and report logic understandable and consistent for stakeholders

`09` is the fourth lens because anomaly handling should not remain a one-off heroic investigation. `09` owns:
- stable KPI definitions
- versioned SQL or check logic
- regeneration
- handover
- preventing drift

So the practical reading is:
- `03` detects, reconciles, validates, and root-causes
- `01` shows the operational impact of the anomaly
- `02` packages the issue into usable reporting and explanation
- `09` makes the anomaly-handling workflow stable and repeatable

Ownership order:
- `03 -> 01 -> 02 -> 09`

Best execution order:
- `03 -> 01 -> 02 -> 09`

That execution order matters because this work naturally starts with trust and reconciliation, then moves to operational impact, then to reporting visibility, and finally to repeatable control.

## 3. Chosen Bounded Slice

The cleanest bounded slice for this HUC requirement is:

`one anomaly-to-resolution cycle on a single recurring service-line KPI pack`

Use one narrow problem only:

`a suspicious-to-case conversion discrepancy across two linked reporting views over one weekly reporting window`

Why this slice works:
- the HUC profile says the candidate should notice when something looks wrong, investigate why, and work to resolve it before it damages reporting quality or decision-making
- the HUC job ad explicitly says the role should highlight and investigate anomalies, assist in resolving discrepancies, and identify where outputs from multiple data sources do not align
- `03` is built for validation, reconciliation, anomaly detection, trust, and defensible reporting
- `01` is built for showing how the anomaly affects operational performance
- `02` is built for surfacing the issue clearly in reporting
- `09` is built for making the checks repeatable rather than one-off

This slice should produce:
- one source and lineage map for the discrepant KPI
- one reconciliation layer
- one issue log
- one corrected KPI comparison
- one compact exception pack
- one rerun-control layer for catching the same issue next cycle

## 4. Why This Slice Was Chosen

This slice was chosen because it gives direct room for:
- spotting one concrete bad pattern rather than describing anomaly handling abstractly
- tracing the discrepancy through the reporting-view path
- identifying a likely root cause
- correcting or controlling the reporting logic
- protecting both reporting quality and operational interpretation

It also avoids the wrong kinds of drift.

The intention is not to:
- build a broad quality programme
- repeat the HUC source-integration slice as another general trust exercise
- document a known semantic caveat without a fresh reporting-control angle
- produce many anomaly types at once
- turn anomaly handling into a generic issue register with no corrected reporting output

The intention is to prove one sharper statement:
- I can spot a reporting anomaly, investigate it through the source and view path, quantify its impact, correct or control it, and embed the fix into the recurring reporting workflow

## 5. Refinement On The Anomaly Choice

This refinement matters.

The anomaly needs to be a real reporting-view control issue, not only a semantic distinction that was already intentionally documented elsewhere.

That means:
- the compared views should be two linked reporting surfaces that would plausibly be expected to agree on suspicious-to-case conversion
- the discrepancy should read as a control failure or reporting inconsistency
- the slice should show why the mismatch would mislead a reporting consumer if left unresolved

So even if this slice reuses governed views from earlier HUC work, the proof burden is different:
- not “these two sources mean different things”
- but “these two reporting views should line up for this KPI, and they did not, so the anomaly had to be investigated and controlled”

## 6. Execution Posture

The default execution stack for this slice is:
- SQL for the discrepancy comparison, reconciliation logic, corrected KPI view, and compact exception outputs
- markdown for the source map, issue log, operational impact note, drill-through explanation, and rerun-control notes
- Python only where useful for rendering the compact anomaly pack after the discrepancy logic is already stable

The execution substrate should be:
- governed reporting-ready outputs
- bounded service-line views
- compact anomaly and exception surfaces derived from the governed world

The default local working assumption is that execution can begin from:
- the reporting-ready HUC pack outputs already created in slices `01` and `02`
- or bounded reporting views adjacent to them

That should still be treated as:
- one bounded anomaly-to-resolution cycle
- not a broad reporting-governance programme
- not permission to rerun or reload the full service-line base without reason

## 7. Lens-by-Lens Execution Checklist

### 7.1 Lens 03 - Detect, validate, and root-cause the discrepancy

This is the core owner. `03` explicitly owns fit-for-use checks, reconciliation, anomaly identification, reporting trust, source rules, and issue logs for suspicious discrepancies.

Tasks:
1. Choose one KPI anomaly:
- use one KPI only:
  - suspicious-to-case conversion
- compare the KPI across two linked views that should agree
2. Map the source path:
- identify the event source
- identify the flow source
- identify the case source
- write down the intended join path and authoritative source for the KPI
3. Run reconciliation checks:
- missing keys
- duplicate relationships
- unmatched rows after joins
- scope inconsistencies between the two views
4. Quantify the discrepancy:
- raw KPI in view A
- raw KPI in view B
- absolute and percentage gap
5. Investigate likely causes:
- join error
- missing or duplicated rows
- wrong scope or window
- wrong authoritative source
- inconsistent numerator or denominator logic
6. Write one issue log:
- anomaly description
- affected KPI or report
- likely root cause
- severity
- immediate corrective action
- long-term control

### 7.2 Lens 01 - Show why the anomaly matters operationally

`01` owns KPI logic, workflow diagnosis, anomaly investigation, and operational interpretation. It is the lens that turns bad data into bad operational understanding.

Tasks:
1. Build one before-and-after KPI comparison:
- conversion as originally reported
- corrected conversion after reconciliation
2. Check linked workflow signals:
- case creation count
- open or aged case count
- outcome yield
- one supporting timing or backlog signal only if needed
3. Write one operational impact note:
- what the discrepancy would have made people believe
- whether it suggested false pressure, false improvement, or false deterioration
- what operational attention might have been misdirected
4. Write one intervention note:
- what should now be monitored
- which segment or period deserves attention after the correction

### 7.3 Lens 02 - Surface the issue in reporting, not just in SQL

`02` owns reporting design, anomaly drill-through, exception reporting, KPI definition sheets, and packaging insight so stakeholders can use it.

Keep this to one compact anomaly pack with `2` pages only.

**Page 1 - Exception summary**
- corrected KPI versus original KPI
- discrepancy magnitude
- short issue summary
- status:
  - open
  - investigated
  - resolved

**Page 2 - Drill-through and explanation**
- where the discrepancy came from
- which dimension or segment was affected
- what changed after correction
- what the corrected interpretation is

Tasks:
1. Define the KPI wording clearly.
2. Add one `why this changed` note.
3. Add one drill-through table or filtered summary.
4. Make the pack readable without oral explanation.
5. Keep the same KPI definition consistent across the pack.

### 7.4 Lens 09 - Make anomaly handling part of the reporting workflow

`09` is what turns this from a one-time investigation into owned, repeatable control.

Tasks:
1. Stabilise the KPI definition:
- numerator
- denominator
- period or window
- authoritative source
- allowed exclusions
2. Version the logic:
- reconciliation SQL
- KPI SQL
- report-pack logic
- any notebook or scripted check
3. Create one rerun checklist:
- what to run before releasing the report
- what discrepancy thresholds trigger review
- what outputs must be checked each cycle
4. Document caveats:
- what the KPI is meant to answer
- what it should not be used for
- what kinds of source changes would invalidate comparability
5. Add one changelog:
- what changed in the KPI or report logic
- whether earlier periods remain comparable

## 8. Suggested Artifact Pack

The minimum credible proof pack for this slice is:
- one source map
- one reconciliation SQL pack
- one issue log
- one before-and-after KPI comparison
- one `2`-page exception or drill-through pack
- one KPI definition note
- one rerun checklist
- one changelog or caveat note

That is enough to prove:
- the analyst did not accept source data at face value
- the anomaly was investigated
- the discrepancy was traced to a cause
- reporting quality was protected
- the fix was embedded into the workflow

## 9. Suggested Artifact Names

These names are placeholders, not fixed schema requirements.

Trust and discrepancy assets:
- `conversion_discrepancy_source_map_v1.md`
- `conversion_discrepancy_reconciliation_v1.sql`
- `conversion_discrepancy_issue_log_v1.md`
- `conversion_discrepancy_source_rules_v1.md`
- `conversion_discrepancy_lineage_v1.md`

Operational-impact assets:
- `conversion_before_after_kpi_v1.sql`
- `conversion_operational_impact_v1.md`
- `conversion_intervention_note_v1.md`

Reporting assets:
- `conversion_exception_pack_v1`
- `conversion_kpi_definition_note_v1.md`
- `conversion_drillthrough_note_v1.md`

Control assets:
- `README_conversion_anomaly_checks.md`
- `conversion_report_run_checklist_v1.md`
- `conversion_reporting_caveats_v1.md`
- `CHANGELOG_conversion_reporting.md`

## 10. Definition Of Done

This slice should be treated as complete only when all of the following are true:
- one KPI anomaly has been detected and quantified
- the join and source path is documented
- the likely root cause is recorded
- one corrected KPI view exists
- one operational impact note exists
- one exception or drill-through pack exists
- one rerun checklist exists
- the same issue would be caught earlier next cycle

## 11. Truth Boundary

As of this note, the correct claim is:
- the slice has been selected
- the lens mapping is clear
- the execution path is defined
- the anomaly-to-resolution proof burden has been bounded

The correct claim is not:
- that the discrepancy has already been resolved
- that a broad anomaly-detection programme has already been built
- that every reporting discrepancy has already been brought under control
- that the service-line reporting lane is now anomaly-free

This note therefore exists to protect against overclaiming while still preserving momentum toward a fast, defensible claim.

## 12. What To Measure For The Eventual `Y`

For this requirement, the strongest `Y` values are:
- discrepancy size:
  - raw versus corrected KPI gap
- reconciliation rate:
  - discrepancy reduced from `[X]%` to `[Y]%`
- coverage:
  - number of checks added to the reporting workflow
- timeliness:
  - rerun or review completed in `[T]` minutes
- control effect:
  - number of future reports covered by the new control
- decision protection:
  - one false operational interpretation prevented or corrected

A good small `Y` set is:
- discrepancy reduced from `[X]%` to `[Y]%`
- `[N]` reconciliation or validation checks added
- exception pack regenerated in `[T]` minutes
- one recurring KPI or report now released only after quality-review steps

## 13. XYZ Claim Surfaces This Slice Is Aiming Toward

This section is included here because the slice definition needs to preserve the exact claim shape the execution is aiming toward, not just the structural checklist.

### 13.1 Full flagship `X by Y by Z` version

> Improved reporting trust and protected operational decision-making, as measured by reducing a suspicious-to-case conversion discrepancy from `[X]%` to `[Y]%`, adding `[N]` repeatable reconciliation checks, and regenerating the corrected exception pack in `[T]` minutes, by tracing a multi-source KPI mismatch across governed event, flow, and case views, identifying the root cause, correcting the KPI logic, and embedding the anomaly checks into the recurring reporting workflow.

### 13.2 Shorter recruiter-readable version

> Improved reporting accuracy and discrepancy handling, as measured by reduced KPI mismatch rates and repeatable anomaly checks across recurring reports, by investigating unexpected performance anomalies, reconciling multi-source views, correcting KPI logic, and packaging the findings into drill-through and exception reporting outputs.

### 13.3 Closest direct response to HUC `3D`

> Strengthened anomaly detection and discrepancy handling in operational reporting, as measured by validated source consistency, corrected KPI outputs, and introduction of repeatable quality checks, by spotting when reported views did not align, investigating the cause, resolving the issue, and preventing it from undermining reporting quality or decision-making.

## 14. Immediate Next-Step Order

The correct build order remains:
1. `03` source map, reconciliation, discrepancy quantification, and issue-log layer
2. `01` before-and-after KPI and operational-impact layer
3. `02` compact exception-pack layer
4. `09` rerun checklist, caveat, changelog, and control layer

That order matters because it prevents the slice from collapsing into a visual exception pack without a real trust and control investigation underneath it.
