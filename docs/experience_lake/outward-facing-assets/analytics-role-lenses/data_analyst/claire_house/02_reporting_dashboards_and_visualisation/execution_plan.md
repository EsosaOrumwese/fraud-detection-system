# Execution Plan - Reporting, Dashboards, And Visualisation Slice

As of `2026-04-04`

Purpose:
- turn the chosen Claire House `3.B` slice into a concrete execution order tied to the trusted provision lane already available in the repo
- keep the work reporting-first, KPI-first, and tightly scoped to one bounded organisational reporting pack rather than broad BI-estate rhetoric, broad dashboard sprawl, or a repeat of the trusted data-provision slice
- prove scheduled and ad hoc reporting-and-visualisation delivery from a controlled analytical base without drifting into full organisation-wide dashboard ownership
- keep execution memory-safe by shaping only bounded reporting-ready outputs from the trusted provision lane rather than treating raw analytical scope like unlimited in-memory working space

Execution substrate:
- governed local artefacts already available in `artefacts/analytics_slices/`
- the trusted provision lane and protected summary already established in Claire House `3.A`
- compact inherited reporting-ready outputs from HUC, InHealth, and Midlands only where reuse is honest and structural rather than copied blindly
- new slice outputs to be written under `artefacts/analytics_slices/data_analyst/claire_house/02_reporting_dashboards_and_visualisation/`

Primary rule:
- confirm the exact trusted provision base inherited from Claire House `3.A` first
- define the bounded KPI family and summary/detail reporting structure before any visual packaging work
- produce one scheduled-style summary page and one ad hoc supporting detail cut from the same governed logic base
- package the reporting and visual outputs only after KPI definitions, comparison rules, and release controls are explicit
- never load broad raw detailed surfaces into pandas or any other in-memory dataframe layer before the SQL gate has already reduced them to compact reporting-ready outputs
- if figures are used, they must be analytical plots that clarify the reporting truth, not explanatory diagrams standing in for analysis

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- the repo already contains a trustworthy provision base from Claire House `3.A` that can feed one bounded reporting-and-visualisation product honestly
- one compact KPI family can be built from the protected provision summary without reopening a broad raw rebuild
- one scheduled-style organisational summary and one ad hoc supporting detail cut can both be produced from the same governed logic base
- one small reporting pack is enough to answer the Claire House responsibility without drifting into a fake BI-estate claim

Candidate first-pass reusable foundations:
- Claire House `01_trusted_data_provision_and_integrity` provision profile, integrity pack, and protected summary
- InHealth `01_reporting_support_for_operational_and_regional_teams` recurring-and-follow-up reporting structure
- HUC `02_reporting_cycle_ownership` reporting ownership and rerun-control structure
- Midlands `06_dashboard_decision_support` compact summary-plus-detail packaging patterns, but not its model-led dashboard framing

Working assumption about the bounded reporting question:
- the reporting layer should sit directly on the trusted provision lane
- the slice should prove that controlled data can be turned into scheduled and ad hoc reporting outputs
- the slice should remain bounded enough that the claim sounds organisationally useful without pretending to cover the whole Claire House reporting estate

Important warning:
- these assumptions must be tested rather than carried forward casually
- if the protected provision summary is too thin for the required reporting product, adapt by adding one compact KPI reshaping layer rather than broadening the raw query footprint

## 2. Reporting-First And KPI-First Posture

This slice must not begin as a figure-first or page-decoration exercise.

The correct posture is:
- confirm the inherited trusted provision base first
- fix the KPI family and comparison rules first
- define the scheduled summary page first
- define the ad hoc supporting detail cut second
- package the reporting visuals only after the governed reporting outputs are stable
- use Python only after the SQL layer has already reduced the slice to compact reporting-ready outputs

This matters because the Claire House responsibility here is about reports, dashboards, and visualisations that track `KPI` movement usefully, not about isolated chart production.

## 2A. Memory And Query Discipline

This slice must be executed with explicit memory discipline.

The underlying run contains very large detailed surfaces, so the correct posture is:
- do not pull broad raw parquet surfaces into pandas
- do not rerun wide historical profiling if the reporting question can be answered from Claire House `3.A` outputs plus compact new SQL shaping
- do not assume one bounded reporting pack justifies casual raw in-memory analysis

The correct query discipline is:
- start with summary-stats and reporting-scope profiling before any new materialisation
- use `DuckDB` or SQL-style scans with predicate pushdown
- filter the reporting window at scan time
- project only the fields needed for KPI shaping, comparison logic, summary output, and the ad hoc supporting cut
- materialise compact intermediate outputs only after the filtered SQL logic is stable
- let Python read only those compact outputs, not the raw detailed source families

The default execution ceiling for this slice is:
- inherited trusted outputs first
- bounded KPI reshaping only
- bounded field selection only
- one controlled intermediate output at a time

