# Segment 3A Implementation Map (Actual)

## S0 - Gate & Sealed Inputs

### Entry: 2026-01-17 09:55

Scope for this pass: read all 3A expanded docs + S0 contracts, then design the
S0 implementation plan only (no code yet).

Files read (expanded docs + contracts + data-intake):
- docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s0.expanded.md
- docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s1.expanded.md
- docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s2.expanded.md
- docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s3.expanded.md
- docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s4.expanded.md
- docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s5.expanded.md
- docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s6.expanded.md
- docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s7.expanded.md
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/dataset_dictionary.layer1.3A.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/schemas.3A.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/artefact_registry_3A.yaml
- docs/model_spec/data-engine/layer-1/specs/data-intake/3A/zone_mixture_policy_3A.md
- docs/model_spec/data-engine/layer-1/specs/data-intake/3A/country_zone_alphas_3A.md
- docs/model_spec/data-engine/layer-1/specs/data-intake/3A/zone_floor_policy_3A.md

Problem statement (S0):
- Implement the 3A gate + sealed-inputs root so every downstream 3A state can
  rely on a deterministic, manifest_fingerprint-scoped input inventory and on
  re-verified upstream PASS gates (1A/1B/2A only).
- S0 must remain RNG-free, deterministic, and only read catalogued inputs.

Assumptions and constraints (from S0 spec):
- Must re-verify validation bundles + _passed.flag for 1A, 1B, 2A (HashGate).
- Must NOT depend on 2B runtime outputs; 2B policy `day_effect_policy_v1` is a
  governed input and should be sealed.
- Must seal: zone_mixture_policy, country_zone_alphas, zone_floor_policy,
  day_effect_policy_v1, iso3166_canonical_2024, tz_world_2025a, outlet_catalogue,
  and optional 2A surfaces (site_timezones, tz_timetable_cache, s4_legality_report).
- Output `s0_gate_receipt_3A` + `sealed_inputs_3A` only; no other outputs.
- All writes go to run-local paths; inputs resolve run-local staged → external
  roots; external inputs must be recorded in sealed_inputs_3A with digests.
- Path↔embed equality required for manifest_fingerprint and other tokens.

Open confirmations before coding:
1) Output format for `sealed_inputs_3A`:
   - Schema in schemas.3A.yaml defines a single object shape (row). Dictionary
     lists `format: json` and a single file path.
   - In prior segments, sealed_inputs are emitted as JSON array (rows) or JSONL
     lines. I will align with the existing engine helper used by 2A/2B S0
     (emit list + validate each row) unless you want a different format.
2) Policy version source in S0 gate receipt:
   - Policies/priors have `{policy_version}` and `{prior_pack_version}` tokens
     in the dictionary and registry, while data-intake docs require `version`
     inside the policy files (non-placeholder).
   - I will use the policy file’s `version` as the primary authority and log
     any mismatch vs registry/dictionary placeholders as a hard fail, unless
     you want to tolerate placeholders in dev mode.
3) Optional 2A inputs:
   - Spec marks `site_timezones`, `tz_timetable_cache`, `s4_legality_report` as
     optional. Plan is: include them in sealed_inputs only when registry entries
     resolve + path exists; otherwise log “optional_missing” and continue.

Detailed plan (pre-implementation):
1) Contracts + catalogues:
   - Load schema packs:
     `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`, `schemas.1A.yaml`,
     `schemas.1B.yaml`, `schemas.2A.yaml`, `schemas.2B.yaml`, `schemas.3A.yaml`.
   - Load dictionaries:
     `dataset_dictionary.layer1.1A.yaml`, `dataset_dictionary.layer1.1B.yaml`,
     `dataset_dictionary.layer1.2A.yaml`, `dataset_dictionary.layer1.2B.yaml`,
     `dataset_dictionary.layer1.3A.yaml`.
   - Load registries:
     `artefact_registry_1A.yaml`, `artefact_registry_1B.yaml`,
     `artefact_registry_2A.yaml`, `artefact_registry_2B.yaml`,
     `artefact_registry_3A.yaml`.
   - Ensure contract source is `model_spec` (dev mode) but resolve via the
     shared loader so switching to root contracts is config-only.

