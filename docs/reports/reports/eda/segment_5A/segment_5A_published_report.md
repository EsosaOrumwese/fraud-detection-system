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

