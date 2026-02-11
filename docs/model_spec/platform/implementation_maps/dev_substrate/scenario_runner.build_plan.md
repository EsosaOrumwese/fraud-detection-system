# Scenario Runner Build Plan (dev_substrate)
_As of 2026-02-11_

## Purpose
Migrate Scenario Runner for `dev_min` Control + Ingress (`3.C`) so READY + run_facts_view remain the canonical run-readiness join surface on managed substrate.

## Authority anchors
- `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.build_plan.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (Phase `3.C`)

## Migration phases (3.C scoped)
### Phase C1 - Dev wiring + Oracle coupling
**Intent:** bind SR to `dev_min` profile and Oracle by-ref truth.

**DoD checklist:**
- [ ] SR resolves `dev_min` wiring without local fallback assumptions.
- [ ] Oracle refs in run_facts_view are valid and run-scoped.
- [ ] SR authority store path/DSN is deterministic for run readiness.

### Phase C2 - Run identity + facts contract gate
**Intent:** enforce canonical run-identity and facts payload integrity.

**DoD checklist:**
- [ ] `platform_run_id` + `scenario_run_id` are present and coherent.
- [ ] `run_config_digest` and policy refs are emitted as pinned.
- [ ] Facts schema checks are fail-closed.

### Phase C3 - READY publish + idempotency gate
**Intent:** ensure READY is deterministic and replay-safe on managed control corridor.

**DoD checklist:**
- [ ] READY publish succeeds on configured control topic.
- [ ] READY message id is idempotent across safe retries/re-emits.
- [ ] READY is never emitted before committed run_facts_view evidence.

### Phase C4 - Run/operate + obs/gov onboarding
**Intent:** treat SR as an operated service in the migration wave, not a one-off command.

**DoD checklist:**
- [ ] SR lifecycle is represented in run/operate `dev_min` control_ingress pack flow.
- [ ] Governance lifecycle emissions include SR run-start/run-ready/run-terminal surfaces.
- [ ] Reporter and logs show SR evidence refs per run.

### Phase C5 - SR migration matrix closure
**Intent:** close SR as a green component before WSP integrated progression.

**DoD checklist:**
- [ ] SR component matrix green on `dev_min`.
- [ ] SR evidence refs recorded in dev_substrate impl/logbook.
- [ ] Open defects are closed or explicitly blocked with user acceptance.

## Current status
- Phase C1: not started
- Phase C2: not started
- Phase C3: not started
- Phase C4: not started
- Phase C5: not started
