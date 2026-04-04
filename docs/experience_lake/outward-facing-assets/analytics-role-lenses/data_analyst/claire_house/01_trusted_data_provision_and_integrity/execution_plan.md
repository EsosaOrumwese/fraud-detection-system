# Execution Plan - Trusted Data Provision And Integrity Slice

As of `2026-04-04`

Purpose:
- turn the chosen Claire House `3.A` slice into a concrete execution order tied to bounded governed analytical surfaces already available in the repo
- keep the work provision-first, integrity-first, and tightly scoped to one trusted data-provision lane rather than broad governance rhetoric, broad systems integration, or a fake organisational data-estate build
- prove support for the production, management, protection, and integrity of one bounded analytical provision path without drifting into enterprise MDM or full charity information-management ownership
- keep execution memory-safe by profiling and shaping only the bounded periods, fields, and control layers required for the slice rather than treating the raw run like unlimited in-memory working space

Execution substrate:
- governed local artefacts already available in `artefacts/analytics_slices/`
- the trusted maintained-dataset and protected-output foundation already established in InHealth `3.C`
- bounded SQL-accessible detailed surfaces for compact additional profiling or integrity checks only where reuse is not sufficient
- new slice outputs to be written under `artefacts/analytics_slices/data_analyst/claire_house/01_trusted_data_provision_and_integrity/`

Primary rule:
- confirm the exact trusted foundation inherited from InHealth `3.C` first
- widen the story into a controlled data-provision lane only after source contribution, field authority, and downstream protection are explicit
- prefer compact inherited outputs and compact new SQL summaries over broad raw rescans
- package the provision and protection notes only after the controlled lane and its checks are real
- never load broad raw detailed surfaces into pandas or any other in-memory dataframe layer before the SQL gate has already reduced them to compact provision-control outputs

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- the repo already contains a trustworthy bounded foundation from InHealth `3.C` that can be widened honestly into Claire House provision language
- one bounded monthly analytical lane can stand in as an honest analogue for organisational data provision
- one controlled source-contribution path can be shown without reopening a broad raw rebuild
- one protected downstream output can be demonstrated as depending on the controlled provision lane

Candidate first-pass reusable foundations:
- InHealth `02_patient_level_dataset_stewardship` maintained dataset, validation checks, reconciliation checks, and reporting-protection logic
- InHealth `01_reporting_support_for_operational_and_regional_teams` downstream monthly reporting-safe output where the protected-use dependency needs to be shown
- Midlands and HUC trust-control patterns only conceptually where naming or structure helps, not as direct execution surfaces

Working assumption about the bounded provision question:
- the slice should show that trusted analytical provision is an actively controlled lane, not a loose set of raw extracts
- the slice should demonstrate controlled production, management, protection, and integrity of one analytical pathway
- the slice should remain bounded enough that the claim sounds organisationally relevant without pretending to cover the whole Claire House information estate

Important warning:
- these assumptions must be tested rather than carried forward casually
- if the inherited InHealth foundation is too narrow to support the widened provision claim honestly, adapt by adding a compact source-path or protection layer rather than broadening the raw query footprint

## 2. Provision-First And Integrity-First Posture

This slice must not begin as a reporting-pack or figure-first exercise.

The correct posture is:
- confirm the inherited maintained-dataset foundation first
- define the widened provision lane first
- map source contribution and field authority first
- run provision integrity checks first
- materialise one protected downstream provision output second
- package the provision-risk, protection, and caveat notes only after the controlled lane is stable
- use Python only after the compact provision-control outputs already exist in stable form

This matters because the Claire House responsibility here is about trusted data provision and integrity, not about decorative downstream reporting.

## 2A. Memory And Query Discipline

This slice must be executed with explicit memory discipline.

The raw run contains very large detailed surfaces, so the correct posture is:
- do not pull broad raw parquet surfaces into pandas
- do not rerun wide historical profiling if the provision question can be answered from inherited controlled outputs plus compact additional SQL checks
- do not assume a bounded monthly lane means all underlying raw rows can be inspected casually in memory

The correct query discipline is:
- start with summary-stats and provision-path profiling before any new materialisation
- use `DuckDB` or SQL-style scans with predicate pushdown
- filter the provision window at scan time
- project only the fields needed for source mapping, field authority, integrity checks, and one protected downstream output
- materialise compact intermediate outputs only after the filtered SQL logic is stable
- let Python read only those compact outputs, not the raw detailed source families

The default execution ceiling for this slice is:
- inherited trusted outputs first
- bounded monthly probes only where required
- bounded field selection only
- one controlled intermediate output at a time

If a query starts behaving like broad exploratory profiling rather than bounded provision-lane control, stop and narrow it before proceeding.

