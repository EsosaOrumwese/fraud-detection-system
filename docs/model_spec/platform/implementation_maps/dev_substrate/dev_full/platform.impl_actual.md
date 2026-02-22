# Platform Implementation Map (dev_substrate/dev_full)
_As of 2026-02-22_

## Entry: 2026-02-22 17:02 +00:00 - Initialize dev_full implementation-map track

### Context
1. `dev_substrate` map hierarchy has been split into `dev_min` and `dev_full` tracks.
2. `dev_min` is closed at certification boundary and should not be mixed with `dev_full` planning/execution.
3. This file initializes the `dev_full` decision trail as the active map for full-platform extension work.

### Decision
1. Use `docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/` as the sole path for active dev_full implementation notes.
2. Keep `dev_min` docs immutable except explicit archival corrections.

### Result
1. dev_full track is now explicitly initialized for append-only planning and execution decisions.

## Entry: 2026-02-22 17:05 +00:00 - Create dev_full migration design authority v0 (sectional rewrite from dev_min structure)

### Problem
1. Existing migration design authority was dev_min-specific and insufficient for full-platform closure.
2. No active `dev_full` authority file existed after prior rollback.
3. Without a fresh authority document, implementation would drift across stack/tooling choices.

### Design approach
1. Preserve the dev_min authority section pattern (0..18) to keep audit continuity and operator familiarity.
2. Rewrite every section to dev_full scope and stack, not as copy-only text replacement.
3. Pin the agreed target stack in one place (Section 5) and align all downstream sections to it.
4. Add an explicit proof-law requiring deploy/monitor/fail/recover/rollback/cost-control artifacts by lane.
5. Leave unresolved items explicit in Decision Registry (`Section 17.2`) instead of defaulting silently.

### Applied changes
1. Created:
   - `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
2. Pinned dev_full stack and posture:
   - EKS, Confluent Cloud Kafka, S3, Aurora PostgreSQL, ElastiCache Redis,
   - Databricks (OFS), SageMaker (MF), MLflow,
   - Airflow (MWAA) + Step Functions orchestration split,
   - OTel observability, Terraform, GitHub Actions,
   - no laptop runtime compute.
3. Added explicit unresolved pin set in `Section 17.2` (cluster tier, Aurora topology, MLflow hosting mode, Airflow mode, Step Functions decomposition).

### Why this structure
1. It preserves continuity with dev_min authority while separating concerns cleanly for dev_full.
2. It is strict enough to stop implicit defaults and supports section-by-section pin closure.
3. It is directly mappable to upcoming runbook/handles rewrites.

### Immediate next step
1. Perform section-by-section USER pin closure on `Section 17.2` open decisions.
2. Then author the matching dev_full run-process authority and handles registry based on this document.

## Entry: 2026-02-22 17:18 +00:00 - Section-by-section pin closure executed for authority Section 5 / 17.2

### Trigger
1. USER instructed to proceed with section-by-section pin closure.
2. Authority had explicit unresolved set in `Section 17.2` that would block fail-closed execution planning.

### Decision strategy
1. Close all seven unresolved items in one bounded pass because they are tightly coupled and all sit in the stack/tooling boundary.
2. Pin values that are:
   - production-shaped enough for senior MLOps signaling,
   - still bounded for v0 operational cost/risk control,
   - directly mappable to future handles/run-process docs.
3. Avoid vague prose; add concrete values and named identifiers where possible.

### Pinned outcomes applied
1. Confluent posture pinned to `Standard` tier with explicit retention and partition defaults.
2. Aurora posture pinned to Serverless v2 Multi-AZ (`1 writer + >=1 reader`) with v0 ACU range.
3. Databricks policy pinned to job-clusters-only with autoscale/auto-terminate + cost guard fail-closed.
4. SageMaker serving pinned to realtime endpoint (active inference) + batch transform (offline lanes), with one primary endpoint in v0.
5. MLflow hosting pinned to Databricks managed mode.
6. Airflow pinned to MWAA managed deployment.
7. Step Functions split and failure taxonomy IDs pinned (three state-machine IDs + five blocker IDs).

### Files updated
1. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`
   - Added `Section 5.1.1` with concrete closure values.
   - Converted `Section 17.2` from open set to closure index referencing `Section 5.1.1`.

### Result
1. Initial dev_full authority ambiguity in Section 17.2 is closed for v0 planning.
2. Next dependency is to propagate these pins into:
   - dev_full handles registry authority,
   - dev_full run-process authority,
   - dev_full build-plan sequencing.

