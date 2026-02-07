# Engine Realism — Step 2 Root-Cause Trace (Critical/High Gaps)
Date: 2026-02-07  
Run baseline: `runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92`  
Scope: Root-cause diagnostics for **Critical/High** gaps in `engine_realism_baseline_gap_ledger.md`.  
Status: **Diagnosis only** (no fixes proposed or implemented here).

---

## 0) Inputs and Evidence Sources
Primary evidence:
- `docs/reports/reports/eda/engine_realism_baseline_gap_ledger.md`
- Segment reports: `segment_1A_published_report.md`, `segment_1B_published_report.md`, `segment_2A_published_report.md`, `segment_2B_published_report.md`, `segment_3A_published_report.md`, `segment_3B_published_report.md`, `segment_5B_published_report.md`, `segment_6A_published_report.md`, `segment_6B_published_report.md`

Policy + implementation anchors (non-exhaustive):
- `config/layer1/1A/policy/s3.rule_ladder.yaml`
- `config/layer1/1A/models/hurdle/hurdle_simulation.priors.yaml`
- `packages/engine/src/engine/layers/l1/seg_1A/s6_foreign_set/runner.py`
- `packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/runner.py`
- `packages/engine/src/engine/layers/l1/seg_2A/s1_tz_lookup/runner.py`
- `packages/engine/src/engine/layers/l1/seg_2A/s2_overrides/runner.py`
- `config/layer1/2B/policy/alias_layout_policy_v1.json`
- `config/layer1/2B/policy/day_effect_policy_v1.json`
- `packages/engine/src/engine/layers/l1/seg_2B/s1_site_weights/runner.py`
- `packages/engine/src/engine/layers/l1/seg_2B/s3_day_effects/runner.py`
- `packages/engine/src/engine/layers/l1/seg_2B/s4_group_weights/runner.py`
- `packages/engine/src/engine/layers/l1/seg_2B/s5_router/runner.py`
- `config/layer1/3A/policy/zone_mixture_policy.yaml`
- `config/layer1/3A/allocation/country_zone_alphas.yaml`
- `packages/engine/src/engine/layers/l1/seg_3A/s1_escalation/runner.py`
- `packages/engine/src/engine/layers/l1/seg_3A/s3_zone_shares/runner.py`
- `packages/engine/src/engine/layers/l1/seg_3A/s4_zone_counts/runner.py`
- `config/layer1/3B/virtual/cdn_country_weights.yaml`
- `config/layer1/3B/virtual/cdn_key_digest.yaml`
- `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py`
- `packages/engine/src/engine/layers/l1/seg_3B/s2_edge_catalogue/runner.py`
- `packages/engine/src/engine/layers/l2/seg_5B/s4_arrival_events/numba_kernel.py`
- `packages/engine/src/engine/layers/l2/seg_5B/s5_validation_bundle/runner.py`
- `config/layer3/6A/priors/account_per_party_priors_6A.v1.yaml`
- `config/layer3/6A/priors/ip_count_priors_6A.v1.yaml`
- `packages/engine/src/engine/layers/l3/seg_6A/s2_accounts/runner.py`
- `packages/engine/src/engine/layers/l3/seg_6A/s4_device_graph/runner.py`
- `packages/engine/src/engine/layers/l3/seg_6A/s5_fraud_posture/runner.py`
- `config/layer3/6B/truth_labelling_policy_6B.yaml`
- `config/layer3/6B/amount_model_6B.yaml`
- `packages/engine/src/engine/layers/l3/seg_6B/s2_baseline_flow/runner.py`
- `packages/engine/src/engine/layers/l3/seg_6B/s4_truth_bank_labels/runner.py`

---

## 1) Critical Gaps — Root Cause Trace

### 1.1) 6B — Truth labels collapse to 100% fraud (Critical)
**Evidence:** Reported `is_fraud_truth=True` for 100% of flows; direct check on sealed run shows `is_fraud_truth_mean = 1.0` with labels `{ABUSE: 124,721,936; FRAUD: 2,217}`.

**Most likely root cause:** Implementation mapping collapses `fraud_pattern_type` without honoring `overlay_anomaly_any`. The mapping dictionary is keyed only by `fraud_pattern_type`, so duplicate rules for `NONE` overwrite each other and force `ABUSE` for all `campaign_type = NONE` rows.

