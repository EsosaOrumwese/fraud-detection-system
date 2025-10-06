# AGENT BRIEF - S1 HURDLE L2

Purpose: Orchestrate the hurdle flow by combining IO and kernels, performing the Bernoulli draw, and routing singles versus multis to the appropriate next states.

Guidance for future agents:
- Ensure RNG usage stays reproducible and derived from the manifest fingerprint.
- Emit audit logs for every decision path.
- Guard idempotency so reruns do not redraw already sealed merchants.

