# Execution Plan - Trend Risk And Opportunity Identification Slice

As of `2026-04-04`

Purpose:
- turn the chosen InHealth trend / risk / opportunity slice into a concrete execution order tied to bounded governed analytical outputs already available in the repo
- keep the work interpretation-first, trend-first, and tightly scoped to one rolling monthly operational lane rather than broad service-improvement or broad reporting-estate work
- prove identification of meaningful movement, risk, or opportunity without drifting into full process-improvement ownership
- keep execution memory-safe by shaping only the bounded months, fields, and aggregates required for the slice rather than treating the raw run like unlimited in-memory working space

Execution substrate:
- governed local artefacts already available in `artefacts/analytics_slices/`
- compact monthly outputs already established from InHealth `01_reporting_support_for_operational_and_regional_teams`
- maintained dataset truth already established from InHealth `02_patient_level_dataset_stewardship` where that trust layer is needed
- new slice outputs to be written under `artefacts/analytics_slices/data_analyst/inhealth_group/03_trend_risk_and_opportunity_identification/`

Primary rule:
- define the rolling trend question first
- pin the bounded KPI family before packaging any figures or narrative
- build the rolling monthly comparison output first
- identify one concentrated risk or opportunity pocket second
- package the evidence set only after the analytical reading is stable
- keep improvement language at identification level only so the slice does not pre-empt InHealth `3.E`
- never load broad raw monthly surfaces into pandas or any other in-memory dataframe layer before the SQL gate has already reduced them to compact trend-ready outputs

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- the repo already contains a stable monthly lane suitable for rolling trend analysis without rebuilding a broad raw analytical base
- one rolling three-month comparison can be defined honestly from the available period coverage
- one small KPI family is enough to identify a meaningful trend, risk, or opportunity pocket
- one segment or amount-band lens is stable enough to support a bounded attention point
- the slice can remain at identification level without needing broader service-improvement proof

Candidate first-pass reusable foundations:
- InHealth `01_reporting_support_for_operational_and_regional_teams` monthly summary and follow-up outputs
- InHealth `02_patient_level_dataset_stewardship` protected current-month pattern where trust validation is needed
- compact monthly aggregates already proven safe to regenerate from bounded SQL logic

Working assumption about the bounded analytical question:
- the rolling monthly lane should be read for:
  - stable versus changing movement
  - concentrated risk or opportunity
  - where operational attention should go first
- the slice should stop at `identification and framing`, not `improvement ownership`

Important warning:
- those assumptions must be tested rather than carried forward casually
- if the rolling three-month shape is not analytically useful enough, narrow to the strongest honest trend window rather than inventing a bigger story

## 2. Interpretation-First Posture

This slice must not begin as figure-first, recommendation-first, or process-improvement-first work.

The correct posture is:
- define the rolling trend question first
- define the KPI family and period window first
- materialise one rolling comparison view first
- identify the strongest trend, risk, or opportunity pocket second
- package the evidence into figures only after the pattern is analytically stable
- write implication notes only after the bounded attention point is clear

This matters because the InHealth responsibility here is about identifying trends, risks, and opportunities in data, not about producing another recurring pack or jumping straight to operational remedies.

## 2A. Memory And Query Discipline

This slice must be executed with explicit memory discipline.

The raw run contains very large monthly surfaces, so the correct posture is:
- do not pull broad raw parquet surfaces into pandas
- do not run wide exploratory queries across full history unless the slice truly needs them
- do not assume a rolling monthly slice justifies loading all months into memory

The correct query discipline is:
- start with summary-stats and period profiling before any rolling-window build
- use `DuckDB` or SQL-style scans with predicate pushdown
- filter the rolling period at scan time
- project only the fields needed for:
  - KPI shaping
  - segment concentration reading
  - trend direction checks
  - any trust caveat checks
- materialise compact intermediate outputs only after the filtered SQL logic is stable
- let Python read only those compact outputs, not the raw source families

