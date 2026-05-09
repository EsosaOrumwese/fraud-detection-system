# Tesco Mobile Data Scientist - Platform Positioning

## Role Posture

For this role, the platform should be positioned as a production customer analytics and ML platform.

The Tesco Mobile role is about using data science to solve real business problems, improve customer experience, and shape business decisions. The strongest platform emphasis is not only modelling, but end-to-end data science delivery: customer data, statistical methods, production ML workflows, data pipelines, testing, deployment, and clear business communication.

The platform story should quietly answer:

> Can this person solve business problems and improve customer experience by turning large customer datasets into production ML workflows, insights, and business decisions?

## Resume Signal Hierarchy

The resume should answer the role in layers.

| Resume layer | Question answered |
|---|---|
| Headline | What is the compressed professional identity? |
| Professional summary | Can this person solve real business problems and improve customer experience using data science? |
| First experience block | Has this person owned meaningful data science lifecycle work with models, pipelines, statistical methods, and production workflow signals? |
| Supporting experience blocks | Do the wider experiences reinforce large data, modelling, communication, collaboration, and analytical judgement? |

## A-Level Questions

The A-level questions are the top scan questions. They should be answered by the headline and professional summary, then proven by the first experience block.

### 1. Has this person delivered impactful outcomes?

The platform answer is yes, through customer behaviour and risk modelling work.

| Hiring signal | Platform answer |
|---|---|
| Customer data experience | Worked with customer, account, transaction, risk, decision, and outcome data across a 2.35 billion row credit surface. |
| Sales/customer behaviour understanding | Analysed customer/account behaviour signals such as activity movement, risk movement, transaction patterns, payment rhythm, volatility, and behavioural drivers. |
| Fraud/churn/propensity modelling fit | Fraud and propensity are the strongest fit. The platform uses fraud/risk behaviour data and predictive scoring to estimate future risk movement or likelihood of review/action. |
| Impactful outcome | Improved early identification of customer credit risk movement, prioritised high-risk accounts, explained behavioural drivers, and supported better decision strategy testing. |

Core answer:

> Delivered impact by using customer behaviour and risk data to build predictive models that identify risk movement earlier, explain behavioural drivers, and support better decision-making.

### 2. What opportunities were identified to improve products, processes, and performance using data?

| Area | Opportunity identified | Improvement direction |
|---|---|---|
| Product/customer experience | Static or blunt risk rules could lead to poor timing or unnecessary escalation. | Use model-led scoring and behavioural segmentation to support more proportionate customer treatment. |
| Process | Manual/rule-based prioritisation may miss early behavioural risk or overload review queues. | Use predictive scoring, thresholds, and champion/challenger testing to improve prioritisation. |
| Performance | Models and thresholds can drift or lose usefulness in BAU. | Add drift monitoring, feature refreshes, model performance review, and threshold checks. |
| Insight process | Analysts may know a customer is risky but not why. | Use SHAP to explain behavioural drivers behind predictions. |
| Discovery process | Existing features may not capture all useful behavioural signals. | Use OpenAI Codex-supported agentic workflows to generate hypotheses, SQL/Python tests, and model comparison evidence. |

Core answer:

> Identified opportunities to improve customer treatment, review prioritisation, model reliability, and behavioural insight by replacing static decision logic with predictive, explainable, tested, and monitored workflows.

### 3. Can this person analyse data to generate insights that improve customer experience and business outcomes?

| Data analysed | Insight generated | Business/customer use |
|---|---|---|
| Customer/account/transaction data | Behavioural risk movement patterns | Earlier identification of customers/accounts needing review. |
| Model scores | Likelihood of future risk movement | Better prioritisation and reduced blunt treatment. |
| SHAP drivers | Why the model scores accounts higher | Clearer explanations for non-technical users. |
| Threshold tests | Which model thresholds balance risk and review effort | Evidence before adopting strategy changes. |
| BAU monitoring | Whether outputs remain trusted over time | Confidence in recurring model use. |

Core answer:

> Analysed customer behaviour data to generate predictive, explainable, and testable insights that could improve customer experience, prioritisation, and business decision-making.

## B-Level Questions

The B-level questions should be answered by the first experience block. They prove that the A-level claims happened in a credible data science environment.

### 1. Was this in an environment where key stages of the data science lifecycle were owned?

