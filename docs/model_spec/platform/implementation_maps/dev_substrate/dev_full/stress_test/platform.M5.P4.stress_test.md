# Dev Substrate Stress Plan - M5.P4 (P4 INGEST_READY)
_Parent authority: `platform.M5.stress_test.md`_
_Status source of truth: `platform.stress_test.md`_
_Track: `dev_full` only_
_As of 2026-03-03_

## 0) Purpose
M5.P4 stress validates ingress boundary, auth, topic readiness, and envelope controls before M6.

M5.P4 stress must prove:
1. ingest boundary surfaces are healthy and contract-valid.
2. auth posture is enforced fail-closed on protected routes.
3. required MSK topic surfaces are reachable and ready.
4. ingress envelope controls are materially present and behaviorally conformant.
5. P4 rollup emits deterministic verdict for M6 entry (`ADVANCE_TO_M6` only when blocker-free).

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M5.stress_test.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.P4.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. P3 closure evidence from `platform.M5.P3.stress_test.md` execution lane.

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`

## 2) Stage-A Findings (M5.P4)
| ID | Classification | Finding | Required action |
| --- | --- | --- | --- |
| `M5P4-ST-F1` | `PREVENT` | P4 entry is invalid without explicit P3 pass verdict. | Gate P4 S0 on P3 verdict `ADVANCE_TO_P4`. |
| `M5P4-ST-F2` | `PREVENT` | Boundary/auth/topic/envelope checks can pass individually but still fail rollup consistency. | Enforce staged runbook (`S0..S5`) with deterministic rollup rule. |
| `M5P4-ST-F3` | `PREVENT` | Runtime handle drift is a known historical failure mode in ingress lanes. | Require handle/runtime parity checks at S0/S1/S4. |
| `M5P4-ST-F4` | `OBSERVE` | Auth posture can regress after runtime redeploys. | Keep positive and negative auth probes mandatory in S2. |
| `M5P4-ST-F5` | `OBSERVE` | Topic readiness checks can fail from network/auth dependencies in private lanes. | Isolate MSK readiness checks in S3 with explicit blocker mapping. |
| `M5P4-ST-F6` | `ACCEPT` | Historical P4 closure is available as baseline reference. | Use historical evidence only as baseline; require active-lane checks in current cycle. |

## 3) Scope Boundary for M5.P4 Stress
In scope:
1. boundary health and ingress preflight checks.
2. boundary auth enforcement checks.
3. MSK topic readiness checks.
4. ingress envelope conformance checks.
5. P4 rollup and deterministic verdict emission.

Out of scope:
1. oracle boundary/upload/sort lanes (`M5.P3`).
2. M6 runtime activation and downstream full-plane stress.

## 4) M5.P4 Stress Handle Packet (Pinned)
1. `M5P4_STRESS_PROFILE_ID = "ingest_ready_stress_v0"`.
2. `M5P4_STRESS_BLOCKER_REGISTER_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m5p4_blocker_register.json"`.
3. `M5P4_STRESS_EXECUTION_SUMMARY_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m5p4_execution_summary.json"`.
4. `M5P4_STRESS_DECISION_LOG_PATH_PATTERN = "evidence/dev_full/run_control/{phase_execution_id}/stress/m5p4_decision_log.json"`.
5. `M5P4_STRESS_REQUIRED_ARTIFACTS = "m5p4_stagea_findings.json,m5p4_lane_matrix.json,m5p4_probe_latency_throughput_snapshot.json,m5p4_control_rail_conformance_snapshot.json,m5p4_secret_safety_snapshot.json,m5p4_cost_outcome_receipt.json,m5p4_blocker_register.json,m5p4_execution_summary.json,m5p4_decision_log.json"`.
6. `M5P4_STRESS_MAX_RUNTIME_MINUTES = 180`.
7. `M5P4_STRESS_MAX_SPEND_USD = 40`.
8. `M5P4_STRESS_EXPECTED_VERDICT_ON_PASS = "ADVANCE_TO_M6"`.
9. `M5P4_STRESS_REQUIRE_P3_VERDICT = "ADVANCE_TO_P4"`.
10. `M5P4_STRESS_REQUIRE_M6_HANDOFF_PACK = true`.

