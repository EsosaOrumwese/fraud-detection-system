# Dev Substrate Deep Plan - M5.P4 (P4 INGEST_READY)
_Parent phase: `platform.M5.build_plan.md`_
_Last updated: 2026-02-25_

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
- [x] ops and ingest surfaces are healthy.
- [x] response posture is contract-valid.
- [x] health snapshot committed locally and durably.

P4.A precheck:
1. P3 verdict is `ADVANCE_TO_P4`.
2. boundary endpoint handles are pinned and non-empty.

P4.A capability-lane coverage (execution gate):
| Lane | Required handles/surfaces | Verification posture | Fail-closed condition |
| --- | --- | --- | --- |
| Boundary handle integrity | `IG_BASE_URL`, `IG_INGEST_PATH`, `IG_HEALTHCHECK_PATH`, `IG_AUTH_HEADER_NAME`, `SSM_IG_API_KEY_PATH` | resolve handles and validate non-empty/non-placeholder values | missing/inconsistent boundary handle |
| Health endpoint probe | `GET <IG_BASE_URL><IG_HEALTHCHECK_PATH>` | require HTTP `200` and minimal response contract (`status`, `service`, `mode`) | non-200 or malformed health contract |
| Ingest preflight probe | `POST <IG_BASE_URL><IG_INGEST_PATH>` | require HTTP `202` and minimal ingest acceptance contract (`admitted`, `ingress_mode`) | non-202 or malformed ingest contract |
| Boundary auth path availability | SSM API-key retrieval using `SSM_IG_API_KEY_PATH` | retrieve key and use configured auth header during probes | key retrieval failure or auth header mismatch |
| Evidence publication | `S3_EVIDENCE_BUCKET`, `S3_RUN_CONTROL_ROOT_PATTERN` | local snapshot + blocker register + summary, then durable publish/readback | publish/readback failure |

P4.A verification command templates (operator lane):
1. Handle closure:
   - `rg -n "IG_BASE_URL|IG_INGEST_PATH|IG_HEALTHCHECK_PATH|IG_AUTH_HEADER_NAME|SSM_IG_API_KEY_PATH" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
2. Auth key retrieval:
   - `aws ssm get-parameter --name <SSM_IG_API_KEY_PATH> --with-decryption`
3. Health probe:
   - `GET <IG_BASE_URL><IG_HEALTHCHECK_PATH>` with `<IG_AUTH_HEADER_NAME>: <api_key>`
4. Ingest probe:
   - `POST <IG_BASE_URL><IG_INGEST_PATH>` with `<IG_AUTH_HEADER_NAME>: <api_key>` and run-scoped probe payload.
5. Durable publish/readback:
   - `aws s3 cp <local_m5f_ingress_boundary_health_snapshot.json> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5x_execution_id>/m5f_ingress_boundary_health_snapshot.json`
   - `aws s3 ls s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5x_execution_id>/m5f_ingress_boundary_health_snapshot.json`

P4.A scoped blocker mapping (must be explicit before transition):
1. `P4A-B1` -> `M5P4-B1`: boundary handle missing/inconsistent.
2. `P4A-B2` -> `M5P4-B2`: ops/ingest health probe failure.
3. `P4A-B3` -> `M5P4-B2`: response posture contract invalid.
4. `P4A-B4` -> `M5P4-B3`: auth/key retrieval path unavailable for probes.
5. `P4A-B5` -> `M5P4-B8`: durable publish/readback failure.
6. `P4A-B6` -> `M5P4-B9`: transition attempted with unresolved `P4A-B*`.

P4.A exit rule:
1. ops and ingest boundary probes are healthy (`200/202`),
2. response posture contracts are valid,
3. `m5f_ingress_boundary_health_snapshot.json` exists locally and durably,
4. no active `P4A-B*` blocker remains,
5. P4.B remains blocked until P4.A pass is explicit in rollup evidence.

P4.A execution closure (2026-02-25):
1. Initial run (fail-closed baseline):
   - execution id: `m5f_p4a_ingress_boundary_health_20260225T005845Z`
   - result: `overall_pass=false`, blockers `P4A-B2/P4A-B3`.
2. Root cause:
   - stale IG API handle drift (`l3f3x3zr2l` deleted); endpoint resolution failed.
3. Remediation:
   - repinned `APIGW_IG_API_ID` and `IG_BASE_URL` in handle registry to live API `5p7yslq6rc`.
4. Authoritative green run:
   - execution id: `m5f_p4a_ingress_boundary_health_20260225T010044Z`
   - local root: `runs/dev_substrate/dev_full/m5/m5f_p4a_ingress_boundary_health_20260225T010044Z/`
   - summary: `runs/dev_substrate/dev_full/m5/m5f_p4a_ingress_boundary_health_20260225T010044Z/m5f_execution_summary.json`
   - result: `overall_pass=true`, blockers `[]`, ops status `200`, ingest status `202`.
5. Durable evidence (authoritative pass):
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5f_p4a_ingress_boundary_health_20260225T010044Z/m5f_ingress_boundary_health_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5f_p4a_ingress_boundary_health_20260225T010044Z/m5f_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5f_p4a_ingress_boundary_health_20260225T010044Z/m5f_execution_summary.json`
6. Gate impact:
   - P4.A is green; P4.B (`M5.G`) is unblocked.

