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

---

## 8) C) Temporal Shape Realism

### 8.1 Shape normalization (class×zone)
Finding: Every `(demand_class, zone)` shape sums to **1.0** with no deviations
above numerical tolerance.

Explanation: This matters because the shape library is supposed to be a
probability distribution over the weekly grid. Exact normalization means the
library is internally consistent and any realism issues must come from the
shape *content*, not from mass leakage or scaling errors.

### 8.2 Class temporal patterns (per‑zone averages)
Per‑zone averages across all zones show clear, interpretable patterns:

```
demand_class         weekend_share  night_share  open_hours_share  peak_hour  peak_to_mean
bills_utilities            0.146        0.044          0.665            10        3.82
consumer_daytime           0.264        0.057          0.480            11        2.68
evening_weekend            0.445        0.362          0.023            20        7.42
fuel_convenience           0.267        0.078          0.243             7        3.22
office_hours               0.093        0.041          0.736            10        4.34
online_24h                 0.311        0.479          0.115             1        2.11
online_bursty              0.416        0.151          0.263            12        6.45
travel_hospitality         0.392        0.075          0.260             9        3.37
```

Explanation: The classes are clearly differentiated in a realistic way:
`office_hours` is strongly weekday/daytime, `evening_weekend` is night‑heavy
with a late‑evening peak, and `online_24h` is the flattest profile with the
largest night share. This indicates the class labels correspond to distinct
behavioral rhythms rather than arbitrary templates.

### 8.3 Baseline construction integrity
Finding: For every nonzero merchant‑zone, the baseline intensities exactly
sum to weekly expected volume (`sum(lambda_local_base) = weekly_volume_expected`),
with **no clipping** and near‑zero error against the class shape.

Explanation: This confirms that 5A’s baseline is a clean “scale × shape”
composition. The baseline does not distort totals or shapes, so any realism
issues must come from the inputs or the shape library itself, not from
implementation artifacts in S3.

---

## 9) D) Scenario and Overlay Realism

### 9.1 Scenario calendar structure
Finding: 2,000 events over 2026‑01‑01 to 2026‑04‑01.
Event mix: PAYDAY (1157), HOLIDAY (786), OUTAGE (54), CAMPAIGN (3).
No global or merchant‑specific events; mostly country + class scoped.
Amplitude ranges: median **0.85**, min **0.05**, max **1.03**;
peak amplitudes median **1.25**, max **~1.60**.

Explanation: The event calendar is dense but not chaotic. It emphasizes
recurrent effects (paydays, holidays) and keeps shocks bounded. The amplitude
range is plausible: mild suppressions and moderate peaks rather than extreme
distortions.

### 9.2 Overlay factor distribution
Finding: ~90% of buckets have factor exactly 1.0, ~6.5% > 1.0, ~3.6% < 1.0,
with min **0.0325** and max **1.5975**.

Explanation: Overlays are sparse and bounded, which is consistent with
realistic calendars where most time is baseline and only specific windows are
perturbed. The factor range suggests modest amplification/suppression rather
than runaway shocks.

### 9.3 Scenario local consistency (baseline × overlay)
Finding: When aligning the local horizon with each timezone’s offset at the
scenario start (2026‑01‑01T00:00Z), the scenario surface matches
`baseline × overlay` almost exactly (MAE ≈ 0.033; only ~0.7% of rows deviate
> 1e‑6). The residual mismatch is consistent with DST shifts over the 90‑day
horizon.

Explanation: This confirms the scenario surface is mechanically correct once
time alignment is handled properly. The remaining mismatch is small and
expected in a multi‑timezone horizon that crosses DST boundaries.

### 9.4 Local ↔ UTC conversion
Finding: Total intensity per merchant‑zone is conserved exactly between local
and UTC surfaces (MAE = 0, max error = 0).

Explanation: UTC conversion preserves total mass, which means the conversion
logic is correct and does not introduce drift.

### 9.5 DST‑driven residuals (D3 confirmation)
Finding: The remaining mismatches in the scenario‑vs‑baseline×overlay check are
almost entirely explained by DST shifts within the 90‑day horizon.

Evidence:
- TZs with **no DST shift** (0h):  
  frac_mismatch ≈ **0.0003**, MAE ≈ **0.0011**, max_err ≈ **0.19**
- TZs with **+1h DST shift**:  
  frac_mismatch ≈ **0.0178**, MAE ≈ **0.0773**, max_err ≈ **228.48**
- Spearman corr(`frac_mismatch`, DST shift) = **0.62**
- Highest mismatch TZIDs are all DST‑shifting North American zones
  (e.g., America/New_York, America/Chicago, America/Los_Angeles).

Explanation: When the local horizon crosses a DST boundary, the fixed offset
used to align weekly baseline buckets becomes slightly misaligned for part of
the horizon. This introduces small local mismatches but does not affect total
mass. The pattern is isolated to DST‑shifting timezones, which confirms DST is
the root cause rather than a structural bug.

---

## 10) Policy‑Target Alignment (A/B realism targets)

### 10.1 Observed vs target summary (run subset, 886 merchants)
Targets from `config/layer2/5A/policy/merchant_class_policy_5A.v1.yaml`:
- `max_class_share`: **0.55**  
- `min_nontrivial_classes`: **6**  
- `min_class_share_for_nontrivial`: **0.02**  
- `max_single_country_share_within_class`: **0.35**

