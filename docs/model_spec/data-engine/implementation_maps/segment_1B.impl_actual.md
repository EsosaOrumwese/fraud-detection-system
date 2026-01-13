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

### Entry: 2026-01-13 03:22

Design element: S0 gate dependency staging for a fresh run_id
Summary: A fresh run_id was created to reseal updated `world_countries`, but the new run folder does not contain the 1A outputs that S0 requires (`validation_bundle_1A`, `_passed.flag`, `outlet_catalogue`, `s3_candidate_set`). S0 aborts with `E_BUNDLE_MISSING` because the validation bundle path resolves under the new run root and is empty.

Plan (before action, detailed):
1) **Identify a source run that already completed 1A with the same identity.**
   - Choose the latest run folder that contains `data/layer1/1A/validation`, `outlet_catalogue`, and `s3_candidate_set`.
   - Verify the source `run_receipt.json` matches the new run on `manifest_fingerprint`, `parameter_hash`, and `seed` so the 1A outputs are identity-compatible.
   - If any mismatch is found, stop and request a new 1A run rather than copying incompatible outputs.

2) **Stage the minimum required 1A outputs into the new run root.**
   - Copy the full directories:
     - `data/layer1/1A/validation/manifest_fingerprint=...` (includes `_passed.flag`, `index.json`, `egress_checksums.json`).
     - `data/layer1/1A/outlet_catalogue/seed=.../manifest_fingerprint=...`.
     - `data/layer1/1A/s3_candidate_set/parameter_hash=...`.
   - Preserve directory names and tokens so Dictionary path resolution stays deterministic.
   - Do not alter files; treat the copy as a shallow staging action for S0 gate checks.

3) **Re-run S0 gate and confirm sealing.**
   - Run `make segment1b-s0 RUN_ID=<new_run_id>` and confirm the gate validates the copied bundle, verifies `_passed.flag`, and seals `world_countries` and other sealed inputs under the new run_id.
   - If S0 reports any mismatch (e.g., manifest_fingerprint parity in outlet_catalogue), stop and re-evaluate the source run compatibility.

4) **Proceed to S1 only after S0 is green.**
   - Run `make segment1b-s1 RUN_ID=<new_run_id>` and inspect logs for raster/vector performance and validation errors.
   - Record any additional fixes in this log before code changes.

### Entry: 2026-01-13 03:24

Design element: S0 gate dependency staging completed
Summary: Staged the required 1A outputs into the new run root and re-ran S0 gate successfully for run_id `d12d2f6268a74b2988524e98d82315f9`.

Actions taken:
1) **Compatibility verification.**
   - Confirmed source run `559b467dedd77fa576b488f92583d513` matches the new run on `manifest_fingerprint=374b49f7e1cf0e4a526a3396e62382cd171de26015c12ce7714d2a4db1fbfec6`, `parameter_hash=ceedfd1785fe0a71e11e5c3ca1d348f544535e303b99b9cb90d550fc2bf921d5`, and `seed=42`.

2) **Staged 1A outputs (copy only, no mutation).**
   - Copied:
     - `data/layer1/1A/validation/manifest_fingerprint=374b49f7e1cf0e4a526a3396e62382cd171de26015c12ce7714d2a4db1fbfec6`
     - `data/layer1/1A/outlet_catalogue/seed=42/manifest_fingerprint=374b49f7e1cf0e4a526a3396e62382cd171de26015c12ce7714d2a4db1fbfec6`
     - `data/layer1/1A/s3_candidate_set/parameter_hash=ceedfd1785fe0a71e11e5c3ca1d348f544535e303b99b9cb90d550fc2bf921d5`
   - Ensured directory tokens stayed unchanged so Dictionary path resolution remains deterministic.

3) **S0 gate rerun.**
   - `make segment1b-s0 RUN_ID=d12d2f6268a74b2988524e98d82315f9` passed:
     - validation bundle hash verified and `_passed.flag` confirmed,
     - outlet_catalogue parity checks completed,
     - `sealed_inputs_1B` and `s0_gate_receipt_1B` published under the new run_id.

### Entry: 2026-01-13 03:30

Design element: S0 reseal after world_countries repair
Summary: After repairing invalid geometries in `world_countries`, created a new run_id and re-sealed S0 so the updated hash is captured in `sealed_inputs_1B`.

Actions taken:
1) **New run_id created.**
   - `869381446fd74b49bd7f7a4735ab873f` with a cloned `run_receipt.json` (updated `run_id` + `created_utc`).

2) **Staged 1A outputs.**
   - Copied `validation`, `outlet_catalogue`, and `s3_candidate_set` from the compatible 1A run into the new run root.

3) **S0 gate rerun.**
   - `make segment1b-s0 RUN_ID=869381446fd74b49bd7f7a4735ab873f` passed and published `sealed_inputs_1B` + `s0_gate_receipt_1B`.

## S1 - Tile Universe (S1.*)

### Entry: 2026-01-13 01:24

Design element: S1 tile_index + tile_bounds (contract review + pre-implementation plan)
Summary: Reviewed S1 expanded spec plus 1B dictionary/registry/schema anchors for `tile_index`, `tile_bounds`, and `s1_run_report`. Capturing the detailed, stepwise plan for deterministic tile enumeration, geometry predicates, and PAT observability before touching code.

Plan (before implementation, detailed):
1) **Resolve run identity + sealed inputs (no 1A egress).**
   - Load `run_receipt.json` (latest by mtime if no run_id provided) and require `parameter_hash`; read `manifest_fingerprint` only to locate `sealed_inputs_1B`.
   - Resolve `sealed_inputs_1B` via Dictionary path (`data/layer1/1B/sealed_inputs/manifest_fingerprint=.../sealed_inputs_1B.json`).
   - Confirm `iso3166_canonical_2024`, `world_countries`, and `population_raster_2025` appear in `sealed_inputs_1B` for the manifest_fingerprint (spec §4.0; missing ⇒ abort).
   - Resolve actual input paths via the Dictionary (no literal paths), then cross-check that the sealed_inputs path tokens match the resolved Dictionary paths and the on-disk files exist. (Optional: verify SHA-256 from sealed_inputs if cost is acceptable.)
   - Explicitly **do not** read any 1A egress or `tz_world_2025a` (spec §4.4, §5.3).

2) **Resolve output contracts + partition law.**
   - `tile_index` path `data/layer1/1B/tile_index/parameter_hash={parameter_hash}/` (PK `[country_iso,tile_id]`, sort `[country_iso,tile_id]`).
   - `tile_bounds` path `data/layer1/1B/tile_bounds/parameter_hash={parameter_hash}/` (same PK/sort).
   - `s1_run_report` path `reports/layer1/1B/state=S1/parameter_hash={parameter_hash}/s1_run_report.json` (schema: `schemas.1B.yaml#/control/s1_run_report`).
   - All outputs must be staged and atomically moved; re-publish to existing partitions must be byte-identical or fail (immutability).

3) **Predicate selection (inclusion_rule).**
   - Allowed predicates: `"center"` (default) and `"any_overlap"` (schema enum, spec §6.2).
   - Record the predicate used per-row in `tile_index.inclusion_rule` (required by schema) and in the run report (`predicate` field).
   - Decide how the predicate is configured: CLI flag or policy config; default `"center"` if unspecified. (Open question below.)

