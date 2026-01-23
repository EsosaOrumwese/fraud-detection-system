```
       LAYER 1 · SEGMENT 1B — STATE S3 (COUNTRY REQUIREMENTS FRAME · n_sites per merchant×country)  [NO RNG]

Authoritative inputs (read-only at S3 entry)
--------------------------------------------
[Gate] 1B gate receipt (from S0; proves 1A PASS)
    - s0_gate_receipt_1B
        · path: data/layer1/1B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json
        · partitions: [fingerprint]
        · shape: schemas.1B.yaml#/validation/s0_gate_receipt
        · fields (core): manifest_fingerprint, validation_bundle_path, flag_sha256_hex, sealed_inputs[]
        · authority: “1A bundle PASS for this fingerprint” and “these are the surfaces 1B may read”. 

[1A] Counts source (sole source of Nᵢ)
    - outlet_catalogue
        · path family: data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/
        · partitions: [seed, fingerprint]
        · writer sort: [merchant_id, legal_country_iso, site_order]
        · shape: schemas.1A.yaml#/egress/outlet_catalogue
        · law: order-free across countries; `outlet_catalogue` is the **only** counts source for S3. 

[S2] Spatial coverage (parameter-scoped)
    - tile_weights
        · path family: data/layer1/1B/tile_weights/parameter_hash={parameter_hash}/
        · partitions: [parameter_hash]
        · writer sort: [country_iso, tile_id]
        · shape: schemas.1B.yaml#/prep/tile_weights
        · law: for each country_iso with rows here, S2 defines a fixed-dp weight surface over eligible tiles. 

[ISO] FK / domain surface
    - iso3166_canonical_2024
        · shape: schemas.ingress.layer1.yaml#/iso3166_canonical_2024
        · law: canonical uppercase ISO-3166-1 alpha-2 set; S3 must assert all legal_country_iso ∈ this domain. 

[Schema+Dict+Registry] Shape / path / provenance
    - schemas.1B.yaml            (incl. #/plan/s3_requirements, #/prep/tile_weights)
    - schemas.1A.yaml            (outlet_catalogue)
    - schemas.ingress.layer1.yaml (iso surface)
    - dataset_dictionary.layer1.1B.yaml
        · IDs⇢path/partition/sort for s0_gate_receipt_1B, tile_weights, s3_requirements
    - dataset_dictionary.layer1.1A.yaml
        · ID⇢path for outlet_catalogue
    - artefact_registry_1B.yaml
        · provenance/licence; dependencies for s3_requirements: [outlet_catalogue, tile_weights, iso3166_canonical_2024, s0_gate_receipt_1B] 

[Context] Identity & RNG posture
    - Identity triple: { seed, manifest_fingerprint, parameter_hash } (one triple per publish; fixed for whole run).
    - S3 is **RNG-free**; consumes no RNG and writes no RNG logs. 

Sealed but **not** read by S3 (for boundary clarity)
    - s3_candidate_set        (sole inter-country order authority; home rank=0; not read here)
    - tile_index              (eligible tiles; coverage checked via tile_weights only)
    - validation_bundle_1A    (bundle itself; S3 relies on S0 receipt, does not reopen bundle) 


-------------------------------------------------------------- DAG (S3.1–S3.5 · gate → group → FK+coverage → s3_requirements; no RNG)

[Gate],
[Schema+Dict]
      ->  (S3.1) Fix identities & validate S0 receipt (No PASS → No read)
             - Locate `s0_gate_receipt_1B` for target `manifest_fingerprint` via Dictionary.
             - Schema-validate against `#/validation/s0_gate_receipt`; failure ⇒ `E_RECEIPT_SCHEMA_INVALID` → ABORT.
             - Assert:
                 * `receipt.manifest_fingerprint == fingerprint` path token.
                 * `validation_bundle_path` and `flag_sha256_hex` are present (S0 already proved 1A PASS).
             - Fix run identity:
                 * choose one `{seed, manifest_fingerprint, parameter_hash}` for the run;
                 * S3 MUST NOT mix identities within a single publish.
             - Gate law:
                 * If receipt missing/invalid ⇒ **No PASS → No read**: S3 must not read `outlet_catalogue`. 

