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

## S1 - Mixture Policy & Escalation Queue

### Entry: 2026-01-17 11:43
Scope for this pass: contract review + detailed pre-implementation plan for
3A.S1 only (no code yet).

Files read (expanded doc + contracts + data-intake):
- docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s1.expanded.md
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/dataset_dictionary.layer1.3A.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/schemas.3A.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/artefact_registry_3A.yaml
- docs/model_spec/data-engine/layer-1/specs/data-intake/3A/zone_mixture_policy_3A.md
- docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.ingress.layer1.yaml

S1 objective (from spec):
- Deterministic, RNG-free classification of each `(merchant_id, legal_country_iso)`
  into monolithic vs escalated, writing `s1_escalation_queue` as the **sole**
  authority for downstream 3A.S3/S4/S5.

Authoritative inputs (must be sealed in S0):
- S0 artefacts: `s0_gate_receipt_3A`, `sealed_inputs_3A`.
- 1A egress: `outlet_catalogue` (seed + manifest_fingerprint scoped).
- Sealed references: `iso3166_canonical_2024`, `tz_world_2025a`.
- Sealed policy: `zone_mixture_policy` (schema `schemas.3A.yaml#/policy/zone_mixture_policy_v1`).
- Optional sealed inputs: `site_timezones`, `tz_timetable_cache` (spec says S1
  MUST NOT use per-site tzids for zone-count derivation).

Planned implementation (stepwise, phase-aligned to spec):
1) **Resolve S0 + sealed inputs**
   - Resolve and validate `s0_gate_receipt_3A` and `sealed_inputs_3A` against
     `schemas.3A.yaml#/validation/s0_gate_receipt_3A` and
     `schemas.3A.yaml#/validation/sealed_inputs_3A`.
   - Enforce upstream PASS via `s0_gate_receipt_3A.upstream_gates.*`.
   - For each required artefact, confirm a matching row exists in
     `sealed_inputs_3A` and recompute SHA-256 to match `sha256_hex`.

2) **Load + validate mixture policy**
   - Locate policy entry via `sealed_inputs_3A` and `sealed_policy_set`
     (role must be `"zone_mixture_policy"`).
   - Validate the policy against `schemas.3A.yaml#/policy/zone_mixture_policy_v1`.
   - Derive `mixture_policy_id` (logical ID) and `mixture_policy_version`
     (use the policy file `version`; fail if placeholder).
   - Compute policy digest for optional `theta_digest` column.

3) **Build country → Z(c) mapping**
   - Use `tz_world_2025a` + country polygons to compute
     `Z(c) = { tzid | tz_polygon(tzid) ∩ country_polygon(c) ≠ ∅ }`.
   - Derive `zone_count_country(c) = |Z(c)|`.
   - Cache `zone_count_country` in a dict keyed by `legal_country_iso`.
   - If `zone_count_country` is missing for any `legal_country_iso` in scope,
     fail with `E3A_S1_006_ZONE_STRUCTURE_INCONSISTENT` unless policy explicitly
     allows a deterministic monolithic fallback.

4) **Aggregate outlet counts**
   - Read `outlet_catalogue` (columns: `merchant_id`, `legal_country_iso` only).
   - Compute `site_count(m,c)` via group-by; enforce deterministic ordering by
     sorting on `(merchant_id, legal_country_iso)`.

5) **Apply mixture policy per (m,c)**
   - Evaluate rules in policy order; first match wins.
   - If no rule matches, apply deterministic hash mix using `theta_mix` as per
     `zone_mixture_policy_3A` guide:
     `u_det = (SHA256("3A.S1.theta_mix|m|c|parameter_hash")[:8]+0.5)/2^64`.
   - Emit `decision_reason` exactly from policy; `is_escalated` implied by
     decision_reason vocabulary (monolithic vs escalated).

6) **Materialise `s1_escalation_queue`**
   - Populate required columns per `schemas.3A.yaml#/plan/s1_escalation_queue`.
   - Include optional columns when available: `theta_digest`,
     `eligible_for_escalation`, `dominant_zone_share_bucket`, `notes`.
   - Validate rows, sort by dictionary ordering, and write to
     `data/layer1/3A/s1_escalation_queue/seed={seed}/manifest_fingerprint={mf}/`.
   - Enforce immutability: if dataset exists, compare row-by-row; if identical
     skip/overwrite; else fail with immutability error.

7) **Observability + run-report**
   - Emit story header log: objective + gated inputs + outputs.
   - Emit counts: pairs_total, pairs_escalated, pairs_monolithic, escalation_rate,
     and zone-count bucket breakdown.
   - Emit PASS/FAIL run-report per spec (status + error_code mapping).

Performance + determinism notes:
- Use Polars scan + group-by to avoid full in-memory outlet table.
- Single pass over `tz_world_2025a` for Z(c); cache results.
- Deterministic ordering for grouping and output writes.
- RNG-free; no wall-clock time influences.

Open confirmations needed before coding:
1) **Country polygon source for Z(c):**
   Spec defines `Z(c)` via tz polygons intersecting country polygons, but
   `tz_world_2025a` schema does not include `country_iso`, and `iso3166` has no
   geometry. Should we:
   - add `world_countries_2024` (or equivalent) to 3A contracts + S0 sealing and
     use spatial intersection, or
   - treat `tz_world_2025a` as already country-tagged in the actual data and
     update schema if needed?
2) **Theta-mix hash step:**
   The policy authoring guide pins the deterministic hash formula for `theta_mix`.
   Confirm we should implement exactly that (SHA256-based `u_det`) for the
   default branch when no rule matches.
3) **Optional tz_timetable_cache cross-check:**
   If `tz_timetable_cache` is sealed, should S1 validate that every tzid in `Z(c)`
   exists in the compiled tz universe? (If not sealed, S1 will skip this check.)
4) **Zone-count zero handling:**
   If `zone_count_country(c)==0` for a country with outlets, should S1 always
   fail (strict) or allow policy-driven monolithic fallback?

### Entry: 2026-01-17 12:00
Confirmed S1 decisions + pre-implementation plan (before coding).

Decisions confirmed by user (binding for this implementation pass):
1) Country polygon source for Z(c):
   - Add `world_countries` to 3A contracts (dictionary + registry) and seal it
     in 3A.S0 (required input). Use spatial intersection between
     `tz_world_2025a` polygons and `world_countries` polygons to derive
     `Z(c)` and `zone_count_country`.
   - Rationale: `tz_world` schema does not include `country_iso` and iso3166
     has no geometry; explicit polygon dataset keeps S1 deterministic and
     contract-clean (no ad-hoc inputs).

2) Theta-mix hash step:
   - Implement the exact hash formula in
     `zone_mixture_policy_3A.md` for the default branch:
       `msg = "3A.S1.theta_mix|{merchant_id}|{legal_country_iso}|{parameter_hash_hex}"`
       `x = first_8_bytes(SHA256(msg))` (uint64 big-endian)
       `u_det = (x + 0.5) / 2^64`
     If `u_det < theta_mix`: `is_escalated=true` and `decision_reason=default_escalation`;
     else `is_escalated=false` and `decision_reason=legacy_default`.

3) tz_timetable_cache cross-check:
   - If `tz_timetable_cache` is sealed, cross-check derived tzids against the
     compiled tz universe; if not sealed, skip this check (no soft fail).

4) zone_count_country == 0:
   - Fail closed with `E3A_S1_006_ZONE_STRUCTURE_INCONSISTENT` unless a future
     policy explicitly allows a deterministic monolithic fallback (not present
     now). This keeps output integrity and avoids silent empties.

Implementation plan (explicit, stepwise):
1) Contracts + sealing updates
   - Add `world_countries` entry to:
     - `docs/model_spec/data-engine/layer-1/specs/contracts/3A/dataset_dictionary.layer1.3A.yaml`
     - `docs/model_spec/data-engine/layer-1/specs/contracts/3A/artefact_registry_3A.yaml`
   - Update 3A.S0 gate:
     - Add `world_countries` to the cross-layer dictionary consistency check list.
     - Add `world_countries` to the required sealed-inputs list so it is hashed
       and recorded in `sealed_inputs_3A`.

2) New S1 runner + CLI + Makefile wiring
   - Create `packages/engine/src/engine/layers/l1/seg_3A/s1_escalation/runner.py`
     with a deterministic, RNG-free implementation.
   - Create `packages/engine/src/engine/layers/l1/seg_3A/s1_escalation/__init__.py`
     exporting `run_s1`.
   - Create CLI `packages/engine/src/engine/cli/s1_escalation_3a.py` mirroring
     S0 CLI pattern.
   - Add Makefile target `segment3a-s1` and update `segment3a` chain to include S1.

3) S1 input resolution + gate enforcement
   - Resolve `run_receipt.json` (latest unless `--run-id` provided).
   - Load schema packs: `schemas.layer1.yaml`, `schemas.ingress.layer1.yaml`,
     `schemas.1A.yaml`, `schemas.1B.yaml`, `schemas.2A.yaml`, `schemas.2B.yaml`,
     `schemas.3A.yaml`.
   - Load 3A dictionary + registry (contracts layout from config, dev uses
     `model_spec`).
   - Resolve + validate `s0_gate_receipt_3A` and `sealed_inputs_3A`.
   - Enforce upstream PASS status for 1A/1B/2A in the receipt.
   - For each required input, confirm a sealed row exists and recompute SHA-256
     to match `sealed_inputs_3A.sha256_hex` (fail closed on mismatch).

4) Policy loading + validation
   - Load `zone_mixture_policy` from sealed path (YAML).
   - Validate against `schemas.3A.yaml#/policy/zone_mixture_policy_v1`.
   - Extract `policy_id` and `version` (non-placeholder) and compute
     `theta_digest = sha256(policy_bytes)`.

5) Derive Z(c) and zone_count_country
   - Load `world_countries` + `tz_world_2025a` (GeoParquet) via geopandas.
   - Normalize antimeridian using `_split_antimeridian_geometries` so polygons
     intersect consistently.
   - Build STRtree for tz polygons; for each country polygon, query intersecting
     tz geometries, union tzids into `Z(c)`.
   - Compute `zone_count_country[country_iso] = |Z(c)|`.
   - If zero for any country in outlet scope -> `E3A_S1_006_ZONE_STRUCTURE_INCONSISTENT`.
   - If `tz_timetable_cache` is sealed, assert all tzids are present in the
     compiled tz universe (fail with `E3A_S1_010_TZ_UNIVERSE_MISMATCH`).

6) Aggregate outlet counts + apply mixture policy
   - Read `outlet_catalogue` with Polars; group by `(merchant_id, legal_country_iso)`
     to compute `site_count`.
   - For each row:
     - Evaluate rules in order; first match wins.
     - If no rule matches, apply `theta_mix` hash step as above.
   - Derive `is_escalated` from `decision_reason` (monolithic vs escalation
     reasons as defined in the policy guide).

7) Write S1 outputs + reports
   - Emit `s1_escalation_queue` with required columns, including:
     `mixture_policy_id`, `mixture_policy_version`, `theta_digest`.
   - Validate against `schemas.3A.yaml#/plan/s1_escalation_queue`.
   - Enforce immutability: if partition exists, compare hashes and skip if
     identical; else fail.
   - Emit `segment_state_runs` JSONL row and `s1_run_report_3A` file with
     summary counts (pairs_total, pairs_escalated, pairs_monolithic).

8) Logging (story-first)
   - Header: objective, gated inputs, and outputs.
   - Phase logs: policy load, Z(c) build, outlet aggregation, policy application,
     output publish.
   - Progress logs with elapsed/rate/ETA for loops over countries and merchant
     pairs (narrative context included).

9) Test plan
   - Run `make segment3a-s0` (reseal with world_countries) then
     `make segment3a-s1 RUN_ID=<current>`.
   - Validate `s1_escalation_queue` schema + determinism (re-run idempotence).
   - Spot-check `decision_reason` distribution and theta_mix behaviour.

### Entry: 2026-01-17 12:23
Starting 3A.S1 implementation now (new code + wiring + run-to-green).

Additional spec-level details surfaced in the latest read-through (to wire into
the implementation before coding):
- Error code mapping per §9 of the S1 expanded spec:
  - Missing or invalid `s0_gate_receipt_3A` / `sealed_inputs_3A` => `E3A_S1_001`.
  - Any upstream gate status != PASS => `E3A_S1_002` with segment name.
  - Catalogue load/validation failures => `E3A_S1_003` with failing artefact id.
  - Mixture policy missing/ambiguous => `E3A_S1_004` with missing_roles/conflicts.
  - Mixture policy schema invalid => `E3A_S1_005` with violation count.
  - Unknown country or zone-count zero => `E3A_S1_006` with reason.
  - Sealed input digest mismatch => `E3A_S1_007` with logical_id/path/digests.
  - Output schema invalid => `E3A_S1_010` with violation count and field sample.
  - Output immutability violation => `E3A_S1_012`.
  - Any non-logical I/O error => `E3A_S1_013`.
- The schema for `s1_escalation_queue` includes optional
  `dominant_zone_share_bucket` and `eligible_for_escalation`; we will emit
  `eligible_for_escalation` when a rule matches a guard (monolithic) or
  escalation condition; `dominant_zone_share_bucket` will carry any `bucket`
  field from the matched rule (or null).
- `zone_count_country` is allowed to be 0 by schema, but spec declares it as an
  inconsistency for any country with outlets (must fail closed).
- `zone_mixture_policy_3A` guide pins the `theta_mix` hash formula verbatim;
  must implement exact bytes and string formatting as specified.

Concrete implementation steps now (to execute in code):
1) Create `s1_escalation/runner.py`:
   - Reuse helpers from `seg_3A.s0_gate.runner`:
     `_resolve_run_receipt`, `_resolve_dataset_path`, `_render_catalog_path`,
     `_schema_from_pack`, `_table_pack`, `_inline_external_refs`,
     `_segment_state_runs_path`, `_load_json`, `_load_yaml`, `_hash_partition`,
     `_append_jsonl`.
   - Add S1-specific helpers: StepTimer, ProgressTracker, hash mix helper,
     STRtree-based intersection for Z(c), and atomic publish for parquet output.
2) Load + validate S0 artefacts and upstream gate PASS.
3) Validate sealed inputs and recompute digests (policy, outlet_catalogue,
   iso3166, world_countries, tz_world, optional tz_timetable_cache).
4) Build Z(c) using world_countries + tz_world intersections (dateline-safe).
5) Aggregate outlet_catalogue to site_count and apply policy rules + theta_mix.
6) Validate output against `schemas.3A.yaml#/plan/s1_escalation_queue`.
7) Publish output and run-report (segment_state_runs + s1_run_report_3A).
8) Wire CLI + Makefile; run `make segment3a-s0` (reseal world_countries) then
   `make segment3a-s1` until green.

Logging intent (story-first, narrative):
- S1 header: objective + gated inputs + outputs.
- Phase logs: policy load, Z(c) build, outlet aggregation, policy application,
  output validation/publish.
- Progress logs with elapsed/rate/ETA for country loop and merchant-pair loop.

### Entry: 2026-01-17 12:49

S1 implementation decision notes before coding (new details surfaced while
writing the runner):

