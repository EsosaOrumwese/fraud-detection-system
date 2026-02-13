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
- [x] Required M3 handle set is explicit and complete.
- [x] Every required handle has a verification method.
- [x] Unresolved handles are either zero or explicitly blocker-marked.

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
| `SCENARIO_EQUIVALENCE_KEY_INPUT` | registry formula | handles registry (`sha256(canonical_json_v1)`) | `M3A_V6_PLACEHOLDER_GUARD` | `non_secret` | `CLOSED_EXEC` | `none` |
| `SCENARIO_EQUIVALENCE_KEY_CANONICAL_FIELDS` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_EXEC` | `none` |
| `SCENARIO_EQUIVALENCE_KEY_CANONICALIZATION_MODE` | registry literal | handles registry | `M3A_V1_HANDLE_KEY` | `non_secret` | `CLOSED_EXEC` | `none` |
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
   - 20 required rows tracked in closure matrix (including canonical scenario-equivalence field pins).
2. Current blockers:
   - None.
3. M3.A execution posture:
   - M3.A closure checks are complete,
   - progression to M3.B is unblocked.

Execution result (authoritative):
1. Previous fail-closed run:
   - `m3a_20260213T212724Z`
   - result: `overall_pass=false` (expected, placeholder guard fired).
2. Latest closure run:
   - `m3a_20260213T213547Z`
   - result: `overall_pass=true`.
3. Verification summary for latest run:
   - registry handle presence checks executed for all required keys,
   - M2 handoff artifact is present and readable,
   - ECR repository URI resolved (`fraud-platform-dev-min`),
   - evidence bucket reachability check passed,
   - immutable M1 provenance source exists under P(-1) evidence prefix,
   - placeholder guard for `SCENARIO_EQUIVALENCE_KEY_INPUT` passes after pin.
4. Evidence:
   - local:
     - `runs/dev_substrate/m3_a/20260213T213547Z/m3_a_handle_closure_snapshot.json`
   - durable:
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3a_20260213T213547Z/m3_a_handle_closure_snapshot.json`

### M3.B Run Identity Generation Contract
Goal:
1. Generate collision-safe run identity and record run header skeleton.

Tasks:
1. Define canonical `platform_run_id` format for this track:
   - `platform_<YYYYMMDDTHHMMSSZ>` (UTC, second precision).
2. Generate candidate id from UTC clock and validate syntax against the pinned regex.
3. Validate non-collision in run evidence root:
   - query `evidence/runs/<platform_run_id>/` for object existence,
   - if collision exists, regenerate using deterministic suffix policy (`_<nn>` with zero-padded increment).
4. Record run header skeleton:
   - `platform_run_id`
   - `written_at_utc`
   - `phase_id=P1`
   - `scenario_equivalence_key_input` reference.
5. Enforce fail-closed rule on unresolved scenario input:
   - if scenario-equivalence input rule or canonical field contract is missing, open blocker and stop.
6. Emit M3.B run-id generation evidence locally and durably.

DoD:
- [x] `platform_run_id` format is pinned and deterministic.
- [x] Collision check is executed and evidenced.
- [x] Placeholder scenario-equivalence input cannot silently pass.
- [x] Run-id generation evidence is written locally and durably.

### M3.B Decision Pins (Closed Before Execution)
1. Format law:
   - `platform_run_id` must use `platform_<YYYYMMDDTHHMMSSZ>`.
2. Collision law:
   - `evidence/runs/<platform_run_id>/` pre-existence is a hard collision signal.
3. Regeneration law:
   - collision resolution is deterministic and monotonic:
     - `platform_<YYYYMMDDTHHMMSSZ>_01`, `_02`, ... up to configured cap.
4. Retry cap law:
   - if collision retries exceed cap, fail closed and open blocker.
5. Scope law:
   - once minted and accepted, `platform_run_id` is immutable for the run.
6. Non-randomness law:
   - no random UUID fallback in M3.B for this track; ID generation remains auditable and reproducible.

