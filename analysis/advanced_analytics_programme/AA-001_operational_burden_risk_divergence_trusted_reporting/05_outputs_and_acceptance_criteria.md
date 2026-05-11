# AA-001 Outputs and Acceptance Criteria

## Purpose

This document defines what `AA-001` must produce and how completion will be judged.

The project is complete only when it has produced a defensible analytical delivery pack, not merely a notebook, a set of plots, or a dashboard mock-up. The outputs must show that the team turned a complex operating data estate into trusted, explainable, stakeholder-ready insight.

## Output Standard

Every final output must meet three standards.

| Standard | Meaning |
|---|---|
| Traceable | The output can be traced back to source surfaces, join rules, metric definitions, and QA checks. |
| Decision-useful | The output answers a stakeholder decision need rather than existing only as exploratory analysis. |
| Caveat-aware | The output states what the evidence supports and what it does not support. |

## Required Output Pack

The required delivery pack has ten outputs.

| Output ID | Output | Primary audience | Purpose |
|---|---|---|---|
| O1 | Requirements and stakeholder decision log | Project team, BI/Data Lead, Executive Sponsor | Show how stakeholder needs were converted into scoped analytical requirements. |
| O2 | Source inventory and source-to-target model | BI/Data Lead, analysts | Document source surfaces, grains, joins, and derived tables. |
| O3 | Flow-level analytical mart | Analysts, BI/Data Lead | Provide the trusted reporting base. |
| O4 | Metric definition pack | BI/Data Lead, Operations, Risk, Executive Sponsor | Define numerators, denominators, grains, caveats, and interpretation rules. |
| O5 | QA and reconciliation pack | BI/Data Lead, Governance Lead, Platform/MLOps Partner | Prove the outputs are trustworthy enough for reporting. |
| O6 | Operational burden analysis | Operations Lead, Executive Sponsor | Explain case workload, case depth, burden concentration, and process pressure. |
| O7 | Truth-bank divergence analysis | Risk/Assurance Lead, Executive Sponsor | Explain where institutional handling aligns or diverges from final truth. |
| O8 | Responsible analytics and caveat note | Governance Lead, BI/Data Lead, analysts | Prevent unsafe use, leakage, label conflation, and misleading reporting. |
| O9 | Dashboard-ready reporting layer | Operational users, BI users, Executive Sponsor | Provide reusable reporting extracts and dashboard design. |
| O10 | Stakeholder briefing and delivery closure | Executive Sponsor, project team | Communicate findings, caveats, recommendations, and next steps. |

Post-delivery evidence packaging is a separate optional output after analytical delivery closes. It is not part of the project delivery completion gate.

## O1: Requirements and Stakeholder Decision Log

### Required Content

- stakeholder map
- decision each stakeholder needs to support
- stakeholder questions
- required metrics
- priority level
- acceptance expectation
- caveats or rejected requests

### Acceptance Criteria

- Requirements are tied to decisions, not vague dashboard wishes.
- The central problem remains coupled: burden, divergence, and trusted reporting.
- Ambiguous terms such as fraud, risk, case burden, transaction volume, and workload are defined or flagged.
- Requirements do not imply real external stakeholder management beyond the project’s role-realistic delivery framing.

### Evidence Location

- `01_requirements_and_stakeholders.md`
- later execution updates if requirements change

## O2: Source Inventory and Source-to-Target Model

### Required Content

- in-scope source list
- physical paths
- row counts
- schemas
- grain for each surface
- key columns and join keys
- source-to-target mapping into the flow mart and supporting tables
- known source caveats

### Acceptance Criteria

- Every source used in the mart or metric layer is documented.
- Every join route is declared.
- `arrival_events_5B` is treated as a join/context surface, not the canonical scored stream.
- hidden Data Engine authoring artifacts are not used as stakeholder reporting inputs.
- case timeline is not rolled to flow grain until the bridge is proven.

### Evidence Location

- `02_data_scope_and_metric_contract.md`
- `execution/extracts/source_inventory.*`
- `execution/reports/source_to_target_mapping.md`

## O3: Flow-Level Analytical Mart

### Required Content

The mart should contain one row per flow and bring together:

- lineage and flow keys
- flow amount and timing context
- merchant and route context
- channel and physical/virtual indicators
- selected entity handles
- truth label
- bank view
- case summary fields, if bridge-approved
- campaign/fraud marker context with caveats
- live/offline/reporting-use flags where needed

### Acceptance Criteria

- One-row-per-flow uniqueness is proven.
- Mart row count reconciles to the approved flow anchor base.
- Truth and bank joins reconcile.
- Case fields are included only after case-to-flow proof.
- Offline-only/reporting-only fields are labelled.
- The mart supports core P0 metrics without additional hidden joins.
- Bridge-gated P0 case metrics are supported only if the case-to-flow bridge is approved.

