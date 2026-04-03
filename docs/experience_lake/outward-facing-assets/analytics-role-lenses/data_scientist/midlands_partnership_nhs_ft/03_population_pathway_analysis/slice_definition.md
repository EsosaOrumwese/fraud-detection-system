# Population Pathway Analysis Execution Slice - Midlands Data Scientist Requirement

As of `2026-04-03`

Purpose:
- capture the current execution decision for one bounded population-level and pathway-analysis slice
- anchor that decision to the Midlands Partnership NHS Foundation Trust `Data Scientist` requirement around population analysis, linked data, pathway or outcome analysis, and strong data-meaning discipline
- keep the work narrow enough to produce fast, defensible outward-facing evidence without drifting back into the earlier modelling or analytical-product slices

Boundary:
- this note is not an accomplishment record
- this note is not a claim that a full population-health analogue or full analytics plane has already been implemented
- this note captures the chosen slice, why it fits the requirement, what lenses it uses, and what would count as done
- execution should work from governed data extracts or local bounded views rather than broad platform reruns

Placement rule:
- this file lives under the role-shaped lens tree because it is execution-depth material, not a top-level lens definition
- the role folder should hold multiple employer or role-execution lanes over time
- the employer folder should hold one folder per targeted responsibility slice so repeated work stays grouped and readable

Primary source basis:
- [07_advanced-analytics-data-science.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\07_advanced-analytics-data-science.md)
- [03_data-quality-governance-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\03_data-quality-governance-analytics.md)
- [01_operational-performance-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\01_operational-performance-analytics.md)
- [04_analytics-engineering-data-product.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\04_analytics-engineering-data-product.md)
- [data-analytics-engineering-science.ideal-candidate-profiles.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.ideal-candidate-profiles.md)
- [data-analytics-engineering-science.job-ads.evidence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.job-ads.evidence.md)

---

## 1. Requirement Being Targeted

The requirement being targeted here is the Midlands `Data Scientist` expectation around:
- population-level analysis over linked data
- cohort identification and segmentation
- pathway or outcome analysis
- understanding dataset meaning, reporting consistency, and governance-correct use of linked data

This note exists because that requirement is not asking only for a model or only for an analytical product. It is asking for proof that linked governed data can be read as a population, segmented into meaningful cohorts, interpreted as a pathway with outcomes, and handled with enough source discipline to make the analysis trustworthy.

## 2. Lens Mapping For This Requirement

The primary owner lenses for this requirement are:
- `07 - Advanced Analytics and Data Science`
- `03 - Data Quality, Governance, and Trusted Information Stewardship`

They are co-owners because this requirement is really two things at once:
- `07` owns the population/cohort/pathway/outcome analysis
- `03` owns the source meaning, authoritative usage, reconciliation, lineage, and trust rules needed to make that analysis defensible

The main support lens is:
- `01 - Operational Performance Analytics`

That matters because the pathway or outcome analysis must still be interpreted as an operating workflow:
- where pressure enters
- how work converts
- where delay or burden concentrates
- what outcomes result

The optional support lens is:
- `04 - Analytics Engineering and Analytical Data Product`

That lens only enters if the final output is packaged as a reusable linked analytical product rather than left as a one-off analysis pack.

The practical split is:
- `03` pins source meaning, trusted fields, join rules, and fit-for-use checks
- `07` turns the governed linked population into cohorts, segmentation, pathway reading, and outcome comparison
- `01` interprets the pathway as an operating problem rather than just a descriptive table
- `04` packages the result into reusable downstream views if needed

Ownership order:
- `07 -> 03 -> 01 -> 04`

Execution order:
- `03 -> 07 -> 01 -> 04`

That execution order is deliberate. The linked data and trust boundary need to be pinned before the cohort and pathway story can be read cleanly.

## 3. Chosen Bounded Slice

The bounded slice chosen for this requirement is:

`Linked cohort and pathway analysis over one bounded suspicious-flow population`

The proof object is:

`population_pathway_analysis_v1`

