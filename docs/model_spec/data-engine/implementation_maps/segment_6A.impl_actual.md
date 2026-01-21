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

### Entry: 2026-01-21 17:37

6A.S1 expanded spec review (lean path focus):
- Read `docs/model_spec/data-engine/layer-3/specs/state-flow/6A/state.6A.s1.expanded.md` to identify heavy or unrealistic requirements and capture a minimal-relaxation plan before implementation.
- Potentially heavy / unrealistic bindings that can slow S1 or block runs:
  - **Run-report dependency on S0** (Section 2.2): requires a "latest 6A.S0 run-report" PASS, but Layer-3 contracts do not define `segment_state_runs` or any run-report dataset for 6A. This is a blocking requirement in practice. Lean option: treat missing run-report as WARN and accept S0 gate receipt + sealed-inputs digest as sufficient.
  - **RNG trace/audit verbosity**: spec implies detailed `rng_audit_log` + `rng_trace_log` per event. At large N this is prohibitive IO. Lean option: emit aggregated events per cell/batch (counts + counter range) and keep `rng_trace_log` as sparse sampling (or per-batch only), not per-party.
  - **Canonical ordering constraints**: strict ordering can force global materialisation or expensive sorting. Lean option: deterministic cell ordering + deterministic intra-cell generation, but avoid any global sort; rely on canonical writer order via streaming batches per cell.
  - **Digest recomputation**: recomputing `sealed_inputs_digest_6A` is required; that is fine, but avoid re-hashing large upstream bundles (S0 already did) and treat sealed_inputs rows as the authority.
  - **Summary tables and full cross-checks**: full summary table creation and full-table validations can double IO. Lean option: make `s1_party_summary_6A` optional and compute summary from streaming counters rather than re-scanning the base table.
- Minimal-relaxation implementation approach (to propose/confirm with user):
  1. **Eligibility gating**: require `s0_gate_receipt_6A` + `sealed_inputs_6A` + digest match; treat S0 run-report as optional (warn if missing).
  2. **Population planning**: compute `N_cell` in-memory (small) and stream party generation per cell in canonical order; no global sort or full buffering.
  3. **RNG logging**: emit two event logs (`party_count_realisation`, `party_attribute_sampling`) at cell/batch granularity with counter ranges; keep `rng_audit_log` as a concise summary row; `rng_trace_log` optional/sampled.
  4. **Output summary**: maintain counters during streaming; if `s1_party_summary_6A` is requested, write from counters (no re-read).
  5. **Performance guardrails**: enforce a hard cap on total parties and expose a parameter-hash-backed scale factor to keep dev runs fast.
- Questions for approval:
  - Allow missing S0 run-report to be WARN-only (since L3 has no run-report contract)?
  - Accept aggregated RNG logs (per-cell/batch) instead of per-party trace/audit rows?
  - Keep `s1_party_summary_6A` optional and derived from counters only?

### Entry: 2026-01-21 17:55

6A.S1 implementation plan (lean path, decisions confirmed):
- **Contracts source:** use `ContractSource(config.contracts_root, config.contracts_layout)` so dev can run from `model_spec` and production can switch to root packs without code changes.
- **Gating decisions (approved relaxations):**
  - Require `s0_gate_receipt_6A` + `sealed_inputs_6A` + digest match; treat missing S0 run-report as WARN-only because L3 contracts do not define `segment_state_runs`.
  - Enforce strict schema compliance for S1 outputs (schema-validated, columns strict).
  - RNG logs: emit aggregated `rng_event_*` rows per country/party_type (count realisation + attribute sampling) and write a single `rng_trace_log` row per substream with totals; no per-party tracing.
  - Summary: emit `s1_party_summary_6A` from streaming counters only (no re-scan of base).