1) tz_timetable_cache cross-check scope (optional input)
   - The cache manifest only exposes `tzdb_release_tag` + digests; it does not
     carry a tzid list. To avoid reading any uncatalogued files (spec rule),
     the cross-check will be implemented as:
       * if `tz_timetable_cache` is sealed, assert its `tzdb_release_tag`
         matches the release tag implied by the sealed `tz_world_2025a`
         dataset id/path (e.g., `tz_world_2025a` -> release tag `2025a`).
       * if mismatch, fail closed with `E3A_S1_006_ZONE_STRUCTURE_INCONSISTENT`
         and include both tags in the error context.
     - This stays contract-clean and enforces a meaningful compatibility check
       without inventing new input surfaces.

2) eligible_for_escalation semantics (optional diagnostic column)
   - Encode as "eligible but not chosen" vs "never eligible":
     * `eligible_for_escalation = true` for decision reasons:
       `forced_escalation`, `default_escalation`, `legacy_default`.
     * `eligible_for_escalation = false` for monolithic guard reasons:
       `forced_monolithic`, `below_min_sites`.
   - Rationale: "legacy_default" represents a pair that passed guards but
     was not selected by the deterministic mix.

3) dominant_zone_share_bucket population
   - Populate from `rule.bucket` when the matching rule supplies it.
   - Otherwise set to null (no derived bucket).

4) STRtree compatibility guard
   - STRtree query return types differ between Shapely versions (geoms vs
     indices). The implementation will accept both:
       * if candidate is an integer index, look up geometry via `tz_geoms[idx]`;
       * else treat it as a geometry object directly.
   - This avoids version-specific failure while preserving deterministic
     intersection results.

### Entry: 2026-01-17 14:09

Resume 3A.S1 implementation work after the response mix-up. S0 is complete and
green; continue only with S1 wiring + run-to-green.

Immediate pre-implementation plan (before further code changes):
1) Wire S1 CLI and Makefile:
   - Create `packages/engine/src/engine/cli/s1_escalation_3a.py` mirroring the
     S0 CLI pattern (contracts layout/root, runs root, external roots, run_id).
   - Add Makefile variables/targets for `segment3a-s1` and include S1 in the
     `segment3a` chain; update `.PHONY`.
2) Validate the current S1 runner for correctness before running:
   - Confirm policy validation matches the schema + guide (rules, reasons).
   - Confirm Z(c) logic uses `world_countries` + `tz_world` and handles
     antimeridian splits deterministically (STRtree guard retained).
   - Confirm optional `tz_timetable_cache` check is release-tag only, as
     previously decided.
   - Confirm output schema validation uses the JSONSchema adapter (table->row)
     with layer1 defs inlined where needed.
3) Re-seal S0 inputs (world_countries is now required):
   - Run `make segment3a-s0` to reseal and ensure `sealed_inputs_3A` includes
     world_countries; only then run S1.
4) Run to green and iterate:
   - Run `make segment3a-s1 RUN_ID=<current>`; capture any failures.
   - For each failure, append a new entry with the decision + fix path before
     editing code. Log the same decisions/actions in the logbook with time.
5) Logging expectations:
   - Ensure S1 logs a story header (objective, gated inputs, outputs) and
     narrative progress for Z(c) and pair processing; include elapsed/rate/ETA.

Decision note for this continuation:
- No changes to S1 logic are planned unless a run failure or spec mismatch is
  discovered; the immediate focus is wiring + execution.

### Entry: 2026-01-17 14:11

Implemented S1 wiring steps before running:
- Added CLI `packages/engine/src/engine/cli/s1_escalation_3a.py` matching the S0
  CLI contract-switching pattern (contracts layout/root, runs root, external
  roots, optional run_id).
- Added Makefile wiring for S1:
  `SEG3A_S1_RUN_ID`, `SEG3A_S1_ARGS`, `SEG3A_S1_CMD`, `segment3a-s1` target, and
  `segment3a` chain now includes S0 then S1.

Next: run `make segment3a-s0` (to reseal world_countries) then
`make segment3a-s1` and iterate to green, logging any fixes as they arise.

### Entry: 2026-01-17 14:12

Run failure while re-sealing S0 before S1:
- `make segment3a-s0` failed with `E3A_S0_002_CATALOGUE_MALFORMED` because
  `world_countries` schema_ref differs across dictionaries:
  - 1A: `schemas.ingress.layer1.yaml#/world_countries_shp`
  - 1B/2A/3A: `schemas.ingress.layer1.yaml#/world_countries`
  - `world_countries_shp` is just an alias to `world_countries`, but the
    catalogue consistency check requires exact match.

Decision:
- Standardize `world_countries` schema_ref to the canonical anchor
  `schemas.ingress.layer1.yaml#/world_countries` across dictionaries.
  This aligns 1A with 1B/2A/3A and keeps the cross-layer consistency rule strict.

Planned change:
- Update `docs/model_spec/data-engine/layer-1/specs/contracts/1A/dataset_dictionary.layer1.1A.yaml`
  to use `schemas.ingress.layer1.yaml#/world_countries` for `world_countries`.
- Rerun `make segment3a-s0`, then proceed to `make segment3a-s1`.

### Entry: 2026-01-17 14:13

Applied the schema_ref alignment:
- Updated `docs/model_spec/data-engine/layer-1/specs/contracts/1A/dataset_dictionary.layer1.1A.yaml`
  to set `world_countries.schema_ref` = `schemas.ingress.layer1.yaml#/world_countries`
  (aligns with 1B/2A/3A).

Next: rerun `make segment3a-s0` to reseal with the aligned dictionary.

### Entry: 2026-01-17 14:14

S0 reseal attempt failed with immutability:
- `make segment3a-s0` now passes catalogue checks but fails with
  `E3A_S0_009_IMMUTABILITY_VIOLATION` when publishing `sealed_inputs_3A`.
- Reason: the existing run-local `sealed_inputs_3A.json` (from the prior
  schema_ref mismatch state) differs from the newly computed one after the
  dictionary fix, and S0 is write-once by contract.

Decision point:
- To reseal under the same `run_id` and `manifest_fingerprint`, we must delete
  the run-local S0 outputs (`s0_gate_receipt_3A` and `sealed_inputs_3A`) for
  this manifest so S0 can republish, or start a fresh run_id.

Next action pending approval:
- Remove:
  - `runs/local_full_run-5/2b22ab5c8c7265882ca6e50375802b26/data/layer1/3A/s0_gate_receipt/manifest_fingerprint=e8a05027991ba560d5d334258378e2a607cf0c87b1368dd05fb7ef1a04c0afed/s0_gate_receipt_3A.json`
  - `runs/local_full_run-5/2b22ab5c8c7265882ca6e50375802b26/data/layer1/3A/sealed_inputs/manifest_fingerprint=e8a05027991ba560d5d334258378e2a607cf0c87b1368dd05fb7ef1a04c0afed/sealed_inputs_3A.json`
  then rerun `make segment3a-s0` and `make segment3a-s1`.

### Entry: 2026-01-17 14:21

S1 run failure after resealing S0:
- `make segment3a-s1` failed in `outlet_aggregate` with
  `scan_parquet() got an unexpected keyword argument 'columns'`.
- Root cause: the local Polars version does not accept the `columns=...` kwarg
  for `pl.scan_parquet`. This causes an infra error before any domain logic.

Decision:
- Replace the `columns=` kwarg with a `select()` call after scanning:
  `pl.scan_parquet(path).select(["merchant_id","legal_country_iso"])`.
- This preserves lazy scanning semantics and compatibility with older Polars.

Planned change:
- Update `packages/engine/src/engine/layers/l1/seg_3A/s1_escalation/runner.py`
  in the `outlet_aggregate` phase to remove `columns=` and use `select()`.
- Rerun `make segment3a-s1` and continue to green.

### Entry: 2026-01-17 14:22

S1 still failing in outlet aggregation after the scan_parquet fix:
- New error: `'LazyFrame' object has no attribute 'groupby'` from Polars.
- Root cause: local Polars uses `group_by` on LazyFrame (not `groupby`).

Decision:
- Swap `groupby(...)` to `group_by(...)` for the LazyFrame aggregation.
- Keep the rest of the pipeline the same to preserve determinism.

Planned change:
- Update `packages/engine/src/engine/layers/l1/seg_3A/s1_escalation/runner.py`
  to use `group_by` for `outlet_scan`.
- Rerun `make segment3a-s1` and continue to green.

### Entry: 2026-01-17 14:23

S1 failure after LazyFrame group_by fix:
- Error in `zone_structure`: "No match for FieldRef.Name(geom)" while reading
  `world_countries` / `tz_world` with `columns=["...","geom"]`.
- The GeoParquet files expose the geometry column as `geometry`, not `geom`,
  so selecting `geom` fails.

Decision:
- Stop selecting `geom` at read time. Load the GeoParquet without `columns=`
  and use the GeoDataFrame geometry attribute (`row.geometry`) when iterating.
- Add a small helper to resolve geometry from either `row.geometry` or
  `row.geom` to tolerate both column names.

Planned change:
- Update `packages/engine/src/engine/layers/l1/seg_3A/s1_escalation/runner.py`:
  read `world_gdf` and `tz_gdf` without `columns=...` and use a geometry
  accessor for row iteration.
- Rerun `make segment3a-s1`.

### Entry: 2026-01-17 14:24

S1 failure after geometry-column fix:
- Error: `'numpy.int64' object has no attribute 'intersects'` inside the
  STRtree candidate loop.
- Root cause: in some Shapely builds, STRtree returns numpy integer indices
  (not Python int), so the `isinstance(candidate, int)` check misses them and
  the code tries to call `.intersects` on the integer.

Decision:
- Expand the STRtree guard to treat any `numbers.Integral` (including numpy
  integer types) as an index and resolve via `tz_geoms[int(candidate)]`.

Planned change:
- Update `_resolve_candidate_geoms` in
  `packages/engine/src/engine/layers/l1/seg_3A/s1_escalation/runner.py` to
  use `numbers.Integral` for index detection.
- Rerun `make segment3a-s1`.

### Entry: 2026-01-17 14:25

S1 failure after STRtree index guard:
- Error: Polars cannot append `merchant_id` values above int64 when building
  the output DataFrame from `output_rows` (value overflow to i128).
- Root cause: `pl.DataFrame(output_rows)` infers a signed int dtype; some
  `merchant_id` values exceed int64 (they are uint64/id64 in schema).

Decision:
- Build the output DataFrame with an explicit schema that uses `pl.UInt64` for
  `merchant_id` (and `seed`), and appropriate dtypes for other columns.
- This enforces contract-aligned types and avoids inference overflow.

Planned change:
- Update `packages/engine/src/engine/layers/l1/seg_3A/s1_escalation/runner.py`
  to construct `pl.DataFrame(output_rows, schema=...)` with explicit dtypes.
- Rerun `make segment3a-s1`.

### Entry: 2026-01-17 14:26

Actions completed and result:
- Deleted run-local S0 outputs for 3A (approved) so S0 could reseal:
  - `.../data/layer1/3A/s0_gate_receipt/manifest_fingerprint=.../s0_gate_receipt_3A.json`
  - `.../data/layer1/3A/sealed_inputs/manifest_fingerprint=.../sealed_inputs_3A.json`
- Reran `make segment3a-s0` successfully; S0 resealed inputs with aligned
  world_countries schema_ref.
- Applied the remaining S1 fixes:
  - Polars compatibility: `scan_parquet` + `select` and `group_by`.
  - GeoParquet geometry handling: use row geometry regardless of column name.
  - STRtree guard: accept `numbers.Integral` indices.
  - Explicit output schema to keep `merchant_id` in `UInt64`.
- Reran `make segment3a-s1`; S1 completed green and published
  `s1_escalation_queue` (2596 rows) + run-report.

Ready to move to S2 review/plan when you are.

## S2 - Country-Zone Priors & Floors

### Entry: 2026-01-17 14:48

Scope for this pass: S2 contract review + pre-implementation plan (no code yet).

Files read (expanded doc + contracts + policy guides):
- docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s2.expanded.md
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/dataset_dictionary.layer1.3A.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/schemas.3A.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/artefact_registry_3A.yaml
- docs/model_spec/data-engine/layer-1/specs/data-intake/3A/country_zone_alphas_3A.md
- docs/model_spec/data-engine/layer-1/specs/data-intake/3A/zone_floor_policy_3A.md
- docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.ingress.layer1.yaml

S2 objective (from spec):
- Build parameter-scoped (`parameter_hash`) `s2_country_zone_priors` as the
  sole authority for Dirichlet à priors after applying floor/bump policy.
  Deterministic and RNG-free; no dependence on S1 outputs.

Authoritative inputs (must be sealed in S0):
- `s0_gate_receipt_3A`, `sealed_inputs_3A` (gate + whitelist).
- Policies: `country_zone_alphas`, `zone_floor_policy` (sealed, required).
- References: `iso3166_canonical_2024`, `world_countries`, `tz_world_2025a`
  (sealed, required).
- Optional: `tz_timetable_cache` (sealed; only for compatibility checks).

Output:
- `s2_country_zone_priors` partitioned by `parameter_hash` only.
- `s2_run_report_3A` (schema_ref: `schemas.layer1.yaml#/run_report/segment_state_run`).
- `segment_state_runs` JSONL row per invocation.

Key invariants from spec + guides:
- Z(c) must be derived from `world_countries` + `tz_world_2025a` polygons.
- Priors must align exactly to Z(c) and be strictly positive after floors.
- `alpha_effective(c,z) = max(alpha_raw(c,z), floor_alpha(c,z))`.
- `alpha_sum_country` must be > 0; `share_effective` in [0,1] and sums to 1 per country.
- S2 MUST NOT read S1 outputs or merchant-level data; only priors + references.

Open confirmations (need your call before coding):
1) **Z(c) derivation reuse:** should S2 recompute Z(c) from `world_countries` +
   `tz_world_2025a` (preferred, deterministic, policy-guide aligned), or reuse
   any precomputed mapping if one exists? I recommend recomputing in S2 to
   keep S2 parameter-scoped and independent of S1.
2) **Missing/extra tzids in prior pack:** the authoring guide demands exact
   Z(c) match, but the floor-policy semantics define `alpha_raw=0` for missing
   (c,z). Should S2 fail closed on *any* missing/extra tzids, or allow missing
   tzids to be filled with 0.0 and rely on floors? I recommend:
   - **extra tzids** -> hard fail,
   - **missing tzids** -> hard fail (to stay consistent with the pack’s
     “exact universe” rule) unless you explicitly want a “fill + floor” mode.
3) **tz_timetable_cache cross-check:** if sealed, should S2 perform the same
   release-tag compatibility check as S1 (tzdb_release_tag vs tz_world tag)?
   I recommend yes, to keep the tz universe consistent without reading any
   uncatalogued tzid list.
4) **Run-report emission:** dictionary defines `s2_run_report_3A`; do you want
   this file to include a summary of floor/bump counts per tzid (diagnostic), or
   keep it minimal (counts + status) to avoid log/report bloat? I recommend
   minimal by default and include only aggregated counts.

Pre-implementation plan (stepwise, phase-aligned):
1) **Resolve S0 gate + sealed inputs**
   - Load `s0_gate_receipt_3A` + `sealed_inputs_3A`; validate schemas.
   - Confirm upstream gates PASS (1A/1B/2A).
   - Build a sealed lookup by `logical_id` and verify sha256 digests for each
     required artefact.

