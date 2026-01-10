# Segment 1A Implementation Review (impl vs impl_map)

## Scope and sources
- Compared `packages/engine` implementation against `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_map.yaml` and `.md` only.
- This document replaces the prior code-only narrative with map alignment findings.

## Key mismatches and drift (ordered by impact)

### 1) parameter_hash contract mismatch (systemic) — RESOLVED
- Impl map defines governed basenames: `hurdle_coefficients.yaml`, `nb_dispersion_coefficients.yaml`, `crossborder_hyperparams.yaml`, `ccy_smoothing_params.yaml`, `s6_selection_policy.yaml`, `policy.s3.rule_ladder.yaml`, with optional `policy.s3.base_weight.yaml`, `policy.s3.thresholds.yaml`.
  - Evidence: `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_map.yaml` (lineage/governed_basenames).
- Previous implementation required a much larger list (includes 5A/5B/6A/6B basenames) in `_REQUIRED_PARAMETER_FILES`.
  - Evidence: `packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/l2/runner.py`.
- Resolution: `_REQUIRED_PARAMETER_FILES` now matches the impl map’s governed basenames, and optional S3 policies are included only when provided.
  - Evidence: `packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/l2/runner.py`.

### 2) Missing S0 contract outputs/gates
- Impl map requires S0 to write `merchant_abort_log`, `sealed_inputs_1A`, and `s0_gate_receipt_1A`.
  - Evidence: `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_map.yaml` (S0 writes).
- Implementation writes eligibility/design/diagnostics + S0 validation bundle + rng_audit_log only.
  - Evidence: `packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/l2/output.py`.
- Impact: downstream contract surfaces are absent and gate semantics are not produced.

### 3) RNG log path root mismatch
- Impl map paths are rooted at `logs/layer1/1A/rng/...`.
  - Evidence: `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_map.yaml` (S1/S2/S4/S6/S7/S8 address templates).
- Implementation writes under `logs/rng/...` across S1/S2/S4/S6/S7/S8.
  - Evidence: `packages/engine/src/engine/layers/l1/seg_1A/s1_hurdle/l2/runner.py`,
    `packages/engine/src/engine/layers/l1/seg_1A/s2_nb_outlets/l2/output.py`,
    `packages/engine/src/engine/layers/l1/seg_1A/s6_foreign_selection/writer.py`,
    `packages/engine/src/engine/layers/l1/seg_1A/s7_integer_allocation/writer.py`.
- Impact: log consumers looking at contract paths will not find RNG evidence.

### 4) Validation bundle path token drift (fingerprint vs manifest_fingerprint)
- Impl map mandates `data/layer1/1A/validation/manifest_fingerprint=...`.
  - Evidence: `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_map.yaml` (gate + S9 writes).
- S9 writes `data/layer1/1A/validation/fingerprint=...` and does not use the dataset dictionary.
  - Evidence: `packages/engine/src/engine/layers/l1/seg_1A/s9_validation/persist.py`.
- S8 validation expects outlet_catalogue partitions to include `fingerprint=` tokens.
  - Evidence: `packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/validate.py`.
- Impact: contract-correct paths will fail validation; S9 gate location diverges from the map.

### 5) Duplicate validation_bundle_1A emissions (S0 + S8 + S9)
- Impl map expects final bundle only in S9 (the gate is S9).
  - Evidence: `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_map.yaml` (S9 writes + gate).
- Implementation writes `validation_bundle_1A` in S0 and again in S8, plus S9 writes its own bundle at a different path.
  - Evidence: `packages/engine/src/engine/layers/l1/seg_1A/s0_foundations/l2/output.py`,
    `packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/runner.py`,
    `packages/engine/src/engine/layers/l1/seg_1A/s9_validation/persist.py`.
- Impact: conflicting bundle semantics and ambiguous gate source.

### 6) S9 does not read `sealed_inputs_1A`
- Impl map lists `sealed_inputs_1A` as a required S9 input.
  - Evidence: `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_map.yaml` (S9 reads).
- Implementation does not load `sealed_inputs_1A`; instead it loads `validation_bundle_1A/MANIFEST.json` when present.
  - Evidence: `packages/engine/src/engine/layers/l1/seg_1A/s9_validation/loader.py`.
- Impact: sealing inventory check is not aligned to the contract surface.

### 7) On-disk state boundaries bypassed via in-memory handoff
- Impl map expects S7 to read `rng_event_nb_final` and S8 to read `rng_event_residual_rank` / `s6_membership`.
  - Evidence: `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_map.yaml` (S7/S8 reads).
- Implementation passes S2/S6/S7 results in memory (no enforced gate check for in-memory data).
  - Evidence: `packages/engine/src/engine/scenario_runner/l1_seg_1A.py`.
- Impact: gate enforcement and auditability diverge from the map.

### 8) Reference input mismatch for currency assignment
- Impl map references `iso3166_canonical_2024` in S5/S6 inputs.
  - Evidence: `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_map.yaml`.
- Implementation uses `iso_legal_tender` (S5) and `iso_legal_tender_2024` (S6 fallback).
  - Evidence: `packages/engine/src/engine/layers/l1/seg_1A/s5_currency_weights/loader.py`,
    `packages/engine/src/engine/layers/l1/seg_1A/s6_foreign_selection/loader.py`.
- Impact: contract inputs and actual dependency surface differ.

### 9) S5 required outputs vs implementation optionality
- Impl map marks `merchant_currency` and `sparse_flag` as required outputs (optional: false).
  - Evidence: `docs/model_spec/data-engine/implementation_maps/segment_1A.impl_map.yaml` (S5 writes).
- Implementation can skip `merchant_currency` if the share surface or legal tender mapping is incomplete.
  - Evidence: `packages/engine/src/engine/layers/l1/seg_1A/s5_currency_weights/runner.py`.
- Impact: contract-required artefact may be missing in valid runs.

## Status summary
- Resolved: parameter_hash governed basenames now align to the impl map.
- Still open: items 2-9 above remain unresolved in code.

## Questions to resolve
- Should the implementation reduce `_REQUIRED_PARAMETER_FILES` to match the impl map, or should the impl map be updated to reflect the current cross-layer parameter hashing?
- Is the S8 `validation_bundle_1A` intentional (and if so, should it be renamed to avoid collisions) or should it be removed in favor of S9-only bundles?
- Should S7/S8 be refactored to read from on-disk surfaces to enforce gates as described in the map?
- Should path tokens be normalized to `manifest_fingerprint` everywhere, and should dictionary resolution drive S9 bundle paths?
