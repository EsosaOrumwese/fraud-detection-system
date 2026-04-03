# Execution Plan - Conversion Discrepancy Handling Slice

As of `2026-04-03`

Purpose:
- turn the chosen HUC conversion-discrepancy-handling slice into a concrete execution order tied to the bounded governed reporting views
- keep the work anomaly-first, trust-first, and bounded to one KPI discrepancy carried through to control
- prove anomaly detection, discrepancy investigation, operational impact reading, and repeatable reporting control without drifting into a broad quality programme

Execution substrate:
- [`runs/local_full_run-7`](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\runs\local_full_run-7)
- bounded governed service-line outputs already created in HUC slices `01_multi_source_service_performance` and `02_reporting_cycle_ownership`
- governed local artefacts already available in `artefacts/analytics_slices/`

Primary rule:
- choose one KPI discrepancy only
- quantify the mismatch before discussing causes
- prove why it matters operationally
- package the issue into one compact exception pack
- add rerun controls so the same discrepancy is caught earlier next cycle

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- the bounded HUC reporting outputs already contain two linked views that should agree on suspicious-to-case conversion
- the discrepancy can be expressed without rebuilding the full service-line base
- the likely cause can be isolated to reporting logic, scope, or numerator/denominator handling rather than a broad source failure
- one weekly reporting window is sufficient to show the anomaly and its correction
- the corrected control can be embedded into the reporting cycle from HUC slice `02`

Working assumption about the anomaly:
- it will be a suspicious-to-case conversion mismatch across two reporting views
- both views will appear plausible enough that the mismatch would matter if left uninvestigated
- the slice will be stronger if the discrepancy is one that a reporting owner should have caught before release

Important warning:
- those assumptions must be tested rather than carried forward casually
- if the two views do not actually represent a real control issue, adapt early and choose a better discrepancy inside the same reporting lane

## 2. Execution Center Of Gravity

This slice must stay distinct from the earlier HUC work.

That means:
- do not treat this as another general source-reconciliation slice
- do not make the bank-view versus authoritative-truth distinction the whole story unless it creates a real reporting-view mismatch
- do not widen the work into many discrepancy classes
- do not build a generic anomaly dashboard

This slice should instead prove:
- one KPI looked wrong across two linked reporting views
- the mismatch was investigated through source and view lineage
- the discrepancy was quantified
- the operational reading changed after correction
- the reporting workflow now contains a control that would catch the same issue earlier next cycle

## 3. Best Execution Order

The execution order remains:
- `03 -> 01 -> 02 -> 09`

That means:
1. detect, reconcile, and root-cause the discrepancy
2. show the operational impact of the mismatch
3. package the issue into one compact exception pack
4. add rerun and release controls

## 4. First-Pass Objective

The first-pass objective is:

`build one bounded anomaly-to-resolution cycle for suspicious-to-case conversion, ending in one corrected KPI pack and one repeatable reporting control`

The proof object is:
- `conversion_discrepancy_handling_v1`

The first-pass output family is:
- one source and lineage map
- one reconciliation layer
- one issue log
- one before-and-after KPI layer
- one compact two-page exception pack
- one rerun checklist
- one caveat note
- one changelog

## 5. Discrepancy Gate

Before building any pack, run a discrepancy gate.

The first pass must answer:
- which two views are being compared?
- why should they agree on suspicious-to-case conversion?
- what are the numerator and denominator definitions in each view?
- what window and scope rules apply?
- what is the raw gap in absolute and percentage terms?
- is the gap large enough to matter for reporting interpretation?

Required outputs from this gate:
- one source map
- one source-rules note
- one lineage note
- one quantified discrepancy view

Decision rule:
- if the discrepancy is trivial or not a real control issue, choose a better bounded KPI mismatch before proceeding
- if the discrepancy is material and defensible, proceed into reconciliation and root-cause work

## 6. Reconciliation and Root-Cause Strategy

This slice should stay tightly focused on suspicious-to-case conversion.

The reconciliation work must cover:
- missing keys
- duplicate relationships
- unmatched rows
- scope inconsistencies
- numerator and denominator drift
- wrong period or window application

The root-cause work should test only likely causes:
- join error
- missing or duplicated rows
- incorrect scope
- inconsistent numerator or denominator logic
- wrong authoritative source for the KPI

Required outputs:
- one reconciliation SQL pack
- one issue log
- one likely root-cause statement
- one corrective-action statement

Decision rule:
- the slice is not complete until the discrepancy is tied to a plausible cause rather than only described

## 7. Operational-Impact Strategy

Once the discrepancy is understood, show why it matters operationally.

The first-pass operational layer should answer:
- what would the original reported conversion have made people believe?
- did the discrepancy imply false pressure, false improvement, or false deterioration?
- what now looks different after correction?
- what should operations monitor next?

