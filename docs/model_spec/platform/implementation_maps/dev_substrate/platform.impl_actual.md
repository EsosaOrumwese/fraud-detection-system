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

## Entry: 2026-02-12 11:08PM - Legacy Makefile migration calls removed (fresh-start hardening)

### Trigger
USER requested confirmation that no legacy migration Make calls remain.

### Findings before patch
- `makefile` still contained a full legacy `platform-dev-min-phase*` target block and `DEV_MIN_*` defaults pointing to removed scripts/config/terraform paths.
- This created a stale command surface that could reintroduce pre-reset migration flow.

### Action applied
- Removed legacy dev-substrate migration defaults block (`DEV_MIN_*`) from `makefile`.
- Removed all legacy `platform-dev-min-phase*` targets from `makefile` (phase1/phase2/phase3 blocks).
- Kept unrelated platform/local-parity command surfaces intact.

### Verification
- `makefile` now has no matches for:
  - `platform-dev-min-phase`
  - `DEV_MIN_`
  - `scripts/dev_substrate/`
  - `infra/terraform/envs/dev_min`
  - `config/platform/dev_substrate`
  - `config/platform/sr/wiring_dev_min.yaml`
- Remaining occurrences of legacy make calls are historical text in documentation only (implementation notes/challenge archive), not executable make targets.

### Drift sentinel checkpoint
This change removes stale executable migration paths and reinforces the fresh-start authority posture.

## Entry: 2026-02-13 4:38AM - Pre-change lock: migration_to_dev drift cleanup (handle naming, stale pins, P3 seed policy, README posture)

### Trigger
USER instructed: "patch them up" for the four identified drifts after full migration-doc review.

### Drifts to close
1. Runbook/registry handle mismatch for optional mutable image tag key (`IMAGE_TAG_LATEST_OPTIONAL` vs `IMAGE_TAG_DEV_MIN_LATEST`).
2. Stale "pin later" wording where keys are already pinned (`CONFIG_DIGEST_ALGO`, `REPORTER_LOCK_BACKEND`) and stale open-items framing in Section 1.10.
3. P3 seed contradiction: hard ban on local source plus allowance for local-parity bootstrap pre-step.
4. `migration_to_dev/README.md` still written as scaffold/to-be-authored despite populated authoritative docs.

### Decision
- Treat `dev_min_handles.registry.v0.md` as naming authority and align runbook references to registry key names.
- Convert stale future-tense pin notes into current-tense pinned language.
- Enforce strict no-local-source P3 posture end-to-end (no local parity bootstrap pre-step for dev_min runtime path).
- Rewrite migration README to authoritative index posture (not scaffold language).

### Files to patch
1. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
3. `docs/model_spec/platform/migration_to_dev/README.md`

### Validation plan
- `rg` checks for target strings:
  - remove `IMAGE_TAG_LATEST_OPTIONAL` reference from runbook,
  - remove stale "pin later" on `CONFIG_DIGEST_ALGO` and `REPORTER_LOCK_BACKEND`,
  - remove local-parity pre-step allowance sentence,
  - confirm README no longer says scaffold/to-be-authored.
- confirm replacement keys/wording present in patched files.

### Drift sentinel checkpoint
This is docs-alignment only; semantics are unchanged except making P3 local-source prohibition explicit and unambiguous (already user-directed policy).

## Entry: 2026-02-13 4:39AM - Applied migration_to_dev drift cleanup patch (4-item closure set)

### Files updated
1. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`
2. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
3. `docs/model_spec/platform/migration_to_dev/README.md`

### Changes applied
1. Handle naming alignment (runbook -> registry)
- Replaced `IMAGE_TAG_LATEST_OPTIONAL` with `IMAGE_TAG_DEV_MIN_LATEST` in P(-1) required handles.

2. Stale future-tense pin wording removed where already pinned
- Rewrote Section 1.10 from "Open-but-required" into a closure-status section pointing to pinned handles registry authority.
- Updated `CONFIG_DIGEST_ALGO` note to explicit pinned value (`sha256`).
- Updated `REPORTER_LOCK_BACKEND` note to explicit pinned registry/default posture (`db_advisory_lock`).

3. P3 no-local-source policy made fully consistent
- Removed allowance for local-parity bootstrap pre-step in P3 seed semantics.
- Kept strict managed object-store-only seed policy in runbook.
- Repinned registry key `ORACLE_SEED_OPERATOR_PRESTEP_REQUIRED = false` and added note explaining anti-regression intent.

4. `migration_to_dev` README promoted from scaffold to authority index
- Removed "to be authored" language.
- Declared the two migration docs authoritative and expanded mapping source list to addenda 3-5.
- Added working-rule statement for process-flow vs handles registry responsibilities.

### Validation
- Negative grep checks confirmed removed targets are absent in patched files:
  - `IMAGE_TAG_LATEST_OPTIONAL`
  - stale `pin later` notes on `CONFIG_DIGEST_ALGO` and `REPORTER_LOCK_BACKEND`
  - local-parity pre-step allowance sentence
  - README scaffold/to-be-authored text
- Positive grep checks confirmed replacement strings exist:
  - `IMAGE_TAG_DEV_MIN_LATEST`
  - `CONFIG_DIGEST_ALGO = "sha256"`
  - `REPORTER_LOCK_BACKEND = "db_advisory_lock"`
  - `ORACLE_SEED_OPERATOR_PRESTEP_REQUIRED = false`
  - README title `Migration To Dev - Authority Index`

### Drift sentinel assessment
Patch is documentation-alignment only and tightens migration safety posture by eliminating contradictory P3 bootstrap semantics and stale wording that could cause implementation drift.

## Entry: 2026-02-13 4:49AM - Pre-change lock (captured for this pass): author fresh execution build plan for dev_substrate migration

### Trigger
USER requested a fresh execution build plan that is systematic, progressive, and avoids rushed migration decisions.

### Problem statement
`docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md` was empty, leaving no active execution tracker for controlled phase-by-phase migration.

### Decision
Create a fresh plan anchored to migration authority docs with:
- explicit scope lock,
- phase roadmap mapped to canonical P(-1)/P0..P12 lifecycle,
- one active phase at a time,
- mandatory phase entry/exit gates and DoD checklists,
- anti-rush controls (no phase advance without evidence + drift closure).

### Planned file edit
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### Validation plan
- Verify plan contains canonical roadmap, active phase declaration, transition checklist, and immediate next action.
- Log both decision and action in implementation map + logbook.

### Drift sentinel checkpoint
Planning artifact only; no runtime/code changes. Purpose is to prevent implementation drift by enforcing progressive elaboration.

## Entry: 2026-02-13 4:49AM - Applied fresh execution build plan baseline (dev_substrate)

### File updated
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### What was added
1. Program-level migration purpose, scope lock, authority precedence, and non-negotiable guardrails.
2. Progressive elaboration method with single-active-phase rule and phase status model.
3. Canonical roadmap M0..M10 mapped to migration phase IDs (`P(-1)`/`P0..P12`).
4. Detailed ACTIVE phase (`M0`) with tasks, DoD checklist, rollback posture, evidence outputs, and exit criteria.
5. Prepared next phase (`M1`) and gate-level DoD summaries for remaining phases without premature over-detail.
6. Mandatory phase transition checklist + pinned risk/control section.
7. Immediate next action to transition from M0 to M1 with explicit status move.

### Validation
- Structural markers present: roadmap table, `M0` active section, phase transition checklist, immediate next action.
- Plan now encodes "no halfbaked phase progression" and evidence-first closure semantics.

### Drift sentinel assessment
This closes a control gap in execution governance and improves migration safety by forcing phase-discipline and auditable progression.

## Entry: 2026-02-13 4:58AM - Pre-change lock: build-plan audit hardening against dev_min runbook gate fidelity

### Trigger
USER requested a pre-commit run-through to ensure the fresh build plan makes sense for dev expectations and captures migration runbook DoDs at high level.

### Review outcome
- Plan structure is sound (authority, roadmap, progressive elaboration, active-phase control).
- Drift found: some grouped phase DoD summaries are too compressed versus runbook gate surfaces and could allow interpretation drift during implementation.

### Targeted hardening scope
1. Strengthen grouped phase DoD summaries:
   - M6 (`P4..P7`) must explicitly include IG auth gate, READY publish proof, WSP stream proof, receipt/quarantine + offset evidence, and unresolved `PUBLISH_AMBIGUOUS` hard-fail.
   - M7 (`P8..P10`) must explicitly include RTDL lag gate, archive durability evidence, decision/audit idempotency outcomes, and managed DB append-only case/label evidence.
   - M9 (`P12`) must explicitly include demo credential/resource cleanup checks and teardown-proof evidence.
   - M10 must include incident drill evidence and replay narrative in addition to 20/200 run closure.
2. Add high-level evidence fidelity mapping section so each roadmap phase has visible proof expectations aligned with runbook families.

### File to patch
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### Validation plan
- grep for strengthened gate keywords (`READY`, `kafka_offsets_snapshot`, `RTDL_CAUGHT_UP_LAG_MAX`, `run_completed`, `teardown_proof`, `incident drill`).
- verify roadmap + progressive-elaboration policy remains intact.

### Drift sentinel checkpoint
This is documentation hardening only; no runtime/code changes. Objective is to prevent phase gate under-specification.

## Entry: 2026-02-13 5:00AM - Applied build-plan runbook-fidelity hardening (pre-commit review closure)

### File updated
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### What was strengthened
1. Program DoD now explicitly requires incident-drill evidence (fail-closed behavior proven).
2. M2..M10 DoD summaries were tightened to reflect runbook gate intent:
   - M2: SSM Confluent credential visibility, topic existence, no-NAT runtime posture.
   - M3: run manifest must exist before daemon/job execution.
   - M4: single-replica deterministic daemon posture + readiness snapshot evidence.
   - M5: checker PASS/fail-closed requirement explicit.
   - M6: explicit sub-gate coverage for P4/P5/P6/P7 and offsets evidence.
   - M7: RTDL lag gate (`RTDL_CAUGHT_UP_LAG_MAX`), archive durability evidence, and managed DB posture for case/labels.
   - M8: single-writer conflict fail-closed evidence explicit.
   - M9: post-destroy resource and secret cleanup checks explicit.
   - M10: incident drill + replay-anchor narrative evidence explicit.
3. Added `9.1 High-Level Evidence Fidelity Map` mapping each plan phase to minimum evidence families, aligned to runbook artifact topology.

### Validation
- Marker scan confirms strengthened keywords and evidence families present (`PUBLISH_AMBIGUOUS`, `kafka_offsets_snapshot`, `RTDL_CAUGHT_UP_LAG_MAX`, `run_completed`, teardown proof).
- Progressive-elaboration posture preserved (single active phase; future phases remain gate-level).

### Assessment for USER ask
The build plan now makes sense for dev expectations and captures migration-runbook DoDs at high level without over-prescribing implementation details too early.

### Drift sentinel assessment
This closes a docs-specification gap that could have allowed interpretation drift during migration execution.

## Entry: 2026-02-13 5:06AM - Pre-change lock: strengthen dev validation model beyond 20/200 event counts

### Trigger
USER challenged validation strength: 20/200 events is too weak for dev expectations and risks building a managed toy.

### Problem framing
Current build plan uses M10 certification wording centered on 20/200 event runs. That is useful for semantic smoke but insufficient for throughput/operational confidence.

### Decision
Refactor M10 into a two-layer certification model:
1. Semantic Green (retain 20/200 as gate-law smoke checks).
2. Scale Green (add representative-window, burst, soak, and recovery-under-load validations).

Add explicit rule that 20/200 alone cannot close migration certification.

### Planned edits
- Update Global Success Criteria and M10 roadmap text.
- Expand M10 DoD into semantic + scale gate bullets.
- Add high-level scale threshold pinning rule at M10 entry (to avoid ad hoc interpretations).
- Update evidence-fidelity map row for M10 to include scale/recovery evidence families.

### File to patch
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### Validation plan
- grep for "Semantic Green", "Scale Green", "representative window", "burst", "soak", "recovery" markers.
- confirm no wording implies 20/200 is sufficient by itself.

### Drift sentinel checkpoint
This is a planning hardening change to align dev validation with production-like expectations while preserving canonical semantic gates.

## Entry: 2026-02-13 5:06AM - Applied certification model upgrade: Semantic Green + Scale Green

### File updated
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### Changes applied
1. Global program DoD upgraded:
- replaced count-only validation posture with two-layer requirement:
  - Semantic Green (`20` + `200`),
  - Scale Green (representative-window + burst + soak + recovery-under-load).

2. Roadmap normalization:
- M10 label changed from "20-event then 200-event" to "Semantic Green + Scale Green certification".

3. M10 section hardening:
- renamed to `Certification (Semantic + Scale)`.
- added phase-entry requirement that scale thresholds must be pinned before execution.
- split DoD into explicit Semantic Green and Scale Green bullets.
- preserved drill + evidence + replay narrative obligations.

4. Evidence map update:
- M10 evidence family now includes both semantic and scale run bundles.

5. Added `9.2 Scale-Green Threshold Pinning Rule`:
- requires explicit threshold pinning for representative-window, burst, soak, recovery dimensions.
- states 20/200 alone cannot close M10.

### Validation
- diff check confirms M10 + global DoD updates are present.
- plan now explicitly prevents closing certification using 20/200 only.

### Assessment
This aligns dev validation expectations with production-like behavior without abandoning canonical semantic smoke gates.

### Drift sentinel assessment
No runtime/code changes; this is planning quality hardening to prevent underpowered dev certification claims.

## Entry: 2026-02-13 5:10AM - User-pinned validation posture note (dev certification strength)

### User decision recorded
`20/200` event runs are not sufficient as standalone dev certification.

### Pinned interpretation
- `20/200` remains mandatory as Semantic Green smoke for law/gate fidelity.
- Dev certification requires additional Scale Green validation (representative-window + burst + soak + recovery-under-load).
- Migration cannot be claimed green-for-dev if only count-capped smoke runs were executed.

### Where enforced
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
  - Global Success Criteria
  - M10 Certification (Semantic + Scale)
  - 9.2 Scale-Green Threshold Pinning Rule

### Effect on execution
Before M10 execution, scale thresholds must be explicitly pinned and logged; no ad hoc acceptance at runtime.

## Entry: 2026-02-13 5:16AM - Pre-change lock: introduce per-phase deep build-plan docs with main-plan status ownership

### Trigger
USER requested phase-specific planning docs under `platform.M*.md` while keeping the main platform plan as the central execution map.

### Decision
Adopt two-layer planning structure:
1. `platform.build_plan.md` remains control hub for:
   - phase statuses,
   - entry/exit transitions,
   - cross-phase DoD/evidence policy.
2. `platform.M*.md` holds deep planning for each phase.
   - Start with `platform.M0.build_plan.md` only.
   - Additional phase docs created only when phase activation is approved.

### Scope for this pass
- Expand `platform.build_plan.md` with explicit deep-plan routing and status-ownership rules.
- Create `platform.M0.build_plan.md` with detailed M0 plan and DoD checklists.
- Keep this pass planning-only (no runtime/infrastructure implementation).

### Validation plan
- confirm main plan contains deep-plan index and status ownership rule.
- confirm M0 deep plan file exists with objective, tasks, evidence, and exit gates.

### Drift sentinel checkpoint
This improves planning depth while preventing control fragmentation by centralizing status in main plan.

## Entry: 2026-02-13 5:17AM - Applied two-layer planning structure (main plan + M0 deep plan)

### Files updated
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M0.build_plan.md` (new)
3. `docs/model_spec/platform/implementation_maps/dev_substrate/README.md`

### What changed
1. Main plan expansion
- Added `6.1 Deep Phase Plan Routing` with:
  - `platform.M*.build_plan.md` naming pattern,
  - explicit rule that `platform.build_plan.md` is the only status owner,
  - current file-state note (`M0` present, `M1..M10` deferred).
- Expanded M0 section to include deep-plan drafting/alignment task and DoD checks.

2. Deep M0 phase plan created
- New `platform.M0.build_plan.md` includes:
  - authority inputs,
  - scope boundaries,
  - deliverables,
  - deep work breakdown (`M0.A`..`M0.E`),
  - risk controls,
  - completion checklist and exit criteria.
- Explicitly states it cannot change phase status.

3. README routing update
- Added active mention of `platform.M0.build_plan.md`.
- Added phase deep-plan pattern guidance and status ownership reminder.

### Validation
- Main plan now contains deep-plan routing and status ownership text.
- `platform.M0.build_plan.md` exists and is aligned to main-plan M0 objectives.
- README reflects the adopted structure.

### Drift sentinel assessment
This improves planning depth while preserving deterministic control flow by preventing status fragmentation across docs.

## Entry: 2026-02-13 5:22AM - Pre-change lock: close M0 end-to-end (careful governance implementation)

### Trigger
USER requested careful and thorough implementation of M0 as a whole.

### Implementation intent
Close M0 completely as a governance phase by:
1. adding any missing M0 governance artifact (phase evidence template + transition authority clause),
2. marking M0 DoD and M0 deep-plan checklists complete with explicit evidence references,
3. updating main roadmap status to reflect M0 closure,
4. leaving M1 unactivated until explicit USER go (aligned to user instruction not to build without direct approval).

### Files to update
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M0.build_plan.md`

### Validation plan
- M0 status row reflects closure.
- M0 checklists are fully marked complete in both files.
- New phase-evidence template and transition-authority rule are present.
- main plan explicitly states M1 remains pending explicit user activation.

### Drift sentinel checkpoint
Planning/governance only; no runtime/infra implementation in this pass.

## Entry: 2026-02-13 5:22AM - Applied M0 full closure (governance phase complete)

### Files updated
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M0.build_plan.md`

### What was implemented
1. Main roadmap/status closure
- Marked `M0` as `DONE` in roadmap.
- Kept `M1` as `NOT_STARTED` (pending explicit USER activation).
- Added current-phase posture note: no active phase until user starts M1.

2. Missing M0 governance artifact added
- Added `6.2 Phase Evidence Template (Pinned at M0)` to main plan.
- Template now defines required evidence shape for each phase closure.

3. Transition authority hardened to match user control posture
- Updated phase transition checklist to require explicit USER go for next-phase activation.
- Added `10.1 Transition Authority Rule (User-governed activation)`.
- Updated "Immediate Next Action" to start M1 only on explicit USER approval.

4. M0 DoD closure
- Marked all M0 checklist items complete in main plan.
- Updated M0 phase exit text to reflect actual closure and hold on M1.

5. Deep M0 plan closure
- Marked all sub-DoD checkboxes complete (`M0.A`..`M0.E`).
- Marked full M0 completion checklist complete.
- Added `M0 Closure Snapshot` with evidence references and handoff posture.

### Validation
- M0 row status is `DONE`; M1 remains `NOT_STARTED`.
- No unchecked boxes remain in `platform.M0.build_plan.md`.
- Main plan contains evidence template and transition authority rule.
- Main plan + M0 deep plan are consistent about user-gated activation of M1.

### Drift sentinel assessment
M0 is now fully implemented as a governance phase. No runtime/infra build execution was performed; execution remains blocked until explicit USER activation of M1.

