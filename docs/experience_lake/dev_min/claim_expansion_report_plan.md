# Claim Expansion Report Plan (Dev-Min Workstream)
_As of 2026-02-25_

## 1) Purpose
This plan defines how we turn shortlisted claims into technical reports that are:
- recruiter-readable (Senior MLOps / Senior Platform Engineer language),
- technically defensible,
- concise enough for interviews and hiring loops,
- reusable for CV bullets, cover letters, LinkedIn posts, and interview answers.

This is not a project build plan. It is a reporting and evidence-hardening plan.

## 2) Audience
Primary:
- technical recruiters,
- hiring managers,
- senior engineers running deep-dive interviews.

Secondary:
- portfolio reviewers and screening panels.

## 3) Scope
In scope:
- one report per shortlisted claim,
- technical narrative focused on production outcomes, risk control, and repeatability,
- proof hooks (artifact or run anchors) without dumping raw logs/secrets/policies.

Out of scope:
- internal phase labels and repo-specific shorthand in headline claims,
- raw credential material or sensitive runtime values,
- low-signal implementation trivia.

## 4) Language Rules (Mandatory)
1. Use external engineering language:
   - "managed environment", "release pipeline", "runtime identity", "ingestion boundary", "replay safety", "incident recovery".
2. Avoid internal-only shorthand in report body:
   - avoid terms like internal phase codes unless they appear only in proof hooks.
3. Keep claims outcome-first:
   - "what changed in operational capability", not "which internal step completed".
4. Keep evidence references minimal:
   - reference artifact names/anchors, not full raw dumps.

## 5) Report Template (Per Claim)
Each claim report must use this section order:

1. Claim Statement
2. Outcome Target
3. System Context
4. Problem and Risk
5. Design Decision and Trade-offs
6. Implementation Summary
7. Controls and Guardrails (fail-closed posture)
8. Validation Strategy
9. Results and Operational Outcome
10. Limitations and Non-Claims
11. Proof Hooks
12. Recruiter Relevance

## 6) Quality Gates (Per Claim)
A claim report is "ready" only if all are true:

1. Clarity gate:
   - understandable without repository context.
2. Technical gate:
   - includes mechanism, constraints, and trade-offs.
3. Evidence gate:
   - at least one concrete proof hook is included.
4. Honesty gate:
   - explicitly marks achieved vs current vs target when relevant.
5. Security gate:
   - no secrets, tokens, or sensitive payloads.
6. Recruiter gate:
   - explicitly answers "why this matters for a senior role".

## 6.1 Burden-of-Proof Standard (Mandatory)
Every claim section must prefer explicit mechanics over shorthand.

Required posture:
- define terms that can be misread,
- state failure condition -> remediation -> closure,
- state what was enforced by system behavior (not just operator intent),
- distinguish "observed fact" from "inference",
- include at least one challenge-ready proof hook for each major claim branch.

## 7) Workflow (One Claim at a Time)
For each claim:

1. Frame:
   - finalize claim wording in external language.
2. Expand:
   - write full report with the template above.
3. Harden:
   - remove internal jargon and ambiguous words.
4. Verify:
   - check report against quality gates.
5. Certify:
   - mark claim as Draft / Hardened / Certified.
6. Extract:
   - derive short versions (CV bullet, interview STAR seed, LinkedIn snippet).

No parallel claim drafting unless explicitly requested.

## 7.1 Incident-First Reporting Pattern (when claim is failure-driven)
If a claim is based on real CI/runtime failures, use this sequence:
1. Failure signature(s) observed.
2. Control gap identified.
3. Concrete remediation applied.
4. Re-run and closure result.
5. Guardrail added to prevent recurrence.

This avoids "we fixed it" narrative drift and keeps recruiter trust high.

## 8) Evidence Handling Policy
Do:
- cite one or two audit anchors per claim,
- describe evidence meaning in plain language.

Do not:
- paste raw JSON blocks by default,
- paste IAM policies or secret-bearing logs into reports,
- overload reports with low-signal artifacts.

If challenged, deeper evidence can be provided in a separate annex.

## 9) Deliverables
For each shortlisted claim, use intent-first filenames:
- `<claim_slug>.report.md` (full technical report),
- `<claim_slug>.extracts.md` (CV/interview/post variants),
- optional `<claim_slug>.evidence.annex.md` (only if deeper proof is needed).

Slug rule:
- lowercase words,
- short and specific,
- joined by underscores,
- no internal phase codes.

Examples:
- `auditable_release_pipeline_immutable_images.report.md`
- `managed_iac_with_cost_guardrails.report.md`
- `streaming_reliability_replay_safe_ingestion.report.md`

## 10) Status Model
- `Draft`: first technical narrative written.
- `Hardened`: language cleaned and ambiguity removed.
- `Certified`: passes all quality gates.
- `Published`: extracted into outward-facing assets.

## 11) Immediate Next Step
Use this plan for Claim 2 and produce first draft:
- `secure_ci_oidc_and_least_privilege_registry_auth.report.md`

## 12) Claim 2 Addendum (CI OIDC + Registry Authorization)
Target claim:
- "Implemented secure CI auth via federated OIDC role assumption and hardened least-privilege container-registry permissions after real CI failures exposed missing trust/provider and missing authorization scope."

Claim-2 report emphasis:
1. Security control clarity:
   - explain federated identity model and why static credentials were not used.
2. Authorization boundary clarity:
   - separate identity success from registry permission success.
3. Failure chronology:
   - fail (identity) -> fail (registry auth) -> pass (after scoped remediation).
4. Least-privilege framing:
   - permissions were expanded only to required publish/read/auth actions.
5. Recruiter signal:
   - demonstrate cloud IAM debugging, release reliability hardening, and security-by-default delivery.

Claim-2 section-level focus notes:
- Section 4 (Problem/Risk): emphasize "identity and auth are separate failure planes."
- Section 5 (Design/Trade-offs): include short-lived federated auth vs static key trade-off.
- Section 7 (Controls): include hard gate: no cloud auth -> no publish; no registry auth -> no publish.
- Section 8 (Validation): include explicit negative-path validation (expected fail) and closure rerun.
- Section 11 (Proof Hooks): include the fail/fail/pass CI run sequence and one final identity+artifact proof anchor.
