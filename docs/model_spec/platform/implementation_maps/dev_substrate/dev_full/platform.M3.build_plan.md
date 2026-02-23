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
- [x] run-id format pin is explicit.
- [x] collision probes are evidenced.
- [x] scenario-run derivation is deterministic and reproducible.

M3.B decision pins (closed before execution):
1. Platform-run-id format law:
   - `platform_run_id` format is `platform_<YYYYMMDDTHHMMSSZ>` (UTC, second precision).
2. Platform-run-id regex law:
   - accepted shape regex: `^platform_[0-9]{8}T[0-9]{6}Z(_[0-9]{2})?$`.
3. Collision law:
   - collision check target is durable evidence root prefix:
     - `evidence/runs/{platform_run_id}/`
   - if prefix has objects, the id is treated as colliding.
4. Retry/suffix law:
   - collisions are resolved by deterministic monotonic suffix:
     - `_01`, `_02`, ... `_20` (max 20 retries).
5. Scenario-run derivation law:
   - `scenario_run_id` must be generated via `SCENARIO_RUN_ID_DERIVATION_MODE` using `SCENARIO_EQUIVALENCE_KEY_INPUT` and canonical fields from registry.
   - no random/uuid fallback is allowed.
6. Immutability law:
   - once accepted and emitted in M3.B artifacts, `platform_run_id` and `scenario_run_id` are immutable for this run.

M3.B verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3B-V1-FORMAT` | local regex check against candidate `platform_run_id` | enforces canonical id shape |
| `M3B-V2-COLLISION-PROBE` | `aws s3api list-objects-v2 --bucket <S3_EVIDENCE_BUCKET> --prefix evidence/runs/<platform_run_id>/ --max-keys 1` | detects run-id collision in durable evidence root |
| `M3B-V3-HANDLE-CONTRACT` | `rg -n \"SCENARIO_EQUIVALENCE_KEY_INPUT|SCENARIO_EQUIVALENCE_KEY_CANONICAL_FIELDS|SCENARIO_RUN_ID_DERIVATION_MODE\" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` | confirms scenario-id derivation contract exists |
| `M3B-V4-SEED-WRITE-LOCAL` | write local seed artifact under `runs/dev_substrate/dev_full/m3/<m3b_execution_id>/` | proves local generation trace |
| `M3B-V5-SEED-WRITE-DURABLE` | `aws s3 cp <local_seed> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m3b_execution_id>/m3b_run_identity_seed.json` | proves durable publication lane |

M3.B blocker taxonomy (fail-closed):
1. `M3B-B1`: generated `platform_run_id` fails format regex.
2. `M3B-B2`: collision unresolved within retry cap.
3. `M3B-B3`: scenario derivation contract missing/incomplete.
4. `M3B-B4`: local run-id seed artifact write failure.
5. `M3B-B5`: durable seed artifact publish failure.
6. `M3B-B6`: `scenario_run_id` derivation non-deterministic across recompute.
7. `M3B-B7`: M3.B evidence contract missing/incomplete.

M3.B evidence contract (planned):
1. `m3b_run_id_generation_snapshot.json`
2. `m3b_collision_probe_receipts.json`
3. `m3b_run_identity_seed.json`
4. `m3b_execution_summary.json`

`m3b_run_id_generation_snapshot.json` minimum fields:
1. `candidate_platform_run_id`
2. `final_platform_run_id`
3. `collision_detected`
4. `collision_attempts`
5. `format_check_pass`
6. `scenario_run_id`
7. `scenario_derivation_mode`
8. `scenario_derivation_recompute_pass`
9. `overall_pass`

M3.B closure rule:
1. M3.B can close only when:
   - final `platform_run_id` passes format law,
   - collision probe is evidenced and resolved within retry cap,
   - `scenario_run_id` derivation is deterministic and reproducible,
   - all M3.B evidence artifacts are present locally and in durable run-control prefix,
   - no active `M3B-B*` blockers remain.

M3.B planning status (historical pre-execution):
1. Prerequisite lane `M3.A` is closed green.
2. Required identity/derivation handles are pinned in registry.
3. No known pre-execution blockers for M3.B at planning time.
4. Phase posture:
   - planning expanded before execution.

M3.B execution status (2026-02-23):
1. Authoritative execution id:
   - `m3b_20260223T184232Z`
2. Local evidence root:
   - `runs/dev_substrate/dev_full/m3/m3b_20260223T184232Z/`
3. Durable evidence mirror:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m3b_20260223T184232Z/`
4. PASS artifacts:
   - `m3b_run_id_generation_snapshot.json`
   - `m3b_collision_probe_receipts.json`
   - `m3b_run_identity_seed.json`
   - `m3b_execution_summary.json`
   - `m3b_command_receipts.json`
5. Closure results:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M3.B_READY`
   - `platform_run_id=platform_20260223T184232Z`
   - `scenario_run_id=scenario_38753050f3b70c666e16f7552016b330`
   - collision probe attempts: `1` (no collision, suffix not required)
   - deterministic recompute check: `PASS`
