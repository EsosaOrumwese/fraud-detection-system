# Segment 5B — Design vs Implementation Observations (Arrival Realisation)
Date: 2026-02-05  
Run: `runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92`  
Scope: Design intent vs implementation notes for Segment 5B (S0–S5) prior to deep statistical assessment.

---

## 0) Why this report exists
Segment 5B is the **arrival realisation layer**. It takes 5A scenario intensities and produces concrete arrival events via a latent LGCP field, bucket counts, micro‑time placement, and routing to sites or virtual edges. This report captures:
1. **Design intent** (what 5B is supposed to produce).
2. **Implementation decisions** (how we actually built the states).
3. **Known deviations** that matter for realism interpretation.

This report includes both design/implementation context and the statistical findings gathered so far; later sections expand as analysis proceeds.

---

## 1) Design intent (what 5B should do)
1. **S0 — Gate & sealed inputs**  
   Verify upstream PASS gates (1A–3B, 5A) and seal all required inputs/policies into `sealed_inputs_5B`.

2. **S1 — Time grid & grouping**  
   Build the bucket grid and grouping plan that align with the 5A scenario surface and routing groups.

3. **S2 — Latent intensity field (LGCP)**  
   Apply a latent stochastic field to `lambda_target` to produce `lambda_realised`, with deterministic RNG per seed.

4. **S3 — Bucket counts**  
   Draw integer counts per entity×bucket from the realised intensity according to `arrival_count_config_5B`.

5. **S4 — Micro‑time & routing**  
   Expand counts into arrival events with exact timestamps inside buckets and route each arrival to a physical site or virtual edge using 2B/3A/3B routing policies.

6. **S5 — Validation & PASS gate**  
   Validate invariants and RNG accounting for S0–S4 and publish the authoritative 5B validation bundle and `_passed.flag`.

---

## 2) Priority datasets (realism‑relevant)
Primary realism surfaces:
1. `arrival_events_5B` (per‑arrival skeleton with timestamps and routing)
2. `s3_bucket_counts_5B` (count realisation for each entity×bucket)
3. `s2_realised_intensity_5B` (latent‑adjusted intensity)

Mechanism surfaces used to explain realism:
1. `s1_time_grid_5B`
2. `s1_grouping_5B`
3. Optional `s2_latent_field_5B` (if emitted)
4. Routing references from 2B/3B (`s1_site_weights`, alias tables, edge catalogue)

Evidence surfaces (minimal realism impact):
1. `s0_gate_receipt_5B`, `sealed_inputs_5B`
2. `validation_bundle_5B` + `_passed.flag`

---

## 3) Implementation observations (what is actually done)
Based on `docs\model_spec\data-engine\implementation_maps\segment_5B.impl_actual.md` and 5B state‑expanded specs.

### 3.1 S0 — Gate & sealed inputs
Observed posture: strict, metadata‑only, seed‑invariant sealing.

Key implementation decisions:
1. **Scenario set from 5A manifest.**  
   `scenario_set` defaults to the full `scenario_manifest_5A` list (run‑scoped subsets are not used unless explicitly supported later).
2. **Seed‑invariant sealed inputs.**  
   `sealed_inputs_5B` is keyed only by `(parameter_hash, manifest_fingerprint)` with `{seed}` placeholders left unresolved.
3. **Structural digests for data‑plane outputs.**  
   Large seed‑scoped data outputs are not hashed by content; structural digests are used to keep S0 metadata‑only.
4. **`bundle_layout_policy_5B` treated as optional.**  
   Spec text lists it as required, but dictionary marks it optional and repo lacks a file, so S0 logs optional‑missing.

### 3.2 S2 — Latent intensity (LGCP)
Observed posture: deterministic LGCP with explicit RNG policy alignment.

Key implementation decisions:
1. **Lambda target source fixed to local scenario surface.**  
   `merchant_zone_scenario_local_5A.lambda_local_scenario` is the sole target; UTC surface is not used.
2. **Philox open‑interval uniforms + Box‑Muller.**  
   Uniforms use `(x+0.5)/2^64` mapping; Box‑Muller draws 2 uniforms per normal.
