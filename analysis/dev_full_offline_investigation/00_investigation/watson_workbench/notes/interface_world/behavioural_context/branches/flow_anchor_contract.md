# Branch Investigation: Flow Anchor Contract

## Branch question

The behavioural streams are intentionally thin. They carry the event body:

- `flow_id`
- `event_seq`
- `event_type`
- `ts_utc`
- `amount`
- lineage fields
- post-overlay fraud fields where applicable

This branch asks:

> How do thin event streams recover flow, entity, and amount context through the flow anchors?

The answer is that the flow anchors are the flow-grain context surfaces for the event streams. `s2_event_stream_baseline_6B` is interpreted through `s2_flow_anchor_baseline_6B`; `s3_event_stream_with_fraud_6B` is interpreted through `s3_flow_anchor_with_fraud_6B`. The event streams express the authorization grammar. The anchors carry the one-row-per-flow context needed to make those event rows analytically usable: merchant, arrival, party, account, instrument, device, IP, timestamp, amount, lineage, and post-overlay fraud/campaign fields.

So the anchor contract is not decorative. It is the mechanism that lets a streaming event remain small while still being recoverable into the operating fraud world.

## Evidence used

Primary reports:

- [`../behavioural_context_investigation.md`](../behavioural_context_investigation.md)
- [`../../behavioural_streams/behavioural_streams_investigation.md`](../../behavioural_streams/behavioural_streams_investigation.md)
- [`../../behavioural_streams/branches/baseline_vs_fraud_overlay_contract.md`](../../behavioural_streams/branches/baseline_vs_fraud_overlay_contract.md)

Contract references:

- [`docs/model_spec/data-engine/interface_pack/data_engine_interface.md`](../../../../../../../../docs/model_spec/data-engine/interface_pack/data_engine_interface.md)
- [`docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`](../../../../../../../../docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml)
- [`docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`](../../../../../../../../docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml)
- [`docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`](../../../../../../../../docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml)

Pinned data surfaces:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s2_event_stream_baseline_6B`](../../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s2_event_stream_baseline_6B)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s3_event_stream_with_fraud_6B`](../../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s3_event_stream_with_fraud_6B)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s2_flow_anchor_baseline_6B`](../../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s2_flow_anchor_baseline_6B)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s3_flow_anchor_with_fraud_6B`](../../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s3_flow_anchor_with_fraud_6B)

Branch exports:

- [`event_anchor_field_map.csv`](../../../../exports/interface_world/behavioural_context/branches/flow_anchor_contract/event_anchor_field_map.csv)
- [`event_anchor_pair_profile.csv`](../../../../exports/interface_world/behavioural_context/branches/flow_anchor_contract/event_anchor_pair_profile.csv)
- [`baseline_event_schema.csv`](../../../../exports/interface_world/behavioural_context/branches/flow_anchor_contract/baseline_event_schema.csv)
- [`fraud_event_schema.csv`](../../../../exports/interface_world/behavioural_context/branches/flow_anchor_contract/fraud_event_schema.csv)
- [`baseline_anchor_schema.csv`](../../../../exports/interface_world/behavioural_context/branches/flow_anchor_contract/baseline_anchor_schema.csv)
- [`fraud_anchor_schema.csv`](../../../../exports/interface_world/behavioural_context/branches/flow_anchor_contract/fraud_anchor_schema.csv)

Parent exports reused:

- [`context_key_reconciliation.csv`](../../../../exports/interface_world/behavioural_context/context_key_reconciliation.csv)
- [`fraud_anchor_vs_baseline.csv`](../../../../exports/interface_world/behavioural_context/fraud_anchor_vs_baseline.csv)
- [`fraud_anchor_overlay_summary.csv`](../../../../exports/interface_world/behavioural_context/fraud_anchor_overlay_summary.csv)
- [`fraud_anchor_campaign_summary.csv`](../../../../exports/interface_world/behavioural_context/fraud_anchor_campaign_summary.csv)

This branch uses compact schema, profile, field-map, and key-reconciliation exports. It does not claim that a full row-level event-to-anchor anti-join was completed inside this branch. That full validation is still a useful engineering check, but the current report only makes claims supported by the compact evidence available here.

## What an anchor is in this operating world

A flow anchor is a one-row-per-flow context record.

In the fraud decisioning platform framing, the event stream is what moves through the traffic path. The anchor is the context surface that lets the platform, replay notebook, offline learner, case reviewer, or analyst recover the flow's business and entity meaning.

The baseline pair is:

- event stream: `s2_event_stream_baseline_6B`
- flow anchor: `s2_flow_anchor_baseline_6B`

The post-overlay pair is:

- event stream: `s3_event_stream_with_fraud_6B`
- flow anchor: `s3_flow_anchor_with_fraud_6B`

That pairing matters because the post-overlay world is not just the baseline world with an extra label column. Fraud overlay can change the amount and add campaign/fraud fields. So if a post-overlay event row needs context, it should be read against the post-overlay anchor, not lazily joined to the baseline anchor unless the analytical question is specifically a baseline-versus-overlay comparison.

