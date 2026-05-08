# Role Mapping Methodology

This is a living note for building experience evidence against the BNP Paribas Data Scientist role.

## Platform Positioning

Full platform positioning is kept separately in:

`platform_positioning.md`

## Platform Experience

### Business Problem

> Understanding and predicting customer credit behaviour to identify risk movement earlier and support responsible financial decisions.

### Method Focus

> XGBoost / gradient boosted trees.

### XYZ Breakdown

| Option | X | Y | Z |
|---|---|---|---|
| 1 | Improved early identification of customer credit risk movement | 18% lift over a Logistic Regression baseline | By deploying an XGBoost scoring workflow across engineered customer, account, transaction, and decision features |
| 2 | Prioritised customer/account reviews | 42% of future risk movement concentrated in the top 20% of scored accounts | By deploying gradient boosted risk scoring into recurring customer/account prioritisation workflows |
| 3 | Replaced static rule based review logic with modelled probability scores | 11% reduction in low value review volume at the same risk coverage | By deploying XGBoost scores into threshold testing and risk band segmentation |
| 4 | Supported responsible customer decisioning | 3 score thresholds tested to balance risk coverage and review volume | By deploying gradient boosted model outputs into strategy comparison workflows |
| 5 | Built a predictive customer behaviour model for credit risk movement | Validated across time based splits to reduce overfitting and future leakage | By deploying XGBoost through a repeatable train-score-monitor workflow |

### CV Bullet

- Improved early identification of customer credit risk movement by 18% over a Logistic Regression baseline by deploying an XGBoost scoring workflow across engineered customer, account, transaction, and decision features.

### Method Focus

> SHAP explainability on top of XGBoost predictions.

### XYZ Breakdown

| Option | X | Y | Z |
|---|---|---|---|
| 1 | Identified behavioural levers behind customer credit risk movement | 4 key drivers surfaced across priority customer/account segments | By applying SHAP explainability on top of XGBoost predictions |
| 2 | Turned XGBoost predictions into explainable business-facing insight | 100% of scored high-risk accounts supported with account-level explanations | By generating local SHAP values for individual customer/account scores |
| 3 | Improved understanding of why customers/accounts were scored as higher risk | Top 5 SHAP drivers used to explain most high-risk movement patterns | By analysing feature contribution values across engineered behavioural signals |
| 4 | Supported clearer prioritisation and responsible decision support | 3 business-facing driver summaries produced for model outputs and risk segments | By aggregating SHAP values across customer/account cohorts |
| 5 | Reduced black-box risk in the XGBoost model | Model outputs translated into explainable behavioural drivers for review and challenge | By combining local and segment-level SHAP explanations |

### CV Bullet

- Identified behavioural levers behind customer credit risk movement by surfacing 4 key drivers across priority customer/account segments using SHAP explainability on top of XGBoost predictions.

### Method Focus

> Agentic behavioural-driver discovery using OpenAI Codex.

### XYZ Breakdown

| Part | Built |
|---|---|
| X | Supported an agentic behavioural-driver discovery workflow for future customer credit risk-movement prediction. |
| Y | From customer credit data exploration to candidate risk-factor hypotheses, SQL/Python feature tests, model comparison, and evidence summaries. |
| Z | Using OpenAI Codex. |

### CV Bullet

- Supported an agentic behavioural-driver discovery workflow for future customer credit risk-movement prediction, using OpenAI Codex to move from customer credit data exploration to candidate risk-factor hypotheses, SQL/Python feature tests, model comparison, and evidence summaries.

### Method Focus

> A/B and champion/challenger testing for model led decision strategies.

### XYZ Breakdown

| Part | Built |
|---|---|
| X | Improved evidence before adopting customer credit strategy changes. |
| Y | 3 threshold strategies compared across 5 outcome measures: risk capture, review waste, escalation rate, time to detection, and operational load. |
| Z | By implementing A/B and champion/challenger testing logic for model led decision strategies. |

### CV Bullet

- Improved evidence before adopting customer credit strategy changes by comparing 3 threshold strategies across 5 outcome measures: risk capture, review waste, escalation rate, time to detection, and operational load, using A/B and champion/challenger testing logic for model led decision strategies.

### Method Focus

> BAU model process maintenance and improvement.

### XYZ Breakdown

| Part | Built |
|---|---|
| X | Kept predictive outputs reliable and trusted. |
| Y | Across customer credit scoring, feature refreshes, drift monitoring, threshold checks, reporting outputs, and model performance reviews. |
| Z | By maintaining and improving BAU model processes. |

### CV Bullet

- Kept predictive outputs reliable and trusted across customer credit scoring, feature refreshes, drift monitoring, threshold checks, reporting outputs, and model performance reviews by maintaining and improving BAU model processes.
