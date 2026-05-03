# PB-002: Public-Service Access Network / Geospatial Domain Bridge

## Working Title

**Mapping Public-Service Access, Pressure, and Inequality with Network and Geospatial Analysis**

Shorter portfolio title:

> **Public-Service Access and Network Inequality Analytics**

## Project Positioning

This project is the domain-bridge project.

Its purpose is to create evidence that is closer to health, public services, local government, transport, or service-access analytics than the fraud platform can naturally provide.

The final topic should be chosen based on dataset quality. The project should not repeat the old terrorism-network topic unless there is a strong reason. The preferred direction is safer and more relevant to public-sector roles: access to services, pathway pressure, geographic inequality, referral/service networks, public feedback, or transport accessibility.

## Portfolio Role

This project should provide evidence for:

- network analysis, geospatial analysis, text analysis, or a deliberate combination
- public-service or health-adjacent analytical thinking
- inequality/access/pressure interpretation
- readable visual communication
- research framing and method justification
- baseline comparison or alternative method comparison
- stakeholder-facing recommendations or caveats

It should not be forced to prove production data engineering or fraud-platform depth.

## Delivery Role

The assumed role is:

> **Data Analyst / Data Scientist supporting public-service planning and access insight.**

The analyst is asked to use network, geospatial, or text methods to identify where service access, service pressure, or user need appears uneven, fragile, or poorly understood.

## Tooling Assumption

The future repo should make the analytical tooling explicit without forcing a method before the dataset route is selected:

- Use `Python` and `SQL` for reproducible data preparation, profiling, joins, metric calculation, and analytical checks.
- Use notebooks or scripts for investigation, but keep dashboard/reporting extracts separate from exploratory outputs.
- Use geospatial, network, or text-analysis libraries only where the chosen route justifies them.
- Use a local analytical query layer such as `DuckDB` where SQL modelling or larger extracts make it useful.
- Produce dashboard-ready extracts and a page specification that could be implemented in `Power BI` or an equivalent BI tool.
- A finished `.pbix` file is optional at brief stage; the required output is a defensible reporting-ready layer, metric/method definitions, caveats, and stakeholder-facing recommendations.

## Topic Decision

The final repo should choose one of these paths after dataset scouting.

| Option | Focus | Strongest evidence |
|---|---|---|
| A: Healthcare/service access geography | Distance, travel time, deprivation, provider availability, underserved areas. | NHS/public-service domain bridge, geospatial analysis, inequality insight. |
| B: Referral or pathway network | Movement between services, bottlenecks, centrality, pathway pressure. | Network methods, operational service flow, bottleneck analysis. |
| C: Transport/service accessibility | Access to essential services by public transport or geography. | Civil service / local government / DfT relevance, geospatial network analysis. |
| D: Public feedback text analysis | Complaints, surveys, consultation responses, service reviews. | Text analysis, theme extraction, stakeholder communication. |

Preferred starting option:

> **Option A or C**, because geospatial access and public-service inequality are easier to frame credibly for NHS, local government, DfT, and civil service roles if suitable data is available.

## Core Problem

The project must answer:

> **Where do people, communities, or service users appear to face weaker access, higher service pressure, or poorer service visibility, and what evidence should planners use to prioritise improvement?**

The exact wording should be narrowed once the dataset is chosen.

## Candidate Stakeholders

| Stakeholder | Concern | Required project response |
|---|---|---|
| Service Planning Lead | Which communities or routes appear underserved? | Access/pressure maps, ranking tables, prioritisation evidence. |
| Operational Lead | Where are bottlenecks or high-pressure nodes? | Network centrality, flow/pathway concentration, capacity caveats. |
| Public Health / Equity Lead | Are access gaps associated with deprivation or geography? | Inequality/access comparison by area type. |
| Data / Methods Lead | Are methods and assumptions defensible? | Data-quality note, method explanation, limitations. |
| Executive / Non-technical Audience | What should be improved first? | Plain-English briefing and recommendation table. |

## Stakeholder Concerns and Decision Needs

This project must be designed around a service-planning decision, not around showing that network or geospatial methods can be used.