### P4.B (M5.G) Boundary Auth Enforcement
Goal:
1. prove auth contract is enforced exactly as pinned.

Tasks:
1. verify auth handles:
   - `IG_AUTH_MODE`,
   - `IG_AUTH_HEADER_NAME`,
   - `SSM_IG_API_KEY_PATH`.
2. run positive auth probe with valid key for both protected routes:
   - `GET /ops/health`,
   - `POST /ingest/push`.
3. run negative auth probe without key and require `401`.
4. run negative auth probe with invalid key and require `401`.
4. emit `m5g_boundary_auth_snapshot.json`.

DoD:
- [x] auth handles are consistent and explicit.
- [x] positive and negative probes match expected outcomes for all protected routes.
- [x] auth snapshot committed locally and durably.

P4.B precheck:
1. P4.A is green.
2. auth secret path resolves and key retrieval path is available.

P4.B capability-lane coverage (execution gate):
| Lane | Required handles/surfaces | Verification posture | Fail-closed condition |
| --- | --- | --- | --- |
| Auth handle integrity | `IG_AUTH_MODE`, `IG_AUTH_HEADER_NAME`, `SSM_IG_API_KEY_PATH`, `IG_BASE_URL`, `IG_INGEST_PATH`, `IG_HEALTHCHECK_PATH` | resolve handles and validate non-empty/non-placeholder values | missing/inconsistent handle |
| Auth secret retrieval | SSM API-key retrieval using `SSM_IG_API_KEY_PATH` | retrieve valid non-empty key before probes | secret retrieval/read failure |
| Positive probe contract | `GET /ops/health`, `POST /ingest/push` with valid header | require `200` and `202` respectively | valid-key request rejected or malformed contract |
| Missing-key rejection | same protected routes without auth header | require `401` for both routes | missing key admitted or wrong status |
| Invalid-key rejection | same protected routes with invalid auth header | require `401` for both routes | invalid key admitted or wrong status |
| Evidence publication | `S3_EVIDENCE_BUCKET`, `S3_RUN_CONTROL_ROOT_PATTERN` | local snapshot + blocker register + summary, then durable publish/readback | publish/readback failure |

