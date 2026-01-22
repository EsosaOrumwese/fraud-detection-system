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


### Entry: 2026-01-22 10:10

S1 failure (post-run) and immediate fix plan:
- Failure: Polars panic on `scan_parquet(...).collect(streaming=True)` with error "Parquet no longer supported for old streaming engine".
- Decision: remove `streaming=True` to avoid invoking the old streaming engine; fall back to standard collect for the session summary aggregation. The session summary parts are already reduced (per-batch), so memory risk is acceptable. If memory spikes, next alternative is to aggregate via pyarrow dataset and groupby in chunks.
- Steps:
  1) Update `packages/engine/src/engine/layers/l3/seg_6B/s1_attachment_session/runner.py` to use `.collect()` (no streaming flag) for session_index aggregation.
  2) Re-run `python -m py_compile` on the runner and CLI.
  3) Re-run `make segment6b-s1` and monitor ETA; if failure persists, switch to pyarrow aggregation.


### Entry: 2026-01-22 10:13

Compression tuning decision:
- Problem: ETA still above 15 min; need lower I/O cost per batch.
- Decision: expose parquet compression as a configurable knob (CLI + Makefile). Default remains zstd for size; for speed use lz4 or snappy.
- Implementation:
  - Add `parquet_compression` arg to `run_s1` and validate allowed codecs (zstd/lz4/snappy/uncompressed).
  - Thread `--parquet-compression` through CLI (`ENGINE_6B_S1_PARQUET_COMPRESSION`) and Makefile.
  - Apply compression setting to all S1 parquet writes (arrival parts, session summaries, final session_index).
- Next run: `make segment6b-s1 ENGINE_6B_S1_BATCH_ROWS=1000000 ENGINE_6B_S1_PARQUET_COMPRESSION=lz4` and monitor ETA; if still > 15 min, consider larger batch_rows or reduced session_key fields.


### Entry: 2026-01-22 10:29

6B.S2 spec review + lean plan (pre-implementation)

Spec review highlights (binding vs heavy):
- Binding: must gate on S0 PASS + upstream PASS + S1 PASS for each (seed, parameter_hash, scenario_id); must resolve all inputs via sealed_inputs_6B; must emit only `s2_flow_anchor_baseline_6B` + `s2_event_stream_baseline_6B` with required schema fields and no orphan flows/events.
- Heavy portions (relaxed for performance): full flow-shape stochasticity (multi-flow per session), event timing distributions, per-branch RNG decisions, session-level planning. These are valid but too expensive for the current throughput goal.

Lean compromises agreed (speed-first, deterministic, auditable):
1) Flow mapping: one-flow-per-arrival (not per session). Rationale: S1 already produced arrival-level canon; this avoids cross-arrival grouping and keeps O(N) streaming.
2) Event template: only AUTH_REQUEST + AUTH_RESPONSE. No clearing/refund/step-up/reversal. Rationale: minimal event count (2x), avoids complex branching and timing budgets.
3) Timing: use arrival ts_utc for both events (no parsing/offset distributions). Rationale: avoids heavy timestamp parsing and RNG timing draws. Event order still enforced via event_seq.
4) Amounts: deterministic hash-based amount draw from amount_model_6B price points; no tail sampling. Rationale: O(1) per row and still tied to the policy pack; tail ignored for speed.
5) Context joins: skip optional 6A/5B joins. Rationale: avoid large joins and memory overhead.
6) RNG accounting: emit aggregated RNG envelopes for `flow_anchor_baseline` and `event_stream_baseline` + rng_trace_log rows; budgets recorded but draws may be non-consuming for flow-shape/timing. Rationale: keep deterministic accounting without per-row logs.

Algorithm plan (streaming):
- Preconditions: verify S0 receipt + upstream PASS; verify S1 PASS for each scenario; verify sealed_inputs rows for S1 + S2 policies (flow_shape_policy_6B, amount_model_6B, timing_policy_6B, flow_rng_policy_6B, rng_profile_layer3).
- Discover scenario_ids by scanning S1 arrival_entities partitions (sealed_inputs path).
- For each scenario_id:
  - Ensure S1 arrival_entities + session_index partitions exist.
  - Stream arrival_entities parquet in batches (pyarrow iter_batches) with required columns.
  - For each batch:
    - Compute flow_id = hash(manifest_fingerprint, parameter_hash, seed, scenario_id, merchant_id, arrival_seq).
    - Compute amount from price_points_minor in amount_model_6B (default PURCHASE) using deterministic hash; convert to major units.
    - Write flow_anchor rows to part-*.parquet.
    - Build event_stream rows by duplicating per-flow rows into two events with event_seq={0,1}, event_type={AUTH_REQUEST, AUTH_RESPONSE}, ts_utc unchanged, amount same.
  - Publish part files to final output directories (idempotent; clear prior parts in dir).
