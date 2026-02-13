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
- [ ] Single-image contract is explicitly documented.
- [ ] Immutable tag contract is pinned and maps to handles registry keys.
- [ ] Mutable convenience tag posture is clearly non-authoritative.

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
- [ ] Full entrypoint matrix exists with zero missing in-scope components.
- [ ] Every entrypoint has a deterministic invocation contract.
- [ ] Validation method is pinned (what proves entrypoint exists and is callable).

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
- [ ] Provenance field set is complete.
- [ ] Evidence path contract is pinned and run-scoped.
- [ ] Mismatch handling is fail-closed.

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
- [ ] M1.A complete
- [ ] M1.B complete
- [ ] M1.C complete
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