P4.B verification command templates (operator lane):
1. Handle closure:
   - `rg -n "IG_AUTH_MODE|IG_AUTH_HEADER_NAME|SSM_IG_API_KEY_PATH|IG_BASE_URL|IG_INGEST_PATH|IG_HEALTHCHECK_PATH" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
2. Auth key retrieval:
   - `aws ssm get-parameter --name <SSM_IG_API_KEY_PATH> --with-decryption`
3. Positive probes:
   - `GET <IG_BASE_URL><IG_HEALTHCHECK_PATH>` with `<IG_AUTH_HEADER_NAME>: <api_key>` -> expect `200`
   - `POST <IG_BASE_URL><IG_INGEST_PATH>` with `<IG_AUTH_HEADER_NAME>: <api_key>` -> expect `202`
4. Missing-key negative probes:
   - `GET <IG_BASE_URL><IG_HEALTHCHECK_PATH>` without auth header -> expect `401`
   - `POST <IG_BASE_URL><IG_INGEST_PATH>` without auth header -> expect `401`
5. Invalid-key negative probes:
   - `GET <IG_BASE_URL><IG_HEALTHCHECK_PATH>` with invalid key -> expect `401`
   - `POST <IG_BASE_URL><IG_INGEST_PATH>` with invalid key -> expect `401`
6. Durable publish/readback:
   - `aws s3 cp <local_m5g_boundary_auth_snapshot.json> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5x_execution_id>/m5g_boundary_auth_snapshot.json`
   - `aws s3 ls s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5x_execution_id>/m5g_boundary_auth_snapshot.json`

P4.B scoped blocker mapping (must be explicit before transition):
1. `P4B-B1` -> `M5P4-B1`: auth handles missing/inconsistent.
2. `P4B-B2` -> `M5P4-B3`: positive auth probe failure with valid key.
3. `P4B-B3` -> `M5P4-B3`: missing-key request was not rejected (`401` expected).
4. `P4B-B4` -> `M5P4-B3`: invalid-key request was not rejected (`401` expected).
5. `P4B-B5` -> `M5P4-B8`: durable publish/readback failure.
6. `P4B-B6` -> `M5P4-B9`: transition attempted with unresolved `P4B-B*`.
7. `P4B-B7` -> `M5P4-B3`: runtime implementation drift (protected route not auth-guarded).

P4.B exit rule:
1. auth handles are resolved and consistent with runtime wiring,
2. valid-key probes pass (`200` health, `202` ingest),
3. missing-key and invalid-key probes return `401` on all protected routes,
4. `m5g_boundary_auth_snapshot.json` exists locally and durably,
5. no active `P4B-B*` blocker remains,
6. P4.C remains blocked until explicit `P4.B` pass evidence is committed.

P4.B execution closure (2026-02-25):
1. Drift confirmation before remediation:
   - live probes admitted requests without auth (`202` on ingest) for missing/invalid API keys.
   - root cause was missing auth guard in `infra/terraform/dev_full/runtime/lambda/ig_handler.py`.
2. Remediation implemented:
   - Lambda auth enforcement added for protected routes (`GET /ops/health`, `POST /ingest/push`),
   - rejection contract pinned in runtime: missing/invalid key -> `401`,
   - runtime env wiring pinned via Terraform: `IG_AUTH_MODE`, `IG_AUTH_HEADER_NAME`.
3. Runtime re-materialization:
   - `terraform -chdir=infra/terraform/dev_full/runtime apply` updated `aws_lambda_function.ig_handler`,
   - runtime outputs now include `IG_AUTH_MODE=api_key`, `IG_AUTH_HEADER_NAME=X-IG-Api-Key`.
4. Authoritative green run:
   - execution id: `m5g_p4b_boundary_auth_20260225T011324Z`
   - local root: `runs/dev_substrate/dev_full/m5/m5g_p4b_boundary_auth_20260225T011324Z/`
   - summary: `runs/dev_substrate/dev_full/m5/m5g_p4b_boundary_auth_20260225T011324Z/m5g_execution_summary.json`
   - result: `overall_pass=true`, blockers `[]`.
5. Probe outcomes (authoritative):
   - positive: health `200`, ingest `202` with valid key,
   - missing key: health `401`, ingest `401`,
   - invalid key: health `401`, ingest `401`.
6. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5g_p4b_boundary_auth_20260225T011324Z/m5g_boundary_auth_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5g_p4b_boundary_auth_20260225T011324Z/m5g_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5g_p4b_boundary_auth_20260225T011324Z/m5g_execution_summary.json`
7. Gate impact:
   - P4.B is green; P4.C (`M5.H`) is unblocked.

### P4.C (M5.H) MSK Topic Readiness
Goal:
1. prove required topics are present and reachable for ingress/control flow.

Tasks:
1. resolve `MSK_*` cluster/bootstrap handles from live streaming outputs and compare against registry pins.
2. execute in-VPC Kafka admin probe using IAM auth to validate required spine topics are reachable.
3. if required topics are missing, request topic creation and re-check readiness set.
4. emit `m5h_msk_topic_readiness_snapshot.json`.
5. emit `m5h_blocker_register.json` and `m5h_execution_summary.json`.

DoD:
- [x] required topics exist and are reachable.
- [x] topic ownership/readiness checks pass.
- [x] topic readiness snapshot committed locally and durably.

P4.C precheck:
1. P4.B is green.
2. MSK connectivity handles are pinned and valid.

