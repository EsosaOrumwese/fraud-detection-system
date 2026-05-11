# Trend Risk And Opportunity Identification Execution Slice - InHealth Group Data Analyst Requirement

As of `2026-04-04`

Purpose:
- capture the chosen bounded slice for the InHealth requirement around identifying trends, risks, and opportunities in operational data
- keep the note aligned to the actual InHealth responsibility rather than drifting into broad service-improvement ownership, generic commentary, or another recurring-reporting slice
- preserve the distinction between this slice and InHealth `3.A` by making this one about analytical reading of movement and emerging issues, not about monthly pack delivery itself

Boundary:
- this note is not an accomplishment record
- this note is not a claim that a broad InHealth trend-monitoring estate has already been implemented
- this note captures the chosen slice, why it fits the requirement, which lenses own it, and what the proof burden should be
- execution should begin from bounded rolling-month aggregates and governed monthly outputs where appropriate, rather than broad raw reloads or unnecessary row-level rebuilds

Placement rule:
- this file lives under the role-shaped lens tree because it is execution-depth material, not a top-level lens definition
- the role folder should hold multiple employer lanes over time
- the employer folder should hold one folder per targeted responsibility slice so repeated work stays grouped and readable

Primary source basis:
- [01_operational-performance-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\01_operational-performance-analytics.md)
- [02_bi-insight-reporting-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\02_bi-insight-reporting-analytics.md)
- [05_business-analysis-change-decision-support.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\05_business-analysis-change-decision-support.md)
- [03_data-quality-governance-trusted-information-stewardship.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\03_data-quality-governance-trusted-information-stewardship.md)
- [data-analytics-engineering-science.ideal-candidate-profiles.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.ideal-candidate-profiles.md)
- [data-analytics-engineering-science.job-ads.evidence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.job-ads.evidence.md)

---

## 1. Requirement Being Targeted

The requirement being targeted here is the InHealth `Data Analyst` expectation around:
- identifying trends in operational data
- spotting risk or opportunity in those trends
- surfacing what deserves attention
- turning raw movement into a bounded analytical reading rather than passive reporting

This maps directly to the InHealth candidate-profile requirement that the analyst should be able to describe:
- reviewing operational data for meaningful trends
- identifying risks, issues, or improvement opportunities early enough to matter
- distinguishing between stable operating movement and signals that deserve attention
- supporting teams with evidence-led interpretation rather than only recurring report production

This note exists because that requirement is easy to flatten into the vague statement `good at analysing data`. The employer is asking for something narrower and more useful:
- detect what is actually changing over time
- identify whether the change is a risk, an opportunity, or ordinary variation
- surface where attention should go first

## 2. The Analogue On The Current Platform

The current platform does not contain literal patient pathways or healthcare waiting-list measures, so the slice has to use an honest analogue.

The closest truthful analogue is:
- a rolling monthly programme lane
- stable conversion and quality KPIs already established in InHealth `3.A`
- bounded segment or amount-band structure that can carry:
  - trend movement
  - risk concentration
  - opportunity concentration

So for this slice:
- `trend, risk, and opportunity identification` in the employer wording maps to `rolling monthly operational-pattern reading` on the current platform
- the proof burden is the same:
  - compare periods carefully
  - find what is stable versus what is changing
  - identify the strongest risk or opportunity pocket
  - support a bounded analytical conclusion

The claim must therefore remain:
- healthcare-role shaped
- platform-truth bounded
- careful not to imply direct healthcare service improvement ownership where this slice only proves analytical identification

## 3. Lens Stack For This Requirement

The cleanest lens stack for this InHealth `3.D` requirement is:

**Primary**
- `01 - Operational Performance Analytics`

**Strong support**
- `02 - BI, Insight, and Reporting Analytics`

**Support**
- `05 - Business Analysis, Change, and Decision Support`

**Light support where needed**
- `03 - Data Quality, Governance, and Trusted Information Stewardship`

Why this stack fits:

`01` is the main owner because the requirement is explicitly about:
- reading operational movement over time
- identifying patterns, risk, or opportunity
- spotting where service attention should go

That is directly `01` territory:
- KPI movement interpretation
- trend reading
- bottleneck or burden pattern identification
- distinguishing stable position from emerging operational concern

`02` matters because the identified trend still has to be packaged into a usable analytical output:
- rolling comparisons
- concise evidence views
- focused trend or exception figures
- readable issue summaries rather than dense metric dumps

`05` matters because this responsibility is not only about saying `something moved`. It is about understanding:
- why the pattern matters
- whether it represents risk or opportunity
- what kind of attention it should trigger

`03` is not a main owner, but it becomes useful if a suspected trend turns out to be partly explained by a trust or field-definition issue rather than a genuine operational change. The default posture should still be performance interpretation first.

So the practical reading is:
- `01` identifies and interprets the trend
- `02` packages the evidence cleanly
- `05` frames why the pattern matters as risk or opportunity
- `03` protects against mistaking a trust defect for a trend if needed

Ownership order:
- `01 -> 02 -> 05 -> 03`

Best execution order:
- `01 -> 02 -> 05 -> 03`