6. Blocker remediation outcomes:
   - prior failed attempt `m3b_20260223T183752Z` had parser drift on list/dict handle values.
   - rerun used strict markdown-handle parser and closed with zero blockers.

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
- [x] payload field set is explicit and complete.
- [x] digest reproducibility check passes.
- [x] payload evidence is secret-safe.

M3.C decision pins (closed before execution):
1. Canonicalization law:
   - payload canonicalization mode is registry-pinned `json_sorted_keys_v1`.
   - canonical encoding uses sorted object keys and UTF-8 JSON bytes.
2. Digest law:
   - digest algorithm is registry-pinned `sha256` (`CONFIG_DIGEST_ALGO`).
   - digest field name is registry-pinned `config_digest` (`CONFIG_DIGEST_FIELD`).
3. Payload composition law:
   - M3.C canonical payload must include at minimum:
     - `platform_run_id` (from M3.B),
     - `scenario_run_id` (from M3.B),
     - `oracle_input_manifest_uri`,
     - `oracle_input_manifest_sha256`,
     - `oracle_required_output_ids`,
     - `oracle_sort_key_by_output_id` (active required-output scope),
     - `phase_id` (`P1`).
4. Digest scope law:
   - `config_digest` is computed from `digest_input_payload` only, where keys match `SCENARIO_EQUIVALENCE_KEY_CANONICAL_FIELDS`.
   - self-reference exclusion applies: `config_digest` key is excluded from digest-input bytes to avoid recursive hash definition.
   - run context fields (`platform_run_id`, `scenario_run_id`, `phase_id`) are persisted in the artifact but excluded from digest input bytes.
   - M3.C must assert equality between recomputed digest and `seed_inputs.config_digest` from authoritative M3.B output.
5. Secret-safety law:
   - payload and digest evidence must not include credentials, SSM secret values, API secrets, or tokens.
6. Immutability law:
   - once `config_digest` is accepted for a run, digest-changing edits require a new `platform_run_id`.
7. Recompute law:
   - digest must be recomputed from a second canonicalization pass and match exactly before closure.
8. Baseline continuity law (M3C-B4 remediation pin):
   - for this migration baseline, `config_digest` must be generated with `m3b_seed_formula_v1` to preserve P1 continuity:
     - `algo`,
     - `oracle_source_namespace`,
     - `oracle_engine_run_id`,
     - `oracle_required_output_ids`,
     - `oracle_sort_key_by_output_id`,
     - `scenario_mode`.
   - M3.C must assert computed digest equals authoritative `seed_inputs.config_digest` from M3.B.

M3.C verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3C-V1-M3B-INPUTS` | `Test-Path runs/dev_substrate/dev_full/m3/<m3b_execution_id>/m3b_run_identity_seed.json` | ensures run identity seed exists for payload assembly |
| `M3C-V2-HANDLE-CONTRACT` | `rg -n \"CONFIG_DIGEST_ALGO|CONFIG_DIGEST_FIELD|SCENARIO_EQUIVALENCE_KEY_CANONICALIZATION_MODE\" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` | confirms digest/canonicalization handles are pinned |
| `M3C-V3-CANONICAL-PAYLOAD-WRITE` | write `m3c_run_config_payload.json` to local M3.C evidence root | proves canonical payload materialization |
| `M3C-V4-DIGEST-RECOMPUTE` | compute digest twice from independent canonicalization passes and compare | proves deterministic digest reproducibility |
| `M3C-V5-DURABLE-PUBLISH` | `aws s3 cp <local_artifact> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m3c_execution_id>/...` | proves durable publication lane |

M3.C blocker taxonomy (fail-closed):
1. `M3C-B1`: required payload fields missing/incomplete.
2. `M3C-B2`: canonicalization mode mismatch or serialization drift.
3. `M3C-B3`: digest algorithm/field contract mismatch.
4. `M3C-B4`: recompute digest mismatch (non-deterministic payload hash).
5. `M3C-B5`: secret material detected in payload/evidence surface.
6. `M3C-B6`: durable evidence publish failure.
7. `M3C-B7`: M3.C evidence contract missing/incomplete.

M3.C evidence contract (planned):
1. `m3c_run_config_payload.json`
2. `m3c_run_config_digest_snapshot.json`
3. `m3c_digest_recompute_receipts.json`
4. `m3c_execution_summary.json`

`m3c_run_config_digest_snapshot.json` minimum fields:
1. `platform_run_id`
2. `scenario_run_id`
3. `phase_id`
4. `canonicalization_mode`
5. `digest_algo`
6. `digest_field`
7. `config_digest`
8. `recompute_digest`
9. `digest_match`
10. `overall_pass`

M3.C closure rule:
1. M3.C can close only when:
   - canonical payload contains all required non-secret fields,
   - digest is computed with pinned algorithm/field name,
   - independent recompute matches exactly,
   - all M3.C evidence artifacts exist locally and in durable run-control prefix,
   - no active `M3C-B*` blockers remain.

M3.C planning status (historical pre-execution):
1. Prerequisite lane `M3.B` is closed green.
2. Digest/canonicalization handles are pinned in registry.
3. No known pre-execution blockers for M3.C at planning time.
4. Phase posture:
   - planning expanded before execution.

