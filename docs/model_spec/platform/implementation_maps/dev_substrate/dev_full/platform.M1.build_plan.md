# Dev Substrate Deep Plan - M1 (P(-1) Packaging Readiness)
_Status source of truth: `platform.build_plan.md`_
_This document provides deep planning detail for M1._
_Last updated: 2026-02-22_

## 0) Purpose
M1 defines and closes the dev_full packaging contract for `P(-1)`:
- reproducible image build,
- full-platform entrypoint coverage (Spine + Learning/Evolution),
- immutable provenance evidence,
- fail-closed secret posture.

## 1) Authority Inputs
Primary:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.build_plan.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` (`P(-1)`)
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` (image/ECR/entrypoint handles)
4. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

Supporting:
1. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.impl_actual.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/dev_min/platform.M1.build_plan.md` (structure reference only)

## 2) Scope Boundary for M1
In scope:
1. Image contract freeze for dev_full.
2. Full-platform entrypoint matrix (spine + OFS + MF + MPR).
3. Immutable provenance/evidence contract for `P(-1)`.
4. Secret handling and packaging security posture.
5. Build-go transition protocol and execution blockers.

Out of scope:
1. Terraform substrate execution (`M2`).
2. Runtime daemon execution (`M4+`).
3. Learning runtime execution (`M9+`).

## 3) M1 Deliverables
1. Pinned image contract for dev_full and explicit content boundary.
2. Complete entrypoint matrix with deterministic invocation contracts.
3. Provenance evidence contract for `P(-1)` and run-level linkage rules.
4. Security/secret-injection contract with fail-closed checks.
5. Build-go protocol with explicit blockers and no-go conditions.

## 4) Execution Gate for This Phase
Current posture:
1. `M1` is `ACTIVE` for planning.

Execution block:
1. Build execution is blocked until planning lanes `M1.A..M1.E` are closed.
2. Build execution is hard-blocked if `ECR_REPO_URI` is unresolved (`M1-B1` from M0.D). Current status: `RESOLVED` (2026-02-22).
3. Build execution requires explicit USER command to proceed.

## 5) Work Breakdown (Deep)

## M1.A Image Contract Freeze (dev_full)
Goal:
- lock the packaging strategy and image boundary for full-platform runtime.

Tasks:
1. Confirm image strategy (`single image` vs decomposition) for dev_full v0 and rationale.
2. Pin authoritative image reference mode (immutable-first).
3. Pin image content boundary (required includes/excludes) for dev_full runtime.
4. Ensure learning-plane entrypoints are represented in package surface.
5. Define M1.A closure evidence artifacts and fail-closed blockers.

DoD:
- [x] image strategy is explicit and authority-aligned.
- [x] immutable tag/digest posture is explicit.
- [x] content boundary is explicit and auditable.
- [x] no local-only/runtime-irrelevant payloads are in authoritative build context.
- [x] M1.A blocker set is empty or explicitly carried as no-go for build execution.

M1.A planning precheck (decision completeness):
1. `ECR_REPO_URI` is now materialized; historical `M1-B1` blocker is closed.
2. M1.A closure requires contract pinning only; image build proof is executed later in M1 build-go lane.

M1.A image strategy contract (planned):
1. Strategy for dev_full v0 is `single platform image` with multi-entrypoint runtime modes.
2. Rationale:
   - preserves deterministic parity with dev_min closure model while adding learning entrypoints,
   - minimizes release drift across lanes before runtime stabilization in M2-M13,
   - keeps rollback semantics simple (one immutable digest across all services/jobs).
3. Decomposition policy:
   - multi-image split is explicitly out of scope for M1 and requires repin in design authority + handles registry before adoption.

M1.A immutable image reference posture (planned):
1. Authoritative mode: `IMAGE_REFERENCE_MODE = "immutable_preferred"` from handles registry.
2. Authoritative tag: `IMAGE_TAG_GIT_SHA_PATTERN`.
3. Non-authoritative convenience tag: `IMAGE_TAG_DEV_FULL_LATEST` (operator convenience only; never closure evidence).
4. No phase closure may rely on mutable tags.

M1.A authoritative image content boundary (planned):
1. Required include set (explicit path allowlist):
   - `pyproject.toml`
   - `Dockerfile`
   - `src/fraud_detection/` (recursive)
   - `config/platform/` (recursive)
   - `docs/model_spec/platform/contracts/` (recursive)
   - `docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`
   - `docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml`
   - `docs/model_spec/data-engine/interface_pack/contracts/canonical_event_envelope.schema.yaml`
   - `docs/model_spec/data-engine/interface_pack/contracts/engine_invocation.schema.yaml`
   - `docs/model_spec/data-engine/interface_pack/contracts/engine_output_locator.schema.yaml`
   - `docs/model_spec/data-engine/interface_pack/contracts/gate_receipt.schema.yaml`
   - `docs/model_spec/data-engine/interface_pack/contracts/instance_proof_receipt.schema.yaml`
   - `docs/model_spec/data-engine/interface_pack/contracts/run_receipt.schema.yaml`
   - `docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml`
   - `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`
2. Explicit exclude set (must not be included in image context payload):
   - `packages/engine/src/engine/` and any other engine-runtime source trees
   - `runs/`, `data/`, `reference/`, `artefacts/`, `scratch_files/`
   - `.git/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
   - `docs/logbook/`, `docs/tmp/`
   - `infra/terraform/` and infra-local helper trees not required by runtime image execution
   - `.env`, `.env.*`, ad hoc credential/token files
