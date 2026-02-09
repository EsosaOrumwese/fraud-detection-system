# Label Store Build Plan (v0)
_As of 2026-02-09_

## Purpose
Provide an executable, component-scoped plan for Label Store (LS) aligned to platform Phase 5 (`Label & Case`).

## Authorities (binding)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 5 sections `5.1..5.9`)
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/label_store.design-authority.md`
- `docs/model_spec/platform/pre-design_decisions/case_and_labels.pre-design_decision.md`
- `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`

## Planning rules (binding)
- Progressive elaboration: expand active phase detail, keep objective DoD gates.
- Append-only truth and dual-time semantics are mandatory.
- Fail closed on contract incompatibility, missing pins, and idempotency collisions.
- LS is the sole label truth writer; no bypass lanes for authoritative label state.

## Component boundary
- LS owns:
  - append-only label timelines,
  - label writer boundary validation/idempotency,
  - as-of and timeline query semantics for learning/evaluation.
- LS does not own:
  - case workflow truth (CM),
  - side-effect execution (AL),
  - model training logic (OFS/MF),
  - upstream evidence truth mutation (DLA/EB/Archive).

## Phase plan (v0)

### Phase 1 — LabelAssertion contract + subject model lock
**Intent:** pin non-ambiguous assertion semantics before storage/runtime code.

**DoD checklist:**
- `LabelSubjectKey=(platform_run_id,event_id)` is pinned for v0 primary learning target.
- Controlled `label_type` and value vocabularies are pinned with extension posture.
- Required assertion fields are pinned:
  `label_type`, `label_value`, `effective_time`, `observed_time`, provenance, evidence refs.
- Deterministic assertion identity and dedupe tuple are pinned.

### Phase 2 — Writer boundary + idempotency corridor
**Intent:** make LS write path deterministic and replay-safe.

**DoD checklist:**
- Writer boundary validates required pins, schema, and provenance.
- Dedupe tuple and payload-hash collision policy are enforced fail-closed.
- Durable ack is returned only after commit.
- Retry behavior is deterministic (same assertion -> same outcome).

### Phase 3 — Append-only timeline persistence
**Intent:** persist label truth as immutable timelines with correction semantics.

**DoD checklist:**
- Labels are append-only assertions; corrections are new assertions (no mutation/deletes).
- Timeline ordering semantics are deterministic and auditable.
- Provenance and evidence refs are persisted by reference.
- Storage design supports rebuild-safe backups/restores.

### Phase 4 — As-of and resolved-query surfaces
**Intent:** provide leakage-safe read surfaces for learning and governance.

**DoD checklist:**
- Timeline query by subject is supported.
- `label_as_of(subject, T)` enforces observed-time eligibility explicitly.
- Resolved view conflict posture is deterministic and explicit (or returns conflict state).
- Query contract is stable for OFS/MF consumption.

### Phase 5 — Ingest adapters (CM and engine/external truth lanes)
**Intent:** accept all v0 label sources without violating LS authority boundaries.

**DoD checklist:**
- CM LabelAssertion writes are accepted with full handshake semantics.
- Engine 6B truth/bank-view/case signals can be translated and ingested as assertions with source provenance.
- External adjudication feeds (if enabled) follow the same assertion/idempotency contract.
- No direct truth mutation path bypasses LS writer checks.

### Phase 6 — Observability, governance, and access audit
**Intent:** make LS auditable and operable under meta-layer rules.

**DoD checklist:**
- Run-scoped LS counters are emitted (`accepted`, `rejected`, `duplicate`, `pending`, anomaly classes).
- Label lifecycle governance events are emitted with actor attribution and evidence refs.
- Evidence-ref resolution/access audit hooks are available where required.
- Sensitive payload details are excluded from governance/audit records.

### Phase 7 — OFS integration and as-of training safety
**Intent:** guarantee LS can serve deterministic learning joins.

**DoD checklist:**
- OFS can consume `label_as_of` reads at scale with explicit as-of boundary.
- Label maturity/coverage signals are available for dataset gating.
- Multi-run safety is preserved through run-scoped subject keys.
- Replay/rebuild behavior is documented and validated.

### Phase 8 — Integration closure and parity proof
**Intent:** prove LS closes the human truth loop end-to-end.

**DoD checklist:**
- End-to-end proof exists:
  `CM disposition -> LabelAssertion -> LS ack -> as-of read`.
- Negative-path proof exists (hash mismatch, duplicate assertion, invalid subject, unavailable writer store).
- Reconciliation artifacts include labels accepted/rejected/pending counts with evidence refs.
- Closure statement is explicit and tied to platform Phase 5 section `5.9`.

## Status (rolling)
- Phase 1 (`LabelAssertion contract + subject model lock`): completed on `2026-02-09`.
  - Evidence:
    - `src/fraud_detection/label_store/contracts.py`
    - `src/fraud_detection/label_store/ids.py`
    - `docs/model_spec/platform/contracts/case_and_labels/label_assertion.schema.yaml`
    - `tests/services/label_store/test_phase1_label_store_contracts.py`
    - `tests/services/label_store/test_phase1_label_store_ids.py`
  - Validation:
    - `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py` -> `10 passed`
- Phase 2 (`Writer boundary + idempotency corridor`): completed on `2026-02-09`.
  - Evidence:
    - `src/fraud_detection/label_store/writer_boundary.py`
    - `src/fraud_detection/label_store/__init__.py` (Phase 2 exports)
    - `tests/services/label_store/test_phase2_writer_boundary.py`
  - Validation:
    - `python -m py_compile src/fraud_detection/label_store/writer_boundary.py src/fraud_detection/label_store/__init__.py tests/services/label_store/test_phase2_writer_boundary.py` -> pass
    - `python -m pytest -q tests/services/label_store/test_phase2_writer_boundary.py` -> `5 passed`
    - `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py` -> `15 passed`
    - `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py` -> `10 passed`
    - `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase6_action_handshake.py tests/services/case_mgmt/test_phase7_observability.py tests/services/case_mgmt/test_phase8_validation_matrix.py` -> `44 passed`
    - `python -m pytest -q tests/services/platform_reporter/test_run_reporter.py` -> `2 passed`
- Phase 3 (`Append-only timeline persistence`): completed on `2026-02-09`.
  - Evidence:
    - `src/fraud_detection/label_store/writer_boundary.py` (append-only `ls_label_timeline` + deterministic subject timeline API + rebuild utility)
    - `src/fraud_detection/label_store/__init__.py` (Phase 3 exports)
    - `tests/services/label_store/test_phase3_timeline_persistence.py`
  - Validation:
    - `python -m py_compile src/fraud_detection/label_store/writer_boundary.py src/fraud_detection/label_store/__init__.py tests/services/label_store/test_phase3_timeline_persistence.py` -> pass
    - `python -m pytest -q tests/services/label_store/test_phase3_timeline_persistence.py` -> `4 passed`
    - `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py tests/services/label_store/test_phase3_timeline_persistence.py` -> `19 passed`
    - `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py` -> `10 passed`
    - `python -m pytest -q tests/services/case_mgmt/test_phase1_contracts.py tests/services/case_mgmt/test_phase1_ids.py tests/services/case_mgmt/test_phase2_intake.py tests/services/case_mgmt/test_phase3_projection.py tests/services/case_mgmt/test_phase4_evidence_resolution.py tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase6_action_handshake.py tests/services/case_mgmt/test_phase7_observability.py tests/services/case_mgmt/test_phase8_validation_matrix.py` -> `44 passed`
    - `python -m pytest -q tests/services/platform_reporter/test_run_reporter.py` -> `2 passed`
- Phase 4 (`As-of and resolved-query surfaces`): completed on `2026-02-09`.
  - Evidence:
    - `src/fraud_detection/label_store/writer_boundary.py` (`label_as_of(...)`, `resolved_labels_as_of(...)`, explicit `RESOLVED/CONFLICT/NOT_FOUND` posture, deterministic precedence and conflict-candidate refs)
    - `src/fraud_detection/label_store/__init__.py` (Phase 4 exports)
    - `tests/services/label_store/test_phase4_as_of_queries.py`
  - Validation:
    - `python -m py_compile src/fraud_detection/label_store/writer_boundary.py src/fraud_detection/label_store/__init__.py tests/services/label_store/test_phase4_as_of_queries.py` -> pass
    - `python -m pytest -q tests/services/label_store/test_phase4_as_of_queries.py` -> `4 passed`
    - `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py tests/services/label_store/test_phase3_timeline_persistence.py tests/services/label_store/test_phase4_as_of_queries.py` -> `23 passed`
    - `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py` -> `10 passed`
- Phase 5 (`Ingest adapters (CM and engine/external truth lanes)`): completed on `2026-02-09`.
  - Evidence:
    - `src/fraud_detection/label_store/adapters.py` (source lanes `CM_ASSERTION` / `EXTERNAL_ADJUDICATION` / `ENGINE_TRUTH`, fail-closed adaptation, deterministic non-CM case-event derivation)
    - `src/fraud_detection/label_store/__init__.py` (Phase 5 exports)
    - `tests/services/label_store/test_phase5_ingest_adapters.py`
  - Validation:
    - `python -m py_compile src/fraud_detection/label_store/adapters.py src/fraud_detection/label_store/__init__.py tests/services/label_store/test_phase5_ingest_adapters.py` -> pass
    - `python -m pytest -q tests/services/label_store/test_phase5_ingest_adapters.py` -> `5 passed`
    - `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py tests/services/label_store/test_phase3_timeline_persistence.py tests/services/label_store/test_phase4_as_of_queries.py tests/services/label_store/test_phase5_ingest_adapters.py` -> `28 passed`
    - `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py` -> `10 passed`
- Phase 6 (`Observability, governance, and access audit`): completed on `2026-02-09`.
  - Evidence:
    - `src/fraud_detection/label_store/observability.py` (run-scoped LS reporter, lifecycle governance emission, and evidence access-audit hook surfaces)
    - `src/fraud_detection/label_store/__init__.py` (Phase 6 exports)
    - `src/fraud_detection/platform_reporter/run_reporter.py` (LS reconciliation refs included for platform report evidence surfaces)
    - `tests/services/label_store/test_phase6_observability.py`
  - Validation:
    - `python -m py_compile src/fraud_detection/label_store/observability.py src/fraud_detection/label_store/__init__.py src/fraud_detection/platform_reporter/run_reporter.py tests/services/label_store/test_phase6_observability.py` -> pass
    - `python -m pytest -q tests/services/label_store/test_phase6_observability.py` -> `4 passed`
    - `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py tests/services/label_store/test_phase3_timeline_persistence.py tests/services/label_store/test_phase4_as_of_queries.py tests/services/label_store/test_phase5_ingest_adapters.py tests/services/label_store/test_phase6_observability.py` -> `32 passed`
    - `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py` -> `10 passed`
    - `python -m pytest -q tests/services/platform_reporter/test_run_reporter.py` -> `2 passed`
- Phase 7 (`OFS integration and as-of training safety`): completed on `2026-02-09`.
  - Evidence:
    - `src/fraud_detection/label_store/slices.py` (bulk `label_as_of` slice builder with explicit basis, run-scope enforcement, deterministic digest artifacts, and dataset gate signal surfaces)
    - `src/fraud_detection/label_store/__init__.py` (Phase 7 exports)
    - `tests/services/label_store/test_phase7_ofs_slices.py`
  - Validation:
    - `python -m py_compile src/fraud_detection/label_store/slices.py src/fraud_detection/label_store/__init__.py tests/services/label_store/test_phase7_ofs_slices.py` -> pass
    - `python -m pytest -q tests/services/label_store/test_phase7_ofs_slices.py` -> `4 passed`
    - `python -m pytest -q tests/services/label_store/test_phase1_label_store_contracts.py tests/services/label_store/test_phase1_label_store_ids.py tests/services/label_store/test_phase2_writer_boundary.py tests/services/label_store/test_phase3_timeline_persistence.py tests/services/label_store/test_phase4_as_of_queries.py tests/services/label_store/test_phase5_ingest_adapters.py tests/services/label_store/test_phase6_observability.py tests/services/label_store/test_phase7_ofs_slices.py` -> `36 passed`
    - `python -m pytest -q tests/services/case_mgmt/test_phase5_label_handshake.py tests/services/case_mgmt/test_phase8_validation_matrix.py` -> `10 passed`
    - `python -m pytest -q tests/services/platform_reporter/test_run_reporter.py` -> `2 passed`
- Next action: Phase 8 implementation (integration closure and parity proof).
