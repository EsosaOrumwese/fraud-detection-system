# Segment 5A — Design vs Implementation Observations (Scenario & Intensity Surfaces)
Date: 2026-02-05  
Run: `runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92`  
Scope: Design intent vs implementation notes for Segment 5A (S0–S5) prior to deep statistical assessment.

---

## 0) Why this report exists
Segment 5A is the **traffic‑shape and intensity definition layer**. It turns the sealed Layer‑1 world into deterministic baseline and scenario‑adjusted intensity surfaces. This report captures:
1. **Design intent** (what 5A is supposed to produce).
2. **Implementation decisions** (what we actually built and enforced).
3. **Known deviations** that matter for realism interpretation.

This is a pre‑analysis report. It does not include deep statistical findings yet.

---

## 1) Design intent (what 5A should do)
1. **S0 — Gate & sealed inputs**  
   Verify upstream PASS gates (1A–3B) and seal all required 5A inputs/policies into `sealed_inputs_5A`.

2. **S1 — Merchant×Zone classification & base scale**  
   Deterministically assign `demand_class` and base scale for each merchant×zone using sealed policies.

3. **S2 — Weekly shape library**  
   Produce normalized class/zone weekly shapes on a fixed local‑week grid. Unit‑mass templates only.

4. **S3 — Baseline intensities**  
   Compose scale × shape to create baseline weekly intensities per merchant×zone.

5. **S4 — Scenario overlays**  
   Apply deterministic calendar and scenario overlays to baseline intensities to produce scenario surfaces.

6. **S5 — Validation & PASS gate**  
   Validate S0–S4 outputs and publish the authoritative 5A PASS bundle and `_passed.flag`.

---

## 2) Priority datasets (realism‑relevant)
Primary realism surfaces:
1. `merchant_zone_scenario_local_5A`
2. `merchant_zone_scenario_utc_5A` (if emitted)

Mechanism surfaces used to explain realism:
1. `merchant_zone_baseline_local_5A`
2. `class_zone_shape_5A`
3. `shape_grid_definition_5A`
4. `merchant_zone_profile_5A`
5. `merchant_class_profile_5A`
6. `merchant_zone_overlay_factors_5A`

Evidence surfaces (minimal realism impact):
1. `s0_gate_receipt_5A`, `sealed_inputs_5A`
2. `validation_bundle_5A` + `_passed.flag`

---

## 3) Implementation observations (what is actually done)
Based on `docs\model_spec\data-engine\implementation_maps\segment_5A.impl_actual.md`.

### 3.1 S0 — Gate & sealed inputs
Observed posture: strict and deterministic, with several corrective fixes.

Key implementation decisions:
1. **3B bundle validation is special‑cased.**  
   3B uses a `members` index schema, so S0 recomputes the digest using a dedicated members‑bytes law instead of the generic `files` law.

2. **Policy schema alignment was enforced.**  
   Multiple 5A policy files were reshaped or normalized to satisfy strict schema validation and dataset dictionary version rules.

3. **Optional input handling fixed.**  
   Missing optional inputs no longer abort sealing; they are recorded as optional‑missing.

4. **Layer‑1 schema refs were inlined** for sealed inputs, gate receipt, and scenario manifest validation.

Run outcome: `segment5a-s0` completes successfully after the fixes.

### 3.2 S1–S4 — Modelling states
No implementation‑map deviations were recorded for S1–S4.  
Assumption: these states follow the specs unless contradicted by data.

### 3.3 S5 — Validation
No implementation‑map deviations recorded.  
Assumption: validation follows contract checks as specified.

---

## 4) Design vs implementation deltas (material)
1. **3B bundle hashing law is bespoke** in 5A.S0 (members‑bytes), not the generic files‑index law.
2. **Policy payloads were corrected** to satisfy strict schemas and dictionary versioning (`version: v1`).
3. **Optional configs were authored later**, but **could not be resealed** in the same run due to `S0_OUTPUT_CONFLICT`.

---

## 5) Implications for realism assessment
1. **This run’s sealed inputs do NOT include optional configs**:  
   `zone_shape_modifiers_5A`, `overlay_ordering_policy_5A`,  
   `scenario_overlay_validation_policy_5A`, `validation_policy_5A`,  
   `spec_compatibility_config_5A`.

2. Realism signals must be interpreted in light of this omission.  
   Expect **less heterogeneity** in shapes and overlays than intended by the optional configs.

