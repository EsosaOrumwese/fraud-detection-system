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
This section traces each observed weakness to concrete policy, code-path, and data-flow causes.  
Goal: establish causal accountability before proposing fixes.

### 3.1 Root-cause mapping matrix
| Weakness (Section 1) | Immediate cause | Deeper cause | Primary evidence | Statistical effect |
|---|---|---|---|---|
| 1.1 Over‑concentrated priors (S2) | Country‑zone alpha packs are dominated by one tzid | Prior construction uses heavy dominance assumptions without balancing tail | `s2_country_zone_priors` metrics in `segment_3A_published_report.md` | `top1_share` near 1.0 for most countries |
| 1.2 Escalation intent mismatch | S1 escalates many pairs, but S2/S3/S4 collapse to single zone | Escalation policy is aggressive while priors remain highly concentrated | S1 escalation stats + S2/S3/S4 distributions | Escalation does not produce multi‑zone outcomes |
| 1.3 Sampling lacks heterogeneity | S3 draws closely mirror priors | Dirichlet alpha mass too concentrated; no merchant‑level random effects | S3 vs S2 correlation `0.998`, low std of shares | Merchants inside a country behave nearly identically |
| 1.4 Integerization collapse | S4 rounding pushes small shares to zero | Share mass too concentrated before integerization; floor rules do not rescue tails | S4 zero inflation and top1 share metrics | Final counts are monolithic |
| 1.5 Final output monolithic | `zone_alloc` mirrors S4 counts | No diversity is introduced after S4 | `zone_alloc` top‑1 share metrics | Output realism collapses |
| 1.6 Forced / non‑monotonic escalation | S1 thresholds interact in brittle ways | Escalation rules are hard thresholds rather than smooth geography response | S1 decision reasons and non‑monotonic escalation curve | Gate behavior looks synthetic |
| 1.7 Floor/bump not corrective | Floors apply but do not reshape priors | Base prior geometry is already too dominant | S2 alpha ratio diagnostics | Floors do not create diversity |

### 3.2 Detailed trace: S2 prior construction is the primary bottleneck
1. The alpha pack produces highly dominant priors for most countries.
2. Even multi‑TZ countries are effectively single‑TZ in the prior.
3. S3 sampling cannot diversify because the probability mass is already concentrated.
4. S4 integerization then has no chance to preserve multi‑zone allocation.

Interpretation:
1. The priors are the primary realism choke‑point.
2. Fixing S4 alone will not help if S2 remains degenerate.

### 3.3 Detailed trace: S1 escalation is out of balance with S2 priors
1. S1 escalates ~62% of merchant‑country pairs.
2. S2 priors then collapse most of those escalations into a single dominant zone.
3. This creates a policy contradiction: escalation is triggered, but outcomes remain monolithic.

Interpretation:
1. Either escalation thresholds must be reshaped,
2. Or priors must be loosened so escalation produces multi‑zone behavior.

### 3.4 Detailed trace: S3 sampling is not introducing merchant variability
1. `mean(sample share)` aligns almost perfectly with `S2 share_effective`.
2. Merchant‑level standard deviation is extremely low.

Interpretation:
1. S3 is an echo of S2, not a heterogeneity generator.
2. Merchant‑level random effects or dispersion controls are missing.

### 3.5 Detailed trace: integerization amplifies collapse rather than rescuing diversity
1. Small shares are rounded to zero, yielding 87% zero rows.
2. Top‑1 count share becomes exactly 1.0 for most pairs.

Interpretation:
1. S4 is not the initial cause, but it finalizes the collapse.
2. Any downstream realism claim must therefore fix S2/S3 first.

### 3.6 Detailed trace: escalation rule shape is brittle
1. Escalation rate is non‑monotonic with respect to `tz_count`.
2. `forced_escalation` dominates decision reasons.

Interpretation:
1. The policy reads as threshold‑driven rather than smooth geographic response.
2. This behavior is explainable but does not look realistic.