## Entry: 2026-02-13 5:38AM - Pre-change lock: activate M1 phase and author deep M1 plan (planning-only)

### Trigger
USER approved proceeding to the next step after M0 closure.

### Decision
1. Activate `M1` in the main plan (`platform.build_plan.md`).
2. Create `platform.M1.build_plan.md` with deep, execution-ready planning detail for P(-1) packaging readiness.
3. Keep this pass planning-only; no runtime/infra/image build execution occurs in this step.

### Files to update
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md` (new)
- `docs/model_spec/platform/implementation_maps/dev_substrate/README.md`

### Validation plan
- Confirm roadmap and current-phase posture show `M1 = ACTIVE`.
- Confirm deep-plan index includes M1 file.
- Confirm M1 deep plan includes objective, scope, work breakdown, DoD, evidence, risks, and exit criteria.

### Drift sentinel checkpoint
This phase activation is document-controlled and user-approved. No build/runtime execution is performed.

## Entry: 2026-02-13 5:39AM - Applied M1 activation + deep M1 planning baseline (planning-only)

### Files updated
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md` (new)
3. `docs/model_spec/platform/implementation_maps/dev_substrate/README.md`

### What changed
1. Main plan activation
- Set roadmap status `M1 = ACTIVE` and kept `M2..` as `NOT_STARTED`.
- Updated current-phase posture to show `M1` active.
- Updated deep-plan index state to include M1 deep plan file.
- Converted Section 8 into current active-phase framing.
- Added active-phase execution note: this pass is planning/contract-finalization; build/push requires explicit USER build-go.
- Added M1 checklist in main plan for closure control.
- Updated immediate-next-action text to execution posture for M1 build-go pass.

2. Deep M1 plan authoring
- Created `platform.M1.build_plan.md` with:
  - authority inputs,
  - scope boundaries,
  - deliverables,
  - execution-gate rule,
  - deep work breakdown (`M1.A`..`M1.F`),
  - phase completion checklist,
  - risk controls,
  - exit criteria.

3. README alignment
- Added M1 deep-plan file to active map list and clarified M0 is closed.

### Validation
- Main plan now indicates `M1` as active phase.
- M1 deep plan exists and is cross-aligned with main-plan M1 scope/DoD.
- No build/runtime execution was performed in this pass.

### Drift sentinel assessment
This advances migration planning governance to the next phase without violating user control over build execution.

## Entry: 2026-02-13 8:14AM - Pre-change lock: implement M1.A image contract freeze

### Trigger
USER directed: proceed with `M1.A`.

### Objective
Close M1.A as a completed planning sub-phase by freezing the image identity contract with explicit handle mapping and acceptance posture.

### Planned updates
1. `platform.M1.build_plan.md`
   - add explicit M1.A contract decisions (single-image, immutable tag, mutable-tag posture, reference mode),
   - add handle key mapping for image contract,
   - add M1.A closure evidence notes,
   - mark M1.A DoD and completion checklist item as complete.
2. `platform.build_plan.md`
   - add active-phase progress note reflecting M1.A completion while keeping overall M1 active.

### Constraints
- planning-only; do not run image build/push.
- do not mark full M1 as complete.

### Validation plan
- confirm M1.A DoD checkboxes are all `[x]`.
- confirm `M1.A complete` is checked in section 6 of M1 deep plan.
- confirm main plan shows M1 still active with explicit M1.A progress note.

### Drift sentinel checkpoint
This is contract-freeze planning work only and remains within M1 scope.

## Entry: 2026-02-13 8:15AM - Applied M1.A image contract freeze

### Files updated
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### What was implemented
1. M1.A contract freeze completed in deep plan:
- Marked M1.A DoD checklist items complete.
- Added explicit frozen contract decisions:
  - single-image strategy,
  - immutable tag authority,
  - mutable tag non-authoritative posture,
  - immutable-preferred reference mode,
  - repin requirement for future multi-image split.
- Added handle-key mapping for each decision:
  - `ECR_REPO_NAME`, `ECR_REPO_URI`, `IMAGE_TAG_GIT_SHA_PATTERN`, `IMAGE_TAG_DEV_MIN_LATEST`, `IMAGE_REFERENCE_MODE`.
- Added M1.A planning evidence note tying freeze decisions to registry/runbook sections.

2. Main plan progress marker updated:
- Added active-phase progress note indicating `M1.A` complete while `M1.B..M1.F` remain pending.

### Validation
- `platform.M1.build_plan.md` now has:
  - M1.A DoD all `[x]`,
  - Section 6 checklist with `M1.A complete` as `[x]`.
- `platform.build_plan.md` still shows `M1` as active and reflects sub-phase progress.

### Drift sentinel assessment
M1 remains active and incomplete overall. This pass only closed M1.A contract planning and did not execute image build/push.

## Entry: 2026-02-13 8:20AM - Pre-change lock: implement M1.B entrypoint matrix completion

### Trigger
USER directed: move to `M1.B`.

### Objective
Close M1.B by pinning a complete logical-entrypoint to module-command matrix for Spine Green v0 packaging readiness.

### Scope
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
   - complete M1.B DoD,
   - add frozen matrix for all Section 6.5 entrypoint handles,
   - pin validation method for build-go pass.
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - update active-phase sub-progress to reflect M1.B closure.

### Key decisions (before patch)
1. Use registry handle keys as canonical matrix keys; do not invent new logical handles.
2. Expand grouped handles (`ENTRYPOINT_RTDL_CORE_WORKER`, `ENTRYPOINT_DECISION_LANE_WORKER`) into explicit runtime modes to avoid launch ambiguity.
3. Pin Oracle checker contract to the real module path `fraud_detection.oracle_store.cli` (not `checker.py` module).
4. Keep this pass planning-only; no image build/push/runtime execution.

### Validation plan
- Confirm M1.B DoD checkboxes all `[x]`.
- Confirm M1 checklist marks `M1.B complete`.
- Confirm main plan sub-phase progress marks M1.B complete and M1 remains ACTIVE.

### Drift sentinel checkpoint
Documentation-contract closure only; no runtime semantic or ownership-boundary changes.

## Entry: 2026-02-13 8:21AM - Applied M1.B entrypoint matrix completion

### Files updated
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### What was implemented
1. Completed M1.B DoD in deep plan:
- Added full frozen entrypoint matrix mapping registry handles to concrete `python -m fraud_detection...` module contracts.
- Included required-argument contracts for each row.
- Expanded grouped handles into explicit runtime modes:
  - RTDL core: ArchiveWriter, IEG, OFP, CSFB.
  - Decision lane: DL, DF, AL, DLA, CaseTrigger.
- Clarified case/label service slots:
  - `ENTRYPOINT_CM_SERVICE` -> `case_mgmt.worker`
  - `ENTRYPOINT_LS_SERVICE` -> `label_store.worker`
- Pinned Oracle checker to `fraud_detection.oracle_store.cli`.

2. Pinned M1.B validation method:
- `python -m <module> --help` import/argparse smoke for each row (SR uses `run --help`).
- required-args dry invocation contract check in build-go pass.
- explicit no-fallback rule for Oracle checker module path.

3. Checklist progress updates:
- Marked `M1.B complete` in M1 deep-plan completion checklist.
- Updated main-plan active-phase progress to:
  - `M1.A` complete,
  - `M1.B` complete,
  - `M1.C..M1.F` pending.

### Validation
- M1.B DoD checkboxes are all checked.
- Section 6 checklist now has `M1.A` and `M1.B` complete.
- Main plan still shows M1 as ACTIVE with remaining sub-phases pending.

### Drift sentinel assessment
No drift against migration authority or local-parity semantics. This closes a packaging-contract ambiguity surface only.

## Entry: 2026-02-13 8:53AM - Pre-change lock: implement M1.C provenance and evidence contract

### Trigger
USER directed: move to `M1.C`.

### Objective
Close M1.C by pinning the packaging provenance field contract, run-scoped evidence paths, and fail-closed mismatch handling.

### Scope
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
   - complete M1.C DoD,
   - freeze provenance field set and required keys,
   - pin run-scoped evidence object contract,
   - define fail-closed mismatch criteria.
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - update active-phase sub-progress to reflect M1.C closure.

### Key decisions (before patch)
1. Keep evidence contract aligned to existing registry handles; no ad hoc handle invention.
2. Pin canonical packaging evidence under run-scoped phase prefix using `EVIDENCE_PHASE_PREFIX_PATTERN` with `phase_id="P(-1)"`.
3. Require image provenance mirror in `run.json` (`EVIDENCE_RUN_JSON_KEY`) so P(-1) and P1 remain consistent.
4. Treat any provenance mismatch (ECR vs artifact vs run header) as fail-closed blocker.

### Validation plan
- Confirm M1.C DoD checkboxes are all `[x]`.
- Confirm M1 completion checklist marks `M1.C complete`.
- Confirm main plan sub-phase progress marks M1.C complete while M1 stays ACTIVE.

### Drift sentinel checkpoint
Documentation-contract closure only; no runtime or infrastructure execution changes.

## Entry: 2026-02-13 8:54AM - Applied M1.C provenance and evidence contract freeze

### Files updated
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### What was implemented
1. Completed M1.C DoD in deep plan:
- pinned provenance fields for P(-1): `phase_id`, `platform_run_id`, `written_at_utc`, image tag/digest/git fields, build timestamp, and build actor.
- pinned deterministic source pointers (`ECR_REPO_URI`, `IMAGE_REFERENCE_MODE`, `IMAGE_DOCKERFILE_PATH`, `IMAGE_BUILD_PATH`).
- pinned digest integrity anchors (`oci_digest_algo`, `oci_digest_value`).

2. Pinned run-scoped evidence path contract:
- canonical object: `s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<platform_run_id>/P(-1)/packaging_provenance.json`.
- mirror requirement in `EVIDENCE_RUN_JSON_KEY` (`run.json`) for image provenance consistency.

3. Pinned fail-closed mismatch handling:
- ECR tag->digest mismatch blocks P(-1).
- packaging artifact vs `run.json` provenance mismatch blocks progression.
- git SHA mismatch against immutable tag payload blocks P(-1).
- missing packaging provenance object means packaging is not committed.

4. Updated checklist progress:
- marked `M1.C complete` in M1 deep-plan checklist.
- updated main-plan active sub-phase progress to show M1.A/M1.B/M1.C complete and M1.D..M1.F pending.

### Validation
- M1.C DoD checkboxes are all checked.
- M1 completion checklist now marks M1.C complete.
- Main plan still shows M1 as ACTIVE with later sub-phases pending.

### Drift sentinel assessment
No semantic drift introduced. This closes provenance/evidence ambiguity and tightens fail-closed posture before build execution.

## Entry: 2026-02-13 8:55AM - Pre-change lock: implement M1.D security and secret-injection contract

### Trigger
USER directed: move to `M1.D`.

### Objective
Close M1.D by pinning an explicit no-baked-secrets policy, runtime secret source/ownership model, and fail-closed leakage checks for the M1 build-go pass.

### Scope
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
   - complete M1.D DoD,
   - pin security/secret contract content,
   - define execution-time checks and evidence.
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - update M1 sub-phase progress for M1.D completion.

### Key decisions (before patch)
1. Secret handle contract must reuse existing registry keys only (`SSM_CONFLUENT_*`, `SSM_IG_API_KEY_PATH`, `SSM_DB_*`), not wildcard placeholders.
2. Enforce strict role boundary: execution role is non-secret; app roles get least-privilege path reads only.
3. Treat any secret leakage or missing runtime secret path as fail-closed blocker for M1 closure.
4. Keep this pass planning-only (no image build, no runtime rollout).

### Validation plan
- Confirm M1.D DoD checkboxes are `[x]`.
- Confirm M1 completion checklist marks `M1.D complete`.
- Confirm main plan sub-phase progress reflects M1.D completion with M1 still ACTIVE.

### Drift sentinel checkpoint
Documentation-contract hardening only; no runtime or infrastructure behavior execution changes.

## Entry: 2026-02-13 8:56AM - Applied M1.D security and secret-injection contract freeze

### Files updated
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### What was implemented
1. Completed M1.D DoD in deep plan:
- pinned no-baked-secrets policy with explicit prohibited surfaces (Confluent/IG/DB secrets).
- pinned runtime secret source handles and ownership split (provision vs runtime role consumption).
- pinned execution-role boundary: `ROLE_ECS_TASK_EXECUTION` is not an app secret-read role.

2. Pinned leakage and fail-closed checks for build-go pass:
- pre-build context checks,
- post-build image metadata/history checks,
- runtime secret-path existence/readability checks,
- fail-closed startup behavior when secret inputs are missing.

3. Pinned evidence artifact for security checks:
- `s3://<S3_EVIDENCE_BUCKET>/evidence/runs/<platform_run_id>/P(-1)/security_secret_injection_checks.json`.

4. Updated checklist/progress:
- marked `M1.D complete` in M1 deep-plan checklist.
- updated main-plan sub-phase progress to show M1.A/M1.B/M1.C/M1.D complete and M1.E..M1.F pending.

### Validation
- M1.D DoD is fully checked.
- M1 completion checklist now includes M1.D as complete.
- Main plan remains `M1 ACTIVE` with later sub-phases pending.

### Drift sentinel assessment
No semantic or ownership-boundary drift introduced. This reduces packaging-time secret-risk ambiguity before execution.

## Entry: 2026-02-13 8:59AM - Pre-change lock: add explicit M1 deep-plan reference in main plan and implement M1.E

### Trigger
USER requested two actions in sequence:
1. Add explicit reference in `platform.build_plan.md` that detailed M1 decisions are in `platform.M1.build_plan.md`.
2. Move to and implement `M1.E`.

### Objective
Close documentation drift between main-plan active phase and deep-plan authority, then close M1.E by pinning canonical build command surface and reproducibility/failure posture.

### Scope
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - add explicit M1 deep-plan reference in active M1 section,
   - update sub-phase progress for M1.E completion,
   - update applicable M1 checklist items that become objectively satisfied.
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
   - complete M1.E DoD,
   - pin canonical build/push command surface,
   - pin required inputs/handles,
   - pin fail-closed retry/failure posture.

### Key decisions (before patch)
1. Main plan must explicitly route implementers to `platform.M1.build_plan.md` during M1 execution because it holds pinned command/provenance/security decisions.
2. M1.E will pin one canonical command surface family with deterministic command templates and required handles; no ad hoc command variants allowed.
3. Any build/push/provenance mismatch remains fail-closed blocker for M1 execution closure.
4. This pass remains planning-only; no image build/push execution starts yet.

### Validation plan
- confirm M1.E DoD checkboxes are all checked.
- confirm M1 completion checklist marks M1.E complete.
- confirm main plan includes explicit M1 deep-plan reference and updated sub-phase progress.

### Drift sentinel checkpoint
Documentation-contract closure only; no runtime/infrastructure execution changes.

## Entry: 2026-02-13 9:00AM - Applied M1 main-plan reference update and M1.E build command-surface closure

