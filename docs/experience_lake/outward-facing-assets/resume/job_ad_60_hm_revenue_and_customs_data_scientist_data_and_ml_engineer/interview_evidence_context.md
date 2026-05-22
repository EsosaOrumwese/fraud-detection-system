# Interview Evidence Context - HM Revenue and Customs - Data Scientist (Data and ML Engineer)

Created: 2026-05-22 16:35:56 +01:00

Purpose: working evidence bank for Eric's HMRC application. This file captures interview-style question/response material before compression into a 750-word personal statement, optional 250-word desirable criteria evidence, and a name-blind CV.

## Evidence Item 1 - South Western, MSc and Platform Fit Against HMRC Platform Duties

### Question

Alright Eric, you have seen that this role covers the duties as seen below. Can you walk me through your experience at South Western, MSc and your platform, convincing me of your fit for this role due to the assumption of a similar exposure to what this job requires:

> This role will be responsible for a variety of data management activities across the platform:
>
> Collaborating with Data Scientists and Engineers to help identify, test, deploy and utilise new platform capabilities and data sources.
>
> Developing, scheduling and monitoring jobs for commonly required data transformations and transfers.
>
> Identifying and considering opportunities for data re-use.
>
> Oversight of analysis, R/Python applications & APIs deployed on the platform, including GDPR compliance.
>
> Controlling, facilitating and monitoring access to datasets.
>
> Responsibility for creating and managing data virtualisation layers, to support data exploitation and analytics.
>
> Developing and maintaining documentation on the team's data virtualisation and integration processes.
>
> Being an active member of the data virtualisation community, monitoring the programme for opportunities and potential issues, whilst ensuring data scientists have immediate and performant access to the data.

### Response

The way I see this role is that HMRC is not looking for someone who only builds models in isolation. The duties describe a person who helps a data science platform work properly for data scientists and engineers: integrating data feeds, building reusable data products, scheduling and monitoring transformations, managing access, overseeing deployed Python applications and APIs, maintaining documentation, supporting data virtualisation layers, and making sure the platform is safe, performant and useful for analytics work. That matches the platform and data engineering side of my experience more than a traditional data analyst role alone.

My strongest fit comes from three areas: my Data Analyst role at South Western Technologies & Oilfield Services Ltd, my MSc in Data Science with Artificial Intelligence, and my independent production-ready fraud and transaction decisioning platform. South Western gave me operational data experience in a real business environment. The MSc gave me the formal machine learning, statistical and research foundation. The platform gave me the closest exposure to what this role is asking for: building, deploying and operating a data and machine learning platform where code, data feeds, access, testing, monitoring, documentation and production risk all mattered.

At South Western, the environment was operational and multi-disciplinary. The company's work involved oilfield services, so the data was tied to field jobs, service lines, equipment, crews, QHSE records, mobilisation, completion status and close-out documentation. In that role, I worked with operational records that came from different parts of the business: operations, equipment, QHSE, admin, commercial and management. A job could be marked as completed by one team, but still be missing a signed service report, equipment return confirmation, man-hour record or close-out status. My responsibility was to help turn those scattered records into reliable management information.

That exposed me to the same kind of data integration thinking this HMRC role requires, even though the industry was different. I worked with Oracle-backed operational data and Excel reporting outputs, bringing together job trackers, service activity records, equipment movement records, QHSE submissions and close-out documentation. The goal was not simply to create a report, but to create a usable data product: a weekly operations and close-out view that showed what was active, delayed, field-completed, fully closed, blocked or awaiting follow-up. I used structured Excel workbooks, lookup formulas, pivot tables, validation checks, exception lists and standardised status definitions so that the report could be used repeatedly and trusted by non-technical colleagues.

What that taught me was that integration is not only a technical exercise. Different teams often hold different parts of the truth. Operations may know the job status, equipment teams may know whether the kit has returned, QHSE may know whether records are complete, and admin may know whether a service report has been received. If the analyst simply pulls one status field and reports it, the output may be neat but wrong. I learned to map data back to the real business process, separate confirmed information from missing information, and show uncertainty clearly. That is directly relevant to a platform role where data scientists need immediate and reliable access to data, but that data must still be governed, tested and understood.

I also had to communicate those findings across teams. I did not speak to colleagues as though they were data specialists. I translated the issue into their operating language: this job is field-completed but not document-complete; this equipment is returned but not confirmed as available; this delay is due to client approval, not internal documentation; this QHSE submission is missing, so a zero should not be treated as a true zero. That experience is relevant because this role requires communication with technical and non-technical stakeholders and collaboration across multidisciplinary teams. I learned that a good analyst must make the data useful to the person who has to act on it.

The QHSE reporting work also gave me practical statistical judgement. Raw counts were often not enough. If one service line had more observations than another, it did not automatically mean it had more safety issues. It might have had more man-hours or better reporting discipline. I used rates such as observations per 1,000 man-hours, descriptive statistics, trend views, median and mean comparisons, standard deviation, outlier checks, Pareto breakdowns and data-completeness checks. That helped the team separate high activity from high risk, true zero values from missing submissions, and normal variation from issues needing follow-up. That experience matters here because data products and machine learning outputs can mislead if the underlying data, denominator, definitions and uncertainty are not understood.

My MSc then gave me the formal technical foundation behind that practical experience. Across the MSc in Data Science with Artificial Intelligence, I worked with Python, SQL, machine learning, data preprocessing, statistical modelling, classification, regression, optimisation, feature selection, visualisation and model evaluation. My thesis involved multi-task learning for driver identification and transport mode classification using smartphone sensor data. I downsampled high-frequency sensor readings, segmented journeys, created sliding-window samples, built deep learning models and evaluated them using accuracy, precision, recall and F1-score. That project taught me how to move through a full analytical chain: raw data, preprocessing, feature representation, model training, evaluation, interpretation and limitation reporting.

The MSc is relevant to this HMRC role because it trained me to think beyond whether code runs. In a data science project, the important questions are: is the data representative, has it been transformed correctly, are the labels reliable, are the metrics appropriate, is the model overfitting, is the result reproducible, and can the conclusion be explained? Those are the same questions I later applied in my platform work. The MSc also gave me experience working with notebooks, scripts, version control, the command line, integrated development environments and technical documentation. It strengthened my ability to learn new tools quickly, which is important in HMRC's environment where the role involves platform capabilities, Oracle, SAS, Denodo, Python applications, APIs and new data sources.

The platform is the main reason I believe I fit this role. I built an independent fraud and transaction decisioning platform because I wanted to move beyond coursework and prove I could build something that behaved like a working data and machine learning system. It was not just a model. It included ingestion, validation, transformation, feature creation, decisioning, case creation, dashboards, scheduled jobs, monitoring, access control, testing, deployment, documentation and offline evaluation.

The platform used Python, SQL and SAS. Python was used for services, APIs, data processing, model scoring and orchestration logic. SQL was used for querying, transformations, validation checks and curated analytical views. SAS was used for analytical processing and batch-oriented transformation work where structured statistical processing and repeatable data preparation were useful. The important point is that I did not treat these as isolated tools. I used them as part of a platform workflow where data moved through governed stages and had to become usable for downstream analytics, decisioning and monitoring.

The data flow began with incoming transaction or event data. The first responsibility was ingestion and validation. Events had to be checked for required fields, valid timestamps, recognised categories, duplicate records and values that could not safely be processed. A malformed record could not simply be allowed to pass through silently, because it could distort a risk score or create a misleading case. So validation was part of the system boundary, not an afterthought. Invalid or incomplete records were routed differently, logged, or made visible as data-quality issues rather than being treated as normal.

From there, the platform produced transformed data products. Raw events were separated from cleaned events, cleaned events were separated from feature-ready data, and feature-ready data was separated from decision outputs and case-management records. That separation mattered because each layer had a different purpose. Raw data preserved the original event. Cleaned data supported traceability. Feature data supported scoring. Decision outputs supported case creation. Evaluation data supported model and rule assessment. This is the same principle behind integrating and separating data feeds to map, produce, transform and test new data products.

I also created data virtualisation layers. By that I mean I created governed access layers that allowed the platform, dashboards and analysis workflows to use curated data products without each user or service needing to touch raw storage directly. The raw event store was not the same thing as the analytical view. The case-review layer was not the same thing as the training dataset. The monitoring view was not the same thing as the source transaction stream. I created logical layers and curated views that exposed the right fields for the right use: scoring, monitoring, case review, model evaluation and reporting. That is the same class of work that tools like Denodo support in an enterprise setting: giving users and applications performant access to governed data without forcing them to understand every underlying source.

Scheduling and monitoring jobs was another major part of the platform. The platform needed jobs for data transformations, batch evaluation, feature refreshes, model scoring, validation checks, dashboard refreshes and evidence generation. Some jobs were batch-oriented; others were tied to event-driven processing. I had to monitor whether they ran, whether they failed, whether data arrived late, whether validation errors increased, and whether downstream dashboards reflected fresh data. If a transformation job failed, the problem was not just a technical failure; it could mean a dashboard was stale, a model evaluation was incomplete or a case queue was not trustworthy.

That gave me a clear understanding of why scheduled and monitored jobs matter in a data science platform. Data scientists cannot work effectively if they do not know whether the data they are using is current, complete and fit for purpose. If a feature table is stale, a model evaluation may be wrong. If an ingestion job fails, a drop in case volume may look like reduced risk when it is actually a pipeline issue. If a validation job starts failing, the right response is not to ignore the dashboard but to investigate the upstream feed. I built monitoring around those principles.

The platform also had deployed applications and APIs. Python services exposed decisioning functionality and supported case-management workflows. The APIs were not just technical endpoints; they were part of the operating model. They allowed events to be submitted, decisions to be formed, cases to be created, and outputs to be inspected. I had to think about input validation, response structure, error handling, logging, authentication and what information should be exposed to different users. In a platform role like this HMRC post, oversight of deployed Python applications and APIs matters because an application can create organisational risk if it exposes the wrong data, uses stale outputs, has poor logging or is not compliant with data protection requirements.

Access control was central. I separated access to raw data, transformed data, case records, model outputs, monitoring dashboards and evaluation results. Different users and services did not need the same level of access. A scoring service needed access to feature data. A case reviewer needed the case view and reason codes. A monitoring dashboard needed aggregates and quality indicators. A training workflow needed historical labelled data, but only through controlled and documented pathways. I used permissions, environment configuration, secrets management and cloud access controls so that access was not treated casually.

That is relevant to HMRC because the role specifically mentions controlling, facilitating and monitoring access to datasets. In my platform, access control was about limiting exposure, protecting sensitive information, and ensuring that users or services saw what they needed without unnecessary raw data access. I also learned to avoid hard-coded credentials, use environment variables and managed secrets, apply least-privilege thinking, and keep access paths documented. I understand the fundamentals of data protection from that experience: collect and expose only what is needed, restrict access, maintain traceability, document assumptions, and avoid presenting sensitive or uncertain outputs irresponsibly.

Testing and deployment risk were also important. I could not treat the platform as production-ready just because it ran on my machine. For me, production meant the platform was deployed into a live cloud environment, had repeatable jobs, had monitored services, had access controls, had logs, had testable data flows, had dashboards that could be checked against source records, and had a process for evaluating whether outputs were reliable. It also meant I had to think about failure: what happens if ingestion fails, if validation rejects too many records, if a model threshold creates too many cases, if a dashboard is stale, if a scheduled job fails, or if a rule stops firing?

