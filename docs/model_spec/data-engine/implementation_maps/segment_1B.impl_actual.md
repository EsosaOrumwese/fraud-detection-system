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

### Entry: 2026-01-13 06:52

Design element: S3 contract review + pre-implementation plan (requirements frame)
Summary: Completed the S3 expanded spec read and contract anchor review (schema + dictionary + registry). Logging the detailed design plan and decisions for a deterministic, streaming requirements frame before writing any S3 code.

Contract review (authorities + shape/path anchors):
1) **Schema authority (shape/keys).**
   - `schemas.1B.yaml#/plan/s3_requirements` defines PK `[merchant_id, legal_country_iso]`, partitions `[seed, manifest_fingerprint, parameter_hash]`, writer sort `[merchant_id, legal_country_iso]`, strict columns: `merchant_id`, `legal_country_iso`, `n_sites (>=1)`.
   - Run report anchor: `schemas.1B.yaml#/control/s3_run_report` requires `{seed, manifest_fingerprint, parameter_hash}` and allows extra fields; S3 spec mandates additional fields in the report.

2) **Dictionary authority (paths/partitions/licence/retention).**
   - `s3_requirements` path: `data/layer1/1B/s3_requirements/seed={seed}/parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/` with writer sort `[merchant_id, legal_country_iso]`.
   - `s3_run_report` path: `reports/layer1/1B/state=S3/seed={seed}/parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/s3_run_report.json` (control-plane, must be outside dataset partition).

3) **Registry authority (dependencies).**
   - `s3_requirements` depends on `outlet_catalogue`, `tile_weights`, `iso3166_canonical_2024`, `s0_gate_receipt_1B`.

Pre-implementation plan (brainstormed steps, explicit):
1) **Resolve run identity (seed/manifest_fingerprint/parameter_hash).**
   - Load `run_receipt.json` (latest by mtime if run_id not provided) to get `{seed, manifest_fingerprint, parameter_hash}`.
   - Read `s0_gate_receipt_1B` for `manifest_fingerprint` and validate against `schemas.1B.yaml#/validation/s0_gate_receipt`.
   - Enforce `manifest_fingerprint` path token equals receipt field; abort on mismatch or missing receipt (E301/E_RECEIPT_SCHEMA_INVALID).
   - Do **not** rehash the 1A bundle; S3 trusts the S0 receipt only.

2) **Resolve inputs via Dictionary (no literal paths).**
   - `outlet_catalogue` via Dictionary path `seed={seed}/manifest_fingerprint={manifest_fingerprint}`.
   - `tile_weights` via Dictionary path `parameter_hash={parameter_hash}`.
   - `iso3166_canonical_2024` reference for FK set.
   - Enforce path‑embed equality for `outlet_catalogue` columns (`manifest_fingerprint`, and `global_seed` if present) vs path tokens; no equivalent columns exist for `tile_weights` (path token only).

3) **Streamed group-by over outlet_catalogue (deterministic, O(1) memory per group).**
   - Because writer sort is `[merchant_id, legal_country_iso, site_order]`, compute counts in a single pass:
     - Track current `(merchant_id, legal_country_iso)` group and `site_order` contiguous range.
     - Validate `MIN(site_order)=1`, `MAX(site_order)=count`, `COUNT(DISTINCT)=count` (E314 on violation).
     - Emit one row per group with `n_sites=count` (n_sites >= 1; elide zero counts).
   - This avoids full materialisation and aligns with the S3 performance envelope (O(1) memory per group).

4) **FK + coverage checks (deterministic asserts).**
   - Build `iso_set` from `iso3166_canonical_2024`; assert all `legal_country_iso` are in ISO2 and uppercase (E302).
   - Build `tile_weight_countries` from `tile_weights`:
     - Option A (preferred): stream `tile_weights` once and collect distinct `country_iso` (table is sorted by country_iso).
     - Option B (if output is per-country files): derive from parquet metadata/partition naming, but only if reliable (avoid implicit assumptions).
   - Coverage rule: every `legal_country_iso` emitted by S3 must be present in `tile_weight_countries` (E303 on missing).

5) **Output writing + immutability.**
   - Write `s3_requirements` as parquet sorted by `[merchant_id, legal_country_iso]`.
   - Stage outputs in temp dir, fsync, then atomic rename into the dictionary partition.
   - If partition exists, require byte-identical content (E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL).

6) **Run report + determinism receipt (required).**
   - Write `s3_run_report.json` to dictionary path (outside dataset partition), including required fields:
     - `seed`, `manifest_fingerprint`, `parameter_hash`,
     - `rows_emitted`, `merchants_total`, `countries_total`,
     - `source_rows_total` (rows counted from outlet_catalogue),
     - `ingress_versions.iso3166` (use Dictionary version token `2024-12-31`),
     - `determinism_receipt` (ASCII‑lex hash over partition files).
   - Optional summaries: per-merchant totals, `fk_country_violations`, `coverage_missing_countries` counters for audit trace.

7) **Failure events + logging clarity.**
   - Emit `S3_ERROR` with `{code, at, seed, manifest_fingerprint, parameter_hash}` and optional `{merchant_id, legal_country_iso}`.
   - Logs should narrate steps: "S3: gate receipt validated", "S3: building coverage set from tile_weights", "S3: counting outlet_catalogue rows", plus progress (elapsed/rate/eta).
   - Keep outputs out of partition; do not read world_countries/population_raster/tz_world (E311 on disallowed reads).

Implementation decisions (with rationale):
1) **Coverage set strategy:** stream `tile_weights` once to build a country set. This avoids relying on file naming and is deterministic even if file layout changes.
2) **Group-by method:** single-pass streaming using writer sort to keep memory bounded and enforce site_order contiguity deterministically.
3) **Ingress version in report:** use Dictionary version token for `iso3166` (per S3 spec 10.2); no new config required.

Open questions (if any before coding):
1) None from spec; all required sources and contracts exist. Proceed to implementation once this plan is acknowledged.

### Entry: 2026-01-13 16:42

Design element: S3 performance risk posture (explicit risk/mitigation note)
Summary: S3 is performance-sensitive because it scans large `outlet_catalogue` and needs coverage checks against `tile_weights`. Poor implementation can blow memory or add O(n) overhead beyond streaming.

Risks if implemented poorly (explicit):
1) **Full materialisation of outlet_catalogue** (or wide group-by in memory) would exceed RAM and thrash, turning a streaming count into a multi-hour job.
2) **Naive join against tile_weights** could trigger massive shuffles or full-table joins across 200M+ rows.
3) **Repeated scans** of outlet_catalogue or tile_weights (e.g., double-pass grouping without need) would amplify IO beyond 1.25x and slow to a crawl.
4) **Ignoring writer-sort** would force an in-memory sort or external sort, increasing time and disk usage.

Mitigations baked into the plan (how we avoid these):
1) **Single-pass streaming counts** over outlet_catalogue using its writer sort `[merchant_id, legal_country_iso, site_order]`, keeping O(1) memory per group.
2) **Coverage set pre-scan** of tile_weights to materialise only the distinct `country_iso` set (tiny) and avoid any join.
3) **No full-table joins** or repartitioning; counts source is outlet_catalogue only (spec law).
4) **Strict writer-sort adherence** and deterministic output ordering; no extra sorts unless input violates the contract (then fail fast).
5) **Progress/ETA logging** during long scans to detect stalls early and avoid silent hangs.

### Entry: 2026-01-13 16:55

Design element: S3 implementation approach (row-group streaming + chunked output)
Summary: Recording the concrete algorithm choices for S3 implementation before code changes, focusing on streaming group detection, site_order integrity checks, and output chunking.

Implementation decisions (pre-code, explicit):
1) **Row-group streaming over outlet_catalogue (pyarrow-first).**
   - Prefer pyarrow row-group reads for `outlet_catalogue` to avoid loading entire partitions.
   - Read only required columns: `merchant_id`, `legal_country_iso`, `site_order`, plus `manifest_fingerprint` and `global_seed` (if present) for path-embed checks.
   - If pyarrow is unavailable, fall back to Polars `scan_parquet` with streaming and explicitly log the fallback (performance risk noted).

2) **Group detection using vectorized boundaries.**
   - Within each row group, compute boundary indices where `(merchant_id, legal_country_iso)` changes.
   - Emit one output row per group segment; track group state across row-group boundaries to ensure counts continue correctly.
   - This avoids per-row Python loops while preserving deterministic grouping.

3) **Site_order integrity check (contiguous 1..n).**
   - For each group, enforce `site_order[0] == 1` and `site_order[-1] == count` with strict +1 increments.
   - Any gap, duplicate, or non-monotonic sequence triggers `E314_SITE_ORDER_INTEGRITY` immediately.

4) **Coverage set strategy for tile_weights.**
   - Build a distinct `country_iso` set by streaming `tile_weights` (only the `country_iso` column).
   - Use this set for coverage checks during S3 emission (E303 on missing coverage).

5) **Chunked output writing.**
   - Accumulate output rows in memory up to a fixed batch size (e.g., 1M rows), then write each batch as `part-xxxxx.parquet`.
   - Maintain global ordering by writing batches in the streaming order (writer sort `[merchant_id, legal_country_iso]` preserved per file).
   - After all parts are written, compute determinism receipt across the partition.

6) **Run report contents (required + extended).**
   - Include required fields (`seed`, `manifest_fingerprint`, `parameter_hash`, `rows_emitted`, `merchants_total`, `countries_total`, `source_rows_total`, `ingress_versions.iso3166`, `determinism_receipt`).
   - Add performance counters (`bytes_read_outlet_catalogue_total`, `bytes_read_tile_weights_total`, `wall_clock_seconds_total`, `cpu_seconds_total`, `max_worker_rss_bytes`, `open_files_peak`, `workers_used`).

Rationale:
- Ensures O(1) memory per group, avoids full joins, preserves deterministic output ordering, and keeps large scans observable.

### Entry: 2026-01-13 17:01

Design element: S3 runner + CLI + Makefile wiring (implementation)
Summary: Implemented the S3 requirements runner with streaming group-by, coverage checks, output chunking, and added CLI/Makefile wiring.

Implementation actions (detailed):
1) **Runner scaffold + contract resolution.**
   - Added `packages/engine/src/engine/layers/l1/seg_1B/s3_requirements/runner.py`.
   - Loads `dataset_dictionary.layer1.1B.yaml` and `schemas.1B.yaml`; resolves `s0_gate_receipt_1B`, `outlet_catalogue`, `tile_weights`, `iso3166_canonical_2024`, `s3_requirements`, and `s3_run_report`.

2) **Gate receipt validation.**
   - Validates `s0_gate_receipt_1B` against `schemas.1B.yaml#/validation/s0_gate_receipt`.
   - Enforces `manifest_fingerprint` parity with the path token; emits `S3_ERROR` on mismatch.

3) **Coverage + FK setup.**
   - Builds `iso_set` from `iso3166_canonical_2024`.
   - Streams `tile_weights` to materialise the distinct `country_iso` coverage set used by S3 (no join).

4) **Streaming group-by over outlet_catalogue.**
   - Uses pyarrow row-group scans (fallback to Polars if pyarrow unavailable) to read `merchant_id`, `legal_country_iso`, `site_order`, plus `manifest_fingerprint`/`global_seed` for path-embed checks.
   - Detects group boundaries via vectorized key-change indices; carries the open group across row groups.
   - Enforces `site_order` contiguity strictly (`1..n` with +1 increments); violations emit `E314_SITE_ORDER_INTEGRITY`.
   - Enforces writer-sort monotonicity via `(merchant_id, legal_country_iso)` ordering; violations emit `E310_UNSORTED`.

5) **Output chunking + publish.**
   - Emits `s3_requirements` rows in batches (`part-00000.parquet`, etc.) preserving writer sort.
   - Computes determinism receipt (ASCII-lex bytes hash) and publishes atomically with immutability guard.

6) **Run report emission.**
   - Writes `s3_run_report.json` with required fields plus PAT counters (bytes read, wall/cpu time, RSS, open files).
   - Validates the report against `schemas.1B.yaml#/control/s3_run_report`.

7) **CLI + Makefile wiring.**
   - Added `packages/engine/src/engine/cli/s3_requirements.py`.
   - Added Makefile vars `SEG1B_S3_RUN_ID`, args, and target `segment1b-s3` (with `.PHONY` update).

Next step:
- Run `make segment1b-s3 RUN_ID=f079e82cb937e7bdb61615dbdcf0d038` and iterate on any failures, logging each decision and fix.

### Entry: 2026-01-13 17:04

Design element: S3 execution fixes + green run
Summary: Ran S3, hit a Polars streaming panic while building the tile_weights coverage set, switched to a pyarrow-based coverage scan, and re-ran S3 to green.

Observed failure (first run):
1) **Polars streaming panic** while collecting `tile_weights` country coverage:
   - Error: `Parquet no longer supported for old streaming engine` when calling `collect(streaming=True)` on a lazy scan.
   - Impact: S3 aborted before reading `outlet_catalogue`.

Resolution (documented change before rerun):
1) **Switched coverage scan to pyarrow row-group reads.**
   - Added `_load_tile_weight_countries()` to scan `country_iso` via pyarrow when available; falls back to `pl.read_parquet` without streaming.
   - Added an explicit `tile_weights_empty` guard to emit `E303_TILE_WEIGHT_COVERAGE` if the coverage set is empty.

Rerun outcome (green):
1) **Command:** `make segment1b-s3 RUN_ID=f079e82cb937e7bdb61615dbdcf0d038`.
2) **Run log evidence:**
   - Coverage set loaded (`countries=249`) and outlet_catalogue scan completed.
   - Output published: `s3_requirements` with `rows_emitted=2635`.
   - Run report written to the dictionary path under `reports/layer1/1B/state=S3/.../s3_run_report.json`.
3) **Spec compliance checks:**
   - Run report includes required fields (`seed`, `manifest_fingerprint`, `parameter_hash`, `rows_emitted`, `merchants_total`, `countries_total`, `source_rows_total`, `ingress_versions`, `determinism_receipt`).
   - Output partition exists at `data/layer1/1B/s3_requirements/seed=42/parameter_hash=56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7/manifest_fingerprint=9673aac41b35e823b2c78da79bdf913998e5b7cbe4429cf70515adf02a4c0774/`.

### Entry: 2026-01-13 17:28

Design element: S3 spec-compliance tightening + resource hygiene
Summary: Added sealed-inputs gating checks, clarified log intent, and reduced parquet handle retention; re-ran S3 to confirm green and recheck PAT counters.

Brainstorm + decision detail (captured before editing):
1) **Sealed-input enforcement.**
   - Problem: S3 reads `outlet_catalogue` + `iso3166_canonical_2024`; spec expects those to be sealed by S0 and S3 should fail if it’s about to read unsealed inputs.
   - Options considered:
     - Trust the receipt path only (weak; doesn’t guarantee seal).
     - Validate that `sealed_inputs` includes the required dataset IDs and hard-fail if missing (best match to S0 gate intent).
   - Decision: Implement a sealed-inputs check after receipt validation and emit `E311_DISALLOWED_READ` if `outlet_catalogue` or `iso3166_canonical_2024` are missing.

2) **Log clarity around lineage parity.**
   - Problem: S3 logs didn’t explicitly confirm path-embedded parity (seed/manifest), making the “story” unclear when reviewing logs.
   - Decision: Add a clear log line after validating `manifest_fingerprint`/`global_seed` inside `outlet_catalogue`, so the run narrative is explicit about lineage gating.

3) **Open-files peak unexpectedly high.**
   - Observation: `open_files_peak` stayed high (hundreds) even after earlier S3 runs; suspected parquet readers were not being closed during tile-weights coverage and row-count pre-scan.
   - Options considered:
     - Switch the metric to `psutil.Process.open_files()` length (truer “file handle” count, but expensive inside per-row-group loops).
     - Keep the metric but tighten reader lifecycle so we aren’t inflating handles ourselves.
   - Decision: Close pyarrow readers explicitly after each file in tile-weights coverage and total-rows pre-scan. Keep the metric (num_handles) for now to avoid per-row-group overhead; revisit only if needed.

Implementation actions:
1) **Receipt enforcement.**
   - Added `sealed_inputs` presence check for `outlet_catalogue` and `iso3166_canonical_2024` after receipt schema validation.
   - Emits `E311_DISALLOWED_READ` with `missing` list if the seal is absent.
   - Added log line: `S3: s0_gate_receipt validated (sealed_inputs=...)`.

2) **Parquet reader lifecycle fixes.**
   - Added `_close_parquet_reader()` usage in `_load_tile_weight_countries()` to close each pyarrow ParquetFile.
   - Closed ParquetFile handles after the `total_rows` pre-scan as well.

3) **Rerun + outcome.**
   - Command: `make segment1b-s3 RUN_ID=f079e82cb937e7bdb61615dbdcf0d038`.
   - Result: green; output partition already existed with identical bytes; run report written.
   - Log evidence includes: `S3: s0_gate_receipt validated (sealed_inputs=10)`, `S3: outlet_catalogue path-embed parity verified (pyarrow)`, and atomic publish guard message.
   - `open_files_peak` still reports `484` in `s3_run_report.json`; this suggests the metric reflects global process handles rather than leaked parquet readers. Keeping the metric as-is for now, but closing readers avoids us adding extra handles.

### Entry: 2026-01-13 19:56

Design element: S3 PAT open_files_peak meaning + metric correction
Summary: Reworked `open_files_peak` to report actual open file descriptors (not process handles) and recorded the metric basis in the run report.

Brainstorm + decision detail (captured before editing):
1) **Problem statement.**
   - `open_files_peak=484` was misleading for S3 because it counted process handles (sockets, DLLs, etc.) instead of open files; it did not reflect parquet-reader leakage risk.
2) **Options considered.**
   - Keep `num_handles` (cheap, but not file-specific; fails the intent of “open files”).
   - Switch to `psutil.Process.open_files()` count (file-specific, but potentially more expensive).
   - Add a dual metric (handles + open files) for clarity (extra noise in PAT).
3) **Decision.**
   - Use `open_files()` when available and fall back to handles only if `open_files()` fails.
   - Record which metric is used in `pat.open_files_metric` so the meaning is explicit.
   - Add a log line so the run log explains the basis (`S3: PAT open_files metric=...`).

Implementation actions:
1) **Metric selector.**
   - Added `_select_open_files_counter()` to pick `open_files` or fallback (`handles`/`fds`), returning a callable + label.
2) **Run report.**
   - Added `open_files_metric` to `pat` to document the basis.
3) **Rerun + outcome.**
   - Command: `make segment1b-s3 RUN_ID=f079e82cb937e7bdb61615dbdcf0d038`.
   - Log confirms `S3: PAT open_files metric=open_files`.
   - `s3_run_report.json` now reports `open_files_peak=6`, which aligns with expected open-file usage.

## S4 - Allocation Plan (S4.*)

### Entry: 2026-01-14 11:27

Design element: S4–S8 logging retrofit (storytelling, phase clarity, and progress semantics).
Summary: The current run logs show raw counters without context. We will retrofit S4–S8 logs so each state narrates its purpose, inputs, progress meaning, and outputs without forcing the operator to read the spec. This is a logging-only change (no data mutation) but must be implemented carefully to avoid log spam or ambiguity.

Plan (before implementation, detailed and explicit):
1) **Define the story arc per state (one-line intent + phase markers).**
   - S4: “Allocate tiles to satisfy S3 requirements.” Clarify that each `(merchant, country)` pair yields tile plan rows.
   - S5: “Assign concrete tiles to each site requirement using RNG.” Clarify that each site gets one tile; RNG events are logged.
   - S6: “Jitter within tile bounds and enforce point‑in‑country.” Clarify that each site gets one jittered point, with resample attempts.
   - S7: “Synthesize site records by joining S5 assignments + S6 jitter + 1A outlet catalogue.” Clarify that output is per‑site and order‑free.
   - S8: “Materialise `site_locations` egress from S7.” Clarify that egress is order‑free and parity with S7 is enforced.

2) **Add explicit phase headers in logs (start/inputs/loop/output).**
   - Add “phase start” log after gate receipt validation (authorized inputs).
   - Add “inputs loaded” log that names the key datasets and what their rows represent.
   - For each progress tracker, label what “processed” means (pairs vs sites vs egress rows).
   - Add “output published” log that restates what the output represents (e.g., site locations for downstream joins).

3) **Adjust progress labels to be self‑describing.**
   - Replace generic labels like `S4 pairs processed` with `S4 allocation progress pairs_processed (merchant‑country requirements)`.
   - Replace `S5 progress sites` with `S5 assignment progress sites_processed (tile assignment per site)`.
   - Replace `S6 progress sites_processed` with `S6 jitter progress sites_processed (location per site)`.
   - Replace `S7 progress sites_processed` with `S7 synthesis progress sites_processed (site records built)`.
   - Replace `S8 progress sites_processed` with `S8 egress progress sites_processed (site_locations rows)`.

4) **Keep logs lean and non‑spammy.**
   - Only add a few summary logs per state and avoid per‑row logging.
   - Preserve existing error logs and timers; add context to the messages rather than increasing volume.

Expected outcome:
 - Run logs read as a narrative for each state, with clear "what this step is doing" context.
 - Operators can diagnose issues without cross-referencing the spec for common cases.

### Entry: 2026-01-14 11:35

Design element: S4 logging retrofit implementation (allocation plan story logs).
Summary: Implemented the planned S4 narrative logging so the run log explains what is being allocated, what each counter means, and what the output represents. No data-path or determinism changes.

Implementation actions (detailed):
1) **Gate + input narration.**
   - Updated the gate receipt log to explain the authorization scope (S3 requirements + tile assets).
   - Added `S4: allocation inputs resolved (s3_requirements + tile_weights + tile_index)` so the operator sees which datasets are in play.
   - Clarified the ISO domain log as "for country validation" to show why it is loaded.

2) **Input context (no new volume).**
   - Clarified the `s3_requirements` size log as "merchant-country requirements" so the row/file counts have meaning.
   - Kept the "read mode" log to avoid unnecessary verbosity.

3) **Progress semantics.**
   - Changed the progress label to `S4 allocation progress pairs_processed (merchant-country requirements)`.
   - Updated the loop start timer to `starting allocation loop (per pair -> tile plan rows)`.

4) **Output narrative.**
   - Added `S4: allocation plan ready for S5 (rows_emitted=..., pairs_total=...)` to explain downstream usage.
   - Updated the run report log to `allocation summary + determinism receipt`.

Notes:
- Logging only; allocation math, writer sort, and determinism receipts are unchanged.
- No additional per-row logging was introduced.

### Entry: 2026-01-13 19:58

Design element: S4 pre-implementation review + planning (integer allocation plan)
Summary: Completed S4 spec/contract review and captured a detailed implementation plan with validation, determinism, and performance posture; flagged open questions before coding.

Spec + contract review notes (sources reviewed):
1) **Expanded spec:** `state.1B.s4.expanded.md` (integerisation law, identity parity, overflow requirements, validators, run report fields).
2) **Dictionary:** `dataset_dictionary.layer1.1B.yaml` entries for `s4_alloc_plan` + `s4_run_report`.
3) **Schema pack:** `schemas.1B.yaml#/plan/s4_alloc_plan` + `#/control/s4_run_report` (shape authority).
4) **Registry:** `artefact_registry_1B.yaml` entry for `s4_alloc_plan` (role + dependencies).

Planning notes (detailed, before implementation):
1) **Identity + gate enforcement (fail-closed).**
   - Resolve `{seed, manifest_fingerprint, parameter_hash}` from `run_receipt.json`.
   - Validate `s0_gate_receipt_1B` (schema) and ensure `sealed_inputs` includes `s3_requirements`, `tile_weights`, `tile_index`, `iso3166_canonical_2024`.
   - Enforce parity: receipt fingerprint = publish fingerprint; `s3_requirements` seed = publish seed; S2 tables read with same parameter_hash.

2) **Inputs resolution (Dictionary only).**
   - Resolve:
     - `s3_requirements` (seed+fingerprint+parameter_hash).
     - `tile_weights` (parameter_hash).
     - `tile_index` (parameter_hash).
     - `iso3166_canonical_2024` (ingress; FK domain).
   - Prohibit reads of non-listed surfaces (world_countries, population_raster, tz_world_2025a).

3) **Country coverage + universe checks (fast-fail).**
   - Build per-country tile universe from `tile_index` (must be non-empty).
   - Build per-country weights from `tile_weights` (must exist for every country in `s3_requirements`).
   - Verify `legal_country_iso` in S3 belongs to ISO domain.
   - Decision: treat any country missing weights or tiles as `E402_MISSING_TILE_WEIGHTS` / `E403_ZERO_TILE_UNIVERSE` and abort.

4) **Integerisation algorithm (largest remainder; no RNG).**
   - For each `(merchant_id, legal_country_iso, n_sites)` in S3:
     - Read `(tile_id, weight_fp, dp)` for that country.
     - Use integer arithmetic with bignum to avoid overflow:
       - `prod = weight_fp * n_sites` (Python int).
       - `z = prod // K`, `rnum = prod % K`, `K = 10^dp`.
     - `S = n_sites - sum(z)` (shortfall).
     - Add +1 to the `S` tiles with largest `rnum`, tie-break `tile_id` ascending.
     - Emit only rows where `n_sites_tile >= 1`.
   - Enforce conservation per pair; emit `E404_ALLOCATION_MISMATCH` on violation.
   - Enforce positivity (no zero rows) → `E412_ZERO_ROW_EMITTED`.

5) **Tie-break + ordering (deterministic).**
   - Sort tie candidates by `rnum` desc, `tile_id` asc.
   - Writer sort for output: `[merchant_id, legal_country_iso, tile_id]` (stable merge order).
   - Reject unsorted emission (`E408_UNSORTED`) and PK duplicates (`E407_PK_DUPLICATE`).

6) **Overflow posture (hard error).**
   - Use Python int for all `weight_fp * n_sites` and accumulation steps.
   - If any overflow guard or recompute indicates wrap, emit `E416_NUMERIC_OVERFLOW`.

7) **Run report + determinism receipt (outside dataset partition).**
   - Write `s4_run_report.json` with required fields:
     - `seed`, `manifest_fingerprint`, `parameter_hash`, `rows_emitted`, `merchants_total`,
       `pairs_total`, `alloc_sum_equals_requirements`, `ingress_versions`, `determinism_receipt`.
   - Record PAT counters: `bytes_read_s3`, `bytes_read_weights`, `bytes_read_index`,
     `rows_emitted`, `pairs_total`, `ties_broken_total`, `wall_clock_seconds_total`,
     `cpu_seconds_total`, `workers_used`, `max_worker_rss_bytes`, `open_files_peak`.
   - Determinism receipt computed from ASCII-lex ordered bytes in `s4_alloc_plan`.

8) **Performance posture (large weights; avoid cross joins).**
   - Stream `s3_requirements` in writer order; group by `(merchant_id, legal_country_iso)`.
   - Cache per-country weights + tile universe (LRU by country) to avoid re-reading for each pair.
   - Avoid full materialisation of `tile_weights` across all countries; read only countries present in S3.
   - Keep output batched (row groups ~100k–250k) for read efficiency.

Open questions / confirmations needed before implementation:
1) **Extra weights vs tile_index mismatch.**
   - Spec mandates allocation only over tile_index and says weights cover eligible tiles.
   - If `tile_weights` contains tiles absent from `tile_index`, should we hard-fail (treat as coverage mismatch), or ignore extras? Current leaning: hard-fail to avoid silent re-normalisation.