### M3.B Verification Command Catalog (Pinned)
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3B_V1_ID_FORMAT` | validate candidate against regex `^platform_[0-9]{8}T[0-9]{6}Z(_[0-9]{2})?$` | enforces canonical id shape |
| `M3B_V2_EVIDENCE_PREFIX_COLLISION` | `aws s3api list-objects-v2 --bucket <S3_EVIDENCE_BUCKET> --prefix evidence/runs/<platform_run_id>/ --max-keys 1` | detects run-id collision in durable evidence root |
| `M3B_V3_SCENARIO_RULE_PRESENT` | `rg -n \"SCENARIO_EQUIVALENCE_KEY_INPUT|SCENARIO_EQUIVALENCE_KEY_CANONICAL_FIELDS|SCENARIO_EQUIVALENCE_KEY_CANONICALIZATION_MODE\" docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md` | confirms scenario-equivalence rule contract exists |
| `M3B_V4_SKELETON_WRITE_LOCAL` | write `m3_b_run_header_seed.json` under local run dir | proves run header skeleton generation |
| `M3B_V5_SKELETON_WRITE_DURABLE` | `aws s3 cp <local_seed_file> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_min/run_control/<m3b_execution_id>/m3_b_run_header_seed.json` | proves durable publication lane for M3.B |

### M3.B Blocker Taxonomy (Fail-Closed)
1. `M3B-B1`: invalid `platform_run_id` format.
2. `M3B-B2`: collision unresolved within retry cap.
3. `M3B-B3`: scenario-equivalence rule contract missing/incomplete.
4. `M3B-B4`: local seed evidence write failure.
5. `M3B-B5`: durable seed evidence publish failure.

### M3.B Evidence Contract (Execution)
1. Local:
   - `runs/dev_substrate/m3_b/<timestamp>/m3_b_run_id_generation_snapshot.json`
   - `runs/dev_substrate/m3_b/<timestamp>/m3_b_run_header_seed.json`
2. Durable:
   - `evidence/dev_min/run_control/<m3b_execution_id>/m3_b_run_id_generation_snapshot.json`
   - `evidence/dev_min/run_control/<m3b_execution_id>/m3_b_run_header_seed.json`
3. Snapshot minimum fields:
   - `candidate_platform_run_id`
   - `final_platform_run_id`
   - `collision_attempts`
   - `collision_detected`
   - `format_check_pass`
   - `scenario_rule_contract_pass`
   - `overall_pass`

### M3.B Planning Status (Current)
1. M3.B planning has been expanded to closure-grade detail.
2. Execution has completed with authoritative run:
   - `m3b_20260213T214223Z`,
   - result: `overall_pass=true`.
3. Verification summary:
   - `platform_run_id` candidate `platform_20260213T214223Z` passed format check,
   - collision probe on `evidence/runs/platform_20260213T214223Z/` returned no collision (`collision_attempts=0`),
   - scenario-equivalence contract presence checks passed,
   - local and durable seed/snapshot publication passed.
4. Evidence:
   - local:
     - `runs/dev_substrate/m3_b/20260213T214223Z/m3_b_run_header_seed.json`
     - `runs/dev_substrate/m3_b/20260213T214223Z/m3_b_run_id_generation_snapshot.json`
   - durable:
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3b_20260213T214223Z/m3_b_run_header_seed.json`
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3b_20260213T214223Z/m3_b_run_id_generation_snapshot.json`
5. No open M3.B blocker is currently registered.

### M3.C Config Payload + Digest Contract
Goal:
1. Produce deterministic run payload and digest.

Tasks:
1. Assemble run config payload from:
   - M2 handoff substrate handles (S3/topic/DB/runtime identifiers),
   - registry literals required for P1 identity/provenance,
   - image provenance fields from immutable M1 packaging evidence,
   - M3.B accepted run identity (`platform_run_id`).
2. Build payload structure using pinned field names:
   - `FIELD_PLATFORM_RUN_ID`
   - `FIELD_SCENARIO_RUN_ID`
   - `FIELD_WRITTEN_AT_UTC`
   - `CONFIG_DIGEST_FIELD`
3. Canonicalize payload serialization with deterministic ordering (`json_sorted_keys_v1` posture).
4. Compute digest using `CONFIG_DIGEST_ALGO`.
5. Verify digest reproducibility by recomputing and comparing value.
6. Ensure no secret values are embedded in payload evidence.
7. Publish M3.C payload/digest evidence locally and durably.

DoD:
- [x] Payload covers required P1 identity/provenance fields.
- [x] Digest is reproducible and stored under `CONFIG_DIGEST_FIELD`.
- [x] Payload evidence is non-secret.
- [x] M3.C payload/digest evidence exists locally and durably.

### M3.C Decision Pins (Closed Before Execution)
1. Input-anchor law:
   - M3.C must consume the M3.B accepted run identity as immutable input for this run (`platform_20260213T214223Z`).
2. Envelope law:
   - payload must include, at minimum:
     - `env=dev_min`,
     - `phase_id=P1`,
     - `platform_run_id`,
     - `written_at_utc`,
     - scenario-equivalence contract fields,
     - referenced substrate-handle map,
     - image provenance fields (`image_tag`, `image_digest`, `git_sha`).
