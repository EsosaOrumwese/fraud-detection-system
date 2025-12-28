```
        LAYER 3 · SEGMENT 6A — STATE S5 (STATIC FRAUD POSTURE & 6A HASHGATE)  [RNG-BEARING]

Authoritative inputs (read-only at S5 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_6A
      @ data/layer3/6A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_6A.json
      · provides, for this world:
          - manifest_fingerprint        (world id from Layers 1 & 2),
          - parameter_hash              (6A parameter/prior pack id),
          - run_id                      (S5 must NOT depend on run_id),
          - sealed_inputs_digest_6A     (hash over sealed_inputs_6A),
          - upstream_gates{segment_id → {gate_status,bundle_root,sha256_hex}},
          - s0_spec_version, created_utc.
      · S5 MUST:
          - trust upstream gate_status for {1A,1B,2A,2B,3A,3B,5A,5B},
          - only run if all required segments have gate_status="PASS",
          - recompute sealed_inputs_digest_6A from sealed_inputs_6A and require equality.

    - sealed_inputs_6A
      @ data/layer3/6A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6A.parquet
      · one row per artefact the 6A segment is allowed to read:
          {owner_layer, owner_segment, artifact_id, manifest_key,
           path_template, partition_keys[], schema_ref,
           sha256_hex, role, status, read_scope, source_dictionary, source_registry}.
      · S5 MUST:
          - only consume artefacts recorded here,
          - honour status (REQUIRED/OPTIONAL/IGNORED/REQUIRED_MISSING),
          - honour read_scope:
                · ROW_LEVEL      → may read rows,
                · METADATA_ONLY  → metadata only.

[Schema+Dict · catalogue authority]
    - schemas.layer3.yaml, schemas.6A.yaml
        · shape authority for:
              - s1_party_base_6A,
              - s2_account_base_6A, s2_party_product_holdings_6A,
              - s3_instrument_base_6A, s3_account_instrument_links_6A,
              - s4_device_base_6A, s4_ip_base_6A,
              - s4_device_links_6A, s4_ip_links_6A,
              - s5_party_fraud_roles_6A,
              - s5_account_fraud_roles_6A,
              - s5_merchant_fraud_roles_6A,
              - s5_device_fraud_roles_6A,
              - s5_ip_fraud_roles_6A,
              - s5_validation_report_6A,
              - s5_issue_table_6A,
              - validation_bundle_index_6A,
              - validation_passed_flag_6A.
    - dataset_dictionary.layer3.6A.yaml
        · IDs & contracts for all 6A datasets, including:
              - s5_party_fraud_roles_6A
                · path:
                    data/layer3/6A/s5_party_fraud_roles_6A/seed={seed}/fingerprint={manifest_fingerprint}/s5_party_fraud_roles_6A.parquet
                · partitioning: [seed, fingerprint]
                · ordering:     [party_id]
                · schema_ref:   schemas.6A.yaml#/s5/party_fraud_roles
              - s5_account_fraud_roles_6A
                · similar, partitioned by [seed, fingerprint], ordered by [account_id]
                · schema_ref:   schemas.6A.yaml#/s5/account_fraud_roles
              - s5_merchant_fraud_roles_6A
                · ordered by [merchant_id]
                · schema_ref:   schemas.6A.yaml#/s5/merchant_fraud_roles
              - s5_device_fraud_roles_6A
                · ordered by [device_id]
                · schema_ref:   schemas.6A.yaml#/s5/device_fraud_roles
              - s5_ip_fraud_roles_6A
                · ordered by [ip_id]
                · schema_ref:   schemas.6A.yaml#/s5/ip_fraud_roles
              - s5_validation_report_6A
                · path:
                    data/layer3/6A/validation/fingerprint={manifest_fingerprint}/s5_validation_report_6A.json
                · partitioning: [fingerprint]
                · schema_ref:   schemas.layer3.yaml#/validation/6A/validation_report_6A
              - s5_issue_table_6A (optional)
                · path:
                    data/layer3/6A/validation/fingerprint={manifest_fingerprint}/s5_issue_table_6A.parquet
                · schema_ref:   schemas.layer3.yaml#/validation/6A/issue_table_6A
              - validation_bundle_index_6A
                · path:
                    data/layer3/6A/validation/fingerprint={manifest_fingerprint}/validation_bundle_index_6A.json
                · schema_ref:   schemas.layer3.yaml#/validation/6A/validation_bundle_index_6A
              - validation_passed_flag_6A
                · path:
                    data/layer3/6A/validation/fingerprint={manifest_fingerprint}/_passed.flag
                · schema_ref:   schemas.layer3.yaml#/validation/6A/passed_flag_6A

[Inputs from 6A.S1–S4 · entity bases & links]
    For each `(seed, manifest_fingerprint)` universe that S5 is asked to posture:

    - s1_party_base_6A
        · party_id, party_type, segment_id, region_id/country_iso, static attributes.
    - s2_account_base_6A
        · account_id, owner_party_id, optional owner_merchant_id,
          account_type, product_family_id, currency_iso, static flags.
    - s2_party_product_holdings_6A
        · per-party holdings by product, derived from s2_account_base_6A.
    - Merchant universe (from upstream Layer-1/3A)
        · merchant_id, mcc, channel, region/country; treated as read-only surface.
    - s3_instrument_base_6A, s3_account_instrument_links_6A
        · instrument_id, instrument_type, scheme/network, and their links to accounts/parties.
    - s3_party_instrument_holdings_6A (optional)
        · per-party instrument counts; used as context only.
    - s4_device_base_6A, s4_ip_base_6A
        · device_id, device_type, os/UA families, static risk flags;
        · ip_id, ip_type, asn_class, geo, static risk flags.
    - s4_device_links_6A, s4_ip_links_6A
        · device→entity edges (device↔party/account/instrument/merchant),
        · ip→device/party/merchant edges.

    S5 MUST NOT:
        - create new parties/accounts/merchants/devices/IPs,
        - mutate any upstream bases or link tables.

[S5 priors, taxonomies & validation policy]
    - Fraud-role priors per entity type:
        · party-level role priors (per region, segment, party_type, and possibly graph features),
        · account-level role priors (per product family, account_type, owner segment),
        · merchant-level role priors (per mcc/channel/region),
        · device-level role priors (per device_type, risk flags, degree),
        · ip-level role priors (per ip_type/asn_class/risk flags, degree).
    - Fraud-role taxonomies:
        · enumerations of roles per entity type (e.g. PARTY roles, ACCOUNT roles, DEVICE roles, etc.),
        · allowed transitions & compatibility constraints (e.g. certain role combinations forbidden on same entity).
    - S5 validation policy:
        · list of checks to run (coverage, mix vs priors, structure constraints, graph invariants),
        · severity per check (ERROR/WARN/INFO),
        · thresholds and tolerances per metric.

[Outputs owned by S5]
    Seed-scoped fraud-posture surfaces  (partitioned by [seed, fingerprint]):

    - s5_party_fraud_roles_6A
        · one row per party_id; columns include:
              party_id, fraud_role_party (enum), optional risk_tier_party, cell_id, priors used, RNG lineage.

    - s5_account_fraud_roles_6A
        · one row per account_id; columns include:
              account_id, fraud_role_account, optional risk_tier_account, cell_id, etc.

    - s5_merchant_fraud_roles_6A
        · one row per merchant_id in the world; columns include:
              merchant_id, fraud_role_merchant, optional risk_tier_merchant.

    - s5_device_fraud_roles_6A
        · one row per device_id; columns include:
              device_id, fraud_role_device, optional risk_tier_device.

    - s5_ip_fraud_roles_6A
        · one row per ip_id; columns include:
              ip_id, fraud_role_ip, optional risk_tier_ip.

    Fingerprint-scoped validation artefacts  (partitioned by [fingerprint]):

    - s5_validation_report_6A
        · single JSON per manifest_fingerprint; summary of checks & metrics.

    - s5_issue_table_6A (optional)
        · per-issue table; one row per failing/borderline check instance.

    - validation_bundle_index_6A
        · index.json; enumerates bundle members `{path, sha256_hex}`, paths relative to 6A validation root.

    - validation_passed_flag_6A (`_passed.flag`)
        · tiny text artefact with `sha256_hex = <bundle_digest_sha256>`.

[Numeric & RNG posture]
    - S5 is **RNG-bearing**:
        · RNG families:
              - `fraud_role_count_realisation` per entity type:
                    * converts continuous role targets → integer counts per (cell, role).
              - `fraud_role_assignment_sampling` per entity type:
                    * assigns roles to specific entities using priors & structural features.
        · S5 MUST:
              - use only approved RNG streams for these families,
              - log all RNG usage into rng_event/rng_trace_log/rng_audit_log.
    - Determinism:
        · Given fixed (manifest_fingerprint, parameter_hash, seed), sealed_inputs_6A, S1–S4 outputs & S5 priors,
          S5 MUST produce identical fraud-role surfaces and validation artefacts.


----------------------------------------------------------------------
DAG — 6A.S5 (S1–S4 world + priors → static fraud posture + 6A HashGate)  [RNG-BEARING]

### Phase 1 — Gate & load bases (no RNG)

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S5.1) Verify S0 gate & sealed_inputs_6A
                    - Resolve s0_gate_receipt_6A and sealed_inputs_6A via Layer-3 dictionary.
                    - Validate both against schemas.6A.yaml.
                    - Recompute sealed_inputs_digest_6A from sealed_inputs_6A (canonical row order + serialisation);
                      require equality with value embedded in s0_gate_receipt_6A.
                    - Check upstream_gates in receipt:
                        · all required segments {1A,1B,2A,2B,3A,3B,5A,5B} MUST be "PASS".
                    - If any check fails:
                        · S5 MUST NOT proceed with fraud roles or bundling.

sealed_inputs_6A,
artefact_registry_6A,
dataset_dictionary.layer3.6A.yaml,
[Schema+Dict]
                ->  (S5.2) Resolve S1–S4 bases & S5 priors/taxonomies
                    - Filter sealed_inputs_6A to roles needed by S5:
                          "party_base", "account_base", "party_product_holdings",
                          "instrument_base", "account_instrument_links", "party_instrument_holdings",
                          "device_base", "ip_base", "device_links", "ip_links",
                          "fraud_role_priors_*", "fraud_role_taxonomy_*",
                          "s5_validation_policy", "s5_config".
                    - Resolve and validate:
                        · s1_party_base_6A@seed={seed}/fingerprint={mf},
                        · s2_account_base_6A@seed={seed}/fingerprint={mf},
                        · s2_party_product_holdings_6A@seed={seed}/fingerprint={mf},
                        · merchant universe surface (Layer-1),
                        · s3_instrument_base_6A, s3_account_instrument_links_6A,
                        · s4_device_base_6A, s4_ip_base_6A,
                        · s4_device_links_6A, s4_ip_links_6A,
                        · fraud-role priors & taxonomies per entity type,
                        · S5 validation policy.
                    - For each external artefact:
                        · recompute SHA-256(raw bytes), assert equality with sha256_hex in sealed_inputs_6A,
                        · validate against its schema_ref.

### Phase 2 — Role domains & continuous targets (no RNG)

s1_party_base_6A,
fraud-role priors/taxonomies for parties
                ->  (S5.3) Define party role cells & continuous targets  (RNG-free)
                    - Define **party role cell** key:
                          c_party = (region_id, segment_id, party_type, maybe extra features)
                      as defined in S5 spec.
                    - Map each party to its role cell using S1 attributes.
                    - For each cell c_party:
                        · compute N_party(c_party) = number of parties in that cell.
                    - From party fraud-role priors:
                        · derive per-role fractions π_party_role(c_party, r) for roles r in PARTY_ROLE_ENUM.
                        · continuous targets:
                              N_party_target(c_party,r) = N_party(c_party) × π_party_role(c_party,r).
                    - Collect {N_party_target(c_party,r)} for all (c_party,r).

Analogous steps for other entity types:

s2_account_base_6A,
fraud-role priors/taxonomies for accounts
                ->  (S5.4) Define account role cells & continuous targets  (RNG-free)
                    - Define **account role cell** key:
                          c_account = (region_id, owner_segment_id, account_type, product_family_id, maybe flags).
                    - Map each account to c_account and count N_account(c_account).
                    - From account fraud-role priors:
                        · derive per-role fractions π_account_role(c_account, r),
                        · continuous targets N_account_target(c_account,r) = N_account(c_account) × π_account_role(c_account,r).

merchant universe,
fraud-role priors/taxonomies for merchants
                ->  (S5.5) Define merchant role cells & continuous targets  (RNG-free)
                    - Define **merchant role cell** key:
                          c_merch = (region_id, mcc_group, channel, [zone_class]).
                    - Map each merchant to c_merch and count N_merch(c_merch).
                    - From merchant fraud-role priors:
                        · derive π_merchant_role(c_merch,r),
                        · N_merch_target(c_merch,r) = N_merch(c_merch) × π_merchant_role(c_merch,r).

s4_device_base_6A,
fraud-role priors/taxonomies for devices
                ->  (S5.6) Define device role cells & continuous targets  (RNG-free)
                    - Define **device role cell** key:
                          c_device = (region_id, device_type, os_family, risk_flags, [degree_bucket]).
                    - Map devices to c_device and count N_device(c_device),
                      optionally using degree from s4_device_links_6A (e.g. #parties per device).
                    - From device fraud-role priors:
                        · derive π_device_role(c_device,r),
                        · N_device_target(c_device,r) = N_device(c_device) × π_device_role(c_device,r).

s4_ip_base_6A,
fraud-role priors/taxonomies for IPs
                ->  (S5.7) Define IP role cells & continuous targets  (RNG-free)
                    - Define **IP role cell** key:
                          c_ip = (region_id, ip_type, asn_class, risk_flags, [degree_bucket]).
                    - Map IPs to c_ip and count N_ip(c_ip),
                      optionally using degree from s4_ip_links_6A (e.g. #devices per IP).
                    - From IP fraud-role priors:
                        · derive π_ip_role(c_ip,r),
                        · N_ip_target(c_ip,r) = N_ip(c_ip) × π_ip_role(c_ip,r).

### Phase 3 — Integer role counts per cell×role (RNG-bearing)

N_party_target(c_party,r),
N_account_target(c_account,r),
N_merch_target(c_merch,r),
N_device_target(c_device,r),
N_ip_target(c_ip,r),
fraud_role_count_realisation RNG family
                ->  (S5.8) Integerise role counts per cell×role  (RNG-bearing)
                    - Introduce RNG using `fraud_role_count_realisation` (per entity type or shared).
                    - For each entity type E ∈ {PARTY, ACCOUNT, MERCHANT, DEVICE, IP}:
                        · For each cell c_E:
                              - treat target vector {N_E_target(c_E, r)} over roles r,
                              - apply multinomial or rounding+residual scheme to draw integer counts N_E(c_E,r),
                                subject to:
                                     Σ_r N_E(c_E,r) == N_E(c_E) (the number of entities in cell c_E),
                                     N_E(c_E,r) ≥ 0 for all r,
                                     additional constraints from priors (e.g. min counts for some roles).
                    - Any integerisation failure (negative counts, mismatch of totals) MUST trigger a failure
                      (e.g. `6A.S5.ROLE_COUNT_REALISATION_FAILED`).

### Phase 4 — Assign roles to individual entities (RNG-bearing)

s1_party_base_6A,
N_party(c_party),
N_party(c_party,r),
fraud_role_assignment_sampling RNG family
                ->  (S5.9) Assign fraud roles to parties  (RNG-bearing)
                    - For each party role cell c_party:
                        · extract parties in that cell:
                              P(c_party) = {party_id} from s1_party_base_6A.
                        · we already have:
                              counts N_party(c_party,r) for each role r.
                        - Using `fraud_role_assignment_sampling`:
                              - attach a score or sampling weight to each party (optionally using structural features,
                                e.g. graph degree, product holdings),
                              - assign roles r to parties such that:
                                     exactly N_party(c_party,r) parties receive role r,
                                     each party receives exactly one role from PARTY_ROLE_ENUM.
                    - Construct `s5_party_fraud_roles_6A` rows:
                        · for each party_id, write {party_id, fraud_role_party, optional risk_tier_party, cell_id, priors_used…}.
                    - Validate:
                        · no party without a role,
                        · no party with multiple roles,
                        · role values from taxonomy only.

Analogous assignments for other entity types:

s2_account_base_6A,
N_account(c_account,r)
                ->  (S5.10) Assign fraud roles to accounts  (RNG-bearing)
                    - For each account role cell c_account:
                        · A(c_account) = set of account_id in that cell.
                        · assign roles r to accounts with exactly N_account(c_account,r) accounts per role.
                    - Emit `s5_account_fraud_roles_6A` rows.

merchant universe,
N_merch(c_merch,r)
                ->  (S5.11) Assign fraud roles to merchants  (RNG-bearing)
                    - For each merchant role cell c_merch:
                        · M(c_merch) = set of merchant_id in that cell.
                        · assign roles to match N_merch(c_merch,r) per role r.
                    - Emit `s5_merchant_fraud_roles_6A` rows.

s4_device_base_6A,
N_device(c_device,r)
                ->  (S5.12) Assign fraud roles to devices  (RNG-bearing)
                    - For each device role cell c_device:
                        · D(c_device) = set of device_id in that cell.
                        · assign roles to match N_device(c_device,r).
                    - Emit `s5_device_fraud_roles_6A` rows.

s4_ip_base_6A,
N_ip(c_ip,r)
                ->  (S5.13) Assign fraud roles to IPs  (RNG-bearing)
                    - For each IP role cell c_ip:
                        · I(c_ip) = set of ip_id in that cell.
                        · assign roles to match N_ip(c_ip,r).
                    - Emit `s5_ip_fraud_roles_6A` rows.

### Phase 5 — Segment-level checks & validation artefacts (no RNG)

fraud-role surfaces,
S1–S4 bases/links,
S5 validation policy
                ->  (S5.14) Evaluate S5 checks & build issue list  (RNG-free)
                    - Using the S5 validation policy:
                        · define a fixed set of checks (ids, severities, thresholds).
                    - For each entity type E and each check:
                        · evaluate:
                              - coverage (every entity has a role),
                              - role-mix vs priors (global/cell-level deviations),
                              - structural consistency (e.g. cannot label both party and all its accounts as contradictory roles),
                              - graph-based checks (e.g. role clustering, cross-entity consistency).
                        - mark check status as PASS/WARN/FAIL,
                        - accumulate metrics (max deviation, counts, etc.),
                        - append issue records to an in-memory `issues` buffer where checks FAIL/WARN.
                    - The result:
                        · a check registry with {check_id, status, severity, affected_count, description},
                        · an `issues` list with row-level details.

check registry,
metrics,
issues
                ->  (S5.15) Construct s5_validation_report_6A & s5_issue_table_6A  (RNG-free)
                    - Determine overall_status:
                        · "FAIL" if any check has status="FAIL",
                        · "PASS" otherwise (WARNs allowed).
                    - Build `s5_validation_report_6A` JSON:
                        · manifest_fingerprint,
                        · parameter_hash,
                        · overall_status,
                        · checks[] (id, status, severity, affected_count, description),
                        · metrics{} (role-mix deviations, counts, graph metrics, etc.),
                        · error_code if overall_status="FAIL".
                    - Build `s5_issue_table_6A` (if issues non-empty):
                        · one row per issue with:
                              manifest_fingerprint,
                              parameter_hash,
                              seed (or “all seeds” if aggregated),
                              entity_type, entity_id (if applicable),
                              check_id, issue_code, severity,
                              context fields (cell_id, region_id, role, etc.),
                              message.
                    - Validate both against schemas.layer3.yaml validation anchors.

s5_validation_report_6A,
s5_issue_table_6A (optional),
dataset_dictionary.layer3.6A.yaml
                ->  (S5.16) Write s5_validation_report_6A & s5_issue_table_6A  (RNG-free)
                    - Target paths (fingerprint-scoped) via dictionary:
                        · s5_validation_report_6A:
                              data/layer3/6A/validation/fingerprint={mf}/s5_validation_report_6A.json
                        · s5_issue_table_6A (if present):
                              data/layer3/6A/validation/fingerprint={mf}/s5_issue_table_6A.parquet
                    - Immutability:
                        · if artefact does not exist:
                              - write via staging → fsync → atomic move.
                        · if artefact exists:
                              - read existing, normalise logical content,
                              - if byte-identical → idempotent re-run; OK,
                              - else → conflict; MUST NOT overwrite.

### Phase 6 — Validation bundle & `_passed.flag`  (no RNG)

bundle members (report, issues, optional extras),
schemas.layer3.yaml
                ->  (S5.17) Build validation_bundle_index_6A.json
                    - Bundle root:
                        · B_root = data/layer3/6A/validation/fingerprint={mf}/
                    - Choose evidence members, at minimum:
                        · s5_validation_report_6A.json,
                        · s5_issue_table_6A.parquet (if present).
                    - For each member file f:
                        · compute relative path p under B_root (no leading '/', no '.', no '..'),
                        · read raw bytes,
                        · compute sha256_hex(f) = SHA256(raw_bytes) as lowercase hex.
                    - Build entries[] = [{path=p, sha256_hex=sha256_hex(f)}, …].
                    - Sort entries by path ASCII-lexically.
                    - Construct index object conforming to schemas.layer3.yaml#/validation/6A/validation_bundle_index_6A.
                    - Write JSON to:
                        · data/layer3/6A/validation/fingerprint={mf}/validation_bundle_index_6A.json
                      with write-once+idempotence (same rules as above).

validation_bundle_index_6A,
bundle members
                ->  (S5.18) Compute bundle_digest_sha256 & write `_passed.flag`
                    - Re-open validation_bundle_index_6A.json and parse entries.
                    - For each entry in entries[] (in stored order):
                        · read raw bytes from B_root/path,
                        · append to a hash stream.
                    - Compute bundle_digest_sha256 = SHA256(concatenated_bytes), encoded as hex64.
                    - Construct `validation_passed_flag_6A` logical payload:
                        · sha256_hex = bundle_digest_sha256.
                    - On disk:
                        · write `_passed.flag` under B_root with representation required by
                          schemas.layer3.yaml#/validation/6A/passed_flag_6A (e.g. `sha256_hex = <hex>`).
                    - Immutability:
                        · if `_passed.flag` does not exist:
                              - write via staging → fsync → atomic move.
                        · if exists:
                              - read and parse existing sha256_hex,
                              - if equal to bundle_digest_sha256 → idempotent re-run; OK,
                              - else → conflict; MUST NOT overwrite.

Downstream touchpoints
----------------------
- **6B (Layer-3 flows & transactions):**
    - MUST treat the 6A world as **sealed** for this manifest_fingerprint only if:
          1. `validation_bundle_index_6A.json` exists and is schema-valid,
          2. `_passed.flag` exists and its sha256_hex equals the recomputed bundle digest,
          3. `s5_validation_report_6A.overall_status == "PASS"`.
    - Only then may 6B:
          - read s5_*_fraud_roles_6A as authoritative static fraud posture,
          - treat S1–S4 bases & links as a trusted graph.

- **External tooling & audits:**
    - Use s5_validation_report_6A and s5_issue_table_6A as the canonical description of 6A’s health for a world.
    - Use validation_bundle_index_6A + `_passed.flag` to verify that the evidence is complete and untampered.

- **Authority recap:**
    - S1–S4 define the static entity graph (who/what exists and how they connect).
    - S5 defines **static fraud posture** over that graph and the segment-level HashGate.
    - No later component may change roles or HashGate semantics; they can only **consume** them.
```