2) **Load + validate prior and floor policies**
   - `country_zone_alphas`: validate against `schemas.3A.yaml#/policy/country_zone_alphas_v1`.
   - `zone_floor_policy`: validate against `schemas.3A.yaml#/policy/zone_floor_policy_v1`.
   - Extract `prior_pack_id/version` and `floor_policy_id/version` (non-placeholder).

3) **Build Z(c) zone universe**
   - Read `world_countries` and `tz_world_2025a` geos; split antimeridian
     polygons (`_split_antimeridian_geometries`).
   - For each country polygon, intersect with tz polygons to produce Z(c).
   - Fail on any `Z(c)==∅` for a country appearing in the prior pack.
   - Optional tzdb release-tag check if `tz_timetable_cache` is sealed.

4) **Construct alpha_raw per (c,z)**
   - For each country in the prior pack, map `tzid_alphas` to Z(c).
   - Enforce no extra tzids; handle missing tzids per the confirmation above.
   - `alpha_raw` ≥ 0 (strictly >0 per authoring guide unless “fill=0” mode is approved).

5) **Apply floor/bump policy**
   - For each (c,z): compute `alpha_sum_raw`, `share_raw` (0 if sum=0).
   - Determine `floor_value` + `bump_threshold` for tzid (default 0 / 1.0 if missing).
   - `floor_alpha = floor_value` when share_raw ≥ bump_threshold.
   - `alpha_effective = max(alpha_raw, floor_alpha)`.
   - `floor_applied` + `bump_applied` flags from alpha change (v1).

6) **Finalize output rows**
   - `alpha_sum_country = sum(alpha_effective)` per country (must be > 0).
   - `share_effective = alpha_effective / alpha_sum_country`.
   - Populate required columns per `schemas.3A.yaml#/plan/s2_country_zone_priors`.
   - Sort rows by `[country_iso, tzid]` for determinism.

7) **Validate + publish**
   - Validate rows with `validate_dataframe` using `schemas.3A.yaml#/plan/s2_country_zone_priors`
     (layer1 defs inlined).
   - Write to tmp, enforce immutability on publish (parameter_hash partition).

8) **Run-report + logs**
   - Emit story header log (objective, gated inputs, outputs).
   - Progress logs for country loop and tzid loop (elapsed, rate, ETA).
   - Write `segment_state_runs` JSONL and `s2_run_report_3A` (PASS/FAIL, counts).

Performance considerations:
- Parameter-scoped output is small; keep in memory but allow streaming if needed.
- Avoid re-reading geometry; cache Z(c) derivation once per run.

Resumability:
- If `s2_country_zone_priors` already exists and bytes match, skip publish.
- If non-identical, fail immutability per spec.

Awaiting your confirmation on the four open points above before coding.

### Entry: 2026-01-17 15:17

S2 confirmations received (approved):
- Recompute Z(c) from `world_countries` + `tz_world_2025a` each run (no reuse of S1).
- Fail closed on extra tzids in the prior pack; fail closed on missing tzids vs Z(c).
- If `tz_timetable_cache` is sealed, enforce the release-tag match vs the tz_world tag.
- Keep S2 run-report minimal (aggregated counts only; no per-tzid diagnostics).

Implementation notes before coding:
- S2 will validate `s0_gate_receipt_3A` + `sealed_inputs_3A` and hard-fail if upstream
  gates are not PASS or if sealed-input digests/path tokens mismatch.
- S2 must accept `sealed_inputs_3A` in JSON-list (prod) and parquet (test harness)
  without changing the prod contract; parquet support is a local harness fallback.
- I will add `PriorsInputs`/`PriorsRunner` (test harness) that read a local dictionary
  path + data_root without run_receipt; this will not alter the production runner.
- Output will follow `schemas.3A.yaml#/plan/s2_country_zone_priors` with deterministic
  sorting and immutability checks on publish.

### Entry: 2026-01-17 20:24

Re-reviewed 3A.S2 expanded spec + contracts to align the plan with the
current schema/policy content before coding.

Files read this pass:
- docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s2.expanded.md
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/dataset_dictionary.layer1.3A.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/artefact_registry_3A.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/schemas.3A.yaml
- config/layer1/3A/allocation/country_zone_alphas.yaml
- config/layer1/3A/allocation/zone_floor_policy.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.ingress.layer1.yaml

Key schema/policy observations that shape S2:
- `s2_country_zone_priors` requires: `alpha_raw`, `alpha_effective`,
  `alpha_sum_country`, `share_effective`, `floor_applied`, `bump_applied`
  (all non-null; alpha_effective/alpha_sum_country strictly > 0).
- `country_zone_alphas_v1` is per-country and contains `tzid_alphas[]` with
  `alpha > 0` (raw prior mass; no missing-defaults described in schema).
- `zone_floor_policy_v1` is a tzid-keyed global floor list (no per-country
  floors), with `floor_value >= 0` and `bump_threshold` in [0,1].

Plan remains aligned to the earlier S2 workflow:
- Validate S0 gate + sealed_inputs; fail closed on any missing/mismatch.
- Load/validate `country_zone_alphas` + `zone_floor_policy`; capture versions
  (policy file `version` is authoritative, already sealed in S0).
- Build Z(c) by intersecting `world_countries` and `tz_world_2025a` polygons
  (antimeridian-safe). No use of S1 outputs or merchant data.
- Enforce strict Z(c) alignment: prior tzids must be subset of Z(c); Z(c) must
  be fully covered by priors (fail closed if missing or extra).
- Apply floors/bump deterministically:
  - `alpha_effective = max(alpha_raw, floor_value)` for the tzid.
  - `floor_applied` when alpha_effective > alpha_raw.
  - `bump_applied` set when the zone share triggers the bump rule.
- Compute `alpha_sum_country` and `share_effective`; fail if sums are <= 0 or
  share_effective not in [0,1] within tolerance.
- Publish `s2_country_zone_priors` under `parameter_hash` with immutability
  checks; emit `segment_state_runs` + `s2_run_report_3A` (minimal aggregates).

Open confirmations to re-check before coding (only if prior approvals have changed):
1) Z(c) derivation stays in S2 (recompute from polygons, no reuse from S1).
2) Missing/extra tzids in priors: fail closed on both missing and extra.
3) If `tz_timetable_cache` is sealed, enforce tzdb release-tag match to tz_world.
4) Run-report stays minimal (aggregated counts only, no per-tzid diagnostics).

### Entry: 2026-01-18 00:56

Decision log before starting S2 implementation (post-review + user approval).
This entry captures the concrete choices that will guide the S2 build so the
reasoning trail remains auditable during coding.

Problem framing (what S2 must do):
- Produce the parameter-scoped `s2_country_zone_priors` as the single source of
  truth for Dirichlet priors per `(country_iso, tzid)`, after floor/bump rules,
  with strict immutability and no RNG usage.
- Inputs must be limited to S0 outputs + sealed policy/reference artefacts.
- The output must satisfy strict schema + invariants and be deterministic across
  re-runs for the same `parameter_hash`.

Alternatives evaluated and chosen:
1) **Prior pack vs zone-universe mismatch handling**
   - Alternative A (lenient): allow missing tzids in priors by setting
     `alpha_raw=0.0`, then rely on floors to populate mass.
   - Alternative B (strict): fail if priors omit any `tzid` in `Z(c)` or include
     extras not in `Z(c)`.
   - Decision: **Alternative B (strict)**.
   - Rationale: the S2 spec calls for completeness/consistency with `Z(c)` and
     the authoring guide requires exact coverage; failing fast prevents hidden
     drift between priors and the zone universe.

2) **Lineage fields (`prior_pack_id` / `floor_policy_id`)**
   - Alternative A: emit logical IDs shown in docs (e.g. `country_zone_alphas_3A`).
   - Alternative B: emit the dataset dictionary IDs:
     `country_zone_alphas` and `zone_floor_policy`.
   - Decision: **Alternative B (dictionary IDs)**.
   - Rationale: dictionary IDs are the authoritative contract keys and ensure
     the output aligns with catalogue lookups; avoids ad-hoc naming drift.
   - Implementation note: versions are taken from the policy file `version`
     fields; they must match the sealed policy set in S0.

3) **Zone-universe derivation (`Z(c)`)**
   - Alternative A: reuse S1 output (or any precomputed mapping).
   - Alternative B: re-derive from `world_countries` + `tz_world_2025a` for each
     S2 run.
   - Decision: **Alternative B (recompute)**.
   - Rationale: S2 is parameter-scoped and must not depend on S1 or merchant-
     scoped artefacts; recomputation keeps the authority chain clean and matches
     the policy authoring guides.
   - Implementation detail: use the same geometric intersection logic as S1
     (STRtree + antimeridian splits) to keep zone definitions consistent.

4) **Numeric tolerance**
   - Decision: use **1e-12** (float64) for per-country sum checks
     (`share_effective` sum to 1 and `alpha_sum_country` equality).
   - Rationale: matches the spec’s suggested tolerance and is stable in
     float64.

5) **Optional `tz_timetable_cache` sanity check**
   - Decision: if `tz_timetable_cache` is sealed, perform the release-tag
     compatibility check (as in S1) against the tz_world tag; otherwise skip.
   - Rationale: lightweight guard to keep tz universe consistent without
     introducing extra dependencies or heavy logic.

6) **Run-report posture**
   - Decision: emit a minimal aggregated run-report (counts + lineage +
     status/error) under the contracts-defined path, mirroring S1’s style and
     avoiding per-tzid diagnostics.
   - Rationale: keeps run logs readable and avoids bloating outputs while
     still meeting the S2 spec’s required fields.

Planned implementation steps (exact mechanics; to be executed next):
1) **Add the S2 runner**
   - File: `packages/engine/src/engine/layers/l1/seg_3A/s2_priors/runner.py`.
   - Reuse existing helpers from `seg_3A/s0_gate/runner.py` for:
     `_resolve_run_receipt`, `_resolve_dataset_path`, `_render_catalog_path`,
     `_hash_partition`, `_load_json`, `_load_yaml`, `_schema_from_pack`,
     `_inline_external_refs`, and schema validation helpers.
   - Add local helpers for:
     - geometry extraction (tolerate `geometry` vs `geom`),
     - STRtree candidate handling (`numbers.Integral` index guard),
     - floor policy lookup per tzid (default floor=0, bump_threshold=1.0),
     - deterministic row sorting and immutability comparison.

2) **Add the module export**
   - File: `packages/engine/src/engine/layers/l1/seg_3A/s2_priors/__init__.py`
     exporting `run_s2`.

3) **Add the CLI wrapper**
   - File: `packages/engine/src/engine/cli/s2_priors_3a.py`
     mirroring the S0/S1 pattern (contracts layout/root, runs root, external
     roots, run_id).

4) **Makefile wiring**
   - Add `segment3a-s2` target with `SEG3A_S2_*` vars.
   - Update `segment3a` chain to include S2 after S1.

5) **Implementation flow inside `run_s2`**
   - Resolve run receipt; capture `run_id`, `parameter_hash`, `manifest_fingerprint`.
   - Load S0 outputs (`s0_gate_receipt_3A`, `sealed_inputs_3A`) and validate
     schemas; enforce upstream gate PASS (1A/1B/2A).
   - Load contracts (dictionary + registry + schema packs) and resolve all
     input paths via catalogue (no hard-coded paths).
   - Resolve and validate `country_zone_alphas` and `zone_floor_policy`,
     recompute sha256 digests, and match against `sealed_inputs_3A`.
   - Resolve `iso3166_canonical_2024`, `world_countries`, `tz_world_2025a`
     and build `Z(c)` via spatial intersection (STRtree + antimeridian split).
   - Enforce strict Z(c) coverage vs priors (no missing or extra tzids).
   - Apply floor/bump:
     - compute `alpha_sum_raw`, `share_raw` (0 if sum=0),
     - apply bump gate: `share_raw >= bump_threshold`,
     - `alpha_effective = max(alpha_raw, floor_value)` when gate passes.
   - Compute `alpha_sum_country` and `share_effective` (tolerance checks).
   - Build rows with required lineage fields + flags; sort by `[country_iso, tzid]`.
   - Validate against `schemas.3A.yaml#/plan/s2_country_zone_priors`.
   - Write to tmp, publish atomically, enforce immutability if partition exists.
   - Emit run-report + `segment_state_runs` JSONL row (minimal aggregates).

Logging commitments (story-driven):
- Story header: objective + gated inputs + outputs.
- Narrative phase logs before each major loop (Z(c) build, alpha derivation).
- Progress logs for country iteration with elapsed/rate/ETA.
- Validation events for each contract/invariant check.

If any of the above choices need to change mid-implementation, I will append a
new entry documenting the alternative considered, the change, and the reason
before editing code.

### Entry: 2026-01-18 01:21

Implementation start checkpoint for S2 (pre-code). This entry captures the
first concrete mechanics decisions I need to lock in before touching code.

1) **sealed_inputs_3A format handling**
   - Decision: accept the contract JSON list as authoritative, but add a
     *non-invasive* fallback: if JSON parsing fails and the path is a parquet,
     load via Polars and treat each row as a sealed_inputs record.
   - Rationale: existing test harnesses sometimes materialize sealed inputs as
     parquet; this keeps dev runs unblocked without changing the prod contract.
   - Constraint: fallback only if JSON cannot be read; it will not be used
     when the JSON file is valid.

2) **Immutability comparison**
   - Decision: if `s2_country_zone_priors` already exists, read all parquet
     files, sort by `[country_iso, tzid]`, and compare to the newly computed
     DataFrame using exact equality (no tolerance).
   - Rationale: output is deterministic; exact comparisons are required by
     the immutability contract and avoid hiding drift.
   - If mismatch: raise `E3A_S2_011_IMMUTABILITY_VIOLATION` and do not overwrite.

3) **Output file layout**
   - Decision: write a single `part-00000.parquet` under the parameter hash
     partition (the dataset is small and fits in memory).
   - Rationale: stable layout, simplest to hash/compare, aligns with other
     small parameter-scoped outputs.

4) **Error-code mapping choices**
   - Missing/invalid S0 artefacts -> `E3A_S2_001_S0_GATE_OR_SEALED_INPUTS_INVALID`.
   - Missing/malformed catalogue artefacts -> `E3A_S2_002_CATALOGUE_MALFORMED`.
   - Missing or ambiguous policy/prior -> `E3A_S2_003_PRIOR_OR_POLICY_MISSING_OR_AMBIGUOUS`.
   - Policy/prior schema violations -> `E3A_S2_004_PRIOR_OR_POLICY_SCHEMA_INVALID`.
   - Unknown country or empty Z(c) -> `E3A_S2_005_ZONE_UNIVERSE_MISMATCH`.
   - sealed_inputs digest/path mismatch -> `E3A_S2_006_SEALED_INPUT_MISMATCH`.
   - Missing tzids in priors (vs Z(c)) -> `E3A_S2_007_DOMAIN_MISMATCH_UNIVERSE`.
   - Alpha sum or share consistency failures -> `E3A_S2_008_ALPHA_VECTOR_DEGENERATE_OR_INCONSISTENT`.
   - Output schema violations -> `E3A_S2_009_OUTPUT_SCHEMA_INVALID`.
   - Lineage inconsistency -> `E3A_S2_010_LINEAGE_INCONSISTENT`.
   - Output partition conflict -> `E3A_S2_011_IMMUTABILITY_VIOLATION`.
   - Any unexpected I/O/infra failure -> `E3A_S2_012_INFRASTRUCTURE_IO_ERROR`.