### 3.7 Root‑cause conclusion
Segment 3A realism failures are caused by:
1. Over‑dominant priors in S2 (primary bottleneck).
2. Escalation policy that is aggressive but not supported by those priors.
3. S3 sampling that does not introduce merchant‑level diversity.
4. S4 integerization that amplifies collapse.
5. Floor/bump mechanics that do not materially reshape priors.

This causal map is sufficient to move into ranked remediation options in Section 4.

## 4) Remediation Options (Ranked + Tradeoffs)
This section presents ranked remediation options derived from Section 3 causal evidence.  
Ranking is based on expected realism lift per unit implementation effort, while preserving deterministic reproducibility and auditability.

### 4.1 Ranked options matrix
| Rank | Option | What it changes | Weaknesses addressed | Expected realism lift | Tradeoffs / risks |
|---|---|---|---|---|---|
| 1 | Rebuild S2 priors with mixed‑dominance structure | Replace single‑mode dominant priors with mixture of hub + regional tails | 1.1, 1.2, 1.3 | Very high | Requires careful tuning to avoid over‑diffuse priors |
| 2 | Add merchant‑level dispersion in S3 | Add merchant‑specific random effects / dispersion controls in share draws | 1.3 | High | Risk of instability if dispersion too large |
| 3 | Rebalance S1 escalation thresholds | Smooth escalation rules to reduce brittle non‑monotonicity | 1.2, 1.6 | Medium‑high | Must preserve intended escalation rates |
| 4 | Integerization safeguards in S4 | Add minimum second‑zone floor or stochastic rounding | 1.4 | Medium | Risk of inflating multi‑zone for tiny outlet counts |
| 5 | Realism contract expansion (S6/S7) | Add blocking checks for priors, multi‑zone rate, top‑1 share, heterogeneity | 1.7 and prevents regression | High (governance) | More initial gate failures while tuning |
| 6 | Upstream geo diversity assist (2A/2B) | Widen spatial diversity feeding S1/S2 | 1.2 (partial) | Medium (enabling) | Cross‑segment coordination overhead |

### 4.2 Option detail and rationale
#### 4.2.1 Option 1: Mixed‑dominance S2 priors (top priority)
1. Replace single dominant prior with a two‑component mixture:
   - dominant hub component (keeps realism for primary zone),
   - regional tail component (keeps multi‑zone plausibility).
2. Use policy parameters to control:
   - hub share mean,
   - tail mass,
   - dispersion within tail.

Why this is rank 1:
1. S2 priors are the primary bottleneck.
2. Fixing them unlocks every downstream stage.

Risk:
1. If tail mass is too high, priors become unrealistically flat.

#### 4.2.2 Option 2: Merchant‑level dispersion in S3
1. Add merchant‑level random effects to share draws:
   - per‑merchant alpha scaling,
   - bounded dispersion around country priors.
2. Ensure reproducibility via hash‑seeded draws.

Why this is rank 2:
1. Directly creates merchant heterogeneity that is currently missing.

Risk:
1. Too much dispersion can create unstable or implausible profiles.

#### 4.2.3 Option 3: Rebalance S1 escalation thresholds
1. Convert brittle threshold logic into smooth escalation probability bands.
2. Ensure escalation is monotonic in `tz_count` and responsive to `site_count`.

Why this is rank 3:
1. Escalation is high but not matched by outcomes.
2. Tuning it reduces policy contradiction and improves interpretability.

Risk:
1. Too lenient thresholds reduce multi‑zone representation; too strict thresholds inflate it.

#### 4.2.4 Option 4: Integerization safeguards in S4
1. Apply a minimum second‑zone floor for escalated pairs above a site threshold.
2. Use stochastic rounding on near‑threshold zones so diversity survives.

Why this is rank 4:
1. Even with better priors, integerization can still collapse diversity.

Risk:
1. Artificially inflating multi‑zone outcomes in very small outlet counts.

#### 4.2.5 Option 5: Realism contract expansion (S6/S7)
1. Add blocking checks for:
   - S2 top‑1 share ceilings,
   - S3 dispersion floors,
   - S4 multi‑zone rate floors,
   - S4 top‑1 share ceilings.
2. Add cross‑seed stability checks.