4) **Raster grid + tile identity (deterministic geometry only).**
   - Open `population_raster_2025` with rasterio; read grid dimensions (`nrows`, `ncols`) and affine transform.
   - Compute `tile_id = r * ncols + c` with zero-based row/col (spec §6.1/§A.5).
   - Derive centroids and bounds from the affine transform in WGS84 (no reprojection). If rotation terms exist, compute all four corners and use min/max for bounds.
   - Normalise longitudes to [-180,+180] and enforce centroid bounds; any out-of-range ⇒ `E004_BOUNDS` (spec §8/§12).

5) **Country geometry handling (world_countries).**
   - Load `world_countries` as the sole geometry authority; join by ISO2 key from `iso3166_canonical_2024`.
   - Validate geometry health: if a country geometry is invalid/topologically broken and cannot be used for point-in-polygon, **fail with `E001_GEO_INVALID`** (no implicit repairs).
   - Handle holes as area removal; multipolygons are unioned. Boundary policy: for `"center"`, centroid on boundary counts as inside unless on a hole boundary.
   - **Antimeridian handling:** detect polygons whose longitudinal span > 180° and treat them as seamless across the dateline. Plan to shift longitudes to a 0..360 domain for those countries (and shift candidate centroids similarly), then normalize output back to [-180,+180]. (Open question below: confirm preferred approach.)

6) **Eligibility computation (efficient + deterministic).**
   - Use `rasterio.features.geometry_window` to compute minimal raster windows per country polygon.
   - For `"center"`: use `geometry_mask(..., all_touched=False)` to include pixels whose centers fall inside the polygon (holes excluded). This matches §6.2.
   - For `"any_overlap"`: start with `geometry_mask(..., all_touched=True)`, then **refine** any candidate pixels by computing cell-polygon intersection area > 0 to eliminate edge/point-only touches (spec §6.2). This avoids false positives from `all_touched=True`.
   - NODATA values in the raster do **not** affect eligibility; the raster is used for grid geometry only (§6.4).

7) **Pixel area (ellipsoidal) + bounds.**
   - Use `pyproj.Geod` to compute ellipsoidal area for each cell polygon; since pixel size is uniform, precompute per-row areas (lat-dependent) to avoid per-cell geodesic work.
   - Ensure `pixel_area_m2 > 0` for all rows; if any non-positive, abort with `E006_AREA_NONPOS`.
   - Build `tile_bounds` rows from min/max lat/lon and centroid values (schema `#/prep/tile_bounds`).

8) **Output materialisation + determinism receipt.**
   - Stream per-country outputs to parquet shards (deterministic filename convention, e.g., `country=XX/part-000.parquet`), each sorted by `tile_id`.
   - Perform a stable merge or ensure writer sort on `[country_iso, tile_id]` across shards; file order is non-authoritative but byte determinism requires deterministic shard contents.
   - Compute determinism receipt as SHA-256 over ASCII-lex sorted file paths under the `tile_index` partition (spec §9.4). Record only for `tile_index` unless spec explicitly requires the same for `tile_bounds`.

9) **Run report + per-country summaries (observability).**
   - Emit `s1_run_report.json` with required fields (§9.2): `parameter_hash`, `predicate`, `ingress_versions`, `grid_dims`, `countries_total`, `rows_emitted`, `determinism_receipt`, and `pat` counters (including baselines).
   - Emit per-country summaries with `cells_visited`, `cells_included`, `cells_excluded_outside`, `cells_excluded_hole`, `tile_id_min/max` either as an array in the run report or as JSON-lines in logs (prefixed `AUDIT_S1_COUNTRY:`). Decide on storage form (open question below).
   - Ensure these artefacts are **outside** the dataset partition (spec §9.1/§9.7).

10) **Performance Acceptance Tests (PAT) instrumentation (binding for presence).**
   - Track counters: `wall_clock_seconds_total`, `cpu_seconds_total`, `countries_processed`, `cells_scanned_total`, `cells_included_total`, `bytes_read_raster_total`, `bytes_read_vectors_total`, `max_worker_rss_bytes`, `open_files_peak`, `workers_used`, `chunk_size`.
   - Measure baselines (`io_baseline_raster_bps`, `io_baseline_vectors_bps`) by streaming a contiguous ~1GiB segment once (spec Appendix C).
   - After run, compute and log `B_r/S_r` and `B_v/S_v` ratios and the wall-clock bound formula; if any limit fails, raise `E009_PERF_BUDGET` and emit the failure event.
   - Retain run report + per-country summaries ≥30 days (ops retention; not in partition).

11) **Failure events (spec §9.6).**
   - On any hard failure, emit `S1_ERROR` with `code` (`E001_GEO_INVALID`, `E002_RASTER_MISMATCH`, `E003_DUP_TILE`, `E004_BOUNDS`, `E005_ISO_FK`, `E006_AREA_NONPOS`, `E008_INCLUSION_RULE`, `E009_PERF_BUDGET`) and context fields (`parameter_hash`, optional `country_iso`, `raster_row`, `raster_col`).

Open questions / decisions to confirm before coding:
1) **Predicate config source:** Should `inclusion_rule` be driven by a new CLI flag (e.g., `--predicate`) or a policy file under `config/layer1/1B/`? The spec defines `"center"` as default but does not pin a config location.
2) **Antimeridian handling:** Confirm the preferred implementation for dateline-spanning polygons: shift longitudes to a 0..360 domain for those countries and shift candidate centroids accordingly (then normalize outputs back to [-180,+180]), versus another canonical approach you prefer.
3) **Per-country summary delivery:** Prefer embedding the summaries array inside `s1_run_report.json` or emitting JSON-lines in logs? (Spec allows both; dictionary only defines `s1_run_report`.)
4) **Determinism receipt scope:** The spec mandates `tile_index` receipt; do you want the same composite hash recorded for `tile_bounds` as an additional (non-binding) field?

### Entry: 2026-01-13 01:33

Design element: S1 decisions locked (predicate/config + antimeridian + observability)
Summary: Confirmed the implementation choices for S1 predicate configuration, antimeridian strategy, per-country summary delivery, and determinism receipt scope. Recording the decisions and the concrete design implications before any code edits.

Decisions (explicit):
1) **Predicate config:** use CLI flag `--predicate` with default `"center"`. This keeps the selection explicit and avoids introducing a new policy file for S1.
2) **Antimeridian handling:** for dateline-spanning countries, shift country geometry to a 0..360 longitude domain and shift candidate centroids similarly for inclusion tests; normalize output longitudes back to [-180,+180].
3) **Per-country summaries:** emit JSON-lines in logs with prefix `AUDIT_S1_COUNTRY:` (rather than embedding a large array into the run report).
4) **Determinism receipt scope:** compute and record the composite hash for `tile_index` only (spec-mandated). Do not add an additional receipt for `tile_bounds` unless required later.

Design implications and pre-code actions:
- CLI surface will gain `--predicate`, plus `--workers` and `--chunk-size` for performance tuning; defaults must preserve determinism.
- Logging must include predicate choice and country-level counters, and the per-country summaries must be emitted outside the dataset partition (logs only).
- The antimeridian shift needs to be deterministic and only applied to polygons whose longitudinal span exceeds 180°; outputs must always be normalized to [-180,+180].
- Any failure to apply these rules should emit the required `S1_ERROR` event with the spec's error codes and the correct context fields.

### Entry: 2026-01-13 01:55

Design element: S1 runner hardening before execution (antimeridian, PAT counters, path law, validation)
Summary: Identified pre-run compliance gaps in the S1 runner and captured the exact fixes to bring the implementation in line with the expanded spec, dictionary path law, and PAT requirements before further coding.