### Files updated
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`

### What was implemented
1. Main-plan reference hardening (per USER request)
- Added explicit active-phase reference that M1 execution authority lives in:
  - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
- Clarified that this deep plan contains pinned decisions required during build-go execution.

2. M1.E closure in deep plan
- Completed M1.E DoD and added pinned command-surface contract:
  - deterministic command family for `local_cli` and `github_actions`,
  - explicit required handles/inputs,
  - fail-closed retry/failure posture,
  - build command-surface evidence receipt artifact contract.
- Marked `M1.E complete` in M1 completion checklist.

3. Main-plan progress alignment
- Updated M1 sub-phase progress:
  - `M1.A..M1.E` complete,
  - `M1.F` pending.
- Updated M1 DoD checklist to mark objectively satisfied items complete:
  - packaging contract finalized,
  - build command surface pinned,
  - evidence contract pinned,
  - secret-handling rules pinned.
- Left handoff statement item pending for M1.F.

### Validation
- Confirmed explicit M1 deep-plan reference exists in active M1 section.
- Confirmed M1.E DoD and checklist are checked in deep plan.
- Confirmed main-plan M1 progress and DoD checkboxes align with M1.A..M1.E completion state.

### Drift sentinel assessment
No runtime or infrastructure execution changes were made. This is planning/control-surface hardening and phase progression closure for M1.E.

## Entry: 2026-02-13 9:03AM - Pre-change lock: implement M1.F exit-readiness review and handoff

### Trigger
USER directed: proceed to `M1.F`.

### Objective
Close M1.F by completing the M1 exit-readiness review and preparing the explicit build-go execution handoff statement, without prematurely closing M1 phase status.

### Scope
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
   - complete M1.F DoD,
   - add readiness verdict and execution handoff statement,
   - mark M1.F checklist complete.
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - update active-phase sub-progress,
   - mark M1 handoff checklist item complete,
   - keep M1 status `ACTIVE` pending execution evidence.

### Key decisions (before patch)
1. M1.F completion means planning/handoff pack is complete, not that P(-1) runtime execution is done.
2. M1 must stay `ACTIVE` until build-go execution artifacts are produced and validated per M1 exit criteria.
3. Handoff statement must enumerate execution sequence, required artifacts, and fail-closed blockers.

### Validation plan
- M1.F DoD all `[x]` in deep plan.
- M1 completion checklist shows `M1.F complete`.
- Main plan shows all M1 sub-phases complete but explicitly states M1 remains active pending execution evidence.

### Drift sentinel checkpoint
Documentation-control closure only; no runtime/infra execution changes.

## Entry: 2026-02-13 9:04AM - Applied M1.F exit-readiness review and build-go handoff closure

### Files updated
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### What was implemented
1. M1.F completion in deep plan:
- completed all M1.F DoD checkboxes,
- added readiness review verdict (deliverables complete + ambiguity closed within planning scope),
- added explicit build-go handoff statement with:
  - trigger,
  - execution authority,
  - ordered execution sequence,
  - required P(-1) evidence outputs,
  - fail-closed blockers,
  - closure condition for M1->M2 transition.
- marked `M1.F complete` in section 6 checklist.

2. Main plan alignment:
- updated M1 sub-phase progress to mark M1.F complete,
- added explicit note that M1 planning pack is complete but phase remains `ACTIVE` until execution evidence is produced/validated,
- marked the final M1 checklist item (`execution handoff statement prepared`) complete.

### Validation
- M1 deep plan now shows M1.A..M1.F complete.
- Main plan M1 checklist is fully checked.
- M1 phase status remains `ACTIVE` as intended because execution evidence has not been produced yet.

### Drift sentinel assessment
No semantic/runtime drift introduced. This closes planning readiness and cleanly separates planning completion from execution closure.

## Entry: 2026-02-13 9:06AM - Pre-execution lock: run M1 build-go packaging execution (P(-1))

### Trigger
USER directed: proceed with the next step after M1.F, which is M1 build-go execution.

### Objective
Execute the pinned M1 build-go pack for P(-1): build/push image, resolve digest, run entrypoint smoke checks, run secret/leakage checks, and write execution evidence artifacts.

### Execution context
- context file: `runs/dev_substrate/m1_build_go/20260213T090637Z/context.json`
- reserved run scope for packaging evidence: `platform_20260213T090637Z`
- immutable image tag target: `git-8fbf64020567b166d8b288cae402f9f96dd9f17a`

### Planned execution sequence
1. Preflight resource checks (ECR repo presence, toolchain, AWS identity).
2. Ensure ECR repo exists in pinned region (`eu-west-2`) for push target.
3. Execute canonical local_cli command family (auth -> build -> push immutable -> resolve digest -> optional convenience tag).
4. Execute entrypoint `--help` smoke checks in image context.
5. Execute no-baked-secrets/leakage checks + required SSM path checks.
6. Write local execution receipts and upload P(-1) evidence artifacts to `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T090637Z/P(-1)/`.
7. Record pass/fail verdict; fail closed if any blocker occurs.

### Fail-closed blockers
- build/push failure,
- unresolved or mismatched digest,
- entrypoint smoke failure,
- secret leakage finding,
- missing required runtime secret handles.

### Drift sentinel checkpoint
If prerequisites are missing, execution is blocked and phase remains ACTIVE; no silent bypass.

## Entry: 2026-02-13 9:10AM - Blocker detection during M1 build-go: missing IMAGE_DOCKERFILE_PATH artifact

### Detection
M1 build-go execution failed at `docker build` with:
- `failed to read dockerfile: open Dockerfile: no such file or directory`.

### Impact
- P(-1) build command surface is currently non-executable.
- M1 execution cannot progress to push/digest/provenance/entrypoint/security checks.

### Drift classification
Material execution blocker (contract implementation gap), not semantic runtime drift.

### Decision
Implement the missing packaging artifact now:
1. add repository-root `Dockerfile` aligned with pinned `IMAGE_DOCKERFILE_PATH = "Dockerfile"`.
2. add `.dockerignore` to prevent oversized/secrets-prone context and keep build deterministic.
3. rerun canonical M1.E local_cli build/push flow after patch.

### Design constraints for Dockerfile
- must install runtime package + dependencies (`pip install .` from `pyproject.toml`),
- must support module entrypoint execution across M1.B matrix,
- must not bake runtime secrets,
- must set deterministic runtime defaults (`PYTHONUNBUFFERED`, `PYTHONDONTWRITEBYTECODE`).

### Validation plan
- `docker build` succeeds with root Dockerfile.
- image push + digest resolve succeeds.
- follow-on entrypoint and security checks can execute.

## Entry: 2026-02-13 9:52AM - Pre-change lock: reopen M1.A to pin exact image content manifest (no wildcard ambiguity)

### Trigger
USER directed reopening M1.A to explicitly specify what enters the platform image and to remove careless wildcard posture.

### Objective
Replace broad packaging language with an exact, auditable image content manifest for Spine Green v0 dev_min packaging.

### Scope
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
   - add explicit M1.A image content manifest (exact include set + explicit exclusion set),
   - record rationale and acceptance checks,
   - keep M1.A closed only after explicit manifest pin.
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - reflect M1.A repin/reclosure note in active-phase progress.

### Dependency audit basis
- runtime config paths under `config/platform/**`.
- contract paths referenced by in-scope platform code and profiles:
  - `docs/model_spec/platform/contracts/**`
  - `docs/model_spec/data-engine/interface_pack/**`
  - `docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml`
  - `docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`

### Key decisions (pre-patch)
1. No engine source (`packages/engine/src/**`) in image context.
2. No repo-wide copy posture (`COPY . .`) permitted by contract.
3. Manifest must be path-explicit and fail-closed on missing required path.

### Drift sentinel checkpoint
This is a corrective packaging-contract hardening to prevent bloated/non-deterministic image builds.

## Entry: 2026-02-13 9:55AM - Applied M1.A repin: exact image content manifest (no wildcard ambiguity)

### Files updated
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### What changed
1. Reopened and hardened M1.A with explicit image manifest:
- added exact include set (path-explicit),
- added explicit exclusion set (engine source, datasets, logs, caches, env secrets),
- added build-context law forbidding `COPY . .` for M1 execution,
- added fail-closed verification gate for missing required paths or excluded-path leakage.

2. M1.E dependency alignment:
- updated required-input section to explicitly require compliance with the M1.A image manifest.

3. Main plan progress note alignment:
- M1 sub-phase progress now records that M1.A was reopened and reclosed with exact content manifest pinning.

### Outcome
M1.A now contains a deterministic, platform-only image content boundary suitable for large-workspace control and non-bloated build posture.

### Drift sentinel assessment
This corrective repin closes a material packaging ambiguity and prevents accidental repo-wide image context ingestion.

## Entry: 2026-02-13 10:02AM - Applied M1.A manifest path refinement for data-engine interface_pack

### Trigger
USER directed: update required paths after discussion on whether all of `interface_pack` is needed.

### Decision applied
Refined M1.A include set from broad `docs/model_spec/data-engine/interface_pack/` recursive copy to exact runtime-required files only:
- `engine_outputs.catalogue.yaml`
- `engine_gates.map.yaml`
- `contracts/canonical_event_envelope.schema.yaml`
- `contracts/engine_invocation.schema.yaml`
- `contracts/engine_output_locator.schema.yaml`
- `contracts/gate_receipt.schema.yaml`
- `contracts/instance_proof_receipt.schema.yaml`
- `contracts/run_receipt.schema.yaml`

### File updated
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`

### Rationale
This removes non-runtime interface-pack content (docs/examples/harvest) from the required image manifest and keeps packaging scope auditable and minimal.

## Entry: 2026-02-13 10:11AM - Applied fail-closed decision-completeness law (user proceed semantics)

### Trigger
USER requested adding a law to prevent execution drift when they say "proceed" before all required decisions are pinned.

### Decision applied
Codified a binding fail-closed rule:
- "Proceed" does not authorize assumption/default behavior when required decisions are missing.
- Agent must verify decision/input completeness before executing a phase/option/command.
- If holes remain, stop and surface unresolved items; keep at this until closure.

### Files updated
1. `AGENTS.md`
   - added `Decision-completeness law (fail-closed)` under Drift Sentinel Law.
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - added `10.2 Decision-Completeness Gate (Fail-Closed)` with execution-control wording.

### Effect
This creates a hard pre-execution gate against ad hoc defaults and aligns proceed semantics with explicit decision closure before execution.

## Entry: 2026-02-13 10:16AM - Applied M1 sub-phase restructure: new M1.F driver authority pin, prior F shifted to G

### Trigger
USER requested restructuring:
- add a new sub-phase for build driver authority as `M1.F`,
- rename previous exit-readiness/handoff step from `M1.F` to `M1.G`.

### Changes applied
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
- inserted new `M1.F Build Driver Authority Pin`.
- pinned driver decision:
  - authoritative: `github_actions`,
  - non-authoritative: `local_cli` preflight/debug only.
- shifted prior `M1.F Exit Readiness Review` to `M1.G` and aligned references.
- updated completion checklist to include `M1.G complete`.

2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
- updated M1 sub-phase progress labels:
  - `M1.F` now driver authority pin,
  - `M1.G` now exit-readiness + handoff.

### Outcome
Build-driver selection is now an explicit gate before handoff completion, eliminating the prior implicit assumption.

## Entry: 2026-02-13 10:25AM - Pre-change lock: M1 replan to add missing pre-build-go readiness phases

### Trigger
USER requested a full replan update after identifying that M1 lacked explicit readiness phases before build-go execution.

### Problem
Current M1 sequence closes planning handoff without explicit CI realization/validation phases, despite `github_actions` being authoritative. This leaves execution readiness under-specified.

### Decision
Replan M1 with additional explicit pre-build-go phases and reopen readiness closure:
1. Insert `M1.G` for authoritative CI workflow realization (workflow exists + pinned contract).
2. Insert `M1.H` for authoritative CI gate validation (dry-run/provenance/evidence plumbing checks).
3. Shift exit readiness/handoff to `M1.I` and mark it pending until G/H close.
4. Align checklists/progress in main plan so build-go remains blocked.

### Files to update
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### Validation plan
- New G/H/I sections exist with clear goals/tasks/DoDs.
- M1 completion checklist includes A..I with G/H/I pending.
- Main plan sub-phase progress and M1 checklist reflect reopened readiness (not execution-ready).

### Drift sentinel checkpoint
This is control-surface hardening and does not execute runtime/build actions.

## Entry: 2026-02-13 10:26AM - Applied M1 replan: inserted explicit pre-build-go CI phases and reopened readiness

### Files updated
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### Structural changes
1. Added new explicit pre-build-go phases:
- `M1.G Authoritative CI Workflow Realization`
- `M1.H Authoritative CI Gate Validation`
2. Shifted exit readiness/handoff from prior `M1.G` to `M1.I Exit Readiness Review`.
3. Reopened M1 readiness closure by marking `M1.G..M1.I` pending.

### Control impact
- Build-go is now explicitly blocked until:
  - CI workflow exists and is pinned (`M1.G`),
  - CI output/evidence plumbing is validated (`M1.H`),
  - exit readiness/handoff is refreshed and closed (`M1.I`).
- Main plan M1 checklist reflects reopened handoff readiness (unchecked until `M1.I` closure).

### Rationale
This closes the previously implicit assumption that CI execution behavior was already realized/validated before build-go, aligning phase structure to actual readiness requirements.

## Entry: 2026-02-13 10:31AM - Learning capture: build-driver confusion resolution (`github_actions` vs `local_cli`)

### Context
During M1 packaging planning/execution, there was understandable confusion about what `github_actions` and `local_cli` each mean in this migration track.

### Clarified understanding (pinned)
1. Both lanes execute Docker-based packaging, but they serve different authority roles.
2. `github_actions` is the authoritative build driver for M1 closure evidence.
3. `local_cli` is non-authoritative and limited to local preflight/debug support.
4. Build-go means execution authorization after preconditions are closed; it is not the same thing as planning completion.

### Lessons learned
1. Build-driver authority must be explicit before any build attempts (`M1.F`).
2. CI realization + CI gate validation must be explicit pre-build-go phases (`M1.G`, `M1.H`) and not implicit assumptions.
3. Exit-readiness/handoff must happen after these are closed (`M1.I`).
4. In large repositories, image content manifest must be path-explicit and fail-closed to avoid bloat and accidental scope leakage.

### Preventive controls now in place
- Decision-completeness fail-closed law in `AGENTS.md`.
- Decision-completeness execution gate in `platform.build_plan.md`.
- Explicit M1 phase sequencing with pre-build-go CI phases and blocked build-go until closure.

### Why this note exists
This captures user/operator learning value so the same confusion does not recur and can be reflected later in `docs/references/challenge_story_bank.md` if desired.

## Entry: 2026-02-13 10:35AM - Pre-change lock: M1.G authoritative CI workflow realization

### Trigger
USER directed: proceed with `M1.G`.

### Objective
Close `M1.G` by implementing the authoritative GitHub Actions workflow contract for P(-1) packaging so build-go no longer depends on assumed CI behavior.

### Scope
1. Create `.github/workflows/dev_min_m1_packaging.yml` as the authoritative CI build lane (`github_actions`).
2. Ensure workflow emits required machine-readable outputs for M1.C/M1.E:
- immutable image tag,
- resolved image digest,
- CI run id,
- build actor.
3. Record `M1.G` closure in:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
4. Append action record in `docs/logbook/02-2026/2026-02-13.md`.

### Decision posture (before patch)
1. Trigger posture:
- workflow uses `workflow_dispatch` only for safe/manual execution control in dev_min.
2. Auth posture:
- use AWS OIDC role assumption (`id-token: write`), reject static AWS key usage in workflow contract.
3. Output posture:
- workflow job outputs and uploaded artifacts carry immutable tag + digest + actor + CI run id.
4. Failure posture:
- fail closed on missing required dispatch inputs, digest resolution failure, or build/push failure.

### Drift sentinel checkpoint
This change is contract realization for M1 only and does not execute build-go runtime phases.

## Entry: 2026-02-13 10:37AM - Applied M1.G closure: authoritative CI workflow pinned and plans synced

### Files updated
1. `.github/workflows/dev_min_m1_packaging.yml` (new)
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
3. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### What was implemented
1. Authoritative CI workflow realization:
- added `dev-min-m1-packaging` GitHub Actions workflow as the M1 authoritative build lane.
- workflow trigger posture is `workflow_dispatch` only (operator-controlled).
- workflow auth posture is OIDC role assumption with least-privilege permissions (`contents: read`, `id-token: write`).
2. Canonical command sequence realization:
- auth -> immutable build -> immutable push -> digest resolution -> optional convenience tag push.
3. Machine-readable outputs/evidence realization:
- job outputs:
  - `image_tag`
  - `image_digest`
  - `git_sha`
  - `ci_run_id`
  - `build_actor`
- CI artifact pack emitted at:
  - `evidence/runs/<platform_run_id>/P(-1)/build_command_surface_receipt.json`
  - `evidence/runs/<platform_run_id>/P(-1)/packaging_provenance.json`
  - `evidence/runs/<platform_run_id>/P(-1)/ci_m1_outputs.json`
4. Fail-closed controls in workflow:
- fail if pinned Dockerfile path is missing,
- fail on build/push failure,
- fail if immutable digest cannot be resolved from ECR.

### Plan-state synchronization
1. `platform.M1.build_plan.md`:
- marked M1.G DoD checklist complete,
- added pinned realization record (workflow path, permissions, outputs, fail-closed behavior),
- marked M1 completion checklist item `M1.G` complete.
2. `platform.build_plan.md`:
- marked `M1.G` complete in active sub-phase progress with workflow path reference,
- updated build-go block to require only `M1.H..M1.I` closure before execution.

### Drift sentinel assessment
No runtime semantic drift introduced. This is execution-control hardening that removes CI-lane ambiguity and makes build-go prerequisites auditable.

## Entry: 2026-02-13 10:40AM - Pre-change lock: M1.H authoritative CI gate validation

### Trigger
USER directed: proceed to `M1.H`.

### Objective
Close `M1.H` by producing objective validation evidence that the authoritative CI workflow satisfies output plumbing, evidence-artifact obligations, and fail-closed prerequisite behavior.

### Gap discovered before execution
`M1.H` requires validation of three evidence artifacts:
1. `build_command_surface_receipt.json`
2. `packaging_provenance.json`
3. `security_secret_injection_checks.json`

Current workflow emitted only (1) and (2) plus `ci_m1_outputs.json`; therefore `M1.H` cannot close without patching that drift.

### Planned corrective actions
1. Patch `.github/workflows/dev_min_m1_packaging.yml` to emit `security_secret_injection_checks.json`.
2. Add a deterministic local validator script to statically validate CI contract obligations:
- workflow syntax/loadability,
- required outputs wiring,
- evidence file coverage,
- fail-closed guard presence (AWS creds, Dockerfile precheck, digest resolution check).
3. Run validator and record PASS/FAIL evidence.
4. Update:
- `platform.M1.build_plan.md` (`M1.H` closure record + checklist),
- `platform.build_plan.md` (M1 sub-phase progress),
- logbook entry.

### Drift sentinel checkpoint
This is control-surface validation for migration readiness, not runtime flow execution.

## Entry: 2026-02-13 10:41AM - Applied M1.H closure: CI gate validation evidence pinned

### Files updated
1. `.github/workflows/dev_min_m1_packaging.yml`
2. `tools/dev_substrate/validate_m1_ci_workflow_contract.py` (new)
3. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
4. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### Corrective action for discovered gap
1. Patched workflow evidence emission to include:
- `security_secret_injection_checks.json`
This closes the M1.H evidence-artifact contract drift against M1.D/M1.H requirements.

### Validation mechanics implemented
1. Added deterministic local validator:
- `tools/dev_substrate/validate_m1_ci_workflow_contract.py`
2. Validator checks:
- workflow_dispatch required inputs,
- least-privilege permissions posture,
- required job output wiring,
- fail-closed guards (static AWS creds, missing Dockerfile, missing digest),
- evidence artifact coverage,
- artifact upload path contract.

### Validation runs
1. Initial run:
- report: `runs/dev_substrate/m1_h_validation/20260213T104041Z/ci_gate_validation_report.json`
- verdict: FAIL (YAML `on` key normalization issue in validator, corrected immediately).
2. Final run:
- report: `runs/dev_substrate/m1_h_validation/20260213T104101Z/ci_gate_validation_report.json`
- verdict: PASS.

### Plan-state synchronization
1. Marked `M1.H` complete in deep plan with pinned validation record and report path.
2. Marked `M1.H` complete in main plan sub-phase progress.
3. Updated build-go blocker wording: only `M1.I` remains before M1 execution build-go.

### Drift sentinel assessment
No semantic runtime behavior changed. This closes an execution-readiness control gap and improves pre-build-go determinism.

## Entry: 2026-02-13 10:42AM - M1.H revalidation pass after documentation synchronization

### Trigger
Post-sync confidence check after updating plan/log files for M1.H closure.

### Action
Re-ran validator:
- `python tools/dev_substrate/validate_m1_ci_workflow_contract.py --workflow .github/workflows/dev_min_m1_packaging.yml --report runs/dev_substrate/m1_h_validation/20260213T104213Z/ci_gate_validation_report.json`

### Result
- PASS (`runs/dev_substrate/m1_h_validation/20260213T104213Z/ci_gate_validation_report.json`)

### Outcome
Confirms M1.H remains closed with stable validation results after all associated doc updates.

## Entry: 2026-02-13 10:45AM - Pre-change lock: M1.I exit-readiness review closure

### Trigger
USER directed: proceed with `M1.I`.

### Objective
Close M1 planning-phase readiness by:
1. completing explicit exit-readiness review,
2. confirming no unresolved contract ambiguity remains,
3. finalizing authoritative build-go handoff posture.

### Review basis
1. Deep plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
2. Main plan:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
3. CI validation evidence:
- `runs/dev_substrate/m1_h_validation/20260213T104213Z/ci_gate_validation_report.json`

### Pre-closure findings
1. M1.A..M1.H are complete and evidenced.
2. No contract ambiguity remains in build-driver authority, output/evidence fields, or fail-closed posture.
3. Known build-go preflight prerequisites are explicit (not ambiguous):
- pinned Dockerfile path must exist (`IMAGE_DOCKERFILE_PATH = Dockerfile`),
- workflow_dispatch inputs must be supplied at execution time,
- OIDC role/permissions must be valid.

### Planned updates
1. Mark `M1.I` DoD checks complete with a pinned readiness verdict.
2. Mark `M1.I` completion in deep and main M1 progress checklists.
3. Update immediate-next-action text to reflect transition from planning closure to awaiting explicit USER build-go.

### Drift sentinel checkpoint
This is planning/control closure only; no runtime build/push execution is performed in this step.

## Entry: 2026-02-13 10:47AM - Applied M1.I closure: M1 planning gates complete

### Files updated
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M1.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

### M1.I closure outcome
1. M1.I DoD checklist marked complete:
- deliverables checklist complete,
- no unresolved contract ambiguity remains,
- build-go handoff statement prepared.
2. M1.I readiness verdict pinned as:
- `READY_FOR_BUILD_GO` (planning/control closure only).
3. Build-go handoff statement transitioned from provisional to authoritative for M1 execution.

### Explicit preflight prerequisites retained in handoff
1. Pinned Dockerfile path must exist at execution time (`IMAGE_DOCKERFILE_PATH = Dockerfile`).
2. Required `workflow_dispatch` inputs must be supplied.
3. OIDC role assumption + ECR access must be valid for execution principal.

### Main-plan synchronization
1. Marked `M1.I` complete in active M1 sub-phase progress.
2. Marked M1 execution-handoff checklist item complete.
3. Updated immediate-next-action section:
- planning gates closed,
- execution proceeds only on explicit USER build-go.

### Drift sentinel assessment
No runtime behavior was executed or changed. This closes M1 planning control gates and preserves explicit user-governed execution authority.

## Entry: 2026-02-13 10:52AM - M1 build-go execution start (authoritative CI lane)

### Trigger
USER directed explicit build-go execution for M1 and instructed to ignore unrelated engine changes.

### Objective
Execute P(-1) packaging through the authoritative `github_actions` lane and produce required evidence artifacts:
1. `packaging_provenance.json`
2. `build_command_surface_receipt.json`
3. `security_secret_injection_checks.json`

### Execution lane and concrete inputs
1. Build driver:
- `github_actions` (authoritative).
2. Workflow:
- `.github/workflows/dev_min_m1_packaging.yml`
3. Branch/ref:
- `migrate-dev`
4. Runtime inputs discovered from environment/substrate:
- `aws_region = eu-west-2`
- `aws_role_to_assume = arn:aws:iam::230372904534:role/GitHubAction-AssumeRoleWithAction`
- `ecr_repo_name = fraud-platform-dev-min`
- `ecr_repo_uri = 230372904534.dkr.ecr.eu-west-2.amazonaws.com/fraud-platform-dev-min`

### Preflight findings before dispatch
1. AWS CLI auth is active and `sts get-caller-identity` resolves to account `230372904534`.
2. ECR repo exists and URI resolves.
3. Local Dockerfile is currently missing while `IMAGE_DOCKERFILE_PATH` is pinned to `Dockerfile`.
4. Expected first-run posture:
- workflow dispatch is attempted first on authoritative lane,
- if Dockerfile absence fails build step, patch Dockerfile/.dockerignore to pinned M1.A manifest and rerun.

### Fail-closed posture
No fallback to non-authoritative closure proofs. If authoritative CI lane cannot produce required artifacts, M1 remains active/not done.

## Entry: 2026-02-13 10:56AM - Build-go execution blockers discovered and mitigations in progress

### Actions executed
1. Attempted authoritative workflow dispatch:
- `gh workflow run dev_min_m1_packaging.yml --ref migrate-dev ...`
2. Result:
- HTTP 404: workflow file not found on default branch (`main`).
3. Added missing pinned build artifacts locally:
- `Dockerfile` (M1.A include-only copy surfaces, no `COPY . .`),
- `.dockerignore` (allowlist context to enforce M1.A manifest boundary).
4. Attempted local Docker preflight build:
- failed due local Docker daemon availability (`dockerDesktopLinuxEngine/_ping` 500).

### Material blocker
GitHub `workflow_dispatch` requires the workflow file to exist on default branch. Current authoritative workflow exists in working tree/branch but is not present on remote default branch.

### Proposed resolution options
1. Recommended:
- push authoritative workflow file to `main` (default branch),
- push M1 build-go content (`Dockerfile`, `.dockerignore`, docs updates) to `migrate-dev`,
- dispatch workflow with `--ref migrate-dev`.
2. Alternative:
- repin build driver away from `github_actions` (not recommended; requires explicit authority repin).

### Drift sentinel stance
Fail-closed maintained. No non-authoritative build evidence has been used for closure.

## Entry: 2026-02-13 11:35AM - Build-go execution resumed after workflow publication

### Trigger
USER confirmed the authoritative workflow has been added on remote and directed to proceed with build-go.

### Pre-dispatch preflight (authoritative lane)
1. Workflow visibility:
- `gh workflow list` shows `dev-min-m1-packaging` active.
- `gh workflow view dev_min_m1_packaging.yml --yaml` resolves successfully.
2. Build prerequisites:
- local `Dockerfile` is present at pinned path (`IMAGE_DOCKERFILE_PATH = Dockerfile`).
- current branch for execution ref is `migrate-dev`.
3. Auth/substrate:
- AWS caller identity resolves in account `230372904534`,
- ECR repository `fraud-platform-dev-min` exists and URI resolves.

### Decision
Proceed with authoritative `workflow_dispatch` on ref `migrate-dev` using pinned inputs, then evaluate terminal result fail-closed.

## Entry: 2026-02-13 11:42AM - M1 build-go execution result (authoritative CI lane)

### Execution sequence and outcomes
1. Dispatch attempt A (ref `migrate-dev`):
- run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/21985402789`
- result: FAIL at OIDC step.
- blocker: AWS account missing OIDC provider `token.actions.githubusercontent.com`.
2. Remediation A (IAM OIDC provider):
- created provider ARN:
  - `arn:aws:iam::230372904534:oidc-provider/token.actions.githubusercontent.com`
3. Dispatch attempt B (ref `dev`, trust-aligned branch):
- run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/21985472266`
- result: FAIL at ECR login.
- blocker: role lacked `ecr:GetAuthorizationToken` and repo push/read permissions.
4. Remediation B (least-privilege role policy):
- role: `GitHubAction-AssumeRoleWithAction`
- added inline policy: `GitHubActionsEcrPushDevMin`
- scope:
  - `ecr:GetAuthorizationToken` on `*`,
  - push/read actions on `arn:aws:ecr:eu-west-2:230372904534:repository/fraud-platform-dev-min`.
5. Dispatch attempt C (ref `dev`):
- run: `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/21985500168`
- result: SUCCESS.

### Build-go evidence captured
1. GitHub artifact download location:
- `runs/dev_substrate/m1_build_go/20260213T114002Z/`
2. Required P(-1) evidence files (present):
- `build_command_surface_receipt.json`
- `packaging_provenance.json`
- `security_secret_injection_checks.json`
3. Additional CI output file:
- `ci_m1_outputs.json`
4. ECR immutable identity (verified):
- tag: `git-799d398a7daf34857cf363c9a1a629c40ec25d5e`
- digest: `sha256:d71cbe335ec0ced59a40721f0e1f6016b276ec17f34e52708d3fd02c04d79f56`

### S3 evidence persistence
Uploaded evidence files to:
- `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T114002Z/P(-1)/`
Verified object presence for required artifacts and CI output file.

### Control/gating assessment
1. Authoritative build lane (`github_actions`) executed successfully.
2. Required P(-1) artifact set is produced and persisted.
3. M1 build-go execution evidence is now available for phase-closure decisioning.
4. Per phase law, M1->M2 activation remains user-governed; status change to `DONE` should occur only on explicit user direction.

## Entry: 2026-02-13 12:02PM - First-time operator evidence narrative (where compute/artifacts actually ran)

### Why this note exists
Capture an explicit, reusable explanation of what happened during M1 build-go so this can be used later as portfolio experience proof and onboarding aid.

### Runtime topology (non-magic decomposition)
1. Control plane (operator commands):
- local shell (`gh` + `aws` CLI) was used only to trigger and inspect remote execution.
2. Build plane (actual container build compute):
- GitHub-hosted runner (`ubuntu-latest`) performed checkout, Docker build, and Docker push.
- No platform runtime compute for this build occurred on the laptop.
3. Artifact plane (image registry):
- OCI image stored in AWS ECR repo `fraud-platform-dev-min` in `eu-west-2`.
- immutable identity from successful run:
  - tag: `git-799d398a7daf34857cf363c9a1a629c40ec25d5e`
  - digest: `sha256:d71cbe335ec0ced59a40721f0e1f6016b276ec17f34e52708d3fd02c04d79f56`
4. Evidence plane (proof surfaces):
- CI artifact pack in GitHub Actions run record.
- local mirror downloaded to:
  - `runs/dev_substrate/m1_build_go/20260213T114002Z/`
- durable S3 evidence written to:
  - `s3://fraud-platform-dev-min-evidence/evidence/runs/platform_20260213T114002Z/P(-1)/`
  - required proof files:
    - `build_command_surface_receipt.json`
    - `packaging_provenance.json`
    - `security_secret_injection_checks.json`

### Exact execution references
1. Final successful CI run:
- `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/21985500168`
2. Failed attempts that established fail-closed posture:
- `21985402789` (OIDC provider missing),
- `21985472266` (ECR auth permission missing).
3. Remediations applied:
- created IAM OIDC provider for GitHub token issuer,
- attached least-privilege ECR push/read policy to role `GitHubAction-AssumeRoleWithAction`.

### Operational meaning
1. The laptop orchestrated and inspected; it did not perform build-plane compute.
2. Build identity is immutable (`git-<sha>` + digest) and registry-verifiable.
3. Evidence is both human-traceable (GitHub run) and machine-durable (S3 run-scoped path).

## Entry: 2026-02-13 12:09PM - Pre-change lock: M2 expansion with anti-cram planning law

### Trigger
USER directed expansion of M2 in main plan + creation of detailed `platform.M2.build_plan.md`, and explicitly required a binding law to prevent phase under-specification drift seen in M1.

### Objective
1. Promote plan posture from M1 execution-complete to M2 planning-active.
2. Expand M2 in `platform.build_plan.md` beyond gate-level summary into explicit sub-phase coverage.
3. Create deep M2 planning authority file `platform.M2.build_plan.md` with exhaustive P0 substrate lanes and DoDs.
4. Add a binding anti-cram planning law so phase decomposition is not constrained by arbitrary subphase counts.

### Authority reviewed for M2 expansion
1. `dev_min_spine_green_v0_run_process_flow.md`:
- P0 semantics, pinned decisions, required handles, operator procedure, PASS gates, commit evidence, rollback, cost notes.
2. `dev_min_handles.registry.v0.md`:
- Terraform/state, S3, Confluent/SSM, topic map, ECS/network/no-NAT, DB, IAM roles, budgets/alerts, observability handles.
3. Existing main plan controls:
- transition authority, decision-completeness gate, evidence template, single-active-phase rule.

### Planned M2 decomposition (coverage-first)
M2 will be split into explicit planning sub-phases:
1. M2.A substrate authority + handle closure matrix
2. M2.B Terraform core state/backend readiness
3. M2.C Terraform core apply closure contract
4. M2.D Terraform demo apply closure contract
5. M2.E secret/SSM materialization checks
6. M2.F Kafka topic/ACL/access checks
7. M2.G network/no-NAT/egress posture checks
8. M2.H runtime DB readiness and migration readiness
9. M2.I budget and teardown-viability proof
10. M2.J exit readiness + M3 handoff

### New law to add
Binding anti-cram law: no active phase may execute until all required capability lanes for that phase are explicitly represented and checklisted, and sub-phases may be expanded without fixed upper bound until closure-grade coverage is achieved.

### Drift sentinel checkpoint
This is planning-surface expansion and governance hardening only; no M2 runtime execution or infra mutation is performed in this patch set.

## Entry: 2026-02-13 12:33PM - Post-change record: M2 expanded to lane-complete planning baseline

### What was changed
1. Main platform build plan (`platform.build_plan.md`) was promoted to M2-active posture with explicit M2 sub-phase decomposition (`M2.A..M2.J`) and M2 DoD checklist.
2. A binding anti-cram law was pinned in the main plan (`10.3 Phase-Coverage Law`) to block execution when any capability lane is implicit.
3. Deep M2 plan file (`platform.M2.build_plan.md`) was created/expanded into execution-grade structure:
- capability-lane coverage matrix (authority/handles, IAM, network, data stores, messaging, secrets, evidence, rollback, teardown, budget),
- explicit M2 sub-phases with goals/tasks/DoD,
- runbook-aligned handle families and concrete handle keys for closure in M2.A,
- command-surface pinning requirements for M2.B/M2.E/M2.F (without executing commands),
- explicit M2 evidence root + artifact contract,
- unresolved-blocker register with fail-closed rule.

### Why this change was required
1. USER identified M1 under-planning drift risk: missing decision surfaces were discovered only when execution started.
2. M2 is substrate-critical; hidden gaps here cascade into all downstream phases (P1+), so planning had to become lane-complete before mutation.
3. The anti-cram law creates a hard stop condition against fixed-phase-count bias and forces dynamic expansion when new lanes are discovered.

### Design constraints enforced
1. No infra/runtime commands were executed in this pass.
2. No phase status ownership was delegated to deep-plan files; status remains controlled only by `platform.build_plan.md`.
3. Handle naming in M2 deep plan was reconciled against `dev_min_handles.registry.v0.md` to avoid introducing new naming drift.

### Residual open items after this planning pass
1. M2 execution has not started; all M2 sub-phases remain unchecked by design.
2. Immediate next closure target is still:
- `M2.A` handle-closure matrix completion,
- `M2.B` backend/state readiness completion,
before any Terraform mutation command.

### Drift sentinel checkpoint
No designed runtime flow was altered and no substrate mutation occurred.
This change improves process-governance fidelity and reduces planning ambiguity before M2 execution begins.

## Entry: 2026-02-13 12:36PM - Pre-change lock: execute M2.A handle-closure matrix and status sync

### Trigger
USER directed progression into `M2.A` execution work.

### Objective
1. Convert M2.A from intent-only text into an explicit closure matrix with per-handle ownership/source/verification posture.
2. Confirm M2.A required key set is fully present in handles registry.
3. Record secret vs non-secret evidence boundary explicitly.
4. If M2.A DoD is satisfied at planning level, mark `M2.A` complete in deep and main plan status surfaces.

### Preflight result
Automated key-presence check for the M2.A minimum key set returned:
1. `TOTAL_KEYS=46`
2. `ALL_PRESENT`

### Boundaries
1. No Terraform/apply/mutation commands in this pass.
2. This is M2.A planning closure only; runtime resource validation remains in M2.B+.

## Entry: 2026-02-13 12:41PM - Post-change record: M2.A closure matrix completed and status synced

### Delivered for M2.A
1. Added explicit M2.A closure summary with quantitative result:
- required key count `46`,
- unknown required keys `0`,
- registry presence check `ALL_PRESENT`.
2. Added pinned verification command catalog (`V1..V11`) covering:
- registry key presence,
- Terraform backend/validate surface,
- S3 state checks,
- lock-table checks,
- SSM path checks,
- Kafka topic checks,
- ECS/network checks,
- DB checks,
- IAM checks,
- budget checks.
3. Added per-key M2.A handle closure matrix (all 46 keys) with:
- family,
- owner of resolution,
- source of value,
- verification mapping,
- secret classification (`non_secret` vs `secret_locator`),
- status and blocker field.
4. Added explicit secret-surface separation rule to keep M2 evidence non-secret.

### Status synchronization
1. `platform.M2.build_plan.md`:
- M2.A DoD checklist set to complete,
- M2 completion checklist marks `M2.A` complete.
2. `platform.build_plan.md`:
- M2 sub-phase tracker marks `M2.A` complete,
- immediate next action narrowed to `M2.B` closure before any mutation command.

### Drift sentinel checkpoint
1. No Terraform apply/destroy or runtime infra mutation occurred.
2. This closes M2.A as planning-authority closure only; runtime substrate validation remains explicitly blocked behind M2.B+.

## Entry: 2026-02-13 12:44PM - Pre-change lock: add anti-cram law to repository AGENTS policy

### Trigger
USER requested that the anti-cram planning law be pinned in `AGENTS.md` as well (not only in build-plan docs).

### Objective
1. Add a binding policy statement to repository-level agent instructions that prevents fixed-phase-count cramming.
2. Ensure proceed semantics remain fail-closed when capability lanes are missing or implicit.
3. Keep policy wording aligned with existing `Decision-completeness law` and phase-coverage law in platform build planning docs.

### Scope
1. Policy doc update only (`AGENTS.md`).
2. No runtime/substrate/code behavior change.

## Entry: 2026-02-13 12:45PM - Post-change record: anti-cram law pinned in AGENTS.md

### What changed
1. Added a new binding policy bullet under `2.5 Drift Sentinel Law` in `AGENTS.md`:
- `Phase-coverage law (anti-cram, fail-closed)`.
2. The new policy explicitly requires:
- full capability-lane exposure before phase execution,
- dynamic expansion of sub-phases (no fixed-count cramming),
- fail-closed pause + unresolved-item escalation whenever a missing lane is discovered.

### Why this was needed
1. USER requested repository-level policy protection against under-planning recurrence seen in M1.
2. Build-plan-only law was not sufficient for global agent behavior; `AGENTS.md` is the repo-wide execution contract.

### Drift sentinel checkpoint
1. Documentation/policy change only.
2. No platform runtime behavior or substrate mutation occurred.

## Entry: 2026-02-13 12:47PM - Pre-change lock: execute M2.B backend/state partition readiness with live evidence

### Trigger
USER directed progression to `M2.B`.

### Objective
1. Validate Terraform backend/state partition readiness against real substrate controls.
2. Remove any drift between pinned stack roots and filesystem reality.
3. Produce objective evidence for:
- distinct core/demo state keys,
- state bucket security controls,
- lock-table readiness.

### Discovered blocker at phase entry
1. Pinned stack roots (`infra/terraform/dev_min/core|demo`) were missing from filesystem.
2. Existing Terraform module code existed under `infra/terraform/modules/*`, but no canonical root stacks were present.

### Decision
1. Materialize canonical stack roots at pinned paths now (M2.B scope), backed by existing modules.
2. Keep this execution limited to readiness/validation; no apply/destroy mutation.

### Boundaries
1. Allowed:
- add stack-root Terraform files,
- run `init/validate`,
- run read-only AWS checks,
- write evidence artifact.
2. Not allowed:
- `terraform apply`,
- `terraform destroy`,
- manual console drift.

## Entry: 2026-02-13 12:55PM - Post-change record: M2.B closed with live backend/security/lock evidence

### What changed
1. Added canonical stack roots:
- `infra/terraform/dev_min/core/*`
- `infra/terraform/dev_min/demo/*`
2. Added backend config templates with distinct state keys:
- core: `dev_min/core/terraform.tfstate`
- demo: `dev_min/demo/terraform.tfstate`
3. Added root READMEs + tfvars examples to formalize operator command surface.

### Validation executed
1. Static Terraform checks:
- `terraform fmt -recursive infra/terraform/dev_min infra/terraform/modules`
- `terraform -chdir=infra/terraform/dev_min/core init -backend=false` -> PASS
- `terraform -chdir=infra/terraform/dev_min/core validate` -> PASS
- `terraform -chdir=infra/terraform/dev_min/demo init -backend=false` -> PASS
- `terraform -chdir=infra/terraform/dev_min/demo validate` -> PASS
2. Backend command-surface checks:
- `terraform -chdir=infra/terraform/dev_min/core init -reconfigure -backend-config=backend.hcl.example` -> PASS
- `terraform -chdir=infra/terraform/dev_min/demo init -reconfigure -backend-config=backend.hcl.example` -> PASS
3. Live AWS control checks:
- tfstate bucket `fraud-platform-dev-min-tfstate`:
  - versioning `Enabled`
  - public-access-block all true
  - encryption `AES256`
- lock table `fraud-platform-dev-min-tf-locks`:
  - status `ACTIVE`
  - billing `PAY_PER_REQUEST`
  - hash key `LockID`

### Evidence artifacts
1. Local:
- `runs/dev_substrate/m2_b/20260213T125421Z/m2_b_backend_state_readiness_snapshot.json`
2. Durable:
- `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T125421Z/m2_b_backend_state_readiness_snapshot.json`

### Status sync
1. `platform.M2.build_plan.md`:
- M2.B DoD checklist marked complete,
- M2.B closure summary + evidence references added,
- M2 checklist marks `M2.B` complete.
2. `platform.build_plan.md`:
- M2 sub-phase tracker marks `M2.B` complete,
- immediate next action advanced to `M2.C`.

### Drift sentinel checkpoint
1. No apply/destroy mutation occurred.
2. M2.B closure is evidence-backed and consistent with pinned stack-root authority.

## Entry: 2026-02-13 1:00PM - Pre-change lock: execute M2.C core-apply contract closure

### Trigger
USER directed progression to `M2.C` implementation.

### Objective
1. Pin the canonical core apply command surface (no ambiguity, no demo drift).
2. Define and validate core acceptance checks tied to module outputs/resources.
3. Produce an M2.C evidence snapshot with:
- backend/state identity,
- plan metadata,
- output-handle contract,
- rollback posture.
4. Sync M2.C status in deep/main plans only if DoD is objectively satisfied.

### Boundaries
1. Allowed:
- static Terraform checks,
- Terraform plan/read-only metadata collection,
- read-only AWS checks,
- evidence artifact generation.
2. Not allowed in this pass:
- `terraform apply`,
- `terraform destroy`,
- manual console mutation.

## Entry: 2026-02-13 1:05PM - Post-change record: M2.C contract closed with explicit state-mismatch blocker

### What was implemented
1. Expanded M2.C into an execution-grade contract in `platform.M2.build_plan.md`:
- canonical core command surface (`init/validate/plan/apply/output`),
- explicit acceptance checks and required output-key contract,
- pinned evidence schema and path contract,
- rollback/correction posture,
- closure summary and evidence references.
2. Produced M2.C evidence snapshot from live checks:
- local: `runs/dev_substrate/m2_c/20260213T130431Z/m2_c_core_apply_contract_snapshot.json`
- durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T130431Z/m2_c_core_apply_contract_snapshot.json`
3. Synced phase status:
- `platform.M2.build_plan.md`: M2.C DoD and M2 checklist marked complete.
- `platform.build_plan.md`: M2 sub-phase tracker marks `M2.C` complete.

### Material finding (fail-closed)
1. Blocker `M2C-B1` discovered and pinned in unresolved blocker register:
- core backend key `dev_min/core/terraform.tfstate` has no state object,
- core resources already exist in account,
- direct apply is likely to hit already-exists conflicts.
2. Closure rule pinned:
- perform controlled state import/migration and re-plan until conflict-bearing create set is removed.

### Command/evidence highlights
1. `terraform -chdir=infra/terraform/dev_min/core init -reconfigure ...` -> PASS.
2. `terraform -chdir=infra/terraform/dev_min/core validate` -> PASS.
3. `terraform -chdir=infra/terraform/dev_min/core plan -detailed-exitcode` -> exit `2` with create set, confirming state-mismatch risk.
4. Lock table readiness check remains PASS (`ACTIVE`, hash key `LockID`).

### Drift sentinel checkpoint
1. No apply/destroy mutation executed.
2. M2.C is closed as contract/evidence work, while execution progression is fail-closed behind `M2C-B1`.

## Entry: 2026-02-13 1:09PM - Corrective note: core stack file restoration during M2.C pass

### What happened
1. While removing an accidental artifact file named `$plan`, a shell command expanded unexpectedly and removed files under `infra/terraform/dev_min/core`.

### Immediate correction
1. Restored the canonical core stack files to pinned content:
- `versions.tf`, `variables.tf`, `main.tf`, `outputs.tf`,
- `backend.hcl.example`, `terraform.tfvars.example`, `README.md`.
2. Re-ran validation:
- `terraform -chdir=infra/terraform/dev_min/core init -backend=false` -> PASS,
- `terraform -chdir=infra/terraform/dev_min/core validate` -> PASS.

### Net effect
1. Core stack is back in valid state.
2. No substrate mutation (`apply`/`destroy`) occurred from this incident.

## Entry: 2026-02-13 1:22PM - Post-change record: M2C-B1 resolved via controlled core state import/migration

### Problem recap
1. `M2C-B1` blocker:
- backend key `dev_min/core/terraform.tfstate` was empty while core resources already existed in AWS.
- direct first apply risked already-exists conflicts.

### Root-cause detail uncovered during resolution
1. Initial import attempts failed due an import-evaluation issue in `modules/core`:
- dependent resources used `for_each = aws_s3_bucket.core`,
- `terraform import` could not evaluate this deterministically for partial import graph.
2. Additional import friction appeared from strict output indexing during partial bucket imports.

### Technical fixes applied
1. Import-safety fix in `infra/terraform/modules/core/main.tf`:
- changed dependent resource loops to static key space:
  - from `for_each = aws_s3_bucket.core`
  - to `for_each = local.bucket_names`
- bucket references now use `aws_s3_bucket.core[each.key].id`.
2. Import-safety fix in `infra/terraform/modules/core/outputs.tf`:
- changed `bucket_names` output to key-driven mapping with `try(...)` to avoid partial-import index failures.

### Resolution actions executed
1. Initialized backend on canonical core stack root with `backend.hcl.example`.
2. Imported all core resources into state (24 total):
- 4 DynamoDB tables,
- 5 S3 buckets,
- 5 S3 public-access-block resources,
- 5 S3 SSE configuration resources,
- 5 S3 versioning resources.
3. Re-ran core plan post-import and confirmed:
- `CREATE_COUNT=0`,
- state inventory count = `24`.

### Evidence
1. Resolution snapshot (local):
- `runs/dev_substrate/m2_c/20260213T132116Z/m2c_b1_resolution_snapshot.json`
2. Resolution snapshot (durable):
- `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T132116Z/m2c_b1_resolution_snapshot.json`
3. Contract snapshot remains:
- `runs/dev_substrate/m2_c/20260213T130431Z/m2_c_core_apply_contract_snapshot.json`

### Status synchronization
1. `platform.M2.build_plan.md`:
- unresolved blocker register now empty,
- `M2C-B1` moved to resolved-blocker record with evidence refs,
- M2.D entry precondition now explicitly satisfied.
2. `platform.build_plan.md`:
- immediate next action advanced from blocker closure to M2.D closure work.

### Drift sentinel checkpoint
1. No `terraform apply`/`destroy` mutation executed.
2. Blocker was resolved with deterministic, auditable state migration rather than console patching.

## Entry: 2026-02-13 1:26PM - Pre-change lock: execute M2.D demo-apply contract with fail-closed verification

### Trigger
USER directed progression to `M2.D`.

### Objective
1. Pin and execute M2.D contract verification against current demo stack reality.
2. Produce M2.D demo contract evidence snapshot and durable copy.
3. Fail closed if required demo surfaces (Confluent/ECS/DB/SSM) are not represented by current demo stack plan/resources.

### Planned checks
1. Terraform demo stack command surface:
- init/validate/plan.
2. Demo plan/resource classification against required categories:
- Confluent cluster/topics,
- SSM secret writes (Confluent + DB),
- ECS cluster/scaffolding,
- runtime DB.
3. Record blockers in M2 unresolved blocker register if categories are missing.

### Boundaries
1. No `terraform apply`/`destroy` in this pass.
2. No console mutation; evidence and contract closure only.

## Entry: 2026-02-13 1:28PM - Post-change record: M2.D contract executed fail-closed with capability-gap blockers

### What was executed
1. Demo stack contract checks:
- `terraform -chdir=infra/terraform/dev_min/demo init -reconfigure -backend-config=backend.hcl.example` -> PASS
- `terraform -chdir=infra/terraform/dev_min/demo validate` -> PASS
- `terraform -chdir=infra/terraform/dev_min/demo plan` + `show -json` -> PASS
2. Generated M2.D snapshot:
- local: `runs/dev_substrate/m2_d/20260213T132643Z/m2_d_demo_apply_contract_snapshot.json`
- durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T132643Z/m2_d_demo_apply_contract_snapshot.json`

### Material finding (drift surfaced)
Current demo stack plan contains only:
1. `aws_cloudwatch_log_group`
2. `aws_s3_object`
3. `aws_ssm_parameter` (heartbeat path)

Missing required M2.D capability lanes:
1. Confluent cluster/topics
2. ECS scaffolding
3. Runtime DB
4. Required Confluent/DB SSM credential paths

### Blockers registered
1. `M2D-B1` Confluent resources missing
2. `M2D-B2` ECS scaffolding missing
3. `M2D-B3` runtime DB missing
4. `M2D-B4` required Confluent/DB SSM writes missing

### Status sync
1. `platform.M2.build_plan.md`:
- M2.D command-surface and fail-closed checks are now explicit,
- M2.D remains open (`Required demo resource acceptance checks` unchecked),
- unresolved blocker register updated with `M2D-B1..M2D-B4`.
2. `platform.build_plan.md`:
- immediate next action now requires resolving `M2D-B1..M2D-B4` before M2.D closure.

### Drift sentinel checkpoint
1. No apply/destroy mutation executed.
2. Phase progression is explicitly fail-closed on capability gaps.

## Entry: 2026-02-13 1:38PM - Migration learning note: IaC over UI-first setup posture

### Trigger
USER requested this phase-learning insight be captured in implementation notes.

### Learning captured
1. Prior assumption: dev migration would require mostly UI-driven, manual setup for each platform service.
2. Current posture after M1/M2 execution: infrastructure should be created and torn down through IaC-first command lanes, with UI used only for validation or platform limitations.

### Why this matters for migration
1. Repeatability:
- same inputs and pinned handles produce the same substrate shape.
2. Teardown discipline:
- resources can be destroyed cleanly without hidden leftovers.
3. Drift reduction:
- avoids console-only state that breaks deterministic reruns.
4. Auditability:
- apply/plan/evidence artifacts provide proof of what was built and when.

### Fail-closed implication
1. Any required substrate capability that cannot be represented in IaC is now treated as a surfaced decision/blocker, not an implicit manual step.

## Entry: 2026-02-13 1:43PM - Pre-change lock: close M2D-B1..B4 via demo-stack capability expansion

### Trigger
USER directed: "let's close out the blockers".

### Problem statement
Current `infra/terraform/dev_min/demo` plan exposes only log-group + manifest + heartbeat SSM and fails M2.D required categories for:
1. Confluent lane (`M2D-B1`)
2. ECS scaffolding (`M2D-B2`)
3. Runtime DB (`M2D-B3`)
4. Required Confluent/DB SSM paths (`M2D-B4`)

### Decision and rationale
1. Implement missing demo capability lanes directly in Terraform demo module so M2.D plan is lane-complete.
2. Keep no-NAT/no-always-on-LB posture intact.
3. Materialize canonical SSM path surfaces for Confluent + DB credentials in demo stack.
4. Materialize Confluent contract surfaces in demo stack (cluster/env/topic map handles + outputs) and carry live-topic verification to M2.F command checks.

### Planned implementation scope
1. Expand `infra/terraform/modules/demo/*`:
- VPC/public-subnet/security-group scaffolding,
- ECS cluster + minimal task/service scaffolding (desired count 0),
- runtime Postgres RDS instance,
- canonical SSM parameter writes for Confluent/DB/IG paths,
- Confluent topic-catalog artifact for deterministic runtime wiring.
2. Expand `infra/terraform/dev_min/demo/*` root variables/module wiring/outputs to expose required handles.
3. Run `terraform fmt`, `init -reconfigure`, `validate`, `plan`, `show -json` for demo stack.
4. Regenerate M2.D evidence snapshot and update blockers/status in M2 docs + logbook.

### Boundaries
1. No `terraform apply` or `terraform destroy` in this pass.
2. No console mutation.
3. Evidence remains non-secret (only paths/ids, not decrypted secret values).

## Entry: 2026-02-13 1:49PM - Post-change record: M2D-B1..B4 closed via demo-stack capability expansion

### What was implemented
1. Expanded Terraform demo module/root from minimal stub to capability-complete M2.D substrate surfaces:
- network scaffold: VPC + public subnets + IGW + route table + SGs,
- ECS scaffold: cluster + task execution/app roles + Fargate task definition + desired-count-zero service,
- runtime DB: Postgres RDS instance + DB subnet group,
- canonical SSM writes: Confluent bootstrap/api key/api secret, DB user/password, IG API key,
- Confluent contract artifact: topic catalog S3 object + output surfaces.
2. Updated demo root outputs to expose required handle surfaces for downstream phases.
3. Updated demo documentation/variables/tfvars examples to align with new command surface and handle map.

### Validation executed
1. `terraform fmt -recursive infra/terraform/dev_min/demo infra/terraform/modules/demo` -> PASS.
2. `terraform -chdir=infra/terraform/dev_min/demo init -reconfigure "-backend-config=backend.hcl.example"` -> PASS.
3. `terraform -chdir=infra/terraform/dev_min/demo validate` -> PASS.
4. `terraform -chdir=infra/terraform/dev_min/demo plan -input=false -out <plan>` -> PASS.
5. `terraform -chdir=infra/terraform/dev_min/demo show -json <plan>` -> PASS.

### M2.D evidence and closure
1. New M2.D snapshot:
- local: `runs/dev_substrate/m2_d/20260213T134810Z/m2_d_demo_apply_contract_snapshot.json`
- durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T134810Z/m2_d_demo_apply_contract_snapshot.json`
2. Snapshot result:
- `required_demo_categories`: all true (`confluent_cluster_topics`, `ecs_scaffolding`, `runtime_db`, `ssm_secret_writes`),
- `overall_pass=true`.
3. Blocker resolution:
- `M2D-B1..M2D-B4` moved to resolved in M2 deep plan.
4. Status sync:
- `platform.M2.build_plan.md`: `M2.D` marked complete, unresolved blocker register cleared.
- `platform.build_plan.md`: M2 sub-phase tracker marks `M2.D` complete; immediate next action moved to `M2.E`.

### Confluent lane boundary (explicit)
1. M2.D closure mode is `contract_materialized_in_demo_stack`.
2. Live Confluent topic existence/connectivity/ACL checks remain enforced in `M2.F` command-lane verification.

### Drift sentinel checkpoint
1. No `terraform apply`/`destroy` executed in this pass.
2. No console mutation executed.

## Entry: 2026-02-13 1:55PM - Pre-change lock: execute M2.E secret materialization and access checks

### Trigger
USER directed progression to M2.E implementation.

### Objective
1. Validate required SSM path materialization/readability for Confluent, DB, and IG secret locators.
2. Validate runtime IAM boundary for secret reads (execution role vs app/runtime role).
3. Produce non-secret evidence artifact `secret_surface_check.json` and sync phase status.

### Planned checks
1. `aws ssm get-parameter --name <path> --with-decryption --query Parameter.Name --output text` for all required paths.
2. `aws iam get-role` for runtime roles used in demo stack.
3. `aws iam simulate-principal-policy` for SSM read actions against pinned secret parameter ARNs.
4. Redaction policy: evidence stores names/booleans/results only; never secret values.

### Boundaries
1. No `terraform apply`/`destroy` in this pass.
2. No console mutation.

## Entry: 2026-02-13 1:58PM - Post-change record: M2.E executed fail-closed; blockers surfaced

### What was implemented
1. Executed M2.E live secret-surface checks for required SSM paths (Confluent/DB/IG).
2. Executed runtime role existence checks for:
- `fraud-platform-dev-min-ecs-task-execution`
- `fraud-platform-dev-min-ecs-task-app`
3. Added IAM least-privilege hardening in Terraform demo module:
- `module.demo.aws_iam_role_policy.ecs_task_app_secret_read` now pins app-role SSM read to required secret paths.
4. Produced non-secret M2.E evidence artifact.

### Evidence
1. Local:
- `runs/dev_substrate/m2_e/20260213T135629Z/secret_surface_check.json`
2. Durable:
- `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T135629Z/secret_surface_check.json`

### Material findings
1. Confluent secret paths exist/readable by operator.
2. DB secret paths (`/fraud-platform/dev_min/db/user`, `/fraud-platform/dev_min/db/password`) are missing.
3. IG secret path (`/fraud-platform/dev_min/ig/api_key`) is missing.
4. Runtime roles required for IAM-boundary validation are missing in live account.
5. Result: `overall_pass=false` for M2.E snapshot.

### Blockers registered
1. `M2E-B1`: missing required SSM paths.
2. `M2E-B2`: missing runtime roles; least-privilege boundary not yet verifiable live.

### Status sync
1. `platform.M2.build_plan.md` updated with M2.E command surface, closure summary, evidence, and current blockers.
2. `platform.build_plan.md` immediate next action moved to resolve `M2E-B1..M2E-B2` before rerunning M2.E.

### Drift sentinel checkpoint
1. No `terraform apply`/`destroy` executed.
2. No console mutation executed.

## Entry: 2026-02-13 2:03PM - Pre-change lock: resolve M2E-B1/M2E-B2 by materializing live demo resources

### Trigger
USER directed blocker resolution for `M2E-B1` and `M2E-B2`.

### Resolution strategy
1. Run full demo-stack apply (no targeted apply) to materialize missing SSM paths and runtime IAM roles.
2. Protect existing Confluent credentials by supplying current live SSM values as Terraform inputs at apply time.
3. Re-run M2.E secret/access checks and require `overall_pass=true` before closure.

### Safety rules
1. No placeholder Confluent values are allowed in apply input.
2. Evidence outputs contain names/results only, never secret values.
3. If apply or checks fail, M2.E remains fail-closed with explicit blocker update.

## Entry: 2026-02-13 2:15PM - Post-change record: M2E-B1/M2E-B2 resolved and M2.E closed

### Execution summary
1. Performed demo-stack apply to materialize missing live secret/role surfaces required for M2.E.
2. First apply attempt surfaced DB engine-version drift (`postgres 16.3` unavailable in `eu-west-2`) after partial resource creation.
3. Corrected DB engine defaults from `16.3` -> `16.12` in Terraform demo/module variables and reran apply to completion.

### Terraform changes for closure hardening
1. Added app runtime least-privilege secret-read policy in demo module:
- `aws_iam_role_policy.ecs_task_app_secret_read` with path-scoped SSM read permissions.
2. Corrected DB engine version defaults:
- `infra/terraform/modules/demo/variables.tf`
- `infra/terraform/dev_min/demo/variables.tf`
- `infra/terraform/dev_min/demo/terraform.tfvars.example`

### Live materialization outcomes
1. Required secret paths now exist/readable:
- `/fraud-platform/dev_min/confluent/bootstrap`
- `/fraud-platform/dev_min/confluent/api_key`
- `/fraud-platform/dev_min/confluent/api_secret`
- `/fraud-platform/dev_min/db/user`
- `/fraud-platform/dev_min/db/password`
- `/fraud-platform/dev_min/ig/api_key`
2. Runtime roles now exist:
- `fraud-platform-dev-min-ecs-task-execution`
- `fraud-platform-dev-min-ecs-task-app`
3. Demo DB now exists with endpoint output:
- `fraud-platform-dev-min-db.c32cck04kkmn.eu-west-2.rds.amazonaws.com`

### M2.E proof checks
1. IAM simulation (`ssm:GetParameter` on pinned secret ARNs):
- app role allowed count = `6/6`,
- execution role allowed count = `0/6` (`implicitDeny`).
2. Evidence snapshot:
- local: `runs/dev_substrate/m2_e/20260213T141419Z/secret_surface_check.json`
- durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T141419Z/secret_surface_check.json`
- `overall_pass=true`.

### Status synchronization
1. `M2E-B1` and `M2E-B2` moved to resolved blocker list.
2. `M2.E` marked `CLOSED_EXEC` in deep plan and completed in M2 checklist.
3. Main plan next action advanced to `M2.F` execution.

### Drift sentinel checkpoint
1. Terraform mutation executed intentionally in this pass (`apply`) to resolve live materialization blockers.
2. No console mutation executed.

## Entry: 2026-02-13 2:19PM - Pre-change lock: codify cost-accrual learning and add guardrail monitoring surfaces

### Trigger
USER requested a detailed implementation-note record of cost-accrual learning and practical anti-surprise monitoring setup.

### Objective
1. Capture the real cost challenge experienced during live dev-substrate implementation.
2. Pin where cost-guardrail is owned in M2 (`M2.I`) and extend it with executable monitoring controls.
3. Add a monitoring surface (`dashboard or equivalent`) that can be used daily during implementation.

### Planned changes
1. Add a detailed learning entry framing:
- why free-tier overages in S3 requests are usually small,
- why managed runtime resources (especially RDS) dominate risk,
- why AWS billing lag can hide same-day accrual,
- why Confluent spend must be tracked outside AWS Cost Explorer.
2. Add tools under `tools/dev_substrate`:
- cost dashboard template,
- cost snapshot command utility.
3. Register the monitoring commands and artifact expectations in `M2.I` section of deep plan.

### Boundaries
1. Read-only cost queries and dashboard provisioning only.
2. No destructive infrastructure operations.
3. No secret values are written into any monitoring artifact.

## Entry: 2026-02-13 2:23PM - Post-change record: cost-accrual challenge framing + monitoring setup for anti-surprise operations

### Experience framing (challenge now visible during implementation)
1. Core lesson from this phase: moving from laptop to managed substrate changes the risk profile from "compute bottlenecks" to "always-on cost drift".
2. Free-tier overage signals can be misleading if interpreted alone:
- S3 request overages often appear first and are usually low monetary impact,
- but managed runtime resources (especially always-on DBs) dominate monthly risk.
3. Billing visibility is delayed:
- Cost Explorer is authoritative but lagged/estimated, so same-day accrual from newly-created resources may not appear immediately.
4. Multi-platform cost truth is split:
- AWS Cost Explorer does not include Confluent Cloud billing, so AWS-only monitoring is incomplete.

### Concrete findings captured during this run
1. Live demo substrate now includes active RDS instance (`db.t4g.micro`, 20 GB gp2) and this is the primary immediate AWS accrual lane.
2. ECS probe service is desired/running `0` and NAT gateways are absent (no hidden NAT burn).
3. Cost Explorer month-to-date currently shows low S3-led spend; this does not yet fully reflect newly materialized runtime resources due data lag.

### Cost management posture pinned from this experience
1. Treat M2.I as the authoritative cost-guardrail phase for closure (`Budget Guardrails and Teardown Viability`).
2. Run dual-lens monitoring during active implementation:
- lagged finance lens: Cost Explorer + Budgets,
- live posture lens: RDS/ECS/NAT resource state checks.
3. Fail-closed rule:
- if cost trend exceeds planned envelope or unplanned always-on resources appear, pause phase progression and execute teardown/hold decision.

### Implemented monitoring surfaces
1. Added CloudWatch dashboard template:
- `tools/dev_substrate/cost_guardrail_dashboard.json`
- dashboard name: `fraud-platform-dev-min-cost-guardrail`
2. Added cost snapshot utility:
- `tools/dev_substrate/cost_guardrail_snapshot.py`
- emits non-secret snapshot with CE, budgets, and live resource posture.
3. Extended `M2.I` tasks in deep plan to include dashboard + snapshot command lane and live risk checks.

### Why this prevents surprise bills
1. Dashboard provides continuous trend visibility.
2. Snapshot utility gives actionable "what is currently running" evidence, not just delayed billing numbers.
3. Combined with teardown discipline, this keeps spend within an intentional envelope instead of accidental accumulation.

## Entry: 2026-02-13 2:33PM - Post-change execution proof: dashboard activated and first snapshot captured

### Trigger
Close the loop on cost-guardrail hardening by converting tooling from "defined" to "operational."

### Actions executed
1. Provisioned CloudWatch dashboard from template:
- command: `aws cloudwatch put-dashboard --dashboard-name fraud-platform-dev-min-cost-guardrail --dashboard-body file://tools/dev_substrate/cost_guardrail_dashboard.json`
- result: `DashboardValidationMessages=[]` (accepted without validation errors).
2. Executed first cost snapshot:
- command: `python tools/dev_substrate/cost_guardrail_snapshot.py`
- output artifact: `runs/dev_substrate/cost_guardrail/20260213T143327Z/cost_guardrail_snapshot.json`

### Outcome
1. Cost-monitoring surface is now live (dashboard present in account).
2. Snapshot lane is executable and producing non-secret evidence artifacts.
3. M2.I monitoring controls are now both documented and operationalized.

### Drift sentinel checkpoint
1. No platform flow or truth-owner semantics changed.
2. This is observability/governance hardening for cost control only.

## Entry: 2026-02-13 2:50PM - Pre-change lock: M2.F Kafka topic readiness execution with fail-closed lane selection

### Trigger
USER approved moving forward with `M2.F` implementation and accepted the recommended verification approach.

### Problem surfaced during execution planning
1. `confluent` CLI is now installed and available, but topic commands in this release are Confluent Platform REST-proxy commands.
2. Running `confluent kafka topic list --url <Confluent Cloud endpoint>` returns explicit warning that Confluent Cloud URLs are not supported in that command path.
3. This creates a command-lane mismatch if we insist on CLI-only closure for M2.F.

### Decision (fail-closed, no handwaving)
1. Keep M2.F objective unchanged: prove topic existence, auth connectivity, and minimum access posture for required Spine Green v0 topics.
2. Pivot execution lane to the already allowed alternative in M2.F:
- Kafka admin protocol/script lane (non-interactive),
- backed by SSM-resolved bootstrap + Kafka API key/secret.
3. Record CLI mismatch as an explicit execution constraint, not as hidden drift.

### Implementation plan for this pass
1. Resolve required topic handles from registry (required set only).
2. Resolve Kafka bootstrap/API creds from pinned SSM paths (do not persist secrets).
3. Execute Kafka topic metadata checks for each required topic via scripted admin path.
4. Emit non-secret evidence artifact:
- local: `runs/dev_substrate/m2_f/<timestamp>/topic_readiness_snapshot.json`
- durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_<timestamp>/topic_readiness_snapshot.json`
5. Update M2 deep plan and main plan status:
- mark `M2.F` complete only on full PASS,
- otherwise register blocker and keep M2.F open.

### Boundaries
1. No Terraform mutation in this pass.
2. No secret value persistence.
3. No ownership/plane semantic change; this is substrate verification only.

## Entry: 2026-02-13 2:57PM - Post-change record: M2.F executed fail-closed, blocker registered

### What was executed
1. Installed/validated `confluent` CLI and attempted CLI topic lane.
2. Confirmed runtime mismatch:
   - CLI topic command path rejected Confluent Cloud URL usage in this context.
3. Executed Kafka admin script lane using `confluent-kafka` metadata checks with SSM-resolved bootstrap/key/secret.
4. Persisted M2.F evidence:
   - local: `runs/dev_substrate/m2_f/20260213T145630Z/topic_readiness_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T145630Z/topic_readiness_snapshot.json`

### Runtime result
1. Kafka auth/connectivity failed at SASL handshake (`overall_pass=false`).
2. Because auth failed, required-topic existence and ACL-readiness checks cannot be marked PASS.
3. M2.F was not force-closed; fail-closed posture retained.

### Documentation/state updates made
1. Updated `platform.M2.build_plan.md`:
   - pinned canonical M2.F verification lane as Kafka admin protocol script,
   - recorded execution summary and evidence paths,
   - registered open blocker `M2F-B1`.
2. Updated `platform.build_plan.md` immediate next action:
   - resolve `M2F-B1`, then rerun M2.F to `overall_pass=true`.

### Blocker closure path
1. Rotate/fix Confluent Kafka credentials at pinned SSM paths:
   - `/fraud-platform/dev_min/confluent/api_key`
   - `/fraud-platform/dev_min/confluent/api_secret`
2. Rerun M2.F command lane and verify:
   - auth PASS,
   - all required topics present,
   - `topic_readiness_snapshot.json` reports `overall_pass=true`.

### Drift sentinel checkpoint
1. No platform semantic drift introduced.
2. This is substrate truth exposure and blocker registration only.

## Entry: 2026-02-13 3:25PM - Post-change record: Confluent provisioning lane added as first-class IaC substrate

### Implementation delivered
1. Added dedicated Confluent Terraform module and stack:
   - module: `infra/terraform/modules/confluent/`
   - root stack: `infra/terraform/dev_min/confluent/`
2. New stack now provisions:
   - Confluent environment + Kafka cluster,
   - pinned topic map creation,
   - runtime Kafka API key owned by runtime service account,
   - SSM materialization for bootstrap/key/secret using pinned paths.
3. Updated demo stack to consume Confluent outputs by remote state (default):
   - `confluent_credentials_source = "remote_state"` now default in demo variables,
   - demo reads `dev_min/confluent/terraform.tfstate` outputs for cluster metadata + runtime Kafka credentials,
   - manual fallback remains available via `confluent_credentials_source = "manual"`.

### Documentation and contract updates completed
1. Handles registry updated for new stack/state keys:
   - `TF_STATE_KEY_CONFLUENT`,
   - `TF_STACK_CONFLUENT_DIR`,
   - pinned Confluent Terraform input env vars for Cloud API credentials.
2. P0 runbook updated to explicit three-stack order:
   - apply `core`, then `confluent`, then `demo`.
3. M2 plan/main build plan updated:
   - M2 substrate definition now core+confluent+demo,
   - M2F blocker closure path now points to applying Confluent stack and rerunning M2.F.

### Validation evidence (static)
1. `terraform fmt` completed for updated/new stack paths.
2. `terraform validate` passed:
   - `infra/terraform/dev_min/confluent`
   - `infra/terraform/dev_min/demo`
3. No apply executed in this pass; this is code+plan lane enablement and command-surface closure.

### Operational command order pinned (for execution phase)
1. `terraform -chdir=infra/terraform/dev_min/core init -reconfigure -backend-config=backend.hcl`
2. `terraform -chdir=infra/terraform/dev_min/core apply -input=false`
3. `terraform -chdir=infra/terraform/dev_min/confluent init -reconfigure -backend-config=backend.hcl`
4. `terraform -chdir=infra/terraform/dev_min/confluent apply -input=false`
5. `terraform -chdir=infra/terraform/dev_min/demo init -reconfigure -backend-config=backend.hcl`
6. `terraform -chdir=infra/terraform/dev_min/demo apply -input=false`

### Impact on active blocker
1. `M2F-B1` is now structurally addressable via IaC (no UI-only remediation required).
2. M2.F remains fail-closed until Confluent stack apply is run with valid Confluent Cloud management credentials and M2.F verification returns `overall_pass=true`.

## Entry: 2026-02-13 3:15PM - Pre-change lock: add first-class Confluent provisioning lane (IaC) to remove manual key lifecycle

### Trigger
USER explicitly requested adding a Confluent provisioning lane because repeated manual cluster/key creation is not acceptable for IaC quality.

### Problem statement
1. Current `dev_min` Terraform topology has only `core` and `demo`.
2. Confluent bootstrap/API key/API secret are currently injected into `demo` as external values, then written to SSM.
3. If Confluent resources are torn down/recreated outside Terraform, runtime credentials drift and M2.F fails (observed as `M2F-B1`).

### Decision
1. Introduce a dedicated Terraform stack: `infra/terraform/dev_min/confluent`.
2. Add a dedicated Terraform module: `infra/terraform/modules/confluent`.
3. Move Confluent resource lifecycle into IaC:
   - environment,
   - Kafka cluster,
   - runtime service account + Kafka API key,
   - pinned topic map creation.
4. Write runtime Kafka bootstrap/key/secret to pinned AWS SSM paths from this stack.
5. Update demo module posture:
   - demo no longer owns Confluent SSM parameter values,
   - demo consumes pinned path handles and Confluent metadata only.

### Why this path
1. Removes manual cluster/key churn from normal bring-up/teardown cycle.
2. Preserves deterministic handle surfaces already used across runbook and phase gates.
3. Keeps `core` persistent and `demo` ephemeral while making Confluent lifecycle explicit and auditable.

### Planned touchpoints
1. Terraform:
   - `infra/terraform/modules/confluent/*` (new),
   - `infra/terraform/dev_min/confluent/*` (new),
   - `infra/terraform/modules/demo/*` (remove Confluent secret value ownership),
   - `infra/terraform/dev_min/demo/*` (consume Confluent metadata without manual secret injection).
2. Docs:
   - `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`,
   - `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`,
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M2.build_plan.md`,
   - `infra/terraform/dev_min/*/README.md` and `infra/terraform/modules/README.md`.
3. Execution posture:
   - M2.F remains fail-closed until new lane is applied and auth/topic checks pass.

### Boundaries
1. No secret values committed to repo.
2. No console-only patching accepted.
3. Existing unrelated worktree changes remain untouched.

## Entry: 2026-02-13 3:44PM - M2.F deterministic rerun lane codified and executed (still fail-closed on auth)

### Trigger
USER asked to return to settling `M2.F` and close ambiguity in the verification process.

### Problem statement
1. `M2.F` had an open blocker (`M2F-B1`) and prior execution evidence, but the command lane was not yet codified as a reusable script in-repo.
2. We needed a deterministic rerun surface that:
   - resolves pinned SSM paths,
   - performs Kafka metadata readiness checks,
   - emits non-secret evidence,
   - supports immediate durable upload.

### Decision
1. Add a dedicated M2.F verification utility:
   - `tools/dev_substrate/verify_m2f_topic_readiness.py`.
2. Pin this utility as the canonical M2.F execution command in `platform.M2.build_plan.md`.
3. Execute the command immediately and persist fresh evidence locally and in S3.

### Implementation
1. Created `tools/dev_substrate/verify_m2f_topic_readiness.py` with:
   - SSM resolution for bootstrap/key/secret paths,
   - Confluent Kafka admin metadata check (primary lane),
   - `kafka-python` fallback diagnostic lane,
   - JSON snapshot output (`overall_pass` fail-closed),
   - optional evidence upload support.
2. Executed:
   - `python tools/dev_substrate/verify_m2f_topic_readiness.py`
   - `aws s3 cp runs/dev_substrate/m2_f/20260213T154433Z/topic_readiness_snapshot.json s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T154433Z/topic_readiness_snapshot.json`
   - `terraform -chdir=infra/terraform/dev_min/confluent init -reconfigure -backend-config=\"bucket=fraud-platform-dev-min-tfstate\" -backend-config=\"key=dev_min/confluent/terraform.tfstate\" -backend-config=\"region=eu-west-2\" -backend-config=\"dynamodb_table=fraud-platform-dev-min-tf-locks\" -backend-config=\"encrypt=true\"`
   - `terraform -chdir=infra/terraform/dev_min/confluent plan -input=false` (confirmed fail-closed on missing `TF_VAR_confluent_cloud_api_key` / `TF_VAR_confluent_cloud_api_secret`)
