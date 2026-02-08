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

## 4) Remediation Options (Ranked + Tradeoffs)

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)

## 6) Validation Tests + Thresholds

## 7) Expected Grade Lift (Local + Downstream Impact)
