# Dev Substrate Deep Plan - M1 (P(-1) Packaging Readiness)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M1._
_Last updated: 2026-02-13_

## 0) Purpose
M1 defines the packaging and provenance contract that must be satisfied before substrate and runtime phases begin.
This phase ensures we can produce a reproducible runtime image with validated entrypoints and evidence-grade provenance.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (P(-1))
3. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md` (ECR/image/entrypoint handles)
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

Supporting:
- `docs/design/platform/local-parity/addendum_2_process_job_cards.txt` (process entrypoint semantics)

## 2) Scope Boundary for M1
In scope:
- single-image packaging strategy confirmation,
- entrypoint-mode contract for Spine Green v0 components,
- immutable tag + digest provenance contract,
- runtime secret-injection contract (no baked secrets),
- build/run evidence artifact contract for P(-1),
- build command-surface pinning.

Out of scope:
- Terraform substrate deployment (M2),
- run pinning and daemon/job runtime execution (M3+),
- full workload streaming/ingest/runtime validation (M4+).

## 3) M1 Deliverables
1. Packaging contract document is complete and unambiguous.
2. Entrypoint matrix is complete for all in-scope lanes.
3. Build/provenance evidence schema for P(-1) is pinned.
4. Secret-handling and supply-chain guardrails are pinned.
5. Build-go checklist is ready for execution pass.

## 4) Execution Gate for This Phase
Current posture:
- M1 is active for planning and contract-finalization.

Execution rule:
- Image build/push commands run only after explicit USER build-go.
- This file prepares the execution checklist and acceptance criteria for that pass.

## 5) Work Breakdown (Deep)

## M1.A Image Contract Freeze
Goal:
- lock a reproducible image identity model for dev_min v0.

Tasks:
1. Confirm single-image strategy for v0 and capture rationale.
2. Pin immutable tagging convention (`git-<sha>` style) and optional convenience tag.
3. Define image reference mode for ECS task/service consumption.

DoD:
- [x] Single-image contract is explicitly documented.
- [x] Immutable tag contract is pinned and maps to handles registry keys.
- [x] Mutable convenience tag posture is clearly non-authoritative.

M1.A contract freeze record:
1. Single-image strategy is pinned for v0.
   - Handle mapping: `ECR_REPO_NAME`, `ECR_REPO_URI`.
   - Posture: one platform image must serve all Spine Green v0 entrypoint modes.
2. Immutable tag strategy is pinned.
   - Handle mapping: `IMAGE_TAG_GIT_SHA_PATTERN`.
   - Posture: immutable `git-<sha>` tag is authoritative for reproducibility.
3. Mutable tag strategy is pinned as convenience-only.
   - Handle mapping: `IMAGE_TAG_DEV_MIN_LATEST`.
   - Posture: optional operator convenience tag is non-authoritative and cannot be used as closure proof.
4. Runtime reference mode is pinned.
   - Handle mapping: `IMAGE_REFERENCE_MODE = "immutable_preferred"`.
   - Posture: ECS task/service definitions must be able to pin immutable tag references.
5. Future split policy is pinned.
   - Multi-image decomposition is out-of-scope for M1 and requires explicit repin in authority docs.

M1.A planning evidence:
- Registry authority source reviewed:
  - `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md` (Section 6).
- Runbook alignment source reviewed:
  - `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (P(-1) pinned decisions).
- This phase is contract-finalization only; build/push evidence is deferred to M1 execution build-go pass.

## M1.B Entrypoint Matrix Completion
Goal:
- ensure one image supports all required phase entrypoint modes.

Tasks:
1. Enumerate all required logical entrypoints:
   - oracle seed/sort/checker,
   - SR,
   - WSP,
   - IG service,
   - RTDL core workers,
   - decision lane workers,
   - case/labels workers,
   - reporter.
2. Map each logical entrypoint to module/command contract (without executing).
3. Define entrypoint validation method for build-go pass.

DoD:
- [x] Full entrypoint matrix exists with zero missing in-scope components.
- [x] Every entrypoint has a deterministic invocation contract.
- [x] Validation method is pinned (what proves entrypoint exists and is callable).

M1.B entrypoint matrix (frozen):

