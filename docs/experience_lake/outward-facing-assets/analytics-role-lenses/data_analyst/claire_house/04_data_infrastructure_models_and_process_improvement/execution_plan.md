# Execution Plan - Data Infrastructure, Models, And Process Improvement Slice

As of `2026-04-04`

Purpose:
- turn the chosen Claire House `3.D` slice into a concrete execution order tied to the trusted provision and reporting outputs already available in the repo
- keep the work analytical-layer-first and efficiency-first, not platform-rhetoric-first
- prove one maintained analytical shaping layer, one bounded control weakness, and one bounded efficiency or automation improvement without drifting into broad data-engineering or application-development ownership
- keep execution memory-safe by reusing the Claire House `3.A` and `3.B` compact outputs before considering any broader raw query footprint

Execution substrate:
- governed local artefacts already available in `artefacts/analytics_slices/`
- the trusted provision lane already established in Claire House `3.A`
- the governed reporting outputs already established in Claire House `3.B`
- compact reshaping outputs and notes to be written under `artefacts/analytics_slices/data_analyst/claire_house/04_data_infrastructure_models_and_process_improvement/`

Primary rule:
- confirm the exact shaping path already sitting between Claire House `3.A` and `3.B` first
- materialise one maintained analytical layer explicitly from that path
- surface one control or capture weakness that matters for downstream reuse
- release one bounded efficiency or automation improvement from the same maintained layer
- never load broad raw detailed surfaces into pandas or any other in-memory dataframe layer before the SQL gate has already reduced them to compact maintained outputs
- if figures are used later, they must be analytical plots that clarify the maintained-layer and efficiency story, not explanatory diagrams or faux architecture drawings

---

## 1. Confirmed Working Assumptions

This plan is built around the following assumptions that must be tested immediately:
- the repo already contains enough trusted provision and reporting evidence from Claire House `3.A` and `3.B` to define one maintained analytical shaping layer honestly
- the maintained layer can be expressed as a compact reusable output rather than a broad raw reconstruction
- one meaningful control or capture weakness can be surfaced from the path between provision and reporting
- one bounded efficiency or automation improvement can be shown without inventing a wider engineering programme

Candidate first-pass reusable foundations:
- Claire House `01_trusted_data_provision_and_integrity` provision-trust and control-path outputs
- Claire House `02_reporting_dashboards_and_visualisation` summary output, ad hoc detail output, and release checks
- InHealth `02_patient_level_dataset_stewardship` only conceptually where maintained-layer control logic is relevant, not as a direct execution surface

Working assumption about the bounded processing question:
- the maintained analytical layer should be fixed from the path already implicit between the trusted provision lane and the reporting outputs
- the reuse and control story should be made explicit without broadening the reporting window
- the slice should prove maintainability and efficiency under the reporting layer, not a new reporting product

Important warning:
- these assumptions must be tested rather than carried forward casually
- if the Claire House `3.A` and `3.B` bases do not support one honest maintained-layer proof, adapt by narrowing the maintained-layer claim rather than broadening the raw query footprint

## 2. Maintained-Layer-First Posture

This slice must not begin as a generic optimisation exercise.

The correct posture is:
- confirm the inherited provision and reporting bases first
- define the maintained analytical layer first
- define the downstream uses that depend on that layer second
- define the control weakness third
- define the bounded efficiency improvement fourth
- add rerun, caveat, and release notes after the maintained layer is stable
- use Python only after the SQL layer has already reduced the slice to compact maintained outputs

This matters because the Claire House responsibility here is about infrastructure, models, and process improvement support, and the execution should read like careful analytical-layer stewardship rather than loose technical ambition.

## 2A. Memory And Query Discipline

This slice must be executed with explicit memory discipline.

The underlying run contains very large detailed surfaces, so the correct posture is:
- do not pull broad raw parquet surfaces into pandas
- do not rerun wide historical profiling if the infrastructure-and-efficiency question can be answered from Claire House `3.A` and `3.B` outputs plus one compact reshaping layer
- do not assume that a maintained-layer slice justifies reopening broad raw analytical scope

The correct query discipline is:
- start with summary-stats and structure profiling before any new materialisation
- use `DuckDB` or SQL-style scans with predicate pushdown
- filter the reporting window at scan time
- project only the fields needed for the maintained layer, the control weakness, the downstream reuse proof, and any later analytical plot
- materialise compact intermediate outputs only after the filtered SQL logic is stable
- let Python read only those compact outputs, not the raw detailed source families

The default execution ceiling for this slice is:
- inherited trusted outputs first
- one compact maintained layer second
- one compact control profile third
- one compact reuse summary fourth

If a query starts behaving like broad exploratory rebuild rather than bounded analytical-layer support, stop and narrow it before proceeding.

