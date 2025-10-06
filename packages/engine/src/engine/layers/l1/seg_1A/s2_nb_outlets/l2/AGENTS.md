# AGENT BRIEF - S2 NB OUTLETS L2

Purpose: Orchestrate negative binomial sampling by wiring IO, kernels, and retry logic until counts of at least two are produced.

Guidance for future agents:
- Centralise rejection handling and log each attempt for validation.
- Maintain stable ordering between input merchants and outputs.
- Surface metrics needed by later states, including mean, dispersion, and rejection rate.

