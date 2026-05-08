# BNP / Arval Financial Data Analyst - Platform Positioning

## Role Posture

For this role, the platform should be positioned as a financial/customer credit data flow platform, not as a fraud analytics or machine learning project.

The BNP / Arval role is about joining a finance team to build and maintain data flows, review existing data processing, manage finance reporting and data requests, and uphold data quality and governance practices.

The platform story should quietly answer:

> Can this person take messy and high volume financial data, organise it into reliable flows, maintain queryable datasets, support reporting requests, and make the data more usable for finance and risk decisions?

## Core Platform Positioning

The first experience should be framed around:

> Built and maintained an AWS hosted customer credit data platform processing a 2.35 billion row credit surface, transforming raw customer, account, and transaction data into governed SQL and SAS reporting datasets for financial analysis, risk monitoring, data quality checks, and general reporting requests.

This is not a final resume bullet. It is the role posture.

It should communicate:

- data flows;
- financial datasets;
- large scale;
- SQL;
- SAS programming;
- reporting;
- data governance;
- finance and risk relevance;
- maintainability.

## Data IQ to Enhance

For this role, "enhance data IQ" means improving stakeholders' ability to understand, trust, query, explain, and act on customer credit financial data.

The platform should not be positioned as only storing a 2.35 billion row credit surface. The value is the intelligence layer built on top of the raw volume.

Stakeholders would want clearer answers to questions such as:

- What is happening across customer, account, transaction, risk, and reporting data?
- Can we trust the numbers?
- Which customers or accounts are changing?
- What is driving the change?
- Which cases, reports, or exceptions need attention?
- Which reports are safe to use?
- Where did this number come from?

| Data IQ area | What stakeholders gain |
| --- | --- |
| Customer/account visibility | A clearer view of each customer, account, transaction activity, risk band, flags, and decision history. |
| Financial reporting confidence | Reporting datasets that are clean, reconciled, queryable, and ready for finance analysis. |
| Risk understanding | Ability to see which accounts are becoming riskier, improving, staying stable, or needing review. |
| Trend intelligence | Ability to track changes over time across payment behaviour, account activity, risk movement, escalation patterns, and reporting exceptions. |
| Data quality awareness | Visibility into missing values, duplicates, broken joins, stale data, schema changes, and unusual row count movements. |
| Governance and lineage | Ability to trace where a dataset came from, when it was processed, what rules were applied, and whether it is safe to use. |
| Decision support | Clearer evidence for prioritisation, review queues, customer messaging logic, escalation decisions, and reporting requests. |
| Self-serve querying | SQL, SAS, Power BI, and Excel ready datasets so stakeholders do not need to rebuild raw logic every time they ask a question. |

Stakeholder versions of data IQ:

| Stakeholder group | What data IQ means to them |
| --- | --- |
| Finance team | Can I trust this dataset enough to use it for reporting and analysis? |
| Credit risk team | Can I see which accounts are becoming riskier and why? |
| Collections strategy team | Can we use the data to make better, fairer prioritisation decisions? |
| Operations/contact centre teams | Can this data tell us what to do next? |
| Governance/compliance stakeholders | Can we prove where the numbers came from and whether they were produced correctly? |

In platform terms, the data IQ story is:

> Raw customer/account/transaction/decision data becomes governed, queryable, reporting ready intelligence about customer credit behaviour, risk movement, data quality, and decision outcomes.

Key phrase:

> From raw volume to trusted intelligence.

## Data Flows in the Platform

| Data flow | Platform meaning |
| --- | --- |
| Customer/account data flow | Customer and account level records flowing into the platform as the base entity layer. |
| Transaction/activity data flow | High volume transaction, payment, account activity, balance, or event records feeding the 2.35 billion row credit surface. |
| Risk signal data flow | Derived flags, risk bands, behavioural indicators, arrears signals, exposure signals, and review triggers. |
| Decision/outcome data flow | Review outcomes, escalation outcomes, collections decisions, prioritisation outputs, and status changes. |
| Reporting data flow | Curated datasets prepared for finance reporting, dashboards, trend analysis, and general data requests. |
| Data quality/governance flow | Row counts, schema checks, duplicate checks, freshness checks, completeness checks, lineage, and reconciliation outputs. |
| SAS/statistical reporting flow | Curated reporting tables or extracts used in SAS Studio / SAS programming for validation, summaries, and repeatable financial analysis. |

Strong posture:

> I built and maintained data flows from raw customer/account/transaction data into governed reporting datasets used for credit risk monitoring, finance analysis, and decision support.

## Storage and Querying Architecture

For a 2.35 billion row platform, the credible storage story is a cloud data lake / lakehouse pattern, not local files.

