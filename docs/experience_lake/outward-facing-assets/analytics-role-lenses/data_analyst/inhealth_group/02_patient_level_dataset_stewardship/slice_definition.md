# Patient-Level Dataset Stewardship Execution Slice - InHealth Group Data Analyst Requirement

As of `2026-04-04`

Purpose:
- capture the chosen bounded slice for the InHealth requirement around patient-level dataset maintenance, validation, and reconciliation
- keep the note aligned to the actual InHealth responsibility rather than drifting into generic data quality language, generic reporting support, or a broad healthcare-data stewardship programme
- preserve the distinction between this slice and InHealth `3.A` by making this one about the trusted detailed dataset underneath reporting, not about the reporting cycle itself

Boundary:
- this note is not an accomplishment record
- this note is not a claim that a broad patient-level data-management estate has already been implemented
- this note captures the chosen slice, why it fits the requirement, which lenses own it, and what the proof burden should be
- execution should begin from bounded profiling, governed analytical surfaces, and compact validation outputs rather than broad raw-data extracts into memory

Placement rule:
- this file lives under the role-shaped lens tree because it is execution-depth material, not a top-level lens definition
- the role folder should hold multiple employer lanes over time
- the employer folder should hold one folder per targeted responsibility slice so repeated work stays grouped and readable

Primary source basis:
- [03_data-quality-governance-trusted-information-stewardship.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\03_data-quality-governance-trusted-information-stewardship.md)
- [02_bi-insight-reporting-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\02_bi-insight-reporting-analytics.md)
- [09_analytical-delivery-operating-discipline.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\09_analytical-delivery-operating-discipline.md)
- [01_operational-performance-analytics.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\analytics-role-lenses\01_operational-performance-analytics.md)
- [data-analytics-engineering-science.ideal-candidate-profiles.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.ideal-candidate-profiles.md)
- [data-analytics-engineering-science.job-ads.evidence.md](c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system\docs\experience_lake\outward-facing-assets\job-descriptions-specifications\data-analytics-engineering-science.job-ads.evidence.md)

---

## 1. Requirement Being Targeted

The requirement being targeted here is the InHealth `Data Analyst` expectation around:
- maintaining patient-level datasets
- validating patient-level datasets
- reconciling patient-level datasets
- ensuring reporting accuracy through dataset maintenance and reconciliation work

This maps directly to the InHealth candidate-profile requirement that the analyst should be able to describe:
- treating dataset stewardship as a core part of the role
- maintaining trusted datasets rather than waiting for others to prepare them
- validating records and checking completeness or consistency
- reconciling discrepancies across sources or reporting views
- improving confidence in the data used for reporting

This note exists because that requirement is easy to flatten into the vague statement `good with data quality`. The employer is asking for something narrower and more valuable:
- careful stewardship of sensitive detailed records
- validation and reconciliation as part of day-to-day analytical work
- protection of reporting accuracy through that stewardship

## 2. The Analogue On The Current Platform

The current platform does not contain literal patient records, so the slice has to use an honest analogue.

The closest truthful analogue is:
- case-level and event-linked sensitive operational records
- detailed enough that grain, join logic, field authority, and record consistency materially affect reporting accuracy
- structured enough to support validation and reconciliation without pretending to be a healthcare dataset

So for this slice:
- `patient-level dataset` in the employer wording maps to `case-level sensitive operational reporting dataset` on the current platform
- the proof burden is the same:
  - maintain a trusted detailed reporting dataset
  - validate it
  - reconcile it
  - show that downstream reporting depends on that stewardship

The claim must therefore remain:
- healthcare-role shaped
- platform-truth bounded
- careful not to imply direct patient-record handling where none exists

## 3. Lens Stack For This Requirement

The cleanest lens stack for this InHealth `3.C` requirement is:

**Primary**
- `03 - Data Quality, Governance, and Trusted Information Stewardship`

**Strong support**
- `02 - BI, Insight, and Reporting Analytics`

**Support**
- `09 - Analytical Delivery Operating Discipline`

**Secondary support**
- `01 - Operational Performance Analytics`

Why this stack fits:

