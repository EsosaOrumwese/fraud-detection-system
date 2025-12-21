```
        LAYER 3 · SEGMENT 6A — STATE S3 (INSTRUMENT & CREDENTIAL BASE)  [RNG-BEARING]

Authoritative inputs (read-only at S3 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_6A
      @ data/layer3/6A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_6A.json
      · provides, for this world:
          - manifest_fingerprint        (world id from Layers 1 & 2),
          - parameter_hash              (6A parameter pack),
          - run_id                      (6A run id; S3 outputs MUST NOT depend on it),
          - sealed_inputs_digest_6A     (hash over sealed_inputs_6A),
          - upstream_gates{segment_id → {gate_status,bundle_root,sha256_hex}},
          - s0_spec_version, created_utc.
      · S3 MUST:
          - trust upstream gate_status for {1A,1B,2A,2B,3A,3B,5A,5B},
          - only run if all required segments have gate_status="PASS",
          - recompute sealed_inputs_digest_6A from sealed_inputs_6A and require equality.

    - sealed_inputs_6A
      @ data/layer3/6A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6A.parquet
      · one row per artefact 6A is allowed to read:
          {owner_layer, owner_segment, artifact_id, manifest_key,
           path_template, partition_keys[], schema_ref,
           sha256_hex, role, status, read_scope, source_dictionary, source_registry}.
      · S3 MUST:
          - only consume artefacts recorded here,
          - honour status (REQUIRED/OPTIONAL/IGNORED, REQUIRED_MISSING),
          - honour read_scope:
                · ROW_LEVEL      → may read rows,
                · METADATA_ONLY  → metadata only.

[Schema+Dict · catalogue authority]
    - schemas.layer3.yaml, schemas.6A.yaml
        · shape authority for:
              - s2_account_base_6A,
              - s3_instrument_base_6A,
              - s3_account_instrument_links_6A,
              - s3_party_instrument_holdings_6A,
              - s3_instrument_summary_6A.
    - dataset_dictionary.layer3.6A.yaml
        · IDs & contracts:
              - s2_account_base_6A
                · path:
                    data/layer3/6A/s2_account_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/s2_account_base_6A.parquet
                · partition_keys: [seed, fingerprint]
                · primary_key:    [account_id]
              - s3_instrument_base_6A
                · path:
                    data/layer3/6A/s3_instrument_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/s3_instrument_base_6A.parquet
                · partition_keys: [seed, fingerprint]
                · primary_key:    [instrument_id]
                · ordering:       [owner_account_id, instrument_type, instrument_id]
                · schema_ref:     schemas.6A.yaml#/s3/instrument_base
              - s3_account_instrument_links_6A
                · path:
                    data/layer3/6A/s3_account_instrument_links_6A/seed={seed}/fingerprint={manifest_fingerprint}/s3_account_instrument_links_6A.parquet
                · schema_ref:     schemas.6A.yaml#/s3/account_instrument_links
              - s3_party_instrument_holdings_6A (optional)
              - s3_instrument_summary_6A        (optional)
    - artefact_registry_6A.yaml
        · maps 6A priors/taxonomies/configs to logical IDs, roles, schema_refs.

[Inputs from 6A.S2 · account universe]
    - s2_account_base_6A
      @ data/layer3/6A/s2_account_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/s2_account_base_6A.parquet
      · producer: 6A.S2.
      · partition_keys: [seed, fingerprint]
      · primary_key:    [account_id]
      · S3 MUST treat this as:
          - the **sole authority** on accounts,
          - the source of account_type, product_family_id, currency_iso, owner_party_id
            and any static account attributes needed for instrument planning.

[6A priors & taxonomies used by S3 (must be in sealed_inputs_6A)]
    - Instrument mix priors:
        · expected number of instruments per account (distribution over counts) by:
              account_type, product_family, segment, region, etc.
        · mix over instrument_type (e.g. `CARD`, `HANDLE`, `WALLET`, `TOKEN`) per account class.
        · optional scheme/network mix priors per instrument_type & region.
    - Instrument taxonomies:
        · instrument_type taxonomy (card vs handle vs wallet vs other),
        · scheme/network/brand taxonomies,
        · token_type taxonomies (if modelling tokenised credentials).
    - Instrument eligibility & linkage rules:
        · which account types can carry which instrument types/schemes,
        · min/max instruments per account per type,
        · any mandatory instruments (e.g. “each primary current account must have at least one card”).
    - Instrument attribute priors:
        · expiry profiles (months/years to expiry) per scheme/network/type,
        · limits and flags (e.g. contactless_enabled, 3DS_enforced),
        · masked identifier formats, BIN/brand mixes (if owned here).
    - S3 configuration:
        · knobs for smoothing, global caps (“max cards per world”), or per-cell guardrails.

[Optional upstream/context surfaces]
    - world/usage signals S3 MAY use to modulate priors (METADATA_ONLY unless explicitly ROW_LEVEL), e.g.:
        · card mix by product in source market priors,
        · merchant density or active-device priors.

[Outputs owned by S3]
    - s3_instrument_base_6A   (required)
      @ data/layer3/6A/s3_instrument_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/s3_instrument_base_6A.parquet
      · one row per instrument/credential, with at minimum:
            seed,
            manifest_fingerprint,
            instrument_id,
            instrument_type        (card/handle/wallet/token/…),
            owner_account_id,
            owner_party_id?       (optional denormalised),
            scheme/network_id?    (for cards),
            token_type_id?        (for tokens),
            masked_identifier?    (if defined at S3),
            expiry_profile?       (e.g. months_to_expiry),
            static attributes S3 owns (limits, flags, brand tiers),
            source_policy_id/version for priors used.

    - s3_account_instrument_links_6A   (required)
      @ data/layer3/6A/s3_account_instrument_links_6A/seed={seed}/fingerprint={manifest_fingerprint}/…
      · one row per (account_id, instrument_id) link,
        with link_role (e.g. PRIMARY, SECONDARY, TOKEN_OF, BACKUP).

    - s3_party_instrument_holdings_6A  (optional)
      @ data/layer3/6A/s3_party_instrument_holdings_6A/seed={seed}/fingerprint={manifest_fingerprint}/…
      · aggregated holdings per party×instrument_type/scheme.

    - s3_instrument_summary_6A         (optional)
      · aggregated counts by region×segment×account_type×instrument_type/scheme.

[Numeric & RNG posture]
    - S3 is **RNG-bearing**:
        · RNG families:
              - `instrument_count_realisation`:
                    * integerise continuous targets → N_instr per (cell, account_type, instrument_type).
              - `instrument_allocation_sampling`:
                    * assign instruments to specific accounts, obeying eligibility and per-account caps.
              - `instrument_attribute_sampling`:
                    * sample per-instrument attributes (scheme, brand, expiry, flags).
        · S3 MUST:
              - use only approved RNG streams/substreams per family,
              - log events according to Layer-3 RNG envelope (blocks/draws, counters),
              - be deterministic given (mf, parameter_hash, seed) and sealed priors.
    - Partitioning:
        · all S3 outputs are partitioned by [seed, fingerprint],
          with `instrument_id` unique within (seed, fingerprint).


----------------------------------------------------------------------
DAG — 6A.S3 (account_base + priors → realised instruments & account↔instrument links)  [RNG-BEARING]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S3.1) Verify S0 gate & sealed_inputs_6A  (RNG-free)
                    - Resolve:
                        · s0_gate_receipt_6A@fingerprint={manifest_fingerprint},
                        · sealed_inputs_6A@fingerprint={manifest_fingerprint},
                      via dataset_dictionary.layer3.6A.yaml.
                    - Validate both against schemas.6A.yaml.
                    - Recompute sealed_inputs_digest_6A from sealed_inputs_6A;
                      require equality with receipt.sealed_inputs_digest_6A.
                    - Check upstream_gates:
                        · all required segments {1A,1B,2A,2B,3A,3B,5A,5B} must have gate_status="PASS".
                    - If any check fails:
                        · S3 MUST abort; no instrument/links outputs may be written.

sealed_inputs_6A,
artefact_registry_6A,
dataset_dictionary.layer3.6A.yaml,
[Schema+Dict]
                ->  (S3.2) Resolve S2 account_base & S3 priors/taxonomies  (RNG-free)
                    - Filter sealed_inputs_6A rows to those with roles needed by S3:
                          "account_base", "instrument_mix_priors", "instrument_taxonomy",
                          "instrument_eligibility_rules", "instrument_attribute_priors", "s3_config", plus any OPTIONAL context.
                    - Resolve:
                        · s2_account_base_6A@seed={seed}/fingerprint={manifest_fingerprint},
                        · instrument priors & taxonomies via artefact_registry_6A.
                    - For each resolved external artefact:
                        · recompute SHA-256(raw bytes), assert equality with sha256_hex,
                        · validate against its schema_ref.
                    - Load s2_account_base_6A (or stream), verifying:
                        · schema_ref = schemas.6A.yaml#/s2/account_base,
                        · partition keys [seed, fingerprint] are correct.

s2_account_base_6A,
instrument mix priors,
eligibility rules,
taxonomies
                ->  (S3.3) Define instrument-planning cell domain C_instr  (RNG-free)
                    - Define an **instrument planning cell** as:
                          c_instr = (account_type, product_family_id, region_id, segment_id, maybe extra dims)
                      as specified in S3 design.
                    - For each account row:
                        · derive its cell key c_instr(account):
                              - via account_type, product_family, and party-based features (from joining owner_party_id to S1 if needed).
                    - Count accounts per cell:
                        · A_cell(c_instr) = # accounts mapped to c_instr.
                    - Use eligibility rules to restrict instrument cell domain:
                        · Only keep (c_instr, instrument_type) pairs that are allowed by rules.
                    - Define domain:
                        · C_instr = set of (c_instr, instrument_type) used for planning,
                          where either:
                              - A_cell(c_instr) > 0, or
                              - S3 config says “force cell even with 0 accounts” (rare).
                    - S3 MUST NOT:
                        · treat any upstream artefact as direct list of instruments,
                        · create instrument cells that have no eligible accounts and are not explicitly mandated.

instrument mix priors,
A_cell(c_instr),
eligibility rules
                ->  (S3.4) Compute continuous instrument targets N_instr_target(c_instr, I)  (RNG-free)
                    - For each cell c ∈ C_instr and instrument_type I allowed in that cell:
                        · from priors, derive expected instruments per account for (c,I):
                              μ_instr(c,I) = E[ # instruments of type I per account in cell c ].
                        · Continuous target count:
                              N_instr_target(c,I) = A_cell(c) × μ_instr(c,I).
                    - Apply any global/device-family caps or floors specified in S3 config:
                        · e.g. max cards per world, minimum number of handles per product_family.
                    - Assemble in-memory list:
                        · (c_instr, instrument_type I, N_instr_target(c,I)).
                    - Guardrails:
                        · N_instr_target(c,I) ≥ 0 and finite,
                        · required (c,I) mandated by policy must have N_instr_target(c,I) ≥ ε or be handled explicitly.

N_instr_target(c,I),
`instrument_count_realisation` RNG family
                ->  (S3.5) Realise integer instrument counts N_instr(c,I)  (RNG-bearing)
                    - Introduce RNG under `instrument_count_realisation`.
                    - For each cell c:
                        · Option 1: per-cell multinomial over instrument types:
                              - N_total_instr(c) = Σ_I N_instr_target(c,I),
                              - π_I(c) = N_instr_target(c,I) / N_total_instr(c),
                              - draw {N_instr(c,I)} ~ Multinomial(N_total_instr(c), π_I(c)).
                        · Option 2: per-(c,I) rounding + residual allocation (documented in S3 spec).
                    - Invariants:
                        · N_instr(c,I) ≥ 0 for all c,I,
                        · per-cell totals align with N_total_instr(c) within acceptable error thresholds,
                        · any mandatory cell×type must have N_instr(c,I) ≥ 1, or S3 MUST fail gracefully.
                    - Any numerical or feasibility failure ⇒ `6A.S3.INSTRUMENT_COUNT_REALISATION_FAILED`.

s2_account_base_6A,
N_instr(c,I),
eligibility rules,
`instrument_allocation_sampling` RNG family
                ->  (S3.6) Allocate instruments to accounts  (RNG-bearing)
                    - For each cell c ∈ C_instr:
                        · get account list:
                              ACCOUNTS(c) = [account_id_1, ..., account_id_{A_cell(c)}].
                        - For each instrument_type I with N_instr(c,I) > 0:
                              1. Determine eligible accounts:
                                     ELIGIBLE(c,I) = {a ∈ ACCOUNTS(c) | eligibility rules allow a to carry I}.
                                     If ELIGIBLE(c,I) is empty and N_instr(c,I) > 0:
                                          → configuration error, abort.
                              2. Use `instrument_allocation_sampling` RNG family to:
                                     - assign N_instr(c,I) instrument slots to accounts in ELIGIBLE(c,I),
                                       obeying per-account caps and any special rules (e.g. primary vs secondary).
                                     - typical pattern:
                                           · sample per-account counts from a multinomial,
                                           · enforce max_instruments_per_account via rejection or redistribution.
                    - Produce a set of **instrument slots**:
                        · SLOT = (owner_account_id, cell c, instrument_type I, local_index j).
                    - S3 MUST ensure:
                        · sum of slots across accounts in cell c for type I equals N_instr(c,I),
                        · no account violates max instruments per type/product if rules specify such caps.

instrument slots (owner_account_id, c,I,j),
taxonomies,
instrument_attribute_priors,
`instrument_attribute_sampling` RNG family
                ->  (S3.7) Construct instrument_id and sample instrument attributes  (RNG-bearing)
                    - For each slot (owner_account_id a, cell c, instrument_type I, local index j):
                        1. Construct instrument_id deterministically:
                               instrument_id = LOW64(
                                   SHA256( mf || seed || "instr" || account_id || I || uint64(j) )
                               ).
                        2. Determine scheme/network/brand (if applicable):
                               - from priors conditioned on (c,I) and possibly account/product attributes,
                               - use `instrument_attribute_sampling` RNG as needed.
                        3. Determine token_type (for tokenised credentials, if modelled).
                        4. Determine expiry profile (e.g. months_to_expiry, expiry_month/year) from expiry priors.
                        5. Determine static flags/limits:
                               - e.g. credit_limit_band, contactless_enabled, 3DS_mandatory, card_present_only, etc.
                        6. Optionally derive masked_identifier:
                               - if S3 owns the masked form (e.g. last 4 digits, brand BIN), sample or derive consistently
                                 using `instrument_attribute_sampling` + taxonomies.
                    - Guardrails:
                        · instrument_id MUST be unique in (seed, mf),
                        · all attributes MUST be valid per taxonomies,
                        · any impossible combination MUST result in an error, not silent coercion.

instrument rows (instrument_id, owner_account_id, attrs)
                ->  (S3.8) Assemble s3_instrument_base_6A  (RNG-free)
                    - Collect all realised instruments for this (seed, mf) into a table.
                    - Validate against schemas.6A.yaml#/s3/instrument_base:
                        · required fields present,
                        · instrument_id unique,
                        · owner_account_id exists in s2_account_base_6A and has allowed account_type,
                        · instrument_type, scheme/network, token_type, expiry, flags are valid per taxonomies.
                    - Order rows as per dictionary: e.g. [owner_account_id, instrument_type, instrument_id].
                    - Write to:
                        · data/layer3/6A/s3_instrument_base_6A/seed={seed}/fingerprint={mf}/s3_instrument_base_6A.parquet
                      using write-once+idempotence:
                        · if partition missing → staging → fsync → atomic move,
                        · if exists → load+normalise; if identical → OK; else → conflict, abort.

s3_instrument_base_6A,
s2_account_base_6A
                ->  (S3.9) Build s3_account_instrument_links_6A  (RNG-free)
                    - For each instrument row:
                        · create a link row:
                              account_id    = owner_account_id,
                              instrument_id = instrument_id,
                              link_role     = "PRIMARY" (or other role if policy assigns e.g. “SECONDARY”, “TOKEN_OF”…).
                    - If design uses more complex roles (e.g. multiple instruments referencing same base credential),
                      S3 uses instrument layout rules (non-RNG at this stage — purely structural).
                    - Validate against schemas.6A.yaml#/s3/account_instrument_links:
                        · each instrument has at least one link,
                        · link_role codes valid,
                        · no orphan instrument or orphan account references.
                    - Write to:
                        · data/layer3/6A/s3_account_instrument_links_6A/seed={seed}/fingerprint={mf}/s3_account_instrument_links_6A.parquet
                      with standard immutability/idempotence rules.

s3_instrument_base_6A,
s2_account_base_6A,
s1_party_base_6A (if needed for aggregation)
                ->  (S3.10) Build optional s3_party_instrument_holdings_6A & s3_instrument_summary_6A  (RNG-free)
                    - If `s3_party_instrument_holdings_6A` is enabled:
                        · join s3_instrument_base_6A → s2_account_base_6A → s1_party_base_6A
                          to derive per-party holdings:
                              - counts per instrument_type and/or scheme/network,
                              - booleans like has_card, has_tokenised_card, etc.
                        - validate against schemas.6A.yaml#/s3/party_instrument_holdings,
                        - write to dictionary path with immutability rules.
                    - If `s3_instrument_summary_6A` is enabled:
                        · aggregate instruments by region, segment, account_type, instrument_type, scheme/network:
                              - counts, shares, etc.
                        - validate against schemas.6A.yaml#/s3/instrument_summary,
                        - write to dictionary path with immutability rules.
                    - If these diagnostics are not enabled, S3 MUST NOT emit them.

Downstream touchpoints
----------------------
- **6A.S4 — Device/IP & graph:**
    - MUST treat s3_instrument_base_6A and s3_account_instrument_links_6A as:
          - the only sources of instrument/credential entities and their attachment to accounts.
    - When building device/IP links, S4 may connect devices/IPs to instruments (e.g. “card used on device” patterns),
      but MUST NOT create new instruments or alter existing ones.

- **6A.S5 — Fraud posture & 6A HashGate:**
    - Assigns fraud roles over instruments and uses s3_instrument_base_6A + holdings/summary to:
          - check target role mixes per segment/region/type,
          - ensure no entity is omitted.
    - 6A HashGate bundle will include S3 artefacts as part of the evidence.

- **6B — Behaviour & transaction flows:**
    - Uses s3_instrument_base_6A as the universe of credentials (cards, handles, wallets) that can appear in flows.
    - Uses s3_account_instrument_links_6A to map flows to accounts/parties.
    - MUST gate on the 6A segment-level `_passed.flag_6A` before treating these instruments as trustworthy.
```