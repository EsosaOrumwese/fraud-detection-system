# Behavioural Streams Investigation: `s2_event_stream_baseline_6B` and `s3_event_stream_with_fraud_6B`

## What these surfaces are

The behavioural streams are the downstream estate surfaces that should be read as platform traffic. In the live AWS-hosted Fraud Decisioning Platform framing, these are the transaction-like event rows that WSP publishes from Oracle Store / stream-view, the Ingestion Gate admits, and the Event Bus / RTDL path moves through the service.

The interface contract names two of them:

- `s2_event_stream_baseline_6B`
- `s3_event_stream_with_fraud_6B`

The baseline stream is the production-shaped behavioural stream before fraud overlay. The post-overlay stream carries the same traffic world after synthetic fraud and abuse behaviour have been injected. In platform terms, these are traffic topic families eligible for ingestion, event-bus handling, RTDL context enrichment, online feature consumption, and later comparison against offline labels.

That is the main difference from `arrival_events_5B`. The arrival primitive is a time-safe context surface/topic. These behavioural streams are the traffic body the platform moves through downstream systems.

So these reports should not read the streams as static parquet tables only. The columns are interpreted as a streaming event contract: `flow_id` binds the event to flow context, `event_seq` and `event_type` define the request/response grammar, `ts_utc` defines event time for ordering, `amount` carries the economic signal, and post-overlay fraud fields mark the campaign-modified stream state before final truth is applied.

## References and evidence

Contract references:

- [`docs/model_spec/data-engine/interface_pack/data_engine_interface.md`](../../../../../../../docs/model_spec/data-engine/interface_pack/data_engine_interface.md)
- [`docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`](../../../../../../../docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml)
- [`docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`](../../../../../../../docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml)
- [`docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`](../../../../../../../docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md)
- [`docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.md`](../../../../../../../docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.md)

Pinned data surfaces:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s2_event_stream_baseline_6B`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s2_event_stream_baseline_6B)
- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s3_event_stream_with_fraud_6B`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s3_event_stream_with_fraud_6B)

Support script and exports:

- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/scratch/analyze_behavioural_streams.py`](../../../scratch/analyze_behavioural_streams.py)
- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/interface_world/behavioural_streams`](../../../exports/interface_world/behavioural_streams)

Branch investigations:

- [`branches/event_grammar_and_grain.md`](branches/event_grammar_and_grain.md)

## Contract read before touching the data

The catalogue gives both streams the same primary key:

`seed + manifest_fingerprint + scenario_id + flow_id + event_seq`

The join key also includes `parameter_hash`, giving the platform the full identity tuple needed to bind a stream row back into the pinned world:

`seed + manifest_fingerprint + parameter_hash + scenario_id + flow_id + event_seq`

The interface contract also makes two important statements:

- these are the traffic streams
- the flow-anchor datasets are the context surfaces

So the stream rows are intentionally thin. They are not expected to carry the full merchant, arrival, entity, session, or truth context. That context lives in the neighbouring behavioural-context surfaces and is joined by the platform.

Operationally, this is the core traffic contract. The platform should move these events as traffic while also publishing/maintaining separate context topic families; it should not batch-absorb every context surface into each payload. `flow_id` is the event-to-flow handle, `event_seq` gives the request/response order, `event_type` tells the RTDL path which authorization phase it is seeing, `ts_utc` controls event-time ordering, and `amount` is the economic signal available on the stream. Context, labels, and case outcomes are intentionally outside the row and must be attached through governed joins, projections, or offline workflows.

## Physical shape of the two streams

The two streams have the same row count:

| Stream | Rows | Files | Event types | Event sequence range |
|---|---:|---:|---:|---:|
| `s2_event_stream_baseline_6B` | `473,383,388` | `1,302` | `2` | `0` to `1` |
| `s3_event_stream_with_fraud_6B` | `473,383,388` | `1` | `2` | `0` to `1` |

The post-overlay stream adds two fields:

- `fraud_flag`
- `campaign_id`

Otherwise, its core stream body has the same traffic shape as the baseline stream:

- same row count
- same event types
- same event sequence range
- same key fingerprint over `flow_id + event_seq`

This is the first major finding: the fraud overlay does not appear as an extra traffic stream with additional rows. It appears as an overlay on the same event-key universe. For a live ingestion path, that means the post-overlay stream preserves throughput shape while changing selected event attributes; it is not a second population of synthetic traffic appended on top.

## Event grammar

Both streams contain exactly two event types:

| Event sequence | Event type | Rows |
|---:|---|---:|
| `0` | `AUTH_REQUEST` | `236,691,694` |
| `1` | `AUTH_RESPONSE` | `236,691,694` |

