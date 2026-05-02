# Behavioural Context Investigation

## What these surfaces are

The behavioural-context datasets are the context topic/surface families that make the thin behavioural streams interpretable. In the live AWS-hosted Fraud Decisioning Platform framing, this is the enrichment layer exposed through the run's source-of-stream/context estate and consumed as topics, indexes, projections, or offline reads so admitted event rows become usable for RTDL, feature materialization, entity analysis, replay, and case review.

The interface pack exposes four of them:

- `s1_arrival_entities_6B`
- `s1_session_index_6B`
- `s2_flow_anchor_baseline_6B`
- `s3_flow_anchor_with_fraud_6B`

They are not traffic. They are the context layer around traffic. The platform should not collapse these surfaces into the business stream; it should move or project them as context topic families and offline reads depending on time-safety.

The behavioural streams carry the event grammar: `flow_id`, `event_seq`, `event_type`, `ts_utc`, `amount`, and, after overlay, fraud fields. The context surfaces attach the event stream back to merchants, arrivals, parties, accounts, instruments, devices, IPs, sessions, and flow anchors.

So the analytical role of this group is different from the behavioural streams:

- streams tell us what event rows move through the platform
- context tells us who and what those event rows are attached to
- truth products later tell us what became true about those event rows or flows

So the analysis of these columns is grounded in how a fraud platform would use them. `party_id`, `account_id`, `instrument_id`, `device_id`, and `ip_id` are not abstract IDs; they are the identity graph available for entity risk, network-style analysis, replay, case review, and feature construction. `session_end_utc` and `arrival_count` are not harmless columns; they mark a batch-only surface that must be kept out of live decision-time features.

## References and evidence

Contract references:

- [`docs/model_spec/data-engine/interface_pack/data_engine_interface.md`](../../../../../../../docs/model_spec/data-engine/interface_pack/data_engine_interface.md)
- [`docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`](../../../../../../../docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml)
- [`docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`](../../../../../../../docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml)
- [`docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`](../../../../../../../docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md)
- [`docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.md`](../../../../../../../docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.md)

Pinned data surfaces:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s1_arrival_entities_6B`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s1_arrival_entities_6B)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s1_session_index_6B`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s1_session_index_6B)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s2_flow_anchor_baseline_6B`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s2_flow_anchor_baseline_6B)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s3_flow_anchor_with_fraud_6B`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s3_flow_anchor_with_fraud_6B)

Support script and exports:

- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/scratch/analyze_behavioural_context.py`](../../../scratch/analyze_behavioural_context.py)
- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/interface_world/behavioural_context`](../../../exports/interface_world/behavioural_context)

Branch investigations:

- [`branches/entity_grain_identity_graph.md`](branches/entity_grain_identity_graph.md)
- [`branches/session_index_time_safety.md`](branches/session_index_time_safety.md)

## Contract read before touching the data

The interface contract separates behavioural context into two working levels.

At arrival level:

- `s1_arrival_entities_6B` attaches entity identifiers to arrivals
- `s1_session_index_6B` summarizes arrival sessions

At flow level:

- `s2_flow_anchor_baseline_6B` anchors baseline traffic flows
- `s3_flow_anchor_with_fraud_6B` anchors post-overlay traffic flows

The contract also states the time-safety distinction:

- `s1_arrival_entities_6B`, `s2_flow_anchor_baseline_6B`, and `s3_flow_anchor_with_fraud_6B` are time-safe join surfaces
- `s1_session_index_6B` is oracle-only / batch-only because it contains full-session closure fields such as `session_end_utc` and `arrival_count`

That means the context layer has both live-context and offline-context components. We should not flatten them into one kind of feature surface.

Operationally, the split is the point of the contract. `s1_arrival_entities_6B` and the flow anchors can participate in the real-time path as context topics/projections because they describe the current arrival/flow. `s1_session_index_6B` is useful after the fact because it describes a completed session. If we ignore that distinction, we would accidentally let future knowledge leak into a live fraud decision.

## Physical shape of the context layer

The pinned run contains:

| Surface | Rows | Grain |
|---|---:|---|
| `s1_arrival_entities_6B` | `236,691,694` | one row per arrival |
| `s1_session_index_6B` | `184,820,742` | one row per session |
| `s2_flow_anchor_baseline_6B` | `236,691,694` | one row per baseline flow |
| `s3_flow_anchor_with_fraud_6B` | `236,691,694` | one row per post-overlay flow |

This is the basic shape of the behavioural operating world:

- arrival entity context has the same row count as the arrival skeleton
- flow anchors have the same row count as the flow count
- behavioural streams have twice that row count because each flow becomes request and response events
- session context compresses arrivals into sessions, but not by very much because most sessions have one or two arrivals

