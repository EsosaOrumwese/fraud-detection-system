# Scenario Runner Implementation Map (dev_substrate)
_As of 2026-02-11_

## Entry: 2026-02-11 1:11PM - Pre-change lock: rewrite SR dev_substrate build plan for full-migration 3.C.2 posture

### Trigger
USER requested a dedicated `dev_substrate` SR build plan aligned to the latest full-migration direction and `3.C.2` lock set.

### Problem framing
Existing SR build plan in `dev_substrate` was a lightweight starter:
1. it did not explicitly encode managed-only acceptance runtime/state posture,
2. it did not include the newly locked `3.C.2` repins (re-emit governance, full strict gate stance),
3. it did not define closure-grade ladder/negative-path expectations for component gate progression.

### Authorities and constraints used
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (`3.C.2` locked gate text).
2. `docs/model_spec/platform/component-specific/scenario_runner.design-authority.md`.
3. `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`.
4. `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`.
5. Baseline continuity:
   - `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md`

### Alternatives considered
1. Keep starter SR plan and rely on platform-level `3.C.2` only.
- Rejected: component plan would remain under-specified and easier to drift in execution.
2. Write an exhaustive implementation checklist with code-level steps.
- Rejected for now: premature detail before active coding sections begin.
3. Rewrite SR plan with phase-grade gates tied directly to `3.C.2` lock set.
- Selected: best balance of executable clarity and progressive elaboration.

### Decisions locked before edit
1. SR plan will explicitly carry full-migration repins (managed-only runtime/state acceptance).
2. SR plan will include explicit stop conditions for local fallback and cross-run re-emit violations.
3. SR plan will pin mandatory ladder closure (`20 -> 200 -> 1000`) and mode proof (`fraud` primary + `baseline` secondary).
4. Plan remains a planning artifact (no runtime behavior changes in this pass).

## Entry: 2026-02-11 1:11PM - Applied SR dev_substrate build-plan rewrite

### What changed
Replaced the starter SR build plan with a closure-grade `3.C.2` plan at:
- `docs/model_spec/platform/implementation_maps/dev_substrate/scenario_runner.build_plan.md`

### Structure now encoded
1. Purpose + binding planning rules.
2. Explicit full-migration repin inheritance from platform `3.C.2`.
3. Five SR migration gates:
- `S1` managed execution/state settlement lock,
- `S2` Oracle-coupled facts authority gate,
- `S3` READY contract/idempotency gate,
- `S4` run/operate + obs/gov onboarding gate,
- `S5` validation ladder + closure gate.
4. Explicit stop conditions.
5. Security/performance/operations posture hooks.
6. Rolling status table (`S1..S5` not started).

### Why this is the selected shape
It makes SR component execution auditable and directly traceable to the platform-level full-migration law without waiting for implementation turns to clarify acceptance boundaries.

### Validation
1. Manual consistency check against platform `3.C.2` lock bullets.
2. Confirmed plan still follows progressive elaboration structure with phase-level DoD checklists.

### Cost posture
Docs-only pass; no paid services touched.

## Entry: 2026-02-11 1:18PM - Pre-change lock: implement SR S1 managed execution/state settlement gate

### Trigger
USER requested immediate implementation of `S1` in `dev_substrate/scenario_runner.build_plan.md` with explicit decision documentation.

### S1 closure target
Lock and enforce (not just describe) four S1 requirements:
1. acceptance-valid SR runtime surface is managed-only with explicit execution identity + launch ref,
2. acceptance-valid SR state corridor is managed-only (no sqlite/local fs fallback),
3. READY/run identity sources (`platform_run_id`, `scenario_run_id`, `run_config_digest`) are explicit and auditable,
4. re-emit governance policy is explicit and testable for same-run default versus cross-run override.

### Authorities and constraints used
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (`3.C.2` repins).
2. `docs/model_spec/platform/implementation_maps/dev_substrate/scenario_runner.build_plan.md` (`S1` checklist + DoD).
3. `docs/model_spec/platform/component-specific/scenario_runner.design-authority.md`.
4. `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`.
5. Existing SR runtime behavior in:
- `src/fraud_detection/scenario_runner/config.py`
- `src/fraud_detection/scenario_runner/runner.py`
- `src/fraud_detection/scenario_runner/models.py`

