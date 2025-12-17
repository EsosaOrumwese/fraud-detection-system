```
        LAYER 1 · SEGMENT 2B — STATE S2 (ALIAS TABLES: O(1) SAMPLER BUILD)  [NO RNG]

Authoritative inputs (read-only at S2 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_2B @ data/layer1/2B/s0_gate_receipt/fingerprint={manifest_fingerprint}/…
      · proves: 1B PASS already verified for this manifest_fingerprint (via 1B bundle + _passed.flag_1B)
      · binds this run identity: { seed, manifest_fingerprint, parameter_hash } for 2B
      · carries: catalogue_resolution, determinism_receipt (engine + alias policy IDs/digests)
    - sealed_inputs_v1 @ data/layer1/2B/sealed_inputs/fingerprint={manifest_fingerprint}/…
      · canonical inventory of every cross-layer/policy artefact S0 sealed for 2B under this fingerprint
      · For cross-layer or policy artefacts, S2 MUST treat its read set as a subset of this inventory (subset-of-S0 rule);
        within-segment datasets (e.g. `s1_site_weights`) are not S0-sealed but must be read at the exact
        `[seed, fingerprint]` partition via the Dictionary.

[Schema+Dict]
    - schemas.2B.yaml                     (shape authority for s1_site_weights, s2_alias_index, s2_alias_blob)
    - dataset_dictionary.layer1.2B.yaml   (ID → path/partitions/format for S1/S2/S7/S8 artefacts)
    - artefact_registry_2B.yaml           (ownership/licence/retention only; non-authoritative for paths)
    - schemas.layer1.yaml, schemas.ingress.layer1.yaml
      · supply core types (id64, hex64, rfc3339_micros, etc.) and bundle/index laws

[Required inputs (and nothing else)]
    - s1_site_weights
        · producer: 2B.S1
        · identity: `seed={seed} / fingerprint={manifest_fingerprint}`
        · PK: [merchant_id, legal_country_iso, site_order]
        · columns: p_weight ∈ [0,1], weight_source, quantised_bits, floor_applied, created_utc
        · role here: static per-site probability law per merchant; S2 SHALL NOT recompute weights from site_locations.
    - alias_layout_policy_v1
        · single JSON policy (no partition tokens; path/digest fixed by S0)
        · declares:
            · layout_version (string),
            · endianness ∈ {little, big},
            · alignment_bytes ≥ 1,
            · quantised_bits = b ≥ 1 (bit-depth; defines grid G = 2^b),
            · encode_spec (how to encode integer masses m_i into alias tables),
            · decode_law (how S5/S6 will read those tables),
            · checksum spec (per-merchant checksum field + blob_sha256 rule),
            · required_index_fields: {merchant_id, offset, length, sites, quantised_bits, checksum}.

[Explicit prohibitions & scope fences]
    - Inputs:
        · S2 MAY NOT read 2A pins (`site_timezones`, `tz_timetable_cache`) or any other artefacts.
        · Every cross-layer or policy input S2 resolves (here: `alias_layout_policy_v1`) MUST appear in `sealed_inputs_v1`
          for this fingerprint; within-segment datasets (here: `s1_site_weights`) MUST be read at the exact
          `[seed, fingerprint]` partition but are not S0-sealed.
    - Behaviours:
        · No literal paths, no globs, no network I/O, no re-hashing of 1B (S0 is the sole 1B gate).
        · S2 is RNG-free: it SHALL NOT consume Philox; downstream states handle RNG.

[Numeric & identity posture]
    - Numeric:
        · IEEE-754 binary64, round-to-nearest-even; no FMA/FTZ/DAZ; serial reductions only.
        · Deterministic tie-breaking by PK order wherever needed (remainder ordering, merchant order).
    - Identity & partitions:
        · Run identity: { seed, manifest_fingerprint }.
        · Outputs:
            · s2_alias_index @ data/layer1/2B/s2_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/index.json
            · s2_alias_blob  @ data/layer1/2B/s2_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/alias.bin
        · Path↔embed equality: any embedded manifest_fingerprint (and seed, if embedded) MUST equal the path tokens.
        · Outputs are write-once and immutable; re-emits must be bit-identical.


----------------------------------------------------------------------
DAG — 2B.S2 (s1_site_weights → alias blob + index)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S2.1) Verify S0 evidence & fix run identity
                    - Resolve s0_gate_receipt_2B and sealed_inputs_v1 for manifest_fingerprint via Dictionary.
                    - Validate both against schemas.2B.yaml anchors (structure, required fields).
                    - Fix run identity:
                        · {seed, manifest_fingerprint, parameter_hash} ← s0_gate_receipt_2B.
                    - Discover canonical created_utc:
                        · created_utc_S0 ← s0_gate_receipt_2B.verified_at_utc
                        · S2 SHALL echo created_utc_S0 into s2_alias_index.header.created_utc.
                    - Confirm posture:
                        · Dictionary-only resolution,
                        · S2 is RNG-free and MUST NOT re-hash or re-open 1B’s validation bundle.

[S0 Gate & Identity],
[Schema+Dict],
s1_site_weights,
alias_layout_policy_v1
                ->  (S2.2) Resolve inputs & basic sanity
                    - Resolve s1_site_weights for this {seed, fingerprint} via Dictionary; confirm:
                        · schema matches schemas.2B.yaml#/plan/s1_site_weights,
                        · PK [merchant_id, legal_country_iso, site_order] is unique.
                    - Resolve alias_layout_policy_v1 via the exact path/digest sealed by S0:
                        · confirm it appears in sealed_inputs_v1 (policy row),
                        · load policy minima: {layout_version, endianness, alignment_bytes,
                                              quantised_bits=b, encode_spec, decode_law, checksum, required_index_fields}.
                        · Abort if any required field is missing or invalid (b < 1, alignment_bytes < 1, etc.).
                    - Bit-depth coherence precheck:
                        · Assert that all rows in s1_site_weights have quantised_bits = b
                          (or that any deviation is explicitly permitted in the spec’s acceptance criteria);
                          otherwise Abort with BIT_DEPTH_MISMATCH.
                    - Record layout parameters for downstream steps:
                        · G = 2^b (grid size), endianness, alignment_bytes, decode_law, checksum algorithm.

[Schema+Dict],
s1_site_weights (grouped by merchant)
                ->  (S2.3) Grouping & PK order
                    - Group s1_site_weights rows by merchant_id:
                        · each merchant group carries all (legal_country_iso, site_order) for that merchant.
                    - Within each merchant group:
                        · order rows strictly by the PK triplet
                          [merchant_id, legal_country_iso, site_order].
                    - For each merchant:
                        · define K = number of sites (K ≥ 1).
                        · S2 SHALL use this order for all later tie-breaks
                          (remainder ordering, small/large queues, etc.).
                    - Abort if any merchant group is empty or PK uniqueness is broken.

[Policy alias layout],
s1_site_weights (ordered per merchant)
                ->  (S2.4) Integer grid reconstruction from p_weight
                    - Let b = policy.quantised_bits and G = 2^b (in binary64).
                    - For each merchant and each ordered site row with real probability p = p_weight:
                        8.  Compute real mass: m* = p · G (binary64).
                            · m* MUST be finite and ≥ 0; otherwise Abort.
                        9.  Initial integer mass: m⁰ = round_half_to_even(m*).
                            · Track fractional remainder r = m* − floor(m*) for tie-breaking.
                    - For the merchant:
                        · Compute Δ = G − Σ_i m⁰_i (serial reduction in PK order).
                        · If Δ = 0:
                            - Set m_i = m⁰_i for all sites.
                        · If Δ > 0 (deficit):
                            - Increment +1 the Δ rows with the largest r, breaking ties by PK order.
                        · If Δ < 0 (surplus):
                            - Decrement −1 the |Δ| rows with the smallest r, ties by PK order.
                        · Result:
                            - Integer masses {m_i} satisfying:
                                · Σ_i m_i = G
                                · 0 ≤ m_i ≤ G for all i.
                        - If any m_i < 0 or m_i > G → Abort with GRID_RECONSTRUCTION_ERROR.
                    - These integer masses {m_i} are the sole input to alias encoding;
                      S2 SHALL NOT look back at original floating p_weight except for post-publish checks.

(merchant→{m_i}, ordered),
[Policy alias layout]
                ->  (S2.5) Alias encoding (policy-declared, RNG-free)
                    - For each merchant group (K sites, integer masses m_i):
                        11. Compute threshold M = G / K conceptually in real arithmetic
                            (spec treats exact integer comparisons against m_i; no integer division truncation).
                        12. Initialise queues:
                            - small ← {indices i | m_i < M}, in PK order.
                            - large ← {indices i | m_i ≥ M}, in PK order.
                              (If m_i = M, treat as large; deterministic and avoids aliasing trivial 1/K entries.)
                        13. Encode loop (Vose/Walker-style; exact fields fixed by encode_spec):
                            While small and large are non-empty:
                              a) Pop s from front(small), l from front(large).
                              b) Emit alias entry for index s with:
                                    · base mass m_s,
                                    · alias partner index l,
                                    · per-entry scalar(s) as specified by encode_spec (e.g., scaled m_s/M).
                              c) Update m_l ← m_l − (M − m_s).
                                  - If m_l < M → push l to back(small);
                                  - else        → push l to back(large).
                        14. Residuals:
                            - After the loop, any remaining indices (in small or large) represent “pure” outcomes.
                            - Emit final alias entries for those using encode_spec’s residual rule.
                        15. Per-merchant invariants:
                            - Every site index appears in at least one entry.
                            - The encoded structure must be sufficient to reconstruct probabilities p̂_i exactly as m_i/G
                              when decoded by decode_law (enforced by post-publish checks, not here).
                    - All encode steps are deterministic given {m_i}, G, and the policy; no RNG permitted.

(encoded alias structures per merchant),
[Policy alias layout]
                ->  (S2.6) Blob serialisation & index header/body
                    - Blob serialisation:
                        16. Serialise, per merchant in ascending merchant_id:
                            · convert the encoded alias structures into binary bytes according to encode_spec:
                                - record/field order,
                                - integer widths,
                                - endianness (policy.endianness).
                        17. Alignment & padding:
                            - Maintain a running `offset` in bytes.
                            - Before writing each merchant’s slice:
                                · round `offset` up to the next multiple of alignment_bytes,
                                · fill any pad gap with the policy’s padding_rule (e.g. 0x00),
                                · record this aligned offset as the slice start.
                            - After writing the slice, compute `length` = slice_byte_count (excluding leading padding).
                        18. Per-merchant checksum:
                            - Compute checksum over the merchant’s slice bytes using the policy checksum algorithm.
                            - This checksum will be stored in the corresponding index.merchants row.
                        19. Offset/length bookkeeping:
                            - For each merchant, record `{merchant_id, offset, length, sites=K, quantised_bits=b, checksum}`.
                            - Enforce that merchants are tracked in strictly ascending merchant_id.

                    - Index header + blob digest:
                        20. Construct index header fields:
                            - layout_version  ← policy.layout_version
                            - endianness      ← policy.endianness
                            - alignment_bytes ← policy.alignment_bytes
                            - quantised_bits  ← policy.quantised_bits (b)
                            - created_utc     ← created_utc_S0
                            - policy_id       ← "alias_layout_policy_v1"
                            - policy_digest   ← digest recorded for alias_layout_policy_v1 in sealed_inputs_v1
                        21. Compute blob_sha256 as SHA-256 of the **raw blob bytes** just serialised.
                        22. Counts & bounds:
                            - blob_size_bytes ← total length of blob,
                            - merchants_count ← number of merchant rows,
                            - enforce for every row:
                                · offset % alignment_bytes == 0,
                                · 0 ≤ offset < blob_size_bytes,
                                · offset + length ≤ blob_size_bytes,
                              and merchant slices do not overlap.

(index+blob in memory),
[Schema+Dict]
                ->  (S2.7) Write s2_alias_index & s2_alias_blob (write-once)
                    - Paths (via Dictionary; no literals):
                        · s2_alias_index → data/layer1/2B/s2_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/index.json
                        · s2_alias_blob  → data/layer1/2B/s2_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/alias.bin
                    - Immutability:
                        - Partitions MUST be empty on first publish.
                        - If files exist:
                            · if bytes are bit-identical → treat as idempotent re-emit, no-op.
                            · else → Abort with IMMUTABLE_OVERWRITE.
                    - Atomic two-artefact transaction:
                        - Write index and blob to same-filesystem staging paths.
                        - fsync both.
                        - Atomic rename both into final Dictionary paths.
                        - No partially written artefact may become visible.
                    - After publish:
                        - re-open index.json and blob,
                        - validate index.json against schemas.2B.yaml#/plan/s2_alias_index (fields-strict),
                        - validate blob layout against the binary contract (endianness, alignment_bytes).

(published index+blob),
s1_site_weights,
[Policy alias layout]
                ->  (S2.8) Post-publish assertions & decode spot-check
                    - Path↔embed equality:
                        · any embedded {seed, manifest_fingerprint} in index/blob headers MUST equal path tokens.
                    - Digest coherence:
                        · recompute blob_sha256 over published blob,
                        · assert it matches index.header.blob_sha256.
                    - Coverage & structure:
                        · For every merchant_id:
                            - index.sites equals the count of rows in s1_site_weights for that merchant.
                            - index rows are strictly sorted by merchant_id.
                            - byte ranges [offset, offset+length) are non-overlapping and within blob_size_bytes.
                    - Decode spot-check (deterministic, bounded):
                        · Select up to N merchants (e.g. first N in merchant_id order).
                        · For each selected merchant, decode alias tables from the blob using decode_law
                          into reconstructed probabilities p̂_i over sites.
                        · Check:
                            - Σ_i p̂_i = 1 exactly (on the decoded grid),
                            - |p̂_i − p_weight_i| ≤ quantisation_epsilon for all sampled rows.
                        · Abort on any failure with ALIAS_DECODE_MISMATCH.
                    - Metrics & counters:
                        · Emit acceptance counters (merchant_count, blob_size_bytes,
                          min/max sites per merchant, alignment stats, etc.) into the S2 run-report stream (not a 2B dataset).
                    - Confirm no RNG, no extra inputs, no network I/O were used.
                    - On success, S2 completes; index+blob are now the authoritative alias plan for this (seed, fingerprint).

Downstream touchpoints
----------------------
- **2B.S3 (Day effects):**
    - Does NOT read alias tables directly; uses s1_site_weights as its base mass over sites.
- **2B.S4 (Group weights):**
    - Also uses s1_site_weights (aggregated by tz-group) and S3’s gammas; alias tables are not needed here.
- **2B.S5 / 5B router (runtime routing):**
    - MUST treat s2_alias_index + s2_alias_blob as the **sole directory + storage** for per-merchant alias tables.
    - MUST:
        · verify index.header.blob_sha256 vs the blob before decoding,
        · use the exact decode_law, layout_version, endianness, alignment_bytes from index/policy,
        · never infer offsets/lengths by scanning the blob.
- **2B.S6 (Virtual edges):**
    - Uses alias sampling results from S5 (site picks) but MUST NOT re-encode or mutate alias tables.
- **2B.S7 (Audit) & 2B.S8 (Validation bundle):**
    - Treat s2_alias_index + s2_alias_blob as key inputs for routing audit:
        · check mass conservation, coverage, decode spot-checks, alignment/non-overlap.
    - S8 will include both artefacts (and S7’s audit) in the fingerprint-scoped validation_bundle_2B,
      whose `_passed.flag_2B` will govern downstream “No PASS → No read” for all 2B routing plans.
```