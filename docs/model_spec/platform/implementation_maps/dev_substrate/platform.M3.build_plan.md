# Dev Substrate Deep Plan - M3 (P1 Run Pinning)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M3._
_Last updated: 2026-02-13_

## 0) Purpose
M3 establishes the run identity and provenance anchor for a dev_min execution.
This phase creates and persists the canonical run manifest (`run.json`), pins config digest and image provenance, and emits a deterministic handoff surface for M4 daemon bring-up.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (P1 section)
3. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M2.build_plan.md`
2. `runs/dev_substrate/m2_j/20260213T205715Z/m3_handoff_pack.json`
3. `docs/model_spec/platform/contracts/dev_min/run_header.v0.schema.yaml`
4. `docs/model_spec/platform/contracts/dev_min/README.md`
5. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`

## 2) Scope Boundary for M3
In scope:
1. Run identity generation (`platform_run_id`) with collision protection.
2. P1 run config payload assembly from pinned handles and M2 handoff surfaces.
3. Deterministic config digest computation and manifest integrity checks.
4. Durable publication of run evidence roots and run header artifacts.
5. Runtime scope export contract for M4 (`REQUIRED_PLATFORM_RUN_ID`).
6. M3 blocker model, fail-closed verdict, and M4 handoff artifact.

Out of scope:
1. Daemon/service startup (`M4`).
2. Oracle lane execution (`M5`) and downstream phase execution.
3. Any mutation of substrate resources created/validated by M2.

## 3) M3 Deliverables
1. M3 handle closure matrix with explicit owner/source/verification for P1.
2. Canonical run manifest contract (`run.json`) with digest and provenance fields.
3. Deterministic M3 execution command lane and evidence publication lane.
4. Runtime scope handoff contract for M4 consumers.
5. M3 closeout package:
   - `m3_run_pinning_snapshot.json`
   - `m4_handoff_pack.json`
6. Explicit unresolved-blocker register for M3.

## 4) Execution Gate for This Phase
Current posture:
1. M3 is active for deep planning and closure-hardening.

Execution block:
1. No M4 daemon bring-up is allowed before M3 verdict is `ADVANCE_TO_M4`.
2. No run-scoped phase execution (P2+) is allowed unless `run.json` is durably written.
3. No default value injection is allowed for unresolved run-identity decisions.

## 4.1) Anti-Cram Law (Binding for M3)
1. M3 is not execution-ready unless these lanes are explicit:
   - authority/handles
   - run identity
   - digest/provenance
   - evidence publication
   - runtime-scope export
   - rollback/rerun
2. Sub-phase count is not fixed. Expand if new mandatory lanes appear.
3. Any newly discovered hole pauses progression and must be added to this plan first.

## 4.2) Capability-Lane Coverage Matrix (Must Stay Explicit)
| Capability lane | Primary sub-phase owner | Supporting sub-phases | Minimum PASS evidence |
| --- | --- | --- | --- |
| Run identity generation | M3.B | M3.F | non-colliding `platform_run_id` captured in run artifacts |
| Config payload + digest | M3.C | M3.F | digest reproducibility check passes |
| Image provenance binding | M3.C | M3.D | immutable image tag/digest present in `run.json` |
| Durable run evidence write | M3.D | M3.G | `run.json` exists under `evidence/runs/<platform_run_id>/` |
| Runtime scope export for M4 | M3.E | M3.G | handoff pack includes `REQUIRED_PLATFORM_RUN_ID` map |
| Blocker and verdict discipline | M3.F | M3.G | explicit `ADVANCE_TO_M4` or `HOLD_M3` with reasons |

## 5) Work Breakdown (Deep)

## M3 Decision Pins (Closed Before Execution)
1. Run identity law:
   - `platform_run_id` is created once per run and never reused with a different config digest.
2. Digest law:
   - `CONFIG_DIGEST_ALGO` and `CONFIG_DIGEST_FIELD` from handles registry are mandatory.
3. Evidence-first law:
   - `run.json` must exist durably in S3 before M4 start.
4. Scope law:
   - M4 consumers must receive `REQUIRED_PLATFORM_RUN_ID` equal to the M3 run id.
5. Scenario equivalence law:
   - `SCENARIO_EQUIVALENCE_KEY_INPUT` must be explicitly pinned at M3 execution entry (fail-closed if placeholder).

### M3.A Authority + Handle Closure Matrix
Goal:
1. Close all required P1 handles before command execution.

