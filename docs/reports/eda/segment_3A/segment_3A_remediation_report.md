# Segment 3A Remediation Report

Date: 2026-02-07
Scope: Statistical remediation planning for segment 3A toward target grade `B/B+`.
Status: Planning only. No fixes implemented in this document.

---

## 1) Observed Weakness
This section records the measured weaknesses from `segment_3A_published_report.md` that block a `B/B+` realism claim for Segment 3A.

### 1.1 Critical realism failure: priors are structurally over-concentrated (`S2`)
The largest weakness starts in `s2_country_zone_priors`:
1. Country top-1 prior share is extreme:
   - `82.3%` of countries have top-1 share `>= 0.95`
   - `66.1%` have top-1 share `>= 0.99`
   - `28.6%` are exactly `1.0`
2. Multi-timezone countries are still often effectively monolithic:
   - `93 / 177` countries with `tz_count > 1` still have top-1 share `>= 0.99`
3. Country concentration is near-degenerate:
   - median HHI `= 0.990` (p75 `= 1.0`)

Why this is a blocker:
1. Segment 3A cannot generate realistic multi-zone behavior if the prior layer is already close to single-zone for most countries.
2. Downstream sampling and integerization can only transform what the priors allow; concentrated priors severely cap realism headroom.

### 1.2 High-severity coherence failure: escalation intent does not translate to multi-zone outcomes
Escalation behavior and realized allocation behavior are misaligned:
1. Escalation is high:
   - `1,621 / 2,597 = 62.4%` escalated
2. Realized multi-zone outcomes are low:
   - only `13.3%` of escalated pairs end with more than one nonzero zone
   - `86.7%` of escalated pairs still end with exactly one nonzero zone

Why this is high severity:
1. The policy intent says "split across zones" for most escalated pairs, but observed outcomes remain mostly monolithic.
2. This creates an explainability and realism gap: the pipeline escalates in form but not in behavioral effect.

### 1.3 High-severity sampling weakness: `S3` mostly reproduces priors with minimal merchant diversity
The share-sampling layer provides little additional heterogeneity:
1. Prior-to-sample coupling is almost perfect:
   - correlation(mean sampled share vs prior share) `= 0.998`
   - mean absolute difference `= 0.0052`
2. Within-country merchant dispersion is very low:
   - std of `share_drawn` across merchants (country/tzid groups) median `= 0.003`

Why this matters:
1. Merchant-level variation is a core requirement for synthetic realism.
2. When sampled shares almost mirror priors for all merchants, allocations become repetitive and behaviorally flat.

### 1.4 High-severity integerization collapse: `S4` zero-inflates and amplifies dominance
Integerization finalizes the concentration:
1. `87%` of `S4` rows have `zone_site_count = 0`
2. Top-1 count share is near-total:
   - median `= 1.0`
   - p25 `= 1.0`
   - p10 `= 0.94`

Why this matters:
1. Any residual diversity in `S3` is mostly removed during count conversion.
2. The operational output used downstream becomes effectively single-zone in most merchant-country pairs.

### 1.5 High-severity final-output weakness: `zone_alloc` is behaviorally monolithic
Final egress confirms collapse:
1. `zone_alloc` top-1 share median `= 1.0`
2. Lower quantiles remain highly concentrated:
   - p25 `= 1.0`
   - p10 `= 0.94`

Why this is decisive:
1. `zone_alloc` is the realism surface consumed downstream.
2. If this output is mostly monolithic, Segment 3A misses its core mission even if structural checks pass.

### 1.6 Medium-high escalation policy-shape weakness: forced and non-monotonic gate behavior
`S1` gate behavior appears threshold-heavy rather than smooth:
1. Decision reasons are dominated by forced pathways:
   - `forced_escalation = 1,530` (largest reason bucket)
2. Escalation rate by `zone_count_country` is non-monotonic (for example very high at some counts, then dip at others)

Why this matters:
1. It suggests brittle policy edges rather than natural geographic response.
2. Non-monotonic threshold behavior complicates downstream interpretability and controlled tuning.

