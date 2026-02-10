# Segment 2B Remediation Report

Date: 2026-02-07
Scope: Statistical remediation planning for segment 2B toward target grade `B/B+`.
Status: Planning only. No fixes implemented in this document.

---

## 1) Observed Weakness
This section records the measured weaknesses from `segment_2B_published_report.md` that currently block a `B/B+` realism claim for Segment 2B.

### 1.1 Critical realism failure: S1 site weights are fully uniform, not behavior-shaped
Primary evidence from the analytical report:
1. `weight_source = uniform` for 100% of rows.
2. Merchant-level weight standard deviation is `0` for every merchant.
3. Top-1 site weight quantiles follow exact `1/N` behavior (for example p50 `= 0.0625`).
4. HHI and entropy residual diagnostics collapse to the uniform baseline.

Why this is a critical blocker:
1. No merchant has hub-versus-tail structure in site allocation.
2. Site traffic is mechanically flat inside each merchant footprint.
3. Downstream routing cannot express realistic geographic concentration or explainable site-level risk gradients.

### 1.2 High-severity realism failure: S4 routing mix is heavily single-timezone dominated
Primary evidence:
1. Merchant-days with `max_p_group >= 0.90`: `51.7%`.
2. Merchant-days with `max_p_group >= 0.95`: `49.1%`.
3. Merchant-days with `max_p_group >= 0.99`: `48.4%`.
4. `tz_groups` per merchant-day remains concentrated at 1-2 groups (`1 group = 48.3%`).

Why this is high severity:
1. Multi-region merchants still behave like single-zone merchants on many days.
2. Geographic diversity exists structurally but is weak behaviorally in realized routing weights.

### 1.3 High-severity realism failure: S3 day effects are globally plausible but locally homogeneous
Primary evidence:
1. Aggregate gamma shape is plausible (centered near 1.0 with bounded spread).
2. `sigma_gamma` is effectively constant across merchants (no merchant-specific volatility regimes).
3. Top tz-group gamma distributions are near-identical.

Why this is high severity:
1. Day effects do not encode merchant-level temporal identity.
2. Temporal dynamics become generic and weakly explainable, even when aggregate distribution looks acceptable.

### 1.4 High-severity evaluation weakness: S5 workload is too shallow to validate routing realism
Primary evidence:
1. The assessed roster behaves like a one-day/one-arrival-per-merchant smoke profile.
2. There is little temporal depth for observing routing persistence, drift, or behavioral regime changes.

Why this is high severity:
1. A shallow roster can pass structural gates while hiding realism defects.
2. It under-tests day-to-day routing behavior and weakens confidence in `B/B+` realism claims.

### 1.5 Medium-severity upstream dependency weakness: 2B inherits constrained geography from upstream surfaces
Primary evidence:
1. 2B diagnostics explicitly flag upstream topology shape as a realism limiter in some cohorts.
2. S4 breadth does not consistently scale with merchant size across the panel.

Why this matters:
1. Even improved 2B policy can underperform if upstream spatial diversity remains constrained.
2. This is a contributing factor, not the primary bottleneck.

### 1.6 Structural correctness remains strong, but masks behavioral weakness
Primary evidence:
1. Alias integrity, normalization, audit, and bundle checks are largely green.
2. `sum_p_group` stability is numerically tight around 1.0.

Why this matters:
1. The segment is mechanically correct but statistically weak.
2. Remediation must target generation behavior (distribution shape), not pipeline mechanics.

### 1.7 Section 1 conclusion
Segment 2B’s main weakness is low behavioral realism, not broken infrastructure:
1. Uniform merchant-site weighting in `S1`.
2. Excessive single-group dominance in `S4`.
3. Homogeneous temporal volatility structure in `S3`.
4. Insufficient workload depth in `S5` for realism-grade validation.

This establishes the baseline for Section 2 expected posture and Section 3 root-cause trace.

## 2) Expected Statistical Posture (B/B+)
This section defines the target statistical posture for Segment 2B once remediation is applied.  
Goal: produce routing surfaces that remain structurally correct while exhibiting credible synthetic realism.

### 2.1 Hard `B` gates (fail-closed)
If any gate below fails, Segment 2B cannot be graded `B` regardless of other improvements.

