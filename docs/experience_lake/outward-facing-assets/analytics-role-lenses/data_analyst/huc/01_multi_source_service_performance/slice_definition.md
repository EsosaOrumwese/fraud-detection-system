# Multi-Source Service Performance Execution Slice - HUC Data Analyst Requirement

As of `2026-04-03`

Purpose:
- capture the chosen bounded slice for the HUC requirement around analysing data from multiple operational sources for one unified service-performance purpose
- keep the note aligned to the actual HUC responsibility rather than drifting into generic BI, generic data quality, or model-led analytics
- preserve the distinction between this slice and the earlier Midlands data-science slices

Boundary:
- this note is not an accomplishment record
- this note is not a claim that a broad HUC operational-reporting estate has already been built
- this note captures the chosen slice, why it fits the requirement, which lenses own it, and what the proof burden should be
- execution should work from governed data extracts or local bounded views rather than broad platform reruns

Placement rule:
- this file lives under the role-shaped lens tree because it is execution-depth material, not a top-level lens definition
- the role folder should hold multiple employer lanes over time
- the employer folder should hold one folder per targeted responsibility slice so repeated work stays grouped and readable

Primary source basis:
- [01_operational-performance-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\01_operational-performance-analytics.md)
- [03_data-quality-governance-trusted-information-stewardship.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\03_data-quality-governance-trusted-information-stewardship.md)
- [02_bi-insight-reporting-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\02_bi-insight-reporting-analytics.md)
- [08_stakeholder-translation-communication-influence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\08_stakeholder-translation-communication-influence.md)
- [data-analytics-engineering-science.ideal-candidate-profiles.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.ideal-candidate-profiles.md)
- [data-analytics-engineering-science.job-ads.evidence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.job-ads.evidence.md)

---

## 1. Requirement Being Targeted

The requirement being targeted here is the HUC `Data Analyst` expectation around:
- analysing data from multiple operational sources
- bringing those sources together for a unified analytical purpose
- using the combined view to measure service performance or support decisions
- staying comfortable with imperfect source data rather than assuming the sources are already clean

This maps directly to the HUC candidate-profile requirement that the analyst should be able to describe:
- working with multiple operational datasets
- combining them for a unified performance or decision-support purpose
- checking for consistency before producing outputs
- using the combined data to measure trends or answer operational questions

This note exists because that requirement is broad enough to produce drift if attacked all at once, but narrow enough to support one bounded proof slice that can later become a truthful `X by Y by Z` claim.

## 2. Lens Stack For This Requirement

The best lens combination for this requirement is:

**Primary**
- `01 - Operational Performance Analytics`

**Strong support**
- `03 - Data Quality, Governance, and Trusted Information Stewardship`

**Secondary support**
- `02 - BI, Insight, and Reporting Analytics`

**Optional final-mile support**
- `08 - Stakeholder Translation, Communication, and Decision Influence`

Why this stack fits:

The requirement itself is about:
- working with multiple operational datasets
- bringing them together for one analytical purpose
- measuring service performance
- supporting decisions
- staying comfortable with imperfect source data

That makes `01` the main owner because it is the lens for:
- service performance
- workflow movement
- KPI logic
- trend explanation
- bottleneck detection
- decision-support reporting over governed truth

That also fits the HUC job ad itself, which frames the role around:
- analysing data from multiple sources to measure operations and performance
- tracking trends
- supporting contractual and performance reporting
- using analytics to support operational and strategic decisions

`03` is the next most important lens because this requirement also expects the analyst to be comfortable with imperfect source data and the practical work of combining, checking, and interpreting it. That is classic `03` territory:
- fit-for-use checks
- reconciliation
- source logic
- join correctness
- anomaly detection
- protecting reporting trust

`02` then supports it because once the multi-source data is combined and the KPI logic is sound, HUC still expects it to become reporting and decision-support output. `02` owns:
- turning governed truth into dashboards, summary packs, and stakeholder-ready views
- shaping KPI logic into reusable reporting logic
- making outputs readable to the intended audience

`08` becomes important once the slice needs to emphasise the non-technical communication side, because HUC also expects the analyst to present findings clearly to teams, commissioners, and senior stakeholders.

So the practical reading is:
- `01` combines the sources to answer a real operational performance question
- `03` makes sure the combined view is trustworthy and discrepancies are handled properly
- `02` packages the result into reporting and insight that people can use
- `08` makes the final output understandable and action-oriented for non-technical readers

Ownership order:
- `01 -> 03 -> 02 -> 08`

Best execution order:
- `03 -> 01 -> 02 -> 08`

That execution order matters because the sources need to be checked and reconciled before the KPI logic is interpreted, and the reporting pack needs to sit on stable, governed output rather than unresolved source ambiguity.

## 3. Chosen Bounded Slice

The cleanest bounded slice for this HUC requirement is:

`One multi-source operational performance slice for a single service-line review pack`