The required first-pass summary profiling layer is:
- row counts for the inherited trusted provision and reporting bases
- field coverage needed to express one maintained analytical layer
- confirmation of which downstream outputs the maintained layer can support
- confirmation that one clear control or capture weakness can be surfaced without reopening a large raw lane

## 3. First-Pass Objective

The first-pass objective is:

`build one maintained analytical shaping layer between the trusted provision lane and the reporting layer, surface one control weakness inside that path, and show one bounded efficiency improvement from fixing the layer explicitly`

The proof object is:
- `data_infrastructure_models_and_process_improvement_v1`

The first-pass output family is:
- one processing-layer scope note
- one maintained analytical layer output
- one control-profile output
- one reuse-summary output
- one release-check output
- one efficiency-improvement note
- one caveat and regeneration pack

## 4. Early Scope Gate

Before materialising any new maintained layer, run a bounded scope gate.

The first profiling pass must answer:
- which exact Claire House `3.A` output should act as the trusted input to the maintained layer?
- which exact Claire House `3.B` outputs depend on the maintained analytical shaping path?
- which fields are genuinely required to express the maintained layer and downstream reuse?
- what control or capture weakness is visible in the shaping path?
- what do the row counts, field coverage, and downstream dependencies say about the safe scope of the maintained-layer proof before any packaging begins?

Required checks:
- coverage and stability of the trusted Claire House `3.A` provision output
- coverage and stability of the Claire House `3.B` summary and ad hoc outputs
- continuity of key fields needed to express the maintained layer
- ability to state one clear control or capture weakness
- ability to state one bounded efficiency improvement from making the layer explicit

Those checks should be implemented as:
- aggregate-only SQL probes
- inherited compact outputs where available
- no broad row materialisation into memory

Decision rule:
- if the inherited base is strong enough, proceed with the bounded maintained-layer proof
- if not, add one compact reshaping layer rather than broadening the raw query footprint

## 5. Candidate Maintained Analytical Layer

The first-pass maintained layer should stay bounded and explicit.

Each component should have one stated purpose:
- trusted-input layer
  - define what enters the maintained analytical path from Claire House `3.A`
- maintained-shaping layer
  - define the reusable processing structure that sits under Claire House `3.B`
- control-monitoring layer
  - define where weak capture or processing logic would damage downstream reuse
- downstream-reuse layer
  - define which reporting outputs are supported from the maintained layer

If inherited outputs do not support one of those components cleanly, adapt by creating one compact maintained layer rather than stretching earlier slice outputs past their truth boundary.

## 6. Planned Transformation Chain

The transformation chain should remain explicit and staged:

1. inherited-base confirmation and structure-scope checks
2. maintained analytical-layer materialisation
3. control-profile materialisation
4. downstream-reuse summary materialisation
5. release, caveat, and regeneration packaging

The transformations should not be hidden inside one-off notebook rewriting or manual copy-paste logic.

## 7. Bounded SQL Build Order

### Step 1. Confirm the inherited provision and reporting path

Build small aggregate or profile queries only for:
- available reporting window fields
- keys that connect the provision and reporting outputs
- shaping fields needed to express the maintained layer
- control-profile fields needed to surface one weakness
- downstream-reuse fields needed to prove the maintained layer matters

Goal:
- define the maintained layer honestly
- prove that the analytical-layer question can be answered from the inherited Claire House `3.A` and `3.B` surfaces without broad raw reconstruction

### Step 2. Materialise the maintained analytical layer

Create one bounded output, for example:
- `maintained_processing_layer_v1`

This output should:
- retain the minimal fields needed for downstream reporting reuse
- express the shaping logic explicitly
- remain small enough to act as a maintained analytical layer rather than a new raw base

### Step 3. Materialise the control profile

Create one bounded output, for example:
- `processing_layer_control_profile_v1`

This output should:
- make one control or capture weakness explicit
- show where the maintained layer contains or reduces that weakness
- remain compact and focused on the chosen issue

### Step 4. Materialise the downstream-reuse summary

Create one bounded output, for example:
- `processing_layer_reuse_summary_v1`

This output should:
- show which downstream outputs the maintained layer supports
- make the efficiency benefit explicit
- remain a reuse proof, not another reporting product

### Step 5. Materialise the release-check layer

Create one bounded output, for example:
- `processing_layer_release_checks_v1`

This output should:
- confirm the maintained layer remains consistent with the trusted provision base
- confirm the maintained layer supports the intended downstream outputs
- confirm the control profile and reuse summary are safe to issue

## 8. Control And Efficiency Strategy

The maintained-layer proof must remain small in conceptual scope but strong in control posture.

The first-pass control strategy should answer:
- what exactly is the maintained analytical layer?
- what weakness exists if the layer is left implicit or loose?
- what downstream burden is reduced by making the layer explicit?
- what rerun and caveat controls must travel with the maintained layer?

