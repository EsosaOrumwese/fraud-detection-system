# Preliminary Responses - UKHSA Data Manager

Purpose:
- Build the evidence bank for the supporting information.
- Keep the final statement grounded in real examples.
- Avoid claiming direct UKHSA, respiratory-virus laboratory, clinical-record, or clinical surveillance work.

---

## 1. Lead Criterion - Data Management and Analysis Using Database Software / SQL

**Question being answered**

Tell me how you meet the lead criterion: experience in data management and analysis using database software packages such as MS Access and SQL.

**Context**

The strongest evidence comes from the Fraud Risk Intelligence Platform, where I worked with structured data surfaces that needed to behave like dependable analytical database outputs rather than isolated project files. The platform generated and used multiple related datasets: event records, decision outputs, entity histories, labels, case movement, model outputs, and reporting tables. The problem was that these datasets had different grains and meanings. If they were joined incorrectly or used without validation, the reporting layer could produce misleading outputs.

**Action**

I used SQL and Python to query, join, transform, validate, and analyse those structured datasets. I treated the work as controlled data management: defining the join logic, checking source traceability, documenting assumptions, reviewing schema consistency, and separating reusable analytical surfaces from one-off extracts. I used SQL-style relational thinking to decide which keys could be trusted, where joins could multiply records, and where outputs needed reconciliation before they could be used.

**Result**

The result was a set of reusable analytical datasets with clearer lineage, repeatable extraction logic, stronger validation checks, and outputs that could support reporting on workload exposure, case flow, data integrity, model yield, and demand pressure. The work gives me a strong base for a role where databases, SQL queries, recurring surveillance datasets, and accurate reporting outputs matter.

**Learning**

The main learning was that database analysis is not just about writing a query that runs. It is about understanding dataset meaning, controlling joins, checking accuracy, documenting assumptions, and making sure the output is fit for decision-making.

---

## 2. Scientific / Public-Health-Adjacent Analysis - COVID-19 Project

**Question being answered**

Tell me about evidence of analysing complex scientific, pandemic, or public-health-adjacent data.

**Context**

During my MSc, I completed a COVID-19 pandemic analysis project using the Facebook Business Activity Trends dataset and the Oxford COVID-19 Government Response Tracker dataset. The aim was to understand business activity trends during the pandemic and explore how containment and closure policies related to observed changes. This gives me role-relevant evidence of pandemic-context analysis using large, longitudinal public datasets and policy-response evidence.

**Action**

I combined 1,004 daily CSV files into a single analytical dataset of 2,396,549 observations and 12 variables covering 220 countries over 1,004 days. I assessed the dataset structure, country/date coverage, business-vertical coverage, missingness, duplicates, and metric suitability. I then integrated the activity data with Oxford policy-response data and focused on selected countries to compare trends, policy timing, and unusual movements.

**Result**

The project produced a research-style analysis of pandemic-period activity patterns, including visualisations, written interpretation, and explicit limitations where the available data could not fully explain observed variation. It demonstrated my ability to work with complex longitudinal data, combine external public datasets, assess data quality, choose suitable metrics, and communicate evidence carefully.

**Learning**

The strongest learning was that pandemic data cannot be interpreted responsibly by looking at a single metric alone. Dataset coverage, metric construction, external context, policy timing, and limitations all affect the quality of interpretation.

---

## 3. Accuracy, Data Quality, and Attention to Detail

**Question being answered**

Tell me how you demonstrate attention to detail and a particular emphasis on accuracy of data.

**Context**

Both my platform work and COVID-19 project required careful data-quality handling. In the platform, incorrect joins or unchecked assumptions could distort reporting and model interpretation. In the COVID-19 project, missing business verticals, country coverage, date coverage, and metric behaviour affected whether comparisons were meaningful.

**Action**

I used quality checks such as schema review, missingness checks, duplicate checks, completeness review, source traceability, reconciliation, validation outputs, and documented assumptions. In the COVID-19 work, I checked that countries had 1,004 dates available, reviewed business vertical completeness, identified a limited anomaly in Turkmenistan's retail vertical, and selected activity quantile over activity percentage because it was more robust to outliers and more stable for comparison.

**Result**

These checks improved the trustworthiness of the outputs by making it clear what could be relied on, what needed caution, and what could not be concluded from the data alone. The same discipline is directly relevant to UKHSA's requirement for accurate surveillance databases and scientific reporting.

**Learning**

Accuracy is not just about avoiding typing errors. It is about knowing the source, the grain, the denominator, the coverage, the assumptions, and the limits of interpretation before reporting a finding.

---

## 4. Reporting, Interpretation, and Communication

**Question being answered**

Tell me how you produce reports or communicate complex findings clearly.

**Context**

The UKHSA role requires regular scientific reports, ad hoc analysis, presentations, project reporting, and contribution to publications. My closest evidence comes from writing research-style analysis in the COVID-19 project and producing documented analytical outputs from the fraud risk platform.

**Action**

In the COVID-19 project, I produced visual analysis and written interpretation of trends across selected countries, linking movements to policy changes and external events where evidence supported it. I also stated limitations where the available data could not fully explain variation. In the platform work, I documented data definitions, processing boundaries, validation results, and known limitations so outputs could be reviewed and understood.

**Result**

The result was analysis that did not only show charts or metrics, but explained what the data meant, why the interpretation was reasonable, and where caution was needed. This is relevant to scientific reporting because the reader needs to understand both the finding and the confidence they can place in it.

**Learning**

Clear reporting is not about simplifying the evidence until it loses meaning. It is about explaining the data, method, result, uncertainty, and practical implication in a way that another person can follow and challenge.

---

## 5. Confidentiality, Governance, and Secure Handling Mindset

**Question being answered**

How do you address confidentiality, data security, and governed handling?

**Context**

The honest evidence is that I have worked in governed analytical contexts where outputs needed controlled handling, traceability, validation, and documentation before they could be trusted. This does not become a claim of direct clinical-record or UKHSA policy experience; it is evidence of the discipline I would apply in that environment.

**Action**

In the platform work, I used controlled data handling principles: source traceability, validation records, documented assumptions, careful separation of training/testing/reporting surfaces, and reviewable outputs. I also understand the importance of confidentiality, data protection, and secure handling where sensitive or high-value information is involved.

**Result**

This gives me a strong transferable base for working in a secure public-health data environment, where confidentiality, statutory data-protection duties, and local policies would need to be followed exactly.

**Learning**

The key learning is that governed data work depends on trust. Trust comes from careful access, accurate handling, clear documentation, and knowing when data should not be used beyond its permitted purpose.

---

## 6. Reasons for Applying and Personal Strengths

**Question being answered**

Why this role, and what do I uniquely offer?

**Context**

This role sits at the point where database management, scientific data, public-health surveillance, and high-accuracy reporting meet. That fits my strongest evidence better than a generic reporting-only role because it values SQL, structured data, scientific interpretation, accuracy, and public-service purpose.

**Action**

The strengths I would bring are SQL-led data management, scientific time-series analysis, careful quality assurance, strong documentation, and the ability to explain uncertainty rather than hide it. My COVID-19 project gives me a direct pandemic-data bridge, while the fraud risk platform gives me stronger evidence of governed data workflows, validation, and reusable reporting surfaces.

**Result**

Together, these experiences position me as someone who can learn the respiratory-virus domain while already bringing the core data-management discipline needed to support surveillance systems and scientific reporting.

**Learning**

The role appeals because it would let me apply technical data skills in a high-consequence public-health setting where accuracy, confidentiality, and clear interpretation have real-world value.
