# Branch Investigation: Behavioural Stream Event Grammar and Grain

## Branch question

The main behavioural-stream investigation established that `s2_event_stream_baseline_6B` and `s3_event_stream_with_fraud_6B` are not arrival skeletons. They are platform traffic streams. This branch asks the next grain question:

> What does one behavioural-stream row represent, and how should `flow_id`, `event_seq`, and `event_type` be read before we compute rates, volumes, fraud shares, or downstream joins?

The short answer is that one row is one authorization event side, not one business flow. The stream presents a two-side authorization grammar:

1. `event_seq = 0`, `event_type = AUTH_REQUEST`
2. `event_seq = 1`, `event_type = AUTH_RESPONSE`

That means event-row counts are twice the implied authorization-flow count under the stream contract. Any later analysis that wants flow-level behaviour must collapse or select the request/response side deliberately; any analysis that stays at event-row grain must be explicit that it is measuring platform event traffic, not unique flows.

## Evidence used

Primary report:

- [`behavioural_streams_investigation.md`](../behavioural_streams_investigation.md)

Branch script:

- [`analyze_behavioural_event_grammar_and_grain.py`](../../../../scratch/analyze_behavioural_event_grammar_and_grain.py)

Branch exports:

- [`stream_event_flow_grain.csv`](../../../../exports/interface_world/behavioural_streams/branches/event_grammar_and_grain/stream_event_flow_grain.csv)
- [`event_seq_type_shape.csv`](../../../../exports/interface_world/behavioural_streams/branches/event_grammar_and_grain/event_seq_type_shape.csv)
- [`amount_surface_by_event_side.csv`](../../../../exports/interface_world/behavioural_streams/branches/event_grammar_and_grain/amount_surface_by_event_side.csv)
- [`fraud_balance_by_event_side.csv`](../../../../exports/interface_world/behavioural_streams/branches/event_grammar_and_grain/fraud_balance_by_event_side.csv)
- [`baseline_overlay_key_fingerprint.csv`](../../../../exports/interface_world/behavioural_streams/branches/event_grammar_and_grain/baseline_overlay_key_fingerprint.csv)
- [`event_grammar_and_grain_summary.json`](../../../../exports/interface_world/behavioural_streams/branches/event_grammar_and_grain/event_grammar_and_grain_summary.json)

The branch deliberately uses compact exports from the main behavioural-stream pass rather than performing another full raw-stream materialization. A full exact flow-pair self-join across the whole stream would be expensive and is not needed for the branch's immediate grain finding. The claims here are therefore framed around the exact row/sequence balances, the contract grammar, the fraud-flow checks already performed in the main investigation, and the existing stream fingerprint evidence. Where the evidence is aggregate rather than pairwise, the report says so explicitly.

## One row is an event side, not a flow

Both streams have the same event-grain shape:

| Stream | Event rows | Request rows | Response rows | Request minus response | Implied flows | Event rows per implied flow |
|---|---:|---:|---:|---:|---:|---:|
| `baseline` | `473,383,388` | `236,691,694` | `236,691,694` | `0` | `236,691,694` | `2.0` |
| `with_fraud` | `473,383,388` | `236,691,694` | `236,691,694` | `0` | `236,691,694` | `2.0` |

This is the first discipline point. The stream is not one row per transaction-flow in the way a business analyst might casually say "transactions." It is one row per authorization event side. The row count is doubled under the declared grammar: the stream has one request-side population and one response-side population of the same size.

That does not make the doubling an error. In a live fraud decisioning platform, the request and response phases are different operational moments. The request side is what the decisioning path sees as the authorization comes in. The response side records the outcome-side event in the stream grammar. The contract says these sides belong to the same flow identity, but they remain separate stream events.

The consequence is straightforward:

- If the question is "how many event messages moved through the platform?", use event-row grain.
- If the question is "how many authorization flows occurred?", collapse to flow grain or select one event side under the declared request/response grammar.
- If the question is "what share of flows were fraudulent?", do not use raw event rows unless the numerator and denominator both preserve the same two-event grammar.
- If the question is "what did the RTDL path see as traffic?", event grain may be the correct operating view because event messages are what the stream carries.