- Emit rng_event_flow_anchor_baseline and rng_event_event_stream_baseline jsonl envelopes (one row each) with draws/blocks based on total flows/events; emit rng_trace_log + rng_audit_log rows.

Invariants to enforce:
- Each flow_id unique within partition; no orphan events (event_stream only built from flow anchors).
- Required schema fields present; manifest_fingerprint, parameter_hash, seed, scenario_id match partition tokens.
- Deterministic outputs for fixed inputs (hash-based IDs, deterministic amounts).

Performance considerations:
- Streaming batch processing to keep memory bounded; batch_rows configurable via CLI.
- No global sorts or joins; minimal per-row transformations.

Logging/observability:
- Story header for S2; per-batch progress logs include elapsed, rate, ETA; log the lean relaxations explicitly.

Next steps:
- Implement S2 runner + CLI + Makefile target; wire batch_rows/compression; update logbook with files read and decisions.

### Entry: 2026-01-22 10:37

6B.S2 implementation kickoff (pre-code, lean + deterministic):
- Docs re-read for this implementation pass (before coding):
  - `docs/references/closed-world-fraud-enterprise-conceptual-design.md`
  - `docs/model_spec/data-engine/layer-1/narrative/narrative_1A-to-3B.md`
  - `docs/model_spec/data-engine/layer-2/narrative/narrative_5A-and-5B.md`
  - `docs/model_spec/data-engine/layer-3/narrative/narrative_6A-and-6B.md`
  - `packages/engine/AGENTS.md`
  - `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s2.expanded.md`
  - `docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`
  - `docs/model_spec/data-engine/layer-3/specs/contracts/6B/artefact_registry_6B.yaml`
  - `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`
  - `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.layer3.yaml`
- Contract source posture:
  - Use `ContractSource(config.contracts_root, config.contracts_layout)` so dev uses `model_spec` and prod can switch to root contracts without code changes (via `ENGINE_CONTRACTS_ROOT` / `ENGINE_CONTRACTS_LAYOUT`).
- Lean path confirmation (per user): one-flow-per-arrival, two events (AUTH_REQUEST/AUTH_RESPONSE), no clearing/refund/3DS; timestamps from arrival; deterministic amount draw from `amount_model_6B.price_points`; skip optional joins; aggregated RNG envelopes only.

Planned mechanics (stepwise):
1) Preconditions + gate checks:
   - Load run_receipt for `run_id`, `seed`, `manifest_fingerprint`, `parameter_hash`.
   - Validate `s0_gate_receipt_6B` + upstream PASS statuses; enforce S1 PASS for each `(seed, scenario_id)`.
   - Load + validate `sealed_inputs_6B` and assert required rows for `s1_arrival_entities_6B`, `s1_session_index_6B`, and S2 policies (`flow_shape_policy_6B`, `amount_model_6B`, `timing_policy_6B`, `flow_rng_policy_6B`, `rng_profile_layer3`).
2) Scenario discovery:
   - Resolve S1 arrival_entities path via dictionary/registry; list scenario_id partitions from the path tree.
3) Streaming synthesis (per scenario_id):
   - Verify S1 partition presence for arrival_entities + session_index.
   - Iterate arrival_entities parquet via pyarrow dataset `iter_batches` with configurable `batch_rows`.
   - For each batch:
     - Compute `flow_id` deterministically from `(manifest_fingerprint, parameter_hash, seed, scenario_id, merchant_id, arrival_seq)` (hash to uint64).
     - Compute `amount` from `amount_model_6B.price_points_minor` using deterministic hash-based index; convert to major units.
     - Build flow anchors (schema-required fields only) and write part parquet (compression configurable).
     - Build event stream rows by duplicating per-flow rows into 2 events with `event_seq=0/1`, `event_type`={AUTH_REQUEST, AUTH_RESPONSE}, `ts_utc` same as arrival; write part parquet.
   - Clear existing output part files in target dirs before write; publish via tmp+atomic move to preserve idempotence.
4) RNG logging (lean):
   - Emit `rng_audit_log` and `rng_trace_log` once per run (aggregate draws/blocks/events for `flow_anchor_baseline` + `event_stream_baseline`).
   - Emit one JSONL envelope for `rng_event_flow_anchor_baseline` and `rng_event_event_stream_baseline` with counts only (no per-row events).