That execution order matters because the slice has to establish the operational pattern before it can be framed as a risk or opportunity, and only then should trust escalation be used if the pattern appears analytically unstable.

## 4. Chosen Bounded Slice

The cleanest bounded slice for this InHealth requirement is:

`one rolling monthly trend-and-risk reading for a single programme lane over three bounded months`

In the fraud-platform analogue, that means:
- select one bounded programme-style lane
- compare a short rolling monthly window:
  - `Jan 2026`
  - `Feb 2026`
  - `Mar 2026`
- keep the KPI family intentionally small
- identify one concentrated risk or opportunity pocket within that lane
- stop at analytical identification rather than full improvement ownership

The slice should answer one narrow question:
- `what trend, risk, or opportunity is actually visible across the recent monthly lane, and where is the strongest evidence that operational attention is needed?`

That means the slice should produce:
- one rolling monthly KPI view
- one trend note
- one risk or opportunity note
- one bounded focus view for the strongest pocket
- one compact evidence pack

This slice is the best analogue for the InHealth requirement because it proves:
- period-over-period reading
- operational pattern identification
- bounded risk or opportunity surfacing
- disciplined analytical attention rather than generic commentary

## 5. Why This Slice Was Chosen

This slice was chosen because it gives direct room for:
- proving you can interpret movement over time rather than just publish the monthly pack
- distinguishing a stable topline from a concentrated risk or opportunity pocket
- surfacing one credible attention area without overclaiming service-improvement ownership
- building naturally from InHealth `3.A` without duplicating it

It also avoids the wrong kinds of drift.

The intention is not to:
- repeat InHealth `3.A` as another reporting-delivery slice
- jump early into process-improvement ownership, which belongs more naturally to InHealth `3.E`
- create a broad forecasting or advanced-modelling exercise
- force a dramatic deterioration story where the bounded evidence does not support one
- produce decorative charts that do not change the analytical reading

The intention is to prove one sharper statement:
- I can identify meaningful trends, risks, and opportunities in a bounded operational lane and surface where attention should go first

## 6. Relationship To Earlier Slices

This slice can and should build on already established proof where that is the honest choice.

Most importantly, it can legitimately build on:
- InHealth `01_reporting_support_for_operational_and_regional_teams` as the monthly lane already shaped for recurring reporting
- InHealth `02_patient_level_dataset_stewardship` where the maintained case-linked dataset protects the trust of the monthly reading

But this slice is not a copy of either one.

The difference is:
- InHealth `3.A` proved monthly and ad hoc reporting support
- InHealth `3.C` proved careful detailed-dataset stewardship under that reporting lane
- InHealth `3.D` should prove that the data can be read for trends, risks, and opportunities rather than only delivered accurately

This also makes the slice the correct precursor to InHealth `3.E`:
- `3.D` should end with a bounded analytical reading and the strongest attention point
- `3.E` can then build from that into process or efficiency improvement support

## 7. Execution Posture

The default execution stack for this slice is:
- summary-stats and period profiling first
- SQL for rolling monthly KPI shaping and compact segment views
- Python only after the rolling outputs have been reduced to compact aggregates
- markdown notes for trend reading, risk or opportunity interpretation, and bounded attention framing

The execution substrate should be:
- governed monthly outputs already established where suitable
- rolling three-month aggregates rather than broad raw monthly extracts into memory
- explicit field projection and bounded period filters
- compact extracts suitable for figures and concise analytical notes

The default local working assumption is:
- large raw surfaces stay in the query engine
- profiling comes before rolling-window materialisation
- the slice should reuse trustworthy monthly logic where possible rather than rebuild a broad lane-level base for no reason

The reporting posture should remain:
- figure-supportive rather than dashboard-forcing
- trend-and-risk focused
- compact enough that the slice still reads as one bounded analytical judgment

## 8. Lens-by-Lens Execution Checklist

### 8.1 Lens 01 - Identify the operational trend, risk, or opportunity

This is the core owner.

Tasks:
1. Fix the rolling period window explicitly:
- one current month
- two comparison months
2. Define a small KPI family:
- flow volume or pressure
- conversion or progression
- one downstream quality signal
- one concentration or segment lens
3. Build one rolling monthly comparison view.
4. Identify one clear analytical pattern:
- stable
- worsening
- improving
- concentrated
- broad-based
5. Write one short trend note:
- what moved
- what stayed stable
- why that matters
6. Write one short risk or opportunity note:
- where the strongest concentration sits
- why it deserves attention first

### 8.2 Lens 02 - Package the trend reading into usable evidence

This is the main support lens.

Tasks:
1. Build one compact evidence pack:
- one rolling-month context figure
- one focused risk or opportunity figure
2. Keep the figure set small enough that the reader can grasp the issue quickly.
3. Keep KPI naming stable between the trend view and the focus view.
4. Make the figures supplementary rather than pseudo-dashboard pages.
5. Add one short usage note if the figures need context to be read correctly.

### 8.3 Lens 05 - Frame why the pattern matters

This lens turns pattern reading into a useful analytical conclusion.

