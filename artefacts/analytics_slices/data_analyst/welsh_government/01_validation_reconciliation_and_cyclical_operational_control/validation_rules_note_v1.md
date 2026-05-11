
# Validation Rules Note v1

Authoritative rule:
- suspicious-to-case conversion remains a flow-based control metric
- numerator: case-opened rows
- authoritative denominator: flow rows

Not allowed in the recurring released view:
- reusing the same numerator against entry-event rows as if it were the same balancing base

Why this matters:
- current authoritative rate: `9.59%`
- current discrepant rate: `4.80%`
- current absolute gap: `+4.80 pp`

Bounded control conclusion:
- recurring release is only safe when the authoritative denominator remains fixed and any alternative denominator is treated as a discrepancy condition
