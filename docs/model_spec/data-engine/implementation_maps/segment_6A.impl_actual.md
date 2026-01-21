# segment_6A.impl_actual.md
# Implementation logbook (actuals) for Segment 6A

This file captures in-progress design reasoning and implementation decisions for Segment 6A.

### Entry: 2026-01-21 15:45

Spec review kickoff:
- Begin 6A spec review with a lean-efficiency lens; identify unrealistic requirements and propose minimal relaxations.
- No code changes in this phase; only documentation review and notes.
- Documents to read: state.6A.s0–s5 expanded specs and 6A contracts (dictionary, registry, schemas).

### Entry: 2026-01-21 15:55

S0 spec review notes (lean-path focus, no implementation yet):
- S0 is strictly control-plane: bind `manifest_fingerprint` + `parameter_hash`, verify upstream HashGates, validate 6A contracts, resolve 6A priors/taxonomies, emit `s0_gate_receipt_6A` + `sealed_inputs_6A`.
- Potentially unrealistic/expensive requirements at scale:
  - Full bundle digest recomputation for every upstream segment (1A-3B, 5A-5B) requires reading all bundle files; this is expensive for large bundles.
  - `sealed_inputs_6A` digest requires hashing every artefact (including large upstream egress) unless policy allows metadata-only digesting; could be prohibitively slow on large inputs.
  - Contract validation expects 6A schemas to be fully concrete; current `schemas.6A.yaml` includes placeholder anchors and may not yet match state-expanded specs.
- Lean relaxations to consider (minimal risk, still deterministic):
  1) Upstream HashGate verification: verify `validation_bundle_index_*` + `_passed.flag` only (skip rehashing each evidence file) unless policy requests deep audit. Record in gate receipt that deep verification was skipped.
  2) `sealed_inputs_6A` digests: compute digests for small policies/configs; for large data surfaces marked `METADATA_ONLY`, allow digest from bundle index or a lightweight metadata hash (size + mtime + path) and mark the method used.
  3) 6A contract coherence: enforce dictionary/registry/schema consistency, but tolerate placeholder schema anchors for datasets not yet emitted by the state (log WARN + defer strict validation to state S1–S5 when schemas are concrete).
- Questions to confirm before implementation:
  - Should upstream HashGate verification be shallow by default (index + `_passed.flag`) with optional deep rehash, or must we keep deep rehashing for all segments?
  - For large upstream egress marked `ROW_LEVEL`, do you still want full content hashing in S0, or is it acceptable to record a lightweight digest and rely on downstream state checks?
  - Are we allowed to treat placeholder 6A schema anchors as valid for S0 (control-plane) and enforce detailed validation later?

### Entry: 2026-01-21 16:02

Correction on S0 schema posture:
- Withdraw the earlier placeholder-tolerance suggestion.
- Enforce **strict** schema compliance at S0: all `schema_ref` anchors must resolve to concrete definitions; any placeholder/undefined anchors cause S0 to FAIL.
- Lean-path remains for HashGate verification and digesting, but schema validation is strict.

### Entry: 2026-01-21 16:05

Schema description correction:
- Update `schemas.6A.yaml` description to remove the placeholder/"to be extended" language, aligning it with strict schema compliance at S0.
- No schema content changes; documentation-only update.

### Entry: 2026-01-21 16:14