For the operating platform, this means a streamed event does not carry all its meaning alone. The row counts show the supporting context architecture: one arrival context row, one flow anchor row, and two event rows per flow, plus a separate offline session view. These are companion surfaces in the run's source-of-stream estate, not a staged sequence where context arrives only after traffic has already moved.

## Arrival entity context

`s1_arrival_entities_6B` carries the entity attachments for each arrival:

- `merchant_id`
- `party_id`
- `account_id`
- `instrument_id`
- `device_id`
- `ip_id`
- `session_id`

Observed profile:

- rows: `236,691,694`
- merchants: `4,050`
- approximate parties: `5.80M`
- approximate accounts: `6.14M`
- approximate instruments: `5.93M`
- approximate devices: `6.45M`
- approximate IPs: `2.39M`
- approximate sessions: `181.91M`
- time span: `2026-01-01T00:00:00.001940Z` to `2026-03-31T23:59:59.944516Z`

The session estimate here is an approximate distinct read from the arrival-entity surface. The authoritative exact session count comes from `s1_session_index_6B`, which has `184,820,742` session rows.

This surface is the first point where the stream world starts to look like a fraud platform rather than just merchant traffic. It introduces the customer/account/device/IP identity space that later analytics and case investigation will need.

The important read is that the entity world is much wider than the merchant world. There are only `4,050` merchants, but millions of parties, accounts, instruments, devices, and IPs. That means a downstream investigation cannot stay merchant-only for long. The fraud platform's context layer is designed to support entity-level and network-style questions: account exposure, device reuse, IP concentration, instrument behaviour, and party-level risk are all made possible by this surface.

## Session index

`s1_session_index_6B` has:

- rows / sessions: `184,820,742`
- represented arrivals: `236,691,694`
- merchants: `4,050`
- median arrival count per session: `1`
- p95 arrival count per session: `2`
- max arrival count per session: `10`
- session time span: `2026-01-01T00:00:00.001940Z` to `2026-03-31T23:59:59.944516Z`

Session arrival-count shape:

| Arrival count | Sessions | Session share | Represented arrivals |
|---:|---:|---:|---:|
| `1` | `141,986,429` | `76.82%` | `141,986,429` |
| `2` | `35,140,408` | `19.01%` | `70,280,816` |
| `3` | `6,525,895` | `3.53%` | `19,577,685` |
| `4` | `1,013,373` | `0.55%` | `4,053,492` |
| `5+` | small tail | `<0.1%` each | small tail |

The session surface is internally coherent: summing `arrival_count` exactly reconstructs the `236,691,694` arrival rows.

But it is not live-safe. The session index contains `session_end_utc` and `arrival_count`, which require knowledge of the full session. So this surface is valuable for offline analytics, behavioural reconstruction, and case review, but it must not be used as if it were available at event time. In platform terms, it belongs with offline learning/evaluation and case reconstruction, not the hot RTDL path.

The statistical read is that the platform mostly sees short sessions. Over three quarters of sessions contain one arrival, and about `95.83%` contain one or two arrivals. That means session-level aggregation exists, but most sessions are not long behavioural chains.

## Baseline flow anchor

`s2_flow_anchor_baseline_6B` is the flow-level context surface for the baseline stream.

Observed profile:

- rows / flows: `236,691,694`
- merchants: `4,050`
- approximate parties: `5.80M`
- approximate accounts: `6.14M`
- approximate instruments: `5.93M`
- approximate devices: `6.45M`
- approximate IPs: `2.39M`
- time span: `2026-01-01T00:00:00.001940Z` to `2026-03-31T23:59:59.944516Z`
- mean amount: `24.31`
- median amount: about `14.99`
- p95 amount: about `98.78`
- max amount: `3,401.78`
- total amount: about `5.755B`

This surface is the bridge between event stream and context. The baseline event stream has two rows per flow, but this anchor has one row per flow. So when we want flow-level context, this is the surface to join to.

It also explains why the event stream is intentionally thin. The stream carries event movement; the anchor carries the flow's entity and amount context. In a production service, this is the sort of surface that would be indexed or projected for fast context lookup rather than copied wholesale into each streamed event.

## Post-overlay flow anchor

`s3_flow_anchor_with_fraud_6B` has the same structural grain as the baseline anchor:

- rows / flows: `236,691,694`
- merchants: `4,050`
- same arrival-key hash as `s1_arrival_entities_6B` and `s2_flow_anchor_baseline_6B`
- same flow-key hash as `s2_flow_anchor_baseline_6B`

It adds:

- `fraud_flag`
- `campaign_id`

Fraud overlay at anchor grain:

