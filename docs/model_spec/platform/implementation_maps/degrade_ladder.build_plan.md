# Degrade Ladder Build Plan (v0)
_As of 2026-02-07_

## Purpose
Provide an executable, phase-by-phase DL build plan aligned to platform Phase 4.4 (`DF/DL decision core`) and RTDL fail-safe posture pins.

## Authorities (binding)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 4.4)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/degrade_ladder.design-authority.md`

## Planning rules (binding)
- Progressive elaboration: phases are explicit; active phase expands to implementation steps and tests.
- No half-baked phases: do not advance until DoD is evidenced.
- Rails are non-negotiable: explicit degrade posture, deterministic behavior, fail-closed safety.

## Phase plan (v0)

### Phase 1 — DL contract + policy profile authority
**Intent:** pin DL output contract and the policy profile surface.
**Status:** completed (2026-02-07, component scope).

**DoD checklist:**
- `DegradeDecision` contract is pinned with:
  `mode`, `capabilities_mask`, `policy_rev`, `posture_seq`, `decided_at_utc`, provenance reasons.
- Mode ladder is fixed and documented:
  `NORMAL -> DEGRADED_1 -> DEGRADED_2 -> FAIL_CLOSED`.
- Capability mask vocabulary is pinned (`allow_ieg`, `allowed_feature_groups`, `allow_model_primary`, `allow_model_stage2`, `allow_fallback_heuristics`, `action_posture`).
- Policy profile schema for thresholds/hysteresis is versioned and fail-closed on invalid config.
- Evidence:
  - `python -m pytest tests/services/degrade_ladder -q` -> `7 passed`
  - `config/platform/dl/policy_profiles_v0.yaml`

### Phase 2 — Signal intake + snapshot normalization
**Intent:** build deterministic input snapshots for posture evaluation.
**Status:** completed (2026-02-07, component scope).

**DoD checklist:**
- DL ingests required health signals with explicit freshness/validity semantics.
- Signal snapshots are canonicalized and scoped (global or run/scope key as pinned).
- Missing or stale required signals are represented explicitly and drive fail-safe behavior.
- Snapshot build path is deterministic and observable (no hidden default values).
- Evidence:
  - `python -m pytest tests/services/degrade_ladder -q` -> `11 passed`
  - `src/fraud_detection/degrade_ladder/signals.py`

### Phase 3 — Scope resolution + deterministic evaluator
**Intent:** compute posture deterministically from policy + snapshot.
**Status:** completed (2026-02-07, component scope).

**DoD checklist:**
- Scope resolution for posture evaluation is explicit and deterministic.
- Evaluator produces deterministic mode/mask for identical snapshot + policy inputs.
- Hysteresis is enforced:
  immediate downshift on breach, controlled one-rung upshift after quiet period.
- Policy or evaluator failure yields forced fail-closed posture with explicit reasons.
- Evidence:
  - `python -m pytest tests/services/degrade_ladder -q` -> `18 passed`
  - `src/fraud_detection/degrade_ladder/evaluator.py`
  - `tests/services/degrade_ladder/test_phase3_evaluator.py`

### Phase 4 — Posture store + serve surface
**Intent:** provide DF a stable, low-latency posture read boundary.
**Status:** completed (2026-02-07, component scope).

**DoD checklist:**
- Derived posture store persists current posture with `posture_seq` and policy stamps.
- Serve surface returns posture + provenance and explicit staleness metadata.
- Commit point is transactionally defined before posture can be served as current.
- Store corruption/read-write failure path is fail-safe (serve forced fail-closed if trust is broken).
- Evidence:
  - `python -m pytest tests/services/degrade_ladder -q` -> `23 passed`
  - `src/fraud_detection/degrade_ladder/store.py`
  - `src/fraud_detection/degrade_ladder/serve.py`
  - `tests/services/degrade_ladder/test_phase4_store_and_serve.py`

### Phase 5 — Health gate + self-trust clamp
**Intent:** make DL explicitly self-protecting under degraded internals.
**Status:** completed (2026-02-07, component scope).

**DoD checklist:**
- Health classifier produces explicit state (`HEALTHY/IMPAIRED/BLIND/BROKEN` or equivalent pinned set).
- BLIND/BROKEN classes force fail-closed clamp regardless of normal evaluator outcome.
- Recovery/clear semantics are evidence-based (no silent auto-clear by elapsed time only).
- Rebuild or re-evaluation triggers are controlled and non-storming.
- Evidence:
  - `python -m pytest tests/services/degrade_ladder -q` -> `29 passed`
  - `src/fraud_detection/degrade_ladder/health.py`
  - `src/fraud_detection/degrade_ladder/serve.py`
  - `tests/services/degrade_ladder/test_phase5_health_gate.py`

### Phase 6 — Posture-change emission (observability lane)
**Intent:** expose posture transitions without introducing correctness coupling.
**Status:** completed (2026-02-07, component scope).

**DoD checklist:**
- Posture-change control facts are emitted with deterministic identity and ordering per scope.
- Emission path is outbox/retry safe and idempotent under retries/restarts.
- Control emission is explicitly non-critical for DF correctness (visibility-only lane).
- Publish failure/backlog metrics are emitted and surfaced to operations.
- Evidence:
  - `python -m pytest tests/services/degrade_ladder -q` -> `34 passed`
  - `src/fraud_detection/degrade_ladder/emission.py`
  - `tests/services/degrade_ladder/test_phase6_emission.py`

### Phase 7 — Security, governance, and ops telemetry
**Intent:** ensure DL posture changes are attributable and operable.

**DoD checklist:**
- DL outputs carry `policy_rev` and governance-relevant provenance stamps.
- Secrets remain runtime-only; no secret leakage into posture artifacts/logs/docs.
- Metrics cover posture transitions, fail-safe clamps, evaluator errors, signal freshness, and serve fallback rates.
- Governance events for policy revision changes and forced fail-closed transitions are structured and queryable.

### Phase 8 — Validation, parity proof, and closure boundary
**Intent:** prove DL component readiness and define integration handoff.

**DoD checklist:**
- Unit tests cover evaluator determinism, mode transitions, hysteresis, and fail-closed clamps.
- Integration tests cover DF consumption of DL posture and mask enforcement behavior.
- Replay-style tests verify same snapshot + policy -> same posture output.
- Local-parity proofs demonstrate stable posture behavior under normal and degraded signal scenarios.
- Closure statement is explicit:
  DL component green for posture authority/serving; DF decision coupling and AL/DLA downstream closure remain tracked under platform Phase 4.4/4.5 gates.

## Status (rolling)
- Current focus: Phase 7 planning/implementation (security, governance, ops telemetry).
