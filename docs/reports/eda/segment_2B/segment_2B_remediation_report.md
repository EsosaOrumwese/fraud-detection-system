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

## 6) Validation Tests + Thresholds

## 7) Expected Grade Lift (Local + Downstream Impact)