`03` is the main owner because the requirement is explicitly about:
- maintaining detailed datasets
- validating them
- reconciling them
- protecting reporting trust

That is directly `03` territory:
- fit-for-use checking
- field-level trust rules
- validation
- reconciliation
- issue detection
- trusted information stewardship

`02` matters because the employer does not want stewardship for its own sake. The maintained dataset has to support accurate reporting. That means the slice has to show that reporting outputs become more dependable because the dataset underneath them is maintained and controlled.

`09` matters because this responsibility is not a one-time cleanup. It implies repeatable controls:
- stable dataset definitions
- repeatable validation checks
- reconciliation notes
- caveats
- run discipline
- maintenance-ready documentation

`01` is support only where useful. It becomes relevant if the slice shows that a defect or inconsistency in the detailed dataset would distort an operational KPI or follow-up interpretation. The core burden is still stewardship first, not performance commentary first.

So the practical reading is:
- `03` maintains, validates, reconciles, and protects trust
- `02` shows why that stewardship matters for reporting accuracy
- `09` makes the stewardship repeatable and controlled
- `01` shows downstream operational consequence only where it strengthens the proof

Ownership order:
- `03 -> 02 -> 09 -> 01`

Best execution order:
- `03 -> 02 -> 09 -> 01`

That execution order matters because trust and field authority have to be established before any reporting-accuracy or operational-impact layer can be claimed credibly.

## 4. Chosen Bounded Slice

The cleanest bounded slice for this InHealth requirement is:

`one maintained case-level reporting dataset across one monthly window for one programme lane, with explicit validation, reconciliation, and reporting-protection controls`

In the fraud-platform analogue, that means:
- select one bounded programme-style monthly window
- define one detailed case-level reporting dataset from governed surfaces
- document its grain and authoritative fields explicitly
- run validation and reconciliation checks across the detailed records
- record one discrepancy or trust-risk note where relevant
- show the maintained dataset feeding one reporting-safe summary or downstream view

The slice should answer one narrow question:
- `can this bounded detailed reporting dataset be maintained and trusted well enough that a monthly reporting output built from it remains accurate and defensible?`

That means the slice should produce:
- one source-to-dataset map
- one field-authority and dataset-definition note
- one validation and reconciliation layer
- one maintained detailed dataset extract
- one reporting-accuracy protection note
- one run and maintenance checklist

This slice is the best analogue for the InHealth requirement because it proves:
- stewardship of a detailed sensitive dataset
- validation and reconciliation as part of analytical work
- reporting trust protected through dataset maintenance
- repeatable control rather than one-off inspection

## 5. Why This Slice Was Chosen

This slice was chosen because it gives direct room for:
- proving careful stewardship of a detailed dataset rather than only summary-level KPI control
- showing validation and reconciliation as active analyst work
- connecting data maintenance to reporting accuracy
- keeping the proof bounded enough to execute without pretending to operate a full healthcare data estate

It also avoids the wrong kinds of drift.

The intention is not to:
- repeat InHealth `3.A` as another reporting-delivery slice
- build a broad data quality programme
- claim full patient-record operational ownership across the platform
- collapse the work into a single discrepancy note without a maintained dataset underneath it
- turn this into a generic SQL extraction exercise

The intention is to prove one sharper statement:
- I can maintain, validate, and reconcile a detailed reporting dataset carefully enough to keep downstream reporting accurate and trustworthy

## 6. Relationship To Earlier Slices

This slice can and should build on already established proof where that is the honest choice.

Most importantly, it can legitimately build on:
- Midlands data-quality ownership and governed analytical-dataset shaping
- HUC discrepancy handling and reporting-trust control
- InHealth `01_reporting_support_for_operational_and_regional_teams` as the downstream reporting lane this stewardship protects

But this slice is not a copy of any of those.

The difference is:
- Midlands proved broader governed analytical data shaping and data-quality ownership in a data-science posture
- HUC `03` proved anomaly detection and discrepancy resolution in a reporting-control posture
- InHealth `3.A` proved monthly and ad hoc reporting support
- InHealth `3.C` is narrower and more foundational:
  - maintain one detailed reporting dataset
  - validate it
  - reconcile it
  - keep reporting accurate because that dataset is trustworthy