## Thin stream, thick anchor

The field map shows the contract clearly.

Common fields carried by both stream and anchor:

- `flow_id`
- `amount`
- `ts_utc`
- `seed`
- `manifest_fingerprint`
- `parameter_hash`
- `scenario_id`

Fields carried by the event stream but not the anchor:

- `event_seq`
- `event_type`

Fields carried by the anchor but not the event stream:

- `arrival_seq`
- `merchant_id`
- `party_id`
- `account_id`
- `instrument_id`
- `device_id`
- `ip_id`

Post-overlay fields carried by both post-overlay stream and post-overlay anchor:

- `fraud_flag`
- `campaign_id`

This is the intended split. The stream keeps the moving event grammar: which flow, which event within the flow, what kind of event, when it occurred, and what amount it carried. The anchor keeps the flow's enrichment context: who the flow belongs to, which merchant and entities are attached, which arrival sequence it came from, and which fraud/campaign state applies after overlay.

That means the event stream alone is not enough for most analytics. It can answer traffic-shape questions, but it cannot answer merchant, party, account, device, IP, or arrival-sequence questions without the anchor.

## Shape reconciliation

The compact profile gives the first structural reconciliation:

| Pair | Event rows | Anchor rows | Event rows per anchor row | Event types | Event sequences |
|---|---:|---:|---:|---:|---:|
| Baseline | `473,383,388` | `236,691,694` | `2.0` | `2` | `2` |
| Post-overlay | `473,383,388` | `236,691,694` | `2.0` | `2` | `2` |

This is the core flow/event relationship at aggregate shape. Each anchor row represents a flow, and the stream has exactly two event rows for every anchor row in aggregate: request and response. So the event stream is not missing the entity columns by accident. It is operating at event grain, while the anchor operates at flow grain.

The amount totals also match that grammar:

| Pair | Event total amount | Anchor total amount | Ratio |
|---|---:|---:|---:|
| Baseline | `11.509B` | `5.755B` | `2.0` |
| Post-overlay | `11.510B` | `5.755B` | `2.0` |

The ratio is not a fraud signal. It is the two-event grammar showing up economically. Because both request and response rows carry the flow amount, the event-stream total is approximately twice the anchor total. This is a denominator warning: event-grain amount totals can double the flow-grain economic surface if the request/response pair is not collapsed.

So if we later build stakeholder-facing amount metrics, we need to decide whether the metric is event-exposure or flow-economic value. For fraud-loss, authorization value, or merchant value, the anchor or a flow-collapsed stream is usually the safer denominator.

## Anchor as entity recovery surface

The anchor is where the thin event row gets its operating identity back.

Both anchor surfaces carry:

- `merchant_id`
- `party_id`
- `account_id`
- `instrument_id`
- `device_id`
- `ip_id`

The approximate anchor cardinality profile is the same in the baseline and post-overlay profiles:

| Entity field | Approx distinct count |
|---|---:|
| Merchants | `4,050` |
| Parties | `5.80M` |
| Accounts | `6.14M` |
| Instruments | `5.93M` |
| Devices | `6.45M` |
| IPs | `2.39M` |

This is what makes the anchor operationally important. Without it, the stream can tell us that `flow_id = X` had an authorization request and response. With it, the same flow can be placed into the merchant/customer/device/IP world needed by RTDL enrichment, offline feature work, replay, case review, and entity-level investigation.

The anchor is therefore not only a join convenience. It is the boundary between traffic grammar and fraud-platform context.

## Baseline and post-overlay anchors are the same flow universe

The parent key reconciliation gives strong compact evidence that the baseline and post-overlay anchors are aligned:

| Surface | Rows | Arrival-key hash | Flow-key hash |
|---|---:|---|---|
| `s1_arrival_entities_6B` | `236,691,694` | same as anchors | n/a |
| `s2_flow_anchor_baseline_6B` | `236,691,694` | same as arrival entities | same as post-overlay anchor |
| `s3_flow_anchor_with_fraud_6B` | `236,691,694` | same as arrival entities | same as baseline anchor |

This strongly supports a clear read: the post-overlay anchor is not behaving like a new population of flows. The compact evidence says it carries the same row count and the same flow/arrival key hash surface as the baseline anchor, then modifies selected flow attributes and adds fraud/campaign state.

The parent profiles also show a single pinned lineage context for both anchors: one `seed`, one `manifest_fingerprint`, one `parameter_hash`, and one `scenario_id`. Under that single-context run, the fraud-flow comparison from the parent export confirms the overlay behaviour for the positive class:

| Metric | Value |
|---|---:|
| Fraud flows | `7,132` |
| Matched baseline flows | `7,132` |
| Missing baseline flows | `0` |
| Same timestamp rows | `7,132` |
| Same amount rows | `0` |
| Mean amount delta | `+30.67` |
| Minimum amount delta | `+0.08` |
| Maximum amount delta | `+497.13` |