1. **S1 must no longer be uniform-by-construction.**
   - `weight_source=uniform` share must be `< 90%` (or equivalent mixed model must be active by policy).
   - Median merchant `top1-top2` gap must be `>= 0.03`.
   - Median absolute residual `|p_weight - 1/N|` must be `>= 0.003`.

2. **S4 must not be single-group dominated.**
   - `median(max_p_group) <= 0.85`.
   - `p75(max_p_group) <= 0.93`.
   - Share of merchant-days with `max_p_group >= 0.95` must be `<= 35%`.

3. **S4 must show effective multi-group behavior.**
   - Merchant-days with at least 2 groups where `p_group >= 0.05` must be `>= 35%`.

4. **S3 must carry merchant-level temporal heterogeneity.**
   - Merchant-level gamma volatility spread must be non-zero across merchants.
   - Median merchant day-effect standard deviation must be `>= 0.03`.

5. **S5 workload used for validation must be realism-grade (not smoke-test).**
   - Multi-day roster is mandatory (`>= 28` days minimum).
   - Repeated arrivals per merchant are mandatory (no one-shot panel-only profile).

6. **Structural integrity must remain green.**
   - Alias parity/hash checks pass.
   - `sum_p_group` remains within numeric tolerance.
   - Audit/bundle checks remain PASS.

### 2.2 `B` vs `B+` target bands
| Axis | `B` target | `B+` target |
|---|---|---|
| S1 uniformity residual (`|p-1/N|` median) | `>= 0.003` | `>= 0.006` |
| S1 top1-top2 gap (median) | `>= 0.03` | `>= 0.05` |
| S1 concentration spread (HHI IQR) | `>= 0.06` | `>= 0.10` |
| S4 median `max_p_group` | `<= 0.85` | `<= 0.78` |
| S4 p75 `max_p_group` | `<= 0.93` | `<= 0.88` |
| S4 share `max_p_group >= 0.95` | `<= 35%` | `<= 20%` |
| S4 effective multi-group days (`>=2 groups with p>=0.05`) | `>= 35%` | `>= 50%` |
| S4 entropy p50 | `>= 0.35` | `>= 0.45` |
| S3 merchant volatility heterogeneity | clear non-zero spread | stable segment-like spread |
| S5 realism roster depth | `>= 28` days | full policy horizon (90 days in this run setup) |

### 2.3 Cross-seed stability gates
Required seeds: `{42, 7, 101, 202}`.

1. All hard gates must pass on all required seeds.
2. Cross-seed CV for primary medians (`S1 residual`, `S4 max_p_group`, `S4 entropy`):
   - `<= 0.25` for `B`
   - `<= 0.15` for `B+`
3. No seed-specific mode collapse:
   - no seed may revert to near-uniform S1 or near-monolithic S4 while others pass.

### 2.4 Interpretation of expected posture
For Segment 2B, `B/B+` means:
1. `S1` expresses believable merchant site concentration instead of exact equal-site allocation.
2. `S3` adds merchant-specific temporal behavior rather than a single global volatility template.
3. `S4` preserves meaningful multi-timezone routing in a substantial share of merchant-days.
4. `S5` is validated on a workload with enough temporal depth to expose routing dynamics.
5. Structural correctness remains intact while behavioral realism improves.

## 3) Root-Cause Trace
This section traces each observed weakness back to concrete design/policy/implementation decisions, and identifies whether the weakness is local to 2B or inherited from upstream segments.

### 3.1 Root-cause map (weakness -> mechanism -> locus)
| Weakness from Section 1 | Immediate mechanism | Primary locus | Secondary locus |
|---|---|---|---|
| S1 weights are fully uniform | Per-merchant site weights are generated as equal-share vectors (`1/N`) with no heterogeneity path enabled | **2B S1 policy/implementation** | Upstream geography shape can amplify, but is not primary |
| S4 is heavily single-group dominated | Group mass is computed from S1 base shares plus S3 day multipliers; flat S1 and homogeneous S3 preserve concentration | **2B S1 + S3 -> S4 coupling** | Upstream 1B/2A breadth affects ceiling |
| S3 is globally plausible but locally homogeneous | One effective volatility regime (`sigma_gamma` effectively constant) and weak segment-specific modulation | **2B S3 policy** | None |
| S5 roster cannot validate realism | Validation workload behaves like smoke profile (one-shot, low temporal depth) | **2B S5 validation setup** | Downstream consumer tests inherit blind spot |

