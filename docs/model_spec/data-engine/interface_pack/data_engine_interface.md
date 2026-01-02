# Data Engine Black-Box Interface

_Derived from segment registries, dataset dictionaries, schemas, and state-expanded docs._

## Purpose

This document defines the **black-box interface** of the Data Engine: identity, addressing/discovery, authoritative outputs, and readiness gates. It is designed to be depended on by platform components (Scenario Runner, Ingestion, Event Bus, Feature Planes, Labels/Cases, Observability/Governance) without importing engine internal algorithms.

## Identity and determinism

### Identity fields

- `manifest_fingerprint`: world identity (content-address of the sealed world inputs + governed parameter bundle).
- `parameter_hash`: governed parameter bundle identity (policy/config pack).
- `seed`: realisation key for RNG-consuming lanes.
- `scenario_id`: scenario identity (used where scenario overlays apply).
- `run_id`: execution correlation id; **partitions logs/events** but is not allowed to change sealed world outputs for a fixed identity tuple.

### Determinism promise

**Determinism & immutability.** For every output, **identity is defined by its partition tokens** (as declared in `engine_outputs.catalogue.yaml`). For a fixed identity partition, the engine promises **byte-identical** materialisations across re-runs and enforces **write-once / immutable partitions**. `run_id` may partition logs/events, but **MUST NOT** change the bytes of any output whose identity does not include `run_id`.

## Discovery and addressing

Outputs are addressed by **tokenised path templates**. The canonical fingerprint token is:

- `fingerprint={manifest_fingerprint}`

Common partition families:

- **Parameter-scoped**: `parameter_hash={parameter_hash}`
- **Fingerprint-scoped**: `fingerprint={manifest_fingerprint}`
- **Seed+fingerprint egress**: `seed={seed}/fingerprint={manifest_fingerprint}`
- **Run-scoped logs/events**: `seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}` (and/or `scenario_id` where applicable)

The authoritative inventory of outputs (IDs, paths, schemas, join keys) is `engine_outputs.catalogue.yaml`.

## Output taxonomy

- **Surfaces**: structured datasets (parquet/json) used for joins/context ("authority surfaces").
- **Streams**: append-only event/log families (e.g., RNG event streams).
- **Gate artifacts**: validation bundles, `_passed.flag` files, and gate receipts used to enforce readiness (class `gate` in the catalogue).

## Catalogue fields (selected)

- `class`: `surface`, `stream`, or `gate` (gate artifacts are not consumption surfaces).
- `exposure`: `internal` or `external` (external means the schema anchor lives under `/egress/`).
- `scope`: deterministic identity scope derived from partition tokens (examples: `scope_parameter_hash`, `scope_manifest_fingerprint`, `scope_parameter_hash_seed_run_id`, `scope_parameter_hash_manifest_fingerprint_seed_scenario_id`).
- `availability`: `optional` means the engine may omit the output; absence implies required.

## Join semantics

Join keys are defined per surface in the catalogue (primary keys and stable linkage keys). Downstream components MUST NOT infer semantics from physical file row order; only declared keys and authority fields are binding.

## Lineage invariants (binding)

- **Path-embed equality.** Where lineage appears both in a path token and inside rows/fields, values **MUST byte-equal** (for example, `row.manifest_fingerprint == fingerprint`, `row.seed == seed`, `row.parameter_hash == parameter_hash`).
- **File order is non-authoritative.** Consumers MUST treat **partition keys + PK/UK + declared fields** as truth; physical file order conveys no semantics.
- **Atomic publish + immutability.** Outputs are staged and atomically moved into place; once published, an identity partition is immutable (re-publish must be byte-identical or fail).

## HashGates and readiness rulebook

Every segment publishes a **segment-level HashGate**:

- a fingerprint-scoped validation bundle (or bundle index) and
- a fingerprint-scoped `_passed.flag` (or equivalent) whose content/digest is defined by the segment's hashing law.

**No PASS -> no read.** Any consumer (engine segments and platform components) MUST verify the relevant segment gate before treating gated outputs as authoritative.

* **Do not assume a universal hashing method.** Gate verification is **gate-specific**; some segments hash concatenated raw bytes, others hash structured member digests. Consumers MUST follow `engine_gates.map.yaml` for the exact verification procedure.

Operational verification details (paths, hashing law, and gate->output mapping) are defined in `engine_gates.map.yaml`.

## Segment boundary summaries