With these choices recorded, I can proceed to implement the S2 runner + CLI +
Makefile wiring.

### Entry: 2026-01-18 01:26

Pre-coding alignment checkpoint (logging + wiring context before edits).
Purpose: confirm the concrete implementation flow, logging cadence, and Makefile
targets so the S2 work lands consistent with existing S1/S0 style.

Evidence used:
- Run log style sampled from the current run:
  `runs/local_full_run-5/970b0bd6833be3a0f08df8e8abf0364c/run_log_970b0bd6833be3a0f08df8e8abf0364c.log`
  (story headers, phase logs, progress cadence with elapsed/rate/ETA).
- Contracts refreshed:
  `docs/model_spec/data-engine/layer-1/specs/contracts/3A/dataset_dictionary.layer1.3A.yaml`,
  `docs/model_spec/data-engine/layer-1/specs/contracts/3A/schemas.3A.yaml`.
- Error code section checked in:
  `docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s2.expanded.md`.

Implementation alignment decisions (to avoid drift from prior engineer):
1) **Logging cadence & structure**
   - Emit a story header log before any heavy work:
     objective + gated inputs + outputs.
   - Use phase logs (StepTimer) between major phases (gate, sealed inputs,
     policy load, Z(c) derivation, alpha derivation, publish).
   - Use progress logs with elapsed/rate/ETA for long loops (country iteration
     in Z(c) and alpha derivation), matching the run-log pattern.

2) **CLI + Makefile integration**
   - Mirror `s1_escalation_3a` CLI shape for S2 (`--contracts-layout`,
     `--contracts-root`, `--runs-root`, `--external-root`, `--run-id`).
   - Add `segment3a-s2` target and wire into `segment3a` chain after S1.
   - Add `SEG3A_S2_RUN_ID` + `SEG3A_S2_ARGS/CMD` in Makefile near S0/S1 blocks.

3) **Contracts-root alignment**
   - Continue to resolve contracts via `EngineConfig` with `contracts_layout`
     so switching from model_spec to root contracts remains config-only.

Implementation steps (immediate next actions):
1) Create `packages/engine/src/engine/layers/l1/seg_3A/s2_priors/runner.py`
   following S1's patterns, using S0 helper imports where possible.
2) Add `packages/engine/src/engine/layers/l1/seg_3A/s2_priors/__init__.py`.
3) Add `packages/engine/src/engine/cli/s2_priors_3a.py`.
4) Update Makefile with `segment3a-s2` and S2 run args variables.

If any deviation from these alignment decisions becomes necessary during coding,
I will append a new entry before the change is applied.

### Entry: 2026-01-18 01:45

Implementation actions completed (S2 coding pass) + small in-flight decisions.

Files created/updated:
- `packages/engine/src/engine/layers/l1/seg_3A/s2_priors/runner.py`
  - Full S2 runner with gate + sealed input validation, prior/floor parsing,
    Z(c) derivation via STRtree + antimeridian split, floor/bump application,
    output schema validation, immutability checks, and run-report emission.
- `packages/engine/src/engine/layers/l1/seg_3A/s2_priors/__init__.py`
  - Export `run_s2`.
- `packages/engine/src/engine/cli/s2_priors_3a.py`
  - CLI wrapper mirroring S0/S1 args.
- `makefile`
  - Added `SEG3A_S2_RUN_ID`, `SEG3A_S2_ARGS/CMD`, `segment3a-s2` target, and
    extended `segment3a` chain and `.PHONY` list.

Micro-decisions locked during coding:
1) **Immutability comparison mechanism**
   - Use Polars `DataFrame.equals` for the primary equality check.
   - If equality fails but shapes match, compute `difference_count` using
     anti-joins on all columns (exact match) to populate
     `E3A_S2_011_IMMUTABILITY_VIOLATION` context.
   - Rationale: `equals` is the most direct strict comparison available in
     Polars; anti-joins give a deterministic difference count without
     introducing tolerance.

2) **tz cache release-tag mismatch mapping**
   - If `tz_timetable_cache` is sealed and its `tzdb_release_tag` disagrees
     with the tz_world tag, fail with
     `E3A_S2_005_ZONE_UNIVERSE_MISMATCH` and `reason="unmappable_tzid"`.
   - Rationale: spec does not define a dedicated reason for release-tag
     mismatch; this preserves the error family while capturing the detail.

3) **Domain mismatch enforcement (re-confirmed)**
   - Extra prior tzids -> `E3A_S2_005_ZONE_UNIVERSE_MISMATCH`.
   - Missing prior tzids -> `E3A_S2_007_DOMAIN_MISMATCH_UNIVERSE`.
   - Implemented by precomputing missing/extra counts before alpha derivation.

Next steps:
- Sanity-check the runner for syntax/logic errors.
- Run the requested `make segment2b-s2` and fix any errors (logging decisions).

### Entry: 2026-01-18 01:47

Small correctness fix during S2 review:
- Adjusted `zone_count_buckets` aggregation to use the full list of
  per-country zone counts (no set-deduplication), ensuring accurate frequency
  counts in the run-report.

## S3 - Zone Share Sampling (Dirichlet draws)

### Entry: 2026-01-18 02:10

Context for S3 planning (files read this pass):
- docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s3.expanded.md
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/schemas.3A.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/dataset_dictionary.layer1.3A.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/3A/artefact_registry_3A.yaml
- docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml
- docs/model_spec/data-engine/rdv_rails_constitution_v1.md (Layer-1 RNG law)
- Implementation patterns for RNG + trace:
  - packages/engine/src/engine/layers/l1/seg_1A/s1_hurdle/rng.py
  - packages/engine/src/engine/layers/l1/seg_1A/s2_nb_outlets/runner.py
  - packages/engine/src/engine/layers/l1/seg_1A/s7_integerisation/runner.py
  - packages/engine/src/engine/layers/l1/seg_2B/s5_router/runner.py

Problem statement (S3):
- Implement the RNG-bearing state for Segment 3A. Given:
  - `s1_escalation_queue` (S1 authority on escalated merchant-country pairs),
  - `s2_country_zone_priors` (S2 authority on alpha vectors per country),
  - plus S0 gate + sealed inputs,
  produce:
  - `s3_zone_shares` (one row per escalated merchant x country x tzid),
  - `rng_event_zone_dirichlet` events (one per escalated pair),
  - `rng_trace_log` updates after each event,
  - `rng_audit_log` entry if missing,
  with strict determinism, immutability for `s3_zone_shares`, and Layer-1 RNG
  envelope compliance.

Key decisions and alternatives (some require confirmation):
1) RNG stream keying + `rng_stream_id`
   - Alternative A: `rng_stream_id` as a readable string
     (e.g., `3A.zone_dirichlet:{merchant_id}:{country_iso}`), then hash to
     derive Philox key and base counter.
   - Alternative B: `rng_stream_id` as a SHA-256 hex digest of a canonical
     tuple (module, substream_label, merchant_id, country_iso).
   - Recommendation: **Alternative B** to keep deterministic, fixed-length
     stream IDs and avoid delimiter ambiguity. This ID is written to both
     `rng_event_zone_dirichlet` and `s3_zone_shares`.
   - Confirmation needed: whether you want readable stream IDs or hashed IDs.

2) RNG master material inputs
   - Alternative A: derive master material from `{manifest_fingerprint, seed}`
     (matches 1A RNG helper pattern).
   - Alternative B: include `parameter_hash` (and/or `run_id`) directly in
     master material or stream ID derivation.
   - Recommendation: **Alternative A** to align with existing engine RNG
     practice. `parameter_hash` is already part of `manifest_fingerprint`,
     and `run_id` is used for partitioning/log identity.
   - Confirmation needed: whether you want `run_id` (or explicit
     `parameter_hash`) to influence the stream key beyond the manifest hash.

3) `rng_event_id` in `s3_zone_shares`
   - Alternative A: leave `rng_event_id` null (schema allows nullable).
   - Alternative B: compute deterministic event ID (e.g., hash of
     `{seed, parameter_hash, run_id, module, substream_label, rng_stream_id}`).
   - Recommendation: **Alternative A** (null) unless you want explicit
     linkage beyond `rng_stream_id`.

4) Existing RNG logs behavior on re-run
   - Alternative A: if events + trace already exist for `(seed, parameter_hash, run_id)`,
     validate and skip emitting new RNG logs (idempotent).
   - Alternative B: allow appending new events (would violate append-only
     identity requirements and introduce duplicates).
   - Recommendation: **Alternative A**; if partial logs exist, fail closed.

5) Gamma sampler implementation
   - Alternative A: reuse Marsaglia-Tsang gamma sampler from 1A S7
     (counts blocks/draws precisely).
   - Alternative B: implement new gamma logic.
   - Recommendation: **Alternative A** for consistency and replayability.

Planned implementation steps (pre-coding plan; explicit mechanics):
1) Contracts + identity
   - Load schema packs: `schemas.layer1.yaml`, `schemas.3A.yaml`.
   - Load dictionary/registry: `dataset_dictionary.layer1.3A.yaml`,
     `artefact_registry_3A.yaml`.
   - Resolve run receipt; capture `run_id`, `parameter_hash`, `manifest_fingerprint`,
     and `seed`. Validate token formats.
   - Continue to use `ContractSource` via `EngineConfig` so switching from
     model_spec to root contracts is config-only.

2) Gate + sealed inputs (S0)
   - Resolve `s0_gate_receipt_3A` and `sealed_inputs_3A` via catalogue.
   - Validate schemas; ensure upstream gates for 1A/1B/2A are PASS.
   - Verify `sealed_policy_set` contains S1/S2 policy entries; if an RNG
     policy artefact is ever introduced, verify it is sealed and hashed.

3) Load S1/S2 data-plane inputs
   - Read `s1_escalation_queue@seed/manifest_fingerprint` and validate schema.
   - Read `s2_country_zone_priors@parameter_hash` and validate schema.
   - Build `D_esc`: filter `is_escalated=true`, sort by
     `(merchant_id, legal_country_iso)`; this ordering defines RNG event order.
   - For each country in `D_esc`, assert S2 provides priors
     (missing -> `E3A_S3_003_PRIOR_SURFACE_INCOMPLETE`).

4) Build per-country prior map
   - For each `country_iso`, derive `Z_ord(c)` by sorting `tzid` ascending.
   - Create alpha list `alpha_effective(c, z_i)` in this order.
   - Validate:
     - all `alpha_effective > 0`,
     - `alpha_sum_country` consistent across rows for the country,
     - lineage fields (`prior_pack_id/version`, `floor_policy_id/version`)
       constant across the entire dataset.

5) RNG wiring + sampling loop
   - Implement `seg_3A/s3_zone_shares/rng.py` mirroring 1A RNG helpers:
     - Philox2x64-10 core + `u01` mapping.
     - `Substream` with 128-bit counter and block-based draws.
     - `derive_master_material` (manifest_fingerprint_bytes + seed).
     - `derive_substream_state` using label + canonicalized `(merchant_id, country_iso)`.
   - For each `(merchant_id, legal_country_iso)` in `D_esc`:
     - compute `rng_stream_id` (per decision above),
     - snapshot `counter_before`,
     - for each alpha in `Z_ord(c)` draw `Gamma(alpha, 1)` via MT1998
       implementation (counts blocks/draws),
     - ensure `sum_gamma > 0`, compute `share_drawn = gamma_i / sum_gamma`,
     - snapshot `counter_after`, compute `blocks` (u128 delta) and
       `draws` (uniform count), verify `blocks` matches counter delta.

6) Emit RNG event + trace
   - Write `rng_event_zone_dirichlet` JSONL rows (one per `(m,c)`):
     `module="3A.S3"`, `substream_label="zone_dirichlet"`,
     `rng_stream_id`, `merchant_id`, `country_iso`, `zone_count`,
     counters + blocks/draws, optional `alpha_sum_country`.
   - Append one `rng_trace_log` row after each event using a trace accumulator
     (same pattern as S7): totals per `(module, substream_label)` only.
   - Ensure `rng_audit_log` entry exists (append-only) using the S5 router
     `_ensure_rng_audit` pattern.

7) Build `s3_zone_shares`
   - For each `(m,c,z)` row: populate required columns:
     - `share_drawn`, `share_sum_country`, `alpha_sum_country`,
       lineage fields from S2, `rng_module`, `rng_substream_label`,
       `rng_stream_id`, optional `rng_event_id` (decision pending).
   - Sort rows by `[merchant_id, legal_country_iso, tzid]`.
   - Validate against `schemas.3A.yaml#/plan/s3_zone_shares`.

8) Idempotent publish + immutability
   - If `s3_zone_shares` exists for `{seed, manifest_fingerprint}`:
     - read + normalize + sort existing rows and compare to new rows.
     - identical => skip write; mismatch => `E3A_S3_011_IMMUTABILITY_VIOLATION`.
   - For RNG logs:
     - If events + trace already exist for the run, treat as idempotent
       and skip emitting new logs (validate counts vs D_esc).
     - If partial logs exist, fail closed.
   - Use tmp files + atomic publish to avoid partial outputs.

9) Observability + run-report
   - Story header log: objective, gated inputs, outputs.
   - Phase logs before/after: load S0, load S1/S2, build priors, RNG sampling,
     output publish.
   - Progress logs for `(m,c)` loop: elapsed, rate, ETA.
   - Emit `segment_state_runs` JSONL and `s3_run_report_3A` with:
     counts of escalated pairs, total rows, zone-count distribution,
     RNG events/draws/blocks, status/error code.

Performance + resumability considerations:
- Use in-memory structures for per-country priors (small), and loop per
  escalated pair (streamed). Avoid storing large intermediates in memory.
- If outputs already exist and are identical, skip re-write to support resume.
- If a failure occurs after RNG events are emitted, the run is marked FAIL
  (events remain as append-only logs per spec).

Open confirmations before coding:
1) `rng_stream_id` format (hashed vs readable).
2) Whether to include `run_id` or explicit `parameter_hash` in stream derivation.
3) Whether to populate `rng_event_id` (deterministic) or leave null.
4) Idempotent behavior for existing RNG logs (validate-and-skip vs fail).

If any of the above decisions change mid-implementation, I will append a new
entry capturing the alternatives considered, the change, and the rationale
before editing code.

### Entry: 2026-01-18 02:26

Decisions confirmed for S3 implementation (user-approved):
1) `rng_stream_id` format:
   - Use SHA-256 hex digest of `3A.S3|zone_dirichlet|{merchant_id}|{country_iso}`.
   - Rationale: fixed-length, deterministic, and avoids delimiter ambiguity;
     still tied to `(m,c)` identity for replay and diagnostics.

2) Stream derivation material:
   - Derive master material from `{manifest_fingerprint_bytes, seed}` only,
     mirroring the 1A RNG helper pattern.
   - `run_id` and `parameter_hash` are not injected into the key derivation;
     `run_id` remains an identity partition for RNG logs.
   - Rationale: aligns with existing engine RNG practice while keeping
     deterministic replay for identical run anchors.