### 3.2 Primary bottleneck: S1 uniform-by-construction
Evidence chain:
1. `weight_source=uniform` for all rows.
2. Merchant-level weight standard deviation collapses to zero.
3. Top-1 and top-2 site weights are equal by construction.
4. HHI/entropy follow deterministic equal-share signatures.

Why this is causal, not correlative:
1. If all site weights are equal, downstream sampling cannot create realistic site hubs.
2. S4 can only reweight timezone groups from already-flat site mass, so it inherits weak spatial asymmetry.
3. Any fraud signal tied to “merchant hot sites” is structurally suppressed.

Conclusion: **S1 policy/implementation choice is the single strongest root cause for 2B realism underperformance.**

### 3.3 S4 concentration is mostly inherited, not an isolated S4 bug
Evidence chain:
1. S4 normalization is numerically healthy (`sum(p_group)` close to 1), so mass accounting is not broken.
2. Dominance metrics remain high (`max_p_group` thresholds triggered at large shares), indicating behavioral concentration.
3. S4 receives its base structure from S1 and temporal modulation from S3; both are low-heterogeneity in current posture.

Interpretation:
1. This is not primarily an arithmetic defect in S4.
2. S4 is expressing the limited diversity it is given.
3. Direct S4-only tuning can soften dominance, but durable remediation requires S1+S3 changes first.

### 3.4 S3 issue: realistic aggregate shape, unrealistic local identity
Evidence chain:
1. Aggregate gamma distribution looks plausible.
2. Merchant-level volatility structure is effectively constant.
3. Top tz-group gamma profiles are near-indistinguishable.

Interpretation:
1. The system achieves global plausibility but fails local realism.
2. Fraud modeling requires differentiable merchant and region temporal regimes.
3. Without local heterogeneity, S3 contributes noise-like variation rather than explainable behavior.

### 3.5 Validation blind spot in S5
Evidence chain:
1. Assessed workload depth is too shallow for behavior-grade validation.
2. Short horizon can pass structural gates while masking concentration and homogeneity defects.

Interpretation:
1. The current validation posture is sufficient for pipeline smoke checks.
2. It is insufficient for `B/B+` statistical realism claims.
3. This is a governance/validation design gap, not only a generation-policy gap.

### 3.6 Upstream contribution (1B/2A) is real but secondary
Observed contribution:
1. Constrained spatial topology and tz mapping breadth can limit achievable diversity in 2B outputs.
2. Some merchant cohorts show limited tz breadth even before S4 mixing.

Bounded conclusion:
1. Upstream constraints cap the upper bound of 2B realism.
2. They do **not** explain fully uniform S1 weights or constant S3 volatility.
3. Therefore upstream is a **co-factor**, not the lead cause for current grade.

### 3.7 Responsibility split (to avoid mis-targeted fixes)
1. **2B S1 owner surface:** introduce merchant/site concentration heterogeneity.
2. **2B S3 owner surface:** introduce merchant/segment/tz volatility heterogeneity.
3. **2B S4 owner surface:** preserve normalization while reducing monolithic daily dominance, conditional on S1/S3 fixes.
4. **2B validation surface (S5/gates):** enforce realism-grade workload and anti-regression checks.
5. **Upstream coordination (1B/2A):** increase effective geographic/tz diversity where topology is currently too narrow.

### 3.8 Root-cause conclusion
Segment 2B misses `B/B+` primarily because behavioral diversity was never activated in the generation logic:
1. Flat spatial priors in S1.
2. Flat volatility regimes in S3.
3. S4 inheriting both and appearing overly dominant by group.
4. Validation workload that is too shallow to fail these conditions early.

This root-cause trace supports Section 4 ranking: highest-leverage remediation must start with `S1 -> S3 -> S4`, then lock behavior with stronger validation gates.

## 4) Remediation Options (Ranked + Tradeoffs)
This section enumerates statistically meaningful remediation paths, ranked by expected realism lift per unit implementation effort and risk.  
Ranking principle: prefer options that remove root causes (Section 3), not symptoms.