In the summaries below, "Public (gated) surfaces" means **surfaces a consumer may read after verifying the segment gate**, regardless of whether the catalogue marks them `exposure: internal` or `external`. The catalogue is the source of truth for exposure classification.

### LAYER1 - 1A
- S0: S0.1 - Universe, Symbols, Authority (normative, fixed)
- Gate: `gate.layer1.1A.validation` (see `engine_gates.map.yaml`)
- Upstream gates required: _(none)_
- Public (gated) surfaces:
  - `outlet_catalogue`  (PK: merchant_id, legal_country_iso, site_order)  -> `data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/`

### LAYER1 - 1B
- S0: 1B - State S0 ("Gate-in & Foundations")
- Gate: `gate.layer1.1B.validation` (see `engine_gates.map.yaml`)
- Upstream gates required: `gate.layer1.1A.validation`
- Public (gated) surfaces:
  - `site_locations`  (PK: merchant_id, legal_country_iso, site_order)  -> `data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}/`

### LAYER1 - 2A
- S0: State 2A.S0 - Gate, Manifest & Sealed Inputs
- Gate: `gate.layer1.2A.validation` (see `engine_gates.map.yaml`)
- Upstream gates required: `gate.layer1.1B.validation`
- Public (gated) surfaces:
  - `site_timezones`  (PK: merchant_id, legal_country_iso, site_order)  -> `data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/`

### LAYER1 - 2B
- S0: State 2B.S0 - Gate & Environment Seal
- Gate: `gate.layer1.2B.validation` (see `engine_gates.map.yaml`)
- Upstream gates required: `gate.layer1.1B.validation`, `gate.layer1.2A.validation`
- Public (gated) surfaces:
  - `s1_site_weights` -> `data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest_fingerprint}/`
  - `s2_alias_index` -> `data/layer1/2B/s2_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/index.json`
  - `s2_alias_blob` -> `data/layer1/2B/s2_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/alias.bin`
  - `s3_day_effects` -> `data/layer1/2B/s3_day_effects/seed={seed}/fingerprint={manifest_fingerprint}/`
  - `s4_group_weights` -> `data/layer1/2B/s4_group_weights/seed={seed}/fingerprint={manifest_fingerprint}/`
  - *(plus receipts/policies/audit surfaces; see catalogue for full list)*

### LAYER1 - 3A
- S0: State 3A-S0 - Gate & Sealed Inputs for Zone Allocation
- Gate: `gate.layer1.3A.validation` (see `engine_gates.map.yaml`)
- Upstream gates required: `gate.layer1.1A.validation`, `gate.layer1.1B.validation`, `gate.layer1.2A.validation`
- Public (gated) surfaces:
  - `s1_escalation_queue`  (PK: merchant_id, legal_country_iso)  -> `data/layer1/3A/s1_escalation_queue/seed={seed}/fingerprint={manifest_fingerprint}/`
  - `s3_zone_shares`  (PK: merchant_id, legal_country_iso, tzid)  -> `data/layer1/3A/s3_zone_shares/seed={seed}/fingerprint={manifest_fingerprint}/`
  - `s4_zone_counts`  (PK: merchant_id, legal_country_iso, tzid)  -> `data/layer1/3A/s4_zone_counts/seed={seed}/fingerprint={manifest_fingerprint}/`
  - `s6_issue_table_3A`  (PK: severity, issue_code, merchant_id, legal_country_iso, tzid)  -> `data/layer1/3A/s6_issues/fingerprint={manifest_fingerprint}/issues.parquet`
  - `s6_receipt_3A`  (PK: -)  -> `data/layer1/3A/s6_receipt/fingerprint={manifest_fingerprint}/s6_receipt.json`
  - `s6_validation_report_3A`  (PK: -)  -> `data/layer1/3A/s6_validation_report/fingerprint={manifest_fingerprint}/report.json`
  - `sealed_inputs_3A`  (PK: owner_segment, artefact_kind, logical_id)  -> `data/layer1/3A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3A.parquet`
  - `zone_alloc`  (PK: merchant_id, legal_country_iso, tzid)  -> `data/layer1/3A/zone_alloc/seed={seed}/fingerprint={manifest_fingerprint}/`
  - `zone_alloc_universe_hash`  (PK: -)  -> `data/layer1/3A/zone_universe/fingerprint={manifest_fingerprint}/zone_alloc_universe_hash.json`