I designed tests at different levels. At the data level, I used validation checks for schema, required fields, duplicates, timestamps, impossible values and missing critical fields. At the transformation level, I checked whether row counts, category mappings, derived fields and output tables matched expectations. At the model and decisioning level, I used offline evaluation, classification metrics, threshold analysis, false-positive and false-negative review, score distribution checks and drift awareness. At the deployment level, I used smoke checks, logs, monitoring dashboards and rollback thinking so that a bad change would not silently affect downstream users.

Risk documentation was part of that. I documented assumptions, known failure modes, testing outcomes and what different dashboards or metrics did and did not prove. For example, if flagged cases dropped sharply, that could mean lower risk, but it could also mean an ingestion failure, a broken rule, a missing field or a threshold change. If accuracy was high, it could still hide poor minority-class performance. If a case was flagged, that did not mean it was definitely fraud; it meant it required review. Those distinctions mattered because data products can create false confidence if limitations are not visible.

I also had to think about accessibility in a practical sense. The dashboards and outputs had to be understandable to users who did not know the internal implementation. I used clear labels, reason codes, status fields, explanatory tables and separation between data-quality flags and behavioural-risk flags. A user should not need to read the code to understand why a case is in the review queue or whether a dashboard metric depends on incomplete data. That is the same principle I would bring into HMRC: the platform should make data easier to use, not just more technically available.

The BI and monitoring layer is also important. I built dashboards that showed event volumes, decision outcomes, flagged cases, open and closed cases, reason codes, validation failures, rule triggers, score distributions, false positives, false negatives, threshold effects and data-quality issues. These were not decorative charts. They were control surfaces. They answered questions such as: are events arriving, are decisions being produced, are validation failures increasing, are cases being created, are thresholds creating too much review work, is the model behaving differently over time, and can users trust the data?

That connects directly to the role's requirement to support data scientists with immediate and performant access to data. The platform's data layers and dashboards were designed to reduce repeated manual investigation. Instead of a data scientist or analyst digging through raw events every time, they could work from curated datasets, feature views, evaluation outputs and monitoring dashboards. That supported data reuse because the same curated data products could support decisioning, case review, dashboarding and offline evaluation.

Documentation was another major part. A platform becomes fragile if only the builder understands it. I documented data flows, transformation logic, validation rules, model inputs, output definitions, dashboard measures, access assumptions and operational checks. The purpose was to make the system explainable and maintainable. If a new data feed was added, I needed to understand how it mapped into the existing layers. If a rule changed, I needed to know which outputs were affected. If a dataset was reused for model training, I needed to know whether it was admissible and whether it introduced leakage.

That documentation experience is directly relevant to the duty around developing and maintaining documentation on data virtualisation and integration processes. In my platform, the documentation was not an academic appendix. It was operational. It explained where the data came from, how it was transformed, which layer owned which output, what checks were applied, and how users should interpret the result.

Collaboration is another area where my profile fits. At South Western, I worked across operations, QHSE, equipment and admin colleagues. In the platform, the collaboration was partly through my working method and implementation workflow. I treated the work as a multidisciplinary build: data science, data engineering, machine learning, platform operations, security, monitoring, case-management and business decisioning all had to connect. I worked with implementation support and reviewed designs as the platform evolved, making sure the technical build matched the decisioning and evidence requirements. The same pattern applies in HMRC: data scientists, engineers and platform specialists need to work together so that models and analysis can be deployed into the business safely.

The business problem behind my platform was fraud and transaction risk. The platform existed to reduce manual review burden, prioritise suspicious events, explain why cases were flagged, and evaluate whether the decisioning process was working. That is similar to HMRC's environment in the sense that data science work must solve real operational problems, not just demonstrate technical competence. HMRC has large-scale public-service operations, and the data science platform must help teams deliver reliable solutions into the business. I understand that distinction. A model that cannot be deployed, monitored, explained or governed is not enough.

I also have evidence of developing my own technical capability and developing others. I grew my own capability through the MSc and through building the platform. I learned cloud architecture, data engineering, SAS processing, Python service development, SQL transformations, monitoring, deployment, model evaluation and access control because the platform demanded it. I did not learn these as isolated topics; I learned them because each one solved a real problem in the system.

For developing others, I have two practical examples. At South Western, I supported NYSC students and industrial training students by walking them through reporting workbooks, Excel analysis, operational definitions, data checks and how to interpret exceptions without jumping to conclusions. I showed them how to treat missing documentation differently from a true completed status, how to use pivot tables and validation checks, and how to communicate findings in a way that helped operations rather than blamed colleagues. At Five Guys, I have informally trained trial-shift staff and new starters across stations, including prep work, cutting potatoes, line work, order checking, station handovers and operating procedures. That experience taught me how to break tasks down, check understanding, correct errors patiently and help someone become more confident while working under pressure.

If I bring all of this together, my fit for the role is that I have worked across the same broad capability areas. From South Western, I bring experience integrating operational data from different teams, working with Oracle-backed records, producing reusable management information, communicating with non-technical stakeholders, and supporting junior colleagues. From my MSc, I bring formal data science training in Python, modelling, preprocessing, evaluation and responsible interpretation. From my platform, I bring the strongest direct match: Python, SQL and SAS development; data feeds; transformation jobs; scheduled and monitored processes; data virtualisation layers; deployed applications and APIs; access control; cloud architecture; version control; testing; documentation; GDPR-aware design; and production operation.

I would not present myself as someone who already knows HMRC's internal platform. I would need to learn the specific tools, governance rules, data sources and ways of working. But I do understand the kind of work this role requires. It requires someone who can bridge data science and platform engineering, keep data accessible but controlled, help teams use platform capabilities, test and document what is being deployed, monitor for issues, and communicate clearly across technical and non-technical groups.

That is the experience I would bring: practical operational data experience, formal data science training, and a production-deployed data and machine learning platform where I had to make data flows, applications, access, testing, monitoring, documentation and business usefulness work together.

### Extraction Notes

- This is the core HMRC fit narrative for the platform/data management duties.
- The strongest application anchor should be the fraud decisioning platform, not South Western.
- South Western should support multi-source operational data, data quality, non-technical communication and practical data reuse.
- MSc/thesis should support formal data science, Python, modelling, evaluation, reproducibility and technical learning.
- Important claims to preserve carefully:
  - Python, SQL and SAS exposure.
  - Oracle-backed operational data at South Western.
  - Data virtualisation framed as logical/governed access layers, not necessarily Denodo-specific experience.
  - GDPR/data protection awareness framed as fundamentals and design thinking, not formal DPO/legal ownership.
  - HMRC internal platform experience explicitly not claimed.

## Evidence Item 2 - Programming and Build: Prototype to Production-Ready Platform

Captured: 2026-05-22 16:38:27 +01:00

### Question

Alright Eric, that was good to know. Can you now tell me a time where you demonstrated the ability to design, write and iterate code in R/Python/SQL or SAS from prototype to production-ready, understanding security, accessibility and version control? (3500 words minimum)

### Response

The clearest example I would use is my fraud and transaction decisioning platform, because that was the strongest time I moved from an early working prototype into something I would describe as production-ready in the context of an independent data and machine learning platform.

I would choose that example because it brought together the exact parts of the criterion: writing code in Python, SQL and SAS; moving from experimentation to reliable operation; using version control; thinking about security; making the platform usable and understandable; testing before deployment; and making sure the system could be monitored once it was live.

The project started as a data science idea: I wanted to build a system that could assess incoming transaction events, identify suspicious behaviour, create review cases, and monitor whether the decisioning process was performing sensibly. At the beginning, the first version was closer to a prototype. I had notebooks and scripts that could ingest sample transaction data, create basic features, apply rules or model scores, and produce outputs showing whether a transaction looked suspicious. That early version was useful for proving the logic, but it was not production-ready. It could answer, "Can this approach work?" but not, "Can this be operated safely and repeatedly?"

The gap between those two questions is where most of the real work happened.

In the first version, the code was mainly focused on proving the concept: loading data, applying transformations, creating risk features, testing a few rules, training or evaluating models, and inspecting the results. I used Python heavily for data processing, model evaluation and decisioning logic. I used SQL for querying and transformation logic where data needed to be selected, joined, filtered, aggregated or exposed as curated outputs. I also used SAS for structured analytical processing and repeatable preparation of datasets where I wanted controlled transformation and statistical checking. At that stage, the code worked, but it still had the weaknesses of a prototype: too much logic was manual, outputs were not sufficiently separated by purpose, error handling needed to be stronger, and the system did not yet have enough monitoring, access control or deployment discipline.

The first major iteration was to separate the platform into clearer stages. I stopped thinking of the platform as "a model that scores transactions" and started treating it as a data product with a lifecycle. The stages became: event ingestion, input validation, raw data storage, cleaned event creation, feature generation, rule and model decisioning, case creation, dashboard monitoring, and offline evaluation. That separation mattered because each stage had different responsibilities and different risks.

For example, raw events needed to preserve the original record. Cleaned events needed to be standardised and validated. Feature data needed to contain only variables available at decision time. Decision outputs needed to show the score, decision, reason codes and whether the transaction should become a case. Case data needed to support review, status changes and follow-up. Evaluation data needed to compare decisions against later outcomes. Once I separated those layers, the platform became much easier to test, monitor and explain.

The second major iteration was data validation. In a prototype, it is tempting to assume the input data is clean. In a production-ready system, that is unsafe. I built validation checks so the platform could detect missing required fields, invalid timestamps, duplicate transaction events, unexpected categories, impossible amounts, malformed records and values that could break downstream features. A transaction with a missing timestamp, for example, could affect velocity features. A duplicate event could make a customer look more active than they really were. A missing category could affect rule triggers or model inputs. I did not want those problems to pass through silently and create confident but unreliable decisions.

That is where the Python and SQL work became more disciplined. I wrote validation logic that checked records before they moved into the decisioning layer. I used SQL queries to check counts, nulls, duplicates, distinct values, unexpected categories and consistency between raw and transformed tables. I used SAS where structured processing and repeatable analytical preparation were useful, particularly for transformation checks and producing controlled datasets for analysis. The point was not just to clean data, but to make the platform aware of data quality.

The third iteration was around feature creation and decisioning. Fraud and transaction risk cannot usually be understood from one raw field. A transaction amount on its own does not tell you enough. The same amount may be normal for one user and unusual for another. So I created features that described behaviour more meaningfully: transaction frequency in a recent time window, amount compared with previous behaviour, unusual timing, repeated attempts, category changes, high-risk patterns and ratios that compared current behaviour against a baseline. I had to make sure these features were created only from data available at the time of decision. That was important because if future information leaks into the feature set, the model can look stronger in evaluation than it would be in real use.

That was one of the most important lessons from the project. Production-ready code is not only about clean syntax. It is about protecting the logic of the decision. If a model uses information that would not have existed at the time the decision was made, the whole evaluation becomes misleading. So I built the feature pipeline with time-awareness in mind and checked that decision-time features were not contaminated by later outcomes.

The fourth iteration was moving from a score-only output to a decision-support output. A prototype can output a risk score. A production-ready platform needs to explain what the score means and how a user should act on it. So I added decision outputs and reason codes. If a transaction was flagged, the platform needed to show why: unusual amount, high transaction velocity, repeated attempts, unusual time pattern, missing or invalid field, mismatch from previous behaviour, or rule and model disagreement. This made the system more usable because a reviewer would not just see "high risk"; they would see the reason the case needed attention.

This was also where accessibility became important in a practical sense. I am not claiming that I ran a formal accessibility audit, but I did think about whether the outputs were usable and understandable to someone who had not written the code. I used clear field names, status categories, reason codes, dashboard labels and explanations of what metrics meant. I separated data-quality flags from behavioural-risk flags because those should not be interpreted in the same way. A missing field is not the same as suspicious behaviour. If those are mixed together, a user may misunderstand the output. So accessibility, for me, meant making the system readable, navigable and understandable for the people using the outputs.