3. **Latent models supported.**  
   OU/AR(1) and IID log‑Gaussian options with clipping and optional `lambda_max` caps.
4. **Chunked processing for scale.**  
   Parquet row‑group chunks used to avoid RAM blowups and preserve progress logs.

### 3.3 S3 — Bucket counts
Observed posture: RNG‑consuming Poisson‑like count sampling, with per‑draw RNG event logging.

Key implementation decisions:
1. **Bucket counts are authoritative.**  
   Every `(entity, bucket)` count is drawn from `lambda_realised` under `arrival_count_config_5B`.
2. **Explicit RNG event table.**  
   `rng_event_arrival_bucket_count` is emitted for per‑draw accounting.

### 3.4 S4 — Arrival expansion
Observed posture: strict count conservation, time placement within bucket, and routing using upstream universes.

Key implementation decisions:
1. **Count conservation is binding.**  
   S4 emits exactly `N` arrivals per bucket from S3 with no resampling.
2. **Time placement obeys bucket windows + DST policy.**  
   Arrival timestamps are in `[bucket_start_utc, bucket_end_utc)`; local times derived via 2A timetable.
3. **Routing follows 2B/3A/3B.**  
   Physical routing uses site weights and alias tables; virtual routing uses 3B edge policy.
4. **Schema nullability patch (design decision).**  
   Optional fields (e.g., `site_id`, `edge_id`, `tzid_settlement`) were planned to be nullable; a temporary validation workaround existed in code. The intent is to make schemas explicitly nullable and remove the workaround. This affects how we interpret any schema‑related anomalies during analysis.

### 3.5 S5 — Validation bundle (lean posture)
Observed posture: streaming + summary‑based validation with explicit relaxations.

Key implementation decisions:
1. **Lean validation with sampling.**  
   Expensive checks (civil‑time, ordering, full routing joins) are sampled deterministically rather than exhaustive.
2. **Count conservation preferred via summary.**  
   Uses `s4_arrival_summary_5B` if present; falls back to streaming aggregates.
3. **Routing membership checks are dtype‑safe and physical‑only.**  
   Membership checks ignore virtual arrivals and compare IDs as strings to avoid dtype mismatches.
4. **Relaxed gating for civil‑time and RNG trace.**  
   Civil‑time mismatches and missing RNG trace families are WARN‑level in lean mode, not hard FAIL.

---

## 4) Design vs implementation deltas (material)
1. **S0 uses structural digests for seed‑scoped data.**  
   Design expects sealed inputs; implementation keeps S0 metadata‑only via structural digests. This is a deliberate performance‑safety trade.
2. **`bundle_layout_policy_5B` is optional in practice.**  
   Spec lists it as required, but repo posture treats it as optional.
3. **S5 validation is intentionally lean.**  
   Sampling‑based checks and relaxed gating for civil‑time/RNG trace mean PASS is less strict than a full exhaustive validator.
4. **S4 schema nullability required a contract adjustment.**  
   Optional fields may be null; contract/schema must match. If schemas are not updated, validation can mis‑report issues.

---

## 5) Expectations before statistical analysis
Given the design and implementation posture, we should expect the following in data analysis:
1. **Over‑dispersion vs 5A.**  
   `s2_realised_intensity_5B` should show broader variance than the 5A scenario surface due to the LGCP field.
2. **Bucket counts align with per‑bucket mean.**  
   `s3_bucket_counts_5B` should align with `lambda_realised` (which is already a per‑bucket mean in this run). If the count law is NB2, variance should exceed the mean (i.e., more bursty than a plain Poisson where variance equals mean).
3. **Exact count conservation.**  
   Aggregating `arrival_events_5B` by entity×bucket must equal `s3_bucket_counts_5B` exactly.
4. **Time placement within buckets.**  
   Arrival `ts_utc` should fall strictly within bucket windows; local time should follow 2A timezone rules and DST policies.
5. **Routing matches upstream universes.**  
   Site/edge IDs should be valid per 2B/3B catalogues; physical vs virtual mix should match 3B classification policy.
6. **RNG‑driven reproducibility.**  
   The same `(parameter_hash, manifest_fingerprint, seed, scenario_id)` should yield identical outputs on reruns.

