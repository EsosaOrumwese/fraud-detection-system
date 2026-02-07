# Engine Realism — Step 3 Hypothesis and Acceptance Plan
Date: 2026-02-07  
Run baseline: `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92`  
Scope: One-to-one remediation hypotheses and statistical acceptance tests for every `Critical/High` gap in Step 2.  
Status: Planning and diagnosis only. No implementation changes are made in this step.

---

## 0) Objective
Raise engine realism from the current strict calibrated `D+` to at least `B/B+` by:
- removing structural defects in final truth surfaces (`6B`);
- restoring heterogeneity and causal structure in upstream substrate (`3B`, `6A`, `3A`, `2B`, `1A`);
- adding measurable statistical gates that fail closed when realism regresses.

This document is exhaustive against Step 2 and is keyed by the same gap ids.

---

## 1) Exit Criteria for Step 3
Step 3 is complete when all items below are true:
1. Every Step 2 `Critical/High` gap has a mapped remediation hypothesis.
2. Every gap has at least one numeric acceptance threshold.
3. Every gap has at least one verification test with pass/fail semantics.
4. Priority order is explicit for execution sequencing.
5. A run-gating protocol is defined for pre/post comparison.

---

## 2) Priority Order (Execution Waves)
`Wave 0` must pass before anything else:
1. `1.1` 6B truth collapse
2. `1.2` 6B bank-view uniformity
3. `1.3` 6B case timeline invalidity

`Wave 1` high-propagation substrate:
1. `1.4` and `1.5` 3B edge uniformity and settlement coherence
2. `2.12` to `2.15` 6A graph realism and fraud-role propagation
3. `2.7`, `2.8`, `2.18`, `2.19` 2B routing and temporal variability
4. `2.9`, `2.10`, `2.20` 3A prior/escalation/sampling realism

`Wave 2` upstream shaping and timing correctness:
1. `2.1` to `2.4` 1A base tier and coefficient realism
2. `2.5`, `2.6`, `2.17` 1B/2A geography-timezone realism
3. `2.11` 5B DST correctness
4. `2.16` and `2.21` 6B amount surface and 3B classification evidence

---

## 3) Critical Gap Plan (1:1)

### 1.1) 6B — Truth labels collapse to 100% fraud (Critical)
Hypothesis:
- Truth mapping key is under-specified (`fraud_pattern_type` only), causing class collapse.

Remediation surface:
- Policy contract: truth mapping must resolve by `(fraud_pattern_type, overlay_anomaly_any)`.
- Implementation contract: no key collisions in truth-map loading.

Acceptance tests:
- `LEGIT` share must be non-zero and policy-consistent.
- `is_fraud_truth_mean` must satisfy `0.02 <= rate <= 0.30` for baseline scenario unless policy target says otherwise.
- Jensen-Shannon distance between observed label mix and policy target <= `0.05`.

---

### 1.2) 6B — Bank-view outcomes nearly uniform across strata (Critical)
Hypothesis:
- Bank-view label generation is globally mixed and weakly conditioned on risk covariates.

Remediation surface:
- Policy: conditional bank-view priors by class/channel/amount/cross-border.
- Implementation: conditional sampling path wired to those covariates.

Acceptance tests:
- Cramer’s V for bank-view outcome vs `merchant_class` >= `0.05`.
- Cramer’s V for bank-view outcome vs `amount_bin` >= `0.05`.
- Max minus min bank-fraud rate across major classes >= `0.03`.

---

### 1.3) 6B — Case timelines show invalid temporal gaps (Critical)
Hypothesis:
- Case event timestamps are generated from fixed delays without monotonic timeline enforcement.

Remediation surface:
- Policy: delay distributions with realistic spread and ordering constraints.
- Implementation: enforce monotonic event time per case sequence.

Acceptance tests:
- Negative case-gap rate = `0`.
- Fraction of exact fixed-gap spikes (`3600` and `86400` seconds combined) <= `0.50`.
- Case-duration support includes at least `10` unique duration bins after rounding to minutes.

---

### 1.4) 3B — Edge catalogue is structurally uniform (Critical)
Hypothesis:
- Fixed `edge_scale` and equal per-edge weights remove merchant-level network heterogeneity.

Remediation surface:
- Policy: edge count and weight-concentration priors by merchant profile.
- Implementation: merchant-conditional edge-size and non-uniform edge weights.

Acceptance tests:
- Merchant edge-count coefficient of variation >= `0.25`.
- Median edge-weight Gini per merchant >= `0.20`.
- At least `30%` of merchants with top-edge share >= `0.10`.

