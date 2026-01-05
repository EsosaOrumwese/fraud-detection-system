# Contract Audit 2026-01-04

Scope
- Purpose: Validate contract integrity and coherence across dataset dictionaries, artefact registries, and schema anchors in the root repo.
- Focus: Path/partition logic, ID consistency, duplicate or contradicting entries, cross-segment gate artefacts, and operability of path families.
- Sources: `contracts/dataset_dictionary`, `contracts/artefact_registry`, `contracts/schemas`, `docs/model_spec` contracts.

Method
- Enumerate contract assets per segment and layer (dictionary → registry → schema anchors).
- Check for duplicate IDs/paths, missing registry entries, and inconsistent path templates.
- Verify upstream/downstream gate artefacts (validation_bundle + _passed.flag) are present and aligned with segment specs.

Labels
- [Spec vs repo]: runtime `contracts/` diverge from `docs/model_spec` contracts.
- [Spec-internal]: inconsistency or gap inside the spec contracts themselves (repo currently matches spec).

Initial observations (to validate in detail)
- [Spec vs repo] 1A dataset dictionary lists both `validation_bundle` and `validation_bundle_1A` with the same path (`contracts/dataset_dictionary/l1/seg_1A/layer1.1A.yaml`). This is a duplicate ID/path pairing that can cause ambiguity.
- [Spec vs repo] `contracts/artefact_registry` currently contains registries for 5A/5B/6A/6B only; there are no registry files for 1A-3B.

Next review passes
- Layer-1: audit 1A–3B dictionaries vs state-flow specs for required gate artefacts and egress paths.
- Layer-2: audit 5A–5B dictionaries and registries for policy/config coverage and path determinism.
- Layer-3: audit 6A–6B dictionaries and registries for schema anchor alignment and gating artefacts.

---

Layer-1 contract review (1A–3B)

Segment 1A
- [Spec vs repo] Missing schema anchor file: multiple dictionary entries reference `schemas.1A.yaml#/...` (e.g., `contracts/dataset_dictionary/l1/seg_1A/layer1.1A.yaml`, `contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml`, `contracts/dataset_dictionary/l1/seg_3A/layer1.3A.yaml`), but `contracts/schemas/layer1/schemas.1A.yaml` does not exist. This breaks schema_ref resolution and downstream contract validation.
- [Spec vs repo] Schema_ref mismatch for validation bundle: `validation_bundle` and `validation_bundle_1A` point to `contracts/schemas/l1/seg_1A/s0_outputs.schema.json#/validation_bundle`, but that anchor does not exist in the schema file; `rg` shows no `validation_bundle` entry in `s0_outputs.schema.json`.
- [Spec vs repo] Duplicate bundle IDs: `validation_bundle` and `validation_bundle_1A` are both defined with the same path and schema_ref, creating ambiguous dataset IDs for the same artefact.
- [Spec vs repo] Schema authority rule conflict: 1A specs require dictionary/registry schema_ref to use JSON-Schema anchors under `schemas.*.yaml` (no Avro, no out-of-band schema files). The current 1A dictionary references `s0_outputs.schema.json`, which is a JSON schema file but not a `schemas.*.yaml` anchor, so it violates the stated authority rule.
- [Spec vs repo] Missing artefact registry: 1A specs reference `artefact_registry_1A.yaml` (e.g., S0/S3 governance and dependency-closure rules), but no such file exists under `contracts/` or `contracts/artefact_registry/`.

Segment 1B
- [Spec vs repo] Validation flag schema_ref mismatch: `validation_passed_flag_1A` in `contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml` points to `schemas.1B.yaml#/validation/passed_flag`, but `schemas.1B.yaml` contains no `passed_flag` anchor. The only `passed_flag` anchor appears in `contracts/schemas/layer1/schemas.layer1.yaml`.
- [Spec vs repo] Schema dependency hole: `validation_bundle_1A` and `outlet_catalogue` in `layer1.1B.yaml` reference `schemas.1A.yaml#/...`, but `contracts/schemas/layer1/schemas.1A.yaml` is missing, so these schema_refs cannot resolve.
- [Spec vs repo] Missing artefact registry: 1B specs expect `artefact_registry_1B.yaml` stanzas for validation bundles/flags and key inputs, but no Layer-1 registry files exist for 1A-3B.

Segment 2A
- [Spec vs repo] Upstream bundle schema_ref mismatch: `validation_bundle_1B` in `contracts/dataset_dictionary/l1/seg_2A/layer1.2A.yaml` points to `schemas.1B.yaml#/validation/validation_bundle_1B`, but `schemas.1B.yaml` has no `validation_bundle_1B` anchor.
- [Spec vs repo] Optional MCC mapping vs fixed anchor: 2A S2 spec treats merchant→MCC mapping as programme-specific and optional (only required if MCC overrides are active), yet the dictionary defines a fixed `merchant_mcc_map` dataset with a pinned path/schema and `produced_by: 2A.S0`. This is a contract posture mismatch that should be reconciled.
- [Spec vs repo] Missing artefact registry: 2A specs reference registry stanzas for gate inputs and policies, but there is no `artefact_registry_2A.yaml`.