That makes the event grammar very regular. Each flow is represented as a two-step authorization pair:

1. request
2. response

This also explains why the behavioural stream has exactly twice the row count of `arrival_events_5B`:

- `arrival_events_5B`: `236,691,694` arrival rows
- behavioural streams: `473,383,388` event rows

The platform-facing traffic stream is therefore not one row per arrival. It is one flow represented by two event rows. That distinction matters for every later analysis:

- event-level row counts will double the arrival-flow count
- flow-level analysis must collapse `AUTH_REQUEST` and `AUTH_RESPONSE`
- labels may exist at event level or flow level, and those grains must not be confused

It also matters operationally: RTDL and downstream consumers see event rows, while most fraud judgement and case surfaces are easier to reason about at flow grain. Any metric that mixes these grains can double-count the operating burden or label rate.

## Time coverage and the April spillover

Both behavioural streams span:

- minimum UTC timestamp: `2026-01-01T00:00:00.001940Z`
- maximum UTC timestamp: `2026-04-01T00:01:41.104298Z`

This is slightly different from the arrival primitive, which ended on `2026-03-31T23:59:59.944516Z`.

The monthly event-row counts are:

| Month | Rows |
|---|---:|
| `2026-01` | `163,357,039` |
| `2026-02` | `147,305,153` |
| `2026-03` | `162,721,045` |
| `2026-04` | `151` |

The April presence is small: only `151` rows. The most plausible reading is stream lifecycle rather than extract leakage. The arrival skeleton ends at the end of March, but a two-event stream can still place a small number of response-side events just after midnight on April 1.

This is a useful platform lesson: the traffic stream has event lifecycle semantics, not just arrival-date semantics. If we later define reporting periods, we need to decide whether the boundary is based on arrival time, event time, flow start, or flow completion. A live platform can admit an arrival in one period and complete a response just outside the period boundary.

## Amount surface

The baseline stream has:

- minimum amount: `0.04`
- approximate p05: `2.02`
- approximate p25: `7.42`
- mean: `24.31`
- approximate median: `14.99`
- approximate p75: `29.99`
- approximate p95: `99.44`
- maximum amount: `3,401.78`
- total amount: about `11.509B`

The post-overlay stream is extremely close in its broad amount surface:

- mean: `24.31`
- approximate median: `15.00`
- approximate p95: `99.71`
- maximum amount: `3,401.78`
- total amount: about `11.510B`

The total amount increases by roughly `437.5K` after overlay, which is tiny relative to the full stream amount. That fits the overlay posture: fraud behaviour exists, but it is a sparse layer inside a massive behavioural traffic body.

## Fraud overlay shape

The post-overlay stream has:

| Fraud flag | Rows | Approx flows | Campaigns | Row share |
|---|---:|---:|---:|---:|
| `false` | `473,369,124` | `244,190,267` | `0` | `99.996987%` |
| `true` | `14,264` | `7,208` | `6` | `0.003013%` |

The fraud rows are evenly split by event type:

| Event type | Fraud rows |
|---|---:|
| `AUTH_REQUEST` | `7,132` |
| `AUTH_RESPONSE` | `7,132` |

The exact fraud-flow shape is clean:

- fraud flows: `7,132`
- min events per fraud flow: `2`
- median events per fraud flow: `2`
- max events per fraud flow: `2`
- nonstandard fraud-flow shapes: `0`

That means the overlay is flow-consistent. When a flow is marked fraud, both request and response rows are represented. Fraud is not appearing as a one-sided event-row artifact.

## Campaign surface inside the stream

The post-overlay stream exposes six campaign IDs through `campaign_id`.

| Campaign rank | Rows | Flows | Event types | Time span |
|---:|---:|---:|---:|---|
| 1 | `4,556` | `2,278` | `2` | Jan 1 to Mar 31 |
| 2 | `3,844` | `1,922` | `2` | Jan 1 to Mar 31 |
| 3 | `2,446` | `1,223` | `2` | Jan 1 to Mar 31 |
| 4 | `2,416` | `1,208` | `2` | Jan 1 to Mar 31 |
| 5 | `550` | `275` | `2` | Jan 1 to Mar 31 |
| 6 | `452` | `226` | `2` | Jan 1 to Mar 31 |

The campaign rows also preserve the two-event grammar. Every campaign has two event types, and each campaign row count is twice its flow count.

The campaign IDs are opaque at this stage. We can count them and compare their statistical footprint inside the stream, but we should not infer campaign meaning from the ID alone. The meaning of those IDs belongs to later truth or case surfaces unless the platform explicitly exposes a campaign catalogue to this analytical role.