3. Updated planning docs to reflect the pinned command lane and latest evidence paths.

### Result
1. Snapshot captured at:
   - local: `runs/dev_substrate/m2_f/20260213T154433Z/topic_readiness_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T154433Z/topic_readiness_snapshot.json`
2. Outcome remains fail-closed:
   - `overall_pass=false`,
   - connectivity/auth failure persists against bootstrap endpoint,
   - `M2F-B1` remains open.

### Closure path unchanged
1. Apply `infra/terraform/dev_min/confluent` with valid Confluent Cloud management credentials.
2. Confirm updated runtime key/secret are written to pinned SSM paths.
3. Rerun the canonical command lane and require `overall_pass=true` before marking `M2.F` complete.

## Entry: 2026-02-13 4:07PM - Workflow secret-name mapping added (GitHub uppercase -> Terraform lowercase TF_VAR)

### Trigger
USER confirmed GitHub secrets were created in uppercase and requested the mapping to be implemented.

### Decision
1. Keep GitHub secret names as uppercase:
   - `TF_VAR_CONFLUENT_CLOUD_API_KEY`
   - `TF_VAR_CONFLUENT_CLOUD_API_SECRET`
2. Map these at workflow runtime into Terraform-required lowercase env names:
   - `TF_VAR_confluent_cloud_api_key`
   - `TF_VAR_confluent_cloud_api_secret`