This is the preferred slice because it is the cleanest analogue for the PHM- and NHS-data-shaped requirement inside the fraud platform. It gives one bounded population, one linked pathway from event to case to outcome, one governed trust layer, one small cohort framework, and one operational interpretation pack.

The slice is defined as:
- `Base analytical unit`: `flow_id`
- `Primary analytical population`: one bounded suspicious-flow population from a governed local run
- `Primary linked pathway`: suspicious flow -> case creation/progression -> outcome
- `Primary downstream summaries`: cohort metrics, pathway metrics, outcome comparisons, and one operational interpretation note
- `Deployment meaning for this slice`: not a live service; instead, a governed linked analytical slice with trusted-source rules, cohort definitions, reusable views, and action-oriented interpretation

## 4. Why This Slice Was Chosen

This slice fits the requirement strongly because it gives direct room for:
- population definition
- linked data interpretation
- cohort identification and segmentation
- pathway and outcome analysis
- source meaning and governance rules
- reporting consistency across reused definitions

Just as importantly, it avoids drift.

The intention is not to:
- imitate literal NHS datasets or pretend the fraud platform is a healthcare warehouse
- rerun the first modelling slice as another scoring exercise
- turn the second analytical-product slice into a catch-all linked-data programme
- let the whole platform collapse into one undifferentiated `flow_id` claim

The intention is to build one credible analogue:
- suspicious-flow population as the service population
- event -> case -> outcome chain as the service pathway
- authoritative-source rules, join logic, and KPI consistency as the data-meaning and governance discipline

## 5. Execution Posture

The default execution stack for this slice is:
- `SQL` for source mapping, join validation, reconciliation, linked-base construction, cohort summaries, and pathway metrics
- `Python` only where useful for a compact analytical notebook or figure generation layer
- notes and SQL-backed outputs as the main reproducibility surface

The execution substrate should be:
- governed local extracts
- bounded local views
- materialised linked analytical slices derived from the governed world

The default local working assumption is that execution can begin from a bounded run such as:
- `runs/local_full_run-7`

That should still be treated as:
- a bounded governed extract
- not the whole world
- not permission to overclaim full-platform population analytics coverage

## 6. Lens-by-Lens Execution Checklist

### 6.1 Lens 03 - Data Quality, Governance, and Trusted Information Stewardship

1. Define the canonical vocabulary for the slice:
- what counts as the population
- what counts as the pathway
- what counts as the outcome
- what counts as a cohort
2. Pin authoritative sources for event, flow, case, and outcome fields.
3. Document join rules across event, flow, case, and outcome surfaces.
4. Run fit-for-use checks for granularity, time boundary, and outcome coverage.
5. Run reconciliation checks across event-to-flow, flow-to-case, and case-to-outcome linkage.
6. Record lineage and usage boundaries for downstream reuse.

### 6.2 Lens 07 - Advanced Analytics and Data Science

1. Define `flow_id` as the base analytical unit for the linked population.
2. Build one bounded linked population base joining event, flow, case, and outcome surfaces.
3. Define a compact cohort framework that is computable and distinct.
4. Compare cohort-level yield, timing, burden, and pathway differences.
5. Perform pathway analysis from suspicious flow through case progression to final outcome.
6. Package the findings into one comparison table, one cohort summary, one pathway summary, and one intervention-opportunity note.

### 6.3 Lens 01 - Operational Performance Analytics

1. Define a small KPI family:
- suspicious-flow volume
- suspicious-to-case conversion
- aged or delayed case burden
- case-to-outcome yield
- turnaround by cohort
2. Read the linked pathway as an operating system rather than a descriptive data table.
3. Identify one real operating problem in the bounded slice:
- backlog-prone cohort
- slow-converting cohort
- high-burden / low-yield cohort
- concentrated high-value cohort
4. Write one operational interpretation note describing where pressure or value concentrates.

### 6.4 Lens 04 - Analytics Engineering and Analytical Data Product

1. Create one reusable linked analytical base view.
2. Create one cohort-ready output.
3. Create one reporting-ready output.
4. Write one lightweight product contract describing grain, key fields, authoritative sources, and downstream purpose.