### LAYER1 - 3B
- S0: 3B.S0 - Gate & environment seal
- Gate: `gate.layer1.3B.validation` (see `engine_gates.map.yaml`)
- Upstream gates required: `gate.layer1.1A.validation`, `gate.layer1.1B.validation`, `gate.layer1.2A.validation`, `gate.layer1.2B.validation`, `gate.layer1.3A.validation`
- Public (gated) surfaces:
  - `edge_alias_blob_3B`  (PK: -)  -> `data/layer1/3B/edge_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_blob_3B.bin`
  - `edge_alias_index_3B`  (PK: scope, merchant_id)  -> `data/layer1/3B/edge_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/edge_alias_index_3B.parquet`
  - `edge_catalogue_3B`  (PK: merchant_id, edge_id)  -> `data/layer1/3B/edge_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/`
  - `edge_catalogue_index_3B`  (PK: scope, merchant_id)  -> `data/layer1/3B/edge_catalogue_index/seed={seed}/fingerprint={manifest_fingerprint}/edge_catalogue_index_3B.parquet`
  - `edge_universe_hash_3B`  (PK: -)  -> `data/layer1/3B/edge_universe_hash/fingerprint={manifest_fingerprint}/edge_universe_hash_3B.json`
  - `gamma_draw_log_3B`  (PK: merchant_id, day_index)  -> `logs/layer1/3B/gamma_draw/seed={seed}/fingerprint={manifest_fingerprint}/gamma_draw_log_3B.jsonl`
  - `s4_run_summary_3B`  (PK: -)  -> `data/layer1/3B/s4_run_summary/fingerprint={manifest_fingerprint}/s4_run_summary_3B.json`
  - `s5_manifest_3B`  (PK: -)  -> `data/layer1/3B/validation/fingerprint={manifest_fingerprint}/s5_manifest_3B.json`
  - `sealed_inputs_3B`  (PK: owner_segment, artefact_kind, logical_id, path)  -> `data/layer1/3B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3B.parquet`
  - `virtual_classification_3B`  (PK: merchant_id)  -> `data/layer1/3B/virtual_classification/seed={seed}/fingerprint={manifest_fingerprint}/`
  - `virtual_routing_policy_3B`  (PK: -)  -> `data/layer1/3B/virtual_routing_policy/fingerprint={manifest_fingerprint}/virtual_routing_policy_3B.json`
  - `virtual_settlement_3B`  (PK: merchant_id)  -> `data/layer1/3B/virtual_settlement/seed={seed}/fingerprint={manifest_fingerprint}/`
  - `virtual_validation_contract_3B`  (PK: test_id)  -> `data/layer1/3B/virtual_validation_contract/fingerprint={manifest_fingerprint}/virtual_validation_contract_3B.parquet`

### LAYER2 - 5A
- S0: 5A.S0 - Gate & sealed inputs (Layer-2 / Segment 5A)
- Gate: `gate.layer2.5A.validation` (see `engine_gates.map.yaml`)
- Upstream gates required: `gate.layer1.1A.validation`, `gate.layer1.1B.validation`, `gate.layer1.2A.validation`, `gate.layer1.2B.validation`, `gate.layer1.3A.validation`, `gate.layer1.3B.validation`
- Public (gated) surfaces:
  - `class_zone_baseline_local_5A`  (PK: demand_class, legal_country_iso, tzid, bucket_index)  -> `data/layer2/5A/class_zone_baseline_local/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/class_zone_baseline_local_5A.parquet`
  - `merchant_class_profile_5A`  (PK: merchant_id)  -> `data/layer2/5A/merchant_class_profile/fingerprint={manifest_fingerprint}/merchant_class_profile_5A.parquet`
  - `merchant_zone_baseline_local_5A`  (PK: merchant_id, legal_country_iso, tzid, bucket_index)  -> `data/layer2/5A/merchant_zone_baseline_local/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/merchant_zone_baseline_local_5A.parquet`
  - `merchant_zone_baseline_utc_5A`  (PK: merchant_id, legal_country_iso, tzid, utc_bucket_index)  -> `data/layer2/5A/merchant_zone_baseline_utc/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/merchant_zone_baseline_utc_5A.parquet`
  - `merchant_zone_overlay_factors_5A`  (PK: merchant_id, legal_country_iso, tzid, local_horizon_bucket_index)  -> `data/layer2/5A/merchant_zone_overlay_factors/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/merchant_zone_overlay_factors_5A.parquet`
  - `merchant_zone_profile_5A`  (PK: merchant_id, legal_country_iso, tzid)  -> `data/layer2/5A/merchant_zone_profile/fingerprint={manifest_fingerprint}/merchant_zone_profile_5A.parquet`
  - `merchant_zone_scenario_local_5A`  (PK: merchant_id, legal_country_iso, tzid, local_horizon_bucket_index)  -> `data/layer2/5A/merchant_zone_scenario_local/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/merchant_zone_scenario_local_5A.parquet`
  - `merchant_zone_scenario_utc_5A`  (PK: merchant_id, legal_country_iso, tzid, utc_horizon_bucket_index)  -> `data/layer2/5A/merchant_zone_scenario_utc/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/merchant_zone_scenario_utc_5A.parquet`
  - `scenario_manifest_5A`  (PK: -)  -> `data/layer2/5A/scenario_manifest/fingerprint={manifest_fingerprint}/scenario_manifest_5A.parquet`
  - `sealed_inputs_5A`  (PK: -)  -> `data/layer2/5A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5A.parquet`
  - `validation_issue_table_5A`  (PK: -)  -> `data/layer2/5A/validation/fingerprint={manifest_fingerprint}/issues/validation_issue_table_5A.parquet`
  - `validation_report_5A`  (PK: -)  -> `data/layer2/5A/validation/fingerprint={manifest_fingerprint}/reports/validation_report_5A.json`