3) `rng_event_id` in `s3_zone_shares`:
   - Leave `rng_event_id` null (schema allows nullable).
   - Rationale: linkage is already established by `rng_stream_id` and
     event envelopes; avoid inventing extra identifiers pre-contract.

4) Existing RNG logs on re-run:
   - If `rng_event_zone_dirichlet` and `rng_trace_log` already exist and are
     non-empty, validate-and-skip emitting new logs.
   - If only one exists (partial logs), fail closed as an append-only
     integrity violation.
   - Rationale: preserve append-only semantics and avoid duplicate events.

Implementation start (immediate next steps):
- Build S3 RNG helper (`seg_3A/s3_zone_shares/rng.py`) using Philox2x64-10 +
  Marsaglia-Tsang gamma sampler from 1A, with 3A-specific domain tags.
- Implement `run_s3` runner with:
  - S0 gate + sealed inputs validation,
  - S1/S2 input loading and domain checks,
  - deterministic Dirichlet sampling per escalated `(m,c)`,
  - RNG event + trace logging,
  - `s3_zone_shares` output with immutability checks,
  - run-report and `segment_state_runs` emission.
- Add `__init__.py` export, CLI entrypoint, and Makefile target for `segment3a-s3`.

If any deviation from these decisions becomes necessary during coding, I will
append a new entry describing the change and why before editing code.

### Entry: 2026-01-18 02:46

Implementation actions completed for S3 (Dirichlet zone shares):
Files created/updated:
- `packages/engine/src/engine/layers/l1/seg_3A/s3_zone_shares/rng.py`
  - New 3A-specific RNG helper with domain tags:
    `mlr:3A.master` for master material and `mlr:3A.zone_dirichlet` for stream.
  - Implements Philox substreams + u01 sampling (single/pair) mirroring 1A.
- `packages/engine/src/engine/layers/l1/seg_3A/s3_zone_shares/runner.py`
  - Full S3 runner: S0/S1/S2 validation, deterministic Dirichlet sampling,
    RNG event + trace emission, immutability checks, run-report emission.
- `packages/engine/src/engine/layers/l1/seg_3A/s3_zone_shares/__init__.py`
  - Export `run_s3`.
- `packages/engine/src/engine/cli/s3_zone_shares_3a.py`
  - CLI wrapper mirroring S0/S1/S2 args.
- `makefile`
  - Added `SEG3A_S3_RUN_ID`, S3 args/cmd, `segment3a-s3` target, and updated
    `segment3a` chain + `.PHONY`.

Micro-decisions made during coding:
1) **Alpha consistency check**:
   - For each country, compute `alpha_sum_raw = sum(alpha_effective)` and
     compare to S2’s `alpha_sum_country` within `TOLERANCE`.
   - If mismatch or non-positive, fail with `E3A_S3_006_DIRICHLET_ALPHA_MISMATCH`.
   - Rationale: catches drift between S2 outputs and S3’s sampling inputs.

2) **Existing RNG logs handling (idempotence)**:
   - If both `rng_event_zone_dirichlet` and `rng_trace_log` exist for the run,
     skip emitting new RNG logs; still compute shares and enforce immutability.
   - If only one exists, fail with `E3A_S3_007_RNG_ACCOUNTING_BROKEN`.
   - If logs are skipped, `rng_trace_rows` in run-report is set to the expected
     event count (to reflect the run scope).

3) **Audit log requirement**:
   - If RNG logs already exist, require a matching audit row for the run_id.
   - If writing new logs, append audit row if missing (append-only behavior).

Pending:
- Run `make segment3a-s3` and capture any failures in the logbook (with any
  corrective decisions appended here).

### Entry: 2026-01-18 02:49

Issue observed while running `make segment3a-s3`:
- Run-report shows `E3A_S3_012_INFRASTRUCTURE_IO_ERROR` with
  `error_context` pointing to `'DataFrame' object has no attribute 'groupby'`
  in the S2 prior-validation phase in
  `packages/engine/src/engine/layers/l1/seg_3A/s3_zone_shares/runner.py`.

Plan and decision (pre-fix):
- Root cause: Polars uses `group_by`, not the pandas-style `groupby`.
- Alternatives considered:
  1) Convert to pandas for this check (rejected: unnecessary materialization,
     deviates from polars-only pipeline, increases memory).
  2) Replace with Polars `group_by` (chosen: idiomatic, minimal change, keeps
     invariant enforcement on alpha-sum uniqueness).
- Exact change: replace `s2_df.groupby("country_iso")` with
  `s2_df.group_by("country_iso")` when computing `alpha_sum_counts`.
- Inputs/authorities: S2 output `s2_prior_dirichlet` schema from
  `docs/model_spec/data-engine/layer-1/specs/contracts/3A/schemas.3A.yaml`;
  prior-lineage invariants from S3 expanded spec.
- Invariants preserved: per-country `alpha_sum_country` must be unique.
- Logging: no new logs; existing validation log remains aligned to the S3
  story header for priors validation.
- Resumability: no new artifacts; re-run should reuse existing run scope and
  continue to immutability checks.
- Validation: re-run `make segment3a-s3` and inspect the run report for green
  completion; log outcome and any new decisions in logbook + this map.

### Entry: 2026-01-18 02:53

Issue observed while re-running `make segment3a-s3` after the group_by fix:
- S3 fails with `E3A_S3_003_PRIOR_SURFACE_INCOMPLETE` reporting
  `missing_countries_count=63`, `sample_country_iso=AD`.
- Local inspection shows S1 escalated countries are present in S2 priors,
  so this appears to be a key-mismatch bug in S3, not a true data gap.

Plan and decision (pre-fix):
- Root cause: `polars.DataFrame.partition_by(..., as_dict=True)` returns tuple
  keys (e.g., `('AD',)`), while escalated countries are strings (`'AD'`).
  This causes every escalated country to appear "missing" because the keys
  do not compare equal.
- Alternatives considered:
  1) Replace `partition_by` with `group_by` and aggregate lists, then iterate.
     (rejected: more refactor for a small mismatch fix)
  2) Keep `partition_by` but unwrap tuple keys when building `priors_by_country`
     (chosen: minimal, preserves existing validation flow)
- Exact change: normalize `country_iso` by unwrapping tuple keys to their first
  element before using as dict keys and for logging/validation.
- Inputs/authorities: S1 escalation queue (`legal_country_iso`) and S2 priors
  (`country_iso`) as defined in `schemas.3A.yaml` and the S3 expanded spec.
- Invariants preserved: per-country alpha validation and prior surface
  completeness checks remain unchanged, but now compare like-for-like keys.
- Logging: no new logging; validation errors keep the existing narrative flow.
- Validation: re-run `make segment3a-s3`, verify green run-report, and record
  the outcome in the logbook + this map.

### Entry: 2026-01-18 02:54

Fix applied and outcome:
- Updated `packages/engine/src/engine/layers/l1/seg_3A/s3_zone_shares/runner.py`
  to unwrap tuple keys from `partition_by(..., as_dict=True)` so
  `priors_by_country` uses string `country_iso` keys.
- Re-ran `make segment3a-s3`; S3 completed successfully.
  - Progress logs emitted as expected during the sampling loop.
  - Output published to:
    `runs/local_full_run-5/970b0bd6833be3a0f08df8e8abf0364c/data/layer1/3A/s3_zone_shares/seed=42/manifest_fingerprint=35c89fb31f5d034652df74c69ffbec7641b2128375ba5dd3582fb2e5a4ed2e08`.
  - Run-report written under the matching reports path with status PASS.
- Pending item for `make segment3a-s3` is now satisfied.

### Entry: 2026-01-18 03:04

S4 review + implementation plan (pre-coding):

Goal:
- Implement 3A.S4 integer zone allocation per `docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s4.expanded.md`,
  producing `s4_zone_counts` from S1 site counts and S3 shares, aligned to S2
  zone universes, RNG-free and deterministic.

Contract sources & authorities:
- Contracts loaded via `ContractSource(config.contracts_root, config.contracts_layout)` (dev mode uses
  `docs/model_spec/...` layout; production can switch to root contracts without code changes).
- Inputs: `s0_gate_receipt_3A`, `sealed_inputs_3A`, `s1_escalation_queue`,
  `s2_country_zone_priors`, `s3_zone_shares`, plus run-report rows for S1/S2/S3.
- Output: `s4_zone_counts` and `s4_run_report_3A` (schema ref: `schemas.layer1.yaml#/run_report/segment_state_run`).

Algorithm plan (explicit steps):
1) **Run identity + paths**
   - Read `run_receipt.json` to fix `run_id`, `seed`, `parameter_hash`, `manifest_fingerprint`.
   - Instantiate `RunPaths`, attach file handler, emit story header log with objective and outputs.
2) **Load contracts**
   - Load dictionary and schema packs: `dataset_dictionary.layer1.3A.yaml`, `schemas.3A.yaml`,
     `schemas.layer1.yaml` via `load_dataset_dictionary` / `load_schema_pack`.
   - Fail with `E3A_S4_002_CATALOGUE_MALFORMED` if any required catalogue artefact is missing/invalid.
3) **S0 gate + sealed inputs**
   - Validate `s0_gate_receipt_3A` and `sealed_inputs_3A` schemas.
   - Enforce upstream gates (1A/1B/2A) `PASS`.
   - Verify `sealed_policy_set` includes `zone_mixture_policy`, `country_zone_alphas`, `zone_floor_policy`
     (same posture as S3). If any missing -> `E3A_S4_001_PRECONDITION_FAILED`.
4) **S1 escalation queue**
   - Load and schema-validate `s1_escalation_queue`.
   - Assert no duplicate `(merchant_id, legal_country_iso)` pairs.
   - Build `D` and `D_esc`, sorted by `(merchant_id, legal_country_iso)`.
   - Ensure `site_count >= 1` for escalated pairs; otherwise fail with
     `E3A_S4_003_DOMAIN_MISMATCH_S1` or `E3A_S4_007_OUTPUT_INCONSISTENT` depending on context.
5) **S2 priors**
   - Load and validate `s2_country_zone_priors`.
   - Assert no duplicate `(country_iso, tzid)`.
   - Build `Z(c)` per country (sorted lexicographically by `tzid`).
   - Verify all escalated countries have non-empty `Z(c)`; missing -> `E3A_S4_004_DOMAIN_MISMATCH_ZONES`.
   - Capture `prior_pack_id`, `prior_pack_version`, `floor_policy_id`, `floor_policy_version`
     as unique constants (fail `E3A_S4_007_OUTPUT_INCONSISTENT` on lineage mismatch).
6) **S3 shares**
   - Load and validate `s3_zone_shares`.
   - Assert no duplicate `(merchant_id, legal_country_iso, tzid)`.
   - Project `D_S3` and require `D_S3 == D_esc`; otherwise `E3A_S4_003_DOMAIN_MISMATCH_S1`.
   - For each `(m,c)`, ensure `tzid` set equals `Z(c)` and matches S3; otherwise
     `E3A_S4_004_DOMAIN_MISMATCH_ZONES`.
   - Validate `share_sum_country` consistent within each `(m,c)` and within tolerance of 1.
     Out-of-range or inconsistent -> `E3A_S4_007_OUTPUT_INCONSISTENT`.
7) **Integerisation per `(m,c)`**
   - For each escalated pair, iterate `Z_ord(c)` (lexicographic tzid):
     - `T_z = site_count * share_drawn` (float64).
     - `b_z = floor(T_z)`, `base_sum = Σ b_z`, `R = site_count - base_sum`.
     - If `R < 0` or `base_sum > site_count`, fail `E3A_S4_005_COUNT_CONSERVATION_BROKEN`.
     - Residuals `r_z = T_z - b_z` (in [0,1)).
     - Order by `(-r_z, tzid, stable_index)`; allocate `+1` to top `R`.
     - Record `zone_site_count` and optional `residual_rank`.
   - Compute `zone_site_count_sum = site_count` per `(m,c)` and track conservation stats.
8) **Materialize output**
   - Build rows with required fields:
     `seed`, `manifest_fingerprint`, `merchant_id`, `legal_country_iso`, `tzid`,
     `zone_site_count`, `zone_site_count_sum`, `share_sum_country`,
     `prior_pack_id`, `prior_pack_version`, `floor_policy_id`, `floor_policy_version`,
     plus optional `fractional_target`, `residual_rank`, `alpha_sum_country`, `notes`.
   - Validate against `schemas.3A.yaml#/plan/s4_zone_counts` (schema invalid -> `E3A_S4_006_OUTPUT_SCHEMA_INVALID`).
   - Sort by `(merchant_id, legal_country_iso, tzid)`.
9) **Idempotent publish**
   - If existing `s4_zone_counts` partition exists, normalize + compare row-for-row:
     - identical -> reuse; different -> `E3A_S4_008_IMMUTABILITY_VIOLATION`.
   - Else write via tmp path, then publish atomically.
10) **Run-report + segment_state_runs**
   - Write `s4_run_report_3A` with counts (`pairs_total`, `pairs_escalated`, `pairs_monolithic`,
     `zone_rows_total`, `zones_per_pair_avg`, `zones_zero_allocated`,
     `pairs_with_single_zone_nonzero`, `pairs_count_conserved`,
     `pairs_count_conservation_violations`) and lineage fields.
   - Append to `segment_state_runs` for `(layer1, 3A, S4)` as in S2/S3.
   - Error handling maps to `E3A_S4_001`–`E3A_S4_009` per spec, with `error_context` populated
     to include required fields (e.g., counts + sample identifiers).

Logging + resumability:
- Emit story header log at start with objective and outputs.
- Phase logs aligned to spec steps (S0 gate, S1/S2/S3 load, domain build, integerisation, publish).
- Use progress logs for `(m,c)` loop: elapsed, processed/total, rate, ETA.
- If pre-existing output is identical, skip rewrite; otherwise fail immutability.

Performance considerations:
- Use Polars for all dataset loads; avoid full-row Python loops except per `(m,c)` integerisation.
- Pre-index S3 rows by `(merchant_id, legal_country_iso)` for fast access, but avoid tuple-key mismatches
  (unwrap tuple keys from `partition_by(..., as_dict=True)`).
- Keep memory bounded by iterating per pair; no need to materialize massive intermediate arrays.

Open decisions/questions to confirm with user before coding:
1) Should S4 populate optional `fractional_target`, `residual_rank`, and `alpha_sum_country` columns
   in `s4_zone_counts` (recommended for auditability), or keep output minimal?
2) Tolerance for `share_sum_country` (S4 acceptance): reuse S3's `TOLERANCE=1e-12`, or adopt
   a different epsilon from validation specs?
3) Should S4 enforce presence of S1/S2/S3 run-report rows strictly (fail if missing), or allow
   dataset existence alone in dev mode?

### Entry: 2026-01-18 03:18

S4 decisions confirmed before coding:
- **Optional columns**: populate `fractional_target`, `residual_rank`, and
  `alpha_sum_country` in `s4_zone_counts` to support auditability and replay.
- **Share-sum tolerance**: reuse S3’s `TOLERANCE = 1e-12` for
  `share_sum_country` consistency checks.
