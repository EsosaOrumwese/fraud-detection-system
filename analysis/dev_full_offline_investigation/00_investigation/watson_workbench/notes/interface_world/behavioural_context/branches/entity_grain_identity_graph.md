# Branch Investigation: Entity Grain and Identity Graph

## Branch question

The parent behavioural-context investigation established that `s1_arrival_entities_6B` is the arrival-level context surface that attaches entity identifiers to the operating stream world. This branch asks:

> What does the entity context surface actually represent, and what kind of identity graph does it expose for later fraud analytics?

The short answer is that `s1_arrival_entities_6B` is not a customer master table and not a merchant catalogue. It is an arrival-grain identity binding surface. Each row records one arrival and attaches that arrival to a merchant, party, account, instrument, device, IP, and session. In platform terms, this is the surface that makes a thin authorization stream analytically usable: it gives the operating world the entity handles needed for feature construction, replay, case review, entity risk, and network-style investigation.

The important caution is that the entity graph currently looks broad but also highly governed. Party, account, instrument, and device populations are almost identical in size and have nearly identical arrival-reuse distributions. That suggests a tightly coupled synthetic identity design. The IP layer behaves differently and is much more reused. So the first analytical read is not simply "we have an identity graph"; it is that some parts of the graph may be more useful for network analysis than others.

## Evidence used

Primary report:

- [`../behavioural_context_investigation.md`](../behavioural_context_investigation.md)

Contract references:

- [`docs/model_spec/data-engine/interface_pack/data_engine_interface.md`](../../../../../../../../docs/model_spec/data-engine/interface_pack/data_engine_interface.md)
- [`docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml`](../../../../../../../../docs/model_spec/data-engine/layer-3/specs/contracts/6B/dataset_dictionary.layer3.6B.yaml)
- [`docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml`](../../../../../../../../docs/model_spec/data-engine/layer-3/specs/contracts/6B/schemas.6B.yaml)

Pinned data surface:

- [`runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s1_arrival_entities_6B`](../../../../../../../../runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/data/layer3/6B/s1_arrival_entities_6B)

Parent exports:

- [`arrival_entities_schema.csv`](../../../../exports/interface_world/behavioural_context/arrival_entities_schema.csv)
- [`arrival_entities_profile.csv`](../../../../exports/interface_world/behavioural_context/arrival_entities_profile.csv)
- [`arrival_entities_nulls.csv`](../../../../exports/interface_world/behavioural_context/arrival_entities_nulls.csv)

Branch exports:

- [`entity_cardinality_profile.csv`](../../../../exports/interface_world/behavioural_context/branches/entity_grain_identity_graph/entity_cardinality_profile.csv)
- [`entity_arrival_reuse_summary.csv`](../../../../exports/interface_world/behavioural_context/branches/entity_grain_identity_graph/entity_arrival_reuse_summary.csv)
- [`top_merchant_id_by_arrivals.csv`](../../../../exports/interface_world/behavioural_context/branches/entity_grain_identity_graph/top_merchant_id_by_arrivals.csv)

The branch adds exact cardinality and arrival-reuse summaries for `s1_arrival_entities_6B`. A broader entity fanout scan was deliberately not carried forward into the report because the useful first-order branch question can be answered from exact cardinalities, per-entity arrival reuse, and the contract-defined row grain without materializing heavy many-to-many projections.

## What this surface is

The contract describes `s1_arrival_entities_6B` as arrival events enriched with entity attachments and session identifiers, with one row per arrival. Its primary key is:

- `seed`
- `manifest_fingerprint`
- `scenario_id`
- `merchant_id`
- `arrival_seq`

That key matters. It means the grain is not "one row per party" or "one row per account." The row is one observed arrival in the operating world, and the entity columns are the identifiers attached to that arrival.

The surface has these required business/context fields:

| Field | Operating meaning in this platform |
|---|---|
| `merchant_id` | The merchant/outlet-facing operating entity where the arrival occurs. |
| `arrival_seq` | The merchant-local arrival sequence used to identify the arrival within the run. |
| `ts_utc` | The event-time timestamp for the arrival. |
| `party_id` | The customer/person-like party attached to the arrival. |
| `account_id` | The account relationship used by the party for the arrival. |
| `instrument_id` | The payment instrument or card-like handle used for the arrival. |
| `device_id` | The device handle associated with the arrival. |
| `ip_id` | The IP/network handle associated with the arrival. |
| `session_id` | The session handle that groups one or more arrivals. |

So the row is best read as an arrival-level identity binding rather than a proven ownership hierarchy:

`arrival = {merchant_id, party_id, account_id, instrument_id, device_id, ip_id, session_id, ts_utc}`

