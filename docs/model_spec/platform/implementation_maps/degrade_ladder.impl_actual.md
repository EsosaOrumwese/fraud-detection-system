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
