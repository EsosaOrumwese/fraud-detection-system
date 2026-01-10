# Segment 1B Implementation Review (code-derived)

## Scope and sources
- Derived from `packages/engine` only; implementation maps were not used.
- Covers Segment 1B from S0 gate through S9 validation as executed today.
- The intent is descriptive: current behavior, inputs/outputs, and validation/logging posture.

## Entry points and execution flow
### CLI entry point
- `packages/engine/src/engine/cli/segment1b.py` provides `run` and `validate-*` subcommands.
- `run` calls `Segment1BOrchestrator.run` and optionally writes a JSON summary via `--result-json`.
- Validator subcommands exist for S2-S9 (`validate`, `validate-s3`, `validate-s4`, `validate-s5`, `validate-s6`, `validate-s7`, `validate-s8`, `validate-s9`).

### Orchestrator (S0-S9 pipeline)
- `packages/engine/src/engine/scenario_runner/l1_seg_1B.py` runs states sequentially.
- S0 is optional (`skip_s0`); otherwise requires `manifest_fingerprint` and `seed`.
- S6 is invoked with `run_id_override` from S5 to keep RNG lineage aligned.

### Dictionary and schema resolution
- Dataset dictionary loader: `packages/engine/src/engine/layers/l1/seg_1B/shared/dictionary.py`.
- Default dictionary path: `contracts/dataset_dictionary/l1/seg_1B/layer1.1B.yaml`.
- Schema loader: `packages/engine/src/engine/layers/l1/seg_1B/shared/schema.py` (hard-coded to `contracts/schemas/layer1/schemas.1B.yaml`).

## Cross-cutting conventions
### Determinism receipts
- Most parquet outputs are staged and hashed with `compute_partition_digest`, then published with a determinism receipt in run reports.
- Immutable partitions are enforced; mismatched replays raise deterministic error codes.

### RNG logging
- S5 emits `rng_event_site_tile_assign` and appends `rng_trace_log`.
- S6 emits `rng_event_in_cell_jitter` and writes `rng_audit_log` + `rng_trace_log`.
- Shared trace writer: `packages/engine/src/engine/layers/l1/seg_1B/shared/rng_trace.py` (cumulative totals per `(module, substream_label)`).

### Run identifiers
- S5 assignment run_id is generated via `uuid4().hex` and propagated to S6.
- S7/S8 generate run_id for summaries (distinct from S5/S6 run_id).

## State-by-state implementation

### S0 Gate
Code: `packages/engine/src/engine/layers/l1/seg_1B/s0_gate/l2/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s0_gate/l1/verification.py`

Inputs:
- 1A validation bundle (`validation_bundle_1A`), `_passed.flag`, and `index.json`.
- `outlet_catalogue` partition (seed + manifest_fingerprint).
- Reference surfaces: `iso3166_canonical_2024`, `world_countries`, `population_raster_2025`, `tz_world_2025a`.
- `s3_candidate_set` (parameter_hash scoped) used as a required reference in the gate list.
- `licenses/license_map.yaml` for license coverage validation.

Processing:
- Verifies the validation bundle digest against `_passed.flag`.
- Ensures required reference surfaces exist at dictionary-resolved paths.
- Verifies outlet_catalogue lineage (manifest_fingerprint and global_seed embeddings).
- Builds sealed input inventory from dictionary entries and validates license coverage.

Outputs:
- `s0_gate_receipt_1B` JSON (dictionary path).

Validation:
- JSON schema validation for receipt payload and bundle/index integrity.

### S1 Tile Index
Code: `packages/engine/src/engine/layers/l1/seg_1B/s1_tile_index/l2/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s1_tile_index/l3/validator.py`

Inputs:
- `iso3166_canonical_2024`, `world_countries`, `population_raster_2025`.
- Inclusion rule (default: `center`) and optional worker count.

Processing:
- Loads ISO table, country polygons, and raster metadata.
- Enumerates tile index and tile bounds; can run multi-process for countries.
- Measures I/O baselines and records PAT metrics.

Outputs:
- `tile_index` partition (parameter_hash scoped).
- `tile_bounds` partition (parameter_hash scoped).
- `s1_run_report` and `s1_country_summaries` (dictionary-backed paths).

Validation:
- L3 validator checks schema, path embeddings, and report integrity.

### S2 Tile Weights
Code: `packages/engine/src/engine/layers/l1/seg_1B/s2_tile_weights/l2/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s2_tile_weights/l3/validator.py`

Inputs:
- `tile_index` partition.
- `population_raster_2025` for population basis; ISO table for FK validation.
- Governed parameters: `basis` (`uniform`, `area_m2`, `population`) and `dp`.

Processing:
- Streams tile index by country and computes mass per tile based on basis.
- Quantises to `dp` decimal places and enforces PAT envelope.

Outputs:
- `tile_weights` partition (parameter_hash scoped).
- `s2_country_summaries` JSONL and `s2_run_report`.

Validation:
- L3 validator checks basis/dp, output schemas, and run-report integrity.

### S3 Requirements
Code: `packages/engine/src/engine/layers/l1/seg_1B/s3_requirements/l2/prepare.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s3_requirements/l2/materialise.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s3_requirements/l3/validator.py`

Inputs:
- `s0_gate_receipt_1B` (receipt gating).
- `outlet_catalogue` (seed + manifest_fingerprint).
- `tile_weights` (parameter_hash).
- ISO table.

Processing:
- Validates path embeddings for outlet_catalogue.
- Aggregates per-merchant per-country `n_sites` requirements.