Decision rule:
- every retained field must earn its place in either:
  - maintained-layer structure
  - control monitoring
  - downstream reuse
  - release posture
- if a field does not support one of those purposes, drop it

## 9. Documentation And Control Strategy

The slice is not complete unless another analyst could rerun the maintained layer responsibly.

The documentation and control pack should answer:
- what the maintained layer is for
- which downstream outputs depend on it
- what control weakness was surfaced
- what efficiency gain was achieved by fixing the layer explicitly
- what checks must pass before reuse
- what the layer does and does not support

Create:
- `processing_layer_scope_note_v1.md`
- `maintained_analytical_layer_note_v1.md`
- `data_capture_control_monitoring_note_v1.md`
- `efficiency_improvement_note_v1.md`
- `processing_layer_caveats_v1.md`
- `README_processing_layer_regeneration.md`
- `CHANGELOG_processing_layer.md`

## 10. Reproducibility Strategy

This slice is not complete unless the maintained layer and its controls can be regenerated consistently.

The first-pass reproducibility pack should include:
- versioned SQL maintained-layer logic
- versioned SQL control-profile logic
- versioned SQL reuse-summary logic
- versioned SQL release-check logic
- one compact Python script only if needed for note assembly or later figure render
- one caveat or changelog note

The Python layer must remain:
- compact-output only
- not a substitute for broad analytical processing

That should be strong enough that another analyst could:
- understand the maintained layer
- rerun it
- understand the surfaced control weakness
- regenerate the compact improvement-support pack

## 11. Planned Deliverables

SQL and shaped data:
- one structure-scope and field-coverage query pack
- one maintained-layer query
- one control-profile query
- one reuse-summary query
- one release-check query
- one compact maintained-layer output
- one compact control-profile output
- one compact reuse-summary output
- one compact release-check output

Documentation:
- one processing scope note
- one maintained-layer note
- one control-monitoring note
- one efficiency-improvement note
- one caveats note
- one regeneration README

Reporting outputs:
- no new reporting pack by default
- analytical plots only if they help clarify the maintained-layer and efficiency truth later

Expected output bundle for the first pass:
- one bounded maintained analytical-layer pack
- one compact control and release pack
- one compact efficiency-improvement proof

## 12. What To Measure For The Claim

For this requirement, the strongest measures are maintained-layer reuse, control posture, and bounded efficiency improvement rather than analytical novelty.

Primary measure categories:
- number of maintained analytical layers or outputs fixed for reuse
- number of downstream outputs supported from the same layer
- number of control checks passed on the maintained layer
- one explicit control-monitoring note completed

Secondary measure categories:
- reduction in repeated shaping burden
- regeneration time for the maintained-layer pack
- one completed caveat and rerun pack

## 13. Execution Order

1. Finalise the folder structure for this Claire House responsibility lane.
2. Run the inherited-base and structure-scope gate.
3. Decide the maintained analytical layer from the trusted provision and reporting path.
4. Materialise the maintained analytical layer.
5. Materialise the control-profile output.
6. Materialise the downstream-reuse summary.
7. Materialise the release-check layer.
8. Write the scope, maintained-layer, control, efficiency, caveats, changelog, and regeneration notes.
9. Produce analytical plots only after the maintained-layer proof is stable.
10. Write the execution report and final claim surfaces only after the evidence is real.

## 14. Stop Conditions

Stop and reassess if any of the following happens:
- the Claire House `3.A` and `3.B` bases are too thin to support one honest maintained-layer proof
- the chosen maintained layer starts behaving like a broad raw rebuild rather than a bounded reuse layer
- the control weakness cannot be stated clearly without inventing a larger problem than the evidence supports
- the slice starts drifting into full engineering, storage-platform, or application-development ownership
- the query posture starts requiring broad raw-data loads or memory-heavy dataframe work that should have been handled in bounded SQL instead
- the figures start becoming decorative rather than analytical support for the maintained-layer truth

If one of those happens, the adaptation path is:
- keep the same responsibility lane
- name the actual blocker clearly
- narrow the maintained-layer or efficiency claim if needed
- preserve the center of gravity around one bounded maintained analytical path plus one explicit control and efficiency improvement

## 15. What This Plan Is And Is Not

This is:
- a concrete execution plan for the fourth Claire House responsibility slice
- maintained-layer-first
- bounded
- aligned to analytical data-layer stewardship and efficiency improvement support

This is not:
- the execution report
- a broad data-engineering programme
- a storage-platform build plan
- a whole application-development integration plan
- permission to force engineering language where the bounded evidence does not support it

The first operational move after this plan should be:
- run the inherited-base and structure-scope gate and decide whether the Claire House `3.A` and `3.B` outputs can support one honest maintained analytical layer plus one bounded control and efficiency improvement without reopening a broad raw analytical rebuild