The fifth iteration was the case-management layer. This was a big part of moving from prototype to production-ready. A fraud decisioning system is not useful if it only produces a file of scores. It needs to support an operational workflow. So I built a case layer where flagged transactions could become review cases with a case ID, transaction details, risk score, reason code, status, created time, updated time and review outcome. The user could see open cases, reviewed cases, escalated cases and closed cases. This changed the platform from an analysis exercise into a working decision-support system.

The sixth iteration was testing. I had to test the platform at several levels. At the data level, I tested whether the inputs met expected rules: required fields present, timestamps valid, no unexpected categories, no duplicate events, no impossible values, and consistent row counts between layers. At the transformation level, I checked whether cleaned data matched the intended mapping from raw data, whether derived features made sense, and whether the output tables had the correct structure. At the model and rule level, I tested whether rules fired as expected, whether thresholds produced reasonable volumes, and whether classification metrics were being calculated correctly. At the platform level, I ran smoke checks after deployment to confirm that events could enter the system, decisions could be generated, cases could be created, and dashboards reflected the underlying data.

A specific example of this was threshold testing. In a prototype, I could choose a threshold that looked good on a metric. In a production-ready platform, that is not enough. A lower threshold may catch more suspicious cases but create too much review workload. A higher threshold may reduce false positives but miss important cases. So I tested threshold effects by looking at flagged volume, precision, recall, false positives, false negatives and case workload. That meant the platform was not simply optimising a model metric; it was balancing model performance against operational usability.

The seventh iteration was deployment and monitoring. I deployed the platform on AWS, which changed the nature of the work. Running locally is one thing. Operating live in a cloud environment is different. I had to think about compute, storage, permissions, networking, logs, monitoring, scheduled jobs, environment configuration and cost. Once deployed, the platform needed to tell me whether events were arriving, whether validation failures were increasing, whether decisions were being generated, whether dashboards were fresh, whether scheduled jobs had run, and whether any rule or model output had changed unexpectedly.

I scheduled jobs for common transformation and transfer tasks. These included data refreshes, validation checks, feature generation, batch scoring, dashboard updates and offline evaluation. I monitored whether those jobs ran successfully and whether outputs looked sensible. If a job failed, the issue was not just that a script had failed. It could mean the dashboard was stale, the decision layer was incomplete, or evaluation results were not trustworthy. That is why scheduling and monitoring were part of production readiness.

One example was monitoring the flag rate. If flagged cases suddenly dropped to zero, I could not assume risk had disappeared. It might mean ingestion failed, a rule stopped firing, a required field became null, or a transformation job did not run. So the dashboard needed to show not only the business output but also the health of the data flow. That was a major shift in my thinking. A production-ready data product needs monitoring of both the outcome and the process that created the outcome.

Security was another important part. I did not treat credentials or access casually. I avoided hard-coded secrets. I used environment variables and secrets management approaches so that sensitive configuration was not embedded directly in the code. I applied least-privilege thinking to access: services and users should only access what they need. Raw data, cleaned data, case records, monitoring outputs and evaluation datasets did not all need the same access path. A scoring service needed feature inputs. A reviewer needed case-level information. A dashboard needed aggregates and quality indicators. A training workflow needed historical data, but only through controlled paths. That separation reduced unnecessary exposure.

I also thought about data protection fundamentals. The platform was built around fraud and transaction data, which is sensitive by nature. Even when working independently, I treated the data as if it needed careful handling. I minimised what was exposed in dashboards, separated aggregated monitoring from record-level case views, restricted access to sensitive layers, and documented assumptions around data use. I also made sure that outputs were not misleading. In data protection and governance, the risk is not only that the wrong person sees data; it is also that the right person sees an output that is wrongly presented as certain. So I made missing fields, validation failures and uncertainty visible.

Version control was central throughout. I used Git and GitHub to manage code changes, track iterations, and keep the platform development controlled. I treated commits as a way of preserving the reasoning behind changes. If validation logic changed, if a threshold changed, if feature creation changed, if dashboard logic changed, or if a model evaluation method changed, I wanted those changes traceable. Version control mattered because a platform can become impossible to trust if outputs change and nobody knows why. If last month's false-positive rate was calculated with one threshold and this month's with another, that difference must be understood. Git helped me control that.

I also used the command line and an integrated development environment as part of the normal workflow. The command line was used for running scripts, checking environments, managing dependencies, interacting with repositories, and working with deployment tasks. The integrated development environment was used for writing, navigating and refactoring code, checking errors, managing project files and working more efficiently than I could in notebooks alone. Moving from notebook experimentation into scripts, services and scheduled jobs required that shift. Notebooks were useful for exploration, but production-ready work needed more controlled code.

One important part of iteration was refactoring. In the prototype, some logic existed as long notebook cells or scripts that did too much at once. As the platform matured, I separated responsibilities. Data validation became distinct from feature creation. Decisioning became distinct from case creation. Monitoring became distinct from offline evaluation. Configuration became separate from code logic. This made the platform easier to test and safer to change. If one layer changed, I could reason about what else was affected.

Another important part was documentation. I documented the data flow, validation rules, feature definitions, reason codes, decision thresholds, dashboard measures, testing assumptions and deployment risks. Documentation mattered because the system needed to be understandable beyond the moment I wrote the code. If I returned to the platform after a break, I needed to know why a threshold had been chosen, what a validation failure meant, which layer produced a dashboard measure, and what a case status represented. That is also important for collaboration. In an HMRC context, platform documentation would be essential because data scientists and engineers need to understand how to use platform capabilities and data products safely.

The result was that the platform evolved from a working prototype into a deployed, monitored and access-controlled data and machine learning system. It could ingest events, validate them, transform them into features, run decisioning logic, create cases, expose monitoring views, support offline evaluation and provide evidence for improvement. It had scheduled jobs, logs, dashboards, access separation, version control, testing, documentation and cloud deployment. That is what I mean by production-ready in this context: not that it was a commercial product used by an employer, but that it had the operational characteristics of a system that could be run, monitored, tested, maintained and improved.

The impact of that work was mainly in the discipline it built. It proved that I could take code beyond an experiment. I learned how to think about failure modes, user interpretation, deployment risk, data quality, security and maintainability. I learned that the best model is not necessarily the most useful system. A useful system is one that produces reliable outputs, makes limitations visible, supports decisions, and can be operated safely.

If I connect this directly to the HMRC role, the match is strong. The role asks for someone who can design, write and iterate code in Python, SQL or SAS from prototype to production-ready, with security, accessibility and version control. That is exactly the journey I went through with the platform. I started with exploratory code and ended with a deployed platform with clearer code structure, data validation, scheduled jobs, monitoring, dashboard outputs, access controls, version control and documented risks.

It also connects to HMRC's data and machine learning environment. HMRC's platform needs data scientists to have immediate, performant and governed access to data. My platform taught me that the job is not only to make data available. It is to make the right data available, in the right form, with the right checks, to the right users, with the right documentation. Otherwise, data access can create more confusion than value.

There were also things I would improve further. If I were doing it again in a larger organisation, I would strengthen formal automated testing, improve deployment pipelines, add more formal approval gates, expand accessibility testing, and document risk decisions even more rigorously. But the core experience is already directly relevant: I have taken code through the path from prototype to production-ready operation and learned the difference between something that works once and something that can be trusted repeatedly.

So the specific example I would give is the fraud and transaction decisioning platform. It demonstrated my ability to write and iterate Python, SQL and SAS code; move from notebooks and scripts into deployed services, scheduled jobs and monitored outputs; use Git and GitHub for version control; design validation and test checks; manage security through access control and secrets handling; make outputs understandable through clear dashboards and reason codes; and operate the platform in a cloud environment. That is the strongest evidence I have for this essential criterion.

### Extraction Notes

- Directly supports essential criterion 1: prototype-to-production coding in Python/SQL/SAS with security, accessibility and version control.
- Strong application phrases:
  - "moved from notebooks and scripts into deployed services, scheduled jobs and monitored outputs"
  - "separated raw, cleaned, feature, decision, case and evaluation layers"
  - "used Git/GitHub to make changes traceable"
  - "validation checks for missing fields, invalid timestamps, duplicates, unexpected categories and impossible values"
  - "least-privilege thinking, no hard-coded credentials, environment configuration and secrets management"
  - "clear reason codes, dashboard labels and separation between data-quality flags and behavioural-risk flags"
- Risk adjustment:
  - Keep "production-ready" contextualised as an independent platform, not a commercial employer product.
  - Accessibility should be framed as usability/readability/understandability rather than formal WCAG audit unless later evidence supports that.
  - Data protection should be framed as fundamentals and careful handling, not formal GDPR legal ownership.

## Evidence Item 3 - Communicating Between Technical and Non-Technical Stakeholders

Captured: 2026-05-22 17:05:20 +01:00

### Question

Alright Eric, that was good to know. Can you tell me of a time when you demonstrate the ability to communicate effectively with technical and non-technical stakeholders, supporting and hosting discussions within a multidisciplinary team.

### Response 1 - South Western Technologies & Oilfield Services Ltd

The strongest example I would give is when I supported a weekly operations and job close-out discussion where the main issue was not just producing a report, but helping different teams agree on what the data actually meant.

At South Western, the work was operational. Jobs involved service activity, field teams, equipment movement, QHSE records, man-hours, service reports and close-out documentation. Different teams owned different parts of the same picture. Operations might know whether a job had been carried out. Field supervisors might know what happened on site. Equipment colleagues might know whether tools had returned. QHSE might know whether safety records and man-hours had been submitted. Admin and commercial colleagues might know whether the signed service report and close-out documents were ready.

The problem was that these teams did not always use the same language. A field team might call a job "completed" because the work on site was finished. Commercial might not consider it complete because the signed service report was missing. Equipment might still see it as open because tools had not been confirmed as returned. QHSE might still be waiting for man-hours or safety documentation. So the same job could look complete to one team and incomplete to another.

My task was to help host and support the discussion around the weekly reporting pack so the team could move from conflicting status updates to a shared view of what needed action.

Before the discussion, I prepared the data. I pulled together records from Oracle-backed job information, Excel trackers, equipment movement notes, QHSE submissions, man-hour records and close-out documentation. I did not bring every raw field into the meeting because that would have overwhelmed people. I created a focused exception view showing jobs that needed clarification: completed but missing signed service report, completed but equipment return not confirmed, delayed with unclear reason, field-completed but not ready for close-out, or QHSE record missing.

In the discussion, I adapted my language to the audience. With operations and field colleagues, I spoke in terms of job status, service line, mobilisation, delay reason and what was happening on site. With equipment colleagues, I focused on whether tools had returned, whether inspection was complete and whether the equipment was actually available for another job. With QHSE, I focused on man-hours, toolbox talks, observation cards and missing submissions. With admin and commercial colleagues, I focused on signed service reports, client references and whether the job was ready for close-out.

The most important thing was that I did not present data issues as blame. Instead of saying, "Your data is wrong," I asked specific questions:

> "This job is marked completed, but the signed service report is not showing. Has it been received, or should it remain as awaiting documentation?"

> "This job has a completion date, but the equipment return is not confirmed. Is the equipment back, or still tied to the job?"

> "This delay is marked as pending. Is that client approval, equipment availability, logistics, documentation or internal follow-up?"

That made the conversation practical. People could answer, correct the record, or confirm the next action. It also helped prevent defensive reactions because the discussion was about resolving the status, not blaming a person or team.

One specific issue we had was that "completed" was too broad as a reporting category. I explained to the group that if we treated all completed jobs the same, the report would hide important follow-up work. I proposed separating the status into clearer categories: field-completed, awaiting documentation, awaiting equipment confirmation, ready for close-out, and requiring clarification. That gave each team a clearer view of what they owned.