| Fraud flag | Rows / flows | Campaigns | Row share | Mean amount | Median amount |
|---|---:|---:|---:|---:|---:|
| `false` | `236,684,562` | `0` | `99.996987%` | `24.31` | about `15.00` |
| `true` | `7,132` | `6` | `0.003013%` | `54.76` | about `31.72` |

The post-overlay anchor confirms the behavioural-stream finding at the right grain: there are `7,132` fraud flows, and the behavioural stream represents them as `14,264` fraud event rows.

Operationally, this anchor is the flow-grain context counterpart of the post-overlay stream. It is where a live or replayed event can recover the post-overlay flow amount, entity attachments, and campaign marker without confusing event rows with flow rows.

The campaign distribution is:

| Campaign rank | Flows |
|---:|---:|
| 1 | `2,278` |
| 2 | `1,922` |
| 3 | `1,223` |
| 4 | `1,208` |
| 5 | `275` |
| 6 | `226` |

So the campaign surface is sparse and uneven, but every campaign has a measurable footprint across the three-month window.

## Baseline to post-overlay relationship

The key reconciliation is strong:

| Surface | Rows | Arrival-key hash | Flow-key hash |
|---|---:|---:|---:|
| `s1_arrival_entities_6B` | `236,691,694` | same as anchors | n/a |
| `s2_flow_anchor_baseline_6B` | `236,691,694` | same as arrival entities | same as post-overlay anchor |
| `s3_flow_anchor_with_fraud_6B` | `236,691,694` | same as arrival entities | same as baseline anchor |

This tells us that the context chain is coherent. The post-overlay anchor is not a different flow universe. It preserves the same arrival and flow identity space, then adds fraud/campaign fields and amount changes on selected flows.

For the `7,132` fraud flows:

- all `7,132` match a baseline flow
- all preserve the same timestamp
- none preserve the same amount
- mean amount delta: `+30.67`
- minimum amount delta: `+0.08`
- maximum amount delta: `+497.13`

So the overlay changes economic value while preserving the flow's identity and timing. That is exactly the kind of distinction the context layer is supposed to make visible.

## Null and completeness read

The context surfaces are clean in their core identity and join fields:

- no nulls in `flow_id` where present
- no nulls in `arrival_seq`
- no nulls in `merchant_id`
- no nulls in entity IDs
- no nulls in lineage fields
- no nulls in timestamps
- no nulls in `amount` where present
- no nulls in `fraud_flag` on the post-overlay anchor

The meaningful null pattern is `campaign_id`:

- `campaign_id` is null on `236,684,562` non-fraud flows
- `campaign_id` is populated on `7,132` fraud flows

So campaign nullness is not missing data. It is the representation of non-campaign traffic.

## Time-safety read

The context surfaces should not be treated equally for live decisioning.

Time-safe context:

- `s1_arrival_entities_6B`
- `s2_flow_anchor_baseline_6B`
- `s3_flow_anchor_with_fraud_6B`

Batch-only context:

- `s1_session_index_6B`

The session index is still valuable, but it belongs to offline analysis and reconstruction because `arrival_count` and `session_end_utc` imply future knowledge. If we later design features or analytical claims around sessions, we need to state whether the claim is live-time or offline-only.

## Leads exposed by this investigation

1. The behavioural context layer is the real enrichment layer for the thin streams. It carries entity identity, session identity, and flow-level context that the streams deliberately omit.

2. The arrival-to-flow context is coherent. Arrival entity rows, baseline anchors, and fraud anchors share the same row count and arrival-key hash.

3. Session context is useful but batch-only. It represents all arrivals, but it contains closure information and should not be used as a live decision-time feature source.

4. The entity surface is much wider than the merchant surface. The operating world has millions of parties, accounts, instruments, devices, and IPs attached to only `4,050` merchants.

5. The post-overlay anchor confirms that fraud is a flow-level overlay first, represented as two event rows in the stream.

6. Fraud overlay preserves identity and timing but changes amount. That distinction should guide later comparisons between baseline and post-overlay traffic.

7. Campaign IDs are usable as grouping keys, but their business meaning is still not self-contained in the context surfaces alone.

## Working conclusion

The behavioural context layer is what turns thin event traffic into an analytically usable fraud-platform world.

The behavioural streams tell us that traffic exists as two-row authorization pairs. The context surfaces tell us who those flows belong to, which entities are involved, which sessions they belong to, and how fraud overlay changes the flow surface. They also establish the first serious time-safety distinction in the interface world: flow and arrival entity context can support live-time reasoning, while session index belongs to offline reconstruction.

The next logical investigation is the `s4_*` truth-product group, because that is where the traffic and context world becomes labelled, bank-viewed, and case-reconstructable.
