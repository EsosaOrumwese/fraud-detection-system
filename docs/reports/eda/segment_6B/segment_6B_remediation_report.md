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
This section defines the target statistical posture for Segment 6B at two acceptance bands:
1. `B` = minimum credible synthetic realism for supervised fraud modeling.
2. `B+` = strengthened realism with stable stratification and reduced template artifacts.

### 2.1 Non-negotiable `B` gates (hard requirements)
1. **Truth surface must be non-degenerate.**
   - `LEGIT` share must be non-zero.
   - `is_fraud_truth_mean` must be within `0.02` to `0.30` for baseline scenario unless an explicitly versioned policy target states otherwise.
2. **Bank-view surface must be risk-stratified.**
   - Cramer’s V(`bank_view_outcome`, `merchant_class`) `>= 0.05`.
   - Cramer’s V(`bank_view_outcome`, `amount_bin`) `>= 0.05`.
   - `max_class_bank_fraud_rate - min_class_bank_fraud_rate >= 0.03`.
3. **Case timelines must be temporally valid.**
   - Negative case-gap rate `= 0`.
   - Case events are monotonic by `case_event_seq`.
   - Combined fixed-gap spike share (`3600s` + `86400s`) `<= 0.50`.

If any of these fail, Segment 6B cannot be graded `B` regardless of improvement elsewhere.

### 2.2 `B` vs `B+` expected posture by realism axis
| Realism axis | `B` target posture | `B+` target posture |
|---|---|---|
| Truth class balance | Non-collapsed truth labels; non-zero `LEGIT`; baseline fraud rate in target band | Seed-stable class balance; truth-label mix aligns tightly with policy target (`JS <= 0.03`) |
| Bank-view stratification | Measurable class and amount dependence (`V >= 0.05`) and visible class spread | Stronger, stable stratification (`V >= 0.08`) with clear geography/segment conditioning |
| Truth vs bank coherence | Fraud overlays produce materially higher bank-fraud probability than non-fraud | Calibrated conditional coherence by class/amount/geo/campaign with seed stability |
| Case temporal realism | No negative gaps; bounded fixed-spike dependence; valid lifecycle ordering | Broad delay support with reduced template spikes (`<= 0.25`) and realistic lag spread |
| Amount realism | No near-uniform 8-point collapse; meaningful heavy-tail expression | Context-conditioned spend surfaces by class/channel/geo with stable tail behavior |
| Event timing realism | Non-degenerate auth latency surface (median `0.3s` to `8s`, P99 `> 30s`) | Latency stratifies by risk/context and remains temporally coherent |
| Campaign realism | Campaign effects not limited to a single amount-uplift mechanism | Distinct campaign signatures (class/segment/geo/time) without trivial separability |
| Session/attachment realism | Non-trivial multi-arrival session structure appears | Rich but controlled session and linkage heterogeneity supporting sequence-level explainability |

### 2.3 Cross-seed stability expectations for realism claims
1. All critical metrics must pass at seeds `{42, 7, 101, 202}`.
2. Cross-seed coefficient of variation for primary gate metrics should be `<= 0.25` unless near-zero by construction.
3. No `PASS_WITH_RISK` unresolved on truth/bank/case surfaces.

### 2.4 Why this posture is required
1. Segment 6B is the final supervision surface used by the platform; realism defects here dominate downstream training behavior even when upstream segments look plausible.
2. A `B/B+` claim must therefore reflect both:
   - structural correctness (already mostly present), and
   - non-flat, context-sensitive statistical behavior (currently missing in key S4 and S2 surfaces).

## 3) Root-Cause Trace

## 4) Remediation Options (Ranked + Tradeoffs)

## 5) Chosen Fix Spec (Exact Parameter/Code Deltas)

## 6) Validation Tests + Thresholds

## 7) Expected Grade Lift (Local + Downstream Impact)
