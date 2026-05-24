# Department for Education - Senior Data Analyst (G7) Interview Evidence Context

These are raw evidence narratives, written as if Eric is recalling real situations. They are not final supporting-statement wording yet. The purpose is to give concrete stories that can be compressed later into a 750-word DfE statement, especially because DfE may sift on the first three essentials: analysis, synthesis and modelling; data visualisation and communication; and technical knowledge.

## 1. Platform Story: Setting Analytical Direction, Not Just Building a Model

One of the strongest examples I would use is the fraud and transaction decisioning platform, because that was where I had to stop thinking like someone completing a technical project and start thinking like someone designing an analytical product.

At the beginning, the project could easily have become a normal data science exercise: take transaction records, create a few features, train or test a model, show an accuracy score and produce a dashboard. That would have been technically interesting, but it would not have solved the real problem. The real problem was not "can I score a transaction?" The real problem was "can I build an analytical workflow where incoming events are checked, scored, explained, turned into reviewable cases, monitored over time and improved when the data changes?"

That distinction changed how I approached the work. I realised that a risk score on its own would not be enough for a user. A score does not explain whether the data was complete, whether the case should be reviewed, what triggered the flag, whether similar cases were increasing, or whether the model was behaving differently from previous runs. So I set the analytical direction around the full decision journey, not the model in isolation.

The structure I designed was: event ingestion, validation, feature creation, rule and model decisioning, case creation, monitoring and offline evaluation. Each part had a purpose. The ingestion layer answered whether data was arriving. The validation layer answered whether the data was usable. The feature layer turned raw records into decision-ready variables. The decision layer produced scores, decisions and reason codes. The case layer turned decisions into something a reviewer could act on. The monitoring layer showed whether the platform was behaving sensibly. The offline evaluation layer checked false positives, false negatives, thresholds and model behaviour.

That was the moment the work became more strategic. Instead of asking "which model is best?", I started asking "which analytical outputs does the user need to make a safe decision?" That led me to prioritise reason codes, data-quality flags and monitoring views alongside model metrics. For example, if a transaction was flagged, the user needed to know whether it was because of unusual amount, high transaction velocity, repeated attempts, unusual timing, a missing field, or a score crossing a threshold. If the flag rate changed, the user needed to know whether activity genuinely changed or whether the data feed, validation logic or threshold had changed.

I also had to prioritise what mattered. There were many things I could have built: a more complex model, more features, more dashboards, more automation. But the most important things were reliability, interpretability and usefulness. A slightly more complex model would not help if the inputs were invalid or the output could not be explained. So I gave priority to validation checks, clear feature definitions, decision reason codes, case status and monitoring. That was an analytical leadership decision: choosing the work that made the product more trustworthy, not just more impressive.

This is the story I would use to show analysis, synthesis and modelling at a senior level. I synthesised the problem across data, model, user workflow and operational review. I designed the analytical model around the decision journey. I moved from raw transaction data to decision-ready features, then to reviewable cases and evaluation outputs. I also built the platform so that the analysis could be monitored and improved, rather than being a one-off result.

The lesson I took from it was that good data analysis does not stop when the model works. It has to connect to the user journey, the decision being made, the quality of the source data, and the ability to explain what the output means. That is directly relevant to a role like DfE Senior Data Analyst, where the question is not only whether an analyst can write SQL or produce a dashboard, but whether they can shape analytical work across services and policy problems so that data leads to better decisions.

## 2. Platform Story: Designing Feature and Decision Layers as Analytical Data Models

A more technical version of the platform story is about how I designed the feature and decision layers. This is the example I would use if I needed to show analytical data modelling, SQL thinking and reusable data products.

The early version of the platform used a fairly direct scoring approach. It could take transaction-like records and apply rules or model scores. But I quickly realised that raw fields were not enough. A transaction amount by itself is not meaningful without context. A GBP500 transaction may be normal for one account and unusual for another. A transaction at 2am may be normal in one pattern and suspicious in another. Five transactions in a short period may be expected for some users but unusual for others.

So I designed the feature layer to translate raw events into behaviour-based measures. I thought about features that answered specific analytical questions: how recent was the previous activity, how many events happened in a recent time window, how large was the current amount compared with normal behaviour, whether the category was unusual, whether there were repeated attempts, and whether the current pattern differed from the account's recent history. These were not random variables added for technical interest. They were designed around the question: "What would make a transaction worth looking at?"

