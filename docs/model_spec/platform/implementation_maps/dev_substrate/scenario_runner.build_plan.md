# Scenario Runner Build Plan (dev_substrate, Phase 3.C.2)
_As of 2026-02-11_

## Purpose
Deliver SR migration for `dev_min` under full-migration posture:
1. SR remains the canonical run-readiness authority (`run_facts_view` + READY).
2. Acceptance runs are managed-substrate only (no local runtime/state fallback).
3. Semantic laws from local-parity remain unchanged (identity, idempotency, fail-closed readiness, by-ref provenance).

## Planning rules (binding)
- Progressive elaboration: only expand active `3.C.2` scope to closure-grade detail.
- No partial-green progression: SR must fully close before `3.C.3` acceptance progression.
- Fail-closed posture: unknown/missing/ambiguous Oracle/run facts/READY state is blocked, never guessed.
- Evidence-first: each gate must emit run-scoped refs suitable for reporter/conformance linkage.

## Authority anchors
- `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md`
- `docs/model_spec/platform/platform-wide/deployment_tooling_notes_v0.md`
- `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/scenario_runner.design-authority.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (`3.C.2`)
- Baseline carry-forward:
  - `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.build_plan.md`
  - `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md`

## Full-migration repin inherited from platform 3.C.2 (locked)
- SR acceptance runtime for `dev_min` is managed compute only.
- SR acceptance state corridor is managed-substrate only.
- Gate strictness remains full parity semantics (no reduced subset).
- READY re-emit defaults to same-run only; cross-run emit requires explicit governance override evidence.
- Fail-closed on Oracle pin mismatch/missing by-ref evidence.
- Mandatory SR ladder before `3.C.3`: `20` -> `200` -> `1000`.
- Mode closure requires `fraud` primary and `baseline` secondary proofs.

## Phase plan (3.C.2)
### S1 - Managed execution + state settlement lock
**Intent:** freeze exactly what “managed-only SR acceptance” means for this wave.

**Implementation checklist:**
- [ ] Pin SR runtime surface for acceptance runs (managed execution identity + launch path).
- [ ] Pin SR state backend(s) used for acceptance runs (managed only) and remove local acceptance ambiguity.
- [ ] Pin SR run-config identity inputs (`platform_run_id`, `scenario_run_id`, `run_config_digest`) and where they are sourced.
- [ ] Pin READY re-emit authorization policy and governance override evidence shape.

**DoD checklist:**
- [ ] Acceptance-valid SR execution path is documented and excludes local fallback.
- [ ] Acceptance-valid SR state path is documented and excludes local fallback.
- [ ] Re-emit governance gate is explicit and testable.

### S2 - Oracle-coupled run-facts authority gate
**Intent:** guarantee SR facts view is built from one pinned Oracle identity and by-ref evidence only.

**Implementation checklist:**
- [ ] Enforce explicit Oracle pins (`oracle_engine_run_root`, `oracle_scenario_id`, `oracle_stream_view_root`).
- [ ] Block implicit world selection (`latest` scans, inferred local roots, mixed roots).
- [ ] Ensure facts view includes required Oracle/evidence refs and run-scope pins.
- [ ] Preserve write-once/facts-drift rejection posture on re-entry.

**DoD checklist:**
- [ ] Facts view is by-ref, run-scoped, and immutable for a given run identity.
- [ ] Any Oracle scope mismatch/missing ref fails closed before READY.
- [ ] Evidence refs are consumable by downstream without local-path assumptions.

### S3 - READY contract + idempotency gate
**Intent:** make READY deterministic and safe under at-least-once/retry realities.

**Implementation checklist:**
- [ ] READY payload carries `platform_run_id`, `scenario_run_id`, `run_config_digest`, and facts-view ref.
- [ ] READY idempotency key is stable under same-run re-emit.
- [ ] READY publish ordering remains commit-safe:
  - facts view committed first,
  - status READY committed second,
  - READY publish last.
- [ ] Reject unauthorized cross-run re-emit path by default.

**DoD checklist:**
- [ ] Duplicate/safe retry does not produce semantic drift.
- [ ] READY cannot be emitted without committed facts-view evidence.
- [ ] Cross-run emit without override evidence is blocked fail-closed.

### S4 - Run/operate + obs/gov onboarding gate
**Intent:** treat SR as a managed-operated migration component, not ad-hoc CLI behavior.

**Implementation checklist:**
- [ ] Add SR managed execution surface into `dev_min` run/operate lifecycle.
- [ ] Add SR lifecycle + anomaly + reconciliation outputs into obs/gov corridors.
- [ ] Ensure reporter/conformance can resolve SR run-scoped evidence refs.
- [ ] Capture security/capability boundaries in operated posture.

**DoD checklist:**
- [ ] SR lifecycle is visible in run/operate status/report surfaces.
- [ ] SR governance/reconciliation artifacts are emitted per run.
- [ ] No “component green” claim is possible without meta-layer coverage.

### S5 - SR validation ladder + closure gate
**Intent:** close SR gate objectively before WSP coupled progression.

**Implementation checklist:**
- [ ] Execute `20` smoke in `fraud` mode.
- [ ] Execute `200` acceptance in `fraud` mode.
- [ ] Execute `1000` stress in `fraud` mode.
- [ ] Execute secondary `baseline` mode proof at least on `20` and `200` (or higher if required by settlement).
- [ ] Run negative-path matrix:
  - Oracle pin mismatch,
  - missing required ref,
  - unauthorized cross-run re-emit,
  - duplicate READY replay safety.
- [ ] Record PASS/FAIL + evidence refs in impl map/logbook.

**DoD checklist:**
- [ ] All required ladders are PASS with run-scoped evidence.
- [ ] Negative-path matrix is PASS (fail-closed where expected).
- [ ] SR gate is green and explicitly linked from platform `3.C.2`.

## Stop conditions (blockers)
- Any local runtime/state fallback observed in acceptance evidence.
- READY published without committed facts-view evidence.
- Oracle root/scope ambiguity or by-ref evidence mismatch.
- Cross-run READY emit accepted without governance override evidence.
- Missing run-scoped evidence refs for any claimed PASS rung.

## Security, performance, and operations posture
- Security:
  - no secrets in plan/evidence/logbook artifacts,
  - managed runtime identity must be explicit in acceptance records.
- Performance:
  - ladder timings must be captured at each rung (`20/200/1000`) for trendability.
- Operations:
  - each rung records `KEEP ON` / `TURN OFF NOW` posture for paid surfaces.

## Current status
- S1: not started
- S2: not started
- S3: not started
- S4: not started
- S5: not started