### 4.1 Ranking summary
| Rank | Option | Weaknesses addressed | Expected lift | Main tradeoff |
|---|---|---|---|---|
| 1 | S1 merchant-site heterogeneity model | Uniform S1, weak spatial realism, inherited S4 concentration | Highest (`C` -> `B-` potential alone) | More policy complexity and tuning burden |
| 2 | S3 merchant/segment/tz volatility heterogeneity | Local temporal homogeneity | High (`B-` stabilization and `B` path) | Risk of noisy dynamics if overtuned |
| 3 | Realism-grade validation roster + gates (S5 + audit) | Validation blind spot and false-PASS risk | High confidence lift, strong anti-regression | Runtime/storage overhead |
| 4 | S4 anti-dominance shaping (entropy/floor controls) | Excessive single-group dominance | Medium-high (especially for `B+`) | Can look synthetic if used without S1/S3 fixes |
| 5 | Upstream 1B/2A topology broadening | Structural diversity ceiling | Medium (enables upper bound) | Cross-segment coordination cost |
| 6 | S4-only cosmetic rebalance | Visible dominance symptoms only | Low-medium and fragile | Treats symptom, not source |

### 4.2 Option 1 (Rank 1): S1 heterogeneity injection (highest leverage)
Core mechanism:
1. Replace deterministic equal-share vectors with a mixed concentration law:
   - hub-and-spoke branch (few dominant sites + long tail),
   - heavy-tail branch (Zipf/Dirichlet-style),
   - merchant-size-conditioned concentration.
2. Add segment/country priors so shape differs by merchant cohort instead of one global profile.
3. Keep hard normalization and floor controls to preserve structural correctness.

Why it is first:
1. S1 is the dominant source term for S4 routing realism.
2. With flat S1, downstream stages cannot express realistic spatial asymmetry.
3. It directly addresses the strongest root cause identified in Section 3.

Expected statistical effect:
1. `|p_weight - 1/N|` median rises out of collapse region into target band.
2. `top1-top2` gap becomes non-zero and cohort-sensitive.
3. HHI/entropy spread broadens across merchants.
4. S4 dominance tails reduce organically (without artificial rebalancing).

Tradeoffs:
1. Parameter surface grows and needs guardrails.
2. Requires seed-stability calibration to avoid volatile concentration swings.

### 4.3 Option 2 (Rank 2): S3 heterogeneity and temporal structure
Core mechanism:
1. Move from one effective volatility regime to distributed merchant-level `sigma_gamma`.
2. Layer weak but real structure:
   - weekly rhythm,
   - segment/channel-level variance multipliers,
   - optional tz/region modulation.
3. Preserve aggregate gamma moments while increasing local identifiability.

Why second:
1. Aggregate S3 already looks plausible; the failure is local identity.
2. Temporal heterogeneity is necessary for explainable fraud patterns by merchant and region.

Expected statistical effect:
1. Non-degenerate merchant volatility distribution.
2. Discernible tz-group temporal differences.
3. Better local realism while retaining global plausibility.

Tradeoffs:
1. Over-tuning can create unrealistic oscillation artifacts.
2. Requires stronger acceptance tests (Section 6) to bound dynamics.

### 4.4 Option 3 (Rank 3): Validation roster + realism gates
Core mechanism:
1. Upgrade S5 validation workload from smoke profile to realism-grade profile:
   - `>= 28` days (prefer full horizon),
   - repeated arrivals per merchant/day,
   - preserved class/channel mix coverage.
2. Add explicit realism pass/fail gates to CI evidence (not only structural checks).

Why third:
1. Current posture can pass while still statistically weak.
2. This option prevents recurrence of hidden realism regressions.

Expected statistical effect:
1. Not a generator-shape change by itself.
2. Large confidence uplift through early regression detection.
3. Enables defensible `B/B+` claim governance.

Tradeoffs:
1. More runtime and larger audit artifacts.
2. More operational burden for seed matrix validation.

### 4.5 Option 4 (Rank 4): S4 anti-dominance shaping
Core mechanism:
1. Apply bounded anti-collapse controls in group-mix assembly:
   - soft floor on secondary groups when multi-group eligible,
   - entropy-aware regularization,
   - tail clipping for extreme `max_p_group` only where policy allows.
2. Keep strict `sum(p_group)=1` and provenance columns.

Why fourth:
1. Directly targets failing S4 dominance metrics.
2. Best as a second-order tuner after S1/S3 remediation.

Expected statistical effect:
1. Lower share of merchant-days with `max_p_group >= 0.95`.
2. Higher effective multi-group-day share.
3. Improved entropy distribution center.

Tradeoffs:
1. If applied too early or too strongly, behavior may appear engineered.
2. Can mask root-cause defects if S1/S3 remain unchanged.