If a query starts behaving like broad exploratory analysis rather than bounded reporting-product shaping, stop and narrow it before proceeding.

The required first-pass summary profiling layer is:
- row counts for the inherited protected summary and any additional compact source used in the slice
- period coverage for the reporting window
- coverage of the chosen KPI family across the reporting base
- null rates for required KPI and comparison fields
- confirmation that the same KPI definitions can support both the summary page and the ad hoc supporting detail cut

## 3. First-Pass Objective

The first-pass objective is:

`build one bounded organisational reporting pack from the trusted provision lane, with one scheduled summary page, one ad hoc supporting detail cut, and one consistent KPI family`

The proof object is:
- `reporting_dashboards_and_visualisation_v1`

The first-pass output family is:
- one reporting scope note
- one KPI definition note
- one KPI-ready summary base
- one scheduled summary page
- one ad hoc supporting detail cut
- one audience-usage note
- one rerun and caveat pack

## 4. Early Scope Gate

Before building any reporting page or figure, run a bounded scope gate.

The first profiling pass must answer:
- which exact Claire House `3.A` output should act as the governed reporting base?
- what KPI family can be supported honestly from that base without reopening a large raw lane?
- what reporting window remains the cleanest truthful analogue?
- what comparison logic best supports both the summary page and the ad hoc detail cut?
- which fields are required to support both the visual summary and the deeper supporting view?
- what do the row counts, KPI coverage, field coverage, and comparison stability say about the safe scope of the reporting pack before any packaging begins?

Required checks:
- coverage and stability of the inherited protected summary
- field availability for the KPI family and supporting detail fields
- consistency of KPI meaning across summary and detail outputs
- completeness of the chosen grouping or band dimension
- whether one ad hoc supporting cut can be defined cleanly from the same governed base

Those checks should be implemented as:
- aggregate-only SQL probes
- filtered monthly scans
- inherited compact outputs where available
- no broad row materialisation into memory

Decision rule:
- if the protected provision base is strong enough, proceed with the bounded reporting pack
- if not, add one compact KPI reshaping layer rather than broadening the query footprint

## 5. Candidate Reporting Base

The first-pass reporting base should stay bounded and explicit.

Each component should have one stated purpose:
- reporting scope layer
  - define the reporting audience and window
  - define scheduled versus ad hoc use
- KPI base layer
  - define the stable KPI family and supporting comparison logic
- summary-page layer
  - define the top-level reporting view
- ad hoc detail layer
  - define the deeper supporting view from the same KPI logic
- control layer
  - define release-safe use, rerun steps, and caveats

If inherited outputs do not support one of those components cleanly, adapt by creating one compact local reporting-ready layer rather than stretching earlier slice outputs past their truth boundary.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. inherited-base confirmation and KPI-scope checks
2. KPI-ready summary and comparison layer
3. scheduled summary reporting page
4. ad hoc supporting detail cut
5. audience note, caveats, and rerun packaging

The transformations should not be hidden inside one-off notebook reshaping or manual copy-paste chart logic.

## 7. Bounded SQL Build Order

### Step 1. Confirm the inherited reporting base and KPI field coverage

Build small aggregate or profile queries only for:
- available reporting periods
- KPI field availability
- band or grouping coverage
- summary-versus-detail comparability
- stability of the protected overall baseline

Goal:
- define the Claire House reporting pack honestly
- prove that one scheduled and one ad hoc output can be claimed without broad raw reconstruction

### Step 2. Materialise a KPI-ready summary layer

Create bounded SQL outputs, for example:
- `trusted_reporting_summary_base_v1`
- `trusted_reporting_detail_cut_v1`

These outputs should include:
- the chosen KPI family
- overall comparison values where relevant
- the supporting band or group dimension
- one concise status field if needed for highlight or emphasis

### Step 3. Materialise the scheduled summary page data

Create one bounded output, for example:
- `trusted_reporting_summary_v1`

This output should:
- present the headline KPI readings
- support one compact summary visual surface
- remain small enough to act as a reporting product rather than another analytical estate build

### Step 4. Materialise the ad hoc supporting detail cut

Create one bounded output, for example:
- `trusted_reporting_ad_hoc_detail_v1`

This output should:
- deepen the same KPI story
- reuse the same KPI definitions and grouping logic
- answer a realistic supporting or follow-up reporting question

## 8. KPI Trust Strategy

The reporting pack must remain small in conceptual scope but strong in definition posture.

The first-pass KPI strategy should answer:
- which KPIs are headline KPIs?
- which grouping or band dimension supports both views?
- how is the overall comparison defined?
- what conditions would make the reporting pack misleading or unstable?

Decision rule:
- every retained field must earn its place in either:
  - KPI definition
  - summary-page output
  - ad hoc supporting detail output
- if a field does not support one of those purposes, drop it

## 9. Reporting Product Strategy

Once the KPI layer is stable, package the slice into one compact reporting product.