| Handle key | Runtime mode(s) | Deterministic invocation contract (single image) | Required args contract |
| --- | --- | --- | --- |
| `ENTRYPOINT_ORACLE_SEED` | Oracle pack/seal job | `python -m fraud_detection.oracle_store.pack_cli` | `--profile <path> --engine-run-root <s3://...> --scenario-id <id> --engine-release <release>` |
| `ENTRYPOINT_ORACLE_STREAM_SORT` | Oracle stream-sort job | `python -m fraud_detection.oracle_store.stream_sort_cli` | `--profile <path> --engine-run-root <s3://...> --scenario-id <id>` |
| `ENTRYPOINT_ORACLE_CHECKER` | Oracle checker job | `python -m fraud_detection.oracle_store.cli` | `--profile <path> --engine-run-root <s3://...>` (`--scenario-id`/`--output-ids`/`--strict-seal` optional by phase posture) |
| `ENTRYPOINT_SR` | Scenario runner control task | `python -m fraud_detection.scenario_runner.cli run` | `--wiring <path> --policy <path> --run-equivalence-key <key> --manifest-fingerprint <fp> --parameter-hash <hash> --seed <int> --window-start <iso> --window-end <iso>` |
| `ENTRYPOINT_WSP` | World streamer producer task | `python -m fraud_detection.world_streamer_producer.cli` | `--profile <path>` (`--engine-run-root`, `--scenario-id`, `--output-ids`, `--max-events` optional overrides) |
| `ENTRYPOINT_IG_SERVICE` | IG daemon/service | `python -m fraud_detection.ingestion_gate.service` | `--profile <path>` (`--host`/`--port` pinned in task args; `IG_LISTEN_ADDR` + `IG_PORT` handles) |
| `ENTRYPOINT_RTDL_CORE_WORKER` | ArchiveWriter | `python -m fraud_detection.archive_writer.worker` | `--profile <path>` (`--once` optional for one-shot verification) |
| `ENTRYPOINT_RTDL_CORE_WORKER` | IEG service | `python -m fraud_detection.identity_entity_graph.service` | `--profile <path>` (`--host`/`--port` optional overrides) |
| `ENTRYPOINT_RTDL_CORE_WORKER` | OFP projector | `python -m fraud_detection.online_feature_plane.projector` | `--profile <path>` (`--once` optional) |
| `ENTRYPOINT_RTDL_CORE_WORKER` | CSFB intake | `python -m fraud_detection.context_store_flow_binding.intake` | `--policy <path>` (`--once`/`--replay-manifest` optional) |
| `ENTRYPOINT_DECISION_LANE_WORKER` | DL worker | `python -m fraud_detection.degrade_ladder.worker` | `--profile <path>` (`--once` optional) |
| `ENTRYPOINT_DECISION_LANE_WORKER` | DF worker | `python -m fraud_detection.decision_fabric.worker` | `--profile <path>` (`--once` optional) |
| `ENTRYPOINT_DECISION_LANE_WORKER` | AL worker | `python -m fraud_detection.action_layer.worker` | `--profile <path>` (`--once` optional) |
| `ENTRYPOINT_DECISION_LANE_WORKER` | DLA worker | `python -m fraud_detection.decision_log_audit.worker` | `--profile <path>` (`--once` optional) |
| `ENTRYPOINT_DECISION_LANE_WORKER` | CaseTrigger worker | `python -m fraud_detection.case_trigger.worker` | `--profile <path>` (`--once` optional) |
| `ENTRYPOINT_CM_SERVICE` | CM worker (service slot) | `python -m fraud_detection.case_mgmt.worker` | `--profile <path>` (`--once` optional) |
| `ENTRYPOINT_LS_SERVICE` | LS worker (service slot) | `python -m fraud_detection.label_store.worker` | `--profile <path>` (`--once` optional) |
| `ENTRYPOINT_REPORTER` | Obs/Gov reporter task | `python -m fraud_detection.platform_reporter.cli` | `--profile <path>` (`--platform-run-id` optional; defaults to active run) |

M1.B validation method (pinned for build-go pass):
1. For each matrix row, run the module import/argparse smoke command in image context:
   - `python -m <module> --help` for non-subcommand CLIs.
   - `python -m fraud_detection.scenario_runner.cli run --help` for SR run mode.
2. For each row, run one dry invocation contract check with required args only:
   - use a minimal dev profile/wiring/policy fixture bundle,
   - run daemon-capable workers with `--once` where available,
   - require process startup + argument parse success (`exit 0`) as pass criterion.
3. `ENTRYPOINT_ORACLE_CHECKER` specifically must use `fraud_detection.oracle_store.cli`; no fallback to non-existent checker module path is allowed.

M1.B completion notes:
1. All v0 registry handle keys in Section 6.5 now map to concrete module contracts.
2. Grouped handles (`ENTRYPOINT_RTDL_CORE_WORKER`, `ENTRYPOINT_DECISION_LANE_WORKER`) are explicitly expanded to their service/worker modes to prevent hidden launch ambiguity.
3. `platform_conformance.cli` remains an Obs/Gov support CLI but is not part of the registry entrypoint-handle closure set for M1.B.

## M1.C Provenance and Evidence Contract
Goal:
- make packaging output auditable and replayable.

Tasks:
1. Pin required provenance fields:
   - image tag,
   - image digest,
   - source commit SHA,
   - build timestamp,
   - operator/build actor.
2. Pin P(-1) evidence artifact location and naming pattern.
3. Define acceptance criteria for provenance consistency checks.

DoD:
- [x] Provenance field set is complete.
- [x] Evidence path contract is pinned and run-scoped.
- [x] Mismatch handling is fail-closed.

