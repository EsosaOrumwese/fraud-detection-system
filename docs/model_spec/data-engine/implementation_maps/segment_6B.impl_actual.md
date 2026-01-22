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

### Entry: 2026-01-22 06:55

Schema + gate fixes during first S0 runs:
- Fixed YAML indentation in `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml` (fraud_campaign_catalogue_config_6B section) so the pack parses correctly.
- Updated 6B.S0 HashGate index resolution to accept segment-specific index filenames:
  - Use `index.json` if present; otherwise accept `validation_bundle_index_{SEG}.json` (needed for 5A/5B bundles).
  - Keeps lean validation while respecting existing bundle layouts.
- Recompiled runner after change.

### Entry: 2026-01-22 06:56

Upstream sealed-inputs validation adjustment:
- `sealed_inputs_6A` is a JSON list, but the Layer-3 schema anchor `gate/6A/sealed_inputs_6A` is an object schema.
- Added a special-case wrapper in 6B.S0 to validate list payloads by wrapping the anchor as `{"type": "array", "items": <schema>}`.
- Keeps strict validation while accepting the actual upstream format emitted by 6A.S0.

### Entry: 2026-01-22 06:58

Upstream outputs presence check refinement:
- `arrival_events_5B` and 6A base outputs are not listed in `sealed_inputs_5B`/`sealed_inputs_6A` (those manifests enumerate *inputs* to those segments).
- Updated 6B.S0 to fall back to path existence checks (wildcard-friendly for `{scenario_id}`) when a required upstream output is not found in the sealed-inputs manifest.
- This preserves the sealed-inputs authority where relevant, but avoids false negatives for upstream *outputs*.

### Entry: 2026-01-22 06:59

Wildcard presence checks:
- Updated `_path_has_content` to use `glob.glob()` for wildcard paths so `scenario_id=*` resolves correctly when checking `arrival_events_5B` partitions.
- Prevents false negatives when path wildcards are part of the directory name (not just the filename).

### Entry: 2026-01-22 07:00

Config compliance fix:
- `attachment_policy_6B` failed strict schema validation because `dependencies` included `sessionisation_policy_6B` (not allowed by schema).
- Removed `sessionisation_policy_6B` from `config/layer3/6B/attachment_policy_6B.yaml` dependencies to align with the schema while keeping the policy file present for S1.

### Entry: 2026-01-22 07:02

Attachment policy schema failure triage (plan):
- Observed: 6B.S0 fails strict schema validation for `config/layer3/6B/attachment_policy_6B.yaml` because `provenance.attach_rule_id_vocab` is not allowed (schema has `additionalProperties: false`).
- Alternatives considered:
  - A) Relax schema to allow `attach_rule_id_vocab` (keeps config intact but weakens strictness).
  - B) Move/rename the field into an existing allowed key (if semantically appropriate).
  - C) Remove the field from config to preserve strict schema enforcement (lean path).
- Decision path: inspect schema anchor for `attachment_policy_6B`, inspect config usage in code; prefer option C unless the field is required downstream. If required, add explicit property to schema (option A with a precise allow-list) and document rationale.
- Steps:
  1) Open schema section for `attachment_policy_6B` and config file to confirm allowed keys.
  2) Check 6B layer code for any reliance on `provenance.attach_rule_id_vocab`.
  3) Apply minimal change (remove or relocate) to keep strict schema compliance.
  4) Log the decision and update logbook; rerun `make segment6b-s0` to confirm green.

### Entry: 2026-01-22 07:03

Attachment policy fix (decision):
- Checked schema + code usage: `provenance` only allows `attach_rule_id_enabled`, `attach_score_enabled`, `attach_rng_family_field`; no code references `attach_rule_id_vocab`.
- Decision: keep strict schema and remove `provenance.attach_rule_id_vocab` from `config/layer3/6B/attachment_policy_6B.yaml` (lean path, avoids expanding schema).
- Next: rerun `make segment6b-s0` to confirm green; log any new failures.

### Entry: 2026-01-22 07:04

Sessionisation policy validation failure (plan):
- Observed: `make segment6b-s0` fails on `sessionisation_policy_6B` config validation (S0 gate).
- Goal: keep strict schema compliance; prefer config fixes over schema loosening unless the schema is missing required real fields.
- Steps:
  1) Inspect `config/layer3/6B/sessionisation_policy_6B.yaml` and the schema anchor `#/policy/sessionisation_policy_6B` in `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`.
  2) Identify exact mismatches (missing required keys, additional properties, invalid enums) using a targeted validation run if needed.
  3) Apply minimal config changes to satisfy the schema; if config requires extra fields, extend schema with explicit properties (no wildcard additionalProperties).
  4) Log the decision and rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:05

