# Dev Substrate Deep Plan - M8 (P11 Obs/Gov Closure)
_Status source of truth: `platform.build_plan.md`_  
_This document provides deep planning detail for M8._  
_Last updated: 2026-02-19_

## 0) Purpose
M8 closes `P11 OBS_GOV_CLOSED` on managed substrate by proving:
1. Reporter closeout runs as a one-shot managed task under strict single-writer posture.
2. Run closure evidence bundle is complete, durable, and run-scoped.
3. Replay anchors and reconciliation are coherent against prior phase evidence.
4. Closure marker is written and M9 handoff is published.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (`P11` section)
3. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.build_plan.md`
2. Local M7 handoff:
   - `runs/dev_substrate/m7/20260218T141420Z/m8_handoff_pack.json`
3. Durable M7 handoff:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m8_handoff_pack.json`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`

## 2) Scope Boundary for M8
In scope:
1. P11 authority/handle closure for reporter and Obs/Gov paths.
2. Reporter runtime readiness and lock posture validation.
3. Closure-input evidence readiness checks (from M6/M7 outputs).
4. Reporter one-shot execution and lock contention fail-closed proof.
5. Closure artifact completeness, replay-anchor/reconciliation coherence, and closure marker verification.
6. M8 verdict publication and M9 handoff artifact publication.

Out of scope:
1. P12 teardown operations (M9).
2. M10 semantic/scale certification runs.
3. Any mutation of base truth stores (receipts/audit/timelines).

## 3) M8 Deliverables
1. `M8.A` handle/authority closure snapshot.
2. `M8.B` reporter runtime + lock readiness snapshot.
3. `M8.C` closure input readiness snapshot.
4. `M8.D` single-writer contention probe snapshot.
5. `M8.E` reporter execution snapshot.
6. `M8.F` closure bundle completeness snapshot.
7. `M8.G` replay/reconciliation coherence snapshot.
8. `M8.H` Obs/Gov closure marker snapshot.
9. `M8.I` M8 verdict snapshot (`ADVANCE_TO_M9` or `HOLD_M8`) + `m9_handoff_pack.json`.

## 4) Execution Gate for This Phase
Current posture:
1. M7 is closed through `M7.J` and published `m8_handoff_pack.json`.
2. M8 is active for planning/execution.

Execution block:
1. No M9 execution is allowed before M8 verdict is `ADVANCE_TO_M9`.
2. No M8 closure is allowed if reporter lock discipline is not provable.
3. No manual reporter run is allowed concurrently with any reporter daemon/one-shot for the same run scope.

## 4.1) Anti-Cram Law (Binding for M8)
1. M8 is not execution-ready unless these lanes are explicit:
   - authority/handles
   - identity/IAM + secrets
   - reporter lock backend + contention behavior
   - closure input evidence readiness
   - closure artifact publication + non-secret checks
   - replay/reconciliation coherence
   - rerun/rollback posture
   - runtime budget + cost posture
2. If a missing lane is discovered, execution pauses and plan expansion is mandatory before continuing.

## 4.2) Capability-Lane Coverage Matrix (Must Stay Explicit)
| Capability lane | Primary sub-phase owner | Supporting sub-phases | Minimum PASS evidence |
| --- | --- | --- | --- |
| Authority + handles closure | M8.A | M8.I | zero unresolved required P11 handles |
| Reporter runtime + IAM readiness | M8.B | M8.E | reporter task runtime/role lock-ready |
| Closure-input evidence readiness | M8.C | M8.F/M8.G | required upstream evidence URIs readable |
| Single-writer lock discipline | M8.D | M8.E | contention probe fails closed for second writer |
| Reporter execution | M8.E | M8.F | one-shot reporter completes with lock lifecycle proof |
| Closure bundle completeness | M8.F | M8.H | required closure artifacts exist with run scope |
| Replay/reconciliation coherence | M8.G | M8.I | replay anchors + reconciliation are internally coherent |
| Closure marker + governance outputs | M8.H | M8.I | `run_completed.json` + obs artifacts verified |
| Verdict + M9 handoff | M8.I | - | `ADVANCE_TO_M9` + durable `m9_handoff_pack.json` |

## 5) Work Breakdown (Deep)

### M8.A P11 Authority + Handle Closure
Goal:
1. Close all required P11 handles before any reporter execution.
2. Freeze a deterministic P11 handle matrix for downstream M8 lanes.

Entry conditions:
1. `M7` is `DONE` and `M7.J` handoff artifact is readable.
2. Handoff contract passes:
   - `m8_entry_gate=READY`
   - `overall_pass=true`
   - blockers empty.
3. Active run scope is fixed:
   - `platform_run_id=platform_20260213T214223Z`.

Required inputs:
1. M7 handoff artifacts:
   - local: `runs/dev_substrate/m7/20260218T141420Z/m8_handoff_pack.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m8_handoff_pack.json`.
2. Required P11 handles (registry closure set):
   - reporter runtime:
     - `TD_REPORTER`
     - `ROLE_REPORTER_SINGLE_WRITER`
   - evidence roots and closure outputs:
     - `S3_EVIDENCE_BUCKET`
     - `S3_EVIDENCE_RUN_ROOT_PATTERN`
     - `RUN_CLOSURE_MARKER_PATH_PATTERN`
     - `RUN_REPORT_PATH_PATTERN`
     - `REPLAY_ANCHORS_PATH_PATTERN`
     - `RECONCILIATION_PATH_PATTERN`
     - `ENV_CONFORMANCE_PATH_PATTERN`
   - lock contract:
     - `REPORTER_LOCK_BACKEND`
     - `REPORTER_LOCK_KEY_PATTERN`
   - closeout input evidence patterns:
     - `RECEIPT_SUMMARY_PATH_PATTERN`
     - `KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN`
     - `RTDL_CORE_EVIDENCE_PATH_PATTERN`
     - `DECISION_LANE_EVIDENCE_PATH_PATTERN`
     - `CASE_EVIDENCE_PATH_PATTERN`
     - `LABEL_EVIDENCE_PATH_PATTERN`.
3. Authority sources:
   - `platform.build_plan.md`
   - `dev_min_spine_green_v0_run_process_flow.md` (`P11`)
   - `dev_min_handles.registry.v0.md`.

Preparation checks:
1. Validate M7 handoff run-scope conformance (`platform_run_id`, `m7_execution_id` present and non-placeholder).
2. Validate each required handle key exists in registry and resolves to non-empty concrete value.
3. Validate no wildcard/placeholder posture in required closure set.
4. Validate path-pattern handles preserve run-scope placeholder contract (`{platform_run_id}` where required).

Deterministic verification algorithm (M8.A):
1. Load M7 handoff (local preferred, durable fallback); unreadable/invalid -> `M8A-B1`.
2. Verify handoff gate (`READY`, `overall_pass=true`, blockers empty); mismatch -> `M8A-B1`.
3. Resolve required handle keys from registry into closure matrix:
   - record `value`, `source`, `resolved=true/false`.
4. Fail closed on unresolved required handle -> `M8A-B2`.
5. Detect wildcard/placeholder posture in required set -> `M8A-B3`.
6. Execute lightweight materialization probes:
   - reporter task/role handles present and parseable,
   - evidence bucket/root handles parseable for run-scope rendering.
   Probe failure -> `M8A-B4`.
7. Emit `m8_a_handle_closure_snapshot.json` locally with:
   - run scope and handoff refs,
   - required handle matrix (resolved/unresolved),
   - wildcard/placeholder findings,
   - probe results,
   - blocker list + `overall_pass`.
8. Publish snapshot durably.

Tasks:
1. Validate M7->M8 handoff invariants (`platform_run_id`, verdict, blocker-free posture).
2. Probe required P11 handles from registry and build deterministic closure matrix.
3. Emit and publish `m8_a_handle_closure_snapshot.json` (local + durable).

Required snapshot fields (`m8_a_handle_closure_snapshot.json`):
1. `phase`, `phase_id`, `platform_run_id`, `m8_execution_id`.
2. `source_m7_handoff_local`, `source_m7_handoff_uri`.
3. `required_handle_keys`, `resolved_handle_count`, `unresolved_handle_count`.
4. `unresolved_handle_keys`, `wildcard_handle_keys`, `placeholder_handle_keys`.
5. `probe_results`, `blockers`, `overall_pass`, `elapsed_seconds`.

Runtime budget:
1. `M8.A` target budget: <= 10 minutes wall clock.
2. Over-budget execution remains fail-closed unless USER waiver is explicitly recorded.

DoD:
- [ ] Required handles are explicit and probe-pass.
- [ ] Placeholder/wildcard required handles are absent.
- [ ] Snapshot exists locally and durably.

Planning status:
1. `M8.A` is now execution-grade (entry/precheck/algorithm/snapshot contract pinned).
2. Execution attempted on `2026-02-19` under `m8_execution_id=m8_20260219T073801Z`.
3. Lane is currently blocked fail-closed on `M8A-B2` until reporter handles are concretely materialized.

Execution closure (2026-02-19):
1. Snapshot emitted locally:
   - `runs/dev_substrate/m8/20260219T073801Z/m8_a_handle_closure_snapshot.json`.
2. Snapshot published durably:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T073801Z/m8_a_handle_closure_snapshot.json`.
3. Result:
   - `overall_pass=false`,
   - `resolved_handle_count=15`,
   - `unresolved_handle_count=2`.