Pre-implementation issues to resolve (observed in current draft):
1) **Report path law violation.**
   - `s1_run_report` dictionary path is a file path (`.../s1_run_report.json`), but the runner treats it as a directory and writes `_tmp.*.json` inside it.
   - This violates dictionary path law and would publish the report at the wrong location.

2) **Antimeridian handling is incomplete for `"center"` predicate.**
   - Current code shifts geometry only for `"any_overlap"` and still uses geometry_mask against the unshifted geometry for `"center"`.
   - For dateline-spanning polygons, geometry_mask against the raw geometry can create a huge window and include incorrect cells.

3) **PAT counters incomplete/nullable.**
   - `chunk_size` and `io_baseline_vectors_bps` are `None`; spec states their absence triggers `E009_PERF_BUDGET`.
   - `bytes_read_vectors_total` uses file sizes but `io_baseline_vectors_bps` is missing; we need a consistent baseline measurement.

4) **Missing validation checks required by S1 spec.**
   - No explicit checks for centroid/bounds ranges (lon/lat bounds) or for `pixel_area_m2 > 0`.
   - No explicit duplicate `tile_id` check per country (`E003_DUP_TILE`).

5) **World_countries multi-row handling.**
   - The current `world_map` dict overwrites if multiple geometries exist per ISO; spec expects full geometry surface per ISO.

Planned resolutions (detailed, before code edits):
1) **Fix run report publish path.**
   - Treat `s1_run_report` as a file path: create its parent directory, write a temp file in the parent, then atomic rename to the target file path.
   - Keep report outside the dataset partition (dictionary path already encodes this).

2) **Deterministic antimeridian split strategy.**
   - If a country's geometry spans >180° longitude, shift to a 0..360 domain, intersect with west (0..180) and east (180..360) boxes, then shift the east piece back to [-180,0].
   - Process each piece independently (own geometry_window + masks), then union results by `tile_id` to avoid duplicate inclusion.
   - This avoids global-width windows while keeping coordinates in [-180,+180] for raster alignment and ensures holes are preserved.

3) **Complete PAT counter coverage.**
   - Set `chunk_size` to `0` to denote "per-country, no tile chunking" (explicitly logged in the run report).
   - Compute `io_baseline_vectors_bps` using the actual elapsed time to load ISO + world vectors, with `bytes_read_vectors_total` as the sum of their file sizes (the files are fully loaded).
   - Keep raster baseline read as-is (1 GiB window) and use that for `io_baseline_raster_bps` and `bytes_read_raster_total`.

4) **Add S1 validation checks + error events.**
   - Enforce bounds: `centroid_lon` in [-180,180], `centroid_lat` in [-90,90], and `min/max lon/lat` within bounds; fail with `E004_BOUNDS`.
   - Enforce `pixel_area_m2 > 0` and fail with `E006_AREA_NONPOS`.
   - Check per-country duplicate `tile_id` (after any antimeridian merging) and fail with `E003_DUP_TILE`.
   - Emit `S1_ERROR` events for these failure paths with `parameter_hash` and `country_iso`.

5) **Union geometries per ISO.**
   - If `world_countries` has multiple rows for a country, union the geometries to create a single conformance surface.
   - Validate the unioned geometry; if invalid, fail with `E001_GEO_INVALID`.

Implementation note:
- These changes are required before running S1 to avoid a non-compliant run report path, incomplete PAT counters, and incorrect inclusion for dateline countries. All changes will be logged in the logbook and reflected in the S1 runner code.

### Entry: 2026-01-13 02:05

Design element: S1 runner implementation updates (spec compliance + wiring)
Summary: Implemented the S1 runner fixes identified in the 01:55 plan, added CLI/Makefile wiring, and aligned PAT counters, antimeridian handling, and report paths with spec and dictionary law.

Actions taken (implementation details):
1) **Antimeridian split implementation.**
   - Added deterministic split logic: shift geometry to 0..360, intersect with west (0..180) and east (180..360) boxes, then shift east back to [-180,0].
   - Process each piece with its own geometry_window and masks; union inclusion results across parts.
   - Added a tiny epsilon on the split boundary to avoid duplicate inclusion at lon=180.

2) **Per-country geometry handling.**
   - When `world_countries` has multiple rows per ISO, union the geometries (preserves holes) before processing.
   - Fail fast with `E001_GEO_INVALID` if a unioned geometry is empty or invalid.

3) **Bounds/area/duplicate validation.**
   - Added explicit bounds validation for centroid and bounds columns (`E004_BOUNDS`).
   - Added `pixel_area_m2 > 0` enforcement (`E006_AREA_NONPOS`).
   - Added per-country duplicate `tile_id` detection (`E003_DUP_TILE`).
   - All per-country failures raise `EngineFailure` and are surfaced via `S1_ERROR` in the main runner.

4) **PAT counter completeness.**
   - `chunk_size` is now explicitly reported as `0` (per-country windows, no tile block chunking).
   - `io_baseline_vectors_bps` is computed using the actual load time of ISO + world vectors and their on-disk sizes.
   - Raster baseline logging now includes bytes, elapsed time, and baseline bps.

5) **Run report path compliance.**
   - Fixed `s1_run_report` publish logic to treat the dictionary path as a file (write temp file in the parent, then atomic rename to the target file path).

6) **CLI + Makefile wiring.**
   - Added `engine.cli.s1_tile_index` with `--predicate` and `--workers`.
   - Added Makefile target `segment1b-s1` and associated args (`SEG1B_S1_*`).

Notes for follow-up validation:
- Ensure the per-country audit logs still emit `AUDIT_S1_COUNTRY:` lines after refactors.
- Confirm the run report now lands exactly at `reports/layer1/1B/state=S1/parameter_hash=.../s1_run_report.json`.

### Entry: 2026-01-13 02:26

Design element: world_countries reference rebuild (coverage alignment with ISO canonical)
Summary: Investigated the mismatch between `iso3166_canonical_2024` (251 ISO2 codes) and `world_countries.parquet` (236 rows). The Natural Earth shapefile has 258 rows, but 22 entries use ISO_A2 = -99 and ISO_A3 = -99, so the current build path drops valid sovereigns (e.g., FR, NO) and several ISO2 codes (e.g., BQ, GF, GP) never appear in the shapefile at all. This makes S1 fail with `E005_ISO_FK` for missing world_countries coverage.

Observed evidence (pre-implementation):
1) Shapefile `ne_10m_admin_0_countries.zip` has 258 features; 22 have ISO_A2 = -99 (including France, Norway).
2) Current `world_countries.parquet` has 236 rows; missing ISO2 list matches the S1 failure: `AN, BQ, BV, CC, CS, CX, FR, GF, GP, MQ, NO, RE, SJ, TK, YT`.
3) The current build script (`scripts/build_world_countries.py`) reads a geojson and maps ISO_A2 only, so it cannot recover ISO2 for the 22 -99 rows (even though ADM0_A3 has valid codes like FRA/NOR).

Planned resolution (before code changes):
1) **Upgrade build pipeline to read the shapefile zip directly** (or accept both geojson and zip sources):
   - If source ends with `.zip`, use `gpd.read_file("zip://...")`.
   - Support `.geojson`/`.json`/`.shp` paths without breaking existing usage.

2) **Robust ISO2 mapping order:**
   - Use ISO_A2 when valid (two-letter code).
   - Else use ISO_A3 when valid, mapped to ISO2 via `iso3166_canonical_2024.alpha3`.
   - Else use ADM0_A3 mapped to ISO2 via the same alpha3 map (this recovers FR/NO and other -99 ISO_A2 rows).
   - Preserve FIXUP_MAP for exceptional name-based fixes.

