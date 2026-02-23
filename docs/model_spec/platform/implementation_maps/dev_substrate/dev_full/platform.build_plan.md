# Dev Substrate Build Plan (dev_full)
_Track: dev_min certified baseline -> dev_full full-platform managed substrate_
_Last updated: 2026-02-23_

## 0) Purpose
This is the active execution plan for building `dev_full` from the certified `dev_min` baseline into a full-platform managed stack with:
- no laptop runtime compute,
- strict fail-closed phase gates,
- full-platform scope (Spine + Learning/Evolution),
- deploy/monitor/fail/recover/rollback/cost-control proof per lane,
- cost-to-outcome discipline (spend must map to explicit proof/decision outcomes).

This plan is progressive: detailed phase steps are expanded only when a phase becomes active.

## 1) Scope Lock
In scope:
- Control + Ingress
- RTDL
- Case + Labels
- Run/Operate + Obs/Gov
- Learning + Evolution (OFS/MF/MPR)

Out of scope for dev_full v0:
- multi-region active-active,
- compliance program expansion beyond engineering controls.

## 2) Authority and Precedence
Execution authority:
1. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
2. `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`
3. `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md` (spine baseline continuity)
5. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (spine semantic inheritance)

If drift appears:
- stop implementation,
- log drift severity/impact,
- repin authority before proceeding.

## 3) Global Success Criteria (Program DoD)
Program is complete only when all are true:
- `P(-1), P0..P17` close green in `dev_full` with blocker-free verdict.
- Full-platform proof matrix is complete for each lane (deploy/monitor/fail/recover/rollback/cost-control).
- Spine non-regression anchors remain green after learning activation (`P5`, `P8`, `P9`, `P10`, `P11`).
- Learning closure is complete (`P12..P15`) with rollback drill evidence.
- No laptop runtime compute is used.
- `P17` teardown/idle-safe closure is proven.
- Cost-to-outcome receipts exist for each executed phase.

## 4) Non-Negotiable Guardrails
- No unpinned handle usage.
- No local runtime fallback.
- No unresolved `PUBLISH_UNKNOWN` during green closure.
- No bypass of fail-closed gates.
- No phase advancement without required evidence artifacts.
- No spend-only progress: phase spend without material outcome is blocked.
- Production-pattern law is binding: managed-service-first, no local/toy substitutes for pinned lanes without explicit authority repin.
- Law reference: `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md` Section `7.6` is mandatory for all `dev_full` phase decisions and closures.

## 5) Progressive Elaboration Method
Rules:
- Only one plan phase may be `ACTIVE` at a time.
- A phase cannot start until previous phase is `DONE` (unless explicit controlled exception is pinned).
- Each active phase must define:
  - entry criteria,
  - implementation lanes,
  - explicit DoD checklist,
  - rollback/rerun posture,
  - evidence contract,
  - phase spend envelope + expected outcomes.
- Future phases remain gate-level until activated.

Statuses:
- `NOT_STARTED`
- `ACTIVE`
- `DONE`
- `BLOCKED`

## 6) Phase Roadmap (Canonical)
Canonical lifecycle key: `phase_id=P#` from dev_full runbook.

| Plan Phase | Canonical phase_id | Name | Status |
| --- | --- | --- | --- |
| M0 | pre-P(-1) | Mobilization + authority lock | DONE |
| M1 | P(-1) | Packaging readiness (image/provenance) | DONE |
| M2 | P0 | Substrate readiness (core/streaming/runtime/data_ml/ops) | DONE |
| M3 | P1 | Run pinning and orchestrator readiness | IN_PROGRESS |
| M4 | P2 | Spine runtime-lane readiness (managed-first) | NOT_STARTED |
| M5 | P3-P4 | Oracle readiness + ingest preflight | NOT_STARTED |
| M6 | P5-P7 | Control + Ingress closure | NOT_STARTED |
| M7 | P8-P10 | RTDL + Case/Labels closure | NOT_STARTED |
| M8 | P11 | Spine obs/gov closure + non-regression pack | NOT_STARTED |
| M9 | P12 | Learning input readiness | NOT_STARTED |
| M10 | P13 | OFS dataset closure | NOT_STARTED |
| M11 | P14 | MF train/eval closure | NOT_STARTED |
| M12 | P15 | MPR promotion/rollback closure | NOT_STARTED |
| M13 | P16-P17 | Full-platform verdict + teardown/idle-safe closure | NOT_STARTED |