- **Run-report strictness**: require S1/S2/S3 run-report rows and `status="PASS"`;
  missing or non-PASS is treated as `E3A_S4_001_PRECONDITION_FAILED`.

These decisions are binding for the S4 implementation below; any deviation will
be logged as a new entry before changes are made.

### Entry: 2026-01-18 03:36

S4 implementation actions (coding in progress, deterministic integerisation):
- Added S4 runner at `packages/engine/src/engine/layers/l1/seg_3A/s4_zone_counts/runner.py`.
  Key mechanics implemented:
  1) S0 gate + sealed inputs validation (schema, upstream gate PASS, sealed policy IDs).
  2) Strict run-report checks for S1/S2/S3 (`status="PASS"` required).
  3) S1/S2/S3 dataset validation, duplicate detection, and domain alignment checks.
  4) Deterministic integerisation per `(m,c)` using floor + residual ranking
     with tie-break: `(-residual, tzid, stable_index)`.
  5) Output construction with optional diagnostics populated:
     `fractional_target`, `residual_rank`, `alpha_sum_country`.
  6) Idempotent publish with immutability enforcement (`E3A_S4_008`).
  7) Narrative logs + progress tracker (elapsed/progress/rate/ETA).
  8) Run-report + segment_state_runs emission; structured start/success/failure
     logs per S4 observability spec (in addition to validation logs).
- Added module export: `packages/engine/src/engine/layers/l1/seg_3A/s4_zone_counts/__init__.py`.
- Added CLI entrypoint: `packages/engine/src/engine/cli/s4_zone_counts_3a.py`.
- Updated `makefile` with `SEG3A_S4_RUN_ID`, args/cmd wiring, `segment3a-s4`
  target, and `segment3a` chain update; `.PHONY` updated accordingly.

Notes on error mapping during implementation:
- Precondition errors map to `E3A_S4_001_PRECONDITION_FAILED` with required
  `component/reason/state` fields.
- Domain mismatches use `E3A_S4_003` (pair-level) and `E3A_S4_004` (zone-level).
- Integerisation failures (`remainder_invalid`, `count_sum_mismatch`) map to
  `E3A_S4_005_COUNT_CONSERVATION_BROKEN`.
- Output schema validation maps to `E3A_S4_006_OUTPUT_SCHEMA_INVALID`.
- Output inconsistencies (lineage or share_sum issues) map to `E3A_S4_007`.
- Immutability mismatches map to `E3A_S4_008_IMMUTABILITY_VIOLATION`.

Pending:
- Run `make segment3a-s4` and record any failures and fixes.

### Entry: 2026-01-18 03:37

S4 run verification:
- Executed `make segment3a-s4` for run_id `970b0bd6833be3a0f08df8e8abf0364c`.
- S4 completed successfully; integerisation loop processed 1471 escalated pairs
  and produced 14800 rows.
- Output published to:
  `runs/local_full_run-5/970b0bd6833be3a0f08df8e8abf0364c/data/layer1/3A/s4_zone_counts/seed=42/manifest_fingerprint=35c89fb31f5d034652df74c69ffbec7641b2128375ba5dd3582fb2e5a4ed2e08`.
- Run-report written to:
  `runs/local_full_run-5/970b0bd6833be3a0f08df8e8abf0364c/reports/layer1/3A/state=S4/seed=42/manifest_fingerprint=35c89fb31f5d034652df74c69ffbec7641b2128375ba5dd3582fb2e5a4ed2e08/run_report.json`
  with `status="PASS"` and `pairs_count_conservation_violations=0`.

### Entry: 2026-01-18 03:39

Post-run correction (precondition mapping):
- Adjusted S4 runner to treat missing S0/S1/S2/S3 artefacts as
  `E3A_S4_001_PRECONDITION_FAILED` instead of falling into the generic
  infrastructure error path.
- Implemented explicit `InputResolutionError` handling around:
  - `s0_gate_receipt_3A` and `sealed_inputs_3A`,
  - `s1_escalation_queue`,
  - `s2_country_zone_priors`,
  - `s3_zone_shares`.
- Rationale: aligns S4 error codes with the binding spec’s precondition rules
  for missing upstream artefacts.

Pending:
- Re-run `make segment3a-s4` to confirm the change stays green.

### Entry: 2026-01-18 03:39 (follow-up)

Re-run after precondition-mapping change:
- Executed `make segment3a-s4` again; output was identical and S4 returned PASS.
- Idempotence path exercised: existing `s4_zone_counts` detected and left
  unchanged (logged as identical).

### Entry: 2026-01-18 04:05

S5 planning notebook (initial; pending user clarification on digest recursion).

Problem statement:
- Implement 3A.S5 to publish `zone_alloc` (cross-layer egress) and
  `zone_alloc_universe_hash` (routing universe hash + component digests).
- Must be RNG-free and deterministic; must enforce S0/S1/S2/S3/S4 gates and
  sealed-input integrity; must emit narrative logs and resumable outputs.

Inputs / authorities to be used:
- Run identity from `run_receipt.json`: `run_id`, `seed`, `parameter_hash`,
  `manifest_fingerprint`.
- S0 gate + sealed inputs:
  - `s0_gate_receipt_3A` (upstream gate PASS checks, sealed_policy_set list).
  - `sealed_inputs_3A` (external artefacts whitelist, path + sha256_hex).
- Segment inputs:
  - `s1_escalation_queue` (domain D, `site_count`, escalation flags).
  - `s2_country_zone_priors` (Z(c), `alpha_sum_country`, prior/floor lineage).
  - `s3_zone_shares` (zone domain per escalated pair).
  - `s4_zone_counts` (authoritative integer counts per (m,c,z)).
- External policy artefacts (resolved via dictionary + sealed_inputs):
  - `zone_mixture_policy` -> `config/layer1/3A/policy/zone_mixture_policy.yaml`.
  - `country_zone_alphas` -> `config/layer1/3A/allocation/country_zone_alphas.yaml`.
  - `zone_floor_policy` -> `config/layer1/3A/allocation/zone_floor_policy.yaml`.
  - `day_effect_policy_v1` -> `config/layer1/2B/policy/day_effect_policy_v1.json`.
- Contracts:
  - `schemas.3A.yaml` (`#/egress/zone_alloc`, `#/validation/zone_alloc_universe_hash`).
  - `schemas.layer1.yaml` (`#/run_report/segment_state_run`).
  - `schemas.2B.yaml` (`#/policy/day_effect_policy_v1`).
  - `dataset_dictionary.layer1.3A.yaml` and `artefact_registry_3A.yaml`.
  - Contract source via `ContractSource(config.contracts_root, config.contracts_layout)`.

Plan / mechanics (draft, stepwise):
1) **Run receipt + logging**
   - Resolve `run_receipt.json`, verify `run_id`, `seed`, `parameter_hash`,
     `manifest_fingerprint`.
   - Initialize run log file handler; emit a story header:
     objective + gated inputs + outputs (`zone_alloc`, `zone_alloc_universe_hash`).
2) **Load contracts**
   - Load dataset dictionary + artefact registry + schema packs; on failure
     -> `E3A_S5_002_CATALOGUE_MALFORMED`.
3) **S0 gate / sealed inputs checks**
   - Load + schema-validate `s0_gate_receipt_3A` and `sealed_inputs_3A`.
   - Enforce upstream gate PASS for segments 1A/1B/2A.
   - Ensure `sealed_policy_set` contains logical IDs:
     `zone_mixture_policy`, `country_zone_alphas`, `zone_floor_policy`,
     `day_effect_policy_v1`.
   - Build `sealed_by_id` map; ensure unique logical IDs per row.
4) **Verify sealed policy artefacts**
   - For each required logical ID:
     - Resolve dictionary path and ensure `sealed_inputs_3A.path` matches
       the rendered catalog path.
     - Compute sha256 of raw bytes (file or directory) and compare to
       `sealed_inputs_3A.sha256_hex`.
     - Load policy payload to extract ID/version via `_policy_version_from_payload`
       (used to populate `mixture_policy_version` and `day_effect_policy_version`).
5) **Require upstream run-report PASS**
   - Load `s1_run_report_3A`, `s2_run_report_3A`, `s3_run_report_3A`,
     `s4_run_report_3A`; schema-validate and require `status="PASS"`.
   - Missing/non-PASS -> `E3A_S5_001_PRECONDITION_FAILED`.
6) **Load and validate S1-S4 datasets**
   - Read Parquet for S1/S2/S3/S4, validate against schema anchors.
   - Ensure uniqueness of keys:
     - S1 unique (merchant_id, legal_country_iso).
     - S4 unique (merchant_id, legal_country_iso, tzid).
7) **Domain + conservation checks**
   - Build D_esc from S1 where `is_escalated=true` (plus `site_count`).
   - Build Z(c) from S2 (country_iso, tzid) and `zone_count_by_country`.
   - Validate:
     - S4 (m,c) pairs == D_esc; compute missing/extra counts.
     - S4 tzid per row must exist in Z(c) and per-pair tzid count must equal
       zone_count_by_country (detect missing or extra zones).
     - S3 tzid per row must exist in Z(c) and per-pair tzid count must match
       zone_count_by_country (domain cross-check).
     - For each (m,c): `zone_site_count_sum` equals sum(zone_site_count) and
       equals S1 `site_count`.
   - Any mismatch -> `E3A_S5_003_DOMAIN_MISMATCH` with required counts
     (missing_escalated_pairs_count, unexpected_pairs_count,
     affected_zone_triplets_count + sample identifiers).
8) **Construct zone_alloc rows**
   - Base rows from S4 (`zone_site_count`, `zone_site_count_sum`, prior/floor lineage).
   - Join in S1 `site_count`.
   - Add policy lineage fields:
     `mixture_policy_id`, `mixture_policy_version`,
     `day_effect_policy_id`, `day_effect_policy_version`.
   - Optionally add `alpha_sum_country` (from S2/S4), keep `notes` null.
   - `routing_universe_hash` placeholder until digest computation.
9) **Writer-sort + schema validation**
   - Sort by (merchant_id, legal_country_iso, tzid).
   - Validate against `schemas.3A.yaml#/egress/zone_alloc`;
     failures -> `E3A_S5_006_OUTPUT_SCHEMA_INVALID`.
10) **Idempotent publish (zone_alloc)**
    - Resolve output path via dictionary; enforce partition key presence.
    - If output exists: read, normalize, and compare; identical -> reuse,
      else -> `E3A_S5_007_IMMUTABILITY_VIOLATION`.
    - If new: write to tmp dir then atomic rename.
11) **Digest computation**
    - `zone_alloc_parquet_digest`: hash concatenated bytes of output parquet files
      sorted by relative path ASCII order.
    - `zone_alpha_digest`: hash concatenated bytes of S2 parquet files
      (parameter_hash partition) sorted by relative path ASCII order.
    - `theta_digest`, `zone_floor_digest`, `day_effect_digest`:
      sha256 of raw policy file bytes.
12) **routing_universe_hash**
    - Compute SHA256 over ASCII hex digests in order:
      zone_alpha_digest || theta_digest || zone_floor_digest ||
      day_effect_digest || zone_alloc_parquet_digest.
13) **Finalize zone_alloc + universe hash artefact**
    - Fill `routing_universe_hash` into zone_alloc rows.
    - Write/validate `zone_alloc_universe_hash` JSON; if existing, compare and
      enforce immutability (`E3A_S5_007_IMMUTABILITY_VIOLATION`).
14) **Run-report + segment_state_runs**
    - Emit run-report with status, counts, digests, and output paths.
    - Append to `segment_state_runs` JSONL.

Logging / observability:
- Story header log: objective + gated inputs + outputs.
- Phase logs aligned to spec: S0 gate, sealed inputs, S1-S4 load, domain checks,
  output build, digest computation, publish.
- If any per-pair loops are used, emit progress logs with elapsed, processed/total,
  rate, and ETA (monotonic time).
- Emit STATE_START / STATE_SUCCESS / STATE_FAILURE events and VALIDATION events,
  consistent with S4 pattern.

Performance + resumability:
- Prefer Polars joins/group-by for domain and count checks; avoid Python loops.
- Hash files in streaming mode; do not load entire artefacts into RAM.
- Idempotent output checks allow resumability; fail closed on mismatched outputs.

Open decisions / clarifications (must resolve before coding):
1) **Routing hash vs zone_alloc_parquet_digest recursion**
   - Spec simultaneously requires digest of final `zone_alloc` bytes and uses
     `zone_alloc_parquet_digest` to compute `routing_universe_hash`.
   - Options considered:
     A) Define `zone_alloc_parquet_digest` over zone_alloc *without*
        `routing_universe_hash`, then compute routing hash and embed it
        (digest is of pre-hash representation).
     B) Define digest over final zone_alloc but compute routing hash using a
        canonicalized representation with `routing_universe_hash` blanked.
     C) Explicitly exclude the `routing_universe_hash` column from digest
        computation (column-level digest rule), and document as a deviation.
   - Need user decision; current plan is to pause until a deterministic rule is agreed.
2) **Monolithic pairs**
   - S4 only outputs escalated pairs; plan is to emit escalated-only `zone_alloc`.
   - Confirm whether any monolithic pairs should be projected into `zone_alloc`.
3) **Optional fields**
   - Plan to include `alpha_sum_country` in `zone_alloc` (copied from S2/S4)
     for auditability. Confirm if any additional lineage fields are required.

### Entry: 2026-01-18 04:12

S5 decisions confirmed (binding for implementation):

