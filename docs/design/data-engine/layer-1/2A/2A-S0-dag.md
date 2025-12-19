```
        LAYER 1 · SEGMENT 2A — STATE S0 (GATE & SEALED INPUTS)  [NO RNG]

Authoritative inputs (read-only at S0 entry)
--------------------------------------------
[Schema+Dict] Schema & catalogue authority:
    - schemas.layer1.yaml                (layer-wide RNG/log/core schemas)
    - schemas.1B.yaml                    (1B egress + validation bundle shapes)
    - schemas.2A.yaml                    (2A shapes incl. s0_gate_receipt_2A & sealed_inputs_v1)
    - schemas.ingress.layer1.yaml        (ISO / geo / TZ / tzdb authorities)
    - dataset_dictionary.layer1.1B.yaml  (IDs/paths/partitions for 1B datasets, incl. site_locations, 1B validation bundle)
    - dataset_dictionary.layer1.2A.yaml  (IDs/paths/partitions for 2A surfaces incl. s0_gate_receipt_2A, sealed_inputs_v1)
    - artefact_registry_2A.yaml          (bindings for tzdb_release, tz_world_2025a, tz_overrides, tz_nudge, 2A S0 outputs)

[1B Gate Artefacts] (fingerprint-scoped; S0’s primary subject):
    - validation_bundle_1B                @ data/layer1/1B/validation/fingerprint={manifest_fingerprint}/
        · contains MANIFEST + rng_accounting + egress_checksums + s9_summary + index.json + other non-flag files
    - validation_passed_flag_1B           @ .../validation/fingerprint={manifest_fingerprint}/_passed.flag
        · text: `sha256_hex = <hex64>`; sole consumer gate for 1B egress (site_locations) — No PASS → No Read

[2A Ingress & Policy] Inputs S0 will seal for 2A:
    - site_locations                      (1B egress; partitions [seed, fingerprint]; final_in_layer for 1B)
    - tz_world_2025a                      (TZ polygons; WGS84; ingress anchor)
    - tzdb_release                        (IANA tzdata archive + tag/version)
    - tz_overrides                        (governed override registry: per-site / per-MCC / per-country rules)
    - tz_nudge                            (border-nudge epsilon + policy)
    - iso3166_canonical_2024              (ISO-2 FK surface)
    - other auxiliary refs actually consumed by 2A states (only if later specs reference them)

[Numeric & Fingerprint Law] (inherited, no RNG in S0):
    - numeric_policy.json, math_profile_manifest.json
        · binary64, RNE, no FMA/FTZ/DAZ (decision-critical maths)
    - Layer-1 fingerprint law:
        · sealed inputs + config → manifest_fingerprint via SHA-256 over canonical JSON
    - global lineage/posture:
        · path↔embed equality for {seed, parameter_hash, manifest_fingerprint, run_id}
        · write-once partitions; stage → fsync → single atomic move; file order non-authoritative


----------------------------------------------------------------- DAG (S0.1–S0.7 · upstream gate → sealed manifest → receipt & inventory)  [NO RNG]

[Schema+Dict],
[Numeric & Fingerprint Law]
                ->  (S0.1) Authority rails, identity & scope
                    - Resolve 1B + 2A schema packs and dictionaries by ID (no literal paths).
                    - Assert JSON-Schema as sole shape authority; Dictionary is IDs→paths/partitions/writer policy.
                    - Confirm compatibility window for layer1/1B/2A schema & dict baselines (v1.* lines).
                    - Fix target `manifest_fingerprint` for this 2A run (path token `fingerprint={manifest_fingerprint}`).
                    - Bind the run’s `parameter_hash` to this fingerprint for 2A; record the lineage tuple S0 will use.
                    - Re-state S0 scope:
                        · consumes **no RNG**,
                        · does not assign time zones or parse tzdb,
                        · only gates upstream and emits receipt + inventory.

[Schema+Dict],
[1B Gate Artefacts]
                ->  (S0.2) Locate 1B validation bundle & verify PASS flag (No PASS → No Read)
                    - Resolve 1B validation bundle location via Dictionary:
                        · data/layer1/1B/validation/fingerprint={manifest_fingerprint}/
                    - Read `index.json` and enforce index hygiene:
                        · every non-flag file listed exactly once,
                        · all `path` values relative and ASCII-lex-sortable,
                        · `artifact_id` unique, ASCII-clean.
                    - Read all files listed in `index.json` plus `_passed.flag`.
                    - Recompute bundle hash:
                        · concatenate raw bytes of indexed files in ASCII-lex order of `path`
                          (exclude `_passed.flag`),
                        · compute SHA-256 → `<hex64>`.
                    - Compare to `_passed.flag` content `sha256_hex = <hex64>`:
                        · **match → PASS**: 1B egress is authorised for this fingerprint.
                        · **missing/mismatch → ABORT**: raise 2A-S0 gate error; 2A MUST NOT read `site_locations`.

(S0.2 PASS),
[Schema+Dict],
[2A Ingress & Policy]
                ->  (S0.3) Enumerate & normalise 2A sealed inputs
                    - Enumerate the exact assets 2A will rely on downstream, e.g.:
                        · 1B egress: `site_locations` ([seed,fingerprint]).
                        · TZ polygons: `tz_world_2025a`.
                        · tzdb archive: `tzdb_release` (tag + URI + SHA-256).
                        · policy files: `tz_overrides`, `tz_nudge`.
                        · any auxiliary FK tables (e.g., ISO, world_countries) that 2A states actually reference.
                    - For each asset_id:
                        · resolve via Dictionary → (schema_ref, path family, partitioning, format, licence, retention),
                        · assert schema_ref matches the expected ingress/1B/2A anchor,
                        · pull or compute `sha256_hex` / version tag recorded in Registry.
                    - Enforce sealing constraints:
                        · content-address each asset (ID + version_tag + sha256),
                        · forbid aliasing (two different IDs pointing at same digest),
                        · forbid duplicate basenames within a fingerprint partition,
                        · reject any asset not in the §3.2 allowlist.

(S0.3),
[Numeric & Fingerprint Law]
                ->  (S0.4) Derive & bind 2A fingerprint identity
                    - Apply the Layer-1 fingerprint law over the sealed inputs/config bundle to derive
                      the segment’s `manifest_fingerprint` (or confirm it equals the upstream fingerprint).
                    - Bind `parameter_hash` and the sealed tzdb/override/nudge versions to this fingerprint.
                    - Enforce path↔embed equality where lineage appears (e.g., `manifest_fingerprint` fields in receipts/manifests).

(S0.2 PASS),
(S0.3–S0.4),
[Schema+Dict]
                ->  (S0.5) Emit s0_gate_receipt_2A (fingerprint-scoped; no RNG)
                    - Write a single JSON receipt under:
                        · data/layer1/2A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json
                        · partition: [fingerprint]; PK: manifest_fingerprint.
                    - Populate fields per `schemas.2A.yaml#/validation/s0_gate_receipt_v1`, including at minimum:
                        · manifest_fingerprint (== `fingerprint` path token),
                        · parameter_hash bound for this 2A run,
                        · validation_bundle_path for 1B and `flag_sha256_hex` (recomputed in S0.2),
                        · verified_at_utc (when the gate was checked),
                        · sealed_inputs[]: IDs + partition keys + schema_refs for all 2A assets (site_locations, tz_world_2025a,
                          tzdb_release, tz_overrides, tz_nudge, any aux refs actually used downstream),
                        · optional notes (non-semantic).
                    - Enforce write-once / idempotence:
                        · if a receipt already exists for this fingerprint and bytes differ → immutable-partition error, ABORT.
                        · repeated runs with identical inputs MUST write byte-identical receipts.