4. Blocking unresolved required handles:
   - `ROLE_REPORTER_SINGLE_WRITER`,
   - `TD_REPORTER`.
5. M8.A remains open until required reporter handles are bound to concrete values and rerun passes.

Blockers:
1. `M8A-B1`: M7 handoff invalid or unreadable.
2. `M8A-B2`: required handle unresolved.
3. `M8A-B3`: placeholder/wildcard required handle detected.
4. `M8A-B4`: snapshot write/upload failure.
5. `M8A-B5`: run-scope mismatch between M7 handoff and active execution scope.

### M8.B Reporter Runtime + Lock Readiness
Goal:
1. Prove reporter task runtime posture and lock backend readiness.

Tasks:
1. Validate reporter task definition points to managed platform image and non-stub command.
2. Validate IAM posture for reporter role (read upstream evidence, write closure artifacts, logs).
3. Validate lock backend configuration and lock-key derivation for run scope.
4. Emit `m8_b_reporter_readiness_snapshot.json`.

DoD:
- [ ] Reporter task runtime posture is valid and managed.
- [ ] Role and lock backend posture checks pass.
- [ ] Snapshot exists locally and durably.

Blockers:
1. `M8B-B1`: reporter task/runtime command invalid.
2. `M8B-B2`: reporter role capability mismatch.
3. `M8B-B3`: lock backend/key configuration invalid.
4. `M8B-B4`: snapshot write/upload failure.

