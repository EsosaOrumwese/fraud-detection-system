# Decision Fabric Implementation Map
_As of 2026-02-05_

---

## Entry: 2026-02-05 15:13:45 — Phase 4 planning kickoff (DF scope + output contracts)

### Problem / goal
Prepare Phase 4.4 by locking DF v0 inputs/outputs and decision provenance requirements before implementation.

### Authorities / inputs
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md`
- Platform rails (canonical envelope, ContextPins, no-PASS-no-read, append-only).
- RTDL contracts under `docs/model_spec/platform/contracts/real_time_decision_loop/`.

### Decisions captured (v0 stance)
- DF is **EB-driven only**: consumes admitted events, emits DecisionResponse + ActionIntent via IG→EB.
- Decision boundary time is `ts_utc` (domain time). No hidden “now.”
- Decision provenance must include: `bundle_ref`, `snapshot_hash`, `graph_version`, `eb_offset_basis`, `degrade_posture`, `policy_rev`, `run_config_digest`.
- DecisionResponse event_id is deterministic: `H("decision_response", ContextPins, input_event_id, decision_scope)`.
- ActionIntent event_id is deterministic: `H("action_intent", ContextPins, input_event_id, action_domain)`; ActionIntent carries its own `idempotency_key` for AL.
- Degrade posture is a hard constraint; DF fails closed when DL/Registry/OFP is unavailable.

### Planned implementation scope (Phase 4.4)
- Implement EB consumer for traffic + context topics.
- Build deterministic decision plan: resolve registry bundle, fetch features (OFP), consult DL, produce DecisionResponse + ActionIntents.
- Publish outputs through IG admission (no direct EB writes).

---

## Entry: 2026-02-07 02:53:29 — Plan: expand DF component build plan phase-by-phase from platform 4.4

### Problem / goal
Current `decision_fabric.build_plan.md` is too compact (3 broad phases) for direct implementation execution. Platform `Phase 4.4` was expanded into explicit `4.4.A..4.4.L` DoD gates, so DF component planning must now be expanded with component-granular phases and acceptance checks.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (expanded Phase 4.4)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md`
- Existing DF build/impl docs.

### Decision trail (live)
1. Keep DF plan strictly component-scoped; do not absorb AL/DLA ownership from platform Phase 4.5.
2. Expand DF into implementation phases that map cleanly to platform 4.4 concerns:
   - trigger boundary,
   - DL/Registry integration,
   - context/feature acquisition and budget handling,
   - decision/intent synthesis and publish boundary,
   - determinism/idempotency,
   - observability/validation.
3. Make each phase contain executable DoD checks with explicit artifacts/tests expected.
4. Preserve progressive elaboration doctrine while still giving enough detail to execute v0 without ambiguity.

### Planned edits
- Replace the short three-phase DF plan with a phased v0 map and explicit DoD checklists aligned to platform 4.4.A-L.
- Mark integration-dependent checks (that require AL/DLA closure) explicitly as pending gates, not hidden assumptions.

---

## Entry: 2026-02-07 02:55:08 — Applied DF phase-by-phase build plan expansion

### Change applied
Updated `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` from a 3-phase high-level outline to an executable 8-phase plan with explicit DoD checklists.

### New DF phase map (v0)
1. Contracts + deterministic identity
2. Inlet boundary + trigger gating
3. DL integration + fail-safe enforcement
4. Registry bundle resolution + compatibility
5. Context/features acquisition + decision-time budgets
6. Decision synthesis + intent emission
7. Idempotency/checkpoints/replay safety
8. Observability/validation/closure boundary

### Alignment checks
- Mapped to platform Phase 4.4 gates (A-L) without absorbing AL/DLA authority from Phase 4.5.
- Preserved RTDL pre-design defaults (fail-closed compatibility, join budgets, deterministic resolver/output behavior, provenance minimums).
- Added explicit closure statement to keep component-green scope clear vs integration-pending gates.

---

## Entry: 2026-02-07 10:27:17 — Phase 1 implementation plan (contracts + deterministic identity)

### Problem / goal
Begin Decision Fabric implementation by closing Phase 1 DoD end-to-end:
- pin DF contracts and provenance requirements in code-facing helpers,
- lock deterministic identity recipes for decision and action events,
- pin RTDL event taxonomy/schema compatibility behavior (major mismatch fail-closed),
- keep docs/index references drift-safe.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` (Phase 1)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md`
- `docs/model_spec/platform/contracts/real_time_decision_loop/README.md`
- `docs/model_spec/platform/contracts/real_time_decision_loop/decision_payload.schema.yaml`
- `docs/model_spec/platform/contracts/real_time_decision_loop/action_intent.schema.yaml`