### 4.6 Option 5 (Rank 5): Upstream 1B/2A diversity uplift
Core mechanism:
1. Broaden realistic site topology in 1B where geography is overly narrow.
2. Improve effective timezone mapping breadth in 2A for eligible merchants.

Why fifth:
1. Upstream surfaces constrain the upper realism ceiling.
2. They are not the lead cause of current 2B collapse (Section 3.6).

Expected statistical effect:
1. Better achievable S4 breadth for affected cohorts.
2. Stronger long-run headroom for `B+`.

Tradeoffs:
1. Requires cross-segment alignment and sequencing.
2. Slower delivery than local 2B policy changes.

### 4.7 Option 6 (Rank 6): S4-only cosmetic rebalance (deprioritized)
Core mechanism:
1. Force S4 spread without fixing S1/S3 generators.

Why last:
1. Produces visible but fragile metric improvements.
2. High risk of symptom treatment with weak causal durability.

Tradeoffs:
1. Quick apparent gain.
2. Low credibility and likely regression under seed/roster changes.

### 4.8 Recommended execution package for Segment 2B
Recommended sequence:
1. **Wave 1 (causal core):** Option 1 + Option 2 + Option 3.
2. **Wave 2 (tail tuning):** Option 4.
3. **Wave 3 (ceiling unlock):** Option 5 where still constrained.
4. Keep Option 6 only as a temporary emergency lever, never as primary remediation.

Rationale:
1. This order fixes causes before tuning symptoms.
2. It maximizes probability of durable movement from current `C` posture toward stable `B`, then `B+`.
3. It aligns with Section 3 dependency chain (`S1 -> S3 -> S4`, then harden with validation and upstream coordination).

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)
This section locks the exact remediation package selected from Section 4.  
Scope here is specification only (no implementation in this document).

### 5.1 Chosen package (must ship together)
1. **S1 heterogeneity activation** (primary causal fix).
2. **S3 volatility heterogeneity** (secondary causal fix).
3. **S4 anti-collapse regularization** (bounded tuning layer; applied after S1/S3).
4. **S5 realism-grade validation roster + hard gates** (governance lock to prevent false PASS).

Rationale for coupling:
1. S1 fixes spatial prior collapse.
2. S3 restores merchant/time heterogeneity.
3. S4 then tunes dominance tails without fabricating diversity.
4. S5 ensures the segment cannot be re-certified using shallow smoke profiles.

### 5.2 Exact policy deltas
#### 5.2.1 S1 policy delta (site-weight generator)
File:
1. `config/layer1/2B/policy/alias_layout_policy_v1.json`

Current posture:
1. `weight_source.mode = "uniform"` (deterministic equal-share by construction).

Required delta:
1. Replace with `weight_source.mode = "profile_mixture_v2"`.
2. Add block `profile_mixture_v2` with:
   - `merchant_size_buckets` (`small`, `mid`, `large`)
   - `mixture_weights` (`hub_spoke`, `heavy_tail`, `near_uniform`)
   - `concentration_alpha_by_bucket`
   - `top1_soft_cap_by_bucket`
   - `min_secondary_mass`
   - `deterministic_seed_scope = "merchant_id"`
3. Keep alias/hash/checksum schema unchanged.
4. Keep hard normalization contract (`sum(weights)=1`) unchanged.

Expected direct movement:
1. `|p_weight - 1/N|` median rises out of collapse region.
2. Merchant `top1-top2` gaps become non-zero and cohort-dependent.
3. HHI/entropy spread broadens from deterministic uniform signature.

#### 5.2.2 S3 policy delta (day-effect volatility structure)
File:
1. `config/layer1/2B/policy/day_effect_policy_v1.json`

Current posture:
1. Single scalar `sigma_gamma` acts as one effective volatility regime.

Required delta:
1. Replace scalar with `sigma_gamma_policy_v2`:
   - `sigma_base_by_segment`
   - `sigma_multiplier_by_tz_group`
   - `sigma_jitter_by_merchant` (bounded deterministic jitter)
   - `weekly_component_amp_by_segment`
   - bounds: `sigma_min`, `sigma_max`, `gamma_clip`
2. Preserve aggregate gamma center (around 1.0) while increasing local spread.

