# Tesco Mobile Data Scientist - Evidence-Led Resume Workbench

This workbench is reserved for rebuilding the Tesco Mobile Data Scientist resume materials using:

`docs\experience_lake\outward-facing-assets\frameworks\evidence-led-resume-positioning-framework.md`

## Baseline Read From ChatGPT

Yes -- I've read the Tesco Mobile Data Scientist ad.

My read is: **this is not just a modelling role**. It is a **hands-on customer data science + production ML workflow role**. Tesco wants someone who can solve customer/business problems, but also build, validate, deploy, test, document and manage the data science lifecycle. The ad explicitly combines customer experience, marketing effectiveness, stock management and churn with models, pipelines, production deployment, testing, CI/CD, documentation, SQL, Python, PySpark and stakeholder communication.

## 1. The role's real hiring problem

The job is asking:

> Can this person use customer data and ML to improve Tesco Mobile business decisions, while owning enough of the technical lifecycle to be useful in a real product/data science team?

So our CV should **not** position you as only:

```text
Data Scientist who builds ML models
```

It should position you closer to:

```text
Customer-focused Data Scientist who builds, validates and operationalises SQL/PySpark ML workflows for churn, propensity, fraud/anomaly, targeting and decision support.
```

That is the centre of gravity.

## 2. The three recruiter screens

### Business screen

The business problems are:

```text
customer experience
personalised customer communications
marketing effectiveness
stock management
customer churn
business decision-making
```

For your CV, the strongest matches are likely:

```text
customer behaviour modelling
churn / retention
propensity / targeting
fraud or anomaly detection
segmentation
stakeholder decision support
```

I would **not** force stock management unless we have evidence. It is in the ad, but your stronger proof seems to sit around customer behaviour, churn, propensity, fraud/anomaly and targeting.

### Technical screen

The technical requirements are heavy:

```text
SQL
Python
PySpark
models and pipelines
production workflows
testing
CI/CD
documentation
security
databases
multiple data sources
statistical principles
code optimisation
cloud technologies
```

This means at least one or two bullets must be explicitly technical. We cannot hide all the pipeline/model lifecycle evidence in the context line.

### Working-style screen

They care about:

```text
curiosity
collaboration
hypothesis-driven analysis
clear non-technical explanation
ownership
constructive challenge
product squads
customer-focused thinking
```

So the CV needs bullets that show you did not just build models -- you **translated outputs into decisions**, compared options, explained trade-offs, and made model results usable.

## 3. The proof buckets for this job

For this Tesco ad, I would use these proof buckets:

| Proof bucket | What the CV must prove |
|---|---|
| Customer data / scale | You can work with large customer datasets and customer behaviour signals |
| Churn / retention | You can model or analyse churn-risk problems |
| Propensity / targeting | You can improve campaign or marketing prioritisation |
| Fraud / anomaly | You have adjacent fraud, unusual behaviour or risk modelling evidence |
| Pipelines / production | You can build repeatable SQL/PySpark workflows, not just notebooks |
| Validation / statistics | You can measure model quality and defend outputs |
| Stakeholder decisioning | You can turn analysis into business recommendations |
| Communication / ownership | You can explain rationale and own decisions |

That is the set of "bullet jobs" we should aim to cover.

## 4. What the main experience block probably needs to prove

For your **Customer Behaviour ML Platform**, I would design the bullet portfolio like this:

```text
1. SQL/PySpark customer-data pipeline ownership
2. Churn-risk / retention modelling
3. Propensity / campaign targeting
4. Fraud-risk or anomaly feature evidence
5. Validation / monitoring / metric discipline
6. Stakeholder decision support
```

This would align tightly with the ad without making the CV sound like it was artificially rewritten as Tesco Mobile.

## 5. The positioning direction

For the Tesco version, the strongest headline direction is probably:

```text
Data Scientist | Customer Analytics & ML | Churn, Propensity, Fraud & SQL/PySpark
```

Or slightly more business-facing:

```text
Data Scientist | Customer Behaviour ML | Churn, Propensity, Fraud & Marketing Effectiveness
```

The professional summary should then sell the fit:

```text
Data Scientist with experience building customer-behaviour ML workflows across large-scale SQL/PySpark datasets, including churn, propensity, anomaly detection, segmentation and decision-support use cases. Strong fit for customer-focused roles requiring model development, validation, pipeline ownership and clear translation of complex analysis into business recommendations.
```

That follows the framework: headline sells the category, summary sells the fit, experience context sets the scene, and bullets prove the claims.

## 6. Main warning

The danger with this Tesco ad is over-tailoring.

We should use Tesco's language for the **problem categories**:

```text
customer behaviour
churn
propensity
marketing effectiveness
customer experience
production workflows
stakeholder decisions
```

But we should use your real evidence for the **proof**:

```text
2.35B-row surface
SQL/PySpark pipelines
score bands
validation checks
threshold testing
strategy comparison
fraud/anomaly signals
monitoring
```

So the rule for this job is:

> Make the CV Tesco-relevant, but not Tesco-fictional.

Next, we should build the evidence ledger for your main platform experience against these proof buckets.

# Evidence Ledger - Tesco Mobile Data Scientist

Yes. We'll build the ledger **without locking ourselves into exact numbers**. The only hard fact we'll keep is the **2.35B-row customer behaviour surface**. Everything else stays as `[placeholder]` until we verify the evidence.

The logic follows the framework: **job ad -> proof buckets -> evidence ledger -> bullet shape -> final bullets**. The Tesco ad asks for customer data science, churn/fraud/propensity modelling, SQL/Python/PySpark, production workflows, testing/CI/CD, statistical analysis, and stakeholder communication. The framework says the ledger should test what evidence exists under each proof bucket before we write bullets.

## Experience being mined

```text
Data Scientist
Customer Behaviour ML Platform - Exeter, UK | May 2025 - Present

Customer-behaviour ML platform across a 2.35B-row customer data surface.
```

This is **not CV wording yet**. This is the evidence bank we will later compress into bullets.

---

## 1. Customer data / scale / pipeline ownership

| Ledger field | Working evidence |
|---|---|
| Proof bucket | Customer data scale + SQL/PySpark pipeline ownership |
| Tesco requirement matched | Customer data, sales/customer behaviour, SQL, Python, PySpark, databases, multiple data sources, data pipelines |
| Core artefact | `[SQL/PySpark feature pipeline / scoring pipeline / customer feature table / model-ready dataset]` |
| Data scope | 2.35B-row customer behaviour surface |
| Data sources | `[N] customer data sources: transactions / usage / account activity / lifecycle / campaign / support / product / behavioural logs]` |
| Action | Built / cleaned / joined / transformed / scored `[customer-level records]` |
| Output | `[customer-level feature table / churn scores / propensity scores / anomaly-risk scores / segmentation outputs]` |
| Metric placeholder | `[N] customers scored`, `[N] features engineered`, `[N] tables joined`, `[runtime improvement]`, `[pipeline success rate]` |
| Baseline placeholder | `[manual extract]`, `[notebook workflow]`, `[previous rules workflow]`, `[unjoined data sources]` |
| Claim strength | Strong if we can show repeatable scoring or reusable pipeline output |
| Evidence still needed | Exact tools, number of sources, whether it was batch scoring, whether it had tests, whether it ran repeatedly |
| Possible bullet direction | Technical delivery / scale bullet |

**Candidate bullet shape later:**

```text
Built [SQL/PySpark] customer-data pipelines over a 2.35B-row behaviour surface, combining [N] sources into [repeatable/model-ready/scored] outputs for churn, propensity and anomaly analysis.
```

---

## 2. Churn / retention modelling

| Ledger field | Working evidence |
|---|---|
| Proof bucket | Churn / retention modelling |
| Tesco requirement matched | Reducing customer churn; churn modelling desirable; improving customer experience |
| Core artefact | `[churn-risk model / retention-risk score / disengagement-risk segment]` |
| Business question | Which customers are most likely to disengage, churn, lapse or need retention action? |
| Action | Modelled customer behaviour signals to identify `[at-risk customers]` before `[retention/campaign/contact decision]` |
| Data used | `[usage patterns / account activity / lifecycle stage / spend / engagement / complaints / product behaviour / payment behaviour]` |
| Metric placeholder | `[X]% lift`, `[X]% recall improvement`, `[X]% precision improvement`, `[X]% top-decile capture`, `[AUC/F1/KS/calibration metric]` |
| Baseline placeholder | `[rules-based targeting]`, `[random selection]`, `[previous model]`, `[unsegmented campaign]`, `[manual prioritisation]` |
| Claim strength | Strong if measured against a defined baseline; weaker if only conceptual |
| Evidence still needed | Define "improved": lift? recall? precision? capture rate? AUC? Was it live, backtested, or simulated? |
| Possible bullet direction | Business/model impact bullet |