### Decision trail (before coding)
1. Create a new `src/fraud_detection/decision_fabric` package now, but keep Phase 1 runtime-surface minimal:
   - contracts/parsing helpers,
   - deterministic identity helpers,
   - taxonomy compatibility helper.
2. Preserve current contract file names to avoid churn (`decision_payload.schema.yaml` remains authoritative for DecisionResponse payload in v0), while making documentation explicit that DF `decision_response` event_type uses that schema path.
3. Identity recipes will be canonicalized with stable JSON hashing (sorted keys, compact separators, UTF-8) and explicit recipe constants for:
   - `decision_id`,
   - DecisionResponse envelope `event_id`,
   - ActionIntent envelope `event_id`,
   - ActionIntent `idempotency_key`.
4. Taxonomy compatibility guard:
   - allowed `event_type` set is explicit for Phase 1 (`decision_response`, `action_intent`),
   - `schema_version` parser enforces `v<major>[.<minor>]` form,
   - major version mismatch fails closed by raising typed contract/taxonomy error.
5. Add DF Phase 1 tests under `tests/services/decision_fabric/` for schema validity checks, deterministic identity behavior, and taxonomy compatibility enforcement.

### Files planned
- New:
  - `src/fraud_detection/decision_fabric/__init__.py`
  - `src/fraud_detection/decision_fabric/contracts.py`
  - `src/fraud_detection/decision_fabric/ids.py`
  - `src/fraud_detection/decision_fabric/taxonomy.py`
  - `tests/services/decision_fabric/test_phase1_contracts.py`
  - `tests/services/decision_fabric/test_phase1_ids.py`
  - `tests/services/decision_fabric/test_phase1_taxonomy.py`
- Update:
  - `docs/model_spec/platform/contracts/real_time_decision_loop/README.md`
  - `docs/model_spec/platform/contracts/README.md`
  - `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` (Phase 1 status)

### Invariants to enforce
- DF contract helpers reject missing required provenance keys.
- Identity digests are deterministic across process runs and key orderings.
- Taxonomy acceptance is explicit and fail-closed for unknown event type or incompatible schema major.
- No silent alias drift in contract docs/index for decision_response/action_intent.

### Validation plan
- Run `python -m pytest tests/services/decision_fabric -q`.
- Re-run with package-level import smoke:
  - `python -c "import fraud_detection.decision_fabric as df; print(sorted(df.__all__))"`.
- Append implementation closure details and evidence after tests are green.

---

## Entry: 2026-02-07 10:30:56 — Phase 1 implementation closure (DF contracts + deterministic identity)

### What was implemented
1. Added DF Phase 1 package scaffold:
   - `src/fraud_detection/decision_fabric/__init__.py`
   - `src/fraud_detection/decision_fabric/contracts.py`
   - `src/fraud_detection/decision_fabric/ids.py`
   - `src/fraud_detection/decision_fabric/taxonomy.py`
2. Implemented contract helpers:
   - `DecisionResponse.from_payload(...)` and `ActionIntent.from_payload(...)` enforce required provenance and identity fields,
   - explicit validation for pins, policy revision, degrade posture mask shape, bundle identity, and lineage linkage (`validate_action_intent_lineage`).
3. Implemented deterministic identity recipes (v1):
   - decision ID: deterministic 32-hex hash over source event + scope + bundle + EB basis,
   - DecisionResponse event ID and ActionIntent event ID: deterministic recipe hashes over source event + pins scope + domain/scope,
   - ActionIntent idempotency key: deterministic recipe hash over source event + pins scope + action domain.
4. Implemented fail-closed taxonomy/compatibility guard:
   - allowlisted event types (`decision_response`, `action_intent`),
   - parsed schema versions as `v<major>[.<minor>]`,
   - major mismatch raises explicit compatibility error (fail-closed posture).
5. Updated contract index/readme references to make DecisionResponse payload authority explicit:
   - `docs/model_spec/platform/contracts/real_time_decision_loop/README.md`
   - `docs/model_spec/platform/contracts/README.md`

### Validation results
- `python -m pytest tests/services/decision_fabric -q` -> `14 passed`.
- `PYTHONPATH=.;src python -c "import fraud_detection.decision_fabric as df; print(sorted(df.__all__))"` succeeded.

### DoD closure mapping (Phase 1)
- DecisionResponse + ActionIntent required provenance/identity fields: complete.
- Deterministic identity rules pinned in code (decision_id + output event IDs + idempotency key): complete.
- Event taxonomy + compatibility posture (major mismatch fail-closed): complete.
- Contract docs/index reflect authoritative schema paths without introducing duplicate schema files: complete.