## `event_seq` and `event_type` form a fixed grammar

The grammar is exact in both streams:

| Stream | `event_seq` | `event_type` | Rows | Row share |
|---|---:|---|---:|---:|
| `baseline` | `0` | `AUTH_REQUEST` | `236,691,694` | `50.0%` |
| `baseline` | `1` | `AUTH_RESPONSE` | `236,691,694` | `50.0%` |
| `with_fraud` | `0` | `AUTH_REQUEST` | `236,691,694` | `50.0%` |
| `with_fraud` | `1` | `AUTH_RESPONSE` | `236,691,694` | `50.0%` |

There are only two sequence values: `0` and `1`. There are only two event types: `AUTH_REQUEST` and `AUTH_RESPONSE`. At the aggregate stream level, the mapping is stable: `0` is request, and `1` is response.

This means `event_seq` is not just a row-order decoration. It is part of the event identity and part of the stream contract. `flow_id` identifies the flow handle, while `event_seq` identifies the side of the flow. Treating `flow_id` alone as unique would be a grain error because the declared key requires `event_seq` to distinguish event rows.

The contract read supports the same point. The primary key includes:

`seed + manifest_fingerprint + scenario_id + flow_id + event_seq`

The join key adds `parameter_hash`:

`seed + manifest_fingerprint + parameter_hash + scenario_id + flow_id + event_seq`

So the platform's own identity contract says that `event_seq` is required to distinguish rows. A downstream join that drops `event_seq` will risk turning a one-row event join into a two-row flow join.

## Approximate flow counts should not be used as exact flow counts

The earlier broad profile exported an `approx_flows` field from `approx_count_distinct(flow_id)`. In this branch, that field is useful only as a rough profiling signal. It should not be read as the true flow count.

The approximate estimator reports about `244.2M` flows for each event side, while the sequence-balanced row count gives `236,691,694` implied authorization flows under the stream grammar. The latter is the cleaner operating number for this branch because it comes from the observed request/response row balance and the declared two-side event contract.

This matters because the difference should not be interpreted as fraud-platform behaviour. The `approx_flows` field came from an approximate distinct-count estimator, so it is not suitable as the business-facing flow count here. If a later report says there are `244.2M` flows, it would be importing profiling noise into a place where the grammar already gives us a cleaner count.

The discipline is:

- Use `473,383,388` when discussing event rows.
- Use `236,691,694` when discussing implied authorization flows.
- Avoid using `approx_flows = 244,190,267` as a business-facing flow count.

## The aggregate amount surface is mirrored across the two event sides

The request and response sides have the same broad aggregate amount surface:

| Stream | Event type | Rows | Mean amount | Median amount | Maximum amount |
|---|---|---:|---:|---:|---:|
| `baseline` | `AUTH_REQUEST` | `236,691,694` | `24.3127` | `14.99` | `3,401.78` |
| `baseline` | `AUTH_RESPONSE` | `236,691,694` | `24.3127` | `14.99` | `3,401.78` |
| `with_fraud` | `AUTH_REQUEST` | `236,691,694` | `24.3137` | `14.99` | `3,401.78` |
| `with_fraud` | `AUTH_RESPONSE` | `236,691,694` | `24.3137` | `14.99` | `3,401.78` |

The important point is not that request and response are economically different. At aggregate level, the amount field is present on both sides of the authorization grammar and has the same broad distribution on request and response rows. That is useful operationally because both event sides can stand as event messages with the economic signal present.

But it creates an analytical trap. The branch evidence proves aggregate mirroring, not pairwise equality for every `flow_id`. Even with that limitation, the correct discipline is clear: do not sum both request and response sides as if they were independent business transactions. That may be valid if the question is "amount-bearing event payload passing through the stream," but it is unsafe if the question is "transaction value processed by the business." For business-value questions, the analysis should collapse to flow grain, explicitly choose one event side, or run a dedicated pairwise amount check before making a total-value claim.