### M8.C Closure Input Evidence Readiness
Goal:
1. Verify all required closeout inputs are readable before reporter run.

Tasks:
1. Validate readability of required upstream evidence families:
   - ingest summaries (`ig_ready`, receipt/offset/quarantine where applicable),
   - RTDL core summaries,
   - decision-lane summaries,
   - case/label summaries.
2. Verify source artifacts are run-scoped to active `platform_run_id`.
3. Emit `m8_c_input_readiness_snapshot.json`.

DoD:
- [ ] Required input evidence URIs are readable.
- [ ] Run-scope conformance across required input surfaces passes.
- [ ] Snapshot exists locally and durably.

Blockers:
1. `M8C-B1`: required evidence URI missing/unreadable.
2. `M8C-B2`: run-scope mismatch in required evidence.
3. `M8C-B3`: snapshot write/upload failure.

### M8.D Single-Writer Contention Probe
Goal:
1. Prove fail-closed behavior under same-run reporter contention.

Tasks:
1. Trigger controlled contention probe for same `platform_run_id`.
2. Verify only one reporter obtains lock and second writer fails closed.
3. Verify no concurrent writer produces conflicting closure artifacts.
4. Emit `m8_d_single_writer_probe_snapshot.json`.

DoD:
- [ ] Contention probe demonstrates single-writer lock correctness.
- [ ] No conflicting closure writes occur under probe.
- [ ] Snapshot exists locally and durably.

Blockers:
1. `M8D-B1`: lock does not enforce single-writer.
2. `M8D-B2`: concurrent writer succeeds unexpectedly.
3. `M8D-B3`: snapshot write/upload failure.

