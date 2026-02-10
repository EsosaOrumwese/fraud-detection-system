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