M3.C execution status (2026-02-23):
1. Attempt #1 (blocked):
   - execution id: `m3c_20260223T185814Z`
   - result: `overall_pass=false`
   - blocker: `M3C-B4` (digest profile mismatch versus authoritative M3.B seed digest)
   - evidence:
     - `runs/dev_substrate/dev_full/m3/m3c_20260223T185814Z/`
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m3c_20260223T185814Z/`
2. Authoritative PASS run:
   - execution id: `m3c_20260223T185958Z`
   - local evidence root:
     - `runs/dev_substrate/dev_full/m3/m3c_20260223T185958Z/`
   - durable evidence mirror:
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m3c_20260223T185958Z/`
3. PASS artifacts:
   - `m3c_run_config_payload.json`
   - `m3c_run_config_digest_snapshot.json`
   - `m3c_digest_recompute_receipts.json`
   - `m3c_execution_summary.json`
4. Closure results:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M3.C_READY`
   - `config_digest=13f49c0d8e35264a1923844ae19f0e7bdba2b438763b46ae99db6aeeb0b8dc8b`
   - `recompute_digest=13f49c0d8e35264a1923844ae19f0e7bdba2b438763b46ae99db6aeeb0b8dc8b`
   - `matches_m3b_seed_digest=true`
   - digest profile used: `m3b_seed_formula_v1`
5. Blocker remediation outcome:
   - M3.C digest profile was repinned to `m3b_seed_formula_v1` for P1 continuity with M3.B seed contract.

### M3.D Orchestrator Entry + Lock Identity Readiness
Goal:
1. verify P1 orchestrator-entry surface and run-lock posture.

Tasks:
1. verify Step Functions state machine exists and is queryable.
2. verify execution role handle alignment with runtime stack outputs.
3. define run-lock identity mechanism and fail-closed behavior.
4. emit orchestrator-entry readiness snapshot.

DoD:
- [x] orchestrator-entry surface is reachable and evidenced.
- [x] lock identity contract is explicit.
- [x] runtime-role alignment check passes or blocker is explicit.

M3.D decision pins (closed before execution):
1. Orchestrator authority law:
   - `SFN_PLATFORM_RUN_ORCHESTRATOR_V0` is the only accepted P1 orchestrator-entry surface.
   - `SR_READY_COMMIT_AUTHORITY` must remain `step_functions_only`.
2. State-machine identity law:
   - resolved state-machine name from handles must map to a single concrete ARN in the active account/region.
3. Runtime-scope law:
   - `REQUIRED_PLATFORM_RUN_ID_ENV_KEY` (`REQUIRED_PLATFORM_RUN_ID`) is mandatory for runtime scope propagation.
4. Run-lock identity law:
   - lock identity key is `platform_run_id` enforced by orchestrator execution posture.
   - if any concurrent `RUNNING` execution exists for the same `platform_run_id`, M3.D fails closed.
5. Role alignment law:
   - orchestrator runtime identity must align to `ROLE_STEP_FUNCTIONS_ORCHESTRATOR`.
   - role mismatch between handles and live state-machine configuration is a blocker.
6. Evidence safety law:
   - orchestrator-entry evidence may include ARNs, execution ids, and status only; no secret material.

M3.D verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3D-V1-HANDLE-CONTRACT` | `rg -n \"SFN_PLATFORM_RUN_ORCHESTRATOR_V0|SR_READY_COMMIT_AUTHORITY|ROLE_STEP_FUNCTIONS_ORCHESTRATOR|REQUIRED_PLATFORM_RUN_ID_ENV_KEY\" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` | confirms required orchestrator/lock handles are pinned |
| `M3D-V2-SFN-EXISTS` | `aws stepfunctions list-state-machines --region eu-west-2` | verifies state machine exists and is discoverable |
| `M3D-V3-SFN-DESCRIBE` | `aws stepfunctions describe-state-machine --state-machine-arn <resolved_arn> --region eu-west-2` | verifies orchestrator is queryable and returns roleArn |
| `M3D-V4-ROLE-ALIGN` | compare `describe-state-machine.roleArn` with `ROLE_STEP_FUNCTIONS_ORCHESTRATOR` | validates runtime role alignment |
| `M3D-V5-RUN-LOCK-CHECK` | `aws stepfunctions list-executions --state-machine-arn <resolved_arn> --status-filter RUNNING --max-results 100 --region eu-west-2` + filter by `platform_run_id` in execution input/name | detects concurrent run-lock conflicts |
| `M3D-V6-EVIDENCE-PUBLISH` | `aws s3 cp <local_artifact> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m3d_execution_id>/...` | proves durable publication lane |

M3.D blocker taxonomy (fail-closed):
1. `M3D-B1`: required orchestrator/lock handle missing or unresolved.
2. `M3D-B2`: Step Functions state machine not found/unqueryable.
3. `M3D-B3`: orchestrator role mismatch versus `ROLE_STEP_FUNCTIONS_ORCHESTRATOR`.
4. `M3D-B4`: concurrent `RUNNING` execution detected for current `platform_run_id` (lock conflict).
5. `M3D-B5`: runtime-scope env key contract missing (`REQUIRED_PLATFORM_RUN_ID_ENV_KEY`).
6. `M3D-B6`: durable evidence publish failure.
7. `M3D-B7`: M3.D evidence contract missing/incomplete.

