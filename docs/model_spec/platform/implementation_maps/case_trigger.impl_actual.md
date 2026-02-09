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