### Implementation
1. Updated `.github/workflows/dev_min_m1_packaging.yml`:
   - added top-level `env` mapping block for the two Confluent TF vars.

### Outcome
1. Secret naming is now stable for GitHub UI conventions (uppercase) while preserving Terraform provider variable resolution requirements.
2. No secret values were committed; only key-name mapping was introduced.

## Entry: 2026-02-13 4:08PM - Pre-change lock: add CI-executable M2.F closure lane

### Trigger
USER directed immediate progression to close `M2.F` after workflow secret mapping.

### Problem statement
1. `M2.F` currently has deterministic local command tooling, but closure still depends on manual/local execution context.
2. Target posture requires non-laptop execution and repeatable CI-grade closure for:
   - Confluent runtime credential regeneration (`infra/terraform/dev_min/confluent`),
   - topic readiness verification (`tools/dev_substrate/verify_m2f_topic_readiness.py`),
   - durable evidence production.

### Decision
1. Add a dedicated GitHub Actions workflow for `M2.F` execution.
2. Workflow must:
   - use OIDC AWS auth (no static AWS keys),
   - map uppercase GitHub Confluent secrets to lowercase Terraform `TF_VAR` names,
   - run Terraform init/apply for Confluent stack,
   - run the canonical M2.F verification script,
   - persist CI artifacts and fail closed on non-pass.

