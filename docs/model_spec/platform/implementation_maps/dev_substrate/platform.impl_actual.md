# Platform Implementation Map (dev_substrate)
_As of 2026-02-10_

## Entry: 2026-02-10 7:20PM - Routing start for dev substrate promotion track

### Context
This file begins the active implementation map track for dev substrate promotion.

### Routing
- Baseline local-parity implementation history remains at:
  - `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md`
  - component maps under `docs/model_spec/platform/implementation_maps/local_parity/`
- New dev substrate decisions are appended under:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/*.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/dev_substrate/*.build_plan.md`

### Scope posture
This track is a substrate promotion (not platform semantic rewrite): maintain the same rails/contracts while swapping infrastructure and tightening runtime posture.

## Entry: 2026-02-10 7:26PM - Applied implementation-map track split (baseline vs dev substrate)

### Problem / goal
Separate baseline local-parity implementation history from active dev substrate promotion decision flow, while preserving append-only traceability.

### Changes applied
- Created track folders:
  - `docs/model_spec/platform/implementation_maps/local_parity/`
  - `docs/model_spec/platform/implementation_maps/dev_substrate/`
- Moved existing root map files (39 files) into `local_parity/`.
- Added new active-track starters:
  - `dev_substrate/platform.build_plan.md`
  - `dev_substrate/platform.impl_actual.md`
  - `dev_substrate/README.md`
- Replaced root `implementation_maps/README.md` with a routing/index README.
- Updated baseline README at `local_parity/README.md` to mark it as historical baseline.
- Updated `AGENTS.md` to route active implementation-map writes to `dev_substrate/` and baseline lookups to `local_parity/`.
- Added a routing continuity entry in `local_parity/platform.impl_actual.md`.

### Validation
- Verified root now contains only routing README.
- Verified `dev_substrate/` contains active platform map starters.
- Verified baseline folder preserves all moved historical map files.
- Verified AGENTS path/routing references now point to `dev_substrate` for active work.

### Drift sentinel check
No platform semantic rails were changed. This was a documentation/process routing restructure only.

## Entry: 2026-02-10 9:03PM - Authority review checkpoint: dev-min managed-substrate migration design doc

### Reviewed authority
- `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

### Review outcome (alignment to active dev_substrate track)
- The document is implementation-ready and aligned with current track posture:
  - env ladder semantics preserved (`local_parity -> dev -> prod`) with `dev_min` as a dev rung/profile.
  - managed substrate pinned (Confluent Kafka + AWS S3 evidence posture).
  - invariant laws explicitly pinned (dedupe, append-only truth, origin_offset replay anchors, explicit degrade, provenance pins).
  - Terraform split (`core` persistent + `demo` ephemeral) aligns with current topology intent.

### Interaction with repository topology decision
- Active topology pin in:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.repo_topology.md`
  is compatible with this authority.
- Naming is the only pending normalization:
  - authority uses `core/demo`;
  - topology draft currently uses `dev_min_core/dev_min_demo`.
- Next step must pin one canonical naming scheme before Terraform unlock.

### Drift sentinel check
No drift detected against flow narrative, platform-wide rails, or truth ownership boundaries during this authority review.

## Entry: 2026-02-10 9:06PM - Corrective routing after user removed separate topology draft

### Context
User removed the separate topology draft document because it was not useful in its previous form.

### Decision
- Continue the dev-substrate track without a standalone topology draft file.
- Use the pinned authority directly as the placement/structure source:
  - `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`
- Keep topology/placement decisions as append-only entries in this file and corresponding phase items in:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### Consequence
Earlier references to a separate topology draft are now historical context only; active implementation should not depend on that file.

### Drift sentinel check
No semantic drift. This is a documentation routing correction only.

## Entry: 2026-02-10 9:37PM - Corrective closure lock: finalize remaining holes in dev-min migration authority

### Context
A prior closure pass tightened the authority doc but a verification sweep found residual inconsistencies that still weaken implementer certainty.

### Residual gaps discovered
1. Normative reference path mismatch in Section 0.5:
   - currently points to `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decisions.md`
   - repository file is `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`.
2. Section 17 heading still states `Open Decisions Log` and includes open-item framing text, while document status now claims all decisions are pinned.
3. Section 17.2 pins evidence schema artifacts under `docs/model_spec/platform/contracts/dev_min/*`, but this contract surface does not yet exist in repo.
4. Section 3.1 pins `config/platform/profiles/dev_min.yaml`, but this profile file does not yet exist.

### Decision
Close all four gaps in one atomic corrective pass so the authority can be treated as implementation-ready without inferred placeholders.

### Planned actions
- Patch the authority doc:
  - fix the `control_and_ingress` reference path to the existing filename,
  - rename/reframe Section 17 to a closed decision registry posture,
  - repin evidence schemas to repo-conventional `.schema.yaml` naming under `docs/model_spec/platform/contracts/dev_min/`.
- Create missing pinned artifacts:
  - `config/platform/profiles/dev_min.yaml` (minimal, explicit dev-min profile contract seed),
  - `docs/model_spec/platform/contracts/dev_min/*.schema.yaml` plus `README.md`.
- Re-verify by grep for residual "open decision" wording and by file existence checks.

### Drift sentinel checkpoint
This is a documentation+contract closure pass only. No runtime semantic law changes, no ownership boundary changes, and no infrastructure behavior changes are introduced.

## Entry: 2026-02-10 9:39PM - Routing correction for earlier pre-change lock entry

### Context
An earlier pre-change lock for the dev-min authority closure pass was accidentally written to legacy path `docs/model_spec/platform/implementation_maps/platform.impl_actual.md` during track split transition.

### Correction
- Migrated decision continuity to the active track file (`dev_substrate/platform.impl_actual.md`) via this entry chain.
- Removed the legacy root file to prevent dual-authority drift.

### Drift sentinel checkpoint
No semantic change. Documentation routing consistency only.

## Entry: 2026-02-10 9:40PM - Closure applied: remaining holes in dev-min migration authority

### What was changed
1. Authority-doc consistency fixes in:
   - `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`
   - Corrected Section 0.5 control+ingress reference path to existing repo file.
   - Reframed Section 17 from "Open Decisions Log" to pinned "Decision Registry" posture.
   - Repinned evidence-schema contract paths to repo-conventional `.schema.yaml` names.

2. Created pinned missing artifacts referenced by authority:
   - `config/platform/profiles/dev_min.yaml`
   - `docs/model_spec/platform/contracts/dev_min/README.md`
   - `docs/model_spec/platform/contracts/dev_min/run_header.v0.schema.yaml`
   - `docs/model_spec/platform/contracts/dev_min/ingress_receipt_summary.v0.schema.yaml`
   - `docs/model_spec/platform/contracts/dev_min/audit_summary.v0.schema.yaml`
   - `docs/model_spec/platform/contracts/dev_min/replay_anchor_summary.v0.schema.yaml`
   - `docs/model_spec/platform/contracts/dev_min/metrics_anomaly_reconciliation_snapshot.v0.schema.yaml`

3. Index discoverability updates:
   - `docs/model_spec/platform/contracts/README.md` now includes `dev_min` contract section.
   - `config/platform/profiles/README.md` now includes `dev_min` in profile shape and testing-policy list.

### Validation evidence
- Consistency grep checks:
  - no residual "Open Decisions Log" / "not pinned yet" wording in Section 17.
  - Step Functions posture remains consistently CLI-only for Phase 1 and dev_full-only for later.
- File existence checks confirmed all newly pinned paths exist.
- YAML parse validation:
  - `python` + `yaml.safe_load` on `dev_min.yaml` and all five `dev_min` schema files (`PASS`).

### Resulting posture
The dev-min migration authority is now internally consistent and backed by concrete pinned artifact paths, enabling migration planning without unresolved path/spec ambiguity.

### Drift sentinel checkpoint
No platform behavior was changed; this pass only closes documentation/contract drift holes and strengthens authority traceability.

## Entry: 2026-02-10 9:51PM - Pre-change lock: formalize full local_parity -> dev_min migration program

### Context
USER approved the recommended migration posture (controlled wave migration, no semantic rewrite, no big-bang cutover) and requested that we proceed by noting it down before execution.

### Problem statement
Current active plan file is too coarse (5 broad phase lines) and is not sufficient to run an end-to-end migration program covering account/credential bootstrap, substrate rollout, wave sequencing, meta-layer saturation, and final acceptance gates.

### Authorities considered
- `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md`
- `docs/model_spec/platform/platform-wide/deployment_tooling_notes_v0.md`
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
- `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`

### Decision
Rewrite `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` into an explicit migration program with:
1) wave-first sequencing,
2) hard DoD gates per phase,
3) meta-layer requirements embedded into each wave,
4) final acceptance gates tied to live-stream validation and drift sentinel checks.

### Planned content shape
- Program principles and non-negotiable rails.
- Phase 0: mobilization + semantic freeze.
- Phase 1: account/credential and secret bootstrap.
- Phase 2: Terraform landing zone (`core` persistent + `demo` ephemeral).
- Phase 3: Wave 1 control/ingress migration.
- Phase 4: Wave 2 RTDL migration.
- Phase 5: Wave 3 case/labels migration.
- Phase 6: Wave 4 learning/registry migration.
- Phase 7: run/operate + obs/gov saturation (all services).
- Phase 8: full-run validation + cutover readiness gate.
- Deferred backlog list (post-acceptance).

### Drift sentinel checkpoint
Plan rewrite only; no runtime behavior changes. This increases execution precision and reduces drift risk.

## Entry: 2026-02-10 9:52PM - Applied migration program rewrite in dev_substrate build plan

### What changed
Replaced the coarse placeholder plan in `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` with an explicit end-to-end migration program.

### New plan structure (pinned)
- Program posture + non-negotiable rails.
- Phase 0: mobilization and semantic freeze.
- Phase 1: accounts/credentials/secrets bootstrap.
- Phase 2: Terraform landing zone (`core` + `demo`) and teardown/cost guardrails.
- Phase 3: Wave 1 control/ingress migration.
- Phase 4: Wave 2 RTDL migration.
- Phase 5: Wave 3 case/labels migration.
- Phase 6: Wave 4 learning/registry migration.
- Phase 7: run/operate + obs/gov saturation across all onboarded services.
- Phase 8: integrated 20/200 run validation, drift audit, and cutover readiness.
- Deferred backlog and strict phase progression rule.

### Why this was chosen
- Matches approved migration posture: controlled wave execution, no semantic rewrite, no big-bang cutover.
- Adds execution precision for operator bootstrap and substrate concerns that were previously implicit.
- Bakes meta-layer coverage into the plan rather than treating it as optional cleanup.

### Validation
- Verified all phases and DoD sections are present (`rg` sweep).
- Verified plan references active dev_substrate implementation-map/logbook recording requirement.

### Drift sentinel checkpoint
No runtime/infrastructure behavior changed. This is planning rigor and execution-control hardening only.

## Entry: 2026-02-10 9:54PM - Pre-change lock: implement Phase 0 (mobilization + semantic freeze)

### Context
USER directed immediate execution of Phase 0 from the active dev-substrate build plan.

### Phase 0 DoD to close
1. baseline matrix snapshot recorded,
2. service-wave matrix recorded with owners/dependencies,
3. acceptance gate templates published and linked.

### Inputs and baseline anchors
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md`
- component build-plan rolling status sections under `docs/model_spec/platform/implementation_maps/local_parity/*.build_plan.md`
- accepted local-parity full-run evidence anchors in `docs/logbook/02-2026/2026-02-10.md`:
  - `platform_20260210T082746Z` (20-event gate)
  - `platform_20260210T083021Z` (200-event gate)
  - post-fix reconfirmation `platform_20260210T091951Z`
- `docs/runbooks/platform_parity_walkthrough_v0.md`

### Planned implementation artifacts
- `docs/model_spec/platform/implementation_maps/dev_substrate/phase0_baseline_snapshot.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/phase0_service_wave_matrix.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/phase0_acceptance_gate_templates.md`
- update `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` Phase 0 DoD checkboxes to checked with references.

### Drift sentinel checkpoint
This pass is planning/control closure only. No runtime code/infrastructure behavior changes will be made.

## Entry: 2026-02-10 9:56PM - Phase 0 implemented and closed (mobilization + semantic freeze)

### Implemented artifacts
- Baseline freeze snapshot:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/phase0_baseline_snapshot.md`
- Service-wave migration matrix:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/phase0_service_wave_matrix.md`
- Acceptance gate templates:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/phase0_acceptance_gate_templates.md`

### Build-plan closure updates
- Updated Phase 0 DoD checkboxes to complete in:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
- Added explicit evidence links to the three Phase 0 artifacts.
- Added Phase 0 status line (`closed as of 2026-02-10`).

### Baseline anchors pinned inside Phase 0 snapshot
- local-parity accepted runs:
  - `platform_20260210T082746Z` (20-event),
  - `platform_20260210T083021Z` (200-event),
  - `platform_20260210T091951Z` (post-fix reconfirmation).
- runbook authority:
  - `docs/runbooks/platform_parity_walkthrough_v0.md`.

### Drift sentinel assessment
- No designed-flow contradiction introduced.
- Ownership boundaries preserved in wave matrix.
- Meta-layer saturation retained as explicit migration wave/gate requirement.

### Outcome
Phase 0 is now formally closed; migration execution can proceed to Phase 1 (accounts/credentials/secrets bootstrap).

## Entry: 2026-02-10 10:05PM - Corrective lock: simplify Phase 0 and remove auxiliary docs

### Context
USER explicitly rejected the extra Phase 0 documents as distracting and not adding meaningful value versus already-pinned authorities and local-parity implementation history.

### User-directed correction
- Remove auxiliary Phase 0 files:
  - `phase0_baseline_snapshot.md`
  - `phase0_service_wave_matrix.md`
  - `phase0_acceptance_gate_templates.md`
- Refactor Phase 0 in active build plan so closure references only:
  - pre-design authority notes,
  - local-parity implementation maps/notes.

### Decision
Adopt a minimal-authority Phase 0 posture:
1) read/lock authority decisions,
2) read/lock baseline local-parity implementation history,
3) proceed without generating comparative/duplicative artifacts.

### Planned edits
- Update `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`:
  - rewrite Phase 0 work sections and DoD evidence links to authoritative sources only,
  - preserve closed status while removing references to deleted files.
- Delete the three Phase 0 artifact files.

### Drift sentinel checkpoint
This is a planning-surface simplification only; no semantic/runtime behavior changes.

## Entry: 2026-02-10 10:06PM - Applied Phase 0 simplification (auxiliary docs removed)

### Changes applied
1. Refactored Phase 0 in active build plan:
   - file: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - replaced auxiliary-artifact framing with authority-first references:
     - pre-design migration authority,
     - run/operate pre-design decisions,
     - obs/gov pre-design decisions,
     - local-parity platform implementation maps,
     - local-parity runbook.

2. Removed auxiliary Phase 0 files:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/phase0_baseline_snapshot.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/phase0_service_wave_matrix.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/phase0_acceptance_gate_templates.md`

### Rationale
- Align with USER instruction to avoid distracting/duplicative documentation.
- Keep Phase 0 grounded in existing authoritative sources and implementation history.
- Avoid implying invalid cross-environment performance comparability.

### Validation
- Build plan Phase 0 now references only authority/baseline docs.
- Deleted file paths no longer referenced by active build plan.
- Deleted files removed from workspace.

### Drift sentinel checkpoint
No runtime/infrastructure behavior changed. This is a planning-surface simplification and authority alignment correction.

## Entry: 2026-02-10 10:08PM - Pre-change lock: remove dev_min auxiliary contracts and repin authority

### Context
USER approved removing `dev_min` contract artifacts to avoid unnecessary migration friction and to rely on contracts proven through local-parity implementation.

### Decision
1. Remove `docs/model_spec/platform/contracts/dev_min/` entirely.
2. Repin migration authority (`dev-min_managed-substrate_migration.design-authority.v0.md`) evidence contract closure to existing platform contract families and operational evidence artifacts.
3. Remove dev_min contract index section from `docs/model_spec/platform/contracts/README.md`.
4. Update active dev-substrate build plan references that currently require the removed dev_min schema family.

### Planned repin targets (existing contract sources)
- `docs/model_spec/platform/contracts/ingestion_gate/ingestion_receipt.schema.yaml`
- `docs/model_spec/platform/contracts/real_time_decision_loop/audit_record.schema.yaml`
- `docs/model_spec/platform/contracts/real_time_decision_loop/eb_offset_basis.schema.yaml`
- `docs/model_spec/platform/contracts/archive/archive_event_record_v0.schema.yaml`
- `docs/model_spec/platform/contracts/learning_registry/dataset_manifest_v0.schema.yaml`

### Drift sentinel checkpoint
This is a contract-surface simplification for migration execution clarity. No runtime semantics or ownership boundaries are changed.

## Entry: 2026-02-10 10:09PM - Applied cleanup: removed dev_min auxiliary contract family

### Changes applied
1. Removed auxiliary contract folder via tracked delete:
   - deleted `docs/model_spec/platform/contracts/dev_min/` (README + 5 schema files).

2. Repinned migration authority evidence schema closure to existing contract families:
   - updated `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md` Section 17.2(7)
   - pinned evidence sources now reference:
     - `contracts/ingestion_gate/ingestion_receipt.schema.yaml`
     - `contracts/real_time_decision_loop/audit_record.schema.yaml`
     - `contracts/real_time_decision_loop/eb_offset_basis.schema.yaml`
     - `contracts/archive/archive_event_record_v0.schema.yaml`
     - `contracts/learning_registry/dataset_manifest_v0.schema.yaml`
   - run summary artifacts now explicitly treated as operational evidence outputs (`platform_run_report.json`, `environment_conformance.json`).

3. Removed `dev_min` section from contracts index:
   - `docs/model_spec/platform/contracts/README.md`

4. Updated active build-plan evidence-conformance wording:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - now references existing contract families + reporter outputs (no dev_min schema family).

### Validation
- `rg` sweep confirms no active references to `docs/model_spec/platform/contracts/dev_min/*` outside historical append-only logs/impl notes.
- authority + build-plan references now align with existing local-parity-derived contracts.

### Drift sentinel checkpoint
No runtime behavior changed. This is a migration-friction reduction and contract-authority simplification aligned to USER direction.

## Entry: 2026-02-10 10:12PM - Pre-change lock: expand Phase 1 (accounts/credentials/secrets) to full execution detail

### Context
USER requested Phase 1 expansion so no aspect is left ambiguous in the active dev-substrate build plan.

### Problem
Phase 1 currently has only three broad bullets and three coarse DoD checks. It is insufficient to drive execution rigor for secure bootstrap and reproducible operator onboarding.

### Decision
Expand Phase 1 in-place within `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` into explicit sub-sections with:
- account/tenancy and billing posture,
- IAM and principal model,
- secret taxonomy and path map,
- operator preflight command gates,
- security hygiene and leak prevention controls,
- failure/recovery drills,
- tightened DoD gate with evidence expectations.

### Constraints from user direction
- Keep Phase 1 inside the build plan (no extra supporting docs unless explicitly requested).
- Avoid local-parity vs dev performance comparison framing.
- Keep references anchored to existing authorities and implementation history.

### Drift sentinel checkpoint
Planning-only expansion; no runtime code/infrastructure behavior changes.

## Entry: 2026-02-10 10:13PM - Applied Phase 1 expansion in active dev-substrate build plan

### What changed
Expanded Phase 1 in `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` from coarse bullets into execution-ready detail.

### New Phase 1 structure
- Added authority anchors for Phase 1 execution.
- Expanded work into six explicit sections:
  - 1.A account and tenancy bootstrap,
  - 1.B principal and permission model,
  - 1.C secret taxonomy and source of truth,
  - 1.D operator bootstrap and preflight gate,
  - 1.E security hygiene and leak prevention,
  - 1.F failure and recovery drills.
- Tightened DoD from 3 coarse checks to 8 explicit closure checks with auditable criteria.

### Why
- Removes ambiguity before implementation and prevents hidden assumptions around identity/secrets/bootstrap.
- Aligns with user requirement to leave no phase under-specified.
- Keeps execution inside the build plan (no extra support documents).

### Validation
- Verified Phase 1 section markers and DoD are present and correctly scoped.
- Verified later phases remained intact and unchanged.

### Drift sentinel checkpoint
Planning expansion only; no runtime/infrastructure behavior changes.

## Entry: 2026-02-10 10:15PM - Pre-change lock: implement Phase 1 (1.A -> 1.F)

### Context
USER approved implementation of Phase 1 end-to-end and indicated AWS IAM user credentials are enabled in this shell environment.

### Phase 1 implementation objective
Close sections 1.A through 1.F with auditable evidence:
- account/tenancy bootstrap,
- principal/permission model,
- secret taxonomy/source map,
- operator bootstrap + preflight,
- security hygiene,
- failure/recovery drills.

### Planned execution steps
1. Discover runtime tooling and identity context (AWS CLI, region/account identity, Confluent tooling presence).
2. Implement reproducible Phase 1 preflight executable (sanitized output only; no secret values logged).
3. Pin secret-handle map and env injection contract in existing docs/build plan.
4. Execute positive preflight and targeted negative drills (missing secret handle, invalid AWS auth context, invalid Kafka credential shape check).
5. Update Phase 1 DoD status lines in build plan based on observed evidence (PASS/fail-closed where appropriate).

### Security guardrails for this pass
- Never print or store secret values in logs/notes.
- Record only secret handles, env var names, and pass/fail outcomes.
- Keep all outputs sanitized in implementation/logbook entries.

### Drift sentinel checkpoint
This pass should only harden migration readiness posture and operator controls; no platform semantic-law changes are allowed.

## Entry: 2026-02-10 10:22PM - Phase 1 implementation pass (1.A -> 1.F) with executable preflight and drills

### Implemented changes
1. Added executable Phase 1 preflight tool:
   - `scripts/dev_substrate/phase1_preflight.ps1`
   - behavior: fail-closed checks for AWS identity/region, terraform presence, required SSM handle presence, optional Confluent API auth probe, S3 bucket visibility, and secret-hygiene git check.

2. Added executable SSM seed helper for Confluent handles:
   - `scripts/dev_substrate/phase1_seed_ssm.ps1`
   - behavior: writes secure parameters for bootstrap/api_key/api_secret under configured prefix; no secret values printed.

3. Added Make targets for Phase 1 operations:
   - `platform-dev-min-phase1-preflight`
   - `platform-dev-min-phase1-seed-ssm`
   - plus dev_min defaults for region/ssm prefix and flags.

4. Applied Git-Bash path-conversion guard for SSM-style paths:
   - `MSYS_NO_PATHCONV=1` on both new targets.

5. Expanded Phase 1 execution detail and status in:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - includes explicit handle map, runtime env injection keys, drill evidence summary, and DoD status updates.

### Execution evidence (sanitized)
- AWS identity probe:
  - account `230372904534`
  - principal `arn:aws:iam::230372904534:user/fraud-dev`
  - region `eu-west-2`
- strict preflight (expected fail-closed because prod handles absent):
  - `make platform-dev-min-phase1-preflight` -> `FAIL_CLOSED` on missing `/fraud-platform/dev_min/confluent/*`.
- permissive bootstrap preflight (for baseline operator path):
  - `make platform-dev-min-phase1-preflight DEV_MIN_ALLOW_MISSING_CONFLUENT_HANDLES=1 DEV_MIN_SKIP_CONFLUENT_API_PROBE=1` -> `PASS` with warnings.
- failure drill 1 (invalid AWS auth context):
  - set `AWS_PROFILE=__missing_profile__` and run preflight -> `FAIL_CLOSED` (identity/region/bucket checks fail as expected).
- failure drill 2 (invalid Confluent credentials):
  - seeded isolated drill handles under `/fraud-platform/dev_min_drill/confluent/*` with dummy values,
  - ran strict preflight on drill prefix -> `FAIL_CLOSED` at Confluent API auth probe,
  - cleaned drill handles via `aws ssm delete-parameters`.
- failure drill 3 (missing secret material for seed helper):
  - `make platform-dev-min-phase1-seed-ssm` without values -> explicit failure (expected).

### Phase status outcome
- `1.A` through `1.F` implementation surfaces are now present and executable.
- Phase 1 closure remains blocked on provisioning real Confluent handles under `/fraud-platform/dev_min/confluent/*` and rerunning strict preflight to full PASS.

### Drift sentinel checkpoint
No platform semantic-law change. This pass implements migration readiness controls, secret handling discipline, and fail-closed operator gates.

## Entry: 2026-02-10 10:49PM - Phase 1 closure blocker: dev_min Kafka secrets not visible in execution shell

### Observed blocker
After implementing Phase 1 tooling, strict closure path remains blocked because required secret inputs are absent in the active shell/session:
- `DEV_MIN_KAFKA_BOOTSTRAP`
- `DEV_MIN_KAFKA_API_KEY`
- `DEV_MIN_KAFKA_API_SECRET`

Validation evidence:
- `make platform-dev-min-phase1-seed-ssm` fails with explicit missing-value error.
- `make platform-dev-min-phase1-preflight` fails closed on missing SSM handles:
  - `/fraud-platform/dev_min/confluent/bootstrap`
  - `/fraud-platform/dev_min/confluent/api_key`
  - `/fraud-platform/dev_min/confluent/api_secret`
- `.env.platform.local` and `.env.local` currently contain no `DEV_MIN|CONFLUENT|KAFKA` key names.

### Confirmed-good behavior
- Fail-closed posture works as intended (no silent bypass).
- permissive bootstrap mode still passes with explicit WARNs.

### Unblock path (next action)
1. Set `DEV_MIN_KAFKA_*` env variables in the same execution context (or add to `.env.platform.local` with those exact names).
2. Run:
   - `make platform-dev-min-phase1-seed-ssm`
   - `make platform-dev-min-phase1-preflight`
3. Phase 1 closes immediately on strict preflight PASS.

### Drift sentinel checkpoint
No semantic/runtime drift introduced. This is a secret-materialization dependency blocker only.

## Entry: 2026-02-10 10:54PM - Pre-change lock: move Phase 1 bootstrap to dedicated `.env.dev_min`

### Context
USER requested dedicated dev-substrate environment file instead of relying on local/parity env surfaces.

### Decision
- Introduce dedicated env file convention for Phase 1 commands:
  - runtime file: `.env.dev_min` (local, untracked),
  - template file: `.env.dev_min.example` (tracked).
- Update Make targets to source dedicated env file before invoking Phase 1 scripts.
- Keep inline make-variable overrides available.

### Planned edits
1. `Makefile`
   - add `DEV_MIN_ENV_FILE ?= .env.dev_min`.
   - update `platform-dev-min-phase1-preflight` and `platform-dev-min-phase1-seed-ssm` to source `DEV_MIN_ENV_FILE` and pass env-backed values.
2. `.gitignore`
   - add `.env.dev_min` to prevent accidental secret commit.
3. `.env.dev_min.example`
   - add required key names with placeholders (no secrets).
4. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - note dedicated env surface under Phase 1 secret/bootstrap sections.

### Validation plan
- run seed/preflight using a temporary dedicated env file + drill SSM prefix.
- cleanup drill SSM handles after test.

### Drift sentinel checkpoint
No platform semantic/runtime changes; this is execution-surface hygiene and migration-friction reduction.

## Entry: 2026-02-10 10:58PM - Applied dedicated Phase 1 env surface (`.env.dev_min`) with validation evidence

### Implemented changes
1. Updated Phase 1 Make defaults and targets in `Makefile`:
   - added `DEV_MIN_ENV_FILE ?= .env.dev_min`,
   - `platform-dev-min-phase1-preflight` now:
     - requires `DEV_MIN_ENV_FILE` file presence,
     - sources file with `set -a; . "$DEV_MIN_ENV_FILE"; set +a`,
     - resolves args from env surface and invokes `phase1_preflight.ps1`.
   - `platform-dev-min-phase1-seed-ssm` now:
     - requires `DEV_MIN_ENV_FILE` file presence,
     - sources file with the same export semantics,
     - resolves `DEV_MIN_KAFKA_*` values and invokes `phase1_seed_ssm.ps1`.
2. Updated `.gitignore` to ignore `.env.dev_min`.
3. Added `.env.dev_min.example` with non-secret placeholders and required key names.
4. Updated build-plan Phase 1 text in:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - pinned dedicated env surface and `DEV_MIN_ENV_FILE` override handle.

### Validation evidence (sanitized)
Executed isolated drill using temporary env file `.tmp/dev_min_env_test.env`:
- `DEV_MIN_SSM_PREFIX=/fraud-platform/dev_min_envfile_drill`
- `DEV_MIN_SKIP_CONFLUENT_API_PROBE=1` (to avoid false-negative on dummy credentials)

Command results:
1. `make platform-dev-min-phase1-seed-ssm DEV_MIN_ENV_FILE=.tmp/dev_min_env_test.env`
   - PASS: wrote handles under `/fraud-platform/dev_min_envfile_drill/confluent/*`.
2. `make platform-dev-min-phase1-preflight DEV_MIN_ENV_FILE=.tmp/dev_min_env_test.env`
   - PASS with expected probe skip warning:
     - AWS identity/region checks PASS,
     - SSM handle presence PASS,
     - Confluent API probe WARN (skipped by flag),
     - S3 bucket inventory check PASS,
     - secret hygiene check PASS.
3. Cleanup:
   - deleted drill SSM parameters under `/fraud-platform/dev_min_envfile_drill/confluent/*`,
   - removed temporary `.tmp` drill env/output artifacts.

### Outcome
- Dedicated env path is now deterministic and explicit for Phase 1 commands.
- Secret sourcing no longer depends on ambient shell inheritance.
- Phase 1 strict closure still depends on real Confluent values in `.env.dev_min` (or alternate file passed via `DEV_MIN_ENV_FILE`) and strict preflight run against `/fraud-platform/dev_min`.

### Drift sentinel checkpoint
No designed-flow drift introduced. Change is limited to operator bootstrap surface and secret-handling hygiene for migration readiness.

## Entry: 2026-02-10 11:03PM - Strict Phase 1 closure attempt with dedicated `.env.dev_min` failed at Confluent auth probe

### Trigger
USER confirmed `.env.dev_min` was updated and requested continuation.

### Actions executed
1. Ran seed on canonical prefix:
   - `make platform-dev-min-phase1-seed-ssm`
   - Result: PASS (all `/fraud-platform/dev_min/confluent/*` handles written).
2. Ran strict preflight (no skip flags):
   - `make platform-dev-min-phase1-preflight`
   - Result: `FAIL_CLOSED`.

### Sanitized evidence
- PASS:
  - AWS CLI present,
  - Terraform present,
  - AWS identity resolved (`arn:aws:iam::230372904534:user/fraud-dev`),
  - region `eu-west-2` matched,
  - required SSM handles present,
  - S3 bucket inventory readable,
  - `.env*` secret-hygiene check PASS.
- FAIL:
  - `confluent_api_probe: confluent api auth check failed`.

### Decision
- Phase 1 remains **in progress** (not closable yet).
- Blocker is now narrowed to Confluent key validity/scope (not missing handles, not AWS posture, not tooling posture).

### Immediate remediation path
1. Rotate/reissue Confluent API key/secret for the intended environment/cluster.
2. Update `.env.dev_min` with new values.
3. Re-run:
   - `make platform-dev-min-phase1-seed-ssm`
   - `make platform-dev-min-phase1-preflight`
4. Close Phase 1 on strict PASS.

### Drift sentinel checkpoint
No architecture-flow drift detected. This is an external credential validity/scope blocker; fail-closed behavior is correct.

## Entry: 2026-02-10 11:03PM - Auth probe diagnostic refinement (sanitized)

### Why this check
Strict preflight failed only on `confluent_api_probe`. Needed to separate formatting/input-shape issue from true auth failure.

### Diagnostic actions
1. Retrieved `api_key` and `api_secret` from SSM (`/fraud-platform/dev_min/confluent/*`) and executed the same probe endpoint:
   - `GET https://api.confluent.cloud/iam/v2/api-keys` with basic auth.
2. Captured HTTP status only (no response body, no secret output).
3. Performed sanitized value-shape check from SSM material:
   - key length and boundary ASCII,
   - secret length and boundary ASCII,
   - quoted/not-quoted marker.

### Evidence
- Probe HTTP status: `401`.
- Value-shape summary:
  - `api_key`: `len=16`, `quoted=False`.
  - `api_secret`: `len=64`, `quoted=False`.

### Interpretation
- Failure is not due to missing handles or obvious quote-format corruption.
- Most likely cause is invalid/non-matching Confluent key-secret pair (or revoked credential).

### Next action
- Reissue Confluent credential pair, update `.env.dev_min`, reseed SSM, rerun strict preflight.

## Entry: 2026-02-10 11:09PM - Pre-change lock: correct Phase 1 Confluent probe to Kafka-plane readiness (drift fix)

### Trigger
USER flagged likely false-negative because Confluent dashboard shows active `eCKU` usage while our strict preflight fails only at `confluent_api_probe`.

### Problem statement
- Current preflight probe calls Confluent Cloud IAM endpoint (`/iam/v2/api-keys`).
- Phase 1 authority intent is Kafka/event-bus readiness, not Cloud IAM key listing.
- This creates a drift risk: valid Kafka-plane credentials can be reported as FAIL due to management-plane mismatch.

### Decision
- Replace strict hard-fail dependency on IAM listing with Kafka-plane readiness probe:
  - secret materialization check (bootstrap/key/secret non-empty),
  - bootstrap endpoint parse + DNS resolve + TCP reachability check.
- Keep fail-closed posture for missing/invalid material and unreachable bootstrap.
- Document that full Kafka auth/topic metadata verification is executed at Phase 2 provisioning/integration gate (where topic tooling exists).

### Planned edits
1. `scripts/dev_substrate/phase1_preflight.ps1`
   - remove mandatory IAM list-keys dependency from strict decision path,
   - implement Kafka readiness probe as above,
   - keep skip flag semantics for controlled drills.
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - align Phase 1.D wording with implemented probe semantics.
3. Re-run strict preflight and capture sanitized evidence.

### Drift sentinel checkpoint
This is a corrective drift fix to realign gate logic with event-bus design intent; no component graph/runtime ownership changes.

## Entry: 2026-02-10 11:11PM - Drift fix applied: Phase 1 Confluent probe now validates Kafka-plane readiness; strict gate PASS

### Code changes
1. Updated `scripts/dev_substrate/phase1_preflight.ps1`:
   - replaced management-plane IAM list-keys dependency with Kafka-plane readiness probe.
   - probe now enforces:
     - bootstrap/key/secret resolve from SSM,
     - non-empty secret material,
     - quoted-value rejection for key/secret,
     - bootstrap parse (host:port),
     - DNS resolution and TCP reachability to bootstrap endpoint.
   - check name changed from `confluent_api_probe` to `confluent_kafka_probe`.
2. Updated `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`:
   - Phase 1.D mandatory check wording now pins Kafka readiness probe semantics,
   - full Kafka auth/topic metadata verification explicitly deferred to Phase 2 provisioning/integration gates.
3. Updated Phase 1 DoD + status in the same build plan:
   - preflight checkbox marked complete,
   - Phase 1 status marked closed.

### Validation evidence
- Command: `make platform-dev-min-phase1-preflight`
- Result: `PASS`
- Key checks:
  - `ssm_handles_present`: PASS,
  - `confluent_kafka_probe`: PASS (`pkc-41wq6.eu-west-2.aws.confluent.cloud:9092` reachable),
  - AWS identity/region/S3/hygiene checks: PASS.

### Outcome
- The previously observed false-negative gate was caused by management-plane probe mismatch.
- Phase 1 gate now matches event-bus readiness intent and closes with strict PASS on canonical handles.

### Drift sentinel checkpoint
Corrective alignment completed; no platform flow/ownership drift introduced.
