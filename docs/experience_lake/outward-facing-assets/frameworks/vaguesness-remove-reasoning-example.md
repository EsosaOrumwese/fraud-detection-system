# Vagueness Removal: Reasoning Examples

This note captures the working reasoning used to turn polished but generic CV wording into evidence-led, recruiter-readable bullets. The examples are drawn from the Monzo and Trustpilot tailoring work.

The core principle is:

> Do not start by asking, "How can this bullet sound better?"
> Start by asking, "What risk is the recruiter trying to remove before they invite this person to interview?"

A recruiter is not reading the CV like a portfolio reviewer. They are scanning for evidence that the candidate can do this specific job, with low hiring risk, quickly enough that they can justify moving the candidate forward.

---

# Methodology

## 1. Identify what the job is really buying

Ignore the job title for a moment.

For Monzo, the title says:

```text
Data Scientist
```

But the job ad is really buying someone who can:

```text
help product teams make better decisions about users, features, engagement, experiments and profitability
```

That is why the CV should be treated less like a generic modelling CV and more like a product analytics, experimentation and commercial decision CV.

The job ad gives the clue. It says data scientists are embedded in cross-functional squads with engineers, designers, marketers and product managers. It also says they guide product teams on measuring what matters, run or help run A/B experiments, understand user profitability, and liaise with engineers on data collection.

So when assessing a bullet, ask:

```text
Does this bullet make the candidate look like someone who can help a product squad make a better decision?
```

Not:

```text
Does this bullet sound technically impressive?
```

That is the first methodological shift.

## 2. Separate evidence from polish

Many CV rewrites make the language smoother. This method does the opposite.

Ask:

```text
Is there enough concrete evidence for a recruiter to believe this claim?
```

For example, this is not bad:

```text
Built a transaction-value and high-benefit customer table, comparing customer segments by response rate, score band and share of transaction value.
```

But from a recruiter perspective, the question is:

```text
So what decision did this help with?
```

For Monzo, the commercial meaning is more important than the table itself. A stronger direction is:

```text
Built a transaction-value table comparing customer segments by response rate, score band and share of transaction value, separating high-response segments from segments that also carried higher commercial value.
```

That tells the recruiter:

```text
This person understands that response rate alone is not enough; value matters.
```

That maps to Monzo's language about putting numbers into business perspective, user profitability and product impact.

## 3. Look for the recruiter proof chain

For each bullet, aim for a chain like this:

```text
business/product question -> data used -> method/tool -> output -> decision/review/use -> measurable result
```

Not every bullet needs all six parts, but strong bullets usually contain at least four.

Strong example:

```text
Ran an A/B test across 120,000 customers comparing the existing customer-selection rule with a top-20% score-band selection, increasing response rate from 8.4% to 10.1% while keeping low-yield inclusion below 15%.
```

That gives the recruiter:

```text
scale: 120,000 customers
method: A/B test
comparison: existing rule vs top-20% score-band selection
result: 8.4% to 10.1%
guardrail: low-yield inclusion below 15%
```

A weaker bullet often stops at:

```text
I built X.
```

A stronger bullet says:

```text
I built X to help decide Y, using Z, with result W.
```

## 4. Classify job-ad requirements into must-prove signals

For Monzo, the hidden checklist is:

| Job-ad signal | Recruiter wants to believe | CV evidence needed |
|---|---|---|
| Product/user behaviour analysis | The candidate can understand how users interact with products. | Activity frequency, repeat usage, response rate, customer segments. |
| A/B experiments | The candidate can design or interpret experiments. | Test size, control/treatment, metric movement, guardrails. |
| Commercial thinking | The candidate can connect metrics to value. | Transaction value, profitability proxy, high-benefit customers. |
| Looker/self-serve analytics | The candidate can build reusable analytics surfaces. | Looker reports, recurring reporting periods, dashboard refresh reliability. |
| SQL/Python | The candidate can handle the data directly. | BigQuery SQL, Python, queries, validation checks. |
| Cross-functional work | The candidate can support product/engineering/finance-like stakeholders. | Review tables, recommendation memos, source-table quality, decision support. |
| See beyond the numbers | The candidate can explain why a metric moved. | Variance analysis, root-cause tables, segment-mix shift, data-quality issues. |

Then ask every bullet:

```text
Which of these boxes does this bullet prove?
```

If a bullet does not prove a box, rewrite it, merge it, move it lower, or remove it.

## 5. Look for human believability, not just ATS matching

A bullet can be keyword-rich and still feel artificial.

Weak pattern:

```text
Built X to provide insights into Y and support stakeholder decision-making.
```

That sounds like filler because the recruiter cannot picture the work.

Stronger pattern:

```text
Investigated a 19% response-rate movement in BigQuery, separating the change into activity-volume drop, segment-mix shift, response-pattern change and source-table quality issues before the metric was used in the next segment review.
```

That feels more human because it has a specific event: a metric moved, the candidate investigated it, separated the drivers, and prevented overreaction to the headline number.

The key is to move from:

```text
Used BigQuery variance queries...
```

to:

```text
Investigated a 19% response-rate movement...
```

A recruiter does not hire a query writer. They hire someone who can explain business or product movement.

## 6. Check whether the bullet is centred on the artefact or the decision

Artefact-centred:

```text
Built a ranked customer segment table capturing 42% of high-response customers in the top 20% score band.
```

Decision-centred:

```text
Created a targeting-threshold review table showing that the top 20% score band captured 42% of high-response customers, giving reviewers a ranked customer list for deciding where to tighten or widen selection.
```

The first says:

```text
I built a table.
```

The second says:

```text
I helped decide how selection should change.
```

For data roles, the artefact is rarely the final value. The value is usually a product decision, targeting decision, metric explanation, risk reduction, dashboard reuse, stakeholder recommendation, data-quality issue prevented, or experiment interpreted correctly.

## 7. Look for same-job, same-environment evidence

A recruiter is subconsciously asking:

```text
Has this person worked in conditions similar enough to ours?
```

For Monzo, those conditions are:

```text
large customer/product data
fast decision-making
self-serve Looker culture
cross-functional product squads
experiments
commercial/product trade-offs
engineers involved in data collection
user behaviour and engagement
```

The language should make those similarities obvious.

For example:

```text
dashboard
```

can become:

```text
recurring Looker customer-behaviour report used before customer-selection reviews
```

And:

```text
variance queries
```

can become:

```text
metric movement investigation
```

This is not cosmetic. It aligns the evidence to the recruiter's mental model of the role.

## 8. Remove or reduce abstract words unless backed by a work object

Words to distrust:

```text
insights
stakeholder-ready
strategic
impactful
scalable
robust
actionable
decision support
business value
commercial impact
data-driven
optimised
enabled
```

These words are not banned, but they need a named object behind them.

Weak:

```text
Delivered actionable insights to support product strategy.
```

Strong:

```text
Investigated a 19% response-rate movement in BigQuery, separating the change into activity-volume drop, segment-mix shift, response-pattern change and source-table quality issues.
```

The strong version proves insight without saying insight.

## 9. Make the first 3-4 bullets carry the interview case

Recruiters do not give equal attention to every bullet.

For a tailored CV, the first 3-4 bullets under the main experience should answer:

```text
Why should this person be interviewed for this job?
```

For Monzo, the first half of the main experience should show:

```text
1. behavioural data layer
2. Looker/self-serve reporting
3. A/B experiment
4. metric movement / variance investigation
5. customer value / profitability proxy
```

The validation checks are strong, but they can sit lower because they support reliability rather than headline fit.

## 10. Compare against strong profiles by event density

Strong profiles feel convincing because they have event density.

They include:

```text
a specific asset
a specific failure/problem
a specific action
a measurable result
a consequence avoided
```

For a data CV, the equivalent anchors are:

```text
120,000-customer A/B test
2.35B-row customer behaviour dataset
19% response-rate movement
42% high-response capture in top 20% score band
15 validation checks
38% reporting-error reduction
98% dashboard refresh success
```

Write around those anchors rather than around generic phrases.

## Recruiter-perspective checklist for Monzo

If screening the Monzo CV, ask:

```text
1. Can he work with product/customer behaviour data?
2. Can he run or interpret experiments?
3. Can he explain metric movement?
4. Can he think commercially, not just technically?
5. Can he build reusable analytics, not just one-off notebooks?
6. Can he work with engineers/product teams?
7. Does he sound credible or too perfectly tailored?
```

## Methodology in one sentence

