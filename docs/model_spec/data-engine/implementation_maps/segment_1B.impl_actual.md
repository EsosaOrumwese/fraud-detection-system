# segment_1B.impl_actual.md

Append-only implementation planning log for Segment 1B. Each entry documents the
design element, a short summary of the problem, and the detailed plan to resolve
it. Do not delete prior entries.

---

## S0 - Gate-in & Foundations (S0.*)

### Entry: 2026-01-12 20:01

Design element: Segment 1B readiness (expanded spec + contract review)
Summary: Begin 1B with a full read of S0–S9 expanded specs plus 1B contracts to identify gates, sealed inputs (including population raster/HRSL), and any S0 gate-in constraints that affect downstream states.

Plan (before implementation):
1) **Read all 1B expanded state specs in order (S0–S9).**
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s0.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s1.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s2.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s3.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s4.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s5.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s6.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s7.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s8.expanded.md`
   - `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s9.expanded.md`

2) **Review 1B contract authorities and registry.**
   - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml`
   - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/artefact_registry_1B.yaml`
   - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml`
   - Confirm all `$ref` anchors for 1B tables and validation bundle shapes.

3) **Identify sealed inputs and external data risk.**
   - Pay special attention to population raster / HRSL‑style inputs and world polygons.
   - Verify which S0‑sealed inputs are fingerprint-scoped vs parameter-scoped so parameter_hash changes do not silently invalidate upstream references.

4) **Record a detailed pre‑implementation plan per state.**
   - After reading, add a detailed entry under each state section with the planned data flow, gates, RNG envelope rules, writer sort, and failure posture.

### Entry: 2026-01-12 20:27

Design element: S0 sealed-input availability check (pre-implementation)
Summary: Verified that the sealed reference inputs listed in the 1B dictionary are present locally so S0 can seal them without blocking on missing assets.

Verified paths:
- `reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet`
- `reference/spatial/world_countries/2024/world_countries.parquet`
- `reference/spatial/population/2025/population.tif` (population raster / HRSL-style prior)
- `reference/spatial/tz_world/2025a/tz_world.parquet`

### Entry: 2026-01-13 00:03

Design element: S0 gate verification + sealed_inputs_1B + s0_gate_receipt_1B (full pre-implementation plan)
Summary: Completed the full 1B expanded spec read (S0-S9) and contract review (dictionary, registry, schema). Capturing the detailed S0 implementation plan with deterministic gating, sealed input hashing, and audit-grade logging before touching code.

Plan (before implementation, detailed and explicit):
1) Identity resolution and config inputs (pre-gate).
   - Resolve `manifest_fingerprint` as the primary identity for S0 (fingerprint-scoped outputs only).
   - Decide the sources for `seed` and `parameter_hash` needed to read `outlet_catalogue` and pin `s3_candidate_set`.
     - Primary option: read `parameter_hash_resolved.json` from the 1A validation bundle after locating the bundle root.
     - Secondary check: if a run receipt exists for the current run, verify it matches the bundle value and use it for `seed`.
     - If `seed` cannot be derived from bundle metadata, fall back to run receipt/config (documented; no hard-coded paths).
   - Capture the resolved tokens in logs before any data read so the run is auditable.

2) Gate verification (1A bundle + passed flag).
   - Resolve the 1A validation bundle path via the Dataset Dictionary using `manifest_fingerprint`.
   - Load `index.json` and validate its shape against the 1A bundle index schema (schemas.1A.yaml#/validation/validation_bundle_index_1A).
   - Build the ASCII-lex order over `index.path` values and compute SHA-256 over the concatenated raw bytes of those files (exclude `_passed.flag`).
   - Read `_passed.flag`, assert exact format `sha256_hex = <hex64>`, and compare to the recomputed hash.
   - If any mismatch, abort S0 and write no outputs (no receipt, no sealed_inputs_1B).

3) Post-PASS checks and read authorization (minimal, deterministic).
   - Only after PASS, resolve `outlet_catalogue` via the Dictionary and validate path-embed equality:
     - `row.manifest_fingerprint == manifest_fingerprint` (path token).
     - If `global_seed` is present, `row.global_seed == seed`.
   - Use streaming reads to avoid loading the entire parquet into memory; log progress (rows scanned, rate, elapsed).
   - Do not infer or encode cross-country order (the only authority remains 1A s3_candidate_set).