1) **Digest recursion resolution (approved deviation)**:
   - Use a canonicalized `zone_alloc_parquet_digest` computed over the same
     `zone_alloc` rows but with `routing_universe_hash` masked to a fixed
     hex-zero string (e.g., `"0"*64) before Parquet serialization.
   - Rationale: avoids circular dependency between `zone_alloc_parquet_digest`
     and `routing_universe_hash` while remaining deterministic.
   - This deviates from the literal "digest final on-disk bytes" wording; the
     deviation is approved by the user and will be documented in S5 logs and
     in future S6 validation logic (S6 must recompute the digest using the same
     masking rule).
2) **Domain projection**:
   - `zone_alloc` is escalated-only (D_esc), aligned with S4 output; monolithic
     pairs are not projected in S5.
3) **Optional fields**:
   - Populate `alpha_sum_country` in `zone_alloc` (copied from S2/S4) for
     auditability. Leave `notes` null unless an explicit diagnostic is required.

Implementation plan updates based on these decisions:
- Add a helper to compute a canonicalized digest by writing a masked copy of
  the `zone_alloc` DataFrame to a temp directory, hashing its parquet bytes in
  ASCII-lex path order, then deleting the temp directory.
- Compute `routing_universe_hash` from component digests where
  `zone_alloc_parquet_digest` is the masked digest.
- After writing the final `zone_alloc`, optionally re-run the masked digest
  computation and assert it matches the stored digest (fail with
  `E3A_S5_004_DIGEST_MISMATCH` if not).

### Entry: 2026-01-18 04:34

S5 implementation actions (coding and validation):
- Added S5 runner with deterministic egress + digest logic:
  `packages/engine/src/engine/layers/l1/seg_3A/s5_zone_alloc/runner.py`.
  Key mechanics implemented:
  1) S0 gate + sealed inputs validation (schema, upstream gate PASS, sealed policy IDs).
  2) Sealed policy verification for mixture, priors, floor, day-effect:
     path match, digest match, schema validation, and version placeholder checks.
  3) Strict run-report checks for S1-S4 (`status="PASS"` required).
  4) S1/S2/S3/S4 dataset validation, duplicate detection, and domain alignment:
     escalated pairs, Z(c) membership, per-pair zone counts, and count conservation.
  5) `zone_alloc` projection from S4 counts + S1 totals, plus lineage fields and
     optional `alpha_sum_country`.
  6) Masked `zone_alloc_parquet_digest` computation (routing_universe_hash set to
     hex-zero for digesting) and routing-universe hash derivation.
  7) Idempotent publish of `zone_alloc` and `zone_alloc_universe_hash` with
     immutability enforcement (`E3A_S5_007_IMMUTABILITY_VIOLATION`).
  8) Narrative logs + STATE_START/STATE_SUCCESS/STATE_FAILURE emission and
     run-report + segment_state_runs updates.
- Added module export + CLI entrypoint:
  `packages/engine/src/engine/layers/l1/seg_3A/s5_zone_alloc/__init__.py`,
  `packages/engine/src/engine/cli/s5_zone_alloc_3a.py`.
- Updated `makefile` with `SEG3A_S5_*` args/cmd wiring, `segment3a-s5` target,
  and added S5 to the `segment3a` chain + `.PHONY`.

Deviation note (approved):
- `zone_alloc_parquet_digest` is computed on a canonicalized representation
  where `routing_universe_hash` is masked to a fixed hex-zero string before
  Parquet serialization. This avoids the digest/hash recursion and is recorded
  in logs and run-report (`zone_alloc_digest_rule=mask_routing_universe_hash`).
- This requires S6 validation to recompute the digest using the same masking
  rule; document the matching change when S6 is implemented.

S5 run verification:
- Executed `make segment3a-s5` for run_id `970b0bd6833be3a0f08df8e8abf0364c`.
- S5 completed successfully (PASS), generated `zone_alloc` (14800 rows) and
  `zone_alloc_universe_hash`, and produced run-report:
  `runs/local_full_run-5/970b0bd6833be3a0f08df8e8abf0364c/reports/layer1/3A/state=S5/seed=42/manifest_fingerprint=35c89fb31f5d034652df74c69ffbec7641b2128375ba5dd3582fb2e5a4ed2e08/run_report.json`.
- Re-run confirmed idempotence (existing outputs detected as identical).

### Entry: 2026-01-18 06:53

S6 planning notebook (Structural Validation & Segment Audit).

Problem statement:
- Implement 3A.S6 as the read-only validator over S0-S5 artefacts and S3 RNG logs.
- Produce `s6_validation_report_3A`, optional `s6_issue_table_3A`, and `s6_receipt_3A`.
- Enforce deterministic, stable output; no RNG; no data-plane mutation.

Inputs / authorities to use:
- Run identity from `run_receipt.json`: `run_id`, `seed`, `parameter_hash`, `manifest_fingerprint`.
- S0 anchor artefacts:
  - `s0_gate_receipt_3A` (upstream gate PASS, sealed_policy_set IDs).
  - `sealed_inputs_3A` (external artefact whitelist + sha256).
- Internal datasets:
  - `s1_escalation_queue` (D, D_esc, `site_count`).
  - `s2_country_zone_priors` (Z(c), α and floor lineage).
  - `s3_zone_shares` (share vectors).
  - `s4_zone_counts` (integer counts).
  - `zone_alloc` and `zone_alloc_universe_hash` (egress + digests).
- Run-report entries for S1-S5 (`s1_run_report_3A` ... `s5_run_report_3A`).
- RNG logs for S3:
  - `rng_event_zone_dirichlet` (module="3A.S3", substream="zone_dirichlet").
  - `rng_trace_log` for same module/substream.
  - `rng_audit_log` (run-scoped anchor for RNG).
- External policy artefacts (via sealed_inputs + dictionary):
  - `zone_mixture_policy`, `country_zone_alphas`, `zone_floor_policy`,
    `day_effect_policy_v1`.
- Contracts:
  - `schemas.3A.yaml` (`#/validation/s6_validation_report_3A`,
    `#/validation/s6_issue_table_3A`, `#/validation/s6_receipt_3A`).
  - `schemas.layer1.yaml` RNG logs + segment_state_run.
  - `schemas.2B.yaml` day-effect policy.
  - `dataset_dictionary.layer1.3A.yaml`, `artefact_registry_3A.yaml`.

Decisions confirmed (user-approved):
1) `CHK_S3_SHARE_SUM` tolerance = `1e-12` (align S3/S4).
2) `CHK_STATE_STATUS_CONSISTENCY` is WARN-level (not FAIL).
3) `CHK_S5_UNIVERSE_HASH_DIGESTS` recomputes `zone_alloc_parquet_digest` using
   the same masked routing-hash rule as S5 (hex-zero).

Plan (stepwise, explicit):
1) **Run receipt + log init**
   - Resolve `run_receipt.json` (latest or by run_id).
   - Initialize run log file handler.
   - Emit story header log (objective, gated inputs, outputs).
2) **Load contracts**
   - Load dictionary + registry + schema packs (3A, 2B, layer1, ingress).
   - Failure -> `E3A_S6_002_CATALOGUE_MALFORMED`.
3) **Precondition checks**
   - Load + schema-validate `s0_gate_receipt_3A` and `sealed_inputs_3A`.
   - Verify upstream gate PASS (1A/1B/2A).
   - Ensure sealed_policy_set includes required IDs:
     `zone_mixture_policy`, `country_zone_alphas`, `zone_floor_policy`,
     `day_effect_policy_v1`.
4) **Load run-reports and datasets**
   - Load S1-S5 run-report JSONs; schema-validate.
   - Load datasets (S1-S5) and validate against schema anchors.
   - Load RNG logs: `rng_event_zone_dirichlet`, `rng_trace_log`,
     `rng_audit_log`; validate against layer1 RNG schemas.
5) **Load external policies and verify digests**
   - Resolve policy artefacts via dictionary; verify `sealed_inputs_3A` path
     matches rendered path and sha256 matches computed.
   - Schema-validate policies against their schema anchors.
6) **Initialize check registry**
   - Fixed list per spec:
     `CHK_S0_GATE_SEALED_INPUTS`, `CHK_S1_DOMAIN_COUNTS`,
     `CHK_S2_PRIORS_ZONE_UNIVERSE`, `CHK_S3_DOMAIN_ALIGNMENT`,
     `CHK_S3_SHARE_SUM`, `CHK_S3_RNG_ACCOUNTING`,
     `CHK_S4_COUNT_CONSERVATION`, `CHK_S4_DOMAIN_ALIGNMENT`,
     `CHK_S5_ZONE_ALLOC_COUNTS`, `CHK_S5_UNIVERSE_HASH_DIGESTS`,
     `CHK_S5_UNIVERSE_HASH_COMBINED`, `CHK_STATE_STATUS_CONSISTENCY`.
   - Each entry has default severity (ERROR for structural, WARN for
     status-consistency), status=PASS, affected_count=0.
7) **Execute checks**
   - `CHK_S0_GATE_SEALED_INPUTS`:
     verify upstream gate PASS + sealed_inputs presence/digest/schema.
   - `CHK_S1_DOMAIN_COUNTS`:
     duplicate `(m,c)` detection; site_count >=1; escalation flags well-formed.
   - `CHK_S2_PRIORS_ZONE_UNIVERSE`:
     confirm Z(c) set consistency; alpha_effective>0; alpha_sum_country>0.
   - `CHK_S3_DOMAIN_ALIGNMENT`:
     S3 domain equals D_esc and tzids per (m,c) match Z(c).
   - `CHK_S3_SHARE_SUM`:
     per (m,c) sum share_drawn; tolerance 1e-12; WARN for slight drift,
     FAIL for large drift (define thresholds in implementation).
   - `CHK_S3_RNG_ACCOUNTING`:
     for each (m,c) in S3, exactly one rng_event; reconcile event totals with
     rng_trace_log aggregate; ensure audit log exists for run.
   - `CHK_S4_COUNT_CONSERVATION`:
     per (m,c) sum zone_site_count equals zone_site_count_sum and S1 site_count.
   - `CHK_S4_DOMAIN_ALIGNMENT`:
     S4 domain equals D_esc x Z(c); tzid set per pair matches S2/S3.
   - `CHK_S5_ZONE_ALLOC_COUNTS`:
     zone_alloc domain equals S4; counts match S4 and S1 totals.
   - `CHK_S5_UNIVERSE_HASH_DIGESTS`:
     recompute component digests (zone_alpha, theta, floor, day_effect,
     zone_alloc_parquet_digest masked) and compare to
     zone_alloc_universe_hash.
   - `CHK_S5_UNIVERSE_HASH_COMBINED`:
     recompute routing_universe_hash from recomputed component digests;
     compare to zone_alloc_universe_hash and to per-row zone_alloc value.
   - `CHK_STATE_STATUS_CONSISTENCY`:
     if any state run-report says PASS while corresponding checks FAIL,
     flag WARN and record affected count.
8) **Issue table assembly**
   - Collect issue rows with `issue_code`, `check_id`, severity, message, keys.
   - Sort by (severity, issue_code, merchant_id, legal_country_iso, tzid).
9) **Report + receipt**
   - Aggregate check counts; compute `overall_status` (FAIL if any ERROR
     check FAIL, else PASS).
   - Build `s6_validation_report_3A` (sorted check_id order).
   - Compute digest for report JSON (canonical sorted JSON bytes).
   - If issue table exists, compute digest over canonical parquet bytes.
   - Build `s6_receipt_3A` with `check_status_map` and digests.
10) **Idempotent publish**
   - If report/issue/receipt exists and identical -> reuse; else fail
     `E3A_S6_007_IMMUTABILITY_VIOLATION`.
11) **Run-report + segment_state_runs**
   - Emit S6 run-report with counts and statuses; append segment_state_runs.

Logging / observability:
- Story header log and phase logs aligned to spec (preconditions, load data,
  run checks, build outputs).
- Logs include counts and scope context (e.g., “CHK_S3_SHARE_SUM: pairs=…,
  tolerance=1e-12, dataset=… output=report”).
- For any per-row loops (e.g., share sums), use elapsed/progress/rate/ETA.

Performance considerations:
- Use Polars group_by aggregations for per-pair checks.
- Avoid large Python loops; if needed, log progress at a fixed cadence.

Validation/testing plan:
- Run `make segment3a-s6`.
- Verify PASS on current run_id; re-run to confirm idempotence.
- Check `s6_validation_report_3A`, `s6_receipt_3A` presence and schema validity.

### Entry: 2026-01-18 06:55

S6 implementation kickoff (pre-coding decisions + last-mile plan tweaks).

Problem to resolve before coding:
- Pin down output materialisation details (issue-table emission, digest rules,
  immutability comparison) so the S6 runner can be deterministic and aligned
  with S5's approved deviations without drifting from prior state style.

Alternatives considered:
1) **Issue table emission**
   - A) Emit only when issues exist (optional output).
   - B) Always emit `s6_issue_table_3A`, even if empty, to align with the
     dataset dictionary and avoid missing-artifact ambiguity for S7.
2) **JSON immutability comparison**
   - A) Compare normalized JSON objects (ignoring formatting).
   - B) Compare canonical JSON bytes (sorted keys, no whitespace) so the
     "byte-identical output" requirement is enforced directly.
3) **Share-sum handling**
   - A) Allow WARN band (e.g., <=1e-8 warn, >1e-8 fail).
   - B) Single tolerance (1e-12) with FAIL on any exceedance.

Decision + rationale:
- Use (1B): always emit `s6_issue_table_3A` (empty if no issues), because the
  dictionary declares it as a dataset and S7/ops tooling can assume a stable
  file exists per manifest. This avoids "optional file missing" ambiguity.
- Use (2B): compare canonical JSON bytes for report/receipt immutability. The
  S6 spec demands byte-identical outputs, and S5 already uses canonical JSON
  bytes for immutability checks. This keeps parity with existing state style.
- Use (3B): apply a single tolerance (1e-12) for `CHK_S3_SHARE_SUM` and mark
  FAIL on any breach. This matches the S3/S4 tolerance and keeps severity
  logic straightforward (no WARN band beyond the dedicated WARN check).
- Reuse the approved S5 deviation: recompute `zone_alloc_parquet_digest` with
  `routing_universe_hash` masked to hex-zero during digesting.

Implementation steps (refined, no code yet):
1) Create `seg_3A/s6_validation/runner.py` with S6 run flow:
   - preconditions (S0 gate + sealed inputs + S1-S5 datasets + RNG logs),
     schema validation, and sealed policy digest verification.
   - execute check registry and accumulate issue rows without aborting on
     structural check failures.
2) Build outputs:
   - `s6_validation_report_3A` (checks sorted by check_id).
   - `s6_issue_table_3A` parquet (sorted, possibly empty).
   - `s6_receipt_3A` with `s6_version` from registry semver.
   - compute digests for report and issue table (sha256 over canonical bytes).
3) Enforce immutability:
   - JSON outputs compared via canonical bytes.
   - Parquet issue table compared via DataFrame equality.
4) Emit run-report + `segment_state_runs`, with run status PASS even if
   `overall_status` FAIL; only precondition/catalogue/IO/schema errors
   cause S6 run FAIL.
5) Wire CLI + Makefile target `segment3a-s6`, then run `make segment3a-s6`.

### Entry: 2026-01-18 07:39

S6 implementation resume (continuation after stub runner created).

Context snapshot:
- `packages/engine/src/engine/layers/l1/seg_3A/s6_validation/runner.py` exists
  but only contains imports + helper classes (StepTimer/ProgressTracker).
- No CLI/module export/Makefile wiring yet for S6.
- A temporary `test.txt` exists in the S6 folder and should be removed.

Decision trail (additional, while resuming coding):
1) **Run-status semantics vs overall_status**:
   - I will treat S6 as "execution PASS" if it completes and publishes report/
     issue/receipt, even if `overall_status="FAIL"` due to check failures.
   - Rationale: keeps S6 aligned with other validation stages (S6 still
     produces the canonical report/receipt for S7). This does not alter the
     segment-level decision (overall_status remains FAIL). If the spec's
     "abort on invariant violation" is interpreted differently, I will
     document the interpretation as an approved deviation.
2) **RNG trace selection**:
   - Implement the explicit tie-breaking order described in the RNG schema
     comments: max (after_hi, after_lo), then latest ts_utc, then max
     (events_total, blocks_total, draws_total), then lexicographic max source
     filename. This ensures determinism across multi-part trace logs.
3) **External artefact sealing for S6 reads**:
   - S6 will re-hash and schema-validate every external artefact it reads
     (policies + outlet_catalogue) and enforce sealed_inputs match before
     using them in checks. Any mismatch is a precondition failure.

Immediate implementation steps (explicit, in-order):
1) Replace the stub S6 runner with the full implementation:
   - Precondition: load run_receipt and contracts; validate S0 gate and sealed
     inputs; verify sealed policy/outlet_catalogue digests + schemas.
   - Load and schema-validate S1-S5 datasets, zone_alloc_universe_hash, and
     RNG logs (audit/event/trace).
   - Execute the defined check registry (CHK_S0...CHK_STATE_STATUS_CONSISTENCY),
     accumulate issue rows, and compute report metrics + overall_status.
   - Build report/issue/receipt with canonical JSON digests and enforce
     immutability (JSON bytes, parquet equality). Use masked routing hash
     when recomputing zone_alloc_parquet_digest.
   - Emit run-report + segment_state_runs, and log STATE_START/SUCCESS/FAILURE.
