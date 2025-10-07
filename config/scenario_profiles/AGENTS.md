# AGENT BRIEF - SCENARIO PROFILES

Purpose: Describe runnable scenario profiles—seeded bundles of config that orchestrate which layers, policies, and services activate during simulations.

Guidance for future agents:
- Align profile structure with the scenario runner expectations before adding new keys.
- Reference contract or policy versions explicitly so replays are reproducible.
- Keep profiles small and composable; factor shared defaults into the parent config folder.