Segment 2B
- [Spec vs repo] Upstream bundle schema_ref mismatch: `validation_bundle_1B` in `contracts/dataset_dictionary/l1/seg_2B/layer1.2B.yaml` points to `schemas.1B.yaml#/validation/validation_bundle_1B`, but `schemas.1B.yaml` has no `validation_bundle_1B` anchor.
- [Spec vs repo] Policy pack path inconsistency: policy paths mix `contracts/policy/2B/...` with `contracts/policies/l1/seg_2B/virtual_rules_policy_v1.json`; this is a path-family inconsistency within the same policy pack and may indicate a typo or duplicate location convention.
- [Spec vs repo] Missing artefact registry: 2B specs require registry entries for token-less policy packs and validation bundle/flag (`write_once`, `atomic_publish`), but there is no `artefact_registry_2B.yaml`.

Segment 3A
- [Spec vs repo] Schema_ref mismatch for 1A bundle: `validation_bundle_1A` in `contracts/dataset_dictionary/l1/seg_3A/layer1.3A.yaml` points to `l1/seg_1A/s0_outputs.schema.json#/validation_bundle`, but that anchor does not exist, and the 1A spec requires schema anchors under `schemas.*.yaml`.
- [Spec vs repo] Schema_ref mismatch for 1B gate artefacts: `validation_bundle_1B` and `validation_passed_flag_1B` point to `schemas.1B.yaml#/validation/validation_bundle_1B` and `schemas.1B.yaml#/validation/passed_flag`, but `schemas.1B.yaml` has no such anchors.
- [Spec vs repo] Missing artefact registry: 3A specs reference `artefact_registry_3A.yaml`, but no such file exists under `contracts/artefact_registry/`.

Segment 3B
- [Spec vs repo] Schema_ref mismatch for 1B egress: `site_locations` in `contracts/dataset_dictionary/l1/seg_3B/layer1.3B.yaml` points to `schemas.1B.yaml#/egress/site_locations`, but `contracts/schemas/layer1/schemas.1B.yaml` has no `egress` section or `site_locations` anchor.
- [Spec vs repo] Schema_ref mismatch for CDN weights: `cdn_weights_ext` points to `schemas.3B.yaml#/reference/cdn_weights_ext_yaml_v1`, but `contracts/schemas/layer1/schemas.3B.yaml` defines no `cdn_weights_ext_yaml_v1` anchor under `reference`.
- [Spec vs repo] Missing ingress schema pack in contracts: `schemas.ingress.layer1.yaml` is referenced by `merchant_ids`, `population_raster`, and `tile_population_weights` in `layer1.3B.yaml`, but the file is only present under `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.ingress.layer1.yaml` and does not exist under `contracts/schemas/`, so these schema_refs cannot resolve in the runtime repo.
- [Spec vs repo] Path token mismatch for 3A handoff: `zone_alloc` in `layer1.3B.yaml` uses `path: data/layer1/3A/zone_alloc/seed={seed}/fingerprint={fingerprint}/` while 3A publishes `fingerprint={manifest_fingerprint}` and other 3B entries use `{manifest_fingerprint}`. This token mismatch breaks deterministic path resolution across the 3A->3B handoff.
- [Spec vs repo] Upstream gate schema_ref mismatches persist: `validation_bundle_1A` uses `contracts/schemas/l1/seg_1A/s0_outputs.schema.json#/validation_bundle` (anchor missing) and `validation_bundle_1B`/`validation_passed_flag_1B` use `schemas.1B.yaml` anchors that do not exist.
- [Spec vs repo] Artefact registry location mismatch: `contracts/artefact_registry_3B.yaml` exists at the contracts root instead of under `contracts/artefact_registry/` like other registries, which complicates automated registry discovery.

Validation gate artefacts (spec expectations)
- 1B S0: requires `validation_bundle_1A` + `_passed.flag` (No PASS → No Read) for the same fingerprint; dictionary must provide IDs and paths for both. Spec: `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s0.expanded.md`.
- 2A S0: requires `validation_bundle_1B` + `_passed.flag` (No PASS → No Read) for the same fingerprint; dictionary governs the path. Spec: `docs/model_spec/data-engine/layer-1/specs/state-flow/2A/state.2A.s0.expanded.md`.
- 2B S0: requires `validation_bundle_1B` + `_passed.flag` for the same fingerprint; dictionary governs the path. Spec: `docs/model_spec/data-engine/layer-1/specs/state-flow/2B/state-flow-overview.2B.md`.
- 3A S0: requires `validation_bundle_1A`, `validation_bundle_1B`, `validation_bundle_2A` + flags; MUST NOT depend on 2B. Spec: `docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s0.expanded.md`.
- 3B S0: requires upstream bundles/flags and a 3B bundle+flag schema anchored in `schemas.layer1.yaml`; dictionary/registry must list them. Spec: `docs/model_spec/data-engine/layer-1/specs/state-flow/3B/state.3B.s0.expanded.md`.

