# Segment 3A - Design vs Implementation Observations (Cross-Zone Allocation)
Date: 2026-01-31
Scope: Design intent vs implementation notes for Segment 3A (S0-S7), plus what to look for in 3A datasets before assessment.

---

## 0) Why this report exists
Segment 3A is the **cross-zone allocation layer** for merchant location realism. It decides **which merchantxcountry pairs should be split across multiple time-zones**, builds the **countryxzone priors** that shape those splits, samples **zone shares**, integerises them into **zone counts**, and finally emits the **zone_alloc** egress consumed downstream. This report captures **what the design specifies**, **what the implementation actually does**, and **what signals we should look for** in 3A datasets when assessing realism and correctness.

---

## 1) Design intent (what 3A should do)
High-level intent across states:

1) **S0 - Gate + sealed inputs**
   - Re-verify upstream PASS bundles for 1A/1B/2A (No PASS -> No read).
   - Seal policy inputs: `zone_mixture_policy`, `country_zone_alphas`, `zone_floor_policy`, and `day_effect_policy_v1`.
   - Seal required references: `iso3166_canonical_2024`, `world_countries`, `tz_world_2025a`, plus optional 2A surfaces (`site_timezones`, `tz_timetable_cache`, `s4_legality_report`).
   - Emit `s0_gate_receipt_3A` and `sealed_inputs_3A` only.

2) **S1 - Mixture policy & escalation queue**
   - Decide per **merchantxcountry** whether the pair remains monolithic or escalates into zone allocation.
   - Publish `s1_escalation_queue` as the **sole authority** on escalation decisions for later 3A states.
   - Deterministic and policy-bound: no RNG, no ad-hoc inputs.

3) **S2 - Countryxzone priors**
   - Build parameter-scoped `s2_country_zone_priors` as the **single source of truth** for Dirichlet alpha priors per countryxtzid.
   - Priors are derived from **country_zone_alphas** with **zone_floor_policy** applied; must align to the zone universe Z(c) derived from world polygons.
   - RNG-free, independent of merchant data.

4) **S3 - Zone share sampling**
   - For escalated merchantxcountry pairs, draw **Dirichlet shares** over tzids using the S2 priors.
   - Emit `s3_zone_shares` and RNG evidence logs to make sampling auditable.

5) **S4 - Integerisation to zone counts**
   - Convert continuous zone shares into **integer outlet counts** per tzid using floor/bump rules.
   - Emit `s4_zone_counts` with strict conservation of total outlets per merchantxcountry.

6) **S5 - Zone allocation egress + universe hash**
   - Publish the canonical `zone_alloc` egress for routing.
   - Emit `zone_alloc_universe_hash` to tie the output to its policy + prior inputs.

7) **S6 - Structural validation**
   - Validate S1-S5 outputs (schema, invariants, conservation, joins).
   - Emit `s6_validation_report_3A`, `s6_issue_table_3A`, and `s6_receipt_3A`.

8) **S7 - Validation bundle + _passed.flag**
   - Build a manifest-scoped validation bundle with digest index + `_passed.flag`.
   - Bundle acts as a gate for downstream readers and cross-segment validation.

---

## 2) Expected datasets & evidence surfaces (contract view)
Core datasets to assess later:

**Gate + sealing**
- `s0_gate_receipt_3A`, `sealed_inputs_3A`

**Escalation and priors**
- `s1_escalation_queue`
- `s2_country_zone_priors`

**Zone allocation pipeline**
- `s3_zone_shares`
- `s4_zone_counts`
- `zone_alloc`
- `zone_alloc_universe_hash`

**Validation + evidence**
- `s6_validation_report_3A`, `s6_issue_table_3A`, `s6_receipt_3A`
- `validation_bundle_3A` + `index.json` + `_passed.flag`

**RNG audit evidence (S3)**
- `rng_audit_log`, `rng_trace_log`, `rng_event_zone_dirichlet`

These are the surfaces we will use to evaluate realism and correctness.

---

## 2.1) Priority ranking (by purpose)
If we rank by the actual mission of 3A (realistic cross-zone allocation), the importance order is:
1) `zone_alloc` - final egress consumed by routing; if this is unrealistic, 3A has failed its purpose.
2) `s4_zone_counts` - integerised reality that directly determines `zone_alloc`.
3) `s3_zone_shares` - probabilistic source of counts; reveals whether allocations are skewed or flat.
4) `s2_country_zone_priors` - structural bias that shapes all downstream realism.
5) `s1_escalation_queue` - the gate deciding which merchantxcountry pairs even participate.

Note: the detailed checks below remain in pipeline order for traceability.

---

## 3) Implementation observations (what is actually done)

### 3.1 S0 - Gate + sealed inputs
**Observed posture:** Strict, deterministic, and consistent with Layer-1 gate semantics.

