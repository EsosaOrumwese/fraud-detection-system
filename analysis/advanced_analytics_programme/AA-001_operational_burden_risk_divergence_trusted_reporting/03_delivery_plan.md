# AA-001 Delivery Plan

## Purpose

This document defines how `AA-001` moves from planning into execution.

The project is not an open-ended EDA exercise. It is a controlled analytical delivery programme whose purpose is to produce a trusted operational insight product over the fraud decisioning service interface estate.

The delivery plan must preserve the core discipline established in the project brief, requirements document, and metric contract:

- the main reporting base is flow-grain
- event, arrival, session, case, and case-event grains must remain explicit
- truth, bank view, campaign markers, and case history must not be collapsed into one generic fraud field
- QA and caveats must be built alongside the analysis, not added afterwards
- stakeholder-facing outputs must be earned by reproducible evidence

## Delivery Posture

The delivery posture is analytical engineering first, dashboard second.

The project should not begin by designing pages or visuals. It begins by building the trustworthy data and metric layer that makes those pages defensible.

Execution should follow this order:

1. prove source scope and joinability
2. build the flow-level mart
3. define and validate metrics
4. analyse burden and divergence
5. prepare dashboard-ready outputs
6. write stakeholder-facing findings and caveats
7. prepare post-delivery evidence packaging after the work exists

## Workstream Overview

| Workstream | Name | Purpose | Primary outputs |
|---|---|---|---|
| WS0 | Planning lock | Confirm scope, stakeholders, metric contract, and delivery standards. | Planning docs `00` to `05`. |
| WS1 | Source reconnaissance and profiling | Reconfirm the exact source files, columns, grains, and row counts needed for execution. | Source inventory, schema profile, grain profile. |
| WS2 | Join and reconciliation proof | Prove the required joins and reject unsafe joins before mart construction. | Join coverage checks, reconciliation outputs, anomaly register entries. |
| WS3 | Flow mart construction | Build the flow-level analytical mart and supporting summary tables. | `flow_operational_mart`, `case_summary_by_flow`, source-to-target notes. |
| WS4 | Metric layer | Define, compute, and validate stakeholder-facing metrics. | Metric definition pack, metric extracts, denominator checks. |
| WS5 | Operational burden analysis | Analyse case coverage, case depth, lifecycle paths, segment pressure, and burden concentration. | Burden analysis notebook, burden tables, candidate visuals. |
| WS6 | Truth-bank divergence analysis | Analyse agreement, disagreement, over-action candidates, under-action candidates, and segment patterns. | Divergence analysis notebook, truth-bank matrix outputs. |
| WS7 | Reporting and dashboard-ready layer | Convert validated analysis into reporting-ready tables and dashboard page designs. | `dashboard_export_*`, reporting wireframe/plan, figure set. |
| WS8 | Stakeholder briefing and delivery closure | Write the plain-English briefing, caveats, recommendations, and technical appendix. | Stakeholder briefing, technical appendix, recommendation register. |
| WS9 | Post-delivery evidence packaging | Package the completed work into truthful professional evidence after delivery closes. | Case-study evidence bank. |

## Phase 0: Planning Lock

### Objective

Freeze the execution contract before writing analysis code.

### Inputs

- `00_project_brief.md`
- `01_requirements_and_stakeholders.md`
- `02_data_scope_and_metric_contract.md`

### Tasks

- Confirm the project is scoped as trusted operational analytics, not model development.
- Confirm the interface estate is the reporting boundary.
- Confirm the flow-level mart is the canonical reporting base.
- Confirm the first-pass metric list and QA gates.
- Confirm the outputs and acceptance criteria in `05_outputs_and_acceptance_criteria.md`.

### Exit Criteria

- Planning docs are internally consistent.
- No project objective requires hidden Data Engine authoring data.
- No stakeholder-facing claim is planned without a metric, source, denominator, and caveat route.

## Phase 1: Source Reconnaissance and Profiling

### Objective

Reconfirm the physical source estate before building derived tables.

This phase is not a deep investigation of every source. That has already been done in the workbench. Here the job is to establish execution-ready source facts.

### Tasks

- Locate all in-scope source surfaces under the pinned run.
- Record physical paths, formats, row counts, file counts, and relevant partitioning.
- Profile schemas and key columns for each in-scope surface.
- Record grain evidence for each source.
- Identify fields needed for the first mart and metrics.
- Confirm which columns are exact, approximate, structural, offline-only, or lineage columns.

### Outputs

- `execution/extracts/source_inventory.*`
- `execution/extracts/schema_profile.*`
- `execution/reports/source_reconnaissance_note.md`

### Exit Criteria

- Every in-scope source used by execution has a documented path, row count, schema, primary grain, and intended role.
- Any missing source or schema mismatch is logged before mart construction begins.

## Phase 2: Join and Reconciliation Proof

### Objective

Prove the joins before using them in analysis.

