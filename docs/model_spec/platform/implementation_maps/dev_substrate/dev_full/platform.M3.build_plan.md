# Dev Substrate Deep Plan - M3 (P1 Run Pinning and Orchestrator Readiness)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M3._
_Last updated: 2026-02-23_

## 0) Purpose
M3 closes `P1 RUN_PINNED` for `dev_full` by producing deterministic run identity, config digest, and run-scope evidence that will gate all downstream phases.

M3 must prove:
1. run identity is deterministic and non-colliding,
2. run header and run config digest are committed once and durably,
3. orchestrator entry and run lock posture are valid for this run scope,
4. M4 handoff carries explicit `REQUIRED_PLATFORM_RUN_ID` and correlation contract anchors.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (P1 section)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M2.build_plan.md`
2. `runs/dev_substrate/dev_full/m2/m2j_20260223T061612Z/m2j_m3_entry_readiness_receipt.json`
3. `docs/model_spec/platform/contracts/scenario_runner/run_record.schema.yaml`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`

## 2) Scope Boundary for M3
In scope:
1. P1 handle closure for run pinning/digest/evidence paths.
2. Deterministic `platform_run_id` and `scenario_run_id` derivation checks.
3. Canonical config payload assembly and digest reproducibility checks.
4. Durable publication of `run.json` and run-pin evidence surfaces.
5. Orchestrator entry and run-lock readiness validation.
6. M4 run-scope handoff pack and fail-closed blocker adjudication.

Out of scope:
1. Runtime lane health checks (`M4/P2`).
2. Oracle and ingest preflight (`M5/P3-P4`).
3. Streaming/runtime execution (`P5+`).
4. Any broad substrate reprovisioning not required for P1 closure.

## 3) M3 Deliverables
1. M3 handle closure matrix and decision completeness snapshot.
2. Deterministic run identity snapshot (collision-checked).
3. Canonical run payload and digest reproducibility snapshot.
4. Durable `run.json` + run-header write receipt.
5. M4 handoff pack with required runtime scope fields.
6. M3 blocker register and final verdict (`ADVANCE_TO_M4` or `HOLD_M3`).

## 4) Entry Gate and Current Posture
Entry gate for M3:
1. M2 is `DONE` with blocker-free handoff.

Current posture:
1. M2 handoff is valid and present.
2. This phase is in planning mode only.

Current pre-execution blockers (fail-closed):
1. `M3-B0`: runtime orchestrator surface is currently down after teardown (`runtime` stack destroyed), so P1 orchestrator-entry checks cannot yet pass.
2. `M3-B0.1`: `ROLE_TERRAFORM_APPLY_DEV_FULL` remains `TO_PIN` in registry and must be pinned before managed execution identity is declared closed.

## 4.1 Anti-Cram Law (Binding for M3)
M3 is not execution-ready unless these capability lanes are explicit:
1. authority/handles,
2. identity/IAM,
3. network/control-plane reachability,
4. data stores/evidence roots,
5. messaging/orchestrator references,
6. secrets posture (no plaintext leakage),
7. observability/evidence publication,
8. rollback/rerun policy,
9. phase budget and cost-to-outcome receipt.

## 4.2 Capability Lane Coverage Matrix
| Capability lane | Primary owner sub-phase | Minimum PASS evidence |
| --- | --- | --- |
| Authority + handle closure | M3.A | handle closure snapshot with no unresolved required keys |
| Run identity + collision law | M3.B | run-id generation snapshot with collision probe receipts |
| Canonical payload + digest | M3.C | digest reproducibility snapshot |
| Orchestrator + lock readiness | M3.D | orchestrator-entry readiness snapshot |
| Durable evidence publication | M3.E | S3 write receipts for `run.json` and run header |
| Runtime scope export | M3.F | M4 handoff pack with `REQUIRED_PLATFORM_RUN_ID` |
| Rerun/reset discipline | M3.G | rerun/reset policy snapshot with fail-closed rules |
| Cost/evidence discipline | M3.H | M3 phase budget envelope + cost-outcome receipt |
| Gate rollup and blocker adjudication | M3.I | M3 gate rollup + blocker register |
| Handoff closure | M3.J | M3 execution summary with verdict and M4-ready marker |