The required first-pass summary profiling layer is:
- row counts for the inherited maintained dataset and any additional candidate source used in the widened lane
- period coverage for the provision window
- key coverage at the maintained grain
- null rates for required authority and downstream fields
- duplicate checks at the maintained grain
- grain and field-meaning confirmation before any new transformation logic is written

## 3. First-Pass Objective

The first-pass objective is:

`build one trusted analytical data-provision lane for a bounded monthly pathway, with explicit source mapping, field authority, integrity checks, and one protected downstream output`

The proof object is:
- `trusted_data_provision_and_integrity_v1`

The first-pass output family is:
- one provision scope and source map
- one field-authority and protection note
- one provision profile output
- one provision integrity-check output
- one protected downstream provision summary
- one provision-risk note
- one run checklist and caveat pack

## 4. Early Scope Gate

Before widening the inherited foundation into a Claire House-shaped provision lane, run a bounded scope gate.

The first profiling pass must answer:
- which parts of the InHealth `3.C` foundation can be reused directly without stretching their truth boundary?
- what extra source-contribution or provision-language layer is genuinely needed for Claire House `3.A`?
- what monthly provision window remains the cleanest truthful analogue?
- what exact maintained grain and authoritative key should define the provision lane?
- which fields are required to support both provision control and one protected downstream analytical use?
- what do the row counts, period coverage, key coverage, null rates, and duplicate checks say about the safe scope of the widened provision lane?

Required checks:
- coverage and stability of the inherited maintained dataset
- field availability for the required authority and downstream-protection fields
- grain stability at the maintained lane level
- duplicate exposure at the chosen grain
- completeness of fields needed for protected downstream use
- whether one clear dependency path can be stated between the controlled provision lane and the protected downstream output

Those checks should be implemented as:
- aggregate-only SQL probes
- filtered monthly scans
- inherited compact outputs where available
- no broad row materialisation into memory

Decision rule:
- if the inherited trust lane is strong enough, proceed with the widened provision slice
- if not, add one compact new integrity or source-path layer rather than broadening the query footprint

## 5. Candidate Provision Lane Base

The first-pass provision base should stay bounded and explicit.

Each component should have one stated purpose:
- provision scope layer
  - define the analytical lane being controlled
  - define the reporting window and maintained grain
- source map layer
  - identify contributing surfaces
  - confirm the handoff path into the maintained lane
- field-authority layer
  - choose authoritative fields
  - record exclusions and caveats
- profiling and integrity layer
  - establish row counts, coverage, nulls, duplicates, and alignment
- protected output layer
  - one protected downstream provision summary
- risk and caveat layer
  - one explicit note explaining where trust could be lost and how the lane controls it

If inherited outputs do not support one of those components cleanly, adapt by creating one compact local provision-control layer rather than stretching earlier slice outputs past their truth boundary.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. inherited-foundation confirmation and source-path checks
2. provision profiling layer
3. provision integrity and protection checks
4. protected downstream provision summary
5. provision-risk, checklist, and caveat packaging

The transformations should not be hidden inside one-off notebook reshaping or manual copy-paste reporting logic.

## 7. Bounded SQL Build Order

### Step 1. Confirm the inherited maintained lane and add source-path checks

Build small aggregate or profile queries only for:
- available monthly or period labels
- maintained grain stability
- key availability
- required authority-field availability
- downstream-protection field availability
- alignment between the maintained lane and the protected downstream summary path

Goal:
- define the widened Claire House provision lane honestly
- prove that one controlled provision path can be claimed without broad raw reconstruction

### Step 2. Materialise a provision profile and integrity layer

Create bounded SQL outputs, for example:
- `trusted_data_provision_profile_v1`
- `trusted_data_provision_integrity_checks_v1`

These outputs should include:
- row counts by period partition
- required-field null counts or rates
- duplicate counts at the maintained grain
- field-authority checks
- one concise status per required integrity check

### Step 3. Materialise the protected downstream dependency layer

Create one bounded SQL output, for example:
- `trusted_data_provision_summary_v1`

This output should:
- be derived from the controlled provision lane
- respect the agreed grain and authority rules
- be small enough to act as a protected downstream use proof rather than another reporting-estate build

### Step 4. Package the control surface

Package the compact evidence that makes the widened lane read as organisational-style trusted data provision:
- provision scope note
- source map
- field-authority note
- protection note
- provision-risk note
- caveats and regeneration notes

## 8. Provision Trust Strategy

The provision lane must remain small in conceptual scope but strong in trust posture.

The first-pass trust strategy should answer:
- what exactly is the controlled provision lane?
- how do we know the maintained grain and key are stable?
- which fields are authoritative?
- which fields are safe for downstream analytical use?
- what conditions would make the lane unsafe to treat as trusted provision?

Decision rule:
- every retained field must earn its place in either:
  - source mapping
  - authority and integrity checks
  - the protected downstream use
- if a field does not support one of those purposes, drop it