### LAYER2 - 5B
- S0: 5B.S0 - Gate & sealed inputs (Layer-2 / Segment 5B)
- Gate: `gate.layer2.5B.validation` (see `engine_gates.map.yaml`)
- Upstream gates required: `gate.layer1.1A.validation`, `gate.layer1.1B.validation`, `gate.layer1.2A.validation`, `gate.layer1.2B.validation`, `gate.layer1.3A.validation`, `gate.layer1.3B.validation`, `gate.layer2.5A.validation`
- Public (gated) surfaces:
  - `arrival_events_5B`  (PK: scenario_id, merchant_id, ts_utc, arrival_seq)  -> `data/layer2/5B/arrival_events/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/part-*.parquet`
  - `s1_grouping_5B`  (PK: scenario_id, merchant_id, zone_representation, channel_group)  -> `data/layer2/5B/s1_grouping/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s1_grouping_5B.parquet`
  - `s1_time_grid_5B`  (PK: scenario_id, bucket_index)  -> `data/layer2/5B/s1_time_grid/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s1_time_grid_5B.parquet`
  - `s2_latent_field_5B`  (PK: scenario_id, group_id, bucket_index)  -> `data/layer2/5B/s2_latent_field/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s2_latent_field_5B.parquet`
  - `s2_realised_intensity_5B`  (PK: scenario_id, merchant_id, zone_representation, channel_group, bucket_index)  -> `data/layer2/5B/s2_realised_intensity/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s2_realised_intensity_5B.parquet`
  - `s3_bucket_counts_5B`  (PK: scenario_id, merchant_id, zone_representation, channel_group, bucket_index)  -> `data/layer2/5B/s3_bucket_counts/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s3_bucket_counts_5B.parquet`
  - `s4_arrival_anomalies_5B`  (PK: scenario_id, anomaly_id)  -> `data/layer2/5B/arrival_anomalies/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s4_arrival_anomalies_5B.parquet`
  - `s4_arrival_summary_5B`  (PK: scenario_id, merchant_id, zone_representation, bucket_index)  -> `data/layer2/5B/arrival_summary/seed={seed}/fingerprint={manifest_fingerprint}/scenario_id={scenario_id}/s4_arrival_summary_5B.parquet`
  - `sealed_inputs_5B`  (PK: owner_segment, artifact_id, role)  -> `data/layer2/5B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5B.parquet`
  - `validation_issue_table_5B`  (PK: -)  -> `data/layer2/5B/validation/fingerprint={manifest_fingerprint}/validation_issue_table_5B.parquet`
  - `validation_report_5B`  (PK: -)  -> `data/layer2/5B/validation/fingerprint={manifest_fingerprint}/validation_report_5B.json`