The default execution ceiling for this slice is:
- three bounded months only
- bounded field selection only
- one controlled intermediate output at a time

If a query starts behaving like broad exploratory profiling rather than bounded rolling trend construction, stop and narrow it before proceeding.

The required first-pass summary profiling layer is:
- row counts by month for each candidate source used in the slice
- period coverage for the rolling comparison window
- key and segment coverage for the candidate focus lens
- null rates for fields required by the KPI family
- grain and field-meaning confirmation before any wider transformation logic is written

## 3. First-Pass Objective

The first-pass objective is:

`build one rolling monthly comparison and one concentrated risk-or-opportunity focus view for a bounded programme lane, with enough analytical evidence to support a clear attention point`

The proof object is:
- `trend_risk_and_opportunity_identification_v1`

The first-pass output family is:
- one trend question note
- one rolling monthly comparison output
- one focused risk or opportunity output
- one trend reading note
- one implication note
- one compact two-figure evidence set
- one caveat or usage note

## 4. Early Scope Gate

Before building any figure or interpretation note, run a bounded scope gate.

The first profiling pass must answer:
- which existing monthly outputs are stable enough to support a rolling three-month reading?
- what exact months can be compared honestly from the available data?
- which KPI fields are stable enough to carry one clear trend story?
- which segment or amount-band dimension is stable enough to support a concentrated risk or opportunity focus?
- does the lane show:
  - broad deterioration
  - broad improvement
  - concentrated risk
  - concentrated opportunity
  - or mostly routine movement?
- what do the row counts, period coverage, key coverage, and null rates say about the safe scope of the slice before any heavier build begins?

Required checks:
- month-level coverage across the candidate monthly source family
- field availability for the candidate KPI family
- consistency of KPI meaning across the rolling window
- stability of the candidate focus segment dimension
- whether one compact rolling trend view can be regenerated from the same governed logic base

Those checks should be implemented as:
- aggregate-only SQL probes
- filtered month-level scans
- no broad row materialisation into memory

Decision rule:
- if one rolling monthly source family is stable enough, proceed with the bounded trend/risk/opportunity slice
- if not, adapt by shaping a lighter monthly comparison layer rather than broad new reconstruction

## 5. Candidate Analytical Base

The first-pass analytical base should stay bounded and explicit.

Each component should have one stated purpose:
- rolling monthly KPI base
  - show recent movement over time
  - keep KPI meaning fixed
- focus view
  - isolate the strongest risk or opportunity pocket
  - keep the same KPI logic
- interpretation layer
  - trend note
  - risk or opportunity note
- caveat layer
  - what should and should not be overread from the slice

If the reused outputs do not support one of those components cleanly, adapt by creating a small local trend-reading layer rather than stretching earlier slice outputs past their truth boundary.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. rolling period and field-suitability checks
2. rolling monthly KPI comparison build
3. concentrated risk or opportunity focus build
4. compact evidence-pack shaping
5. trend and implication note writing
6. caveat and regeneration packaging

The transformations should not be hidden inside one-off notebook reshaping or manual interpretation logic.

## 7. Bounded SQL Build Order

### Step 1. Create a rolling-scope and field-suitability layer

Build small aggregate or profile queries only for:
- available month labels
- candidate KPI-field availability
- month-to-month coverage
- stable segment or band dimension availability
- trust suitability of the fields used in the trend reading

Goal:
- define the rolling monthly trend slice honestly
- prove that the comparison and focus views can come from one governed logic base

### Step 2. Materialise a rolling monthly comparison view

Create one bounded SQL output, for example:
- `monthly_trend_compare_v1`

This output should include:
- month label
- bounded lane identifier
- compact KPI family
- rolling period order
- enough information to compare:
  - current position
  - recent movement
  - stable versus changing patterns

### Step 3. Materialise the risk-or-opportunity focus view

