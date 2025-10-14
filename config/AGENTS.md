# AGENT BRIEF – CONFIG

Mission: Maintain the canonical, non-secret configuration catalogue for the platform. Everything under `config/` is now authoritative (the old `configs/` tree has been merged here).

Guidance for future agents:
- Keep secrets out of this tree; reference external secret stores instead.
- Document every new file with who consumes it, how validation happens, and which run or contract pins it.
- Preserve compatibility with scenario runner and CLI tooling when adjusting defaults (update run configs/tests alongside policy changes).
- Version any generated artefacts (e.g., model exports) under the existing `models/<name>/exports/version=*/` hierarchy to keep deterministic replay intact.