### Problem framing
Current SR code allows ambiguous acceptance posture:
1. no dedicated managed-only settlement mode in wiring,
2. no explicit fail-closed gate for local runtime/state fallback under dev-min acceptance,
3. re-emit model lacks explicit cross-run governance override shape,
4. no auditable governance event that records identity source resolution for READY pins.

### Options considered
1. Do docs-only S1 closure with no runtime checks.
- Rejected: does not satisfy "implementation" and leaves acceptance ambiguity in code paths.
2. Implement full SR dev-min runtime orchestration (managed launcher + full component migration) in S1.
- Rejected: too broad; that crosses into S4 and risks partial, drifting implementation.
3. Implement settlement lock surfaces now (config/model/runtime enforcement + phase preflight tool), leaving deeper runtime orchestration to later gates.
- Selected: closes S1 with auditable, testable guardrails and no S2/S3/S4 scope leakage.

### Decisions locked before edits
1. Add explicit SR settlement knobs in wiring profile (`acceptance_mode`, `execution_mode`, `state_mode`, identity/launch refs, re-emit policy controls).
2. Add fail-closed runtime validation for `dev_min_managed` acceptance mode in `ScenarioRunner.__init__`.
3. Extend re-emit request contract with explicit cross-run override evidence shape and optional target platform run override pin.
4. Enforce same-platform-run re-emit default in code when configured; cross-run requires governance override evidence.
5. Emit governance fact for READY identity source mapping (`platform_run_id`, `scenario_run_id`, `run_config_digest` sources).
6. Add `3.C.2 S1` preflight checker script + settlement YAML + make target so operators can validate posture before acceptance runs.

### Planned edits
1. Runtime and contract surfaces:
- `src/fraud_detection/scenario_runner/config.py`
- `src/fraud_detection/scenario_runner/models.py`
- `src/fraud_detection/scenario_runner/runner.py`
- `src/fraud_detection/scenario_runner/cli.py`
- `docs/model_spec/platform/contracts/scenario_runner/reemit_request.schema.yaml`
2. Dev-substrate S1 preflight surfaces:
- `config/platform/dev_substrate/phase3/scenario_runner_settlement_v0.yaml` (new)
- `config/platform/sr/wiring_dev_min.yaml` (new)
- `scripts/dev_substrate/phase3c2_sr_settlement_lock.py` (new)
- `makefile` (new `platform-dev-min-phase3c2-s1-preflight` target + tunables)
3. Validation/tests:
- extend SR re-emit tests for cross-run override policy behavior.
4. Documentation closure:
- update `scenario_runner.build_plan.md` S1 checklist/status,
- append applied implementation entry here,
- append action entry in `docs/logbook/02-2026/2026-02-11.md`.

### Cost posture
Code/docs/test pass only; no paid cloud resources should be touched.

## Entry: 2026-02-11 1:26PM - Applied S1 managed settlement lock implementation (runtime + preflight + tests)

### Applied code and config changes
1. SR wiring/config surface expanded for S1 settlement pins:
- `src/fraud_detection/scenario_runner/config.py`
  - added explicit settlement fields:
    - `acceptance_mode`,
    - `execution_mode`,
    - `execution_launch_ref`,
    - `execution_identity_env`,
    - `state_mode`,
    - `reemit_same_platform_run_only`,
    - `reemit_cross_run_override_required`,
    - `reemit_cross_run_reason_allowlist`.
  - added `${ENV}` / `${ENV:-default}` expansion for `load_wiring` and `load_policy` so dev-min wiring can be env-driven without ad-hoc wrappers.

2. Re-emit governance contract + model enforcement:
- `src/fraud_detection/scenario_runner/models.py`
  - added `ReemitGovernanceOverride` model.
  - extended `ReemitRequest` with:
    - `emit_platform_run_id`,
    - `cross_run_override`.
- `docs/model_spec/platform/contracts/scenario_runner/reemit_request.schema.yaml`
  - added schema support for `emit_platform_run_id` and `cross_run_override` evidence object.
- `src/fraud_detection/scenario_runner/cli.py`
  - added re-emit args:
    - `--emit-platform-run-id`,
    - `--cross-run-override-json`.