**Policy anchors:**
- `config/layer3/6B/truth_labelling_policy_6B.yaml` defines **two** `fraud_pattern_type: NONE` rules differentiated only by `overlay_anomaly_any` (`LEGIT` vs `ABUSE`).

**Implementation anchors:**
- `packages/engine/src/engine/layers/l3/seg_6B/s4_truth_bank_labels/runner.py`: `_load_truth_maps` builds `mapping_label` keyed **only** by `fraud_pattern_type` (lines around 610–626), discarding `overlay_anomaly_any`.
- Same runner defaults unknown/missing campaign type to `NONE` (lines around 1064–1065, 1211–1216).

**Interaction/propagation:** This defect erases the negative class and makes bank-view labels and case timelines uninterpretable as fraud detection data.

**Confidence:** High.

**Falsification check:** Inspect the `campaign_type` distribution in `s3_flow_anchor_with_fraud_6B` and verify if any non-`NONE` types exist; if they do, check whether they remain `LEGIT` after mapping. If mapping still yields `ABUSE` for `NONE` regardless of `overlay_anomaly_any`, this root cause holds.

**Expected posture if corrected:** A non-trivial `LEGIT` majority with `FRAUD`/`ABUSE` as minority classes; `is_fraud_truth_mean` should fall below 0.2 in baseline scenarios.

---

### 1.2) 6B — Bank-view outcomes nearly uniform across strata (Critical)
**Evidence:** Reported bank-fraud rate ~0.155 with Cramer’s V ~0.001 across class/amount; run check shows `is_fraud_bank_view_mean = 0.1550` with fixed label mix.

**Most likely root cause:** Bank-view labels are generated by global, deterministic mixtures with no feature conditioning; with truth labels already collapsed, stratification signal is erased.

**Policy anchors:**
- `bank_view_policy_6B` (loaded in `s4_truth_bank_labels`) appears as a single global mixture rather than covariate-conditioned model.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l3/seg_6B/s4_truth_bank_labels/runner.py`: `_extract_auth_mixture` and model flags are applied globally; `bank_label` is computed from truth + fixed detection/dispute/chargeback flags (lines ~1245–1263).

**Interaction/propagation:** Even if upstream features are realistic, bank-view labels cannot express risk differentiation; model training will see flat outcomes.

**Confidence:** High.

**Falsification check:** Verify that detection/dispute/chargeback flags are independent of features like `merchant_class`, `amount`, `cross_border`, etc. If conditioning is absent in code and policy, this stands.

**Expected posture if corrected:** Bank-view fraud rates should vary across at least **merchant class** and **amount bins** with effect sizes > 0.05, and Cramer’s V > 0.05 in baseline scenarios.

---

### 1.3) 6B — Case timelines show invalid temporal gaps (Critical)
**Evidence:** Report shows negative gaps and rigid 1h/24h patterns in case timelines.

**Most likely root cause:** Case events are constructed from **fixed minimum delays only**, and event timestamps are not enforced to be monotonic. `case_close_delay_seconds` can be smaller than `chargeback_delay_seconds`, creating negative gaps when events are ordered by sequence but timestamps reflect mixed delays.

**Policy anchors:**
- `delay_models_6B` appears to be interpreted as **min-only** in code.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l3/seg_6B/s4_truth_bank_labels/runner.py`: `_load_min_delay_seconds` returns only minimums; all case event timestamps are `base_ts + fixed_delay` (lines ~974–983 and ~1349–1361). No monotonic correction pass is applied.

**Interaction/propagation:** Case timelines cannot be used for realistic lifecycle analytics, which undermines the case/label subsystem and any time-to-resolution modeling.

**Confidence:** High.

**Falsification check:** Confirm whether `case_close_delay_seconds` is ever < `chargeback_delay_seconds` in the policy; if so, negative gaps are inevitable in the current construction.

**Expected posture if corrected:** Event gaps should be non-negative; distributions should show a long tail rather than two fixed spikes.

---

### 1.4) 3B — Edge catalogue is structurally uniform (Critical)
**Evidence:** Report shows each merchant has fixed `edge_scale=500`, near-identical edge-count profile, and `edge_weight = 1/edge_scale` behavior.