Why this is rank 5:
1. Prevents regression; makes realism non‑optional.

Risk:
1. More tuning cycles due to stricter gating.

#### 4.2.6 Option 6: Upstream geo diversity assist (2A/2B)
1. Increase upstream diversity only if 3A improvements still hit a ceiling.
2. Treat as enabling, not core fix.

Why this is rank 6:
1. Helpful, but 3A’s primary failures are local.

### 4.3 Recommended option stack for 3A
#### 4.3.1 Core stack (required for `B`)
1. Option 1 (S2 priors mix).
2. Option 2 (S3 dispersion).
3. Option 5 (realism checks).

#### 4.3.2 Enhancement stack (targeting `B+`)
1. Option 3 (escalation smoothing).
2. Option 4 (integerization safeguards).
3. Option 6 (upstream assist) only if needed after core+B+ tuning.

### 4.4 Why this ranking is statistically coherent
1. S2 priors are the dominant causal bottleneck and must be fixed first.
2. S3 dispersion is the next-order heterogeneity generator.
3. S4 safeguards prevent collapse once priors and dispersion are improved.
4. Governance checks make the gains stable and auditable.

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)
This section selects the concrete remediation package for 3A and defines exact policy/code delta points to execute in a subsequent remediation wave.

### 5.1 Chosen package for 3A
Chosen package for baseline remediation (`B` target):
1. `CF-3A-01` Mixed‑dominance S2 priors (hub + regional tail).
2. `CF-3A-02` Merchant‑level dispersion in S3.
3. `CF-3A-03` Realism contract expansion (S6/S7).

Conditional add‑ons:
1. `CF-3A-04` Escalation smoothing (if escalation curve remains non‑monotonic or too forced).
2. `CF-3A-05` Integerization safeguards (if multi‑zone rate remains below target after priors/dispersion).

### 5.2 Exact policy deltas
#### 5.2.1 File: `config/layer1/3A/zone_mixture_policy.yaml`
Add explicit monotonic smoothing controls:
```yaml
escalation_policy:
  mode: "smooth_band"
  tz_count_monotonic: true
  tz_count_min_escalation:
    1: 0.00
    2: 0.20
    3: 0.35
    4: 0.45
    6: 0.60
    8: 0.75
    11: 0.90
  site_count_effect:
    min_sites_for_escalation: 4
    slope: 0.08
    cap: 0.85
```

#### 5.2.2 File: `config/layer1/3A/country_zone_alphas.yaml`
Replace single‑dominant alpha with mixture components:
```yaml
prior_mixture:
  hub_component:
    weight: 0.70
    alpha_scale: 25.0
  tail_component:
    weight: 0.30
    alpha_scale: 5.0
  tail_floor_alpha: 0.15
  min_effective_tz: 2
```

#### 5.2.3 File: `config/layer1/3A/zone_floor_policy.yaml`
Introduce anti‑collapse floors (only for escalated pairs with sufficient outlets):
```yaml
floor_policy:
  min_second_zone_share: 0.05
  apply_if_total_outlets_gte: 6
  max_forced_zones: 3
```

#### 5.2.4 File: `config/layer1/3A/day_effect_policy_v1.yaml`
If day effects are used for allocation shaping, add guardrails:
```yaml
day_effects:
  max_daily_multiplier: 1.25
  min_daily_multiplier: 0.80
```

### 5.3 Exact code deltas
#### 5.3.1 File: `packages/engine/src/engine/layers/l1/seg_3A/s2_country_zone_priors/runner.py`
Required changes:
1. Replace single alpha construction with mixture:
   - compute hub alpha vector,
   - compute tail alpha vector,
   - combine using mixture weights.
2. Enforce `min_effective_tz >= 2` for multi‑TZ countries.
3. Emit diagnostics:
   - `top1_share`, `hhi`, `effective_tz_count` per country.

#### 5.3.2 File: `packages/engine/src/engine/layers/l1/seg_3A/s3_zone_shares/runner.py`
Required changes:
1. Add merchant‑level dispersion:
   - per‑merchant alpha scaling (hash‑seeded).