Expected direct movement:
1. Non-degenerate merchant-level volatility distribution.
2. Distinguishable tz-group temporal signatures.
3. Better explainability of time behavior in downstream routing/fraud features.

#### 5.2.3 S4 policy delta (anti-collapse tuner)
Policy surface:
1. Add/extend 2B S4 policy block as `group_mix_regularizer_v1`.

Required fields:
1. `enabled = true`
2. `apply_when_groups_ge = 2`
3. `max_p_group_soft_cap`
4. `regularization_strength`
5. `entropy_floor`
6. `preserve_rank_order = true`
7. `sum_to_one = true`

Constraint:
1. This layer is a tuner, not a substitute for S1/S3 fixes.

Expected direct movement:
1. Lower tail mass at `max_p_group >= 0.95`.
2. Higher share of effective multi-group days.
3. Improved entropy center without violating normalization.

### 5.3 Exact code deltas
#### 5.3.1 S1 implementation delta
File:
1. `packages/engine/src/engine/layers/l1/seg_2B/s1_site_weights/runner.py`

Required code behavior:
1. Implement `profile_mixture_v2` resolver.
2. Generate per-merchant site-weight vector from chosen mixture branch.
3. Use deterministic merchant-scoped seed for replay consistency.
4. Apply clip/floor, then renormalize exactly.
5. Emit provenance fields:
   - `weight_profile`
   - `mixture_component`
   - `alpha_used`

#### 5.3.2 S3 implementation delta
File:
1. `packages/engine/src/engine/layers/l1/seg_2B/s3_day_effects/runner.py`

Required code behavior:
1. Replace global sigma path with per-row sigma resolution from `sigma_gamma_policy_v2`.
2. Apply optional weekly component with bounded amplitude.
3. Keep deterministic seeds and reproducibility contract.
4. Emit provenance fields:
   - `sigma_source`
   - `sigma_value`
   - `weekly_amp`

#### 5.3.3 S4 implementation delta
File:
1. `packages/engine/src/engine/layers/l1/seg_2B/s4_group_weights/runner.py`

Required code behavior:
1. Apply regularizer only when `n_groups >= apply_when_groups_ge`.
2. Use soft-cap logic for extreme `max_p_group` (no hard truncation artifacts).
3. Preserve rank order where policy requires.
4. Enforce exact `sum(p_group)=1`.
5. Emit provenance fields:
   - `regularizer_applied`
   - `regularizer_strength`

### 5.4 Validation-roster gate (mandatory for realism certification)
The segment cannot be graded on smoke workload.  
Certification must require:
1. horizon `>= 28` days (target: full run horizon),
2. repeated arrivals per merchant-day,
3. class/channel coverage retained,
4. seed panel execution for stability checks (as defined in Section 2).

Fail-closed rule:
1. If realism roster requirements are not met, Section 6 validation is invalid for grade assignment.

### 5.5 Execution sequencing (sealed-run safe)
Apply and evaluate in strict order:
1. S1 policy + code delta,
2. S3 policy + code delta,
3. S4 policy + code delta,
4. realism-grade roster run,
5. Section 6 gates,
6. Section 7 grade-lift assessment.

Reason:
1. This preserves causal attribution and avoids tuning S4 against still-collapsed upstream generators.

### 5.6 Expected metric movement from chosen spec
After this package, expected movement before final tuning:
1. `|p_weight - 1/N|` median: out of near-zero collapse band.
2. `top1-top2` median: materially positive and cohort-sensitive.
3. `max_p_group` tail (`>=0.95`): significant reduction from current dominance rates.
4. Effective multi-group-day share: increases into/near Section 2 `B` threshold.
5. Merchant-level gamma volatility: clear non-zero spread.

## 6) Validation Tests + Thresholds
This section defines the acceptance protocol for certifying Segment 2B after the chosen fix package in Section 5.  
All tests are fail-closed: any hard failure blocks grade upgrade.

### 6.1 Validation preconditions (fail-closed)
1. Run type must be **realism-grade**, not smoke:
   - horizon `>= 28` days,
   - repeated arrivals per merchant-day,
   - retained class/channel coverage.
2. Required seed panel: `{42, 7, 101, 202}`.
3. Active policy fingerprints for S1/S3/S4 must match Section 5 fix spec.
4. If any precondition fails, certification status is `INVALID_FOR_GRADING`.