3. Provenance law:
   - image fields must come from immutable M1 evidence sources; mutable pointers cannot be authoritative.
4. Canonicalization law:
   - digest input is canonical JSON only (sorted keys, stable separators) under pinned mode.
5. Digest law:
   - digest algorithm is taken from `CONFIG_DIGEST_ALGO` and result is written at `CONFIG_DIGEST_FIELD`.
6. Reproducibility law:
   - two independent digest computations over the same canonical payload must match exactly.
7. Non-secret law:
   - no plaintext secrets/tokens/passwords in M3.C payload or digest artifacts.

### M3.C Verification Command Catalog (Pinned)
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3C_V1_M3B_INPUT` | `Test-Path runs/dev_substrate/m3_b/20260213T214223Z/m3_b_run_id_generation_snapshot.json` | verifies M3.B accepted run-id input anchor exists |
| `M3C_V2_HANDLES_PRESENT` | `rg -n \"FIELD_PLATFORM_RUN_ID|FIELD_SCENARIO_RUN_ID|FIELD_WRITTEN_AT_UTC|CONFIG_DIGEST_ALGO|CONFIG_DIGEST_FIELD|SCENARIO_EQUIVALENCE_KEY_INPUT|IMAGE_TAG_EVIDENCE_FIELD|IMAGE_DIGEST_EVIDENCE_FIELD|IMAGE_GIT_SHA_EVIDENCE_FIELD\" docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md` | verifies required M3.C handle keys exist |
| `M3C_V3_M2_HANDOFF` | `Test-Path runs/dev_substrate/m2_j/20260213T205715Z/m3_handoff_pack.json` | verifies substrate handle source for payload assembly |
| `M3C_V4_PAYLOAD_WRITE_LOCAL` | write `m3_c_config_payload.json` under local M3.C run dir | proves payload assembly succeeded |
| `M3C_V5_CANONICAL_PAYLOAD` | write canonical payload (`m3_c_config_payload.canonical.json`) using sorted-key JSON mode | proves canonical digest input is explicit |
| `M3C_V6_DIGEST_COMPUTE` | compute digest from canonical payload using `CONFIG_DIGEST_ALGO`; write `m3_c_digest_snapshot.json` | proves deterministic digest production |
| `M3C_V7_DIGEST_REPRO` | recompute digest and compare with first digest | proves reproducibility predicate |
| `M3C_V8_SECRET_SCAN` | `rg -n -i \"password|secret|token|apikey|api_key\" runs/dev_substrate/m3_c/<timestamp>/m3_c_config_payload*.json` | fail-closed check for obvious secret leakage |
| `M3C_V9_DURABLE_UPLOAD` | `aws s3 cp <local_m3c_artifact> s3://<S3_EVIDENCE_BUCKET>/evidence/dev_min/run_control/<m3c_execution_id>/` | proves durable M3.C evidence publication |

### M3.C Blocker Taxonomy (Fail-Closed)
1. `M3C-B1`: required payload field or handle reference missing.
2. `M3C-B2`: canonicalization mode unresolved or canonical payload generation failed.
3. `M3C-B3`: digest algorithm missing/unsupported for configured policy.
4. `M3C-B4`: digest reproducibility mismatch.
5. `M3C-B5`: image provenance fields unresolved or sourced from mutable pointer only.
6. `M3C-B6`: non-secret policy violation in payload/digest artifacts.
7. `M3C-B7`: local M3.C artifact write failure.
8. `M3C-B8`: durable M3.C evidence upload failure.

### M3.C Evidence Contract (Execution)
1. Local:
   - `runs/dev_substrate/m3_c/<timestamp>/m3_c_config_payload.json`
   - `runs/dev_substrate/m3_c/<timestamp>/m3_c_config_payload.canonical.json`
   - `runs/dev_substrate/m3_c/<timestamp>/m3_c_digest_snapshot.json`
2. Durable:
   - `evidence/dev_min/run_control/<m3c_execution_id>/m3_c_config_payload.json`
   - `evidence/dev_min/run_control/<m3c_execution_id>/m3_c_config_payload.canonical.json`
   - `evidence/dev_min/run_control/<m3c_execution_id>/m3_c_digest_snapshot.json`
3. Snapshot minimum fields (`m3_c_digest_snapshot.json`):
   - `m3c_execution_id`
   - `platform_run_id`
   - `config_digest_algo`
   - `config_digest`
   - `digest_reproducible`
   - `non_secret_policy_pass`
   - `blockers`
   - `overall_pass`