2. Preserve deterministic RNG evidence logs.
3. Emit diagnostics:
   - per‑merchant `top1_share`, `entropy`.

#### 5.3.3 File: `packages/engine/src/engine/layers/l1/seg_3A/s4_zone_counts/runner.py`
Required changes:
1. Apply minimum second‑zone floor for escalated pairs meeting outlet threshold.
2. Add optional stochastic rounding for near‑threshold zones (seeded).

#### 5.3.4 File: `packages/engine/src/engine/layers/l1/seg_3A/s6_validation/runner.py`
Required changes:
1. Add hard‑gate realism checks defined in Section 6.
2. Persist metrics and thresholds in validation report.

### 5.4 Determinism controls
1. Seed namespaces:
   - `3A_S2_prior_mix`,
   - `3A_S3_dispersion`,
   - `3A_S4_rounding`.
2. Stable merchant keys for per‑merchant draws.
3. No wall‑clock randomness.

### 5.5 Backward‑compatibility constraints
1. Preserve output schema; new fields must be additive.
2. Maintain `zone_alloc` schema and contract.
3. Policy version bump for reproducibility.

### 5.6 Execution order
1. Land S2 prior mixture first (core bottleneck).
2. Land S3 dispersion next (merchant heterogeneity).
3. Enable S6/S7 realism checks in observe‑then‑block mode.
4. Add S4 safeguards only if multi‑zone rate remains below target.
5. Add escalation smoothing only if non‑monotonicity persists.

### 5.7 Expected first‑order metric movement
1. S2 top‑1 share median drops from ~0.99 to ~0.75–0.85.
2. Multi‑zone rate for escalated pairs rises from 13% to `>= 35%`.
3. Merchant dispersion (std share) rises from ~0.003 to `>= 0.02`.
4. S4 top‑1 share median drops below `0.90`.

## 6) Validation Tests + Thresholds
This section defines the validation protocol that proves Section 5 remediation changed statistical behavior in the intended direction and at stable quality.

### 6.1 Validation intent
Validation is split into three layers:
1. `Hard gates (B floor)` that must pass to claim minimum credible realism.
2. `Stretch gates (B+ target)` that must pass to claim stronger realism.
3. `Cross-seed stability gates` that prevent one-seed false confidence.

### 6.2 Execution protocol
1. Run baseline scenario with seeds `{42, 7, 101, 202}`.
2. Compute primary metrics on full populations where feasible.
3. For expensive metrics (JS divergence, etc.), use deterministic hash-sample for tuning and confirm once on a full pass.
4. Metrics derived strictly from S1–S5 outputs (no hidden intermediate state).

### 6.3 Hard‑gate matrix (`B` minimum)
| Test ID | Surface | Metric | `B` Threshold | Why it matters | Fail action |
|---|---|---|---|---|---|
| `3A-V01` | S2 priors | Median top‑1 share (multi‑TZ) | `<= 0.85` | Priors must allow multiple tzids to matter | Block |
| `3A-V02` | S2 priors | % countries with top‑1 share `>=0.99` | `<= 20%` | Prevents degenerate dominance | Block |
| `3A-V03` | S1→S4 coherence | Escalated pairs with >1 nonzero zone | `>= 35%` | Escalation must create multi‑zone outcomes | Block |
| `3A-V04` | S3 dispersion | Median std(share_drawn) within country | `>= 0.02` | Merchant‑level variability required | Block |
| `3A-V05` | S4 realism | Median top‑1 share after counts | `<= 0.90` | Integerization must preserve diversity | Block |
| `3A-V06` | S4 realism | p75 top‑1 share after counts | `<= 0.97` | Prevents “all‑monolithic” tail | Block |
| `3A-V07` | zone_alloc | Median top‑1 share | `<= 0.90` | Final output must be multi‑zone | Block |

