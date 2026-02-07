# Decision Fabric Build Plan (v0)
_As of 2026-02-07_

## Purpose
Provide an executable, phase-by-phase DF build plan aligned to platform Phase 4.4 (`DF/DL decision core`) and RTDL pre-design pins.

## Authorities (binding)
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase 4.4)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md`

## Planning rules (binding)
- Progressive elaboration: phases are explicit; active phase expands into implementation sections/tasks.
- No half-baked phases: do not advance until phase DoD is met with evidence.
- Rails are non-negotiable: canonical envelope, ContextPins, fail-closed posture, IG->EB truth boundary, replay determinism.

## Phase plan (v0)

### Phase 1 — DF contracts + deterministic identity
**Intent:** lock DF output/input contracts before pipeline code.

**DoD checklist:**
- DecisionResponse and ActionIntent schemas pin required provenance fields:
  `bundle_ref`, `snapshot_hash`, `graph_version`, `eb_offset_basis`, `degrade_mode`, `capabilities_mask`, `policy_rev`, `run_config_digest`.
- Deterministic identity rules are pinned and documented:
  `decision_id`, DecisionResponse `event_id`, ActionIntent `event_id`, ActionIntent `idempotency_key`.
- Event taxonomy (`event_type`, `schema_version`) is pinned with compatibility posture (major mismatch fail-closed).
- Contract docs reference authoritative schema paths; no duplicate schema drift.

### Phase 2 — Inlet boundary + trigger gating
**Intent:** ensure DF only processes valid admitted traffic stimuli.

**DoD checklist:**
- DF consumes admitted traffic topics only; context/control topics are never decision triggers.
- Decision trigger allowlist is explicit and versioned.
- Required pins are validated at ingress (`platform_run_id`, `scenario_run_id`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`, `seed` when required).
- Loop prevention is enforced: DF does not retrigger on DF/AL-produced event families.
- Source evidence basis is captured per candidate decision (`source_event_id`, `origin_offset/eb_ref`).

### Phase 3 — DL integration + fail-safe enforcement
**Intent:** enforce explicit degrade posture as a hard runtime constraint.

**DoD checklist:**
- DF consumes `DegradeDecision` (`mode`, `capabilities_mask`, `policy_rev`, provenance reasons).
- DL mask is enforced as hard constraints (no bypass path when capability is disabled).
- Missing/invalid/stale DL posture forces explicit fail-closed decision mode with reasons.
- Posture stamps are written into decision artifacts deterministically.
- Transition behavior is compatible with DL anti-flap semantics (immediate tighten, controlled relax).

### Phase 4 — Registry bundle resolution + compatibility
**Intent:** remove ambiguity in model/policy selection.

**DoD checklist:**
- Registry resolver is deterministic for scope `(environment, mode, bundle_slot, tenant?)`; no implicit "latest."
- Bundle compatibility checks are fail-closed for schema/capability mismatch.
- Resolver fallback behavior is explicit, bounded, and provenance-stamped.
- Resolver outputs are replay-stable for identical input basis + policy revision.

### Phase 5 — Context/features acquisition + decision-time budgets
**Intent:** consume OFP/IEG context safely within RTDL decision budgets.

**DoD checklist:**
- OFP reads use `as_of_time_utc = source event ts_utc` (no hidden wall-clock dependency).
- IEG and OFP calls obey DL mask and join readiness policy.
- `decision_deadline_ms` and `join_wait_budget_ms` are enforced from policy.
- Missing required context produces explicit degrade reasons (no fabricated context).
- Context evidence refs (traffic + context offsets) are captured when used.

### Phase 6 — Decision synthesis + intent emission
**Intent:** produce deterministic decisions and intents at the IG publish boundary.

**DoD checklist:**
- Decision synthesis pipeline is deterministic for fixed basis (guardrails/model stages under explicit posture).
- ActionIntent emission respects DL `action_posture` constraints.
- DecisionResponse and ActionIntent are emitted as canonical envelope traffic through IG (no side channel).
- Publish boundary handles ADMIT/DUPLICATE/QUARANTINE explicitly with stable behavior.
- Decision corrections follow append-only supersede semantics (no overwrite).

### Phase 7 — Idempotency, checkpoints, and replay safety
**Intent:** make DF safe under at-least-once delivery and replay.

**DoD checklist:**
- Re-delivered source events do not produce divergent decision artifacts.
- Determinism rule is proven:
  same event + same DL posture + same bundle + same OFP/IEG basis -> same decision/intents.
- Payload mismatch on equivalent decision identity is surfaced as anomaly; never silently replaced.
- Checkpoints advance only after durable decision/intent publish boundary and local decision persistence commit.

### Phase 8 — Observability, validation, and component closure
**Intent:** prove DF is component-green and ready for 4.5 integration gates.

**DoD checklist:**
- Run-scoped metrics exist for latency (p50/p95/p99), degrade counts, missing context, resolver failures, fail-closed events.
- Reconciliation artifact summarizes decisions by mode/bundle/posture with evidence refs.
- Test matrix is complete:
  - unit tests (resolver determinism, posture enforcement, identity determinism),
  - integration tests (OFP/IEG/DL + IG publish path),
  - replay tests (basis-stable outputs),
  - local-parity proofs (20-event sanity and 200-event monitored run).
- Closure statement is explicit:
  DF component green at decision+intent boundary, with AL/DLA execution/audit closure tracked under platform Phase 4.5.

## Status (rolling)
- Phase 1 (`DF contracts + deterministic identity`): completed on `2026-02-07`.
  - Evidence: `tests/services/decision_fabric/test_phase1_contracts.py`
  - Evidence: `tests/services/decision_fabric/test_phase1_ids.py`
  - Evidence: `tests/services/decision_fabric/test_phase1_taxonomy.py`
  - Validation: `python -m pytest tests/services/decision_fabric -q` -> `14 passed`
- Phase 2 (`Inlet boundary + trigger gating`): completed on `2026-02-07`.
  - Evidence: `config/platform/df/trigger_policy_v0.yaml`
  - Evidence: `src/fraud_detection/decision_fabric/config.py`
  - Evidence: `src/fraud_detection/decision_fabric/inlet.py`
  - Evidence: `tests/services/decision_fabric/test_phase2_config.py`
  - Evidence: `tests/services/decision_fabric/test_phase2_inlet.py`
  - Validation: `python -m pytest tests/services/decision_fabric -q` -> `24 passed`
- Phase 3 (`DL integration + fail-safe enforcement`): completed on `2026-02-07`.
  - Evidence: `src/fraud_detection/decision_fabric/posture.py`
  - Evidence: `tests/services/decision_fabric/test_phase3_posture.py`
  - Validation: `python -m pytest tests/services/decision_fabric -q` -> `29 passed`
- Phase 4 (`Registry bundle resolution + compatibility`): completed on `2026-02-07`.
  - Evidence: `config/platform/df/registry_resolution_policy_v0.yaml`
  - Evidence: `src/fraud_detection/decision_fabric/registry.py`
  - Evidence: `tests/services/decision_fabric/test_phase4_registry.py`
  - Validation: `python -m pytest tests/services/decision_fabric -q` -> `36 passed`
- Current focus: Phase 5 (`Context/features acquisition + decision-time budgets`).