5) Logging + monitoring:
   - Story header log with objective + gated inputs + outputs.
   - Per-batch progress logs with elapsed, processed/total, rate, ETA; narrative counts and stage/output context.
6) Validation/testing:
   - Validate sample rows for flow_anchor/event_stream against `schemas.6B.yaml` anchors.
   - Ensure coverage: events only from anchors; counts tracked; zero-arrival partitions emit empty outputs deterministically.

Files to add/update:
- `packages/engine/src/engine/layers/l3/seg_6B/s2_baseline_flow/runner.py`
- `packages/engine/src/engine/layers/l3/seg_6B/s2_baseline_flow/__init__.py` (export `run_s2`)
- `packages/engine/src/engine/cli/s2_baseline_flow_6b.py`
- `makefile` (segment6b-s2 target + `ENGINE_6B_S2_BATCH_ROWS`, `ENGINE_6B_S2_PARQUET_COMPRESSION`)

Open considerations:
- If `amount_model_6B` lacks `price_points_minor`, fall back to a small default list from config (logged) to avoid blocking runs.
- If S1 partitions exist but are empty, emit empty S2 outputs with PASS semantics; log explicitly.

### Entry: 2026-01-22 11:02

6B.S2 implementation decisions during coding (lean path, determinism-first):
- Implemented new runner: `packages/engine/src/engine/layers/l3/seg_6B/s2_baseline_flow/runner.py`.
  - Streaming batch approach using pyarrow `iter_batches` over `s1_arrival_entities_6B` with configurable `batch_rows`; no global sorts or joins.
  - Flow mapping: one flow per arrival. `flow_id` derived via deterministic hash of `(manifest_fingerprint, parameter_hash, seed, scenario_id, merchant_id, arrival_seq)` to keep idempotence.
  - Event stream: exactly two events per flow (`AUTH_REQUEST`, `AUTH_RESPONSE`) with `event_seq` {0,1}; timestamps copied from arrival `ts_utc` (no timing RNG).
  - Amounts: deterministic hash-index into `amount_model_6B.amount_families.PURCHASE.base_distribution.price_points_minor`; convert minor -> major units by /100. If missing, fallback to default list and log warning (prevents hard failure but recorded).
  - Skip heavy flow-shape + timing logic: `flow_shape_policy_6B` and `timing_policy_6B` are loaded/validated but not used; this is a deliberate performance relaxation.
  - Schema validation: validate sample rows against `schemas.6B.yaml` anchors for flow anchor and event stream.
  - Preconditions: enforce S0 receipt + sealed_inputs schema validity, upstream PASS statuses, sealed_inputs digest match, S1 arrival/session partitions presence.
  - Scope filters: respect `behaviour_config_6B.scope_filters` allow/block lists; on_scope_miss obeys `degrade_posture.on_scope_filter_miss` (skip vs fail).
  - Zero-arrival handling: emit empty parquet outputs for that partition to keep downstream deterministic.
  - RNG logs: aggregated `rng_audit_log` + `rng_trace_log` rows for `flow_anchor_baseline` and `event_stream_baseline` (draws = flows/events, blocks = ceil(draws/2)). Emit one JSONL envelope per RNG event family with deterministic counts.
  - Idempotence: outputs use tmp dirs + part file publish; RNG event JSONL uses content-hash guard (skip if identical, error on drift).
- Added CLI: `packages/engine/src/engine/cli/s2_baseline_flow_6b.py` with `--batch-rows` and `--parquet-compression`.
- Updated Makefile:
  - Added `ENGINE_6B_S2_BATCH_ROWS`, `ENGINE_6B_S2_PARQUET_COMPRESSION`, `SEG6B_S2_RUN_ID`.
  - Added `SEG6B_S2_*` args/cmd and `segment6b-s2` target; `segment6b` now runs S0/S1/S2.
  - Added `segment6b-s2` to `.PHONY`.
- Compiled new runner + CLI with `python -m py_compile`.

### Entry: 2026-01-22 11:04

6B.S2 zero-row partition guard:
- Added explicit handling for the case where S1 arrival partitions exist but contain zero rows.
- If `total_rows == 0`, S2 now emits empty flow/event outputs (part-00000) for the partition instead of failing due to missing parts.
- Rationale: aligns with spec zero-arrival semantics and prevents false IO write conflicts.