This is one of the clearest examples of why grain is not a cosmetic concern. The same field, `amount`, means different things depending on whether the denominator is event messages or flows.

## Fraud marking preserves the two-sided grammar

Fraud marking in the post-overlay stream is also balanced across the two event sides:

| Event sequence | Event type | Fraud flag | Rows | Share within event type |
|---:|---|---|---:|---:|
| `0` | `AUTH_REQUEST` | `false` | `236,684,562` | `99.996987%` |
| `0` | `AUTH_REQUEST` | `true` | `7,132` | `0.003013%` |
| `1` | `AUTH_RESPONSE` | `false` | `236,684,562` | `99.996987%` |
| `1` | `AUTH_RESPONSE` | `true` | `7,132` | `0.003013%` |

This matters because fraud could have appeared as a one-sided marker. For example, a weaker stream contract might mark only the request row or only the response row. That is not what we see here. At aggregate level, the same number of fraud-marked rows exists on the request side and on the response side.

The main behavioural-stream report also performed the stronger per-fraud-flow check: `7,132` fraud flows have exactly two fraud-marked events each, with `0` nonstandard fraud-flow shapes. That lets us read the fraud-marked subset at either event grain or flow grain as long as we respect the two-event multiplier:

- fraud event rows: `14,264`
- fraud flows: `7,132`
- fraud rows per fraud flow: `2`

So a raw fraud-row count is not wrong, but it is an event count. For the fraud-marked subset, the checked fraud-flow shape shows that the flow count is half of the fraud-event count because the overlay marks both sides of the same authorization flow.

## Baseline and post-overlay streams keep the same event-key shape

The broad key-fingerprint export shows the same row count and the same `flow_id + event_seq` hash fingerprint for baseline and post-overlay streams:

| Stream | Rows | Key hash fingerprint |
|---|---:|---:|
| `baseline` | `473,383,388` | `4.365982797643315e+27` |
| `with_fraud` | `473,383,388` | `4.365982797643315e+27` |

This is supporting evidence that the overlay is not changing the event grammar or appending an additional traffic population. It is best read as a compact key-shape fingerprint: the two streams have the same row count and the same aggregate `flow_id + event_seq` hash sum.

We should not read the fingerprint as a substitute for every possible exact join assertion. The main investigation already checked the fraud-marked rows back to baseline and found that all `14,264` fraud rows match baseline rows on `flow_id + event_seq`, preserve event type, and preserve timestamp. This branch's grain point is narrower: the post-overlay stream should be compared to baseline at the same event-key grain, not as a separate population of extra events.

## Working interpretation

The behavioural stream is a thin, regular authorization-event stream. Its row grain is event side. Its flow grain is the paired request/response authorization flow.

That gives us a strict rule for later analysis:

- Event bus, ingestion-load, stream-volume, and RTDL-message questions can legitimately operate at event-row grain.
- Fraud incidence, transaction value, customer/merchant exposure, and case-level questions usually need flow grain or a clearly chosen event side.
- `flow_id` alone is a flow handle, not a unique event-row key.
- `event_seq` is required for event-row identity.
- `amount` is mirrored across request and response sides at aggregate level, so business-value analysis should choose a side, collapse to flow grain, or run a pairwise amount check before summing both sides.
- Fraud rows are balanced across request and response, and the fraud-marked subset has already passed a per-flow two-event shape check, so fraud-row counts must be translated carefully into fraud-flow counts.

This branch therefore closes the first behavioural-stream denominator issue. Before asking what the stream says about fraud, amount, campaigns, or time, we must decide whether we are reading event traffic or authorization flows.

## Leads carried forward

- The time boundary branch should decide whether reporting windows use request time, response time, flow start, or flow completion, especially because of the small April spillover.
- The overlay branch should inspect baseline-vs-post-overlay changes at event-key grain, not by treating the overlay as a separate event population.
- The amount branch should explicitly separate event-payload amount exposure from deduplicated flow-level transaction value.
- The behavioural-context investigation should test whether context surfaces join cleanly at `flow_id` or require event-side specificity for some joins.