### 6.2 S1 spatial heterogeneity tests
#### T-S1-01 Uniformity residual activation
1. Metric: median `|p_site - 1/N_sites|` across merchant-site rows.
2. Thresholds:
   - `B`: `>= 0.003`
   - `B+`: `>= 0.006`
3. Fail condition: median remains below `B` threshold on any required seed.

#### T-S1-02 Dominance gap activation
1. Metric: median merchant-level `top1_share - top2_share`.
2. Thresholds:
   - `B`: `>= 0.03`
   - `B+`: `>= 0.05`
3. Fail condition: gap profile remains near zero (uniform-like collapse).

#### T-S1-03 Concentration spread
1. Metric: IQR of merchant-level HHI (or equivalent concentration metric).
2. Thresholds:
   - `B`: `>= 0.06`
   - `B+`: `>= 0.10`
3. Fail condition: spread remains collapsed at near-deterministic levels.

### 6.3 S3 temporal heterogeneity tests
#### T-S3-01 Merchant volatility spread
1. Metric: distribution spread of merchant-level day-effect standard deviation.
2. Thresholds:
   - `B`: median merchant std-dev `>= 0.03`
   - `B+`: median merchant std-dev `>= 0.04` with visible upper tail
3. Fail condition: near-point-mass volatility (single effective sigma regime).

#### T-S3-02 TZ-group differentiation
1. Metric: between-group variance in gamma profile summaries over common horizon.
2. Thresholds:
   - `B`: statistically non-zero separation across required seeds
   - `B+`: stable non-zero separation with controlled drift
3. Fail condition: top tz-groups remain effectively indistinguishable.

#### T-S3-03 Aggregate stability guardrail
1. Metric: aggregate gamma center and spread remain within design bounds.
2. Threshold: no clipping saturation or instability event.
3. Fail condition: local heterogeneity introduced by destabilizing global shape.

### 6.4 S4 routing realism tests
#### T-S4-01 Dominance center
1. Metric: median `max_p_group` over merchant-day.
2. Thresholds:
   - `B`: `<= 0.85`
   - `B+`: `<= 0.78`
3. Fail condition: median remains in monolithic-routing region.

#### T-S4-02 Dominance tail
1. Metric: share of merchant-days with `max_p_group >= 0.95`.
2. Thresholds:
   - `B`: `<= 35%`
   - `B+`: `<= 20%`
3. Fail condition: extreme-tail dominance persists.

#### T-S4-03 Effective multi-group behavior
1. Metric: share of merchant-days with at least 2 groups where `p_group >= 0.05`.
2. Thresholds:
   - `B`: `>= 35%`
   - `B+`: `>= 50%`
3. Fail condition: breadth exists structurally but not behaviorally.

#### T-S4-04 Entropy center
1. Metric: p50 entropy of group weights per merchant-day.
2. Thresholds:
   - `B`: `>= 0.35`
   - `B+`: `>= 0.45`
3. Fail condition: anti-collapse tuning does not lift entropy distribution.

#### T-S4-05 Mass conservation
1. Metric: rowwise `sum(p_group)`.
2. Threshold: all rows within numeric tolerance of `1.0`.
3. Fail condition: any normalization breach.

### 6.5 Structural integrity non-regression tests
1. Alias parity/hash/canonicalization checks remain PASS.
2. Audit and bundle integrity checks remain PASS.
3. Schema/provenance contracts for added S1/S3/S4 fields remain valid.
4. Any structural failure overrides realism PASS.

### 6.6 Cross-seed stability tests
1. All hard `B` gates in Sections 6.2-6.5 must pass for all required seeds.
2. Cross-seed CV limits for primary medians (`S1 residual`, `S4 max_p_group`, `S4 entropy`):
   - `B`: `CV <= 0.25`
   - `B+`: `CV <= 0.15`
3. No seed-specific collapse is allowed (for example one seed reverting to near-uniform S1 or monolithic S4).

### 6.7 Decision logic
1. `B` certification requires:
   - all hard tests pass at `B` thresholds,
   - structural non-regression passes,
   - preconditions in Section 6.1 pass.
2. `B+` certification requires:
   - all tests pass at `B+` thresholds,
   - tighter cross-seed stability pass,
   - no compensating regressions across S1/S3/S4.
3. Any hard failure returns `NOT_CERTIFIED`.