---

### 1.5) 3B — Settlement coherence is weak (Critical)
Hypothesis:
- Settlement country has weak influence relative to global edge-country weighting.

Remediation surface:
- Policy: explicit settlement-country uplift parameters.
- Implementation: settlement-aware edge-country draw logic.

Acceptance tests:
- Median settlement-country edge share uplift >= `+0.05` above global baseline.
- Median anchor distance to settlement country reduced by at least `30%` from baseline.
- Share of merchants with zero settlement overlap <= `0.30`.

---

## 4) High Gap Plan (1:1)

### 2.1) 1A — Missing single-site merchant tier (High)
Hypothesis: Base generator always emits multi-site merchants.
Acceptance tests:
- Single-site merchant share in `0.25` to `0.60`.
- `min outlets = 1`.

### 2.2) 1A — Home/legal country mismatch is too broad (High)
Hypothesis: Candidate-selection logic over-permits legal-country divergence.
Acceptance tests:
- Home/legal mismatch in `0.05` to `0.20`, unless policy target overrides.
- Mismatch monotonic with merchant-size tier if policy encodes expansion tiers.

### 2.3) 1A — Candidate universe is over-globalized (High)
Hypothesis: Candidate cap and rule ladder produce near-global candidate sets.
Acceptance tests:
- Candidate-country median <= `12`.
- Realization ratio median >= `0.15`.
- Candidate breadth IQR not degenerate (IQR >= `4`).

### 2.4) 1A — Dispersion heterogeneity collapsed (High)
Hypothesis: Hand-authored `phi` coefficients are effectively flat.
Acceptance tests:
- Implied `phi` CV in `0.10` to `0.35`.
- `P95/P05` implied-phi ratio >= `1.5`.
- KS test rejects equality vs baseline-flat shape at `p < 1e-6`.

### 2.5) 1B — Global placement imbalance (High)
Hypothesis: Region weights over-concentrate Europe.
Acceptance tests:
- Region share error per major region <= `5` percentage points from policy target.
- Country HHI for site counts reduced by at least `20%` from baseline.

### 2.6) 2A — Timezone support per country compressed (High)
Hypothesis: Assignment fallbacks plus sparse geometry collapse to singleton tzids.
Acceptance tests:
- Countries with exactly one tzid <= `50%`.
- Top-1 tz share median <= `0.90`.
- Multi-tz countries with entropy > `0.3` must be >= `20`.

### 2.7) 2B — Site weights are behaviorally flat (High)
Hypothesis: Uniform site weighting blocks realistic hub effects.
Acceptance tests:
- Top-1 site share median >= `0.20`.
- Top-1 minus top-2 share median >= `0.05`.
- Weight entropy variance across merchants >= `0.05`.

### 2.8) 2B — Temporal heterogeneity absent (High)
Hypothesis: Single global `sigma_gamma` yields one volatility regime.
Acceptance tests:
- Unique merchant-level sigma bins >= `5`.
- Sigma CV across merchants >= `0.20`.
- Daily coefficient-of-variation of routed mass differs across classes by >= `0.05`.

### 2.9) 3A — Prior dominance suppresses diversity (High)
Hypothesis: Extreme alpha priors dominate posterior shares.
Acceptance tests:
- Country-level top-1 share median <= `0.80`.
- Merchant-country entropy median >= `0.25`.
- Share of merchant-country pairs with top-1 >= `0.95` <= `0.40`.

### 2.10) 3A — Escalation intent vs outcome mismatch (High)
Hypothesis: Escalation thresholds are not aligned with observed site/zone regimes.
Acceptance tests:
- Escalated pairs with multi-zone support >= `0.30`.
- Escalation uplift on effective-zone count >= `+0.5` zones vs non-escalated matched bucket.

### 2.11) 5B — DST mismatch persists (High)
Hypothesis: Local-time conversion applies fixed offsets in DST windows.
Acceptance tests:
- DST mismatch rate <= `0.1%`.
- Absolute local-time offset error set restricted to `{0}` for supported tzids.
- No tz/date cell with mismatch rate > `1%`.

### 2.12) 6A — IP type distribution drifts from priors (High)
Hypothesis: IP assignment priors are not respected in realized composition.
Acceptance tests:
- Per-region IP-type share error <= `5` percentage points.
- Residential global share in `0.35` to `0.60` unless policy target differs.
- Chi-square goodness-of-fit vs prior distribution `p >= 0.05` in major regions.