| Lifecycle stage | Platform evidence |
|---|---|
| Problem framing | Customer behaviour/risk movement prediction and responsible decision support. |
| Data preparation | Customer, account, transaction, decision, outcome, and risk data joined into modelling surfaces. |
| Feature engineering | Rolling behaviour features, transaction volatility, activity change, risk band movement, decision history. |
| Model building | Logistic Regression baseline, XGBoost / gradient boosted scoring. |
| Model evaluation | Lift against baseline, threshold comparison, model comparison. |
| Explainability | SHAP explanations for behavioural drivers. |
| Experimentation | A/B, holdout, and champion/challenger testing. |
| Deployment/BAU | Recurring scoring, feature refreshes, drift monitoring, performance review, threshold checks. |

Core answer:

> Owned key stages of the data science lifecycle from customer data preparation and feature engineering through model build, evaluation, explainability, experimentation, and BAU monitoring.

### 2. Can this person manage data science models and data pipelines?

Already established platform evidence:

| Area | Existing platform evidence |
|---|---|
| Model management | BAU scoring, feature refreshes, drift monitoring, threshold checks, model performance reviews. |
| Data pipelines | AWS-hosted customer/account/transaction/risk/decision/outcome flows. |
| Large datasets | 2.35 billion row credit surface. |
| SQL/Python | SQL/Python feature tests and modelling workflows. |

Needs expansion for Tesco:

| Tesco signal | Needs clearer positioning |
|---|---|
| PySpark | How Spark/PySpark supports large-scale feature building, joins, and pipeline processing. |
| Production deployment | How the model workflow is deployed into repeatable in-house production pipelines. |
| CI/CD/testing | Unit tests, validation tests, workflow checks, version control, deployment discipline. |
| OOP/good coding practices | How model/pipeline code is structured, reusable, and maintainable. |
| Documentation/security | How production workflows are documented and safe. |

Core answer:

> Managed data science models and pipelines across large customer data surfaces, with Tesco-specific expansion needed around PySpark, production deployment, CI/CD, testing, OOP, documentation, and security.

### 3. Can this person use statistical methods to generate insights?

| Statistical/analytical method | Platform answer |
|---|---|
| Baseline modelling | Logistic Regression baseline. |
| Advanced predictive modelling | XGBoost / gradient boosted trees. |
| Model comparison | Baseline vs XGBoost lift. |
| Threshold testing | 3 threshold strategies across 5 outcome measures. |
| Explainability | SHAP driver analysis. |
| Hypothesis-driven analysis | OpenAI Codex-supported hypothesis generation and SQL/Python testing. |
| Behavioural analysis | Customer/account behaviour, risk movement, transaction volatility, activity change. |

Core answer:

> Used statistical modelling, model comparison, threshold testing, and explainability to turn customer behaviour data into insight and decision evidence.

## Already Strong for Tesco

- Customer data and behaviour.
- Fraud/risk/propensity-adjacent modelling.
- Predictive modelling.
- Explainability.
- A/B / champion-challenger testing.
- BAU model maintenance.
- Large datasets.
- Business decision support.

## Needs Tesco-Specific Expansion

- PySpark.
- Production ML deployment.
- In-house production workflows.
- Data pipelines as production assets, not just analytical flows.
- OOP, unit testing, CI/CD, version control.
- Translating ambiguous business questions into structured, hypothesis-driven analysis.
- Customer experience, product, process, and performance language, not only credit risk language.

## PySpark Platform Positioning

### Role Signal

Tesco asks for strong experience in SQL, Python and PySpark, alongside databases, combining multiple data sources, production ML workflows, testing, CI/CD, and cloud technologies.

For this role, PySpark should not be presented as a tool known in isolation.

It should be positioned as:

> The distributed processing layer used to turn large customer, account, transaction, risk, decision, and outcome data into model-ready features, training datasets, scoring inputs, experiment cohorts, and monitoring outputs.

### Why PySpark Exists in the Platform

The platform already has a 2.35 billion row credit surface and multiple customer, account, transaction, risk, decision, and outcome data flows. The wider evidence tree already establishes large-scale data, AWS storage, data flows, feature engineering, ML workflows, monitoring, experimentation, and governed outputs.

The PySpark reason is:

> Local dataframe processing is not credible at this scale. PySpark is used where the platform needs distributed joins, aggregations, rolling-window features, point-in-time snapshots, and repeatable pipeline processing across large customer datasets.

