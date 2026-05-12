# Tesco Mobile Data Scientist - Role Mapping Methodology

This document captures the reasoning journey used to move from the Tesco Mobile Data Scientist job ad to resume-facing achievement bullets.

The central correction is:

> The CV should not lead with evidence, tools, model validation, or platform mechanics. It should lead with the hiring manager's problem.

For this role, the hiring problem is stated directly in the job ad:

> "use data and analytical thinking to solve real business problems and improve customer experiences"

The first experience block must therefore make the recruiter see, quickly and repeatedly, that the candidate has solved Tesco-like problems: customer communications, marketing effectiveness, churn, propensity, fraud/unusual behaviour, customer targeting, and evidence-led business decisions.

## Source Anchors From The Job Ad

| Job ad source wording | What it means for the CV |
|---|---|
| "use data and analytical thinking to solve real business problems and improve customer experiences" | The CV must be problem-facing, not tool-facing. |
| "wide range of projects, from personalising customer communications and improving marketing effectiveness" | Customer communication and marketing effectiveness are primary Tesco problem areas. |
| "to optimising stock management and reducing customer churn" | Operational decisions and churn reduction are named business outcomes. |
| "Your work will directly shape how we make decisions across the business" | The bullets must show decision impact, not just model outputs. |
| "Experience with churn, fraud or propensity modelling would be desirable" | Churn, fraud, and propensity are important modelling/problem domains. |
| "Analyse complex and diverse datasets using statistical methods to generate insights that improve customer experience and business outcomes" | Analytical work must be tied to customer and business outcomes. |
| "Build, validate, optimise and manage data science models and data pipelines" | Models and pipelines matter, but they are the method, not the lead signal. |

## The Mistake Corrected

The earlier approach drifted into an evidence-led structure.

It tried to combine:

> business problem + mechanism + measured result + technical proof + method/tooling

That became too heavy. It made each bullet read like a compressed technical report:

- model comparison;
- validation method;
- PySpark pipelines;
- feature engineering;
- tooling;
- monitoring;
- documentation.

Those details are useful for defence, but they should not dominate the visible bullet.

The corrected view is:

> The evidence ledger answers: "Can this be defended?"  
> The CV bullet answers: "Can the recruiter instantly see Tesco's problem being solved?"

Those are different jobs.

## Corrected Bullet-Building Rule

The bullet should be built from the employer problem hierarchy.

Visible bullet logic:

> Tesco business outcome -> specific Tesco scenario/mechanism -> measured result -> compressed method

The technical method should appear only as a short signal at the end, where needed.

Examples of compressed method signals:

- customer behaviour modelling;
- propensity scoring;
- customer segmentation;
- response-likelihood scoring;
- fraud-style behaviour modelling;
- champion/challenger-style evaluation.

Avoid letting the method expand into the full technical defence unless the bullet specifically needs that signal.

## Problem Hierarchy Used

### Level 0 - Umbrella Problem

> Use data and analytical thinking to solve real business problems and improve customer experiences.

### Level 1 - Broad Outcomes

The role expects work that improves:

- customer experience;
- business outcomes;
- marketing effectiveness;
- churn reduction;
- operational decisions;
- product/process/performance;
- business decision-making.

### Level 2 - Named Problem / Project Areas

The job ad gives these areas directly:

- personalising customer communications;
- improving marketing effectiveness;
- optimising stock management;
- reducing customer churn;
- churn modelling;
- fraud modelling;
- propensity modelling.

### Level 3 - Concrete Tesco-Like Scenarios

Level 3 makes the job ad less vague by naming the customer/business situation and mechanism.

Examples:

- reduce churn risk among customers approaching a retention or renewal decision point;
- identify customers most likely to respond to offers, messages, products, or interventions;
- improve targeting for tariffs, handset upgrades, add-ons, retention, or SIM-only campaigns;
- reduce wasted marketing effort by excluding poor-fit customers;
- personalise renewal, upgrade, SIM-only, add-on, or retention messages;
- detect unusual account, usage, device, SIM, or transaction behaviour earlier;
- compare customer targeting or intervention strategies before rollout.