---

## 6.1) Deep Phase Plan Routing
Per-phase deep planning docs follow:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M0.build_plan.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M1.build_plan.md`
- ...
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M13.build_plan.md`

Control rule:
- `platform.build_plan.md` is the only file allowed to change phase status.
- `platform.M*.build_plan.md` documents deep details and blockers but cannot independently advance status.

## 6.2) Phase Evidence Template (Pinned)
Each phase (M1..M13) must publish:
- plan phase + canonical `phase_id`
- `platform_run_id` (or `N/A` if not created yet)
- authority refs used
- entry gate result
- DoD gate result
- commit evidence artifact list
- rollback/retry note
- phase verdict (`PASS`/`FAIL`)
- cost envelope artifact path
- cost-to-outcome receipt path
- operator + UTC timestamp

## 7) Phase Status Detail

## M0 - Mobilization + Authority Lock
Status: `DONE`

Objective:
- lock dev_full authority and phase-governance so implementation can start without hidden prerequisites or naming drift.

Entry criteria:
- dev_full design authority exists and stack pins are set.
- dev_full run-process authority exists.
- dev_full handles registry exists.
- dev_min is treated as certified baseline (reference only; no scope-mixing).

M0 prerequisite lanes (M0.PR*, mandatory):
1. `M0.PR0` baseline separation check:
   - `dev_min` track remains closed/isolated,
   - `dev_full` has independent authority set.
2. `M0.PR1` authority-trio existence check:
   - `dev-full_managed-substrate_migration.design-authority.v0.md`
   - `dev_full_platform_green_v0_run_process_flow.md`
   - `dev_full_handles.registry.v0.md`
3. `M0.PR2` vocabulary/pin alignment check:
   - stack pins (managed-first runtime: MSK+Flink, API Gateway/Lambda/DynamoDB, selective EKS, S3/Aurora/Redis/Databricks/SageMaker/MLflow/MWAA/Step Functions),
   - canonical phase IDs (`P(-1)..P17`),
   - topic set continuity and owner boundaries,
   - production-pattern adoption law + Oracle Store seating contract.
4. `M0.PR3` fail-closed open-handle isolation:
   - `TO_PIN` set exists in one explicit section,
   - no hidden unresolved handles outside that set.
5. `M0.PR4` cost-to-outcome rule continuity:
   - policy, run-process, and handle docs all include matching phase envelope/receipt posture.
6. `M0.PR5` deep-plan control surface:
   - `platform.M0.build_plan.md` exists and carries execution-grade DoD lanes.

Implementation tasks:
1. `M0.A` authority freeze and precedence validation.
2. `M0.B` planning topology lock (status ownership + deep-plan routing discipline).
3. `M0.C` authority alignment matrix:
   - stack pins, phase IDs, topic ownership, cost-to-outcome surfaces.
4. `M0.D` lock materialization backlog:
   - classify `TO_PIN` handles by dependency order (`identity`, `network`, `data`, `ops`).
5. `M0.E` exit-readiness and M1 transition pin:
   - status owner rule,
   - required M0 closure artifacts,
   - explicit go/no-go criteria.

M0 DoD checklist:
- [x] `M0.PR0`..`M0.PR5` all satisfied and evidenced.
- [x] Authority trio validated without unresolved contradictions.
- [x] `TO_PIN` list accepted as fail-closed materialization backlog with dependency ordering.
- [x] Deep M0 plan exists and is execution-grade (`platform.M0.build_plan.md`).
- [x] M1 transition protocol is pinned with explicit go/no-go checks.
- [x] M0 closure evidence recorded in impl map + logbook.

