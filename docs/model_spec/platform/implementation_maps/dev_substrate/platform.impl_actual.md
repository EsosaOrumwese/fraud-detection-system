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

## Entry: 2026-02-10 11:14PM - Pre-change lock: add binding budget sentinel for dev-substrate execution discipline

### Trigger
USER explicitly requested stronger vigilance for paid-service usage and explicit shutdown guidance when stepping away.

### Problem
Current build plan includes cost guardrails in Phase 2 but does not define an always-on operator behavior contract for cost posture across all phases.

### Decision
Add a dedicated, binding `Budget Sentinel` section to the active dev-substrate build plan that applies to every execution step, not only infra provisioning phases.

### Planned policy content
1. Mandatory pre-action cost surface declaration (what paid services may be touched).
2. Mandatory post-action decision (`KEEP ON` vs `TURN OFF NOW`) with explicit rationale.
3. Immediate teardown on user-away/no-work state for ephemeral resources.
4. No unattended paid resources after command completion unless explicitly approved.
5. Cost action evidence must be logged in logbook and impl notes.

### Drift sentinel checkpoint
Process hardening only; no semantic/component/runtime-flow change.

## Entry: 2026-02-10 11:14PM - Applied binding budget sentinel in dev-substrate build plan

### Implemented change
- Updated `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` with new section:
  - `Budget Sentinel (binding for all dev_substrate phases)`.

### Policy now pinned
1. Pre-action paid-surface declaration is mandatory.
2. Post-action explicit `KEEP ON` vs `TURN OFF NOW` decision is mandatory.
3. Away/no-work state requires immediate teardown confirmation for ephemeral paid resources.
4. No unattended paid runtime without explicit approval.
5. Cost-relevant actions must be logged in both logbook and impl notes.

### Outcome
- Budget discipline is now a standing execution law for the migration track, not phase-local guidance.
- This directly addresses USER requirement for active noob-safe cost posture.

### Drift sentinel checkpoint
Governance/process hardening only; no platform logic/runtime ownership drift.

## Entry: 2026-02-10 11:16PM - Pre-change lock: expand Phase 2 into execution-ready plan

### Trigger
USER requested planning for Phase 2 (after clarifying they meant Phase 2, not Phase 1).

### Problem
Phase 2 currently has only three coarse bullets and three coarse DoD lines. This is not sufficient for deterministic execution under migration + budget sentinel constraints.

### Decision
Expand Phase 2 in-place (no auxiliary docs) with componentized work sections, explicit meta-layer onboarding hooks, and auditable DoD checks.

### Planned expansion scope
1. Add Phase 2 authority anchors (migration authority + run/operate + obs/gov + tooling map).
2. Break Phase 2 into explicit sections:
   - Terraform topology/state boundaries,
   - core persistent substrate,
   - demo ephemeral substrate,
   - cost/teardown controls,
   - operator entrypoints and run surfaces,
   - obs/gov + evidence wiring for infra actions,
   - failure/recovery drills and destroy verification.
3. Tighten DoD into concrete closure checks (idempotency, teardown verification, budget alarms/tags, evidence logging, drift confirmation).
4. Add explicit phase status line for planning completion versus implementation start.

### Constraints
- Planning-only action; no paid service commands should run.
- Keep this in the active build plan and matching logbook/impl trail.

### Drift sentinel checkpoint
Planning elaboration only; no semantic/runtime changes.

## Entry: 2026-02-10 11:17PM - Applied Phase 2 planning expansion in active dev-substrate build plan

### Implemented planning changes
Updated `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` Phase 2 from coarse outline to execution-ready plan.

### What was added
1. Phase 2 authority anchors:
   - migration authority,
   - run/operate and obs/gov pre-design decisions,
   - environment/tooling map,
   - impl trail reference.
2. Sectioned Phase 2 work plan (`2.A` -> `2.G`):
   - Terraform topology/state boundaries,
   - core substrate,
   - demo substrate,
   - cost/teardown controls,
   - run/operate onboarding,
   - obs/gov onboarding,
   - failure/recovery drills.
3. Tightened DoD checklist with explicit closure gates for:
   - idempotent lifecycle commands,
   - residual-resource teardown checks,
   - budget/tagging activation and verification,
   - lifecycle evidence emission and logbook traceability,
   - drift audit closure.
4. Phase status line updated to:
   - planning expanded and implementation-ready, with execution still pending.

### Outcome
- Phase 2 now has unambiguous execution and acceptance criteria.
- Meta-layer requirements are explicitly built into infra lifecycle planning, not deferred.

### Drift sentinel checkpoint
Planning-only update; no runtime or cost-surface changes were executed.

## Entry: 2026-02-10 11:18PM - Pre-change lock: implement Phase 2 end-to-end (Terraform substrate + operator lifecycle + infra evidence)

### Trigger
USER requested: "Proceed with full implementation of phase 2".

### Implementation objective
Deliver executable Phase 2 surfaces for:
1. Terraform topology (`core` persistent + `demo` ephemeral).
2. Deterministic operator lifecycle commands (`plan/up/down/status/post_destroy_check`).
3. Infra lifecycle evidence emission (run/operate + obs/gov hooks for infra actions).
4. Failure/recovery drill path for idempotent destroy and residual detection.

### Design choices
1. Keep Phase 2 infra to low-cost primitives only:
   - S3, DynamoDB, CloudWatch log group, and AWS Budget (optional via variable).
   - no NAT/LB/always-on compute.
2. Implement Terraform as composable modules:
   - `infra/terraform/modules/core` for persistent substrate,
   - `infra/terraform/modules/demo` for ephemeral substrate.
3. Use env-level composition at:
   - `infra/terraform/envs/dev_min`.
4. Add PowerShell operator script:
   - `scripts/dev_substrate/phase2_terraform.ps1`.
5. Add Make targets that source dedicated env file (`.env.dev_min`) and call Phase 2 lifecycle actions.

### Validation plan
1. Static validation: `terraform fmt -check`, `terraform init`, `terraform validate`.
2. Runtime command validation without silent drift:
   - `phase2-plan` must PASS.
   - `phase2-up` then `phase2-status` then `phase2-down`.
   - `phase2-down` rerun for idempotency.
   - `phase2-post-destroy-check` must PASS.
3. Evidence:
   - local infra lifecycle JSON artifacts written under `runs/fraud-platform/dev_substrate/phase2/`.
   - logbook + impl notes capture sanitized outcomes.

### Cost posture before implementation run
- Editing and static terraform validation do not create paid resources.
- `phase2-up` can create paid resources (low-cost only); if executed, immediate `phase2-down` follows in same session unless USER asks to keep running.

### Drift sentinel checkpoint
This pass builds infra lifecycle tooling only and preserves platform semantic laws/ownership boundaries.

## Entry: 2026-02-10 11:30PM - Applied Phase 2 implementation (Terraform substrate + lifecycle operator surfaces)

### Implemented artifacts
1. Terraform module set:
   - `infra/terraform/modules/core/variables.tf`
   - `infra/terraform/modules/core/main.tf`
   - `infra/terraform/modules/core/outputs.tf`
   - `infra/terraform/modules/demo/variables.tf`
   - `infra/terraform/modules/demo/main.tf`
   - `infra/terraform/modules/demo/outputs.tf`
2. Environment composition:
   - `infra/terraform/envs/dev_min/versions.tf`
   - `infra/terraform/envs/dev_min/variables.tf`
   - `infra/terraform/envs/dev_min/main.tf`
   - `infra/terraform/envs/dev_min/outputs.tf`
   - `infra/terraform/envs/dev_min/README.md`
   - `infra/terraform/envs/dev_min/terraform.tfvars.example`
3. Operator lifecycle script:
   - `scripts/dev_substrate/phase2_terraform.ps1`
4. Make targets and defaults:
   - added Phase 2 defaults and targets in `Makefile` for `plan/up/down/down-all/status/post-destroy-check`.
5. Supporting docs:
   - `infra/terraform/modules/README.md`
   - `infra/terraform/envs/README.md`
   - `.env.dev_min.example` updated/recreated with Phase 2 knobs.

### Validation executed
1. Static validation:
   - `terraform fmt -recursive infra/terraform` -> PASS.
   - `terraform -chdir=infra/terraform/envs/dev_min init -input=false -no-color` -> PASS.
   - `terraform -chdir=infra/terraform/envs/dev_min validate -no-color` -> PASS.
2. Lifecycle validation (managed resources touched):
   - `make platform-dev-min-phase2-plan` -> PASS.
   - `make platform-dev-min-phase2-up DEV_MIN_ALLOW_PAID_APPLY=1` -> PASS.
   - `make platform-dev-min-phase2-status` -> PASS (`resources_in_state=25` during active phase).
   - `make platform-dev-min-phase2-down` -> PASS.
   - rerun `make platform-dev-min-phase2-down` (idempotency drill) -> PASS.
   - `make platform-dev-min-phase2-post-destroy-check` initially FAIL due script array-shape bug; fixed and rerun -> PASS.
   - `make platform-dev-min-phase2-down-all DEV_MIN_ALLOW_PAID_DESTROY_ALL=1` -> PASS.
   - final `make platform-dev-min-phase2-status` -> PASS (`resources_in_state=0`).
3. Evidence artifacts emitted under:
   - `runs/fraud-platform/dev_substrate/phase2/infra_phase2_*`.

### Corrective fix during implementation
- `post_destroy_check` failed on JSON parse shape (`Count` lookup on non-array).
- Applied robustness fix in `scripts/dev_substrate/phase2_terraform.ps1` to normalize parsed AWS result into array and then evaluate residual count.

### Cost posture outcome
- Active paid resources were created for validation and then fully torn down.
- End-of-pass decision: `TURN OFF NOW` applied via `down-all`; final state count is `0`.

### Remaining gate
- Budget-alert activation test remains pending explicit `DEV_MIN_ENABLE_BUDGET_ALERT=1` configuration for this account.
- Terraform wiring for this path is implemented; runtime activation is now an operator switch, not a coding gap.

### Additional teardown drill
- Re-ran `down-all` after full teardown:
  - `make platform-dev-min-phase2-down-all DEV_MIN_ALLOW_PAID_DESTROY_ALL=1` -> PASS.
- Confirms idempotent full-teardown behavior when state is already empty.

### Validation note
- A transient local-state file lock occurred when `plan` and `status` were executed concurrently during final verification.
- Reran `status` sequentially and confirmed PASS with `resources_in_state=0`.
- Operator guidance: run Phase 2 terraform actions sequentially against the same workspace/state path.

### Final teardown confirmation
- Queried AWS tagged resources for `fp_phase=phase2`:
  - `aws resourcegroupstaggingapi get-resources --tag-filters Key=fp_phase,Values=phase2 ...`
  - Result: empty list (`[]`).
- Confirms no tagged Phase 2 resources remain active after `down-all`.

## Entry: 2026-02-10 11:40PM - Pre-change lock: activate and verify budget-alert wiring (config-level, no synthetic spend)

### Trigger
USER requested budget-alert validation aligned with budget sentinel and suggested low budget threshold for later runtime confirmation.

### Decision
1. Execute config-level validation now:
   - provision Phase 2 with budget alert enabled,
   - verify budget existence and notification configuration via AWS API,
   - do not generate synthetic spend to force an alert.
2. Set `monthly_budget_limit_usd=1` for practical near-term runtime confirmation during upcoming platform tests.
3. `DEV_MIN_BUDGET_ALERT_EMAIL` is missing in `.env.dev_min`; for this validation pass only, use operator fallback from local git identity email.

### Planned run steps
1. `phase2-up` with:
   - `DEV_MIN_ENABLE_BUDGET_ALERT=1`
   - `DEV_MIN_BUDGET_LIMIT_USD=1`
   - fallback `DEV_MIN_BUDGET_ALERT_EMAIL` override.
2. Verify budget via:
   - Terraform outputs (`budget_name`),
   - AWS Budgets API (`describe-budget`, `describe-notifications-for-budget`).
3. Keep only core resources (`phase2-down`) so budget remains active for upcoming tests unless USER requests full teardown.

### Cost posture
- Paid surfaces touched: S3, DynamoDB, CloudWatch logs, SSM, and AWS Budget metadata.
- Post-action decision target: `KEEP ON (core only)` to retain budget alert during immediate testing window.

### Drift sentinel checkpoint
No semantic/component-flow changes; this is governance-cost control closure for Phase 2 DoD.

## Entry: 2026-02-10 11:42PM - Budget alert activated and config-verified (no synthetic spend)

### Executed actions
1. Enabled budget-alert path for this run via command overrides:
   - `DEV_MIN_ENABLE_BUDGET_ALERT=1`
   - `DEV_MIN_BUDGET_LIMIT_USD=1`
   - subscriber email override from local operator git identity (because `.env.dev_min` lacked `DEV_MIN_BUDGET_ALERT_EMAIL`).
2. Applied infrastructure:
   - `make platform-dev-min-phase2-up DEV_MIN_ALLOW_PAID_APPLY=1 ...` -> PASS.
3. Verified budget configuration using AWS API:
   - Terraform output returned budget name.
   - `aws budgets describe-budget` -> PASS.
   - `aws budgets describe-notifications-for-budget` -> PASS.
   - Observed: budget exists, monthly USD limit set to `1.0`, two ACTUAL notifications configured (80% and 100% thresholds).
4. Minimized spend while retaining budget path for near-term tests:
   - `make platform-dev-min-phase2-down ...` -> PASS (demo off, core retained).
   - `make platform-dev-min-phase2-status` -> PASS (`resources_in_state=23`).
   - `make platform-dev-min-phase2-post-destroy-check` -> PASS (no demo-tier residual resources).

### Build-plan alignment
- Updated Phase 2 DoD to reflect:
  - budget/tagging active + config-verified (closed),
  - explicit remaining gate: real notification delivery observation during platform runtime spend (open).

### Cost posture decision
- Post-action decision: `KEEP ON (core only)`.
- Rationale: keep low-cost core + budget configuration active so upcoming platform tests can naturally confirm notification delivery without re-provisioning.
- Demo-tier resources are off.

### Operator follow-up
- Add `DEV_MIN_BUDGET_ALERT_EMAIL=<operator-email>` to `.env.dev_min` so future runs do not rely on command override fallback.

### Drift sentinel checkpoint
No runtime semantic drift; this is a governance-cost control activation and verification pass.

### Current posture snapshot
- `phase2-status` PASS with `resources_in_state=23`.
- Tag-scan snapshot:
  - `fp_tier=demo`: `0` resources,
  - `fp_tier=core`: `7` resources.
- Budget-validation posture is active while spend-sensitive demo surfaces remain off.

## Entry: 2026-02-10 11:45PM - Corrective policy shift: local-only `.env.dev_min` (no tracked `.env` example artifacts)

### Trigger
USER requested explicit workflow change: do not keep or commit `.env.*.example` artifacts for this migration track.

### Decision
1. Use only local untracked `.env.dev_min` for dev-substrate commands.
2. Remove `.env.dev_min.example` from workspace.
3. Update active Make target guidance and build-plan wording to avoid referencing example files.
4. Keep historical log/impl entries intact (append-only), but pin this corrective policy as the current authority.