3. Build-context law:
   - broad `COPY . .` packaging posture is prohibited for M1 execution,
   - Dockerfile copy instructions must map to explicit include surfaces only,
   - `.dockerignore` must enforce exclude set before build-go.

M1.A entrypoint-surface coverage requirement (planned):
1. Packaging surface must include all runtime modules for:
   - Spine (`SR`, `WSP`, `IG`, RTDL workers, decision workers, CM/LS, reporter),
   - Learning (`OFS`, `MF`, `MPR`) via the registry entrypoint handles.
2. M1.A does not validate invocation behavior; invocation validation remains in `M1.B`.

M1.A closure blockers (planning):
1. `M1A-B1`: image strategy ambiguity (single vs split) not explicitly pinned.
2. `M1A-B2`: include/exclude manifest incomplete or contains runtime-irrelevant payloads.
3. `M1A-B3`: learning entrypoint surfaces absent from package contract.
4. `M1A-B4`: Docker build context policy allows broad repo ingestion.

M1.A evidence contract (planned):
1. `image_contract_manifest.json` under `EVIDENCE_PHASE_PREFIX_PATTERN` with `phase_id="P(-1)"`.
2. `build_context_allowlist_check.json` proving include/exclude validation results.
3. `dockerignore_conformance_receipt.json` proving excluded high-volume/secret surfaces are blocked.

M1.A execution checks and closure (2026-02-22):
1. Docker context conformance checks:
   - `Dockerfile` copy surfaces are explicit and bounded to the M1.A include contract.
   - no broad repo-ingestion instruction (`COPY . .` / `ADD .`) remains.
   - `.dockerignore` remains default-deny with explicit allowlist reopen rules.
2. Drift remediation performed:
   - removed non-referenced schema surfaces from packaging boundary:
     - `docs/model_spec/data-engine/interface_pack/layer-1/specs/contracts/1A/schemas.layer1.yaml`
     - `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.layer3.yaml`
   - remediation aligned runtime packaging to the pinned M1.A include contract.
3. Required include-path existence check:
   - all pinned include paths in M1.A contract were verified present in workspace.
4. Learning surface packaging check:
   - learning-plane source modules are included by `COPY src/fraud_detection` packaging surface,
   - `ENTRYPOINT_OFS_RUNNER`, `ENTRYPOINT_MF_RUNNER`, `ENTRYPOINT_MPR_RUNNER` remain pinned in handles registry for M1.B invocation-matrix closure.

M1.A blocker adjudication (closure):
1. `M1A-B1` image strategy ambiguity: CLOSED.
2. `M1A-B2` include/exclude manifest incompleteness: CLOSED.
3. `M1A-B3` learning entrypoint surfaces absent from package contract: CLOSED.
4. `M1A-B4` broad repo ingestion policy: CLOSED.

M1.A verdict:
1. `PASS` (planning+conformance closure complete).
2. M1 phase remains `ACTIVE`; `M1-B1` is now closed and no longer blocks M1 build-go.

## M1.B Entrypoint Matrix Closure
Goal:
- prove packaging surface can start all required execution modes.

Tasks:
1. Enumerate entrypoints for all required lanes:
   - spine (`SR`, `WSP`, `IG`, RTDL workers, Case/Labels, reporter),
   - learning (`OFS`, `MF`, `MPR` dispatch/runtime hooks).
2. Map each to deterministic invocation contract (module + required args).
3. Define validation method for build-go pass (`--help`/dry invocation contracts).
4. Fail-closed unresolved handle-to-module mappings before M1 closure.

DoD:
- [x] matrix covers all required handles in registry.
- [x] each entrypoint has deterministic invocation contract.
- [x] validation method is pinned and reproducible.

M1.B planning precheck (decision completeness):
1. `M1-B1` (`ECR_REPO_URI`) is closed; matrix closure remains independent from build execution.
2. Matrix closure requires every registry `ENTRYPOINT_*` handle to resolve to a concrete runtime invocation contract.
3. Planning-time unresolved mapping (`ENTRYPOINT_MPR_RUNNER`) is now closed by concrete module implementation in this execution lane.

M1.B entrypoint matrix (planned, execution-grade):

