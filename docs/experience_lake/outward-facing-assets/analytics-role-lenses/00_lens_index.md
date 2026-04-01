# Analytics Role Lenses Index

As of `2026-04-01`

Purpose:
- define the growing set of analytics-role lenses through which the same platform world can be read
- stop any single analytics scenario from becoming the de facto template for all outward-facing analytics interpretation
- provide the master index from which future lens files, job-ad mappings, ideal-candidate mappings, and role-specific claim surfaces can grow

Boundary:
- this folder does not create a second project
- this folder does not replace the platform truth
- this folder does not invent fake employment
- this folder exists to expose more of the same governed platform world through different role lenses over time

Related documents:
- [analytics-role-adoption-posture.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-angle\analytics-role-adoption-posture.md)
- [01_progression_and_entry_point.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\01_progression_and_entry_point.md)
- [fraud_operations_risk_intelligence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-angle\fraud_operations_risk_intelligence.md)
- [data-analytics-engineering-science.job-ads.evidence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.job-ads.evidence.md)
- [data-analytics-engineering-science.ideal-candidate-profiles.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.ideal-candidate-profiles.md)

---

## 1. Why This Folder Exists

The platform already has an `ML Platform / MLOps` reading. It also already has at least one concrete analytics reading in [fraud_operations_risk_intelligence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-angle\fraud_operations_risk_intelligence.md). But one analytics scenario is not enough.

If we leave the current analytics material as the default path, it will become too easy to force every analytics-facing role into one narrow interpretation. That would make the outward-facing work too rigid and would underuse the actual breadth of the governed platform world.

This folder exists to prevent that.

It treats analytics-role interpretation as a growing system of lenses rather than as a single fixed storyline. Each lens reveals a different responsibility surface within the same platform world. As more job ads are collected, more ideal-candidate profiles are written, and more outward-facing role thinking develops, these lenses should grow, refine, split, and become more specific.

The intent is not to create more noise. The intent is to progressively expose more of what this world can truthfully hold as role-shaped work.

## 1A. Folder Structure Rule

This folder should stay scalable as job ads grow.

So the structure should be:
- top-level index and control documents at the folder root
- role-execution files inside role-specific subfolders

Examples:
- `analytics-role-lenses\\data_scientist\\`
- `analytics-role-lenses\\data_analyst\\`
- `analytics-role-lenses\\business_analyst\\`

This keeps the top level readable while allowing role-specific work to grow without clutter.

## 2. What A Lens Means Here

A lens is a role-shaped way of reading the same platform world.

It is not:
- a fake project
- a fake employer
- a disconnected portfolio branch

It is:
- a structured role interpretation
- a responsibility surface
- a way of asking what this world looks like from a specific type of professional ownership

Examples:
- from one lens, the platform may be read as an operational performance environment
- from another lens, it may be read as a BI and reporting environment
- from another, as a governed analytical data-product environment
- from another, as a business-analysis and change-support environment

The world stays fixed.
The lens changes.

## 3. Growth Rule

This folder should remain alive and expanding.

The intended pattern is:
- new job ads are added
- new ideal-candidate profiles are added
- those profiles reveal or sharpen lenses
- existing lenses gain more responsibilities, outputs, and claim surfaces
- if a lens becomes too broad, it can split into smaller lenses

So the lens system should behave like a growing web:
- more light enters
- more of the role surface becomes visible
- responsibilities become more concrete
- claims become easier to defend
- quick implementation paths become clearer for interview or application support

This index is therefore not a fixed taxonomy for all time. It is the current organising surface.

## 4. Current Lens Set

The current lens set is the active working form of the lens system.

These lenses are best understood as:
- responsibility-based lenses
- grouping surfaces for related job-ad demands
- a way to take repeated responsibility patterns from the job ads and examine what those responsibilities mean inside this platform world

This is the preferred direction because it keeps the work anchored to actual responsibilities rather than allowing it to become too vague at the role-description level.

So the main governing question for a lens is:

