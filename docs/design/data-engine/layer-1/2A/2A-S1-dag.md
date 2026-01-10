```
        LAYER 1 · SEGMENT 2A — STATE S1 (PROVISIONAL TZ LOOKUP)  [NO RNG]

Authoritative inputs (read-only at S1 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_2A @ data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/…
      · proves: 1B PASS gate verified for this manifest_fingerprint (via 1B bundle + _passed.flag)
      · seals: allowed inputs for 2A (incl. site_locations, tz_world_2025a, tz_nudge)
      · binds: manifest_fingerprint, parameter_hash for this 2A run

[Schema+Dict]
    - schemas.layer1.yaml               (layer-wide primitives, iana_tzid, iso2, rfc3339_micros)
    - schemas.1B.yaml                   (1B egress: site_locations)
    - schemas.2A.yaml                   (2A shapes: s0_gate_receipt_2A, s1_tz_lookup, tz_nudge_v1)
    - schemas.ingress.layer1.yaml       (tz_world_2025a polygons)
    - dataset_dictionary.layer1.1B.yaml (IDs/paths/partitions for site_locations)
    - dataset_dictionary.layer1.2A.yaml (IDs/paths/partitions for s0_gate_receipt_2A, s1_tz_lookup)
    - artefact_registry_2A.yaml         (bindings for tz_world_2025a, tz_nudge, s1_tz_lookup, licences/TTLs)

[1B Egress · per-site geometry]
    - site_locations
        · schema: schemas.1B.yaml#/egress/site_locations
        · path: data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/
        · partitions: [seed, fingerprint]
        · PK/writer sort: [merchant_id, legal_country_iso, site_order]
        · role: final per-site (lat_deg, lon_deg) at 1B; order-free; write-once; atomic publish

[Ingress TZ polygons]
    - tz_world_2025a
        · schema: schemas.ingress.layer1.yaml#/tz_world_2025a
        · path: reference/spatial/tz_world/2025a/tz_world.parquet
        · CRS: WGS84; non-empty; authoritative tzid geometry
        · role: point-in-polygon authority for tzid membership

[Policy · ε-nudge at borders]
    - tz_nudge (config/layer1/2A/timezone/tz_nudge.yml)
        · schema: schemas.2A.yaml#/policy/tz_nudge_v1
        · content: ε (strictly > 0) and units; nudge strategy at ambiguous/border sites
        · role: deterministic tie-break when geometry alone is ambiguous

Numeric & RNG posture (inherited)
    - S1 consumes **no RNG**
    - binary64, RNE, no FMA/FTZ/DAZ; deterministic geometry decisions
    - Identity & Path Law: path↔embed equality for {seed, manifest_fingerprint}; write-once; atomic publish


----------------------------------------------------------------- DAG (S1.1–S1.6 · gate → inputs → per-site PIP+nudge → s1_tz_lookup)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S1.1) Verify S0 gate & fix run identity
                    - Resolve s0_gate_receipt_2A via Dictionary for the target fingerprint.
                    - Validate receipt schema:
                        · manifest_fingerprint present and equals fingerprint path token,
                        · parameter_hash present and consistent with Layer-1 rules,
                        · sealed_inputs[] includes site_locations, tz_world_2025a, tz_nudge.
                    - Use receipt as the sole gate:
                        · S1 SHALL NOT re-hash 1A/1B bundles,
                        · S1 MAY NOT read site_locations unless this receipt is valid for the fingerprint.
                    - Fix run selection: (seed, manifest_fingerprint) for this S1 publish.

[S0 Gate & Identity],
[Schema+Dict],
[Ingress TZ polygons],
[Policy · tz_nudge]
                ->  (S1.2) Resolve sealed inputs & basic sanity checks
                    - Resolve inputs strictly via Dataset Dictionary (no literal paths):
                        · site_locations @ data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/
                        · tz_world_2025a @ reference/spatial/tz_world/2025a/tz_world.parquet
                        · tz_nudge @ config/layer1/2A/timezone/tz_nudge.yml
                    - Enforce partition discipline:
                        · read site_locations only for this (seed, fingerprint),
                        · treat tz_world_2025a as immutable, WGS84, non-empty.
                    - Validate tz_nudge:
                        · ε strictly > 0; units as per policy schema.
                    - Build minimal in-memory indices as needed:
                        · tz_world index keyed by tzid with prepared PIP predicates per polygon/multipolygon.

[Schema+Dict],
site_locations,
tz_world_2025a,
tz_nudge
                ->  (S1.3) Per-site loop · raw PIP classification
                    - Iterate site_locations in writer sort [merchant_id, legal_country_iso, site_order].
                    - For each site row:
                        · read (lat_deg, lon_deg, merchant_id, legal_country_iso, site_order),
                        · run point-in-polygon against tz_world_2025a:
                            · collect candidate tzids where (lat, lon) is inside polygon(s),
                            · classify the site as:
                                · unambiguous (exactly one tzid),
                                · ambiguous/on-border (zero or multiple tzids).

(S1.3),
tz_nudge
                ->  (S1.4) Apply ε-nudge for ambiguous/border sites (deterministic tie-break)
                    - For sites with **exactly one** tzid from PIP:
                        · set tzid_provisional = that tzid,
                        · set nudge_lat_deg = null, nudge_lon_deg = null.
                    - For ambiguous/border cases:
                        · apply at most one ε-nudge per site:
                            · adjust (lat, lon) by the policy-defined ε in a deterministic direction
                              (e.g., along normal of boundary or pre-defined vector),
                            · recompute PIP against tz_world_2025a.
                        - If post-nudge classification yields a single tzid:
                            · set tzid_provisional = that tzid,
                            · record (nudge_lat_deg, nudge_lon_deg) = (lat_nudged - lat_original,
                                                                     lon_nudged - lon_original).
                        - If still ambiguous / no tzid after the bounded ε-nudge:
                            · treat as structural error (e.g., E_S1_TZ_UNDECIDED) and ABORT the run.

(S1.3–S1.4)
                ->  (S1.5) Assemble s1_tz_lookup frame (bijective projection)
                    - For each input site row (from site_locations), build exactly one output row:
                        · keys:  (merchant_id, legal_country_iso, site_order)
                        · lineage: seed, manifest_fingerprint (embedded if present; MUST equal path tokens)
                        · geometry echo: lat_deg, lon_deg as in site_locations
                        · tzid_provisional (chosen in S1.3/S1.4)
                        · nudge_lat_deg, nudge_lon_deg (nullable; non-null only when ε-nudge applied)
                        · created_utc / run metadata if required by schema.
                    - Enforce bijection:
                        · |s1_tz_lookup| == |site_locations| for this (seed, fingerprint),
                        · no missing or extra keys vs site_locations,
                        · PK uniqueness on [merchant_id, legal_country_iso, site_order].

(S1.5),
[Schema+Dict]
                ->  (S1.6) Materialise s1_tz_lookup & exit posture
                    - Write s1_tz_lookup under:
                        · data/layer1/2A/s1_tz_lookup/seed={seed}/fingerprint={manifest_fingerprint}/
                        · partitions: [seed, fingerprint]
                        · writer sort: [merchant_id, legal_country_iso, site_order]
                        · format: Parquet
                    - Enforce:
                        · schema validity against schemas.2A.yaml#/plan/s1_tz_lookup (columns_strict),
                        · path↔embed equality for lineage fields (seed, manifest_fingerprint),
                        · single-writer & immutability (write-once; re-publish must be byte-identical).
                    - S1 emits **no RNG logs** and mutates no inputs; it is purely deterministic given:
                        · S0 receipt,
                        · site_locations,
                        · tz_world_2025a,
                        · tz_nudge.

Downstream touchpoints
----------------------
- **2A.S2 (Overrides & finalisation)**:
    - Treats s1_tz_lookup as authoritative geometry-only plan:
        · consumes tzid_provisional and nudge_*,
        · applies tz_overrides (site/mcc/country precedence) to produce final site_timezones.
    - Requires 1:1 key coverage with s1_tz_lookup; never re-reads site_locations.

- **2A.S3/S4/S5 (timetables, legality, bundle)**:
    - Depend on S2 egress (site_timezones) and tzdb_release/tz_timetable_cache,
      but their selection identity is the same (seed, manifest_fingerprint) that S1 established.
```