# AGENT BRIEF - S4 ZTP TARGET L3

Purpose: Validate the ZTP outputs by replaying lambda calculations, retries, and final counts to guarantee the stored results are reproducible.

Guidance for future agents:
- Run in read-only mode and compare recomputed values against persisted artefacts.
- Fail closed on any seed or hyperparameter mismatch.
- Produce diagnostics files that help trace sparse edge cases.