### 1.7 Medium shaping weakness: floor/bump activity is not the main corrective mechanism
Floor/bump is active but does not materially reshape concentration:
1. `floor_applied_rate = 22.97%`
2. `bump_applied_rate = 22.97%`
3. Diagnostics indicate effective shares remain close to raw shares in most cases

Why this matters:
1. The dominant issue is base prior geometry, not absence of floor operations.
2. Remediation focused only on floor tuning is unlikely to deliver B-grade realism.

### 1.8 Segment-level weakness summary
1. Segment 3A is structurally correct and reproducible.
2. Behavioral realism is weak due to concentrated priors, low sampling dispersion, and integerization collapse.
3. Net effect: multi-zone exists in schema, but monolithic allocation dominates in practice.

## 2) Expected Statistical Posture (B/B+)
This section defines the target statistical posture for Segment 3A once remediation is applied.  
Goal: reach robust synthetic realism without requiring real‑world ground truth.

### 2.1 Non‑negotiable `B` gates (hard fail)
If any gate below fails, Segment 3A cannot be graded `B` regardless of other improvements.

1. **Priors must be meaningfully multi‑zone in multi‑TZ countries.**
   - Among countries with `tz_count > 1`:
     - median `top1_share <= 0.85`
     - share of countries with `top1_share >= 0.99` must be `<= 20%`

2. **Escalation must translate into multi‑zone outcomes.**
   - Escalated pairs with `>1` nonzero zone must be `>= 35%`
   - Escalated pairs with `>=2` zones above `5%` share must be `>= 20%`

3. **Sampling must introduce merchant heterogeneity.**
   - Median within‑country `std(share_drawn)` across merchants `>= 0.02`

4. **Integerization must preserve diversity.**
   - Median `top1_share` after counts (S4) `<= 0.90`
   - p75 `top1_share` after counts `<= 0.97`

5. **Final `zone_alloc` must be non‑monolithic.**
   - Same thresholds as S4 because `zone_alloc` mirrors S4 counts.

### 2.2 `B` vs `B+` expected posture by axis
| Axis | `B` target | `B+` target |
|---|---|---|
| S2 top‑1 share (multi‑TZ countries) | median `<=0.85`, p75 `<=0.93` | median `<=0.75`, p75 `<=0.88` |
| Countries with top‑1 share `>=0.99` | `<=20%` | `<=10%` |
| Merchant heterogeneity (median std of share_drawn) | `>=0.02` | `>=0.04` |
| Effective multi‑zone rate (escalated pairs) | `>=35%` | `>=55%` |
| Zones above 5% share (escalated) | p50 `>=2` | p50 `>=3` |
| S4 top‑1 share median | `<=0.90` | `<=0.85` |
| S4 top‑1 share p75 | `<=0.97` | `<=0.93` |
| `zone_alloc` top‑1 share median | `<=0.90` | `<=0.85` |
| Escalation monotonicity vs `tz_count` | mostly increasing, no major dips | smooth monotonic trend |

### 2.3 Cross‑seed stability requirements
Required seeds: `{42, 7, 101, 202}`.

1. All hard‑gate metrics pass on all seeds.
2. Cross‑seed CV for primary medians (`S2 top1`, `S3 std`, `S4 top1`, multi‑zone rate):
   - `<=0.25` for `B`
   - `<=0.15` for `B+`
3. Escalation rate must remain within its policy band on all seeds (no seed‑driven regime flips).

### 2.4 Interpretation of the target posture
For Segment 3A, `B/B+` means:
1. Priors allow more than one tzid to matter in multi‑TZ countries.
2. Sampling introduces merchant‑level variability, not just country‑level determinism.
3. Integerization preserves diversity instead of collapsing it.
4. Escalation is reflected in actual multi‑zone outputs.

## 3) Root-Cause Trace

## 4) Remediation Options (Ranked + Tradeoffs)

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)

## 6) Validation Tests + Thresholds

## 7) Expected Grade Lift (Local + Downstream Impact)
