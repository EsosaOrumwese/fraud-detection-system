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