M3.D evidence contract (planned):
1. `m3d_orchestrator_entry_readiness_snapshot.json`
2. `m3d_run_lock_posture_snapshot.json`
3. `m3d_command_receipts.json`
4. `m3d_execution_summary.json`

`m3d_orchestrator_entry_readiness_snapshot.json` minimum fields:
1. `platform_run_id`
2. `scenario_run_id`
3. `resolved_state_machine_name`
4. `resolved_state_machine_arn`
5. `sr_ready_commit_authority`
6. `required_platform_run_id_env_key`
7. `configured_role_arn`
8. `expected_role_arn`
9. `role_alignment_pass`
10. `overall_pass`

M3.D closure rule:
1. M3.D can close only when:
   - orchestrator state machine is resolved and queryable,
   - role alignment check passes,
   - run-lock conflict check shows zero concurrent conflicting runs,
   - all M3.D evidence artifacts exist locally and in durable run-control prefix,
   - no active `M3D-B*` blockers remain.

M3.D planning status (current):
1. Prerequisite lanes `M3.B` and `M3.C` are closed green.
2. Orchestrator and lock-related handles are pinned in registry.
3. No known pre-execution blockers for M3.D at planning time.
4. Phase posture:
   - planning expanded before execution.

M3.D execution status (2026-02-23):
1. Attempt #1 (blocked):
   - execution id: `m3d_20260223T191145Z`
   - result: `overall_pass=false`
   - blockers:
     - `M3D-B1` (handle contract false-positive due registry parser drift),
     - `M3D-B3` (cascaded role-alignment failure from empty expected-role parse).
   - evidence:
     - `runs/dev_substrate/dev_full/m3/m3d_20260223T191145Z/`
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m3d_20260223T191145Z/`
2. Authoritative PASS run:
   - execution id: `m3d_20260223T191338Z`
   - local evidence root:
     - `runs/dev_substrate/dev_full/m3/m3d_20260223T191338Z/`
   - durable evidence mirror:
     - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m3d_20260223T191338Z/`
3. PASS artifacts:
   - `m3d_orchestrator_entry_readiness_snapshot.json`
   - `m3d_run_lock_posture_snapshot.json`
   - `m3d_command_receipts.json`
   - `m3d_execution_summary.json`
4. Closure results:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M3.D_READY`
   - state machine resolved:
     - `arn:aws:states:eu-west-2:230372904534:stateMachine:fraud-platform-dev-full-platform-run-v0`
   - role alignment: `PASS`
   - running execution count: `0`
   - conflicting execution count: `0`
5. Blocker remediation outcome:
   - registry parser updated to accept handle lines with trailing materialization notes; runtime posture unchanged.

### M3.E Durable Run Evidence Publication
Goal:
1. publish run pin artifacts to durable evidence root exactly once.

Tasks:
1. write `run.json` to `EVIDENCE_RUN_JSON_KEY`.
2. write run header to `RUN_PIN_PATH_PATTERN`.
3. emit write receipts and integrity checks (head/readback).
4. enforce write-once posture for the same run id.

DoD:
- [x] durable `run.json` write succeeds and readback passes.
- [x] durable run-header write succeeds and readback passes.
- [x] write-once guard behavior is documented.

M3.E decision pins (closed before execution):
1. Source-of-truth law:
   - `platform_run_id` and `scenario_run_id` must be sourced from M3.B PASS artifacts.
   - `config_digest` must be sourced from M3.C PASS artifacts.
   - orchestrator/lock readiness references must be sourced from M3.D PASS artifacts.
   - M3.E must not recompute identity or digest.
2. Object key law:
   - `run.json` target key is `EVIDENCE_RUN_JSON_KEY` resolved with current `platform_run_id`.
   - run header target key is `RUN_PIN_PATH_PATTERN` resolved with current `platform_run_id`.
3. Write-once law:
   - pre-write `head-object` must confirm target keys do not already exist.
   - if either key exists, M3.E fails closed (no overwrite path for P1 run pin).
4. Integrity law:
   - local payload SHA256 is computed before upload,
   - uploaded object readback hash must equal local hash for both artifacts.
5. Consistency law:
   - `run.json` and run header must carry identical `platform_run_id`, `scenario_run_id`, and `config_digest`.
6. Evidence safety law:
   - no secrets/tokens/credentials in either artifact.

M3.E verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3E-V1-INPUTS` | `Test-Path runs/dev_substrate/dev_full/m3/<m3b_id>/... && Test-Path runs/dev_substrate/dev_full/m3/<m3c_id>/... && Test-Path runs/dev_substrate/dev_full/m3/<m3d_id>/...` | confirms prerequisite evidence surfaces exist |
| `M3E-V2-KEY-RESOLVE` | resolve `EVIDENCE_RUN_JSON_KEY` and `RUN_PIN_PATH_PATTERN` with current `platform_run_id` | proves deterministic target keys |
| `M3E-V3-WRITE-ONCE-GUARD` | `aws s3api head-object --bucket <S3_EVIDENCE_BUCKET> --key <resolved_key>` | fails closed if key already exists |
| `M3E-V4-UPLOAD` | `aws s3 cp <local_artifact> s3://<S3_EVIDENCE_BUCKET>/<resolved_key>` | publishes durable objects |
| `M3E-V5-READBACK` | `aws s3 cp s3://<...>/<resolved_key> -` + local hash compare | verifies readback integrity |
| `M3E-V6-CONSISTENCY` | compare identity/digest fields across both artifacts | enforces cross-object consistency |