The other important design decision was time. I had to make sure features only used information available at the point of decision. If a model uses future information, the evaluation can look strong but become useless in a real decision setting. So the feature layer had to respect decision time. For example, if a transaction was being scored at a certain timestamp, the features could only use previous transactions or context available before that timestamp. This made the data model more defensible.

I separated raw events, validated events, features, decision outputs, case records and evaluation outputs. That separation mattered. Raw events preserved the original input. Validated events represented records fit for processing. Features represented calculated variables for scoring. Decision outputs contained scores, decisions and reason codes. Case records contained workflow status. Evaluation outputs compared decisions against later outcomes. If all of those were mixed into one table or one notebook, it would be difficult to test, explain or reuse.

The decision layer was also important. I did not want the output to be only "risk score equals 0.82." I wanted the decision layer to show what happened and why. So I included the score, decision category, reason code, decision timestamp, applied threshold and relevant signals. That made the output usable for dashboards, case review and offline analysis. It also meant the same decision table could be used in several ways: monitoring flag rates, creating cases, evaluating false positives and explaining individual decisions.

This is where the technical and analytical sides met. SQL and transformation logic were not just for moving data. They were used to create a reliable analytical structure. The data model had to support multiple users: the scoring process, the dashboard, the case view and the evaluation process. If the feature definitions were unclear or inconsistent, the whole system would be weak.

I also used validation checks around the layer boundaries. For example, if raw events entered the platform but fewer validated events appeared than expected, I needed to know whether records were correctly rejected or whether the validation logic was too strict. If a feature changed sharply, I needed to know whether user behaviour changed or an upstream field changed. If a decision output was missing a reason code, the case view would become harder to interpret. These checks made the data model safer.

This example would help DfE because the role asks for designing analytical data models and using SQL to extract and transform data. The story shows that I can design a model around decision needs, not just table structure. It also shows that I can connect user journeys to data journeys: an event arrives, is checked, becomes a feature, becomes a decision, becomes a case, becomes evaluation evidence. That is very close to the kind of thinking needed when mapping analytics data across digital services and identifying gaps in underlying data structures.

## 3. Platform Story: Building Dashboard Standards for Monitoring and Decision Support

Another important platform story is the dashboard and monitoring layer. This is the one I would use for data visualisation, communication and setting standards.

The first dashboard idea was simple: show event volumes, scores, flags and cases. But once I tested that against the actual decision problem, I saw the weakness. A dashboard that only shows headline numbers can easily mislead people. If flagged cases go down, the user may think risk has reduced. But it may actually mean the data feed failed, validation rejected more records, a rule stopped firing, or the threshold changed. If flagged cases go up, the user may think risk increased. But it could mean a new category entered the data, a validation rule changed, or the threshold was too sensitive.

So I changed the dashboard standard. I designed it around three layers: headline, diagnostic and evidence.

The headline layer answered the basic question: what is happening? It showed event volume, number of flagged cases, open cases, reviewed cases, validation failures, and decision categories. This was the part a non-technical user could read quickly.

The diagnostic layer answered the next question: why might this be happening? It showed reason codes, rule triggers, score distributions, validation failure categories, threshold effects and trend movement over time. If the flag rate changed, the user could see whether one reason code or validation issue was driving it.

The evidence layer answered: can we trust this output? It allowed the user to trace dashboard measures back to the decision or case data, see whether the input data had changed, and understand whether the dashboard was based on complete, fresh and validated data.

That became my working standard for useful dashboards: do not just show a number; show enough context for the number to be interpreted safely. I applied that principle to dashboard labels, reason codes, data-quality flags and notes. I separated behavioural-risk flags from data-quality flags because they should not lead to the same conclusion. A case flagged because of missing information is not the same as a case flagged because the behaviour is suspicious.

I also thought about audiences. A technical user may want feature distributions, validation errors, score bands and false-positive patterns. A non-technical user may want to know which cases need attention and why. A senior stakeholder may want to know whether the system is stable, whether review workload is manageable and whether the output supports decisions. So the dashboard needed to move from summary to drill-down without overwhelming the user.

One example was threshold monitoring. If the threshold was too low, the system could create too many review cases. If it was too high, it could miss important cases. So the dashboard needed to show flag volume, precision, recall, false positives, false negatives and review load. This allowed the threshold conversation to become evidence-based. It was not simply "the model score looks good." It was "this threshold creates this level of review burden and this level of detection."

