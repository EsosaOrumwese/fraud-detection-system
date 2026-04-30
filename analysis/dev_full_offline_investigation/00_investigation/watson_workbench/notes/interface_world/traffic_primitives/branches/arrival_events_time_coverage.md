# Branch Investigation: `arrival_events_5B` Time Coverage

## Branch question

The main `arrival_events_5B` report says the surface spans the full January-March operating window and looks like a complete extract rather than an obviously gapped period.

This branch unpacks that claim.

The question is:

> Does `arrival_events_5B` give us a continuous three-month operating context surface, and what does that continuity allow us to trust or not trust in later analysis?

## Evidence used

Primary report:

- [`arrival_events_5B_investigation.md`](../arrival_events_5B_investigation.md)

Workbench exports:

- [`arrival_events_identity_summary.csv`](../../../../exports/interface_world/traffic_primitives/arrival_events_identity_summary.csv)
- [`arrival_events_month_summary.csv`](../../../../exports/interface_world/traffic_primitives/arrival_events_month_summary.csv)
- [`arrival_events_daily_summary.csv`](../../../../exports/interface_world/traffic_primitives/arrival_events_daily_summary.csv)
- [`arrival_events_daily_stats.csv`](../../../../exports/interface_world/traffic_primitives/arrival_events_daily_stats.csv)
- [`arrival_events_utc_hour_summary.csv`](../../../../exports/interface_world/traffic_primitives/arrival_events_utc_hour_summary.csv)
- [`bucket_index_summary.csv`](../../../../exports/interface_world/traffic_primitives/branches/grain_and_identity/bucket_index_summary.csv)

## What time coverage means here

Time coverage is not the same thing as traffic uniformity.

For this surface, time coverage means the arrival-context ledger spans the expected operating horizon without an obvious missing month, missing day sequence, or broken bucket grid. It asks whether the data gives us a continuous observation window that can support later traffic, label, and case-rate analysis.

It does not mean every hour has the same number of arrivals. It does not mean every merchant contributes equally every day. It also does not mean fraud, bank action, or case outcomes are covered here; those questions belong to later truth and case surfaces.

## Horizon boundary

The observed UTC boundary is:

- first timestamp: `2026-01-01T00:00:00.001940Z`
- last timestamp: `2026-03-31T23:59:59.944516Z`
- active UTC dates: `90`

That is the full January-March operating window. The surface starts immediately after midnight on January 1 and ends just before midnight on March 31. At this level, there is no evidence that the extract begins late, ends early, or omits a major part of the quarter.

This matters because many later metrics will use this surface as the timing/routing context for behavioural traffic. If the context surface had a partial horizon, later rate denominators could become misleading. Here, the horizon boundary supports treating the primitive as a full three-month operating context baseline.

## Calendar-month coverage

Monthly totals are:

| Month | Rows | Active merchants | Active days | Rows per active day |
|---|---:|---:|---:|---:|
| `2026-01` | `81,678,596` | `4,050` | `31` | `2,634,793` |
| `2026-02` | `73,652,566` | `4,050` | `28` | `2,630,449` |
| `2026-03` | `81,360,532` | `4,050` | `31` | `2,624,533` |

The raw monthly totals show February lower than January and March. That raw difference is mostly calendar length, not an obvious February traffic collapse. Once normalized by active days, the monthly daily averages are close:

- January: about `2.635M` rows per active day
- February: about `2.630M` rows per active day
- March: about `2.625M` rows per active day

This is the first reason the surface reads like a complete operating extract. The month totals behave as we would expect from a continuous daily process over months of different lengths.

The active-merchant count is also stable at month level. Each month touches all `4,050` merchants at least once. That does not mean every merchant is active every day, but it does mean no month loses a major merchant population.

## Daily coverage and stability

The daily summary contains `90` rows, one for each UTC date from `2026-01-01` through `2026-03-31`.

Daily row statistics:

| Metric | Value |
|---|---:|
| Minimum daily rows | `2,472,304` |
| p25 daily rows | `2,578,974` |
| Mean daily rows | `2,629,908` |
| Median daily rows | `2,626,903` |
| p75 daily rows | `2,656,527` |
| Maximum daily rows | `2,887,820` |
| Daily standard deviation | `82,932` |

The mean and median are close, which tells us the daily volume center is stable. The daily standard deviation is about `3.15%` of the mean, so the day-to-day variation is visible but not large relative to the daily traffic base.