The result was that the weekly discussion became more focused. Instead of asking generally, "What is happening with these jobs?", managers could see which jobs were ready, which were blocked, and what the blocker was. Operations could follow up on delayed jobs. Equipment colleagues could confirm return status. QHSE could chase missing submissions. Admin and commercial colleagues could see which jobs were ready for close-out and which still needed documents.

This example shows my communication approach well. I took technical and operational data, prepared it into a usable format, brought the right people into the discussion, translated the findings into each team's language, and helped the group reach a shared understanding. I also used corrections from colleagues to improve the report, so the discussion was two-way rather than me simply presenting a spreadsheet.

The main lesson I took from it was that communication in a multidisciplinary team is not just about explaining clearly. It is about understanding what each group needs from the data, using language they recognise, making uncertainty visible, and keeping the conversation action-focused. That is the same approach I would bring to HMRC: helping data scientists, engineers, platform colleagues and business users understand the same data product from their different perspectives.

### Response 2 - MSc Data Science Research Project

In the MSc context, the example I would use is my Data Science Research Project / thesis, because it required me to communicate a technically complex machine learning project to people with different levels of technical understanding: my supervisor, technical peers, and readers who needed to understand the problem, method, results and limitations without seeing every line of code.

The project was Multi-Task Learning for Driver Identification and Transport Mode Classification. The technical problem was to use smartphone sensor data to do two tasks at the same time: classify the mode of transport and identify the driver. That involved accelerometer, gyroscope and rotation-vector data, large time-series preprocessing, journey segmentation, sliding windows, deep learning models, and model evaluation using precision, recall and F1-score.

The communication challenge was that the project had several layers. At the technical level, I needed to explain why I was using sequence models, how I transformed high-frequency sensor data, why I downsampled the data, how I created journey segments, why I used sliding windows, and how I evaluated the model. But at the problem level, the project was much simpler: if smartphone data is going to support usage-based insurance or transport analytics, the system needs to know whether the phone user is travelling by car and whether they are actually the driver.

So I had to learn to communicate the same project in different ways depending on the audience.

With my supervisor, the discussion was more technical. I had to explain choices around preprocessing, model architecture, training runs, evaluation metrics, and limitations. For example, I could discuss why accuracy alone was not enough, why F1-score mattered, how class imbalance affected interpretation, and why the small number of users in the dataset limited generalisability. Those conversations helped me sharpen the technical reasoning behind the project.

With peers or a less technical reader, I had to reduce the complexity without making the work sound vague. Instead of starting with "multi-task CNN-GRU-biLSTM architecture," I would start with the practical question:

> "Can a smartphone's movement sensors tell us both how someone is travelling and who is driving?"

Then I would build up from there. I would explain that the phone records movement many times per second, but those raw readings are not useful on their own. They need to be cleaned, reduced, segmented into journeys, converted into model-ready windows, and then evaluated carefully. That helped people understand why preprocessing was not just a technical step, but part of the evidence chain.

One of the most important discussions I had to support was around model evaluation. A non-specialist might assume that a high accuracy score means the model is good. I had to explain that this can be misleading, especially if some classes are easier to predict or more common than others. I explained that precision and recall show different kinds of error: whether the model's positive predictions are reliable, and whether it is missing important cases. That made the evaluation more understandable and prevented the result from being overclaimed.

I also had to communicate limitations clearly. The dataset was large in terms of sensor records, but it still had limits around number of users, phone placement, sampling decisions and generalisability. I made sure I did not present the model as if it were ready for universal deployment. I explained what the model showed, what it did not show, and what would need further testing in a wider real-world setting.

That experience is relevant to the HMRC role because it shows that I can take complex technical work and make it understandable without losing the important detail. In a platform or data science environment, technical teams may care about the model, data pipeline, code and evaluation, while business users care about whether the output can be trusted and used. My MSc taught me to bridge those perspectives.

The result was that my final thesis did not just contain code and results. It presented the problem, dataset, preprocessing decisions, modelling approach, evaluation and limitations in a structured way. That is the communication skill I would bring to HMRC: explaining technical work clearly, adapting the level of detail to the audience, making uncertainty visible, and supporting discussions so that people understand what a data product or model output can safely be used for.

### Extraction Notes

- Directly supports essential criterion 2: communicate effectively with technical and non-technical stakeholders, supporting and hosting multidisciplinary discussions.
- South Western is the stronger STAR example because it has genuine workplace stakeholders and a real multidisciplinary meeting context.
- MSc/thesis is useful supporting evidence for technical-to-non-technical translation and explaining model limitations.
- Strong application phrases:
  - "prepared a focused exception view instead of overwhelming colleagues with raw fields"
  - "translated the same job status into operations, equipment, QHSE and admin/commercial language"
  - "made uncertainty visible and kept the conversation action-focused"
  - "used corrections from colleagues to improve the report, making the discussion two-way"
  - "explained precision, recall, class imbalance and limitations without overclaiming the model"
- Risk adjustment:
  - Avoid implying formal meeting chair responsibility if the better claim is "supported and hosted discussions around the reporting pack".
  - South Western should not be framed as a highly technical engineering platform conversation; it is stronger as multidisciplinary operational data communication.
  - MSc should not replace workplace evidence, but can reinforce the ability to communicate technical material clearly.

## Evidence Item 4 - South Western Oracle and SAS Day-to-Day Data Management Experience

Captured: 2026-05-22 17:19:14 +01:00

### Question

Well, all I can say is that this is rubbish. Let me start again, you work in South Western where you get to use Oracle I guess (maybe SAS)? In no less than 3500 words, what's that day to day experience like? What and how do you use, how does the company use, what do you use it to do. Be concrete in this.

### Response

At South Western Technologies & Oilfield Services Ltd, my day-to-day experience with Oracle and SAS sat around operational reporting, data extraction, transformation, validation and management information. I was not an Oracle database administrator, and I was not a SAS platform administrator. My role was closer to the analyst sitting between operational teams and the data: I used Oracle as a source of structured operational records, SAS as a repeatable analytical processing environment, and Excel reporting outputs to produce information that operations, QHSE, equipment, admin and commercial colleagues could actually use.

South Western was an oilfield services environment, so the company's data was tied to real operational work. It was not abstract customer analytics or a clean academic dataset. The records related to client jobs, service lines, field locations, crews, equipment, mobilisation, demobilisation, man-hours, QHSE submissions, service reports, materials, job status and close-out documentation. Because the company supported oil and gas field services, the data had practical consequences. If a job was shown as complete when documentation was still missing, someone could make the wrong planning or close-out decision. If equipment was shown as available when it had not returned or had not been inspected, another job could be planned on a false assumption. If QHSE submissions were missing but treated as zero, management could get a cleaner safety picture than reality.

Oracle was used as the main structured source for operational and business records. In practical terms, Oracle held the more formal data around jobs, clients, service references, purchase orders, equipment or asset records, materials, cost or commercial references, and sometimes status fields that were needed for reporting. It gave the business a structured record of what had been created, assigned, completed or closed. However, Oracle was not the only source of truth in the working sense. Field reports, QHSE trackers, equipment movement notes and close-out spreadsheets often held additional context. So my role was not just to extract from Oracle and assume the answer was complete. My role was to use Oracle records as a structured base, then reconcile them against operational updates and supporting documents.

A normal day usually started by checking what reporting cycle we were in. If we were preparing a weekly operations report, I would focus on job status, service line, field location, planned and actual dates, equipment allocation, crew information and documentation status. If we were preparing a QHSE or man-hour report, I would focus on man-hours, toolbox talks, observation cards, near misses, incidents and missing submissions. If we were preparing a close-out view, I would focus on completed jobs, service reports, equipment return, client references and whether the job was ready for the next administrative or commercial step.

The first practical step was usually extracting or refreshing the structured records. I would use Oracle reports or query outputs to pull the latest job and operational data. That could include job number, client name, service line, location, job status, planned date, completion date, purchase order reference, equipment reference, assigned crew or department, and any status fields that were maintained in the system. I treated those extracts as the formal base. From there, I would compare them with trackers or submissions from other teams.

For example, Oracle might show that a job had a completion date. But the operations tracker might still show it as awaiting close-out. A field report might have been submitted, but the signed service report field in the close-out tracker might still be blank. The equipment note might say a tool had demobilised from site, but the equipment record might not yet confirm it was inspected and available for another job. Those differences mattered, so my work was to identify them, not hide them.

SAS came in where I needed repeatable transformation and analysis. For recurring work, I did not want to manually copy and paste every week. I used SAS to bring in extracts, standardise fields, join records, create flags, produce summary tables and run checks. This was useful because recurring reports needed consistency. If I manually changed categories each week, the output could drift. SAS allowed me to define transformation steps more consistently.

A typical SAS workflow might start with importing the Oracle extract and other structured files into working tables. Then I would clean field names, convert date fields, standardise service line categories, remove obvious duplicates, and create calculated fields. For example, I might create a close-out status flag based on whether a job had a completion date, whether the signed service report was present, whether the equipment return was confirmed, and whether man-hour records had been submitted. That flag could then categorise jobs as active, delayed, field-completed, awaiting documentation, awaiting equipment confirmation, ready for close-out, or requiring clarification.

That sounds simple, but the value was in making those rules explicit. Without that logic, a job with a completion date could be counted as completed even though it was not ready for close-out. With the rule, the report could show the more accurate operational position. That helped managers and admin colleagues see what actually needed action.

One of the core recurring outputs I worked on was a weekly operations and close-out report. The purpose was to give management a practical view of service activity. It needed to answer questions such as: which jobs were active, which jobs were completed, which jobs were delayed, which completed jobs were still missing documents, which jobs were awaiting equipment confirmation, and which records needed follow-up. This was exactly the kind of work where Oracle, SAS and Excel had different roles.

Oracle provided the structured job and operational records. SAS transformed and tested the data. Excel was often the final review and communication format because it was accessible to managers and team leads who were already comfortable using it. The final output was not just a spreadsheet of rows. It was a management view with tabs for summary, exceptions, job detail and outstanding actions.

In the summary view, I might show counts of active jobs, delayed jobs, field-completed jobs, jobs ready for close-out and jobs requiring clarification. In the exception view, I would list the specific records that needed action. For example: completed but no signed service report, completed but equipment return not confirmed, delayed but no delay reason, field-completed but no man-hour record, duplicate job reference, missing service line, inconsistent client name, or blank close-out status.

The exception list was one of the most important outputs because it turned the report into an action tool. Instead of managers asking generally, "What is happening with these jobs?", they could see exactly what needed to be checked. Operations could follow up on delays. Equipment could confirm return or inspection status. QHSE could chase missing records. Admin could chase service reports. Commercial colleagues could see which jobs were ready for the next step.

SAS was useful for generating those flags in a repeatable way. I could write transformation logic that checked the same conditions each cycle. For example, if completion date was present but service report status was blank, the record would be flagged. If job status was active but completion date was present, it would be flagged for status review. If service line values appeared under different labels, the mapping logic would normalise them. If man-hours were present but not linked to a job reference, the record would be flagged for clarification.

I also used SAS for basic statistical and completeness checks. In QHSE reporting, the issue was not only whether counts existed. It was whether the counts were meaningful. For example, if one service line had ten observation cards and another had two, the raw count alone could mislead. The first service line might have had far more man-hours or more active jobs. So I used man-hour denominators to calculate observation rates. I looked at total man-hours by service line, observation counts, missing submission counts, and rates such as observations per 1,000 man-hours. That helped separate higher activity from higher risk.