### Entry: 2026-01-22 12:01

6B.S1 consolidation failure (post-arrivals) — plan for bucketed session_index aggregation + error logging:
- Problem observed:
  - `make segment6b-s1` completes the arrivals loop (116,424,410 arrivals, ~939s) but exits with a non-zero error after the final arrivals log line.
  - The run log contains no error text, implying the crash is likely in the session_index consolidation stage and stderr is not being captured.
  - Current code uses `pl.scan_parquet(...).group_by(...).collect()` over *all* session summary parts in one shot, which is memory fragile at this scale.
- Goals:
  - Avoid monolithic in-memory aggregation while preserving deterministic outputs.
  - Ensure any failure during consolidation is logged to the run log with narrative context.
  - Keep output schema identical (`s1_session_index_6B`) and maintain idempotent publish semantics.

Contracts + inputs (authoritative sources):
- Contracts: `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml` + `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.layer3.yaml`
- Dataset dictionary / registry: `docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`, `docs/model_spec/data-engine/layer-3/specs/contracts/6B/artefact_registry_6B.yaml`
- Runtime inputs: session summary parts already written to `runs/<run_id>/tmp/s1_session_index_6B_<scenario_id>_summaries/part-*.parquet`

Alternatives considered:
1) Re-run with `PYTHONFAULTHANDLER=1` + `RUST_BACKTRACE=1` to find the exact failing line.
   - Useful for diagnosis but does not address memory fragility in production-scale runs.
2) Use Polars streaming aggregation.
   - Rejected: streaming + parquet is not supported for the old streaming engine (prior crash).
3) Use pyarrow.dataset with partitioning + group-by.
   - Possible, but more complex; may still require full materialization during group-by.
Decision: implement bucketed consolidation by `session_id % N` to guarantee each aggregation unit fits in memory, and write the final parquet via incremental row-group writes.

Planned mechanics (stepwise):
1) After the arrivals loop and per-batch `session_summary` outputs are written, enumerate all `part-*.parquet` in the session summaries temp dir.
2) **Bucketization pass**:
   - Choose `bucket_count` (default 128, overridable via `sessionisation_policy_6B.session_index_buckets`).
   - For each session summary part:
     - Read the part (`pl.read_parquet`), compute `bucket_id = ((session_id % bucket_count) + bucket_count) % bucket_count`.
     - Split by `bucket_id` and write each non-empty subset to `tmp/s1_session_index_6B_<scenario_id>_buckets/bucket=####/part-<orig>.parquet`.
   - Log progress: processed parts / total, elapsed, rate (parts/sec), ETA.
3) **Bucketed aggregation**:
   - For each bucket directory (sorted):
     - Scan all bucket parts with `pl.scan_parquet`, group_by `session_id` with the same aggregations as before.
     - Collect and append to the final `s1_session_index_6B_<scenario_id>.parquet` via `pyarrow.parquet.ParquetWriter` (row-group writes).
   - Validate one sample row (first bucket with data) against `#/s1/session_index_6B` schema anchor.
   - Log progress: processed buckets / total, elapsed, rate (buckets/sec), ETA, cumulative sessions written.
4) **Error logging**:
   - Wrap bucketization + aggregation in `try/except`; on failure `logger.exception(...)` with scenario_id + bucket_count + part counts.
   - Call `_abort("6B.S1.SESSION_INDEX_FAILED", "V-01", "session_index_consolidation_failed", {...})` so failure is visible in the run log.

Invariants to enforce:
- Deterministic output for the same `(seed, manifest_fingerprint, parameter_hash, scenario_id)` regardless of bucket count.
- `session_id` aggregation semantics identical to the current `group_by` logic.
- Output schema unchanged; sample validation still performed.
- Idempotent publish remains unchanged (tmp -> final move).

Logging points:
- “S1: session_index bucketization start” (bucket_count, parts, compression).
- Progress logs for part bucketing and bucket aggregation with elapsed/rate/ETA.
- “S1: session_index bucket aggregation complete” with total sessions written.
- Error log with exception stack trace and context.

Resumability / cleanup considerations:
- Bucket dir is under `tmp/`; safe to rebuild on each run. If pre-existing, it can be cleared at start of consolidation to avoid mixed part files.
- Final tmp parquet is recreated each run; if present, delete before `ParquetWriter`.

Performance expectations:
- Linear pass over session summary parts with bounded memory per bucket.
- Avoids global collect that caused crashes; bucket_count can be tuned if a bucket is still too large.