## Entry: 2026-02-22 17:32 +00:00 - Authority hardening pass: MSK repin + closure of remaining ambiguity sets

### Trigger
1. USER requested final pin closure of remaining vagueness and raised explicit Event Bus direction toward AWS MSK.

### Drift concern detected
1. Current authority still had execution-risk ambiguity in five areas:
   - budget numbers,
   - topic contract table,
   - thresholded acceptance gates,
   - concrete retention tiers,
   - concrete IaC/state/security handle surfaces.
2. Stack was pinned to Confluent in dev_full despite USER push toward AWS-native bus posture.

### Decision
1. Repin `dev_full` Event Bus primary from Confluent to **AWS MSK Serverless** for stack coherence and AWS-heavy senior-signal alignment.
2. Close the five ambiguity sets in the same bounded patch so authority becomes execution-grade and less interpretive.

### Applied authority updates
1. Event bus repin:
   - primary stack line changed to AWS MSK.
   - sectional closure item updated from Confluent tier to MSK serverless profile (`SASL_IAM`, region, partitions, retention).
2. Cost posture now includes explicit monthly cap + alert thresholds.
3. IaC/state/security surfaces now include concrete tf-state handles, role handles, and secret-path contracts.
4. Retention policy now includes concrete day values by artifact class.
5. Acceptance gates now include explicit gate requirements (stack apply/destroy, critical semantic checks, lane proof obligations, learning corridor drills, spine non-regression list).
6. Appendix C now contains a concrete dev_full topic contract table (spine + learning-control topics).

### Files updated
1. `docs/model_spec/platform/pre-design_decisions/dev-full_managed-substrate_migration.design-authority.v0.md`

### Result
1. Authority doc moved from strong draft to execution-grade pin set for v0 planning.
2. Event bus posture is now aligned with USER direction (MSK).

## Entry: 2026-02-22 17:37 +00:00 - Dev-full run-process hardening plan (pre-edit)

### Trigger
1. USER requested moving to the `run_process` flow after completion of dev_full design-authority pin closures.
2. Existing `dev_full_platform_green_v0_run_process_flow.md` exists but is still high-level and not yet closure-grade for execution.

### Problem framing
1. Current run-process file captures phase names and broad intent but does not yet fully encode fail-closed execution semantics, entry/exit gate rigor, evidence contracts, and blocker taxonomy at the level needed for implementation with low interpretation drift.
2. The run-process must inherit spine semantics from dev_min/local-parity while extending to learning/evolution without silently changing existing truths.
3. We must avoid introducing contradictions with newly pinned dev_full authority decisions (notably AWS MSK Serverless, orchestration split, budget thresholds, and proof-law obligations).

### Alternatives considered
1. Minimal patch of only stack names and a few phase notes.
   - Rejected: too weak; would leave interpretation holes and future drift risk.
2. Full rewrite from scratch independent of dev_min structure.
   - Rejected: higher risk of semantic drift on spine phases `P0..P11`.
3. Controlled hardening pass preserving current phase scaffold (`P(-1), P0..P17`) while deepening gates/evidence/blockers and explicitly linking to authority pins.
   - Selected: best balance of continuity + closure rigor.

### Planned edits
1. Rewrite `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` into an execution-grade authority runbook with:
   - explicit authority boundaries and non-negotiables,
   - pinned dev_full stack/tooling profile aligned with design authority,
   - canonical gate/evidence contract,
   - phase-by-phase entry gate, PASS gate, commit evidence, and blocker codes,
   - rerun/reset matrix and final verdict rule,
   - drift watchlist and mandatory companion docs.
2. Update `docs/model_spec/platform/migration_to_dev/README.md` to index dev_full run-process authority explicitly.
3. Append outcome and rationale to this implementation map and logbook after patching.

### Guardrails for this edit
1. Preserve spine semantic inheritance from dev_min/local-parity.
2. Keep `P#` IDs canonical and unchanged.
3. Keep no-laptop-runtime posture explicit.
4. Keep unresolved dependency explicit where appropriate (`dev_full_handles.registry.v0.md` required before execution).

## Entry: 2026-02-22 17:45 +00:00 - Dev-full run-process authority hardened and aligned to pinned stack

### What was implemented
1. Reworked `docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md` from high-level draft into execution-grade run-process authority.
2. Updated `docs/model_spec/platform/migration_to_dev/README.md` to index both authority tracks (`dev_min` and `dev_full`) and clarify process-flow + handles-registry pairing.