Registry-backed required handles for M5.P4:
1. `IG_BASE_URL`
2. `IG_INGEST_PATH`
3. `IG_HEALTHCHECK_PATH`
4. `IG_AUTH_MODE`
5. `IG_AUTH_HEADER_NAME`
6. `SSM_IG_API_KEY_PATH`
7. `APIGW_IG_API_ID`
8. `LAMBDA_IG_HANDLER_NAME`
9. `DDB_IG_IDEMPOTENCY_TABLE`
10. `IG_MAX_REQUEST_BYTES`
11. `IG_REQUEST_TIMEOUT_SECONDS`
12. `IG_INTERNAL_RETRY_MAX_ATTEMPTS`
13. `IG_INTERNAL_RETRY_BACKOFF_MS`
14. `IG_IDEMPOTENCY_TTL_SECONDS`
15. `IG_DLQ_MODE`
16. `IG_DLQ_QUEUE_NAME`
17. `IG_REPLAY_MODE`
18. `IG_RATE_LIMIT_RPS`
19. `IG_RATE_LIMIT_BURST`
20. `MSK_CLUSTER_ARN`
21. `MSK_BOOTSTRAP_BROKERS_SASL_IAM`
22. `MSK_CLIENT_SUBNET_IDS`
23. `MSK_SECURITY_GROUP_ID`
24. `S3_EVIDENCE_BUCKET`
25. `S3_RUN_CONTROL_ROOT_PATTERN`

## 5) Capability-Lane Coverage (Phase-Coverage Law)
| Capability lane | M5.P4 stage owner | Minimum PASS evidence |
| --- | --- | --- |
| Authority + entry gate closure | `S0` | required handles + P3 verdict dependency closure |
| IG boundary health | `S1` | boundary health snapshot blocker-free |
| Boundary auth enforcement | `S2` | positive/negative auth matrix blocker-free |
| MSK topic readiness | `S3` | topic readiness snapshot blocker-free |
| Ingress envelope conformance | `S4` | envelope conformance snapshot blocker-free |
| P4 rollup + M6 handoff verdict | `S5` | deterministic verdict `ADVANCE_TO_M6` + handoff pack |

## 6) Stress Topology (M5.P4)
1. Component sequence:
   - `P4.A` boundary health,
   - `P4.B` auth enforcement,
   - `P4.C` topic readiness,
   - `P4.D` envelope conformance,
   - `P4.E` rollup verdict.
2. Plane sequence:
   - `ingress_boundary_plane`,
   - `ingress_auth_plane`,
   - `ingress_bus_plane`,
   - `ingress_envelope_plane`,
   - `p4_rollup_plane`.
3. Integrated windows:
   - `m5p4_s1_boundary_window`,
   - `m5p4_s2_auth_window`,
   - `m5p4_s3_topic_window`,
   - `m5p4_s4_envelope_window`.

## 7) Execution Plan (Execution-Grade Runbook)
### 7.1 `M5P4-ST-S0` - Authority and entry-gate closure
Objective:
1. validate M5.P4 can run with complete authority and valid P3 verdict dependency.

Actions:
1. validate required M5.P4 handles and placeholder guards.
2. validate latest successful P3 summary:
   - `overall_pass=true`,
   - `verdict=ADVANCE_TO_P4`,
   - no open non-waived `M5P3-B*`.
3. emit Stage-A findings + lane matrix + blocker register.

Pass gate:
1. required handles complete/non-placeholder.
2. P3 dependency verdict is valid/readable and blocker-free.
3. full P4 S0 artifact set exists/readable.

### 7.2 `M5P4-ST-S1` - IG boundary health preflight
Objective:
1. validate ingest and ops boundary health posture.

Actions:
1. run health and ingest preflight probes with expected response contracts.
2. validate response status and required minimal fields.
3. emit boundary health snapshot and blocker register.

Pass gate:
1. ops and ingest probes meet expected pass criteria.
2. response contract validation is blocker-free.

