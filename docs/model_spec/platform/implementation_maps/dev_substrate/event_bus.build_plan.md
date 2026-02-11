# Event Bus Build Plan (dev_substrate)
_As of 2026-02-11_

## Purpose
Migrate EB usage for `dev_min` Control + Ingress (`3.C`) so managed Kafka remains a durable admitted-event log with replay-safe offsets and no ownership drift.

## Authority anchors
- `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.build_plan.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (Phase `3.C`)

## Migration phases (3.C scoped)
### Phase C1 - Topic corridor conformance gate
**Intent:** ensure the managed topic set matches the settlement corridor and ownership expectations.

**DoD checklist:**
- [ ] Control, traffic, context, and audit topics required for C&I are present.
- [ ] Partition minimums and retention posture match settlement constraints.
- [ ] Corridor readiness evidence is recorded and reproducible.

### Phase C2 - Publish/read durability gate
**Intent:** prove admitted publishes are durable and replay-visible.

**DoD checklist:**
- [ ] IG-admitted records are readable from expected topic/partition/offset basis.
- [ ] Receipt `eb_ref` values resolve to actual broker records.
- [ ] Replay from bounded offsets is deterministic for sampled windows.

### Phase C3 - Offset/replay evidence coupling gate
**Intent:** ensure run-scoped evidence links offsets to run identities without ambiguity.

**DoD checklist:**
- [ ] Run reporter can consume EB evidence refs for C&I run.
- [ ] Offset basis artifacts remain aligned with platform run scope.
- [ ] No mismatch between receipt offsets and replay observations.

### Phase C4 - Run/operate + obs/gov onboarding
**Intent:** include EB readiness and replay posture in operated/gov surfaces.

**DoD checklist:**
- [ ] Run/operate status/report includes EB topic corridor posture.
- [ ] Governance emissions include EB-related anomalies and reconciliation facts.
- [ ] Residual/noise conditions are explicit and non-silent.

### Phase C5 - EB migration matrix closure
**Intent:** close EB slice green and unlock `3.C.6` coupled-chain closure.

**DoD checklist:**
- [ ] EB matrix green on `dev_min` for corridor/publish/read/replay checks.
- [ ] Evidence refs recorded in dev_substrate impl/logbook.
- [ ] No unresolved topic-routing drift remains.

## Current status
- Phase C1: not started
- Phase C2: not started
- Phase C3: not started
- Phase C4: not started
- Phase C5: not started
