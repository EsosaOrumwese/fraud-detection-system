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

## Entry: 2026-02-07 18:20:38 - Plan: expand AL build plan to executable Phase 4.5 component map

### Trigger
Platform `4.5` was expanded into `4.5.A...4.5.J`. AL component plan is still a 3-phase high-level stub and cannot support hardened execution sequencing or closure evidence.

### Authorities used
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (`4.5.A...4.5.J`)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (actions semantics, idempotency, observability)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md` (decision -> action -> outcome chain)
- `docs/model_spec/platform/component-specific/action_layer.design-authority.md`

### Design decisions before editing
1. Expand AL into phase sections that map directly to AL-owned portions of `4.5`.
2. Keep boundary explicit:
   - AL owns execution and outcome truth,
   - DLA consumes outcome truth; AL does not own audit closure.
3. Encode uncertain publish/execute semantics explicitly:
   - retries, `FAILED`, and `UNKNOWN/UNCERTAIN_COMMIT` lanes must be first-class.
4. Add closure gates that demand parity evidence (20/200 monitored run) and replay-safe behavior.
5. Keep plan progressive:
   - phase-by-phase with DoD, plus rolling status with current focus.

### Planned file updates
- Update `docs/model_spec/platform/implementation_maps/action_layer.build_plan.md` with expanded phased DoD map.
- Append post-change outcome entry here and logbook entry.

---

## Entry: 2026-02-07 18:21:46 - AL build plan expansion applied

### Scope completed
Updated:
- `docs/model_spec/platform/implementation_maps/action_layer.build_plan.md`

Replaced prior 3-phase scaffold with an executable 8-phase map:
1. intake contracts + pin validation,
2. semantic idempotency ledger,
3. authz/execution posture gates,
4. executor adapters + retry/uncertain commit semantics,
5. append-only outcome store + IG publish discipline,
6. checkpoint/replay determinism,
7. observability/governance/security,
8. platform integration closure (`4.5` AL scope).

### Why this is correct
- Aligns AL plan directly to platform `4.5` gates while preserving ownership boundaries.
- Makes uncertain commit and anomaly lanes first-class (required for production-safe side effects).
- Converts phase transitions into objective DoD checks suitable for hardened implementation.

### Residual posture
- Planning expansion only; no AL runtime implementation started in this entry.
- Current focus is now explicitly Phase 1 in the AL build plan.

---

## Entry: 2026-02-07 18:31:23 - Phase 1 lockstep implementation applied (contracts first, then storage foundation)

### Scope executed
Implemented AL Phase 1 contract surfaces and the agreed lockstep storage kickoff.

### Decisions made during implementation
1. Contract authority stays schema-first.
   - Used existing RTDL schemas as contract authority:
     - `action_intent.schema.yaml`
     - `action_outcome.schema.yaml`
2. Keep AL contract validation deterministic and strict.
   - Added explicit field, pin, and enum checks in code; missing/invalid fields fail closed.
3. Pin semantic idempotency identity in code now (used by phase-2 ledger).
   - Added deterministic semantic identity hash from `(platform_run_id, scenario_run_id, idempotency_key)`.
4. Start storage in lockstep without over-advancing execution logic.
   - Implemented durable idempotency ledger primitive (sqlite/postgres-aware) only.
   - Deferred side-effect executor and outcome publish runtime to later phases.

### Files added/updated
- Added:
  - `src/fraud_detection/action_layer/__init__.py`
  - `src/fraud_detection/action_layer/contracts.py`
  - `src/fraud_detection/action_layer/storage.py`
  - `tests/services/action_layer/test_phase1_contracts.py`
  - `tests/services/action_layer/test_phase1_storage.py`
- Updated:
  - `docs/model_spec/platform/implementation_maps/action_layer.build_plan.md` (Phase 1 evidence + status)

### Validation evidence
- Command:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q`
- Result:
  - `14 passed` (includes AL Phase 1 tests and lockstep DLA tests run together).

### DoD mapping status
- Phase 1 (AL contracts/pins): **complete**.
- Storage kickoff delivered in lockstep via ledger foundation; full Phase 2 closure continues next.

---