| Stakeholder concern | Decision or discussion it supports | Required analytical evidence |
|---|---|---|
| Unequal access | Which communities or areas appear to have weaker service access? | Access scores, map views, area rankings, population/deprivation context. |
| Service pressure | Which service nodes or areas appear more exposed to demand or network dependence? | Provider density, catchment pressure, centrality or flow concentration where data supports it. |
| Geographic inequality | Are access gaps associated with rurality, deprivation, region, or population distribution? | Group comparisons, distribution plots, area-level summaries. |
| Method trust | Can the chosen access or network metric support planning decisions? | Baseline comparison, method explanation, assumptions, sensitivity checks. |
| Prioritisation | Which areas should be reviewed first, and why? | Prioritisation table with evidence, caveats, and recommended next action. |
| Communication | How can complex spatial/network findings be explained to non-specialists? | Maps, ranked tables, concise briefing, method caveats in plain language. |

## Required Dashboard / Reporting Product

The future repo should produce dashboard-ready outputs or a compact reporting product. The product does not have to be deployed in Power BI, but it must be specified clearly enough that it could become a public-service planning dashboard.

The reporting product must be selected after the final topic route is chosen. The core pages below are required for every route; the route-specific pages are only required where the selected data and method support them. This prevents the project from forcing network, geospatial, or text analysis for its own sake.

Core reporting pages:

| Page | Purpose | Expected content |
|---|---|---|
| Executive access overview | Show the headline access or pressure picture. | Key access metrics, highest-concern areas, confidence/caveat summary. |
| Priority review table | Support operational planning discussion. | Ranked areas/services with evidence, caveats, and suggested next action. |
| Data and method caveats | Prevent misuse. | Data coverage, assumptions, rejected interpretations, sensitivity notes. |

Route-specific reporting pages:

| Selected route | Required pages where supported by the data | Expected content |
|---|---|---|
| Healthcare/service access geography | Geographic access map; inequality and area comparison; access-threshold or catchment view. | Map of access, service availability, travel/distance proxy, area scores, deprivation/rurality/population comparisons. |
| Referral or pathway network | Network or pathway pressure view; bottleneck/centrality comparison; pathway concentration table. | Centrality, flow concentration, node/edge ranking, baseline comparison, sensitivity notes. |
| Transport/service accessibility | Geographic access map; route/travel-time access view; area comparison. | Travel-time or distance proxy, service availability, access thresholds, local authority or neighbourhood ranking. |
| Public feedback text analysis | Theme and issue profile; service/geography issue concentration; examples and caveats. | Topic/theme prevalence, sentiment or concern patterns where defensible, area/service cross-tab, representative short excerpts if legally and ethically usable. |

Minimum filters or breakdowns should be chosen after dataset selection, but may include:

- geography or local authority
- deprivation group
- rural/urban classification
- service type
- access threshold or travel-distance band
- population group where available
- time period if the dataset is temporal

## Expected Recommendations and Discussion Outputs

The project must produce a recommendations and discussion section that is tied to evidence.

Expected recommendation types:

- areas or communities that should be prioritised for review because access appears weaker
- service nodes or routes that may need resilience, capacity, or monitoring attention
- data gaps that prevent stronger operational conclusions
- whether the richer method changes the story compared with a simple baseline
- which findings are appropriate for planning discussion and which remain exploratory

The discussion must cover:

- what the selected access/pressure metric actually measures
- what the method does not measure
- whether geography, deprivation, population, or network structure changes the interpretation
- where findings are robust versus assumption-sensitive
- what decision-makers should do next and what they should not conclude

## Candidate Data Sources

The future repo must verify availability and licensing before execution.

Possible source categories:

- NHS or public-service location datasets
- GP practice, hospital, urgent care, pharmacy, or service directory data
- ONS geography and population estimates
- deprivation indices
- public transport access data
- road or public transport network data
- local authority boundaries
- service usage, waiting, referral, or pressure indicators if publicly available
- public consultation or service review text if using text analysis

The project should prefer open data with clear licensing, documented source quality, and enough geographic detail to support credible analysis.

## Analytical Rules

- Do not imply direct patient-level analysis unless patient-level data is actually available and appropriate.
- Do not claim NHS employment or direct operational access.
- Do not treat straight-line distance as real access unless the limitation is explicit.
- Do not use network centrality as if it automatically means operational importance; explain what the metric captures.
- Do not produce maps without interpreting what the geography means.
- Do not create a complex method unless it improves the stakeholder answer.
- Compare at least one method, baseline, or alternative view where possible, because network/text/geospatial results need context.

## Analytical Objectives

### Objective 1: Define the Service Access Question

Clarify:

- service type
- population or area unit
- access definition
- pressure or need proxy
- stakeholder decision
- limitations