Contract findings (Layer-1)
- Duplicate 1A bundle IDs: `contracts/dataset_dictionary/l1/seg_1A/layer1.1A.yaml` defines both `validation_bundle` and `validation_bundle_1A` with the same path and schema_ref. This creates ambiguous ID resolution for downstream contracts and should be reconciled.
- Schema_ref mismatch: `contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml` uses `schemas.1B.yaml#/validation/passed_flag` for `validation_passed_flag_1A` even though the bundle is 1A and other segments use `schemas.layer1.yaml#/validation/passed_flag` for flags. This is an inconsistent schema anchor for the same artefact type.
- Missing registries for Layer-1 segments: `contracts/artefact_registry` contains only 5A/5B/6A/6B; there are no `artefact_registry_1A.yaml`–`artefact_registry_3B.yaml` despite state-flow specs calling for registry stanzas for validation bundles, flags, and key datasets (e.g., 2A S5, 2B S8, 3A S7, 3B S5).

Implementation alignment checkpoints (Layer-1)
- 2A S0 currently attempts to resolve `validation_bundle_1A`, but the 2A dictionary does not list it; the 2A spec only requires 1B gating. This is an implementation vs contract mismatch to resolve.
- 1B S7/S8 run summaries: dictionary paths place run summaries inside partition paths; current implementation uses `dataset_path.parent` (drops partition tokens). This is implementation vs contract mismatch already captured in engine audit.

---

Layer-2 contract review (5A-5B)

Segment 5A
- [Spec vs repo] Scenario calendar path mismatch: `contracts/dataset_dictionary/l2/seg_5A/layer2.5A.yaml` defines `scenario_calendar_5A` under `data/layer2/5A/scenario/calendar/...`, but `contracts/artefact_registry/artefact_registry_5A.yaml` lists the same dataset under `config/layer2/5A/scenario/calendar/...`. This path-family divergence breaks deterministic lookup for the same logical artefact.
- [Spec vs repo] Missing registry entry for baseline intensity policy: `baseline_intensity_policy_5A` exists in the dataset dictionary and is referenced by 5A.S0/S3/S5, but there is no matching entry in `artefact_registry_5A.yaml`, so sealed-input manifests cannot enumerate it.
- [Spec vs repo] Missing registry entry for sealed outputs: `sealed_outputs_5A` is defined in the dataset dictionary, but there is no corresponding registry entry in `artefact_registry_5A.yaml`.
- [Spec vs repo] Schema anchor duplication: `contracts/schemas/layer2/schemas.5A.yaml` defines `baseline_intensity_policy_5A` twice under `policy`, which is ambiguous in YAML and risks silently overriding one definition.
- [Spec vs repo] Schema_ref mismatch for sealed outputs: `sealed_outputs_5A` points to `schemas.5A.yaml#/validation/sealed_inputs_5A`, but there is no `sealed_outputs_5A` schema anchor; this reuse is undocumented and blurs the contract between sealed inputs vs sealed outputs.

Segment 5B
- [Spec-internal] Registry schema inconsistency: `contracts/artefact_registry/artefact_registry_5B.yaml` uses a top-level `artefacts:` list, while the 5A registry uses `subsegments:` and the Layer-3 registries use a flat list. This structural mismatch complicates automated registry parsing across layers.
- [Spec-internal] Cross-layer dependency naming mismatch: 5B registry dependencies reference 5A artefacts as bare IDs (`scenario_manifest_5A`, `merchant_zone_scenario_local_5A`) instead of manifest keys (e.g., `mlr.5A.*`), unlike the upstream dependency style used in `artefact_registry_5A.yaml`. This inconsistency can break dependency resolution rules across registries.

---

Layer-3 contract review (6A-6B)

Segment 6A
- [Spec-internal] Missing registry entries for validation outputs: `contracts/dataset_dictionary/l3/seg_6A/layer3.6A.yaml` defines `s5_validation_report_6A` and `s5_issue_table_6A`, but `contracts/artefact_registry/artefact_registry_6A.yaml` lists only `validation_bundle_index_6A` and `validation_passed_flag_6A`. The report and issue-table artefacts cannot be sealed or referenced via registry.
- [Spec-internal] Placeholder schema pack: `contracts/schemas/layer3/schemas.6A.yaml` declares the 6A anchors as placeholders pending concrete field definitions. This means the contract currently cannot enforce structural validation for 6A business datasets despite `columns_strict: true` in the dictionary.

Segment 6B
- [Spec-internal] Placeholder schema pack: `contracts/schemas/layer3/schemas.6B.yaml` states the S1-S4 anchors will be fleshed out later, so the current schema pack cannot fully enforce field-level validation for 6B outputs yet.
