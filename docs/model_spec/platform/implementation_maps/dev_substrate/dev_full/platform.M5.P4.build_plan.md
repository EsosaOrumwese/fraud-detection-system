# Dev Substrate Deep Plan - M5.P4 (P4 INGEST_READY)
_Parent phase: `platform.M5.build_plan.md`_
_Last updated: 2026-02-24_

## 0) Purpose
This document carries execution-grade planning for M5 `P4 INGEST_READY`.

P4 must prove:
1. ingest boundary endpoints are healthy and reachable,
2. boundary auth posture is enforced fail-closed,
3. required MSK topic surfaces are ready,
4. ingress edge envelope controls conform to pinned handles,
5. deterministic P4 verdict and M6 handoff are emitted.

## 1) Authority Inputs
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P4`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` (IG/MSK/envelope handles)
4. P3 closure artifacts from `platform.M5.P3.build_plan.md` execution.

## 2) P4 Work Breakdown

### P4.A (M5.F) IG Boundary Health Preflight
Goal:
1. prove boundary health for ingest and ops surfaces.

Tasks:
1. resolve boundary endpoint handles:
   - `IG_BASE_URL`,
   - `IG_INGEST_PATH`,
   - `IG_HEALTHCHECK_PATH`.
2. run health probes for ops and ingest preflight surfaces.
3. record response posture (status code + minimal contract fields).
4. emit `m5f_ingress_boundary_health_snapshot.json`.

DoD:
- [ ] ops and ingest surfaces are healthy.
- [ ] response posture is contract-valid.
- [ ] health snapshot committed locally and durably.

P4.A precheck:
1. P3 verdict is `ADVANCE_TO_P4`.
2. boundary endpoint handles are pinned and non-empty.

### P4.B (M5.G) Boundary Auth Enforcement
Goal:
1. prove auth contract is enforced exactly as pinned.

Tasks:
1. verify auth handles:
   - `IG_AUTH_MODE`,
   - `IG_AUTH_HEADER_NAME`,
   - `SSM_IG_API_KEY_PATH`.
2. run positive auth probe with valid key.
3. run negative auth probe without/invalid key and require rejection.
4. emit `m5g_boundary_auth_snapshot.json`.

DoD:
- [ ] auth handles are consistent and explicit.
- [ ] positive and negative probes match expected outcomes.
- [ ] auth snapshot committed locally and durably.

P4.B precheck:
1. P4.A is green.
2. auth secret path resolves and key retrieval path is available.

### P4.C (M5.H) MSK Topic Readiness
Goal:
1. prove required topics are present and reachable for ingress/control flow.

Tasks:
1. resolve `MSK_*` cluster/bootstrap handles.
2. verify required topic names and readiness for publish/consume identities.
3. emit `m5h_msk_topic_readiness_snapshot.json`.

DoD:
- [ ] required topics exist and are reachable.
- [ ] topic ownership/readiness checks pass.
- [ ] topic readiness snapshot committed locally and durably.

P4.C precheck:
1. P4.B is green.
2. MSK connectivity handles are pinned and valid.

### P4.D (M5.I) Ingress Envelope Conformance
Goal:
1. prove envelope controls align with pinned dev_full posture.

Tasks:
1. validate request size and timeout controls:
   - `IG_MAX_REQUEST_BYTES`,
   - `IG_REQUEST_TIMEOUT_SECONDS`.
2. validate retry/idempotency controls:
   - `IG_INTERNAL_RETRY_MAX_ATTEMPTS`,
   - `IG_INTERNAL_RETRY_BACKOFF_MS`,
   - `IG_IDEMPOTENCY_TTL_SECONDS`.
3. validate DLQ/replay/rate controls:
   - `IG_DLQ_*`,
   - `IG_REPLAY_MODE`,
   - `IG_RATE_LIMIT_*`.
4. emit `m5i_ingress_envelope_snapshot.json`.