3. Because S0 is strict and deterministic, any realism issues seen in S1–S4 should be attributed to:
   - upstream data (1A–3B),
   - sealed policies/configs,
   - or the deterministic mechanics of the 5A states.

---

## 6) Next step
Proceed to statistical realism assessment starting from:
1. `merchant_zone_scenario_local_5A`  
2. Trace back into S3, S2, and S1 only when necessary to explain patterns.

---

## 7) Preliminary realism checks (A/B) — findings so far
Run scope: `runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer2\5A`

### 7.1 A) Why are most merchant×zone rows zero?
Join: `merchant_zone_profile_5A` ↔ `layer1/3A/zone_alloc` on  
`merchant_id + legal_country_iso + tzid`.

Key result: **zero volumes align exactly with zero sites**.
- Total rows: 16,528
- Rows with `zone_site_count > 0`: 2,158 (13.06%)
- Rows with `weekly_volume_expected > 0`: 2,158 (13.06%)
- Rows with sites but zero volume: 0
- Rows with volume but zero sites: 0
- `P(volume | sites) = 1.000`, `P(sites | volume) = 1.000`

Per‑merchant zone coverage (median / p90 / p99):
- `zones_total`: 12 / 42 / 64.3 (max 70)
- `zones_with_sites`: 2 / 5 / 10 (max 18)
- `sites_fraction`: 0.130 / 0.50 / 1.00

Explanation: The perfect alignment between “has sites” and “has volume” means
the zeros are not missing data or downstream artifacts; they are a direct
consequence of the upstream site allocation. In other words, 5A is honoring
the world allocation from Layer‑1 rather than inventing activity in empty
zones. The per‑merchant coverage numbers show that most merchants have activity
concentrated in a small subset of their zones, which is a realistic pattern if
merchants operate in a few core markets while still being mapped to a wider
zone universe.

### 7.2 B) Class distribution by merchant size tier
Size tiers are quartiles of `weekly_volume_total_expected`  
(`merchant_class_profile_5A`).

Bin edges: `[359.3, 2291.0, 4508.6, 8261.9, 1,285,623.9]`  
Counts per tier: micro 222, small 221, mid 221, large 222

Top classes per tier:
- **Micro:** consumer_daytime 62.2%, office_hours 12.2%, bills_utilities 8.6%, online_24h 8.6%
- **Small:** consumer_daytime 64.7%, online_24h 12.7%, fuel_convenience 5.9%, bills_utilities 5.4%
- **Mid:** consumer_daytime 62.9%, fuel_convenience 12.2%, online_24h 12.2%
- **Large:** consumer_daytime 50.5%, online_24h 25.2%, fuel_convenience 14.9%, online_bursty 3.6%

Explanation: The class mix shifts with size in a way that mirrors common
commercial structure: large merchants are more likely to be 24‑hour or fuel‑like
operations, while smaller merchants are dominated by daytime consumer and
office‑hours patterns. This indicates that size is not arbitrary noise; it has
an interpretable relationship with behavior class. The effect is not extreme
(consumer_daytime remains common across all tiers), which is what we want if we
expect overlap between classes but still some real structural difference.

### 7.3 A) Deeper zone‑sparsity mechanics (S2–S4)
Key diagnostics:
- `s2_country_zone_priors` **share_effective zero rate = 0.0000**  
  → priors do not hard‑zero zones.
- `s4_zone_counts` **zone_site_count zero rate = 0.8694**  
  → zero volumes trace to S4 allocation.
- `share_drawn` for zones with sites is near 1.0 (median ~0.981);  
  for zones without sites it is tiny (median ~1.74e‑07).
- `fractional_target` for zones without sites is tiny (median ~1.5e‑06; p99 ~0.283).
- Spearman correlation:  
  `weekly_volume_expected` vs `zone_site_count` (nonzero rows) = **0.8626**  
  `share_drawn` vs `zone_site_count` (nonzero) = **0.4831**

Geographic spread:
- Row‑level site share varies by country (examples):  
  FR 0.069, DE 0.093, US 0.112, IT 0.143, AU 0.428.
- TZIDs show high variance (e.g., Europe/Andorra 0.004 vs Europe/Berlin 0.366).