3) **Synthetic geometry fill for ISO2 codes absent from Natural Earth:**
   - Continue to provide small synthetic polygons for BQ, CC, CX, GF, GP, MQ, RE, YT, SJ, BV, TK (existing map).
   - Add synthetic entries for historical ISO2 codes present in `iso3166_canonical_2024` but not in NE (e.g., AN, CS) so S1 is FK-complete.
   - Use deterministic 0.5° boxes centered on a canonical lat/lon (documented in the script for auditability).

4) **Rebuild `reference/spatial/world_countries/2024/world_countries.parquet`:**
   - Regenerate using the fixed builder and the NE shapefile zip in `reference/spatial/world_countries/2024/source/`.
   - Update manifest/QA/provenance artifacts to reflect the new build logic and row count.

Acceptance check after rebuild (must pass before S1 rerun):
- `world_countries.parquet` ISO2 coverage equals `iso3166_canonical_2024` (251 codes).
- S1 preflight for missing world_countries codes is empty.
- QA report lists zero missing ISO2 after synthetic augmentation.

### Entry: 2026-01-13 02:55

Design element: world_countries rebuild applied (source zip + ISO mapping + synthetic fill)
Summary: Implemented the rebuild plan for `world_countries` using the Natural Earth zip source and upgraded ISO mapping to recover missing ISO2s. Regenerated the 2024 parquet, QA, manifest, SHA sums, and provenance to reflect the corrected coverage.

Implementation actions:
1) **Builder upgraded for zip + ISO fallback mapping.**
   - `scripts/build_world_countries.py` now accepts `.zip` sources and reads via `gpd.read_file("zip://...")`.
   - ISO mapping now falls back ISO_A2 -> ISO_A3 -> ADM0_A3 -> FIXUP_MAP.
   - Added synthetic geometries for `AN` and `CS` in addition to the previous set.
   - Added a hard fail if any ISO2 remains missing after synthetic augmentation.

2) **Rebuilt 2024 reference outputs.**
   - Regenerated `reference/spatial/world_countries/2024/world_countries.parquet` from the zip source.
   - New coverage: 251 ISO2 rows (matches `iso3166_canonical_2024`).
   - Updated `world_countries.qa.json`, `world_countries.manifest.json`, and `SHA256SUMS` via the build script.

3) **Updated provenance.**
   - `world_countries.provenance.json` now records the new row count, unmapped count/sample, and updated output SHA, plus notes on ISO mapping and synthetic fill.

Follow-up required before rerunning S1:
- Re-run 1B.S0 to reseal `world_countries` with the new hash in `sealed_inputs_1B`.
- Use a fresh run_id (or clean the old run folder) to avoid immutable partition conflicts.

### Entry: 2026-01-13 03:10

Design element: PROJ database mismatch during raster open (S1 environment fix)
Summary: S1 failed with a GDAL/PROJ error indicating `proj.db` layout version mismatch because `PROJ_LIB` points at a PostGIS installation (`...PostgreSQL\\16\\...\\proj`). Rasterio then reports `E002_RASTER_MISMATCH` because CRS metadata cannot be resolved. This must be resolved at runtime by forcing PROJ to use the bundled pyproj database.

Planned resolution (before code changes):
1) **Detect and override bad PROJ_LIB/PROJ_DATA at runtime.**
   - Use `pyproj.datadir.get_data_dir()` to find the correct `proj.db`.
   - If `PROJ_LIB`/`PROJ_DATA` is unset, set both to the pyproj data dir.
   - If set, inspect `{env_path}/proj.db` with sqlite and read `DATABASE.LAYOUT.VERSION.MINOR`; if `< 4`, override to the pyproj dir.
   - Log the previous PROJ path and the new value so operators can trace the fix.

2) **Apply before any rasterio dataset open.**
   - Call the fix in `run_s1` before opening `population_raster_2025` so CRS resolution succeeds.

3) **No contract changes.**
   - This is an environment correction only; no schema/dictionary changes are required.

Follow-up after fix:
- Re-run S1 with a fresh run_id (and after resealing S0) to confirm CRS checks pass without `proj.db` errors.

### Entry: 2026-01-13 03:06

Design element: PROJ runtime override applied (S1)
Summary: Implemented the runtime guard that inspects `proj.db` and overrides `PROJ_LIB`/`PROJ_DATA` when an incompatible PostGIS PROJ database is detected, ensuring raster CRS resolution succeeds.

Implementation details:
1) **PROJ database inspection.**
   - Added `_read_proj_minor_version()` to read `DATABASE.LAYOUT.VERSION.MINOR` from `proj.db` using sqlite.
   - Added `_ensure_proj_db()` to set `PROJ_LIB`/`PROJ_DATA` to `pyproj.datadir.get_data_dir()` when the env path is missing or the minor layout version is < 4.

2) **Early application.**
   - Called `_ensure_proj_db()` at the start of `run_s1` before any rasterio open.
   - Logs the previous PROJ path when it is overridden, so operators can confirm the fix.

### Entry: 2026-01-13 03:12

Design element: Fresh run folder + run_receipt for S1 rerun
Summary: Preparing a new run_id and run_receipt so 1B.S0 can reseal updated `world_countries` without immutable partition conflicts.

Plan (before implementation):
1) **Clone latest run_receipt.json** from `runs/local_full_run-5/<latest>/run_receipt.json`.
2) **Generate a new run_id** (hex) and update:
   - `run_id` (new value),
   - `created_utc` (current UTC),
   - `runs_root` (unchanged),
   - keep `contracts_root`, `contracts_layout`, `external_roots`, `manifest_fingerprint`, `parameter_hash`, `seed` unchanged.
3) **Write the new receipt** to `runs/local_full_run-5/<new_run_id>/run_receipt.json`.
4) **Re-run 1B.S0** (user will execute) to reseal `world_countries` hash into `sealed_inputs_1B`, then run 1B.S1.

### Entry: 2026-01-13 03:11

Design element: Fresh run folder created
Summary: Created a new run folder and run receipt to avoid immutable partition conflicts after updating `world_countries`.

Action taken:
- New run_id: `446496814c08456c874beb9638fc6cfb`
- Path: `runs/local_full_run-5/446496814c08456c874beb9638fc6cfb/run_receipt.json`
- Receipt cloned from latest run and updated `run_id` + `created_utc` only (all other lineage fields preserved).

### Entry: 2026-01-13 03:16

Design element: S1 raster dtype handling (baseline byte sizing)
Summary: The S1 run failed when computing `bytes_per_pixel` because `dataset.dtypes[0]` is a string and does not expose `.itemsize`. This blocks the raster baseline read and thus PAT counters. Need a robust dtype→bytes conversion that works for rasterio’s dtype strings.

Pre-implementation analysis and plan:
1) **Root cause analysis.**
   - `rasterio.DatasetReader.dtypes` returns a tuple of dtype **strings** (e.g., `"float32"`), not numpy dtype objects.
   - Accessing `.itemsize` on the string fails and raises the observed `AttributeError`.

2) **Correction strategy.**
   - Convert the dtype string to a numpy dtype via `np.dtype(dataset.dtypes[0]).itemsize`.
   - Keep the logic otherwise unchanged so the baseline window read and PAT counters remain identical in semantics.

3) **Risk and validation.**
   - This is a local fix in the baseline measurement path; it does not alter downstream tile enumeration or geometry.
   - After patch, re-run S1 and confirm baseline logging resumes and the run progresses past raster open.

