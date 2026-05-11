# Governed Model Use Case v1

Selected bounded use case:
- predict authoritative fraud truth at `flow_id` level for prioritisation support

Allowed use:
- rank or band flows for human-led review prioritisation
- support decision preparation rather than autonomous adjudication

Explicit non-use:
- no standalone automated decisioning
- no truth-only or post-outcome fields as live-like features
- no bank-view field as the target

Bounded governed evidence:
- `flow_rows`: 3,455,613
- `fraud_truth_rate`: 2.70%
- `bank_view_rate`: 5.72%
- `truth_bank_mismatch_rate`: 7.15%
