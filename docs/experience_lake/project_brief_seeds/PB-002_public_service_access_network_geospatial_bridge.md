# PB-002: Public-Service Access Network / Geospatial Domain Bridge

## Working Title

**Mapping Primary-Care Access, Pressure, and Inequality with Geospatial and Catchment-Network Analysis**

Shorter portfolio title:

> **Primary-Care Access and Pressure Analytics**

## Project Positioning

This project is the domain-bridge project.

Its purpose is to create evidence that is closer to health, public services, local government, transport, or service-access analytics than the fraud platform can naturally provide.

The selected topic is GP / primary-care access and pressure in England. The project should not reopen the old terrorism-network topic or drift into a generic method showcase. The only permitted route change is the fallback described below if GP practice location, registration, or geography linkage proves impractical.

## Portfolio Role

This project should provide evidence for:

- geospatial analysis with a light catchment/network layer where justified
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

The analyst is asked to use public GP practice, registration, geography, deprivation, and optional network-access data to identify where primary-care access or pressure appears uneven, fragile, or poorly understood.

## Tooling Assumption

The future repo should make the analytical tooling explicit while keeping the method tied to the selected primary-care question:

- Use `Python` and `SQL` for reproducible data preparation, profiling, joins, metric calculation, and analytical checks.
- Use notebooks or scripts for investigation, but keep dashboard/reporting extracts separate from exploratory outputs.
- Use geospatial libraries for access, boundary, distance, and area comparison work.
- Use network or routing libraries only where the catchment/network layer improves the stakeholder answer beyond straight-line distance or provider-density baselines.
- Use a local analytical query layer such as `DuckDB` where SQL modelling or larger extracts make it useful.
- Produce dashboard-ready extracts and a page specification that could be implemented in `Power BI` or an equivalent BI tool.
- A finished `.pbix` file is optional at brief stage; the required output is a defensible reporting-ready layer, metric/method definitions, caveats, and stakeholder-facing recommendations.

## Selected Topic Decision

The selected route is:

> **GP / primary-care access and pressure in England, using geospatial access analysis plus a light catchment/network layer.**

This is the strongest route because it is public-service and NHS-adjacent without pretending to use patient-level clinical data. It can support a credible planning question: which communities appear to face weaker primary-care access or higher pressure, and whether those patterns align with deprivation, geography, or provider availability.

The fallback route is transport/service accessibility only if GP practice location, registration, or geography linkage becomes impractical. That fallback must be an explicit documented decision, not casual topic drift.

| Option | Focus | Strongest evidence |
|---|---|---|
| Selected: Primary-care access and pressure | GP practice locations, registered-patient counts, area populations, deprivation, and access/catchment measures. | NHS/public-service domain bridge, geospatial analysis, inequality insight, pressure interpretation, defensible public data. |
| Fallback: Transport/service accessibility | Access to essential services by public transport or geography. | Civil service / local government / DfT relevance, geospatial network analysis. |

## Core Problem

The project must answer:

> **Which communities appear to face weaker access to GP / primary-care provision or higher provider pressure, how does this vary by deprivation and geography, and what evidence should planners use to prioritise review?**

## Candidate Stakeholders

| Stakeholder | Concern | Required project response |
|---|---|---|
| Service Planning Lead | Which communities or routes appear underserved? | Access/pressure maps, ranking tables, prioritisation evidence. |
| Operational Lead | Where do GP practices or areas appear under higher pressure? | Registered-patient pressure, provider-density/catchment evidence, capacity caveats. |
| Public Health / Equity Lead | Are access gaps associated with deprivation or geography? | Inequality/access comparison by area type. |
| Data / Methods Lead | Are methods and assumptions defensible? | Data-quality note, method explanation, limitations. |
| Executive / Non-technical Audience | What should be improved first? | Plain-English briefing and recommendation table. |

## Stakeholder Concerns and Decision Needs

This project must be designed around a service-planning decision, not around showing that network or geospatial methods can be used.