The reporting proof should answer:
- what should a general organisational reader see first?
- what does the ad hoc supporting detail cut add?
- why are these outputs more than loose charts?

Required components:
- one scheduled summary page
- one ad hoc supporting detail page or cut
- one short usage note
- analytical plots only where they clarify KPI or control meaning

Create:
- `organisational_reporting_summary_page_v1.md`
- `organisational_reporting_ad_hoc_detail_page_v1.md`
- `reporting_visualisation_audience_note_v1.md`

## 10. Documentation And Control Strategy

The slice is not complete unless another analyst could rerun the pack responsibly.

The documentation and control pack should answer:
- what the KPI family is
- what the summary page is for
- what the ad hoc supporting detail cut is for
- what to release first
- what checks must pass
- what the pack does and does not answer

Create:
- `reporting_visualisation_scope_note_v1.md`
- `reporting_visualisation_kpi_definitions_v1.md`
- `reporting_visualisation_caveats_v1.md`
- `README_reporting_visualisation_regeneration.md`
- `CHANGELOG_reporting_visualisation.md`

## 11. Reproducibility Strategy

This slice is not complete unless the reporting pack and its controls can be regenerated consistently.

The first-pass reproducibility pack should include:
- versioned SQL KPI shaping logic
- versioned SQL summary-page output logic
- versioned SQL ad hoc detail logic
- one compact Python script only if needed for page assembly or analytical figure render
- one audience note
- one caveat or changelog note

The Python layer must remain:
- compact-output only
- not a substitute for broad analytical processing

That should be strong enough that another analyst could:
- understand the KPI family
- rerun the summary and detail outputs
- regenerate the reporting pack
- understand what the scheduled and ad hoc outputs are and are not safe to claim

## 12. Planned Deliverables

SQL and shaped data:
- one reporting-scope and KPI-coverage query pack
- one KPI-ready summary query
- one ad hoc detail query
- one compact summary-page output
- one compact ad hoc detail output

Documentation:
- one reporting scope note
- one KPI definition note
- one audience-usage note
- one caveats note
- one regeneration README

Reporting outputs:
- one scheduled summary page
- one ad hoc supporting detail page
- analytical plots only if they help clarify the reporting truth

Expected output bundle for the first pass:
- one bounded organisational reporting pack
- one compact control and rerun pack
- one compact scheduled-plus-ad-hoc reporting proof

## 13. What To Measure For The Claim

For this requirement, the strongest measures are reporting-product consistency, scheduled-plus-ad-hoc reuse, and control discipline rather than analytical novelty.

Primary measure categories:
- number of KPI families defined and reused consistently
- number of reporting views delivered from one governed base
- number of ad hoc supporting outputs delivered from the same governed logic
- number of release checks passed before issue

Secondary measure categories:
- regeneration time for the compact reporting pack
- one completed audience note
- one completed caveat and rerun pack

## 14. Execution Order

1. Finalise the folder structure for this Claire House responsibility lane.
2. Run the inherited-base and reporting-scope gate.
3. Decide the bounded KPI family, grouping logic, and overall comparison basis.
4. Materialise the KPI-ready summary layer.
5. Materialise the scheduled summary-page output.
6. Materialise the ad hoc supporting detail output.
7. Write the scope note, KPI definition note, audience note, caveats note, changelog, and regeneration note.
8. Produce analytical plots only after the reporting outputs are stable.
9. Write the execution report and final claim surfaces only after the evidence is real.

## 15. Stop Conditions

Stop and reassess if any of the following happens:
- the Claire House `3.A` provision base is too thin to support a reporting-pack claim honestly
- the chosen KPI family becomes inconsistent between summary and detail outputs
- the ad hoc supporting cut cannot be generated from the same governed base
- the slice starts drifting into broad BI-estate, board-reporting, or regulatory-reporting ownership rather than bounded reporting-and-visualisation delivery
- the query posture starts requiring broad raw-data loads or memory-heavy dataframe work that should have been handled in bounded SQL instead
- the figures start turning into explanatory decoration instead of analytical plots that clarify the reporting truth

If one of those happens, the adaptation path is:
- keep the same responsibility lane
- name the actual blocker clearly
- narrow the KPI family, grouping dimension, or supporting-cut scope if needed
- preserve the center of gravity around bounded reporting-and-visualisation delivery from a trusted provision base

## 16. What This Plan Is And Is Not

This is:
- a concrete execution plan for the second Claire House responsibility slice
- reporting-first
- KPI-first
- bounded
- aligned to reports, dashboards, and visualisation delivery from a trusted provision base

This is not:
- the execution report
- a broad organisation-wide BI programme
- a board-reporting slice
- permission to force dashboards or visuals that do not materially support the reporting claim

The first operational move after this plan should be:
- run the inherited-base and reporting-scope gate and decide whether the Claire House `3.A` provision lane can support one honest scheduled-and-ad-hoc reporting pack without reopening a broad raw analytical rebuild
