# Execution Plan - Patient-Level Dataset Stewardship Slice

As of `2026-04-04`

Purpose:
- turn the chosen InHealth dataset-stewardship slice into a concrete execution order tied to bounded governed analytical surfaces already available in the repo
- keep the work stewardship-first, trust-first, and tightly scoped to one detailed monthly reporting dataset rather than broad reporting delivery or broad quality-programme work
- prove maintenance, validation, and reconciliation of a detailed reporting dataset without drifting into full-platform raw-data handling
- keep execution memory-safe by profiling and shaping only the bounded periods, fields, and grains required for the slice rather than treating the raw run like unlimited in-memory working space

Execution substrate:
- governed local artefacts already available in `artefacts/analytics_slices/`
- governed detailed platform surfaces accessible through bounded SQL scans
- compact outputs already established from earlier slices where reuse is honest and efficient
- new slice outputs to be written under `artefacts/analytics_slices/data_analyst/inhealth_group/02_patient_level_dataset_stewardship/`

Primary rule:
- define the dataset grain, key, and field-authority rules first
- profile the candidate source path before materialising any maintained dataset
- run validation and reconciliation checks before claiming downstream reporting safety
- materialise one maintained detailed dataset only after the trust rules are stable
- package the maintenance and reporting-protection notes only after the dataset checks are real
- never load broad raw detailed surfaces into pandas or any other in-memory dataframe layer before the SQL gate has already reduced them to compact maintained outputs

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- the repo already contains governed detailed surfaces suitable for building one bounded case-level reporting dataset honestly
- one monthly programme-style window can be selected without needing a broad raw-history rebuild
- one detailed reporting grain can be defined with a stable key and a manageable set of authoritative fields
- one downstream reporting-safe summary can be shown from the maintained dataset without turning the slice into another reporting-delivery lane

Candidate first-pass reusable foundations:
- Midlands governed analytical-data-shaping patterns where grain and field-authority logic are already proven conceptually
- HUC discrepancy and reporting-trust control patterns where validation and reconciliation logic is already proven conceptually
- InHealth `01_reporting_support_for_operational_and_regional_teams` monthly lane where one downstream reporting-safe summary can be aligned honestly

Working assumption about the bounded stewardship question:
- the maintained dataset should support one monthly reporting use safely
- the slice should prove that dataset stewardship comes before reporting trust
- the slice should remain detailed-dataset-first rather than collapsing into another KPI-pack exercise

Important warning:
- those assumptions must be tested rather than carried forward casually
- if the candidate detailed source path is not stable enough, adapt early by narrowing the dataset scope rather than forcing a wider build

## 2. Trust-First And Dataset-First Posture

This slice must not begin as a reporting-pack or figure-first exercise.

The correct posture is:
- define the detailed dataset grain first
- define the key and authoritative fields first
- profile the candidate records first
- run validation and reconciliation checks first
- materialise the maintained dataset second
- prove one downstream reporting-safe use only after the maintained dataset is stable
- use Python only after the maintained dataset and compact trust outputs already exist in stable form

This matters because the InHealth responsibility here is about maintaining, validating, and reconciling patient-level datasets, not about decorating downstream outputs.

## 2A. Memory And Query Discipline

This slice must be executed with explicit memory discipline.

The raw run contains very large detailed surfaces, so the correct posture is:
- do not pull broad raw parquet surfaces into pandas
- do not run wide profiling queries across full history unless the slice truly needs them
- do not assume one monthly window means all detailed rows for that period can be inspected casually in memory

The correct query discipline is:
- start with summary-stats and metadata profiling before any maintained-dataset build
- use `DuckDB` or SQL-style scans with predicate pushdown
- filter the stewardship window at scan time
- project only the fields needed for profiling, grain checks, field-authority checks, validation, and reconciliation
- materialise compact intermediate outputs only after the filtered SQL logic is stable
- let Python read only those compact outputs, not the raw detailed source families

The default execution ceiling for this slice is:
- bounded month selection only
- bounded field selection only
- one controlled intermediate output at a time

If a query starts behaving like broad exploratory profiling rather than bounded detailed-dataset stewardship, stop and narrow it before proceeding.

The required first-pass summary profiling layer is:
- raw row counts for each candidate source used in the slice
- period coverage at the monthly stewardship window level
- key coverage for the proposed detailed grain
- null rates for required trust fields
- duplicate checks at the proposed grain
- grain and field-meaning confirmation before any wider transformation logic is written

## 3. First-Pass Objective

The first-pass objective is:

`build one maintained detailed reporting dataset for a bounded monthly programme lane, with explicit validation and reconciliation checks and one reporting-safe downstream use`