DoD:
- [ ] payload/timeout controls conform.
- [ ] retry/idempotency controls conform.
- [ ] DLQ/replay/rate controls conform.
- [ ] envelope snapshot committed locally and durably.

P4.D precheck:
1. P4.C is green.
2. envelope control handles are pinned and non-placeholder.

### P4.E (M5.J) P4 Gate Rollup + M6 Handoff
Goal:
1. adjudicate P4 and publish M6 handoff only when blocker-free.

Tasks:
1. build P4 rollup matrix + blocker register from P4.A..P4.D.
2. emit deterministic P4 verdict:
   - `ADVANCE_TO_M6`, `HOLD_REMEDIATE`, `NO_GO_RESET_REQUIRED`.
3. build `m6_handoff_pack.json` including:
   - run-scope IDs,
   - required env bindings,
   - references to P3/P4 evidence.
4. emit `m5_execution_summary.json`.
5. publish all artifacts locally and durably.

DoD:
- [ ] P4 rollup matrix and blocker register committed.
- [ ] deterministic P4 verdict artifact committed.
- [ ] `m6_handoff_pack.json` committed locally and durably.
- [ ] M5 execution summary committed locally and durably.

P4.E precheck:
1. P4.A..P4.D artifacts exist and are readable.
2. unresolved blocker set is explicit before verdict emission.

## 3) P4 Verification Catalog
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `P4-V1-BOUNDARY-HEALTH` | probe `IG_BASE_URL + IG_HEALTHCHECK_PATH` and ingest preflight surface | validates boundary health |
| `P4-V2-AUTH-ENFORCEMENT` | run positive + negative auth probes using `IG_AUTH_HEADER_NAME` | validates auth fail-closed posture |
| `P4-V3-MSK-READINESS` | verify cluster/topic surfaces from `MSK_*` handles | validates bus readiness |
| `P4-V4-ENVELOPE-CONFORMANCE` | validate IG envelope handles and probe posture | validates ingress controls |
| `P4-V5-ROLLUP-VERDICT` | build P4 rollup + blocker register + verdict | emits deterministic P4 gate output |
| `P4-V6-M6-HANDOFF` | build `m6_handoff_pack.json` and verify refs/readability | emits transition artifact |
| `P4-V7-DURABLE-PUBLISH` | `aws s3 cp <artifact> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5x_execution_id>/...` | commits durable P4 evidence |

## 4) P4 Blocker Taxonomy (Fail-Closed)
1. `M5P4-B1`: boundary endpoint handles missing/inconsistent.
2. `M5P4-B2`: ingest/ops health failure.
3. `M5P4-B3`: auth posture/enforcement mismatch.
4. `M5P4-B4`: MSK topic readiness failure.
5. `M5P4-B5`: ingress envelope conformance failure.
6. `M5P4-B6`: rollup/register inconsistency.
7. `M5P4-B7`: deterministic verdict build failure.
8. `M5P4-B8`: durable publish/readback failure.
9. `M5P4-B9`: advance verdict emitted despite unresolved blockers.
10. `M5P4-B10`: `m6_handoff_pack.json` missing/invalid/unreadable.

## 5) P4 Evidence Contract
1. `m5f_ingress_boundary_health_snapshot.json`
2. `m5g_boundary_auth_snapshot.json`
3. `m5h_msk_topic_readiness_snapshot.json`
4. `m5i_ingress_envelope_snapshot.json`
5. `m5j_p4_gate_rollup_matrix.json`
6. `m5j_p4_blocker_register.json`
7. `m5j_p4_gate_verdict.json`
8. `m6_handoff_pack.json`
9. `m5_execution_summary.json`

## 6) Exit Rule for P4
P4 can close only when:
1. all `M5P4-B*` blockers are resolved,
2. all P4 DoDs are green,
3. P4 evidence exists locally and durably,
4. verdict and handoff are deterministic and blocker-consistent.

Transition:
1. M6 is blocked until P4 verdict is `ADVANCE_TO_M6`.