Rollback posture:
- Docs-only rollback is allowed before M1 starts.

Evidence outputs:
- M0 prerequisite closure notes in `platform.M0.build_plan.md`
- M0 authority alignment notes in `platform.M0.build_plan.md`
- M0 TO_PIN dependency backlog notes in `platform.M0.build_plan.md`
- M0 closure note in `platform.impl_actual.md`
- dated action record in `docs/logbook`

Phase exit:
- M0 can move to `DONE` only after all checklist items are checked.

M0 sub-phase progress:
- [x] `M0.A` authority freeze and precedence validation.
- [x] `M0.B` planning topology lock.
- [x] `M0.C` authority alignment matrix closure pass.
- [x] `M0.D` TO_PIN dependency backlog lock.
- [x] `M0.E` exit-readiness and M1 transition pin.

M0 closure snapshot:
- M0 DoD checklist is fully green.
- All M0 sub-phases `A..E` are complete.
- Handoff to M1 planning is explicitly approved by USER.

M0 revisit snapshot (authority repin pass):
- [x] M0 prerequisites revalidated after managed-first authority repin.
- [x] Vocabulary/pin alignment updated for MSK+Flink + API edge + selective EKS posture.
- [x] No new M0 execution-risk contradiction detected; M0 remains `DONE`.

---

## 8) Phase Plan Stubs (M1..M13)
These are master-plan stubs for all `M#` phases so execution has explicit intent before deep-plan expansion.

## M1 - Packaging Readiness
Status: `DONE`

Objective:
- close `P(-1)` with immutable image and provenance evidence.

Entry gate:
- M0 is `DONE`.
- required image/release handles are resolved.

M1 planning posture:
- M1 planning and execution closure is complete.
- `M1-B1` (`ECR_REPO_URI`) is resolved; handle is now materialized.
- `M1.A` has been expanded to execution-grade contract detail in the deep plan (strategy, boundary, blockers, evidence).
- `M1.B` execution is closed (`PASS`); `ENTRYPOINT_MPR_RUNNER` mapping is now concrete and `M1-B2` is closed.
- `M1.C` execution is closed (`PASS`); immutable digest and provenance evidence are emitted for `platform_20260222T194849Z` and `M1-B3` is closed.
- `M1.D` execution is closed (`PASS`) on managed CI run `22284273953`; required security artifacts are emitted and `M1-B4` is closed.
- `M1.E` execution is closed (`PASS`) with coherent consolidated closure pack `m1e_20260222T200909Z`; `M1-B5` is closed and M2 entry-gate readiness is true.
- M1 revisit after managed-first repin:
  - container/provenance closure remains valid for custom-runtime lanes.
  - managed runtime non-container artifact surfaces (Flink app package + IG Lambda package) are now explicitly tracked under M2 runtime/streaming materialization and are not silently assumed by M1.

Planned lanes:
- build, security/provenance, release evidence.

DoD anchors:
- [x] immutable digest captured.
- [x] entrypoint contract validated.
- [x] release evidence bundle committed.

Deep plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M1.build_plan.md`

M1 sub-phase progress:
- [x] `M1.A` image contract freeze.
- [x] `M1.B` entrypoint matrix closure.
- [x] `M1.C` provenance/evidence contract closure.
- [x] `M1.D` security/secret-injection contract closure.
- [x] `M1.E` build-go transition and blocker adjudication.

## M2 - Substrate Readiness
Status: `DONE`

Objective:
- close `P0` by materializing core/streaming/runtime/data_ml/ops stacks.
 - prove `M0..M2` production-pattern conformance (managed-first surfaces, Oracle read-only seating, lifecycle policy enforcement).

Entry gate:
- M1 is `DONE`.
- state backend and lock table reachable.

Planned lanes:
- Terraform apply/destroy viability, IAM/secret conformance, budget surface.

M2 planning posture:
- M2 deep-plan authority is now materialized at `platform.M2.build_plan.md`.
- M2 is expanded to execution-grade coverage across `M2.A..M2.J`.
- Active blocker lane for phase entry remains `M2-B*` and will be adjudicated during execution.
- `M2.A` is now expanded to execution-grade backend/lock checks with explicit fail-closed blocker taxonomy (`M2A-B*`).
- `M2.A` execution is now closed green with deterministic evidence:
  - `runs/dev_substrate/dev_full/m2/m2a_20260222T204011Z/m2a_execution_summary.json` (`overall_pass=true`, blockers=`0`).
- `M2.B` execution is now closed green with deterministic evidence:
  - `runs/dev_substrate/dev_full/m2/m2b_20260222T210207Z/m2b_execution_summary.json` (`overall_pass=true`, blockers=`0`).
- `M2.B` also published durable evidence:
  - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m2b_20260222T210207Z/`.
