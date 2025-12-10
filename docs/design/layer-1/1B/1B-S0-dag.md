```
        LAYER 1 · SEGMENT 1B — STATE S0 (GATE-IN & FOUNDATIONS)  [NO RNG]

Authoritative inputs (read-only at S0 entry)
--------------------------------------------
[Schema+Dict] Schema & catalogue authority:
    - schemas.layer1.yaml                (layer-wide RNG/log/core schemas)
    - schemas.1A.yaml                    (1A egress + validation bundle)
    - schemas.1B.yaml                    (1B shapes incl. s0_gate_receipt_1B)
    - schemas.ingress.layer1.yaml        (ISO / geo / TZ / raster authorities)
    - dataset_dictionary.layer1.1A.yaml  (IDs/paths/partitions for 1A datasets)
    - dataset_dictionary.layer1.1B.yaml  (IDs/paths/partitions for 1B datasets, incl. s0_gate_receipt_1B)
    - artefact_registry_1B.yaml          (artefact bindings; 1A bundle/flag; s0_gate_receipt_1B entry)

[1A Gate Artefacts] (fingerprint-scoped; S0’s primary subject):
    - validation_bundle_1A                @ data/layer1/1A/validation/fingerprint={manifest_fingerprint}/
        · contains index.json + bundle files (MANIFEST.json, rng_accounting.json, egress_checksums.json, …)
    - validation_passed_flag (_passed.flag)
        · text: `sha256_hex = <hex64>`; **sole consumer gate** for 1A egress

[Refs] Reference / FK surfaces S0 pins for 1B:
    - iso3166_canonical_2024              (ISO-2 FK table)
    - world_countries                     (country polygons)
    - population_raster_2025              (population raster)
    - tz_world_2025a                      (TZ polygons; used later by 2A/2B)

[N] Numeric / RNG posture (inherited; frozen here):
    - numeric_policy.json
    - math_profile_manifest.json
        · IEEE-754 binary64, RNE, FMA-OFF, no FTZ/DAZ
        · philox2x64-10; strict open-interval U(0,1)
        · `before/after/blocks/draws` envelope; 1 trace append per RNG event

[G] Run & lineage context:
    - manifest_fingerprint : hex64  (target fingerprint)
    - seed : u64
    - parameter_hash : hex64
    - run_id : opaque (logs-only; shared with layer)
    - general path↔embed equality law from layer-1 (no drift between path tokens and embedded fields)


----------------------------------------------------------------- DAG (S0.1–S0.7 · gate verification → sealed receipt; no RNG)

[Schema+Dict],
[N],[G]      ->  (S0.1) Authority, precedence & compatibility rails
                    - Resolve all artefact paths **via the Dataset Dictionary** only (no literal paths in code).
                    - Assert JSON-Schema as **sole shape authority**:
                        * schemas.layer1.yaml, schemas.ingress.layer1.yaml, schemas.1A.yaml, schemas.1B.yaml.
                    - Confirm S0’s compatibility window:
                        * 1A/1B schema & dictionary lines are on expected v1.* baselines.
                    - Re-state global lineage & order laws:
                        * path↔embed byte-equality for {seed, parameter_hash, manifest_fingerprint, run_id}.
                        * inter-country order lives **only** in 1A S3 `s3_candidate_set.candidate_rank`;
                          1B egress stays order-free and must join S3 when order is needed.
                    - Fix S0’s scope:
                        * S0 consumes **no RNG**.
                        * S0 does **not** do tiling, jitter, or geometry; it only gates inputs and emits a receipt.

[Schema+Dict],
[Refs]       ->  (S0.2) Reference surface presence & anchors
                    - Using the Dictionary + schemas, assert that all required 1B references exist:
                        * iso3166_canonical_2024
                        * world_countries
                        * population_raster_2025
                        * tz_world_2025a
                    - For each:
                        * resolve ID → (path, partitioning, schema_ref),
                        * check schema_ref matches the ingress anchor in schemas.ingress.layer1.yaml.
                    - On any missing/mismatched reference, raise `E_REFERENCE_SURFACE_MISSING` /
                      `E_SCHEMA_RESOLUTION_FAILED` / `E_DICTIONARY_RESOLUTION_FAILED` and **ABORT** (no receipt).

[Schema+Dict],
[1A Gate],
[G],[N]     ->  (S0.3) Locate 1A bundle & verify gate flag (No PASS → No read)
                    - Locate 1A validation folder via Dictionary:
                        * data/layer1/1A/validation/fingerprint={manifest_fingerprint}/
                    - Read `index.json` and enforce **index hygiene**:
                        * every non-flag file listed exactly once;
                        * relative, ASCII-lex-sortable `path` entries;
                        * unique, ASCII-clean `artifact_id`s.
                    - Read all files named in `index.json` and `_passed.flag`.
                    - Recompute bundle hash:
                        * concatenate raw bytes of files in **ASCII-lex order of index.path**
                          (exclude `_passed.flag`),
                        * compute SHA-256 → `<hex64>`.
                    - Compare to `_passed.flag` content `sha256_hex = <hex64>`:
                        * if match → **PASS**; gate satisfied for this fingerprint.
                        * else → **ABORT**; do **not** read egress; do **not** write any S0 receipt.
                    - Optional: read `egress_checksums.json` and other extras (if present) purely for observability;
                      they are included in the hash but remain non-semantic.

(S0.3 PASS) +
[1A Gate],
[G]         ->  (S0.4) Optional egress lineage parity (if S0 touches outlet_catalogue)
                    - After PASS, S0 *may* open:
                        * data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/
                    - If it does, it **must** re-assert:
                        * `outlet_catalogue.manifest_fingerprint == fingerprint` (path token),
                        * and, if present, `outlet_catalogue.global_seed == seed`.
                    - S0 never mutates 1A datasets; egress remains order-free; no cross-country order stored here.

(S0.1–S0.4),
[Refs],
[Schema+Dict] -> (S0.5) Assemble sealed_inputs set for 1B
                    - Build the list of inputs that 1B states are authorised to read after S0 PASS:
                        * outlet_catalogue:
                            {id:"outlet_catalogue", partition:["seed","fingerprint"],
                             schema_ref:"schemas.1A.yaml#/egress/outlet_catalogue"}
                        * s3_candidate_set (order authority):
                            {id:"s3_candidate_set", partition:["parameter_hash"],
                             schema_ref:"schemas.1A.yaml#/s3/candidate_set"}
                        * iso3166_canonical_2024:
                            {id:"iso3166_canonical_2024",
                             schema_ref:"schemas.ingress.layer1.yaml#/iso3166_canonical_2024"}
                        * world_countries:
                            {id:"world_countries",
                             schema_ref:"schemas.ingress.layer1.yaml#/world_countries"}
                        * population_raster_2025:
                            {id:"population_raster_2025",
                             schema_ref:"schemas.ingress.layer1.yaml#/population_raster_2025"}
                        * tz_world_2025a:
                            {id:"tz_world_2025a",
                             schema_ref:"schemas.ingress.layer1.yaml#/tz_world_2025a"}
                    - sealed_inputs entries use only IDs, partition key names, and schema_ref anchors
                      from the Dictionary/schema (no literal paths).

(S0.3 PASS) +
(S0.5),
[Schema+Dict],
[G]         ->  (S0.6) Publish s0_gate_receipt_1B (fingerprint-scoped; no RNG)
                    - Write exactly one JSON document per `{manifest_fingerprint}`:
                        * path: data/layer1/1B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json
                        * partition: [fingerprint]; PK: manifest_fingerprint
                    - Conform to `schemas.1B.yaml#/validation/s0_gate_receipt`:
                        * `manifest_fingerprint` : hex64  == `fingerprint` path token
                        * `validation_bundle_path` : "data/layer1/1A/validation/fingerprint=<hex64>/"
                        * `flag_sha256_hex` : the `<hex64>` recomputed from S0.3
                        * `verified_at_utc` : RFC3339-micros timestamp (observational only)
                        * `sealed_inputs` : array of objects assembled in S0.5
                        * `notes` : optional, non-semantic
                    - Enforce immutability / idempotence:
                        * if a receipt already exists under this fingerprint with **different bytes**,
                          raise `E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL` and **ABORT** (do not overwrite).
                        * repeated successful runs for the same fingerprint must write byte-identical receipts.
                    - S0 **does not** write any RNG logs/events; it only writes this one receipt on PASS.

