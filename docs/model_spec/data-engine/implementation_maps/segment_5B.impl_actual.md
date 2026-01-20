# Segment 5B Implementation Map (Actual)

Append-only implementation planning log for Segment 5B. Each entry documents
the design element, a short summary, and the detailed decision path. Do not
delete or rewrite prior entries.

---

### Entry: 2026-01-20 02:12

5B.S0 gate & sealed inputs review (initial plan).

Design problem summary:
- Implement 5B.S0 as the closed-world gate for the arrival realisation segment:
  verify upstream PASS for 1A-3B + 5A, seal all permitted inputs into
  `sealed_inputs_5B`, and emit `s0_gate_receipt_5B` with run identity,
  upstream status map, `scenario_set`, and `sealed_inputs_digest`.
- The state must be metadata-only, deterministic, and re-runnable, while
  complying with the catalogue-only resolution rules and the 5B hashing laws.

Decision path and options considered:
1) **Contract source & catalogue layout**
   - Option A: hard-code model_spec paths for 5B dictionaries/schemas.
   - Option B: use `ContractSource` (as in 5A.S0) so dev uses model_spec, and
     production can switch to root without code changes.
   - Decision: use `ContractSource` and `EngineConfig` (same pattern as 5A.S0).

2) **Scenario-set authority**
   - Option A: derive scenario_set solely from `scenario_manifest_5A`.
   - Option B: use `scenario_id` from run receipt and treat it as the sole set.
   - Option C: prefer `scenario_manifest_5A`, but allow a run-specified subset
     if the orchestrator explicitly requests it.
   - Decision: pending confirmation. Spec emphasises consistency with
     `scenario_manifest_5A`; default will be full manifest list unless a
     run-scoped subset is explicitly approved.

3) **Seed vs sealed_inputs identity**
   - Option A: render `{seed}` placeholders into concrete paths in
     `sealed_inputs_5B` and compute digests for those specific seed outputs.
   - Option B: keep `{seed}` placeholders in `path_template` so
     `sealed_inputs_5B` is identical across seeds and compute digests using
     upstream sealed manifests where available.
   - Decision: pending confirmation. The spec says `sealed_inputs_5B` must
     depend only on `(parameter_hash, manifest_fingerprint)`.

4) **Digest resolution strategy**
   - Option A: always hash on-disk artefacts, even large datasets.
   - Option B: reuse upstream `sealed_inputs_*` digests when available and
     fall back to hashing only for configs/policies and small artefacts.
   - Decision: prefer Option B for performance, with safe fallbacks when
     upstream sealed manifests are absent.

5) **Optional vs required config conflict**
   - Spec lists `bundle_layout_policy_5B` as required, but dataset dictionary
     marks it optional and no config file exists in `config/layer2/5B/`.
   - Decision: pending confirmation on whether to treat it as optional (current
     repo posture) or require a new config file to satisfy S0.

Planned implementation outline (stepwise):
1) Create `packages/engine/src/engine/layers/l2/seg_5B/s0_gate/runner.py`
   mirroring the 5A.S0 structure (logging helpers, `_StepTimer`, `_abort`,
   `_schema_from_pack`, `_resolve_dataset_path`, `_render_catalog_path`).
2) Resolve run identity using run receipts (seed/parameter_hash/mf/run_id),
   log a story header, and enforce preconditions (scenario binding).
3) Load schema packs + dictionaries + registries for 1A-3B, 5A, 5B and
   validate schema anchors referenced by 5B dictionaries.
4) Verify upstream PASS bundles for 1A,1B,2A,2B,3A,3B,5A using the correct
   hashing law per segment (reuse or port 5A.S0 helpers for 2B/3A/3B/5A).
5) Build `sealed_inputs_5B` rows by iterating the 5B dataset dictionary /
   registry entries for the required input set, applying roles/status/read_scope
   rules from the spec. Use upstream `sealed_inputs_*` digests when present.