- `M2.C` is now expanded to execution-grade streaming planning (`M2C-B*`, command surface, MSK/schema evidence contracts).
- `M2C-B1` (skeleton-only streaming stack) is now cleared with bounded readiness evidence:
  - `runs/dev_substrate/dev_full/m2/m2c_b1_clear_20260222T212945Z/m2c_b1_clearance_summary.json` (`validate_exit=0`, `plan_exit=2`, `blocker_cleared=true`).
- `M2.C` execution is now closed (`PASS`) with full apply/evidence closure:
  - `runs/dev_substrate/dev_full/m2/m2c_20260222T222113Z/m2c_execution_summary.json` (`overall_pass=true`, blockers=`0`).
  - durable mirror: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m2c_20260222T222113Z/`.
- `M2.D` execution is now closed (`PASS`) with full precheck/evidence closure:
  - `runs/dev_substrate/dev_full/m2/m2d_20260222T230240Z/m2d_execution_summary.json` (`overall_pass=true`, blockers=`0`).
  - durable mirror: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m2d_20260222T230240Z/`.
- `M2.E` execution is now closed (`PASS`) with full runtime stack apply and conformance evidence:
  - `runs/dev_substrate/dev_full/m2/m2e_20260223T043248Z/m2e_execution_summary.json` (`overall_pass=true`, blockers=`0`).
  - durable mirror: `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m2e_20260223T043248Z/`.
- supplemental live API probe evidence was added after lambda path-normalization reconcile:
  - `runs/dev_substrate/dev_full/m2/m2e_20260223T043248Z/m2e_api_edge_live_probe_snapshot.json` (health `200`, ingest `202`).
- runtime-critical handles were materialized and pinned from M2.E outputs (`APIGW_IG_API_ID`, `EKS_CLUSTER_ARN`, runtime role-arn set).
- `M2.F` execution-grade lane remains the secret/role contract authority (`M2F-B*` taxonomy and evidence schema).
- `M2.G` execution is now closed (`PASS`):
  - `runs/dev_substrate/dev_full/m2/m2g_20260223T053551Z/m2g_execution_summary.json` (`overall_pass=true`).
- `M2.H` execution is now closed (`PASS`):
  - `runs/dev_substrate/dev_full/m2/m2h_20260223T053627Z/m2h_execution_summary.json` (`overall_pass=true`).
- `M2.F` rerun after `M2.G/M2.H` is now closed (`PASS`):
  - `runs/dev_substrate/dev_full/m2/m2f_20260223T053933Z/m2f_execution_summary.json`
  - result: `overall_pass=true`, blockers=`0`, `next_gate=M2.F_READY`.
- durable mirrors:
  - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m2g_20260223T053551Z/`
  - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m2h_20260223T053627Z/`
  - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m2f_20260223T053933Z/`
- `M2.I` execution is now closed (`PASS`) with bounded destroy/recover and residual-scan evidence:
  - `runs/dev_substrate/dev_full/m2/m2i_20260223T061220Z/m2i_execution_summary.json` (`overall_pass=true`, blockers=`0`).
- `M2.J` execution is now closed (`PASS`) with P0 rollup and M3-entry receipt:
  - `runs/dev_substrate/dev_full/m2/m2j_20260223T061612Z/m2j_execution_summary.json` (`overall_pass=true`, blockers=`0`, `next_gate=M2_DONE_M3_READY`).
- durable mirrors:
  - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m2i_20260223T061220Z/`
  - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m2j_20260223T061612Z/`
- M2 closure posture is now blocker-free and handoff-ready for M3.

DoD anchors:
- [x] all five stacks apply cleanly.
- [x] required handles are materialized or explicit blockers raised.
- [x] infra evidence snapshot committed.
- [x] production-pattern conformance snapshot (`managed-first + Oracle seating + lifecycle`) committed.

Deep plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M2.build_plan.md`

