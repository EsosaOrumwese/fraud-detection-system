# AGENTS.md - dev_full platform hardening router
_As of 2026-03-09_

Read this before touching platform code.

---

## 1) Scope
- The Data Engine is sealed and green. Treat it as a black box for platform work.
- The active focus is `dev_full` platform hardening toward real production readiness.
- The platform already exists on the `dev_full` track. Do not redesign it from scratch unless a production-grade repin is genuinely required.
- Build for the full platform, not only the spine. That includes:
  - control and ingress,
  - RTDL,
  - case and label management,
  - learning and evolution,
  - MLOps surfaces,
  - ops/governance/meta layers.

---

## 2) Primary authority
For platform work on `dev_full`, reason in this order:
1. `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\build\platform.build_plan.md`
2. The relevant `M*` / `M*P*` build plans under `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\build\`
3. The active `dev_full` implementation maps under `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\`
4. The active road-to-prod plans under `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\road_to_prod\`
5. `docs\model_spec\data-engine\interface_pack\`
6. Supporting component-specific and narrative docs only after the above

`local_parity` is history, not primary authority.

---

## 3) Working posture
- Work autonomously for long stretches. Do not stop for routine blockers you can analyze and resolve yourself.
- Choose the option that best serves production reality, not the option that only gets a green receipt fastest.
- Treat each problem as an engineering problem to be understood, narrowed, fixed, and revalidated.
- Prefer bounded AWS-first runs with fail-fast behavior and precise diagnostics over long expensive blind runs.
- Make the platform work plane by plane before escalating duration and volume.
- Do not touch or rerun the Data Engine unless the user explicitly asks.
- Keep the workspace neat:
  - durable run evidence in `runs/`
  - scratch notes in `scratch_files/`
  - no scattered temp directories or dumped artifacts in repo root

---

## 4) Implementation notes and logbook
- Keep implementation notes, but write them like a natural engineering notebook.
- They should read like real reasoning from an engineer working the problem, not like a templated receipt.
- Record:
  - what the actual problem is,
  - why it matters in production,
  - what options were considered,
  - what was chosen and why,
  - what changed,
  - what the measured impact was,
  - what still remains.
- Use the implementation maps as the living reasoning trail.
- Also log actions and decisions in `docs\logbook` with local time.
- State summaries should focus on impact metrics relevant to that phase or state, then give a direct judgment on whether those metrics actually meet the production-ready goal.

---

## 5) Performance and cost discipline
- Production readiness includes throughput, latency, consistency, explainability, recovery, and cost discipline.
- Do not use large long runs to discover basic correctness defects.
- Before a more expensive run, first prove the platform or plane works on a bounded production-shaped run.
- Scale pressure gradually:
  1. bounded correctness,
  2. bounded stress,
  3. soak only after the earlier gates are genuinely green.
- If a run is expensive, it must answer a clear question.
- If a resource is idle, scale it down or stop it where possible without destroying needed substrate.

---

## 6) Branches, commits, and PR review
- Do not improvise branch history operations.
- The normal active working branch is the current off-`dev` branch, for example `cert-platform`.
- Workflow-only promotion path:
  1. create a single workflow-only commit on the current working branch,
  2. merge that commit path into `dev`,
  3. open a PR from `dev` to `main`,
  4. wait for Copilot/Codex reviewers to comment,
  5. address or explicitly respond to every review point,
  6. wait briefly to confirm no further review issues remain,
  7. merge the PR,
  8. merge `main` back into `dev`,
  9. merge `dev` back into the working branch.
- Do not merge the whole working branch when only workflow changes are intended.
- Do not create commits except when the user has approved that scope. If the approval is workflow-only, stage only workflow files.

---

## 7) Testing posture
- Own the test plan.
- Test according to the real design and production intent, not random runner convenience.
- Prefer live AWS validation for platform runtime truth.
- Keep tests and runs targeted so failures are easy to localize.

---

## 8) Final reminder
The job is not to prove the platform is merely wired. The job is to make sure the full `dev_full` platform can operate as a production system under meaningful load while producing meaningful, explainable, auditable outcomes.