**Most likely root cause:** Policy sets a fixed edge cardinality and implementation applies uniform per-edge mass. There is no merchant-level heterogeneity layer before final edge materialization.

**Policy anchors:**
- `config/layer1/3B/virtual/cdn_country_weights.yaml` and `cdn_key_digest.yaml` define fixed `edge_scale: 500` and uniform-tail behavior.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_3B/s2_edge_catalogue/runner.py`: fixed-scale read path (`edge_scale`), and deterministic uniform edge weights (`edge_weight = 1.0 / edge_scale`).

**Interaction/propagation:** 3B feeds a structurally flat edge substrate into layer-2/layer-3. Later segments can only add realism by overlaying rules, not by inheriting organic network diversity.

**Confidence:** High.

**Falsification check:** If edge-weight variance within merchant is effectively zero and edge-count distribution is degenerate at 500, this diagnosis holds.

**Expected posture if corrected:** Edge counts and edge weights should vary by merchant profile (size/class/country), with heterogeneous concentration patterns.

---

### 1.5) 3B — Settlement coherence is weak (Critical)
**Evidence:** Settlement-country overlap is near baseline (~0.5%), and many edges are far from settlement anchor countries.

**Most likely root cause:** Country-edge allocation is driven by global weight tables with weak settlement-aware conditioning, so settlement information has minimal pull on final edge geography.

**Policy anchors:**
- `config/layer1/3B/virtual/cdn_country_weights.yaml` emphasizes global/tail weights; settlement affinity terms are weak relative to global mass.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_3B/s2_edge_catalogue/runner.py`: edge-country draw path references global country weights and digest-driven deterministic assignment without strong settlement-coupled reweighting.

**Interaction/propagation:** Legal/settlement identity stops being a strong explanatory variable for virtual footprint, weakening downstream auditability and cross-border realism narratives.

**Confidence:** High.

**Falsification check:** Compare edge-country probabilities conditioned on settlement country versus global baseline. If uplift is weak or absent, coherence failure is confirmed.

**Expected posture if corrected:** Settlement country and proximate legal markets should receive statistically significant uplift over global baseline in edge assignment.

---

## 2) High Gaps — Root Cause Trace

### 2.1) 1A — Missing single-site merchant tier (High)
**Evidence:** Report shows `min outlets = 2` and `single_vs_multi_flag=True` for all merchants.

**Most likely root cause:** Implementation sets all merchants as multi-site and never emits the single-site tier, regardless of policy intention.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/runner.py`: assigns `single_vs_multi_flag=True` for all rows (lines ~2050–2052).

**Interaction/propagation:** Overstates multi-site behavior, exaggerating routing complexity and cross-border footprints.

**Confidence:** High.

**Falsification check:** Inspect `s8_outlet_catalogue_1A` for any `single_vs_multi_flag=False` rows. If none exist, this is confirmed.

**Expected posture if corrected:** A non-trivial single-site fraction (typically >30% in synthetic worlds) to seed realistic small merchants.

---

### 2.2) 1A — Home/legal country mismatch is too broad (High)
**Evidence:** Reported ~38.6% of rows with `home_country_iso != legal_country_iso`.

**Most likely root cause:** Candidate expansion rules allow global reach; `legal_country_iso` is drawn from expanded foreign set while `home_country_iso` is fixed, creating wide divergence.

**Policy anchors:**
- `config/layer1/1A/policy/s3.rule_ladder.yaml`: `GLOBAL_CORE` admission set used by `ALLOW_*` rules (lines ~21, 74, 90).

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_1A/s8_outlet_catalogue/runner.py`: sets `home_country_iso` from `home_iso`, `legal_country_iso` from selected country (lines ~2050–2051).

**Interaction/propagation:** Distorts legal-country realism, which cascades into cross-border labeling and regional interpretation in later segments.

**Confidence:** High.

**Falsification check:** Inspect s6 membership selection; if `legal_country_iso` is drawn from a large candidate set independent of home, mismatch will remain high.

**Expected posture if corrected:** Home/legal mismatch should be a minority signal with clear policy rationale (e.g., 5–15%).

---