M3.E blocker taxonomy (fail-closed):
1. `M3E-B1`: prerequisite M3.B/M3.C/M3.D PASS artifacts missing.
2. `M3E-B2`: target key resolution failure for run evidence objects.
3. `M3E-B3`: write-once guard violation (existing key detected).
4. `M3E-B4`: durable write/upload failure.
5. `M3E-B5`: readback integrity/hash mismatch.
6. `M3E-B6`: cross-artifact identity/digest inconsistency.
7. `M3E-B7`: secret material detected in run evidence payload.
8. `M3E-B8`: M3.E evidence contract missing/incomplete.

M3.E evidence contract (planned):
1. `m3e_run_json_write_receipt.json`
2. `m3e_run_header_write_receipt.json`
3. `m3e_integrity_readback_receipts.json`
4. `m3e_execution_summary.json`

`m3e_run_json_write_receipt.json` minimum fields:
1. `platform_run_id`
2. `scenario_run_id`
3. `config_digest`
4. `resolved_run_json_key`
5. `local_sha256`
6. `s3_etag`
7. `readback_sha256`
8. `write_once_guard_pass`
9. `overall_pass`

M3.E closure rule:
1. M3.E can close only when:
   - both run evidence objects are published to resolved keys,
   - write-once guard is explicitly evidenced as pass,
   - readback hash checks pass for both objects,
   - identity/digest consistency across objects is true,
   - all M3.E evidence artifacts exist locally and in durable run-control prefix,
   - no active `M3E-B*` blockers remain.

M3.E planning status (current):
1. Prerequisite lanes `M3.B`, `M3.C`, and `M3.D` are closed green.
2. Run evidence key handles are pinned in registry.
3. No known pre-execution blockers for M3.E at planning time.
4. Phase posture:
   - planning expanded before execution.

M3.E execution status (2026-02-23):
1. Authoritative execution id:
   - `m3e_20260223T223411Z`
2. Local evidence root:
   - `runs/dev_substrate/dev_full/m3/m3e_20260223T223411Z/`
3. Durable run-control evidence mirror:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m3e_20260223T223411Z/`
4. Published run evidence objects:
   - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/run.json`
   - `s3://fraud-platform-dev-full-evidence/evidence/runs/platform_20260223T184232Z/run_pin/run_header.json`
5. PASS artifacts:
   - `m3e_run_json_write_receipt.json`
   - `m3e_run_header_write_receipt.json`
   - `m3e_integrity_readback_receipts.json`
   - `m3e_execution_summary.json`
6. Closure results:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M3.E_READY`
   - write-once guard: `PASS` (both target keys absent pre-write via head-object 404)
   - readback integrity: `PASS` for both objects
   - cross-artifact consistency: `PASS`

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
- [x] handoff pack contains all required run-scope fields.
- [x] handoff references are durable and readable.
- [x] M4 runtime-scope env mapping is explicit.

M3.F decision pins (closed before execution):
1. Source-of-truth law:
   - `platform_run_id` and `scenario_run_id` come from M3.B PASS artifacts.
   - `config_digest` comes from M3.C PASS artifacts.
   - run evidence object references come from M3.E committed objects.
   - orchestrator entry references come from M3.D PASS artifacts.
   - M3.F must not recompute identity or digest.
2. Runtime-scope binding law:
   - `required_platform_run_id_env_key` must equal registry-pinned `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`.
   - `required_platform_run_id_env_value` must equal current `platform_run_id`.
3. Correlation contract law:
   - handoff pack must include required correlation fields list from runbook cross-runtime rule:
     - `platform_run_id,scenario_run_id,phase_id,event_id,runtime_lane,trace_id`.
4. Durable reference law:
   - handoff pack must reference durable and readable M3 evidence surfaces:
     - `evidence/runs/{platform_run_id}/run.json`,
     - `evidence/runs/{platform_run_id}/run_pin/run_header.json`,
     - M3.D orchestrator-entry readiness evidence object.
5. Immutability law:
   - once `m4_handoff_pack.json` is emitted for current M3 chain, in-place mutation is prohibited; changes require new M3.F execution id.
6. Evidence safety law:
   - handoff pack contains no secrets/tokens/credentials.

M3.F verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3F-V1-INPUTS` | `Test-Path` checks for authoritative M3.B/M3.C/M3.D/M3.E artifacts | confirms prerequisite sources exist |
| `M3F-V2-ENV-BINDING` | compare handoff `required_platform_run_id_env_key/value` with registry + current run id | verifies runtime-scope binding |
| `M3F-V3-CORRELATION-CONTRACT` | verify handoff correlation list equals runbook pinned list | enforces correlation continuity anchor |
| `M3F-V4-REF-READABLE` | `aws s3api head-object --bucket <S3_EVIDENCE_BUCKET> --key <referenced_key>` | proves referenced durable artifacts exist |
| `M3F-V5-HANDOFF-PUBLISH` | `aws s3 cp <local_handoff_pack> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m3f_execution_id>/m4_handoff_pack.json` | publishes durable handoff pack |
| `M3F-V6-HANDOFF-READBACK` | `aws s3 cp s3://<...>/m4_handoff_pack.json -` + local hash compare | proves durable handoff readback integrity |

