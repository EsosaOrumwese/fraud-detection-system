# Decision Log & Audit Build Plan (v0)
_As of 2026-02-07_

## Purpose
Provide an executable, component-scoped DLA plan aligned to platform `Phase 4.5` audit-closure requirements.

## Authorities (binding)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (`4.5.A...4.5.J`)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/decision_log_audit.design-authority.md`

## Planning rules (binding)
- Progressive elaboration: expand only active phase sections while preserving objective DoD gates.
- No half-baked transitions: do not advance until phase DoD is validated.
- Rails are non-negotiable: append-only truth, by-ref evidence, fail-closed provenance.

## Component boundary
- This component owns:
  - append-only audit records for decision->action->outcome lineage,
  - evidence-boundary persistence and deterministic lookup/index,
  - audit-chain reconciliation outputs.
- This component does not own:
  - decision synthesis (DF),
  - side-effect execution (AL),
  - admission decisions (IG).

## Phase plan (v0)

### Phase 1 — Audit contracts + evidence model
**Intent:** lock canonical audit record contracts and required provenance fields.

**DoD checklist:**
- Audit schema pins decision ref, action intent ref, outcome ref, bundle/policy refs, ContextPins, and run_config_digest.
- Required EB evidence boundary fields are explicit (traffic origin_offset + context offsets when used).
- By-ref evidence contract is pinned; payload copy usage is policy-gated only.
- Contract validation tests cover missing/incompatible provenance.
**Evidence (Phase 1):**
- Code:
  - `src/fraud_detection/decision_log_audit/contracts.py`
  - `src/fraud_detection/decision_log_audit/__init__.py`
- Tests:
  - `tests/services/decision_log_audit/test_dla_phase1_contracts.py`
- Validation:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit -q`

### Phase 2 — Storage layout + append-only substrate
**Intent:** establish immutable record storage and deterministic object paths.

**DoD checklist:**
- Object-store prefix layout is pinned for per-run audit artifacts.
- DLA writer enforces append-only writes (no update/delete mutation path).
- Index schema (Postgres/local parity equivalent) is pinned for deterministic lookup keys.
- Retention posture is defined per environment ladder.
**Evidence (Phase 2):**
- Config:
  - `config/platform/dla/storage_policy_v0.yaml`
- Code:
  - `src/fraud_detection/decision_log_audit/storage.py`
  - `src/fraud_detection/decision_log_audit/__init__.py`
- Tests:
  - `tests/services/decision_log_audit/test_dla_phase2_storage.py`
- Validation:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit/test_dla_phase2_storage.py -q`
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit -q`
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q`

### Phase 3 — Intake consumer + fail-closed validation
**Intent:** consume decision/outcome streams safely from admitted EB surfaces.

**DoD checklist:**
- Consumer accepts only allowed event families/schemas for audit assembly.
- Envelope + pins + schema compatibility are validated fail-closed.
- Invalid or incomplete events are quarantined with explicit reason taxonomy.
- Checkpoint does not advance on failed validation/write paths.
**Evidence (Phase 3):**
- Config:
  - `config/platform/dla/intake_policy_v0.yaml`
- Code:
  - `src/fraud_detection/decision_log_audit/config.py`
  - `src/fraud_detection/decision_log_audit/inlet.py`
  - `src/fraud_detection/decision_log_audit/intake.py`
  - `src/fraud_detection/decision_log_audit/storage.py`
  - `src/fraud_detection/decision_log_audit/__init__.py`
- Tests:
  - `tests/services/decision_log_audit/test_dla_phase3_intake.py`
- Validation:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit/test_dla_phase3_intake.py -q`
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit -q`
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q`

### Phase 4 — Lineage assembly (decision -> intent -> outcome)
**Intent:** materialize deterministic audit-chain linkage.

**DoD checklist:**
- DLA assembles immutable lineage keyed by decision identity and linked outcome identities.
- Supports partial-order arrivals (decision before outcome, outcome before decision) with deterministic reconciliation semantics.
- No silent correction: missing links remain explicit unresolved states until resolved by later append.
- Audit chain stores provenance refs needed for replay and inspection.
**Evidence (Phase 4):**
- Code:
  - `src/fraud_detection/decision_log_audit/storage.py`
  - `src/fraud_detection/decision_log_audit/intake.py`
  - `src/fraud_detection/decision_log_audit/__init__.py`
- Tests:
  - `tests/services/decision_log_audit/test_dla_phase4_lineage.py`
- Validation:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit/test_dla_phase4_lineage.py -q`
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit -q`
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q`

### Phase 5 — Index + query/read contract
**Intent:** provide deterministic and operationally useful audit lookup.

