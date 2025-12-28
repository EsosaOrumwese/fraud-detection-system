```
        LAYER 1 · SEGMENT 3B — STATE S2 (CDN EDGE CATALOGUE CONSTRUCTION)  [RNG-BOUNDED]

Authoritative inputs (read-only at S2 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_3B
      @ data/layer1/3B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3B.json
      · sole authority for:
          - identity triple {seed, parameter_hash, manifest_fingerprint},
          - upstream gates for segments 1A, 1B, 2A, 3A (all MUST be PASS),
          - catalogue_versions for schemas.3B.yaml, dataset_dictionary.layer1.3B.yaml, artefact_registry_3B.yaml.
    - sealed_inputs_3B
      @ data/layer1/3B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3B.parquet
      · whitelist of all external artefacts S2 MAY read.
      · Any external artefact S2 reads MUST:
          - appear as a row in sealed_inputs_3B,
          - match on {logical_id, path, schema_ref},
          - have matching sha256_hex (S2 MUST recompute in hardened mode).

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml
        · RNG envelope (Philox2x64-10, rng_event schema, rng_trace_log),
        · numeric policy (binary64, RNE, no FMA/FTZ/DAZ).
    - schemas.3B.yaml
        · anchors for:
              - plan/virtual_classification_3B,
              - plan/virtual_settlement_3B,
              - plan/edge_catalogue_3B,
              - plan/edge_catalogue_index_3B.
    - schemas.1B.yaml (for tile_index/tile_weights if using 1B tiling).
    - schemas.2A.yaml (for tz assets, if referenced).
    - dataset_dictionary.layer1.{3B,1B,2A}.yaml
        · IDs → paths/partitions/schema_refs.
    - artefact_registry_{3B,1B,2A}.yaml
        · artefact kinds, logical_ids, ownership.

[Binding data-plane inputs from 3B.S1]
    - virtual_classification_3B
      @ data/layer1/3B/virtual_classification/seed={seed}/fingerprint={manifest_fingerprint}/…
      · PK: [merchant_id]; universe M of merchants.
      · S2’s use:
          - derive virtual set V = { m | is_virtual(m)=1 },
          - MUST NOT re-run MCC/channel rules; classification is owned by S1.
    - virtual_settlement_3B
      @ data/layer1/3B/virtual_settlement/seed={seed}/fingerprint={manifest_fingerprint}/…
      · PK: [merchant_id]; one row per virtual merchant.
      · S2’s use:
          - anchor each virtual merchant to a settlement node:
                (settlement_site_id, settlement_lat_deg, settlement_lon_deg, tzid_settlement, tz_source),
          - MUST NOT alter coordinates or tzid_settlement.

[CDN edge-budget & geography policy inputs]
    - cdn_country_weights (and, if configured, class-specific variants)
        · sealed policy pack(s) that define:
            - global country mix vector w_global(c),
            - optional per-class/per-merchant overrides w_class(class,c),
            - mapping class(m) based on merchant attributes / allow lists,
            - per-class nominal total edges E_total(class),
            - global min_edges_per_merchant / max_edges_per_merchant,
            - per-country floors/caps (e.g. min edges in key countries).
        · S2 MUST treat these packs as the sole authority on edge budgets and allowed countries C_m.

[Spatial tiling & HRSL surfaces]
    - tile_index / tile_weights
        · either 1B-owned surfaces (schemas.1B.yaml), or 3B-specific tiling datasets:
            - per tile: country_iso, tile_id, geometry (extent or centroid+size),
            - tile_weight (w_tile(c,t)) consistent with declared basis (e.g. HRSL population).
    - hrsl_raster
        · HRSL population raster used to drive tile_weights or jitter targets.

[Timezone inputs & tz semantics]
    - civil_time_manifest (2A roll-up)
        · tz-world polygons, tzdb archive, tz overrides & tz_index digests.
        · S2 MUST use 2A-compatible logic for `tzid_operational` (point→tzid).

[RNG & routing policy inputs]
    - routing / 3B RNG policy artefact(s), sealed in sealed_inputs_3B
        · define:
            - engine = Philox2x64-10,
            - allowed streams/substreams for S2:
                  module="3B.S2",
                  substream_label ∈ {"edge_tile_assign","edge_jitter"} (or equivalent),
            - per-stream budgets (blocks, draws) per edge slot and jitter attempt,
            - mapping from {seed, parameter_hash, manifest_fingerprint} to Philox keys/counters.

[Outputs owned by S2]
    - edge_catalogue_3B
      @ data/layer1/3B/edge_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/…
      · partition_keys: [seed, fingerprint]
      · primary_key:    [merchant_id, edge_id]
      · sort_keys:      [merchant_id, edge_id]
      · schema_ref: schemas.3B.yaml#/plan/edge_catalogue_3B
      · columns (min):
            seed, fingerprint,
            merchant_id, edge_id, edge_seq_index,
            country_iso,
            lat_deg, lon_deg,
            tzid_operational, tz_source,
            edge_weight ≥ 0,
            hrsl_tile_id?, spatial_surface_id?,
            cdn_policy_id?, cdn_policy_version?,
            rng_stream_id, rng_event_id,
            sampling_rank?, edge_digest (hex64).

    - edge_catalogue_index_3B
      @ data/layer1/3B/edge_catalogue_index/seed={seed}/fingerprint={manifest_fingerprint}/edge_catalogue_index_3B.parquet
      · partition_keys: [seed, fingerprint]
      · primary_key:    [scope, merchant_id]
      · sort_keys:      [scope, merchant_id]
      · schema_ref: schemas.3B.yaml#/plan/edge_catalogue_index_3B
      · columns (min):
            scope ∈ {MERCHANT, GLOBAL},
            seed, fingerprint,
            merchant_id? (null for GLOBAL),
            edge_count_total?,
            edge_digest?,
            edge_catalogue_path?,
            edge_catalogue_size_bytes?,
            country_mix_summary?,
            edge_count_total_all_merchants? (GLOBAL),
            edge_catalogue_digest_global? (GLOBAL),
            notes?.

    - RNG evidence (layer-wide, not 3B datasets):
        · rng_event_edge_jitter, rng_event_edge_tile_assign (or analogous S2 families),
        · rng_audit_log, rng_trace_log.

[Numeric & RNG posture]
    - Two-phase:
        · Phases A–C, E, F are RNG-free,
        · Phase D (edge jitter / placement) is RNG-bearing.
    - RNG:
        · S2 MUST use Philox2x64-10 only under the configured streams/substreams,
        · all RNG usage confined to Phase D; envelopes logged in RNG events and trace logs.
    - Determinism:
        · Given fixed {seed, parameter_hash, manifest_fingerprint}, sealed_inputs_3B and RNG policy,
          S2 MUST produce identical edge coordinates, tzid_operational, edge_id, edge_weight, RNG logs and outputs.


----------------------------------------------------------------------
DAG — 3B.S2 (virtual set + policy + spatial surfaces → edge catalogue)  [RNG-BOUNDED]

### Phase A — Environment & input load (RNG-free)

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S2.1) Validate S0 gate & identity
                    - Resolve and validate:
                        · s0_gate_receipt_3B@fingerprint={manifest_fingerprint},
                        · sealed_inputs_3B@fingerprint={manifest_fingerprint}.
                    - Assert:
                        · segment_id="3B", state_id="S0",
                        · gate_receipt.manifest_fingerprint == run manifest_fingerprint,
                        · (if present) gate_receipt.seed == seed, gate_receipt.parameter_hash == parameter_hash.
                    - From upstream_gates in s0_gate_receipt_3B:
                        · require segment_1A/1B/2A/3A.status == "PASS".
                    - On failure: S2 MUST NOT proceed.

sealed_inputs_3B,
[Schema+Dict]
                ->  (S2.2) Resolve binding inputs from S1 & policy packs
                    - Resolve and validate via dictionary + sealed_inputs_3B:
                        · virtual_classification_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · virtual_settlement_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · CDN policy packs (cdn_country_weights, classes, overrides, floors/caps),
                        · tiling surfaces (tile_index, tile_weights),
                        · hrsl_raster,
                        · civil_time_manifest / tz assets,
                        · routing/RNG policy pack(s) for 3B.S2 (module="3B.S2").
                    - For each external artefact:
                        · confirm row exists in sealed_inputs_3B,
                        · recompute SHA-256(raw bytes) and assert equality with `sha256_hex`.
                    - Validate shapes:
                        · S1 datasets against schemas.3B.yaml
                          (`#/plan/virtual_classification_3B`, `#/plan/virtual_settlement_3B`),
                        · tiling surfaces against 1B/3B tiling schemas,
                        · CDN policy and RNG policy against their policy schemas.