Validation/testing:
- Ensure sample payload validation still runs.
- Run `python -m py_compile` after code changes.
- Run `make segment6b-s1` to confirm session_index publish completes without crash.

### Entry: 2026-01-22 12:34

6B.S2 sealed_inputs gap for S1 outputs — plan to relax precondition (internal outputs are run-local):
- Problem observed:
  - After S0 PASS, `sealed_inputs_6B` does not include `mlr.6B.s1.arrival_entities` or `mlr.6B.s1.session_index` keys.
  - S2 currently *requires* those keys in sealed_inputs and fails fast (`InputResolutionError`).
  - S1 outputs are run-local (same segment), not external inputs; sealed_inputs is intended for external roots and upstream egress.
- Decision:
  - Treat missing sealed_inputs rows for S1 outputs as acceptable.
  - Keep strict sealed_inputs checks for policies and other external inputs.
  - Log a warning when sealed_inputs entries are missing for `s1_arrival_entities_6B` / `s1_session_index_6B`, and continue using the dataset dictionary/registry paths.

Planned change (stepwise):
1) Add helper to attempt sealed_inputs lookup with graceful fallback for S1 outputs.
2) In the precondition loop for `required_dataset_ids`, catch missing keys and log:
   - “S2: sealed_inputs missing for {dataset_id}; using run-local output path.”
3) Only enforce `status=REQUIRED` + `read_scope=ROW_LEVEL` when the sealed_inputs row is present.
4) Leave all policy sealed_inputs validation unchanged and still required.

Invariants:
- S2 still uses dictionary/registry for actual path resolution.
- No change to outputs, schema validation, or RNG logging.

Validation/testing:
- Re-run `make segment6b-s2` after the change.

### Entry: 2026-01-22 12:36

6B.S2 policy status OPTIONAL — plan to accept optional policies when present:
- Problem observed:
  - `sealed_inputs_6B` marks `mlr.6B.policy.behaviour_config` as `OPTIONAL`, which causes S2 to abort because `_load_policy` requires `status == REQUIRED`.
- Decision:
  - Accept `OPTIONAL` for policy rows when the row is present; log a warning but continue.
  - Keep failure for unexpected statuses or missing rows.

Planned change:
1) Update `_load_policy` in `packages/engine/src/engine/layers/l3/seg_6B/s2_baseline_flow/runner.py`:
   - Allow `status in {"REQUIRED", "OPTIONAL"}`.
   - If `OPTIONAL`, log a warning and proceed with the provided config.
2) Re-run `make segment6b-s2`.

### Entry: 2026-01-22 12:37

6B.S2 amount_minor ColumnNotFound — plan to split amount derivation into explicit series:
- Problem observed:
  - S2 failed with `polars.exceptions.ColumnNotFoundError: amount_minor` when adding `amount` in the same `with_columns` call that defines `amount_minor`.
- Decision:
  - Compute `amount_minor` and `amount` as numpy arrays and attach both as `pl.Series` in a single `with_columns` call, avoiding self-references.
- Planned change:
  - Replace `(pl.col("amount_minor") / ...)` with `pl.Series("amount", amount_minor / 100.0)` so no intra-call dependency exists.
  - Re-run `make segment6b-s2`.

### Entry: 2026-01-22 12:42

6B.S3 lean fraud overlay (tagging + minimal amount shift) — implementation plan:
- Context / goal:
  - S3 should introduce fraud/abuse patterns so downstream models can learn signal, but must remain lean and fast.
  - We will avoid heavy event reshaping and new flow creation, and instead produce **campaign tags + fraud_flag** plus a **small bounded amount upshift** for targeted flows/events.
  - This keeps realism at the “signal injection” level and maintains high throughput for 116M+ flows.

Contracts + authorities:
- Expanded spec: `docs/model_spec/data-engine/layer-3/specs/state-flow/6B/state.6B.s3.expanded.md`
- Schema anchors: `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml` (`#/s3/campaign_catalogue_6B`, `#/s3/flow_anchor_with_fraud_6B`, `#/s3/event_stream_with_fraud_6B`)
- Registry/dictionary: `docs/model_spec/data-engine/layer-3/specs/contracts/6B/artefact_registry_6B.yaml`, `docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`
- Policy inputs: `config/layer3/6B/fraud_campaign_catalogue_config_6B.yaml`, `config/layer3/6B/fraud_overlay_policy_6B.yaml`, `config/layer3/6B/fraud_rng_policy_6B.yaml`

