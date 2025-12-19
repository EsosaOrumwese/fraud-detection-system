```
   LAYER 1 · SEGMENT 1B — STATE S7 (SITE SYNTHESIS & CONFORMANCE · DETERMINISTIC)  [NO RNG]

Authoritative inputs (read-only at S7 entry)
--------------------------------------------
[S5] Site→tile assignment (run-scoped; site keyset authority)
    - s5_site_tile_assignment
        · path family: data/layer1/1B/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
        · partitions: [seed, fingerprint, parameter_hash]
        · writer sort: [merchant_id, legal_country_iso, site_order]
        · schema: schemas.1B.yaml#/plan/s5_site_tile_assignment
        · semantics:
            * exactly one row per site key (merchant_id, legal_country_iso, site_order)
            * authoritative mapping: site key → tile_id
            * FK: (legal_country_iso, tile_id) → S1 tile geometry (same parameter_hash)

[S6] Per-site jitter (run-scoped; delta authority)
    - s6_site_jitter
        · same path family & partitions as S5
        · writer sort: [merchant_id, legal_country_iso, site_order]
        · schema: schemas.1B.yaml#/plan/s6_site_jitter
        · semantics:
            * one row per site key (merchant_id, legal_country_iso, site_order)
            * effective deltas: delta_lon_deg, delta_lat_deg (accepted attempt only)
            * S6 remains **sole authority** for effective jitter; S7 MUST NOT re-sample

[S1] Tile geometry (parameter-scoped; pixel authority)
    - tile_bounds
        · path family: data/layer1/1B/tile_bounds/parameter_hash={parameter_hash}/
        · partitions: [parameter_hash]
        · writer sort: [country_iso, tile_id]
        · schema: schemas.1B.yaml#/prep/tile_bounds
        · semantics:
            * one row per (country_iso, tile_id) with:
                · min_lon_deg, max_lon_deg, min_lat_deg, max_lat_deg
                · centroid_lon_deg, centroid_lat_deg
            * authoritative rectangle & centroid for S7’s pixel checks

[1A] Outlet universe (read-only; coverage & identity parity)
    - outlet_catalogue
        · path family: data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/
        · partitions: [seed, fingerprint]
        · writer sort: [merchant_id, legal_country_iso, site_order]
        · schema: schemas.1A.yaml#/egress/outlet_catalogue
        · semantics:
            * one row per outlet stub (merchant_id, legal_country_iso, site_order)
            * order-free across countries; inter-country order authority remains 1A S3 candidate_rank

[Gate & lineage] 1A validation gate + identity law
    - s0_gate_receipt_1B / 1A validation bundle & _passed.flag
        · prove that 1A bundle PASSes for this manifest_fingerprint (**No PASS → No read** of outlet_catalogue)
    - Identity tuple: {seed, manifest_fingerprint, parameter_hash}
        · fixed for entire S7 publish; S7 is RNG-free (no run_id, no new RNG logs)

[Schema+Dict+Registry] Shape / paths / precedence
    - schemas.1B.yaml
        · anchors for #/plan/s5_site_tile_assignment, #/plan/s6_site_jitter, #/prep/tile_bounds, #/plan/s7_site_synthesis
    - schemas.1A.yaml
        · anchor for #/egress/outlet_catalogue
    - dataset_dictionary.layer1.1B.yaml / .1A.yaml
        · IDs → {path family, partitions, writer sort} for all above datasets
    - artefact_registry_1B.yaml
        · provenance, write-once posture, and dependency graph for s7_site_synthesis

Prohibited surfaces (fail-closed for S7 behaviour)
    - MUST NOT read: tile_index, tile_weights, s3_requirements, s4_alloc_plan, world_countries,
      population_raster_2025, tz_world_2025a, RNG logs, any 1A data other than outlet_catalogue.


---------------------------------------------------- DAG (S7.1–S7.5 · join frame → reconstruct → checks → synthesis; no RNG)

[S5],
[S6],
[S1],
[Schema+Dict],
[Gate],
[Context]
      ->  (S7.1) Identity, preconditions & allowed reads (no RNG)
             - Fix dataset identity tuple for this publish:
                 * {seed, manifest_fingerprint, parameter_hash}
             - Enforce authority stack:
                 * JSON-Schema is shape authority for all datasets.
                 * Dataset Dictionary is sole authority for IDs → path/partition/writer sort.
                 * Artefact Registry governs write-once, atomic move, non-authoritative file order.
             - Gate discipline for 1A:
                 * S7 SHALL read 1A outlet_catalogue **only if** the 1A validation bundle for the same
                   manifest_fingerprint PASSes (per S0/S9 1A). No PASS → No read.
             - Resolve inputs via Dictionary (no literal paths):
                 * s5_site_tile_assignment @ [seed,fingerprint,parameter_hash], sort [merchant, country, site_order]
                 * s6_site_jitter        @ [seed,fingerprint,parameter_hash], sort [merchant, country, site_order]
                 * tile_bounds           @ [parameter_hash], sort [country_iso, tile_id]
                 * outlet_catalogue      @ [seed,fingerprint], sort [merchant, country, site_order]
             - Schema + writer-hygiene checks:
                 * S5, S6, tile_bounds, outlet_catalogue validate against their schema anchors.
                 * All path↔embed identity fields (if present) byte-equal {seed, fingerprint, parameter_hash}
                   where applicable.

(S7.1),
[S5],
[S6],
[S1]
      ->  (S7.2) Per-site join frame (S5 ↔ S6 ↔ tile_bounds; no RNG)
             - Define canonical site keyset:
                 * K = { (merchant_id, legal_country_iso, site_order) } from s5_site_tile_assignment
                 * iteration order: S5 writer-sort → [merchant_id, legal_country_iso, site_order]
             - Join S5 → S6 (1:1 on PK + partitions):
                 * for each k ∈ K:
                     · inner-join to s6_site_jitter on (merchant_id, legal_country_iso, site_order)
                     · enforce exactly one S6 row per S5 row; missing/dup rows ⇒ structural failure.
                 * resulting frame includes:
                     · merchant_id, legal_country_iso, site_order
                     · tile_id (from S5; S5 remains tile assignment authority)
                     · delta_lon_deg, delta_lat_deg (from S6; S6 remains jitter authority)
             - Join S5/S6 frame → S1 tile_bounds (by tile):
                 * join on (country_iso = legal_country_iso, tile_id) for the same parameter_hash
                 * fetch:
                     · centroid_lon_deg, centroid_lat_deg
                     · min_lon_deg, max_lon_deg, min_lat_deg, max_lat_deg
                 * enforce FK: every (legal_country_iso, tile_id) in S5/S6 must exist in tile_bounds.
             - At the end of S7.2, for each site key k, S7 has a fully-determined join frame:
                 * keys (m,c,s), tile_id, deltas (δ_lon,δ_lat), centroid, and pixel rectangle.

(S7.2)
      ->  (S7.3) Reconstruct absolutes & pixel conformance (RNG-free)
             - For each site key (m,c,s) in writer-sort order:
                 * reconstruct realised coordinates:
                     lon* = centroid_lon_deg + delta_lon_deg
                     lat* = centroid_lat_deg + delta_lat_deg
                 * using only sealed inputs from S1 + S6; numeric policy is S0’s binary64/RN-even.
             - Inside-pixel check (per row):
                 * assert (lon*, lat*) lies **inside** the rectangle
                       [min_lon_deg, max_lon_deg] × [min_lat_deg, max_lat_deg] for (c, tile_id),
                       respecting S1’s antimeridian semantics.
                 * violation ⇒ acceptance failure (A705) and no S7 publish for this identity.
             - Note: S7 introduces **no RNG**; reconstruction is deterministic given inputs.

(S7.3),
[S5],
[1A],
[Gate],
[Schema+Dict]
      ->  (S7.4) 1:1 coverage & identity parity (S5 ↔ S7 ↔ 1A)
             - S5 ↔ S7 key parity (A701):
                 * S7 SHALL emit exactly one row per S5 site key K:
                     · |S7| = |S5| (count parity)
                     · keyset(S7) == keyset(S5) on [merchant_id, legal_country_iso, site_order]
                 * enforce PK uniqueness on S7 PK: (merchant_id, legal_country_iso, site_order)
             - 1A coverage parity (A706):
                 * after confirming 1A gate for this fingerprint (No PASS → No read),
                   perform read-side join:
                       S7.site_key ↔ outlet_catalogue.site_key
                 * require 1:1 join (no missing/extra), and preserve:
                       · merchant_id
                       · legal_country_iso
                       · site_order continuity
                 * violation ⇒ acceptance failure; S7 MUST NOT be accepted for this identity.
             - Inter-country order:
                 * S7 does not define or encode cross-country order; any ordering needs for downstream
                   are satisfied by joining 1A S3 candidate_rank.

(S7.3),
(S7.4),
[Schema+Dict],
[Context]
      ->  (S7.5) Materialise s7_site_synthesis (write-once; RNG-free)
             - Dataset ID: s7_site_synthesis
             - Path family (from Dictionary):
                 * data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
             - Partitions: [seed, fingerprint, parameter_hash]
             - Writer sort: [merchant_id, legal_country_iso, site_order]
             - Schema: schemas.1B.yaml#/plan/s7_site_synthesis
                 * PK: [merchant_id, legal_country_iso, site_order]
                 * columns_strict = true (no extra columns beyond schema)
             - For each site key (m,c,s):
                 * write exactly one row with at least:
                     · merchant_id, legal_country_iso, site_order
                     · tile_id        (from S5 join; preserved through S6/S7)
                     · lon_deg, lat_deg (reconstructed absolutes from S7.3)
                     · lineage fields (e.g. manifest_fingerprint) as required by schema
             - Identity & path↔embed equality (A703):
                 * embedded manifest_fingerprint (if present) MUST byte-equal `fingerprint=` path token
                 * any embedded seed/parameter_hash fields MUST match their path tokens
             - Ordering posture (A704):
                 * enforce non-decreasing [merchant_id, legal_country_iso, site_order] within the partition
                 * file order is non-authoritative; writer sort is the binding order
             - Immutability & determinism:
                 * partition is write-once; re-publish for same {seed,fingerprint,parameter_hash} MUST be byte-identical
                 * S7 introduces no RNG logs; existing S5/S6 RNG logs remain read-only audit artefacts.

State boundary (what S7 “owns”)
-------------------------------
- s7_site_synthesis
    * Path: data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
    * Partitions: [seed, fingerprint, parameter_hash]
    * Writer sort: [merchant_id, legal_country_iso, site_order]
    * PK: [merchant_id, legal_country_iso, site_order]
    * Semantics:
        · deterministic per-site synthesis:
             – carries tile_id from S5 (unchanged),
             – carries reconstructed lon_deg, lat_deg from S6 deltas + S1 centroids,
        · 1:1 key parity with S5 and with 1A outlet_catalogue for the fingerprint,
        · suitable for S8 to project to egress `site_locations` without adding inter-country order.
- Control-plane:
    * S7 run-report (not detailed here) with:
        · identity tuple, row counts, FK checks, 1A parity checks,
        · determinism receipt: SHA-256 over s7_site_synthesis partition contents,
        · PAT counters (CPU/IO/wall-clock).


Downstream touchpoints
----------------------
- 1B.S8 (Egress publish — `site_locations`; RNG-free)
    * consumes s7_site_synthesis exclusively to produce:
         data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/
      with partitions [seed, fingerprint] and same writer sort [merchant_id, legal_country_iso, site_order].
    * S8 MUST:
         · treat s7_site_synthesis as the sole authority for per-site lon_deg, lat_deg and tile_id,
         · publish order-free egress (no inter-country order encoded),
         · keep S7/S8 identity law and 1A gate discipline intact.

- 1B.S9 (Validation bundle)
    * uses s7_site_synthesis + S6/S1 + 1A artefacts to:
         · re-check A701–A707 acceptance criteria,
         · recompute lon* from S6+S1 and assert equality with S7 lon_deg/lat_deg,
         · assert S7’s schema/partition/order discipline and 1A read discipline.

- Any diagnostics / downstream model or scenario runner:
    * may read s7_site_synthesis via Dictionary as the definitive per-site geometry surface for this run,
      but MUST:
         · treat inter-country order as external (join 1A S3 candidate_rank),
         · not mutate or override S7’s lon_deg/lat_deg or tile_id for the same identity.
```