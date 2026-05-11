# Prelim Response - Statement of Suitability

Role: Intergenerational Harm Analyst - Ministry of Justice

Purpose:
- Build the raw evidence for the 1000-word statement of suitability.
- Keep the final statement name-blind: no name, institution names, nationality, address, contact details, or immigration detail.
- Avoid false direct claims: no direct MoJ, HMPPS, HMRC, DfE, prison, probation, parental-imprisonment, offending-data, benefits-data, education-data, or formal data-sharing agreement experience unless separately evidenced.
- Use the evidence to sound like linked-data, public-interest, quality-assured analysis rather than generic fraud analytics.

## Experience 1 Question

Question:
Are you a member of a civil service analytical profession? If so, please answer in one word: GORS, GSS, GSR or GES. If you do not belong to a profession, please state N/A.

Answer:
N/A

## Statement Strategy

The statement should not try to cover every CV detail. It should prove the essential experience and skills:

- Data and quantitative analysis: large complex datasets, complex analytical techniques, insights, visualisations.
- Data sharing, ethics, and quality assurance.
- Analytical tools and languages: Python and SQL, with Power BI/Excel where useful.
- Analytical project management: scoping, planning, delivery, coordination of analytical requirements and outputs, quality, timeliness.
- Communication to technical and non-technical audiences.
- BPSS and SC willingness, only briefly and only as required.

The strongest evidence mix:

- Fraud Risk Intelligence Platform: linked multi-source operational data, entity/event/case/label/reporting records, QA, matching logic, decision-support analysis.
- COVID-19 policy/activity analysis: public-interest policy data, 1,004 daily CSV files, 2,396,549 observations, 220 countries, policy-context interpretation.
- Network analysis surveillance-prioritisation project: hidden relationships, risk coverage, method-led decision implications.
- Engineering/service work: controlled operational discipline, accurate readings, escalation, handovers, pace, communication.

## Evidence Block 1 - Large Complex Data, Linked Records, and Quantitative Analysis

The fraud risk intelligence platform is the main evidence for large, complex linked-data analysis. The analytical problem was not one clean table but a governed data world made up of operational events, decision outputs, entity histories, labels, case movement, controls, and reporting evidence. The practical question was how to turn those separate records into reliable evidence for prioritisation, workload understanding, quality review, and bounded demand planning without losing lineage or creating misleading joins.

My work involved shaping linked analytical datasets that connected upstream events, entities, decisions, and downstream outcomes. I used Python and SQL-led workflows to inspect grains, check keys, validate relationships, and separate event-level, entity-level, label-level, and case-level logic. That mattered because a wrong join could make a decision look effective when the evidence actually belonged to a different record, period, or outcome. I therefore treated linkage as an analytical method in its own right, not as a mechanical data-preparation step.

The analysis produced usable decision-support evidence rather than raw model output alone. For example, the highest-risk band produced 2.29x baseline yield, and bounded demand planning achieved 7.31% test MAPE. The importance of these measures was not the numbers by themselves; it was that they helped judge where review effort could be concentrated, what workload pressure might follow, and how much confidence to place in the output. The core lesson was that linked operational and administrative data must be analysed with constant attention to grain, coverage, missingness, matching quality, and the decision that the evidence is meant to support.

## Evidence Block 2 - Data Quality, Ethics, Assurance, and Matching Risk

My quality-assurance evidence comes from working with linked operational data where errors could change the interpretation of risk, workload, and performance. In that setting, I had to treat data quality as part of the analytical conclusion. A dashboard or model result was not acceptable simply because the code ran; it needed to be traceable, reproducible, and honest about what the data could and could not support.

I used schema checks, completeness review, reconciliation, source traceability, leakage controls, and documented assumptions to test whether the data was suitable for analysis. When discrepancies appeared, I separated possible source-data issues from transformation errors, modelling errors, control logic, matching logic, and interpretation problems before drawing conclusions. That discipline matters in linked-data work because matching errors can create both false positives and false negatives: records may be connected when they should not be, or missed when the relationship exists but is weak, incomplete, or inconsistently recorded.

I also used a responsible-use mindset. My analytical outputs were designed to support prioritisation and review, not to remove human judgement. I documented limitations, validation outcomes, and handover notes so another reviewer could understand why a result was produced and what caution should follow. The same discipline supports data sharing, linkage, and analytical quality through transparency, minimisation of avoidable harm, clear assumptions, and respect for the public-interest purpose of the analysis.

## Evidence Block 3 - Public-Interest and Policy-Relevant Evidence

The strongest public-interest evidence comes from a COVID-19 policy and activity analysis. The task was to understand business activity patterns in the context of government pandemic responses, rather than treating the data as a detached time-series exercise. I combined 1,004 daily CSV files in Python into 2,396,549 observations and 12 variables across 220 countries and 1,004 days, then integrated Facebook Business Activity Trends data with Oxford COVID-19 Government Response Tracker policy data.

The work required quality checks before interpretation. I assessed coverage, missingness, duplicates, country/date validity, metric suitability, and limitations before comparing country trends. I then produced visual analysis that linked unusual movements to containment policies, public-health events, and documented external evidence. That gave the analysis a public-policy frame: what changed, when it changed, which policy context surrounded the change, and what could be stated responsibly from the data.