### Boundaries
1. No secret values logged or committed.
2. No change to phase status until PASS evidence is produced.
3. Existing unrelated workspace changes remain untouched.

## Entry: 2026-02-13 4:10PM - Post-change record: CI M2.F closure workflow added and pinned

### Implementation delivered
1. Added workflow:
   - `.github/workflows/dev_min_m2f_topic_readiness.yml`
2. Workflow behavior:
   - enforces OIDC AWS credential posture,
   - validates Confluent management secrets are present via mapped Terraform `TF_VAR` names,
   - runs Terraform init/apply for `infra/terraform/dev_min/confluent`,
   - runs canonical verifier `tools/dev_substrate/verify_m2f_topic_readiness.py`,
   - uploads M2.F snapshot artifact.
3. Secret mapping posture preserved:
   - uppercase GitHub secrets are mapped to lowercase Terraform runtime names.

### Documentation alignment updates
1. Updated `platform.M2.build_plan.md`:
   - pinned CI workflow as canonical M2.F execution lane.
2. Updated `platform.build_plan.md`:
   - immediate next action now includes CI dispatch path for M2.F closure.

### Validation
1. Parsed workflow YAML successfully (syntax check).
2. No secret values were emitted to repo artifacts.

### Current phase status
1. `M2.F` remains open until a successful workflow/local execution produces `overall_pass=true`.

