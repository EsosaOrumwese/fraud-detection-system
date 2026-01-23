# AGENT BRIEF – CONFIG

Mission: Maintain the canonical, non-secret configuration catalogue for the platform. Everything under `config/` is authoritative and must match the `docs/model_spec` contract paths.

Guidance for future agents:
- Keep secrets out of this tree; reference external secret stores instead.
- Document every new file with who consumes it, how validation happens, and which run or contract pins it.
- Preserve compatibility with scenario runner and CLI tooling when adjusting defaults (update run configs/tests alongside policy changes).
- Version any generated artefacts (e.g., model exports) under the layer-scoped hierarchy (e.g., `layer1/1A/models/<name>/exports/version=*/`) to keep deterministic replay intact.