M2 sub-phase progress:
- [x] `M2.A` state backend and lock conformance.
- [x] `M2.B` core stack materialization.
- [x] `M2.C` streaming stack materialization.
- [x] `M2.D` topic/schema readiness precheck.
- [x] `M2.E` runtime stack and IAM role posture.
- [x] `M2.F` secret path contract and materialization checks.
- [x] `M2.G` data_ml stack materialization.
- [x] `M2.H` ops stack and cost guardrail surfaces.
- [x] `M2.I` destroy/recover rehearsal and residual scan.
- [x] `M2.J` P0 gate rollup and verdict.

## M3 - Run Pinning and Orchestrator Readiness
Status: `IN_PROGRESS`

Objective:
- close `P1` with deterministic run pinning and orchestration entry integrity.

Entry gate:
- M2 is `DONE`.

Planned lanes:
- run header/digest, lock identity, orchestrator wiring.
- authority/handles closure, deterministic run-id, durable evidence write, M4 handoff contract, rerun/reset and phase-budget discipline.

M3 planning posture:
- Deep plan has been created and expanded to execution-grade coverage across `M3.A..M3.J`.
- `M3.A` has been expanded with command-level verification catalog, blocker taxonomy, and evidence/closure contract.
- `M3.B` has been expanded with deterministic run-id laws, collision retry policy, verification command catalog, blocker taxonomy, and evidence/closure contract.
- `M3.C` has been expanded with canonical payload/digest decision pins, verification command catalog, blocker taxonomy, and evidence/closure contract.
- `M3.D` has been expanded with orchestrator-entry/run-lock decision pins, verification command catalog, blocker taxonomy, and evidence/closure contract.
- `M3.E` has been expanded with durable write-once evidence publication decision pins, verification command catalog, blocker taxonomy, and evidence/closure contract.
- `M3.F` has been expanded with runtime-scope export and M4 handoff decision pins, verification command catalog, blocker taxonomy, and evidence/closure contract.
- `M3.A` execution is now closed (`PASS`):
  - `runs/dev_substrate/dev_full/m3/m3a_20260223T174307Z/m3a_execution_summary.json` (`overall_pass=true`, blockers=`0`).
- `M3.A` blocker remediation closed:
  - `ROLE_TERRAFORM_APPLY_DEV_FULL` repinned from `TO_PIN` to active apply principal in registry.
  - `core -> streaming -> runtime` rematerialized; Step Functions orchestrator surface restored and verified.
- durable mirror:
  - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m3a_20260223T174307Z/`
- `M3.B` execution is now closed (`PASS`):
  - `runs/dev_substrate/dev_full/m3/m3b_20260223T184232Z/m3b_execution_summary.json` (`overall_pass=true`, blockers=`0`).
  - `platform_run_id=platform_20260223T184232Z`
  - `scenario_run_id=scenario_38753050f3b70c666e16f7552016b330`
- M3.B durable mirror:
  - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m3b_20260223T184232Z/`
- `M3.C` execution is now closed (`PASS`):
  - `runs/dev_substrate/dev_full/m3/m3c_20260223T185958Z/m3c_execution_summary.json` (`overall_pass=true`, blockers=`0`).
  - `config_digest=13f49c0d8e35264a1923844ae19f0e7bdba2b438763b46ae99db6aeeb0b8dc8b`
  - digest profile continuity: `m3b_seed_formula_v1`, `matches_m3b_seed_digest=true`