The minimum daily volume occurs on `2026-01-25` with `2,472,304` rows. The maximum occurs on `2026-01-30` with `2,887,820` rows. Relative to the mean, the minimum is about `94.0%` of average daily volume and the maximum is about `109.8%` of average daily volume.

That range supports the continuity claim. The surface is not perfectly flat, and it should not be expected to be flat, but the daily totals do not show an obvious missing-day collapse or runaway duplicate-day explosion.

## Daily merchant and channel presence

The daily summary shows both channels present every day.

Merchant presence is nearly complete every day:

- `89` days have `4,050` active merchants
- `1` day has `4,049` active merchants: `2026-03-22`

This is an important nuance. The main report's month-level statement that every month has `4,050` active merchants is true, but the daily view shows one day where one merchant does not appear. That is not evidence of a coverage defect by itself. It is a normal distinction between month-level participation and day-level participation.

The practical reading is that the surface has full calendar-day coverage and nearly complete daily merchant participation. We should not phrase it as "every merchant appears every day" unless that one-day exception is handled.

## Weekday shape

A simple weekday aggregation shows a mild operating-week pattern:

| Weekday | Days | Rows | Mean rows per day |
|---|---:|---:|---:|
| Monday | `13` | `34,105,596` | `2,623,507` |
| Tuesday | `13` | `34,150,828` | `2,626,987` |
| Wednesday | `12` | `31,935,013` | `2,661,251` |
| Thursday | `13` | `34,785,982` | `2,675,845` |
| Friday | `13` | `35,448,430` | `2,726,802` |
| Saturday | `13` | `33,497,724` | `2,576,748` |
| Sunday | `13` | `32,768,121` | `2,520,625` |

Friday is the strongest average day, and Sunday is the weakest. This does not change the coverage conclusion, but it does tell us the surface is not temporally featureless. The arrival process carries a weekly rhythm.

That rhythm is useful for later analysis because fraud rates, case rates, and review workload should not be interpreted against a flat-time assumption. If later surfaces show outcome changes by day, we need to distinguish true outcome movement from ordinary traffic rhythm.

## Bucket-grid coverage

The observed `bucket_index` range is:

- minimum: `0`
- maximum: `2,159`
- distinct bucket indexes: `2,160`

The branch-level bucket summary confirms all expected bucket indexes are present. Since `90 * 24 = 2,160`, this supports the reading that the run behaves as an hourly UTC grid over the 90-day horizon.

This gives us stronger evidence than date coverage alone. A dataset could have all dates present but still have missing hourly sections. Here, the bucket grid supports continuous hourly horizon coverage at the primitive's declared time-grid level.

That does not mean every bucket has the same row count. It means every bucket exists and carries arrivals.

## UTC-hour profile as a coverage sanity check

The UTC-hour summary is not the main time-coverage evidence, but it helps confirm that the surface carries operating-time structure.

The lowest row shares occur around early UTC hours:

- `03:00`: `2.81%`
- `04:00`: `2.77%`
- `05:00`: `2.92%`

The strongest row shares occur during the late-morning to late-afternoon UTC band:

- `14:00`: `5.32%`
- `15:00`: `5.40%`
- `16:00`: `5.36%`
- `17:00`: `5.29%`

This pattern is consistent with an operating traffic surface rather than a uniformly sprayed timestamp field. The field carries time-of-day shape, which will matter when we later compare UTC time with operational local time.

## What this coverage lets us trust

The time coverage supports these uses:

- treating January-March as a continuous operating context horizon
- computing daily and monthly arrival-volume baselines
- joining later behavioural, truth, and case surfaces back to a stable context period
- using `bucket_index` for hourly time-grid analysis
- comparing later outcome rates against a continuous traffic denominator

The main value is denominator trust. If later analysis says "fraud rate per day," "case rate per month," or "traffic share by hour," this surface gives us a continuous arrival-context denominator for the same operating period.

## What this coverage does not prove

The coverage does not prove:

- that fraud labels are complete across the same horizon
- that case timelines finish inside January-March
- that every merchant appears every day
- that local-time interpretation is already solved
- that daily traffic should be treated as uniform
- that `arrival_events_5B` is the canonical scored transaction stream

The last point matters. This is a time-safe arrival-context surface. It gives timing and routing context behind the platform's traffic, but it is not by itself the behavioural transaction stream, the truth surface, or the case surface.

## Working interpretation

