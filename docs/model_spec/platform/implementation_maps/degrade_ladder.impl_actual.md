# Degrade Ladder Implementation Map
_As of 2026-02-05_

---

## Entry: 2026-02-05 15:14:10 — Phase 4 planning kickoff (DL scope + output contract)

### Problem / goal
Lock DL v0 outer-contract semantics so DF can depend on explicit, deterministic degrade posture.

### Authorities / inputs
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/degrade_ladder.design-authority.md`
- Platform rails (explicit degrade posture; fail-closed).
- RTDL contracts under `docs/model_spec/platform/contracts/real_time_decision_loop/`.

### Decisions captured (v0 stance)
- DL is the **single authority** for degrade mode + capabilities mask.
- v0 modes (ordered): `NORMAL → DEGRADED_1 → DEGRADED_2 → FAIL_CLOSED`.
- Capabilities mask fields are pinned (`allow_ieg`, `allowed_feature_groups`, `allow_model_primary`, `allow_model_stage2`, `allow_fallback_heuristics`, `action_posture`).
- Determinism + hysteresis: downshift immediate; upshift after quiet period; missing signals fail closed.
- DL output is recordable and must include `policy_rev` + `posture_seq` + `decided_at_utc`.

### Planned implementation scope (Phase 4.4)
- Implement DL evaluator as a single deployable unit (v0) with policy-driven thresholds.
- Maintain posture store (derived, rebuildable) and expose current posture to DF.
- Emit posture-change facts to obs/gov (optional control bus).

---

## Entry: 2026-02-07 02:53:29 — Plan: expand DL component build plan phase-by-phase from platform 4.4

### Problem / goal
Current `degrade_ladder.build_plan.md` is still high-level (3 broad phases). With platform `Phase 4.4` now expanded, DL requires a component-granular phased plan that can be executed and audited without interpretation drift.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (expanded Phase 4.4)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/degrade_ladder.design-authority.md`
- Existing DL build/impl docs.

### Decision trail (live)
1. Keep DL scoped to posture authority and serving semantics; avoid bleeding into DF decision logic details.
2. Expand DL plan into clear phases:
   - contract/policy profile,
   - signal snapshot + scope resolution,
   - deterministic evaluator/hysteresis,
   - posture store + serve contract,
   - optional control emission + health gates,
   - validation/parity and handoff.
3. Encode fail-closed, deterministic, and anti-flap behavior as explicit DoD gates.
4. Keep visibility/control-bus emission non-critical for correctness (observability-only by default).

### Planned edits
- Replace current high-level DL plan with phase-by-phase v0 DoD map aligned to platform 4.4.B/J/K/L.
- Explicitly separate "component-closable now" from integration-dependent checks with DF/Obs-Gov.

---

## Entry: 2026-02-07 02:55:08 — Applied DL phase-by-phase build plan expansion

### Change applied
Updated `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` from a 3-phase high-level outline to an executable 8-phase plan with explicit DoD checklists.

### New DL phase map (v0)
1. Contract + policy profile authority
2. Signal intake + snapshot normalization
3. Scope resolution + deterministic evaluator
4. Posture store + serve surface
5. Health gate + self-trust clamp
6. Posture-change emission (observability lane)
7. Security/governance/ops telemetry
8. Validation/parity proof/closure boundary

### Alignment checks
- Mapped to platform Phase 4.4 posture and validation gates while keeping DL scoped to posture authority.
- Preserved fail-closed semantics and anti-flap/hysteresis requirements from RTDL pre-design decisions.
- Kept control-bus posture emission explicitly non-critical for correctness (visibility-only lane).

---

## Entry: 2026-02-07 02:57:10 — Phase 1 implementation plan (DL contracts + policy profile authority)

### Problem / goal
User requested implementation of DL Phase 1. Current repo has RTDL payload contracts but no DL runtime package and no pinned `config/platform/dl` policy profile artifact. Phase 1 requires:
1. degrade posture contract completeness and validity,
2. policy profile format pinned + versioned,
3. implementation-facing loaders/validators to prevent drift.

