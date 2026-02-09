# CaseTrigger Implementation Map
_As of 2026-02-09_

---

## Entry: 2026-02-09 03:49PM - Phase 5.2 planning kickoff (CaseTrigger as explicit component)

### Objective
Create an explicit implementation decision trail for CaseTrigger so trigger production is treated as a first-class service boundary in Phase `5.2`.

### Inputs / authorities
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `5.2`)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/pre-design_decisions/case_and_labels.pre-design_decision.md`
- `docs/model_spec/platform/platform-wide/v0_environment_resource_tooling_map.md`
- `docs/model_spec/platform/component-specific/case_mgmt.design-authority.md`

### Decisions captured
- Adopt explicit CaseTrigger service posture (preferred Option A from pre-design decisions).
- Keep CM opaque by feeding only CaseTrigger events (not direct multi-stream source parsing inside CM).
- Preserve by-ref evidence discipline and deterministic id recipes from Phase `5.1` contracts.
- Keep v0 no-merge case policy in downstream integration gates.

### Planned implementation threads
1. Contract + taxonomy alignment for trigger source mapping.
2. Source adapter and eligibility gate implementation.
3. Deterministic publish boundary with replay-safe retries/checkpoints.
4. CM integration and parity closure evidence.

### Invariants to enforce
- ContextPins and CaseSubjectKey are mandatory for all published triggers.
- Trigger identities remain stable across retries and replay.
- Collision semantics are fail-closed (never silent replace).
- Trigger lane remains low-volume control/governance posture (no hot-path payload mirroring).

## Entry: 2026-02-09 03:50PM - Pre-change lock for Phase 1 implementation (contract + taxonomy)

### Problem / goal
Close CaseTrigger Phase 1 by implementing:
- a dedicated CaseTrigger runtime contract validator for writer-side gating,
- taxonomy guards for trigger/source compatibility,
- a versioned trigger policy loader with deterministic digest.

### Planned files
- New package:
  - `src/fraud_detection/case_trigger/__init__.py`
  - `src/fraud_detection/case_trigger/contracts.py`
  - `src/fraud_detection/case_trigger/taxonomy.py`
  - `src/fraud_detection/case_trigger/config.py`
- New config:
  - `config/platform/case_trigger/trigger_policy_v0.yaml`
- New tests:
  - `tests/services/case_trigger/test_phase1_taxonomy.py`
  - `tests/services/case_trigger/test_phase1_config.py`
  - `tests/services/case_trigger/test_phase1_contracts.py`

### Implementation choices
- Reuse `CaseTrigger` shape validation from `fraud_detection.case_mgmt.contracts` to avoid duplicate contract drift.
- Add CaseTrigger writer-side contract that enforces:
  - trigger type support,
  - allowed source class per trigger type,
  - required evidence ref presence by trigger mapping policy.
- Policy digest canonicalization mirrors other platform components (`json.dumps(..., sort_keys=True)` + SHA-256).

### Validation plan
- `python -m pytest -q tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py`
- compile check for new package modules.

## Entry: 2026-02-09 03:53PM - Resume lock after interruption; Phase 1 execution plan finalized

### Trigger
- User directed: proceed with CaseTrigger Phase 1 implementation now.
- Previous turn was interrupted; state was re-verified before edits.

### Verification summary before coding
- Existing contract authority is already present in `docs/model_spec/platform/contracts/case_and_labels/case_trigger.schema.yaml`.
- Existing runtime contract authority for identity/payload hashing is present in `src/fraud_detection/case_mgmt/contracts.py` and `src/fraud_detection/case_mgmt/ids.py`.
- Existing taxonomy/config patterns to mirror were confirmed in:
  - `src/fraud_detection/context_store_flow_binding/taxonomy.py`
  - `src/fraud_detection/decision_fabric/config.py`

### Finalized implementation decision
- Implement a dedicated `case_trigger` package with three explicit boundaries:
  1. `taxonomy.py`: trigger-source compatibility + required evidence-ref policy (versioned constants, fail-closed checks).
  2. `config.py`: versioned trigger policy loader with deterministic `content_digest`.
  3. `contracts.py`: writer-side validator that reuses `CaseTrigger` structural validation from CM, then enforces CaseTrigger-specific source/taxonomy/policy checks.
- Keep identity and payload-hash rules inherited from CM contract surfaces to avoid drift.
- Add `config/platform/case_trigger/trigger_policy_v0.yaml` to pin v0 source/evidence policy.
- Add targeted Phase 1 tests for taxonomy/config/contracts, then run pytest + py_compile.

### Invariants locked for this pass
- No implicit source coercion: unsupported source class or trigger/source mismatch fails closed.
- Required evidence refs are enforced deterministically per trigger type.
- Contract/policy digest is stable under reload and order-insensitive map/list canonicalization.
- No publish runtime logic in Phase 1; this pass is contract/taxonomy/config only.

## Entry: 2026-02-09 03:56PM - Phase 1 implemented and validated (contract + taxonomy lock)

### Implementation completed
1. New CaseTrigger runtime package:
- `src/fraud_detection/case_trigger/__init__.py`
- `src/fraud_detection/case_trigger/taxonomy.py`
- `src/fraud_detection/case_trigger/config.py`
- `src/fraud_detection/case_trigger/contracts.py`

2. New versioned policy config:
- `config/platform/case_trigger/trigger_policy_v0.yaml`

3. New targeted validation suite:
- `tests/services/case_trigger/test_phase1_taxonomy.py`
- `tests/services/case_trigger/test_phase1_config.py`
- `tests/services/case_trigger/test_phase1_contracts.py`

### Design and reasoning notes captured during implementation
- Taxonomy explicitly pins the v0 trigger-source compatibility matrix:
  - `DECISION_ESCALATION <- DF_DECISION`
  - `ACTION_FAILURE <- AL_OUTCOME`
  - `ANOMALY <- DLA_AUDIT`
  - `EXTERNAL_SIGNAL <- EXTERNAL_SIGNAL`
  - `MANUAL_ASSERTION <- MANUAL_ASSERTION`
- Required evidence-ref families are pinned per trigger type and fail closed when missing.
- Writer-side contract path intentionally reuses `case_mgmt.CaseTrigger` for structural + deterministic id/payload checks, then layers CaseTrigger service policy/taxonomy checks on top. This prevents CM/CaseTrigger drift.
- Policy loader computes deterministic `content_digest` over canonicalized JSON payload for revision provenance.
- Policy completeness check requires all supported trigger types to be declared in config.

### Validation evidence
- `python -m py_compile src/fraud_detection/case_trigger/__init__.py src/fraud_detection/case_trigger/taxonomy.py src/fraud_detection/case_trigger/config.py src/fraud_detection/case_trigger/contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py`
  - result: pass
- `python -m pytest -q tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py`
  - result: `9 passed`

### Phase closure statement
- CaseTrigger Phase 1 DoD is satisfied:
  - trigger vocabulary + source mapping pinned and versioned,
  - writer-side runtime contract aligns with schema/identity pins,
  - config/policy loader and tests provide deterministic contract posture for next phases.

## Entry: 2026-02-09 03:58PM - Phase 1 hardening addendum (policy evidence-ref vocab guard)

### Why this addendum was needed
- After initial Phase 1 closure, a gap was identified: `config.py` accepted arbitrary `required_evidence_ref_types` tokens in policy files.
- This could allow silent policy drift away from the controlled evidence-ref vocabulary.

### Change applied
- `src/fraud_detection/case_trigger/config.py` now validates each configured `required_evidence_ref_type` against supported CM evidence ref vocabulary.
- Added regression test in `tests/services/case_trigger/test_phase1_config.py` to fail policy load on unknown evidence-ref token.

### Validation evidence
- `python -m py_compile src/fraud_detection/case_trigger/config.py tests/services/case_trigger/test_phase1_config.py` -> pass.
- `python -m pytest -q tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py` -> `10 passed`.

### Updated closure posture
- Phase 1 remains closed with strengthened config guardrails and updated evidence count (`10 passed`).

## Entry: 2026-02-09 04:00PM - Pre-change lock for Phase 2 (source adapters + eligibility gates)

### Objective
Close CaseTrigger Phase 2 by adding explicit adapter boundaries for `DF`/`AL`/`DLA`/`external`/`manual` sources, with fail-closed source eligibility.

### Inputs / authorities used now
- `docs/model_spec/platform/implementation_maps/case_trigger.build_plan.md` (Phase 2 DoD)
- `src/fraud_detection/decision_fabric/contracts.py` (`DecisionResponse` contract)
- `src/fraud_detection/action_layer/contracts.py` (`ActionOutcome` contract)
- `src/fraud_detection/decision_log_audit/contracts.py` (`AuditRecord` contract)
- Existing CaseTrigger Phase 1 modules in `src/fraud_detection/case_trigger/`

### Key design decisions before implementation
1. Add a new adapter module (`src/fraud_detection/case_trigger/adapters.py`) as the single source adapter boundary for Phase 2.
2. Reuse existing source contract validators (`DecisionResponse`, `ActionOutcome`, `AuditRecord`) inside adapters so source shape checks are inherited from owning components.
3. Build minimal by-ref CaseTrigger payloads only:
   - no source payload mirroring,
   - refs + controlled metadata only.
4. Enforce fail-closed gating:
   - unsupported source class rejected,
   - AL `ACTION_FAILURE` adapter accepts only non-success outcomes (`FAILED`/`DENIED`),
   - required additional refs (`audit_record_id`, `source_event_id`) required where source payload cannot provide them.

### Planned files for this phase
- New code:
  - `src/fraud_detection/case_trigger/adapters.py`
- Update exports:
  - `src/fraud_detection/case_trigger/__init__.py`
- New tests:
  - `tests/services/case_trigger/test_phase2_adapters.py`

### Validation plan
- `python -m pytest -q tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py`
- compile check for updated/new CaseTrigger modules.

## Entry: 2026-02-09 04:03PM - Phase 2 implemented and validated (source adapters + eligibility gates)

### Implementation completed
1. Added explicit source adapter boundary:
- `src/fraud_detection/case_trigger/adapters.py`

2. Updated package exports for adapter surfaces:
- `src/fraud_detection/case_trigger/__init__.py`

3. Added Phase 2 validation suite:
- `tests/services/case_trigger/test_phase2_adapters.py`

### Adapter boundaries delivered
- `DF_DECISION -> DECISION_ESCALATION`
  - source contract validation via `DecisionResponse`.
  - requires explicit `audit_record_id` (fail closed when absent).
- `AL_OUTCOME -> ACTION_FAILURE`
  - source contract validation via `ActionOutcome`.
  - trigger eligibility restricted to `FAILED|DENIED` statuses (EXECUTED rejected).
  - requires explicit `source_event_id` and `audit_record_id` (fail closed when absent).
- `DLA_AUDIT -> ANOMALY`
  - source contract validation via `AuditRecord`.
  - case subject event defaults to `decision_event.event_id` unless overridden.
- `EXTERNAL_SIGNAL -> EXTERNAL_SIGNAL`
  - explicit payload contract requires `external_ref_id/ref_id`, `case_subject_key`, `pins`, `observed_time`.
- `MANUAL_ASSERTION -> MANUAL_ASSERTION`
  - explicit payload contract requires `manual_assertion_id/ref_id`, `case_subject_key`, `pins`, `observed_time`.

### Fail-closed posture implemented
- Unsupported `source_class` values are rejected in dispatcher.
- Source payloads are validated through owning component contracts before mapping.
- Adapter outputs still pass through Phase 1 CaseTrigger writer-side validation (`validate_case_trigger_payload`) with source_class + policy checks.

### By-ref minimal enrichment posture
- Adapter payloads include refs and minimal metadata only (e.g., status/action kind/mode), no source payload mirroring.

### Validation evidence
- `python -m py_compile src/fraud_detection/case_trigger/__init__.py src/fraud_detection/case_trigger/adapters.py src/fraud_detection/case_trigger/taxonomy.py src/fraud_detection/case_trigger/config.py src/fraud_detection/case_trigger/contracts.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py`
  - result: pass
- `python -m pytest -q tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py`
  - result: `18 passed`

### Phase closure statement
- Phase 2 DoD is satisfied for current scope:
  - explicit source adapters exist for DF/AL/DLA/external/manual,
  - unsupported/insufficient source facts fail closed,
  - adapter outputs remain minimal by-ref and contract-validated.

## Entry: 2026-02-09 04:05PM - Pre-change lock for Phase 3 (deterministic identity + collision handling)

### Objective
Close CaseTrigger Phase 3 by adding deterministic replay/collision handling for CaseTrigger identities under at-least-once retries.

### Why additional runtime logic is needed
- Phase 1 already enforces deterministic identity/payload hash at contract parse time.
- Phase 3 requires operational collision behavior: duplicate replay vs same-key/different-payload anomaly handling.
- This requires append-safe registration storage, not only stateless validation.

### Implementation decision
- Add a dedicated CaseTrigger replay ledger module: `src/fraud_detection/case_trigger/replay.py`.
- Ledger semantics:
  - `NEW` on first seen `case_trigger_id`.
  - `REPLAY_MATCH` when same `case_trigger_id` and same canonical payload hash.
  - `PAYLOAD_MISMATCH` when same `case_trigger_id` but different canonical payload hash (collision anomaly, no overwrite).
- Ledger input path validates payload through Phase 1 contract gate (`validate_case_trigger_payload`) before registration; this guarantees deterministic `case_id`/`case_trigger_id` and payload hash rules are enforced before persistence.
- Backends: sqlite + postgres parity (mirroring existing DF/AL replay modules).

### Planned files
- New code:
  - `src/fraud_detection/case_trigger/replay.py`
- Export update:
  - `src/fraud_detection/case_trigger/__init__.py`
- New tests:
  - `tests/services/case_trigger/test_phase3_replay.py`

### Validation plan
- `python -m pytest -q tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py`
- compile check for updated/new modules.

## Entry: 2026-02-09 04:07PM - Phase 3 implemented and validated (deterministic identity + collision handling)

### Implementation completed
1. Added CaseTrigger replay/collision ledger:
- `src/fraud_detection/case_trigger/replay.py`

2. Updated package exports:
- `src/fraud_detection/case_trigger/__init__.py`

3. Added Phase 3 replay validation suite:
- `tests/services/case_trigger/test_phase3_replay.py`

### Runtime mechanics implemented
- Replay ledger registration now validates payload via `validate_case_trigger_payload(...)` before persistence, enforcing deterministic `case_id`/`case_trigger_id` and canonical payload hash posture from Phase 1.
- Registration outcomes:
  - `NEW`: first-seen deterministic `case_trigger_id`.
  - `REPLAY_MATCH`: same `case_trigger_id` + same canonical payload hash.
  - `PAYLOAD_MISMATCH`: same `case_trigger_id` + different canonical payload hash (collision anomaly; overwrite blocked).
- Persistence backends are parity-aligned with existing platform patterns:
  - sqlite backend,
  - postgres backend (dsn-detected).
- Ledger stores append-safe replay/mismatch counters and mismatch evidence rows (`case_trigger_payload_mismatches`) for auditability.

### DoD closure mapping (Phase 3)
- Deterministic identity recipes enforced:
  - by upstream contract parsing in replay registration path.
- Canonical payload hash stability:
  - hash computed from canonicalized validated payload.
- Collision posture:
  - same key with payload drift emits `PAYLOAD_MISMATCH` and preserves stored canonical payload hash (no silent overwrite).

### Validation evidence
- `python -m py_compile src/fraud_detection/case_trigger/__init__.py src/fraud_detection/case_trigger/replay.py src/fraud_detection/case_trigger/adapters.py src/fraud_detection/case_trigger/contracts.py src/fraud_detection/case_trigger/config.py src/fraud_detection/case_trigger/taxonomy.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py`
  - result: pass
- `python -m pytest -q tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py`
  - result: `22 passed`

### Phase closure statement
- Phase 3 DoD is satisfied for current scope with explicit replay/collision behavior and deterministic identity enforcement in runtime registration path.

## Entry: 2026-02-09 04:12PM - Phase 4 pre-change lock (publish corridor + IG onboarding)

### Objective
Implement CaseTrigger Phase 4 publish corridor with explicit outcomes and persisted publish evidence, and pin IG path by policy/profile.

### Implementation decisions locked before edits
1. Add CaseTrigger publish boundary module (`publish.py`) modeled on DF/AL IG push helpers:
   - explicit outcomes: `ADMIT`, `DUPLICATE`, `QUARANTINE`, `AMBIGUOUS`.
   - canonical envelope validation before send.
   - transient retry with bounded backoff.
   - retry exhaustion returns explicit `AMBIGUOUS` record.
2. Add CaseTrigger publish store (`storage.py`) to persist publish outcomes (`NEW`/`DUPLICATE`/`HASH_MISMATCH`) keyed by `case_trigger_id`.
3. Integrate optional persistence from publisher into store so Phase 4 outcomes are not only in-memory return values.
4. Pin IG onboarding for CaseTrigger lane in config + admission profile mapping:
   - class map: `case_trigger` class + event mapping,
   - schema policy: `case_trigger` payload schema path + `v1` version gate,
   - partitioning profile: dedicated `ig.partitioning.v0.case.trigger` route.
5. Add ingestion-gate onboarding test to keep publish path pinned and auditable.

### Planned file edits
- New:
  - `src/fraud_detection/case_trigger/publish.py`
  - `src/fraud_detection/case_trigger/storage.py`
  - `tests/services/case_trigger/test_phase4_publish.py`
  - `tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`
- Update:
  - `src/fraud_detection/case_trigger/__init__.py`
  - `src/fraud_detection/ingestion_gate/admission.py` (`_profile_id_for_class`)
  - `config/platform/ig/class_map_v0.yaml`
  - `config/platform/ig/schema_policy_v0.yaml`
  - `config/platform/ig/partitioning_profiles_v0.yaml`

### Validation plan
- Compile check on new/updated CaseTrigger and IG files.
- Pytest suites:
  - `tests/services/case_trigger/test_phase4_publish.py`
  - `tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`
  - plus existing CaseTrigger Phase1/2/3 suites.

## Entry: 2026-02-09 04:15PM - Phase 4 implemented and validated (publish corridor)

### Implementation completed
1. Added CaseTrigger publish corridor module:
- `src/fraud_detection/case_trigger/publish.py`

2. Added publish outcome persistence module:
- `src/fraud_detection/case_trigger/storage.py`

3. Updated package exports:
- `src/fraud_detection/case_trigger/__init__.py`

4. Pinned IG path for CaseTrigger lane:
- `config/platform/ig/class_map_v0.yaml` (`case_trigger` class + event mapping)
- `config/platform/ig/schema_policy_v0.yaml` (`case_trigger` payload schema + `v1` gate)
- `config/platform/ig/partitioning_profiles_v0.yaml` (`ig.partitioning.v0.case.trigger` -> `fp.bus.case.v1`)
- `src/fraud_detection/ingestion_gate/admission.py` (`_profile_id_for_class` maps `case_trigger` class)

5. Added Phase 4 tests:
- `tests/services/case_trigger/test_phase4_publish.py`
- `tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`

### Publish corridor mechanics delivered
- Publish outcomes are explicit terminal states:
  - `ADMIT`, `DUPLICATE`, `QUARANTINE`, `AMBIGUOUS`.
- Retry exhaustion on transient errors returns explicit `AMBIGUOUS` record (not silent failure).
- Non-retryable 4xx push responses fail closed.
- Envelope is validated against canonical envelope schema before send.
- Envelope builder pins:
  - `event_type=case_trigger`,
  - `schema_version=v1`,
  - `event_id=case_trigger_id`,
  - `ts_utc` canonicalized from trigger `observed_time`.

### Actor attribution + persistence posture
- Publisher enforces auth-token presence by default (`require_auth_token=True`) so writer boundary attribution is not optional.
- Publish records persist actor attribution derived from writer auth token hint (`actor_principal` + `actor_source_type`) in `CaseTriggerPublishStore`.
- Publish store dedupe semantics:
  - same `case_trigger_id` + same publish identity => `DUPLICATE`,
  - same `case_trigger_id` + different publish identity => `HASH_MISMATCH`.

### Validation evidence
- `python -m py_compile src/fraud_detection/case_trigger/__init__.py src/fraud_detection/case_trigger/publish.py src/fraud_detection/case_trigger/storage.py src/fraud_detection/ingestion_gate/admission.py tests/services/case_trigger/test_phase4_publish.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`
  - result: pass
- `python -m pytest -q tests/services/case_trigger/test_phase4_publish.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py`
  - result: `31 passed`

### Phase closure statement
- Phase 4 DoD is satisfied for current scope:
  - publish path is pinned in IG policy/profile,
  - publish outcomes are explicit,
  - publish outcome records are persistable with actor attribution,
  - onboarding drift is test-guarded.

## Entry: 2026-02-09 04:17PM - Pre-change lock for Phase 5 (retry/checkpoint/replay safety)

### Objective
Close CaseTrigger Phase 5 by implementing deterministic checkpoint gating coupled to replay/publish outcomes.

### Problem framing
- Phase 3 provides identity/collision replay ledger.
- Phase 4 provides explicit publish outcomes + persistence.
- A checkpoint progression gate is still missing, so there is no enforced rule that source progression waits for durable publish outcomes.

### Implementation decisions locked before edits
1. Add CaseTrigger checkpoint gate module (`src/fraud_detection/case_trigger/checkpoints.py`) modeled on DF checkpoint semantics.
2. Gate transitions:
   - token issued deterministically from `(source_ref_id, case_trigger_id)`,
   - ledger committed mark required,
   - publish result mark required,
   - checkpoint commit allowed only when publish decision is safe (`ADMIT` or `DUPLICATE`) and not halted.
   - `QUARANTINE`/`AMBIGUOUS` block commit.
3. Keep backend parity:
   - sqlite + postgres support.
4. Add focused tests to prove:
   - checkpoint blocked until ledger+publish are recorded,
   - retry-safe token stability (same source tuple -> same token id),
   - duplicate publish remains committable,
   - ambiguous/quarantine remain blocked.
5. Add a replay-coupled test showing same CaseTrigger payload replay reuses identity and can commit with duplicate-safe publish result.

### Planned files
- New code:
  - `src/fraud_detection/case_trigger/checkpoints.py`
- Update exports:
  - `src/fraud_detection/case_trigger/__init__.py`
- New tests:
  - `tests/services/case_trigger/test_phase5_checkpoints.py`

### Validation plan
- `python -m pytest -q tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py`
- compile checks for new/updated modules.

## Entry: 2026-02-09 04:21PM - Phase 5 implemented and validated (retry/checkpoint/replay safety)

### Implementation completed
1. Added deterministic checkpoint gate module:
- `src/fraud_detection/case_trigger/checkpoints.py`

2. Updated package exports for checkpoint surfaces:
- `src/fraud_detection/case_trigger/__init__.py`

3. Added and hardened Phase 5 checkpoint tests:
- `tests/services/case_trigger/test_phase5_checkpoints.py`

### Gate mechanics delivered
- Deterministic checkpoint token id derived from `sha256(source_ref_id + ":" + case_trigger_id)[:32]`.
- Progression stages are explicit:
  - token issued,
  - ledger committed mark,
  - publish result mark,
  - checkpoint commit.
- Commit is blocked unless:
  - ledger is committed,
  - publish result exists,
  - publish is non-halted and in safe set (`ADMIT`, `DUPLICATE`).
- Block reasons are explicit and persisted by result:
  - `LEDGER_NOT_COMMITTED`,
  - `PUBLISH_NOT_RECORDED`,
  - `PUBLISH_HALTED`,
  - `PUBLISH_QUARANTINED`,
  - `PUBLISH_AMBIGUOUS`,
  - `PUBLISH_DECISION_UNSAFE`.
- Backend parity is maintained with sqlite and postgres stores.

### Implementation decisions during test hardening
- Initial Phase 5 safety test used sqlite `:memory:` locator. Because checkpoint store opens a fresh sqlite connection per operation, `:memory:` created isolated databases per call and would not preserve issued tokens.
- Decision: use file-backed sqlite (`tmp_path / "checkpoint.sqlite"`) in tests to match durable checkpoint semantics and avoid false negatives.
- Expanded publish-safety coverage to assert both quarantine and halt paths independently:
  - `PUBLISH_QUARANTINED` when publish decision is `QUARANTINE` and not halted,
  - `PUBLISH_HALTED` when halted flag is true even with an otherwise safe decision.

### Validation evidence
- `python -m py_compile src/fraud_detection/case_trigger/checkpoints.py src/fraud_detection/case_trigger/__init__.py tests/services/case_trigger/test_phase5_checkpoints.py`
  - result: pass
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`
  - result: `36 passed`

