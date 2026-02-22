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
2. Build execution is hard-blocked if `ECR_REPO_URI` is unresolved (`M1-B1` from M0.D).
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

DoD:
- [ ] image strategy is explicit and authority-aligned.
- [ ] immutable tag/digest posture is explicit.
- [ ] content boundary is explicit and auditable.
- [ ] no local-only/runtime-irrelevant payloads are in authoritative build context.

## M1.B Entrypoint Matrix Closure
Goal:
- prove packaging surface can start all required execution modes.

Tasks:
1. Enumerate entrypoints for all required lanes:
   - spine (`SR`, `WSP`, `IG`, RTDL workers, Case/Labels, reporter),
   - learning (`OFS`, `MF`, `MPR` dispatch/runtime hooks).
2. Map each to deterministic invocation contract (module + required args).
3. Define validation method for build-go pass (`--help`/dry invocation contracts).

DoD:
- [ ] matrix covers all required handles in registry.
- [ ] each entrypoint has deterministic invocation contract.
- [ ] validation method is pinned and reproducible.

## M1.C Provenance and Evidence Contract
Goal:
- make `P(-1)` output auditable and replay-safe.

Tasks:
1. Pin required provenance fields (`image_tag`, `image_digest`, `git_sha`, build metadata).
2. Map `P(-1)` evidence paths to run-scoped S3 handles.
3. Pin mismatch handling rules (`tag->digest`, digest mismatch, missing evidence).

DoD:
- [ ] provenance field set complete.
- [ ] evidence paths and run-linkage contract explicit.
- [ ] mismatch policy is fail-closed.

## M1.D Security and Secret Injection Contract
Goal:
- enforce production-like secret posture at packaging layer.

Tasks:
1. Pin no-baked-secret policy for image build.
2. Pin runtime secret source expectations (SSM/Secrets Manager handles).
3. Define packaging-time leakage checks (context lint + env policy).

DoD:
- [ ] no-baked-secret policy explicit and testable.
- [ ] runtime secret source contract explicit.
- [ ] leak-check criteria defined for build-go.

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

## 6) Blocker Taxonomy (M1)
- `M1-B1`: `ECR_REPO_URI` unresolved (hard blocker for packaging execution).
- `M1-B2`: entrypoint coverage incomplete for required lanes.
- `M1-B3`: provenance/evidence contract ambiguous or inconsistent.
- `M1-B4`: secret posture incomplete or leakage checks undefined.
- `M1-B5`: build-go transition remains ambiguous.

Any active `M1-B*` blocker prevents M1 execution closure.

## 7) M1 Completion Checklist
- [ ] M1.A complete.
- [ ] M1.B complete.
- [ ] M1.C complete.
- [ ] M1.D complete.
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