---

## 6) Implications for realism assessment
1. **Lean validation means we must check more directly.**  
   Because S5 does sampling and relaxed gates for civil‑time/RNG trace, we should independently verify DST behavior and RNG‑driven consistency in analysis.
2. **Structural digests do not confirm data content.**  
   `sealed_inputs_5B` does not hash large data outputs, so any realism anomalies are more likely to reflect data‑generation logic than S0 sealing.
3. **Schema nullability should be treated as intentional.**  
   Nulls in optional fields (e.g., site_id for virtual, edge_id for physical) are expected and should not be interpreted as data quality issues.

---

## 7) Next step
Proceed to statistical realism assessment starting from:
1. `arrival_events_5B`
2. Trace back to `s3_bucket_counts_5B` and `s2_realised_intensity_5B` only when needed to explain patterns.

---

## 8) Preliminary realism checks — findings so far (A/B)
Run scope: `runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer2\5B`

### 8.1 Scope and totals (sanity)
Observed partitions: **seed=42, scenario_id=baseline_v1** (single manifest_fingerprint + parameter_hash).

Totals:
1. `arrival_events_5B` total arrivals = **124,724,153**
2. `s3_bucket_counts_5B` sum(`count_N`) = **124,724,153**

Explanation: At the run‑partition level, arrivals exactly conserve counts. This is not merely a bookkeeping check — it is the foundational realism requirement for any downstream analysis. The entire arrival process in 5B is supposed to be: **intensity → counts → arrivals**. If the total arrivals differ from total counts, it means arrivals were created or dropped after the stochastic draw, which would invalidate any realism judgments about timing, dispersion, or routing because the baseline mass would be wrong. Since totals match exactly, we can trust that later realism checks are assessing a consistent world.

### 8.2 Key duplication in S2/S3 (structural reality, not a bug)
Both `s2_realised_intensity_5B` and `s3_bucket_counts_5B` contain **multiple rows per key** `(merchant_id, zone_representation, channel_group, bucket_index)`:
1. Unique keys: **29,913,840**
2. Total rows: **35,700,480**
3. Multiplicity distribution (keys):  
   1× **25,667,280**, 2× **3,170,880**, 3× **773,280**, 4× **196,560**, 5× **49,680**, 6× **56,160**

Explanation: The surfaces are not strictly unique by key. This is a structural property of the pipeline: multiple modeling components can contribute to the same key (for example, multiple latent sub‑components or grouped fragments). That does **not** imply a bug by itself, but it changes how you interpret the data. For realism analysis, you **must aggregate by key** (sum `lambda_realised` or `count_N`) before comparing to arrivals; otherwise you will see false mismatches because you are comparing a single arrival total to a partial component. Once aggregated, the pipeline is internally consistent (see 8.3). The realism implication is: duplication is an **internal modeling representation**, not an artifact that changes the final arrival mass.

### 8.3 Count conservation at key‑level (after aggregation)
After aggregating S3 by key and comparing to arrival counts:
1. **All keys match** (mismatch = 0, total_abs_diff = 0).

Explanation: The apparent mismatches in sampled joins disappear once duplicate keys are aggregated. This confirms that S4 expands the **aggregated** S3 counts exactly as required, and that the duplication is a modeling representation rather than a data quality issue. In practical terms: if you collapse the internal components into their logical bucket, you get **perfect conservation**. That is the key realism guarantee we need before looking at timing, routing, or dispersion.

### 8.4 S2 latent intensity realism (B)
Key statistics (`s2_realised_intensity_5B`):
1. Correlation `lambda_baseline` vs `lambda_realised` = **0.965**  
2. `lambda_random_component` distribution:  
   mean **0.997**, p50 **0.962**, p90 **1.357**, p99 **1.807**, min **0.2**, max **5.0**  
3. Clipping is rare: **112** rows at min, **13** at max.
4. Lag‑1 autocorrelation of `lambda_random_component` across buckets ≈ **0.96** (sample).

