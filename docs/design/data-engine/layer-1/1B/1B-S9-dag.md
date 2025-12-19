```
   LAYER 1 · SEGMENT 1B — STATE S9 (VALIDATION BUNDLE & PASS GATE)  [NO RNG]

Authoritative inputs (read-only at S9 entry)
--------------------------------------------
[S7+S8] Prep + Egress (dataset-level subjects of validation)
    - s7_site_synthesis
        · path family: data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/
        · partitions: [seed, fingerprint, parameter_hash]
        · writer sort: [merchant_id, legal_country_iso, site_order]
        · PK: [merchant_id, legal_country_iso, site_order]
        · schema: schemas.1B.yaml#/plan/s7_site_synthesis
        · deterministic, RNG-free per-site synthesis (tile_id, lon_deg, lat_deg)

    - site_locations
        · path family: data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/
        · partitions: [seed, fingerprint]
        · writer sort: [merchant_id, legal_country_iso, site_order]
        · PK: [merchant_id, legal_country_iso, site_order]
        · schema: schemas.1B.yaml#/egress/site_locations
        · final order-free egress; final_in_layer: true; columns_strict=true

[RNG evidence] S5/S6 event families + core logs (for this run)
    - rng_event_site_tile_assign   (S5 · “site→tile assignment” events)
        · path family: logs/rng/events/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/
        · partitions: [seed, parameter_hash, run_id]
        · schema: schemas.layer1.yaml#/rng/events/site_tile_assign
        · semantics:
            * exactly one event per site (one draw per site), bounded by layer RNG envelope

    - rng_event_in_cell_jitter     (S6 · in-pixel jitter attempts)
        · path family: logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/
        · partitions: [seed, parameter_hash, run_id]
        · schema: schemas.layer1.yaml#/rng/events/in_cell_jitter
        · semantics:
            * ≥1 event per site (one per attempt)
            * per-event budget: blocks=1, draws="2" (two uniforms per attempt)

    - rng_audit_log, rng_trace_log (layer core logs)
        · partitions: [seed, parameter_hash, run_id]
        · semantics:
            * core envelope counters; must reconcile with total blocks/draws from all events
            * law: u128(after) − u128(before) = blocks; draws is dec-u128 string

[Schema+Dict+Registry] Shape & path authority
    - schemas.1B.yaml
        · anchors for s7_site_synthesis, site_locations, bundle content docs (MANIFEST, s9_summary, rng_accounting, egress_checksums)
    - schemas.layer1.yaml
        · anchors for RNG event families and core logs
    - dataset_dictionary.layer1.1B.yaml / .layer1.yaml
        · IDs → {path family, partitions, writer sort, format} for all above datasets/logs
        · ID → path for `validation_1B` bundle root
    - artefact_registry_1B.yaml
        · defines that S9 owns:
            * validation bundle under fingerprint={manifest_fingerprint}
            * `_passed.flag_1B` as gate for `site_locations`

[Context] Identity & posture
    - Sealed run identity:
        · { seed, manifest_fingerprint, parameter_hash, run_id }
    - S9 posture:
        · RNG-free (no new RNG events/logs; reads RNG evidence only)
        · read-only w.r.t. S7/S8; MUST NOT mutate or overwrite them
    - Bundle root:
        · data/layer1/1B/validation/fingerprint={manifest_fingerprint}/
        · partition: [fingerprint]; path↔embed equality on manifest_fingerprint is binding

Prohibited surfaces (fail-closed)
    - S9 MUST NOT depend on:
        · priors/policies (tile_weights, tile_index, world_countries, tz_world_2025a, population_raster_2025, etc.)
        · 1A egress or 1A bundles directly (S9 validates only 1B S7/S8 + RNG logs)
        · any other random logs or datasets not enumerated in the inputs above.


------------------------------------------------------ DAG (S9.1–S9.6 · parity + RNG audit → bundle + PASS gate; no RNG)

[S7+S8],
[RNG evidence],
[Schema+Dict+Registry],
[Context]
      ->  (S9.1) Assemble sealed inputs for this run (no RNG)
             - Fix run identity: {seed, manifest_fingerprint, parameter_hash, run_id}.
             - Resolve all dataset/log IDs via Dataset Dictionary (no literal paths):
                 * s7_site_synthesis @ [seed, fingerprint, parameter_hash]
                 * site_locations    @ [seed, fingerprint]
                 * rng_event_site_tile_assign @ [seed, parameter_hash, run_id]
                 * rng_event_in_cell_jitter   @ [seed, parameter_hash, run_id]
                 * rng_audit_log, rng_trace_log @ [seed, parameter_hash, run_id]
             - Schema + partition checks:
                 * all inputs conform to their schema anchors (S7/S8 datasets, RNG event families, RNG core logs)
                 * path↔embed equality for identity fields wherever present
             - Fail-closed rule:
                 * if any required input fails schema/partition/identity checks, S9 MUST NOT publish a `_passed.flag`.

(S9.1),
[S7+S8]
      ->  (S9.2) Dataset parity & identity checks (S7 ↔ S8; no RNG)
             - Derive keysets:
                 * K7 = {(merchant_id, legal_country_iso, site_order)} from S7 (PK view)
                 * K8 = {(merchant_id, legal_country_iso, site_order)} from S8 (PK view)
             - Enforce A901 (row & key parity):
                 * |K7| == |K8|
                 * K7 == K8 exactly; no missing/extra keys
                 * PK uniqueness holds in both S7 and S8 partitions
             - Egress schema & partition law (A902–A903):
                 * site_locations rows conform to #/egress/site_locations (columns_strict=true)
                 * egress lives only under:
                       data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/
                   with partitions [seed,fingerprint]; no parameter_hash in the path
                 * path↔embed equality:
                       – any embedded seed/manifest_fingerprint in egress rows MUST match path tokens
             - Ordering & order-free law:
                 * rows in S7 and S8 are sorted by [merchant_id, legal_country_iso, site_order]
                 * S9 MUST NOT infer or encode any inter-country order; egress remains order-free.

(S9.1),
[RNG evidence],
[S7+S8]
      ->  (S9.3) RNG coverage & envelope reconciliation (site_tile_assign + in_cell_jitter)
             - Use S7 keyset K7 as the authoritative site universe.
             - S5 events — site_tile_assign:
                 * join rng_event_site_tile_assign to K7 by site identifiers (and partition identity)
                 * require:
                     · exactly one event per site in K7 (coverage)
                     · per-event budget matches contract: blocks=1, draws="1" (or equivalent per spec)
                 * aggregate S5 events:
                     · sum blocks/draws; reconcile with rng_trace_log counters for this family
             - S6 events — in_cell_jitter:
                 * join rng_event_in_cell_jitter to K7 by site identifiers
                 * require:
                     · ≥1 event per site (at least one jitter attempt)
                     · per-event budget: blocks=1, draws="2"
                 * aggregate S6 events:
                     · per-site attempt counts
                     · global blocks/draws; reconcile with rng_trace_log counters for this family
             - RNG core reconciliation:
                 * ensure that accumulated blocks/draws from all events are consistent with:
                     – rng_audit_log (initial state)
                     – rng_trace_log (final state)
                     – u128(after) − u128(before) == blocks and draws as dec-u128
             - Any mismatch (missing/extra events, budget/envelope violations, or core-log inconsistency)
               ⇒ S9 fails for this run; no PASS flag is written.

(S9.2),
(S9.3),
[S7+S8],
[Schema+Dict+Registry],
[Context]
      ->  (S9.4) Egress checksums & bundle content assembly (no RNG)
             - Egress checksums:
                 * enumerate all data files under:
                       data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/
                   ignoring any control JSON (e.g., s8_run_summary.json).
                 * for each Parquet data file:
                       – compute per-file SHA-256 digest (sha256_hex)
                       – record `{"path": <relative_path>, "sha256_hex": <hex64>}`
                 * optionally compute a composite digest over all egress files (fixed ASCII-lex order).
             - RNG accounting JSON:
                 * summarise coverage and envelope results for S5/S6:
                     · events_per_site, attempts_per_site (S6), totals for blocks/draws
                     · reconciliation with rng_audit_log / rng_trace_log
             - S9 summary JSON:
                 * record acceptance verdicts:
                     · S7↔S8 parity, schema/partition/order checks
                     · RNG coverage & envelope reconciliation
                     · egress checksum status
                     · identity tuple and input partitions used
             - MANIFEST & identity JSONs:
                 * MANIFEST.json: lists identity, input datasets/logs, and bundle members
                 * parameter_hash_resolved.json: binds parameter_hash used for S7/S8 + RNG evidence
                 * manifest_fingerprint_resolved.json: binds manifest_fingerprint for this bundle root

(S9.4),
[Schema+Dict+Registry],
[Context]
      ->  (S9.5) Build bundle index (`index.json`) (no RNG)
             - Stage all non-flag bundle files under a temporary directory:
                 * e.g., data/layer1/1B/validation/_tmp.{uuid}/
             - Bundle members (minimum set):
                 * MANIFEST.json
                 * parameter_hash_resolved.json
                 * manifest_fingerprint_resolved.json
                 * rng_accounting.json
                 * s9_summary.json
                 * egress_checksums.json
                 * any additional evidence files required by the spec
             - Construct `index.json`:
                 * one entry per non-flag file:
                       – `path`: relative path (ASCII-clean; relative to bundle root)
                       – `artifact_id`: unique identifier
                 * validate index.json against the 1A bundle-index schema:
                       – each file listed exactly once
                       – no references to `_passed.flag`
                       – `path` fields form an ASCII-lex sortable set
             - The ASCII-lex order of `index.path` values is the **canonical concatenation order**
               for the hashing step.

(S9.5),
[Context]
      ->  (S9.6) Compute `_passed.flag` & publish fingerprint-scoped bundle (no RNG)
             - Hash computation:
                 * sort entries from index.json by `path` in ASCII-lex order
                 * for each `path` in that order:
                       – read file bytes (non-flag members only)
                 * concatenate bytes in that order into a single byte stream
                 * compute SHA-256 digest → `<hex64>`
             - Write `_passed.flag`:
                 * content is a single line:
                       `sha256_hex = <hex64>`
                 * file MUST NOT be referenced in index.json
             - Atomic publish:
                 * move staged directory to final bundle root:
                       data/layer1/1B/validation/fingerprint={manifest_fingerprint}/
                 * partition: [fingerprint]; path↔embed equality for manifest_fingerprint is binding
                 * bundle is write-once for this fingerprint; re-publish must be byte-identical
             - Gate rule for consumers:
                 * downstream SHALL:
                       1) resolve bundle root via Dictionary for their target fingerprint,
                       2) read index.json and non-flag files, recompute the SHA-256 using the same ASCII-lex order of `path`,
                       3) compare to `_passed.flag.sha256_hex`.
                 * If hashes mismatch, or `_passed.flag` is missing/invalid:
                       → **No PASS → No read `site_locations` for that fingerprint.**


State boundary (what S9 “owns”)
-------------------------------
- 1B validation bundle (fingerprint-scoped)
    * Root: data/layer1/1B/validation/fingerprint={manifest_fingerprint}/
    * Partition: [fingerprint]
    * Required members (non-exhaustive, but minimal):
         – MANIFEST.json
         – parameter_hash_resolved.json
         – manifest_fingerprint_resolved.json
         – rng_accounting.json
         – s9_summary.json
         – egress_checksums.json
         – index.json
         – (optional) additional evidence files as per spec
    * All non-flag members are listed in index.json; their bytes drive the flag hash.

- `_passed.flag`
    * Path: data/layer1/1B/validation/fingerprint={manifest_fingerprint}/_passed.flag
    * Content: `sha256_hex = <hex64>`
    * Semantics:
         – the **only** gate for reading `site_locations` for this fingerprint;
         – digest over all non-flag bundle members in ASCII-lex `index.path` order.

- Control-plane role
    * S9’s bundle + flag are read-only evidence surfaces for validators and downstream services;
    * S9 NEVER mutates S7/S8 or RNG logs.


Downstream touchpoints
----------------------
- Any consumer of `site_locations` (ingestion gate, scenario runner, Layer-2, model training):
    * MUST:
         1) resolve the 1B validation bundle root for the same fingerprint via Dictionary,
         2) recompute the SHA-256 over bundle files per the S9 hashing/index law,
         3) verify that `_passed.flag.sha256_hex` matches their recomputation.
    * If verification fails, `site_locations` for that fingerprint MUST be treated as unreadable.

- Enterprise HashGate / platform governance:
    * may surface S9’s bundle + flag as a single “1B HashGate receipt”:
         – logs which fingerprints are safe to ingest,
         – enables auditing (RNG accounting, S7/S8 parity, egress checksums).

- Future layers / cross-system integrations:
    * MUST rely on the S9 PASS flag for 1B rather than re-deriving checks ad hoc;
    * may inspect S9’s `s9_summary.json` / `rng_accounting.json` / `egress_checksums.json` for observability,
      but these do not replace the hashing rule as the formal gate.
```