2) **dp consistency.**
   - S2 policy defines dp; S4 assumes a constant dp per parameter_hash.
   - Should we enforce a single dp across all tile_weights rows and fail if any deviation is detected?

### Entry: 2026-01-13 20:25

Design element: S4 decision lock-in (post-approval)
Summary: Recorded the approved posture for S4 before coding to avoid silent defaults.

Decision lock-in:
1) **tile_weights vs tile_index mismatch.**
   - Hard-fail if `tile_weights` includes tiles not present in `tile_index` for the parameter_hash. This avoids silent drops or renormalisation and enforces universe integrity.
2) **dp consistency.**
   - Enforce a single `dp` across all tile_weights rows for the parameter_hash; any deviation is a hard error.

Next steps (approved):
1) Implement S4 runner (streamed integerisation + validators) with determinism receipt and run report.
2) Add CLI + Makefile wiring (`segment1b-s4`) and run on current RUN_ID.
3) Iterate until green; update run log review and compliance notes.

### Entry: 2026-01-13 20:50

Design element: S4 seal-authority failure (E409) and S0 receipt strategy adjustment
Summary: The first S4 run failed because `s0_gate_receipt_1B` did not authorize reads for S4 outputs (`s3_requirements`, `tile_weights`, `tile_index`). Documenting the decision process and fix before completing S4.

Observed failure (run log + error detail):
- `EngineFailure: F4:E409_DISALLOWED_READ S4 1B.s4_alloc_plan` with `missing=["s3_requirements","tile_weights","tile_index"]`.
- Root cause: the S0 receipt `sealed_inputs` list only included the S0-sealed inputs, not downstream state outputs required by S4. S4 is intentionally fail-closed when a read is not authorized.

Brainstormed options (and why each was considered):
1) **Relax S4 to allow reads not listed in `sealed_inputs`.**
   - Pro: avoids re-running S0.
   - Con: violates the gate model and makes receipts less authoritative; undermines the “sealed_inputs as read-authorization” contract.
2) **Add S4 dependencies to `sealed_inputs_1B` (hashed).**
   - Pro: keeps all reads in a single authoritative list.
   - Con: invalid for S0 because these assets do not exist yet at the time S0 runs; would either force forward writes or cause a permanent mismatch.
3) **Extend `s0_gate_receipt_1B.sealed_inputs` with receipt-only entries for downstream outputs, while keeping `sealed_inputs_1B` unchanged.**
   - Pro: keeps S0’s sealed inputs immutable and hash-backed, but still authorizes reads for later states by naming them in the receipt.
   - Con: requires a new S0 receipt (immutable partition) and re-running S0 under a new run_id.

Decision:
- **Option 3.** Add `s3_requirements`, `tile_weights`, and `tile_index` to the receipt `sealed_inputs` list as receipt-only entries (no hashes), while leaving `sealed_inputs_1B` untouched.
- Rationale: preserves the contract that `sealed_inputs_1B` is the hash-backed inventory of S0-sealed assets, while the receipt serves as the read-authorization boundary for downstream states.

Planned implementation steps (pre-code, explicit):
1) Update S0 gate runner to build a `receipt_inputs` list consisting of:
   - All sealed assets (current behavior).
   - Receipt-only entries for `s3_requirements`, `tile_weights`, and `tile_index` (with partition keys + schema_ref).
2) Keep `sealed_inputs_1B` unchanged (no new hashes for outputs that do not exist at S0 time).
3) Regenerate S0 outputs under a fresh run_id (immutable partitions).
4) Re-run S4 and confirm the sealed-inputs authorization passes.

### Entry: 2026-01-13 20:56

Design element: S4 implementation + rerun fixes (receipt-only + new run_id)
Summary: Implemented S4 runner/CLI/Makefile wiring, then addressed S4 rerun failures by regenerating S0 with receipt-only entries and correcting staged inputs for the new run_id.

Implementation actions (completed):
1) **S4 runner/CLI/Makefile wiring.**
   - Added `seg_1B/s4_alloc_plan/runner.py` with deterministic integer allocation, sealing checks, and run report + determinism receipt.
   - Added CLI `engine.cli.s4_alloc_plan` and Makefile target `segment1b-s4` with `SEG1B_S4_*` args.
2) **S0 receipt update.**
   - Implemented `receipt_inputs` in S0 gate to include receipt-only entries (`s3_requirements`, `tile_weights`, `tile_index`) while leaving `sealed_inputs_1B` unchanged (hash-backed assets only).
   - Rationale: preserves gate authority without pretending S0 can hash outputs that don’t exist yet.

Rerun troubleshooting (detailed):
1) **E401_NO_S3_REQUIREMENTS (first rerun).**
   - Cause: staged `s3_requirements` into the wrong path (copied files to `data/layer1/1B/s3_requirements/` root without the seed/parameter_hash/manifest partitions).
   - Fix: re-copied `s3_requirements` into the exact dictionary partition path:
     - `data/layer1/1B/s3_requirements/seed=42/parameter_hash=.../manifest_fingerprint=.../`
2) **E403_ZERO_TILE_UNIVERSE (second rerun).**
   - Cause: `tile_index` (and `tile_weights`) were initially copied into `data/layer1/1B/parameter_hash=.../` instead of `data/layer1/1B/tile_index/parameter_hash=.../` and `tile_weights/parameter_hash=.../`.
   - Fix: re-copied `tile_index` and `tile_weights` into their dictionary-resolved paths.
   - Note: the stray `data/layer1/1B/parameter_hash=.../` folder is unused by dictionary resolution; leave in place for now to avoid destructive deletes, but it should be cleaned later if desired.

Current status:
- A new run_id was created and S0 re-run successfully with the updated receipt.
- S4 rerun started at `2026-01-13 20:53:38` and is currently running; no run report has been emitted yet.
- Next step after completion: inspect `s4_run_report.json` + output partition for spec compliance and adjust if any issues surface.

### Entry: 2026-01-13 21:08

Design element: S4 run log visibility (progress/heartbeat logging gap)
Summary: The S4 run log stops after initialization (`PAT open_files metric=...`), which means the main allocation loop provides no visible progress. This violates the logging requirement (story + heartbeat) and makes it hard to diagnose long-running behavior.

Brainstormed options for better S4 run visibility:
1) **Add progress tracking that works with and without pyarrow.**
   - Problem: current `_ProgressTracker` relies on a known total and does not emit if total=0 (pyarrow missing or pre-scan disabled).
   - Option: allow `total=None` to emit `processed`, `elapsed`, `rate` without ETA.
2) **Add explicit phase logs before long operations.**
   - Log the number of `s3_requirements` files, total bytes, and the intended processing mode (pyarrow vs polars).
   - Log when tile_index/tile_weights are loaded for a country and how many tiles are in scope.
3) **Add a lightweight heartbeat inside the row loop.**
   - Only log every N rows or every T seconds to avoid spamming.
   - Include rows processed, merchants seen, and cache hit/miss counts (if cheap).

Decision:
- Implement option 1 + 2, and add a time-gated heartbeat (every ~5s) inside the row-group loop.
- Keep logs sparse (no per-row logging) but informative enough to trace “where” in the state flow we are.

Planned code changes (before editing):
1) Update `_ProgressTracker` to accept `total=None` and emit logs without ETA when total is unknown.
2) Log S4 phase entry: resolved input paths, file counts, bytes, and read mode (pyarrow/polars).
3) Log per-country load summary (country, tiles count, dp) on first load.
4) Add a heartbeat that prints processed rows and rate every few seconds even when total is unknown.

### Entry: 2026-01-13 21:15

Design element: S4 progress/heartbeat logging (implementation)
Summary: Implemented the planned S4 logging enhancements so long-running allocation is visible and traceable.

Actions taken (implementation):
1) **Progress tracker upgraded.**
   - `_ProgressTracker` now accepts `total=None` and still emits progress logs without ETA (processed, elapsed, rate).
2) **Phase-entry logs added.**
   - Logs ISO domain size, S3 file count/bytes, and read mode (pyarrow vs polars).
   - Logs total pair count when pyarrow metadata is available.
3) **Per-country load summary.**
   - Added a log when each country’s tile assets are loaded (tiles count, dp, bytes read, cache size).
4) **Heartbeat logging.**
   - Added a time-gated heartbeat every ~5 seconds (checked every 10k pairs) with pairs/merchants/rows counts and rate.
5) **Completion log.**
   - Added a summary log after the allocation loop before determinism hashing.

Next step:
- Re-run `segment1b-s4` for run_id `04ffabbdfbd34b9d8a4d61e7be70782b` after stopping the currently running process (the running process uses the older logging code).

### Entry: 2026-01-13 21:13

Design element: S4 rerun with new logging (terminate + restart)
Summary: Proceeding to terminate the active S4 run (old logging) and rerun with the updated logging so progress is visible.

Decision and action plan (explicit):
1) Identify the active `engine.cli.s4_alloc_plan` process and terminate it (user-approved).
2) Re-run `make segment1b-s4 RUN_ID=04ffabbdfbd34b9d8a4d61e7be70782b`.
3) Monitor `run_log_04ff...` to confirm the new progress/heartbeat lines appear.
4) If any failures occur, log the error and the fix ideas immediately before changing code.

### Entry: 2026-01-13 21:17

Design element: S4 rerun executed with new logging
Summary: Re-ran S4 with updated logging; progress is now visible in the run log.

Observed outcomes (post-rerun):
1) **Termination check.**
   - No active `engine.cli.s4_alloc_plan` process was found at rerun time, so there was nothing to terminate.
2) **Rerun started successfully.**
   - `make segment1b-s4 RUN_ID=04ffabbdfbd34b9d8a4d61e7be70782b` launched and began emitting new logs:
     - ISO domain count, S3 file counts/bytes, read mode, row count.
     - Per-country asset load summaries (tiles/dp/bytes/cache).
3) **Heartbeat note.**
   - The heartbeat log is time‑gated and checks every 10k pairs; this run has only 2635 pairs, so heartbeat lines may not appear even though the logging is now active.

Next step:
- Let the run complete and confirm `s4_run_report.json` + output partition; if the run stalls or fails, capture the error and adjust before re-running.

### Entry: 2026-01-13 21:31

Design element: S4 log noise reduction + progress clarity (implementation)
Summary: Adjusted S4 logging to reduce per‑country spam while keeping progress clear, and added cache summaries so operators can interpret run health.

Reasoning captured before edits:
1) Per‑country logs were firing on every cache miss (including reloads after eviction), which drowned out real progress.
2) Heartbeat was unlikely to fire on small runs; we need a lower step threshold and clearer progress text.
3) The operator still needs to understand cache behavior and how far the run has progressed without scanning hundreds of lines.

Changes applied:
1) **Per‑country logs only on first‑seen countries.**
   - Added a `seen_countries` set so the “loaded country assets” line emits only once per ISO.
2) **Cache stats tracking.**
   - Added counters for `cache_hits`, `cache_misses`, and `cache_evictions`.
   - Added a cache summary log at the end of the allocation loop.
3) **Heartbeat tuning.**
   - Heartbeat check step now scales with total pairs (`max(500, total_pairs/10)`).
   - Heartbeat log now includes cache stats and prints `pairs_processed` against total when available.
4) **Progress tracker final log.**
   - `_ProgressTracker` now emits a final progress line when `processed >= total` even if the last update was within the throttle window.

Expected outcome:
- Far fewer per‑country lines while keeping “where we are” visible.
- Heartbeat emits even for mid‑sized runs, and the final progress line always appears when total is known.

### Entry: 2026-01-14 00:03

Design element: S4 run completion + spec compliance check
Summary: S4 completed successfully on run_id `04ffabbdfbd34b9d8a4d61e7be70782b`; run report and determinism receipt are present and align with the spec.

Evidence from run log:
- `S4: run report written` and `S4 1B complete` lines present in `runs/local_full_run-5/04ffabbdfbd34b9d8a4d61e7be70782b/run_log_04ffabbdfbd34b9d8a4d61e7be70782b.log`.

Run report highlights (spec checks):
1) Required fields present:
   - `seed`, `manifest_fingerprint`, `parameter_hash`.
   - `rows_emitted=30785`, `merchants_total=1263`, `pairs_total=2635`.
   - `alloc_sum_equals_requirements=true`.
   - `ingress_versions.iso3166=2024-12-31`.
   - `determinism_receipt` with `partition_path`, `sha256_hex`, `bytes_hashed`.
2) PAT counters present:
   - `bytes_read_s3_total`, `bytes_read_weights_total`, `bytes_read_index_total`.
   - `wall_clock_seconds_total`, `cpu_seconds_total`, `max_worker_rss_bytes`.
   - `open_files_peak`, `open_files_metric`, `workers_used`, `ties_broken_total`.

Spec compliance judgement:
- S4 is green and compliant for this run_id; safe to advance to S5.

### Entry: 2026-01-14 01:48

Design element: S4 timer logger crash (pre-fix analysis)
Summary: A new S4 run crashed after writing the parquet output because `_StepTimer.info` does not accept formatting args.

Observed failure:
- `TypeError: _StepTimer.info() takes 2 positional arguments but 5 were given` at `runner.py:1216`.
- The code calls `timer.info("S4: ... %s", a, b, c)` in multiple places, but the method signature only accepts `message: str`.

Decision and plan (before editing):
1) Update `_StepTimer.info` to accept `*args`, and format the message when args are provided (same pattern used in other runners).
2) Keep log output identical (elapsed/delta unchanged) so only the crash is removed.

### Entry: 2026-01-14 01:49

Design element: S4 timer logger crash (implementation)
Summary: Updated the S4 step timer to accept formatting args, eliminating the `TypeError` after output write.

Change applied:
- `packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py` now defines `_StepTimer.info(self, message, *args)` and formats the message when args are supplied.

Expected outcome:
- S4 no longer crashes at the final `timer.info(...)` call; elapsed/delta logging remains unchanged.

## S5 - Site-to-Tile Assignment RNG (S5.*)

### Entry: 2026-01-14 11:36

Design element: S5 logging retrofit implementation (site-to-tile assignment story logs).
Summary: Implemented narrative log updates for S5 so the log explains the assignment story (inputs, RNG loop meaning, and outputs) without spec lookups. No data-path changes.

Implementation actions (detailed):
1) **Gate + input narration.**
   - Updated gate receipt log to describe authorization scope (S4 allocation + tile assets).
   - Added `S5: assignment inputs resolved (s4_alloc_plan + tile_index)` and clarified the ISO log as "for country validation".
   - Clarified the `s4_alloc_plan` size log as "tile requirements per merchant-country".

2) **Progress semantics.**
   - Changed the progress label to `S5 assignment progress sites_processed (tile assignment per site)`.
   - Added loop start log: `starting tile assignment loop (per site -> tile_id)` so "processed" has meaning.

3) **Output narrative.**
   - Kept the assignment completion log and updated the run report log to `assignment summary + determinism receipt`.

Notes:
- RNG emission, writer sort, and determinism receipts remain unchanged.
- Log volume kept minimal (phase markers + progress).

### Entry: 2026-01-14 00:08

Design element: S5 contract review + pre-implementation plan (site-to-tile assignment RNG)
Summary: Completed S5 expanded spec + contract review and captured a detailed, deterministic implementation plan before touching code.

Spec + contract review (authoritative sources checked):
1) **Expanded spec:** `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s5.expanded.md`.
2) **Dataset dictionary:** `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml` entries for:
   - `s5_site_tile_assignment`, `s5_run_report`, `rng_event_site_tile_assign`, `rng_audit_log`.
3) **Schema anchors:**
   - Dataset: `schemas.1B.yaml#/plan/s5_site_tile_assignment`.
   - Run report: `schemas.1B.yaml#/control/s5_run_report`.
   - RNG events: `schemas.layer1.yaml#/rng/events/site_tile_assign` (requires `rng_envelope` fields).

Key contract constraints to honor (binding):
1) **Identity triple:** all reads/writes bound to `{seed, manifest_fingerprint, parameter_hash}`; no mixing.
2) **Inputs:** `s4_alloc_plan`, `tile_index`, `iso3166_canonical_2024` only (no outlet_catalogue reads).
3) **RNG budget:** exactly one `site_tile_assign` event per emitted site row; events must validate against RNG envelope.
4) **Writer sort:** dataset sorted by `[merchant_id, legal_country_iso, site_order]`; no duplicates/omissions.
5) **Tile universe:** assigned `(legal_country_iso, tile_id)` must exist in `tile_index` for `parameter_hash`.
6) **Immutability:** re‑publish to same identity must be byte‑identical; RNG events must be identical too.

Implementation plan (pre‑code, detailed):
1) **Gate + identity setup.**
   - Resolve `run_receipt.json` (latest if run_id not supplied).
   - Validate `s0_gate_receipt_1B` and require `sealed_inputs` include `s4_alloc_plan`, `tile_index`, `iso3166_canonical_2024`.
   - Confirm `{seed, manifest_fingerprint, parameter_hash}` parity with input paths.

2) **RNG audit log handling (core log).**
   - Use dictionary entry `rng_audit_log` and schema `schemas.layer1.yaml#/rng/core/rng_audit_log/record`.
   - If an entry for `{seed, parameter_hash, run_id}` exists, log “audit present”.
   - If missing, append a new audit row (philox2x64‑10, build commit hash), matching S1/S6 behaviour.

3) **Per‑pair processing (deterministic + RNG).**
   - Read `s4_alloc_plan` in writer order `[merchant_id, legal_country_iso, tile_id]`.
   - For each `(merchant_id, legal_country_iso)`:
     - Build tile multiset `T` by expanding `tile_id` by `n_sites_tile` (positives only), in ascending `tile_id`.
     - Compute `N = sum(n_sites_tile)` and create site list `S = [1..N]` (site_order).
     - Generate one RNG draw per site under substream `site_tile_assign`:
       - Use Philox2x64‑10; store counters `before/after` per site, `draws="1"`, `blocks=1`.
       - Log RNG events to JSONL as they are generated (order not required).
     - Permute sites by sorting `(u, site_order)` ascending; tie‑break by site_order.
     - Assign sequentially to `T` (tile_id runs) so each tile gets its exact quota.
     - Emit dataset rows `(merchant_id, legal_country_iso, site_order, tile_id)` in writer sort.

4) **RNG stream determinism.**
   - Ensure RNG generation is independent of processing order (no inter‑country order encoding).
   - Derive substream key/counter deterministically per **pair** to avoid cross‑country coupling.

5) **Performance posture (large N).**
   - If `N` is small, sort `(u, site_order)` in memory.
   - If `N` exceeds a threshold, use external sort:
     - Write sorted runs for `(u, site_order)` and k‑way merge them to build `S_perm`.
     - Assign tiles while streaming the merge to avoid holding all `N` in RAM.
   - Batch output rows and RNG events; avoid wide in‑memory tables.

6) **Validation + error posture (fail‑closed).**
   - Enforce FK: every `(legal_country_iso, tile_id)` must exist in `tile_index`.
   - Enforce counts: `rows_emitted == rng_events_emitted`; `pairs_total` matches distinct pairs.
   - Emit `S5_ERROR` with `seed/manifest_fingerprint/parameter_hash/run_id` on any failure.

7) **Run report + determinism receipt.**
   - Write `s5_run_report.json` with required fields:
     - `seed`, `manifest_fingerprint`, `parameter_hash`, `run_id`,
       `rows_emitted`, `pairs_total`, `rng_events_emitted`, `determinism_receipt`.
   - Determinism receipt is the SHA‑256 over dataset partition files only (ASCII‑lex file order).

Open questions / confirmations needed before coding:
1) **Run ID source for RNG logs.** Should S5 use the run_receipt `run_id` (recommended for determinism) or mint a new run_id at S5 start?
2) **Pair-scoped RNG derivation.** I plan to derive the RNG substream per `(merchant_id, legal_country_iso)` to avoid inter-country order effects. Confirm this is acceptable.
3) **External sort threshold.** Any preference for the in-memory vs spill threshold (e.g., `N > 1e6` sites)?

### Entry: 2026-01-14 00:28

Design element: S5 decisions locked + detailed implementation approach (before coding)
Summary: Decisions resolved for S5 RNG identity and sorting strategy; documenting the exact algorithm and logging posture to follow during implementation.

Decisions confirmed (explicit):
1) **Run ID source for RNG logs:** use the `run_receipt` `run_id` as the single S5 RNG stream identifier. No new run_id minted in S5.
2) **Pair-scoped RNG substream:** derive Philox substreams per `(merchant_id, legal_country_iso)` to keep pair assignments independent of inter-country processing order.
3) **External sort threshold:** use `N > 1_000_000` as the spill-to-disk threshold; in-memory sort below that.

Detailed implementation steps (pre-code, exhaustive):
1) **Identity + gate checks.**
   - Resolve `run_receipt.json` (run_id, seed, parameter_hash, manifest_fingerprint).
   - Validate `s0_gate_receipt_1B` against `schemas.1B.yaml#/validation/s0_gate_receipt`.
   - Require sealed_inputs to include `tile_index` and `iso3166_canonical_2024` (authorization for reads used by S5).
   - Confirm path tokens for S4/S5 inputs match `{seed, manifest_fingerprint, parameter_hash}` from the run receipt.

2) **Input resolution (strict).**
   - Resolve `s4_alloc_plan` under `{seed, parameter_hash, manifest_fingerprint}`.
   - Resolve `tile_index` under `{parameter_hash}` and `iso3166_canonical_2024` at reference scope.
   - Do not read any other surfaces (no `world_countries`, no `population_raster_2025`, no `tz_world_2025a`).

3) **Tile index FK cache (performance + correctness).**
   - Load `tile_index` per-country into a cached `set(tile_id)` using pyarrow row groups when available.
   - Cache size limited (reuse S4-style cache) and log cache hits/misses.
   - For every S4 row, validate `(legal_country_iso, tile_id)` exists; otherwise emit `E505_TILE_NOT_IN_INDEX`.

4) **RNG derivation (deterministic per pair).**
   - Build master material with `mlr:1B.master` + manifest_fingerprint bytes + seed (Philox2x64-10).
   - For each `(merchant_id, legal_country_iso)` pair, derive `(key, counter_hi, counter_lo)` using:
     - label: `site_tile_assign`
     - merchant_u64 (sha256-based)
     - legal_country_iso string (UER-encoded)
   - One draw per site: `u = u01(philox(counter_hi, counter_lo, key))`, increment counter by 1.

5) **Pair assignment algorithm (authoritative).**
   - Build tile multiset `T` by repeating each `tile_id` `n_sites_tile` times; `T` is sorted by `tile_id` (ascending).
   - Build site list `S = [1..N]` where `N = sum(n_sites_tile)` (site_order).
   - Generate `u` per site (in site_order order), then sort `(u, site_order)` ascending to get the permutation.
   - Assign `tile_id` from `T` sequentially to the permuted sites; then emit rows in writer sort order `[merchant_id, legal_country_iso, site_order]`.

6) **Large-N handling (spill path).**
   - If `N > 1_000_000`, switch to external sort:
     - Generate `u` + counters sequentially; store `u`/counters in memmap arrays by site_order.
     - Write sorted runs of `(u, site_order)` to temp files and k-way merge them.
     - Assign tiles during merge into a memmap `tile_id` array keyed by site_order.
   - After assignment, stream site_order 1..N to emit dataset rows + RNG events without holding all rows in RAM.

7) **RNG logs + trace + audit.**
   - RNG events: write one JSONL event per site to `rng_event_site_tile_assign` path, include all envelope fields + `merchant_id`, `legal_country_iso`, `site_order`, `tile_id`, `u`.
   - RNG trace log: append exactly one trace row per event (RngTraceAccumulator).
   - RNG audit log: if no row exists for `{seed, parameter_hash, run_id}`, append a new audit entry; if present, do not duplicate.

8) **Run report + determinism receipt (after publish).**
   - Compute composite SHA-256 over dataset partition files only (ASCII-lex relative paths).
   - Emit `s5_run_report.json` with required fields:
     - `seed`, `manifest_fingerprint`, `parameter_hash`, `run_id`
     - `rows_emitted`, `pairs_total`, `rng_events_emitted`
     - `determinism_receipt`
   - Include PAT counters (bytes read, wall/cpu, rss, open_files_peak) for auditability.

9) **Logging posture (story-driven).**
   - Log phase entry: inputs resolved, S4 files count/bytes, read mode (pyarrow/polars), iso domain size.
   - For each pair: log `merchant_id`, `legal_country_iso`, `n_sites_total`, `tiles_distinct`.
   - Heartbeat logs: progress in rows and pairs, plus rate/ETA, to avoid silent long loops.
   - Emit `S5_ERROR` with details on any abort, including `run_id` and pair identifiers when applicable.

### Entry: 2026-01-14 00:56

Design element: S5 implementation hardening (pre-code adjustments before first run)
Summary: Before running S5, I need to add a few guardrails and performance tweaks that the spec implies but the initial draft code does not explicitly enforce.

Detailed decisions and rationale (before editing):
1) **Writer-order + PK guard on emitted rows.**
   - Add an output key tracker `(merchant_id, legal_country_iso, site_order)` and fail fast on:
     - **Duplicate keys** -> `E502_PK_DUPLICATE_SITE`.
     - **Out-of-order keys** -> `E509_UNSORTED`.
   - Rationale: spec requires writer sort and PK uniqueness; enforcing at emit time is cheap and prevents silent corruption.

2) **Throttle progress updates in the per-site loop.**
   - Today, the per-site loop calls `progress_sites.update(1)` for every row, which adds overhead for very large runs.
   - Implement a step-based update (e.g., every 1k-50k sites depending on `n_sites_total`, always emitting a final update at the end of the pair).
   - Rationale: maintain heartbeat visibility without inflating CPU on million-scale loops (performance priority).

3) **Throttle RNG generation progress logs.**
   - Only emit RNG generation progress for large `n_sites_total` and update in coarse steps (similar to site loop).
   - Rationale: RNG generation is already heavy; logging per draw is unnecessary noise/overhead.

4) **Close handles + clean temp artifacts deterministically.**
   - Ensure `event_handle` and `trace_handle` are closed in a `finally` block.
   - For external sort pairs, flush/del memmaps and remove the per-pair temp directory after the pair is processed.
   - Remove the S5 temp root after successful publish to avoid disk bloat.
   - Rationale: resilience + clean reruns; avoids leaving large spill files behind.

5) **Makefile target for S5.**
   - Add `segment1b-s5` target so S5 can be run independently via `make` (consistent with S0-S4).
   - Rationale: operational parity with other states and easier reruns.

Planned edits (after this note):
1) Update `packages/engine/src/engine/layers/l1/seg_1B/s5_site_tile_assignment/runner.py` with the guards, throttling, and cleanup logic.
2) Update `makefile` to add the `segment1b-s5` target (S5 command wiring already present).

### Entry: 2026-01-14 00:59

Design element: S5 implementation hardening (applied)
Summary: Implemented the pre-run guardrails and performance adjustments described at 00:56 so the first S5 run is spec-aligned and performant.

Implementation actions (explicit, as executed):
1) **Output order + PK guard added.**
   - Implemented `last_output_key` tracking in the per-site emit loop.
   - On duplicate key: emit `E502_PK_DUPLICATE_SITE` and abort.
   - On out-of-order key: emit `E509_UNSORTED` and abort.
   - This enforces writer sort + PK uniqueness at emit-time (cheap, deterministic).