| Handle key | Runtime mode | Deterministic invocation contract | Required args contract | Mapping status |
| --- | --- | --- | --- | --- |
| `ENTRYPOINT_ORACLE_STREAM_SORT` | Oracle stream-sort job | `python -m fraud_detection.oracle_store.stream_sort_cli` | `--profile <path> --engine-run-root <s3://...> --scenario-id <id>` | READY |
| `ENTRYPOINT_ORACLE_CHECKER` | Oracle checker job | `python -m fraud_detection.oracle_store.cli` | `--profile <path> --engine-run-root <s3://...>` (`--scenario-id`/`--output-ids` optional by phase posture) | READY |
| `ENTRYPOINT_SR` | Scenario runner control task | `python -m fraud_detection.scenario_runner.cli run` | `--wiring <path> --policy <path> --run-equivalence-key <key> --manifest-fingerprint <fp> --parameter-hash <hash> --seed <int> --window-start <iso> --window-end <iso>` | READY |
| `ENTRYPOINT_WSP` | World streamer producer task | `python -m fraud_detection.world_streamer_producer.cli` | `--profile <path>` (`--engine-run-root`, `--scenario-id`, `--output-ids`, `--max-events` optional overrides) | READY |
| `ENTRYPOINT_IG_SERVICE` | IG daemon/service | `python -m fraud_detection.ingestion_gate.service` | `--profile <path>` (`--host`/`--port` optional overrides) | READY |
| `ENTRYPOINT_RTDL_CORE_WORKER` | ArchiveWriter worker | `python -m fraud_detection.archive_writer.worker` | `--profile <path>` (`--once` optional) | READY |
| `ENTRYPOINT_RTDL_CORE_WORKER` | IEG query service | `python -m fraud_detection.identity_entity_graph.service` | `--profile <path>` (`--host`/`--port` optional overrides) | READY |
| `ENTRYPOINT_RTDL_CORE_WORKER` | OFP projector worker | `python -m fraud_detection.online_feature_plane.projector` | `--profile <path>` (`--once` optional) | READY |
| `ENTRYPOINT_RTDL_CORE_WORKER` | CSFB intake worker | `python -m fraud_detection.context_store_flow_binding.intake` | `--policy <path>` (`--once`/`--replay-manifest` optional) | READY |
| `ENTRYPOINT_DECISION_LANE_WORKER` | DL worker | `python -m fraud_detection.degrade_ladder.worker` | `--profile <path>` (`--once` optional) | READY |
| `ENTRYPOINT_DECISION_LANE_WORKER` | DF worker | `python -m fraud_detection.decision_fabric.worker` | `--profile <path>` (`--once` optional) | READY |
| `ENTRYPOINT_DECISION_LANE_WORKER` | AL worker | `python -m fraud_detection.action_layer.worker` | `--profile <path>` (`--once` optional) | READY |
| `ENTRYPOINT_DECISION_LANE_WORKER` | DLA worker | `python -m fraud_detection.decision_log_audit.worker` | `--profile <path>` (`--once` optional) | READY |
| `ENTRYPOINT_CASE_TRIGGER_WORKER` | CaseTrigger worker | `python -m fraud_detection.case_trigger.worker` | `--profile <path>` (`--once` optional) | READY |
| `ENTRYPOINT_CM_SERVICE` | CM worker | `python -m fraud_detection.case_mgmt.worker` | `--profile <path>` (`--once` optional) | READY |
| `ENTRYPOINT_LS_SERVICE` | LS worker | `python -m fraud_detection.label_store.worker` | `--profile <path>` (`--once` optional) | READY |
| `ENTRYPOINT_ENV_CONFORMANCE_WORKER` | Env conformance worker | `python -m fraud_detection.platform_conformance.worker` | `--local-parity-profile <path> --dev-profile <path> --prod-profile <path>` (`--required-platform-run-id` optional, `--once` optional) | READY |
| `ENTRYPOINT_REPORTER` | Obs/Gov reporter worker | `python -m fraud_detection.platform_reporter.worker` | `--profile <path>` (`--required-platform-run-id` optional, `--once` optional) | READY |
| `ENTRYPOINT_OFS_RUNNER` | OFS worker/launcher | `python -m fraud_detection.offline_feature_plane.worker` | `--profile <path> run` (`--once` optional) | READY |
| `ENTRYPOINT_MF_RUNNER` | MF worker/launcher | `python -m fraud_detection.model_factory.worker` | `--profile <path> run` (`--once` optional) | READY |
| `ENTRYPOINT_MPR_RUNNER` | MPR promotion corridor runner | `python -m fraud_detection.learning_registry.worker` | `--profile <path> run` (`--once` optional); lifecycle checks via `promote --event-path <json>` and `rollback-drill --event-path <json>` | READY |

M1.B validation method (pinned for build-go pass):
1. Handle-level argparse smoke checks in image context:
   - run `python -m <module> --help` for non-subcommand workers/services,
   - run `python -m <module> <subcommand> --help` for subcommand CLIs (`SR`, `OFS`, `MF`).
