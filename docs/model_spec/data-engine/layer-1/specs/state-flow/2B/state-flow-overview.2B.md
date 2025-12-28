# Layer-1 - Segment 2B - State Overview (S0-S8)

Segment 2B is the routing engine. It freezes per-site weights, builds alias tables, draws day effects, normalises group weights, provides a two-stage router (group -> site) and a virtual-edge branch, audits everything, and seals the segment with a PASS bundle. All plan tables are `[seed, fingerprint]`; runtime logs are `[seed, parameter_hash, run_id, utc_day]`; the bundle/flag are `[fingerprint]`. Inter-country order stays with 1A `s3_candidate_set`.

## Segment role at a glance
- Enforce the 1B HashGate ("no PASS -> no read") and seal routing policies before reading `site_locations`.
- Deterministically derive long-run site weights and alias tables.
- Introduce day-level gamma shocks per tz-group; renormalise group weights per merchant/day.
- Route arrivals via two-stage alias (group, then site) with RNG evidence; branch for virtual-edge routing.
- Audit structural/RNG parity and publish `validation_bundle_2B` + `_passed.flag`.

---

## S0 - Gate & sealed inputs (RNG-free)
**Purpose & scope**  
Verify 1B `_passed.flag` for the target `manifest_fingerprint`; seal the inputs/policies 2B may read.

**Preconditions & gates**  
`validation_bundle_1B` + `_passed.flag` must match; otherwise abort ("no PASS -> no read").

**Inputs**  
`validation_bundle_1B`, `_passed.flag`; 1B `site_locations` `[seed, fingerprint]`; policy artefacts `route_rng_policy_v1`, `alias_layout_policy_v1`, `day_effect_policy_v1`, `virtual_edge_policy_v1`.

**Outputs & identity**  
`s0_gate_receipt_2B` at `data/layer1/2B/s0_gate_receipt/fingerprint={manifest_fingerprint}/`; `sealed_inputs_v1` at `data/layer1/2B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_v1.parquet`.

**RNG**  
None.

**Key invariants**  
No 2B reads without 1B PASS; only sealed artefacts may be read; path tokens equal embedded lineage where present.

**Downstream consumers**  
All later 2B states must verify the receipt; S8 replays its digests.

---

## S1 - Per-merchant site weights (deterministic)
**Purpose & scope**  
Derive long-run per-site probabilities per merchant from `site_locations` using `alias_layout_policy_v1` floors/caps/quantisation.

**Preconditions & gates**  
S0 PASS; `site_locations` present for `{seed, fingerprint}`; policy sealed.

**Inputs**  
`site_locations`; `alias_layout_policy_v1`.

**Outputs & identity**  
`s1_site_weights` at `data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest_fingerprint}/`, PK `(merchant_id, legal_country_iso, site_order)`, with `p_weight`, provenance flags, quantisation bits.

**RNG**  
None.

**Key invariants**  
1:1 coverage with `site_locations`; per-merchant weights sum to 1 (within tolerance); floors/caps applied per policy and flagged.

**Downstream consumers**  
S2 alias build; S4 base shares; S5/S6 routing.

---

## S2 - Alias tables (deterministic)
**Purpose & scope**  
Build O(1) alias tables per merchant from `s1_site_weights`; pack as blob + index with checksums.

**Preconditions & gates**  
S0, S1 PASS; alias layout policy sealed.

**Inputs**  
`s1_site_weights`; `alias_layout_policy_v1`.

**Outputs & identity**  
`s2_alias_blob` and `s2_alias_index` at `data/layer1/2B/s2_alias_{blob,index}/seed={seed}/fingerprint={manifest_fingerprint}/`, index includes layout metadata, offsets, lengths, per-merchant checksums, and `blob_sha256_hex`.

**RNG**  
None.

**Key invariants**  
Offsets non-overlapping and aligned per policy; per-merchant masses reconstructed from alias tables match quantised weights; blob/index digests match bytes.

**Downstream consumers**  
S5/S6 use alias tables for routing; S7 audits parity.

---

## S3 - Day effects (RNG)
**Purpose & scope**  
Draw per-day gamma multipliers by tz-group per merchant to add short-run co-movement without biasing long-run shares.

**Preconditions & gates**  
S0, S1 PASS; `site_timezones` from 2A available; `day_effect_policy_v1` and RNG policy sealed.

**Inputs**  
`s1_site_weights` (merchant/site universe); `site_timezones` (tz grouping); `day_effect_policy_v1`; `route_rng_policy_v1`.

**Outputs & identity**  
`s3_day_effects` at `data/layer1/2B/s3_day_effects/seed={seed}/fingerprint={manifest_fingerprint}/`, with `utc_day`, `tz_group_id`, `gamma`, `log_gamma`, variance parameters, RNG provenance.

**RNG posture**  
Philox stream for `day_effect` family; typically one Gaussian -> gamma per `(merchant, utc_day, tz_group)`; budgets recorded in events/trace (anchor in layer RNG pack).

**Key invariants**  
E[gamma]=1 per policy; one event per group/day; only tz-groups present in `site_timezones`.

**Downstream consumers**  
S4 consumes gamma to scale group weights; S7 audits RNG budgets.

---

