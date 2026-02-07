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
