# World Streamer Producer Build Plan (dev_substrate)
_As of 2026-02-11_

## Purpose
Migrate WSP for `dev_min` Control + Ingress (`3.C`) as the live stream head between Oracle and IG while preserving run-scope pins, bounded retry posture, and checkpoint safety.

## Authority anchors
- `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.build_plan.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (Phase `3.C`)

## Migration phases (3.C scoped)
### Phase C1 - READY intake + run-scope validation
**Intent:** consume SR READY from managed control topic and lock run identity before streaming.

**DoD checklist:**
- [ ] WSP consumes READY in `dev_min` control corridor.
- [ ] READY/run_facts identity checks fail closed on mismatch.
- [ ] WSP refuses stale/foreign run READY payloads.

### Phase C2 - Oracle stream-view replay gate
**Intent:** stream only from Oracle stream-view outputs required by current run mode.

**DoD checklist:**
- [ ] Stream-view manifest/receipt checks pass for selected outputs.
- [ ] Event-time replay uses canonical `ts_utc` order.
- [ ] No local data path is consumed while `dev_min` profile is active.

### Phase C3 - IG push reliability + checkpoint safety
**Intent:** preserve bounded retry semantics and run-safe resume posture.

**DoD checklist:**
- [ ] Retry taxonomy is bounded and deterministic (retryable vs terminal).
- [ ] Same event identity is preserved across retries.
- [ ] Checkpoint scope is run-safe and does not drift across runs.

### Phase C4 - Run/operate + obs/gov onboarding
**Intent:** onboard WSP as an operated long-running service with explicit telemetry.

**DoD checklist:**
- [ ] WSP lifecycle is represented in `dev_min` run/operate pack surfaces.
- [ ] Governance/reporting captures stream start/stop/cap/defer outcomes.
- [ ] Required-pack gating posture is explicit and evidence-backed.

### Phase C5 - WSP migration matrix closure
**Intent:** close WSP as green before IG/EB final coupled closure.

**DoD checklist:**
- [ ] WSP matrix green on `dev_min` (READY -> stream -> IG push).
- [ ] Run-scoped evidence refs recorded in impl/logbook.
- [ ] No unresolved drift remains in run-scope pins or checkpoint semantics.

## Current status
- Phase C1: not started
- Phase C2: not started
- Phase C3: not started
- Phase C4: not started
- Phase C5: not started
