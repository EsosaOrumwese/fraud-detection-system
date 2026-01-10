```
        LAYER 1 · SEGMENT 2A — STATE S3 (TZ TIMETABLE CACHE COMPILE)  [NO RNG]

Authoritative inputs (read-only at S3 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_2A @ data/layer1/2A/s0_gate_receipt/manifest_fingerprint={manifest_fingerprint}/…
      · proves: 1B PASS gate verified for this manifest_fingerprint (via 1B bundle + _passed.flag)
      · seals: tzdb_release + tz_world_2025a as the only TZ inputs S3 may read
      · binds: manifest_fingerprint, parameter_hash, verified_at_utc for this 2A run

[Schema+Dict]
    - schemas.layer1.yaml               (core types, int ranges, iana_tzid, rfc3339_micros)
    - schemas.2A.yaml                   (shape for tz_timetable_cache manifest, s0_gate_receipt_2A)
    - schemas.ingress.layer1.yaml       (shape for tz_world_2025a, tzdb_release descriptors)
    - dataset_dictionary.layer1.2A.yaml (IDs/paths/partitions for tz_timetable_cache, s0_gate_receipt_2A)
    - artefact_registry_2A.yaml         (bindings for tzdb_release artefact, tz_world_2025a, tz_timetable_cache; licences/TTLs)

[TZ Archive · tzdb_release]
    - tzdb_release
        · schema: schemas.ingress.layer1.yaml#/tzdb_release_v1
        · fields: { tag (e.g. "2025a"), archive_uri, archive_sha256_hex, format }
        · sealed by S0: exact archive digest + tag this fingerprint must use
        · role: single source of truth for offsets/transition instants per tzid

[Ingress TZ polygons · TZID domain]
    - tz_world_2025a
        · schema: schemas.ingress.layer1.yaml#/tz_world_2025a
        · path:   reference/spatial/tz_world/2025a/tz_world.parquet
        · CRS: WGS84
        · role: authoritative *set of tzids* the programme recognises; S3 will require
                 that every tzid in this surface appears in the compiled index

Numeric & RNG posture
    - S3 consumes **no RNG**
    - binary64, RNE, no FMA/FTZ/DAZ; deterministic parse + compile
    - identity law: path↔embed equality for {manifest_fingerprint}; write-once; atomic publish; file order non-authoritative


----------------------------------------------------------------- DAG (S3.1–S3.6 · gate → tzdb parse → canonical index → fingerprint cache)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S3.1) Verify S0 gate & fix fingerprint identity
                    - Resolve s0_gate_receipt_2A for this manifest_fingerprint via Dictionary.
                    - Validate receipt schema:
                        · manifest_fingerprint present and equals fingerprint path token,
                        · parameter_hash present (coherent with Layer-1 law),
                        · sealed_inputs[] includes tzdb_release + tz_world_2025a.
                    - Treat receipt as sole gate:
                        · S3 SHALL NOT re-hash 1B or 2A bundles,
                        · S3 MAY NOT read TZ surfaces not listed as sealed inputs.
                    - Fix run identity:
                        · fingerprint = manifest_fingerprint (partition key for this cache),
                        · verified_at_utc = S0.receipt.verified_at_utc (used as created_utc).

[S3.1],
[Schema+Dict],
tzdb_release,
tz_world_2025a
                ->  (S3.2) Resolve sealed TZ inputs & basic sanity
                    - Resolve tzdb_release via Registry/Dictionary:
                        · verify archive_uri, archive_sha256_hex match S0’s sealed values,
                        · assert tag (e.g. "2025a") is non-empty and stable.
                    - Resolve tz_world_2025a via Dictionary:
                        · treat as immutable WGS84 dataset; no geometry ops in S3, only tzid domain.
                    - Extract tzid domain:
                        · TZID_world = { tzid | distinct tz_world_2025a.tzid }.
                        · ensure no null/empty tzid; enforce iana_tzid pattern per schema.
                    - Confirm S3 output slot exists in Dictionary:
                        · tz_timetable_cache entry with schema_ref, path family, partitions [manifest_fingerprint],
                          writer policy and licence present.

[S3.2],
tzdb_release
                ->  (S3.3) Parse tzdb archive → raw per-tzid rules
                    - Fetch tzdb archive bytes from archive_uri; verify SHA-256 == archive_sha256_hex.
                    - Parse archive into an internal, deterministic representation:
                        · for each tzid in archive: its rules/transitions as per IANA tzdb semantics.
                    - Enforce:
                        · all tzids in archive obey iana_tzid pattern,
                        · no duplicate rule sets for the same tzid,
                        · parse errors (unknown format, corrupt archive) → structural error, ABORT.

[S3.3]
                ->  (S3.4) Derive canonical transition series per tzid
                    - For each tzid in the parsed archive:
                        · compute an ordered list of UTC transition instants:
                            · strictly increasing sequence of instants (no ties),
                        · compute effective UTC offsets in integral minutes for each segment:
                            · offset_minutes ∈ [min_offset, max_offset] (e.g. −900..+900),
                            · no NaN/Inf; non-finite values → error.
                        · coalesce redundant transitions:
                            · if two consecutive transitions yield same effective offset, collapse as needed.
                    - Build a provisional per-tzid map:
                        · transitions[tzid] = [(t0, offset0), (t1, offset1), …] in strictly increasing t order.

[S3.4],
tz_world_2025a
                ->  (S3.5) Canonical index & coverage checks
                    - Build canonical index structure:
                        · sort tzids ASCII-lexicographically,
                        · for each tzid, ensure its transitions list is sorted by UTC instant ascending,
                        · encode the index using a pinned, deterministic encoding (e.g. fixed endianness, no locale).
                    - Compute tz_index_digest:
                        · canonical_bytes = encode(transitions by sorted tzid, then per-tzid transitions),
                        · tz_index_digest = SHA-256(canonical_bytes) (lowercase hex64).
                    - Coverage checks:
                        · for every tzid ∈ TZID_world:
                            · assert tzid ∈ transitions (archive must cover all programme TZs),
                        · optionally allow archive to contain tzids not present in TZID_world (superset OK),
                        · any tzid missing from transitions → E_S3_TZID_MISSING, ABORT.

[S3.5],
[Schema+Dict]
                ->  (S3.6) Materialise tz_timetable_cache (fingerprint-scoped) & exit posture
                    - Write tz_timetable_cache under:
                        · data/layer1/2A/tz_timetable_cache/manifest_fingerprint={manifest_fingerprint}/
                        · partitions: [manifest_fingerprint]
                        · format: as per Dictionary (e.g. Parquet + sidecar manifest JSON).
                    - Emit at least a manifest row/object per schema:
                        · manifest_fingerprint  == fingerprint path token,
                        · tzdb_release_tag      == tzdb_release.tag,
                        · tzdb_archive_sha256   == tzdb_release.archive_sha256_hex,
                        · tz_index_digest       == computed digest from S3.5,
                        · rle_cache_bytes (or equivalent size counter) == size of the encoded cache payload,
                        · created_utc           == S0.receipt.verified_at_utc.
                    - Persist the canonical index/payload bytes:
                        · only for this fingerprint; no seed partition,
                        · writer policy obeys Dictionary (single writer, no compaction).
                    - Enforce:
                        · schema validity against schemas.2A.yaml#/plan/tz_timetable_cache,
                        · path↔embed equality for manifest_fingerprint,
                        · write-once partition: publish via stage → fsync → single atomic move;
                          any re-publish with different bytes MUST fail.
                    - S3 consumes no RNG and mutates no input surfaces; it is purely a deterministic compile step.

Downstream touchpoints
----------------------
- **2A.S4 — Legality report (DST gaps/folds)**:
    - Reads tz_timetable_cache for this fingerprint,
      combines with site_timezones[seed, manifest_fingerprint] to:
        · compute gap/fold windows per tzid,
        · detect missing tzids,
        · emit s4_legality_report[seed, manifest_fingerprint] (PASS/FAIL).

- **2A.S5 — 2A validation bundle & PASS flag**:
    - For the same fingerprint, packages:
        · tz_timetable_cache manifest,
        · all s4_legality_report[seed, manifest_fingerprint] for seeds that have site_timezones,
      into a fingerprint-scoped validation bundle,
      computes the ASCII-lex + SHA-256 digest over bundle files,
      and writes `_passed.flag` that downstream must verify before reading
      site_timezones / tz_timetable_cache.
```