### 6.8 Mandatory artifacts for evidence pack
1. Per-seed metric table with PASS/FAIL by test ID.
2. Cross-seed stability table with CV for primary medians.
3. Active policy fingerprint snapshot proving Section 5 fix spec.
4. Final certification record with status and failed gates (if any).

## 7) Expected Grade Lift (Local + Downstream Impact)
With Sections 5 and 6 executed as specified, this section defines expected grade movement and downstream impact.

### 7.1 Local grade lift expectation (2B only)
#### 7.1.1 Baseline (current)
1. Current statistical posture is in the `C` band: structurally correct but behaviorally weak.
2. Primary blockers are:
   - S1 uniform-by-construction,
   - S3 local temporal homogeneity,
   - S4 heavy single-group dominance tail,
   - shallow validation roster that can mask these defects.

#### 7.1.2 After Wave 1 (`S1 + S3 + validation guardrail`)
1. Expected grade movement: `C -> B- / B`.
2. Why:
   - S1 breaks deterministic equal-share collapse.
   - S3 introduces merchant/tz-level temporal identity.
   - validation preconditions block smoke-roster false PASS.

#### 7.1.3 After Wave 2 (`S4 anti-collapse tuning`)
1. Expected grade movement: stable `B`, with credible path to `B+`.
2. Why:
   - S4 dominance tail contracts,
   - effective multi-group routing share rises,
   - entropy center shifts upward while normalization remains exact.

#### 7.1.4 After Wave 3 (targeted upstream unlock where constrained)
1. Expected grade movement: `B+` for cohorts not topology-capped.
2. Why:
   - residual ceilings from upstream geography/tz constraints are reduced,
   - 2B can express broader realistic diversity where policy intends.

### 7.2 Metric-by-metric expected movement
#### 7.2.1 S1 metrics
1. `|p_site - 1/N|` median:
   - target movement to `>= 0.003` (`B`), stretch `>= 0.006` (`B+`).
2. `top1-top2` median:
   - target movement to `>= 0.03` (`B`), stretch `>= 0.05` (`B+`).
3. Concentration spread (HHI IQR):
   - target movement to `>= 0.06` (`B`), stretch `>= 0.10` (`B+`).

#### 7.2.2 S3 metrics
1. Merchant-level volatility spread:
   - from near-single regime to non-degenerate spread (`median std-dev >= 0.03` for `B`).
2. TZ-group differentiation:
   - from near-indistinguishable to stable non-zero separation.
3. Aggregate gamma guardrail:
   - global center/spread remains plausible and bounded (no instability accepted as tradeoff).

#### 7.2.3 S4 metrics
1. `median(max_p_group)`:
   - movement to `<= 0.85` (`B`), stretch `<= 0.78` (`B+`).
2. Share of merchant-days with `max_p_group >= 0.95`:
   - movement to `<= 35%` (`B`), stretch `<= 20%` (`B+`).
3. Effective multi-group days (`>= 2` groups with `p_group >= 0.05`):
   - movement to `>= 35%` (`B`), stretch `>= 50%` (`B+`).
4. Entropy p50:
   - movement to `>= 0.35` (`B`), stretch `>= 0.45`.

#### 7.2.4 Validation quality movement
1. Roster quality shifts from smoke-check capable to realism-certifiable.
2. Seed stability becomes an explicit hard gate instead of a narrative observation.

### 7.3 Downstream impact expectation
1. **Improved credibility for downstream segments (5B/6A/6B):**
   - richer 2B routing diversity reduces downstream over-simplification artifacts.
2. **Fraud-feature quality uplift:**
   - better site/time heterogeneity increases discriminability and explainability.
3. **Governance uplift:**
   - certification becomes evidence-driven and fail-closed, reducing regression risk.

### 7.4 Residual risks after remediation
1. **Topology ceiling risk:**
   - upstream 1B/2A constraints can still cap some cohorts below `B+`.
2. **Over-regularization risk:**
   - excessive S4 tuning can manufacture spread and reduce realism fidelity.
3. **Seed fragility risk:**
   - single-seed success is insufficient; cross-seed gates remain mandatory.

### 7.5 Certification expectation statement
If Section 5 is implemented exactly and Section 6 passes on required seeds with realism-grade roster:
1. Segment 2B is expected to move from `C` to at least `B`.
2. `B+` is achievable for cohorts not limited by upstream diversity ceilings.
3. Any hard-gate failure results in `NOT_CERTIFIED` for grade upgrade.
