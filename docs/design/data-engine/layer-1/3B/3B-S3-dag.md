```
        LAYER 1 · SEGMENT 3B — STATE S3 (EDGE ALIAS TABLES & VIRTUAL EDGE UNIVERSE HASH)  [NO RNG]

Authoritative inputs (read-only at S3 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_3B
      @ data/layer1/3B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3B.json
      · sole authority for this manifest on:
          - identity triple {seed, parameter_hash, manifest_fingerprint},
          - upstream gates for segments 1A, 1B, 2A, 3A (all MUST be status="PASS"),
          - catalogue_versions for {schemas.3B, dataset_dictionary.layer1.3B, artefact_registry_3B}.
    - sealed_inputs_3B
      @ data/layer1/3B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3B.parquet
      · whitelist of all external artefacts S3 MAY read (CDN weights, alias-layout policy, RNG/routing policy, virtual rules,
        spatial surfaces, etc.).
      · Any external artefact S3 reads MUST:
          - appear in sealed_inputs_3B with matching {logical_id, path, schema_ref},
          - match sha256_hex when S3 recomputes SHA-256 over bytes.

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml
        · numeric policy (binary64, RNE, no FMA/FTZ/DAZ),
        · RNG envelopes (for compatibility with 2B, although S3 uses no RNG).
    - schemas.3B.yaml
        · anchors for:
            - binary/edge_alias_blob_header_3B,
            - plan/edge_alias_index_3B,
            - validation/edge_universe_hash_3B,
            - validation/gamma_draw_log_entry_3B.
    - dataset_dictionary.layer1.3B.yaml
        · IDs→{path, partitioning, schema_ref} for:
            - edge_catalogue_3B, edge_catalogue_index_3B (inputs from S2),
            - edge_alias_blob_3B, edge_alias_index_3B, edge_universe_hash_3B, gamma_draw_log_3B (S3 outputs).
    - artefact_registry_3B.yaml
        · manifests for alias-layout policy, CDN policy digests, virtual rules digest, RNG/routing policy digests, etc.

[3B data-plane inputs from S2 (edge universe)]
    - edge_catalogue_3B
      @ data/layer1/3B/edge_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/…
      · producer: 3B.S2.
      · PK/sort: [merchant_id, edge_id] (canonical key order).
      · columns (min):
            merchant_id, edge_id,
            country_iso,
            lat_deg, lon_deg,
            tzid_operational, tz_source,
            edge_weight ≥ 0,
            any spatial/RNG provenance from S2.
      · S3’s use:
            - define per-merchant edge sets E_m and raw edge_weight(m, edge_id),
            - S3 MUST NOT add/remove edges or change any of these fields.

    - edge_catalogue_index_3B
      @ data/layer1/3B/edge_catalogue_index/seed={seed}/fingerprint={manifest_fingerprint}/edge_catalogue_index_3B.parquet
      · producer: 3B.S2.
      · PK/sort: [scope, merchant_id], where:
            scope="MERCHANT" rows ⇒ per-merchant counts/digests,
            scope="GLOBAL"   rows ⇒ aggregate counts/digest.
      · columns (min):
            scope,
            merchant_id?,
            edge_count_total?,
            edge_digest?,
            edge_count_total_all_merchants? (GLOBAL),
            edge_catalogue_digest_global? (GLOBAL),
            notes?.
      · S3’s use:
            - sanity check per-merchant edge counts vs edge_catalogue_3B,
            - re-use or recompute global edge_catalogue_digest_global for universe hash.

[Optional context from S1]
    - virtual_classification_3B, virtual_settlement_3B
      · producer: 3B.S1.
      · S3 MAY read for:
            - consistency checks (e.g. “edge_catalogue_3B only contains virtual merchants”),
            - diagnostics.
      · S3 MUST NOT re-classify or reinterpret settlement semantics.

[Alias-layout & routing policy artefacts]
    - Alias-layout policy for edges (e.g. edge_alias_layout_policy_v1)
        · resolved via sealed_inputs_3B.
        · defines:
            - layout_version, header fields,
            - endianness, alignment_bytes,
            - integer grid size G (e.g. 2^b),
            - quantisation law (targets, floors, residual handling),
            - per-merchant checksum algorithm (merchant_alias_checksum),
            - mapping from alias indices to edges.
        · This is the sole authority on how alias tables are encoded in the blob.

    - RNG / routing policy artefact(s)
        · define compatibility expectations for how 2B will decode alias tables:
            - which layout_version values 2B supports,
            - expectations on index→edge_id mapping.
        · S3 is RNG-free but MUST ensure alias layout is compatible with this policy.

[Policy/edge digests for universe hash]
    - cdn_country_weights_digest (or equivalent) — from sealed CDN weights artefact(s).
    - virtual_rules_digest        — from sealed mcc_channel_rules / virtual classification policy artefact(s).
    - edge_catalogue_index_digest — from edge_catalogue_index_3B scope=GLOBAL row or recomputed.
    - edge_alias_index_digest     — will be computed over edge_alias_index_3B by S3.
    - These four digests, plus derived universe_hash, populate edge_universe_hash_3B.

[Outputs owned by S3]
    - edge_alias_blob_3B
      @ data/layer1/3B/edge_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_blob_3B.bin
      · partition_keys: [seed, fingerprint]
      · schema_ref: schemas.3B.yaml#/binary/edge_alias_blob_header_3B (for header)
      · header fields (min):
            layout_version, endianness, alignment_bytes,
            blob_length_bytes, blob_sha256_hex,
            alias_layout_policy_id, alias_layout_policy_version,
            universe_hash (virtual edge universe hash echoed here),
            notes (optional).

    - edge_alias_index_3B
      @ data/layer1/3B/edge_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_index_3B.parquet
      · partition_keys: [seed, fingerprint]
      · primary_key:    [scope, merchant_id]
      · sort_keys:      [scope, merchant_id]
      · schema_ref: schemas.3B.yaml#/plan/edge_alias_index_3B
      · rows:
            * scope="MERCHANT": one row per merchant with alias segment metadata & checksum.
            * scope="GLOBAL":   one or few summary rows with blob-level metadata & digests.

    - edge_universe_hash_3B
      @ data/layer1/3B/edge_universe_hash/fingerprint={manifest_fingerprint}/edge_universe_hash_3B.json
      · partition_keys: [fingerprint]
      · schema_ref: schemas.3B.yaml#/validation/edge_universe_hash_3B
      · fields:
            manifest_fingerprint,
            parameter_hash,
            cdn_weights_digest,
            edge_catalogue_index_digest,
            edge_alias_index_digest,
            virtual_rules_digest,
            universe_hash,
            created_at_utc (non-authoritative timestamp).

    - gamma_draw_log_3B   (guardrail; expected empty)
      @ logs/layer1/3B/gamma_draw/seed={seed}/fingerprint={manifest_fingerprint}/gamma_draw_log_3B.jsonl
      · partition_keys: [seed, fingerprint]
      · schema_ref: schemas.3B.yaml#/validation/gamma_draw_log_entry_3B
      · MUST exist (even as an empty shard) for this run; SHOULD contain zero records.


[Numeric & RNG posture]
    - S3 is **strictly RNG-free**:
        · MUST NOT open or advance any Philox stream,
        · MUST NOT emit any RNG events,
        · MUST NOT modify RNG policy artefacts.
    - Determinism:
        · Given fixed {seed, parameter_hash, manifest_fingerprint}, sealed_inputs_3B, S1/S2 outputs, alias-layout policy,
          and catalogue, S3 MUST produce bit-identical:
              edge_alias_blob_3B, edge_alias_index_3B, edge_universe_hash_3B, gamma_draw_log_3B.
    - Time:
        · created_at_utc in edge_universe_hash_3B MUST either be:
              - supplied by deterministic harness input, or
              - omitted / treated as non-authoritative; S3 MUST NOT call `now()`.


----------------------------------------------------------------------
DAG — 3B.S3 (S2 edge universe → alias blob, alias index, edge universe hash)  [NO RNG]

### Phase A — Environment & input load (RNG-free)

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S3.1) Validate S0 gate & align identity
                    - Resolve:
                        · s0_gate_receipt_3B@fingerprint={manifest_fingerprint},
                        · sealed_inputs_3B@fingerprint={manifest_fingerprint},
                      via dataset_dictionary.layer1.3B.yaml.
                    - Validate both against schemas.3B.yaml.
                    - Check identity:
                        · receipt.manifest_fingerprint == target manifest_fingerprint,
                        · (if present) receipt.seed == seed, receipt.parameter_hash == parameter_hash.
                    - Check upstream gates in receipt:
                        · segment_1A.status == segment_1B.status == segment_2A.status == segment_3A.status == "PASS".
                    - On any failure: treat as FATAL; S3 MUST NOT produce outputs.

sealed_inputs_3B,
[Schema+Dict]
                ->  (S3.2) Resolve required inputs (edge universe + policies)
                    - Using sealed_inputs_3B + dictionary+registry, resolve:
                        · edge_catalogue_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · edge_catalogue_index_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · alias-layout policy artefact(s) for edges,
                        · RNG/routing policy artefact(s) relevant to alias decoding,
                        · cdn_country_weights (for cdn_weights_digest),
                        · virtual_rules policy (for virtual_rules_digest).
                    - For each external artefact:
                        · recompute SHA-256 over raw bytes,
                        · assert equality with sealed_inputs_3B.sha256_hex.
                    - Validate shapes:
                        · edge_catalogue_3B, edge_catalogue_index_3B against schemas.3B.yaml,
                        · alias-layout and RNG/routing policies against their policy schemas
                          (layout version, grid size G, quantisation rules, checksum fields, compatibility flags).

edge_catalogue_3B,
edge_catalogue_index_3B
                ->  (S3.3) Edge universe domain & consistency checks
                    - From edge_catalogue_3B:
                        · derive per-merchant edge sets:
                              E_m = sorted list of edges for merchant m, sorted by (merchant_id, edge_id).
                        · compute:
                              edge_count_total_from_rows(m) = |E_m|.
                    - From edge_catalogue_index_3B:
                        · read scope="MERCHANT" rows:
                              edge_count_total_index(m).
                        · read scope="GLOBAL" row(s):
                              edge_count_total_all_merchants_index,
                              edge_catalogue_digest_global (optional).
                    - S3 MUST assert:
                        · the set of merchants in index == set of merchants in edge_catalogue_3B,
                        · for each m:
                              edge_count_total_from_rows(m) == edge_count_total_index(m),
                        · Σ_m edge_count_total_index(m) == edge_count_total_all_merchants_index (if present).
                    - Any mismatch ⇒ edge-universe inconsistency ⇒ S3 MUST fail.

### Phase B — Per-merchant edge lists & weight preparation (RNG-free)

edge_catalogue_3B (canonical sort),
alias-layout policy
                ->  (S3.4) Canonical per-merchant edge lists & raw weights
                    - Sort edge_catalogue_3B globally by:
                        1. merchant_id ASC,
                        2. edge_id ASC.
                    - For each merchant m:
                        · define:
                              E_m = (e₀, e₁, …, e_{n−1}) in this order,
                              w_raw(m,i) = edge_weight(e_i).
                        - n = |E_m|; may be 0 or 1 in edge cases.
                    - S3 MUST NOT drop any edge; E_m must cover all rows for m.

E_m, w_raw(m,i),
alias-layout policy
                ->  (S3.5) Clamp & normalise weights per merchant
                    - For each merchant m:
                        1. Clamp negatives:
                               w_pos(m,i) = max(w_raw(m,i), 0).
                        2. Compute:
                               Z_m = Σ_i w_pos(m,i).
                        3. If n > 0 and Z_m ≤ 0:
                               - behaviour MUST follow alias-layout policy:
                                   · preferred: treat as FATAL (`E3B_S3_ZERO_WEIGHT_SUM`),
                                   · or use an explicit documented fallback (e.g. uniform distribution),
                                     marking this in metadata if schema allows.
                        4. If Z_m > 0:
                               - normalise:
                                     w_norm(m,i) = w_pos(m,i) / Z_m.
                    - S3 MUST NOT silently “fix” weight shapes beyond what alias-layout policy prescribes.

w_norm(m,i),
alias-layout policy (grid size G & quantisation law)
                ->  (S3.6) Quantise weights onto integer grid M(m,i)
                    - Alias-layout policy defines:
                        · grid size G (e.g. G = 2^b or G = 10^d),
                        · allowed max quantisation error.
                    - For each merchant m:
                        1. Compute real targets:
                               M_target(m,i) = G * w_norm(m,i).
                        2. Base masses:
                               M_base(m,i) = floor(M_target(m,i)).
                        3. base_sum_m = Σ_i M_base(m,i),
                               R_m = G − base_sum_m.
                        4. Residuals:
                               r_m(i) = M_target(m,i) − M_base(m,i).
                        5. Rank indices i by:
                               - descending r_m(i),
                               - then ascending i (or edge_id) as tie-break.
                        6. Final masses:
                               M(m,i) = M_base(m,i) + 1 for top R_m indices,
                                        M_base(m,i)     otherwise.
                    - S3 MUST verify:
                        · Σ_i M(m,i) == G for each m,
                        · per-policy quantisation error tolerances are respected.

### Phase C — Per-merchant alias table construction (RNG-free)

E_m, M(m,i),
alias-layout policy
                ->  (S3.7) Build alias table per merchant
                    - For merchant m with n = |E_m| edges:
                        · define canonical index mapping:
                              i ∈ {0,…,n−1} ↔ edge e_i in the order from (S3.4).
                        - Treat M(m,i) as integer “mass” per index on grid G.
                    - Using alias-layout policy, S3 MUST:
                        · construct an alias table (arrays of prob/alias integers) that:
                              - covers indices {0,…,alias_table_length−1},
                              - encodes a distribution exactly M(m,i)/G (within allowed tolerances),
                              - uses a fully-specified deterministic queue/stack discipline (e.g. Walker/Vose with queues).
                        - Handle degenerate cases:
                              - n = 0:
                                    * behaviour dictated by policy (e.g. disallowed or “no-edge” mode),
                              - n = 1:
                                    * trivial alias table that always picks edge 0.

alias tables per merchant,
alias-layout policy
                ->  (S3.8) Map alias indices back to edges
                    - S3 MUST ensure that, for each merchant m:
                        · there is a clear, deterministic mapping from alias index i to edge_id:
                              - either implicit via “edges sorted by edge_id in edge_catalogue_3B”, or
                              - via extra metadata agreed in alias-layout policy.
                    - This mapping MUST:
                        · match 2B’s decoding expectations from the RNG/routing policy,
                        · be independent of in-memory or file iteration order.

### Phase D — Blob layout & index construction (RNG-free)

alias tables per merchant,
alias-layout policy
                ->  (S3.9) Lay out alias blob & header
                    - Choose canonical merchant order:
                        · merchants sorted ascending by merchant_id (or agreed composite key).
                    - Initialise offset `off = header_size`, respecting alignment_bytes from alias-layout policy.
                    - For each merchant in order:
                        1. Serialise merchant’s alias table to bytes:
                               - using layout_version & endianness from policy,
                               - producing a contiguous segment of length len_m bytes.
                        2. Align:
                               - round `off` up to next multiple of alignment_bytes,
                               - write alias segment at offset `off`.
                        3. Append segment bytes to blob buffer.
                        4. Compute merchant_alias_checksum(m) over this segment (algorithm per policy).
                        5. Record for index:
                               blob_offset_bytes(m) = off (post-alignment),
                               blob_length_bytes(m) = len_m.
                        6. Update off ← off + len_m.
                    - After all merchants:
                        · blob_length_bytes = total size of blob buffer,
                        · blob_sha256_hex   = SHA256(blob buffer),
                        · construct header object:
                              layout_version,
                              endianness,
                              alignment_bytes,
                              blob_length_bytes,
                              blob_sha256_hex,
                              alias_layout_policy_id/version,
                              universe_hash = null/placeholder (to be filled after Phase E).

per-merchant metadata (offset, length, edge counts, checksums),
blob header
                ->  (S3.10) Build edge_alias_index_3B rows
                    - For each merchant m:
                        · read edge_count_total(m) from edge_catalogue_index_3B (MERCHANT row),
                        · alias_table_length(m) from alias table size,
                        · construct MERCHANT-scope row:
                              scope                 = "MERCHANT",
                              seed, fingerprint,
                              merchant_id=m,
                              blob_offset_bytes     = blob_offset_bytes(m),
                              blob_length_bytes     = blob_length_bytes(m),
                              edge_count_total      = edge_count_total(m),
                              alias_table_length    = alias_table_length(m),
                              merchant_alias_checksum = merchant_alias_checksum(m),
                              alias_layout_version  = header.layout_version,
                              universe_hash         = null (to be filled later),
                              blob_sha256_hex       = header.blob_sha256_hex.
                    - Construct GLOBAL-scope row(s):
                        · aggregate:
                              edge_count_total_all_merchants = Σ_m edge_count_total(m),
                              blob_length_bytes              = header.blob_length_bytes,
                              blob_sha256_hex                = header.blob_sha256_hex,
                              edge_catalogue_digest_global   = value from edge_catalogue_index_3B GLOBAL row (if present).
                        · create row:
                              scope          = "GLOBAL",
                              merchant_id    = null,
                              edge_count_total_all_merchants,
                              blob_length_bytes,
                              blob_sha256_hex,
                              edge_catalogue_digest_global (if available).
                    - Assemble table, sort by [scope, merchant_id], validate against schemas.3B.yaml#/plan/edge_alias_index_3B.

### Phase E — Digest computation & edge universe hash (RNG-free)

cdn_country_weights artefact,
virtual_rules artefact,
edge_catalogue_index_3B,
edge_alias_index_3B
                ->  (S3.11) Compute component digests for edge_universe_hash_3B
                    - cdn_weights_digest:
                        · SHA256 over canonical bytes of sealed cdn_country_weights artefact(s).
                    - edge_catalogue_index_digest:
                        · SHA256 over canonical bytes of edge_catalogue_index_3B
                          (e.g. concatenated Parquet data file bytes in ASCII-lex path order).
                    - edge_alias_index_digest:
                        · SHA256 over canonical bytes of edge_alias_index_3B.
                    - virtual_rules_digest:
                        · SHA256 over canonical bytes of the sealed virtual rules policy artefact(s) (e.g. mcc_channel_rules).
                    - S3 MUST record these four digests as the only component digests in edge_universe_hash_3B.

cdn_weights_digest,
edge_catalogue_index_digest,
edge_alias_index_digest,
virtual_rules_digest
                ->  (S3.12) Compute combined universe_hash
                    - Construct an ordered list or structure of components:
                        · e.g. [("cdn_weights", cdn_weights_digest),
                                ("edge_catalogue_index", edge_catalogue_index_digest),
                                ("edge_alias_index", edge_alias_index_digest),
                                ("virtual_rules", virtual_rules_digest)].
                    - Sort this list by component name in ASCII-lex order.
                    - Concatenate digest bytes (or their hex) in that order to form a byte string B.
                    - Compute:
                        · universe_hash = SHA256(B), encoded as lower-case hex.
                    - This universe_hash MUST be used consistently:
                        · in edge_universe_hash_3B,
                        · echoed into edge_alias_blob_3B header and edge_alias_index_3B rows.

cdn_weights_digest,
edge_catalogue_index_digest,
edge_alias_index_digest,
virtual_rules_digest,
universe_hash
                ->  (S3.13) Build edge_universe_hash_3B object
                    - Construct JSON object conforming to schemas.3B.yaml#/validation/edge_universe_hash_3B:
                        · manifest_fingerprint = current manifest_fingerprint,
                        · parameter_hash       = current parameter_hash,
                        · cdn_weights_digest,
                        · edge_catalogue_index_digest,
                        · edge_alias_index_digest,
                        · virtual_rules_digest,
                        · universe_hash,
                        · created_at_utc       = harness-supplied timestamp or omitted if not available.
                    - Validate against schema.
                    - Later, S3 or validation MUST ensure:
                        · the digests used here match those recorded in sealed_inputs_3B and in index/header.

### Phase F — Output materialisation & guardrails (RNG-free)

alias blob (header+payload),
edge_alias_index_3B table,
edge_universe_hash_3B object
                ->  (S3.14) Finalise header/index with universe_hash & write outputs
                    - Update header.universe_hash = universe_hash.
                    - Update each edge_alias_index_3B row:
                        · set universe_hash = universe_hash (MERCHANT and GLOBAL scope).
                    - Validate:
                        · header matches schemas.3B.yaml#/binary/edge_alias_blob_header_3B,
                        · edge_alias_index_3B matches schemas.3B.yaml#/plan/edge_alias_index_3B.
                    - Write `edge_alias_blob_3B`:
                        · path: data/layer1/3B/edge_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_blob_3B.bin
                        · write blob bytes (header + segments) via staging → fsync → atomic move.
                        · if file already exists:
                              - read existing bytes and compare to candidate,
                              - if identical → idempotent re-run; OK,
                              - else → immutability violation; MUST NOT overwrite.
                    - Write `edge_alias_index_3B`:
                        · path: data/layer1/3B/edge_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_index_3B.parquet
                        · same immutability/idempotence rules as above.
                    - Write `edge_universe_hash_3B`:
                        · path: data/layer1/3B/edge_universe_hash/fingerprint={manifest_fingerprint}/edge_universe_hash_3B.json
                        · partition_keys: [fingerprint],
                        · immutability/idempotence as above.

[Schema+Dict],
gamma_draw_log_3B entry in dictionary
                ->  (S3.15) Publish gamma_draw_log_3B partition (expected empty)
                    - Locate dataset entry for `gamma_draw_log_3B` in dataset_dictionary.layer1.3B.yaml:
                        · path: logs/layer1/3B/gamma_draw/seed={seed}/fingerprint={manifest_fingerprint}/gamma_draw_log_3B.jsonl.
                    - S3 MUST:
                        · ensure the partition exists for this {seed, fingerprint},
                        · write an empty JSONL file (or equivalent proof of emptiness),
                        · MUST NOT write any records.
                    - Invariants:
                        · any record present in gamma_draw_log_3B constitutes `E3B_S3_RNG_USED` and is a fatal contract violation.

Downstream touchpoints
----------------------
- **3B.S4 — Virtual routing & validation contracts:**
    - Reads `edge_alias_index_3B` and `edge_universe_hash_3B` to:
        · reference alias layout/version and universe_hash in `virtual_routing_policy_3B`,
        · bind validation contracts to the exact virtual edge universe.

- **3B.S5 — 3B validation bundle & `_passed.flag_3B`:**
    - Uses:
        · `edge_alias_blob_3B`, `edge_alias_index_3B`, and `edge_universe_hash_3B`,
        · `edge_catalogue_3B`/`edge_catalogue_index_3B`,
        · `gamma_draw_log_3B`,
      to check:
        · alias index ↔ blob consistency,
        · merchant/global counts vs S2,
        · digests vs sealed_inputs_3B,
        · that S3 remained RNG-free (gamma_draw_log_3B empty).

- **2B virtual routing branch:**
    - MUST treat:
        · `edge_alias_blob_3B` + `edge_alias_index_3B` as the sole authority for per-merchant edge alias tables,
        · `edge_universe_hash_3B.universe_hash` as the virtual edge universe hash.
    - MUST enforce 3B’s segment-level HashGate (S5 bundle + `_passed.flag_3B`) before decoding alias tables:
          **No 3B PASS → No read** of 3B virtual edge artefacts.
```