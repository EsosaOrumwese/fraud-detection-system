# Layer-1 - Segment 3A - State Overview (S0-S7)

Segment 3A is the zone allocation universe. It gates 1A/1B/2A, decides which merchant x country pairs need multi-zone splits, samples Dirichlet zone shares, integerises to per-zone outlet counts, publishes `zone_alloc` plus a routing universe hash, and seals the segment with a PASS bundle. Inter-country order remains with 1A `s3_candidate_set`.

## Segment role at a glance
- Enforce 1A/1B/2A HashGates ("no PASS -> no read") and seal priors/policies for zone allocation.
- Determine escalation (multi-zone vs single-zone) per merchant x country and freeze counts.
- Prepare country x tzid Dirichlet priors, draw zone shares (RNG), and integerise to zone counts.
- Publish `zone_alloc` and `zone_alloc_universe_hash`; validate and bundle with `_passed.flag_3A`.

---

## S0 - Gate & sealed inputs (RNG-free)
**Purpose & scope**  
Verify `_passed.flag` from 1A, 1B, and 2A for the target `manifest_fingerprint`; seal all artefacts 3A may read.

**Preconditions & gates**  
`validation_bundle_{1A,1B,2A}` + flags must match; otherwise abort ("no PASS -> no read").

**Inputs**  
Upstream gated egress: 1B `site_locations`/`outlet_catalogue`, 2A `site_timezones` and `tz_timetable_cache`; policy packs `zone_mixture_policy`, `country_zone_alphas`, `zone_floor_policy`, `day_effect_policy_v1`.

**Outputs & identity**  
`s0_gate_receipt_3A` at `data/layer1/3A/s0_gate_receipt/fingerprint={manifest_fingerprint}/`; `sealed_inputs_3A` at `data/layer1/3A/sealed_inputs/fingerprint={manifest_fingerprint}/`.

**RNG**  
None.

**Key invariants**  
No 3A read without 1A/1B/2A PASS; only artefacts listed in `sealed_inputs_3A` are allowed; path/embed parity holds.

**Downstream consumers**  
All later 3A states verify the receipt; S7 replays its digests.

---

## S1 - Escalation & requirements frame (deterministic)
**Purpose & scope**  
Decide which merchant x country pairs are escalated to multi-zone and record their outlet counts.

**Preconditions & gates**  
S0 PASS; `site_locations` available for `{seed, fingerprint}`; `zone_mixture_policy` sealed.

**Inputs**  
`site_locations` (for `site_count` per merchant/country); `zone_mixture_policy` (thresholds/overrides).

**Outputs & identity**  
`s1_escalation_queue` at `data/layer1/3A/s1_escalation_queue/seed={seed}/manifest_fingerprint={manifest_fingerprint}/`, with `site_count`, `is_escalated`, `decision_reason`.

**RNG**  
None.

**Key invariants**  
Every `(merchant, country)` with outlets appears once; counts match 1B/1A; escalation decisions follow policy deterministically.

**Downstream consumers**  
S3 uses escalated domain and counts; S4 integerises; S5 egress lineage.

---

## S2 - Country x zone priors (deterministic)
**Purpose & scope**  
Prepare parameter-scoped Dirichlet alpha vectors per country x tzid, applying floors/bump rules.

**Preconditions & gates**  
S0 PASS; `country_zone_alphas` and `zone_floor_policy` sealed.

**Inputs**  
`country_zone_alphas`; `zone_floor_policy`; zone universe per country (from ingress/2A/3A config).

**Outputs & identity**  
`s2_country_zone_priors` at `data/layer1/3A/s2_country_zone_priors/parameter_hash={parameter_hash}/` with `alpha_raw`, `alpha_effective`, `alpha_sum_country`, floor/bump flags.

**RNG**  
None.

**Key invariants**  
Only declared `(country, tzid)` pairs appear; `alpha_effective` respects floors; `alpha_sum_country` > 0 for valid countries.

**Downstream consumers**  
S3 Dirichlet draws use these priors; S5 hashes them into the universe digest.

---

## S3 - Dirichlet zone shares (RNG)
**Purpose & scope**  
For each escalated merchant x country, draw zone share vectors over that country's tzids.

**Preconditions & gates**  
S0, S1, S2 PASS; Layer-1 RNG envelope available.

**Inputs**  
`s1_escalation_queue` (escalated domain, `site_count`); `s2_country_zone_priors`; country zone universes.

**Outputs & identity**  
`s3_zone_shares` at `data/layer1/3A/s3_zone_shares/seed={seed}/fingerprint={manifest_fingerprint}/`, one row per escalated `(merchant_id, legal_country_iso, tzid)` with `share_drawn`, sum fields, and RNG provenance.

**RNG posture**  
Gamma draws per zone -> normalise (Dirichlet); RNG event family `rng_event_zone_dirichlet` under `logs/rng/events/.../seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`; budgets per alpha, trace reconciled.

