# Context Store + FlowBinding Implementation Notes
_As of 2026-02-07_

## Entry: 2026-02-07 14:02:30 - Component bootstrap and pre-implementation plan

### Problem statement
RTDL integration still needs a shared runtime join plane that DF/DL can query deterministically at decision time. Existing components cover adjacent truth planes but do not provide an explicit runtime JoinFrame + FlowBinding service boundary:
- IEG: projection/world state
- OFP: feature snapshots
- DF/DL: decision core

The missing explicit boundary increases ambiguity on where flow resolution and join-readiness truth are sourced during live decisioning.

### Authorities and references used
- `docs/model_spec/platform/implementation_maps/platform.build_plan.md` (Phase `4.3.5`)
- `docs/model_spec/platform/pre-design_decisions/real-time_decision_loop.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/component-specific/identity_entity_graph.design-authority.md`
- `docs/model_spec/platform/component-specific/decision_fabric.design-authority.md`

### Decision
Treat the shared join plane as its own component:
- Component id: `context_store_flow_binding`
- Build plan path:
  - `docs/model_spec/platform/implementation_maps/context_store_flow_binding.build_plan.md`
- Implementation notes path:
  - `docs/model_spec/platform/implementation_maps/context_store_flow_binding.impl_actual.md`

### Alternatives considered
1. Extend IEG to own join-plane runtime reads.
- Rejected: mixes projection authority with decision-time join readiness service concerns.

2. Extend OFP to own FlowBinding and runtime join lookups.
- Rejected: OFP owns snapshot materialization/serve, not authoritative flow-binding updates.

3. Introduce dedicated join-plane component (selected).
- Selected: clean ownership boundary for JoinFrame + FlowBinding runtime duties and explicit DF/DL read contract.

### Planned implementation order
1. Phase 1 contract pinning:
- define JoinFrameKey contract and required pins.
- define FlowBinding contract and conflict semantics.
- define query/read schema for DF/DL.

2. Phase 2 storage:
- add Postgres schema + indexes + checkpoint tables.
- pin commit-point and replay invariants.

3. Phase 3 intake worker:
- EB context intake with idempotent apply and conflict handling.

4. Phase 4+:
- query API
- observability and reconciliation
- parity runs and hardening.

### Invariants to enforce from day 1
- No fabricated joins: missing binding/context is explicit fail-closed response.
- FlowBinding authority is only flow-anchor lineage.
- Replay from identical offset basis must reproduce identical runtime state.
- All rows and artifacts are run-scoped via ContextPins.

### Security and governance posture
- No secrets in runtime artifacts, implementation notes, or logbook.
- Conflict and compatibility failures emit anomaly records; never silently overwrite.

### Validation plan for initial implementation phases
- Unit tests for key normalization, idempotency tuple, and conflict detection.
- Integration tests for context intake -> FlowBinding resolve -> JoinFrame read.
- Replay tests proving same basis -> same state.

---

## Entry: 2026-02-07 14:38:00 - Phase 1 implementation plan (contracts/keys/ownership pins)

### Active-phase objective
Implement Phase 1 from `context_store_flow_binding.build_plan.md` by producing enforceable contract surfaces and policy loaders that downstream runtime code can rely on without ambiguity.

### Decision thread 1: where contracts live
Options considered:
1. Keep Phase 1 contracts as Python-only dataclasses.
2. Create JSON schemas under RTDL contract folder and mirror them in Python validators.

Decision:
- Use Option 2.

Reasoning:
- Existing platform contract authority is schema-first under
  `docs/model_spec/platform/contracts/real_time_decision_loop`.
- Runtime code should consume a typed Python API, but schema artifacts are needed for cross-component and auditable contract review.

Planned schema artifacts:
- `context_store_flow_binding_join_frame_key.schema.yaml`
- `context_store_flow_binding_flow_binding.schema.yaml`
- `context_store_flow_binding_query_request.schema.yaml`
- `context_store_flow_binding_query_response.schema.yaml`

### Decision thread 2: package/module structure
Options considered:
1. Add code into IEG/OFP modules as helpers.
2. New dedicated package `src/fraud_detection/context_store_flow_binding/`.

Decision:
- Option 2 (dedicated package).

Reasoning:
- Prevents ownership blending and keeps the 4.3.5 boundary explicit.
- Enables isolated tests (`tests/services/context_store_flow_binding/`) and phased implementation.