### Inputs / authorities
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (Phase 1 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/contracts/real_time_decision_loop/degrade_posture.schema.yaml`
- platform profile structure under `config/platform/profiles/*.yaml`

### Decision trail (live)
1. Implement Phase 1 as **contract + config scaffolding**, not evaluator/runtime yet (that belongs to later DL phases).
2. Add first-class DL package (`src/fraud_detection/degrade_ladder`) with:
   - contract validator/model helpers for `DegradeDecision`,
   - policy profile loader/validator for versioned `policy_profiles_v0.yaml`.
3. Pin policy profiles in `config/platform/dl/policy_profiles_v0.yaml` and reference them from platform profile files to keep ladder wiring explicit.
4. Add focused tests under `tests/services/degrade_ladder` to prove:
   - contract shape validity and required fields,
   - policy profile loading and mode/mask completeness.
5. Fix existing schema formatting defect in `degrade_posture.schema.yaml` discovered during Phase 1 read-through (mis-indented `evidence_refs`).

### Planned file edits
- `src/fraud_detection/degrade_ladder/__init__.py` (new)
- `src/fraud_detection/degrade_ladder/contracts.py` (new)
- `src/fraud_detection/degrade_ladder/config.py` (new)
- `config/platform/dl/policy_profiles_v0.yaml` (new)
- `config/platform/dl/README.md` (new)
- `config/platform/profiles/local.yaml` (dl policy refs)
- `config/platform/profiles/local_parity.yaml` (dl policy refs)
- `config/platform/profiles/dev.yaml` (dl policy refs)
- `config/platform/profiles/prod.yaml` (dl policy refs)
- `config/platform/profiles/README.md` (shape update)
- `docs/model_spec/platform/contracts/real_time_decision_loop/degrade_posture.schema.yaml` (schema fix)
- `tests/services/degrade_ladder/test_phase1_contracts.py` (new)
- `tests/services/degrade_ladder/test_phase1_policy_profiles.py` (new)

### Validation plan
- `python -m pytest tests/services/degrade_ladder -q`
- optional parse check for `degrade_posture.schema.yaml` via tests to ensure valid YAML + required keys.

---

## Entry: 2026-02-07 03:06:23 — DL Phase 1 implemented (contracts + policy profile authority)

### What was implemented
1. Added DL Phase 1 runtime scaffolding:
   - `src/fraud_detection/degrade_ladder/contracts.py`
   - `src/fraud_detection/degrade_ladder/config.py`
   - `src/fraud_detection/degrade_ladder/__init__.py`
2. Added versioned DL policy profile artifact:
   - `config/platform/dl/policy_profiles_v0.yaml`
   - `config/platform/dl/README.md`
3. Wired platform profiles to explicit DL policy profile refs:
   - `config/platform/profiles/local.yaml`
   - `config/platform/profiles/local_parity.yaml`
   - `config/platform/profiles/dev.yaml`
   - `config/platform/profiles/prod.yaml`
   - `config/platform/profiles/README.md`
4. Fixed contract schema defect in:
   - `docs/model_spec/platform/contracts/real_time_decision_loop/degrade_posture.schema.yaml`
   (`evidence_refs` indentation under properties was invalid and is now corrected).
5. Added Phase 1 tests:
   - `tests/services/degrade_ladder/test_phase1_contracts.py`
   - `tests/services/degrade_ladder/test_phase1_policy_profiles.py`

### Validation results
- `python -m pytest tests/services/degrade_ladder -q` -> `7 passed`
- Parsed all platform profile YAML files post-edit to verify syntax integrity (`4` files parsed).

### Phase closure assessment
- DL Phase 1 DoD is satisfied at component scope:
  - contract fields pinned and validated,
  - mode/mask vocabulary enforced,
  - policy profile format pinned/versioned with environment profile references,
  - tests proving contract and profile loading behavior.

---

## Entry: 2026-02-07 03:08:40 — Corrective hardening: contract helper payload coercion

### Issue
Initial `DegradeDecision.from_payload` used eager `dict(...)` coercion for nested payloads, which could raise non-contract exceptions on malformed non-mapping inputs.

### Correction
- Updated `src/fraud_detection/degrade_ladder/contracts.py` to pass nested payloads directly into typed validators so malformed shapes consistently raise `DegradeContractError`.

### Validation
- `python -m pytest tests/services/degrade_ladder -q` -> `7 passed`

---

## Entry: 2026-02-07 03:17:17 — Phase 2 implementation plan (signal intake + snapshot normalization)

### Problem / goal
User requested proceeding to DL Phase 2. Phase 1 established contracts/profile authority; Phase 2 now needs concrete signal ingestion and deterministic snapshot normalization behavior to feed the evaluator in later phases.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (Phase 2 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (health gates, freshness, fail-closed stance)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md` (explicit degrade semantics)
- Existing DL Phase 1 modules and `config/platform/dl/policy_profiles_v0.yaml`.

### Decision trail (live)
1. Implement a dedicated `signals.py` module in DL for:
   - strict signal sample parsing,
   - deterministic per-scope snapshot build,
   - explicit per-signal state classification (`OK|STALE|MISSING|ERROR`),
   - deterministic snapshot hash for replay/equality checks.
2. Extend DL policy profile parsing with explicit signal policy:
   - required signal names,
   - optional signal names,
   - freshness threshold (`required_max_age_seconds`).
3. Keep snapshot build fail-safe and explicit:
   - required stale/missing/error signals set `has_required_gaps=True`,
   - no hidden default decision time (must be provided).
4. Add focused Phase 2 tests to prove deterministic behavior and stale/missing semantics.

### Planned edits
- `src/fraud_detection/degrade_ladder/signals.py` (new)
- `src/fraud_detection/degrade_ladder/config.py` (signal policy parsing)
- `src/fraud_detection/degrade_ladder/__init__.py` (exports)
- `config/platform/dl/policy_profiles_v0.yaml` (add signal policy sections)
- `tests/services/degrade_ladder/test_phase1_policy_profiles.py` (assert signal policy parse)
- `tests/services/degrade_ladder/test_phase2_signals.py` (new)
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (mark Phase 2 status with evidence when green)

### Validation plan
- `python -m pytest tests/services/degrade_ladder -q`
- smoke loader check for policy bundle resolution using new signal policy fields.

---

## Entry: 2026-02-07 03:19:52 — DL Phase 2 implemented (signal intake + snapshot normalization)

### What was implemented
1. Added signal normalization module:
   - `src/fraud_detection/degrade_ladder/signals.py`
   - strict sample parsing (`DlSignalSample`),
   - deterministic snapshot builder (`DlSignalSnapshot`),
   - explicit per-signal states (`OK|STALE|MISSING|ERROR`),
   - deterministic `snapshot_digest` over canonical payload.
2. Extended DL policy parsing for signal policy authority:
   - `src/fraud_detection/degrade_ladder/config.py`
   - new `DlSignalPolicy` with `required_signals`, `optional_signals`, `required_max_age_seconds`.
3. Extended DL policy profiles:
   - `config/platform/dl/policy_profiles_v0.yaml`
   - added explicit `signals` section for `local/local_parity/dev/prod`.
4. Updated exports and documentation:
   - `src/fraud_detection/degrade_ladder/__init__.py`
   - `config/platform/dl/README.md`
5. Added/updated tests:
   - `tests/services/degrade_ladder/test_phase2_signals.py`
   - `tests/services/degrade_ladder/test_phase1_policy_profiles.py` (signal-policy assertions)

### Validation results
- `python -m pytest tests/services/degrade_ladder -q` -> `11 passed`
- Policy loader smoke check (`PYTHONPATH=.;src`) confirms all env profiles resolve with expected signal policy:
  - local/local_parity/dev/prod each with `required_max_age_seconds=120`.

### Phase closure assessment
- DL Phase 2 DoD is satisfied at component scope:
  - explicit signal freshness/validity semantics implemented,
  - snapshot normalization deterministic and scoped,
  - required stale/missing representation explicit (`has_required_gaps`),
  - behavior validated via dedicated tests.

---

## Entry: 2026-02-07 03:23:55 — Phase 3 implementation plan (scope resolution + deterministic evaluator)

### Problem / goal
Proceed to DL Phase 3 by implementing:
1. explicit deterministic scope resolution,
2. deterministic posture evaluator from (policy + normalized snapshot),
3. hysteresis semantics (immediate downshift, controlled one-rung upshift),
4. explicit fail-closed on evaluator/policy failures.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (Phase 3 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/degrade_ladder.design-authority.md`
- DL Phase 1/2 modules (`contracts.py`, `config.py`, `signals.py`)

### Decision trail (live)
1. Add dedicated evaluator module (`evaluator.py`) to isolate phase-3 logic from config/contracts.
2. Scope resolution function will be explicit and deterministic with pinned modes:
   - `GLOBAL`, `MANIFEST`, `RUN`.
3. Evaluator baseline posture target from snapshot:
   - required gaps -> `FAIL_CLOSED`,
   - optional error -> `DEGRADED_2`,
   - optional stale/missing -> `DEGRADED_1`,
   - otherwise `NORMAL`.
4. Hysteresis:
   - immediate tighten (move directly to more-degraded target),
   - relax only after quiet period and by one rung per evaluation.
5. Add `evaluate_posture_safe` wrapper that guarantees fail-closed output with explicit reason on unexpected evaluator/policy errors.

### Planned edits
- `src/fraud_detection/degrade_ladder/evaluator.py` (new)
- `src/fraud_detection/degrade_ladder/__init__.py` (exports)
- `tests/services/degrade_ladder/test_phase3_evaluator.py` (new)
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (Phase 3 status + evidence if green)

### Validation plan
- `python -m pytest tests/services/degrade_ladder -q`
- direct assertions for:
  - deterministic outputs,
  - scope resolution behavior,
  - hysteresis down/up transitions,
  - fail-closed fallback path.

---

## Entry: 2026-02-07 03:52:34 — DL Phase 3 implemented (scope resolution + deterministic evaluator)

### Implementation summary
Phase 3 is now implemented and validated at component scope.

### What was implemented
1. Added deterministic evaluator module:
   - `src/fraud_detection/degrade_ladder/evaluator.py`
   - explicit scope model + canonical scope keys (`GLOBAL`, `MANIFEST`, `RUN`) via `resolve_scope`.
   - deterministic baseline mode selection from normalized signal states:
     - required gaps -> `FAIL_CLOSED`
     - optional error -> `DEGRADED_2`
     - optional stale/missing -> `DEGRADED_1`
     - all healthy -> `NORMAL`
   - hysteresis transition rules:
     - immediate downshift on worse baseline
     - upshift only after policy quiet-period and only one rung per evaluation.
2. Added fail-safe wrapper:
   - `evaluate_posture_safe(...)` guarantees a `FAIL_CLOSED` decision with explicit evaluator-failure reason if policy/snapshot/evaluator resolution fails.
3. Exported Phase 3 APIs for downstream usage:
   - updated `src/fraud_detection/degrade_ladder/__init__.py` to export evaluator symbols.
4. Added Phase 3 tests:
   - `tests/services/degrade_ladder/test_phase3_evaluator.py`
   - coverage includes scope determinism, evaluator determinism, required-gap downshift, quiet-period hold, one-rung upshift, and fail-closed wrapper behavior.

### Invariants enforced
- Scope key is explicit and deterministic; snapshot scope mismatch is treated as evaluator error.
- Decision path has no hidden wall-clock dependency (`decision_time_utc` is caller supplied).
- Hysteresis cannot disable immediate downshift; invalid policy hysteresis shape is rejected.
- Evaluator failures do not produce permissive behavior; forced `FAIL_CLOSED` is returned with provenance reason.

### Security and production posture notes
- No secret-bearing artifacts were introduced.
- Fail-closed fallback preserves safety under malformed config or runtime evaluator exceptions.
- Scope mismatch handling reduces cross-run/scope contamination risk.

### Validation evidence
- `python -m pytest tests/services/degrade_ladder -q` -> `18 passed`.

### Phase closure assessment
- Phase 3 DoD is satisfied at component scope:
  - explicit deterministic scope resolution,
  - deterministic evaluator output for fixed inputs,
  - downshift/upshift hysteresis semantics implemented,
  - forced fail-closed wrapper on evaluator/policy failure.

---

## Entry: 2026-02-07 03:29:49 — Phase 4 implementation plan (posture store + serve surface)

### Problem / goal
Proceed to DL Phase 4 and implement the first operational serving boundary DF can consume safely:
1. durable current-posture store with `posture_seq` + policy stamps,
2. explicit transaction/commit semantics,
3. serve API with freshness metadata and fail-safe fallback on store trust failures.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (Phase 4 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/degrade_ladder.design-authority.md` (S5/S6 expectations)
- existing DL modules (`contracts.py`, `config.py`, `signals.py`, `evaluator.py`)
- existing repository patterns for dual SQLite/Postgres stores (`online_feature_plane/store.py`, `scenario_runner/authority.py`)

### Decision trail (live)
1. Implement DL posture store as a dedicated module (`store.py`) with:
   - `build_store(dsn, stream_id)` backend selector,
   - SQLite + Postgres implementations,
   - a strict store contract that only serves committed/valid records.
2. Persist one authoritative current row per scope key with:
   - full `DegradeDecision` payload,
   - `policy_*` stamps and `updated_at_utc`,
   - monotonic update rule on `posture_seq`.
3. Define transaction boundary explicitly:
   - each write operation uses a DB transaction and returns only after commit; read path only observes committed rows.
4. Fail-safe trust posture:
   - malformed row payload, sequence regression, or unreadable/corrupt store state is surfaced as a trusted-state error for serving.
5. Implement serve surface (`serve.py`) as a deterministic API:
   - `get_current_posture(scope_key, decision_time_utc, max_age_seconds, policy_bundle?)`,
   - returns posture + staleness metadata (`age_seconds`, `is_stale`, `staleness_reason`, `served_at_utc`),
   - if store missing/corrupt/unreadable: return explicit `FAIL_CLOSED` decision with reason evidence.
6. Keep Phase 4 scope tight:
   - no outbox/control bus emission (Phase 6),
   - no health classifier state machine (Phase 5),
   - no DF wiring yet; only component-level serving contract.

### Planned edits
- `src/fraud_detection/degrade_ladder/store.py` (new)
- `src/fraud_detection/degrade_ladder/serve.py` (new)
- `src/fraud_detection/degrade_ladder/__init__.py` (exports)
- `tests/services/degrade_ladder/test_phase4_store_and_serve.py` (new)
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (mark Phase 4 status + evidence if green)

### Invariants to enforce
- One current posture per `(stream_id, scope_key)`.
- `posture_seq` cannot regress.
- Store payload must deserialize through `DegradeDecision.from_payload`; invalid payloads are treated as trust break.
- Serve surface never returns permissive posture when trust is broken; must clamp `FAIL_CLOSED`.
- Staleness is computed against caller-supplied `decision_time_utc` (no hidden now).

### Validation plan
- `python -m pytest tests/services/degrade_ladder -q`
- direct assertions on:
  - transactional write/read behavior,
  - monotonic sequence enforcement,
  - freshness metadata correctness,
  - forced fail-closed on missing/corrupt store state.

---

## Entry: 2026-02-07 03:33:07 — DL Phase 4 implemented (posture store + serve surface)

### Implementation summary
Phase 4 is now implemented and validated at component scope.

### What was implemented
1. Added current-posture store module:
   - `src/fraud_detection/degrade_ladder/store.py`
   - `build_store(dsn, stream_id)` selector with SQLite/Postgres backends.
   - `dl_current_posture` schema with persisted decision payload + policy stamps (`policy_id`, `policy_revision`, `policy_content_digest`) and `posture_seq`.
2. Added transactional commit semantics:
   - `commit_current(scope_key, decision)` executes under DB transaction with sequence checks:
     - reject sequence regression (`POSTURE_SEQ_REGRESSION`),
     - reject same-seq different-decision collisions,
     - return deterministic commit status (`inserted`, `updated`, `noop`).
3. Added trust-checked read semantics:
   - `read_current(scope_key)` parses stored `decision_json` via `DegradeDecision.from_payload`.
   - row columns are cross-validated against decoded decision payload.
   - malformed or inconsistent rows raise `DlPostureTrustError` (explicit trust break, not silent read).
4. Added serving boundary:
   - `src/fraud_detection/degrade_ladder/serve.py`
   - `DlCurrentPostureService.get_current_posture(...)` returns:
     - posture decision,
     - source/trust state,
     - `age_seconds`, `is_stale`, and `staleness_reason`,
     - serve timestamp metadata.
   - stale, missing, or store-error conditions clamp to explicit `FAIL_CLOSED` with provenance reasons.
5. Exposed Phase 4 APIs:
   - updated `src/fraud_detection/degrade_ladder/__init__.py` with store/serve exports.
6. Added Phase 4 tests:
   - `tests/services/degrade_ladder/test_phase4_store_and_serve.py`
   - validates commit/read roundtrip, sequence regression protection, freshness metadata behavior, and fail-safe clamp on corrupt store rows.

### Invariants enforced
- One current posture row per `(stream_id, scope_key)`.
- `posture_seq` is monotonic and cannot regress.
- Only contract-valid decisions are served from the store.
- Store trust failures and stale posture never produce permissive serve responses; they force fail-closed.
- Staleness is computed against explicit caller-supplied `decision_time_utc`.

### Security and production posture notes
- No credential-bearing artifacts introduced.
- Store corruption path is explicit and conservative (`DlPostureTrustError` -> serve fail-closed).
- Postgres backend included to preserve env-ladder operability while retaining local-parity SQLite support.

### Validation evidence
- `python -m pytest tests/services/degrade_ladder -q` -> `23 passed`.

### Phase closure assessment
- Phase 4 DoD is satisfied at component scope:
  - derived posture store persisted with policy/posture stamps,
  - serve surface returns posture + staleness metadata,
  - transactional commit boundary defined and tested,
  - corruption/read failure path enforces fail-safe output.

---

## Entry: 2026-02-07 03:29:49 — Phase 5 implementation plan (health gate + self-trust clamp)

### Problem / goal
Proceed to DL Phase 5 and make DL explicitly self-protecting:
1. classify operational trust into explicit health states,
2. force fail-closed for BLIND/BROKEN regardless of normal posture,
3. require evidence-based recovery (no elapsed-time-only clear),
4. control rebuild/re-evaluation triggers to avoid storms.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (Phase 5 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (health gates / fail-closed posture)
- `docs/model_spec/platform/component-specific/degrade_ladder.design-authority.md` (S8 health gate semantics)
- existing DL modules (`signals.py`, `serve.py`, `store.py`, `evaluator.py`)

### Decision trail (live)
1. Add dedicated health gate module (`health.py`) with:
   - pinned health states: `HEALTHY`, `IMPAIRED`, `BLIND`, `BROKEN`,
   - explicit gate object carrying `forced_mode`, reasons, and rebuild trigger metadata.
2. Implement controller semantics with per-scope memory:
   - immediate escalation on unsafe evidence,
   - recovery requires consecutive healthy evaluations (`healthy_clear_observations`) and hold-down clearance,
   - no auto-clear by elapsed time alone.
3. Rebuild trigger policy:
   - trigger only on selected reason codes (`POSTURE_MISSING`, `POSTURE_STORE_ERROR`, `POSTURE_STORE_CORRUPT`),
   - cooldown-backed (`rebuild_cooldown_seconds`) to prevent storming.
4. Integrate health gate with serving boundary:
   - add guarded service wrapper that applies health gate before normal posture serving,
   - BLIND/BROKEN always return fail-closed posture with gate provenance.
5. Keep scope to component-level behavior:
   - no external control-bus emission yet (Phase 6),
   - no DF integration yet.

### Planned edits
- `src/fraud_detection/degrade_ladder/health.py` (new)
- `src/fraud_detection/degrade_ladder/serve.py` (guarded serving integration)
- `src/fraud_detection/degrade_ladder/__init__.py` (exports)
- `tests/services/degrade_ladder/test_phase5_health_gate.py` (new)
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (mark Phase 5 status + evidence if green)

### Invariants to enforce
- State vocabulary is fixed (`HEALTHY/IMPAIRED/BLIND/BROKEN`).
- BLIND/BROKEN always force fail-closed.
- Recovery requires positive evidence; time passage without healthy observations is insufficient.
- Rebuild triggers are deterministic and cooldown-limited per scope.

### Validation plan
- `python -m pytest tests/services/degrade_ladder -q`
- direct assertions on:
  - health classification transitions,
  - forced fail-closed behavior under BLIND/BROKEN,
  - evidence-based recovery gating,
  - rebuild trigger cooldown behavior.

---

## Entry: 2026-02-07 06:54:21 — DL Phase 5 implemented (health gate + self-trust clamp)

### Implementation summary
Phase 5 is now implemented and validated at component scope.

### What was implemented
1. Added health gate module:
   - `src/fraud_detection/degrade_ladder/health.py`
   - pinned health states: `HEALTHY`, `IMPAIRED`, `BLIND`, `BROKEN`.
   - `DlHealthGateController` maintains per-scope memory and evaluates trust state from policy/signal/store/serve/control evidence.
2. Added forced fail-closed semantics:
   - gate returns `forced_mode=FAIL_CLOSED` for `BLIND/BROKEN`.
   - guarded serving path enforces gate clamps before normal posture serving.
3. Added evidence-based recovery rules:
   - recovery from BLIND/BROKEN requires configured healthy observation streak (`healthy_clear_observations`) and hold-down clearance.
   - no elapsed-time-only clearance path exists.
4. Added controlled rebuild trigger behavior:
   - rebuild signals emitted only for pinned reasons (`POSTURE_MISSING`, `POSTURE_STORE_ERROR`, `POSTURE_STORE_CORRUPT`).
   - per-scope cooldown (`rebuild_cooldown_seconds`) prevents rebuild storms.
5. Integrated health gate with serve boundary:
   - `src/fraud_detection/degrade_ladder/serve.py` now includes `DlGuardedPostureService`.
   - guarded service evaluates gate first; BLIND/BROKEN returns explicit fail-closed serve result with health-gate provenance.
   - guarded service escalates store-missing/store-error serve outcomes back into health gate state.
6. Exported Phase 5 APIs:
   - updated `src/fraud_detection/degrade_ladder/__init__.py` for health + guarded serve symbols.
7. Added Phase 5 tests:
   - `tests/services/degrade_ladder/test_phase5_health_gate.py`
   - covers state classification, forced clamp behavior, recovery gating, rebuild cooldown control, and guarded-store escalation behavior.

### Invariants enforced
- Health state vocabulary is explicit and fixed.
- BLIND/BROKEN always force fail-closed regardless of evaluator/store posture content.
- Recovery requires positive evidence; hold-down + streak gating prevents silent flip-flop.
- Rebuild triggers are deterministic and cooldown-limited.

### Security and production posture notes
- No secret-bearing artifacts introduced.
- Trust failures now route through explicit, auditable health gate reasons before serving.
- Guarded serve prevents accidental permissive posture under partial DL self-observability failure.

### Validation evidence
- `python -m pytest tests/services/degrade_ladder -q` -> `29 passed`.

### Phase closure assessment
- Phase 5 DoD is satisfied at component scope:
  - explicit health classifier states implemented,
  - BLIND/BROKEN forced fail-closed clamp implemented,
  - evidence-based recovery semantics enforced,
  - rebuild/re-evaluation trigger storm controls implemented.

---

## Entry: 2026-02-07 06:56:29 — Phase 6 implementation plan (posture-change emission lane)

### Problem / goal
Proceed to DL Phase 6 and implement posture-transition visibility without introducing correctness coupling:
1. deterministic posture-change event identity and per-scope ordering,
2. outbox/retry/idempotent emission behavior under restarts/failures,
3. explicit visibility-only semantics (DF correctness cannot depend on emitter),
4. emission failure/backlog metrics for operations.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (Phase 6 DoD)
- `docs/model_spec/platform/component-specific/degrade_ladder.design-authority.md` (S7 emission lane)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- existing DL modules (`store.py`, `serve.py`, `health.py`, `contracts.py`)

### Decision trail (live)
1. Add dedicated emission module (`emission.py`) with:
   - deterministic `event_id = sha256(scope_key|posture_seq)`,
   - canonical posture-change envelope builder (`dl.posture_changed.v1`),
   - global scope sentinel manifest handling.
2. Implement durable outbox store with SQLite/Postgres backends:
   - primary key `(stream_id, scope_key, posture_seq)` for idempotency,
   - status lifecycle `PENDING -> SENT` or `FAILED -> DEAD`,
   - retry scheduling with bounded backoff.
3. Enforce per-scope publish ordering:
   - drain processes the lowest unsent `posture_seq` per scope before later ones.
4. Keep control emission non-critical:
   - drain returns failure metrics/status; no coupling to serving/store correctness.
5. Surface operational metrics:
   - pending/failed/dead counts + oldest pending age seconds.

### Planned edits
- `src/fraud_detection/degrade_ladder/emission.py` (new)
- `src/fraud_detection/degrade_ladder/__init__.py` (exports)
- `tests/services/degrade_ladder/test_phase6_emission.py` (new)
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (mark Phase 6 status + evidence when green)

### Invariants to enforce
- Same `(scope_key, posture_seq)` always maps to the same `event_id`.
- Outbox enqueue is idempotent for duplicate transition attempts.
- Per-scope sequence order is preserved by drain behavior.
- Emission failures do not mutate posture correctness surfaces.

### Validation plan
- `python -m pytest tests/services/degrade_ladder -q`
- direct assertions for:
  - deterministic identity and idempotent enqueue,
  - retry/backoff and dead-letter transitions,
  - per-scope ordered drain,
  - backlog/failure metric exposure.

---

## Entry: 2026-02-07 06:56:29 — DL Phase 6 implemented (posture-change emission lane)

### Implementation summary
Phase 6 is now implemented and validated at component scope.

### What was implemented
1. Added emission lane module:
   - `src/fraud_detection/degrade_ladder/emission.py`
   - deterministic identity helper `event_id = sha256(scope_key|posture_seq)`,
   - canonical posture-change envelope builder (`dl.posture_changed.v1`).
2. Added durable outbox store abstraction:
   - `build_outbox_store(dsn, stream_id)` with SQLite/Postgres backends,
   - idempotent keying by `(stream_id, scope_key, posture_seq)`,
   - lifecycle statuses `PENDING`, `FAILED`, `SENT`, `DEAD`.
3. Added ordered drain + retry behavior:
   - per-scope ordering preserved by draining only the earliest unsent sequence per scope,
   - bounded retry with exponential backoff,
   - dead-letter transition after max attempts.
4. Added operational metrics surface:
   - pending/failed/dead/sent counters,
   - oldest pending age in seconds.
5. Exported Phase 6 APIs:
   - updated `src/fraud_detection/degrade_ladder/__init__.py` to include emission lane symbols.
6. Added Phase 6 tests:
   - `tests/services/degrade_ladder/test_phase6_emission.py`
   - verifies deterministic IDs, idempotent enqueue, ordered drain, retry/backoff/dead-letter transitions, and backlog metrics.

### Invariants enforced
- Same `(scope_key, posture_seq)` always produces the same event identity.
- Duplicate enqueue attempts do not duplicate outbox transitions.
- Later posture sequences in a scope are not emitted before earlier unsent sequences.
- Emission failures are tracked operationally without affecting posture serving correctness.

### Security and production posture notes
- Emission lane is visibility-only; serving and posture correctness do not depend on publish success.
- Error payloads are truncated to bounded length in outbox error fields.
- Global scope events use explicit manifest sentinel for canonical envelope compliance.

### Validation evidence
- `python -m pytest tests/services/degrade_ladder -q` -> `34 passed`.

### Phase closure assessment
- Phase 6 DoD is satisfied at component scope:
  - deterministic posture-change identity + ordering semantics are implemented,
  - outbox/retry/idempotent emission path implemented,
  - correctness remains decoupled from emitter success,
  - failure/backlog metrics are surfaced for operations.

---

## Entry: 2026-02-07 07:01:28 — Phase 7 implementation plan (security, governance, ops telemetry)

### Problem / goal
Proceed to DL Phase 7 and make posture operations attributable + operable:
1. guarantee governance-relevant posture outputs carry `policy_rev` and provenance stamps,
2. add structured/queryable governance event recording for key posture-control changes,
3. add operational metrics covering transitions/fail-safe/evaluator/signal freshness/serve fallback,
4. enforce payload hygiene to avoid secret leakage in governance/ops artifacts.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (Phase 7 DoD)
- `docs/model_spec/platform/component-specific/degrade_ladder.design-authority.md` (S7/S8 visibility/governance posture)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- existing DL modules (`contracts.py`, `signals.py`, `serve.py`, `health.py`, `emission.py`)

### Decision trail (live)
1. Implement a dedicated persistence-backed governance/telemetry module (`ops.py`) using SQLite/Postgres parity.
2. Record structured governance events for:
   - policy activation changes (`dl.policy_activated.v1`),
   - forced fail-closed transitions (`dl.fail_closed_forced.v1`),
   - posture transitions (`dl.posture_transition.v1`).
3. Ensure each governance event stores:
   - deterministic `event_id`,
   - `policy_id/revision/content_digest`,
   - scope, timestamp, and sanitized payload.
4. Add metrics counters covering Phase 7 DoD:
   - `posture_transitions_total`,
   - `forced_fail_closed_total`,
   - `evaluator_errors_total`,
   - signal freshness counters (`signal_required_ok_total`, `signal_required_bad_total`),
   - serve fallback counters (`serve_fallback_total`).
5. Add payload sanitizer for governance event payloads to redact secret-like fields (`token`, `secret`, `password`, `key`, `credential`, `lease_token`).
6. Keep correctness coupling explicit:
   - governance/metrics recording errors should raise explicit ops errors to caller layer; runtime can decide whether to hard-fail or best-effort.

### Planned edits
- `src/fraud_detection/degrade_ladder/ops.py` (new)
- `src/fraud_detection/degrade_ladder/__init__.py` (exports)
- `tests/services/degrade_ladder/test_phase7_ops_governance.py` (new)
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (mark Phase 7 status + evidence when green)

### Invariants to enforce
- Governance events are structured and queryable by type/scope/time.
- Governance records and posture transition events include `policy_rev` stamps.
- Secret-like keys are redacted from persisted governance payloads.
- Metrics include all required Phase 7 categories.

### Validation plan
- `python -m pytest tests/services/degrade_ladder -q`
- direct assertions for:
  - policy stamp presence in governance/posture events,
  - query/filter behavior over governance event table,
  - metric counters for transitions/fail-safe/evaluator/signal freshness/serve fallback,
  - payload redaction behavior.

---

## Entry: 2026-02-07 07:04:36 — DL Phase 7 implemented (security, governance, ops telemetry)

### Implementation summary
Phase 7 is now implemented and validated at component scope.

### What was implemented
1. Added governance/ops telemetry module:
   - `src/fraud_detection/degrade_ladder/ops.py`
   - queryable governance event store with SQLite/Postgres backends.
2. Added structured governance events:
   - `dl.policy_activated.v1`
   - `dl.posture_transition.v1`
   - `dl.fail_closed_forced.v1`
   Each event persists `policy_id`, `policy_revision`, `policy_content_digest`, scope, timestamp, and structured payload.
3. Added secret redaction guardrails:
   - payload sanitizer redacts sensitive keys (`token`, `secret`, `password`, `credential`, key-like secret markers) before persistence.
4. Added required Phase 7 metrics coverage:
   - `posture_transitions_total`
   - `forced_fail_closed_total`
   - `evaluator_errors_total`
   - `signal_required_ok_total`
   - `signal_required_bad_total`
   - `serve_fallback_total`
5. Added query surfaces:
   - event queries by type/scope with deterministic ordering,
   - metric snapshots by scope or aggregate.
6. Exported Phase 7 APIs:
   - updated `src/fraud_detection/degrade_ladder/__init__.py`.
7. Added Phase 7 tests:
   - `tests/services/degrade_ladder/test_phase7_ops_governance.py`
   - validates policy stamps, redaction, structured queryability, and metric coverage.

### Additional hardening performed
- Adjusted Phase 6 outbox enqueue timing in `src/fraud_detection/degrade_ladder/emission.py` so newly enqueued transitions are immediately due based on decision timestamp, removing wall-clock nondeterminism in ordered-drain behavior.

### Invariants enforced
- Governance events are structured and queryable by type/scope/time.
- Policy revision/provenance stamps are persisted with posture/policy governance records.
- Sensitive payload fields are redacted before storage.
- Required operational metrics are recorded and queryable.

### Security and production posture notes
- No secrets are persisted from payload metadata in governance events.
- Governance and telemetry are explicit persistence lanes; production services can decide strictness on recorder failure handling at call sites.

### Validation evidence
- `python -m pytest tests/services/degrade_ladder -q` -> `37 passed`.

### Phase closure assessment
- Phase 7 DoD is satisfied at component scope:
  - policy/provenance stamps carried in governance event outputs,
  - redaction guardrails prevent secret leakage in persisted payloads,
  - required ops metrics are covered and queryable,
  - governance events for policy changes and forced fail-closed transitions are structured and queryable.

---

## Entry: 2026-02-07 07:01:28 — Phase 8 implementation plan (validation, parity proof, closure boundary)

### Problem / goal
Proceed to DL Phase 8 and explicitly close component readiness with evidence:
1. validate existing unit behavior coverage remains intact after Phases 1-7,
2. add integration-level tests for DF-facing posture consumption + mask enforcement semantics,
3. add replay-style determinism tests (same snapshot/policy => same output),
4. add local-parity behavior proofs under healthy/degraded signal scenarios,
5. publish explicit closure boundary statement for DL vs pending DF/AL/DLA coupling.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (Phase 8 DoD)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 4.4/4.5 boundaries)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- existing DL module/test surfaces through Phase 7.

### Decision trail (live)
1. Use a Phase 8 validation test suite file (`test_phase8_validation_parity.py`) to avoid mixing closure evidence into earlier phase files.
2. Because `src/fraud_detection/decision_fabric` is not present yet, integration proof will use a deterministic DF-consumption shim in tests that enforces DL capability mask rules exactly as pinned:
   - `allow_ieg`, `allowed_feature_groups`, model toggles, `action_posture`.
3. Replay proof will exercise full DL flow (snapshot -> evaluator -> store -> serve) with identical inputs and assert stable digest/output.
4. Local-parity proof will run a multi-step scenario in `local_parity` profile to show stable transitions:
   - healthy baseline,
   - required-signal degradation to fail-closed,
   - quiet-period gated recovery one rung at a time.
5. Build-plan closure text will explicitly state:
   - DL component is green for posture authority/serving/emission/governance,
   - DF decision coupling + AL/DLA downstream integration remains tracked under platform Phase 4.4/4.5.

### Planned edits
- `tests/services/degrade_ladder/test_phase8_validation_parity.py` (new)
- `docs/model_spec/platform/implementation_maps/degrade_ladder.build_plan.md` (Phase 8 status + closure statement evidence)

### Invariants to enforce
- DF-facing mask enforcement semantics are deterministic and conservative.
- Replay determinism is insensitive to invocation order for identical inputs.
- Recovery behavior in local-parity profile respects hysteresis and one-rung upshift posture.

### Validation plan
- `python -m pytest tests/services/degrade_ladder -q`
- confirm all prior phase tests still pass and new Phase 8 tests pass with deterministic outputs.

---

## Entry: 2026-02-07 07:14:13 — DL Phase 8 implemented (validation/parity/closure boundary)

### Implementation summary
Phase 8 is now implemented and validated at component scope.

### What was implemented
1. Added dedicated Phase 8 validation suite:
   - `tests/services/degrade_ladder/test_phase8_validation_parity.py`
2. Added integration-level DF consumption proof (contract-style):
   - deterministic DF-like mask enforcement shim validates DL mask semantics for:
     - `allow_ieg`
     - `allowed_feature_groups`
     - `allow_model_primary`
     - `allow_model_stage2`
     - `action_posture`.
   - posture is served from DL store/serve boundary and then enforced by shim.
3. Added replay determinism proof:
   - same profile + same snapshot + same decision time + same scope + same posture_seq yields identical decision digest across repeated evaluations.
   - persisted/readback posture digest remains stable.
4. Added local-parity transition proof:
   - `local_parity` profile scenario demonstrates stable lifecycle:
     - healthy baseline -> `NORMAL`
     - required-signal gap -> immediate `FAIL_CLOSED`
     - healthy before quiet period expiry -> hold at `FAIL_CLOSED`
     - post-quiet recovery -> one-rung steps `DEGRADED_2` -> `DEGRADED_1` -> `NORMAL`.

### Invariants confirmed by Phase 8
- DF-facing enforcement semantics are deterministic and conservative under degraded masks.
- Replay-style evaluation is deterministic for identical inputs.
- Local-parity hysteresis behavior is stable and policy-driven.
- Full DL component test suite remains green after Phases 1-8.

### Validation evidence
- `python -m pytest tests/services/degrade_ladder -q` -> `40 passed`.

### Closure boundary statement
- DL is component-green for posture authority, posture serving, health self-trust clamp, posture-change emission lane, and governance/ops telemetry.
- Remaining non-DL closure tracks:
  - runtime DF decision coupling and end-to-end mask consumption in live RTDL path,
  - AL/DLA downstream closure and full plane end-to-end outcomes,
  remain under platform Phase 4.4/4.5 integration gates.

---

## Entry: 2026-02-07 07:31:11 — DL 20-event runtime plumbing sanity run (pre-DF integration)

### Goal
Run a compact, auditable 20-step DL runtime plumbing pass now (before DF runtime integration) to confirm module wiring behavior end-to-end:
- signals -> evaluator -> posture store -> guarded serve -> emission outbox -> ops/governance telemetry.

### Run details
- Run id: `dl_sanity_20260207T073111Z`
- Scope: `scope=GLOBAL`
- Events processed: `20`
- Artifacts:
  - `runs/fraud-platform/dl_sanity_20260207T073111Z/degrade_ladder/dl_20_event_summary.json`
  - `runs/fraud-platform/dl_sanity_20260207T073111Z/degrade_ladder/dl_20_event_rows.json`
  - `runs/fraud-platform/dl_sanity_20260207T073111Z/degrade_ladder/posture.sqlite`
  - `runs/fraud-platform/dl_sanity_20260207T073111Z/degrade_ladder/outbox.sqlite`
  - `runs/fraud-platform/dl_sanity_20260207T073111Z/degrade_ladder/ops.sqlite`

### Observed outcomes
- Served mode counts:
  - `NORMAL`: 10
  - `FAIL_CLOSED`: 10
- Health states observed:
  - `HEALTHY`, `BLIND`
- Outbox/emission:
  - posture transitions emitted: `2`
  - outbox metrics: pending `0`, failed `0`, dead `0`, sent `2`
- Governance/ops telemetry:
  - governance events total: `4`
  - metrics snapshot:
    - `forced_fail_closed_total`: `1`
    - `posture_transitions_total`: `2`
    - `serve_fallback_total`: `5`
    - `signal_required_bad_total`: `16`
    - `signal_required_ok_total`: `84`

### Interpretation
- DL runtime plumbing path is functioning as expected in a pre-DF isolated pass:
  - posture decisions committed and served,
  - health gate enforced fail-closed during degraded signal window,
  - transitions emitted deterministically,
  - governance + ops metrics recorded and queryable.
- This is a **DL plumbing sanity run**, not full RTDL E2E closure; DF runtime coupling and downstream AL/DLA remain integration gates outside DL scope.

---

## Entry: 2026-02-07 13:01:00 - Plan: DF-compatible deterministic scope-key posture boundary

### Problem
DL store/serve is functioning, but DF integration still presents scope as free-form strings in some paths. For deterministic RTDL replay and registry alignment, DF and DL must use the same canonical scope token derived from structured scope axes.

### Authorities
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md`

### Decision
1. Keep DL internal behavior unchanged (GLOBAL/MANIFEST/RUN logic and anti-flap semantics).
2. Tighten DF-facing contract so scope key supplied to DL guard is deterministic and derived from registry scope axes.
3. Validate that posture stamps emitted back to DF retain the same deterministic scope key.

### Files expected (integration-side)
- primary changes in DF posture integration layer (`decision_fabric/posture.py` + tests).
- DL-side code change only if compatibility gaps surface during tests.

### Validation plan
- `python -m pytest tests/services/decision_fabric/test_phase3_posture.py -q`
- `python -m pytest tests/services/degrade_ladder -q` (if DF-side changes trigger contract assumptions).

---

## Entry: 2026-02-07 13:09:19 - Deterministic DF scope-key boundary validated with DL

### What changed
No DL core algorithm changes were required. Scope-key normalization was implemented in DF posture integration and validated against DL serving expectations.

### Validation performed
1. DF posture tests now include scope mapping normalization proof (`environment/mode/bundle_slot` -> canonical token).
2. DL full suite re-run to confirm no behavioral regressions at DL boundaries.

### Evidence
- `python -m pytest tests/services/degrade_ladder -q` -> `40 passed`.
- DF posture coverage is included in `python -m pytest tests/services/decision_fabric -q` -> `69 passed`.

### Outcome
DL posture service remains stable while accepting deterministic scope tokens from DF integration.
