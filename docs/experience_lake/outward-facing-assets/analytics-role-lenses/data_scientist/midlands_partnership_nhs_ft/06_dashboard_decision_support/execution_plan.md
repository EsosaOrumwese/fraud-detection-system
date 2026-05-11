# Execution Plan - Dashboard Integration and Decision Support Slice

As of `2026-04-03`

Purpose:
- turn the chosen dashboard-and-decision-support slice into a concrete execution order tied to the existing governed outputs
- keep the work pack-first, audience-first, and bounded to one regenerable 3-page reporting product
- preserve the real proof burden of this requirement: turning analytical outputs into stakeholder-facing decision-support reporting rather than leaving them as technical analysis only

Execution substrate:
- [`runs/local_full_run-7`](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\runs\local_full_run-7)
- previously executed bounded slices under `artefacts/analytics_slices/data_scientist/midlands_partnership_nhs_ft/`

Primary rule:
- reuse existing governed model and pathway outputs first
- build only the reporting-ready layer and dashboard pack needed for this responsibility
- do not drift into another modelling programme or broad BI estate
- keep the dashboard pack compact, regenerable, and audience-specific

---

## 1. Confirmed Working Assumptions

This plan is built around the following already-confirmed local facts:
- `flow_id` is the natural grain for the model-led reporting slice
- the governed and explainable scoring slice already produced reusable risk-band and review-summary outputs
- the population-pathway slice already produced compact KPI and reporting summaries that can support the workflow page
- the local governed run already supports the dimensions needed for a bounded drill-through layer

Confirmed reusable upstream assets:
- slice `05_governed_explainable_ai`
  - `flow_model_risk_band_summary_v1.parquet`
  - `flow_model_review_summary_v1.parquet`
  - `validation_scores_selected_v1.parquet`
  - `test_scores_selected_v1.parquet`
- slice `03_population_pathway_analysis`
  - `population_pathway_kpis_v1.parquet`
  - `population_pathway_reporting_v1.parquet`
  - `population_cohort_metrics_v1.parquet`

Working assumption about the reporting pack:
- it will be built as an “equivalent BI” pack rather than a Power BI file
- the proof surface can be notebook-generated figures, scorecards, compact tables, and annotated page outputs
- the pack still has to behave like real decision-support reporting, not a loose set of charts

## 2. Required Execution Order

This slice should follow the chosen execution order:
- `04 -> 07 -> 02 -> 08`

Meaning:
- first shape the reporting-ready views
- then pin the exact model and cohort outputs worth surfacing
- then build the dashboard pages
- then annotate and translate them for executive and operational audiences

This order matters because:
- the dashboard pack should sit on stable reporting-ready views
- the audience notes should describe the final reporting outputs, not moving intermediate logic

## 3. First-Pass Objective

The first-pass objective is:

`build one compact flow-level prioritisation and operations dashboard pack with explicit executive, operational, and drill-through views`

The proof object is:
- `dashboard_decision_support_v1`

The first-pass output family is:
- one reporting-ready base view
- one executive summary view
- one drill-through view
- one compact 3-page dashboard pack
- one KPI definitions note
- one executive brief
- one operations note
- one challenge-response note

## 4. Existing Analytical Outputs To Reuse

The slice should not start by rebuilding the earlier analytical work.

The reporting pack should reuse:
- selected-model risk-band behaviour from slice `05`
- selected-model explanation summaries from slice `05`
- pathway and workload context from slice `03`
- bounded cohort and value signals already surfaced in earlier slices

Expected high-value reused facts:
- selected model: `challenger_logistic_encoded_history`
- test `High` band truth rate: `6.32%`
- test `High` band lift: `2.31x`
- selected model remains reviewable because it is coefficient-based logistic scoring with encoded historical-risk features
- workflow and pathway context already available from the pathway slice to support a backlog or conversion view

Decision rule:
- if an existing upstream artefact already answers a page requirement truthfully, reuse it
- only rebuild at SQL/view level when the earlier artefact is too narrow, too technical, or not reporting-ready enough

## 5. Lens 04 Execution Block - Build The Reporting-Ready Product Layer

This block should run first.

### Step 1. Create a reporting-ready base view

Create one bounded SQL output:
- `vw_flow_dashboard_base_v1.sql`

This view should join:
- `flow_id`
- split role
- prioritisation score where safe to include
- selected risk band
- cohort label
- bounded case or outcome flags
- compact time fields for trend grouping
- the minimum drill-through dimensions needed for later explanation

The base view should be:
- explicit
- documented
- safe for downstream reporting use
- stripped of truth-only or overly technical fields that do not belong in a reporting pack

### Step 2. Create an executive-summary view

Create:
- `vw_flow_dashboard_summary_v1.sql`

This view should pre-shape:
- headline workload volume
- selected-model risk-band volumes
- fraud-truth yield by band
- one compact trend surface
- one cohort concentration surface

### Step 3. Create a drill-through view

Create:
- `vw_flow_dashboard_drillthrough_v1.sql`

This view should support:
- filtered row-level examples
- explanation of why a segment matters
- compact review columns rather than raw modelling internals

### Step 4. Write the product contract

Create:
- `flow_dashboard_product_contract_v1.md`