6A.S0 implementation plan (lean but strict schema compliance):
- Objective: implement `6A.S0` gate runner to verify upstream HashGates (1A-3B, 5A-5B), validate 6A contracts/priors, and emit `s0_gate_receipt_6A` + `sealed_inputs_6A` with a deterministic digest.
- Inputs/authorities to resolve (catalog-driven, no hard-coded paths):
  - Run identity: `runs/<run_id>/run_receipt.json` (seed, `parameter_hash`, `manifest_fingerprint`).
  - Contract sources via `ContractSource(config.contracts_root, config.contracts_layout)`:
    - 6A dictionary/registry: `dataset_dictionary.layer3.6A.yaml`, `artefact_registry_6A.yaml`.
    - Schema packs: `schemas.layer3.yaml`, `schemas.6A.yaml`, plus upstream packs needed for schema_ref validation (`schemas.1A/1B/2A/2B/3A/3B/5A/5B.yaml`, `schemas.layer1.yaml`, `schemas.layer2.yaml`).
  - Upstream gate artefacts (from 6A dictionary reference_data): `validation_bundle_*` + `validation_passed_flag_*` for 1A-3B and 5A-5B.
  - Upstream egress surfaces (from 6A dictionary reference_data): `outlet_catalogue`, `site_locations`, `site_timezones`, `tz_timetable_cache`, `zone_alloc`, `zone_alloc_universe_hash`, `virtual_classification_3B`, `virtual_settlement_3B`, `edge_universe_hash_3B`, `virtual_routing_policy_3B`, `merchant_zone_profile_5A`, `arrival_events_5B`.
  - 6A priors/taxonomies/policies (dictionary entries consumed_by 6A.S0).
- Alternatives considered:
  1) Full deep-hash of all upstream egress/arrival data at S0. Rejected as too heavy for control-plane.
  2) Rely solely on `_passed.flag` content without re-deriving bundle digests. Rejected; still compute bundle digest from each segment’s index per HashGate law to confirm flag integrity.
  3) Skip schema validation for priors/configs and only hash. Rejected; user requires strict schema compliance at S0.
- Decisions:
  - Strict schema compliance: every `schema_ref` must resolve and every 6A prior/policy payload must validate against its schema.
  - HashGate verification per-segment law: reuse bundle index parsing rules (e.g., 1A/1B/2A use index file list; 2B uses index list; 3A uses member digests; 3B uses index members + file hashing; 5A/5B use layer2 validation bundle indices). Compare computed digest to `_passed.flag`.
  - Lean sealed-inputs digesting: for large row-level datasets (upstream egress, arrival events), use a structural digest derived from `path_template`, `schema_ref`, and `partition_keys` (not full data rehash). For policies/priors/contracts, hash file contents and verify registry digest if provided.
  - For `arrival_events_5B` presence, allow wildcard resolution when `{scenario_id}` is unresolved to avoid reading scenario manifests; require at least one matching partition.
- Planned mechanics (code structure):
  - New module: `packages/engine/src/engine/layers/l3/seg_6A/s0_gate/runner.py`.
  - Provide helpers for run receipt resolution, schema-anchor validation, JSON/YAML loading, bundle index validation, bundle digest calculation, and sealed-inputs digest canonicalization.
  - Build `sealed_inputs_6A` rows from dictionary entries where `lineage.consumed_by` includes `6A.S0`, plus contract rows (schemas + dictionary + registry) with role `CONTRACT`.
  - Assign roles: `UPSTREAM_EGRESS`, `UPSTREAM_GATE_BUNDLE`, `UPSTREAM_GATE_FLAG`, `POPULATION_PRIOR`, `SEGMENT_PRIOR`, `PRODUCT_PRIOR`, `DEVICE_IP_PRIOR`, `FRAUD_ROLE_PRIOR`, `TAXONOMY`, `POLICY`, `CONTRACT`.
  - Ensure ordering for digest: sort by `(owner_layer, owner_segment, manifest_key)`; digest fields in schema order.
  - Validate `sealed_inputs_6A` and `s0_gate_receipt_6A` against `schemas.layer3.yaml` anchors.
  - Output handling: if outputs already exist, verify digest/payload match and skip; if partial outputs exist, fail.
- Invariants to enforce:
  - `parameter_hash` and `manifest_fingerprint` are valid hex64.
  - No duplicate `(owner_layer, owner_segment, manifest_key)` in sealed inputs.
  - Schema refs resolve to the correct pack; no conflicting `$defs` between `schemas.layer3.yaml` and `schemas.6A.yaml`.
  - Required inputs exist; OPTIONAL inputs missing are logged but not fatal.
- Logging & observability:
  - Story header log: objective, required gates, and outputs.
  - Per-segment HashGate logs: bundle path, digest method, PASS/FAIL status.
  - Sealed-inputs summary: total rows, counts by role/status, digest.
  - Progress logs with elapsed/rate/ETA for any multi-file hashing loops.