This phase exists because the project’s biggest failure mode is not bad plotting; it is bad linkage. If the joins are wrong, every downstream metric can look polished while being false.

### Required Join Proofs

| Join | Required proof |
|---|---|
| Event stream to flow anchor | Coverage count, duplicate check, event-per-flow grammar profile. |
| Flow anchor to arrival context | Coverage count on `seed + manifest_fingerprint + scenario_id + merchant_id + arrival_seq`. |
| Arrival context to entity attachments | Coverage count and duplicate check on arrival-level key. |
| Flow truth labels to flow anchor | Coverage count and truth-cell reconciliation. |
| Bank view to flow anchor | Coverage count and bank-cell reconciliation. |
| Event labels to event stream | Coverage count and event-sequence reconciliation. |
| Case timeline to flow mart | Explicit case-to-flow bridge proof before rollup. |

### Tasks

- Implement compact DuckDB/SQL checks for all required joins.
- Export reconciliation tables.
- Record exceptions and caveats.
- Reject or defer any join that cannot be proven.
- Decide whether the case timeline bridge is strong enough for `case_summary_by_flow`.

### Outputs

- `execution/sql/qa_join_reconciliation.sql`
- `execution/extracts/join_reconciliation_*`
- `execution/reports/qa_assurance_pack.md` with a join reconciliation section
- `execution/reports/anomaly_register.md` entries where needed

### Exit Criteria

- The flow mart base can be built without unresolved join ambiguity.
- The case timeline is either safely bridged to flow grain or explicitly excluded from flow-level reporting until resolved.
- All join checks are reproducible.

## Phase 3: Flow Mart Construction

### Objective

Build the core flow-level analytical mart.

### Mart Role

`flow_operational_mart` is the main reporting base for `AA-001`. It should contain one row per flow and enough context to support burden, divergence, segment, and reporting-caveat analysis.

### Candidate Mart Fields

The exact field list must be finalized during implementation, but the mart should likely include:

- lineage fields
- flow identifier
- event/request timing fields derived safely from event stream or anchor context
- merchant and amount context
- arrival sequence and route context
- channel and physical/virtual route indicators
- selected entity handles
- truth label fields
- bank view fields
- case summary fields, if the case-to-flow bridge is proven
- campaign/fraud marker fields with clear semantics
- live/offline/reporting-use classification flags where needed

### Supporting Tables

- `case_summary_by_flow`
- `truth_bank_alignment_summary`
- `case_burden_metrics`
- `data_quality_checks`

### Outputs

- `execution/sql/build_flow_operational_mart.sql`
- `execution/extracts/flow_operational_mart.*`
- `execution/extracts/case_summary_by_flow.*`
- `execution/reports/source_to_target_mapping.md`

### Exit Criteria

- One-row-per-flow uniqueness is proven.
- Source-to-target mapping exists.
- Any offline-only or reporting-only fields are labelled.
- The mart can support the P0 metrics in the metric contract.

## Phase 4: Metric Layer

### Objective

Turn the metric contract into computed, validated metrics.

### Tasks

- Create metric definitions for all P0 metrics.
- Compute P0 metrics from the mart and supporting tables.
- Reconcile metric denominators to source counts.
- Mark case-dependent P0 metrics as approved, rejected, or deferred based on the case-to-flow bridge proof.
- Add caveats to metrics where definitions are narrow or potentially misleading.
- Identify P1 metrics that are ready for segment analysis.

### Outputs

- `execution/reports/metric_definition_pack.md`
- `execution/extracts/metric_summary_*`
- `execution/sql/build_metric_layer.sql`

### Exit Criteria

- Every core P0 metric has numerator, denominator, grain, source, caveat, and example interpretation.
- Every bridge-gated P0 case metric has approval, rejection, or deferral status.
- Metrics reconcile back to the mart or source summary.
- No stakeholder-facing metric uses an undeclared denominator.

## Phase 5: Operational Burden Analysis

### Objective

Understand where case workload and handling burden are created.

### Analytical Focus

The burden analysis should answer:

- what share of flows become cases
- how deep case lifecycles are
- which paths create more handling work
- where burden concentrates by valid operational segment
- whether burden is exposure-driven, segment-driven, or lifecycle-driven
- which findings are actionable and which are only descriptive

### Tasks

- Analyse case coverage.
- Analyse case depth and case-event volume.
- Analyse dispute and chargeback paths.
- Analyse burden by truth-bank cell.
- Analyse burden by channel, route mode, merchant cohort, amount band, and time period where valid.
- Record realism concerns or data limitations that affect stakeholder conclusions.

### Outputs

- `execution/notebooks/operational_burden_analysis.ipynb`
- `execution/extracts/case_burden_*`
- `execution/figures/case_burden_*`
- `execution/reports/operational_burden_findings.md`

### Exit Criteria

- The analysis distinguishes cases from case events.
- Burden metrics are flow/case/case-event labelled.
- Recommendations are tied to evidence, not just high counts.