2) Resolve identity + paths:
   - Resolve `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`.
   - Resolve run-local output roots: `runs/<run_id>/data/layer1/3A/...`
   - Resolve external roots from config (shared inputs, reference data).

3) Upstream gate verification (HashGate):
   - For each of 1A/1B/2A:
     - Resolve `validation_bundle_*` path + `_passed.flag`.
     - Read `index.json`, recompute composite digest (canonical order), compare
       to `_passed.flag`. On mismatch → abort with `E3A_S0_001_*`.
     - Record gate entries in `s0_gate_receipt_3A` (bundle_id/path/flag/sha/status).

4) Enumerate sealed policy set:
   - Policies: zone_mixture_policy, country_zone_alphas, zone_floor_policy,
     day_effect_policy_v1.
   - For each:
     - Resolve path from dictionary/registry.
     - Validate against schema_ref.
     - Compute SHA-256 digest (streaming).
     - Capture policy version (from file) and record in gate receipt.
     - If registry digest exists and mismatches computed → fail closed.

5) Enumerate sealed input inventory:
   - Required:
     - upstream validation bundles + passed flags (1A/1B/2A)
     - outlet_catalogue
     - iso3166_canonical_2024
     - tz_world_2025a
     - zone_mixture_policy, country_zone_alphas, zone_floor_policy,
       day_effect_policy_v1
   - Optional:
     - site_timezones, tz_timetable_cache, s4_legality_report
   - For each resolved artefact:
     - Resolve path and schema_ref from dictionary/registry.
     - Compute sha256 (streaming if large).
     - Capture owner_segment, artefact_kind, logical_id, role, license_class.
   - If required input missing or digest mismatch → abort.
   - If optional input missing → log + continue.

6) Output materialisation + idempotence:
   - Write outputs to run-local tmp directory:
     - `s0_gate_receipt_3A.json`
     - `sealed_inputs_3A.json` (format TBD; see confirmations).
   - Validate outputs against `schemas.3A.yaml` anchors.
   - Atomic publish to final paths; if already exists:
     - If byte-identical → log idempotent OK.
     - If different → fail with immutability violation.

7) Observability/logging:
   - Story header log: objective, upstream gates, sealed inputs, outputs.
   - Gate logs: for each segment, include bundle path, flag, digest, status.
   - Sealing logs: counts of required/optional inputs, missing optional list.
   - Progress logs for any long loops (artefact list) with elapsed/rate/ETA.
   - Run-report: emit segment_state_runs row with PASS/FAIL, timing, counts,
     and error code mapping per spec.

8) Validation + tests:
   - Unit: HashGate verification on known good bundle + mismatch cases.
   - Integration: run `make segment3a-s0` after 1A/1B/2A complete; ensure
     outputs match schema + idempotent rerun.
   - Negative: missing required input -> fail with correct error code.

Performance considerations:
- Stream digests for large artefacts (Parquet, bundles).
- Cache schema packs/dictionaries to avoid repeated loads.
- Avoid reading full datasets; only hash or validate metadata.

Resumability hooks:
- If outputs exist and match, skip rewrite and report idempotent PASS.
- If run aborted mid-way, temp directory is safe to delete and re-run.

Pending: confirm the three open points above before coding.

### Entry: 2026-01-17 10:06

Decisions confirmed for S0 implementation:
1) `sealed_inputs_3A` output format:
   - Emit a single JSON file containing a list of row objects (array of
     `sealed_inputs_3A` rows). Validate each row against
     `schemas.3A.yaml#/validation/sealed_inputs_3A` before publish.
   - Rationale: aligns with existing S0 helpers used in 2A/2B, keeps dictionary
     `format: json`, and preserves deterministic output.

2) Policy/prior version authority + placeholders:
   - Treat the policy/prior file `version` field as canonical and require it
     to be non-placeholder. If registry `semver` is concrete, enforce equality
     with the policy `version`; if registry `semver` is placeholder, accept the
     policy version and record it in the gate receipt.
   - Any mismatch with a concrete registry semver => fail closed.

