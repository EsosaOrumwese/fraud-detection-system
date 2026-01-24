# AGENTS.md - Router for the Closed-World Enterprise Fraud System
_As of 2026-01-23_

Use this to orient yourself before touching code. It captures what is in scope, what to read first, and where the detailed routers live. Ensure to read this file to the end before routing away

---

## 0) Scope (current focus)
- **Build status:** Data Engine is sealed + green; treat it as a **black box** for platform work. Use `docs\model_spec\data-engine\interface_pack\` as the boundary contract.
- **Current focus:** Platform build (vertical-slice v0 → full platform). Start with Scenario Runner + Ingestion Gate + Event Bus + Decision Fabric + Actions Layer + Decision Log/Audit, then expand to IEG/OFP/DL, then Label/Case, then Learning/Registry, then Obs/Gov hardening.
- **Engine code:** Only touch the engine if explicitly requested; if so, follow `packages\engine\AGENTS.md`.

---

## 0.5) Collaboration posture (designer + implementer)
The AGENT is expected to **lead the design and implementation**, not wait for steering. With the entire view of the platform in mind (having read ALL the component design authority notes and the implementation decision taking so far), the AGENT is expect

- **Drive the process:** propose concrete production ready options, surface risks/edge cases, and ask for confirmation only on material decisions with the aim of reaching the goal of building the interconnected, fully-functional, and production ready platform.
- **Assume the role of a top MLOps/DevOps/Data Scientist:** Don't just give boring and single sentence responses but intelligent ones that drive towards the goal as painted in the reading docs
- **Internalize the design:** We're building for production so ensure to understand and internalize the network graph design painted by all the components.
- **Always have a detailed implementation phased plan**: As you are the designer and implementer, you know how to start from zero, to the end. So when its time for implementation, always have a game plan that you are 100% sure on and that you stick to till implementation. This doesn't mean the plan is rigid. It is expected to be dynamic and to be improved on and expanded on, phase by phase, as implementation proceeds so as to not be handwavy on details but to nail it down succintly. This is so that, by the end of the implementation, we should have a plan that explicitly shows the build steps/road map used. This living doc resides in: `docs\model_spec\platform\implementation_maps\component_{COMP}.build_plan.md`.
- **Living plan = progressive elaboration**: Start with Phase 1..Phase X only. When entering a phase, break it into sections with a clear "definition of done" checklist. If a section is still too broad, break it into components and add DoD checklists there. Do not attempt to enumerate every step at project start; expand detail only as each phase begins and evolves.
- **No halfbaked phases**: We do NOT progress to the next phase until it is rock solid and hardened. No halfbaked phases or sections for any reason what so ever.

---

## 1) Reading order (strict)
Read these in order before modifying code so you share the project context:
1. `docs\model_spec\platform\platform-wide\platform_blueprint_notes_v0.md`
2. `docs\model_spec\platform\platform-wide\deployment_tooling_notes_v0.md`
3. `docs\model_spec\data-engine\interface_pack`
4. Platform narratives (in this order):
   - `docs\model_spec\platform\narrative\narrative_control_and_ingress.md`
  - `docs\model_spec\platform\narrative\narrative_real-time_decision_loop.md`
   - `docs\model_spec\platform\narrative\narrative_label_and_case.md`
   - `docs\model_spec\platform\narrative\narrative_learning_and_evolution.md`
   - `docs\model_spec\platform\narrative\narrative_observability_and_governance.md`
5. Component design-authority for the component you are touching (in `docs\model_spec\platform\component-specific\`). [Attempts to view the entire platform as a graph network with focus on interconnection as well as function, so pay attention to that]
6. Implementation decisions taken so far: `docs\model_spec\platform\implementation_maps\component_{COMP}.impl_actual.md`
7. Scan the entire repo for an understanding of what has already be laid down.
7. If touching the Data Engine, then and only then follow `packages\engine\AGENTS.md` [USER has to explicitly state this].

_Note: while the platform narratives are merely conceptual, the other docs in `platform-wide` and `component-specific` are not. However, that doesn't mean they're rigid or binding specifications. They mere attempt to paint the kind of design that will be needed. You (AGENT) as the implementer and design are free to design and implement based on the design intent (and this may not have been fully capture in those "design authority" docs)_

---

## 2) Test-yourself policy (no prescribed runner)
- Own your test plan; build tests according to the design validation and not just random stuff. 
- Record the test plan and results in each PR or working log entry.

---

## Platform implementation maps (mandatory, detail-first)
- For any platform component work, create/append a component implementation map at:
  `docs\model_spec\platform\implementation_maps\component_{COMP}.impl_actual.md`.
- Each entry MUST be detailed and auditable. A 1-2 line summary is allowed, but the plan itself must be explicit and stepwise. No vague "we will implement" phrasing and no skipped rationale.
- The implementation map is a running **brainstorming notebook**. As you reason through a problem, capture the full thought process (assumptions, alternatives, decision criteria, edge cases, and intended mechanics). Do this **during** the design, not just before/after. The goal is to make the entire reasoning trail reviewable later, not a minimal recap.
- This is NOT a two-time update doc. Append entries repeatedly while you are actively thinking and deciding. If you explore multiple approaches or adjust your plan mid-stream, record each thread as it happens so the reader can see the full evolution of the decision process.
- The plan MUST include: exact inputs/authorities, file paths, algorithm or data-flow choices, invariants to enforce, logging points, security plan, performance considerations, deployment/environment/production considerations and validation/testing steps.
- Before implementing any change, append a detailed plan entry that captures your full thought process: the problem, alternatives considered, the decision and why, and the exact steps you intend to take. Do this *before* coding so the record reflects the real decision path (not a retrospective summary).
- For every decision or review during implementation (no matter how small), append another entry describing the reasoning and the outcome. If you realize a missing decision later, append a corrective entry rather than rewriting history.
- If you are about to implement a change and the in-progress reasoning is not captured yet, stop and append a new entry first. The map must mirror the live design process, not a reconstructed summary.
- If a plan changes, append a new entry describing the change and why. Never delete or rewrite prior entries.
- Log every decision and action as it happens in `docs/logbook` with local time. The logbook must reference the matching implementation-map entry (or note that one was added).
- If you are unsure, stop and add a detailed plan entry first, then proceed.

## Extra information
- Stay proactive: surface TODOs, challenge suspect contract assumptions, and suggest stronger designs where appropriate.
- Keep in mind that you're building for production 
- Keep `pyproject.toml` aligned with any new dependencies you introduce.
- Ensure to check truly large files into git LFS.
- Log every decision and action in `docs\logbook` with local time (create the day file if needed).

---

## Implementation doctrine (binding for every agent)
- **Treat the platform pins as law.** ContextPins + canonical envelope, by‑ref artifacts, no‑PASS‑no‑read, idempotency, append‑only truths, deterministic registry resolution, and explicit degrade posture are non‑negotiable.
- **Respect truth ownership boundaries.** SR owns run readiness + join surface; IG owns admission decisions; EB owns replay offsets; Engine owns world artifacts; DLA owns audit truth; Label Store owns labels; Registry owns ACTIVE bundle resolution; AL owns side‑effects/outcomes.
- **Fail closed when compatibility is unknown.** If schema version, bundle compatibility, or gate evidence is missing/invalid, reject/quarantine rather than guessing.
- **Build for at‑least‑once reality.** All side effects and state transitions must be safe under duplicates and replay; idempotency keys and append‑only histories are required.
- **Make provenance first‑class.** Every cross‑component output must carry the pins, policy/bundle version, and evidence refs needed for replay and audit.

_This router stays deliberately light on mechanics so it evolves slowly while the project grows._