P4.C capability-lane coverage (execution gate):
| Lane | Required handles/surfaces | Verification posture | Fail-closed condition |
| --- | --- | --- | --- |
| Handle integrity | `MSK_CLUSTER_ARN`, `MSK_BOOTSTRAP_BROKERS_SASL_IAM`, `MSK_CLIENT_SUBNET_IDS`, `MSK_SECURITY_GROUP_ID` | compare registry pins against `terraform output` for `infra/terraform/dev_full/streaming` and `infra/terraform/dev_full/core` | stale/mismatched handle pin (`M5P4-B1`) |
| Cluster health | MSK control-plane cluster state | require `State=ACTIVE` from `describe-cluster-v2` | non-active cluster (`M5P4-B4`) |
| In-VPC topic probe | private-subnet Lambda probe with `kafka-python` + IAM token signer | list required topics and require all to be present/reachable; allow create-and-relist for missing topics | probe error/function error/missing topic (`M5P4-B4`) |
| Topic contract scope | required P4 spine topics | require 9/9 readiness for `FP_BUS_{CONTROL,TRAFFIC_FRAUD,CONTEXT_*,RTDL,AUDIT,CASE_TRIGGERS,LABELS_EVENTS}` | partial/ambiguous readiness (`M5P4-B4`) |
| Evidence durability | `S3_EVIDENCE_BUCKET` + run-control prefix | local artifacts + durable upload/readability under `evidence/dev_full/run_control/<m5h_execution_id>/` | missing/unreadable artifacts (`M5P4-B8`) |

P4.C verification command templates (operator lane):
1. Live handle surfaces:
   - `terraform -chdir=infra/terraform/dev_full/streaming output -json`
   - `terraform -chdir=infra/terraform/dev_full/core output -json`
2. Cluster state:
   - `aws kafka describe-cluster-v2 --cluster-arn <MSK_CLUSTER_ARN> --region eu-west-2`
3. In-VPC probe:
   - temporary Lambda in private subnets with MSK SG, IAM `kafka-cluster:*` scope, `kafka-python` admin probe, then cleanup.
4. Durable publish:
   - `aws s3 cp <m5h_artifact> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m5h_execution_id>/...`

P4.C scoped blocker mapping (must be explicit before transition):
1. `P4C-B1` -> `M5P4-B1`: `MSK_CLUSTER_ARN` drift between registry and runtime outputs.
2. `P4C-B2` -> `M5P4-B1`: `MSK_BOOTSTRAP_BROKERS_SASL_IAM` drift between registry and runtime outputs.
3. `P4C-B3` -> `M5P4-B4`: in-VPC probe cannot reach required control plane (for example, SSM dependency from private subnet).
4. `P4C-B4` -> `M5P4-B4`: probe implementation/runtime error (invoke function error, Kafka admin incompatibility).
5. `P4C-B5` -> `M5P4-B4`: required topics not ready after probe.
6. `P4C-B6` -> `M5P4-B8`: durable publish/readback failure.

P4.C exit rule:
1. live `MSK_*` handle pins are aligned (no registry/runtime drift),
2. in-VPC probe reports 9/9 required topics ready,
3. `m5h_msk_topic_readiness_snapshot.json`, `m5h_blocker_register.json`, and `m5h_execution_summary.json` exist locally and durably,
4. no active `P4C-B*` blocker remains,
5. P4.D remains blocked until explicit P4.C pass evidence is committed.

P4.C execution closure (2026-02-25):
1. Fail-closed baselines (captured intentionally):
   - `m5h_p4c_msk_topic_readiness_20260225T013103Z` -> invoke race while Lambda pending + stale MSK handle drift.
   - `m5h_p4c_msk_topic_readiness_20260225T014014Z` -> private-subnet probe attempted SSM call and timed out (`ConnectTimeout`).
   - `m5h_p4c_msk_topic_readiness_20260225T014538Z` -> Kafka admin method signature mismatch.
   - `m5h_p4c_msk_topic_readiness_20260225T014950Z` -> create-topics response handling mismatch.
2. Remediations applied before authoritative rerun:
   - repinned `MSK_CLUSTER_ARN`, `MSK_BOOTSTRAP_BROKERS_SASL_IAM`, `MSK_CLIENT_SUBNET_IDS`, and `MSK_SECURITY_GROUP_ID` in `dev_full_handles.registry.v0.md` to current streaming outputs.
   - removed SSM dependency from in-VPC probe payload; pass bootstrap directly.
   - corrected Kafka admin probe behavior for `kafka-python` response types (create + relist contract).