Another common issue was distinguishing true zero from missing data. If a team submitted a report showing zero near misses, that meant one thing. If the team had not submitted the report at all, that meant something very different. In SAS, I could create completeness indicators: submitted, not submitted, partially complete, missing job reference, missing date, missing service line, or awaiting clarification. This prevented the final report from treating missing records as clean performance.

A concrete example was a monthly QHSE activity summary. The source data might include man-hour records, toolbox talk attendance, observation cards, incident notes and near-miss logs. Oracle might provide job and crew references, while QHSE trackers provided the safety submissions. I would use SAS to join the records by job reference, service line, date and team. Then I would produce tables showing total man-hours, number of submissions, missing submissions, observation categories and rates. I could then identify where the data suggested a reporting gap rather than a true reduction in risk.

For instance, if a service line showed high man-hours but no observation cards and several missing toolbox talk records, I would not present that as "no safety issues." I would mark it as requiring confirmation. In discussions, I would explain that the issue was not necessarily poor performance; the issue was that the data was not complete enough to draw a confident conclusion. That is the kind of statistical caution I developed in the role.

My day-to-day also involved testing. I did not treat Oracle extracts or SAS outputs as automatically correct. I checked row counts before and after transformation. I checked whether any records dropped unexpectedly during joins. I looked for duplicate job numbers, missing dates, blank service lines, strange status transitions, and totals that did not align with the previous period. If the number of completed jobs changed sharply from one week to the next, I would ask whether the change reflected actual operations or a data update issue.

For example, if last week there were thirty active jobs and this week the extract showed twelve, I would not immediately report that activity had dropped. I would check whether the date filter changed, whether the Oracle extract was incomplete, whether a service line was excluded, whether a status field changed, or whether a file had failed to load correctly. This habit was important because the report was used by people who might act on the numbers. Testing was not only technical quality control; it protected decision-making.

The same applied to mappings. Service lines could be written differently across sources. One source might say cementing, another might say pumping and cementing, another might use an abbreviation. If those were not mapped consistently, the report would split one activity into several categories. I maintained mapping logic so the reporting categories were stable. That is a small example, but it matters because inconsistent categories make trend comparison unreliable.

Another part of my work was reconciling Oracle outputs against operational reality. Oracle held structured records, but field activity moved quickly. Sometimes the system was behind the site update. Sometimes the field update existed but had not been entered into the system. Sometimes a service report was submitted but not marked as received. So I had to treat Oracle as the formal source but still validate it against supporting teams. That meant the final report often became a point of discussion.

When I found a mismatch, I would not simply overwrite the data. I would ask the relevant person for confirmation. For example, I might ask operations whether a job was genuinely completed, equipment whether the tools had returned, QHSE whether the submission had been received, or admin whether the signed report had been filed. Once confirmed, I would update the reporting view or mark it as requiring clarification. This was important because the analyst's role was not to guess. It was to present the current known position and identify what was uncertain.

In terms of what the company used Oracle for, it was mainly to hold structured enterprise records. That included job and project references, client details, service lines, equipment and asset records, purchase or commercial references, and formal status information. The company needed Oracle because oilfield operations create many linked records. A job is not just a job. It may have a client, a purchase order, a field location, a service line, equipment, crew, cost elements, documents and close-out requirements. Oracle allowed those records to be held in a structured way.

But the business still needed analysts because structured records do not automatically become insight. A manager does not want to inspect every raw field. They want to know what is happening, what is delayed, what is blocked, what is complete and what needs action. That is where SAS and reporting came in. My role was to turn system records and team submissions into usable outputs.

The company used SAS more for analytical processing and repeatable reporting. SAS was useful where I needed to join sources, clean fields, apply rules, create reporting categories, calculate rates, and produce controlled outputs. It gave more structure than manual spreadsheet work and helped reduce the risk of doing transformations differently each week. It also helped with auditability, because the logic could be reviewed and rerun.

A typical SAS program for a recurring report might bring in the latest Oracle extract, bring in a QHSE tracker or close-out file, standardise field formats, apply mappings, join records, create exception flags, calculate summary counts and export output tables for review. I would then inspect the output before sharing it. That inspection mattered because code can run and still produce the wrong answer if the input changed or the assumptions no longer hold.

One example is a status mapping. Suppose Oracle had status values such as open, active, completed, closed and cancelled, while the operational tracker used scheduled, mobilised, demobilised, awaiting report and ready for close-out. SAS helped create a combined reporting status. That reporting status was more meaningful to management than either source alone. It could show that a job was field-completed but not ready for close-out, which was the distinction the business actually needed.

Another example is equipment availability. Oracle might show equipment assigned to a job, but availability depended on whether it had returned, whether inspection was complete and whether documentation had been updated. I could join job records with equipment movement records and flag equipment still tied to a completed job. That helped operations avoid assuming that equipment was free when the system record was not fully updated.

The same logic applied to commercial close-out. A job might be operationally complete, but the commercial process needed signed service reports, client references, man-hours and supporting documentation. The report helped identify which completed jobs were actually ready for the next step. This mattered because delays in documentation could delay commercial processing or create repeated follow-up work.

The day-to-day experience was therefore a mixture of extraction, transformation, testing, reporting and communication. I would spend part of the day working with Oracle outputs, part of the day running or adjusting SAS logic, part of the day checking the results, and part of the day clarifying issues with colleagues. Some days were more technical. Other days were more communication-heavy. During reporting deadlines, the priority was to get a reliable view ready in time for a meeting or management review.

The most concrete example of that pressure was the weekly operations pack. Before the meeting, I needed to refresh the data, run the transformations, check exceptions, compare against the previous period, and prepare the summary. If there were unresolved mismatches, I had to decide whether to mark them as awaiting clarification or chase confirmation before the report went out. I learned not to delay the entire report waiting for perfect data, but also not to hide uncertainty. The report needed to show both the known position and the unresolved items.

That is a key part of real operational reporting. Data is rarely perfect by the deadline. The analyst has to be honest about what is confirmed and what is pending. In my reports, an "awaiting clarification" category was not a weakness; it was a way of preventing false certainty. It told users that the record needed confirmation before being treated as complete.

I also learned to document definitions. If "completed" meant one thing in Oracle and another thing in the operations discussion, I needed to explain how the reporting category was defined. For example, field-completed meant work had ended on site. Ready for close-out meant the required documentation and confirmations were present. Closed meant the process had been fully completed. These distinctions helped users understand the report and reduced repeated arguments about what a number meant.

The most valuable part of using Oracle and SAS in that role was that they taught me how enterprise data and analytical processing fit together. Oracle gave structured operational records. SAS gave a way to transform, test and summarise those records. The final reporting output gave teams information they could act on. Each layer had a purpose.

I also developed a stronger appreciation for access and responsibility. Not everyone needed access to every raw record. Some people needed job-level detail. Others only needed aggregated summaries. Some records contained commercial or operationally sensitive information. I learned to be careful about what was included in reporting outputs, who the output was for, and whether the detail was necessary. That was not GDPR in the same way as a UK public-sector role, but it was still responsible information handling.

If I were explaining this experience for the HMRC role, I would say it gave me exactly the practical grounding behind the data feed criterion. I integrated data from Oracle and team-level sources. I separated raw extracts, cleaned datasets, exception views and final reporting outputs. I mapped fields across different sources. I transformed operational records into reusable data products. I tested outputs using row counts, duplicates, missing fields, status logic, reconciliation and business checks. I used SAS to make recurring transformations more repeatable. I used Oracle as the structured source of enterprise data. I used the final reports to support operational, QHSE and commercial decision-making.

The biggest lesson was that a data product is not just a table or a report. It is a controlled way of answering a business question. At South Western, the question was often: what work is active, what is delayed, what is complete, what is blocked, and what needs action? Oracle held part of the answer. SAS helped build the answer. The reporting discussion tested whether the answer matched reality.

That is the experience I would bring into a role like HMRC's Data Scientist, Data and ML Engineer post. I understand how to work with structured enterprise data, transform it into controlled analytical outputs, test the logic, document definitions, and communicate the result to users who need to make decisions. I also understand that named tools matter, but the deeper skill is knowing how to move data safely from source to product without losing meaning, traceability or trust.

### Extraction Notes

- This replaces the weaker generic South Western framing when discussing Oracle/SAS.
- Directly supports:
  - Essential criterion 3: integrate and separate data feeds to map, produce, transform and test new data products.
  - Essential criterion 4: plan, design, execute and report tests.
  - Technical skill: data development process.
  - Technical skill: data engineering.
  - Technical skill: communicating between technical and non-technical, if paired with the weekly operations discussion.
- Strong application phrases:
  - "Oracle as the structured source; SAS as the repeatable analytical processing environment; Excel as the communication output."
  - "separated raw extracts, cleaned datasets, exception views and final reporting outputs."
  - "checked row counts before and after transformation, unexpected drops during joins, duplicates, missing fields and status logic."
  - "distinguished true zero from missing submissions."
  - "created explicit rules for field-completed, awaiting documentation, awaiting equipment confirmation, ready for close-out and requiring clarification."
  - "treated Oracle as the formal source but reconciled it against operational reality."
- Risk adjustment:
  - Keep the role clear: analyst/user of Oracle and SAS, not Oracle DBA, SAS administrator or enterprise platform owner.
  - Keep "Oracle-backed" and "Oracle reports/query outputs" wording unless stronger evidence confirms direct SQL access privileges.
  - Keep SAS framing around repeatable analytical processing and reporting, not advanced SAS platform administration.
  - Do not overstate GDPR from South Western; use "responsible information handling" unless discussing the fraud platform separately.

## Evidence Item 5 - Deployment and Cloud Architecture Understanding

Captured: 2026-05-22 18:49:55 +01:00

### Question

What is your understanding of deployment and also cloud architecture? Do you have any technical experience in both? Talk me through it in no less than 3500 words.

### Response

My understanding is that deployment is the point where code, data pipelines, models, applications or analytical services stop being local experiments and become something that can run in a controlled environment for users, systems or scheduled processes. It is not just "uploading code" or "pressing run." Deployment means the code has been packaged, configured, connected to its data sources, given the right permissions, tested, monitored, and made available in a way that can be repeated and supported.

For me, deployment has four parts.

First, there is the technical release: the code, service, model, data transformation or dashboard has to move from development into an environment where it can run reliably. That could mean a container running on a cluster, a Python service behind an API endpoint, a scheduled transformation job, a deployed model artifact, or a dashboard reading from curated data.

Second, there is the configuration and access layer: the deployed component must know where to find its data, which credentials or permissions it has, which environment variables it needs, what secrets it must not expose, and what other services it is allowed to communicate with.

Third, there is the testing and validation layer: before I can trust the deployed component, I need evidence that it works after deployment, not just on my local machine. That includes smoke checks, data validation, input and output checks, error handling, monitoring, and confirmation that the output reconciles back to source records.

Fourth, there is the operational layer: once it is live, I need logs, metrics, alarms, dashboards and a way to respond when something fails or behaves unexpectedly. A deployed platform is not finished at the moment it goes live. It becomes something that has to be watched, maintained, improved and sometimes rolled back or corrected.

My understanding of cloud architecture is that it is the design of the environment where those deployed systems run. It covers how compute, storage, networking, data movement, security, identity, monitoring, cost control and operational processes work together. In cloud architecture, I am not only thinking about one application. I am thinking about how the whole system is arranged: where data enters, where it is stored, how it moves, what services process it, which users or services can access it, what happens when components fail, how logs and metrics are captured, and how the platform remains secure and cost-aware.

My strongest technical experience with both deployment and cloud architecture comes from building and operating my fraud and transaction decisioning platform on AWS. That platform was the main project where I moved beyond local analysis and worked through what it means to deploy a data and machine learning system into a live cloud environment.