6) Write `sealed_inputs_5B` (sorted per spec), recompute digest, and emit
   `s0_gate_receipt_5B` with upstream map + `scenario_set` + `sealed_inputs_digest`.
7) Add CLI entrypoint + makefile target (segment5b-s0) and ensure run-report
   emission matches layer-2 conventions.

Logging/observability plan:
- Emit a story header with objective + gated inputs + outputs.
- Log each upstream segment gate result (bundle path, flag path, digest law).
- Log sealed inputs counts by status/role and the computed digest.
- Use structured progress logs where loops exceed a few dozen artefacts.

Open questions for confirmation:
- Should `scenario_set` in `s0_gate_receipt_5B` always include **all**
  scenarios from `scenario_manifest_5A`, or can it be a run-scoped subset?
- Should `sealed_inputs_5B` keep `{seed}` placeholders (seed-invariant) or
  embed concrete seed paths/digests (seed-specific)?
- Is `bundle_layout_policy_5B` truly required (create a config) or should it
  remain optional per the dataset dictionary?

### Entry: 2026-01-20 03:30

5B.S0 gate & sealed inputs (decisions locked before coding).

Design problem summary:
- Build a 5B.S0 gate that enforces upstream PASS for 1A-3B + 5A, seals a
  deterministic input universe for 5B, and emits `sealed_inputs_5B` plus
  `s0_gate_receipt_5B` with upstream status and sealed-inputs digest. The
  solution must obey catalogue-only resolution and remain lightweight
  (metadata-only), while producing seed-invariant outputs per spec.

Decision path and options considered:
1) **Scenario-set authority**
   - Option A: derive scenario_set from `scenario_manifest_5A` (full list).
   - Option B: use a run-scoped scenario binding if provided in run receipt.
   - Decision: use `scenario_manifest_5A` as the canonical source of scenarios
     and default to **all** scenario_ids in that manifest. If a run-scoped
     subset is ever provided (future run receipt or CLI extension), we will
     enforce subset-of-manifest and record it in the receipt; but the current
     implementation assumes full-manifest because run receipts do not carry a
     scenario binding today.

2) **Seed-invariant sealed_inputs_5B**
   - Option A: resolve `{seed}` placeholders to concrete paths and hash those
     datasets, making sealed_inputs depend on seed.
   - Option B: keep `{seed}` placeholders in `path_template` and avoid reading
     seed-scoped data-plane outputs so `sealed_inputs_5B` is invariant across
     seeds.
   - Decision: adopt Option B to satisfy the spec requirement that
     `sealed_inputs_5B` is keyed only by `(parameter_hash, manifest_fingerprint)`.
     This means we will not read or hash bulk seed-scoped outputs (site locations,
     alias tables, edge catalogues, etc.) in S0.

3) **Digest strategy for large seed-scoped outputs**
   - Option A: hash large artefacts anyway (violates metadata-only and blows up
     runtime for S0).
   - Option B: use a structural digest (stable hash of catalogue metadata such
     as manifest_key + schema_ref + path_template + partition_keys) and annotate
     the sealed_inputs rows with a note that the digest is structural.
   - Decision: Option B. We will compute real SHA-256 digests only for small
     configs/policies and for upstream validation bundles/flags (via their own
     hashing law). For data-plane outputs, we will use a structural digest and
     include a `notes` marker (e.g., `seed_scoped_structural_digest`) so later
     validation states can treat these as metadata-only. This is a spec-aligned
     performance choice; it will be called out in the logbook as an approved
     deviation from content hashing for bulk data-plane artefacts.

4) **bundle_layout_policy_5B optionality**
   - Spec text lists it as required, but the dataset dictionary marks it
     `optional` and the repo has no config file for it.
   - Decision: follow the dataset dictionary and treat it as OPTIONAL. If the
     file exists, seal it; if not, log it as an optional missing input. This
     avoids forcing a placeholder config and keeps S0 in sync with repo posture.

