```
                  LAYER 3 · SEGMENT 6A — STATIC BANK WORLD & FRAUD POSTURE

Authoritative upstream & inputs (sealed by 6A.S0)
-------------------------------------------------
[World identity]
    - manifest_fingerprint      (which Layer-1/Layer-2 world we’re on)
    - parameter_hash            (which 6A parameter/prior pack)
    - seed                      (used from S1–S4; S5 is usually seed-scoped for roles)

[Upstream segments that MUST be PASS for this manifest_fingerprint]
    - Layer 1:
        · 1A — merchant universe & hurdles
        · 1B — site/location universe
        · 2A — time-zones & civil-time surfaces
        · 2B — routing plans (sites/edges)
        · 3A — zone allocations
        · 3B — virtual merchant & edge world
    - Layer 2:
        · 5A — arrival intensity planner
        · 5B — arrival realisation (events)

[6A priors, taxonomies & configs]
    - Population & segmentation priors:
        · expected party populations per region/type/segment,
        · segment taxonomies, party-type taxonomies, region/country taxonomies,
        · attribute priors (income band, lifecycle stage, etc.).
    - Account & product priors:
        · accounts-per-party distributions,
        · product/account-type mix per segment/region,
        · account/product taxonomies, eligibility/linkage rules.
    - Instrument priors:
        · instruments-per-account distributions,
        · instrument_type/scheme/network taxonomies,
        · expiry and attribute priors.
    - Device/IP priors:
        · device_type/OS/UA priors,
        · ip_type/asn_class priors,
        · graph-shape priors (degrees, sharing patterns).
    - Fraud-role priors & taxonomies:
        · role enums per entity type (party/account/merchant/device/IP),
        · role-mix priors per cell.
    - Validation policy & config:
        · which checks to run at S5,
        · thresholds & severities.


DAG
---
(World & priors) --> (S0) GATE & SEALED INPUTS   [NO RNG]
    - Verifies upstream HashGates for segments 1A–3B & 5A–5B for this manifest_fingerprint.
    - Discovers all 6A-relevant artefacts via dictionaries & registries:
        · population/account/instrument/device/IP priors,
        · fraud-role priors & taxonomies,
        · any world context surfaces 6A is allowed to read.
    - Computes SHA-256 digests over each artefact and writes:
        · sealed_inputs_6A@fingerprint:
              one row per artefact with its role, path_template, schema_ref, sha256_hex, status, read_scope.
        · s0_gate_receipt_6A@fingerprint:
              manifest_fingerprint, parameter_hash, run_id,
              upstream_gates status map,
              sealed_inputs_digest_6A.
    - S0 is RNG-free and row-free; it defines **what** 6A may read and **which world** it belongs to.

                                      |
                                      | s0_gate_receipt_6A, sealed_inputs_6A
                                      v

(S1) PARTY / CUSTOMER BASE POPULATION         [RNG-BEARING]
    inputs:
        - s0_gate_receipt_6A, sealed_inputs_6A,
        - population & segmentation priors,
        - party-type & segment taxonomies,
        - any optional world context for shaping priors.
    -> s1_party_base_6A@seed,fingerprint
         - Defines the **party universe** for this (manifest_fingerprint, seed):
              - defines population cells (region, party_type, segment),
              - computes continuous population targets per cell from priors,
              - uses RNG to integerise those into counts per cell,
              - gives each party a unique party_id via deterministic hashing,
              - samples static attributes (income band, lifecycle stage, etc.) from conditional priors.
         - Outputs one row per party with:
              party_id, party_type, segment_id, country/region, attributes.

    - S1 is where “who exists as a customer/party” is realised.

                                      |
                                      | s1_party_base_6A
                                      v

(S2) ACCOUNT & PRODUCT BASE                  [RNG-BEARING]
    inputs:
        - s1_party_base_6A,
        - account/product mix priors,
        - account & product taxonomies,
        - account eligibility & linkage rules.
    -> s2_account_base_6A@seed,fingerprint
         - Defines the **account universe**:
              - defines account-planning cells (region, party_type, segment, etc.),
              - computes continuous account targets per cell×account_type from priors,
              - integerises to get how many accounts of each type per cell,
              - allocates accounts to specific parties (with RNG), respecting eligibility & caps,
              - samples static account attributes (currency, risk tier, flags).
         - Each row is an account_id with owner_party_id (and/or owner_merchant_id), account_type, product_family, currency, attrs.

    -> s2_party_product_holdings_6A@seed,fingerprint
         - Per-party counts of holdings by account_type/product_family.

    - S2 is where “what accounts/products exist and who owns them” is realised.

                                      |
                                      | s2_account_base_6A, s1_party_base_6A
                                      v

(S3) INSTRUMENT & CREDENTIAL BASE            [RNG-BEARING]
    inputs:
        - s2_account_base_6A,
        - instrument mix priors,
        - instrument taxonomies (card/handle/wallet/token, scheme/network, brand),
        - instrument eligibility & attribute priors.
    -> s3_instrument_base_6A@seed,fingerprint
         - Defines the **instrument / credential universe**:
              - defines instrument-planning cells (account/profile & context),
              - computes continuous instrument targets per cell×instrument_type from priors,
              - integerises to get counts per cell×instrument_type,
              - allocates instruments to accounts (RNG), obeying caps,
              - samples instrument attributes (scheme, brand, expiry, limits, masked identifiers).
         - Each row is an instrument_id owning account_id and attributes.

    -> s3_account_instrument_links_6A@seed,fingerprint
         - Links instruments to accounts (and implicitly to parties via accounts).

    -> optional s3_party_instrument_holdings_6A, s3_instrument_summary_6A.

    - S3 is where “which cards/handles/wallets exist and which accounts they belong to” is realised.

                                      |
                                      | s1_party_base_6A, s2_account_base_6A,
                                      | s3_instrument_base_6A, s3_account_instrument_links_6A
                                      v

(S4) DEVICES, IPs & NETWORK GRAPH            [RNG-BEARING]
    inputs:
        - s1_party_base_6A,
        - s2_account_base_6A,
        - s3_instrument_base_6A & account_instrument_links,
        - device priors & taxonomies,
        - IP priors & taxonomies,
        - graph/linkage rules (who devices/IPs can attach to and how they share),
        - S4 config (caps, degree limits).
    -> s4_device_base_6A@seed,fingerprint
         - Defines the **device universe**:
              - device-planning cells (region, party segment, device_type),
              - continuous device targets per cell×type → integer device counts with RNG,
              - allocate devices to parties/accounts/merchants (anchors) with optional sharing.

    -> s4_device_links_6A@seed,fingerprint
         - Graph edges: device_id → party/account/instrument/merchant with roles (PRIMARY_OWNER, USED_BY, etc.).

    -> s4_ip_base_6A@seed,fingerprint
         - Defines the **IP / endpoint universe**:
              - IP-planning cells (region, ip_type, asn_class),
              - continuous IP targets → integer IP counts,
              - sample IP attributes (asn_class, ip_type, risk flags).

    -> s4_ip_links_6A@seed,fingerprint
         - Graph edges: ip_id → device/party/merchant with roles (SEEN_FROM, HOME_IP_FOR, etc.).

    - S4 is where “which devices & IPs exist, and how everything connects into a graph” is realised.

                                      |
                                      | s1_party_base_6A, s2_account_base_6A,
                                      | s3_instrument_base_6A, s3_account_instrument_links_6A,
                                      | s4_device_base_6A, s4_ip_base_6A,
                                      | s4_device_links_6A, s4_ip_links_6A,
                                      | fraud-role priors & taxonomies, validation policy
                                      v

(S5) STATIC FRAUD POSTURE & 6A HASHGATE       [RNG-BEARING + VALIDATION]
    inputs:
        - all 6A bases & link tables (S1–S4),
        - fraud-role priors & taxonomies per entity type (party/account/merchant/device/IP),
        - S5 validation policy (which checks to run).
    -> s5_party_fraud_roles_6A@seed,fingerprint
         - Assigns each party a static fraud role (e.g. clean, mule, synthetic, etc.), matching per-cell priors.

    -> s5_account_fraud_roles_6A@seed,fingerprint
         - Assigns each account a fraud role (e.g. clean, mule_account, high_risk_account).

    -> s5_merchant_fraud_roles_6A@seed,fingerprint
         - Assigns each merchant a fraud role (e.g. clean, risky_merchant).

    -> s5_device_fraud_roles_6A@seed,fingerprint
         - Assigns each device a fraud role (e.g. normal_device, mule_device, risky_device).

    -> s5_ip_fraud_roles_6A@seed,fingerprint
         - Assigns each IP a fraud role (e.g. residential_clean, hosting_risky, mule_ip).

    -> s5_validation_report_6A@fingerprint
         - Runs checks:
              - coverage (everyone has a role),
              - role mixes vs priors (per cell, global),
              - structural constraints (e.g. incompatible role combos),
              - graph-based invariants.
         - Produces an overall PASS/FAIL with metrics and per-check status.

    -> s5_issue_table_6A@fingerprint (optional)
         - Row-level issues.

    -> validation_bundle_index_6A@fingerprint/index.json
         - Lists all 6A validation evidence files and their SHA-256 digests.

    -> `_passed.flag_6A`@fingerprint
         - Computes bundle_digest over all evidence and writes:
              `sha256_hex = <bundle_digest>`.

    - S5 is where the static fraud posture is finalised and the **6A segment-level HashGate** is built.


Downstream obligations
----------------------
- **6B (Layer-3 flows & transactions)** MUST:
    - treat s1–s4 bases as the only entity/graph definition for this world & seed,
    - treat s5_*_fraud_roles_6A as the only static fraud roles,
    - gate all use of 6A outputs on the 6A HashGate:
          1. validate validation_bundle_index_6A.json,
          2. recompute its bundle digest over evidence files,
          3. ensure `_passed.flag_6A.sha256_hex` matches that digest,
          4. ensure s5_validation_report_6A.overall_status == "PASS".

- **External tools / auditors**:
    - use s5_validation_report_6A + issue table + bundle/flag to decide if a given 6A world
      is acceptable for simulation or analysis.

Legend
------
(Sx) = state in Segment 6A
[seed, fingerprint]  = partitions for seed-scoped outputs (S1–S4 + fraud-role surfaces)
[fingerprint]         = partitions for S0 & S5 validation artefacts
[NO RNG]              = state consumes no RNG
[RNG-BEARING]         = state uses RNG under Layer-3 RNG policy
HashGate (6A)         = validation_bundle_index_6A + `_passed.flag_6A` per manifest_fingerprint
```