## Phase 6: Truth-Bank Divergence Analysis

### Objective

Understand how institutional handling aligns with or diverges from eventual truth.

### Analytical Focus

The divergence analysis should answer:

- how truth and bank view agree or disagree
- whether bank view is broader or narrower than truth
- which cells represent candidate over-action and under-action
- how case burden differs across truth-bank cells
- whether disagreement concentrates by channel, route, merchant, amount, or time segment
- which interpretations require caution

### Tasks

- Build truth-bank matrix.
- Compute divergence rates.
- Segment divergence patterns.
- Cross divergence with case coverage and burden.
- Identify reporting risks where stakeholders might misuse bank view as truth.

### Outputs

- `execution/notebooks/truth_bank_divergence_analysis.ipynb`
- `execution/extracts/truth_bank_*`
- `execution/figures/truth_bank_*`
- `execution/reports/truth_bank_divergence_findings.md`

### Exit Criteria

- Truth, bank view, campaign marker, and case timeline remain separate.
- Over-action and under-action are framed as analytical candidates, not automatic proof of operational failure.
- Findings are suitable for stakeholder briefing with caveats.

## Phase 7: Reporting and Dashboard-Ready Layer

### Objective

Convert validated analysis into reusable reporting outputs.

### Tasks

- Design reporting pages around stakeholder questions.
- Build dashboard-ready extracts with declared grain.
- Attach metric definitions or links to each export.
- Prepare visual candidates for executive, operations, risk, and QA views.
- Keep caveats visible near the metrics they affect.

### Candidate Reporting Pages

- Executive overview
- Truth vs bank handling
- Operational case burden
- Segment and exposure analysis
- Data quality and caveats

### Outputs

- `execution/extracts/dashboard_export_*`
- `execution/dashboard/dashboard_design_note.md`
- `execution/reports/reporting_data_dictionary.md`

### Exit Criteria

- Dashboard-ready tables do not require hidden notebook logic to interpret.
- Each export declares grain, filters, period, and metric definitions.
- Caveated metrics are visibly caveated.

## Phase 8: Stakeholder Briefing and Evidence Packaging

### Objective

Turn the analysis into decision-ready communication and truthful experience evidence.

### Tasks

- Write a short stakeholder briefing.
- Write a technical appendix.
- Summarize recommendations and caveats.
- Produce a case-study bank only after the work is complete.
- Separate what was actually done from what could be done next.

### Outputs

- `execution/reports/stakeholder_briefing.md`
- `execution/reports/technical_appendix.md`
- `execution/reports/recommendation_register.md`

### Exit Criteria

- The briefing explains what matters, why it matters, what action is recommended, and what caveats apply.
- The delivery pack is complete enough to support evidence packaging later without writing the portfolio narrative inside the delivery gate.

## Phase 9: Post-Delivery Evidence Packaging

### Objective

Convert the completed delivery into truthful professional evidence after the analytical work has closed.

This phase is not required for analytical delivery completion. It exists because the completed project may later support interview, portfolio, and supporting-statement evidence.

### Tasks

- Write evidence-backed case-study notes.
- Separate what was delivered from what was simulated or role-framed.
- Avoid claims of real external employment, real stakeholder management, or domain experience not supported by the work.
- Link each professional claim to delivery evidence.

### Outputs

- `execution/reports/case_study_bank.md`

### Exit Criteria

- The case-study bank is evidence-based and does not overclaim real stakeholder management or external employment.

## Sequencing Rules

- Do not build dashboard exports before the mart and metric layer are validated.
- Do not write stakeholder conclusions before QA and caveats are known.
- Do not turn exploratory leads into recommendations unless the evidence supports them.
- Do not use a source surface in reporting unless its grain and join route are documented.
- Do not treat a failed or caveated metric as project failure; rejecting a misleading metric is a valid delivery outcome.

## Delivery Risks

| Risk | Why it matters | Control |
|---|---|---|
| Event-flow double counting | Inflates volume and workload. | Flow-grain mart, event-to-flow grammar checks. |
| Case timeline misjoin | Creates false case burden. | Mandatory case-to-flow bridge proof. |
| Truth/bank conflation | Produces false risk conclusions. | Separate semantics and truth-bank matrix. |
| Fraud marker misuse | Makes campaign overlay look like final fraud truth. | Label contract and caveats. |
| Session leakage | Creates unsafe live-feature interpretation. | Live/offline classification. |
| Dashboard-first execution | Produces polished but weak outputs. | Mart and QA gates before reporting. |
| Portfolio overclaiming | Weakens interview credibility. | Evidence bank written only after execution. |

## Delivery Conclusion

The delivery route for `AA-001` is deliberately staged.

The project must first prove the data model, then compute assured metrics, then analyse burden and divergence, then produce reporting outputs and stakeholder communication. This protects the work from becoming either casual EDA or a dashboard over untrusted joins.