3) Optional 2A inputs:
   - `site_timezones`, `tz_timetable_cache`, `s4_legality_report` are optional.
   - Include in `sealed_inputs_3A` only if path resolves and artefact exists.
   - If missing: log `optional_missing` and continue. If present but digest
     mismatch or schema invalid: fail closed (not silent).

Plan adjustments based on decisions:
- Update sealed_inputs materialisation to emit JSON list + per-row validation.
- Add explicit policy-version checks (file vs registry semver) before sealing.
 - Add optional-input presence logic with clear logging and strict validation on
  present artefacts.

### Entry: 2026-01-17 10:14

Implementation choices before coding S0:
- Run-report output: emit a `segment_state_runs` JSONL row only (using the
  dictionary entry for `segment_state_runs`). Do not create an ad-hoc S0 report
  file because 3A contracts do not define `s0_run_report_3A`, and I want to
  avoid un-catalogued outputs. This aligns with the S0 doc that calls for the
  layer-level run-report row.
- Catalogue consistency check: load upstream dictionaries (1A/1B/2A/2B) and
  assert that cross-layer dataset IDs used by 3A (validation bundles, passed
  flags, outlet_catalogue, site_timezones, tz_timetable_cache,
  s4_legality_report, day_effect_policy_v1) have matching `path` and
  `schema_ref` in the upstream dictionary vs the 3A dictionary. Any mismatch
  will fail with `E3A_S0_002_CATALOGUE_MALFORMED`.
- Registry digest enforcement: enforce registry `digest` only when it is a
  concrete hex64 (not placeholder); otherwise accept computed digests but
  record them in sealed_inputs and gate receipt.

### Entry: 2026-01-17 10:25

Pre-implementation implementation map entry before coding S0 (detailed steps
and mechanics for the actual implementation pass).

What I am about to build (files + wiring):
- Create `packages/engine/src/engine/layers/l1/seg_3A/s0_gate/runner.py` with
  the full S0 implementation and helper functions.
- Create `packages/engine/src/engine/layers/l1/seg_3A/s0_gate/__init__.py`
  exporting `run_s0`.
- Create CLI entrypoint `packages/engine/src/engine/cli/s0_gate_3a.py` modelled
  after 2A/2B S0 CLIs (contracts layout/root + external roots + run_id).
- Add Makefile wiring for `segment3a-s0` (and `segment3a` chain for now only
  S0), plus `SEG3A_S0_RUN_ID`, `SEG3A_S0_ARGS`, `SEG3A_S0_CMD`, and update
  `.PHONY` list.

Exact logic choices for S0 implementation:
1) Upstream gate validation (HashGate) per segment 1A/1B/2A:
   - Resolve `validation_bundle_*` and `_passed.flag` paths through dictionary
     and registry (no hard-coded paths).
   - Validate `index.json` against the segment-specific bundle index schema:
       1A: `schemas.1A.yaml#/validation/validation_bundle_index_1A`
       1B: `schemas.1B.yaml#/validation/validation_bundle_index_1B`
       2A: `schemas.2A.yaml#/validation/validation_bundle_index_2A`
   - Enforce: every file in bundle is listed; no duplicates; no backslashes;
     file sha256 matches index; composite bundle hash equals `_passed.flag`.
   - On any failure: raise `E3A_S0_001_UPSTREAM_GATE_FAILED` with
     `upstream_segment` and detail.

2) Catalogue consistency checks:
   - Load dictionaries for 1A/1B/2A/2B/3A and registries for 1A/1B/2A/2B/3A.
   - For cross-layer IDs (validation bundles/flags, outlet_catalogue,
     site_timezones, tz_timetable_cache, s4_legality_report, day_effect_policy_v1),
     verify 3A dictionary path + schema_ref match upstream dictionary entries.
   - Verify 3A registry entry path + schema matches 3A dictionary path +
     schema_ref (template-level).
   - Any mismatch -> `E3A_S0_002_CATALOGUE_MALFORMED`.