Tasks:
1. Resolve and verify required handle keys:
   - run fields:
     - `FIELD_PLATFORM_RUN_ID`
     - `FIELD_SCENARIO_RUN_ID`
     - `FIELD_WRITTEN_AT_UTC`
   - digest controls:
     - `CONFIG_DIGEST_ALGO`
     - `CONFIG_DIGEST_FIELD`
     - `SCENARIO_EQUIVALENCE_KEY_INPUT`
     - `SCENARIO_RUN_ID_DERIVATION_MODE`
   - evidence locations:
     - `S3_EVIDENCE_BUCKET`
     - `S3_EVIDENCE_RUN_ROOT_PATTERN`
     - `EVIDENCE_RUN_JSON_KEY`
   - provenance:
     - `ECR_REPO_URI`
     - `IMAGE_TAG_GIT_SHA_PATTERN`
     - `IMAGE_TAG_EVIDENCE_FIELD`
     - `IMAGE_DIGEST_EVIDENCE_FIELD`
     - `IMAGE_GIT_SHA_EVIDENCE_FIELD`
   - runtime scope:
     - `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`
2. Verify M2 handoff artifact availability:
   - `runs/dev_substrate/m2_j/20260213T205715Z/m3_handoff_pack.json`.
3. Mark unresolved handles as blockers.

DoD:
- [ ] Required M3 handle set is explicit and complete.
- [ ] Every required handle has a verification method.
- [ ] Unresolved handles are either zero or explicitly blocker-marked.

### M3.A Decision Pins (Closed Before Execution)
1. Handle-source law:
   - every required P1 handle must be mapped to one authoritative source class:
     - registry literal,
     - M2 handoff artifact,
     - AWS control-plane lookup,
     - M1 packaging evidence artifact.
2. Provenance-source law:
   - image provenance fields in `run.json` must come from immutable P(-1) evidence (`git-<sha>` + digest), not mutable tags.
3. Placeholder law:
   - if any required handle value remains placeholder at execution entry, `M3.A` is blocked.
4. Non-secret law:
   - M3.A closure artifacts may include handle names and non-secret resolved values only.

### M3.A Verification Command Catalog (Pinned)
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3A_V1_HANDLE_KEY` | `rg -n "\\b<HANDLE_KEY>\\b" docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md` | confirms handle exists in authoritative registry |
| `M3A_V2_M2_HANDOFF` | `Test-Path runs/dev_substrate/m2_j/20260213T205715Z/m3_handoff_pack.json` | confirms M2->M3 handoff artifact availability |
| `M3A_V3_ECR_URI` | `aws ecr describe-repositories --repository-names <ECR_REPO_NAME> --region <AWS_REGION>` | resolves/validates `ECR_REPO_URI` from control plane |
| `M3A_V4_P1_EVIDENCE_ROOT` | `aws s3api head-bucket --bucket <S3_EVIDENCE_BUCKET>` | validates run evidence bucket reachability |
| `M3A_V5_M1_PROVENANCE` | `aws s3 ls s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<m1_platform_run_id>/P(-1)/` | validates immutable packaging evidence source for image provenance |
| `M3A_V6_PLACEHOLDER_GUARD` | `rg -n \"SCENARIO_EQUIVALENCE_KEY_INPUT\\s*=\\s*\\\"<PIN_AT_P1_PHASE_ENTRY>\\\"\" docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md` | fail-closed check for unresolved scenario-equivalence key |

