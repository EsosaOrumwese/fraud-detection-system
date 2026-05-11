# Execution Plan - Reporting Support For Operational And Regional Teams Slice

As of `2026-04-04`

Purpose:
- turn the chosen InHealth reporting-support slice into a concrete execution order tied to bounded governed analytical outputs already available in the repo
- keep the work reporting-first, logic-first, and tightly scoped to one monthly reporting cycle plus one ad hoc follow-up output
- prove dependable monthly and ad hoc reporting support without drifting into a broad dashboard estate, broad reporting-ownership claim, or patient-level stewardship slice
- keep the execution memory-safe by scanning only the bounded periods and fields needed for the slice rather than treating the raw run like unlimited in-memory working space

Execution substrate:
- governed local artefacts already available in `artefacts/analytics_slices/`
- compact outputs already established from earlier slices where reuse is honest and efficient
- new slice outputs to be written under `artefacts/analytics_slices/data_analyst/inhealth_group/01_reporting_support_for_operational_and_regional_teams/`

Primary rule:
- define the bounded monthly reporting question first
- pin the KPI logic before packaging any reporting views
- build the recurring monthly output first
- derive one ad hoc follow-up output from the same governed logic
- harden the rerun and usage posture only after the recurring and follow-up outputs are stable
- never load broad raw surfaces into pandas or any other in-memory dataframe layer before the SQL gate has already reduced them to compact reporting-ready outputs

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- the repo already contains compact governed outputs suitable for reuse in a reporting-support slice without rebuilding the large analytical base
- one bounded programme-style reporting lane can be defined honestly from the available outputs
- one monthly reporting view and one ad hoc follow-up output can be produced from the same governed KPI layer
- the chosen KPI family can remain intentionally small while still being useful to:
  - operational teams
  - regional or programme oversight readers

Candidate first-pass reusable outputs:
- HUC `01_multi_source_service_performance` compact extracts where the underlying KPI structure is already suitable
- HUC `02_reporting_cycle_ownership` compact reporting-cycle outputs where rerun or control logic is reusable
- HUC `04_issue_to_action_briefing` compact issue-focused outputs where one follow-up reporting cut can be adapted honestly

Working assumption about the bounded reporting question:
- the recurring output should answer the current monthly operational position for one bounded lane
- the follow-up output should answer one realistic ad hoc reporting need without redefining the KPI logic
- the slice should remain support-oriented rather than turning into a broad service-line ownership claim

Important warning:
- those assumptions must be tested rather than carried forward casually
- if the existing compact outputs are not suitable enough, the slice should adapt early by shaping a lighter new reporting-ready view rather than forcing weak reuse

## 2. Reporting-First And Logic-First Posture

This slice must not begin as figure-first or dashboard-first work.

The correct posture is:
- define the monthly reporting question first
- define the KPI and comparison logic in SQL first
- define what the ad hoc follow-up output is meant to answer
- materialise compact reporting-ready views before any narrative or figure work
- use Python only after the monthly and follow-up reporting outputs already exist in a stable form

This matters because the InHealth responsibility here is about dependable reporting support, not decorative reporting surfaces.

## 2A. Memory And Query Discipline

This slice must be executed with explicit memory discipline.

The raw run contains very large surfaces, so the correct posture is:
- do not pull broad raw parquet surfaces into pandas
- do not run wide profiling queries across full history unless the slice truly needs them
- do not assume monthly scope means the whole dataset can be inspected casually

The correct query discipline is:
- start with summary-stats and metadata profiling before any slice build
- use `DuckDB` or SQL-style scans with predicate pushdown
- filter the reporting period at scan time
- project only the columns needed for the current step
- materialise compact intermediate outputs only after the filtered SQL logic is stable
- let Python read only those compact outputs, not the raw source families

The default execution ceiling for this slice is:
- bounded month selection only
- bounded field selection only
- one controlled intermediate output at a time

If a query starts behaving like broad exploratory profiling rather than bounded slice construction, stop and narrow it before proceeding.

The required first-pass summary profiling layer is:
- raw row counts for each candidate source used in the slice
- period coverage at month and comparison-window level
- key coverage for the join path or reporting grain
- null rates for fields required by the KPI family
- grain and field-meaning confirmation before any wider transformation logic is written

## 3. First-Pass Objective

The first-pass objective is:

`build one bounded monthly reporting cycle and one ad hoc follow-up output from the same governed KPI base, with enough control and usage clarity to support operational and regional reporting needs`

The proof object is:
- `reporting_support_for_operational_and_regional_teams_v1`