M3.F blocker taxonomy (fail-closed):
1. `M3F-B1`: prerequisite source artifacts missing or not PASS.
2. `M3F-B2`: runtime-scope env key/value binding mismatch.
3. `M3F-B3`: correlation required fields list mismatch/incomplete.
4. `M3F-B4`: referenced durable M3 artifacts unreadable/missing.
5. `M3F-B5`: durable handoff publish failure.
6. `M3F-B6`: handoff readback integrity mismatch.
7. `M3F-B7`: secret material detected in handoff pack.
8. `M3F-B8`: M3.F evidence contract missing/incomplete.

M3.F evidence contract (planned):
1. `m4_handoff_pack.json`
2. `m3f_runtime_scope_binding_snapshot.json`
3. `m3f_handoff_reference_receipts.json`
4. `m3f_execution_summary.json`

`m4_handoff_pack.json` minimum fields:
1. `platform_run_id`
2. `scenario_run_id`
3. `config_digest`
4. `required_platform_run_id_env_key`
5. `required_platform_run_id_env_value`
6. `correlation_required_fields`
7. `durable_references`
8. `source_execution_ids`
9. `overall_pass`

M3.F closure rule:
1. M3.F can close only when:
   - handoff pack contains all required run-scope and correlation fields,
   - runtime-scope env mapping is explicit and correct,
   - all referenced M3 durable artifacts are readable,
   - handoff pack exists locally and durably with readback hash match,
   - no active `M3F-B*` blockers remain.

M3.F planning status (current):
1. Prerequisite lanes `M3.B`, `M3.C`, `M3.D`, and `M3.E` are closed green.
2. Runtime-scope and evidence handles are pinned in registry.
3. No known pre-execution blockers for M3.F at planning time.
4. Phase posture:
   - planning expanded before execution.

M3.F execution status (2026-02-23):
1. Authoritative execution id:
   - `m3f_20260223T224855Z`
2. Local evidence root:
   - `runs/dev_substrate/dev_full/m3/m3f_20260223T224855Z/`
3. Durable evidence mirror:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m3f_20260223T224855Z/`
4. PASS artifacts:
   - `m4_handoff_pack.json`
   - `m3f_runtime_scope_binding_snapshot.json`
   - `m3f_handoff_reference_receipts.json`
   - `m3f_execution_summary.json`
5. Closure results:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M3.F_READY`
   - env binding: `REQUIRED_PLATFORM_RUN_ID -> platform_20260223T184232Z` (`PASS`)
   - correlation contract fields: `platform_run_id,scenario_run_id,phase_id,event_id,runtime_lane,trace_id` (`PASS`)
   - durable reference readability: `3/3` refs readable (`PASS`)
   - handoff readback hash match: `PASS`

### M3.G Rerun and Reset Discipline
Goal:
1. codify fail-closed rerun behavior for P1 identity changes.

Tasks:
1. pin rerun rules for digest drift and identity drift.
2. require new `platform_run_id` on identity/config change.
3. prohibit destructive mutation of existing run evidence.
4. emit rerun/reset policy snapshot for M3.

DoD:
- [x] rerun/reset rules are explicit and auditable.
- [x] destructive rerun paths are prohibited.
- [x] identity drift behavior is fail-closed.

M3.G decision pins (closed before execution):
1. Non-destructive law:
   - append-only truth surfaces must not be deleted or rewritten for rerun.
   - prohibited: deleting `evidence/runs/{platform_run_id}/...` objects to force rerun.
2. Boundary-rerun law:
   - rerun starts from failed phase boundary only, not from ad-hoc phase skipping.
   - rerun requires explicit prior-phase closure evidence references.
3. Identity drift law:
   - if `platform_run_id`, `scenario_run_id`, or `config_digest` changes, a new run identity is mandatory.
   - old run evidence remains immutable.
4. Reset class law (runbook aligned):
   - permitted reset classes are:
     - service/runtime reset,
     - checkpoint reset (only where policy exists),
     - data replay reset from committed replay basis.
   - local ad-hoc input replay is prohibited.
5. Fail-closed approval law:
   - any fallback/reset outside pinned classes requires blocker adjudication and explicit approval with a new `phase_execution_id`.
6. Auditability law:
   - each reset action must emit receipt with actor, timestamp, reason, class, and scope.