virtual_classification_3B,
virtual_settlement_3B
                ->  (S2.3) Derive virtual merchant set V & check settlement coverage
                    - From virtual_classification_3B:
                        · M = set of all merchant_id,
                        · V = { m ∈ M | is_virtual(m)=1 }.
                    - From virtual_settlement_3B:
                        · ensure exactly one row per m ∈ V
                          (and no rows for non-virtual merchants).
                    - If any virtual merchant lacks a settlement row:
                        · S2 MUST signal a 3B.S1 contract violation; no edge catalogue may be emitted.
                    - After this step:
                        · V is fixed,
                        · per-merchant settlement data is known and read-only.

CDN policy packs,
tiling surfaces,
hrsl_raster,
civil_time_manifest / tz assets,
RNG policy (for later)
                ->  (S2.4) Load policy-driven constants (no RNG)
                    - Parse CDN policy pack(s) into in-memory structures:
                        · global country weights w_global(c),
                        · class mapping function class(m) (if used),
                        · E_total(class) nominal per-merchant edges,
                        · min_edges_per_merchant, max_edges_per_merchant,
                        · any per-country floors/caps.
                    - Prepare tiling surfaces:
                        · build per-country tile set T_c from tile_index and tile_weights,
                        · check Σ_t w_tile(c,t) > 0 for each c with any tile.
                    - Prepare tz resolvers from civil_time_manifest:
                        · pointer to tz polygons, tzdb archive & overrides,
                        · 2A-compatible point→tzid mapping.
                    - Prepare RNG config:
                        · stream/substream layout reserved for S2:
                              module="3B.S2",
                              substream_label ∈ {"edge_tile_assign","edge_jitter"} (or equivalent),
                        · per-stream draw budgets per edge slot and jitter attempt.

