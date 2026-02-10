# Platform Build Plan (dev_substrate)
_As of 2026-02-10_

## Purpose
Execute a controlled migration from `local_parity` to `dev_min` managed substrate while preserving platform laws, ownership boundaries, and designed event flow.

## Scope and posture
- `local_parity` remains the semantic baseline and fallback harness.
- `dev_min` is the managed-substrate proof rung (Confluent Kafka + AWS S3 evidence posture).
- Migration is adapter/wiring and operational posture change, not component-logic redesign.
- No plane is accepted if run/operate and obs/gov are partial for onboarded services.

## Non-negotiable rails
- No semantic drift: dedupe tuple + payload hash anomaly semantics, append-only truths, origin offsets, explicit degrade, provenance pins.
- No ownership drift: SR/IG/EB/Engine/DLA/LS/Registry/AL boundaries remain intact.
- Fail closed on unknown compatibility or missing evidence.
- At-least-once safety and idempotency remain mandatory.
- Drift sentinel law applies at each substantial step and after every full run.

## Phase 0 - Mobilization and semantic freeze
### Objective
Start migration from authoritative sources only, without duplicative planning artifacts.

### Work sections
1. Lock pre-design authorities
- Use pinned migration authority and platform pre-design decisions as the controlling design intent.
- Confirm run/operate and obs/gov meta-layer decisions are part of migration scope from day one.

2. Lock local-parity baseline history
- Use local-parity platform/component implementation maps as baseline decision history and known closure posture.
- Use local-parity runbook as operational reference for rails and acceptance sequencing (`20 -> 200`).

3. Lock phase progression posture
- Keep gate posture in this build plan and implementation notes/logbook entries.
- Avoid standalone phase artifacts unless explicitly requested by USER.