### Follow-on boundary
- Phase 2 will implement runtime inlet gating against admitted traffic topics and trigger allowlists.

---

## Entry: 2026-02-07 10:32:23 — Phase 1 test hardening follow-up

### Problem / observation
After Phase 1 closure, the identity determinism test for reordered offsets used a dict-expansion expression that could mask intended field ordering variation.

### Corrective change
- Updated `tests/services/decision_fabric/test_phase1_ids.py` to build a dedicated `reordered_offsets_basis` object explicitly, ensuring the test truly exercises order-insensitive normalization inside DF identity hashing.

### Re-validation
- `python -m pytest tests/services/decision_fabric -q` -> `14 passed`.

### Outcome
- No behavioral code changes were needed.
- Phase 1 closure remains valid with stronger determinism evidence.

---

## Entry: 2026-02-07 10:45:23 — Phase 2 implementation plan (inlet boundary + trigger gating)

### Problem / goal
Implement DF Phase 2 so the Decision Fabric inlet only forms decision candidates from admitted traffic stimuli and rejects non-trigger/control/looping families deterministically.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` (Phase 2)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (RTDL topic discovery, traffic-trigger posture, fail-closed compatibility)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md` (context streams are state-builders, traffic is trigger)
- Existing projector inlet patterns:
  - `src/fraud_detection/online_feature_plane/projector.py`
  - `src/fraud_detection/identity_entity_graph/projector.py`

### Decision trail (before coding)
1. Introduce an explicit, versioned DF trigger policy file under `config/platform/df/` instead of hard-coding trigger sets in Python. This satisfies "allowlist explicit and versioned."
2. Build two new DF modules:
   - `config.py` for loading/validating trigger policy and computing a policy content digest.
   - `inlet.py` for envelope validation + traffic-topic gating + event trigger allowlist + loop prevention + pins validation + evidence-basis extraction.
3. Preserve fail-closed posture at inlet:
   - invalid/missing envelope or missing pins -> reject with explicit reason code,
   - unknown event type/schema mismatch -> reject with explicit reason code,
   - blocked loop families (DF/AL outputs) -> reject even if they appear on traffic topics.
4. Capture source evidence basis for accepted candidates as a structured `eb_ref` (`topic`, `partition`, `offset`, `offset_kind`, `published_at_utc`) and `source_event_id`.
5. Keep this phase runtime-light:
   - no long-running DF service loop yet,
   - focus on deterministic, unit-tested inlet semantics that later phases will use.

### Files planned
- New:
  - `config/platform/df/trigger_policy_v0.yaml`
  - `config/platform/df/README.md`
  - `src/fraud_detection/decision_fabric/config.py`
  - `src/fraud_detection/decision_fabric/inlet.py`
  - `tests/services/decision_fabric/test_phase2_config.py`
  - `tests/services/decision_fabric/test_phase2_inlet.py`
- Update:
  - `src/fraud_detection/decision_fabric/__init__.py`
  - `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` (status after closure)

### Invariants to enforce
- Only configured admitted traffic topics can produce trigger candidates.
- Trigger event types are explicit and versioned in policy.
- Required pins are validated at inlet; `seed` requirement is policy-controlled (default required in v0).
- DF/AL output families are never trigger-eligible (loop prevention).
- Accepted candidate always carries `source_event_id` and `source_eb_ref`.

### Validation plan
- Run `python -m pytest tests/services/decision_fabric -q`.
- Ensure tests explicitly cover:
  - non-traffic topic rejection,
  - context/control rejection,
  - loop family rejection,
  - pin-required rejection,
  - source evidence basis capture on accepted candidate.

---

## Entry: 2026-02-07 10:48:27 — Phase 2 implementation closure (inlet boundary + trigger gating)

### What was implemented
1. Added versioned DF trigger policy assets:
   - `config/platform/df/trigger_policy_v0.yaml`
   - `config/platform/df/README.md`
2. Added DF trigger policy loader:
   - `src/fraud_detection/decision_fabric/config.py`
   - validates policy shape and dedupes trigger rules,
   - computes deterministic `content_digest`,
   - exposes `allowed_schema_versions(...)`, `is_blocked_event_type(...)`, and required-pin checks.
3. Added DF inlet gate:
   - `src/fraud_detection/decision_fabric/inlet.py`
   - validates canonical envelope,
   - enforces traffic-topic-only trigger eligibility,
   - enforces versioned trigger allowlist (`event_type` + `schema_version`),
   - enforces loop prevention for blocked DF/AL/IG families,
   - enforces required pins at ingress,
   - emits accepted candidate with evidence basis:
     - `source_event_id`
     - `source_eb_ref = {topic, partition, offset, offset_kind, published_at_utc}`.
