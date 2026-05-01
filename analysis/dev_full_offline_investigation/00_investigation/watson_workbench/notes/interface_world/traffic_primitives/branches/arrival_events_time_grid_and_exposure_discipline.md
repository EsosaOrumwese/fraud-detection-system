# Branch Investigation: `arrival_events_5B` Time Grid and Exposure Discipline

## Branch question

The earlier `arrival_events_5B` branches left three related issues unresolved:

- `bucket_index` is complete, but its repeated hourly rhythm had not been inspected as its own operating coordinate.
- Merchant arrival volume is unequal, which can distort later row-weighted rates.
- One date, `2026-03-22`, has `4,049` active merchants instead of `4,050`.

This branch closes those points together because they are all denominator-discipline questions:

> Can we trust `bucket_index` as a time-grid coordinate, and what exposure caveats must travel with it when later analysis moves into behavioural streams, truth products, and cases?

The short answer is yes, `bucket_index` is a clean UTC-hour grid coordinate. It covers every expected hour from `0` to `2,159`, and `bucket_index % 24` matches the UTC hour on every row. But it is not neutral: bucket intensity varies strongly by hour, channel, route mode, and merchant exposure. The one merchant-day exception is real but small and localized to a very low-volume merchant.

## Evidence used

Primary report:

- [`arrival_events_5B_investigation.md`](../arrival_events_5B_investigation.md)

Related branches:

- [`arrival_events_grain_and_identity.md`](arrival_events_grain_and_identity.md)
- [`arrival_events_time_coverage.md`](arrival_events_time_coverage.md)
- [`arrival_events_zone_timezone_structure.md`](arrival_events_zone_timezone_structure.md)
- [`grain_discipline_for_interface_analysis.md`](grain_discipline_for_interface_analysis.md)

Workbench script:

- [`analyze_arrival_events_time_grid_exposure_discipline.py`](../../../../scratch/analyze_arrival_events_time_grid_exposure_discipline.py)

Workbench exports:

- [`bucket_grid_summary.csv`](../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/bucket_grid_summary.csv)
- [`bucket_profile.csv`](../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/bucket_profile.csv)
- [`bucket_distribution_stats.csv`](../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/bucket_distribution_stats.csv)
- [`bucket_hour_profile.csv`](../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/bucket_hour_profile.csv)
- [`bucket_hour_by_channel_route.csv`](../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/bucket_hour_by_channel_route.csv)
- [`merchant_exposure_ranked.csv`](../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/merchant_exposure_ranked.csv)
- [`merchant_exposure_summary.csv`](../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/merchant_exposure_summary.csv)
- [`daily_merchant_presence.csv`](../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/daily_merchant_presence.csv)
- [`merchant_day_exception_context.csv`](../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/merchant_day_exception_context.csv)
- [`time_grid_exposure_discipline_summary.json`](../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/time_grid_exposure_discipline_summary.json)

## `bucket_index` is a complete UTC-hour grid

The bucket grid is exact:

| Check | Value |
|---|---:|
| rows | `236,691,694` |
| merchants | `4,050` |
| minimum `bucket_index` | `0` |
| maximum `bucket_index` | `2,159` |
| observed buckets | `2,160` |
| expected buckets | `2,160` |
| missing buckets | `0` |
| rows where `bucket_index % 24 != utc_hour` | `0` |
| buckets with any hour mismatch | `0` |

This is the strongest possible result for the field as a time-grid coordinate. The bucket index spans the full `90 x 24 = 2,160` hour grid, and its modulo-24 hour agrees with the parsed UTC timestamp on every row.

That does not make `bucket_index` a row identity. Many merchants and many arrivals share the same bucket. The field answers "which UTC-hour slot in the operating horizon does this arrival belong to?" It does not answer "which arrival is this?" Row identity still requires the declared key, especially `merchant_id + arrival_seq` inside the sealed run/scenario identity.

