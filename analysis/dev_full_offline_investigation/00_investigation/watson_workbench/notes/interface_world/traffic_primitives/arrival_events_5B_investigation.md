# Traffic Primitive Investigation: `arrival_events_5B`

## What this surface is

`arrival_events_5B` is the only traffic primitive in the downstream interface estate. In the live AWS-hosted Fraud Decisioning Platform framing, it is the arrival-context primitive available from Oracle Store / stream-view and published as part of the platform's source-of-stream topic family.

It is event-like, but the interface contract is explicit that it is **not** the canonical business traffic stream emitted as the transaction body. The real-time service should not treat this as the transaction stream a model scores. It is a time-safe context topic/surface: it tells the platform where, when, and through which physical/virtual route an arrival entered the operating world so behavioural streams and entity/flow context can be joined consistently.

That gives it a specific analytical role:

- it tells us the shape of arrival activity that accompanies the canonical behavioural streams
- it gives us the first exposed time axis of the operating world
- it exposes the arrival-level merchant, routing, zone, channel, site, and virtual-edge structure
- it should be read as time-safe context, not as final truth or fraud-labelled traffic

So when we inspect its columns and counts, we are reading them as the arrival/routing context of a financial-institution fraud platform: merchant arrivals, local-time representations, physical-site versus virtual-edge routing, and channel structure. The questions it raises are operational questions about traffic context, not engine-state questions about how the world was authored internally.

## References and evidence

Contract references:

- [`docs/model_spec/data-engine/interface_pack/data_engine_interface.md`](../../../../../../../docs/model_spec/data-engine/interface_pack/data_engine_interface.md)
- [`docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml`](../../../../../../../docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml)
- [`docs/model_spec/data-engine/layer-2/specs/contracts/5B/dataset_dictionary.layer2.5B.yaml`](../../../../../../../docs/model_spec/data-engine/layer-2/specs/contracts/5B/dataset_dictionary.layer2.5B.yaml)
- [`docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`](../../../../../../../docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md)
- [`docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.md`](../../../../../../../docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/proving_plane/platform.production_readiness.md)

