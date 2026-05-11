# X-First Role Mapping Methodology

This note records the corrected resume-positioning method for mapping job ads to the platform evidence tree.

## Why This Exists

The earlier mapping approach was useful for collecting evidence, but it was too method-led.

It often started from:

> what was built, what tools were used, what lifecycle stages were owned, what models were trained, what pipelines were managed

That created Z-heavy positioning. It proved capability, but it did not always make the employer's problem visible quickly enough.

A recruiter or hiring manager scanning a CV is not first asking:

> Did this person use PySpark, XGBoost, CI/CD, and production pipelines?

They are first asking:

> Can this person solve the problem I am hiring for?

The tools, duties, workflows, and methods matter because they explain how the problem was solved. They should not usually be the lead signal.

## Old Method

The old method tended to collapse the role into:

> Z -> Y -> X

or:

> Z -> X -> Y

Examples of Z-first posture:

> Built an end-to-end ML workflow...

> Used PySpark to process large customer datasets...

> Managed BAU model monitoring...

These are not wrong as evidence, but they start with the candidate's activity. On a fast scan, the reader sees tools and workstreams before they see the business/customer problem solved.

## What Was Wrong

The old approach made three things too easy:

1. Treating platform capabilities as achievements.
2. Treating metrics as proof without clearly stating the business problem they prove.
3. Treating any "by identifying..." phrase as Z, even when it was actually the business mechanism that gave X its context.

This produced bullets that could be technically strong but scan weakly, because the reader had to finish the whole sentence to infer the point.

## Corrected Method

The corrected method is:

> X first, but with X made specific before adding Y and Z.

That means we do not stop at vague X phrases such as:

> solved business problems

> improved customer experience

> generated insights

> improved products, processes, and performance

Those phrases are useful as umbrella positioning, but they are usually too broad for individual bullets.

## Four-Part Construction

For role mapping and bullet design, use four parts:

| Layer | Meaning |
|---|---|
| Concrete X | The specific customer or business outcome. |
| Business mechanism / target signal | The behaviour, condition, segment, timing, issue, or decision point that gives X business context. |
| Y | How well the outcome was solved, measured, qualified, or evidenced. |
| Z | The method, responsibility, tool, workflow, or duty used to create the outcome. |

The business mechanism is the important addition.

It sits between X and Z. It explains what exactly is happening in the business world, but it is not necessarily the final method used by the candidate.

## Distinguishing Business Mechanism From Z

Some phrases look like Z because they use "by".

Example:

> Reduce churn risk among renewal-stage customers by identifying usage drop-off, price sensitivity, service issues, and upgrade intent.

This contains:

| Layer | Content |
|---|---|
| Concrete X | Reduce churn risk among renewal-stage customers. |
| Business mechanism / target signal | Usage drop-off, price sensitivity, service issues, upgrade intent. |
| Y | Churn reduction, retention uplift, response uplift, earlier detection, precision/recall of churn-risk identification. |
| Z | Build a churn or propensity model; combine usage, billing, service, contract, and customer data; engineer behavioural features; validate and deploy scoring outputs. |

The target signals should not be discarded. They make the X specific. But they should not replace the actual Z duties.

## Approved Case Stories

These case stories are not claims about the current platform. They are approved structure examples showing the level of information a strong role-mapping answer should carry.

They show how to separate:

> Concrete X -> business mechanism / target signal -> Y proof -> Z method

### Case Story 1 - Renewal-Stage Churn

Original Level 3 scenario:

> Reduce churn risk among customers approaching contract renewal by identifying usage drops, price sensitivity, service issues, or upgrade intent before they leave.

Better split:

| Layer | Content |
|---|---|
| Concrete X | Reduce churn risk among customers approaching contract renewal. |
| Business mechanism / target signal | Usage drop-off, price sensitivity, service issues, upgrade intent, contract-end behaviour. |
| Y | Churn reduction, retention uplift, response uplift, earlier detection, recall/precision of churn-risk identification. |
| Z | Build a churn or propensity model; combine usage, billing, service, contract, and customer data; engineer behavioural features; validate the model; deploy scoring outputs. |

Clean bullet structure:

> Reduced churn risk among renewal-stage customers by X%, by building a propensity model across usage, billing, service, and contract data to identify usage drop-off, price sensitivity, service issues, and upgrade intent.

What this teaches:

- The X is not "built a propensity model".
- The X is reducing churn risk among renewal-stage customers.
- The business mechanism is the customer behaviour or condition that explains the churn risk.
- The Z is the actual duty or method used to solve it: modelling, data combination, feature engineering, validation, and scoring.

### Case Story 2 - Early-Life Churn

Original Level 3 scenario:

> Reduce early-life churn among new Tesco Mobile customers by detecting poor onboarding signals, low usage, failed setup patterns, or early dissatisfaction indicators.

