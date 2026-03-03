# Dev Full Stress Plan - M2 (Substrate Readiness Under Load)
_Track: dev_substrate/dev_full_
_As of 2026-03-03_
_Status: ACTIVE_PLANNING_AUTHORITY_

## 0) Objective
Validate that substrate foundations can handle realistic production throughput and failure posture before control-plane runtime activation:
1. under sustained and burst load,
2. with deterministic fail-closed behavior,
3. with bounded runtime and spend.

M2 stress is accepted only when behavior is stable and auditable, not merely when Terraform apply succeeds.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M2.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`
2. `runs/dev_substrate/dev_full/m2/` historical closure evidence from build phase.

## 2) Scope Boundary
In scope:
1. substrate stress of `network + IAM + messaging + secrets + state + budget control` surfaces.
2. control-rail readiness stress:
   - runtime-path governance,
   - SR commit authority route,
   - IG edge envelope/auth contract,
   - cross-runtime correlation contract.
3. rollback/rerun and teardown safety probes for substrate-only scope.

Out of scope:
1. business-lane throughput (Control+Ingress runtime behavior) - deferred to M6+.
2. model/lifecycle workload stress - deferred to M9+.
3. certification result claims.

## 3) Entry Prerequisites (Pinned)
1. M1 closure posture is accepted with immutable artifact-promotion baseline.
2. M2 handle registry is current and queryable (`dev_full_handles.registry.v0.md`).
3. P0/M2 historical evidence roots are readable (local or durable mirror).
4. Non-active non-substrate runtime lanes remain in idle-safe posture.

## 4) Stage-A Decision/Bottleneck Pre-Read

### 4.1 Findings classification
| ID | Classification | Finding | Required action before stress execution |
| --- | --- | --- | --- |
| `M2-ST-F1` | `PREVENT` | No dedicated M2 stress authority file existed; control file was still inline-only. | Create/pin `platform.M2.stress_test.md` and route active phase to it. |
| `M2-ST-F2` | `PREVENT` | Stress handle packet for M2 is not yet pinned in stress authority (`profile`, `artifacts`, runtime/spend budgets). | Pin M2 stress handle packet in this file before any managed stress run. |
| `M2-ST-F3` | `PREVENT` | M2 has many coupled lanes (`A..J`); no stress lane matrix existed for component->plane->integrated progression. | Pin deterministic lane matrix and execution order in Sections 6-9. |
| `M2-ST-F4` | `OBSERVE` | Historical M2 closure used provisioning checks; runtime load sensitivity of shared substrate (MSK/API/SSM) is not yet profiled under current traffic envelopes. | Run bounded baseline + burst stress windows with telemetry capture. |
| `M2-ST-F5` | `OBSERVE` | Secret-path readability and API-edge auth are known fail-closed areas; regression risk rises under concurrent probes. | Add concurrency-aware secret/auth probe window with strict leak checks. |
| `M2-ST-F6` | `ACCEPT` | M2 build evidence already contains full blocker taxonomy and lane-level artifacts (`M2A..M2J`). | Reuse as starting baseline for stress contract and blocker IDs. |

### 4.2 Stage-A exit rule
No M2 stress execution starts while `M2-ST-F1..F3` remain unresolved.

## 5) M2 Stress Handle Packet (Pinned)
1. `STRESS_ACTIVE_PHASE = "M2"`.
2. `M2_STRESS_PROFILE_ID = "substrate_load_and_failure_profile_v0"`.
3. `M2_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m2_blocker_register.json"`.
4. `M2_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m2_execution_summary.json"`.
5. `M2_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m2_decision_log.json"`.
6. `M2_STRESS_REQUIRED_ARTIFACTS = "m2_blocker_register.json,m2_execution_summary.json,m2_decision_log.json,m2_stagea_findings.json,m2_lane_matrix.json"`.
7. `M2_STRESS_MAX_RUNTIME_MINUTES = 180`.
8. `M2_STRESS_MAX_SPEND_USD = 35`.
9. `M2_STRESS_FAIL_ON_CONTROL_RAIL_DRIFT = true`.
10. `M2_STRESS_FAIL_ON_UNATTRIBUTED_SPEND = true`.
11. `M2_STRESS_FAIL_ON_SECRET_PLAINTEXT = true`.
12. `M2_STRESS_BASELINE_EVENTS_PER_SECOND = 20`.
13. `M2_STRESS_BURST_EVENTS_PER_SECOND = 40`.
14. `M2_STRESS_WINDOW_MINUTES = 10`.