### M3.C Planning Status (Current)
1. M3.C planning has been expanded to closure-grade detail.
2. Input anchor is explicit:
   - accepted M3.B run-id source:
     - `runs/dev_substrate/m3_b/20260213T214223Z/m3_b_run_id_generation_snapshot.json`
3. Execution has completed with authoritative run:
   - `m3c_20260213T215336Z`,
   - result: `overall_pass=true`.
4. Verification summary:
   - payload includes required P1 identity/provenance fields,
   - digest computed with `sha256` and written to `config_digest`,
   - digest recomputation matched exactly (`digest_reproducible=true`),
   - non-secret policy check passed,
   - local and durable payload/canonical/digest artifacts published successfully.
5. Evidence:
   - local:
     - `runs/dev_substrate/m3_c/20260213T215336Z/m3_c_config_payload.json`
     - `runs/dev_substrate/m3_c/20260213T215336Z/m3_c_config_payload.canonical.json`
     - `runs/dev_substrate/m3_c/20260213T215336Z/m3_c_digest_snapshot.json`
   - durable:
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3c_20260213T215336Z/m3_c_config_payload.json`
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3c_20260213T215336Z/m3_c_config_payload.canonical.json`
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3c_20260213T215336Z/m3_c_digest_snapshot.json`
6. No open M3.C blocker is currently registered.

### M3.D Durable Run Evidence Publication
Goal:
1. Persist the run anchor to S3 and verify durability.

Tasks:
1. Create canonical M3 execution root for the D->G closure lane:
   - `m3_execution_id = m3_<YYYYMMDDTHHmmssZ>`,
   - local root: `runs/dev_substrate/m3/<timestamp>/`.
2. Materialize local run anchor artifacts from M3.C outputs:
   - `runs/dev_substrate/m3/<timestamp>/run.json`
   - `runs/dev_substrate/m3/<timestamp>/run_started.json`
3. Upload durable run anchor artifacts:
   - `evidence/runs/<platform_run_id>/run.json`
   - `evidence/runs/<platform_run_id>/run_started.json`
4. Verify durable existence via S3 head/list checks.
5. Publish D-lane publication snapshot:
   - local: `runs/dev_substrate/m3/<timestamp>/m3_d_run_publication_snapshot.json`
   - durable: `evidence/dev_min/run_control/<m3_execution_id>/m3_d_run_publication_snapshot.json`
6. Record write receipts and object URIs for M3 evidence.

DoD:
- [x] `run.json` and `run_started.json` exist locally and durably.
- [x] Durable object verification succeeds.
- [x] `run.json` references the correct `platform_run_id`.
- [x] M3.D publication snapshot exists locally and durably.

### M3.D Decision Pins (Closed Before Execution)
1. Input-anchor law:
   - M3.D consumes M3.C as its single input anchor and must fail closed unless M3.C `overall_pass=true`.
2. Manifest law:
   - `run.json` must include at minimum:
     - `platform_run_id`,
     - `scenario_run_id`,
     - `env`,
     - `written_at_utc`,
     - `config_digest`,
     - image provenance fields.
3. Start-marker law:
   - this track requires explicit `run_started.json` (even though optional in runbook) for deterministic evidence symmetry.
4. Write-order law:
   - local `run.json` and `run_started.json` must be written before durable upload attempts.
5. Immutability law:
   - if durable `run.json` already exists for `platform_run_id` with conflicting digest/provenance, fail closed and open blocker.
6. Non-secret law:
   - run anchor artifacts must remain non-secret.

### M3.D Verification Command Catalog (Pinned)
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3D_V1_M3C_PASS` | `Get-Content runs/dev_substrate/m3_c/<timestamp>/m3_c_digest_snapshot.json | ConvertFrom-Json` | verifies M3.C pass anchor and digest availability |
| `M3D_V2_LOCAL_RUN_JSON` | write `run.json` under `runs/dev_substrate/m3/<timestamp>/` | proves local run anchor generation |
| `M3D_V3_LOCAL_RUN_STARTED` | write `run_started.json` under `runs/dev_substrate/m3/<timestamp>/` | proves explicit start-marker generation |
| `M3D_V4_DURABLE_UPLOAD_RUN_JSON` | `aws s3 cp run.json s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<platform_run_id>/run.json` | publishes canonical run anchor |
| `M3D_V5_DURABLE_UPLOAD_RUN_STARTED` | `aws s3 cp run_started.json s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<platform_run_id>/run_started.json` | publishes run start marker |
| `M3D_V6_DURABLE_HEAD_CHECK` | `aws s3api head-object --bucket <S3_EVIDENCE_BUCKET> --key evidence/runs/<platform_run_id>/{run.json|run_started.json}` | verifies durable object existence |
| `M3D_V7_PUBLICATION_SNAPSHOT` | write/upload `m3_d_run_publication_snapshot.json` | captures deterministic D-lane closure verdict |

