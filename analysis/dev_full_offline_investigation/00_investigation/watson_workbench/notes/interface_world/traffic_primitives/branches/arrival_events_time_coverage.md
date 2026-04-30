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

This appendix holds the visual evidence behind the time-coverage branch. The figures are not included as decoration. Each figure tests a specific part of the coverage argument: whether the observed horizon is complete, whether month-level differences are calendar effects, whether daily volume is stable enough to serve as a denominator, and whether the surface carries real temporal structure rather than a flat synthetic spread.

The core distinction running through the appendix is this: **coverage** asks whether the operating period is continuously represented; **traffic shape** asks how arrival volume moves inside that period. A continuous surface does not have to be flat. In fact, if this is a plausible operating traffic surface, we should expect visible daily, weekly, and hourly rhythm. The question is whether those rhythms sit inside a complete and interpretable time frame.

### A1. Daily horizon coverage and boundary behaviour

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/01_horizon_daily_coverage.png" alt="Daily coverage across the January-March operating horizon" width="780">

This figure is the first coverage check because it asks the most basic question: does the surface actually contain every UTC date in the claimed operating window? The top strip answers that directly: `90 / 90` UTC dates are present from `2026-01-01` through `2026-03-31`. That is the first piece of evidence that this is a full-quarter context surface rather than a partial slice.

The lower panel then shows that the row counts live inside the same continuous date frame. The title records the timestamp boundary: the first row begins just after midnight on `2026-01-01`, and the last row lands just before midnight on `2026-03-31`. That boundary is important because a dataset can have rows in January, February, and March while still being incomplete at the edges. Here, the timestamps show that the surface opens and closes at the expected quarter boundary.

The daily line is intentionally not interpreted as a flatness test. Flatness is not the goal. A live fraud decisioning platform should have day-to-day movement because merchant activity, customer behaviour, channel use, and calendar effects vary. The statistical point is that the movement occurs inside an unbroken date sequence. There is no visible missing-date collapse where traffic drops to zero, no late start, and no early termination.

This is why the figure supports denominator trust at the date level. Later, when we compute traffic shares, fraud rates, case rates, or other daily/period rates, we need confidence that the denominator exists for the whole period. This figure does not prove that later labels or case products are complete. It proves that the arrival-context denominator itself spans the full date horizon.

### A2. Raw monthly totals versus calendar-normalized traffic

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/02_monthly_raw_vs_daily_normalized.png" alt="Raw monthly rows versus rows per active day" width="780">

This figure tests a common interpretation trap: reading raw month totals without accounting for month length. The left panel shows total rows by month. January has `81.68M` rows, February has `73.65M`, and March has `81.36M`. On raw totals alone, February appears materially lower.

The right panel changes the question from "how many rows are in the month?" to "how many rows are there per active day?" That denominator shift is the whole point of the figure. Once normalized by active days, the three months are very close: January is about `2.635M` rows per day, February about `2.630M`, and March about `2.625M`.

This means the apparent February dip is mostly calendar arithmetic. February has `28` days; January and March have `31`. A three-day difference at roughly `2.63M` rows per day accounts for most of the raw monthly gap. If February were genuinely missing operating coverage, the normalized daily bar would also be depressed. It is not.

This figure therefore supports the branch claim that month-level coverage behaves like a continuous daily process over months of different lengths. It also shows why denominator choice matters even in a time-coverage branch. Raw totals answer "how much traffic occurred in this calendar month"; normalized totals answer "what was the daily operating pace inside the month." The coverage interpretation needs the second view.

### A3. Daily volume stability across the horizon

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/03_daily_volume_stability.png" alt="Daily arrival volume stability" width="780">

This figure moves from calendar completeness to operating stability. It asks whether the complete date horizon is populated by plausible daily traffic volumes, or whether the full set of dates hides serious instability. The daily row count line stays around a central band near `2.63M` rows per day.

The mean and median are almost on top of each other at about `2.63M`. That is a meaningful stability signal. When the mean and median are close, the center of the distribution is not being dragged far away from the typical day by a few extreme observations. In this case, the daily surface has variation, but its center is coherent.

The shaded band marks the interquartile range, meaning the middle half of daily volumes. The line repeatedly moves above and below that band, which shows ordinary day-level traffic movement. The minimum day, `2026-01-25`, has about `2.47M` rows; the maximum day, `2026-01-30`, has about `2.89M` rows. These are real excursions, but they remain inside the same operating scale. They do not look like a missing-day failure, where volume would collapse toward zero, or a duplicated-day failure, where volume would jump to a different order of magnitude.

The figure therefore supports a precise reading: the surface is continuous and operationally stable, but not uniform. This is the correct posture for later analysis. We should trust the horizon as a denominator, but still preserve daily movement because that movement is part of the operating reality.

### A4. Distribution and range of daily traffic

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/04_daily_volume_distribution_and_range.png" alt="Daily volume distribution and range" width="780">

This figure reads daily traffic as a distribution rather than a chronological sequence. That matters because the time-series view can show when movement happens, while the distribution view shows the shape of the 90 daily totals as a population.

The histogram shows clustering around the daily center, and the boxplot compresses the same evidence into median, spread, whiskers, and high-side points. The mean and median are both around `2.63M`, repeating the stable-center signal from the previous figure. The distribution is not perfectly symmetric, and some high-volume days sit above the main body, but the spread does not suggest a broken extract.