## Complete grid does not mean uniform traffic

Bucket row counts vary materially:

| Metric | Rows per bucket |
|---|---:|
| minimum | `68,584` |
| p05 | `73,242` |
| p25 | `84,559` |
| median | `108,028` |
| mean | `109,579` |
| p75 | `137,248` |
| p95 | `145,047` |
| maximum | `160,084` |

Each bucket is present, but the hourly intensity is not flat. The median bucket has about `108K` rows, while the maximum bucket has about `160K`. That is not a data-quality problem. It is the operating rhythm of the arrival-context surface.

The hourly bucket profile shows the same shape already seen in the UTC-hour branch, now grounded directly in `bucket_index`:

| UTC hour | Buckets | Rows | Mean rows per bucket |
|---:|---:|---:|---:|
| `3` | `90` | `6,647,756` | `73,864` |
| `4` | `90` | `6,560,221` | `72,891` |
| `5` | `90` | `6,907,887` | `76,754` |
| `10` | `90` | `12,328,907` | `136,988` |
| `11` | `90` | `12,456,834` | `138,409` |
| `14` | `90` | `12,590,512` | `139,895` |
| `15` | `90` | `12,775,002` | `141,944` |
| `17` | `90` | `12,519,701` | `139,108` |

The grid is complete at every UTC hour; each hour has `90` buckets, one per date. The difference is intensity. Early UTC hours around `03:00-05:00` carry much less traffic than the stronger daytime/afternoon hours.

The branch conclusion is therefore precise: `bucket_index` is safe as a time-coordinate denominator, but the analyst must not treat each bucket as equal traffic exposure.

## Hourly rhythm differs by operating lane

The grid-level hour shape is not identical across channel and route mode:

| Channel | Route mode | Rows | Peak UTC hour | Peak share | Trough UTC hour | Trough share |
|---|---|---:|---:|---:|---:|---:|
| `card_present` | physical | `153,665,526` | `12` | `6.58%` | `2` | `1.86%` |
| `card_present` | virtual | `3,452,010` | `0` | `6.81%` | `11` | `2.35%` |
| `card_not_present` | physical | `62,470,581` | `0` | `5.86%` | `12` | `2.60%` |
| `card_not_present` | virtual | `17,103,577` | `20` | `5.74%` | `9` | `2.80%` |

This is the important operating-context wrinkle. The same UTC-hour grid carries different rhythms depending on the lane being read. Card-present physical traffic peaks around midday UTC. Card-not-present physical traffic peaks around midnight UTC. Virtual card-not-present peaks later in UTC. Small card-present virtual traffic has its own shape.

That does not make the grid inconsistent. It means the grid is a common coordinate over heterogeneous operating lanes. If a later fraud or case metric varies by UTC hour, the first question should be whether the numerator changed, the denominator changed, or whether the channel/route mix changed inside that hour.

This is also why the zone/timezone branch matters. UTC-hour is useful for platform-wide alignment, but local-hour interpretation depends on the question and the lane.

## Merchant exposure inequality is cohort-weighted, not single-merchant dominated

Merchant row counts remain highly unequal:

| Metric | Rows per merchant |
|---|---:|
| minimum | `1,842` |
| p05 | `3,935` |
| p25 | `17,176` |
| median | `35,671` |
| mean | `58,442` |
| p75 | `69,228` |
| p95 | `189,748` |
| maximum | `841,654` |

The mean is well above the median, and the p95 is more than five times the median. That is the statistical basis for the row-weighting caution.

But the exposure is not dominated by one merchant:

| Merchant rank group | Cumulative row share |
|---|---:|
| top `1` merchant | `0.36%` |
| top `5` merchants | `1.65%` |
| top `10` merchants | `3.13%` |
| top `50` merchants | `11.19%` |
| top `100` merchants | `17.78%` |
| top `10%` of merchants (`405`) | `40.39%` |