2. Grouped-handle expansion is mandatory:
   - `ENTRYPOINT_RTDL_CORE_WORKER` and `ENTRYPOINT_DECISION_LANE_WORKER` must validate all mapped workers/services, not a single representative command.
3. Validation result contract:
   - each matrix row must record `module`, `command`, `exit_code`, `stderr_summary`, and `status`.
4. Fail-closed criteria:
   - missing module, argparse failure, or unresolved handle mapping fails `M1.B`.
   - `M1.B` cannot close while any row remains `BLOCKED`.

M1.B execution checks and closure (2026-02-22):
1. Matrix run #1 (`PYTHONPATH` missing):
   - artifact: `runs/dev_substrate/dev_full/m1/m1b_entrypoint_validation_20260222T192558Z.json`
   - outcome: all rows failed with module-resolution launcher error.
   - remediation: rerun with explicit `PYTHONPATH=src` to test command contracts, not shell drift.
2. Matrix run #2 (`PYTHONPATH=src`):
   - artifact: `runs/dev_substrate/dev_full/m1/m1b_entrypoint_validation_20260222T192718Z.json`
   - outcome: `overall=PASS` for all entrypoint rows.
3. Subcommand validation checks:
   - artifact: `runs/dev_substrate/dev_full/m1/m1b_subcommand_validation_20260222T192734Z.json`
   - outcome: `overall=PASS` for `SR`, `OFS`, `MF`, and `MPR` subcommand help contracts.
4. MPR fail-closed command checks:
   - artifact: `runs/dev_substrate/dev_full/m1/m1b_mpr_command_checks_20260222T192755Z.json`
   - outcome: expected PASS/PASS/FAIL behavior confirmed for valid promote, valid rollback-drill, and invalid promote event-type case.

M1.B blocker adjudication:
1. `M1-B2` (entrypoint coverage incomplete): CLOSED.
2. `M1-B1` is closed by concrete handle materialization in the registry and AWS ECR.

M1-B1 resolution evidence (2026-02-22):
1. Registry handle materialized:
   - `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` (`ECR_REPO_URI` no longer `TO_PIN`).
2. AWS substrate evidence:
   - `runs/dev_substrate/dev_full/m1/m1b1_ecr_resolution_20260222T193300Z.json`.

## M1.C Provenance and Evidence Contract
Goal:
- make `P(-1)` output auditable and replay-safe.

Tasks:
1. Pin required provenance fields (`image_tag`, `image_digest`, `git_sha`, build metadata).
2. Map `P(-1)` evidence paths to run-scoped S3 handles.
3. Pin mismatch handling rules (`tag->digest`, digest mismatch, missing evidence).
4. Pin `P(-1)` -> `P1` run-linkage equality checks for immutable replay.

DoD:
- [x] provenance field set complete.
- [x] evidence paths and run-linkage contract explicit.
- [x] mismatch policy is fail-closed.

M1.C planning precheck (decision completeness):
1. `M1-B1` is closed (`ECR_REPO_URI` materialized).
2. `M1-B2` is closed (entrypoint matrix coverage complete).
3. `M1.C` closure remains required to clear `M1-B3` before M1 phase closure.

M1.C provenance contract (planned):
1. P(-1) provenance required fields:
   - `phase_id = "P(-1)"`
   - `platform_run_id` (same run identity used by P1 run pinning)
   - `written_at_utc` (aligned to `FIELD_WRITTEN_AT_UTC`)
   - `image_tag` (immutable tag from `IMAGE_TAG_GIT_SHA_PATTERN`)
   - `image_digest` (resolved OCI digest)
   - `git_sha` (source revision for immutable tag)
   - `build_driver` (aligned to `IMAGE_BUILD_DRIVER`)
   - `image_reference_mode` (aligned to `IMAGE_REFERENCE_MODE`)
   - `ecr_repo_uri` (aligned to `ECR_REPO_URI`)
   - `dockerfile_path` (aligned to `IMAGE_DOCKERFILE_PATH`)
   - `build_context_path` (aligned to `IMAGE_BUILD_CONTEXT_PATH`)
   - `build_completed_at_utc`
   - `build_actor`
2. Digest integrity anchors:
   - `oci_digest_algo = "sha256"`
   - `oci_digest_value = image_digest`
3. P(-1) metadata completeness:
   - include release metadata receipt refs and provenance metadata refs produced by build-go surface.

M1.C evidence path contract (run-scoped, planned):
1. Canonical phase prefix:
   - `s3://<S3_EVIDENCE_BUCKET>/` + `EVIDENCE_PHASE_PREFIX_PATTERN` with `phase_id="P(-1)"`.
2. Mandatory P(-1) evidence objects under phase prefix:
   - `packaging_provenance.json`
   - `image_digest_manifest.json`
   - `release_metadata_receipt.json`
