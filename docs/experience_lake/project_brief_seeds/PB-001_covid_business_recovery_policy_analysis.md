# PB-001: COVID Business Recovery and Policy Response Analysis

## Working Title

**Discovering Business Recovery Strategies and the Role of Government Policies through Analysis of Facebook Business Activity Trends during the COVID-19 Pandemic**

Shorter portfolio title:

> **COVID Business Recovery and Policy Response Analytics**

## Project Positioning

This project is the public-sector and policy-facing analytics project.

It should not be treated as a simple coursework repeat. The old coursework brief is useful because it defines the original analytical surface: Facebook Business Activity Trends, metric interpretation, missingness/duplicates, time-series behaviour, geographic comparisons, event interpretation, and reflective limitations. The rebuild should turn that into a professional analytical project with a clear brief, reproducible workflow, visual evidence, policy/event context, and stakeholder-ready communication.

## Portfolio Role

This project should provide evidence for:

- public data analysis
- time-series analysis
- policy/event interpretation
- geospatial communication
- metric interpretation and limitations
- data quality assessment
- reproducible Python/SQL workflow
- stakeholder-facing briefing
- clear communication of uncertainty and caveats

It should not be forced to prove complex platform engineering, fraud-domain expertise, or production ML deployment.

## Delivery Role

The assumed role is:

> **Data Analyst / Public Policy Analyst supporting economic recovery and resilience insight.**

The analyst is tasked with turning large-scale public-interest activity data into an evidence-led view of business disruption, recovery, and policy context across countries and sectors.

## Tooling Assumption

The future repo should make the analytical tooling explicit enough for a handoff agent to execute the project professionally:

- Use `Python` and `SQL` for reproducible data preparation, profiling, joins, metric calculation, and analytical checks.
- Use notebooks or scripts for investigative analysis, but keep stakeholder-facing outputs separate from exploratory work.
- Use a local analytical query layer such as `DuckDB` where the data volume or workflow benefits from SQL-style modelling.
- Produce dashboard-ready extracts and a page specification that could be implemented in `Power BI` or an equivalent BI tool.
- A finished `.pbix` file is optional at brief stage; the non-negotiable output is a reporting-ready data layer, metric definitions, page design, caveats, and stakeholder briefing.

## Operating Scenario

During and after the COVID-19 pandemic, public-sector and economic recovery stakeholders need to understand how business activity changed across countries, sectors, and time.

The available data is not direct financial transaction data. It is a public-interest activity signal derived from Facebook Business Activity Trends. That makes metric interpretation central: the project must explain what the metrics mean, what they do not mean, and how policy/event context should be used without overclaiming causality.

## Core Problem

The project must answer:

> **How did business activity change across countries and sectors during the COVID-19 pandemic, how do those changes relate to major policy or event periods, and what recovery patterns or analytical caveats should decision-makers understand?**

## Candidate Stakeholders

| Stakeholder | Concern | Required project response |
|---|---|---|
| Economic Recovery Lead | Which countries or sectors recovered faster or remained disrupted? | Time-series recovery profiles, cross-country comparisons, sector breakdowns. |
| Policy Analyst | How do activity changes align with restrictions, reopening, or major events? | Event/policy overlays and cautious interpretation. |
| Data Quality / Methods Lead | Can these metrics be trusted and compared? | Metric definitions, missingness/duplicates, data-quality checks, caveats. |
| Executive / Public Briefing Audience | What are the key findings and implications? | Plain-English briefing with clear figures and limitations. |

## Stakeholder Concerns and Decision Needs

This project must not stop at exploratory plots. It must be structured around the decisions or discussions that public-sector and economic recovery stakeholders would need to have.

| Stakeholder concern | Decision or discussion it supports | Required analytical evidence |
|---|---|---|
| Uneven recovery | Which countries, regions, or sectors appear to need closer monitoring or support? | Recovery trajectories, recovery timing, residual disruption, representative country/sector comparisons. |
| Policy/event interpretation | How should activity changes be interpreted alongside restrictions, reopening, or major events? | Annotated trend views, policy/event overlays, careful distinction between association and causality. |
| Metric trust | Which activity metric should be used for which kind of statement? | Metric dictionary, examples of where `activity_quantile` and `activity_percentage` agree or diverge, caveat notes. |
| Geographic communication | Where are the most visible spatial differences in disruption or recovery? | Map views and regional comparisons tied to a specific statistical finding. |
| Data reliability | Which findings are strong enough for a briefing, and which need caution? | Coverage checks, missingness/duplicates profile, country/sector inclusion rules. |
| Forward monitoring | What would be worth tracking in future recovery or resilience reporting? | Recommended indicator set, caveats, and additional data needs. |

## Required Dashboard / Reporting Product

The rebuild should produce dashboard-ready outputs or a lightweight reporting product. It does not need to be a fully deployed BI dashboard, but it must specify the pages, metrics, filters, and intended user decisions clearly enough that a dashboard could be built from it.