4) **If further errors appear.**
   - Capture the next failure point in the logbook and append another entry here before changing code again, per the detailed documentation requirement.

### Entry: 2026-01-13 03:17

Design element: S1 raster dtype fix applied
Summary: Implemented the dtype conversion for the raster baseline byte-size calculation to unblock S1 PAT measurement.

Action taken:
- Updated `bytes_per_pixel` to use `np.dtype(dataset.dtypes[0]).itemsize` so rasterio dtype strings resolve to byte sizes.

Next step:
- Re-run `make segment1b-s1` on the fresh run_id and inspect logs for the next failure (if any) before further edits.

### Entry: 2026-01-13 03:18

Design element: Run receipt missing during S1 rerun
Summary: `make segment1b-s1 RUN_ID=446496814c08456c874beb9638fc6cfb` failed because the run_receipt.json was missing at the expected path. The run folder no longer exists, so S1 cannot resolve the receipt.

Plan:
1) Verify whether the run folder exists under `runs/local_full_run-5/`.
2) If missing, create a new run_id and run_receipt.json (clone the latest receipt, update run_id + created_utc).
3) Retry `segment1b-s0` then `segment1b-s1` using the new run_id.

### Entry: 2026-01-13 03:19

Design element: New run folder created after missing receipt
Summary: Created a new run_id and run_receipt.json because the previously created run folder was missing at execution time.

Action taken:
- New run_id: `d12d2f6268a74b2988524e98d82315f9`
- Path: `runs/local_full_run-5/d12d2f6268a74b2988524e98d82315f9/run_receipt.json`

### Entry: 2026-01-13 03:25

Design element: S1 TopologyException during antimeridian split (invalid geometry)
Summary: `make segment1b-s1` failed with `shapely.errors.GEOSException: TopologyException` while intersecting a country geometry against the antimeridian windows. A direct validity scan of `world_countries.parquet` shows one invalid geometry (`country_iso=EG`), which violates the S1 contract (invalid geometry must trigger `E001_GEO_INVALID`).

Plan (before implementation, detailed):
1) **Confirm invalid geometry at the data source.**
   - Run a validity check on `reference/spatial/world_countries/2024/world_countries.parquet` and list invalid `country_iso` values (currently `EG`).
   - Treat invalid geometry as a data-prep issue (world_countries is the geometry authority for S1) rather than auto-healing inside S1.

2) **Repair geometry in the reference build step.**
   - Update `scripts/build_world_countries.py` to detect invalid geometries and apply `shapely.make_valid` during dataset construction.
   - Record the list of repaired ISO codes in the QA/provenance outputs.
   - If any geometry remains invalid after repair, fail the build with a clear error.

3) **Add explicit E001_GEO_INVALID enforcement in S1.**
   - Before any antimeridian intersection, check `geom.is_valid` for each country.
   - If invalid, raise `EngineFailure` with code `E001_GEO_INVALID` and include `country_iso` in the detail payload.
   - Do **not** auto-heal inside S1; rely on the reference dataset to be valid (spec §6.3).

4) **Rebuild + reseal + rerun.**
   - Rebuild `world_countries.parquet` and update QA/provenance/hash outputs.
   - Re-run S0 for the new run_id to seal the updated `world_countries` hash.
   - Re-run S1 and confirm no topology exceptions and that logs remain spec-compliant.

### Entry: 2026-01-13 03:27

Design element: world_countries geometry repair (reference dataset)
Summary: Rebuilt `world_countries` with explicit invalid-geometry repair to eliminate the Egypt invalid polygon while keeping ISO coverage intact.

Actions taken:
1) **Build script update.**
   - Added `_fix_invalid_geometry()` using `shapely.make_valid` (fallback to `buffer(0)` if still invalid).
   - Captures `invalid_iso_before_fix` and `invalid_iso_after_fix` in the QA payload; hard-fails if any invalid geometries remain.

2) **Dataset rebuild.**
   - Regenerated `reference/spatial/world_countries/2024/world_countries.parquet` from `ne_10m_admin_0_countries.zip`.
   - QA now records `invalid_iso_before_fix=["EG"]` and `invalid_iso_after_fix=[]`.
   - Updated `world_countries.manifest.json`, `world_countries.qa.json`, and `SHA256SUMS`.
   - Updated provenance to record the repair and new output hash.

### Entry: 2026-01-13 03:28

Design element: S1 invalid-geometry enforcement
Summary: Added explicit validation and error mapping so invalid country geometries fail deterministically with `E001_GEO_INVALID`, per spec §6.3.

Implementation details:
1) **Pre-geometry check.**
   - Before any geometry operations, S1 checks `geom.is_valid` and raises `EngineFailure(E001_GEO_INVALID)` with `country_iso` and `explain_validity()` detail.

2) **Antimeridian guard.**
   - Wrapped `_split_antimeridian_geometries()` in a `GEOSException` guard; if triggered, map to `E001_GEO_INVALID` with the exception detail.

### Entry: 2026-01-13 03:31

Design element: Antimeridian split failure for valid geometries (AQ)
Summary: After repairing invalid inputs and enforcing `E001_GEO_INVALID`, S1 still fails for Antarctica (`AQ`) because the **shift-to-360 step** produces an invalid geometry (self-intersection), which then raises a GEOS `TopologyException` during intersection. The original geometry is valid; the invalidity is an artefact of the shift operation.

Plan (before implementation, detailed):
1) **Do not treat this as input invalidity.**
   - `AQ` is valid in the original -180..180 coordinate space; per spec, we should not fail `E001_GEO_INVALID` for a valid geometry.

2) **Normalize the shifted geometry only.**
   - After `_shift_geometry_to_360`, if `geom_360.is_valid` is false, apply `shapely.make_valid(geom_360)` before the west/east intersections.
   - This is a *local* normalization step for the antimeridian split and does not mutate the authoritative input geometry.

3) **Fallback behaviour.**
   - If `make_valid` yields empty geometry or still triggers GEOS errors, the existing `GEOSException` guard will surface `E001_GEO_INVALID`.
   - Log the fix in the logbook and re-run S1 to confirm the split is stable for `AQ`.

### Entry: 2026-01-13 03:32

Design element: Shifted-geometry normalization applied
Summary: Implemented a localized `make_valid` on the shifted 0..360 geometry in `_split_antimeridian_geometries` to prevent self-intersection errors for valid source geometries (e.g., `AQ`).

Action taken:
1) **Runner update.**
   - Added `import shapely` and applied `shapely.make_valid(geom_360)` when the shifted geometry is invalid.
   - Returns early if the repaired geometry is empty; otherwise continues with west/east intersections as before.

Next step:
- Re-run `make segment1b-s1 RUN_ID=869381446fd74b49bd7f7a4735ab873f` and confirm the AQ topology error is resolved.

### Entry: 2026-01-13 03:38

Design element: S1 rerun completed (post-fix)
Summary: S1 completed successfully after the shifted-geometry normalization, publishing the `tile_index` outputs for the new run_id.

Run outcome:
- `make segment1b-s1 RUN_ID=869381446fd74b49bd7f7a4735ab873f` completed (runtime ~327s).
- No `E001_GEO_INVALID` errors observed after the antimeridian fix.
- Output path (per log): `runs/local_full_run-5/869381446fd74b49bd7f7a4735ab873f/data/layer1/1B/tile_index/parameter_hash=ceedfd1785fe0a71e11e5c3ca1d348f544535e303b99b9cb90d550fc2bf921d5`.

## S2 - Tile Weights (S2.*)