`When this responsibility family is transferred into our platform world, what does it actually mean, what does it touch, and what work does it create here?`

That is the active interpretation that should guide future lens development.

### 4.1 Operational Performance Analytics Over Governed Truth Surfaces

Definition:
- roles centred on service performance, throughput, targets, workflow pressure, trend tracking, waiting times, operational intervention, and KPI-led monitoring
- this lens is based primarily on persisted governed truth surfaces rather than on active live platform runtime
- its default mode is bounded or historical operational analysis over trusted datasets, not real-time operator telemetry

Current role examples feeding this lens:
- `Data Analyst - HUC`
- `Data Analyst - InHealth Group`
- `Data and Information Officer - Hertfordshire Partnership University NHS Foundation Trust`

Future lens file:
- `01_operational-performance-analytics.md`

### 4.2 BI, Insight, and Reporting Analytics

Definition:
- roles centred on dashboards, board packs, stakeholder reporting, data storytelling, visualisation, scheduled reporting, and decision-support outputs

Current role examples feeding this lens:
- `Data Analyst - HUC`
- `Data Analyst - InHealth Group`
- `Data & Insight Analyst - Claire House`
- `Data Insight Analyst - The Money and Pensions Service`

Future lens file:
- `02_bi-insight-reporting.md`

### 4.3 Data Quality, Governance, and Trusted Information Stewardship

Definition:
- roles centred on trusted data, reconciliation, validation, integrity, compliant handling, controlled reporting inputs, and governance-aware analytical work

Current role examples feeding this lens:
- `Data Scientist - Midlands Partnership NHS Foundation Trust`
- `Data & Insight Analyst - Claire House`
- `Data and Information Officer - Hertfordshire Partnership University NHS Foundation Trust`
- `Data Insight Analyst - The Money and Pensions Service`
- `Payroll Data Analyst x 2 - Welsh Government`

Future lens file:
- `03_data-quality-governance-analytics.md`

### 4.4 Analytics Engineering and Analytical Data Product

Definition:
- roles centred on shaping analytical datasets, building reporting-ready models, designing governed analytical layers, supporting metric logic, and making data usable downstream

Current role examples feeding this lens:
- `Data Scientist - Midlands Partnership NHS Foundation Trust`
- `Data & Insight Analyst - Claire House`
- `Data Insight Analyst - The Money and Pensions Service`
- `Business Analyst - The Pensions Regulator` partially

Future lens file:
- `04_analytics-engineering-data-product.md`

### 4.5 Business Analysis, Change, and Decision Support

Definition:
- roles centred on process understanding, requirement shaping, options and impact analysis, stakeholder translation, and supporting business change through data and structured analysis

Current role examples feeding this lens:
- `Business Analyst - The Pensions Regulator`
- `Data & Insight Analyst - Claire House`
- `Data and Information Officer - Hertfordshire Partnership University NHS Foundation Trust`
- `Data Insight Analyst - The Money and Pensions Service`

Future lens file:
- `05_business-analysis-change-support.md`

### 4.6 Domain-Control and Compliance Analytics

Definition:
- roles centred on reconciliation, auditability, rule-bound data handling, control reporting, exceptions, and high-accountability domain operations

Current role examples feeding this lens:
- `Payroll Data Analyst x 2 - Welsh Government`

Future lens file:
- `06_domain-control-compliance-analytics.md`

### 4.7 Advanced Analytics and Data Science

Definition:
- roles centred on modelling, segmentation, prediction, population-level analysis, governed model deployment, and advanced analytical methods in operational settings

Current role examples feeding this lens:
- `Data Scientist - Midlands Partnership NHS Foundation Trust`

Future lens file:
- `07_advanced-analytics-data-science.md`

### 4.8 Stakeholder Translation, Communication, and Decision Influence

Definition:
- roles centred on explaining complex analytical outputs to non-technical audiences, shaping stakeholder understanding, packaging evidence for decision forums, and turning governed analysis into action-oriented meaning