In the fraud-platform analogue, that means:
- combine `4` governed surfaces into one bounded service-performance view:
  - event truth
  - flow or context truth
  - case chronology
  - outcome or label truth
- answer one unified question:
  - `what is happening to workflow performance, and which segment or period is driving it?`
- produce:
  - one merged analytical base
  - one KPI layer
  - one discrepancy and reconciliation layer
  - one compact reporting pack
  - one stakeholder explanation brief

To keep the service-line review pack concrete and bounded, the single operational lens for this slice should be:
- `current-vs-prior workflow pressure and conversion into case work, with backlog or aging pressure and outcome quality used to explain what changed`

That refinement is not a change of meaning. It is there to stop the slice from turning into a broad mixed operational summary.

This slice is the best analogue for the HUC requirement because it proves:
- multi-source integration
- comfort with imperfect source data
- service-performance measurement
- KPI logic
- reporting-ready output
- decision-support translation

## 4. Why This Slice Was Chosen

This slice was chosen because it gives direct room for:
- combining multiple operational datasets into one governed analytical purpose
- measuring service performance rather than generic activity
- handling discrepancies and inconsistencies explicitly
- comparing current versus prior service-line behaviour
- turning the result into stakeholder-ready operational reporting

It also avoids the wrong kinds of drift.

The intention is not to:
- build a broad enterprise reporting estate
- mix many unrelated service questions into one pack
- produce generic data quality checks without an operational use case
- create a dashboard wall with too many KPIs
- wander into predictive modelling when the HUC requirement here is operational integration and performance reading

The intention is to prove one sharper statement:
- I can bring multiple operational datasets together for one trusted service-performance purpose, handle imperfect source data, and turn the result into reporting that supports operational and leadership decisions

## 5. Execution Posture

The default execution stack for this slice is:
- `SQL` for source reconciliation, join-path definition, merged base construction, and KPI shaping
- `Python` for compact pack generation, discrepancy summaries, and bounded reporting surfaces where useful
- markdown notes for source rules, discrepancy interpretation, and audience-facing explanation

The execution substrate should be:
- governed local extracts
- bounded local views
- reporting-ready analytical outputs derived from the governed world

The default local working assumption is that execution can begin from a bounded run such as:
- `runs/local_full_run-7`

That should still be treated as:
- a bounded operational extract
- not the whole world
- not permission to overclaim full operational coverage

## 6. Lens-by-Lens Execution Checklist

### 6.1 Lens 03 - Combine, check, and trust the sources

This is where the slice proves comfort with imperfect source data rather than pretending the inputs are already stable. `03` is the lens for validation, reconciliation, source meaning, fit-for-use checks, and protecting reporting trust.

1. Pick one bounded period, such as one week or one operational review window.
2. Define the four source surfaces to combine.
3. Write a short source-purpose note:
- what each source contributes
- what grain it lives at
- what it should and should not be used for
4. Build reconciliation checks for:
- key availability
- duplicate relationships
- missing rows after joins
- scope inconsistencies between views
5. Build one discrepancy log:
- issue
- likely cause
- affected KPI
- severity
- action
6. Record authoritative-source rules for each KPI family.
7. Record the join path and any exclusions.

### 6.2 Lens 01 - Turn the combined data into one operational performance view

This is the main ownership lens for the requirement because `01` is about KPI logic, workflow diagnosis, throughput, bottlenecks, trend explanation, and decision-support reporting over governed truth.

Keep it bounded to `4` KPI families only:
- volume or pressure
- conversion into case work
- backlog or aging
- outcome quality

Tasks:
1. Define the analytical grain as day or week, plus one business segment such as campaign or cohort.
2. Build one combined service-performance base view from the reconciled sources.
3. Create KPI views for:
- suspicious event volume
- suspicious-to-case conversion
- open or aged case count
- case-to-outcome yield
4. Compare the current period to one prior period.
5. Identify one operational problem:
- pressure spike
- conversion drop
- backlog growth
- outcome deterioration
6. Write one short `what changed` note.
7. Write one `where intervention is needed` note.

### 6.3 Lens 02 - Package the result into reporting

`02` owns the reporting product:
- what gets shown
- how it is grouped
- what belongs on executive versus operational views
- how KPI logic becomes reusable reporting logic

Keep this to one compact reporting pack with `3` pages only:

**Page 1 - Executive overview**
- headline KPIs
- trend direction
- one short issue summary

**Page 2 - Workflow health**
- conversion
- backlog or aging
- one anomaly comparison

**Page 3 - Drill-through or detail**
- segment comparison
- discrepancy note
- short interpretation note

Tasks:
1. Define the KPI names and meanings.
2. Keep metric logic consistent across all pages.
3. Decide what operations should see first and what leadership should see first.
4. Add page-level notes so the output is readable without oral explanation.
5. Build one reusable summary-pack export.