| Stakeholder concern | Decision or discussion it supports | Required analytical evidence |
|---|---|---|
| Unequal access | Which communities or areas appear to have weaker service access? | Access scores, map views, area rankings, population/deprivation context. |
| Service pressure | Which GP practices or areas appear more exposed to demand or weaker provision? | Provider density, registered-patient pressure, catchment pressure, and baseline/richer-method comparison where data supports it. |
| Geographic inequality | Are access gaps associated with rurality, deprivation, region, or population distribution? | Group comparisons, distribution plots, area-level summaries. |
| Method trust | Can the chosen access or network metric support planning decisions? | Baseline comparison, method explanation, assumptions, sensitivity checks. |
| Prioritisation | Which areas should be reviewed first, and why? | Prioritisation table with evidence, caveats, and recommended next action. |
| Communication | How can complex spatial/network findings be explained to non-specialists? | Maps, ranked tables, concise briefing, method caveats in plain language. |

## Required Dashboard / Reporting Product

The future repo should produce dashboard-ready outputs or a compact reporting product for the selected primary-care access project. The product does not have to be deployed in Power BI, but it must be specified clearly enough that it could become a public-service planning dashboard.

Required reporting pages:

| Page | Purpose | Expected content |
|---|---|---|
| Executive access overview | Show the headline access or pressure picture. | Key access metrics, highest-concern areas, confidence/caveat summary. |
| Primary-care access map | Make spatial variation in GP access visible. | GP practice availability, distance/travel proxy, area score, deprivation overlay where appropriate. |
| Pressure and population view | Show where provider pressure appears higher. | Registered-patient counts, patients per practice or provider proxy, population/deprivation context, high-pressure segments. |
| Inequality and area comparison | Show whether access or pressure differs by area type. | Deprivation, rurality, population, region, local authority, or ICB-style area comparisons where data supports them. |
| Catchment or network access view | Show whether a richer access method changes the baseline story. | Catchment/routing/network-access result, compared against simple distance or provider-density baseline. |
| Priority review table | Support operational planning discussion. | Ranked areas/services with evidence, caveats, and suggested next action. |
| Data and method caveats | Prevent misuse. | Data coverage, assumptions, rejected interpretations, sensitivity notes. |

Minimum filters or breakdowns should be chosen after the source-stack gate is resolved, but may include:

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
- GP practices, neighbourhoods, or planning areas that may need resilience, capacity, or monitoring attention
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

The future repo must verify availability and licensing before execution. The initial sourcing route is:

| Source | Role |
|---|---|
| NHS Organisation Data Service GP Practices / `epraccur` | GP practice identity, address, postcode, and organisation reference data. |
| Patients Registered at a GP Practice | Practice-level registered-patient counts and age/sex breakdowns; main pressure denominator. |
| General Practice Workforce | Optional provider-capacity/pressure extension if practice-level workforce linkage is usable. |
| ONS Open Geography Portal | LSOA/MSOA/local authority boundaries, lookup files, and geographic context. |
| ONS Postcode Directory or equivalent postcode lookup | Join GP practice postcodes to coordinates and small-area geography where needed. |
| English Indices of Deprivation 2019 | Deprivation ranks/deciles for small-area inequality analysis. |
| OpenStreetMap / Geofabrik or OSMnx | Road/walk/travel network source if moving beyond straight-line distance into catchment/network access. |

Practical source locations to check first:

- NHS ODS GP practice data: <https://digital.nhs.uk/services/organisation-data-service/data-search-and-export/csv-downloads/gp-and-gp-practice-related-data>
- ODS `epraccur` report specification: <https://www.odsdatasearchandexport.nhs.uk/referenceDataCatalogue/565791179.html>
- Patients Registered at a GP Practice publication series: <https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice>
- General Practice Workforce publication series: <https://digital.nhs.uk/data-and-information/publications/statistical/general-and-personal-medical-services>
- ONS Open Geography Portal: <https://geoportal.statistics.gov.uk/>
- ONS statistical geography explanation: <https://www.ons.gov.uk/methodology/geography/ukgeographies/statisticalgeographies>
- English Indices of Deprivation 2019: <https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019>
- Geofabrik OpenStreetMap extracts: <https://download.geofabrik.de/>