4) Build sealed_inputs_1B inventory (authoritative asset list).
   - Required assets to include (per S0 spec): `outlet_catalogue`, `s3_candidate_set`, `iso3166_canonical_2024`, `world_countries`, `population_raster_2025`, `tz_world_2025a`.
   - Consider including `validation_bundle_1A` and `validation_passed_flag_1A` for completeness even if not explicitly required; decide before coding and document the choice.
   - For each asset: resolve path and partition keys via Dictionary, capture `schema_ref`, and compute deterministic `sha256_hex`.
   - Ensure `sealed_inputs_1B` includes `schema_ref` even though the schema marks it optional; the S0 spec treats it as required.

5) Digest strategy (performance-sensitive).
   - For file assets (ISO parquet, world_countries parquet, tz_world parquet, population.tif), compute SHA-256 by streaming (no full file load).
   - For directory-style datasets (e.g., outlet_catalogue or s3_candidate_set partitions), decide on a stable digest strategy:
     - Option A: reuse `egress_checksums.json` from the 1A validation bundle for outlet_catalogue to avoid rescanning large partitions.
     - Option B: compute composite digest by hashing all files under the partition in ASCII-lex relative-path order.
   - Record the chosen strategy and rationale before coding (trade-off: correctness proof vs runtime cost).

6) Write S0 outputs (fingerprint-scoped, atomic, immutable).
   - `s0_gate_receipt_1B` fields: `manifest_fingerprint`, `validation_bundle_path`, `flag_sha256_hex`, `verified_at_utc`, and `sealed_inputs[]` (id + partition + schema_ref).
   - `sealed_inputs_1B`: list of asset records sorted by `(asset_id, path)` with `asset_id`, `version_tag`, `sha256_hex`, `path`, `partition`, `schema_ref`.
   - Stage to temp dir, fsync, then atomic move into the fingerprint partition path; if target exists, require byte-identical content.

7) Logging and auditability (per AGENTS.md).
   - Emit step-by-step logs: bundle validation start/end, number of bundle files hashed, digest timing, outlet_catalogue path-embed scan progress, and sealed_inputs emission.
   - For long hashing/scan loops, log elapsed time, rate, and ETA to avoid silent hangs.
   - Record any deviations or decisions in the logbook and append them here before code changes.

Open questions / contract gaps to resolve before coding:
- Dictionary vs spec license mismatch: `world_countries` is Public-Domain in the dictionary but ODbL-1.0 in S1 spec. Clarify which license to treat as authoritative in sealed_inputs (even though sealed_inputs does not store license, this is a governance mismatch).
- `tz_world_2025a` shows `consumed_by: []` in the dictionary, yet S0 spec requires sealing it. Decide whether to update dictionary or accept sealing despite `consumed_by` being empty.
- S0 receipt `sealed_inputs` example uses partition key name `fingerprint`, while dictionary uses `manifest_fingerprint`. Use dictionary naming for consistency; confirm if any downstream expects the shorter label.
- Digesting large partitioned datasets: confirm whether using 1A bundle `egress_checksums.json` is acceptable for `outlet_catalogue` hashing, or if S0 must recompute composite hashes itself.

---

### Entry: 2026-01-13 00:25

Design element: S0 contract gaps resolved (authoritative choices for gate + sealed inputs)
Summary: Resolved the open contract questions for S0 so the implementation can proceed with deterministic, spec-consistent sealing and logging.

Decisions (with rationale and required updates before coding):
1) **License authority for `world_countries` → Public-Domain (dictionary is authoritative).**
   - Rationale: the dataset dictionary is the contract authority for asset governance; S0 sealing must follow the dictionary even if the S1 spec text diverges.
   - Required updates: change the license label in `state.1B.s1.expanded.md` and its listed references to align with the dictionary.

2) **`tz_world_2025a` `consumed_by` → add `1B`.**
   - Rationale: S0 requires sealing `tz_world_2025a`, so the dictionary must reflect that it is consumed by 1B; otherwise gating conflicts with the contract authority.
   - Required updates: update `dataset_dictionary.layer1.1B.yaml` so `tz_world_2025a` includes `1B` in `consumed_by`.