### Where PySpark Sits in the Platform

| Platform layer | PySpark role |
|---|---|
| Raw/curated data layer | Reads customer, account, transaction, risk, decision, and outcome datasets from AWS/S3-backed storage. |
| Join layer | Combines multiple large datasets into customer/account-level modelling tables. |
| Feature engineering layer | Builds behavioural features from transaction, account, payment, risk, decision, and activity history. |
| Snapshot layer | Creates point-in-time customer/account snapshots for training, validation, and scoring. |
| ML input layer | Produces model-ready datasets for Python, XGBoost, and Logistic Regression workflows. |
| Monitoring layer | Creates score, feature, drift, and outcome tables for BAU model monitoring. |
| Experiment layer | Prepares A/B, holdout, and champion/challenger datasets for threshold and strategy testing. |

### What PySpark Processes

| Data area | Platform meaning |
|---|---|
| Customer data | Customer/account identifiers, status, history, and segments. |
| Account data | Account state, balance/exposure movement, account age, and current status. |
| Transaction/activity data | High-volume activity records used to detect behavioural change. |
| Risk signal data | Flags, risk bands, review triggers, and risk movement history. |
| Decision data | Review decisions, prioritisation outputs, escalation paths, and intervention labels. |
| Outcome data | Later review outcomes, escalations, strategy outcomes, and future labels. |
| Monitoring data | Feature distributions, score distributions, drift checks, and model output history. |

### What PySpark Builds

| Output | Why it matters |
|---|---|
| Model-ready feature tables | Feeds Logistic Regression, XGBoost, and other ML workflows. |
| Customer/account snapshots | Prevents leakage and supports time-based validation. |
| Rolling-window features | Captures behaviour change over 7, 30, 60, and 90 day windows. |
| Risk movement labels | Creates training targets such as future risk-band deterioration or review need. |
| Scoring inputs | Supports recurring model scoring in BAU. |
| Experiment datasets | Enables threshold testing, holdout testing, and champion/challenger comparison. |
| Monitoring tables | Supports drift, feature refresh, threshold stability, and performance checks. |

### Specific Feature Examples

| Feature type | Example |
|---|---|
| Recency | Days since last account activity or payment event. |
| Frequency | Number of transactions or events over a rolling period. |
| Volatility | Change in transaction volume or value compared with prior windows. |
| Trend | Slope or direction of account/risk movement over time. |
| Risk momentum | Speed and direction of movement across risk bands. |
| Threshold behaviour | Repeated near-threshold activity before formal escalation. |
| Outcome history | Previous review or escalation outcomes linked to future behaviour. |

### What It Improves

Before PySpark, the weak version of the positioned platform would be:

> Large raw datasets exist, but feature generation, joins, snapshots, and monitoring outputs are too slow, fragmented, or not repeatable enough for production ML workflows.

With PySpark, the positioned platform becomes:

> Large customer datasets are processed through repeatable distributed pipelines that produce consistent ML inputs, scoring datasets, experiment cohorts, and monitoring outputs.

### Strong Posture

> Used PySpark as the distributed processing layer for the customer behaviour platform, joining multiple customer, account, transaction, risk, decision, and outcome datasets into point-in-time feature tables, ML inputs, scoring datasets, experiment cohorts, and monitoring outputs across a 2.35 billion row surface.

## Production Deployment Platform Positioning

### Role Signal

Tesco asks for experience delivering end-to-end ML solutions independently, deploying fully in-house production workflows, and owning key stages of the data science lifecycle including deployment to production, testing, CI/CD, documentation, and security.

For this role, production deployment should not be presented as a model training claim.

It should be positioned as:

> Taking a data science model from build and evaluation into a repeatable, tested, in-house production workflow that can score refreshed customer data, generate outputs, support monitoring, and be maintained.

### Why Production Deployment Exists in the Platform

The platform already has a 2.35 billion row customer/risk surface, PySpark feature pipelines, Logistic Regression baseline modelling, XGBoost scoring, SHAP explanations, A/B and champion/challenger testing, and BAU model monitoring.

In the positioned platform, production deployment means:

> The customer behaviour ML workflow is not a one-off experiment. It runs as a repeatable AWS-hosted pipeline that ingests data, builds features, scores customers/accounts, writes outputs, runs checks, and feeds monitoring or decision-support layers.

