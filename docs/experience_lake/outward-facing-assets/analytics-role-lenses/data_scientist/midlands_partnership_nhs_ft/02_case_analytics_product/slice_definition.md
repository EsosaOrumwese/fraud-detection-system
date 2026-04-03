# Case Analytics Product Execution Slice - Midlands Data Scientist Requirement

As of `2026-04-03`

Purpose:
- capture the current execution decision for one bounded analytics-engineering slice
- anchor that decision to a real requirement from the Midlands Partnership NHS Foundation Trust `Data Scientist` profile
- keep the work narrow enough to produce fast, defensible outward-facing evidence without drifting back into the previous modelling-first slice

Boundary:
- this note is not an accomplishment record
- this note is not a claim that a full analytics plane has already been implemented
- this note captures the chosen slice, why it fits the requirement, what lenses it uses, and what would count as done
- execution should work from governed data extracts or local bounded views rather than broad platform reruns

Placement rule:
- this file lives under the role-shaped lens tree because it is execution-depth material, not a top-level lens definition
- the role folder should hold multiple employer or role-execution lanes over time
- the employer folder should hold one folder per targeted responsibility slice so repeated work stays grouped and readable

Primary source basis:
- [04_analytics-engineering-data-product.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\04_analytics-engineering-data-product.md)
- [09_analytical-delivery-operating-discipline.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\09_analytical-delivery-operating-discipline.md)
- [03_data-quality-governance-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\03_data-quality-governance-analytics.md)
- [07_advanced-analytics-data-science.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\07_advanced-analytics-data-science.md)
- [data-analytics-engineering-science.ideal-candidate-profiles.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.ideal-candidate-profiles.md)
- [data-analytics-engineering-science.job-ads.evidence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.job-ads.evidence.md)

---

## 1. Requirement Being Targeted

The requirement being targeted here is the Midlands `Data Scientist` expectation around:
- designing or maintaining analytical datasets, pipelines, transformations, and reproducible workflows
- using engineering-grade analytical preparation so analysis becomes production-usable rather than remaining ad hoc
- extracting, cleaning, transforming, and linking large datasets into stable downstream analytical products
- keeping analytical pipelines, features, and outputs version-controlled, documented, and reusable

This note exists because that requirement is not mainly asking for a model. It is asking for proof that analytical preparation can be designed, maintained, validated, and handed over as a governed product.

## 2. Lens Mapping For This Requirement

The primary owner lens for this requirement is:
- `04 - Analytics Engineering and Analytical Data Product`

That is the direct owner because it explicitly covers:
- analytical datasets
- reusable analytical tables and views
- model-ready and reporting-ready products
- analytical grains and join paths
- downstream packaging for reporting, modelling, and decision support

The essential support lenses are:
- `09 - Analytical Delivery Operating Discipline`
- `03 - Data Quality, Governance, and Trusted Information Stewardship`

The adjacent proof lens is:
- `07 - Advanced Analytics and Data Science`

The practical split is:
- `04` builds the analytical product
- `09` makes it reproducible, versioned, and handover-safe
- `03` makes it trustworthy and fit for use
- `07` proves the product serves real downstream analysis rather than empty plumbing

## 3. Chosen Bounded Slice

The bounded slice chosen for this requirement is:

`Case-centric analytical preparation layer with one model-ready output and one reporting-ready output`

The proof object is:

`case_analytics_product_v1`

This is the preferred slice because it answers the responsibility directly. It proves analytical-product design, transformation, linkage, validation, lineage, and reproducibility without collapsing back into a modelling-first posture.

The slice is defined as:
- `Natural grain`: `case_id`
- `Primary purpose`: one governed analytical preparation layer for downstream modelling and reporting
- `Primary downstream outputs`: `case_model_ready_v1` and `case_reporting_ready_v1`
- `Deployment meaning for this slice`: not a live application surface; instead, a stable analytical product with explicit transformations, trust checks, and regeneration logic that another analyst could reuse

## 4. Why This Slice Was Chosen

This slice fits the requirement strongly because it gives direct room for:
- dataset design
- source linkage and transformation
- reproducible SQL-backed analytical preparation
- fit-for-use and reconciliation checks
- model-ready and reporting-ready downstream outputs
- handover-safe analytical delivery

Just as importantly, it avoids drift.

The intention is not to:
- rerun the first modelling slice at another grain
- build another full predictive programme
- broaden into a full data-platform refactor
- treat the whole platform as one universal `flow_id` world

The intention is to get one credible, inspectable, reusable case-centric analytical product to the point where it can support a strong outward-facing claim for this responsibility.

## 5. Execution Posture

The default execution stack for this slice is:
- `SQL` for source mapping, joins, transformations, analytical base construction, downstream outputs, and fit-for-use checks
- `Python` only where needed for a light analytical consumer or validation helper
- notebooks only as optional consumer evidence, not as the backbone of the reproducibility story

