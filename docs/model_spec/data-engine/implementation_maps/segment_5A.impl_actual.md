# Segment 5A Implementation Map (Actual)

Append-only implementation planning log for Segment 5A. Each entry documents
the design element, a short summary, and the detailed decision path. Do not
delete or rewrite prior entries.

---

## S0 - Gate & sealed inputs

### Entry: 2026-01-19 11:23

Context read and pre-implementation planning for 5A.S0.

Files read (expanded spec + contracts + layer-2 schema):
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s0.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s1.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s2.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s3.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s4.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s5.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5A/dataset_dictionary.layer2.5A.yaml`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5A/artefact_registry_5A.yaml`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5A/schemas.5A.yaml`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5A/schemas.layer2.yaml`

Design problem summary:
- Implement 5A.S0 as the Layer-2 gate + sealed input universe for 5A, mirroring
  Layer-1 S0 discipline (strict gate, deterministic sealed inventory, no RNG).
- Verify upstream PASS for 1A-3B by re-checking each segment's validation bundle
  and `_passed.flag` using that segment’s hashing law.
- Build `sealed_inputs_5A` with all required/optional inputs (Layer-1 egresses,
  5A policy packs, and scenario configs) and produce `sealed_inputs_digest`.
- Emit `s0_gate_receipt_5A` containing run identity, upstream gate map, and
  scenario binding; optionally emit `scenario_manifest_5A`.

Key decisions (approved):
1) **Strict gating**: if any upstream bundle/flag is missing or fails its hash
   law, abort and emit no outputs (no “receipt-with-failures” mode).
2) **Scenario manifest**: produce `scenario_manifest_5A` by default when
   scenario configs resolve cleanly, since it is low-cost and aids traceability.
3) **Scenario authority**: derive `scenario_id`/`scenario_version` from
   `scenario_horizon_config_5A`; treat `scenario_metadata` as optional metadata
   for pack IDs if present (schema allows free-form).
4) **Scenario calendar digest**: compute a deterministic digest across all
   scenario calendars for the manifest by hashing the sorted parquet bytes
   (ignore provenance JSONs). This yields a stable single digest for the
   `scenario_calendar_5A` sealed input row without duplicating rows.
5) **Catalogue consistency**: cross-check 5A dictionary entries against
   upstream dictionaries for path/schema_ref alignment, with a known exception
   for `validation_bundle_2B` (5A points at `index.json` while 2B defines the
   directory). This deviation is already approved and logged.
6) **Contracts source**: use `ContractSource(config.contracts_root,
   config.contracts_layout)` so switching from model_spec to root contracts is a
   config flip only (no code change).

Known blockers to expect during first run (do not patch with placeholders):
- `config/layer2/5A/scenario/scenario_metadata.v1.yaml` is missing in-repo.
- `config/layer2/5A/policy/shape_time_grid_policy_5A.v1.yaml` is missing.
- `scenario_calendar_5A` is generated under `config/layer2/5A/scenario/calendar`
  by the current script, while the dictionary expects
  `data/layer2/5A/scenario_calendar/...`; S0 will fail until a proper data
  artefact exists at the contract path.

Implementation plan (stepwise, detail-first):
1) **Module & CLI scaffolding**
   - Create `packages/engine/src/engine/layers/l2/seg_5A/s0_gate/runner.py`
     and `__init__.py` packages for `layers/l2` and `layers/l2/seg_5A`.
   - Add CLI entrypoint `packages/engine/src/engine/cli/s0_gate_5a.py`,
     mirroring Layer-1 CLI patterns.
   - Add Makefile target `segment5a-s0` + args + `.PHONY` entry.

2) **Run identity & logging**
   - Read `run_receipt.json` (via `_resolve_run_receipt`) to capture
     `run_id`, `parameter_hash`, `manifest_fingerprint`, and `seed` (needed for
     Layer-1 egress path tokens).
   - Emit a story header log describing S0 objective, gated inputs, and outputs.

3) **Contracts load + schema validation helpers**
   - Load dataset dictionaries and registries for 1A–3B and 5A; load schema
     packs for 1A–3B, `schemas.layer1.yaml`, `schemas.layer2.yaml`, and
     `schemas.5A.yaml`.
   - Implement `_validate_schema_ref` supporting both layer-1 and layer-2 packs.

4) **Catalogue consistency checks**
   - Cross-check 5A dictionary entries for upstream inputs against upstream
     dictionaries (path and schema_ref).
   - Allow the known `validation_bundle_2B` path deviation and log as WARN.

5) **Upstream gate verification (1A–3B)**
   - For 1A/1B/2A: load bundle root + `index.json`, validate schema, compute
     digest by reading member bytes in ASCII path order; compare to `_passed.flag`.
   - For 2B: read `index.json` (list of entries), compute digest by reading the
     run-root relative paths per the 2B hashing law; compare to `_passed.flag`.
   - For 3A: read bundle index and compute digest via concatenated
     `sha256_hex` values sorted by `logical_id` (index-only law).
   - For 3B: read bundle index members and compute digest by hashing bundle
     member file bytes in ASCII path order.
   - Record `verified_upstream_segments` with status + bundle/flag digests.