M1.C provenance contract freeze:
1. P(-1) provenance required fields are pinned:
   - `phase_id = "P(-1)"`
   - `platform_run_id` (same value that is later used in P1 run header)
   - `written_at_utc` (field name aligned to `FIELD_WRITTEN_AT_UTC`)
   - `image_tag` field name aligned to handle `IMAGE_TAG_EVIDENCE_FIELD`
   - `image_digest` field name aligned to handle `IMAGE_DIGEST_EVIDENCE_FIELD`
   - `git_sha` field name aligned to handle `IMAGE_GIT_SHA_EVIDENCE_FIELD`
   - `build_completed_at_utc`
   - `build_actor`
2. P(-1) provenance must include deterministic source pointers:
   - `ecr_repo_uri` (aligned to `ECR_REPO_URI`)
   - `image_reference_mode` (aligned to `IMAGE_REFERENCE_MODE`)
   - `dockerfile_path` (aligned to `IMAGE_DOCKERFILE_PATH`)
   - `build_path` (aligned to `IMAGE_BUILD_PATH`)
3. P(-1) provenance must include digest integrity anchors:
   - `oci_digest_algo` (expected `sha256`)
   - `oci_digest_value` (same value as `image_digest`)

M1.C evidence path contract (run-scoped):
1. Canonical run-scoped packaging provenance object:
   - `s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<platform_run_id>/P(-1)/packaging_provenance.json`
   - pattern alignment: `EVIDENCE_PHASE_PREFIX_PATTERN` with `phase_id="P(-1)"`.
2. Run-header mirror requirement:
   - `s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<platform_run_id>/run.json` (aligned to `EVIDENCE_RUN_JSON_KEY`) must contain:
     - image provenance fields (`image_tag`, `image_digest`, `git_sha`),
     - config digest field name aligned to `CONFIG_DIGEST_FIELD` once P1 writes run pinning payload.
3. P(-1) PASS evidence is not complete unless both are true:
   - packaging provenance object exists under phase prefix,
   - `run.json` carries matching image provenance values after P1 commit.

M1.C mismatch handling (fail-closed):
1. ECR mismatch:
   - if `image_tag` does not resolve to recorded `image_digest`, fail P(-1) and block M1 closure.
2. Provenance mismatch:
   - if `packaging_provenance.json` and `run.json` image fields differ, fail P1 gate progression until reconciled.
3. Git mismatch:
   - if `git_sha` in provenance does not match immutable tag pattern payload, fail P(-1).
4. Missing evidence:
   - if phase provenance object is missing from run-scoped path, treat packaging as not committed (no green progression).

M1.C validation method (build-go pass):
1. Resolve immutable image ref in ECR and capture digest.
2. Write `packaging_provenance.json` under `P(-1)` phase prefix for the intended `platform_run_id`.
3. During P1 run-header write, enforce exact image provenance field equality against packaging artifact.
4. Record PASS only when equality and path-existence checks pass.

## M1.D Security and Secret Injection Contract
Goal:
- enforce production-like secret posture from the first packaged phase.

Tasks:
1. Confirm no runtime secrets are embedded in image layers.
2. Pin runtime secret sources (SSM/env injection) and ownership.
3. Define guard checks for secret leakage in build-go pass.

DoD:
- [ ] No-baked-secrets policy is explicit and testable.
- [ ] Runtime secret source contract is pinned.
- [ ] Leakage check requirements are documented for execution pass.

## M1.E Build Command Surface and Reproducibility
Goal:
- remove ad hoc build behavior before execution.

Tasks:
1. Pin canonical build/push command surfaces for build-go execution.
2. Pin required inputs/env handles for those commands.
3. Pin retry/failure posture for build and push failures.

DoD:
- [ ] Canonical command surface is defined (no alternative ad hoc path).
- [ ] Required inputs are explicitly listed.
- [ ] Failure handling is fail-closed and documented.

## M1.F Exit Readiness Review
Goal:
- confirm M1 is ready to execute and close when build-go is granted.

Tasks:
1. Review M1 checklist completeness.
2. Confirm no unresolved ambiguity remains in packaging, entrypoints, provenance, or secrets.
3. Prepare execution handoff statement for M1 build-go pass.

DoD:
- [ ] M1 deliverables checklist complete.
- [ ] No unresolved contract ambiguity remains.
- [ ] Build-go handoff statement prepared.

## 6) M1 Completion Checklist
- [x] M1.A complete
- [x] M1.B complete
- [x] M1.C complete
- [ ] M1.D complete
- [ ] M1.E complete
- [ ] M1.F complete

## 7) Risks and Controls
R1: image/entrypoint mismatch discovered late  
Control: full matrix completion before build-go.

R2: provenance gaps undermine reproducibility claims  
Control: pinned provenance field set + evidence path contract.

R3: secret leakage during packaging  
Control: explicit no-baked-secrets policy + leakage checks in execution pass.

R4: ad hoc command drift  
Control: canonical build command surface pinned before execution.

## 8) Exit Criteria
M1 can be marked `DONE` only when:
1. all checklist items in Section 6 are complete,
2. build-go execution evidence is produced and validated,
3. main plan M1 checklist and DoD are complete,
4. user approves progression to M2 activation planning.

Note:
- This file does not change phase status.
- Status transition is made only in `platform.build_plan.md`.