This also makes the slice a useful precursor to broader trusted-data-provision responsibilities in later job ads without forcing those broader claims yet.

## 7. Execution Posture

The default execution stack for this slice is:
- summary-stats and metadata profiling first
- SQL for bounded dataset shaping, validation checks, reconciliation checks, and compact maintained outputs
- Python only after the dataset has been reduced to compact controlled outputs
- markdown notes for field definitions, authority rules, issue notes, maintenance instructions, and reporting-protection notes

The execution substrate should be:
- governed detailed surfaces already available on the platform
- bounded monthly filters
- explicit field projection
- compact maintained outputs rather than broad raw extracts

The default local working assumption is:
- large raw surfaces stay in the query engine
- profiling comes before dataset materialisation
- the detailed maintained dataset is a bounded analogue, not a full-platform export

The reporting posture should remain:
- figure-supportive rather than dashboard-forcing
- trust-and-structure focused
- visually useful only where it helps explain validation, reconciliation, or protected reporting impact

## 8. Lens-by-Lens Execution Checklist

### 8.1 Lens 03 - Maintain, validate, and reconcile the detailed dataset

This is the core owner.

Tasks:
1. Define the dataset grain explicitly:
- one record grain
- one monthly reporting window
- one bounded programme lane
2. Map the source path:
- source surfaces used
- join path
- authoritative dataset key
- authoritative field choices
3. Profile the dataset before shaping:
- row counts
- period coverage
- key coverage
- null rates for required fields
- duplicate checks at the chosen grain
4. Build validation checks:
- completeness
- consistency
- grain integrity
- field-rule adherence
5. Build reconciliation checks:
- source-to-dataset row alignment where appropriate
- reporting-view alignment where appropriate
- unmatched or duplicated relationships
6. Write one issue or trust-risk note:
- what was checked
- what was found
- what was corrected or controlled
- what remains caveated

### 8.2 Lens 02 - Show that reporting accuracy depends on the maintained dataset

This is the main support lens.

Tasks:
1. Build one reporting-safe summary from the maintained dataset.
2. Show the summary depends on the controlled dataset definition.
3. Record one reporting-protection note:
- which reporting output the dataset supports
- what would go wrong if the detailed dataset were uncontrolled
- what trust boundary the maintained dataset protects
4. Keep the downstream reporting proof compact:
- one summary
- one comparison or control note only if needed

### 8.3 Lens 09 - Make dataset stewardship repeatable

This is what turns the slice from one careful inspection into a maintainable analytical responsibility.

Tasks:
1. Stabilise the dataset definition:
- grain
- key
- authoritative fields
- allowed exclusions
- reporting window rule
2. Version the logic:
- profiling SQL
- validation SQL
- reconciliation SQL
- maintained dataset build logic
3. Create one maintenance checklist:
- what to profile first
- what checks must pass
- what thresholds trigger review
- what output is safe to release downstream
4. Document caveats:
- what the dataset is suitable for
- what it should not be used for
- what source changes would break comparability
5. Add one changelog or maintenance note:
- what changed in the dataset logic
- whether prior outputs remain comparable

### 8.4 Lens 01 - Show one downstream operational consequence if useful

This lens is optional support only.

Tasks:
1. Identify one KPI or monthly output fed by the maintained dataset.
2. Write one short note explaining why dataset trust matters operationally.
3. Avoid broad service interpretation. Keep it to one protected downstream reading only.

## 9. Suggested Artifact Pack

The minimum credible proof pack for this slice is:
- one source and grain map
- one field-authority and dataset-definition note
- one profiling and validation SQL pack
- one reconciliation SQL pack
- one maintained detailed dataset extract
- one reporting-accuracy protection note
- one maintenance checklist
- one caveat or changelog note

That is enough to prove:
- careful dataset stewardship
- validation and reconciliation capability
- reporting trust protection
- repeatable control over a detailed reporting dataset

## 10. Suggested Artifact Names

These names are placeholders, not fixed schema requirements.