This is one of the strongest stories for DfE because Schools Digital needs analysts who can create clear, compelling outputs for technical and non-technical audiences, including senior stakeholders. The story shows that I can set a direction for visualisation standards: headline first, diagnostic context second, evidence and quality checks underneath. It also shows that I understand visualisation as communication, not decoration.

The main lesson I took was that the best dashboard is not the one with the most charts. It is the one that helps the user decide what to do next and understand whether the answer is safe to trust.

## 4. BigQuery, Dataform, Looker and Power BI Story: Creating Trusted Analytical Datasets

A strong technical story for DfE would be around cloud analytics and trusted reporting datasets, especially because the desirable criteria mention Google Cloud Platform tools such as BigQuery, Data Studio and Power BI.

The situation I would describe is a reporting environment where analysts were producing outputs from related data, but the logic was not always consistent. Different queries could define the same measure slightly differently. One report might count events based on created date, another based on completed date. One dashboard might exclude invalid records, another might not. If the differences were not documented, two outputs could disagree and the conversation would become about whose number was right rather than what the data meant.

The work I did was to make the reporting logic more structured. In BigQuery, I used SQL to create curated analytical tables rather than leaving every dashboard or report to query raw data independently. I separated raw data, cleaned data and reporting-ready outputs. I used Dataform to organise transformation logic into repeatable SQL models, so definitions could be versioned, tested and reused. That meant if a metric changed, there was one place to update and one logic path to review.

For example, if the reporting question was about case volume, I would not let each dashboard define case volume differently. I would define the source table, the date field, the inclusion rule, the exclusion rule, the status categories and the validation checks. Then the dashboard could read from that curated table rather than reconstructing the logic every time.

I also built checks into the process. These included checks for missing IDs, duplicate records, unexpected categories, row-count movements, null values in key fields and mismatch between source totals and reporting outputs. The aim was not only to clean data after errors appeared, but to catch issues before the figures reached the dashboard.

In Looker and Power BI, the focus was on making the output usable. The dashboard needed headline measures, trends, exception views and drill-down paths. I avoided making the dashboard depend on raw fields that users could misinterpret. Instead, I used curated metrics with clear definitions. For example, if a record was excluded because it failed validation, that exclusion needed to be visible somewhere. Otherwise, a lower count could look like reduced activity when it was actually a data-quality issue.

This story is strong because it shows technical knowledge at a senior analyst level. It is not just "I know BigQuery." It is: I used BigQuery and Dataform to make reporting logic reusable and governed; I used SQL to create trusted datasets; I used Looker and Power BI to expose those datasets in a way users could interpret; and I used validation checks to improve data quality before insight was consumed.

It also supports the DfE idea of scalable data products. A dashboard reading from one-off queries is fragile. A dashboard reading from documented, tested, reusable models is a data product. That is the level of maturity I would want to bring into Schools Digital: not just answering one question, but improving how teams use and trust data over time.

## 5. South Western Story: Turning Messy Close-Out Data Into an Action-Led Management View

My strongest workplace story is still from South Western Technologies & Oilfield Services Ltd, because it was a real operational reporting problem with real users.

The issue was around weekly operations and close-out reporting. Managers needed to know which jobs were active, delayed, completed or ready for the next stage. But the data was split across several sources: Oracle records, Excel trackers, equipment movement notes, QHSE records, man-hour sheets, service reports and close-out documentation. The problem was not only that data was messy. It was that the same status could mean different things to different teams.

A field team could say a job was completed because the work on site had ended. Admin could say it was not ready because the signed service report was missing. Equipment could say it was not clear because tools had returned but inspection was not confirmed. QHSE could say man-hour or safety records were incomplete. If I reported all of these as "completed," the management view would be wrong.

I changed the report by separating the broad status into more useful categories: active, delayed, field-completed, awaiting documentation, awaiting equipment confirmation, ready for close-out and requiring clarification. This made the report more honest. It also made it easier for each team to see what they owned.

The output was an exception view, not just a summary table. It showed which jobs had a completion date but no service report, which had equipment still tied to the job, which had missing man-hours, which delay reasons were unclear, and which jobs were genuinely ready for close-out. That changed the discussion. Instead of managers asking "how many jobs are completed?", the better question became "which jobs are field-completed but not ready for close-out, and what is blocking them?"

I used Excel, Access, Oracle extracts and SAS processing to make the reporting process more repeatable. Excel handled pivot summaries, formulas, lookups, conditional formatting and exception lists. Access helped structure local reporting inputs where a simple spreadsheet was too loose. Oracle provided formal job and status records. SAS helped with repeatable cleaning, joins and checks.