- Resumability hooks:
  - Skip publish if existing outputs match; otherwise fail on partial outputs.
  - Run-report row appended for S0 (segment_state_runs) with upstream gate counts and sealed_inputs_digest.
- Performance considerations:
  - Avoid row-level scans of large datasets.
  - Use structural digest for large partitions and content digest for small config/policy files.
- Validation/tests:
  - `python -m py_compile` for new runner and CLI.
  - Add `make segment6a-s0` target and run once after implementation (if outputs conflict, instruct user to delete or use a new run_id).

### Entry: 2026-01-21 16:23

Run-report path check:
- Reviewed `dataset_dictionary.layer3.6A.yaml` for a `segment_state_runs` (or similar) dataset; none present.
- Decision: do not emit a segment_state_runs row for 6A.S0 yet; rely on run log + gate receipt for audit. If/when Layer-3 contracts add a run-report dataset, wire it then.

### Entry: 2026-01-21 17:03

6A.S0 implementation decisions while coding:
- Implemented `run_s0` end-to-end with upstream HashGate verification, sealed-input construction, digesting, schema validation, and idempotent output handling.
- Error-code alignment with spec:
  - Upstream gates now map to `UPSTREAM_HASHGATE_MISSING`, `UPSTREAM_HASHGATE_SCHEMA_INVALID`, `UPSTREAM_HASHGATE_DIGEST_MISMATCH`.
  - Run-receipt resolution issues map to `IO_READ_FAILED` (closed-code set compliance).
  - Contract-load failures map to `L3_SCHEMA_MISSING_OR_INVALID`.
  - Output conflicts map to `GATE_RECEIPT_CONFLICT` / `SEALED_INPUTS_CONFLICT`.
- Sealed-inputs digest strategy (lean path):
  - Structural digest for upstream egress/arrival data and ignored items (path_template + schema_ref + partition_keys).
  - Content digest (sha256 of file bytes) for 6A priors/taxonomies/policies; validate payloads against `schemas.6A.yaml` anchors.
  - Optional priors missing are skipped with log; required missing aborts with `PRIOR_PACK_MISSING`.
- Added contract rows (schemas + dictionary + registry) to `sealed_inputs_6A` and `contracts_6A` summary.
  - Introduced `schemas.layer3.yaml#/$defs/contract_file` as a permissive contract-file anchor; used for these rows.
- Sealed-input schema handling:
  - `schemas.layer3.yaml#/gate/6A/sealed_inputs_6A` is defined as an object; validate by wrapping as an array schema when needed.
  - Enforce unique `(owner_layer, owner_segment, manifest_key)` key.
- Receipt handling:
  - Build `s0_gate_receipt_6A` with only schema-allowed fields (`manifest_fingerprint`, `parameter_hash`, `spec_version_6A`, `upstream_segments`, `contracts_6A`, `sealed_inputs_digest_6A`).
  - On existing outputs: recompute digest, verify stored receipt payload and digest; otherwise fail with conflict codes.
- Operational hooks:
  - Added CLI `engine.cli.s0_gate_6a` and Makefile `segment6a-s0` target for consistent invocation.

### Entry: 2026-01-21 17:05

Progress logging adjustment:
- Added per-file progress tracking to upstream bundle hashing (`_bundle_hash`, `_bundle_hash_from_index`) so long bundle scans emit elapsed/rate/ETA logs.

### Entry: 2026-01-21 17:06

Contract schema anchor validation:
- Added an explicit `_validate_schema_ref` check for `schemas.layer3.yaml#/$defs/contract_file` so S0 fails fast if the contract-file anchor is missing or malformed.

### Entry: 2026-01-21 17:07

Sealed-inputs observability:
- Added a dedicated status-count log (`REQUIRED`/`OPTIONAL`/`IGNORED`) after computing `sealed_inputs_6A` to make gate outcomes clearer in run logs.

### Entry: 2026-01-21 17:11