- `M3.C` blocker remediation trail retained:
  - failed attempt `m3c_20260223T185814Z` raised `M3C-B4` (digest profile mismatch) and is preserved as audit evidence.
- M3.C durable mirror:
  - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m3c_20260223T185958Z/`
- `M3.D` execution is now closed (`PASS`):
  - `runs/dev_substrate/dev_full/m3/m3d_20260223T191338Z/m3d_execution_summary.json` (`overall_pass=true`, blockers=`0`).
  - state machine resolution and role alignment both pass.
  - run-lock conflict check: running=`0`, conflicts=`0`.
- `M3.D` blocker remediation trail retained:
  - failed attempt `m3d_20260223T191145Z` raised `M3D-B1/M3D-B3` from local parser drift; rerun closed without runtime changes.
- M3.D durable mirror:
  - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m3d_20260223T191338Z/`
- `M3.E` execution is now closed (`PASS`):
  - `runs/dev_substrate/dev_full/m3/m3e_20260223T223411Z/m3e_execution_summary.json` (`overall_pass=true`, blockers=`0`).
  - run evidence objects committed:
    - `evidence/runs/platform_20260223T184232Z/run.json`
    - `evidence/runs/platform_20260223T184232Z/run_pin/run_header.json`
  - write-once guard and readback hash integrity both pass.
- M3.E durable mirror:
  - `s3://fraud-platform-dev-full-evidence/evidence/dev_full/run_control/m3e_20260223T223411Z/`

DoD anchors:
- [x] run pin artifact committed.
- [x] config digest committed.
- [x] run-scope identity checks pass.

Deep plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M3.build_plan.md`

M3 sub-phase progress:
- [x] `M3.A` authority and handle closure matrix.
- [x] `M3.B` deterministic run identity generation.
- [x] `M3.C` canonical payload and digest reproducibility.
- [x] `M3.D` orchestrator entry and lock identity readiness.
- [x] `M3.E` durable run evidence publication.
- [ ] `M3.F` runtime scope export and M4 handoff pack.
- [ ] `M3.G` rerun/reset discipline.
- [ ] `M3.H` phase budget and cost-outcome receipt.
- [ ] `M3.I` gate rollup and blocker adjudication.
- [ ] `M3.J` verdict and M4 entry marker.

## M4 - Spine Runtime-Lane Readiness (Managed-First)
Status: `NOT_STARTED`

Objective:
- close `P2` runtime-lane readiness for spine services under managed-first posture.

Entry gate:
- M3 is `DONE`.

Planned lanes:
- lane health (Flink/API edge/selective EKS), env conformance, telemetry heartbeat + correlation continuity.

DoD anchors:
- [ ] required spine runtime lanes are healthy.
- [ ] run-scope bindings are validated.
- [ ] runtime readiness snapshot committed.

Deep plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M4.build_plan.md`

## M5 - Oracle Readiness and Ingest Preflight
Status: `NOT_STARTED`

Objective:
- close `P3-P4` with oracle/stream-view validation and ingress boundary readiness.

Entry gate:
- M4 is `DONE`.

Planned lanes:
- oracle contract checks, stream-view checks, topic readiness, IG boundary preflight.

DoD anchors:
- [ ] required oracle outputs/manifest checks pass.
- [ ] ingress boundary + MSK readiness evidence committed.

Deep plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M5.build_plan.md`

## M6 - Control and Ingress Closure
Status: `NOT_STARTED`

Objective:
- close `P5-P7` end-to-end ingest streaming and commit semantics.

Entry gate:
- M5 is `DONE`.

Planned lanes:
- READY publication, WSP streaming, receipt/quarantine/offset closure.

DoD anchors:
- [ ] READY receipt committed.
- [ ] streaming active with bounded lag.
- [ ] ingest commit evidence complete.

Deep plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.build_plan.md`

## M7 - RTDL and Case/Labels Closure
Status: `NOT_STARTED`

Objective:
- close `P8-P10` for RTDL, decision chain, and case/label append lanes.

