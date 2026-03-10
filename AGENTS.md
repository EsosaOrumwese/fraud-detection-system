# AGENTS.md - dev_full platform hardening router
_As of 2026-03-10_

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
- Our focus is discussed in `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\proving_plane\`

---

## 2) Primary docs for contextual understanding of direction we are heading 
For platform work on `dev_full`, read in this order:
1. `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\proving_plane\platform.production_readiness.md`
2. The relevant phase plans under `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\proving_plane\`
3. The active `dev_full` implementation maps under `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\proving_plane\`

And very much related, is the experience we are trying to acquire in this project
* `docs\experience_lake\recruiter-expectation_MLOps.md`
* `docs\experience_lake\recruiter-expectation_MLPlatformEngr.md`
* `docs\experience_lake\platform-production-standard.md`

It's important to note that as you go through the repo, `local-parity`, `dev_min` are all profiles or substrates we have moved from and are now in making `dev_full` production hardened (this is different from `prod_target` as that doesn't mean our production target but rather an endgame substrate that we could hit if we want to push things much further. ). Surely you can find and infer the meaning of what these mean from this repo
---

## 3) Working posture
- Work autonomously for long stretches. Do not stop for routine blockers you can analyze and resolve yourself. Most problems are solvable, you just have to give it the time to assess it.
- This mindset should remain with you: In achieving our goals, you would encounter problems/blockers/issues/etc across all planes and the platform as a whole. These are issues, when found you should take your time analyzing it and resolving it without adding more points of failure or sacrificing on our goals. Don't be too scared to then stop the long run to report the blocker as there are undoubtably a lot of problems that cover the entire implementation of this platform across all planes, meta players, components and their infrastructure.
- The current platform might use resources or decisions that are not the very best or would hinder our production standard, you have the autonomy to decide how to approach that, ensure to note it though in your own road-to-production notes.
- Choose the option that best serves production reality, not the option that only gets a green receipt fastest.
- I want the AGENT to focus heavily on problem finding and resolving to avoid the number of trial and errors. This involves high level of reasoning to identify problems surrounding and issue, and most important why they're problems, tests to catch points of breakage and then coming up with proven solutions to resolve such problems. This isn't a template I'm giving you but a mindset because as we build this network in incremental stages, points of failures increase and so identifying this beforehand and resolving it avoids excess time wasted in back and forths.
- Treat each problem as an engineering problem to be understood, narrowed, fixed, and revalidated.
- Prefer bounded AWS-first runs with fail-fast behavior and precise diagnostics over long expensive blind runs.
- Make the platform work plane by plane before escalating duration and volume.
- Do not touch or rerun the Data Engine unless the user explicitly asks. Deleting or reruning the data engine or whatever is out of bounds, work with the data we've put in the oracle store (this just prevents us from leaving the realm of platform to manipulate the data engine which is another realm and exists outside of the platform.)
- Keep the workspace neat:
  - durable run evidence in `runs/`
  - no scattered temp directories or dumped artifacts in repo root

---

## 4) Implementation notes and logbook
- Keep implementation notes, but write them like a detailed natural engineering notebook.
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
- Also log actions and decisions in `docs\logbook` with local time. Local time is essential as there are times (for both docs, logbook and implementation notes) where you go with the time in your VM or you lazily assume the time. But whatever it is, you end up with false times which after a series of entries, cause you to most times be 6hrs ahead of the actual time.
- State summaries should focus on impact metrics relevant to that phase or state, then give a direct judgment on whether those metrics actually meet the production-ready goal.

### 4A) Network Graphs
Note: This only applies when we are production hardening the platform and not elsewhere. The implementation notes is your decisions capturing notes, while the network graphs which are derived explanatory graphs from our current state and not truth/binding docs are more for the USER'S understanding of the current state of the platform.
- Understanding the purpose of the graphs in `docs\design\platform\dev_full\graph\readiness` is linked to the incremental network hardening posture taken in `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\proving_plane\platform.production_readiness.plan.md`.
- It should be your focus that but as we move to each plane, tackling problems in it and then attaching the plane to the current hardened network to verify paths and connections, the graphs should regularly be updated even though it's not hardened so the USER can understand what problems exist and where. 
   - Control and Ingress plane showcase this mindset. It highlights the phase 0 C&I green network (`dev_full_platform_network_production_ready_current_v0.mermaid.mmd`), as well as the readiness delta (`dev_full_control_ingress_readiness_delta_current_v0.mermaid.png`)
   - It doesn't replace the implementation note or try to fit in as much detail but for its purposes, it tries to reflect the current status of the platform at that phase for the USER and supplement the notes. This doesn't mean the graph is a lazy summary or simplification or a dumbing down of the actual process.
- So basically I need three graphs as we work on each phase:
   *  Production-Ready Network Graph: a topology graph of the currently confirmed production-ready working platform that only includes planes, components, paths, and supporting surfaces that are already proven and promoted into the working platform. Essentially a derived readiness graph that shows only the currently confirmed working platform. It grows phase by phase as new planes and coupled paths are proven and promoted. Absence means “not yet confirmed production-ready.”
   * Production-Ready Resource Graph: a concrete resource view of the currently confirmed production-ready working platform that shows the actual AWS / managed resources, names, sizing, and key runtime posture for the confirmed working platform. Essentially a derived readiness graph that shows the concrete provisioned resources backing the currently confirmed working platform, including actual cloud names and key sizing/runtime posture, so the operator can map readiness claims directly to the cloud console.
   * Readiness-Delta Graph: a derived explanatory graph for the currently active plane or coupled network under hardening. It captures the live readiness story as component/scope -> blocker -> remediation or unresolved issue -> measured impact -> readiness verdict. It should be created and updated during active remediation, then finalized or removed based on usefulness once the plane closes.

---

## 5) Performance and cost discipline
- Production readiness includes throughput, latency, consistency, explainability, recovery, and cost discipline.
- Do not use large long runs to discover basic correctness defects.
- It best to have a detailed methology for capturing and monitoring ongoing runs live so we aren't stuck in the dark when running to know when to kill a process or to properly debug a consistently failed issue.
- Before a more expensive run, first prove the platform or plane works on a bounded production-shaped run.
- Scale pressure gradually:
  1. bounded correctness,
  2. bounded stress,
  3. soak only after the earlier gates are genuinely green.
- If a run is expensive, it must answer a clear question.
- If a resource is idle, scale it down or stop it where possible without destroying needed substrate.
- As we run/test/harden our platform, we tend to accumalate a huge amount of data in storage (either databases, buckets, registries, etc.). Routine flushing of these would prove cost effective.

---

## 6) Branches, commits, and PR review
- Do not improvise branch history operations.
- The normal active working branch is the current off-`dev` branch, for example `cert-platform`.
- Workflow-only promotion path:
  1. create a single workflow-only commit on the current working branch,
  2. merge that commit path into `dev`,
  3. open a PR from `dev` to `main`,
  4. wait for Copilot/Codex reviewers to comment (maybe 4/5 minutes),
  5. address or explicitly respond to every review point,
  6. wait briefly to confirm no further review issues remain (same time as above),
  7. merge the PR,
  8. merge `main` back into `dev`,
  9. merge `dev` back into the working branch.
- Do not merge the whole working branch when only workflow changes are intended.
- Do not create commits except when the user has approved that scope. If the approval is workflow-only, stage only workflow files.
- Within prompt/chat, the user will give explicit context for commits + pushes and merges. Most times in long run works.
- In long runs, you are expected to commit and push your work at regular intervals (at the the normal active working branch which we have state above) so that from whereever the USER is, the USER is able to observe the repo and the notes to see what you're doing. So choose what frequency works for you and won't hinder your problem solving (maybe every 20mins or after every milestone or after solving a problem, its up to you.) However, don't mess up my branches. You are only allowed to merge the commits for workflows (I approve of this) but it should be done according to how we discussed.

---

## 7) Testing posture
- Own the test plan.
- Test according to the real design and production intent, not random runner convenience.
- Prefer live AWS validation for platform runtime truth.
- Keep tests and runs targeted so failures are easy to localize.

---

## 8) Final reminder
The job is not to prove the platform is merely wired. The job is to make sure the full `dev_full` platform can operate as a production system under meaningful load while producing meaningful, explainable, auditable outcomes.