### Key hardening outcomes in run-process doc
1. Preserved canonical phase structure `P(-1), P0..P17` and explicit inheritance of spine semantics from dev_min/local-parity.
2. Aligned substrate/tooling posture to current dev_full pins:
   - EKS, AWS MSK Serverless, S3, Aurora PostgreSQL Serverless v2, Redis,
   - Databricks, SageMaker, Databricks-managed MLflow,
   - Step Functions + MWAA split,
   - Terraform + GitHub Actions,
   - OTel + CloudWatch.
3. Added explicit phase-level contracts for every phase:
   - entry gate,
   - PASS gate,
   - commit evidence,
   - blocker IDs.
4. Added explicit rerun/reset law and stop-the-line conditions to enforce fail-closed behavior.
5. Added explicit dependency gate that execution is blocked until `dev_full_handles.registry.v0.md` exists and is pinned.
6. Added summary appendices for topic set continuity and mandatory six-proof publication rule.

### Why this resolves the immediate request
1. USER requested moving to run-process flow given newly pinned design authority.
2. The previous run-process was structurally present but too broad; this patch closes interpretation gaps before implementation planning/execution.
3. The updated run-process is now a practical authority bridge from pinned design decisions to phase-executable migration work.

### Remaining dependency (explicit, not hidden)
1. `dev_full_handles.registry.v0.md` is still required and currently absent.
2. This is intentionally surfaced as a hard execution precondition to prevent silent defaults.

## Entry: 2026-02-22 17:58 +00:00 - Dev-full handles registry drafting plan (pre-edit)

### Trigger
1. USER requested: "draft the dev_full handles registry".
2. Run-process authority now explicitly blocks execution until this registry exists.

### Design objective
1. Produce a closure-grade `dev_full_handles.registry.v0.md` that removes naming/path/ID ambiguity for `P(-1)..P17` execution.
2. Keep only account-specific infrastructure IDs as explicit `TO_PIN` fields; no hidden defaults.

### Structure decision
1. Mirror proven dev_min registry style for operator familiarity and drift control.
2. Extend sections to cover dev_full-only lanes:
   - MSK + schema registry,
   - EKS namespaces/deployments,
   - Step Functions + MWAA,
   - Databricks + SageMaker + MLflow,
   - learning-phase evidence paths (`P12..P16`),
   - cross-platform cost capture handles.

### Key constraints being enforced
1. Event bus is MSK (not Confluent) for dev_full.
2. Full-platform scope includes OFS/MF/MPR handles.
3. Registry is single source of truth for concrete naming surfaces.
4. No local-compute/runtime handles allowed.

### Planned follow-on updates
1. Update migration README wording now that dev_full registry will exist.
2. Append implementation-map and logbook entries with rationale and resulting file paths.

## Entry: 2026-02-22 18:07 +00:00 - Dev-full handles registry created and aligned to run-process/design-authority pins

### Implemented artifact
1. Created `docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md` as the concrete handle authority for dev_full.

### Why this structure was chosen
1. Mirrored dev_min registry shape to preserve operator familiarity and reduce cross-env drift.
2. Extended scope to include full-platform lanes (Spine + OFS/MF/MPR) and dev_full stack surfaces.
3. Kept account-specific unresolved items explicit in one fail-closed section (`Section 14`) rather than scattering ambiguity.

### Coverage closed by this draft
1. Global constants, run pinning, tags, and budget thresholds.
2. Terraform state/stack handles for `core/streaming/runtime/data_ml/ops` split.
3. S3 object/evidence/artifact bucket handles and lane-level evidence path contracts through full-platform closure.
4. MSK + schema registry handles, topic map, partition/retention defaults.
5. ECR/image handles and runtime entrypoint contract.
6. EKS cluster/namespaces/deployment handles (spine + learning dispatch surfaces).
7. Aurora/Redis handles and secret paths.
8. Databricks/SageMaker/MLflow handles.
9. Step Functions + MWAA handles and pinned failure taxonomy keys.
10. IAM/secret map with the exact required role+path set from design authority.
11. Observability/governance handles and cost/teardown handles.

### Validation completed
1. Verified required IAM role handles from design authority Section 8.6 are present.
2. Verified required secret path handles from design authority Section 8.6 are present.
3. Verified Appendix C topic set is fully represented as concrete topic handles.

### Companion index update
1. Updated `docs/model_spec/platform/migration_to_dev/README.md` to mark `dev_full_handles.registry.v0.md` as present and authoritative, with `TO_PIN` materialization prerequisites explicitly called out.

### Remaining explicit dependency
1. `Section 14` `TO_PIN` materialization handles still require value closure before first `dev-full-up` execution.