The project should prefer open data with clear licensing, documented source quality, and enough geographic detail to support credible analysis.

## Analytical Rules

- Do not imply direct patient-level analysis unless patient-level data is actually available and appropriate.
- Do not claim NHS employment or direct operational access.
- Do not treat straight-line distance as real access unless the limitation is explicit.
- Do not use catchment or network-derived scores as if they automatically mean operational importance; explain what each metric captures.
- Do not produce maps without interpreting what the geography means.
- Do not create a complex method unless it improves the stakeholder answer.
- Compare at least one method, baseline, or alternative view where possible, because geospatial and catchment/network results need context.

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

Depending on the validated source stack:

- distance or travel-time access
- provider density
- service availability per population
- deprivation/access relationship
- catchment or route-network access indicators where defensible
- baseline versus richer access-method comparison

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

Use only methods justified by the validated primary-care source stack.

| Method family | Possible use |
|---|---|
| Geospatial joins | Link service locations to areas, populations, deprivation, or boundaries. |
| Distance/travel-time analysis | Estimate access from areas to services. |
| Catchment or route-network analysis | Test whether a richer access method changes the simple distance/provider-density story. |
| Service-area comparison | Compare access or pressure across deprivation, rurality, local authority, or regional groups. |
| Baseline comparison | Compare simple distance or provider count against a richer access/catchment measure. |

## Expected Outputs

| Output | Purpose |
|---|---|
| Project brief | Define topic, stakeholders, question, and acceptance criteria. |
| Source-stack validation note | Explain why the GP/primary-care source stack is suitable, or why the fallback was activated. |
| Source inventory and data-quality note | Document data sources, coverage, missingness, caveats. |
| Method plan | Explain chosen geospatial and catchment/network methods and why they fit. |
| Reproducible analysis workflow | Python/SQL notebooks or scripts. |
| Visual evidence pack | Maps, network diagrams, ranking plots, comparison charts. |
| Dashboard-ready reporting layer | Defines pages, metrics, filters, and extracts for stakeholder reporting. |
| Findings report | Technical interpretation and limitations. |
| Stakeholder briefing | Plain-English recommendations and caveats. |
| Recommendation and discussion register | Records recommended actions, evidence, caveats, and rejected conclusions. |

## Acceptance Criteria

The project is successful if:

- the validated source stack supports a clear public-service or health-adjacent question
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
- catchment or network-derived scores are treated as self-explanatory
- the project ignores deprivation, geography, population, or context where they are essential
- the final story sounds like a classroom demo rather than a public-service analytical brief

## Initial Execution Sequence for Future Repo

1. Create repo and copy this brief as `00_project_brief.md`.
2. Validate the primary-care source stack: ODS GP practice data, registered-patient counts, ONS geography/postcode linkage, deprivation data, and optional workforce/network data.
3. Record the source-stack gate decision: proceed with GP/primary-care access, or activate the transport/service accessibility fallback if GP linkage is not defensible.
4. Build `01_data_scope_and_method_contract.md`, including geography units, join keys, pressure/access definitions, and caveats.
5. Profile sources, geography, joins, missingness, and licensing.
6. Build a baseline primary-care access/pressure view.
7. Add the richer geospatial or catchment-network layer only where it improves the stakeholder answer.
8. Compare baseline and richer method outputs.
9. Produce visual evidence, dashboard-ready extracts, and commentary.
10. Build the recommendation and discussion register.
11. Write stakeholder briefing and technical appendix.

## Dataset Selection Criteria

A dataset is suitable if:

- it is open or legally usable
- it has clear documentation
- it supports a public-service question
- it can be joined to geography, population, service locations, deprivation, or network structure
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
- applying geospatial and catchment/network methods to a real planning problem
- communicating complex methods clearly
- explaining assumptions and limitations
- producing accessible visuals for decision-makers
- recommending improvements based on evidence

This project should become the bridge between technical capability and public-service relevance.
