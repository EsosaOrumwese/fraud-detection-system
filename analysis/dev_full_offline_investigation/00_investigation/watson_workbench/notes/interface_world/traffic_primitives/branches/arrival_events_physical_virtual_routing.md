# Branch Investigation: `arrival_events_5B` Physical Versus Virtual Routing

## Branch question

The surface-level report says that the `site_id` / `edge_id` null profile is not random missingness. It encodes two route modes:

- physical arrivals: `is_virtual = false`, `site_id` populated, `edge_id` null
- virtual arrivals: `is_virtual = true`, `edge_id` populated, `site_id` null

This branch exists to unpack what that means in the operating fraud platform.

The question is:

> Is physical versus virtual routing merely a data-quality/null-profile detail, or is it a first-class operating split in the arrival-context surface?

The answer matters because downstream analysis will eventually compare behavioural streams, fraud truth, and case products. If route mode changes the denominator, endpoint density, merchant population, or channel intersection, then route mode must be preserved as analytical context rather than treated as a nuisance column.

## Evidence used

Primary references:

- [`docs/model_spec/data-engine/interface_pack/data_engine_interface.md`](../../../../../../../docs/model_spec/data-engine/interface_pack/data_engine_interface.md)
- [`docs/model_spec/data-engine/layer-2/specs/contracts/5B/dataset_dictionary.layer2.5B.yaml`](../../../../../../../docs/model_spec/data-engine/layer-2/specs/contracts/5B/dataset_dictionary.layer2.5B.yaml)
- [`docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml`](../../../../../../../docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml)
- [`docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s4.expanded.md`](../../../../../../../docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s4.expanded.md)
- [`docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s5.expanded.md`](../../../../../../../docs/model_spec/data-engine/layer-2/specs/state-flow/5B/state.5B.s5.expanded.md)

Workbench evidence:

- [`arrival_events_5B_investigation.md`](../arrival_events_5B_investigation.md)
- [`analyze_arrival_events_physical_virtual_routing.py`](../../../../scratch/analyze_arrival_events_physical_virtual_routing.py)
- [`route_overview.csv`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/route_overview.csv)
- [`route_consistency.csv`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/route_consistency.csv)
- [`merchant_route_stability.csv`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/merchant_route_stability.csv)
- [`merchant_volume_by_route.csv`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/merchant_volume_by_route.csv)
- [`endpoint_density.csv`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/endpoint_density.csv)
- [`route_by_channel.csv`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/route_by_channel.csv)
- [`route_daily_summary.csv`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/route_daily_summary.csv)
- [`route_daily_share_stats.csv`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/route_daily_share_stats.csv)
- [`top_zones_by_route.csv`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/top_zones_by_route.csv)
- [`physical_virtual_routing_summary.json`](../../../../exports/interface_world/traffic_primitives/branches/physical_virtual_routing/physical_virtual_routing_summary.json)

## What physical and virtual routing mean here

`is_virtual` is the route-endpoint flag of the arrival-context surface.

It is not the same thing as `channel_group`.

It is also not a generic boolean for "online transaction." In this surface, it tells the platform which kind of route endpoint the arrival is attached to:

| Route mode | Field contract | Operating meaning |
|---|---|---|
| physical | `is_virtual = false`, `site_id` populated, `edge_id` null | The arrival is attached to a physical merchant site/outlet. |
| virtual | `is_virtual = true`, `edge_id` populated, `site_id` null | The arrival is attached to a virtual edge from the virtual routing fabric. |

The 5B contract is strict on this. Physical arrivals must resolve to a valid `site_id`. Virtual arrivals must resolve to a valid `edge_id`. A row with both endpoint ids populated, both endpoint ids missing, or endpoint ids inconsistent with `is_virtual` is invalid by the route contract.

In company-operating language, this field tells us whether the arrival-context system should recover physical site context or virtual edge context when enriching later traffic. That affects joins, denominators, endpoint-level analysis, feature context, and later comparison of fraud/case rates by route mode.

## Route-mode scale

The arrival surface is mostly physical by rows and by merchants, but virtual routing is still a meaningful lane.

| Route mode | Rows | Row share | Merchants | Merchant share | Sites | Edges | Zones |
|---|---:|---:|---:|---:|---:|---:|---:|
| physical | `216,136,107` | `91.32%` | `3,893` | `96.12%` | `78,516` | `0` | `339` |
| virtual | `20,555,587` | `8.68%` | `157` | `3.88%` | `0` | `3,005` | `267` |

Physical routing is the dominant operating route. It covers nearly all merchants and most arrival rows.

Virtual routing is smaller, but not negligible. It accounts for only `3.88%` of merchants, yet `8.68%` of arrival rows. So virtual merchants are more arrival-dense on average than their merchant count suggests.

This is the first route-level denominator warning. If we count merchants, virtual routing looks very small. If we count arrival exposure, it is still a minority but more material. If we later count endpoints, it becomes another shape again: physical has `78,516` sites, while virtual has `3,005` edges.