**Candidate bullet shape later:**

```text
Improved churn-risk identification by [X]% versus [baseline] in [backtested/live] evaluation, using customer behaviour signals to prioritise [retention/customer contact] decisions.
```

---

## 3. Propensity / targeting / marketing effectiveness

| Ledger field | Working evidence |
|---|---|
| Proof bucket | Propensity / targeting / marketing effectiveness |
| Tesco requirement matched | Personalising customer communications; improving marketing effectiveness; propensity modelling desirable |
| Core artefact | `[propensity model / response likelihood score / offer targeting score / campaign audience ranking]` |
| Business question | Which customers are most likely to respond, convert, upgrade, accept an offer, or benefit from intervention? |
| Action | Ranked customers by `[response likelihood / expected value / offer fit / intervention priority]` |
| Output | `[priority audience / score bands / campaign segment / ranked customer list]` |
| Metric placeholder | Captured `[X]%` of `[responders/high-benefit customers/target customers]` in top `[Y]%` score band |
| Baseline placeholder | `[random targeting]`, `[broad campaign]`, `[previous segmentation]`, `[rules-based selection]` |
| Claim strength | Strong if framed as ranking-quality evidence rather than vague "improved targeting" |
| Evidence still needed | Define target group, score band, evaluation sample, baseline and whether "high-benefit" means conversion, retention, margin, response, or value |
| Possible bullet direction | Ranking / segmentation bullet |

**Candidate bullet shape later:**

```text
Validated propensity ranking quality by capturing [X]% of [target customers] in the top [Y]% score band, creating a defensible priority audience for [offers/messages/interventions].
```

---

## 4. Marketing waste / audience efficiency

| Ledger field | Working evidence |
|---|---|
| Proof bucket | Marketing effectiveness / reducing low-yield targeting |
| Tesco requirement matched | Improving marketing effectiveness; personalising communications; improving business outcomes |
| Core artefact | `[threshold test / scored segmentation / campaign exclusion logic / audience refinement]` |
| Business question | How do we reduce low-value or low-likelihood audience inclusion without losing important customers? |
| Action | Tested score thresholds and segments to reduce `[low-yield/low-propensity/low-value]` campaign inclusion |
| Metric placeholder | Reduced `[low-yield inclusion / wasted targeting / low-propensity contacts]` by `[X]%` |
| Guardrail metric | Preserved `[Y]%` of `[priority-customer coverage / expected responders / high-value customers / retention-risk customers]` |
| Baseline placeholder | `[unsegmented campaign]`, `[previous threshold]`, `[rules-based audience]`, `[broad targeting]` |
| Claim strength | Strong if both efficiency and coverage are defined; risky if "waste" is undefined |
| Evidence still needed | What exactly counts as "waste"? Non-response? Low value? Wrong segment? Duplicate contact? Low expected benefit? |
| Possible bullet direction | Business efficiency / threshold-testing bullet |

**Candidate bullet shape later:**

```text
Reduced [low-yield audience inclusion] by [X]% while preserving [Y]% [priority-customer coverage], using score thresholds and segmentation tests to improve campaign efficiency.
```

---

## 5. Fraud / anomaly / unusual behaviour detection

