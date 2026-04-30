# Branch Investigation: `arrival_events_5B` Channel Structure

## Branch question

The surface-level report says that `arrival_events_5B` has two channel groups, and that no merchant appears in more than one channel.

This branch exists to unpack what that means in the operating fraud platform.

The question is:

> Is `channel_group` behaving like event-level variation, merchant-level operating identity, or something else inside the arrival-context surface?

That distinction matters because a channel field can be misread very easily. If channel varied freely row by row, then it would describe transaction-level routing choice at arrival grain. If channel is stable per merchant, then it behaves more like the merchant's operating lane inside the platform's arrival context. Those two readings lead to different later analyses.

## Evidence used

Primary references:

- [`docs/model_spec/data-engine/interface_pack/data_engine_interface.md`](../../../../../../../docs/model_spec/data-engine/interface_pack/data_engine_interface.md)
- [`docs/model_spec/data-engine/layer-2/specs/contracts/5B/dataset_dictionary.layer2.5B.yaml`](../../../../../../../docs/model_spec/data-engine/layer-2/specs/contracts/5B/dataset_dictionary.layer2.5B.yaml)
- [`docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml`](../../../../../../../docs/model_spec/data-engine/layer-2/specs/contracts/5B/schemas.5B.yaml)
- [`docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md`](../../../../../../../docs/model_spec/platform/migration_to_dev/dev_full_platform_green_v0_run_process_flow.md)

Workbench evidence:

- [`arrival_events_5B_investigation.md`](../arrival_events_5B_investigation.md)
- [`analyze_arrival_events_channel_structure.py`](../../../../scratch/analyze_arrival_events_channel_structure.py)
- [`channel_overview.csv`](../../../../exports/interface_world/traffic_primitives/branches/channel_structure/channel_overview.csv)
- [`channel_by_route_mode.csv`](../../../../exports/interface_world/traffic_primitives/branches/channel_structure/channel_by_route_mode.csv)
- [`merchant_channel_stability.csv`](../../../../exports/interface_world/traffic_primitives/branches/channel_structure/merchant_channel_stability.csv)
- [`merchant_volume_by_channel.csv`](../../../../exports/interface_world/traffic_primitives/branches/channel_structure/merchant_volume_by_channel.csv)
- [`channel_daily_summary.csv`](../../../../exports/interface_world/traffic_primitives/branches/channel_structure/channel_daily_summary.csv)
- [`channel_daily_share_stats.csv`](../../../../exports/interface_world/traffic_primitives/branches/channel_structure/channel_daily_share_stats.csv)
- [`channel_structure_summary.json`](../../../../exports/interface_world/traffic_primitives/branches/channel_structure/channel_structure_summary.json)

## What channel means at arrival grain

At the surface grain, one row is one merchant-local arrival-context observation. `channel_group` does not identify the row by itself. It gives the arrival's operating lane:

- `card_present`
- `card_not_present`

The key question is whether the same merchant can appear in both lanes. In this run, the answer is no.

| Distinct channel groups per merchant | Merchants | Rows |
|---:|---:|---:|
| `1` | `4,050` | `236,691,694` |

Every merchant has exactly one observed `channel_group`.

That is the central finding of this branch. Inside `arrival_events_5B`, channel behaves as merchant-stable operating identity, not as a row-by-row customer or transaction choice. A merchant's arrivals are all carried through one channel lane in this primitive.

This does not mean real payment behaviour could never vary by channel in a different system. It means that in this interface surface, as received for this operating horizon, `channel_group` partitions the merchant population into two stable lanes.

## Participation versus exposure

The two channel groups do not carry the same amount of merchant participation or row exposure.

| Channel | Rows | Row share | Merchants | Merchant share | Sites | Edges |
|---|---:|---:|---:|---:|---:|---:|
| `card_present` | `157,117,536` | `66.38%` | `3,261` | `80.52%` | `68,780` | `537` |
| `card_not_present` | `79,574,158` | `33.62%` | `789` | `19.48%` | `9,736` | `2,468` |

The participation story and the exposure story are not the same.

`card_present` contains most merchants: `80.52%` of the merchant population. It also contains most rows: `66.38%` of arrivals. So card-present is the broad merchant-participation lane and the larger arrival-volume lane.

`card_not_present` contains only `19.48%` of merchants but still carries `33.62%` of arrivals. That means card-not-present merchants are heavier, on average, at arrival grain. The channel is smaller by merchant count, but not proportionally small by platform exposure.

This is why channel analysis cannot stop at raw row share. A row-weighted read answers "what share of arrival exposure belongs to this channel?" A merchant-weighted read answers "what share of merchants operate in this channel?" Here those answers diverge.

## Merchant volume inside each channel

The per-merchant arrival distribution confirms that card-not-present is the heavier lane at merchant grain.

| Channel | Merchants | Median rows per merchant | Mean rows per merchant | p95 rows per merchant | Max rows per merchant |
|---|---:|---:|---:|---:|---:|
| `card_present` | `3,261` | `32,162` | `48,181` | `144,057` | `841,654` |
| `card_not_present` | `789` | `66,662` | `100,854` | `308,314` | `836,294` |

Card-not-present has:

- `2.09x` the mean rows per merchant of card-present
- `2.07x` the median rows per merchant of card-present
- `2.14x` the p95 rows per merchant of card-present

This makes the exposure imbalance clearer. Card-not-present is not just a smaller lane with fewer merchants. Its merchants are materially more arrival-dense across the distribution, including at the center and the upper tail.