3. SR runtime fail-closed settlement enforcement:
- `src/fraud_detection/scenario_runner/runner.py`
  - added `_validate_settlement_lock()` in initializer.
  - `dev_min_managed` mode now fails closed if:
    - execution/state mode are not `managed`,
    - execution launch ref/identity env are missing,
    - execution identity env value is missing,
    - object store is not `s3://`,
    - control bus kind is `file`,
    - authority store DSN is missing or sqlite.
  - control-bus builder now fails closed on unknown kinds (no implicit fallback from unknown kind to file bus).
  - added cross-run re-emit scope checks:
    - same-platform-run default when configured,
    - cross-run requires governance override evidence,
    - optional reason-code allowlist enforcement.
  - added governance event emission for approved cross-run override.
  - added auditable READY identity-source governance fact:
    - `GOV_RUN_IDENTITY_SOURCES` with source mapping for
      `platform_run_id`, `scenario_run_id`, and `run_config_digest`.

4. Dev-substrate S1 settlement artifacts:
- added `config/platform/dev_substrate/phase3/scenario_runner_settlement_v0.yaml`.
- added `config/platform/sr/wiring_dev_min.yaml`.
- added `scripts/dev_substrate/phase3c2_sr_settlement_lock.py` with `preflight` command for S1 fail-closed validation.
- `makefile` updates:
  - new vars:
    - `DEV_MIN_PHASE3C2_OUTPUT_ROOT`,
    - `DEV_MIN_PHASE3C2_SETTLEMENT`,
    - `DEV_MIN_PHASE3C2_SR_WIRING`.
  - new target:
    - `platform-dev-min-phase3c2-s1-preflight`.

5. Test coverage updates:
- `tests/services/scenario_runner/test_reemit.py`
  - added cross-run blocked-without-override case,
  - added cross-run allowed-with-override case.
- added `tests/services/scenario_runner/test_settlement_lock.py`
  - verifies `dev_min_managed` lock fails closed on local fallback posture.

### Validation executed
1. `python -m py_compile` on modified/new Python files (`PASS`).
2. `.\.venv\Scripts\python.exe -m pytest tests/services/scenario_runner/test_reemit.py tests/services/scenario_runner/test_settlement_lock.py -q` (`PASS`, 10 passed).
3. `python scripts/dev_substrate/phase3c2_sr_settlement_lock.py --help` (`PASS`).
4. `make -n platform-dev-min-phase3c2-s1-preflight` render check (`PASS`).
5. Preflight sample run with explicit local env overrides:
- `python scripts/dev_substrate/phase3c2_sr_settlement_lock.py preflight --settlement ... --wiring ...` (`PASS`).
- evidence written under `runs/fraud-platform/dev_substrate/phase3/phase3c2_sr_s1_preflight_*.json`.

### S1 closure assessment
`S1` checklists in `scenario_runner.build_plan.md` are now marked complete because:
1. managed runtime/state posture is both documented and code-enforced (fail-closed),
2. identity source mapping for READY pins is explicit and auditable,
3. re-emit governance override gate is explicit, schema-backed, and test-covered.

### Cost posture
Implementation + local validation only; no paid cloud resources/services touched in this pass.

## Entry: 2026-02-11 1:39PM - Corrective pre-change lock: start S2 Oracle-coupled authority implementation (partial closure)

### Trigger
USER requested proceeding with what can be implemented for SR `S2` before Oracle stream-sort completion.

### Corrective note
Initial code hooks for S2 were started immediately to maintain execution momentum. This entry captures the intended decision path explicitly so the implementation trail remains auditable.

### S2 scope now (implementable before stream-sort complete)
1. Enforce explicit Oracle pins in SR runtime posture for `dev_min_managed`:
- `oracle_engine_run_root`,
- `oracle_scenario_id`,
- `oracle_stream_view_root`.
2. Block implicit/ambiguous world selection:
- reject `latest/current/wildcard` selectors,
- reject request-root mismatch versus pinned Oracle root,
- reject scenario mismatch versus pinned Oracle scenario.
3. Ensure run facts include by-ref Oracle context needed downstream:
- scenario id,
- stream view root,
- per-output stream-view refs.
4. Preserve write-once drift behavior already owned by ledger:
- `FACTS_VIEW_DRIFT`,
- `READY_SIGNAL_DRIFT`.

### Out-of-scope for this S2 pass
1. Positive acceptance closure against real stream-view artifacts (requires completed sync + stream-sort).
2. Coupled-chain acceptance progression into later `3.C.*` gates.

