# Population Pathway Operating Note v1

Purpose:
- interpret the bounded pathway outputs as an operating problem rather than just a descriptive segmentation pack

Bounded population reading:
- test population size: `691,122` flows
- case-selected suspicious-pathway subset: `73,644` flows (`10.66%`)
- authoritative fraud-truth rate across the full test population: `2.73%`

Main operating pattern:
- the overall population is dominated by `no_case` flows, but the real operating burden sits inside the case-selected subset
- within the case-selected subset, low-yield cohorts dominate volume:
  - `high_burden_low_yield`: `29,675` flows
  - `low_burden_low_yield`: `29,601` flows
- together, those two low-yield cohorts account for `80.4%` of case-selected test flows

Most important pressure point:
- `high_burden_low_yield` is the main operating burden cohort
- it carries `29,675` test flows with `0%` fraud-truth yield and average lifecycle of `771.6` hours
- this suggests a large amount of long-running case work with weak authoritative downstream value

Important counterweight:
- `slow_converting_high_yield` is much smaller (`7,156` flows) but has `100%` fraud-truth yield and very long average lifecycle (`1,858.9` hours)
- this indicates a separate high-value but slow-moving cohort that may merit targeted acceleration rather than volume reduction

Operational implication:
- the pathway appears bifurcated
- one large low-yield burden segment consumes substantial case duration
- one smaller high-yield segment carries strong value but slow resolution

First intervention question:
- should operational effort focus first on reducing burden in the long-running low-yield cohort, or on accelerating the smaller but high-value slow-converting cohort?

Bounded recommendation:
- prioritise investigation of why `high_burden_low_yield` remains long-running despite zero fraud-truth yield
- separately review whether `slow_converting_high_yield` can be shortened without sacrificing outcome quality
