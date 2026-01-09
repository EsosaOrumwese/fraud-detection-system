```
                     LAYER 1 - SEGMENT 2A (site_locations → per-site civil time & tzdb cache)  

Authoritative inputs (sealed in S0)
-----------------------------------
[M] Upstream 1B egress & gates:
    - validation_bundle_1B              @ [fingerprint]
    - validation_passed_flag_1B         @ [fingerprint]  (_passed.flag; HashGate for 1B)
    - site_locations                    @ [seed, fingerprint]
      · final per-site geometry from 1B (lat_deg, lon_deg)
      · PK: (merchant_id, legal_country_iso, site_order); order-free; write-once

[R] Reference civil-time & ID surfaces:
    - iso3166_canonical_2024            (ISO-2 FK; country_iso domain)
    - tz_world_2025a                    (TZ polygons; WGS84; tzid coverage/domain)
    - tzdb_release                      (pinned IANA tzdata archive: tag + archive_sha256)
      · sole authority for UTC↔local transitions per tzid

[P] Policy / hyperparams:
    - tz_overrides                      (governed overrides: per-site / per-MCC / per-country tzid rules)
    - tz_nudge                          (ε-nudge magnitude + strategy for border/ambiguous sites)

[N] Numeric & lineage posture:
    - numeric_policy.json, math_profile_manifest.json
      · IEEE-754 binary64; RNE; FMA-off; deterministic libm on decision paths
    - Layer-1 lineage & HashGate law:
      · manifest_fingerprint from sealed inputs/config
      · path↔embed equality for {seed, manifest_fingerprint, parameter_hash}
      · partitions are write-once; stage → fsync → single atomic move; file order non-authoritative
    - 2A itself consumes **no RNG**; all states are deterministic functions of sealed inputs


DAG
---
(M,R,P,N) --> (S0) Gate-in & sealed inputs (no RNG)
                    - Verify 1B’s fingerprint gate for this manifest_fingerprint:
                        * open validation_bundle_1B/ @ [fingerprint]
                        * read index.json (relative, ASCII-sortable paths; one entry per non-flag file)
                        * recompute SHA-256 over raw bytes in ASCII-lex order (flag excluded)
                        * compare to _passed.flag (sha256_hex = <hex64>)
                        * **No PASS → No read** of site_locations for 2A
                    - Resolve all 2A inputs via Dictionary (no literal paths):
                        * 1B egress: site_locations @ [seed, fingerprint]
                        * tz_world_2025a, tzdb_release, tz_overrides, tz_nudge, iso3166_canonical_2024
                    - Bind 2A identity for this fingerprint:
                        * manifest_fingerprint (path token ↔ embedded field equality),
                        * parameter_hash (parameter pack for civil-time layer)
                    - Emit:
                        * s0_gate_receipt_2A      @ [fingerprint]
                            · proves 1B PASS
                            · records 2A’s sealed_inputs[] for this fingerprint
                            · carries parameter_hash + verified_at_utc
                        * sealed_inputs_2A        @ [fingerprint]
                            · tabular inventory of all 2A inputs (ids, paths, schema_refs, sha256, licence, retention)
                    - S0 consumes **no RNG**; it gates & seals; does not read 1B row data or tzdb internals

                                      |
                                      | s0_gate_receipt_2A (gate & identity)
                                      v

             (S1) Provisional TZ lookup — geometry-only  [NO RNG]
                inputs: site_locations @ [seed, fingerprint],
                        tz_world_2025a (tz polygons),
                        tz_nudge policy (ε border rules),
                        iso3166_canonical_2024 (FK domain)
                -> s1_tz_lookup @ [seed, fingerprint]
                     - PK/sort: (merchant_id, legal_country_iso, site_order)
                     - per-site tzid_provisional from tz polygons:
                         · point-in-polygon (lat_deg, lon_deg) → tzid
                         · if ambiguous/on-border → apply deterministic ε-nudge per tz_nudge, then re-check
                     - records nudge_lat_deg, nudge_lon_deg (nullable)
                     - 1:1 with site_locations for this (seed, fingerprint)
                # S1 does not read tzdb_release; no overrides; no RNG

             (S2) Overrides & final tzid — per-site civil time egress  [NO RNG]
                inputs: s1_tz_lookup @ [seed, fingerprint],
                        tz_overrides (policy),
                        tz_world_2025a (tzid validity),
                        optional merchant_mcc_map (if sealed)
                -> site_timezones @ [seed, fingerprint]  (2A egress)
                     - PK/sort: (merchant_id, legal_country_iso, site_order)
                     - columns (schema-owned) include:
                         · tzid            (final IANA timezone)
                         · tzid_source     ∈ {"polygon","override"}
                         · override_scope  ∈ {"site","mcc","country"} | null
                         · nudge_lat_deg, nudge_lon_deg (echo from S1)
                         · created_utc     == s0_gate_receipt_2A.verified_at_utc
                     - Deterministic override engine:
                         · start from tzid_provisional
                         · gather active overrides (expiry ≥ S0 verified_at_utc):
                               site-level > mcc-level > country-level
                         · apply highest-precedence override (if any), else keep polygon tzid
                         · validate tzid_final ∈ tz_world_2025a domain (iana_tzid)
                     - 1:1 with s1_tz_lookup; S2 consumes **no RNG**

                                      |
                                      | tzid set used by sites (TZ_USED), tzdb_release tag
                                      v

             (S3) TZ timetable cache compile (tzdb → fingerprint cache)  [NO RNG]
                inputs: tzdb_release (IANA archive), tz_world_2025a (tzid domain), s0_gate_receipt_2A
                -> tz_timetable_cache @ [fingerprint]
                     - partitions: [fingerprint]
                     - compiles tzdb into canonical per-tzid transition series:
                         · strictly increasing UTC instants,
                         · integer UTC offsets in bounded minutes range
                     - coverage:
                         · every tzid in tz_world_2025a appears in the index (superset permitted)
                     - emits manifest with:
                         · manifest_fingerprint   == path token
                         · tzdb_release_tag       (e.g. "2025a")
                         · tzdb_archive_sha256
                         · tz_index_digest        (SHA-256 over canonical tz-index bytes)
                         · rle_cache_bytes, created_utc = S0.receipt.verified_at_utc
                     - write-once; partitioned [fingerprint]; no seed/run_id dimension

                                      |
                                      | site_timezones @ [seed,fingerprint]
                                      | tz_timetable_cache @ [fingerprint]
                                      v

             (S4) TZ legality & DST windows (per-seed report)  [NO RNG]
                inputs: site_timezones[seed,fingerprint],
                        tz_timetable_cache[fingerprint],
                        s0_gate_receipt_2A
                -> s4_legality_report @ [seed, fingerprint]
                     - one JSON per (seed, manifest_fingerprint)
                     - computes DST legality from tz_timetable_cache for the tzids actually used:
                         · sites_total      = |site_timezones|
                         · tzids_total      = |TZ_USED|
                         · gap_windows_total, fold_windows_total across all tzids
                     - checks:
                         · every tzid in site_timezones exists in tz_timetable_cache
                         · per-tzid gap/fold windows computed from transition series
                         · status = "PASS" iff coverage OK and no structural violations
                     - emits report with:
                         · manifest_fingerprint, seed
                         · counts { sites_total, tzids_total, gap_windows_total, fold_windows_total }
                         · missing_tzids[] (if any), status, generated_utc = S0.receipt.verified_at_utc
                     - read-only w.r.t. site_timezones & cache; no RNG

                                      |
                                      | tz_timetable_cache @ [fingerprint]
                                      | all s4_legality_report[seed,fingerprint] for this fingerprint
                                      v

             (S5) Validation bundle & PASS flag for 2A (fingerprint-scoped)  [NO RNG]
                inputs: s0_gate_receipt_2A,
                        tz_timetable_cache[fingerprint],
                        s4_legality_report[seed,fingerprint] for all seeds that have site_timezones
                -> validation_bundle_2A/      @ [fingerprint]
                     - stage MANIFEST + tz_timetable_cache manifest + s4_legality_report[*] + any checks/metrics
                     - build index.json:
                         · list every non-flag file exactly once
                         · path = relative; ASCII-lex-sortable; no ".." or absolute paths
                         · per-file sha256_hex = SHA-256(file bytes)
                     - compute bundle digest:
                         · concat raw bytes of files in ASCII-lex(index.path) order (flag excluded)
                         · SHA-256 → <hex64>
                -> validation_passed_flag_2A   @ [fingerprint]
                     - _passed.flag content: `sha256_hex = <hex64>`
                     - fingerprint-scoped HashGate for all 2A civil-time surfaces
                     - publish via stage → fsync → single atomic move; write-once; file order non-authoritative

Downstream touchpoints
----------------------
- **Any consumer of 2A civil-time surfaces** (2B arrival mechanics, 3A/3B fraud posture, ingestion gate, scenario runner, model training):
    1) locate `data/layer1/2A/validation/fingerprint={manifest_fingerprint}/`,
    2) read `index.json` and recompute SHA-256 over the listed files in ASCII-lex `path` order (flag excluded),
    3) read `_passed.flag` and compare the `sha256_hex`,
    4) only then read:
         · site_timezones       @ [seed, fingerprint]
         · tz_timetable_cache   @ [fingerprint]
       **No PASS → No Read** for all 2A civil-time outputs.

- **Later layers needing local civil time or DST semantics**:
    - Use site_timezones (per-site tzid) + tz_timetable_cache (per-tzid transitions)
      to map any UTC timestamp to local civil time, offset, and (gap/fold) classification
      under the same manifest_fingerprint that 2A S5 has certified.

Legend
------
(Sx) = state
[name @ partitions] = artefact + its partition keys
[NO RNG] = state consumes no RNG; all 2A states are RNG-free
HashGate for a segment = fingerprint-scoped validation_bundle + _passed.flag; **No PASS → No Read** of that segment’s egress
Order authority for cross-country sequencing remains in 1A S3 (`s3_candidate_set.candidate_rank`); 2A encodes no inter-country order.
```
