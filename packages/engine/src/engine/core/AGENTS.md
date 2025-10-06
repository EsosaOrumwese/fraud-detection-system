# AGENT BRIEF - CORE

Purpose: Provide shared primitives such as manifest helpers, RNG utilities, and config loading used across layers and services.

Guidance for future agents:
- Keep APIs pure where possible and avoid pulling in layer-specific dependencies.
- Add focused unit tests for new helpers with deterministic fixtures.
- Update docstrings to reference the governing specs when you encode contract rules.