Explanation: The latent field perturbs baseline intensities in a smooth, bounded way. The random component is centered near **1.0**, so it **scales** the baseline up or down without changing the overall magnitude drastically. The spread (p90 ≈ 1.36, p99 ≈ 1.81) means most buckets get moderate variation, with occasional larger boosts or suppressions — a realistic pattern for commerce traffic.  
Clipping is extremely rare (125 rows out of 35.7M), which tells us the field is not being artificially constrained at its limits. That matters because frequent clipping would signal that the latent field is “pushing too hard” and being truncated, which would look synthetic.  
The lag‑1 correlation of ≈0.96 indicates **strong temporal persistence**: adjacent buckets move together rather than jittering. This is exactly what we expect in real transactional intensity where demand changes gradually, not as white noise. In short: the latent field adds variability, but does so with continuity and realistic magnitude.

### 8.5 S3 bucket‑count realism (A)
Key statistics (`s3_bucket_counts_5B`):
1. Mean `mu` ≈ **3.492**; mean `count_N` ≈ **3.494**.
2. Zero‑rate ≈ **0.88965**, Poisson‑expected zero‑rate `E[e^{-mu}]` ≈ **0.88927** (very close).
3. `count_law_id` = **nb2** for all rows.
4. Standardized residuals `(count_N − mu)/sqrt(mu)` have **sd ≈ 1.40** (over‑dispersion vs Poisson sd ~1).
5. `count_N / mu` mean **1.0003** with wide upper tail (p99 **~4.14**).

Explanation: Counts are centered correctly on `mu` (the per‑bucket mean count), but variance is larger than Poisson (sd ≈ 1.40). This matters because real transactional traffic is **over‑dispersed**: you see bursts and lulls that exceed a Poisson baseline where variance equals the mean. The NB2 law is designed to capture exactly that, and the data show it.  
The observed zero‑rate is almost identical to the Poisson‑implied zero‑rate. That tells us the extra variance is **not** coming from artificially forcing more zeros (zero‑inflation), which would make the dataset look too sparse. Instead, the variance inflation comes from heavier tails on the **positive** side — occasional high‑count buckets — which is a realistic pattern for heterogeneous merchants.  
Finally, `count_N / mu` has a long but not absurd tail (p99 ≈ 4.14), indicating bursts that are strong but still within plausible bounds. This is the kind of dispersion we expect in synthetic data that aims to feel realistic rather than overly smooth.

### 8.6 Micro‑time placement inside buckets
Using a 1,000,000‑row sample of arrivals:
1. All timestamps are within bucket windows (`n_before=0`, `n_after=0`).
2. Offset ratios are close to uniform:  
   mean **0.4999**, p50 **0.5002**, p90 **0.9000**.

Explanation: Time placement looks uniform within each 1‑hour bucket, which is exactly what a neutral intra‑bucket placement policy should produce. If arrivals were clustering at the start or end of buckets, we would see skewed ratios and boundary leaks — that would signal artificial micro‑bursts or a broken placement law. Instead, the distribution is symmetric around 0.5, and there are zero out‑of‑window events, so the micro‑time placement is statistically clean and realism‑compatible.

Additional realism reasoning (C1/C2):  
1. **C1 — In‑bucket placement looks statistically correct.** Uniform offsets (mean ~0.5, p90 ~0.9) tell us that arrivals are not being “pushed” toward bucket edges or clustered at a specific sub‑bucket time. If that were happening, it would create artificial micro‑bursts that do not correspond to any policy or behavioral signal. Because the offsets are symmetric and bounded, the timing is behaving like a neutral placement law, which is exactly what we want unless a shaped policy was intended.  
2. **C2 — No bucket leakage confirms temporal integrity.** The zero leak rate means every arrival lives inside the bucket that generated it. This matters because any leakage would break the core consistency between the intensity surface and realized arrivals; a time‑based model could then see demand “shift” into neighboring buckets for purely technical reasons. Since there is no leakage, the time grid remains trustworthy for realism analysis.

Local hour‑of‑day structure (C3 context):  
The local‑time hour‑of‑day curve peaks around **11–16** (e.g., hour 12 has **~8.85M** arrivals, hours 11/13/16 are all **~8.4–8.5M**), and then gradually declines into the night (e.g., hour 4 has **~1.74M**). This mid‑day peak and smooth taper is consistent with typical commerce behavior and indicates that aggregate temporal rhythm is plausible rather than flat or erratic.