### Entry: 2026-01-13 05:35

Design element: S2 contract review + pre-implementation plan (RUN_ID=869381446fd74b49bd7f7a4735ab873f)
Summary: Reviewed S2 expanded spec and the 1B contracts for `tile_weights` and `s2_run_report`. Capturing the detailed plan for deterministic fixed-dp weight computation, evidence emission, and performance guards before touching code.

Contract review notes (authorities + paths):
1) **Schema authority (shape/keys):**
   - `schemas.1B.yaml#/prep/tile_weights` defines PK `[country_iso, tile_id]`, partition `[parameter_hash]`, sort `[country_iso, tile_id]`, required columns `country_iso`, `tile_id`, `weight_fp`, `dp` (plus optional `basis`).
   - `schemas.1B.yaml#/control/s2_run_report` is minimal (requires `parameter_hash`), but the S2 spec mandates additional fields in the report.

2) **Dictionary authority (paths/partition/sort/licence/retention):**
   - `dataset_dictionary.layer1.1B.yaml#tile_weights` → `data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/`, writer sort `[country_iso, tile_id]`, parquet, Proprietary-Internal, retention 365, pii=false.
   - `dataset_dictionary.layer1.1B.yaml#s2_run_report` → `reports/layer1/1B/state=S2/parameter_hash={parameter_hash}/s2_run_report.json` (control-plane; must not be under the dataset partition).

3) **Registry (provenance, not shape):**
   - `artefact_registry_1B.yaml` declares `tile_weights` depends on `tile_index` (and only reads `population_raster_2025` when `basis="population"`).

Pre-implementation plan (detailed):
1) **Resolve run identity and inputs (RUN_ID=869381446fd74b49bd7f7a4735ab873f).**
   - Load `run_receipt.json` to obtain `{parameter_hash}`.
   - Resolve `tile_index` via the Dictionary path family (`data/layer1/1B/tile_index/parameter_hash={parameter_hash}/`).
   - Enforce §5.2 pre-read checks:
     - path exists for the partition,
     - schema anchor `schemas.1B.yaml#/prep/tile_index` (columns/PK/partition/sort),
     - writer sort expectations (or fail `E108_WRITER_HYGIENE` if input violates Dictionary law).
   - Confirm S2 reads **no 1A egress** and does **not** consult `s0_gate_receipt_1B` (spec §5.6).

2) **Parameter governance (basis + dp).**
   - S2 requires `basis ∈ {uniform, area_m2, population}` and a single `dp` (non-negative integer) per partition; both must be disclosed in the run report.
   - Identify the parameter source that feeds `{parameter_hash}` and carries `basis` + `dp` (no `config/layer1/1B` exists yet).
   - Open question to resolve before coding: **where do `basis` and `dp` live for 1B (config file, policy registry, or inline CLI args)?** This must be pinned to the parameter_hash for determinism.

3) **Mass calculation per basis (deterministic).**
   - **uniform:** `m_i := 1` (no extra reads).
   - **area_m2:** `m_i := tile_index.pixel_area_m2` (authoritative S1 area).
   - **population:** read `population_raster_2025` COG and sample the cell for each tile; NODATA → 0. Only read this raster when basis=population.
   - Validate mass domain: finite and ≥ 0; any invalid mass triggers `E105_NORMALIZATION`.

4) **Per-country normalization + fixed-dp quantization.**
   - Compute `M_c = Σ m_i` per country and `U_c` counts.
   - If `U_c` is empty → `E103_ZERO_COUNTRY`.
   - If `M_c = 0` with `|U_c| > 0`, fallback to uniform for that country and record `zero_mass_fallback=true` in per-country summary.
   - Quantize using largest-remainder with stable tie-break:
     - `q_i = m_i * K / M_c`, `z_i = floor(q_i)`, residue `r_i = q_i - z_i`.
     - `S = K - Σ z_i`; assign `+1` to top `S` residues, tie-break by ascending `tile_id`.
   - Ensure exact per-country sum `Σ weight_fp = K`; fail `E105_NORMALIZATION` if not.

5) **Scale for large S1 (221M rows).**
   - Use streaming/iterative processing to avoid materializing the full partition in memory; memory must remain `O(window)` per spec §11.2.
   - Two-pass strategy:
     - Pass 1: compute per-country `M_c` and counts.
     - Pass 2: compute `z_i` and residues, then select top `S` residues per country via an external (on-disk) sort by `(country_iso, residue desc, tile_id asc)` to avoid keeping all residues in memory.
   - Writer output must be sorted `[country_iso, tile_id]` before publish.

6) **Observability artefacts (must be present, outside dataset partition).**
   - Emit `s2_run_report.json` with required fields: `parameter_hash`, `basis`, `dp`, `ingress_versions`, `rows_emitted`, `countries_total`, `determinism_receipt`, and PAT counters.
   - Emit per-country normalization summaries (array in report or JSON-lines `AUDIT_S2_COUNTRY:`).
   - Compute determinism receipt: ASCII-lex list of partition files → concat bytes → SHA-256.

7) **Performance/PAT instrumentation.**
   - Record bytes read for tile_index and raster (if used); vector bytes only if optional geometry validations are used.
   - Capture I/O baselines at start (`io_baseline_ti_bps`, `io_baseline_raster_bps` if population).
   - Record `wall_clock_seconds_total`, `cpu_seconds_total`, `max_worker_rss_bytes`, `open_files_peak`, `workers_used`, and `chunk_size`.
   - Enforce amplification bounds (≤1.25) and runtime inequality (§11.1), else emit `E109_PERF_BUDGET`.

8) **Publish discipline and hygiene.**
   - Stage output outside the live partition; fsync + atomic rename.
   - Re-publish to the same `{parameter_hash}` must be byte-identical.
   - Ensure no non-schema artefacts are written under `tile_weights/parameter_hash=.../`.

Open questions to resolve before implementation:
1) **Basis & dp authority:** Where should S2 read the governed `basis` and `dp` so they are tied to `{parameter_hash}` (new config/policy, CLI args, or another registry file)?
2) **Ingress version strings:** For `ingress_versions` in the run report, should we use path version tokens (e.g., `2024-12-31`, `2024`, `2025`) or add explicit version tags in the Dictionary?

### Entry: 2026-01-13 05:55

Design element: S2 policy source + ingress versioning clarification
Summary: Re-checked the S2 spec for an explicit policy/config location for `basis` and `dp` and confirmed the spec does **not** name a concrete file or registry entry. It only states these are governed parameters captured by `{parameter_hash}` and must be disclosed in the run report.

Resolution posture (pre-implementation decision):
1) **Basis/dp source:** The spec leaves this open; to keep determinism and parameter_hash integrity, the safest path is to introduce a **new 1B policy/config file** (e.g., `config/layer1/1B/policy/s2_tile_weights.yaml`) and ensure it is part of the parameter_hash input set. Without this, S2 would rely on ad-hoc CLI args, which would not be governed.
2) **Ingress version strings:** Recommend using **Dictionary path version tokens** (e.g., `iso3166=2024-12-31`, `world_countries=2024`, `population_raster=2025`) in `ingress_versions` to avoid new contract changes while staying deterministic and aligned with the “Dictionary IDs/versions, not raw hashes” rule.

Pending confirmation:
- Whether to add the new S2 policy/config file now (and include it in parameter_hash).

### Entry: 2026-01-13 06:01

