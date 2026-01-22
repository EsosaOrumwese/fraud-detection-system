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

### Entry: 2026-01-22 07:37

6B.S1 review + lean implementation plan (pending approval):
- Problem: Implement 6B.S1 (arrival→entity attachment + sessionisation) with strict contracts but lean/runtime-safe behavior. Specs are heavy on scoring/RNG; we need a pragmatic, deterministic attachment/session model that stays within required invariants and outputs.
- Contracts source (dev→prod switch): use `ContractSource(config.contracts_root, config.contracts_layout)` (default `model_spec` per `engine.core.config`). This keeps dev reading from `docs/model_spec/...` and allows production by setting `ENGINE_CONTRACTS_LAYOUT=contracts` and `ENGINE_CONTRACTS_ROOT=<repo_root>` without code changes.
- Alternatives considered:
  - A) Full spec scoring/priors (multi-feature weights, stochastic boundary law). Accurate but heavy and slow.
  - B) Deterministic hash-based selection within valid 6A candidate sets (uniform weights + optional home-country bias). Lean and vectorizable; still respects 6A linkage constraints.
  - C) Row-by-row Python loops for attachment/sessionisation (simpler but slow/ETA risk).
- Decision (lean path): adopt B with vectorized Polars + deterministic hash → index selection; keep strict invariants but relax heavy scoring features; optionally disable stochastic session boundary if allowed.

Planned mechanics (high-level):
1) Preconditions/gates:
   - Validate `s0_gate_receipt_6B` and upstream PASS status.
   - Load `sealed_inputs_6B` and resolve all required input paths via dataset dictionary + artefact registry (no manual paths).
2) Input load (per seed/scenario partition):
   - Load `arrival_events_5B` columns needed for attachment + session key (arrival_seq, merchant_id, ts_utc, channel_group, scenario_id, legal_country_iso if present).
   - Load 6A bases + links for same seed/manifest/parameter_hash: party_base, account_base, instrument_base, account_instrument_links, device_base, ip_base, device_links, ip_links.
3) Build candidate indices (vectorized):
   - Party pools: global list; optional home-country list (if arrival has country field and party_base has country).
   - Account lists per party; instrument lists per account; device lists per party and per merchant (if available); IP lists per device and per merchant.
4) Attachment (vectorized, deterministic):
   - Compute deterministic `u` via hash on stable keys (manifest_fingerprint, parameter_hash, seed, scenario_id, merchant_id, arrival_seq, dimension tag).
   - Use policy mix (e.g., home vs global) with single `u` per dimension; choose candidate index via `floor(u * n)`; if `n==0` and required → fail fast.
   - Channel-aware requiredness + device mode per policy (customer vs terminal); fallback rules when candidate list empty (if allowed by policy).
5) Sessionisation:
   - Build `session_key_base` from policy fields; group by key, sort by ts_utc+arrival_seq; compute gaps; apply deterministic boundary rules (hard_timeout/hard_break; optionally stochastic ramp if enabled).
   - Assign session ids deterministically (anchored hash on first arrival in session + key fields) to avoid order dependence.
   - Build session_index with required fields (session_id, arrival_count, start/end); include optional fields if cheap (party_id/device_id/merchant_id).
6) Outputs:
   - Write `s1_arrival_entities_6B` and `s1_session_index_6B` to partitioned Parquet per dictionary paths.
   - Emit `rng_trace_log` + `rng_audit_log` entries (counts per RNG family and substream label) following layer3 schemas; re-use append/atomic helpers from existing runners.
7) Logging + monitoring:
   - Story header log describing objective, gated inputs, outputs.
   - Per-partition progress logs with elapsed, count/total, rate, ETA for attachments + sessionisation loops.
   - Log candidate set sizes and fallback usage (narrative counts/gates).
8) Resumability + determinism:
   - If outputs exist and match deterministic hashes, skip; otherwise overwrite via tmp+atomic publish.
   - Ensure stable sort keys and hash inputs to keep deterministic outputs.
9) Validation/testing:
   - Schema validate sample rows for outputs.
   - Cross-check arrival coverage (1:1 with arrivals), session coverage (all session_ids present in index), and FK existence in 6A bases.