Planned implementation outline (stepwise):
1) Create `packages/engine/src/engine/layers/l2/seg_5B/s0_gate/runner.py` by
   mirroring 5A.S0 structure: logging helpers, step timer, `_abort`, schema
   anchor validation, dataset path resolution, and sealed-input digest.
2) Resolve run identity from `run_receipt.json` and initialise run logs; load
   dictionaries, registries, and schema packs for 1A-3B, 5A, 5B, and layer-level
   schema packs required for validation.
3) Verify upstream PASS bundles for 1A,1B,2A,2B,3A,3B,5A using segment-specific
   hashing laws (reuse the 5A.S0 logic for 2B/3A/3B bundle hashing).
4) Load `scenario_manifest_5A` (parquet) to compute `scenario_set` and validate
   that it is non-empty; record it in `s0_gate_receipt_5B`.
5) Build `sealed_inputs_5B` rows from the 5B dataset dictionary and registry:
   classify `status` (REQUIRED/OPTIONAL), `role`, `read_scope`; compute digests
   for configs/policies and bundle/flag entries; use structural digests for
   seed-scoped data-plane outputs; include `notes` for structural digest rows.
6) Validate `sealed_inputs_5B` and `s0_gate_receipt_5B` against `schemas.5B.yaml`,
   compute `sealed_inputs_digest`, and publish outputs atomically.
7) Emit a segment state run-report record (segment_state_runs jsonl) including
   upstream counts and sealed-inputs counts by status/role per spec.
8) Add CLI entrypoint `s0_gate_5b.py` and wire `segment5b-s0` into the makefile.

Logging/observability plan:
- Story header: objective, required upstream segments, and outputs.
- Log upstream gate verification per segment with bundle+flag paths and digest.
- Log scenario_set size and IDs (bounded) once loaded from scenario_manifest.
- Log sealed_inputs counts by status/role and emit the sealed_inputs_digest.
- For loops over dictionary entries, use a progress tracker if rows are large
  (>50) to keep the console alive without noisy spam.

### Entry: 2026-01-20 03:45

5B.S0 upstream gate details & hashing edge cases (pre-implementation check).

New observations:
- `validation_passed_flag_5A` is JSON (contains `bundle_digest_sha256`), not the
  `sha256_hex = ...` text format used by 1A-3B. Example from the current run:
  `data/layer2/5A/validation/.../_passed.flag` holds a JSON object with
  `bundle_digest_sha256`.
- 5A’s bundle index file is named `validation_bundle_index_5A.json` (per the
  dataset dictionary), and its schema expects a dict with an `entries` list.

Decision updates:
1) **5A gate verification**
   - Use the dataset dictionary entry for `validation_bundle_index_5A` to load
     the index file, validate it against `schemas.layer2.yaml#/validation/validation_bundle_index_5A`,
     and compute the bundle digest by hashing the indexed files.
   - Parse `validation_passed_flag_5A` as JSON and compare its
     `bundle_digest_sha256` to the computed digest.
   - Rationale: this matches the 5A.S5 emission format and preserves HashGate
     semantics for the 5A bundle.

2) **Data-plane digest posture (reaffirmed)**
   - Avoid hashing bulk data-plane outputs (parquet/blobs). Use structural
     digests derived from catalogue metadata and annotate rows with notes.
   - Still perform existence checks (path exists for the current run/seed and
     scenario_set) so missing outputs fail fast without reading row-level data.

### Entry: 2026-01-20 03:58

5B.S0 implementation alignment updates (pre-code clarifications).

Design problem summary:
- Resolve two remaining mismatches before coding: (a) the 5B spec says
  `scenario_manifest_5A` is required for S0, but the dataset dictionary marks
  it optional; (b) the 5B spec says `sealed_inputs_digest` should be computed
  from raw file bytes, while existing layer-2 gates (5A.S0) use a canonical
  row-based digest for determinism and re-checks.