Tasks:
1. Define the analytical decision question:
- what kind of attention should this trend trigger?
2. Distinguish between:
- broad deterioration
- concentrated risk
- efficiency opportunity
- routine fluctuation
3. Write one bounded implication note:
- what should be watched next
- what should not be overread from this slice
4. Keep the framing at `identification` level only so the slice does not drift into `3.E`.

### 8.4 Lens 03 - Escalate only if trust instability affects the trend

This lens is optional light support only.

Tasks:
1. Check whether the identified pattern depends on unstable fields or definitions.
2. Record one trust caveat if necessary.
3. Avoid turning the slice into another stewardship or discrepancy-handling exercise unless the trend is genuinely contaminated by a data issue.

## 9. Suggested Artifact Pack

The minimum credible proof pack for this slice is:
- one trend question note
- one rolling monthly comparison output
- one concentrated risk or opportunity output
- one trend note
- one risk or opportunity note
- one compact two-figure evidence pack
- one caveat or usage note

That is enough to prove:
- trend reading
- risk or opportunity identification
- bounded analytical interpretation
- usable evidence packaging

## 10. Suggested Artifact Names

These names are placeholders, not fixed schema requirements.

Trend and focus assets:
- `trend_question_note_v1.md`
- `vw_monthly_trend_compare_v1.sql`
- `vw_monthly_risk_opportunity_focus_v1.sql`
- `monthly_trend_compare_v1.parquet`
- `monthly_risk_opportunity_focus_v1.parquet`
- `trend_reading_note_v1.md`
- `risk_or_opportunity_note_v1.md`

Evidence-pack assets:
- `monthly_trend_context_v1.png`
- `risk_or_opportunity_focus_v1.png`
- `trend_risk_evidence_pack_v1.md`

Control and usage assets:
- `trend_usage_note_v1.md`
- `trend_caveats_v1.md`
- `README_trend_risk_regeneration.md`

## 11. Definition Of Done

This slice should be treated as complete only when all of the following are true:
- one rolling monthly comparison has been built
- one bounded KPI family has been fixed
- one trend note exists
- one concentrated risk or opportunity pocket has been identified
- one risk or opportunity note exists
- one compact figure set exists
- the slice clearly distinguishes stable top line from the identified attention point
- the result stops at analytical identification rather than drifting into improvement ownership

## 12. Truth Boundary

As of this note, the correct claim is:
- the slice has been selected
- the lens mapping is clear
- the execution path is defined
- the bounded trend/risk/opportunity proof object has been chosen

The correct claim is not:
- that a broad operational-improvement programme has already been implemented
- that every emerging trend in the lane has already been identified
- that the slice already proves process change outcomes
- that all future monthly movement will be monitored automatically without review

This note therefore exists to protect against overclaiming while preserving a fast path toward a defensible claim.

## 13. What To Measure For The Eventual `Y`

For this requirement, the strongest `Y` values are:
- number of months compared in one bounded rolling trend view
- number of KPI families kept stable across the trend reading
- one explicit risk or opportunity pocket identified
- one bounded analytical recommendation about where attention should go next
- regeneration time for the rolling trend and focus outputs

A strong small `Y` set would be:
- `[N]` bounded months compared through one rolling analytical view
- `[K]` KPI families kept stable across the trend reading
- one explicit risk or opportunity pocket identified for follow-up attention
- one rolling trend and focus pack regenerated in `[T]` minutes

## 14. XYZ Claim Surfaces This Slice Is Aiming Toward

This section is included here because the slice definition needs to preserve the exact claim shape the execution is aiming toward, not just the structural checklist.

### 14.1 Full flagship `X by Y by Z` version

> Identified meaningful trends, risks, and opportunities in a bounded operational reporting lane, as measured by comparison of `[N]` rolling monthly periods through `[K]` stable KPI families, isolation of one concentrated risk or opportunity pocket, and regeneration of the trend-and-focus evidence pack in `[T]` minutes, by reading the monthly lane beyond headline movement, distinguishing stable top-line position from concentrated pattern change, and packaging the strongest attention point into concise analytical evidence for follow-up.

### 14.2 Shorter recruiter-readable version

> Identified trends, risks, and opportunities from rolling monthly operational data, as measured by stable KPI comparison across a bounded monthly window and clear isolation of one priority attention point, by turning recurring reporting outputs into focused analytical reading rather than passive month-end summary.

### 14.3 Closest direct response to the InHealth requirement

> Identified trends, risks, and opportunities in operational data, as measured by bounded rolling-month comparison, stable KPI interpretation, and clear selection of one priority attention point, by analysing recent monthly movement carefully, separating broad lane stability from concentrated segment-level pattern change, and surfacing where attention should go first.

## 15. Immediate Next-Step Order

The correct build order remains:
1. profile and fix the rolling monthly window and bounded KPI family
2. build one rolling monthly comparison output
3. identify one concentrated risk or opportunity pocket
4. package the trend context and focus views into a compact evidence set
5. add trend, implication, and caveat notes

That order matters because it prevents the slice from collapsing into premature improvement language before the underlying trend and attention point have been identified cleanly.
