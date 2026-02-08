# Segment 1B Remediation Report

Date: 2026-02-07
Scope: Statistical remediation planning for segment 1B toward target grade `B/B+`.
Status: Planning only. No fixes implemented in this document.

---

## 1) Observed Weakness

This section captures the measured realism blockers from `segment_1B_published_report.md` for Segment 1B (`site_locations` realism surface).

### 1.1 Macro concentration is too strong for B/B+
Measured evidence:
1. Country concentration is severe (`Gini = 0.753`).
2. Top-country shares are high:
- top 1% of countries hold `13.66%` of sites
- top 5% hold `39.33%`
- top 10% hold `59.74%`
3. Top-20 ranking is heavily concentrated in a narrow country set.

Why this blocks `B/B+`:
1. A B/B+ synthetic-global posture should still show concentration, but not a dominance regime where a small country subset drives most spatial mass.
2. Current concentration makes downstream behavior overly country-template-driven.

### 1.2 Geographic coverage is imbalanced (Europe-centric, weak global breadth)
Measured evidence:
1. Lat/lon distributions show strong peaks in northern mid-latitudes and Europe/Africa longitudes.
2. Southern hemisphere coverage is visibly thinner.
3. Choropleth and country bars show sparse presence across much of Africa and South America relative to Europe/North America/Australia.

Why this blocks `B/B+`:
1. Even under synthetic policy constraints, global realism needs credible regional breadth.
2. Empty or near-empty continental zones create obvious realism breaks for human reviewers.

### 1.3 Within-country geometry shows synthetic template artifacts
Measured evidence:
1. Small-multiple country panels show narrow latitude bands, corridor-like shapes, and split clusters in several countries.
2. These shapes are too regular in places and look policy-template generated rather than emergent urban spread.

Why this blocks `B/B+`:
1. Country-level geometry should reflect mixed urban cores plus secondary spread, not repeated stripe/corridor motifs.
2. Template artifacts amplify detectability of synthetic generation rules.

### 1.4 Local clustering is plausible but statistically unbalanced
Measured evidence:
1. Nearest-neighbor distance sample shows dense local clustering (`p50 = 0.28 km`, `p90 = 1.86 km`).
2. Tail is heavy (`p99 = 11.16 km`, with very long-distance outliers).

Why this blocks `B/B+`:
1. Dense cores are good, but the current core-plus-long-tail mix suggests uneven placement priors and diffuse sparse placements.
2. The spatial process does not yet look calibrated to a stable urban plus controlled rural tail target.

### 1.5 Upstream policy-expression weakness (distributional, not structural)
Measured evidence:
1. Structural integrity is strong (row parity, no duplicate key issues, coordinate bounds valid).
2. Weaknesses are distributional (where points are placed), not mechanical correctness.

Why this blocks `B/B+`:
1. A structurally perfect pipeline can still fail realism if placement policy is not representative.
2. The current grade bottleneck is policy shape and priors, not data loss or contract failures.

### 1.6 What is not weak (boundary condition)
1. Coordinate validity is clean (no out-of-range lat/lon).
2. Pipeline parity and deterministic lineage are clean.
3. Segment is reliable for reproducibility; realism shortfall is specifically geospatial representativeness.

### 1.7 Section 1 conclusion
Segment 1B currently has a structurally sound but geographically imbalanced posture:
1. mechanics and integrity are strong,
2. country concentration and continental imbalance are too high,
3. within-country placement shapes reveal synthetic template artifacts,
4. these jointly hold 1B below B/B+ until spatial priors and allocation shape are remediated.

## 2) Expected Statistical Posture (B/B+)

This section defines the target statistical shape for Segment 1B after remediation.  
Goal: preserve deterministic, auditable spatial generation while producing geographically credible synthetic site distributions.

### 2.1 Hard `B` gates (fail-closed)
1. Structural integrity remains perfect
- Row parity across key 1B outputs must hold.
- Duplicate key rate on site identity surfaces must be `0`.
- Coordinate validity (lat/lon in legal ranges) must be `100%`.
- Bundle and validation gates must remain PASS.