2) **Progress throttling for per-site loop.**
   - Added `progress_step` computed per pair (`max(1000, min(50_000, n_sites_total/200))` for large pairs).
   - Progress updates now occur per step (and on the final remainder), reducing per-row overhead while preserving heartbeat logs.

3) **RNG generation progress throttling.**
   - `_generate_rng_arrays` now only emits progress when `n_sites >= 100000`.
   - Progress updates are step-based (same scale as above) to avoid per-draw overhead.

4) **RNG event budget guard.**
   - Added explicit `rng_events_emitted == rows_emitted` check with `E507_RNG_EVENT_MISMATCH` before publish.
   - This enforces the one-event-per-site budget required by the spec.

5) **Temp cleanup + handle safety.**
   - Wrapped the S4 scan loop in `try/finally` so RNG event/trace handles are closed on success or failure.
   - For external-sort pairs, memmaps are flushed and per-pair temp dirs removed in `finally`.
   - Removed the S5 temp root after successful publish to avoid disk bloat.

6) **Makefile target added.**
   - Added `segment1b-s5` target to invoke `engine.cli.s5_site_tile_assignment`.

Files updated:
- `packages/engine/src/engine/layers/l1/seg_1B/s5_site_tile_assignment/runner.py`
- `makefile`

### Entry: 2026-01-14 01:02

Design element: S5 run failure on rng_audit_log schema validation (pre-fix reasoning)
Summary: First S5 run failed before processing pairs because the rng_audit_log payload failed JSON-schema validation (`None is not of type 'string'`).

Failure details:
- Run command: `make segment1b-s5 RUN_ID=04ffabbdfbd34b9d8a4d61e7be70782b`
- Error: `SchemaValidationError: None is not of type 'string'` while validating `rng/core/rng_audit_log/record`.
- Root cause: audit payload included optional fields (`code_digest`, `hostname`, `platform`, `notes`) with `None`, but the Draft202012 validator does not honor `nullable: true` in the schema, so `None` fails `type: string`.

Decision and plan (before edit):
1) **Drop `None` optional fields from audit payload before validation.**
   - These fields are not required by the schema, so omission is valid and avoids the `nullable` keyword mismatch.
   - This keeps the payload schema-valid while preserving required fields (`ts_utc`, `run_id`, `seed`, `manifest_fingerprint`, `parameter_hash`, `algorithm`, `build_commit`).

2) **Leave the broader nullable-handling issue for later.**
   - This same schema nuance exists elsewhere (other runners), but the immediate fix is scoped to S5 to unblock the run.
   - If needed, we can later implement a shared helper that converts `nullable: true` to `type: [X, "null"]`.

Planned change:
- Adjust `audit_entry_payload` assembly in `seg_1B/s5_site_tile_assignment/runner.py` to filter out `None` values before `_validate_payload`.

### Entry: 2026-01-14 01:03

Design element: S5 rng_audit_log validation fix (applied)
Summary: Implemented the fix for the rng_audit_log schema error by dropping None-valued optional fields before validation.

Change applied:
- In `seg_1B/s5_site_tile_assignment/runner.py`, filtered `audit_entry_payload` with a dict comprehension to remove `None` values, leaving only required fields (and any non-null optional fields).

Expected outcome:
- Draft202012 validation passes for `rng_audit_log` since all remaining fields are of type `string`.
- The audit entry remains schema-valid and still captures required provenance fields.

### Entry: 2026-01-14 01:05

Design element: S5 run after audit fix (execution note)
Summary: Re-ran S5 with the audit fix; the CLI timed out while the run continued, so I am tracking completion via the run log.

Observed execution:
- `make segment1b-s5 RUN_ID=04ffabbdfbd34b9d8a4d61e7be70782b` started successfully.
- The log shows active per-pair assignment lines and S5 progress heartbeat entries.
- The CLI timed out (tool limit) before completion, so I will inspect the run log for `S5: run report written` and `S5 1B complete` to confirm success.

Next step:
- Monitor `runs/local_full_run-5/04ffabbdfbd34b9d8a4d61e7be70782b/run_log_04ffabbdfbd34b9d8a4d61e7be70782b.log` for completion or failure markers, and fix any errors if present.

### Entry: 2026-01-14 01:08

Design element: S5 run completion + spec compliance check
Summary: The S5 run completed successfully for run_id `04ffabbdfbd34b9d8a4d61e7be70782b`. Run report and determinism receipt are present and satisfy required fields.

Evidence from run log:
- `S5: run report written` and `S5 1B complete` lines present in `runs/local_full_run-5/04ffabbdfbd34b9d8a4d61e7be70782b/run_log_04ffabbdfbd34b9d8a4d61e7be70782b.log`.
- No `S5_ERROR` entries after completion.

Run report checks (spec compliance):
- Required fields present: `seed`, `manifest_fingerprint`, `parameter_hash`, `run_id`, `rows_emitted`, `pairs_total`, `rng_events_emitted`, `determinism_receipt`.
- Budget equality: `rows_emitted=31159` equals `rng_events_emitted=31159`.
- Determinism receipt present with `sha256_hex` and `bytes_hashed`.
- PAT counters present (bytes_read_s4_total, bytes_read_index_total, wall/cpu time, open_files_peak).

Compliance judgement:
- S5 is green and spec-compliant for this run identity; safe to proceed to S6 when ready.

### Entry: 2026-01-14 01:16

Design element: Shared nullable-schema helper for RNG audit log validation
Summary: Implemented a shared JSON Schema normalizer to support `nullable: true` across RNG audit log validations and integrated it into the runners that validate audit records.

Problem observed:
- RNG audit log schemas use `nullable: true` on optional fields, but Draft202012Validator does not interpret `nullable` unless it is converted into a union type. This caused validation failures when optional fields were set to `null`.

Decision (before code):
1) Add a shared helper that rewrites schema fragments containing `nullable: true` into Draft2020-compatible unions (`type: [X, "null"]` or `anyOf` for `$ref`).
2) Apply this helper in the `_schema_from_pack` functions used by RNG audit log validation so any record schema is normalized before validation.

Implementation applied:
- Added `normalize_nullable_schema` to `packages/engine/src/engine/contracts/jsonschema_adapter.py`.
- Updated `_schema_from_pack` in:
  - `packages/engine/src/engine/layers/l1/seg_1B/s5_site_tile_assignment/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_1A/s6_foreign_set/runner.py`
  - `packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/runner.py`
  to return normalized schemas, ensuring RNG audit log validation accepts nullable optional fields.

Expected outcome:
- RNG audit log validation will accept `null` for optional fields without per-runner workarounds.
- This reduces the risk of repeat `None is not of type 'string'` errors across states that validate RNG audit logs.

## S6 - In-Cell Jitter RNG (S6.*)

### Entry: 2026-01-14 11:37

Design element: S6 logging retrofit implementation (in-cell jitter story logs).
Summary: Added narrative logs to make S6's purpose and progress readable (jittering site locations within tiles). No data-path changes.

Implementation actions (detailed):
1) **Gate + input narration.**
   - Updated the gate receipt log to clarify authorization (S5 assignments + world_countries geometry).
   - Added `S6: jitter inputs resolved (s5_site_tile_assignment + tile_bounds + world_countries)` and a world_countries load count.
   - Added a sampling statement: `uniform-in-tile bounds with point-in-country check (max_attempts=64)` to explain the loop behavior.

2) **Progress semantics.**
   - Changed the progress label to `S6 jitter progress sites_processed (location per site)`.

3) **Output narrative.**
   - Updated the run report log to `jitter summary + determinism receipt`.

Notes:
- RNG event emission and writer sort are unchanged.
- No per-site logging added; progress remains periodic.

### Entry: 2026-01-14 02:12

Design element: S6 contract review + pre-implementation plan (uniform in-pixel jitter with bounded resample, point-in-country).

Sources reviewed (binding/authority):
1) `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s6.expanded.md`
2) `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml` (S6 datasets and RNG log paths/partitions)
3) `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml` (S6 table + run report schema anchors)
4) `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml` (RNG event envelope for `in_cell_jitter`)

Contract review notes (explicit obligations from the spec + contracts):
- Inputs (sealed): `s5_site_tile_assignment`, `tile_index`, `world_countries`, `s0_gate_receipt_1B` (No PASS -> No read). S6 must rely on the gate receipt only and not re-hash the 1A bundle.
- Output dataset: `s6_site_jitter` in `data/layer1/1B/s6_site_jitter/seed={seed}/parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/` with partitions `[seed, manifest_fingerprint, parameter_hash]`, writer sort `[merchant_id, legal_country_iso, site_order]`, PK `[merchant_id, legal_country_iso, site_order]`. Columns strict. Must include `tile_id`, `delta_lat_deg`, `delta_lon_deg`, and `manifest_fingerprint` column equal to path token.
- Output control report: `s6_run_report` in `reports/layer1/1B/state=S6/seed={seed}/parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/s6_run_report.json`. Schema allows additional fields; only `seed`, `manifest_fingerprint`, `parameter_hash` are required, but spec expects coverage metrics and attempt stats.
- RNG log: `rng_event_in_cell_jitter` under `logs/layer1/1B/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/`. Each attempt emits one event with `blocks=1` and `draws="2"`. Events include `merchant_id`, `legal_country_iso`, `site_order`, `delta_lat_deg`, `delta_lon_deg`, `sigma_lat_deg`, `sigma_lon_deg` per schema; envelope requires `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`, counters, and `ts_utc`.
- Behavioral requirements: uniform sampling inside pixel rectangle, point-in-country predicate must pass, bounded resample with `MAX_ATTEMPTS=64` (explicit in spec). If a site exhausts attempts, abort the state (no publish).
- Identity: path-embed equality for `manifest_fingerprint` is binding; file order is non-authoritative; writer sort is binding.
- FK: `(legal_country_iso, tile_id)` must exist in `tile_index` for the same `parameter_hash`.

Ambiguities / decisions to resolve before coding:
1) Pixel bounds authority: S6 spec text says bounds/centroids come from `tile_index`, but `tile_index` schema does not contain bounds; `tile_bounds` (S1 companion) does. Plan proposal is to use `tile_bounds` for min/max + centroid while still validating FK against `tile_index`. Need confirmation if this is acceptable or if the spec should be clarified to explicitly reference `tile_bounds`.
2) Geometry semantics: the point-in-country test must follow S1 rules (dateline handling). I plan to reuse the S1 world_countries geometry helpers to avoid divergence; confirm if any additional topology rules are expected beyond S1.

Pre-implementation plan (detailed, step-by-step):
1) Gate preflight:
   - Resolve `s0_gate_receipt_1B` via Dictionary and validate it; ensure it authorizes sealed inputs (S5, tile_index, world_countries, and tile_bounds if used).
   - Abort with explicit error if the receipt is missing or fails schema validation.
2) Resolve inputs/outputs through the Dictionary:
   - Inputs: `s5_site_tile_assignment`, `tile_index`, `world_countries`, and (if confirmed) `tile_bounds`.
   - Outputs: `s6_site_jitter`, `s6_run_report`, `rng_event_in_cell_jitter`.
3) Geometry lookup strategy (performance-critical):
   - Avoid full materialization of `tile_bounds` (very large).
   - Build a filtered bounds table by joining S5 to `tile_bounds` on `(legal_country_iso, tile_id)` using a disk-backed join (DuckDB or Polars scan + streaming join). Keep only needed tiles, then stream through the joined rows in writer order.
   - Validate FK to `tile_index` using either a lightweight existence check (e.g., bloom or join) or by enforcing the FK through the join with `tile_index` if needed for audit counters.
4) World countries:
   - Load `world_countries` into an in-memory per-ISO polygon map once; reuse for all sites.
   - Ensure point-in-country uses the S1 dateline-aware predicate.
5) RNG setup:
   - Resolve `run_id` from run receipt and initialize RNG audit log (if required by the shared RNG utilities).
   - Use deterministic per-site substreams derived from `(merchant_id, legal_country_iso, site_order)` to allow parallelism without changing results.
6) Main loop (streamed):
   - For each S5 site (with bounds and centroid), run up to `MAX_ATTEMPTS=64`:
     a) Draw `u_lon`, `u_lat` from open-interval U(0,1).
     b) Map to pixel rectangle -> `(lon*, lat*)`.
     c) Check point-in-country predicate. If fail, log RNG event for the attempt and resample.
     d) If pass, compute `delta_lon_deg = lon* - centroid_lon_deg` and `delta_lat_deg = lat* - centroid_lat_deg`.
     e) Emit the final RNG event (for the accepted attempt) with `blocks=1`, `draws="2"`, sigma=0.0, and deltas.
     f) Emit one row in `s6_site_jitter` with the deltas and manifest_fingerprint.
   - If attempts exhausted for any site, abort the state with an explicit error and no publishes.
7) Output handling:
   - Write `s6_site_jitter` into a temp partition, enforce writer sort, then atomically move into the dictionary path.
   - Append RNG events to JSONL files under the log path; ensure counters and event totals reconcile.
   - Write `s6_run_report` with counts: sites_total, rng events_total, attempts histogram (if computed), outside-country count, and determinism receipt fields (non-authoritative but useful).
8) Validation:
   - Validate outputs against the schema anchors and enforce path-embed equality for manifest_fingerprint.
   - Ensure the S6 dataset row count equals S5 row count and RNG events >= rows (attempts).
9) Logging/observability:
   - Log start/end with identity, chunk progress, attempts rate, and counts for outside-country resamples to keep the run log interpretable without flooding.

Performance risk notes (to avoid pitfalls):
- Tile geometry lookup is the critical scale risk; a naive full read of `tile_bounds` is too large. The plan uses a filtered join keyed by S5 tiles to keep memory bounded.
- RNG logging can explode if resamples are frequent; implement progress throttling and include attempt hist in the run report to detect pathological cases.
- Point-in-country checks must be vectorized or cached per-country where possible to avoid per-point overhead; reuse pre-built geometries and prepared predicates.

### Entry: 2026-01-14 02:19

Design element: Finalize S6 implementation decisions before coding (geometry authority, join strategy, RNG substreams).

Decision set (explicit, with reasoning):
1) **Bounds authority (tile_bounds vs tile_index).**
   - Choice: Use `tile_bounds` for min/max and centroids, and still enforce the FK against `tile_index`.
   - Reasoning: `tile_bounds` is the only dataset carrying min/max bounds and centroids; `tile_index` lacks bounds. The spec text mentions `tile_index` as the geometry authority, but the dictionary and schema show bounds in `tile_bounds`. Using `tile_bounds` for geometry matches the actual contract shapes; we still validate that `(legal_country_iso, tile_id)` exists in `tile_index` for the same `parameter_hash` so the FK rule is enforced.

2) **Point-in-country semantics.**
   - Choice: Reuse S1 geometry helpers (antimeridian split + prepared polygons) and apply the same predicate semantics used in S1.
   - Reasoning: S1 already establishes the canonical dateline handling for `world_countries`. Reusing it keeps the country predicate consistent across S1 and S6 and avoids divergent topological interpretations.

3) **Join/lookup strategy for `tile_bounds`.**
   - Choice: Use a disk-backed join (DuckDB or Polars lazy scan) between `s5_site_tile_assignment` and `tile_bounds` keyed by `(legal_country_iso, tile_id)` to stream per-site bounds without loading all tiles into memory.
   - Reasoning: `tile_bounds` is extremely large; a full read or in-memory map is not feasible. A streaming join confines memory to the current batch and keeps I/O proportional to S5’s actual tile usage.

4) **RNG substream derivation.**
   - Choice: Derive per-site RNG substreams from `(merchant_id, legal_country_iso, site_order)` using the same Philox2x64-10 machinery and hashing conventions as S5 (labelled for S6).
   - Reasoning: The spec demands deterministic substreams keyed by site identity; reusing the existing RNG primitives keeps the implementation aligned with the layer’s RNG envelope and substream/counter model.

Next step:
- Proceed to implement S6 runner + CLI + Makefile wiring using the above decisions, then run `make segment1b-s6` on the current run_id and iterate to green.

### Entry: 2026-01-14 02:41

Design element: S6 implementation (runner + CLI + Makefile wiring).

Implementation actions (step-by-step with rationale):
1) **Runner scaffolding (new S6 module).**
   - Added `packages/engine/src/engine/layers/l1/seg_1B/s6_site_jitter/runner.py` with a dedicated S6 runner.
   - Mirrored the S5/S1 runner patterns for contract loading, run receipt resolution, gate receipt verification, and deterministic publish (atomic move, hash-based immutability guard).
   - Rationale: keep S6 consistent with prior 1B states and ensure deterministic, resumable behavior.

2) **Geometry authority alignment (tile_bounds + tile_index).**
   - Implemented per-batch loading of `tile_bounds` (min/max + centroids) using Parquet filters keyed by `(country_iso, tile_id)` and retained explicit FK checks against `tile_index` via a per-country LRU cache.
   - Rationale: geometry lives only in `tile_bounds`; FK enforcement still required by spec and validated against `tile_index` for the same `parameter_hash`.

3) **Point-in-country predicate (S1 semantics).**
   - Copied the S1 antimeridian split helpers and prepared per-country polygons for fast point checks; predicate uses `prepared.contains` or boundary `touches`.
   - Rationale: ensure consistent dateline handling with S1 and avoid divergent geometry logic.

4) **RNG substreams and event logging.**
   - Implemented per-site Philox2x64-10 substreams keyed by `(merchant_id, legal_country_iso, site_order)` with one event per attempt (`blocks=1`, `draws=\"2\"`), plus trace log support and audit log idempotency.

### Entry: 2026-01-14 10:56

Design element: S6 rng_trace_log append strategy to satisfy S9 reconciliation (trace missing when event log exists).
Summary: S6 currently suppresses trace emission when `rng_trace_log` already exists. That keeps immutability, but breaks S9 because S6 `rng_event_in_cell_jitter` exists without matching trace rows. The spec requires trace coverage per event family, so we need to append missing S6 trace rows in a controlled, idempotent way.

Plan (before implementation, detailed and explicit):
1) **Detect trace coverage for S6 substream.**
   - Load `rng_trace_log` if it exists for `{seed, parameter_hash, run_id}`.
   - Scan for any row with `module=1B.S6.jitter` and `substream_label=in_cell_jitter`.
   - If any exist, treat S6 trace as already emitted and skip new trace writes (avoid duplicate rows).

2) **Decide trace emission mode (create vs append vs skip).**
   - If trace file **does not exist**, emit trace rows as normal to a temp file and publish atomically (current behavior).
   - If trace file **exists but lacks S6 substream**, append S6 trace rows to the existing file (append-only, no deletion).
   - If trace file **exists and already has S6 substream**, skip trace emission (idempotent).

3) **If event log exists but trace is missing, rebuild trace from events.**
   - S6 may skip event emission if `rng_event_in_cell_jitter` already exists.
   - In that case, rebuild the trace by streaming existing event JSONL rows from the event log directory and feeding them into `RngTraceAccumulator` to emit **one trace row per event** (cumulative totals).
   - Append those rows to `rng_trace_log` when `trace_mode=append`, or write to temp then publish when `trace_mode=create`.
   - Abort with a clear error if the event log directory exists but no JSONL event rows are found (trace cannot be reconstructed).

4) **Ensure append-only integrity and logging clarity.**
   - Never delete or overwrite existing `rng_trace_log`.
   - Log which mode is used: `trace=create`, `trace=append_from_existing_events`, or `trace=skip_existing_substream`.
   - Record counts for appended trace rows and the number of event rows processed so S9 troubleshooting is straightforward.

5) **Preserve deterministic results.**
   - Trace rows are deterministic from event log content; append order follows file sort order (`*.jsonl` lexicographic) to keep byte stability.
   - Ensure trace rows embed the same `seed` and `run_id` as path tokens (path↔embed equality).

Expected outcome:
 - S6 emits or appends `rng_trace_log` rows for `in_cell_jitter` so S9 reconciliation passes.
 - Immutability is preserved: existing trace rows are never altered, only appended when missing.
 - Reruns remain idempotent: if S6 trace already exists, no new rows are appended.

### Entry: 2026-01-14 11:06

Design element: S6 rng_trace_log append implementation (trace rebuild from existing events).
Summary: Implemented the append-only trace handling so S6 can emit trace rows even when the event log already exists, without overwriting the shared trace log.

Changes applied (explicit, step-by-step):
1) **Added shared JSONL readers and trace detection helpers.**
   - Introduced `_iter_jsonl_paths`, `_iter_jsonl_rows`, `_trace_has_substream`, and `_append_trace_from_events` in `packages/engine/src/engine/layers/l1/seg_1B/s6_site_jitter/runner.py`.
   - These allow S6 to detect whether its substream already appears in `rng_trace_log` and to rebuild trace rows from existing event logs when needed.

2) **Replaced the old trace suppression logic with a three-mode controller.**
   - `trace_mode=create` when `rng_trace_log` does not exist (write temp + atomic publish).
   - `trace_mode=append` when `rng_trace_log` exists but lacks the S6 substream (append-only).
   - `trace_mode=skip` when `rng_trace_log` already contains S6 rows (idempotent).
   - Logged the chosen mode for operator visibility.

3) **Prevented recomputed-trace drift when event logs already exist.**
   - If `rng_event_in_cell_jitter` already exists and trace is missing, S6 now streams the existing JSONL event rows and appends one trace row per event via `RngTraceAccumulator`.
   - This keeps trace totals aligned to the authoritative event log bytes instead of recomputed events.

4) **Publish behavior adjusted for append vs create.**
   - When `trace_mode=create`, the temp trace file is atomically published to the trace path.
   - When `trace_mode=append`, no publish step occurs; rows are appended directly to the existing trace log.

Expected effect:
 - S6 trace coverage will exist for `in_cell_jitter` even on reruns with pre-existing event logs.
 - S9 reconciliation will see matching event totals and trace totals for the S6 substream.

### Entry: 2026-01-14 11:15

Design element: S6 rerun to append missing trace rows (run_id=b4235da0cecba7e7ffd475f8ffb23906).
Summary: Executed S6 with the new trace-append logic to repair missing trace coverage for `in_cell_jitter` without re-emitting events.

Execution details (explicit):
1) **Run invocation:** `make segment1b-s6 RUN_ID=b4235da0cecba7e7ffd475f8ffb23906`.
2) **Trace mode:** `append` (existing `rng_trace_log` detected, S6 substream missing).
3) **Event handling:** `rng_event_in_cell_jitter` already existed; S6 skipped event emission and rebuilt trace rows from the existing event JSONL files.
4) **Trace append result:** appended `30115` trace rows to the existing trace log.
5) **Publish behavior:** `s6_site_jitter` partition already existed and matched (identical bytes); no overwrite performed.
6) **Outcome:** `S6 1B complete` logged; run report updated with consistent counts and determinism receipt.

Expected impact:
- S9 can now reconcile S6 events against `rng_trace_log` for the `(module=1B.S6.jitter, substream_label=in_cell_jitter)` key.
   - Rationale: spec requires deterministic substreams and per-attempt event logging; trace/audit logs align with existing RNG governance patterns.

5) **Output dataset + run report.**
   - Emitted `s6_site_jitter` in writer sort order (PK + sort checks), enforced `manifest_fingerprint` path/embed equality, and built `s6_run_report` with totals, attempt histogram, per-country counts, and PAT counters.
   - Rationale: meets schema anchors and provides operational insight without altering identity-bearing outputs.

6) **CLI + Makefile wiring.**
   - Added `packages/engine/src/engine/cli/s6_site_jitter.py` and `segment1b-s6` target in `makefile`, with standard args for contracts layout/root, runs root, external roots, and run_id selection.
   - Rationale: keep run ergonomics consistent with other 1B states.

Implementation notes / risk tracking:
- **Tile bounds filtering:** uses pyarrow filters when available; polars fallback filters in-memory. If pyarrow is missing or the filter list is huge, performance could degrade (tracked in run log + PAT counters).
- **Country geometry preparation:** loads `world_countries` fully into memory (expected manageable). If memory pressure appears, revisit with per-country streaming.
- **Resample cap:** fixed at MAX_ATTEMPTS=64 per spec; if any site exhausts attempts, the state aborts with `E613_RESAMPLE_EXHAUSTED` and nothing is published.

Files changed/added:
- `packages/engine/src/engine/layers/l1/seg_1B/s6_site_jitter/runner.py`
- `packages/engine/src/engine/cli/s6_site_jitter.py`
- `makefile` (SEG1B_S6 args/cmd + target)

### Entry: 2026-01-14 02:44

Design element: S6 run failure while loading tile_bounds (pyarrow filter API mismatch).

Observed failure (verbatim):
- `TypeError: ParquetDataset.read() got an unexpected keyword argument 'filters'` at `_load_tile_bounds_country`.
- This happened during the first S6 run (`make segment1b-s6`) when attempting to load a filtered subset of `tile_bounds` for the batch.

Root cause analysis (explicit):
1) `pyarrow.parquet.ParquetDataset.read()` in the installed pyarrow version does not accept a `filters` argument (it exists in newer `pyarrow.dataset` APIs).
2) The S6 implementation used `ParquetDataset.read(..., filters=...)`, which is not supported in this environment.

Decision / fix plan (before code):
1) Switch to `pyarrow.dataset.dataset(...).to_table(filter=...)` when pyarrow is available so predicate pushdown works with the expected API.
2) Keep a fallback path: if dataset filters are unavailable, read the full table and filter in-memory as a safety net (still correct, possibly slower).
3) Re-run S6 after the fix and document any further errors, focusing on performance and correctness.

### Entry: 2026-01-14 02:45

Design element: Implement S6 tile_bounds filter fix (pyarrow.dataset + fallback).

Implementation details:
1) Added `pyarrow.dataset as ds` to the optional pyarrow import block.
2) Updated `_load_tile_bounds_country`:
   - Primary path: `ds.dataset(...).to_table(..., filter=ds.field(\"tile_id\").isin(tile_ids))` for predicate pushdown.
   - Fallback path: `ParquetDataset.read()` + in-memory `np.isin` filter when `pyarrow.dataset` is unavailable.
3) Kept the in-memory filter as a correctness fallback; it may be slower but avoids hard failure on older pyarrow builds.

Next step:
- Re-run `make segment1b-s6` and continue fixing/logging until green.

### Entry: 2026-01-14 02:47

Design element: S6 rerun failure due to rng_trace_log immutability collision.

Observed failure (verbatim):
- `EngineFailure: F4:E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL` at `_atomic_publish_file(trace_tmp, trace_path, ...)`.

Root cause analysis:
1) `rng_trace_log` is a shared log path keyed only by `{seed, parameter_hash, run_id}`.
2) S5 already published `rng_trace_log` for this run_id, so S6 attempting to write its own trace file triggers the immutability guard.

Decision / fix plan (before code):
1) Treat `rng_trace_log` as optional for S6 (spec notes trace is optional).
2) If `trace_path` already exists, skip trace emission and log that S6 is leaving the existing trace intact.
3) Only write trace when the log is absent (first RNG publisher) to preserve immutability.

Next step:
- Implement trace suppression logic and re-run S6.

### Entry: 2026-01-14 02:48

Design element: Implement trace suppression when rng_trace_log already exists.