The platform started as a data science idea. I wanted to process transaction events, score risk, flag suspicious behaviour, create cases for review, monitor how the system behaved and evaluate whether the decisioning logic was working. At the beginning, I could prove parts of that in a local environment using Python, SQL and SAS. I could load data, create features, run rules or models, evaluate outputs and inspect the results. But that was only a prototype. It did not yet answer the harder question: can this run as an actual platform?

To make it deployable, I had to separate the system into clear responsibilities. I had an ingress layer for incoming events, a data validation layer, transformation jobs, feature creation, decisioning services, case creation, monitoring dashboards, offline evaluation and evidence storage. Each part had to have a defined role. The ingress service was responsible for receiving events and rejecting or routing invalid inputs. The transformation layer was responsible for turning raw data into usable records. The decisioning layer was responsible for applying rules and model outputs. The case layer was responsible for creating and updating review cases. The evaluation layer was responsible for checking false positives, false negatives, thresholds and model behaviour. The monitoring layer was responsible for showing whether the platform was healthy.

This is where cloud architecture became important. In AWS, I used services for API access, serverless processing, streaming, storage, orchestration, containerised services, databases, monitoring, secrets and evidence. The platform used an API Gateway entry point to receive events. It used Lambda for ingestion logic where events could be validated, deduplicated and published onward. It used managed streaming through MSK Serverless so that fraud traffic and context events could move through the platform. It used a schema registry so that event structures were not left informal. It used EKS for running the real-time decisioning and case-related services. It used Aurora PostgreSQL for runtime state such as decisions, actions, cases, labels and continuity records. It used S3 for object storage, evidence, training data, evaluation outputs and proof records. It used SSM Parameter Store and secrets handling for active handles and configuration. It used CloudWatch for logs, metrics, alarms and dashboards. It used Databricks, SageMaker and MLflow for the learning, evaluation and model lineage parts.

That architecture mattered because each service solved a different problem. API Gateway gave a controlled edge for incoming traffic. Lambda gave a managed execution layer for ingestion. MSK provided event transport. EKS gave me a place to run longer-lived platform services. Aurora gave transactional state. S3 gave durable object and evidence storage. CloudWatch gave observability. Databricks and SageMaker supported the managed learning side. GitHub Actions supported controlled dispatch and release workflows. IAM roles and OIDC trust supported identity and deployment security.

My role in building it was not just to select services. I had to understand the boundaries between them. For example, an incoming event should not go directly into a model. It first needed to pass through an access point, be logged, be checked for validity, be deduplicated, and then be published into the transport layer. From there, downstream services could consume it, derive context, create features, resolve identities or entities, and form decisions. That separation helped the platform become more reliable because failures could be isolated and monitored.

One important deployment lesson was around environment configuration. Locally, I might have a file path, a database string or an API key on my machine. In a deployed cloud environment, that is not acceptable. Configuration must be externalised. Secrets must not be hard-coded. Services must read environment-specific values from controlled places. In the platform, that meant using parameter and secret handling for active handles, broker information, API keys and configuration references. It also meant thinking about which service identity had permission to read which value.

That connects directly to security. Security in deployment is not one feature at the end. It is built into the architecture. I had to think about IAM roles, least privilege, access to object stores, access to database state, service-to-service permissions, API access, secret handling, and what information appeared in logs. For example, the ingestion function should not have unlimited access to every data store. A dashboard should not need raw sensitive records if aggregated metrics are enough. A training job should access admitted datasets through controlled storage paths rather than grabbing ungoverned data. The decisioning service should have the minimum permissions needed to read features and write decisions.

I also had to think about access control at the data-product level. The platform had different kinds of data: raw events, cleaned events, feature records, decisions, cases, labels, monitoring metrics and evaluation outputs. These were not all the same sensitivity or purpose. A case reviewer needs different access from a model evaluator. A monitoring dashboard may only need aggregates. A model training process may need historical labelled data, but only after it has passed admission and quality checks. That is the same logic behind proper data platform design: access should be based on role, purpose and risk.

Another major part of deployment was testing after release. I learned quickly that code working locally is not enough. After deployment, I needed to confirm that the deployed environment behaved correctly. That meant checking whether API Gateway accepted requests, whether Lambda handled validation and deduplication, whether messages reached MSK, whether schema expectations held, whether services running on EKS consumed and produced the right records, whether Aurora state was updated, whether S3 evidence was written, whether CloudWatch logs appeared, and whether dashboards reflected the underlying data.

I also had to test data transformations. A deployed transformation job can run successfully and still produce bad data if the input changed or the mapping logic no longer applies. So I used checks around record counts, missing fields, duplicate identifiers, invalid timestamps, category mapping, failed joins, unexpected null values, and reconciliation between input and output layers. When output metrics changed sharply, I did not assume the business reality had changed. I checked whether the data flow had changed, whether a scheduled job failed, whether a field became missing, or whether a rule or threshold had changed.

One concrete example is the flag rate in the fraud platform. If the flag rate rose sharply, a simple interpretation would be that risk increased. But there were other possible explanations: event volume changed, the data feed included a new category, a validation issue caused a rule to fire more often, a threshold changed, or the score distribution shifted. So the monitoring layer had to show not only flagged cases, but also total processed events, validation failures, reason codes, score distribution and threshold effects. That is a deployment and cloud operations lesson: live metrics must be interpreted with knowledge of the pipeline that created them.

Scheduling was also part of my deployment experience. The platform needed repeated jobs, not just interactive runs. There were jobs for data refreshes, validation checks, feature generation, batch scoring, offline evaluation, dashboard updates and evidence generation. Scheduling those jobs meant thinking about timing, dependencies, outputs, logging and failure. If a feature-refresh job failed, the scoring service might still run but use stale data. If an evaluation job failed, I might not detect model performance issues. If a dashboard refresh failed, a user might see old information. So scheduling and monitoring jobs were part of making the platform production-ready.

CloudWatch was important here because it gave me logs, metrics and alarms. I used it to see function logs, service logs, error patterns, latency, event counts, alarm state and dashboard views. For me, CloudWatch became the operational window into the platform. It helped answer questions like: are events arriving, are services running, are validation failures increasing, are alarms firing, are costs rising, and are scheduled jobs producing evidence?

Cost was another part of cloud architecture. Running on AWS creates real cost. A local project does not teach that in the same way. I had to think about what services were running, which components needed to stay live, which workloads could be scheduled, and how to monitor cost posture. Budgets and cost dashboards helped make the platform more responsible. In an organisation like HMRC, cost control matters because cloud resources must support business value rather than silently expanding.

Another part of the architecture was evidence and traceability. I designed the platform so that runs, decisions, cases, labels, dataset-quality checks, model training results and promotion or rollback evidence could be stored. That mattered because if a decision was challenged later, I needed to know what data, configuration, model bundle or rule set contributed to it. If an evaluation result changed, I needed to know whether the source data changed, the transformation changed, the model changed, or the threshold changed. That is why I treated evidence storage and lineage as part of deployment, not as optional documentation.

The learning part of the platform also gave me deployment experience. I had to think about how runtime evidence became admitted learning data. I could not simply train on everything. There needed to be a dataset admission boundary, a quality gate, leakage checks and lineage. If the model learns from future data or from labels that were not mature at the time, the evaluation becomes misleading. I used the learning layer to build offline feature bases, check data quality, train models, evaluate them, log lineage and publish active model bundles. That connects deployment to machine learning operations. A model deployment is not complete unless there is a way to evaluate it, track it, and roll it back or replace it if necessary.

When I say I deployed the platform into production, I mean it was not only code sitting in a repository. It was running in a cloud environment with real cloud resources, service boundaries, scheduled jobs, monitoring dashboards, logs, alarms, access controls and evidence outputs. It had live ingress capability, runtime services, state storage, object storage, training workflows and monitoring. I could observe whether it was working. I could trace outputs. I could see failures. I could manage active configuration. I could reason about deployment risk.

This experience changed my understanding of production. Before building the platform, I might have thought production meant code is live. Now I see production as a set of operational promises. It means the service can run repeatedly. It means failures can be detected. It means data quality is monitored. It means access is controlled. It means outputs can be traced. It means changes are versioned. It means there is documentation. It means users can understand what the output means. It means someone can ask, "What happened?" and the platform can provide evidence rather than guesses.

Version control was part of this. I used Git and GitHub to manage code changes and keep the platform development controlled. Version control allowed me to track changes to services, transformations, configuration, model evaluation logic and dashboard definitions. In platform work, this matters because a small change can alter outputs. If a threshold changes, a rule changes, or a feature definition changes, the resulting decisions and metrics may change. Without version control, I would not be able to explain why the platform behaved differently between runs.

The command line and integrated development environments were part of the working routine. I used the command line for repository work, running scripts, managing environments, checking dependencies, interacting with cloud tooling and launching local or deployment-related commands. I used an integrated development environment to work on Python services, scripts, configuration and tests. Notebooks were useful for exploration and model investigation, but the deployed platform required code that could run as services and jobs. That pushed me to write more modular, maintainable code.

Security also included input handling. An API receiving events should not trust the input blindly. I built validation around event shape, expected fields, timestamps, duplicates and category values. That protects downstream systems from malformed data. It is also part of accessibility and usability because users should not see confusing outputs caused by bad inputs. If an event fails validation, the system should make that failure visible rather than quietly producing a wrong decision.

In relation to data protection, my understanding is that systems should only collect, process and expose data for a clear purpose; access should be limited; sensitive values should be protected; outputs should be minimised where possible; and users should understand what data they are seeing. In the platform, I applied those principles by separating raw data from analytical and dashboard outputs, limiting access paths, using aggregated monitoring where detailed records were not needed, keeping secrets out of code, and making data-quality issues visible.

I also understand that deployment risk is not only technical. There is user risk and decision risk. If a dashboard labels something poorly, users may misread it. If a risk score appears without reason codes, reviewers may not understand it. If a model metric hides minority-class failure, the platform may look better than it is. If missing data is treated as a true zero, the dashboard may create false reassurance. I considered those risks in the platform by using reason codes, status fields, validation flags, false-positive analysis, false-negative analysis and clear separation between data-quality issues and behavioural-risk signals.

If I compare this to HMRC's role, I see a strong connection. The role is about helping data scientists and engineers use a data analytics platform effectively, identifying and deploying platform capabilities, scheduling and monitoring jobs, overseeing deployed applications and APIs, controlling access to datasets, managing data virtualisation layers, documenting integration processes, and ensuring performant access to data. My platform experience covered those same areas in an independent environment: I created data flows, deployed services, scheduled jobs, monitored outputs, managed access, created logical data layers, documented processes, and operated cloud infrastructure.

I would be honest that I have not worked inside HMRC's platform, and I would need to learn the specific governance, tooling and data estate. But the concepts are not new to me. I understand why a data platform needs clear data layers, governed access, monitored jobs, deployment controls, testing, versioning, documentation and cloud observability. I have built those concepts into my own platform.

One of the biggest lessons from the platform is that cloud architecture should serve the data product, not the other way around. It is easy to list cloud services. But the reason for using them must be clear. API Gateway existed to control ingress. Lambda existed to validate and publish events. MSK existed to move event streams. EKS existed to run platform services. Aurora existed for runtime state. S3 existed for object and evidence storage. CloudWatch existed for observability. Databricks and SageMaker existed for learning and evaluation. IAM existed to control identity and access. Each service had a role in the data product.

Another lesson is that architecture must support change. A platform is not static. New data feeds may arrive. Rules may change. Models may be retrained. Dashboards may need new metrics. Access requirements may change. Regulations may require tighter controls. If the architecture is tangled, every change becomes risky. By separating layers and responsibilities, I made it easier to change one component without losing control of the whole system.

