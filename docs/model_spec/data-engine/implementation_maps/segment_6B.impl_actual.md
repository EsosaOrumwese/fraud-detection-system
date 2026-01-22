# segment_6B.impl_actual.md
# Implementation logbook (actuals) for Segment 6B

This file captures in-progress design reasoning and implementation decisions for Segment 6B.

### Entry: 2026-01-22 06:07

6B.S0 implementation plan (lean, strict schema compliance):
- Objective: implement `6B.S0` gate runner to verify upstream HashGates (1A–3B, 5A–5B, 6A), validate 6B contracts/configs, and emit `s0_gate_receipt_6B` + `sealed_inputs_6B` deterministically.
- Documents read (expanded + contracts) before design: `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s0.expanded.md`, `docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`, `docs/model_spec/data-engine/layer-3/specs/contracts/6B/artefact_registry_6B.yaml`, `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`.
- Inputs/authorities (catalog-driven; no hard-coded paths):
  - Run identity: `runs/<run_id>/run_receipt.json` (seed, `parameter_hash`, `manifest_fingerprint`, run_id).
  - Contracts via `ContractSource(config.contracts_root, config.contracts_layout)`:
    - 6B dictionary/registry: `dataset_dictionary.layer3.6B.yaml`, `artefact_registry_6B.yaml`.
    - Schema packs: `schemas.6B.yaml` (6B), `schemas.layer3.yaml` (Layer-3 gates), plus upstream packs needed to resolve schema_ref anchors (1A/1B/2A/2B/3A/3B/5A/5B/6A + layer1 + layer2).
  - Upstream HashGate artefacts (from dictionary reference_data): `validation_bundle_*` + `validation_passed_flag_*` for 1A–3B, 5A–5B, 6A.
  - Upstream sealed-input manifests: `sealed_inputs_5A`, `sealed_inputs_5B`, `sealed_inputs_6A`.
  - Upstream data-plane surfaces for 6B: `arrival_events_5B`, 6A base tables (party/account/instrument/device/ip/linkage), etc.
  - 6B config/policy packs: attachment/sessionisation/behaviour config & priors, flow/amount/timing, fraud campaign/catalogue, labels, validation policy, RNG policies.
- Critical contract gap discovered:
  - `schemas.layer3.yaml` is missing under `docs/model_spec/data-engine/layer-3/specs/contracts/6B/`.
  - Decision: create `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.layer3.yaml` by mirroring the existing Layer-3 pack from 6A (contains `gate/6B` anchors).
- Alternatives considered:
  1) Full upstream bundle rehash (deep HashGate verification). Rejected for lean path; too slow for metadata-only S0.
  2) Skip schema validation for 6B config/policy packs. Rejected; user requires strict schema compliance at S0.
  3) Ignore upstream sealed_inputs manifests and trust dictionary only. Rejected; spec expects sealed_inputs_5B/6A to be primary authority for upstream presence.
- Decisions (lean path confirmed by user):
  - HashGate verification: require bundle path + index.json presence + `_passed.flag` parse; use `_passed.flag` digest as bundle digest (no per-file rehash).
  - Schema compliance: validate every `schema_ref` anchor (dictionary + registry) and validate each 6B policy/config payload against `schemas.6B.yaml`.
  - Upstream presence checks: for data-plane inputs (arrival/events + 6A bases), verify presence via upstream sealed_inputs manifests (path/manifest_key/artifact_id match). No row-level scans.
  - Digests:
    - Policies/configs/contracts/sealed_inputs manifests: content sha256.
    - Upstream bundles/flags: bundle digest from `_passed.flag`.
    - Large upstream egress data: structural digest derived from path_template + schema_ref + partition_keys.
- Planned mechanics (code structure):
  - New module: `packages/engine/src/engine/layers/l3/seg_6B/s0_gate/runner.py`.
  - CLI entry: `packages/engine/src/engine/cli/s0_gate_6b.py`.
  - Makefile target: `segment6b-s0` with EngineConfig args and run_id selection.
  - Helper functions for: run receipt resolution, path rendering, schema anchor validation, upstream HashGate checks, sealed_inputs validation, structural digesting, deterministic ordering, atomic publish, idempotent re-run.