### Phase B — Edge budgets per merchant & country (RNG-free)

virtual_classification_3B (M,V),
CDN policy packs
                ->  (S2.5) Compute per-merchant total edge budgets E_clipped(m)
                    - For each m ∈ V:
                        1. Determine class(m) using policy-defined mapping (deterministic function of S1 attributes / allow lists).
                        2. Compute nominal edges:
                               E_nominal(m) = E_total(class(m)).
                        3. Apply global min/max:
                               E_clipped(m) = clamp(E_nominal(m),
                                                    min_edges_per_merchant,
                                                    max_edges_per_merchant),
                           then integerise (fixed rounding rule) so E_clipped(m) ∈ ℕ.
                    - If policy disallows zero-edge virtual merchants:
                        · require E_clipped(m) ≥ 1 for all m; else configuration error.
                    - Result:
                        · total edge budget E_clipped(m) per virtual merchant.

CDN policy packs,
V, E_clipped(m)
                ->  (S2.6) Compute per-merchant country weights w_m(c) and shares s_m(c)
                    - For each m ∈ V:
                        1. Start from country weights:
                               w_m(c) = w_global(c),
                           or override via w_class/class-specific rules if configured.
                        2. Restrict to allowed countries:
                               C_m = { c | w_m(c) > 0 and policy allows m to have edges in c }.
                        3. Normalise:
                               Z_m = Σ_{c∈C_m} w_m(c) (must be > 0),
                               s_m(c) = w_m(c) / Z_m for c ∈ C_m.
                    - All choices (global vs per-class vs per-merchant overrides) MUST be deterministic and documented in the CDN policy.

