# AGENTS.md - Router for the Closed-World Enterprise Fraud System
_As of 2025-01-10_

Use this to orient yourself before touching code. It captures what is in scope, what to read first, and where the detailed routers live.

---

## 0) Scope (current focus)
- **Build sequencing:** Engine specs are complete for layer-1 (1A-3B), layer-2 (5A-5B), and layer-3 (6A-6B). After the conceptual reading order, follow `packages\engine\AGENTS.md`.
- For now, all other components of the fraud enterprise platform are not yet built.

---

## 1) Reading order (strict)
Read these in order before modifying code so you share the project context:
1. `docs/references/closed-world-enterprise-conceptual-design*.md`
2. `docs\model_spec\data-engine\layer-1\narrative\narrative_1A-to-3B.md` 
3. `docs\model_spec\data-engine\layer-2\narrative\narrative_5A-and-5B.md`
4. `docs\model_spec\data-engine\layer-3\narrative\narrative_6A-and-6B.md`

---

## 2) Test-yourself policy (no prescribed runner)
- Own your test plan; build tests according to the design validation and not just random stuff. 
- Record the test plan and results in each PR or working log entry.

---

## Extra information
- Stay proactive: surface TODOs, challenge suspect contract assumptions, and suggest stronger designs where appropriate.
- As it's very difficult to know your approach to implementation. Ensure in high detail and for auditability, ensure you create a file in `docs\model_spec\data-engine\implementation_maps` called segment_{SEG}.impl_actual.md. You will section it according to the states there in that segment. For every single design element that you want to tackle in a state, you document what that design problem is in summary, but in detail, you articulate your plan to resolve it. Even if you have lots of trials, you append it to the previous and don't remove the former. This is very essential (especially the detail) so the USER can review your thought process and suggests improvements where necessary. Remember, your decisions or plans aren't to be summarized there but to be dropped in detail
- Keep `pyproject.toml` aligned with any new dependencies you introduce.
- Ensure to check truly large files into git LFS
- Kindly note that the makefile calls for the engine is in no way binding. You are free to remove it and put yours. Do not try to reverse engineer it and code around it. Work with yours and replace the old stuff there
- As we build this project, constantly update the makefile so the USER will find it easy to run these processes that involve long CLI commands. Also try to make the Makefile human readable.
- When working on a task, log every decision and action taken (not just the summary at the end) in the associated logbook in `docs\logbook` ensuring that you use one with the actual local date (if none exist, create one in the same format as the other logs) and log at the local time and not any random time. This will allow the USER to review the AGENTS actions and decisions
- Ensure to employ the use of loggers in your implementation. Whilst the USER doesn't want to be spammed with logs, it's important that whilst having a heartbeat log, there's a log that gives information (with appropriate states) of what's going on in every process (and not just start and completed) such that at no point is console blank and the USER left confused on whether the run is hanging or not

---

## Implementation doctrine (binding for every agent)
- **Chase project outcomes, not verbatim spec text.** Specs capture intent; if the implementation path in the doc would violate determinism, performance, or robustness targets, design a compliant alternative and call it out in the logbook before landing changes. Deviations must still honour the published contracts.
- **Engineer for efficiency from day zero.** Profile early, stream large artefacts, and design kernels that cope with the actual data volumes (Segment 1B S1 is your cautionary tale). Aim for multi-minute, not multi-hour, execution envelopes.
- **Control memory usage deliberately.** Prefer chunked/iterator-based flows, deterministic temp directories, and spill-to-disk patterns over loading entire datasets into RAM. Treat OS-level crashes or thrash as regressions.
- **Build for resumability.** Leverage run receipts, `_passed.flag`, and determinism records so the orchestrator can skip completed states, resume at the point of failure, or clearly instruct the operator how to recover.
- **Instrument heavy paths.** Add structured logging around long-running loops and RNG envelopes so operators can observe progress in real time.
- **Protect reproducibility.** Deterministic artefacts must hash identical across seeded runs. Volatile metadata (timestamps, `run_id`, temp paths) should be isolated from comparisons or normalised through tooling.

_This router stays deliberately light on mechanics so it evolves slowly while the project grows._