Implementation details:
1) Added `trace_enabled = not trace_path.exists()` in S6 runner and logged a note when trace is skipped.
2) Guarded trace accumulator writes and trace file publish behind `trace_enabled`.
3) Preserved RNG events + run report emission regardless of trace log presence.

Next step:
- Re-run `make segment1b-s6` to confirm the state completes with existing trace log.

### Entry: 2026-01-14 02:49

Design element: S6 rerun failure due to rng_event_in_cell_jitter immutability collision.

Observed failure (verbatim):
- `EngineFailure: F4:E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL` at `_atomic_publish_dir(event_tmp, event_root, ...)`.

Root cause analysis:
1) The RNG event log includes per-attempt `ts_utc`, so re-running S6 with the same `run_id` produces a different JSONL payload.
2) Since `rng_event_in_cell_jitter` is partitioned by `{seed, parameter_hash, run_id}`, the immutability guard correctly rejects a second publish for the same run_id.

Decision / fix plan (before code):
1) Treat existing RNG event log as authoritative for the run_id; if `event_root` already exists, skip event emission and publishing.
2) Continue computing outputs and `s6_run_report` for the rerun (counts are deterministic), but do not overwrite the existing log.
3) Log the skip so operators understand why no event file was written.

Next step:
- Implement event-log suppression and re-run S6 to confirm completion.

### Entry: 2026-01-14 02:50

Design element: Implement event-log suppression when rng_event_in_cell_jitter already exists.

Implementation details:
1) Added `event_enabled = not event_root.exists()` with a log line that S6 will skip RNG event emission when the log already exists.
2) Guarded event JSONL writes and the event publish step behind `event_enabled`.
3) Left run-report computation intact (counts are deterministic) so reruns can still produce a report without altering existing logs.

Next step:
- Re-run `make segment1b-s6` and confirm completion.

### Entry: 2026-01-14 02:52

Design element: S6 run completion + spec compliance check.

Execution details:
1) **Run invocation:** `make segment1b-s6` (RUNS_ROOT defaults to `runs/local_full_run-5`).
2) **Run identity:** `run_id=b4235da0cecba7e7ffd475f8ffb23906`, `seed=42`, `parameter_hash=56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7`, `manifest_fingerprint=8ef8eaa92e30fb40d269fa00dc3551899d99c4a1b083150592c96849755ac9a1`.
3) **Trace/event log posture:** both `rng_event_in_cell_jitter` and `rng_trace_log` already existed from the earlier attempt; S6 skipped emitting/publishing those logs to preserve immutability, as documented.
4) **Output dataset:** `s6_site_jitter` partition already existed and matched byte-for-byte, so the runner skipped publish (immutability guard OK).
5) **Run report:** `s6_run_report.json` written successfully; keys include `seed`, `manifest_fingerprint`, `parameter_hash`, `run_id`, `counts`, `attempt_histogram`, `by_country`, and `pat`.

Spec compliance checks (explicit):
- Row parity: `sites_total=27942` equals S5 row count for the run; no missing/extra rows reported.
- RNG budget: `events_total=30115` with `draws_total="60230"` and `blocks_total=30115` satisfy the fixed `draws=2` / `blocks=1` per event expectation.
- Gate receipt verified; sealed `world_countries` path matched the dictionary resolution.
- Writer sort and PK guard checks remained enabled (no violations logged).

Outcome:
- S6 is green for this run_id; ready to move to S7 planning once requested.

## S7 - Site Synthesis (S7.*)

### Entry: 2026-01-14 11:38

Design element: S7 logging retrofit implementation (site synthesis story logs).
Summary: Updated S7 logs to narrate the join/synthesis flow and explain what the progress counters represent. No data-path changes.

Implementation actions (detailed):
1) **Gate + input narration.**
   - Updated the gate receipt log to clarify outlet_catalogue authorization.
   - Added `S7: synthesis inputs resolved (S5 assignments + S6 jitter + 1A outlet_catalogue)`.
   - Added `input row counts` log for S5, S6, and outlet_catalogue to make parity checks explicit.

2) **Progress semantics.**
   - Changed the progress label to `S7 synthesis progress sites_processed (site records built)`.

3) **Output narrative.**
   - Updated the publish log to `site synthesis published`.
   - Updated the run summary log to `parity + validation counters`.

Notes:
- S7 validation behavior and output schema are unchanged.
- Logging remains phase-based and avoids per-row noise.

### Entry: 2026-01-14 03:27

Design element: S7 contract review + pre-implementation plan (deterministic site synthesis).

Contract review (authoritative surfaces read):
1) **State spec:** `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s7.expanded.md`.
   - Binding inputs: `s5_site_tile_assignment`, `s6_site_jitter`, `tile_bounds`, `outlet_catalogue` (1A egress; gated).
   - Binding outputs: `s7_site_synthesis` (parquet; `[seed, manifest_fingerprint, parameter_hash]`).
   - Determinism: RNG-free; no new RNG logs; write-once + atomic move.
   - Must enforce: S5↔S6 1:1 join, inside-pixel check via S1 bounds, 1A coverage parity (No PASS → No read), and path-embed equality where lineage columns exist.
   - Optional: point-in-country reassertion (MAY).
2) **Dataset Dictionary:** `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml`.
   - `s7_site_synthesis` path/partitions/sort: `data/layer1/1B/s7_site_synthesis/seed={seed}/parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/`.
   - `s7_run_summary` path: `reports/layer1/1B/state=S7/seed={seed}/parameter_hash={parameter_hash}/manifest_fingerprint={manifest_fingerprint}/s7_run_summary.json`.
3) **Schemas:** `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml`.
   - `#/plan/s7_site_synthesis`: columns are `{merchant_id, legal_country_iso, site_order, tile_id, lon_deg, lat_deg}`, `columns_strict=true`.
   - `#/control/s7_run_summary`: required keys `{seed, manifest_fingerprint, parameter_hash}` (additional fields allowed).
4) **1A egress schema:** `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.1A.yaml#/egress/outlet_catalogue` for coverage parity keys `(merchant_id, legal_country_iso, site_order)` and manifest_fingerprint column.

Brainstorm & decision notes (detailed):
- **Join strategy (S5↔S6):** 
  - Option A: Polars lazy scan + inner join + `collect(streaming=True)` for memory control; risk: join may not preserve writer-sort, requiring a full sort on output.
  - Option B: Manual merge-join on sorted inputs (S5/S6 already writer-sorted by the PK) to preserve order without a full sort; more implementation complexity but best for large datasets.
  - **Tentative choice:** implement a merge-join iterator (or a streaming join that preserves left order) so output can be written in writer-sort without a full re-sort; fall back to a controlled sort if streaming join cannot guarantee order in this environment.
- **Tile geometry lookup:** 
  - Tile bounds are huge (S1 tile_bounds ~ hundreds of millions of rows), so loading full bounds is not viable.
  - Reuse S6’s per-country `tile_bounds` loader (S1 wrote `tile_bounds/country=XX/part-*.parquet`) and load only tile_ids needed for each country encountered; cache per-country bounds map to avoid repeated I/O.
  - If a required tile_id is missing for a country, fail with an explicit S7 error and include missing IDs in the payload.
- **Inside-pixel check:** 
  - Use S1 bounds (min/max) and same antimeridian handling as S1/S6 to avoid drift. This is an acceptance gate (fail-closed).
  - Optional point-in-country check is heavier (needs world_countries geometry); default to off unless explicitly requested.
- **Outlet coverage parity:** 
  - Gate read via `s0_gate_receipt_1B` (manifest_fingerprint match + sealed_inputs includes outlet_catalogue).
  - Enforce 1:1 join between S5 site keys and outlet_catalogue keys; report `coverage_1a_ok_count`/`coverage_1a_miss_count` and abort on any miss.
  - Track `path_embed_mismatches` from outlet_catalogue manifest_fingerprint column (if any).
- **Run summary content:** 
  - Emit `s7_run_summary.json` with counters similar to spec example (`sizes`, `validation_counters`, `gates` with `flag_sha256_hex`).
  - Store `seed`, `manifest_fingerprint`, `parameter_hash` at top-level per schema anchor.

Pre-implementation plan (step-by-step):
1) **Preflight + gate discipline:**
   - Load dictionary + schema pack; resolve run context.
   - Validate `s0_gate_receipt_1B` for the manifest_fingerprint and ensure sealed_inputs includes `outlet_catalogue`; store `flag_sha256_hex` for run summary.
2) **Resolve inputs/outputs by dictionary IDs:**
   - Inputs: `s5_site_tile_assignment`, `s6_site_jitter`, `tile_bounds`, `outlet_catalogue`.
   - Outputs: `s7_site_synthesis`, `s7_run_summary`.
3) **Row counts + 1:1 parity checks:**
   - Count S5/S6 rows for early parity check; abort if mismatched.
4) **Deterministic join + reconstruction:**
   - Stream S5↔S6 by PK; reconstruct `(lon_deg, lat_deg) = centroid + delta`.
   - Enforce inside-pixel check using bounds from tile_bounds lookup; abort on failure with context.
5) **Outlet coverage parity:**
   - Join/compare S5 keyset to outlet_catalogue keyset; abort on any missing coverage.
6) **Write outputs:**
   - Emit S7 rows in writer-sort order `[merchant_id, legal_country_iso, site_order]`.
   - Publish via stage → fsync → atomic move; no RNG logs.
7) **Emit run summary:**
   - Write `s7_run_summary.json` with counters, parity flags, and `flag_sha256_hex` gate value.

Open questions (need confirmation before coding):
1) **Optional point-in-country check:** Should we enable the optional deterministic point-in-country check (adds geometry cost), or leave it disabled for performance?
2) **Path-embed mismatch handling:** If `outlet_catalogue.manifest_fingerprint` or `s6_site_jitter.manifest_fingerprint` mismatches the path token, should S7 hard-fail immediately (strict) or count + fail at the end (still fail-closed either way)?

### Entry: 2026-01-14 07:21

Design element: S7 implementation decisions confirmed + execution posture.

Decision outcomes (explicit):
1) **Point-in-country check:** Leave **disabled** for S7 by default. Rationale: spec marks it MAY; S7 already enforces inside-pixel and tile FK, and avoiding world geometry re-loads protects throughput and memory.
2) **Path-embed mismatches:** **Hard-fail immediately** on the first mismatch (fail-fast). Rationale: path-embed equality is a MUST and any mismatch invalidates the partition; continuing wastes time and risks partial outputs.

Implementation approach updates (detailed):
- **Join strategy:** Start with a deterministic streaming join on S5 and S6 keyed by `[merchant_id, legal_country_iso, site_order]` using a per-row merge-join across sorted scans. This preserves writer-sort with no full shuffle. If multiple files break global ordering, detect order violations and (for now) fail with an actionable error rather than silently resorting large volumes; we can add an external sort fallback if that becomes necessary.
- **Tile bounds lookup:** Reuse S6’s `tile_bounds` loader to read per-country parquet under `tile_bounds/country=XX`, filter to needed tile_ids, and cache per-country bounds map. This avoids loading the full S1 geometry surface.
- **Inside-pixel checks:** Use the same antimeridian logic and inclusive bounds checks as S6/S1; this is a hard acceptance gate (fail-closed on any out-of-bounds point).
- **Coverage parity:** Gate read via `s0_gate_receipt_1B` (manifest_fingerprint and sealed_inputs check). Enforce 1:1 coverage against `outlet_catalogue` and preserve site_order; fail fast on any missing key.
- **Run summary:** Emit `s7_run_summary.json` with top-level `{seed, manifest_fingerprint, parameter_hash}` and additional counters (`sizes`, `validation_counters`, `gates.flag_sha256_hex`) to mirror the spec’s run-summary example.

### Entry: 2026-01-14 07:25

Design element: S7 implementation kickoff (detailed in-process reasoning before code).

Brainstorm & decision checkpoints (before coding):
- **S5/S6 join mechanics:** 
  - Option A: load both tables with Polars and `join` then `sort` by PK. Simple but may materialize large frames and sort globally (RAM heavy).
  - Option B: streaming merge-join over sorted scans (S5/S6 writer-sorted by PK), preserving order and avoiding a full shuffle.
  - **Chosen:** Option B, with explicit sort-order guards. If a partition is not globally sorted (multi-file disorder), fail with an actionable error rather than silently re-sorting a huge table (keeps determinism and avoids hidden memory blowups).
- **Outlet coverage parity check:** 
  - Option A: load outlet_catalogue into a set and check membership; O(N) memory.
  - Option B: sorted merge-compare using an iterator on outlet_catalogue in writer-sort; fail fast on any mismatch.
  - **Chosen:** Option B to cap memory and remain deterministic.
- **Tile bounds retrieval:** 
  - Option A: load full `tile_bounds` (too large).
  - Option B: per-country partial load for tile_ids present in the current S5 batch (pattern used in S6).
  - **Chosen:** Option B with an LRU cache; also enforce missing-tile FK errors immediately.
- **Inside-pixel check:** 
  - Use S1 bounds with antimeridian-aware check (same logic as S6) and enforce inclusive bounds.
  - Fail-closed on first out-of-bounds to avoid partial outputs.

Immediate implementation steps (ordered):
1) Create `packages/engine/src/engine/layers/l1/seg_1B/s7_site_synthesis/runner.py` with merge-join loop, bounds lookup, parity checks, and run summary emission.
2) Add CLI wrapper `packages/engine/src/engine/cli/s7_site_synthesis.py` to wire `run_s7`.
3) Extend `makefile` with `SEG1B_S7_*` variables and `segment1b-s7` target.

### Entry: 2026-01-14 07:55

Design element: S7 implementation (runner + CLI + Makefile) with deterministic merge-join, gate discipline, and dictionary/schema coherence checks.

Implementation actions and reasoning (detailed, step-by-step):
1) **Module scaffold + CLI wiring.**
   - Created `packages/engine/src/engine/layers/l1/seg_1B/s7_site_synthesis/__init__.py` for the new state module.
   - Added `packages/engine/src/engine/cli/s7_site_synthesis.py` to call `run_s7`, using run_receipt selection (latest by mtime if `--run-id` absent) and consistent EngineConfig wiring (contracts layout/root + runs root).
   - Updated `makefile` with `SEG1B_S7_*` variables + `segment1b-s7` target so S7 can be run in isolation.

2) **Run identity and contract loading.**
   - Implemented run_receipt resolution: validate `run_id` exists and the run_receipt path name matches the embedded run_id to avoid cross-run identity leakage.
   - Loaded dictionary + schema packs (`schemas.1B.yaml` and `schemas.1A.yaml`) and logged the resolved contract roots for auditability.
   - Added a dictionary/schema coherence check (`_assert_schema_ref`) that verifies each referenced `schema_ref` anchor exists; missing/invalid anchors hard-fail with `E711_DICT_SCHEMA_MISMATCH` before any data read.

3) **Gate discipline (No PASS ￫ No read).**
   - Resolved `s0_gate_receipt_1B` by dictionary ID + `manifest_fingerprint`, validated the receipt schema, and checked the manifest_fingerprint in the payload matches the path token.
   - Verified `sealed_inputs` includes `outlet_catalogue` (fail-closed if missing).
   - Recorded the receipt’s `flag_sha256_hex` into the run summary for traceability.

4) **Input resolution and preflight counts.**
   - Resolved inputs via Dictionary IDs only: `s5_site_tile_assignment`, `s6_site_jitter`, `tile_bounds`, `outlet_catalogue`.
   - Resolved outputs via Dictionary IDs: `s7_site_synthesis`, `s7_run_summary`.
   - Added row-count preflight using Parquet metadata (pyarrow when available): abort if S5 vs S6 or S5 vs outlet_catalogue counts mismatch (prevents expensive streaming when parity already fails).

5) **Deterministic merge-join implementation (S5 ￫ S6 ￫ outlet).**
   - Implemented a streaming merge-join that preserves writer-sort order and avoids a full global sort (critical for large datasets).
   - Enforced writer-sort monotonicity and PK uniqueness while scanning:
     - S5/S6/outlet duplicate keys -> `E703_DUP_KEY`.
     - Out-of-order keys -> `E706_WRITER_SORT_VIOLATION`.
   - Enforced 1:1 S5⇄S6 parity (missing/extra rows -> `E701_ROW_MISSING` / `E702_ROW_EXTRA`).
   - Enforced S6 path-embed equality (manifest_fingerprint) and outlet path-embed equality (manifest_fingerprint + global_seed when present) -> `E705_PARTITION_OR_IDENTITY` on first mismatch (fail-fast per decision).

6) **Geometry reconstruction and inside-pixel checks.**
   - Reused the S1 `tile_bounds` per-country partitioning: compute required tile_id sets per batch, then load only those tile IDs for each country.
   - Added a small LRU cache (`CACHE_COUNTRIES_MAX=6`) to keep hot country bounds in memory, reducing repeated IO without ballooning RAM.
   - Reconstructed `lon_deg/lat_deg` from centroid + deltas and validated inclusive bounds with antimeridian-aware longitude handling.
   - Missing `(country_iso, tile_id)` or reconstructed point outside pixel -> `E709_TILE_FK_VIOLATION` / `E707_POINT_OUTSIDE_PIXEL` (fail-closed).
   - Point-in-country check intentionally **disabled** (MAY in spec; performance-sensitive).

7) **Output publishing and run summary.**
   - Wrote output rows in batches (`BATCH_SIZE=200_000`) to parquet with fixed schema columns and zstd compression, maintaining writer-sort order.
   - Published `s7_site_synthesis` via stage ￫ fsync ￫ atomic move; existing partitions must be byte-identical (immutability guard).
   - Emitted `s7_run_summary.json` with required identity, size parity fields, validation counters, by_country rollups, gate flag, PAT metrics, cache stats, and ingress_versions; validated against `schemas.1B.yaml#/control/s7_run_summary` before atomic publish.

8) **State-level correctness posture captured in code.**
   - S7 is RNG-free; no RNG logs are emitted.
   - S7 outputs are strictly partitioned by `[seed, manifest_fingerprint, parameter_hash]`, writer-sorted by `[merchant_id, legal_country_iso, site_order]`, and hard-fail on any path/token mismatch or parity violation.

Follow-up note (for run time validation):
- When we run `segment1b-s7`, we must confirm the run log reflects the gate verification, parity counters, and inside-pixel checks, and that the run summary contains all required counters. If any spec-required field is missing in the summary, we must revise before marking S7 green.

### Entry: 2026-01-14 08:05

Design element: S7 schema-ref validation failure (E711) + correction of schema pack selection.

Observed failure (from run log):
- `E711_DICT_SCHEMA_MISMATCH` raised for `outlet_catalogue` because `schema_ref=schemas.1A.yaml#/egress/outlet_catalogue` could not be resolved; the validator reported `KeyError: 'egress'`.

Root-cause analysis (brainstorming + conclusion):
- Hypothesis A: Dictionary schema_ref is wrong (should point to schemas.layer1.yaml).  
  - Checked `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.1A.yaml` and confirmed **`egress.outlet_catalogue` exists** there, so the dictionary reference is correct.
- Hypothesis B: S7 is loading the wrong schema pack for 1A.  
  - Confirmed `load_schema_pack(source, "1A", "layer1")` was used, which loads **`schemas.layer1.yaml`** (no `egress` section), so the resolver fails even though the dictionary is correct.
- Conclusion: **S7 must load the 1A-specific schema pack** (`schemas.1A.yaml`) when validating schema_ref for 1A datasets.

Decision + fix (before re-run):
- Change `load_schema_pack(source, "1A", "layer1")` to `load_schema_pack(source, "1A", "1A")` in the S7 runner so schema_ref validation uses the correct 1A pack.
- Keep the `E711_DICT_SCHEMA_MISMATCH` guard in place; this preserves early detection of dictionary/schema drift while correctly resolving 1A anchors.

Planned validation after fix:
- Re-run `make segment1b-s7 RUN_ID=b4235da0cecba7e7ffd475f8ffb23906`.
- Confirm the run log passes the schema-ref gate and proceeds into merge-join; check that `s7_run_summary.json` contains the required counters (sizes, validation_counters, gate flag).

### Entry: 2026-01-14 08:08

Design element: S7 receipt schema validation failure (UnknownType: table) + validation adapter correction.

Observed failure (from run log):
- `jsonschema.exceptions.UnknownType: Unknown type 'table'` during validation of `s0_gate_receipt_1B`.
- The receipt was being validated using the raw table spec from `schemas.1B.yaml#/validation/s0_gate_receipt`.

Root-cause analysis (brainstorming + conclusion):
- Hypothesis A: The receipt schema must be converted from a **table** spec into a **row/object** schema before Draft202012 validation.  
  - Confirmed S0 uses `_table_row_schema` for the receipt; it does not validate the table spec directly.
- Hypothesis B: S7 should mirror S0's approach to avoid `UnknownType: table`.  
  - Current S7 code uses `_schema_from_pack` (table spec), which Draft202012 rejects.
- Conclusion: **Convert the table spec to a row schema in S7** before validating the receipt payload.

Decision + fix (before re-run):
- Added `_table_row_schema` and `_column_schema` helpers in the S7 runner and switched receipt validation to `receipt_schema = _table_row_schema(schema_1b, "validation/s0_gate_receipt")`.
- Kept `normalize_nullable_schema` so `nullable: true` fields are handled consistently.

Planned validation after fix:
- Re-run `make segment1b-s7 RUN_ID=b4235da0cecba7e7ffd475f8ffb23906`.
- Confirm the receipt schema validates and the run proceeds into S5/S6/outlet merge; check `s7_run_summary.json` for required counters and gate flag.

### Entry: 2026-01-14 08:10

Design element: S7 parquet write failure due to merchant_id dtype overflow + explicit row-orientation enforcement.

Observed failure (from run log):
- Polars raised `ComputeError: could not append value ... of type: i128` when writing batch rows; merchant_id `9230010917950124015` exceeded signed int64.
- Warning: `DataOrientationWarning` because row orientation was inferred during DataFrame construction.

Root-cause analysis (brainstorming + conclusion):
- Hypothesis A: `merchant_id` should be unsigned (uint64) per id64 definition; using `pl.Int64` causes overflow when values exceed signed max.  
  - Confirmed `schemas.layer1.yaml#/$defs/id64` is an unsigned envelope (max 2^64-1).
- Hypothesis B: Polars infers row/column orientation ambiguously; with mixed types this can trigger i128 inference and append failure.
- Conclusion: **Use `pl.UInt64` for merchant_id and force `orient="row"`** so the batch schema is deterministic and matches the id64 contract.

Decision + fix (before re-run):
- Change `merchant_id` column type to `pl.UInt64` in `_write_batch`.
- Add `orient="row"` to DataFrame construction to avoid orientation warnings and schema inference drift.

Planned validation after fix:
- Re-run `make segment1b-s7 RUN_ID=b4235da0cecba7e7ffd475f8ffb23906` and confirm batch writes complete with no dtype warnings or overflow errors.

### Entry: 2026-01-14 08:12

Design element: S7 execution result + spec compliance check (post-fix).

Execution details:
1) **Run invocation:** `make segment1b-s7 RUN_ID=b4235da0cecba7e7ffd475f8ffb23906`.
2) **Identity:** `seed=42`, `parameter_hash=56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7`, `manifest_fingerprint=8ef8eaa92e30fb40d269fa00dc3551899d99c4a1b083150592c96849755ac9a1`, `run_id=b4235da0cecba7e7ffd475f8ffb23906`.
3) **Outputs:** 
   - `s7_site_synthesis` published at `runs/local_full_run-5/b4235da0cecba7e7ffd475f8ffb23906/data/layer1/1B/s7_site_synthesis/seed=42/parameter_hash=56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7/manifest_fingerprint=8ef8eaa92e30fb40d269fa00dc3551899d99c4a1b083150592c96849755ac9a1/`.
   - `s7_run_summary.json` published at `runs/local_full_run-5/b4235da0cecba7e7ffd475f8ffb23906/reports/layer1/1B/state=S7/seed=42/parameter_hash=56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7/manifest_fingerprint=8ef8eaa92e30fb40d269fa00dc3551899d99c4a1b083150592c96849755ac9a1/s7_run_summary.json`.

Spec compliance checks (explicit):
- **Parity counters:** `sites_total_s5=sites_total_s6=sites_total_s7=27942` with `parity_s5_s6_ok=true` and `parity_s5_s7_ok=true`.
- **Coverage gate:** `coverage_1a_miss_count=0`, `coverage_1a_ok_count=27942`, and `gates.outlet_catalogue_pass_flag_sha256` is present.
- **Geometry checks:** `fk_tile_fail_count=0`, `inside_pixel_fail_count=0` (all inside-pixel checks passed).
- **Path/embed:** `path_embed_mismatches=0`.
- **By-country rollup:** present for all ISO partitions observed; no failures logged.

Outcome:
- S7 is green for this run_id and aligns with the binding spec requirements for S7 (deterministic, RNG-free, write-once, parity + coverage checks, inside-pixel enforcement, and required run summary counters).

## S8 - Egress Site Locations (S8.*)

### Entry: 2026-01-14 11:39

Design element: S8 logging retrofit implementation (site_locations egress story logs).
Summary: Added narrative logs so S8's order-free egress and row meaning are clear from the run log. No data-path changes.

Implementation actions (detailed):
1) **Input narration.**
   - Added `S8: egress inputs resolved (S7 site synthesis -> site_locations)`.
   - Added `S8: egress is order-free and fingerprint-scoped` to emphasize ordering semantics.
   - Clarified `S7 rows` log to state that each row maps to one site_locations row.

2) **Progress semantics.**
   - Changed the progress label to `S8 egress progress sites_processed (site_locations rows)`.

3) **Output narrative.**
   - Updated the publish log to mention order-free egress.
   - Updated the run summary log to `parity + validation counters`.

Notes:
- Egress mapping, writer sort enforcement, and validation logic are unchanged.
- Added logs are phase markers only (no log spam).

### Entry: 2026-01-14 08:11

Design element: S8 contract review + pre-implementation plan (egress `site_locations` publish).

Contract review (authoritative surfaces read):
1) **State spec:** `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s8.expanded.md`.
   - Inputs: **only** `s7_site_synthesis` under `[seed, manifest_fingerprint, parameter_hash]`.
   - Output: `site_locations` under `[seed, manifest_fingerprint]` (drop `parameter_hash`).
   - Determinism: RNG-free; **order-free** egress; no 1A/S1 reads; write-once + atomic move.
   - Required validators: row parity S7↔S8, schema conformance, writer sort, path↔embed equality (if lineage fields appear), partition-shift law, order-free pledge.
   - Required run summary keys: identity (seed, manifest_fingerprint, parameter_hash_consumed), sizes (rows_s7/rows_s8/parity_ok), validation_counters (schema/path/sort/order), by_country rollup.
2) **Dataset Dictionary:** `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml`.
   - `site_locations`: path `data/layer1/1B/site_locations/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`, final_in_layer=true, ordering `[merchant_id, legal_country_iso, site_order]`.
   - `s8_run_summary`: path `reports/layer1/1B/state=S8/seed={seed}/manifest_fingerprint={manifest_fingerprint}/s8_run_summary.json`.
3) **Schemas:** `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml`.
   - Input anchor: `#/plan/s7_site_synthesis`.
   - Egress anchor: `#/egress/site_locations` (columns_strict=true).
   - Summary anchor: `#/control/s8_run_summary` (requires seed + manifest_fingerprint; additional fields allowed).
