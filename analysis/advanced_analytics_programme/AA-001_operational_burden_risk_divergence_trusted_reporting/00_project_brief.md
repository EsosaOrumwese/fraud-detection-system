# AA-001 Project Brief: Operational Burden, Risk Divergence, and Trusted Reporting

## Working Title

**Operational Burden, Risk Divergence, and Trusted Reporting for a High-Volume Decisioning Service**

This project is not a generic fraud analysis. It is a public-sector-style operational analytics work package using the fraud decisioning platform as the operating estate.

The project is designed to produce a trusted reporting and insight product over a high-volume decisioning service. The work links multiple operational datasets to explain workload, risk-handling divergence, data quality issues, and service-improvement opportunities.

## Brief Status

| Field | Value |
|---|---|
| Brief ID | `AA-001` |
| Status | Planning |
| Project type | Flagship analytical delivery project |
| Primary delivery role | Analytics Engineer / Data Analyst embedded in a high-volume decisioning service |
| Current phase | Project definition |
| Execution status | Not started |

## Why This Project Exists

The data-interface investigation established what the advanced analytics team can legitimately access from the live operating platform: arrival/routing context, behavioural streams, behavioural context, flow anchors, truth products, bank/institutional view, and case timelines.

That investigation also exposed a problem: the platform's downstream data world is rich, but easy to misuse. Different surfaces operate at different grains, carry different meanings, and support different decisions. Event rows, flows, arrivals, sessions, truth labels, bank views, and case events cannot be casually joined or summarized without creating misleading results.

In a real operating organisation, that situation creates a practical stakeholder problem. Leadership, operations, risk, BI, data governance, and responsible analytics stakeholders need a trusted way to understand:

- how much operational workload the service creates
- where case burden is concentrated
- how institutional handling diverges from eventual truth
- which metrics are safe to report
- which data limitations could mislead decision-makers
- where service improvement should focus first

This project exists to turn the investigated interface estate into a trusted operational insight and reporting product.

## Delivery Role

The delivery role for this project is:

> **Analytics Engineer / Data Analyst embedded in a high-volume decisioning and case-handling service.**

The responsibility is to turn a complex governed data estate into a trusted reporting and insight product for stakeholders.

This project is not primarily scoped as:

- a machine learning engineer
- a cloud engineer
- a platform engineer
- a backend developer
- a fraud modeller

Those disciplines may support or constrain the work, but the project itself is centred on operational analytics, reporting assurance, metric definition, stakeholder communication, and decision support.

## Operating Scenario

The organisation runs a high-volume fraud decisioning service.

The service receives and records large volumes of flows, attaches behavioural and entity context, records institutional judgement, and produces case-handling activity. The advanced analytics function has received a three-month governed extract from the operating platform.

Senior stakeholders are concerned that the organisation does not yet have a single trusted view of the relationship between:

- traffic and flow volume
- institutional handling
- eventual truth
- case workload
- segment-level pressure
- amount exposure
- reporting caveats
- data quality and responsible-use limits

The operating estate contains multiple surfaces, but they do not all answer the same question. A row in the event stream is not the same as a flow. A case event is not the same as a case. A bank-positive judgement is not the same as truth. A completed session field is not necessarily live-safe. A structural null is not necessarily missing data.

The project starts from that reality.

## Core Business Problem

The service leadership team needs a trusted answer to this question:

> **Where is operational burden coming from, how does institutional handling diverge from eventual truth, and what action should stakeholders take to improve reporting, workload management, and risk handling?**

Everything in the project must serve that central problem.

The goal is not to produce a large collection of exploratory outputs. The goal is to build a defensible analytical product that explains burden, divergence, data quality, metric definitions, and improvement priorities in a way stakeholders can use.

## Intended Business Result

If executed well, the project should give the organisation:

- a flow-level analytical mart that links valid context, truth, bank view, and case summaries
- a metric definition pack that prevents denominator and grain mistakes
- a QA and reconciliation pack that makes the reporting trustworthy
- an operational burden analysis that identifies where workload is created
- a risk-divergence analysis that separates truth-positive, bank-positive, over-action, and under-action patterns
- a responsible analytics note that defines safe use, offline-only fields, leakage risks, and reporting caveats
- dashboard-ready outputs and/or a reporting product for operational and senior stakeholders
- a stakeholder briefing with clear findings, caveats, and recommendations