I also learned that deployment requires humility. A system can fail in ways you did not expect. A job can run but produce incomplete output. A dashboard can look normal while showing stale data. A model can perform well in evaluation but create too many review cases. A data feed can change shape without warning. Cloud costs can rise if resources are not managed. That is why monitoring, logs, alarms, documentation and testing matter. They are not bureaucracy. They are what make a platform trustworthy.

If I were explaining this in a concise interview answer, I would say:

My understanding of deployment is taking tested code, models, data transformations or applications from development into a controlled live environment where they can run repeatedly, securely and observably. My understanding of cloud architecture is designing the compute, storage, networking, identity, monitoring, data movement and governance layers that allow deployed systems to run safely and effectively. I have technical experience in both through my AWS-hosted fraud and transaction decisioning platform, where I deployed Python services, SQL and SAS transformation workflows, scheduled jobs, monitoring dashboards, data validation, case-management outputs, model evaluation and access controls. I used AWS services including API Gateway, Lambda, MSK Serverless, EKS, Aurora PostgreSQL, S3, SSM Parameter Store, CloudWatch, Databricks, SageMaker, MLflow, IAM roles and cost dashboards. The platform taught me how to move from local code into a deployed data and machine learning system with security, testing, observability, documentation and operational risk management.

But the fuller answer is that I now see deployment and cloud architecture as disciplines of trust. They are about making sure data products can be used safely, not just built impressively. A deployed platform must answer: is the data valid, is access controlled, are jobs running, are outputs fresh, are models behaving, are failures visible, are changes traceable, are users protected from misleading outputs, and can the system be improved without losing control? That is the understanding and technical experience I would bring to this role.

### Extraction Notes

- Directly supports desirable criterion: understanding of cloud architecture.
- Also supports:
  - Essential criterion 1: prototype-to-production code and version control.
  - Essential criterion 4: testing, deployment risk and documentation.
  - Data Engineering technical skill.
  - Data development process technical skill.
  - Platform duties around deployed applications/APIs, scheduling, monitoring and access control.
- Strong application phrases:
  - "deployment is not just uploading code; it is packaging, configuration, permissions, testing, monitoring and repeatable operation."
  - "production as a set of operational promises: repeatability, observability, access control, traceability, versioning and documentation."
  - "cloud architecture should serve the data product, not the other way around."
  - "API Gateway for controlled ingress; Lambda for validation and publishing; MSK for event transport; EKS for platform services; Aurora for runtime state; S3 for object/evidence storage; CloudWatch for observability; IAM for identity and access."
  - "monitored both the business output and the health of the data flow."
- Risk adjustment:
  - Keep this framed as independent AWS-hosted platform experience, not employer production ownership.
  - If used in the 250-word desirable criteria section, avoid overloading with a long AWS service list unless space permits.
  - "Databricks, SageMaker and MLflow" should be retained only where supported by the actual platform evidence and not over-expanded into expert-level claims unless later evidence supports it.
  - Avoid implying formal enterprise cloud architect responsibility; frame as practical cloud architecture experience from building and operating the platform.

## Evidence Item 6 - Fundamentals of Data Protection Regulations

Captured: 2026-05-22 18:52:29 +01:00

### Question

What's your understanding of fundamentals of data protection regulations?

### Response

My understanding is that data protection is about making sure personal data is collected, processed, shared, stored and deleted in a lawful, fair, secure and proportionate way. It is not just "keep data private." It is about designing the whole data process so that people's information is only used for a clear purpose, only accessed by the right people, protected from misuse, and not retained or exposed unnecessarily.

In the UK, I understand the main framework as UK GDPR, supported by the Data Protection Act 2018 and ICO guidance. The core UK GDPR principles are lawfulness, fairness and transparency; purpose limitation; data minimisation; accuracy; storage limitation; integrity and confidentiality; and accountability. Those principles should sit at the centre of how personal data is processed.

Practically, I understand this as several responsibilities.

First, there must be a lawful basis for processing personal data. The ICO guidance says organisations must identify a valid lawful basis before using personal information and document it. The lawful basis depends on the purpose and relationship with the individual, and for public authorities it may often involve public task or legal obligation depending on the function being carried out.

Second, data should be used for a clear purpose. If the data was collected for one reason, it should not casually be reused for another without checking whether that new use is compatible and lawful. In a data science or platform environment, this matters because it is tempting to reuse datasets just because they are available. My understanding is that availability does not equal permission.

Third, data should be minimised. A model, dashboard, API or reporting layer should not expose raw personal data if aggregated, pseudonymised, masked or restricted fields are enough. For example, a monitoring dashboard may need counts, error rates, case volumes and quality indicators, but not the full personal record behind every transaction.

Fourth, data should be accurate and kept up to date. In analytics, inaccurate data can harm both privacy and decision-making. A wrong status, stale field, duplicate record or mismatched identifier can lead to incorrect outputs. That is why validation, reconciliation, data-quality checks and clear definitions are part of responsible data protection, not separate from it.

Fifth, data should be kept only for as long as needed. For a platform, this means thinking about retention for raw events, curated datasets, model-training data, logs, case records and evaluation evidence. Logs are especially important: they are useful for debugging and audit, but they should not unnecessarily expose sensitive values.

Sixth, there must be appropriate security. My practical understanding includes access control, least privilege, separation between raw and transformed data, secrets management, encryption where appropriate, auditability, monitoring, and making sure credentials are not hard-coded into code or notebooks. In my platform work, this meant separating access to raw events, feature datasets, case outputs, dashboards and evaluation data so that users or services only saw what they needed.

Seventh, there is accountability. It is not enough to say the system is compliant; the organisation must be able to demonstrate what it did and why. For me, that means documentation: data-flow diagrams, data dictionaries, processing purpose, access decisions, test evidence, validation checks, deployment notes, model limitations, and risk decisions.

I also understand that some data needs extra care. Special category data and criminal offence data require more than just a standard lawful basis; they need additional conditions for processing. In a government context, this matters because data may be sensitive, high-impact, or linked to statutory functions.

For HMRC specifically, my understanding is that data protection would be especially important because the organisation handles sensitive information about individuals, businesses, tax, payments and compliance. In a data and machine learning engineering role, I would think about data protection at every stage: ingestion, transformation, virtualisation, access, modelling, dashboards, APIs, testing, deployment and monitoring.

In practical terms, I would apply it like this:

- Use only the data needed for the defined analytical or operational purpose.
- Separate raw data from curated analytical data.
- Restrict access through role-based permissions and least-privilege principles.
- Avoid exposing personal fields in dashboards where aggregate measures are enough.
- Keep credentials and secrets out of code.
- Document data lineage, definitions, assumptions and known limitations.
- Validate outputs so incorrect or stale data is not presented as fact.
- Treat logs carefully so they support debugging without leaking sensitive information.
- Make sure deployed applications and APIs expose only the data required for their purpose.
- Raise concerns if a proposed reuse of data appears outside the original purpose or carries avoidable risk.

My platform experience helped me understand this in a practical way. In the fraud decisioning platform, different layers had different sensitivity: raw transaction events, transformed features, decision outputs, case records, monitoring dashboards and evaluation datasets. I could not treat all of them the same. A case reviewer needed case-level information and reason codes. A monitoring dashboard often only needed aggregate volumes, validation failures and trends. A model evaluation process needed historical labelled data, but through controlled and documented access. That taught me to think about privacy by design rather than treating data protection as a final compliance check.

So my understanding of data protection fundamentals is: know the purpose, identify the lawful basis, minimise the data, control access, keep it accurate, secure it properly, retain it only as needed, document decisions, and make sure people using the data understand its limits. In a role like this, I would not see data protection as a barrier to analytics; I would see it as part of building trustworthy analytics and machine learning systems.

### Sources

- ICO: A guide to the data protection principles - https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/data-protection-principles/a-guide-to-the-data-protection-principles/
- ICO: A guide to lawful basis - https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/a-guide-to-lawful-basis/

### Extraction Notes

- Directly supports desirable criterion: understanding of fundamentals of data protection regulations.
- Also supports platform duties around GDPR compliance, deployed applications/APIs, access control and dataset monitoring.
- Strong application phrases:
  - "availability does not equal permission"
  - "privacy by design rather than a final compliance check"
  - "separated raw transaction events, transformed features, decision outputs, case records, monitoring dashboards and evaluation datasets"
  - "use only the data needed, control access, keep it accurate, secure it, retain it only as needed, and document decisions"
- Risk adjustment:
  - Do not imply formal legal/data protection officer responsibility.
  - Keep this as fundamentals and practical application through platform design.
  - If used in the 250-word desirable criteria section, compress heavily and focus on UK GDPR principles plus platform application.

## Evidence Item 7 - Reusable Data Layers and Data Virtualisation Thinking

Captured: 2026-05-22 19:05:28 +01:00

### Question

Alright Eric, can you explain, in plain terms, how you created or managed reusable data layers so analysts, data scientists, dashboards, applications or services could use trusted data without going directly to raw sources every time?

### Response

When I hear "data virtualisation layer" or "reusable data layer," I understand it as a way of giving analysts, data scientists, dashboards, applications or services access to the data they need without forcing them to go directly into raw source systems every time. The goal is not just convenience. It is about trust, performance, governance and consistency.

If every analyst touches the raw data directly, different people may clean it differently, define fields differently, join tables differently, apply filters differently, or accidentally use data that should not be exposed. That creates inconsistent outputs. One dashboard says one number, another notebook says a different number, and nobody can easily explain which one is right. A reusable curated layer reduces that risk. It gives people an agreed place to work from: cleaned data, defined fields, tested transformations, access controls, documented assumptions and a stable interface.

That was the principle I applied in my platform work. I did not want the platform to be one large system where every component could read every raw table and make its own interpretation. I wanted to separate the platform into layers so that each service, dashboard or analytical process accessed the right version of the data for its purpose.

The easiest way to explain it is this: I created layers between the raw data and the final users.

Raw events entered the platform first. These were transaction or event records. At that stage, the data was not yet safe for decisioning or reporting. It might contain missing fields, duplicate event IDs, invalid timestamps, unexpected categories or values that needed to be checked. So I did not expose that raw layer directly to dashboards or scoring services as if it were already trusted.

The first reusable layer was the validated event layer. This layer held events that had passed basic checks: required fields present, timestamp usable, event ID valid, no obvious duplicate, category understood, and no impossible values. Events that failed those checks were not silently pushed through. They were separated into a data-quality route so the platform could show that something was wrong with the input. That mattered because a dashboard showing fewer events should not automatically be interpreted as lower activity if the real issue was failed validation.

The next layer was the context layer. A transaction event by itself is not enough to support good decisioning. The platform needed to understand the event in context: what account or entity it related to, whether it matched known identifiers, what previous behaviour existed, and how the current event fitted into a wider sequence. In the platform, this meant creating context projections such as arrival events, arrival entities and fraud-flow anchors. In plain terms, I created cleaned and organised representations of the incoming event so downstream services did not have to keep reinterpreting the raw event every time.

That is one of the key reasons reusable layers are valuable. If every service had to parse the raw event, resolve the entity, interpret the timestamp, check the category and rebuild the same context, the platform would become slow and inconsistent. By creating a context layer, later services could work from a more stable view of the event.

The next reusable layer was the entity and graph resolution layer. In fraud decisioning, the same person, account, device, merchant or transaction pattern may appear across different records. The platform needed a way to resolve those relationships so that features and decisions were not built from isolated events. This layer helped create a more reliable view of the entity behind the event. Again, downstream services did not need to touch the raw source and work out relationships from scratch. They could use the resolved view.