### 7.3 `M5P4-ST-S2` - Boundary auth enforcement
Objective:
1. validate auth enforcement behavior for protected ingress routes.

Actions:
1. execute valid-key positive probes on protected routes.
2. execute missing-key and invalid-key negative probes.
3. require deterministic status outcomes and emit auth matrix snapshot.

Pass gate:
1. positive and negative auth probes are contract-consistent.
2. no auth enforcement drift or bypass signal exists.

### 7.4 `M5P4-ST-S3` - MSK topic readiness
Objective:
1. validate required MSK topic readiness and reachability posture.

Actions:
1. validate MSK handle parity against live runtime outputs.
2. execute topic readiness probe in correct network/auth posture.
3. emit topic readiness snapshot and blocker register.

Pass gate:
1. required topics are ready/reachable.
2. no unresolved MSK handle or readiness blockers remain.

### 7.5 `M5P4-ST-S4` - Ingress envelope conformance
Objective:
1. validate envelope controls are pinned and behaviorally enforced.

Actions:
1. validate envelope handles and runtime materialization parity.
2. run bounded behavior probes (normal and oversized payloads).
3. emit envelope conformance snapshot and blocker register.

Pass gate:
1. envelope handles and runtime surfaces are aligned.
2. behavior probes match expected contract.

### 7.6 `M5P4-ST-S5` - P4 rollup and deterministic verdict
Objective:
1. emit deterministic P4 verdict and M6 handoff recommendation.

Actions:
1. aggregate S1..S4 artifacts and blocker registers.
2. enforce blocker-consistent verdict rule.
3. emit verdict:
   - `ADVANCE_TO_M6` only when blocker-free,
   - otherwise `HOLD_REMEDIATE` or `NO_GO_RESET_REQUIRED`.
4. require `m6_handoff_pack` reference/readability on pass.

Pass gate:
1. no open non-waived `M5P4-B*` blockers.
2. verdict equals `ADVANCE_TO_M6`.
3. M6 handoff pack reference is present/readable.

## 8) Blocker Taxonomy (M5.P4)
1. `M5P4-B1`: boundary endpoint handles missing/inconsistent.
2. `M5P4-B2`: ingest/ops health failure.
3. `M5P4-B3`: auth posture/enforcement mismatch.
4. `M5P4-B4`: MSK topic readiness failure.
5. `M5P4-B5`: ingress envelope conformance failure.
6. `M5P4-B6`: rollup/register inconsistency.
7. `M5P4-B7`: deterministic verdict build failure.
8. `M5P4-B8`: durable publish/readback failure.
9. `M5P4-B9`: advance verdict emitted despite unresolved blockers.
10. `M5P4-B10`: `m6_handoff_pack` missing/invalid/unreadable.

Any open `M5P4-B*` blocks P4 closure and blocks M6 transition.

## 9) Evidence Contract (M5.P4)
Required artifacts for each M5.P4 stage:
1. `m5p4_stagea_findings.json`
2. `m5p4_lane_matrix.json`
3. `m5p4_probe_latency_throughput_snapshot.json`
4. `m5p4_control_rail_conformance_snapshot.json`
5. `m5p4_secret_safety_snapshot.json`
6. `m5p4_cost_outcome_receipt.json`
7. `m5p4_blocker_register.json`
8. `m5p4_execution_summary.json`
9. `m5p4_decision_log.json`

## 10) DoD (Planning to Execution-Ready)
- [x] Dedicated M5.P4 stress authority created.
- [x] P4 staged runbook (`S0..S5`) pinned with fail-closed transitions.
- [x] P4 blocker taxonomy and evidence contract pinned.
- [ ] M5.P4 S0 executed with blocker-free entry closure.
- [ ] P4 verdict `ADVANCE_TO_M6` emitted from blocker-free rollup.

## 11) Immediate Next Actions
1. Execute `M5P4-ST-S0` authority/entry-gate closure after P3 verdict closure.
2. Keep auth/topic/envelope checks as independent fail-closed stages (`S2..S4`) with targeted reruns only.
3. Do not enter `M5P4-ST-S1` until `S0` closes blocker-free.