## Problem Chains

The problem chain connects the concrete Tesco problem upward into the broader hiring problem.

| Problem chain | Level 3 concrete problem | Level 2 business area | Level 1 / Level 0 outcome |
|---|---|---|---|
| Churn / retention | Reduce churn risk among customers approaching a retention decision point. | Customer churn reduction / churn modelling | Improve customer experience and business outcomes. |
| Early-life churn | Reduce early-life churn among new Tesco Mobile customers. | Customer churn reduction / churn modelling | Improve customer experience and business outcomes. |
| Customer targeting / propensity | Identify customers most likely to respond to a specific offer, product, message, or intervention. | Propensity modelling / customer targeting | Improve customer experience, business outcomes, and decision-making. |
| Communication relevance / personalisation | Personalise renewal, upgrade, SIM-only, add-on, or retention messages for different customer groups. | Customer communication personalisation | Improve customer experience and marketing effectiveness. |
| Poor-fit communication | Reduce generic or poorly timed customer communications. | Customer communication personalisation | Improve customer experience and business outcomes. |
| Marketing targeting | Improve targeting for tariffs, handset upgrades, add-ons, retention, or SIM-only campaigns. | Marketing effectiveness improvement | Improve business outcomes, performance, and decision-making. |
| Marketing waste | Reduce wasted marketing effort by excluding poor-fit customers from campaigns. | Marketing effectiveness improvement | Improve business outcomes and performance. |
| Stock planning | Improve handset or SIM stock planning around expected customer demand. | Stock management optimisation | Improve processes, performance, and resource planning. |
| Demand alignment | Align stock decisions with customer behaviour and campaign demand. | Stock management optimisation | Improve processes, performance, and decision-making. |
| Fraud / abnormal behaviour | Detect unusual account, usage, device, SIM, or transaction behaviour earlier. | Fraud modelling / fraud detection | Improve business outcomes, performance, and customer protection. |
| Business decision-shaping | Compare customer targeting or intervention strategies before rollout. | Evidence-led decision-making | Shape business decisions and improve outcomes. |

## Chains Selected For The First Experience Block

The first experience block should carry the strongest Tesco-facing signals. The selection is based on the hiring manager's hierarchy, not on platform convenience.

| Priority | Chain | Reason |
|---|---|---|
| 1 | Churn / retention | Tesco directly names reducing customer churn, and churn modelling is desirable. |
| 2 | Customer targeting / propensity | Propensity modelling is directly named and supports communications, marketing effectiveness, and business decisioning. |
| 3 | Marketing targeting / marketing waste | Tesco directly names improving marketing effectiveness. |
| 4 | Communication relevance / personalisation | Tesco directly names personalising customer communications and keeping customers at the heart of decisions. |
| 5 | Fraud / abnormal behaviour | Fraud modelling is directly named as desirable and gives a strong customer-data modelling signal. |
| 6 | Business decision-shaping | Tesco says the work will directly shape decisions across the business. |

Stock / demand planning is relevant because the ad names stock management. It is not selected for the first six bullets because it currently has weaker measured achievement language than churn, propensity, marketing, communications, fraud, and decisioning.

## Business-Facing Achievement Directions

These are the business-facing achievement directions before compressed method is added.

| Chain | Business-facing achievement direction |
|---|---|
| Churn / retention | Improved churn-risk identification by identifying customers likely to disengage before a retention decision point. |
| Customer targeting / propensity | Improved propensity-based customer targeting by focusing offers, messages, or interventions on higher-fit customers. |
| Marketing targeting / marketing waste | Reduced low-fit marketing targeting while maintaining priority-customer coverage. |
| Communication relevance / personalisation | Improved customer communication relevance by segmenting customers around behaviour, lifecycle stage, and likely response. |
| Fraud / abnormal behaviour | Improved early detection of unusual customer or account behaviour before later triggers. |
| Business decision-shaping | Improved evidence-led customer decisioning by comparing targeting and intervention strategies before rollout. |
| Stock / demand planning optional | Supported better stock and demand planning decisions by linking customer demand, campaign timing, and product-interest signals. |

