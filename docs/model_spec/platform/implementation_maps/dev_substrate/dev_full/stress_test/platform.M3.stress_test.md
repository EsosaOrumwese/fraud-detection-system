# Dev Substrate Stress Plan - M3 (Run Pinning + Orchestrator Readiness)
_Status source of truth: `platform.stress_test.md`_
_This document provides deep stress-planning detail for M3._
_Track: `dev_full` only_
_As of 2026-03-03_

## 0) Purpose
M3 stress validates that run pinning and orchestrator-entry behavior stay deterministic under realistic concurrency, retries, and controlled fault conditions before M4 runtime-lane stress begins.

M3 stress must prove:
1. run identity and config-digest surfaces are deterministic and non-colliding under stress,
2. orchestrator entry and run-lock posture remain fail-closed under contention,
3. cross-run mixing is prevented across retries/restarts,
4. run evidence and handoff artifacts remain complete/readable within runtime and spend envelopes.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M3.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s5_20260303T173815Z/stress/m2_execution_summary.json`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
3. `docs/model_spec/platform/contracts/scenario_runner/run_record.schema.yaml`

## 2) Stage-A Findings (M3)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M3-ST-F1` | `PREVENT` | M3 run pinning uses coupled identity + digest + orchestrator surfaces; inline stress plan is too coarse for fail-closed execution. | Create dedicated M3 stress authority and explicit stage gates before run launch. |
| `M3-ST-F2` | `PREVENT` | Symbolic-handle chains (identity/orchestrator/evidence roots) can drift from runner interpretation if not explicitly resolved each run. | Require handle-chain resolution and placeholder guard in `S0/S1`. |
| `M3-ST-F3` | `PREVENT` | Orchestrator lock/contention behavior under concurrent run activation is high-risk for cross-run mixing. | Add explicit concurrent activation stress window with lock/correlation invariants in `S2`. |
| `M3-ST-F4` | `OBSERVE` | Deterministic run-id collision handling path is rarely exercised in normal execution. | Add bounded collision and stale-lock failure injection in `S3`. |
| `M3-ST-F5` | `OBSERVE` | Retry and rerun discipline can leave stale evidence/partial states if not audited post-remediation. | Enforce selective-rerun policy and before/after evidence in `S4`. |
| `M3-ST-F6` | `OBSERVE` | Cost/runtime posture may regress when orchestrator contention windows are expanded. | Track runtime/spend envelopes across all M3 windows and gate in `S5`. |
| `M3-ST-F7` | `ACCEPT` | M2 closure is green with explicit `M3_READY` recommendation and zero open blockers. | Use M2 S5 output as authoritative entry gate for M3 activation. |

## 3) Scope Boundary for M3 Stress
In scope:
1. run pin determinism and collision law under stress.
2. orchestrator-entry/run-lock behavior under concurrency and retries.
3. correlation/run-scope isolation checks for cross-run mixing prevention.
4. run-control evidence durability/completeness under stress windows.
5. M4 handoff recommendation (`GO`/`NO_GO`) from M3 closure rollup.

Out of scope:
1. runtime lane throughput/latency stress (`M4+`).
2. oracle/ingress streaming execution (`M5+`).
3. broad substrate reprovisioning unrelated to M3 closure.

## 4) M3 Stress Handle Packet (Pinned)
1. `M3_STRESS_PROFILE_ID = "run_pinning_orchestrator_stress_v0"`.
2. `M3_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m3_blocker_register.json"`.
3. `M3_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m3_execution_summary.json"`.
4. `M3_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m3_decision_log.json"`.
5. `M3_STRESS_REQUIRED_ARTIFACTS = "m3_stagea_findings.json,m3_lane_matrix.json,m3_probe_latency_throughput_snapshot.json,m3_control_rail_conformance_snapshot.json,m3_secret_safety_snapshot.json,m3_cost_outcome_receipt.json,m3_blocker_register.json,m3_execution_summary.json,m3_decision_log.json"`.
6. `M3_STRESS_MAX_RUNTIME_MINUTES = 120`.
7. `M3_STRESS_MAX_SPEND_USD = 20`.
8. `M3_STRESS_BASELINE_CONCURRENT_RUNS = 2`.
9. `M3_STRESS_BURST_CONCURRENT_RUNS = 6`.
10. `M3_STRESS_WINDOW_MINUTES = 10`.
11. `M3_STRESS_RUN_ID_REGEX = "^platform_[0-9]{8}T[0-9]{6}Z(_[0-9]{2})?$"`.
12. `M3_STRESS_RUN_ID_COLLISION_RETRY_CAP = 20`.
13. `M3_STRESS_EXPECTED_NEXT_GATE_ON_PASS = "M4_READY"`.