Required reporting pages:

| Page | Purpose | Expected content |
|---|---|---|
| Executive recovery overview | Give a senior reader the main recovery picture. | Headline metrics, selected country/sector comparison, key findings, confidence/caveat summary. |
| Country and sector trend explorer | Show how activity changed over time. | Time-series by country, business vertical, metric, and selected policy/event periods. |
| Policy/event context view | Support cautious discussion of restrictions, reopening, and activity shifts. | Annotated trends, policy response indicators, before/after windows where justified. |
| Geographic recovery view | Communicate spatial variation. | Map-based or regional comparison views for selected dates or recovery metrics. |
| Data quality and metric caveats | Prevent misuse of the data. | Coverage, missingness, duplicate checks, metric definitions, known limitations. |

Minimum filters or breakdowns:

- country or region
- continent or income/region group if available
- business vertical
- date range
- metric type
- policy/event period

## Expected Recommendations and Discussion Outputs

The final project should produce recommendations, but they must be evidence-led and caveated.

Expected recommendation types:

- countries or sectors that warrant closer monitoring because recovery appears slower, more volatile, or more incomplete
- policy/event periods where activity changed sharply and should be discussed in context
- which metric is safer for which type of reporting statement
- what additional data would improve confidence, such as employment, revenue, restrictions, mobility, business support, or local economic indicators
- what should not be concluded from the data, especially direct causality or direct financial loss

The project should also include a discussion section that covers:

- what the activity metrics reveal
- what they cannot reveal
- where policy context helps interpretation
- where the evidence is suggestive but not conclusive
- which findings are robust enough for stakeholder briefing
- which findings should remain caveated or exploratory

## Candidate Data Scope

The final repo should verify and document exact sources before execution. The current sourcing posture is:

- `Facebook Business Activity Trends during COVID-19` remains the main activity surface, but it is not clearly exposed as a simple public bulk CSV. Meta's public note says access to Business Activity Trends / Commuting Zones is by request for nonprofits or academics; if the original coursework data is already available locally, the future repo should treat that local copy as the practical starting extract and document its provenance.
- The Development Data Partnership example confirms the Business Activity Trends concept and structure: daily business activity quantile information, including COVID-triggered national-level data from March 1, 2020 to November 29, 2022.
- `Oxford COVID-19 Government Response Tracker` is the preferred policy-context source because it is public, documented, and exposes both policy indicators and aggregate response/stringency indices.

| Source | Role |
|---|---|
| Facebook Business Activity Trends during COVID-19 | Main activity surface; expected to come from the original coursework/local extract or authorised Meta/Data for Good access. |
| Oxford COVID-19 Government Response Tracker | Policy restriction / response context; use the GitHub `covid-policy-dataset` compact/simplified files or the Azure Open Datasets curated CSV/Parquet mirror. |
| Country metadata such as continent, income group, population, or region | Comparison and grouping context; use World Bank, Our World in Data, or another documented public source. |
| GADM, Natural Earth, or other boundary files | Geospatial visualization support, depending on the final country/region grain. |
| Major event timeline from trusted public sources | Context for annotated changes; must be source-cited and not treated as causal proof. |

Practical source locations to check first:

- Meta announcement / access route: <https://about.fb.com/news/2020/12/data-for-good-new-tools-to-help-small-businesses-and-communities-during-the-covid-19-pandemic/>
- Development Data Partnership example: <https://datapartnership.org/egypt-economic-monitor/notebooks/activity/business-activity-trends.html>
- OxCGRT final dataset repository: <https://github.com/OxCGRT/covid-policy-dataset>
- OxCGRT Azure Open Datasets mirror: <https://learn.microsoft.com/en-us/azure/open-datasets/dataset-oxford-covid-government-response-tracker>

### Data-Access Gate

Before execution begins, the future repo must make one of these decisions and document it in the data scope note:

| Decision | When it applies | Consequence |
|---|---|---|
| Proceed with FBAT | The original coursework/local FBAT extract is available, legally usable, and sufficiently documented. | Use FBAT as the main activity surface and document provenance, fields, coverage, and limitations. |
| Proceed with authorised FBAT access | Meta/Data for Good or another authorised route provides access. | Use the authorised extract and document access terms, permitted use, and reproducibility limits. |
| Activate fallback activity proxy | FBAT cannot be accessed or cannot be used defensibly. | Re-scope the project to a public activity proxy such as Google Community Mobility, business registry/opening data, public economic indicators, or another documented public source before building analysis. |

The project must not build analysis around FBAT until one of these gates is resolved. If the fallback route is activated, the title, metric dictionary, dashboard pages, and stakeholder claims must be adjusted so the project no longer claims to analyse Facebook Business Activity Trends.

## Analytical Rules

