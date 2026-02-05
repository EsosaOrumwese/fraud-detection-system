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