4. Updated package exports:
   - `src/fraud_detection/decision_fabric/__init__.py`.

### Validation results
- Added tests:
  - `tests/services/decision_fabric/test_phase2_config.py`
  - `tests/services/decision_fabric/test_phase2_inlet.py`
- Ran:
  - `python -m pytest tests/services/decision_fabric -q` -> `24 passed`.
  - `PYTHONPATH=.;src python -c "import fraud_detection.decision_fabric as df; print('ok', 'DecisionFabricInlet' in df.__all__, 'load_trigger_policy' in df.__all__)"` -> `ok True True`.

### DoD closure mapping (Phase 2)
- DF consumes admitted traffic topics only; context/control topics never trigger: complete (topic gate in inlet policy).
- Decision trigger allowlist explicit + versioned: complete (`trigger_policy_v0.yaml` with `event_type` + `schema_versions`).
- Required pins validated at ingress: complete (policy-driven required pin checks).
- Loop prevention (DF/AL output families never re-trigger): complete (blocked type/prefix checks).
- Source evidence basis captured per candidate decision: complete (`source_event_id` + structured `source_eb_ref`).

### Follow-on boundary
- Phase 3 will integrate DL posture input and enforce fail-safe posture behavior in DF runtime planning.

---

## Entry: 2026-02-07 11:05:22 — Phase 3 implementation plan (DL integration + fail-safe enforcement)