3. P1 linkage surfaces:
   - run header at `RUN_PIN_PATH_PATTERN`
   - run summary at `EVIDENCE_RUN_JSON_KEY`
4. PASS condition for run-linkage:
   - `image_tag`, `image_digest`, and `git_sha` values in `run.json` must equal `packaging_provenance.json`,
   - `config_digest` must remain canonical in run pin payload (`CONFIG_DIGEST_FIELD`) and must not mutate image provenance fields.

M1.C mismatch policy (fail-closed, planned):
1. Tag-to-digest mismatch:
   - if immutable tag does not resolve to recorded `image_digest`, fail P(-1) closure.
2. Digest-format mismatch:
   - if `image_digest` is missing/empty or not `sha256:*`, fail closure.
3. Provenance object mismatch:
   - if `packaging_provenance.json`, `image_digest_manifest.json`, and run-header mirrors disagree, block P1 progression.
4. Missing evidence:
   - if any mandatory P(-1) evidence object is missing, treat packaging as uncommitted.
5. Mutable-tag misuse:
   - convenience tag (`IMAGE_TAG_DEV_FULL_LATEST`) cannot be used as closure evidence.

M1.C validation method (build-go lane, planned):
1. Resolve immutable tag in ECR and capture digest from AWS source-of-truth.
2. Write phase evidence objects under `P(-1)` evidence prefix.
3. Verify object existence/readability for all mandatory P(-1) evidence files.
4. Enforce equality checks across:
   - ECR resolved digest,
   - `packaging_provenance.json`,
   - `image_digest_manifest.json`,
   - `run.json`/run-header mirrors after P1.
5. Emit conformance artifact:
   - `provenance_consistency_checks.json` under P(-1) phase prefix with row-level PASS/FAIL and reason codes.

M1.C blocker adjudication contract (planned):
1. `M1-B3` remains active until:
   - provenance field contract is complete,
   - path/linkage contract is complete,
   - mismatch policy and validation contract are pinned and executable.
2. Any unresolved M1.C sub-blocker fails M1 closure:
   - `M1C-B1` incomplete provenance field contract,
   - `M1C-B2` ambiguous evidence path/linkage contract,
   - `M1C-B3` missing fail-closed mismatch policy,
   - `M1C-B4` incomplete validation artifact contract.

M1.C execution closure (2026-02-22):
1. Managed execution path selected:
   - `IMAGE_BUILD_DRIVER=github_actions` preserved.
   - attempted dedicated workflow dispatch (`dev_full_m1_packaging.yml`) was blocked by GitHub default-branch workflow discovery posture.
   - fail-closed fallback used: execute default-branch managed workflow (`dev_min_m1_packaging.yml`) against `ref=migrate-dev` with dev_full ECR handles.
2. Managed run evidence:
   - failed run (permission blocker): `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22284036943`
   - passing run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22284070905`
   - platform run id: `platform_20260222T194849Z`
3. Blocker remediation during execution:
   - root cause: OIDC role `GitHubAction-AssumeRoleWithAction` missing `ecr:InitiateLayerUpload` on `fraud-platform-dev-full`.
   - remediation: inline IAM policy `GitHubActionsEcrPushDevFull` added with repo-scoped ECR push/read actions.
4. Local evidence mirror (authoritative for this execution lane):
   - `runs/dev_substrate/dev_full/m1/m1c_20260222T195004Z/m1c_execution_snapshot.json`
   - phase evidence root:
     - `runs/dev_substrate/dev_full/m1/m1c_20260222T195004Z/evidence/runs/platform_20260222T194849Z/P(-1)/`
5. Required M1.C evidence objects present (PASS):
   - `packaging_provenance.json`
   - `image_digest_manifest.json`
   - `release_metadata_receipt.json`
   - `provenance_consistency_checks.json`
6. Conformance results:
   - ECR-resolved digest matches CI digest (`sha256:99aa504b127598d17d3ec33e9f7d78af6d37c24f8dddea47687821e9dcdc4f11`).
   - immutable tag contract satisfied (`git-<sha>` matches `git_sha`).
   - required provenance fields complete and normalized (`build_context_path` materialized).
7. P1 linkage rule posture:
   - run-pin equality checks are explicitly deferred-by-contract until `RUN_PIN_PATH_PATTERN` and `EVIDENCE_RUN_JSON_KEY` are materialized in `M3+`.
8. S3 evidence path posture:
   - canonical path contract remains pinned to `S3_EVIDENCE_BUCKET + EVIDENCE_PHASE_PREFIX_PATTERN`,
   - direct S3 upload deferred in M1 because dev_full evidence bucket materialization is a substrate lane concern (`M2`).
9. Drift-control follow-up:
   - manual IAM remediation (`GitHubActionsEcrPushDevFull`) must be codified in IaC during `M2` to avoid policy drift.

M1.C blocker adjudication (execution):
1. `M1C-B1` incomplete provenance field contract: CLOSED.
2. `M1C-B2` ambiguous evidence path/linkage contract: CLOSED.
3. `M1C-B3` missing fail-closed mismatch policy: CLOSED.
4. `M1C-B4` incomplete validation artifact contract: CLOSED.
5. `M1C-B5` managed workflow push permission gap: CLOSED (OIDC role policy remediated).

M1.C verdict:
1. `PASS` (execution closure complete).
2. Phase-level blocker `M1-B3` is now closed.

## M1.D Security and Secret Injection Contract
Goal:
- enforce production-like secret posture at packaging layer.

Tasks:
1. Pin no-baked-secret policy for image build.
2. Pin runtime secret source expectations (SSM/Secrets Manager handles).
3. Define packaging-time leakage checks (context lint + env policy).

DoD:
- [x] no-baked-secret policy explicit and testable.
- [x] runtime secret source contract explicit.
- [x] leak-check criteria defined for build-go.

M1.D planning precheck (decision completeness):
1. `M1-B1` (ECR handle) is closed and no longer blocks packaging execution.
2. `M1-B2` (entrypoint coverage) is closed and no longer blocks packaging execution.
3. `M1-B3` (provenance/evidence ambiguity) is closed in `M1.C`.
4. `M1-B4` remains the active blocker lane until security and secret-injection controls are executable and evidenced.

M1.D no-baked-secret policy contract (planned):
1. Hard prohibitions for `P(-1)` packaging surfaces:
   - no static cloud credentials in Dockerfile, workflow env blocks, or build args (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`),
   - no direct secret material injection through Docker `ARG`/`ENV`,
   - no secret files or dotenv payloads in build context (`.env*`, key files, token dumps),
   - no secret values in committed evidence artifacts.