This proves co-occurrence at arrival grain. It does not yet prove that these IDs form a validated many-to-many graph or a strict directed chain. That fanout question is a follow-on branch.

This is exactly why the behavioural streams are intentionally thin. The event stream carries the authorization event grammar. `s1_arrival_entities_6B` carries the entity handles needed to make those events meaningful for risk analysis.

## Physical profile and completeness

The surface contains:

| Metric | Value |
|---|---:|
| Rows / arrivals | `236,691,694` |
| Merchants | `4,050` |
| Time span | `2026-01-01T00:00:00.001940Z` to `2026-03-31T23:59:59.944516Z` |
| Arrival sequence range | `1` to `841,654` |
| Seeds / manifests / parameter hashes / scenarios | `1` each |

The required fields are complete. There are no nulls in `scenario_id`, `arrival_seq`, `merchant_id`, `ts_utc`, `party_id`, `account_id`, `instrument_id`, `device_id`, `ip_id`, `session_id`, `seed`, `manifest_fingerprint`, or `parameter_hash`.

That gives us a clean join surface. Missingness is not the first issue here. The more important question is what kind of entity world the complete surface is describing.

## Exact entity cardinalities

The exact distinct counts from the branch export are:

| Entity type | Distinct entities | Arrival rows represented |
|---|---:|---:|
| `merchant_id` | `4,050` | `236,691,694` |
| `party_id` | `5,588,988` | `236,691,694` |
| `account_id` | `5,589,035` | `236,691,694` |
| `instrument_id` | `5,589,071` | `236,691,694` |
| `device_id` | `5,589,056` | `236,691,694` |
| `ip_id` | `2,394,218` | `236,691,694` |
| `session_id` | `184,820,742` | `236,691,694` |

This is the first important shape. The merchant population is tiny compared with the customer/account/device world. There are only `4,050` merchants, but roughly `5.59M` parties, accounts, instruments, and devices. That means any analysis that stays only at merchant grain will miss most of the identity structure exposed by the platform.

The second shape is more subtle. Party, account, instrument, and device counts are almost the same. In a real financial-services identity graph, we would often expect these populations to differ more strongly: one party can have several accounts, one account can have several instruments, a device can be shared, and an instrument can move across devices. Here, the equal cardinalities do not prove a strict one-to-one mapping, but they are a strong early signal that the synthetic identity design may be highly coupled.

The IP population is different: `2.39M` IPs for `236.69M` arrivals. That is materially fewer than parties/devices/accounts, which means IPs are reused more heavily. This makes IP one of the more promising context handles for network-style analysis, shared-infrastructure analysis, and concentration checks.

The session population is much larger: `184.82M` sessions. That does not mean sessions are the richest identity layer. It means sessions are numerous and short, which the reuse profile confirms.

## Arrival reuse by entity type

The arrival-reuse summary shows how many arrival rows each entity type tends to carry. The entity counts, represented arrivals, minimums, maximums, and means are exact in the export; the percentile columns are approximate quantiles from DuckDB and should be read as distribution-shape evidence rather than exact order statistics.

| Entity type | Entities | Approx median arrivals | Approx P95 arrivals | Approx P99 arrivals | Max arrivals | Mean arrivals |
|---|---:|---:|---:|---:|---:|---:|
| `merchant_id` | `4,050` | `35,618` | `189,890` | `408,075` | `841,654` | `58,442.39` |
| `party_id` | `5,588,988` | `36` | `75` | `83` | `114` | `42.35` |
| `account_id` | `5,589,035` | `36` | `75` | `83` | `114` | `42.35` |
| `instrument_id` | `5,589,071` | `36` | `75` | `83` | `114` | `42.35` |
| `device_id` | `5,589,056` | `36` | `75` | `83` | `114` | `42.35` |
| `ip_id` | `2,394,218` | `40` | `433` | `635` | `1,481` | `98.86` |
| `session_id` | `184,820,742` | `1` | `2` | `3` | `10` | `1.28` |

This table gives the branch its main analytical shape.

Merchants are high-volume operating nodes. The median merchant has `35,618` arrivals, the P95 merchant has `189,890`, and the maximum merchant has `841,654`. This is expected because merchants are the operating venues where many parties and transactions pass through.

Party, account, instrument, and device IDs have almost identical reuse distributions. Median reuse is `36` arrivals, P95 is `75`, P99 is `83`, and max is `114` across all four entity types. That is unusually symmetric. It strongly suggests that these four identities were generated under a shared template or tightly coupled policy. For analytics, that means we should be careful before assuming that account-level, instrument-level, and device-level analyses are independent views of the world. They may produce similar results because the underlying synthetic design made them move together.