## 6) Capability-Lane Coverage (Phase-Coverage Law)
1. Authority/handles:
   - M2 lane handles (`TF_STATE_*`, `TF_STACK_*`, `MSK_*`, `GLUE_*`, `ROLE_*`, `SSM_*`, `PHASE_RUNTIME_PATH_*`, `SR_READY_*`, `CORRELATION_*`).
2. Identity/IAM:
   - runtime-critical role resolution and least-privilege conformance under probe load.
3. Network:
   - core + streaming + runtime connectivity surfaces (`subnets`, `SG`, API edge, broker endpoints).
4. Data stores:
   - S3, DynamoDB, SSM read/write query posture under bounded concurrency.
5. Messaging:
   - MSK bootstrap/query readiness and schema-registry path behavior under stress windows.
6. Secrets:
   - required path readability and leak-free evidence contract.
7. Observability/evidence:
   - mandatory stress artifacts + throughput/latency/cost snapshots.
8. Rollback/rerun:
   - deterministic rerun profile and blocker-driven remediation loop.
9. Teardown:
   - non-active lane stop guarantees and post-window residual checks.
10. Budget:
   - run-window envelope and cost-to-outcome receipt requirement.

## 7) Stress Topology (M2)
Component-level sequence:
1. `M2.A/B/C` substrate control-plane foundations.
2. `M2.D/E/F` control rails + identity + secrets under concurrent probes.
3. `M2.G/H` data_ml and ops dependency readiness under bounded load.

Plane-level sequence:
1. Substrate plane: state/backend + network + messaging + identity.
2. Control rail plane: runtime-path + SR authority + IG edge + correlation.
3. Safety plane: secret-path conformance + cost/residual integrity.

Integrated sequence:
1. Baseline window:
   - 20 eps equivalent probe load, 10 minutes.
2. Burst window:
   - 40 eps equivalent probe load, 10 minutes.
3. Failure-injection window:
   - bounded secret-path/readability denial simulation,
   - bounded API-edge dependency degradation simulation,
   - verify fail-closed posture and clean recovery.

## 8) Execution Plan (Execution-Grade Runbook)
This section is the authoritative execution method for M2.

### 8.1 `M2-ST-S0` - Stage-A artifact emission and dispatch hardening
Objective:
1. Convert planning authority into execution artifacts and pinned dispatch contract.

Actions:
1. Emit `m2_stagea_findings.json` from Section-4 findings.
2. Emit `m2_lane_matrix.json` mapping `M2.A..M2.J` to stress probe surfaces.
3. Build dispatch profile contract for `S1/S2/S3`:
   - target eps,
   - concurrency,
   - timeout budget,
   - probe list.
4. Validate run-control output paths and required artifact list serialization.

Pass gate:
1. Both Stage-A artifacts are written and readable at pinned stress control paths.
2. Dispatch profile is deterministic and references only pinned handles.
3. `M2-ST-F1..F3` are all closed in the blocker register.

### 8.2 `M2-ST-S1` - Baseline substrate window
Objective:
1. Establish low-risk baseline behavior under realistic sustained load.

Window:
1. `M2_STRESS_BASELINE_EVENTS_PER_SECOND = 20`.
2. `M2_STRESS_WINDOW_MINUTES = 10`.

Probe surfaces:
1. Terraform/state backend reachability (`TF_STATE_BUCKET`, `TF_LOCK_TABLE` read probes).
2. Messaging substrate (`MSK_CLUSTER_ARN` describe, bootstrap-path read, schema-registry read).
3. API edge substrate (`APIGW_IG_API_ID` health/readiness probe, lambda + ddb descriptor checks).
4. Secrets substrate (`SSM_*` required path readability and role simulation checks).
5. Control rail substrate (`PHASE_RUNTIME_PATH_*`, `SR_READY_*`, `CORRELATION_*` conformance probes).