The first-pass output family is:
- one reporting requirements note
- one monthly KPI layer
- one monthly reporting pack
- one ad hoc follow-up output
- one KPI definition note
- one audience-usage note
- one rerun or release checklist

## 4. Early Scope Gate

Before building any reporting pack or figure, run a bounded scope gate.

The first profiling pass must answer:
- which existing compact outputs are stable enough to support a monthly reporting lane?
- what monthly comparison window can be defined honestly from the available timestamps or period labels?
- which KPI fields are stable enough to be reused consistently between recurring and follow-up outputs?
- what is the most realistic ad hoc reporting follow-up question to support from the same governed logic?
- what operational audience emphasis differs from the regional audience emphasis without requiring two different KPI definitions?
- what do the row counts, period coverage, key coverage, and null rates say about the safe scope of the slice before any heavier build begins?

Required checks:
- period coverage across the candidate compact outputs
- field availability for the candidate KPI family
- consistency of KPI meaning across reusable sources
- suitability of one segment or follow-up dimension for the ad hoc cut
- ability to regenerate the monthly and follow-up outputs from the same controlled logic

Those checks should be implemented as:
- aggregate-only SQL probes
- filtered month-level scans
- no broad row materialisation into memory

Decision rule:
- if one compact source family is stable enough, proceed with the bounded reporting-support slice
- if not, create a lighter reporting-ready SQL layer rather than broad new analytical reconstruction

## 5. Candidate Reporting Base

The first-pass reporting base should stay bounded and explicit.

Each reporting component should have one stated purpose:
- monthly KPI base
  - current monthly operational position
  - comparison to one prior monthly baseline where honest
  - stable KPI definitions for recurring use
- ad hoc follow-up base
  - same KPI meanings
  - one realistic follow-up or filtered reporting need
  - no manual KPI redefinition
- audience note layer
  - what operational readers should notice first
  - what regional readers should notice first
- control layer
  - rerun steps
  - release checks
  - caveats

If the reused outputs do not support one of those components cleanly, adapt by creating a small local reporting-support layer rather than stretching the earlier slice outputs past their truth boundary.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. reporting-scope and field-suitability checks
2. monthly KPI base construction
3. monthly reporting-pack shaping
4. ad hoc follow-up cut from the same KPI base
5. KPI definition and audience-usage note writing
6. rerun and release-control packaging

The transformations should not be hidden inside one-off notebook reshaping or manual copy-paste reporting.

## 7. Bounded SQL Build Order

### Step 1. Create a reporting-scope and field-suitability layer

Build small aggregate or profile queries only for:
- available monthly or period labels
- candidate KPI-field availability
- comparison-baseline coverage
- stable segment or follow-up dimension availability
- consistency of recurring versus follow-up field meaning

Goal:
- define the monthly reporting-support slice honestly
- prove that the recurring and follow-up outputs can come from one governed logic base

### Step 2. Materialise a monthly KPI view

Create one bounded SQL output, for example:
- `programme_monthly_kpis_v1`

This output should include:
- reporting period label
- current-versus-prior role where available
- bounded lane identifier
- compact KPI family
- one follow-up dimension that can support realistic ad hoc reporting

### Step 3. Materialise the ad hoc follow-up cut

Create one bounded SQL output, for example:
- `programme_ad_hoc_follow_up_v1`

This output should:
- derive from the same governed KPI logic
- answer one realistic follow-up reporting question
- keep the KPI meanings unchanged
- support either an operational follow-up or a regional oversight cut without redefining the logic

## 8. KPI Strategy

The KPI family must remain small and stable.

The first-pass KPI set should cover only what the monthly reporting question genuinely needs, likely:
- volume or pressure
- conversion or progression
- backlog or aging if relevant
- one downstream quality or yield signal if useful

The first-pass reporting reading should answer:
- what is the current monthly operational position?
- what moved versus the prior period, if a prior period is honest to compare?
- what realistic follow-up question would an operational or regional team ask next?
- can that follow-up be answered from the same KPI logic without redefining the metrics?

Decision rule:
- every KPI must support the monthly reporting support question
- if a metric does not help answer that question, drop it

## 9. Monthly Reporting-Pack Strategy

Once the KPI base is stable, package the slice into one compact monthly reporting pack.

The monthly pack should answer:
- what is the current position?
- what changed versus the prior month or baseline?
- what should the operational or regional reader notice first?

Required components:
- headline KPIs
- current-versus-prior comparison where valid
- one short operational note
- one short audience usage cue

Create:
- `programme_monthly_reporting_pack_v1.md`
- `programme_kpi_definition_note_v1.md`
- `programme_audience_usage_note_v1.md`