### 8.7 Routing posture (physical vs virtual)
Routing mix:
1. Virtual arrivals = **2,802,007** (share **2.25%**).
2. Physical arrivals = **121,922,146**.
3. Routing field integrity holds:  
   all virtual rows have `edge_id` and null `site_id`; all physical rows have `site_id` and null `edge_id`.

Explanation: The virtual share is small but non‑zero, which is realistic if the synthetic world is dominated by physical merchants with a minority of virtual activity. The strict null/non‑null integrity between `site_id` and `edge_id` confirms the routing model is internally coherent: virtual events never leak into physical fields and vice‑versa. This gives us confidence that any routing‑mix realism issues (if any) are policy‑level rather than data integrity problems.

### 8.8 Local‑time correctness and DST mismatch
Local‑time check (sample of 50,000 arrivals):
1. Mismatch rate ≈ **2.6%**.
2. All mismatches are exactly **−3600 seconds** (local time is 1 hour earlier than expected).
3. Mismatches concentrate on DST transition windows:
   - **US DST** around **2026‑03‑08** to **2026‑03‑11**
   - **EU DST** around **2026‑03‑29** to **2026‑03‑31**

Explanation: This strongly suggests that local timestamps are being computed without applying DST shifts (standard time only). The error is small in proportion but **systematic** and **clustered**, which makes it more important than a random 2–3% noise. In other words, the issue is predictable and localized to DST windows rather than scattered. This is the single strongest realism mismatch observed so far in 5B.

Additional realism reasoning (D1/D2/D3):  
1. **D1 — Small but systematic mismatch.** A consistent 1‑hour error during DST windows is not random noise; it indicates a specific missing step in local‑time construction (DST adjustment). Even though the rate is only ~2.6%, it is concentrated in critical windows, which makes the bias predictable and repeatable.  
2. **D2 — Localized but impactful.** The mismatch concentrates in high‑volume EU/US timezones, so it disproportionately affects the most influential traffic. This matters for any model that uses hour‑of‑day or “night vs day” features. The error is not large enough to change weekly totals, but it **does** shift hour‑level distributions around DST windows.  
3. **D3 — Rare +3600 offsets confirm edge‑case TZ gaps.** The small number of +3600s (e.g., Africa/El_Aaiun) shows the issue is not confined to EU/US DST rules; there are timezone‑specific edge cases where the local‑time mapping also deviates. This reinforces that DST handling is globally incomplete, not just a regional oversight.

### 8.9 Weekend‑share alignment (expected vs observed)
Expected weekend share from intensities (`s2_realised_intensity_5B` + `s1_time_grid_5B`): **0.28617**  
Observed weekend share from arrivals (`ts_local_primary`): **0.28653**  
Absolute difference: **0.00036** (0.036 percentage points)

Explanation: The weekend share in arrivals matches the intensity surface almost perfectly. This is the concrete answer to the earlier C3 question: if the hour‑of‑day curve looked plausible but weekend share was off, we would suspect the arrival realisation step was distorting weekly rhythm. Instead, the match is effectively exact, which means the micro‑time placement and count realisation are respecting the weekly structure encoded upstream. That’s a strong realism signal.

### 8.10 DST mismatch impact on features
Using a 200,000‑row sample:
1. Overall mismatch rate: **2.6235%**
2. Hour‑of‑day shift rate: **2.6235%** (every mismatch shifts hour)
3. Date (day‑of‑week) shift rate: **0.0425%**

Explanation: The DST mismatch primarily affects **hour‑of‑day** features, not day‑of‑week. This means models using hourly patterns will be slightly skewed during DST windows, while weekend/weekday features remain almost entirely correct. The effect is real but narrow: it does not broadly corrupt the calendar structure, it mostly shifts hour‑level positioning for a small slice of events.