Registry-backed required handles for execution:
1. `FIELD_PLATFORM_RUN_ID`
2. `FIELD_SCENARIO_RUN_ID`
3. `FIELD_CONFIG_DIGEST`
4. `CONFIG_DIGEST_ALGO`
5. `CONFIG_DIGEST_FIELD`
6. `SCENARIO_EQUIVALENCE_KEY_INPUT`
7. `SCENARIO_EQUIVALENCE_KEY_CANONICAL_FIELDS`
8. `SCENARIO_EQUIVALENCE_KEY_CANONICALIZATION_MODE`
9. `SCENARIO_RUN_ID_DERIVATION_MODE`
10. `S3_EVIDENCE_BUCKET`
11. `S3_EVIDENCE_RUN_ROOT_PATTERN`
12. `RUN_PIN_PATH_PATTERN`
13. `EVIDENCE_RUN_JSON_KEY`
14. `SFN_PLATFORM_RUN_ORCHESTRATOR_V0`
15. `SR_READY_COMMIT_AUTHORITY`
16. `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`

## 5) Capability-Lane Coverage (Phase-Coverage Law)
| Capability lane | M3 stress stage owner | Minimum PASS evidence |
| --- | --- | --- |
| Authority + handles | `S0` | required M3 handle closure snapshot, zero unresolved placeholders |
| Identity + digest determinism | `S1` | deterministic run-id/digest reproducibility snapshot |
| Orchestrator + lock contention | `S2` | concurrent run activation snapshot with no cross-run mixing |
| Failure detection + recovery | `S3` | deterministic injection classification + recovery snapshot |
| Selective remediation + rerun | `S4` | before/after blocker closure evidence for failed windows |
| Cost/runtime closure + handoff | `S5` | closure rollup with `M4_READY` recommendation and receipt |

## 6) Stress Topology (M3)
1. Component sequence:
   - `M3.A/B/C` (handle + identity + digest),
   - `M3.D/E/F` (orchestrator + evidence + handoff),
   - `M3.G/H/I/J` (rerun policy + cost + gate rollup + closure).
2. Plane sequence:
   - `identity_digest_plane`,
   - `orchestrator_lock_plane`,
   - `evidence_cost_plane`.
3. Integrated windows:
   - `S1_baseline`,
   - `S2_concurrency`,
   - `S3_failure_injection`.

## 7) Execution Plan (Execution-Grade Runbook)
### 7.1 `M3-ST-S0` - Authority and handle closure gate
Objective:
1. fail-closed validation that M3 stress can run without missing contracts.

Actions:
1. resolve required handles from registry/build authority.
2. verify no required handle remains `TO_PIN`.
3. verify entry evidence from M2 S5 is readable.
4. emit Stage-A findings + lane matrix + blocker register.

Pass gate:
1. required handle set complete and resolved.
2. M2->M3 handoff evidence readable.
3. `M3-ST-F1..F3` closed in blocker register.

Required-handle closure checklist (S0):
1. `FIELD_PLATFORM_RUN_ID`
2. `FIELD_SCENARIO_RUN_ID`
3. `FIELD_CONFIG_DIGEST`
4. `CONFIG_DIGEST_ALGO`
5. `CONFIG_DIGEST_FIELD`
6. `SCENARIO_EQUIVALENCE_KEY_INPUT`
7. `SCENARIO_EQUIVALENCE_KEY_CANONICAL_FIELDS`
8. `SCENARIO_EQUIVALENCE_KEY_CANONICALIZATION_MODE`
9. `SCENARIO_RUN_ID_DERIVATION_MODE`
10. `S3_EVIDENCE_BUCKET`
11. `S3_EVIDENCE_RUN_ROOT_PATTERN`
12. `RUN_PIN_PATH_PATTERN`
13. `EVIDENCE_RUN_JSON_KEY`
14. `SFN_PLATFORM_RUN_ORCHESTRATOR_V0`
15. `SR_READY_COMMIT_AUTHORITY`
16. `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`
17. `ROLE_TERRAFORM_APPLY_DEV_FULL`