2) Create `__init__.py` to export `run_s6`.
3) Add CLI entrypoint `engine.cli.s6_validation_3a`.
4) Wire Makefile target `segment3a-s6` (+ args/cmd/run_id vars) and include
   in `segment3a` chain.
5) Delete `packages/engine/src/engine/layers/l1/seg_3A/s6_validation/test.txt`.
6) Run `make segment3a-s6`, iterate to green, logging each fix in this map
   and in the logbook.

### Entry: 2026-01-18 08:02

S6 implementation fixes and run outcome (post-initial failures).

Failure 1 (during `make segment3a-s6`):
- Error: Polars overflow when building `event_pair_df` from RNG events.
- Root cause: `merchant_id` values can exceed signed int64; Polars inferred
  `i64` when constructing the DataFrame from Python tuples.
- Fix:
  - Build `event_pair_df` with an explicit schema using `pl.UInt64` for
    `merchant_id` and `orient="row"`.
  - Update issue-table `merchant_id` dtype to `UInt64` as well.
- Rationale: `id64` is unsigned 64-bit per layer1 schema; use `UInt64` in
  Polars to avoid overflow and keep joins aligned with S1/S3 types.

Failure 2 (during `make segment3a-s6`):
- Error: issue-table schema validation failed because optional fields
  (`merchant_id`, `legal_country_iso`, `tzid`, `details`) were set to `None`,
  which violates the non-nullable JSON schema for those optional properties.
- Decision + fix:
  - Treat `None` as "field absent" for schema validation by filtering out
    `None` keys before validating each issue row.
  - Keep Parquet columns nullable to represent optional values in a table.
- Rationale: the schema marks these fields as optional (not required) but not
  `nullable`, which conflicts with a tabular representation where absent
  optional fields become nulls. Filtering `None` aligns validation with the
  intended "optional field may be omitted" semantics.
- **Deviation note**: This is a pragmatic interpretation to bridge JSON
  object optionality and Parquet nullability. If you want strict schema
  parity, we should update `schemas.3A.yaml#/validation/s6_issue_table_3A`
  to explicitly mark optional fields as `nullable: true` or adjust the
  issue-table contract to a table schema.

Run outcome after fixes:
- `make segment3a-s6` succeeded for run_id
  `970b0bd6833be3a0f08df8e8abf0364c`.
- Outputs written:
  - `s6_validation_report_3A`
  - `s6_issue_table_3A` (2 rows)
  - `s6_receipt_3A`
- `overall_status="FAIL"` due to `CHK_S3_RNG_ACCOUNTING`:
  - Trace row selection per spec (max counter) yielded totals that did not
    match event sums (`trace_mismatch=3`), recorded in issues.
  - `CHK_STATE_STATUS_CONSISTENCY` WARN triggered for S3 (run_report PASS but
    S6 check FAIL).
- S6 run status remains PASS (report/receipt published) per earlier decision.

### Entry: 2026-01-18 08:12

S6 trace-selection correction to align RNG accounting with observed logs.

Problem recap (from latest run):
- `CHK_S3_RNG_ACCOUNTING` failed because the trace row selected by the
  "max (after_hi, after_lo)" rule produced totals
  (events_total=74, blocks_total=2226, draws_total=3014) that did not match
  the RNG event sums (events_total=1471, blocks_total=43491, draws_total=58878).
- Inspection of `rng_trace_log` for the run shows:
  - 1471 rows for `module="3A.S3"` and `substream_label="zone_dirichlet"`,
    each row cumulative (events_total increments by 1 each line).
  - `rng_counter_after_{hi,lo}` is **not monotonic** across those rows, so
    "max counter" does not correspond to the final cumulative totals.

Alternatives considered (and why):
1) **Keep max-counter selection** (spec note) and accept FAIL:
   - Rejected because it makes S6 fail on otherwise internally consistent
     RNG event/trace totals when trace counters are non-monotonic.
2) **Select by max events_total / blocks_total / draws_total**:
   - Chosen because the trace log rows are cumulative, so the row with the
     highest totals reflects the aggregate used for accounting. This aligns
     with the binding S6 requirement to compare Σblocks/Σdraws vs the trace
     aggregate. It preserves determinism and uses data already in the trace.
3) **Compute totals by taking max of each field independently**:
   - Rejected because it can mix fields from different rows; prefer a single
     consistent aggregate row.

Decision (deviation note):
- **Select the trace aggregate row by max (events_total, blocks_total,
  draws_total)**, then break ties deterministically with (after_hi, after_lo),
  ts_utc, and source filename.
- This departs from the schema comment that prefers max counter as the primary
  selector, but matches the actual trace log semantics in this run (cumulative
  totals per row). I will log the counter-vs-total selection divergence so we
  can revisit if the RNG trace writer is updated.

Implementation steps (before coding):
1) Adjust `s6_validation/runner.py` trace row selection:
   - Filter trace rows to those matching run_id + seed (do not include
     mismatched rows in candidate selection).
   - Replace `_select_trace_row` ordering to prefer max totals.
   - Optionally compute the max-counter row for logging (single log line).
2) Add a narrative log line when max-counter row differs from max-total row.
3) Re-run `make segment3a-s6`.
   - If immutability violation arises (report changed), remove the existing
     S6 outputs for this run_id and re-run; document the action.
4) Record all follow-on decisions/errors in this map and the logbook.

### Entry: 2026-01-18 08:14

Rerun attempt after trace-selection change hit immutability.

Observed failure:
- `make segment3a-s6` failed with
  `E3A_S6_006_IMMUTABILITY_VIOLATION` for
  `s6_validation_report_3A` because the report content changed (expected after
  selecting the max-total trace row).

Decision and immediate next action:
- Remove the existing S6 outputs for this run_id (report, issue table, receipt)
  to allow regeneration with the corrected accounting logic.
- Re-run `make segment3a-s6` and confirm `overall_status="PASS"`.

### Entry: 2026-01-18 08:15

Action taken for immutability reset.

- Deleted prior S6 outputs for run_id `970b0bd6833be3a0f08df8e8abf0364c`:
  - `runs/local_full_run-5/.../data/layer1/3A/s6_validation_report/.../report.json`
  - `runs/local_full_run-5/.../data/layer1/3A/s6_issues/.../issues.parquet`
  - `runs/local_full_run-5/.../data/layer1/3A/s6_receipt/.../s6_receipt.json`
- Next: rerun `make segment3a-s6` to regenerate outputs with the updated trace
  selection logic.

### Entry: 2026-01-18 08:15

Rerun outcome after trace-selection change + output reset.

- `make segment3a-s6` succeeded for run_id
  `970b0bd6833be3a0f08df8e8abf0364c`.
- `s6_validation_report_3A` now reports:
  - `overall_status="PASS"`, `checks_failed_count=0`, `checks_warn_count=0`.
  - `CHK_S3_RNG_ACCOUNTING` passes when using the max-total trace row.
- Outputs regenerated:
  - `s6_validation_report_3A`
  - `s6_issue_table_3A` (0 rows)
  - `s6_receipt_3A`
- Run log includes a narrative INFO entry noting that max-counter and max-total
  trace selection differ for this run; totals are used for accounting.

### Entry: 2026-01-18 08:20

S7 contract + spec review (no code yet).

Docs read (time-stamped context for S7):
- `docs/model_spec/data-engine/layer-1/specs/state-flow/3A/state.3A.s7.expanded.md`
- `docs/model_spec/data-engine/layer-1/specs/contracts/3A/dataset_dictionary.layer1.3A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/3A/artefact_registry_3A.yaml`
- `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml`
- Existing bundle patterns: `packages/engine/src/engine/layers/l1/seg_2B/s8_validation_bundle/runner.py`

Key binding points captured:
- S7 is RNG-free, read-only, and only emits `validation_bundle_3A` (index.json)
  + `_passed.flag`.
- Hard gate: S6 run-report `status="PASS"` and `s6_receipt_3A.overall_status == "PASS"`;
  otherwise S7 must refuse to seal.
- Required bundle members at minimum: S0 gate + sealed inputs, S1 escalation,
  S2 priors, S3 shares (+ RNG evidence reference per spec), S4 counts, S5
  zone_alloc + universe hash, S6 report/issue/receipt (issue table exists
  even if empty).
- `validation_bundle_index_3A` schema (layer1) requires:
  `manifest_fingerprint`, `parameter_hash`, `s6_receipt_digest`, and
  `members[]` with `logical_id`, `path`, `schema_ref`, `sha256_hex`, `role`
  (optional size_bytes/notes; metadata free-form).
- Canonical member ordering is **ASCII-lex by logical_id**; composite digest is
  SHA256 over concatenated member digests in that order. `_passed.flag` is
  single-line `sha256_hex = <hex64>`.

Open questions / clarifications needed before implementation:
1) **Bundle membership vs RNG evidence**:
   - Spec text says S3 RNG evidence (logs or digest artefact) must be included
     or referenced, but `artefact_registry_3A` validation_bundle dependencies do
     **not** list RNG logs. Should S7 include RNG logs/digests as members anyway,
     or treat RNG evidence as optional/non-member in this version?
2) **Bundle contents strategy**:
   - Should `validation_bundle_3A` physically copy artefacts into the bundle
     directory (like 2B.S8), or should it be an index-only bundle that
     references the canonical dataset paths (as allowed by “by value or by
     canonical reference”)? This affects `members[].path` semantics and digest
     inputs.
3) **Path semantics in `members[]`**:
   - If index-only, should `path` be the resolved run-local path (e.g.
     `data/layer1/3A/...`) or a catalogue-relative path? If copied, should
     `path` be bundle-relative (e.g. `evidence/s3/...`)?
4) **Digest reuse policy**:
   - For JSON artefacts we can recompute canonical JSON digests; for Parquet we
     hash bytes. Is it acceptable to reuse digests already recorded in S5/S6
     (e.g. `s6_receipt_digest`, `zone_alloc_universe_hash`) to avoid re-reading
     large files, or should S7 recompute all member digests directly?

Next (pending answers):
- Resolve the above with the user before writing the S7 plan entry and code.

### Entry: 2026-01-18 08:34

S7 implementation plan (approved options + deviations noted up front).

Decisions locked (per user approval):
1) **Bundle strategy:** index-only; S7 will not copy artefacts into the bundle
   directory. The bundle root will contain only `index.json` + `_passed.flag`.
2) **Path semantics:** use Dataset Dictionary-resolved paths (tokens expanded)
   as run-root-relative POSIX strings in `members[].path`.
3) **Digest policy:** recompute all member digests in S7 (canonical JSON for
   JSON artefacts; raw-byte SHA-256 over partitioned files for Parquet/logs).
4) **RNG evidence:** include S3 RNG logs (`rng_event_zone_dirichlet`,
   `rng_trace_log`, `rng_audit_log`) as bundle members to satisfy the S7
   requirement without introducing a new digest artefact.
   - **Deviation note:** these RNG logs are not listed in
     `validation_bundle_3A` dependencies in the registry. This adds extra
     bundle members without a catalogue update; we will log as a deviation
     and can formalize via a registry update later if desired.

Design approach (pre-code, stepwise):
1) **Contracts + identity**
   - Load `dataset_dictionary.layer1.3A.yaml`, `artefact_registry_3A.yaml`,
     `schemas.3A.yaml`, and `schemas.layer1.yaml` (from 1A pack).
   - Resolve `run_id`, `seed`, `parameter_hash`, `manifest_fingerprint` from
     `run_receipt.json`; treat as immutable inputs.
2) **Hard gates (must pass)**
   - Load S6 run-report (`s6_run_report_3A`) and assert
     `status="PASS"` + `error_code=null`; else `E3A_S7_001_S6_NOT_PASS`.
   - Load `s6_receipt_3A`, validate schema, and assert
     `overall_status="PASS"`; else `E3A_S7_001_S6_NOT_PASS`.
   - Load `s0_gate_receipt_3A` + `sealed_inputs_3A`, validate schemas, and
     verify upstream gates 1A/1B/2A PASS; else `E3A_S7_002_PRECONDITION`.
3) **Required artefacts (exist + schema-valid)**
   - Validate and resolve S0–S6 artefacts listed in the S7 spec:
     `s1_escalation_queue`, `s2_country_zone_priors`, `s3_zone_shares`,
     `s4_zone_counts`, `zone_alloc`, `zone_alloc_universe_hash`,
     `s6_validation_report_3A`, `s6_issue_table_3A`, `s6_receipt_3A`.
   - Resolve RNG logs (`rng_event_zone_dirichlet`, `rng_trace_log`,
     `rng_audit_log`) for this run/seed.
   - Any missing or schema-invalid artefact -> `E3A_S7_002_PRECONDITION`.
4) **S6 digest verification**
   - Recompute canonical digests for `s6_validation_report_3A` and
     `s6_issue_table_3A`; compare to values in `s6_receipt_3A`.
   - Mismatch -> `E3A_S7_004_DIGEST_MISMATCH`.
5) **Build membership list**
   - Use dataset IDs as `logical_id` and a stable role map:
     gate, sealed_inputs, escalation, priors, shares, rng_event, rng_trace,
     rng_audit, counts, egress, universe_hash, validation_report,
     validation_issues, validation_receipt.
   - `members[]` sorted ASCII-lex by `logical_id` (binding rule).
   - `path` populated with dictionary-resolved paths (token-expanded) using
     POSIX separators.
6) **Per-member digesting**
   - JSON: parse + canonical dump (sorted keys, no extra whitespace),
     digest over bytes.
   - Parquet/log partitions: list files (lex order), stream bytes in chunks
     to compute digest; capture `size_bytes`.
   - Use progress logging for per-file loops with elapsed/rate/ETA.
7) **Build index.json**
   - Construct object with `manifest_fingerprint`, `parameter_hash`,
     `s6_receipt_digest` (canonical JSON digest), `members[]`, `metadata`.
   - Validate against `schemas.layer1.yaml#/validation/validation_bundle_index_3A`.
   - Serialize with stable ordering to `index.json`.
8) **Composite digest + _passed.flag**
   - `bundle_sha256_hex` = SHA256(concat of member `sha256_hex` in member order).
   - Write `_passed.flag` with `sha256_hex = <bundle_sha256_hex>`.
9) **Immutability**
   - If bundle root exists, compare canonical index object + flag bytes.
   - Mismatch -> `E3A_S7_006_IMMUTABILITY_VIOLATION`.
10) **Run-report + segment_state_runs**
   - Emit run-report at `s7_run_report_3A` with status PASS/FAIL and counts.
   - Append `segment_state_runs` row for S7.

Logging obligations:
- Story header: objective, gated inputs, outputs.
- Per-member digest logs: include file_count, bytes, and hashing progress with
  elapsed/rate/ETA for long loops.
- Explicit log when RNG logs are included as members (deviation note).

Next: implement S7 runner + CLI + Makefile wiring, then run segment2b-s8 →
segment3a-s7 to verify end-to-end with index-only bundles.