### Phase closure statement
- Phase 5 DoD is satisfied for current scope:
  - retry-safe identity/token behavior is deterministic,
  - checkpoint progression is publish-outcome-gated and fail-closed on unsafe outcomes,
  - replay path preserves trigger identity and checkpoint committability under duplicate-safe publish outcomes.

## Entry: 2026-02-09 04:26PM - Pre-change lock for Phase 6 (CM intake integration gate)

### Objective
Close CaseTrigger Phase 6 by proving the CaseTrigger->CM intake boundary with deterministic case creation and duplicate-safe trigger intake behavior.

### Problem framing
- CaseTrigger phases 1-5 are complete and validated at writer/replay/publish/checkpoint boundaries.
- Integration gate remains open until CM consumes CaseTrigger contract directly and enforces idempotent case creation + deterministic duplicate/no-op behavior under at-least-once delivery.

### Implementation decisions locked before edits
1. Implement explicit CM intake module in `case_mgmt` (authoritative owner), not inside `case_trigger`, to preserve truth ownership boundaries.
2. Intake path must validate input through `CaseTrigger.from_payload(...)` (direct contract consumption; no shadow parser).
3. Case creation idempotency key is `CaseSubjectKey` via deterministic `case_id`; no-merge remains strict for v0.
4. Trigger duplicates are deterministic:
   - same `case_trigger_id` + same payload hash => duplicate/no-op,
   - same `case_trigger_id` + different payload hash => fail-closed anomaly (`PAYLOAD_MISMATCH`).