Concentration of volume across zones (per merchant, nonzero zones):
- `top1_share` mean 0.769 (p90 = 1.00)  
- `top3_share` mean 0.971 (p90 = 1.00)  
- Gini (merchants with ≥2 zones) mean 0.309 (p90 = 0.520)

Explanation: S2 priors do not zero anything; S4 does. This tells us that
sparsity is a policy‑driven allocation decision rather than a limitation of the
shape library or demand classing. The tiny `share_drawn` and
`fractional_target` values in zero‑site zones show that those zones were never
intended to receive activity. The strong correlation between site count and
volume confirms that, once a zone is “active,” its magnitude is governed by how
many sites are allocated there. Geographic variation shows this allocation
is not uniform; some countries/timezones are deliberately sparser than others.

### 7.4 A) One‑level deeper: priors → shares → counts
Share/prior alignment:
- Spearman corr(`share_drawn`, `share_effective`) = **0.7687**
- `sum(share_drawn)` matches `share_sum_country` per merchant+country  
  to floating‑point precision.
- Spearman corr(`alpha_sum_country`, share entropy) = **0.2603**  
  (higher alpha → more diffuse shares).

Fractional‑target rounding:
- `P(zone_site_count == floor(fractional_target)) = 0.8867`
- `P(zone_site_count == ceil(fractional_target)) = 0.1145`
- Extra allocation rate (zone_site_count > floor) = **0.1133**
- Extra allocations occur where `fractional_part` is high  
  (median 0.915 vs 2.17e‑06 when no extra).
- `max fractional_target` with zero sites = **0.5783**  
  `min fractional_target` with nonzero sites = **0.2376**
- Spearman corr(`zone_site_count`, `fractional_target`) = **0.5854**
- Spearman corr(`residual_rank`, `fractional_part`) = **−0.6391**
- `sum(fractional_target)` matches `zone_site_count_sum` per merchant+country  
  to floating‑point precision.

Site total conservation:
- `site_count` vs total allocated `zone_site_count_sum` (per merchant):  
  median diff 0, p90 0, p99 0 (exact for 99%+ merchants).

Explanation: The share‑drawn alignment with priors means the stochastic draw is
faithful to country‑zone priors, not arbitrary noise. The rounding diagnostics
show the exact mechanics: counts are mostly the floor of the fractional target,
with a minority receiving one extra site according to residual ranking. This is
why fractional targets below 1 almost always end up as zeros, and why totals
still conserve at the merchant‑country level. The mechanics are deterministic
and auditable, which is desirable for reproducibility and for explaining why
any given zone is active or inactive.

### 7.5 B) Deeper class‑size realism tests
Association strength:
- Chi‑square p = **2.18e‑15**, dof = 21  
  Cramér’s V = **0.210** (small‑to‑moderate association)
- Kruskal‑Wallis across classes on `weekly_volume_total_expected`:  
  p = **5.50e‑19**, epsilon_sq ≈ **0.108**  
  (class explains ~11% of volume variance)

Channel‑stratified association:
- `card_present`: n=727, Cramér’s V = 0.193, p = 4.62e‑11  
- `card_not_present`: n=159, Cramér’s V = 0.213, p = 0.0256

Explanation: The association is statistically strong and consistent across
channels, but not so strong that size alone determines class. This is a healthy
signal for realism: size influences behavior, yet overlap remains, which is
what we observe in real merchant populations. The Kruskal‑Wallis result shows
that volume distributions differ by class in a substantial way, supporting the
claim that classes are not just labels but reflect different operational
profiles.

### 7.6 A) Regression: volume drivers (nonzero rows)
Model: `weekly_volume_expected ~ zone_site_count + share_drawn + fractional_target`  
Rows: 2,158 (nonzero volume only)

Multicollinearity diagnostic:
- Spearman corr(`zone_site_count`, `fractional_target`) = **0.996**
- VIFs ~ **86,000** for both predictors
- Condition number ~ **605**

Raw‑scale OLS (HC3 robust):
- R² ≈ **0.956**
- `zone_site_count` and `fractional_target` dominate absolute volume,  
  but are not separately identifiable due to collinearity.
- `share_drawn` adds negligible raw‑scale explanatory power.

R² breakdown (raw):
- `zone_site_count` alone: **0.956**
- `fractional_target` alone: **0.956**
- `share_drawn` alone: **0.004**
- Full model: **0.956**