Pinned data surface:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer2/5B/arrival_events`](../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer2/5B/arrival_events)

Support script and exports:

- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/scratch/analyze_traffic_primitive_arrival_events.py`](../../../scratch/analyze_traffic_primitive_arrival_events.py)
- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/interface_world/traffic_primitives/arrival_events_investigation_summary.json`](../../../exports/interface_world/traffic_primitives/arrival_events_investigation_summary.json)
- [`analysis/dev_full_offline_investigation/00_investigation/watson_workbench/exports/interface_world/traffic_primitives`](../../../exports/interface_world/traffic_primitives)

## Contract read before touching the data

The catalogue defines the surface as:

- output id: `arrival_events_5B`
- class: `surface`
- exposure: `external`
- scope: `seed`, `manifest_fingerprint`, `scenario_id`
- primary key: `seed`, `manifest_fingerprint`, `scenario_id`, `merchant_id`, `arrival_seq`
- join keys: `seed`, `manifest_fingerprint`, `scenario_id`, `merchant_id`, `arrival_seq`
- read gate: `gate.layer2.5B.validation`

The dataset dictionary adds the operational meaning:

- it is the final `5B` egress surface
- it is produced by `5B.S4`
- it is consumed by `5B.S5`, `6A`, `6B`, and `enterprise_ingestion`
- it is ordered by scenario, merchant, timestamp, and arrival sequence
- it is PII-bearing

Operationally, this means the surface belongs to the platform's context stream/view, not to the scored transaction body. `merchant_id` and `arrival_seq` form the arrival identity that `6B` surfaces use. `ts_utc` and the local timestamp/timezone fields describe how the platform can reason about event time versus local operating time. `site_id`, `edge_id`, `is_virtual`, `channel_group`, and `zone_representation` describe routing/channel context. None of these fields is a decision, label, case outcome, or model target.

The important posture is that this is not the business transaction stream. It is the arrival-context family that WSP/platform consumers can publish or join alongside traffic according to the run's stream-view and topic contracts.

## Physical shape of the data

The pinned run contains:

- `1,302` parquet files
- `236,691,694` arrival rows
- one seed: `42`
- one scenario: `baseline_v1`
- one manifest fingerprint
- one parameter hash
- one routing universe hash
- one `s4_spec_version`: `1.0.0`

This is a clean single-run, single-scenario surface. There is no mixed scenario or mixed lineage problem inside this primitive, which matters because a live platform relies on run identity and source/topic contracts to publish and join context safely rather than infer meaning from file names or row order.

The row count is large enough that this should be treated as a warehouse-style analytical surface. The workbench analysis uses DuckDB aggregates and exports small summaries rather than loading the data into memory.

## Grain and identity

Branch investigation:

- [`branches/arrival_events_grain_and_identity.md`](branches/arrival_events_grain_and_identity.md)

The observed grain matches the declared primary key:

`seed + manifest_fingerprint + scenario_id + merchant_id + arrival_seq`

The surface covers:

- `4,050` merchants
- `78,516` physical sites
- `3,005` virtual edges
- `339` zone representations
- `2` channel groups
- `2,160` bucket indexes
- `281` operational timezones

The merchant sequence check is clean:

- `0` merchants have an arrival-sequence span mismatch
- every merchant begins at `arrival_seq = 1`
- each merchant's maximum arrival sequence equals its row count

That matters because `arrival_seq` is not just a loose row number. It behaves as a stable per-merchant arrival clock that can support joins into `6B`. In platform terms, it is the join handle that lets a thin flow/event row recover its arrival-routing context without scanning the wider Oracle Store at decision time.

## Time coverage

The surface spans the full three-month operating window:

- first UTC timestamp: `2026-01-01T00:00:00.001940Z`
- last UTC timestamp: `2026-03-31T23:59:59.944516Z`
- active days: `90`

Monthly rows:

| Month | Rows | Active merchants | Active days |
|---|---:|---:|---:|
| `2026-01` | `81,678,596` | `4,050` | `31` |
| `2026-02` | `73,652,566` | `4,050` | `28` |
| `2026-03` | `81,360,532` | `4,050` | `31` |

Daily volume is stable at the broad level:

- mean daily rows: `2,629,908`
- median daily rows: `2,626,903`
- minimum daily rows: `2,472,304`
- maximum daily rows: `2,887,820`
- daily standard deviation: `82,932`

The month pattern mostly reflects calendar length. January and March are close to each other, while February is lower because it has fewer days. That tells us the arrival-context surface is continuous rather than a partial extract with obvious month-level dropouts. For the assumed live service, this makes it usable as a three-month operating context baseline for traffic, label, and case-rate interpretation.

## Channel structure

The surface has two channel groups:

| Channel | Rows | Row share | Merchants | Sites | Edges |
|---|---:|---:|---:|---:|---:|
| `card_present` | `157,117,536` | `66.38%` | `3,261` | `68,780` | `537` |
| `card_not_present` | `79,574,158` | `33.62%` | `789` | `9,736` | `2,468` |

The first important read is that channel is merchant-stable in this primitive:

- `0` merchants appear in more than one channel

So the traffic primitive does not show merchants switching between card-present and card-not-present arrival modes. Channel behaves like a merchant-level operating identity here, not an event-by-event behavioral variation. In a fraud-platform read, that changes how we should interpret channel: it is closer to the merchant's operating lane than to a transaction-by-transaction customer choice at this surface.

The second read is that virtual routing is much more concentrated in card-not-present activity. Card-not-present accounts for about one third of rows but most distinct virtual edges. That gives us an early lead for the behavioural-stream investigation: when we move into `s3_event_stream_with_fraud_6B`, we should check whether virtual / card-not-present traffic carries a different fraud, flow, or case structure.

## Physical versus virtual routing

The site and edge null profile is not random missingness. It encodes the two routing modes:

| Routing mode | Rows | Row share | Merchants | Sites | Edges |
|---|---:|---:|---:|---:|---:|
| physical (`is_virtual = false`) | `216,136,107` | `91.32%` | `3,893` | `78,516` | `0` |
| virtual (`is_virtual = true`) | `20,555,587` | `8.68%` | `157` | `0` | `3,005` |

This explains the apparent nulls:

- `site_id` is null exactly on the virtual side
- `edge_id` is null exactly on the physical side

So the column-null profile is structurally meaningful. It separates physical site arrivals from virtual edge arrivals. It should not be treated as a data-quality defect.

Analytically, this is one of the most important facts exposed by the primitive. Alongside canonical traffic, the arrival context tells us that the behavioural world is not a single homogeneous route. It has a large physical-site majority and a smaller, distinct virtual-edge lane. Operationally, this is a routing split the platform would need to preserve when enriching traffic, building features, or comparing case rates across physical and virtual channels.

## Merchant activity distribution

The merchant population is very uneven in arrival volume:

- merchants: `4,050`
- minimum rows per merchant: `1,842`
- p05 rows per merchant: `3,935`
- p25 rows per merchant: `17,176`
- median rows per merchant: `35,671`
- mean rows per merchant: `58,442`
- p75 rows per merchant: `69,228`
- p95 rows per merchant: `189,748`
- maximum rows per merchant: `841,654`

The mean is well above the median, and the maximum merchant is far beyond the p95. That tells us the arrival skeleton contains a strong merchant-volume tail.

This is not yet a fraud finding. It is an operating-shape finding. Before labels, cases, or enriched event streams appear, the arrival primitive already tells us that a relatively small set of merchants may dominate the raw arrival volume. That affects how we should later read event counts, case counts, and model-evaluation metrics: row-level traffic will be weighted heavily toward high-volume merchants unless we deliberately switch to merchant-level views.

## Zone and timezone structure

The surface covers `339` zone representations. The top zones by row count are:

| Zone | Rows | Row share | Merchants | Sites | Edges |
|---|---:|---:|---:|---:|---:|
| `Europe/Paris` | `18,850,372` | `7.96%` | `2,011` | `33,785` | `1,214` |
| `Europe/Berlin` | `12,651,836` | `5.35%` | `2,046` | `37,876` | `1,365` |
| `Europe/Oslo` | `12,011,938` | `5.07%` | `313` | `6,146` | `264` |
| `Europe/Luxembourg` | `11,168,076` | `4.72%` | `1,707` | `25,376` | `934` |
| `Europe/Zurich` | `10,006,135` | `4.23%` | `1,818` | `26,585` | `1,122` |
| `Africa/Accra` | `8,764,162` | `3.70%` | `143` | `2,763` | `178` |
| `Europe/Monaco` | `5,208,486` | `2.20%` | `1,131` | `14,049` | `416` |

Two things stand out.

First, the top zone is meaningful but not overwhelming. `Europe/Paris` is the largest zone, but it still holds less than `8%` of arrival rows. The traffic primitive is geographically broad.

Second, zone exposure is not merely a merchant count story. For example, `Africa/Accra` has only `143` merchants but more than `8.7M` rows. That means some zones are volume-heavy relative to their merchant count. This becomes a lead for later traffic and truth analysis: when fraud or case rates are inspected, we need to distinguish high merchant presence from high traffic intensity.

Every merchant appears in more than one zone:

- multi-zone merchants: `4,050`

So zones are not merchant-home identities in this surface. They are arrival/routing representations. That is important: if we read `zone_representation` as if it were merchant domicile, we will misinterpret the primitive.

## UTC hour shape

The UTC-hour profile has a visible business-day shape:

- lowest shares sit around early UTC hours, especially `03:00` to `05:00`
- the strongest hours run from around `10:00` to `17:00` UTC
- peak hour is `15:00` UTC with about `5.40%` of all rows

This is consistent with the surface carrying real temporal operating structure rather than being uniformly spread over the day.

Because the surface also carries primary, settlement, and operational local timestamps, the right later analysis should not stop at UTC. The traffic primitive gives us enough material to compare UTC activity to local operating time, but that should be done deliberately in the notebook or next workbench step because local-time interpretation depends on the platform question being asked.

## Data-quality and readiness read

The surface is clean on the fields that define identity and operational interpretation:

- no nulls in lineage fields
- no nulls in `merchant_id`
- no nulls in `zone_representation`
- no nulls in `channel_group`
- no nulls in `bucket_index`
- no nulls in `arrival_seq`
- no nulls in UTC or local timestamp fields
- no nulls in timezone fields
- no nulls in `routing_universe_hash`
- no nulls in `is_virtual`
- no nulls in `s4_spec_version`

The only nulls are the structurally expected split between `site_id` and `edge_id`:

- `site_id` null rows: `20,555,587`, exactly the virtual row count
- `edge_id` null rows: `216,136,107`, exactly the physical row count

So the primitive is usable as a stable timing/routing context surface. The main caution is not completeness; it is interpretation. The fields are complete enough for governed joins and operating-time analysis, but they must not be promoted into claims about fraud, bank action, or customer outcome without the `6B` context and `s4_*` truth layers.

## Leads exposed by this investigation

The traffic primitive leaves several trails worth carrying forward:

1. The downstream operating world begins with `236.7M` arrival skeleton rows, but only `4,050` merchants. Row-level analysis will be dominated by merchant-volume inequality unless we control the grain.

2. Channel behaves as merchant-stable in this primitive. That suggests channel may be closer to merchant operating mode than transaction-level behavior at this stage.

3. Virtual traffic is small by rows but structurally distinct by edge identity and concentrated merchant count. It deserves separate treatment when we inspect behavioural streams and truth products.

4. Zone is an arrival/routing representation, not a merchant-home field. Zone-level findings must be phrased as traffic/routing findings unless later context proves otherwise.

5. Time coverage is complete across January to March. The primitive looks like a full operating extract rather than an obviously gapped period.

6. The primitive is time-safe as a join surface, but it is not the canonical traffic stream. The next layer to inspect should show how this arrival context lines up with `6B` behavioural traffic and context.

## Working conclusion

`arrival_events_5B` gives us the arrival-context pulse of the platform: a large, continuous, three-month context surface with clean lineage, stable keys, complete timestamps, and a meaningful split between physical-site and virtual-edge routing.

It does not answer fraud questions by itself. It tells us what arrival/routing context accompanies platform traffic before offline truth and case history are considered. In the live-service story, it is a context family behind traffic, not the business transaction stream itself.

For the next investigation, the natural move is to inspect how this primitive is carried into the `6B` behavioural context and streams:

- `s1_arrival_entities_6B`
- `s2_event_stream_baseline_6B`
- `s2_flow_anchor_baseline_6B`
- `s3_event_stream_with_fraud_6B`
- `s3_flow_anchor_with_fraud_6B`