Entry gate:
- M6 is `DONE`.

Planned lanes:
- RTDL caught-up proof, decision/action/audit proof, case/label writer-boundary proof.

DoD anchors:
- [ ] RTDL core closure evidence is green.
- [ ] decision/action/audit triplet closure is green.
- [ ] case/label append closure is green.

Deep plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.build_plan.md`

## M8 - Spine Obs/Gov Closure
Status: `NOT_STARTED`

Objective:
- close `P11` and publish spine non-regression pack.

Entry gate:
- M7 is `DONE`.

Planned lanes:
- run report/reconciliation, governance append closure, non-regression anchors.

DoD anchors:
- [ ] spine run report committed.
- [ ] governance closure marker committed.
- [ ] non-regression pack committed.

Deep plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M8.build_plan.md`

## M9 - Learning Input Readiness
Status: `NOT_STARTED`

Objective:
- close `P12` with anti-leakage and replay-basis pinning.

Entry gate:
- M8 is `DONE`.

Planned lanes:
- learning input contract, as-of label policy, replay basis checks.

DoD anchors:
- [ ] anti-leakage checks pass.
- [ ] learning input readiness snapshot committed.

Deep plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M9.build_plan.md`

## M10 - OFS Dataset Closure
Status: `NOT_STARTED`

Objective:
- close `P13` with immutable dataset manifest, fingerprint, and Iceberg table-commit evidence.

Entry gate:
- M9 is `DONE`.

Planned lanes:
- Databricks dataset build, Iceberg (Glue catalog) table commit, quality gates, rollback recipe.

DoD anchors:
- [ ] OFS manifest committed.
- [ ] dataset fingerprint committed.
- [ ] Iceberg table/metadata commit receipt committed.
- [ ] OFS rollback recipe committed.

Deep plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M10.build_plan.md`

## M11 - MF Train/Eval Closure
Status: `NOT_STARTED`

Objective:
- close `P14` with reproducible training/evaluation and candidate bundle evidence.

Entry gate:
- M10 is `DONE`.

Planned lanes:
- SageMaker runs, MLflow lineage, eval gates, rollback/safe-disable path.

DoD anchors:
- [ ] MF eval report committed.
- [ ] candidate bundle receipt committed.
- [ ] rollback/safe-disable evidence committed.

Deep plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M11.build_plan.md`

## M12 - MPR Promotion/Rollback Closure
Status: `NOT_STARTED`

Objective:
- close `P15` promotion corridor with rollback drill evidence.

Entry gate:
- M11 is `DONE`.

Planned lanes:
- promotion gate checks, rollback drill, active-bundle compatibility checks.

DoD anchors:
- [ ] promotion receipt committed.
- [ ] rollback drill report committed.
- [ ] active-bundle compatibility checks green.

Deep plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M12.build_plan.md`

## M13 - Final Verdict and Teardown Closure
Status: `NOT_STARTED`

Objective:
- close `P16-P17` with full-platform verdict and idle-safe cost closure.

Entry gate:
- M12 is `DONE`.

Planned lanes:
- full source matrix aggregation, six-proof matrix check, teardown residual scan, cost closure.

DoD anchors:
- [ ] final verdict bundle committed.
- [ ] teardown residual scan clean or accepted with explicit waiver.
- [ ] cost-to-outcome receipt and cost snapshot committed.

Deep plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M13.build_plan.md`

## 9) Cost-to-Outcome Operating Rule (Execution Binding)
For every active phase:
1. Publish a phase spend envelope before execution.
2. Publish phase cost-to-outcome receipt at closure.
3. Block advancement if spend occurred without material proof/decision outcome.
4. Maintain daily cross-platform cost posture during active execution windows.

This rule is binding for all phases M1..M13.

## 10) Branch and Change Safety
- No branch-history operations without explicit USER branch-governance confirmation.
- No cross-branch execution improvisation.
- No destructive git commands.

## 11) Next Action
- Continue active phase `M2` by executing `M2.F` secret path contract and materialization checks.
