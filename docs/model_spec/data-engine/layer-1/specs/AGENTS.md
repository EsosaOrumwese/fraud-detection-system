# AGENTS.md — Data-Engine Specs Router

- Editing this `specs/` tree is **locked** unless the USER explicitly says we're working on specifications.
- When spec work is approved, keep all changes inside `specs/` (state-flow, contracts, policies, deployment). Engine source, tests, or configs outside this tree remain off-limits.
- Deprecated folders: `data-intake/`, `pseudocode-set/`. Leave them untouched; they exist for historical reference only.
- `deployment/` may later house workflows but is currently informational.
- Keep specs minimal: describe intent, interfaces, and evidentiary outputs. Save efficiency/memory strategies for implementation phases. Stay familiar with the live engine, contracts, and workflow so specs track the system we actually run.
