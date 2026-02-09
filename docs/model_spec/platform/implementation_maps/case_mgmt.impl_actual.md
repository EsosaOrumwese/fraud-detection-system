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
