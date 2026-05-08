# BNP Paribas Data Scientist - Platform Positioning

## Role Posture

For this role, the platform should be positioned as a customer behaviour intelligence and predictive decisioning platform, with the resume emphasis placed on applied data science work inside that platform.

The BNP Paribas Personal Finance role is about using advanced analytical methods to deliver commercial value, understand customer behaviours, test and predict behavioural levers, implement ML/AI business tools, maintain BAU model processes, and communicate clear outputs to senior and non-technical business users.

The platform story should quietly answer:

> Can this person use advanced analytics, ML, AI, and experimentation to understand, predict, test, and explain customer finance behaviour in a way that supports commercial value and responsible financial decisions?

## Core Platform Positioning

The first experience should be framed around:

> AWS-hosted open-source customer credit behaviour platform using advanced analytics, ML workflows, experimentation, model monitoring, and explainable outputs to understand, predict, test, and explain customer behaviour and decisioning levers.

This is not a final resume bullet. It is the role posture.

It should communicate:

- advanced analytical methods;
- customer behaviour;
- commercial value;
- responsible finance decision support;
- predictive modelling;
- ML and AI business tools;
- experimentation and A/B testing;
- model maintenance and BAU confidence;
- senior/non-technical communication;
- innovation through GenAI/Codex-assisted workflows where defensible.

## Customer Behaviour and Business Challenge

The platform should not be presented as a generic fraud or reporting project. For this role, the platform is a customer finance behaviour environment.

The business challenge is:

> Move from reactive review of customer/account activity to earlier, model-supported understanding of behavioural risk movement, decision levers, and customer outcomes.

The platform should be able to answer questions such as:

- Which customers or accounts are changing behaviour?
- Which behaviours signal future risk movement?
- Which cases should be prioritised for review or action?
- Which strategy, threshold, or intervention performs better?
- Which customer behaviours are linked to responsible finance outcomes?
- Can the model still be trusted in BAU?
- Can the result be explained to senior and non-technical business users?

Ranked business challenges to use:

| Rank | Business challenge | Why it fits the platform posture |
| --- | --- | --- |
| 1 | Understanding and predicting customer credit behaviour to identify risk movement earlier and support responsible financial decisions. | Strongest fit for customer behaviour, predictive modelling, responsible finance, and commercial value. |
| 2 | Prioritising customer/account reviews using ML risk signals so attention is focused on cases most likely to need action. | Fits risk scoring, segmentation, thresholding, and practical decision support. |
| 3 | Testing model thresholds and decision strategies before adoption to understand which changes improve customer and business outcomes. | Fits A/B testing, champion/challenger, experimentation, and evidence-led change. |
| 4 | Explaining behavioural levers behind customer risk movement so model outputs can be understood and acted on by non-technical users. | Fits explainability, feature importance, stakeholder communication, and senior-ready outputs. |
| 5 | Maintaining model confidence in BAU by monitoring drift, performance, thresholds, and data refresh quality. | Fits model maintenance, BAU processes, and keeping outputs trusted after deployment. |

## Advanced Analytics Deployment

For the responsibility around deploying tried and tested advanced analytical techniques, the platform story should show named techniques, where they sit, what data they use, and which business challenge they solve.

