# Advanced Analytics Programme

## Purpose

This folder holds the next phase after the data-interface investigation.

The previous investigation established what the advanced analytics team can see from the live fraud decisioning platform's interface pack: traffic primitives, behavioural streams, behavioural context, truth products, case products, and the limits attached to each. This programme turns that understood data world into a controlled set of analytical delivery briefs.

The goal is not to invent dashboard questions. The goal is to emulate the kind of work an advanced analytics, BI, risk, fraud operations, and data governance team would receive inside a company operating the platform.

Each brief should therefore be substantial enough to guide real work:

- what operating problem triggered the work
- which stakeholders need the answer
- what decision or service action the work supports
- what data is valid for the work
- what analytical method is appropriate
- what output will be delivered
- how the work will be quality-assured
- what risks, caveats, and realism concerns must be carried forward

This programme is not a job-ad mapping exercise. The job-ad and recruiter-call material informs the level of professional seriousness expected from the work, but briefs should not be designed as tick-box responses to named employers. More roles will appear, and the stronger strategy is to build a small number of rich, defensible analytical projects that would stand up across many public-sector, NHS, civil-service, operational analytics, BI, and data-science contexts.

## Operating Assumption

We are working as the advanced analytics function inside an organisation running an AWS-hosted fraud decisioning platform.

The platform is treated as live and operational. The data available to the analytics team is the governed extract described by the data interface pack and represented in the current local run. The Data Engine remains outside the operating team's direct control for this phase; its outputs are treated as the source systems and analytical surfaces available to the company.

This means briefs should be written as real internal delivery work, not as portfolio demonstrations. They should sound like work commissioned because a stakeholder, service owner, risk lead, fraud operations team, data manager, or senior decision-maker needs a defensible answer.

## Programme Structure

```text
analysis/advanced_analytics_programme/
  README.md
  templates/
    project_brief_template.md
  briefs/
    <brief-id>_<brief-name>/
      brief.md
      delivery_plan.md
      assurance_log.md
      findings_register.md
  execution/
    <brief-id>_<brief-name>/
      notebooks/
      sql/
      extracts/
      figures/
      dashboard_candidates/
      reports/
  governance/
    data_fitness_register.md
    analytical_assurance_register.md
    stakeholder_decision_log.md
  shared_assets/
    reusable_sql/
    reusable_plotting/
    metric_definitions/
    glossary.md
```

The structure separates the brief from execution. A brief defines the work. The execution folder holds the analytical notebooks, queries, figures, extracts, dashboard candidates, and final reports used to answer it.

## Document Roles

### Programme README

Defines the operating posture, folder structure, delivery standards, and how project briefs should be treated.

### Project brief template

The reusable template for every serious analytical project in this programme. It is intentionally richer than a one-page request because thin briefs produce weak analysis.

### Brief folder

Each approved project receives its own brief folder under `briefs/`. This is where the problem statement, stakeholder needs, delivery scope, risks, and expected outcomes live.

### Execution folder

Each project receives a matching folder under `execution/`. This is where the actual analysis happens. Execution artifacts should not be dumped into the brief. The brief points to the work; it does not become the workbench.

### Governance folder

Cross-brief registers belong here. Examples include data fitness concerns, analytical assumptions, quality-assurance checks, and stakeholder decisions that affect more than one brief.

### Shared assets

Reusable metric definitions, SQL fragments, plotting utilities, and glossary entries belong here once they become common across briefs.

## Brief Lifecycle

1. **Candidate brief raised.** A potential stakeholder problem is identified from the interface-world investigation or from a credible operating need.
2. **Brief drafted.** The template is completed far enough to define the problem, decision need, data scope, risks, and likely outputs.
3. **Scope review.** The brief is checked for realism, analytical value, data feasibility, and whether it depends on unavailable or unsafe fields.
4. **Execution approved.** Only approved briefs receive execution folders and notebooks.
5. **Investigation and build.** Work proceeds through notebooks, SQL, compact exports, figures, and dashboard/report candidates.
6. **Assurance review.** Denominators, leakage, label definitions, data quality, and synthetic-world limits are checked before conclusions are used.
7. **Stakeholder-ready output.** The final output is produced as a report, dashboard, memo, model evaluation, monitoring design, or operational recommendation.
8. **Experience capture.** Only after delivery is complete should the work be translated into outward-facing experience evidence.

## Brief Selection Standards

A brief should not be accepted just because it sounds analytically interesting.

A good brief should satisfy most of the following:

- it is rooted in the operating fraud platform, not generic fraud analysis
- it has a stakeholder who would plausibly care about the result
- it supports a decision, action, monitoring need, or governance judgement
- it uses data surfaces the advanced analytics team would legitimately have
- it can be answered locally without rerunning the Data Engine or incurring platform cost
- it contains enough uncertainty to justify investigation
- it has a clear output and assurance standard
- it can produce defensible findings even if the final answer is "the data is not fit for this claim"

## Flagship Brief Standard

The programme should favour a small number of rich flagship briefs over many thin slices.

Each flagship brief should behave like a real cross-functional company project. It should not isolate one capability such as `SQL`, `Power BI`, modelling, governance, stakeholder engagement, or data quality into a separate standalone exercise. In real analytical delivery, those capabilities usually appear together:

- stakeholders raise an operational or strategic concern
- analysts clarify the decision need
- data owners and platform teams help define valid surfaces and caveats
- SQL and Python are used to inspect, join, summarize, and validate the data
- statistical analysis exposes what is actually happening
- visual evidence and BI candidates make the findings usable
- governance and assurance determine what can be safely claimed
- recommendations are written for operational, technical, and senior audiences

For this reason, each approved flagship brief should carry the full delivery arc unless there is a clear reason not to:

- stakeholder demand and requirement clarification
- operational context inside the fraud decisioning platform
- data-surface selection and grain discipline
- SQL/Python analytical work
- data-quality and realism assessment
- statistical or modelling method where appropriate
- visual evidence and dashboard/report candidates
- analytical assurance and limitation control
- stakeholder-facing recommendations
- reusable assets such as SQL, definitions, or metric logic

The expected portfolio shape is therefore not ten small exercises. It is closer to two or three serious briefs that are rich enough to support multiple discussions about stakeholder management, technical execution, analytical judgement, data governance, communication, and business impact.

## Analytical Standards

Every project must preserve the standards learned during the interface investigation:

- state the grain before calculating metrics
- state the denominator before presenting rates or shares
- separate event, flow, case, session, and entity-level claims
- distinguish live-safe fields from offline-only fields
- avoid target leakage in modelling or feature claims
- keep `fraud_flag`, supervised truth, bank view, campaign markers, and case outcomes semantically separate
- distinguish explicit fraud from broader abuse/risk-positive labels
- document realism concerns instead of hiding them
- use compact DuckDB summaries where data is large
- treat visuals as evidence, not decoration
- state what each analysis proves and what it does not prove

## Current Source Context

The programme is grounded in the current interface-world investigation:

- [`../dev_full_offline_investigation/00_investigation/watson_workbench/notes/interface_world`](../dev_full_offline_investigation/00_investigation/watson_workbench/notes/interface_world)

The current pinned data source remains:

- [`../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1`](../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1)

## Current Status

No project briefs are approved yet.

The next step is to draft candidate flagship briefs from the investigative leads already uncovered: truth/bank divergence, case burden, data fitness for fraud analytics, amount/denominator discipline, customer or merchant risk posture, model target definition, and stakeholder-facing monitoring.
