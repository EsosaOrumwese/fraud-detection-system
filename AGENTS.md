# AGENTS.md — Router for the Closed-World Enterprise Fraud System
_As of 2025-10-06_

This file is router that firstly routes you to where to find the context of this project and its components, and two points to which component we're building currently

---

## 0) Scope (current focus)
- We are currently building the data engine.
- Other services/packages (apart from contracts) exist but are **LOCKED** for code changes (see their nested `AGENTS.md`).
- NOTE: If need be and you need to access a locked section/folder, let the USER know so the USER can UNLOCK it for you to go ahead. State your reason and the USER will it grant or deny you permission to unlock it.
---

## 1) Reading order (strict)
Read in this exact order before changing anything. This gives you the conceptual overview of the project and its components:

1. `docs/references/closed-world-enterprise-conceptual-design*.md`
2. `docs/references/closed-world-synthetic-data-engine-with-realism*.md` [building focus at the momemnt]

## 2) Project Components

A. Data engine: Refer now to `packages/engine/AGENTS.md` as this is currently the building focus


## 3) Test-yourself policy (no prescribed runner)
- Ensure to robustly test yourself as any little mistake could cause the entire system to break
- Execution details (how to run tests) are up to you; keep runs **deterministic**.
- Document the **test plan** and outcomes in your PR.

---

## 4) Restructuring policy (engine only)
- You may reorganize **`packages/engine/**`** to improve clarity and progress.
- If you do:
  - Update the simple reposity layout in the root level README file.
  - Include a brief **migration note** (old → new paths, rationale).

---

## Extra information
- Ensure that we're always using best practices and that you're entire code is efficient (in every way possible).
- Ensure you're proactive, thinking ahead as a software engineer and not just depending on me to guide you every step of the way. This means suggesting TODOs where neccesary or not overrelying on a faulty contractual implementation but rather understanding the implementation goal and working towards the best way to acheive it.
- As we build each component of the project, always remember how it fits into the enterprise system thereby ensuring that we're building with that goal in mind. 
- Ensure to add comments (not too much though) where necessary, so that a human can easily scan through it and understand what's going on in the code.
- You are to also manage the `pyproject.toml` file to ensure that it's up to date with the dependencies used during our implementation.

_This file is intentionally light on mechanics and heavy on routing, so it won’t drift as the project grows._