| Ledger field | Working evidence |
|---|---|
| Proof bucket | Fraud / anomaly modelling |
| Tesco requirement matched | Fraud modelling desirable; customer behaviour modelling; improving business outcomes |
| Core artefact | `[anomaly features / fraud-risk score / unusual behaviour detection layer / rule-comparison analysis]` |
| Business question | Which accounts, behaviours or transactions look unusual before standard rules would flag them? |
| Action | Surfaced abnormal patterns in `[usage / account activity / transaction behaviour / device/account changes / behavioural sequences]` |
| Output | `[high-risk cases / anomaly segments / ranked alerts / fraud-risk indicators]` |
| Metric placeholder | Flagged `[N]` high-risk cases; improved early detection by `[X]%`; captured `[X]%` of known risky cases in top `[Y]%`; reduced false positives by `[X]%` |
| Baseline placeholder | `[rule-based trigger]`, `[manual review]`, `[existing fraud flag]`, `[threshold-only method]` |
| Claim strength | Strong if we can compare to known labels, rules, manual review, or historical confirmed cases |
| Evidence still needed | Were there confirmed fraud labels? Was this anomaly-only? Was it a feature layer, model, or exploratory analysis? |
| Possible bullet direction | Risk/anomaly detection bullet |

**Candidate bullet shape later:**

```text
Built anomaly features from [usage/account/transaction] behaviour, flagging [N] high-risk cases or patterns before [rules/manual review] in [backtested/live] evaluation.
```

---

## 6. Validation / statistics / model trust

| Ledger field | Working evidence |
|---|---|
| Proof bucket | Validation and statistical judgement |
| Tesco requirement matched | Build, validate and optimise models; statistical principles; numerical analysis; model understanding |
| Core artefact | `[validation framework / backtest / lift chart / calibration check / holdout evaluation / stability report]` |
| Business question | Can stakeholders trust the model outputs before using them in decisions? |
| Action | Tested model outputs across `[lift / calibration / freshness / drift / segment stability / threshold sensitivity / coverage]` |
| Metric placeholder | `[AUC]`, `[F1]`, `[precision/recall]`, `[lift]`, `[calibration error]`, `[PSI/drift score]`, `[freshness SLA]`, `[segment stability %]` |
| Baseline placeholder | `[previous model]`, `[rules]`, `[random ranking]`, `[unsegmented campaign]`, `[historical period]` |
| Claim strength | Very strong for Tesco if true, because the ad explicitly asks for validation and statistical methods |
| Evidence still needed | Which validation methods were actually used? Was there holdout data? Time split? Cross-validation? Backtesting? |
| Possible bullet direction | Validation / monitoring bullet |

**Candidate bullet shape later:**

```text
Validated model outputs using [lift/calibration/freshness/stability] checks, improving confidence in customer-level scores before [campaign/retention/fraud] use.
```

---

## 7. Production-shaped workflow / monitoring / testing

| Ledger field | Working evidence |
|---|---|
| Proof bucket | Production workflow / lifecycle ownership |
| Tesco requirement matched | Production workflows, deployment, testing, CI/CD, documentation, security, code optimisation, cloud technologies |
| Core artefact | `[AWS-hosted workflow / versioned scoring pipeline / automated checks / monitoring dashboard / deployment-ready package]` |
| Business question | Can the model workflow be repeated, trusted and maintained beyond a one-off notebook? |
| Action | Packaged, monitored or structured `[data/model/scoring]` workflows for repeatable use |
| Metric placeholder | `[N] scoring runs`, `[X]% pipeline reliability]`, `[runtime reduced from A to B]`, `[N] tests/checks]`, `[freshness SLA]`, `[deployment frequency]` |
| Baseline placeholder | `[manual notebook]`, `[ad hoc scoring]`, `[unversioned script]`, `[manual QA]` |
| Claim strength | Extremely valuable if true; should not be overstated if not actually deployed |
| Evidence still needed | Was it deployed to production, production-shaped, or local/project-based? Were there unit tests, data-quality tests, CI/CD, version control, monitoring? |
| Possible bullet direction | Technical delivery / production-readiness bullet |

**Candidate bullet shape later:**

```text
Packaged [scoring/model/data] workflows with [tests/monitoring/versioned configs] on [AWS/cloud/local], supporting repeatable promotion from validation to [production/stakeholder use].
```

Important: if this was **not fully deployed**, we should say "production-shaped," "repeatable," "deployment-ready," or "validation-to-use workflow" rather than pretending it was production.

---

## 8. Stakeholder decision support / hypothesis-driven analysis