IP IDs break that symmetry. The median IP carries `40` arrivals, but P95 is `433`, P99 is `635`, and max is `1,481`. IP reuse is much heavier than party/account/instrument/device reuse. If we want a branch that can actually expose shared infrastructure, concentration, bot-like reuse, or network-risk behaviour, IP is a better first lead than account/device fanout.

Sessions are mostly short. The median session has `1` arrival, P95 has `2`, P99 has `3`, and the maximum has `10`. This agrees with the parent session-index finding that most sessions contain one or two arrivals. So session is useful for reconstructing short behavioural windows, but it is not a long-chain behavioural history for most traffic.

## What the identity graph can and cannot support

The surface can support several real analytical tasks:

- joining thin stream events back to entity handles
- counting exposure by party, account, instrument, device, IP, session, or merchant
- comparing row-weighted traffic to entity-weighted traffic
- checking whether fraud, abuse, disputes, chargebacks, or bank-action disagreements concentrate on specific entity handles
- building offline features and case-review context around entity recurrence
- asking whether shared IPs or repeated sessions mark operationally meaningful risk clusters

But the current branch also exposes limits.

First, the row does not by itself prove true many-to-many identity relationships. It records co-occurrence at arrival grain. To prove that devices are shared by many parties, or that parties use many accounts, we need a fanout branch that explicitly groups one entity type against another. This branch gives the first evidence that such a fanout branch is worth doing, but it does not claim to have completed it.

Second, the symmetric reuse profile across party/account/instrument/device suggests that those surfaces may not add as much independent analytical variety as their names imply. They are still useful handles, but we should not assume they behave like separately evolved real-world identity systems until fanout evidence proves that.

Third, session context is operationally different from the other identity handles. `session_id` is present on the arrival entity surface, but the separate `s1_session_index_6B` contains closure fields such as `session_end_utc` and `arrival_count`, which are batch-only. So session identity can be attached to an arrival, but full session summary features must not be treated as live decision-time features.

## Operating-platform interpretation

For the live fraud decisioning platform, the entity context layer is the bridge between event movement and entity meaning.

An authorization stream row can tell us that a request or response occurred. It cannot, by itself, tell us which party, account, instrument, device, IP, or session should be considered when evaluating risk. `s1_arrival_entities_6B` supplies those handles at arrival grain.

This matters for later stakeholder-facing analytics. If the eventual question is about customer friction, account exposure, suspicious device reuse, repeated IP infrastructure, merchant concentration, or case-review workload, the context surface is where those denominators come from. A fraud dashboard that only counts event rows will not know whether it is seeing many customers, one customer many times, many devices, one IP pool, or one merchant's high-volume operating pattern.

The graph is therefore useful, but it is not automatically realistic enough for every advanced analytics claim. The current evidence says:

- merchant grain is broad enough to support merchant-volume and merchant-risk analysis
- entity grain is broad enough to support party/account/device/instrument exposure analysis
- IP grain is the strongest early candidate for shared-network analysis
- session grain is mostly short-window reconstruction, not long behavioural history
- party/account/instrument/device symmetry is a realism and modelling caution

## Leads exposed by this branch

1. **Fanout branch needed.** The next deeper identity question is whether parties, accounts, instruments, devices, and IPs form meaningful many-to-many relationships or mostly move in lockstep.

2. **IP reuse looks analytically promising.** IPs are fewer and more reused than parties/accounts/instruments/devices, making IP a strong candidate for network-risk and concentration analysis.

3. **Party/account/instrument/device symmetry may limit realism.** Their exact cardinalities and reuse distributions are nearly identical. That could make some entity-level analyses redundant unless fanout proves otherwise.

4. **Session identity is not the same as session summary.** `session_id` can identify the arrival's session, but session closure attributes belong to batch/offline reconstruction.

5. **Merchant-volume inequality still matters.** The top merchant reaches `841,654` arrivals, while the median merchant has `35,618`. Merchant exposure can dominate row-weighted context analysis if not controlled.

## Working conclusion

`s1_arrival_entities_6B` is the arrival-grain identity binding surface for the behavioural context layer. It turns thin stream traffic into a usable fraud-platform world by attaching each arrival to merchant, party, account, instrument, device, IP, and session handles.

The surface is complete and coherent at required-field level, and it is rich enough to support entity-aware analytics. But the first statistical read shows a governed synthetic identity world rather than an obviously organic one. Party, account, instrument, and device IDs are broad but highly symmetric. IPs are much more reused. Sessions are numerous and short.

So the next useful branch should not simply describe more columns. It should test identity fanout directly: how many accounts per party, instruments per account, devices per party, parties per device, parties per IP, and merchants per entity. That is the branch that will tell us whether the context layer can support realistic network-style fraud analytics or whether its strongest defensible use is simpler entity exposure and IP/session concentration analysis.