**Key invariants**  
Shares non-negative; per `(merchant, country)` shares sum to 1 (tolerance per spec); only escalated pairs are drawn; S4 must not resample.

**Downstream consumers**  
S4 integer allocation; S6 validation; S5 hash.

---

## S4 - Integer zone allocation (deterministic)
**Purpose & scope**  
Convert zone shares and total outlets into integer zone counts via deterministic largest-remainder.

**Preconditions & gates**  
S0–S3 PASS; counts and shares available.

**Inputs**  
`s1_escalation_queue` (`site_count`), `s3_zone_shares` (`share_drawn`), zone universes.

**Outputs & identity**  
`s4_zone_counts` at `data/layer1/3A/s4_zone_counts/seed={seed}/fingerprint={manifest_fingerprint}/`, one row per escalated `(merchant, country, tzid)` with `zone_site_count`.

**RNG**  
None.

**Key invariants**  
For each `(merchant, country)`, sum of `zone_site_count` equals `site_count`; tzid domain matches the country's zone universe; no zero-count rows emitted unless required by schema.

**Downstream consumers**  
S5 egress; S6 count checks; downstream segments rely on counts via `zone_alloc`.

---

## S5 - Zone egress & universe hash
**Purpose & scope**  
Publish `zone_alloc` as cross-layer authority and compute `zone_alloc_universe_hash` tying priors/policies/results into one digest.

**Preconditions & gates**  
S0–S4 PASS; policy packs sealed.

**Inputs**  
`s4_zone_counts`; `s2_country_zone_priors`; `zone_mixture_policy`; `zone_floor_policy`; `day_effect_policy_v1` (for routing universe hash).

**Outputs & identity**  
`zone_alloc` at `data/layer1/3A/zone_alloc/seed={seed}/fingerprint={manifest_fingerprint}/`, with counts, per-pair sums, and policy lineage fields.  
`zone_alloc_universe_hash` at `data/layer1/3A/zone_alloc_universe_hash/fingerprint={manifest_fingerprint}/zone_alloc_universe_hash.json` containing component digests (alphas, mixture, floors, day-effect, `zone_alloc` parquet) and combined `routing_universe_hash`.

**RNG**  
None.

**Key invariants**  
`zone_alloc` matches `s4_zone_counts`; `routing_universe_hash` is stable for the same inputs; downstream (2B, 5B, 3B) must treat `zone_alloc` + universe hash as immutable authority.

**Downstream consumers**  
S6 validation; S7 bundle; routing/arrival segments consume `zone_alloc` after PASS.

---

## S6 - Validation report (deterministic)
**Purpose & scope**  
Audit 3A outputs (structure, counts, RNG accounting) and produce validation artefacts.

**Preconditions & gates**  
S0–S5 PASS; all datasets and RNG logs available.

**Inputs**  
`s0_gate_receipt_3A`, `sealed_inputs_3A`; `s1_escalation_queue`, `s2_country_zone_priors`, `s3_zone_shares`, `s4_zone_counts`, `zone_alloc`, `zone_alloc_universe_hash`; RNG logs `rng_event_zone_dirichlet`, `rng_audit_log`, `rng_trace_log`.

**Outputs & identity**  
`s6_validation_report_3A` at `data/layer1/3A/s6_validation_report_3A/fingerprint={manifest_fingerprint}/`; optional `s6_issue_table_3A`; `s6_receipt_3A` summarising status and digests.

**RNG**  
None (auditor only).

**Key invariants**  
Counts conserve across S1/S4/zone_alloc; domain checks pass; RNG budgets align with trace/events; `overall_status` must be PASS for gating.

**Downstream consumers**  
S7 requires PASS receipt before bundling; operators inspect issues.

---

## S7 - Validation bundle & `_passed.flag_3A`
**Purpose & scope**  
Seal Segment 3A for the fingerprint and publish the HashGate for downstream consumers.

**Preconditions & gates**  
S0–S6 PASS with `s6_receipt_3A.overall_status="PASS"`; upstream gates still verify.

**Inputs**  
Gate receipt and sealed inputs; all 3A datasets (`s1`–`s5`, universe hash); validation artefacts (`s6_*`).

**Outputs & identity**  
`validation_bundle_3A` at `data/layer1/3A/validation/fingerprint={manifest_fingerprint}/` with `validation_bundle_index_3A`; `_passed.flag_3A` alongside containing `sha256_hex = <bundle_digest>` over indexed files in ASCII-lex order (flag excluded).

**RNG**  
None.

**Key invariants**  
Bundle index is complete; recomputed digest matches `_passed.flag_3A`; enforces "no PASS -> no read" for `zone_alloc` and `zone_alloc_universe_hash`.

**Downstream consumers**  
Segments 2B, 3B, 5B must verify `_passed.flag_3A` before using 3A egress; routing uses the universe hash as authority.