### M3.A Handle Closure Matrix (Planning Snapshot)
| Handle key / prerequisite | Source class | Resolution source | Verification | Secret class | Status | Blocker |
| --- | --- | --- | --- | --- | --- | --- |
| `FIELD_PLATFORM_RUN_ID` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `FIELD_SCENARIO_RUN_ID` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `FIELD_WRITTEN_AT_UTC` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `CONFIG_DIGEST_ALGO` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `CONFIG_DIGEST_FIELD` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `SCENARIO_EQUIVALENCE_KEY_INPUT` | registry placeholder | handles registry (phase-entry pin pending) | `M3A_V6_PLACEHOLDER_GUARD` | `non_secret` | `BLOCKED` | `M3A-B1` |
| `SCENARIO_RUN_ID_DERIVATION_MODE` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `S3_EVIDENCE_BUCKET` | M2 handoff output | `m3_handoff_pack.json` -> `core_outputs.s3_bucket_names.evidence` | `M3A_V2_M2_HANDOFF` + `M3A_V4_P1_EVIDENCE_ROOT` | `non_secret` | `CLOSED_SPEC` | `none` |
| `S3_EVIDENCE_RUN_ROOT_PATTERN` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `EVIDENCE_RUN_JSON_KEY` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `ECR_REPO_URI` | AWS control-plane lookup | ECR repo describe result (`fraud-platform-dev-min`) | `M3A_V3_ECR_URI` | `non_secret` | `CLOSED_SPEC` | `none` |
| `IMAGE_TAG_GIT_SHA_PATTERN` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `IMAGE_TAG_EVIDENCE_FIELD` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `IMAGE_DIGEST_EVIDENCE_FIELD` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `IMAGE_GIT_SHA_EVIDENCE_FIELD` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| `REQUIRED_PLATFORM_RUN_ID_ENV_KEY` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_SPEC` | `none` |
| M2->M3 handoff artifact | M2 durable artifact | `runs/dev_substrate/m2_j/20260213T205715Z/m3_handoff_pack.json` | `M3A_V2_M2_HANDOFF` | `non_secret` | `CLOSED_SPEC` | `none` |
| Immutable image provenance source | M1 durable artifact | `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T114002Z/P(-1)/` | `M3A_V5_M1_PROVENANCE` | `non_secret` | `CLOSED_SPEC` | `none` |

### M3.A Planning Status (Current)
1. Required-handle coverage:
   - 18 required rows tracked in closure matrix.
2. Current blockers:
   - `M3A-B1`: `SCENARIO_EQUIVALENCE_KEY_INPUT` remains placeholder (`<PIN_AT_P1_PHASE_ENTRY>`).
3. M3.A execution posture:
   - planning is in progress,
   - runtime execution for M3 remains blocked until `M3A-B1` is closed.

### M3.B Run Identity Generation Contract
Goal:
1. Generate collision-safe run identity and record run header skeleton.

Tasks:
1. Define canonical `platform_run_id` format for this track.
2. Validate non-collision:
   - if `evidence/runs/<platform_run_id>/` already exists, fail and regenerate.
3. Record run header skeleton:
   - `platform_run_id`
   - `written_at_utc`
   - `phase_id=P1`.
4. Enforce fail-closed rule on unresolved scenario input:
   - if `SCENARIO_EQUIVALENCE_KEY_INPUT` remains placeholder, open blocker and stop.

DoD:
- [ ] `platform_run_id` format is pinned and deterministic.
- [ ] Collision check is executed and evidenced.
- [ ] Placeholder scenario-equivalence input cannot silently pass.

### M3.C Config Payload + Digest Contract
Goal:
1. Produce deterministic run payload and digest.

Tasks:
1. Assemble run config payload from:
   - M2 handoff substrate handles,
   - registry literals,
   - image provenance fields from M1,
   - runtime scope contract key.
2. Canonicalize payload serialization (deterministic field ordering).
3. Compute digest using `CONFIG_DIGEST_ALGO`.
4. Verify digest reproducibility by recomputing and comparing value.
5. Ensure no secret values are embedded in payload evidence.

DoD:
- [ ] Payload covers required P1 identity/provenance fields.
- [ ] Digest is reproducible and stored under `CONFIG_DIGEST_FIELD`.
- [ ] Payload evidence is non-secret.

### M3.D Durable Run Evidence Publication
Goal:
1. Persist the run anchor to S3 and verify durability.

Tasks:
1. Write local artifacts:
   - `runs/dev_substrate/m3/<timestamp>/run.json`
   - `runs/dev_substrate/m3/<timestamp>/run_started.json`
2. Upload durable artifacts:
   - `evidence/runs/<platform_run_id>/run.json`
   - `evidence/runs/<platform_run_id>/run_started.json`
3. Verify object existence via S3 head/list checks.
4. Record write receipts and object URIs for M3 evidence.

DoD:
- [ ] `run.json` and `run_started.json` exist locally and durably.
- [ ] Durable object verification succeeds.
- [ ] `run.json` references the correct `platform_run_id`.

### M3.E Runtime Scope Export Contract for M4
Goal:
1. Export deterministic run-scope surface for daemon start lanes.

Tasks:
1. Build M4 runtime scope bundle with:
   - `platform_run_id`
   - `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`
   - run evidence root URI
   - M3 manifest URI references.
2. Ensure bundle is non-secret.
3. Publish local and durable handoff helper artifact:
   - `m4_runtime_scope_bundle.json`.

DoD:
- [ ] Runtime scope bundle is complete and non-secret.
- [ ] M4 consumers can read a single authoritative scope surface.
- [ ] Missing run-scope keys are fail-closed.

### M3.F Pass Gates, Blockers, and Verdict
Goal:
1. Apply deterministic pass criteria and blocker model.

Tasks:
1. Evaluate predicates:
   - `handles_closed`
   - `run_id_collision_free`
   - `digest_reproducible`
   - `run_json_durable`
   - `runtime_scope_export_ready`
2. Compute verdict:
   - all true => `ADVANCE_TO_M4`
   - otherwise => `HOLD_M3`.
3. Blocker taxonomy:
   - `M3-B1`: unresolved/placeholder scenario equivalence key input.
   - `M3-B2`: run-id collision or invalid run-id format.
   - `M3-B3`: digest mismatch/non-reproducible payload.
   - `M3-B4`: run evidence publication failure/incomplete run.json.
   - `M3-B5`: runtime scope export incomplete for M4.
   - `M3-B6`: secret leakage detected in M3 artifacts.

DoD:
- [ ] Verdict predicates are explicit and reproducible.
- [ ] Blocker taxonomy is fail-closed and actionable.
- [ ] Verdict is persisted in M3 closeout artifacts.

### M3.G M4 Handoff Artifact Publication
Goal:
1. Publish canonical M3 closeout package used to activate M4.

Tasks:
1. Emit local artifacts:
   - `runs/dev_substrate/m3/<timestamp>/m3_run_pinning_snapshot.json`
   - `runs/dev_substrate/m3/<timestamp>/m4_handoff_pack.json`
2. Upload durable artifacts:
   - `evidence/dev_min/run_control/<m3_execution_id>/m3_run_pinning_snapshot.json`
   - `evidence/dev_min/run_control/<m3_execution_id>/m4_handoff_pack.json`
3. Record artifact URIs in execution notes.

DoD:
- [ ] Handoff artifacts exist locally and durably.
- [ ] `m4_handoff_pack.json` is structurally complete and non-secret.
- [ ] Artifact URI list is captured for M4 entry.

## 6) M3 Evidence Contract (Pinned for Execution)
Evidence roots:
1. Run-scoped evidence root:
   - `evidence/runs/<platform_run_id>/`
2. M3 control-plane evidence root:
   - `evidence/dev_min/run_control/<m3_execution_id>/`
3. `<m3_execution_id>` format:
   - `m3_<YYYYMMDDThhmmssZ>`

Minimum evidence payloads:
1. `evidence/runs/<platform_run_id>/run.json`
2. `evidence/runs/<platform_run_id>/run_started.json`
3. `evidence/dev_min/run_control/<m3_execution_id>/m3_run_pinning_snapshot.json`
4. `evidence/dev_min/run_control/<m3_execution_id>/m4_handoff_pack.json`
5. local mirrors under:
   - `runs/dev_substrate/m3/<timestamp>/...`

Notes:
1. Evidence must be non-secret.
2. Any secret-bearing payload detected in run artifacts is a hard blocker.
3. Scenario-equivalence input may be represented by stable hash/reference rather than raw secret value.

## 7) M3 Completion Checklist
- [ ] M3.A complete
- [ ] M3.B complete
- [ ] M3.C complete
- [ ] M3.D complete
- [ ] M3.E complete
- [ ] M3.F complete
- [ ] M3.G complete

## 8) Risks and Controls
R1: Reused or colliding run id can contaminate run scope.  
Control: mandatory collision check + fail-closed regeneration.

R2: Manifest drift after daemon start.  
Control: `run.json` durable write before any M4 start attempt.

R3: Undetected config/provenance drift.  
Control: deterministic digest and reproducibility check.

R4: Hidden secret leakage in run artifacts.  
Control: non-secret artifact policy + explicit blocker `M3-B6`.

## 8.1) Unresolved Blocker Register (Must Be Empty Before M3 Execution)
Current blockers:
1. `M3A-B1` (open)
   - impacted sub-phase:
     - `M3.A`
   - summary:
     - `SCENARIO_EQUIVALENCE_KEY_INPUT` is still placeholder (`<PIN_AT_P1_PHASE_ENTRY>`) in handles registry.
   - runtime impact:
     - scenario-equivalence provenance cannot be pinned deterministically at P1, so run pinning cannot proceed fail-closed.
   - closure criteria:
     - pin explicit value/reference for `SCENARIO_EQUIVALENCE_KEY_INPUT` at M3 entry,
     - rerun M3.A handle closure and confirm placeholder guard no longer matches.

Resolved blockers:
1. None.

Rule:
1. Any newly discovered blocker is appended here with closure criteria.
2. If this register is non-empty, no M3 execution command may run.

## 9) Exit Criteria
M3 can be marked `DONE` only when:
1. Section 7 checklist is fully complete.
2. M3 evidence contract artifacts are produced and verified.
3. Main plan M3 DoD checklist is complete.
4. `m4_handoff_pack.json` is published with verdict `ADVANCE_TO_M4`.
5. USER confirms progression to M4 activation.

Note:
1. This file does not change phase status.
2. Status transition is made only in `platform.build_plan.md`.
