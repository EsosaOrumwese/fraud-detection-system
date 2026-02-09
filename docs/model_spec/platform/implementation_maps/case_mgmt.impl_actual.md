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