## Measured Result Layer

The measured result should prove the business/customer problem moved. It should not merely prove that a model performed better.

| Chain | Business-facing achievement with measured result |
|---|---|
| Churn / retention | Improved churn-risk identification by 18%, identifying customers likely to disengage before a retention decision point. |
| Customer targeting / propensity | Concentrated 42% of likely high-fit customers in the top 20% scored customer segment, improving focus on customers most likely to benefit from offers, messages, or interventions. |
| Marketing targeting / marketing waste | Reduced low-fit marketing targeting by 11% while maintaining high-value customer coverage, helping improve campaign efficiency and reduce wasted customer contact. |
| Communication relevance / personalisation | Improved customer communication relevance by segmenting high-fit customer groups, supporting more targeted retention, upgrade, or intervention messaging. |
| Fraud / abnormal behaviour | Improved early detection of unusual customer/account behaviour by 18%, surfacing abnormal usage, activity, or transaction patterns before later triggers. |
| Business decision-shaping | Compared 3 customer decision strategies across 5 outcome measures, helping select lower-waste targeting/intervention approaches while preserving priority-customer coverage. |
| Stock / demand planning optional | Supported more informed stock and demand planning decisions by linking customer demand signals, campaign timing, and product-interest patterns. |

## Compressed Method Layer

Compressed method is added lightly. It should explain how the business result was achieved without taking over the bullet.

| Business-facing achievement + measure | Compressed method |
|---|---|
| Improved churn-risk identification by 18% | through customer behaviour modelling and churn/propensity scoring |
| Concentrated 42% of likely high-fit customers in the top 20% scored customer segment | using propensity scoring and customer segmentation |
| Reduced low-fit marketing targeting by 11% while maintaining high-value customer coverage | using model-led customer targeting and segment comparison |
| Improved customer communication relevance | using lifecycle, behaviour, and response-likelihood segmentation |
| Improved early detection of unusual customer/account behaviour by 18% | through fraud-style customer behaviour modelling |
| Compared 3 customer decision strategies across 5 outcome measures | using champion/challenger-style strategy evaluation |

## Final First Experience Block Direction

This is the current Tesco-facing first experience block direction. It keeps the visible language problem-facing while using the platform line to carry technical context: AWS, SQL/PySpark, statistical modelling, monitoring, scale, and relevant modelling domains.

### Data Scientist

Customer Behaviour ML Platform - Exeter, UK | May 2025 - Present

AWS-hosted customer-behaviour ML platform using SQL/PySpark pipelines, statistical modelling, and monitoring across a 2.35B-row customer data surface to support churn, propensity, fraud detection, targeting, and business decisioning.

- Improved churn-risk identification by 18% in backtested evaluation, identifying customers likely to disengage before retention decision points through customer behaviour modelling.

- Concentrated 42% of likely high-fit customers in the top 20% scored customer segment, using propensity scoring to focus offers, messages, and interventions on customers most likely to benefit.

- Reduced low-fit marketing targeting by 11% while maintaining high-value customer coverage, using customer segmentation and model-led targeting to improve campaign and intervention efficiency.

- Improved customer communication relevance by segmenting customers around lifecycle stage, behaviour, and response likelihood, supporting more targeted retention, upgrade, and intervention messaging.

- Improved early detection of unusual customer/account behaviour by 18% in backtested evaluation, surfacing abnormal usage, activity, and transaction patterns through fraud-style behaviour modelling.

- Compared 3 customer decision strategies across 5 outcome measures, using repeatable SQL/PySpark scoring, validation, and monitoring workflows to support evidence-led rollout decisions.

## Supporting Experience Blocks

The supporting experience blocks should follow the same correction as the first platform block. They should not read like project reports. They should show the Tesco hiring manager that the candidate has repeated evidence of solving adjacent problems through behavioural modelling, complex data analysis, business insight, operational reporting, and stakeholder communication.

These blocks do not need to mirror Tesco as aggressively as the first experience block, but they should still reinforce the same role signals:

