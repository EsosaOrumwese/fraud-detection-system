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

## 3) Root-Cause Trace

## 4) Remediation Options (Ranked + Tradeoffs)

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)

## 6) Validation Tests + Thresholds

## 7) Expected Grade Lift (Local + Downstream Impact)