### 6.4 Lens 08 - Make the output usable for decisions

`08` is the final-mile lens. It owns translating technical output into operational meaning, tailoring it for the audience, preparing challenge-ready notes, and connecting evidence to action.

Tasks:
1. Write one executive brief:
- what changed
- why it matters
- what should be monitored next
2. Write one operational action note:
- which segment needs attention
- what the likely issue is
- what follow-up is justified
3. Write one challenge-response note:
- why trust this number?
- what does this KPI include?
- what discrepancy caveat applies?
4. Annotate the reporting pack for non-technical readers.

## 7. Suggested Artifact Pack

The minimum credible proof pack for this slice is:
- one source map
- one reconciliation and discrepancy pack
- one merged service-performance SQL view
- one KPI SQL view
- one `3`-page reporting pack
- one executive brief
- one action note

That is enough to prove:
- multi-source integration
- comfort with imperfect source data
- service-performance measurement
- reporting-ready output
- decision-support translation

## 8. Suggested Artifact Names

These names are placeholders, not fixed schema requirements.

Source, trust, and discrepancy assets:
- `service_line_source_map_v1.md`
- `service_line_reconciliation_checks_v1.sql`
- `service_line_discrepancy_log_v1.md`
- `service_line_authoritative_source_rules_v1.md`
- `service_line_join_lineage_v1.md`

Service-performance and KPI assets:
- `vw_service_line_performance_base_v1.sql`
- `vw_service_line_kpis_v1.sql`
- `service_line_what_changed_v1.md`
- `service_line_problem_statement_v1.md`

Reporting and communication assets:
- `service_line_reporting_pack_v1`
- `service_line_kpi_definitions_v1.md`
- `service_line_page_notes_v1.md`
- `service_line_exec_brief_v1.md`
- `service_line_action_note_v1.md`
- `service_line_challenge_response_v1.md`

## 9. Definition Of Done

This slice should be treated as complete only when all of the following are true:
- `4` governed sources have been combined into one bounded analytical slice
- reconciliation checks and a discrepancy log exist
- one shared KPI layer exists for the service-line question
- one prior-versus-current comparison exists
- one operational problem has been identified and explained
- one reporting pack exists
- one non-technical action brief exists

## 10. Truth Boundary

As of this note, the correct claim is:
- the slice has been selected
- the lens mapping is clear
- the execution path is defined
- the output pack has been bounded

The correct claim is not:
- that the slice has already been executed
- that a recurring HUC reporting cycle has already been implemented
- that source discrepancies have already been resolved
- that the service-line pack is already in operational use

This note therefore exists to protect against overclaiming while still preserving momentum toward a fast, defensible claim.

## 11. What To Measure For The Eventual `Y`

For this requirement, the strongest `Y` values are:
- number of sources successfully integrated into one analytical slice
- reconciliation discrepancy rate
- number of KPI families defined and reused consistently
- number of anomaly or discrepancy classes identified
- time to regenerate the service-line pack
- number of audience-specific outputs produced

A strong small `Y` set would be:
- `[N]` operational sources integrated into one service-performance slice
- reconciliation discrepancy reduced to or held below `[X]%`
- `[K]` KPI families defined consistently across the pack
- `[M]` discrepancy classes identified and investigated
- one pack regenerated from governed SQL or views in `[T]` minutes

## 12. XYZ Claim Surfaces This Slice Is Aiming Toward

This section is included here because the slice definition needs to preserve the exact claim shape the execution is aiming toward, not just the structural checklist.

### 12.1 Full flagship `X by Y by Z` version

> Improved service-line performance visibility and decision support, as measured by successful integration of `[N]` operational data sources into one governed analytical slice, reconciliation discrepancy below `[X]%`, and consistent reuse of `[K]` KPI families across the reporting pack, by combining event, flow, case, and outcome data into a unified performance layer, validating discrepancies and source logic, and turning the results into recurring executive and operational reporting outputs.

### 12.2 Shorter recruiter-readable version

> Integrated multiple operational data sources into one trusted performance-analysis slice, as measured by validated source consistency, reusable KPI logic, and delivery of stakeholder-ready service-line reporting, by combining, checking, and interpreting governed workflow and outcome data for operational decision support.

### 12.3 Closest direct response to the HUC requirement

> Brought multiple operational datasets together for a unified service-performance purpose, as measured by reconciled multi-source views, stable KPI definitions, and reporting outputs used to track trends and support decisions, by combining imperfect source data, checking consistency, and packaging the results into operational and leadership reporting.

## 13. Immediate Next-Step Order

The correct build order remains:
1. `03` source map, fit-for-use, and reconciliation layer
2. `01` merged service-performance and KPI layer
3. `02` compact three-page reporting pack
4. `08` executive, action, and challenge-response notes

That order matters because it prevents the slice from collapsing into polished reporting on top of unresolved source ambiguity.