## 10. Ad Hoc Follow-Up Strategy

The follow-up output is not there to inflate the slice. It is there to prove responsive reporting support from the same governed base.

The ad hoc follow-up output should answer:
- one realistic reporting follow-up question
- using the same KPI definitions as the monthly pack
- with only the extra detail needed for the follow-up

Possible follow-up shapes:
- one filtered segment cut
- one regional comparison
- one programme-lane exception or focus cut

Decision rule:
- pick the follow-up shape that best proves ad hoc support without expanding the slice into a second reporting programme

Create:
- `programme_ad_hoc_follow_up_pack_v1.md`

## 11. Audience-Usage Strategy

The outputs are not complete unless the reader can understand how to use them without long oral explanation.

The audience-usage note should answer:
- what operational teams should look at first
- what regional or programme oversight should look at first
- what should not be overread from the pack

Optional short support note:
- one challenge-response note only if needed for clarity

## 12. Reproducibility Strategy

This slice is not complete unless the recurring and follow-up outputs can be regenerated consistently.

The first-pass reproducibility pack should include:
- versioned SQL build logic
- one compact Python script only if needed for render or table export
- one KPI definition note
- one audience-usage note
- one report-run checklist
- one caveat note

The Python layer must remain:
- compact-output only
- figure and note generation only
- not a substitute for broad raw-data processing

That should be strong enough that another analyst could:
- understand the reporting question
- rebuild the monthly KPI layer
- regenerate the monthly pack
- regenerate the ad hoc follow-up output
- understand what the outputs are and are not safe to claim

## 13. Planned Deliverables

SQL and shaped data:
- one field-suitability and reporting-scope query pack
- one monthly KPI build query
- one ad hoc follow-up build query
- one compact monthly summary output

Documentation:
- one reporting requirements note
- one KPI definition note
- one audience-usage note
- one report-run checklist
- one reporting caveats note
- one regeneration README

Expected output bundle for the first pass:
- one bounded monthly KPI layer
- one compact monthly reporting pack
- one ad hoc follow-up reporting output
- one controlled rerun and usage pack

## 14. What To Measure For The Claim

For this requirement, the strongest measures are dependable delivery, follow-up responsiveness, KPI consistency, and rerun control rather than advanced analytical novelty.

Primary measure categories:
- one monthly reporting pack delivered from one stable governed logic base
- number of ad hoc follow-up outputs answered from that same governed logic
- number of KPI families reused consistently between recurring and follow-up outputs
- number of release or quality checks passed before issue

Secondary measure categories:
- regeneration time for the monthly pack and follow-up output
- one audience-usage note completed for operational and regional readers
- one controlled rerun path documented

## 15. Execution Order

1. Finalise the folder structure for this InHealth responsibility lane.
2. Run the reporting-scope and field-suitability gate.
3. Decide the bounded monthly reporting question and follow-up reporting question.
4. Materialise the monthly KPI layer.
5. Shape the monthly reporting pack.
6. Materialise the ad hoc follow-up output from the same logic base.
7. Write the KPI definition and audience-usage notes.
8. Write the rerun checklist, caveats note, and regeneration note.
9. Produce complementary figures only after the reporting outputs are stable.
10. Write the execution report and final claim surfaces only after the evidence is real.

## 16. Stop Conditions

Stop and reassess if any of the following happens:
- the existing compact outputs are not stable enough to support one monthly reporting lane honestly
- the monthly-versus-follow-up outputs require different KPI meanings
- the reporting pack starts drifting into a broad dashboard estate
- the follow-up output turns into a second reporting programme rather than one realistic ad hoc response
- the slice starts drifting into patient-level dataset stewardship, which belongs more naturally to InHealth `3.C`
- the query posture starts requiring broad raw-data loads or memory-heavy dataframe work that should have been handled in bounded SQL instead

If one of those happens, the adaptation path is:
- keep the same responsibility lane
- name the actual blocker clearly
- narrow the monthly reporting question if needed
- preserve the center of gravity around dependable monthly and ad hoc reporting support

## 17. What This Plan Is And Is Not

This is:
- a concrete execution plan for the first InHealth responsibility slice
- reporting-first
- logic-first
- bounded
- aligned to dependable monthly and ad hoc reporting support

This is not:
- the execution report
- a broad BI programme
- a patient-level stewardship slice
- permission to force dashboard-like outputs where cleaner figures or pack views would do

The first operational move after this plan should be:
- run the bounded reporting-scope and field-suitability gate and decide whether the planned monthly-plus-follow-up reporting question is fully supportable from the compact governed outputs already available