3) **Receipt partition key naming → use `manifest_fingerprint`.**
   - Rationale: dictionary and existing 1A conventions already use `manifest_fingerprint`; keeping a single key name avoids downstream ambiguity and prevents accidental partition mismatches.
   - Implementation impact: `s0_gate_receipt_1B` and any sealed_inputs paths use `manifest_fingerprint` as the partition token.

4) **Digest strategy for `outlet_catalogue` → reuse 1A `egress_checksums.json` (when bundle matches run identity).**
   - Rationale: outlet_catalogue is potentially large; reusing the 1A egress checksums preserves determinism and avoids expensive re-hashing while still verifying integrity.
   - Guardrails: only reuse when the 1A bundle `manifest_fingerprint` and `global_seed` match S0’s resolved values; otherwise fall back to composite file hashing.

5) **Sealed inputs include gate artifacts: `validation_bundle_1A` + `_passed.flag`.**
   - Rationale: S0 gating is authoritative; including these artifacts in `sealed_inputs_1B` captures the exact upstream gate state and improves reproducibility.
   - Implementation impact: add both assets to `sealed_inputs_1B` with their own hashes, partitions, and schema_refs (if applicable).

Planned order of operations (to enforce these decisions):
- Update contract/spec files to reflect decisions 1 and 2 before writing code.
- Encode decisions 3-5 directly in the S0 runner logic and receipt writer.
- Log these decisions and any further deviations in the logbook and here before each coding step.

### Entry: 2026-01-13 00:28

Design element: Contract alignment updates (pre-code)
Summary: Applied the agreed contract corrections so S0 can rely on the Dictionary/Spec without ambiguity.

Actions taken (pre-code, deterministic alignment):
1) **Updated S1 expanded spec to match dictionary licence for `world_countries`.**
   - Changed `world_countries` licence references from **ODbL-1.0** to **Public-Domain** in `state.1B.s1.expanded.md`, including the licence summary list.

2) **Updated 1B Dictionary to reflect `tz_world_2025a` consumption by 1B.**
   - `consumed_by` now includes `[1B]`, and the description now states it is sealed by 1B.S0.

Rationale:
- Keeps the S0 sealing requirements and the downstream S1 references aligned with the Dictionary authority, avoiding licence or consumed_by mismatches before implementation.

### Entry: 2026-01-13 00:34

Design element: S0 implementation design details (pre-code)
Summary: Finalised the concrete implementation approach for S0 gating, run identity resolution, sealed_inputs hashing, and schema validation before touching code.

Implementation decisions (pre-code, explicit):
1) **Run identity source (seed/parameter_hash/manifest_fingerprint/run_id).**
   - Primary source: `run_receipt.json` under the selected run root (latest by mtime if `--run-id` not supplied).
   - Secondary validation: `parameter_hash_resolved.json` and `manifest_fingerprint_resolved.json` inside the 1A validation bundle must match the run_receipt values; mismatch is a hard fail.
   - Rationale: keeps 1B aligned with the already-established run lineage and avoids divergent identities when resuming.

2) **Gate validation flow.**
   - Use the dictionary-resolved `validation_bundle_1A` path and validate `index.json` against `schemas.1A.yaml#/validation/validation_bundle_index_1A`.
   - Compute the bundle hash by streaming bytes of each `index.path` entry in ASCII-lex order (flag excluded) to avoid loading large files into RAM.
   - Validate `_passed.flag` format and match against computed hash before any `outlet_catalogue` read.

3) **Outlet catalogue lineage check (path-embed parity).**
   - Use row-group scanning (pyarrow if available; otherwise Polars streaming) to validate `manifest_fingerprint` matches the path token and `global_seed` (if present) equals `seed`.
   - Log progress with elapsed/rate/ETA per row-group to satisfy live monitoring requirements.