6) **Resolve and seal inputs**
   - Build required/optional lists exactly from the S0 spec contract card.
   - Resolve each dataset path via dictionary/registry and `RunPaths` +
     `external_roots` (run-local staged → external roots → error).
   - Validate policy/config YAMLs via schema anchors (no row-level scans).
   - Compute digests:
     - validation bundles/flags: use upstream gate digest.
     - directories: hash all files under the resolved directory.
     - files: SHA-256 of file bytes.
     - `scenario_calendar_5A`: hash the sorted parquet bytes for all
       scenario_ids derived from `scenario_horizon_config_5A`.
   - Construct `sealed_inputs_5A` rows with:
     - `status` (REQUIRED/OPTIONAL), `role`, and `read_scope`.
     - `path_template` = dictionary path template (not resolved path).
     - `source_dictionary` / `source_registry` = 5A contract paths.
   - Deterministically sort rows before hashing or writing.

7) **Compute `sealed_inputs_digest`**
   - Serialize rows to canonical JSON with fixed field order and no whitespace.
   - Hash concatenated row bytes to produce `sealed_inputs_digest`.

8) **Build outputs**
   - `s0_gate_receipt_5A` with `s0_spec_version` (registry semver),
     upstream status map, `scenario_id` (single or list), and
     `sealed_inputs_digest`.
   - `scenario_manifest_5A` with one row per scenario from
     `scenario_horizon_config_5A`.
   - Validate payloads against their schema anchors.

9) **Idempotent write**
   - If outputs already exist and match byte-for-byte, no-op.
   - Otherwise, write atomically using temporary staging directories.

Logging points:
- Story header per spec (objective, gated inputs, outputs).
- Per-segment upstream gate status with digest and hashing law.
- Sealed input resolution summary (counts of required/optional, missing optional).
- Digest computation logs for large assets (scenario calendars if large).

Resumability:
- `s0_gate_receipt_5A` / `sealed_inputs_5A` are immutable; reruns with identical
  inputs no-op; mismatches raise immutability violation.

Performance considerations:
- Avoid any row-level reads of large parquet data; only path existence checks
  and byte-hashing for integrity.

Validation/testing steps:
- `python -m py_compile` for new 5A S0 modules.
- `make segment5a-s0` once required configs are present.

---

### Entry: 2026-01-19 11:58

Additional context review + implementation approach adjustments before coding 5A.S0.

Files read (project context + spec deep-dive):
- `docs/references/closed-world-fraud-enterprise-conceptual-design.md`
- `docs/references/closed-world-synthetic-data-engine-with-realism-conceptual-design.md`
- `docs/model_spec/data-engine/layer-1/narrative/narrative_1A-to-3B.md`
- `docs/model_spec/data-engine/layer-2/narrative/narrative_5A-and-5B.md`
- `docs/model_spec/data-engine/layer-3/narrative/narrative_6A-and-6B.md`
- `docs/model_spec/data-engine/layer-2/specs/state-flow/5A/state.5A.s0.expanded.md`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5A/dataset_dictionary.layer2.5A.yaml`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5A/artefact_registry_5A.yaml`
- `docs/model_spec/data-engine/layer-2/specs/contracts/5A/schemas.5A.yaml`

Design adjustments / decisions (with rationale):
1) **ContractSource needs layer-2 routing**: current `ContractSource` only resolves
   layer-1 paths. For 5A we need `layer-2/specs/contracts/5A/...` (model_spec) and
   a future-ready `contracts/dataset_dictionary/l2/seg_5A/...` (root). I will extend
   `ContractSource` to detect segment prefix and map `5* -> layer-2`, `6* -> layer-3`
   while keeping existing layer-1 behaviour unchanged, so production switching is
   a config flip only (no code change).
2) **File authoring approach**: avoid long PowerShell here-strings to prevent the
   `InvalidFilename: filename or extension is too long` error encountered earlier;
   use `apply_patch` to author the 5A S0 runner and CLI in manageable chunks.
3) **Sealed inputs row construction**: follow 3B S0 style (explicit required/optional
   lists) while still resolving every artefact through dictionary + registry paths
   and schema anchors. This stays compliant with “catalogue-driven discovery” and
   matches the existing implementer style (lists are from the spec contract card).
4) **`read_scope` classification**: use explicit sets to mark row-level inputs
   (e.g., `outlet_catalogue`, `zone_alloc`, `scenario_calendar_5A`, `edge_catalogue_3B`)
   and metadata-only inputs (validation bundles/flags, alias blobs, policy/config
   YAMLs). This aligns with the spec example and prevents later confusion about
   row-level reads.
5) **Scenario calendar digest**: keep the approved “single digest across all
   scenario calendars” approach (sorted scenario_id order, hash file bytes) and
   record it under the single `scenario_calendar_5A` sealed input row.