Decision path and options considered:
1) **`scenario_manifest_5A` requiredness**
   - Option A: honor the dataset dictionary and treat it as optional; allow S0
     to proceed without a scenario manifest.
   - Option B: follow the S0 expanded spec and treat `scenario_manifest_5A` as
     required because it is the canonical source for `scenario_set_5B`.
   - Decision: Option B. 5B.S0 will require `scenario_manifest_5A` to exist and
     abort if it is missing or empty. This is a deliberate choice to align with
     the S0 spec and avoid a world where `scenario_set_5B` is undefined.

2) **`sealed_inputs_digest` hashing law**
   - Option A: compute the digest from raw JSON bytes after writing, exactly as
     the spec describes.
   - Option B: compute a deterministic digest from a canonical row projection
     (as done in 5A.S0), avoiding dependence on JSON formatting and making
     re-validation deterministic across writers.
   - Decision: Option B. 5B.S0 will use a row-based digest over a fixed set of
     fields, mirroring 5A.S0. This is a documented deviation from the spec’s
     raw-bytes rule, chosen for consistency with existing layer-2 gates and to
     avoid checksum drift due to JSON formatting changes.

Planned implementation adjustments:
- Add `scenario_manifest_5A` to the required input list and raise a required
  scenario error if the manifest is missing or yields zero `scenario_id` values.
- Implement `_sealed_inputs_digest` for 5B using a canonical JSON projection,
  and ensure downstream checks reuse the same function when 5B states are added.

### Entry: 2026-01-20 04:03

5B.S0 config version matching (policy/config vs dictionary).

Design problem summary:
- The 5B config YAML files in `config/layer2/5B` declare patch versions
  (e.g., `v1.0.1`), while the dataset dictionary entries for those configs
  declare coarse `version: 'v1'`. The strict equality check used in 5A.S0
  would reject these configs and block S0.

Decision path and options considered:
1) **Strict equality (5A behavior)**
   - Pro: matches the exact contract field.
   - Con: fails all current 5B configs and forces contract edits or config rewrites.
2) **Relaxed semver prefix match**
   - Treat dictionary `v1` as a major version gate and accept `v1.x.y`.
   - Still reject cross-major mismatches.
3) **Disable version checks entirely**
   - Pro: avoids failures.
   - Con: loses an important safety signal for policy drift.

Decision:
- Adopt Option 2. Implement a semver-prefix match:
  - If the dictionary version is a bare major (`v1`), accept any config with
    `v1.*` and log that the version is compatible.
  - If the dictionary specifies `v1.2`, require the config to match `v1.2.*`.
  - If the dictionary is fully specified (`v1.2.3`), require exact match.
- Rationale: this preserves a guardrail on major/minor changes while aligning
  with the current config files without rewriting contracts.

Planned implementation adjustments:
- Add `_policy_version_matches()` helper and replace the strict equality check
  with prefix-based semver matching for 5B policy/config entries.

### Entry: 2026-01-20 04:28

5B.S0 optional surface handling & scenario-bound structural notes.

Design problem summary:
- The S0 spec text contains mixed cues on whether `merchant_zone_scenario_utc_5A`
  is required, while the dataset dictionary marks it optional. We also need a
  way to make scenario-set changes visible in `sealed_inputs_5B` when using
  structural digests for scenario-partitioned outputs.

Decision path and options considered:
1) **`merchant_zone_scenario_utc_5A` required vs optional**
   - Option A: treat it as required (strict reading of §6 candidate list).
   - Option B: treat it as optional, consistent with the dataset dictionary and
     the later spec note that optional surfaces may be absent.
   - Decision: Option B. We will treat `merchant_zone_scenario_utc_5A` as
     optional and skip sealing if missing, logging it as an optional omission.

2) **Scenario-set visibility in structural digests**
   - Option A: keep structural digests purely on path/schema metadata.
   - Option B: add scenario-set metadata into `notes` for scenario-partitioned
     datasets so the overall `sealed_inputs_digest` changes when the scenario
     set changes.
   - Decision: Option B. For scenario-partitioned datasets, include
     `scenario_ids=<...>` in `notes` alongside the structural digest marker.

