```
   LAYER 1 · SEGMENT 1B — STATE S6 (IN-PIXEL UNIFORM JITTER + POINT-IN-COUNTRY)  [RNG]

Authoritative inputs (read-only at S6 entry)
--------------------------------------------
[S5] Site→tile assignment (run-scoped; S6’s site universe)
    - s5_site_tile_assignment
        · path: data/layer1/1B/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
        · partitions: [seed, fingerprint, parameter_hash]
        · writer sort: [merchant_id, legal_country_iso, site_order]
        · schema: schemas.1B.yaml#/plan/s5_site_tile_assignment
        · semantics:
            * exactly one row per site key (merchant_id, legal_country_iso, site_order)
            * authoritative mapping: (merchant_id, legal_country_iso, site_order) → tile_id
            * FK to ISO + FK to S1 tile_index (same parameter_hash)

[S1] Tile geometry (parameter-scoped)
    - tile_index
        · path: data/layer1/1B/tile_index/parameter_hash={parameter_hash}/
        · partitions: [parameter_hash]
        · writer sort: [country_iso, tile_id]
        · schema: schemas.1B.yaml#/prep/tile_index
        · semantics:
            * PK (country_iso, tile_id)
            * pixel rectangle per tile: [min_lon_deg, max_lon_deg] × [min_lat_deg, max_lat_deg]
            * centroid_lon_deg, centroid_lat_deg
            * antimeridian/topology semantics fixed in S1

[Geo] Country polygons (point-in-country authority)
    - world_countries
        · schema: schemas.ingress.layer1.yaml#/world_countries
        · semantics:
            * canonical country polygons for ISO2 codes (including holes/antimeridian handling)
            * S6 MUST use this for point-in-country predicate; no other shapes allowed

[Gate] 1B gate receipt / 1A PASS (context)
    - s0_gate_receipt_1B
        · proves 1A bundle PASS for manifest_fingerprint
        · must exist and be valid before S6 runs
        · S6 *relies* on this; does not re-hash 1A validation bundle

[Schema+Dict+Registry] Shape / path / RNG envelope
    - schemas.1B.yaml
        · anchor for s5_site_tile_assignment, s6_site_jitter
    - schemas.layer1.yaml
        · anchor for rng_event_in_cell_jitter (and RNG envelope)
    - dataset_dictionary.layer1.1B.yaml
        · IDs ⇢ {path, partitioning, writer sort} for s5_site_tile_assignment, tile_index, s6_site_jitter, s6_run_report, in_cell_jitter
    - artefact_registry_1B.yaml
        · provenance/roles; declares S6 produces s6_site_jitter + in_cell_jitter

[Context] Identity & RNG posture
    - Dataset identity: { seed, manifest_fingerprint, parameter_hash } (one tuple per S6 publish)
    - RNG identity: { seed, parameter_hash, run_id } for in_cell_jitter
        · one run_id per publish
    - S6 is RNG-bound:
        · **RNG events:** rng_event_in_cell_jitter (substream_label="in_cell_jitter", module="1B.S6.jitter")
        · **Per attempt:** blocks = 1, draws = "2" (two uniforms per attempt)
    - Inter-country order:
        · never encoded by S6; 1B never encodes inter-country order; consumers join 1A S3 candidate_rank if needed.


---------------------------------------------------------------- DAG (S6.1–S6.6 · assignment → jitter attempts → accepted deltas; RNG-bound)

[S5],
[S1],
[Geo],
[Schema+Dict],
[Context]
      ->  (S6.1) Preconditions, identity & allowed reads (no RNG yet)
             - Fix identity tuple: {seed, manifest_fingerprint, parameter_hash} for this publish.
             - Enforce gate:
                 * S0 gate receipt MUST exist and be valid for manifest_fingerprint
                 * S6 does NOT re-hash 1A bundle, but assumes “No PASS → No read” already enforced.
             - Resolve inputs via Dictionary (no literal paths):
                 * s5_site_tile_assignment @ …/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
                 * tile_index @ …/parameter_hash={parameter_hash}/
                 * world_countries ingress surface
             - Schema + writer-hygiene for inputs:
                 * s5_site_tile_assignment conforms to #/plan/s5_site_tile_assignment; PK, partitions, sort OK.
                 * tile_index conforms to #/prep/tile_index; PK (country_iso, tile_id), partitions, sort OK.
             - FK pre-checks:
                 * every (legal_country_iso, tile_id) in S5 FK’s to tile_index for same parameter_hash.
                 * legal_country_iso ∈ ISO domain via S5/S1 schema FKs.
             - Prohibited reads for S6 behaviour:
                 * MUST NOT read: s3_requirements, s4_alloc_plan, tile_weights, outlet_catalogue, s3_candidate_set,
                   population_raster_2025, tz_world_2025a, or 1A validation bundle.

(S6.1),
[S5],
[S1]
      ->  (S6.2) Deterministic site iteration & geometric context (no RNG)
             - Iteration order:
                 * iterate sites in S5 writer sort: [merchant_id, legal_country_iso, site_order]
                 * this is the authoritative keyset for S6: every S5 row induces one S6 row (A601).
             - For each site key k = (m, c, s):
                 * read tile_id from s5_site_tile_assignment
                 * join to tile_index on (country_iso = c, tile_id) for same parameter_hash
                     · retrieve [min_lon_deg, max_lon_deg], [min_lat_deg, max_lat_deg], centroid_lon_deg, centroid_lat_deg
             - Define per-site attempt loop state:
                 * MAX_ATTEMPTS = 64 (cap on attempts per site)
                 * attempt_counter = 0
             - No RNG yet; this step just sets up geometry & iteration order.

(S6.2),
[Context]
      ->  (S6.3) Per-attempt RNG discipline (in_cell_jitter; 2 uniforms per attempt)
             - For each site (m,c,s), within its attempt loop:
                 * for each attempt:
                     · increment attempt_counter
                     · draw two uniforms (u_lon, u_lat) from substream "in_cell_jitter"
                     · emit one rng_event_in_cell_jitter (JSONL) with:
                         - lineage: {seed, parameter_hash, run_id}
                         - key fields: merchant_id=m, legal_country_iso=c, site_order=s, attempt index
                         - module: "1B.S6.jitter", substream_label: "in_cell_jitter"
                         - envelope: blocks = 1, draws = "2" (two uniforms per event)
             - Budget law:
                 * at least one in_cell_jitter event per site (A608)
                 * total events = total attempts; each event consumes exactly two uniforms; counters before/after reconcile (A609).
             - Determinism posture:
                 * for fixed {seed, manifest_fingerprint, parameter_hash, run_id} and same inputs,
                   the event stream and sampled uniforms per site are reproducible.

(S6.3),
(S6.2),
[Geo]
      ->  (S6.4) Candidate generation (uniform in pixel) & point-in-country predicate
             - Candidate generation (per attempt):
                 * for the site’s tile rectangle [min_lon, max_lon] × [min_lat, max_lat]:
                       lon* = min_lon + u_lon · (max_lon − min_lon)
                       lat* = min_lat + u_lat · (max_lat − min_lat)
                 * if tile crosses ±180°:
                       – unwrap to a continuous longitude interval, compute lon* there,
                         then normalise back to WGS84 in [-180, 180] as in S1.
                 * compute deltas relative to centroid from tile_index:
                       delta_lon_deg = lon* − centroid_lon_deg
                       delta_lat_deg = lat* − centroid_lat_deg
                 * these deltas are what S6 will persist on success (subject to schema guards, e.g. [-1,1]).
             - Country predicate (per attempt):
                 * using world_countries polygon for c = legal_country_iso:
                       – `(lon*, lat*)` MUST lie inside the polygon for c,
                         respecting S1’s topology (holes, antimeridian).
             - Bounded resample:
                 * if predicate fails:
                       – if attempt_counter < MAX_ATTEMPTS (64): retry with a new in_cell_jitter event
                       – else: ABORT S6 for this identity with E613_RESAMPLE_EXHAUSTED (no partial publish)
                 * on first success: accept `(delta_lat_deg, delta_lon_deg)` and exit attempt loop for this site.

(S6.4),
[Schema+Dict],
[Context]
      ->  (S6.5) Materialise s6_site_jitter & enforce per-site coverage
             - Dataset ID: s6_site_jitter
             - Path (via Dictionary):
                 * data/layer1/1B/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
             - Partitions: [seed, fingerprint, parameter_hash]
             - Writer sort: [merchant_id, legal_country_iso, site_order]
             - Schema: schemas.1B.yaml#/plan/s6_site_jitter
                 * PK: [merchant_id, legal_country_iso, site_order]
                 * Columns (strict):
                     · merchant_id          (id64)
                     · legal_country_iso    (ISO2; FK to ISO ingress surface)
                     · site_order           (int ≥ 1; contiguous 1..N per (m,c), preserved from S5)
                     · tile_id              (uint64; FK to tile_index for same parameter_hash)
                     · delta_lat_deg        (bounded e.g. [-1,1])
                     · delta_lon_deg        (bounded e.g. [-1,1])
                     · manifest_fingerprint (hex64; MUST equal fingerprint path token)
             - For each site (m,c,s) with accepted candidate:
                 * write exactly one row:
                     (merchant_id=m, legal_country_iso=c, site_order=s,
                      tile_id from S5, delta_lat_deg, delta_lon_deg, manifest_fingerprint)
             - Coverage & FK invariants:
                 * A601: |S6| == |S5|; 1:1 keyset on (merchant_id, legal_country_iso, site_order)
                 * A605: every (legal_country_iso, tile_id) in S6 exists in tile_index for this parameter_hash
             - Identity & immutability:
                 * dataset is write-once for this identity; re-publish must be byte-identical
                 * embedded lineage fields MUST match path tokens.

(S6.5),
(S6.3),
[Context]
      ->  (S6.6) Run report, RNG accounting & acceptance posture (control-plane)
             - s6_run_report (control/s6_site_jitter/…/s6_run_report.json):
                 * identity: seed, manifest_fingerprint, parameter_hash, run_id
                 * counts:
                     · s5_rows_total, s6_rows_total
                     · attempts_per_site distribution, E613 occurrences (expected 0 for PASS)
                 * RNG coverage:
                     · total in_cell_jitter events
                     · event_count_per_site (≥1)
                     · check rows_total == Σ event_count_per_site (IMM-level invariants)
                 * determinism receipt:
                     · list s6_site_jitter files in ASCII-lex path order
                     · concatenate bytes; SHA-256 digest stored as hex64
                 * PAT counters: wall_time, cpu_time, IO bytes for S5, tile_index, world_countries, S6 outputs.
             - Acceptance criteria (S6 passes only if ALL hold):
                 * A601–A605: key parity, schema, partitions, writer sort, FK to tile_index
                 * A606: reconstructed lon*/lat* using S1 bounds + deltas lie inside pixel rectangle
                 * A607: reconstructed lon*/lat* lie inside world_countries polygon for each row
                 * A608–A610: RNG event coverage, logs partitions, and envelope budget/counter checks
                 * A613: last in_cell_jitter event per site corresponds to the accepted delta written to S6
             - S6 does NOT publish or mutate 1B egress `site_locations`; it only owns jitter + RNG events.


State boundary (what S6 “owns”)
-------------------------------
- s6_site_jitter  @ data/layer1/1B/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
    * PK: [merchant_id, legal_country_iso, site_order]
    * partitions: [seed, fingerprint, parameter_hash]
    * writer sort: [merchant_id, legal_country_iso, site_order]
    * per-site jitter surface:
        · includes tile_id + (delta_lat_deg, delta_lon_deg) for each site
        · one row per site in s5_site_tile_assignment; no missing or extra sites
        · deltas correspond to a uniform-in-pixel sample inside the S1 tile & inside country polygon.

- rng_event_in_cell_jitter @ logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/
    * append-only JSONL events; partitions [seed, parameter_hash, run_id]
    * ≥ 1 event per site (one per attempt); each event has blocks=1, draws="2"
    * module="1B.S6.jitter", substream_label="in_cell_jitter"
    * envelope counters track total uniform draws for S6 per identity.

- s6_run_report (control-plane)
    * control/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s6_run_report.json
    * summary of counts, RNG coverage, FK/geometry checks, determinism receipt.


Downstream touchpoints
----------------------
- 1B.S7 (Site synthesis; RNG-free)
    * consumes s5_site_tile_assignment + s6_site_jitter + tile_bounds:
         · reconstructs absolute lon/lat per site:
               lon* = centroid_lon_deg + delta_lon_deg
               lat* = centroid_lat_deg + delta_lat_deg
         · enforces 1:1 coverage with both S5 and 1A outlet_catalogue (via S0 gate).
    * S7 MUST NOT re-sample jitter; it treats S6 deltas as authoritative.

- 1B.S9 (Validation bundle)
    * uses s6_site_jitter + in_cell_jitter (and S1 geometry) to:
         · re-check FK to tile_index and ISO
         · verify uniform-in-pixel and point-in-country properties (A606–A607)
         · reconcile RNG budgets: per-site attempts vs events; final-event ↔ accepted delta (A608–A613).

- Any diagnostics / analysis of spatial jitter:
    * may read s6_site_jitter + tile_index + world_countries to understand jitter patterns,
      but MUST treat S6 as authority for per-site deltas and MUST NOT mutate tile assignments or resample jitter.
```