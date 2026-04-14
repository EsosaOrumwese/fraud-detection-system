# Ruleset Comparison Note

The first-pass comparison stays on two postures:
- baseline: `bank_view_true` selecting `4,018,508` flows
- preferred: `bank_view_true AND amount < 50` selecting `3,507,008` flows

The preferred posture cuts `511,500` selected flows, a `12.73%` reduction versus the broad bank-view gate.
It also increases fraud-truth yield from `12.06%` to `12.37%`.