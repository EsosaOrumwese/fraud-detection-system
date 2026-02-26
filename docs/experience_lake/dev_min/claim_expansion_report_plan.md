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

### Claim A - Release Workflow Integrity
File:
- `docs/experience_lake/dev_min/auditable_release_pipeline_immutable_images.report.md`

Scope:
- Auditable CI release lane.
- Immutable image identity (tag + digest).
- Provenance output.
- Deterministic build surface controls (include/exclude, bounded dependency selection).

Status:
- Complete (hardening + recruiter-trim done).

### Claim B - Secure CI Federation and Registry Authorization
File:
- `docs/experience_lake/dev_min/secure_ci_oidc_and_least_privilege_registry_auth.report.md`

Scope:
- OIDC role assumption for CI.
- Separation of authentication vs authorization failure classes.
- Least-privilege registry permissions with fail-closed remediation.

Status:
- Complete (hardening + recruiter-trim done).

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
Planned file:
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