Key implementation traits:
- **HashGate verification is enforced** for 1A/1B/2A validation bundles and `_passed.flag` before any read of their outputs.
- **Sealed inputs are emitted as a JSON list of rows** (array of objects). Each row is validated against the row schema; missing required artefacts fail closed.
- **Policy versioning is strict**: policy file `version` is authoritative and must be non-placeholder; if registry semver is concrete it must match.
- **Catalogue consistency checks are enforced** (3A dictionary vs upstream dictionaries) to prevent path/schema drift.
- **Optional 2A inputs** (`site_timezones`, `tz_timetable_cache`, `s4_legality_report`) are included only if present; missing optional inputs are logged but do not fail the run.
- **No ad-hoc S0 report file** is produced (only `segment_state_runs`), aligning with the contracts.

Net: S0 is strict, policy-sealed, and deterministic, which is essential because all downstream realism depends on the correctness of the sealed input set.

---

### 3.2 S1 - Mixture policy & escalation queue
**Observed posture:** Implemented and green; escalation queue published.

Implementation highlights:
- **Z(c) universe is derived from `world_countries` + `tz_world_2025a`** via polygon intersection, not from site-level geometry. This matches the design boundary (S1 MUST NOT read 1B `site_locations`).
- **Escalation decisions are deterministic** and follow the mixture policy thresholds, with `decision_reason` attached per row.
- **Fail-closed posture**: if the policy requests escalation but Z(c) is empty, the state raises an error rather than manufacturing data.
- Output `s1_escalation_queue` is emitted with stable ordering and is treated as immutable.

Net: S1 behaves as the **sole authority** on escalation decisions, which is exactly what later states require for deterministic routing realism.

---

### 3.3 S2 - Countryxzone priors
**Observed posture:** Full plan locked; strictness decisions approved before coding.

Key choices locked in the implementation plan:
- **Z(c) recomputed from world polygons each run** (keeps S2 parameter-scoped and independent of S1).
- **Strict coverage rules**: any missing or extra tzids in the prior pack cause a hard fail (no silent fill-ins).
- **Optional tz_timetable_cache release check** enforced if sealed.
- **Run report kept minimal** (aggregates only).

Net: The planned S2 implementation is conservative and audit-grade: priors are only accepted if they precisely match the zone universe and policy.

---

### 3.4 S3 - Zone share sampling
**Observed posture:** Implemented with RNG evidence logging and strict bundle inclusion.

Highlights from implementation:
- **RNG evidence logs are produced** (audit, trace, event logs) and are included as bundle members for S7.
- Sampling is deterministic given `seed`, `parameter_hash`, and inputs; RNG evidence is the audit trail.

Net: S3 aligns with design by making Dirichlet sampling auditable and reproducible.

---

### 3.5 S4 - Integerisation to zone counts
**Observed posture:** Implemented with standard floor/bump logic and strict invariants.

Expected behavior enforced in validation:
- **Counts are integers** and must conserve the total outlet count per merchantxcountry.
- **Zone floor policy** is applied deterministically.

Net: S4 is the transition from probabilistic shares to concrete counts; correctness here is critical because errors will surface as unrealistic allocations downstream.

---

### 3.6 S5 - Zone allocation egress + universe hash
**Observed posture:** Implemented; produces `zone_alloc` and `zone_alloc_universe_hash`.

Key expectations enforced:
- `zone_alloc` is the canonical cross-segment egress and must be consistent with S4 counts.
- `zone_alloc_universe_hash` ties the output back to policy + prior inputs (auditability).

---

### 3.7 S6 - Structural validation
**Observed posture:** Implemented with schema-level validation and issue capture.

Key traits:
- Produces a **report + issue table + receipt**, which are later gated in S7.
- Validation is strict enough to block bundle publication if structural invariants break.

---

### 3.8 S7 - Validation bundle
**Observed posture:** Implemented with two deliberate deviations.

1) **Index-only bundle**
   - The bundle root contains only `index.json` + `_passed.flag`.
   - Member paths are **run-root-relative**, not bundle-relative.

2) **RNG logs included as members**
   - RNG evidence logs are included in the bundle membership even though they are not listed in `validation_bundle_3A` dependencies in the registry.

Net: These are documented deviations that affect how downstream gate verification must interpret the bundle index and digest law.

---

## 4) Design vs implementation deltas (summary)
1) **S7 index-only bundle**: Design allows bundles "by reference," but registry dependency lists are not updated. Implementation uses run-root-relative paths; gate verification must use run-root base.
2) **RNG evidence in bundle**: Included as members even though not declared in the registry dependency list. This is a deliberate deviation for audit completeness.
3) **Sealed inputs format**: `sealed_inputs_3A` is emitted as a JSON list, while the schema defines a row object. Implementation validates per row and treats the list as the envelope (consistent with other segments).

These deltas must be remembered when validating bundles or reading `sealed_inputs_3A` in downstream tooling.

---

## 5) What to look for in 3A datasets (realism + correctness)
This is the **forward-looking checklist** for the 3A outputs. It is focused on realism, not just schema validity.