4) **Registry:** `docs/model_spec/data-engine/layer-1/specs/contracts/1B/artefact_registry_1B.yaml` (write-once; atomic move; order-free egress posture).

Brainstorm & decision notes (detailed):
- **Mapping strategy (S7 → S8):**
  - Option A: load S7 into a DataFrame, select columns, then write. Simple but can inflate memory.
  - Option B: stream S7 in writer-sort and emit S8 rows directly (no joins/shuffles).
  - **Chosen:** streaming pass-through (Option B) to keep memory bounded and preserve writer-sort.
- **Schema validation:**
  - S8 must validate `site_locations` rows against `#/egress/site_locations`.
  - Use a row-schema validator (table→row conversion) to avoid `type: table` errors; validate in streaming batches with capped error collection.
- **Writer-sort + duplicates:**
  - S7 should already be sorted, but S8 must still enforce writer-sort and PK uniqueness to satisfy E806/E803.
  - Fail fast on out-of-order or duplicate keys instead of re-sorting (keeps determinism and avoids hidden memory blowups).
- **Path↔embed equality:**
  - `site_locations` schema does **not** include `manifest_fingerprint`, so path-embed equality is a no-op unless schema adds it later.
  - We will still check for embedded lineage only if a column exists (future-proof).
- **Order-free pledge:**
  - Columns in `site_locations` are limited to `[merchant_id, legal_country_iso, site_order, lon_deg, lat_deg]`.
  - `order_leak_indicators` should be 0 unless unexpected columns appear or dictionary/schema mismatch is detected.
- **Partition shift law:**
  - Must ensure S8 output path **drops** `parameter_hash`; verify `{seed,manifest_fingerprint}` matches the consumed S7 partition.

Pre-implementation plan (step-by-step):
1) **Preflight + identity resolution:**
   - Resolve `run_id`, `seed`, `manifest_fingerprint`, `parameter_hash` from run_receipt.
   - Load dictionary + schema packs; log resolved contract roots for audit.
2) **Dictionary/schema coherence checks (E808/E811/E812 guardrails):**
   - Validate schema_ref anchors for `s7_site_synthesis`, `site_locations`, and `s8_run_summary`.
   - Cross-check dictionary partitioning/ordering vs schema anchor partition_keys/sort_keys.
   - Assert `site_locations.final_in_layer == true` from dictionary; fail with `E811_FINAL_FLAG_MISMATCH` if not.
3) **Resolve input/output paths via Dictionary (no literal paths):**
   - Input: `s7_site_synthesis` under `[seed, manifest_fingerprint, parameter_hash]`.
   - Outputs: `site_locations` under `[seed, manifest_fingerprint]` and `s8_run_summary.json` under the reports path.
4) **Stream S7 and map to egress shape:**
   - Read S7 in writer-sort; build S8 rows by selecting `{merchant_id, legal_country_iso, site_order, lon_deg, lat_deg}`.
   - Maintain writer-sort and detect duplicates/out-of-order keys (E803/E806).
   - Count `rows_s7` and `rows_s8` (should match); accumulate by_country counts.
5) **Schema validation (egress rows):**
   - Validate rows against `schemas.1B.yaml#/egress/site_locations` using a row-schema validator.
   - Track `schema_fail_count` and abort if any failures (E804).
6) **Partition shift checks:**
   - Verify S8 `{seed,manifest_fingerprint}` equals S7’s `{seed,manifest_fingerprint}` for the consumed `parameter_hash`.
   - Ensure egress path has **no** parameter_hash directory (E809).
7) **Publish + immutability:**
   - Write S8 rows to a staging dir, fsync, then atomic move into the egress partition.
   - Enforce write-once (byte-identical if re-published) (E810).
8) **Emit run summary (`s8_run_summary.json`):**
   - Include identity `{seed, manifest_fingerprint, parameter_hash_consumed}`.
   - Sizes: `rows_s7`, `rows_s8`, `parity_ok`.
   - Validation counters: `schema_fail_count`, `path_embed_mismatches`, `writer_sort_violations`, `order_leak_indicators`.
   - By-country rollup `{rows_s7, rows_s8, parity_ok}`.

Open questions (need confirmation before coding):
1) **Schema validation cost:** Do you want strict per-row JSON-Schema validation for S8 (full compliance, slower) or a faster dtype/constraint check + spot validation? Spec says full schema validation, but confirm performance posture.
2) **Order-leak detection:** The schema is columns_strict; should `order_leak_indicators` always be 0 unless we detect unexpected columns, or do you want explicit scanning for any ordering hints beyond writer-sort (e.g., if a future column appears)?

### Entry: 2026-01-14 08:27

Design element: S8 confirmation of validation posture + implementation kickoff (pre-code).

Decision outcomes (explicit):
1) **Schema validation:** Perform **full per-row JSON-Schema validation** against `schemas.1B.yaml#/egress/site_locations` in streaming batches (spec compliance prioritized; schema is narrow so overhead is acceptable).
2) **Order-leak indicators:** Keep `order_leak_indicators=0` by default and increment only if unexpected/order-bearing columns appear (which should be blocked by `columns_strict=true`).

Implementation approach updates (before coding):
- Use dictionary-only resolution for `s7_site_synthesis`, `site_locations`, and `s8_run_summary`, plus explicit schema_ref anchor checks for E808/E812 guards.
- Enforce writer-sort monotonicity and PK uniqueness while streaming S7 (E803/E806).
- Map only `{merchant_id, legal_country_iso, site_order, lon_deg, lat_deg}` into egress rows; no extra fields.
- Emit `s8_run_summary.json` with identity `{seed, manifest_fingerprint, parameter_hash_consumed}`, sizes, validation counters, and by_country parity.

### Entry: 2026-01-14 08:34

Design element: S8 implementation (runner + CLI + Makefile wiring) with streaming publish + strict validation.

Implementation actions and reasoning (detailed, step-by-step):
1) **Module scaffold + CLI wiring.**
   - Added `packages/engine/src/engine/layers/l1/seg_1B/s8_site_locations/__init__.py`.
   - Added `packages/engine/src/engine/cli/s8_site_locations.py` to run `run_s8` with the standard contracts/runs/external roots flags and optional `--run-id`.
   - Updated `makefile` to add `SEG1B_S8_*` variables and `segment1b-s8` target.

2) **Contract loading + schema_ref validation (E808/E812 guardrails).**
   - Implemented dictionary-only dataset resolution for `s7_site_synthesis`, `site_locations`, and `s8_run_summary`.
   - Added `_assert_schema_ref` to validate that the referenced schema anchors exist before any data read.
   - Added `_assert_alignment` to cross-check Dictionary `partitioning`/`ordering` against the Schema anchor’s `partition_keys`/`sort_keys` for both S7 input and S8 output.
   - Enforced `final_in_layer: true` for `site_locations` (E811 on mismatch).

3) **Partition shift law (E809).**
   - Verified S7 input path uses `[seed, manifest_fingerprint, parameter_hash]` and S8 output path **does not** include `parameter_hash` (hard-fail if it does).

4) **Streaming S7 → S8 mapping (order-free egress).**
   - Implemented streaming scan of S7 parquet files with only required columns (`merchant_id, legal_country_iso, site_order, lon_deg, lat_deg`).
   - Enforced writer-sort monotonicity and duplicate key detection:
     - Duplicate key → `E803_DUP_KEY`.
     - Out-of-order key → `E806_WRITER_SORT_VIOLATION`.
   - Mapped rows directly to `site_locations` shape (no joins, no RNG, no geometry reads).

5) **Schema validation (strict per-row).**
   - Added table→row schema conversion (`_table_row_schema`) and per-row Draft202012 validation against `schemas.1B.yaml#/egress/site_locations`.
   - Included `schemas.layer1.yaml` `$defs` and rewrote external `$ref` to local `$defs` to avoid unresolved refs.
   - Any schema violation triggers `E804_SCHEMA_VIOLATION` (fail-fast).

6) **Publish posture (E810).**
   - Wrote output in parquet batches to a staging directory and used atomic move into the identity partition.
   - If a target partition exists, require byte-identical content (write-once guarantee).

7) **Run summary emission.**
   - Emitted `s8_run_summary.json` with identity (`seed`, `manifest_fingerprint`, `parameter_hash_consumed`), sizes, validation counters, and by_country parity.
   - Validated summary against `schemas.1B.yaml#/control/s8_run_summary` and published atomically.

Follow-up note (for run time validation):
- On first `segment1b-s8` run, confirm row parity (`rows_s7 == rows_s8`), validation_counters are zero, and output path matches `[seed, manifest_fingerprint]` with no parameter_hash in the egress path.

### Entry: 2026-01-14 08:35

Design element: S8 run failure after publish (timer formatting bug) + fix.

Observed failure (from run log):
- `TypeError: _StepTimer.info() takes 2 positional arguments but 3 were given` when logging `timer.info("S8: published site_locations rows=%d", counts["rows_s8"])`.
- This occurred **after** `site_locations` was published and **before** the run summary was written.

Root-cause analysis:
- `_StepTimer.info` in S8 accepted only `(message)` while the call site used formatting arguments (same class of issue fixed earlier in S4).

Decision + fix:
- Updated `_StepTimer.info` to accept `*args` and perform inline formatting before logging (match the S7/S4 timer behavior).
- Re-run `segment1b-s8` to complete run summary emission; immutability guard will require byte-identical egress content.

### Entry: 2026-01-14 08:36

Design element: S8 run summary validation failure (control schema is object, not table) + correction.

Observed failure (from run log):
- `SchemaValidationError: Table 'control/s8_run_summary' has no columns.` after publish, when validating the run summary.

Root-cause analysis:
- The `schemas.1B.yaml#/control/s8_run_summary` anchor is a **type: object** with required keys, not a `type: table`.
- S8 incorrectly used `_table_row_schema` (table conversion) for this anchor, which expects `columns`.

Decision + fix:
- Added `_schema_from_pack` for object-style schemas and switched summary validation to use it.
- Re-run `segment1b-s8` to emit the run summary; publish remains idempotent because egress was already written.

### Entry: 2026-01-14 08:36

Design element: S8 execution result + spec compliance check (post-fix).

Execution details:
1) **Run invocation:** `make segment1b-s8 RUN_ID=b4235da0cecba7e7ffd475f8ffb23906`.
2) **Identity:** `seed=42`, `manifest_fingerprint=8ef8eaa92e30fb40d269fa00dc3551899d99c4a1b083150592c96849755ac9a1`, `parameter_hash_consumed=56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7`, `run_id=b4235da0cecba7e7ffd475f8ffb23906`.
3) **Outputs:** 
   - `site_locations` published at `runs/local_full_run-5/b4235da0cecba7e7ffd475f8ffb23906/data/layer1/1B/site_locations/seed=42/manifest_fingerprint=8ef8eaa92e30fb40d269fa00dc3551899d99c4a1b083150592c96849755ac9a1/`.
   - `s8_run_summary.json` published at `runs/local_full_run-5/b4235da0cecba7e7ffd475f8ffb23906/reports/layer1/1B/state=S8/seed=42/manifest_fingerprint=8ef8eaa92e30fb40d269fa00dc3551899d99c4a1b083150592c96849755ac9a1/s8_run_summary.json`.

Spec compliance checks (explicit):
- **Row parity:** `rows_s7=rows_s8=27942`, `parity_ok=true`.
- **Validation counters:** `schema_fail_count=0`, `writer_sort_violations=0`, `path_embed_mismatches=0`, `order_leak_indicators=0`.
- **By-country parity:** all countries show `parity_ok=true`.
- **Partition shift law:** egress path contains `[seed, manifest_fingerprint]` only; `parameter_hash` absent.

Outcome:
- S8 is green for this run_id and aligns with the binding S8 spec requirements (deterministic, RNG-free, order-free egress, writer-sort discipline, parity with S7, and required run summary fields).

## S9 - Validation Bundle & Gate (S9.*)

### Entry: 2026-01-14 09:20

Design element: S9 contract review + pre-implementation plan (validation bundle + PASS gate).
Summary: Completed the S9 expanded spec and contract review and captured the detailed plan for parity validation, RNG accounting, bundle emission, and `_passed.flag` hashing. This entry also queues the post-S9 retrofit of S4–S8 logs to improve “story” readability.

Contracts reviewed (authoritative sources read):
1) **State spec:** `docs/model_spec/data-engine/layer-1/specs/state-flow/1B/state.1B.s9.expanded.md`.
   - Inputs: S7 `s7_site_synthesis` (seed+manifest_fingerprint+parameter_hash), S8 `site_locations` (seed+manifest_fingerprint), RNG events + core logs under `[seed, parameter_hash, run_id]`.
   - Outputs: `validation_bundle_1B`, `validation_bundle_index_1B`, `_passed.flag` (fingerprint-scoped).
   - Hashing law: `_passed.flag` = SHA-256 over **raw bytes** of files listed in `index.json` in **ASCII-lex order of `path`**, flag excluded.
2) **Dictionary:** `docs/model_spec/data-engine/layer-1/specs/contracts/1B/dataset_dictionary.layer1.1B.yaml`.
   - Paths/partitions for `validation_bundle_1B`, `validation_bundle_index_1B`, `validation_passed_flag_1B`, and input datasets/logs.
3) **Registry:** `docs/model_spec/data-engine/layer-1/specs/contracts/1B/artefact_registry_1B.yaml`.
   - Write-once + atomic move posture, no file-order semantics, dependencies list for bundle.
4) **Schemas:** `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml`.
   - `validation_bundle_1B`, `validation_bundle_index_1B`, `passed_flag`, `s9_summary`, `rng_accounting`, and input anchors.
5) **Layer schemas for shared anchors:** `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.layer1.yaml`.
   - `parameter_hash_resolved` + `manifest_fingerprint_resolved` shapes (required fields).
6) **Index schema baseline:** `docs/model_spec/data-engine/layer-1/specs/contracts/1A/schemas.1A.yaml`.
   - `validation_bundle_index_1A` shape for cross-checking index compatibility (S9 says index is 1A-compatible).

Brainstorm & decision notes (detailed, before coding):
- **Identity scope:** S9 is fingerprint-scoped but must read S7 at `[seed, manifest_fingerprint, parameter_hash]`, S8 at `[seed, manifest_fingerprint]`, and RNG logs at `[seed, parameter_hash, run_id]`. This means `run_id` is required for RNG reconciliation even though the output bundle is fingerprint-only.
- **Parity strategy:** S7 and S8 share writer sort `[merchant_id, legal_country_iso, site_order]`, so a streaming merge-join on sorted inputs is the only safe approach; a full-table join would explode memory. Parity must check **exact keyset equality**, not just row counts.
- **RNG accounting:** S5 `site_tile_assign` must be exactly one event per site; S6 `in_cell_jitter` must be ≥1 per site (per attempt) with per-event `blocks=1`, `draws="2"` and envelope law `u128(after)-u128(before)=blocks`. Reconcile event totals against `rng_trace_log` using `(module, substream_label, run_id)` to avoid re-scanning.
- **Bundle files must be deterministic:** Because `_passed.flag` hashes bundle files, avoid volatile fields (timestamps) in `MANIFEST.json`, `parameter_hash_resolved.json`, and `manifest_fingerprint_resolved.json`, otherwise reruns would change the bundle bytes and violate immutability. Only stable identity fields should be emitted unless the spec explicitly requires time.
- **Egress checksums:** Compute per-file SHA-256 for the S8 partition; store in `egress_checksums.json` using **relative paths** (per spec) so checksums remain stable. Use ASCII-lex ordering when computing any composite hash.
- **Story logging:** S9 logs must narrate the story (parity proof → RNG reconciliation → checksums → bundle → PASS gate). After S9, retrofit S4–S8 logging to the same narrative posture.

Pre-implementation plan (step-by-step):
1) **Resolve run identity and validate gating context.**
   - Read `run_receipt.json` for `{seed, parameter_hash, manifest_fingerprint, run_id}`.
   - Log a “story header” for S9: objective, inputs being validated, and outputs/gates to be produced.
2) **Load contract packs + validate schema anchors.**
   - Load schema packs: 1B (`schemas.1B.yaml`), layer1 (`schemas.layer1.yaml`), and 1A (`schemas.1A.yaml`) for index compatibility checks.
   - Validate dictionary `schema_ref` anchors for inputs/outputs; fail fast with `E911_DICT_SCHEMA_MISMATCH` if any anchor is missing.
3) **Resolve all input/output paths via Dictionary.**
   - Inputs: `s7_site_synthesis`, `site_locations`, `rng_event_site_tile_assign`, `rng_event_in_cell_jitter`, `rng_audit_log`, `rng_trace_log`.
   - Outputs: `validation_bundle_1B` root, `index.json`, `_passed.flag`.
   - Enforce registry posture: write-once + atomic move, no file-order semantics.
4) **Parity validation (S7 vs S8).**
   - Stream S7 and S8 in writer sort; merge-join on `[merchant_id, legal_country_iso, site_order]`.
   - Track `rows_s7`, `rows_s8`, `parity_ok`, per-country counts, and writer-sort violations.
   - Fail fast on duplicates or out-of-order keys; record counters in `s9_summary.json`.
5) **Egress checksum computation.**
   - Walk S8 partition files; compute per-file SHA-256 over raw bytes.
   - Store relative paths (bundle-root-relative) and optional composite hash in `egress_checksums.json`.
6) **RNG accounting + envelope checks.**
   - Stream `rng_event_site_tile_assign` and `rng_event_in_cell_jitter` logs; validate against schema anchors (use `normalize_nullable_schema` for nullable fields).
   - Enforce S6 per-event budget (`blocks=1`, `draws="2"`) and envelope law.
   - Join S7 keys to event coverage; compute missing/extra events and coverage stats per family.
   - Reconcile `events_total`, `blocks_total`, `draws_total` against the final `rng_trace_log` row for each family.
7) **Build bundle artifacts (deterministic content).**
   - `MANIFEST.json`: deterministic identity + input/output references; no timestamps.
   - `parameter_hash_resolved.json` + `manifest_fingerprint_resolved.json`: follow layer schema anchors; populate required fields only.
   - `rng_accounting.json`, `s9_summary.json`, `egress_checksums.json`.
8) **Index + PASS flag.**
   - Build `index.json` using the 1B index schema (1A-compatible), listing every non-flag file exactly once with relative `path`.
   - Compute `_passed.flag` as SHA-256 over **raw bytes** of files in ASCII-lex order of `path`.
9) **Publish (atomic, fail-closed).**
   - Stage bundle files under a temp dir; fsync; atomic move to `validation/manifest_fingerprint={manifest_fingerprint}/`.
   - If any validation fails, still write non-flag files for audit but **do not** write `_passed.flag`.
10) **Logging + diagnostics (story-driven).**
   - Log phases with narrative: “Parity check (S7 vs S8)”, “RNG coverage & budget”, “Egress checksums”, “Bundle index + PASS flag”.
   - Progress logs include elapsed time, rate, and ETA for long loops.
11) **Post-S9 logging retrofit (queued).**
   - After S9, retrofit S4–S8 logs to include story headers and phase narration per AGENTS.md.

Open confirmations (need resolution before coding):
1) **`MANIFEST.json` content:** propose a deterministic identity-only object (no timestamps). Confirm if any required fields are expected beyond identity and pointers.
2) **`parameter_hash_resolved.json` / `manifest_fingerprint_resolved.json`:** decide where to source `artifact_count` and `git_commit_hex`. Preferred: use run_receipt fields if present; otherwise compute `git_commit_hex` from repo head and set `artifact_count` to the number of parameter inputs recorded for this run (if available). Confirm if that is acceptable.
3) **`egress_checksums.json` path semantics:** propose storing paths relative to the bundle root (e.g., `../site_locations/.../part-00000.parquet`) to satisfy spec “relative path” guidance. Confirm if you prefer paths relative to the run root instead.

### Entry: 2026-01-14 09:24

Design element: S9 confirmation decisions (implementation posture locked).
Summary: User approved the S9 confirmations; locking the deterministic bundle content, git commit resolution, and egress checksum path strategy before coding.

Decision record (explicit):
1) **`MANIFEST.json`** will be deterministic and identity-only (no timestamps). Fields: `version`, `seed`, `parameter_hash`, `manifest_fingerprint`, `run_id`, and minimal input/output pointers. This ensures re-runs can remain byte-identical.
2) **`parameter_hash_resolved.json` + `manifest_fingerprint_resolved.json`:**
   - `git_commit_hex` will come from `run_receipt.json` when present; otherwise resolve from repo HEAD.
   - `artifact_count` will be set from run-recorded parameter inputs if available; if not present, set to `0` and log that the count was unavailable.
3) **`egress_checksums.json` path semantics:** store paths **relative to the bundle root** (e.g., `../site_locations/.../part-00000.parquet`) to keep the bundle self-descriptive and portable.

Implementation note:
- These decisions will be applied consistently across S9 output files and logged with "story header" + phase narration per AGENTS.md.

### Entry: 2026-01-14 10:05

Design element: S9 implementation kickoff (pre-code) + file creation strategy.
Summary: Preparing to implement the S9 runner/CLI/Makefile wiring and to run S9 for the current run_id. Also documenting the file-writing strategy needed to avoid Windows path/command-length errors when creating the new S9 runner file.

In-process plan and decision log (before code changes, detailed):
1) **Runner creation strategy (Windows command-length guardrail).**
   - Issue encountered earlier: writing a large `runner.py` in one command triggered `The filename or extension is too long` (Windows error 206) even though the path is short.
   - Decision: build the S9 runner in **small chunks** using repeated `Add-Content`/`apply_patch` updates so each command stays under Windows command-length limits.
   - Cleanup plan: remove any temporary stub files (`test_stub.py`) and replace the current `runner.py` stub content with the full implementation once the staged writes are complete.

2) **S9 runner architecture (functional map, ordered).**
   - **Identity resolution:** read `run_receipt.json` (latest if no `run_id`) for `{seed, parameter_hash, manifest_fingerprint, run_id}`; log a story header with these tokens.
   - **Contract loading:** load 1B schema pack (`schemas.1B.yaml`), layer schema pack (`schemas.layer1.yaml`), and 1A schema pack (for index compatibility). Validate dictionary `schema_ref` anchors before any data read.
   - **Path resolution:** resolve `s7_site_synthesis`, `site_locations`, RNG logs, and bundle outputs via the Dictionary only (no literal paths).
   - **Parity validation:** stream-merge S7/S8 by writer sort key `(merchant_id, legal_country_iso, site_order)` to detect:
     - E901 missing S8 rows, E902 extra S8 rows, E903 duplicate S8 keys, E906 writer sort violations.
   - **Egress schema validation:** per-row validation of S8 rows against `schemas.1B.yaml#/egress/site_locations` (E904 on failure).
   - **Identity coherence:** verify S8 path partitions `[seed, manifest_fingerprint]` (no parameter_hash in path), and check any embedded lineage fields if present (E905/E912).
   - **RNG accounting:** stream `rng_event_site_tile_assign` and `rng_event_in_cell_jitter` logs; enforce S6 per-event budget (`blocks=1`, `draws="2"`), envelope law, and per-site coverage; reconcile totals with `rng_trace_log` final rows keyed by `(module, substream_label, run_id)` (E907 on any mismatch).
   - **Bundle outputs:** write `MANIFEST.json`, `parameter_hash_resolved.json`, `manifest_fingerprint_resolved.json`, `rng_accounting.json`, `s9_summary.json`, `egress_checksums.json`, `index.json` deterministically; compute `_passed.flag` (ASCII-lex order, raw-bytes hash).
   - **Publish posture:** stage -> fsync -> atomic move; if target exists with different bytes, fail with E913 (immutability).

3) **Shared nullable-schema helper usage (consistency).**
   - Use `normalize_nullable_schema` when validating RNG audit/event schemas to avoid `nullable: true` pitfalls, aligned with the earlier shared helper change.

4) **Post-implementation tasks (queued).**
   - After S9 is green, retrofit S4-S8 logging to narrate the state flow clearly (story header + phase markers).

### Entry: 2026-01-14 10:56

Design element: Validation bundle immutability guard + explicit archive workflow + 1A/1B alignment.
Summary: S9 re-runs for the same `manifest_fingerprint` must not silently overwrite prior bundles. We keep the immutability guard, add an explicit archive helper for operators, and align 1A S9 to the same publish posture as 1B S9.

Decision set (explicit, with reasoning):
1) **Immutability guard stays on.**
   - Reasoning: The spec calls the bundle write-once and fingerprint-scoped; overwriting defeats the audit trail. If bytes differ, S9 must fail closed.
   - Consequence: Operators must explicitly archive or delete failed bundles before re-running S9 for the same fingerprint.

2) **Archive helper instead of implicit overwrite.**
   - Reasoning: We need a repeatable, explicit workflow for reruns that preserves history. The helper moves the existing bundle to a `_failed/` archive path with a timestamp.
   - Consequence: Reruns become a deliberate action (archive → re-run), and the provenance chain remains intact.

3) **Align 1A S9 to the same guard.**
   - Reasoning: 1A currently removes an existing bundle prior to publish. That is inconsistent with 1B and undermines the write-once contract. Alignment avoids future surprises when re-running 1A S9.
   - Consequence: 1A S9 will raise the same immutability error if the bundle exists and differs, and will require explicit archive/removal to re-run.

Plan (before implementation, detailed and explicit):
1) **Add an atomic publish guard to 1A S9.**
   - Implement a `_atomic_publish_dir` helper in `seg_1A/s9_validation/runner.py` similar to 1B:
     - If the destination bundle exists, hash the temp bundle and existing bundle (stable traversal).
     - If hashes match, delete temp and return with an info log.
     - If hashes differ, raise `E913_ATOMIC_PUBLISH_VIOLATION` (fail closed).
   - Replace the current `shutil.rmtree(bundle_root)` overwrite with this guard.

2) **Introduce explicit archive helper targets (1A + 1B).**
   - Add Makefile targets (`segment1a-s9-archive`, `segment1b-s9-archive`) that:
     - Read `run_receipt.json` to resolve `manifest_fingerprint`.
     - Move the existing bundle directory to `data/layer1/{segment}/validation/_failed/manifest_fingerprint={fingerprint}/attempt={timestamp}`.
     - Log the source and destination paths.
   - This keeps archive content outside dictionary paths and retains the full byte history.

3) **Update documentation/logbook.**
   - Record the guard alignment and archive workflow in `segment_1B.impl_actual.md`, `segment_1A.impl_actual.md`, and the logbook.
   - Note that S9 reruns for an existing fingerprint are explicitly two-step (archive → re-run).

Expected outcome:
 - S9 publishes are truly immutable and audit-safe across 1A and 1B.
 - Rerun workflows are explicit and repeatable without silent mutation of validation bundles.

### Entry: 2026-01-14 11:06

Design element: Implement archive helper targets + 1A S9 immutability guard alignment.
Summary: Added explicit Makefile helpers for archiving validation bundles prior to S9 reruns and aligned 1A S9 publish to the same immutability guard used in 1B.

Changes applied (explicit, step-by-step):
1) **Makefile archive targets.**
   - Added `segment1a-s9-archive` and `segment1b-s9-archive` targets.
   - Each target reads `run_receipt.json`, resolves `manifest_fingerprint`, and moves the existing bundle to:
     - `data/layer1/{segment}/validation/_failed/manifest_fingerprint={fingerprint}/attempt={timestamp}`.
   - Updated `.PHONY` to include the new targets and added a default `SEG1A_S9_RUN_ID`.