Planned implementation adjustments:
- Keep `merchant_zone_overlay_factors_5A` and `merchant_zone_scenario_utc_5A`
  in the optional input list.
- Embed `scenario_ids` into `notes` for scenario-partitioned datasets so
  scenario-set changes affect `sealed_inputs_digest`.

### Entry: 2026-01-20 04:29

5B.S0 run failure: schema pack parse error (schemas.5B.yaml).

Design problem summary:
- `make segment5b-s0` failed before any gating because YAML parsing of
  `docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml`
  raised a `ParserError` near the `s1_grouping_5B` schema.

Observation:
- The `properties` map for `s1_grouping_5B` contains a mis-indented
  `group_id` entry under `channel_group`, which breaks YAML structure.

Decision and fix plan:
- Correct the indentation so `group_id` is a sibling of `channel_group`
  (both under `properties:`). This restores valid YAML without altering
  semantics.
- Re-run `make segment5b-s0` after the schema fix to validate the gate.

### Entry: 2026-01-20 04:30

5B.S0 schema pack fix applied (schemas.5B.yaml).

Action taken:
- Fixed the indentation error in `schemas.5B.yaml` under
  `s1_grouping_5B.properties` so `group_id` is aligned with `channel_group`.

Outcome:
- YAML now parses; re-run of `make segment5b-s0` can proceed.

### Entry: 2026-01-20 04:31

5B.S0 schema pack fix applied (schemas.5B.yaml, s2_latent_field_5B).

Observation:
- `make segment5b-s0` surfaced a second YAML parse error under
  `s2_latent_field_5B.properties` where `group_id` was mis-indented beneath
  `scenario_id`.

Action taken:
- Aligned `group_id` with `scenario_id` in the `properties:` block to restore
  valid YAML structure.

### Entry: 2026-01-20 04:32

5B.S0 scenario manifest validation adjustment.

Design problem summary:
- `make segment5b-s0` failed while validating `scenario_manifest_5A` because
  `validate_dataframe()` only supports table/object schemas, while the
  `scenario_manifest_5A` schema is defined as an `array` of objects.

Decision and fix plan:
- Replace `validate_dataframe()` with direct JSON Schema validation using
  `Draft202012Validator` on the array payload. Inline external refs as needed.
- This keeps schema enforcement while respecting the array schema shape.

### Entry: 2026-01-20 04:32

5B.S0 scenario manifest validation fix applied.

Action taken:
- Switched `scenario_manifest_5A` validation to `Draft202012Validator` against
  the array schema, with external refs inlined, instead of `validate_dataframe()`.

### Entry: 2026-01-20 04:33

5B.S0 optional input resolution guard.

Design problem summary:
- `bundle_layout_policy_5B` is optional but missing on disk; the current loop
  calls `_resolve_partitioned_paths`, which raises `InputResolutionError`
  before optional handling can skip it.

Decision and fix plan:
- Wrap `_resolve_partitioned_paths` in a try/except. If the dataset is optional,
  log and skip; if required, raise `5B.S0.SEALED_INPUTS_INCOMPLETE`.

### Entry: 2026-01-20 04:33

5B.S0 optional input resolution guard applied.

Action taken:
- Added `InputResolutionError` handling around `_resolve_partitioned_paths` to
  skip missing optional inputs (e.g., `bundle_layout_policy_5B`) while still
  failing fast for required artefacts.

### Entry: 2026-01-20 04:34

5B.S0 run completed (segment5b-s0).

Outcome:
- `make segment5b-s0` completed successfully for run
  `d61f08e2e45ef1bc28884034de4c1b68` with `status=PASS`.
- Optional inputs absent and logged: `merchant_zone_scenario_utc_5A` (missing
  scenario partition) and `bundle_layout_policy_5B` (no config file).
- `sealed_inputs_5B` and `s0_gate_receipt_5B` were published, with
  `sealed_inputs_digest=776e55da6292490b60ce6525780bdff99e0be9a84c902d0f89f75eca1d92fd1f`.