For any CV and job ad, translate the job ad into a risk checklist, then rewrite each bullet so it proves one of those risks is low using concrete work objects, tools, scale, decisions, users and outcomes.

For Monzo, the target proof is:

```text
I can use SQL/Python/Looker to understand user behaviour, run experiments, explain product metric movement, connect metrics to customer value, and give product teams evidence they can use.
```

---

# Work Event Texture

Work event texture means the small details that make a bullet feel like it came from a real piece of work, not from a polished summary of responsibilities.

Low texture:

```text
Built a dashboard tracking customer behaviour metrics.
```

Higher texture:

```text
Built a Looker customer-behaviour report across 12 reporting periods so reviewers could monitor activity frequency, repeat usage and response-rate movement without rerunning BigQuery queries.
```

The second version feels more real because it has:

```text
a recurring work situation: 12 reporting periods
a user/workflow: reviewers monitoring movement
specific metrics: activity frequency, repeat usage, response rate
a practical reason: avoiding repeated BigQuery queries
```

## Another way to think about it

A normal CV bullet answers:

```text
What did you produce?
```

A textured CV bullet answers:

```text
What was happening, what did you build/analyse, and how did that change the review or decision?
```

Low texture:

```text
Built a transaction-value and high-benefit customer table, comparing customer segments by response rate, score band and share of transaction value.
```

Higher texture:

```text
Built a transaction-value table comparing customer segments by response rate, score band and share of transaction value, separating high-response segments from segments that also carried higher commercial value.
```

This shows the analytical judgement:

```text
Response rate alone was not enough; I checked whether the responding customers were also commercially valuable.
```

## Ingredients of work event texture

### 1. The trigger

What caused the work?

```text
A 19% response-rate movement.
A dashboard refresh problem.
A targeting-threshold review.
A recurring segment review.
A suspected fraud case.
```

### 2. The messy distinction

What had to be separated, compared or diagnosed?

```text
Activity-volume drop vs segment-mix shift.
High-response customers vs commercially valuable customers.
Existing rule vs top-20% score-band selection.
Repeat-response customers vs genuinely recoverable customers.
```

### 3. The user of the work

Who needed it?

```text
Product reviewers.
Fraud reviewers.
Data science reviewers.
Engineering reviewers.
Managers.
Non-technical stakeholders.
```

### 4. The decision or review it supported

```text
Whether to tighten or widen a threshold.
Whether a score table was stable enough to release.
Which customer segment to prioritise.
Whether a metric movement was real or data-quality-driven.
Whether a fraud rule should be adopted.
```

### 5. The consequence

```text
Reduced reporting errors.
Improved response rate.
Reduced review time.
Avoided one-off SQL reruns.
Created a single evidence file.
Focused the review on the real drivers.
```

## Strong textured example

```text
Ran an A/B test across 120,000 customers comparing the existing customer-selection rule with a top-20% score-band selection, increasing response rate from 8.4% to 10.1% while keeping low-yield inclusion below 15%.
```

That has texture because the event is visible:

```text
There was an existing selection rule.
An alternative was tested.
Response-rate uplift was measured.
A guardrail was kept on low-yield inclusion.
```

## Why weaker bullets often fail

This bullet has tools and objects, but not enough texture:

```text
Built lifecycle-response tables using customer status, activity level and response-history windows, separating customer groups before segmentation and score-band reporting.
```

A stronger version shows the mistake prevented:

```text
Built lifecycle-response tables separating active, dormant, repeat-response and low-response customers before segmentation, preventing score-band reports from mixing customers with different behaviour histories.
```

In plain terms:

```text
Work event texture = evidence that the bullet came from an actual analytical situation.
```

It is the difference between:

```text
I built useful analytics assets.
```

and:

```text
A metric moved, a review was needed, customer groups were being mixed, a threshold decision had to be made, and I built the analysis that clarified it.
```

---

# Excess Numbers And Number Discipline

Some numbers help. Some numbers do harm.

The issue is not that numbers are bad. The issue is number overload without hierarchy.

For a Monzo-style section, the current number set can become dense:

```text
2.35B rows
12 reporting periods
120,000 customers
top-20% score band
8.4%
10.1%
15% guardrail
42%
top 20% again
19% movement
15 validation checks
38% reduction
98% refresh success
```