Design element: Add S2 policy file and wire into parameter_hash + S0 sealing
Summary: User approved creating a new 1B policy/config file for S2 weights (`basis` + `dp`), wiring it into the parameter_hash inputs, and sealing it in 1B.S0. This requires updates to the hashing inputs, contract entries, and a full re-run path to propagate the new parameter_hash into the 1A validation bundle and 1B sealed_inputs.

Planned changes (before code edits, detailed):
1) **Policy file + schema.**
   - Create `config/layer1/1B/policy/policy.s2.tile_weights.yaml` with governed fields:
     - `policy_version` (string), `basis` (`uniform|area_m2|population`), `dp` (non-negative int), optional `notes`.
   - Add a new schema anchor in `schemas.1B.yaml` under `policy`:
     - `policy/s2_tile_weights_policy` matching the above structure.

2) **Dictionary + registry wiring (1B).**
   - Add `s2_tile_weights_policy` (or matching ID) to `dataset_dictionary.layer1.1B.yaml`:
     - path `config/layer1/1B/policy/policy.s2.tile_weights.yaml`
     - schema_ref `schemas.1B.yaml#/policy/s2_tile_weights_policy`
     - governance: Proprietary-Internal, retention 365, pii=false.
   - Add the policy to `artefact_registry_1B.yaml` with provenance metadata.

3) **Parameter hash inclusion (1A S0 hashing).**
   - Extend `REQUIRED_PARAM_BASENAMES` in `seg_1A/s0_foundations/hashing.py` to include `policy.s2.tile_weights.yaml` (ASCII basename).
   - Extend `_resolve_param_files` in `seg_1A/s0_foundations/runner.py` to resolve the new policy file and include it in the param list used by `compute_parameter_hash`.
   - Decide whether to register the policy in `artefact_registry_1A.yaml` (so `_resolve_param_files` can find it) or to load `artefact_registry_1B.yaml` additionally. Preference: add a registry entry to 1A to avoid changing loader plumbing.

4) **S0 sealing (1B).**
   - Add the policy dataset ID to the `required_ids` list in `seg_1B/s0_gate/runner.py` so it is hashed into `sealed_inputs_1B`.
   - This requires a new run_id because the S0 partition is immutable and `sealed_inputs_1B` will change.

5) **Re-run path (determinism).**
   - Re-run 1A S0 to generate a new parameter_hash (and new validation bundle with `parameter_hash_resolved.json`).
   - Create a new run_id/receipt, stage 1A outputs, rerun 1B S0 to reseal inputs, then rerun S1 and S2 under the new parameter_hash.

6) **Ingress version reporting (Q2 decision).**
   - `ingress_versions` in the S2 run report will use Dictionary path version tokens (e.g., `2024-12-31`, `2024`, `2025`), not raw hashes.
### Entry: 2026-01-13 06:08

Design element: S2 policy contract wiring (actions taken)
Summary: Implemented the approved policy/config file for S2 weights and wired it into the contract authorities, parameter_hash inputs, and S0 sealing so S2 can read governed basis + dp deterministically.

Actions taken (explicit, for audit):
1) **Policy file created.**
   - `config/layer1/1B/policy/policy.s2.tile_weights.yaml` with `policy_version`, `basis`, `dp`, and optional `notes`.
   - Chosen defaults: `basis=area_m2`, `dp=6` (deterministic fixed-decimal posture; no RNG).

2) **Schema anchor added.**
   - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml` now includes `policy/s2_tile_weights_policy` with required fields `policy_version`, `basis`, `dp`.

3) **Dictionary + registry wiring (1B).**
   - Added `s2_tile_weights_policy` to `dataset_dictionary.layer1.1B.yaml` (path, schema_ref, licence, retention).
   - Added `policy.s2.tile_weights.yaml` to `artefact_registry_1B.yaml` with the same schema anchor.

4) **Parameter_hash + sealing integration.**
   - Added `policy.s2.tile_weights.yaml` to 1A S0 parameter hash inputs (`seg_1A/s0_foundations/hashing.py` + `_resolve_param_files` in `seg_1A/s0_foundations/runner.py`).
   - Added `policy.s2.tile_weights.yaml` to `artefact_registry_1A.yaml` so the parameter hash resolver can find it.
   - Added `s2_tile_weights_policy` to 1B S0 `required_ids` so it is sealed into `sealed_inputs_1B`.

Immediate follow-ups (pre-code for S2):
- Update S0 expanded spec to list `s2_tile_weights_policy` in sealed inputs and input lists.
- Update S2 expanded spec to include `s2_tile_weights_policy` as a required input and clarify that `basis`/`dp` come from it.
- Implement S2 runner/CLI/Makefile wiring and rerun S0->S2 with the new parameter_hash.

### Entry: 2026-01-13 06:20

Design element: S2 runner implementation plan (performance + determinism)
Summary: Preparing the concrete S2 runner design now that the policy input is wired. This plan focuses on streaming per-country processing for large S1 outputs, fixed-dp quantisation, and full evidence emission without loading 221M rows into memory.

Plan (before code edits, detailed):
1) **Inputs and policy resolution (governed, deterministic).**
   - Resolve run_receipt (latest if run_id omitted) and extract `{parameter_hash}`.
   - Resolve `tile_index` via Dictionary; enumerate country partition files under `data/layer1/1B/tile_index/parameter_hash={parameter_hash}/country=*`.
   - Resolve `s2_tile_weights_policy` via Dictionary, validate against `schemas.1B.yaml#/policy/s2_tile_weights_policy`, and read `basis` + `dp` from it (no CLI overrides).
   - Load ISO set from `iso3166_canonical_2024` and treat any unknown `country_iso` as a pre-read contract failure (E101).

2) **Per-country streaming (memory control).**
   - Process **one country file at a time**; keep only that country's arrays in memory.
   - If any country file contains mixed `country_iso` values, treat as writer-hygiene error (E108).
   - Track `countries_total`, `rows_emitted`, and per-country diagnostics for the run report.

3) **Mass calculation per basis.**
   - `uniform`: mass = 1 for each tile.
   - `area_m2`: mass = `pixel_area_m2` from `tile_index`.
   - `population`: sample `population_raster_2025` at tile centroids (rasterio sample); NODATA -> 0.
   - Enforce mass domain: all finite, `>= 0`; any invalid value => E105_NORMALIZATION.

4) **Fixed-dp quantisation (largest remainder, deterministic).**
   - Compute `K=10^dp`, `M_c`, and `q_i = m_i*K/M_c` per country.
   - `z_i = floor(q_i)`, `r_i = q_i - z_i`, `S = K - sum(z_i)`.
   - Allocate `+1` to top `S` residues, tie-break by ascending `tile_id`.
   - Enforce per-country sum `sum(weight_fp) == K`; mismatch => E105_NORMALIZATION.
   - If `M_c = 0` with `|U_c|>0`, fallback to uniform and set `zero_mass_fallback=true`; absence => E104_ZERO_MASS.

5) **Writer hygiene and ordering.**
   - Verify `tile_id` monotonic within each country file; if not, fail E108 (do not silently sort).
   - Emit per-country parquet parts under the tile_weights partition root (no extra partition keys), ensuring writer sort `[country_iso, tile_id]`.
   - Stage under `tmp/` and perform atomic publish; if a partition exists with different bytes => E108.