`arrival_events_5B` has complete time coverage for the January-March operating horizon at the date and hourly bucket levels.

The month totals align with calendar length, the daily totals remain within a relatively stable operating band, both channels appear every day, and the bucket grid covers all `2,160` expected hourly slots. There is one small daily merchant-participation exception on `2026-03-22`, where `4,049` merchants appear instead of `4,050`, but that does not undermine the broader coverage claim.

The correct conclusion is not "traffic is uniform." The correct conclusion is that the arrival-context surface is continuous enough to serve as a three-month operating denominator for later traffic, label, and case-rate interpretation.

## Leads exposed

1. `bucket_index` deserves a deeper time-grid branch: hourly coverage is complete, but the repeated traffic rhythm needs its own analysis.

2. UTC time should later be compared with local operating time, because the surface carries primary, settlement, and operational local timestamp fields.

3. The one-day `4,049` merchant participation exception on `2026-03-22` should be kept in mind if a later analysis requires strict merchant-by-day completeness.

4. When truth products and case timelines are inspected, we should verify whether their effective time coverage aligns with this arrival-context denominator or extends beyond it.

## Appendix: visual evidence and assessment

This appendix holds the visual evidence behind the time-coverage branch. The figures are not included as decoration. Each one tests a specific part of the coverage argument: whether the horizon is complete, whether month-level differences are calendar effects, whether daily volume is stable enough to serve as a denominator, and whether the surface carries real temporal structure rather than a flat synthetic spread.

### A1. Daily horizon coverage and boundary behaviour

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/01_horizon_daily_coverage.png" alt="Daily coverage across the January-March operating horizon" width="780">

This figure is the first coverage check because it answers the simplest question: do we actually have the full January-March date horizon? The top strip shows `90 / 90` UTC dates present. That means there is no missing calendar day between `2026-01-01` and `2026-03-31`.

The lower panel then places the daily row counts inside that same continuous window. The title records the timestamp boundary: the first row begins just after midnight on `2026-01-01`, and the last row lands just before midnight on `2026-03-31`. That boundary matters because it rules out a common extract problem: a file that claims to represent a quarter but actually starts late, ends early, or omits part of the edge days.

The daily line is not flat, and it should not be read as though flatness is the goal. A live operating platform should have day-to-day movement. The relevant statistical point is that the movement occurs inside a complete date sequence. The surface therefore gives us a continuous arrival-context denominator for the three-month operating window, while still preserving ordinary daily traffic variation.

### A2. Raw monthly totals versus calendar-normalized traffic

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/02_monthly_raw_vs_daily_normalized.png" alt="Raw monthly rows versus rows per active day" width="780">

This figure tests whether the lower February total should be treated as a coverage concern. The left panel shows raw monthly rows: January and March sit around `81M`, while February sits around `73.65M`. If we stopped there, February might look like a weaker or partially missing month.

The right panel changes the denominator from month to active day. Once the rows are divided by the number of active days, the three months are close: January is about `2.635M` rows per day, February about `2.630M`, and March about `2.625M`. The apparent monthly drop is therefore mostly explained by February having `28` active days rather than `31`.

This distinction is important because raw period totals can mislead when period lengths differ. The evidence here supports the branch conclusion that the monthly pattern behaves like a continuous daily process over months of different lengths, not like an obvious February data-loss event.

### A3. Daily volume stability across the horizon

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/03_daily_volume_stability.png" alt="Daily arrival volume stability" width="780">

This view asks whether the complete date horizon is also operationally stable. The mean and median daily volumes sit almost on top of each other at about `2.63M` rows. That matters because a large separation between mean and median would suggest that a small number of unusual days is pulling the center away from the typical day. Here, the center is stable.

The shaded band marks the interquartile range, the middle half of daily volumes. The daily line moves above and below that band, but it does so without producing a day that looks like a missing-data collapse. The minimum day, `2026-01-25`, has about `2.47M` rows. The maximum day, `2026-01-30`, has about `2.89M` rows. Relative to the daily base, those are real excursions but not structural breaks.

The statistical reading is continuity with variation. This figure supports the branch's wording that time coverage is not the same thing as uniform traffic. The surface can be continuous and still show peaks, troughs, and weekly rhythm. That is exactly what we should expect from an operating traffic context surface.

### A4. Distribution and range of daily traffic

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/04_daily_volume_distribution_and_range.png" alt="Daily volume distribution and range" width="780">