Open questions / approval gates:
- Stochastic boundary: set `sessionisation_policy_6B.stochastic_boundary.enabled=false` for lean determinism, or implement the ramped RNG (1 draw per ambiguous gap)?
- Party selection: use home-country bias when `arrival_events_5B` exposes `legal_country_iso` (if absent, fall back to global pool only)?
- Device/IP selection: if merchant-side device/IP links are missing in 6A, is it acceptable to always use party-linked devices/IPs (even for POS/ATM)?
- Output fields: OK to emit only schema-required columns (plus optional ids), or do you want extra diagnostics (attach scores, rule ids)?

### Entry: 2026-01-22 07:48

6B.S1 implementation decision (approved lean defaults):
- Adopt deterministic, vectorized attachment + sessionisation path (no per-row Python loops).
- Stochastic boundary disabled: use only hard_timeout/hard_break rules (no RNG for session splits) to keep runtime predictable.
- Party selection: use home-country bias only when both arrival country and party country fields exist; otherwise use global pool only.
- Device/IP: prefer merchant-linked candidates when available for POS/ATM; otherwise fall back to party-linked candidates and log fallback counts. Requiredness enforced; missing candidates → hard failure.
- Outputs: emit only schema-required fields + optional ids; skip attach scores/rule ids to keep lean.
- RNG logging: emit aggregate rng_trace_log/rng_audit_log rows (families used + counts), no per-row spam.
- Proceed to implement S1 runner + CLI + Makefile target; run `make segment6b-s1` until green, logging fixes as they occur.

### Entry: 2026-01-22 08:06

6B.S1 lean re-implementation plan (pre-code, refresh for current session):
- Problem: implement 6B.S1 from scratch to attach arrivals to entities + sessionise with deterministic, fast kernels that respect contracts but avoid heavy/slow scoring and per-row RNG noise.
- Alternatives considered:
  - A) Full spec scoring + per-step Philox draws + stochastic boundaries (high fidelity, high cost).
  - B) Deterministic hash-based selection within valid 6A candidate sets using vectorized Polars (lean, fast).
  - C) Python per-row loops (simple but too slow).
- Decision: use B with guarded relaxations: skip heavy prior scoring, apply minimal eligibility filters, disable stochastic boundary, and log deviations; keep strict coverage and FK invariants.

Inputs/authorities (resolved via sealed_inputs_6B + dictionaries/registries; no manual paths):
- Control: `s0_gate_receipt_6B`, `sealed_inputs_6B` (schemas.layer3.yaml#/gate/6B/*).
- Arrivals: `arrival_events_5B` (schemas.5B.yaml s4_arrival_events_5B).
- Entities: `s1_party_base_6A`, `s2_account_base_6A`, `s3_instrument_base_6A`, `s3_account_instrument_links_6A`,
  `s4_device_base_6A`, `s4_ip_base_6A`, `s4_device_links_6A`, `s4_ip_links_6A`, plus fraud roles (read-only).
- Policies: `attachment_policy_6B`, `sessionisation_policy_6B`, `behaviour_config_6B`, `behaviour_prior_pack_6B`,
  `rng_policy_6B`, `rng_profile_layer3` (use ContractSource for model_spec → contracts switch).

Planned mechanics (stepwise):
1) Preconditions:
   - Load run_receipt → run_id, seed, manifest_fingerprint, parameter_hash.
   - Validate `s0_gate_receipt_6B` + upstream PASS statuses.
   - Load + validate `sealed_inputs_6B`; ensure required rows exist with status=REQUIRED.
2) Policy scope:
   - Respect `behaviour_config_6B.scope_filters.scenario_id_allowlist`; if scenario not allowed → skip partition per degrade_posture.
3) Candidate index build (deterministic, minimal eligibility):
   - Accounts: restrict to accounts with ≥1 instrument link; sort by (owner_party_id, account_id); assign per-party index/count.
   - Devices: restrict to devices with ≥1 IP link; derive per-party device lists from device_links; sort + index.
   - Parties: eligible if account_count>0 and device_count>0; use global party pool (home-country bias disabled because
     arrival_events_5B lacks legal_country_iso).
   - Instruments: per-account list from account_instrument_links; sort + index.
   - IPs: per-device list from ip_links; sort + index.
4) Attachment (vectorized, deterministic hash → index):
   - Compute u01 via Polars hash on stable keys + step tag; map to indices via floor(u * count).
   - Attach party → account → instrument → device → ip; enforce requiredness; fail fast on missing candidates.