**DoD checklist:**
- Query surfaces support lookup by run scope, decision id, action intent id, outcome id, and time range.
- Responses include provenance refs and chain completeness status.
- Query contract is deterministic under duplicate/replayed inputs.
- Access controls and redaction policy hooks are enforced on read paths.
**Evidence (Phase 5):**
- Code:
  - `src/fraud_detection/decision_log_audit/storage.py`
  - `src/fraud_detection/decision_log_audit/query.py`
  - `src/fraud_detection/decision_log_audit/__init__.py`
- Tests:
  - `tests/services/decision_log_audit/test_dla_phase5_query.py`
- Validation:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit/test_dla_phase5_query.py -q`
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit -q`
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q`

### Phase 6 — Commit ordering + checkpoint/replay determinism
**Intent:** enforce commit semantics required by RTDL v0.

**DoD checklist:**
- Durable DLA append is explicit commit gate for relevant checkpoint advancement.
- Replay from same basis reproduces identical audit identity chain.
- Crash/restart tests verify no skipped/duplicated append artifacts.
- Divergence/mismatch detection emits audit anomalies and blocks unsafe advancement.
**Evidence (Phase 6):**
- Code:
  - `src/fraud_detection/decision_log_audit/storage.py`
  - `src/fraud_detection/decision_log_audit/intake.py`
  - `src/fraud_detection/decision_log_audit/__init__.py`
- Tests:
  - `tests/services/decision_log_audit/test_dla_phase6_commit_replay.py`
- Validation:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit/test_dla_phase6_commit_replay.py -q`
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit -q`
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q`

### Phase 7 — Observability + reconciliation + security
**Intent:** make audit closure health explicit and operable.

**DoD checklist:**
- Metrics/logs expose append success/failure, unresolved links, quarantine counts, lag, and checkpoint status.
- Reconciliation artifact summarizes per-run chain completeness and anomaly lanes.
- Security controls cover least-privilege reads/writes and secret-safe artifact handling.
- Governance stamps are retained for policy/bundle/execution profile attribution.
**Evidence (Phase 7):**
- Code:
  - `src/fraud_detection/decision_log_audit/observability.py`
  - `src/fraud_detection/decision_log_audit/storage.py`
  - `src/fraud_detection/decision_log_audit/intake.py`
  - `src/fraud_detection/decision_log_audit/__init__.py`
- Tests:
  - `tests/services/decision_log_audit/test_dla_phase7_observability.py`
- Validation:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit/test_dla_phase7_observability.py -q`
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit -q`
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q`

### Phase 8 — Platform integration closure (`4.5` DLA scope)
**Intent:** prove DLA is green at component boundary and satisfies platform audit closure expectations.

**DoD checklist:**
- Integration tests prove DF/AL event surfaces form complete DLA audit chains.
- Local-parity monitored 20 and 200 event runs produce complete audit evidence artifacts.
- Replay tests prove deterministic audit-chain reconstruction from the same basis.
- Closure statement is explicit: DLA component green; remaining platform dependencies (if any) are listed for phase handoff.
**Evidence (Phase 8):**
- Code:
  - `src/fraud_detection/decision_log_audit/storage.py`
  - `tests/services/decision_log_audit/test_dla_phase8_validation_matrix.py`
- Validation:
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit/test_dla_phase8_validation_matrix.py -q`
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/decision_log_audit -q`
  - `$env:PYTHONPATH='.;src'; python -m pytest tests/services/action_layer tests/services/decision_log_audit -q`
- Parity artifacts:
  - `runs/fraud-platform/platform_20260207T220000Z/decision_log_audit/reconciliation/phase8_parity_proof_20.json`
  - `runs/fraud-platform/platform_20260207T220000Z/decision_log_audit/reconciliation/phase8_parity_proof_200.json`

## Status (rolling)
- Phase 1 (`Audit contracts + evidence model`): completed on `2026-02-07`.
- Phase 2 (`Storage layout + append-only substrate`): completed on `2026-02-07`.
- Phase 3 (`Intake consumer + fail-closed validation`): completed on `2026-02-07`.
- Phase 4 (`Lineage assembly (decision -> intent -> outcome)`): completed on `2026-02-07`.
- Phase 5 (`Index + query/read contract`): completed on `2026-02-07`.
- Phase 6 (`Commit ordering + checkpoint/replay determinism`): completed on `2026-02-07`.
- Phase 7 (`Observability + reconciliation + security`): completed on `2026-02-07`.
- Phase 8 (`Platform integration closure (4.5 DLA scope)`): completed on `2026-02-07`.
- Component closure: DLA `4.5` scope is green at component boundary; remaining end-to-end RTDL closure depends on platform-level integration with still-in-flight components.