| Ledger field | Working evidence |
|---|---|
| Proof bucket | Stakeholder decisioning and communication |
| Tesco requirement matched | Translate ambiguous business questions into hypothesis-driven analysis; communicate rationale; shape decisions across the business |
| Core artefact | `[strategy comparison / decision memo / model trade-off analysis / recommendation / stakeholder-facing report]` |
| Business question | Which strategy should the business choose, and what trade-offs matter? |
| Action | Compared `[N]` strategies across `[M]` outcome measures |
| Outcome measures placeholder | `[reach]`, `[conversion]`, `[retention risk]`, `[expected value]`, `[cost]`, `[coverage]`, `[false positives]`, `[customer impact]`, `[operational feasibility]` |
| Output | `[recommendation / prioritisation framework / rollout option / threshold decision / campaign strategy]` |
| Metric placeholder | `[N] strategies`, `[M] measures`, `[X]% trade-off improvement]`, `[decision time reduced]`, `[stakeholder sign-off]` |
| Baseline placeholder | `[single strategy]`, `[manual judgement]`, `[unvalidated rollout]`, `[no trade-off comparison]` |
| Claim strength | Strong if you can explain the options, measures and recommendation |
| Evidence still needed | Who were the stakeholders? What options were compared? What decision was made? |
| Possible bullet direction | Stakeholder decision / communication bullet |

**Candidate bullet shape later:**

```text
Compared [N] targeting strategies across [M] outcome measures, translating model trade-offs into a stakeholder recommendation for [campaign/retention/fraud/customer] rollout.
```

---

## 9. Customer communication / segmentation

| Ledger field | Working evidence |
|---|---|
| Proof bucket | Personalised customer communication |
| Tesco requirement matched | Personalising customer communications; improving customer experience |
| Core artefact | `[customer segmentation / lifecycle grouping / response segment / intervention segment]` |
| Business question | Which customers should receive which message, offer or intervention? |
| Action | Grouped customers using `[lifecycle / behaviour / response likelihood / risk / product usage / value]` signals |
| Output | `[retention segment]`, `[upgrade segment]`, `[intervention segment]`, `[do-not-target / low-priority segment]` |
| Metric placeholder | `[N] segments]`, `[X]% improvement in segment separability]`, `[X]% uplift in response]`, `[Y]% coverage of priority customers]` |
| Baseline placeholder | `[one-size-fits-all communication]`, `[manual segmentation]`, `[broad campaign]` |
| Claim strength | Good if framed as segmentation; risky if claiming "improved relevance" without a relevance metric |
| Evidence still needed | How was relevance measured? Response rate? Segment fit? Conversion? Customer value? Stakeholder review? |
| Possible bullet direction | Segmentation / customer communication bullet |

**Candidate bullet shape later:**

```text
Segmented customers by [lifecycle/behaviour/response] signals into [N] actionable groups, giving [CRM/marketing/retention] teams clearer audiences for personalised communications.
```

---

# Prioritised ledger summary

For the Tesco CV, these are the strongest bullet candidates to carry forward:

| Priority | Proof bucket | Why it matters |
|---|---|---|
| 1 | Customer data / SQL/PySpark pipeline | Direct ATS + technical match |
| 2 | Churn / retention modelling | Directly named in the ad |
| 3 | Propensity / targeting | Directly named and highly relevant to marketing effectiveness |
| 4 | Validation / statistics | Proves model discipline, not just modelling claims |
| 5 | Production-shaped workflow / monitoring | Critical because Tesco asks for production workflows, testing and CI/CD |
| 6 | Stakeholder decision support | Matches hypothesis-driven analysis and communication |
| 7 | Fraud / anomaly | Useful because fraud modelling is desirable |
| 8 | Segmentation / customer communication | Useful if we need a customer-experience bullet |

I would probably build the final platform section around **six bullets**:

```text
1. Pipeline / scale / SQL-PySpark
2. Churn-risk modelling
3. Propensity / campaign targeting
4. Fraud or anomaly detection
5. Validation / monitoring / production-readiness
6. Stakeholder strategy comparison
```

That gives us a balanced Tesco-facing portfolio: business relevance, technical delivery, model validation, and stakeholder communication.