### 2.3) 1A — Candidate universe is over-globalized (High)
**Evidence:** Candidate countries per merchant median ~38/39 with near-zero realization ratios.

**Most likely root cause:** Rule ladder allows global admission for most merchants; selection then caps or filters late, producing large candidate lists but low realization.

**Policy anchors:**
- `config/layer1/1A/policy/s3.rule_ladder.yaml`: `GLOBAL_CORE` used widely.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_1A/s6_foreign_set/runner.py`: `max_candidates_cap` applied only **after** candidate list is built (lines ~1404–1413).

**Interaction/propagation:** Weakens explainability (“can expand anywhere but rarely does”).

**Confidence:** Medium.

**Falsification check:** Count candidate list sizes before cap; if median ~38 persists, root cause is confirmed.

**Expected posture if corrected:** Candidate breadth should vary by merchant scale or policy tier, with many merchants having small candidate lists.

---

### 2.4) 1A — Dispersion heterogeneity collapsed (High)
**Evidence:** Implied `phi` CV ~0.00053, P95/P05 ~1.00004.

**Most likely root cause:** Hand-authored dispersion coefficients are effectively constant or mapped through a pipeline that collapses per-merchant variance, despite priors allowing variability.

**Policy anchors:**
- `config/layer1/1A/models/hurdle/hurdle_simulation.priors.yaml`: `per_merchant_log_phi_sd: 0.18` and `phi` min/max wide (lines ~22, 27, 142–143).

**Implementation anchors:**
- Coefficient bundle diagnostics show almost no dispersion spread (see `segment_1A` plots `22_phi_actual_vs_reference.png`).

**Interaction/propagation:** Suppresses stochastic heterogeneity that should feed later variability surfaces.

**Confidence:** Medium.

**Falsification check:** Validate whether any stage applies `per_merchant_log_phi_sd` when building coefficient bundles. If not, the collapse is policy-authoring, not code.

**Expected posture if corrected:** Implied `phi` should exhibit meaningful CV (e.g., 0.1–0.3) with visible tails.

---

### 2.5) 1B — Global placement imbalance (High)
**Evidence:** Europe-heavy concentration and weak southern hemisphere/AF/SA coverage.

**Most likely root cause:** World-site placement policy weights are regionally biased; placement templates are deterministic and over-represent Europe.

**Policy anchors:**
- `config/layer1/1B/policy/policy.s2.tile_weights.yaml` is deterministic; the underlying weights appear to be Europe-centric in the generated `site_locations` surface.

**Interaction/propagation:** Timezone diversity compresses in 2A, affecting arrival realism in 5B.

**Confidence:** Medium.

**Falsification check:** Recompute site-count by region from `site_locations` and compare to intended region weights.

**Expected posture if corrected:** Country-level site counts reflect target global mix, not just European density.

---

### 2.6) 2A — Timezone support per country compressed (High)
**Evidence:** ~70% of countries have exactly 1 tzid; top-1 share median ~1.00.

**Most likely root cause:** Upstream spatial collapse + fallback rules in tz assignment yield singleton tzids.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_2A/s1_tz_lookup/runner.py`: country-singleton fallback and nearest-tz fallback (lines ~1277–1317), plus override paths (lines ~1260–1274).

**Interaction/propagation:** Local-time realism weakens and DST effects become concentrated.

**Confidence:** High.

**Falsification check:** Count `overrides_country_singleton_auto` and `fallback_nearest_*` in run report; if high, this is confirmed.

**Expected posture if corrected:** Multi-tz countries should show 2–4 tzids with non-degenerate shares.

---

### 2.7) 2B — Site weights are behaviorally flat (High)
**Evidence:** Uniformity residuals near zero; no hub dominance.

**Most likely root cause:** Weight policy is explicitly uniform; fallback is uniform; implementation uses uniform mode unless a column is provided.

