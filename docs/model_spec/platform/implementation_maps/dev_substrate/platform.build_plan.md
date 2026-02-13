# Dev Substrate Migration Build Plan (Fresh Start)
_Track: local_parity -> dev_min managed substrate (Spine Green v0)_
_Last updated: 2026-02-13_

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
- P3 seed/sync is S3->S3 only (no local bootstrap path).
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
| M3 | P1 | Run pinning + run manifest evidence | ACTIVE |
| M4 | P2 | Daemon bring-up on ECS with run-scope controls | NOT_STARTED |
| M5 | P3 | Oracle lane (seed/sort/checker) | NOT_STARTED |
| M6 | P4-P7 | Control+Ingress closure | NOT_STARTED |
| M7 | P8-P10 | RTDL + Case/Labels closure | NOT_STARTED |
| M8 | P11 | Obs/Gov closure | NOT_STARTED |
| M9 | P12 | Teardown proof + cost guardrails | NOT_STARTED |
| M10 | certification | Semantic Green + Scale Green certification | NOT_STARTED |

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
- `M4..M10`: deferred until phase activation is approved.

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
- `M3` is `ACTIVE` for deep planning and closure-hardening.

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
- [x] No NAT and no forbidden always-on infra posture is proven.
- [x] runtime DB and migration readiness are validated.
- [x] Budget alerts and teardown viability are evidenced.

---

## M3 - P1 Run pinning
Status: `ACTIVE`

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

Active-phase planning posture:
- Detailed M3 authority file: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M3.build_plan.md`.
- M3.A planning status:
  - closure matrix + verification catalog executed,
  - latest authoritative run: `m3a_20260213T213547Z`,
  - blocker posture: `M3A-B1` resolved (no open M3.A blocker),
  - evidence:
    - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3a_20260213T213547Z/m3_a_handle_closure_snapshot.json`.
- Sub-phase progress:
  - [x] `M3.A` authority + handle closure matrix for P1.
  - [ ] `M3.B` run identity generation contract (`platform_run_id` uniqueness).
  - [ ] `M3.C` run config payload + deterministic digest contract.
  - [ ] `M3.D` durable run evidence publication (`run.json` + start marker).
  - [ ] `M3.E` runtime scope export handoff for M4.
  - [ ] `M3.F` pass gates + blocker model closure.
  - [ ] `M3.G` M4 handoff artifact publication + readiness verdict.

M3 DoD checklist:
- [ ] `platform_run_id` is generated and collision-checked.
- [ ] run config payload is canonicalized and digest-complete.
- [ ] `run.json` exists at run evidence root and is structurally complete.
- [ ] runtime scope export (`REQUIRED_PLATFORM_RUN_ID`) is prepared for M4 consumers.
- [ ] M3 closeout verdict + handoff artifact are published and non-secret.

---

## 9) Remaining Phases (Gate-Level Only Until Activation)

## M4 - P2 Daemon bring-up
Status: `NOT_STARTED`
Entry gate:
- M3 is `DONE`.
DoD summary:
- required services/tasks run on ECS only.
- run-scope enforcement active (`REQUIRED_PLATFORM_RUN_ID` semantics).
- service replica posture is deterministic for v0 (single replica per daemon/service).
- daemon readiness snapshot evidence is written.

## M5 - P3 Oracle lane
Status: `NOT_STARTED`
Entry gate:
- M4 is `DONE`.
DoD summary:
- seed/sort/checker complete via managed compute.
- stream_view manifests + sort receipts present.
- strict S3->S3 source policy enforced.
- checker PASS evidence is present and fail-closed on partial/invalid outputs.

## M6 - P4-P7 Control + Ingress closure
Status: `NOT_STARTED`
Entry gate:
- M5 is `DONE`.
DoD summary:
- P4: IG auth + health contract passes (`/v1/ops/health` and ingest auth fail-closed behavior).
- P5: SR gate/lease passes and READY publish evidence exists.
- P6: WSP streams from P3 `stream_view` only, with deterministic identity/retry posture.
- P7: IG commit evidence includes receipt/quarantine summaries and Kafka offsets snapshot.
- no unresolved `PUBLISH_AMBIGUOUS` for closure set.

## M7 - P8-P10 RTDL + Case/Labels closure
Status: `NOT_STARTED`
Entry gate:
- M6 is `DONE`.
DoD summary:
- P8: RTDL core catch-up evidence exists and lag <= `RTDL_CAUGHT_UP_LAG_MAX`.
- P8: archive durability evidence is present (archive objects plus durable offset progress evidence).
- P9: decision lane + DLA evidence exists with append-only/idempotent posture preserved.
- P10: case + label evidence exists, append-only posture preserved, and managed DB runtime state is used.

## M8 - P11 Obs/Gov closure
Status: `NOT_STARTED`
Entry gate:
- M7 is `DONE`.
DoD summary:
- single-writer reporter lock enforced.
- run report, reconciliation, conformance, replay anchors produced.
- run closure marker written.
- concurrent reporter/manual closeout contention fails closed with explicit conflict evidence.

## M9 - P12 Teardown
Status: `NOT_STARTED`
Entry gate:
- M8 is `DONE`.
DoD summary:
- demo resources destroyed; core/evidence preserved.
- no demo ECS services/tasks remain and no NAT/LB cost-footgun resources remain.
- demo-scoped secrets/credentials are removed from SSM.
- teardown proof artifact exists.

## M10 - Certification (Semantic + Scale)
Status: `NOT_STARTED`
Entry gate:
- M9 is `DONE` for dry cycle OR explicit rerun approved.
- Scale thresholds are pinned before execution (no ad hoc pass criteria during run).
DoD summary:
- Semantic Green:
  - 20-event shakedown run green end-to-end.
  - 200-event run green end-to-end.
  - at least one incident drill is executed with expected fail-closed evidence.
- Scale Green:
  - representative-window run passes on contiguous event-time slice (not sub-second toy slice).
  - burst run passes at elevated ingest pressure without semantic drift.
  - soak run passes under sustained load with stable lag/checkpoint behavior.
  - recovery run passes after controlled restart under load with idempotent outcomes.
- evidence bundle supports portfolio-grade claim.
- replay-anchor narrative is demonstrable from evidence artifacts.

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
| M8 | P11 | `obs/run_report.json`, `obs/reconciliation.json`, `obs/environment_conformance.json`, replay anchors, `run_completed.json` |
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
Control: explicit no-local-compute and S3->S3 P3 policy.

R3: Incomplete closure accepted as green  
Control: phase DoD + evidence checks + no halfbaked transitions.

R4: Cost leakage after demos  
Control: required P12 teardown proof and budget guardrails.

## 12) Immediate Next Action
M3 is active for deep planning and execution preparation.
Next action:
- execute `M3.B` run-identity generation contract with collision-safe evidence,
- continue M3 deep-plan progression (`M3.C -> M3.G`) with explicit evidence artifacts,
- maintain fail-closed posture: no M4 activation until M3 verdict is `ADVANCE_TO_M4` with durable handoff artifacts.