The proof object is:
- `patient_level_dataset_stewardship_v1`

The first-pass output family is:
- one source and grain map
- one field-authority note
- one profiling output
- one validation output
- one reconciliation output
- one maintained detailed dataset output
- one reporting-protection note
- one maintenance checklist

## 4. Early Scope Gate

Before building any maintained dataset or downstream summary, run a bounded scope gate.

The first profiling pass must answer:
- which governed detailed source path is stable enough to support one monthly maintained dataset?
- what monthly stewardship window can be defined honestly from the available timestamps or period labels?
- what exact grain is safe for the maintained dataset?
- what key or composite key best protects that grain?
- which fields are required to support both trust checks and one downstream reporting-safe use?
- what do the row counts, period coverage, key coverage, null rates, and duplicate checks say about the safe scope of the slice before any heavier build begins?

Required checks:
- period coverage across the candidate detailed source path
- field availability for the required reporting and trust fields
- grain stability at the candidate record level
- duplicate exposure at the chosen grain
- completeness of fields needed for downstream reporting-safe use
- whether one reconciliation path can be defined cleanly between source and maintained dataset or between maintained dataset and reporting-safe summary

Those checks should be implemented as:
- aggregate-only SQL probes
- filtered monthly scans
- no broad row materialisation into memory

Decision rule:
- if one detailed source family is stable enough, proceed with the bounded stewardship slice
- if not, narrow the lane, window, or field scope rather than broadening the query footprint

## 5. Candidate Detailed Dataset Base

The first-pass dataset base should stay bounded and explicit.

Each component should have one stated purpose:
- source map
  - identify contributing surfaces
  - confirm the join path
  - confirm the detailed grain
- field-authority layer
  - choose authoritative fields
  - record exclusions and caveats
- profiling layer
  - establish row counts, coverage, nulls, and duplicates
- validation and reconciliation layer
  - test completeness, consistency, and alignment
- maintained dataset layer
  - one reporting-safe detailed output
- downstream reporting-protection layer
  - one compact summary or note showing what the maintained dataset protects

If the reused outputs do not support one of those components cleanly, adapt by creating a small local stewardship layer rather than stretching earlier slice outputs past their truth boundary.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. source-path, grain, and field-suitability checks
2. profiling layer
3. validation and reconciliation layer
4. maintained dataset materialisation
5. downstream reporting-safe summary or protection note
6. maintenance checklist and caveat packaging

The transformations should not be hidden inside one-off notebook reshaping or manual copy-paste reporting logic.

## 7. Bounded SQL Build Order

### Step 1. Create a source-path and field-suitability layer

Build small aggregate or profile queries only for:
- available monthly or period labels
- candidate grain stability
- key availability
- required field availability
- downstream-reporting field availability
- alignment between the detailed source path and any reporting-safe summary path

Goal:
- define the bounded stewardship slice honestly
- prove that one maintained dataset can be built without broad raw reconstruction

### Step 2. Materialise a profiling and validation layer

Create bounded SQL outputs, for example:
- `patient_level_dataset_profile_v1`
- `patient_level_dataset_validation_v1`

These outputs should include:
- row counts by month or relevant period partition
- required-field null counts or rates
- duplicate counts at the chosen grain
- field-rule checks
- one concise validity status per required check

### Step 3. Materialise the reconciliation layer

Create one bounded SQL output, for example:
- `patient_level_dataset_reconciliation_v1`

This output should:
- compare expected and actual record relationships
- surface unmatched or duplicate relationships where appropriate
- confirm whether the maintained dataset can be trusted for downstream reporting-safe use

### Step 4. Materialise the maintained detailed dataset

Create one bounded SQL output, for example:
- `vw_patient_level_reporting_dataset_v1`

This output should:
- use the agreed detailed grain
- apply the authoritative field choices
- respect the monthly stewardship window
- exclude or control records that fail the bounded trust rules

## 8. Dataset Trust Strategy

The maintained dataset must remain small in conceptual scope but strong in trust posture.

The first-pass trust strategy should answer:
- what is one record?
- how do we know the key is stable?
- which fields are authoritative?
- which fields are usable for downstream reporting?
- what conditions would make the dataset unsafe for reporting use?

Decision rule:
- every retained field must earn its place in either:
  - the trust checks
  - the maintained dataset
  - the downstream reporting-safe use
- if a field does not support one of those purposes, drop it

## 9. Reporting-Protection Strategy

Once the maintained dataset is stable, package the slice into one compact reporting-protection proof.

The downstream proof should answer:
- which reporting-safe output does this maintained dataset protect?
- what trust issue would exist if the dataset were uncontrolled?
- why is the maintained version safe enough for bounded reporting use?