3. Authoritative green run:
   - execution id: `m5h_p4c_msk_topic_readiness_20260225T015352Z`
   - local root: `runs/dev_substrate/dev_full/m5/m5h_p4c_msk_topic_readiness_20260225T015352Z/`
   - summary: `runs/dev_substrate/dev_full/m5/m5h_p4c_msk_topic_readiness_20260225T015352Z/m5h_execution_summary.json`
   - result: `overall_pass=true`, blockers `[]`, next gate `M5.I_READY`.
4. Topic readiness outcomes (authoritative):
   - required topics ready: `9/9`,
   - probe errors: `0`,
   - handle drift: none.
5. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5h_p4c_msk_topic_readiness_20260225T015352Z/m5h_msk_topic_readiness_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5h_p4c_msk_topic_readiness_20260225T015352Z/m5h_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5h_p4c_msk_topic_readiness_20260225T015352Z/m5h_execution_summary.json`
6. Gate impact:
   - P4.C is green; P4.D (`M5.I`) is unblocked.

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
- [x] payload/timeout controls conform.
- [x] retry/idempotency controls conform.
- [x] DLQ/replay/rate controls conform.
- [x] envelope snapshot committed locally and durably.

P4.D precheck:
1. P4.C is green.
2. envelope control handles are pinned and non-placeholder.

P4.D capability-lane coverage (execution gate):
| Lane | Required handles/surfaces | Verification posture | Fail-closed condition |
| --- | --- | --- | --- |
| Handle integrity | `IG_MAX_REQUEST_BYTES`, `IG_REQUEST_TIMEOUT_SECONDS`, `IG_INTERNAL_RETRY_MAX_ATTEMPTS`, `IG_INTERNAL_RETRY_BACKOFF_MS`, `IG_IDEMPOTENCY_TTL_SECONDS`, `IG_DLQ_MODE`, `IG_DLQ_QUEUE_NAME`, `IG_REPLAY_MODE`, `IG_RATE_LIMIT_RPS`, `IG_RATE_LIMIT_BURST` | validate all required envelope handles are pinned and non-placeholder in registry | missing/placeholder handle (`M5P4-B5`) |
| Runtime materialization | Lambda env + API Gateway integration/stage + DDB TTL + SQS DLQ | require runtime surfaces to match pinned values (timeout, throttle, retry/backoff, TTL, DLQ/replay wiring) | runtime/handle drift (`M5P4-B5`) |
| Behavioral probes | authenticated ingest + health probes | require normal payload `202` and oversized payload `413 payload_too_large`; health includes envelope surface | probe mismatch (`M5P4-B5`) |
| Evidence durability | run-control prefix in evidence bucket | local + durable artifacts readable (`m5i_*`) | publish/readback failure (`M5P4-B8`) |

P4.D verification command templates (operator lane):
1. Runtime apply/outputs:
   - `terraform -chdir=infra/terraform/dev_full/runtime plan`
   - `terraform -chdir=infra/terraform/dev_full/runtime apply`
   - `terraform -chdir=infra/terraform/dev_full/runtime output -json`
2. Runtime surfaces:
   - `aws lambda get-function-configuration --function-name fraud-platform-dev-full-ig-handler --region eu-west-2`
   - `aws apigatewayv2 get-integrations --api-id <APIGW_IG_API_ID> --region eu-west-2`
   - `aws apigatewayv2 get-stage --api-id <APIGW_IG_API_ID> --stage-name v1 --region eu-west-2`
   - `aws dynamodb describe-time-to-live --table-name <DDB_IG_IDEMPOTENCY_TABLE> --region eu-west-2`
   - `aws sqs get-queue-url --queue-name <IG_DLQ_QUEUE_NAME> --region eu-west-2`
3. Behavioral probes:
   - `POST <IG_BASE_URL><IG_INGEST_PATH>` with valid key and small payload -> `202`
   - `POST <IG_BASE_URL><IG_INGEST_PATH>` with valid key and oversized payload -> `413`
   - `GET <IG_BASE_URL><IG_HEALTHCHECK_PATH>` with valid key -> `200` and envelope contract fields

P4.D scoped blocker mapping (must be explicit before transition):
1. `P4D-B1` -> `M5P4-B5`: required envelope handles missing/unpinned.
2. `P4D-B2` -> `M5P4-B5`: runtime materialization drift vs pinned envelope handles.
3. `P4D-B3` -> `M5P4-B5`: behavioral envelope probe mismatch.
4. `P4D-B4` -> `M5P4-B8`: durable artifact publish/readback failure.

P4.D exit rule:
1. required envelope handles are pinned and resolved,
2. runtime materialization matches pinned envelope values,
3. behavioral probes satisfy small/large payload contract,
4. `m5i_ingress_envelope_snapshot.json`, `m5i_blocker_register.json`, and `m5i_execution_summary.json` exist locally and durably,
5. no active `P4D-B*` blocker remains,
6. P4.E remains blocked until explicit P4.D pass evidence is committed.

P4.D execution closure (2026-02-25):
1. Runtime conformance remediation applied before authoritative run:
   - materialized IG envelope controls into runtime stack (`IG_*` env surfaces),
   - added DLQ queue resource and wiring (`fraud-platform-dev-full-ig-dlq`),
   - applied API Gateway stage throttling and integration timeout from pinned handles,
   - added IG payload-size fail-closed behavior (`413` on oversize payload).
2. Authoritative green run:
   - execution id: `m5i_p4d_ingress_envelope_20260225T020758Z`
   - local root: `runs/dev_substrate/dev_full/m5/m5i_p4d_ingress_envelope_20260225T020758Z/`
   - summary: `runs/dev_substrate/dev_full/m5/m5i_p4d_ingress_envelope_20260225T020758Z/m5i_execution_summary.json`
   - result: `overall_pass=true`, blockers `[]`, next gate `M5.J_READY`.
3. Contract outcomes (authoritative):
   - normal ingest with valid key: `202`,
   - oversized ingest with valid key: `413` + `payload_too_large`,
   - integration timeout: `30000ms` (`IG_REQUEST_TIMEOUT_SECONDS=30`),
   - stage throttles: `rps=200`, `burst=400`,
   - DDB TTL enabled on `ttl_epoch`,
   - DLQ queue exists and wired.
4. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5i_p4d_ingress_envelope_20260225T020758Z/m5i_ingress_envelope_snapshot.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5i_p4d_ingress_envelope_20260225T020758Z/m5i_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5i_p4d_ingress_envelope_20260225T020758Z/m5i_execution_summary.json`
5. Gate impact:
   - P4.D is green; P4.E (`M5.J`) is unblocked.

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
- [x] P4 rollup matrix and blocker register committed.
- [x] deterministic P4 verdict artifact committed.
- [x] `m6_handoff_pack.json` committed locally and durably.
- [x] M5 execution summary committed locally and durably.