The execution substrate should be:
- governed local extracts
- bounded local views
- materialised analytical products derived from the governed world

The default local working assumption is that execution can begin from a bounded run such as:
- `runs/local_full_run-7`

That should still be treated as:
- a bounded governed extract
- not the whole world
- not permission to overclaim full-platform analytical coverage

## 6. Lens-by-Lens Execution Checklist

### 6.1 Lens 04 - Analytics Engineering and Analytical Data Product

1. Define the product contract for `case_analytics_product_v1`.
2. Pin the consumer outputs: `case_model_ready_v1` and `case_reporting_ready_v1`.
3. Choose the minimum governed source chain needed for case-level analytical preparation.
4. Build one stable case-grain analytical base.
5. Split that base into one model-ready and one reporting-ready downstream product.
6. Materialise the shaping logic as stable SQL-backed outputs rather than one-off extracts.

### 6.2 Lens 09 - Analytical Delivery Operating Discipline

1. Pin stable definitions for case, target, feature-only fields, and reporting-only fields.
2. Version the SQL shaping logic and any downstream consumer script.
3. Document join keys, transformation rules, exclusions, and caveats.
4. Create a regeneration path that another analyst can follow.
5. Package the product for handover and reuse.

### 6.3 Lens 03 - Data Quality, Governance, and Trusted Information Stewardship

1. Confirm the chosen sources are fit for case-level analytical use.
2. Reconcile event-to-case and case-to-outcome coherence.
3. Check for missing keys, duplicated relationships, dropped records, and inconsistent totals.
4. Record authoritative-source rules for chronology, outcome, and downstream-safe fields.
5. Write lineage and usage boundaries that control how consumers should rely on the product.

### 6.4 Lens 07 - Advanced Analytics and Data Science

1. Point one small analytical consumer at `case_model_ready_v1`.
2. Use it for one bounded case-yield, case-cohort, or prioritisation summary.
3. Stop once the product has been proven analytically useful.

## 7. Minimum Artifact Pack

The smallest useful proof pack for this requirement is:
- one case-grain analytical base build
- one model-ready case output
- one reporting-ready case output
- one fit-for-use and reconciliation check pack
- one lineage and usage-boundary pack
- one regeneration guide
- one light downstream analytical consumer

Suggested artefact names:
- `vw_case_analytics_base_v1.sql`
- `vw_case_model_ready_v1.sql`
- `vw_case_reporting_ready_v1.sql`
- `case_product_lineage_notes_v1.md`
- `case_product_fit_for_use_checks_v1.md`
- `README_regeneration_v1.md`
- `case_product_consumer_summary_v1.md`

## 8. Definition Of Done

This slice should be treated as complete only when all of the following are true:
- one stable case-grain analytical base exists
- one model-ready and one reporting-ready output are derived from it
- critical joins and downstream totals reconcile
- lineage, assumptions, and usage boundaries are written down
- the whole product can be regenerated from versioned logic
- one real analytical consumer uses the model-ready output successfully

## 9. Truth Boundary

As of this note, the correct claim is:
- the slice has been selected
- the lens mapping is clear
- the proof object is distinct from the first modelling slice
- the execution path is defined

The correct claim is not:
- that the case-grain product has already been built
- that the joins are already proven clean
- that downstream consumers have already adopted the outputs
- that the full analytics-engineering responsibility has already been exhausted

This note therefore exists to protect against overclaiming while preserving momentum toward a fast, defensible claim.

## 10. XYZ Claim Surfaces This Slice Is Aiming Toward

The strongest eventual claim shape for this slice is:

> Built a reusable analytical preparation layer for downstream fraud modelling and reporting, as measured by successful reuse across model-ready and reporting-ready outputs, validated reconciliation of critical joins and transformations, and reproducible regeneration from version-controlled SQL and script workflows in under `[N]` minutes, by designing a case-centric governed data product that linked event, context, case, and outcome data into stable analytical views with documented lineage, assumptions, and usage boundaries.

A shorter recruiter-readable version is:

> Built a reusable analytical data product for downstream modelling and reporting, as measured by validated join consistency, reproducible regeneration, and reuse across multiple analytical outputs, by shaping governed multi-source fraud data into stable SQL views, documented model-ready slices, and reporting-ready analytical tables.

The closest direct response to the requirement is:

> Made analysis production-usable, as measured by reusable model-ready and reporting-ready datasets, documented transformation logic and lineage, and reproducible regeneration from controlled workflows, by designing and maintaining a governed analytical preparation layer over linked event, context, case, and outcome data.

## 11. Immediate Next-Step Order

The correct build order remains:
1. `04` core analytical-product build
2. `09` reproducibility and regeneration pack
3. `03` trust and fit-for-use pack
4. `07` light analytical-consumer proof

That order matters because it prevents the slice from collapsing back into model-first work with only superficial data-product packaging added afterward.