6) **Evidence + PAT counters.**
   - Run report fields: `parameter_hash`, `basis`, `dp`, `ingress_versions` (Dictionary version tokens), `rows_emitted`, `countries_total`, `determinism_receipt`, `pat` counters.
   - Per-country normalization summary list (country_iso, tiles, mass_sum, K, postquant_sum_fp, residues, zero_mass_fallback).
   - Determinism receipt = ASCII-lex hash of tile_weights partition files.
   - Performance counters: wall_clock, cpu_seconds, bytes_read_tile_index_total (sum file sizes), bytes_read_raster_total (sample_count * bytes_per_pixel), io_baseline_ti_bps (first-file read), io_baseline_raster_bps (population basis only), max RSS and open-files peak.

7) **Logging (storyline clarity).**
   - Log "S2: loaded policy" with basis/dp, "S2: processing country" with tiles count, and progress with rate/eta.
   - Include meaning in logs (e.g., "basis=area_m2 uses pixel_area_m2" and "zero_mass_fallback engaged").

Implementation note:
- This plan intentionally avoids global group-by on 221M rows and uses the S1 per-country partition layout to keep memory bounded.

### Entry: 2026-01-13 06:29

Design element: S2 runner + CLI + Makefile wiring (implementation)
Summary: Implemented the S2 tile weights runner with per-country streaming, governed basis/dp policy, fixed-dp quantisation, run report emission, and Makefile/CLI wiring for execution.

Implementation actions (detailed):
1) **Runner scaffold + contract resolution.**
   - Added `packages/engine/src/engine/layers/l1/seg_1B/s2_tile_weights/runner.py`.
   - Uses ContractSource to load dictionary/registry/schema packs; resolves dataset paths for `tile_index`, `tile_weights`, `s2_run_report`, `iso3166`, `population_raster`, and `s2_tile_weights_policy`.
   - Adds run log file handler under `runs/<run_id>/run_log_<run_id>.log`.

2) **Governed policy enforcement.**
   - Reads `policy.s2.tile_weights.yaml` via Dictionary path, validates against `schemas.1B.yaml#/policy/s2_tile_weights_policy`.
   - Enforces `basis in {uniform, area_m2, population}` and `dp >= 0`, raising `E105_NORMALIZATION` on invalid inputs.

3) **Per-country processing to control memory.**
   - Iterates `country=*` partitions under `tile_index` and loads per-country parquet(s) only.
   - Validates single `country_iso` per partition and enforces `tile_id` monotonicity (writer hygiene).
   - Validates ISO membership via `iso3166_canonical_2024` (FK check).

4) **Fixed-dp weight computation.**
   - Computes `K=10^dp`, masses per basis (uniform/area/population), and largest-remainder allocation with `tile_id` tie-break.
   - Handles zero-mass fallback deterministically and emits `zero_mass_fallback` in summaries.
   - Enforces per-country sum equals `K` (fail `E105_NORMALIZATION` otherwise).

5) **Output + determinism evidence.**
   - Writes per-country parquet parts under a temp directory, then atomically publishes to `tile_weights` partition.
   - Computes determinism receipt (ASCII-lex hash of partition files) and includes it in the run report.

6) **PAT counters and progress logging.**
   - Records wall/CPU time, bytes read, baseline IO bps, max RSS, open-files peak, and progress ETA logs.
   - Captures `ingress_versions` from Dictionary version tokens (population set to null if basis != population).

7) **CLI + Makefile wiring.**
   - Added `packages/engine/src/engine/cli/s2_tile_weights.py`.
   - Added `SEG1B_S2_*` args + `segment1b-s2` target in `makefile`.

Immediate next step:
- Re-run 1A S0 to regenerate parameter_hash, then reseal 1B S0 and rerun S1 and S2 to green; document any failures and fixes inline in this log.

## S3 - Requirements (S3.*)

## S4 - Allocation Plan (S4.*)

## S5 - Site-to-Tile Assignment RNG (S5.*)

## S6 - In-Cell Jitter RNG (S6.*)

## S7 - Site Synthesis (S7.*)

## S8 - Egress Site Locations (S8.*)

## S9 - Validation Bundle & Gate (S9.*)

## S1 - Tile Index (S1.*)

### Entry: 2026-01-13 06:50

Design element: S1 rerun after S2 policy introduction (new parameter_hash lineage)
Summary: After adding `policy.s2.tile_weights.yaml` to the parameter_hash inputs, re-ran S1 under the new run_id to regenerate `tile_index` for the updated parameter_hash and verified completion from the run log.

Execution notes (detailed, evidence-backed):
1) **Run identity.**
   - Run ID: `f079e82cb937e7bdb61615dbdcf0d038`.
   - Parameter hash: `56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7` (from S0).

2) **Execution status (CLI timeout vs run log truth).**
   - The CLI invocation for `segment1b-s1` exceeded the tool timeout window, but the run continued in-process.
   - Verified completion in `runs/local_full_run-5/f079e82cb937e7bdb61615dbdcf0d038/run_log_f079e82cb937e7bdb61615dbdcf0d038.log`.

3) **Completion evidence.**
   - The log shows `S1: completed tile index publish` with `rows_emitted=221253340`.
   - No `S1_ERROR` entries are present after the completion line.
   - Output path recorded in the log matches the dictionary partition:
     - `runs/local_full_run-5/f079e82cb937e7bdb61615dbdcf0d038/data/layer1/1B/tile_index/parameter_hash=56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7/`.

4) **Spec compliance check.**
   - The run log includes ISO coverage and tile enumeration steps as required.
   - The output row count aligns with the S1 run report expectations for the updated `world_countries` build.

Decision record:
- Treat the timeout as a tooling limitation only; completion was validated from the run log and outputs, so no re-run required for S1.

## S2 - Tile Weights (S2.*)

### Entry: 2026-01-13 06:50

Design element: S2 execution and spec-compliance verification (post-policy integration)
Summary: Executed S2 for the new parameter_hash and verified the run report + run log satisfy the S2 spec requirements.

Execution details and checks (explicit):
1) **Run identity.**
   - Run ID: `f079e82cb937e7bdb61615dbdcf0d038`.
   - Parameter hash: `56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7`.

2) **Execution status (CLI timeout vs run log truth).**
   - The CLI invocation for `segment1b-s2` exceeded the tool timeout window, but the run continued.
   - Verified completion in `runs/local_full_run-5/f079e82cb937e7bdb61615dbdcf0d038/run_log_f079e82cb937e7bdb61615dbdcf0d038.log`:
     - `S2 progress ... countries_processed=249/249 rows_emitted=221253340`.
     - `S2: run report written`.
     - CLI completion line with output paths.

3) **Run report inspection (spec compliance).**
   - Report path:
     - `runs/local_full_run-5/f079e82cb937e7bdb61615dbdcf0d038/reports/layer1/1B/state=S2/parameter_hash=56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7/s2_run_report.json`
   - Key fields present and correct:
     - `basis=area_m2` (from policy), `dp=6`, `countries_total=249`, `rows_emitted=221253340`.
     - `ingress_versions` uses Dictionary tokens (`iso3166=2024-12-31`, `world_countries=2024`, `population_raster=null` because basis != population).
     - `determinism_receipt` populated with `sha256_hex`.
     - `pat` counters present (bytes_read, wall/cpu time, rss, open_files_peak).
     - `country_summaries` list includes `postquant_sum_fp=1000000` and `zero_mass_fallback=false` across countries.

4) **Output publish confirmation.**
   - Output path logged matches dictionary partition:
     - `runs/local_full_run-5/f079e82cb937e7bdb61615dbdcf0d038/data/layer1/1B/tile_weights/parameter_hash=56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7/`.
   - No `S2_ERROR` events observed.

Decision record:
- S2 is considered green and spec-compliant for the current parameter_hash; no further rerun required unless downstream checks detect a lineage mismatch.