3) Policy/prior sealing:
   - Required policies: `zone_mixture_policy`, `country_zone_alphas`,
     `zone_floor_policy`, `day_effect_policy_v1`.
   - Parse policy files and extract `version` field (YAML) or `policy_version`
     (JSON) and enforce non-placeholder.
   - If registry semver is concrete: must equal policy version; if registry
     semver is placeholder: accept policy version and record it in receipt.
   - Validate each policy against its schema_ref; on failure
     -> `E3A_S0_004_POLICY_SCHEMA_INVALID`.
   - Missing or ambiguous policy -> `E3A_S0_003_POLICY_SET_INCOMPLETE`.
   - Populate `sealed_policy_set` in receipt with logical_id, owner_segment,
     role (short tag), sha256_hex, schema_ref, optional path.

4) Sealed inputs inventory:
   - Required IDs: validation_bundle_1A/1B/2A, validation_passed_flag_1A/1B/2A,
     outlet_catalogue, iso3166_canonical_2024, tz_world_2025a,
     zone_mixture_policy, country_zone_alphas, zone_floor_policy,
     day_effect_policy_v1.
   - Optional IDs: site_timezones, tz_timetable_cache, s4_legality_report.
     If missing -> log optional_missing and continue. If present but schema or
     digest mismatch -> fail.
   - `artefact_kind` mapping:
       - registry type bundle -> "bundle"
       - type policy -> "policy"
       - type log -> "log"
       - type manifest (passed_flag) -> "dataset"
       - category reference -> "reference"
       - else -> "dataset"
   - `role` mapping (short tags):
       - validation_bundle_*: "upstream_gate_bundle"
       - validation_passed_flag_*: "upstream_gate_flag"
       - outlet_catalogue: "input_egress"
       - site_timezones: "input_egress"
       - tz_timetable_cache: "input_cache"
       - s4_legality_report: "diagnostic_report"
       - iso3166_canonical_2024: "reference_iso"
       - tz_world_2025a: "reference_geo"
       - policies: "zone_mixture_policy", "country_zone_alphas",
         "zone_floor_policy", "day_effect_policy"
   - Compute sha256 for:
       - bundles: composite hash from index.json files (canonical order)
       - directories: hash over all files (stable sorted)
       - files: sha256_file (streamed)
   - Enforce path↔embed equality for manifest_fingerprint and any partition
     tokens (seed, parameter_hash) as per dictionary partitioning.
   - Sort rows by (owner_segment, artefact_kind, logical_id, path).

5) Output construction:
   - `sealed_inputs_3A.json`: JSON array of rows; validate each row against
     `schemas.3A.yaml#/validation/sealed_inputs_3A` with layer1 $defs inlined.
   - `s0_gate_receipt_3A.json`:
       - `version`: registry semver for s0_gate_receipt_3A (expected "1.0.0")
       - `verified_at_utc`: deterministic: prefer existing receipt value (if
         file exists), else `run_receipt.created_utc`. If missing, fail with
         `E3A_S0_010_INFRASTRUCTURE_IO_ERROR` (no wall-clock fallback).
       - `catalogue_versions`: include schema/dictionary/registry version tags
         + sha256 digests of the catalogue files for auditability.
   - Self-consistency checks:
       - Every sealed_policy_set entry must exist in sealed_inputs rows with
         matching logical_id and sha256_hex.
       - Every upstream gate bundle/flag must exist in sealed_inputs.
       - Any mismatch -> `E3A_S0_008_OUTPUT_SELF_INCONSISTENT`.
   - Atomic publish: write via temp dir/file; if output exists and differs,
     raise `E3A_S0_009_IMMUTABILITY_VIOLATION`.

6) Logging:
   - Story header log: objective + gated inputs + outputs.
   - Structured VALIDATION events with codes V-01.. and failure code mapping.
   - Progress logs for hash loops (files processed, elapsed, rate, ETA).
   - Narrative logs for optional inputs and policy set completeness.

7) Run-report:
   - Emit a `segment_state_runs` JSONL row only (no ad-hoc S0 report file).
   - Include status PASS/FAIL, error_code if failure, and counts of required/
     optional sealed inputs for operational scanning.

Implementation guardrails:
- Use ContractSource with `config.contracts_layout` so dev vs prod root switch
  is config-only.
- Avoid any RNG usage.
- Avoid using current wall-clock for receipt fields; use run_receipt created_utc
  or existing receipt field for determinism.
