# Segment 6B Remediation Report

Date: 2026-02-07
Scope: Statistical remediation planning for segment 6B toward target grade `B/B+`.
Status: Planning only. No fixes implemented in this document.

---

## 1) Observed Weakness
This section captures the observed statistical weaknesses in Segment 6B exactly as established in the Segment 6B analytical report. These are the issues remediation must address before 6B can be credibly graded in the `B/B+` band.

### 1.1 Critical blockers (must be fixed first)
1. **Truth-label collapse (critical):** `is_fraud_truth` collapses to a single class (`True`) at full-run scale, with no usable negative class (`LEGIT`) in the training surface.
   - Why this is a blocker: without a negative class, discrimination, calibration, and threshold analysis are structurally invalid.
2. **Bank-view stratification collapse (critical):** bank-view fraud rate is effectively flat (about `0.155`) across class, amount, geography, merchant size, and segment, with near-zero association strength in the report's stratification tests.
   - Why this is a blocker: the bank-view outcome surface behaves like a near-constant allocator, not a risk-sensitive decision surface.
3. **Case-timeline temporal invalidity (critical):** sampled case gaps include non-monotonic and templated values (for example negative and fixed spikes around `-82801`, `0`, `1`, `3599`, `3600`, `82800`) and durations concentrated on fixed values (about `3600s` and `86401s`).
   - Why this is a blocker: case lifecycle timing features become unreliable for realism and downstream model validation.

### 1.2 High-severity realism weaknesses
1. **Amount distribution is over-discretized and near-uniform (high):** flow amounts are concentrated in 8 fixed price points with near-equal shares (~12.5% each), with weak heavy-tail expression relative to policy intent.
   - Impact: spend intensity lacks realistic heterogeneity; amount-based explainability becomes mechanically driven.
2. **Timing surface is over-deterministic (high):** event and flow timestamps are almost perfectly aligned with no meaningful latency surface.
   - Impact: operational timing signals (auth latency, async behavior, delay effects) are largely absent.
3. **Fraud overlay mechanics are narrow (high):** fraud behaves primarily as a bounded amount uplift plus tag assignment, with weak evidence of campaign-specific class/segment/geo targeting richness.
   - Impact: fraud-vs-legit separability can become too shortcut-like (single-feature separation) instead of context-driven.

### 1.3 Medium-severity structural realism limitations
1. **Session realism is thin (medium):** sessionization is close to identity behavior, with many single-arrival / near-zero-duration sessions in the observed posture.
   - Impact: sequence-level behavioral realism is limited.
2. **Attachment/connectivity realism is under-expressive (medium):** entity-linkage surfaces are structurally clean but comparatively under-connected for richer behavior-network realism.
   - Impact: graph-derived behavioral and fraud features are weaker than expected for production-like pattern learning.
3. **Geographic realism is imbalanced (medium):** cross-border is uniformly high while risk outcomes remain largely unstratified by geography.
   - Impact: geography contributes less explanatory signal than expected in realistic fraud ecosystems.

### 1.4 Practical interpretation for remediation
1. Segment 6B is **mechanically consistent** but **statistically non-credible** for supervised fraud modelling in its current state.
2. The highest-impact weaknesses sit in **S4 truth/bank/case outputs**, not in row-count parity mechanics.
3. Remediation should therefore prioritize restoring label validity and risk stratification first, then improving amount/time/campaign behavior depth.

## 2) Expected Statistical Posture (B/B+)

## 3) Root-Cause Trace

## 4) Remediation Options (Ranked + Tradeoffs)

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)

## 6) Validation Tests + Thresholds

## 7) Expected Grade Lift (Local + Downstream Impact)