Outputs:
- `s3_requirements` partition.
- `s3_run_report`.
- Failure event JSONL on errors (`s3_failure_event`).

Validation:
- L3 validator enforces schema, sort order, and nonzero `n_sites`.

### S4 Allocation Plan
Code: `packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/l2/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/l2/materialise.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s4_alloc_plan/l3/validator.py`

Inputs:
- `s3_requirements`, `tile_weights`, `tile_index`, ISO table.
- `dp` pulled from tile_weights.

Processing:
- Builds allocation plan with tie-breaking and shortfall handling.
- Emits run report with determinism receipt and resource metrics.

Outputs:
- `s4_alloc_plan` partition.
- `s4_run_report`.
- Failure event JSONL (`s4_failure_event`).

Validation:
- L3 validator checks allocation sum, schema, and run-report invariants.

### S5 Site-Tile Assignment
Code: `packages/engine/src/engine/layers/l1/seg_1B/s5_site_tile_assignment/l2/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s5_site_tile_assignment/l2/materialise.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s5_site_tile_assignment/l3/validator.py`

Inputs:
- `s4_alloc_plan`, `tile_index`, `tile_weights`, ISO table.

Processing:
- Generates `run_id` via `uuid4().hex`.
- Emits RNG events for site-tile assignment.
- Appends to `rng_trace_log`.

Outputs:
- `s5_site_tile_assignment` partition.
- `rng_event_site_tile_assign` JSONL partition.
- `s5_run_report` (control-plane report).

Validation:
- L3 validator checks RNG logs, control-plane report, and schema/sort invariants.

### S6 Site Jitter
Code: `packages/engine/src/engine/layers/l1/seg_1B/s6_site_jitter/l2/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s6_site_jitter/l2/materialise.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s6_site_jitter/l3/validator.py`

Inputs:
- `s5_site_tile_assignment`, `tile_index`, `tile_bounds`, `world_countries`, ISO table.
- `run_id` is inherited from S5 for RNG lineage alignment.

Processing:
- Jitters site coordinates inside pixels and country polygons.
- Emits RNG events, audit log, and trace log.
- Builds run report with counters for PIP failures, resamples, and resource metrics.

Outputs:
- `s6_site_jitter` partition.
- `rng_event_in_cell_jitter` JSONL.
- `rng_audit_log`, `rng_trace_log`.
- `s6_run_report`.

Validation:
- L3 validator checks RNG budgets/counters, report metrics, and schema invariants.

### S7 Site Synthesis
Code: `packages/engine/src/engine/layers/l1/seg_1B/s7_site_synthesis/l2/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s7_site_synthesis/l2/materialise.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s7_site_synthesis/l3/validator.py`

Inputs:
- Consumer gate receipt (`verify_consumer_gate`).
- `s5_site_tile_assignment`, `s6_site_jitter`, `tile_bounds`, `outlet_catalogue`.

Processing:
- Merges assignments and jitter into final per-site locations.
- Enforces FK coverage, writer sort, and parity checks against S5/S6.

Outputs:
- `s7_site_synthesis` partition.
- `s7_run_summary.json` next to the dataset partition.

Validation:
- L3 validator checks schema, coverage, and parity counters.

### S8 Site Locations (egress)
Code: `packages/engine/src/engine/layers/l1/seg_1B/s8_site_locations/l2/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s8_site_locations/l2/materialise.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s8_site_locations/l3/validator.py`

Inputs:
- `s7_site_synthesis` partition.

Processing:
- Produces egress `site_locations` with schema and writer sort enforcement.

Outputs:
- `site_locations` partition.
- `s8_run_summary.json` next to the dataset partition.

Validation:
- L3 validator checks schema, writer sort, and parity with S7.

### S9 Validation (handover)
Code: `packages/engine/src/engine/layers/l1/seg_1B/s9_validation/runner.py`,
`packages/engine/src/engine/layers/l1/seg_1B/s9_validation/validator.py`

Inputs:
- `s7_site_synthesis`, `site_locations`.
- RNG logs: `rng_event_site_tile_assign`, `rng_event_in_cell_jitter`, `rng_audit_log`, `rng_trace_log`.

Processing:
- Loads deterministic context from dictionary paths.
- Validates schema, RNG accounting, and egress checksums.
- Builds validation bundle and optional `_passed.flag`.

Outputs:
- Validation bundle under dataset id `validation_bundle_1B`.
- Stage log `logs/stages/s9_validation/segment_1B/S9_STAGES.jsonl`.

## Hardcoded or fixed path resolution flags
- `packages/engine/src/engine/layers/l1/seg_1B/s1_tile_index/l2/runner.py` reads `/proc/self/fd` for open-file counts on non-Windows hosts.
- `packages/engine/src/engine/layers/l1/seg_1B/s9_validation/constants.py` hardcodes stage logs to `logs/stages/s9_validation/segment_1B`.
- `packages/engine/src/engine/layers/l1/seg_1B/s7_site_synthesis/l2/materialise.py` writes `s7_run_summary.json` as `dataset_path.parent / "s7_run_summary.json"`.
- `packages/engine/src/engine/layers/l1/seg_1B/s8_site_locations/l2/materialise.py` writes `s8_run_summary.json` as `dataset_path.parent / "s8_run_summary.json"`.
- `packages/engine/src/engine/layers/l1/seg_1B/s0_gate/l1/verification.py` expects `licenses/license_map.yaml` under repo root (fixed location).
