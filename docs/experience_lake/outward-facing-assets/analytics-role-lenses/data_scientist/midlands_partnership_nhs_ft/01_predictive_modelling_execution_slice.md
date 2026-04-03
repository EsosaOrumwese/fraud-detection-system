# Predictive Modelling Execution Slice - Midlands Data Scientist Requirement

As of `2026-04-03`

Purpose:
- capture the current execution decision for one bounded advanced-analytics slice
- anchor that decision to a real requirement from the Midlands Partnership NHS Foundation Trust `Data Scientist` profile
- keep the work narrow enough to produce fast, defensible outward-facing evidence without pretending the wider lens has already been fully executed

Boundary:
- this note is not an accomplishment record
- this note is not a claim that a full analytics plane has already been implemented
- this note captures the chosen slice, why it fits the requirement, what lenses it uses, and what would count as done
- execution should work from governed data extracts or local bounded views rather than from broad platform reruns

Placement rule:
- this file lives under the role-shaped lens tree because it is execution-depth material, not a top-level lens definition
- the role folder should hold multiple employer or role-execution lanes over time
- the employer folder should hold one note per targeted responsibility slice so repeated work stays grouped and readable

Primary source basis:
- [07_advanced-analytics-data-science.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\07_advanced-analytics-data-science.md)
- [04_analytics-engineering-data-product.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\04_analytics-engineering-data-product.md)
- [08_stakeholder-translation-communication-influence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\08_stakeholder-translation-communication-influence.md)
- [09_analytical-delivery-operating-discipline.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\09_analytical-delivery-operating-discipline.md)
- [data-analytics-engineering-science.ideal-candidate-profiles.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.ideal-candidate-profiles.md)
- [data-analytics-engineering-science.job-ads.evidence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.job-ads.evidence.md)

---

## 1. Requirement Being Targeted

The requirement being targeted here is the Midlands `Data Scientist` expectation around:
- developing predictive and statistical models in a real delivery setting
- using tools such as `Python`, `R`, and `SQL`
- applying those models to forecasting, segmentation, risk identification, or service improvement
- making the work production-usable rather than leaving it as exploratory notebook output

This note exists because that requirement is broad enough to produce drift if attacked as a whole, but narrow enough to support one bounded slice that can later become a truthful `X by Y by Z` outward-facing claim.

## 2. Lens Mapping For This Requirement

The primary lens for this requirement is:
- `07 - Advanced Analytics and Data Science`

That is the direct owner because it explicitly covers:
- predictive logic
- descriptive and statistical explanation
- segmentation and cohorting
- bounded forecasting
- model-ready analytical slices
- decision-support outputs

But `07` on its own is not enough if the result needs to read as real delivery rather than isolated modelling work.

The supporting lenses are:
- `04 - Analytics Engineering and Analytical Data Product`
- `09 - Analytical Delivery Operating Discipline`
- `08 - Stakeholder Translation, Communication, and Decision Influence`

The practical split is:
- `07` builds the analytical logic
- `04` makes the analytical tables and outputs reusable
- `09` makes the work reproducible, versioned, and defensible
- `08` makes the outputs decision-relevant rather than privately analytical

## 3. Chosen Bounded Slice

The bounded slice chosen for this requirement is:

`Flow-level risk stratification + cohort segmentation + a small case-demand forecast`

This is the preferred slice because it is large enough to look like real analytical delivery, but still small enough to execute quickly without dragging the whole analytics plane into scope.

The slice is defined as:
- `Analytical unit`: `flow_id`
- `Primary business question`: which suspicious flows are most likely to produce authoritative fraud-confirmed or high-yield downstream outcomes, and therefore deserve prioritised operational attention?
- `Primary model output`: flow-level risk score
- `Secondary outputs`: three risk bands, cohort summary, and one lightweight next-window case-demand forecast
- `Deployment meaning for this slice`: not a live scoring API; instead, a reusable scored table, cohort view, and decision-support output that downstream users could actually consume

## 4. Why This Slice Was Chosen

This slice fits the requirement strongly because it gives direct room for:
- predictive modelling
- statistical comparison
- risk identification
- segmentation
- bounded forecasting
- practical service-improvement interpretation

It also matches the Lens `07` execution path already implied in the main lens document:
- define the analytical unit
- build governed joins
- define the target
- construct feature-ready slices
- build scoring, cohorts, and forecasting
- translate the output into decision-support form

Just as important, this slice avoids unnecessary expansion.

The intention is not to:
- build event-level and flow-level models at the same time
- create a live scoring service
- build a full dashboard estate
- recreate a broad cloud-serving environment
- train many model families at once
- spread work across every possible forecast surface

The intention is to get one credible, inspectable, reusable analytical slice to the point where it can support a strong outward-facing claim.

## 5. Execution Posture

The default execution stack for this slice is:
- `SQL` for joins, target shaping, bounded windows, and reusable views
- `Python` for feature engineering, modelling, scoring, cohorting, and forecasting
- `R` only if it is genuinely useful for statistical comparison or explanation, not as a mandatory tool mention

The execution substrate should be:
- governed data extracts
- bounded local views
- reporting-ready or modelling-ready shaped slices derived from the governed world

The default local working assumption is that execution can begin from a local bounded run such as:
- `runs/local_full_run-7`

That should still be treated as:
- a bounded analytical extract
- not the whole world
- not a reason to casually overclaim full-platform reruns

## 6. Lens-by-Lens Execution Checklist

