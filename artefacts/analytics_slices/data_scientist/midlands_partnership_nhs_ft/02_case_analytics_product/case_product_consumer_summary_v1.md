# Case Product Consumer Summary v1

Purpose:
- show one real analytical consumer of the engineered case product without turning the slice into a modelling-first programme

Consumer used:
- pathway-stage segmentation over `case_reporting_ready_v1`

Why this consumer:
- it proves the reporting-ready product can support real analytical comparison
- it uses the engineered stage and lifecycle outputs directly
- it stays aligned to the responsibility, which is analytical-product design and usability rather than model maximisation

Observed bounded-slice pathway pattern:

Test split:
- `opened_only`: `53,539` cases, fraud-truth rate `0.23%`, bank-positive rate `64.50%`
- `chargeback_decision`: `10,311` cases, fraud-truth rate `95.79%`, bank-positive rate `33.64%`
- `customer_dispute`: `5,494` cases, fraud-truth rate `66.49%`, bank-positive rate `12.94%`
- `detection_event_attached`: `2,956` cases, fraud-truth rate `15.36%`, bank-positive rate `31.43%`

Validation/test consistency:
- the same pathway-stage ordering is preserved across train, validation, and test
- `chargeback_decision` is the highest-yield stage
- `customer_dispute` is materially elevated relative to `opened_only`
- `opened_only` is high-volume but very low fraud-truth yield

Why this matters:
- the engineered product supports more than storage or transformation
- it supports immediate downstream segmentation and prioritisation thinking
- that is enough to prove the product is analytically useful without dragging the slice back into a full modelling programme