### M3.D Blocker Taxonomy (Fail-Closed)
1. `M3D-B1`: M3.C pass anchor missing or non-pass.
2. `M3D-B2`: `run.json` missing required fields or invalid shape.
3. `M3D-B3`: local run anchor artifact write failure.
4. `M3D-B4`: pre-existing durable `run.json` conflicts with M3.C digest/provenance.
5. `M3D-B5`: durable upload failure for `run.json`.
6. `M3D-B6`: durable upload/head verification failure for `run_started.json`.
7. `M3D-B7`: non-secret policy violation in D-lane artifacts.
8. `M3D-B8`: D-lane publication snapshot missing.

### M3.D Planning Status (Current)
1. M3.D planning has been expanded to closure-grade detail.
2. Input anchors are explicit:
   - M3.C digest snapshot (`m3c_20260213T215336Z`),
   - M3.B run-id anchor (`platform_20260213T214223Z`).
3. Execution has completed with authoritative run:
   - `m3_20260213T221631Z`,
   - result: `overall_pass=true`.
4. Verification summary:
   - M3.C pass anchor check passed,
   - local `run.json` + `run_started.json` writes passed,
   - durable run anchor objects exist under `evidence/runs/platform_20260213T214223Z/`,
   - non-secret policy check passed.
5. Blocker handling during execution:
   - first D-lane attempt surfaced `M3D-B4` due false-positive preexistence detection in head-object helper,
   - resolution: corrected preexistence detection to use AWS CLI exit-code truth; rerun accepted existing compatible `run.json`,
   - final D-lane resolution mode: `reused_existing_compatible_run_json`.
6. Evidence:
   - local:
     - `runs/dev_substrate/m3/20260213T221631Z/run.json`
     - `runs/dev_substrate/m3/20260213T221631Z/run_started.json`
     - `runs/dev_substrate/m3/20260213T221631Z/m3_d_run_publication_snapshot.json`
   - durable:
     - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/run.json`
     - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/run_started.json`
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3_20260213T221631Z/m3_d_run_publication_snapshot.json`
7. No open M3.D blocker is currently registered.

### M3.E Runtime Scope Export Contract for M4
Goal:
1. Export deterministic run-scope surface for daemon start lanes.

Tasks:
1. Build M4 runtime scope bundle with:
   - `platform_run_id`
   - `REQUIRED_PLATFORM_RUN_ID_ENV_KEY`
   - env-key/value map (`REQUIRED_PLATFORM_RUN_ID=<platform_run_id>`)
   - run evidence root URI
   - M3 manifest URI references (`run.json`, `run_started.json`, M3.C digest snapshot).
2. Include deterministic service family scope coverage for P2 bring-up:
   - WSP, IG, IEG, OFP, CSFB, ArchiveWriter, DL, DF, AL, DLA, CaseTrigger, CM, LS, reporter lane.
3. Ensure bundle is non-secret.
4. Publish local and durable handoff artifacts:
   - `runs/dev_substrate/m3/<timestamp>/m4_runtime_scope_bundle.json`
   - `runs/dev_substrate/m3/<timestamp>/m3_e_runtime_scope_snapshot.json`
   - `evidence/dev_min/run_control/<m3_execution_id>/m4_runtime_scope_bundle.json`
   - `evidence/dev_min/run_control/<m3_execution_id>/m3_e_runtime_scope_snapshot.json`

DoD:
- [x] Runtime scope bundle is complete and non-secret.
- [x] M4 consumers can read a single authoritative scope surface.
- [x] Missing run-scope keys are fail-closed.
- [x] Runtime-scope snapshot exists locally and durably.

### M3.E Decision Pins (Closed Before Execution)
1. Scope-source law:
   - M3.E must source `platform_run_id` and run evidence URIs from M3.D-published artifacts only.
2. Env-key law:
   - runtime env key must be taken from `REQUIRED_PLATFORM_RUN_ID_ENV_KEY` and not hardcoded ad hoc.
3. Single-surface law:
   - M4 consumers must use only `m4_runtime_scope_bundle.json` as the authoritative run-scope surface.
4. Coverage law:
   - all in-scope P2 daemon families must be represented in the runtime-scope export map.
5. Non-secret law:
   - no secret values are allowed in runtime scope bundle/snapshot artifacts.
6. Fail-closed law:
   - missing scope key/value for any required family blocks M3 progression.

### M3.E Verification Command Catalog (Pinned)
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3E_V1_DURABLE_RUN_ANCHOR` | `aws s3api head-object --bucket <S3_EVIDENCE_BUCKET> --key evidence/runs/<platform_run_id>/{run.json|run_started.json}` | verifies D-lane durable anchors exist |
| `M3E_V2_SCOPE_KEY_HANDLE` | `rg -n \"REQUIRED_PLATFORM_RUN_ID_ENV_KEY\" docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md` | verifies env-key source pin exists |
| `M3E_V3_LOCAL_SCOPE_BUNDLE` | write `m4_runtime_scope_bundle.json` locally | proves scope bundle materialization |
| `M3E_V4_SCOPE_COMPLETENESS` | validate bundle includes required daemon family map + env key/value + URIs | proves coverage and schema completeness |
| `M3E_V5_SECRET_SCAN` | scan `m4_runtime_scope_bundle.json` / `m3_e_runtime_scope_snapshot.json` for secret markers | enforces non-secret policy |
| `M3E_V6_DURABLE_UPLOAD` | `aws s3 cp` bundle/snapshot to `evidence/dev_min/run_control/<m3_execution_id>/` | proves durable publication |

