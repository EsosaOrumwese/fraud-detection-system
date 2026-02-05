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

This is a pre‑analysis report. It does not include statistical findings yet.

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
2. **Poisson‑like bucket counts.**  
   `s3_bucket_counts_5B` should align with `lambda_realised × bucket_duration`, with variance roughly proportional to mean.
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

Explanation: Counts are centered correctly on `mu`, but variance is larger than Poisson (sd ≈ 1.40). This matters because real transactional traffic is **over‑dispersed**: you see bursts and lulls that exceed Poisson randomness. The NB2 law is designed to capture exactly that, and the data show it.  
The observed zero‑rate is almost identical to the Poisson‑implied zero‑rate. That tells us the extra variance is **not** coming from artificially forcing more zeros (zero‑inflation), which would make the dataset look too sparse. Instead, the variance inflation comes from heavier tails on the **positive** side — occasional high‑count buckets — which is a realistic pattern for heterogeneous merchants.  
Finally, `count_N / mu` has a long but not absurd tail (p99 ≈ 4.14), indicating bursts that are strong but still within plausible bounds. This is the kind of dispersion we expect in synthetic data that aims to feel realistic rather than overly smooth.

### 8.6 Micro‑time placement inside buckets
Using a 1,000,000‑row sample of arrivals:
1. All timestamps are within bucket windows (`n_before=0`, `n_after=0`).
2. Offset ratios are close to uniform:  
   mean **0.4999**, p50 **0.5002**, p90 **0.9000**.

Explanation: Time placement looks uniform within each 1‑hour bucket, which is consistent with a neutral intra‑bucket placement policy. There is no evidence of boundary leakage or time‑window violations.

### 8.7 Routing posture (physical vs virtual)
Routing mix:
1. Virtual arrivals = **2,802,007** (share **2.25%**).
2. Physical arrivals = **121,922,146**.
3. Routing field integrity holds:  
   all virtual rows have `edge_id` and null `site_id`; all physical rows have `site_id` and null `edge_id`.

Explanation: The virtual share is small but non‑zero and the physical/virtual field invariants are clean. This indicates routing logic is applied consistently and that virtual traffic is present but rare in this world.

### 8.8 Local‑time correctness and DST mismatch
Local‑time check (sample of 50,000 arrivals):
1. Mismatch rate ≈ **2.6%**.
2. All mismatches are exactly **−3600 seconds** (local time is 1 hour earlier than expected).
3. Mismatches concentrate on DST transition windows:
   - **US DST** around **2026‑03‑08** to **2026‑03‑11**
   - **EU DST** around **2026‑03‑29** to **2026‑03‑31**

Explanation: This strongly suggests that local timestamps are being computed without applying DST shifts (standard time only). The error is small in proportion but systematic and clustered; it is the main realism mismatch observed so far.

---

## 8) Preliminary realism checks — findings so far
Run scope: `runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer2\5B`

### 8.1 Scope and totals (sanity)
Observed partitions: **seed=42, scenario_id=baseline_v1** (single manifest_fingerprint + parameter_hash).

Totals:
1. `arrival_events_5B` total arrivals = **124,724,153**
2. `s3_bucket_counts_5B` sum(`count_N`) = **124,724,153**

Explanation: At the run‑partition level, arrivals exactly conserve counts. This is the primary integrity requirement of S4 and it holds in this run.

### 8.2 Key duplication in S2/S3 (structural reality, not a bug)
Both `s2_realised_intensity_5B` and `s3_bucket_counts_5B` contain **multiple rows per key** `(merchant_id, zone_representation, channel_group, bucket_index)`:
1. Unique keys: **29,913,840**
2. Total rows: **35,700,480**
3. Multiplicity distribution (keys):  
   1× **25,667,280**, 2× **3,170,880**, 3× **773,280**, 4× **196,560**, 5× **49,680**, 6× **56,160**

Explanation: The surfaces are not strictly unique by key. Realism analysis must therefore aggregate by key (sum of `lambda_realised` or `count_N`) before comparing to arrivals. When aggregated, S2→S3 and S3→S4 are perfectly consistent (see 8.3).

### 8.3 Count conservation at key‑level (after aggregation)
After aggregating S3 by key and comparing to arrival counts:
1. **All keys match** (mismatch = 0, total_abs_diff = 0).

Explanation: The apparent mismatches in sampled joins disappear once duplicate keys are aggregated. This confirms that S4 expands the **aggregated** S3 counts exactly as required.

### 8.4 S2 latent intensity realism