### 8.11 DST mismatch attribution (where it comes from)
Mismatch attribution (200,000‑row sample, 5,352 mismatches):
1. **EU DST window (2026‑03‑29 to 2026‑04‑04): 87.7%**
2. **US DST window (2026‑03‑08 to 2026‑03‑14): 3.5%**
3. **Other dates: 8.8%**

Explanation: The mismatch is overwhelmingly driven by EU DST transitions, with a smaller US DST component. The “other” bucket likely reflects timezone edge cases with non‑standard DST rules (e.g., Africa/El_Aaiun). This confirms the issue is not random; it is a predictable DST handling gap concentrated in specific windows.

---

## 9) E — Routing Realism (Physical vs Virtual)

### 9.1 Physical vs virtual mix
Virtual share = **2.25%** (2,802,007 of 124,724,153); physical share = **97.75%**.

Explanation: This is a small but meaningful virtual presence. If the synthetic world is mostly physical merchants with a minority of virtual activity, this is plausible. It is not so small that virtual is “absent,” and not so large that virtual dominates. The mix feels consistent with a physical‑first world.

### 9.2 Physical site concentration
Sites: **23,989**.  
Share of physical arrivals by site concentration:
1. Top 1% sites: **7.15%**
2. Top 5% sites: **22.08%**
3. Top 10% sites: **33.04%**

Explanation: Physical traffic shows **moderate concentration**. A small head of sites carries a disproportionate share of volume, but not to an extreme degree. This is realistic for retail networks, where a few flagship or dense‑area sites dominate, while many sites remain low‑volume.

### 9.3 Virtual edge concentration
Edges: **5,000**.  
Share of virtual arrivals by edge concentration:
1. Top 1% edges: **5.05%**
2. Top 5% edges: **24.79%**
3. Top 10% edges: **48.85%**

Explanation: Virtual traffic is **more concentrated** than physical traffic. This is realistic if the virtual catalog has a few dominant “platform‑like” edges alongside a long tail of smaller edges. The concentration is strong but not pathological.

### 9.4 Physical vs virtual temporal profile
Hour‑of‑day profile summary:
1. **Physical** peak hour = **12** (mid‑day)  
   - Day share (09–17): **0.5805**  
   - Evening share (18–23): **0.2480**  
   - Night share (00–05): **0.0907**
2. **Virtual** peak hour = **21** (late evening)  
   - Day share: **0.3234**  
   - Evening share: **0.3048**  
   - Night share: **0.2675**

Explanation: Virtual traffic is clearly later‑hour heavy, while physical traffic is day‑centric. This is exactly the separation we would expect between online and in‑person activity. It is a strong realism indicator: the routing type is not just a label; it is associated with a different temporal rhythm.

### 9.5 Weekend share by routing class
Weekend share:
1. Physical = **0.2856**
2. Virtual = **0.3289**

Explanation: Virtual traffic is more weekend‑heavy, which is consistent with consumer online behavior. This adds realism to the routing mix and shows that virtual activity is not merely a scaled‑down copy of physical traffic.

---

## 10) F — Macro‑Distribution Realism (Arrivals)

### 10.1 Merchant heavy‑tail (arrival totals)
Merchants: **886**.  
Arrival totals:
1. Median **58,385**, p90 **215,799**, p99 **1,543,702**, max **16,954,915**
2. Top‑1% share **28.80%**
3. Top‑5% share **49.46%**

Explanation: The arrival distribution is strongly heavy‑tailed, with a small head carrying roughly half of total volume. This is a realistic macro signature for merchant activity: a handful of large merchants dominate, while most remain smaller. The tail is steep but not implausible.

### 10.2 Merchant heavy‑tail vs intensity (is routing inflating?)
Comparison of arrivals vs S2 intensity by merchant:
1. Corr(`arrivals`, `sum_lambda`) = **0.999998**
2. Top‑1% share: arrivals **28.80%** vs intensity **28.78%**
3. Top‑5% share: arrivals **49.46%** vs intensity **49.44%**

Explanation: The heavy‑tail in arrivals is essentially identical to the heavy‑tail in S2 intensity. This shows that routing and micro‑time placement are **not inflating** the macro distribution; they are faithfully realising the intensity surface. In other words, the heavy‑tail is a **policy/world design feature**, not a routing artifact.