The weak version of the platform would be:

> Models were trained and evaluated, but outputs remained experimental and were not connected to repeatable scoring, monitoring, or decision workflows.

The positioned version becomes:

> Models are deployed into repeatable production workflows where feature refreshes, model scoring, output generation, explainability, monitoring, and testing operate as managed pipeline stages.

### Where Production Deployment Sits in the Platform

| Platform layer | Production deployment role |
|---|---|
| Feature pipeline | Uses PySpark/SQL outputs as stable model inputs. |
| Model packaging | Saves trained model artefacts, metadata, feature schema, and evaluation results. |
| Scoring workflow | Applies the selected model to refreshed customer/account feature tables. |
| Explainability workflow | Generates SHAP outputs for scored accounts or priority segments. |
| Experiment workflow | Sends scores and thresholds into A/B, holdout, or champion/challenger comparison. |
| Monitoring workflow | Tracks drift, feature refreshes, score distributions, threshold stability, and model performance. |
| Output layer | Produces scoring datasets, risk bands, decision evidence, and business-facing summaries. |

### What Gets Deployed

| Deployed asset | Platform meaning |
|---|---|
| Feature pipeline | Repeatable process that produces model-ready features from customer/account/transaction data. |
| Model artefact | Trained XGBoost / Logistic Regression model version with schema and metrics. |
| Scoring job | Recurring job that scores refreshed customer/account records. |
| SHAP explanation job | Workflow that produces driver explanations for model outputs. |
| Threshold logic | Cutoffs used for prioritisation, review, or strategy comparison. |
| Monitoring checks | Drift, performance, feature quality, and output stability checks. |
| Evidence outputs | Tables and summaries used for business review and decision support. |

### What Makes It Production Rather Than Analysis

| Notebook/project version | Production-positioned version |
|---|---|
| Manual model run | Scheduled or repeatable scoring workflow. |
| Local data processing | AWS-hosted pipeline using SQL/PySpark and S3-backed data. |
| One-off train/test split | Time-based validation and repeatable model evaluation. |
| No clear model version | Versioned model artefact and tracked baseline/challenger. |
| No output checks | Data quality checks, score checks, and monitoring outputs. |
| No deployment discipline | Version control, tests, CI/CD, documentation, and rollback/rerun discipline. |
| Hard to explain | Business-facing outputs, model cards, and evidence summaries. |

### Business Problem It Solves

The production deployment branch answers:

> Can this person take a useful model and make it usable repeatedly inside a business workflow?

In the platform, the business problem is:

> Customer behaviour changes continuously, so the business needs a reliable way to refresh data, score accounts, monitor risk movement, and generate outputs without rebuilding the model workflow manually each time.

### What It Improves

Before production deployment:

> Model results exist, but they are not repeatable enough for business use.

After production deployment:

> The model workflow can be re-run, tested, monitored, explained, and connected to recurring customer decision or support processes.

### Strong Posture

> Deployed in-house production ML workflows that connected PySpark feature pipelines, XGBoost scoring, SHAP explanations, threshold logic, and BAU monitoring into repeatable customer behaviour model outputs.

### Safe Wording Boundary

Do not imply the platform was deployed into a real company's live customer system unless that is true.

Safer wording options:

- production-shaped AWS-hosted workflow;
- repeatable in-house ML pipeline;
- deployed into recurring scoring and monitoring workflows;
- production-ready model workflow with testing, CI/CD, documentation, and monitoring.

Best Tesco-facing phrase:

> repeatable in-house ML production workflow.

## Software Engineering Best Practices Platform Positioning

### Role Signal

Tesco asks for good coding practices, object-oriented programming, code optimisation, writing tests, version control, CI/CD, deployment, documentation, security, and cloud technologies.

For this role, software engineering best practices should not be presented as a generic tools list.

It should be positioned as:

> A data science codebase where model pipelines, feature logic, scoring workflows, tests, configuration, documentation, and deployment steps are structured, versioned, and maintainable.

### Why Software Engineering Best Practices Exist in the Platform

For the positioned platform, software engineering best practices means:

> Customer behaviour ML workflows were organised into reusable pipeline components for ingestion, feature engineering, model training, scoring, evaluation, monitoring, and reporting, with tests and version control around the workflow.

The weak version of the platform would be:

> Data science work exists as notebooks or one-off scripts that are hard to test, reuse, deploy, optimise, or challenge.

The positioned version becomes:

> Data science workflows are built as maintainable production code, with reusable modules, tests, configuration, version control, CI checks, documented assumptions, and deployment discipline.

### Where Software Engineering Best Practices Sit in the Platform

| Platform area | Software engineering positioning |
|---|---|
| Feature pipeline code | Reusable PySpark/Python modules for joins, transformations, rolling features, snapshots, and validation. |
| Model training code | Structured training workflow with configuration, model parameters, evaluation outputs, and reproducible runs. |
| Scoring code | Reusable scoring component that loads model artefacts and applies them to refreshed feature tables. |
| Explainability code | SHAP workflow separated from training so explanations can be rerun or reviewed. |
| Experiment code | Threshold, A/B, holdout, and champion/challenger logic held in controlled modules or configuration. |
| Monitoring code | Drift, performance, score distribution, and data quality checks run as repeatable checks. |
| Test suite | Unit and validation tests for transformations, schema expectations, features, scoring logic, and outputs. |
| CI/CD | Automated checks before model or pipeline changes are promoted. |
| Version control | Tracks code, configuration, model logic, feature definitions, and documentation changes. |
| Documentation | Explains model purpose, assumptions, feature logic, metrics, limitations, and operational use. |
| Security | Handles data access, secrets, permissions, and controlled release of outputs. |

### Platform Components and Practices

| Platform area | Software engineering practice |
|---|---|
| Data ingestion | Reusable loaders for customer, account, transaction, risk, decision, and outcome data. |
| Feature engineering | Modular feature builders for rolling windows, behaviour changes, risk movement, and customer/account snapshots. |
| Model training | Config-driven training workflows for Logistic Regression, XGBoost, and baseline/challenger comparisons. |
| Scoring | Reusable scoring functions/classes that load model artefacts and produce customer/account risk scores. |
| Evaluation | Standard metric functions for recall, precision, lift, AUC, threshold testing, and time-based validation. |
| Monitoring | Reusable checks for drift, feature freshness, score distribution, threshold stability, and performance decay. |
| Reporting outputs | Repeatable generation of model summaries, evidence packs, and stakeholder-facing outputs. |

### What Good Coding Practices Look Like

| Practice | Platform positioning |
|---|---|
| Version control | Git-tracked codebase for pipeline logic, model experiments, configuration, tests, and documentation. |
| Object-oriented programming | Pipeline components structured as reusable classes/modules instead of one-off scripts. |
| Unit testing | Tests for feature logic, label creation, threshold rules, scoring outputs, and metric calculations. |
| Integration testing | Small-sample pipeline tests checking ingestion -> feature build -> scoring -> output generation. |
| CI/CD | Automated checks before merging or deploying changes to pipeline or model workflow code. |
| Code optimisation | Avoided inefficient local processing by using PySpark/SQL for large-scale joins, aggregations, and feature generation. |
| Configuration management | Model thresholds, data paths, feature windows, and experiment settings stored as configurable parameters. |
| Documentation | Model cards, pipeline docs, assumptions, limitations, and run instructions maintained with the workflow. |

### What It Improves

Before software engineering discipline:

> The ML workflow may work, but it is hard to trust, rerun, test, maintain, optimise, or hand over.

After software engineering discipline:

> The ML workflow becomes production-ready enough to be reviewed, tested, deployed, monitored, and maintained by a team.

### Strong Posture

> Applied software engineering best practices across the customer behaviour ML platform, structuring PySpark/Python pipelines, model training, scoring, explainability, experimentation, monitoring, tests, version control, CI/CD, documentation, and security controls for maintainable production workflows.

### Best Tesco-Facing Wording

> Structured ML pipelines using Python, PySpark, Git, OOP, unit testing, and CI/CD checks to keep feature engineering, scoring, evaluation, and monitoring workflows reusable and maintainable.

## Hypothesis-Driven Analysis Platform Positioning

### Role Signal

Tesco asks for the ability to translate ambiguous business questions into structured, hypothesis-driven analysis.

For this role, hypothesis-driven analysis should not be presented as generic EDA.

It should be positioned as:

> Taking a broad business or customer problem, breaking it into testable hypotheses, testing those hypotheses against customer data, and turning the results into model features, strategy tests, or business recommendations.