- Invariants to enforce:
  - `parameter_hash` and `manifest_fingerprint` are valid hex64.
  - `schema_ref` anchors resolve (allow registry schema_ref fallback when dictionary schema_ref is blank).
  - Required upstream bundles/flags + sealed_inputs exist; optional missing inputs are logged and skipped.
  - No duplicate `(owner_layer, owner_segment, manifest_key)` in sealed inputs.
  - Sealed inputs + receipt schema validation passes before write.
  - Idempotence: if outputs exist and differ, fail with drift/idempotence codes.
- Logging & observability:
  - Story header log with objective, required gates, and outputs.
  - Structured events: `6B.S0.START`, `6B.S0.UPSTREAM_CHECK`, `6B.S0.SEALED_INPUTS_BUILT`, `6B.S0.SEALED_INPUTS_DIGEST`, `6B.S0.GATE_RECEIPT_WRITE`, `6B.S0.END`.
  - Progress logs with elapsed/rate/ETA for any multi-file hashing loops (expected minimal).
- Resumability hooks:
  - If outputs exist, compare computed digest + receipt payload; skip if identical; fail on drift or partial outputs.
- Performance considerations:
  - No data-plane row reads.
  - No deep bundle rehash; only `_passed.flag` digest usage and index presence check.
  - Structural digests for large upstream datasets.
- Validation/tests:
  - `python -m py_compile` for new runner + CLI.
  - `make segment6b-s0` (after wiring target) when inputs are available.

### Entry: 2026-01-22 06:33

Contract gap resolution (before coding):
- Created `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.layer3.yaml` by mirroring the existing Layer-3 pack from 6A.
- Rationale: `ContractSource(..., layout=model_spec)` resolves `schemas.layer3.yaml` under the segment’s contract folder; without this file, 6B.S0 cannot validate `gate/6B/*` anchors.
- This is a stopgap until a 6B-specific layer3 pack is authored; content matches the shared layer-3 gate definitions already in use.

### Entry: 2026-01-22 06:46

6B.S0 implementation decisions while coding:
- Implemented `packages/engine/src/engine/layers/l3/seg_6B/s0_gate/runner.py` with lean HashGate checks (index.json presence + `_passed.flag` digest; no deep bundle rehashing).
- Enforced strict schema compliance:
  - Resolved `schema_ref` via dictionary+registry alignment; registry schema_ref acts as fallback when dictionary has `null`.
  - Validated 6B policy/config payloads against `schemas.6B.yaml` with `schemas.layer3.yaml` refs inlined.
  - Validated upstream `sealed_inputs_5A`, `sealed_inputs_5B`, `sealed_inputs_6A` against their schema anchors.
- Used upstream sealed inputs as authority for data-plane presence:
  - `arrival_events_5B` and 6A base tables must appear via `artifact_id`/`manifest_key`/`path_template` match.
  - Optional upstream entries are logged and skipped; required missing entries fail with `SEALED_INPUTS_REQUIRED_ARTIFACT_MISSING`.
- Digest strategy:
  - Policies/contracts/sealed_inputs manifests: content sha256 (plus optional registry digest check).
  - Upstream HashGate bundles/flags: digest taken from `_passed.flag`.
  - Large data-plane surfaces: structural digest from `{path_template, schema_ref, partition_keys}`.
- Idempotence:
  - If `sealed_inputs_6B` + `s0_gate_receipt_6B` already exist, compare digests/payloads; skip if identical, fail on drift.
- Logging:
  - Structured events for start, upstream checks, sealed inputs build/digest, receipt write, and end-of-state.
  - Story header includes objective + outputs to keep run narrative intact.
- Wired CLI + Makefile:
  - Added `packages/engine/src/engine/cli/s0_gate_6b.py`.
  - Added `SEG6B_S0_*` args and `segment6b-s0` target in Makefile; removed obsolete `segment6b` CLI block.
