# Local Run Process Inventory Matrix (Baseline for Migration)
_As of 2026-02-12_

## Purpose
Capture what "it worked locally" means at process depth before managed-substrate cutover.
This is the mandatory baseline artifact referenced by the dev-substrate migration playbook.

## Source Authorities
1. `docs/runbooks/platform_parity_walkthrough_v0.md`
2. `config/platform/run_operate/packs/local_parity_control_ingress.v0.yaml`
3. `config/platform/run_operate/packs/local_parity_rtdl_core.v0.yaml`
4. `config/platform/run_operate/packs/local_parity_rtdl_decision_lane.v0.yaml`
5. `config/platform/run_operate/packs/local_parity_case_labels.v0.yaml`
6. `config/platform/run_operate/packs/local_parity_learning_jobs.v0.yaml`
7. `config/platform/run_operate/packs/local_parity_obs_gov.v0.yaml`
8. `makefile` parity and dev-substrate phase targets
9. `infra/local/docker-compose.platform-parity.yaml`

## Scope Boundary
- Included: processes required for local parity full-run execution and the current dev-substrate local-operator migration lane.
- Excluded: ad-hoc diagnostics that are not required for run success (for example manual one-off AWS/Kinesis probe commands).

## ID Scheme
- `LP-INF-*` infrastructure and bootstrap
- `LP-ORA-*` Oracle Store local lane
- `LP-CI-*` Control and Ingress chain
- `LP-RTDLC-*` RTDL core workers
- `LP-RTDLD-*` RTDL decision-lane workers
- `LP-CL-*` Case and Label workers
- `LP-LRN-*` Learning jobs
- `LP-OG-*` Observability and governance
- `LP-DM-*` dev-substrate migration commands still executed from local operator compute