| Technique area | Named methods | Where it sits in the platform | Business challenge solved |
| --- | --- | --- | --- |
| Classification / risk prediction | Logistic Regression, Random Forest, XGBoost / gradient boosted trees, neural network classifier where defensible | Learning/model layer and decision support layer | Predict which customers/accounts are likely to move into higher risk or need intervention. |
| Baseline modelling | Logistic Regression baseline, decision tree baseline, rule based baseline | Model evaluation layer | Prove whether more advanced methods outperform simpler existing logic. |
| Segmentation | K-Means clustering, hierarchical clustering, behavioural cohorting, quantile/risk band segmentation | Offline analysis and strategy layer | Group customers by behaviour so strategies are not one-size-fits-all. |
| Time behaviour features | Rolling window features, lag features, moving averages, trend slopes, time based validation | Feature engineering and validation layer | Capture how customer behaviour changes over time. |
| Model comparison | Champion/challenger model comparison, baseline vs ML model lift comparison | Learning/model layer | Select stronger methods instead of relying on one untested approach. |
| Explainability | SHAP values, feature importance, scorecard driver analysis | Stakeholder insight layer | Explain why customers/accounts are flagged, prioritised, or predicted to change. |
| Experimentation / A-B logic | Holdout testing, champion/challenger testing, threshold testing, before/after comparison | Strategy evaluation layer | Compare strategy, threshold, or intervention changes before adoption. |
| Anomaly / exception detection | Isolation Forest, z-score/IQR outlier detection, rule based exception flags | Monitoring and exception layer | Identify unusual customer/account movements or reporting exceptions. |
| Calibration / thresholding | Precision-recall trade-off, ROC-AUC, lift curves, decile/gain charts, threshold optimisation | Model deployment and decisioning layer | Choose thresholds that balance commercial value, customer treatment, and review effort. |
| Model maintenance | Drift monitoring, performance monitoring, retraining trigger checks | BAU model maintenance layer | Detect when behaviour or model performance changes and needs review. |

Strong posture:

> Deployed predictive modelling, behavioural segmentation, risk scoring, rolling window feature engineering, time based validation, champion/challenger comparison, threshold testing, and explainability analysis across customer credit behaviour workflows to solve challenges around risk movement, prioritisation, strategy testing, and responsible decision support.

## Strongest Defensible Method Set

Use these first because they are easier to defend and fit the platform story:

- Logistic Regression.
- Random Forest.
- XGBoost / gradient boosted trees.
- Risk band segmentation.
- Rolling window feature engineering.
- Time based validation.
- Threshold testing.
- Feature importance / SHAP explainability.
- Champion/challenger comparison.

## Gradient Boosting for Customer Credit Behaviour Prediction

For the primary business challenge, gradient boosting should be positioned as the main predictive engine for customer credit behaviour.

Business challenge:

> Understanding and predicting customer credit behaviour to identify risk movement earlier and support responsible financial decisions.

What gradient boosting is brought in to solve:

| Problem | Platform positioning |
| --- | --- |
| Customer behaviour is complex | Risk movement is not driven by one variable; it comes from combinations of account activity, transaction behaviour, recent changes, flags, outcomes, and timing. |
| Linear/rule logic may miss interactions | Simple rules or linear models can miss non-linear patterns such as risk rising only when several weak signals appear together. |
| Need earlier risk movement detection | The model should identify accounts likely to worsen before they reach a later escalation stage. |
| Need prioritisation | Predictions should help rank customers/accounts by likelihood of risk movement or need for review. |
| Need commercial and responsible decisions | The output should support better targeting, not blanket treatment of all customers. |

How gradient boosting fits the platform:

| Platform layer | Use of gradient boosting |
| --- | --- |
| Feature layer | Uses engineered customer/account/transaction features: rolling activity, payment behaviour, risk band history, flags, decision outcomes, recent movement. |
| Model layer | Trains XGBoost / gradient boosted trees to predict future risk movement or review need. |
| Decision layer | Converts predicted probabilities into risk bands, prioritisation queues, or strategy groups. |
| Testing layer | Compares model performance against baseline Logistic Regression or rule based scoring. |
| Monitoring layer | Tracks model performance over time to ensure it remains useful in BAU. |

Why gradient boosting specifically:

- Handles non-linear relationships.
- Captures feature interactions.
- Performs well on tabular customer/account data.
- Works with mixed behavioural and transactional features.
- Stronger than simple rules where signals combine in complex ways.
- Still explainable enough when paired with SHAP or feature importance.

What data it uses:

| Data area | Example signals |
| --- | --- |
| Customer/account history | Account age, status changes, previous flags, risk band movement. |
| Transaction behaviour | Frequency, value, recency, volatility, repeated patterns, sudden changes. |
| Payment/credit behaviour | Missed/late payment indicators, repayment pattern changes, utilisation movement if available. |
| Decision outcomes | Previous reviews, escalations, interventions, outcome labels. |
| Time based features | Rolling 7/14/30 day changes, lag features, trend slopes, recent vs historical behaviour. |

What it replaces or improves:

> A static rule based or baseline Logistic Regression approach that could rank obvious cases but may miss complex behavioural combinations and early risk movement.

How it would be deployed:

> The trained gradient boosting model scores customer/account records on a recurring basis, producing probability scores for future risk movement or review need. Those scores feed risk bands, prioritisation outputs, monitoring dashboards, and strategy testing workflows.

Expected results:

| Result type | What it means |
| --- | --- |
| Lift over baseline | XGBoost identifies more future risk movement than static rules or Logistic Regression at the same review volume. |
| Earlier detection | Accounts likely to worsen are identified before later escalation or missed-payment stage. |
| Better prioritisation | Review queues focus more on accounts with genuine movement risk, reducing low-value reviews. |
| Improved threshold control | Risk thresholds can be tuned to balance coverage, review volume, and customer treatment. |
| More stable BAU scoring | Model performance is monitored over time and remains usable across reporting windows. |
| Better commercial targeting | Actions/interventions can be aimed at segments with clearer behavioural evidence. |
| Explainable drivers | SHAP/feature importance shows which behaviours are contributing to risk movement. |

Metric directions:

| Metric | Example |
| --- | --- |
| Lift | Improved high risk identification by 18% over a Logistic Regression baseline. |
| Prioritisation | Concentrated 42% of future risk movement in the top 20% of scored accounts. |
| Review efficiency | Reduced low value review volume by 11% at the same risk coverage. |
| Earlier detection | Identified risk movement 14 days earlier than static rule triggers. |
| Threshold testing | Tested 3 score thresholds to balance risk coverage and review volume. |

Most suitable result for this role:

> Improved early identification of customer credit risk movement by 18% over a Logistic Regression baseline using XGBoost / gradient boosted trees.

Alternative business-facing result:

> Concentrated future risk movement into the top scored account bands, helping prioritise review effort and support earlier responsible decisioning.

Strong posture:

> Used XGBoost / gradient boosted trees on engineered customer, account, transaction, and decision features to predict future credit risk movement, replacing static rule logic with a modelled probability score that supported earlier prioritisation and responsible decision support.

## SHAP Explainability for Behavioural Levers

SHAP should be positioned as the explainability layer on top of the predictive model, not as a separate modelling technique.

Business challenge:

> The model can predict customer credit risk movement, but business users still need to understand why a customer/account was scored higher and which behavioural levers are driving the prediction.

Where SHAP sits in the platform:

| Platform layer | SHAP use |
| --- | --- |
| Model interpretation layer | Explains XGBoost predictions after the model scores customers/accounts. |
| Customer/account review layer | Shows the top factors contributing to an individual account's risk movement score. |
| Segment insight layer | Aggregates SHAP values across groups to identify common behavioural levers. |
| Strategy testing layer | Helps explain why one threshold, segment, or strategy performs differently from another. |
| Stakeholder output layer | Converts model drivers into business-facing explanations and recommended actions. |
| BAU monitoring layer | Tracks whether important drivers change over time, supporting model confidence review. |

What data/outputs it uses:

| Input | SHAP output |
| --- | --- |
| XGBoost model | Contribution values for each feature. |
| Engineered features | Which variables increased or decreased the risk score. |
| Customer/account records | Individual explanation for each prediction. |
| Segment groups | Common drivers across customer cohorts. |
| Time windows | Whether drivers shift between reporting periods. |

How it is applied:

1. Train XGBoost / gradient boosted trees on customer, account, transaction, and decision features.
2. Generate SHAP values for model predictions.
3. Use local SHAP explanations to explain individual high-risk account scores.
4. Aggregate SHAP values to identify the strongest behavioural levers across customer segments.
5. Use those drivers to support model explanation, risk analysis, strategy recommendations, and stakeholder communication.
6. Monitor whether top drivers change over time as part of BAU model confidence checks.

What SHAP explains in this platform:

| Behavioural lever | Meaning |
| --- | --- |
| Recent transaction volatility | Sudden changes in customer/account activity. |
| Risk band movement | Movement from lower risk to medium/high risk states. |
| Frequency/recency changes | Changes in how often or how recently activity occurs. |
| Failed/late payment indicators | Signals linked to worsening financial behaviour if available. |
| Previous flags/reviews | Whether prior risk signals continue to matter. |
| Exposure/utilisation movement | Whether account balance/exposure patterns are shifting. |
| Decision outcome history | Whether previous interventions/reviews relate to current risk. |

Expected SHAP results:

| Result type | What it means |
| --- | --- |
| Behavioural lever identification | Identified which behaviours were most responsible for customer credit risk movement. |
| Individual account explanation | Explained why specific accounts were scored higher or lower by the model. |
| Segment-level insight | Showed which drivers mattered most across different customer/account cohorts. |
| Better stakeholder trust | Made model outputs easier to understand and challenge before action. |
| Clearer strategy recommendations | Linked model drivers to practical decisions around prioritisation, thresholds, or interventions. |
| BAU monitoring insight | Showed whether the main model drivers changed over time, supporting model confidence checks. |
| Reduced black-box risk | Turned XGBoost from a high-performing black box into an explainable decision-support tool. |

Metric directions:

| Metric | Example |
| --- | --- |
| Driver concentration | Top 5 SHAP drivers explained most high-risk movement patterns. |
| Explanation coverage | Produced account-level explanations for 100% of scored high-risk cases. |
| Segment insight | Identified 4 behavioural levers across priority customer/account segments. |
| Stakeholder output | Converted model outputs into 3 business-facing driver summaries. |
| Monitoring | Tracked top driver stability across monthly scoring windows. |

Most suitable result for this role:

> Identified 4 behavioural levers behind customer credit risk movement using SHAP, turning XGBoost predictions into explainable business-facing insight for prioritisation and responsible decision support.

Alternative result:

> Produced SHAP explanations for scored accounts, showing which behavioural features drove higher risk scores and helping translate model outputs into clear prioritisation evidence.

Strong posture:

> Used SHAP explainability on top of XGBoost predictions to identify the behavioural levers behind customer credit risk movement, explain individual account scores, and translate model outputs into business-facing insight for prioritisation and responsible decision support.

Use these only where a clear platform need is defined:

- Bayesian modelling.
- Gaussian models.
- KNN.
- LightGBM.
- Isolation Forest.
- Partial dependence plots.
- Population stability index.

## Experimentation and A/B Testing

For the responsibility around implementing A/B testing techniques, the platform story should be about evidence before adoption.

The platform can position A/B testing as:

> Testing strategy, threshold, model, or intervention changes against a baseline before recommending wider adoption.

Potential comparison designs:

| Testing approach | Platform meaning |
| --- | --- |
| Champion/challenger | Compare an existing rule/model against a new model or threshold strategy. |
| Holdout testing | Reserve a comparison group to measure whether a new strategy produces better outcomes. |
| Threshold testing | Compare different risk score cutoffs for review, escalation, or intervention. |
| Before/after comparison | Compare outcome movement before and after a strategy or rule change. |
| Segment testing | Compare whether different customer/account segments respond differently to the same strategy. |

Strong posture:

> Used A/B style evaluation and champion/challenger testing to compare model thresholds, risk strategies, and intervention logic before recommending decisioning changes.

