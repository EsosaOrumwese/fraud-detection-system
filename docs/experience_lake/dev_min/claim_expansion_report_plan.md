# Dev-Min Claim Expansion Report Plan
_As of 2026-02-26_

## 1) Purpose
This file is the active execution plan for recruiter-facing claim reports in `docs/experience_lake/dev_min/`.
It exists to keep report work focused, current, and externally legible.

## 2) What This Plan Must Do
- Keep claims in recruiter language, not internal project shorthand.
- Enforce evidence-backed writing without dumping raw internals.
- Prevent overlap between reports unless overlap is intentional and scoped.
- Track current claim status and next action only.

## 3) What This Plan Must Not Contain
- Historical work logs.
- Internal phase diaries.
- Long narrative content that belongs inside report files.
- Repeated repository-specific terminology in claim text.

## 4) Writing Standard (All Claims)
Each report must satisfy all rules below:
1. Lead with one clear capability claim in external engineering language.
2. Define in-scope boundary and explicit non-claims.
3. Explain problem, risk, and design decisions with trade-offs.
4. Describe implementation mechanics clearly enough for technical challenge.
5. Show controls/guardrails and fail-closed behavior.
6. Present defensible outcomes and limitations.
7. Provide proof hooks (paths, run markers, artifacts) without secret material.
8. End with recruiter relevance (why this capability matters to a senior role).

## 5) Standard Report Structure
1. Claim Statement
2. Outcome Target
3. System Context
4. Problem and Risk
5. Design Decisions and Trade-offs
6. Implementation Summary
7. Controls and Guardrails
8. Validation Strategy
9. Results and Operational Outcome
10. Limitations and Non-Claims
11. Proof Hooks
12. Recruiter Relevance

## 6) Delivery Workflow (Per Claim)
- Scope Lock: claim line, boundary, non-claims, and merge/standalone decision pinned.
- Draft Core: Sections 1-8 written with technical depth and no hand-wavy language.
- Outcome Lock: Sections 9-10 completed with only defensible statements.
- Proof Lock: Sections 11-12 completed with challenge-ready anchors.
- Hardening Pass: remove ambiguity, repetition, and repo-jargon overload.

Exit rule: a claim is done only when all five workflow steps are complete.

## 7) Active Claim Queue

### Claim 0 - Service-Level Objective-Gated Managed Platform Certification (Primary)
Plan file:
- `docs/experience_lake/dev_min/managed_slo_gated_platform_certification.report_plan.md`

Target report file:
- `docs/experience_lake/dev_min/managed_slo_gated_platform_certification.report.md`

Locked claim:
- Designed and executed a machine-adjudicated certification program for a distributed fraud platform in a managed cloud environment, where closure required semantic correctness, incident resilience, scale behavior, recovery performance, and reproducibility to pass explicit Service Level Objective thresholds under fail-closed blocker semantics.

Status:
- Active top-priority claim (primary claim; draft not started).

### Claim A - CI/CD and Release Engineering (Merged)
Target file:
- `docs/experience_lake/dev_min/cicd_release_engineering_secure_auditable_immutable.report.md`

Locked claim (merged):
- Built and operated a secure, auditable CI/CD release lane where GitHub Actions is the authoritative build path, releases are accepted only with immutable artifact identity (tag plus digest) and machine-readable provenance, cloud access is enforced through OpenID Connect role assumption plus least-privilege Elastic Container Registry permissions (including explicit `ecr:GetAuthorizationToken` closure), and image contents are kept deterministic through explicit include/exclude build-context controls in a large monorepo.

In scope:
- Authoritative CI build/publish lane and fail-closed release gates.
- Immutable container identity (tag plus digest) and machine-readable provenance.
- Authentication and authorization plane separation for CI-to-cloud access.
- OpenID Connect trust/provider closure and least-privilege Elastic Container Registry scope closure.
- Deterministic image-content controls (explicit include/exclude, no repository-wide copy, bounded dependency surface).
- Real failure chain coverage (authentication failure -> authorization failure -> successful closure).

Out of scope:
- Organization-wide identity and access management programs outside this CI release lane.
- Full software supply-chain attestation program across all services.
- Runtime reliability outcomes after image publish (owned by runtime claims).

Status:
- Complete (hardening + recruiter-readability trim done).

### Claim C - Managed IaC Foundation and Cost Guardrails
File:
- `docs/experience_lake/dev_min/managed_iac_state_locking_and_cost_guardrails.report.md`