S0 verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3S0-V1-HANDLE-EXISTS` | `rg -n "\\b<HANDLE_KEY>\\b" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` | confirms required handle key exists in registry |
| `M3S0-V2-PLACEHOLDER-GUARD` | `rg -n "^\\* `<HANDLE_KEY> = \\\"TO_PIN\\\"`" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` | fail-closed if required handle remains placeholder |
| `M3S0-V3-M2-S5-LATEST` | read latest successful `m2_stress_s5_*/stress/m2_execution_summary.json` | confirms M2 closure handoff is present |
| `M3S0-V4-HANDOFF-GATE` | validate `next_gate=M3_READY` and `m3_readiness_recommendation=GO` in M2 S5 summary | confirms phase-entry authority |
| `M3S0-V5-SFN-SURFACE` | `aws stepfunctions list-state-machines --region eu-west-2 --max-results 100` | verifies orchestrator control-plane surface queryability |
| `M3S0-V6-EVIDENCE-BUCKET` | `aws s3api head-bucket --bucket <S3_EVIDENCE_BUCKET> --region eu-west-2` | verifies durable evidence root reachable |

S0 blocker mapping (fail-closed):
1. `M3-ST-B1`:
   - any required handle missing or unresolved (`TO_PIN`).
2. `M3-ST-B3`:
   - orchestrator/evidence control-plane query fails.
3. `M3-ST-B9`:
   - M2 handoff artifact missing/unreadable,
   - S0 required artifacts missing/incomplete.

S0 required artifacts:
1. `m3_stagea_findings.json`
2. `m3_lane_matrix.json`
3. `m3_probe_latency_throughput_snapshot.json`
4. `m3_control_rail_conformance_snapshot.json`
5. `m3_secret_safety_snapshot.json`
6. `m3_cost_outcome_receipt.json`
7. `m3_blocker_register.json`
8. `m3_execution_summary.json`
9. `m3_decision_log.json`

S0 closure rule:
1. `S0` closes only when:
   - all required handles pass presence + placeholder guard,
   - latest successful M2 S5 handoff gate is valid (`M3_READY` + `GO`),
   - control-plane query checks are green or explicitly blocker-classified,
   - full S0 artifact set is emitted and readable.

### 7.2 `M3-ST-S1` - Deterministic baseline window
Objective:
1. verify deterministic run-id/digest/orchestrator-entry behavior under baseline concurrency.

Window:
1. `M3_STRESS_BASELINE_CONCURRENT_RUNS = 2`.
2. `M3_STRESS_WINDOW_MINUTES = 10`.

Actions:
1. run repeated deterministic generation of `platform_run_id` and `scenario_run_id`.
2. verify digest reproducibility across recompute passes.
3. verify orchestrator lookup/entry/readiness and run-header evidence write.

Pass gate:
1. run-id format/collision policy pass.
2. digest recompute consistency pass.
3. no control-rail drift and no secret leakage.
4. spend/runtime within envelope.

S1 deterministic verification checklist:
1. `platform_run_id` format check against `M3_STRESS_RUN_ID_REGEX`.
2. collision probe against `S3_EVIDENCE_RUN_ROOT_PATTERN`.
3. deterministic collision-retry cap enforcement (`M3_STRESS_RUN_ID_COLLISION_RETRY_CAP`).
4. canonical payload serialization mode check (`json_sorted_keys_v1`).
5. digest recompute equality check using `CONFIG_DIGEST_ALGO`.
6. scenario-run deterministic recompute equality using `SCENARIO_RUN_ID_DERIVATION_MODE`.
7. orchestrator surface query and `SR_READY_COMMIT_AUTHORITY` conformance.

S1 verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3S1-V1-RUNID-FORMAT` | local regex check using `M3_STRESS_RUN_ID_REGEX` | enforces canonical `platform_run_id` shape |
| `M3S1-V2-COLLISION-PROBE` | `aws s3api list-objects-v2 --bucket <S3_EVIDENCE_BUCKET> --prefix evidence/runs/<platform_run_id>/ --max-keys 1` | detects run-id collisions in durable root |
| `M3S1-V3-DIGEST-RECOMPUTE` | local canonical-json hashing pass x2 | verifies deterministic digest |
| `M3S1-V4-SCENARIO-RECOMPUTE` | local deterministic scenario-id derivation pass x2 | verifies deterministic scenario id |
| `M3S1-V5-SFN-LOOKUP` | `aws stepfunctions list-state-machines --region eu-west-2 --max-results 100 ...` | validates orchestrator lookup path |
| `M3S1-V6-EVIDENCE-BUCKET` | `aws s3api head-bucket --bucket <S3_EVIDENCE_BUCKET> --region eu-west-2` | validates evidence-root reachability |