Observed (segment 5A):
- `max_class_share`: **0.600** (`consumer_daytime`) → **exceeds target**  
- `min_nontrivial_classes`: **8** → meets target  
- `min_class_share_for_nontrivial`: **0.021** → meets target  
- `max_single_country_share_within_class`: **0.532** (`fuel_convenience`, DE) → **exceeds target**  
  Additional above‑target classes:  
  `bills_utilities` 0.457 (DE), `consumer_daytime` 0.412 (DE), `online_bursty` 0.364 (DE)

### 10.2 Suggested edits to align with targets

**A) Reduce `consumer_daytime` share to ≤ 0.55**  
Main driver is `card_present + sector=other` in MCC mapping.  
Small, targeted remap of travel‑like MCCs reduces this share:

Edit `config/layer2/5A/policy/merchant_class_policy_5A.v1.yaml`  
`mcc_sector_map` (change `other → travel_hospitality` for these MCCs):
```
4011  # Railroads
4119  # Local/commuter transport
4214  # Motor freight
4215  # Courier services
4789  # Transportation services (NEC)
7033  # Campgrounds / RV parks
```

Expected effect (run subset):
- `consumer_daytime` **0.600 → ~0.542**  
- `travel_hospitality` **0.025 → ~0.084**  
All classes remain under `max_class_share = 0.55`.

**B) Reduce max single‑country share to ≤ 0.35**  
This is driven primarily by the upstream country distribution, not the class
decision tree. Adjust the country generation weights to flatten the tail:

Edit `config/layer1/1A/ingress/transaction_schema_merchant_ids.bootstrap.yaml`  
```
home_country:
  floor_weight: 0.20   # was 0.10
  bucket_base: 1.5     # was 2.0
  min_distinct: 80     # was 50
```

Expected effect: lower dominance of any single country within each class, which
brings `max_single_country_share_within_class` closer to the 0.35 target.

### 10.3 Alternative (accept current realism)
If the current distributions are acceptable, you can instead adjust targets:
```
max_class_share: 0.62
max_single_country_share_within_class: 0.55
```

---

## 11) Policy‑Posture for C/D (Temporal Shapes + Scenario Overlays)

### 11.1 C — Temporal shape realism is *explicitly engineered*
Finding: Weekly shapes are **exactly normalized**. Every
`(demand_class, country, tzid, channel_group)` shape sums to 1.0
(`max_abs_diff ≈ 1e‑15`).

Explanation: The shape policy is designed so *distributional* realism
dominates, not volume. This makes time‑of‑day/weekend patterns explainable
without confounding scale effects. This is consistent with the shape library
template intent in `config/layer2/5A/policy/shape_library_5A.v1.yaml`.

Finding: The policy only enforces **minimum realism floors**, and the observed
patterns exceed those floors by a large margin:
- `min_night_mass_online24h = 0.08` vs observed **0.357**  
- `min_weekend_mass_evening_weekend = 0.30` vs observed **0.445**  
- `min_weekday_mass_office_hours = 0.65` vs observed **0.811**

Explanation: This is a *high‑contrast archetype* regime. The policy sets
minimum realism but allows strong, stylized patterns. The resulting profiles
are intentionally sharp and explainable rather than naturally noisy.

Finding: Peakiness is strong relative to the policy’s nonflat floor
(`shape_nonflat_ratio_min = 1.6`). Observed peak‑to‑mean ratios range from
~2.1 (`online_24h`) to **~7.4** (`evening_weekend`).

Explanation: The template shapes use large peak amplitudes and powers > 1.0,
so sharp peaks are expected. This supports explainable patterns but creates a
clear “synthetic stylization” footprint if you want more organic variation.

Finding: Shape diversity is deliberately limited. Each class has **three**
template variants, selected deterministically by tzid.

Explanation: This improves determinism and reproducibility, but it reduces
heterogeneity within a class. If realism requires more within‑class variety,
the template pool (not the constraints) is the lever.

Finding: Policy expects all channel groups, but the run produces only
`channel_group = mixed` in `class_zone_shape_5A`.

Explanation: This is a **policy‑realization gap**. Temporal differences between
card‑present vs card‑not‑present are not realized in this run, even though the
policy is structured to support them.

### 11.2 D — Overlay realism is bounded and conservative
Finding: Scenario event amplitudes are **inside policy bounds**:
- `HOLIDAY` observed **0.65–1.03** (policy bounds **0.50–1.05**)  
- `PAYDAY` observed **1.000–1.599** (policy bounds **1.00–1.60**)  
- `CAMPAIGN` observed **1.35** (policy bounds **1.00–2.50**)  
- `OUTAGE` observed **0.05** (policy bounds **0.00–0.50**)

Explanation: The overlay policy (`config/layer2/5A/scenario/scenario_overlay_policy_5A.v1.yaml`)
is being respected tightly. This means the “realism posture” is deliberately
bounded: shocks are explainable and constrained rather than extreme.

Finding: Overlay factors are sparse and mild (mean **1.005**, P95 **1.052**,
~90% of buckets = 1.0). This also sits inside the validation warning bands
(baseline mean must be **0.85–1.25**).

Explanation: The baseline scenario is intentionally stable with intermittent
events, which yields realistic calendar effects without overwhelming the base
signal. The overlay validation policy supports this conservative posture.

Finding: Event scoping is macro‑level. In baseline_v1, events are only:
`country + demand_class`, `tzid`, or `demand_class`. No `merchant` or `global`
events are present, even though the policy allows them.

Explanation: This produces realism that is **systemic** (macro shocks) rather
than idiosyncratic. It is plausible, but it limits merchant‑level variability.

Finding: DST residuals are not addressed in overlay policy. Residual mismatch
is confined to DST‑shifting TZIDs and does not affect total mass.

Explanation: This is a technical artifact, not a policy violation. If desired,
policy could explicitly encode DST alignment or scenario grid correction.