Sessionisation policy fix (decision):
- Schema only allows `stochastic_boundary.enabled` and `stochastic_boundary.key_ids`; removed extra fields (`ambiguity_band`, `decision_law`, `keying`) from `config/layer3/6B/sessionisation_policy_6B.yaml` and mapped `keying.ids` -> `key_ids`.
- Guardrails schema allows only a fixed set of fields; replaced unsupported keys with lean equivalents:
  - `max_arrivals_per_session` -> `max_events_per_flow` (800)
  - `max_sessions_per_session_key` -> `max_sessions_per_seed_scenario` (50000)
  - Dropped `max_session_duration_seconds` (no schema field).
- Rationale: strict schema compliance and lean config until S1 needs richer sessionisation logic.
- Next: rerun `make segment6b-s0` and log outcome.

### Entry: 2026-01-22 07:06

Behaviour config validation failure (plan):
- Observed: `make segment6b-s0` now fails on `behaviour_config_6B` schema validation.
- Plan: inspect `config/layer3/6B/behaviour_config_6B.yaml` vs schema `#/policy/behaviour_config_6B` for missing required keys or extra properties; prefer lean config that matches schema (strict compliance).
- Steps:
  1) Open config and schema sections.
  2) Remove/rename unsupported fields; add missing required keys with minimal realistic defaults.
  3) Log decision and rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:06

Behaviour config fix (decision):
- `behaviour_config_6B` schema has `additionalProperties: false`; top-level `notes` is not allowed.
- Removed the `notes` block from `config/layer3/6B/behaviour_config_6B.yaml` to keep strict compliance and lean config.
- Next: rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:07

Behaviour config schema indentation issue (plan):
- Found `behaviour_config_6B` schema resolves to `behaviour_prior_pack_6B` requirements; YAML shows mis-indentation where `behaviour_prior_pack_6B` is nested under `behaviour_config_6B`.
- Plan: fix indentation in `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml` so `behaviour_config_6B` and `behaviour_prior_pack_6B` are sibling properties under `policy.properties`.
- After fix, re-validate `behaviour_config_6B` config and rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:08

Behaviour config schema fix (decision):
- Unindented `behaviour_prior_pack_6B` in `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml` so it is a sibling to `behaviour_config_6B` under `policy.properties`.
- This restores the correct schema for `behaviour_config_6B` and prevents prior-pack requirements from being applied to the config.
- Next: revalidate `behaviour_config_6B` and rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:09

Behaviour prior pack validation failure (plan):
- Observed: `make segment6b-s0` fails on `behaviour_prior_pack_6B` config schema validation.
- Plan: inspect `config/layer3/6B/behaviour_prior_pack_6B.yaml` vs schema `#/policy/behaviour_prior_pack_6B`; run a targeted validator to surface exact mismatches.
- Apply lean fixes: remove unsupported fields or add missing required fields with realistic defaults while keeping strict schema compliance.
- Rerun `make segment6b-s0` after changes.

### Entry: 2026-01-22 07:10

Behaviour prior pack fix (decision):
- Schema only allows campaign-style guardrails + realism targets; replaced weight/probability guardrails with schema-allowed campaign limits using values from `config/layer3/6B/fraud_campaign_catalogue_config_6B.yaml`.
- Updated `realism_targets` to schema-allowed keys (min_templates_total, min_fraud_family_coverage, targeting_diversity_min, proxy_usage_presence, campaign_prevalence_ranges), mirroring catalogue values; removed unsupported booleans.
- Rationale: strict schema compliance with realistic, existing contract values and lean defaults.
- Next: rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:11

Flow shape policy validation failure (plan):
- Observed: `make segment6b-s0` fails on `flow_shape_policy_6B` config schema validation.
- Plan: inspect `config/layer3/6B/flow_shape_policy_6B.yaml` against schema `#/policy/flow_shape_policy_6B`; run targeted validation to identify mismatches.
- Apply lean config edits or minimal schema fixes (if indentation errors exist) while keeping strict compliance.
- Rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:12

Flow shape policy fix (decision):
- `arrival_to_flow_model.tie_break_order` schema expects an array of strings, not a map.
- Flattened tie-break ordering to a single array: `[ts_utc, merchant_id, arrival_seq, flow_index_within_session]` in `config/layer3/6B/flow_shape_policy_6B.yaml`.
- Next: rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:13

Amount model validation failure (plan):
- Observed: `make segment6b-s0` fails on `amount_model_6B` config schema validation.
- Plan: inspect `config/layer3/6B/amount_model_6B.yaml` and schema `#/policy/amount_model_6B`; run targeted validation with $defs injection.
- Apply lean config edits to match schema (or fix schema indentation if needed).
- Rerun `make segment6b-s0` after change.

### Entry: 2026-01-22 07:13

Amount model fix (decision):
- Schema forbids `bindings.channel_groups` and `bindings.event_type_vocab`; removed both from `config/layer3/6B/amount_model_6B.yaml`.
- Dropped `currency_policy.require_merchant_primary_ccy` (not in schema).
- Added required `realism_targets.decline_amount_distribution_same_as_approved: true`.
- Next: rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:14