## 7. Cohort Framework For This Slice

The cohort framework should stay small and operationally meaningful.

The preferred first-pass cohort family is:
- `fast_converting_high_yield`
- `slow_converting_high_yield`
- `high_burden_low_yield`
- `low_burden_low_yield`

This is preferred over looser conceptual cohort sets because:
- it can be computed from pathway timing and outcome fields
- it is easier to compare consistently across outputs
- it is easier to translate into an operational problem statement

If the bounded data does not support all four cleanly, reduce the set rather than invent weak cohort boundaries.

## 8. Minimum Artifact Pack

The smallest useful proof pack for this requirement is:
- one linked population base SQL view
- one reconciliation and fit-for-use pack
- one trusted-source and vocabulary pack
- one cohort-rules note
- one cohort and pathway analysis notebook or script-backed summary
- one KPI summary view
- one operational interpretation note
- one product contract or lineage note

Suggested artefact names:
- `vw_population_pathway_base_v1.sql`
- `population_pathway_reconciliation_v1.sql`
- `population_pathway_fit_for_use_v1.md`
- `population_pathway_lineage_v1.md`
- `population_pathway_data_dictionary_v1.md`
- `population_cohort_rules_v1.md`
- `population_pathway_kpis_v1.sql`
- `population_pathway_operating_note_v1.md`
- `population_pathway_product_contract_v1.md`

## 9. Definition Of Done

This slice should be treated as complete only when all of the following are true:
- the bounded population is clearly defined
- authoritative sources are pinned
- the join path is documented and reconciled
- 3 to 4 cohorts are defined and analysed
- one pathway and outcome pack exists
- one operating problem statement exists
- one reusable linked analytical product exists
- the whole slice can be explained without breaking the truth boundary

## 10. Truth Boundary

As of this note, the correct claim is:
- the slice has been selected
- the lens mapping is clear
- the proof object is distinct from the first two slices
- the population, pathway, and trust posture are defined
- the execution path is defined

The correct claim is not:
- that the linked base has already been built
- that the join path is already proven clean
- that the final cohorts are already validated
- that pathway and outcome differences are already known
- that the full governance-heavy population-analysis responsibility has already been exhausted

This note therefore exists to protect against overclaiming while preserving momentum toward a fast, defensible claim.

## 11. XYZ Claim Surfaces This Slice Is Aiming Toward

The strongest eventual claim shape for this slice is:

> Built a governed linked-data population and pathway analysis layer for fraud operations, as measured by successful linkage of `[N]` governed data surfaces, reconciliation discrepancy below `[X]%`, and cohort-level pathway and outcome analysis that revealed `[Y]x` variation in yield or turnaround across defined segments, by defining a bounded suspicious-flow population, constructing reusable cohort and pathway views over event, flow, case, and outcome truth, validating source meaning and join rules, and packaging the results into operational KPI summaries and reusable analytical outputs.

A governance-heavier version is:

> Improved the trust and usability of linked cohort and pathway analysis, as measured by validated join consistency, documented authoritative-source rules, and reuse of one canonical cohort and KPI definition set across multiple outputs, by building a governed population-pathway analytical slice over fraud event, flow, case, and outcome data and packaging it with reconciliation checks, lineage notes, and reporting-ready views.

A shorter recruiter-readable version is:

> Delivered linked population, cohort, and pathway analysis over governed fraud data, as measured by trusted multi-surface linkage, consistent cohort definitions, and clear differentiation in outcome and turnaround patterns across segments, by combining event, flow, case, and outcome data into reusable analytical views and turning the results into action-oriented operational summaries.

## 12. Immediate Next-Step Order

The correct build order remains:
1. `03` trusted-source rules, vocabulary, and reconciliation gate
2. `07` cohort, segmentation, pathway, and outcome analysis
3. `01` KPI framing and operating problem interpretation
4. `04` reusable packaging of the linked analytical slice

That order matters because it prevents the slice from collapsing into descriptive segmentation without a defensible trust boundary underneath.