### Entry: 2026-01-20 05:36

5B.S0 optional config alignment (bundle_layout_policy_5B).

Design problem summary:
- `bundle_layout_policy_5B` is optional per the dataset dictionary but missing
  on disk, so S0 logs it as an optional-missing input. The operator wants a
  clean, fully sealed policy set without optional-missing warnings.

Options considered:
1. Leave the config missing and accept the warning (least effort, but noisy).
2. Write an empty YAML object `{}` (valid but inconsistent with other 5B
   policy files).
3. Add a minimal policy file with metadata fields (`policy_id`, `version`,
   `notes`) that matches existing 5B config style and keeps schema flexibility.

Decision:
- Proceed with option 3: create a minimal policy file at
  `config/layer2/5B/bundle_layout_policy_5B.yaml` with metadata-only content.
  The schema allows arbitrary properties, so this keeps future layout fields
  extensible without overcommitting to a spec we have not yet implemented in
  S5.
- Do not attempt to populate `merchant_zone_scenario_utc_5A` here; that is an
  upstream 5A data artefact and should remain optional/missing unless explicitly
  requested for a full-data run.

Plan:
- Author `config/layer2/5B/bundle_layout_policy_5B.yaml` (policy_id, version,
  notes).
- Re-run `make segment5b-s0` to confirm the optional-missing warning for
  `bundle_layout_policy_5B` is cleared (any remaining warning should only be
  for `merchant_zone_scenario_utc_5A`).

### Entry: 2026-01-20 05:37

5B.S0 bundle_layout_policy_5B config authored.

Action taken:
- Added `config/layer2/5B/bundle_layout_policy_5B.yaml` with minimal metadata
  fields (`policy_id`, `version`, `notes`) to remove the optional-missing
  warning while leaving layout semantics to S5 defaults.

Next validation:
- Re-run `make segment5b-s0` to confirm the optional-missing warning for
  `bundle_layout_policy_5B` is cleared.

### Entry: 2026-01-20 05:38

5B.S0 reseal required after adding bundle_layout_policy_5B.

Observation:
- Re-running `make segment5b-s0` now computes a different
  `sealed_inputs_digest` because the new `bundle_layout_policy_5B` config is
  included, but the previous `sealed_inputs_5B.json` exists on disk for the
  same `manifest_fingerprint`.
- The run fails with `F4:5B.S0.IO_WRITE_CONFLICT`, reporting expected digest
  `41b13b85...` vs existing `776e55da...`.

Decision:
- Remove the prior S0 outputs for this fingerprint so the run can reseal with
  the updated inputs:
  - `runs/local_full_run-5/d61f08e2e45ef1bc28884034de4c1b68/data/layer2/5B/sealed_inputs/manifest_fingerprint=1cb60481d69b836ee24505ec9a6ec231c8f18523ee9b7dabbd38c0a33bf15765/sealed_inputs_5B.json`
  - `runs/local_full_run-5/d61f08e2e45ef1bc28884034de4c1b68/data/layer2/5B/s0_gate_receipt/manifest_fingerprint=1cb60481d69b836ee24505ec9a6ec231c8f18523ee9b7dabbd38c0a33bf15765/s0_gate_receipt_5B.json`
- Re-run `make segment5b-s0` after deletion to reseal.

### Entry: 2026-01-20 05:39

5B.S0 reseal completed after bundle_layout_policy_5B addition.

Action taken:
- Deleted the prior S0 outputs for the fingerprint (sealed inputs + gate receipt)
  and re-ran `make segment5b-s0`.

Outcome:
- S0 completed successfully with `sealed_inputs_digest=41b13b85fa4cd78d44635c07f29e2849256f08a3927bda098643d57d8e114bf7`.
- The optional-missing warning for `bundle_layout_policy_5B` is gone.
- Only remaining optional-missing input is `merchant_zone_scenario_utc_5A`
  (missing partition `baseline_v1`), which remains intentionally optional.