This figure reads the same daily-volume evidence as a distribution rather than as a sequence. The histogram shows how the 90 daily totals cluster, and the boxplot gives a compact range check. The mean and median both sit around `2.63M`, confirming the same stable-center observation from the time-series view.

The coefficient of variation is `3.15%`. In plain statistical terms, the daily standard deviation is small relative to the mean daily traffic base. That does not mean every day is identical. It means the surface varies inside a comparatively narrow operating band when measured against a base of roughly `2.63M` rows per day.

The upper-side points in the boxplot are useful because they show that some high-volume days exist. The correct conclusion is not that the daily distribution is perfectly smooth or symmetric. The correct conclusion is that the spread is modest enough to support denominator trust: daily traffic moves, but it does not behave like a broken or intermittently missing extract.

### A5. Daily merchant and channel presence

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/05_daily_merchant_and_channel_presence.png" alt="Daily merchant and channel presence" width="780">

This figure checks whether daily coverage is only a row-count claim or whether the main participant fields also remain present. The channel panel is straightforward: both channel groups are present every day, so the daily horizon does not lose an entire channel lane.

The merchant panel adds an important nuance. Most days have all `4,050` merchants active, but `2026-03-22` has `4,049`. That single-day exception is small, but it matters for wording. At month level, every month touches all `4,050` merchants. At day level, one day is short by one merchant.

This is why the branch should say "nearly complete daily merchant participation" rather than "every merchant appears every day." The exception does not undermine the overall time-coverage claim, because the date, channel, and row-volume evidence remain continuous. It does, however, matter if a later analysis requires strict merchant-by-day completeness.

### A6. Weekday operating shape

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/06_weekday_operating_shape.png" alt="Weekday operating shape in daily arrival volume" width="780">

This figure shows that the arrival surface has an operating-week rhythm. Friday has the strongest average daily volume, while Sunday has the weakest. The vertical ranges show that each weekday also has its own day-to-day spread, so the weekday pattern is not the only source of daily movement.

The point is not that weekday alone explains the time series. The point is that time is already meaningful inside the traffic primitive. A flat-time assumption would ignore this structure and could distort later comparisons. For example, a future case-rate or fraud-rate view that rises on a Friday should be compared against the fact that Friday also carries higher arrival volume.

This figure therefore converts "coverage" into an analytical warning. A continuous denominator is valuable, but it is not neutral over time. The traffic denominator has weekly shape, and later outcome analysis should preserve that time context rather than collapsing the whole quarter into one undifferentiated block.

### A7. Hourly bucket-grid coverage and intensity

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/07_bucket_grid_coverage_and_intensity.png" alt="Hourly bucket grid coverage and arrival intensity" width="780">

This figure is stronger than a date-level coverage check because it tests the canonical hourly grid. The top panel confirms that all `2,160` expected bucket indexes are present. Since the horizon is 90 days and `90 * 24 = 2,160`, this supports the claim that `bucket_index` is complete at the hourly UTC-grid level.

The lower panel then shows row intensity inside each hourly bucket. The repeated peaks and troughs are not a defect; they show that the hourly grid carries operating rhythm. This is the difference between structural coverage and traffic intensity. Coverage asks whether the bucket exists. Intensity asks how much traffic is inside it. Both are visible here.

This matters for later analysis because a dataset could pass a date-level check and still have missing hourly sections. This surface does not show that problem. The hourly grid is present across the full horizon, which gives us stronger confidence in using `bucket_index` for time-window analysis, replay framing, and later rate denominators.

### A8. UTC-hour profile

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/08_utc_hour_profile.png" alt="UTC hour profile" width="780">

This figure collapses the full quarter into a 24-hour UTC profile. The early UTC hours around `03:00` to `05:00` have the lowest shares, while the late-morning to late-afternoon band carries the strongest shares. The peak sits around `15:00` UTC.

The statistical point is that timestamp mass is not uniformly distributed across the day. If the surface were time-flat, each hour would sit close to `1 / 24`, or about `4.17%`, of rows. Instead, the profile ranges from under `3%` in the lowest hours to above `5%` in the strongest hours. That is a meaningful time-of-day shape.

This figure does not yet settle local operating rhythm because UTC is only one time frame. The surface also carries primary, settlement, and operational local timestamp fields, so a later branch should compare UTC activity to local operating time. What this figure proves at this stage is narrower but important: time-of-day structure exists, and later traffic, label, and case-rate analysis should not ignore it.