Current role examples feeding this lens:
- `Data Scientist - Midlands Partnership NHS Foundation Trust`
- `Data Analyst - HUC`
- `Data Analyst - InHealth Group`
- `Data & Insight Analyst - Claire House`
- `Data and Information Officer - Hertfordshire Partnership University NHS Foundation Trust`
- `Data Insight Analyst - The Money and Pensions Service`
- `Business Analyst - The Pensions Regulator`

Future lens file:
- `08_stakeholder-translation-communication-influence.md`

### 4.9 Analytical Delivery Operating Discipline

Definition:
- roles centred on reproducibility, version control, lineage, stable definitions, regeneration paths, reusable analytical products, and the controlled operating discipline needed to keep analytical work trustworthy over time

Current role examples feeding this lens:
- `Data Scientist - Midlands Partnership NHS Foundation Trust`
- `Data & Insight Analyst - Claire House`
- `Data Insight Analyst - The Money and Pensions Service`
- `Payroll Data Analyst x 2 - Welsh Government`
- `Business Analyst - The Pensions Regulator` partially

Future lens file:
- `09_analytical-delivery-operating-discipline.md`

## 5. Status Of The Existing Analytics Scenario

[fraud_operations_risk_intelligence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-angle\fraud_operations_risk_intelligence.md) remains useful, but its role is now clarified:

It is one worked analytics lane.

It is not the universal analytics template for this platform.

It should therefore be read as:
- one concrete analytical interpretation
- one scenario instantiation
- one outward-facing example of the broader lens system

Over time, additional worked lanes may emerge under other lenses.

## 6. What Each Future Lens File Should Eventually Contain

Each lens file should grow over time and should eventually contain:
- the definition of the lens
- which job ads currently feed it
- which ideal-candidate profiles currently feed it
- which parts of the platform world this lens exposes
- what responsibilities this lens would carry in that world
- what outputs or deliverables this lens would produce
- what problems this lens would solve
- what can be implemented quickly, if needed, to make the lens more concrete for application or interview support

The key is that the lens file should not stop at naming a responsibility family.

It should go further and answer:
- what does this responsibility family actually mean in this platform world?
- which governed datasets or truth surfaces would it work on?
- what kind of analyses, routines, artefacts, and judgements would it involve?
- how would it be defended if challenged in detail?

Role-specific expression may still be derived later, but it should be derived from mature responsibility lenses rather than used as the primary organising principle.

## 7. Active Analytics Focus Rule

For the current analytics-role expansion phase, the primary focus is the `governed data world`.

That means the main analytical substrate for the lens system is:
- the generated datasets already produced by the data engine
- the trusted truth surfaces already available in the oracle-facing world
- event truth, case truth, label truth, timeline truth, context structure, and other persisted analytical surfaces

Important operational note:
- these governed datasets are currently resident in the `Oracle store`
- they should not be casually described as if they are sitting locally in the repo as ready-to-query local analytical files
- where local work is needed, it should be thought of as working from bounded extracts, shaped slices, or derived analytical views from the oracle-resident governed world

This is the area that carries the strongest analytical value because:
- it is where the statistical and analytical substance already exists
- it supports KPI design, SQL work, reporting logic, dashboards, DAX-style thinking, anomaly investigation, and decision-support interpretation
- it is immediately reusable without re-incurring platform runtime cost
- it keeps the role lenses grounded in a world that is already rich, governed, and defensible

## 8. Cost and Execution Discipline For Lens Work

The default rule for this folder is:

`governed data world first, platform runtime only if genuinely needed`

In practice, this means:
- do not default to rerunning ingestion
- do not default to rerunning streaming paths
- do not default to rerunning the full platform end to end
- do not assume active runtime participation is needed to make an analytics claim credible

For most analytics lenses, the highest-impact and lowest-cost path is:
- work from existing generated datasets
- work from persisted truth surfaces
- use time slices, analytical slices, and bounded extracts where needed
- shape outputs locally or cheaply where that helps make the lens concrete