Required components:
- one compact maintained-dataset summary
- one reporting-protection note
- one short comparison or control note only if genuinely needed

Create:
- `patient_level_reporting_safe_summary_v1`
- `patient_level_reporting_protection_note_v1.md`

## 10. Documentation And Control Strategy

The slice is not complete unless another analyst could maintain the dataset responsibly.

The documentation and control pack should answer:
- what the grain is
- what the key is
- which fields are authoritative
- what to profile first
- what validation checks must pass
- what reconciliation checks must pass
- what downstream use is safe
- what should not be claimed from this dataset

Create:
- `patient_level_dataset_source_map_v1.md`
- `patient_level_dataset_field_authority_v1.md`
- `patient_level_dataset_maintenance_checklist_v1.md`
- `patient_level_dataset_caveats_v1.md`
- `README_patient_level_dataset_regeneration.md`

## 11. Reproducibility Strategy

This slice is not complete unless the maintained dataset and its trust checks can be regenerated consistently.

The first-pass reproducibility pack should include:
- versioned SQL profiling logic
- versioned SQL validation logic
- versioned SQL reconciliation logic
- versioned SQL maintained-dataset build logic
- one compact Python script only if needed for compact table export or figure render
- one maintenance checklist
- one caveat or changelog note

The Python layer must remain:
- compact-output only
- not a substitute for broad detailed-data processing

That should be strong enough that another analyst could:
- understand the dataset grain and source path
- rerun the profiling layer
- rerun the validation and reconciliation checks
- regenerate the maintained dataset
- understand what downstream reporting use is and is not safe

## 12. Planned Deliverables

SQL and shaped data:
- one source-path and field-suitability query pack
- one profiling query
- one validation query
- one reconciliation query
- one maintained-dataset build query
- one compact maintained dataset output
- one compact reporting-safe summary output

Documentation:
- one source map
- one field-authority note
- one issue or trust-risk note
- one reporting-protection note
- one maintenance checklist
- one caveats note
- one regeneration README

Expected output bundle for the first pass:
- one bounded maintained detailed dataset
- one compact trust and control pack
- one compact downstream reporting-protection proof

## 13. What To Measure For The Claim

For this requirement, the strongest measures are controlled trust, validation coverage, reconciliation strength, and reporting protection rather than analytical novelty.

Primary measure categories:
- number of validation checks applied to the detailed dataset
- number of reconciliation checks applied to the detailed dataset
- required-field coverage after validation
- duplicate or mismatch exposure at the chosen grain
- one maintained dataset released for reporting-safe use

Secondary measure categories:
- regeneration time for the maintained dataset and its control checks
- one reporting-safe downstream summary produced
- one maintenance checklist completed

## 14. Execution Order

1. Finalise the folder structure for this InHealth responsibility lane.
2. Run the source-path, grain, and field-suitability gate.
3. Decide the bounded monthly stewardship window and detailed grain.
4. Materialise the profiling layer.
5. Materialise the validation and reconciliation layers.
6. Materialise the maintained detailed dataset.
7. Shape the compact reporting-safe summary and protection note.
8. Write the source map, field-authority note, maintenance checklist, caveats note, and regeneration note.
9. Produce complementary figures only after the trust outputs are stable.
10. Write the execution report and final claim surfaces only after the evidence is real.

## 15. Stop Conditions

Stop and reassess if any of the following happens:
- the candidate detailed source path does not support one stable grain honestly
- the key or composite key is too unstable for a maintained-dataset claim
- required trust fields have poor enough availability that the bounded slice becomes weak or misleading
- the slice starts drifting into broad service-reporting delivery rather than dataset stewardship
- the query posture starts requiring broad raw-data loads or memory-heavy dataframe work that should have been handled in bounded SQL instead
- the downstream proof starts depending on a larger reporting-estate claim than the slice actually supports

If one of those happens, the adaptation path is:
- keep the same responsibility lane
- name the actual blocker clearly
- narrow the grain, field scope, or window if needed
- preserve the center of gravity around maintained, validated, and reconciled detailed reporting data

## 16. What This Plan Is And Is Not

This is:
- a concrete execution plan for the second InHealth responsibility slice
- dataset-first
- trust-first
- bounded
- aligned to patient-level dataset maintenance, validation, and reconciliation

This is not:
- the execution report
- a broad healthcare data-governance programme
- another reporting-pack slice
- permission to force dashboard-like outputs where cleaner trust figures or tables would do

The first operational move after this plan should be:
- run the bounded source-path, grain, and field-suitability gate and decide whether the planned maintained dataset can be supported honestly from the governed detailed surfaces already available
