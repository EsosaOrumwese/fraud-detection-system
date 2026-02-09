# Case Management Implementation Map
_As of 2026-02-09_

---

## Entry: 2026-02-09 03:26PM - Phase 5 planning kickoff (CM outer contract to executable plan)

### Objective
Start Case Management planning with an explicit, auditable execution map aligned to platform Phase 5 and pinned flow semantics.

### Authorities / inputs
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 5 sections)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/case_mgmt.design-authority.md`
- `docs/model_spec/platform/pre-design_decisions/case_and_labels.pre-design_decision.md`
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`

### Decisions captured (planning posture)
- CM truth ownership remains strict: case objects + append-only timeline only.
- CM intake will be explicit `CaseTrigger` driven in v0; no implicit multi-stream parsing boundary.
- v0 case identity is pinned to `CaseSubjectKey=(platform_run_id,event_class,event_id)` with deterministic `case_id`.
- CM->LS and CM->AL are handshake boundaries only; CM never claims LS or AL truth before downstream durable ack/outcome.
- Collision policy is explicit: same deterministic key + payload mismatch is anomaly/fail-closed, never overwrite.

### Planned implementation sequencing
1. Phase 1 contracts/identity pinning.
2. Trigger intake + idempotent case creation.
3. Timeline truth and derived workflow views.
4. Evidence-by-ref corridor.
5. Label emission handshake to LS.
6. Manual actions through AL.
7. Observability/governance/reconciliation.
8. Integration closure with parity evidence.

### Invariants to enforce
- ContextPins and by-ref evidence are mandatory across all CM boundaries.
- Append-only timeline semantics (no destructive edits).
- Actor attribution is mandatory on timeline and governance surfaces.
- At-least-once safe behavior for all inbound and outbound CM interactions.

## Entry: 2026-02-09 03:30PM - Pre-change lock for Phase 1 implementation (contracts + deterministic IDs)

### Problem / goal
Close CM Phase 1 by implementing concrete contract and identity artifacts that can be reused by later CM phases.

### Decisions locked before code
- CaseSubjectKey remains canonical `(platform_run_id, event_class, event_id)`.
- CaseTrigger shape is explicit and idempotent with stable `case_trigger_id`.
- Timeline event dedupe/identity uses `(case_id, timeline_event_type, source_ref_id)` and deterministic hash ID.
- Collision rule is fail-closed (same dedupe key + different payload hash => anomaly path).

### Planned module set
- `src/fraud_detection/case_mgmt/contracts.py`
- `src/fraud_detection/case_mgmt/ids.py`
- `src/fraud_detection/case_mgmt/__init__.py`
- tests under `tests/services/case_mgmt/` for contracts and identity determinism.

## Entry: 2026-02-09 03:40PM - Phase 1 implemented (CM contracts + deterministic IDs)

### Changes applied
- Added deterministic identity helpers:
  - `src/fraud_detection/case_mgmt/ids.py`
  - recipes pinned for `case_id`, `case_trigger_id`, `case_timeline_event_id`, and canonical payload hashes.
- Added CM contract validators:
  - `src/fraud_detection/case_mgmt/contracts.py`
  - `CaseSubjectKey`, `CaseTrigger`, `CaseTimelineEvent`, `EvidenceRef`, strict pin checks, deterministic-id validation, collision fail-closed checks.
- Added package exports:
  - `src/fraud_detection/case_mgmt/__init__.py`
- Added authoritative schemas:
  - `docs/model_spec/platform/contracts/case_and_labels/case_trigger.schema.yaml`
  - `docs/model_spec/platform/contracts/case_and_labels/case_timeline_event.schema.yaml`
- Added taxonomy pin config:
  - `config/platform/case_mgmt/taxonomy_v0.yaml`
- Added tests:
  - `tests/services/case_mgmt/test_phase1_contracts.py`
  - `tests/services/case_mgmt/test_phase1_ids.py`