### Objective 2: Build the Data and Geography Base

Create:

- source inventory
- geographic unit dictionary
- location cleaning rules
- join rules
- data-quality checks
- missingness and coverage profile

### Objective 3: Measure Access or Pressure

Depending on dataset:

- distance or travel-time access
- provider density
- service availability per population
- deprivation/access relationship
- network centrality or bottleneck indicators
- pathway or referral concentration
- text themes and sentiment if text route is chosen

### Objective 4: Compare Areas or Groups

The project should compare:

- urban/rural areas
- high/low deprivation
- regions/local authorities
- service types
- high/low access groups
- baseline versus improved method where possible

### Objective 5: Communicate the Evidence

Produce visuals that explain:

- where access appears weaker
- where pressure appears concentrated
- which findings are robust
- which findings are assumption-sensitive
- what decision-makers should consider first

## Candidate Methods

Use only methods justified by the chosen dataset.

| Method family | Possible use |
|---|---|
| Geospatial joins | Link service locations to areas, populations, deprivation, or boundaries. |
| Distance/travel-time analysis | Estimate access from areas to services. |
| Network analysis | Identify central, fragile, or bottleneck nodes/edges. |
| Community detection | Identify service clusters or access regions where meaningful. |
| Centrality measures | Compare node importance, with caveats. |
| Text analysis | Extract themes from complaints/reviews/consultation responses. |
| Baseline comparison | Compare simple distance, provider count, or centrality against a richer measure. |

## Expected Outputs

| Output | Purpose |
|---|---|
| Project brief | Define topic, stakeholders, question, and acceptance criteria. |
| Dataset selection note | Explain why the chosen dataset is suitable and what was rejected. |
| Source inventory and data-quality note | Document data sources, coverage, missingness, caveats. |
| Method plan | Explain chosen network/geospatial/text methods and why they fit. |
| Reproducible analysis workflow | Python/SQL notebooks or scripts. |
| Visual evidence pack | Maps, network diagrams, ranking plots, comparison charts. |
| Dashboard-ready reporting layer | Defines pages, metrics, filters, and extracts for stakeholder reporting. |
| Findings report | Technical interpretation and limitations. |
| Stakeholder briefing | Plain-English recommendations and caveats. |
| Recommendation and discussion register | Records recommended actions, evidence, caveats, and rejected conclusions. |

## Acceptance Criteria

The project is successful if:

- the chosen dataset supports a clear public-service or health-adjacent question
- the method matches the question rather than showing off technique
- data quality and licensing are documented
- geographic or network assumptions are explicit
- results include comparisons or baselines where meaningful
- visuals are readable and tied to findings
- dashboard/reporting pages are organised around stakeholder decisions
- recommendations are evidence-led and caveated
- the final project provides a credible domain bridge for public-sector/NHS-style applications without claiming direct employment experience

## Non-Completion Conditions

The project is not successful if:

- the topic is chosen only because the method looks impressive
- maps or networks are decorative rather than explanatory
- access or pressure is claimed without a defensible proxy
- centrality scores are treated as self-explanatory
- the project ignores deprivation, geography, population, or context where they are essential
- the final story sounds like a classroom demo rather than a public-service analytical brief

## Initial Execution Sequence for Future Repo

1. Start with dataset scouting and choose Option A, B, C, or D.
2. Write the project-specific `00_project_brief.md`.
3. Build `01_data_scope_and_method_contract.md`.
4. Profile sources, geography, and joins.
5. Build a baseline access/pressure view.
6. Add network/geospatial/text method layer.
7. Compare baseline and richer method outputs.
8. Produce visual evidence and commentary.
9. Write stakeholder briefing and technical appendix.

## Dataset Selection Criteria

A dataset is suitable if:

- it is open or legally usable
- it has clear documentation
- it supports a public-service question
- it can be joined to geography, population, service locations, text, or network structure
- it has enough coverage for meaningful comparison
- it does not require pretending to have private operational access

Reject a dataset if:

- the licence is unclear
- the data is too sparse for the intended claim
- the topic creates reputational or ethical risk without analytical benefit
- the method would be forced onto the data

## Experience Evidence Target

After execution, this project should support truthful examples around:

- selecting and scoping a public-service dataset
- applying network, geospatial, or text methods to a real planning problem
- communicating complex methods clearly
- explaining assumptions and limitations
- producing accessible visuals for decision-makers
- recommending improvements based on evidence

This project should become the bridge between technical capability and public-service relevance.