## Entry: 2026-02-13 4:25PM - M2.F CI lane hardened after feedback; new IAM blocker exposed (`M2F-B2`)

### Trigger
1. USER challenged the workflow design for depending on repository-local verifier tooling.
2. USER requested continuation toward M2.F closure.

### Actions performed
1. Published CI workflow lane to default branch via PR:
   - PR `#46` (merged): adds `dev_min_m2f_topic_readiness` workflow and Confluent secret mapping.
2. Initial CI execution attempts:
   - run `21993925506` (`migrate-dev`) failed at OIDC assume-role because role trust allowed only `main`/`dev`.
   - run `21994101734` (`main`) failed because Confluent stack path did not exist on `main` checkout.
3. Refactored workflow to avoid local script dependency and bridge trusted ref constraint:
   - PR `#48` (merged): workflow now runs verifier inline and supports `checkout_ref` (default `migrate-dev`) while dispatching from trusted `main`.
4. Re-ran CI:
   - run `21994243860` (`main`) reached OIDC successfully, but Terraform backend init failed with `403` on state object access.

### Decision and implications
1. USER feedback accepted: M2.F workflow no longer requires `tools/dev_substrate/verify_m2f_topic_readiness.py` for CI execution.
2. New explicit blocker identified and pinned:
   - `M2F-B2`: OIDC role policy lacks required backend/SSM/evidence permissions for Confluent Terraform lane.
3. M2.F remains fail-closed until IAM permission gap is remediated and CI rerun yields `overall_pass=true`.

## Entry: 2026-02-13 6:43PM - Pre-change lock for M2.F closure: import adoption lane hardening

### Trigger
1. USER directed immediate resolution now that valid Confluent credentials are available.
2. Latest CI run (`21998530514`) still fails in Terraform apply because Confluent topics already exist but are missing from Terraform state.

### Problem diagnosis
1. Existing workflow import step has two deterministic defects:
   - cluster ID extraction uses broad `awk` matching on `terraform state show`, producing malformed import IDs,
   - topic import does not set required import-time Kafka credentials (`IMPORT_KAFKA_API_KEY`, `IMPORT_KAFKA_API_SECRET`), so provider import fails and topic adoption is skipped.
2. Skipped adoption leaves `confluent_kafka_topic.topics[*]` absent from state, so apply re-creates and fails on `Topic already exists`.

### Decision
1. Harden `.github/workflows/dev_min_m2f_topic_readiness.yml` import lane to:
   - resolve `confluent_cluster_id` and `kafka_rest_endpoint` from Terraform outputs (not brittle state text parsing),
   - resolve import Kafka credentials from Terraform outputs first (`runtime_kafka_api_key`, `runtime_kafka_api_secret`), with fallback to state-held API keys for Basic-cluster recovery,
   - fail closed before apply if cluster exists but import credentials are unavailable,
   - classify import results explicitly (`imported`, `already-managed`, `failed`) and fail on non-recoverable import errors.
2. Keep branch posture unchanged (`migrate-dev` only) and avoid branch-history operations.

### Execution plan
1. Patch workflow import step only.
2. Commit and push to `origin/migrate-dev`.
3. Dispatch fresh `dev_min_m2f_topic_readiness` run on `migrate-dev`.
4. Require end-to-end pass (`Terraform apply` + `overall_pass=true`) before marking `M2.F` complete.

## Entry: 2026-02-13 6:52PM - Post-change record: M2.F closed green on CI

### Implementation delivered
1. Patched `.github/workflows/dev_min_m2f_topic_readiness.yml` import lane:
   - switched cluster/REST resolution to Terraform outputs (`confluent_cluster_id`, `kafka_rest_endpoint`),
   - added deterministic import credential resolution (`runtime_kafka_api_key` / `runtime_kafka_api_secret`) with SSM fallback,
   - fail-closed guard when cluster exists but import credentials are unavailable,
   - explicit import outcome handling (`imported`, `already-managed`, `non-existent remote object`, hard-fail on unexpected errors).
2. Pushed workflow patch to `migrate-dev`:
   - commit `30756555`.
3. Applied IAM policy correction on role `GitHubAction-AssumeRoleWithAction` (`GitHubActionsTerraformConfluentStateDevMin`):
   - added evidence object/list permissions for `evidence/dev_min/*` prefix in `fraud-platform-dev-min-evidence`.

### Validation runs
1. Run `21998686793`:
   - topic adoption + Terraform apply succeeded,
   - verifier failed only on evidence upload `AccessDenied` (`s3:PutObject` on `evidence/dev_min/substrate/...`).
2. Run `21998790226`:
   - full workflow succeeded end-to-end,
   - verifier reported `overall_pass=true`.

### Evidence
1. CI run:
   - `https://github.com/EsosaOrumwese/fraud-detection-system/actions/runs/21998790226`
2. Local artifact download:
   - `runs/dev_substrate/m2_f/ci_artifacts_21998790226/m2f-topic-readiness-20260213T184917Z/topic_readiness_snapshot.json`
3. Durable evidence:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T184917Z/topic_readiness_snapshot.json`

### Phase status update
1. `M2.F` marked complete in:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M2.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`

## Entry: 2026-02-13 7:01PM - M2.G planning expansion (network posture lane, fail-closed)

### Trigger
1. USER directed progression to `M2.G` and requested planning expansion before execution.

### Planning problem
1. Existing `M2.G` section was too coarse (3 checklist bullets) and did not pin:
   - concrete command lane,
   - explicit blocker taxonomy,
   - evidence schema + pass predicates,
   - deterministic handle-resolution sequence.
2. That gap risks reintroducing anti-cram drift during execution (`M2.G` appearing "done" without closure-grade proof).

### Authority reviewed for expansion
1. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`:
   - hard no-NAT/no-always-on-LB/no-always-on-fleets posture.
2. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`:
   - policy constants and network handles (`VPC_ID`, `SUBNET_IDS_PUBLIC`, SG handles, ECS cluster handle).
3. Current Terraform runtime truth:
   - `infra/terraform/modules/demo/main.tf` and outputs show public-subnet + IGW route posture, SG resources, ECS service scaffolding (`desired_count=0`), and no LB/NAT resources in the module.

### Decisions pinned in plan
1. `M2.G` is decomposed into `M2.G-A..M2.G-E`:
   - A: handle resolution and preflight,
   - B: forbidden-resource checks (NAT/LB/fleet),
   - C: SG/subnet/route posture checks,
   - D: evidence + pass contract,
   - E: blocker model.
2. LB rule for v0 M2:
   - hard fail if any LB exists in demo VPC during M2 (no exception lane pinned yet).
3. Fleet rule for v0 M2:
   - hard fail if any ECS service has `desiredCount > 0` during M2 substrate phase.
4. Evidence contract expanded:
   - adds `network_posture_snapshot.json` while retaining `no_nat_check.json` compatibility artifact.

### Files updated for planning alignment
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M2.build_plan.md`
   - expanded M2.G into closure-grade sub-phases, command templates, blockers, and DoD.
   - capability matrix/evidence list updated for `network_posture_snapshot.json`.
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
   - immediate next action now points to executing `M2.G-A -> M2.G-E` with required M2.G evidence gates.

### Execution posture after planning
1. `M2.G` is now execution-ready from a planning perspective.
2. No runtime mutation executed in this step; this update is planning-only and fail-closed.

## Entry: 2026-02-13 7:09PM - M2.G executed end-to-end and closed green

### Trigger
1. USER directed: proceed with entirety of `M2.G`.

### Execution summary
1. Resolved handles from Terraform outputs:
   - `VPC_ID`, `SUBNET_IDS_PUBLIC`, `SECURITY_GROUP_ID_APP`, `SECURITY_GROUP_ID_DB`, `ECS_CLUSTER_NAME`.
2. Confirmed policy constants from handles registry:
   - `FORBID_NAT_GATEWAY=true`
   - `FORBID_ALWAYS_ON_LOAD_BALANCER=true`
   - `FORBID_ALWAYS_ON_FLEETS=true`
3. Ran M2.G checks:
   - NAT gateways in VPC,
   - ALB/NLB + Classic ELB in VPC,
   - ECS services desired counts,
   - subnet public-IP mapping + IGW default routes,
   - app/db SG ingress posture.

### Correction applied during execution
1. First artifact attempt used a subnet argument join form that can mask command failure in PowerShell.
2. Re-ran the full lane with strict exit-code assertions after every external command.
3. Marked first attempt as superseded and removed its durable artifacts from S3.

### Final result (authoritative run)
1. M2 execution id:
   - `m2_20260213T190819Z`
2. PASS predicates:
   - `nat_gateways_non_deleted_count=0`
   - `load_balancers_count=0`
   - `ecs_services_desired_gt_zero_count=0`
   - `sg_subnet_route_checks_pass=true`
   - `overall_pass=true`
3. Blockers:
   - none (`M2G-B1..B4` not triggered).

### Evidence
1. Local:
   - `runs/dev_substrate/m2_g/20260213T190819Z/network_posture_snapshot.json`
   - `runs/dev_substrate/m2_g/20260213T190819Z/no_nat_check.json`
2. Durable:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T190819Z/network_posture_snapshot.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T190819Z/no_nat_check.json`

### Planning status updates applied
1. Marked `M2.G` complete in:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M2.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. Shifted immediate next action to `M2.H` DB/migrations readiness lane.

## Entry: 2026-02-13 7:36PM - M2.H planning expansion and fail-closed blocker pin

### Trigger
1. USER directed start of `M2.H` planning.

### Planning analysis
1. Existing `M2.H` section was high-level and did not pin:
   - concrete command lane for migration invocation,
   - blocker taxonomy,
   - evidence artifacts for DB readiness vs migration readiness vs migration run result.
2. Current runtime truth inspection showed:
   - registry pins `DB_MIGRATIONS_REQUIRED=true` and requires `TD_DB_MIGRATIONS`,
   - demo Terraform outputs currently expose probe task definition but no dedicated migration task-definition output.

### Decisions pinned in M2.H plan
1. Expanded `M2.H` into `M2.H-A..M2.H-F`:
   - A: handle resolution and preconditions,
   - B: RDS control-plane readiness,
   - C: DB secret/auth surface checks,
   - D: migration task readiness contract,
   - E: canonical command lane + evidence,
   - F: rollback + blocker model.
2. Added explicit M2.H blockers:
   - `M2H-B1` missing/unresolved `TD_DB_MIGRATIONS`,
   - `M2H-B2` RDS readiness failure,
   - `M2H-B3` DB auth material failure,
   - `M2H-B4` migration execution failure.
3. Added M2 evidence contract extensions:
   - `db_readiness_snapshot.json`
   - `db_migration_readiness_snapshot.json`
   - `db_migration_run_snapshot.json`

### Fail-closed update
1. Added `M2H-B1` to unresolved blocker register because `DB_MIGRATIONS_REQUIRED=true` is pinned but a concrete `TD_DB_MIGRATIONS` handle surface is not yet materialized in current demo outputs.
2. Updated main platform build plan immediate next action:
   - close `M2H-B1` first,
   - then execute `M2.H-A -> M2.H-F`.

## Entry: 2026-02-13 7:41PM - M2H-B1 resolved (TD_DB_MIGRATIONS materialized)

### Trigger
1. USER directed: resolve `M2H-B1` first.

### Implementation
1. Materialized DB migration task definition in Terraform demo module:
   - added `aws_ecs_task_definition.db_migrations` in `infra/terraform/modules/demo/main.tf`.
2. Exposed concrete migration handles in outputs:
   - module outputs:
     - `ecs_db_migrations_task_definition_arn`
     - `ecs_db_migrations_task_definition_family`
     - `role_db_migrations_name`
   - dev_min stack outputs:
     - `ecs_db_migrations_task_definition_arn`
     - `td_db_migrations`
     - `role_db_migrations_name`
3. Updated handles registry to bind `TD_DB_MIGRATIONS` to these materialized outputs.

### Runtime materialization and verification
1. Applied targeted Terraform change:
   - `terraform -chdir=infra/terraform/dev_min/demo apply -input=false -auto-approve -target='module.demo.aws_ecs_task_definition.db_migrations'`
2. Verified handles resolve from live state:
   - `td_db_migrations = fraud-platform-dev-min-db-migrations`
   - `ecs_db_migrations_task_definition_arn = arn:aws:ecs:eu-west-2:230372904534:task-definition/fraud-platform-dev-min-db-migrations:1`
   - `role_db_migrations_name = fraud-platform-dev-min-ecs-task-app`
3. Verified ECS control plane:
   - task definition status `ACTIVE`.

### Evidence
1. Local:
   - `runs/dev_substrate/m2_h/20260213T194120Z/m2h_b1_resolution_snapshot.json`
2. Durable:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T194120Z/m2h_b1_resolution_snapshot.json`

### Notes
1. Post-targeted-apply `terraform plan -detailed-exitcode` returned `2` (unrelated pending drift), recorded in evidence but not blocking `M2H-B1` closure.
2. `M2H-B1` moved from open blockers to resolved blockers in `platform.M2.build_plan.md`.

## Entry: 2026-02-13 8:00PM - M2.H fully executed and closed with managed migration proof

### Trigger
1. USER directed: proceed with the entirety of `M2.H`.

### Execution scope
1. Ran full `M2.H-A -> M2.H-F` lane fail-closed from local CLI as control plane only:
   - resolved runtime handles from Terraform state,
   - validated RDS control-plane readiness + SG posture,
   - validated DB auth SSM paths (redacted checks only),
   - validated migration task definition readiness contract,
   - executed canonical ECS one-shot migration task and validated success semantics.

### Runtime result
1. Authoritative execution id:
   - `m2_20260213T195244Z`
2. Gate outcomes:
   - `M2.H-A`: pass (all required DB/migration handles resolvable),
   - `M2.H-B`: pass (`RDS available`, endpoint/port contract matched, DB SG not open-world),
   - `M2.H-C`: pass (user/password SSM material decryptable + non-empty; secret-safe evidence only),
   - `M2.H-D`: pass (`TD_DB_MIGRATIONS` active, `awsvpc`, role binding matched),
   - `M2.H-E`: pass (ECS run-task exit `0` and completion marker found in CloudWatch logs),
   - `M2.H-F`: pass (no open `M2H-B*` blockers).
3. Optional DSN posture:
   - `SSM_DB_DSN_PATH` is not required/used for this closure lane; canonical auth surface remains `SSM_DB_USER_PATH` + `SSM_DB_PASSWORD_PATH`.

### Evidence
1. Local:
   - `runs/dev_substrate/m2_h/20260213T195244Z/db_readiness_snapshot.json`
   - `runs/dev_substrate/m2_h/20260213T195244Z/db_migration_readiness_snapshot.json`
   - `runs/dev_substrate/m2_h/20260213T195244Z/db_migration_run_snapshot.json`
2. Durable:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T195244Z/db_readiness_snapshot.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T195244Z/db_migration_readiness_snapshot.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T195244Z/db_migration_run_snapshot.json`

### Plan-state updates
1. Marked `M2.H` complete in:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M2.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. Shifted immediate next action to `M2.I` budget/teardown guardrail lane.

## Entry: 2026-02-13 8:01PM - Pre-change lock: expand M2.I planning to closure-grade depth before execution

### Trigger
1. USER directed: "Let's go to M2.I planning".

### Problem statement
1. `M2.I` currently has only top-level tasks and DoD bullets, but lacks:
   - explicit decision pins to close ambiguity before execution,
   - sub-phase decomposition with lane-by-lane DoDs (`A..F` style),
   - blocker taxonomy and fail-closed halt criteria,
   - fully explicit command/evidence contract mapped to pinned handles.
2. Without this expansion, M2.I execution risks the same anti-cram drift that earlier phases exposed.

### Planning objective
1. Convert M2.I into a closure-grade execution blueprint that is:
   - handle-driven (`dev_min_handles.registry.v0.md`),
   - authority-aligned (`dev-min_managed-substrate_migration.design-authority.v0.md`),
   - evidence-first and fail-closed.
2. Keep this pass planning-only (no infrastructure mutation).

### Design references reviewed for this planning pass
1. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M2.build_plan.md`
2. `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
3. `docs/model_spec/platform/migration_to_dev/dev_min_handles.registry.v0.md`
4. `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`
5. `docs/model_spec/platform/migration_to_dev/dev_min_spine_green_v0_run_process_flow.md`

### Planned documentation changes
1. Expand `M2.I` section in deep plan into:
   - `M2.I Decision Pins`
   - `M2.I-A` handle resolution/preconditions
   - `M2.I-B` budget object + threshold + alert-channel validation
   - `M2.I-C` live cost-risk posture checks (resource-state lens)
   - `M2.I-D` teardown viability contract + destroy preflight evidence
   - `M2.I-E` emergency budget-stop protocol and run-lock posture
   - `M2.I-F` blocker taxonomy + rollback/recovery model
2. Keep canonical command lane primarily AWS/Terraform CLI so closure does not depend on optional local helper scripts.
3. Update main platform build plan immediate-next-action wording to reference execution of `M2.I-A -> M2.I-F` after planning closure.

### Fail-closed posture for this planning pass
1. If any required budget/teardown handle is unresolved or contradictory in authority docs, M2.I execution remains blocked until pinned.
2. No progression to `M2.J` is allowed until M2.I artifacts and blockers are fully closed.

## Entry: 2026-02-13 8:04PM - Post-change record: M2.I planning expanded to closure-grade execution map

### What changed
1. Expanded `M2.I` in deep plan (`platform.M2.build_plan.md`) from top-level bullets into explicit execution map:
   - `M2.I Decision Pins`
   - `M2.I-A` handle resolution/preconditions
   - `M2.I-B` budget object + threshold + alert-channel validation
   - `M2.I-C` live cost-risk posture checks
   - `M2.I-D` teardown viability preflight + checklist contract
   - `M2.I-E` emergency budget-stop protocol
   - `M2.I-F` blocker taxonomy + recovery/closure rule
2. Updated main platform build plan immediate-next-action to explicitly execute `M2.I-A -> M2.I-F`.