The coefficient of variation is `3.15%`. This means the daily standard deviation is small relative to the mean daily volume. The point of this metric is not to hide the variation; it gives scale to the variation. A standard deviation of roughly `83K` rows sounds large in isolation, but against a daily base of roughly `2.63M` rows, it is modest.

The correct inference is that daily traffic has controlled variability. The surface is not mechanically flat, but neither is it unstable in a way that would undermine its use as a baseline denominator. This matters for later metrics because a stable denominator makes it easier to distinguish outcome movement from denominator failure.

### A5. Daily merchant and channel presence

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/05_daily_merchant_and_channel_presence.png" alt="Daily merchant and channel presence" width="780">

This figure asks whether daily coverage is only true at the row-count level, or whether the participant fields also remain stable. That is important because a surface could have rows every day while quietly losing a channel lane or a large part of the merchant population on some days.

The lower panel shows that both channel groups are present every day. This supports channel-level coverage: the daily horizon does not lose card-present or card-not-present visibility on any date in the period.

The merchant panel is almost flat at `4,050`, but it has one visible exception: `2026-03-22` has `4,049` active merchants. This is a small exception, but it is analytically important because it prevents us from overclaiming. Month-level participation says every month touches all `4,050` merchants. Day-level participation says almost every day touches all merchants, with one day short by one merchant.

The correct conclusion is therefore not "merchant participation is perfectly complete every day." The correct conclusion is "daily merchant participation is effectively complete, with one known one-merchant exception." That distinction matters if we later compute merchant-day completeness, merchant-level exposure, or any metric that assumes all merchants appear on every date.

### A6. Weekday operating shape

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/06_weekday_operating_shape.png" alt="Weekday operating shape in daily arrival volume" width="780">

This figure shows that the continuous horizon carries weekday structure. Friday has the strongest average daily volume, while Sunday has the weakest. The direction is operationally plausible: weekday traffic is generally stronger than weekend traffic, with Sunday at the bottom of the profile.

The vertical ranges are important because they show that weekday category is not the only source of movement. Each weekday still has day-to-day variation inside it. So the figure is not saying "weekday fully explains daily volume." It is saying that weekday is one visible component of the surface's time structure.

This matters for later rate interpretation. If fraud outcomes, bank outcomes, or case activity appear higher on certain weekdays, the first question should be whether the numerator changed, the denominator changed, or both. A Friday increase in cases has a different meaning if Friday also has higher arrival volume.

This figure therefore turns the time-coverage branch into a caution about temporal normalization. The denominator is continuous, but it is not neutral over the week. Later analysis should preserve weekday context instead of collapsing the entire quarter into one undifferentiated time block.

### A7. Hourly bucket-grid coverage and intensity

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/07_bucket_grid_coverage_and_intensity.png" alt="Hourly bucket grid coverage and arrival intensity" width="780">

This figure strengthens the coverage claim by moving below the day grain. A dataset can pass a daily coverage check while still having missing hours. The top panel tests that risk directly: all `2,160` expected hourly bucket indexes are present. Since the horizon is 90 days and `90 * 24 = 2,160`, this supports the claim that the `bucket_index` grid is complete at the hourly UTC level.

The lower panel then shows the number of arrivals inside each hourly bucket. This is a different question from coverage. Coverage asks whether the bucket exists. Intensity asks how much traffic falls into it. Both matter. A complete grid with empty or erratic traffic would raise different questions from a complete grid with a repeated operating rhythm.

The repeated peaks and troughs show that the hourly bucket field carries real temporal intensity. The pattern is not random visual noise; it repeats across the horizon, which is consistent with daily operating cycles. At this branch stage, we do not need to explain every peak. The claim is narrower: `bucket_index` is both complete as a grid and meaningful as a time-intensity coordinate.

This gives stronger confidence in using `bucket_index` for later time-window analysis, replay framing, and denominator alignment. It also exposes a follow-on branch: the repeated hourly rhythm deserves its own analysis rather than being treated as a background detail.

### A8. UTC-hour profile

<img src="../../../../exports/interface_world/traffic_primitives/branches/time_coverage/figures/08_utc_hour_profile.png" alt="UTC hour profile" width="780">

This figure collapses the full quarter into a 24-hour UTC profile. It answers a different question from the bucket-intensity line. The bucket line shows the sequence of hourly traffic across the whole horizon; this profile asks how traffic mass is distributed across the 24 UTC hours after aggregating the quarter.

If arrivals were uniformly distributed across UTC hours, each hour would hold about `1 / 24`, or `4.17%`, of rows. The figure does not show that. The early UTC hours around `03:00` to `05:00` are below `3%`, while the late-morning to late-afternoon band sits above `5%`, with the peak around `15:00` UTC.

That spread is a meaningful time-of-day structure. The difference between roughly `2.8%` and `5.4%` is not a small cosmetic fluctuation around uniformity; the strongest hours carry nearly twice the share of the weakest hours. That matters if later rates are compared by hour, because the denominator itself is not evenly distributed through the day.

This figure does not yet settle local operating rhythm because UTC is only one frame of time. The surface also carries primary, settlement, and operational local timestamp fields. The correct conclusion is therefore not "the business day peaks at 15:00 everywhere." The correct conclusion is that UTC time-of-day structure is present, and a later local-time branch is necessary before making stronger operational claims about local business rhythms.