Pass gate:
1. Error rate <= `1.0%`.
2. No unresolved handle/probe-path failures.
3. No secret plaintext leakage findings.
4. No control-rail contract drift.
5. Spend remains within active window envelope.

### 8.3 `M2-ST-S2` - Burst substrate window
Objective:
1. Measure saturation behavior and degradation pattern under higher concurrency.

Window:
1. `M2_STRESS_BURST_EVENTS_PER_SECOND = 40`.
2. `M2_STRESS_WINDOW_MINUTES = 10`.

Execution rule:
1. Run same probe set as `S1` with higher concurrency and tighter timeout enforcement.
2. Compare metrics against `S1` baseline to identify nonlinear failure signatures.

Pass gate:
1. Error rate <= `2.0%`.
2. No sustained probe-failure streak > `3` consecutive intervals.
3. No new control-rail drift vs `S1`.
4. No secret leakage and no unattributed spend.

### 8.4 `M2-ST-S3` - Controlled failure-injection window
Objective:
1. Prove fail-closed behavior and recovery posture under expected substrate faults.

Injection set (bounded):
1. Missing-path simulation for one non-critical SSM probe target.
2. Permission-denied simulation via IAM policy simulation on selected action/path.
3. API-edge dependency degradation simulation via bounded invalid route/auth probe.

Pass gate:
1. All injected faults are detected and classified deterministically.
2. System fails closed (no silent pass, no implicit fallback path switch).
3. Recovery probes return to green after injection window closes.
4. Evidence artifacts capture fault cause, impact, and recovery outcome.

### 8.5 `M2-ST-S4` - Remediation and selective rerun
Objective:
1. Close blockers with minimal-cost reruns.

Execution rule:
1. Rank open blockers by production impact and closure cost.
2. Apply targeted remediation only for failed lanes.
3. Rerun only failed windows (`S1`/`S2`/`S3`) after remediation.

Pass gate:
1. All open `M2-ST-B*` blockers are closed or explicitly user-waived.
2. Rerun evidence shows direct before/after improvement on affected metrics.

### 8.6 `M2-ST-S5` - Closure rollup and M3 handoff
Objective:
1. Publish closure verdict and explicit handoff posture.

Actions:
1. Emit final rollup:
   - `m2_execution_summary.json`,
   - `m2_blocker_register.json`,
   - `m2_decision_log.json`,
   - `m2_cost_outcome_receipt.json`.
2. Produce explicit `M3` readiness recommendation (`GO`/`NO_GO`) with rationale.

Pass gate:
1. No open non-waived `M2-ST-B*` blockers.
2. All required artifacts are present/readable.
3. Runtime/spend envelopes remained within pinned bounds.

### 8.7 Execution control surface (pinned)
1. Runner implementation target: `scripts/dev_substrate/m2_stress_runner.py`.
2. Runner responsibilities:
   - execute `S0..S5` deterministically,
   - write all required artifacts into phase execution run-control stress path,
   - emit blocker/severity rollup with explicit next-gate result.
3. Managed dispatch posture:
   - execute from managed lane when user approves run launch,
   - keep local execution for preflight/static validation and artifact-shape checks only.

## 9) Blocker Taxonomy (M2 Stress)
1. `M2-ST-B1`: missing or drifted handle contract for active stress lane.
2. `M2-ST-B2`: substrate probe path unavailable (state/lock/MSK/API/SSM unreadable).
3. `M2-ST-B3`: runtime-path governance contract drift.
4. `M2-ST-B4`: SR commit-authority route drift.
5. `M2-ST-B5`: IG edge envelope/auth contract drift.
6. `M2-ST-B6`: secret-path unreadable or plaintext leakage.
7. `M2-ST-B7`: unexplained latency/throughput collapse or sustained lag growth.
8. `M2-ST-B8`: unattributed spend or envelope breach.
9. `M2-ST-B9`: artifact/evidence contract incomplete or inconsistent.