**Policy anchors:**
- `config/layer1/2B/policy/alias_layout_policy_v1.json`: `weight_source.mode = uniform`, fallback `uniform`, note says deterministic uniform weights.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_2B/s1_site_weights/runner.py`: uniform mode handling (lines ~248, 842, 929–930).

**Interaction/propagation:** Routing cannot express realistic site concentration.

**Confidence:** High.

**Falsification check:** Check if any `weight_source` column exists in `s1_site_weights_2B`; if not, uniformity is by policy.

**Expected posture if corrected:** Top sites should capture materially higher share than median sites in high-volume merchants.

---

### 2.8) 2B — Temporal heterogeneity absent (High)
**Evidence:** Single `sigma_gamma` value across merchants (~0.12).

**Most likely root cause:** Day-effect policy uses a global scalar; implementation applies it uniformly.

**Policy anchors:**
- `config/layer1/2B/policy/day_effect_policy_v1.json`: `sigma_gamma: 0.12`.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_2B/s3_day_effects/runner.py`: `sigma_gamma` applied globally (lines ~637, 764, 814).

**Interaction/propagation:** Merchants share a single volatility regime, weakening temporal realism.

**Confidence:** High.

**Falsification check:** Validate if any merchant-level sigma exists in `s3_day_effects_2B`. If all identical, confirmed.

**Expected posture if corrected:** Sigma should vary by merchant class or size with meaningful spread.

---

### 2.9) 3A — Prior dominance suppresses diversity (High)
**Evidence:** High top-1 shares persist even for multi-tz countries; low entropy and low variance.

**Most likely root cause:** `country_zone_alphas.yaml` contains extreme alphas (very large and very small), driving Dirichlet draws toward single-zone dominance.

**Policy anchors:**
- `config/layer1/3A/allocation/country_zone_alphas.yaml` includes extreme alpha values (e.g., `0.005`, `66.31`, `58.97`).

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_3A/s3_zone_shares/runner.py`: Dirichlet sampling directly from alphas (lines ~901–933).

**Interaction/propagation:** Multi-zone diversity fails to materialize before 3B/5B.

**Confidence:** High.

**Falsification check:** Compute alpha histograms vs observed share entropy; if alphas imply high concentration, this is consistent.

**Expected posture if corrected:** Alphas should yield broader share distributions in multi-tz countries.

---

### 2.10) 3A — Escalation intent vs outcome mismatch (High)
**Evidence:** Escalated pairs multi-zone only ~13.3%; escalation does not produce diversity.

**Most likely root cause:** Threshold rules for escalation are too strict or misaligned with site/zone counts.

**Policy anchors:**
- `config/layer1/3A/policy/zone_mixture_policy.yaml` sets thresholds (`site_count_lt`, `zone_count_country_le`, etc.).

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_3A/s1_escalation/runner.py`: decision logic and default escalation (lines ~809–841, 827).

**Interaction/propagation:** Escalation becomes nominal, not structural; downstream diversity remains thin.

**Confidence:** Medium.

**Falsification check:** Compare escalation rates by bucket to rule thresholds; if most merchants fall outside thresholds, the mismatch is explained.

**Expected posture if corrected:** Escalation should materially increase multi-zone presence in high-site merchants.

---

### 2.11) 5B — DST mismatch persists (High)
**Evidence:** ~2.6% mismatch concentrated in DST windows; exact ±3600s offsets.

**Most likely root cause:** Local timestamp is computed with a fixed offset table that does not apply DST transitions for all tzids.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l2/seg_5B/s4_arrival_events/numba_kernel.py`: `tz_offsets_minutes` applied via `_tz_offset_minutes` without explicit DST handling (lines ~71–94, 290–299, 351–363).
- `packages/engine/src/engine/layers/l2/seg_5B/s5_validation_bundle/runner.py`: civil-time mismatches are WARN in lean mode (lines ~844–856).

**Interaction/propagation:** Hour-of-day features are biased in DST windows, affecting downstream models.

**Confidence:** Medium.

**Falsification check:** Inspect tz timetable inputs (2A timetable cache) and verify DST offsets for affected tzids.

**Expected posture if corrected:** Mismatch rate near zero; DST windows show correct local-time shifts.

---

### 2.12) 6A — IP type distribution drifts from priors (High)
**Evidence:** Residential observed ~96% vs expected ~34–42% in priors.

**Most likely root cause:** IP assignment is driven by high `p_zero_weight` or lambda settings that collapse non-residential types, plus possible normalization or clipping in the generator.

**Policy anchors:**
- `config/layer3/6A/priors/ip_count_priors_6A.v1.yaml`: expected IP-type shares by region (lines ~59–107).

**Implementation anchors:**
- `packages/engine/src/engine/layers/l3/seg_6A/s4_device_graph/runner.py`: uses `p_zero_weight_by_group` and `lambda_ip_per_device_by_group` (lines ~1646–1677), clamps by `max_ips_per_device` (lines ~1177–1178).

**Interaction/propagation:** Fraud risk by IP type and ASN class becomes unrealistic.

**Confidence:** Medium.

**Falsification check:** Compare realized `ip_type` composition against the prior by region to confirm systematic drift.

**Expected posture if corrected:** Observed IP-type shares should stay within the declared prior ranges.

---

### 2.13) 6A — Sparse device→IP linkage (High)
**Evidence:** Only ~14.8% of devices linked to IP.

**Most likely root cause:** High `p_zero_weight` in the link generator or low `lambda_ip_per_device` by device group.

**Policy anchors:**
- `config/layer3/6A/priors/ip_count_priors_6A.v1.yaml`: `lambda_ip_per_device_by_group` and `p_zero` semantics.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l3/seg_6A/s4_device_graph/runner.py`: uses `p_zero_by_group` and applies `max_ips_per_device` caps (lines ~1077–1178).