### M3.E Blocker Taxonomy (Fail-Closed)
1. `M3E-B1`: M3.D durable run anchor artifacts missing.
2. `M3E-B2`: `REQUIRED_PLATFORM_RUN_ID_ENV_KEY` unresolved/missing.
3. `M3E-B3`: runtime-scope bundle missing required fields/families.
4. `M3E-B4`: run-scope env map mismatch (`value != platform_run_id`).
5. `M3E-B5`: local bundle/snapshot write failure.
6. `M3E-B6`: durable bundle/snapshot upload failure.
7. `M3E-B7`: non-secret policy violation in E-lane artifacts.

### M3.E Planning Status (Current)
1. M3.E planning has been expanded to closure-grade detail.
2. Execution has completed with authoritative run:
   - `m3_20260213T221631Z`,
   - result: `overall_pass=true`.
3. Verification summary:
   - durable run anchor precondition passed,
   - runtime scope key/value map is complete and valid for required families,
   - non-secret policy check passed,
   - durable bundle/snapshot publication checks passed.
4. Blocker handling during execution:
   - first E-lane attempt surfaced `M3E-B3` and `M3E-B6` due scope completeness predicate mismatch on ordered map shape,
   - resolution: corrected completeness validation to deterministic map-count check (`envMap.Count`), then reran the lane.
5. Evidence:
   - local:
     - `runs/dev_substrate/m3/20260213T221631Z/m4_runtime_scope_bundle.json`
     - `runs/dev_substrate/m3/20260213T221631Z/m3_e_runtime_scope_snapshot.json`
   - durable:
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3_20260213T221631Z/m4_runtime_scope_bundle.json`
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3_20260213T221631Z/m3_e_runtime_scope_snapshot.json`
6. No open M3.E blocker is currently registered.

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
3. Compile explicit blocker set from sub-phase outputs (`M3A-*`, `M3B-*`, `M3C-*`, `M3D-*`, `M3E-*`).
4. Publish F-lane verdict artifact:
   - `runs/dev_substrate/m3/<timestamp>/m3_f_verdict_snapshot.json`
   - `evidence/dev_min/run_control/<m3_execution_id>/m3_f_verdict_snapshot.json`

DoD:
- [x] Verdict predicates are explicit and reproducible.
- [x] Blocker taxonomy is fail-closed and actionable.
- [x] Verdict is persisted in M3 closeout artifacts.

### M3.F Decision Pins (Closed Before Execution)
1. Predicate law:
   - only the five pinned predicates are used for binary verdicting.
2. Source law:
   - predicates must be derived from authoritative sub-phase snapshots, not operator memory/manual interpretation.
3. Binary verdict law:
   - `ADVANCE_TO_M4` only when all predicates are true and blocker set is empty.
4. Hold law:
   - any false predicate or any blocker forces `HOLD_M3`.
5. Trace law:
   - verdict snapshot must include predicate map + blocker register + source execution IDs.

