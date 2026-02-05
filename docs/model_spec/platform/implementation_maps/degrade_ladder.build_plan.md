# Degrade Ladder Build Plan (v0)
_As of 2026-02-05_

## Purpose
Provide a progressive, component-scoped build plan for DL aligned to Phase 4.4 (RTDL safety posture).

## Planning rules (binding)
- Progressive elaboration: expand only the active phase into sections + DoD.
- No half-baked phases: do not advance until DoD is satisfied.
- Rails are non-negotiable: explicit degrade posture, determinism, fail-closed.

## Phase plan (v0)

### Phase 1 — Contracts + policy profile
**Intent:** lock degrade decision contract and policy-driven thresholds.

**DoD checklist:**
- Degrade posture schema includes mode, capabilities_mask, policy_rev, posture_seq, decided_at_utc.
- Policy profile format for thresholds is pinned and versioned.

### Phase 2 — Evaluator + posture store
**Intent:** compute deterministic posture from signals.

**DoD checklist:**
- Deterministic evaluation with hysteresis (downshift immediate, upshift gated).
- Derived posture store persists current mode + mask for DF consumption.

### Phase 3 — Ops signals
**Intent:** expose posture changes and health signals.

**DoD checklist:**
- Emit posture-change facts and health signals for governance/ops.

---
