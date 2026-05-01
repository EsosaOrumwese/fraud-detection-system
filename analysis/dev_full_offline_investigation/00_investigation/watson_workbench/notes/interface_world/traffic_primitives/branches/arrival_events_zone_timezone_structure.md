# Branch Investigation: `arrival_events_5B` Zone and Timezone Structure

## Branch question

The main `arrival_events_5B` report says the surface covers `339` zone representations, that every merchant appears in more than one zone, and that the UTC-hour profile has a visible business-day shape.

This branch unpacks those statements together because they are connected. The question is:

> What does `zone_representation` mean in the arrival-context surface, how does it relate to the timezone fields, and does the global UTC-hour shape hold once we inspect zone-level structure?

The short answer is that `zone_representation` is not merchant domicile and not simply the active timezone. It is an arrival/routing representation attached to the arrival context. The timezone fields carry the clock interpretation. The UTC-hour shape is real at the global surface level, but it should not be treated as a universal zone-level pattern.

## Evidence used

Primary report:

- [`arrival_events_5B_investigation.md`](../arrival_events_5B_investigation.md)

Workbench script:

- [`analyze_arrival_events_zone_timezone_structure.py`](../../../../scratch/analyze_arrival_events_zone_timezone_structure.py)

Workbench exports:

- [`zone_timezone_overview.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/zone_timezone_overview.csv)
- [`zone_timezone_null_profile.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/zone_timezone_null_profile.csv)
- [`zone_overview.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/zone_overview.csv)
- [`zone_distribution_stats.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/zone_distribution_stats.csv)
- [`zone_concentration_ranked.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/zone_concentration_ranked.csv)
- [`merchant_zone_distribution.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/merchant_zone_distribution.csv)
- [`merchant_top_zone_dependence.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/merchant_top_zone_dependence.csv)
- [`timezone_field_relationships.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/timezone_field_relationships.csv)
- [`timezone_field_relationships_by_route.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/timezone_field_relationships_by_route.csv)
- [`zone_timezone_equality_by_route.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/zone_timezone_equality_by_route.csv)
- [`hour_profile_utc.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/hour_profile_utc.csv)
- [`hour_profile_local.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/hour_profile_local.csv)
- [`local_vs_utc_peak_summary.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/local_vs_utc_peak_summary.csv)
- [`zone_hour_profile_top_zones.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/zone_hour_profile_top_zones.csv)
- [`zone_hour_shape_summary.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/zone_hour_shape_summary.csv)
- [`zone_hour_shape_rollup.csv`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/zone_hour_shape_rollup.csv)
- [`zone_timezone_structure_summary.json`](../../../../exports/interface_world/traffic_primitives/branches/zone_timezone_structure/zone_timezone_structure_summary.json)

## What the zone field is doing

`arrival_events_5B` carries four related but distinct fields:

| Field | What it gives us in the operating surface |
|---|---|
| `zone_representation` | Arrival/routing zone label attached to the context row. |
| `tzid_primary` | Primary local-clock interpretation for the arrival. |
| `tzid_settlement` | Settlement-clock interpretation for the arrival. |
| `tzid_operational` | Operational local-clock interpretation for the arrival. |

These fields are complete. There are no nulls in `zone_representation`, the three timezone ids, UTC hour, or the local-hour fields extracted from the primary, settlement, and operational timestamps.

That completeness is useful, but it does not mean the fields are interchangeable. A row can have a zone representation that differs from the timezone used to interpret its local clock. In the full surface:

- rows: `236,691,694`
- zone representations: `339`
- primary timezones: `281`
- settlement timezones: `227`
- operational timezones: `281`
- distinct `zone_representation + tzid_primary` pairs: `11,854`
- distinct timezone triples: `1,331`
- rows where `zone_representation = tzid_primary`: `93,072,135`, or about `39.3%`
- rows where `zone_representation = tzid_operational`: `93,072,135`, also about `39.3%`

So `zone_representation` sometimes matches the active timezone label, but most rows do not have that equality. The field should therefore not be read as "the timezone of the row" without checking the timezone columns. In the platform context, the safer interpretation is that zone belongs to arrival/routing representation, while the timezone columns tell us which clocks should be used for primary, settlement, and operational reads.

## Zone exposure is broad, but not flat

The largest zones by row count are:

| Zone | Rows | Row share | Merchants | Sites | Edges | Primary timezones |
|---|---:|---:|---:|---:|---:|---:|
| `Europe/Paris` | `18,850,372` | `7.96%` | `2,011` | `33,785` | `1,214` | `136` |
| `Europe/Berlin` | `12,651,836` | `5.35%` | `2,046` | `37,876` | `1,365` | `140` |
| `Europe/Oslo` | `12,011,938` | `5.07%` | `313` | `6,146` | `264` | `43` |
| `Europe/Luxembourg` | `11,168,076` | `4.72%` | `1,707` | `25,376` | `934` | `132` |
| `Europe/Zurich` | `10,006,135` | `4.23%` | `1,818` | `26,585` | `1,122` | `134` |
| `Africa/Accra` | `8,764,162` | `3.70%` | `143` | `2,763` | `178` | `35` |
| `Europe/Monaco` | `5,208,486` | `2.20%` | `1,131` | `14,049` | `416` | `80` |

The top zone is meaningful, but it does not dominate the surface by itself. `Europe/Paris` holds less than `8%` of all rows. At the same time, the zone surface is not flat:

- top `5` zones hold about `27.3%` of rows
- top `10` zones hold about `39.2%` of rows
- top `20` zones hold about `55.2%` of rows
- top `50` zones hold about `77.4%` of rows
- top `100` zones hold about `90.4%` of rows

This is an exposure-concentration pattern, not a single-zone domination pattern. The arrival-context platform surface is geographically and operationally broad, but most arrival exposure still sits in a relatively concentrated head of the zone distribution.

The top-zone table also shows why zone cannot be simplified to timezone. `Europe/Paris` appears with `136` distinct primary timezones, and `Europe/Berlin` appears with `140`. Those are not plausible if the zone field simply meant "the row's local clock." They make sense if the zone is a routing/representation surface that can carry traffic whose active local-clock fields vary.

## Zone is not merchant-home identity

The main report already noted that every merchant appears in more than one zone. The branch-level distribution makes the point stronger:

| Metric | Value |
|---|---:|
| merchants | `4,050` |
| minimum zones per merchant | `2` |
| p25 zones per merchant | `5` |
| median zones per merchant | `11` |
| mean zones per merchant | `15.05` |
| p75 zones per merchant | `22` |
| p95 zones per merchant | `42` |
| maximum zones per merchant | `64` |

If `zone_representation` were merchant domicile or a fixed merchant-home field, the minimum and median would not look like this. A merchant can participate across many zones in this arrival-context surface.

There is a second nuance. Multi-zone does not mean evenly distributed across zones. For each merchant, we measured the share of that merchant's rows held by its largest zone:

| Metric | Top-zone row share per merchant |
|---|---:|
| p25 | `54.0%` |
| median | `70.6%` |
| mean | `67.5%` |
| p75 | `82.9%` |
| p95 | `93.6%` |

So most merchants are multi-zone, but many still have a dominant zone. That matters for later analysis. A merchant-level read and a zone-level read can both be true while answering different questions. If we group fraud, case, or flow behaviour by zone, we are grouping arrival exposure by routing representation. We are not simply grouping merchants by home country or home timezone.

## Timezone fields carry different clock meanings

Most rows have all three timezone fields equal:

| Timezone relationship | Rows | Row share | Merchants | Zones |
|---|---:|---:|---:|---:|
| all three equal | `218,869,380` | `92.47%` | `3,988` | `339` |
| primary equals operational only | `17,822,314` | `7.53%` | `157` | `267` |

The route split explains this relationship:

| Route mode | Timezone relationship | Rows | Share within route | Merchants | Zones |
|---|---|---:|---:|---:|---:|
| physical | all three equal | `216,136,107` | `100.00%` | `3,893` | `339` |
| virtual | primary equals operational only | `17,822,314` | `86.70%` | `157` | `267` |
| virtual | all three equal | `2,733,273` | `13.30%` | `95` | `205` |

This is an operating distinction. Physical arrivals collapse primary, settlement, and operational clocks into the same timezone in this primitive. Virtual arrivals usually do not: for most virtual rows, primary and operational clocks match while settlement is separate.

That fits the route model already exposed in the physical/virtual branch. Physical arrivals attach to physical site context. Virtual arrivals attach to operational edge context and can carry a separate settlement anchor. Therefore, if we later compare case rates or traffic rhythms by local time, we must choose the clock deliberately. Operational local time and settlement local time are not guaranteed to answer the same question for virtual traffic.

## UTC-hour shape exists, but it is a mixed-clock view

At the global surface level, UTC hour has the business-day shape described in the main report:

| Clock field | Peak hour | Peak share | Trough hour | Trough share | Share in 10-17 band | Share in 03-05 band |
|---|---:|---:|---:|---:|---:|---:|
| UTC | `15` | `5.40%` | `4` | `2.77%` | `42.28%` | `8.50%` |
| primary local | `17` | `5.98%` | `5` | `2.15%` | `45.27%` | `6.86%` |
| operational local | `17` | `5.98%` | `5` | `2.15%` | `45.27%` | `6.86%` |
| settlement local | `18` | `6.00%` | `5` | `2.12%` | `45.05%` | `6.84%` |

The UTC profile is therefore real, but it is not the cleanest clock for operating interpretation. UTC mixes traffic from many active local clocks. The local-clock profiles concentrate a little more strongly into the operating-day band and reduce the early-hour low band. That is exactly what we should expect if the platform receives traffic from a global operating world but each row also carries local clock context.

The zone-level check prevents overclaiming the global UTC shape. Across all `339` zones:

- `134` zones have their UTC peak hour inside the global `10:00-17:00` UTC band
- `77` zones have their UTC trough inside the global `03:00-05:00` UTC low band

Restricting to the `189` zones with at least `100,000` rows:

- `84` zones have their UTC peak inside `10:00-17:00`
- `59` zones have their UTC trough inside `03:00-05:00`

So the global UTC-hour story does not flow cleanly through every zone. Some high-volume zones peak inside the global band, but many do not. Examples from the largest zones show the variation:

| Zone | Rows | Peak UTC hour | Trough UTC hour | Share in 10-17 UTC |
|---|---:|---:|---:|---:|
| `Europe/Paris` | `18,850,372` | `11` | `5` | `45.74%` |
| `Europe/Berlin` | `12,651,836` | `13` | `23` | `51.11%` |
| `Africa/Accra` | `8,764,162` | `18` | `4` | `40.57%` |
| `Asia/Shanghai` | `3,870,505` | `5` | `21` | `28.32%` |
| `America/New_York` | `3,628,474` | `15` | `10` | `35.08%` |

That variation is not a defect. It is the expected consequence of global traffic viewed through UTC. For platform analysis, UTC is useful for checking extract continuity, global ingestion rhythm, and warehouse scheduling. It is weaker for interpreting local customer or merchant operating behaviour unless we explicitly frame the question as UTC-facing.

## Working interpretation

`arrival_events_5B` carries a zone/time structure with three layers:

- `zone_representation` gives the arrival/routing representation.
- `tzid_primary`, `tzid_settlement`, and `tzid_operational` give the clock contexts.
- UTC hour gives a global time axis that is useful but mixed across local operating clocks.

The practical rule is that zone-level analysis must be named carefully. A zone finding is not automatically a merchant-home finding, a country finding, or a local-time finding. It is a finding about arrival exposure under the zone representation carried by the traffic primitive.

The UTC-hour branch should not be split off as a separate universal assumption. It belongs here because its interpretation depends on zone and timezone structure. The global UTC rhythm is visible, but later analytical work should prefer local-clock views when the question concerns merchant/customer operating behaviour, and UTC views when the question concerns global platform ingestion or extract coverage.

## Leads carried forward

This branch creates several later checks:

- When behavioural streams are joined back to arrival context, test whether risk/event patterns differ by `zone_representation`, but phrase them as arrival-route exposure unless other evidence justifies a stronger geographic claim.
- For physical traffic, a single local clock is usually enough because primary, settlement, and operational timezones are equal in this primitive.
- For virtual traffic, operational-time and settlement-time views should be kept separate because most virtual rows have a distinct settlement clock.
- Any dashboard using hour-of-day should decide upfront whether it is a UTC operations dashboard or a local operating-time dashboard.
- Zone-level rate denominators should be exposure-weighted and merchant-aware, because merchants are multi-zone but often have a dominant zone.