- Do not treat Facebook activity metrics as direct revenue, sales, employment, or business closure counts.
- Do not claim policy causality unless the method supports it. Most analysis will support alignment, timing, association, or plausible context, not causal proof.
- Do not cherry-pick only countries that tell a neat story. Country selection must be justified by geography, income, region, policy contrast, data completeness, and analytical usefulness.
- Use all relevant data for profiling and quality assessment before narrowing into focused comparison views.
- Separate activity metric interpretation from policy/event interpretation.
- Clearly explain the difference between `activity_quantile` and `activity_percentage`.

## Analytical Objectives

### Objective 1: Understand the Data Surface

Build a source profile covering:

- countries/regions
- dates and coverage windows
- business verticals
- missingness
- duplicates
- metric definitions
- anomalies
- geographic granularity

### Objective 2: Explain the Metrics

Define and interpret:

- `activity_quantile`
- `activity_percentage`

The project must explain what each metric measures, how each should be read, and where each can mislead.

### Objective 3: Compare Business Activity Over Time

Analyse activity trajectories for a representative set of countries and sectors.

The analysis should include:

- long-run time-series
- selected country comparisons
- selected sector comparisons
- weekday/weekend or periodic patterns where meaningful
- recovery profile classification

### Objective 4: Link Activity Changes to Policy/Event Context

Overlay or compare activity shifts with:

- lockdown / restriction periods
- reopening periods
- major waves or public events
- policy stringency or response indicators where data permits

The goal is policy-context interpretation, not unsupported causal proof.

### Objective 5: Communicate Geographic Patterns

Use maps and region/country comparison views to show spatial variation in activity or recovery.

The map work must support a finding. It should not be decorative.

### Objective 6: Produce a Stakeholder-Ready Briefing

The final output should include a clear narrative:

- what changed
- where recovery differed
- how policy context helps interpret the changes
- what limitations matter
- what additional data would improve confidence

## Expected Outputs

| Output | Purpose |
|---|---|
| Project brief and requirements note | Define the professional framing and stakeholder questions. |
| Data inventory and metric dictionary | Explain source, coverage, and metric meaning. |
| Reproducible analysis workflow | Python/SQL notebooks or scripts with clear outputs. |
| Data quality note | Missingness, duplicates, anomalies, coverage limits. |
| Time-series analysis notebook/report | Main trend and recovery analysis. |
| Policy/event context analysis | Interprets changes against policy/event periods. |
| Geospatial figures or map pack | Shows spatial variation where analytically useful. |
| Dashboard-ready reporting layer | Defines pages, metrics, filters, and extracts for stakeholder reporting. |
| Stakeholder briefing | Plain-English findings, caveats, and implications. |
| Technical appendix | Methods, definitions, caveats, and reproducibility details. |
| Recommendation and discussion register | Records evidence-led recommendations, caveats, and what not to conclude. |

## Acceptance Criteria

The project is successful if:

- the metrics are explained clearly and not misrepresented
- data quality and coverage are assessed before conclusions
- country and sector selections are justified
- time-series findings are supported by readable visuals and statistics
- policy/event interpretation is cautious and evidence-led
- maps or geospatial views add analytical value
- dashboard/reporting pages are defined around stakeholder decisions, not just chart categories
- recommendations are tied to statistical evidence and caveats
- final briefing is understandable without reading the full notebook
- the project produces evidence of public-sector-style analytical insight

## Non-Completion Conditions

The project is not successful if:

- it only recreates coursework answers without a professional brief
- it uses plots without interpreting the statistical or policy meaning
- it claims causality from policy without a causal method
- it ignores metric limitations
- it hides missingness or data coverage problems
- it relies on a few cherry-picked countries without justification

## Initial Execution Sequence for Future Repo

1. Create repo and copy this brief as `00_project_brief.md`.
2. Build `01_data_scope_and_metric_dictionary.md`.
3. Profile source availability and decide exact country/sector scope.
4. Build data-quality and coverage checks.
5. Perform metric interpretation and exploratory trend analysis.
6. Add policy/event context.
7. Build geospatial views where useful.
8. Define the dashboard/reporting page specification, including page purpose, metric definitions, filters, caveats, and the dashboard-ready extracts each page needs.
9. Build the dashboard-ready reporting layer from the analysed data, keeping stakeholder-facing extracts separate from exploratory notebooks.
10. Build the recommendation and discussion register, tying each proposed action, caution, or follow-on question to the statistical evidence that supports it.
11. Write stakeholder briefing and technical appendix.

## Experience Evidence Target

After execution, this project should support truthful examples around:

- analysing public-interest datasets
- explaining metric limitations
- linking data trends to policy context
- producing visual and written insight for non-technical audiences
- handling missingness and data-quality issues
- working with time-series and geographic comparisons

The project should not claim health-domain experience unless health data is actually introduced and analysed.