2) **1A S9 immutability guard.**
   - Implemented `_hash_partition` + `_atomic_publish_dir` in `packages/engine/src/engine/layers/l1/seg_1A/s9_validation/runner.py`.
   - Replaced the unconditional `shutil.rmtree(bundle_root)` with `_atomic_publish_dir` so 1A S9 now fails closed when the bundle exists but differs.

Expected effect:
 - Operators can explicitly archive failed bundles before re-running S9.
 - 1A and 1B now share the same write-once validation bundle behavior.

### Entry: 2026-01-14 11:15

Design element: S9 rerun after archive (bundle publish PASS).
Summary: Archived the prior fingerprint bundle, reran S9, and confirmed PASS with a newly published validation bundle for `manifest_fingerprint=8ef8eaa92e30fb40d269fa00dc3551899d99c4a1b083150592c96849755ac9a1`.

Execution details (explicit):
1) **Archive helper used:** `make segment1b-s9-archive RUN_ID=b4235da0cecba7e7ffd475f8ffb23906`.
   - Bundle moved to `.../data/layer1/1B/validation/_failed/manifest_fingerprint=8ef8eaa92e30fb40d269fa00dc3551899d99c4a1b083150592c96849755ac9a1/attempt=20260114T111317`.
2) **Run invocation:** `make segment1b-s9 RUN_ID=b4235da0cecba7e7ffd475f8ffb23906`.
3) **Parity validation:** `rows_s7=27942`, `rows_s8=27942`, `parity_ok=true`.
4) **RNG accounting:** trace/audit scan and event scan completed without mismatches.
5) **Bundle publish:** `decision=PASS`; bundle emitted under `runs/local_full_run-5/b4235da0cecba7e7ffd475f8ffb23906/data/layer1/1B/validation/manifest_fingerprint=8ef8eaa92e30fb40d269fa00dc3551899d99c4a1b083150592c96849755ac9a1/`.

Outcome:
- S9 is now green for this run_id and fingerprint; downstream consumers can verify `_passed.flag` and proceed.

### Entry: 2026-01-14 10:33

Design element: S9 implementation (runner + CLI + Makefile wiring) with deterministic bundle outputs.
Summary: Implemented the S9 runner and CLI wiring, added Makefile target for `segment1b-s9`, and cleaned temporary stub files. Captured the concrete checks for parity, RNG coverage, and bundle hashing, and ensured nullable-schema normalization for RNG logs.

Actions and implementation details (step-by-step):
1) **Created/updated S9 package exports.**
   - Updated `packages/engine/src/engine/layers/l1/seg_1B/s9_validation_bundle/__init__.py` to export `run_s9` and `S9RunResult`.
   - This ensures CLI imports are stable and avoid direct path imports.

2) **Implemented `run_s9` runner with full parity + RNG accounting.**
   - File: `packages/engine/src/engine/layers/l1/seg_1B/s9_validation_bundle/runner.py`.
   - Core flow:
     - Resolve run identity from `run_receipt.json` (seed/parameter_hash/manifest_fingerprint/run_id) and attach run-scoped log handler.
     - Load Dictionary + schema packs (1B, layer1, 1A) and preflight schema_ref anchors.
     - Enforce egress `final_in_layer` + identity coherence (no parameter_hash in S8 path/partition).
     - Stream-merge S7/S8 in writer sort order; record missing/extra keys (E901/E902), duplicates (E903), writer sort violations (E906), and per-row schema failures for S8 (E904).
     - Build `s7_keys` for RNG coverage and `by_country` parity counters while streaming.
     - Scan RNG event logs (S5/S6) with schema validation, envelope law checks, and per-event budget checks (`blocks=1`, `draws="2"` for S6), then reconcile totals against `rng_trace_log`.
     - Compute `egress_checksums.json` with per-file SHA-256 and composite hash using paths relative to the bundle root.
     - Emit deterministic bundle JSON files, build `index.json`, compute `_passed.flag` when PASS.
     - Atomic publish with immutability guard (E913 on non-identical existing bundle).

3) **Nullable-schema normalization for RNG logs.**
   - Added `_normalize_refs` and applied `normalize_nullable_schema` in `_schema_from_pack`/`_record_schema` so RNG audit/trace/event schemas handle `nullable: true`.
   - Ensured layer1 event schemas can resolve external `$ref` entries by merging 1B `$defs`.

4) **CLI entry-point added.**
   - Added `packages/engine/src/engine/cli/s9_validation_bundle.py`, mirroring the standard CLI contract flags and `--validate-only` path.

5) **Makefile wiring added.**
   - Added `SEG1B_S9_RUN_ID`, `SEG1B_S9_ARGS`, and `SEG1B_S9_CMD`.
   - Added `segment1b-s9` target to run the new CLI.
   - Updated `.PHONY` to include `segment1b-s9`.

6) **Cleanup of temporary stubs.**
   - Removed `foo.txt`, `test_stub.py`, and `__pycache__` created during incremental file writing.

Notes queued for validation run:
- Recompute final decision **after** bundle file presence checks to avoid writing `_passed.flag` when failures are discovered late.
- If run log shows any schema-ref mismatch or trace reconciliation mismatch, adjust or re-run after diagnosing the precise upstream artifact.

### Entry: 2026-01-14 10:36

Design element: S9 run failure on RNG event schema validation (unevaluatedProperties) + fix.
Summary: The first S9 run failed the RNG event schema validation with `unevaluatedProperties` errors on all event fields. Diagnosed it as a Draft202012 allOf + unevaluatedProperties scoping issue and applied the same fix used in 1A S9.

Observed failure (from run log):
- `E907_RNG_BUDGET_OR_COUNTERS` with message: `Unevaluated properties are not allowed (...)` for S5 `rng_event_site_tile_assign`.
- This indicates the schema pack still contained `unevaluatedProperties: false` in a subschema of `allOf`, which invalidates properties from other subschemas.

Root cause reasoning:
- Layer1 RNG event schemas (`schemas.layer1.yaml#/rng/events/site_tile_assign`) are built with `allOf`:
  - `$ref` to `rng_envelope`,
  - object with event fields,
  - object with `unevaluatedProperties: false`.
- Draft202012Validator treats unevaluatedProperties inside one subschema as applying to the merged instance, causing legitimate envelope fields to be marked as unevaluated.
- This is already solved in 1A S9 by hoisting `unevaluatedProperties` to the top-level schema before validation.

Fix applied:
- Updated `_schema_from_pack` in `packages/engine/src/engine/layers/l1/seg_1B/s9_validation_bundle/runner.py` to:
  - Detect `unevaluatedProperties` inside `allOf`,
  - Remove it from subschemas,
  - Reattach it at the top-level schema before validation.

Next step:
- Re-run `make segment1b-s9 RUN_ID=b4235da0cecba7e7ffd475f8ffb23906` and validate RNG schema passes and bundle is emitted with PASS when no other failures remain.

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

---

### Entry: 2026-01-23 12:48

Design element: stable latest run_receipt selection (Segment 1B).
Summary: Multiple 1B states select the latest run_receipt by file mtime, which can drift if receipts are touched. We will select latest by run_receipt.created_utc instead (fallback to mtime when missing) using a shared helper to preserve determinism.

Planned steps:
1) Add `pick_latest_run_receipt(runs_root)` helper in `engine/core/run_receipt.py`.
2) Update 1B state runners’ `_pick_latest_run_receipt` to call the helper (no behavioral change when run_id is explicit).
3) Keep fallback to mtime if created_utc is missing to avoid breaking old receipts.

Invariants:
- Explicit run_id paths are unchanged.
- Latest selection is deterministic and stable.

---

### Entry: 2026-01-23 12:57

Implementation update: latest receipt helper (1B).

Actions taken:
- Added shared helper `engine/core/run_receipt.py::pick_latest_run_receipt`.
- Updated 1B runners’ `_pick_latest_run_receipt` to delegate to the helper (created_utc sort, mtime fallback).

Expected outcome:
- Latest-run selection is stable and deterministic without changing explicit run_id behavior.

---

### Entry: 2026-02-13 12:26

Design element: Segment 1B remediation build-plan authoring kickoff (data-first, phase-locked).
Summary: User requested creating the Segment 1B remediation build plan document before implementation. Decision is to build a phased, DoD-driven plan that prioritizes statistical realism movement on data outputs while preserving the progressive state dependency law.

Planning decisions (before authoring the build-plan doc):
1) **Use report-driven remediation scope (`S2 + S4 + S6 + S9`) with strict progressive reruns.**
   - Rationale: 1B remediation report identifies these as the causal loci for concentration, coverage, and local geometry realism.
   - Constraint: reruns must follow state dependencies; no isolated downstream patching.

2) **Adopt a two-lane run protocol for heavy compute.**
   - Fast lane for single-seed tuning from changed state onward.
   - Certification lane across required seed set only after fast-lane candidate is stable.
   - Rationale: reduce iteration time while preserving promotion rigor.

3) **Lock 1A as immutable upstream during 1B remediation.**
   - Rationale: prevent attribution drift and avoid reopening already-frozen upstream behavior.

4) **Center DoDs on data realism metrics, not PASS mechanics.**
   - Concentration, coverage, and local geometry metrics are phase closure criteria.
   - Structural/gate checks remain veto rails, not tuning targets.

Planned file action:
- Create `docs/model_spec/data-engine/implementation_maps/segment_1B.build_plan.md` with phased sections, state-owned tuning responsibilities, DoDs, and freeze rules.

---

### Entry: 2026-02-13 12:33

Design element: Segment 1B remediation build plan published.
Summary: Authored and published a new phased build plan for Segment 1B remediation, anchored to the 1B published/remediation reports and all 1B state-expanded contracts.

Actions taken:
1) Added `docs/model_spec/data-engine/implementation_maps/segment_1B.build_plan.md`.
2) Encoded the remediation objective and closure logic for `B` minimum with `B+` target.
3) Captured authority stack (reports + `S0..S9` expanded specs + 1B contracts).
4) Declared active remediation scope and progressive rerun matrix:
   - `S2` changes rerun `S2->S9`,
   - `S4` changes rerun `S4->S9`,
   - `S6` changes rerun `S6->S9`,
   - `S9` gate-only changes rerun `S9`.
5) Added heavy-compute iteration protocol:
   - fast lane vs certification lane,
   - run folder retention/pruning policy to avoid storage growth.
6) Added phased plan with DoDs:
   - `P0` baseline/harness lock,
   - `P1` S2 macro-mass reshape,
   - `P2` S4 anti-collapse closure,
   - `P3` S6 geometry closure,
   - `P4` integrated closure run,
   - `P5` certification and freeze.
7) Added state-first triage mapping and explicit phase freeze/reopen rule.

Expected effect:
- Remediation execution stays causally ordered, data-focused, and auditable while minimizing wasted compute in 1B’s long-run states.

---

### Entry: 2026-02-13 12:32

Design element: P0 expansion plan before edit (baseline/harness detail uplift).
Summary: User requested expanding `P0` in the new Segment 1B build plan. The current `P0` is too terse for execution and needs concrete sub-phases, artifacts, and state/data checks.

Decision (before editing build-plan doc):
1) Expand `P0` into explicit sub-phases (`P0.1..P0.5`) rather than adding narrative prose.
2) Keep `P0` data-centric:
   - baseline realism authority capture,
   - metric harness and scorer outputs,
   - run-id retention/pruning protocol,
   - fast-lane profile lock for heavy compute.
3) Keep remediation states unchanged (`S2/S4/S6/S9`) and avoid leaking tuning logic into `P0`.
4) Add binary DoDs per sub-phase so `P0` can be closed unambiguously before `P1`.

Planned file change:
- Update `docs/model_spec/data-engine/implementation_maps/segment_1B.build_plan.md` under `P0` only, with no scope drift into later phases.

---

### Entry: 2026-02-13 12:32

Design element: P0 expansion applied in build plan (execution-ready detail).
Summary: Expanded `P0` into concrete baseline/harness work packages with explicit artifacts, state-level checkpoints, and closure gates.

Applied updates:
1) Added `P0.1` baseline authority pin with required lineage tokens and upstream-freeze statement.
2) Added `P0.2` baseline scorecard materialization with core realism metrics plus companion country/region/NN tables.
3) Added `P0.3` state-level baseline checkpoints for `S2`, `S4`, and `S6/S8`.
4) Added `P0.4` run harness and storage discipline lock (retained folders + prune-before-run + fast/cert lane lock).
5) Added `P0.5` approval gate requiring explicit go/no-go before entering `P1`.
6) Replaced the old minimal DoD with a phase-exit checklist that is binary and auditable.

Expected outcome:
- `P0` is now operationally actionable and can be closed deterministically before any remediation tuning begins in `P1`.

---

### Entry: 2026-02-13 12:46

Design element: P0 execution implementation plan (baseline artifact generation + harness activation).
Summary: Moving from plan authoring to P0 execution. We will generate baseline score artifacts from authority run `c25...`, create retained-folder harness structure for 1B remediation, run prune-before-run flow, and then close P0 DoD checkboxes.

Decisions before implementation:
1) **Add a dedicated baseline scorer tool for Segment 1B P0.**
   - New file: `tools/score_segment1b_p0_baseline.py`.
   - Inputs: baseline run root (`runs/local_full_run-5/c25...`) and state reports (`S2/S4/S6/S8`).
   - Outputs:
     - baseline scorecard JSON,
     - country-share CSV,
     - region-share CSV,
     - NN quantile CSV.
   - Rationale: reproducible evidence artifact instead of ad-hoc notebook-style outputs.

2) **Use published-report-compatible concentration math from `site_locations`.**
   - Country concentration computed over active countries (nonzero site counts), matching published-report posture.
   - This reproduces baseline `Gini/top-k` values used as remediation anchor.

3) **Use ISO canonical region lookup from local reference when available.**
   - Primary lookup: `_untracked/reference/layer1/iso_canonical/.../iso_canonical.csv` (has `region` and `subregion`).
   - Fallback: tracked ISO parquet with `Unknown` region values.
   - Rationale: produce a deterministic region-share table without introducing external dependencies.

4) **Activate harness folders without copying heavy baseline data.**
   - Create:
     - `runs/fix-data-engine/segment_1B/baseline_authority/`,
     - `runs/fix-data-engine/segment_1B/current_candidate/`,
     - `runs/fix-data-engine/segment_1B/last_good/`.
   - Store pointer metadata to baseline run rather than duplicating datasets.

5) **Prune workflow activation for 1B root.**
   - Execute `tools/prune_failed_runs.py --runs-root runs/fix-data-engine/segment_1B`.
   - Record output in P0 work logs and mark prune-before-run as active.

Execution order:
1) add scorer tool,
2) run scorer against baseline run,
3) create harness/pointer files and iteration protocol metadata,
4) run prune script for 1B root,
5) mark P0 DoD closure in build plan + logbook.

---

### Entry: 2026-02-13 12:52

Design element: P0 execution completed (baseline artifacts + harness + closure gate).
Summary: Completed the full P0 checklist and recorded an explicit GO into `P1`.

Implementation actions completed:
1) Added baseline scorer tool:
   - `tools/score_segment1b_p0_baseline.py`.
   - Computes concentration/coverage/NN metrics, emits companion tables, and captures `S2/S4/S6/S8` checkpoint summaries.

2) Materialized baseline authority artifacts from run `c25a2675fbfbacd952b13bb594880e92`:
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p0_baseline_c25a2675fbfbacd952b13bb594880e92.json`
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p0_baseline_c25a2675fbfbacd952b13bb594880e92_country_share.csv`
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p0_baseline_c25a2675fbfbacd952b13bb594880e92_region_share.csv`
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p0_baseline_c25a2675fbfbacd952b13bb594880e92_nn_quantiles.csv`

3) Baseline metrics captured (authority):
   - `country_gini=0.7528246140`
   - `top1_share=0.1365774067`
   - `top5_share=0.3932559107`
   - `top10_share=0.5974021819`
   - `eligible_country_nonzero_share=0.3092369478`
   - `southern_hemisphere_share=0.0585788783`
   - `nn_p99_p50_ratio=11.7929786966`
   - These values align with published-report concentration posture for the same run.

4) Activated run harness folders and pointers:
   - `runs/fix-data-engine/segment_1B/baseline_authority/baseline_pointer.json`
   - `runs/fix-data-engine/segment_1B/current_candidate/README.txt`
   - `runs/fix-data-engine/segment_1B/last_good/last_good_pointer.json`
   - `runs/fix-data-engine/segment_1B/iteration_protocol.json`
   - No heavy data copy was performed; pointers reference authoritative run paths.

5) Activated prune-before-run workflow for 1B root:
   - Command executed: `python tools/prune_failed_runs.py --runs-root runs/fix-data-engine/segment_1B`
   - Evidence file:
     - `runs/fix-data-engine/segment_1B/reports/segment1b_p0_prune_check.txt`

6) Closed P0 checklist in build plan and recorded phase closure/go decision:
   - `docs/model_spec/data-engine/implementation_maps/segment_1B.build_plan.md`
   - Decision: `GO` into `P1`.

---

### Entry: 2026-02-13 12:48

Design element: P1 expansion planning request (no `P1.1` sub-numbering).
Summary: User requested expanding `P1` and explicitly noted they do not want `P1.1` style breakdown. We will expand `P1` with work blocks using lettered sections and clear DoDs.

Pre-edit decisions:
1) Replace the current short `P1` stub with a full execution design that stays S2-centric.
2) Use block labels (`P1-A`, `P1-B`, ...) instead of `P1.1`.
3) Keep P1 data-focused:
   - policy/config and deterministic weighting mechanics,
   - concentration/breadth shape movement,
   - replay stability and lock criteria.
4) Keep P1 boundaries explicit:
   - active remediation locus is `S2`,
   - downstream spot-checks are only for shape confirmation, not full-phase closure in P1.
5) Record concrete file surfaces and tuning knobs so implementation can start without ambiguous interpretation.

---

### Entry: 2026-02-13 12:48

Design element: P1 build-plan expansion applied (block-based, no dotted subphase numbering).
Summary: Expanded P1 in `segment_1B.build_plan.md` using `P1-A..P1-E` work blocks with explicit scope boundaries, file surfaces, knob map, and closure criteria.

Applied changes:
1) Replaced the short P1 stub with a full execution section.
2) Added explicit P1 scope boundary:
   - P1 is S2-centric,
   - downstream checks in P1 are confirmation-only.
3) Added concrete file surfaces (policy, contracts, runner) to avoid ambiguous implementation targeting.
4) Added S2 tuning knob map:
   - `basis_mix`, region floors, soft/hard caps, top-k targets, concentration penalty, deterministic namespace.
5) Added block-based workflow:
   - `P1-A` policy/contract enablement,
   - `P1-B` deterministic rebalance implementation,
   - `P1-C` diagnostics extraction,
   - `P1-D` calibration loop,
   - `P1-E` lock handoff.
6) Expanded DoD checklist to include:
   - governed diagnostics availability,
   - measurable concentration improvement vs P0 baseline,
   - reproducibility and lock-record requirements.

Outcome:
- P1 is now implementation-ready and aligned with the requested non-dotted subphase style.

---

### Entry: 2026-02-13 12:54

Design element: P1 execution kickoff (S2 blend_v2 implementation + deterministic candidate-run lane).
Summary: Proceeding with the full P1 execution (`P1-A..P1-E`) with S2-only tuning ownership. The immediate work is policy/schema/runtime enablement for `blend_v2`, deterministic diagnostics emission, and a fast-lane candidate run from `S2 -> S9` under `runs/fix-data-engine/segment_1B`.

Decisions before implementation:
1) **Implement `blend_v2` as governed policy, not hidden runtime knobs.**
   - Update:
     - `config/layer1/1B/policy/policy.s2.tile_weights.yaml`
     - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml`
   - Keep legacy fallback active:
     - if `blend_v2.enabled=false`, retain existing single-basis behavior.

2) **Use deterministic two-pass rebalance in S2.**
   - File:
     - `packages/engine/src/engine/layers/l1/seg_1B/s2_tile_weights/runner.py`
   - Pass A:
     - compute raw mixed mass from `{uniform, area_m2, population}` per tile.
   - Pass B:
     - country-level scaling with deterministic tie-breaks for:
       - region floor uplift,
       - soft/hard country caps,
       - concentration penalty pull toward uniform country mass.
   - Preserve existing fixed-dp largest-remainder quantization semantics per country.

3) **Emit governed diagnostics from S2 run report for P1 scoring.**
   - Add:
     - `country_share_topk` (`top1`, `top5`, `top10`),
     - `country_gini_proxy`,
     - `region_share_vector`,
     - `blend_v2_diagnostics` (iterations, convergence delta, policy knobs in effect).
   - Keep existing report fields for backward compatibility.

4) **Run-lane discipline for P1 execution under fix-data-engine root.**
   - Create one candidate run-id under:
     - `runs/fix-data-engine/segment_1B/<candidate_run_id>/`
   - Do not mutate baseline authority run.
   - Seed/manifest/parameter lineage copied from baseline receipt, with run_id changed to candidate id.
   - Copy only required upstream inputs into candidate run root (`S0/S1 + 1A outlet surface`) to allow `S2->S9` rerun chain.
   - Before launching candidate reruns, execute prune script to avoid run-folder sprawl.

5) **P1 scoring posture.**
   - Add a dedicated P1 scorer artifact under:
     - `runs/fix-data-engine/segment_1B/reports/`
   - Evaluate:
     - S2 diagnostics movement vs P0 baseline,
     - downstream no-regression sentinel metrics from S4/S8.
   - Record accepted P1 lock (policy snapshot + run_id + metric deltas) before declaring P1 complete.

Execution order:
1) implement policy/schema/runner changes,
2) create P1 candidate run root and required upstream carry-forward inputs,
3) run prune-before-run,
4) execute `segment1b-s2` through `segment1b-s9`,
5) score candidate and run reproducibility repeat,
6) update build-plan DoD, impl notes, and daily log with lock/handoff details.

---

### Entry: 2026-02-13 13:00

Design element: P1-A/P1-B applied (blend_v2 policy-governed S2 implementation).
Summary: Implemented the S2-side remediation surfaces for `blend_v2` and deterministic rebalance diagnostics, while preserving existing fixed-dp quantization and legacy fallback behavior.

Implemented changes:
1) **Policy enablement (`P1-A`).**
   - Updated `config/layer1/1B/policy/policy.s2.tile_weights.yaml`:
     - policy version bumped to `2026-02-13`,
     - added `fallback_mode: legacy_basis_only`,
     - added `blend_v2` with governed knobs (`basis_mix`, `region_floor_share`, soft/hard caps, top-k caps, penalty strength, deterministic namespace, iteration controls).

2) **Contract governance (`P1-A`).**
   - Updated `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml`:
     - extended `policy/s2_tile_weights_policy` to govern `fallback_mode` and full `blend_v2` surface,
     - kept legacy required fields (`policy_version`, `basis`, `dp`) for backward compatibility.

3) **Runtime implementation (`P1-B`).**
   - Updated `packages/engine/src/engine/layers/l1/seg_1B/s2_tile_weights/runner.py`:
     - parses/validates `blend_v2` policy,
     - computes blended per-tile masses (`uniform`, `area_m2`, `population`) when enabled,
     - retains legacy single-basis path when disabled,
     - keeps deterministic per-country fixed-dp largest-remainder quantization unchanged,
     - adds deterministic country-share rebalance diagnostics (region floors, soft/hard caps, top-k caps, concentration penalty),
     - emits new S2 run-report diagnostics:
       - `country_share_topk`,
       - `country_gini_proxy`,
       - `region_share_vector`,
       - `blend_v2_diagnostics`.

4) **Build sanity check.**
   - Verified syntax compile:
     - `python -m py_compile packages/engine/src/engine/layers/l1/seg_1B/s2_tile_weights/runner.py`.

Clarifying constraint captured for downstream phases:
- S2 still enforces per-country fixed-dp normalization (`sum(weight_fp)=10^dp` per country), so country-level volume movement in final `site_locations` remains primarily downstream of S3/S4 ownership. P1 therefore targets S2 mass-shape diagnostics and within-country weight realism, then hands off anti-collapse country-volume controls to P2 (`S4`).

---

### Entry: 2026-02-13 14:05

Design element: P1 fast-lane compute correction (population component staging).
Summary: First P1 candidate run timed out while still in `S2` because `blend_v2.population` forced full raster sampling across all tiles in every country. For P1 closure (S2 mechanics + deterministic diagnostics), we are staging population influence to `0.0` so the full `S2->S9` chain can complete within practical tuning time.

Decision and rationale:
1) Set `blend_v2.basis_mix.population` to `0.0` and reallocate to `uniform/area_m2` while keeping `blend_v2` enabled.
2) Keep all other P1 knobs active (region floors, caps, top-k targets, concentration penalty, deterministic rebalance diagnostics).
3) Treat this as a compute-lane staging choice, not a permanent removal:
   - population-weighted blend remains implemented in runner + schema,
   - it can be re-enabled in a later pass once we move beyond P1 closure and budget a longer run window.

Operational consequence:
- We can now execute full fast-lane `S2->S9` for P1 lock validation without multi-hour S2 bottleneck from per-tile raster sampling.

---

### Entry: 2026-02-13 15:03

Design element: P1 rerun correction under immutable partition law.
Summary: Attempting to rerun `S2->S9` on an existing candidate run-id failed at `S5` with immutable-partition protection. We shifted to fresh run-id bootstrapping for every full-chain retry to preserve append-only run semantics.

Decision and rationale:
1) Do not rerun downstream states on a run-id that already contains published partitions when upstream inputs changed.
2) For each full-chain P1 retry, create a fresh run-id under `runs/fix-data-engine/segment_1B/` with only required upstream surfaces copied:
   - `1A/outlet_catalogue`,
   - `1B/s0_gate_receipt`,
   - `1B/sealed_inputs`,
   - `1B/tile_index`,
   - `1B/tile_bounds`,
   - plus a cloned `run_receipt.json` with updated `run_id/created_utc`.
3) Keep prune-before-run active before launching new full-chain attempts.

Operational consequence:
- Immutable collision at `S5` is avoided without violating run immutability or deleting valid published partitions.

---

### Entry: 2026-02-13 15:26

Design element: P1 final closure, reproducibility proof, and lock promotion.
Summary: Completed P1 closure using accepted candidate run `335c9a7eec04491a845abc2a049f959f`, verified all P1 checks pass, and validated two-run same-seed S2 reproducibility.

Implementation actions completed:
1) Full fast-lane chain success (`S2->S9`) on fresh run-id:
   - `run_id=335c9a7eec04491a845abc2a049f959f`
   - `S9` decision: `PASS`.
2) P1 candidate scoring:
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p1_candidate_335c9a7eec04491a845abc2a049f959f.json`
   - `checks_all_pass=true`.
3) Reproducibility run:
   - second fresh run-id `8b25602ba5ab48cb9fe459ffece15858` executed for `S2`,
   - compared `country_gini_proxy`, `country_share_topk`, `region_share_vector`, `blend_v2_diagnostics`,
   - all fields equal between accepted run and repro run.
4) Repro/lock artifacts written:
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p1_repro_check_335c9a7eec04491a845abc2a049f959f_8b25602ba5ab48cb9fe459ffece15858.json`
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p1_lock_record.json`
5) Pointer promotion:
   - `runs/fix-data-engine/segment_1B/current_candidate/current_candidate_pointer.json`
   - `runs/fix-data-engine/segment_1B/last_good/last_good_pointer.json`
   - both now point to accepted run `335c9a7eec04491a845abc2a049f959f`.