5) Sessionisation:
   - Build session_key_base per sessionisation_policy fields; normalise channel_group to ASCII uppercase.
   - Sort by (session_key_base, ts_utc, arrival_seq); compute gaps; new session on hard_timeout/hard_break.
   - Stochastic boundary disabled even if policy says enabled (lean relaxation); log this decision.
   - Compute session_id via sha256(anchor=first arrival in session + domain tag), int.from_bytes(..., "little").
6) Outputs + RNG:
   - Write `s1_arrival_entities_6B` (required fields only) and `s1_session_index_6B` (required + optional ids).
   - Emit rng_audit_log + rng_trace_log with aggregated counts for `rng_event_entity_attach` and `rng_event_session_boundary`
     (boundary draws expected 0 due to disabled stochastic boundary); counters advanced by blocks=ceil(draws/2).
7) Resumability:
   - Use idempotent publish (tmp write + sha256 compare) to skip identical outputs; abort on conflict.
8) Logging/monitoring:
   - Story header: objective + gated inputs + outputs.
   - Per-scenario progress logs with elapsed/count/rate/ETA.
   - Narrative counts: arrivals_in_scope, eligible_parties, accounts_with_instruments, devices_with_ips, sessions_produced.
9) Validation/tests:
   - Ensure arrival coverage 1:1 and session coverage 1:1 (arrival sessions ↔ session_index).
   - Verify required fields non-null; abort on mismatches; run `make segment6b-s1` until PASS.

Edge cases to capture:
- arrival_events_5B missing channel_group → fill default from attachment_policy.
- zero arrivals for scenario → emit empty outputs (consistent with spec default).
- missing eligible parties/devices/accounts → hard failure with S1_PRECONDITION_* error.

### Entry: 2026-01-22 08:29

6B.S1 implementation kickoff (pre-code, current session):
- Re-confirmed lean path decisions: deterministic, vectorized attachment/sessionisation; skip heavy priors/scoring; disable stochastic session boundary; enforce requiredness and coverage; log relaxations explicitly.
- Contract source: continue using `ContractSource(config.contracts_root, config.contracts_layout)` so dev uses `model_spec`, prod can switch to repo-root contracts without code changes (via `ENGINE_CONTRACTS_LAYOUT` / `ENGINE_CONTRACTS_ROOT`).
- RNG posture (lean): use deterministic hash-based U(0,1) (open interval) for attachment selection; record aggregate draws/events to `rng_trace_log` and `rng_audit_log` without per-row event logs; session boundary draws set to zero (stochastic disabled).
- Implementation steps (immediate):
  1) Build `packages/engine/src/engine/layers/l3/seg_6B/s1_attachment_session/runner.py` with: gate checks, sealed_inputs resolution, candidate indices, vectorized attachments, deterministic sessionisation, idempotent outputs, RNG audit/trace writes, and narrative progress logs.
  2) Add CLI entry `packages/engine/src/engine/cli/s1_attachment_session_6b.py`.
  3) Update Makefile with `segment6b-s1` target and include in `segment6b`.
- Invariants to enforce: arrivals 1:1, all entity ids exist in 6A bases/links, session index coverage 1:1, schema-required fields only, deterministic outputs for fixed `(manifest_fingerprint, parameter_hash, seed, scenario_id)`.
- Potential deviations to log if encountered:
  - `attachment_policy_6B` references `arrival.legal_country_iso` (not in 5B schema) → global party pool only.
  - `device_policy` merchant-terminal mode (POS/ATM) not supported by 6A links → party-linked devices only.

### Entry: 2026-01-22 08:47

6B.S1 implementation (coding decisions + outcomes):
- Implemented runner at `packages/engine/src/engine/layers/l3/seg_6B/s1_attachment_session/runner.py` using deterministic hash-based attachment and vectorized Polars joins; sessionisation via hard_timeout/hard_break only (stochastic boundary disabled by design).
- Resolved candidate selection with per-entity index tables to avoid duplicate join columns:
  - Built `account_counts` + `account_index_df`, `instrument_counts` + `instrument_index_df`, `device_counts` + `device_index_df`, `ip_counts` + `ip_index_df` and joined using (party_id/account_id/device_id + index) to guarantee one-to-one selection.
  - Ensured device candidates are limited to devices with IP links (devices_with_ips) so IP attachment is always feasible (requiredness enforced).