### Evidence Location

- `execution/sql/build_flow_operational_mart.sql`
- `execution/extracts/flow_operational_mart.*`
- `execution/reports/source_to_target_mapping.md`
- QA outputs from `execution/extracts/join_reconciliation_*`

## O4: Metric Definition Pack

### Required Content

For every stakeholder-facing metric:

- metric name
- business question
- numerator
- denominator
- grain
- source surfaces
- filters
- caveats
- stakeholder owner
- example interpretation
- approval status

### P0 Metrics

The core P0 metric set must include:

- total flows
- total event rows
- implied event rows per flow
- truth-positive rate
- bank-positive rate
- truth-bank agreement rate
- truth-positive / bank-negative rate
- truth-negative / bank-positive rate

The bridge-gated P0 case metric set must be approved, rejected, or deferred after the case-to-flow bridge proof:

- case coverage rate
- case events per case
- case events per 1,000 flows
- deep-case rate
- chargeback-path rate
- dispute-path rate

### Acceptance Criteria

- No metric enters reporting without numerator, denominator, grain, source, and caveat.
- Flow, event, case, and case-event metrics are separated.
- Truth, bank view, campaign marker, and case lifecycle are separated.
- Bridge-gated P0 case metrics are not forced into reporting if the bridge is not proven.
- Rejected or caveated metrics are recorded rather than silently omitted.

### Evidence Location

- `execution/reports/metric_definition_pack.md`
- `execution/extracts/metric_summary_*`

## O5: QA and Reconciliation Pack

### Required Content

- source inventory checks
- schema checks
- join coverage checks
- duplicate-key checks
- row-count reconciliation
- event-to-flow grammar checks
- truth-bank cell reconciliation
- case timeline rollup reconciliation
- structural-null checks
- reporting-period boundary checks
- session leakage checks
- approximate metric caveats
- anomaly register
- caveat register
- realism concern register

### Acceptance Criteria

- QA checks are reproducible.
- Exceptions are classified.
- Reconciliation outputs tie back to final reporting tables.
- Known caveats are visible in the reporting pack.
- Synthetic realism concerns are recorded where they affect stakeholder conclusions.

### Evidence Location

- `04_assurance_and_governance_plan.md`
- `execution/sql/qa_join_reconciliation.sql`
- `execution/extracts/data_quality_checks.*`
- `execution/reports/qa_assurance_pack.md`
- `execution/reports/caveat_register.md`
- `execution/reports/anomaly_register.md`
- `execution/reports/realism_concern_register.md`

## O6: Operational Burden Analysis

### Required Content

- case coverage
- case-event volume
- case depth
- shallow versus deep case paths
- dispute and chargeback paths
- burden by truth-bank cell
- burden by channel, route, merchant cohort, amount band, and time where valid
- operational recommendations
- limitations

### Acceptance Criteria

- The analysis separates flows, cases, and case events.
- Burden concentration is explained with the correct denominator.
- Recommendations are tied to evidence.
- Realism limitations are stated where they affect stakeholder relevance.
- The analysis is reproducible from the mart and supporting case summary.

### Evidence Location

- `execution/notebooks/operational_burden_analysis.ipynb`
- `execution/extracts/case_burden_*`
- `execution/figures/case_burden_*`
- `execution/reports/operational_burden_findings.md`

## O7: Truth-Bank Divergence Analysis

### Required Content

- truth-bank matrix
- agreement and disagreement rates
- over-action candidate cell
- under-action candidate cell
- divergence by case burden
- divergence by segment where valid
- interpretation caveats
- recommended monitoring or review priorities

### Acceptance Criteria

- Truth and bank view are not conflated.
- Over-action and under-action are framed as candidate analytical interpretations, not proven misconduct or operational failure.
- Divergence findings reconcile to total flow count.
- Case burden is used to interpret divergence without turning case history into truth.
- Stakeholder recommendations are evidence-based.

### Evidence Location

- `execution/notebooks/truth_bank_divergence_analysis.ipynb`
- `execution/extracts/truth_bank_*`
- `execution/figures/truth_bank_*`
- `execution/reports/truth_bank_divergence_findings.md`

## O8: Responsible Analytics and Caveat Note

### Required Content

- live-compatible versus offline-only classification
- reporting-only outcome fields
- leakage risks
- truth/bank/fraud/case label distinctions
- structural null explanation
- permitted uses
- prohibited uses
- caveated uses
- rejected metrics or fields

### Acceptance Criteria

- Completed-session fields are not treated as live-safe.
- Truth labels and case outcomes are not used as live decision-time features.
- `fraud_flag` is not presented as final fraud truth.
- Structural nulls are explained before data-quality conclusions.
- Caveats are written in language that stakeholders can understand.