### Problem / goal
Implement DF Phase 3 so Decision Fabric consumes DL posture as a hard runtime constraint and stamps posture provenance deterministically into downstream decision artifacts.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` (Phase 3)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (explicit degrade, fail-closed, deterministic posture provenance)
- `src/fraud_detection/degrade_ladder/serve.py`
- `src/fraud_detection/degrade_ladder/contracts.py`
- `src/fraud_detection/degrade_ladder/health.py`

### Decision trail (before coding)
1. Add a dedicated DF posture module (`posture.py`) instead of spreading DL logic across inlet/runtime files.
2. Use DL guarded serve API as the default source of truth:
   - consume `DlGuardedPostureService.get_guarded_posture(...)`,
   - map serve output to a DF-native posture stamp object.
3. Enforce DL mask as hard constraints through a DF helper:
   - no IEG if `allow_ieg=false`,
   - no disallowed feature groups,
   - no model stage usage when respective mask flags are false,
   - no action posture escalation beyond DL posture.
4. Missing/invalid/stale posture behavior:
   - consume DL fail-safe outputs (`FAILSAFE_*`, `FAIL_CLOSED`) directly,
   - add defensive fallback that produces explicit fail-closed stamp if malformed posture arrives.
5. Add a transition-compatibility guard to stay aligned with DL anti-flap semantics:
   - immediate tighten accepted,
   - relax transitions can be hold-down controlled by a local interval gate (optional but deterministic),
   - non-monotonic relax posture sequence is blocked.
6. Provide deterministic posture stamping helpers (`as_dict`/canonical/digest) for Phase 6 artifact emission.

### Files planned
- New:
  - `src/fraud_detection/decision_fabric/posture.py`
  - `tests/services/decision_fabric/test_phase3_posture.py`
- Update:
  - `src/fraud_detection/decision_fabric/__init__.py`
  - `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` (status after closure)

### Invariants to enforce
- DF never bypasses DL mask constraints.
- DL missing/stale/untrusted outcomes force explicit fail-closed posture at DF boundary.
- Posture stamp serialization/digest is deterministic for identical posture inputs.
- Transition handling is compatible with DL anti-flap posture evolution.

### Validation plan
- Run `python -m pytest tests/services/decision_fabric -q`.
- Tests must explicitly cover:
  - hard mask enforcement failures,
  - fail-closed on malformed or stale posture,
  - deterministic posture stamp digest,
  - immediate tighten + controlled relax transition behavior.

---

## Entry: 2026-02-07 11:08:15 — Phase 3 implementation closure (DL integration + fail-safe enforcement)

### What was implemented
1. Added DF posture integration module:
   - `src/fraud_detection/decision_fabric/posture.py`
   - includes:
     - `DfPostureResolver` that consumes `DlGuardedPostureService.get_guarded_posture(...)`,
     - `posture_stamp_from_dl(...)` mapping DL serve outputs into DF posture stamps,
     - `enforce_posture_constraints(...)` for hard mask enforcement (no bypass),
     - `DfPostureTransitionGuard` for immediate tighten + controlled relax compatibility.
2. Added deterministic posture stamp representation:
   - `DfPostureStamp.as_dict()`, `canonical_json()`, `digest()`.
3. Added defensive fail-safe behavior:
   - malformed DL posture payload at DF boundary yields explicit `FAIL_CLOSED` posture stamp with `DL_POSTURE_INVALID:*` reason codes.
4. Updated DF package exports:
   - `src/fraud_detection/decision_fabric/__init__.py`.

### Validation results
- Added tests:
  - `tests/services/decision_fabric/test_phase3_posture.py`
- Re-ran full DF suite:
  - `python -m pytest tests/services/decision_fabric -q` -> `29 passed`.
- Import/export smoke:
  - `PYTHONPATH=.;src python -c "import fraud_detection.decision_fabric as df; print('ok', 'DfPostureResolver' in df.__all__, 'enforce_posture_constraints' in df.__all__)"` -> `ok True True`.

### DoD closure mapping (Phase 3)
- DF consumes `DegradeDecision` posture surface via DL guarded serve: complete.
- DL mask enforced as hard constraints (no bypass): complete (`enforce_posture_constraints`).
- Missing/invalid/stale posture forces explicit fail-closed posture mode: complete (DL fail-safe mapping + defensive invalid-result fallback).
- Posture stamps written deterministically for artifact embedding: complete (`DfPostureStamp` canonical/digest).
- Transition behavior compatible with DL anti-flap semantics: complete (`DfPostureTransitionGuard` immediate tighten + hold-down controlled relax).

### Follow-on boundary
- Phase 4 will add deterministic registry bundle resolution + compatibility fail-closed checks.

---

## Entry: 2026-02-07 11:12:21 — Phase 4 implementation plan (registry bundle resolution + compatibility)

### Problem / goal
Implement DF Phase 4 so bundle/policy selection is deterministic per scope and compatibility-aware under current degrade posture and feature contract basis.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` (Phase 4)
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md` (deterministic active-bundle resolution, no implicit latest, incompatibility -> safe fallback/fail-closed)
- `docs/model_spec/platform/component-specific/model_policy_registry.design-authority.md` (one active per scope, explicit scope key, compatibility gate)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (fail-closed compatibility posture)

### Decision trail (before coding)
1. Add a DF-local registry resolution policy file under `config/platform/df/`:
   - explicit scope axes `(environment, mode, bundle_slot, tenant_id?)`,
   - explicit fallback posture controls (`allow_last_known_good`, explicit fallback map),
   - policy revision fields for provenance stamping.
2. Add a dedicated DF registry module (`registry.py`) with:
   - typed `RegistryScopeKey`,
   - typed bundle compatibility contract (required feature groups + required capabilities),
   - typed resolver output (`RESOLVED`, `FALLBACK`, `FAIL_CLOSED`) including deterministic resolution digest.
3. Enforce deterministic scope resolution:
   - exact scope match only, no implicit “latest.”
   - snapshot loading rejects duplicate active entries for same scope.
4. Compatibility checks are fail-closed by default:
   - mismatch between bundle required capabilities and current DL mask -> incompatible,
   - mismatch between bundle required feature group versions and provided feature basis -> incompatible.
5. Fallback behavior explicit and bounded:
   - explicit per-scope fallback bundle allowed when configured,
   - optional last-known-good allowed only when policy explicitly enables it and data exists,
   - otherwise return `FAIL_CLOSED` outcome with reason codes.
6. Ensure replay stability:
   - identical input basis (`scope_key`, posture stamp, feature basis, policy rev/snapshot) produces identical resolver output + digest.

### Files planned
- New:
  - `config/platform/df/registry_resolution_policy_v0.yaml`
  - `src/fraud_detection/decision_fabric/registry.py`
  - `tests/services/decision_fabric/test_phase4_registry.py`
- Update:
  - `config/platform/df/README.md`
  - `src/fraud_detection/decision_fabric/__init__.py`
  - `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` (status after closure)

### Invariants to enforce
- No implicit latest selection; exact scope resolution only.
- Compatibility mismatch never silently resolves as normal active bundle.
- Fallback path is policy-controlled and provenance-stamped.
- Resolver output and digest are deterministic for identical basis.

### Validation plan
- Run `python -m pytest tests/services/decision_fabric -q`.
- Add explicit tests for:
  - deterministic scope resolution,
  - capability mismatch fail-closed,
  - feature-version mismatch fail-closed,
  - explicit fallback selection,
  - replay-stable resolution digest.

---

## Entry: 2026-02-07 11:16:34 — Phase 4 implementation closure (registry bundle resolution + compatibility)

### What was implemented
1. Added DF registry resolution policy artifact:
   - `config/platform/df/registry_resolution_policy_v0.yaml`
   - explicit scope axes `(environment, mode, bundle_slot, tenant_id)`,
   - explicit fallback controls (`allow_last_known_good`, `explicit_by_scope`).
2. Added DF registry resolution module:
   - `src/fraud_detection/decision_fabric/registry.py`
   - includes:
     - typed `RegistryScopeKey` and exact-scope canonical keying,
     - `RegistryResolutionPolicy` loader with deterministic content digest,
     - `RegistrySnapshot` loader with duplicate-scope rejection,
     - compatibility gate (`feature contract` + `capability contract`) with fail-closed reasoning,
     - bounded fallback selection (`explicit_by_scope`, optional last-known-good),
     - deterministic `RegistryResolutionResult` with stable `basis_digest` and result digest.
3. Updated DF package exports:
   - `src/fraud_detection/decision_fabric/__init__.py`.
4. Updated DF config readme:
   - `config/platform/df/README.md` now includes registry policy intent.

### Validation results
- Added tests:
  - `tests/services/decision_fabric/test_phase4_registry.py`
- Re-ran DF suite:
  - `python -m pytest tests/services/decision_fabric -q` -> `36 passed`.
- Import/export smoke:
  - `PYTHONPATH=.;src python -c "import fraud_detection.decision_fabric as df; print('ok', 'RegistryResolver' in df.__all__, 'RegistryResolutionPolicy' in df.__all__)"` -> `ok True True`.

### DoD closure mapping (Phase 4)
- Deterministic resolver for scope `(environment, mode, bundle_slot, tenant?)` with no implicit latest: complete.
- Compatibility checks fail-closed on capability/feature mismatches: complete.
- Fallback behavior explicit and bounded (policy-gated): complete.
- Resolver outputs replay-stable for identical basis + policy revision: complete (`basis_digest` + deterministic result digest tests).

### Follow-on boundary
- Phase 5 will integrate OFP/IEG acquisition under decision-time budgets and DL mask constraints.

---

## Entry: 2026-02-07 11:25:20 — Phase 5 implementation plan (context/features acquisition + decision-time budgets)

### Problem / goal
Implement DF Phase 5 so Decision Fabric acquires OFP/IEG context within explicit RTDL budgets, enforces DL mask constraints, and records context evidence refs deterministically with no hidden time.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` (Phase 5 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (decision_deadline_ms, join_wait_budget_ms, required context)
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md` (DF-E4: OFP as_of_time_utc = event_time; IEG optional; fail-closed)
- `docs/model_spec/platform/contracts/real_time_decision_loop/ofp_get_features_request.schema.yaml`
- `docs/model_spec/platform/contracts/real_time_decision_loop/ofp_get_features_response.schema.yaml`
- `src/fraud_detection/online_feature_plane/serve.py` (OfpGetFeaturesService)
- `src/fraud_detection/identity_entity_graph/query.py` (IdentityGraphQuery)
- DF Phase 3 posture enforcement (`src/fraud_detection/decision_fabric/posture.py`)

### Decision trail (before coding)
1. Create a DF-local context policy file under `config/platform/df/` to pin:
   - `decision_deadline_ms` and `join_wait_budget_ms` (must be <= decision_deadline),
   - required vs optional context roles (`arrival_events`, `flow_anchor` required; `arrival_entities` optional),
   - OFP request defaults (feature_groups, graph_resolution_mode),
   - IEG requirement flag (default false, but enforceable).
2. Add a DF context module (`context.py`) to own:
   - policy loading + deterministic content digest,
   - decision budget math (explicit `started_at_utc` + `now_utc`, no hidden time),
   - join readiness evaluation + missing-context reason codes,
   - OFP request assembly with `as_of_time_utc = source_event.ts_utc`,
   - DL mask enforcement via `enforce_posture_constraints(...)` before calling OFP/IEG,
   - acquisition result structure with evidence refs and deterministic digest.
3. Keep external calls injectable:
   - accept an `OfpGetFeaturesService` instance and optional `IdentityGraphQuery` or resolver callback,
   - allow tests to stub OFP/IEG responses without running the services.
4. Missing required context must return explicit reason codes and not fabricate context; optional context missing is recorded but does not block.
5. Context evidence refs must include:
   - traffic `source_eb_ref` from inlet,
   - context offsets used (join frame refs if provided),
   - OFP `eb_offset_basis` + `snapshot_hash`,
   - IEG `graph_version` if used.

### Files planned
- New:
  - `config/platform/df/context_policy_v0.yaml`
  - `src/fraud_detection/decision_fabric/context.py`
  - `tests/services/decision_fabric/test_phase5_context.py`
- Update:
  - `config/platform/df/README.md`
  - `src/fraud_detection/decision_fabric/__init__.py`
  - `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` (Phase 5 status)

### Invariants to enforce
- OFP `as_of_time_utc` equals the source event `ts_utc`; no hidden wall-clock time in decisions.
- DL mask enforcement is applied before OFP/IEG calls; forbidden capabilities are never attempted.
- `join_wait_budget_ms` is enforced against explicit `now_utc` and is always <= `decision_deadline_ms`.
- Missing required context yields explicit degrade reasons (`context_missing:*`) and `status=CONSTRAINED_SAFE`.
- Context evidence refs are recorded deterministically when context is used.

### Validation plan
- Add tests covering:
  - OFP request uses `source_ts_utc` for `as_of_time_utc`.
  - DL mask blocks IEG/OFP calls when not allowed.
  - Deadline/join budget enforcement on explicit `now_utc`.
  - Missing required context surfaces explicit reason codes.
  - Evidence refs include traffic `source_eb_ref` and OFP basis when used.
- Run `python -m pytest tests/services/decision_fabric -q`.

---

## Entry: 2026-02-07 11:33:41 — Phase 5 implementation closure (context/features acquisition + decision-time budgets)

### What was implemented
1. Added DF context policy artifact:
   - `config/platform/df/context_policy_v0.yaml` pins decision deadlines, join-wait budgets, required/optional context roles, OFP defaults, and IEG requirement flag.
2. Added DF context acquisition module:
   - `src/fraud_detection/decision_fabric/context.py`
   - implements policy loading + deterministic content digest,
   - decision budget snapshots (`DecisionBudget` + `DecisionBudgetSnapshot`) with explicit `now_utc`,
   - join readiness checks with `CONTEXT_WAITING` vs `CONTEXT_MISSING` outcomes,
   - DL mask enforcement before OFP/IEG calls,
   - OFP request assembly with `as_of_time_utc = source_ts_utc`,
   - context evidence refs capture (`source_eb_ref`, context refs, OFP basis/snapshot, graph_version).
3. Updated DF package exports:
   - `src/fraud_detection/decision_fabric/__init__.py` now includes context policy/acquirer types and status constants.
4. Updated DF config README:
   - `config/platform/df/README.md` lists the context policy file.

### Validation results
- Added tests:
  - `tests/services/decision_fabric/test_phase5_context.py`
- Re-ran DF suite:
  - `python -m pytest tests/services/decision_fabric -q` -> `41 passed`.

### DoD closure mapping (Phase 5)
- OFP reads use `as_of_time_utc = source event ts_utc`: complete (request assembly + test).
- IEG/OFP calls obey DL mask and join readiness policy: complete (mask enforcement + waiting/missing outcomes).
- `decision_deadline_ms` and `join_wait_budget_ms` enforced from policy: complete (budget snapshot + tests).
- Missing required context yields explicit degrade reasons: complete (`CONTEXT_WAITING`/`CONTEXT_MISSING` with reason codes).
- Context evidence refs captured when used: complete (ContextEvidence + tests).

### Follow-on boundary
- Phase 6 will implement deterministic decision synthesis + ActionIntent emission at the IG publish boundary.

---

## Entry: 2026-02-07 11:37:15 — Phase 6 implementation plan (decision synthesis + intent emission)

### Problem / goal
Implement DF Phase 6 so decision/intents are synthesized deterministically from frozen basis and published through IG with explicit ADMIT/DUPLICATE/QUARANTINE handling and correction supersede semantics.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` (Phase 6 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (explicit degrade, append-only corrections)
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md` (DF->IG->EB trust boundary, deterministic outputs, safe fallback)
- `docs/model_spec/platform/contracts/real_time_decision_loop/decision_payload.schema.yaml`
- `docs/model_spec/platform/contracts/real_time_decision_loop/action_intent.schema.yaml`
- `docs/model_spec/data-engine/interface_pack/contracts/canonical_event_envelope.schema.yaml`
- `src/fraud_detection/ingestion_gate/service.py` + `src/fraud_detection/ingestion_gate/admission.py` (IG response decisions: ADMIT, DUPLICATE, QUARANTINE)

### Decision trail (before coding)
1. Split Phase 6 into two modules:
   - `synthesis.py`: deterministic decision + action intent payload synthesis and correction helpers.
   - `publish.py`: canonical-envelope emission through IG with explicit publish outcome model.
2. Deterministic synthesis basis will be explicit:
   - candidate source refs/pins,
   - posture stamp + mask,
   - registry resolution result,
   - context result (snapshot hashes/basis/graph_version).
   No wall-clock dependencies beyond explicit `decided_at_utc`/`requested_at_utc` args.
3. Action posture constraints:
   - if posture mask is `STEP_UP_ONLY`, synthesized action intent posture is clamped and reason-coded.
4. IG publish boundary:
   - emit DecisionResponse envelope first, then ActionIntent envelopes.
   - map IG decisions (`ADMIT`, `DUPLICATE`, `QUARANTINE`) into typed publish outcomes; unknown responses fail closed.
5. Correction semantics:
   - add helper to produce correction decision with `supersedes_decision_id` in decision payload and new deterministic decision/event IDs.
   - keep append-only shape by never mutating original decision payload.

### Files planned
- New:
  - `src/fraud_detection/decision_fabric/synthesis.py`
  - `src/fraud_detection/decision_fabric/publish.py`
  - `tests/services/decision_fabric/test_phase6_synthesis.py`
  - `tests/services/decision_fabric/test_phase6_publish.py`
- Update:
  - `src/fraud_detection/decision_fabric/__init__.py`
  - `docs/model_spec/platform/implementation_maps/decision_fabric.build_plan.md` (Phase 6 status)

### Invariants to enforce
- Same basis -> byte-stable decision/action payloads (excluding explicit call timestamps supplied by caller).
- Action intents never violate DL action posture.
- All DF outputs are canonical envelopes and go through IG push endpoint semantics.
- Publish handling is explicit and stable per IG decision code.
- Correction payloads are append-only and reference superseded decision IDs.

### Validation plan
- Add tests for:
  - deterministic synthesis output + identity stability,
  - action posture clamp behavior,
  - canonical envelope formation for decision_response/action_intent,
  - publish decision mapping (`ADMIT`/`DUPLICATE`/`QUARANTINE`) and unknown-decision fail-closed,
  - correction helper produces new decision with explicit supersede linkage.
- Run `python -m pytest tests/services/decision_fabric -q`.

---

## Entry: 2026-02-07 11:45:52 — Phase 6 implementation closure (decision synthesis + intent emission)

### What was implemented
1. Added deterministic synthesis module:
   - `src/fraud_detection/decision_fabric/synthesis.py`
   - builds DecisionResponse payload from fixed basis (candidate + posture + registry + context),
   - emits deterministic ActionIntent payload(s) with stable idempotency keys,
   - emits canonical envelopes for `decision_response` and `action_intent`,
   - enforces DL action posture clamp (`STEP_UP_ONLY`) in synthesis,
   - adds correction helper with append-only supersede linkage (`supersedes_decision_id`).
2. Added IG publish boundary module:
   - `src/fraud_detection/decision_fabric/publish.py`
   - validates canonical envelope before send,
   - publishes only through IG `/v1/ingest/push`,
   - maps publish outcomes explicitly (`ADMIT`, `DUPLICATE`, `QUARANTINE`),
   - fail-closes on unknown IG decision or invalid responses,
   - supports deterministic batch behavior (halt on quarantined decision/action).
3. Updated DF package exports:
   - `src/fraud_detection/decision_fabric/__init__.py` now exports synthesis/publish types/constants.

### Validation results
- Added tests:
  - `tests/services/decision_fabric/test_phase6_synthesis.py`
  - `tests/services/decision_fabric/test_phase6_publish.py`
- Re-ran DF suite:
  - `python -m pytest tests/services/decision_fabric -q` -> `52 passed`.
- Import/export smoke:
  - `$env:PYTHONPATH='.;src'; python -c "import fraud_detection.decision_fabric as df; print('ok', 'DecisionSynthesizer' in df.__all__, 'DecisionFabricIgPublisher' in df.__all__)"` -> `ok True True`.

### DoD closure mapping (Phase 6)
- Decision synthesis deterministic for fixed basis: complete (synthesis module + determinism tests).
- ActionIntent emission respects DL action posture: complete (clamp path + tests).
- DecisionResponse/ActionIntent emitted as canonical envelope traffic via IG boundary helper: complete.
- Publish boundary handles ADMIT/DUPLICATE/QUARANTINE explicitly with stable behavior: complete.
- Corrections use append-only supersede semantics (no overwrite): complete (correction helper + tests).

### Follow-on boundary
- Phase 7 will add idempotency/checkpoint/replay safety and mismatch anomaly surfacing.

---