Better split:

| Layer | Content |
|---|---|
| Concrete X | Reduce early-life churn among new customers. |
| Business mechanism / target signal | Poor onboarding signals, low usage, failed setup patterns, early dissatisfaction indicators. |
| Y | Reduction in early-life churn, earlier detection window, improved recall of at-risk new customers, increased successful onboarding rate. |
| Z | Analyse onboarding, usage, service, and account-activity data; engineer early-life behavioural features; build and test a churn-risk model. |

Clean bullet structure:

> Reduced early-life churn among new customers by X%, by analysing onboarding, usage, service, and account-activity data to build early-risk features and test a churn-risk model.

What this teaches:

- The X is not "analysed onboarding data".
- The X is reducing early-life churn among new customers.
- The business mechanism is the onboarding or early dissatisfaction signal that makes the churn problem specific.
- The Z is the analytical and modelling work used to detect, test, and operationalise the signal.

## Case Story Guideline

When creating a role-mapping answer, carry enough information to answer four questions:

1. What exact customer or business outcome is being improved?
2. What behaviour, condition, segment, timing, or decision point makes that outcome specific?
3. How could that improvement be measured or evidenced?
4. What duty, method, model, pipeline, analysis, or workflow creates the improvement?

If any one of these is missing, the bullet or positioning line will likely become vague, Z-led, or unsupported.

## Job-Ad X Hierarchy

Before mapping the platform, build the employer's X hierarchy:

| Level | Purpose |
|---|---|
| Level 0 | Umbrella company problem. |
| Level 1 | Main outcome facets. |
| Level 2 | Short business outcome examples or business areas that make Level 1 less vague while staying scan-friendly. |
| Level 3 | Specific role-context scenarios with business mechanisms / target signals. |

Level 2 should not be a repeat of Level 1 wording, but it also should not become long stakeholder concern sentences. It should use short, recognisable business outcome labels that land quickly on a fast scan.

Preferred Level 2 style:

> Reduce customer churn.

Less useful Level 2 style:

> Customers may leave before the business identifies the right retention signal or intervention point.

The second version contains useful thinking, but it is too long for Level 2 and starts to do Level 3's job. Level 3 is where the customer situation, timing, mechanism, and target signal should be unpacked.

Only after this hierarchy exists should the platform be mapped.

The mapping flow is:

> employer umbrella problem -> employer outcome facet -> employer business outcome example -> employer concrete scenario plus business mechanism -> platform equivalent concrete X plus platform mechanism -> Y proof -> Z method

## Bullet Construction Rule

A strong bullet should usually read as:

> specific customer/business problem -> business mechanism or target signal -> measured proof -> method used

Not:

> method used -> metric -> implied business problem

For example:

> Reduced churn risk among renewal-stage customers by 12% by modelling usage drop-off, price sensitivity, service issues, and upgrade intent across usage, billing, service, contract, and customer data.

This is not a final claim for the current platform. It is a structure example.

The structure is:

| Part | Example content |
|---|---|
| Concrete X | Reduced churn risk among renewal-stage customers. |
| Business mechanism / target signal | Usage drop-off, price sensitivity, service issues, upgrade intent. |
| Y | By 12%. |
| Z | By modelling signals across usage, billing, service, contract, and customer data. |

## How This Applies To The Platform Evidence Tree

The platform evidence tree remains the evidence bank. It stores:

- data sources;
- metrics;
- models;
- pipelines;
- monitoring;
- experiments;
- explainability;
- production workflow evidence.

But when writing outward-facing positioning, do not lead with the evidence bank.

First identify the employer's concrete X and business mechanism. Then choose the platform evidence that can credibly map to it.

The platform story should therefore be shaped as:

> employer problem first, platform evidence second

not:

> platform capability first, employer problem inferred later

## Practical Test

Before accepting a bullet, ask:

1. If the reader only sees the first 5 to 8 words, do they see an outcome or just an activity?
2. Is the X specific enough, or is it still a vague phrase such as "improved customer experience"?
3. Does the bullet name the business mechanism or target signal that makes the X real?
4. Is Y proving the outcome, not just decorating the sentence with a number?
5. Is Z drawn from the duties and methods the employer actually asked for?

If the answer is no, the bullet is probably still Z-led or too vague.

## Full Role-Mapping Pipeline

The Tesco Mobile resume rebuild exposed the full process more clearly than the earlier framework.

The resume problem was not that the platform lacked substance. The platform had strong substance: large-scale customer/account data, PySpark pipelines, XGBoost, SHAP, model monitoring, experimentation, validation, and production-shaped workflows.

The problem was that the resume was evidence-led instead of employer-problem-led.

It kept starting from:

> what was built, what tools were used, what models were trained, what pipelines were managed, what lifecycle stages were owned