E_clipped(m),
s_m(c) over C_m
                ->  (S2.7) Integerise per-merchant country budgets E_m(c)
                    - For each m ∈ V:
                        1. Compute real-valued targets:
                               T_m(c) = E_clipped(m) * s_m(c), for c ∈ C_m.
                        2. Base integer counts:
                               b_m(c) = floor(T_m(c)) (for each c).
                        3. base_sum_m = Σ_{c∈C_m} b_m(c);
                               R_m = E_clipped(m) − base_sum_m.
                        4. Residuals:
                               r_m(c) = T_m(c) − b_m(c).
                        5. Rank countries by:
                               - descending r_m(c),
                               - then ascending country_iso,
                               - then stable secondary key (e.g. ASCII-lex of (country_iso, merchant_id)).
                        6. Assign extra units:
                               E_m(c) = b_m(c) + 1 if c among top R_m in this ranking,
                                        b_m(c) otherwise.
                    - Invariants:
                        · Σ_{c∈C_m} E_m(c) = E_clipped(m),
                        · E_m(c) ≥ 0 for all c,
                        · any policy-defined floors/caps respected (possibly by adjusting E_clipped(m) or redistributing deterministically).

### Phase C — Tile-level edge allocation per country (RNG-free)

tiling surfaces (tile_index, tile_weights)
                ->  (S2.8) Build per-country tile sets T_c and p_tile(c,t)
                    - For each country c with any edges (some m with E_m(c) > 0):
                        1. Enumerate tiles:
                               T_c = { t | tile_index(c,t) exists and is eligible for edge placement }.
                        2. Associate raw tile weights:
                               w_tile(c,t) from tile_weights (or equivalent).
                        3. Normalise:
                               W_c = Σ_{t∈T_c} w_tile(c,t) (> 0) else configuration error,
                               p_tile(c,t) = w_tile(c,t) / W_c.
                    - T_c and p_tile(c,t) are RNG-free planning surfaces for tile allocation.

E_m(c),
T_c, p_tile(c,t)
                ->  (S2.9) Integerise per-tile edge counts E_m(c,t)
                    - For each (m,c) with E_m(c) > 0:
                        1. Compute real-valued targets:
                               U_m(c,t) = E_m(c) * p_tile(c,t) for each t ∈ T_c.
                        2. Base integer counts:
                               b_m(c,t) = floor(U_m(c,t)).
                        3. base_sum_m_c = Σ_{t∈T_c} b_m(c,t);
                               R_m(c) = E_m(c) − base_sum_m_c.
                        4. Residuals:
                               r_m(c,t) = U_m(c,t) − b_m(c,t).
                        5. Rank tiles by:
                               - descending r_m(c,t),
                               - then ascending tile_id,
                               - then stable tertiary key (e.g. (country_iso, merchant_id)).
                        6. Assign extra units:
                               E_m(c,t) = b_m(c,t) + 1 if t among top R_m(c),
                                          b_m(c,t) otherwise.
                    - Invariants:
                        · Σ_{t∈T_c} E_m(c,t) = E_m(c) for each (m,c),
                        · E_m(c,t) ≥ 0 for all tiles,
                        · no edges assigned to tiles not in T_c.

### Phase D — Edge placement within tiles (RNG-bearing)