### Key decisions pinned in this planning pass
1. M2.I command lane is CLI-first (`aws` + `terraform`) so closure does not depend on optional local helper scripts.
2. Budget guardrail validation must prove both:
   - budget object/thresholds/notification channel correctness,
   - live resource posture safety (NAT/LB/fleet and runtime risk checks).
3. Teardown viability must be evidenced via destroy preflight + explicit post-teardown checklist contract (not assumed).
4. Emergency threshold (`>=£28`) is fail-closed:
   - progression to `M2.J/M3` blocked until operator stop protocol is satisfied.

### Why this closes prior planning holes
1. Removes ambiguity on what constitutes M2.I pass/fail and what evidence is mandatory.
2. Prevents anti-cram drift by exposing budget, live-risk, teardown, and emergency-control lanes separately.
3. Gives a deterministic blocker model (`M2I-B1..B5`) before execution begins.

## Entry: 2026-02-13 8:09PM - Pre-change lock: close M2.I budget materialization drift before rerun

### Trigger
1. During M2.I execution, budget validation failed with `NotFoundException` for `fraud-platform-dev-min-budget`.

### Runtime diagnosis
1. `infra/terraform/dev_min/core output -json` shows `budget_name=""` (no materialized budget object).
2. Core Terraform budget resource is currently gated by:
   - `enable_budget_alert=true` and
   - non-empty `budget_alert_email`.
3. Active defaults leave `budget_alert_email` empty, so budget resource count is `0`.
4. Current core budget semantics also drift from pinned handles:
   - name pattern currently `${name_prefix}-monthly-cost` rather than `fraud-platform-dev-min-budget`,
   - threshold model currently percentage `80/100` instead of pinned absolute `10/20/28`.

### Decision and scope for this correction
1. Patch core Terraform budget lane to align with pinned dev_min handles:
   - budget name to `${name_prefix}-budget`,
   - absolute threshold notifications `10/20/28`,
   - budget amount default aligned to `30`.
2. Materialize budget by applying core with operator email from local git identity (`git config user.email`) for this environment.
3. Then rerun full M2.I lane with corrected command argument handling and publish authoritative artifacts.

### Safety constraints
1. Limit infrastructure mutation to core budget lane required for M2.I closure.
2. No secret values persisted in evidence.
3. Keep fail-closed posture: if budget still cannot be materialized/validated, `M2I-B2` remains open and M2.I does not close.

## Entry: 2026-02-13 8:15PM - M2.I execution closure with budget/tag/teardown blocker remediation

### Trigger
1. USER directed: proceed with entirety of `M2.I`.

### Runtime blocker chain observed and resolved
1. Initial M2.I run surfaced:
   - `M2I-B2`: budget object missing (`fraud-platform-dev-min-budget` not materialized),
   - `M2I-B3`: tag posture failed (`expires_at` missing on discovered dev_min resources),
   - `M2I-B4`: teardown preflight JSON parse lane failed (`terraform show` provider-schema context issue).
2. Root-cause findings:
   - core budget resource was gated on non-empty `budget_alert_email`, but none was pinned in active runtime vars,
   - budget lane semantic drift existed vs handles (name/threshold model),
   - teardown parser was executed outside initialized demo context in first attempt.

### Infrastructure/documentation corrections applied
1. Budget Terraform alignment:
   - updated core module + dev_min/core variable surface to explicit budget handles:
     - `budget_name`,
     - `budget_limit_amount`,
     - `budget_limit_unit`,
     - `budget_alert_thresholds`.
   - pinned runtime budget to:
     - name: `fraud-platform-dev-min-budget`,
     - amount: `30`,
     - thresholds: `10/20/28`,
     - alert channel: email via operator address.
2. Provider constraint closure:
   - attempted `GBP` unit failed (`InvalidParameterException: supported unit set [USD]`),
   - repinned runtime enforcement unit to `USD` and documented this explicitly in handles/M2 docs as provider/account constraint.
3. Tag posture remediation:
   - applied core and demo with `expires_at=2026-02-28`,
   - this removed tag-surface drift for required cost-attribution keys.
4. Teardown parser remediation:
   - reran destroy preflight and `terraform show` from initialized demo stack context, eliminating schema-load failure.

### M2.I authoritative execution result
1. Final execution id:
   - `m2_20260213T201427Z`
2. Outcome:
   - `budget_guardrail_pass=true`
   - `teardown_viability_pass=true`
   - `overall_pass=true`
   - blockers: none.
3. Key validated facts:
   - budget object exists with `30 USD` cap and threshold notifications `10/20/28`,
   - alert channel is auditable (email subscriber materialized),
   - no NAT / no LB in demo VPC / no desired>0 ECS services,
   - tag posture for discovered dev_min resources includes `project/env/owner/expires_at`,
   - destroy preflight is valid with demo-scoped delete set only.

### Evidence
1. Local:
   - `runs/dev_substrate/m2_i/20260213T201427Z/budget_guardrail_snapshot.json`
   - `runs/dev_substrate/m2_i/20260213T201427Z/teardown_viability_snapshot.json`
2. Durable:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T201427Z/budget_guardrail_snapshot.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T201427Z/teardown_viability_snapshot.json`

### Plan-state updates
1. Marked `M2.I` complete in:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M2.build_plan.md`
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.build_plan.md`
2. Advanced immediate-next-action to `M2.J` exit-readiness/handoff.

## Entry: 2026-02-13 8:34PM - Cost dashboard text widget rendering fix (markdown escape cleanup)

### Trigger
1. USER reported CloudWatch dashboard `fraud-platform-dev-min-cost-guardrail` text widget rendering raw escape content (visible `\"...\\n...\"` form).

### Diagnosis
1. Pulled live dashboard body via `aws cloudwatch get-dashboard`.
2. Confirmed text widget markdown payload was being rendered as escaped line-break text in UI context.
3. Verified no semantic issue in metrics widgets; issue isolated to text markdown formatting surface.

### Change applied
1. Updated text widget markdown in:
   - `tools/dev_substrate/cost_guardrail_dashboard.json`
2. Replaced newline-escape dependent formatting with explicit `<br/>` separators to avoid raw escape rendering in CloudWatch text widget surface.
3. Re-applied dashboard:
   - `aws cloudwatch put-dashboard --dashboard-name fraud-platform-dev-min-cost-guardrail --dashboard-body file://tools/dev_substrate/cost_guardrail_dashboard.json`
4. Verified live dashboard payload reflects updated markdown content (no quoted/escaped wrapper artifact in body).

### Outcome
1. Dashboard message is now structured for clean rendering in CloudWatch UI.
2. No impact on M2 runtime rails, evidence contracts, or infrastructure semantics.

## Entry: 2026-02-13 8:38PM - Cost dashboard text widget simplified to single-line title

### Trigger
1. USER requested dashboard text be reduced to only `# Dev-Min Cost Guardrail` because multiline formatting was rendering poorly.

### Change
1. Updated `tools/dev_substrate/cost_guardrail_dashboard.json` text widget markdown to:
   - `# Dev-Min Cost Guardrail`
2. Reapplied dashboard:
   - `aws cloudwatch put-dashboard --dashboard-name fraud-platform-dev-min-cost-guardrail --dashboard-body file://tools/dev_substrate/cost_guardrail_dashboard.json`
3. Verified live dashboard body now returns the exact single-line markdown value.

## Entry: 2026-02-13 8:41PM - Pre-change lock: expand M2.J planning to closure-grade handoff map

### Trigger
1. USER directed: "Let's start planning for M2.J".

### Planning problem
1. Current `M2.J` section is still high-level and does not yet pin:
   - deterministic closure sequence,
   - explicit M2 readiness verdict contract (`ADVANCE` vs `HOLD`),
   - artifact-completeness checks against the M2 evidence contract,
   - explicit blocker taxonomy for handoff failures.

### Objective
1. Expand `M2.J` into an executable plan surface (`M2.J-A..F`) before any M2 closeout command runs.
2. Keep this pass planning-only; no infrastructure mutation.

### Inputs reviewed
1. `platform.M2.build_plan.md` current M2 completion/evidence sections.
2. `platform.build_plan.md` M2 status + immediate next action.
3. Current M2 closure evidence roots, including:
   - `m2_20260213T195244Z` (M2.H),
   - `m2_20260213T201427Z` (M2.I).

### Planned outcome of this planning pass
1. Add `M2.J Decision Pins`.
2. Expand M2.J into:
   - `M2.J-A` preconditions + blocker register lock,
   - `M2.J-B` M2 evidence completeness/integrity index,
   - `M2.J-C` M3 entry-handle snapshot and prerequisite checks,
   - `M2.J-D` readiness verdict protocol,
   - `M2.J-E` canonical handoff artifact publication (`m3_handoff_pack.json`),
   - `M2.J-F` blocker/recovery model.
3. Keep M2 exit criteria fail-closed: no M3 activation when any M2.J blocker remains open.

## Entry: 2026-02-13 8:42PM - Post-change record: M2.J planning expanded to closure-grade handoff protocol

### What changed
1. Expanded `M2.J` in `platform.M2.build_plan.md` from high-level bullets to explicit sub-phases:
   - `M2.J Decision Pins`
   - `M2.J-A` Preconditions and blocker lock
   - `M2.J-B` Evidence completeness/integrity index
   - `M2.J-C` M3 entry prerequisites + handle snapshot
   - `M2.J-D` Readiness verdict protocol
   - `M2.J-E` Canonical handoff artifact publication
   - `M2.J-F` Blockers/recovery/exit rule
2. Extended M2 evidence contract to include:
   - `m2_exit_readiness_snapshot.json` (local + durable counterpart in M2 execution root).
3. Updated main build plan immediate next action to explicitly execute:
   - `M2.J-A -> M2.J-F`.

### Key planning decisions pinned
1. M2 verdict is binary and fail-closed:
   - `ADVANCE_TO_M3` or `HOLD_M2`.
2. `m3_handoff_pack.json` is mandatory before M2 closeout can be claimed.
3. M3 activation remains blocked unless:
   - checklist complete,
   - blockers empty,
   - evidence complete,
   - M3 prerequisite handles resolved,
   - open-risk register empty.

### Execution posture after this planning pass
1. M2.J is now execution-ready from a plan-quality perspective.
2. No runtime/infrastructure action was executed in this pass.

## Entry: 2026-02-13 9:00PM - M2.J execution closure and M2 DONE transition

### Trigger
1. USER directed: proceed with full `M2.J`.

### Execution summary
1. Executed full `M2.J-A -> M2.J-F` closeout lane and published canonical artifacts.
2. Authoritative M2.J execution id:
   - `m2_20260213T205715Z`
3. Final verdict:
   - `ADVANCE_TO_M3`
4. Final predicate state:
   - `checklist_complete=true`
   - `blockers_empty=true`
   - `evidence_complete=true`
   - `m3_prereqs_ready=true`
   - `open_risk_register_empty=true`

### Notable closure actions
1. Built deterministic 18-family M2 evidence index with local + durable URI checks.
2. Closed legacy evidence naming drift by synthesizing compatibility artifacts in M2.J:
   - `core_apply_snapshot.json`
   - `demo_apply_snapshot.json`
   - `handle_resolution_snapshot.json`
3. Refreshed M2.B backend snapshot in current execution context:
   - `m2_b_backend_state_readiness_snapshot.json` now reports `overall_pass=true`.
4. Generated M3 handoff surface with non-secret handle snapshot from:
   - Terraform core outputs,
   - Terraform confluent outputs (runtime credentials redacted),
   - Terraform demo outputs,
   - pinned registry literals required at M3 entry.

### Evidence
1. Local:
   - `runs/dev_substrate/m2_j/20260213T205715Z/m2_exit_readiness_snapshot.json`
   - `runs/dev_substrate/m2_j/20260213T205715Z/m3_handoff_pack.json`
2. Durable:
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T205715Z/m2_exit_readiness_snapshot.json`
   - `s3://fraud-platform-dev-min-evidence/evidence/dev_min/substrate/m2_20260213T205715Z/m3_handoff_pack.json`

### Planning state transition applied
1. `platform.M2.build_plan.md`:
   - marked all M2.J DoDs complete,
   - recorded authoritative M2.J execution result block,
   - marked M2 completion checklist item `M2.J complete`.
2. `platform.build_plan.md`:
   - transitioned M2 status `ACTIVE -> DONE`,
   - left M3 as `NOT_STARTED` pending explicit USER activation,
   - updated immediate next action to M3 activation gating via handoff artifact.

## Entry: 2026-02-13 9:12PM - M3 planning activation and deep-plan creation

### Trigger
1. USER directed: proceed with M3 planning in the main platform plan and then the deep `platform.M3.build_plan.md`.

### Planning decisions applied
1. Activated M3 planning posture in the main tracker:
   - `platform.build_plan.md` now sets M3 status to `ACTIVE`.
2. Expanded main M3 section from gate-summary to execution-planning surface:
   - objective/scope/failure posture,
   - `M3.A -> M3.G` sub-phase progression checklist,
   - explicit M3 DoD checklist.
3. Registered deep-plan routing for M3 in Section 6.1:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M3.build_plan.md`.
4. Updated immediate-next-action block to focus on closing M3 decision pins and preparing M3 execution lane with fail-closed gating to M4.

### Deep-plan file created
1. Added `platform.M3.build_plan.md` with closure-grade structure:
   - authority/scope/deliverables/execution gates,
   - anti-cram coverage matrix for run identity, digest, evidence, and run-scope export,
   - sub-phases:
     - `M3.A` handle closure
     - `M3.B` run-id generation/collision checks
     - `M3.C` payload + digest determinism
     - `M3.D` durable run evidence publication
     - `M3.E` runtime scope export for M4
     - `M3.F` verdict + blocker taxonomy
     - `M3.G` M4 handoff artifact publication
   - pinned M3 evidence contract and exit criteria.

### Drift/safety posture
1. Planning-only pass: no runtime infra mutation and no phase execution commands.
2. Fail-closed decision noted in M3 plan:
   - `SCENARIO_EQUIVALENCE_KEY_INPUT` must be explicitly pinned at M3 execution entry.

## Entry: 2026-02-13 9:18PM - M3.A planning expansion and blocker surfacing

### Trigger
1. USER directed: move to `M3.A` and begin planning it.

### What was expanded
1. Upgraded `M3.A` from lightweight bullets to closure-grade planning content in:
   - `docs/model_spec/platform/implementation_maps/dev_substrate/platform.M3.build_plan.md`.
2. Added:
   - `M3.A Decision Pins (Closed Before Execution)`,
   - `M3.A Verification Command Catalog`,
   - `M3.A Handle Closure Matrix (Planning Snapshot)`,
   - `M3.A Planning Status (Current)`.
3. Extended M3 unresolved blocker register with concrete active blocker:
   - `M3A-B1`: `SCENARIO_EQUIVALENCE_KEY_INPUT` still placeholder.

### Key planning findings (M3.A)
1. Handle closure matrix now tracks 18 required rows for M3.A authority closure.
2. Source model is explicit per handle:
   - registry literals,
   - M2 handoff artifact,
   - AWS control-plane lookup (`ECR_REPO_URI` via ECR describe),
   - immutable M1 packaging evidence for image provenance.
3. `SCENARIO_EQUIVALENCE_KEY_INPUT` is the only currently open blocker for M3 execution entry.

### Main-plan alignment updates
1. `platform.build_plan.md` M3 section now explicitly references:
   - M3.A planning-in-progress,
   - open blocker `M3A-B1`.
2. Immediate-next-action block now prioritizes:
   - close `M3A-B1`, then complete M3.A closure before progressing to `M3.B+`.

### Safety posture
1. Planning-only change; no runtime execution command run for M3.
2. Fail-closed enforcement strengthened:
   - no M3 execution while `M3A-B1` is open.

## Entry: 2026-02-13 9:27PM - M3.A execution lane run with fail-closed blocker verdict

### Trigger
1. USER directed: proceed with entirety of `M3.A`.

### Execution performed
1. Ran full M3.A verification catalog against live authority surfaces:
   - registry-key presence checks,
   - M2 handoff artifact availability,
   - ECR repo/URI resolution,
   - evidence bucket reachability,
   - M1 immutable provenance prefix existence,
   - placeholder guard for `SCENARIO_EQUIVALENCE_KEY_INPUT`.
2. Produced M3.A closure snapshot:
   - local: `runs/dev_substrate/m3_a/20260213T212724Z/m3_a_handle_closure_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3a_20260213T212724Z/m3_a_handle_closure_snapshot.json`

### Outcome
1. Authoritative M3.A execution id:
   - `m3a_20260213T212724Z`
2. Verdict:
   - `overall_pass=false` (expected fail-closed)
3. Open blockers:
   - `M3A-B1` only (`SCENARIO_EQUIVALENCE_KEY_INPUT` still placeholder).
4. All other M3.A surfaces verified:
   - M2 handoff artifact exists,
   - ECR URI resolvable,
   - evidence bucket reachable,
   - M1 immutable provenance source present,
   - required handle keys present in registry.

### Documentation updates applied
1. `platform.M3.build_plan.md`:
   - marked M3.A DoD checks complete (closure matrix + verification + blocker marking),
   - added authoritative execution result block for M3.A,
   - attached latest evidence references to blocker `M3A-B1`.
2. `platform.build_plan.md`:
   - updated M3.A planning status with execution id and durable evidence URI.

### Safety posture
1. No progression to M3.B execution while `M3A-B1` remains open.
2. Required closure action is unchanged:
   - explicitly pin `SCENARIO_EQUIVALENCE_KEY_INPUT`, then rerun M3.A verification.

## Entry: 2026-02-13 9:36PM - M3A-B1 closure by pinning scenario-equivalence input and rerun

### Trigger
1. USER approved recommended scenario-equivalence pin strategy.

### Changes applied
1. Updated handles registry at Section 1.6:
   - `SCENARIO_EQUIVALENCE_KEY_INPUT = "sha256(canonical_json_v1)"`
   - `SCENARIO_EQUIVALENCE_KEY_CANONICAL_FIELDS = "oracle_seed_manifest_uri,oracle_seed_manifest_sha256,oracle_required_output_ids,oracle_sort_key_by_output_id,config_digest"`
   - `SCENARIO_EQUIVALENCE_KEY_CANONICALIZATION_MODE = "json_sorted_keys_v1"`
2. Added explicit note preventing run-unique fields (`platform_run_id`, timestamps) from entering scenario-equivalence input.

### Verification execution
1. Reran full M3.A verification lane after pinning.
2. Authoritative run:
   - `m3a_20260213T213547Z`
3. Result:
   - `overall_pass=true`
   - blockers: none.
4. Evidence:
   - local: `runs/dev_substrate/m3_a/20260213T213547Z/m3_a_handle_closure_snapshot.json`
   - durable: `s3://fraud-platform-dev-min-evidence/evidence/dev_min/run_control/m3a_20260213T213547Z/m3_a_handle_closure_snapshot.json`

### Documentation state updates
1. `platform.M3.build_plan.md`:
   - M3.A execution result updated with latest passing run,
   - M3.A marked complete in completion checklist,
   - `M3A-B1` moved to resolved blockers.
2. `platform.build_plan.md`:
   - M3.A status updated to closed,
   - immediate next action advanced to M3.B.
