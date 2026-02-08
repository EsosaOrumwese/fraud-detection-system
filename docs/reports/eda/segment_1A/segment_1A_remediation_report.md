# Segment 1A Remediation Report

Date: 2026-02-07
Scope: Statistical remediation planning for segment 1A toward target grade `B/B+`.
Status: Planning only. No fixes implemented in this document.

---

## 1) Observed Weakness

For segment `1A`, the observed weaknesses are concentrated in population-shape realism, geographic realism, identity semantics, and stochastic variance realism.

1. Missing single-site merchant base tier (major)
- `outlets_per_merchant` has `min=2`, so no merchant exists at `outlet_count=1`.
- `single_vs_multi_flag` is effectively always `True` in this run.
- Why this is a weakness:
the most common merchant type in normal economies (single-site merchants) is absent, which structurally biases downstream layers toward chain-like behavior.

2. Over-global candidate universe with weak realization coupling (major)
- Candidate breadth is near-saturated (`median ~38` candidates out of `39` countries).
- Actual foreign membership realization is sparse for most merchants (low realization ratio, weak candidate-to-membership coupling).
- Why this is a weakness:
the generator encodes "almost everyone could expand everywhere," while realized behavior says "most do not," producing a policy posture that looks internally inconsistent for baseline realism.

3. Elevated home-vs-legal mismatch across broad merchant sizes (major)
- Share of rows with `home_country_iso != legal_country_iso` is high (about `38.6%` in the assessment run).
- The mismatch is not isolated to very large/global merchants; it appears broadly across size buckets.
- Why this is a weakness:
for baseline synthetic commerce, legal-domicile divergence should be concentrated in specific enterprise strata, not distributed this widely.

4. Site identity semantics create downstream ambiguity (moderate-major)
- Duplicate merchant-site pairs are material (pair-level duplicate exposure is non-trivial; merchant exposure is broad).
- Duplicates are primarily cross-country reuse patterns.
- Why this is a weakness:
if downstream consumers assume site IDs are globally unique physical locations, joins/features can silently encode wrong semantics.

5. NB dispersion block is statistically weak (major; stochastic realism)
- Implied merchant-level `phi` is near-constant around `~12` with extremely low spread (`CV(phi)~0.00053`, `P95/P05~1.00004`).
- Channel/GDP effects in dispersion are effectively flat at merchant level.
- Why this is a weakness:
mean-level heterogeneity exists, but variance-level heterogeneity is almost absent; synthetic counts can look too regular once conditioned on mean.

6. Missing approved outputs reduce auditability and controllability (moderate)
- Expected artifacts such as `s3_integerised_counts`, `s3_site_sequence`, `sparse_flag`, `merchant_abort_log`, and `hurdle_stationarity_tests` are absent in the assessed output set.
- Why this is a weakness:
some realism properties cannot be fully verified or monitored run-over-run, even where data may look plausible.

7. Net observed posture for `1A`
- Strong signal:
heavy-tail outlet concentration is present and directionally plausible.
- Weak signal:
base-tier absence (no single-site), over-global candidate design, high domicile mismatch, and near-constant dispersion dominate realism risk.
- Downstream implication:
these weaknesses propagate into `2A/2B` topology and weighting behavior, then into `3A/3B`, and eventually shape `5A/5B/6A/6B` event realism.

## 2) Expected Statistical Posture (B/B+)

## 3) Root-Cause Trace

## 4) Remediation Options (Ranked + Tradeoffs)

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)

## 6) Validation Tests + Thresholds

## 7) Expected Grade Lift (Local + Downstream Impact)