Fraud campaign catalogue config validation failure (plan):
- Observed: `make segment6b-s0` fails on `fraud_campaign_catalogue_config_6B` config schema validation.
- Plan: inspect `config/layer3/6B/fraud_campaign_catalogue_config_6B.yaml` vs schema `#/policy/fraud_campaign_catalogue_config_6B`; run targeted validation (with $defs) to identify mismatches.
- Apply lean config edits or fix schema indentation issues if present; rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:16

Fraud campaign catalogue config fix (decision):
- Schema requires activation models to include `rng_family` + `key_ids`; added these to `ACT_DETERMINISTIC_ONE`.
- Schema does not allow `on_no_candidates`; removed from all templates.
- Schema expects `target_flow_scope` as a string; converted flow-scope objects to string expressions.
- Schema quota models only allow `mode`, `targets_per_day`, `burstiness`, `rng_family`, `key_ids`:
  - Converted `QUOTA_FRACTION_SMALL` and `QUOTA_FIXED_SMALL` to `RATE_PER_DAY_V1` with `targets_per_day` (50 and 200) and added RNG keying.
- Next: rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:17

Fraud overlay policy validation failure (plan):
- Observed: `make segment6b-s0` fails on `fraud_overlay_policy_6B` config schema validation.
- Plan: inspect `config/layer3/6B/fraud_overlay_policy_6B.yaml` against schema `#/policy/fraud_overlay_policy_6B`; run targeted validation with $defs.
- Apply lean config edits (remove unsupported fields/add required ones) while keeping strict schema compliance.
- Rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:17

Fraud overlay policy fix (decision):
- Removed unsupported `provenance.preserve_baseline_ids` from `config/layer3/6B/fraud_overlay_policy_6B.yaml`.
- Removed unsupported `realism_targets.min_fraction_of_campaigns_with_any_mutation` (not allowed by schema).
- Next: rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:18

Bank view policy validation failure (plan):
- Observed: `make segment6b-s0` fails on `bank_view_policy_6B` config schema validation.
- Plan: inspect `config/layer3/6B/bank_view_policy_6B.yaml` vs schema `#/policy/bank_view_policy_6B`; run targeted validation with $defs.
- Apply lean config edits to match schema; rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:19

Bank view policy fix (decision):
- Removed unsupported `inputs_allowed.forbid_arrival_row_level_use` and `constraints.forbid_bank_confirmed_fraud_when_truth_legit_without_dispute`.
- Trimmed `realism_targets` to schema-allowed keys: `false_positive_rate_range` and `detection_rate_range_by_truth_label`.
- Next: rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:20

Delay models validation failure (plan):
- Observed: `make segment6b-s0` fails on `delay_models_6B` config schema validation.
- Plan: inspect `config/layer3/6B/delay_models_6B.yaml` vs schema `#/policy/delay_models_6B`; run targeted validation with $defs.
- Apply lean config edits to match schema and rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:20

Delay models fix (decision):
- `sampling_contract.mixture_sampling` must be an object; converted string to `{ mode: deterministic_split_remap_v1 }` in `config/layer3/6B/delay_models_6B.yaml`.
- Next: rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:21

Case policy validation failure (plan):
- Observed: `make segment6b-s0` fails on `case_policy_6B` config schema validation.
- Plan: inspect `config/layer3/6B/case_policy_6B.yaml` vs schema `#/policy/case_policy_6B`; run targeted validation with $defs.
- Apply lean config edits to match schema and rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:22

Case policy fix (decision):
- Simplified `case_involvement` to schema-allowed keys: `case_trigger_labels` and a string `predicate`.
- Reduced `case_key_model` to `precedence` + `encoding` only; dropped field maps/encode object.
- Renamed `sort_member_flows_by` -> `order_by` in `case_grouping_model`.
- Replaced `case_event_model` with `event_order` + string `timestamp_sources`; removed linkage/allow_open_cases objects.
- Next: rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:23

Segment validation policy failure (plan):
- Observed: `make segment6b-s0` fails on `segment_validation_policy_6B` config schema validation.
- Plan: inspect `config/layer3/6B/segment_validation_policy_6B.yaml` vs schema `#/policy/segment_validation_policy_6B`; run targeted validation with $defs.
- Apply lean config edits to match schema and rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:24

Segment validation policy fix (decision):
- `seal_rules.bundle_hashing_law` must be an object; wrapped as `{ mode: index_json_ascii_lex_raw_bytes_excluding_passed_flag }` in `config/layer3/6B/segment_validation_policy_6B.yaml`.
- Next: rerun `make segment6b-s0`.

### Entry: 2026-01-22 07:24

6B.S0 status:
- `make segment6b-s0` now passes; sealed_inputs and gate receipt emitted for manifest_fingerprint 1cb60481d69b836ee24505ec9a6ec231c8f18523ee9b7dabbd38c0a33bf15765.
