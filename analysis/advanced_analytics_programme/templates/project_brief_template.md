# Project Brief Template

> Copy this template into `analysis/advanced_analytics_programme/briefs/<brief-id>_<brief-name>/brief.md` when a project brief is approved for drafting.

---

## 1. Brief Control

| Field | Value |
|---|---|
| Brief ID | `AA-###` |
| Brief title |  |
| Status | Candidate / Draft / Scope review / Approved / In execution / Closed |
| Brief type | Flagship / Supporting |
| Owner | Advanced Analytics |
| Primary stakeholder |  |
| Supporting stakeholders |  |
| Date opened |  |
| Review cadence |  |
| Linked execution folder | `analysis/advanced_analytics_programme/execution/<brief-id>_<brief-name>` |

## 2. Executive Summary

State the brief in plain operational language.

This should answer:

- what problem has been raised
- why it matters now
- which part of the fraud decisioning platform it concerns
- what decision or action the work should support
- what the expected output will be

This section should be written last, after the rest of the brief is clear.

For a flagship brief, this section should make the cross-functional shape of the work clear. It should not read like a narrow request for one dashboard, one model, or one query. It should make clear why the brief needs stakeholder clarification, data work, statistical investigation, assurance, and stakeholder-ready communication.

## 3. Operating Context

Describe the platform context behind the request.

The brief should be grounded in the organisation running the AWS-hosted fraud decisioning platform. It should explain where this problem sits in the live operating service:

- traffic and authorization flow
- behavioural streams
- behavioural context
- truth products
- case products
- fraud operations
- risk/compliance
- BI/reporting
- data governance
- model monitoring or learning

Do not describe the work as if it is a generic CSV analysis. Explain what part of the operating world emits, consumes, or depends on the data.

## 4. Trigger and Background

Explain why the work exists.

Possible trigger types:

- stakeholder concern
- operational pain point
- metric ambiguity
- model-risk concern
- data-quality concern
- case workload concern
- fraud-loss or abuse-risk concern
- executive reporting need
- regulatory or audit-style assurance need
- finding exposed during the interface-world investigation

The trigger should be specific enough that the brief would make sense in a real organisation.

## 5. Problem Statement

Write the problem as an operating problem, not merely as an analytical question.

Strong problem statements usually include:

- the affected process or team
- the uncertainty or failure mode
- why the current state is insufficient
- what risk or missed opportunity exists if the problem is not answered

Avoid weak forms such as:

- "Analyze fraud."
- "Build a dashboard."
- "Find insights."

## 6. Stakeholder Concerns

List the stakeholder groups and what each needs from the work.

| Stakeholder | Concern | Decision or action they need to support |
|---|---|---|
| Fraud Operations |  |  |
| Risk / Compliance |  |  |
| BI / Reporting |  |  |
| Data Management |  |  |
| Platform / MLOps |  |  |
| Leadership |  |  |

Only keep rows that genuinely apply. Add others if the brief needs them.

For flagship briefs, expect several stakeholder groups to be involved. The purpose is not to invent unnecessary stakeholders, but to reflect the reality that serious analytics work usually crosses fraud operations, risk, BI/reporting, data management, platform, and leadership concerns.

## 7. Decision Need

State the decision this work is meant to inform.

Examples:

- whether a dashboard metric should use event grain, flow grain, case grain, or entity grain
- whether truth-positive labels are fit for a supervised model target
- whether bank-view divergence represents operational risk, customer friction, or expected institutional judgement
- whether case workload is concentrated enough to justify triage redesign
- whether the current synthetic extract is fit for stakeholder-facing fraud analytics
- whether model monitoring should track campaign markers, truth labels, bank labels, or case outcomes

If there is no decision need, the brief is probably not ready.

## 8. Business Value and Expected Result

Explain what the organisation gains if the work is completed well.

Possible result types:

- clearer fraud-risk definition
- better operational prioritisation
- reduced false-positive burden
- stronger model target discipline
- better dashboard denominator discipline
- improved trust in reporting
- identified data-fitness constraints
- concrete recommendations for monitoring, triage, or governance
- evidence that a requested analysis should not be used for stakeholder claims

The expected result does not have to be a positive finding. A defensible "not fit for this use" conclusion can be valuable.

## 9. Scope

### In Scope

List the surfaces, questions, and outputs included in this brief.

### Out of Scope

State what will not be done.

Common exclusions:

- rerunning or editing the Data Engine
- changing platform infrastructure
- using internal world-builder artifacts not available to the analytics team
- treating offline-only fields as live model features
- creating dashboards before the metric definitions are proven
- making explicit fraud-loss claims from broad abuse-risk labels without definition control

## 10. Data Scope

List the datasets and interface-pack surfaces that are valid for the brief.

| Data surface | Grain | Role in brief | Live-safe / offline-only | Caveats |
|---|---|---|---|---|
|  |  |  |  |  |

For each surface, state why it is valid for this brief. Do not include data just because it exists.

## 11. Metric and Definition Discipline

Define the terms that must not be used loosely.

Examples:

- event row
- flow
- arrival
- session
- case
- truth-positive
- explicit fraud
- abuse
- bank-confirmed fraud
- campaign marker
- amount exposure
- loss
- review burden
- false positive
- false negative

For each critical term, state:

- exact data field or derivation
- grain
- denominator
- allowed interpretation
- forbidden interpretation

## 12. Analytical Questions

Write the investigation questions that follow from the problem statement.