### Planned edits
- `Makefile`: change all error/help text from “copy from .env.dev_min.example” to local-only `.env.dev_min` instructions.
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`: remove template-file reference from dedicated env surface section.
- delete `.env.dev_min.example`.

### Cost posture
- No cloud commands/resources touched for this correction.

### Drift sentinel checkpoint
Process/documentation correction only; no platform semantic/runtime behavior changes.

## Entry: 2026-02-10 11:46PM - Applied local-only `.env.dev_min` policy (removed tracked example references)

### Applied changes
1. Deleted `.env.dev_min.example` from workspace.
2. Updated `Makefile` messaging for Phase 1/2 targets:
   - replaced “copy from .env.dev_min.example” with local-only guidance to create `.env.dev_min` with `DEV_MIN_*` keys.
3. Updated active build-plan wording:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - dedicated env surface now pins only local `.env.dev_min` + `DEV_MIN_ENV_FILE` override.

### Outcome
- Current workflow no longer depends on or references tracked `.env` example files in active execution surfaces.
- Existing historical entries mentioning `.env.dev_min.example` remain as immutable historical trail; this entry supersedes them for current posture.

### Cost posture
- No cloud/resource actions were executed.

### Drift sentinel checkpoint
Policy/documentation/tooling text correction only; no runtime semantic changes.

## Entry: 2026-02-10 11:52PM - Local `.env.dev_min` updated with budget keys (sanitized)

### Action
Per USER direction to operate directly on local env file, updated `.env.dev_min` to persist budget controls:
- `DEV_MIN_ENABLE_BUDGET_ALERT`
- `DEV_MIN_BUDGET_LIMIT_USD`
- `DEV_MIN_BUDGET_ALERT_EMAIL`

### Verification
Presence check confirms all three keys are set (values intentionally not logged).

### Cost posture
No cloud actions executed for this local file update.

### Drift sentinel checkpoint
No semantic-law or ownership-boundary drift detected. Changes are substrate-lifecycle only and align with migration authority.

## Entry: 2026-02-11 08:51AM - Post-return credential/posture reconfirmation (Phase 1 + Phase 2 status)

### Trigger
USER resumed work and requested immediate reconfirmation while keeping existing Confluent credentials.

### Actions executed
1. `make platform-dev-min-phase1-seed-ssm` -> PASS.
   - canonical handles `/fraud-platform/dev_min/confluent/*` updated to version `4`.
2. `make platform-dev-min-phase1-preflight` -> PASS.
   - Kafka readiness probe PASS against bootstrap `pkc-41wq6.eu-west-2.aws.confluent.cloud:9092`.
3. `make platform-dev-min-phase2-status` -> PASS.
   - workspace `dev_min_demo`,
   - `resources_in_state=23`,
   - evidence written under `runs/fraud-platform/dev_substrate/phase2/`.

### Outcome
- Credential continuity confirmed (no forced rotation required).
- Phase 1 strict gate remains green.
- Phase 2 core posture remains active and healthy for continued migration work.

### Cost posture decision
- `KEEP ON (core only)` for active working session.
- No `up` action run in this pass; no additional infra expansion performed.

## Entry: 2026-02-11 09:08AM - Pre-change lock: expand Phase 3 (Control + Ingress) to settlement-first migration plan

### Trigger
USER requested expansion of Phase 3 so platform-level decisions are settled before component migration begins.

### Problem
Current Phase 3 section is too coarse (3 bullets + 3 DoD lines) and does not explicitly encode:
- platform-level settlement gates,
- run/operate + obs/gov growth at each integration step,
- validation ladder and performance/cost checkpoints,
- local-parity decision carry-forward protocol.

### Decision
Rewrite Phase 3 in-place as a settlement-first plan with explicit sections:
1. Platform-level settlement gate (contracts, topics, ownership boundaries, SLO/budget guards).
2. Infra readiness for C&I wave.
3. Component migration sequence (SR -> WSP -> IG -> EB corridor) with coupling awareness.
4. Meta-layer expansion at each migration step.
5. Validation ladder (`20` smoke -> `200` acceptance -> `1000` stress) plus cost checkpoints.
6. Drift sentinel audit and closure rules.

### Constraints
- Planning-only update; no resource provisioning commands.
- Keep authority alignment with migration design authority + local-parity implementation notes.

### Cost posture
- No paid resources touched for this planning expansion.

### Drift sentinel checkpoint
Planning/process elaboration only; no runtime semantic changes.

## Entry: 2026-02-11 09:09AM - Applied Phase 3 expansion (settlement-first Control+Ingress migration plan)

### Implemented planning changes
Updated `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` Phase 3 from coarse outline to execution-ready, platform-settlement-first plan.

### What was added
1. Authority anchors for Phase 3:
   - C&I pre-design decision,
   - flow narrative,
   - run/operate + obs/gov pre-design decisions,
   - mandatory local-parity C&I + oracle implementation-note carry-forward set.
2. Sectioned Phase 3 work plan (`3.A` -> `3.F`):
   - platform-level settlement gate,
   - infra readiness,
   - component migration sequence,
   - meta-layer expansion during integration,
   - validation ladder + cost checkpoints,
   - drift audit and closure.
3. Validation ladder pinned exactly as discussed:
   - `20` smoke -> `200` acceptance -> `1000` stress.
4. DoD tightened to include:
   - settlement gate closure before coding/migration,
   - meta-layer saturation requirement for C&I services,
   - per-rung cost decision logging (`KEEP ON` vs `TURN OFF NOW`),
   - explicit drift-audit closure.
5. Phase status updated to:
   - planning expanded and execution pending.

### Outcome
- Phase 3 now explicitly settles platform-level constraints before service migration starts.
- Prior gap (meta-layers lagging behind component integration) is now structurally prevented in the plan.

### Cost posture
- Planning-only update; no cloud/resource actions executed.

### Drift sentinel checkpoint
Planning/process elaboration only; no runtime semantic or ownership changes.

## Entry: 2026-02-11 09:25AM - Pre-change lock: implement Phase 3.A and 3.B execution surfaces

### Trigger
USER requested to proceed with implementation of Phase `3.A` then `3.B` with detailed decision trail.

### Scope to implement now
1. **Phase 3.A (platform-level settlement gate)**
   - materialize settlement as an executable artifact (config),
   - add a fail-closed settlement conformity check against `dev_min` profile wiring.
2. **Phase 3.B (infra readiness)**
   - add IG durability prerequisites in Terraform core substrate,
   - implement C&I readiness checker for Kafka topics + S3 prefixes + DynamoDB prereqs,
   - produce run-scoped readiness evidence under `runs/fraud-platform/dev_substrate/phase3/`.

### Design choices
1. Settlement will be stored as a versioned YAML under `config/platform/dev_substrate/phase3/`.
2. Settlement check will be Python-based (`PyYAML` already available) and fail closed on schema/contract mismatches.
3. Kafka topic readiness will be executed via Kafka admin protocol using `kafka-python`:
   - supports explicit topic existence/create for Confluent bootstrap endpoint,
   - avoids dependence on unavailable Confluent Cloud management credentials for this repo.
4. ACL corridor in this rung will be encoded as credential-boundary posture evidence (single principal key in `dev_min`) with explicit note that fine-grained ACL inspection remains external to this checker.
5. Terraform core will be extended with IG admission/publish-state tables and outputs.

### Validation plan
1. `terraform fmt/init/validate` for changed env/module files.
2. Apply core update with existing phase2 lifecycle command (demo off).
3. Run `phase3a` settlement check -> PASS.
4. Run `phase3b` infra readiness check -> PASS.
5. Update Phase 3 DoD line items for 3.A and 3.B.

### Cost posture (before execution)
- This pass can touch paid services when applying Terraform core updates and creating Kafka topics.
- Post-action default: keep only core resources on; no demo surfaces.

### Drift sentinel checkpoint
This pass is C&I migration enablement only; no component behavior rewrite is introduced.

## Entry: 2026-02-11 09:38AM - Phase 3.B decision correction: Kafka REST v3 readiness (no new Python deps)

### Trigger
During implementation review, the earlier pre-change note proposed `kafka-python` for topic readiness. Repository dependency posture and migration friction constraints favored avoiding a new dependency for this rung.

### Decision update
1. Replace `kafka-python` plan with **Confluent Kafka REST v3** checks using existing `requests` dependency.
2. Keep topic management fail-closed and explicit:
   - list/verify required topics,
   - optionally create missing topics only under explicit operator flag.
3. Keep ACL posture evidence at credential-boundary level for this rung:
   - successful authenticated REST access is required,
   - fine-grained ACL introspection remains external operator control (as pinned in settlement).

### Rationale
- Avoids dependency churn in `pyproject.toml`.
- Uses existing env surface (`DEV_MIN_KAFKA_BOOTSTRAP`, API key/secret) and preserves rapid migration flow.
- Maintains explicit, auditable readiness evidence without introducing additional client/runtime complexity.

### Planned implementation impact
- Add `scripts/dev_substrate/phase3b_ci_infra_readiness.py` (Kafka REST + S3 prefix probe + DynamoDB table checks).
- Extend Terraform core for IG admission/publish-state tables and outputs.
- Add Make targets for `phase3a` and `phase3b` execution.

## Entry: 2026-02-11 09:50AM - Phase 3.A/3.B implementation pass: Terraform + tooling surfaces added

### Applied changes (code)
1. Terraform `core` module expanded with IG durability prerequisites:
   - new DynamoDB tables:
     - `ig_admission_state` (`pk`, `sk`),
     - `ig_publish_state` (`pk`, `sk`).
2. Terraform variable/output surfaces expanded to carry IG table names through:
   - `infra/terraform/modules/core/variables.tf`,
   - `infra/terraform/modules/core/outputs.tf`,
   - `infra/terraform/envs/dev_min/main.tf`,
   - `infra/terraform/envs/dev_min/variables.tf`,
   - `infra/terraform/envs/dev_min/outputs.tf`.
3. Phase-2 lifecycle script updated to pass optional env overrides for new IG table names:
   - `scripts/dev_substrate/phase2_terraform.ps1`.
4. Build command surface expanded:
   - Makefile vars for IG table env keys + Phase 3 output root + topic-create control,
   - new targets:
     - `platform-dev-min-phase3a-check`,
     - `platform-dev-min-phase3b-readiness`.
5. New Phase 3.B readiness checker implemented:
   - `scripts/dev_substrate/phase3b_ci_infra_readiness.py`
   - capabilities:
     - Kafka REST v3 cluster/topic readiness (optional topic create flag),
     - S3 bucket/prefix marker write probes,
     - DynamoDB prerequisite table readiness.

### Design rationale
- Keep migration friction low by using existing dependency set (`requests`, `boto3`, `PyYAML`).
- Keep `3.B` fail-closed on missing prerequisites while allowing explicit operator-controlled topic creation.
- Preserve budget posture by keeping actions scoped to C&I corridor only.

### Next validation sequence
1. `terraform fmt` + `terraform validate`.
2. `phase3a` settlement check.
3. Core apply path (`phase2-up`) to materialize new IG tables.
4. `phase3b` readiness check with topic-create flag.
5. Update build-plan `3.A` and `3.B` DoD items when evidence is green.

## Entry: 2026-02-11 09:56AM - Phase 3.B corrective pivot after first execution failure

### Failure evidence
- `phase3b_ci_infra_readiness` failed with:
  - Kafka corridor: `404` on `https://<bootstrap-host>:443/kafka/v3/clusters`.
  - S3 stores: missing bucket env keys in local `.env.dev_min` for settlement-mapped names.

### Root-cause assessment
1. `DEV_MIN_KAFKA_BOOTSTRAP` points to broker bootstrap endpoint, not guaranteed Kafka REST admin endpoint.
2. Active `.env.dev_min` currently carries Kafka credentials and region but not bucket env bindings required by settlement key names.

### Corrective decision
1. Use **Kafka admin protocol** for topic readiness (`kafka-python`) driven by bootstrap + SASL creds.
2. Keep checker fail-closed but add deterministic fallback derivation for missing bucket/table env values from `DEV_MIN_NAME_PREFIX` so infra created via Terraform defaults is still verifiable.
3. Keep explicit operator flag for topic creation (`--allow-topic-create`) unchanged.

### Contract impact
- No platform semantic changes.
- Readiness mechanism changes only (tooling implementation detail), still aligned to Phase 3.B DoD.

## Entry: 2026-02-11 10:00AM - Phase 3.A executed PASS; Phase 3.B partial PASS with Kafka auth blocker (fail-closed)

### Execution summary
1. **Phase 3.A settlement gate**
   - Command: `make platform-dev-min-phase3a-check`
   - Result: `PASS`.
   - Evidence:
     - `runs/fraud-platform/dev_substrate/phase3/phase3a_settlement_check_20260211T093206Z.json`
     - `runs/fraud-platform/dev_substrate/phase3/phase3a_settlement_check_20260211T093752Z.json`
2. **Terraform core update for IG durability prerequisites**
   - Command: `make platform-dev-min-phase2-down` (core retained, demo disabled).
   - Result: `PASS`.
   - Outcome: state count moved to `25` resources (added IG tables).
3. **Phase 3.B readiness checker**
   - Command: `make platform-dev-min-phase3b-readiness DEV_MIN_PHASE3B_ALLOW_TOPIC_CREATE=1`
   - Result: `FAIL_CLOSED`.
   - Evidence:
     - `runs/fraud-platform/dev_substrate/phase3/phase3b_ci_infra_readiness_20260211T093306Z.json`
     - `runs/fraud-platform/dev_substrate/phase3/phase3b_ci_infra_readiness_20260211T093602Z.json`

### Gate posture by sub-surface
- Kafka corridor (topics/ACL-boundary via auth principal): **FAIL**
  - first failure mode: REST path mismatch on broker bootstrap endpoint (corrected by implementation pivot),
  - second/current failure mode: SASL authentication failure against broker during Kafka admin handshake.
- S3 readiness (object/evidence/quarantine/archive): **PASS**
  - marker write probes succeeded with deterministic bucket defaults.
- DynamoDB readiness (control/admission/publish-state): **PASS**
  - all three prerequisite tables are active.

### Diagnostics and reasoning
1. Bootstrap endpoint DNS/TCP is reachable (Phase 1 probe still green).
2. Kafka protocol handshake reaches SASL auth stage, but credentials are rejected by broker.
3. This is a credential-surface/operator-secret issue, not a Terraform substrate defect and not an ownership/semantic drift issue.

### Drift sentinel checkpoint
- No designed-flow drift introduced.
- Phase 3.B is intentionally **not** marked closed because Kafka corridor readiness is mandatory and currently fail-closed.

### Cost posture decision
- `KEEP ON (core only)`.
- Demo tier remains off; verified via `make platform-dev-min-phase2-post-destroy-check` PASS.

### Required operator action to close 3.B
- Refresh valid broker-scoped Confluent Kafka API key/secret in `.env.dev_min` (`DEV_MIN_KAFKA_API_KEY`, `DEV_MIN_KAFKA_API_SECRET`), then rerun:
  - `make platform-dev-min-phase3b-readiness DEV_MIN_PHASE3B_ALLOW_TOPIC_CREATE=1`

## Entry: 2026-02-11 10:03AM - Build-plan DoD state update after Phase 3.A/3.B execution

### Update applied
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
  - Marked Phase 3 DoD item for settlement gate (`3.A`) as complete.
  - Kept infra readiness (`3.B`) open with explicit blocker note:
    - S3 + Dynamo green,
    - Kafka corridor fail-closed pending valid broker-scoped credentials.

### Reasoning
- This preserves strict gate truth and prevents accidental progression into `3.C` while Kafka readiness is unresolved.

## Entry: 2026-02-11 10:08AM - Phase 3.B closure after credential-port diagnosis and target hardening

### What happened
1. USER requested rerun after credential update.
2. `phase3b` still failed in Kafka corridor while S3+Dynamo stayed green.
3. Focused diagnostics identified bootstrap configuration drift in local env:
   - `.env.dev_min` had `DEV_MIN_KAFKA_BOOTSTRAP=...:443`.
   - Kafka admin protocol in this migration requires broker endpoint `:9092`.

### Corrective actions
1. Re-ran `phase3b` with broker bootstrap override `:9092` -> full `PASS`.
2. Hardened Make target `platform-dev-min-phase3b-readiness` so explicit command-line overrides for
   `DEV_MIN_KAFKA_BOOTSTRAP`, `DEV_MIN_KAFKA_API_KEY`, `DEV_MIN_KAFKA_API_SECRET`, `DEV_MIN_AWS_REGION`
   reliably override `.env.dev_min` values.

### Evidence
- PASS evidence artifact:
  - `runs/fraud-platform/dev_substrate/phase3/phase3b_ci_infra_readiness_20260211T094735Z.json`

### Build-plan update
- Marked Phase 3 DoD line `C&I infra readiness is validated and evidence-logged` as complete.

### Drift sentinel checkpoint
- No semantic/ownership drift detected.
- Failure was configuration-level bootstrap-port mismatch in operator env, now diagnosed and controlled.

### Cost posture decision
- `KEEP ON (core only)`; demo-tier remains off.

## Entry: 2026-02-11 10:20AM - Pre-change lock: Phase 3.C planning expansion + component-focused dev_substrate build plans (C&I wave)

### Trigger
USER requested:
1. read local-parity implementation notes for Oracle Store / Scenario Runner / WSP / Ingestion Gate / Event Bus plus platform local-parity implementation notes,
2. expand `dev_substrate` Phase 3.C plan with explicit DoDs,
3. create focused component build plans so migration is thorough and no loose ends remain.

### Inputs reviewed
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md`
- `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md`
- `docs/model_spec/platform/implementation_maps/local_parity/scenario_runner.impl_actual.md`
- `docs/model_spec/platform/implementation_maps/local_parity/world_streamer_producer.impl_actual.md`
- `docs/model_spec/platform/implementation_maps/local_parity/ingestion_gate.impl_actual.md`
- `docs/model_spec/platform/implementation_maps/local_parity/event_bus.impl_actual.md`
- Supporting structure references:
  - corresponding local-parity `*.build_plan.md` docs,
  - active `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`.

### Observations distilled for 3.C planning
1. Local parity repeatedly converged only when sequence was explicit and oracle stream-view identity was pinned before WSP/IG progression.
2. Runtime drift risks observed historically in local parity were mostly wiring/order/startup-scope issues (run-id scope, bootstrap endpoint class, stale control messages), not core semantic laws.
3. The strongest anti-drift posture for migration is a strict coupled sequence with per-step gate evidence before moving to the next component.

### Planning decisions (locked)
1. Phase 3.C will be expanded into a **strict, coupled migration order** with explicit component gates:
   - `3.C.1 Oracle Store readiness` -> `3.C.2 SR` -> `3.C.3 WSP` -> `3.C.4 IG` -> `3.C.5 EB` -> `3.C.6 coupled-chain replay proof`.
2. Each step will include:
   - boundary ownership assertions,
   - required evidence artifacts,
   - fail-closed stop conditions,
   - residual risk notes.
3. Create dedicated dev_substrate component build plans for C&I wave:
   - `oracle_store.build_plan.md`
   - `scenario_runner.build_plan.md`
   - `world_streamer_producer.build_plan.md`
   - `ingestion_gate.build_plan.md`
   - `event_bus.build_plan.md`
4. Component plans will be migration-scoped (local_parity carry-forward + dev_min wiring + matrix + run/operate + obs/gov hooks), not full component redesign docs.

### Planned edits in this pass
- Expand Phase 3.C section + DoD granularity in:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
- Add focused component build plans listed above under:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/`
- Update dev_substrate README index to list active build-plan files.

### Cost posture
- Documentation/planning edits only; no paid resources/services touched.

### Drift sentinel checkpoint
- This pass is planning elaboration only and strengthens drift-detection posture by forcing component-gated progression.

## Entry: 2026-02-11 10:29AM - Applied Phase 3.C planning expansion + component-focused C&I build plans (dev_substrate)

### Applied edits
1. Expanded `Phase 3.C` in:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. Added strict coupled migration structure:
   - `3.C.1 Oracle Store gate`
   - `3.C.2 Scenario Runner gate`
   - `3.C.3 WSP gate`
   - `3.C.4 IG gate`
   - `3.C.5 EB gate`
   - `3.C.6 coupled-chain closure gate`
3. Tightened DoD granularity in Phase 3:
   - component-matrix closure now explicitly references focused component build plans.
4. Added focused dev_substrate component build plans:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/oracle_store.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/scenario_runner.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/world_streamer_producer.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/ingestion_gate.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/event_bus.build_plan.md`
5. Updated dev_substrate index file:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/README.md`

### Why this closes the planning ask
- Local-parity carry-forward lessons are now encoded as explicit `dev_min` gates:
  - oracle identity lock before streaming,
  - run-id pin coherence through SR/WSP/IG,
  - publish/offset evidence before progression,
  - no partial green movement across components.
- Component plans now provide focused migration tracks so execution remains thorough and auditable, rather than implicit in platform-only notes.

### Cost posture
- Planning/docs only; no paid services touched.

### Drift sentinel checkpoint
- No runtime drift introduced.
- Planning posture is stricter than prior state (more fail-closed progression control).

## Entry: 2026-02-11 10:14AM - Pre-change lock: harden Oracle Store Phase 3.C plan to strict managed substrate (non-local)

### Trigger
USER requested a proper Oracle Store build plan and explicitly clarified Oracle Store in `dev_substrate` must not be local.

### Problem statement
Current `dev_substrate/oracle_store.build_plan.md` was usable but still broad:
1. It did not explicitly encode a managed-only substrate law for every phase.
2. It did not define cost/governance/security gates at Oracle-component level with enough closure detail for production-oriented dev migration.
3. It risked interpretation drift where local-parity semantics could leak into `dev_min` execution posture.

### Authorities considered
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (`3.C.1` Oracle first gate).
- `docs/model_spec/platform/pre-design_decisions/control_and_ingress.pre-design_decision.md`.
- `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`.
- Local baseline records:
  - `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/local_parity/oracle_store.build_plan.md`

### Options considered
1. Keep current C1..C5 structure and add one global non-local note.
   - Rejected: too easy to pass a phase while ignoring managed-only requirements in practice.
2. Rewrite Oracle plan into explicit managed-substrate gates with per-phase fail-closed conditions and evidence requirements.
   - Selected: strongest anti-drift posture and aligns with USER ask.

### Locked decision
Rewrite `dev_substrate/oracle_store.build_plan.md` so each phase is explicitly managed-substrate-only and includes:
1. S3 truth authority lock and local fallback prohibition.
2. Stream-view readiness with evidence-by-ref closure.
3. SR/WSP coupling checks against one oracle root identity.
4. Run/operate + obs/gov onboarding requirements at Oracle boundary.
5. Security + retention + cost sentinel controls.
6. Matrix closure and objective exit criteria into downstream C&I migration.

### Planned edits in this pass
1. Update `docs/model_spec/platform/implementation_maps/dev_substrate/oracle_store.build_plan.md`.
2. Add component-specific trail file `docs/model_spec/platform/implementation_maps/dev_substrate/oracle_store.impl_actual.md` (missing today) for Oracle decisions.
3. Update `docs/model_spec/platform/implementation_maps/dev_substrate/README.md` to index Oracle component implementation map.

### Cost posture
- Docs/planning only in this pass; no paid resources touched.

### Drift sentinel checkpoint
- This change is meant to reduce design-intent drift risk by enforcing non-local semantics in Oracle planning gates.

## Entry: 2026-02-11 10:15AM - Applied Oracle Store plan hardening for Phase 3.C.1 (managed-only)

### What was changed
1. Replaced `dev_substrate/oracle_store.build_plan.md` with a strict managed-substrate plan:
   - Oracle authority lock,
   - seal/manifest verification,
   - stream-view readiness,
   - SR/WSP contract coupling,
   - run/operate onboarding,
   - obs/gov onboarding,
   - security/retention/cost sentinel checks,
   - matrix closure gate.
2. Added missing component-specific implementation map:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/oracle_store.impl_actual.md`
3. Updated dev_substrate index:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/README.md`

### Why this resolves the USER ask
- Oracle Store plan is now explicitly non-local in every phase and fail-closed by default.
- `3.C.1` execution now has clear, auditable gates that block SR/WSP progression until Oracle truth posture is proven on managed substrate.

### Key invariants made explicit
1. No local-path fallback in `dev_min`.
2. No implicit/latest Oracle root selection.
3. By-ref, run-scoped evidence required for Oracle readiness and downstream coupling.
4. Oracle gate acceptance requires both run/operate and obs/gov surfaces.

### Cost posture
- Docs/planning edits only; no paid resources touched.

### Drift sentinel checkpoint
- No runtime behavior changed in this pass.
- Planning drift risk reduced by converting ambiguous Oracle migration text into strict gate language.

## Entry: 2026-02-11 10:46AM - Corrected platform expectation for Oracle in Phase 3.C.1 (engine-owned truth + managed landing)

### Trigger
USER corrected Oracle interpretation and requested both:
1. Oracle component build plan rewrite,
2. platform-level Oracle expectation rewrite.

### Correction summary
1. Oracle artifacts are produced by Data Engine; platform consumes them.
2. Current dev migration mode is controlled sync/backfill into AWS S3 Oracle root.
3. Direct engine->S3 write is target mode and should not alter platform contract semantics.

### Platform-level expectation changes applied
1. `3.C` now explicitly allows parallel component build/config work while Oracle sync is in-flight.
2. `3.C.1` now requires:
   - pinned source->destination contract,
   - managed destination root under oracle prefix,
   - landing sync evidence,
   - stream-view and receipt/seal/manifest verification at destination.
3. Integrated coupled acceptance remains blocked until `3.C.1` is fully green.

### Why this matters
This prevents two drift classes:
1. ownership drift (platform accidentally treated as Oracle producer),
2. sequencing drift (acceptance run started before Oracle authority actually landed).

### Cost posture
- Docs-only pass; no paid services touched.

## Entry: 2026-02-11 12:25PM - Pre-change lock: append Flow Step 1 bootstrap prose to migration narrative

### Trigger
USER asked to append the drafted prose section that defines the first migration flow step (trust/control bootstrap before service swaps).

### Decision
Append this as the first substantive section in:
`docs/model_spec/platform/implementation_maps/dev_substrate/dev_min_migration_narrative.md`.

### Section intent
1. Anchor migration start from fully green local-parity baseline.
2. Make trust/control bootstrap explicit as first flow move.
3. Enforce meta-layer-first posture (Run/Operate + Obs/Gov) before plane-by-plane swap.

### Cost posture
- Docs-only pass; no paid services touched.

## Entry: 2026-02-11 12:27PM - Applied Section 1 prose in incremental migration narrative

### Applied change
Appended first substantive section to:
`docs/model_spec/platform/implementation_maps/dev_substrate/dev_min_migration_narrative.md`

### Section appended
`Section 1: Bootstrap Before Swap (Flow Step 1)` now establishes:
1. local-parity green baseline as migration start state,
2. trust/control bootstrap as first migration gate,
3. mandatory early onboarding of Run/Operate and Obs/Gov,
4. incremental plane migration only after bootstrap gate is green.

### Rationale
This codifies the agreed sequencing posture in prose so later component-level plans remain anchored to the same flow law and do not drift into ad hoc service swapping.

### Drift sentinel check
No drift introduced. The new section reinforces pinned intent: meta-layer-first governance and controlled incremental migration.

### Cost posture
- Docs-only pass; no paid services touched.

## Entry: 2026-02-11 12:16PM - Applied fresh incremental migration narrative scaffold

### Trigger
USER requested a fresh, empty narrative document so migration discussion can proceed incrementally by appended sections.

### Applied changes
1. Created `docs/model_spec/platform/implementation_maps/dev_substrate/dev_min_migration_narrative.md`.
2. Indexed the new document in `docs/model_spec/platform/implementation_maps/dev_substrate/README.md`.

### Content posture
The document intentionally starts as a minimal scaffold and explicitly states that sections will be appended in discussion order from local-parity baseline into `dev_min`.

### Drift sentinel check
No design drift introduced; this is documentation scaffolding only to enforce incremental planning posture.

### Cost posture
- Docs-only pass; no paid services touched.

## Entry: 2026-02-11 12:14PM - Applied creation of incremental migration narrative doc

### Applied edits
1. Added new narrative doc:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_min_migration_narrative.md`
2. Updated dev_substrate index:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/README.md`

### Outcome
There is now a dedicated, minimal narrative artifact ready for progressive section append as discussion proceeds, without forcing a top-down completed-platform narrative.

### Cost posture
- Docs-only pass; no paid services touched.

## Entry: 2026-02-11 12:13PM - Pre-change lock: create incremental migration prose narrative document

### Trigger
USER requested a reset to incremental migration planning and asked for a fresh narrative doc that can be appended section-by-section during discussion.

### Decision
Create a dedicated dev_substrate narrative document with minimal starting content (no big upfront architecture dump), then progressively elaborate it as decisions are discussed.

### File plan
1. Add:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/dev_min_migration_narrative.md`
2. Update index:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/README.md`

### Authoring posture for this doc
1. Incremental-first narrative only.
2. Start from local-parity implemented baseline, then move gate-by-gate.
3. No future-plane deep-detail unless the active gate requires it.

### Cost posture
- Docs-only pass; no paid services touched.

## Entry: 2026-02-11 11:00AM - Pre-change lock: operator env pinning for Oracle 3.C.1 kickoff

### Trigger
USER asked that missing Oracle env values be set directly rather than left as suggestions.

### Decision
Apply explicit `.env.dev_min` pin values required to start Oracle `3.C.1`:
1. managed object-store bucket name,
2. Oracle root and engine-run root under settlement prefix,
3. scenario id pin,
4. stream-view root pin,
5. local sync source pin.

### Cost posture
- Local env-file edit only; no paid services touched.

## Entry: 2026-02-11 11:08AM - Execution lock for Oracle 3.C.1 retry (network restored)

### Trigger
USER requested retry after network recovery.

### Planned execution
1. AWS identity + bucket reachability checks.
2. Oracle landing sync into pinned `DEV_MIN_ORACLE_ENGINE_RUN_ROOT`.
3. Stream-sort closure and strict Oracle validation.

### Cost posture declaration (pre-action)
- Paid surfaces touched: AWS S3 API + storage.
- Post-action cost decision (`KEEP ON` / `TURN OFF NOW`) will be logged.

## Entry: 2026-02-11 11:21AM - Sync attempt halted per user interruption; background process terminated

### Runtime note
1. Oracle sync command was running and remained active after user abort.
2. Active `aws` process (`PID 9848`) was detected and terminated.
3. No `aws` process is active now.

### Cost posture
- `TURN OFF NOW` applied for this attempt (no ongoing paid transfer process).

## Entry: 2026-02-11 11:24AM - Bucket cleanup execution lock (prep for user-run Oracle sync/sort)

### Trigger
USER requested bucket cleanup first, then USER will run Oracle sync + stream-sort manually.

### Planned action
1. Clear `DEV_MIN_OBJECT_STORE_BUCKET` contents.
2. Verify empty-state evidence.
3. Hand off ordered sync/sort command sequence to USER.

### Cost posture declaration (pre-action)
- Paid surface: AWS S3 API delete/list/head operations.

## Entry: 2026-02-11 11:25AM - Versioned-bucket correction for cleanup completeness

### Finding
`DEV_MIN_OBJECT_STORE_BUCKET` is versioned; recursive delete alone does not remove historical versions.

### Decision
Run full version purge so cleanup semantics match user intent ("clean out the bucket").

### Cost posture declaration (pre-action)
- Paid surfaces: S3 version-list + batch delete API calls.

## Entry: 2026-02-11 11:34AM - Cleanup completion snapshot

### Result
1. `DEV_MIN_OBJECT_STORE_BUCKET` is fully empty including versioned history.
2. No active `aws` cleanup process remains.

### Verified counts
- `current=0`
- `versions=0`
- `delete_markers=0`

### Cost posture
- `TURN OFF NOW` (no ongoing paid cleanup operation).

## Entry: 2026-02-11 10:51AM - Pre-change lock: enforce stream-sort contract in platform expectation for Oracle 3.C.1

### Trigger
USER requested that Phase `3.C.1` planning include the fact that downstream C&I runtime uses sorted Oracle stream views, not unsorted raw landed datasets.

### Decision
Amend platform-level Oracle expectation so `3.C.1` is considered green only when:
1. landed Oracle root is present,
2. required per-output stream views are built and validated,
3. sort receipts/manifests exist and match pinned root/scope.

### Why
Without this, C&I progression could falsely pass on landed-but-unsorted artifacts and fail later in WSP/SR integration.

### Planned files
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/oracle_store.build_plan.md`

### Cost posture
- Docs-only pass; no paid services touched.

## Entry: 2026-02-11 10:53AM - Applied platform 3.C.1 expectation update for sorted Oracle runtime inputs

### Applied changes
Updated `dev_substrate/platform.build_plan.md` (`3.C.1`) to require:
1. required output_ids are present as sorted per-output stream views,
2. deterministic sort contract + fallback-key policy for non-`ts_utc` outputs,
3. per-output stream-view manifest/receipt integrity checks.

### Additional stop conditions added
1. required outputs present but not sorted to contract,
2. partial stream-view leftovers not reconciled (`STREAM_VIEW_PARTIAL_EXISTS`).

### Why this closes the gap
This aligns platform acceptance with actual downstream consumption behavior: WSP/SR rely on sorted stream views, not raw landed datasets.

### Cost posture
- Docs-only pass; no paid services touched.

## Entry: 2026-02-11 1:07PM - Corrective pre-change lock: repin SR 3.C.2 to full-migration managed-only posture

### Trigger
USER directed explicit full-migration posture ("nothing stays local") and requested the decisions be locked in `platform.build_plan.md` at `3.C.2`.

### Corrective note
The `3.C.2` plan update was applied immediately to satisfy the direct lock request. This entry records the pre-change decision trail and scope explicitly for audit completeness.

### Problem framing
`3.C.2` previously specified identity and READY checks but did not explicitly forbid local runtime/state acceptance paths for SR, and did not lock re-emit/governance/ladder details under full migration.

### Decisions to lock
1. SR acceptance path in `dev_min` is managed-only runtime/state (no local fallback accepted).
2. Gate strictness remains full parity semantics (no reduced bring-up subset).
3. Re-emit defaults to same-run only; cross-run emit requires explicit governance override evidence.
4. Fail-closed posture for Oracle pin mismatch/missing by-ref evidence.
5. Mandatory SR component ladder before progression: `20 -> 200 -> 1000`.
6. Traffic-mode closure proof requires `fraud` primary and `baseline` secondary run evidence.

### Scope of edit
- File: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
- Section: `3.C.2 Scenario Runner migration gate` only.

### Drift sentinel checkpoint
This is a planning repin/clarification pass; no runtime code behavior changed in this step.

## Entry: 2026-02-11 1:07PM - Applied 3.C.2 SR full-migration repin in platform build plan

### Changes applied
Updated `3.C.2` in `dev_substrate/platform.build_plan.md` to encode full-migration SR posture:
1. Objective now explicitly states managed-only acceptance (no local runtime/state fallback).
2. Added locked repin bullets for:
   - managed compute/state acceptance,
   - full parity gate strictness,
   - same-run re-emit default + governance override requirement for cross-run,
   - fail-closed Oracle pin posture.
3. Expanded required checks with managed-runtime identity/state evidence and local-fallback rejection.
4. Added mandatory component ladder at this gate (`20`, `200`, `1000`) before progression.
5. Expanded stop conditions for Oracle evidence mismatch, unauthorized cross-run emit, and local fallback observation.

### Why this is the correct lock
It converts the user-approved "full migration, nothing local" direction into explicit gate law in the active plan so later implementation/validation cannot claim green using mixed local/managed posture.

### Cost posture
- Docs-only pass; no paid services touched.

## Entry: 2026-02-11 02:58PM - Pre-change lock: make dev_min S3 versioning policy role-aware (avoid object-store bloat)

### Trigger
USER asked to stop blanket bucket versioning behavior after discussing large (`~100GB`) Oracle/object-store payload growth and teardown friction.

### Problem framing
Current `core` module enables versioning for all buckets uniformly.
- This is good for state/audit buckets, but expensive and operationally noisy for high-churn object-store data.
- Versioned object-store also complicates teardown because versions/delete markers must be purged separately.

### Decision
Implement role-aware versioning policy with secure defaults:
1. `object_store`: `Suspended` (default)
2. `quarantine`: `Suspended` (default)
3. `evidence`: `Enabled` (default)
4. `archive`: `Enabled` (default)
5. `tf_state`: `Enabled` (default)

### Design details
1. Add `bucket_versioning_status_by_role` map variable to core module with validation.
2. Pass the map from `envs/dev_min` so environment defaults are explicit and reviewable.
3. Keep override path from `phase2_terraform.ps1` via env-derived JSON map for operator control.
4. Preserve existing bucket names, encryption, and public-access blocks unchanged.

### Planned files
1. `infra/terraform/modules/core/{variables.tf,main.tf}`
2. `infra/terraform/envs/dev_min/{variables.tf,main.tf,terraform.tfvars.example}`
3. `scripts/dev_substrate/phase2_terraform.ps1`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
5. `docs/logbook/02-2026/2026-02-11.md`

### Validation plan
1. `terraform fmt` on touched terraform files.
2. `terraform validate` under `infra/terraform/envs/dev_min`.
3. `make -n platform-dev-min-phase2-{plan,up,down,down-all}` to ensure script wiring unchanged.

### Cost posture declaration
Local code + terraform static validation only; no apply/destroy execution in this step.

## Entry: 2026-02-11 03:02PM - Applied role-aware bucket versioning policy for dev_min core buckets

### Changes applied
1. Core module versioning policy became role-aware:
- `infra/terraform/modules/core/variables.tf`
  - added `bucket_versioning_status_by_role` (map) with validation.
- `infra/terraform/modules/core/main.tf`
  - `aws_s3_bucket_versioning.core` now uses per-role status instead of hardcoded `Enabled`.
2. `dev_min` environment now pins explicit defaults:
- `infra/terraform/envs/dev_min/variables.tf`
  - added `bucket_versioning_status_by_role` default:
    - `object_store=Suspended`
    - `quarantine=Suspended`
    - `evidence=Enabled`
    - `archive=Enabled`
    - `tf_state=Enabled`
- `infra/terraform/envs/dev_min/main.tf`
  - passed map into `module.core`.
- `infra/terraform/envs/dev_min/terraform.tfvars.example`
  - documented the map explicitly.
3. Phase2 operator script supports env-level override + fail-closed validation:
- `scripts/dev_substrate/phase2_terraform.ps1`
  - added `Normalize-VersioningStatus` helper,
  - maps env vars into `TF_VAR_bucket_versioning_status_by_role`:
    - `DEV_MIN_OBJECT_STORE_VERSIONING_STATUS`
    - `DEV_MIN_EVIDENCE_VERSIONING_STATUS`
    - `DEV_MIN_QUARANTINE_VERSIONING_STATUS`
    - `DEV_MIN_ARCHIVE_VERSIONING_STATUS`
    - `DEV_MIN_TF_STATE_VERSIONING_STATUS`.

### Validation executed
1. Formatting:
- `terraform fmt` on touched `.tf` files (`PASS`).
2. Terraform config validity:
- `terraform -chdir=infra/terraform/envs/dev_min validate` (`PASS`).
3. Phase2 toolchain checks:
- `make -n platform-dev-min-phase2-{plan,up,down,down-all}` (`PASS` render).
4. Runtime script checks:
- `pwsh ... phase2_terraform.ps1 -Action plan` with `DEV_MIN_AWS_REGION` set (`PASS`).
- same command with `DEV_MIN_OBJECT_STORE_VERSIONING_STATUS=bad` (`FAIL_CLOSED` as intended).

### Drift assessment
1. Ownership boundaries preserved:
- no component truth-owner changes; this is infra durability/cost posture only.
2. Fail-closed posture improved:
- invalid versioning values now block before plan/apply.
3. Security posture unchanged:
- encryption/public-access blocks retained; no bucket ACL relaxation.

### Cost posture
Plan/validate operations only; no `apply` or `destroy` executed in this change. `TURN OFF NOW`.

## Entry: 2026-02-12 4:29AM - Pre-change lock: codify local-to-managed compute migration challenge and exact planning response

### Trigger
USER raised a critical migration concern: current roadmap may under-specify the practical transition from "service runs on local compute" to "service runs on managed dev substrate compute" and asked that this challenge + solution be captured in platform planning.

### Problem framing
Current `dev_substrate` plan is strong on rails/gates but the migration challenge needs explicit cross-phase structure for first-time operators:
1. hidden local compute assumptions (runtime/dependency/state coupling),
2. missing managed execution handles (queue/definition/runtime image/roles/secrets),
3. unclear cutover law from local-run success to managed-run acceptance,
4. risk of phase progression with matrix-only green while compute substrate is not actually portable.

### Decision
Add a binding cross-phase planning section to `platform.build_plan.md` that makes local-to-managed compute transition explicit and auditable.

### Options considered
1. Keep guidance implicit inside existing phase text only.
- Rejected: too easy to miss and does not create a reusable operator checklist.
2. Add a dedicated cross-phase migration playbook section with challenge statement, concrete work sections, and DoD.
- Selected: directly captures user challenge and converts it into execution law.
3. Create a separate new document and link from build plan.
- Rejected for now: increases fragmentation and weakens day-to-day operational visibility.

### Planned edits
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
- Add `Local-to-Managed Compute Migration Playbook (binding)` section with:
  - challenge statement,
  - compute/state inventory requirement,
  - execution package contract requirement,
  - managed-lane preflight gate requirement,
  - cutover+rollback requirement,
  - portability acceptance definition (`run anywhere` evidence).
- Add explicit coupling bullet under Phase `3.C` enforcing this playbook at each component gate.
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
- Record pre-change and applied closure entries.
3. `docs/logbook/02-2026/2026-02-12.md`
- Log the same decision/action timeline with local time.

### Validation plan
1. Structural validation: headings and section order in `platform.build_plan.md` remain coherent.
2. Drift check: no ownership/semantic law changes introduced; this is planning-method hardening only.

### Drift sentinel checkpoint
No runtime behavior changes in this step. This is a planning-control hardening pass to reduce migration blocker risk and preserve fail-closed progression.

### Cost posture
Docs-only pass; no paid services touched.

## Entry: 2026-02-12 4:30AM - Applied local-to-managed compute migration playbook in active platform build plan

### Changes applied
1. Updated `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` with a new binding cross-phase section:
- `## Local-to-Managed Compute Migration Playbook (binding across phases)`.
2. New section includes:
- challenge statement (local success does not equal managed portability),
- objective (convert uncertainty into fail-closed gates),
- five explicit work sections:
  - compute/state coupling inventory,
  - managed execution package contract,
  - managed-lane preflight gate,
  - cutover/rollback contract,
  - portability acceptance proof.
- cross-phase DoD checklist for migration portability.
3. Strengthened Phase `3.C` progression law:
- added explicit bullet requiring each component step to satisfy this playbook before acceptance-valid status.

### Why this resolves the raised challenge
1. Captures the exact blocker pattern encountered in Oracle stream-sort migration (local compute success vs missing managed execution handles).
2. Makes substrate portability an explicit acceptance criterion instead of implicit assumption.
3. Gives first-time operators a deterministic checklist from local implementation to managed dev substrate execution.

### Validation performed
1. Verified section insertion and discoverability:
- `Local-to-Managed Compute Migration Playbook` present at top-level in `platform.build_plan.md`.
2. Verified coupling into active migration path:
- Phase `3.C` now explicitly references this playbook as mandatory for component acceptance progression.

### Drift assessment
1. No semantic law changes (contracts, idempotency, provenance, fail-closed doctrine unchanged).
2. No ownership-boundary changes (SR/IG/EB/Engine/DLA/LS/Registry/AL truths unchanged).
3. This is planning-method hardening to reduce migration execution drift and hidden compute-coupling risk.

### Cost posture
Docs-only pass; no paid services touched.

## Entry: 2026-02-12 4:31AM - Pre-change lock: require full local run process decomposition as migration baseline

### Trigger
USER requested that migration planning start from a deep, complete understanding of what "it worked locally" means, including every single process inside each plane/corridor.

### Problem framing
Current playbook section includes coupling inventory per service, but does not yet explicitly force decomposition of the local run into process-level units (subprocesses/steps) with traceable IDs.

### Decision
Extend the `Local-to-Managed Compute Migration Playbook` with a mandatory process decomposition section and a binding artifact requirement (`Local Run Process Inventory Matrix`).

### Planned edit
- File: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
- Add explicit requirements:
  1. enumerate every local process/subprocess that participates in a run,
  2. assign stable process IDs and corridor ownership,
  3. capture command/runtime/state/credentials/evidence/retry semantics per process,
  4. require this matrix to be complete before managed acceptance progression.

### Validation plan
- Confirm section + DoD checklist updates are present and linked to progression law.

### Drift sentinel checkpoint
Planning hardening only; no runtime behavior changes.

### Cost posture
Docs-only pass; no paid services touched.

## Entry: 2026-02-12 4:46AM - Applied mandatory local process-inventory baseline into migration playbook

### Changes applied
1. Updated `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` under:
- `Local-to-Managed Compute Migration Playbook (binding across phases)`.
2. Added new mandatory-first work section:
- `0. Local run process decomposition baseline (mandatory first)`.
3. This section now locks a required artifact:
- `Local Run Process Inventory Matrix` containing every local process/subprocess with process IDs and execution details (command/runtime/dependencies/state/credentials/IO/evidence/retry).
4. Updated cross-phase DoD checklist:
- added explicit item requiring matrix completion for the active corridor before acceptance progression.

### Why this better matches USER direction
1. USER asked for a deep full picture of what "it worked locally" means.
2. This change makes that baseline explicit and non-optional, rather than implied by service-level coupling text.
3. It reduces hidden-process migration risk and improves blocker discovery before managed cutover.

### Validation
- Verified new section and DoD lines are present in `platform.build_plan.md`.

### Drift assessment
- No ownership or semantic law change; this is migration planning-method hardening.

### Cost posture
Docs-only pass; no paid services touched.

## Entry: 2026-02-12 4:49AM - Pre-change lock: create Local Run Process Inventory Matrix artifact for migration baseline

### Trigger
USER requested immediate creation of the `Local Run Process Inventory Matrix` to capture every process/subprocess that currently constitutes "it worked locally" before managed cutover work.

### Problem framing
The playbook now mandates a matrix, but no concrete artifact file exists yet. Without a materialized matrix, migration planning remains abstract and blockers can stay hidden.

### Decision
Create a dedicated matrix file in active dev_substrate implementation maps and populate it with process-level inventory extracted from local parity authorities.

### Inputs/authorities used
1. `docs/runbooks/platform_parity_walkthrough_v0.md`
2. `config/platform/run_operate/packs/local_parity_*.v0.yaml` (all six packs)
3. `makefile` parity/dev-substrate orchestration targets
4. `infra/local/docker-compose.platform-parity.yaml`
5. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (playbook requirement)

### Planned outputs
1. New artifact:
- `docs/model_spec/platform/implementation_maps/dev_substrate/local_run_process_inventory_matrix.md`
2. Build-plan reference update:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (explicit artifact path bullet under playbook section 0).
3. Log trail update:
- `docs/logbook/02-2026/2026-02-12.md`

### Inventory scope for this pass
1. Infrastructure daemons and bootstrap/init surfaces.
2. Oracle sync/pack/sort/validate local execution lane.
3. Control+Ingress chain (SR/WSP/IG/EB-backed flow).
4. RTDL core + decision-lane workers.
5. Case/Label workers.
6. Learning jobs workers and request enqueue commands.
7. Obs/Gov workers and report/conformance commands.

### Validation plan
1. Verify matrix file exists and contains stable process IDs with command/runtime/state/evidence fields.
2. Verify build plan references artifact path.
3. Confirm no semantic ownership changes (documentation-only inventory pass).

### Drift sentinel checkpoint
This pass is documentation and decomposition only. No runtime code or infrastructure behavior changes.

### Cost posture
Docs-only pass; no paid services touched.

## Entry: 2026-02-12 4:50AM - Applied Local Run Process Inventory Matrix artifact (first concrete baseline)

### Changes applied
1. Created baseline matrix artifact:
- `docs/model_spec/platform/implementation_maps/dev_substrate/local_run_process_inventory_matrix.md`
2. Linked artifact explicitly in active build plan playbook section:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
  - added artifact path under `0. Local run process decomposition baseline (mandatory first)`.

### Matrix coverage delivered in this pass
1. Infrastructure + bootstrap surfaces (compose daemons/init/bootstrap/run-id/orchestration launcher).
2. Oracle local lane (sync/pack/check/sort variants).
3. Control+Ingress chain (SR/WSP/IG + EB boundary), including key internal SR/WSP subprocess decomposition.
4. RTDL core workers (IEG/OFP/CSFB/ArchiveWriter).
5. RTDL decision-lane workers (DL/DF/AL/DLA).
6. Case/Label workers (CaseTrigger/CM/LS).
7. Learning jobs (OFS/MF workers + enqueue producers).
8. Obs/Gov workers (run reporter + conformance + manual support commands).
9. Current dev-substrate local-operator migration lane commands (`phase3a/3b/3c1/3c2`).

### Inventory properties
- Stable process ID scheme added by corridor (`LP-INF`, `LP-ORA`, `LP-CI`, `LP-RTDLC`, `LP-RTDLD`, `LP-CL`, `LP-LRN`, `LP-OG`, `LP-DM`).
- Each entry includes command/entrypoint, local runtime substrate, touched state/evidence surfaces, and managed migration note.
- Current process count in artifact snapshot: `65`.

### Validation performed
1. Verified artifact exists and is readable.
2. Verified build-plan playbook references the artifact path.

### Drift assessment
1. No runtime behavior change; documentation/inventory only.
2. Ownership boundaries and semantic rails unchanged.
3. This converts migration ambiguity into a concrete process-level baseline for managed mapping.

### Cost posture
Docs-only pass; no paid services touched.

## Entry: 2026-02-12 7:59AM - Executed Spine Green v0 parity verification run (200-event bounded stream) and assessed closure state

### Run identity and scope
1. Platform run id: `platform_20260212T075128Z`.
2. Scenario run id: `dcf42be5a84c65a95dfcb6f2108c10f8`.
3. Engine root: `s3://oracle-store/local_full_run-5/c25a2675fbfbacd952b13bb594880e92`.
4. Bounded stream scope executed: `WSP_MAX_EVENTS_PER_OUTPUT=200` with fraud traffic + fraud-context outputs.
5. Scope enforced for this migration baseline check:
- included: `Control/Ingress`, `RTDL`, `Case+Labels`, `Run/Operate+Obs/Gov`
- excluded: `Learning/Registry (OFS/MF/MPR lifecycle closure)`.

### Execution trail (major)
1. Brought local parity substrate up (MinIO/LocalStack/Postgres) and validated required streams/buckets.
2. Synced engine outputs into MinIO (`platform-oracle-sync`), sealed Oracle pack, and passed strict oracle check.
3. Built stream views for:
- `s3_event_stream_with_fraud_6B`
- `arrival_events_5B`
- `s1_arrival_entities_6B`
- `s3_flow_anchor_with_fraud_6B`
4. Started run/operate packs for spine-only lanes:
- `control_ingress`, `rtdl_core`, `rtdl_decision_lane`, `case_labels`, `obs_gov`
5. Published SR READY and executed WSP bounded pass.
6. Confirmed WSP stop markers at exactly `emitted=200` for all four outputs (`800` sent total).
7. Collected closure evidence from:
- `runs/fraud-platform/platform_20260212T075128Z/*`
- `runs/fraud-platform/operate/*/logs/*`
- `s3://fraud-platform/platform_20260212T075128Z/*`
- LocalStack Kinesis stream probes.

### Evidence summary
1. Control/Ingress:
- `platform.log` shows `SR READY published`, `WSP stream start/stop`, and IG summary/admission progression.
- IG receipts total: `1581`; sampled receipts include `eb_ref.offset_kind=kinesis_sequence`.
- SR artifacts present under `s3://fraud-platform/platform_20260212T075128Z/sr/*`.
2. RTDL:
- Stream presence confirmed on `fp.bus.rtdl.v1`.
- DF/AL/DL artifacts present and updating; DL converged to `health_state=GREEN` (`decision_mode=NORMAL` by 07:59:28Z).
- DF reasons are deterministic fail-closed compatibility outcomes (`ACTIVE_BUNDLE_INCOMPATIBLE`, `FAIL_CLOSED_NO_COMPATIBLE_BUNDLE`, `REGISTRY_FAIL_CLOSED`) and remain explainable for local parity.
3. Case+Labels:
- `case_trigger`, `case_mgmt`, `label_store` health/reconciliation artifacts present with GREEN health surfaces.
4. Run/Operate + Obs/Gov:
- `obs/platform_run_report.json` and `obs/environment_conformance.json` emitted for active run.
- Conformance status: `PASS`.
- Governance stream includes `RUN_STARTED`, `RUN_READY_SEEN`, `RUN_ENDED`, `RUN_REPORT_GENERATED`, and evidence-resolution events.

### Blocking findings against strict all-green declaration
1. `decision_log_audit` remains `health_state=AMBER` with `health_reasons=["UNRESOLVED_AMBER"]` and `lineage_unresolved_total=1`.
2. `make platform-operate-parity-status` is not spine-safe when Learning env vars are absent (`ENV_VAR_MISSING:PARITY_OFS_RUN_LEDGER_DSN`), even though Learning is explicitly out of migration scope.
3. IG `/v1/ops/health` without API key currently throws `500` (unauthorized path raises unhandled `IngestionError`); with valid header (`X-IG-Api-Key: local-parity-wsp`) health reports `GREEN`.

### Drift sentinel assessment
1. Ownership boundaries remained intact in observed event flow (`SR -> WSP -> IG -> EB -> RTDL -> Case/Labels -> Obs/Gov`).
2. No silent cross-plane ownership violations were observed.
3. Strict Spine Green v0 PASS cannot be asserted for this run while DLA health is AMBER.
4. This is classified as a material mismatch for migration green gate semantics and must be surfaced to USER prior to remediation.

### Cost posture
Local-only parity execution; no managed-cloud spend.

## Entry: 2026-02-12 5:29AM - Pre-change lock: pin Spine Green baseline for dev_substrate migration scope

### Trigger
USER requested migration planning resume on `dev_substrate` and directed that baseline "green" be pinned to the local-parity freeze story as **Spine Green**, not full Learning/Registry closure.

### Problem framing
Current dev_substrate planning references local-parity as baseline but does not yet explicitly scope migration acceptance against a pinned freeze-level green definition. Without this pin, migration sequencing can drift back into requiring local Learning-plane completion before managed-substrate promotion.

### Decision
Add an explicit migration-baseline section to `dev_substrate/platform.build_plan.md` that defines:
1. what is considered baseline green for migration,
2. what is explicitly out of scope for this migration phase,
3. which local-parity freeze authorities anchor that baseline.

### Authority basis used
- `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md`
  - Phase 3 complete,
  - Phase 4 + 4.6 complete,
  - Phase 5 + 5.10 complete,
  - Phase 6 active (not closed at freeze).
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md`
  - user-directed freeze transition entry (`2026-02-10 4:15PM`).

### Planned edit
- File: `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
- Add a top-level section that pins:
  - `Spine Green v0 = C&I + RTDL + Case/Labels + Run/Operate/Obs/Gov`,
  - `Learning/Registry (OFS/MF/MPR lifecycle closure)` out of scope for this migration phase.

### Validation plan
1. Verify the new baseline section is present and clear.
2. Verify no rail/ownership doctrine changes were introduced.
3. Log decision/action trail in `docs/logbook/02-2026/2026-02-12.md`.

### Drift sentinel checkpoint
Planning-only scope pin. No runtime/code behavior changes in this step.

### Cost posture
Docs-only pass; no paid services touched.

## Entry: 2026-02-12 5:29AM - Applied Spine Green baseline pin for dev_substrate migration planning

### Changes applied
1. Updated `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`.
2. Added section:
- `## Migration Baseline Gate (Spine Green v0)`.
3. The section now explicitly pins:
- baseline migration green = `C&I + RTDL + Case/Labels + Run/Operate/Obs/Gov`,
- local-parity freeze docs as authority,
- Learning/Registry full closure (`OFS/MF/MPR`) out of scope for this migration phase.

### Why this resolves the ambiguity
1. Removes mixed interpretation between runbook-wide "full stack" checks and freeze-time migration baseline.
2. Aligns dev_substrate sequencing with user-approved freeze story from local parity.
3. Preserves forward path: dev_substrate migration can proceed on spine semantics without requiring local Learning-plane closure first.

### Validation
1. Confirmed section present and discoverable near top-level scope/posture in build plan.
2. Confirmed no changes to non-negotiable rails, ownership boundaries, or fail-closed doctrine.

### Drift sentinel assessment
No designed-flow/runtime drift introduced; this is a migration-scope clarification pin.

### Cost posture
Docs-only pass; no paid services touched.

## Entry: 2026-02-12 5:45AM - Pre-change lock: capture ordered Spine Green local process flow list artifact

### Trigger
USER requested that the previously produced Spine Green local execution sequence be persisted "in a list somewhere" for continued migration planning.

### Problem framing
The process inventory matrix is intentionally broad and includes many rows (including non-Spine and dev-substrate operator rows). We need a concise, ordered, run-sequence artifact scoped strictly to Spine Green v0 that can be referenced without re-deriving process order from packs/runbook text.

### Decision
Create a dedicated implementation-map artifact that records the major Spine Green local process flow from start to finish, with each item including:
1. process name,
2. execution entry point (`make`, CLI, or run_operate step id),
3. one-line inputs -> outputs,
4. one concrete green-proof artifact path/topic/table.

### Authority basis used
- `docs/runbooks/platform_parity_walkthrough_v0.md`
- `makefile` local parity run and run_operate targets
- `config/platform/run_operate/packs/local_parity_*.v0.yaml`
- existing run evidence under `runs/fraud-platform/platform_20260210T091951Z/`

### Planned edits
1. Add file:
- `docs/model_spec/platform/implementation_maps/dev_substrate/local_run_spine_green_major_process_flow.md`
2. Append action/evidence trail to:
- `docs/logbook/02-2026/2026-02-12.md`

### Validation plan
1. Confirm file exists and is discoverable under dev_substrate implementation maps.
2. Confirm ordering matches local parity operator flow and run_operate pack sequencing.
3. Confirm Learning (`OFS/MF/MPR`) is excluded from scope.

### Drift sentinel checkpoint
Documentation-only operation; no runtime/component wiring changes.

### Cost posture
Docs-only pass; no paid services touched.

## Entry: 2026-02-12 5:45AM - Applied ordered Spine Green local process flow list artifact

### Changes applied
1. Added:
- `docs/model_spec/platform/implementation_maps/dev_substrate/local_run_spine_green_major_process_flow.md`
2. Captured strict Spine Green v0 local run order from substrate bring-up through obs/gov closure:
- CI (`SR -> WSP -> IG`),
- RTDL core + decision lane,
- Case/Labels,
- Run/Operate + Obs/Gov.
3. Explicitly excluded Learning-plane processes.

### Validation
1. Confirmed artifact is present in `docs/model_spec/platform/implementation_maps/dev_substrate/`.
2. Confirmed each step includes required fields (name, entry point, inputs/outputs, proof artifact).
3. Confirmed proof artifacts reference existing repo paths or configured parity topics/object-store paths already used in local parity authorities.

### Drift sentinel assessment
No designed-flow/runtime drift introduced. This improves migration planning clarity without changing execution semantics.

### Cost posture
Docs-only pass; no paid services touched.

## Entry: 2026-02-12 5:55AM - Pre-run execution plan for Spine Green v0 parity verification (200-event target)

### Trigger
USER requested proof that current local parity run satisfies `Spine Green v0` for migration baseline using:
- `docs/runbooks/platform_parity_walkthrough_v0.md`
- active local engine dataset rooted at `c25a2675fbfbacd952b13bb594880e92`
- bounded stream proof at `200` events.

### Scope lock
Verification scope in this run:
1. Control & Ingress closure.
2. RTDL closure.
3. Case + Labels closure.
4. Run/Operate + Obs/Gov closure.

Explicitly out of scope for migration baseline in this run:
1. Learning/Registry lifecycle closure (`OFS/MF/MPR`), except that any accidental activation will be treated as noise and excluded from pass/fail.

### Authority basis reviewed
1. `docs/model_spec/platform/platform-wide/platform_blueprint_notes_v0.md`
2. `docs/model_spec/platform/platform-wide/deployment_tooling_notes_v0.md`
3. `docs/model_spec/data-engine/interface_pack/*`
4. Platform narratives (control/ingress, RTDL, label/case, learning/evolution, obs/gov)
5. `docs/model_spec/platform/component-specific/world_streamer_producer.design-authority.md`
6. `docs/model_spec/platform/component-specific/flow-narrative-platform-design.md`
7. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
8. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
9. `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md`
10. `docs/runbooks/platform_parity_walkthrough_v0.md`

### Planned execution sequence
1. Bring parity substrate up and bootstrap (`stack-up`, `bootstrap`, `status`).
2. Refresh Oracle inputs for `c25...` into MinIO (`platform-oracle-sync`) and seal pack (`platform-oracle-pack`).
3. Build/validate stream view sorting (`platform-oracle-stream-sort` and targeted context/traffic checks if needed).
4. Create fresh `platform_run_id`.
5. Start run/operate packs only for Spine Green v0:
- `control_ingress`
- `rtdl_core`
- `rtdl_decision`
- `case_labels`
- `obs_gov`
6. Execute SR READY publish for active run.
7. Execute WSP bounded stream for `WSP_MAX_EVENTS_PER_OUTPUT=200` (single READY message).
8. Collect closure evidence:
- run-scoped logs and artifacts,
- IG receipts with EB refs,
- EB topic record presence across traffic/context/rtdl/case,
- component health/metrics artifacts (IEG/DL and lane components),
- obs/gov outputs (`platform_run_report`, governance log, env conformance).
9. Run post-pass validation commands from runbook Section `14.1`.
10. Assess drift sentinel criteria for ownership boundaries and fail-closed posture.

### Risk/edge cases pre-identified
1. `STREAM_VIEW_ID_MISMATCH` from stale/mismatched oracle root.
2. LocalStack stream replay causing repeated READY reprocessing.
3. Governance append conflict if manual run-report overlaps live reporter worker.
4. Stale watermark warnings after bounded run; classify informational only per runbook closeout rule unless ingress still active.
5. Sensitive tokens may appear in run artifacts/logs; do not copy secrets into docs.

### Validation and acceptance criteria for this run
1. Evidence supports all four in-scope Spine Green v0 corridors.
2. `200` bounded pass completes with expected admissions and downstream processing.
3. No unresolved fail-closed or ownership-boundary drift for in-scope planes.
4. If drift is detected/suspected, stop and escalate to USER before continuing remediation.

### Cost posture
Local-only parity execution (MinIO/LocalStack/Postgres); no managed-cloud spend expected.

## Entry: 2026-02-12 8:35AM - Pre-change lock for Spine Green remediation pass (parity-status env tolerance + DLA unresolved lineage)

### Trigger
USER directed: "proceed with both options" after prior 200-event Spine Green check surfaced:
1. `platform-operate-parity-status` hard-fail from missing `PARITY_OFS_RUN_LEDGER_DSN` / `PARITY_MF_RUN_LEDGER_DSN` even for spine-only verification.
2. `decision_log_audit` `UNRESOLVED_AMBER` caused by at least one chain with outcome present but decision/intent links absent.

### Problem framing
For migration baseline, Spine Green v0 is explicitly scoped to:
1. Control + Ingress
2. RTDL
3. Case + Labels
4. Run/Operate + Obs/Gov

Learning/Registry lifecycle closure remains out of scope. The runtime should not require explicit learning DSNs to report parity status for spine checks. Separately, DLA unresolved lineage in bounded runs indicates early-event intake gaps that can block green closure even when downstream corridors are healthy.

### Root-cause analysis captured
1. Parity status path:
- `make platform-operate-parity-status` unconditionally calls `platform-operate-learning-jobs-status`.
- Learning pack env used strict token expansion for `OFS_RUN_LEDGER_DSN` and `MF_RUN_LEDGER_DSN` without default fallback.
- Result: status command fails closed on missing env token before evaluating process state.
2. DLA unresolved path:
- Investigated unresolved chain had `outcome_count=1`, `intent_count=0`, `decision_event_id=NULL`.
- Candidate table lacked corresponding decision event, meaning event was not ingested at all (not merely lineage conflict).
- Local parity profile uses `event_bus_start_position: latest` for DLA; if worker starts after first run events are published, early decision/intent can be missed permanently while later outcomes are consumed.

### Decision
Apply two remediations:
1. Learning pack env fallback:
- make `OFS_RUN_LEDGER_DSN` and `MF_RUN_LEDGER_DSN` default-safe with fallback to `PARITY_IG_ADMISSION_DSN` (or empty as terminal fallback), so parity status remains evaluable in spine-only posture.
2. DLA intake robustness for run-scoped local parity:
- when inlet rejects event with `RUN_SCOPE_MISMATCH`, skip quarantine writes and only advance checkpoint (expected non-error while traversing non-target run records),
- for kinesis intake with no checkpoint and required run pin active, force first-read start position to `trim_horizon` to avoid missing early run events.

### Alternatives considered
1. Make `platform-operate-parity-status` skip learning status call.
- Rejected for now: alters command semantics and drifts from current parity operator surface.
2. Relax DLA health threshold (`amber_unresolved_total`) for bounded runs.
- Rejected: masks lineage incompleteness rather than fixing ingestion behavior.
3. Add lineage repair/backfill utility.
- Deferred: larger change than needed for immediate local parity remediation.

### Planned edits
1. `config/platform/run_operate/packs/local_parity_learning_jobs.v0.yaml`
2. `src/fraud_detection/decision_log_audit/intake.py`
3. `tests/services/decision_log_audit/test_dla_phase3_intake.py` (coverage updates)
4. `docs/logbook/02-2026/2026-02-12.md` (action trail)
5. Post-run notes append to:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md`

### Validation plan
1. Targeted tests for DLA intake behavior changes.
2. `make platform-operate-parity-status` should no longer crash from missing explicit learning DSNs.
3. Fresh 200-event parity run should close spine evidence with DLA health green (no unresolved lineage for run scope).

### Drift sentinel checkpoint
No ownership boundary shift introduced:
- run-scope mismatches remain fail-closed for target run data (not silently accepted), but non-target run records are treated as expected skip traffic during replay window traversal.
- lineage completeness remains enforced; remediation targets intake completeness, not health masking.

### Cost posture
Local parity only; no managed-cloud spend expected.

## Entry: 2026-02-12 9:00AM - Mid-pass decision update: unresolved DLA amber traced to AL initial-kinesis start gap

### New evidence from first remediation rerun
Run `platform_20260212T084037Z` after DLA/learning-pack changes produced:
1. `platform-operate-parity-status` stable (env expansion issue resolved),
2. DLA still `AMBER` with `lineage_unresolved_total=1`, but unresolved reason changed to:
- `MISSING_OUTCOME_LINK` (not `MISSING_DECISION`/`MISSING_INTENT_LINK`).

### Runtime forensics summary
1. DLA unresolved chain had:
- decision + intent present,
- no outcome.
2. Action Layer metrics for same run:
- `intake_total=175`, `outcome_executed_total=175`.
3. Decision Fabric metrics for same run:
- `decisions_total=176`.
4. AL backing stores contained no ledger/outcome row for the unresolved chain action id.

Inference from above:
AL missed one early action-intent event, which leaves DLA with one unresolved chain missing outcome.

### Root cause at implementation level
`src/fraud_detection/action_layer/worker.py::_read_kinesis` currently uses `event_bus_start_position` directly when no checkpoint exists.
With `start_position=latest` and no checkpoint, repeatedly acquiring new `LATEST` iterators can skip records that arrived between poll cycles before the first checkpoint advances.

### Decision
Apply same hardening pattern used for DLA:
1. For AL kinesis intake, when checkpoint is absent and `required_platform_run_id` is set, force first-read `start_position=trim_horizon`.
2. Keep existing run-scope gate behavior (non-target run intents are checkpoint-advanced and ignored).

This preserves fail-closed ownership while preventing initial-gap drops for run-scoped local parity.

### Planned edit delta
1. `src/fraud_detection/action_layer/worker.py` (`_read_kinesis` start-position selection).
2. Optional targeted test coverage deferred if integration rerun is sufficient for this pass; full run validation is mandatory either way.

### Drift sentinel checkpoint
No ownership-boundary drift:
- AL still only executes admitted `action_intent` under required run pin.
- Change is intake completeness at startup, not policy relaxation.

### Cost posture
Local-only rerun cost (MinIO/LocalStack/Postgres).

## Entry: 2026-02-12 9:01AM - Applied remediation set and validated Spine Green v0 on fresh 200-event run

### Changes applied
1. Learning-pack parity status env tolerance:
- `config/platform/run_operate/packs/local_parity_learning_jobs.v0.yaml`
  - `OFS_RUN_LEDGER_DSN` now defaults to `PARITY_OFS_RUN_LEDGER_DSN` then `PARITY_IG_ADMISSION_DSN`.
  - `MF_RUN_LEDGER_DSN` now defaults to `PARITY_MF_RUN_LEDGER_DSN` then `PARITY_IG_ADMISSION_DSN`.
2. DLA intake hardening:
- `src/fraud_detection/decision_log_audit/intake.py`
  - `RUN_SCOPE_MISMATCH` now checkpoint-skips without quarantine writes.
  - first kinesis read with no checkpoint + required run pin forces `trim_horizon`.
3. AL intake hardening (root-cause follow-on):
- `src/fraud_detection/action_layer/worker.py`
  - first kinesis read with no checkpoint + required run pin forces `trim_horizon`.
4. Tests updated:
- `tests/services/decision_log_audit/test_dla_phase3_intake.py`
  - run-scope mismatch skip path coverage,
  - kinesis first-read start-position behavior coverage.

### Test and validation execution
1. Unit tests:
- `tests/services/decision_log_audit/test_dla_phase3_intake.py` -> pass (`12`).
- `tests/services/decision_log_audit/test_dla_phase4_lineage.py` -> pass (`5`).
- `tests/services/action_layer/test_phase8_validation_matrix.py` -> pass (`3`).
2. Local parity rerun for closure (fresh run):
- run id: `platform_20260212T085637Z`
- bounded stream: `WSP_MAX_EVENTS_PER_OUTPUT=200`
- WSP stop markers observed for four outputs with `emitted=200`.
3. Post-run spine evidence:
- `platform-operate-parity-status` all packs running/ready.
- DLA health: `GREEN`, `lineage_unresolved_total=0`.
- DF health: `GREEN`.
- AL health: `GREEN` with `intake_total=195`, `outcome_executed_total=195`, matching DF decisions.
- Case/Label states in run report: all component health `GREEN`.
- Obs/Gov conformance: `obs/environment_conformance.json` status `PASS`.

### Drift sentinel assessment
No ownership-boundary drift detected in this pass:
1. No fail-open behavior introduced; run-scope gating remains enforced.
2. Intake hardening addresses startup completeness without relaxing contract checks.
3. Spine Green v0 in-scope corridors close with green health and conformance evidence.

### Cost posture
Local-only parity verification; no managed-cloud spend.

## Entry: 2026-02-12 9:01AM - Post-apply correction: avoid nested env token expansion in run-operate packs

### Issue discovered
Initial learning-pack fallback used nested token form:
- `${PARITY_OFS_RUN_LEDGER_DSN:-${PARITY_IG_ADMISSION_DSN:-}}`
- `${PARITY_MF_RUN_LEDGER_DSN:-${PARITY_IG_ADMISSION_DSN:-}}`

Run-operate env resolver does not support nested token parsing; this produced malformed literal expansion side effects during worker startup.

### Correction applied
1. `config/platform/run_operate/packs/local_parity_learning_jobs.v0.yaml`
- simplified to flat tokens:
  - `OFS_RUN_LEDGER_DSN: ${PARITY_OFS_RUN_LEDGER_DSN:-}`
  - `MF_RUN_LEDGER_DSN: ${PARITY_MF_RUN_LEDGER_DSN:-}`
2. `makefile`
- learning-jobs orchestrator targets now inject resolved vars explicitly from make defaults:
  - `PARITY_OFS_RUN_LEDGER_DSN="$(PARITY_OFS_RUN_LEDGER_DSN)"`
  - `PARITY_MF_RUN_LEDGER_DSN="$(PARITY_MF_RUN_LEDGER_DSN)"`
  - applied to `platform-operate-learning-jobs-{up,down,restart,status}`.

### Validation
1. `make platform-operate-learning-jobs-status` returns clean status with active run.
2. No malformed env-token side-effect artifact remains in repo root.

### Drift sentinel assessment
No semantic drift; this is a parser-compatibility correction preserving the intended fallback behavior.

## Entry: 2026-02-12 10:31AM - Pre-change lock for IG ops auth error mapping (unauth health path)

### Trigger
USER requested resolving IG `/v1/ops/health` behavior after confirming unauthenticated calls currently return HTTP `500`.

### Problem framing
For IG service security posture:
1. unauthenticated ops endpoints should fail closed with auth status (`401`), not internal-error status.
2. authenticated ops endpoints should return normal payload (`state/reasons` for health).

Current implementation in `src/fraud_detection/ingestion_gate/service.py` calls `_require_auth` directly inside `ops_health` and `ops_lookup` without local `IngestionError` handling. `IngestionError("UNAUTHORIZED")` bubbles to Flask and becomes `500`.

### Decision
1. Wrap `ops_health` and `ops_lookup` route bodies in the same error mapping pattern already used by `ingest_push`:
- `except IngestionError -> _error_status(exc)` (401 for unauthorized),
- defensive `except Exception -> 500` with reason code.
2. Add targeted service tests for unauthorized + authorized behavior on ops endpoints.

### Planned edits
1. `src/fraud_detection/ingestion_gate/service.py`
2. `tests/services/ingestion_gate/test_phase5_auth_rate.py`
3. Append action trail in `docs/logbook/02-2026/2026-02-12.md`

### Validation plan
1. Run targeted IG service tests (`test_phase5_auth_rate.py` and smoke check for service tests).
2. Confirm unauthenticated `/v1/ops/health` now returns `401` in tests.
3. Confirm authenticated `/v1/ops/health` still returns `200`.

### Drift sentinel checkpoint
No interface or ownership changes; only correcting error-code mapping at HTTP boundary for existing auth contract.

## Entry: 2026-02-12 10:37AM - Applied IG ops auth error-mapping fix and validated runtime behavior

### Changes applied
1. `src/fraud_detection/ingestion_gate/service.py`
- wrapped `ops_lookup` and `ops_health` route logic with:
  - `except IngestionError -> _error_status(exc)` response mapping,
  - defensive `except Exception -> 500`.
- this aligns ops endpoints with `ingest_push` error handling semantics.
2. `tests/services/ingestion_gate/test_phase5_auth_rate.py`
- added:
  - `test_ops_health_requires_api_key`
  - `test_ops_lookup_requires_api_key`
- asserts unauthenticated ops access returns `401` + `UNAUTHORIZED`, and authenticated health remains `200`.

### Validation
1. Tests:
- `pytest tests/services/ingestion_gate/test_phase5_auth_rate.py tests/services/ingestion_gate/test_phase4_service.py -q`
- result: `7 passed`.
2. Runtime (local parity process):
- restarted control/ingress pack to load patched service.
- unauthenticated request:
  - `GET http://127.0.0.1:8081/v1/ops/health` -> `401` with `{"error":"UNAUTHORIZED"}`.
- authenticated request:
  - with `X-IG-Api-Key: local-parity-wsp` -> `200` with `{"state":"GREEN","reasons":[]}`.

### Drift sentinel assessment
No flow/ownership drift introduced.
This closes an error-code correctness gap on auth failure paths while preserving fail-closed semantics.

## Entry: 2026-02-12 11:44AM - Canonical narrative hardening for spine_green_v0_run_process_flow.txt (Spine Green v0)

### Trigger
USER requested closing runtime/documentation gaps so the main local-parity narrative exactly matches the executed Spine Green v0 200-event run posture.

### Problem framing
The main narrative file had drift against observed runtime behavior:
1. bounded stream command did not encode the 200-event migration baseline,
2. status command implied full parity status despite Spine-only learning scope exclusion,
3. WSP/IG log locations and SR narrative log anchor were not aligned with run-operate reality,
4. IG ops-health auth contract and expected duplicate READY behavior were not explicit,
5. AL/DLA startup intake invariant used in remediation closure was undocumented,
6. no strict closeout evidence packet was pinned in the main narrative,
7. shutdown flow omitted optional substrate teardown.

### Changes applied
Updated docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt to:
1. add Spine-safe status commands and mark platform-operate-parity-status as full-parity (learning-inclusive),
2. set bounded manual WSP command to WSP_MAX_EVENTS_PER_OUTPUT=200 and note optional 20 -> 200 gate pattern,
3. align SR/WSP/IG log and artifact references to actual run paths under run-operate packs,
4. pin IG ops-health auth expectations (401 unauth, 200 auth),
5. add AL/DLA first-read 	rim_horizon run-scoped startup invariant,
6. add strict Spine Green closeout evidence and pass conditions (DF/AL/DLA/Obs + bounded emitted=200),
7. add optional substrate teardown command (make platform-parity-stack-down).

### Drift sentinel assessment
This pass reduces narrative/runtime drift and does not alter runtime semantics. Ownership boundaries and fail-closed posture are preserved; documentation now reflects the implemented run contract.

## Entry: 2026-02-12 11:54AM - Pre-change lock for run-operate log/evidence path split (operator control vs run-scoped truth)

### Trigger
USER asked to implement the recommendation from discussion: avoid run-operate log conflation while preserving current control surface semantics.

### Discussion captured (problem/challenge)
1. USER concern: if operator logs stay under `runs/fraud-platform/operate/<pack_id>/logs`, repeated runs append into the same files and become conflated.
2. Observed implementation confirms append posture:
- process logs are opened with append mode in `src/fraud_detection/run_operate/orchestrator.py` (`open("a")`),
- pack events are also append-only in `events.jsonl`.
3. Current split intent exists but is partial:
- `operate/<pack_id>` carries orchestration state/status/logs/events,
- `<platform_run_id>/<component>` carries component truth artifacts.
4. Migration challenge to solve:
- keep operator control stable and simple,
- prevent cross-run log blending,
- maintain clear run-scoped evidence ownership for audit/replay and migration gates.

### Recommendation selected (hybrid layout)
Keep operator state/status pack-scoped, but move daemon logs/events to run-scoped operate paths.

- Keep pack-scoped control files:
  - `runs/fraud-platform/operate/<pack_id>/state.json`
  - `runs/fraud-platform/operate/<pack_id>/status/last_status.json`
- Move operational log streams to run scope:
  - `runs/fraud-platform/<platform_run_id>/operate/<pack_id>/logs/<process>.log`
  - `runs/fraud-platform/<platform_run_id>/operate/<pack_id>/events.jsonl`

### Why this is selected
1. Eliminates cross-run log conflation by construction.
2. Preserves stable operator surface (`up/down/status`) and pack lifecycle controls.
3. Aligns evidence with run-scoped migration closure and incident forensics.
4. Avoids invasive changes to run-operate state machine.

### Alternatives considered
1. Keep everything under `operate/<pack_id>` and add rotation only.
- Rejected: still intermixes run narratives and requires retention/rotation policy tuning to be reliable for audit.
2. Move all run-operate files (including `state.json`/`status`) under run scope.
- Rejected for now: weakens operator continuity and makes control-plane status discovery noisier across run transitions.

### Planned edits
1. `src/fraud_detection/run_operate/orchestrator.py`
- introduce active-run-aware runtime root for logs/events,
- retain pack-scoped `state.json` and `status/last_status.json`.
2. run-operate tests (add/update) to assert:
- state/status remain pack-scoped,
- log/events resolve to run-scoped paths when active run id is present.
3. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
- update run-operate artifact paths to reflect hybrid layout.

### Validation plan
1. targeted run-operate unit tests.
2. `make platform-operate-*-status` sanity checks.
3. verify status payload `log_path` values now point to `<platform_run_id>/operate/<pack_id>/logs/...`.

### Drift sentinel checkpoint
No ownership boundary change. This is path/topology hardening of run-operate evidence surfaces; contracts and component semantics remain unchanged.

## Entry: 2026-02-12 11:56AM - Applied closure for hybrid run-operate path model (logs/events run-scoped, control state pack-scoped)

### Challenge solved
We needed to remove cross-run log conflation risk while preserving stable operator controls.
- Prior behavior appended process logs/events at `runs/fraud-platform/operate/<pack_id>/...`, causing multi-run interleaving.
- USER requested implementation plus explicit documentation of discussion/recommendation and the migration challenge being addressed.

### Applied implementation
1. `src/fraud_detection/run_operate/orchestrator.py`
- kept control-plane files pack-scoped:
  - `runs/fraud-platform/operate/<pack_id>/state.json`
  - `runs/fraud-platform/operate/<pack_id>/status/last_status.json`
- moved runtime logs/events to run-scoped runtime root when active run id is known:
  - `runs/fraud-platform/<platform_run_id>/operate/<pack_id>/logs/<process>.log`
  - `runs/fraud-platform/<platform_run_id>/operate/<pack_id>/events.jsonl`
- added helper methods:
  - `_runtime_root(active_run_id)`
  - `_logs_root(active_run_id)`
  - `_events_path(active_run_id)`
- updated event appends to target run-scoped path when run id is available.
- status rows now prefer persisted process `record.log_path` to avoid mismatched path display during run-id transition windows.

2. `tests/services/run_operate/test_orchestrator.py`
- added `test_logs_and_events_are_run_scoped_but_state_status_remain_pack_scoped`.
- test asserts:
  - log path resolves to run-scoped path,
  - `state.json`/`status/last_status.json` remain pack-scoped,
  - legacy pack-scoped `events.jsonl` is not created for active-run flow.

3. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
- updated run-operate artifact section to explicitly describe hybrid layout,
- updated WSP/IG log references and strict closeout log evidence path to run-scoped operate location.

### Validation evidence
- `.venv\Scripts\python.exe -m pytest tests/services/run_operate/test_orchestrator.py -q`
- result: `6 passed`.

### Recommendation carried forward
Use hybrid pathing as canonical:
- pack-scoped for orchestrator control state/status,
- run-scoped for process logs/events and run evidence.
This keeps operations simple while preserving clean per-run auditability and migration traceability.

### Drift sentinel assessment
No ownership/contract drift introduced. This is runtime artifact topology hardening only; component behavior and fail-closed semantics are unchanged.

## Entry: 2026-02-12 11:57AM - Live sanity validation after hybrid run-operate path implementation

### Runtime sanity actions
1. Executed `make platform-operate-control-ingress-restart` to force fresh process spawn under active run id.
2. Executed `make platform-operate-control-ingress-status`.
3. Inspected `runs/fraud-platform/operate/local_parity_control_ingress_v0/status/last_status.json`.

### Observed results
1. Status remained green (IG tcp probe open, WSP process alive).
2. Status `log_path` values now resolve to run-scoped paths:
- `runs/fraud-platform/platform_20260212T085637Z/operate/local_parity_control_ingress_v0/logs/ig_service.log`
- `runs/fraud-platform/platform_20260212T085637Z/operate/local_parity_control_ingress_v0/logs/wsp_ready_consumer.log`
3. Run-scoped events file exists and receives new events:
- `runs/fraud-platform/platform_20260212T085637Z/operate/local_parity_control_ingress_v0/events.jsonl`
4. Legacy pack-scoped events file remains as historical artifact from pre-change runs.

### Interpretation
Implementation is functioning as intended for new process lifecycles. Historical pack-scoped event files may coexist until cleanup policy is explicitly applied; this is expected and non-breaking.

## Entry: 2026-02-12 12:07PM - Pre-change lock for Addendum 1 state-machine/gates alignment

### Trigger
USER requested moving to Addendum 1 hardening after main narrative closure.

### Problem framing
`docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt` still carries drift versus current canonical run posture in a few gate/evidence points:
1. P6 evidence path still references legacy `runs/.../world_streamer_producer/...` style instead of run-operate run-scoped logs.
2. P4 IG health gate does not explicitly encode current auth contract (`401` unauth, `200` authenticated health).
3. P2 gate language should explicitly steer operators to Spine-safe status checks and clarify full parity status includes learning.
4. P9/P11 closeout language can be tightened to reflect strict Spine 200-event closure posture (DLA unresolved lineage = 0, conformance PASS).
5. Retry notes should explicitly classify duplicate READY skips as expected under replay history.

### Planned edits
- Update P2, P4, P5, P6, P9, P11 sections in Addendum 1 for path/gate/runtime correctness.
- Keep phase topology unchanged (no phase additions/removals).
- Keep scope lock unchanged (Learning/Registry still out of scope).

### Validation plan
1. line-by-line check for required canonical markers after edit:
- Spine-safe status posture,
- run-scoped operate log path in P6 evidence,
- IG auth gate language,
- DLA unresolved lineage closure criterion,
- conformance PASS criterion.
2. no code/runtime behavior changes in this pass (docs-only alignment).

### Drift sentinel checkpoint
Docs-only correction to reduce narrative drift; no ownership or runtime contract modifications.

## Entry: 2026-02-12 12:08PM - Applied closure for Addendum 1 state-machine/gates alignment

### What was updated
Updated `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt` to align with current canonical runtime behavior.

### Changes applied
1. Retry loop note for P6 now classifies duplicate READY skips as expected under control-bus history replay.
2. P2 gate/evidence tightened:
- explicit Spine-safe status posture,
- explicit note that full parity status includes learning-jobs,
- evidence split clarified (pack-scoped control files + run-scoped process log paths).
3. P4 gate/evidence aligned to IG auth contract:
- unauthenticated health returns `401`,
- authenticated health call is gate evidence.
4. P5 exit gate wording corrected to SR run log source.
5. P6 commit evidence path aligned to run-scoped operate log for WSP ready consumer.
6. P9 exit gate tightened with DLA closure criterion (`health GREEN`, `lineage_unresolved_total = 0`).
7. P11 conformance criterion made explicit (`environment_conformance.status = PASS`).

### Validation
Post-edit marker check passed for all targeted canonical anchors (Spine-safe status, IG auth gate, run-scoped log path, DLA unresolved lineage closure, conformance PASS).

### Drift sentinel assessment
Docs-only correction; no runtime semantics changed. This closes Addendum 1 drift against the canonical local Spine Green run posture.

## Entry: 2026-02-12 12:12PM - Pre-change lock for Addendum 1 operator checklist alignment

### Trigger
USER requested hardening `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt` after Addendum 1 state-machine alignment.

### Problem framing
Checklist still contains a few operator-risk drifts relative to canonical Spine Green posture:
1. P2 gate command uses full parity status without clarifying learning-inclusive semantics.
2. P3c required output set uses abstract labels that can be misread as literal Oracle `output_id` values.
3. P4/P5/P6 checks do not fully pin auth/log-path/runtime evidence details now used in canonical runs.
4. P9/P11 checks can be tightened for strict closure criteria (`DLA lineage_unresolved_total=0`, conformance `status=PASS`, no reporter/manual race).
5. bounded gate wording is approximate (`~20`, `~200`) instead of explicit operator env value posture.

### Planned edits
- Update checks 3, 6, 7, 8, 9, 12, 13, 15 and bounded-gate footer wording.
- Keep the 0..15 checklist structure intact.
- Keep scope lock unchanged (Learning/Registry out-of-scope for baseline).

### Validation plan
1. Marker scan for canonical anchors after edit:
- Spine-safe status posture,
- authenticated IG health gate,
- run-scoped WSP log path,
- explicit bounded `WSP_MAX_EVENTS_PER_OUTPUT=20/200`,
- DLA unresolved lineage closure,
- conformance PASS + no concurrent reporter/manual conflict note.

### Drift sentinel checkpoint
Docs-only correction to reduce operational ambiguity; no runtime behavior change.

## Entry: 2026-02-12 12:13PM - Applied closure for Addendum 1 operator checklist alignment

### What was updated
Updated `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt` so the checklist reflects canonical Spine Green local run behavior and reduces operator ambiguity.

### Changes applied
1. Check 3 (P2) now uses Spine-safe status commands and explicitly marks full parity status as learning-inclusive.
2. Check 6 (P3c) distinguishes logical required surfaces from dataset-specific output_id examples.
3. Check 7 (P4) pins IG auth-aware health contract (`401` unauth, `200` authenticated).
4. Check 8 (P5) anchors READY evidence to SR run log path.
5. Check 9 (P6) anchors WSP evidence to run-scoped operate log path and adds bounded Gate-200 completion expectation (`emitted=200`).
6. Check 12 (P8) path tightened to exact IEG reconciliation location.
7. Check 13 (P9) adds strict DLA closure (`health GREEN`, `lineage_unresolved_total=0`).
8. Check 15 (P11) clarifies no manual report while obs_gov reporter is active and requires conformance `status=PASS`.
9. Footer bounded gates now use explicit env values (`WSP_MAX_EVENTS_PER_OUTPUT=20/200`) rather than approximate caps.
10. Minor indentation/readability cleanup for aligned checklist scanning.

### Validation
Post-edit marker scan passed for all targeted anchors:
- Spine-safe status posture,
- learning-inclusive parity status caveat,
- IG auth gate,
- run-scoped WSP log evidence,
- DLA unresolved lineage closure,
- conformance PASS,
- explicit Gate-20/Gate-200 env values.

### Drift sentinel assessment
Docs-only alignment pass; no runtime semantics changed.

## Entry: 2026-02-12 12:18PM - Pre-change lock for LS runtime-role terminology clarification (migration readability)

### Trigger
USER asked to clarify ambiguous wording such as `LS writer boundary (as implemented)` so migration planning can distinguish authority role vs concrete runtime unit.

### Problem framing
Current wording can be read as if LS is not a concrete process type. In local parity, LS is both:
1. an authority role (`writer boundary` for label truth semantics), and
2. a concrete run-operate unit (`label_store_worker` daemon worker).

Ambiguous phrases (`as implemented`, `daemon service or internal writer`) reduce migration clarity when mapping to dev packaging and ops ownership.

### Decision
Clarify docs by explicitly pairing role + runtime shape:
- Role: Label Store writer boundary semantics.
- Runtime (local parity): daemon worker `label_store_worker` under case_labels pack.

### Planned edits
1. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
- replace ambiguous LS phrase with explicit daemon worker wording.
2. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
- set LS job card type to DAEMON WORKER (local parity) and keep writer-boundary role language explicit.
3. `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`
- annotate LS writer boundary references with local-parity runtime mapping to `label_store_worker`.

### Validation plan
Post-edit scan for:
- `label_store_worker` references in the above files,
- explicit distinction between writer-boundary role and daemon worker runtime.

### Drift sentinel checkpoint
Docs-only clarification; no runtime or ownership semantics change.

## Entry: 2026-02-12 12:20PM - Applied terminology clarification for LS runtime role vs authority role

### What was clarified
Resolved ambiguity around phrases like `LS writer boundary (as implemented)` by explicitly separating:
1. authority role: LS writer boundary semantics (idempotent append-only label truth),
2. runtime shape in local parity: daemon worker `label_store_worker` in case_labels pack.

### Files updated
1. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
- case_labels pack process list now explicitly says LS is a daemon worker (`label_store_worker`) enforcing writer-boundary semantics.
- case/labels component section now explicitly states LS runtime shape in local parity.

2. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
- LS jobcard renamed to `daemon worker + writer boundary`.
- Type set explicitly to `DAEMON WORKER (local_parity pack-managed)`.
- Entry point set explicitly to `fraud_detection.label_store.worker`.
- Inputs clarified to CM->LS writer-boundary submission flow.
- additional non-LS ambiguous `as implemented` phrasing replaced with concrete wording where touched.

3. `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`
- LS writer-boundary references annotated with local-parity runtime mapping to `label_store_worker`.
- remaining vague `as implemented` phrasing in touched section replaced with explicit evidence/artifact wording.

### Validation
Post-edit scan confirms explicit `label_store_worker` mapping and removal of ambiguous LS `as implemented` wording in the touched docs.

### Drift sentinel assessment
Docs-only clarity pass; no runtime behavior or ownership semantics changed.

## Entry: 2026-02-12 12:22PM - Pre-change lock for run-id namespace clarity across main/addendum-1/checklist

### Trigger
USER requested a full blind-spot review of the three active migration docs to prevent future operator headaches.

### Blind spot found
Inconsistent identifier namespace in docs:
- main narrative predominantly uses `<platform_run_id>`,
- addendum state-machine and operator checklist still use `<run_id>` in multiple evidence paths.

This is risky because run docs also carry `scenario_run_id`; operators can misread `<run_id>` as scenario-scoped ID and query wrong paths.

### Decision
Normalize run-scoped artifact and object-store path references to `<platform_run_id>` across the two Addendum 1 docs.
Where text intends platform run identity (ACTIVE_RUN_ID), use explicit term `platform_run_id`.

### Planned edits
1. `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt`
2. `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`

### Validation plan
- Post-edit scan: no residual `<run_id>` placeholders in those two docs where platform run scope is intended.
- Quick readability pass to ensure no scenario-run references were accidentally overwritten.

### Drift sentinel checkpoint
Docs-only namespace clarification; no runtime semantic changes.

## Entry: 2026-02-12 12:24PM - Applied closure after full three-doc blind-spot review (main + addendum state machine + operator checklist)

### Review scope
Performed full section-by-section read of:
1. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
2. `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt`
3. `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`

### Blind spot found and resolved
Identifier namespace inconsistency:
- Addendum files used `<run_id>` while main doc used `<platform_run_id>`.
- This can be confused with `scenario_run_id` and lead to wrong artifact path checks during migration.

### Fix applied
Normalized platform-run artifact references in Addendum 1 docs to `<platform_run_id>` and explicit `platform_run_id` wording where intended:
- `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt`
- `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`

### Validation
- Post-fix scan confirms no residual `<run_id>` placeholders in the two Addendum 1 docs.
- Canonical marker scan across all three docs confirms retained alignment for:
  - Spine-safe status posture,
  - IG auth gate (401 unauth / authenticated health),
  - bounded gate values (`WSP_MAX_EVENTS_PER_OUTPUT=20/200`),
  - DLA closure criterion (`lineage_unresolved_total=0`),
  - conformance `status=PASS`,
  - LS runtime-role clarity (`label_store_worker`).

### Drift sentinel assessment
Docs-only clarity/consistency closure. No runtime behavior changes.

## Entry: 2026-02-12 12:44PM - Corrective closure for Addendum 1 phase-to-packaging namespace consistency

### Trigger
USER moved review scope to `docs/design/platform/local-parity/addendum_1_phase_to_packaging_map.txt`.

### Blind spot found
The packaging map still contained a legacy `<run_id>` placeholder in P11 (`OBS_GOV_CLOSED`) while the active local-parity docs had already been normalized to `<platform_run_id>`.

### Decision
Apply a minimal consistency correction only:
- replace `<run_id>` with `<platform_run_id>` in the P11 reporter evidence path example.

### File updated
1. `docs/design/platform/local-parity/addendum_1_phase_to_packaging_map.txt`

### Validation
- Post-edit scan confirms no residual `<run_id>` placeholder in this file.
- P11 now references `evidence/runs/<platform_run_id>/...` consistently with the other Addendum 1 docs.

### Drift sentinel assessment
Docs-only correction; no runtime behavior or packaging semantics changed.

## Entry: 2026-02-12 12:45PM - Addendum phase map wording normalization (P1 identity term)

### Additional clarity fix
After namespace correction in P11, a second ambiguity remained in P1 wording:
- `(run_id fixed for all processes)` could be misread as `scenario_run_id`.

### Applied update
In `docs/design/platform/local-parity/addendum_1_phase_to_packaging_map.txt`, P1 text is now:
- `(platform_run_id fixed for all processes)`.

### Validation
Quick scan confirms P1 and P11 both use platform-run terminology consistently.

### Drift sentinel assessment
Docs-only wording normalization; no runtime semantics changed.

## Entry: 2026-02-12 12:46PM - Pre-change plan for sequential hardening pass of remaining local-parity docs

### Trigger
USER directed: run through remaining local-parity files sequentially and fix them diligently.

### Scope
Target files in order:
1. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
2. `docs/design/platform/local-parity/addendum_3_rerun_cleanup_matrix.txt`
3. `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`
4. `docs/design/platform/local-parity/addendum_5_concurrency_backpressure_knobs.txt`
5. `docs/design/platform/local-parity/README.md`

### Authorities and alignment targets
- Canonical local run narrative in `spine_green_v0_run_process_flow.txt`.
- Addendum 1 docs already normalized around `platform_run_id`, spine-safe status posture, IG auth gate, and DLA closure requirements.

### Diligence checks per file
- Identity namespace consistency:
  - Use `platform_run_id` for platform-run scoped paths.
  - Keep `scenario_run_id` only where scenario-scope is explicitly intended.
- Path topology consistency:
  - ensure run-operate hybrid log/event paths reflect current implementation where relevant.
- Contract consistency:
  - IG health auth posture, conformance expectations, and baseline scope lock (Learning/Registry out-of-scope).
- Terminology clarity:
  - remove or tighten ambiguous placeholders where they create migration/operator confusion.

### Decision policy
- Apply minimal, high-signal edits only.
- Avoid structural rewrites unless a section materially conflicts with canonical runtime behavior.

### Validation plan
After each file edit:
1. targeted marker scan for changed terms/paths,
2. quick readability pass to avoid semantic drift,
3. append outcome to logbook.

### Drift sentinel checkpoint
This is a docs-consistency hardening pass only. Any discovered semantic/runtime conflict with canonical run posture will be escalated instead of silently edited.

## Entry: 2026-02-12 12:49PM - Pre-change lock for Addendum 2 (process job cards) consistency hardening

### File
`docs/design/platform/local-parity/addendum_2_process_job_cards.txt`

### Issues identified
1. Run/Operate orchestrator outputs still show old topology for logs/events under pack-scoped `runs/fraud-platform/operate/<pack_id>/...`.
   - Current implementation is hybrid:
     - pack-scoped control/state/status,
     - run-scoped logs/events at `runs/fraud-platform/<platform_run_id>/operate/<pack_id>/...`.
2. WSP job card log path examples only reference legacy direct component path and omit current pack-managed path.
3. IG job card health endpoint omits auth behavior contract that operators rely on.
4. Obs/Gov job card still uses legacy `<run_id>` placeholder for governance object path.

### Decision
Apply targeted corrections only in affected lines to preserve document structure while restoring canonical alignment.

### Planned edits
- Update Run/Operate output path block to hybrid topology.
- Update WSP output path notes to include pack-managed run-scoped path (and keep once-mode distinction explicit).
- Add IG health auth expectation (`401` unauth, `200` with API key).
- Normalize Obs/Gov governance path to `<platform_run_id>`.

### Validation
- Marker scan for `<run_id>` removal in this file.
- Marker scan for run-operate path references to ensure hybrid pattern present.
- Readability pass around modified blocks.

### Drift sentinel checkpoint
Docs-only alignment to already-implemented behavior; no runtime semantics changes.

## Entry: 2026-02-12 12:51PM - Applied closure for Addendum 2 job-card consistency

### File updated
`docs/design/platform/local-parity/addendum_2_process_job_cards.txt`

### Changes applied
1. Run/Operate orchestrator outputs updated to hybrid topology:
- pack-scoped: `runs/fraud-platform/operate/<pack_id>/state.json`, `.../status/last_status.json`
- run-scoped: `runs/fraud-platform/<platform_run_id>/operate/<pack_id>/events.jsonl`, `.../logs/<process>.log`
2. WSP card output paths clarified by runtime mode:
- pack-managed path under control_ingress operate logs,
- once-mode path under world_streamer_producer run root.
3. IG card now includes `/v1/ops/health` auth contract (`401` unauthenticated, `200` with API key).
4. Obs/Gov governance object path normalized from `<run_id>` to `<platform_run_id>`.

### Validation
- Marker scan confirms no residual `<run_id>` in this file.
- Readability pass on modified blocks completed.

### Drift sentinel assessment
Docs-only alignment to implemented local runtime behavior; no semantic/runtime changes.

## Entry: 2026-02-12 12:52PM - Pre-change lock for Addendum 3 lease identity wording

### File
`docs/design/platform/local-parity/addendum_3_rerun_cleanup_matrix.txt`

### Issue identified
In section (4) `CONTROL BUS / SR: LEASE_BUSY`, wording says "delete the single lease row ... for that run_id".
This is ambiguous against platform-run identity conventions and can be misread as `platform_run_id`, while SR lease contention is tied to scenario/equivalence identity discipline.

### Decision
Apply one wording clarification only to preserve document intent while removing namespace ambiguity.

### Planned edit
- Replace "for that run_id" with explicit "for that scenario/equivalence key identity" in section (4).

### Validation
- Readability pass on section (4) to confirm clear operator action semantics.

### Drift sentinel checkpoint
Docs-only clarity fix; no behavior or cleanup semantics changed.

## Entry: 2026-02-12 12:53PM - Applied closure for Addendum 3 lease-identity clarification

### File updated
`docs/design/platform/local-parity/addendum_3_rerun_cleanup_matrix.txt`

### Change applied
- In section (4) `CONTROL BUS / SR: LEASE_BUSY`, clarified surgical cleanup wording:
  - from "delete ... lease row ... for that run_id"
  - to "delete ... lease row ... for that scenario/equivalence-key identity".

### Why
Prevents operator confusion between SR lease identity and `platform_run_id` naming used in other docs.

### Validation
- Post-edit marker scan confirms updated wording and no residual ambiguous phrase in that section.

### Drift sentinel assessment
Docs-only wording fix; cleanup semantics unchanged.

## Entry: 2026-02-12 12:54PM - Addendum 3 minor namespace normalization

### File updated
`docs/design/platform/local-parity/addendum_3_rerun_cleanup_matrix.txt`

### Change applied
- Normalized `platform run_id` -> `platform_run_id` in section (11) safe action wording.

### Validation
- Marker scan confirms consistent `platform_run_id` spelling in the file.

### Drift sentinel assessment
Docs-only naming consistency correction; no semantic change.

## Entry: 2026-02-12 12:55PM - Pre-change lock for Addendum 4 IO ownership namespace normalization

### File
`docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`

### Problem framing
The IO ownership matrix is platform-run scoped (header already uses `runs/fraud-platform/<platform_run_id>/`), but many rows still use legacy `<run_id>` in filesystem and S3 path examples.
This inconsistency creates migration/operator ambiguity and can conflict with `scenario_run_id` naming used elsewhere.

### Decision
Normalize platform-run path placeholders in this file from `<run_id>` to `<platform_run_id>` where the context is platform-run artifact ownership.
No ownership semantics, writer boundaries, or component responsibilities will be changed.

### Planned edits
- Replace legacy `<run_id>` placeholders in path examples across matrix rows.
- Preserve scenario-specific identifiers (for example `<scenario_run_id>`) where explicitly intended.

### Validation
- Marker scan: zero `<run_id>` placeholders remaining in this file.
- Readability pass on representative sections (header, IG rows, RTDL rows, Obs/Gov rows).

### Drift sentinel checkpoint
Docs-only identity namespace correction; no runtime behavior change.

## Entry: 2026-02-12 12:58PM - Applied closure for Addendum 4 IO ownership hardening

### File updated
`docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`

### Changes applied
1. Normalized all platform-run path placeholders from `<run_id>` to `<platform_run_id>`.
2. Added IG health auth contract note in endpoint registry:
- `/v1/ops/health` => `401` unauthenticated, `200` with `X-IG-Api-Key`.
3. Updated WSP write surface to reflect runtime modes:
- pack-managed logs path under operate control_ingress pack,
- once-mode logs path under world_streamer_producer run root.
4. Updated IG write surface logs path to canonical pack-managed path, with optional service-native artifact path noted.

### Validation
- Marker scan confirms zero `<run_id>` tokens remain in this file.
- Readability pass confirms WSP/IG path blocks align with active local run topology.

### Drift sentinel assessment
Docs-only consistency update; ownership boundaries and component responsibilities unchanged.

## Entry: 2026-02-12 1:00PM - Pre-change lock for Addendum 5 knob-name and identity wording consistency

### File
`docs/design/platform/local-parity/addendum_5_concurrency_backpressure_knobs.txt`

### Issues identified
1. Global cap example uses `READY_MAX_EVENTS`, while the active docs use `WSP_READY_MAX_EVENTS`.
2. Single-writer identity wording uses generic `(run_id, writer_identity)` and should be explicit as `(platform_run_id, writer_identity)` for this local-parity track.

### Decision
Apply minimal wording corrections only; no structural changes to the knob matrix.

### Planned edits
- Replace `READY_MAX_EVENTS` with `WSP_READY_MAX_EVENTS`.
- Replace `(run_id, writer_identity)` with `(platform_run_id, writer_identity)`.

### Validation
- Marker scan for updated terms.
- Readability pass on section 0.

### Drift sentinel checkpoint
Docs-only naming correction; no behavioral guidance change.

## Entry: 2026-02-12 1:01PM - Applied closure for Addendum 5 consistency nits

### File updated
`docs/design/platform/local-parity/addendum_5_concurrency_backpressure_knobs.txt`

### Changes applied
1. Normalized global cap example to canonical knob names:
- `WSP_MAX_EVENTS_PER_OUTPUT / WSP_READY_MAX_EVENTS`.
2. Clarified single-writer identity tuple:
- `(platform_run_id, writer_identity)`.

### Validation
- Marker scan confirms `READY_MAX_EVENTS` alias removed and updated terms present.

### Drift sentinel assessment
Docs-only terminology alignment; behavior guidance unchanged.

## Entry: 2026-02-12 1:02PM - Pre-change lock for local-parity README consistency anchors

### File
`docs/design/platform/local-parity/README.md`

### Opportunity identified
README index is accurate but does not explicitly state two conventions now enforced in the addenda:
1. `platform_run_id` vs `scenario_run_id` identity split,
2. run-operate hybrid pathing (pack-scoped state/status; run-scoped logs/events).

### Decision
Add a concise conventions section to the README without changing document ordering or scope.

### Planned edits
- Add `Conventions` section with identity and artifact topology notes.

### Validation
- Quick readability check for index flow continuity.

### Drift sentinel checkpoint
Docs-only index enrichment; no runtime semantic change.

## Entry: 2026-02-12 1:03PM - Applied closure for local-parity README conventions anchors

### File updated
`docs/design/platform/local-parity/README.md`

### Change applied
Added `Conventions` section to anchor cross-doc interpretation:
1. `platform_run_id` vs `scenario_run_id` scope split,
2. run-operate hybrid artifact topology (pack-scoped state/status, run-scoped logs/events).

### Validation
- Readability pass confirms document ordering and roles remain unchanged.
- Index links continue to point to current `.txt` docs.

### Drift sentinel assessment
Docs-only index hardening; no runtime semantic change.

## Entry: 2026-02-12 1:03PM - Sequential remaining-files pass closure

### Scope completed (in order)
1. `addendum_2_process_job_cards.txt`
2. `addendum_3_rerun_cleanup_matrix.txt`
3. `addendum_4_io_ownership_matrix.txt`
4. `addendum_5_concurrency_backpressure_knobs.txt`
5. `README.md`

### Cross-file outcomes
- Platform-run namespace normalized (`<platform_run_id>`).
- Run-operate hybrid log/event topology reflected where relevant.
- IG health auth contract consistently documented.
- Knob names aligned to canonical env keys (`WSP_READY_MAX_EVENTS`).
- SR lease wording clarified to avoid run-id scope confusion.

### Final validation
- Folder-level scan shows no residual legacy `<run_id>` placeholders in local-parity docs.
- No runtime code changes introduced; docs-only pass.

### Drift sentinel assessment
No design-intent drift detected in this docs pass; changes reduce migration/operator ambiguity.

## Entry: 2026-02-12 1:11PM - Pre-change lock for comprehensive docs gate hardening (Spine Green v0)

### Trigger
USER requested patching all identified content issues so docs mirror runtime truth and prevent false-green declarations.

### Scope (docs-only)
1. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
2. `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt`
3. `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`
4. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`

### Issues to resolve
1. Strict closeout under-specifies in-scope plane closure (RTDL core + Case/Labels not hard-gated).
2. IG admission gate can pass on weak evidence (receipts/stream non-zero only) without explicit admitted_count guard.
3. ArchiveWriter treated as optional although RTDL core is in-scope.
4. Case+Labels closure conditionalized as "if exercised" despite in-scope closure requirement.
5. Main-doc authority statement implies runbook is direct source-of-truth even though runbook is a superset/full-parity narrative with different scope/path details.
6. Addendum 2 template fields not fully populated for CM/LS job cards.
7. RTDL core gate in checklist/state-machine lacks explicit artifact-level checks for OFP/CSFB/ArchiveWriter.

### Decision
Harden gates/evidence to artifact-first, run-scoped closure criteria matching active local run behavior.
No runtime semantics are being changed; only documentation acceptance criteria and narrative authority are corrected.

### Planned edits
- Main process flow:
  - clarify authority posture as Spine Green v0 derivative of full-parity runbook,
  - make ArchiveWriter and Case+Labels closure explicit and required,
  - expand strict closeout evidence and pass conditions to include RTDL core + Case/Labels artifact checks and IG admit signal.
- Addendum 1 phase-state-machine:
  - P7: require explicit admitted_count > 0 for run in addition to receipts/offset refs,
  - P8: replace optional archive language with required artifact checks,
  - P10: remove conditional LS closure and require concrete CaseTrigger/CM/LS artifacts + health,
  - P11 strictness remains conformance PASS.
- Addendum 1 operator checklist:
  - strengthen checks 10/11/12/14 with run-scoped artifact and counter criteria,
  - remove soft/optional wording where in-scope closure is required.
- Addendum 2 job cards:
  - complete CM and LS cards with checkpoint/state identity, required env, fail-closed behavior, reset/retry, idempotency details.

### Validation plan
1. Marker scan for removal of weak/optional closure phrasing in P8/P10 and checklist.
2. Marker scan for explicit added artifacts/health checks (ArchiveWriter, OFP, CSFB, CaseTrigger, CM, LS).
3. Ensure IG gates require run-scoped admitted_count signal.
4. Readability pass so phase flow remains coherent and operator-usable.

### Drift sentinel checkpoint
Docs-only acceptance-hardening aligned to observed runtime surfaces and scope lock. If any criterion cannot be evidenced in active run, escalation required; no silent downgrade.

## Entry: 2026-02-12 1:14PM - Applied closure: comprehensive Spine Green v0 docs gate hardening (runtime-truth alignment)

### Files updated
1. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
2. `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt`
3. `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`
4. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`

### What was corrected
1. **Authority posture in main narrative**
- Replaced direct "runbook is source-of-truth" wording with explicit scoped authority:
  - runbook is full-parity superset anchor,
  - Spine Green v0 scope lock/gates in local-parity docs govern this baseline.

2. **Strict closeout completeness (main narrative)**
- Expanded `11.1 strict closeout` evidence and pass criteria from decision-lane-heavy checks to full in-scope plane closure:
  - added required RTDL core health artifacts (ArchiveWriter/IEG/OFP/CSFB),
  - added required Case+Labels health artifacts (CaseTrigger/CM/LS),
  - added required positive ingress admit signal (`platform_run_report ingress.admit > 0`),
  - retained DLA lineage closure and bounded WSP completion gates.

3. **IG gate anti-false-green hardening**
- In phase-state-machine P7 and operator checklist check 10:
  - made `admitted_count > 0` a required gate signal,
  - clarified duplicate-only outcomes are fail conditions for Gate-200 closure.

4. **RTDL core closure hardening**
- Removed optional/archive-soft language.
- P8 and checklist now require explicit artifact paths and health/counter checks for:
  - ArchiveWriter (`health GREEN`, `metrics.seen_total > 0`),
  - IEG (`reconciliation + health GREEN`),
  - OFP (`health GREEN`, `events_seen > 0`),
  - CSFB (`health GREEN`, `join_hits > 0`, reconciliation artifact present).

5. **Case+Labels closure hardening**
- Removed conditional "if exercised" posture.
- P10 and checklist now require explicit health+metrics closure for CaseTrigger/CM/LS:
  - `triggers_seen > 0`, `cases_created > 0`, `accepted > 0`.

6. **Addendum 2 completeness for CM/LS job cards**
- Filled template-level missing mechanics for both cards:
  - idempotency/dedupe posture,
  - checkpoint/state identity,
  - required env/run-scope pins,
  - fail-closed behavior,
  - reset/retry rules.

### Validation
- Marker scans confirm removal of weak optional closure wording and presence of required artifact/counter gates.
- No legacy `<run_id>` placeholders introduced.
- Updated paths and counters align with active run artifact surfaces (`platform_20260212T085637Z`).

### Drift sentinel assessment
No runtime behavior changed. This pass strictly hardens documentation acceptance criteria so declarations of Spine Green v0 cannot pass on partial/ambiguous evidence.

## Entry: 2026-02-12 1:16PM - Pre-change lock for runbook scope-authority clarification

### Trigger
USER requested proceeding with the same scope-locked authority note in the primary runbook to remove baseline confusion.

### File
`docs/runbooks/platform_parity_walkthrough_v0.md`

### Problem framing
The runbook is written as full-parity walkthrough (includes learning jobs and broad closure surfaces), while Spine Green v0 is a scoped migration baseline.
Without an explicit authority note, operators can treat full-parity instructions as baseline acceptance criteria and/or misread artifact topology expectations.

### Decision
Add explicit scope and authority note near the top:
- this runbook is full-parity superset,
- Spine Green v0 acceptance is governed by local-parity docs in `docs/design/platform/local-parity/`.
Also add concise run-operate artifact topology note to avoid path confusion.

### Planned edits
1. Insert `Scope and authority` subsection after intro paragraph.
2. Insert concise note in Run/Operate section clarifying hybrid artifact paths and deferral to local-parity docs for Spine Green acceptance.

### Validation
- Marker scan for `Scope and authority` note and local-parity doc references.
- Readability pass to ensure no change to full-parity mechanics.

### Drift sentinel checkpoint
Docs-only clarification; no runtime or policy behavior changes.

## Entry: 2026-02-12 1:18PM - Applied closure for runbook scope-authority and artifact-topology clarification

### File updated
`docs/runbooks/platform_parity_walkthrough_v0.md`

### Changes applied
1. Added explicit `Scope and authority` section near the runbook intro:
- marks this runbook as full-parity superset,
- points Spine Green v0 acceptance authority to local-parity docs under `docs/design/platform/local-parity/`.

2. Corrected Run/Operate artifact topology in section 3.1 to match current implementation:
- pack-scoped: `runs/fraud-platform/operate/<pack_id>/{state.json,status/last_status.json}`,
- run-scoped: `runs/fraud-platform/<platform_run_id>/operate/<pack_id>/{events.jsonl,logs/<process>.log}`.

3. Added explicit scope note in section 3.1:
- `learning_jobs` commands are full-parity superset,
- Spine Green v0 baseline should start only in-scope packs.

### Validation
- Marker scan confirms presence of scope-authority anchors and corrected run-scoped events/log paths.
- Readability pass confirms no procedural full-parity steps were removed.

### Drift sentinel assessment
Docs-only clarification update; runtime behavior unchanged.

## Entry: 2026-02-12 1:32PM - Pre-change lock for managed-compute-only repin (remove laptop dependency)

### Trigger
USER explicitly set new migration posture: no compute on laptop.

### Conflict detected
Current dev-min authority doc still pins local compute as default and AWS compute as optional.
This conflicts with the new user direction and can cause implementation drift.

### Decision
Apply a superseding repin in the migration authority and aligned packaging map:
1. `dev_min` compute is managed-only (no laptop compute) for platform services.
2. Allowed lane for v0 remains ephemeral ECS tasks/services (destroy-by-default).
3. `local_parity` remains local correctness harness and historical baseline only.

### Files to update
1. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`
2. `docs/design/platform/local-parity/addendum_1_phase_to_packaging_map.txt`

### Planned edits
- Add superseding repin note near authority boundaries.
- Replace local-default compute wording in pinned sections/table/appendix notes with managed-only posture.
- Flip phase-to-packaging map defaults from local to ECS-managed for dev_min lanes.

### Validation
- Marker scan confirms no remaining normative "local default compute" posture in migrated sections.
- Readability pass ensures dev-min budget/destroy posture remains explicit.

### Drift sentinel checkpoint
This is a design-authority repin documentation change. Implementation must follow new managed-compute-only lane for dev-min; no runtime code changes in this step.

## Entry: 2026-02-12 1:36PM - Applied closure: managed-compute-only repin (no laptop runtime compute)

### Trigger
USER direction: remove laptop dependency; no platform runtime compute on laptop.

### Files updated
1. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`
2. `docs/design/platform/local-parity/addendum_1_phase_to_packaging_map.txt`

### Authority repin applied
1. Dev-min compute posture changed from "local default + optional AWS" to:
- managed compute only for platform services,
- v0 lane pinned as ephemeral ECS tasks/services,
- destroy-by-default remains mandatory.

2. Networking/identity posture aligned:
- runtime services must use IAM runtime roles,
- laptop operator identity cannot be runtime principal for platform services.

3. State-store posture aligned with no-laptop policy:
- removed language allowing local runtime Postgres for dev-min runtime,
- pinned managed runtime state stores for CM/LS/receipts,
- S3 evidence export remains mandatory.

4. Decision matrix/table rows aligned:
- SR/WSP/IG/RTDL workers/CM-LS rows now indicate managed compute required,
- notes removed "Local (default)" interpretation for dev-min.

5. Cost/teardown appendix wording aligned:
- ECS runtime is now required demo compute lane,
- teardown checks retain mandatory "no ECS services/tasks remain".

### Packaging map alignment applied
`addendum_1_phase_to_packaging_map.txt` now reflects managed-compute-only dev-min path:
- removed local-default compute language,
- P2/P3/P4/P5/P6/P8/P9/P10/P11 defaults moved to ECS managed runtime,
- explicit "no laptop compute" constraint added in header,
- teardown path now references Kafka + ECS demo resources.

### Validation
- Marker scans show no remaining conflicting phrases such as:
  - `local compute default`,
  - `Local (default)` in dev-min columns,
  - `if compute runs locally`,
  - `No ECS services/tasks remain (if used)`.
- Updated docs remain internally consistent with demo→destroy budget posture.

### Drift sentinel assessment
This is a deliberate design-authority repin. Implementation must now target managed runtime compute for dev-min; local compute path is no longer acceptable for that rung.

## Entry: 2026-02-12 1:49PM - Corrective pre-change lock for option-1 remaining decision pins

### Trigger
USER requested: "pin the remaining decisions (option 1 alone)".

### Scope (remaining items)
1. IG dedupe key enforcement for migration.
2. Managed runtime DB/backend posture for IG/CM/LS.
3. Obs/Gov single-writer append lock mechanism.

### Problem framing
After managed-compute-only repin, the authority doc still had residual ambiguity in these areas:
- no explicit hard pin under primary stack selections for the three remaining decisions,
- one stale implementer-freedom clause still allowed local CM/LS runtime DB posture,
- semantic/evidence sections did not explicitly gate single-writer governance append behavior.

### Decision
Apply option-1 closure only (strict pinning path):
- enforce canonical IG dedupe tuple as promotion-critical,
- require managed runtime state backends for IG/CM/LS in dev_min,
- require lock-guarded single-writer governance append behavior with fail-closed conflict evidence.

### File targeted
`docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

### Planned edits
1. Add explicit pinned items in section 5.1 for dedupe, runtime-state backends, and Obs/Gov writer discipline.
2. Replace stale CM/LS local-runtime freedom sentence with managed-backend-only freedom.
3. Extend section 6.6 to include managed append lock primitive.
4. Remove residual local-compute backend allowance in section 11.3.
5. Add single-writer lock law in section 11.4 evidence requirements.
6. Add semantic gate clause in section 15.2 for writer-lock preservation.
7. Append decision-registry closures for these three decisions.

### Validation plan
- Marker scans for key phrases: `(platform_run_id, event_class, event_id)`, `laptop-resident`, `single-writer`, `S3_APPEND_CONFLICT`.
- Confirm stale local-runtime allowance removed in touched sections.
- Readability pass for numbered section continuity.

### Drift sentinel checkpoint
Docs are being aligned to implementation/runtime truth and pinned migration posture. This is documentation authority closure only; no runtime code changes in this step.

## Entry: 2026-02-12 1:50PM - Applied closure for option-1 remaining decision pins

### File updated
`docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

### Changes applied
1. Section 5.1 now explicitly pins three additional items:
- IG dedupe identity enforcement on `(platform_run_id, event_class, event_id)` with promotion-critical status,
- managed runtime state backends required for IG/CM/LS (no laptop-resident runtime DB),
- Obs/Gov single-writer append discipline with fail-closed contention behavior.

2. Section 6.4 implementer freedom corrected:
- removed "CM/LS may remain local" allowance,
- replaced with managed-engine/sizing freedom only.

3. Section 6.6 (Meta Layers) strengthened:
- added governance append lock-guard behavior in wiring changes,
- pinned a managed lock primitive resource for writer exclusivity.

4. Section 11.3 corrected:
- removed the remaining local-compute logging allowance line.

5. Section 11.4 strengthened:
- added MUST-level single-writer lock requirement for governance append writes,
- concurrent append attempts must fail closed with explicit conflict evidence.

6. Section 15.2 semantic gates strengthened:
- added explicit Obs/Gov append writer law gate.

7. Section 17 decision registry extended:
- added closed decisions for IG dedupe tuple enforcement,
- managed runtime backend posture for IG/CM/LS,
- Obs/Gov single-writer lock mechanism.

### Validation
- Marker scan confirms target pins are present.
- Marker scan confirms stale local logging allowance is removed from section 11.3.
- Readability pass complete for section numbering and continuity.

### Drift sentinel assessment
No platform runtime behavior changed in this step. This closes documentation ambiguity and prevents migration drift by making the three remaining decisions explicit and testable.

## Entry: 2026-02-12 2:34PM - Pre-change lock for remaining local-parity doc drift cleanup

### Trigger
USER requested: "Patch the remaining drifts" after reviewing `scratch_files/scratch.md` against local-parity docs and pinned migration authority.

### Drift set to close
1. IG job-card output ownership contradiction in Addendum 2 (IG listing decision/case/audit topics as outputs).
2. IG dedupe-gap phrasing in Addendum 2/3 that can be read as acceptable baseline rather than migration blocker.
3. CM local sqlite checkpoint wording in Addendum 2 not explicitly bounded to local_parity-only posture.
4. Main local run flow strict closeout section lacks explicit portability note that dev_min gates must bind to S3 evidence.

### Design intent
Preserve runtime-truth narration for local_parity while eliminating migration ambiguity:
- local docs remain honest about current implementation,
- pinned dev_min decisions remain non-negotiable,
- no wording should imply conflicting ownership or green claims across contradictory semantics.

### Files targeted
1. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
2. `docs/design/platform/local-parity/addendum_3_rerun_cleanup_matrix.txt`
3. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`

### Planned edits
1. Addendum 2 IG outputs: remove non-IG downstream topic lines and add explicit ownership note.
2. Addendum 2 IG dedupe section: keep current-state note but add explicit dev_min required tuple and blocker wording.
3. Addendum 2 CM checkpoint section: label sqlite checkpoint as local_parity implementation detail and add dev_min managed-checkpoint requirement note.
4. Addendum 2 known-gaps heading/content: change from "do not block v0" to migration-critical closure language.
5. Addendum 3 item (8): keep safe local rerun playbook but add explicit "not allowed for dev_min green" note.
6. Main flow strict closeout: add portability note mapping local FS closeout to dev_min S3 evidence bundle requirement.

### Validation plan
- marker scans for removed contradictory IG outputs lines,
- marker scans for new explicit dev_min blocker language,
- marker scans for CM sqlite bounded-to-local wording,
- readability pass to keep local run sequence unchanged.

### Drift sentinel checkpoint
Docs-only alignment work to prevent migration posture drift. No runtime behavior/code changes.

## Entry: 2026-02-12 2:35PM - Applied closure for remaining local-parity doc drifts

### Files updated
1. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
2. `docs/design/platform/local-parity/addendum_3_rerun_cleanup_matrix.txt`
3. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`

### Changes applied
1. **IG output ownership correction (Addendum 2)**
- Removed misleading IG output lines that listed `fp.bus.rtdl.v1`, `fp.bus.case.v1`, and `fp.bus.audit.v1` as IG outputs.
- Added explicit ownership note: IG only publishes admitted traffic/context; decision/case/audit lanes belong to downstream writers.

2. **IG dedupe gap reframed as migration blocker (Addendum 2 + 3)**
- Kept local-parity runtime-truth wording for current dedupe key implementation.
- Added explicit dev_min requirement language: canonical dedupe tuple `(platform_run_id, event_class, event_id)` is required for promotion.
- In rerun matrix item (8), added Option D remediation and explicit statement that Option A purge is local workaround only and not dev_min green-compatible.

3. **CM checkpoint portability bounded (Addendum 2)**
- Preserved current local sqlite checkpoint description as local_parity implementation detail.
- Added explicit dev_min requirement to move checkpoint/state to managed runtime backend (no local filesystem dependency).

4. **Known-gaps section hardened (Addendum 2)**
- Retitled from soft “do not block” phrasing to migration-critical closure language.
- Added explicit note that IG publish ambiguity must be modeled before dev_min green.

5. **Strict closeout portability note (Main flow)**
- Added explicit note that section 11.1 evidence list is local_parity closeout surface.
- Added explicit dev_min promotion mapping to S3 evidence prefix `evidence/runs/<platform_run_id>/...`.

### Validation
- Marker scans confirm contradictory IG downstream-output lines are removed.
- Marker scans confirm blocker language appears for IG dedupe and local workaround boundaries.
- Marker scans confirm CM sqlite wording is bounded to local_parity and paired with managed-backend requirement.
- Marker scans confirm strict-closeout portability note exists in the main flow file.

### Drift sentinel assessment
This pass is docs-only and aligns local narrative with pinned migration authority without rewriting current implementation truth.

## Entry: 2026-02-12 2:52PM - Pre-change lock for final local-parity drift closure set

### Trigger
USER approved patch scope to close remaining local-parity doc drifts from fresh scratch review.

### Approved scope
1. Model IG publish ambiguity with explicit `PUBLISH_UNKNOWN` branch semantics.
2. Pin ArchiveWriter local durable object-store path family + commit evidence in IO matrix.
3. Add explicit consumer start/checkpoint/restart runtime-basis summary (cross-component).
4. Add CM sqlite checkpoint as explicit IO surface + rerun handling.
5. Pin IG ingest auth posture (not only ops health auth) in local-parity docs.
6. Fix rerun matrix ownership misattribution for missing-stream publish failures.

### Files targeted
1. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
2. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
3. `docs/design/platform/local-parity/addendum_3_rerun_cleanup_matrix.txt`
4. `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`

### Constraints
- Preserve local runtime truth; no fabricated behavior.
- Use explicit migration-blocker language where behavior is not yet remediated.
- Keep ownership boundaries aligned with IO matrix laws and pinned migration authority.

### Validation plan
- Marker scan for `PUBLISH_UNKNOWN` branches and recovery playbook notes.
- Marker scan for ArchiveWriter object-store path family and commit evidence wording.
- Marker scan for IG ingest auth posture (`X-IG-Api-Key`, `/v1/ingest/push`, 401 path).
- Marker scan for CM sqlite checkpoint IO + rerun consequences.
- Marker scan that missing-stream symptom no longer attributes `rtdl/audit/case` stream ownership to IG.

### Drift sentinel checkpoint
Docs-only closure pass to align local process exposure with pinned migration semantics. No runtime code change in this step.

## Entry: 2026-02-12 2:56PM - Applied closure for final local-parity drift set

### Files updated
1. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
2. `docs/design/platform/local-parity/addendum_3_rerun_cleanup_matrix.txt`
3. `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`
4. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`

### Changes applied
1. **IG publish ambiguity modeled explicitly (docs/runtime posture)**
- Added `PUBLISH_UNKNOWN` failure/ambiguity branch semantics in main flow and rerun matrix.
- Added IG job-card fail-closed wording: no ADMIT success claim until eb_ref commit evidence is proven.

2. **IG ingest auth posture pinned (local_parity)**
- Added explicit ingest auth contract: `api_key` mode with `X-IG-Api-Key`; missing/invalid token returns 401.
- Added WSP caller requirement to send header/token expected by IG.
- Added IO matrix endpoint auth posture and WSP call header note.

3. **ArchiveWriter durable object-store path + commit basis exposed**
- Added local runtime archive object path family to IO matrix:
  `s3://fraud-platform/<platform_run_id>/archive/events/topic=<topic>/partition=<partition>/offset_kind=<offset_kind>/offset=<offset>.json`.
- Added explicit commit evidence basis: archive object exists + archive ledger offset advanced.

4. **Consumer start/checkpoint behavior made explicit**
- Added consolidated consumer start/checkpoint/restart summary in Addendum 2 for WSP, IEG/OFP/CSFB, DF, AL/DLA, CaseTrigger, CM, LS.

5. **CM sqlite checkpoint surfaced as explicit IO + rerun implication**
- Added CM sqlite checkpoint path as explicit read/write IO surface in IO matrix.
- Added rerun matrix note that deleting checkpoint file can force replay-like intake behavior.

6. **Missing-stream ownership misattribution corrected**
- Replaced IG-only missing-stream wording with producer ownership split:
  IG(traffic/context), DF/AL(rtdl), DLA(audit), CaseTrigger(case).

7. **Main run flow process exposure strengthened**
- Added `IMPLICIT STATES THAT PERSIST ACROSS RESTARTS` section (SR leases, WSP checkpoints, IG index, RTDL checkpoints, CM sqlite checkpoint, governance single-writer discipline).

### Validation
- Marker scans confirm:
  - `PUBLISH_UNKNOWN` branch exists in both process flow and rerun matrix,
  - IG ingest auth posture and header requirement are explicit,
  - ArchiveWriter object-store path family + commit basis are present,
  - CM sqlite checkpoint appears in IO matrix + rerun notes,
  - old IG ownership misattribution for rtdl/audit/case streams is removed.

### Drift sentinel assessment
Docs-only closure; no runtime code or contract implementation changed. This reduces migration blind spots while preserving local runtime truth.

## Entry: 2026-02-12 3:27PM - Pre-change lock for LS writer-boundary protocol hardening

### Trigger
USER requested: "Fix up #5" after confirming remaining gap is LS writer-boundary protocol specificity in local-parity exposure docs.

### Gap to close
Local-parity docs mention CM -> LS writer boundary but do not fully pin:
- boundary type/mechanics,
- request/ack semantics,
- idempotency/dedupe identity basis,
- failure/retry posture.

### Sources used for runtime-truth grounding
- `src/fraud_detection/case_mgmt/worker.py`
- `src/fraud_detection/case_mgmt/label_handshake.py`
- `src/fraud_detection/label_store/writer_boundary.py`
- `src/fraud_detection/label_store/contracts.py`
- local-parity exposure docs in `docs/design/platform/local-parity/`.

### Decision
Patch docs only (no code/runtime changes) to explicitly expose current local-parity LS boundary behavior:
- boundary type: in-process CM handshake calling `LabelStoreWriterBoundary.write_label_assertion`.
- writer responses and semantics:
  - `ACCEPTED` (new commit or replay-match),
  - `REJECTED` (contract invalid/missing evidence/dedupe collision/payload mismatch),
  - `PENDING` only at CM handshake layer when write exception occurs.
- idempotency basis: deterministic `label_assertion_id` and dedupe tuple `(platform_run_id, event_id, label_type, label_assertion_id)`.
- failure/retry: fail-closed with bounded retries (`max_retry_attempts` policy) and explicit terminal accepted/rejected states.

### Files targeted
1. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
2. `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`
3. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`

### Validation plan
- marker scan for explicit LS protocol terms (`write_label_assertion`, ACCEPTED/REJECTED/PENDING, dedupe tuple, bounded retries).
- readability check to keep local-parity flow chronology unchanged.

### Drift sentinel checkpoint
Docs-only hardening to remove remaining implicit boundary semantics; no implementation/runtime behavior change.

## Entry: 2026-02-12 3:30PM - Applied closure for LS writer-boundary protocol hardening

### Files updated
1. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
2. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
3. `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`

### Changes applied
1. **Main flow protocol exposure added**
- Added explicit `LS WRITER BOUNDARY PROTOCOL (LOCAL_PARITY)` section under Case+Labels in the canonical run flow.
- Pinned boundary type, payload basis, writer outcomes, handshake status mapping, idempotency basis, and bounded retry posture.

2. **Job card protocol semantics pinned**
- Expanded LS job card with explicit local boundary call shape:
  `LabelStoreWriterBoundary.write_label_assertion(assertion_payload)`.
- Added writer status semantics (`ACCEPTED | REJECTED`) and CM handshake mapping
  (`EMISSION_ACCEPTED | EMISSION_REJECTED | EMISSION_PENDING`).
- Added reason-code families and retry-bound statement (`max_retry_attempts` policy bound).

3. **IO ownership contract clarified**
- Expanded CM `CALL` contract to specify expected LS outcomes and exception treatment.
- Expanded LS `READ/WRITE/MUST NOT` rules with identity tuple and explicit prohibition on unresolved/exceptional ACCEPTED semantics.

### Validation
- Marker scans confirmed the protocol surfaces are present:
  - `LS WRITER BOUNDARY PROTOCOL (LOCAL_PARITY)` in main flow,
  - `write_label_assertion(assertion_payload)` in job cards + IO matrix,
  - `EMISSION_ACCEPTED | EMISSION_REJECTED | EMISSION_PENDING` mapping,
  - idempotency tuple `(platform_run_id, event_id, label_type, label_assertion_id)`,
  - bounded retry note tied to policy.

### Drift sentinel assessment
Docs-only closure aligned to runtime truth from CM/LS current implementation boundary. No runtime code or behavior was changed in this pass.

## Entry: 2026-02-12 3:37PM - Pre-change lock for A-E hardening pass after external review challenge

### Trigger
USER requested immediate correction pass after external reviewer challenged closure status and asked to "Fix the issues".

### Objective
Run one docs-only hardening pass that removes any residual ambiguity for the five contested items:
1. IG ingest auth contract exposure,
2. IG topic ownership consistency,
3. ArchiveWriter object-store commit semantics in local_parity,
4. explicit publish ambiguity (`PUBLISH_UNKNOWN`) semantics and run-closure effects,
5. LS writer-boundary commit semantics.

### Scope
Patch only local-parity exposure docs:
1. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
2. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
3. `docs/design/platform/local-parity/addendum_3_rerun_cleanup_matrix.txt`
4. `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`

### Decision rules
- Preserve runtime truth; do not invent implementation behavior.
- If wording is already present, strengthen it where ambiguity can still be inferred.
- Ensure same semantics appear in main flow + job cards + rerun matrix + IO matrix (no single-doc truth).

### Validation plan
- marker scan for:
  - ingest auth on `/v1/ingest/push` with `X-IG-Api-Key`,
  - ownership split for `traffic/context` vs `rtdl/audit/case`,
  - ArchiveWriter object-store key family + commit evidence basis,
  - `PUBLISH_UNKNOWN` fail-closed run-closure handling,
  - LS durable commit meaning for ACCEPTED.

### Drift sentinel checkpoint
Docs-only pass to de-risk migration misreads and close interpretation drift; no runtime behavior change intended.

## Entry: 2026-02-12 3:38PM - Applied closure for A-E hardening pass (ambiguity-elimination)

### Files updated
1. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
2. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
3. `docs/design/platform/local-parity/addendum_3_rerun_cleanup_matrix.txt`
4. `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`

### Changes applied
1. **IG ingest auth contract strengthened**
- Added explicit WSP ingest-caller contract in main flow and IO matrix.
- Clarified that health auth checks are not a substitute for ingest auth enforcement.

2. **ADMIT commit semantics tightened**
- Added explicit rule that ADMIT is only committed when receipt + admission-index `eb_ref` evidence are durable.
- Added explicit `PUBLISH_UNKNOWN` fail-closed rule in IG job card and rerun matrix wording.

3. **ArchiveWriter local parity durability semantics tightened**
- Added exact local parity archive object key family in main flow.
- Added explicit commit proof rule: object exists + archive ledger offset advanced.
- Clarified that filesystem artifacts are observability-only, not archive durability truth.

4. **Ownership clarity preserved and reasserted**
- Confirmed job card and rerun matrix language preserves the split:
  IG(traffic/context), DF/AL(rtdl), DLA(audit), CaseTrigger(case).

5. **LS ACCEPTED durability semantics tightened**
- Added explicit prohibition in IO matrix and job card language:
  ACCEPTED cannot be emitted before durable append commit in `PARITY_LABEL_STORE_LOCATOR`.

### Validation
- Marker scans confirmed presence of:
  - ingest auth contract language on `/v1/ingest/push`,
  - ADMIT commit evidence language (`receipt + eb_ref` durable),
  - `PUBLISH_UNKNOWN` fail-closed language,
  - archive object key family + observability-only FS clarification,
  - LS durable-commit ACCEPTED rule.
- Marker scans confirmed ownership split wording remains consistent across job cards/rerun matrix.

### Drift sentinel assessment
This pass is docs-only and aligns local-parity exposure text to runtime-truth posture while removing interpretation gaps that could mislead migration execution.

## Entry: 2026-02-12 3:47PM - Pre-change lock for PUBLISH_UNKNOWN observable-artifact pin

### Trigger
USER shared final external recommendation to make `PUBLISH_UNKNOWN` operator-visible as a named canonical artifact and requested issue closure without ambiguity.

### Runtime-truth check performed
Inspected IG implementation before doc edits:
- `src/fraud_detection/ingestion_gate/admission.py`
- `src/fraud_detection/ingestion_gate/index.py`
- `src/fraud_detection/ingestion_gate/pg_index.py`
- `src/fraud_detection/ingestion_gate/receipts.py`

Observed behavior:
- publish transport/timeout ambiguity is recorded as `PUBLISH_AMBIGUOUS` in admission index state (`record_ambiguous`),
- the event path is quarantined with reason code `PUBLISH_AMBIGUOUS`,
- IG writes both quarantine artifact and quarantine receipt (decision `QUARANTINE`) under existing IG prefixes.

### Decision
Do not invent new runtime artifact types.
Pin canonical evidence contract in docs as:
1. admission index state = `PUBLISH_AMBIGUOUS`,
2. `s3://fraud-platform/<platform_run_id>/ig/quarantine/<quarantine_id>.json` with reason code `PUBLISH_AMBIGUOUS`,
3. matching receipt under `ig/receipts/` with decision `QUARANTINE`.

### Scope
Docs-only hardening across local-parity pack:
- main run flow,
- job cards,
- rerun/cleanup matrix,
- phase/gate checklist,
- phase state machine,
- IO matrix.

### Drift sentinel checkpoint
This pass aligns operator-facing ambiguity semantics to implementation truth and eliminates state-name mismatch risk during migration.

## Entry: 2026-02-12 3:49PM - Applied closure for PUBLISH_UNKNOWN observable-artifact pin

### Files updated
1. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
2. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
3. `docs/design/platform/local-parity/addendum_3_rerun_cleanup_matrix.txt`
4. `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`
5. `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt`
6. `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`

### Changes applied
1. **Canonical mapping pinned**
- Documented that `PUBLISH_UNKNOWN` (operator ambiguity state) is materialized by current runtime as:
  - admissions state `PUBLISH_AMBIGUOUS`,
  - quarantine artifact under `ig/quarantine/`,
  - quarantine receipt under `ig/receipts/` with `decision=QUARANTINE` and reason code including `PUBLISH_AMBIGUOUS`.

2. **Gate semantics tightened**
- Added explicit P7 closure condition: no unresolved `PUBLISH_AMBIGUOUS` evidence for closure set.
- Added operator checklist pass criterion reflecting the same rule.

3. **Recovery playbook tightened**
- Added explicit artifact checks in rerun matrix item `(6b)` for ambiguous publish triage.
- Reasserted fail-closed behavior until ambiguity is reconciled.

### Validation
- Marker scans confirm all six docs now carry the same `PUBLISH_UNKNOWN -> PUBLISH_AMBIGUOUS evidence` mapping.
- Verified no ownership regressions introduced in IG/RTDL/case lane wording.

### Drift sentinel assessment
Docs-only closure, strictly aligned to IG implementation behavior; no runtime code changes were made.

## Entry: 2026-02-12 4:44PM - Pre-change lock for remaining local-parity operationalization drifts

### Trigger
USER provided another external review listing remaining ambiguity/operationalization drifts and requested correction.

### Runtime-truth checks completed before edits
- CaseTrigger source ingestion basis:
  - `src/fraud_detection/case_trigger/worker.py`
  - default `admitted_topics` is `fp.bus.rtdl.v1`; worker consumes `decision_response` and `action_outcome` from RTDL lane.
- DF posture integration basis:
  - `src/fraud_detection/decision_fabric/worker.py`
  - DF resolves posture via DL store (`dl_store_dsn`, `dl_stream_id`) through `DlCurrentPostureService`; no posture topic contract.
- SR read/write surfaces:
  - `src/fraud_detection/scenario_runner/runner.py`
  - `src/fraud_detection/scenario_runner/ledger.py`
  - SR reads resolved `oracle_engine_run_root`; canonical writes are `run_plan`, `run_record`, `run_status`, `run_facts_view`, `ready_signal`.
- DLA object-store evidence layout:
  - `src/fraud_detection/decision_log_audit/storage.py`
  - canonical path family: `<object_store_prefix>/<platform_run_id>/decision_log_audit/records/<audit_id>.json`.
- Daemon stream/checkpoint/run-scope surfaces:
  - archive_writer/action_layer/case_trigger/case_mgmt/dla workers + OFP/IEG/CSFB configs/stores.

### Drifts to close in docs
1. Add ArchiveWriter durable object evidence check into P8 gate/checklist (not only health artifacts).
2. Remove `and/or` ambiguity for CaseTrigger input basis; pin Spine Green v0 to RTDL lane intake.
3. Pin DL -> DF coupling explicitly (DF reads posture from DL store/stream identity, not DL topic).
4. Replace SR `and/or` read wording and expand SR canonical artifact surfaces.
5. Pin DLA object-store path family in local-parity docs.
6. Expand daemon checkpoint identity + run-scope enforcement matrix for all Spine Green v0 daemons.
7. Replace checklist “inspect” phrasing with concrete executable command patterns.
8. Tighten ambiguous topic-ownership wording in phase-state prechecks.
9. Mark addendum 5 as advisory matrix (non-authoritative) and point to authoritative sources.

### Files targeted
1. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
2. `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt`
3. `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`
4. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
5. `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`
6. `docs/design/platform/local-parity/addendum_5_concurrency_backpressure_knobs.txt`

### Drift sentinel checkpoint
Docs-only hardening pass; goal is operationally executable and unambiguous local-parity run exposure aligned to code/runtime truth.

## Entry: 2026-02-12 4:47PM - Pre-change lock for residual local-parity drift closure (review 13-point pass)

### Trigger
USER supplied an external review with 13 remaining ambiguity/operationalization items and requested direct correction.

### Re-assessment against current docs
1. Already closed in latest docs:
- P7/P10 gating includes publish-ambiguity fail-closed semantics.
- ArchiveWriter durable object evidence is already present in P8 gate/checklist.
- IG ingest auth and topic ownership split are already aligned in main flow + job cards.
2. Still open and to be patched in this pass:
- IO matrix still carries `and/or` ambiguity in SR read basis and CaseTrigger input basis.
- IO matrix does not yet pin DF posture dependency on DL store path.
- IO matrix still uses vague DLA object-store evidence wording and vague SR output surface wildcard.
- Phase/checklist can be tightened with explicit operator-visible checks for `PUBLISH_AMBIGUOUS`.
- Addendum 5 still appears half-authoritative (`verify exact env names`) without explicit authority boundary.
- Addendum 2 has thin-card unevenness; add explicit fallback pointer to authoritative pack YAML/env sources.

### Patch plan
1. Update `addendum_4_io_ownership_matrix.txt` to pin:
- SR read basis = `ORACLE_ENGINE_RUN_ROOT` (with optional manifest validation under same root),
- SR write surface artifact families,
- DF read posture coupling via DL store (`dl_store_dsn` + `dl_stream_id`),
- DLA evidence object path family,
- CaseTrigger read basis = RTDL lane only for Spine Green v0.
2. Update `addendum_1_phase_state_machine_and_gates.txt`:
- include ingest endpoint auth contract in P4 gate,
- make P5 commit evidence list canonical SR artifacts,
- tighten P7 ambiguity closure wording to explicit fail condition.
3. Update `addendum_1_operator_gate_checklist.txt`:
- make P4 ingest auth check explicit,
- add concrete command pattern to verify no unresolved `PUBLISH_AMBIGUOUS` evidence during P7 closure.
4. Update `addendum_2_process_job_cards.txt`:
- add explicit thin-card authority pointer,
- pin ArchiveWriter object path family in outputs.
5. Update `addendum_5_concurrency_backpressure_knobs.txt`:
- mark as conceptual control matrix (not authoritative env-key contract),
- point exact key ownership to pack YAML/component config.

### Drift sentinel checkpoint
Docs-only correction pass; objective is to eliminate residual ambiguity without changing runtime implementation posture.

## Entry: 2026-02-12 5:03PM - Applied residual drift closure patches (local-parity docs)

### Files updated
1. `docs/design/platform/local-parity/addendum_1_phase_state_machine_and_gates.txt`
2. `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`
3. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`
4. `docs/design/platform/local-parity/addendum_4_io_ownership_matrix.txt`
5. `docs/design/platform/local-parity/addendum_5_concurrency_backpressure_knobs.txt`

### Applied changes
1. P4/P5/P7 gate hardening:
- P4 now explicitly gates ingest auth on `/v1/ingest/push` (not only ops health).
- P5 commit evidence now enumerates canonical SR artifacts (`run_plan`, `run_record`, `run_status`, `run_facts_view`, `ready_signal`).
- P7 now explicitly states unresolved `PUBLISH_AMBIGUOUS` evidence is a FAIL for green closure.

2. Operator checklist executable bindings:
- Added concrete curl commands for IG ops + ingest auth behavior checks.
- Added concrete S3 commands to list receipts/quarantine prefixes and scan receipt payloads for `PUBLISH_AMBIGUOUS`.
- Preserved archive durable prefix check in P8 and clarified P7 fail condition if ambiguity evidence exists.

3. IO ownership closure:
- SR read basis pinned to `ORACLE_ENGINE_RUN_ROOT` with optional `_oracle_pack_manifest.json` validation under same root.
- SR write surface expanded from wildcard to canonical artifact families.
- DF read dependency now explicitly includes DL store posture coupling (`dl_store_dsn` + `dl_stream_id`), no posture topic.
- DLA evidence path pinned to concrete local-parity family:
  `s3://fraud-platform/<platform_run_id>/decision_log_audit/records/<audit_id>.json`.
- CaseTrigger input basis pinned to RTDL lane only (`fp.bus.rtdl.v1`, `decision_response` + `action_outcome`).
- Rule 4 case lane producer pin tightened to CaseTrigger-only for Spine Green v0.

4. Addendum authority posture cleanup:
- Addendum 2 now states thin-card fallback authority for exact env/checkpoint key names (pack YAML + component config).
- Addendum 5 now explicitly declares itself as semantic guidance, with exact key strings owned by pack/config files.

### Drift sentinel assessment
- This pass is docs-only and aligns process exposure to current runtime implementation.
- No runtime code paths were modified; no ownership boundary regressions introduced.

## Entry: 2026-02-12 5:02PM - Final micro-closeout for scratch diff alignment

### Trigger
USER asked to proceed with final recommendation: add explicit publish-ambiguity fail-closed line in main flow PASS CONDITIONS and record intentional non-adoptions in migration decision authority.

### Files updated
1. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
2. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`

### Applied changes
1. Main flow explicit closure rule:
- Added PASS condition: no unresolved `PUBLISH_AMBIGUOUS` evidence/receipts for active-run closure set.
2. Migration decision authority note:
- Appended Local-Parity Canonical Alignment notes that intentionally preserve:
  - SR read root pin to `ORACLE_ENGINE_RUN_ROOT` (+ optional manifest validation),
  - CaseTrigger direct ownership of case lane output in local parity (no IG corridor route).

### Drift sentinel assessment
Docs-only closure note; runtime implementation posture unchanged.

## Entry: 2026-02-12 5:13PM - Canonical phase-id normalization pass (P0-P11 as primary key)

### Trigger
USER supplied review identifying dual reference systems (timeline numbering vs P-phase ids) and requested unification to prevent migration drift.

### Problem statement
- `spine_green_v0_run_process_flow.txt` uses chronological numeric steps (`0..12`) without canonical P-id tags.
- `addendum_1_operator_gate_checklist.txt` mixes P labels with subphase variants (`P3a/P3b/P3c`) and one mixed label (`P7/P8`).
- `addendum_2_process_job_cards.txt` does not expose per-card `phase_id`.

### Decision
Adopt `P0-P11` as canonical phase identifiers across the local-parity exposure set. Keep chronology/checklist numbering as secondary human ordering, but every relevant section/card now carries explicit canonical `phase_id`.

### Planned edits
1. `spine_green_v0_run_process_flow.txt`
- Add canonical phase-id policy note near the timeline header.
- Annotate each major section header with its corresponding phase id.
- Add explicit P4 readiness section before SR (align chronology with state machine order).

2. `addendum_1_operator_gate_checklist.txt`
- Add canonical phase-id policy note.
- Normalize labels to canonical ids (`P3` instead of `P3a/b/c`, avoid ambiguous mixed labels by assigning a primary phase and noting support).

3. `addendum_2_process_job_cards.txt`
- Add `phase_id` field to template.
- Add `phase_id:` line to each in-scope job card with explicit mapping.

### Drift sentinel checkpoint
Docs-only normalization; no runtime behavior, component ownership, or substrate contracts are changed.

## Entry: 2026-02-12 5:21PM - Applied canonical phase-id normalization

### Files updated
1. `docs/design/platform/local-parity/spine_green_v0_run_process_flow.txt`
2. `docs/design/platform/local-parity/addendum_1_operator_gate_checklist.txt`
3. `docs/design/platform/local-parity/addendum_2_process_job_cards.txt`

### Applied changes
1. Main flow normalization
- Added explicit canonical-key note: `phase_id=P#` is primary; numeric timeline labels are secondary.
- Annotated major timeline steps with phase ids:
  - step 0/1 -> `P0`
  - step 2 -> `P1`
  - step 3 -> `P2`
  - step 4 -> `P3`
  - inserted step `4.4` -> `P4` (IG readiness precondition before READY publish)
  - step 5..11 -> `P5..P11`
  - optional shutdown -> `P12`

2. Checklist normalization
- Added canonical-key note at top.
- Replaced non-canonical labels `P3a/P3b/P3c` with `P3`.
- Replaced mixed `P7/P8` label with explicit primary ownership (`P7 primary; supports P8`).

3. Job card normalization
- Added `phase_id` field to card template.
- Added explicit `phase_id` to each in-scope job card.
- IG card set to `phase_id: P7` with explicit note that readiness is checked at `P4`.

### Drift sentinel assessment
This is a naming/reference unification pass only. It does not alter implementation mechanics or runtime truth ownership boundaries.

## Entry: 2026-02-12 5:18PM - Final polish for canonical phase-id references

### Trigger
USER requested final polish after phase-id normalization.

### Scope
1. `docs/design/platform/local-parity/README.md`
2. `docs/design/platform/local-parity/addendum_1_phase_to_packaging_map.txt`

### Planned polish
- Add concise canonical phase-id policy statement in README with an explicit P0..P11/P12 interpretation.
- Add matching policy statement in phase-to-packaging map so migration packaging references cannot drift back to alternate numbering.

### Drift sentinel checkpoint
Docs-only editorial consistency pass; no runtime or ownership semantics changed.

## Entry: 2026-02-12 5:24PM - Applied canonical phase-id polish in index + packaging map

### Files updated
1. `docs/design/platform/local-parity/README.md`
2. `docs/design/platform/local-parity/addendum_1_phase_to_packaging_map.txt`

### Applied changes
1. README polish
- Added explicit canonical-id convention:
  - `phase_id=P#` (`P0..P11`) is primary cross-doc reference key.
  - `P12` is teardown-only and outside green closure acceptance.
- Added concise `Canonical Phase IDs` section listing `P0..P12` meanings.

2. Packaging map polish
- Added canonical-id policy note directly under header constraints:
  - use `phase_id=P#` as only cross-doc identifier for migration planning,
  - `P0..P11` are lifecycle phases, `P12` is teardown-only.

### Drift sentinel assessment
Documentation consistency only; no mechanics, gates, ownership, or runtime contracts changed.

## Entry: 2026-02-12 5:33PM - Milestone close: local-process canonicalization complete; migration-design focus opened

### Milestone outcome (completed)
We have completed the local-parity process discovery/canonicalization needed before migration planning:
- end-to-end local process flow is explicitly documented and phase-gated (`P0..P11` canonical reference key),
- operator checklist and job cards are aligned to the same phase ids,
- major hidden-flow drifts were closed in docs (auth gates, publish ambiguity fail-closed posture, IO ownership, durable evidence surfaces, checkpoint/run-scope notes),
- initial dev-environment pinned decisions were captured in pre-design decision authority notes.

### Transition statement
This closes the “understand and pin how it works on my laptop” stage for Spine Green v0 documentation.

### Next design objective (opened)
Design and execute migration lift from local-parity runtime to dev managed substrate with:
- no local compute in the runtime path,
- managed compute for all run-time processing,
- preservation of canonical ownership boundaries, fail-closed gates, and append-only evidence semantics.

### Drift sentinel checkpoint
This entry is milestone accounting/planning only. No runtime code behavior changed in this step.

## Entry: 2026-02-12 6:14PM - Migration challenge note (near-resolution): lifting laptop flow to dev with zero local compute

### Challenge (active, near-resolved)
How to migrate the proven local Spine Green v0 process into dev managed substrate without hidden coupling or local runtime compute, while preserving the same gate semantics and truth ownership.

### Why this challenge matters
- Local success currently proves semantics, but migration fails if phase wiring/handles are implicit.
- Without a single per-phase mapping of compute + handles + gates + proof + rollback, implementation can drift and silently break green closure.

### Proposed resolution (accepted direction)
Adopt a two-document migration control surface:
1. `dev_min_spine_green_v0_run_process_flow.md` (dev twin of local process)
- Phase-canonical runbook (`P0..P11`, with optional preflight `P(-1)` and teardown `P12`),
- each phase must specify: managed compute target, handles used, gate owner, proof artifacts, rollback/rerun posture,
- explicit no-local-compute runtime rule across all phases.
2. `dev_min_handles.registry.v0.md` (single source of truth for wiring)
- authoritative names/IDs/paths for S3/Kafka/ECS/RDS/SSM/IAM/budgets,
- all runtime/config/docs references must resolve through registry keys,
- change-control rules for handle updates to prevent drift.

### Closure criteria for this challenge
- Both docs exist and are internally consistent with local-parity canonical phases and pinned dev-min decisions.
- Every `P0..P11` phase in the dev runbook has complete fields: compute, handles, gates, proof, rollback.
- No runtime step in the dev runbook depends on laptop compute.
- Stop-line conditions remain fail-closed (especially publish ambiguity and append-only truth ownership).

### Drift sentinel checkpoint
This entry records challenge framing and accepted resolution approach only; no runtime implementation changes in this step.

## Entry: 2026-02-12 9:07PM - Pre-change plan for migration_to_dev scaffold files

### Trigger
USER requested creation of empty files under `docs/model_spec/platform/migration_to_dev` and a README that explains file purpose + mapping to local-parity flow docs.

### Problem
The migration challenge has pinned two key dev-min control documents, but the target folder needs explicit scaffold files and an index note to anchor future authoring against local-parity canonical flow.

### Decision
Create a minimal scaffold now:
1. `dev_min_spine_green_v0_run_process_flow.md` (empty)
2. `dev_min_handles.registry.v0.md` (empty)
3. `README.md` (non-empty index/intent document)

### Planned implementation steps
1. Ensure `docs/model_spec/platform/migration_to_dev` exists.
2. Create the two empty markdown files listed above.
3. Write `README.md` with:
- purpose of this folder,
- list of scaffold files,
- explicit statement that these docs map/translate the flow in `docs/design/platform/local-parity`.
4. Verify created files and sizes.

### Drift sentinel checkpoint
Docs-only scaffold; no runtime behavior or contracts changed in this step.

## Entry: 2026-02-12 9:11PM - Applied migration_to_dev scaffold creation

### Files created
1. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md` (empty)
2. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md` (empty)
3. `docs/model_spec/platform/migration_to_dev/README.md` (index + mapping note)

### README content summary
- states folder purpose for Spine Green v0 migration scaffolding,
- enumerates the two empty scaffold files and intended roles,
- explicitly declares mapping source from `docs/design/platform/local-parity` canonical flow and addenda,
- reiterates canonical phase-id convention `P0..P11` (+ `P12` teardown-only).

### Verification
Directory listing confirms:
- `dev_min_spine_green_v0_run_process_flow.md` length `0`,
- `dev_min_handles.registry.v0.md` length `0`,
- `README.md` present and non-empty.

### Drift sentinel assessment
No behavioral/runtime edits. This is documentation scaffolding to enable controlled migration authoring.

## Entry: 2026-02-12 10:14PM - Pre-change plan: dev_min migration-doc drift closure (no-local P3 seed + handle alignment)

### Trigger
USER pinned a hard constraint: `P3` seeding from local sources is fully forbidden (including temporary bootstrap), and requested implementation of remaining migration-doc fixes.

### Problem statement
Current `migration_to_dev` docs contained drifts that can reintroduce laptop dependency or wiring ambiguity:
1. P3 text still allowed local seed/bootstrap language.
2. Runbook referenced several handle names that did not match the handle registry naming (`*_PREFIX_PATTERN` vs pinned `*_RUN_PREFIX_PATTERN` / `*_KEY_PATTERN`).
3. Runbook required IG auth/path handles not yet pinned in the handle registry.
4. IG health path default in registry (`/health`) drifted from local-parity contract posture (`/v1/ops/health`).
5. Phase identity wording needed explicit statement that `P(-1)` is preflight-only and not a green closure phase.

### Decision
Apply docs-only patch to these two files:
1. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`

Decision rails:
- remove all local-seeding allowance in `P3`; managed object-store source only,
- align runbook handle names to current registry vocabulary,
- add missing IG runtime/auth handles to registry,
- pin IG health endpoint to `/v1/ops/health`,
- keep `P(-1)` explicitly non-canonical for Spine Green closure.

### Planned verification
- grep/symbol sweep for old handle names and local-seeding language,
- verify IG handle block in registry includes ingest path + auth header + SSM key,
- verify runbook references those keys consistently.

### Drift sentinel checkpoint
Docs-only alignment to preserve design intent and prevent laptop/runtime drift. No runtime code or infra state changed in this step.

## Entry: 2026-02-12 10:14PM - Applied dev_min migration-doc drift closure patch

### Files updated
1. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`

### Applied changes
1. P3 local-seed prohibition hardened
- Replaced permissive seed text with strict managed-source-only policy.
- Added explicit ban on laptop-local, MinIO, and local filesystem seeding in P3 semantics + P3.A sub-step.

2. Canonical phase wording
- Added explicit note: `P(-1)` is packaging preflight and not part of Spine Green v0 closure acceptance.

3. Handle-name normalization in runbook
- Replaced old names with registry-aligned names:
  - `S3_ORACLE_RUN_PREFIX_PATTERN`
  - `S3_STREAM_VIEW_MANIFEST_KEY_PATTERN`
  - `S3_STREAM_SORT_RECEIPT_KEY_PATTERN`
  - `S3_QUARANTINE_RUN_PREFIX_PATTERN`
  - `S3_EVIDENCE_RUN_ROOT_PATTERN`
  - `S3_ARCHIVE_RUN_PREFIX_PATTERN`
- Updated networking handle refs in relevant sections:
  - `SUBNET_IDS_PUBLIC`, `SECURITY_GROUP_ID_APP`.

4. IG boundary clarity in runbook
- Added `IG_BASE_URL` and `IG_INGEST_PATH` to P4 required handles.
- Auth smoke check now explicitly targets `IG_INGEST_PATH`.
- WSP IG target handles now include `IG_INGEST_PATH`.

5. IG handle completeness in registry
- Added and pinned:
  - `IG_LISTEN_ADDR`
  - `IG_PORT`
  - `IG_INGEST_PATH = "/v1/ingest/push"`
  - `IG_HEALTHCHECK_PATH = "/v1/ops/health"`
  - `IG_AUTH_MODE = "api_key"`
  - `IG_AUTH_HEADER_NAME = "X-IG-Api-Key"`
  - `SSM_IG_API_KEY_PATH = "/fraud-platform/dev_min/ig/api_key"`

### Verification summary
- Old/ambiguous handle tokens removed from runbook.
- P3 no longer permits local seeding bootstrap.
- Registry now contains IG auth + ingest + health handles required by runbook.

### Drift sentinel assessment
Patch removes ambiguity and laptop-seed escape hatches in migration docs while preserving local-parity semantics and dev_min managed-substrate posture.

## Entry: 2026-02-12 10:39PM - Pre-change plan: close remaining migration-doc ambiguity rails (wildcards, missing handles, P3 seed source, DB backend)

### Trigger
USER requested proceeding with recommended cleanups and explicitly closing the four remaining ambiguity buckets:
1. wildcard handle refs in runbook,
2. referenced-but-undefined handles,
3. P3 managed seed source handles,
4. DB backend choice ambiguity.

### Problem statement
While core migration posture was already pinned, docs still had implementation-drift risk:
- runbook referenced wildcard families (`SSM_CONFLUENT_*`, `RDS_*`, `SVC_*`) in phase-critical sections,
- runbook referenced gate/evidence handles not yet present in handle registry,
- P3 forbidden-local policy existed but source-handle contract for managed seed source was not pinned,
- registry still presented RDS vs Aurora as open choice.

### Decision
Apply docs-only hardening in one pass:
- make runbook handle references explicit (no wildcard families in phase requirements),
- add missing runbook-referenced keys to registry (with defaults or phase-entry placeholders where appropriate),
- add explicit P3 seed-source handles + operator pre-step wording,
- pin DB backend to `rds_instance` for dev_min v0,
- align tag-key naming and remove duplicated observability value declarations.

### Planned verification
- grep sweep for wildcard handle families in runbook,
- grep sweep for newly added keys in registry,
- compatibility pass: runbook handle-like tokens should all resolve to registry keys (excluding phase labels/outcome enums),
- check DB section no longer presents parallel backend options.

### Drift sentinel checkpoint
Docs-only migration hardening. No runtime code, infra state, or component behavior changed.

## Entry: 2026-02-12 10:39PM - Applied migration-doc ambiguity closure patch set

### Files updated
1. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`

### Applied changes
1. Wildcard handle removal in runbook (phase-critical sections)
- Replaced wildcard families with explicit keys in P0/P1/P2/P8/P9/P10/P12 requirement blocks.
- Replaced ambiguous service groups with concrete service/task handles.
- Replaced wildcard topic/DB/confluent references with explicit handle sets.

2. Missing referenced-handle closure in registry
- Added run pinning controls: `CONFIG_DIGEST_ALGO`, `CONFIG_DIGEST_FIELD`, scenario derivation knobs.
- Added runtime control knobs: READY filter, WSP retry/inflight, RTDL gate knobs.
- Added reporter single-writer lock handles.
- Added decision idempotency + case/label subject-key handles.
- Added evidence path contracts for ingest/RTDL/decision/case/obs closure artifacts.

3. P3 managed seed source contract closure
- Added seed source handles:
  - `ORACLE_SEED_SOURCE_MODE`, `ORACLE_SEED_SOURCE_BUCKET`, `ORACLE_SEED_SOURCE_PREFIX_PATTERN`, `ORACLE_SEED_OPERATOR_PRESTEP_REQUIRED`.
- Added runbook line pinning that local parity upload is an operator pre-step outside `dev-min-run`; P3 seed jobs are S3-only.

4. DB backend ambiguity closure
- Pinned `DB_BACKEND_MODE = "rds_instance"`.
- Kept active DB identifiers as `RDS_INSTANCE_ID` + `RDS_ENDPOINT`.
- Marked Aurora explicitly out-of-scope for dev_min v0.

5. Naming consistency + observability de-dup
- Aligned P12 tagging handles to `TAG_*_KEY` names.
- Removed duplicated observability values by referencing Section 7.1 handles from Section 12.

### Verification summary
- No wildcard handle family patterns remain in runbook phase requirement sections.
- Previously missing keys now exist in registry.
- Handle-like token diff shows runbook keys resolve to registry keys; only non-handle terms remaining are phase labels/outcome enum names.
- DB section now contains a single pinned backend mode for v0.

### Drift sentinel assessment
Patch tightened migration docs against implementation drift while preserving the just-in-time pinning posture (defaults + explicit phase-entry placeholders where premature hard pinning would be harmful).

## Entry: 2026-02-12 10:49PM - Bridge sealed: local-parity to dev migration narrative is now implementation-safe

### Problem (previously observed)
- A major blocker in this project was not “writing code”, but translating a working local_parity flow into a dev environment without drifting semantics or getting trapped in infra chaos.
- The local build hides critical realities (managed compute wiring, IAM boundaries, runtime state backends, reproducible teardown), so the migration surface had many unseen decision points (e.g., oracle stream-sort compute, DB/state portability, evidence materialization).

### What changed / what we shipped (bridge sealed)
We sealed the local→dev_min bridge by producing two authoritative “migration spine” documents:

1) `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
   - A phase-by-phase dev_min translation of the canonical local parity Spine Green v0 flow.
   - Mirrors the same phase machine P(-1), P0..P12, preserving gates and meanings.
   - Pins packaging targets (ECS task vs ECS service), operator procedure, PASS proofs, and rollback semantics per phase.
   - Enforces non-negotiables: no laptop runtime dependency, CLI orchestration, demo→destroy, no NAT, no always-on LB, and scope lock (Learning/Registry out of baseline).

2) `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
   - A single source of truth for all wiring handles used by Terraform and runtime:
     - S3 buckets/prefix contracts (oracle/archive/quarantine/evidence),
     - Confluent cluster + topic map + SSM secret paths,
     - ECR image identity strategy,
     - ECS task/service identities,
     - managed DB handles,
     - IAM role map,
     - budgets/alerts and observability pins.
   - Prevents name drift and stops the implementer from inventing new resources “because it seemed easier”.

### Why these two docs seal the bridge
- They convert “it works locally” (implicit laptop compute + local shims) into an explicit, reproducible dev_min execution plan where every phase has:
  - declared substrate dependencies,
  - declared compute packaging,
  - pinned inputs/outputs,
  - explicit gates,
  - proof artifacts written durably (S3 evidence),
  - and rollback strategy.
- They force decision points to surface early (e.g., managed stream-sort lane, managed DB requirement for CM/LS, identity/role boundaries), rather than appearing mid-migration as hidden blockers.

### What would have happened without these docs (the failure mode)
- The migration would have degenerated into ad hoc infrastructure changes with silent semantic drift:
  - new schemas/contracts accidentally invented,
  - misaligned naming of topics/buckets/paths across components,
  - “temporary” laptop dependencies creeping back in,
  - partial implementations that appear to run but cannot be proven/replayed,
  - and expensive trial-and-error on managed services (cost leakage, teardown failures).
- Worst case: “a working toy deployed to AWS” with no trustworthy gates, no evidence bundle, and no clean way to prove correctness or reproduce runs—making the platform impossible to sell as production-like.

### Net result
- We now have a pinned, operator-shaped migration roadmap (Spine Green v0 baseline) that Codex can implement safely without redesigning the platform.
- Migration execution is now phase-by-phase, fail-closed, and evidence-backed rather than guesswork.

## Entry: 2026-02-12 11:05PM - **FRESH START RESET (AUTHORITATIVE)** for dev_substrate

### **EMPHASIS: We are starting dev_substrate migration implementation from scratch.**

### Why this reset was executed
- USER directive: cleanse prior faulty dev_substrate implementation paths so we do not adapt to legacy drift.
- Risk addressed: old partial wiring creates temptation to "build around" broken assumptions instead of following the migration runbook/handles authority.

### What was purged (legacy implementation surfaces)
1. Legacy dev_substrate scripts
- Removed: `scripts/dev_substrate/*`

2. Legacy dev_min Terraform environment implementation
- Removed: `infra/terraform/envs/dev_min/*` (including lock/config files)
- Removed local Terraform runtime residue directories under that env (`.terraform`, `terraform.tfstate.d`)

3. Legacy dev wiring configs
- Removed: `config/platform/dev_substrate/*`
- Removed: `config/platform/profiles/dev_min.yaml`
- Removed: `config/platform/sr/wiring_dev_min.yaml`

4. Legacy component-level dev_substrate implementation maps/build plans
- Removed component artifacts under `docs/model_spec/platform/implementation_maps/dev_substrate/` for event bus, ingestion gate, oracle store, scenario runner, and WSP, plus prior `platform.build_plan.md`.

### New baseline after reset
- Active dev_substrate maps are now only:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` (fresh baseline)
- Folder README was rewritten to mark the reset and to route all implementation work to migration authority docs.

### Authority after reset (non-negotiable)
- Execution authority:
  - `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
  - `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
- Legacy removed paths are non-authoritative and must not be resurrected without explicit USER repin.

### Counterfactual if reset was not done
- High probability of reusing inconsistent naming/wiring and reintroducing laptop-coupled shortcuts.
- Increased risk of false-green dev runs (gates appear to pass but semantics drift from migration authority).
- Elevated teardown/cost drift due mixed-old/new substrate assumptions.

### Drift sentinel checkpoint
This reset is intentional and user-directed. It removes migration drift vectors and forces phase-entry implementation to align strictly with the migration runbook + handles registry.
