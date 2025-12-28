# Layer-3 - Segment 6A - State Overview (S0-S5)

Segment 6A builds the entity and product world. It gates upstream layers, realises parties, accounts, instruments, devices/IPs, assigns static fraud posture, and seals the segment with a PASS bundle. Outputs are authoritative for 6B and any consumer.

## Segment role at a glance
- Enforce upstream HashGates (1A–3B, 5A, 5B) and seal 6A priors/policies before any read.
- Realise the party/customer universe (ids, segments, geos).
- Realise accounts/products and attach them to parties (and merchants where applicable).
- Realise instruments, devices, IPs, and the static entity graph (links across all entities).
- Assign static fraud roles and publish `validation_bundle_6A` + `_passed.flag`.

---

## S0 - Gate & sealed inputs (RNG-free)
**Purpose & scope**  
Verify `_passed.flag_*` for 1A–3B and 5A/5B for the target `manifest_fingerprint`; seal all artefacts 6A may read.

**Preconditions & gates**  
Layer-3 schemas/dictionaries/registry present; upstream bundles/flags match; identities `{seed, parameter_hash, manifest_fingerprint}` fixed.

**Inputs**  
Upstream gated surfaces (for discovery/authority): merchant/site/zone/edge universes, routing hashes, intensity/arrival surfaces. 6A priors/policies: population/segment, product/account priors, instrument/device/IP taxonomies, fraud-role priors.

**Outputs & identity**  
`s0_gate_receipt_6A` at `data/layer3/6A/s0_gate_receipt/fingerprint={manifest_fingerprint}/`; `sealed_inputs_6A` at `data/layer3/6A/sealed_inputs/fingerprint={manifest_fingerprint}/`.

**RNG**  
None.

**Key invariants**  
Only artefacts in `sealed_inputs_6A` are readable; sealed digest verified by downstream states; upstream PASS enforced (“no PASS -> no read”).

**Downstream consumers**  
S1–S5 must verify receipt/digest; 6B uses it as upstream authority.

---

## S1 - Party base (RNG)
**Purpose & scope**  
Realise the party/customer universe with ids, segments, and geos per `{seed, fingerprint}`.

**Preconditions & gates**  
S0 PASS; population/segment priors sealed.

**Inputs**  
Population/segmentation priors; optional upstream context features (only if listed in `sealed_inputs_6A`).

**Outputs & identity**  
`s1_party_base_6A` at `data/layer3/6A/s1_party_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/` with `party_id`, `party_type`, segments, geos, static attrs. Optional `s1_party_summary_6A`.

**RNG posture**  
Philox streams for counts/attribute sampling (`party_count_realisation`, `party_attribute_sampling`); events/trace logged.

**Key invariants**  
Counts match priors (tolerance); FK domain for later states; deterministic given `(seed, parameter_hash, manifest_fingerprint)` + priors.

**Downstream consumers**  
S2–S5 use parties as FK roots; 6B treats as authority for entities.

---

## S2 - Accounts & product holdings (RNG)
**Purpose & scope**  
Realise accounts/products and attach to parties (and merchants where applicable).

**Preconditions & gates**  
S0, S1 PASS; product/account priors and taxonomies sealed.

**Inputs**  
`s1_party_base_6A`; product/account priors (type mix, accounts-per-party distributions); taxonomies (types, families, currency lists).

**Outputs & identity**  
`s2_account_base_6A` at `data/layer3/6A/s2_account_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/` with account ids, owners, types, currency, static flags.  
`s2_party_product_holdings_6A` (same partitions) plus optional merchant account base/summaries.

**RNG posture**  
Philox streams for counts, allocation, attribute sampling; events/trace logged.

**Key invariants**  
FK coverage to parties (and merchants if present); counts align with priors; no new accounts beyond S2 authority.

**Downstream consumers**  
S3 instruments attach to these accounts; S4 links incorporate accounts; S5 roles reference them.

---

## S3 - Instruments & payment credentials (RNG)
**Purpose & scope**  
Create instruments/credentials and link them to accounts/parties/merchants; set static instrument metadata.

**Preconditions & gates**  
S0–S2 PASS; instrument priors/taxonomies sealed.

**Inputs**  
`s2_account_base_6A`, `s2_party_product_holdings_6A`; instrument priors (counts/mix) and taxonomies.

**Outputs & identity**  
`s3_instrument_base_6A` at `data/layer3/6A/s3_instrument_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/`; `s3_account_instrument_links_6A`; optional holdings/summaries.

**RNG posture**  
Philox streams for counts, allocation, attributes; events/trace logged.

**Key invariants**  
FK coverage to accounts/parties/merchants; counts/attributes align with priors; instruments only created here.

**Downstream consumers**  
S4 links devices/IPs to instruments; S5 roles reference instruments.

---

## S4 - Devices, IPs & static graph (RNG)
**Purpose & scope**  
Realise devices and IP endpoints and build the static entity graph (links across parties/accounts/instruments/merchants).

**Preconditions & gates**  
S0–S3 PASS; device/IP priors/taxonomies sealed.

**Inputs**  
`s1_party_base_6A`, `s2_account_base_6A`, `s3_instrument_base_6A`; device/IP priors for counts/sharing; taxonomies for attributes.

**Outputs & identity**  
`s4_device_base_6A`, `s4_ip_base_6A`, `s4_device_links_6A`, `s4_ip_links_6A` at `seed={seed}/fingerprint={manifest_fingerprint}/`; optional neighbourhood/network summaries.

**RNG posture**  
Philox streams for counts, allocation of links, attribute sampling; events/trace logged.

**Key invariants**  
FK coverage across all links; sharing/degree profiles match priors; graph is deterministic given inputs + priors.

**Downstream consumers**  
S5 fraud roles; 6B uses graph as authority for entities/links.

---

## S5 - Static fraud posture & HashGate
**Purpose & scope**  
Assign static fraud roles to all entities and seal 6A with `validation_bundle_6A` + `_passed.flag`.

**Preconditions & gates**  
S0–S4 PASS; fraud-role priors/policies sealed; upstream gates still verify.

**Inputs**  
`s0_gate_receipt_6A`, `sealed_inputs_6A`; all S1–S4 datasets; fraud-role priors/policies; RNG logs/events/trace.

**Outputs & identity**  
Fraud-role surfaces: `s5_party_fraud_roles_6A`, `s5_account_fraud_roles_6A`, `s5_merchant_fraud_roles_6A`, `s5_device_fraud_roles_6A`, `s5_ip_fraud_roles_6A` (`seed={seed}/fingerprint={manifest_fingerprint}/` except merchants which may be fingerprint-only).  
Validation artefacts: `s5_validation_report_6A`, optional `s5_issue_table_6A`; `validation_bundle_6A` at `data/layer3/6A/validation/fingerprint={manifest_fingerprint}/` with `validation_bundle_index_6A`; `_passed.flag` containing `sha256_hex = <bundle_digest>` over indexed files in ASCII-lex order (flag excluded).

**RNG posture**  
Philox streams for role counts/assignments; events/trace logged; validator is RNG-free.

**Key invariants**  
One role per entity; role distributions match priors (tolerance); cross-entity consistency holds; RNG budgets close; bundle digest matches `_passed.flag`; enforces “no PASS -> no read” for all 6A artefacts.

**Downstream consumers**  
6B must verify `_passed.flag` before using any 6A surface; enterprise consumers do the same.
