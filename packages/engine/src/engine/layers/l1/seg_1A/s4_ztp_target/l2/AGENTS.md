# AGENT BRIEF - S4 ZTP TARGET L2

Purpose: Orchestrate the ZTP sampling by combining IO, kernels, and RNG streams to produce foreign-country counts and diagnostics.

Guidance for future agents:
- Ensure RNG seeds derive from manifest fingerprints for reproducibility.
- Apply retry logic and log each attempt before giving up at the hard cap.
- Emit metrics consumed by later weight-selection states.