This posture exists because the goal of this lane is not to prove live platform operation again. The goal is to expose the analytics-role responsibility surfaces that already exist in the world the platform created.

## 9. Role-Lens Scope Discipline

The current analytics-lens programme should favour lenses that stay close to the governed data world, for example:
- operational performance analytics
- BI, insight, and reporting analytics
- data quality, reconciliation, and trusted-information work
- business-facing decision support
- selective advanced analytics where the existing datasets already support it

The current analytics-lens programme should de-emphasize, by default:
- ingestion-heavy interpretations
- streaming-runtime-heavy interpretations
- operational telemetry as the primary basis for analytics work
- data-engineering expansion for its own sake

This does not mean those areas are invalid forever. It means they are not the default focus for maximum-impact, low-cost analytics-role development right now.

## 10. Practical Consequence For Future Lens Development

When developing or expanding a lens, the first question should be:

`What can this lens expose from the governed data world we already have?`

Only after that should we ask whether any extra execution is needed.

In most cases, the preferred order is:
1. use existing governed datasets
2. use persisted truth surfaces
3. use analytical time slices or bounded extracts
4. add lightweight implementation surfaces such as SQL, dashboard logic, DAX-style measures, or reporting packs
5. only consider live platform execution if the lens genuinely cannot be made concrete otherwise

This rule is intended to keep the lens system:
- grounded
- cheap to work with
- quick to operationalise for applications or interviews
- defensible without unnecessary reruns

## 11. How This Folder Should Be Used

The intended workflow is:

1. collect job ads
2. extract raw evidence
3. write ideal-candidate profiles
4. map those profiles into lenses
5. grow the lens files
6. expose the platform through each responsibility lens
7. only later derive role-shaped interpretation where useful

So this folder is the bridge between:
- job-market evidence
- role-adoption posture
- and future application-ready role framing

In practical terms, that bridge has two layers:

### 11.1 Classification layer

This is the layer currently represented by the lens set in this index.

Its purpose is to:
- sort job ads into broad role/responsibility families
- show where different ideal-candidate profiles overlap
- reveal the main analytics-role territories already visible in the corpus

### 11.2 Execution-depth layer

This is the layer the folder should move toward next.

Its purpose is to:
- take one responsibility lens at a time
- expose what that responsibility means in execution inside the platform world
- connect those execution details back to job-ad responsibilities, specifications, and ideal-candidate expectations

This second layer is the one that ultimately matters most for truthful role embodiment and later application defence.

## 12. Anti-Drift Rules For This Folder

- Do not let one analytics scenario become the master template for every role.
- Do not treat the lens set as permanently fixed.
- Do not invent new lenses without a real job-ad or role-shape reason.
- Do not collapse different role shapes into one vague “analytics” bucket when they are materially different.
- Do not forget that all lenses still depend on the same governed platform world.
- Do not use this folder to create fake projects or fake employer history.
- Do not overfocus on one tool, one dashboard, or one reporting surface at the expense of the broader role lens.
- Do not default to rerunning ingestion or the full platform when the existing governed datasets are already sufficient.
- Do not let the analytics lane drift into data-engineering work unless that expansion is explicitly needed.
- Do not jump too early into role-shaped prose if it weakens the depth of the actual responsibility analysis.
- Do not let ideal-candidate language flatten the concrete responsibility surfaces the platform can actually support.

## 13. Current Working Consequence

The platform should now be read as a governed world that can support multiple outward-facing analytics-role interpretations.

This means the next steps are no longer:
- force everything through one analytics document
- or jump straight into CV writing

The next steps are:
- keep collecting job ads
- keep expanding ideal-candidate profiles
- let those profiles sharpen the lenses
- deepen the active responsibility-based lenses
- use those lenses to expose more of the platform as truthful responsibility-shaped work
- only derive role-shaped interpretation later where it genuinely helps

That is how the role becomes more real, more executable, and more defensible over time.
