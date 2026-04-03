# Population Cohort Rules v1

Purpose:
- define the compact cohort framework used in the bounded population-pathway slice
- keep the cohort story stable across outputs

Population for cohorting:
- only case-selected flows (`is_case_selected = 1`)
- non-case flows remain in the population and pathway outputs, but not in the four-case cohort framework

Inputs used:
- authoritative fraud truth
- case lifecycle hours

Threshold logic:
- positive-yield lifecycle threshold:
  - median `lifecycle_hours` among case-selected flows where `target_is_fraud_truth = TRUE`
- low-yield lifecycle threshold:
  - median `lifecycle_hours` among case-selected flows where `target_is_fraud_truth = FALSE`

Cohort definitions:
- `fast_converting_high_yield`
  - `target_is_fraud_truth = TRUE`
  - `lifecycle_hours <= positive-yield median`
- `slow_converting_high_yield`
  - `target_is_fraud_truth = TRUE`
  - `lifecycle_hours > positive-yield median`
- `high_burden_low_yield`
  - `target_is_fraud_truth = FALSE`
  - `lifecycle_hours > low-yield median`
- `low_burden_low_yield`
  - remaining case-selected flows

Why this cohort family was used:
- it is computable from the bounded linked slice
- it supports direct comparison of burden, conversion timing, and outcome value
- it is easier to translate into an operational problem statement than abstract labels alone

Observed test-split distribution:
- `fast_converting_high_yield`: `7,212` flows
- `slow_converting_high_yield`: `7,156` flows
- `high_burden_low_yield`: `29,675` flows
- `low_burden_low_yield`: `29,601` flows

Usage boundary:
- these rules are retrospective analytical cohorts for the bounded slice
- they are not a production policy or a live triage rule
