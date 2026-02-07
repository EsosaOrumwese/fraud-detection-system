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

## Entry: 2026-02-07 18:35:53 - Phase 2 implementation plan (semantic idempotency ledger)

### Trigger
User asked to proceed with AL Phase 2 specifically.

### Authorities used
- `docs/model_spec/platform/implementation_maps/action_layer.build_plan.md` (Phase 2 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (idempotency + retry semantics)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md` (at-least-once + payload-hash mismatch anomaly posture)
- Existing AL Phase 1 code (`contracts.py`, `storage.py`) and tests.

### Problem framing
Phase 1 validates payload contracts but does not yet expose a dedicated semantic idempotency decision surface that downstream executors can consume directly (`execute`, `drop duplicate`, `quarantine mismatch`) with deterministic reasoning and durable backing.

### Decisions before implementation
1. Add a dedicated AL idempotency gate module instead of embedding policy into tests/runtime call sites.
2. Keep semantic identity deterministic and replay-stable:
   - semantic key derived from run pins + idempotency key.
3. Hash scope for duplicate detection:
   - canonical JSON over normalized ActionIntent execution-relevant fields.
4. Keep durable state run-scoped:
   - introduce/maintain ledger persistence keyed by run scope + semantic identity.
5. Preserve Phase 1 API compatibility:
   - do not break existing `register_intent(...)`; add semantic-ledger path and gate abstraction.

### Planned code/test/doc updates
- Code:
  - `src/fraud_detection/action_layer/idempotency.py` (gate + payload hash policy + dispositions)
  - `src/fraud_detection/action_layer/storage.py` (semantic ledger table + register path)
  - `src/fraud_detection/action_layer/__init__.py` exports
- Tests:
  - `tests/services/action_layer/test_phase2_idempotency.py`
- Docs:
- update AL build-plan status/evidence for Phase 2
- append post-implementation evidence entry here and logbook.

---

## Entry: 2026-02-07 18:37:54 - Phase 2 implementation closure (semantic idempotency ledger)

### What was implemented
1. Added AL idempotency gate surface:
   - `src/fraud_detection/action_layer/idempotency.py`
   - exposes deterministic dispositions:
     - `EXECUTE` (new semantic intent),
     - `DROP_DUPLICATE` (same semantic key + same payload hash),
     - `QUARANTINE` (same semantic key + payload hash mismatch).
2. Added canonical payload-hash policy for ActionIntent execution-relevant fields:
   - `build_action_payload_hash(...)` uses canonical JSON, sorted keys, ASCII-safe encoding.
3. Extended durable storage with semantic ledger table:
   - `src/fraud_detection/action_layer/storage.py`
   - new table `al_semantic_ledger` keyed by `(platform_run_id, scenario_run_id, semantic_key)`.
   - new method `register_semantic_intent(...)` returning `NEW|DUPLICATE|HASH_MISMATCH`.
4. Preserved Phase 1 compatibility:
   - existing `register_intent(...)` path kept unchanged.
5. Exported Phase 2 surfaces:
   - `src/fraud_detection/action_layer/__init__.py`.

### Decisions made during implementation
1. Keep semantic identity derivation in contracts layer:
   - reused `build_semantic_idempotency_key(...)` to avoid duplicate logic drift.
2. Keep mismatch handling explicit and non-destructive:
   - `HASH_MISMATCH` leads to quarantine disposition; no in-place replacement.
3. Make run-scope isolation first-class in storage key:
   - semantic ledger PK includes both run pins and semantic key.
4. Keep this phase limited to idempotency semantics only:
   - no executor or publish behavior added in Phase 2 closure.

### Tests added
- `tests/services/action_layer/test_phase2_idempotency.py`
  - payload-hash sensitivity checks,
  - new -> execute path,
  - duplicate -> drop path,
  - mismatch -> quarantine path,
  - run-scope isolation behavior.

### Validation evidence
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer -q` -> `12 passed`
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q` -> `18 passed`

### DoD mapping outcome
- Semantic execution key deterministic + replay-stable: **complete**.
- Duplicate intent no re-execute path: **complete**.
- Payload mismatch anomaly/quarantine path: **complete**.
- Durable run-scoped idempotency state: **complete**.

---

## Entry: 2026-02-07 18:44:57 - Corrective planning capture for Phase 3 (authz + execution posture)

### Why this corrective entry exists
Phase 3 implementation started immediately after user instruction to proceed, and the pre-implementation decision capture was not written before code edits. This entry records the actual planning decisions to keep the implementation map auditable without rewriting prior entries.

### Authorities used
- `docs/model_spec/platform/implementation_maps/action_layer.build_plan.md` (Phase 3 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (actions semantics + fail-safe posture expectations)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md` (deny/fail-safe before side effects)

### Decisions taken
1. Add explicit AL policy bundle loader under `config/platform/al/policy_v0.yaml` and code loader in `policy.py`.
2. Add a dedicated authorization module (`authz.py`) that:
   - evaluates allow/deny from policy,
   - fails safe when posture is blocked or missing,
   - emits deterministic deny reason codes.
3. Add helper to build immutable `DENIED` outcomes stamped with `authz_policy_rev`.
4. Keep scope bounded to Phase 3:
   - no side-effect executor or retry loop yet (Phase 4+).

---

## Entry: 2026-02-07 18:44:57 - Phase 3 implementation closure (authorization + execution posture gates)

### What was implemented
1. Added AL policy bundle:
   - `config/platform/al/policy_v0.yaml`
2. Added policy loader + posture model:
   - `src/fraud_detection/action_layer/policy.py`
3. Added authorization/posture gate:
   - `src/fraud_detection/action_layer/authz.py`
   - dispositions: `ALLOW` / `DENY`
   - fail-safe behavior on posture block and missing policy bundle.
4. Added immutable denied-outcome helper:
   - `build_denied_outcome_payload(...)` stamped with `authz_policy_rev`.
5. Updated package exports:
   - `src/fraud_detection/action_layer/__init__.py`

### Tests added
- `tests/services/action_layer/test_phase3_policy.py`
- `tests/services/action_layer/test_phase3_authz.py`

### Validation evidence
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer -q` -> `20 passed`
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q` -> `26 passed`

### DoD mapping outcome
- Authz/policy checks run before execution path: **complete** (policy+authz gate module).
- Denied intents produce immutable `DENIED` outcomes with policy reason refs: **complete** (denied payload builder + contract-valid test).
- Missing/invalid execution posture fail-safe (no blind execution): **complete** (`bundle=None`/blocked posture -> deny fail-safe).
- Policy revision stamps captured on outcomes: **complete** (`authz_policy_rev` derived from policy bundle and asserted in tests).

---

## Entry: 2026-02-07 18:47:45 - Phase 4 implementation plan (executor adapters + retry/failure semantics)

### Trigger
User requested to proceed to AL Phase 4.

### Authorities used
- `docs/model_spec/platform/implementation_maps/action_layer.build_plan.md` (Phase 4 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (retry posture + terminal failure semantics)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md` (idempotent side-effect execution and explicit outcome truth)

### Problem framing
AL has contracts, idempotency, and authz posture checks, but no execution adapter/retry engine yet. Phase 4 requires explicit, bounded retry behavior, terminal failure taxonomy, and an explicit uncertain-commit lane that remains replay-safe.

### Decisions before implementation
1. Add a dedicated execution module (`execution.py`) rather than embedding retry logic in authz/idempotency modules.
2. Keep retry policy deterministic and bounded:
   - explicit `max_attempts`, `base_backoff_ms`, and `max_backoff_ms`.
3. Keep uncertain commit explicit even with current outcome schema:
   - use terminal class `UNCERTAIN_COMMIT` and emit immutable `FAILED` outcome with explicit reason code.
4. Preserve side-effect idempotency expectations:
   - executor request carries a stable idempotency token derived from semantic identity.
5. Keep this phase scoped to execution semantics only:
   - no IG publish flow yet (Phase 5).

### Planned file/test updates
- Add:
  - `src/fraud_detection/action_layer/execution.py`
  - `tests/services/action_layer/test_phase4_execution.py`
- Update:
  - `src/fraud_detection/action_layer/__init__.py` exports
  - `docs/model_spec/platform/implementation_maps/action_layer.build_plan.md` (Phase 4 evidence/status)
- implementation/logbook closure entries after validation.

---

## Entry: 2026-02-07 18:50:08 - Phase 4 implementation closure (executor adapters + retry/failure semantics)

### What was implemented
1. Added retry/execution engine module:
   - `src/fraud_detection/action_layer/execution.py`
   - includes:
     - explicit external execution result states (`COMMITTED`, `RETRYABLE_ERROR`, `PERMANENT_ERROR`, `UNKNOWN_COMMIT`),
     - bounded retry engine with deterministic terminal outcomes,
     - explicit terminal lane for uncertain commit (`UNCERTAIN_COMMIT`),
     - execution outcome payload builder producing immutable ActionOutcome payloads.
2. Extended AL policy bundle for retry controls:
   - `src/fraud_detection/action_layer/policy.py`
   - added `AlRetryPolicy` parsing and validation.
   - policy now carries `retry_policy` in `AlPolicyBundle`.
3. Updated AL policy config:
   - `config/platform/al/policy_v0.yaml`
   - added `retry.max_attempts`, `retry.base_backoff_ms`, `retry.max_backoff_ms`.
4. Updated exports:
   - `src/fraud_detection/action_layer/__init__.py`.

### Decisions made during implementation
1. Keep uncertain commit explicit without breaking current outcome schema:
   - represent uncertain terminal as `terminal_state=UNCERTAIN_COMMIT` in `outcome_payload`,
   - publish contract status remains schema-compatible (`FAILED`) with explicit reason code `UNCERTAIN_COMMIT:*`.
2. Ensure retry path is side-effect safe:
   - executor request carries stable `idempotency_token=semantic_key` on every retry attempt.
3. Keep retry policy configurable from policy bundle:
   - avoids hardcoded backoff/attempt behavior and keeps phase behavior auditable by revision.

### Tests added/updated
- Added:
  - `tests/services/action_layer/test_phase4_execution.py`
- Updated:
  - `tests/services/action_layer/test_phase3_policy.py` (retry policy assertion)
  - `tests/services/action_layer/test_phase3_authz.py` (bundle constructor update for new retry field)

### Validation evidence
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer -q` -> `24 passed`
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q` -> `30 passed`

### DoD mapping outcome
- Bounded retries with explicit terminal behavior: **complete**.
- Final failure emits immutable `FAILED` outcome with stable reason taxonomy: **complete**.
- Uncertain commit lane explicit and replay-safe: **complete** (`terminal_state=UNCERTAIN_COMMIT`, deterministic payload identity).
- Retry requests preserve stable idempotency token to prevent duplicate external effects: **complete**.

---

## Entry: 2026-02-07 18:59:55 - Phase 4 hardening plan (enforced retry pacing)

### Trigger
User requested explicit hardening of AL Phase 4 and detailed decision logging.

### Problem framing
Current Phase 4 engine computes bounded retry backoff schedule but does not enforce wait/pacing between retryable attempts. This can produce tight-loop retry storms under provider faults and does not reflect realistic execution posture expected in dev/prod.

### Decision thread (before coding)
1. Enforce retry pacing inside `ActionExecutionEngine` rather than delegating pacing to external caller.
   - Reasoning: pacing is part of execution safety semantics and should be guaranteed by component logic, not optional orchestration behavior.
2. Keep pacing test-safe via injectable sleeper.
   - Reasoning: production should sleep; tests must remain fast and deterministic.
3. Preserve deterministic bounded schedule as policy authority.
   - Reasoning: no unbounded retry; no random jitter introduction in this hardening pass to avoid changing replay determinism and existing policy contract.
4. Keep uncertain-commit semantics unchanged.
   - Reasoning: this hardening is retry pacing only; terminal taxonomy remains the same.

### Planned file changes
- `src/fraud_detection/action_layer/execution.py`
  - add enforced sleep between retryable attempts using policy-derived backoff.
  - add injectable sleeper callable with safe default.
- `tests/services/action_layer/test_phase4_execution.py`
  - add assertions that sleep is called with expected delays on retry path.
  - add assertion that no sleep occurs on immediate terminal paths.
- `docs/model_spec/platform/implementation_maps/action_layer.build_plan.md`
  - optionally pin explicit note that backoff is now enforced, not only computed.

### Validation plan
- Run `python -m pytest tests/services/action_layer -q`.
- Confirm all Phase 4 tests pass with new pacing semantics.

---

## Entry: 2026-02-07 19:00:00 - Phase 4 hardening closure (enforced retry pacing)

### What changed
1. Hardened retry loop to enforce pacing between retryable attempts:
   - `src/fraud_detection/action_layer/execution.py`
   - `ActionExecutionEngine` now applies policy-derived delay via injectable `sleeper` before next retry attempt.
2. Refined backoff calculation surface:
   - added `backoff_for_attempt_ms(attempt_seq)` to keep delay derivation explicit and validated.
   - `backoff_schedule_ms()` now delegates to the same function to avoid divergence.
3. Strengthened tests:
   - `tests/services/action_layer/test_phase4_execution.py`
   - added `SleepRecorder` and assertions proving:
     - retries invoke expected delays (`0.1s`, `0.2s` for current policy),
     - terminal lanes on first attempt do not sleep.

### Decisions made during implementation (with reasoning)
1. **Inject sleeper as a dependency (`Callable[[float], None]`)**
   - Reasoning: production behavior should enforce pacing, while tests must remain deterministic and fast.
2. **No jitter in this hardening pass**
   - Reasoning: preserves current deterministic replay posture and avoids changing policy surface mid-phase; jitter can be introduced as an explicit future decision if required.
3. **Pacing applies only on retry transitions**
   - Reasoning: terminal outcomes (`COMMITTED`, `PERMANENT_ERROR`, `UNKNOWN_COMMIT`) should complete immediately without extra delay.

### Validation evidence
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer -q` -> `24 passed`.

### DoD impact
- Phase 4 DoD item "bounded retry + backoff" is now **enforced** (not just computed/surfaced).
- Remaining Phase 4 DoD items unchanged and still satisfied:
  - stable terminal taxonomy,
  - explicit uncertain-commit lane,
  - stable idempotency token per retry attempt.

---

## Entry: 2026-02-07 19:04:22 - Phase 5 pre-implementation plan (outcome append + IG publish discipline)

### Trigger
User requested to proceed with AL Phase 5.

### Authorities used
- `docs/model_spec/platform/implementation_maps/action_layer.build_plan.md` (Phase 5 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (admission via IG, deterministic publish posture)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md` (DF/AL through IG to EB, provenance-first)
- `docs/model_spec/platform/contracts/real_time_decision_loop/action_outcome.schema.yaml`

### Problem framing
AL currently has contracts, idempotency, authz, and execution semantics, but does not yet provide:
1. durable append-only outcome store,
2. deterministic IG publish boundary for `action_outcome`,
3. persisted receipt/evidence linkage for reconciliation.

### Design decisions before coding
1. Add dedicated `ActionOutcomeStore` under `action_layer.storage`.
   - Reasoning: append-only outcome truth and publish evidence need durable state with backend parity (sqlite/postgres), analogous to DLA/DF stores.
2. Use `outcome_id` as canonical AL outcome event identity.
   - Reasoning: it is deterministic, contract-validated (`hex32`), and already tied to execution terminal identity.
3. Publish to IG through a dedicated AL publisher module (`action_layer.publish`) with explicit decision taxonomy:
   - `ADMIT`, `DUPLICATE`, `QUARANTINE`, `AMBIGUOUS`.
   - Reasoning: AL Phase 5 DoD explicitly includes ambiguous handling; IG may return quarantine for server-side ambiguity, while client-side timeout/network ambiguity must still be represented deterministically.
4. Keep fail-closed response handling:
   - unknown IG decision or malformed response => deterministic publish error.
5. Keep Phase 5 scope bounded:
   - implement append+publish+evidence persistence surfaces and tests,
   - do not implement checkpoint/replay cursor progression yet (Phase 6).

### Planned file changes
- `src/fraud_detection/action_layer/storage.py`
  - add append-only outcome row model and write API with hash-mismatch protection.
  - add publish evidence persistence API keyed by `outcome_id`.
- `src/fraud_detection/action_layer/publish.py` (new)
  - add IG publish client for action outcomes with bounded retry and explicit ambiguous mapping.
  - add canonical envelope builder for `event_type=action_outcome` + `schema_version=v1`.
- `src/fraud_detection/action_layer/__init__.py`
  - export new Phase 5 surfaces.
- `tests/services/action_layer/test_phase5_outcomes.py` (new)
  - append-only behavior + hash mismatch.
  - IG publish decisions (admit/duplicate/quarantine/ambiguous).
  - receipt/evidence persistence.
- Config/IG policy alignment (if missing):
  - `config/platform/ig/schema_policy_v0.yaml`
  - `config/platform/ig/class_map_v0.yaml`
  - `config/platform/ig/partitioning_profiles_v0.yaml`

### Validation plan
- `python -m pytest tests/services/action_layer -q`
- If IG config changed, run targeted IG/DF tests for schema/policy compatibility as needed.

---

## Entry: 2026-02-07 19:09:44 - Phase 5 implementation closure (outcome store + IG publish discipline)

### What was implemented
1. Added append-only outcome store with hash-guarded immutability:
   - `src/fraud_detection/action_layer/storage.py`
   - introduced `ActionOutcomeStore` with:
     - `register_outcome(...)` -> `NEW|DUPLICATE|HASH_MISMATCH` using canonical payload hash,
     - `register_publish_result(...)` -> deterministic publish evidence persistence keyed by `outcome_id`.
2. Added AL -> IG publish boundary module:
   - `src/fraud_detection/action_layer/publish.py`
   - introduced:
     - `build_action_outcome_envelope(...)` (canonical envelope for `event_type=action_outcome`, `schema_version=v1`, stable `event_id=outcome_id`),
     - `ActionLayerIgPublisher.publish_envelope(...)` with bounded retry and deterministic decisions,
     - publish taxonomy: `ADMIT | DUPLICATE | QUARANTINE | AMBIGUOUS`.
3. Exported Phase 5 surfaces:
   - `src/fraud_detection/action_layer/__init__.py`.
4. Aligned IG policy/routing for AL outcome family:
   - `config/platform/ig/schema_policy_v0.yaml` -> add `action_outcome` payload schema policy.
   - `config/platform/ig/class_map_v0.yaml` -> add `rtdl_action_outcome` class + event map.
   - `config/platform/ig/partitioning_profiles_v0.yaml` -> add `ig.partitioning.v0.rtdl.action_outcome` profile.
   - `src/fraud_detection/ingestion_gate/admission.py` -> class-to-profile mapping for `rtdl_action_outcome`.
5. Prevented RTDL projector drift on shared traffic stream:
   - `src/fraud_detection/online_feature_plane/projector.py` -> `action_outcome` added to ignored non-apply families.
   - `config/platform/ieg/classification_v0.yaml` -> `action_outcome` added to `graph_irrelevant`.

### Decisions made during implementation (with reasoning)
1. **Canonical AL publish identity uses `outcome_id` as envelope `event_id`.**
   - Reasoning: `outcome_id` is already deterministic and contract-pinned for immutable outcome truth.
2. **Ambiguity is represented explicitly at publisher boundary.**
   - Reasoning: IG response enum remains `ADMIT|DUPLICATE|QUARANTINE`; network/timeouts/retry exhaustion are represented as `AMBIGUOUS` in AL publish evidence so replay/reconciliation can distinguish transport ambiguity from IG quarantine.
3. **Outcome append and publish evidence are both hash-guarded.**
   - Reasoning: protects append-only truth from silent overwrite under retries or accidental shape drift.
4. **`action_outcome` routed on shared RTDL traffic stream in parity and explicitly ignored/irrelevant by OFP/IEG.**
   - Reasoning: preserves current shared-stream topology while preventing projector apply-failure drift.

### Tests added/updated
- Added:
  - `tests/services/action_layer/test_phase5_outcomes.py`
- Updated:
  - `tests/services/online_feature_plane/test_phase2_projector.py` (non-apply families include `action_outcome`)
  - `tests/services/identity_entity_graph/test_projector_determinism.py` (RTDL output irrelevance includes `action_outcome`)

### Validation evidence
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/online_feature_plane/test_phase2_projector.py tests/services/identity_entity_graph/test_projector_determinism.py -q` -> `45 passed`.

### DoD mapping outcome
- Outcome records append-only with stable identity: **complete** (`ActionOutcomeStore.register_outcome`).
- Publish path through IG with stable event identity: **complete** (`ActionLayerIgPublisher` + `event_id=outcome_id`).
- Publish decisions include admit/duplicate/quarantine/ambiguous deterministically: **complete**.
- Receipt/evidence refs persisted for reconciliation: **complete** (`register_publish_result`).

---

## Entry: 2026-02-07 19:11:52 - Phase 6 pre-implementation plan (checkpoints + replay determinism)

### Trigger
User requested to proceed to AL Phase 6.

### Authorities used
- `docs/model_spec/platform/implementation_maps/action_layer.build_plan.md` (Phase 6 DoD)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md` (at-least-once + idempotent side effects)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md` (deterministic replay and provenance)

### Problem framing
Phase 5 established append-only outcomes and IG publish discipline, but AL still lacks a commit gate that binds checkpoint advancement to durable append+publish completion, and lacks an explicit replay ledger for deterministic mismatch detection under restart/replay pressure.

### Design decisions before coding
1. Add explicit AL checkpoint gate module (`action_layer/checkpoints.py`) with durable token state.
   - Reasoning: commit gating must be first-class and auditable, not inferred from ad-hoc state checks.
2. Gate checkpoint commit on two prerequisites:
   - outcome append committed,
   - publish decision recorded and terminal.
   - Reasoning: aligns with DoD requirement that checkpoint advances only after append/publish gate.
3. Treat `AMBIGUOUS` publish as non-committable.
   - Reasoning: ambiguity means admission outcome is unknown; advancing checkpoint would risk dropping work.
4. Add replay ledger module (`action_layer/replay.py`) keyed by `outcome_id` + payload hash.
   - Reasoning: enables deterministic replay classification (`NEW|REPLAY_MATCH|PAYLOAD_MISMATCH`) and explicit drift evidence.
5. Keep backend parity (`sqlite` + `postgres`) for new stores.
   - Reasoning: local-parity and env-ladder behavior must remain consistent.

### Planned file/test updates
- Add:
  - `src/fraud_detection/action_layer/checkpoints.py`
  - `src/fraud_detection/action_layer/replay.py`
  - `tests/services/action_layer/test_phase6_checkpoints.py`
  - `tests/services/action_layer/test_phase6_replay.py`
- Update:
  - `src/fraud_detection/action_layer/__init__.py` (exports)

### Validation plan
- Run `python -m pytest tests/services/action_layer -q`.
- Ensure explicit coverage for:
  - commit blocked until append+publish gates,
  - ambiguous publish blocks checkpoint,
  - duplicate-storm replay stability,
  - restart/reopen safety on persisted stores.

---

## Entry: 2026-02-07 19:11:52 - Phase 6 implementation closure (checkpoints + replay determinism)

### What was implemented
1. Added explicit AL checkpoint commit gate:
   - `src/fraud_detection/action_layer/checkpoints.py`
   - introduced:
     - `ActionCheckpointGate` with deterministic token issuance,
     - prerequisite markers `mark_outcome_appended(...)` and `mark_publish_result(...)`,
     - `commit_checkpoint(...)` returning `COMMITTED` or `BLOCKED` with machine-readable reasons.
2. Added AL replay ledger:
   - `src/fraud_detection/action_layer/replay.py`
   - introduced:
     - `ActionOutcomeReplayLedger` with outcomes `NEW|REPLAY_MATCH|PAYLOAD_MISMATCH`,
     - mismatch evidence table,
     - deterministic `identity_chain_hash()` over persisted outcome identities.
3. Backend parity for new Phase 6 stores:
   - both modules support sqlite and postgres through backend-aware stores.
4. Exported Phase 6 surfaces:
   - `src/fraud_detection/action_layer/__init__.py`.

### Decisions made during implementation (with reasoning)
1. **Checkpoint commit remains blocked for `PUBLISH_AMBIGUOUS`.**
   - Reasoning: publish ambiguity means downstream admission truth is unknown; committing checkpoint would risk skipping unresolved work.
2. **Checkpoint token identity binds `outcome_id + action_id + decision_id`.**
   - Reasoning: keeps token deterministic and tied to immutable AL execution identity.
3. **Replay ledger key is `outcome_id` with payload-hash drift detection.**
   - Reasoning: `outcome_id` is the stable AL identity; hash mismatch indicates deterministic replay drift and must be captured as evidence, never overwritten.
4. **Identity chain hash derived from persisted `(outcome_id, payload_hash)` ordered set.**
   - Reasoning: provides fast deterministic parity proof across restarts/replays.

### Tests added
- `tests/services/action_layer/test_phase6_checkpoints.py`
  - commit blocked until append+publish complete,
  - ambiguous publish blocks commit,
  - restart/reopen idempotent commit behavior.
- `tests/services/action_layer/test_phase6_replay.py`
  - new/match/mismatch replay classification,
  - duplicate storm replay stability,
  - restart-preserved identity chain hash.

### Validation evidence
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer/test_phase6_checkpoints.py tests/services/action_layer/test_phase6_replay.py -q` -> `6 passed`.
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer -q` -> `37 passed`.

### DoD mapping outcome
- Checkpoint advances only after durable append/publish gate: **complete**.
- Replay from same basis reproduces identical outcome identity chain: **complete**.
- Duplicate storm does not cause replay drift/mismatch: **complete**.
- Crash/restart recovery preserves checkpoint/replay state without mutation: **complete**.

---

## Entry: 2026-02-07 19:24:40 - Phase 7 pre-implementation plan (observability + governance + security)

### Trigger
User requested AL Phase 7 execution and explicit DoD closure.

### Authorities used
- docs/model_spec/platform/implementation_maps/action_layer.build_plan.md (Phase 7 DoD)
- docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md (explicit degrade posture + provenance)
- docs/model_spec/platform/component-specific/flow-narrative-platform-design.md (decision/outcome provenance continuity)
- docs/model_spec/platform/implementation_maps/platform.build_plan.md (Phase 4.5 AL/DLA expectations)

### Problem framing
AL has deterministic execution/idempotency/publish/replay surfaces (Phases 1-6), but still lacks a dedicated operability layer that:
1. exposes run-scoped metrics/health posture for operations,
2. enforces governance stamps uniformly across denied and executed outcomes,
3. redacts sensitive token/credential fields from exported observability artifacts.

### Design decisions before coding
1. Add a dedicated AL observability module (ction_layer/observability.py) with two explicit surfaces:
   - run-scoped metrics collector,
   - health evaluator with explicit GREEN|AMBER|RED + reason codes.
   - Reasoning: keep observability logic out of execution control paths while still making posture auditable.
2. Require governance stamps in execution outcomes (not only denied outcomes).
   - Reasoning: Phase 7 requires policy_rev, xecution_profile_ref, and actor attribution on all outcome families.
3. Add deterministic sensitive-field redaction for exported payload snapshots.
   - Reasoning: Phase 7 security DoD requires that credentials/tokens are never emitted in artifacts/logs.
4. Keep health posture inputs explicit and caller-supplied (lag_events, queue_depth, rror_count/vents_seen) with policy thresholds.
   - Reasoning: avoids hidden coupling to a specific runtime transport while preserving consistent evaluation semantics across local/dev/prod.
5. Keep schema backward compatibility for existing tests/consumers by adding governance fields in outcome_payload without removing existing fields.

### Planned file changes
- Add src/fraud_detection/action_layer/observability.py
  - counters for intake/attempts/outcome statuses/retries/deny/quarantine/ambiguous,
  - health posture evaluator and JSON export,
  - recursive redaction helper for sensitive keys.
- Update src/fraud_detection/action_layer/execution.py
  - add governance stamp support in uild_execution_outcome_payload.
- Update src/fraud_detection/action_layer/__init__.py
  - export observability/health symbols.
- Add 	ests/services/action_layer/test_phase7_observability.py
  - verify counters + health posture + governance stamping + redaction.

### Validation plan
- python -m pytest tests/services/action_layer/test_phase7_observability.py -q
- python -m pytest tests/services/action_layer -q

---

## Entry: 2026-02-07 19:27:37 - Phase 7 implementation closure (observability + governance + security)

### What was implemented
1. Added Action Layer observability + health surfaces:
   - src/fraud_detection/action_layer/observability.py
   - introduced:
     - ActionLayerRunMetrics (run-scoped counters + sanitized recent-events export),
     - ActionLayerHealthThresholds and ActionLayerHealthStatus,
     - explicit health evaluation over lag/queue/error-rate with reason codes,
     - edact_sensitive_fields(...) recursive sanitizer for sensitive key families.
2. Added governance stamps for execution outcomes:
   - src/fraud_detection/action_layer/execution.py
   - uild_execution_outcome_payload(...) now stamps outcome_payload.governance with:
     - policy_rev,
     - xecution_profile_ref,
     - ctor_principal,
     - origin.
3. Exported new Phase 7 surfaces:
   - src/fraud_detection/action_layer/__init__.py.
4. Added dedicated Phase 7 tests:
   - 	ests/services/action_layer/test_phase7_observability.py
   - coverage includes required metrics lanes, health reason codes, governance stamping, redaction, and run-scope fail-closed checks.

### Decisions made during implementation (with reasoning)
1. **Health posture is signal-driven, not transport-coupled.**
   - Reasoning: health evaluation accepts explicit lag_events and queue_depth inputs so the same semantics work across local/dev/prod regardless of queue implementation details.
2. **Error-rate posture derives from AL-relevant failure lanes.**
   - Reasoning: Phase 7 DoD requires execution/publish anomaly visibility; outcome_failed + publish_quarantine + publish_ambiguous forms a practical, deterministic denominator-based signal.
3. **Governance stamping is enforced on execution outcomes, not only DENIED outcomes.**
   - Reasoning: audit consumers should not branch on terminal lane to discover policy attribution.
4. **Sensitive field protection is recursive and key-marker based.**
   - Reasoning: credentials often appear nested in payloads; recursive key inspection (	oken, secret, pi_key, uthorization, etc.) ensures exports do not leak values.
5. **Observability remains non-control-path.**
   - Reasoning: metrics/health helpers do not alter execution outcomes/checkpoints; they report state and posture only.

### Tests added
- 	ests/services/action_layer/test_phase7_observability.py
  - verifies counters for intake/attempts/retries/statuses/quarantine/ambiguous,
  - verifies AMBER/RED health posture and reason codes,
  - verifies execution outcome governance stamps,
  - verifies sensitive-field redaction in exported artifacts,
  - verifies run-scope mismatch fails closed.

### Validation evidence
- $env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer/test_phase7_observability.py -q -> 5 passed.
- $env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer -q -> 42 passed.

### DoD mapping outcome
- Metrics/logs cover intake, attempts, retries, statuses, denies, quarantines, ambiguous: **complete**.
- Health posture exposes lag/error/queue with reason codes: **complete**.
- Governance/security stamps present in outcome payloads: **complete**.
- Sensitive credentials/tokens excluded from observability exports: **complete**.

---

## Entry: 2026-02-07 19:34:08 - Phase 8 pre-implementation plan (platform integration closure)

### Trigger
User requested to proceed to AL Phase 8.

### Authorities used
- docs/model_spec/platform/implementation_maps/action_layer.build_plan.md (Phase 8 DoD)
- docs/model_spec/platform/implementation_maps/platform.build_plan.md (4.5.I, 4.5.J)
- docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md
- docs/model_spec/platform/component-specific/flow-narrative-platform-design.md

### Problem framing
AL Phases 1-7 are complete, but Phase 8 requires explicit component closure proof with integration-grade evidence:
1. DF decision/intent continuity into AL execution/outcome emission.
2. Local-parity monitored proof at 20 and 200 event scales.
3. Replay/no-duplicate side-effect proof with stable outcome lineage.
4. Explicit closure statement with dependency boundary (DLA remains platform integration peer under 4.5).

### Design decisions before coding
1. Add a dedicated AL Phase 8 validation matrix test module.
   - Reasoning: existing AL tests are phase-sliced; Phase 8 requires integrated end-to-end component proof.
2. Use DF synthesizer outputs as upstream source for ActionIntent continuity checks.
   - Reasoning: validates DF->AL handoff semantics at the contract boundary rather than synthetic AL-only payloads.
3. Keep production policy unchanged; use a test-local AL policy bundle variant to permit DF action families for continuity testing.
   - Reasoning: prevents accidental production policy drift while proving cross-component wiring behavior.
4. Include explicit 20/200 local-parity proof in tests via deterministic component-run harness.
   - Reasoning: matches existing DF Phase 8 closure pattern and creates auditable evidence in CI/local without requiring manual long-running service orchestration.
5. Validate replay/no-duplicate effect safety by injecting duplicate storms and asserting executor call cardinality + replay ledger stability.
   - Reasoning: Phase 8 requires proof that AL does not double-apply side effects under replay.

### Planned file changes
- Add 	ests/services/action_layer/test_phase8_validation_matrix.py with:
  - DF->AL continuity test,
  - 20/200 component local-parity proof,
  - replay/no-duplicate side-effect assertions.
- Update docs/model_spec/platform/implementation_maps/action_layer.build_plan.md status/evidence for Phase 8 closure.
- Append closure evidence to docs/model_spec/platform/implementation_maps/action_layer.impl_actual.md and docs/logbook/02-2026/2026-02-07.md.

### Validation plan
- python -m pytest tests/services/action_layer/test_phase8_validation_matrix.py -q
- python -m pytest tests/services/action_layer -q

---

## Entry: 2026-02-07 19:37:40 - Phase 8 implementation closure (platform integration closure)

### What was implemented
1. Added AL Phase 8 validation matrix:
   - `tests/services/action_layer/test_phase8_validation_matrix.py`
   - includes:
     - DF decision/intent -> AL execution -> ActionOutcome publish continuity proof,
     - component local-parity proof at `20` and `200` events,
     - duplicate-storm no-reexecute assertions,
     - replay-ledger identity-chain stability after restart.
2. Added explicit local-parity operational instructions for AL boundary checks:
   - `docs/runbooks/platform_parity_walkthrough_v0.md` (new Section `19`).
3. Produced parity proof artifacts during validation run:
   - `runs/fraud-platform/platform_20260207T200000Z/action_layer/reconciliation/phase8_parity_proof_20.json`
   - `runs/fraud-platform/platform_20260207T200000Z/action_layer/reconciliation/phase8_parity_proof_200.json`

### Decisions made during implementation (with reasoning)
1. **Use DF synthesizer outputs as upstream integration source.**
   - Reasoning: validates real producer->consumer contract continuity instead of AL-only synthetic payloads.
2. **Keep production AL policy unchanged; allow DF action families via test-local policy bundle only.**
   - Reasoning: avoids production policy drift while still proving Phase 8 integration behavior.
3. **Define local-parity proof at component boundary (not full stack orchestration).**
   - Reasoning: Phase 8 closure here is AL component scope; full platform `4.5` closure still requires DLA integration gates.
4. **Treat duplicate storm as a semantic idempotency gate assertion.**
   - Reasoning: duplicate intents must be dropped before external effect execution; proof uses executor call cardinality.
5. **Replay proof anchored to identity-chain hash stability.**
   - Reasoning: deterministic lineage is required under restart/replay and directly maps to Phase 8 DoD replay clause.

### Validation evidence
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer/test_phase8_validation_matrix.py -q` -> `3 passed`.
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer -q` -> `45 passed`.

### DoD mapping outcome
- Integration tests prove DF decision/intent -> AL execution -> outcome emission continuity: **complete**.
- Local-parity monitored runs exist for 20 and 200 events with AL evidence captured: **complete**.
- Replay validation confirms no duplicate side effects and stable outcome lineage: **complete**.
- Closure statement explicit with remaining dependency boundary (DLA under platform 4.5): **complete**.

---