2. Country concentration must relax from dominance regime
- Country-site concentration Gini must be:
  - `<= 0.68` for `B`
  - `<= 0.60` for `B+`.
- Top-country concentration limits:
  - top 10% country share `<= 50%` for `B`, `<= 42%` for `B+`
  - top 5% country share `<= 33%` for `B`, `<= 27%` for `B+`
  - top 1% country share `<= 10%` for `B`, `<= 8%` for `B+`.

3. Global coverage breadth improves materially
- Minimum active-country coverage:
  - at least `85%` of configured eligible countries must have nonzero sites for `B`
  - at least `92%` for `B+`.
- Regional floor guardrails:
  - no major region (Africa, South America, Oceania, Asia, Europe, North America) should be near-empty when eligible countries exist in that region.
- Southern-hemisphere share floor:
  - site share in southern hemisphere `>= 12%` for `B`
  - `>= 18%` for `B+`, unless scenario policy explicitly constrains this.

4. Within-country representativeness improves
- For high-site countries (`C_large`), enforce:
  - no persistent strip/corridor collapse in coordinate spread diagnostics,
  - multi-cluster support where population and urban priors imply it.
- Proxy thresholds:
  - country-level spatial dispersion (bbox or convex-hull proxy) must increase versus baseline for previously collapsed countries.
  - median nearest-neighbor distance in `C_large` remains in plausible urban range while reducing extreme tail mass.

5. Nearest-neighbor tail is controlled
- Keep dense clustering signal, but reduce extreme sparse artifacts:
  - `p50` NN distance remains low (urban clustering preserved),
  - `p99/p50` ratio must contract versus baseline by at least `20%` for `B`, `35%` for `B+`.

### 2.2 `B` vs `B+` target table
| Axis | `B` target | `B+` target |
|---|---|---|
| Country concentration Gini | `<= 0.68` | `<= 0.60` |
| Top 10% country share | `<= 50%` | `<= 42%` |
| Top 5% country share | `<= 33%` | `<= 27%` |
| Top 1% country share | `<= 10%` | `<= 8%` |
| Eligible countries with nonzero sites | `>= 85%` | `>= 92%` |
| Southern hemisphere site share | `>= 12%` | `>= 18%` |
| NN tail contraction (`p99/p50` vs baseline) | `>= 20%` better | `>= 35%` better |
| Structural parity / validity / bundles | PASS required | PASS required |

### 2.3 Coupling expectations with downstream segments
1. Segment 2A timezone realism should improve.
- As country spatial representativeness improves, country-level timezone diversity in 2A should increase for multi-timezone countries.

2. Segment 3A and 3B temporal realism should stabilize.
- Better timezone geography in 2A should reduce downstream civil-time skew artifacts.

3. Segment 5A, 5B, 6A, and 6B interpretability should improve.
- Reduced spatial bias should reduce geography-induced distortions in allocation, cross-border behavior, and fraud targeting interpretation.

### 2.4 Cross-seed stability gates
Required seeds: `{42, 7, 101, 202}`.

1. All hard `B` gates must pass on all seeds.
2. Cross-seed CV thresholds for core metrics:
- `B`: `<= 0.30`
- `B+`: `<= 0.20`.
3. No seed should revert to dominance-collapse mode (for example Gini or top-share returning near baseline failure posture).

### 2.5 Interpretation of expected posture
For Segment 1B, `B/B+` means:
1. The pipeline remains mechanically perfect and deterministic.
2. Country mass is still realistically concentrated, but no longer dominated by a narrow set of countries.
3. Coverage breadth is credible for a synthetic global narrative.
4. Within-country geometry looks population-aware rather than template-collapsed.
5. Downstream timezone and temporal realism improve for causal reasons, not post-hoc corrections.

## 3) Root-Cause Trace

This section traces each observed 1B realism weakness to concrete mechanisms and ownership surfaces, so remediation addresses causes rather than symptoms.