| Layer | Storage/query choice | Why it makes sense |
| --- | --- | --- |
| Raw / landing layer | AWS S3 | Scalable storage for incoming datasets. |
| Curated analytical layer | S3 in partitioned Parquet | Better for querying billions of rows than CSV. |
| Metadata/catalogue layer | AWS Glue Data Catalog | Makes S3 data discoverable and queryable as tables. |
| Query layer | AWS Athena or Redshift Spectrum | SQL querying over large S3 datasets. |
| Reporting layer | Redshift / Athena views / Power BI datasets | Finance reporting and dashboard consumption. |
| SAS layer | SAS Studio / SAS programming on curated extracts or reporting marts | Useful for governed summaries, validation, statistical reporting, and finance analysis. |

Key design point:

> S3 stores the scale; SQL/Athena/Redshift query the scale; SAS works on governed reporting outputs, extracts, summaries, or marts.

Do not position SAS as the thing storing or directly managing the whole 2.35 billion rows unless the proof exists. SAS should be positioned as a programming, reporting, validation, and analysis layer.

## Build Work

| Build area | What is being built |
| --- | --- |
| Ingestion flows | Bringing in customer, account, transaction, decision, and outcome data. |
| Standardisation flows | Converting different source formats into consistent schemas. |
| Data modelling | Creating customer, account, transaction, risk, decision, and reporting tables. |
| Transformation logic | Turning raw activity into risk bands, flags, aggregates, and reporting ready fields. |
| Reporting marts | Creating datasets that answer finance and risk questions without reprocessing raw data every time. |
| Validation checks | Building checks for row counts, nulls, duplicates, schema changes, freshness, and reconciliation. |
| SAS reporting layer | Creating SAS programs that clean, join, summarise, validate, and output finance reports. |
| Dashboard/report outputs | Preparing data for Power BI, Excel, and general reporting requests. |

The platform is not just:

> I analysed data.

It is:

> I built the flows that make the data usable, queryable, reportable, and governable.

## Maintenance Work

| Maintenance area | What it means |
| --- | --- |
| Schema maintenance | Handling new, missing, renamed, or changed fields. |
| Freshness monitoring | Checking whether expected datasets arrived and were processed on time. |
| Data quality monitoring | Detecting duplicates, missing values, invalid dates, broken joins, or unexpected row counts. |
| Query performance | Partitioning large datasets properly so reports do not become slow or expensive. |
| Reporting stability | Making sure downstream reports do not break when upstream data changes. |
| Governance/lineage | Knowing which source created which output, when it was processed, and what logic was applied. |
| Request handling | Creating or adapting datasets for finance questions without rebuilding everything manually. |
| SAS program maintenance | Keeping repeatable SAS reporting scripts aligned with source schema and reporting needs. |

Maintenance story:

> I can maintain complex data flows so finance and risk users can trust the datasets they query and report from.

## Data Users

Because this is an open-source/platform project, do not claim real business teams used it unless they did. The safer position is that the platform was designed around these business user groups.

| Team/user type | What they would use the data for |
| --- | --- |
| Finance team | Reporting, reconciliations, account level summaries, trend analysis, data requests. |
| Credit risk team | Risk monitoring, account segmentation, risk band movement, exposure trends. |
| Collections strategy team | Prioritisation, escalation logic, collections outcomes, strategy review. |
| Operations/contact centre teams | Account review queues, customer status, escalation reasons, case prioritisation. |
| Compliance/data governance | Auditability, data quality checks, lineage, governed reporting outputs. |
| BI/reporting users | Power BI dashboards, Excel extracts, recurring reports, management packs. |
| Data/platform team | Pipeline health, data freshness, schema changes, query performance, storage layout. |

For BNP, the most relevant users are:

> Finance, data/reporting, governance, risk, and operations.

## Clean Mental Model

Raw financial/customer activity data comes in. It is stored in AWS S3. It is transformed into curated customer, account, transaction, risk, and reporting tables. SQL handles large scale querying and modelling. SAS programming handles governed finance reporting, validation, and summary outputs. Power BI/Excel consume curated outputs. Data quality and governance checks make the flow maintainable and trustworthy.

## Working Boundaries

| Area | Positioning rule |
| --- | --- |
| Platform identity | Financial/customer credit data flow platform |
| Main problem solved | Building and maintaining reliable data flows for finance and risk reporting and insight |
| Scale | 2.35 billion row credit surface, plus supporting customer/account/transaction/risk/outcome/reporting datasets |
| Storage story | AWS S3 for scale, partitioned Parquet/curated tables for queryability, SQL/Athena/Redshift querying |
| SAS role | SAS programming for governed reporting, validation, summaries, and finance analytical outputs |
| Power BI/Excel role | Downstream reporting, dashboards, finance requests, and business consumption |
| Governance story | Data quality checks, reconciliation, lineage, freshness, schema control, repeatable outputs |
| Teams | Finance, reporting/BI, credit risk, governance, operations, collections strategy |

## One Line Platform Description Candidate

AWS hosted open-source financial/customer credit data platform transforming raw customer, account, and transaction data into governed SQL and SAS reporting datasets for finance reporting, credit risk analysis, data quality checks, and decision support.