### Evidence Location

- `execution/reports/responsible_analytics_note.md`
- `execution/reports/caveat_register.md`
- `execution/reports/reporting_data_dictionary.md`

## O9: Dashboard-Ready Reporting Layer

### Required Content

Dashboard-ready outputs should support these pages:

1. Executive overview
2. Truth vs bank handling
3. Operational case burden
4. Segment and exposure analysis
5. Data quality and caveats

Each export must include or link to:

- grain
- reporting period
- filters
- metric definitions
- caveats
- refresh or lineage note

### Acceptance Criteria

- Dashboard exports reconcile to the metric layer.
- Dashboard tables do not require the user to understand hidden engine internals.
- Caveats are visible at the point of metric use.
- Flow counts, event counts, case counts, and case-event counts are visually and semantically separated.
- Dashboard design supports stakeholder questions from `01_requirements_and_stakeholders.md`.

### Evidence Location

- `execution/extracts/dashboard_export_*`
- `execution/dashboard/dashboard_design_note.md`
- `execution/reports/reporting_data_dictionary.md`

## O10: Stakeholder Briefing and Delivery Closure

### Required Content

The stakeholder briefing should include:

- purpose
- headline findings
- burden picture
- divergence picture
- quality and caveat summary
- recommendations
- what not to conclude
- next steps

### Acceptance Criteria

- The stakeholder briefing is understandable without reading the notebooks.
- Claims are tied to evidence and caveats.
- Recommendations are separated from caveats and next-step hypotheses.
- Delivery closure states what was completed, what was rejected or deferred, and why.

### Evidence Location

- `execution/reports/stakeholder_briefing.md`
- `execution/reports/technical_appendix.md`
- `execution/reports/recommendation_register.md`

## Post-Delivery Evidence Packaging

This output is allowed only after analytical delivery is complete. It is useful for portfolio and interview preparation, but it is not required for the analytics project to close.

The case-study evidence bank should include evidence-backed narratives for:

- requirements-to-reporting delivery
- multi-source analytical model
- data quality and assurance
- operational burden analysis
- responsible analytics boundary control
- reproducible workflow and stakeholder communication

Acceptance criteria:

- The case-study bank is written only after execution has produced the evidence.
- The case-study bank links every claim to a delivery artifact.
- The case-study bank does not claim external employment, real stakeholder management, or domain experience not supported by the work.

Evidence location:

- `execution/reports/case_study_bank.md`

## Overall Completion Criteria

`AA-001` is complete when all of the following are true:

- Planning docs `00` to `05` are internally consistent.
- In-scope sources are profiled and documented.
- Required joins are proven or rejected with reasons.
- `flow_operational_mart` exists and is reconciled.
- Core P0 metrics are defined, computed, caveated, and reconciled.
- Bridge-gated P0 case metrics are approved, rejected, or deferred based on bridge evidence.
- Operational burden analysis is complete.
- Truth-bank divergence analysis is complete.
- QA, caveat, anomaly, and realism concern registers are complete enough for reporting.
- Responsible analytics note is complete.
- Dashboard-ready extracts and reporting design exist.
- Stakeholder briefing exists.

## Non-Completion Conditions

The project is not complete if:

- outputs are only notebook screenshots without reproducible extracts
- dashboard tables exist but metric definitions do not
- event rows are used as transaction counts
- case events are used as case counts
- truth, bank view, fraud marker, and case outcome are conflated
- case timeline is joined to flow grain without bridge proof
- session closure fields are described as live-safe
- caveats are hidden from stakeholder-facing outputs
- recommendations are not tied to evidence

Post-delivery evidence packaging is not complete if experience narratives are written before the evidence exists or if they overclaim what the delivery actually proved.

## Acceptable Partial Completion

If execution reveals that a planned output cannot be completed safely, the project may still be partially successful if it documents:

- what was attempted
- why the output was rejected or deferred
- what evidence supports that decision
- what stakeholder risk was avoided
- what would be required to complete it later

Examples:

- rejecting a metric because the denominator is not defensible
- deferring case burden by segment because the case-to-flow bridge is not proven
- caveating fraud-rate conclusions because the synthetic fraud marker prevalence is unrealistic
- excluding a session feature from live-safe reporting because it leaks future knowledge

## Output Conclusion

The success standard for `AA-001` is not volume of analysis. It is whether the final pack gives stakeholders a trusted, traceable, caveat-aware view of operational burden and risk-handling divergence.

The project should produce enough evidence to support strong professional claims about data modelling, QA, governed analytics, responsible use, reporting design, and stakeholder-oriented communication without forcing the fraud platform to prove public-policy or health-domain experience it does not naturally own.