For fraud flows inside this pinned context, the anchor relationship says: the selected flow keys match back to baseline, timing is preserved, amount is changed, and fraud/campaign state is added. That is the observed overlay contract at flow grain.

This is also why the correct analytical comparison is not "did fraud create new traffic?" At least for these anchor surfaces, the better question is "which existing flow keys were selected and economically altered?"

## How event streams recover context through anchors

The recovery path is:

1. A stream row arrives with `flow_id`, lineage fields, `event_seq`, `event_type`, `ts_utc`, and `amount`.
2. The platform or offline analysis uses `flow_id` plus lineage context to bind the event row to the matching flow anchor.
3. The anchor supplies `arrival_seq`, merchant context, entity context, IP context, and post-overlay fraud/campaign state where applicable.
4. The event row can now be interpreted as part of a merchant/entity/arrival world instead of as a thin traffic row.

The important grain distinction is that the join is event-to-flow, not event-to-event. The event stream is designed as a two-row request/response grammar at flow grain. The anchor has one row per flow. If the anchor is joined to the stream without collapsing the event grammar, anchor context will be repeated across the event rows in the joined result.

That repetition is not wrong. It is only wrong if the analyst forgets it happened. For event-time operational questions, the repetition may be appropriate. For flow-level merchant, amount, fraud, or loss questions, the joined result must be collapsed back to flow grain or read directly from the anchor.

## What this branch proves and does not prove

This branch proves:

- the event streams are thin by design
- the flow anchors carry the missing merchant/entity/IP/arrival context
- baseline and post-overlay event streams have exactly two event rows per anchor row at aggregate shape
- event amount totals are approximately two times anchor amount totals, consistent with request/response duplication
- compact key reconciliation strongly supports that baseline and post-overlay anchors share the same flow and arrival identity universe
- fraud-marked post-overlay anchor rows all match baseline flows in the parent comparison under the single pinned lineage context
- fraud overlay preserves timestamp and changes amount for those fraud flows

This branch does not prove:

- a completed full-population anti-join showing every single event row has a matching anchor row
- that anchor fields were consumed correctly by a live model or feature service
- that campaign IDs are semantically meaningful without a campaign catalogue or truth/case context
- that event-grain amount totals should be used as economic exposure

The first limitation is important. The aggregate shape is very strong, and the contract is coherent, but a production validation suite should still include a targeted full event-to-anchor coverage check. That check should be engineered carefully because a naive full join over `473.38M` event rows and `236.69M` anchor rows is expensive.

## Time-safety and operating use

Unlike the completed session index, the flow anchors are live-compatible context surfaces in concept. They describe the current flow and its attached entities. That makes them candidates for RTDL context enrichment, event replay, offline training joins, and case reconstruction.

However, live-compatible does not mean every anchor field is automatically safe in every path. The baseline anchor and post-overlay anchor belong to different operating states:

- baseline anchor: context for the baseline stream
- post-overlay anchor: context for the post-overlay stream, including `fraud_flag` and `campaign_id`

For live model scoring, `fraud_flag` and `campaign_id` would not be ordinary decision-time features if they represent injected or later-known fraud state. They are valid for investigation, replay, labelling analysis, and controlled post-overlay experiments, but they must not be casually treated as real-time predictor inputs.

So the safe rule is:

- use anchor identity fields to recover flow context
- keep event and flow grain separate
- choose the anchor matching the stream state being analyzed
- avoid treating post-overlay fraud/campaign fields as live predictor features unless the feature design explicitly permits that state

## Leads exposed by this branch

1. **Full event-to-anchor coverage validation.** The branch has aggregate and compact key evidence, but not a full anti-join proof. If this becomes a platform-quality gate, run it as a targeted engineered validation rather than an ad hoc notebook join.

2. **Flow-grain amount discipline.** Event stream totals can double flow economic value because request and response both carry amount. Future dashboards must decide whether they report event exposure or flow value.

3. **Post-overlay anchor usage.** Fraud/campaign fields are useful for investigation, but they should be classified carefully before any live-feature story.

4. **Anchor-to-truth bridge.** The next truth/case analyses should use anchors to recover entity context for labelled flows, but must avoid double-counting by event row.

5. **Entity-context expansion.** Since anchors carry merchant, party, account, instrument, device, and IP, later fraud analytics can branch into entity reuse, network concentration, and merchant/entity risk posture.

## Working conclusion

The flow anchors are the contract that makes the thin behavioural streams usable.

The stream rows carry the authorization event grammar. The anchors recover the flow's merchant, arrival, entity, IP, amount, and overlay context. The aggregate shape is coherent: the event-row count is twice the anchor-row count, and event amount totals are approximately doubled for the same reason. Compact key reconciliation strongly supports that the baseline and post-overlay anchors share the same flow universe, while fraud overlay changes selected flow amounts and attaches fraud/campaign state.

The practical analytical rule is straightforward: use streams to understand event movement, use anchors to recover flow context, and collapse back to flow grain before making flow-level economic, fraud, or stakeholder claims.