M3.G verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3G-V1-RUNBOOK-RULES` | `rg -n \"Never rerun by deleting append-only truth surfaces|Rerun from failed phase boundary|Mandatory reset classes\" docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` | anchors M3.G to runbook reset laws |
| `M3G-V2-IDENTITY-DRIFT` | compare current `platform_run_id/scenario_run_id/config_digest` vs previous run metadata | enforces new-run requirement on drift |
| `M3G-V3-PROHIBITED-MUTATION-GUARD` | check no delete/mutate commands or receipts target committed run evidence keys | proves non-destructive posture |
| `M3G-V4-RESET-CLASS-MAP` | validate all reset actions map to allowed classes | blocks ad-hoc reset behavior |
| `M3G-V5-RESET-RECEIPTS` | verify reset receipts include actor/timestamp/reason/class/scope | enforces auditability |
| `M3G-V6-DURABLE-PUBLISH` | `aws s3 cp <local_artifact> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m3g_execution_id>/...` | publishes durable M3.G evidence |

M3.G blocker taxonomy (fail-closed):
1. `M3G-B1`: rerun/reset policy missing or internally inconsistent.
2. `M3G-B2`: identity drift detected without new-run posture.
3. `M3G-B3`: destructive mutation/delete action detected on committed evidence.
4. `M3G-B4`: reset action outside permitted reset classes.
5. `M3G-B5`: missing/invalid reset audit receipts.
6. `M3G-B6`: fallback/reset without explicit blocker adjudication + phase execution id.
7. `M3G-B7`: durable publication failure for M3.G policy evidence.
8. `M3G-B8`: M3.G evidence contract missing/incomplete.

M3.G evidence contract (planned):
1. `m3g_rerun_reset_policy_snapshot.json`
2. `m3g_reset_class_matrix.json`
3. `m3g_prohibited_mutation_guard_receipts.json`
4. `m3g_execution_summary.json`

`m3g_rerun_reset_policy_snapshot.json` minimum fields:
1. `platform_run_id`
2. `scenario_run_id`
3. `config_digest`
4. `identity_drift_policy`
5. `permitted_reset_classes`
6. `prohibited_actions`
7. `fallback_approval_rule`
8. `overall_pass`

M3.G closure rule:
1. M3.G can close only when:
   - rerun/reset policy is explicit, runbook-aligned, and auditable,
   - prohibited destructive paths are explicitly blocked,
   - identity drift handling is fail-closed,
   - reset-class mapping and receipts are complete,
   - all M3.G evidence artifacts exist locally and in durable run-control prefix,
   - no active `M3G-B*` blockers remain.

M3.G planning status (current):
1. Prerequisite lanes `M3.B`..`M3.F` are closed green.
2. Runbook reset laws and fail-closed posture are available and pinned.
3. No known pre-execution blockers for M3.G at planning time.
4. Phase posture:
   - planning expanded; execution closed green.

M3.G execution status (2026-02-23):
1. Authoritative execution id:
   - `m3g_20260223T225607Z`
2. Local evidence root:
   - `runs/dev_substrate/dev_full/m3/m3g_20260223T225607Z/`