The most important part was not the tools. It was the decision logic. I made sure the report reflected the business process. If a job was missing a signed service report, it could not be treated the same as a fully closed job. If equipment return was unconfirmed, the operations team needed to know. If the delay reason was simply "pending," that was not good enough for a management decision.

The outcome was a more action-led reporting view. It reduced repeated checking and helped teams focus on what needed action. It also gave managers a clearer basis for decision-making because the report showed blockers, not just counts.

This story is strong for DfE because it shows synthesis. I connected records from different parts of a service journey and turned them into a management view. In Schools Digital, the domain would be different, but the analytical discipline is similar: map the user journey, identify where data is weak or ambiguous, define meaningful categories, and produce insights that help teams act.

## 6. South Western Story: Using Data Quality Evidence to Influence People Without Authority

Another South Western story is about influence. I did not line-manage operations, equipment, QHSE, admin or commercial colleagues, but my reports depended on their input. If they did not clarify records or update missing fields, the report would remain weak.

The issue was that people were busy, and data quality was not always their first priority. A field supervisor may care about the job being completed safely. Equipment may care about tools being ready for the next job. Admin may care about documentation. QHSE may care about safety records. Each team had its own pressure. So if I simply said "the data is incomplete," it would not help.

I learned to influence by making the data issue practical. Instead of saying "your data is wrong," I asked specific questions:

> Is this job still awaiting the signed service report, or has it been received but not recorded?

> Has this equipment returned and cleared inspection, or should it remain tied to the completed job?

> This delay is marked as pending. Is it client approval, equipment availability, documentation, logistics or internal follow-up?

That approach changed the tone. It made the issue specific and action-based. It also reduced defensiveness because I was not blaming the team. I was helping them make the shared report more accurate.

In one weekly reporting discussion, there were several jobs marked as completed, but they were not all at the same stage. I showed the exception view and explained that if we treated them all as completed, the report would hide follow-up work. I then walked through the categories and asked each team to confirm the items relevant to them. Operations confirmed which jobs were field-completed. Equipment clarified which tools had returned. Admin confirmed which reports were still missing. QHSE clarified which man-hour records needed chasing.

The result was that the report improved through the discussion. It was not me presenting a fixed spreadsheet and asking everyone to accept it. It was a two-way process: I brought structure and evidence; the teams brought operational context; together we produced a more accurate reporting view.

This story matters for DfE because a G7 analyst needs to influence across teams. Data quality problems are rarely solved by the analyst alone. They require other teams to understand why data quality matters and to change or improve their input. My experience shows that I can do that respectfully and practically.

## 7. South Western Story: Training Trainees to Work to a Reporting Standard

A useful leadership story is from supporting NYSC students and industrial training students at South Western. I would not overstate it as formal line management, but it was real coaching and quality-checking work.

The situation was that junior trainees could help with reporting tasks, but only if they understood the difference between entering data and producing information that could be trusted. The risk was that someone might update a tracker mechanically without understanding what the fields meant. For example, they might see a completion date and assume the job was closed, or treat a blank QHSE submission as zero, or copy a status without checking whether supporting documents existed.

I started by walking them through the reporting workbook and explaining the business meaning of the fields. I explained the difference between field-completed and ready for close-out. I showed why signed service reports, equipment return confirmation, man-hour records and QHSE submissions mattered. I also showed them the checks we used: looking for missing fields, duplicate job numbers, inconsistent status combinations, unclear delay reasons and mismatches between source records.

Then I gave them small checking tasks. For example, I might ask them to review a set of completed jobs and flag any missing close-out items. Or I would ask them to compare a tracker against an Oracle extract and note records where the status did not align. The important part was that I reviewed their checks afterwards. If they missed something, I explained why it mattered. If they marked something as an error when it was only awaiting confirmation, I explained the difference.

This helped them understand that reporting quality depends on judgement. A blank field is not always the same kind of problem. A missing service report, missing equipment confirmation and unclear delay reason each require different follow-up. I also encouraged them to write notes that someone else could understand, not just mark a cell in a colour.

The result was that their work became more useful and they became more confident. They were not just helping with spreadsheet tasks; they were learning the reporting logic behind the task. This also made my work easier because I could trust them with small checks and use my time on interpretation and stakeholder follow-up.

For DfE, this story supports mentoring and raising analytical standards. It shows that I can help others understand why checks matter, review outputs, correct misunderstandings and build capability. At G7 level, that is important because the role includes supporting analyst development and setting standards for the team.