**Interaction/propagation:** Entity graph signal is thin, weakening fraud propagation in 6B.

**Confidence:** Medium.

**Falsification check:** Inspect link-rate by device group; if `p_zero_weight` dominates, linkage rate will collapse.

**Expected posture if corrected:** A meaningful majority of devices (e.g., >50%) linked to at least one IP.

---

### 2.14) 6A — Account cap semantics violated (High)
**Evidence:** Widespread `K_max` breaches by account type.

**Most likely root cause:** K_max is defined in priors but not enforced during allocation; generator uses `p_zero_weight` and `sigma` without hard cap.

**Policy anchors:**
- `config/layer3/6A/priors/account_per_party_priors_6A.v1.yaml`: `K_max` defined per account type (lines ~26–76), global cap (line ~101).

**Implementation anchors:**
- `packages/engine/src/engine/layers/l3/seg_6A/s2_accounts/runner.py`: uses `p_zero_weight`, `sigma`, `weight_floor`, but no visible `K_max` clamp in the allocation loop (lines ~1402–1453).

**Interaction/propagation:** Inflated account counts distort fraud/risk realism in 6B.

**Confidence:** Medium.

**Falsification check:** Verify if any later stage enforces `K_max` post-hoc. If not, breaches are implementation-driven.

**Expected posture if corrected:** Max accounts per party should respect per-type `K_max` with only rare exceptions.

---

### 2.15) 6A — Fraud-role propagation weak (High)
**Evidence:** Risky parties do not strongly imply risky accounts/devices/IPs.

**Most likely root cause:** Fraud roles are assigned independently per entity type via deterministic hash, not via graph propagation.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l3/seg_6A/s5_fraud_posture/runner.py`: per-entity `_hash_to_unit` assignment for party/account/merchant/device/IP (lines ~1056–1473). No conditional linkage between entity roles.

**Interaction/propagation:** Weak causal signals into 6B overlay and labels.

**Confidence:** High.

**Falsification check:** Compute conditional probability of risky device given risky party; if near base rate, independence is confirmed.

**Expected posture if corrected:** Risk should propagate along entity links with elevated conditional probabilities.

---

### 2.16) 6B — Amount/timing surfaces are mechanical (High)
**Evidence:** 8-point uniform amounts, no auth latency behavior.

**Most likely root cause:** Amounts are selected by deterministic hash index from `price_points_minor`, with no merchant-specific or covariate conditioning; events are timestamp-aligned with flows.

**Policy anchors:**
- `config/layer3/6B/amount_model_6B.yaml`: `price_points_minor` list (line ~17).

**Implementation anchors:**
- `packages/engine/src/engine/layers/l3/seg_6B/s2_baseline_flow/runner.py`: `amount_index` is hash-modulus of price points (lines ~1069–1074). No per-merchant distribution.

**Interaction/propagation:** Amounts are unrealistic and weakly informative for detection.

**Confidence:** High.

**Falsification check:** Check distinct amounts per merchant; if all merchants see all 8 points, this is confirmed.

**Expected posture if corrected:** Merchant-specific amount profiles with uneven weight and tails.

---

### 2.17) 2A — Non-representative country->tzid outcomes (High)
**Evidence:** Reported examples include implausible country-timezone pairings (e.g., NL mapped to Caribbean tzid class, NO to Arctic-only tzid class, US collapsing to Phoenix-only posture in sampled outputs).

**Most likely root cause:** The fallback chain in S1 resolves ambiguities using country-singleton and nearest-polygon logic. Under sparse/synthetic upstream site geometry, those fallbacks can produce technically valid but behaviorally implausible assignments.

**Policy anchors:**
- `config/layer1/2A/timezone/tz_nudge.yml` (country/tz nudges and ambiguity-handling policy inputs consumed by S1).
- `config/layer1/2A/timezone/tz_overrides.yaml` (country/site/mcc override pathways).

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_2A/s1_tz_lookup/runner.py`: country-singleton auto resolution (`overrides_country_singleton_auto`) and nearest fallback (`fallback_nearest_*`) in border/empty-candidate path (lines around 1277–1317).
- `packages/engine/src/engine/layers/l1/seg_2A/s1_tz_lookup/runner.py`: override precedence paths (`site` -> `mcc` -> `country`) (lines around 1261–1274).
- `packages/engine/src/engine/layers/l1/seg_2A/s2_overrides/runner.py`: final override reconciliation and mismatch checks against S1 provisional output (lines around 1220–1321).