(S3.1),
[Schema+Dict]
      ->  (S3.2) Locate inputs via Dictionary & enforce path↔embed parity (no RNG)
             - Resolve dataset IDs → path families **via Dictionary only** (no literal paths):
                 * `outlet_catalogue`:
                     · `…/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/`
                     · partitions: [seed, fingerprint]; writer sort `[merchant_id, legal_country_iso, site_order]`
                 * `tile_weights`:
                     · `…/tile_weights/parameter_hash={parameter_hash}/`
                     · partitions: [parameter_hash]; writer sort `[country_iso, tile_id]`
                 * `iso3166_canonical_2024` (unpartitioned ingress FK surface).
             - Path↔embed equality:
                 * in `outlet_catalogue`, embedded `manifest_fingerprint` (and `global_seed` if present)
                   MUST equal the path tokens `{fingerprint, seed}`.
                 * `tile_weights` has no lineage columns; `{parameter_hash}` path token is the authority.
                   (If a column appears in future schema, its value MUST equal the path token.)
             - Prohibitions:
                 * Do not read `validation_bundle_1A` or `tile_index`, `world_countries`, `population_raster_2025`,
                   `tz_world_2025a` here (out-of-scope surfaces). Reading them ⇒ `E311_DISALLOWED_READ`. 

(S3.2),
[1A],
[Context]
      ->  (S3.3) Build requirements frame from outlet_catalogue (group + site-order integrity; no RNG)
             - Stream over `outlet_catalogue` (seed+fingerprint partition), writer-sorted by
               `[merchant_id, legal_country_iso, site_order]`.
             - For each `(merchant_id, legal_country_iso)` block:
                 * compute `n_sites := COUNT(*)` (rows in that block).
                 * assert **site-order integrity**:
                     · `MIN(site_order) = 1`
                     · `MAX(site_order) = n_sites`
                     · `COUNT(DISTINCT site_order) = n_sites`
                   Violations ⇒ `E314_SITE_ORDER_INTEGRITY` → ABORT (no output publish).
             - Build in-memory / streaming “requirements frame”:
                 * one record per `(merchant_id, legal_country_iso)` with `n_sites ≥ 1`.
             - Counts source law:
                 * `outlet_catalogue` is the **only** source for `n_sites`; S3 MUST NOT derive counts
                   from any other surface. 

(S3.3),
[ISO]
      ->  (S3.4) FK & normalisation checks on legal_country_iso (no RNG)
             - For each `(merchant_id, legal_country_iso, n_sites)` in the requirements frame:
                 * assert `legal_country_iso` ∈ `iso3166_canonical_2024`.
                     · otherwise ⇒ FK violation ⇒ ABORT for this identity.
                 * assert uppercase ISO-2; S3 does NOT transform/canonicalise — it only checks.
             - Any country failing FK or uppercase law ⇒ run-level failure; do not materialise output. 

(S3.3),
[S2]
      ->  (S3.5) Coverage checks vs tile_weights (parameter-scoped)
             - For fixed `{parameter_hash}`, read only `tile_weights.country_iso` domain:
                 * build set `C_weights = {country_iso}` where tile_weights has at least one row.
             - From the requirements frame, build `C_req = {legal_country_iso}`.
             - Enforce **coverage dependency**:
                 * for every `c ∈ C_req`, require `c ∈ C_weights` (i.e., at least one tile in tile_weights
                   for that country). Missing ⇒ `coverage_missing_countries > 0` ⇒ ABORT.
             - S3 does NOT inspect `tile_id`, `weight_fp`, or `dp` — only country presence. 

