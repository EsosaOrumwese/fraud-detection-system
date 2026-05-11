# Execution Plan - Senior Leadership And External Reporting Slice

As of `2026-04-04`

Purpose:
- turn the chosen Claire House `3.C` slice into a concrete execution order tied to the trusted provision and reporting outputs already available in the repo
- keep the work audience-first, concise, and tightly scoped to one leadership summary pack plus one external-style oversight reporting cut rather than broad board-reporting rhetoric, regulatory-programme claims, or a repeat of the general reporting slice
- prove higher-accountability reporting support from a controlled reporting base without drifting into a fake full senior-and-external reporting estate
- keep execution memory-safe by reshaping only bounded reporting-ready outputs from Claire House `3.A` and `3.B` rather than treating raw analytical scope like unlimited in-memory working space

Execution substrate:
- governed local artefacts already available in `artefacts/analytics_slices/`
- the trusted provision lane already established in Claire House `3.A`
- the scheduled and ad hoc reporting outputs already established in Claire House `3.B`
- compact reshaping outputs and notes to be written under `artefacts/analytics_slices/data_analyst/claire_house/03_senior_leadership_and_external_reporting/`

Primary rule:
- confirm the exact governed base inherited from Claire House `3.A` and `3.B` first
- define the leadership audience and external-style oversight audience explicitly before any repackaging work
- produce one leadership summary pack and one external-style oversight cut from the same governed KPI base
- package caveats, release posture, and trust boundary only after the audience cuts are real
- never load broad raw detailed surfaces into pandas or any other in-memory dataframe layer before the SQL gate has already reduced them to compact audience-shaped outputs
- if figures are used, they must be analytical plots that clarify the reporting truth for the higher-accountability audiences, not explanatory diagrams or decorative slideware

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- the repo already contains a trustworthy reporting base from Claire House `3.A` and `3.B` that can be reshaped for leadership and external-style oversight use honestly
- one compact KPI family is already stable enough that a higher-accountability audience cut can be created without reopening a broad analytical rebuild
- one leadership summary and one external-style oversight cut are enough to answer the Claire House responsibility without drifting into whole-estate reporting claims
- the external side can be handled as one controlled oversight-style cut rather than a broad submission programme

Candidate first-pass reusable foundations:
- Claire House `01_trusted_data_provision_and_integrity` provision-trust and release posture
- Claire House `02_reporting_dashboards_and_visualisation` scheduled summary output, ad hoc supporting detail output, and KPI definition logic
- HUC `04_issue_to_action_briefing` only conceptually where concise high-level reporting structure is useful, not as a direct execution surface

Working assumption about the bounded reporting question:
- the leadership pack should sit directly on the Claire House `3.B` governed reporting base
- the external-style oversight cut should reuse the same KPI family and trust base
- the slice should prove higher-accountability audience shaping, not new analytical discovery

Important warning:
- these assumptions must be tested rather than carried forward casually
- if the Claire House `3.B` reporting base is too thin for one of the audience cuts, adapt by narrowing the audience product rather than broadening the raw query footprint

## 2. Audience-First And Concision-First Posture

This slice must not begin as a chart-first or generic reporting-pack exercise.

The correct posture is:
- confirm the inherited reporting base first
- define the audience matrix first
- define what leadership needs to see first
- define what the external-style oversight audience needs to see first
- build the leadership summary pack second
- build the external-style oversight cut third
- add caveats, release checks, and trust notes after the audience cuts are stable
- use Python only after the SQL layer has already reduced the slice to compact audience-ready outputs

This matters because the Claire House responsibility here is about senior and external-style reporting, and the execution should read like careful audience shaping and control, not like general report polishing.

## 2A. Memory And Query Discipline

This slice must be executed with explicit memory discipline.

The underlying run contains very large detailed surfaces, so the correct posture is:
- do not pull broad raw parquet surfaces into pandas
- do not rerun wide historical profiling if the higher-accountability reporting question can be answered from Claire House `3.A` and `3.B` outputs plus compact audience reshaping
- do not assume that a leadership or external-style pack justifies reopening broad raw analytical scope

The correct query discipline is:
- start with summary-stats and audience-scope profiling before any new materialisation
- use `DuckDB` or SQL-style scans with predicate pushdown
- filter the reporting window at scan time
- project only the fields needed for leadership emphasis, external-style oversight emphasis, release posture, and any supporting analytical plot
- materialise compact intermediate outputs only after the filtered SQL logic is stable
- let Python read only those compact outputs, not the raw detailed source families

The default execution ceiling for this slice is:
- inherited trusted outputs first
- bounded audience reshaping only
- bounded field selection only
- one controlled intermediate output at a time

If a query starts behaving like broad exploratory reporting rather than bounded higher-accountability repackaging, stop and narrow it before proceeding.