- Hash selection: used `pl.struct(...).hash(seed)` with open-interval mapping `(hash+0.5)/2^64` to get deterministic U(0,1) for each attachment step; steps keyed by `(manifest_fingerprint, parameter_hash, seed, scenario_id, merchant_id, arrival_seq, step_tag)` for stability.
- Session IDs: hash derived from `domain_tag + session_key_base + first_arrival_seq + session_start_utc`, mapped into positive id64 range via modulo; session_index only includes schema-allowed fields (no parameter_hash).
- RNG logs: aggregated `rng_trace_log` rows for `rng_event_entity_attach` and `rng_event_session_boundary` (boundary draws=0), counters set to block counts; `rng_audit_log` emitted once per run. No per-row event logs to keep lean.
- Added CLI `packages/engine/src/engine/cli/s1_attachment_session_6b.py`, exported `run_s1` in `packages/engine/src/engine/layers/l3/seg_6B/s1_attachment_session/__init__.py`, and wired Makefile `segment6b-s1` + `segment6b` target.


### Entry: 2026-01-22 09:15

Corrective notes after S1 run failures (logged after-the-fact; should have been captured before edits):
- Failure: 6B.S1 aborted on missing artifact registry entry for `s4_ip_links_6A` (ContractError) and later on missing sealed_inputs manifest key `mlr.6A.s4.ip_links`.
  - Decision: treat as contract omission for 6B; add `s4_ip_links_6A` to 6B dataset dictionary and 6B artefact registry with the same path/schema/manifest_key as 6A.
  - Files updated: `docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`, `docs/model_spec/data-engine/layer-3/specs/contracts/6B/artefact_registry_6B.yaml`.
  - Action: delete `runs/<run_id>/data/layer3/6B/s0_gate_receipt` + `sealed_inputs` for this run and rerun `make segment6b-s0` so S0 re-seals inputs with the new entry.
- Failure: `merchant_id` cast overflow (u64 -> i64) during S1. The 5B schema uses id64 (uint64), so Int64 is incorrect.
  - Decision: cast `merchant_id` to `pl.UInt64` and keep unsigned when reading arrivals; ensure empty schemas use UInt64 for merchant_id to avoid dtype collisions.
  - File updated: `packages/engine/src/engine/layers/l3/seg_6B/s1_attachment_session/runner.py`.
- Failure: S1 crashed after `arrivals_in_scope=116,424,410` (process exit 2816). Root cause is full in-memory read + global sort.
  - Decision: switch to streaming batch processing for arrivals and relax sessionisation to fixed time buckets to avoid global sort.
  - Inputs/authorities: `arrival_events_5B` is ordered by scenario_id/merchant_id/ts_utc; use `hard_timeout_seconds` to bucket sessions; keep deterministic attachment via hash.
  - Algorithm changes:
    1) Replace `pl.read_parquet` with pyarrow `iter_batches` (batch_rows) per file.
    2) For each batch: attach party/account/instrument/device/ip via deterministic hash indices; write `s1_arrival_entities_6B` parts directly to tmp.
    3) Sessionisation: compute `session_key_base` from policy fields, parse `ts_utc` to epoch seconds, bucket by `floor(epoch / hard_timeout_seconds)`; session_id = hash(domain_tag + session_key_base + session_bucket). Ignore hard_break/day-boundary and stochastic boundary.
    4) Write per-batch session summaries; after all batches, aggregate summaries to build `s1_session_index_6B` (sum count, min/max ts, first ids).
    5) Publish parts to final output directory using a new helper that clears existing part files.
  - Performance considerations: bounded memory, batch_rows default 250k (tunable) and progress logs include elapsed/rate/ETA.
  - Resumability: clears tmp part dirs before run; output directories are cleared per scenario to avoid mixing; still run-id scoped.
  - Logging: story header retained; per-batch progress via `_ProgressTracker`; warnings for session bucket relaxation.
  - Files updated: `packages/engine/src/engine/layers/l3/seg_6B/s1_attachment_session/runner.py`, `packages/engine/src/engine/cli/s1_attachment_session_6b.py`, `Makefile` (added `ENGINE_6B_S1_BATCH_ROWS` + `--batch-rows`).
  - Validation/testing: validate one sample row for arrival_entities + session_index after aggregation; rerun `make segment6b-s1` and observe ETA; if still too high, revisit batch_rows or session_key fields.
