# AGENT BRIEF - ENGINE

Purpose: Anchor the runtime surface for the closed-world data engine. This directory wires shared registries, layer bootstrapping, and CLI exposure so state teams can work against stable contracts.

Guidance for future agents:
- Read packages/engine/AGENTS.md before editing here.
- Keep imports light and reuse utilities from core rather than duplicating logic.
- Register new entry points through the registry or CLI packages instead of ad-hoc globals.