### M8.E Reporter One-Shot Execution
Goal:
1. Execute reporter closeout for active run scope on managed compute.

Tasks:
1. Invoke one-shot reporter task with run-scope inputs.
2. Verify task completion (`exit=0`) and lock lifecycle in logs (acquire/write/release).
3. Emit `m8_e_reporter_execution_snapshot.json`.

DoD:
- [ ] Reporter task exits successfully.
- [ ] Lock lifecycle is evidenced in runtime logs/snapshot.
- [ ] Snapshot exists locally and durably.

Blockers:
1. `M8E-B1`: reporter task failed or timed out.
2. `M8E-B2`: lock lifecycle evidence incomplete.
3. `M8E-B3`: snapshot write/upload failure.

### M8.F Closure Bundle Completeness
Goal:
1. Verify required closure artifacts exist and are run-scoped.

Tasks:
1. Validate artifact existence:
   - `evidence/runs/<platform_run_id>/run_completed.json`
   - `evidence/runs/<platform_run_id>/obs/run_report.json`
   - `evidence/runs/<platform_run_id>/obs/reconciliation.json`
   - `evidence/runs/<platform_run_id>/obs/replay_anchors.json`
   - `evidence/runs/<platform_run_id>/obs/environment_conformance.json`
   - `evidence/runs/<platform_run_id>/obs/anomaly_summary.json`.
2. Validate each artifact references active run scope.
3. Emit `m8_f_bundle_completeness_snapshot.json`.

DoD:
- [ ] Required closure artifacts exist at pinned paths.
- [ ] Artifact run-scope conformance checks pass.
- [ ] Snapshot exists locally and durably.

Blockers:
1. `M8F-B1`: required closure artifact missing.
2. `M8F-B2`: closure artifact run-scope mismatch.
3. `M8F-B3`: snapshot write/upload failure.

### M8.G Replay Anchors + Reconciliation Coherence
Goal:
1. Verify replay anchors and reconciliation summaries are coherent.

Tasks:
1. Validate replay anchor structure (required topic/partition offsets present).
2. Validate reconciliation arithmetic against prior phase summary counts.
3. Validate no impossible negative/drift deltas in closure summaries.
4. Emit `m8_g_replay_reconciliation_snapshot.json`.

DoD:
- [ ] Replay anchors are structurally complete and coherent.
- [ ] Reconciliation results are coherent with upstream evidence.
- [ ] Snapshot exists locally and durably.

Blockers:
1. `M8G-B1`: replay anchor fields missing/incoherent.
2. `M8G-B2`: reconciliation mismatch beyond allowed rules.
3. `M8G-B3`: snapshot write/upload failure.

### M8.H Closure Marker + Obs/Gov Surface Verification
Goal:
1. Confirm closure marker and governance outputs satisfy P11 close condition.

Tasks:
1. Verify `run_completed.json` exists and indicates completed run posture.
2. Verify `environment_conformance.json` and `anomaly_summary.json` are present and run-scoped.
3. Verify outputs remain derived summaries (no base-truth mutation signal).
4. Emit `m8_h_obs_gov_closure_snapshot.json`.

DoD:
- [ ] Closure marker exists with correct run scope.
- [ ] Environment-conformance and anomaly-summary outputs are present and valid.
- [ ] Snapshot exists locally and durably.

Blockers:
1. `M8H-B1`: closure marker missing/invalid.
2. `M8H-B2`: required Obs/Gov output missing/invalid.
3. `M8H-B3`: snapshot write/upload failure.

### M8.I P11 Verdict + M9 Handoff
Goal:
1. Compute deterministic M8 verdict and publish M9 handoff artifact.

Tasks:
1. Roll up blockers from `M8.A..M8.H` with source provenance.
2. Compute P11 predicates:
   - single-writer verified,
   - closure bundle complete,
   - replay/reconciliation coherent,
   - closure marker valid.
3. Set verdict:
   - predicates all true + blocker rollup empty => `ADVANCE_TO_M9`
   - else => `HOLD_M8`.
4. Publish:
   - `m8_i_verdict_snapshot.json`
   - `m9_handoff_pack.json`
   locally and durably.

