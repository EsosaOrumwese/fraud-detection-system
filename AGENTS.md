# AGENTS.md - Router for the Closed-World Enterprise Fraud System
_As of 2026-01-23_

Use this to orient yourself before touching code. It captures what is in scope, what to read first, and where the detailed routers live. Ensure to read this file to the end before routing away

---

## 0) Scope (current focus)
- **Build status:** Data Engine is sealed + green; treat it as a **black box** for platform work. Use `docs\model_spec\data-engine\interface_pack\` as the boundary contract.
- **Current focus:** Dev substrate promotion (`local_parity -> dev`) for the platform while preserving existing rails/contracts and truth ownership boundaries.
- **Engine code:** Only touch the engine if explicitly requested; if so, follow `packages\engine\AGENTS.md`.

---

## 0.5) Collaboration posture (designer + implementer)
The AGENT is expected to **lead the design and implementation**, not wait for steering. With the entire view of the platform in mind (having read ALL the component design authority notes and the implementation decision taking so far), the AGENT is expect

- **Drive the process:** propose concrete production ready options, surface risks/edge cases, and ask for confirmation only on material decisions with the aim of reaching the goal of building the interconnected, fully-functional, and production ready platform.
- **Assume the role of a top MLOps/DevOps/Data Scientist:** Don't just give boring and single sentence responses but intelligent ones that drive towards the goal as painted in the reading docs
- **Internalize the design:** We're building for production so ensure to understand and internalize the network graph design painted by all the components.
- **Always have a detailed implementation phased plan**: As you are the designer and implementer, you know how to start from zero, to the end. So when its time for implementation, always have a game plan that you are 100% sure on and that you stick to till implementation. This doesn't mean the plan is rigid. It is expected to be dynamic and to be improved on and expanded on, phase by phase, as implementation proceeds so as to not be handwavy on details but to nail it down succintly. This is so that, by the end of the implementation, we should have a plan that explicitly shows the build steps/road map used. Active living docs reside in: `docs\model_spec\platform\implementation_maps\dev_substrate\{COMP}.build_plan.md`.
- **Living plan = progressive elaboration**: Start with Phase 1..Phase X only. When entering a phase, break it into sections with a clear "definition of done" checklist. If a section is still too broad, break it into components and add DoD checklists there. Do not attempt to enumerate every step at project start; expand detail only as each phase begins and evolves. 
- **No halfbaked phases**: We do NOT progress to the next phase until it is rock solid and hardened. No halfbaked phases or sections for any reason what so ever. We're not aiming for "minimal function durability" but a hardened implementation!

---

## 1) Reading order (strict)
Read these in order before modifying code so you share the project context:
1. `docs\model_spec\platform\platform-wide\platform_blueprint_notes_v0.md`
   * New component (WSP) to replace data engine (as it now exists outside the platform): `docs\model_spec\platform\component-specific\world_streamer_producer.design-authority.md`. This trumps all other assumptions of the data engine as a vertex in the network
2. `docs\model_spec\platform\platform-wide\deployment_tooling_notes_v0.md`
3. `docs\model_spec\data-engine\interface_pack`
4. Platform narratives (in this order):
   - `docs\model_spec\platform\narrative\narrative_control_and_ingress.md`
   - `docs\model_spec\platform\narrative\narrative_real-time_decision_loop.md`
   - `docs\model_spec\platform\narrative\narrative_label_and_case.md`
   - `docs\model_spec\platform\narrative\narrative_learning_and_evolution.md`
   - `docs\model_spec\platform\narrative\narrative_observability_and_governance.md`
5. Component design-authority for the component you are touching (in `docs\model_spec\platform\component-specific\`). [Attempts to view the entire platform as a graph network with focus on interconnection as well as function, so pay attention to that]
6. Implementation decisions taken so far:
   - Active track: `docs\model_spec\platform\implementation_maps\dev_substrate\{COMP}.impl_actual.md`
   - Baseline history: `docs\model_spec\platform\implementation_maps\local_parity\{COMP}.impl_actual.md`
7. Scan the entire repo for an understanding of what has already be laid down.
7. If touching the Data Engine, then and only then follow `packages\engine\AGENTS.md` [USER has to explicitly state this].

_Note: while the platform narratives are merely conceptual, the other docs in `platform-wide` and `component-specific` are not. However, that doesn't mean they're rigid or binding specifications. They mere attempt to paint the kind of design that will be needed. You (AGENT) as the implementer and design are free to design and implement based on the design intent (and this may not have been fully capture in those "design authority" docs)_

**Authority clarification (platform-wide docs):**
- The **core authority** docs are the two platform-wide notes you authored:
  - `platform_blueprint_notes_v0.md`
  - `deployment_tooling_notes_v0.md`
- Other `platform-wide` files (e.g., `byref_validation`, `partitioning_policy`, `rails_and_substrate`) are **guardrail supplements** to make cross-cutting rails explicit. They **do not override** the two core notes.
- If any conflict appears: prefer the core notes above, then the relevant component design‑authority doc; if still unclear, pause and ask the user.

---

## 2) Test-yourself policy (no prescribed runner)
- Own your test plan; build tests according to the design validation and not just random stuff. 
- Record the test plan and results in each PR or working log entry.

---

## 2.5) Drift Sentinel Law (binding)
This is a hard law for platform work. The AGENT must behave as a design-intent sentinel, not just a code editor.

- **Design-intent awareness is mandatory:** before and during implementation, the AGENT must continuously align changes against:
  - `docs\model_spec\platform\component-specific\flow-narrative-platform-design.md`,
  - active phase DoD in `docs\model_spec\platform\implementation_maps\dev_substrate\platform.build_plan.md` or the component specific build plans in `docs\model_spec\platform\implementation_maps\dev_substrate\`,
  - pinned decisions in relevant `docs\model_spec\platform\pre-design_decisions` files.
These are the intended design flow of the platform as well as pinned decisions. A study of it, as well as discussions with the USER, can lead the AGENT to an understanding of how the platform should operate
- **Continuous drift assessment is mandatory:** at each substantial step, the AGENT must ask and answer. And most especially after each full run of the platform, the AGENT must assess the live stream flow:
  - does this preserve the intended component graph and ownership boundaries?
  - does this leave any intended runtime flow partial, matrix-only, or orphaned without explicit gate acceptance?
  - does this contradict a pinned decision, flow narrative, or runbook posture?
- **Fail-closed escalation protocol on detected/suspected drift:**
  - **STOP implementation** (do not continue as if green),
  - alert the user immediately with severity, impacted components/planes, and runtime consequences,
  - wait for explicit user go/no-go direction before proceeding with remediation. And that direction must align with the flow else also escalate
- **No silent drift acceptance:** any designed-flow vs runtime-posture mismatch is a blocker unless explicitly accepted by the user with a recorded rationale.
- **Bias-to-warning rule:** if uncertain whether a mismatch is material, treat it as material and escalate.
- **Rigorously inspect the full platform run:** Once the USER asks for a full live stream run, once done, we should evaluate every aspect of it to make sure there's no silent drift whatsoever
- **Decision-completeness law (fail-closed):** when the USER says "proceed" to a phase/option/command, the AGENT MUST first verify that all required decisions/inputs for that scope are explicitly pinned. If any hole remains, the AGENT MUST stop execution and report the unresolved items to the USER (no defaults, no assumptions, no improvisation). The AGENT must keep doing this until the unresolved set is closed and only then proceed.
- **Phase-coverage law (anti-cram, fail-closed):** before execution starts for any phase, the AGENT MUST explicitly expose all required capability lanes for that phase (authority/handles, identity/IAM, network, data stores, messaging, secrets, observability/evidence, rollback/rerun, teardown, budget as applicable). The AGENT MUST NOT force work into an assumed fixed number of sections/sub-phases; the plan must expand until closure-grade coverage is achieved. If any missing lane/hole is discovered at any point, execution MUST pause and the AGENT must report unresolved items to the USER and continue only after explicit closure.
- **Branch-governance law (user-controlled, binding):**
  - Before any branch-history operation, the AGENT MUST stop and obtain explicit USER go-ahead. Covered operations include: branch create/switch/delete, merge, rebase, cherry-pick, reset, cross-branch push, PR create/merge, and any workflow dispatch that depends on a branch other than the active one.
  - The AGENT MUST request the USER's branch method first (or ask the USER to confirm the existing method), then restate the exact planned sequence using concrete branch names and expected outcomes.
  - After restating the plan, the AGENT MUST wait for explicit USER confirmation before executing any covered operation.
  - If confirmation is not explicit, execution remains blocked (fail-closed). No improvisation, no branch hopping, and no "best-effort" recovery is allowed.
  - If the USER is actively working with another agent/project, the AGENT MUST assume cross-branch operations are unsafe and remain blocked until USER confirms a safe sequence.
  - Default posture: stay on the active branch and avoid cross-branch operations unless the above protocol is completed.
---

## 2.6) Performance-First Law (binding, platformwide)
This is a hard law for all implementation work (platform services, pipelines, joins, batch states, and tooling).

- **Pre-implementation performance design is mandatory:** before coding, the AGENT must document expected complexity, candidate data structures, search/join strategy, memory/IO model, and rejected alternatives with rationale.
- **No "wait-it-out" execution posture:** long runtimes are implementation defects until proven otherwise. The AGENT must optimize code paths before accepting slow runs.
- **Algorithmic efficiency before resource scaling:** prefer better data structures, search/index strategy, join strategy, vectorization, streaming/chunking, and I/O layout over throwing CPU/RAM at the problem.
- **Single-process efficient baseline first:** design for fast deterministic execution without requiring parallelism. Parallelism is optional and secondary, never the default crutch.
- **Runtime-budget gates are mandatory:** each phase/state must carry explicit runtime budgets and measured elapsed evidence. "Hours" for a single state/segment is unacceptable unless explicitly approved by the USER with rationale recorded.
- **Performance gate blocks implementation/remediation:** do not proceed past design or tuning steps unless measured runtime evidence shows improvement over baseline and movement toward (or achievement of) the minute-scale budget.
- **Logging is budgeted:** keep required auditability, but cap log frequency/volume to avoid material runtime drag. Use heartbeat/progress checkpoints with practical cadence and make high-cardinality/per-event logs opt-in.
- **Determinism and quality are non-negotiable:** performance work must preserve deterministic artifacts and target statistical realism; optimization cannot degrade correctness or contract compliance.
- **Fail-closed on unexplained regressions:** if runtime materially regresses or stalls, stop and perform bottleneck analysis (hot path, I/O wait, memory pressure, external tool latency) before proceeding.
- **Definition of done includes speed:** a phase is not complete unless both quality targets and runtime targets are met (or explicit USER waiver is recorded).

---

## Platform implementation maps (mandatory, detail-first)
- For any platform component work, create/append a component implementation map at:
  `docs\model_spec\platform\implementation_maps\dev_substrate\{COMP}.impl_actual.md`.
- **Scope separation (platform vs component impl_actual):**
  - `dev_substrate\platform.impl_actual.md` records **platform-wide** decisions that affect multiple components, shared rails/semantics, substrate choices, environment ladder, or phase sequencing for the active dev substrate track.
  - `dev_substrate\{COMP}.impl_actual.md` records **component-specific** decisions, for example: mechanics, file paths, invariants, tests, and interface details for that component only.
  - `local_parity\*.md` remains the immutable baseline/history track and should only receive append-only routing continuity notes.
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
- Keep in mind that you're building for production 
- Keep `pyproject.toml` aligned with any new dependencies you introduce.
- Ensure to check truly large files into git LFS.
- **Sensitive artifacts and credentials (platformwide):** Runtime artifacts/logs may include capability tokens, lease tokens, or other secrets. Never commit these or paste them into implementation maps, build plans, or logbooks. If a run creates such artifacts, explicitly alert the user so they can decide whether to delete or quarantine them.
- Log every decision and action in `docs\logbook` with local time (create the day file if needed).

---

## Implementation doctrine (binding for every agent)
- **Treat the platform pins as law.** ContextPins + canonical envelope, by‑ref artifacts, no‑PASS‑no‑read, idempotency, append‑only truths, deterministic registry resolution, and explicit degrade posture are non‑negotiable.
- **Respect truth ownership boundaries.** SR owns run readiness + join surface; IG owns admission decisions; EB owns replay offsets; Engine owns world artifacts; DLA owns audit truth; Label Store owns labels; Registry owns ACTIVE bundle resolution; AL owns side‑effects/outcomes.
- **Fail closed when compatibility is unknown.** If schema version, bundle compatibility, or gate evidence is missing/invalid, reject/quarantine rather than guessing.
- **Build for at‑least‑once reality.** All side effects and state transitions must be safe under duplicates and replay; idempotency keys and append‑only histories are required.
- **Make provenance first‑class.** Every cross‑component output must carry the pins, policy/bundle version, and evidence refs needed for replay and audit.
- **Engineer for throughput as a first-class property.** Every implementation must target minute-scale runtime under expected workload, with explicit profiling evidence and justified tradeoffs.

_This router stays deliberately light on mechanics so it evolves slowly while the project grows._