The platform does not just run models. It turns unclear business questions into testable analytical questions, features, models, comparisons, and decision evidence.

### Why Hypothesis-Driven Analysis Exists in the Platform

The platform has customer, account, transaction, risk, decision, and outcome data. Business questions are therefore rarely answered by one table, one metric, or one model run.

Example ambiguous questions:

- Why are some customers or accounts becoming higher risk?
- Which behavioural signals appear before escalation?
- Which customers are being reviewed unnecessarily?
- Which threshold produces better customer and business outcomes?
- Which segments behave differently over time?
- Are model outputs still reliable after behaviour changes?

The weak version of the platform would be:

> Look at the data and report interesting patterns.

The positioned version becomes:

> Translate ambiguous customer behaviour questions into hypotheses, build features to test them, compare model and threshold results, and produce evidence for decision-making.

The important point is not:

> I analysed customer data.

It is:

> I converted a business uncertainty into a structured investigation, tested it with data, and produced evidence that could guide a product, process, or decision change.

### Ambiguous Questions Converted Into Structured Analysis

| Ambiguous business question | Structured analytical version |
|---|---|
| Why are some customers becoming riskier? | Which behavioural signals predict future risk-band movement over the next reporting window? |
| Are we reviewing too many accounts? | Can model-led prioritisation reduce low-value reviews while maintaining risk coverage? |
| Which customers need earlier attention? | Which customer/account behaviours appear before later risk movement or escalation? |
| Are our current rules good enough? | Does XGBoost scoring outperform rule-based or Logistic Regression baselines under time-based validation? |
| What should we change? | Which threshold, segment, or strategy performs better under champion/challenger testing? |

### Hypothesis Loop in the Platform

The platform analysis loop is:

> business question -> hypothesis -> data sources -> feature design -> statistical/ML test -> model comparison -> evidence summary -> recommended action.

| Stage | Platform meaning |
|---|---|
| Business question | Start with an unclear problem around customer behaviour, risk movement, prioritisation, or review volume. |
| Hypothesis | Turn it into a testable statement, such as "transaction volatility predicts later risk movement." |
| Data selection | Pull relevant customer, account, transaction, risk, decision, and outcome data. |
| Feature design | Create behavioural features such as recency, frequency, volatility, risk momentum, or threshold-near-miss behaviour. |
| Testing | Use statistical checks, baseline models, XGBoost, segmentation, or time-based validation. |
| Comparison | Compare against rule-based logic, Logistic Regression baseline, or previous threshold strategy. |
| Evidence | Summarise whether the hypothesis holds and where it is strongest or weakest. |
| Decision support | Recommend whether to adopt, reject, monitor, or test the idea further. |

### Where Hypothesis-Driven Analysis Sits in the Platform

| Platform stage | Hypothesis-driven role |
|---|---|
| Business question framing | Convert a broad customer/business problem into testable analytical questions. |
| Hypothesis design | Define possible behavioural causes, risk drivers, or process issues. |
| Data mapping | Identify which customer, account, transaction, risk, decision, and outcome data is needed. |
| Feature/test design | Create SQL/PySpark/Python tests or features to check whether the hypothesis holds. |
| Model comparison | Test whether the hypothesis improves prediction, segmentation, or prioritisation. |
| Experimentation | Compare thresholds or strategies using A/B, holdout, or champion/challenger logic. |
| Evidence summary | Translate findings into recommendations, limitations, and next analytical actions. |

### Platform Examples

| Ambiguous question | Hypothesis | Test / analysis |
|---|---|---|
| Why are some accounts worsening? | Rising transaction volatility and risk-band momentum appear before deterioration. | Build rolling volatility and risk-momentum features, then test lift in XGBoost. |
| Are some customers over-prioritised? | Static thresholds may flag customers whose recent behaviour suggests recovery. | Compare rule-based flags against recent recovery trend features and later outcomes. |
| Which customers need earlier review? | Behavioural change appears before formal escalation. | Test recency/frequency/volatility features against future review or risk movement labels. |
| Which strategy is safer to adopt? | A model threshold can reduce low-value reviews while maintaining risk capture. | Run champion/challenger threshold comparison across outcome measures. |
| Can the model still be trusted? | Feature drift or score distribution shifts may explain performance movement. | Monitor feature drift, score changes, and performance metrics across refresh windows. |