This gives public-interest evidence in a policy context: combining data sources, respecting limitations, avoiding overclaimed causality, and producing analysis that helps people understand risk, service implications, or policy choices. The learning was that public-interest analysis must balance technical confidence with caution: the output should be clear enough to support decisions, but honest enough not to overstate what the data proves.

## Evidence Block 4 - Network Analysis, Hidden Relationships, and Prevention Logic

The network-analysis evidence adds a second angle on hidden relationships and prevention logic. The aim was to use network structure to reason about hidden relationships, risk coverage, and prioritisation choices. This was not a simple ranking exercise. The value came from understanding how relationships between nodes changed the interpretation of risk and how a limited intervention or surveillance resource could be directed more intelligently.

I applied game-theoretic network analysis and produced method-led findings that explained both the analytical approach and the decision implications. The key discipline was not to treat network metrics as self-explanatory. A central node, bridge, or high-risk cluster only matters when the method, assumption, and practical implication are explained clearly. This is relevant to linked administrative data because families, individuals, services, cases, and events can form complex relationship structures where risk is not always visible from a single record.

The result was evidence that could support prioritisation logic: which relationships mattered, where coverage was stronger or weaker, and what the limits of the method were. The learning for this role is that prevention-focused analysis often depends on finding patterns that are not obvious in flat data. That requires careful matching, network thinking, quality assurance, and clear explanation of what the analysis can support.

## Evidence Block 5 - Analytical Project Management and Delivery

The delivery evidence comes from moving a broad, complex data environment into scoped, reviewable analytical outputs. The challenge was deciding what to analyse first, what evidence was needed, what definitions had to be fixed, and how to prevent the work becoming an uncontrolled exploration.

I planned the work in stages: understand the data world, define the relevant grains, build linked datasets, validate the outputs, produce analysis, document assumptions, and refine findings into decision-support evidence. I used Git and structured documentation to keep the work reproducible. I also used controlled AI-assisted support for drafting, coding, and documentation, but kept human judgement, testing, and review in control of the final analytical decisions.

The delivery standard was that another analyst should be able to follow the reasoning, understand the source of each result, and see the limitations without needing informal explanation from me. That matters for this role because analytical projects involving sensitive linked data need clear scoping, quality gates, timeliness, and evidence trails. The learning was that good delivery is not just finishing an analysis; it is making the analysis usable, auditable, and safe to rely on.

## Evidence Block 6 - Communication to Technical and Non-Technical Audiences

The communication evidence comes from translating complex analytical work into two levels of explanation: technical enough for someone to inspect the method, and plain enough for someone to understand the decision implication. In the fraud platform, technical communication meant explaining linkage logic, model validation, leakage controls, assumptions, MAPE, yield, and quality checks. Non-technical communication meant explaining what the findings implied for workload, prioritisation, confidence, and caution.

For example, a result such as 2.29x baseline yield is not useful if left as a model statistic. I translated it into the operational meaning: the top band was more concentrated with relevant cases than the baseline, so it could support prioritised review if the data quality checks and assumptions held. Similarly, 7.31% MAPE was not presented as a mathematical trophy; it was evidence about the expected error in bounded demand planning and therefore how cautiously the forecast should be used.

The COVID-19 analysis required a similar communication discipline. Visualisations had to show patterns clearly, but the written interpretation had to explain policy context and limitations without overstating causality. The learning was that good analytical communication is not simplifying until the evidence becomes vague. It is choosing the right level of detail so the audience understands the method, the result, the uncertainty, and the practical action or caution that follows.

## Evidence Block 7 - Behaviours and Role Posture

Changing and Improving is shown through the way I improve analytical workflows rather than accepting raw extracts or first-pass outputs. I look for better ways to validate data, document assumptions, reduce manual ambiguity, and make outputs easier to reuse or review. This includes using automation and AI-assisted tools carefully, but only where the result remains tested and governed.

Making Effective Decisions is shown through my focus on evidence, uncertainty, and implications. I do not treat a metric as a decision by itself. I check whether the data is reliable, whether the denominator is right, whether the result is stable enough, and what limitation should be communicated before recommending how the evidence should be used.

Working Together needs to be framed truthfully. The strongest direct evidence is not a claim of formal cross-government stakeholder coordination. It is that I design analysis around the needs of different users of evidence: technical reviewers who need method and QA clarity, and non-technical decision users who need implications, options, and caution. Combined with my engineering and live-service work, this gives me a practical foundation for working constructively in multidisciplinary teams where analysts, policy users, operational colleagues, and technical specialists need shared evidence they can trust.

## Final Statement Notes

Keep in final:
- Large data scale: 2,396,549 observations; 1,004 CSVs; 220 countries; 81m raw platform records only if useful and not metric-heavy.
- Python, SQL, QA, linkage, matching, entity/event/case/label logic.
- Public-interest and prevention framing.
- Ethics and quality assurance as active analytical behaviour.
- Communication through method, limitations, and implications.
- Willingness to meet BPSS and apply for SC clearance.

Avoid in final:
- Education institution names.
- Personal details.
- Claiming direct MoJ, HMPPS, HMRC, DfE, prison, probation, parental-imprisonment, offending-data, benefits-data, education-data, or formal data-sharing experience.
- Saying "although I do not have direct..." or similar self-disqualifying language.
- Repeating the CV.
- Overloading the statement with too many metrics.