Locked claim:
- Designed a managed development platform on Terraform with remote state locking and persistent/ephemeral stack separation, then enforced budget guardrails so environment operations remained reproducible, low-risk, and cost-bounded.

In scope:
- Remote state + lock discipline.
- Persistent core vs ephemeral demo stack split.
- Budget controls and banned cost footguns.
- Teardown posture as cost and risk control.

Out of scope:
- Enterprise-wide FinOps governance.
- Organization-level multi-account policy programs.

Status:
- Complete (hardening + recruiter-trim done).

### Claim D - Managed Secret Lifecycle and Runtime Credential Freshness
File:
- `docs/experience_lake/dev_min/managed_secret_lifecycle_and_runtime_credential_freshness.report.md`

Locked claim:
- Implemented a managed secret lifecycle for messaging credentials using encrypted parameter storage (no plaintext source-control exposure), controlled rotation, and teardown-aligned disposal, and enforced service redeploy after rotation so running workloads actually consume new credentials rather than stale in-memory values.

In scope:
- Secret material storage in encrypted parameter store and non-commit posture.
- Rotation workflow and bounded operational sequence for credential updates.
- Runtime freshness enforcement through post-rotation service redeploy.
- Teardown-aligned secret disposal to avoid stale credential residue.
- Failure class and remediation for the gap between rotation and runtime consumption.

Out of scope:
- Full enterprise key-management architecture across all environments.
- Full organization-wide secrets governance/compliance policy.
- Runtime business-metric outcomes unrelated to credential lifecycle control.

Status:
- Complete (hardening + recruiter-trim done).

### Claim E - Streaming Ingestion Reliability and Transport Truth Boundaries
File:
- `docs/experience_lake/dev_min/replay_safe_stream_ingestion_and_transport_truth_boundaries.report.md`

Locked claim (merged):
- Built a production-style streaming ingestion boundary that is idempotent, replay-safe, and fail-closed (canonical dedupe identity, mismatch-as-anomaly, no silent overwrite), while enforcing clear truth ownership by treating Kafka as an ephemeral transport layer (with pinned topic/partition semantics) and durable state/evidence in object storage.

In scope:
- Canonical dedupe identity and replay-safe ingest behavior.
- Fail-closed mismatch handling (anomaly/quarantine posture vs overwrite).
- Topic map and partitioning semantics as intentional transport design.
- Kafka retention posture as ephemeral transport, not durable source of truth.
- Durable truth/evidence surfaces outside broker retention.
- One real incident/remediation chain that demonstrates these controls under failure.

Out of scope:
- Exactly-once end-to-end semantics across every downstream side effect.
- Broker replacement strategy or multi-region disaster recovery architecture.
- Organization-wide streaming governance beyond this platform boundary.

Status:
- Complete (hardening + recruiter-trim done).

### Claim F - Evidence-Driven Runtime Assurance and Data-Plane Readiness
Planned file:
- `docs/experience_lake/dev_min/evidence_driven_runtime_assurance_and_data_plane_readiness.report.md`

Locked claim (merged):
- Built an evidence-driven runtime assurance model where each run publishes durable, machine-readable proof artifacts and closure fails closed when required evidence is missing, then hardened preflight and readiness probes against data-plane failure surfaces (not control-plane proxies) to reduce false negatives and force controlled drift remediation.

In scope:
- Durable run evidence bundle model (including CI provenance surfaces where relevant to runtime adjudication).
- Artifact-presence and artifact-integrity gates as closure blockers.
- Preflight and readiness probes mapped to actual data-plane risks (messaging reachability/compatibility, boundary readiness, and end-to-end semantic viability).
- Fail-to-fix-to-pass incident chain proving probe redesign and controlled remediation.
- Clear separation of operator summaries vs machine-readable adjudication artifacts.

Out of scope:
- Full enterprise observability program across all environments and teams.
- End-to-end business key performance indicator ownership beyond runtime assurance controls.
- Generic health-check catalogs that are not tied to adjudicated runtime risk surfaces.

Execution plan (report workflow states):
- Scope Lock: complete.
- Draft Core: next (Sections 1-8).
- Outcome Lock: pending (Sections 9-10).
- Proof Lock: pending (Sections 11-12).
- Hardening Pass: pending.

Priority:
- Next active claim for section-by-section drafting.

## 8) Backlog Source
Candidate claims are sourced from:
- `docs/experience_lake/dev_min/wrk_experience_dev_min.md`

Promotion rule:
- Move a candidate into this queue only when claim text, boundary, and non-claims are explicitly locked.