Required outputs:
- one before-and-after KPI comparison
- one operational impact note
- one intervention note

The operational layer must remain small.
- only include supporting signals if they help explain the conversion discrepancy
- do not turn this into a broad service-line review

## 8. Exception-Pack Strategy

Once the discrepancy and impact are stable, package the issue into one compact `2`-page pack.

### Page 1. Exception summary

This page should answer:
- what was wrong?
- how large was the discrepancy?
- what is the corrected KPI?
- what is the current status?

Required components:
- original versus corrected KPI
- discrepancy magnitude
- short issue summary
- status:
  - open
  - investigated
  - resolved

### Page 2. Drill-through and explanation

This page should answer:
- where did the discrepancy come from?
- which dimension or segment was affected?
- what changed after correction?
- what is the corrected interpretation?

Required components:
- source or view explanation
- one drill-through summary
- one correction note
- one corrected interpretation note

Create:
- `conversion_exception_pack_v1`
- `conversion_kpi_definition_note_v1.md`
- `conversion_drillthrough_note_v1.md`

## 9. Reporting-Control Strategy

This is what makes the slice about discrepancy handling rather than a one-time investigation.

The first-pass control layer should include:
- one rerun checklist
- one caveat note
- one changelog
- one regeneration README

Those outputs must answer:
- what to run before releasing the report
- what discrepancy threshold should trigger review
- what outputs must be checked each cycle
- what changed in the KPI or report logic
- whether earlier periods remain comparable

Required outputs:
- `README_conversion_anomaly_checks.md`
- `conversion_report_run_checklist_v1.md`
- `conversion_reporting_caveats_v1.md`
- `CHANGELOG_conversion_reporting.md`

## 10. Reuse Strategy

This slice should reuse bounded artefacts from HUC slices `01` and `02` where that helps prove discrepancy handling.

Permitted reuse:
- stable weekly service-line KPI context
- current-versus-prior pack structure
- rerun-control structure from the owned reporting cycle
- compact reporting-ready views where the conversion discrepancy can be isolated cleanly

But the proof burden must shift from:
- `can we build and own a recurring pack?`

to:
- `can we catch, investigate, correct, and control a KPI discrepancy inside that pack?`

## 11. Planned Deliverables

Trust and discrepancy:
- one source map
- one source-rules note
- one lineage note
- one reconciliation SQL layer
- one issue log

Operational impact:
- one before-and-after KPI comparison
- one operational impact note
- one intervention note

Reporting product:
- one compact two-page exception pack
- one KPI definition note
- one drill-through note

Reporting controls:
- one rerun checklist
- one caveat note
- one changelog
- one anomaly-check README

Expected output bundle for the first pass:
- one detected and quantified discrepancy
- one likely root cause
- one corrected KPI view
- one compact exception pack
- one repeatable control layer

## 12. What To Measure For The Claim

For this requirement, the strongest measures are discrepancy size, correction effect, and repeatable control.

Primary measure categories:
- raw versus corrected KPI gap
- reduction in discrepancy after correction
- number of validation or reconciliation checks added
- time to rerun the corrected exception pack
- number of future releases covered by the new control

Secondary measure categories:
- one false operational interpretation corrected
- one report now gated by anomaly review before release

## 13. Execution Order

1. Finalise the folder structure for this HUC discrepancy-handling lane.
2. Identify the two reporting views and quantify the conversion gap.
3. Write the source map, source-rule, and lineage layer.
4. Build the reconciliation and issue-log layer.
5. Build the corrected before-and-after KPI layer.
6. Write the operational impact and intervention notes.
7. Build the two-page exception pack.
8. Add the rerun checklist, caveat note, changelog, and anomaly-check README.
9. Write the execution report and claim surfaces only after the evidence is real.

## 14. Stop Conditions

Stop and reassess if any of the following happens:
- the compared views are not actually supposed to agree
- the discrepancy is too small to matter for reporting or decision-making
- the mismatch cannot be tied to a plausible cause
- the slice starts turning into a broad quality programme
- the correction requires rebuilding much larger surfaces than the bounded reporting lane justifies

If one of those happens, the adaptation path is:
- keep the same responsibility lane
- name the actual blocker clearly
- choose a better bounded discrepancy inside the same reporting cycle if needed
- preserve the center of gravity around one anomaly-to-resolution proof rather than broad quality activity

## 15. What This Plan Is And Is Not

This is:
- a concrete execution plan for the third HUC responsibility slice
- anomaly-first
- trust-first
- bounded
- aligned to discrepancy investigation, correction, and reporting control

This is not:
- the execution report
- a broad quality programme
- another generic reporting pack
- permission to assume the anomaly is real before quantifying it

The first operational move after this plan should be:
- identify the two linked reporting views for suspicious-to-case conversion and quantify the raw gap before any root-cause language is written