## Endpoint key consistency

The endpoint-null profile is structurally clean.

| Route key state | Rows | Merchants |
|---|---:|---:|
| `physical_valid_site_only` | `216,136,107` | `3,893` |
| `virtual_valid_edge_only` | `20,555,587` | `157` |

No inconsistent route-key states appear in the compact check:

- no rows with both `site_id` and `edge_id` null
- no rows with both `site_id` and `edge_id` populated
- no physical rows missing `site_id`
- no virtual rows missing `edge_id`

This is why the nulls should not be treated as missing data. A null `edge_id` on a physical row is expected because physical rows are keyed by `site_id`. A null `site_id` on a virtual row is expected because virtual rows are keyed by `edge_id`.

The branch therefore changes how those columns should be handled in analysis. A generic null-count report would make the surface look partially missing. The contract-aware read says the route endpoint is complete, but represented by mutually exclusive columns.

## Merchant route stability

Route mode is merchant-stable in this primitive.

| Distinct route modes per merchant | Merchants | Rows |
|---:|---:|---:|
| `1` | `4,050` | `236,691,694` |

Every merchant appears in exactly one route mode over the three-month arrival-context extract.

This is a major interpretive fact. Route mode is not behaving as a row-by-row endpoint choice for the same merchant. It behaves like a merchant route assignment in this arrival primitive: a merchant is physical-routed or virtual-routed for this surface.

That does not mean future behavioural streams cannot carry more detailed event context. It means that within `arrival_events_5B`, route mode partitions the merchant population into stable route lanes. Later analysis should treat route mode as a merchant-level segmentation field unless a downstream surface proves more granular behaviour.

## Merchant exposure by route mode

Virtual routing has fewer merchants but heavier arrival exposure per merchant.

| Route mode | Merchants | Median rows per merchant | Mean rows per merchant | p95 rows per merchant | Max rows per merchant |
|---|---:|---:|---:|---:|---:|
| physical | `3,893` | `34,690` | `55,519` | `178,077` | `841,654` |
| virtual | `157` | `95,103` | `130,927` | `422,411` | `763,822` |

The virtual lane has:

- `2.36x` the mean rows per merchant of the physical lane
- `2.74x` the median rows per merchant of the physical lane
- `2.37x` the p95 rows per merchant of the physical lane

So virtual routing is not merely a tiny edge case attached to a few low-volume merchants. It is a smaller merchant population with materially heavier arrival exposure per merchant.

This matters for future fraud and case analysis. A virtual lane can produce a disproportionate amount of row-level activity relative to merchant count. Raw counts may therefore overstate or understate route differences unless the denominator is declared: arrival-weighted, merchant-weighted, endpoint-weighted, flow-weighted, label-weighted, or case-weighted.

## Endpoint density

Physical and virtual route endpoints also have different density profiles.

| Endpoint type | Endpoints | Rows | Median rows per endpoint | Mean rows per endpoint | p95 rows per endpoint | Max rows per endpoint |
|---|---:|---:|---:|---:|---:|---:|
| physical site | `78,516` | `216,136,107` | `967` | `2,753` | `10,710` | `403,212` |
| virtual edge | `3,005` | `20,555,587` | `3,394` | `6,840` | `24,693` | `137,585` |

Virtual edges are fewer than physical sites, but they are more arrival-dense:

- `2.49x` the mean rows per endpoint of physical sites
- `3.51x` the median rows per endpoint of physical sites
- `2.31x` the p95 rows per endpoint of physical sites

That gives route mode a second denominator layer. Merchant exposure is heavier in the virtual lane, and endpoint exposure is also heavier in the virtual lane. This suggests that virtual route analysis should not be reduced to "small share of rows." It has a compressed endpoint estate carrying a meaningful arrival load.

The endpoint maximums also show tails on both sides. The largest physical site carries `403,212` rows, while the largest virtual edge carries `137,585` rows. So physical has the broader estate and the highest single endpoint in this run, while virtual has the denser typical endpoint.

## Channel interaction

Route mode intersects with channel, but it does not collapse into channel.

| Route mode | Channel | Rows | Share within route mode | Share within channel | Merchants | Sites | Edges |
|---|---|---:|---:|---:|---:|---:|---:|
| physical | `card_present` | `153,665,526` | `71.10%` | `97.80%` | `3,229` | `68,780` | `0` |
| physical | `card_not_present` | `62,470,581` | `28.90%` | `78.51%` | `664` | `9,736` | `0` |
| virtual | `card_not_present` | `17,103,577` | `83.21%` | `21.49%` | `125` | `0` | `2,468` |
| virtual | `card_present` | `3,452,010` | `16.79%` | `2.20%` | `32` | `0` | `537` |

The route split and channel split are related in a strong but incomplete way.

Physical routing is mostly card-present, but not exclusively. Virtual routing is mostly card-not-present, but not exclusively. This is consistent with the channel branch's interpretation: `channel_group` describes acceptance lane, while `is_virtual` describes routing endpoint.