Any open `M2-ST-B*` blocks M2 stress closure.

## 10) Evidence Contract
Required artifacts for each M2 stress window:
1. `m2_stagea_findings.json`.
2. `m2_lane_matrix.json`.
3. `m2_probe_latency_throughput_snapshot.json`.
4. `m2_control_rail_conformance_snapshot.json`.
5. `m2_secret_safety_snapshot.json`.
6. `m2_cost_outcome_receipt.json`.
7. `m2_blocker_register.json`.
8. `m2_execution_summary.json`.
9. `m2_decision_log.json`.

## 11) DoD (Planning to Execution-Ready)
- [x] Dedicated M2 stress authority file created.
- [x] Stage-A findings (`PREVENT/OBSERVE/ACCEPT`) pinned.
- [x] M2 stress handle packet pinned.
- [x] Capability-lane coverage mapped (authority/identity/network/data/messaging/secrets/obs/rollback/teardown/budget).
- [x] Stress topology and execution sequence pinned.
- [x] Execution-grade runbook for `S0..S5` pinned with stage pass gates.
- [x] Execution control surface pinned (runner + managed dispatch posture).
- [x] Blocker taxonomy and evidence contract pinned.
- [x] Stage-A artifacts emitted to run-control path.
- [x] USER go-ahead captured for first M2 managed stress window dispatch.

## 12) Immediate Next Actions
1. Resolve `M2-ST-B3`/`M2-ST-B4` by repinning `SR_READY_COMMIT_STATE_MACHINE` to live state-machine name/ARN and updating authority/registry as needed.
2. Rerun `M2-ST-S1` baseline window immediately after handle repin.
3. Advance to `M2-ST-S2` only if rerun closes all open blockers.

## 13) Execution Progress
### `M2-ST-S0` execution (2026-03-03)
1. Phase execution id: `m2_stress_s0_20260303T155942Z`.
2. Runner:
   - `python scripts/dev_substrate/m2_stress_runner.py --stage S0`
3. Verdict:
   - `overall_pass=true`,
   - `next_gate=M2_ST_S1_READY`,
   - `open_blockers=0`.
4. Artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s0_20260303T155942Z/stress/m2_stagea_findings.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s0_20260303T155942Z/stress/m2_lane_matrix.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s0_20260303T155942Z/stress/m2_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s0_20260303T155942Z/stress/m2_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s0_20260303T155942Z/stress/m2_decision_log.json`

### `M2-ST-S1` baseline execution (2026-03-03)
1. Phase execution id: `m2_stress_s1_20260303T160937Z`.
2. Runner:
   - `python scripts/dev_substrate/m2_stress_runner.py --stage S1`
3. Window profile:
   - `window_seconds_observed=600`,
   - `probe_count=630`,
   - `error_rate_pct=0.0`.
4. Verdict:
   - `overall_pass=false`,
   - `next_gate=BLOCKED`,
   - `open_blockers=2`.
5. Open blockers:
   - `M2-ST-B3` (`control_rail` drift),
   - `M2-ST-B4` (`SR` commit-authority route unresolved).
6. Root cause signal:
   - Step Functions lookup probe returned `stdout=None` for handle `SR_READY_COMMIT_STATE_MACHINE="SFN_PLATFORM_RUN_ORCHESTRATOR_V0"`,
   - live state machine list currently contains `fraud-platform-dev-full-platform-run-v0`.
7. Artifacts:
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s1_20260303T160937Z/stress/m2_stagea_findings.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s1_20260303T160937Z/stress/m2_lane_matrix.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s1_20260303T160937Z/stress/m2_probe_latency_throughput_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s1_20260303T160937Z/stress/m2_control_rail_conformance_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s1_20260303T160937Z/stress/m2_secret_safety_snapshot.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s1_20260303T160937Z/stress/m2_cost_outcome_receipt.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s1_20260303T160937Z/stress/m2_blocker_register.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s1_20260303T160937Z/stress/m2_execution_summary.json`
   - `runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control/m2_stress_s1_20260303T160937Z/stress/m2_decision_log.json`