That made the resume Z-first. On a fast scan, the recruiter could see technical activity before seeing the business/customer problem being solved.

The corrected pipeline is:

> job problem -> employer X hierarchy -> platform X hierarchy -> selected rich Xs -> Z responsibility fit -> Business Y plus technical proof -> raw substance bullets -> commercial translation -> final resume

### Step 1 - Define The Employer Problem

Read the job ad for the employer's problem, not just keywords.

Ask:

> What are they hiring someone to fix, improve, reduce, increase, support, or deliver?

For Tesco, the umbrella problem was:

> Use data science to solve real business problems and improve customer experiences.

This should be identified before collecting tools, duties, or keyword matches.

### Step 2 - Build The Employer X Hierarchy

Build the employer's problem tree before mapping the platform.

| Level | Purpose | Tesco example |
|---|---|---|
| Level 0 | Umbrella company problem. | Solve real business problems and improve customer experiences using data science. |
| Level 1 | Broad outcome facets. | Improve customer experience; improve business outcomes; shape decisions; improve products, processes, and performance; generate insight; support planning. |
| Level 2 | Short, scan-friendly business outcome areas. | Personalise customer communications; improve marketing effectiveness; optimise stock management; reduce churn; improve product decisions; shape customer and business strategy. |
| Level 3 | Concrete role-context scenarios plus business mechanisms. | Reduce churn among renewal-stage customers; personalise upgrade offers; improve campaign targeting; identify customers at risk of bill shock; compare customer strategies before rollout. |

Level 2 should stay short and business-facing. Level 3 carries the customer situation, timing, target signal, and business mechanism.

### Step 3 - Build The Platform X Hierarchy

Do not shrink the employer's problem down to the current platform too early.

The platform should be positioned upward into the employer's problem structure.

Usually:

- Level 0 should align closely with the employer's Level 0.
- Level 1 should also align closely with the employer's Level 1.
- Level 2 starts to specialise into platform-relevant business outcome areas.
- Level 3 becomes concrete platform scenarios with business mechanisms / target signals.

For Tesco, the platform hierarchy specialised into areas such as:

- early risk movement detection;
- account review prioritisation;
- unnecessary review and escalation reduction;
- segmented decision strategies;
- evidence-led strategy selection;
- explainable account prioritisation;
- review capacity planning;
- trusted recurring decision-support outputs.

### Step 4 - Select The Strongest Platform Xs

Before adding methods or metrics, choose the strongest 4 to 6 Xs.

Do not choose Xs only because the platform already has obvious evidence for them. Choose Xs because they best match the employer's problem, then build or position the evidence tree so the X can be defended.

Selection criteria:

| Criterion | Meaning |
|---|---|
| Direct employer fit | Does the X clearly answer the employer's main problem? |
| Specificity | Is the X concrete enough to avoid vague phrases like "improved insight"? |
| Business mechanism | Does the X have a clear behaviour, segment, timing, condition, or decision point? |
| Evidence-buildability / defensibility | Can the platform credibly carry this X with a defensible Z and Y? |
| Coverage | Across the selected Xs, do we cover the job's key responsibilities and assessment signals? |
| Scanability | Does the first phrase show a business/customer problem quickly? |
| Non-overlap | Do the Xs show different dimensions of value rather than repeating the same claim? |
| Interview defensibility | Can the platform story be explained cleanly if challenged? |

Evidence strength is not a limiter in the narrow sense. The better rule is:

> Pick the best Xs for the employer first, then position the platform evidence, Z method, and Y proof around them.

But do not fabricate claims that cannot be explained or demonstrated if challenged.

### Step 5 - Build Rich Xs

Selected Xs can be made richer by folding in supporting angles.

For example:

| Main X | Supporting angles that can enrich it |
|---|---|
| Prioritise account reviews toward cases most likely to need action. | Review-capacity planning; segmentation; explainability; expected case load. |
| Select decision strategies using evidence before adoption. | Threshold comparison; champion/challenger testing; false-positive control; operational load. |

Supporting Xs are not extra bullets by default. They are colour, context, or supporting detail that can be folded into the main X so the bullet signals more of the employer's Level 1 problem.

### Step 6 - Attach Z After X Is Clear

Z is added after the X and business mechanism are clear.

Z should be checked against the job responsibilities, not just against the platform's technical inventory.

For a data science role, the Z coverage check may include:

- build, validate, optimise, and manage models;
- manage data pipelines;
- own key lifecycle stages;
- production or production-shaped deployment;
- statistical methods;
- SQL, Python, PySpark, databases, cloud;
- testing, CI/CD, OOP, unit tests;
- documentation, security, monitoring;
- stakeholder communication and rationale.

This prevents the final bullet from having a good X but weak role-duty coverage.