**Interaction/propagation:** Civil-time realism becomes fragile, and downstream hour/day features become harder to interpret even when schema-level integrity is clean.

**Confidence:** High.

**Falsification check:** Inspect `s1_tz_lookup` run report counters (`overrides_country_singleton_auto`, `fallback_nearest_within_threshold`, `fallback_nearest_outside_threshold`) plus sampled ambiguity logs. If non-trivial, this mechanism is active and sufficient to explain observed outliers.

**Expected posture if corrected:** Multi-tz countries should map to plausible domestic timezone mixtures, with fallback paths rare and auditable exceptions.

---

### 2.18) 2B — Excessive single-tz daily dominance (High)
**Evidence:** About half of merchant-days have `max p_group >= 0.9`, indicating near-monozone daily routing.

**Most likely root cause:** S4 renormalizes `base_share * gamma`, but both drivers are diversity-thin:
- S1 site weights are uniform, so any sparse tz footprint in S1 directly hard-codes dominance.
- S3 uses a single global `sigma_gamma`, so day noise is insufficient to overturn dominant base shares.

**Policy anchors:**
- `config/layer1/2B/policy/alias_layout_policy_v1.json`: deterministic uniform site weights.
- `config/layer1/2B/policy/day_effect_policy_v1.json`: global scalar `sigma_gamma`.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_2B/s1_site_weights/runner.py`: uniform weight mode path.
- `packages/engine/src/engine/layers/l1/seg_2B/s3_day_effects/runner.py`: global `sigma_gamma` applied to every merchant/tz/day row (lines around 636–645, 814).
- `packages/engine/src/engine/layers/l1/seg_2B/s4_group_weights/runner.py`: `mass_raw = base_share * gamma` and day renormalization to `p_group` (lines around 804–846).

**Interaction/propagation:** 3A and 3B inherit a low-entropy daily routing substrate, reducing the ability to express believable zone diversity.

**Confidence:** High.

**Falsification check:** Compute correlation between per-merchant S1 top-1 `base_share` and S4 daily `max(p_group)`. If correlation is near 1 and day-level spread is narrow, this root cause is confirmed.

**Expected posture if corrected:** High-site and escalated merchants should exhibit materially broader daily `p_group` dispersion, not persistent >0.9 top-1 dominance.

---

### 2.19) 2B — Panel/roster realism shallow (High)
**Evidence:** Full rectangular 90-day merchant-day panel and one-arrival-per-merchant/day roster behavior.

**Most likely root cause:** Roster generation is deterministic at scenario level; S5 routing consumes sealed `s5_arrival_roster` as fixed input and does not add lifecycle/churn dynamics.

**Policy anchors:**
- Scenario roster policy (as represented in the sealed `s5_arrival_roster` artifact and documented in the 2B report) sets a rigid daily panel.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_2B/s5_router/runner.py`: treats `s5_arrival_roster` as sealed batch input and only routes group/site choice per row (lines around 818–870, 1125–1137).

