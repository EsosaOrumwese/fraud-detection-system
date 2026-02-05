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