### Hypothesis Examples and Evidence Produced

| Hypothesis | How it would be tested | Evidence produced |
|---|---|---|
| Customers with rising transaction volatility are more likely to move into higher risk. | Build rolling volatility features and test them in Logistic Regression/XGBoost. | Feature lift, SHAP contribution, recall change, segment-level effect. |
| Static rules flag too many low-value review cases. | Compare rule-based prioritisation with XGBoost score thresholds. | Review volume, risk capture rate, false positive/review waste rate. |
| Recent behaviour matters more than long-term history for some customers. | Compare 30-day, 60-day, and 90-day rolling features. | Model performance by window, threshold stability, driver importance. |
| Some customer segments need different decision thresholds. | Segment customers and compare threshold performance by group. | Segment-level precision/recall, review load, risk concentration. |
| Risk movement can be detected earlier than current triggers. | Use time-based validation to test whether model scores rise before rule triggers. | Earlier detection window, lift over baseline, top-band concentration. |

### Why This Matters for Tesco

Tesco does not only want someone who can build a model from a prepared dataset. They want someone who can deal with real business ambiguity.

This branch answers:

> Can this person take a vague customer or business problem and turn it into structured analysis that improves customer experience or business outcomes?

For the platform, the answer is:

> Yes. Customer behaviour questions are translated into hypotheses around risk movement, customer segments, behavioural signals, thresholds, and review strategies, then tested using statistical methods, ML models, and experiment logic.

### What It Improves

Before hypothesis-driven analysis:

> Data science work risks becoming model-first or pattern-reporting without a clear business decision path.

After hypothesis-driven analysis:

> Each model, feature, test, or insight is tied to a business/customer question and produces evidence that can support a decision.

### Strong Posture

> Translated ambiguous customer behaviour questions into structured hypotheses, engineered testable behavioural features, compared baseline and ML models, and turned the evidence into decision recommendations for customer risk prioritisation.

### Possible Resume Language Later

Not final wording:

> Translated ambiguous customer behaviour questions into hypothesis-driven analysis, using engineered behavioural features, baseline comparisons, and XGBoost models to generate evidence for risk-prioritisation decisions.

## Customer Experience / Product-Process-Performance Improvement Platform Positioning

### Role Signal

Tesco describes the role as solving real business problems, improving customer experiences, personalising customer communications, improving marketing effectiveness, optimising stock management, reducing customer churn, improving products, processes and performance through innovative data-driven solutions, and delivering impactful outcomes.

For this role, customer experience and business improvement should not be positioned as:

> I built a model.

It should be positioned as:

> I used customer data and ML to identify where customer decisions, review processes, or prioritisation strategies could be improved, then tested and explained those improvements through model outputs, thresholds, segments, and evidence summaries.

The platform does not just predict risk. It uses customer behaviour insight to improve how decisions, processes, and outcomes are handled.

In the positioned platform, this means:

> Using customer behaviour data to identify where decision processes are too blunt, too late, too manual, or poorly targeted, then improving them through model-led prioritisation, segmentation, threshold testing, and monitoring.

The customer experience link is not:

> We directly advised customers.

It is:

> We improved the decision-support process so customers/accounts could be understood earlier, prioritised better, and handled with more relevant evidence.

### Why This Exists in the Platform

The platform has customer/account behaviour data, transaction activity, risk signals, decisions, outcomes, model scores, thresholds, SHAP drivers, and monitoring outputs.

This allows the platform to ask:

- Which customers are changing behaviour?
- Which customer groups need earlier attention?
- Which rules or thresholds create unnecessary review?
- Which decision path is too blunt?
- Which behaviour patterns explain risk, recovery, or deterioration?
- Which process is creating wasted effort or poor timing?
- Which model threshold better balances customer and business outcomes?

### What Customer Experience Improvement Means Here

Do not claim direct Tesco Mobile customer experience unless the evidence exists. In this platform, customer experience improvement means making customer decisioning more timely, proportionate, explainable, and evidence-led.

| Customer experience angle | Platform meaning |
|---|---|
| Better timing | Identify behavioural risk before later escalation, so action can happen earlier and more proportionately. |
| Better prioritisation | Focus review/action on accounts with stronger evidence of need, reducing blunt treatment. |
| More relevant treatment | Segment customers/accounts by behaviour rather than applying one rule to all. |
| Fewer unnecessary interventions | Reduce low-value or false-positive reviews from static rules. |
| Clearer decision rationale | Use SHAP and evidence summaries to explain why a customer/account is prioritised. |
| More responsible decisions | Balance risk capture, review load, and customer treatment through threshold testing. |
| More stable outputs | Monitor models and thresholds so decisions remain trusted over time. |