### Validation
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py` -> `12 passed`.
- `python -m py_compile src/fraud_detection/case_mgmt/__init__.py src/fraud_detection/case_mgmt/contracts.py src/fraud_detection/case_mgmt/ids.py` -> pass.

### Notes
- Identity and payload-hash recipes are deterministic and stable under evidence-ref ordering differences.
- Contract posture is fail-closed on deterministic key mismatches and payload hash mismatches.

## Entry: 2026-02-09 04:26PM - Pre-change lock for Phase 2 (CaseTrigger intake + idempotent case creation)

### Objective
Implement CM Phase 2 by adding an intake boundary that consumes CaseTrigger contracts directly and enforces idempotent case creation with deterministic duplicate behavior.

### Inputs / authorities
- `docs/model_spec/platform/implementation_maps/case_mgmt.build_plan.md` (Phase 2 DoD)
- `docs/model_spec/platform/implementation_maps/case_trigger.build_plan.md` (Phase 6 CM integration gate)
- `docs/model_spec/platform/component-specific/case_mgmt.design-authority.md`
- `docs/model_spec/platform/pre-design_decisions/case_and_labels.pre-design_decision.md`
- Existing CM contract/identity modules:
  - `src/fraud_detection/case_mgmt/contracts.py`
  - `src/fraud_detection/case_mgmt/ids.py`

### Decisions locked before coding
1. Create `case_mgmt/intake.py` as explicit CM trigger intake service + persistence boundary.
2. Intake must parse/validate incoming triggers using `CaseTrigger.from_payload(...)` to guarantee direct contract conformance.
3. Case create semantics:
   - case identity = deterministic `case_id` from `CaseSubjectKey`,
   - first trigger creates case record,
   - subsequent triggers with same case subject attach to existing case,
   - no-merge policy remains enforced.
4. Trigger replay/collision semantics:
   - same `case_trigger_id` + same payload hash => `DUPLICATE_TRIGGER` (no new timeline append),
   - same `case_trigger_id` + different payload hash => `TRIGGER_PAYLOAD_MISMATCH` fail-closed.
5. Timeline semantics for this phase:
   - append one deterministic `CASE_TRIGGERED` timeline event per new trigger (`source_ref_id=case_trigger_id`),
   - duplicate trigger intake produces no duplicate timeline truth.
6. Backend posture:
   - sqlite and postgres parity in the intake store layer.

### Planned file changes
- New module: `src/fraud_detection/case_mgmt/intake.py`
- Export update: `src/fraud_detection/case_mgmt/__init__.py`
- New tests: `tests/services/case_mgmt/test_phase2_intake.py`

### Validation gate
- Compile checks on new/updated CM files.
- Pytest: CM Phase1+2 plus CaseTrigger Phase1-5 + IG onboarding regression set.

## Entry: 2026-02-09 04:33PM - Phase 2 implemented and validated (CaseTrigger intake + idempotent case creation)

### Implementation completed
1. Added explicit CM intake boundary:
- `src/fraud_detection/case_mgmt/intake.py`

2. Updated package exports:
- `src/fraud_detection/case_mgmt/__init__.py`

3. Added Phase 2 test suite:
- `tests/services/case_mgmt/test_phase2_intake.py`

### Runtime mechanics delivered
- Intake parses incoming payloads through `CaseTrigger.from_payload(...)`; invalid trigger contracts are rejected fail-closed before persistence.
- Case creation is idempotent on deterministic `case_id` (`CaseSubjectKey` identity). Cases are unique per `case_subject_hash`; no-merge posture is enforced.
- Trigger intake ledger outcomes are explicit:
  - `NEW_TRIGGER`
  - `DUPLICATE_TRIGGER`
  - `TRIGGER_PAYLOAD_MISMATCH`
- Collision discipline:
  - same `case_trigger_id` + same payload hash => duplicate/no-op,
  - same `case_trigger_id` + different payload hash => mismatch anomaly, no timeline append.
- Timeline behavior:
  - new triggers append one deterministic `CASE_TRIGGERED` timeline event,
  - duplicate/mismatch triggers do not append duplicate truth (`TIMELINE_NOOP`).

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
- CM Phase 2 DoD is satisfied:
  - trigger intake consumes CaseTrigger contract directly,
  - case creation is idempotent on CaseSubjectKey,
  - duplicate trigger behavior is deterministic and no-merge remains enforced.

## Entry: 2026-02-09 04:36PM - Phase 2 hardening addendum (defensive JSON decode on lookup path)

### Why this addendum was needed
- Post-closure review identified a small robustness gap: lookup helpers in `case_mgmt/intake.py` parsed persisted JSON without guarding decode failures.
- While persisted rows are expected to be valid, defensive handling avoids lookup-path crashes under corrupted/test-fixture rows.

### Change applied
- `src/fraud_detection/case_mgmt/intake.py`
  - `_json_to_dict(...)` now catches `json.JSONDecodeError` and returns `{}` instead of raising.

### Validation evidence
- `python -m py_compile src/fraud_detection/case_mgmt/intake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase2_intake.py` -> pass.
- `python -m pytest -q tests/services/case_mgmt/test_phase2_intake.py` -> `4 passed`.
- `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py` -> `16 passed`.
- `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py` -> `36 passed`.