That matters for later fraud and case analysis. If a future chart shows card-not-present contributing a large share of events, alerts, fraud labels, or cases, that may reflect both risk difference and exposure difference. We will need rates and denominators, not only counts.

## Channel and route mode are related, but not identical

`channel_group` and `is_virtual` are not the same field, and the data proves they should not be collapsed into one another.

| Channel | Route mode | Rows | Share within channel | Share within route mode | Merchants | Sites | Edges |
|---|---|---:|---:|---:|---:|---:|---:|
| `card_present` | physical | `153,665,526` | `97.80%` | `71.10%` | `3,229` | `68,780` | `0` |
| `card_present` | virtual | `3,452,010` | `2.20%` | `16.79%` | `32` | `0` | `537` |
| `card_not_present` | physical | `62,470,581` | `78.51%` | `28.90%` | `664` | `9,736` | `0` |
| `card_not_present` | virtual | `17,103,577` | `21.49%` | `83.21%` | `125` | `0` | `2,468` |

The card-present lane is overwhelmingly physical: `97.80%` of its rows are physical-site arrivals. Only `2.20%` of card-present rows are virtual.

The card-not-present lane is still mostly physical by row count, but it carries a much larger virtual component: `21.49%` of card-not-present rows are virtual. Card-not-present also holds `83.21%` of all virtual rows and `82.13%` of all virtual edges.

This is the important nuance. Card-not-present is not equivalent to virtual routing, because most card-not-present rows are still physical in this surface. But virtual routing is heavily concentrated inside card-not-present. So the right interpretation is:

> Channel is a merchant-stable operating lane; virtual route mode is a routing context; the two interact strongly but are not interchangeable.

If we collapse them, we lose information. If we separate them, we can later ask better questions: whether fraud, flow behaviour, case creation, or false-positive burden is driven by channel, virtual routing, or their intersection.

## Daily continuity of the channel lanes

Both channel lanes are present across the full 90-day operating window.

| Channel | Days present | Min daily share | Median daily share | Mean daily share | Max daily share | Daily share stddev |
|---|---:|---:|---:|---:|---:|---:|
| `card_present` | `90` | `60.96%` | `67.68%` | `66.34%` | `68.84%` | `2.62pp` |
| `card_not_present` | `90` | `31.16%` | `32.32%` | `33.66%` | `39.04%` | `2.62pp` |

The daily merchant counts are also stable:

- card-not-present has `789` active merchants every day
- card-present has `3,261` active merchants on most days, with a minimum of `3,260`

So the channel split is not caused by a short-lived period where one channel appears or disappears. Both channels are continuously present through the three-month extract.

The daily shares move within a bounded range. Card-present stays between `60.96%` and `68.84%` of daily arrival rows, while card-not-present stays between `31.16%` and `39.04%`. This is enough movement to matter for time-aware analysis, but not enough to suggest that channel coverage is intermittent or broken.

For the operating platform, this means channel is a stable segmentation axis. It can be used as a persistent denominator when later comparing traffic, fraud, labels, and cases, provided we keep the exposure imbalance in view.

## What this branch lets us trust

This branch gives us confidence in four things.

First, `channel_group` is complete and stable at merchant level in this arrival primitive. There is no evidence of merchants crossing channel lanes in this surface.

Second, both channel lanes are present throughout the full 90-day window. The channel split is not a partial-period artefact.

Third, channel is analytically meaningful because it changes both participation and exposure. Card-present is the broad merchant lane; card-not-present is the smaller but heavier lane.

Fourth, channel and route mode need to be handled together but separately. Card-not-present carries most virtual routing complexity, but it is not synonymous with virtual routing.

## What this branch does not prove

This branch does not prove that card-not-present is riskier.

It does not prove that virtual routing is riskier.

It does not prove that the platform should score channels differently.

It does not prove that card-present and card-not-present have different fraud rates, false-positive rates, case rates, or operational burdens.

Those claims require behavioural streams, truth products, and case surfaces. At this stage, the only defensible conclusion is about the shape of arrival exposure and merchant-channel identity.

## Working interpretation

`arrival_events_5B` exposes channel as a stable merchant operating lane in the arrival-context world.

The main split is not simply "two channels by row count." The stronger structure is:

- card-present is the larger and broader merchant lane
- card-not-present is a smaller merchant lane with heavier arrival exposure per merchant
- virtual routing is a minority route mode overall, but it is concentrated inside card-not-present
- both channels persist through the full January-March operating window

So channel should be carried forward as a first-class segmentation field, but not as a standalone explanation. Later investigations should compare channel against route mode, merchant volume, behavioural traffic, fraud truth, and case outcomes. The channel field tells us where operating exposure is partitioned; it does not yet tell us whether that exposure is safer, riskier, or more operationally costly.

## Leads exposed

1. Card-not-present has heavier arrival exposure per merchant. Later behavioural and truth analyses should compare channel-level rates using both row-weighted and merchant-weighted denominators.

2. Virtual routing is concentrated inside card-not-present. Later route-mode analysis should separate physical card-not-present from virtual card-not-present instead of treating all CNP traffic as one homogeneous block.

3. Channel is merchant-stable in `arrival_events_5B`. When inspecting `6B` event streams, we should verify whether that merchant-stable channel assignment carries through the behavioural surfaces or whether richer event bodies introduce additional channel semantics.

4. Daily channel shares are stable but not flat. If later fraud or case rates vary by date, channel mix should be checked as a possible denominator effect before interpreting the movement as a risk change.

5. The small set of card-present virtual merchants is unusual enough to preserve as a later check. It may be legitimate platform routing context, but it should not be silently absorbed into the ordinary physical card-present story.