### LAYER3 - 6A
- S0: 6A.S0 - Gate & sealed inputs for the entity & product world (Layer-3 / Segment 6A)
- Gate: `gate.layer3.6A.validation` (see `engine_gates.map.yaml`)
- Upstream gates required: `gate.layer1.1A.validation`, `gate.layer1.1B.validation`, `gate.layer1.2A.validation`, `gate.layer1.2B.validation`, `gate.layer1.3A.validation`, `gate.layer1.3B.validation`, `gate.layer2.5A.validation`, `gate.layer2.5B.validation`
- Public (gated) surfaces:
  - `s1_party_base_6A`  (PK: country_iso, segment_id, party_type, party_id)  -> `data/layer3/6A/s1_party_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s1_party_base_6A.parquet`
  - `s1_party_summary_6A`  (PK: country_iso, segment_id, party_type)  -> `data/layer3/6A/s1_party_summary_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s1_party_summary_6A.parquet`
  - `s2_account_base_6A`  (PK: country_iso, account_type, owner_party_id, account_id)  -> `data/layer3/6A/s2_account_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s2_account_base_6A.parquet`
  - `s2_account_summary_6A`  (PK: country_iso, segment_id, account_type)  -> `data/layer3/6A/s2_account_summary_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s2_account_summary_6A.parquet`
  - `s2_merchant_account_base_6A`  (PK: owner_merchant_id, account_type, account_id)  -> `data/layer3/6A/s2_merchant_account_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s2_merchant_account_base_6A.parquet`
  - `s2_party_product_holdings_6A`  (PK: party_id, account_type)  -> `data/layer3/6A/s2_party_product_holdings_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s2_party_product_holdings_6A.parquet`
  - `s3_account_instrument_links_6A`  (PK: account_id, instrument_type, scheme, instrument_id)  -> `data/layer3/6A/s3_account_instrument_links_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s3_account_instrument_links_6A.parquet`
  - `s3_instrument_base_6A`  (PK: account_id, instrument_type, scheme, instrument_id)  -> `data/layer3/6A/s3_instrument_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s3_instrument_base_6A.parquet`
  - `s3_instrument_summary_6A`  (PK: region_id, segment_id, account_type, instrument_type, scheme)  -> `data/layer3/6A/s3_instrument_summary_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s3_instrument_summary_6A.parquet`
  - `s3_party_instrument_holdings_6A`  (PK: party_id, instrument_type, scheme)  -> `data/layer3/6A/s3_party_instrument_holdings_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s3_party_instrument_holdings_6A.parquet`
  - `s4_device_base_6A`  (PK: device_type, primary_party_id, primary_merchant_id, device_id)  -> `data/layer3/6A/s4_device_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s4_device_base_6A.parquet`
  - `s4_device_links_6A`  (PK: device_id, party_id, account_id, instrument_id, merchant_id, link_role)  -> `data/layer3/6A/s4_device_links_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s4_device_links_6A.parquet`
  - `s4_entity_neighbourhoods_6A`  (PK: entity_type, entity_id)  -> `data/layer3/6A/s4_entity_neighbourhoods_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s4_entity_neighbourhoods_6A.parquet`
  - `s4_ip_base_6A`  (PK: ip_type, asn_class, country_iso, ip_id)  -> `data/layer3/6A/s4_ip_base_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s4_ip_base_6A.parquet`
  - `s4_ip_links_6A`  (PK: ip_id, device_id, party_id, merchant_id, link_role)  -> `data/layer3/6A/s4_ip_links_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s4_ip_links_6A.parquet`
  - `s4_network_summary_6A`  (PK: region_id, segment_id, account_type, metric_id)  -> `data/layer3/6A/s4_network_summary_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s4_network_summary_6A.parquet`
  - `s5_account_fraud_roles_6A`  (PK: account_id)  -> `data/layer3/6A/s5_account_fraud_roles_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s5_account_fraud_roles_6A.parquet`
  - `s5_device_fraud_roles_6A`  (PK: device_id)  -> `data/layer3/6A/s5_device_fraud_roles_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s5_device_fraud_roles_6A.parquet`
  - `s5_ip_fraud_roles_6A`  (PK: ip_id)  -> `data/layer3/6A/s5_ip_fraud_roles_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s5_ip_fraud_roles_6A.parquet`
  - `s5_issue_table_6A`  (PK: check_id, scope_type, issue_id)  -> `data/layer3/6A/validation/fingerprint={manifest_fingerprint}/s5_issue_table_6A.parquet`
  - `s5_merchant_fraud_roles_6A`  (PK: merchant_id)  -> `data/layer3/6A/s5_merchant_fraud_roles_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s5_merchant_fraud_roles_6A.parquet`
  - `s5_party_fraud_roles_6A`  (PK: party_id)  -> `data/layer3/6A/s5_party_fraud_roles_6A/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s5_party_fraud_roles_6A.parquet`
  - `s5_validation_report_6A`  (PK: -)  -> `data/layer3/6A/validation/fingerprint={manifest_fingerprint}/s5_validation_report_6A.json`
  - `sealed_inputs_6A`  (PK: owner_layer, owner_segment, manifest_key)  -> `data/layer3/6A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6A.parquet`