RNG policy,
E_m(c,t),
tiling surfaces,
hrsl_raster,
country polygons
                ->  (S2.10) Place edges within tiles using RNG (jitter)
                    - Let E_total = Σ_{m∈V} Σ_{c∈C_m} Σ_{t∈T_c} E_m(c,t) (total edge slots).
                    - For each (m,c,t) with E_m(c,t) > 0:
                        · For k = 1..E_m(c,t) (edge slots in this tile):
                            1. Use RNG policy to derive a Philox stream/substream for this edge slot
                               (module="3B.S2", substream_label="edge_jitter" or equivalent; keyed by seed, parameter_hash, manifest_fingerprint, merchant_id, tile_id, edge_seq_index).
                            2. Jitter attempts:
                                   a. Draw u_lon, u_lat ∈ (0,1) via Philox (respecting per-event draw budgets).
                                   b. Map (u_lon, u_lat) into a candidate (lon_candidate, lat_candidate) inside tile t
                                      (e.g. linear map within pixel bounds or polygonal rejection).
                                   c. Check:
                                          - candidate lies within tile geometry t,
                                          - candidate lies within country polygon for c.
                                   d. If both pass:
                                          - accept this coordinate,
                                          - log rng_event_edge_jitter with envelope (counters_before/after, blocks, draws).
                                   e. If either fails:
                                          - log rng_event_edge_jitter as a jitter attempt,
                                          - retry up to JITTER_MAX_ATTEMPTS.
                            3. If JITTER_MAX_ATTEMPTS exhausted without valid point:
                                   - treat as FATAL jitter error; S2 MUST abort and MUST NOT “force” an invalid coordinate.
                    - RNG discipline:
                        · All jitter events logged with correct {blocks, draws} matching actual uniforms used,
                        · No RNG use outside Phase D,
                        · RNG trace/audit logs updated accordingly.

### Phase E — Operational timezone assignment (RNG-free)

edge coordinates (lon_deg, lat_deg),
civil_time_manifest / tz assets
                ->  (S2.11) Assign tzid_operational & tz_source per edge
                    - For each edge node (m, slot k):
                        1. If a trusted tzid is present from upstream mapping (rare case):
                               - validate against tz-world/tzdb,
                               - set tzid_operational and tz_source="INGESTED" (if allowed by spec).
                        2. Otherwise:
                               - call 2A-compatible mapping:
                                     tzid_operational = map_point_to_tzid(lon_deg, lat_deg, tz_world, tzdb, overrides),
                                 with the same ε-nudge and override precedence rules as 2A.
                               - set tz_source ∈ {"POLYGON","OVERRIDE","NUDGE"} accordingly.
                    - Invariants:
                        · tzid_operational must be a valid IANA tzid,
                        · S2 MUST NOT introduce non-IANA tzids or bespoke tz names.

### Phase F — Edge identity, weights & catalogue outputs (RNG-free)

edge slots (m,c,t,k) with coordinates & tzid,
CDN policy (edge weight law)
                ->  (S2.12) Construct edge_id, edge_seq_index, edge_weight, edge_digest
                    - For each merchant m ∈ V:
                        1. Enumerate its edge slots in a **deterministic order**:
                               e.g. sort by (country_iso, tile_id, jitter_rank).
                        2. Assign edge_seq_index = 0..E_clipped(m)−1 in that order.
                        3. Construct edge_id(m,k) deterministically, e.g.:
                               k_bytes = UTF8("3B.EDGE") || 0x1F || UTF8(merchant_id) || 0x1F || LE32(edge_seq_index),
                               digest = SHA256(k_bytes),
                               edge_id = LOW64(digest) as 16-char zero-padded lower-case hex.
                        4. Compute edge_weight:
                               - derive from per-country weights s_m(c) and tile weights p_tile(c,t), or
                               - treat all edges for m as uniform,
                               - then normalise so Σ_edges_of_m edge_weight = 1.
                        5. Compute edge_digest:
                               - SHA256 over a canonical per-edge representation (e.g. merchant_id, edge_id, country_iso,
                                 lat_deg, lon_deg, tzid_operational) as defined in schemas.3B.yaml.
                    - All of the above are RNG-free; they depend only on prior phases and policy.

edge rows,
[Schema+Dict]
                ->  (S2.13) Assemble and write edge_catalogue_3B (write-once)
                    - Build table with one row per edge node:
                        · fields as per schemas.3B.yaml#/plan/edge_catalogue_3B.
                    - Sort by [merchant_id, edge_id].
                    - Validate against schema (columns_strict, PK, partition_keys).
                    - Target path from dictionary:
                        · data/layer1/3B/edge_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/…
                    - Immutability:
                        · if partition empty → write via staging → fsync → atomic move.
                        · if partition exists:
                              - read existing dataset, normalise schema & sort,
                              - if byte-identical → idempotent re-run; OK,
                              - else → immutability violation; MUST NOT overwrite.

