# Oracle Store Build Plan (dev_substrate, managed substrate only)
_As of 2026-02-11_

## Objective
Close Phase `3.C.1` by migrating Oracle Store usage from local-parity assumptions to `dev_min` managed substrate semantics, with S3 as the only truth authority for Oracle artifacts in this plane.

## Scope
- In scope:
  - Oracle source authority lock for C&I migration wave.
  - Stream-view readiness and by-ref evidence requirements consumed by SR/WSP.
  - Oracle-specific run/operate and obs/gov onboarding requirements.
- Out of scope:
  - Data Engine implementation internals.
  - SR/WSP/IG/EB migration steps beyond Oracle boundary contracts.

## Authority anchors
- `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (`3.C.1`)
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
- Local baseline carry-forward:
  - `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.build_plan.md`

## Non-negotiable migration laws
1. Oracle truth for `dev_substrate` is managed only; local filesystem fallback is forbidden.
2. All Oracle references consumed downstream must be by-ref and run-scoped.
3. Unknown/missing compatibility evidence is fail-closed, not inferred.
4. Oracle gate closes only when run/operate + obs/gov are wired for this boundary.

## Phase plan (Phase 3.C.1 closure track)
### O1. Oracle authority lock (managed source only)
**Intent:** ensure one explicit Oracle root is selected and immutable for the run.

**Implementation checklist:**
- [ ] Resolve `oracle_engine_run_root` and `scenario_id` explicitly from managed substrate configuration.
- [ ] Enforce hard reject when Oracle root resolves to local path semantics under `dev_min`.
- [ ] Record selected Oracle root identity and digest refs in run evidence.

**DoD:**
- [ ] No implicit `latest` root selection.
- [ ] No local-path fallback accepted.
- [ ] Evidence artifact records exact Oracle root ref used for this run.

### O2. Seal + manifest fail-closed verification
**Intent:** prove selected Oracle root is valid and complete enough for stream-view consumption.

**Implementation checklist:**
- [ ] Validate required seal/manifest artifacts exist for selected root.
- [ ] Fail closed when mandatory compatibility/version fields are absent.
- [ ] Emit explicit reason codes for each failure class.

**DoD:**
- [ ] PASS result includes manifest/seal refs.
- [ ] FAIL result includes stable reason code and locator.
- [ ] No permissive/partial mode in `dev_min`.

### O3. Stream-view readiness gate
**Intent:** guarantee WSP-consumable stream-view outputs exist with deterministic ordering keys.

**Implementation checklist:**
- [ ] Verify required outputs under `stream_view/ts_utc/output_id=...`.
- [ ] Verify stream-view locator refs resolve from managed substrate.
- [ ] Ensure output set required by active scenario is complete before READY progression.

**DoD:**
- [ ] Required output IDs are present and resolvable.
- [ ] Missing output ID fails gate before SR/WSP progression.
- [ ] Evidence captures output-level refs/digests by-ref.

### O4. SR/WSP boundary contract emission
**Intent:** expose Oracle-derived refs in a single run-scoped contract basis consumed by SR/WSP.

**Implementation checklist:**
- [ ] Ensure SR run facts include Oracle refs pinned to the selected Oracle root.
- [ ] Ensure WSP stream identity resolves to the same root/scope tuple.
- [ ] Validate no mixed-root contract state in one run.

**DoD:**
- [ ] SR and WSP contract refs point to identical Oracle root identity.
- [ ] Root mismatch is fail-closed with explicit gate refusal.
- [ ] Contract basis is recorded in matrix evidence.

### O5. Run/operate onboarding for Oracle boundary
**Intent:** prevent Oracle checks from being matrix-only by integrating into platform run lifecycle.

**Implementation checklist:**
- [ ] Add Oracle readiness step into `dev_min` run/operate workflow.
- [ ] Add Oracle failure signatures and remediation hints to operator outputs.
- [ ] Include Oracle gate status in phase snapshots/reporter surfaces.

**DoD:**
- [ ] Oracle gate is visible in run lifecycle output.
- [ ] Oracle gate failures are diagnosable without source code lookup.
- [ ] Oracle step blocks downstream C&I startup when not green.

### O6. Obs/Gov onboarding for Oracle boundary
**Intent:** ensure Oracle posture is auditable in governance/reporting planes.

**Implementation checklist:**
- [ ] Emit Oracle gate lifecycle events for PASS/FAIL transitions.
- [ ] Emit evidence refs required for replay/audit of Oracle selection and readiness.
- [ ] Preserve append-only governance reporting posture.

**DoD:**
- [ ] Oracle PASS/FAIL appears in governance/report outputs.
- [ ] Evidence refs are by-ref and run-scoped.
- [ ] Oracle gate state can be reconstructed for audit.

### O7. Security, retention, and cost sentinel checks
**Intent:** enforce production-minded dev posture before accepting Oracle migration closure.

**Implementation checklist:**
- [ ] Confirm no sensitive tokens/secrets are written into impl maps/logbook artifacts.
- [ ] Confirm retention/lifecycle expectations for Oracle evidence prefixes are documented.
- [ ] Record keep-on/turn-off decision for resources used during Oracle gate runs.

**DoD:**
- [ ] Security handling posture recorded.
- [ ] Cost sentinel decision recorded for each Oracle validation run.
- [ ] Retention intent is explicit for Oracle evidence surfaces.

### O8. Oracle matrix and closure gate
**Intent:** mark Phase `3.C.1` complete with explicit evidence and residual-risk posture.

**Implementation checklist:**
- [ ] Run Oracle matrix checks on `dev_min` and collect evidence bundle refs.
- [ ] Link evidence in `dev_substrate/platform.impl_actual.md` and logbook.
- [ ] Record residual risks as remediated or explicitly accepted by USER.

**DoD:**
- [ ] Oracle matrix PASS is evidenced and linked.
- [ ] `3.C.1` can be marked complete in platform build plan.
- [ ] No unresolved Oracle drift remains silent.

## Validation matrix expectations
- Mandatory checks:
  - managed-source authority lock PASS,
  - manifest/seal PASS,
  - stream-view readiness PASS,
  - SR/WSP root-coupling PASS.
- Failure policy:
  - any unknown/missing Oracle contract evidence => `FAIL_CLOSED`.

## Current status
- O1: not started
- O2: not started
- O3: not started
- O4: not started
- O5: not started
- O6: not started
- O7: not started
- O8: not started