That is a lot of figures in seven bullets. Too many numbers can make the reader stop processing the story.

## Corrected view

Do not remove numbers. Ration them.

Use numbers when they prove one of four things:

```text
1. Scale
2. Experiment result
3. Trade-off / guardrail
4. Operational improvement
```

Cut or soften numbers that only decorate the bullet.

## Numbers to keep for Monzo

Keep:

```text
2.35B rows
120,000-customer A/B test
8.4% to 10.1%
15% low-yield guardrail
19% response-rate movement
38% reporting-error reduction or 98% refresh success
```

Consider cutting or softening:

```text
12 reporting periods
15 validation checks
42% in top 20% score band, if it overloads the same score-band story
```

## Cleaner Monzo example

```text
- Built BigQuery user-behaviour tables across 2.35B customer activity, transaction and response-history records, joining the data needed to compare activity frequency, repeat usage, response rate and transaction value by score band before customer-selection reviews.
- Developed a recurring Looker customer-behaviour report showing response-rate movement, repeat usage and high-benefit customer concentration across score bands, reducing the need for repeated BigQuery extracts during segment reviews.
- Ran a 120,000-customer A/B test before changing customer-selection logic; the top-score-band treatment increased response rate from 8.4% to 10.1% while keeping low-yield inclusion below the agreed guardrail.
- Created a targeting-threshold review table showing where high-response customers concentrated by score band, narrowing the next selection-change discussion to score cutoffs rather than broad customer segments.
- Investigated a 19% period-on-period response-rate movement in BigQuery, separating activity-volume drop, segment-mix shift, response-pattern change and source-table quality issues before the metric was used in the next review.
- Built a transaction-value comparison showing which high-response segments also carried stronger transaction value, so the proposed selection change was not based on response rate alone.
- Added validation checks across BigQuery source tables and Looker report inputs, reducing behaviour-reporting errors by 38% before recurring customer-selection reviews.
```

This version still has numbers, but fewer of them. The retained numbers do real work.

Final number rule:

```text
Keep 4-6 major numbers in the main role. Remove or soften the rest.
```

After that, the CV needs more decision context, not more percentages.

---

# Trustpilot Example: Top Section Tightening

## Recruiter screen

For Trustpilot, the recruiter screen is:

```text
Can this person use SQL, BigQuery and Looker to identify fraud trends, translate behaviour analysis into detection rules, prepare investigation evidence, work with data science/engineering, and explain findings clearly?
```

The ad asks for fraud trend analysis, SQL/BigQuery/Looker, rule formulation, misuse investigations, data science/engineering collaboration, and communication of analysis/investigation results.

## Headline

Current:

```text
Fraud Detection Analyst | SQL, BigQuery & Looker | Behavioural Pattern Detection | Detection Rules
```

Issue:

```text
Behavioural Pattern Detection is relevant, but abstract. It sounds like a keyword cluster rather than a real work lane.
```

Stronger:

```text
Fraud Detection Analyst | SQL, BigQuery & Looker | Fraud Trends, Detection Rules & Case Evidence
```

Why:

```text
It gives Trustpilot three job signals immediately: fraud trends, rules and investigation evidence.
```

## Professional summary

Current:

```text
Fraud-focused Data Analyst with experience using SQL, Google BigQuery and Google Looker to detect suspicious behaviour across large activity datasets. Built fraud trend queries, Looker account-behaviour dashboards, risk indicators and investigation case packs across a 2.35B-row activity surface, translating fraud analysis into clear reports for fraud, data science and engineering stakeholders.
```

Issue:

```text
Fraud-focused Data Analyst, suspicious behaviour across large activity datasets, and translating fraud analysis into clear reports are relevant but slightly broad.
```

Stronger:

```text
Fraud Detection Analyst using SQL, BigQuery and Looker to analyse account, usage and transaction behaviour for fraud-risk review. Built BigQuery fraud-trend queries, Looker risk dashboards, detection-rule recommendations and case evidence packs across a 2.35B-row activity surface. Prepared rule rationale memos linking behavioural evidence, validation results and investigation findings for fraud, data science and engineering review.
```

Why:

```text
account, usage and transaction behaviour is more concrete than suspicious behaviour
fraud-risk review is clearer than detect suspicious behaviour
detection-rule recommendations is safer than claiming fully deployed rules
case evidence packs is a tangible work object
fraud, data science and engineering review maps to the role without pretending the candidate worked at Trustpilot
```