### 10.3 Timezone concentration (global skew)
Timezones: **139**.  
Top‑share concentration:
1. Top 1% TZ share = **13.96%**
2. Top 5% TZ share = **58.63%**
3. Top 10% TZ share = **81.30%**

Explanation: The world is heavily concentrated in a small set of timezones, which implies a strong geographic skew. This can be realistic **if** the synthetic world is intentionally Europe‑heavy (which appears to be the case in the upstream world design). If we want a more globally balanced world, this concentration would be too strong.

### 10.4 Virtual vs physical TZ skew
Top‑10 TZ share comparison:
1. **Virtual**: **56.82%**
2. **Physical**: **76.80%**

Top virtual TZs are Asia‑ and LatAm‑leaning (e.g., Asia/Shanghai, Asia/Kolkata, America/Phoenix), while physical is much more Europe‑dominant.

Explanation: Virtual traffic is **less Europe‑skewed** and more globally distributed than physical traffic. This is realistic: online activity can be global even if the physical merchant footprint is concentrated. It also shows that the virtual component adds diversity rather than reinforcing the same geographic skew.

### 10.5 Site/edge concentration (Gini)
Gini coefficients:
1. **Sites (physical)** = **0.384**
2. **Edges (virtual)** = **0.605**

Explanation: Physical traffic shows moderate inequality across sites, while virtual traffic is substantially more concentrated. Here “Gini” is a 0–1 concentration measure (higher means more unequal/clustered). The values indicate that online edges are dominated by a smaller set of large platforms, whereas physical sites are more evenly spread. The difference is strong but plausible.

---

## 11) Realism Grade (5B)

**Grade: B+**

### Why this grade (strengths)
1. **Internal statistical coherence is excellent.**  
   Counts conserve exactly into arrivals once keys are aggregated, and intensity → counts → arrivals stay aligned. That is the core realism requirement and it passes cleanly.
2. **Dispersion is realistically bursty.**  
   NB2 behavior shows variance > mean without artificial zero‑inflation. This is a realistic statistical posture for heterogeneous commerce data.
3. **Latent field behavior is plausible.**  
   It adds variability without clipping, is smooth over time (high lag‑1), and does not distort totals. That gives realism without chaos.
4. **Routing realism is strong.**  
   Physical vs virtual traffic differs in time‑of‑day and weekend share, and concentration patterns are plausible (moderate for sites, stronger for edges).
5. **Macro distributions are plausible.**  
   Heavy‑tail behavior mirrors the intensity surface almost perfectly, which means routing and timing are not creating artificial skew.

### Why not an A (gaps)
1. **DST handling is a real realism defect.**  
   ~2.6% of arrivals have systematic 1‑hour local‑time errors clustered in DST windows, which directly affects hour‑level features and explainability.
2. **Geographic skew is very strong.**  
   Top‑10 timezones carry ~81% of volume, implying a Europe‑heavy world. This can be fine if intentional but limits “global realism.”
3. **Virtual share is small.**  
   2.25% is plausible but may under‑represent online activity if the intended world should include richer virtual behavior.

### What would move this to A‑ / A
1. **Fix DST alignment** in local timestamps (this is the main blocker).
   This would remove the systematic 1‑hour offsets in DST windows and eliminate the only clear realism defect in C/D. It would also reduce feature bias for hour‑of‑day and “night vs day” analyses during DST periods.
2. **Broaden geographic distribution** or explicitly justify the Europe‑heavy skew in policy.
   Right now, the top‑10 TZs hold ~81% of volume. If we want global realism, we should either rebalance the world allocation (e.g., more non‑EU sites or merchants) or explicitly document that the synthetic world is intentionally Europe‑centric so the skew becomes a stated design choice rather than a perceived weakness.
3. **Increase virtual share modestly** if the policy intent is to model more online behavior.
   Virtual traffic is only ~2.25%. If downstream fraud modeling expects meaningful online patterns (CNP‑like rhythms, weekend‑heavy behavior, late‑hour concentration), a slightly higher virtual share would make those signals more robust and reduce over‑reliance on the physical distribution.