## 5) Work Breakdown (Deep)

### M3.A Authority + Handle Closure Matrix
Goal:
1. close all required P1 handles before execution.

Tasks:
1. resolve required run-identity and digest handles:
   - `FIELD_PLATFORM_RUN_ID`
   - `FIELD_SCENARIO_RUN_ID`
   - `FIELD_CONFIG_DIGEST`
   - `CONFIG_DIGEST_ALGO`
   - `CONFIG_DIGEST_FIELD`
   - `SCENARIO_EQUIVALENCE_KEY_INPUT`
   - `SCENARIO_EQUIVALENCE_KEY_CANONICAL_FIELDS`
   - `SCENARIO_EQUIVALENCE_KEY_CANONICALIZATION_MODE`
   - `SCENARIO_RUN_ID_DERIVATION_MODE`
2. resolve required evidence path handles:
   - `S3_EVIDENCE_BUCKET`
   - `S3_EVIDENCE_RUN_ROOT_PATTERN`
   - `RUN_PIN_PATH_PATTERN`
   - `EVIDENCE_RUN_JSON_KEY`
3. resolve required orchestrator/scope handles:
   - `SFN_PLATFORM_RUN_ORCHESTRATOR_V0`
   - `SR_READY_COMMIT_AUTHORITY`
   - `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`
4. classify unresolved required handles as blockers.

DoD:
- [x] required M3 handle set is explicit and complete.
- [x] every required handle has a verification method.
- [x] unresolved required handles are blocker-marked.

M3.A decision pins (closed before execution):
1. Handle-source law:
   - every required M3.A handle must map to one source class only:
     - registry literal,
     - M2 handoff artifact,
     - runtime stack output/control-plane query.
2. Placeholder law:
   - any required handle with value `TO_PIN` is an execution blocker.
3. Runtime-path law:
   - M3.A must not claim orchestrator-entry readiness if runtime stack is down.
4. Non-secret evidence law:
   - M3.A evidence may include handle keys and non-secret values only; no secret payloads/credentials.

M3.A verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3A-V1-HANDLE-EXISTS` | `rg -n "\\b<HANDLE_KEY>\\b" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` | confirms required handle key exists in registry |
| `M3A-V2-PLACEHOLDER-GUARD` | `rg -n "^\\* `<HANDLE_KEY> = \\\"TO_PIN\\\"`" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` | fails closed if required handle remains placeholder |
| `M3A-V3-M2-HANDOFF` | `Test-Path runs/dev_substrate/dev_full/m2/m2j_20260223T061612Z/m2j_m3_entry_readiness_receipt.json` | confirms M2->M3 handoff artifact exists |
| `M3A-V4-SFN-QUERY` | `aws stepfunctions list-state-machines --region eu-west-2` | verifies orchestrator state-machine surface exists |
| `M3A-V5-EVIDENCE-BUCKET` | `aws s3api head-bucket --bucket <S3_EVIDENCE_BUCKET>` | verifies durable evidence root is reachable |
| `M3A-V6-CORE-OUTPUTS` | `terraform -chdir=infra/terraform/dev_full/core output -json` | validates runtime-referenced handles against stack outputs |

M3.A blocker taxonomy (fail-closed):
1. `M3A-B1`: required handle key missing from registry.
2. `M3A-B2`: required handle value unresolved (`TO_PIN`).
3. `M3A-B3`: M2->M3 handoff artifact missing/unreadable.
4. `M3A-B4`: orchestrator runtime surface unavailable/unqueryable.
5. `M3A-B5`: evidence bucket/root unreachable.
6. `M3A-B6`: control-plane/stack output contradictions for required handle values.
7. `M3A-B7`: M3.A evidence artifact set missing/incomplete.

M3.A evidence contract (planned):
1. `m3a_handle_closure_snapshot.json`
2. `m3a_blocker_register.json`
3. `m3a_command_receipts.json`

`m3a_handle_closure_snapshot.json` minimum fields:
1. `required_handles`
2. `resolved_handles`
3. `unresolved_handles`
4. `placeholder_handles`
5. `source_class_by_handle`
6. `verification_results`
7. `overall_pass`

M3.A closure rule:
1. M3.A can close only when:
   - all required handles are present and source-mapped,
   - required handle set has zero unresolved `TO_PIN`,
   - M2->M3 handoff artifact is readable,
   - orchestrator/evidence surfaces required for P1 are queryable or explicitly blocker-marked with hold verdict,
   - M3.A evidence contract is complete.

M3.A planning status (pre-execution historical):
1. Required handles are enumerated.
2. Known open blockers before execution were:
   - `M3A-B2`: `ROLE_TERRAFORM_APPLY_DEV_FULL` is currently `TO_PIN`.
   - `M3A-B4`: runtime orchestrator surface is down post-teardown and cannot satisfy readiness query until rematerialized.
3. Phase posture:
   - planning expanded and then executed.

M3.A execution status (2026-02-23):
1. Authoritative execution id:
   - `m3a_20260223T174307Z`
2. Local evidence root:
   - `runs/dev_substrate/dev_full/m3/m3a_20260223T174307Z/`
3. Durable evidence mirror:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m3a_20260223T174307Z/`
4. PASS artifacts:
   - `m3a_handle_closure_snapshot.json`
   - `m3a_blocker_register.json`
   - `m3a_command_receipts.json`
   - `m3a_execution_summary.json`
   - `m3a_rematerialization_receipts.json`