### 6.1 Lens 07 - Advanced Analytics and Data Science

1. Choose one bounded historical window and pin the as-of boundary.
2. Define one defendable flow-level target from authoritative downstream truth.
3. Build one feature-ready modelling table with leak-safe features only.
4. Train one explainable baseline model and, if needed, one stronger challenger.
5. Evaluate with a small metric set focused on:
- lift or yield in the high-risk band
- capture of positive outcomes in top-ranked flows
- stability across time-split windows
6. Create three operationally interpretable risk bands.
7. Build one cohort summary that explains where value or risk concentrates.
8. Add one bounded near-term case-demand forecast.

### 6.2 Lens 04 - Analytics Engineering and Analytical Data Product

1. Confirm that `flow_id` is the correct analytical grain for the consumer-facing use case.
2. Create one reusable model-ready base view.
3. Create one reusable scored-output view.
4. Create one reusable cohort summary view.
5. Keep modelling and reporting outputs separate so downstream use stays clear.

### 6.3 Lens 09 - Analytical Delivery Operating Discipline

1. Pin the target definition.
2. Pin the risk-band rules.
3. Pin the cohort rules.
4. Record the exact source surfaces, join keys, and transformation assumptions.
5. Version the shaping logic and modelling logic.
6. Document what the output can answer and what it must not be used for.
7. Package enough regeneration guidance that another analyst could rerun the slice.

### 6.4 Lens 08 - Stakeholder Translation, Communication, and Decision Influence

1. Write one short decision brief explaining what is being scored and why it matters.
2. Show what the risk bands mean operationally.
3. Show which cohorts deserve attention.
4. Add challenge-ready caveat notes.
5. Make the next action explicit rather than leaving the output as a private model artifact.

## 7. Minimum Artifact Pack

The smallest useful proof pack for this requirement is:
- one model-ready flow table
- one modelling notebook or script
- one scored output view
- one three-band cohort summary
- one bounded forecast table
- one definitions and lineage pack
- one decision brief or annotated reporting surface

That pack is enough to support claims about:
- predictive and statistical modelling
- segmentation
- risk identification
- production-usable analytical shaping
- reproducibility
- decision-support packaging

## 8. Suggested Artifact Names

These names are placeholders, not fixed schema requirements.

Analytical outputs:
- `flow_risk_model_base_v1`
- `flow_risk_scores_v1`
- `flow_risk_bands_v1`
- `flow_risk_cohort_summary_v1`
- `case_demand_forecast_v1`

SQL and shaping assets:
- `vw_flow_model_base_v1.sql`
- `vw_flow_risk_scores_v1.sql`
- `vw_flow_risk_cohorts_v1.sql`
- `vw_flow_priority_reporting_v1.sql`

Documentation and delivery-control assets:
- `target_and_feature_definition_v1.md`
- `lineage_and_join_notes_v1.md`
- `usage_caveats_v1.md`
- `README_regeneration.md`
- `CHANGELOG.md`
- `flow_risk_brief_v1.md`
- `flow_risk_action_summary_v1.md`

## 9. Definition Of Done

This slice should be treated as complete only when all of the following are true:
- one target is clearly defined and defendable
- one bounded time-split modelling slice exists
- one scored output is materialised into a reusable downstream table or view
- three risk bands exist and are interpretable in operational terms
- one cohort summary shows where value or risk concentrates
- one bounded forecast exists
- one decision brief explains what the outputs mean and what should be done with them
- one documentation pack makes the slice reproducible and reusable

## 10. Truth Boundary

As of this note, the correct claim is:
- the slice has been selected
- the lens mapping is clear
- the execution path is defined
- the output pack has been bounded

The correct claim is not:
- that the slice has already been executed
- that the models have already been deployed
- that the forecast is already validated
- that a live decisioning or live BI product has already adopted the outputs

This note therefore exists to protect against overclaiming while still preserving momentum toward a fast, defensible claim.

## 11. XYZ Claim Surfaces This Slice Is Aiming Toward

The strongest eventual claim shape for this slice is:

> Improved fraud-review prioritisation and near-term case planning, as measured by [X%] lift in confirmed-yield within the highest-risk band, [Y%] capture of positive outcomes within the top-ranked flows, and [Z%] forecast error on next-window case demand, by building and operationalising a bounded flow-level predictive and statistical modelling slice in `Python` and `SQL` over governed event, flow, case, and outcome data, packaging the outputs into reusable score tables, cohort views, and stakeholder-ready decision summaries.

A shorter variant, if the forecast portion is dropped, is:

> Improved operational fraud prioritisation, as measured by [X%] higher positive-yield in high-risk cohorts and stable time-split validation performance, by shaping model-ready governed datasets in `SQL`, developing a flow-level risk stratification model in `Python`, versioning feature and target logic, and turning scored outputs into reusable reporting-ready views and action summaries.

The recruiter-readable responsibility version is:

> Built and deployed predictive and statistical analytics over governed fraud data, as measured by risk-band yield improvement and stable validation performance, by creating reusable model-ready slices, applying `Python`/`SQL`-based segmentation and scoring, and operationalising the outputs into prioritisation views and decision-support reporting.

## 12. Immediate Next-Step Order

The correct build order remains:
1. `07` core analytical build
2. `04` reusable analytical tables
3. `09` reproducibility and control pack
4. `08` decision brief and reporting surface

That order matters because it prevents the work from collapsing into polished outward-facing packaging with no defensible analytical core behind it.
