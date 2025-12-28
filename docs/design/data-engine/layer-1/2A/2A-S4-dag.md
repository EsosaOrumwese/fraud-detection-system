```
        LAYER 1 · SEGMENT 2A — STATE S4 (TZ LEGALITY & DST WINDOWS)  [NO RNG]

Authoritative inputs (read-only at S4 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_2A @ data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/…
      · proves: 1B PASS gate was verified for this manifest_fingerprint (via 1B bundle + _passed.flag)
      · seals: site_timezones + tz_timetable_cache as allowed 2A inputs
      · binds: manifest_fingerprint, parameter_hash, verified_at_utc for this 2A run

[Schema+Dict]
    - schemas.layer1.yaml               (core primitives, iana_tzid, rfc3339_micros)
    - schemas.2A.yaml                   (shapes for s0_gate_receipt_2A, site_timezones, tz_timetable_cache, s4_legality_report)
    - dataset_dictionary.layer1.2A.yaml (IDs/paths/partitions for site_timezones, tz_timetable_cache, s4_legality_report)
    - artefact_registry_2A.yaml         (bindings/licences for tz_timetable_cache, site_timezones, legality_report)

[S2 Egress · per-site final tzid]
    - site_timezones
        · schema: schemas.2A.yaml#/egress/site_timezones
        · path:   data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/
        · partitions: [seed, fingerprint]
        · PK / writer sort: [merchant_id, legal_country_iso, site_order]
        · contents: final tzid per site + tzid_source, override_scope, nudge_* (S2 is authority)

[S3 Output · compiled tz timetable]
    - tz_timetable_cache
        · schema: schemas.2A.yaml#/plan/tz_timetable_cache
        · path:   data/layer1/2A/tz_timetable_cache/fingerprint={manifest_fingerprint}/
        · partitions: [fingerprint]
        · contents: canonical transition series per tzid, tzdb_release_tag, tzdb_archive_sha256, tz_index_digest, rle_cache_bytes

Numeric & RNG posture
    - S4 consumes **no RNG**
    - binary64, RNE, no FMA/FTZ/DAZ; deterministic counts & window derivation
    - identity law: path↔embed equality for {seed, manifest_fingerprint}; write-once; atomic publish; file order non-authoritative


----------------------------------------------------------------- DAG (S4.1–S4.6 · gate → tzid set → gap/fold windows → legality report)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S4.1) Verify S0 gate & fix run identity
                    - Resolve s0_gate_receipt_2A via Dictionary for this manifest_fingerprint.
                    - Validate receipt schema:
                        · manifest_fingerprint present and equals fingerprint path token,
                        · sealed_inputs[] includes site_timezones + tz_timetable_cache,
                        · verified_at_utc present (used as generated_utc for S4 report).
                    - Treat receipt as the sole gate:
                        · S4 SHALL NOT re-hash 1B or 2A bundles,
                        · S4 MAY NOT read surfaces not listed as sealed inputs.
                    - Fix run identity:
                        · seed = chosen seed for this legality_report partition,
                        · manifest_fingerprint = bundle fingerprint (partition token for cache),
                        · parameter_hash used only for lineage; S4 itself is fingerprint+seed scoped.

[S4.1],
[Schema+Dict],
site_timezones
                ->  (S4.2) Resolve site_timezones & derive TZ_USED
                    - Resolve site_timezones via Dictionary:
                        · data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/
                        · partitions: [seed, fingerprint]; writer sort [merchant_id, legal_country_iso, site_order].
                    - Validate shape:
                        · conforms to schemas.2A.yaml#/egress/site_timezones (columns_strict),
                        · PK uniqueness on [merchant_id, legal_country_iso, site_order].
                    - Derive per-run counts:
                        · sites_total  := number of rows in site_timezones,
                        · tzids_total  := |distinct tzid in site_timezones|,
                        · TZ_USED      := set of distinct tzid seen in site_timezones.
                    - Sanity:
                        · no null/empty tzid; each tzid obeys iana_tzid pattern per schema,
                        · sites_total ≥ 0; tzids_total ≥ 0.

[S4.1],
[Schema+Dict],
tz_timetable_cache
                ->  (S4.3) Resolve tz_timetable_cache & canonical index
                    - Resolve tz_timetable_cache via Dictionary:
                        · data/layer1/2A/tz_timetable_cache/fingerprint={manifest_fingerprint}/
                        · partitions: [fingerprint]; write-once; atomic publish.
                    - Validate shape:
                        · manifest object conforms to schemas.2A.yaml#/plan/tz_timetable_cache,
                        · embedded manifest_fingerprint equals fingerprint path token.
                    - Decode the canonical index payload:
                        · reconstruct for each tzid:
                            · ordered list of UTC transition instants,
                            · corresponding offset_minutes (int, bounded),
                        · assert monotone UTC times per tzid (strictly increasing),
                        · assert offset_minutes are finite and within configured bounds.

[S4.2],
[S4.3]
                ->  (S4.4) Per-tzid DST analysis · gap/fold windows & coverage
                    - For each tzid in TZ_USED:
                        · if tzid not present in timetable cache:
                            · record in missing_tzids[], mark coverage_fail = true, skip window calc for this tzid.
                        · else:
                            · load its transitions [(t0, offset0), (t1, offset1), …] from the cache.
                            · for each consecutive pair (ti, offset_i) → (t_{i+1}, offset_{i+1}):
                                · Δoffset = offset_{i+1} − offset_i  (minutes)
                                · if Δoffset > 0: this indicates a **gap window** (non-existent local times)
                                    - increment gap_windows_total,
                                    - accumulate country/tzid-level gap counters.
                                · if Δoffset < 0: this indicates a **fold window** (ambiguous local times)
                                    - increment fold_windows_total,
                                    - accumulate country/tzid-level fold counters.
                            · record per-tzid summary:
                                · gap_windows[tzid], fold_windows[tzid],
                                · may compute total_gap_minutes / total_fold_minutes (optional, per spec).

(S4.4)
                ->  (S4.5) Aggregate legality metrics & decide status
                    - Aggregate run-level metrics:
                        · sites_total        (from S4.2),
                        · tzids_total        = |TZ_USED|,
                        · gap_windows_total  = Σ_tz gap_windows[tzid],
                        · fold_windows_total = Σ_tz fold_windows[tzid].
                    - Derive missing_tzids:
                        · any tzid in TZ_USED that had no timetable entry in the cache.
                    - Decide status:
                        · status = "PASS" if:
                            - missing_tzids is empty, AND
                            - gap/fold counts are within expectations (no structural errors),
                          else "FAIL".
                    - Prepare legality payload (in-memory):
                        · identity block: { seed, manifest_fingerprint },
                        · counts: { sites_total, tzids_total, gap_windows_total, fold_windows_total },
                        · missing_tzids[] (possibly empty),
                        · generated_utc = S0.receipt.verified_at_utc,
                        · optional per-tzid summary map { tzid → { gap_windows, fold_windows } } for auditors.

(S4.5),
[Schema+Dict]
                ->  (S4.6) Materialise s4_legality_report & exit posture
                    - Write a single JSON legality report under:
                        · data/layer1/2A/legality_report/seed={seed}/fingerprint={manifest_fingerprint}/s4_legality_report.json
                        · partitions: [seed, fingerprint]
                        · schema: schemas.2A.yaml#/plan/s4_legality_report (shape-owned by 2A schema pack).
                    - Populate fields:
                        · manifest_fingerprint (MUST equal fingerprint path token),
                        · seed,
                        · tzids_total, sites_total,
                        · gap_windows_total, fold_windows_total,
                        · missing_tzids[] (empty array permitted),
                        · status: "PASS" | "FAIL",
                        · generated_utc = S0.receipt.verified_at_utc,
                        · any optional per-tzid / per-country diagnostics per schema.
                    - Enforce:
                        · schema validity against s4_legality_report anchor (columns/fields as declared),
                        · path↔embed equality for manifest_fingerprint,
                        · write-once semantics: publish via stage → fsync → single atomic move; any re-publish
                          with different bytes MUST fail.
                    - S4 remains RNG-free and does not mutate site_timezones or tz_timetable_cache; it only reads and
                      emits one legality report per (seed, manifest_fingerprint).

Downstream touchpoints
----------------------
- **2A.S5 — 2A validation bundle & PASS flag (fingerprint-scoped)**:
    - Discovers all seeds that have site_timezones for this manifest_fingerprint,
      then for each such seed:
        · reads s4_legality_report[seed,fingerprint],
        · requires status == "PASS".
    - Packages:
        · all s4_legality_report[seed,fingerprint],
        · tz_timetable_cache manifest for this fingerprint,
      into the 2A validation bundle at:
        · data/layer1/2A/validation/fingerprint={manifest_fingerprint}/
      builds index.json, computes ASCII-lex + SHA-256 digest, and writes `_passed.flag`.
    - Downstream consumers of site_timezones / tz_timetable_cache MUST verify `_passed.flag`
      for this fingerprint before reads (No PASS → No Read for 2A civil-time surfaces).
```