# Flow Quality Issue Log - v1

As of `2026-04-03`

## FQ-001

Issue:
- bank-view outcome semantics materially diverge from authoritative fraud truth on the case-selected slice

Affected outputs:
- case-selected yield KPI
- pathway-stage yield comparisons
- any downstream risk, cohort, or reporting surface that uses bank view as a stand-in for authoritative outcome

Severity:
- high

Observed evidence:
- test overall case-selected yield:
  - raw bank-view reading: `54.95%`
  - corrected authoritative-truth reading: `19.51%`
  - absolute gap: `35.44` percentage points
- test `opened_only` yield:
  - raw bank-view reading: `64.62%`
  - corrected authoritative-truth reading: `0.23%`
  - absolute gap: `64.39` percentage points
- test mismatch rate across case-selected flows: `62.41%` (`45,960` of `73,644`)

Root-cause reading:
- `s4_flow_bank_view_6B` is not carrying the same business meaning as `s4_flow_truth_labels_6B`
- the strongest mismatch pattern is `truth_negative_bank_positive`
- in the bounded test slice alone, `36,030` case-selected flows were truth-negative but bank-positive
- the crosswalk is dominated by `LEGIT` + `BANK_CONFIRMED_FRAUD`, which shows that bank-positive status cannot be treated as authoritative fraud yield

Immediate action:
- pin `s4_flow_truth_labels_6B` as the authoritative outcome source for yield KPIs
- expose bank view only as a comparison surface

Longer-term fix:
- enforce authoritative-source notes in reporting-ready outputs
- add rerunnable checks that fail review if raw bank-view and authoritative-truth KPI logic are being conflated again