This should pin:
- grain
- key fields
- allowed uses
- caveats
- which upstream slices feed the pack

## 6. Lens 07 Execution Block - Pin The Analytical Outputs Worth Surfacing

This block should stay light and reuse-first.

### Step 1. Reuse the selected risk output

The default reporting logic should use the selected governed model output from slice `05`, not the earlier generic modelling slice.

Reason:
- it already has the strongest governed-delivery posture
- it carries explicit threshold and explanation notes
- it better fits the decision-support responsibility than the earlier modelling slice alone

### Step 2. Define the compact surfaced output family

The dashboard pack should surface only:
- one risk band
- one cohort label
- one prioritisation ordering

The cohort summary should be limited to:
- high-risk / high-yield
- high-burden / low-yield
- fast-converting / slow-converting

### Step 3. Build one compact explanation surface

Create:
- `flow_priority_explanation_v1.md`

This should explain:
- the main drivers of the higher-risk or higher-priority group
- where operational value concentrates
- where burden is high but value is weak

The explanation surface should translate the selected-model logic into reporting language, not raw model language.

## 7. Lens 02 Execution Block - Build The Dashboard Pack

This is the core owner block.

The pack should be produced as a compact, regenerable three-page artefact:
- notebook export
- HTML
- PDF
- or image-based dashboard pack

Tool choice is secondary.
Page behaviour is primary.

### Page 1. Executive overview

This page should answer:
- what changed?
- how much work is sitting in the important bands or cohorts?
- where is the value concentration?

Required components:
- headline risk and workload KPIs
- one trend panel
- one cohort-concentration panel
- one short `what changed` annotation

### Page 2. Workflow and prioritisation

This page should answer:
- what deserves attention first?
- how do the risk bands or cohorts relate to conversion, throughput, or backlog?

Required components:
- one workflow or conversion view
- one risk-band or cohort comparison
- one prioritisation table

### Page 3. Explanation and drill-through

This page should answer:
- why does this group matter?
- what does the underlying slice actually contain?
- what caveats should a reviewer remember?

Required components:
- one detailed cohort or segment breakdown
- one explanation panel
- one drill-through table or filtered row set

### Support tasks

Create:
- `dashboard_pack_v1`
- `dashboard_kpi_definitions_v1.md`
- `dashboard_page_notes_v1.md`

The KPI definitions note should pin:
- KPI names
- meanings
- page reuse rules
- whether each KPI is executive-facing, operational, or drill-through only

## 8. Lens 08 Execution Block - Make It Understandable And Decision-Ready

This block must make the pack legible without oral explanation.

Create:
- `dashboard_executive_brief_v1.md`
- `dashboard_operations_note_v1.md`
- `dashboard_challenge_response_v1.md`

The executive brief should answer:
- what changed
- why it matters
- what should be monitored next

The operations note should answer:
- which segment or cohort needs attention
- what the dashboard suggests should happen first
- what should be reviewed next

The challenge-response note should answer:
- why trust this metric?
- what does this cohort include?
- what caveats apply?
- what is the reporting surface not claiming?

This is important because the pack must read as decision support, not as a technical appendix.

## 9. KPI Strategy

The KPI family should stay intentionally small.

First-pass KPI candidates:
- total bounded flows in scope
- selected `High` and `Medium` band workload
- fraud-truth yield by risk band
- one trend KPI over time
- one workflow or conversion KPI
- one cohort concentration KPI

The rule is:
- every KPI must appear for a reason
- if a metric is not needed to support executive, operational, or drill-through reading, it should not be included

This matters because the requirement is about clear presentation and decision support, not metric volume.

## 10. Regeneration Strategy

The pack should be reproducible from the same governed inputs and upstream slice artefacts.

Required regeneration steps:
- rebuild reporting-ready SQL views
- refresh the compact dashboard dataset
- rerender the three dashboard pages
- rerender the annotated notes or page exports

The regeneration notes should be saved alongside the artefacts so the reporting pack reads like a reusable product, not a one-off deck.

## 11. Artefact Destinations

Execution artefacts:
- `artefacts/analytics_slices/data_scientist/midlands_partnership_nhs_ft/06_dashboard_decision_support/`

Documentation:
- `docs/experience_lake/outward-facing-assets/analytics-role-lenses/data_scientist/midlands_partnership_nhs_ft/06_dashboard_decision_support/`

## 12. Definition Of A Successful First Pass

The first pass should be considered successful if:
- one reporting-ready analytical layer exists
- one governed model or cohort output has been surfaced cleanly into the pack
- the pack has clear executive, operational, and drill-through views
- KPI definitions are stable and reused consistently
- a non-technical reader can understand what changed and why it matters
- at least one action or prioritisation recommendation is explicit
- the pack can be regenerated from the same governed inputs

If the work only produces attractive charts without a stable reporting-ready layer and audience notes, the slice has under-delivered.

## 13. What This Plan Is And Is Not

This is:
- a concrete execution plan for the dashboard-integration and decision-support slice
- model-led but not Power-BI-locked
- built to operationalise existing governed outputs into a reporting pack

This is not:
- the execution report
- a broad BI programme plan
- permission to sprawl the pack beyond the three-page audience structure

The first operational move after this plan should be:
- create the reporting-ready base, summary, and drill-through views from the existing governed outputs
