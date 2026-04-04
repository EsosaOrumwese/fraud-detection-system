# Execution Plan - Process And Efficiency Improvement Support Slice

As of `2026-04-04`

Purpose:
- turn the chosen InHealth process and efficiency improvement-support slice into a concrete execution order tied to bounded governed analytical outputs already available in the repo
- keep the work interpretation-first, recommendation-support-first, and tightly scoped to one already-identified `50_plus` issue rather than broad service-improvement ownership
- prove that a recurring analytical pattern can be translated into a realistic targeted review recommendation without drifting into claims that the process was already improved
- keep execution memory-safe by reusing compact `3.D` outputs first and only allowing additional bounded SQL probes if the improvement-support question genuinely needs them

Execution substrate:
- governed local artefacts already available in `artefacts/analytics_slices/`
- compact monthly outputs already established from InHealth `01_reporting_support_for_operational_and_regional_teams`
- trusted monthly interpretation already established from InHealth `02_patient_level_dataset_stewardship`
- recurring `50_plus` risk evidence already established from InHealth `03_trend_risk_and_opportunity_identification`
- new slice outputs to be written under `artefacts/analytics_slices/data_analyst/inhealth_group/04_process_and_efficiency_improvement_support/`

Primary rule:
- define the improvement-support question first
- reuse the existing trusted rolling trend lane before building anything new
- prove the operational burden interpretation before packaging any recommendation
- make one explicit targeted review recommendation second
- package the evidence set only after the analytical and recommendation posture is stable
- keep the language at `support review / support improvement discussion` level only so the slice does not overclaim operational change delivery
- never load broad raw monthly surfaces into pandas or any other in-memory dataframe layer before the SQL gate has already reduced them to compact outputs

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- the repo already contains enough trusted rolling-month evidence from InHealth `3.D` to support an efficiency-support reading without a heavy raw rebuild
- the recurring `50_plus` pressure-versus-quality pattern is strong enough to support one targeted review recommendation
- the recommendation can remain bounded to:
  - review
  - attention
  - prioritisation
  - follow-up
  and does not need to claim that a process change was implemented
- one small KPI family is enough to support the burden-versus-yield interpretation
- one compact evidence pack is enough to support the slice

Candidate first-pass reusable foundations:
- InHealth `03_trend_risk_and_opportunity_identification` monthly trend comparison output
- InHealth `03_trend_risk_and_opportunity_identification` monthly risk-focus output
- InHealth `01_reporting_support_for_operational_and_regional_teams` monthly lane logic where stable KPI meaning needs confirmation
- InHealth `02_patient_level_dataset_stewardship` trust boundary where any deeper interpretation needs protection from raw-grain misreading

Working assumption about the bounded analytical question:
- the slice should read the recurring `50_plus` pattern as:
  - concentrated effort burden
  - weaker quality return
  - targeted review priority
- the slice should stop at `improvement-support interpretation and recommendation`, not `improvement ownership`

Important warning:
- those assumptions must be tested rather than carried forward casually
- if the existing `3.D` outputs are not enough to support the improvement-support reading, add only the smallest new SQL probe required to answer the question

## 2. Improvement-Support-First Posture

This slice must not begin as:
- figure-first
- action-slogan-first
- or broad process-redesign-first work

The correct posture is:
- define the improvement-support question first
- confirm the bounded recurring issue from `3.D`
- build one burden-versus-yield interpretation second
- frame one targeted review recommendation third
- package the evidence into figures only after the recommendation remains proportional to the data
- write challenge and caveat notes only after the recommendation wording is stable

This matters because the InHealth responsibility here is about supporting process or efficiency improvement with analysis, not about claiming ownership of operational redesign.

## 2A. Memory And Query Discipline

This slice must be executed with explicit memory discipline.

The correct posture is:
- do not pull broad raw parquet surfaces into pandas
- do not rescan the full monthly raw lane if compact `3.D` outputs already answer the improvement-support question
- do not assume a process-improvement slice justifies a larger rebuild than the trend-identification slice

The correct query discipline is:
- start with compact-output profiling before any new raw probe
- use `DuckDB` or SQL-style scans with predicate pushdown if a new probe is needed
- filter the rolling period at scan time
- project only the fields needed for:
  - burden-versus-yield comparison
  - focus-band comparison
  - recommendation support
  - challenge or caveat checks