6) Storage discipline after lock:
   - pruned superseded run-id folders:
     - `a7d72773443c4206bb7ab44695274e92`,
     - `8b25602ba5ab48cb9fe459ffece15858`.

Lock statement:
- P1 (`S2` macro-mass policy + diagnostics posture) is now locked.
- Downstream phases (`P2+`) must treat P1 settings as frozen unless an explicit reopen decision is recorded.

---

### Entry: 2026-02-13 15:45

Design element: P2 planning expansion (S4 anti-collapse closure plan).
Summary: Expanded the build plan `P2` section into explicit work blocks so execution starts with a clear freeze boundary, S4-owned tuning surfaces, fast-lane iteration rules, acceptance/repro gates, and lock-handoff requirements.

Decisions captured:
1) Keep `P1` (`S2`) immutable throughout `P2`; no S2 knob drift is allowed during S4 closure.
2) Start P2 with a locked-baseline authority snapshot from accepted P1 run `335c9a7eec04491a845abc2a049f959f`.
3) Restrict tuning ownership to S4 anti-collapse controls:
   - `country_share_soft_guard`,
   - deterministic reroute ordering,
   - bounded residual redistribution.
4) Use fresh run-id per fast-lane cycle and rerun `S4->S9` to avoid immutable partition collisions.
5) Require explicit reproducibility evidence (second same-seed run) before P2 lock promotion.

Expected outcome:
- P2 execution can proceed without ambiguity while preserving causal attribution (`S4` changes only) and storage/run discipline.

---

### Entry: 2026-02-13 15:52

Design element: P2 execution kickoff plan (implement S4 anti-collapse controls + scoring lane).
Summary: Starting full P2 execution end-to-end. Current S4 runner only performs largest-remainder integerisation with no policy-governed anti-collapse controls and minimal diagnostics, so we will implement S4 policy governance, deterministic redistribution logic, and explicit S4/S8 scoring artifacts for lock decisions.

Decisions before implementation:
1) **Introduce governed S4 policy surface.**
   - Add `config/layer1/1B/policy/policy.s4.alloc_plan.yaml`.
   - Add schema anchor `#/policy/s4_alloc_plan_policy` in `schemas.1B.yaml`.
   - Add dictionary entry `s4_alloc_plan_policy` in `dataset_dictionary.layer1.1B.yaml`.
   - Keep backward-safe defaults: if policy disabled/missing controls, S4 preserves current allocation behavior.

2) **Implement deterministic anti-collapse guard in S4 (no RNG).**
   - File: `packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py`.
   - After base largest-remainder allocation:
     - enforce `country_share_soft_guard` as max per-tile share within each `(merchant_id, legal_country_iso)` allocation vector,
     - reroute excess counts from donor tiles to deterministic receiver tiles,
     - apply bounded residual redistribution to increase active-tile breadth where configured.
   - Preserve hard invariants:
     - per-pair sum exactly equals `n_sites`,
     - no zero/negative emitted counts,
     - deterministic tie-breaks and stable writer ordering remain intact.

3) **Emit S4 diagnostics required for P2 DoD closure.**
   - Add pre/post anti-collapse metrics in `s4_run_report`:
     - pair-level top1-share and HHI summaries,
     - active-tile breadth summaries,
     - move/redistribution counters,
     - policy snapshot in effect.
   - Keep existing report keys unchanged for compatibility.

4) **Add explicit P2 scorer artifact for baseline/candidate comparison.**
   - New tool: `tools/score_segment1b_p2_candidate.py`.
   - Inputs: locked P1 baseline run + candidate run.
   - Outputs:
     - S4 pre/post metric deltas,
     - S8 no-regression checks,
     - P2 candidate checklist in one JSON artifact under `runs/fix-data-engine/segment_1B/reports/`.

5) **Run-lane and storage discipline for P2.**
   - Fresh run-id per candidate iteration (bootstrap only required upstream inputs).
   - Rerun chain from S4 only: `S4 -> S5 -> S6 -> S7 -> S8 -> S9`.
   - After accepted candidate + reproducibility pass, update lock pointers and prune superseded run-id folders.

Execution order:
1) implement policy/schema/dictionary/runner/scorer surfaces,
2) create P2 baseline artifact from locked P1 run,
3) run first P2 candidate (`S4->S9`) and score,
4) tune S4 policy if needed with bounded cycles,
5) run same-seed reproducibility check on second fresh run-id,
6) write P2 lock artifact, update pointers, prune superseded runs, and close P2 DoD/logbook.

---

### Entry: 2026-02-13 17:46

Design element: P2 continuation under branch drift recovery (S4 policy retune wave-1).
Summary: Recovered from cross-branch drift and confirmed the P2 surfaces are present on `migrate-dev` (`2f8ef956`, `5c253035`, `624bedfd`). Scored current P2 candidate `923332139abd4f588a7770513f6f40a0` against locked P1 baseline `335c9a7eec04491a845abc2a049f959f`; result shows zero S4/S8 movement and `checks_all_pass=false` because S4 anti-collapse controls were never triggered (`pairs_guard_touched=0`, moves=0).

Decision and rationale before editing:
1) Keep P2 scope strictly on S4 policy knobs (P1 S2 freeze remains binding).
2) Execute a policy-only retune first (no S4 code change) because current no-movement is caused by lenient thresholds relative to observed pair-level top1/hhi posture, not by missing controls.
3) Retune strategy for wave-1:
   - decrease `country_share_soft_guard` to force donor detection on medium-size pairs,
   - keep `country_share_hard_guard` above soft guard to avoid infeasible receiver caps,
   - increase residual activation floor modestly so breadth expansion can trigger where pair active-tile counts are too concentrated,
   - keep deterministic namespace and reroute mode unchanged.
4) Run fresh candidate from locked P1 run with immutable-run discipline (`S4->S9`, new run-id) and score using `tools/score_segment1b_p2_candidate.py`.
5) Acceptance criteria for this wave:
   - S4 diagnostics must show non-zero guard movement,
   - S4 pair-level `top1`/`HHI` means must improve vs baseline,
   - S8 must not regress concentration and parity rails.
6) If wave-1 still no-move, proceed to wave-2 with stronger soft/hard caps; if improvement appears, run same-seed reproducibility on second fresh run-id before P2 lock promotion.

---

### Entry: 2026-02-13 18:19

Design element: P2 feasibility check correction (S4 bound-aware closure logic).
Summary: Wave-1 retuned candidate (`47ad6781ab9d4d92b311b068f51141f6`) still produced zero movement even though the updated S4 policy was loaded. Deep diagnostics show this is a feasibility boundary, not a missed knob:
- only `3/2597` pairs have any tile with count `>1`,
- those 3 pairs are all `BM` with `pair_total in {101,119,129}` and `active_tiles=90`,
- BM tile universe is exactly `90` tiles (`part-BM.parquet`),
- observed counts already match the minimum-imbalance occupancy (`1/2` distribution) for those totals.

Decision and rationale before code edits:
1) Keep `P1` freeze intact; no upstream reopen during this P2 pass.
2) Treat strict `candidate < baseline` checks in `tools/score_segment1b_p2_candidate.py` as over-constrained when baseline is already at theoretical floor.
3) Update the P2 scorer to compute per-pair lower bounds for `top1` and `HHI` from `(pair_total, country_tile_capacity)` and aggregate mean floor headroom.
4) Convert P2 acceptance rule to:
   - require strict improvement when baseline headroom exists,
   - allow floor-hold pass when baseline headroom is zero (or epsilon-close) and candidate is non-regressive.
5) Persist explicit floor diagnostics in the scorer output so acceptance is auditable and not threshold-forged.

Expected result:
- P2 closure remains data-truthful: we do not claim fake movement where math disallows it, and we still veto any regression.

---

### Entry: 2026-02-13 18:43

Design element: P2 execution closure (bound-aware scoring + lock handoff).
Summary: Implemented and exercised floor-aware P2 scoring, then completed candidate/repro runs and locked P2 with non-regressive floor-hold evidence.

Implementation outcomes:
1) **Scorer upgraded for feasibility-aware gates.**
   - File updated: `tools/score_segment1b_p2_candidate.py`.
   - Added per-country tile-capacity extraction from `tile_weights`.
   - Added per-pair theoretical lower bounds for `top1` and `HHI` from `(pair_total, tile_capacity)`.
   - Added aggregated `theoretical_floor` and `theoretical_headroom` in `s4_pair_metrics`.
   - Updated P2 gate semantics:
     - if baseline headroom exists, require strict improvement;
     - if baseline headroom is zero, require floor-hold + non-regression.
   - Added explicit `feasibility` block in score output for auditability.

2) **Candidate and reproducibility evidence.**
   - Accepted candidate run: `47ad6781ab9d4d92b311b068f51141f6`.
   - Repro run: `57cc24a38a4646f3867b7f815063d26f` (fresh run-id; full chain `S4->S9`).
   - Score artifacts:
     - `segment1b_p2_candidate_47ad6781ab9d4d92b311b068f51141f6.json`
     - `segment1b_p2_candidate_57cc24a38a4646f3867b7f815063d26f.json`
   - Both scorecards report `checks_all_pass=true` with zero S8 regression and zero baseline headroom.
   - Repro comparison artifact written:
     - `segment1b_p2_repro_check_47ad6781ab9d4d92b311b068f51141f6_57cc24a38a4646f3867b7f815063d26f.json`.

3) **P2 lock and storage discipline.**
   - Wrote lock artifact:
     - `runs/fix-data-engine/segment_1B/reports/segment1b_p2_lock_record.json`.
   - Updated pointers:
     - `runs/fix-data-engine/segment_1B/current_candidate/current_candidate_pointer.json`
     - `runs/fix-data-engine/segment_1B/last_good/last_good_pointer.json`
   - Pruned superseded run folders:
     - `923332139abd4f588a7770513f6f40a0`,
     - `57cc24a38a4646f3867b7f815063d26f`.

Decision statement:
- P2 is closed with a mathematically justified floor-hold posture under locked P1 inputs.
- Downstream phases can proceed with P1/P2 both treated as immutable unless explicit reopen is approved.

---

### Entry: 2026-02-13 18:52

Design element: P3 planning expansion (S6 geometry closure under P1/P2 freeze).
Summary: Expanded P3 from a high-level note into execution-grade blocks (`P3-A..P3-E`) with explicit freeze boundaries, governed file surfaces, and measurable DoDs tied to geometry realism without reopening P1/P2.

Planning decisions captured:
1) **Freeze discipline remains strict.**
   - P3 may only tune S6 surfaces.
   - P1 (S2) and P2 (S4) are hard-locked unless explicit reopen approval is recorded.

2) **P3 authority stack is two-layered.**
   - Grade reference remains P0 baseline metrics.
   - No-regression reference for downstream posture is P2 lock run.
   - This prevents fake gain claims from swapping baselines mid-phase.

3) **S6 control surfaces must be policy-governed first.**
   - Add `policy.s6.jitter.yaml` and activate governed schema/dictionary mapping.
   - No hidden tuning constants in runner logic.

4) **Implementation lane remains deterministic and fail-closed.**
   - Mixture jitter (`core`, `secondary`, `sparse_tail`) must preserve deterministic namespace semantics.
   - Point-in-country, coordinate bounds, and immutable partition laws remain non-negotiable.

5) **Calibration and acceptance protocol mirrors P2 rigor.**
   - Fresh run-id per cycle.
   - Fast-lane rerun limited to `S6->S9`.
   - Same-seed reproducibility required before lock.
   - Prune superseded run-id folders at handoff.

6) **P3 DoD is grade-oriented but scoped.**
   - Primary objective: NN-tail contraction toward B threshold (`>=20%` vs baseline target).
   - Secondary objective: stripe/corridor sentinel removal in top-volume countries.
   - Hard veto: no concentration/coverage regression against P2 lock posture.

Implementation intent for next step:
- execute `P3-A` baseline snapshot + scorer lane prep, then proceed to policy/schema activation (`P3-B`) before touching S6 runtime logic (`P3-C`).

---

### Entry: 2026-02-13 18:55

Design element: P3 implementation strategy before code edits (S6-only lane).
Summary: Finalised the concrete implementation route for P3 to avoid hand-wavy tuning: first activate a governed S6 policy surface, then implement deterministic mixture jitter with fixed RNG budget per event, then score and calibrate via `S6->S9` fast-lane cycles.

Pre-edit decisions:
1) **Policy governance first, runtime second.**
   - `jitter_policy` in contracts/dictionary is still marked reserved and path-misaligned (`config/layer1/1B/policy/1B.jitter.yaml`).
   - We will activate it as an S6-consumed policy at `config/layer1/1B/policy/policy.s6.jitter.yaml`.

2) **RNG envelope must remain stable.**
   - Existing S6 event schema requires `blocks=1` and `draws=\"2\"` per attempt/event.
   - Mixture jitter must therefore be implemented using exactly the same two uniforms per attempt (no extra RNG draws), preserving determinism and trace compatibility.

3) **Mixture implementation form (deterministic, bounded).**
   - Introduce `uniform_v1` (legacy) and `mixture_v2` modes.
   - `mixture_v2` uses component weights (`core`, `secondary`, `sparse_tail`) with component-specific center-shape exponents and max offset fractions.
   - Component selection will be deterministic from existing uniforms; lat/lon fractions remain bounded to tile limits before country check.

4) **P3 scoring is missing and must be added.**
   - Add `tools/score_segment1b_p3_candidate.py` to evaluate:
     - NN tail contraction vs P0 baseline (`p99/p50`),
     - S8 concentration no-regression vs P2 lock,
     - stripe/corridor sentinel across top-volume countries,
     - parity and structural checks.

5) **Fast-lane execution and lock discipline.**
   - Candidate cycles will use fresh run-id bootstraps from locked P2 run and rerun only `S6->S9`.
   - After acceptance, run one same-seed reproducibility cycle, write P3 lock record, update pointers, prune superseded runs.

Risk noted upfront:
- Given current 1B posture, NN-tail may have limited S6 headroom because much of spacing is inherited from upstream tile assignment (`S5`/`S4`). If contraction target remains unreachable after bounded tuning, we will produce explicit feasibility evidence rather than claim synthetic gains.

---

### Entry: 2026-02-13 19:25

Design element: P3 feasibility diagnosis + S6 algorithm correction plan (no P1/P2 reopen).
Summary: P3 candidate scoring shows persistent failure on `nn_tail_contraction_b_target` and `top_country_no_collapse` even after activating `mixture_v2`. A direct diagnostic on locked P2 topology confirms several top countries are effectively single-latitude corridors already at S5/tile-centroid support, so bounded in-cell jitter cannot clear collapse sentinels.

Evidence captured before edits:
1) Latest candidate `2fc45e1204bd417abc272521c8a0de06`:
   - `nn_p99/p50 = 13.555` (worse than baseline),
   - collapse sentinel still flags `DE, FR, GB, DK, CH, IT, ES, NO`.
2) S5/tile centroid support is lat-collapsed for key countries under locked P2:
   - `DE`: 4269 sites across 215 tiles but centroid lat range is constant (`51.279167..51.279167`),
   - `FR`: constant (`49.937500..49.937500`),
   - `ES`: constant (`39.020834..39.020834`),
   - `NO`: constant (`78.629167..78.629167`).
3) This proves P3 failure is not just knob tuning; it is a geometry-support ceiling under strict in-pixel jitter.

Decision and implementation plan:
1) Keep P1/P2 frozen (no reopen in this pass).
2) Upgrade S6 `mixture_v2` sampling from strict in-pixel fractions to deterministic **tile-neighborhood displacement** around tile centroids with component-specific floor spans.
3) Preserve non-negotiables:
   - RNG budget remains `blocks=1`, `draws="2"` per attempt/event,
   - deterministic seed namespace behavior unchanged,
   - point-in-country acceptance remains mandatory,
   - coordinate bounds and immutable publish laws remain fail-closed.
4) Keep `uniform_v1` lane behavior unchanged for backward compatibility.
5) Retune S6 policy weights toward dense-core realism with bounded sparse tail, then rerun fresh candidate with required chain `S5->S9` and rescore.

Planned file surfaces:
- `packages/engine/src/engine/layers/l1/seg_1B/s6_site_jitter/runner.py`
- `config/layer1/1B/policy/policy.s6.jitter.yaml`
- (no P1/P2 file touches)

---

### Entry: 2026-02-13 19:29

Design element: P3-C S6 runtime correction implemented (neighborhood mixture lane).
Summary: Implemented the S6 algorithm change required by the 19:25 diagnosis: `mixture_v2` is no longer restricted to strict in-pixel fractions and now supports deterministic tile-neighborhood displacement around tile centroids with component-specific floor spans.

What changed:
1) `packages/engine/src/engine/layers/l1/seg_1B/s6_site_jitter/runner.py`
   - Added deterministic component floor spans:
     - `core=0.015 deg half-span`,
     - `secondary=0.035 deg half-span`,
     - `sparse=0.080 deg half-span`.
   - Added centered-shape sampler for mixture mode and switched `mixture_v2` sampling to centroid-based displacement with bounded component scale.
   - Kept `uniform_v1` lane unchanged (strict in-pixel behavior preserved).
   - Kept RNG envelope invariant: still one Philox block/two uniforms per attempt event.
   - Pixel-bound checks remain enforced for `uniform_v1`; `mixture_v2` now relies on point-in-country + global coordinate bounds.
   - `sigma_lat_deg`/`sigma_lon_deg` now emit effective displacement scale in degrees for diagnostics.
2) `config/layer1/1B/policy/policy.s6.jitter.yaml`
   - bumped to `policy_version=2026-02-13-r3`.
   - moved to core-heavy mixture profile (`core=0.72`, `secondary=0.24`, `sparse=0.04`) with tighter core spread and bounded secondary lane.

Verification completed:
- `python -m py_compile packages/engine/src/engine/layers/l1/seg_1B/s6_site_jitter/runner.py` passed.

Next execution step:
- bootstrap a fresh candidate run-id from locked P2 authority,
- run `S5->S9` (required chain for trace consistency),
- score with `tools/score_segment1b_p3_candidate.py` and decide lock vs further bounded retune.

---

### Entry: 2026-02-13 19:38

Design element: P3 out-of-pixel experiment verdict + rollback to in-contract lane.
Summary: The neighborhood-displacement experiment was executed on run `ca19edb80ba4441f99a66ab194b38dd1` and failed fail-closed at S7 (`E707_POINT_OUTSIDE_PIXEL`). This confirms S7 contract semantics currently require S6 realizations to remain in pixel support; the experimental lane is invalid without explicit S7/contract broadening.

Actions taken:
1) Reverted S6 runner back to in-pixel-safe mixture implementation (kept existing policy-governance framework intact).
2) Kept P1/P2 frozen and moved back to in-contract P3 calibration.
3) Preserved failure evidence in run logs; did not promote the experimental lane.

Decision:
- Do not pursue out-of-pixel displacement inside P3 under current freeze/contract posture.
- Continue with in-contract candidate scoring to determine feasibility-limited closure versus lock promotion.

---

### Entry: 2026-02-13 19:40

Design element: P3 final calibration outcome under frozen P1/P2 (blocked closure).
Summary: Executed fresh in-contract candidate `run_id=36d94ea5f4c64592a4938884cd3535a3` with full required chain `S5->S9` (`S9 PASS`) and scored against P0 baseline + P2 lock. P3 hard geometry gates remain unsatisfied.

Observed outcomes:
1) Candidate score artifact:
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p3_candidate_36d94ea5f4c64592a4938884cd3535a3.json`.
2) Hard-gate status:
   - `nn_tail_contraction_b_target=false` (`nn_p99/p50=35.5577`, severe regression),
   - `top_country_no_collapse=false` (same 8 flagged top countries).
3) No-regression rails that still hold:
   - concentration/coverage not worse than P2,
   - coordinate bounds valid,
   - S8 parity OK.

Feasibility evidence recorded:
- `runs/fix-data-engine/segment_1B/reports/segment1b_p3_feasibility_47ad6781ab9d4d92b311b068f51141f6.json`.
- Under locked P2 support, top countries `DE, FR, GB, DK, CH, IT, ES, NO` have 4dp latitude-uniqueness upper bounds below collapse threshold from S5 centroid support bands, so collapse sentinel clearance is unreachable without upstream support widening.

Phase decision:
- P3 cannot be lock-closed under current freeze assumptions.
- Required explicit reopen/contract decision is now pinned in the build plan before further P3 work.

Storage discipline after P3 attempts:
- Pruned superseded run folders: `ca19edb80ba4441f99a66ab194b38dd1`, `2e12e1049a5c4862bf7a8d6774556e28`, `2fc45e1204bd417abc272521c8a0de06`, `3490add55cc84da78de1347fec92753e`.
- Retained run-id folders:
  - `335c9a7eec04491a845abc2a049f959f` (P1 lock),
  - `47ad6781ab9d4d92b311b068f51141f6` (P2 lock / no-regression authority),
  - `36d94ea5f4c64592a4938884cd3535a3` (latest P3 evidence run).

---

### Entry: 2026-02-13 19:53

Design element: Preferred-path reopen approved (`P2/S4`) for P3 blockage.
Summary: USER approved upstream reopen path. We are reopening S4 support-shaping (while keeping S2 fixed unless evidence later requires S2 reopen) to break repeated top-tile reuse across merchant-country pairs that causes country-level corridor collapse under locked support.

Problem statement for this reopen pass:
1) Under locked P2, S4 allocates many small pairs using deterministic highest-residue picks on the same tile subset repeatedly.
2) This preserves macro concentration but collapses within-country support diversity, leaving P3 collapse sentinels unresolved.
3) S6-only tuning proved insufficient and out-of-pixel S6 lane is invalid under current S7 contract checks.

Decision for implementation:
1) Add a governed S4 policy block for **deterministic support diversification** (phase rotation over high-residue candidate window), not random noise.
2) Keep conservation invariants intact:
   - per-pair `sum(n_sites_tile)=n_sites`,
   - no negative/zero emitted counts,
   - tile universe remains S1/S2 constrained,
   - deterministic replay preserved.
3) Apply diversification only in the shortfall bump lane so base quota math remains aligned with fixed-dp weight authority.
4) Emit explicit diagnostics in S4 run report to measure diversification activity and avoid hidden behavior.

Planned file surfaces for this reopen pass:
- `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml` (governed S4 policy surface extension)
- `config/layer1/1B/policy/policy.s4.alloc_plan.yaml` (S4 reopen policy values)
- `packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py` (deterministic diversification implementation)

Execution plan after code edits:
1) compile checks,
2) fresh run-id bootstrap from locked upstream,
3) run `S4->S9` (with required state continuity),
4) score P2 non-regression and P3 candidate,
5) decide keep/revert based on metrics.

---

### Entry: 2026-02-13 19:57

Design element: S4 reopen implementation (`policy.s4.alloc_plan` + runner + contract governance).
Summary: Implemented governed deterministic support-diversification in S4 shortfall bump selection to reduce repeated top-tile reuse across many small merchant-country pairs while preserving strict conservation and deterministic replay invariants.

Implemented changes:
1) Contract surface extension:
   - `docs/model_spec/data-engine/layer-1/specs/contracts/1B/schemas.1B.yaml`
   - Added optional `policy/s4_alloc_plan_policy/support_diversification` object with governed fields:
     - `enabled`
     - `apply_n_sites_max`
     - `candidate_window_fraction`
     - `candidate_window_min`

2) Policy activation:
   - `config/layer1/1B/policy/policy.s4.alloc_plan.yaml`
   - Bumped to `policy_version=2026-02-13-r3`.
   - Enabled `support_diversification` with small-pair scope (`apply_n_sites_max=24`) and top-window controls.

3) Runtime implementation:
   - `packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py`
   - Added policy fields and parsing for support diversification.
   - Added deterministic rotation helper keyed by `deterministic_seed_namespace|merchant_id|legal_country_iso`.
   - Replaced fixed `order[:shortfall]` bump selection with governed selector:
     - base order remains highest-residue with tile-id tie-break,
     - when enabled and within small-pair bound, bumps are chosen from a rotated high-residue candidate window.
   - Added diagnostics counters:
     - `pairs_diversified_touched`,
     - `diversification_bumps_total`,
     - `diversified_touched_share`.
   - Added policy echo for `support_diversification` in `anti_collapse_policy` run-report snapshot.

Invariant checks preserved:
- per-pair `sum(n_sites_tile)=n_sites`;
- no zero/negative emitted allocations;
- tile-universe constraints unchanged;
- deterministic, RNG-free S4 behavior preserved.

Verification:
- `python -m py_compile packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py` passed.

Next step:
- execute fresh `S4->S9` candidate run from locked upstream,
- score P2 no-regression and P3 geometry gates,
- accept/revert based on evidence.

---

### Entry: 2026-02-13 20:24

Design element: P3 reopen candidate diagnosis after S4 diversification run `a430c66a9cfa4ac1b70ed6566eb18d1c`.
Summary: Fresh reopen candidate improved NN-tail strongly and kept all concentration/coverage/parity gates green, but P3 still fails one contractual gate because S6 policy mode remained `uniform_v1` (`policy_version=2026-02-13-hold-uniform`).

Observed scorer outcome (`segment1b_p3_candidate_a430c66a9cfa4ac1b70ed6566eb18d1c.json`):
1) `checks_all_pass=false`.
2) Only failing check is `s6_mode_mixture_v2=false`.
3) Statistical gates are green:
   - `nn_tail_contraction_b_target=true` (65.74% contraction vs P0 baseline),
   - `top_country_no_collapse=true`,
   - concentration and coverage non-regression gates true.

Decision:
1) Do not reopen additional upstream states for this step.
2) Execute a narrow contract-alignment pass:
   - switch S6 policy `mode` from `uniform_v1` to `mixture_v2` (governed existing lane),
   - keep all other S6 knobs unchanged first,
   - run minimal required chain on a fresh run-id: `S5 -> S6 -> S7 -> S8 -> S9`,
   - rescore P3 and accept only if gates remain green.
3) Storage posture: run on a new run-id and prune the superseded run-id folder if the new candidate fully supersedes it.

---

### Entry: 2026-02-13 20:40

Design element: P3 closure execution after approved S4 reopen path.
Summary: Executed the narrow contract-alignment pass (S6 mode restore to `mixture_v2`) on fresh run-ids from reopened S4 authority and closed P3 with reproducible green scorecards.

Implementation + execution trail:
1) Policy alignment edit:
   - `config/layer1/1B/policy/policy.s6.jitter.yaml`
   - changed `mode: uniform_v1 -> mixture_v2`, `policy_version: 2026-02-13-r4`.
2) Fresh candidate bootstrap/run (`S5->S9`):
   - candidate run: `979129e39a89446b942df9a463f09508`.
   - state outcomes: `S5 PASS`, `S6 PASS`, `S7 PASS`, `S8 PASS`, `S9 PASS`.
   - score artifact: `runs/fix-data-engine/segment_1B/reports/segment1b_p3_candidate_979129e39a89446b942df9a463f09508.json`.
   - P3 result: `checks_all_pass=true`.
3) Same-seed reproducibility witness (`S5->S9`):
   - repro run: `81d1a2b5902146f08a693836eb852f85`.
   - state outcomes: `S5 PASS`, `S6 PASS`, `S7 PASS`, `S8 PASS`, `S9 PASS`.
   - score artifact: `runs/fix-data-engine/segment_1B/reports/segment1b_p3_candidate_81d1a2b5902146f08a693836eb852f85.json`.
4) Repro check + lock artifacts:
   - repro check: `runs/fix-data-engine/segment_1B/reports/segment1b_p3_repro_check_979129e39a89446b942df9a463f09508_81d1a2b5902146f08a693836eb852f85.json` (identical checks + candidate metrics).
   - lock record: `runs/fix-data-engine/segment_1B/reports/segment1b_p3_lock_record.json`.
5) Pointer updates:
   - `runs/fix-data-engine/segment_1B/current_candidate/current_candidate_pointer.json`
   - `runs/fix-data-engine/segment_1B/last_good/last_good_pointer.json`
   - both now point to P3 accepted run `979129e39a89446b942df9a463f09508`.
6) Storage hygiene:
   - pruned superseded run-id folders:
     - `a430c66a9cfa4ac1b70ed6566eb18d1c`
     - `36d94ea5f4c64592a4938884cd3535a3`
   - retained authority/freeze runs:
     - `335c9a7eec04491a845abc2a049f959f` (P1 lock),
     - `47ad6781ab9d4d92b311b068f51141f6` (P2 lock),
     - `979129e39a89446b942df9a463f09508` (P3 lock),
     - `81d1a2b5902146f08a693836eb852f85` (P3 repro witness).

Result posture:
- P3 is now closure-grade green under the approved reopen path.
- Remaining progression moves to integrated `P4` with `P1/P2/P3` locked by default.

---

### Entry: 2026-02-13 20:44

Design element: P4 plan expansion from coarse block to execution-grade phased structure.
Summary: Expanded P4 into `P4.1 -> P4.4` so integrated closure is run under explicit lock authority, bounded recovery rules, and deterministic handoff evidence.

Why expansion was required:
1) Prior P4 block stated intent only and was under-specified for execution control.
2) We need explicit fail-closed classification (`GREEN_B`, `AMBER_NEAR_BPLUS`, `RED_REOPEN_REQUIRED`) before any tuning loop.
3) We need storage-safe and causality-safe execution boundaries so integrated work does not silently reopen locked upstream phases.

What was added to build plan:
1) `P4.1` authority envelope pinning (`P1/P2/P3` locks + scorer/policy authority).
2) `P4.2` integrated baseline pass with single scorecard and status classifier.
3) `P4.3` bounded B/B+ recovery mini-loop (one knob-group-at-a-time, strict veto).
4) `P4.4` acceptance/handoff (repro witness, lock record, pointers, prune set).
5) Updated P4 DoD checklist aligned to those four blocks.

Execution posture after this planning update:
- No runtime state was executed in this step.
- No policy/runner code was changed in this step.
- Next actionable step is `P4.1` authority envelope materialization.

---

### Entry: 2026-02-13 20:47

Design element: P4 full execution plan (P4.1->P4.4) under locked `P1/P2/P3`.
Summary: Execute one integrated candidate from `S2->S9` using frozen authorities, then classify against B/B+ hard gates with explicit fail-closed status (`GREEN_B`, `AMBER_NEAR_BPLUS`, `RED_REOPEN_REQUIRED`).

Execution decisions pinned before implementation:
1) Integrated run scope:
   - use fresh run-id bootstrapped from locked P3 authority inputs,
   - rerun `S2->S9` to include all active remediation states (`S2/S4/S6`) in one coherent pass.
2) P4 scoring surface:
   - create dedicated P4 integrated scorer artifact (`segment1b_p4_integrated_*.json`) to avoid ad-hoc manual interpretation.
   - score against the pinned B/B+ thresholds from build plan section 3.
3) P4 classification semantics:
   - `GREEN_B`: all B hard gates pass (B+ may or may not pass; reported separately),
   - `AMBER_NEAR_BPLUS`: B passes but B+ not yet fully met,
   - `RED_REOPEN_REQUIRED`: B hard gates fail under locked posture, implying reopen is required for further movement.
4) Fail-closed behavior:
   - `P4.3` bounded retune runs only if `AMBER_NEAR_BPLUS`.
   - `RED_REOPEN_REQUIRED` blocks tuning and requires explicit upstream reopen approval.
5) Storage posture:
   - keep only authority + accepted + repro run folders after closure attempt,
   - prune superseded integrated attempt runs.

---

### Entry: 2026-02-13 21:17

Design element: P4 full execution (`P4.1` + `P4.2`) and fail-closed classification.
Summary: Executed integrated `S2->S9` candidate under locked authority envelope, scored with new P4 integrated scorer, and reached `RED_REOPEN_REQUIRED` (no P4.3 retune allowed).

Implemented artifacts and execution:
1) New P4 scorer implementation:
   - `tools/score_segment1b_p4_integrated.py`.
   - Purpose: apply absolute B/B+ gates + structural/no-regression checks and emit status classifier.
2) P4.1 authority envelope:
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p4_authority_envelope.json`.
   - Pins lock authorities: `P1=335c9a7eec04491a845abc2a049f959f`, `P2=47ad6781ab9d4d92b311b068f51141f6`, `P3=979129e39a89446b942df9a463f09508`.
