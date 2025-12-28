# Layer-1 - Segment 2A - State Overview (S0-S5)

Segment 2A is the civil-time engine. It trusts sealed 1B outputs, assigns authoritative tzids to sites, builds the tz transition cache, checks DST legality, and publishes a HashGate so downstream segments read only after PASS. Inter-country order stays with 1A `s3_candidate_set.candidate_rank`.

## Segment role at a glance
- Enforce the 1B HashGate ("no PASS -> no read") and seal the ingress set 2A may touch.
- Map each site to a provisional tz via polygons and nudges; apply governed overrides to produce authoritative `site_timezones`.
- Compile the IANA tzdb into `tz_timetable_cache` for all tzids in use.
- Produce per-seed DST legality reports and seal everything into `validation_bundle_2A` + `_passed.flag`.

---

## S0 - Gate, manifest, sealed inputs (RNG-free)
**Purpose & scope**  
Verify 1B `_passed.flag` for the target `manifest_fingerprint` and seal the exact artefacts 2A is allowed to read; emit the gate receipt and sealed-input manifest.

**Preconditions & gates**  
`validation_bundle_1B` + `_passed.flag` must match for the fingerprint; otherwise abort ("no PASS -> no read").

**Inputs**  
1B validation bundle/flag; 1B egress `site_locations` `[seed, fingerprint]`; ingress/policy artefacts: `tz_world_2025a`, `tzdb_release`, `tz_overrides`, `tz_nudge`, optional ISO/country refs.

**Outputs & identity**  
`s0_gate_receipt_2A` at `data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/`; `sealed_inputs_v1` at `data/layer1/2A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_v1.parquet` with digests and read scopes.

**RNG**  
None.

**Key invariants**  
No 2A read of `site_locations` without 1B PASS; `sealed_inputs_v1` is the only whitelist; receipt digests equal the sealed manifest; path tokens equal embedded lineage where present.

**Downstream consumers**  
All later 2A states must verify the gate receipt; S5 replays its digests.

---

## S1 - Provisional tz lookup (deterministic)
**Purpose & scope**  
Assign a provisional tzid per site via tz polygons, applying deterministic nudges for edge cases.

**Preconditions & gates**  
S0 PASS; `site_locations` available for all seeds; `tz_world` and `tz_nudge` sealed.

**Inputs**  
`site_locations` `[seed, fingerprint]`; `tz_world_2025a`; `tz_nudge` policy.

**Outputs & identity**  
`s1_tz_lookup` at `data/layer1/2A/s1_tz_lookup/seed={seed}/fingerprint={manifest_fingerprint}/`, one row per site with `tzid_provisional`, optional `nudge_lat_deg`/`nudge_lon_deg`, and provenance.

**RNG**  
None.

**Key invariants**  
1:1 with `site_locations`; nudged points remain inside tile and polygon; every `tzid_provisional` exists in `tz_world`.

**Downstream consumers**  
S2 applies overrides atop these provisional tzids; S4 uses tz usage.

---

## S2 - Overrides and final `site_timezones` (deterministic)
**Purpose & scope**  
Apply governed overrides (site/MCC/country) to S1 tzids; emit authoritative per-site tzids.

**Preconditions & gates**  
S0 PASS; S1 PASS; `tz_overrides` sealed; any MCC mapping required by policy available.

**Inputs**  
`s1_tz_lookup`; `tz_overrides`; `tz_world` for tzid validity; optional merchant/MCC surfaces if policy needs them.

**Outputs & identity**  
`site_timezones` at `data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/`, one row per site with final `tzid`, `tzid_source`, `override_scope`, override ids, and carried `nudge_*`.

**RNG**  
None.

**Key invariants**  
1:1 with `s1_tz_lookup`; overrides valid, in scope, and point to tzids in `tz_world`; if no override, `tzid` equals provisional and `tzid_source="polygon"`.

**Downstream consumers**  
All later segments treat `site_timezones` as the sole tz authority after 2A PASS; S4 counts tz usage.

---

## S3 - Tz timetable cache build (deterministic)
**Purpose & scope**  
Compile the sealed IANA tzdb release into a fingerprint-scoped transition cache for downstream legality and conversions.

**Preconditions & gates**  
S0 PASS; tzdb archive bytes match the sealed digest.

**Inputs**  
`tzdb_release` archive/tag; `tz_world` for tzid validation.

**Outputs & identity**  
`tz_timetable_cache` at `data/layer1/2A/tz_timetable_cache/fingerprint={manifest_fingerprint}/` with `tzdb_release_tag`, archive digest, per-tzid transition records, and `tz_index_digest`.

**RNG**  
None.

**Key invariants**  
Transitions strictly increasing per tzid; offsets are integer minutes; cache digests stable for the release and fingerprint.

**Downstream consumers**  
S4 legality checks; S5 bundle; later segments reuse cache for UTC<->local.

---

## S4 - Legality report (deterministic)
**Purpose & scope**  
Assess DST gaps/folds and tz coverage used by sites; one report per `{seed, fingerprint}`.

**Preconditions & gates**  
S2 PASS (`site_timezones`), S3 PASS (`tz_timetable_cache`).

**Inputs**  
`site_timezones` for the seed/fingerprint; `tz_timetable_cache` for the fingerprint.

**Outputs & identity**  
`s4_legality_report` at `data/layer1/2A/legality_report/seed={seed}/fingerprint={manifest_fingerprint}/s4_legality_report.json`, with status, used tzids, gaps/folds summary, and missing-tz diagnostics.

**RNG**  
None.

**Key invariants**  
Every tzid in `site_timezones` appears in the cache; gaps/folds computed from transitions; status FAIL if any tzid missing.

**Downstream consumers**  
S5 aggregates reports into the bundle; operators inspect for DST issues.

---

## S5 - Validation bundle & PASS gate
**Purpose & scope**  
Seal 2A by bundling gate receipt, `tz_timetable_cache`, and all legality reports; publish `_passed.flag`.

**Preconditions & gates**  
S0-S4 PASS for the fingerprint; every discovered seed has a legality report.

**Inputs**  
`s0_gate_receipt_2A`; `sealed_inputs_v1`; `tz_timetable_cache`; all `s4_legality_report` files for the fingerprint.

**Outputs & identity**  
`validation_bundle_2A` at `data/layer1/2A/validation/fingerprint={manifest_fingerprint}/` with `validation_bundle_index_2A`; `_passed.flag` alongside, containing `sha256_hex = <bundle_digest>` where the digest is over indexed files in ASCII-lex order (flag excluded).

**RNG**  
None.

**Key invariants**  
All required reports present and PASS; cache digest matches manifest; recomputed bundle digest equals `_passed.flag`; gate text enforces "no PASS -> no read" for `site_timezones` and `tz_timetable_cache`.

**Downstream consumers**  
Segments 2B, 3A, 5A/5B, 6A/6B must verify `_passed.flag` before reading 2A egress or cache.