**Realism focus priority (where analytical energy goes):**
1) **`zone_alloc`** - the final egress (realism outcome).
2) **`s4_zone_counts`** - integerised allocations that directly drive `zone_alloc`.
3) **`s3_zone_shares`** - sampled distributions that feed integerisation.
4) **`s2_country_zone_priors`** - structural bias that shapes shares.
5) **`s1_escalation_queue`** - eligibility gate for multi-zone behavior.

### 5.1 `s1_escalation_queue` (realism gate)
**What to inspect:**
- **Escalation rate** overall and by country: realistic data should not be all-escalated or all-monolithic.
- **Decision reasons**: distribution of `decision_reason` should line up with policy thresholds (e.g., below-min-sites vs dominant-zone).
- **Zone-count alignment**: escalation should correlate with higher `zone_count_country` (more tzids in Z(c)).
- **Domain parity**: rows should match 1A `outlet_catalogue` by `(merchant_id, legal_country_iso)` with no missing or extra pairs.

**Realism risks:**
- If escalation is near 0% or near 100%, the system is not expressing a meaningful mix of monolithic vs multi-zone merchants.
- If escalation is concentrated in tiny countries with few zones, the policy thresholds may be mis-tuned.

---

### 5.2 `s2_country_zone_priors` (structural realism bias)
**What to inspect:**
- **Coverage**: each `(country_iso, tzid)` in Z(c) should appear exactly once.
- **Alpha magnitude + dispersion**: do priors meaningfully differentiate zones, or are they uniform?
- **Floor/bump impact**: check how often floors are applied and whether they distort priors into uniformity.
- **Share normalization**: `share_effective` must sum to 1 per country and be in [0,1].

**Realism risks:**
- Uniform priors across tzids will produce unrealistic zone allocation (every zone equally likely regardless of population/urban density).
- Excessive floor application can flatten natural variation and remove dominant-zone patterns.

---

### 5.3 `s3_zone_shares` (sampled realism)
**What to inspect:**
- **Sum-to-1 per merchantxcountry** for escalated pairs.
- **Share concentration**: distributions should show a mix of dominant zones and long tails, not perfect uniformity.
- **RNG audit**: ensure `rng_audit_log`, `rng_trace_log`, and `rng_event_zone_dirichlet` are present and consistent with share counts.

**Realism risks:**
- If all zone shares are near-uniform, S2 priors are not injecting meaningful realism.
- If share distributions are identical across all merchants, there is no merchant-level heterogeneity.

---

### 5.4 `s4_zone_counts` (integerised realism)
**What to inspect:**
- **Conservation**: zone counts sum to the merchantxcountry outlet count.
- **Floor/bump effect**: verify small zones are not always floored to 1 (would make every zone artificially represented).
- **Rounding artifacts**: check if the integerisation systematically favors or punishes specific zones.

**Realism risks:**
- If a large fraction of merchantxcountry pairs become "one per zone," the allocations will look evenly spread and unrealistic.
- Large rounding drift indicates the integerisation is not preserving probabilistic intent.

---

### 5.5 `zone_alloc` (final realism signal)
**What to inspect:**
- **Country-level distribution of zones**: does zone allocation resemble plausible geographic footprints (few dominant tzids, long tail)?
- **Merchant heterogeneity**: do merchants with similar footprints have different zone allocations, or are they identical?
- **Consistency with `zone_alloc_universe_hash`**: the hash should change when policies/priors change; if not, the output is not tied to its inputs.

**Realism risks:**
- If zone allocation is identical across merchants (same tzid shares), the system lacks behavioral variation.
- If allocations ignore country boundaries (tzids outside Z(c)), the spatial realism is broken.

---

### 5.6 Validation and bundle surfaces
**What to inspect:**
- **S6 report and issues**: any FAIL or WARN codes should be explained and traced back to upstream decisions.
- **Validation bundle**: recompute digest using the index-only rule (run-root-relative paths).
- **RNG logs**: ensure presence and correct partitioning (seed, parameter_hash, run_id).

**Realism risks:**
- If validation passes but key realism metrics are flat (uniform priors, uniform shares), the system is structurally correct but behaviorally weak.

---

## 6) Interpretation guide (when we assess realism)
If 3A outputs look unrealistic, the most likely causes are:
1) **Over-uniform priors** (S2) -> zone allocations become flat and uninformative.
2) **Over-strict escalation thresholds** (S1) -> too few escalated pairs, which collapses the multi-zone realism layer.
3) **Aggressive floors** (S2/S4) -> every zone gets forced mass/counts, which removes dominant-zone realism.

So in assessment, we will separate:
- **Structural correctness** (schemas, gates, sum-to-1, conservation).
- **Realism quality** (heterogeneity, dominance patterns, sensible geographic variation).

---

(Next: detailed assessment of the actual 3A outputs under your run folder.)