### 6.4 Stretch matrix (`B+` target)
| Test ID | Metric | `B+` Threshold |
|---|---|---|
| `3A-S01` | Median top‑1 share (multi‑TZ) | `<= 0.75` |
| `3A-S02` | % top‑1 share `>=0.99` | `<= 10%` |
| `3A-S03` | Escalated pairs multi‑zone rate | `>= 55%` |
| `3A-S04` | Median std(share_drawn) | `>= 0.04` |
| `3A-S05` | S4 median top‑1 share | `<= 0.85` |
| `3A-S06` | zone_alloc median top‑1 share | `<= 0.85` |
| `3A-S07` | Escalation monotonicity | no major dips across `tz_count` |

### 6.5 Cross‑seed stability gates
| Test ID | Metric family | Threshold |
|---|---|---|
| `3A-X01` | CV of key medians (S2 top1, S3 std, S4 top1, multi‑zone rate) | `<= 0.25` for `B`, `<= 0.15` for `B+` |
| `3A-X02` | Escalation rate stability | within policy band on all seeds |
| `3A-X03` | Hard‑gate consistency | no hard‑gate failures on any seed |

### 6.6 Diagnostic add‑ons (confidence layer)
1. KS test between seeds for top‑1 share distribution (shape stability).
2. Bootstrap CI for multi‑zone rate; lower 95% bound must exceed threshold.
3. “Before vs after” uplift test: post‑remediation must show directional improvement vs baseline on all core metrics.

### 6.7 Acceptance logic
1. `B pass`: all hard gates and stability gates pass.
2. `B+ pass`: hard + stretch + tighter stability pass.
3. Any hard‑gate fail means no `B` claim.

### 6.8 Required artifacts per validation cycle
1. `3A_validation_metrics_seed_<seed>.json`
2. `3A_validation_cross_seed_summary.json`
3. `3A_validation_failure_trace.md` with fault domain (`policy`, `code`, `upstream`) when failed.

## 7) Expected Grade Lift (Local + Downstream Impact)
This section converts the remediation package into expected grade movement for Segment 3A and downstream segments.

### 7.1 Local grade‑lift forecast for 3A
| Scenario | Change package | Expected grade band | Rationale |
|---|---|---|---|
| Current baseline | none | `C` | structurally correct, behaviorally flat (priors + sampling + integerization collapse) |
| Core remediation | `CF-3A-01 + CF-3A-02 + CF-3A-03` | `B-` to `B` | restores priors diversity, adds merchant heterogeneity, gates realism |
| Core + safeguards | core + `CF-3A-05` | `B` (stronger) | prevents integerization collapse if still present |
| Full calibration | core + `CF-3A-04 + CF-3A-05` | `B` to `B+` | smooth escalation + preserve multi‑zone breadth |

### 7.2 Metric‑level lift expectations
| Metric | Current posture | Expected after core (`B`) | Expected after full (`B+`) |
|---|---|---|---|
| S2 top‑1 share median (multi‑TZ) | ~0.99 | `<=0.85` | `<=0.75` |
| % countries with top‑1 share >=0.99 | ~66% | `<=20%` | `<=10%` |
| Escalated pairs multi‑zone rate | 13% | `>=35%` | `>=55%` |
| Median std(share_drawn) | ~0.003 | `>=0.02` | `>=0.04` |
| S4 top‑1 share median | ~1.0 | `<=0.90` | `<=0.85` |
| zone_alloc top‑1 share median | ~1.0 | `<=0.90` | `<=0.85` |

### 7.3 Downstream impact forecast
1. **On 5A/5B**: expected medium lift because more realistic multi‑zone allocation improves downstream routing diversity and zone‑level volume realism.
2. **On 6A/6B**: expected medium lift; 3A affects cross‑zone structures that feed later routing/flow distributions, reducing uniformity artifacts.

### 7.4 Confidence and caveats
1. **Confidence to reach `B`**: high if priors + dispersion + contract gates pass.
2. **Confidence to reach `B+`**: medium; depends on successful escalation smoothing and integerization safeguards.
3. **Caveat**: multi‑zone improvements must be stable across seeds to claim grade.

### 7.5 Decision rule for final grading
1. Award `B` only if all `3A-V*` hard gates and `3A-X*` stability gates pass.
2. Award `B+` only if hard + stretch + tighter stability pass.
3. Any hard‑gate failure keeps 3A below `B` regardless of improvements elsewhere.