### M3.F Verification Command Catalog (Pinned)
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3F_V1_LOAD_PHASE_SNAPSHOTS` | load A/B/C/D/E snapshot artifacts (`ConvertFrom-Json`) | ensures verdicting inputs are authoritative and machine-readable |
| `M3F_V2_PREDICATE_EVAL` | evaluate `handles_closed`, `run_id_collision_free`, `digest_reproducible`, `run_json_durable`, `runtime_scope_export_ready` | computes deterministic predicate truth map |
| `M3F_V3_BLOCKER_ROLLUP` | merge blocker arrays across A-E snapshots | enforces fail-closed blocker propagation |
| `M3F_V4_VERDICT_WRITE_LOCAL` | write `m3_f_verdict_snapshot.json` locally | persists binary verdict and rationale |
| `M3F_V5_VERDICT_UPLOAD_DURABLE` | `aws s3 cp` verdict snapshot to run-control prefix | proves durable verdict publication |

### M3.F Blocker Taxonomy (Fail-Closed)
1. `M3F-B1`: missing/unreadable prerequisite snapshot from A-E lanes.
2. `M3F-B2`: predicate evaluation error or incomplete predicate map.
3. `M3F-B3`: non-empty blocker rollup from prior lanes.
4. `M3F-B4`: verdict snapshot write failure (local).
5. `M3F-B5`: verdict snapshot upload failure (durable).

### M3.F Planning Status (Current)
1. M3.F planning has been expanded to closure-grade detail.
2. Execution has completed with authoritative run:
   - `m3_20260213T221631Z`,
   - result: `overall_pass=true`,
   - verdict: `ADVANCE_TO_M4`.
3. Predicate summary:
   - `handles_closed=true`
   - `run_id_collision_free=true`
   - `digest_reproducible=true`
   - `run_json_durable=true`
   - `runtime_scope_export_ready=true`
4. Evidence:
   - local:
     - `runs/dev_substrate/m3/20260213T221631Z/m3_f_verdict_snapshot.json`
   - durable:
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3_20260213T221631Z/m3_f_verdict_snapshot.json`
5. No open M3.F blocker is currently registered.

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
3. Ensure handoff pack includes:
   - `platform_run_id`
   - `scenario_run_id`
   - `config_digest`
   - `m3_verdict`
   - `runtime_scope_bundle_uri`
   - run evidence root and anchor artifact URIs
   - source execution IDs (`m3a`, `m3b`, `m3c`, `m3d`, `m3e`, `m3f`)
4. Record artifact URIs in execution notes.

DoD:
- [x] Handoff artifacts exist locally and durably.
- [x] `m4_handoff_pack.json` is structurally complete and non-secret.
- [x] Artifact URI list is captured for M4 entry.

### M3.G Decision Pins (Closed Before Execution)
1. Precondition law:
   - M3.G can run only when M3.F verdict is `ADVANCE_TO_M4`.
2. Handoff completeness law:
   - `m4_handoff_pack.json` must include all required M4 activation handles and URIs listed above.
3. Non-secret law:
   - handoff artifacts must not contain secrets; only handles/URIs/IDs.
4. Finalization law:
   - M3 phase closure claim is valid only after durable `m3_run_pinning_snapshot.json` and `m4_handoff_pack.json` publication.

### M3.G Verification Command Catalog (Pinned)
| Verify ID | Command template | Purpose |
| --- | --- | --- |
| `M3G_V1_REQUIRE_ADVANCE_VERDICT` | read `m3_f_verdict_snapshot.json` and assert `verdict=ADVANCE_TO_M4` | enforces precondition law |
| `M3G_V2_BUILD_HANDOFF_LOCAL` | write `m3_run_pinning_snapshot.json` and `m4_handoff_pack.json` locally | materializes final M3 closure/handoff package |
| `M3G_V3_HANDOFF_SCHEMA_CHECK` | validate required keys/URIs exist in `m4_handoff_pack.json` | enforces completeness law |
| `M3G_V4_SECRET_SCAN` | scan handoff artifacts for secret markers | enforces non-secret law |
| `M3G_V5_DURABLE_UPLOAD` | `aws s3 cp` both artifacts to `evidence/dev_min/run_control/<m3_execution_id>/` | proves durable closeout publication |
| `M3G_V6_URI_CAPTURE` | append published URIs to execution note/logbook | provides operator-ready M4 entry references |

### M3.G Blocker Taxonomy (Fail-Closed)
1. `M3G-B1`: M3.F verdict is not `ADVANCE_TO_M4`.
2. `M3G-B2`: handoff pack missing required fields or URIs.
3. `M3G-B3`: local closeout artifact write failure.
4. `M3G-B4`: durable closeout artifact upload failure.
5. `M3G-B5`: non-secret policy violation in handoff artifacts.