## 9. Protected-Output Strategy

Once the provision lane is stable, package the slice into one compact protection proof.

The downstream proof should answer:
- which downstream analytical use does this controlled lane protect?
- what trust issue would exist if the lane were just loose raw extracts?
- why is the controlled provision lane safe enough for bounded downstream use?

Required components:
- one compact protected provision summary
- one protection note
- one short dependency or control note only if genuinely needed

Create:
- `trusted_data_provision_summary_v1`
- `data_provision_protection_note_v1.md`

## 10. Documentation And Control Strategy

The slice is not complete unless another analyst could understand and rerun the provision lane responsibly.

The documentation and control pack should answer:
- what the controlled provision lane is
- which sources contribute to it
- what the maintained grain and key are
- which fields are authoritative
- what to profile first
- what integrity checks must pass
- what downstream use is safe
- what should not be claimed from this lane

Create:
- `data_provision_scope_note_v1.md`
- `data_provision_source_map_v1.md`
- `data_provision_field_authority_v1.md`
- `data_provision_integrity_note_v1.md`
- `data_provision_caveats_v1.md`
- `README_trusted_data_provision_regeneration.md`

## 11. Reproducibility Strategy

This slice is not complete unless the controlled provision lane and its checks can be regenerated consistently.

The first-pass reproducibility pack should include:
- versioned SQL profiling logic
- versioned SQL integrity-check logic
- versioned SQL protected-output logic
- one compact Python script only if needed for compact table export or figure render
- one run checklist
- one caveat or changelog note

The Python layer must remain:
- compact-output only
- not a substitute for broad detailed-data processing

That should be strong enough that another analyst could:
- understand the provision lane and source path
- rerun the profiling layer
- rerun the integrity checks
- regenerate the protected downstream output
- understand what downstream analytical use is and is not safe

## 12. Planned Deliverables

SQL and shaped data:
- one provision scope and source-path query pack
- one provision profile query
- one integrity-check query
- one protected-output build query
- one compact provision profile output
- one compact integrity-check output
- one protected downstream provision summary output

Documentation:
- one provision scope note
- one source map
- one field-authority note
- one provision-risk note
- one protection note
- one run checklist
- one caveats note
- one regeneration README

Expected output bundle for the first pass:
- one bounded trusted provision lane
- one compact trust and control pack
- one compact protected downstream analytical-use proof

## 13. What To Measure For The Claim

For this requirement, the strongest measures are controlled provision scope, field authority, integrity strength, and downstream protection rather than analytical novelty.

Primary measure categories:
- number of source surfaces mapped into the provision lane
- number of trusted-field or authority rules held consistently
- number of integrity checks applied and passed
- number of protected downstream outputs released from the controlled lane

Secondary measure categories:
- regeneration time for the compact provision pack
- row or key coverage at the maintained grain
- one completed caveat and checklist pack

## 14. Execution Order

1. Finalise the folder structure for this Claire House responsibility lane.
2. Run the inherited-foundation and provision-scope gate.
3. Decide the bounded monthly provision window, maintained grain, and authoritative key.
4. Materialise the provision profile layer.
5. Materialise the integrity-check layer.
6. Materialise the protected downstream provision summary.
7. Write the scope note, source map, field-authority note, protection note, risk note, caveats note, and regeneration note.
8. Produce complementary figures only after the provision-control outputs are stable.
9. Write the execution report and final claim surfaces only after the evidence is real.

## 15. Stop Conditions

Stop and reassess if any of the following happens:
- the inherited InHealth `3.C` foundation is too narrow to support a widened provision-lane claim honestly
- the maintained grain or key is too unstable for a controlled provision claim
- required authority or downstream fields have poor enough availability that the widened slice becomes weak or misleading
- the slice starts drifting into broad organisational governance or systems-integration ownership rather than trusted data provision support
- the query posture starts requiring broad raw-data loads or memory-heavy dataframe work that should have been handled in bounded SQL instead
- the downstream proof starts depending on a larger reporting-estate or organisational-estate claim than the slice actually supports

If one of those happens, the adaptation path is:
- keep the same responsibility lane
- name the actual blocker clearly
- narrow the window, field scope, or downstream-use proof if needed
- preserve the center of gravity around controlled, protected, integrity-aware data provision

## 16. What This Plan Is And Is Not

This is:
- a concrete execution plan for the first Claire House responsibility slice
- provision-first
- integrity-first
- bounded
- aligned to trusted data provision and protection of downstream analytical use

This is not:
- the execution report
- a broad organisational data-governance programme
- a board-reporting slice
- permission to force dashboard-like outputs where cleaner control figures or tables would do

The first operational move after this plan should be:
- run the inherited-foundation and provision-scope gate and decide whether the widened Claire House provision lane can be supported honestly from the controlled InHealth `3.C` foundation plus bounded compact new checks