### Step 7 - Separate Business Y From Technical Proof

This was a major correction.

Y should prove the X changed. It should not merely prove the model or method was technically strong.

Use two separate proof layers:

| Layer | Purpose |
|---|---|
| Business Y | Stakeholder-facing proof that the business/customer problem improved. |
| Technical proof | Evidence that the method/model/evaluation was valid. |

Example:

| X | Business Y | Technical proof |
|---|---|---|
| Improve early customer-risk detection. | Improved early-risk identification by 18%, reducing missed pre-escalation cases. | XGBoost improved recall by 18% over Logistic Regression using time-based validation. |
| Focus account review capacity. | Concentrated 42% of future-risk cases into the top 20% priority group. | XGBoost scoring ranked accounts by risk-movement probability; top-score band analysis showed risk concentration. |
| Reduce unnecessary reviews/escalations. | Reduced low-value review volume by 11% while maintaining risk coverage. | Compared rule thresholds against model-led scoring and champion/challenger threshold tests. |
| Select decision strategies before rollout. | Selected a lower-review-load strategy while preserving risk coverage and controlling false positives. | Tested 3 threshold strategies across 5 outcome measures. |

Metrics such as recall, AUC, model lift, number of thresholds, or number of features can be useful, but they are often technical proof unless translated into stakeholder-facing problem movement.

### Step 8 - Create Raw Substance Bullets

Before writing final resume bullets, combine:

> X + business mechanism + Business Y + technical proof + Z

Do not shorten yet.

This produces long, report-like bullets, but that is useful because it preserves the evidence layer.

The raw substance bullet is not the final CV bullet. It is the evidence compression input.

### Step 9 - Translate From Report Language To Commercial CV Language

The raw version will often still sound like a platform report.

The final translation pass asks:

> What should the recruiter see first?

Usually the answer is not the most technically precise Level 3 X. It is the most commercially legible version of the X, often closer to Level 1 or Level 2 wording, with the Level 3 mechanism retained as proof.

Raw/report-like:

> Identified customers/accounts likely to move into higher risk before escalation using risk-band momentum, transaction volatility, activity drop-off, rising exposure/utilisation, repeated near-threshold behaviour, and recency/frequency changes.

Commercial-facing:

> Improved early customer-risk detection by 18%, identifying more pre-escalation risk cases through customer-behaviour modelling across customer, account, transaction, risk, decision, and outcome data.

The second version works better because the first thing the recruiter sees is:

> improved early customer-risk detection

not:

> model features, target signals, data plumbing, or platform mechanics

### Step 10 - Final Resume Compression

The final bullet should usually follow:

> business/customer outcome -> measured proof -> compressed method

For example:

> Improved early-risk detection by 18% in backtested evaluation, surfacing more pre-escalation risk cases through customer-behaviour modelling and XGBoost-based scoring.

This is different from a generic commercial claim because it still carries the platform substance: risk detection, backtested evaluation, pre-escalation cases, behaviour modelling, and XGBoost scoring.

## Tesco Reference Transformation

The Tesco first experience block became the reference example for this method.

The raw platform evidence included:

- customer/account/transaction/risk/decision/outcome data;
- 2.35B-row credit-risk surface;
- PySpark/SQL feature pipelines;
- XGBoost and Logistic Regression;
- SHAP behavioural drivers;
- threshold testing;
- champion/challenger evaluation;
- AWS-hosted scoring workflows;
- drift checks, validation tests, model monitoring, and documentation.

The final commercial-facing bullets led with business/customer outcomes:

- improved early-risk detection;
- focused operational review capacity;
- reduced low-value reviews;
- improved evidence-led strategy selection;
- maintained recurring decision-support workflows.

This is the model:

> The platform evidence remains underneath, but the visible resume line starts with the employer-relevant problem movement.

## Warning Signs

A bullet is drifting back into weak positioning when it starts with activity and asks the reader to infer the outcome.

Common warning starts:

> Built...

> Used...

> Managed...

> Developed...

> Implemented...

These are not banned words. Sometimes they are appropriate, especially when the employer directly values construction or ownership. But they often signal Z-led writing.

Stronger starts often include:

> Improved...

> Reduced...

> Increased...

> Identified...

> Focused...

> Prevented...

> Selected...

> Delivered...

> Accelerated...

> Concentrated...

But the verb alone is not enough.

Weak:

> Improved customer insight.

Stronger:

> Improved early customer-risk detection by 18%.

Stronger still:

> Improved early customer-risk detection by 18%, identifying more pre-escalation cases through customer-behaviour modelling.

## Simplest Rule

Do not lead with what was done.

Lead with what problem changed.

Then use the platform evidence to prove and explain it.

The shortest version of the method is:

> specific business/customer problem solved -> business mechanism -> measured impact -> technical method