Contract registry fix:
- Fixed YAML indentation for `sealed_inputs_6A` in `artefact_registry_6A.yaml` so it is correctly nested under the 6A artifacts list.

### Entry: 2026-01-21 17:11

Schema pack YAML fix:
- Repaired missing spaces in inline map entries (`thresholds:{...}`) in `schemas.layer3.yaml` so the schema pack parses correctly.

### Entry: 2026-01-21 17:12

Schema defs compatibility:
- Relaxed `_assert_schema_defs_consistent` to treat `$defs` entries in `schemas.6A.yaml` that are pure `$ref` links to `schemas.layer3.yaml` as compatible (e.g., `hex64`).

### Entry: 2026-01-21 17:14

Upstream index validation:
- Switched `_validate_index` to use `validate_dataframe` (table-to-JSON-schema adapter) when index payloads are lists, matching the 5B S0 gate and avoiding `type: table` validator errors.

### Entry: 2026-01-21 17:15

HashGate flag parsing:
- Added BOM stripping in `_parse_pass_flag_any` so `_passed.flag` files with UTF-8 BOM parse correctly.

### Entry: 2026-01-21 17:16

HashGate regex fix:
- Corrected `_FLAG_PATTERN` to use `\s*` instead of a literal `\\s*` so `_passed.flag` lines match as intended.

### Entry: 2026-01-21 17:18

5B HashGate index path:
- Updated 5B HashGate verification to read `index.json` (per dataset dictionary path) instead of `validation_bundle_index_5B.json`.

### Entry: 2026-01-21 17:20

5B HashGate digest law:
- Switched 5B bundle digest derivation to hash bundle file contents (same law as 5B.S5) instead of hashing the `sha256_hex` list from the index.

### Entry: 2026-01-21 17:21

Schema anchor traversal:
- Updated `_schema_from_pack` and `_schema_anchor_exists` to traverse into `properties` when resolving anchors like `#/prior/population_priors_6A` or `#/gate/6A/...` so grouped schema packs validate correctly.

### Entry: 2026-01-21 17:26

Plan to repair failing prior packs (starting with `prior_ip_counts_6A`):
- Observed 6A.S0 fails on `prior_ip_counts_6A` schema validation after upstream HashGates pass.
- Approach:
  - Validate `config/layer3/6A/priors/ip_count_priors_6A.v1.yaml` against `schemas.6A.yaml#/prior/ip_count_priors_6A` to capture precise missing/invalid fields.
  - Patch the prior pack minimally to satisfy required fields while preserving intended semantics (no behavior changes beyond completing required fields).
  - Re-validate via the same schema anchor and re-run `make segment6a-s0` to surface any additional prior-pack failures.
- Expected edits:
  - `ip_edge_demand_model.region_multiplier` currently has only `enabled`; schema requires `mode`, `region_scores`, `clip_multiplier`. Add neutral defaults with consistent region ids and a safe clip range.
  - Keep other sections unchanged unless validation exposes further schema mismatches.
- Repeat loop for any other prior packs that fail after this fix (validate -> patch -> re-run).

### Entry: 2026-01-21 17:27

`prior_ip_counts_6A` repair:
- Added required `region_multiplier` fields (`mode`, `region_scores`, `clip_multiplier`) with neutral defaults to satisfy `schemas.6A.yaml#/prior/ip_count_priors_6A`.
- Verified schema validation passes for `config/layer3/6A/priors/ip_count_priors_6A.v1.yaml`.

### Entry: 2026-01-21 17:28

`device_linkage_rules_6A` repair:
- Removed unsupported `merchant_owner_role_id` from `owner_policy` to satisfy `schemas.6A.yaml#/policy/device_linkage_rules_6A` (schema only allows `owner_kind_by_group`, `primary_owner_role_id`, `selection_scope`).
- Verified schema validation passes for `config/layer3/6A/policy/device_linkage_rules_6A.v1.yaml`.

### Entry: 2026-01-21 17:30

Contract/prior digest encoding:
- Fixed `sha256_file` usage in 6A.S0 so `sha256_hex` stores the digest string (not the `FileDigest` object) for contract rows and prior-pack rows.
