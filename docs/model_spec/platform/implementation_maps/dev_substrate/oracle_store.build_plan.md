# Oracle Store Build Plan (dev_substrate)
_As of 2026-02-11_

## Purpose
Migrate Oracle Store usage for Control + Ingress (`3.C`) so `dev_min` streaming is anchored to sealed S3 truth and never falls back to local filesystem semantics.

## Authority anchors
- `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.build_plan.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (Phase `3.C`)

## Migration phases (3.C scoped)
### Phase C1 - Oracle source authority lock
**Intent:** prove Oracle source is explicit and immutable for `dev_min`.

**DoD checklist:**
- [ ] `oracle_engine_run_root` + `scenario_id` are explicit for the run.
- [ ] Seal/manifest posture is validated for selected oracle root.
- [ ] No implicit "latest" lookup or local-path fallback is permitted.

### Phase C2 - Stream-view readiness gate
**Intent:** confirm WSP-required outputs are available in sorted stream-view form.

**DoD checklist:**
- [ ] Required stream-view outputs exist under `stream_view/ts_utc/output_id=...`.
- [ ] Stream-view manifest/receipt checks pass fail-closed.
- [ ] Evidence contains output-level locator refs and digests.

### Phase C3 - SR/WSP contract coupling
**Intent:** lock Oracle refs consumed by SR and WSP to one run-scoped truth basis.

**DoD checklist:**
- [ ] SR run_facts_view carries oracle refs that resolve against the selected root.
- [ ] WSP stream identity matches the same oracle root and scenario scope.
- [ ] Any locator mismatch halts progression to WSP matrix.

### Phase C4 - Run/operate + obs/gov onboarding
**Intent:** ensure Oracle checks are represented in operational and evidence surfaces.

**DoD checklist:**
- [ ] Run/operate flow includes deterministic Oracle readiness step.
- [ ] Governance/reporting surfaces include Oracle readiness result refs.
- [ ] Failure signatures are explicit and mapped to stable reason codes.

### Phase C5 - Oracle migration matrix closure
**Intent:** close Oracle slice of `3.C` before SR/WSP full migration.

**DoD checklist:**
- [ ] Matrix run demonstrates PASS on Oracle source + stream-view checks.
- [ ] Evidence paths are recorded in dev_substrate impl/logbook.
- [ ] Residual risks (if any) are explicitly accepted or remediated.

## Current status
- Phase C1: not started
- Phase C2: not started
- Phase C3: not started
- Phase C4: not started
- Phase C5: not started
