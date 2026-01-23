```
        LAYER 3 · SEGMENT 6A — STATE S4 (DEVICES, IPs & NETWORK GRAPH)  [RNG-BEARING]

Authoritative inputs (read-only at S4 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_6A
      @ data/layer3/6A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_6A.json
      · provides, for this world:
          - manifest_fingerprint      (world id from Layers 1 & 2),
          - parameter_hash            (6A parameter pack),
          - run_id                    (6A run id; S4 outputs MUST NOT depend on it),
          - sealed_inputs_digest_6A   (hash over sealed_inputs_6A),
          - upstream_gates{segment_id → {gate_status,bundle_root,sha256_hex}},
          - s0_spec_version, created_utc.
      · S4 MUST:
          - trust upstream gate_status for {1A,1B,2A,2B,3A,3B,5A,5B},
          - only run if all required segments have gate_status="PASS",
          - recompute sealed_inputs_digest_6A from sealed_inputs_6A and require equality.

    - sealed_inputs_6A
      @ data/layer3/6A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6A.parquet
      · one row per artefact that 6A is allowed to read:
          {owner_layer, owner_segment, artifact_id, manifest_key,
           path_template, partition_keys[], schema_ref,
           sha256_hex, role, status, read_scope, source_dictionary, source_registry}.
      · S4 MUST:
          - only consume artefacts recorded here,
          - honour status (REQUIRED/OPTIONAL/IGNORED/REQUIRED_MISSING),
          - honour read_scope:
                · ROW_LEVEL      → may read rows,
                · METADATA_ONLY  → metadata only (no row-level logic).

[Schema+Dict · catalogue authority]
    - schemas.layer3.yaml, schemas.6A.yaml
        · shape authority for:
              - s1_party_base_6A,
              - s2_account_base_6A,
              - s3_instrument_base_6A, s3_account_instrument_links_6A,
              - s4_device_base_6A,
              - s4_ip_base_6A,
              - s4_device_links_6A,
              - s4_ip_links_6A.
    - dataset_dictionary.layer3.6A.yaml
        · IDs & contracts for:
              - s1_party_base_6A
                · path: data/layer3/6A/s1_party_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/…
              - s2_account_base_6A
                · path: data/layer3/6A/s2_account_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/…
              - s3_instrument_base_6A
                · path: data/layer3/6A/s3_instrument_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/…
              - s3_account_instrument_links_6A
                · path: data/layer3/6A/s3_account_instrument_links_6A/seed={seed}/fingerprint={manifest_fingerprint}/…
              - s4_device_base_6A
                · path: data/layer3/6A/s4_device_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/…
                · partition_keys: [seed, fingerprint]
                · primary_key:    [device_id]
                · schema_ref:     schemas.6A.yaml#/s4/device_base
              - s4_ip_base_6A
                · path: data/layer3/6A/s4_ip_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/…
                · primary_key:    [ip_id]
                · schema_ref:     schemas.6A.yaml#/s4/ip_base
              - s4_device_links_6A
                · path: data/layer3/6A/s4_device_links_6A/seed={seed}/fingerprint={manifest_fingerprint}/s4_device_links_6A.parquet
                · schema_ref:     schemas.6A.yaml#/s4/device_links
              - s4_ip_links_6A
                · path: data/layer3/6A/s4_ip_links_6A/seed={seed}/fingerprint={manifest_fingerprint}/s4_ip_links_6A.parquet
                · schema_ref:     schemas.6A.yaml#/s4/ip_links
    - artefact_registry_6A.yaml
        · maps S4 priors/taxonomies/configs to logical IDs, roles and schema_refs.

[Inputs from 6A.S1–S3 · entity bases]
    - s1_party_base_6A
      · producer: 6A.S1 — universe of parties/customers.
      · S4 uses:
          - party_id,
          - party_type, segment_id, region_id / country_iso,
          - any static attributes used as features in device/IP priors.

    - s2_account_base_6A
      · producer: 6A.S2 — universe of accounts/products.
      · S4 uses:
          - account_id, owner_party_id, owner_merchant_id?,
          - account_type, product_family_id, currency_iso,
          - as features for device planning (e.g. more devices for certain account profiles).

    - s3_instrument_base_6A, s3_account_instrument_links_6A
      · producer: 6A.S3 — universe of instruments (cards/handles etc.) and their links to accounts.
      · S4 uses:
          - instrument_id, instrument_type, scheme, etc.
          - as optional features for graph wiring (e.g. devices linked to instruments).

[6A priors & taxonomies used by S4 (must be in sealed_inputs_6A)]
    - Device priors & taxonomies:
        · device_type taxonomy (e.g. MOBILE_PHONE, TABLET, DESKTOP, POS_TERMINAL, ATM),
        · OS, UA-family, device_risk_code taxonomies,
        · device-count priors:
              - expected devices per party/account/merchant per device planning cell,
        · device-sharing priors:
              - how often devices are shared across parties/accounts/merchants,
              - degree distributions (devices per party, parties per device).

    - IP / endpoint priors & taxonomies:
        · ip_type taxonomy (e.g. RESIDENTIAL, CORP, MOBILE_NETWORK, HOSTING_PROVIDER),
        · ip_asn_class taxonomy,
        · IP-count priors:
              - expected IPs per device/party/merchant per IP planning cell,
        · IP-sharing priors & degree distributions:
              - devices per IP, parties per IP, merchants per IP.

    - Graph/linkage rules:
        · which entity types devices/IPs may link to (party/account/instrument/merchant),
        · min/max degrees:
              - min_devices_per_party, max_devices_per_party,
              - min_ips_per_device, max_ips_per_device,
              - similar for parties/merchants.

    - S4 configuration:
        · knobs for smoothing, global caps and performance cutoffs,
        · RNG-family configuration (for counts, allocations, wiring).

[Outputs owned by S4]
    - s4_device_base_6A   (required)
      · one row per device_id (unique within seed+mf) with:
            seed,
            manifest_fingerprint,
            device_id,
            device_type,
            os_family?,
            ua_family?,
            static flags (e.g. is_emulator, is_rooted) if modelled,
            optional primary_party_id / primary_merchant_id / home_region_id,
            source_policy_id/version.

    - s4_ip_base_6A       (required)
      · one row per ip_id (masked endpoint) with:
            seed,
            manifest_fingerprint,
            ip_id,
            ip_type,
            asn_class?,
            home_region_id / country_iso?,
            static risk flags (e.g. is_datacenter, is_high_risk),
            source_policy_id/version.

    - s4_device_links_6A  (required)
      · device→entity edges; each row describes one device link:
            seed, manifest_fingerprint,
            device_id,
            link_target_type ∈ {PARTY, ACCOUNT, INSTRUMENT, MERCHANT},
            link_target_id,
            link_role          (e.g. PRIMARY_OWNER, SECONDARY_OWNER, USED_ON, ISSUER_DEVICE_FOR…),
            link_strength?     (optional weight/score if modelled).

    - s4_ip_links_6A      (required)
      · ip→entity/device edges; each row describes one IP link:
            seed, manifest_fingerprint,
            ip_id,
            link_target_type ∈ {DEVICE, PARTY, MERCHANT},
            link_target_id,
            link_role          (e.g. SEEN_FROM, HOME_IP_FOR, LOGINS_FROM),
            link_strength?     (optional).

[Numeric & RNG posture]
    - S4 is **RNG-bearing**:
        · RNG families:
              - `device_count_realisation`:
                    * integerises continuous device targets → N_device per cell/device_type.
              - `device_allocation_sampling`:
                    * allocates devices to parties/accounts/merchants, with sharing patterns.
              - `ip_count_realisation`:
                    * integerises continuous IP targets → N_ip per cell/ip_type.
              - `ip_allocation_sampling`:
                    * allocates IPs to devices/parties/merchants with sharing patterns.
        · S4 MUST:
              - use only approved streams/substreams per RNG family,
              - log events with correct blocks/draws/counters into rng_event, rng_trace_log, rng_audit_log.

    - Determinism:
        · Given (manifest_fingerprint, parameter_hash, seed) and sealed priors/configs,
          S4 MUST produce the same device/IP bases and link tables.


----------------------------------------------------------------------
DAG — 6A.S4 (party/account/instrument bases + priors → devices, IPs & graph)  [RNG-BEARING]

### Phase 1 — Gate & resolve inputs (RNG-free)

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S4.1) Verify S0 gate & sealed_inputs_6A
                    - Resolve:
                        · s0_gate_receipt_6A@fingerprint={manifest_fingerprint},
                        · sealed_inputs_6A@fingerprint={manifest_fingerprint},
                      via dataset_dictionary.layer3.6A.yaml.
                    - Validate both against schemas.6A.yaml.
                    - Recompute sealed_inputs_digest_6A from sealed_inputs_6A;
                      require equality with `sealed_inputs_digest_6A` in the receipt.
                    - Check `upstream_gates`:
                        · all required segments {1A,1B,2A,2B,3A,3B,5A,5B} must have gate_status="PASS".
                    - If any check fails:
                        · S4 MUST abort; no devices/IPs may be realised.

sealed_inputs_6A,
artefact_registry_6A,
dataset_dictionary.layer3.6A.yaml,
[Schema+Dict]
                ->  (S4.2) Resolve S1–S3 bases & S4 priors/taxonomies
                    - Filter sealed_inputs_6A rows for S4 roles:
                          "party_base", "account_base", "instrument_base", "account_instrument_links",
                          "device_priors", "device_taxonomy", "ip_priors", "ip_taxonomy",
                          "graph_linkage_rules", "s4_config", plus any OPTIONAL context.
                    - Resolve:
                        · s1_party_base_6A@seed={seed}/fingerprint={manifest_fingerprint},
                        · s2_account_base_6A@seed={seed}/fingerprint={manifest_fingerprint},
                        · s3_instrument_base_6A@seed={seed}/fingerprint={manifest_fingerprint},
                        · s3_account_instrument_links_6A@seed={seed}/fingerprint={manifest_fingerprint},
                        · device/IP priors & taxonomies, graph/linkage rules, S4 config.
                    - For each resolved external artefact:
                        · recompute SHA-256(raw bytes),
                        · assert equality with sha256_hex in sealed_inputs_6A,
                        · validate against its schema_ref.
                    - Validate S1–S3 datasets against their schema anchors.

### Phase 2 — Device planning & realisation

s1_party_base_6A,
s2_account_base_6A,
(optional) merchant universe from upstream (METADATA_ONLY),
device priors & taxonomies
                ->  (S4.3) Define device-planning cell domain C_dev  (RNG-free)
                    - Define a **device planning cell** c_dev, e.g.:
                          c_dev = (region_id, party_type, segment_id[, account_class])
                      as specified in the S4 spec.
                    - Map each party to its planning cell via S1 fields.
                    - Optionally, derive account-based totals per cell:
                          N_parties(c_dev), N_accounts(c_dev) and/or N_merchants(c_dev)
                          from S1/S2 and merchant context (where available).
                    - Domain C_dev:
                        · cells where priors indicate device mass > 0 or where S4 config mandates a cell.
                    - S4 MUST NOT derive devices directly from upstream events; only from priors & cell counts.

C_dev,
device priors,
N_parties(c_dev), N_accounts(c_dev), N_merchants(c_dev)
                ->  (S4.4) Compute continuous device targets N_device_target(c_dev, Dtype)  (RNG-free)
                    - For each device planning cell c_dev and device_type Dtype:
                        · from priors, compute λ_devices_per_party, λ_devices_per_account, λ_devices_per_merchant.
                        · Compute continuous target:
                              N_device_target(c_dev, Dtype) =
                                  N_parties(c_dev)  * λ_devices_per_party(c_dev,Dtype)  +
                                  N_accounts(c_dev) * λ_devices_per_account(c_dev,Dtype) +
                                  N_merchants(c_dev)* λ_devices_per_merchant(c_dev,Dtype).
                    - Apply global/world-level caps if configured:
                        · e.g. limit total mobile phones or POS terminals.
                    - Ensure:
                        · N_device_target ≥ 0 and finite for all (c_dev,Dtype).

N_device_target(c_dev,Dtype),
device_count_realisation RNG family
                ->  (S4.5) Realise integer device counts N_device(c_dev,Dtype)  (RNG-bearing)
                    - Introduce RNG using `device_count_realisation`.
                    - For each cell c_dev (potentially with a hierarchical scheme):
                        · integerise N_device_target(c_dev,Dtype) → N_device(c_dev,Dtype)
                          using a documented rounding + residual distribution or multinomial law.
                    - Invariants:
                        · N_device(c_dev,Dtype) ≥ 0,
                        · per-cell totals respect config (e.g. sum across types ≈ sum of targets),
                        · required cell×type combos have N_device(c_dev,Dtype) ≥ 1 where mandated.
                    - Any failure ⇒ `6A.S4.DEVICE_COUNT_REALISATION_FAILED`.

s1_party_base_6A,
s2_account_base_6A,
(optional) merchant info,
N_device(c_dev,Dtype),
graph/linkage rules,
device_allocation_sampling RNG family
                ->  (S4.6) Allocate devices to parties/accounts/merchants (sharing patterns)  (RNG-bearing)
                    - For each (c_dev,Dtype) with N_device>0:
                        · Build eligible sets:
                              ELIGIBLE_PARTY(c_dev,Dtype),
                              ELIGIBLE_ACCOUNT(c_dev,Dtype),
                              ELIGIBLE_MERCHANT(c_dev,Dtype),
                          according to linkage rules (which entity types may own/use this device_type in this cell).
                        - Using `device_allocation_sampling` and sharing priors:
                              - decide how many devices are “anchored” to each party/account/merchant,
                              - optionally decide sharing:
                                    * how many parties/devices share a device,
                                    * device degrees (devices per party, parties per device).
                    - This yields **device slots**:
                        · SLOT_dev = (device_anchor_entity_id, device_type Dtype, cell c_dev, local index j),
                          where device_anchor_entity_id is usually a party or merchant id.
                    - S4 MUST enforce:
                        · per-entity max_devices_per_type as defined in rules,
                        · no slot assigned to ineligible entities.

device slots,
device taxonomies,
device attribute priors,
device_attribute_sampling RNG family
                ->  (S4.7) Construct device_id & sample device attributes  (RNG-bearing)
                    - For each device slot (anchor_entity_id, c_dev,Dtype,j):
                        1. Construct device_id deterministically:
                               device_id = LOW64(
                                   SHA256( mf || seed || "device" || anchor_entity_id || Dtype || uint64(j) )
                               ).
                        2. Sample device attributes from priors conditioned on (c_dev,Dtype), e.g.:
                               - os_family, ua_family,
                               - static risk codes (is_emulator, is_rooted),
                               - primary_party_id / primary_merchant_id (if anchor is ambiguous).
                        3. Optionally derive a home_region_id / home_country_iso.
                    - Guardrails:
                        · device_id MUST be unique within (seed, mf),
                        · attributes MUST be consistent with taxonomies & linkage context.

device rows (device_id, anchor_entity_id, attrs)
                ->  (S4.8) Assemble s4_device_base_6A & device→entity links  (RNG-free)
                    - Build `s4_device_base_6A`:
                        · one row per device_id with:
                              device_type, os_family, ua_family, static flags, primary_party_id/merchant_id, home_region_id, etc.
                    - Build `s4_device_links_6A`:
                        · for each device:
                              - at least one link row for its anchor_entity_id:
                                    link_target_type ∈ {PARTY, MERCHANT},
                                    link_target_id   = anchor_entity_id,
                                    link_role        = "PRIMARY_OWNER" (or similar).
                              - additional link rows per sharing rules:
                                    link_target_type could be PARTY/ACCOUNT/INSTRUMENT/MERCHANT,
                                    link_role codes per graph/linkage config (e.g. USED_BY, DEVICE_FOR_ACCOUNT).
                    - Validate:
                        · s4_device_base_6A against schemas.6A.yaml#/s4/device_base,
                        · s4_device_links_6A against schemas.6A.yaml#/s4/device_links,
                        · referential integrity:
                              device_id in links must exist in device_base,
                              link_target_id must exist in the corresponding base (party/account/instrument/merchant).
                    - Write both datasets to their dictionary paths with write-once+idempotent discipline.

### Phase 3 — IP / endpoint planning & realisation

s1_party_base_6A,
(optional) merchant universe,
s4_device_base_6A,
s4_device_links_6A,
IP priors & taxonomies
                ->  (S4.9) Define IP-planning cell domain C_ip  (RNG-free)
                    - Define an **IP planning cell** c_ip, e.g.:
                          c_ip = (region_id, ip_type, asn_class)
                      as specified in S4 design.
                    - From device_base and device_links (and optional party/merchant context):
                        · derive counts such as:
                              N_devices(c_ip), N_parties(c_ip), N_merchants(c_ip).
                    - Domain:
                        · C_ip = { c_ip | priors indicate IP mass > 0 or config mandates cell }.
                    - S4 MUST NOT derive IPs directly from upstream events; only from priors and entity counts.

C_ip,
IP priors,
N_devices(c_ip), N_parties(c_ip), N_merchants(c_ip)
                ->  (S4.10) Compute continuous IP targets N_ip_target(c_ip, Iptype)  (RNG-free)
                    - For each c_ip and ip_type Iptype:
                        · from priors, compute λ_ip_per_device / λ_ip_per_party / λ_ip_per_merchant,
                        · continuous target:
                              N_ip_target(c_ip,Iptype) =
                                  N_devices(c_ip)  * λ_ip_per_device(c_ip,Iptype)  +
                                  N_parties(c_ip) * λ_ip_per_party(c_ip,Iptype)   +
                                  N_merchants(c_ip)*λ_ip_per_merchant(c_ip,Iptype).
                    - Apply any global caps:
                        · e.g. max hosting IPs per world.
                    - Ensure N_ip_target(c_ip,Iptype) ≥ 0 and finite.

N_ip_target(c_ip,Iptype),
ip_count_realisation RNG family
                ->  (S4.11) Realise integer IP counts N_ip(c_ip,Iptype)  (RNG-bearing)
                    - Introduce RNG under `ip_count_realisation`.
                    - Per c_ip, integerise N_ip_target(c_ip,Iptype) → N_ip(c_ip,Iptype)
                      via multinomial or rounding + residual distribution.
                    - Invariants:
                        · N_ip(c_ip,Iptype) ≥ 0,
                        · any mandatory (c_ip,Iptype) has N_ip ≥ 1 where required.
                    - Any failure ⇒ `6A.S4.IP_COUNT_REALISATION_FAILED`.

N_ip(c_ip,Iptype),
s4_device_base_6A,
s4_device_links_6A,
s1_party_base_6A,
(optional) merchant context,
ip_allocation_sampling RNG family
                ->  (S4.12) Allocate IPs to devices/parties/merchants  (RNG-bearing)
                    - For each c_ip and ip_type Iptype with N_ip>0:
                        · build eligible sets per linking rules:
                              ELIGIBLE_DEVICE(c_ip,Iptype),
                              ELIGIBLE_PARTY(c_ip,Iptype),
                              ELIGIBLE_MERCHANT(c_ip,Iptype).
                        - Use `ip_allocation_sampling` and sharing priors to:
                              - decide which devices/parties/merchants get each IP,
                              - decide sharing structure (IPs shared across devices, parties behind same IP, etc.),
                              - enforce min/max degrees (e.g. ip_max_devices, device_max_ips).
                    - This yields IP slots plus their target attachments:
                        · SLOT_ip = (ip_anchor_type, ip_anchor_id, c_ip,Iptype,j),
                          plus planned edges (device/party/merchant) per sharing pattern.

SLOT_ip,
ip taxonomies,
ip attribute priors,
ip_attribute_sampling RNG family
                ->  (S4.13) Construct ip_id & sample IP attributes  (RNG-bearing)
                    - For each IP slot:
                        1. Construct ip_id deterministically:
                               ip_id = LOW64(
                                   SHA256( mf || seed || "ip" || ip_anchor_type || ip_anchor_id || uint64(j) )
                               ).
                        2. Sample IP attributes per priors:
                               - ip_type, asn_class,
                               - home_region_id / country_iso,
                               - static risk codes (e.g. is_datacenter, is_high_risk),
                               - optionally masked textual representation (e.g. last octet masked).
                    - Guardrails:
                        · ip_id unique within (seed,mf),
                        · attributes valid per taxonomies.

IP rows (ip_id, attrs),
planned IP edges
                ->  (S4.14) Assemble s4_ip_base_6A & ip→entity/device links  (RNG-free)
                    - Build `s4_ip_base_6A`:
                        · one row per ip_id with ip_type, asn_class, home_region_id, risk flags, etc.
                    - Build `s4_ip_links_6A`:
                        · one or more link rows per ip_id according to plan:
                              - ip_id,
                              - link_target_type ∈ {DEVICE, PARTY, MERCHANT},
                              - link_target_id,
                              - link_role (e.g. SEEN_FROM, HOME_IP_FOR),
                              - link_strength if modelled.
                    - Validate:
                        · s4_ip_base_6A against schemas.6A.yaml#/s4/ip_base,
                        · s4_ip_links_6A against schemas.6A.yaml#/s4/ip_links,
                        · referential integrity:
                              - ip_id in links must exist in ip_base,
                              - link_target_id must exist in corresponding bases (device, party, merchant).
                    - Write both datasets to their dictionary paths with write-once+idempotent semantics.

Downstream touchpoints
----------------------
- **6A.S5 — Fraud posture & 6A HashGate:**
    - MUST treat:
          - s4_device_base_6A, s4_ip_base_6A as the only device/IP universes for this (mf,seed),
          - s4_device_links_6A, s4_ip_links_6A as the **complete** static graph edge sets.
    - When assigning fraud roles (e.g. risky device, risky IP, mule clusters),
      S5 uses these bases & links plus S1–S3 outputs.

- **6B — Behavioural flows & fraud simulation:**
    - MUST treat s4_device_base_6A/s4_ip_base_6A & link tables as read-only ground truth for
      “which devices/IPs exist and who/what they are attached to”.
    - All transaction/fraud flows in 6B that refer to device_id or ip_id MUST use IDs from these bases.
    - 6B MUST gate on the 6A segment-level HashGate (S5 bundle + `_passed.flag`) before trusting this graph.

- **Authority recap:**
    - S1 owns parties; S2 owns accounts; S3 owns instruments.
    - S4 owns only:
         - device & IP universes,
         - and the static entity graph over {party, account, instrument, merchant, device, ip}.
    - Upstream surfaces MUST NOT be mutated; S4 only adds new nodes & edges.
```