### Product / Process / Performance Improvement

| Improvement area | Platform opportunity | Platform response |
|---|---|---|
| Product | Static customer treatment may not reflect actual behaviour. | Use behavioural segmentation and predictive scores to support more targeted decision paths. |
| Process | Rule-based review queues may be overloaded or poorly prioritised. | Use model-led prioritisation, thresholds, and champion/challenger testing. |
| Performance | Existing strategies may not balance customer outcome and business outcome well. | Compare thresholds using risk capture, review waste, escalation rate, time to detection, and operational load. |
| Insight process | Model outputs may not be trusted if they cannot be explained. | Use SHAP and evidence summaries to explain behavioural drivers. |
| BAU process | Models may degrade as behaviour changes. | Use drift checks, scoring refreshes, threshold stability checks, and performance monitoring. |

### Product, Process, and Performance Improvements

| Area | What improves in the platform | Example |
|---|---|---|
| Product | The customer decision-support product becomes more predictive and explainable. | Static risk flags become model scores, behavioural drivers, and prioritisation bands. |
| Process | Review/prioritisation moves from manual or rule-only logic to repeatable ML-supported workflows. | Accounts are scored, thresholded, tested, and monitored through a recurring pipeline. |
| Performance | The platform improves prediction, review efficiency, detection timing, or threshold stability. | XGBoost improves recall over Logistic Regression; threshold testing reduces low-value reviews. |

### Opportunities Identified Using Data

| Opportunity found | Why it matters | Platform response |
|---|---|---|
| Static rules were too blunt | They may flag obvious cases but miss early behavioural patterns. | Introduce XGBoost risk scoring using behavioural features. |
| Some accounts were reviewed unnecessarily | This wastes effort and may create poor customer handling. | Tune thresholds and compare strategies through champion/challenger testing. |
| Customer behaviour differed by segment | One-size-fits-all thresholds may not work equally well. | Use segmentation and segment-level model evaluation. |
| Risk movement appeared before formal triggers | Waiting for late triggers delays action. | Build rolling-window features to detect earlier movement. |
| Model outputs needed business interpretation | Predictions alone do not tell stakeholders what to do. | Use SHAP and evidence summaries to explain behavioural drivers. |
| Model performance could drift | A model that worked once may weaken over time. | Add BAU monitoring for drift, performance, and threshold stability. |

### Business Question Examples

| Business question | Platform improvement route |
|---|---|
| Which customers are likely to become higher risk? | Predict risk movement with XGBoost and behavioural features. |
| Are we reviewing the right accounts? | Compare rule-based review against model-led prioritisation. |
| Can we reduce unnecessary escalation? | Tune thresholds and monitor false-positive/review waste. |
| Which customer groups need different treatment? | Use segmentation and segment-level model performance checks. |
| Can we trust this model next month? | Monitor drift, score movement, feature refresh quality, and performance. |

### What It Improves

Before:

> Customer decisions or review processes rely heavily on static rules, delayed signals, or unclear model outputs.

After:

> Customer behaviour data is used to predict risk movement earlier, segment customers more intelligently, test decision strategies, explain model outputs, and monitor whether the process remains useful over time.

### Strong Posture

> Identified opportunities to improve customer decision processes by using behavioural data, XGBoost scoring, segmentation, threshold testing, and BAU monitoring to support earlier risk detection, better prioritisation, and more relevant customer/account treatment.

### Possible Resume Language Later

Not final wording:

> Identified opportunities to improve customer decision processes, using behavioural features, XGBoost scoring, segmentation, and threshold testing to support earlier risk detection and better account prioritisation.

Alternative concise wording:

> Improved customer decision workflows by replacing blunt rule-based prioritisation with model-led scoring, behavioural segmentation, and monitored threshold testing.

## Unified Platform Evidence Tree Link

This positioning must remain part of the wider platform evidence tree.

The Tesco branch should not create a separate platform. It should expose the production ML, customer analytics, and software engineering branch of the same customer behaviour/risk intelligence platform.