### 3.1 Root-cause map (weakness -> mechanism -> locus)
| Weakness | Immediate mechanism | Primary locus | Secondary locus |
|---|---|---|---|
| Excessive country concentration (`Gini` and top-k too high) | Country mass allocation priors over-weight a narrow set of countries; weak balancing constraints | **1B country allocation policy** | 1A merchant-country composition |
| Europe-centric profile and weak southern/emerging-region coverage | Regional priors and eligibility mix skew toward Europe-like footprint; insufficient regional floor constraints | **1B regional weighting policy** | Scenario-level mix assumptions |
| Within-country stripe and corridor template artifacts | Coordinate synthesis relies on narrow geometric bands or limited sub-country support points | **1B intra-country placement policy** | Tile granularity and jitter mechanics |
| Heavy nearest-neighbor tail with sparse outliers | Mix of dense clusters plus under-constrained sparse placement in low-density areas | **1B tile-weight and sampling shape** | Jitter magnitude and tail controls |
| Realism shortfall despite structural PASS | Validation emphasizes mechanics (parity and bounds) but underweights representativeness gates | **1B validation contract scope** | Segment-grade rubric |

### 3.2 What is working correctly (not the bottleneck)
1. Structural pipeline integrity is strong (row parity, deterministic lineage, no key corruption).
2. Coordinate validity is strong (lat/lon ranges are legal).
3. Reproducibility controls are functioning.

Implication:
1. Segment 1B is not failing on mechanics; it is failing on distributional realism.

### 3.3 Primary cause: country allocation priors induce dominance regime
Evidence-linked mechanism:
1. Concentration metrics (Gini and top-k shares) indicate small-country-set dominance.
2. This pattern is consistent with strong allocation priors and weak anti-concentration constraints.
3. Once country counts are fixed this way, downstream intra-country logic cannot recover global balance.

Bounded conclusion:
1. The top realism bottleneck is country-level mass policy, not coordinate jitter or minor mapping details.

### 3.4 Secondary cause: regional balancing guardrails are too weak
Evidence-linked mechanism:
1. Visible continental imbalance (thin southern hemisphere, sparse Africa and South America).
2. This indicates lack of hard regional floor constraints in allocation objectives.
3. Even globally eligible scenarios can collapse into a narrow regional footprint without explicit guardrails.

Bounded conclusion:
1. Regional coverage defects are policy-structural, not random noise.

### 3.5 Tertiary cause: intra-country placement templates are too rigid
Evidence-linked mechanism:
1. Small-multiple plots show recurring narrow-band and split-corridor geometries.
2. That is typical when placement kernels are simplistic (few anchors or bands) relative to country complexity.
3. Resulting shapes look synthetic even when coordinates remain technically valid.

Bounded conclusion:
1. Intra-country representativeness needs richer multi-cluster kernels and stronger dispersion controls.

### 3.6 Quaternary cause: realism validation under-specifies representativeness
Evidence-linked mechanism:
1. Current segment PASS surfaces confirm structural correctness.
2. Realism defects still persisted to published output, so representativeness thresholds were not binding.
3. Without hard concentration and coverage gates, low-realism outputs can pass operational checks.

Bounded conclusion:
1. Validation must include explicit statistical realism gates, not only mechanical checks.

### 3.7 Responsibility split (to avoid mis-targeted fixes)
1. 1B policy owner surface
- Country mass priors
- Regional balancing constraints
- Intra-country placement kernels
- Tail controls for sparse placement

2. 1B implementation owner surface
- Faithful execution of policy shape
- Deterministic seeded sampling and provenance
- Metric emission for realism diagnostics

3. Validation owner surface
- Hard gates for concentration and coverage
- Cross-seed stability criteria
- Explicit fail-closed rules for realism threshold breaches

4. Upstream influence (non-primary)
- 1A merchant-country composition can amplify concentration, but 1B is still responsible for preventing extreme spatial collapse.

### 3.8 Root-cause conclusion
Segment 1B misses `B/B+` mainly because representativeness controls are too weak at the allocation-policy layer:
1. country-level mass is over-concentrated,
2. regional breadth lacks hard balancing floors,
3. intra-country placement kernels generate synthetic-looking geometry motifs,
4. realism thresholds are not yet enforced as hard validation gates.

