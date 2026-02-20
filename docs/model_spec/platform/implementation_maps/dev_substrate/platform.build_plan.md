# Dev Substrate Migration Build Plan (Fresh Start)
_Track: local_parity -> dev_min managed substrate (Spine Green v0)_
_Last updated: 2026-02-19_

## 0) Purpose
This is the active execution plan for migrating the already-canonical local-parity Spine Green v0 flow into `dev_min` with:
- no laptop runtime compute,
- strict phase gates,
- fail-closed behavior,
- durable evidence for every phase,
- demo -> destroy cost posture.

This plan is intentionally progressive: we only expand detailed implementation steps when a phase becomes active.

## 1) Scope Lock
In scope for green migration baseline:
- Control + Ingress
- RTDL
- Case + Labels
- Run/Operate + Obs/Gov

Out of scope for this baseline:
- Learning/Registry (OFS/MF/MPR)

## 2) Authority and Precedence
Execution authority:
1. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
3. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`
4. `docs/design/platform/local-parity/*` for semantic source truth

If drift appears:
- stop implementation,
- log drift with impact and severity,
- resolve by explicit repin before proceeding.

## 3) Global Success Criteria (Program DoD)
Migration program is complete only when all are true:
- P0..P11 are green in `dev_min` using managed substrates.
- Semantic Green is proven (20-event + 200-event law/gate validation).
- Scale Green is proven (representative-window, burst, soak, and recovery-under-load validation).
- At least one scripted incident drill is evidenced and fail-closed behavior is demonstrated.
- No local/laptop runtime compute is used for platform services/jobs.
- P12 teardown leaves no demo cost-bearing resources.
- A second run is reproducible without semantic drift.

## 4) Non-Negotiable Guardrails
- No laptop compute for runtime jobs/services.
- P3 inlet is external/pre-staged (no platform seed/sync lane).
- IG writer-boundary auth remains enforced and fail-closed.
- `PUBLISH_AMBIGUOUS` blocks green closure until reconciled.
- Single-writer enforcement for P11 reporter/governance append.
- No NAT gateway, no always-on LB dependency, no always-on fleets.

## 5) Progressive Elaboration Method
Rules:
- Only one phase may be `ACTIVE`.
- A phase cannot start until prior phase is `DONE`.
- Each active phase must have:
  - explicit phase entry criteria,
  - concrete implementation tasks,
  - phase DoD checklist,
  - rollback/retry posture,
  - evidence contract.
- Future phases remain gate-level until activated.

Statuses:
- `NOT_STARTED`
- `ACTIVE`
- `DONE`
- `BLOCKED`

## 6) Phase Roadmap (Canonical)
Canonical lifecycle key: `phase_id=P#` from migration runbook.

| Plan Phase | Canonical phase_id | Name | Status |
| --- | --- | --- | --- |
| M0 | pre-P(-1) | Mobilization + authority lock | DONE |
| M1 | P(-1) | Packaging readiness (image + entrypoints + provenance) | DONE |
| M2 | P0 | Substrate readiness (Terraform core+confluent+demo) | DONE |
| M3 | P1 | Run pinning + run manifest evidence | DONE |
| M4 | P2 | Daemon bring-up on ECS with run-scope controls | DONE |
| M5 | P3 | Oracle lane (inlet assertion/sort/checker) | DONE |
| M6 | P4-P7 | Control+Ingress closure | DONE |
| M7 | P8-P10 | RTDL + Case/Labels closure | DONE |
| M8 | P11 | Obs/Gov closure | DONE |
| M9 | P12 | Teardown proof + cost guardrails | DONE |
| M10 | certification | Semantic Green + Scale Green certification | ACTIVE |

---

## 6.1) Deep Phase Plan Routing
Per-phase deep planning docs follow this naming pattern:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M0.build_plan.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
- ...
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M10.build_plan.md`

Control rule:
- `platform.build_plan.md` is the only file allowed to change phase status (`ACTIVE/DONE/BLOCKED`).
- `platform.M*.build_plan.md` documents deep plan detail, but cannot independently advance status.

Current deep-plan file state:
- `M0`: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M0.build_plan.md` (present)
- `M1`: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md` (present)
- `M2`: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M2.build_plan.md` (present)
- `M3`: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M3.build_plan.md` (present)
- `M4`: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M4.build_plan.md` (present)
- `M5`: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M5.build_plan.md` (present)
- `M6`: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M6.build_plan.md` (present)
- `M7`: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.build_plan.md` (present)
- `M7` branch deep plans:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P8.build_plan.md` (present)
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P9.build_plan.md` (present)
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P10.build_plan.md` (present)
- `M8`: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M8.build_plan.md` (present)
- `M9`: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M9.build_plan.md` (present)
- `M10`: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M10.build_plan.md` (present)

---

## 6.2) Phase Evidence Template (Pinned at M0)
Each phase (M1..M10) must produce an evidence snapshot aligned to this template:
- `phase_id` and plan phase (`M#`)
- `platform_run_id` (or `N/A` when run not created yet)
- authority refs used (runbook + handles sections)
- entry gate check results
- DoD check results
- commit evidence object list (paths/keys)
- failure/rollback note (if any)
- final phase verdict (`PASS`/`FAIL`)
- operator and timestamp (UTC)

Template usage:
- record deep details in the corresponding `platform.M*.build_plan.md`,
- summarize closure in `platform.impl_actual.md`,
- log execution action in daily logbook.

---

## 7) Phase Detail (Current State)
Current phase posture:
- `M1` is closed,
- `M0` is closed,
- `M2` is `DONE`,
- `M3` is `DONE`,
- `M4` is `DONE`,
- `M5` is `DONE`,
- `M6` is `DONE`,
- `M7` is `DONE`,
- `M8` is `DONE`,
- `M9` is `DONE`,
- `M10` is `ACTIVE` (planning expansion).

## M0 - Mobilization + Authority Lock
Status: `DONE`

Objective:
- Establish a clean, deterministic migration starting point so implementation cannot drift into legacy paths or implicit assumptions.

Entry criteria:
- Fresh-start reset for dev_substrate is already recorded.
- Migration runbook + handles registry are patched and internally consistent.

Implementation tasks:
1. Freeze migration authority set in working docs and implementation notes.
2. Open this build plan as the single execution tracker for the run.
3. Define acceptance evidence template for each upcoming phase (what file/object proves phase PASS).
4. Define phase-transition protocol (who/what confirms DoD before phase advance).
5. Prepare execution log discipline:
   - append implementation decisions in `platform.impl_actual.md`,
   - append action logs in `docs/logbook/02-2026/2026-02-13.md`.
6. Draft and approve deep-phase planning structure starting with:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M0.build_plan.md`.

DoD checklist:
- [x] Build plan exists with canonical roadmap and progressive-elaboration rules.
- [x] Active phase is explicitly declared.
- [x] No legacy migration path is treated as executable authority.
- [x] Phase transition and evidence policy are pinned in this file.
- [x] Deep-phase routing/status-ownership rule is pinned.
- [x] M0 deep plan exists and is aligned to this section.

Rollback posture:
- Documentation-only rollback is allowed before M1 begins.

Evidence outputs:
- This file committed/updated with active status and gates.
- Matching implementation-map/logbook entries.
- M0 deep plan document committed and cross-linked.
- Phase evidence template (Section 6.2) pinned for M1..M10 execution closure.

Phase exit:
- M0 is closed as `DONE`.
- M1 remains `NOT_STARTED` until explicit USER activation to proceed.

---

## 8) Current Active Phase

## M1 - P(-1) Packaging readiness
Status: `DONE`

Entry gate:
- M0 is `DONE`.
- Handles needed for image + ECS references are present in registry.

Scope:
- Build/push single platform image to ECR.
- Validate required entrypoint modes for Spine Green v0.
- Record immutable provenance (`git-<sha>`, digest) into run evidence path contract.

DoD (summary):
- image exists in ECR with immutable tag and digest.
- entrypoint contract validated (oracle jobs, SR, WSP, IG, RTDL workers, case/labels, reporter).
- no secrets baked into image.

Failure posture:
- fail closed on missing entrypoint/provenance mismatch.

Phase closure snapshot:
- This phase completed planning + execution with authoritative CI evidence.
- Detailed M1 execution authority is `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md` (contains pinned decisions required during build-go).
- Sub-phase progress:
  - [x] `M1.A` image contract freeze complete (reopened + reclosed with exact image content manifest).
  - [x] `M1.B` entrypoint matrix completion complete.
  - [x] `M1.C` provenance/evidence contract freeze complete.
  - [x] `M1.D` security/secret-injection contract freeze complete.
  - [x] `M1.E` build command surface/reproducibility contract freeze complete.
  - [x] `M1.F` build driver authority pin complete (`github_actions` authoritative; `local_cli` preflight-only).
  - [x] `M1.G` authoritative CI workflow realization complete (`.github/workflows/dev_min_m1_packaging.yml`).
  - [x] `M1.H` authoritative CI gate validation complete (`runs/dev_substrate/m1_h_validation/20260213T104213Z/ci_gate_validation_report.json`).
  - [x] `M1.I` exit-readiness review and build-go handoff complete.
  - M1 planning pack is closed; M1 execution remains user-governed by explicit build-go.
  - Build-go execution evidence now exists:
    - CI run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/21985500168`
    - evidence root: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T114002Z/P(-1)/`

M1 DoD checklist:
- [x] Packaging contract finalized in `platform.M1.build_plan.md` (image, entrypoints, provenance, security).
- [x] Build command surface and inputs are pinned (no ad hoc build path).
- [x] Evidence write contract for P(-1) is pinned and testable.
- [x] Runtime secret-handling rules are pinned (no secret baked into image).
- [x] M1 execution handoff statement is prepared for build-go pass.

Phase exit:
- M1 is closed as `DONE`.
- M2 is activated as the current planning/execution phase by explicit USER direction.

---

## M2 - P0 Substrate readiness
Status: `DONE`

Entry gate:
- M1 is `DONE`.
- USER has explicitly activated M2 expansion/planning.

Objective:
- Prove the managed substrate is ready and reproducible (core+confluent+demo infra, handles, secrets, topics, DB, network, budget, teardown viability) before any P1/P2 runtime progression.

Scope:
- Terraform core/confluent/demo posture and state separation.
- Handle-resolution completeness for all P0 dependencies.
- Confluent/SSM/topic readiness.
- ECS/network/no-NAT posture.
- runtime DB readiness and migration readiness.
- budget and teardown viability controls.

Failure posture:
- fail closed on any unresolved substrate handle, forbidden infra, missing secret/topic, or teardown-risk ambiguity.

Phase closure snapshot:
- Detailed M2 authority file: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M2.build_plan.md`.
- Sub-phase progress:
  - [x] `M2.A` substrate authority and handle-closure matrix.
  - [x] `M2.B` Terraform backend/state partition readiness.
  - [x] `M2.C` core apply closure contract and evidence.
  - [x] `M2.D` demo apply closure contract and evidence.
  - [x] `M2.E` SSM secret materialization and access checks.
  - [x] `M2.F` Kafka topic/ACL/access readiness.
  - [x] `M2.G` network/no-NAT/no-always-on-LB verification.
  - [x] `M2.H` runtime DB readiness + migrations posture.
  - [x] `M2.I` budget and teardown-viability proof.
  - [x] `M2.I` control-plane unified teardown lane materialized in GitHub Actions (`.github/workflows/dev_min_confluent_destroy.yml`, `stack_target=confluent|demo`) to avoid local secret dependency.
  - [x] `M2.J` exit-readiness and M3 handoff.
  - authoritative closeout execution:
    - `m2_execution_id=m2_20260213T205715Z`
    - verdict: `ADVANCE_TO_M3`
    - handoff artifacts:
      - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T205715Z/m2_exit_readiness_snapshot.json`
      - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T205715Z/m3_handoff_pack.json`

M2 DoD checklist:
- [x] Terraform core/confluent/demo apply+destroy flow is pinned and reproducible.
- [x] Required handles resolve to reachable substrate resources.
- [x] Confluent bootstrap/key/secret and required topics are validated.
  - Canonical command lane: `python tools/dev_substrate/verify_m2f_topic_readiness.py`.
- [x] Unified teardown capability is available in GitHub Actions (`workflow_dispatch`) with OIDC and remote-state lock discipline.
- [x] No NAT and no forbidden always-on infra posture is proven.
- [x] runtime DB and migration readiness are validated.
- [x] Budget alerts and teardown viability are evidenced.

---

## M3 - P1 Run pinning
Status: `DONE`

Entry gate:
- M2 is `DONE`.

Objective:
- Create run identity/provenance exactly once, publish durable run manifest evidence, and produce M3->M4 handoff contract so daemons can enforce run-scope fail-closed.

Scope:
- `platform_run_id` generation and collision-safe uniqueness checks.
- run config payload assembly + deterministic config digest.
- run evidence publication (`run.json` + start marker) under run-scoped S3 root.
- runtime scope export contract for M4 (`REQUIRED_PLATFORM_RUN_ID` wiring surface).
- M3 blocker model and explicit `ADVANCE_TO_M4`/`HOLD_M3` verdict rule.

Failure posture:
- fail closed on unresolved run identity inputs, digest mismatch, incomplete run manifest, or non-durable evidence publication.

Phase closure posture:
- Detailed M3 authority file: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M3.build_plan.md`.
- M3.A planning status:
  - closure matrix + verification catalog executed,
  - latest authoritative run: `m3a_20260213T213547Z`,
  - blocker posture: `M3A-B1` resolved (no open M3.A blocker),
  - evidence:
    - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3a_20260213T213547Z/m3_a_handle_closure_snapshot.json`.
- M3.B planning status:
  - expanded to closure-grade planning (decision pins, command catalog, blocker taxonomy, evidence contract),
  - pinned run-id format: `platform_<YYYYMMDDTHHMMSSZ>`,
  - authoritative execution run: `m3b_20260213T214223Z`,
  - result: `overall_pass=true`,
  - evidence:
    - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3b_20260213T214223Z/m3_b_run_id_generation_snapshot.json`.
- M3.C planning status:
  - expanded to closure-grade planning (decision pins, command catalog, blocker taxonomy, evidence contract),
  - input anchor pinned to accepted M3.B run-id source,
  - authoritative execution run: `m3c_20260213T215336Z`,
  - result: `overall_pass=true`,
  - note: `ORACLE_REQUIRED_OUTPUT_IDS` and `ORACLE_SORT_KEY_BY_OUTPUT_ID` are now pinned in the handles registry; historical M3.C evidence remains provisional because it was produced before this pin and should be refreshed when M3.C is next re-executed,
  - evidence:
    - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3c_20260213T215336Z/m3_c_digest_snapshot.json`.
- M3.D->M3.G planning status:
  - expanded sequentially to closure-grade planning in `platform.M3.build_plan.md` (decision pins, command catalogs, blocker taxonomies, and evidence contracts for each of D/E/F/G),
  - authoritative execution run: `m3_20260213T221631Z`,
  - all sub-phases passed in fail-closed order (`M3.D -> M3.E -> M3.F -> M3.G`),
  - final M3 verdict: `ADVANCE_TO_M4`,
  - blocker handling summary:
    - resolved `M3D-B4` false-positive preexistence detection in D-lane,
    - resolved `M3E-B3/M3E-B6` scope completeness/publish hold in E-lane,
  - durable evidence:
    - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3_20260213T221631Z/m3_f_verdict_snapshot.json`
    - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3_20260213T221631Z/m4_handoff_pack.json`.
- Sub-phase progress:
  - [x] `M3.A` authority + handle closure matrix for P1.
  - [x] `M3.B` run identity generation contract (`platform_run_id` uniqueness).
  - [x] `M3.C` run config payload + deterministic digest contract.
  - [x] `M3.D` durable run evidence publication (`run.json` + start marker).
  - [x] `M3.E` runtime scope export handoff for M4.
  - [x] `M3.F` pass gates + blocker model closure.
  - [x] `M3.G` M4 handoff artifact publication + readiness verdict.

M3 DoD checklist:
- [x] `platform_run_id` is generated and collision-checked.
- [x] run config payload is canonicalized and digest-complete.
- [x] `run.json` exists at run evidence root and is structurally complete.
- [x] runtime scope export (`REQUIRED_PLATFORM_RUN_ID`) is prepared for M4 consumers.
- [x] M3 closeout verdict + handoff artifact are published and non-secret.
- [x] phase-transition confirmation to M4 activation is USER-approved.

---

## 9) Remaining Phases (Current Program State)

## M4 - P2 Daemon bring-up
Status: `DONE`
Closure summary:
- M4 executed end-to-end and closed with `M4.J` handoff publication PASS.
- Closure evidence anchors:
  - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/operate/daemons_ready.json`
  - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m4_20260214T170155Z/m4_i_verdict_snapshot.json`
  - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m4_20260214T170953Z/m5_handoff_pack.json`
- M4 deep authority/closure ledger:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M4.build_plan.md`

## M5 - P3 Oracle lane
Status: `DONE`
Entry gate:
- M4 is `DONE`.
- M4 handoff artifact is present:
  - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m4_20260214T170953Z/m5_handoff_pack.json`.

Objective:
- Materialize deterministic P3 oracle readiness for WSP by producing run-scoped `stream_view` outputs and checker PASS evidence on managed compute only.
- Keep migration functional closure and scale/perf closure as explicit separate lanes (no silent gate mutation).

Scope:
- P3 oracle-lane flow:
  - inlet contract is explicit (how oracle inputs arrive into run-scoped S3),
  - external inlet assertion only (no platform sync/copy/seed job),
  - stream-sort per required output_id with deterministic sort keys,
  - checker fail-closed validation across all required output_ids.
- Commit run-scoped durable evidence:
  - stream_view manifests + sort receipts under oracle prefix,
  - `oracle/inlet_assertion_snapshot.json`,
  - `oracle/stream_sort_summary.json`,
  - `oracle/checker_pass.json`.
- Preserve no-laptop and external-inlet laws with per-output rerun semantics.

Failure posture:
- fail closed on unresolved P3 handles, inlet-policy drift, missing manifest/receipt, checker failure, or missing durable evidence.

Active-phase planning posture:
- Detailed M5 authority file:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M5.build_plan.md`.
- M5 entry handoff anchor:
  - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m4_20260214T170953Z/m5_handoff_pack.json`.
- M5 sub-phase progression model:
  - `M5.A` authority + handle closure for P3.
  - `M5.B` oracle inlet policy closure (external ownership boundary).
  - `M5.C` oracle input presence assertion (no platform seed execution).
  - `M5.D` stream-sort launch contract and per-output task plan.
  - `M5.E` stream-sort execution + receipt/manifest publication (`lane_mode` pinned per run).
  - `M5.F` checker execution + pass artifact publication.
  - `M5.G` per-output rerun safety proof (targeted failure/recovery drill or equivalent evidence).
  - `M5.H` P3 gate evaluation + blocker rollup + verdict.
  - `M5.I` M6 handoff artifact publication.
- M5 expansion state:
  - `M5.A -> M5.I` are now expanded to execution-grade in the deep plan with entry criteria, required inputs, deterministic tasks, DoD, and blockers.
  - `M5.A` now explicitly pins M4->M5 entry invariants, always-required P3 handles, and local+durable `m5_a_handle_closure_snapshot.json` publication contract.
  - `M5.B` now explicitly pins M5.A carry-forward invariants, inlet-policy exact-match validation, seed-lane drift-scan guards, and local+durable `m5_b_inlet_policy_snapshot.json` publication contract.
  - `M5.C` now explicitly pins M5.B carry-forward invariants, run-scoped input prefix + manifest/seal readability assertions, manifest output-id coverage checks, and local+durable `oracle/inlet_assertion_snapshot.json` publication contract.
  - `M5.C` execution closed PASS after one fail-closed correction cycle (`M5C-B2/M5C-B4` -> fixed -> PASS); final evidence:
    - local: `runs/dev_substrate/m5/20260214T193548Z/inlet_assertion_snapshot.json`
    - durable: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/oracle/inlet_assertion_snapshot.json`
  - `M5.D` is now explicitly expanded to launch-contract closure grade:
    - M5.C carry-forward invariants,
    - deterministic per-output launch matrix + sort-key closure,
    - managed ECS one-shot task profile closure,
    - local+durable `m5_d_stream_sort_launch_snapshot.json` publication contract.
  - `M5.D` execution attempt is now evidenced and fail-closed:
    - local: `runs/dev_substrate/m5/20260214T194850Z/m5_d_stream_sort_launch_snapshot.json`
    - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T194850Z/m5_d_stream_sort_launch_snapshot.json`
    - blocker: `M5D-B4` (`TD_ORACLE_STREAM_SORT` not materialized in ECS)
  - `M5D-B4` is resolved by IaC materialization of oracle task definitions + rerun PASS:
    - local: `runs/dev_substrate/m5/20260214T195741Z/m5_d_stream_sort_launch_snapshot.json`
    - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T195741Z/m5_d_stream_sort_launch_snapshot.json`
  - `M5.E` is now explicitly expanded to execution-grade stream-sort closure:
    - M5.D carry-forward invariant gate,
    - deterministic per-output ECS one-shot execution contract,
    - per-output shard/manifest/receipt durable evidence checks,
    - local+durable `oracle/stream_sort_summary.json` publication contract.
  - `M5.E` execution challenge proof is now explicit and fail-closed:
    - first full-matrix execution failed due IAM and compute pressure with non-zero exits/missing shard closure.
    - local evidence: `runs/dev_substrate/m5/20260214T202411Z/stream_sort_summary.json`
    - durable evidence: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/oracle/stream_sort_summary.json`
    - heavy single-output proof (`arrival_events_5B`, `124724153` rows) completed only under high-resource profile with long runtime.
  - decision lock:
    - `M5` gates migration using `lane_mode=functional_green` workload profile only.
    - full-scale throughput/perf closure is routed to `M10` (Scale Green), not used to mutate M5 gate semantics.
    - functional-gating M5.E runs must publish `functional_workload_profile.json` as pre-launch evidence.
- Sub-phase progress:
  - [x] `M5.A` authority + handle closure for P3.
  - [x] `M5.B` oracle inlet policy closure.
  - [x] `M5.C` oracle input presence assertion.
  - [x] `M5.D` stream-sort launch contract.
  - [x] `M5.E` stream-sort execution + receipts/manifests.
  - [x] `M5.F` checker execution + checker pass artifact.
  - [x] `M5.G` per-output rerun safety proof.
  - [x] `M5.H` P3 verdict + blocker rollup.
  - [x] `M5.I` M6 handoff publication.
  - closure evidence:
    - `runs/dev_substrate/m5/20260214T235117Z/stream_sort_summary.json`
    - `runs/dev_substrate/m5/20260215T002040Z/checker_pass.json`
    - `runs/dev_substrate/m5/20260215T002310Z/m5_g_rerun_probe_snapshot.json`
    - `runs/dev_substrate/m5/20260215T002310Z/m5_h_verdict_snapshot.json`
    - `runs/dev_substrate/m5/20260215T002310Z/m6_handoff_pack.json`

M5 DoD checklist:
- [x] P3 inputs for this run exist in S3 under canonical run-scoped input prefix (external-prestaged / engine-written).
- [x] `functional_workload_profile.json` is published for the active `functional_green` M5.E run.
- [x] For each required output_id in the pinned `functional_green` workload profile, stream_view shards + manifest + stream_sort receipt exist.
- [x] `oracle/checker_pass.json` exists and confirms full PASS for required output_ids.
- [x] P3 rerun posture is fail-closed and per-output (no forced full rerun for single-output failure).
- [x] M5 verdict and M6 handoff package are published and non-secret.

## M6 - P4-P7 Control + Ingress closure
Status: `DONE`
Entry gate:
- M5 is `DONE`.
- M5 handoff artifact is present:
  - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T235117Z/m6_handoff_pack.json`.

Objective:
- Close `P4..P7` end-to-end on managed substrate:
  - `P4` IG readiness + writer-boundary auth,
  - `P5` SR gate execution + READY publication,
  - `P6` WSP stream activation from P3 `stream_view`,
  - `P7` ingest commit verification (receipts, quarantine, offsets, ambiguity gate).
- Preserve no-laptop runtime law and fail-closed progression to M7.

Scope:
- `P4 INGEST_READY`:
  - `SVC_IG` health and auth boundary checks,
  - Kafka publish smoke and S3 receipt/quarantine write smoke,
  - run-scoped `ingest/ig_ready.json` evidence.
- `P5 READY_PUBLISHED`:
  - one-shot `TD_SR` run under run scope,
  - SR gate PASS + READY message publication receipt,
  - run-scoped SR evidence artifacts.
- `P6 STREAMING_ACTIVE`:
  - one-shot `TD_WSP` run with READY precondition,
  - stream-view-first reads from M5 outputs only,
  - deterministic send/retry posture + WSP summary artifacts.
- `P7 INGEST_COMMITTED`:
  - IG outcome verification (ADMIT/DUPLICATE/QUARANTINE/ANOMALY),
  - receipt and offset snapshot closure,
  - hard fail on unresolved `PUBLISH_AMBIGUOUS`.

Failure posture:
- fail closed on any of:
  - IG auth/health boundary failure,
  - SR failure or missing READY publication,
  - WSP non-retryable/terminal failure,
  - missing ingest commit evidence,
  - unresolved `PUBLISH_AMBIGUOUS`.

Active-phase planning posture:
- Detailed M6 authority file:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M6.build_plan.md`.
- M6 entry handoff anchor:
  - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m5_20260214T235117Z/m6_handoff_pack.json`.
- M6 sub-phase progression model:
  - `M6.A` authority + handle closure for `P4..P7`,
  - `M6.B` P4 IG deploy/health/auth readiness checks,
  - `M6.C` P4 Kafka/S3 smoke + `ig_ready.json` publication,
  - `M6.D` P5 SR task run + READY publication proof,
  - `M6.E` P6 WSP launch contract + READY consumption proof,
  - `M6.F` P6 WSP execution summary + IG boundary transfer proof,
  - `M6.G` P7 ingest commit verification (receipts/quarantine/offsets),
  - `M6.H` P4..P7 gate rollup + verdict,
  - `M6.I` M7 handoff artifact publication.
- M6 expansion state:
  - `M6.A` is now execution-grade in deep plan with:
    - explicit required input set,
    - deterministic handle-closure matrix contract,
    - materialization probe requirements,
    - fail-closed blocker taxonomy and snapshot schema.
  - `M6.A` has been executed once (fail-closed) with authoritative snapshot:
    - local: `runs/dev_substrate/m6/20260215T032545Z/m6_a_handle_closure_snapshot.json`
    - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T032545Z/m6_a_handle_closure_snapshot.json`
    - result: `overall_pass=true`, blocker rollup empty.
    - closure path completed:
      - pinned handles (`IG_BASE_URL`, `TD_SR`, `TD_WSP`, `ROLE_SR_TASK`, `ROLE_WSP_TASK`)
      - materialized `TD_SR` and `TD_WSP` task definitions in ECS.
  - `M6.B` closed PASS with authoritative snapshot:
    - local: `runs/dev_substrate/m6/20260215T040527Z/m6_b_ig_readiness_snapshot.json`
    - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T040527Z/m6_b_ig_readiness_snapshot.json`
    - result: `overall_pass=true`, blocker rollup empty.
    - closure proof:
      - IG runtime is no longer placeholder and exposes `8080`,
      - app SG ingress rule exists for probe path,
      - IG API key in SSM is non-placeholder,
      - health/auth probes satisfy M6.B gate contract.
  - `M6.C` was planning-expanded and execution-gated:
    - explicit runtime-preflight, Kafka offset-smoke, and durable `ig_ready.json` publication lanes are defined in deep plan,
    - initial pre-execution blocker `M6C-B4` was opened on temporary `file`-bus/local-store shim from M6.B closure.
  - Initial `M6.C` fail-closed execution history:
    - local snapshot: `runs/dev_substrate/m6/20260215T071807Z/m6_c_ingest_ready_snapshot.json`
    - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T071807Z/m6_c_ingest_ready_snapshot.json`
    - result: `overall_pass=false` with blocker `M6C-B4`;
    - no Kafka smoke / `ig_ready.json` claim was made while runtime posture is non-conformant.
  - `M6.C` closure rerun now passes with durable evidence:
    - local snapshot: `runs/dev_substrate/m6/20260215T083126Z/m6_c_ingest_ready_snapshot.json`
    - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T083126Z/m6_c_ingest_ready_snapshot.json`
    - run-scoped readiness artifact: `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/ingest/ig_ready.json`
    - result: `overall_pass=true`, blocker rollup empty for M6.C.
    - publish/read proof captured via active managed stream adapter evidence (`eb_ref.offset_kind=kinesis_sequence`).
  - Terraform state convergence is now complete for the IG rematerialization lane:
    - imported stream resource `module.demo.aws_kinesis_stream.ig_event_bus`,
    - applied `infra/terraform/dev_min/demo` with pinned runtime vars,
    - final post-apply `terraform plan -detailed-exitcode` returned `0`.
  - Post-convergence M6.C rerun also passes on IG task definition `:8`:
    - local snapshot: `runs/dev_substrate/m6/20260215T124328Z/m6_c_ingest_ready_snapshot.json`
    - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260215T124328Z/m6_c_ingest_ready_snapshot.json`
    - run-scoped readiness artifact (refreshed): `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/ingest/ig_ready.json`
    - result: `overall_pass=true`, blocker rollup empty.
  - `M6.D` is now execution-closed with authoritative PASS evidence:
    - authoritative READY signal (durable):
      - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/sr/ready_signal/17dacbdc997e6765bcd242f7cb3b6c37.json`
    - 4-output Oracle Store posture is proven in READY payload (`oracle_pack_ref.stream_view_output_refs`):
      - `arrival_events_5B`, `s1_arrival_entities_6B`, `s3_event_stream_with_fraud_6B`, `s3_flow_anchor_with_fraud_6B`.
    - closure is now aligned to published runtime posture (no task-scoped shims):
      - SR task definition revision: `fraud-platform-dev-min-sr:2`
      - image digest: `sha256:5550d39731e762bd4211fcae0d55edb72059bef5d3a1c7a3bdbab599064b89c3`.
  - `M6.G` is now execution-closed with authoritative PASS evidence (`m6_execution_id=m6_20260216T064825Z`):
    - local snapshot:
      - `runs/dev_substrate/m6/20260216T064825Z/m6_g_ingest_commit_snapshot.json`
    - durable snapshots:
      - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/ingest/m6_g_ingest_commit_snapshot.json`
      - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260216T064825Z/m6_g_ingest_commit_snapshot.json`
    - closure facts:
      - `overall_pass=true`, blockers empty.
      - IG preflight `state=GREEN`.
      - receipt counts: `ADMIT=800`, `DUPLICATE=800`, `QUARANTINE=0`.
      - ambiguity gate: `publish_ambiguous_count=0`, `publish_in_flight_count=0`.
  - `M6.H` + `M6.I` are now execution-closed with authoritative PASS evidence (`m6_execution_id=m6_20260216T214025Z`):
    - local snapshots:
      - `runs/dev_substrate/m6/20260216T214025Z/m6_h_verdict_snapshot.json`
      - `runs/dev_substrate/m6/20260216T214025Z/m7_handoff_pack.json`
    - durable snapshots:
      - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260216T214025Z/m6_h_verdict_snapshot.json`
      - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260216T214025Z/m7_handoff_pack.json`
    - closure facts:
      - verdict: `ADVANCE_TO_M7`
      - blocker rollup: empty
      - `overall_pass=true`.

- Sub-phase progress:
  - [x] `M6.A` authority + handle closure for `P4..P7`.
  - [x] `M6.B` P4 IG deploy/health/auth readiness.
  - [x] `M6.C` P4 Kafka/S3 smoke and `ig_ready.json`.
  - [x] `M6.D` P5 SR PASS + READY publication.
  - [x] `M6.E` P6 WSP launch contract + READY consumption proof.
  - [x] `M6.F` P6 WSP execution summary.
  - [x] `M6.G` P7 ingest commit evidence closure.
  - [x] `M6.H` P4..P7 verdict + blocker rollup.
  - [x] `M6.I` M7 handoff publication.

M6 DoD checklist:
- [x] IG service readiness + auth boundary checks pass and `ingest/ig_ready.json` is durable.
- [x] SR task PASS evidence exists and READY publication receipt is durable.
- [x] WSP executes from P3 `stream_view` only and emits closure-grade summary evidence (READY record + per-output CloudWatch proof) with durable `M6.F` snapshot.
- [x] Ingest receipt/offset/quarantine summaries exist and are coherent.
- [x] `PUBLISH_AMBIGUOUS` unresolved count is zero for closure set.
- [x] M6 verdict is `ADVANCE_TO_M7` with empty blocker rollup.
- [x] M7 handoff pack is published and non-secret.

## M7 - P8-P10 RTDL + Case/Labels closure
Status: `DONE`
Entry gate:
- M6 is `DONE`.
- M6 handoff artifact is present:
  - local: `runs/dev_substrate/m6/20260216T214025Z/m7_handoff_pack.json`
  - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260216T214025Z/m7_handoff_pack.json`.

Objective:
- Close `P8..P10` end-to-end on managed substrate:
  - `P8` RTDL catch-up + origin-offset/archive evidence closure,
  - `P9` decision-chain commit + append-only DLA evidence closure,
  - `P10` case/label append-only commit closure on managed DB.
- Preserve no-laptop runtime law and fail-closed progression to M8.

Scope:
- `P8 RTDL_CAUGHT_UP`:
  - RTDL core daemon health + Kafka consumption progression,
  - commit-after-durable-write discipline and lag gate closure,
  - offsets/caught-up evidence and archive-write summary proof (if writer active).
- `P9 DECISION_CHAIN_COMMITTED`:
  - decision lane daemon health and processing closure (DL/DF/AL/DLA),
  - idempotent action/outcome contract and append-only DLA truth,
  - decision/action/audit evidence summaries under run scope.
- `P10 CASE_LABELS_COMMITTED`:
  - case/label services and managed DB readiness closure,
  - append-only + idempotent case timeline/label assertion posture,
  - case/label evidence summaries under run scope.

Failure posture:
- fail closed on any of:
  - unresolved required handles or placeholders at execution entry,
  - missing RTDL lag/offset/archive proof,
  - missing decision/action/audit evidence or append-only drift,
  - unresolved `CASE_SUBJECT_KEY_FIELDS` / `LABEL_SUBJECT_KEY_FIELDS`,
  - missing case/label commit evidence.

Active-phase planning posture:
- Detailed M7 authority file:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.build_plan.md`.
- Detailed M7 branch authority files:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P8.build_plan.md` (`P8` RTDL core).
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P9.build_plan.md` (`P9` decision lane).
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P10.build_plan.md` (`P10` case/labels).
- M7 entry handoff anchor:
  - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m6_20260216T214025Z/m7_handoff_pack.json`.
- M7 sub-phase progression model:
  - `M7.A` authority + handle closure for `P8..P10`,
  - `M7.B` P8 RTDL core readiness and consumer posture checks,
  - `M7.C` P8 offsets/caught-up gate evidence publication,
  - `M7.D` P8 archive durability proof closure (when archive writer lane is active),
  - `M7.E` P9 decision-lane readiness and idempotency posture checks,
  - `M7.F` P9 decision/action/audit commit evidence closure,
  - `M7.G` P10 case/label identity key pin + managed DB readiness closure,
  - `M7.H` P10 case/label commit evidence closure,
  - `M7.I` P8..P10 gate rollup + verdict,
  - `M7.J` M8 handoff artifact publication.
- M7 expansion state:
  - `M7.A..M7.J` are planning-expanded in the M7 orchestrator deep plan.
  - Plane-depth execution detail is branched by phase:
    - `P8` detail in `platform.M7.P8.build_plan.md`
    - `P9` detail in `platform.M7.P9.build_plan.md`
    - `P10` detail in `platform.M7.P10.build_plan.md`
  - runtime execution has started:
    - `M7.A` closed at `m7_20260218T141420Z`
    - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_a_handle_closure_snapshot.json`.
    - `M7.B` closed at `m7_20260218T141420Z`
    - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_b_rtdl_readiness_snapshot.json`.
  - `M7.C` rerun is now closed PASS:
    - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_c_rtdl_caught_up_snapshot.json`
    - closure result: `overall_pass=true`, blockers empty.
    - note: refreshed active-epoch P7 basis currently captures empty required Kafka topics (`run_end_offset=-1` on all required partitions).
  - `M7.D` rerun is now closed PASS:
    - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_d_archive_durability_snapshot.json`
    - closure result: `overall_pass=true`, blockers empty.
    - closure path completed:
      - runtime image rebuild/publish with Kafka intake fixes,
      - archive-writer rematerialized to task definition `:16`,
      - rerun evidence republished with stable writer posture.
  - `P8.D` plane rollup is now closed PASS:
    - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_p8_plane_snapshot.json`
    - closure result: `overall_pass=true`, blocker rollup empty, runtime budgets within thresholds.
  - `M7.E` (`P9.A`) is now closed PASS:
    - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_e_decision_lane_readiness_snapshot.json`
    - closure result: `overall_pass=true`, blockers empty.
    - closure notes:
      - first probe window failed fail-closed on rollout churn (`M7E-B1`);
      - rerun after service stabilization closed green on two-probe health + run-scope/idempotency/dependency checks.
  - `M7.F` (`P9.B`) planning is now expanded to execution-grade:
    - authoritative deep plan section: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M7.P9.build_plan.md`
    - planning closure includes:
      - pre-execution readiness matrix for `P9.B`,
      - deterministic verification algorithm,
      - snapshot schema contract,
      - fail-closed blocker taxonomy (`M7F-B1..M7F-B6`).
    - runtime execution performed (`2026-02-18`) and initially closed fail-closed:
      - run-scoped artifacts were published:
        - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/decision_lane/decision_summary.json`
        - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/decision_lane/action_summary.json`
        - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/decision_lane/audit_summary.json`
      - control snapshot published:
        - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_f_decision_chain_snapshot.json`
      - closure result: `overall_pass=false` with open blockers `M7F-B1` and `M7F-B2`.
    - rerun closure (`2026-02-18`) after DLA image drift remediation:
      - `decision-lane-dla` restored from probe image drift to platform image/task definition `:24`,
      - refreshed summaries are non-zero (`decisions=200`, `action_outcomes=200`, `audit_records=600`),
      - closure result: `overall_pass=true`, blocker rollup empty.
    - `P9.C` rollup closure (`2026-02-19`):
      - local snapshot: `runs/dev_substrate/m7/20260218T141420Z/m7_p9_plane_snapshot.json`
      - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_p9_plane_snapshot.json`
      - closure result: `overall_pass=true`, blocker rollup empty.
  - `M7.G` (`P10.A`) initial fail-closed then rerun pass (`2026-02-19`):
    - local snapshot: `runs/dev_substrate/m7/20260218T141420Z/m7_g_case_label_db_readiness_snapshot.json`
    - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_g_case_label_db_readiness_snapshot.json`
    - closure subset now green:
      - subject-key handles are pinned and runtime-aligned (`CASE_SUBJECT_KEY_FIELDS`, `LABEL_SUBJECT_KEY_FIELDS`).
    - remediation closure:
      - CM/LS rematerialized to real worker runtime (`:14` task definitions),
      - DB migrations rematerialized to one-shot runtime proof (`:13`) and executed with `exit=0` and `db_migrations_ok tables=5`,
      - rerun snapshot verdict: `overall_pass=true`, blockers empty.
  - `M7.H` (`P10.B`) closure (`2026-02-19`):
    - root-cause fix applied in `src/fraud_detection/case_mgmt/worker.py` for Kafka envelope handling,
    - managed image refresh/rematerialization completed (`case-mgmt` on digest `sha256:126d604ebc6a3e1ffe7bed9754a6c0ef718132559c3c277bce96c23685af3165`),
    - closure artifacts published:
      - local:
        - `runs/dev_substrate/m7/20260218T141420Z/case_labels/case_summary.json`
        - `runs/dev_substrate/m7/20260218T141420Z/case_labels/label_summary.json`
        - `runs/dev_substrate/m7/20260218T141420Z/m7_h_case_label_commit_snapshot.json`
      - durable:
        - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/case_labels/case_summary.json`
        - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/case_labels/label_summary.json`
        - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_h_case_label_commit_snapshot.json`
    - closure result: `overall_pass=true`, blockers empty.
  - `M7.I` (`P8..P10 verdict`) closure (`2026-02-19`):
    - first pass failed closed on source schema contract (`M7I-B2`: `m7_a_handle_closure_snapshot.json` missing `phase_id`),
    - `M7.A` snapshot schema normalized (`phase_id=P8..P10_HANDLE_CLOSURE`) and republished local+durable,
    - rerun closure artifacts:
      - local:
        - `runs/dev_substrate/m7/20260218T141420Z/m7_i_verdict_snapshot.json`
      - durable:
        - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m7_i_verdict_snapshot.json`
    - closure result: `verdict=ADVANCE_TO_M8`, `overall_pass=true`, blockers empty.
  - `M7.J` planning expansion (`2026-02-19`):
    - deep plan now pins deterministic handoff payload contract and required fields,
    - non-secret payload gate and evidence-URI readability checks are fail-closed prerequisites,
    - execution is pending explicit USER go-ahead.
  - `M7.J` execution closure (`2026-02-19`):
    - handoff artifact published local + durable:
      - `runs/dev_substrate/m7/20260218T141420Z/m8_handoff_pack.json`
      - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m8_handoff_pack.json`
    - contract posture:
      - `m8_entry_gate=READY`
      - `non_secret_payload=true`
      - `overall_pass=true`, blockers empty.

Sub-phase progress:
  - [x] `M7.A` authority + handle closure for `P8..P10`.
  - [x] `M7.B` P8 RTDL readiness + consumer posture.
  - [x] `M7.C` P8 offsets/caught-up evidence closure.
  - [x] `M7.D` P8 archive durability proof closure.
  - [x] `M7.E` P9 decision-lane readiness + idempotency posture.
  - [x] `M7.F` P9 decision/action/audit commit evidence closure.
  - [x] `M7.G` P10 identity-key pin + managed DB readiness.
  - [x] `M7.H` P10 case/label commit evidence closure.
  - [x] `M7.I` P8..P10 verdict + blocker rollup.
  - [x] `M7.J` M8 handoff publication.

M7 DoD checklist:
- [x] RTDL caught-up evidence exists with lag <= `RTDL_CAUGHT_UP_LAG_MAX`.
- [x] RTDL offsets snapshot and caught-up artifact are durable and run-scoped.
- [x] Decision lane commit evidence exists (`decision_summary`, `action_summary`, `audit_summary`) and append-only posture holds.
- [x] P10 identity key fields are pinned for this run and no placeholders remain.
- [x] Case and label summaries are durable and consistent with append-only/idempotent writes.
- [x] M7 verdict is `ADVANCE_TO_M8` with empty blocker rollup.
- [x] M8 handoff pack is published and non-secret.

## M8 - P11 Obs/Gov closure
Status: `ACTIVE`
Entry gate:
- M7 is `DONE`.
- M7 handoff artifact is present:
  - local: `runs/dev_substrate/m7/20260218T141420Z/m8_handoff_pack.json`
  - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m7_20260218T141420Z/m8_handoff_pack.json`.

Objective:
- Close `P11 OBS_GOV_CLOSED` on managed substrate with single-writer discipline:
  - reporter one-shot closeout lock succeeds,
  - run closure evidence bundle is complete and durable,
  - replay anchors and reconciliation are coherent and run-scoped,
  - run completion marker is written.
- Preserve no-laptop compute law and fail-closed governance posture.

Scope:
- reporter runtime readiness on ECS one-shot task (`TD_REPORTER`) with lock backend.
- input evidence intake from prior phases (`M6`, `M7`) for closure aggregation.
- closure bundle publication under run evidence prefix:
  - `run_completed.json`
  - `obs/run_report.json`
  - `obs/reconciliation.json`
  - `obs/replay_anchors.json`
  - `obs/environment_conformance.json`
  - `obs/anomaly_summary.json`.
- reporter contention fail-closed proof and single-writer conformance.
- P11 verdict rollup + M9 handoff publication.

Failure posture:
- fail closed on any of:
  - reporter lock acquisition failure or concurrent-writer success,
  - missing required closure artifacts or unreadable evidence URIs,
  - replay anchors/reconciliation inconsistency against prior phase evidence,
  - non-secret policy violation in control artifacts,
  - missing run completion marker.

Active-phase planning posture:
- Detailed M8 authority file:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M8.build_plan.md`.
- M8 sub-phase progression model:
  - `M8.A` P11 authority + handles closure,
  - `M8.B` reporter runtime + single-writer lock readiness,
  - `M8.C` P11 input evidence readiness checks,
  - `M8.D` reporter contention fail-closed probe,
  - `M8.E` reporter one-shot execution,
  - `M8.F` closure bundle completeness verification,
  - `M8.G` replay anchors + reconciliation coherence verification,
  - `M8.H` closure marker + env/anomaly outputs verification,
  - `M8.I` P11 verdict rollup + M9 handoff publication.
- M8 expansion state:
  - planning is expanded to execution-grade in `platform.M8.build_plan.md`,
  - `M8.A` is expanded to execution-grade with deterministic handle-closure algorithm and snapshot contract,
  - `M8.B` is expanded to execution-grade with deterministic reporter readiness algorithm and snapshot contract,
  - `M8.C` is expanded to execution-grade with deterministic input-readiness algorithm and snapshot contract,
  - `M8.D` is expanded to execution-grade with deterministic contention-probe algorithm and snapshot contract,
  - `M8.E` is expanded to execution-grade with deterministic one-shot reporter verification algorithm and snapshot contract,
  - `M8.F` is expanded to execution-grade with deterministic closure-bundle verification algorithm and snapshot contract,
  - `M8.A` rerun is green after reporter surface materialization,
  - `M8.B` execution is green,
  - `M8.C` execution is green,
  - `M8.D` remediation rerun is green with blockers empty; `M8.E` is unblocked.
  - `M8.E` execution is green with blockers empty; `M8.F` is unblocked.
  - `M8.F` executed fail-closed on canonical rerun with blocker `M8F-B1`; `M8.G..M8.I` blocked pending remediation.
  - `M8.F` remediation reruns are green with blockers empty; `M8.G..M8.I` are unblocked.
  - `M8.G` is expanded to execution-grade with deterministic replay-anchor/reconciliation verification algorithm and snapshot contract.
  - `M8.G` execution is green with blockers empty; `M8.H` is unblocked.
  - `M8.H` is expanded to execution-grade with deterministic closure-marker/Obs-Gov surface verification algorithm and snapshot contract.
  - `M8.H` execution is green with blockers empty; `M8.I` is unblocked.
  - `M8.I` is expanded to execution-grade with deterministic verdict-rollup + M9 handoff contract.
  - `M8.I` execution is green with blockers empty; verdict is `ADVANCE_TO_M9`.
  - `M8.I` is expanded to execution-grade with deterministic verdict-rollup + M9 handoff contract.

M8.A execution closure (2026-02-19):
  - execution id: `m8_20260219T073801Z`
  - local snapshot: `runs/dev_substrate/m8/20260219T073801Z/m8_a_handle_closure_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T073801Z/m8_a_handle_closure_snapshot.json`
  - result: `overall_pass=false` with blocker `M8A-B2`
  - unresolved required handles: `ROLE_REPORTER_SINGLE_WRITER`, `TD_REPORTER`
  - posture: fail-closed hold on `M8.A`; `M8.B..M8.I` remain blocked until rerun passes.

M8.A remediation + rerun closure (2026-02-19):
  - materialized reporter role: `fraud-platform-dev-min-reporter-single-writer`
  - materialized reporter task family: `fraud-platform-dev-min-reporter`
  - execution id: `m8_20260219T075228Z`
  - local snapshot: `runs/dev_substrate/m8/m8_20260219T075228Z/m8_a_handle_closure_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T075228Z/m8_a_handle_closure_snapshot.json`
  - result: `overall_pass=true`, blockers empty.

M8.B execution closure (2026-02-19):
  - execution id: `m8_20260219T080757Z`
  - local snapshot: `runs/dev_substrate/m8/m8_20260219T080757Z/m8_b_reporter_readiness_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T080757Z/m8_b_reporter_readiness_snapshot.json`
  - result: `overall_pass=true`, blockers empty
  - posture: reporter runtime/role/lock readiness verified; `M8.C` unblocked.

M8.C execution closure (2026-02-19):
  - fail-first trace:
    - `m8_20260219T082518Z` (local snapshot only), `overall_pass=false`, blockers `M8C-B5`, `M8C-B3`
    - `m8_20260219T082755Z` (local + durable), `overall_pass=false`, blocker `M8C-B3`
  - closure pass:
    - execution id: `m8_20260219T082913Z`
    - local snapshot: `runs/dev_substrate/m8/m8_20260219T082913Z/m8_c_input_readiness_snapshot.json`
    - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T082913Z/m8_c_input_readiness_snapshot.json`
    - result: `overall_pass=true`, blockers empty
    - elapsed: `1.673s`
  - posture:
    - required P7/P8/P9/P10 evidence objects readable and run-scoped,
    - ingest ambiguity indicators resolved at zero,
    - ingest and RTDL offsets semantic minimums pass.

M8.D execution closure (2026-02-19):
  - execution id: `m8_20260219T091250Z`
  - local snapshot: `runs/dev_substrate/m8/m8_20260219T091250Z/m8_d_single_writer_probe_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T091250Z/m8_d_single_writer_probe_snapshot.json`
  - result: `overall_pass=false`, blocker `M8D-B4`
  - probe outcomes:
    - two same-run reporter tasks overlapped (`32.435s`)
    - one task succeeded, one failed with `S3_APPEND_CONFLICT`
    - conflict-signal evidence confirmed; `M8D-B1` cleared
  - fail-closed posture:
    - reporter contention deny behavior exists at append-conflict layer,
    - pinned lock contract (`db_advisory_lock` via `REPORTER_LOCK_*`) is not executable/provable in reporter runtime path.
  - consequence:
    - `M8.D` remains open; `M8.E..M8.I` blocked pending `M8D-B4` remediation + rerun.

M8.D remediation rerun closure (2026-02-19):
  - remediation applied:
    - reporter worker lock path is now explicit (`db_advisory_lock`),
    - reporter runtime env now carries `REPORTER_LOCK_BACKEND` + `REPORTER_LOCK_KEY_PATTERN`,
    - reporter task definition rematerialized to revision `fraud-platform-dev-min-reporter:3`.
  - execution id: `m8_20260219T093130Z`
  - local snapshot: `runs/dev_substrate/m8/m8_20260219T093130Z/m8_d_single_writer_probe_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T093130Z/m8_d_single_writer_probe_snapshot.json`
  - result: `overall_pass=true`, blockers empty
  - probe outcomes:
    - two same-run reporter tasks overlapped (`30.782s`)
    - one task succeeded, one failed closed under lock/conflict posture
    - conflict/lock signals recorded (`lock_conflict_signal_count=9`)
    - no conflicting closure writes observed
  - consequence:
    - `M8.D` is closed
    - `M8.E..M8.I` are unblocked for sequential execution.

M8.E execution closure (2026-02-19):
  - execution id: `m8_20260219T095720Z`
  - local snapshot: `runs/dev_substrate/m8/m8_20260219T095720Z/m8_e_reporter_execution_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T095720Z/m8_e_reporter_execution_snapshot.json`
  - result: `overall_pass=true`, blockers empty
  - runtime outcomes:
    - reporter one-shot task `89ce923388114e13932d3b793d790b47` exited `0`
    - lock lifecycle evidence present (`attempt/acquired/released`)
    - no lock-denied signal and no fatal runtime pattern
  - elapsed: `77.158s`
  - consequence:
    - `M8.E` is closed
    - `M8.F..M8.I` are unblocked for sequential execution.

M8.F execution closure (2026-02-19):
  - fail-first witness:
    - execution id: `m8_20260219T104212Z`
    - local snapshot: `runs/dev_substrate/m8/m8_20260219T104212Z/m8_f_bundle_completeness_snapshot.json`
    - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T104212Z/m8_f_bundle_completeness_snapshot.json`
    - posture: fail-closed witness only; rerun produced canonical blocker classification.
  - canonical rerun:
    - execution id: `m8_20260219T104508Z`
    - local snapshot: `runs/dev_substrate/m8/m8_20260219T104508Z/m8_f_bundle_completeness_snapshot.json`
    - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T104508Z/m8_f_bundle_completeness_snapshot.json`
    - result: `overall_pass=false`, blocker `M8F-B1`
    - elapsed: `11.756s`
  - drift evidence:
    - required bundle targets missing: `run_completed.json`, `obs/run_report.json`, `obs/reconciliation.json`, `obs/replay_anchors.json`, `obs/environment_conformance.json`, `obs/anomaly_summary.json`
    - observed non-substitute Obs files: `obs/platform_run_report.json`, `obs/governance/events.jsonl`
  - consequence:
    - `M8.F` remains open fail-closed
    - `M8.G..M8.I` remain blocked pending `M8F-B1` remediation + rerun.
  - remediation closure:
    - reporter task definition rematerialized to `fraud-platform-dev-min-reporter:4`
    - image digest: `sha256:2072e48137013851c349e9de2e5e0b4a8a2ff522d0a0db1ef609970d9c080c54`
    - `M8.E` rerun:
      - execution id: `m8_20260219T111715Z`
      - local snapshot: `runs/dev_substrate/m8/m8_20260219T111715Z/m8_e_reporter_execution_snapshot.json`
      - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T111715Z/m8_e_reporter_execution_snapshot.json`
      - result: `overall_pass=true`, blockers empty
    - `M8.F` rerun:
      - execution id: `m8_20260219T111902Z`
      - local snapshot: `runs/dev_substrate/m8/m8_20260219T111902Z/m8_f_bundle_completeness_snapshot.json`
      - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T111902Z/m8_f_bundle_completeness_snapshot.json`
      - result: `overall_pass=true`, blockers empty
    - required bundle targets now present + run-scoped:
      - `run_completed.json`
      - `obs/run_report.json`
      - `obs/reconciliation.json`
      - `obs/replay_anchors.json`
      - `obs/environment_conformance.json`
      - `obs/anomaly_summary.json`
  - consequence (current):
    - `M8.F` is closed
    - `M8.G..M8.I` are unblocked for sequential execution.

M8.G execution closure (2026-02-19):
  - execution id: `m8_20260219T114220Z`
  - local snapshot: `runs/dev_substrate/m8/m8_20260219T114220Z/m8_g_replay_reconciliation_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T114220Z/m8_g_replay_reconciliation_snapshot.json`
  - result: `overall_pass=true`, blockers empty
  - coherence outcomes:
    - replay-anchor structure checks passed,
    - anchor count parity checks passed,
    - derived lower-bound checks passed (ingest expected `0` actual `0`; rtdl expected `0` actual `0`),
    - reconciliation checks passed (`status=PASS`, all check-map predicates true),
    - delta non-negativity and cross-artifact arithmetic identities passed.
  - consequence:
    - `M8.G` is closed
    - `M8.H..M8.I` are unblocked for sequential execution.

M8.H execution closure (2026-02-19):
  - execution id: `m8_20260219T120213Z`
  - local snapshot: `runs/dev_substrate/m8/m8_20260219T120213Z/m8_h_obs_gov_closure_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T120213Z/m8_h_obs_gov_closure_snapshot.json`
  - result: `overall_pass=true`, blockers empty
  - closure-surface outcomes:
    - closure marker present and valid (`status=COMPLETED`, run-scoped, required refs present),
    - environment-conformance and anomaly-summary outputs valid and run-scoped,
    - governance surface sample parse and run-scope checks passed,
    - derived-summary boundary checks passed (no base-truth mutation signal).
  - consequence:
    - `M8.H` is closed
    - `M8.I` is unblocked for execution.

M8.I execution closure (2026-02-19):
  - execution id: `m8_20260219T121603Z`
  - local verdict snapshot: `runs/dev_substrate/m8/m8_20260219T121603Z/m8_i_verdict_snapshot.json`
  - durable verdict snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T121603Z/m8_i_verdict_snapshot.json`
  - local handoff artifact: `runs/dev_substrate/m8/m8_20260219T121603Z/m9_handoff_pack.json`
  - durable handoff artifact: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T121603Z/m9_handoff_pack.json`
  - result:
    - `overall_pass=true`
    - blockers empty
    - verdict `ADVANCE_TO_M9`
    - non-secret policy pass with zero violations
  - consequence:
    - `M8.I` is closed
    - M8 execution lanes are complete and ready for user-governed M9 activation.

Sub-phase progress:
  - [x] `M8.A` P11 authority + handles closure.
  - [x] `M8.B` reporter runtime + lock readiness.
  - [x] `M8.C` closure input evidence readiness.
  - [x] `M8.D` single-writer contention fail-closed probe.
  - [x] `M8.E` reporter one-shot execution.
  - [x] `M8.F` closure evidence bundle completeness.
  - [x] `M8.G` replay anchor + reconciliation coherence.
  - [x] `M8.H` closure marker + env/anomaly outputs verification.
  - [x] `M8.I` P11 verdict + M9 handoff.

M8 DoD checklist:
- [x] Single-writer reporter lock is enforced and evidenced.
- [x] Required Obs/Gov closure artifacts are durable and run-scoped.
- [x] Replay anchors and reconciliation are coherent with prior phase evidence.
- [x] `run_completed.json` exists and references correct `platform_run_id`.
- [x] M8 verdict is `ADVANCE_TO_M9` with empty blocker rollup.
- [x] M9 handoff pack is published and non-secret.

## M9 - P12 Teardown
Status: `DONE`
Entry gate:
- M8 is `DONE`.
- M8 verdict is `ADVANCE_TO_M9`.
- M9 handoff pack is present:
  - local: `runs/dev_substrate/m8/m8_20260219T121603Z/m9_handoff_pack.json`
  - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m8_20260219T121603Z/m9_handoff_pack.json`.

Objective:
- Execute deterministic, cost-safe P12 teardown on managed substrate while preserving required long-lived evidence/object-store surfaces.

Scope:
- Teardown execution lanes only via managed control-plane workflows (no local secret-bearing destroy path).
- demo/runtime resource destroy, residual-resource checks, demo-scoped secret cleanup, and teardown-proof publication.
- cost posture verification after teardown.

Out of scope:
- deletion of retained evidence/object-store buckets,
- Learning/Registry rollout.

Decision pin (closed):
- M9 uses one canonical stack-aware teardown workflow:
  - `.github/workflows/dev_min_confluent_destroy.yml`
  - `stack_target=confluent|demo`.

Phase closure posture:
- Detailed M9 authority file:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M9.build_plan.md`.
- M9 sub-phase progression model:
  - `M9.A` authority + handoff closure matrix for P12,
  - `M9.B` teardown inventory + preserve-set freeze,
  - `M9.C` Confluent teardown execution (unified workflow, `stack_target=confluent`),
  - `M9.D` demo stack teardown execution (unified workflow, `stack_target=demo`),
  - `M9.E` post-destroy residual-resource verification,
  - `M9.F` demo-scoped secret/credential cleanup verification,
  - `M9.G` cost-guardrail snapshot after teardown,
  - `M9.H` teardown-proof artifact assembly/publication,
  - `M9.I` M9 verdict rollup + M10 handoff pack publication.
- M9 expansion state:
  - `M9.A` is expanded to execution-grade with deterministic handoff/handle-closure algorithm and snapshot contract.
  - `M9.A` execution is green with blockers empty; `M9.B` is unblocked.
  - `M9.B` is expanded to execution-grade with deterministic destroy/preserve inventory algorithm and overlap/scope guards.
  - `M9.B` execution is green with blockers empty; `M9.C` is unblocked.
  - `M9.C` is expanded to execution-grade with deterministic workflow-dispatch/poll/verification algorithm and snapshot contract.
  - `M9.C` execution is green with blockers empty; `M9.D` is unblocked.
  - `M9.D` is expanded to execution-grade with deterministic managed-lane dispatch/poll/verification algorithm and preserve-control drift gate.
  - `M9.D` execution is green with blockers empty; `M9.E` is unblocked.
  - `M9.E` is expanded to execution-grade with deterministic residual scan/blocker mapping/snapshot contract.
  - `M9.E` execution is green with blockers empty; `M9.F` is unblocked.
  - `M9.F` is expanded to execution-grade with deterministic metadata-only SSM cleanup verification and snapshot contract.
  - `M9.F` execution is green with blockers empty; `M9.G` is unblocked.
  - `M9.G` is expanded to execution-grade with deterministic cross-platform (`AWS + Confluent Cloud`) cost posture validation and post-teardown footgun checks.
  - `M9.G` was executed AWS-only; scope uplift reopens `M9.G` until Confluent billing is included.
  - managed Confluent billing lane is implemented in `.github/workflows/dev_min_m9g_confluent_billing.yml`.
  - cost-optimization posture is pinned in `platform.M9.build_plan.md` (phase-aware start/stop, `RunTask` conversion, TTL teardown, right-sizing, mandatory cross-platform gate).
  - managed optimization lanes are now implemented:
    - `.github/workflows/dev_min_ecs_phase_profile.yml`
    - `.github/workflows/dev_min_idle_teardown_guard.yml`
    - `.github/workflows/dev_min_ecs_rightsizing_report.yml`
    - `.github/workflows/dev_min_m9g_cost_guardrail.yml`
  - note: these controls supersede historical M4 always-on singleton posture for current dev operations (default-off + explicit phase activation).
  - `M9.I` is now expanded to execution-grade with deterministic source-matrix rollup (`M9.A..M9.H`), predicate-based verdict (`ADVANCE_TO_M10|HOLD_M9`), non-secret handoff policy, and local+durable artifact contract (`m9_i_verdict_snapshot.json`, `m10_handoff_pack.json`).
  - `M9.I` execution closed fail-closed after two scanner false-positive attempts and one authoritative pass run (`m9_20260219T191706Z`) with `verdict=ADVANCE_TO_M10`.

Sub-phase progress:
  - [x] `M9.A` P12 authority + handoff closure.
  - [x] `M9.B` teardown inventory + preserve-set freeze.
  - [x] `M9.C` Confluent teardown execution (existing workflow lane).
  - [x] `M9.D` demo stack teardown execution.
  - [x] `M9.E` post-destroy residual checks.
  - [x] `M9.F` demo-scoped secret cleanup verification.
  - [x] `M9.G` post-teardown cost-guardrail snapshot (cross-platform).
  - [x] `M9.H` teardown-proof artifact publication.
  - [x] `M9.I` M9 verdict + M10 handoff.

M9.A execution closure (2026-02-19):
  - execution id: `m9_20260219T123856Z`
  - local snapshot: `runs/dev_substrate/m9/m9_20260219T123856Z/m9_a_handle_handoff_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T123856Z/m9_a_handle_handoff_snapshot.json`
  - result: `overall_pass=true`, blockers empty
  - gate outcomes:
    - M8 verdict/handoff gate checks pass (`ADVANCE_TO_M9`, `overall_pass=true`, blocker-free phase matrix)
    - run-scope continuity pass (`platform_20260213T214223Z`)
  - handle closure outcomes:
    - `resolved_handle_count=28`
    - `unresolved_handle_count=0`
    - placeholder/wildcard required handles: none
  - consequence:
    - `M9.A` is closed
    - `M9.B` is unblocked.

M9.B execution closure (2026-02-19):
  - execution id: `m9_20260219T125838Z`
  - local snapshot: `runs/dev_substrate/m9/m9_20260219T125838Z/m9_b_teardown_inventory_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T125838Z/m9_b_teardown_inventory_snapshot.json`
  - result: `overall_pass=true`, blockers empty
  - validation outcomes:
    - destroy-set is explicit and demo/confluent scoped,
    - preserve-set includes retained core buckets + state/budget surfaces,
    - overlap targets: none,
    - destroy-scope violations: none,
    - preserve-missing targets: none.
  - consequence:
    - `M9.B` is closed
    - `M9.C` is unblocked.

M9.C execution closure (2026-02-19):
  - execution id: `m9_20260219T131353Z`
  - workflow run id/url:
    - `22183221157`
    - `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22183221157`
  - source snapshot:
    - local artifact: `runs/dev_substrate/m9/m9_20260219T131353Z/workflow_artifacts/dev-min-confluent-destroy-20260219T131335Z/confluent_destroy_snapshot.json`
    - durable uri: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m2i_confluent_destroy_20260219T131335Z/confluent_destroy_snapshot.json`
  - local snapshot: `runs/dev_substrate/m9/m9_20260219T131353Z/m9_c_confluent_destroy_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T131353Z/m9_c_confluent_destroy_snapshot.json`
  - result: `overall_pass=true`, blockers empty
  - semantic outcomes:
    - `destroy_outcome=success`
    - `post_destroy_state_resource_count=0`
    - source `overall_pass=true`
  - consequence:
    - `M9.C` is closed
    - `M9.D` is unblocked.

M9.D execution closure (2026-02-19):
  - execution id: `m9_20260219T150604Z`
  - workflow run id/url:
    - `22187272766`
    - `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22187272766`
  - source snapshot:
    - durable uri: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/teardown_demo_20260219T150604Z/demo_destroy_snapshot.json`
  - local snapshot: `runs/dev_substrate/m9/m9_20260219T150604Z/m9_d_demo_destroy_snapshot.json`
  - result: `overall_pass=true`, blockers empty
  - semantic outcomes:
    - `destroy_outcome=success`
    - `post_destroy_state_resource_count=0`
    - source `overall_pass=true`
  - consequence:
    - `M9.D` is closed
    - `M9.E` is unblocked.

M9.E execution closure (2026-02-19):
  - execution id: `m9_20260219T153208Z`
  - local snapshot: `runs/dev_substrate/m9/m9_20260219T153208Z/m9_e_post_destroy_residual_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T153208Z/m9_e_post_destroy_residual_snapshot.json`
  - result: `overall_pass=true`, blockers empty
  - residual outcomes:
    - ECS services: `0` total, `0` residual
    - ECS running tasks: `0`
    - NAT gateways: `0` non-deleted, `0` demo-scoped residual
    - load balancers: `0` scanned, `0` demo-scoped residual
    - runtime DB state: `not_found`
    - query errors: none
  - consequence:
    - `M9.E` is closed
    - `M9.F` is unblocked.

M9.F execution closure (2026-02-19):
  - execution id: `m9_20260219T155120Z`
  - local snapshot: `runs/dev_substrate/m9/m9_20260219T155120Z/m9_f_secret_cleanup_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T155120Z/m9_f_secret_cleanup_snapshot.json`
  - result: `overall_pass=true`, blockers empty
  - cleanup outcomes:
    - canonical demo-secret targets absent: `7/7`
    - `present_targets=[]`
    - `unknown_targets=[]`
    - `query_errors=[]`
    - `non_secret_policy_pass=true`
  - consequence:
    - `M9.F` is closed
    - `M9.G` is unblocked.

M9.G execution closure (2026-02-19):
  - attempt-1 fail-closed:
    - execution id: `m9_20260219T160439Z`
    - blocker: `M9G-B1` (`ce.get-cost-and-usage` time-period argument formatting error).
  - remediation:
    - reran lane with quoted CE time-period argument (`"Start=<date>,End=<date>"`) and preserved full fail-closed checks.
  - authoritative PASS run:
    - execution id: `m9_20260219T160549Z`
  - local snapshot: `runs/dev_substrate/m9/m9_20260219T160549Z/m9_g_cost_guardrail_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T160549Z/m9_g_cost_guardrail_snapshot.json`
  - result: `overall_pass=true`, blockers empty
  - cost posture outcomes:
    - budget aligned (`fraud-platform-dev-min-budget`, `30 USD`)
    - threshold set present (`10/20/28`)
    - MTD cost `17.8956072585 USD` (`59.6520%` of budget)
    - critical threshold (`28 USD`) not breached
  - post-teardown footgun outcomes:
    - NAT non-deleted: `0`
    - demo-scoped load balancers: `0`
    - ECS desired>0 services: `0`
    - runtime DB state: `not_found`
    - log-retention drift: `0`
  - consequence:
    - `M9.G` is closed
    - `M9.H` is unblocked.

M9.G scope uplift (2026-02-19):
  - policy decision:
    - cost capture for this program must include all active platforms/resources (`AWS + Confluent Cloud`) to avoid surprise charges.
  - effect:
    - previous `M9.G` closure (`m9_20260219T160549Z`) is downgraded to `aws_only_observation`.
    - `M9.G` is reopened under cross-platform scope and must be rerun with Confluent billing included.
  - progression guard:
    - `M9.H` must not execute until reopened `M9.G` passes blocker-free.

M9.G cross-platform rerun attempt (2026-02-19):
  - execution id: `m9_20260219T162445Z`
  - local snapshot: `runs/dev_substrate/m9/m9_20260219T162445Z/m9_g_cost_guardrail_snapshot.json`
  - durable snapshot: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T162445Z/m9_g_cost_guardrail_snapshot.json`
  - result: `overall_pass=false`
  - blocker:
    - `M9G-B8` (`confluent.billing.cost.list` unavailable because Confluent Cloud billing auth context is missing locally)
  - posture:
    - AWS side still healthy (`aws_mtd_cost_amount=17.8956072585`, thresholds match, cost-footgun checks clear)
    - cross-platform closure remains blocked until Confluent MTD billing is captured.
  - remediation path:
    - use managed workflow lane `.github/workflows/dev_min_m9g_confluent_billing.yml` to produce:
      - `evidence/dev_min/run_control/<m9_execution_id>/confluent_billing_snapshot.json`,
    - then rerun `M9.G` rollup using that managed snapshot.

M9.G managed cross-platform closure (2026-02-19):
  - workflow run:
    - `dev-min-m9g-cost-guardrail` run id `22194086983`
    - URL: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22194086983`
    - result: `success`
  - dispatched billing run:
    - `dev-min-m9g-confluent-billing` run id `22194097718`
    - URL: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22194097718`
    - result: `success`
  - authoritative execution id:
    - `m9_20260219T181052Z`
  - local snapshots:
    - `runs/dev_substrate/m9/m9_20260219T181052Z/m9_g_cost_guardrail_snapshot.json`
    - `runs/dev_substrate/m9/m9_20260219T181052Z/confluent_billing_snapshot.json`
  - durable snapshots:
    - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T181052Z/m9_g_cost_guardrail_snapshot.json`
    - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T181052Z/confluent_billing_snapshot.json`
  - result:
    - `overall_pass=true`
    - blockers empty
  - consequence:
    - `M9.G` is closed under cross-platform scope
    - `M9.H` is unblocked.

M9.G post-hardening validation rerun (2026-02-19):
  - trigger:
    - rerun after Copilot-driven workflow hardening patch to reconfirm managed closure behavior.
  - guardrail workflow:
    - run id: `22195574172`
    - URL: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22195574172`
    - result: `success`
  - dispatched billing workflow:
    - run id: `22195586583`
    - URL: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22195586583`
    - result: `success`
  - authoritative execution id:
    - `m9_20260219T185355Z`
  - local snapshots:
    - `runs/dev_substrate/m9/m9_20260219T185355Z/m9_g_cost_guardrail_snapshot.json`
    - `runs/dev_substrate/m9/m9_20260219T185355Z/confluent_billing_snapshot.json`
  - durable snapshots:
    - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T185355Z/m9_g_cost_guardrail_snapshot.json`
    - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T185355Z/confluent_billing_snapshot.json`
  - result:
    - `overall_pass=true`
    - blockers empty
  - note:
    - snapshot `errors[]` includes non-blocking ELB `DescribeLoadBalancers` AccessDenied diagnostic under current lane policy.

M9.G IAM-drift closure rerun (2026-02-19):
  - trigger:
    - remove ELB AccessDenied diagnostic residual from guardrail evidence.
  - IAM remediation:
    - role: `GitHubAction-AssumeRoleWithAction`
    - added inline policy `GitHubActionsM9GuardrailReadOnlyDevMin` granting:
      - `elasticloadbalancing:DescribeLoadBalancers` on `*`.
  - guardrail workflow:
    - run id: `22195781513`
    - URL: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22195781513`
    - result: `success`
  - dispatched billing workflow:
    - run id: `22195792243`
    - URL: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/22195792243`
    - result: `success`
  - authoritative execution id:
    - `m9_20260219T185951Z`
  - local snapshots:
    - `runs/dev_substrate/m9/m9_20260219T185951Z/m9_g_cost_guardrail_snapshot.json`
    - `runs/dev_substrate/m9/m9_20260219T185951Z/confluent_billing_snapshot.json`
  - durable snapshots:
    - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T185951Z/m9_g_cost_guardrail_snapshot.json`
    - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T185951Z/confluent_billing_snapshot.json`
  - result:
    - `overall_pass=true`
    - blockers empty
    - `errors=[]` in guardrail snapshot.

M9.H execution closure (2026-02-19):
  - execution id:
    - `m9_20260219T181800Z`
  - local artifact:
    - `runs/dev_substrate/m9/m9_20260219T181800Z/teardown_proof.json`
  - durable canonical artifact:
    - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T214223Z/teardown/teardown_proof.json`
  - result:
    - `overall_pass=true`
    - blockers empty
  - semantic outcomes:
    - teardown proof is run-scoped (`platform_run_id=platform_20260213T214223Z`)
    - required P12.6 fields are present:
      - teardown timestamp
      - terraform destroy status (`confluent=success`, `demo=success`, `overall=success`)
      - confirmed-absent categories (`ecs_services=false`, `db=false`, `nat_gateway=false`, `load_balancer=false`, `confluent_cluster=false`)
    - source references for `M9.B..M9.G` local + durable artifacts are embedded.
  - consequence:
    - `M9.H` is closed
    - `M9.I` is unblocked.

M9.I execution closure (2026-02-19):
  - attempt-1 fail-closed:
    - execution id: `m9_20260219T191458Z`
    - result: `overall_pass=false`, `verdict=HOLD_M9`
    - blocker: `M9I-B5`
    - cause: false-positive non-secret scan on policy metadata key `non_secret_policy`.
  - attempt-2 fail-closed:
    - execution id: `m9_20260219T191602Z`
    - result: `overall_pass=false`, `verdict=HOLD_M9`
    - blocker: `M9I-B5`
    - cause: broad token scan flagged benign evidence filename reference.
  - remediation:
    - narrowed scanner to credential-shaped detections only while preserving fail-closed behavior.
  - authoritative pass:
    - execution id: `m9_20260219T191706Z`
    - local artifacts:
      - `runs/dev_substrate/m9/m9_20260219T191706Z/m9_i_verdict_snapshot.json`
      - `runs/dev_substrate/m9/m9_20260219T191706Z/m10_handoff_pack.json`
    - durable artifacts:
      - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T191706Z/m9_i_verdict_snapshot.json`
      - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T191706Z/m10_handoff_pack.json`
  - result:
    - `overall_pass=true`
    - `verdict=ADVANCE_TO_M10`
    - blockers empty
    - `source_blocker_rollup=[]`
    - `non_secret_policy.pass=true`
  - consequence:
    - `M9.I` is closed
    - M9 is closed and M10 entry gate is satisfied.

M9 DoD checklist:
- [x] Canonical execution lane is GitHub Actions teardown workflows produced under `M2.I`; no local secret-bearing destroy path is used.
- [x] demo resources are destroyed while retained core/evidence surfaces remain as pinned.
- [x] no demo ECS services/tasks remain and no NAT/LB cost-footgun resources remain.
- [x] demo-scoped secrets/credentials are removed from SSM.
- [x] post-teardown cross-platform (`AWS + Confluent Cloud`) cost guardrail snapshot is captured and blocker-free.
- [x] teardown proof artifact exists locally and durably.
- [x] M9 verdict is `ADVANCE_TO_M10` with empty blocker rollup.

## M10 - Certification (Semantic + Scale)
Status: `ACTIVE`
Entry gate:
- M9 is `DONE`.
- M9->M10 handoff is present:
  - local: `runs/dev_substrate/m9/m9_20260219T191706Z/m10_handoff_pack.json`
  - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T191706Z/m10_handoff_pack.json`.
- Scale thresholds must be pinned before any scale lane execution (no ad hoc pass criteria mid-run).
- Runtime posture remains managed-substrate only (no laptop runtime compute).

Objective:
- Produce certification-grade proof that dev-substrate spine is both semantically correct and operationally credible under scale-oriented conditions.

Scope:
- Semantic certification runs (20-event and 200-event) with deterministic evidence.
- Incident drill execution with fail-closed behavior and replay/audit trace.
- Scale certification runs:
  - representative-window,
  - burst,
  - soak,
  - recovery-under-load.
- Reproducibility proof via second run and deterministic replay-anchor coherence.
- Final certification verdict and evidence bundle publication.

Out of scope:
- Learning/Registry rollout (still baseline out-of-scope).
- Production SLO commitment; this phase is dev certification, not prod go-live.

Failure posture:
- Fail closed on any of:
  - missing/unpinned thresholds before scale lanes,
  - semantic gate failures in 20/200 runs,
  - missing incident drill evidence,
  - scale-lane SLO/gate failure,
  - reproducibility or replay-anchor drift,
  - incomplete certification bundle publication.

Phase closure posture:
- Detailed M10 authority file:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M10.build_plan.md`.
- M10 entry handoff anchor:
  - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m9_20260219T191706Z/m10_handoff_pack.json`.
- M10 sub-phase progression model:
  - `M10.A` authority + threshold pinning + execution matrix freeze.
  - `M10.B` semantic 20-event certification run.
  - `M10.C` semantic 200-event certification run.
  - `M10.D` incident drill execution + evidence closure.
  - `M10.E` representative-window scale run.
  - `M10.F` burst run.
  - `M10.G` soak run.
  - `M10.H` recovery-under-load run.
  - `M10.I` reproducibility + deterministic replay coherence.
  - `M10.J` final certification verdict + portfolio evidence bundle publication.
- M10 expansion state:
  - planning expansion is in progress with deep lane mapping in `platform.M10.build_plan.md`,
  - `M10.A` is now expanded to execution-grade with:
    - entry-gate checks from M9 handoff,
    - deterministic threshold pinning algorithm,
    - explicit snapshot schema and blocker taxonomy,
    - lane-dependency matrix freeze contract for `M10.B..M10.J`,
  - `M10.A` execution is closed green (`m10_20260219T231017Z`) with durable threshold snapshot and blocker-free gate checks,
  - `M10.B` is now expanded to execution-grade with:
    - entry dependency on closed `M10.A`,
    - deterministic semantic verification algorithm for 20-event run,
    - explicit semantic evidence surface contract and snapshot schema,
    - fail-closed blocker taxonomy (`M10B-B1..B5`),
  - `M10.B` runtime lane has been executed and closed pass on `platform_20260219T234150Z`,
  - authoritative closure snapshot: `m10_20260220T032146Z/m10_b_semantic_20_snapshot.json` (`overall_pass=true`, blockers empty).

Sub-phase progress:
  - [x] `M10.A` authority + threshold pinning.
  - [x] `M10.B` semantic 20-event run.
  - [ ] `M10.C` semantic 200-event run.
  - [ ] `M10.D` incident drill execution.
  - [ ] `M10.E` representative-window run.
  - [ ] `M10.F` burst run.
  - [ ] `M10.G` soak run.
  - [ ] `M10.H` recovery-under-load run.
  - [ ] `M10.I` reproducibility + replay coherence.
  - [ ] `M10.J` final certification verdict + bundle publish.

M10 DoD checklist:
- [ ] Semantic Green:
  - [ ] 20-event shakedown run green end-to-end.
  - [ ] 200-event run green end-to-end.
  - [ ] at least one incident drill executed with expected fail-closed evidence.
- [ ] Scale Green:
  - [ ] representative-window run passes on contiguous event-time slice (not sub-second toy slice).
  - [ ] burst run passes at elevated ingest pressure without semantic drift.
  - [ ] soak run passes under sustained load with stable lag/checkpoint behavior.
  - [ ] recovery run passes after controlled restart under load with idempotent outcomes.
- [ ] Reproducibility:
  - [ ] second run demonstrates deterministic replay/evidence coherence.
- [ ] Evidence bundle:
  - [ ] certification bundle is published locally + durably and supports portfolio-grade claim.

---

## 9.1) High-Level Evidence Fidelity Map (Runbook Alignment)
This map keeps high-level planning aligned to runbook evidence obligations.

| Plan Phase | Canonical phase_id | Minimum evidence family expected |
| --- | --- | --- |
| M1 | P(-1) | image provenance snapshot (tag + digest + source SHA) |
| M2 | P0 | substrate apply snapshot + handle resolution proof |
| M3 | P1 | `run.json` manifest with pins + config digest |
| M4 | P2 | daemon readiness snapshot |
| M5 | P3 | stream-sort receipts/manifests + checker pass evidence |
| M6 | P4-P7 | `ingest/ig_ready.json`, `ingest/receipt_summary.json`, `ingest/quarantine_summary.json` (if any), `ingest/kafka_offsets_snapshot.json` |
| M7 | P8-P10 | `rtdl_core/*`, `decision_lane/*`, `case_labels/*` evidence summaries |
| M8 | P11 | `obs/run_report.json`, `obs/reconciliation.json`, `obs/replay_anchors.json`, `obs/environment_conformance.json`, `obs/anomaly_summary.json`, `run_completed.json` |
| M9 | P12 | teardown proof artifact + post-destroy resource check snapshot |
| M10 | certification | semantic run bundles (20/200) + scale-run bundles (window/burst/soak/recovery) + drill refs |

---

## 9.2) Scale-Green Threshold Pinning Rule
Scale validation thresholds must be pinned at M10 phase entry and recorded in:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
- daily logbook entry for the execution day.

Minimum threshold dimensions to pin:
- representative window:
  - contiguous event-time duration,
  - minimum admitted-event count.
- burst:
  - target ingest multiplier versus representative baseline,
  - burst duration.
- soak:
  - sustained runtime duration,
  - lag stability boundary (aligned to runbook lag gates).
- recovery:
  - restart target component(s),
  - recovery time objective and replay/idempotency acceptance checks.

Rule:
- M10 cannot be marked `DONE` if only 20/200 runs are executed.
- 20/200 is mandatory for semantic smoke, but insufficient for dev certification on its own.

---

## 10) Phase Transition Checklist (Mandatory)
Before marking any phase `DONE`:
1. Confirm all DoD checkboxes are objectively satisfied.
2. Confirm evidence objects/files exist at pinned paths.
3. Confirm no drift exceptions remain open.
4. Append decision/action notes:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
   - `docs/logbook/<month>/<day>.md`
5. If USER has given explicit go-ahead, set next phase to `ACTIVE`.
6. If USER has not given explicit go-ahead, leave next phase `NOT_STARTED` and record hold reason.

## 10.1) Transition Authority Rule (User-governed activation)
- Phase completion can be agent-driven once DoD is objectively satisfied.
- Phase activation for the next implementation phase is user-governed.
- No runtime/infra build execution starts for a phase unless that phase is explicitly activated by USER direction.

## 10.2) Decision-Completeness Gate (Fail-Closed)
- A USER "proceed" instruction is not, by itself, authorization to improvise missing decisions.
- Before executing any phase/option/command, the AGENT MUST verify all required decisions/inputs for that scope are explicitly pinned.
- If any required decision/input is missing, execution MUST stop and the AGENT MUST report unresolved items to the USER.
- No defaulting, assumption-filling, or ad hoc expansion is allowed while unresolved items exist.
- Execution can resume only after the unresolved set is explicitly closed by USER direction and recorded in implementation notes/logbook.

## 10.3) Phase-Coverage Law (Anti-Cram, Binding)
- A phase plan MUST expose every required capability lane for that phase before execution starts.
- Capability lanes include, at minimum where applicable: authority/handles, identity/IAM, network, data stores, messaging, secrets, observability/evidence, rollback/rerun, teardown, and budget.
- No phase may be considered execution-ready if any capability lane is only implicit, assumed, or deferred without a pinned closure rule.
- Sub-phase count is not fixed; the plan MUST be expanded until closure-grade coverage is achieved.
- If new blockers reveal an unplanned lane, phase execution pauses and the phase plan is expanded before continuing.

## 11) Risks and Controls (Pinned)
R1: Semantic drift under delivery pressure  
Control: fail-closed drift sentinel + no phase advance without evidence.

R2: Hidden local dependency reintroduced  
Control: explicit no-local-compute and external-prestaged P3 inlet policy.

R3: Incomplete closure accepted as green  
Control: phase DoD + evidence checks + no halfbaked transitions.

R4: Cost leakage after demos  
Control: required P12 teardown proof and budget guardrails.

## 12) Immediate Next Action
M10 is active for planning expansion under the M9 handoff.
Next action:
- execute `M10.C` semantic 200-event certification run using the same evidence-contract posture that closed `M10.B`.