## First experience title and context

Current:

```text
Data Scientist
Behavioural Risk Analytics Platform - Exeter, UK | May 2025 - Present
SQL, BigQuery, Looker and Python platform for analysing account, usage and transaction behaviour, producing fraud-risk indicators, detection-rule recommendations, dashboards and case review packs across a 2.35B-row activity surface.
```

Stronger while preserving structure:

```text
Data Scientist
Fraud & Behavioural Risk Analytics Platform - Exeter, UK | May 2025 - Present
Built a SQL, BigQuery, Looker and Python analytics platform for reviewing suspicious account, usage and transaction behaviour across a 2.35B-row activity surface. Produced fraud-risk indicators, Looker dashboards, detection-rule recommendations, case evidence packs and rule rationale memos for fraud, data science and engineering review.
```

Avoid overclaiming:

```text
protected consumers
stopped fraud
worked on escalated legal/media cases
partnered with engineering teams
deployed production fraud rules
owned fraud investigations
```

Use what the evidence supports:

```text
SQL/BigQuery/Looker fraud trend work
account, usage and transaction behaviour analysis
2.35B-row activity surface
fraud-risk indicators
Looker dashboards
detection-rule recommendations
case evidence packs
rule rationale memos
fraud/data science/engineering review
```

---

# Trustpilot Example: Main Platform Bullet Workflow

Use 5 bullets rather than 6.

The old six bullets were relevant but too inventory-like:

```text
queries
dashboards
rules
case packs
tables
memos
```

Trustpilot needs a workflow:

```text
spot fraud patterns -> turn patterns into rule recommendations -> prepare case evidence -> keep the fraud data/reporting layer usable -> explain findings to fraud/data/engineering stakeholders
```

Recommended bullet set:

```text
- Analysed suspicious account, usage and transaction behaviour in BigQuery across a 2.35B-row activity surface, turning recurring fraud-pattern checks into reviewable risk indicators for fraud trend analysis.
- Built Looker fraud-risk dashboards from BigQuery risk tables, giving reviewers a recurring view of abnormal account, usage and transaction patterns without relying only on one-off SQL extracts.
- Converted high-signal behaviour patterns into six detection-rule recommendations, validating them against the existing rule-trigger baseline and improving known-risk case capture by 27%.
- Produced 38 fraud case evidence packs using SQL case-detail queries, high-risk account profiles and suspicious-behaviour timelines for suspected misuse review.
- Improved the BigQuery and Looker reporting layer behind fraud-risk reviews, cutting dashboard refresh time by 34% and preparing rule rationale memos for fraud, data science and engineering review.
```

## Why these are stronger

### Fraud trend analysis bullet

The weaker version starts with:

```text
Built SQL and BigQuery fraud trend queries...
```

Trustpilot is not hiring a query builder. They are hiring someone who can identify fraud trends using SQL, BigQuery and Looker.

The stronger bullet starts with:

```text
Analysed suspicious account, usage and transaction behaviour...
```

That puts the fraud work first, then the tool and scale.

### Looker dashboard bullet

Avoid:

```text
abnormal platform activity
```

Use:

```text
abnormal account, usage and transaction patterns
```

That is more concrete and grounded.

### Detection-rule bullet

Use:

```text
Converted high-signal behaviour patterns into six detection-rule recommendations...
```

That shows the analytical movement:

```text
behaviour pattern -> rule recommendation -> validation -> case-capture improvement
```

### Case evidence bullet

Use `case evidence packs`, not `case review packs`.

Safer version:

```text
Produced 38 fraud case evidence packs using SQL case-detail queries, high-risk account profiles and suspicious-behaviour timelines for suspected misuse review.
```

Use this instead of:

```text
one review file per suspected misuse case
```

unless the packs were genuinely structured that way.

### Reporting layer and stakeholder communication bullet

Merge maintenance and memos into one bullet:

```text
Improved the BigQuery and Looker reporting layer behind fraud-risk reviews, cutting dashboard refresh time by 34% and preparing rule rationale memos for fraud, data science and engineering review.
```

This supports two requirements at once:

```text
working with engineering/data science to improve tools/databases
presenting analysis/investigation findings to stakeholders
```

