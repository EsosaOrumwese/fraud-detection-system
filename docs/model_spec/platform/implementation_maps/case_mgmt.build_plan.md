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
- Next action: Phase 3 implementation (append-only timeline truth + workflow projection).