The required first-pass summary profiling layer is:
- row counts for the inherited leadership-candidate and external-candidate reporting bases
- confirmation that the chosen KPI family remains stable across both audience cuts
- field coverage for leadership notes, external-style caveats, and release posture
- confirmation that one concise leadership pack and one concise oversight cut can be created from the same governed base

## 3. First-Pass Objective

The first-pass objective is:

`build one leadership summary pack plus one external-style oversight reporting cut from the trusted Claire House reporting base, with explicit audience matrix, caveat posture, and release controls`

The proof object is:
- `senior_leadership_and_external_reporting_v1`

The first-pass output family is:
- one leadership-and-external reporting scope note
- one audience matrix
- one leadership summary output
- one external-style oversight cut
- one release-check output
- one caveat and trust note
- one regeneration and release-readiness note

## 4. Early Scope Gate

Before building either audience cut, run a bounded scope gate.

The first profiling pass must answer:
- which exact Claire House `3.B` output should act as the governed base for the leadership summary?
- which exact Claire House `3.B` output should act as the governed base for the external-style oversight cut?
- what KPI family can be reused intact across both audience cuts?
- what additional phrasing or caveat layers are genuinely needed for higher-accountability use?
- which fields are required to support both the concise leadership view and the tighter external-style oversight cut?
- what do the row counts, KPI coverage, field coverage, and release-posture needs say about the safe scope of the higher-accountability pack before any packaging begins?

Required checks:
- coverage and stability of the inherited scheduled summary
- coverage and stability of the inherited ad hoc supporting detail cut
- consistency of KPI meaning across both inherited outputs
- completeness of fields needed for concise audience-specific reshaping
- whether one explicit leadership-versus-external audience matrix can be stated cleanly

Those checks should be implemented as:
- aggregate-only SQL probes
- inherited compact outputs where available
- no broad row materialisation into memory

Decision rule:
- if the inherited reporting base is strong enough, proceed with the bounded leadership-and-external pack
- if not, add one compact reshaping layer rather than broadening the query footprint

## 5. Candidate Higher-Accountability Reporting Base

The first-pass reporting base should stay bounded and explicit.

Each component should have one stated purpose:
- leadership scope layer
  - define what leadership should see first
  - define the concise top-line structure
- external-style oversight layer
  - define what an external-style reader should receive
  - define what caveat posture travels with it
- release-control layer
  - define what checks must pass before either cut is safe to issue
- trust-boundary layer
  - define what the cuts inherit from Claire House `3.A` and `3.B`

If inherited outputs do not support one of those components cleanly, adapt by creating one compact higher-accountability reshaping layer rather than stretching earlier slice outputs past their truth boundary.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. inherited-base confirmation and audience-scope checks
2. leadership summary reshaping layer
3. external-style oversight cut reshaping layer
4. release and trust boundary layer
5. caveat, audience matrix, and regeneration packaging

The transformations should not be hidden inside one-off notebook rewriting or manual copy-paste reporting logic.

## 7. Bounded SQL Build Order

### Step 1. Confirm the inherited reporting base and audience-field coverage

Build small aggregate or profile queries only for:
- available reporting window fields
- KPI field stability
- supporting band or grouping coverage
- leadership-versus-external audience emphasis fields
- release-check and caveat-support fields

Goal:
- define the higher-accountability reporting pack honestly
- prove that both audience cuts can be supported from the same governed base without broad raw reconstruction

### Step 2. Materialise the leadership summary output

Create one bounded output, for example:
- `leadership_reporting_summary_v1`

This output should:
- retain the shared KPI family
- tighten the top-line summary for leadership reading
- include one concise `what matters next` emphasis
- remain small enough to act as a leadership pack rather than another general dashboard page

### Step 3. Materialise the external-style oversight cut

Create one bounded output, for example:
- `external_oversight_reporting_cut_v1`

This output should:
- retain the same KPI family and comparison basis
- tighten the phrasing and structure for external-style oversight use
- include one compact oversight-style table or cut
- remain bounded and controlled

### Step 4. Materialise the release and trust layer

Create one bounded output, for example:
- `leadership_external_release_checks_v1`

This output should:
- confirm shared KPI consistency across both audience cuts
- confirm the outputs still inherit the trusted Claire House `3.A` and `3.B` bases
- confirm the audience cuts are safe for bounded issue

## 8. Audience And Trust Strategy

The higher-accountability pack must remain small in conceptual scope but strong in control posture.

The first-pass audience strategy should answer:
- what does leadership need first?
- what does the external-style oversight audience need first?
- how are the same KPIs being emphasised differently?
- what caveats and trust conditions must travel with the outputs?

Decision rule:
- every retained field must earn its place in either:
  - leadership summary meaning
  - external-style oversight meaning
  - release or trust control
- if a field does not support one of those purposes, drop it

## 9. Reporting Product Strategy

Once the audience cuts are stable, package the slice into one compact higher-accountability reporting product.

The reporting proof should answer:
- what should leadership see first?
- what should the external-style audience receive?
- why are these not just reused internal charts with a different heading?