edge_catalogue_3B,
[Schema+Dict]
                ->  (S2.14) Build and write edge_catalogue_index_3B (write-once)
                    - Derive per-merchant summaries:
                        · for each m ∈ V:
                              edge_count_total(m) = number of rows in edge_catalogue_3B with merchant_id=m,
                              edge_digest(m)      = SHA256(canonical concatenation of edges for m),
                              country_mix_summary(m) = human-readable or JSON-encoded summary of country_iso distribution.
                        · create MERCHANT rows:
                              scope="MERCHANT",
                              merchant_id=m,
                              edge_count_total=edge_count_total(m),
                              edge_digest=edge_digest(m),
                              edge_catalogue_path,
                              edge_catalogue_size_bytes (optional),
                              notes (optional).
                    - Derive global summary:
                        · edge_count_total_all_merchants = Σ_m edge_count_total(m),
                        · edge_catalogue_digest_global   = SHA256(canonical concatenation of all edge rows or per-merchant digests).
                        · create GLOBAL row:
                              scope="GLOBAL",
                              merchant_id=null,
                              edge_count_total_all_merchants,
                              edge_catalogue_digest_global,
                              notes (optional).
                    - Assemble index table, sort by [scope, merchant_id].
                    - Validate against schemas.3B.yaml#/plan/edge_catalogue_index_3B.
                    - Target path:
                        · data/layer1/3B/edge_catalogue_index/seed={seed}/fingerprint={manifest_fingerprint}/edge_catalogue_index_3B.parquet
                    - Immutability:
                        · same write-once/idempotence rules as edge_catalogue_3B.

rng_event_edge_*,
rng_trace_log,
rng_audit_log
                ->  (S2.15) RNG trace & audit consistency (Phase D post-conditions)
                    - Using layer-wide RNG infrastructure:
                        · aggregate all S2 RNG events (jitter/placement) for module="3B.S2",
                        · compute total draws, blocks, counters_used.
                    - Update or verify rng_trace_log entries for:
                        · (seed, parameter_hash, run_id, module="3B.S2", substreams="edge_tile_assign"/"edge_jitter").
                    - Update/verify rng_audit_log to reflect:
                        · number of edges,
                        · number of RNG events,
                        · draws per edge vs policy budget.
                    - S2 MUST NOT emit additional RNG events beyond those specified in Phase D.

Downstream touchpoints
----------------------
- **3B.S3 — Edge alias tables & edge_universe_hash:**
    - MUST treat `edge_catalogue_3B` as the **only** authority on:
          - the set of edges per merchant,
          - their coordinates,
          - `tzid_operational` and `tz_source`,
          - `edge_weight`.
    - MUST treat `edge_catalogue_index_3B` as the sole digest/index surface for per-merchant and global summaries.

- **3B.S4 — Virtual routing & validation contracts:**
    - Uses `edge_catalogue_index_3B` and `edge_universe_hash_3B` (constructed in S3) to bind routing policy
      to a specific virtual edge universe.

- **3B.S5 — 3B validation bundle & `_passed.flag`:**
    - Replays S2’s structural invariants:
          - domain coverage vis-à-vis V and tiling surfaces,
          - count conservation (E_m(c), E_m(c,t), edge counts),
          - RNG accounting (events & trace vs budgets),
          - digest coherence edge_catalogue_3B ↔ edge_catalogue_index_3B.

- **Cross-segment consumers (2B routing, analytics):**
    - MUST NOT read `edge_catalogue_3B` or `edge_catalogue_index_3B` directly unless 3B’s segment-level HashGate
      (S5 bundle + `_passed.flag`) is PASS for this `manifest_fingerprint` (No PASS → No read).
```