2. Build identity posture:
   - build auth is OIDC-assumed role only (no static key mode),
   - secret backend posture is pinned to `SECRETS_BACKEND = "ssm_and_secrets_manager"`.
3. Packaging boundary posture:
   - build context must remain allowlist-bounded (`Dockerfile` + `.dockerignore` contract from `M1.A`),
   - broad context ingestion patterns that can reintroduce secret drift are prohibited.

M1.D runtime secret source contract (planned):
1. Runtime secret values are not packaged; only secret path references are allowed in image/runtime wiring contracts.
2. Required secret path handles (authoritative source = registry Section 11.3):
   - `/fraud-platform/dev_full/msk/bootstrap_brokers`
   - `/fraud-platform/dev_full/aurora/endpoint`
   - `/fraud-platform/dev_full/aurora/reader_endpoint`
   - `/fraud-platform/dev_full/aurora/username`
   - `/fraud-platform/dev_full/aurora/password`
   - `/fraud-platform/dev_full/redis/endpoint`
   - `/fraud-platform/dev_full/databricks/workspace_url`
   - `/fraud-platform/dev_full/databricks/token`
   - `/fraud-platform/dev_full/mlflow/tracking_uri`
   - `/fraud-platform/dev_full/sagemaker/model_exec_role_arn`
   - `/fraud-platform/dev_full/mwaa/webserver_url`
   - `/fraud-platform/dev_full/ig/api_key`
3. M1 scope boundary:
   - `M1.D` validates that path handles are pinned and referenced by name only,
   - path existence/materialization and runtime retrieval checks are executed in substrate/runtime lanes (`M2+`), not claimed by `M1`.

M1.D packaging-time leakage checks (planned):
1. Dockerfile policy checks:
   - fail if Dockerfile contains known secret key names in `ARG`/`ENV`,
   - fail if Dockerfile copies banned secret-file patterns.
2. Workflow policy checks:
   - fail if workflow exports static cloud credentials,
   - fail if secret values are echoed or persisted into evidence artifacts.
3. Build-context file checks:
   - fail if allowlist boundary is violated by secret-bearing files,
   - fail if banned secret extensions/patterns are present in image context.
4. Evidence payload checks:
   - fail if generated evidence objects include secret-value fields,
   - permit only handle refs, ARNs, and path identifiers.

M1.D fail-closed mismatch policy (planned):
1. Any discovered secret-in-image or secret-in-build-context finding blocks `P(-1)` closure.
2. Any static credential export posture in build-go blocks closure.
3. Any missing required secret-path handle in registry-to-plan mapping blocks closure.
4. Any evidence artifact containing plain secret values blocks closure and triggers remediation before rerun.

M1.D evidence contract (planned):
1. Mandatory `P(-1)` security artifacts:
   - `security_secret_injection_checks.json`
   - `secret_source_contract_receipt.json`
   - `build_context_secret_scan.json`
2. `security_secret_injection_checks.json` must include:
   - static credential rejection verdict,
   - Dockerfile secret-policy verdict,
   - workflow credential-policy verdict,
   - final pass/fail and blocker code.