### Planned implementation surfaces
1. Runtime/config:
- `src/fraud_detection/scenario_runner/config.py`
- `src/fraud_detection/scenario_runner/runner.py`
- `config/platform/sr/wiring_dev_min.yaml`
2. Contract schema extension for Oracle by-ref context in facts/ready:
- `docs/model_spec/platform/contracts/scenario_runner/run_facts_view.schema.yaml`
- `docs/model_spec/platform/contracts/scenario_runner/run_ready_signal.schema.yaml`
3. Tests:
- add S2-focused tests for Oracle scope mismatch handling and Oracle ref enrichment.
4. Documentation status:
- update S2 status in build plan as implementation-in-progress if acceptance remains pending.

### Cost posture
Local implementation/testing only; no paid services should be touched in this pass.

## Entry: 2026-02-11 1:44PM - Applied S2 implementable scope (Oracle pin gate + by-ref stream refs) with acceptance pending

### What was implemented now
1. Explicit Oracle pin surfaces in SR wiring profile:
- `src/fraud_detection/scenario_runner/config.py`
  - added:
    - `oracle_scenario_id`,
    - `oracle_stream_view_root`.
- `config/platform/sr/wiring_dev_min.yaml`
  - now wires:
    - `oracle_scenario_id: ${DEV_MIN_ORACLE_SCENARIO_ID}`,
    - `oracle_stream_view_root: ${DEV_MIN_ORACLE_STREAM_VIEW_ROOT}`.

2. Fail-closed Oracle scope enforcement before SR run authority resolution:
- `src/fraud_detection/scenario_runner/runner.py`
  - `submit_run` now runs `_validate_oracle_scope(...)` and rejects fail-closed before planning/READY if:
    - required Oracle pins are missing,
    - pinned/request roots mismatch,
    - scenario pin mismatches,
    - root/scope selectors are ambiguous (`latest/current/wildcards`),
    - stream-view root is outside pinned engine-root stream-view scope.
  - rejection is persisted as `ORACLE_SCOPE_REJECTED` event with explicit reason code.

3. Managed-settlement lock strengthened for Oracle pin posture:
- `src/fraud_detection/scenario_runner/runner.py`
  - `_validate_settlement_lock()` for `dev_min_managed` now also requires:
    - `oracle_engine_run_root`,
    - `oracle_scenario_id`,
    - `oracle_stream_view_root`,
    - managed `s3://` schemes,
    - non-ambiguous selectors,
    - stream-view scope under `oracle_engine_run_root/stream_view/`.

4. Facts-view Oracle by-ref enrichment (S2 contract surface):
- `src/fraud_detection/scenario_runner/runner.py`
  - `_build_oracle_pack_ref(...)` now adds:
    - `scenario_id`,
    - `stream_view_root`,
    - `stream_view_output_refs` (per intended output id).
  - in `dev_min_managed`, `_validate_stream_view_output_refs(...)` fail-closes before READY if required output stream-view artifacts are missing:
    - `_stream_view_manifest.json`,
    - `_stream_sort_receipt.json`,
    - `*.parquet` parts.

5. Contract schema updates for new by-ref fields:
- `docs/model_spec/platform/contracts/scenario_runner/run_facts_view.schema.yaml`
- `docs/model_spec/platform/contracts/scenario_runner/run_ready_signal.schema.yaml`
  - `oracle_pack_ref` now supports:
    - `scenario_id`,
    - `stream_view_root`,
    - `stream_view_output_refs`.
- `docs/model_spec/platform/contracts/scenario_runner/README.md`
  - updated compatibility note for these refs.

6. S2 test coverage added:
- `tests/services/scenario_runner/test_oracle_authority_s2.py` (new)
  - request-root mismatch fail-closed,
  - scenario mismatch fail-closed,
  - oracle pack ref enrichment with stream refs,
  - fail-closed when stream-view output artifacts are missing,
  - pass path when required artifacts are present.

### Validation executed
1. `py_compile` for changed S2 files (`PASS`).
2. `.\.venv\Scripts\python.exe -m pytest tests/services/scenario_runner/test_reemit.py tests/services/scenario_runner/test_settlement_lock.py tests/services/scenario_runner/test_oracle_authority_s2.py -q` (`PASS`, 15 passed).

### S2 status assessment
S2 implementation surfaces are now in place and enforce fail-closed Oracle scope behavior. Gate acceptance remains pending real Oracle stream-sort completion and live-run positive proof against managed artifacts.

### Cost posture
Local implementation/testing only; no paid services touched.