3. Durable evidence mirror:
   - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m3g_20260223T225607Z/`
4. PASS artifacts:
   - `m3g_rerun_reset_policy_snapshot.json`
   - `m3g_reset_class_matrix.json`
   - `m3g_prohibited_mutation_guard_receipts.json`
   - `m3g_execution_summary.json`
5. Closure results:
   - `overall_pass=true`
   - `blocker_count=0`
   - `next_gate=M3.G_READY`
   - runbook reset-law anchors found (`PASS`)
   - identity drift check (`PASS`: drift not detected for active run triplet)
   - prohibited mutation guard (`PASS`: no delete markers, no multi-version rewrite on committed run evidence keys)
   - reset-class and receipt integrity (`PASS`)

### M3.H Cost Envelope and Outcome Receipt
Goal:
1. satisfy phase budget law for M3 before advancement.

Tasks:
1. emit M3 phase budget envelope.
2. record M3 spend window and expected proof artifacts.
3. emit M3 cost-to-outcome receipt.
4. prove spend-without-proof hard-stop posture for M3 gate advancement.

DoD:
- [ ] phase budget envelope is committed.
- [ ] cost-to-outcome receipt is committed.
- [ ] spend-without-proof is fail-closed.

M3.H planning precheck (decision completeness):
1. Required handles are pinned for this lane:
   - `DEV_FULL_MONTHLY_BUDGET_LIMIT_USD`, `DEV_FULL_BUDGET_ALERT_1_USD`, `DEV_FULL_BUDGET_ALERT_2_USD`, `DEV_FULL_BUDGET_ALERT_3_USD`, `BUDGET_CURRENCY`.
   - `COST_CAPTURE_SCOPE`, `AWS_COST_CAPTURE_ENABLED`, `DATABRICKS_COST_CAPTURE_ENABLED`.
   - `PHASE_BUDGET_ENVELOPE_PATH_PATTERN`, `PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN`, `DAILY_COST_POSTURE_PATH_PATTERN`.
   - `PHASE_COST_OUTCOME_REQUIRED`, `PHASE_ENVELOPE_REQUIRED`, `PHASE_COST_HARD_STOP_ON_MISSING_OUTCOME`.
   - `COST_OUTCOME_RECEIPT_REQUIRED_FIELDS`.
2. Upstream closure dependency:
   - M3.A..M3.G authoritative summaries must remain `overall_pass=true`.
3. Required source posture:
   - AWS billing source must be queryable in billing region (`us-east-1`) for the active M3 window.
   - Databricks billing source must be explicitly pinned when `DATABRICKS_COST_CAPTURE_ENABLED=true`.

M3.H decision pins (closed before execution):
1. Envelope-first law:
   - M3.H must emit budget envelope before outcome receipt adjudication.
2. Spend-without-proof law:
   - if spend exists and outcome receipt is missing/invalid, phase fails closed (`M3H-B9`).
3. Cross-source law:
   - M3.H cost posture must include all enabled sources in `COST_CAPTURE_SCOPE`.
   - source omission without explicit approved waiver is blocker.
4. Currency normalization law:
   - all source spends are normalized to `BUDGET_CURRENCY` before threshold checks.
5. Required-fields law:
   - receipt fields must satisfy `COST_OUTCOME_RECEIPT_REQUIRED_FIELDS` exactly.
6. Window-bound law:
   - M3 spend window in receipt is explicit (`window_start_utc`, `window_end_utc`) and tied to M3 execution interval.

M3.H verification command catalog (planned, execution-time):
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3H-V1-HANDLE-CLOSURE` | `rg -n \"DEV_FULL_MONTHLY_BUDGET_LIMIT_USD|PHASE_BUDGET_ENVELOPE_PATH_PATTERN|PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN|DATABRICKS_COST_CAPTURE_ENABLED\" docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` | confirms required handle presence |
| `M3H-V2-UPSTREAM-PASS` | parse M3.A..M3.G `m3*_execution_summary.json` and assert `overall_pass=true` | ensures budget lane anchors only on committed green chain |
| `M3H-V3-AWS-COST-SOURCE` | `aws ce get-cost-and-usage --region us-east-1 --time-period Start=<month_start>,End=<tomorrow> --granularity MONTHLY --metrics UnblendedCost` | captures AWS MTD source spend |
| `M3H-V4-DBX-COST-SOURCE` | load pinned Databricks billing source artifact for same window (`M3H_DATABRICKS_COST_SOURCE_URI`) | captures Databricks MTD source spend when enabled |
| `M3H-V5-ENVELOPE-BUILD` | build `m3h_phase_budget_envelope.json` from pinned limits/alerts/currency | emits authoritative phase budget envelope |
| `M3H-V6-OUTCOME-BUILD` | build `m3h_phase_cost_outcome_receipt.json` with required fields and artifact refs | emits cost-to-outcome proof |
| `M3H-V7-DURABLE-PUBLISH` | `aws s3 cp <local_artifact> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_full/run_control/<m3h_execution_id>/...` | publishes durable M3.H evidence |

M3.H blocker taxonomy (fail-closed):
1. `M3H-B1`: one or more budget/cost handles missing or malformed.
2. `M3H-B2`: upstream M3.A..M3.G closure evidence missing/non-green.
3. `M3H-B3`: AWS billing source query fails or returns unusable payload.
4. `M3H-B4`: Databricks cost capture is enabled but no pinned/queryable Databricks billing source exists.
5. `M3H-B5`: phase budget envelope missing required fields or invalid thresholds.
6. `M3H-B6`: cost-outcome receipt missing required fields or invalid artifact references.
7. `M3H-B7`: spend currency normalization fails against `BUDGET_CURRENCY`.
8. `M3H-B8`: durable publish/readback for M3.H artifacts fails.
9. `M3H-B9`: spend observed without accepted cost-outcome receipt (`PHASE_COST_HARD_STOP_ON_MISSING_OUTCOME=true`).

M3.H evidence contract (planned):
1. `m3h_phase_budget_envelope.json`
2. `m3h_phase_cost_outcome_receipt.json`
3. `m3h_daily_cost_posture.json`
4. `m3h_cost_source_receipts.json`
5. `m3h_execution_summary.json`

M3.H closure rule:
1. M3.H can close only when:
   - all `M3H-B*` blockers are resolved,
   - DoD checks are green,
   - envelope + outcome artifacts are present locally and durably,
   - spend-without-proof policy check passes.

M3.H planning status (current):
1. Prerequisite lanes `M3.A`..`M3.G` are closed green.
2. M3.H is expanded to execution-grade with explicit fail-closed blockers and evidence contract.
3. Pre-execution open blocker to close before runtime execution:
   - `M3H-B4` remains possible until a concrete Databricks billing source URI/handle is pinned for the active window while `DATABRICKS_COST_CAPTURE_ENABLED=true`.
4. Phase posture:
   - planning expanded; execution not started.

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
- [x] M3.B complete.
- [x] M3.C complete.
- [x] M3.D complete.
- [x] M3.E complete.
- [x] M3.F complete.
- [x] M3.G complete.
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