3. `secret_source_contract_receipt.json` must include:
   - pinned secret backend value,
   - required secret-path handle list,
   - runtime-materialization deferral note (`M2+` conformance ownership).
4. `build_context_secret_scan.json` must include:
   - scanned root paths,
   - banned pattern set,
   - findings summary and pass/fail verdict.

M1.D validation method (build-go lane, planned):
1. Run static security policy checks in managed build lane before image push finalization.
2. Emit the three mandatory security artifacts under `P(-1)` evidence prefix.
3. Fail workflow if any security check returns `FAIL`.
4. Record blocker codes for deterministic rerun triage (`M1D-B*`).

M1.D blocker adjudication contract (planned):
1. `M1-B4` remains active until:
   - no-baked-secret policy is explicit and testable,
   - runtime secret-source contract is explicit,
   - leak-check criteria and artifacts are executable.
2. M1.D sub-blockers (fail-closed):
   - `M1D-B1`: Dockerfile/build-context secret injection risk unresolved.
   - `M1D-B2`: static credential rejection posture missing or bypassable.
   - `M1D-B3`: runtime secret source mapping incomplete (required handle set not represented).
   - `M1D-B4`: security evidence artifact contract incomplete or non-executable.
   - `M1D-B5`: security check failure in build-go execution.

M1.D execution closure (2026-02-22):
1. Managed execution carrier:
   - workflow id: `dev_min_m1_packaging` (executed on `ref=migrate-dev`).
   - security profile: `secret_contract_profile=dev_full`.
2. Authoritative pass run:
   - `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22284273953`
   - platform run id: `platform_20260222T200115Z`.
3. Managed step closure:
   - `Run M1.D security and secret-injection checks` completed `success` before build/push finalization.
4. Evidence artifact pack (CI download mirror):
   - `runs/dev_substrate/dev_full/m1/m1d_20260222T200233Z/m1-p-1-packaging-ci-evidence/`
   - includes mandatory M1.D artifacts:
     - `security_secret_injection_checks.json`
     - `secret_source_contract_receipt.json`
     - `build_context_secret_scan.json`
5. Security verdict highlights:
   - `security_secret_injection_checks.json`:
     - `verdict=PASS`,
     - blocker codes empty,
     - Dockerfile secret env/copy hits = `0`,
     - build-context findings = `0`.
   - `secret_source_contract_receipt.json`:
     - `secrets_backend=ssm_and_secrets_manager`,
     - required secret-path handle list count = `12`,
     - runtime materialization ownership explicitly deferred to `M2+`.
   - `build_context_secret_scan.json`:
     - scanned files count = `360`,
     - findings count = `0`,
     - summary pass = `true`.
6. Execution rollup snapshot:
   - `runs/dev_substrate/dev_full/m1/m1d_20260222T200233Z/m1d_execution_snapshot.json`
   - `overall_pass=true`, active blockers empty.

M1.D blocker adjudication (execution):
1. `M1D-B1` Dockerfile/build-context secret injection risk unresolved: CLOSED.
2. `M1D-B2` static credential rejection posture missing/bypassable: CLOSED.
3. `M1D-B3` runtime secret source mapping incomplete: CLOSED.
4. `M1D-B4` security evidence artifact contract incomplete/non-executable: CLOSED.
5. `M1D-B5` security check failure in build-go execution: CLOSED.

M1.D verdict:
1. `PASS` (execution closure complete).
2. Phase-level blocker `M1-B4` is now closed.

## M1.E Build-Go Transition and Blocker Adjudication
Goal:
- make M1 execution start deterministic and fail-closed.

Tasks:
1. Pin build-go preconditions and no-go conditions.
2. Resolve or explicitly carry blockers with severity.
3. Define closure evidence required to mark M1 `DONE`.

DoD:
- [ ] build-go checklist is explicit and complete.
- [ ] blocker register exists with clear owner/action.
- [ ] M1 closure evidence contract is explicit.

M1.E planning precheck (decision completeness):
1. `M1-B1` (`ECR_REPO_URI`) is closed.
2. `M1-B2` (entrypoint contract coverage) is closed.
3. `M1-B3` (provenance/evidence ambiguity) is closed.
4. `M1-B4` (security/secret-injection posture) is closed.
5. `M1-B5` remains the only active M1 blocker and is owned by this lane.

M1.E build-go preconditions (planned, mandatory):
1. Packaging identity and provenance surfaces remain pinned:
   - `IMAGE_BUILD_DRIVER=github_actions`
   - `IMAGE_REFERENCE_MODE=immutable_preferred`
   - `IMAGE_TAG_GIT_SHA_PATTERN` contract preserved (`git-{git_sha}`).
2. Managed workflow lane readiness:
   - default-branch dispatchable workflow id exists for packaging lane,
   - active-branch code path is targetable via `--ref`,
   - OIDC role for workflow has required ECR permissions for target repository.