P4.E precheck:
1. P4.A..P4.D artifacts exist and are readable.
2. unresolved blocker set is explicit before verdict emission.

P4.E execution closure (2026-02-25):
1. Authoritative green run:
   - execution id: `m5j_p4e_gate_rollup_20260225T021715Z`
   - local root: `runs/dev_substrate/dev_full/m5/m5j_p4e_gate_rollup_20260225T021715Z/`
   - summary: `runs/dev_substrate/dev_full/m5/m5j_p4e_gate_rollup_20260225T021715Z/m5j_execution_summary.json`
   - result: `overall_pass=true`, blockers `[]`, verdict `ADVANCE_TO_M6`, next gate `M6_READY`.
2. P4 rollup outcomes:
   - source lanes: `P4.A..P4.D`,
   - lane pass count: `4/4`,
   - unresolved blocker set: none.
3. Cost-outcome hard-stop closure:
   - `m5j_phase_budget_envelope.json` emitted,
   - `m5j_phase_cost_outcome_receipt.json` emitted (`spend_amount=64.835684`, `USD`),
   - no `M5-B11`/`M5-B12` active blocker.
4. Durable evidence:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5j_p4e_gate_rollup_20260225T021715Z/m5j_p4_gate_rollup_matrix.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5j_p4e_gate_rollup_20260225T021715Z/m5j_p4_blocker_register.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5j_p4e_gate_rollup_20260225T021715Z/m5j_p4_gate_verdict.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5j_p4e_gate_rollup_20260225T021715Z/m6_handoff_pack.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5j_p4e_gate_rollup_20260225T021715Z/m5j_phase_budget_envelope.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5j_p4e_gate_rollup_20260225T021715Z/m5j_phase_cost_outcome_receipt.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5j_p4e_gate_rollup_20260225T021715Z/m5_execution_summary.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m5j_p4e_gate_rollup_20260225T021715Z/m5j_execution_summary.json`
5. Gate impact:
   - P4 is closed green,
   - M6 entry is unblocked (`ADVANCE_TO_M6`).

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