Log‑scale (log1p) sensitivity:
- `zone_site_count` positive and significant (p ≈ 0.028)
- `share_drawn` strongly positive (p ≪ 1e‑6)
- `fractional_target` negative (p ≈ 0.031)  
  (interpreted with caution due to collinearity)

R² breakdown (log1p):
- `zone_site_count` alone: **0.095**
- `fractional_target` alone: **0.095**
- `share_drawn` alone: **0.283**
- Full model: **0.356**

Explanation: The multicollinearity confirms that `zone_site_count` and
`fractional_target` encode essentially the same signal (pre‑rounding vs
post‑rounding). On the raw scale, these allocations explain nearly all variance
in weekly volume, meaning total magnitude is fundamentally a site‑allocation
problem. On the log scale, `share_drawn` becomes the driver: it explains how
activity is distributed across the active zones once the total scale is set.
This separation—allocation controls totals, shares control relative intensity—
is coherent and interpretable.

### 7.7 A) Country‑level sparsity elasticity
Country‑level sparsity uses `row_site_share = rows_with_sites / rows`.

Key finding: `share_sum_country` is effectively constant:
- variance ≈ **5.93e‑33**, std ≈ **5e‑17**  
→ does not explain cross‑country sparsity.

Correlations:
- `row_site_share` vs `alpha_sum_country_mean`:  
  Pearson **−0.473**, Spearman **−0.600**
- `row_site_share` vs `share_sum_country_mean`:  
  Pearson **0.112**, Spearman **0.066** (negligible)

Logit model (country level):
`logit(row_site_share) ~ log(alpha_sum_country)`  
- coefficient **−3.356**, p = **0.010**

Explanation: Because `share_sum_country` is effectively constant, it cannot be
an explanatory lever for cross‑country sparsity in this run. The negative
relationship with `alpha_sum_country` implies that countries with higher alpha
are assigned activity more conservatively across zones. Interpreting the logit
coefficient, a 1% increase in alpha corresponds to roughly a 3.3% decrease in
the odds that a zone is active, which is a sizable elasticity.

### 7.8 A) Regression refit (remove multicollinearity)
Refit on nonzero rows, dropping one of the collinear predictors.

Raw scale:
1. `weekly_volume_expected ~ zone_site_count + share_drawn`  
   - `zone_site_count`: **+484.6**, p < 0.001  
   - `share_drawn`: ns  
   - R² = **0.956**
2. `weekly_volume_expected ~ fractional_target + share_drawn`  
   - `fractional_target`: **+484.5**, p < 0.001  
   - `share_drawn`: ns  
   - R² = **0.956**

Explanation (raw): Once the collinearity is removed, the site‑allocation term
is stable and highly significant, while `share_drawn` remains non‑significant.
This reinforces that, at absolute scale, volume is essentially proportional to
the site allocation decision.

Log scale (log1p):
1. `log1p(weekly_volume_expected) ~ zone_site_count + share_drawn`  
   - `share_drawn`: **+1.63**, p ≪ 1e‑6  
   - `zone_site_count`: ns  
   - R² = **0.354**
2. `log1p(weekly_volume_expected) ~ fractional_target + share_drawn`  
   - `share_drawn`: **+1.63**, p ≪ 1e‑6  
   - `fractional_target`: ns  
   - R² = **0.354**

Explanation (log): After normalization, the magnitude of `share_drawn` becomes
the dominant signal for relative intensity, while site allocation contributes
little. This is the same story as in 7.6, but now with stable coefficients that
avoid the collinearity instability.

### 7.9 A) Country elasticity (merchant‑level sparsity)
Robustness check using per‑merchant sparsity:
`mc_site_share = zones_with_sites / zones_total` (merchant‑country),  
aggregated to country mean.

Correlations:
- `mc_site_share_mean` vs `alpha_sum_country_mean`:  
  Pearson **−0.473**, Spearman **−0.602**
- `mc_site_share_mean` vs `share_sum_country_mean`:  
  Pearson **0.112**, Spearman **0.068** (negligible)

Logit model:
`logit(mc_site_share_mean) ~ log(alpha_sum_country)`  
- coefficient **−3.356**, p = **0.010**

Explanation: Using merchant‑level sparsity removes the possibility that the
row‑level result is driven by countries with many zones or merchants. The same
negative elasticity appears, which confirms the relationship is robust to how
sparsity is summarized. This strengthens the case that `alpha_sum_country` is
the primary driver of country‑level sparsity in the current configuration.
