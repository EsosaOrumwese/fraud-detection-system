# AGENT BRIEF - S3 CROSSBORDER UNIVERSE L0

Purpose: Handle IO for cross-border eligibility, loading policy artefacts and writing eligibility flags for multi-site merchants.

Guidance for future agents:
- Validate policy versions before use and enforce schema contracts on read.
- Keep writes limited to the eligibility surfaces consumed by ZTP stages.
- Capture reasons and rule identifiers for each merchant.