This establishes remediation direction: strengthen 1B allocation and placement policy first, then harden realism validation so these failures cannot silently recur.

## 4) Remediation Options (Ranked + Tradeoffs)

Below is the ranked option set for 1B, ordered by expected impact on failing realism axes (`country concentration`, `regional breadth`, `within-country geometry`, `nearest-neighbor tail`) and by downstream leverage into `2A+`.

### Rank 1: Rebuild country allocation as a constrained sampler (highest impact)
1. Change:
- Replace raw country priors with a constrained draw that enforces:
- concentration-cap constraints (`Gini`, top-k share ceilings),
- minimum-breadth constraints (active-country floor and region-floor mass).
2. Why it ranks first:
- Most of 1B failure is macro-allocation shape; this directly attacks the largest error source.
3. Expected gain:
- Immediate movement on concentration and global coverage targets.
- Prevents few-country dominance from propagating downstream.
4. Tradeoffs:
- Hard constraints can feel less organic if set too tightly.
- Requires careful seed-stability tuning so runs do not become boundary-brittle.

### Rank 2: Add region-level balancing layer above country priors
1. Change:
- Use two-stage allocation:
- allocate mass by macro-region to target bands,
- then allocate countries within each region.
2. Why it ranks second:
- Fixes Europe-heavy collapse and southern/emerging under-coverage without overfitting country-level knobs.
3. Expected gain:
- Better continental realism and stronger global narrative plausibility.
4. Tradeoffs:
- Slight increase in policy complexity.
- If region bands are too rigid, output can look engineered rather than emergent.

### Rank 3: Replace rigid intra-country templates with mixture-of-kernels
1. Change:
- Move from stripe/corridor-like placement to a mixture:
- dense urban cores,
- secondary city clusters,
- controlled rural/sparse tail.
2. Why it ranks third:
- Directly targets the visible geometric artifacts in country panels.
3. Expected gain:
- Better micro-shape realism and less template repetition.
4. Tradeoffs:
- More parameters to calibrate per country class.
- Added diagnostic burden to prevent overfitting shape controls.

### Rank 4: Tail calibrator for nearest-neighbor distance (anti-pathology control)
1. Change:
- Add post-draw tail calibration guardrails for nearest-neighbor distance:
- cap pathological ultra-sparse tail mass,
- preserve realistic urban clustering.
2. Why it ranks fourth:
- Useful cleanup after macro-allocation and kernel fixes.
3. Expected gain:
- Reduces outlier-heavy sparse behavior that looks synthetic.
4. Tradeoffs:
- If overused, can flatten legitimate heterogeneity.
- Must be monitored so it does not hide upstream sampling defects.

### Rank 5: Upstream coupling control from 1A into 1B (stability option)
1. Change:
- Limit amplification from 1A merchant-country composition into 1B concentration.
- Add coupling limits or a reweighting bridge for stability.
2. Why it ranks fifth:
- Not primary root cause, but can reintroduce concentration drift if untreated.
3. Expected gain:
- Better cross-seed and cross-run stability of 1B realism.
4. Tradeoffs:
- Added coupling logic between segments.
- Requires clear ownership boundaries so 1A and 1B responsibilities do not blur.

### Rank 6: Upgrade validation from PASS mechanics to PASS realism gates
1. Change:
- Promote concentration, coverage, and shape diagnostics to fail-closed realism gates.
2. Why it ranks sixth:
- Does not fix generation directly, but prevents regression and false green states.
3. Expected gain:
- Sustained quality and auditable acceptance criteria.
4. Tradeoffs:
- More failed runs during tuning windows.
- Requires threshold governance and exception discipline.

### Recommended package for `B/B+`
1. Minimum high-confidence package:
- Rank 1 + Rank 2 + Rank 3 + Rank 6.
2. Optional hardening:
- Add Rank 4 for additional tail cleanup.
- Add Rank 5 only if 1A-driven drift remains after first rerun.

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)

## 6) Validation Tests + Thresholds

## 7) Expected Grade Lift (Local + Downstream Impact)