- behavioural modelling;
- customer/risk insight;
- complex data handling;
- business decision support;
- stakeholder communication;
- operational reporting discipline.

### Usage-Based Insurance Behaviour Modelling

University of Exeter - Exeter, UK | Aug 2024

Behavioural modelling project using smartphone sensor signals to improve insurance risk decisioning without relying on costly in-vehicle telematics.

- Improved insurance-risk decisioning by modelling transport behaviour and driver identity from smartphone sensor signals, showing how lower-cost behavioural data could support usage-based pricing.

- Increased behavioural classification reliability by combining transport-mode and driver-identification tasks into a shared deep learning workflow, reducing dependence on single-purpose models.

- Translated complex smartphone movement patterns into practical risk-assessment insight for stakeholders, connecting sensor behaviour to fairer driver-risk decisions.

### COVID-19 Business Recovery Trend Analysis

University of Exeter - Exeter, UK | Nov 2023

Business analytics project explaining disruption, recovery, and policy-linked activity changes across countries and business sectors.

- Identified business recovery patterns across 220 countries and 12 sectors, helping explain where activity returned, remained disrupted, or shifted from pre-crisis behaviour.

- Linked business activity changes with policy-response signals across 6 countries and 8 policy areas, showing how external decisions and events shaped recovery trends.

- Produced 3 evidence-led strategy recommendations from visual trend analysis, translating complex disruption patterns into business-facing decision support.

### Completions Engineer

South Western Technologies & Oilfield Services Ltd - Rivers, Nigeria | Jul 2021 - Aug 2022

Operations reporting and field-data coordination role supporting live rig decisions, handovers, HSE documentation, and completions execution.

- Improved live operational decision visibility by tracking completion progress, equipment sequence, tubing/casing tallies, depths, and daily rig activity.

- Reduced reporting ambiguity by reconciling 4 operational record types across field reports, HSE records, equipment checks, and daily updates before handover.

- Supported safer field execution by coordinating reporting, equipment readiness, and HSE requirements across completions, safety, and field operations teams.

## Recruiter Scan Test

Each bullet should pass the first-phrase test:

| Bullet opening | Does it show Tesco's problem? |
|---|---|
| Improved churn-risk identification | Yes: churn is named in the ad. |
| Concentrated likely target outcomes | Yes, but may need a stronger customer-targeting lead phrase in the final CV. |
| Reduced low-fit marketing targeting | Yes: marketing effectiveness and customer targeting are visible. |
| Improved customer communication relevance | Yes: personalising customer communications and customer experience are visible. |
| Improved early detection of unusual customer/account behaviour | Yes: fraud/unusual behaviour modelling is visible. |
| Compared customer decision strategies | Yes: decision-shaping is visible, but final wording should make the business decision impact clear. |

## Decision Log

| Decision | Reason |
|---|---|
| Do not use the old evidence-led formula as the bullet-writing method. | It makes the bullet read like a technical report and dilutes the employer problem. |
| Use the problem hierarchy as the bullet source. | Tesco's hiring problem must remain visible throughout the bullet. |
| Keep technical proof behind the bullet. | It is needed for interview defence, but it should not dominate limited CV real estate. |
| Use measured results only when they prove business/customer movement. | The metric should support the problem solved, not merely the model method. |
| Drop stock/demand planning from the first six bullets for now. | It is relevant but weaker than churn, propensity, marketing, communication, fraud, and decision-shaping for the current positioning. |
| Keep six bullets for the first experience block. | Six gives enough breadth without making the first block feel unfocused. |

## Operating Rule For Future Job Ads

For future role mapping:

1. Identify the employer's stated problem from the job ad.
2. Build the employer problem hierarchy from the ad's own language.
3. Build problem chains from Level 3 back to Level 1/0.
4. Select the chains that best represent the hiring manager's problem.
5. Turn chains into business-facing achievements.
6. Add measured results that prove the problem moved.
7. Add compressed method only after the business problem and result are clear.
8. Keep full technical proof as a defence layer, not the visible bullet formula.