4) **Sealed input digest strategy.**
   - `outlet_catalogue`: reuse `egress_checksums.json` composite hash when the bundle manifest_fingerprint + seed match the run identity; fallback to streaming composite hash over the parquet files (ASCII-lex relative paths).
   - `s3_candidate_set`: always compute a composite hash by streaming all parquet files under the partition in ASCII-lex relative path order.
   - Reference files (`iso3166_canonical_2024`, `world_countries`, `population_raster_2025`, `tz_world_2025a`): hash file bytes with `sha256_file` (streaming).
   - Gate artifacts (`validation_bundle_1A`, `_passed.flag`): use the computed bundle hash for the bundle directory and file hash for `_passed.flag`.

5) **Receipt + sealed_inputs validation.**
   - Validate `s0_gate_receipt_1B` and `sealed_inputs_1B` via JSON Schema (`schemas.1B.yaml`) before publishing.
   - Any schema error triggers `E_RECEIPT_SCHEMA_INVALID` and aborts publish.

6) **Output paths + atomic publish.**
   - Use Dictionary path templates and `manifest_fingerprint` partition for `s0_gate_receipt_1B` and `sealed_inputs_1B`.
   - Write to a temporary directory under the run root, fsync, then atomic rename; if a partition already exists with differing bytes, raise `E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL`.

Open implementation checks to log during coding:
- If pyarrow is unavailable, document the fallback path (Polars streaming) and its performance impact.
- If any dictionary entry lacks a licence/retention value, fail with a dictionary resolution error and record which ID is missing governance metadata.

### Entry: 2026-01-13 00:48

Design element: S0 implementation (runner + CLI + Makefile wiring)
Summary: Implemented the initial S0 gate runner, CLI entry-point, and a Makefile target to execute S0 in isolation.

Actions taken:
1) **Created Segment 1B S0 module scaffold.**
   - Added `packages/engine/src/engine/layers/l1/seg_1B/__init__.py` and `seg_1B/s0_gate/__init__.py`.

2) **Implemented `S0` gate runner.**
   - Added `packages/engine/src/engine/layers/l1/seg_1B/s0_gate/runner.py` with:
     - run_receipt resolution (latest by mtime if `--run-id` absent),
     - validation bundle gate verification (`index.json` + `_passed.flag`),
     - identity cross-check against bundle-resolved parameters,
     - outlet_catalogue path-embed parity scan (pyarrow row-group; Polars fallback),
     - sealed_inputs_1B hashing rules (bundle hash, outlet_catalogue digest reuse, composite hashes),
     - schema validation for `s0_gate_receipt_1B` and `sealed_inputs_1B`,
     - atomic publish with immutability guard.

3) **Added CLI entry-point for S0.**
   - Added `packages/engine/src/engine/cli/s0_gate_1b.py` to wire contracts layout/root, runs root, external roots, and optional run_id selection.

4) **Added Makefile target for S0.**
   - Added `SEG1B_S0_ARGS`/`SEG1B_S0_CMD` and target `segment1b-s0` to run the new CLI.

Notes to verify during first run:
- Confirm the outlet_catalogue scan path and global_seed checks behave correctly with real data.
- Confirm receipt/inputs JSON validates against `schemas.1B.yaml`.
- Confirm run log file is created under the active run_id.

### Entry: 2026-01-13 00:49

Design element: S0 run fix-up (schema pack resolution)
Summary: First S0 run failed on ingress schema pack resolution; corrected the schema pack kind to the layer-wide ingress filename.

Observed failure:
- `ContractError: Missing contract file ... schemas.ingress.yaml` when loading `load_schema_pack(source, "1A", "ingress")`.

Resolution:
- Switched ingress schema loading to `load_schema_pack(source, "1A", "ingress.layer1")`, matching the file name `schemas.ingress.layer1.yaml`.

Next step:
- Re-run `make segment1b-s0` to validate the gate flow and adjust any further issues.

### Entry: 2026-01-13 00:51

Design element: S0 receipt validation + green run
Summary: The first S0 run reached receipt validation and failed due to the JSON schema adapter not supporting `array` items of type `object`; implemented a local row-schema conversion for the receipt and re-ran S0 to green.

Observed failure:
- `ContractError: Unsupported array item type 'object'` raised while validating `s0_gate_receipt_1B` with the generic JSON schema adapter.

Resolution:
- Implemented `_table_row_schema` + `_column_schema` in `seg_1B/s0_gate/runner.py` to handle array-of-object columns.
- Validated `s0_gate_receipt_1B` with `Draft202012Validator` using the custom row schema; kept `sealed_inputs_1B` validation via `_validate_payload`.

