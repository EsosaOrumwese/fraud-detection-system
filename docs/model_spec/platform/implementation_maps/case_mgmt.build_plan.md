# Case Management Build Plan (v0)
_As of 2026-02-09_

## Purpose
Provide an executable, component-scoped plan for Case Management (CM) aligned to platform Phase 5 (`Label & Case`).

## Authorities (binding)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 5 sections `5.1..5.9`)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/case_mgmt.design-authority.md`
- `docs/model_spec/platform/pre-design_decisions/case_and_labels.pre-design_decision.md`
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`

## Planning rules (binding)
- Progressive elaboration only: expand details for active phase while keeping explicit DoD gates.
- No half-baked phase transitions: do not advance without evidence-backed closure.
- Rails are non-negotiable: ContextPins, append-only truth, by-ref evidence, idempotency, fail-closed on incompatibility.

## Component boundary
- CM owns:
  - case identity and append-only timeline truth,
  - workflow projections derived from timeline events,
  - label-intent emission to Label Store and manual-action intent emission to AL.
- CM does not own:
  - label truth storage (LS),
  - side-effect execution truth (AL),
  - audit truth ownership (DLA),
  - traffic admission authority (IG).

## Phase plan (v0)

### Phase 1 — Contracts + identity model lock
**Intent:** pin CaseTrigger/CaseSubject/timeline vocab before service implementation.

**DoD checklist:**
- `CaseSubjectKey=(platform_run_id,event_class,event_id)` and deterministic `case_id` recipe are pinned.
- `CaseTrigger` shape and trigger vocabulary are pinned with required ContextPins and evidence refs.
- Timeline event vocabulary is pinned with deterministic `case_timeline_event_id` recipe.
- Collision posture (same key + different payload) is pinned as anomaly/fail-closed.

### Phase 2 — Trigger intake + idempotent case creation
**Intent:** make CM safe under at-least-once CaseTrigger delivery.

**DoD checklist:**
- Intake validates required pins and references.
- Case creation is idempotent per `CaseSubjectKey`.
- Duplicate triggers append no duplicate truth; no-merge policy is enforced for v0.
- Retry/replay behavior is deterministic.

### Phase 3 — Append-only timeline truth + workflow projection
**Intent:** establish timeline as CM truth and derive workflow state safely.

**DoD checklist:**
- All meaningful state changes are timeline appends with actor attribution and observed time.
- Case header/status is projection-only (no hidden mutable bypass).
- Query surfaces cover case, subject refs, queue state, and time windows.
- Concurrent writer behavior is deterministic and auditable.

#### Phase 3.A — Timeline append API + actor attribution lock
**Intent:** expose explicit append API for non-trigger timeline events and enforce actor/source typing.

**DoD checklist:**
- CM append API accepts `CaseTimelineEvent` payload + `actor_id` + `source_type` + append timestamp.
- Duplicate append (`same id + same payload hash`) is deterministic no-op.
- Payload mismatch on deterministic event id fails closed and is recorded as anomaly evidence.
- Trigger-intake-generated timeline rows are also actor-attributed (`SYSTEM::case_trigger_intake`).

#### Phase 3.B — Projection semantics lock (S2 -> derived header/status)
**Intent:** pin deterministic projection mapping and remove hidden mutable-state dependence.

**DoD checklist:**
- Projection ordering is deterministic: `observed_time ASC`, tie-break `case_timeline_event_id ASC`.
- Header/status/queue flags are computed from timeline events only.
- Projection API returns explicit fields (`status`, `queue_state`, `is_open`, pending flags, `last_activity_observed_time`).
- Projection remains rebuildable from timeline rows alone.

#### Phase 3.C — Query surfaces for refs/state/time
**Intent:** provide investigation-safe lookup interfaces required by Phase 5.3.

**DoD checklist:**
- Query by `case_id` returns timeline + projection.
- Query by linked refs supports `event_id`, `decision_id`, `action_outcome_id`, `audit_record_id`.
- Query supports derived `status`/`queue_state` filters.
- Query supports last-activity time-window filtering.

#### Phase 3.D — Determinism/concurrency validation matrix
**Intent:** prove append-only/concurrent-safe behavior with deterministic projection outputs.

**DoD checklist:**
- Same-event concurrent-style append replay yields deterministic no-op/mismatch outcomes.
- Projection outputs are invariant under duplicate appends.
- Linked-ref queries remain deterministic and auditable across replay order ties.

### Phase 4 — Evidence-by-ref resolution corridor
**Intent:** support investigation context without duplicating payload truth.

**DoD checklist:**
- CM stores refs + minimal metadata only (audit refs, decision refs, outcome refs, EB coordinates).
- Evidence resolution path is gated/audited per platform corridor policy.
- Missing/unresolvable evidence is explicit (`pending/unavailable`) without truth mutation.

### Phase 5 — Label emission handshake to LS
**Intent:** close adjudication loop while preserving LS truth ownership.

**DoD checklist:**
- CM emits LabelAssertions with stable idempotency key and pinned provenance fields.
- CM records `LABEL_PENDING` until LS durable ack.
- LS ack/reject outcomes are appended as timeline events (`LABEL_ACCEPTED`/`LABEL_REJECTED`/retry).
- CM never claims label truth before LS ack.

### Phase 6 — Manual actions via AL boundary
**Intent:** preserve side-effect ownership boundaries during human workflows.

**DoD checklist:**
- CM emits ActionIntents to AL with stable idempotency keys and evidence refs.
- AL outcomes attach to timeline by reference only.
- Failures/denials are represented explicitly without side-effect truth claims in CM.

### Phase 7 — Observability, governance, and reconciliation
**Intent:** make CM operationally diagnosable and audit-ready.

**DoD checklist:**
- Run-scoped counters exist (`case_triggers`, `cases_created`, `timeline_events`, `label_pending/accepted/rejected`).
- Governance events are emitted for required lifecycle points with actor attribution.
- Corridor anomalies are structured and low-noise.
- CM contributes to run reconciliation artifact under case/labels prefix.

### Phase 8 — Integration closure and parity proof
**Intent:** prove CM continuity with RTDL, AL, and LS boundaries.

**DoD checklist:**
- End-to-end proof exists:
  `DLA/AL evidence -> CaseTrigger -> CM timeline -> LabelAssertion submit -> LS ack`.
- Negative-path proof exists (duplicate trigger, hash mismatch, LS unavailable, retry idempotency).
- Monitored local-parity evidence artifacts are captured and referenced in implementation maps/logbook.
- Closure statement is explicit and tied to platform Phase 5 section `5.9`.

## Status (rolling)
- Phase 1 (`Contracts + identity model lock`): completed on `2026-02-09`.
  - Evidence:
    - `src/fraud_detection/case_mgmt/contracts.py`
    - `src/fraud_detection/case_mgmt/ids.py`
    - `docs/model_spec/platform/contracts/case_and_labels/case_trigger.schema.yaml`
    - `docs/model_spec/platform/contracts/case_and_labels/case_timeline_event.schema.yaml`
    - `tests/services/case_mgmt/test_phase1_contracts.py`
    - `tests/services/case_mgmt/test_phase1_ids.py`
  - Validation:
    - `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py` -> `12 passed`
- Phase 2 (`Trigger intake + idempotent case creation`): completed on `2026-02-09`.
  - Evidence:
    - `src/fraud_detection/case_mgmt/intake.py`
    - `src/fraud_detection/case_mgmt/__init__.py`
    - `tests/services/case_mgmt/test_phase2_intake.py`
  - Validation:
    - `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py` -> `16 passed`
- Phase 3 (`Append-only timeline truth + workflow projection`): completed on `2026-02-09`.
  - Evidence:
    - `src/fraud_detection/case_mgmt/intake.py` (append API, actor attribution, projection/query surfaces, linked-ref index)
    - `src/fraud_detection/case_mgmt/__init__.py` (Phase 3 exports)
    - `tests/services/case_mgmt/test_phase3_projection.py`
  - Validation:
    - `python -m pytest -q tests/services/case_mgmt/test_phase3_projection.py` -> `4 passed`
    - `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py` -> `20 passed`
    - `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py` -> `45 passed`
- Phase 4 (`Evidence-by-ref resolution corridor`): completed on `2026-02-09`.
  - Evidence:
    - `src/fraud_detection/case_mgmt/evidence.py`
    - `config/platform/case_mgmt/evidence_resolution_policy_v0.yaml`
    - `src/fraud_detection/case_mgmt/__init__.py` (Phase 4 exports)
    - `tests/services/case_mgmt/test_phase4_evidence_resolution.py`
  - Validation:
    - `python -m pytest -q tests/services/case_mgmt/test_phase4_evidence_resolution.py` -> `4 passed`
    - `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py` -> `24 passed`
    - `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py` -> `45 passed`
- Phase 5 (`Label emission handshake to Label Store`): completed on `2026-02-09`.
  - Evidence:
    - `src/fraud_detection/case_mgmt/label_handshake.py`
    - `config/platform/case_mgmt/label_emission_policy_v0.yaml`
    - `src/fraud_detection/case_mgmt/__init__.py` (Phase 5 exports)
    - `tests/services/case_mgmt/test_phase5_label_handshake.py`
  - Validation:
    - `python -m py_compile src/fraud_detection/case_mgmt/label_handshake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase5_label_handshake.py` -> pass
    - `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py` -> `6 passed`
    - `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py tests/services/case_mgmt/test_phase5_label_handshake.py` -> `30 passed`
    - `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py` -> `45 passed`
- Phase 6 (`Manual actions via AL boundary`): completed on `2026-02-09`.
  - Evidence:
    - `src/fraud_detection/case_mgmt/action_handshake.py`
    - `config/platform/case_mgmt/action_emission_policy_v0.yaml`
    - `src/fraud_detection/case_mgmt/intake.py` (projection semantics for submit statuses and outcome classes)
    - `src/fraud_detection/case_mgmt/__init__.py` (Phase 6 exports)
    - `tests/services/case_mgmt/test_phase6_action_handshake.py`
  - Validation:
    - `python -m py_compile src/fraud_detection/case_mgmt/action_handshake.py src/fraud_detection/case_mgmt/intake.py src/fraud_detection/case_mgmt/__init__.py tests/services/case_mgmt/test_phase6_action_handshake.py` -> pass
    - `python -m pytest -q tests/services/case_mgmt/test_phase6_action_handshake.py` -> `6 passed`
    - `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase6_action_handshake.py` -> `36 passed`
    - `python -m pytest -q tests/services/case_trigger/test_phase1_config.py tests/services/case_trigger/test_phase1_contracts.py tests/services/case_trigger/test_phase1_taxonomy.py tests/services/case_trigger/test_phase2_adapters.py tests/services/case_trigger/test_phase3_replay.py tests/services/case_trigger/test_phase4_publish.py tests/services/case_trigger/test_phase5_checkpoints.py tests/services/case_trigger/test_phase7_observability.py tests/services/case_trigger/test_phase8_validation_matrix.py tests/services/ingestion_gate/test_phase11_case_trigger_onboarding.py` -> `45 passed`
- Next action: Phase 7 implementation (observability, governance, and reconciliation).
