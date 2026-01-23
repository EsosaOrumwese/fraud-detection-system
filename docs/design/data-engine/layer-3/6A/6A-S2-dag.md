```
        LAYER 3 · SEGMENT 6A — STATE S2 (ACCOUNT & PRODUCT BASE)  [RNG-BEARING]

Authoritative inputs (read-only at S2 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_6A
      @ data/layer3/6A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_6A.json
      · provides for this world:
          - manifest_fingerprint        (world id from Layers 1 & 2),
          - parameter_hash              (6A parameter pack),
          - run_id                      (6A run identity; S2 outputs MUST NOT depend on it),
          - sealed_inputs_digest_6A     (hash over sealed_inputs_6A),
          - upstream_gates{segment_id → {gate_status,bundle_root,sha256_hex}},
          - s0_spec_version, created_utc.
      · S2 MUST:
          - trust upstream gate_status for {1A,1B,2A,2B,3A,3B,5A,5B},
          - only run if all required segments have gate_status="PASS",
          - recompute sealed_inputs_digest_6A from sealed_inputs_6A and require equality.

    - sealed_inputs_6A
      @ data/layer3/6A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6A.parquet
      · one row per artefact that 6A is allowed to read:
          {owner_layer, owner_segment, artifact_id, manifest_key,
           path_template, partition_keys[], schema_ref,
           sha256_hex, role, status, read_scope, source_dictionary, source_registry}.
      · S2 MUST:
          - only consume artefacts recorded here,
          - honour status (REQUIRED/OPTIONAL/IGNORED, REQUIRED_MISSING),
          - honour read_scope:
                · ROW_LEVEL      → may read rows,
                · METADATA_ONLY  → only presence/shape checks.

[Schema+Dict · catalogue authority]
    - schemas.layer3.yaml, schemas.6A.yaml
        · shape authority for:
              - s1_party_base_6A        (S1),
              - s2_account_base_6A      (S2 primary output),
              - s2_party_product_holdings_6A (S2 secondary output),
              - s2_account_summary_6A   (optional diagnostics).
    - dataset_dictionary.layer3.6A.yaml
        · IDs & contracts for:
              - s1_party_base_6A
                · path:
                    data/layer3/6A/s1_party_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/s1_party_base_6A.parquet
              - s2_account_base_6A
                · path:
                    data/layer3/6A/s2_account_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/s2_account_base_6A.parquet
                · partition_keys: [seed, fingerprint]
                · primary_key:    [account_id]
                · ordering:       [owner_party_id, account_type, account_id]
                · schema_ref:     schemas.6A.yaml#/s2/account_base
              - s2_party_product_holdings_6A
                · path:
                    data/layer3/6A/s2_party_product_holdings_6A/seed={seed}/fingerprint={manifest_fingerprint}/s2_party_product_holdings_6A.parquet
                · schema_ref:     schemas.6A.yaml#/s2/party_product_holdings
              - s2_account_summary_6A (optional)
    - artefact_registry_6A.yaml
        · maps 6A priors/taxonomies/configs to logical IDs, roles, schema_refs.

[Inputs from 6A.S1 · party universe]
    - s1_party_base_6A
      @ data/layer3/6A/s1_party_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/s1_party_base_6A.parquet
      · producer: 6A.S1.
      · partition_keys: [seed, fingerprint]
      · primary_key:    [party_id]
      · S2 MUST treat this as:
          - the **sole authority** on which parties exist,
          - the source of segmentation and geography for account planning:
                party_type, segment_id, region_id / country_iso, and static attributes.

[6A priors & taxonomies used by S2 (must be in sealed_inputs_6A)]
    - Account/product mix priors:
        · expected number of accounts per party (distribution over counts),
        · mix of account types per party segment & region (e.g. current vs savings vs credit vs loan),
        · product-family priors per account_type (e.g. “standard current”, “premium current”).
    - Account/product taxonomies:
        · canonical account_type codes,
        · product_family/product_id taxonomies,
        · currency/exposure taxonomies (e.g. allowed currencies per region/product).
    - Account eligibility & linkage rules:
        · which (party_type, segment, region) may hold which account_type/product_family,
        · min/max accounts per party per type/family,
        · any mandatory products (e.g. “every business party must have at least one operating account”).
    - S2 configuration:
        · any S2-specific tuning:
              - global caps (“max accounts per world”),
              - per-cell smoothing parameters.

[Optional upstream context (METADATA_ONLY unless explicitly ROW_LEVEL)]
    - world surfaces S2 MAY use to modulate account priors, e.g.:
        · merchant-world density per region,
        · income bands per region from external priors.
    - S2 MUST treat these as shaping priors only; they do not list accounts.

[Outputs owned by S2]
    - s2_account_base_6A   (required)
      @ data/layer3/6A/s2_account_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/s2_account_base_6A.parquet
      · one row per realised account, with at minimum:
            seed,
            manifest_fingerprint,
            account_id,
            owner_party_id        (or owner_merchant_id for merchant-side accounts),
            account_type,
            product_family_id,
            product_id?           (if enumerated),
            currency_iso,
            open_date_relative?   (if S2 owns relative opening date),
            static account attributes S2 owns (risk_tier, eligibility flags),
            source_policy_id/version for account & product priors.

    - s2_party_product_holdings_6A  (required)
      @ data/layer3/6A/s2_party_product_holdings_6A/seed={seed}/fingerprint={manifest_fingerprint}/…
      · one row per party×account_type/product_family with:
            counts / holdings summaries from s2_account_base_6A.

    - s2_account_summary_6A  (optional)
      · aggregated counts by region × segment × account_type / product_family.

[Numeric & RNG posture]
    - S2 is **RNG-bearing**:
        · RNG families:
              - `account_count_realisation`:
                    * used to convert continuous targets into integer numbers of accounts per cell×account_type.
              - `account_allocation_sampling`:
                    * used to assign accounts to specific parties within a cell.
              - `account_attribute_sampling`:
                    * used to sample attributes (currency, risk tier, etc.) per account.
        · S2 MUST:
              - use only approved RNG streams per family,
              - log events per the Layer-3 RNG envelope,
              - keep counts and attributes deterministic given seed+priors.
    - Determinism:
        · For fixed (manifest_fingerprint, parameter_hash, seed) and fixed priors/configs,
          S2 MUST produce the same account universe and holdings.


----------------------------------------------------------------------
DAG — 6A.S2 (party_base + priors → realised account & product universe)  [RNG-BEARING]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S2.1) Verify S0 gate & sealed_inputs_6A  (RNG-free)
                    - Resolve:
                        · s0_gate_receipt_6A@fingerprint={manifest_fingerprint},
                        · sealed_inputs_6A@fingerprint={manifest_fingerprint},
                      via dataset_dictionary.layer3.6A.yaml.
                    - Validate both against schemas.6A.yaml.
                    - Recompute sealed_inputs_digest_6A from sealed_inputs_6A
                      (canonical row order + serialisation); require equality with receipt.
                    - Check upstream_gates in receipt:
                        · required segments {1A,1B,2A,2B,3A,3B,5A,5B} MUST have gate_status="PASS".
                    - If any check fails:
                        · S2 MUST abort with `6A.S2.S0_GATE_FAILED`, writing no business outputs.

sealed_inputs_6A,
artefact_registry_6A,
dataset_dictionary.layer3.6A.yaml,
[Schema+Dict]
                ->  (S2.2) Resolve S1 party_base & S2 priors/taxonomies  (RNG-free)
                    - Filter sealed_inputs_6A to rows with roles required by S2:
                          "party_base", "account_mix_priors", "account_taxonomy",
                          "product_taxonomy", "account_eligibility_rules", "s2_config", plus any OPTIONAL context.
                    - Resolve:
                        · `s1_party_base_6A@seed={seed}/fingerprint={manifest_fingerprint}` via dictionary.
                        · account/product priors & taxonomies via artefact_registry_6A.
                    - For each resolved artefact:
                        · recompute SHA-256(raw bytes), assert equality with sha256_hex in sealed_inputs_6A,
                        · validate against its schema_ref (priors, taxonomies, configs).
                    - Load s1_party_base_6A into memory (or streaming), verifying:
                        · schema_ref = schemas.6A.yaml#/s1/party_base,
                        · partition keys [seed, fingerprint] match context.

s1_party_base_6A,
account/product priors,
eligibility rules,
region & segment taxonomies
                ->  (S2.3) Define account-planning cell domain C_acc  (RNG-free)
                    - Define an **account planning cell** as:
                          c_acc = (region_id, party_type, segment_id, maybe extra dimensions
                                   e.g. business_size_band, income_band)
                      as specified by the 6A design.
                    - From s1_party_base_6A:
                        · for each party, compute its cell key c_acc(party).
                        · count number of parties per cell:
                              P_cell(c_acc) = # of parties p with cell key c_acc.
                    - Using eligibility rules:
                        · filter cells to those eligible for at least one account_type/product_family.
                    - Domain:
                        · C_acc = { c_acc | P_cell(c_acc) > 0 or policy requires a cell even with 0 parties }.
                    - S2 MUST NOT:
                        · create account-planning cells that are not connected to at least one party or mandated by policy.

account/product priors,
eligibility rules,
C_acc,
P_cell(c_acc)
                ->  (S2.4) Compute continuous account targets per cell×account_type  (RNG-free)
                    - For each cell c ∈ C_acc:
                        · from priors, derive:
                              - expected number of accounts of each type T in this cell,
                              - e.g. E_acc(c,T) = P_cell(c) × E_accounts_per_party(c,T).
                        - For each (c,T):
                              N_acc_target(c,T) = E_acc(c,T),
                              subject to:
                                  - global/product-family caps if defined,
                                  - min requirements (e.g. at least 1 operating account for business types).
                    - Assemble in-memory table of continuous targets:
                        · columns: (cell c, account_type T, N_acc_target(c,T)).
                    - Guardrails:
                        · N_acc_target(c,T) ≥ 0 and finite for all c,T,
                        · any required cell×type for legal consistency (e.g. mandatory accounts) must have N_acc_target ≥ small ε or be handled explicitly.

N_acc_target(c,T),
`account_count_realisation` RNG family
                ->  (S2.5) Realise integer account counts N_acc(c,T)  (RNG-bearing)
                    - Introduce RNG under `account_count_realisation`.
                    - Choose an integerisation strategy consistent with priors and any caps:
                        · e.g. per cell multinomial across account types:
                              - for each cell c, with total expected accounts N_total(c) = Σ_T N_acc_target(c,T),
                              - derive type weights π_T(c) = N_acc_target(c,T) / N_total(c),
                              - draw {N_acc(c,T)} from Multinomial(N_total(c), π_T(c)).
                    - Alternative: treat each (c,T) independently with rounding + residual distribution.
                    - Invariants:
                        · N_acc(c,T) ≥ 0 for all c,T,
                        · per-cell totals and global totals must respect configuration rules
                          (e.g. total accounts per cell close to Σ_T N_acc_target(c,T)).
                        · any mandatory cell×type must have N_acc(c,T) ≥ 1, or S2 must abort with appropriate error.
                    - Any integerisation failure ⇒ `6A.S2.ACCOUNT_COUNT_REALISATION_FAILED`.

N_acc(c,T),
P_cell(c),
s1_party_base_6A,
eligibility rules,
`account_allocation_sampling` RNG family
                ->  (S2.6) Allocate accounts to specific parties  (RNG-bearing)
                    - For each cell c ∈ C_acc:
                        · let P_cell(c) parties and account-type counts {N_acc(c,T)}.
                        · For each account_type T where N_acc(c,T) > 0:
                              - define eligible party set:
                                    ELIGIBLE(c,T) = {p in cell c | eligibility rules allow p to hold T}.
                              - If ELIGIBLE(c,T) is empty and N_acc(c,T)>0:
                                    → configuration error; S2 MUST fail.
                              - Use `account_allocation_sampling` RNG family to assign N_acc(c,T) accounts to ELIGIBLE(c,T):
                                    * e.g. by drawing counts per party from a multinomial,
                                      or by sampling party indices with replacement, obeying per-party max constraints.
                    - For each allocated account slot, materialise a tuple (party_id, account_type T, cell c).
                    - Invariants:
                        · no party exceeds its max allowed accounts for type T if rules define caps,
                        · all N_acc(c,T) accounts are allocated to some party in ELIGIBLE(c,T).

allocated account slots (party_id, c,T, local index j),
taxonomies,
s2_config,
`account_attribute_sampling` RNG family
                ->  (S2.7) Construct account_id and sample account attributes  (RNG-bearing)
                    - For each allocated slot (party_id p, cell c, account_type T, local index j):
                        1. Construct account_id deterministically:
                               account_id = LOW64( SHA256( mf || seed || "acct" || party_id || T || uint64(j) ) ).
                        2. Determine product_family and (optionally) product_id:
                               - via product taxonomy and priors conditioned on (c,T),
                               - use `account_attribute_sampling` RNG where needed.
                        3. Determine currency_iso:
                               - from currency priors per (region, account_type or product_family).
                        4. Sample account attributes S2 owns:
                               - e.g. risk_tier, open_date_relative, flags (e.g. overdraft_allowed),
                               - using `account_attribute_sampling` RNG.
                    - Guardrails:
                        · account_id must be unique within (seed,manifest_fingerprint),
                        · all sampled attributes must be in allowed domains,
                        · any impossible combination MUST trigger an error rather than silent coercion.

account rows (account_id, owner_party_id, account_type, product_family_id, currency_iso, attrs)
                ->  (S2.8) Assemble s2_account_base_6A  (RNG-free)
                    - Collect all realised account rows for this (seed, mf).
                    - Validate against schemas.6A.yaml#/s2/account_base:
                        · seed & manifest_fingerprint columns correct,
                        · primary key uniqueness on account_id,
                        · owner_party_id references existing party_id in s1_party_base_6A,
                        · account_type, product_family_id, currency_iso, attrs all valid per taxonomies.
                    - Order rows as per dictionary (e.g. [owner_party_id, account_type, account_id]).
                    - Write to:
                        · data/layer3/6A/s2_account_base_6A/seed={seed}/fingerprint={mf}/s2_account_base_6A.parquet
                      with write-once+idempotent semantics:
                        · if partition missing → staging → fsync → atomic move,
                        · if exists → load & normalise; if identical → OK; else → conflict, abort.

s2_account_base_6A,
s1_party_base_6A
                ->  (S2.9) Build s2_party_product_holdings_6A  (RNG-free)
                    - Derive per-party holdings directly from s2_account_base_6A:
                        · group by (owner_party_id, account_type, product_family_id [, currency_iso if needed]),
                        · compute counts and any summary measures defined by schema
                          (e.g. number_of_accounts, has_credit_card_flag).
                    - Join in party metadata (country_iso, segment_id, party_type) where required by schema.
                    - Validate table against schemas.6A.yaml#/s2/party_product_holdings.
                    - Write to:
                        · data/layer3/6A/s2_party_product_holdings_6A/seed={seed}/fingerprint={mf}/s2_party_product_holdings_6A.parquet
                      with same immutability/idempotence rules.

s2_account_base_6A (optional aggregation)
                ->  (S2.10) Optionally build s2_account_summary_6A  (RNG-free)
                    - If account summary is registered/enabled:
                        · aggregate s2_account_base_6A by region, segment, account_type, product_family or as specified:
                              * counts, optional share metrics, etc.
                        · validate against schemas.6A.yaml#/s2/account_summary.
                        · write to dictionary path with standard immutability/idempotence.
                    - If not enabled, S2 MUST NOT emit this dataset.

Downstream touchpoints
----------------------
- **6A.S3 — Instruments & credentials:**
    - MUST treat s2_account_base_6A as the sole authority on accounts:
          - one account row per `account_id`, with owner_party_id, account_type, product_family_id, currency_iso.
    - MUST NOT invent new accounts; instrument allocation must reference existing account_ids.

- **6A.S4 — Device/IP & graph:**
    - May look at account mix per party (e.g. business vs retail footprint), but MUST NOT alter accounts.

- **6A.S5 — Fraud posture & 6A HashGate:**
    - When assigning fraud roles to accounts or reasoning about product mixes,
      MUST derive those from s2_account_base_6A / s2_party_product_holdings_6A only.

- **6B — Flows/transactions:**
    - Later uses account_ids and account metadata as part of transaction context,
      but MUST gate on the 6A HashGate before trusting accounts/products.

```