## Matrix
| Process ID | Corridor | Local process (command/entrypoint) | Runtime substrate (local) | State / evidence touched | Managed migration note |
|---|---|---|---|---|---|
| LP-INF-001 | Infra | `make platform-parity-stack-up` | Local shell -> Docker Compose | Starts MinIO/LocalStack/Postgres containers | Replace with managed infra lifecycle (`phase2` Terraform + managed services). |
| LP-INF-002 | Infra | `minio` service (`docker-compose.platform-parity.yaml`) | Local Docker container | `oracle-store` and `fraud-platform` buckets on local volume | Replace with AWS S3 buckets/prefix policy. |
| LP-INF-003 | Infra | `localstack` service (`kinesis`) | Local Docker container | local Kinesis stream backend for EB/control/context/audit | Replace with managed Kafka/Kinesis corridor per dev-substrate settlement. |
| LP-INF-004 | Infra | `postgres` service | Local Docker container | IG/WSP/RTDL/Case/Label/Learning DSN-backed stores | Replace with managed Postgres/other managed stores per component plans. |
| LP-INF-005 | Infra | `minio-init` | Local Docker init container | Ensures `oracle-store` and `fraud-platform` buckets exist | Replace with Terraform-managed bucket provisioning. |
| LP-INF-006 | Infra | `localstack-init` | Local Docker init container | Ensures required local Kinesis streams exist | Replace with managed topic/stream provisioning + ACLs. |
| LP-INF-007 | Infra | `make platform-parity-bootstrap` | Local shell + inline Python/boto3 | Creates local streams and buckets (idempotent bootstrap) | Replace with managed readiness gates (`phase3b` infra readiness). |
| LP-INF-008 | Control | `make platform-run-new` -> `fraud_detection.platform_runtime` | Local Python process | `runs/fraud-platform/ACTIVE_RUN_ID` | Keep semantics; move run control evidence/state to managed acceptance corridor. |
| LP-INF-009 | Orchestration | `make platform-operate-parity-up/down/status` | Local orchestrator process | `runs/fraud-platform/operate/<pack_id>/*` process state/events/logs | Replace with managed orchestration pack execution (no laptop process dependency). |
| LP-ORA-001 | Oracle | `make platform-oracle-sync` | Local shell + `aws s3 sync` | Copies engine outputs to MinIO Oracle root | In dev-min this is `phase3c1 sync` to managed S3 root (transitional until direct engine write). |
| LP-ORA-002 | Oracle | `make platform-oracle-pack` -> `fraud_detection.oracle_store.packer` | Local Python process | `_oracle_pack_manifest.json`, `_SEALED.json` | Keep contract; execution substrate can move, artifact contract unchanged. |
| LP-ORA-003 | Oracle | `make platform-oracle-check-strict` -> strict seal check | Local Python process | strict checker evidence | Keep strict fail-closed checker in managed lane. |
| LP-ORA-004 | Oracle | `make platform-oracle-stream-sort` -> `stream_sort_cli` | Local Python + DuckDB compute | `stream_view/ts_utc/output_id=.../part-*.parquet`, stream sort receipts/manifests | Primary migration blocker surface: move compute off laptop while preserving output contract. |
| LP-ORA-005 | Oracle | `make platform-oracle-stream-sort-context-fraud` | Local Python + DuckDB compute | context fraud stream-view outputs | Same as LP-ORA-004. |
| LP-ORA-006 | Oracle | `make platform-oracle-stream-sort-context-baseline` | Local Python + DuckDB compute | context baseline stream-view outputs | Same as LP-ORA-004. |
| LP-ORA-007 | Oracle | `make platform-oracle-stream-sort-traffic-both` | Local Python + DuckDB compute | traffic baseline+fraud stream-view outputs | Same as LP-ORA-004. |
| LP-CI-001 | Control/Ingress | `make platform-operate-control-ingress-up` | Local orchestrator process | pack state/events/logs under `runs/fraud-platform/operate/local_parity_control_ingress_v0/` | Launch mechanism must move to managed runner/controller for acceptance runs. |
| LP-CI-002 | IG | `fraud_detection.ingestion_gate.service` (`ig_service`) | Local Python daemon | Admission DB (`PARITY_IG_ADMISSION_DSN`), receipts/quarantine refs under platform store | Move daemon runtime to managed compute; preserve admission truth ownership and receipt contracts. |
| LP-CI-003 | SR | `make platform-sr-run-reuse` -> `fraud_detection.scenario_runner.cli run` | Local Python command process | SR run records, run facts view, readiness outputs under `s3://fraud-platform/<run>/sr/` | Must become managed runtime execution for dev-min acceptance. |
| LP-CI-003A | SR (internal) | SR plan compilation + gate derivation (`ScenarioRunner.submit_run`) | In-process (local Python) | run plan + gate intent artifacts | Keep deterministic behavior; move compute substrate only. |
| LP-CI-003B | SR (internal) | Evidence/gate verification | In-process (local Python) | by-ref evidence reads + gate verdicts | Preserve no-PASS-no-read fail-closed law. |
| LP-CI-003C | SR (internal) | Engine invocation adapter attempt lifecycle | Local subprocess from SR | attempt events/logs and run status facts | Move invocation host to managed execution lane. |
| LP-CI-003D | SR (internal) | Run facts + READY emission | In-process + control bus publish | control message with pins/idempotency | Keep idempotency and pin schema unchanged under managed bus. |
| LP-CI-004 | WSP | `fraud_detection.world_streamer_producer.ready_consumer` (`wsp_ready_consumer`) | Local Python daemon | WSP checkpoints (`PARITY_WSP_CHECKPOINT_DSN`) | Move daemon compute; maintain checkpoint/idempotent replay semantics. |
| LP-CI-004A | WSP (internal) | Poll control bus for READY | In-process | control offsets/checkpoints | Managed consumer group behavior must preserve run-scope filtering. |
| LP-CI-004B | WSP (internal) | Resolve Oracle stream-view refs and read sorted parquet | In-process + S3 client | Oracle stream-view reads | Must keep stream-view contract and sorted assumptions. |
| LP-CI-004C | WSP (internal) | Emit envelopes to IG ingest API | In-process HTTP client | IG admission attempts and downstream EB refs | Maintain retry class behavior + fail-closed mismatch handling. |
| LP-CI-005 | WSP | `make platform-wsp-ready-consumer-once` | Local Python one-shot | same as LP-CI-004 but bounded | Keep as bounded validation rung in managed acceptance ladder. |
| LP-CI-006 | IG/EB boundary | IG admission -> EB publish path | Local IG process + local Kinesis backend | `eb_ref` in receipts, offsets in bus backend | In dev-min backend changes but ownership boundary must remain IG->EB. |
| LP-RTDLC-001 | RTDL Core | `make platform-operate-rtdl-core-up` | Local orchestrator process | pack state/events/logs | Managed launcher required for acceptance runs. |
| LP-RTDLC-002 | IEG | `fraud_detection.identity_entity_graph.projector` | Local Python daemon | IEG projection DB (`PARITY_IEG_PROJECTION_DSN`) | Move compute; preserve deterministic projection/checkpoint behavior. |
| LP-RTDLC-003 | OFP | `fraud_detection.online_feature_plane.projector` | Local Python daemon | OFP projection + snapshot index DSNs | Move compute; preserve snapshot hash and basis semantics. |
| LP-RTDLC-004 | CSFB | `fraud_detection.context_store_flow_binding.intake` | Local Python daemon | CSFB projection DSN | Move compute; preserve flow-binding semantics and run scope checks. |
| LP-RTDLC-005 | Archive Writer | `fraud_detection.archive_writer.worker` | Local Python daemon | Archive writer ledger DSN + archive refs | Move compute; keep append-only archive authority semantics. |
| LP-RTDLD-001 | RTDL Decision | `make platform-operate-rtdl-decision-up` | Local orchestrator process | pack state/events/logs | Managed launcher required for acceptance runs. |
| LP-RTDLD-002 | DL | `fraud_detection.degrade_ladder.worker` | Local Python daemon | DL posture/outbox/ops DSNs | Move compute; preserve fail-closed posture outcomes. |
| LP-RTDLD-003 | DF | `fraud_detection.decision_fabric.worker` | Local Python daemon | DF replay/checkpoint DSNs | Move compute; preserve deterministic resolver and idempotency. |
| LP-RTDLD-004 | AL | `fraud_detection.action_layer.worker` | Local Python daemon | AL ledger/outcomes/replay/checkpoint DSNs | Move compute; preserve semantic idempotency + uncertain-commit handling. |
| LP-RTDLD-005 | DLA | `fraud_detection.decision_log_audit.worker` | Local Python daemon | DLA index/audit truth DSN + by-ref evidence | Move compute; preserve append-only lineage and replay determinism. |
| LP-CL-001 | Case/Label | `make platform-operate-case-labels-up` | Local orchestrator process | pack state/events/logs | Managed launcher required for acceptance runs. |
| LP-CL-002 | Case Trigger | `fraud_detection.case_trigger.worker` | Local Python daemon | case trigger replay/checkpoint/publish store DSNs | Move compute; preserve trigger idempotency + publish semantics. |
| LP-CL-003 | Case Mgmt | `fraud_detection.case_mgmt.worker` | Local Python daemon | case management locator DSN | Move compute; preserve append-only timeline semantics. |
| LP-CL-004 | Label Store | `fraud_detection.label_store.worker` | Local Python daemon | label store locator DSN | Move compute; preserve label truth ownership and as-of semantics. |
| LP-LRN-001 | Learning | `make platform-operate-learning-jobs-up` | Local orchestrator process | pack state/events/logs | Managed launcher required for acceptance runs. |
| LP-LRN-002 | OFS Worker | `fraud_detection.offline_feature_plane.worker run` | Local Python daemon | OFS run ledger DSN + job request prefix + artifacts | Move compute; preserve deterministic replay/label/manifest gates. |
| LP-LRN-003 | MF Worker | `fraud_detection.model_factory.worker run` | Local Python daemon | MF run ledger DSN + job request prefix + artifacts | Move compute; preserve deterministic build/publish contracts. |
| LP-LRN-004 | OFS enqueue build | `make platform-ofs-enqueue-build` | Local Python command process | writes OFS job request envelope | Can remain operator command; acceptance compute belongs to worker lane. |
| LP-LRN-005 | OFS enqueue publish-retry | `make platform-ofs-enqueue-publish-retry` | Local Python command process | writes OFS publish retry request | Same as LP-LRN-004. |
| LP-LRN-006 | MF enqueue train-build | `make platform-mf-enqueue-train-build` | Local Python command process | writes MF job request envelope | Same as LP-LRN-004. |
| LP-LRN-007 | MF enqueue publish-retry | `make platform-mf-enqueue-publish-retry` | Local Python command process | writes MF publish retry request | Same as LP-LRN-004. |
| LP-OG-001 | Obs/Gov | `make platform-operate-obs-gov-up` | Local orchestrator process | pack state/events/logs | Managed launcher required for acceptance runs. |
| LP-OG-002 | Run Reporter | `fraud_detection.platform_reporter.worker` | Local Python daemon | run reporter artifacts and summary outputs | Move compute; preserve run-scoped evidence stamping. |
| LP-OG-003 | Conformance | `fraud_detection.platform_conformance.worker` | Local Python daemon | conformance receipts/reconciliation outputs | Move compute; preserve fail-closed conformance checks. |
| LP-OG-004 | Manual run report | `make platform-run-report` | Local Python command process | explicit reporter artifact generation | Keep as diagnostics; avoid conflicting with daemonized reporter in acceptance runs. |
| LP-OG-005 | Manual governance query | `make platform-governance-query` | Local Python command process | governance query outputs | Diagnostic/support process; not required daemon lane. |
| LP-OG-006 | Manual env conformance | `make platform-env-conformance` | Local Python command process | one-shot conformance check output | Diagnostic/support process; not required daemon lane. |
| LP-DM-001 | Dev-substrate migration lane | `make platform-dev-min-phase3a-check` | Local Python command process | phase3 settlement evidence JSON | Keep as preflight gate; execution location can remain operator lane. |
| LP-DM-002 | Dev-substrate migration lane | `make platform-dev-min-phase3b-readiness` | Local Python command process | infra readiness evidence JSON | Keep as preflight gate; execution location can remain operator lane. |
| LP-DM-003 | Dev-substrate migration lane | `make platform-dev-min-phase3c1-preflight` | Local Python command process | Oracle preflight evidence JSON | Keep as preflight gate; execution location can remain operator lane. |
| LP-DM-004 | Dev-substrate migration lane | `make platform-dev-min-phase3c1-sync` | Local shell + `aws s3 sync` | managed S3 Oracle landing state + sync evidence | Transitional local compute process until fully managed ingestion path is available. |
| LP-DM-005 | Dev-substrate migration lane | `make platform-dev-min-phase3c1-stream-sort` | Local Python + DuckDB compute | managed S3 stream-view outputs + stream-sort evidence | Primary compute-offload target for migration. |
| LP-DM-006 | Dev-substrate migration lane | `make platform-dev-min-phase3c1-stream-sort-managed` | Local submit/monitor process + managed Batch job compute | managed sort job evidence + CloudWatch/job status | Submission stays local; compute is managed (target posture). |
| LP-DM-007 | Dev-substrate migration lane | `make platform-dev-min-phase3c1-validate` | Local Python command process | strict Oracle authority evidence JSON | Keep as validation gate. |
| LP-DM-008 | Dev-substrate migration lane | `make platform-dev-min-phase3c1-run` | Local Python command process (composite runner) | preflight+sync+sort+validate evidence chain | Composite convenience command; acceptance should reference explicit per-step evidence. |
| LP-DM-009 | Dev-substrate migration lane | `make platform-dev-min-phase3c2-s1-preflight` | Local Python command process | SR settlement-lock preflight evidence JSON | Keep as validation gate; required before SR managed cutover acceptance. |

## Completeness Snapshot
- Total inventoried process IDs in this pass: `65`.
- Active migration corridor (`3.C` Oracle + SR + WSP + IG + EB boundary) is covered.
- RTDL/Case/Label/Learning/Obs worker processes are included to preserve full-run visibility.

## Known Gaps to Fill in Next Pass
1. Add per-process throughput/SLO and resource envelope baselines from observed local runs.
2. Add exact managed target runtime contracts per process (`container image`, `queue/definition`, `service account/IAM`, `secret handles`).
3. Add process-level rollback actions and cutover evidence refs once managed lanes are implemented.