Planned modules:
- `contracts.py`: normalized typed contracts + validation.
- `taxonomy.py`: authoritative event-type compatibility checks for flow-binding source lineage.
- `config.py`: phase policy loader (`required_pins`, source allowlist, compatibility posture, digest).
- `__init__.py`: public exports.

### Decision thread 3: pin posture in Phase 1
Decision:
- Required pins remain strict v0 synthetic posture:
  `platform_run_id`, `scenario_run_id`, `manifest_fingerprint`, `parameter_hash`, `scenario_id`, `seed`.
- `run_id` remains optional compatibility alias where present.

Reasoning:
- This matches existing RTDL contract posture and current DF/OFP/IEG pin requirements.

### Decision thread 4: query contract scope
Decision:
- Phase 1 query contract supports two deterministic lookup selectors:
  - by `flow_id` (FlowBinding resolution path),
  - by explicit `join_frame_key`.
- Request must provide exactly one selector to avoid ambiguous read semantics.

Reasoning:
- Matches planned runtime join-plane behavior and avoids hidden precedence rules in reads.

### Decision thread 5: authoritative writer rule encoding
Decision:
- FlowBinding contract and taxonomy will enforce source lineage event types:
  - `s2_flow_anchor_baseline_6B`
  - `s3_flow_anchor_with_fraud_6B`

Reasoning:
- This encodes the "flow-anchor only" authority in Phase 1 so later ingestion/apply code can fail closed by contract, not by ad-hoc branching.

### Phase 1 validation matrix (concrete)
- Contract tests:
  - valid/invalid JoinFrameKey normalization.
  - FlowBinding source-event gate enforcement.
  - query request selector exclusivity.
- Taxonomy tests:
  - allowed flow-anchor families accepted, others rejected.
- Config tests:
  - policy loader deterministic digest and required fields.

---

## Entry: 2026-02-07 14:56:40 - Phase 1 implementation completed (contracts + policy + tests)

### What was implemented
- Contract schemas (RTDL):
  - `context_store_flow_binding_join_frame_key.schema.yaml`
  - `context_store_flow_binding_flow_binding.schema.yaml`
  - `context_store_flow_binding_query_request.schema.yaml`
  - `context_store_flow_binding_query_response.schema.yaml`
- Runtime validation package:
  - `src/fraud_detection/context_store_flow_binding/contracts.py`
  - `src/fraud_detection/context_store_flow_binding/taxonomy.py`
  - `src/fraud_detection/context_store_flow_binding/config.py`
- Policy:
  - `config/platform/context_store_flow_binding/policy_v0.yaml`
- Contract index update:
  - `docs/model_spec/platform/contracts/real_time_decision_loop/README.md`

### Decisions made during implementation (with reasoning)
1. **Seed pin enforcement tied to policy flag**
   - Decision: `require_seed=true` must imply `seed` is present in `required_pins`.
   - Reasoning: prevents policies that claim to require seed while omitting it from the pin allowlist, which would create a hidden mismatch between validation and policy posture.

2. **Taxonomy enforcement raises config errors at policy load**
   - Decision: unknown authoritative event types raise `ContextStoreFlowBindingConfigError`, not a raw taxonomy error.
   - Reasoning: policy loading is the authoritative boundary; callers expect a uniform config exception class for policy issues.

3. **Selector exclusivity as hard contract invariant**
   - Decision: Query requests require exactly one selector (`flow_id` xor `join_frame_key`).
   - Reasoning: removes ambiguous precedence during read and keeps join-plane semantics deterministic in Phase 1.

4. **Run identity normalization**
   - Decision: `platform_run_id` uses strict `platform_YYYYMMDDTHHMMSSZ` format; `run_id` stays optional compatibility alias.
   - Reasoning: avoids reintroducing legacy ambiguity while still tolerating legacy `run_id` presence.

### Phase 1 DoD mapping
- JoinFrameKey schema pinned in schema + Python validator.
- FlowBinding schema + authoritative writer rule enforced by taxonomy allowlist.
- ContextPins are validated in both request/response and FlowBinding records.
- Query contract versioned with selector exclusivity.

### Tests executed
- `$env:PYTHONPATH='.;src'; python -m pytest tests/services/context_store_flow_binding -q`
  - Result: `12 passed`

### Notes on constraints and invariants
- All contracts are fail-closed; missing or malformed pins result in explicit contract errors.
- No fabricated joins: queries can only resolve by explicit FlowBinding or explicit JoinFrameKey.
- Phase 1 implements contract/policy boundaries only; storage and intake are deferred to Phase 2+.
