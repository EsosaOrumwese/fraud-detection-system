# Action Layer Build Plan (v0)
_As of 2026-02-07_

## Purpose
Provide an executable, component-scoped AL plan aligned to platform `Phase 4.5` (`decision -> outcome -> audit`) and RTDL pinned decisions.

## Authorities (binding)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (`4.5.A...4.5.J`)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/action_layer.design-authority.md`

## Planning rules (binding)
- Progressive elaboration: expand only active phase sections while preserving explicit DoD gates.
- No half-baked transitions: do not advance until phase DoD is validated.
- Rails are non-negotiable: admitted ingress only, idempotent side effects, append-only outcomes, provenance first.

## Component boundary
- This component owns:
  - intake/normalization of admitted ActionIntent events,
  - execution idempotency and side-effect attempts,
  - immutable ActionOutcome truth and publish behavior.
- This component does not own:
  - decision synthesis (DF),
  - append-only audit truth (DLA),
  - admission decisions (IG).

## Phase plan (v0)

### Phase 1 — Intake contracts + pin/shape validation
**Intent:** lock strict ActionIntent and ActionOutcome contracts at AL boundary.

**DoD checklist:**
- ActionIntent required fields are pinned (`actor_principal`, `origin`, `decision_id`, `idempotency_key`, required ContextPins).
- AL intake validates envelope + pins fail-closed with explicit reason codes.
- Normalization path is deterministic and emits machine-readable failure lane (no silent drop).
- Contract and taxonomy tests exist for accepted/rejected payloads.

### Phase 2 — Semantic idempotency ledger
**Intent:** guarantee at-least-once safe execution.

**DoD checklist:**
- Semantic execution key is deterministic and replay-stable.
- Duplicate intents with same payload do not re-execute effects.
- Same semantic key with payload hash mismatch is anomaly/quarantine (never overwrite).
- Idempotency state is durable and scoped by run pins.

### Phase 3 — Authorization + execution posture gates
**Intent:** make execution policy explicit and safe.

**DoD checklist:**
- Authz/policy checks execute before side effects.
- Denied intents produce immutable `DENIED` outcomes with policy reason refs.
- Missing/invalid execution posture is fail-safe (no blind execution).
- Policy revision stamps are captured on outcomes.

### Phase 4 — Executor adapters + retry/failure semantics
**Intent:** execute effects safely across retriable/uncertain conditions.

**DoD checklist:**
- Executor adapters support bounded retry + backoff with explicit terminal behavior.
- Final failure emits immutable `FAILED` outcome with stable error taxonomy.
- Uncertain commit lane is explicit (`UNKNOWN/UNCERTAIN_COMMIT`) and replay-safe.
- Retries never produce duplicate external effects.

### Phase 5 — Outcome store + IG publish discipline
**Intent:** keep outcomes immutable and publishable through canonical ingress.

**DoD checklist:**
- Outcome records are append-only with stable `outcome_id`.
- Outcome publish path uses IG with stable event identity.
- Publish outcomes (`ADMIT`, `DUPLICATE`, `QUARANTINE`, ambiguous) are handled deterministically.
- Receipt/evidence refs are persisted for reconciliation.

### Phase 6 — Checkpoints + replay determinism
**Intent:** guarantee deterministic AL behavior under restarts/replay.

**DoD checklist:**
- Checkpoints advance only after durable outcome append/publish gate.
- Replay from same basis reproduces identical outcome identity chain.
- Duplicate storm tests prove no double execution.
- Crash/restart recovery does not skip or mutate prior outcomes.

### Phase 7 — Observability + governance + security
**Intent:** make AL operable and auditable without becoming control-path logic.

**DoD checklist:**
- Metrics/logs cover intent intake, exec attempts, outcome status, retries, denies, quarantines, ambiguous commits.
- Health posture exposes lag/error/queue saturation signals with reason codes.
- Governance/security stamps are present (`policy_rev`, execution profile ref, actor attribution).
- Sensitive credentials/tokens are excluded from emitted artifacts/logs.

### Phase 8 — Platform integration closure (`4.5` AL scope)
**Intent:** prove AL is green at component boundary and ready for platform `4.5` closure with DLA.

**DoD checklist:**
- Integration tests prove DF decision/intent -> AL execution -> outcome emission continuity.
- Local-parity monitored runs exist for 20 and 200 events with AL evidence captured.
- Replay validation confirms no duplicate side effects and stable outcome lineage.
- Closure statement is explicit: AL component green; DLA-linked audit closure tracked by platform `4.5` gates.

## Status (rolling)
- Current focus: Phase 1 (`Intake contracts + pin/shape validation`).