(S3.3),
(S3.4),
(S3.5),
[Schema+Dict],
[Context]
      ->  (S3.6) Materialise s3_requirements (run-scoped; write-once; no RNG)
             - Dataset ID: `s3_requirements`
             - Path family (Dictionary-owned):
                 * data/layer1/1B/s3_requirements/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
             - Partitions: [seed, fingerprint, parameter_hash]
             - Writer sort: [merchant_id, legal_country_iso]
             - Shape authority: schemas.1B.yaml#/plan/s3_requirements
                 * PK: [merchant_id, legal_country_iso]
                 * Columns (strict): merchant_id, legal_country_iso, n_sites (integer ≥ 1); no extras.
             - Emit exactly one row per `(merchant_id, legal_country_iso)` from the requirements frame,
               with the corresponding `n_sites`.
             - Immutability & idempotence:
                 * partitions are write-once; publishing to an existing partition with different bytes ⇒
                   `E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL` → ABORT.
                 * re-running S3 for the same identity must produce a byte-identical partition
                   (determinism; `E313_NONDETERMINISTIC_OUTPUT` otherwise). 

(S3.6),
[Context]
      ->  (S3.7) Run report, determinism receipt & failure posture (control-plane; no RNG)
             - Produce **S3 run report** (JSON; control/s3_requirements/…/s3_run_report.json):
                 * required fields: seed, manifest_fingerprint, parameter_hash,
                   rows_emitted, merchants_total, countries_total, source_rows_total,
                   ingress_versions.iso3166, determinism_receipt, notes (optional). 
                 * may include run-scale health counters: fk_country_violations,
                   coverage_missing_countries (expected 0 when accepted).
             - Determinism receipt (binding for presence, non-semantic for data):
                 * list partition files under …/s3_requirements/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
                   as relative paths, ASCII-lex sorted;
                 * concatenate bytes in that order; compute SHA-256, encode as lowercase hex64;
                 * store `{ partition_path, sha256_hex }` in run report. 
             - Failure events:
                 * on any §9 failure code (E301+… E314, E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL), emit
                   control-plane event `S3_ERROR` with `{code, at, seed, manifest_fingerprint, parameter_hash}`,
                   optionally merchant_id, legal_country_iso.
                 * abort semantics: **no** files promoted into live `s3_requirements` partition on failure;
                   partial publishes are forbidden. 


State boundary (what S3 “owns”)
-------------------------------
- s3_requirements  @ data/layer1/1B/s3_requirements/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
    * PK: [merchant_id, legal_country_iso]
    * partitions: [seed, fingerprint, parameter_hash]
    * writer sort: [merchant_id, legal_country_iso]
    * schema: schemas.1B.yaml#/plan/s3_requirements
    * semantics:
        · deterministic, RNG-free site counts per (merchant_id, legal_country_iso) for this run;
        · n_sites is taken **only** from outlet_catalogue counts, with site-order integrity enforced;
        · every country in the table is covered by S2 tile_weights for this parameter_hash.
- Control-plane artefacts (outside dataset partition; required for presence):
    * s3_run_report  @ control/s3_requirements/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s3_run_report.json
    * determinism_receipt embedded in run report (partition_path, sha256_hex).
    * optional per-merchant / health summaries (non-semantic but recommended). 


Downstream touchpoints
----------------------
- 1B.S4 (Tile allocation plan):
    * treats `s3_requirements` as **sole authority** for `n_sites` per (merchant_id, legal_country_iso);
      uses it together with `tile_weights` and `tile_index` to build `s4_alloc_plan` (per-tile n_sites_tile).
      S4 must not re-count outlet_catalogue. 
- 1B.S5 (Site→tile assignment):
    * indirectly relies on S3 via S4 — S5’s quotas per tile must sum back to S3 n_sites.
- Any other consumer needing per-country requirements:
    * MUST treat `s3_requirements` as run-scoped requirements frame for this `{seed, fingerprint, parameter_hash}`,
      not encode inter-country order, and join 1A `s3_candidate_set.candidate_rank` if an order over countries is needed. 
```