### Entry: 2026-01-17 10:58
Resuming 3A.S0 implementation after interruption. Immediate focus: implement runner + CLI + Makefile wiring, then run segment3a-s0 and iterate to green. Will re-check 2A/2B S0 patterns for helper function parity, then build 3A S0 with narrative logging, strict catalogue checks, and deterministic sealing as planned.

### Entry: 2026-01-17 11:19
Context refresh + immediate fix before continuing implementation:
- I re-read `docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s0.expanded.md`
  and the 3A contracts to confirm the gate/HashGate flow and sealed-input
  schema expectations.
- I reviewed 2A/2B S0 gate runners to ensure I reuse the correct index-schema
  validation helper (they use `validate_dataframe` against `validation_bundle_index_*`).

Design issue discovered:
- In the 3A S0 runner, `_validate_index` was using `Draft202012Validator` directly
  against a `type: table` schema. This will fail with `Unknown type 'table'`,
  because the engine’s schema packs encode tables in a custom shape that must be
  adapted via `validate_dataframe`.

Decision + rationale:
- Switch `_validate_index` to call `validate_dataframe(payload, pack, table_name)`
  and catch `SchemaValidationError`, mirroring the 2A S0 implementation.
- This keeps HashGate validation aligned with the rest of Layer-1 and avoids the
  `Unknown type 'table'` failure mode.

Next steps (still within S0 implementation):
- Finish CLI wiring (`packages/engine/src/engine/cli/s0_gate_3a.py`),
  module export (`seg_3A/s0_gate/__init__.py`), and Makefile targets for
  `segment3a-s0`.
- Run `make segment3a-s0`, capture any failures, and iterate to green with
  detailed logbook + implementation map entries for each fix.

### Entry: 2026-01-17 11:32
Implementation actions completed in this pass (S0 only):
1) Fixed upstream bundle index validation:
   - Replaced `Draft202012Validator(...).iter_errors(...)` on the
     `validation_bundle_index_*` tables with `validate_dataframe(...)`, and
     now trap `SchemaValidationError` to emit a precise `E3A_S0_001` failure.
   - Reason: the index schema is a `type: table` contract (custom shape), so
     direct Draft202012 validation fails with `Unknown type 'table'`. The
     adapter is the canonical table-to-JSONSchema bridge used in 2A/2B.

2) Added 3A S0 module exports:
   - Created `packages/engine/src/engine/layers/l1/seg_3A/s0_gate/__init__.py`
     to export `run_s0` and match other segment layouts.

3) Added the 3A S0 CLI entrypoint:
   - Created `packages/engine/src/engine/cli/s0_gate_3a.py`, mirroring the 2B
     S0 CLI: supports `--contracts-layout`, `--contracts-root`, `--runs-root`,
     `--external-root`, and `--run-id`.
   - The CLI logs the final `run_id`, `parameter_hash`, and `manifest_fingerprint`.

4) Added Makefile wiring for state-by-state execution:
   - New vars: `SEG3A_S0_RUN_ID`, `SEG3A_S0_ARGS`, `SEG3A_S0_CMD`.
   - New targets: `segment3a-s0` and `segment3a` (currently only S0).
   - Added `segment3a` / `segment3a-s0` to `.PHONY` list.

Immediate next steps:
- Run `make segment3a-s0` and capture any errors.
- If failures arise (missing inputs, schema mismatch, digest mismatch), log the
  investigation + resolution steps in this file *as they happen* and in the
  logbook with timestamps.

### Entry: 2026-01-17 11:36
Runtime failure observed on first `make segment3a-s0`:
- Error: `E3A_S0_002_CATALOGUE_MALFORMED` during cross-layer dictionary check.
- Detail: `tz_world_2025a` has `schema_ref` mismatch:
  - 3A dictionary: `schemas.ingress.layer1.yaml#/tz_world_2025a`
  - Upstream (1A dictionary): `schemas.ingress.layer1.yaml#/tz_world_shp`
  - Both anchors resolve to the same schema (`tz_world_shp` is an alias to
    `tz_world_2025a` in the ingress schema pack), so this is a contract
    alignment issue rather than a real shape conflict.