S1 closure rule:
1. `S1` closes only when:
   - S0 continuity artifacts are present/readable,
   - run-id format and collision policy checks pass,
   - digest + scenario derivation recompute checks pass,
   - control-plane and authority checks pass,
   - complete S1 artifact set is emitted with zero open blockers.

### 7.3 `M3-ST-S2` - Concurrency and retry contention window
Objective:
1. stress orchestrator lock and cross-run isolation under elevated concurrent activation and retries.

Window:
1. `M3_STRESS_BURST_CONCURRENT_RUNS = 6`.
2. `M3_STRESS_WINDOW_MINUTES = 10`.

Execution rule:
1. run same probe set as `S1` at elevated concurrency.
2. include retry attempts for duplicate/near-simultaneous run activation.
3. compare against `S1` baseline for new lock/correlation drift signals.

Pass gate:
1. no cross-run mixing evidence.
2. lock posture deterministic under contention.
3. no new control/correlation drift vs `S1`.
4. no secret leakage and no unattributed spend.

### 7.4 `M3-ST-S3` - Controlled failure-injection window
Objective:
1. prove deterministic fault detection and fail-closed recovery behavior.

Injection set (bounded):
1. forced run-id collision scenario (bounded retries).
2. malformed/partial run payload/digest mismatch scenario.
3. stale lock or duplicate activation scenario.

Pass gate:
1. all injections classified deterministically.
2. system fails closed without silent fallback.
3. recovery checks return green after injection window.
4. evidence captures cause, impact, remediation hint, and recovery outcome.

### 7.5 `M3-ST-S4` - Remediation and selective rerun
Objective:
1. close blockers with minimal-cost targeted reruns.

Execution rule:
1. rank open blockers by production impact and closure cost.
2. apply remediation only for failed lanes.
3. rerun only failed windows (`S1/S2/S3`) after remediation.

Pass gate:
1. all open non-waived `M3-ST-B*` blockers closed.
2. rerun evidence shows direct before/after improvement.

### 7.6 `M3-ST-S5` - Closure rollup and M4 handoff recommendation
Objective:
1. publish M3 closure verdict and explicit M4 readiness posture.

Actions:
1. emit final rollup artifacts:
   - `m3_execution_summary.json`,
   - `m3_blocker_register.json`,
   - `m3_decision_log.json`,
   - `m3_cost_outcome_receipt.json`.
2. produce explicit `M4` recommendation (`GO`/`NO_GO`) with rationale.

Pass gate:
1. no open non-waived `M3-ST-B*` blockers.
2. required artifacts are complete/readable.
3. runtime/spend envelopes remain within pinned bounds.

## 8) Blocker Taxonomy (M3 Stress)
1. `M3-ST-B1`: missing or unresolved required handle/contract.
2. `M3-ST-B2`: run-id/digest determinism or collision law failure.
3. `M3-ST-B3`: orchestrator/run-lock readiness path failure.
4. `M3-ST-B4`: cross-run correlation/scope drift.
5. `M3-ST-B5`: durable evidence publication failure.
6. `M3-ST-B6`: secret-path violation or plaintext leakage.
7. `M3-ST-B7`: contention/retry instability or recovery failure.
8. `M3-ST-B8`: unattributed spend or budget envelope breach.
9. `M3-ST-B9`: artifact/evidence contract incomplete or unreadable.