Required components:
- one leadership summary pack
- one external-style oversight cut
- one audience matrix
- one caveat and trust note
- analytical plots only if they clarify the audience-specific reporting truth

Create:
- `leadership_summary_pack_v1.md`
- `external_oversight_reporting_cut_v1.md`
- `leadership_external_audience_matrix_v1.md`

## 10. Documentation And Control Strategy

The slice is not complete unless another analyst could rerun the audience cuts responsibly.

The documentation and control pack should answer:
- what the leadership pack is for
- what the external-style oversight cut is for
- what the shared KPI family is
- what caveats travel with each audience cut
- what checks must pass before issue
- what the pack does and does not answer

Create:
- `leadership_external_reporting_scope_note_v1.md`
- `leadership_reporting_reading_note_v1.md`
- `external_oversight_reporting_use_note_v1.md`
- `leadership_external_caveats_v1.md`
- `leadership_external_trust_note_v1.md`
- `README_leadership_external_reporting_regeneration.md`
- `CHANGELOG_leadership_external_reporting.md`

## 11. Reproducibility Strategy

This slice is not complete unless the higher-accountability pack and its controls can be regenerated consistently.

The first-pass reproducibility pack should include:
- versioned SQL leadership-summary reshaping logic
- versioned SQL external-cut reshaping logic
- versioned SQL release-check logic
- one compact Python script only if needed for page assembly or analytical figure render
- one audience matrix
- one caveat or changelog note

The Python layer must remain:
- compact-output only
- not a substitute for broad analytical processing

That should be strong enough that another analyst could:
- understand the leadership and external audience cuts
- rerun both outputs
- regenerate the higher-accountability pack
- understand what the outputs are and are not safe to claim

## 12. Planned Deliverables

SQL and shaped data:
- one audience-scope and field-coverage query pack
- one leadership-summary query
- one external-oversight query
- one release-check query
- one compact leadership output
- one compact external-style oversight output
- one compact release-check output

Documentation:
- one reporting scope note
- one audience matrix
- one leadership reading note
- one external oversight-use note
- one caveats note
- one trust note
- one regeneration README

Reporting outputs:
- one leadership summary pack
- one external-style oversight cut
- analytical plots only if they help clarify the higher-accountability reporting truth

Expected output bundle for the first pass:
- one bounded leadership-and-external reporting pack
- one compact control and release pack
- one compact higher-accountability reporting proof

## 13. What To Measure For The Claim

For this requirement, the strongest measures are audience-specific reporting delivery, release control, and KPI consistency rather than analytical novelty.

Primary measure categories:
- number of audience-specific reporting views delivered
- number of KPI families reused consistently across those views
- number of release checks passed before issue
- one explicit audience matrix completed

Secondary measure categories:
- regeneration time for the compact higher-accountability pack
- one completed caveat and trust pack
- one completed leadership and external-use note set

## 14. Execution Order

1. Finalise the folder structure for this Claire House responsibility lane.
2. Run the inherited-base and audience-scope gate.
3. Decide the leadership-summary and external-style oversight cuts from the shared KPI base.
4. Materialise the leadership summary output.
5. Materialise the external-style oversight output.
6. Materialise the release-check layer.
7. Write the audience matrix, leadership note, external-use note, caveats note, trust note, changelog, and regeneration note.
8. Produce analytical plots only after the reporting outputs are stable.
9. Write the execution report and final claim surfaces only after the evidence is real.

## 15. Stop Conditions

Stop and reassess if any of the following happens:
- the Claire House `3.A` and `3.B` bases are too thin to support a higher-accountability audience cut honestly
- the chosen KPI family becomes inconsistent across leadership and external-style outputs
- the external-style cut starts sounding like a fake regulatory submission or broad compliance programme
- the slice starts drifting into whole-estate board, trustee, or external-reporting ownership rather than bounded support
- the query posture starts requiring broad raw-data loads or memory-heavy dataframe work that should have been handled in bounded SQL instead
- the figures start becoming decorative rather than analytical support for the higher-accountability reporting truth

If one of those happens, the adaptation path is:
- keep the same responsibility lane
- name the actual blocker clearly
- narrow the audience cut or reduce the output footprint if needed
- preserve the center of gravity around one bounded leadership pack and one bounded external-style oversight cut from a trusted reporting base

## 16. What This Plan Is And Is Not

This is:
- a concrete execution plan for the third Claire House responsibility slice
- audience-first
- concise
- bounded
- aligned to leadership and external-style reporting support from a trusted reporting base

This is not:
- the execution report
- a broad board-reporting programme
- a full regulatory or compliance reporting function
- permission to force leadership-style packaging where the bounded evidence does not support it

The first operational move after this plan should be:
- run the inherited-base and audience-scope gate and decide whether the Claire House `3.A` and `3.B` outputs can support one honest leadership summary pack plus one external-style oversight cut without reopening a broad raw analytical rebuild
