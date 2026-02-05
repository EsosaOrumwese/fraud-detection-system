# Action Layer Build Plan (v0)
_As of 2026-02-05_

## Purpose
Provide a progressive, component-scoped build plan for AL aligned to Phase 4.5 (actions + outcomes).

## Planning rules (binding)
- Progressive elaboration: expand only the active phase into sections + DoD.
- No half-baked phases: do not advance until DoD is satisfied.
- Rails are non-negotiable: IG→EB as sole front door, idempotent outcomes, append-only truth.

## Phase plan (v0)

### Phase 1 — Contracts + idempotency ledger
**Intent:** lock ActionIntent/ActionOutcome contracts and dedupe semantics.

**DoD checklist:**
- ActionIntent includes actor_principal + origin + idempotency_key.
- ActionOutcome status vocabulary is pinned (EXECUTED|DENIED|FAILED).
- Idempotency scope `(ContextPins, idempotency_key)` is enforced.

### Phase 2 — Execution + outcome emission
**Intent:** execute side effects safely and emit outcomes through IG.

**DoD checklist:**
- Action execution uses bounded retries and never double-executes.
- Outcomes are immutable and joinable to decision_id + action_id.
- Outcomes are published via IG and receipts are recorded.

### Phase 3 — Ops posture
**Intent:** expose executor health + authorization signals.

**DoD checklist:**
- Emit execution latency/error metrics and authz-deny counts.

---