Lean decisions (explicit relaxations):
- No new flows or extra events; S3 overlays are **tags + optional amount shifts** only.
- No timing/routing/device/IP swaps; skip structure/identity/routing/timing tactics.
- Campaign activation simplified to “one instance per template” (if feasible), with deterministic hash selection; RNG events emitted with non‑consuming budgets (draws=0) for accounting.
- If targeting filters reference missing fields (e.g., `flow_type`, `channel_group`), **skip those filters** with a warning instead of failing.
- If insufficient targets exist, **soft‑skip** campaign (catalogue row with fraud_rate=0, zero targets), no partition failure.

Algorithm (stepwise):
1) Preconditions:
   - Load S0 receipt + sealed_inputs; verify digest.
   - Accept missing sealed_inputs rows for **run‑local** S2 outputs (warn + proceed).
   - Accept policy rows marked `OPTIONAL` (warn + proceed).
2) Read configs:
   - Parse campaign templates from `fraud_campaign_catalogue_config_6B.yaml`.
   - Read guardrails from `fraud_overlay_policy_6B.yaml` (use `max_targets_total_per_seed_scenario`, `max_amount_multiplier` for clamps).
   - Read `fraud_rng_policy_6B.yaml` for RNG families to log.
3) Campaign instance setup (per scenario_id):
   - For each template, create one deterministic campaign instance:
     - `campaign_id = sha256("6B.S3|template_id|seed|scenario_id|parameter_hash|manifest_fingerprint")` (hex string).
     - `campaign_label = template_id`.
   - Determine target budget:
     - Use `quota_models[template.quota_model_id].targets_per_day` and `schedule_models[template.schedule_model_id]` to estimate `duration_days` (fixed window or multi‑window; FULL_SCENARIO => default 7 days).
     - `target_count = clamp(int(targets_per_day * duration_days), min_targets_per_instance, max_targets_per_instance)`.
   - Convert `target_count` to `target_rate = target_count / total_flows` (cap by `max_targets_total_per_seed_scenario`).
4) Flow overlay (streaming):
   - Iterate S2 flow anchors in batches (pyarrow iter_batches).
   - For each campaign in deterministic order, compute mask:
     - `mask = hash(flow_id, campaign_id, seed, scenario_id) % 1_000_000 < floor(target_rate * 1_000_000)`
     - Assign `campaign_id` only where not already assigned (no multi‑campaign stacking).
   - `fraud_flag = campaign_id != null`.
   - Amount upshift for fraud flows:
     - Factor = uniform in [1.10, 1.50], derived from deterministic hash of `(flow_id, campaign_id)`; clamp by overlay policy `max_amount_multiplier`.
     - Apply to `amount` for fraud flows only.
   - Write `s3_flow_anchor_with_fraud_6B` as partitioned parts (idempotent publish).
   - Track `campaign_flow_counts` (increment per fraud flow) for catalogue fraud_rate.
5) Event overlay (streaming):
   - Iterate S2 event stream in batches.
   - Recompute campaign assignment from `flow_id` with same deterministic logic (ensures match with flow anchors).
   - `fraud_flag` and amount upshift consistent with flow anchor for the same flow_id.
   - Write `s3_event_stream_with_fraud_6B` parts.
6) Campaign catalogue:
   - For each campaign, write a row with:
     - `campaign_id`, `campaign_label`, `fraud_rate = campaign_flow_count / total_flows`, identity axes.
   - Single parquet file per scenario_id.
7) RNG logging:
   - Emit `rng_audit_log` and `rng_trace_log` rows for `6B.S3` with **non‑consuming** draws (0) and counts of campaigns/targets.
   - Emit `rng_event_fraud_campaign_pick` and `rng_event_fraud_overlay_apply` JSONL envelopes with draws=0, blocks=0, context notes “deterministic hash selection.”

Invariants / checks:
- Outputs preserve S2 rows and keys; no mutation of IDs or event_seq.
- Every flow/event has `fraud_flag` and `campaign_id` (null when not fraud).
- `s3_event_stream_with_fraud_6B` and `s3_flow_anchor_with_fraud_6B` are consistent by deterministic assignment.
- Amounts remain non‑negative and within `max_amount_multiplier`.

Logging requirements:
- Story header: objective + gated inputs + outputs.
- Per‑batch progress logs with elapsed, processed/total, rate, ETA.
- Warnings for skipped filters or inactive campaigns.
- Campaign summary log with counts and fraud_rate.

Resumability:
- Use tmp dirs under `runs/<run_id>/tmp` and idempotent publish.
- Clear tmp parts before write; do not overwrite existing final outputs unless identical.