6) **Idempotency**: if either `sealed_inputs_5A` or `s0_gate_receipt_5A` already
   exists and differs from recomputed content, raise `S0_OUTPUT_CONFLICT`; if
   both exist and match, no-op. Always ensure sealed_inputs lands before receipt.

Implementation steps (concrete):
1) Update `packages/engine/src/engine/contracts/source.py` with layer-aware path
   resolution for dataset dictionaries, registries, and schema packs (model_spec +
   contracts layouts).
2) Implement `packages/engine/src/engine/layers/l2/seg_5A/s0_gate/runner.py`:
   - Run identity + log story header (objective/gated inputs/outputs).
   - Load dictionaries/registries/schemas for 1A-3B + 5A + layer1/layer2 schema packs.
   - Validate upstream gates (1A/1B/2A/2B/3A/3B) using each segment’s hashing law.
   - Resolve + validate policy/config YAMLs (no placeholders); compute digests.
   - Build `sealed_inputs_5A` rows with deterministic ordering and canonical digest.
   - Emit `s0_gate_receipt_5A` and `scenario_manifest_5A` (parquet), schema-validated.
   - Persist outputs with staging and idempotency checks.
3) Add CLI entrypoint `packages/engine/src/engine/cli/s0_gate_5a.py` and makefile
   target `segment5a-s0` (plus args/cmd in the S0 section, plus `.PHONY`).

Logging expectations to enforce:
- Story header log for S0 objective and outputs.
- Per-segment gate verification with digest + hashing law.
- `sealed_inputs_digest` + counts by role + optional-missing list.
- Progress logs for large hashing (scenario calendars).

Risk & edge-case notes:
- Missing `scenario_metadata` and `shape_time_grid_policy_5A` should fail hard
  (no placeholders), per dictionary policy.
- `scenario_calendar_5A` currently generated under config paths; S0 will fail
  until a data artefact exists at the dictionary location.
- Known deviation (`validation_bundle_2B` path points at `index.json` in 5A dictionary)
  will be logged as WARN (approved by user); no other mismatches tolerated.

---

### Entry: 2026-01-19 12:30

Implementation actions + in-flight decisions while coding 5A.S0.

Files updated/created (code + build wiring):
- `packages/engine/src/engine/contracts/source.py`
- `packages/engine/src/engine/layers/l2/seg_5A/s0_gate/runner.py`
- `packages/engine/src/engine/cli/s0_gate_5a.py`
- `makefile`

Decisions made during implementation (with rationale):
1) **ContractSource layer routing**: added segment-prefix routing so `5*` maps
   to `layer-2` and `6*` maps to `layer-3`, with `layer_tag` expansion for both
   model_spec and contracts layouts. This preserves existing layer-1 behaviour
   and keeps the dev→prod contract switch code-free.
2) **Catalogue mismatch tolerance**: explicitly allow `validation_bundle_2B`
   mismatches on `path` *and* `schema_ref` when cross-checking against 2B’s
   dictionary, because 5A uses `index.json` + generic `validation_bundle/index_schema`
   while 2B defines a directory + `validation_bundle_index_2B`. This is the approved
   deviation; any other mismatch remains a hard fail.
3) **`read_scope` mapping**: encoded explicit sets:
   - `METADATA_ONLY` for validation bundles/flags, policy/config YAMLs, alias blobs,
     alias indexes, and hash-only artefacts (e.g., `edge_universe_hash_3B`),
   - `ROW_LEVEL` for merchant/site/zone surfaces and scenario calendar data.
   This matches the S0 spec’s guidance and avoids implying row-level reads where
   none are expected.
4) **Scenario manifest rows**: emit one row per scenario (from
   `scenario_horizon_config_5A.scenarios`) with `scenario_config_ids` derived
   from the sealed scenario config artefacts; this keeps the manifest strictly
   derivable from sealed inputs + S0 receipt.
5) **Idempotency and created_utc**: if S0 outputs already exist, reuse the
   existing receipt’s `created_utc` so byte-comparison succeeds; otherwise
   treat mismatched outputs as `S0_OUTPUT_CONFLICT`.
6) **Patch strategy**: `apply_patch` failed with “filename or extension too long”
   when attempting a single large patch. Switched to incremental patches to
   build the runner file in smaller, deterministic chunks (documented here to
   preserve the reasoning trail).

Validation hooks added:
- JSON schema validation for `s0_gate_receipt_5A`, `sealed_inputs_5A`, and
  `scenario_manifest_5A`.
- Upstream gate hashing laws respected for 1A/1B/2A (index files), 2B (index
  paths relative to run root), 3A (index-only members), and 3B (bundle bytes).

Open risks acknowledged (no placeholder mitigation):
- If `scenario_metadata` or `shape_time_grid_policy_5A` are missing, S0 fails
  with `S0_REQUIRED_SCENARIO_MISSING` / `S0_REQUIRED_POLICY_MISSING` as required.
- If `scenario_calendar_5A` is not present at the contracted `data/` location,
  S0 fails (digest computation needs actual parquet files).

---