## BAU Model Maintenance

For the responsibility around maintaining and improving BAU processes, the platform story should show that models and analytical processes remain trusted after initial build.

BAU maintenance can include:

| Maintenance area | Platform meaning |
| --- | --- |
| Model performance monitoring | Track whether model precision, recall, lift, or other evaluation measures are stable over time. |
| Drift monitoring | Check whether input behaviour or customer/account distributions are changing. |
| Threshold stability | Review whether score cutoffs still produce the intended case volumes or risk concentration. |
| Data refresh checks | Confirm new data windows are processed correctly before model/reporting use. |
| Rerun discipline | Keep model experiments and outputs reproducible. |
| QA checks | Validate outputs before they are used in reporting, monitoring, or decision support. |
| Documentation | Keep model logic, assumptions, metrics, and limitations explainable. |

Strong posture:

> Maintained BAU model confidence through model performance monitoring, drift checks, threshold review, data refresh validation, rerun discipline, QA checks, and documentation of model assumptions and limitations.

## GenAI and Innovation

For the responsibility around exploring and innovating new solutions using technologies such as generative AI, the platform story should focus on practical GenAI-assisted data science workflow, not hype.

The stronger defensible angle is:

> Use Codex/OpenAI to support an agentic behavioural-driver discovery workflow, moving from customer credit data exploration to candidate risk-factor hypotheses, SQL/Python feature tests, model comparison, and evidence summaries for future risk-movement prediction.

This is stronger than only using GenAI to summarise SHAP values. SHAP explains what an existing model already learned. Agentic AI helps discover what the model should test next.

Business problem:

> The platform needs to discover which customer behaviours signal future risk early enough to support better, more responsible decisions.

The old approach might be:

> React when a customer crosses a fixed rule or threshold.

The improved approach is:

> Search for behavioural patterns that appear before the threshold is crossed, test whether those patterns improve prediction and prioritisation, and use the evidence to guide the next model or strategy experiment.

Agentic investigation loop:

> question -> data exploration -> hypothesis -> feature idea -> SQL/Python test -> model comparison -> evidence summary -> recommended next experiment

What the AI workflow helps with:

| Stage | What the AI helps with |
| --- | --- |
| Explore | Inspect customer credit behaviour patterns, risk movement, account changes, threshold behaviour, recovery patterns, and early stress signals. |
| Hypothesise | Suggest candidate behavioural drivers or risk-factor hypotheses. |
| Feature design | Propose features such as payment consistency, utilisation acceleration, transaction volatility, recovery trend, repeated threshold near-misses, risk band momentum, and account stability. |
| Test | Generate SQL/Python checks or feature tests to validate whether a hypothesis holds. |
| Compare | Help structure model comparisons against baseline features or previous model versions. |
| Summarise | Convert results into evidence notes and next experiment recommendations. |

Examples of candidate behavioural drivers:

| Driver idea | Platform meaning |
| --- | --- |
| Payment rhythm changes | A change in the consistency or timing of customer payment behaviour. |
| Utilisation acceleration | Customer/account exposure rising faster than normal. |
| Transaction volatility | Sudden changes in volume, value, or frequency of transaction activity. |
| Activity drop-off | Reduced activity that may signal stress, disengagement, or changed behaviour. |
| Recovery trend | Evidence that a previously risky account is stabilising or improving. |
| Repeated near-threshold behaviour | Customers repeatedly close to risk thresholds before formal escalation. |
| Risk band momentum | Direction and speed of movement across risk bands. |
| Account stability index | Composite signal capturing whether behaviour is stable, worsening, or recovering. |

Relationship to the wider data science workflow:

| Step | Role |
| --- | --- |
| Agentic AI | Discovers candidate behavioural drivers and feature ideas. |
| XGBoost / gradient boosted trees | Tests whether those drivers improve risk movement prediction. |
| SHAP | Explains which drivers matter after the model learns them. |
| Experimentation | Tests whether thresholds or strategies based on those drivers improve outcomes. |
| Stakeholder outputs | Translate the evidence into business-facing recommendations. |