Decision:
- Keep strict cross-layer checking (per S0 spec), but align the upstream
  dictionary to the canonical anchor used by 3A (`#/tz_world_2025a`).
- This preserves the “path+schema_ref equality” invariant without weakening
  validation logic, and keeps a single canonical anchor for tz_world going
  forward.

Planned change:
- Update `docs/model_spec/data-engine/layer-1/specs/contracts/1A/dataset_dictionary.layer1.1A.yaml`
  for `tz_world_2025a.schema_ref` from `#/tz_world_shp` to `#/tz_world_2025a`.
- Re-run `make segment3a-s0` after the dictionary fix.

### Entry: 2026-01-17 11:40
Applied the contract alignment change for tz_world:
- Updated `docs/model_spec/data-engine/layer-1/specs/contracts/1A/dataset_dictionary.layer1.1A.yaml`
  to set `tz_world_2025a.schema_ref` to `schemas.ingress.layer1.yaml#/tz_world_2025a`.
- This keeps cross-layer dictionary equality intact without weakening S0 checks.
Next: re-run `make segment3a-s0` to confirm the gate passes this consistency check.

### Entry: 2026-01-17 11:47
Second `make segment3a-s0` failed while validating the 2A validation bundle index:
- 2A’s `validation_bundle_index_2A` is defined as an **object with `files[]`**
  (not a `type: table` list like 1A/1B).
- The 3A `_validate_index` helper was assuming list-shaped payloads and threw
  `index.json must be a list` for 2A bundles.

Fix applied:
- `_validate_index` now supports both index shapes:
  - list/table payloads (1A/1B) validated via `validate_dataframe`
  - object payloads with `files[]` (2A) validated via Draft202012 against the
    schema anchor, with layer1 `$defs` inlined.
- Added ASCII-path validation for both shapes, mirroring 2A’s S0 guardrails.

Next: rerun `make segment3a-s0` and continue S0 to green.

### Entry: 2026-01-17 11:52
Third `make segment3a-s0` failed because 2A’s index.json does **not** list
`index.json` as a member, so the “bundle files vs index paths” comparison
flagged an extra file.

Resolution applied:
- Adjusted `_validate_index` to **ignore index.json** when it is not listed in
  the index payload (i.e., drop `index.json` from `bundle_rel` when absent).
- This preserves strict membership checking for all listed files, but respects
  the 2A bundle’s documented pattern (index.json is metadata, not a member).

Next: rerun `make segment3a-s0`.

### Entry: 2026-01-17 11:28
Observed S0 failure after the index fixes: the policy file carries
`version: v1.0.0` while the registry semver is `1.0.0`, triggering
`E3A_S0_003_POLICY_SET_INCOMPLETE` even though the semantic version is the same.

Alternatives considered:
- Change the policy file to remove the `v` prefix.
- Change the registry semver to include `v`.
- Normalize comparison to accept `v` prefixes but still reject real mismatches.

Decision:
Normalize semver comparison in the S0 policy gate by stripping a leading
`v`/`V` and whitespace before comparing. Keep placeholder detection intact, and
still fail if normalized values differ. This keeps the registry/policy inputs
unchanged while honoring the intended contract.

Planned change:
- Update `packages/engine/src/engine/layers/l1/seg_3A/s0_gate/runner.py` to use
  `_normalize_semver()` for the semver check inside the policy loop.
- Re-run `make segment3a-s0` to confirm S0 completes to green.

### Entry: 2026-01-17 11:29
Applied the semver normalization in the S0 policy gate:
- `packages/engine/src/engine/layers/l1/seg_3A/s0_gate/runner.py` now compares
  `_normalize_semver(file_version)` vs `_normalize_semver(registry_semver)`.
- Placeholder checks remain unchanged; real mismatches still hard-fail with
  `E3A_S0_003_POLICY_SET_INCOMPLETE`.

Next: rerun `make segment3a-s0` and continue to green.

### Entry: 2026-01-17 11:31
New S0 failure after semver normalization:
`ContractError: Schema section not found: schemas.3A.yaml#/policy/zone_mixture_policy_v1`.