5. Timeline append semantics:
   - append `CASE_TRIGGERED` once per trigger using deterministic `case_timeline_event_id`,
   - duplicate trigger intake does not append duplicate timeline truth.
6. Keep backend parity (sqlite + postgres) and add regression tests covering:
   - new case + append,
   - same-subject second trigger attaches to existing case,
   - exact duplicate trigger no-op,
   - payload mismatch anomaly.

### Planned files
- New code:
  - `src/fraud_detection/case_mgmt/intake.py`
- Export update:
  - `src/fraud_detection/case_mgmt/__init__.py`
- New tests:
  - `tests/services/case_mgmt/test_phase2_intake.py`
- Status updates after validation:
  - `docs/model_spec/platform/implementation_maps/case_trigger.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/platform.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/case_mgmt.build_plan.md`

### Validation plan
- `python -m py_compile src/fraud_detection/case_mgmt/intake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase2_intake.py`
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`

## Entry: 2026-02-09 04:33PM - Phase 6 implemented and validated (CM intake integration gate)

### What closed
- Implemented and validated the CaseTrigger->CM boundary by adding deterministic CM intake behavior that consumes CaseTrigger contracts directly.

### Delivered artifacts
- `src/fraud_detection/case_mgmt/intake.py`
- `src/fraud_detection/case_mgmt/__init__.py`
- `tests/services/case_mgmt/test_phase2_intake.py`

### Integration behavior now pinned
- CM intake validates trigger payloads through `CaseTrigger.from_payload(...)` (direct contract consumption).
- Case creation remains idempotent on `CaseSubjectKey`/deterministic `case_id`.
- Trigger duplicate semantics are deterministic and explicit:
  - `NEW_TRIGGER` appends one `CASE_TRIGGERED` timeline event.
  - `DUPLICATE_TRIGGER` is no-op on timeline append.
  - `TRIGGER_PAYLOAD_MISMATCH` is fail-closed and no-op on timeline append.
- No-merge posture remains enforced via case subject hash consistency for persisted case identity.

### Validation evidence
- `python -m py_compile src/fraud_detection/case_mgmt/intake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase2_intake.py`
  - result: pass
- `python -m pytest -q tests/services/case_mgmt/test_phase2_intake.py`
  - result: `4 passed`
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py`
  - result: `16 passed`
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py`
  - result: `36 passed`

### Phase closure statement
- Phase 6 DoD is satisfied:
  - CM consumes CaseTrigger contract directly,
  - case creation idempotency holds on CaseSubjectKey,
  - duplicate trigger handling is deterministic (append/no-op) and no-merge is preserved.

## Entry: 2026-02-09 04:36PM - Phase 6 hardening addendum (CM lookup robustness)

### Adjustment
- Added defensive JSON-decode handling in CM intake lookup helper (`_json_to_dict`) so malformed rows do not raise runtime exceptions.

### Validation refresh
- `python -m py_compile src/fraud_detection/case_mgmt/intake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase2_intake.py` -> pass.
- `python -m pytest -q tests/services/case_mgmt/test_phase2_intake.py` -> `4 passed`.
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py` -> `16 passed`.
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py` -> `36 passed`.