- materialise compact intermediate outputs only after the filtered SQL logic is stable
- let Python read only those compact outputs, not the raw source families

The default execution ceiling for this slice is:
- reuse existing `Jan 2026 -> Mar 2026` compact outputs first
- one controlled new compact output at a time if required
- no broad row-level monthly materialisation

If the slice starts behaving like a fresh raw rebuild rather than a bounded extension of `3.D`, stop and narrow it before proceeding.

The required first-pass profiling layer is:
- row counts and shape of the compact `3.D` outputs
- month coverage of the existing rolling window
- stability of the focus-band reading
- availability of any extra field needed to support the improvement-support interpretation
- confirmation that the recommendation can be defended from compact outputs alone before any raw probe is added

## 3. First-Pass Objective

The first-pass objective is:

`build one bounded improvement-support interpretation and one explicit targeted review recommendation for the recurring 50_plus issue, with enough evidence to justify attention without claiming change delivery`

The proof object is:
- `process_and_efficiency_improvement_support_v1`

The first-pass output family is:
- one improvement question note
- one compact burden-versus-yield output
- one targeted review output
- one efficiency interpretation note
- one recommendation note
- one challenge-response note
- one compact two-figure evidence set
- one caveat or usage note

## 4. Early Scope Gate

Before building any figure or recommendation note, run a bounded scope gate.

The first profiling pass must answer:
- do the compact `3.D` outputs already prove the persistent `50_plus` burden strongly enough to support improvement framing?
- which exact metrics best support:
  - effort burden
  - weaker yield
  - targeted review need
- does the evidence support:
  - broad lane-wide action
  - or focused review of one concentration pocket?
- what do the compact row counts, month coverage, and peer-gap stability say about the safe scope of the slice before any heavier build begins?
- is any new SQL output required, or can the slice stay fully downstream of `3.D`?

Required checks:
- month-level persistence of the focus band
- consistency of KPI meaning across the reused outputs
- stability of peer gaps for the focus band
- whether one compact improvement-support view can be regenerated from the same governed logic base
- whether the recommendation can stay at review/support level rather than implicit process-ownership level

Those checks should be implemented as:
- compact-output profiling
- aggregate-only SQL probes if needed
- no broad raw row materialisation into memory

Decision rule:
- if the `3.D` outputs already support one bounded improvement-support interpretation, proceed with the extension slice
- if not, adapt by adding only the smallest compact peer-gap or burden-support layer needed

## 5. Candidate Analytical Base

The first-pass analytical base should stay bounded and explicit.

Each component should have one stated purpose:
- improvement-support base
  - show why the recurring issue plausibly creates avoidable effort or weaker efficiency
- targeted review view
  - show why focused review is more defensible than broad lane-wide escalation
- interpretation layer
  - efficiency note
  - review recommendation note
- challenge layer
  - what the recommendation does and does not claim

If the reused outputs do not support one of those components cleanly, adapt by creating a small local improvement-support layer rather than stretching earlier slice outputs past their truth boundary.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. compact-output suitability and recommendation-scope checks
2. improvement-support comparison build
3. targeted review output build
4. compact evidence-pack shaping
5. interpretation and recommendation note writing
6. challenge, caveat, and regeneration packaging

The transformations should not be hidden inside one-off notebook reshaping or manual recommendation logic.

## 7. Bounded SQL Build Order

### Step 1. Profile compact outputs and recommendation suitability

Build small profile queries or direct compact-output checks only for:
- available month labels
- persistence of the focus band
- peer-gap stability
- bounded support for:
  - concentrated burden
  - weaker yield
  - targeted review need

Goal:
- define the improvement-support slice honestly
- prove that the recommendation can come from one governed logic base

### Step 2. Materialise an improvement-support comparison view

Create one bounded SQL output if needed, for example:
- `efficiency_support_compare_v1`

This output should include:
- month label
- focus-band identifier
- peer comparison
- burden-versus-yield comparison
- enough information to explain why the issue supports targeted review

If the compact `3.D` outputs already satisfy this shape cleanly, do not create a redundant new view.