3) Integrated runtime candidate:
   - run `625644d528a44f148bbf44339a41a044` with chain `S2->S3->S4->S5->S6->S7->S8->S9`.
   - `S9` decision: `PASS`.
4) Score artifacts:
   - `segment1b_p2_candidate_625644d528a44f148bbf44339a41a044.json`
   - `segment1b_p3_candidate_625644d528a44f148bbf44339a41a044.json`
   - `segment1b_p4_integrated_625644d528a44f148bbf44339a41a044.json`

P4 classifier result:
- `status=RED_REOPEN_REQUIRED`.
- Structural checks: PASS (`s6_mode_mixture_v2`, parity, bounds, collapse sentinel clear).
- No-regression checks vs P3 lock: PASS.
- B/B+ hard-gate failures are concentration/coverage axis:
  - `country_gini=0.7528` (fails B/B+),
  - `top10=0.5974`, `top5=0.3933`, `top1=0.1366` (fail B/B+),
  - `eligible_country_nonzero_share=0.3092`, `southern_hemisphere_share=0.0600` (fail B/B+).
- NN-tail contraction remains strong (`~63.35%` vs baseline), so failure is not on geometry tail.

Fail-closed output:
- Wrote explicit blocker artifact:
  - `runs/fix-data-engine/segment_1B/reports/segment1b_p4_red_reopen_625644d528a44f148bbf44339a41a044.json`.
- Decision:
  - block `P4.3` (bounded B+ recovery) because status is RED,
  - explicit reopen approval required before any upstream edits,
  - recommended reopen lanes: `P1/S2`, then `P2/S4`.

---

### Entry: 2026-02-13 21:28

Design element: Path-1 upstream reopen approval with 1A freeze-veto contract.
Summary: USER approved path-1 (upstream reopen) with a strict boundary: any resulting change must not spoil Segment `1A` frozen grade posture. Before touching any 1A/1B runtime lane, we are pinning a hard no-regression guard.

Pinned decisions before implementation:
1) Upstream posture changes from "1A immutable" to "1A reopen allowed only under guard".
2) Reopen acceptance is fail-closed on a new **1A freeze guard**:
   - candidate must remain `eligible_B=true` at minimum,
   - no regression on authority-hard-gates,
   - no regression on authority B-pass metrics,
   - concentration (`top10`, `gini`) cannot worsen versus frozen certification authority.
3) We will materialize this as a dedicated scorer artifact (tooling) so every path-1 candidate has machine-checkable evidence before 1B promotion.
4) 1B integrated scoring remains unchanged; this new guard is an upstream veto gate, not a replacement for P4/P5 B/B+ gates.

Planned implementation surfaces:
1) New scorer tool:
   - `tools/score_segment1a_freeze_guard.py`.
2) Build plan updates:
   - `docs/model_spec/data-engine/implementation_maps/segment_1B.build_plan.md` (upstream scope and rerun matrix now include guarded 1A reopen).
3) Logbook evidence append:
   - `docs/logbook/02-2026/2026-02-13.md`.

---

### Entry: 2026-02-13 21:36

Design element: Path-1 plan activation wiring (1A freeze-guard gated reopen).
Summary: Updated Segment `1B` build planning authority to move from strict 1A immutability to guarded path-1 reopen, with explicit ordering that blocks any 1B promotion if 1A freeze guard fails.

Changes applied:
1) `segment_1B.build_plan.md` section updates:
   - upstream scope now states: default frozen + approved guarded exception (`path-1`),
   - added `2.0 Path-1 freeze-veto contract`,
   - updated rerun matrix with upstream-reopen lane (`1A accepted candidate -> rerun 1B S0->S9`),
   - added P4 execution status activation note for path-1 order of operations.
2) Guard tool reference pinned in plan:
   - `tools/score_segment1a_freeze_guard.py`,
   - authority artifact `segment1a_p5_certification.json`.

Execution implication:
1) For every upstream candidate cycle:
   - run 1A guard first,
   - continue to 1B integrated run only if guard is `PASS`.
2) This enforces USER constraint that 1A frozen grade cannot be spoiled while attempting 1B recovery.

---

### Entry: 2026-02-13 21:44

Design element: Path-1 cycle #1 execution plan (guarded upstream re-anchor).
Summary: Start first path-1 execution cycle by re-anchoring 1B run identity to accepted 1A authority run `416afa430db3f5bf87180f8514329fe8` (`manifest_fingerprint=12adbd...`, `parameter_hash=59ca67...`), then run integrated `S0->S9` and score against P4 gates.

Pinned execution sequence:
1) Confirm upstream guard status:
   - require `segment1a_freeze_guard_416afa...` to be `PASS` before 1B run bootstrap.
2) Bootstrap fresh 1B run-id:
   - clone latest 1B receipt template,
   - update `run_id`, `created_utc`, and upstream identity tokens (`manifest_fingerprint`, `parameter_hash`) to match the selected 1A authority.
3) Stage required 1A upstream surfaces into the new 1B run root (copy-only, no mutation):
   - `validation/manifest_fingerprint=12adbd...`,
   - `outlet_catalogue/seed=42/manifest_fingerprint=12adbd...`,
   - `s3_candidate_set/parameter_hash=59ca67...`.
4) Execute integrated 1B chain on that run-id:
   - `S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8 -> S9`.
5) Score and classify:
   - `tools/score_segment1b_p4_integrated.py`,
   - capture status and gate movement versus existing P4 RED authority.
6) Storage hygiene:
   - keep this candidate until decision; prune only superseded failed folders after scoring.

---

### Entry: 2026-02-13 23:57

Design element: Path-1 cycle #1 full execution outcome + runtime diagnosis.
Summary: Completed the guarded full 1B chain on run `e4d92c9cfbd3453fb6b9183ef6e3b6f6` and re-scored P4. Status remained `RED_REOPEN_REQUIRED`; concentration/coverage improved materially versus prior RED run but still below B thresholds, with top-country collapse sentinel triggered.

Execution trail (completed):
1) Run bootstrap + identity:
   - run-id: `e4d92c9cfbd3453fb6b9183ef6e3b6f6`
   - upstream identity pinned to accepted 1A authority:
     - `manifest_fingerprint=12adbd0603b3259db571e3c576e6037f4aafe73314037908498f1696003162a9`
     - `parameter_hash=59ca6719a623f6f024806b79344926c5941841789f2f92264bccad187f710f72`
2) Full state chain executed successfully:
   - `S0,S1,S2,S3,S4,S5,S6,S7,S8,S9` complete, with `S9 decision=PASS`.
3) Integrated scoring artifact:
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p4_integrated_e4d92c9cfbd3453fb6b9183ef6e3b6f6.json`.
4) 1A freeze-veto reconfirmed after 1B cycle:
   - `runs/fix-data-engine/segment_1A/reports/segment1a_freeze_guard_416afa430db3f5bf87180f8514329fe8.json`
   - `status=PASS`.

Observed score movement vs prior RED candidate `625644d528a44f148bbf44339a41a044`:
1) Improved:
   - `country_gini`: `0.7528 -> 0.7182`
   - `top1`: `0.1366 -> 0.1240`
   - `top5`: `0.3933 -> 0.3879`
   - `top10`: `0.5974 -> 0.5656`
   - `eligible_country_nonzero_share`: `0.3092 -> 0.7550`
   - `southern_hemisphere_share`: `0.0600 -> 0.0755`
2) Still failing B/B+ hard gates:
   - all concentration and coverage checks remain below B targets.
3) Structural blocker:
   - `top_country_no_collapse=false`
   - collapse sentinel flagged `MC` and `BM` (flagged_count=`2`).

Runtime diagnosis captured for next iteration policy:
1) `S4` is dominant runtime bottleneck.
2) Heartbeats show persistent country-asset cache churn:
   - final heartbeat near completion: `pairs_processed=14420/14423`, `cache_miss=8693`, `evictions=8685`, cache size fixed at `9`.
3) Decision trail consequence:
   - do not brute-force repeated full reruns without a performance rail;
   - next technical lever for iteration speed is an explicit S4 cache/runtime rail (performance-only, no semantics change), while keeping realism gates fail-closed.

---

### Entry: 2026-02-14 06:20

Design element: Post-RED detailed recovery planning update in build authority.
Summary: Added an execution-grade `P4.R` program to the Segment `1B` build plan so recovery proceeds with bounded compute cost, guarded upstream reopen control, and explicit fail-closed gates.

Why this planning expansion was required:
1) Current integrated status is still `RED_REOPEN_REQUIRED` after a full chain run.
2) Runtime churn (especially `S4`) makes blind full reruns non-viable for iterative remediation.
3) We need deterministic, auditable flow from idea -> cheap rejection -> expensive promotion run.

Plan structure pinned in build plan:
1) `P4.R1` runtime rail stabilization for `S4` (performance-only, no semantic drift).
2) `P4.R2` guarded upstream reopen lane (`1A` candidates must pass freeze guard before 1B compute).
3) `P4.R3` proxy-first fast-screen lane for macro realism from `S2/S4`.
4) `P4.R4` collapse/geometry closure lane in `S6` with strict vetoes.
5) `P4.R5` integrated promotion run with explicit classifier decision path.
6) `P4.R6` storage/run-retention hard cap with prune-before-new-full-run.

Execution implication:
1) We no longer iterate by default via full `S0->S9` runs per idea.
2) Long full-chain runs are reserved for shortlisted candidates that clear proxy and structural veto gates.
3) Upstream reopen remains allowed only under the existing `1A` freeze-veto contract.

---

### Entry: 2026-02-14 06:24

Design element: `P4.R1` execution plan (S4 runtime rail implementation).
Summary: Implement a performance-only runtime rail in `S4` by replacing fixed-count country cache behavior with bounded configurable caching (`entry cap` + `byte budget`) while preserving allocation semantics.

Pre-implementation decisions:
1) No statistical semantics change:
   - allocation math, tie-breaking, anti-collapse logic, and output ordering remain unchanged.
2) Runtime knobs (compute-only):
   - `ENGINE_1B_S4_CACHE_COUNTRIES_MAX` (entry bound),
   - `ENGINE_1B_S4_CACHE_MAX_BYTES` (approximate in-memory cache byte budget).
3) Safe defaults:
   - preserve current behavior compatibility when env knobs are unset.
4) Observability:
   - emit effective runtime-cache settings and live cache bytes in `S4` run report/heartbeat context.
5) Benchmark method:
   - compare `S4` before/after on the same run envelope (`run_id=e4d92c9cfbd3453fb6b9183ef6e3b6f6`) using `s4_run_report` wall-clock and cache miss/eviction counters.

Planned file surfaces:
1) `packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py`
2) optional make wiring for explicit env forwarding if needed (`makefile`) without changing statistical policy surfaces.

---

### Entry: 2026-02-14 07:47

Design element: `P4.R1` execution result (S4 runtime rail + benchmark evidence).
Summary: Implemented runtime-cache controls for `S4`, wired them through `make`, and benchmarked on the same envelope run-id. The rail is deterministic and materially faster, but this first pass did not yet reach the `>=30%` speed target.

Implemented changes:
1) `S4` runtime rail in runner:
   - file: `packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/runner.py`.
   - added env-driven cache knobs:
     - `ENGINE_1B_S4_CACHE_COUNTRIES_MAX`,
     - `ENGINE_1B_S4_CACHE_MAX_BYTES`.
   - replaced fixed-count cache behavior with bounded cache eviction using:
     - entry cap,
     - byte-budget cap.
   - added runtime-cache telemetry into `s4_run_report.pat.runtime_cache`.
2) make wiring:
   - file: `makefile`.
   - `segment1b-s4` now forwards:
     - `ENGINE_1B_S4_CACHE_COUNTRIES_MAX`,
     - `ENGINE_1B_S4_CACHE_MAX_BYTES`.

Benchmark execution:
1) Baseline snapshot preserved:
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r1_s4_before_e4d92c9cfbd3453fb6b9183ef6e3b6f6.json`
2) Benchmark run:
   - command equivalent:
     - `make segment1b-s4 ... ENGINE_1B_S4_CACHE_COUNTRIES_MAX=24 ENGINE_1B_S4_CACHE_MAX_BYTES=1000000000`
   - envelope run-id: `e4d92c9cfbd3453fb6b9183ef6e3b6f6`.
3) Result artifacts:
   - after snapshot:
     - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r1_s4_after_e4d92c9cfbd3453fb6b9183ef6e3b6f6.json`
   - benchmark summary:
     - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r1_benchmark_e4d92c9cfbd3453fb6b9183ef6e3b6f6.json`

Measured outcome:
1) Wall-clock:
   - `6386.64s -> 4804.72s` (improvement `1581.92s`, `24.77%` faster).
2) CPU:
   - `6478.19s -> 4767.66s`.
3) Determinism/output parity:
   - determinism hash unchanged (`sha256` identical),
   - `rows_emitted` unchanged (`141377`),
   - `s4_alloc_plan` partition detected as byte-identical.

Decision:
1) `P4.R1` is valid (performance-only + deterministic), but target threshold is not yet fully met in this pass.
2) Keep this rail; if we require strict `>=30%`, run one bounded parameter sweep (`cache entries` and `byte budget`) before closing `P4.R1`.

---

### Entry: 2026-02-14 07:55

Design element: `P4.R1` bounded knob sweep execution plan.
Summary: Execute a bounded `S4` runtime-cache sweep to attempt crossing the `>=30%` wall-clock improvement target before entering `P4.R2`.

Sweep constraints:
1) Same envelope and deterministic identity:
   - `run_id=e4d92c9cfbd3453fb6b9183ef6e3b6f6`,
   - identical `seed/manifest_fingerprint/parameter_hash`.
2) Performance-only knobs:
   - `ENGINE_1B_S4_CACHE_COUNTRIES_MAX`,
   - `ENGINE_1B_S4_CACHE_MAX_BYTES`.
3) Early-stop rule:
   - stop sweep immediately when wall-clock improvement reaches `>=30%` versus baseline (`6386.64s`).
4) Bounded attempt set:
   - attempt A: `(32, 1500000000)`,
   - attempt B: `(48, 2500000000)`,
   - attempt C: `(64, 3500000000)`.
5) Safety:
   - no semantics or policy changes;
   - copy each resulting `s4_run_report` into `runs/fix-data-engine/segment_1B/reports/` with per-attempt name.

---

### Entry: 2026-02-14 11:09

Design element: `P4.R1` bounded sweep closure and runtime rail selection.
Summary: Executed the bounded `S4` cache sweep and crossed the strict `>=30%` wall-clock improvement target while preserving deterministic parity.

Sweep execution outcome:
1) Attempt A (`countries_max=32`, `cache_max_bytes=1500000000`):
   - wall-clock improvement: `29.02%` (below target).
   - artifact: `runs/fix-data-engine/segment_1B/reports/segment1b_p4r1_sweep_attempt_A_32_1500000000.json`.
2) Attempt B (`countries_max=48`, `cache_max_bytes=2500000000`):
   - wall-clock improvement: `30.10%` (target met, early stop).
   - artifact: `runs/fix-data-engine/segment_1B/reports/segment1b_p4r1_sweep_attempt_B_48_2500000000.json`.
3) Determinism/parity posture remained intact:
   - output hash unchanged,
   - row count unchanged.

Decision:
1) Close `P4.R1` with selected runtime rail:
   - `ENGINE_1B_S4_CACHE_COUNTRIES_MAX=48`
   - `ENGINE_1B_S4_CACHE_MAX_BYTES=2500000000`
2) Proceed to `P4.R2` guarded upstream lane.

---

### Entry: 2026-02-14 11:16

Design element: `P4.R2` wave-1 guarded upstream lane execution (`max 2` candidates).
Summary: Ran the first bounded upstream candidate wave using 1A run-ids, enforced freeze-veto gating, and emitted an explicit promoted/rejected list before any downstream 1B compute.

Pre-execution decision:
1) Use an existing-run wave first to avoid unnecessary heavy 1A recompute while validating guard operations:
   - candidate A: `416afa430db3f5bf87180f8514329fe8` (authority-anchored posture),
   - candidate B: `59cc9b7ed3a1ef84f3ce69a3511389ee` (older posture).
2) Require machine artifact per candidate and fail-closed blocking for any non-pass.

Implementation hardening required during wave:
1) Guard tool originally aborted on incomplete candidates without writing a verdict artifact.
2) Updated `tools/score_segment1a_freeze_guard.py` so scoring exceptions now emit explicit `FAIL` artifact with error payload, then exit non-zero.
3) Compile guard passed:
   - `python -m py_compile tools/score_segment1a_freeze_guard.py`.

Wave-1 results:
1) `416afa430db3f5bf87180f8514329fe8`:
   - guard: `PASS`.
   - artifact: `runs/fix-data-engine/segment_1A/reports/segment1a_freeze_guard_416afa430db3f5bf87180f8514329fe8.json`.
2) `59cc9b7ed3a1ef84f3ce69a3511389ee`:
   - guard: `FAIL` (missing `s3_integerised_counts`; fail-closed).
   - artifact: `runs/fix-data-engine/segment_1A/reports/segment1a_freeze_guard_59cc9b7ed3a1ef84f3ce69a3511389ee.json`.
3) Wave summary/promotions:
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r2_wave1_guard_summary.json`.
   - promoted list: `[416afa430db3f5bf87180f8514329fe8]`.
   - rejected list: `[59cc9b7ed3a1ef84f3ce69a3511389ee]`.

Decision:
1) `P4.R2` wave-1 DoD is satisfied for guarded promotion discipline.
2) Rejected candidate is blocked from all 1B runs.
3) Next phase input to `P4.R3` is the bounded promoted list from wave-1.

---

### Entry: 2026-02-14 11:31

Design element: `P4.R3` proxy-lane implementation plan (S4 macro fast-screen, no heavy rerun).
Summary: Execute `P4.R3` by scoring promoted upstream candidates on S4 concentration/coverage movement before any `S6->S9` closure attempt. To avoid unnecessary compute churn, this wave will first reuse existing 1B runs that match promoted 1A lineage.

Pinned decisions before implementation:
1) Candidate source is `P4.R2` promoted list from:
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r2_wave1_guard_summary.json`.
2) Proxy metrics are computed from `s4_alloc_plan` only:
   - `country_gini_s4`, `top1/top5/top10_share_s4`, `nonzero_country_count_s4`.
3) Reference posture for movement direction is the prior RED authority run:
   - `625644d528a44f148bbf44339a41a044`.
4) Fail-fast competitiveness gate for proxy lane:
   - concentration non-regression vs reference (`gini`, `top1`, `top5`, `top10` not worse),
   - coverage non-regression (`nonzero_country_count_s4` not lower).
5) Shortlist remains bounded at `max 2` and will carry forward only proxy-competitive candidates.

Implementation surfaces:
1) New scorer tool:
   - `tools/score_segment1b_p4r3_proxy.py`.
2) New invocation lane:
   - `makefile` target `segment1b-p4r3-proxy`.

Execution plan:
1) build scorer with deterministic JSON artifacts per candidate + wave summary,
2) compile guard,
3) execute scorer on wave-1 promoted list,
4) record shortlist for `P4.R4` input.

---

### Entry: 2026-02-14 11:37

Design element: `P4.R3` execution closure (proxy artifacts + bounded shortlist).
Summary: Implemented and executed the proxy scorer lane. Wave-1 produced complete candidate artifacts, filtered via fail-fast gates, and yielded a bounded shortlist for `P4.R4` without launching new heavy state-chain runs.

Changes applied:
1) Added tool:
   - `tools/score_segment1b_p4r3_proxy.py`.
   - behavior:
     - reads `P4.R2` promoted list,
     - maps each promoted 1A run to latest matching 1B run by `{seed, parameter_hash, manifest_fingerprint}` with available `s4_alloc_plan`,
     - computes S4 proxy metrics + deltas vs reference RED run,
     - emits per-candidate proxy artifact and wave summary,
     - ranks candidates and returns bounded shortlist (`max 2`).
2) Added make target:
   - `segment1b-p4r3-proxy` in `makefile`.

Verification:
1) `python -m py_compile tools/score_segment1b_p4r3_proxy.py` passed.
2) executed:
   - `make segment1b-p4r3-proxy RUNS_ROOT=runs/fix-data-engine/segment_1B`.

Wave-1 outputs:
1) summary:
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r3_proxy_wave_1.json`.
2) candidate artifact:
   - `runs/fix-data-engine/segment_1B/reports/segment1b_p4r3_proxy_416afa430db3f5bf87180f8514329fe8.json`.

Proxy decision outcome:
1) candidate `416afa430db3f5bf87180f8514329fe8` mapped to 1B run `e4d92c9cfbd3453fb6b9183ef6e3b6f6`.
2) proxy checks:
   - `concentration_direction_non_regression=true`,
   - `coverage_direction_non_regression=true`,
   - `proxy_competitive=true`.
3) shortlist:
   - shortlisted 1A candidate(s): `[416afa430db3f5bf87180f8514329fe8]`,
   - shortlisted 1B run(s): `[e4d92c9cfbd3453fb6b9183ef6e3b6f6]`,
   - dropped candidates: none,
   - shortlist boundedness: satisfied (`1 <= 2`).

Decision:
1) `P4.R3` DoD is satisfied.
2) Input to `P4.R4` is the single shortlisted 1B run `e4d92c9cfbd3453fb6b9183ef6e3b6f6`.

---

### Entry: 2026-02-14 11:41

Design element: `P4.R3` summary-check correctness hardening.
Summary: Tightened the proxy summary check semantics so `non_competitive_filtered_before_expensive_runs` is computed from candidate-level gate outcomes instead of a trivial always-true condition.

Change:
1) Updated `tools/score_segment1b_p4r3_proxy.py`:
   - derive `non_competitive_ids` from candidates with `proxy_competitive=false`,
   - derive `dropped_ids` from wave dropped list,
   - set summary check to `non_competitive_ids ⊆ dropped_ids`.
2) Re-ran scorer to regenerate wave artifacts with corrected summary-check semantics.

Verification:
1) `python -m py_compile tools/score_segment1b_p4r3_proxy.py` passed.
2) `segment1b_p4r3_proxy_wave_1.json` reports:
   - `all_candidates_have_artifacts=true`,
   - `non_competitive_filtered_before_expensive_runs=true`,
   - `shortlist_bounded=true`.
