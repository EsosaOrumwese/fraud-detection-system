# Flow Quality Operational Impact - v1

As of `2026-04-03`

The defect in this slice is not abstract hygiene. It changes operational interpretation.

## Overall case-selected yield

Test window:
- raw bank-view reading: `54.95%`
- corrected authoritative-truth reading: `19.51%`
- inflation: `2.82x`

Operational implication:
- a team reading bank view as authoritative would believe case-selected workload is far more fraud-productive than it actually is

## `opened_only` pathway stage

Test window:
- raw bank-view reading: `64.62%`
- corrected authoritative-truth reading: `0.23%`
- inflation: `277.57x`

Operational implication:
- this stage would look highly valuable if the wrong surface were used
- in reality, it is almost entirely low-yield from the perspective of authoritative fraud truth

## `chargeback_decision` pathway stage

Test window:
- raw bank-view reading: `33.74%`
- corrected authoritative-truth reading: `95.83%`
- understatement: `62.08` percentage points

Operational implication:
- the same misuse can also hide high-value work
- a downstream reader could under-prioritise the most fraud-positive stage because the comparison-only bank view understates authoritative truth there

Decision risk if ignored:
- false pressure would be assigned to low-value workload
- genuine high-value pathway stages could be under-read
- model and reporting consumers would inherit unstable or misleading outcome interpretation