(S0.3–S0.5),
[Schema+Dict]
                ->  (S0.6) Materialise sealed_inputs_v1 (fingerprint-scoped inventory)
                    - Write `sealed_inputs_v1` (Parquet) under:
                        · data/layer1/2A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_v1.parquet
                        · partition: [fingerprint]; writer sort by (asset_kind, asset_id, or similar per schema).
                    - Emit one row per sealed asset:
                        · asset_id, schema_ref, catalogue_path_template,
                        · partitioning keys, version_tag, sha256_hex, licence, retention, consumed_by.
                    - Keep the partition immutable; re-publishing must be byte-identical.
                    - This table is **diagnostic/manifest only**; downstream states still resolve paths via the Dataset Dictionary.

(S0.*)      ->  (S0.7) Exit posture, observability & downstream contract
                    - On **PASS**:
                        · s0_gate_receipt_2A and sealed_inputs_v1 exist, validate, and together define the 2A sealed-input universe
                          for this fingerprint and its `parameter_hash`.
                        · Downstream 2A states (S1–S5) MUST:
                            · locate the fingerprint partition,
                            · validate the receipt against its schema,
                            · restrict reads to the asset IDs listed in sealed_inputs_v1 (plus their Dictionary-declared partitions).
                    - On any 2A.S0 error:
                        · no 2A outputs are published for this fingerprint (no receipt, no sealed_inputs_v1),
                        · 1B’s “No PASS → No Read” on `site_locations` remains the only valid gate.
                    - S0 remains RNG-free, performs no tz assignment, and never mutates 1B datasets or RNG logs.

Downstream touchpoints
----------------------
- **2A.S1–S4**:
    - MUST treat `s0_gate_receipt_2A` as the **single gate** for 2A:
        · proves 1B PASS for this fingerprint (via 1B bundle + `_passed.flag_1B`),
        · enumerates the exact 2A ingress + policy assets they’re allowed to read.
    - MUST resolve all inputs via IDs + schema_refs in sealed_inputs_v1 / Dictionary; no new surfaces.
- **2A.S5 (2A validation bundle & PASS flag)**:
    - Treats the same sealed_inputs set as the **supply-chain manifest** when building the 2A validation bundle for this fingerprint.
    - Reuses the same fingerprint-partition + ASCII-lex index + SHA-256 `_passed.flag` law as 1A/1B for its own gate.
```