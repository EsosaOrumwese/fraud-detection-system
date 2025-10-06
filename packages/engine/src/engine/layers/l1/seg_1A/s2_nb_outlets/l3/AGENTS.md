# AGENT BRIEF - S2 NB OUTLETS L3

Purpose: Replay the negative binomial sampling to confirm stored counts, rejection tallies, and parameter usage before cross-border logic runs.

Guidance for future agents:
- Operate in read-only mode; recompute mu and phi and compare with stored values.
- Fail closed on any mismatch and include context to debug RNG divergence.
- Keep tolerance thresholds consistent with the documentation to preserve determinism.