These should be question-led but not artificially narrow. They should leave room for discovery while still giving the work direction.

| Question | Why it matters | Expected evidence |
|---|---|---|
|  |  |  |

## 13. Analytical Approach

Describe the planned method.

Possible components:

- EDA and data profiling
- denominator and grain reconciliation
- cohort analysis
- distribution analysis
- temporal analysis
- label agreement / disagreement analysis
- case lifecycle analysis
- operational burden analysis
- feature-readiness assessment
- model target assessment
- dashboard metric design
- statistical testing or uncertainty framing
- model development, if justified

The approach should match the problem. Do not include modelling unless the decision need requires it.

For flagship briefs, the analytical approach should normally combine several modes of work rather than isolate one capability. A strong brief may include SQL extraction, Python profiling, metric definition, statistical analysis, visual evidence, dashboard candidates, and assurance review in one coherent delivery path.

## 14. Visual Evidence and Reporting Plan

Describe the kinds of visual evidence expected, without fixing every plot too early.

State:

- which statistical realities must be made visible
- where static plots are enough
- where interactive/dashboard views may be needed later
- which visuals are for investigation and which are candidates for stakeholder reporting

Visuals must be evidence. They are not decoration.

## 15. Delivery Outputs

List expected deliverables.

| Output | Purpose | Location |
|---|---|---|
| Investigation notebook | Inspect data and reasoning |  |
| SQL assets | Reusable query logic |  |
| Compact exports | Evidence summaries |  |
| Figure set | Visual evidence |  |
| Analytical report | Findings and recommendations |  |
| Dashboard candidate | Stakeholder-facing monitoring or insight |  |
| Assurance log | Quality and caveat tracking |  |

Only keep outputs that the brief genuinely needs.

For flagship briefs, the default expectation is that the work should produce enough artifacts to demonstrate real delivery: not only a notebook, not only a dashboard, and not only a written report. The exact mix depends on the problem, but the brief should make clear how the work moves from investigation to stakeholder-usable output.

## 16. Assurance Plan

State how the work will be checked before conclusions are used.

Minimum checks:

- grain is stated for every metric
- denominator is stated for every rate/share
- large data scans use DuckDB or compact summaries
- no unavailable world-builder data is used as if it were operational interface data
- live-safe and offline-only fields are separated
- target definitions are not conflated
- nulls are classified as missing, structural, or not applicable
- visual conclusions are traceable to data
- limitations are carried into the final output

Additional checks for modelling:

- leakage review
- target-definition review
- class imbalance handling
- temporal split discipline
- baseline model comparison
- evaluation metric justification
- explainability and operational usability

## 17. Risks, Caveats, and Realism Concerns

Record known issues before execution begins.

Examples from the interface-world investigation:

- upstream `fraud_flag` is very sparse
- explicit `FRAUD` may be much smaller than broad truth-positive `ABUSE`
- event-grain amount totals can double flow-grain economic value
- session index contains completed-session information and is offline-only
- campaign IDs may be grouping keys without self-contained business meaning
- case products are selective and require denominator discipline
- synthetic-world data may be fit for some stakeholder questions but not others

This section should be updated during execution.

## 18. Delivery Plan

Break the work into phases.

| Phase | Objective | Exit criteria |
|---|---|---|
| 1. Discovery and scoping | Confirm data, definitions, and feasibility | Brief approved for execution |
| 2. Investigation | Build evidence and identify leads | Findings are traceable and reviewed |
| 3. Analytical build | Produce agreed metrics, models, reports, or dashboards | Outputs meet assurance checks |
| 4. Stakeholder synthesis | Translate findings into decisions and recommendations | Stakeholder-ready output complete |
| 5. Closeout | Record caveats, next steps, and reusable assets | Brief closed or extended |

## 19. Acceptance Criteria

Define what "good enough" means.

Examples:

- the brief answers the decision need directly
- conclusions are supported by traceable evidence
- metrics are reproducible from SQL/notebooks
- visuals expose the relevant statistical reality
- caveats are not hidden
- stakeholder-facing language is precise
- the output is useful even if the answer is negative or cautionary

## 20. Stakeholder Communication Plan

State how results will be communicated.

Possible formats:

- analytical report
- executive summary
- Power BI dashboard
- technical notebook walkthrough
- model evaluation memo
- data quality memo
- operational recommendation paper

State which audience each output is for.

## 21. Delivery Evidence and Professional Capability

This section is not a job-ad mapping table and not a tick-box exercise. It records the professional evidence produced by the completed work.

The purpose is to make sure the delivery itself is rich enough to stand up as serious professional experience. A completed flagship brief should usually produce evidence across several areas at once:

- stakeholder requirement clarification
- operating-context understanding
- SQL and Python analytical execution
- data modelling or metric-definition discipline
- data-quality, caveat, and realism assessment
- statistical, modelling, or analytical-method judgement
- visual evidence and dashboard/report design
- governance, assurance, leakage, or responsible-use reasoning
- business recommendation and decision-support communication
- reusable analytical assets, definitions, or processes

Only complete this section after the work has produced real evidence. Do not write claims the brief did not earn.

## 22. Open Questions

List unresolved questions that need stakeholder, data, or analytical clarification.

| Question | Owner | Required before execution? |
|---|---|---|
|  |  |  |

## 23. Approval Decision

| Decision | Notes |
|---|---|
| Approved / rejected / revise |  |
| Conditions |  |
| Date |  |
| Approved by |  |