### Definition of Done
- [x] Pre-design authority set for migration is locked and referenced.
  - Evidence: `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`
  - Evidence: `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
  - Evidence: `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`
- [x] Local-parity implementation history is the pinned baseline reference.
  - Evidence: `docs/model_spec/platform/implementation_maps/local_parity/platform.build_plan.md`
  - Evidence: `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md`
- [x] Local-parity operational runbook is pinned as execution reference.
  - Evidence: `docs/runbooks/platform_parity_walkthrough_v0.md`

### Phase status
- Phase 0 is closed as of `2026-02-10` with authority + baseline references pinned (no auxiliary phase documents).

## Phase 1 - Accounts, credentials, and secret bootstrap
### Objective
Stand up secure operator-ready access for AWS + Confluent without embedding secrets in repo.

### Authority anchors
- `docs/model_spec/platform/pre-design_decisions/dev-min_managed-substrate_migration.design-authority.v0.md`
- `docs/model_spec/platform/pre-design_decisions/run_and_operate.pre-design_decisions.md`
- `docs/model_spec/platform/pre-design_decisions/observability_and_governance.pre-design_decisions.md`
- `docs/model_spec/platform/implementation_maps/local_parity/platform.impl_actual.md`

### Work sections
1. Phase 1.A - Account and tenancy bootstrap
- Pin AWS account id, region, and billing owner for `dev_min`.
- Pin Confluent organization/environment/cluster ownership and operating region.
- Pin resource naming and cost-tag schema (`project`, `env`, `owner`, `expires_at`) for all provisioned resources.
- Confirm budget alert ownership path and escalation destination.
- Pinned execution snapshot (2026-02-10):
  - AWS account: `230372904534`
  - AWS principal: `arn:aws:iam::230372904534:user/fraud-dev`
  - AWS region: `eu-west-2`
  - Terraform state bucket visibility check: `tfstate-esosaorumwese808-fraud` readable.

2. Phase 1.B - Principal and permission model
- Define operator principal set (human operator, automation principal, optional break-glass principal).
- Pin least-privilege boundaries per substrate:
  - AWS: S3 prefixes, Parameter Store paths, Terraform state access, budget/readonly billing visibility.
  - Confluent: cluster/topic admin for setup, runtime producer/consumer ACL scopes.
- Pin deny-by-default posture for unknown principals and wildcard credentials.
- Pinned phase-1 principal set:
  - Human operator: AWS IAM user `fraud-dev` (current active principal).
  - Automation principal: to be created in Phase 2 Terraform lane (non-human, least privilege).
  - Break-glass principal: deferred but required before dev_full promotion.

3. Phase 1.C - Secret taxonomy and source of truth
- Pin secret classes:
  - cloud auth/session material,
  - Kafka bootstrap + API key/secret,
  - data-store DSNs and service tokens.
- Pin source-of-truth paths and naming conventions for each class.
- Pin runtime injection contract (env var keys and process boundaries) without storing secret values in repo.
- Pinned handle map (`dev_min`):
  - `/fraud-platform/dev_min/confluent/bootstrap`
  - `/fraud-platform/dev_min/confluent/api_key`
  - `/fraud-platform/dev_min/confluent/api_secret`
- Pinned runtime env keys (from `config/platform/profiles/dev_min.yaml`):
  - `DEV_MIN_KAFKA_BOOTSTRAP`
  - `DEV_MIN_KAFKA_API_KEY`
  - `DEV_MIN_KAFKA_API_SECRET`
  - `DEV_MIN_OBJECT_STORE_BUCKET`
  - `DEV_MIN_EVIDENCE_BUCKET`
  - `DEV_MIN_QUARANTINE_BUCKET`
  - `DEV_MIN_ARCHIVE_BUCKET`
  - `DEV_MIN_AWS_REGION`
- Dedicated operator env surface for Phase 1 commands:
  - runtime file: `.env.dev_min` (untracked),
  - template: `.env.dev_min.example` (tracked),
  - override handle: `DEV_MIN_ENV_FILE` for alternate file paths.

4. Phase 1.D - Operator bootstrap and preflight gate
- Define deterministic bootstrap sequence for a fresh shell session:
  - authenticate to AWS and Confluent,
  - load `DEV_MIN_ENV_FILE` (default `.env.dev_min`) for Phase 1 command execution,
  - resolve required secret handles,
  - materialize runtime env for operator commands.
- Define mandatory preflight checks:
  - caller identity and account/region match,
  - secret-handle presence and version freshness,
  - Kafka auth and topic metadata read check,
  - S3 prefix read/write probe for expected evidence roots.
- Pin fail-closed rule: any failed preflight blocks phase advancement and phase-2 execution.
- Implemented preflight tooling:
  - `scripts/dev_substrate/phase1_preflight.ps1`
  - `make platform-dev-min-phase1-preflight`
- Implemented SSM seed helper:
  - `scripts/dev_substrate/phase1_seed_ssm.ps1`
  - `make platform-dev-min-phase1-seed-ssm`

5. Phase 1.E - Security hygiene and leak prevention
- Enforce no-secret-in-repo posture for `.env`, logs, notes, and implementation maps.
- Pin redaction posture for command output copied into logbook/implementation notes.
- Pin routine credential hygiene steps (rotation awareness, stale-session invalidation, revoke path).
- Implemented hygiene preflight checks:
  - fail if `.env*` files are git-tracked,
  - do not print secret values; record handles and pass/fail only.

6. Phase 1.F - Failure and recovery drills
- Execute and document at least one controlled failure drill for each class:
  - expired/invalid AWS session,
  - revoked/rotated Confluent key,
  - missing/incorrect secret handle.
- Verify operator guidance leads to deterministic recovery without manual console drift.
- Record fail signatures and recovery steps in logbook for runbook carry-forward.
- Executed drill set (2026-02-10):
  - invalid AWS auth context (`AWS_PROFILE=__missing_profile__`) -> `FAIL_CLOSED` as expected,
  - missing required SSM handles (`/fraud-platform/dev_min/...`) -> `FAIL_CLOSED` as expected,
  - invalid Confluent credentials under isolated drill prefix (`/fraud-platform/dev_min_drill/...`) -> API auth probe `FAIL_CLOSED` as expected.

### Definition of Done
- [x] Account/tenancy ownership and region posture are pinned for AWS + Confluent.
- [x] Principal model and least-privilege boundaries are pinned and auditable.
- [x] Secret taxonomy, source-of-truth path map, and runtime injection contract are pinned.
- [x] Fresh-shell operator bootstrap succeeds end-to-end without manual hidden steps.
- [ ] Preflight suite passes (identity, secret handles, Kafka auth/metadata, S3 prefix probe).
  - Blocker: production `dev_min` Confluent handles under `/fraud-platform/dev_min/confluent/*` are not yet provisioned.
- [x] Failure drills (auth/session/secret) are executed and recovery steps are logged.
- [x] Secret-leak hygiene checks pass (`git` and notes/logbook remain secret-free).
- [x] Closure evidence is recorded in `dev_substrate/platform.impl_actual.md` and `docs/logbook` with sanitized outputs only.

### Phase status
- Phase 1 is **in progress**: sections `1.A` through `1.F` are implemented; final closure is blocked only on provisioning real Confluent handles and rerunning strict preflight to full PASS.

## Phase 2 - Landing zone and Terraform substrate
### Objective
Provision and control `dev_min` infrastructure with reproducible up/down posture and budget guardrails.

### Work sections
1. Core versus demo split
- Implement `core` persistent resources (state, buckets/prefixes, minimal control tables, budget alarms).
- Implement `demo` ephemeral resources (Kafka/topic provisioning and optional demo compute surfaces).

2. Cost and teardown guardrails
- Enforce no-NAT, no always-on LB, no always-on compute fleet.
- Enforce destroy-by-default path and post-destroy verification.

3. Operator entrypoints
- Provide deterministic up/down/report commands for infra lifecycle.

### Definition of Done
- [ ] `up` and `down` are idempotent.
- [ ] Post-destroy check confirms only allowed core resources remain.
- [ ] Budget alerts and tagging policy are active.

## Phase 3 - Wave 1 migration: Control and Ingress
### Objective
Migrate SR/WSP/IG/EB control path to managed substrate and prove stable event admission flow.

### Work sections
1. Bus and topic wiring cutover
- Route control and ingress topics to managed Kafka under pinned topic map.
- Keep partitioning and event-class semantics unchanged.

2. Oracle and evidence path
- Route run evidence outputs to S3 prefixes.
- Preserve PASS-gate/no-pass-no-read behavior.

3. Wave validation
- Execute component matrix, then integrated 20-event and 200-event runs.

### Definition of Done
- [ ] SR/WSP/IG/EB matrix is green on `dev_min` wiring.
- [ ] 20-event and 200-event runs pass for Wave 1 scope.
- [ ] Drift audit confirms no C&I semantic or ownership drift.

## Phase 4 - Wave 2 migration: RTDL plane
### Objective
Migrate RTDL services to managed substrate while preserving decision-lane contracts and replay evidence basis.

### Work sections
1. Projection and join services
- Onboard IEG/OFP/CSFB to managed bus/evidence substrate.

2. Decision lane services
- Onboard DF/DL/AL/DLA with deterministic context resolution and append-only audit posture.

3. Wave validation
- Run component matrices and integrated flow tests with decision-lane coverage.

### Definition of Done
- [ ] RTDL service matrix is green.
- [ ] Decision lane stays live (not matrix-only) in integrated runs.
- [ ] Replay anchors and audit evidence are complete and consistent.

## Phase 5 - Wave 3 migration: Case and Label plane
### Objective
Migrate CaseTrigger/CM/LS to managed substrate and keep timeline/label truth contracts intact.

### Work sections
1. Trigger and case flow wiring
- Onboard case trigger topics and CM processing path on managed bus.

2. Label truth path
- Onboard label store emission/append semantics and evidence export.

3. Wave validation
- Validate case/label service matrices and integrated run behavior with prior waves.

### Definition of Done
- [ ] CaseTrigger, CM, and LS matrices are green.
- [ ] Case timelines and label assertions remain append-only and replayable.
- [ ] Integrated runs show case/label participation under run/operate orchestration.

## Phase 6 - Wave 4 migration: Learning and Registry plane
### Objective
Migrate OFS/MF/Registry-facing path needed for `dev_min` proof without over-expanding into dev_full.

### Work sections
1. Archive and dataset path
- Ensure archive writer and dataset-manifest path are wired to S3 evidence/archive posture.

2. OFS and MF operational path
- Onboard OFS/MF runtime wiring and request corridor under `dev_min` profile.

3. Registry interactions
- Preserve deterministic bundle resolution interfaces and lifecycle evidence events.

### Definition of Done
- [ ] OFS/MF matrices are green for `dev_min` scope.
- [ ] Learning-plane evidence artifacts are emitted and indexed.
- [ ] Registry-facing contracts remain deterministic and replay-safe.

## Phase 7 - Meta-layer saturation (all onboarded services)
### Objective
Guarantee run/operate and obs/gov cover every migrated service end-to-end.

### Work sections
1. Run/operate pack coverage
- Ensure every service is present in orchestrated packs with health/startup/teardown behavior.

2. Observability and governance emissions
- Ensure lifecycle, anomalies, reconciliation, and run reporter outputs are emitted and persisted.

3. Schema and evidence conformance
- Validate emitted evidence against existing platform contract families (IG receipts, RTDL audit/offset basis, archive records, learning dataset manifests) and run-scoped reporter outputs.

### Definition of Done
- [ ] No onboarded service is orphaned from orchestration.
- [ ] No onboarded service is orphaned from obs/gov emissions.
- [ ] Evidence bundle contract checks pass for migrated waves.

## Phase 8 - Integrated validation and cutover readiness
### Objective
Close migration with full-run proof, drift audit, and operational handoff readiness.

### Work sections
1. Full-platform validation
- Run full 20-event and 200-event `dev_min` live-stream validation.
- Capture component matrix, flow narrative proof, and replay/evidence checks.

2. Drift sentinel audit
- Compare runtime graph to flow narrative and pinned decisions.
- Escalate and close any detected mismatch before acceptance.

3. Operational closure
- Update runbook and logbook with final commands, known limits, and rollback posture.

### Definition of Done
- [ ] Full-platform 20-event run green.
- [ ] Full-platform 200-event run green.
- [ ] Drift audit confirms no silent mismatch.
- [ ] Runbook and implementation notes are current and auditable.

## Deferred backlog (post-acceptance)
- Step Functions orchestration (dev_full upgrade path).
- Managed Redis/Postgres upgrades where currently optional.
- Performance optimization beyond migration acceptance baseline.
- Additional cost automation beyond v0 manual hard-stop protocol.

## Execution rule
Do not start the next phase until the current phase DoD is fully closed and recorded in:
- `docs/model_spec/platform/implementation_maps/dev_substrate/platform.impl_actual.md`
- `docs/logbook/<month>/<date>.md`