- **Inputs / authorities:**
  - Required sealed inputs (ROW_LEVEL): `prior_population_6A`, `prior_segmentation_6A`, `taxonomy_party_6A`, `outlet_catalogue` (for country weights), `merchant_zone_profile_5A` (for expected arrivals by country).
  - Contracts (METADATA_ONLY): `schemas.layer3.yaml`, `schemas.6A.yaml`, `dataset_dictionary.layer3.6A.yaml`, `artefact_registry_6A.yaml`.
  - Any hint required by `population_priors.inputs_allowed.required_hints` but missing -> WARN + fallback (approved relaxation).
- **Region mapping decision (lean):**
  - No sealed country→region mapping exists; derive `region_id` deterministically by hashing `country_iso` into the region list defined in `segmentation_priors_6A.region_party_type_mix`.
  - Log mapping rule and per-region counts; treat as a relaxation until a sealed region taxonomy is added.
- **Population planning algorithm:**
  1. Load priors/taxonomy (validate against schema refs).
  2. Compute country weights from outlet counts and merchant_zone_profile expected arrivals:
     - `weight = (outlet_count + outlet_offset)^outlet_exponent * (arrivals + arrival_offset)^arrival_exponent` per country; apply `country_weight_floor`.
     - If arrivals data missing or totals zero in `arrivals_based_v1`, fallback to outlet-only estimate and log WARN.
  3. Compute `N_world_target`:
     - `arrivals_based_v1`: `expected_arrivals_total / (arrivals_per_active_party_per_week * active_fraction)`.
     - `outlets_based_v1`: `outlets_total * parties_per_outlet`.
     - Apply seed-scale lognormal if configured; clamp to `[N_world_min, N_world_max]`.
  4. Integerise country totals via largest-remainder (deterministic tie by country code).
  5. Split each country into party_type counts using region-level mixes; split each country+party_type into segment counts via region-type segment mixes (largest-remainder + RNG tie-break).
- **RNG envelope (lean but auditable):**
  - Use Philox2x64-10 from `engine.layers.l1.seg_1A.s1_hurdle.rng` with a 6A-specific hash prefix; allocate counters per substream (`party_count_realisation`, `party_attribute_sampling`).
  - Emit envelope fields (`rng_counter_before_*`, `rng_counter_after_*`, `draws`, `blocks`) at country/party_type granularity.
- **Output writing (streaming, idempotent):**
  - Write `s1_party_base_6A.parquet` via `pyarrow.ParquetWriter` (row-group streaming), then publish atomically; fail on output conflict.
  - Generate parties in canonical order: `country_iso` → `segment_id` → `party_type` → `party_id` with sequential IDs for determinism.
  - Use in-loop counters to assemble `s1_party_summary_6A` and write a single parquet file.
- **Logging/observability:**
  - Story header log; phase logs for gating, input loading, population planning, integerisation, generation, and outputs.
  - Progress logs for long loops with elapsed/processed/rate/ETA (monotonic).
- **Validation/testing:**
  - Validate priors/taxonomy with schema pack anchors.
  - Schema-check a sample of output rows plus summary frame.
- Run `python -m py_compile` and `make segment6a-s1` after implementation; terminate early if ETA exceeds target.

### Entry: 2026-01-21 18:19

6A.S1 integration + execution plan (post-implementation wiring):
- Add Makefile wiring for S1 (`SEG6A_S1_RUN_ID`, args, CLI command, target, .PHONY).
- Verify S1 runner/CLI files are complete; avoid functional changes unless a blocker is found.
- Run `python -m py_compile` for new S1 modules to catch syntax errors early.
- Execute `make segment6a-s1` and monitor progress logs for ETA; abort if it exceeds target run time.
- Log execution outcomes in logbook with timestamp and note any additional decisions or deviations.

### Entry: 2026-01-21 18:21