(S0.*)      ->  (S0.7) Failure, observability & security posture
                    - On any `E_*`:
                        * fail closed: **no** receipt is written; 1A’s “no PASS → no read” remains in force.
                    - Observability:
                        * primary evidence = 1A validation bundle + `_passed.flag` + S0 receipt (when present).
                        * S0 never mutates 1A artefacts or RNG logs.
                    - Security / governance:
                        * closed-world: no external network calls; all inputs are sealed artefacts.
                        * resolve everything via Dictionary; no hard-coded paths.
                        * publish receipt via stage → fsync → atomic rename; partitions are write-once.
                        * ensure licence/retention for sealed_inputs come from Dictionary/Registry and are respected.


State boundary (what S0 “owns”)
-------------------------------
- **New dataset:**
    - s0_gate_receipt_1B @ data/layer1/1B/s0_gate_receipt/fingerprint={manifest_fingerprint}/
        · partition: [fingerprint]
        · schema_ref: schemas.1B.yaml#/validation/s0_gate_receipt
        · PK: manifest_fingerprint (must equal path token)
        · embeds:
            * validation_bundle_path, flag_sha256_hex, verified_at_utc
            * sealed_inputs[] listing the only inputs 1B states are authorised to read
- **Verified hand-off:**
    - 1A’s `_passed.flag` is confirmed to equal SHA-256 over validation_bundle_1A contents.
    - The “No PASS → No read `outlet_catalogue`” rule is enforced and recorded.


Downstream touchpoints
----------------------
- All **1B states (S1–S9)**:
    - MUST treat `s0_gate_receipt_1B` as the **single source of truth** for:
        * which 1A surfaces are gated and now usable (`outlet_catalogue`, `s3_candidate_set`),
        * which reference surfaces are sealed for 1B (`iso3166_canonical_2024`, `world_countries`,
          `population_raster_2025`, `tz_world_2025a`),
        * confirmed `manifest_fingerprint` and gate hash.
    - MUST obey “No PASS → No read” for any 1A egress; they MAY rely on S0’s receipt or **re-run** the bundle hash
      check themselves using the same algorithm.
- Any downstream component (e.g., 2A, scenario runner) that wants to trust 1B’s use of `outlet_catalogue`
  only needs to:
    1) verify S0’s receipt exists and is schema-valid for its fingerprint, and
    2) trust that S0 enforced the 1A gate as specified (hashing rule + `_passed.flag`).
```