Strong posture:

> Used Codex/OpenAI to support an agentic behavioural-driver discovery workflow that explored customer credit data, generated candidate risk-factor hypotheses, produced SQL/Python feature tests, and evaluated which behavioural signals improved risk-movement prediction.

## Stakeholder Outputs and Communication

For the responsibility around clear outputs for stakeholders at all levels, the platform story should focus on explaining customer behaviour and model levers.

Outputs should not look like raw technical reports. They should help business users understand:

- what behaviour changed;
- which levers matter;
- why a model or segment is useful;
- what trade-offs exist;
- what action is recommended;
- what the evidence does and does not prove.

Potential outputs:

| Output type | Purpose |
| --- | --- |
| Senior summary | Explain commercial value, customer impact, and recommended action. |
| Behaviour driver analysis | Show which features or behaviours explain risk movement. |
| Model comparison summary | Explain why one model/threshold is preferred over another. |
| A/B test result summary | Show whether a strategy, threshold, or intervention performed better. |
| Monitoring pack | Show whether model/process performance remains stable in BAU. |
| Limitation note | Explain uncertainty, assumptions, and where the result should not be overused. |

Strong posture:

> Created clear business-facing outputs that explained customer behaviour, model drivers, test results, trade-offs, and recommended actions to senior and non-technical users.

## Data Users

Because this is an open-source/platform project, do not claim real business teams used it unless they did. The safer position is that the platform was designed around these business user groups.

| Team/user type | What they would use the outputs for |
| --- | --- |
| Commercial leadership | Understand customer behaviour, commercial value, and recommended actions. |
| Credit/risk team | Monitor risk movement, model outputs, thresholds, and customer/account prioritisation. |
| Customer strategy team | Compare strategies, segments, and intervention logic. |
| Operations/contact centre teams | Understand case priority, escalation reasons, and customer status. |
| Data science/analytics team | Maintain models, monitor performance, compare methods, and improve processes. |
| Governance/compliance stakeholders | Understand limitations, responsible decision support, data quality, and model traceability. |

For BNP, the most relevant users are:

> Commercial leadership, credit/risk, customer strategy, operations, data science/analytics, and governance.

## Clean Mental Model

Customer finance behaviour data comes in. It is transformed into behavioural features, segments, risk signals, model inputs, predictions, test groups, and monitoring outputs. Advanced analytics and ML are used to understand, predict, test, and explain customer behaviour. Experimentation compares strategies and thresholds before adoption. BAU monitoring checks whether models remain trusted. Outputs are translated into business-facing insight for commercial value and responsible financial decision support.

## Working Boundaries

| Area | Positioning rule |
| --- | --- |
| Platform identity | Customer behaviour intelligence and predictive decisioning platform |
| Main problem solved | Using advanced analytics and ML to understand, predict, test, and explain customer finance behaviour |
| Scale | Large customer/account/transaction/risk surfaces, including the 2.35 billion row credit surface where relevant |
| Storage/query story | AWS-hosted platform with SQL/Python/SAS-capable analytical workflows |
| ML role | Predictive modelling, segmentation, model comparison, threshold testing, and explainability |
| AI/GenAI role | Practical Codex/GenAI-assisted experimentation, QA, documentation, and model evaluation support |
| A/B testing role | Compare strategy, threshold, and intervention changes before adoption |
| BAU role | Maintain model confidence through drift/performance checks, reruns, QA, and documentation |
| Communication story | Translate customer behaviour, model drivers, trade-offs, and recommendations for senior/non-technical users |

## One Line Platform Description Candidate

AWS-hosted open-source customer credit behaviour platform using advanced analytics, ML workflows, experimentation, model monitoring, and explainable outputs to understand, predict, test, and explain customer behaviour and decisioning levers.