Create one bounded SQL output, for example:
- `monthly_risk_opportunity_focus_v1`

This output should:
- derive from the same governed monthly logic
- isolate the strongest concentrated pattern
- keep KPI meanings unchanged
- support one bounded analytical conclusion about where attention should go first

## 8. KPI Strategy

The KPI family must remain small and stable.

The first-pass KPI set should cover only what the trend question genuinely needs, likely:
- volume or pressure
- conversion or progression
- one downstream quality signal
- one concentration lens by segment or amount band

The first-pass analytical reading should answer:
- what is the recent monthly direction of travel?
- what has remained stable?
- what concentration pocket stands out most?
- does the evidence support a risk story, an opportunity story, or mostly stability?

Decision rule:
- every KPI must support the rolling trend question
- if a metric does not materially help answer that question, drop it

## 9. Evidence-Pack Strategy

Once the rolling comparison and focus view are stable, package the slice into one compact evidence set.

The evidence set should answer:
- what has happened across the recent monthly window?
- what should the reader not overread as broad deterioration or improvement?
- where is the strongest concentrated attention point?

Required components:
- one rolling trend-context figure
- one focused risk or opportunity figure
- one short trend reading note
- one short risk or opportunity note

Create:
- `trend_risk_evidence_pack_v1.md`
- `trend_reading_note_v1.md`
- `risk_or_opportunity_note_v1.md`

## 10. Analytical-Framing Strategy

This slice is not complete unless the identified pattern is framed correctly.

The framing note should answer:
- is this broad deterioration, concentrated risk, concentrated opportunity, or mostly stability?
- what should operational readers watch next?
- what should not be overclaimed from this slice?

Important boundary:
- do not convert the slice into process or efficiency improvement ownership yet
- the wording should stop at:
  - identified pattern
  - likely risk or opportunity
  - where attention should go first

## 11. Reproducibility Strategy

This slice is not complete unless the rolling comparison and focus outputs can be regenerated consistently.

The first-pass reproducibility pack should include:
- versioned SQL build logic for the rolling trend view
- versioned SQL build logic for the focus view
- one compact Python script only if needed for compact figure render or table export
- one usage or caveat note
- one regeneration README

The Python layer must remain:
- compact-output only
- figure and note generation only
- not a substitute for broad raw-data processing

That should be strong enough that another analyst could:
- understand the rolling monthly question
- rebuild the trend view
- rebuild the focus view
- regenerate the figures
- understand what the slice is and is not safe to claim

## 12. Planned Deliverables

SQL and shaped data:
- one field-suitability and period-scope query pack
- one rolling monthly trend build query
- one risk-or-opportunity focus build query
- one compact rolling trend output
- one compact focus output

Documentation:
- one trend question note
- one trend reading note
- one risk or opportunity note
- one caveat or usage note
- one regeneration README

Evidence figures:
- one rolling-month context figure
- one focused risk or opportunity figure

## 13. Execution Stop Conditions

Stop and reassess if any of the following happen:
- the rolling monthly data does not support a stable three-month comparison
- the slice starts depending on broad raw-history reloads rather than bounded monthly outputs
- the identified pattern turns out to be mostly a trust or field-definition issue rather than a real operational signal
- the slice starts drifting into full improvement ownership rather than trend / risk / opportunity identification

If any of those conditions occur:
- narrow the month window
- narrow the KPI family
- downgrade the claim to a smaller but more truthful analytical reading
- or pause and explicitly pivot the slice posture before proceeding

## 14. Immediate Execution Order

The correct build order remains:
1. profile the rolling monthly coverage and fix the KPI family
2. build one rolling monthly comparison output
3. identify one concentrated risk or opportunity focus view
4. package the trend and focus views into a compact evidence set
5. add trend, implication, caveat, and regeneration notes

That order matters because it prevents the slice from collapsing into generic commentary or premature improvement language before the actual analytical pattern is established.
