# AGENT BRIEF - CONFIG

Purpose: Hold repository-wide configuration that is safe to version-control: environment descriptors, policy toggles, and defaults shared across services and the data engine.

Guidance for future agents:
- Keep secrets out of this tree; reference external secret stores instead.
- Document every new file with who consumes it and how validation happens.
- Preserve compatibility with scenario runner and CLI tooling when adjusting defaults.