## 8. Public-Data Project Story: Analysing Business Recovery and Policy Context Without Overclaiming Causation

The public-data project is useful for DfE because it shows policy-facing analysis. It was not in education, but it involved public data, government policy context, time-series interpretation and careful communication of limitations.

The project looked at Facebook Business Activity Trends during COVID-19 and compared business activity changes with Oxford Government Response Tracker policy data. The dataset came as 1,004 daily files, which I combined into a dataset of around 2.4 million rows. I focused on selected countries and business sectors, including restaurants and grocery or convenience stores.

The first challenge was understanding the data rather than rushing into charts. I had to understand what the activity metrics meant. Activity percentage was easier to explain, but activity quantile was more stable for comparison because it was less dominated by highly active business pages. I chose the metric based on suitability, not convenience.

Then I checked coverage. I looked at countries, business verticals, dates and missingness. I found that the data had strong country-level coverage, but some region fields were not usable. That affected the scope of analysis. Instead of pretending the dataset could answer every question, I narrowed the work to countries and sectors where comparison was meaningful.

The policy data added another layer. I used the Oxford policy indicators to understand restrictions such as workplace closure, public event cancellation, stay-at-home requirements and movement restrictions. The analytical challenge was avoiding overclaiming. If business activity dropped during a period of higher restrictions, that did not prove the policy caused the drop. There could be seasonal effects, consumer behaviour changes, infection waves or data limitations.

So the output was cautious. I showed time-series trends, compared sectors and countries, and interpreted movement against policy context without turning correlation into causation. I also explained limitations clearly: the Facebook data measured posting activity, not revenue; the data was aggregated, not business-level; and policy timing did not by itself prove causal impact.

This story is useful for DfE because education policy analysis has similar risks. A change in attendance, teacher recruitment, SEND demand or service use can be affected by many factors. A senior analyst needs to connect data to policy context without overstating what the data proves. This project shows that I can handle public datasets, choose appropriate metrics, communicate uncertainty and produce insight that respects context.

## 9. Five Guys Story: Maintaining Quality Service Under Pressure and Training New Starters

Five Guys is not a data-analysis example, and I would not use it as one. But it is useful for leadership, quality service, training and pressure.

One busy shift stands out. Orders were building across in-store, takeaway and delivery. The risk was not just speed; it was accuracy. Some bags had burgers but were waiting on fries. Some delivery orders were waiting on drinks. Some tickets had been started but were not complete. Delivery drivers were waiting and customers were asking for updates.

In that situation, poor communication could create mistakes quickly. If an incomplete bag went out, the customer experience would suffer and the team would have to fix it under even more pressure. So I focused on making order status clear. I used specific updates: "this order is waiting on fries," "this delivery still needs the shake," "this bag has burgers but no fries," rather than vague comments like "this one is not ready."

I also helped newer staff understand how to check orders before handover. I explained that the ticket is the source of truth. The bag may look complete, but it is not complete until the ticket has been checked against burgers, fries, drinks, shakes and delivery labels. I broke the process down into steps and corrected errors patiently. The aim was not to criticise someone for being new, but to help them understand the quality standard.

This helped stabilise the shift. It reduced repeated checking, made handovers clearer and helped prevent incomplete orders going out. It also taught me something relevant to data work: quality under pressure depends on clear process, visible status and calm correction. Whether it is a food order or a data output, people need to know what is complete, what is waiting, what has been checked and what still needs action.

For DfE, I would only use this story if needed for Leadership or Managing a Quality Service. It shows that I can train others, maintain standards under pressure, communicate clearly and improve a live process without needing formal authority. The main analytical evidence should still come from the platform and South Western, but this supports the behaviour side.

## Evidence Spine

Taken together, these stories give Eric a stronger G7 posture:

- The platform shows he can set analytical direction and build scalable data products.
- The feature and decision layer story shows analytical modelling and technical design.
- The dashboard story shows visualisation standards and communication.
- The BigQuery, Dataform, Looker and Power BI story shows modern cloud analytics and reusable data products.
- The South Western stories show real workplace data quality, stakeholder influence and decision-support reporting.
- The trainee story shows coaching and raising standards.
- The public-data project shows policy-aware analysis and cautious interpretation.
- The Five Guys story supports quality service, leadership under pressure and training.

This gives enough material to later write a statement that says:

> I can lead analytical work from question to decision: define the analytical approach, design trusted datasets, create clear visual outputs, quality-assure the analysis, influence stakeholders, and help others work to stronger analytical standards.