3. Required `P(-1)` evidence objects are present and coherent:
   - `packaging_provenance.json`,
   - `image_digest_manifest.json`,
   - `release_metadata_receipt.json`,
   - `provenance_consistency_checks.json`,
   - `security_secret_injection_checks.json`,
   - `secret_source_contract_receipt.json`,
   - `build_context_secret_scan.json`.
4. Digest integrity posture:
   - ECR-resolved digest equals CI-recorded digest,
   - immutable tag resolves to same digest and same `git_sha`.
5. Security posture:
   - no secret findings in build-context scan,
   - no blocker codes in security checks,
   - `SECRETS_BACKEND=ssm_and_secrets_manager` in contract receipt.

M1.E no-go conditions (planned, fail-closed):
1. Any active `M1-B*` blocker remains unresolved.
2. Managed workflow cannot be dispatched/replayed under pinned driver posture.
3. Any required `P(-1)` evidence object missing/unreadable.
4. Any digest mismatch across ECR, provenance, and receipt surfaces.
5. Any security scan failure or secret leakage finding.
6. Any unresolved branch/workflow execution ambiguity that would force local-only fallback.

M1.E blocker register contract (planned):
1. Severity classes:
   - `S1` hard blocker: invalidates M1 closure immediately,
   - `S2` transition blocker: allows analysis but blocks handoff to M2,
   - `S3` advisory: must be recorded with rationale if accepted.
2. Required blocker fields:
   - `blocker_id`, `severity`, `owner_lane`, `detected_at_utc`, `evidence_ref`, `resolution_action`, `resolution_status`.
3. Lane-specific blockers for M1.E:
   - `M1E-B1`: build-go precondition set incomplete.
   - `M1E-B2`: workflow-dispatch path ambiguous under pinned driver posture.
   - `M1E-B3`: closure evidence bundle incomplete or inconsistent.
   - `M1E-B4`: unresolved cross-lane blocker carried without explicit acceptance.
   - `M1E-B5`: M1->M2 handoff gate ambiguity.

M1.E closure evidence contract (planned):
1. Required closure artifacts:
   - `m1_closure_blocker_register.json`
   - `m1_build_go_transition_receipt.json`
   - `m1_handoff_readiness_snapshot.json`
2. Artifact placement:
   - local mirror: `runs/dev_substrate/dev_full/m1/<execution_id>/`
   - canonical contract path (when evidence bucket materializes in M2): `EVIDENCE_PHASE_PREFIX_PATTERN` with `phase_id="P(-1)"`.
3. `m1_build_go_transition_receipt.json` minimum fields:
   - `phase_id`, `platform_run_id`, `image_tag`, `image_digest`, `git_sha`, `build_driver`, `workflow_run_id`, `workflow_run_url`, `transition_verdict`.
4. `m1_handoff_readiness_snapshot.json` minimum fields:
   - `m1_subphase_status` (`A..E`),
   - `active_blockers` list,
   - `m2_entry_gate_ready` boolean,
   - `notes` and explicit `fail_closed` flag.

M1.E validation method (planned):
1. Compile closure inputs from M1.A..M1.D execution artifacts and run metadata.
2. Evaluate no-go conditions and blocker severity matrix.
3. Emit closure artifacts with deterministic verdicts.
4. Mark M1 `DONE` only if:
   - `M1.E` verdict is `PASS`,
   - `M1-B5` is closed,
   - no residual `S1/S2` blockers remain.

M1.E execution boundary note (planned):
1. `M1.E` does not perform new image builds by default; it adjudicates build-go closure from existing managed evidence unless rerun is required for contradiction resolution.

## 6) Blocker Taxonomy (M1)
- `M1-B1`: `ECR_REPO_URI` unresolved (hard blocker for packaging execution) - `CLOSED` (2026-02-22).
- `M1-B2`: entrypoint coverage incomplete for required lanes - `CLOSED` (2026-02-22).
- `M1-B3`: provenance/evidence contract ambiguous or inconsistent - `CLOSED` (2026-02-22).
- `M1-B4`: secret posture incomplete or leakage checks undefined - `CLOSED` (2026-02-22).
- `M1-B5`: build-go transition remains ambiguous.

Any active `M1-B*` blocker prevents M1 execution closure.

## 7) M1 Completion Checklist
- [x] M1.A complete.
- [x] M1.B complete.
- [x] M1.C complete.
- [x] M1.D complete.
- [ ] M1.E complete.
- [ ] M1 blockers resolved or explicitly pinned for no-go.
- [ ] M1 closure note appended in implementation map.
- [ ] M1 action log appended in logbook.

## 8) Exit Criteria and Handoff
M1 is eligible for closure when:
1. all checklist items in Section 7 are complete,
2. no active execution blocker remains for `P(-1)` closure,
3. closure evidence is captured per `P(-1)` contract,
4. USER confirms progression to M2.

Handoff posture:
- M2 remains `NOT_STARTED` until M1 is marked `DONE` in master plan.
