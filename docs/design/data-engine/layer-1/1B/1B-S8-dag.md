```
      LAYER 1 · SEGMENT 1B — STATE S8 (EGRESS PUBLISH: `site_locations`)  [NO RNG]

Authoritative inputs (read-only at S8 entry)
--------------------------------------------
[S7] Upstream per-site synthesis (sole data input)
    - s7_site_synthesis
        · ID → Schema:  schemas.1B.yaml#/plan/s7_site_synthesis
        · Path family (Dictionary):
              data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
        · Partitions (binding): [seed, fingerprint, parameter_hash]
        · Writer sort (binding): [merchant_id, legal_country_iso, site_order]
        · PK: [merchant_id, legal_country_iso, site_order]
        · Semantics:
            * deterministic, RNG-free per-site synthesis from S7:
                – tile_id (from S5)
                – lon_deg, lat_deg (from S6 deltas + S1 centroids)
            * 1:1 key parity with S5 and 1A outlet_catalogue for this identity
            * Schema is columns_strict=true; no extra columns

[Schema+Dict+Registry] Shape, paths, precedence
    - schemas.1B.yaml
        · egress anchor:  #/egress/site_locations
        · input anchor:   #/plan/s7_site_synthesis
    - dataset_dictionary.layer1.1B.yaml
        · ID `site_locations`:
              path family:  data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/
              partitions:   [seed, fingerprint]
              writer sort:  [merchant_id, legal_country_iso, site_order]
              final_in_layer: true
        · ID `s7_site_synthesis`:
              path family:  data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
              partitions:   [seed, fingerprint, parameter_hash]
              writer sort:  [merchant_id, legal_country_iso, site_order]
    - artefact_registry_1B.yaml
        · egress role for `site_locations`: “order-free; join 1A S3 for inter-country order”
        · write-once posture; atomic move; file order non-authoritative

[Context] Identity & posture
    - Identity tuple for this publish:
        · {seed, manifest_fingerprint, parameter_hash}
    - S8 is strictly RNG-free:
        · no RNG events; no RNG logs; no new run_id
    - Inter-country order:
        · `site_locations` is order-free egress;
          any inter-country ordering MUST come from 1A S3 candidate_rank.


Prohibited surfaces (fail-closed)
---------------------------------
S8 SHALL NOT read any surface other than `s7_site_synthesis`.

In particular:
    - MUST NOT read: outlet_catalogue, s5_site_tile_assignment, s6_site_jitter,
                     tile_index, tile_bounds, tile_weights, s3_requirements, s4_alloc_plan,
                     world_countries, population_raster_2025, tz_world_2025a, RNG logs, 1A bundles.
    - Any behaviour that depends on such reads is non-conformant.


--------------------------------------------------------- DAG (S8.1–S8.4 · S7 stream → projection → egress; RNG-free)

[S7],
[Schema+Dict],
[Context]
      ->  (S8.1) Fix identity & resolve S7 input (no RNG)
             - Fix sealed identity triple {seed, manifest_fingerprint, parameter_hash} for this publish.
             - Resolve `s7_site_synthesis` via Dataset Dictionary:
                 * path family:
                       data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
                 * partitions:   [seed, fingerprint, parameter_hash]
                 * writer sort:  [merchant_id, legal_country_iso, site_order]
             - Schema + hygiene:
                 * dataset conforms to schemas.1B.yaml#/plan/s7_site_synthesis (columns_strict=true)
                 * PK uniqueness on [merchant_id, legal_country_iso, site_order]
                 * optional lineage fields (e.g. manifest_fingerprint) match the path tokens
             - S8 SHALL treat s7_site_synthesis as its **sole data input**.

(S8.1)
      ->  (S8.2) Ingress stream from S7 (fixed identity; no RNG)
             - Open s7_site_synthesis as a streaming source in its writer sort:
                 * iterate rows in non-decreasing [merchant_id, legal_country_iso, site_order]
             - S8 does not reorder, filter, or batch by any other key when *conceptually* processing rows.
             - For each S7 row, expose only the columns defined in the S7 anchor; no inferred fields.

(S8.2),
[Schema+Dict]
      ->  (S8.3) Row mapping S7 → `site_locations` shape (pure projection)
             - Egress shape authority: schemas.1B.yaml#/egress/site_locations
                 * PK: [merchant_id, legal_country_iso, site_order]
                 * columns_strict=true (Schema owns the exact column set)
             - For each row in the S7 stream (key k = (merchant_id, legal_country_iso, site_order)):
                 * **Select/map** required columns for egress:
                     · merchant_id        := S7.merchant_id
                     · legal_country_iso  := S7.legal_country_iso
                     · site_order         := S7.site_order
                     · lon_deg            := S7.lon_deg
                     · lat_deg            := S7.lat_deg
                 * Do NOT:
                     · introduce new columns,
                     · drop any of the required egress columns,
                     · transform lon_deg/lat_deg or re-encode geometries,
                     · perform any new joins or ordering beyond writer sort.
             - Row-by-row mapping is strictly 1:1:
                 * exactly one candidate egress row per S7 row; no extras or deletions.

(S8.3),
[Schema+Dict],
[Context]
      ->  (S8.4) Materialise `site_locations` egress & run-summary (RNG-free)
             - Dataset ID: `site_locations`
             - Resolve output path via Dictionary:
                 * path family:
                       data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/
                 * partitions:   [seed, fingerprint]
                 * writer sort:  [merchant_id, legal_country_iso, site_order]
             - Partition shift law (S7 → S8):
                 * S7 input is under [seed, fingerprint, parameter_hash].
                 * S8 egress drops parameter_hash and publishes under [seed, fingerprint] only.
                 * `parameter_hash` is subsumed by manifest_fingerprint; it MUST NOT appear in the egress partition.
             - Emit rows:
                 * write projected rows in non-decreasing [merchant_id, legal_country_iso, site_order].
                 * enforce schema:
                     · every row validates #/egress/site_locations (columns_strict=true).
             - Identity & path↔embed equality:
                 * wherever lineage fields appear in rows (e.g., manifest_fingerprint),
                   values MUST byte-equal the corresponding path tokens (fingerprint=…).
             - Publish posture:
                 * write-once under [seed,fingerprint] for this identity.
                 * stage → fsync → single atomic move into the egress directory.
                 * file order is non-authoritative; data’s writer sort is the binding order.
             - Control-plane summary (e.g., s8_run_summary.json):
                 * identity: seed, manifest_fingerprint, parameter_hash used upstream
                 * counters: rows_s7, rows_s8
                 * A801–A808 acceptance outcomes (parity, schema, partitions, order, Dictionary coherence)
                 * determinism receipt:
                     · list site_locations files in ASCII-lex path order,
                     · concatenate bytes; compute SHA-256; store hex digest + partition_path
                 * PAT counters (CPU/IO/wall-clock) for S8.


State boundary (what S8 “owns”)
-------------------------------
- site_locations  @ data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/
    * Partitions: [seed, fingerprint]
    * Writer sort: [merchant_id, legal_country_iso, site_order]
    * Schema: schemas.1B.yaml#/egress/site_locations (columns_strict=true)
    * PK: [merchant_id, legal_country_iso, site_order]
    * Semantics:
        · final, order-free egress surface for Segment 1B:
             – geometry: lon_deg, lat_deg per outlet stub,
             – identity: merchant_id, legal_country_iso, site_order,
        · 1:1 row parity with s7_site_synthesis for the same identity,
        · no inter-country order encoded; any ordering comes from 1A S3 candidate_rank.
    * final_in_layer: true (Dictionary); no further egress variants for 1B.

- s8_run_summary (control-plane, not data-plane)
    * Path: data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/s8_run_summary.json
    * Semantics:
        · records S8 acceptance checks (A801–A808), determinism receipt, PAT,
        · used by operators / validators, not by ingestion or models.


Downstream touchpoints
----------------------
- 1B.S9 (Validation bundle for 1B)
    * treats site_locations as the **egress subject** of the 1B HashGate:
         – includes site_locations in the 1B validation bundle,
         – computes `_passed.flag` hashing over bundle contents,
         – enforces “No PASS → No read `site_locations`” for downstream consumers.
- Layer-1 / Layer-2 / Scenario runner / Ingestion gate
    * MUST treat `site_locations` as the **only** concrete site-geometry egress for 1B:
         – read via Dictionary,
         – verify 1B `_passed.flag` before use,
         – obtain any inter-country order by joining 1A S3 candidate_rank.
```