## S4 - Group weights per day (deterministic)
**Purpose & scope**  
Combine base shares and day effects to produce per-day tz-group weights per merchant; renormalise.

**Preconditions & gates**  
S0, S1, S3 PASS; `site_timezones` available.

**Inputs**  
Base shares derived from `s1_site_weights` + `site_timezones`; `s3_day_effects`.

**Outputs & identity**  
`s4_group_weights` at `data/layer1/2B/s4_group_weights/seed={seed}/fingerprint={manifest_fingerprint}/`, with `p_group`, `gamma`, `base_share`, `mass_sum`, etc.

**RNG**  
None (pure function of inputs).

**Key invariants**  
For each `(merchant, utc_day)`, sum of `p_group` = 1 (tolerance per policy); groups align with `site_timezones` and `s3_day_effects`.

**Downstream consumers**  
S5 uses these weights for group sampling; S7 audits sums.

---

## S5 - Router core (RNG)
**Purpose & scope**  
Two-stage routing: sample tz-group per arrival/day, then sample site via alias; emit RNG evidence/logs.

**Preconditions & gates**  
S0-S4 PASS; alias blob/index and group weights available; `route_rng_policy_v1` governs streams/budgets.

**Inputs**  
`s4_group_weights`; `s2_alias_blob`/`s2_alias_index`; `s1_site_weights`; `site_timezones`; runtime arrivals (logical stream).

**Outputs & identity**  
Optional `s5_selection_log` at `data/layer1/2B/s5_selection_log/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/utc_day={utc_day}/`; RNG events `alias_pick_group` and `alias_pick_site` under `logs/rng/events/.../seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl`.

**RNG posture**  
Two single-uniform events per routed arrival (one group, one site); `blocks=1`, `draws="1"` per event; path/embed parity with `{seed, parameter_hash, run_id}`; trace reconciles totals.

**Key invariants**  
Selected group exists in `s4_group_weights`; selected site exists in `site_locations` and matches group tz; one event per draw; budgets equal logs.

**Downstream consumers**  
S7 audits; S8 bundles evidence.

---

## S6 - Virtual-edge routing (RNG, branch)
**Purpose & scope**  
For virtual merchants, route to CDN-style edges using a dedicated alias/policy; physical merchants bypass.

**Preconditions & gates**  
S0 PASS; `virtual_edge_policy_v1` sealed; edge catalogue/policy from 3B sealed in S0.

**Inputs**  
Virtual edge policy + edge weights/catalogue; arrivals marked `is_virtual=1`.

**Outputs & identity**  
Optional `s6_edge_log` at `data/layer1/2B/s6_edge_log/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/utc_day={utc_day}/`; RNG events `cdn_edge_pick` under `logs/rng/events/cdn_edge_pick/...`.

**RNG posture**  
Single-uniform per virtual arrival; `blocks=1`, `draws="1"`; budgets logged and reconciled.

**Key invariants**  
Runs only for `is_virtual=1`; chosen `edge_id` exists in sealed catalogue; log IP/geo consistent with policy if recorded; budgets match trace.

**Downstream consumers**  
S7 audits; S8 includes edge logs/evidence.

---

## S7 - Audit report (deterministic)
**Purpose & scope**  
Aggregate structural and RNG checks across S1-S6 for each `{seed, fingerprint}`; emit `s7_audit_report`.

**Preconditions & gates**  
S0-S6 PASS for the seed/fingerprint; plan tables and RNG logs available.

**Inputs**  
`s1_site_weights`, `s2_alias_*`, `s3_day_effects`, `s4_group_weights`, optional `s5_selection_log`, `s6_edge_log`, RNG logs (`rng_audit_log`, `rng_trace_log`, events), and all policies.

**Outputs & identity**  
`s7_audit_report` at `data/layer1/2B/s7_audit_report/seed={seed}/fingerprint={manifest_fingerprint}/` with overall status and findings.

**RNG**  
None.

**Key invariants**  
PASS only if structural checks (weights sums, alias/index parity), RNG budgets, and routing invariants succeed; required evidence present.

**Downstream consumers**  
S8 requires PASS reports for all seeds before issuing the HashGate.

---

## S8 - Validation bundle & PASS gate
**Purpose & scope**  
Seal Segment 2B for the fingerprint; publish `validation_bundle_2B` + `_passed.flag`.

**Preconditions & gates**  
For the fingerprint: S0 PASS; all discovered seeds have S1-S7 PASS and `s7_audit_report` with PASS; 1B gate still verifies.

**Inputs**  
All `s7_audit_report` files; supporting evidence (e.g., RNG summaries); contracts in `schemas.layer1.yaml`/`schemas.2B.yaml`.

**Outputs & identity**  
`validation_bundle_2B` at `data/layer1/2B/validation/fingerprint={manifest_fingerprint}/` with `index.json`; `_passed.flag` alongside containing `sha256_hex = <bundle_digest>` where the digest is over indexed files in ASCII-lex order (flag excluded).

**RNG**  
None.

**Key invariants**  
All required reports present and PASS; bundle digest matches `_passed.flag`; enforces "no PASS -> no read" for 2B artefacts.

**Downstream consumers**  
Any consumer (5B, runtime routers, enterprise ingestion) must verify `_passed.flag` before reading 2B plan tables or logs.