Diagnosis:
`_schema_from_pack()` currently walks the path string verbatim. When the
dictionary provides a full schema_ref (e.g., `schemas.3A.yaml#/policy/...`),
the first path segment becomes `schemas.3A.yaml#`, which is not a key in the
loaded schema pack, so lookup fails even though the anchor exists.

Alternatives considered:
- Rewrite dictionary schema_ref values to `#/policy/...` (risk: diverges from
  other segments and expected contract style).
- Strip the filename prefix at each callsite before passing into
  `_schema_from_pack` (repetitive and error-prone).
- Teach `_schema_from_pack` to accept either full refs or anchors (preferred).

Decision:
Update `_schema_from_pack` to split on `#` and use only the anchor path when a
full ref is provided. This preserves dictionary semantics and aligns with how
`_schema_anchor_exists` already handles refs.

Planned change:
- Modify `_schema_from_pack` in
  `packages/engine/src/engine/layers/l1/seg_3A/s0_gate/runner.py` to strip any
  `schemas.*.yaml` prefix and use the fragment path when present.
- Re-run `make segment3a-s0`.

### Entry: 2026-01-17 11:31
Applied the schema-ref normalization:
- `_schema_from_pack` now strips any filename prefix and walks only the
  fragment path (supports both `schemas.3A.yaml#/policy/...` and `#/policy/...`).
Next: rerun `make segment3a-s0`.

### Entry: 2026-01-17 11:32
New S0 failure after schema-ref fix:
`AttributeError: 'str' object has no attribute 'get'` while validating
`sealed_inputs_3A` with Draft202012. The schema still contains external
`$ref` values (e.g., `schemas.layer1.yaml#/$defs/hex64`) that are not inlined
or registered, so the resolver chokes.

Alternatives considered:
- Use `validate_dataframe` (not applicable; sealed_inputs is an object schema).
- Register an explicit resolver/registry for layer1 refs.
- Inline external `$ref`s for layer1 before validation (preferred).

Decision:
Inline layer1 `$defs` into `sealed_schema` before Draft202012 validation by
calling `_inline_external_refs(sealed_schema, schema_layer1, "schemas.layer1.yaml#")`.

Planned change:
- Add `_inline_external_refs` call right after `_schema_from_pack` for
  `sealed_inputs_3A` validation in
  `packages/engine/src/engine/layers/l1/seg_3A/s0_gate/runner.py`.
- Re-run `make segment3a-s0`.

### Entry: 2026-01-17 11:33
Applied the sealed-inputs schema fix:
- Inlined layer1 `$defs` into `sealed_schema` before Draft202012 validation
  via `_inline_external_refs(sealed_schema, schema_layer1, "schemas.layer1.yaml#")`.
Next: rerun `make segment3a-s0`.

### Entry: 2026-01-17 11:34
New S0 failure after sealed-inputs fix:
`E3A_S0_007_OUTPUT_SCHEMA_INVALID` for `upstream_gates.segment_1A` because the
schema properties include a malformed key `bundle_path:{ type` (typo in the
schema line), so `bundle_path` is rejected as an unexpected property.

Decision:
Fix the typo in `docs/model_spec/data-engine/layer-1/specs/contracts/3A/schemas.3A.yaml`
so `bundle_path` is a valid property: `bundle_path: { type: string }`.

Planned change:
- Correct the malformed `bundle_path` property under the shared gate-status
  schema in `schemas.3A.yaml`.
- Re-run `make segment3a-s0`.

### Entry: 2026-01-17 11:34
Applied the schema typo fix:
- Updated `docs/model_spec/data-engine/layer-1/specs/contracts/3A/schemas.3A.yaml`
  to correct `bundle_path: { type: string }`.
Next: rerun `make segment3a-s0`.

### Entry: 2026-01-17 11:35
`make segment3a-s0` now completes green after the schema fixes.
- Run id: `2b22ab5c8c7265882ca6e50375802b26`
- manifest_fingerprint: `e8a05027991ba560d5d334258378e2a607cf0c87b1368dd05fb7ef1a04c0afed`
- parameter_hash: `56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7`

Next: confirm S0 artefacts (`s0_gate_receipt_3A`, `sealed_inputs_3A`) exist
and move to S1 planning when you’re ready.