DoD:
- [ ] M8 verdict snapshot is deterministic and reproducible.
- [ ] M9 handoff artifact is complete and non-secret.
- [ ] Both artifacts exist locally and durably.

Blockers:
1. `M8I-B1`: source snapshot missing/unreadable.
2. `M8I-B2`: predicate evaluation incomplete/invalid.
3. `M8I-B3`: blocker rollup non-empty.
4. `M8I-B4`: verdict/handoff write or upload failure.
5. `M8I-B5`: handoff payload non-secret policy violation.

## 6) Runtime Budget Gates
1. `M8.A`: <= 10 minutes
2. `M8.B`: <= 10 minutes
3. `M8.C`: <= 10 minutes
4. `M8.D`: <= 15 minutes
5. `M8.E`: <= 15 minutes
6. `M8.F`: <= 10 minutes
7. `M8.G`: <= 10 minutes
8. `M8.H`: <= 10 minutes
9. `M8.I`: <= 10 minutes
10. M8 total target: <= 100 minutes wall clock

Rule:
1. Any over-budget lane remains fail-closed unless USER waiver is explicitly recorded.

## 7) M8 Evidence Contract (Pinned for Execution)
Evidence roots:
1. Run-scoped evidence root:
   - `evidence/runs/<platform_run_id>/`
2. M8 control-plane evidence root:
   - `evidence/dev_min/run_control/<m8_execution_id>/`
3. `<m8_execution_id>` format:
   - `m8_<YYYYMMDDTHHmmssZ>`.

Minimum run-scoped closure artifacts:
1. `evidence/runs/<platform_run_id>/run_completed.json`
2. `evidence/runs/<platform_run_id>/obs/run_report.json`
3. `evidence/runs/<platform_run_id>/obs/reconciliation.json`
4. `evidence/runs/<platform_run_id>/obs/replay_anchors.json`
5. `evidence/runs/<platform_run_id>/obs/environment_conformance.json`
6. `evidence/runs/<platform_run_id>/obs/anomaly_summary.json`

Minimum M8 control-plane artifacts:
1. `evidence/dev_min/run_control/<m8_execution_id>/m8_a_handle_closure_snapshot.json`
2. `evidence/dev_min/run_control/<m8_execution_id>/m8_b_reporter_readiness_snapshot.json`
3. `evidence/dev_min/run_control/<m8_execution_id>/m8_c_input_readiness_snapshot.json`
4. `evidence/dev_min/run_control/<m8_execution_id>/m8_d_single_writer_probe_snapshot.json`
5. `evidence/dev_min/run_control/<m8_execution_id>/m8_e_reporter_execution_snapshot.json`
6. `evidence/dev_min/run_control/<m8_execution_id>/m8_f_bundle_completeness_snapshot.json`
7. `evidence/dev_min/run_control/<m8_execution_id>/m8_g_replay_reconciliation_snapshot.json`
8. `evidence/dev_min/run_control/<m8_execution_id>/m8_h_obs_gov_closure_snapshot.json`
9. `evidence/dev_min/run_control/<m8_execution_id>/m8_i_verdict_snapshot.json`
10. `evidence/dev_min/run_control/<m8_execution_id>/m9_handoff_pack.json`

Notes:
1. M8 artifacts must be non-secret.
2. Any secret-bearing payload in M8 artifacts is a hard blocker.
3. Missing required evidence object keeps M8 in `HOLD_M8`.

## 8) M8 Completion Checklist
- [ ] M8.A complete
- [ ] M8.B complete
- [ ] M8.C complete
- [ ] M8.D complete
- [ ] M8.E complete
- [ ] M8.F complete
- [ ] M8.G complete
- [ ] M8.H complete
- [ ] M8.I complete

## 9) Exit Criteria
M8 can be marked `DONE` only when:
1. Section 8 checklist is fully complete.
2. Required run-scoped and control-plane artifacts are durable and readable.
3. `m8_i_verdict_snapshot.json` has `verdict=ADVANCE_TO_M9` and `overall_pass=true`.
4. `m9_handoff_pack.json` is published and non-secret.
5. USER confirms progression to M9 activation.

Note:
1. This file does not change phase status.
2. Status transition is made only in `platform.build_plan.md`.
