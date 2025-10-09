# AGENT BRIEF - REGISTRY

Purpose: Maintain registries for artefacts, parameters, and state entry points so the engine can discover implementations at runtime.

Guidance for future agents:
- Update registry tables whenever new layers or segments unlock.
- Keep registration declarative and avoid executing heavy logic at import time.
- Document each registry key and its owning spec for auditing.

