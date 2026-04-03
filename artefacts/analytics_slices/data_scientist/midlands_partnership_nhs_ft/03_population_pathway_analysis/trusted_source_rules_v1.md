# Trusted Source Rules v1

Purpose:
- pin authoritative-source rules for the bounded population-pathway slice
- prevent downstream outputs from silently drifting across competing meanings

Authoritative sources:
- population entry and event timing:
  - `s2_event_stream_baseline_6B`
- suspicious-pathway entry and case progression:
  - `s4_case_timeline_6B`
- flow context and core linked dimensions:
  - `s2_flow_anchor_baseline_6B`
- authoritative fraud outcome:
  - `s4_flow_truth_labels_6B.is_fraud_truth`
- comparison-only operational outcome:
  - `s4_flow_bank_view_6B.is_fraud_bank_view`

Override rules:
- `CASE_OPENED` is the authoritative marker for entry into the suspicious-pathway subset
- `s4_flow_truth_labels_6B` is the authoritative fraud outcome and is not overridden by bank-view labels
- `s4_flow_bank_view_6B` is comparison-only and should be used to contextualise disagreement or operational divergence, not to redefine truth

Join rules:
- population base joins on `flow_id`
- `case_id` is downstream-only and is sourced from `s4_case_timeline_6B`
- unmatched case fields are allowed for non-case flows
- unmatched truth or bank-view fields are not expected in this bounded slice and would be treated as a trust issue

Observed bounded-slice result:
- event-to-case linked flows: `361,504`
- exact event-to-`CASE_OPENED` timestamp matches: `361,504`
- flows with multiple cases: `0`

Usage boundary:
- these rules are valid only for the bounded 20-part slice
- they should not be promoted to whole-world rules without revalidation
