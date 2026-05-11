# Flow Quality Fit For Use - v1

As of `2026-04-03`

Scope:
- bounded 20-part governed slice from `runs/local_full_run-7`
- analytical grain: `flow_id`
- governed path: event -> flow -> case -> outcome
- downstream consumer family: flow-level risk, cohort, and KPI interpretation

Fit-for-use verdict:
- the chosen path is fit for this slice
- linkage quality is clean enough to support a semantic quality problem rather than a join-integrity problem

Key checks:
- `3,455,613` distinct event flows in scope
- `361,504` case-selected flows in scope
- `0` flows with multiple case IDs
- `0` event flows missing truth rows
- `0` event flows missing bank-view rows
- `0` duplicate truth rows
- `0` duplicate bank-view rows

Interpretation:
- the path itself is stable enough to support trusted comparison
- the strongest defect in this slice is therefore not broken linkage
- the strongest defect is outcome-surface misuse: a comparison-only bank-view field can materially distort yield KPIs if it is treated as authoritative