### 2.13) 6A — Sparse device→IP linkage (High)
Hypothesis: `p_zero`/lambda settings over-sparsify linkage.
Acceptance tests:
- Devices with >=1 IP >= `0.50`.
- Mean IPs per linked device >= `1.2`.
- Linked graph giant-component share >= `0.40` (device+IP bipartite projection).

### 2.14) 6A — Account cap semantics violated (High)
Hypothesis: `K_max` declared but not enforced in allocation.
Acceptance tests:
- Breach rate of `K_max` <= `0.1%`.
- Max overshoot <= `+1` where stochastic rounding is allowed.

### 2.15) 6A — Fraud-role propagation weak (High)
Hypothesis: Fraud roles sampled independently across entity types.
Acceptance tests:
- `P(risky_device | risky_party) - P(risky_device)` >= `0.15`.
- `P(risky_account | risky_party) - P(risky_account)` >= `0.15`.
- Mutual information between linked risk roles >= `0.02`.

### 2.16) 6B — Amount/timing surfaces are mechanical (High)
Hypothesis: Hash-indexed amount selection and zero-latency eventing produce rule-flat outputs.
Acceptance tests:
- Distinct amounts per merchant median <= `6` and >= `3`.
- Amount-share entropy varies across merchant classes (CV >= `0.10`).
- Auth response latency median in `0.3s` to `8s`, with long-tail P99 > `30s`.

### 2.17) 2A — Non-representative country->tzid outcomes (High)
Hypothesis: Fallback precedence creates behaviorally implausible country/tz mappings.
Acceptance tests:
- Implausible country->tzid pair rate <= `0.5%` of site rows.
- Country singleton auto-override rate <= `10%` unless country is truly single-tz.
- Nearest-fallback outside threshold rate <= `1%`.

### 2.18) 2B — Excessive single-tz daily dominance (High)
Hypothesis: Dominant base shares plus low day-variance force daily top-1 collapse.
Acceptance tests:
- Merchant-days with `max p_group >= 0.9` <= `25%`.
- Merchant-days with `max p_group <= 0.7` >= `30%`.

### 2.19) 2B — Panel/roster realism shallow (High)
Hypothesis: Fully rectangular roster suppresses lifecycle variation.
Acceptance tests:
- Merchant-day coverage not fully rectangular, missingness in `5%` to `25%`.
- Daily arrival count variance-to-mean ratio > `1` for at least `40%` merchants.

### 2.20) 3A — Sampling adds little merchant variance (High)
Hypothesis: S3 stochasticity is compressed by S4 integerization.
Acceptance tests:
- Variance retention after S4 integerization >= `60%` of S3 pre-integer variance.
- Merchant-country distinct share profiles count increased by >= `50%` vs baseline.

### 2.21) 3B — Classification evidence is flat (High)
Hypothesis: Binary MCC/channel gate is too coarse for realistic evidence diversity.
Acceptance tests:
- Within MCC-channel pair variance in classification score > `0` for >= `50%` pairs.
- At least `3` independent evidence families contribute non-trivial lift (each lift >= `0.02` absolute risk delta).

---

## 5) Statistical Gate Protocol (Applied to Every Remediation Run)
Run-gating method:
1. Keep fixed seeds for comparability: baseline seed `42` plus robustness seeds `{7, 101, 202}`.
2. Compute all acceptance metrics at segment level and engine aggregate.
3. Fail run if any `Critical` gate fails or if more than `2` `High` gates fail.
4. Track deltas against Step 1 baseline and require directional improvement for all touched gaps.

Required test families:
- Distribution fit: KS, Chi-square, Jensen-Shannon.
- Association strength: Cramer’s V, mutual information, odds-ratio deltas.
- Concentration: Gini, HHI, top-k share.
- Temporal validity: monotonicity checks, gap-sign checks, DST offset checks.

---

## 6) B/B+ Readiness Criteria
Minimum readiness to claim synthetic realism at `B/B+`:
1. All `Critical` gates passing for two consecutive runs.
2. At least `85%` of `High` gates passing.
3. No segment below calibrated `C+`, and both `6A` and `6B` at least `B-`.
4. `6B` truth/bank/case surfaces demonstrate non-degenerate class balance, stratification, and temporal validity.

---

## 7) Step-3 Outcome
This step defines the exhaustive diagnosis-to-remediation bridge:
- one-to-one hypotheses from Step 2;
- numeric acceptance thresholds;
- run-gating protocol for objective pass/fail realism claims.

Next step (Step 4) should convert this plan into an execution backlog:
- policy edits and implementation tasks mapped to specific files;
- per-task expected metric movement;
- test harness scripts and CI-style realism gates.