## Fraud amount posture

Fraud-flagged rows have a much higher amount profile than the overall stream:

- fraud mean amount: `54.76`
- non-fraud mean amount: `24.31`
- fraud median amount: `31.75`
- non-fraud median amount: `14.99`
- fraud max amount: `729.73`
- global max amount: `3,401.78`

So fraud rows are not the highest absolute-value events in the whole stream, but they are materially elevated relative to normal traffic.

This distinction matters. The fraud layer is sparse and amount-elevated, but not simply “all the largest transactions are fraud.” Later modelling or analysis should therefore avoid reducing fraud to a high-amount-only story.

## What the overlay changes

The fraud-row comparison back to the baseline stream gives a useful read on how the overlay behaves.

For the `14,264` fraud rows:

- all `14,264` match a baseline row on `flow_id + event_seq`
- all `14,264` preserve the same event type
- all `14,264` preserve the same UTC timestamp
- `0` preserve the same amount

The amount deltas are:

- mean amount delta: `+30.67`
- minimum amount delta: `+0.08`
- maximum amount delta: `+497.13`

So the overlay is not creating a new timing universe and it is not changing the event grammar. It is selecting existing event keys, preserving their position in the stream, and changing the economic value carried by those fraud-marked events.

That is an important investigative finding because it tells us how to compare baseline and post-overlay traffic. The right comparison is not “did new events appear?” The right comparison is “which existing event keys were marked and economically altered?” In the service story, the fraud overlay changes what selected transactions look like to downstream decisioning and learning; it does not change the event-bus grammar.

## Null and completeness read

The baseline stream has no nulls across its core fields:

- `flow_id`
- `event_seq`
- `event_type`
- `ts_utc`
- `amount`
- `seed`
- `manifest_fingerprint`
- `parameter_hash`
- `scenario_id`

The post-overlay stream also has no nulls in the core fields or in `fraud_flag`.

`campaign_id` is null for `473,369,124` rows, which exactly matches the non-fraud row count. That null pattern is meaningful:

- non-fraud row -> no campaign ID
- fraud row -> campaign ID present

So `campaign_id` missingness is not a quality problem. It is the representation of non-campaign traffic.

## Relationship to the traffic primitive

The behavioural stream row count is exactly twice the `arrival_events_5B` row count.

That gives us a clean lifecycle reading:

1. `arrival_events_5B` gives the arrival skeleton.
2. `s2_event_stream_baseline_6B` turns each arrival/flow into a two-event authorization stream.
3. `s3_event_stream_with_fraud_6B` preserves that event-key universe while adding fraud/campaign marking.

So the platform traffic world is not created by discarding the arrival primitive. It is a structured expansion of it into an event grammar.

This also means the next behavioural-context investigation should focus on the bridge:

- how `flow_id` relates back to `merchant_id + arrival_seq`
- how anchors enrich the thin stream
- whether the context surfaces preserve the same event/flow counts

## Leads exposed by this investigation

1. The canonical traffic stream is thin and regular: two rows per flow, one request and one response.

2. Event-level and flow-level grains must be kept separate. Any count of rows in these streams is an event count, not a flow count.

3. The post-overlay stream appears to preserve the baseline key universe while adding fraud/campaign fields.

4. For fraud-marked rows, the overlay preserves event key, event type, and timestamp, but changes amount.

5. Fraud is extremely sparse at the event-row level: about `0.003%` of stream rows.

6. Fraud is flow-consistent: `7,132` fraud flows have exactly two fraud-marked events each.

7. Fraud rows are amount-elevated but not simply the maximum-value tail of the whole stream.

8. A small April spillover exists in the behavioural stream. This should be handled as a stream lifecycle boundary issue when we later define analysis windows.

9. Campaign IDs are exposed in the stream, but their semantic meaning is not self-contained in this stream alone.

## Working conclusion

The behavioural streams are the platform's first true traffic body. They take the arrival skeleton and express it as a regular authorization event pair: request and response.

The baseline stream gives the clean production-shaped traffic surface. The post-overlay stream keeps the same traffic body and adds a sparse fraud/campaign layer. This means the fraud world is not a separate stream floating beside traffic; it is embedded inside the same event grammar that the platform would ingest and analyze.

For the next investigation, the natural move is the behavioural context section:

- `s1_arrival_entities_6B`
- `s1_session_index_6B`
- `s2_flow_anchor_baseline_6B`
- `s3_flow_anchor_with_fraud_6B`

Those surfaces should explain how the thin event stream gets enough context to become analytically meaningful.
