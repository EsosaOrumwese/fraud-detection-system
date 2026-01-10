```
        LAYER 1 · SEGMENT 2A — STATE S2 (OVERRIDES & FINAL TZID)  [NO RNG]

Authoritative inputs (read-only at S2 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_2A @ data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/…
      · proves: 1B PASS gate verified for this manifest_fingerprint (via 1B bundle + _passed.flag)
      · seals: allowed 2A inputs (incl. s1_tz_lookup, tz_overrides, tz_world_2025a, tz_nudge, optional merchant_mcc_map)
      · binds: manifest_fingerprint, parameter_hash, verified_at_utc for this 2A run

[Schema+Dict]
    - schemas.layer1.yaml               (iana_tzid type, iso2, rfc3339_micros)
    - schemas.1B.yaml                   (shape for site_locations — used via S1 contract, not read directly here)
    - schemas.2A.yaml                   (shapes for s0_gate_receipt_2A, s1_tz_lookup, site_timezones, tz_overrides)
    - schemas.ingress.layer1.yaml       (tz_world_2025a, iso3166_canonical_2024, optional merchant_mcc_map)
    - dataset_dictionary.layer1.2A.yaml (IDs/paths/partitions for s1_tz_lookup, site_timezones, tz_overrides, s4_legality_report)
    - artefact_registry_2A.yaml         (bindings/licences for tz_overrides, tz_world_2025a, merchant_mcc_map, site_timezones)

[S1 Output · geometry-only tz guess]
    - s1_tz_lookup
        · schema: schemas.2A.yaml#/plan/s1_tz_lookup
        · path:   data/layer1/2A/s1_tz_lookup/seed={seed}/fingerprint={manifest_fingerprint}/
        · partitions: [seed, fingerprint]
        · PK/sort: [merchant_id, legal_country_iso, site_order]
        · contents: tzid_provisional, nudge_lat_deg, nudge_lon_deg (+ lat_deg, lon_deg echo)

[Policy · overrides]
    - tz_overrides
        · schema: schemas.2A.yaml#/policy/tz_overrides_v1
        · path:   config/layer1/2A/timezone/tz_overrides.yml (Dictionary/Registry-owned)
        · rows: { scope, target, tzid, expiry_yyyy_mm_dd?, comment? }
        · scope ∈ {"site","mcc","country"}; precedence: site > mcc > country

[Ingress TZ domain]
    - tz_world_2025a
        · schema: schemas.ingress.layer1.yaml#/tz_world_2025a
        · path:   reference/spatial/tz_world/2025a/tz_world.parquet
        · role: authoritative set of tzids allowed in this programme

[Optional] Merchant → MCC mapping
    - merchant_mcc_map (only if sealed in S0)
        · schema: schemas.ingress.layer1.yaml#/merchant_mcc_map_…
        · role: map merchant_id → mcc for MCC-scope overrides
        · if not sealed: MCC-scope overrides are unusable; using them MUST fail

Numeric & RNG posture
    - S2 consumes **no RNG**
    - binary64, RNE, no FMA/FTZ/DAZ; deterministic behaviour for fixed inputs
    - identity law: path↔embed equality for {seed, manifest_fingerprint}; write-once; atomic publish


----------------------------------------------------------------- DAG (S2.1–S2.6 · gate → override index → per-site resolution → site_timezones)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S2.1) Verify S0 gate & fix run identity
                    - Resolve s0_gate_receipt_2A via Dictionary for this manifest_fingerprint.
                    - Validate receipt schema:
                        · manifest_fingerprint present and equals fingerprint path token,
                        · parameter_hash present and coherent with Layer-1 rules,
                        · sealed_inputs[] includes s1_tz_lookup, tz_overrides, tz_world_2025a
                          (and merchant_mcc_map if MCC overrides are intended).
                    - Treat receipt as the sole consumption gate:
                        · S2 SHALL NOT re-hash 1B bundles,
                        · S2 MAY NOT read surfaces not listed as sealed inputs.
                    - Fix run identity (seed, manifest_fingerprint) for this S2 publish.
                    - Fix cut-off date for overrides:
                        · override is active only if expiry_yyyy_mm_dd is null or ≥ date(verified_at_utc).

[S2.1],
[Schema+Dict]
                ->  (S2.2) Resolve inputs & structural sanity
                    - Resolve via Dataset Dictionary (no literal paths):
                        · s1_tz_lookup @ data/layer1/2A/s1_tz_lookup/seed={seed}/fingerprint={manifest_fingerprint}/
                        · tz_overrides  @ config/layer1/2A/timezone/tz_overrides.yml (or equivalent path family)
                        · tz_world_2025a @ reference/spatial/tz_world/2025a/tz_world.parquet
                        · merchant_mcc_map (only if sealed and referenced by S0)
                    - Enforce partitions:
                        · s1_tz_lookup only under this (seed, fingerprint),
                        · tz_world_2025a and tz_overrides treated as immutable reference surfaces.
                    - Validate shapes:
                        · s1_tz_lookup conforms to its schema (PK, partitions, required cols),
                        · tz_overrides conforms (scope enum, target format, tzid domain, optional expiry),
                        · tz_world_2025a carries a set of tzids forming the authoritative TZ domain.
                    - Determine MCC override capability:
                        · if merchant_mcc_map is sealed & valid → MCC overrides allowed,
                        · else → MCC overrides considered unusable; any attempt to enforce them MUST be treated as error.

[Policy · tz_overrides],
(optional merchant_mcc_map)
                ->  (S2.3) Build override index (by scope, with dedup guards)
                    - Partition overrides by scope:
                        · site-scope:    rules targeting specific (merchant_id, legal_country_iso, site_order) or equivalent key.
                        · mcc-scope:     rules targeting MCC values (only if merchant_mcc_map sealed).
                        · country-scope: rules targeting legal_country_iso.
                    - For each (scope, target):
                        - Collect rules whose expiry_yyyy_mm_dd is null or ≥ S0.verified_at_utc → “active” set.
                        - Enforce dedup:
                            · at most one active override per (scope,target),
                            · if >1 active rule for same (scope,target) → structural error (e.g. E_S2_DUP_OVERRIDE), ABORT.
                    - Build lookups:
                        · site_overrides[target_site_key]    → {tzid, expiry, comment}
                        · mcc_overrides[target_mcc]          → {tzid, expiry, comment} (if MCC allowed)
                        · country_overrides[legal_country_iso] → {tzid, expiry, comment}
                    - Validate override tzids against tz_world_2025a domain where possible; reject unknown tzids early.

[S2.2],
[S2.3],
tz_world_2025a,
(optional merchant_mcc_map)
                ->  (S2.4) Per-site override resolution (site, then MCC, then country; deterministic precedence)
                    - Iterate s1_tz_lookup in writer sort [merchant_id, legal_country_iso, site_order].
                    - For each site row k = (merchant_id, legal_country_iso, site_order):
                        · Base tzid = tzid_provisional from S1.
                        · Derive effective override candidates:
                            1) Site-scope:
                                · look up k in site_overrides; if present → site_override.
                            2) MCC-scope (if MCC allowed):
                                · find mcc = merchant_mcc_map[merchant_id] (if mapping present),
                                · look up mcc in mcc_overrides; if present → mcc_override.
                            3) Country-scope:
                                · look up legal_country_iso in country_overrides; if present → country_override.
                        · Apply precedence:
                            - if site_override exists → chosen_override = site_override, override_scope="site".
                            - else if mcc_override exists → chosen_override = mcc_override, override_scope="mcc".
                            - else if country_override exists → chosen_override = country_override, override_scope="country".
                            - else → chosen_override = null, override_scope = null.
                        · Determine final tzid:
                            - if chosen_override != null:
                                · tzid_final = chosen_override.tzid,
                                · tzid_source = "override".
                            - else:
                                · tzid_final = tzid_provisional,
                                · tzid_source = "polygon".
                        · Validate tzid_final:
                            - conforms to iana_tzid pattern (schema),
                            - exists in tz_world_2025a tzid domain (no unknown/typo tzid).
                        - On any failure (unknown tzid, MCC override used without merchant_mcc_map, etc.) → hard error.

(S2.4)
                ->  (S2.5) Assemble site_timezones frame (1:1 with S1)
                    - For each s1_tz_lookup row, construct exactly one site_timezones row:
                        · keys:   merchant_id, legal_country_iso, site_order
                        · lineage: seed, manifest_fingerprint (embedded; MUST equal path tokens where present)
                        · tzid:   tzid_final from S2.4
                        · tzid_source: "override" or "polygon"
                        · override_scope: "site" | "mcc" | "country" | null
                        · nudge_lat_deg, nudge_lon_deg:
                            - copied verbatim from s1_tz_lookup (NOT recomputed),
                            - non-null indicates a geometric nudge occurred in S1.
                        · created_utc:
                            - MUST equal S0.receipt.verified_at_utc (NOT wall-clock “now”).
                        · any additional audit fields required by schema (e.g. override_id, comments) are filled deterministically.
                    - Enforce bijection:
                        · |site_timezones| == |s1_tz_lookup| for this (seed, fingerprint),
                        · no missing or extra site keys vs s1_tz_lookup,
                        · any site key seen in s1_tz_lookup appears exactly once in site_timezones.

(S2.5),
[Schema+Dict]
                ->  (S2.6) Materialise site_timezones & exit posture
                    - Write site_timezones under:
                        · data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/
                        · partitions: [seed, fingerprint]
                        · writer sort: [merchant_id, legal_country_iso, site_order]
                        · format: Parquet
                    - Enforce:
                        · schema validity against schemas.2A.yaml#/egress/site_timezones (columns_strict),
                        · PK uniqueness on [merchant_id, legal_country_iso, site_order],
                        · path↔embed equality for lineage fields (seed, manifest_fingerprint),
                        · write-once partitions; publish via stage → fsync → single atomic move;
                          re-publishing with different bytes MUST fail.
                    - S2 remains RNG-free; it does not mutate s1_tz_lookup, tz_world_2025a, tz_overrides, or merchant_mcc_map.

Downstream touchpoints
----------------------
- **2A.S3 — tz_timetable_cache (tzdb compile)**:
    - Reads the set of tzids actually used in site_timezones to decide which tzids
      must appear in the compiled timetable cache for this fingerprint.
    - Treats site_timezones as authoritative per-site tzid source.

- **2A.S4 — legality report**:
    - Uses site_timezones plus tz_timetable_cache to:
        · compute gap/fold windows per tzid,
        · detect missing tzids in the cache,
        · emit s4_legality_report[seed,fingerprint] (PASS / FAIL).

- **2A.S5 — 2A validation bundle & PASS flag**:
    - For a given manifest_fingerprint, ensures:
        · every seed that has site_timezones also has a PASS s4_legality_report,
      then packages those reports + cache manifest into a fingerprint-scoped bundle
      and writes the 2A `_passed.flag` that gates downstream consumers.
```