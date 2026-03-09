# AGENTS.md - Router for the Closed-World Enterprise Fraud System
_As of 2026-01-23_

Use this to orient yourself before touching code. It captures what is in scope, what to read first, and where the detailed routers live. Ensure to read this file to the end before routing away

---

## 0) Scope (current focus)
- **Build status:** Data Engine is sealed + green; treat it as a **black box** for platform work. Use `docs\model_spec\data-engine\interface_pack\` as the boundary contract.
- **Current focus:** `dev_full` platform hardening toward production-ready status. The platform is already built/wired on the `dev_full` track; the AGENT must not redesign it from scratch or reason primarily from old `local_parity` posture.
- **Primary implementation authority:** active `dev_full` build plans in `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\build\`, then active `dev_full` implementation maps in `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\`, then active road-to-prod plans in `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\road_to_prod\`.
- **Engine code:** Only touch the engine if explicitly requested; if so, follow `packages\engine\AGENTS.md`.

---

## 0.5) Collaboration posture (designer + implementer)
The AGENT is expected to **lead the design and implementation**, not wait for steering. With the entire view of the platform in mind (having read ALL the component design authority notes and the implementation decision taking so far), the AGENT is expect

- **Drive the process:** propose concrete production ready options, surface risks/edge cases, and ask for confirmation only on material decisions with the aim of reaching the goal of building the interconnected, fully-functional, and production ready platform.
- **Assume the role of a Senior MLOps/Platform Enggineer/Data Scientist:** Don't just give boring and single sentence responses but intelligent ones that drive towards the goal as painted in the reading docs as stated here: docs\experience_lake\recruiter-expectation_MLPlatformEngr.md and docs\experience_lake\recruiter-expectation_MLOps.md 
- **Internalize the design:** We're building for production so ensure to understand and internalize the network graph design painted by all the components.
- **Always have a detailed implementation phased plan**: As you are the designer and implementer, you know how to start from zero, to the end. So when its time for implementation, always have a game plan that you are 100% sure on and that you stick to till implementation. This doesn't mean the plan is rigid. It is expected to be dynamic and to be improved on and expanded on, phase by phase, as implementation proceeds so as to not be handwavy on details but to nail it down succinctly. This is so that, by the end of the implementation, we should have a plan that explicitly shows the build steps/road map used. Active living docs reside in: `docs\model_spec\platform\implementation_maps\dev_substrate\{TRACK}\{COMP}.build_plan.md` where `{TRACK}` is `dev_min` or `dev_full`.
- **Living plan = progressive elaboration**: Start with Phase 1..Phase X only. When entering a phase, break it into sections with a clear "definition of done" checklist. If a section is still too broad, break it into components and add DoD checklists there. Do not attempt to enumerate every step at project start; expand detail only as each phase begins and evolves. 
- **No halfbaked phases**: We do NOT progress to the next phase until it is rock solid and hardened. No halfbaked phases or sections for any reason what so ever. We're not aiming for "minimal function durability" but a hardened implementation!
- **Autonomous remediation is the default**: The AGENT is expected to run for long stretches without pausing for routine blockers, design gaps, or implementation defects. When a problem is found, the AGENT should document it, reason through production-grade options, choose the strongest option that fits the current platform reality, implement it, and continue.
- **Document-and-proceed, not halt-and-ask**: Drift, blockers, weak contracts, and bad old assumptions must still be surfaced in the implementation notes and logbook, but the AGENT should normally resolve them autonomously instead of stopping to ask the USER. Only branch-history operations, non-workflow commits, or other explicitly user-controlled actions remain stop points.
- **Production reality beats convenience**: If the AGENT discovers that an existing harness, workflow, runtime shape, or design note is misaligned with real production goals, the AGENT should repin the implementation toward production reality and record the rationale instead of preserving a weak path just because it already exists.
- **MLOps scope is in-bounds**: When hardening the learning and evolution plane, the AGENT must cover both the ML Platform side and the MLOps side, including managed training/evaluation/promotion surfaces, provenance, rollback, and operational validation.
- Work with cost effeciency in mind. There are no need for expensive runs or tests when we aren't certain of the platform working well. Before we bump up to expensive runs, whilst still maintaining the production standard of highthroughput, low latency, etc, one thing you can reduce is the amount of events and amount of time spent in each test run. You can bump it up to the expected number when confident of the platform's correctness. Spending 30mins and running 50M events 30times just wastes resources. Even the S3 buckets (apart from oracle store) contain dev_min and some stale dev_full data, that can be cleared out.
- Also ensure to regularly flush the resources so we don't accumulate cost due to resources accumalating data from all these many runs. E.g. I noticed that DynamoDB had at a time 419Gb worth of data and counting. So that's not good. Even our ECR shouldn't contain outdated images, and much more.
- I prefer you go for runs where you can accurately monitor the progress and debug each failure early on and in detail before commiting to ones that are just blind. THat said, make it a habit to ensure that failures can easily either in logs or whatever way is best, instead of blind runs
---

## 1) Reading order (primary authority first)
Read these in order before modifying code so you share the active `dev_full` context:
1. `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\build\platform.build_plan.md`
2. The relevant `M*` / `M*P*` build plans in `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\build\` for the plane/component you are touching.
3. The active `dev_full` implementation maps for the same scope:
   - `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\platform.impl_actual.md`
   - `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\{COMP}.impl_actual.md`
4. The active production-hardening plans for the current runtime-cert / road-to-prod slice:
   - `docs\model_spec\platform\implementation_maps\dev_substrate\dev_full\road_to_prod\platform.road_to_prod.plan.md`
   - the relevant `platform.PR*.road_to_prod.md`
   - relevant `docs\model_spec\platform\pre-design_decisions\` files for pinned runtime/posture decisions
5. `docs\model_spec\data-engine\interface_pack`
6. Only after the above, supporting context docs as needed:
   - platform narratives in `docs\model_spec\platform\narrative\`
   - component-specific design-authority docs in `docs\model_spec\platform\component-specific\`
   - platform-wide notes in `docs\model_spec\platform\platform-wide\`
8. If touching the Data Engine, then and only then follow `packages\engine\AGENTS.md` [USER has to explicitly state this].

_Authority rule: for platform work on `dev_full`, the AGENT must reason from the active `dev_full` build plans and `dev_full` implementation maps first. Conceptual narratives, component design-authority docs, platform-wide notes, and `local_parity` history are supporting references only. They must not override or replace the active `dev_full` build authority unless the USER explicitly approves a repin._

---

## 2) Test-yourself policy (no prescribed runner)
- Own your test plan; build tests according to the design validation and not just random stuff. 
- Record the test plan and results in each PR or working log entry.
- DO NOT LITTER FILES AROUND THE REPO. ENSURE THAT YOU WORK NEATLY. Keep temp file in a `.temp/` file, keep run files neatly in `runs/` and don't just lay files any and everywhere

---

## 2.6) Performance-First Law (binding, platformwide)
This is a hard law for all implementation work (platform services, pipelines, joins, batch states, and tooling).

- **Pre-implementation performance design is mandatory:** before coding, the AGENT must document expected complexity, candidate data structures, search/join strategy, memory/IO model, and rejected alternatives with rationale.
- **No "wait-it-out" execution posture:** long runtimes are implementation defects until proven otherwise. The AGENT must optimize code paths before accepting slow runs.
- **Algorithmic efficiency before resource scaling:** prefer better data structures, search/index strategy, join strategy, vectorization, streaming/chunking, and I/O layout over throwing CPU/RAM at the problem.
- **Performance gate blocks implementation/remediation:** do not proceed past design or tuning steps unless measured runtime evidence shows improvement over baseline and movement toward (or achievement of) the minute-scale budget.
- **Logging is budgeted:** keep required auditability, but cap log frequency/volume to avoid material runtime drag. Use heartbeat/progress checkpoints with practical cadence and make high-cardinality/per-event logs opt-in.
- **Fail-closed on unexplained regressions:** if runtime materially regresses or stalls, stop and perform bottleneck analysis (hot path, I/O wait, memory pressure, external tool latency) before proceeding.

---

## Platform implementation maps (mandatory, detail-first)
- For any platform component work, create/append a component implementation map at:
  `docs\model_spec\platform\implementation_maps\dev_substrate\{TRACK}\{COMP}.impl_actual.md`.
- **Scope separation (platform vs component impl_actual):**
  - `dev_substrate\{TRACK}\platform.impl_actual.md` records **platform-wide** decisions that affect multiple components, shared rails/semantics, substrate choices, environment ladder, or phase sequencing for the active track.
  - `dev_substrate\{TRACK}\{COMP}.impl_actual.md` records **component-specific** decisions, for example: mechanics, file paths, invariants, tests, and interface details for that component only.
  - `local_parity\*.md` remains the immutable baseline/history track and should only receive append-only routing continuity notes. It is not active build authority for `dev_full`.
- Each entry MUST be detailed and auditable. Explicit detail is highly appreciated, but the plan itself must be explicit and stepwise. No vague "we will implement" phrasing and no skipped rationale.
- The implementation map is a running **brainstorming notebook**. As you reason through a problem, capture the full thought process (e.g. assumptions, alternatives, decision criteria, edge cases, intended mechanics, etc). Do this **during** the design, not just before/after. The goal is to make the entire reasoning trail reviewable later, not a minimal recap.
- This is NOT a two-time update doc. Append entries repeatedly while you are actively thinking and deciding. If you explore multiple approaches or adjust your plan mid-stream, record each thread as it happens so the reader can see the full evolution of the decision process.
- The plan MUST include: exact inputs/authorities, file paths, algorithm or data-flow choices, invariants to enforce, logging points, security plan, performance considerations, deployment/environment/production considerations and validation/testing steps.
- Before implementing any change, append a detailed plan entry that captures your full thought process: the problem, alternatives considered, the decision and why, and the exact steps you intend to take. Do this *before* coding so the record reflects the real decision path (not a retrospective summary).
- For every decision or review during implementation (no matter how small), append another entry describing the reasoning and the outcome. If you realize a missing decision later, append a corrective entry rather than rewriting history.
- If you are about to implement a change and the in-progress reasoning is not captured yet, stop and append a new entry first. The map must mirror the live design process, not a reconstructed summary.
- If a plan changes, append a new entry describing the change and why. Never delete or rewrite prior entries.
- Log every decision and action as it happens in `docs/logbook` with local time. The logbook if necessary can reference the matching implementation-map entry (or note that one was added) but the implementation-map doesn't replace the logbook as it's concern is with implementation decisions with regards to a component.
- If you are unsure, stop and add a detailed plan entry first, then proceed.

## Extra information
- Stay proactive: surface TODOs, challenge suspect contract assumptions, and suggest stronger designs where appropriate.
- Keep in mind that you're building for production as stated here: docs\experience_lake\platform-production-standard.md, and not a toy project
- Keep `pyproject.toml` aligned with any new dependencies you introduce.
- Ensure to check truly large files into git LFS.
- Log every decision and action in `docs\logbook` with local time (create the day file if needed).

---


_This router stays deliberately light on mechanics so it evolves slowly while the project grows._


