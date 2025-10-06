# AGENT BRIEF - S1 HURDLE L3

Purpose: Validate hurdle outputs by replaying logits, probabilities, and RNG draws to prove the recorded decisions.

Guidance for future agents:
- Treat inputs as read-only and only raise validation errors.
- Compare recomputed values to stored artefacts with strict tolerances.
- Capture diagnostics that help identify coefficient or seed drift quickly.