### Step 3. Materialise the targeted review output

Create one bounded SQL or compact derived output, for example:
- `targeted_review_support_v1`

This output should:
- derive from the same governed improvement-support logic
- keep KPI meanings unchanged
- support one bounded analytical conclusion about why focused review is more defensible than broad lane-wide escalation

## 8. KPI Strategy

The KPI family must remain small and stable.

The first-pass KPI set should cover only what the improvement-support question genuinely needs, likely:
- volume or share of the focus band
- case-opening pressure
- one downstream quality or yield signal
- one peer-gap view

The first-pass analytical reading should answer:
- does the recurring issue imply concentrated effort burden?
- does it imply weaker operational yield than peers?
- is the evidence strong enough to justify targeted review?
- does the evidence justify broad escalation? If not, why not?

Decision rule:
- every KPI must support the improvement-support question
- if a metric does not materially help answer that question, drop it

## 9. Evidence-Pack Strategy

Once the improvement-support interpretation and targeted review output are stable, package the slice into one compact evidence set.

The evidence set should answer:
- why does the recurring `50_plus` issue matter for process or efficiency discussion?
- why is targeted review the right bounded response?
- what should the reader not overclaim from this slice?

Required components:
- one burden-versus-yield figure
- one targeted-review-versus-broad-escalation figure
- one short efficiency interpretation note
- one short targeted review recommendation note

Create:
- `process_efficiency_evidence_pack_v1.md`
- `efficiency_interpretation_note_v1.md`
- `targeted_review_recommendation_v1.md`
- `challenge_response_note_v1.md`

## 10. Analytical-Framing Strategy

This slice is not complete unless the recommendation is framed correctly.

The framing note should answer:
- what kind of inefficiency or weaker yield is the pattern suggesting?
- why is targeted review the correct next step?
- what should not be overclaimed as delivered improvement?

Important boundary:
- do not convert the slice into claimed process ownership
- do not imply quantified efficiency gains were achieved
- the wording should stop at:
  - bounded interpretation
  - targeted review recommendation
  - challenge and caveat framing

## 11. Reproducibility Strategy

This slice is not complete unless the improvement-support and recommendation outputs can be regenerated consistently.

The first-pass reproducibility pack should include:
- versioned SQL build logic for any new improvement-support view
- versioned SQL build logic for the targeted review output if needed
- one compact Python script only if needed for compact figure render or table export
- one usage or caveat note
- one regeneration README

The Python layer must remain:
- compact-output only
- figure and note generation only
- not a substitute for broad raw-data processing

That should be strong enough that another analyst could:
- understand the improvement-support question
- rebuild the comparison and recommendation outputs
- regenerate the figures
- understand what the slice is and is not safe to claim

## 12. Planned Deliverables

SQL and shaped data:
- one compact-output suitability and scope query pack
- one improvement-support build query if needed
- one targeted review support build query if needed
- one compact improvement-support output
- one compact recommendation-support output

Documentation:
- one improvement question note
- one efficiency interpretation note
- one targeted review recommendation note
- one challenge-response note
- one caveat or usage note
- one regeneration README

Evidence figures:
- one concentrated burden-versus-yield figure
- one targeted-review support figure

## 13. Execution Stop Conditions

Stop and reassess if any of the following happen:
- the compact `3.D` outputs are not strong enough to support a recommendation and the slice starts requiring a broad raw rebuild
- the evidence does not support a targeted review recommendation strongly enough
- the slice starts drifting into claimed process-change ownership
- the interpretation turns out to be mostly speculative rather than grounded in the bounded peer-gap evidence

If any of those conditions occur:
- narrow the recommendation
- narrow the KPI family
- downgrade the slice to a smaller but more truthful improvement-support reading
- or pause and explicitly pivot the slice posture before proceeding

## 14. Immediate Execution Order

The correct build order remains:
1. profile the compact `3.D` outputs and confirm recommendation suitability
2. build one improvement-support interpretation output if needed
3. build one targeted review support output if needed
4. package the outputs into a compact evidence set
5. add interpretation, recommendation, challenge, caveat, and regeneration notes

That order matters because it prevents the slice from collapsing into vague action language or premature process-ownership claims before the actual bounded improvement-support case is established.