This is a cohort concentration pattern. No single merchant controls the surface, but the high-volume merchant cohort matters a lot. The top `10%` of merchants carry about `40%` of all arrival rows.

That distinction matters for later stakeholder language. It would be wrong to say the arrival primitive is "dominated by a few merchants" if that implies one or two actors determine the surface. It is more accurate to say that arrival-weighted analysis is materially shaped by the high-volume merchant cohort. If we ask platform-load questions, that weighting is appropriate. If we ask typical-merchant questions, it is misleading.

The highest-ranked merchants also appear across all `2,160` buckets and all `90` dates. That means their high exposure is not caused by a short burst in one part of the horizon. It is sustained across the operating window.

## The `2026-03-22` merchant-day exception is localized

The daily merchant count is `4,050` on every date except `2026-03-22`, where it is `4,049`.

The missing merchant is:

| Missing UTC date | Merchant |
|---|---:|
| `2026-03-22` | `13317238460857713575` |

Its surrounding daily activity is small:

| Date | Rows |
|---|---:|
| `2026-03-19` | `25` |
| `2026-03-20` | `36` |
| `2026-03-21` | `7` |
| `2026-03-22` | `0` |
| `2026-03-23` | `26` |
| `2026-03-24` | `26` |
| `2026-03-25` | `17` |

This reads like a low-volume merchant with no arrivals on one date, not a platform-wide coverage failure. The date itself still has a full arrival surface and every other merchant is present.

The exception should still be recorded because it matters for strict merchant-day completeness claims. If an analysis later assumes every merchant appears every day, that assumption is false by one merchant-day. But for row-level denominator analysis, the exception is negligible.

## Working interpretation

This branch closes the remaining `arrival_events_5B` denominator issues.

`bucket_index` is a trustworthy UTC-hour grid coordinate. It is complete, ordered, and aligned with UTC hour. It can support time-window analysis, replay framing, hourly denominators, and joins into later surfaces.

The caution is that a complete grid is not a neutral grid. Arrival intensity varies by hour, lane, and merchant exposure. Later fraud, case, or event rates should therefore declare whether they are row-weighted, merchant-weighted, hourly, local-time, channel-specific, route-specific, or some combination.

The one merchant-day exception is real but localized. It should be carried as a completeness footnote, not treated as a blocker.

## Leads carried forward

This branch does not create another arrival-events branch. It converts the remaining arrival-surface concerns into rules for later interface-world analysis:

- Use `bucket_index` for UTC-hour alignment, but use local timestamp fields for local operating behaviour.
- Treat row-weighted rates as exposure-weighted rates.
- Use merchant-weighted views when the question is about the typical merchant rather than platform load.
- Check channel and route mix before interpreting hour-of-day movement as risk movement.
- Keep the `2026-03-22` merchant-day exception in mind only when strict merchant-day completeness is required.

## Appendix: visual evidence

### A1. Bucket grid contract

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/figures/01_bucket_grid_contract.png" alt="Bucket grid contract checks for arrival events" width="780">

### A2. Bucket intensity surface

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/figures/02_bucket_intensity_surface.png" alt="Bucket-level traffic intensity across UTC date and hour" width="780">

### A3. Hourly bucket profile and channel mix

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/figures/03_hourly_bucket_profile_and_channel_mix.png" alt="Hourly bucket profile and channel mix" width="780">

### A4. Channel and route hour shapes

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/figures/04_channel_route_hour_shapes.png" alt="Channel and route operating lanes by UTC hour" width="780">

### A5. Merchant exposure distribution and concentration

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/figures/05_merchant_exposure_distribution_and_concentration.png" alt="Merchant exposure distribution and cumulative row concentration" width="780">

### A6. Merchant-day exception context

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_grid_exposure_discipline/figures/06_merchant_day_exception_context.png" alt="Localized merchant-day exception context for 2026-03-22" width="780">