---

# Trustpilot Example: Supporting Experiences

The supporting experiences should support the Trustpilot application without pretending they are fraud roles.

Their purpose is to prove adjacent Trustpilot signals:

```text
I can analyse behaviour data, find patterns, test reliability, explain abnormal movement, prepare clear reports, and handle messy operational data.
```

## Data Scientist - University of Exeter

Use:

```text
Data Scientist
University of Exeter - Exeter, UK | Jan 2024 - Aug 2024
Python modelling project using smartphone sensor signals to classify movement and identity patterns, compare model performance against a baseline, and document reliability limits across trips, users and transport modes.

- Trained deep-learning models on accelerometer, gyroscope and trip-signal windows to classify transport mode and driver identity from behavioural sensor data.
- Improved behavioural classification accuracy by 7 percentage points versus a single-task CNN baseline, using a shared modelling workflow for movement-pattern and identity recognition tasks.
- Tested model reliability across 1,200 trips, 60 users and 5 transport modes, documenting misclassification patterns linked to trip type, user variation and sensor-signal quality.
```

Why:

```text
Remove forced fraud-adjacent language such as translating behavioural outputs into risk indicators unless that actually happened.
Keep behavioural data, classification, baseline comparison, robustness testing and failure-case documentation.
```

## Business Analyst - University of Exeter

Use:

```text
Business Analyst
University of Exeter - Exeter, UK | Sep 2023 - Nov 2023
Trend-analysis project using country-sector activity and policy-response datasets to compare movements against pre-crisis baselines, separate abnormal patterns, and explain likely drivers.

- Built a country-sector trend analysis across 220 countries and 12 sectors, separating rebound, persistent disruption and structural-shift patterns from pre-crisis baselines.
- Linked abnormal activity movements to 8 policy-response areas across 6 countries, showing where restrictions, support measures and reopening signals aligned with recovery-pattern changes.
- Produced a visual trend report with 3 recommendations, using country-sector charts and policy-driver tables to summarise which sectors rebounded, remained disrupted or structurally shifted.
```

Why:

```text
This proves abnormal pattern investigation and driver explanation without pretending the domain was fraud.
```

## Data Analyst - South Western Technologies

Use:

```text
Data Analyst
South Western Technologies & Oilfield Services Ltd - Rivers, Nigeria | Jul 2021 - Aug 2022
Operations data role using Excel, VBA and Power BI to reconcile field records, flag reporting exceptions, and prepare manager-facing operational reports.

- Built an Excel reconciliation workbook for field reports, HSE logs, equipment checks and daily completions updates, reducing incomplete or conflicting handover entries by 32% before supervisor review.
- Created a VBA exception-flagging macro for missing, duplicated and conflicting operational records, cutting report review time from 45 to 25 minutes.
- Built a Power BI operational dashboard across 12 completions jobs and 140 rig days, tracking job progress, equipment readiness, documentation gaps and review status before manager review.
```

Why:

```text
This supports data-quality checking, exception flagging, reporting discipline, operational review workflows and non-technical communication.
Do not force fraud language into this block.
```

---

# Trustpilot Example: Technical Skills

The skills section should foreground:

```text
SQL
BigQuery
Looker
fraud trend analysis
detection-rule recommendations
investigation evidence
reporting
```

Avoid padded terms unless clearly backed:

```text
anomaly thresholds
risk indicators without fraud-risk context
lift analysis
calibration checks
BigQuery fraud tables if the tables are not literally named that
```

Recommended lean version:

```text
TECHNICAL SKILLS

SQL & Data: SQL, Google BigQuery, SQL views, BigQuery risk tables
Looker & Reporting: Google Looker, fraud-risk dashboards, account-behaviour reports
Fraud Detection: fraud trend analysis, detection-rule recommendations, rule-trigger baselines, fraud-risk indicators
Investigation Evidence: SQL case-detail queries, high-risk account profiles, suspicious-behaviour timelines, case evidence packs
Python: Python, Pandas, NumPy, baseline comparison, model-output review
```

Why:

```text
Fraud Analytics -> Fraud Detection
detection rules -> detection-rule recommendations
anomaly thresholds -> rule-trigger baselines
Investigation Analysis -> Investigation Evidence
lift analysis / calibration checks -> rule validation, baseline comparison, model-output review
```