### LAYER3 - 6B
- S0: 6B.S0 - Behavioural universe gate & sealed inputs (Layer-3 / Segment 6B)
- Gate: `gate.layer3.6B.validation` (see `engine_gates.map.yaml`)
- Upstream gates required: `gate.layer1.1A.validation`, `gate.layer1.1B.validation`, `gate.layer1.2A.validation`, `gate.layer1.2B.validation`, `gate.layer1.3A.validation`, `gate.layer1.3B.validation`, `gate.layer2.5A.validation`, `gate.layer2.5B.validation`, `gate.layer3.6A.validation`
- Public (gated) surfaces:
  - `s1_arrival_entities_6B`  (PK: seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq)  -> `data/layer3/6B/s1_arrival_entities_6B/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/scenario_id={scenario_id}/part-*.parquet`
  - `s1_session_index_6B`  (PK: seed, manifest_fingerprint, scenario_id, session_id)  -> `data/layer3/6B/s1_session_index_6B/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/scenario_id={scenario_id}/part-*.parquet`
  - `s2_event_stream_baseline_6B`  (PK: seed, manifest_fingerprint, scenario_id, flow_id, event_seq)  -> `data/layer3/6B/s2_event_stream_baseline_6B/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/scenario_id={scenario_id}/part-*.parquet`
  - `s2_flow_anchor_baseline_6B`  (PK: seed, manifest_fingerprint, scenario_id, flow_id)  -> `data/layer3/6B/s2_flow_anchor_baseline_6B/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/scenario_id={scenario_id}/part-*.parquet`
  - `s3_campaign_catalogue_6B`  (PK: campaign_id)  -> `data/layer3/6B/s3_campaign_catalogue_6B/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/scenario_id={scenario_id}/s3_campaign_catalogue_6B.parquet`
  - `s3_event_stream_with_fraud_6B`  (PK: seed, manifest_fingerprint, scenario_id, flow_id, event_seq)  -> `data/layer3/6B/s3_event_stream_with_fraud_6B/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/scenario_id={scenario_id}/part-*.parquet`
  - `s3_flow_anchor_with_fraud_6B`  (PK: seed, manifest_fingerprint, scenario_id, flow_id)  -> `data/layer3/6B/s3_flow_anchor_with_fraud_6B/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/scenario_id={scenario_id}/part-*.parquet`
  - `s4_case_timeline_6B`  (PK: case_id, case_event_seq)  -> `data/layer3/6B/s4_case_timeline_6B/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/scenario_id={scenario_id}/part-*.parquet`
  - `s4_event_labels_6B`  (PK: seed, manifest_fingerprint, scenario_id, flow_id, event_seq)  -> `data/layer3/6B/s4_event_labels_6B/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/scenario_id={scenario_id}/part-*.parquet`
  - `s4_flow_bank_view_6B`  (PK: seed, manifest_fingerprint, scenario_id, flow_id)  -> `data/layer3/6B/s4_flow_bank_view_6B/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/scenario_id={scenario_id}/part-*.parquet`
  - `s4_flow_truth_labels_6B`  (PK: seed, manifest_fingerprint, scenario_id, flow_id)  -> `data/layer3/6B/s4_flow_truth_labels_6B/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/scenario_id={scenario_id}/part-*.parquet`
  - `s5_issue_table_6B`  (PK: manifest_fingerprint, check_id, issue_id)  -> `data/layer3/6B/validation/fingerprint={manifest_fingerprint}/s5_issue_table_6B.parquet`
  - `s5_validation_report_6B`  (PK: -)  -> `data/layer3/6B/validation/fingerprint={manifest_fingerprint}/s5_validation_report_6B.json`
  - `sealed_inputs_6B`  (PK: owner_layer, owner_segment, manifest_key)  -> `data/layer3/6B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_6B.parquet`
