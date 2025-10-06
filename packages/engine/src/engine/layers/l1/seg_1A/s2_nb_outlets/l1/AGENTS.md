# AGENT BRIEF - S2 NB OUTLETS L1

Purpose: Host the pure negative binomial kernels that compute mu and phi and prepare Poisson or Gamma samples for outlet counts.

Guidance for future agents:
- Implement deterministic kernels and expose hooks for unit tests with seeded RNG.
- Accept well-typed feature vectors; return structures consumed by L2.
- Document parameter expectations inline with references to the spec.

