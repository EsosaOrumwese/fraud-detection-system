```
        LAYER 1 · SEGMENT 2A — STATE S5 (VALIDATION BUNDLE & PASS FLAG)  [NO RNG]

Authoritative inputs (read-only at S5 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_2A @ data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/…
      · proves: 1B gate was verified for this manifest_fingerprint
      · seals: site_timezones, tz_timetable_cache, s4_legality_report as 2A inputs
      · binds: manifest_fingerprint, parameter_hash, verified_at_utc for this 2A fingerprint  

[Schema+Dict]
    - schemas.layer1.yaml               (core primitives; iana_tzid; rfc3339_micros)
    - schemas.2A.yaml                   (shapes for s0_gate_receipt_2A, site_timezones, tz_timetable_cache,
                                         s4_legality_report, validation_bundle_2A, bundle_index_v1, passed_flag)  
    - dataset_dictionary.layer1.2A.yaml (IDs/paths/partitions for site_timezones, tz_timetable_cache,
                                         s4_legality_report, validation_bundle_2A, validation_passed_flag_2A)  :contentReference[oaicite:2]{index=2}
    - artefact_registry_2A.yaml         (bindings/licences/lineage for the same artefacts)  

[S2 Egress · discovery surface]
    - site_timezones
        · schema: schemas.2A.yaml#/egress/site_timezones
        · path:   data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/
        · partitions: [seed, fingerprint]
        · role in S5: **discovery only** — S5 uses it just to discover the seed set SEEDS;
                      it MUST NOT read or copy site rows.  

[S3 Cache · tz timetable]
    - tz_timetable_cache
        · schema: schemas.2A.yaml#/cache/tz_timetable_cache
        · path:   data/layer1/2A/tz_timetable_cache/fingerprint={manifest_fingerprint}/
        · partitions: [fingerprint]
        · role: compiled tzdb transitions for this fingerprint; must be schema-valid, path↔embed correct, non-empty.  

[S4 Evidence · per-seed legality]
    - s4_legality_report
        · schema: schemas.2A.yaml#/validation/s4_legality_report
        · path:   data/layer1/2A/legality_report/seed={seed}/fingerprint={manifest_fingerprint}/s4_legality_report.json
        · partitions: [seed, fingerprint]
        · role: MUST exist with status="PASS" for every discovered seed; copied verbatim into bundle.  

Numeric & RNG posture
    - S5 consumes **no RNG**
    - binary64, RNE, no FMA/FTZ/DAZ; deterministic hashing & selection
    - identity law: path↔embed equality for manifest_fingerprint; write-once; atomic publish; file order non-authoritative  


----------------------------------------------------------------- DAG (S5.1–S5.6 · gate → seed discovery → evidence check → bundle+flag)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S5.1) Verify S0 receipt & fix fingerprint identity
                    - Resolve s0_gate_receipt_2A for this manifest_fingerprint; validate against its schema.
                    - Assert:
                        · manifest_fingerprint field == fingerprint path token,
                        · sealed_inputs[] includes site_timezones, tz_timetable_cache, s4_legality_report IDs.
                    - Treat receipt as sole gate:
                        · S5 SHALL NOT re-hash 1B or 2A bundles,
                        · S5 MAY NOT read artefacts not listed in sealed_inputs.
                    - Fix fingerprint identity for this S5 publish:
                        · manifest_fingerprint (partition key),
                        · parameter_hash (for lineage only),
                        · verified_at_utc (used for optional diagnostics).

[Schema+Dict],
site_timezones
                ->  (S5.2) Discover SEEDS from site_timezones catalogue (discovery only)
                    - Using Dataset Dictionary for `site_timezones`:
                        · list all partitions matching fingerprint={manifest_fingerprint},
                          i.e. all distinct seed values under:
                              data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/
                    - Define:
                        · SEEDS := { all such seed values } (may be empty).
                    - S5 MUST NOT:
                        · read any site_timezones rows,
                        · derive seeds from file listings outside catalogue resolution.
                    - If catalogue resolution fails → 2A-S5-010 INPUT_RESOLUTION_FAILED.

[S5.2],
tz_timetable_cache,
[Schema+Dict]
                ->  (S5.3) Resolve cache & S4 reports; verify evidence completeness
                    - Resolve tz_timetable_cache for this fingerprint:
                        · data/layer1/2A/tz_timetable_cache/fingerprint={manifest_fingerprint}/
                        · validate against its schema anchor; ensure:
                            · manifest_fingerprint field == fingerprint path token,
                            · rle_cache_bytes > 0 and all referenced cache files exist.
                        · Failure → 2A-S5-020 CACHE_INVALID.
                    - For each seed ∈ SEEDS:
                        · resolve s4_legality_report[seed,fingerprint] via Dictionary:
                            data/layer1/2A/legality_report/seed={seed}/fingerprint={manifest_fingerprint}/s4_legality_report.json
                        · validate shape against its schema anchor,
                        · require status == "PASS".
                        · missing or failing report → 2A-S5-030 MISSING_OR_FAILING_S4 (Abort).
                    - Build in-memory evidence set:
                        · E_cache_manifest   (from tz_timetable_cache),
                        · E_legality_reports = { s4_legality_report[seed,fingerprint] | seed ∈ SEEDS }.

(S5.3),
[Schema+Dict]
                ->  (S5.4) Stage bundle root & copy evidence verbatim
                    - Create a temporary bundle root, e.g.:
                        · data/layer1/2A/validation/_tmp.{uuid}/
                    - Copy required evidence into this temp root, byte-for-byte from catalogued sources:
                        · all s4_legality_report[seed,fingerprint] for seed ∈ SEEDS,
                        · a snapshot manifest for tz_timetable_cache (and any required cache descriptor),
                        · optionally checks/metrics JSON (if present in spec).
                    - Guarantee:
                        · every copied file’s bytes == source bytes (else 2A-S5-046 EVIDENCE_NOT_VERBATIM),
                        · all copied paths are inside this temp root; no upward/out-of-root references.

(S5.4)
                ->  (S5.5) Build index.json, compute bundle digest & write _passed.flag_2A
                    - Enumerate all non-flag files under the temp root.
                    - Construct index.json per schemas.2A.yaml#/validation/bundle_index_v1:
                        · files[*].path      = relative path from bundle root (no leading "/", no "."/".."),
                        · files[*].sha256_hex = SHA-256 hex over raw bytes of that file,
                        · entries sorted strictly in ASCII-lex order by path,
                        · no duplicate paths.
                    - Validate index.json shape:
                        · else 2A-S5-040 INDEX_SCHEMA_INVALID, 2A-S5-041 INDEX_NOT_ASCII_LEX, 2A-S5-042 INDEX_PATH_OUT_OF_ROOT,
                          2A-S5-043 INDEX_DUPLICATE_ENTRY, 2A-S5-044 INDEX_UNLISTED_FILE, 2A-S5-045 FLAG_LISTED_IN_INDEX.
                    - Compute bundle digest:
                        · concatenate raw bytes of files listed in index.json in ASCII-lex path order,
                        · compute SHA-256 → <hex64>, encode as lowercase hex.
                    - Write `_passed.flag` into the temp root:
                        · single ASCII line `sha256_hex = <hex64>`,
                        · no additional lines or trailing spaces,
                        · hex is 64 lowercase hex chars.
                    - Validate flag content:
                        · else 2A-S5-051 FLAG_OR_INDEX_HEX_INVALID, 2A-S5-052 FLAG_FORMAT_INVALID,
                          2A-S5-050 FLAG_DIGEST_MISMATCH.

(S5.5),
[Schema+Dict]
                ->  (S5.6) Atomic publish validation_bundle_2A & exit posture
                    - Move the staged bundle root atomically into:
                        · data/layer1/2A/validation/fingerprint={manifest_fingerprint}/
                        · partitions: [fingerprint]; no seed partition.
                    - Ensure:
                        · bundle contents match index.json exactly (no extra/unlisted files),
                        · path↔embed equality holds wherever manifest_fingerprint appears in evidence files,
                        · immutable partition:
                            · if target fingerprint partition already exists with different bytes → 2A-S5-060 IMMUTABLE_PARTITION_OVERWRITE.
                    - Register outputs via Dictionary/Registry:
                        · validation_bundle_2A (bundle root; schema_ref: validation_bundle_2A),
                        · validation_passed_flag_2A (text file _passed.flag; schema_ref: passed_flag).
                    - S5 remains RNG-free and does not mutate any input artefact (site_timezones, tz_timetable_cache, s4_legality_report).

Downstream touchpoints
----------------------
- **Consumers of 2A egress** (2B, 3A, 3B, ingestion gates, scenario runner, model training):
    - MUST, for a given manifest_fingerprint:
        1) resolve data/layer1/2A/validation/fingerprint={manifest_fingerprint}/ via Dictionary,
        2) read index.json and recompute SHA-256 over raw bytes of indexed files in ASCII-lex path order,
        3) read _passed.flag_2A and compare its sha256_hex to their recomputation,
        4) only then read:
            · site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/
            · tz_timetable_cache/fingerprint={manifest_fingerprint}/
       If comparison fails or _passed.flag_2A is missing → **No PASS → No Read** for 2A civil-time surfaces.
- **Enterprise HashGate / governance tooling**:
    - MAY treat validation_bundle_2A + _passed.flag_2A as the single “2A HashGate receipt”
      for this fingerprint, exposing:
        · which tzdb tag & archive were used,
        · which seeds exist and all have status="PASS" in S4,
        · digest stability for audit and replay.
```