Dataset and trust assets:
- `patient_level_dataset_source_map_v1.md`
- `patient_level_dataset_field_authority_v1.md`
- `patient_level_dataset_profile_v1.sql`
- `patient_level_dataset_validation_v1.sql`
- `patient_level_dataset_reconciliation_v1.sql`
- `patient_level_dataset_issue_note_v1.md`
- `patient_level_dataset_lineage_v1.md`

Maintained dataset and reporting-protection assets:
- `vw_patient_level_reporting_dataset_v1.sql`
- `patient_level_reporting_dataset_v1.parquet`
- `patient_level_reporting_protection_note_v1.md`
- `patient_level_reporting_safe_summary_v1.parquet`

Control assets:
- `patient_level_dataset_maintenance_checklist_v1.md`
- `patient_level_dataset_caveats_v1.md`
- `CHANGELOG_patient_level_dataset.md`
- `README_patient_level_dataset_regeneration.md`

## 11. Definition Of Done

This slice should be treated as complete only when all of the following are true:
- one bounded detailed reporting dataset has been defined
- its grain, key, and authoritative fields are documented
- profiling has established row counts, coverage, and basic field integrity
- validation checks exist and have been run
- reconciliation checks exist and have been run
- one maintained dataset output exists
- one downstream reporting-protection note exists
- one maintenance checklist exists

## 12. Truth Boundary

As of this note, the correct claim is:
- the slice has been selected
- the lens mapping is clear
- the execution path is defined
- the bounded stewardship proof object has been chosen

The correct claim is not:
- that a broad patient-level healthcare dataset has already been maintained on the platform
- that all dataset-quality issues are already resolved
- that the platform now proves full healthcare operational stewardship
- that all downstream reporting has already been protected by this slice

This note therefore exists to protect against overclaiming while preserving a fast path toward a defensible claim.

## 13. What To Measure For The Eventual `Y`

For this requirement, the strongest `Y` values are:
- number of validation checks applied to the detailed dataset
- number of reconciliation checks applied to the detailed dataset
- coverage of required fields after validation
- duplicate or mismatch rate reduced or controlled
- one maintained dataset released for reporting-safe use
- regeneration time for the maintained dataset and its control checks

A strong small `Y` set would be:
- `[N]` validation and reconciliation checks applied to one detailed reporting dataset
- required-field coverage held at `[X]%` after validation
- duplicate or mismatch exceptions reduced to `[Y]` or explicitly controlled
- one maintained dataset and one downstream reporting-safe summary regenerated in `[T]` minutes

## 14. XYZ Claim Surfaces This Slice Is Aiming Toward

This section is included here because the slice definition needs to preserve the exact claim shape the execution is aiming toward, not just the structural checklist.

### 14.1 Full flagship `X by Y by Z` version

> Maintained, validated, and reconciled a detailed reporting dataset to protect reporting accuracy, as measured by application of `[N]` validation and reconciliation checks, controlled field and key integrity across one bounded monthly dataset, and regeneration of the maintained dataset and reporting-safe summary in `[T]` minutes, by defining the dataset grain and authoritative fields, profiling and reconciling detailed records from governed platform surfaces, and embedding the maintenance checks needed to keep downstream reporting trustworthy.

### 14.2 Shorter recruiter-readable version

> Maintained and reconciled a trusted detailed reporting dataset, as measured by repeatable validation checks, controlled reconciliation logic, and a reporting-safe downstream output, by turning governed detailed records into a maintained dataset that could be used confidently for monthly reporting rather than relying on unchecked raw extracts.

### 14.3 Closest direct response to the InHealth requirement

> Maintained, validated, and reconciled a detailed reporting dataset to keep reporting accurate, as measured by repeatable dataset checks, controlled field authority, and a downstream reporting-safe output, by profiling detailed records carefully, resolving or controlling inconsistencies, and releasing a maintained dataset fit for reporting use.

## 15. Immediate Next-Step Order

The correct build order remains:
1. profile the bounded detailed dataset and define its grain, key, and field authority
2. build validation and reconciliation checks against that definition
3. materialise one maintained dataset output
4. show one protected downstream reporting-safe summary
5. add checklist, caveats, and regeneration notes

That order matters because it prevents the slice from collapsing into a downstream report claim without first proving that the detailed dataset underneath it is maintained and trustworthy.