**Interaction/propagation:** Downstream layers observe structurally regular activity, reducing realism for lifecycle features (entry/exit, inactivity streaks, burst starts/stops).

**Confidence:** High.

**Falsification check:** Check merchant-day coverage matrix for missing days and within-day multiplicity in roster. If near-rectangular with low within-day count variation, diagnosis holds.

**Expected posture if corrected:** Merchant activity should include entry/exit churn, intermittent inactivity, and variable daily event counts.

---

### 2.20) 3A — Sampling adds little merchant variance (High)
**Evidence:** Very low within-country/tz share variance despite stochastic sampling stage.

**Most likely root cause:** Dirichlet sampling exists, but effective variance is muted by high/peaked alpha structure and then further damped by count integerization.

**Policy anchors:**
- `config/layer1/3A/allocation/country_zone_alphas.yaml`: high alpha-mass structure in several countries reduces draw variance.

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_3A/s3_zone_shares/runner.py`: merchant-country Dirichlet sampling from provided alphas (lines around 924–959).
- `packages/engine/src/engine/layers/l1/seg_3A/s4_zone_counts/runner.py`: floor/residual-rank integerization compresses small share differences into identical integer counts (lines around 874–917).

**Interaction/propagation:** Merchant signatures remain weak entering 3B/5A, so downstream heterogeneity is dominated by later deterministic rules rather than organic upstream variance.

**Confidence:** Medium-high.

**Falsification check:** Compare variance before vs after S4 integerization at merchant-country level. If S4 sharply reduces dispersion, the compression mechanism is confirmed.

**Expected posture if corrected:** Distinct merchants in the same country should retain visibly different zone-share/count profiles after S4.

---

### 2.21) 3B — Classification evidence is flat (High)
**Evidence:** Classification appears dominated by MCC/channel gate with weak supporting variation; metadata/digest posture is near-singleton in effect.

**Most likely root cause:** Classification is a direct join of `(mcc, channel)` to binary decision map; no additional merchant- or geography-conditioned signal enters S1 classification.

**Policy anchors:**
- `mcc_channel_rules` policy artifact (binary mapping by MCC/channel pair).

**Implementation anchors:**
- `packages/engine/src/engine/layers/l1/seg_3B/s1_virtual_classification/runner.py`: rule map keyed by `(mcc, channel)` and left-join onto merchant table (lines around 683, 771–774).
- Same runner stamps shared `classification_digest` derived from one policy artifact across rows (lines around 597, 794).

**Interaction/propagation:** Audit explainability for why a merchant is virtual vs non-virtual is thin; downstream behavior can look policy-flat even when structurally valid.

**Confidence:** High.

**Falsification check:** Measure variance in virtual probability/decision within each MCC-channel pair using additional merchant covariates. If within-pair variance is effectively zero, diagnosis is confirmed.

**Expected posture if corrected:** Classification evidence should include additional conditioning (merchant scale, country context, settlement affinity), producing controlled within-pair variance.

---

## 3) Cross-Segment Interaction Chains
These are the most consequential propagation paths detected:

**1B → 2A → 5B:** Europe-heavy site placement compresses tz diversity; tz fallback in 2A locks single tzids; DST mismatch in 5B concentrates in EU/US tzids, magnifying bias.

**1A + 2B + 3A → 3B:** Over-global candidate breadth, uniform routing weights, and prior-dominated zone shares create a flat surface; 3B then hard-uniforms edges, making downstream diversity nearly impossible.

**6A → 6B:** Weak IP realism, sparse linkage, and independent fraud-role assignment leave 6B with little causal structure; 6B’s mapping defects then destroy label realism outright.

---

## 4) Step-2 Output Summary
- Root causes are **primarily policy + implementation simplifications**, not data corruption.
- The most urgent blockers are in **6B**, then **3B**, then **6A/2B/3A**.
- Several defects are **structural** (e.g., mapping collapse, uniform edges), so improvements will require **policy redesign + implementation logic changes**.

Next step (Step 3) should define **targeted remediation hypotheses** and **acceptance tests** per gap.
