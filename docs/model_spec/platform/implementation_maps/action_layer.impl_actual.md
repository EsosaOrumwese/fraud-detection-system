# Action Layer Implementation Map
_As of 2026-02-05_

---

## Entry: 2026-02-05 15:14:40 — Phase 4 planning kickoff (AL scope + idempotency)

### Problem / goal
Lock AL v0 input/output semantics and idempotency rules before implementation.

### Authorities / inputs
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/action_layer.design-authority.md`
- Platform rails (IG→EB is sole front door; canonical envelope; append-only outcomes).
- RTDL contracts under `docs/model_spec/platform/contracts/real_time_decision_loop/`.

### Decisions captured (v0 stance)
- AL is the **only executor**; it consumes ActionIntents via EB and emits ActionOutcomes via IG→EB.
- Semantic idempotency key is `(ContextPins, idempotency_key)`; duplicates **never** re-execute.
- ActionIntent must carry `actor_principal` + `origin`; ActionOutcome records `authz_policy_rev`.
- Outcome status vocabulary: `EXECUTED | DENIED | FAILED`.
- Authz is enforced at AL (deny emits outcome, no side effects).

### Planned implementation scope (Phase 4.5)
- Implement intent ledger + outcome store (Postgres), idempotent execution, and retry/backoff.
- Publish outcomes through IG admission with stable event_id.

---