The project can still succeed if the data proves unfit for some stakeholder claims. A defensible "do not use this metric for that decision" finding is a valid business result.

## Source Data Boundary

This project uses the downstream interface estate available to the advanced analytics function.

It must not use hidden Data Engine authoring artifacts as if they were operational data available to the company. Data Engine internals may inform our understanding when permitted by the investigation posture, but they are not valid project inputs for stakeholder reporting or mart construction.

The current pinned local source remains:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1`](../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1)

## Project Boundaries

### In Scope

- stakeholder requirements and decision needs
- source-surface review and data modelling
- flow-level analytical mart design
- truth-bank divergence analysis
- case burden and case-path analysis
- segment and exposure analysis
- data quality, reconciliation, and anomaly tracking
- metric definitions and denominator rules
- live-safe versus offline-only classification
- responsible analytics caveats
- dashboard-ready tables and reporting design
- stakeholder briefing and recommendations
- post-execution case-study packaging

### Out of Scope for v0

- building a new machine learning model
- deploying a model
- changing the fraud decisioning platform
- changing or rerunning the Data Engine
- building new streaming infrastructure
- creating a full model monitoring system
- re-labelling the domain as NHS, rail, energy, or another sector
- representing the work as having been done for an external employer
- using internal world-builder data as stakeholder-facing evidence

The project should not maximise technical complexity for its own sake. It should maximise credible, assured, decision-useful analytical delivery.

## Expected Professional Evidence

The project is designed backwards from the kind of evidence a serious analytical delivery project should be able to produce. By the end of execution, the work should be capable of supporting truthful examples around:

- gathering stakeholder requirements and turning them into a scoped analytical product
- linking multiple governed operational datasets into a trusted reporting model
- defining metrics with clear numerators, denominators, grains, caveats, and owners
- using SQL and Python to build reproducible analytical workflows
- detecting and explaining data quality risks, anomalies, and structural null patterns
- applying assurance controls before stakeholder-facing conclusions are made
- designing dashboard-ready outputs and reporting pages for different users
- communicating complex technical findings in plain operational language
- recommending service-improvement priorities from evidence rather than intuition
- explaining responsible-use boundaries such as leakage, offline-only fields, and target-definition limits

These examples are not to be written as case studies until execution has produced the evidence. This section exists only to define the standard the project must be capable of earning.

## Delivery Pack Structure

This project is split into planning and execution documents:

| Document | Purpose |
|---|---|
| `00_project_brief.md` | Formal project anchor: why the project exists, core problem, scope, and expected result |
| `01_requirements_and_stakeholders.md` | Stakeholders, decision needs, user questions, priorities, and acceptance expectations |
| `02_data_scope_and_metric_contract.md` | In-scope data surfaces, grains, joins, metric definitions, denominator rules, and non-negotiable analytical constraints |
| `03_delivery_plan.md` | Workstreams, sequencing, milestones, and transition from planning to execution |
| `04_assurance_and_governance_plan.md` | QA, reconciliation, caveats, responsible-use boundaries, leakage control, and safe-use rules |
| `05_outputs_and_acceptance_criteria.md` | Required outputs, dashboard/reporting product, briefing pack, case-study bank, and completion criteria |

Execution artifacts will live under:

- `execution/notebooks`
- `execution/sql`
- `execution/extracts`
- `execution/figures`
- `execution/dashboard`
- `execution/reports`

## Working Principle

This project should be built backwards from the evidence it needs to earn, but it must not fake the evidence before execution.

The brief may define the case-study outcomes the work should be capable of supporting. The actual case-study bank must only be written after the work is complete and the evidence has been produced.

The project must remain anchored in the operating problem, not in portfolio presentation. If a planned activity does not help explain burden, divergence, trusted reporting, data quality, or responsible use, it should be challenged before execution.
