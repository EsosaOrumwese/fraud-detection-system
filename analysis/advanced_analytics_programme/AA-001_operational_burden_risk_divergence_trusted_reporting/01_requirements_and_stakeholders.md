# AA-001 Requirements and Stakeholders

## Purpose

This document defines the stakeholder and requirement frame for `AA-001`.

The project is not starting from a dashboard request. It is starting from an operating concern: the organisation runs a high-volume decisioning and case-handling service, but stakeholders do not yet have a trusted, assured view of workload, risk-handling divergence, reporting caveats, and improvement priorities.

The requirements here are written as internal project requirements. They are deliberately role-realistic: different stakeholders care about different parts of the same operating problem, and the analytical product must reconcile those needs without producing contradictory metrics.

## Requirements Posture

The analytics team must not act as a passive reporting function that simply builds whatever view is requested first.

The team must:

- clarify what decision each stakeholder needs to make
- identify where stakeholder language hides different definitions
- distinguish operational questions from reporting questions
- separate flow-level, event-level, case-level, and case-event-level requirements
- define which requests are safe, which need caveats, and which should be rejected
- turn the stakeholder pressure into a scoped analytical product

This is the requirements-gathering part of the project. It should produce enough clarity that later SQL, Python, dashboard, and reporting work is not built on ambiguous terms.

## Stakeholder Map

| Stakeholder | Primary concern | Decision they need to support | Required project response |
|---|---|---|---|
| Operations Lead | Case workload, case depth, dispute and chargeback pressure, process burden | Where should operational attention, staffing, triage, or process improvement focus? | Quantify case burden, identify concentration, separate shallow and deep case paths, and show workload by valid operational segments. |
| Risk / Assurance Lead | Divergence between eventual truth and institutional handling | Where are we over-acting, under-acting, or misaligned with the eventual risk view? | Build truth-bank alignment analysis, distinguish truth-positive from bank-positive, and define safe interpretation of disagreement. |
| BI / Data Lead | Reporting definitions, metric trust, refreshable outputs, quality checks | Which metrics and tables can be safely exposed in reporting products? | Create metric definitions, source-to-output rules, QA checks, and dashboard-ready tables with caveats. |
| Data Governance / Responsible Analytics Lead | Safe use, leakage, caveats, offline-only fields, label meaning | What must be prevented before outputs influence decisions? | Document live/offline boundaries, structural nulls, target semantics, permitted uses, prohibited uses, and known limitations. |
| Executive Sponsor | High-level service pressure, risk posture, priority actions | What are the key issues, what should be improved first, and how confident are we? | Produce a plain-English briefing with key findings, confidence levels, caveats, and recommended actions. |
| Operational Users | Usable filters, clear definitions, practical views | How can they inspect workload or risk without misreading the data? | Design dashboard/reporting pages with definitions, filters, and warning labels where needed. |
| Platform / MLOps Partner | Analytical use of platform-derived surfaces and potential feedback into monitoring | Which analytical findings suggest platform monitoring, feature, or data-product improvements? | Identify reusable checks, data-quality concerns, and responsible-use issues that should inform platform monitoring or future engineering. |

## Central Requirement

The project must answer:

> **Where is operational burden coming from, how does institutional handling diverge from eventual truth, and what action should stakeholders take to improve reporting, workload management, and risk handling?**

This requirement has three coupled parts:

1. **Operational burden.** Understand the case workload and where it concentrates.
2. **Risk-handling divergence.** Understand how institutional judgement differs from eventual truth.
3. **Trusted reporting.** Define metrics, caveats, and outputs that stakeholders can use without being misled.

These parts must remain coupled. Separating them into independent mini-projects would weaken the result because case burden, risk divergence, and reporting trust explain one another.

## Stakeholder Questions

### Operations Lead

The Operations Lead needs to understand workload in practical operating terms.

Key questions:

- How many flows become cases?
- How many case events are generated?
- Which case paths are shallow, and which become operationally deep?
- What share of cases involve disputes, chargebacks, or write-off-like outcomes?
- Which truth-bank alignment groups produce the most case volume?
- Are certain channels, route types, merchants, or entity patterns producing disproportionate workload?
- Which workload segments should be prioritised for process review?

Expected answer shape:

- case coverage metrics
- case depth analysis
- case path breakdown
- burden concentration views
- operational recommendation table

### Risk / Assurance Lead

The Risk / Assurance Lead needs to understand whether institutional handling aligns with eventual truth.

Key questions:

- How often do truth and bank view agree?
- Where does the institution appear to over-act?
- Where does the institution appear to under-act?
- Are disagreement patterns concentrated in particular segments?
- Does case handling explain or amplify the disagreement?
- Which divergence groups create the largest operational or risk concern?
- Which label should be used for which analytical purpose?

Expected answer shape:

- truth-bank matrix
- divergence-rate metrics
- disagreement by case coverage and depth
- segment-level divergence views
- interpretation guidance separating truth, bank view, and case outcomes

### BI / Data Lead

The BI / Data Lead needs a reporting model that can be trusted.

Key questions:

- What is the reporting grain?
- Which tables are valid sources for dashboard metrics?
- Which joins are allowed?
- Which metrics are event-grain, flow-grain, case-grain, or case-event-grain?
- Which structural nulls should be explained instead of treated as quality defects?
- Which metrics need caveat labels?
- Which extracts should be dashboard-ready rather than notebook-only?

