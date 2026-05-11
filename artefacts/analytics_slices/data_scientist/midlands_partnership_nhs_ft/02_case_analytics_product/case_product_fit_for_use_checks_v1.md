# Case Product Fit-for-Use Checks v1

Purpose:
- record the key bounded-slice checks that justify using `case_id` as the product grain for this slice

Case-grain viability:
- `361,504` distinct `case_id`
- `361,504` distinct linked `flow_id`
- average chronology rows per case: `2.61`
- maximum chronology rows per case: `6`
- average distinct flows per case: `1.00`
- maximum distinct flows per case: `1`
- cases with multiple linked flows: `0`
- flows with multiple linked cases: `0`

Key coverage:
- null `case_id` rows in chronology: `0`
- null `flow_id` rows in chronology: `0`
- cases with all linked flows present in anchor: `361,504`
- cases with all linked flows present in truth: `361,504`
- cases with all linked flows present in bank view: `361,504`

Analytical base checks:
- analytical base rows: `361,504`
- duplicate case rows in analytical base: `0`
- null case rows in analytical base: `0`
- null flow rows in analytical base: `0`
- negative lifecycle rows: `0`
- non-null target rows: `361,504`
- non-null bank-view rows: `361,504`

Downstream-output checks:
- model-ready rows: `361,504`
- model-ready distinct case ids: `361,504`
- reporting-ready rows: `361,504`
- reporting-ready distinct case ids: `361,504`

Interpretation:
- within the bounded slice, the chosen case product grain is stable enough to support one analytical base and two downstream consumers
- the major trust risk for this slice was whether case-to-flow attachment would duplicate or drop records
- that risk did not materialise in the bounded slice