Any open `M3-ST-B*` blocks M3 stress closure.

## 9) Evidence Contract
Required artifacts for each M3 stress window:
1. `m3_stagea_findings.json`.
2. `m3_lane_matrix.json`.
3. `m3_probe_latency_throughput_snapshot.json`.
4. `m3_control_rail_conformance_snapshot.json`.
5. `m3_secret_safety_snapshot.json`.
6. `m3_cost_outcome_receipt.json`.
7. `m3_blocker_register.json`.
8. `m3_execution_summary.json`.
9. `m3_decision_log.json`.

## 10) DoD (Planning to Execution-Ready)
- [x] Dedicated M3 stress authority file created.
- [x] Stage-A findings (`PREVENT/OBSERVE/ACCEPT`) pinned.
- [x] M3 stress handle packet pinned.
- [x] Capability-lane coverage mapped.
- [x] Stress topology and execution sequence pinned.
- [x] Execution-grade runbook for `S0..S5` pinned.
- [x] Blocker taxonomy and evidence contract pinned.
- [x] Stage-A artifacts emitted to run-control path.
- [x] First managed M3 stress window executed.

## 11) Immediate Next Actions
1. Expand M3 runner to `S2` concurrency/retry contention window (`scripts/dev_substrate/m3_stress_runner.py`).
2. Execute `M3-ST-S2` window and open fail-closed blockers on any lock/correlation drift.
3. Advance to `M3-ST-S3` only if `S2` closes with zero open blockers.

## 12) Execution Progress
### `M3-ST-S0` authority/handle gate execution (2026-03-03)
1. Phase execution id: `m3_stress_s0_20260303T175048Z`.
2. Runner:
   - `python scripts/dev_substrate/m3_stress_runner.py --stage S0`
3. Verification summary:
   - required handle and placeholder guards passed,
   - latest successful M2 S5 handoff gate validated (`M3_READY`, `GO`),
   - orchestrator surface query passed,
   - evidence bucket reachability query passed.
4. Verdict:
   - `overall_pass=true`,
   - `next_gate=M3_ST_S1_READY`,
   - `open_blockers=0`.
5. Artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s0_20260303T175048Z/stress/m3_stagea_findings.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s0_20260303T175048Z/stress/m3_lane_matrix.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s0_20260303T175048Z/stress/m3_probe_latency_throughput_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s0_20260303T175048Z/stress/m3_control_rail_conformance_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s0_20260303T175048Z/stress/m3_secret_safety_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s0_20260303T175048Z/stress/m3_cost_outcome_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s0_20260303T175048Z/stress/m3_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s0_20260303T175048Z/stress/m3_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s0_20260303T175048Z/stress/m3_decision_log.json`

### `M3-ST-S1` deterministic baseline execution (2026-03-03)
1. Phase execution id: `m3_stress_s1_20260303T175534Z`.
2. Runner:
   - `python scripts/dev_substrate/m3_stress_runner.py --stage S1`
3. Determinism summary:
   - `platform_run_id_candidate=platform_20260303T175534Z`,
   - `platform_run_id_final=platform_20260303T175534Z`,
   - collision probe attempts `1` (`collision_detected=false`),
   - `config_digest_match=true`,
   - `scenario_run_id_match=true`.
4. Control summary:
   - orchestrator lookup `PASS`,
   - evidence bucket reachability `PASS`,
   - control issues `[]`.
5. Verdict:
   - `overall_pass=true`,
   - `next_gate=M3_ST_S2_READY`,
   - `open_blockers=0`.
6. Artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s1_20260303T175534Z/stress/m3_stagea_findings.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s1_20260303T175534Z/stress/m3_lane_matrix.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s1_20260303T175534Z/stress/m3_probe_latency_throughput_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s1_20260303T175534Z/stress/m3_control_rail_conformance_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s1_20260303T175534Z/stress/m3_secret_safety_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s1_20260303T175534Z/stress/m3_cost_outcome_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s1_20260303T175534Z/stress/m3_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s1_20260303T175534Z/stress/m3_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m3_stress_s1_20260303T175534Z/stress/m3_decision_log.json`