Expected answer shape:

- flow-level mart design
- case summary table design
- metric definition pack
- source-to-target mapping
- QA checks and reconciliation outputs
- dashboard-ready tables

### Data Governance / Responsible Analytics Lead

The Governance Lead needs to prevent unsafe or misleading use.

Key questions:

- Which surfaces are live-safe, offline-only, or reporting-only?
- Which fields would leak future knowledge if used in live scoring?
- What is the difference between `fraud_flag`, truth-positive labels, explicit `FRAUD`, bank view, and case outcomes?
- Which null patterns are structural?
- Which stakeholder claims would be unsupported or unsafe?
- Which caveats must appear in reports and dashboards?

Expected answer shape:

- responsible analytics note
- safe-use and prohibited-use table
- leakage warning table
- target-definition guidance
- caveat register

### Executive Sponsor

The Executive Sponsor needs a decision-ready synthesis.

Key questions:

- What is the overall burden picture?
- Where is the largest pressure?
- What is the most important divergence issue?
- What can be improved first?
- Which metrics can leadership trust?
- Which conclusions require caution?
- What should be monitored next?

Expected answer shape:

- one-to-two page stakeholder briefing
- executive dashboard page
- key findings and recommendations
- confidence and caveat summary

### Operational Users

Operational users need a product they can actually use.

Key questions:

- Can they filter workload by channel, route, merchant, time, or alignment group?
- Are definitions visible enough to prevent misuse?
- Can they identify priority segments without reading technical notebooks?
- Are caveats visible at the point where a metric is used?
- Can they distinguish flow counts, case counts, and case-event counts?

Expected answer shape:

- dashboard/reporting pages
- user-facing definitions
- practical filters
- warning labels for caveated metrics

### Platform / MLOps Partner

The Platform / MLOps partner needs to know whether analytical findings expose reusable platform checks or monitoring concerns.

Key questions:

- Which reconciliation checks should become repeatable monitoring checks?
- Which source-surface caveats affect future platform analytics?
- Which offline-only fields must be kept out of live feature paths?
- Which label or target definitions need stronger governance before modelling?
- Which analytical marts could become reusable data products?

Expected answer shape:

- reusable QA check list
- future monitoring candidates
- data-product recommendations
- model-readiness caveats where relevant

## Requirement Priorities

| Priority | Requirement | Why it matters |
|---|---|---|
| P0 | Build a valid flow-level analytical mart | Without a trusted grain, later reporting can double-count or misjoin surfaces. |
| P0 | Define truth, bank view, case, and fraud marker semantics | The project cannot make risk claims if these fields are conflated. |
| P0 | Quantify truth-bank divergence | This is one of the central stakeholder concerns. |
| P0 | Quantify operational case burden | Workload pressure is the main operational question. |
| P0 | Produce metric definitions and denominator rules | Dashboard/reporting outputs are unsafe without this. |
| P1 | Analyse burden and divergence by key segments | This turns aggregate findings into actionable operational priorities. |
| P1 | Produce QA and reconciliation pack | The work must be trusted before it is communicated. |
| P1 | Produce stakeholder briefing | Findings must be translated into decisions and recommendations. |
| P1 | Produce dashboard-ready tables and reporting design | The output must be usable beyond the notebook. |
| P2 | Identify platform monitoring candidates | Useful follow-on, but not required before the first stakeholder product. |
| P2 | Package final case-study narratives | Only after execution is complete and evidence exists. |

## Acceptance Expectations by Stakeholder

| Stakeholder | The project is acceptable if... |
|---|---|
| Operations Lead | The output identifies workload volume, case depth, and burden concentration without confusing flows, cases, and case events. |
| Risk / Assurance Lead | The output explains truth-bank agreement and disagreement with clear label definitions and defensible caveats. |
| BI / Data Lead | The output contains reproducible source-to-output logic, documented metrics, and dashboard-ready tables. |
| Governance Lead | The output separates safe, caveated, and prohibited uses and does not hide leakage or label-definition risks. |
| Executive Sponsor | The briefing explains what matters, why it matters, what action is recommended, and how confident the team is. |
| Operational Users | The reporting product is usable without reading the full technical analysis and includes enough definitions to avoid misuse. |
| Platform / MLOps Partner | The work identifies reusable checks or data-product lessons without requiring immediate platform changes. |

## Requirements Risks

The main requirements risk is that stakeholders may use the same words for different things.

Examples:

- "fraud" may mean upstream `fraud_flag`, truth-positive, explicit `FRAUD`, bank-positive, case-confirmed fraud, or chargeback/write-off outcome.
- "case burden" may mean number of case flows, number of case events, deep cases, chargeback cases, or operational handling effort.
- "transaction volume" may mean event rows, flows, arrivals, or amount exposure.
- "risk" may mean supervised truth, institutional action, expected loss, operational review burden, or customer friction.

This project must make those terms explicit before building stakeholder-facing outputs.

## Requirements Conclusion

The stakeholder requirement is not simply to build a dashboard.

The requirement is to create a trusted operational insight product that helps the organisation understand burden, divergence, and reporting risk. The project must convert ambiguous stakeholder concerns into a flow-grain analytical mart, assured metrics, burden/divergence analysis, dashboard-ready outputs, and a clear briefing.

The next planning document, `02_data_scope_and_metric_contract.md`, defines which surfaces, grains, joins, and metric rules are allowed to satisfy these requirements.
