```
        LAYER 3 · SEGMENT 6A — STATE S1 (CUSTOMER & PARTY BASE POPULATION)  [RNG-BEARING]

Authoritative inputs (read-only at S1 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_6A
      @ data/layer3/6A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_6A.json
      · provides, for this world:
          - manifest_fingerprint      (world id from Layers 1 & 2),
          - parameter_hash            (6A parameter pack),
          - run_id                    (6A run identity; S1 outputs MUST NOT depend on it),
          - sealed_inputs_digest_6A   (hash over sealed_inputs_6A),
          - upstream_gates{segment_id → {gate_status,bundle_root,sha256_hex}},
          - s0_spec_version, created_utc.
      · S1 MUST:
          - trust upstream gate_status for {1A,1B,2A,2B,3A,3B,5A,5B},
          - only run if all required segments have gate_status="PASS",
          - recompute sealed_inputs_digest_6A from sealed_inputs_6A and require equality.

    - sealed_inputs_6A
      @ data/layer3/6A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6A.parquet
      · one row per artefact that 6A is allowed to read in this world:
          {owner_layer, owner_segment, artifact_id, manifest_key,
           path_template, partition_keys[], schema_ref,
           sha256_hex, role, status, read_scope, source_dictionary, source_registry}.
      · S1 MUST:
          - only consume artefacts recorded here,
          - honour status (REQUIRED/OPTIONAL/IGNORED, REQUIRED_MISSING),
          - honour read_scope:
                · ROW_LEVEL      → may read rows,
                · METADATA_ONLY  → only presence/shape checks, no row-level logic.

[Schema+Dict · catalogue authority]
    - schemas.layer3.yaml, schemas.6A.yaml
        · shape authority for:
              - s1_party_base_6A              (6A.S1 primary output),
              - s1_party_summary_6A           (optional diagnostics).
    - dataset_dictionary.layer3.6A.yaml
        · IDs & contracts for:
              - s1_party_base_6A
                · path:
                    data/layer3/6A/s1_party_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/s1_party_base_6A.parquet
                · partitioning: [seed, fingerprint]
                · primary_key:  [party_id]
                · ordering:     [country_iso, segment_id, party_type, party_id]
                · schema_ref:   schemas.6A.yaml#/s1/party_base
              - s1_party_summary_6A (optional)
    - artefact_registry_6A.yaml
        · maps 6A priors/taxonomies/configs to logical IDs, roles and schema_refs.
    - dataset_dictionary.layer1.*.yaml, dataset_dictionary.layer2.*.yaml
        · accessible only where 6A.S1 is allowed to consume world context; S1 MUST NOT read upstream rows
          unless the artefact appears in sealed_inputs_6A with read_scope=ROW_LEVEL.

[6A priors & taxonomies S1 may read (must be in sealed_inputs_6A)]
    - Population priors:
        · world/region-level population priors (expected number of parties per region/type),
        · cell-level mixture priors (fraction of parties in each segment per region/type),
        · demographic distributions if used in the size of the population.
    - Segmentation taxonomies:
        · party_type taxonomy (retail, SME, corporate, organisation, etc.),
        · segment taxonomy (e.g. “mass_market”, “affluent”, “SME_micro”, …),
        · region taxonomy (e.g. country_iso → region_id).
    - Party attribute priors:
        · conditional priors for per-party attributes S1 owns, e.g.:
              - lifecycle_stage priors per (region, party_type, segment),
              - income_band priors per (region, segment, lifecycle_stage),
              - turnover_band, tenure_band, etc.
    - S1 configuration:
        · any S1-specific config/tuning (e.g. total population targets, optional region scaling).

[Optional upstream context]
    - world context surfaces S1 MAY use (if listed in sealed_inputs_6A with read_scope=ROW_LEVEL or METADATA_ONLY), e.g.:
        · region-level intensities or merchant densities (for “align population to merchant density”),
        · zone / country taxonomies from Layer-1.
    - S1 MUST NOT treat any upstream artefact as an “oracle of party existence”;
      upstream context only shapes priors, it does not list parties.

[Outputs owned by S1]
    - s1_party_base_6A  (required)
      @ data/layer3/6A/s1_party_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/s1_party_base_6A.parquet
      · partition_keys: [seed, fingerprint]
      · primary_key:    [party_id]    # with party_id unique within (seed, fingerprint)
      · ordering:       [country_iso, segment_id, party_type, party_id]
      · schema_ref:     schemas.6A.yaml#/s1/party_base
      · one row per party in `(manifest_fingerprint, seed)`, with at minimum:
            seed,
            manifest_fingerprint,
            party_id,
            party_type,
            segment_id,
            country_iso / region_id,
            static attributes S1 owns (lifecycle_stage, income_band, etc.),
            source_policy_ids/versions for priors used.

    - s1_party_summary_6A  (optional diagnostics)
      @ data/layer3/6A/s1_party_summary_6A/seed={seed}/fingerprint={manifest_fingerprint}/s1_party_summary_6A.parquet
      · partition_keys: [seed, fingerprint]
      · primary_key:    [country_iso, segment_id, party_type]
      · schema_ref:     schemas.6A.yaml#/s1/party_summary
      · aggregated counts per region/segment/type, derived from s1_party_base_6A.

[Numeric & RNG posture]
    - S1 is **deterministic given**:
        · sealed priors/taxonomies,
        · world identity (manifest_fingerprint),
        · parameter_hash,
        · seed.
    - RNG families:
        · `party_count_realisation`:
              - used once to convert continuous targets into integer `N_cell` per population cell,
              - event-level usage and stream layout defined by the Layer-3 RNG spec.
        · `party_attribute_sampling`:
              - used to sample per-party attribute assignments from conditional priors.
    - S1 MUST:
        · never use RNG outside these families,
        · obey Layer-3 RNG envelope (blocks/draws, counters, logging),
        · produce the same party base for the same (mf,parameter_hash,seed) triple.


----------------------------------------------------------------------
DAG — 6A.S1 (sealed priors → realised party / customer universe)  [RNG-BEARING]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S1.1) Verify S0 gate & fixed input universe  (RNG-free)
                    - Resolve:
                        · s0_gate_receipt_6A@fingerprint={manifest_fingerprint},
                        · sealed_inputs_6A@fingerprint={manifest_fingerprint},
                      via dataset_dictionary.layer3.6A.yaml.
                    - Validate both against schemas.6A.yaml.
                    - Recompute sealed_inputs_digest_6A from sealed_inputs_6A
                      (canonical row order + serialisation); require equality with the value
                      embedded in s0_gate_receipt_6A.
                    - Check `upstream_gates` in s0_gate_receipt_6A:
                        · all required segments {1A,1B,2A,2B,3A,3B,5A,5B} MUST have gate_status="PASS".
                    - If any condition fails:
                        · S1 MUST abort with a gate failure (`6A.S1.S0_GATE_FAILED`), writing no business outputs.

sealed_inputs_6A,
artefact_registry_6A,
dataset_dictionary.layer3.6A.yaml,
[Schema+Dict]
                ->  (S1.2) Resolve population priors, taxonomies, configs  (RNG-free)
                    - Filter sealed_inputs_6A rows to those with roles used by S1:
                          - "population_priors", "segment_priors", "party_attribute_priors",
                            "party_type_taxonomy", "segment_taxonomy", "region_taxonomy",
                            "s1_config", and any OPTIONAL context roles.
                    - For each such row:
                        · resolve `path_template` via the corresponding dictionary & partition_keys,
                        · recompute SHA-256(raw bytes), assert equality with `sha256_hex`,
                        · validate against its `schema_ref` (population priors, taxonomies, etc.).
                    - Materialise in memory:
                        · population priors: world-level + region/type/segment splits,
                        · taxonomies: definitions of region_id, party_type, segment_id, and any hierarchies,
                        · conditional priors for attributes under S1’s control,
                        · S1 configuration (e.g. global total population target, optional scaling knobs).

population & segmentation priors,
taxonomies,
(optional) world context
                ->  (S1.3) Define population cell domain C  (RNG-free)
                    - Define a **population cell** as:
                          c = (region_id, party_type, segment_id)
                      or another fixed design chosen by 6A (must be a binding choice).
                    - Using taxonomies + priors, construct the cell domain:
                        · for each region_id in region taxonomy,
                        · for each party_type allowed in that region,
                        · for each segment_id allowed for that (region, party_type),
                          add cell c if its prior mass > 0 (or if config says “force small cells”).
                    - Domain C = {c} MUST be:
                        · finite,
                        · deterministic given (manifest_fingerprint, parameter_hash) and priors.
                    - S1 MUST NOT:
                        · infer existing parties from upstream datasets,
                        · add/remove cells based on anything outside policy and priors.

population priors,
cell domain C,
(optional) world/context features
                ->  (S1.4) Compute continuous target counts N_cell_target(c)  (RNG-free)
                    - From S1 configuration and priors:
                        · determine **global total** target population N_total (for this world),
                        · compute per-region target totals N_region_target(r),
                        · compute per-cell fractional targets N_cell_target(c) for c∈C such that:
                              Σ_c N_cell_target(c) ≈ N_total,
                              Σ_{c in region r} N_cell_target(c) ≈ N_region_target(r).
                    - Typical pattern:
                        · N_total from global priors,
                        · N_region_target(r) = N_total × region_weight(r),
                        · N_cell_target(c)   = N_region_target(region(c)) × mixture_weight(c | region(c), party_type(c)).
                    - S1 MUST:
                        · ensure all N_cell_target(c) ≥ 0 and finite,
                        · record these values (in memory) as the continuous basis for integerisation.

N_cell_target(c),
N_region_target(r),
`party_count_realisation` RNG family,
RNG policy
                ->  (S1.5) Realise integer party counts N_cell(c)  (RNG-bearing)
                    - Introduce RNG using the `party_count_realisation` family.
                    - Depending on design, perform either:
                        · direct integerisation per cell, OR
                        · two-step region+cell integerisation.
                    - A typical two-step design:
                        1. Region integerisation (purely arithmetic or RNG, as policy dictates):
                               - for each region r, derive integer N_region(r) from N_region_target(r)
                                 (e.g. by rounding + residual, ensuring Σ_r N_region(r) ≈ N_total).
                        2. Within-region cell multinomial:
                               - for each region r separately:
                                     · compute cell shares π_cell|region(r,c) from N_cell_target(c),
                                     · draw integer counts {N_cell(c) for c in region r} such that
                                           Σ_{c in region r} N_cell(c) = N_region(r),
                                       using multinomial/binomial decomposition under `party_count_realisation`.
                    - Guardrails:
                        · S1 MUST ensure N_cell(c) ≥ 0 and finite,
                        · if any target cell N_cell_target(c) is effectively zero and config says “drop tiny cells”,
                          N_cell(c) MAY be zero (no parties in that cell).
                        - Any integerisation failure (negative counts, non-conservation, etc.) MUST abort S1
                          with a `6A.S1.COUNT_REALISATION_FAILED`-style error.

N_cell(c),
cell domain C
                ->  (S1.6) Define party index (mf, seed, c, i)  (RNG-free)
                    - For each (manifest_fingerprint, seed):
                        1. Fix a canonical ordering of cells C:
                               - sort by (region_id, party_type, segment_id).
                        2. Within each cell c, define:
                               - i = 0..N_cell(c)-1 as the local index of parties in that cell,
                                 in ascending order.
                    - This defines a **party index**: (mf, seed, c, i) for all c with N_cell(c)>0.
                    - S1 MUST NOT use RNG here; the index is purely deterministic based on counts.

party index (mf, seed, c, i)
                ->  (S1.7) Construct globally unique party_id per row  (RNG-free)
                    - For each (mf, seed, c, i):
                        · define party_id as a deterministic, collision-resistant function, e.g.:
                              party_id = LOW64( SHA256( mf || seed || cell_key(c) || uint64(i) ) )
                          where `cell_key(c)` encodes (region_id, party_type, segment_id).
                    - Requirements:
                        · party_id MUST be unique within (seed, manifest_fingerprint),
                        · the mapping (mf, seed, c, i) → party_id must be stable across re-runs.
                    - No RNG is used in ID construction.

N_cell(c),
party_id(mf,seed,c,i),
taxonomies (region, party_type, segment)
                ->  (S1.8) Build base party rows (type, segment, geography)  (RNG-free)
                    - For each (mf,seed,c,i):
                        · let c = (region_id, party_type, segment_id).
                        · create a base row:
                              seed                 = seed,
                              manifest_fingerprint = mf,
                              party_id             = party_id(mf,seed,c,i),
                              party_type           = party_type(c),
                              segment_id           = segment_id(c),
                              region_id            = region_id(c),
                              country_iso          = derived from region_id via taxonomy.
                    - At this stage, only type/segment/geo are filled; attributes are NULL/unset.
                    - All of this remains RNG-free.

party base rows (without attributes),
party attribute priors,
`party_attribute_sampling` RNG family
                ->  (S1.9) Sample static party attributes  (RNG-bearing)
                    - For each attribute A that S1 owns (e.g. lifecycle_stage, income_band, tenure_band):
                        · determine its conditional prior:
                              π_A | context, where context might include:
                                    region_id, party_type, segment_id, previously sampled attributes.
                        · Using `party_attribute_sampling` RNG:
                              - draw attribute values from π_A | context for each party,
                                or per cell then assign deterministically if policy allows.
                    - The sampling law and granularity (per-party vs per-cell events) are defined
                      in the 6A RNG/spec; S1 MUST:
                        · record RNG events per the Layer-3 RNG envelope,
                        · enforce that all sampled attributes are in allowed domains,
                        · abort if any impossible combination arises (e.g. unsupported attribute code).
                    - After this phase, each party row is fully populated with the static attributes S1 owns.

party rows (with attributes)
                ->  (S1.10) Assemble s1_party_base_6A & optional s1_party_summary_6A  (RNG-free)
                    - Collect all party rows for this (mf, seed) into a table.
                    - Validate against schemas.6A.yaml#/s1/party_base:
                        · required fields present,
                        · no duplicate party_id,
                        · partition keys [seed, fingerprint] well-formed.
                    - Sort rows according to dictionary’s ordering:
                        · [country_iso, segment_id, party_type, party_id].
                    - Write `s1_party_base_6A` to:
                        · data/layer3/6A/s1_party_base_6A/seed={seed}/fingerprint={mf}/s1_party_base_6A.parquet
                        · using write-once + idempotence:
                              - if partition empty → write via staging → fsync → atomic move.
                              - if exists → load and normalise; if byte-identical → OK; else → conflict, abort.
                    - If `s1_party_summary_6A` is enabled/registered:
                        · aggregate party_base rows per (country_iso, segment_id, party_type),
                        · validate against schemas.6A.yaml#/s1/party_summary,
                        · write to dictionary path with the same immutability rules.

Downstream touchpoints
----------------------
- **6A.S2 — Account & product base:**
    - MUST treat `s1_party_base_6A` as the sole authority on who exists as a party in this world+seed:
          - it MAY derive party-level features from S1 rows,
          - it MUST NOT add or remove parties on its own.

- **6A.S3 — Instruments & credentials:**
    - Uses party_type, segment_id and geography from S1 when deciding instrument distributions.
    - MUST NEVER alter or reinterpret S1’s party universe; only read it.

- **6A.S4 — Device/IP & graph:**
    - Uses parties as the “anchor” entities in the entity graph (devices & IPs connect to them).
    - MUST not create new parties; the graph must be built over S1’s party_base.

- **6A.S5 — Fraud posture & 6A HashGate:**
    - Assigns fraud roles **over** S1’s party IDs and S2–S4 entities.
    - When validating segment-level priors (role mixes per region/segment), it relies on S1’s counts and segmentation.

- **6B — Behavioural flows & transactions:**
    - MUST treat S1’s party_base as the only source of parties/customers in the world:
          - all 6B flows/transactions must attach to party_id from s1_party_base_6A (and related S2–S4 entities),
          - it MUST gate on 6A’s HashGate (S5 `_passed.flag`) before trusting any 6A entities/roles.
```