6A.S1 runtime error fix (StepTimer logging):
- Observed `TypeError: _StepTimer.info() takes 2 positional arguments but 6 were given` during `make segment6a-s1`.
- Decision: allow `_StepTimer.info` to accept `*args` and pass them through to `logger.info`, matching other logging calls that use format strings.
- Plan: update `_StepTimer.info(self, message: str, *args)` and leave call sites unchanged; re-run `make segment6a-s1`.

### Entry: 2026-01-21 18:22

6A.S1 schema $defs resolution fix:
- Observed `jsonschema.exceptions._WrappedReferencingError` due to `$ref: "#/$defs/hex64"` inside subschema without `$defs`.
- Root cause: `_schema_from_pack` returns a nested schema node without carrying top-level `$defs`, so local `$ref` lookups fail.
- Decision: inject root `$defs` into the returned subschema when missing.
- Plan: after `_schema_from_pack` resolves and normalizes the node, attach `$defs` from the schema pack if present and not already defined; re-run `make segment6a-s1`.

### Entry: 2026-01-21 18:25

6A.S1 sealed_inputs schema validation fix:
- Observed `sealed_inputs_6A.json` is a list of rows, but schema anchor `#/gate/6A/sealed_inputs_6A` defines a single row object.
- Decision: treat list payloads as arrays-of-row when schema type is `object` by wrapping the schema in `{"type":"array","items":schema}` before validation.
- Plan: update `_validate_payload` to detect list payload + object schema and validate as an array; re-run `make segment6a-s1`.

### Entry: 2026-01-21 18:26

6A.S1 array wrapper $defs fix:
- New error: after wrapping the sealed_inputs schema into an array, `$defs` lived inside `items`, so `#/$defs/...` references still failed.
- Decision: when wrapping object schema into array, hoist `$defs` to the root of the wrapper and keep `items` clean.
- Plan: modify `_validate_payload` to extract `$defs` from the object schema and attach it at the array root before validation.

### Entry: 2026-01-21 18:27

6A.S1 sealed_inputs digest alignment:
- Observed `sealed_inputs_digest_mismatch` between S1 recompute and S0 receipt.
- Root cause: S1 digest logic uses different field order/set and sorts differently than S0.
- Decision: match S0 digest law: sort rows by `(owner_layer, owner_segment, manifest_key, path_template)` and hash canonical rows with ordered fields including `schema_ref` + `notes`.
- Plan: update `_sealed_inputs_digest` in S1 to mirror S0’s implementation and re-run `make segment6a-s1`.

### Entry: 2026-01-21 18:28

6A.S1 sealed input path resolution:
- New failure: `Dataset entry missing path` when resolving sealed input entries, because sealed inputs use `path_template` (not `path`).
- Decision: allow `_resolve_dataset_path` to fall back to `path_template` when `path` is missing.
- Plan: update `_resolve_dataset_path` to accept either field, then re-run `make segment6a-s1`.

### Entry: 2026-01-21 18:29

6A.S1 RNG event temp file collision:
- Failure: `rng_event_party_attribute_sampling` publish failed because temp file was already moved when publishing `rng_event_party_count_realisation` (both used `part-00000.jsonl` in the same tmp dir).
- Decision: ensure distinct temp filenames for count vs attribute event JSONL in the temp directory.
- Plan: if `rng_count_path.name == rng_attr_path.name`, override temp names to `party_count_realisation.jsonl` and `party_attribute_sampling.jsonl` before publishing.

### Entry: 2026-01-21 18:31

6A.S1 stabilization outcome:
- Applied fixes for `$defs` injection, sealed_inputs list validation, digest alignment, `path_template` resolution, and RNG temp file naming.
- `make segment6a-s1` completes successfully for run_id `d61f08e2e45ef1bc28884034de4c1b68` (outputs: `s1_party_base_6A`, `s1_party_summary_6A`, RNG logs + event JSONL).
- Noted warnings: `min_parties_per_country` below threshold in several countries; Polars `DataOrientationWarning` during buffer DataFrame creation (non-fatal).