### M3.G Planning Status (Current)
1. M3.G planning has been expanded to closure-grade detail.
2. Execution has completed with authoritative run:
   - `m3_20260213T221631Z`,
   - result: `overall_pass=true`.
3. Verification summary:
   - `M3.F` verdict precondition passed (`ADVANCE_TO_M4`),
   - handoff keys and required URIs are complete,
   - non-secret policy check passed,
   - durable publication checks for closeout artifacts passed.
4. Evidence:
   - local:
     - `runs/dev_substrate/m3/20260213T221631Z/m3_run_pinning_snapshot.json`
     - `runs/dev_substrate/m3/20260213T221631Z/m4_handoff_pack.json`
     - `runs/dev_substrate/m3/20260213T221631Z/m3_g_handoff_snapshot.json`
   - durable:
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3_20260213T221631Z/m3_run_pinning_snapshot.json`
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3_20260213T221631Z/m4_handoff_pack.json`
     - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3_20260213T221631Z/m3_g_handoff_snapshot.json`
5. No open M3.G blocker is currently registered.

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
3. `evidence/dev_min/run_control/<m3_execution_id>/m3_d_run_publication_snapshot.json`
4. `evidence/dev_min/run_control/<m3_execution_id>/m4_runtime_scope_bundle.json`
5. `evidence/dev_min/run_control/<m3_execution_id>/m3_e_runtime_scope_snapshot.json`
6. `evidence/dev_min/run_control/<m3_execution_id>/m3_f_verdict_snapshot.json`
7. `evidence/dev_min/run_control/<m3_execution_id>/m3_run_pinning_snapshot.json`
8. `evidence/dev_min/run_control/<m3_execution_id>/m4_handoff_pack.json`
9. `evidence/dev_min/run_control/<m3b_execution_id>/m3_b_run_id_generation_snapshot.json`
10. `evidence/dev_min/run_control/<m3b_execution_id>/m3_b_run_header_seed.json`
11. `evidence/dev_min/run_control/<m3c_execution_id>/m3_c_config_payload.json`
12. `evidence/dev_min/run_control/<m3c_execution_id>/m3_c_config_payload.canonical.json`
13. `evidence/dev_min/run_control/<m3c_execution_id>/m3_c_digest_snapshot.json`
14. local mirrors under:
   - `runs/dev_substrate/m3/<timestamp>/...`
   - `runs/dev_substrate/m3_b/<timestamp>/...`
   - `runs/dev_substrate/m3_c/<timestamp>/...`

Notes:
1. Evidence must be non-secret.
2. Any secret-bearing payload detected in run artifacts is a hard blocker.
3. Scenario-equivalence input may be represented by stable hash/reference rather than raw secret value.

## 7) M3 Completion Checklist
- [x] M3.A complete
- [x] M3.B complete
- [x] M3.C complete
- [x] M3.D complete
- [x] M3.E complete
- [x] M3.F complete
- [x] M3.G complete

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
1. None.

Resolved blockers:
1. `M3A-B1` (resolved)
   - impacted sub-phase:
     - `M3.A`
   - resolution summary:
     - pinned `SCENARIO_EQUIVALENCE_KEY_INPUT` to `sha256(canonical_json_v1)` in handles registry,
     - added canonical-equivalence field pins and canonicalization mode,
     - reran M3.A verification with placeholder guard passing.
   - closure evidence:
     - local: `runs/dev_substrate/m3_a/20260213T213547Z/m3_a_handle_closure_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3a_20260213T213547Z/m3_a_handle_closure_snapshot.json`
2. `M3D-B4` (resolved)
   - impacted sub-phase:
     - `M3.D`
   - resolution summary:
     - first execution surfaced false-positive preexistence conflict due head-object detection helper,
     - corrected detection to AWS CLI exit-code truth and reran D-lane,
     - accepted existing compatible `run.json` and preserved immutability law.
   - closure evidence:
     - local: `runs/dev_substrate/m3/20260213T221631Z/m3_d_run_publication_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3_20260213T221631Z/m3_d_run_publication_snapshot.json`
3. `M3E-B3` and `M3E-B6` (resolved)
   - impacted sub-phase:
     - `M3.E`
   - resolution summary:
     - first execution had scope-completeness predicate mismatch on ordered map shape, causing publish hold,
     - corrected completeness predicate to deterministic env-map count check and reran E-lane.
   - closure evidence:
     - local: `runs/dev_substrate/m3/20260213T221631Z/m3_e_runtime_scope_snapshot.json`
     - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3_20260213T221631Z/m3_e_runtime_scope_snapshot.json`

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