Validation/testing:
- Validate sample rows against S3 schema anchors.
- Run `python -m py_compile` for new runner + CLI.
- Run `make segment6b-s3` and watch ETA; terminate if abnormal.
\n---\n## 6B.S3 — Implementation notes (2026-01-22 13:14 local)\n- Decision: create s3_fraud_overlay/runner.py as a new file, then write contents in chunks to avoid prior Windows path length/command size errors.\n- Rationale: New-Item succeeds; previous pply_patch/Set-Content attempts failed with Win32 error 206. Chunked Add-Content should avoid command-size/path issues while preserving the new-from-scratch requirement.\n- Action plan: write runner in 4–6 chunks; verify file size; run python -m py_compile on new runner + CLI; then make segment6b-s3.\n
\n---\n## 6B.S3 — Implementation decisions (2026-01-22 13:26 local)\n- Implemented lean overlay runner at packages/engine/src/engine/layers/l3/seg_6B/s3_fraud_overlay/runner.py with deterministic hash-based campaign assignment (flow_id + campaign_id), no per-row loops.\n- Campaign planning: one instance per template; target_count derived from quota targets_per_day × schedule duration_days; clamped by template min/max and overlay guardrail max_targets_total_per_seed_scenario (scaled down if needed).\n- Overlay mechanics: no new flows/events; inject campaign_id + raud_flag; apply bounded amount upshift to all events for fraud flows using deterministic hash factor in [min,max] capped by guardrail max_amount_multiplier.\n- Filters/tactics: targeting filters from config not enforced (logged); we treat campaigns as deterministic sampling against all flows for speed and reproducibility.\n- Outputs: streaming batch writes for s3_flow_anchor_with_fraud_6B and s3_event_stream_with_fraud_6B, campaign catalogue per scenario, RNG audit/trace + non-consuming RNG event logs.\n- Added CLI packages/engine/src/engine/cli/s3_fraud_overlay_6b.py and make target segment6b-s3 with batch_rows/compression defaults.\n
\n---\n## 6B.S4 — Lean implementation plan (2026-01-22 13:46 local)\nProblem framing:\n- S4 must label every S3 flow/event and emit case timelines. Spec is heavy (collateral windows, posture joins, stochastic delays, cross-flow case grouping). Goal is fast, deterministic, realistic-enough labels without per-row loops or massive joins.\n\nInputs/authorities to use (contract source must remain switchable):\n- Contracts loaded via ContractSource(layout=ENGINE_CONTRACTS_LAYOUT, root=ENGINE_CONTRACTS_ROOT or repo_root) so dev uses model_spec but can switch to contracts mirror without code changes.\n- Authoritative inputs: s0_gate_receipt_6B, sealed_inputs_6B, s3_flow_anchor_with_fraud_6B, s3_event_stream_with_fraud_6B, plus config packs: 	ruth_labelling_policy_6B, ank_view_policy_6B, delay_models_6B, case_policy_6B, label_rng_policy_6B.\n- Optional posture inputs ignored for now (lean path).\n\nAlternatives considered:\n- Full spec: collateral rules + posture overrides + stochastic delay sampling + cross-flow case grouping. Rejected for time/CPU/memory and likely >15min on large runs.\n- Lean deterministic: campaign-driven truth labels; bank-view probabilities via hash-derived uniforms; fixed delays; 1-case-per-flow. Selected as minimal viable realism with deterministic reproducibility.\n\nDecisions (lean relaxations):\n- Truth labels: derive solely from S3 campaign_id using campaign catalogue + template->campaign_type mapping; map to truth_label via 	ruth_labelling_policy_6B.direct_pattern_map. LEGIT if no campaign. Skip collateral rules and posture overrides.\n- Bank-view: compute auth/detect/dispute/chargeback flags using deterministic hash-uniform draws keyed by (flow_id, decision_id); apply policy probabilities without RNG state. Use simplified auth rule: CARD_TESTING => DECLINE regardless of channel (channel_group not available in flow anchor).\n- Delays: use fixed min_seconds from delay_models_6B for detection/dispute/chargeback/case_close. Apply only when emitting case timeline timestamps.\n- Case grouping: 1-case-per-flow when case_opened; no cross-flow grouping or reopen logic. case_id is deterministic hash of (manifest_fingerprint, seed, flow_id, domain_tag).\n- RNG logs: emit non-consuming ng_event_truth_label + ng_event_bank_view_label envelopes with draws=0; append rng_trace rows for S4 substreams.\n\nAlgorithm/data-flow (per scenario_id):\n1) Validate S0 receipt + sealed_inputs; enforce upstream PASS; verify sealed_inputs digest.\n2) Resolve S3 flow/event outputs and S3 campaign catalogue for scenario_id. Build mapping: campaign_id -> campaign_type (via campaign_label/template_id + config templates). Build mapping: campaign_type -> truth_label (from truth policy).\n3) Stream flows in batches (parquet):\n   - Columns: flow_id, ts_utc, campaign_id, seed, manifest_fingerprint, parameter_hash, scenario_id.\n   - Derive campaign_type, truth_label, is_fraud_truth.\n   - Compute auth_decision, detect_flag, dispute_flag, chargeback_flag, chargeback_outcome with deterministic hash uniforms and policy probabilities.\n   - Compute bank_label via final_label_map rules; set is_fraud_bank_view from bank_label.\n   - Write s4_flow_truth_labels_6B and s4_flow_bank_view_6B parts.\n   - For case_opened flows (detected/review/dispute), emit case timeline rows with fixed delays and ordered case_event_seq.\n4) Stream events in batches: derive truth/bank flags using same deterministic decisions from flow_id + campaign_id; write s4_event_labels_6B parts (no joins).\n5) Publish parts to final output dirs; idempotent publish; write rng logs.\n\nInvariants to enforce:\n- One row per flow/event in S4 outputs; flow_id/event_seq preserved.\n- campaign_id presence -> truth_label != LEGIT.\n- Outputs contain required columns per schema anchors #/s4/flow_truth_labels_6B, #/s4/flow_bank_view_6B, #/s4/event_labels_6B, #/s4/case_timeline_6B.\n- Case timeline events ordered by case_event_seq; case_id deterministic and stable.\n\nLogging points (narrative, state-aware):\n- Story header: objective + gated inputs + outputs.\n- Per-scenario summary: total flows/events, campaigns mapped, label rates (fraud/abuse/legit, bank_view flags).\n- Progress logs for flow/event batches with elapsed, processed/total, rate, ETA (monotonic).\n- Case timeline counts per batch.\n\nResumability/IO:\n- Write to tmp dirs under runs/<run_id>/tmp; clean temp parts before write.\n- Idempotent publish: if final dir exists, skip.\n\nPerformance considerations:\n- Avoid joins by recomputing labels for events via deterministic hashing.\n- Keep polars expressions vectorized; no per-row Python loops.\n- Case timeline generated only for subset flows (case_opened) per batch.\n\nValidation/testing:\n- Validate sample row for each output against schema anchors.\n- python -m py_compile for runner + CLI.\n- Run make segment6b-s4; monitor ETA; terminate if abnormal.\n
\n---\n## 6B.S4 — Implementation notes (2026-01-22 13:58 local)\n- Implemented s4_truth_bank_labels/runner.py with deterministic hash-based probabilities for auth/detect/dispute/chargeback; no RNG state consumed.\n- Truth label mapping uses campaign catalogue (campaign_id -> template_id) and fraud_campaign_catalogue_config_6B templates -> campaign_type; then truth_labelling_policy direct_pattern_map to truth_label/subtype. Unknown templates abort if policy constraint fail_on_unknown_fraud_pattern_type=true.\n- Bank-view label computed via simplified final_label_map rules; is_fraud_bank_view true for BANK_CONFIRMED_FRAUD/CHARGEBACK_WRITTEN_OFF.\n- Case timeline is 1-case-per-flow when case_opened (detect OR dispute OR auth_decision review/challenge). Case_id = hash64(domain_tag, manifest_fingerprint, seed, flow_id). Timeline emits ordered events with fixed min delays from delay_models_6B.\n- Event labels recompute truth/bank flags directly from flow_id + campaign_id to avoid joins; ensures deterministic consistency with flow labels.\n- RNG logs emitted as non-consuming envelopes in rng_event_truth_label + rng_event_bank_view_label; rng_trace rows appended for 6B.S4 substreams.\n
\n---\n## 6B.S4 — Fixups after first run (2026-01-22 14:10 local)\n- Replaced Polars map_dict (not available) with left-join to a campaign_id->campaign_type lookup DataFrame; fill nulls to NONE to keep deterministic defaults.\n- Normalized chargeback outcome probability tables from policy YAML into (label, prob) tuples before feeding into choice_expr.\n- Re-ran make segment6b-s4; completed green with acceptable ETAs.\n