The route branch therefore preserves four operating contexts:

- physical card-present
- physical card-not-present
- virtual card-present
- virtual card-not-present

That four-way structure is likely more useful for later fraud/case analysis than either `channel_group` alone or `is_virtual` alone.

## Time continuity

Both route modes are present across the full 90-day operating window.

| Route mode | Days present | Min daily share | Median daily share | Mean daily share | Max daily share | Daily share stddev |
|---|---:|---:|---:|---:|---:|---:|
| physical | `90` | `89.84%` | `91.50%` | `91.30%` | `92.21%` | `0.59pp` |
| virtual | `90` | `7.79%` | `8.50%` | `8.70%` | `10.16%` | `0.59pp` |

The virtual lane is not a short-period insertion or a partial extract artefact. It is present every day.

The daily share is also bounded. Virtual routing moves between `7.79%` and `10.16%` of daily arrivals. That is enough variation to matter when reading daily rates, but not enough to suggest that virtual coverage is intermittent.

So route mode can be used as a stable denominator across the full January-March period. Later daily fraud or case movements should still control for route mix, but the route denominator itself appears continuously available.

## Zone and timezone footprint

Physical routing covers all `339` observed zones. Virtual routing covers `267` zones.

Physical routing has `222` primary, settlement, and operational timezones. Virtual routing has `197` primary and operational timezones, but only `63` settlement timezones.

That tells us virtual routing is geographically broad but semantically different in its clock footprint. The route is not just a small local special case: it spans many zones and timezones. At the same time, its settlement-timezone footprint is more compressed than its primary/operational footprint, which matches the idea that virtual edge routing can carry different settlement versus operational clock semantics.

The top zones also differ by route mode:

| Route mode | Top zone | Rows | Share within route |
|---|---|---:|---:|
| physical | `Europe/Paris` | `17,433,798` | `8.07%` |
| virtual | `Europe/Luxembourg` | `1,461,604` | `7.11%` |

The top zone share is not overwhelming in either route mode. Physical and virtual route contexts are broad rather than dominated by one zone.

This is a caution for later geography work. Route mode and zone should not be collapsed. A virtual route is not automatically a single virtual geography; it still carries a distributed route/time context.

## What this branch lets us trust

This branch gives us confidence in the route endpoint structure of `arrival_events_5B`.

The endpoint keys are contract-consistent. Physical rows have `site_id` and no `edge_id`; virtual rows have `edge_id` and no `site_id`. The null pattern is therefore structural and should be interpreted, not cleaned away.

The route mode is stable at merchant level in this primitive. Every merchant appears in exactly one route lane.

Both route lanes persist through the whole operating window. Virtual routing is smaller, but present every day and materially arrival-dense.

Route mode carries independent analytical meaning from channel. Channel and route interact, but neither replaces the other.

## What this branch does not prove

This branch does not prove that virtual traffic is riskier.

It does not prove that physical traffic is safer.

It does not prove that virtual edges cause higher case rates, fraud rates, false-positive rates, or model burden.

It does not prove that the platform should score physical and virtual routes differently.

Those questions require behavioural streams, truth products, and case surfaces. At this stage, the defensible claim is about arrival-context route structure: endpoint mode, denominator shape, exposure density, and route-channel intersection.

## Working interpretation

Physical versus virtual routing is a first-class operating split in `arrival_events_5B`.

The surface is physically dominated by rows, merchants, and site estate, but virtual routing is not marginal in analytical meaning. It has fewer merchants and fewer endpoints, yet it carries heavier exposure per merchant and per endpoint. It is also present every day, spans many zones/timezones, and intersects strongly with card-not-present without being identical to it.

So route mode should be carried forward as a required segmentation field when we inspect behavioural streams, truth products, and case products. The wrong posture would be to treat `site_id` and `edge_id` nulls as missingness or to collapse virtual routing into card-not-present. The right posture is to preserve the route endpoint model and declare the denominator being used whenever physical and virtual are compared.

## Leads exposed

1. Virtual routing is more arrival-dense per merchant and per endpoint. Later fraud/case analysis should compare route-level rates using row, merchant, endpoint, flow, label, and case denominators where appropriate.

2. Route mode is merchant-stable in this primitive. When moving to `6B`, we should verify whether behavioural streams preserve this route assignment or introduce additional event-level route semantics.

3. The route-channel intersection should remain a four-way segmentation, not two separate one-dimensional cuts. Physical card-not-present and virtual card-present are both real observed contexts in this surface.

4. Virtual settlement-timezone coverage is much more compressed than virtual primary/operational timezone coverage. A later timezone branch should inspect what that means before using local-time features or settlement-time summaries.

5. Endpoint density is uneven in both physical and virtual estates. If later cases or fraud labels concentrate by endpoint, the first question should be whether that reflects endpoint exposure before interpreting it as endpoint risk.
