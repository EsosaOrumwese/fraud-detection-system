# Person Specification Responses - NICE Data Scientist (ML Engineer)

## Education / Qualifications - Essential criteria

I meet this criterion through a First Class BEng Mechanical Engineering degree and an MSc Data Science with Artificial Intelligence, completed with Distinction. My MSc developed specialist knowledge in Python, SQL, statistics, machine learning, data preprocessing, model evaluation, visualisation and responsible interpretation of analytical outputs. My engineering background strengthened my numerical reasoning, structured problem-solving and ability to work carefully with complex technical systems.

I have also developed the required specialist knowledge through practical ML engineering work. My strongest example is an AWS-hosted fraud and transaction decisioning platform covering ingestion, validation, feature creation, rule and model decisioning, case creation, monitoring dashboards and offline evaluation. This gave me applied experience across the full ML lifecycle: preparing data, developing models, deploying services, evaluating outputs, monitoring behaviour, documenting assumptions and building controls so outputs could be reviewed rather than treated as black-box scores.

## Education / Qualifications - Desirable criteria: Artificial intelligence certification

I do not currently hold a separate standalone artificial intelligence certification. My AI and machine-learning knowledge is evidenced through my MSc Data Science with Artificial Intelligence, completed with Distinction, and through applied ML engineering work on an AWS-hosted fraud and transaction decisioning platform.

That work involved building and evaluating machine-learning and decisioning components using Python, SQL, rules, logistic regression baselines, gradient-boosted models, anomaly-detection experiments, thresholds and reason codes. I also worked with model evaluation, data-quality checks, monitoring dashboards, model-version records, threshold-version records, documented limitations and responsible-AI controls. I would be willing to complete further AI certification or professional development where this would support NICE's standards, governance approach and organisational AI capability.

## Experience - Essential criteria: designing, building and deploying ML / AI solutions

My strongest evidence is an AWS-hosted fraud and transaction decisioning platform that I built across the full ML lifecycle. The system covered event ingestion, validation, feature creation, rule and model decisioning, case creation, monitoring dashboards and offline evaluation. The aim was not simply to produce a risk score; it was to create a decisioning workflow where events were checked, scored, explained, turned into reviewable cases, monitored over time and improved when data quality or model behaviour changed.

The deployed architecture used API Gateway and Lambda for controlled event ingestion and validation, MSK Serverless for event movement, Docker, ECR and EKS for containerised services, Aurora PostgreSQL for cases and decisions, S3 for raw and curated datasets, CloudWatch for logs and alarms, and EventBridge for scheduled monitoring and evaluation jobs. I used GitHub Actions for linting, unit tests, Docker builds and deployment workflows.

I selected techniques based on the decision problem: rules for transparent checks, logistic regression as an interpretable baseline, gradient-boosted models for stronger scoring candidates, anomaly-detection experiments for unusual patterns, and thresholds/reason codes so outputs could be reviewed. I evaluated models using precision, recall, F1-score, ROC-AUC, PR-AUC, confusion matrices, false-positive and false-negative review, and threshold analysis.

## Experience - Essential criteria: programming, data engineering, complex datasets and analytical products

I have strong programming and data engineering experience across Python, SQL and AWS-based analytical workflows. In my decisioning platform, I used Python and SQL to process data, create features, validate records, score events, evaluate outputs and create analysis-ready datasets. I separated raw events, validated records, feature tables, decision outputs, case records, monitoring outputs and evaluation evidence so each layer could be checked and reused.

I built validation checks for missing fields, duplicate event IDs, invalid categories, failed joins, unexpected row-count movements, null rates and rejected records. I monitored event volumes, validation failures, reason-code frequency, score distributions, threshold-band movement and reviewed-case outcomes so that real behavioural change could be distinguished from broken feeds, missing fields or over-sensitive thresholds.

I have also worked with large and complex datasets outside the platform. In a public-data project, I combined over one thousand daily business activity files into a multi-million-row dataset using Python and pandas, selected stable metrics for time-series interpretation and communicated findings alongside policy context without overstating causation. In my MSc research, I worked with high-frequency smartphone sensor data, creating model-ready windows and evaluating classification outputs while documenting limitations around sampling, class balance and generalisability.

## Skills / Knowledge - Essential criteria: applied mathematics, statistics and numerical analysis

My MSc and applied project work gave me strong grounding in statistics, machine learning and numerical analysis. I have applied statistical and analytical techniques to real problems rather than treating them as theory alone. In my MSc research, I worked with high-frequency sensor data for multi-task classification, preparing model-ready windows and evaluating outputs using accuracy, precision, recall and F1-score while documenting class-balance, sampling and generalisability limitations.

In my decisioning platform, I evaluated model behaviour using precision, recall, F1-score, ROC-AUC, PR-AUC, confusion matrices, false positives, false negatives and threshold effects. I did not rely on headline accuracy because fraud-style data can be imbalanced. I also reviewed how threshold changes affected review workload, because a technically strong model can still fail operationally if it creates too many cases for users to handle.

This gave me practical optimisation experience: balancing detection performance, false-positive burden, false-negative risk and review capacity. I have also used time-series analysis in a public-data project, selecting stable metrics and interpreting movement over time while avoiding unsupported causal claims.

## Skills / Knowledge - Essential criteria: communication and multidisciplinary working

I can communicate analytical outputs clearly to both technical and non-technical audiences. In my decisioning platform, dashboards were designed around user questions: event volume, flagged cases, reason codes, validation failures, score distributions, threshold effects and review workload. Headline views gave the main position quickly, while diagnostic views allowed technical users to investigate model and data behaviour.

My South Western experience also strengthened my ability to work across multidisciplinary teams. I worked with field crews, supervisors, HSE, logistics, maintenance, inventory, commercial colleagues and operations management. I used written summaries, exception views, dashboard outputs and verbal explanations to show what the data said, what was uncertain and what action was needed. This taught me to adapt language depending on whether I was speaking to technical users, operational colleagues or managers.

I have also supported trainees by explaining reporting workbooks, data checks, operational definitions and exception interpretation. In the ML platform, I documented model purpose, features, thresholds, validation rules, dashboard measures and failure checks so another analyst or engineer could understand the workflow, rerun evaluations and challenge the output.