After that came the online feature layer. This was one of the most important curated layers. A feature layer is a place where raw and contextual data is transformed into variables that a model, rule engine, dashboard or evaluation process can use. For example, instead of exposing every previous transaction to a decision service, the feature layer could provide calculated fields such as recent transaction count, amount compared with normal behaviour, time since previous activity, unusual activity indicators, category change, repeated attempts, or other risk signals.

That helped performance because the decision service did not need to do heavy calculations from raw history every time an event arrived. It also helped consistency because the feature definition lived in one controlled place. If "recent transaction count" means the previous hour, or previous day, or previous five events, that definition should not change depending on which service is using it. The feature layer made that definition reusable.

This is where I see the connection to data virtualisation. In an enterprise setting, a tool like Denodo may provide governed access to data across several underlying systems without users needing to know exactly where each source sits. In my platform, I built the same practical concept through curated layers, APIs, topics, tables and dashboard sources. A downstream service did not need raw access to every underlying source. It accessed the agreed layer for its task.

I also created a decision layer. This layer stored the outcome of the rule and model decisioning process. It included the event identity, score, decision, reason codes, policy or model bundle used, and relevant status information. This mattered because a decision is not just a number. If the platform flags a case, someone needs to know why. Was it flagged because of unusual behaviour, repeated attempts, high velocity, a missing field, a threshold breach, a model score, or a rule? So the decision layer became a reusable product for case management, dashboards, monitoring and later evaluation.

Without that layer, every consumer would have to reconstruct the decision from raw model logs or rule outputs. That would be inefficient and risky. By creating a decision layer, I gave the platform a stable truth for "what decision was made and why."

The next reusable layer was the case layer. Not every event needed to become a case. The case layer was created when something was review-worthy. It carried case ID, event reference, reason code, risk score, status, timeline, review action and later outcome. That layer was separate from the decision layer because a decision is not the same as a case. A decision might say "flag," but the case layer tracks the human or operational workflow around that flag.

That separation helped avoid confusion. A dashboard looking at decision volume could use the decision layer. A reviewer looking at open cases could use the case layer. A model evaluator looking at final outcomes could use the label or evaluation layer. Each user or service accessed the layer that matched the question.

The label layer was another important one. In a fraud platform, labels are not always available immediately. A transaction may be flagged today but only confirmed later. If I let the model learn from immature or uncertain labels, the evaluation would become unreliable. So I separated candidate labels from authoritative labels. I treated label maturity as a boundary. Only labels that were admissible and mature enough were used for learning and evaluation. That layer supported the offline learning process without forcing the training workflow to touch raw case notes directly.

Then there was the offline feature and learning layer. This was different from the online feature layer. The online feature layer supported real-time or near-real-time decisioning. The offline layer supported training, evaluation and model improvement. It had to respect time order. The model should not learn from future information. So I created a learning pipeline where runtime decision evidence, case evidence and label truth could be admitted into training datasets only after checks. This included dataset admission, feature basis creation, quality checks, leakage checks, model training, experiment tracking and promotion or rollback evidence.

This was another example of reusable data layers. The training process should not rebuild its world by grabbing raw events, raw decisions and raw case records without control. It should use admitted datasets, controlled feature bases and documented evaluation outputs. That makes the learning process safer and more reproducible.

I also created monitoring and evidence layers. These were not just dashboards. They were part of the platform's trust system. They showed whether events were arriving, whether validation failures were rising, whether decisions were being produced, whether scheduled jobs had run, whether score distributions changed, whether case volumes looked normal, and whether model or rule performance shifted. These layers allowed users and operators to inspect the state of the platform without querying raw tables directly.

For example, if flagged cases suddenly fell to zero, a user looking only at the final case dashboard might think risk had dropped. But the monitoring layer would help ask better questions: did ingestion stop, did validation failures increase, did a scheduled job fail, did a rule stop firing, did the score distribution change, or did a data feed change shape? That is why curated monitoring layers are important. They protect users from shallow interpretation.

In practical terms, the reusable layers were exposed through a combination of database tables, views, APIs, event topics, object storage outputs and dashboards. The exact method depended on the layer. Some outputs needed to be consumed by services. Some needed to be queried by analysis workflows. Some needed to be shown in dashboards. Some needed to be stored as evidence. The important thing was that the raw source was not the main interface for everyone. The platform provided controlled interfaces.

For analysts or data scientists, this meant they could start from a curated feature basis, decision table, evaluation dataset or monitoring output rather than raw event logs. For dashboards, it meant visualisations could read from stable summary tables or monitoring layers rather than recalculate everything from raw events. For services, it meant decisioning services could consume validated and contextualised data rather than raw and untrusted inputs. For operators, it meant monitoring dashboards showed the health of the system without requiring direct access to sensitive raw data.

Performance was a major reason for this design. Immediate and performant access does not happen if every request has to scan raw event history and rebuild features from scratch. By materialising certain layers, caching active handles, separating online and offline paths, and creating purpose-specific outputs, the platform could serve different users more efficiently. A decision service needed fast access to online features. A dashboard needed aggregated metrics. An offline training job needed larger historical datasets but could run in a batch process. Those are different access patterns, so they needed different layers.

Governance was another reason. If raw data contains sensitive or unnecessary fields, not every user should see it. The curated layer can remove fields that are not needed, aggregate values where record-level detail is unnecessary, and expose only the columns required for a task. A case reviewer may need transaction context and reason code, but not every raw attribute. A monitoring dashboard may need counts, rates and validation failures, but not full customer-level data. A model training job may need historical features and labels, but through an admitted and documented dataset. Data virtualisation is not just about speed; it is about controlled access.

Testing was built around the layers. I tested whether data moved correctly from raw to validated, from validated to context, from context to features, from features to decisions, from decisions to cases, and from cases and labels to learning datasets. I checked row counts, missing fields, duplicate IDs, schema expectations, invalid timestamps, unexpected categories, failed joins and output reconciliation. If a downstream layer showed fewer records than expected, I needed to know whether that was correct filtering or an error.

I also tested meaning, not only structure. For example, if a validation layer rejected many records, I needed to know whether the input feed changed or whether the validation rule was too strict. If a feature value changed sharply, I needed to know whether behaviour changed or whether upstream context changed. If the decision layer produced many more flags, I needed to know whether risk increased, thresholds changed, data quality changed, or a rule became too sensitive. So the reusable layers were tested both technically and analytically.

Documentation was essential. A reusable layer is only useful if people know what it means. I documented what each layer was for, what it contained, what it did not contain, where it came from, what transformations were applied, what checks were performed, and what downstream users should be careful about. For example, the decision layer should not be interpreted as confirmed fraud. It is a decision output or review trigger. The label layer should only include matured outcomes. The monitoring layer should show platform health and data-quality context. These definitions matter because the same term can be misunderstood if not documented.

This is where my South Western experience helped me. At South Western, I learned that "completed" could mean different things to different teams. In the platform, I applied the same lesson to data layers. A "flag," a "case," a "label," a "decision," and an "outcome" are not the same thing. If those terms are not separated, the whole platform becomes confusing. So I created separate layers and definitions to avoid that confusion.

Access control also followed the layer structure. Raw data access was restricted. Curated datasets were exposed based on purpose. Services accessed what they needed. Dashboards read from appropriate outputs. Case-level data was separated from aggregate monitoring. Secrets and configuration were not embedded in the code. Access paths were documented. That helped reduce the risk of exposing the wrong information to the wrong process or user.

A concrete example is the dashboard layer. The dashboard did not need to show all raw event fields. It needed to show event volume, validation failure counts, flag rate, reason codes, case status, rule triggers, score distribution and threshold effects. Those metrics came from curated monitoring and decision layers. This meant the dashboard could answer operational questions without exposing unnecessary raw data. It also meant the dashboard was easier to trust because the metrics were based on tested layers rather than ad hoc queries.

Another concrete example is the offline evaluation layer. I did not want evaluation to pull directly from raw event logs and raw case notes every time. I created an admitted learning dataset that combined decision evidence, case timeline evidence and mature labels after checks. That made evaluation more reproducible. It also reduced leakage risk because the dataset was built with time and maturity rules in mind.

Another example is the feature layer. The decisioning service did not need all transaction history. It needed current, decision-time features. By materialising those features in a controlled layer, I reduced repeated computation and reduced the risk that the service would accidentally use the wrong lookback period or future data. That is exactly the kind of reusable product that helps data scientists and services work faster.

When I think about HMRC's mention of immediate and performant access for data scientists, this is what I understand. Data scientists should not have to spend most of their time reconstructing the same joins, filters and cleaning logic. They should have access to trusted, documented, performant layers that let them focus on analysis, modelling and business problems. But those layers must still preserve lineage and governance. Fast access without control creates risk. Control without usability slows delivery. The balance is the point of the role.

I did not use Denodo directly. I would be honest about that. But I understand what the capability is meant to achieve because I implemented equivalent principles in my own platform: abstraction over raw sources, governed access, curated outputs, reusable data products, performance-aware design, documentation and lineage. If I joined HMRC, I would need to learn Denodo specifically, but the reasoning behind data virtualisation is familiar to me.

I also worked with Oracle at South Western, where structured operational data had to be extracted and reconciled with other team-held sources. That gave me experience with the enterprise data side: formal source records, stable identifiers, reference fields, status fields and the need to map system records against operational reality. My platform then extended that thinking into cloud services, event feeds, feature layers, APIs and monitoring outputs.

The biggest lesson I learned is that raw data is not a good interface for most users. Raw data is necessary, but it is not where most people should work. It is too detailed, too easy to misinterpret and often too sensitive. A well-designed data layer gives people the version of the data that fits their need: clean enough to trust, documented enough to understand, restricted enough to be safe, and performant enough to use.

If I were to summarise my experience in one example, I would say: in my fraud and transaction decisioning platform, I created a set of reusable data layers that separated raw events, validated events, context projections, entity resolution, online features, decisions, cases, labels, offline learning datasets, monitoring outputs and evidence. These layers allowed services, dashboards and analysis workflows to use curated data without directly touching raw sources. I tested the layers through validation checks, reconciliation, schema expectations, row counts, quality gates and analytical review. I documented the purpose and limitations of each layer, controlled access based on role and purpose, and designed the layers so downstream users could get immediate and reliable access to the data they needed.

That is my practical understanding of data virtualisation and reusable data layers: create a governed bridge between raw source systems and the people or services that need to use data. Make it easier to access the right data, but harder to misuse the wrong data. Make outputs fast enough for operational use, but traceable enough to defend. Make the data reusable, but not ambiguous. That is the approach I would bring into HMRC.

### Extraction Notes

- Directly supports the HMRC duty: responsibility for creating and managing data virtualisation layers to support data exploitation and analytics.
- Also supports:
  - Data Engineering technical skill.
  - Data development process technical skill.
  - Access control and data protection fundamentals.
  - Scheduling/monitoring and platform performance.
- Strong application phrases:
  - "raw data is necessary, but it is not where most people should work."
  - "a governed bridge between raw source systems and the people or services that need to use data."
  - "clean enough to trust, documented enough to understand, restricted enough to be safe, and performant enough to use."
  - "separated raw events, validated events, context projections, entity resolution, online features, decisions, cases, labels, offline learning datasets, monitoring outputs and evidence."
  - "fast access without control creates risk; control without usability slows delivery."
- Risk adjustment:
  - Explicitly state no direct Denodo experience, but equivalent principles through curated layers, APIs, topics, tables and dashboards.
  - Avoid implying official enterprise data virtualisation ownership in employment; position the strongest example as independent platform work.
  - Use South Western Oracle experience as supporting enterprise-data context, not as the main data virtualisation example.