Run outcome:
- `make segment1b-s0` completed successfully.
- `s0_gate_receipt_1B` and `sealed_inputs_1B` published under the current run_id/manifest_fingerprint.
- Logs show PASS gate verification, outlet_catalogue path-embed parity, and digest emission (including reuse of `egress_checksums.json`).

### Entry: 2026-01-13 00:52

Design element: Licence-map coverage check (spec gap to resolve)
Summary: S0 spec §14.2 requires verifying sealed-input licences are covered by the governance `license_map`, but the 1B Dictionary lacks a `license_map` entry, so there is no contract-authoritative path to resolve.

Implication:
- Implementing the licence coverage check would require adding a Dictionary entry for `license_map` (or equivalent), otherwise S0 would violate the "no literal paths" rule.

Next decision needed:
- Add `license_map` (and any LICENSES/ path) to `dataset_dictionary.layer1.1B.yaml` and wire a minimal presence check in S0, **or** explicitly defer/relax this requirement in the spec.

### Entry: 2026-01-13 00:57

Design element: Licence-map addition (user instruction)
Summary: User approved adding `license_map` to the 1B Dictionary and wiring S0 to verify it exists and include its hash in `sealed_inputs_1B`.

Planned changes (before code edits):
1) **Dictionary update:** add `license_map` to `dataset_dictionary.layer1.1B.yaml` with path `licenses/license_map.yaml`, schema_ref `schemas.layer1.yaml#/governance/license_map`, and governance metadata (retention/licence).
2) **S0 runner update:** include `license_map` in required IDs, resolve via Dictionary, hash with `sha256_file`, and add to `sealed_inputs_1B`.
3) **Schema anchor resolution:** load `schemas.layer1.yaml` for 1B S0 and extend schema_ref validation to allow `schemas.layer1.yaml#...`.

### Entry: 2026-01-13 00:58

Design element: Licence-map wiring completed
Summary: Added `license_map` to the 1B Dictionary and updated S0 to validate its schema anchor and seal it in `sealed_inputs_1B`.

Actions taken:
1) **Dictionary entry added.**
   - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml` now includes `license_map` (path `licenses/license_map.yaml`, schema_ref `schemas.layer1.yaml#/governance/license_map`, retention/licence populated).

2) **S0 runner updated.**
   - Loads `schemas.layer1.yaml` and accepts `schemas.layer1.yaml#...` anchors during schema_ref validation.
   - Adds `license_map` to the required sealed inputs list and hashes it via `sha256_file`.

Next step:
- Re-run `make segment1b-s0` to confirm `license_map` is included and no schema/lookup errors are triggered.

### Entry: 2026-01-13 00:59

Design element: S0 rerun failure after licence-map addition
Summary: Re-running S0 after adding `license_map` surfaced two issues: a logging format mismatch and immutable partition enforcement due to previously written outputs.

Observed issues:
1) **Logging format error** on the contracts summary log (too many args for the format string).
2) **Immutable partition conflict** (`E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL`) when writing `sealed_inputs_1B` because the prior S0 outputs (without license_map) already exist under the same manifest_fingerprint.

Planned resolution:
- Fix the logger format string to include the extra schema path.
- Decide how to handle the immutable partition conflict (delete prior S0 outputs for this fingerprint or create a new run_id/fingerprint).

### Entry: 2026-01-13 01:00

Design element: Logger format fix
Summary: Fixed the contract-summary log format string to match the number of schema path arguments after adding schema_layer1.

Action taken:
- Updated the logger format string in `seg_1B/s0_gate/runner.py` to accept four schema paths (1B, 1A, layer1, ingress).

## S1 - Tile Universe (S1.*)

## S2 - Tile Weights (S2.*)

## S3 - Requirements (S3.*)

## S4 - Allocation Plan (S4.*)

## S5 - Site-to-Tile Assignment RNG (S5.*)

## S6 - In-Cell Jitter RNG (S6.*)

## S7 - Site Synthesis (S7.*)

## S8 - Egress Site Locations (S8.*)

## S9 - Validation Bundle & Gate (S9.*)