5. Closure results:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M3.A_READY`
   - required handle set: `17/17` present, placeholder count `0`
   - orchestrator query pass: `true` (Step Functions state machine present)
6. Blocker remediation outcomes:
   - `M3A-B2` closed by pinning `ROLE_TERRAFORM_APPLY_DEV_FULL` from `TO_PIN` to active apply principal.
   - `M3A-B4` closed by rematerializing `core -> streaming -> runtime` and re-verifying Step Functions orchestrator surface.
7. Wrapper/runtime command-surface retries occurred during remediation; failed attempts are retained as audit artifacts and excluded from closure evidence.

### M3.B Run Identity Generation Contract
Goal:
1. generate deterministic run identity with collision protection.

Tasks:
1. pin `platform_run_id` format and regex.
2. derive `scenario_run_id` using pinned deterministic mode.
3. collision-probe `evidence/runs/{platform_run_id}/`.
4. enforce deterministic retry suffix policy if collision exists.
5. emit run identity snapshot with collision receipts.

DoD:
- [ ] run-id format pin is explicit.
- [ ] collision probes are evidenced.
- [ ] scenario-run derivation is deterministic and reproducible.

### M3.C Config Payload + Digest Contract
Goal:
1. produce canonical run payload and reproducible digest.

Tasks:
1. assemble canonical payload fields for run pin.
2. canonicalize using pinned mode (`json_sorted_keys_v1`).
3. compute digest with pinned algorithm and field name.
4. recompute and compare digest for reproducibility.
5. emit payload hash evidence without secrets.

DoD:
- [ ] payload field set is explicit and complete.
- [ ] digest reproducibility check passes.
- [ ] payload evidence is secret-safe.

### M3.D Orchestrator Entry + Lock Identity Readiness
Goal:
1. verify P1 orchestrator-entry surface and run-lock posture.

Tasks:
1. verify Step Functions state machine exists and is queryable.
2. verify execution role handle alignment with runtime stack outputs.
3. define run-lock identity mechanism and fail-closed behavior.
4. emit orchestrator-entry readiness snapshot.

DoD:
- [ ] orchestrator-entry surface is reachable and evidenced.
- [ ] lock identity contract is explicit.
- [ ] runtime-role alignment check passes or blocker is explicit.

### M3.E Durable Run Evidence Publication
Goal:
1. publish run pin artifacts to durable evidence root exactly once.

Tasks:
1. write `run.json` to `EVIDENCE_RUN_JSON_KEY`.
2. write run header to `RUN_PIN_PATH_PATTERN`.
3. emit write receipts and integrity checks (head/readback).
4. enforce write-once posture for the same run id.

DoD:
- [ ] durable `run.json` write succeeds and readback passes.
- [ ] durable run-header write succeeds and readback passes.
- [ ] write-once guard behavior is documented.

### M3.F Runtime Scope Export and M4 Handoff
Goal:
1. export run-scope contract required by M4.

Tasks:
1. build handoff pack containing:
   - `platform_run_id`
   - `scenario_run_id`
   - `config_digest`
   - `required_platform_run_id_env_key`
   - correlation required fields list
2. verify handoff pack references durable M3 artifacts.
3. emit `m4_handoff_pack.json` locally and durably.

DoD:
- [ ] handoff pack contains all required run-scope fields.
- [ ] handoff references are durable and readable.
- [ ] M4 runtime-scope env mapping is explicit.

### M3.G Rerun and Reset Discipline
Goal:
1. codify fail-closed rerun behavior for P1 identity changes.

Tasks:
1. pin rerun rules for digest drift and identity drift.
2. require new `platform_run_id` on identity/config change.
3. prohibit destructive mutation of existing run evidence.
4. emit rerun/reset policy snapshot for M3.

DoD:
- [ ] rerun/reset rules are explicit and auditable.
- [ ] destructive rerun paths are prohibited.
- [ ] identity drift behavior is fail-closed.

### M3.H Cost Envelope and Outcome Receipt
Goal:
1. satisfy phase budget law for M3 before advancement.

Tasks:
1. emit M3 phase budget envelope.
2. record M3 spend window and expected proof artifacts.
3. emit M3 cost-to-outcome receipt.

DoD:
- [ ] phase budget envelope is committed.
- [ ] cost-to-outcome receipt is committed.
- [ ] spend-without-proof is fail-closed.

### M3.I Gate Rollup and Blocker Adjudication
Goal:
1. roll up M3.A..M3.H evidence into a single P1 verdict.

Tasks:
1. collect lane evidence and verify completeness.
2. evaluate blockers severity and closure status.
3. publish M3 gate rollup matrix and blocker register.

DoD:
- [ ] rollup matrix is complete.
- [ ] unresolved blocker set is explicit.
- [ ] P1 verdict is deterministic.

### M3.J Phase Verdict and M4 Entry Marker
Goal:
1. close M3 and issue M4 entry marker if green.

Tasks:
1. publish `m3_execution_summary.json`.
2. publish `m4_entry_readiness_receipt.json`.
3. append closure note to master plan, impl map, and logbook.

DoD:
- [ ] M3 summary artifact committed.
- [ ] M4 entry readiness marker committed (if green).
- [ ] closure notes are appended to required docs.

## 6) M3 Blocker Taxonomy (Fail-Closed)
- `M3-B0`: runtime orchestrator surface unavailable at phase start.
- `M3-B0.1`: unresolved required `TO_PIN` handle blocks execution identity closure.
- `M3-B1`: required handle missing or inconsistent with authority.
- `M3-B2`: run-id collision unresolved or invalid identity format.
- `M3-B3`: scenario equivalence or digest contract mismatch.
- `M3-B4`: orchestrator/lock readiness failure.
- `M3-B5`: durable evidence write/readback failure.
- `M3-B6`: run-scope handoff pack missing/incomplete.
- `M3-B7`: rerun/reset policy inconsistency or destructive path detected.
- `M3-B8`: phase budget envelope or cost outcome receipt missing.
- `M3-B9`: rollup evidence incomplete/inconsistent.

Any active `M3-B*` blocker prevents M3 closure.

## 7) M3 Completion Checklist
- [x] M3.A complete.
- [ ] M3.B complete.
- [ ] M3.C complete.
- [ ] M3.D complete.
- [ ] M3.E complete.
- [ ] M3.F complete.
- [ ] M3.G complete.
- [ ] M3.H complete.
- [ ] M3.I complete.
- [ ] M3.J complete.
- [ ] M3 blockers resolved or explicitly fail-closed.
- [ ] M3 closure note appended in implementation map.
- [ ] M3 action log appended in logbook.

## 8) Exit Criteria and Handoff
M3 can close only when:
1. all checklist items in Section 7 are complete,
2. P1 verdict is blocker-free,
3. run pin + digest + durable evidence are complete and readable,
4. M4 handoff receipt is committed and explicit.

Handoff posture:
1. M4 remains blocked until M3 verdict is `ADVANCE_TO_M4`.
