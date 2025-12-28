```
        LAYER 1 · SEGMENT 3B — STATE S4 (VIRTUAL ROUTING SEMANTICS & VALIDATION CONTRACTS)  [NO RNG]

Authoritative inputs (read-only at S4 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_3B
      @ data/layer1/3B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3B.json
      · sole authority for:
          - identity triple {seed, parameter_hash, manifest_fingerprint},
          - upstream gates for 1A, 1B, 2A, 3A (all MUST be PASS for S4 to run),
          - which versions of schemas/dicts/registries are in force,
          - which artefacts are sealed via sealed_inputs_3B.
    - sealed_inputs_3B
      @ data/layer1/3B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3B.parquet
      · whitelist of all **external** artefacts 3B is allowed to read.
      · Any external artefact S4 uses MUST:
          - appear as a row in sealed_inputs_3B (by logical_id / owner_segment),
          - be resolved via dictionary+registry,
          - match sealed_inputs_3B.sha256_hex (if S4 recomputes it).

[Schema+Dict & routing-field contracts]
    - schemas.layer1.yaml
        · Layer-1 numeric policy profile (binary64, RNE, no FMA/FTZ/DAZ),
        · Layer-1 RNG profile (for compatibility; S4 itself is RNG-free).
    - schemas.3B.yaml
        · anchors for:
            - plan/virtual_classification_3B, plan/virtual_settlement_3B,
            - plan/edge_catalogue_3B, plan/edge_catalogue_index_3B,
            - egress/virtual_routing_policy_3B,
            - egress/virtual_validation_contract_3B,
            - validation/edge_universe_hash_3B,
            - validation/virtual_validation_policy_3B (policy pack).
    - schemas.2B.yaml / routing-field contracts (via sealed inputs)
        · define the **event schema** 2B uses for routing,
        · provide schema anchors for:
              - event fields holding settlement vs operational TZ,
              - event fields holding IP geo (country, lat, lon) and any other virtual-test fields.
    - dataset_dictionary.layer1.3B.yaml
        · IDs→{path, partitioning, schema_ref} for:
              virtual_classification_3B,
              virtual_settlement_3B,
              edge_catalogue_3B,
              edge_catalogue_index_3B,
              edge_alias_blob_3B,
              edge_alias_index_3B,
              edge_universe_hash_3B,
              virtual_routing_policy_3B,
              virtual_validation_contract_3B.
    - artefact_registry_3B.yaml
        · ownership, manifest_keys, roles for all of the above.

[Inputs from 3B.S1 — virtual semantics]
    - virtual_classification_3B
      @ seed={seed} / fingerprint={manifest_fingerprint}
      · authoritative classification of merchants as virtual vs non-virtual.
      · S4 uses:
          - the virtual merchant set V,
          - classification flags, rule reasons for documentation / overrides.
      · S4 MUST NOT re-run classification rules or change is_virtual flags.

    - virtual_settlement_3B
      @ seed={seed} / fingerprint={manifest_fingerprint}
      · one settlement node per **virtual** merchant:
            merchant_id,
            settlement_site_id,
            settlement_lat_deg, settlement_lon_deg,
            tzid_settlement, tz_source,
            coordination provenance.
      · S4 uses:
          - tzid_settlement as the “settlement clock” anchor,
          - settlement_site_id as the “legal seat” anchor.
      · S4 MUST NOT move settlement nodes or change tzid_settlement/tz_source.

[Inputs from 3B.S2 — edge semantics]
    - edge_catalogue_3B
      @ seed={seed} / fingerprint={manifest_fingerprint}
      · per-edge node records:
            merchant_id, edge_id,
            country_iso,
            lat_deg, lon_deg,
            tzid_operational, tz_source,
            edge_weight, spatial/RNG provenance.
      · S4 uses:
          - operational geography & tzid_operational,
          - country/edge distributions in documentation/validation hooks.
      · S4 MUST NOT add/remove edges or change any S2 fields.

    - edge_catalogue_index_3B
      @ seed={seed} / fingerprint={manifest_fingerprint}
      · summarises per-merchant/global edge counts & digests.
      · S4 uses:
          - edge_count_summary for documentation or validation references.
      · S4 MUST NOT re-derive edge universe or override any digest.

[Inputs from 3B.S3 — alias & edge-universe hash]
    - edge_alias_blob_3B
    - edge_alias_index_3B
    - edge_universe_hash_3B
      · produced by 3B.S3 and sealed via sealed_inputs_3B.
      · S4 uses:
          - layout_version,
          - blob/index manifest_keys and paths,
          - `edge_universe_hash_3B.universe_hash` as the **virtual edge universe hash**,
          - digests for documentation.
      · S4 MUST NOT:
          - modify alias tables,
          - re-define layout semantics,
          - compute a new edge universe hash that overrides S3.

[Validation-policy & routing/RNG policy inputs]
    - virtual_validation_policy_3B (policy pack)
        · sealed policy defining:
            - test types (IP-country mix, clock/cutoff tests, edge-usage tests, etc.),
            - parameterisation of each test (per merchant/cohort/global),
            - thresholds and PASS/WARN/FAIL semantics,
            - target population expressions (virtual-only, per-class, etc.).
        · S4 MUST NOT invent tests outside this policy.

    - routing/RNG policy artefact(s) (shared with 2B)
        · sealed artefact(s) defining:
            - which RNG stream/substream 2B MUST use for:
                  - virtual edge selection (`cdn_edge_pick`),
                  - virtual vs physical routing switches,
            - which alias layout versions are supported by 2B,
            - event schemas for RNG events (routing event contracts).
        · S4 uses this ONLY to:
            - bind virtual routing policy to the correct RNG stream/label,
            - assert alias_layout_version compatibility.
        · S4 MUST NOT change RNG policy or allocate new streams.

[Feature flags & configuration modes]
    - 3B configuration bundle (part of parameter_hash) with flags like:
        · enable_virtual_routing / disable_virtual_routing,
        · virtual_validation_profile ∈ {strict, relaxed, off},
        · per-merchant hybrid modes (if design uses them).
    - S4 MUST:
        · read these from a governed, sealed config (as per 2.5),
        · obey semantics for each flag/mode,
        · treat missing required artefacts in enabled modes as a **hard failure**.

[Outputs owned by S4 (RNG-free, fingerprint-scoped)]
    - virtual_routing_policy_3B
      @ data/layer1/3B/virtual_routing_policy/fingerprint={manifest_fingerprint}/virtual_routing_policy_3B.json
      · partition_keys: ["fingerprint"]
      · schema_ref: schemas.3B.yaml#/egress/virtual_routing_policy_3B
      · single JSON document per manifest; defines:
            identity & provenance,
            dual-timezone semantics,
            geo field bindings,
            artefact references (edge_catalogue_index, alias blob/index, edge_universe_hash),
            RNG/alias binding for virtual routing,
            per-merchant overrides (optional).

    - virtual_validation_contract_3B
      @ data/layer1/3B/virtual_validation_contract/fingerprint={manifest_fingerprint}/virtual_validation_contract_3B.parquet
      · partition_keys: ["fingerprint"]
      · schema_ref: schemas.3B.yaml#/egress/virtual_validation_contract_3B
      · table with rows per test configuration:
            test_id, test_type, scope, target_population, inputs, thresholds, severity, enabled, notes.

    - (optional) s4_run_summary_3B
      @ data/layer1/3B/s4_run_summary/fingerprint={manifest_fingerprint}/s4_run_summary_3B.json
      · non-authoritative run-summary (counts, IDs, high-level status).

[Numeric & RNG posture]
    - RNG:
        · S4 is **strictly RNG-free**:
            - MUST NOT open/advance Philox,
            - MUST NOT emit RNG events or alter RNG logs.
    - Determinism:
        · Given fixed {seed, parameter_hash, manifest_fingerprint},
          S0–S3 outputs, sealed policies, and catalogue, S4 MUST produce byte-identical outputs.
    - Time:
        · If created_at_utc is present in outputs, it MUST be provided by the engine/harness or treated as
          non-authoritative; S4 MUST NOT call `now()` itself.
    - Immutability:
        · For a fixed identity triple, virtual_routing_policy_3B and virtual_validation_contract_3B are
          logically immutable; any non-identical re-run MUST fail with a conflict error.


----------------------------------------------------------------------
DAG — 3B.S4 (S1–S3 semantics + policy packs → routing & validation contracts)  [NO RNG]

### Phase A — Environment & identity (RNG-free)

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S4.1) Load S0 artefacts & fix identity
                    - Resolve:
                        · s0_gate_receipt_3B@fingerprint={manifest_fingerprint},
                        · sealed_inputs_3B@fingerprint={manifest_fingerprint},
                      via dataset_dictionary.layer1.3B.yaml.
                    - Validate:
                        · s0_gate_receipt_3B schema-valid,
                        · sealed_inputs_3B schema-valid.
                    - Check identity:
                        · receipt.manifest_fingerprint == manifest_fingerprint (path token),
                        · (if present) receipt.parameter_hash == parameter_hash, receipt.seed == seed.
                    - Require upstream gates:
                        · 1A/1B/2A/3A status == "PASS".
                      On any failure: S4 MUST fail and emit no outputs.

sealed_inputs_3B,
[Schema+Dict]
                ->  (S4.2) Resolve S1–S3 artefacts and 3B policies
                    - Using sealed_inputs_3B + dictionary/registry, resolve:
                        · virtual_classification_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · virtual_settlement_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · edge_catalogue_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · edge_catalogue_index_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · edge_alias_blob_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · edge_alias_index_3B@seed={seed}/fingerprint={manifest_fingerprint},
                        · edge_universe_hash_3B@fingerprint={manifest_fingerprint},
                        · virtual_validation_policy_3B (policy pack),
                        · routing/RNG policy artefact(s) for virtual routing (shared with 2B),
                        · event schema / routing-field contracts.
                    - For each **external** artefact (policy, event schema, etc.):
                        · find sealed_inputs_3B row by logical_id,
                        · resolve path, recompute SHA256(raw bytes),
                        · assert equality with sealed_inputs_3B.sha256_hex.
                    - Validate shapes against declared schema_ref anchors.

### Phase B — Cross-check S1–S3 surfaces (RNG-free)

virtual_classification_3B,
virtual_settlement_3B
                ->  (S4.3) Derive virtual merchant set & settlement coverage
                    - Derive virtual set:
                        · M_all = set of merchants in virtual_classification_3B,
                        · V      = { m | classification/is_virtual(m) = "VIRTUAL" }.
                    - Check settlement coverage:
                        · virtual_settlement_3B must have exactly one row per m ∈ V,
                        · no rows for non-virtual merchants.
                    - On mismatch:
                        · S4 MUST treat this as a cross-state contract violation and fail, not repair data.

edge_catalogue_3B,
edge_catalogue_index_3B,
virtual_classification_3B
                ->  (S4.4) Sanity-check edge universe vis-à-vis virtual merchants
                    - S4 MAY (and SHOULD) check:
                        · all merchants present in edge_catalogue_3B are virtual (∈ V),
                        · edge_catalogue_index_3B MERCHANT rows line up with V,
                        · edge counts per merchant match between catalogue and index.
                    - On inconsistency:
                        · S4 MUST fail; **it MUST NOT** add/remove edges or reclassify merchants.

edge_alias_blob_3B,
edge_alias_index_3B,
edge_universe_hash_3B,
alias-layout policy
                ->  (S4.5) Alias layout & edge-universe hash compatibility
                    - Read edge_alias_blob_3B header:
                        · layout_version, endianness, alignment_bytes, blob_sha256_hex,
                          alias_layout_policy_id/version, universe_hash (from S3).
                    - Read edge_alias_index_3B GLOBAL row(s):
                        · blob_sha256_hex, edge_catalogue_digest_global, universe_hash (if present).
                    - Read edge_universe_hash_3B:
                        · {cdn_weights_digest, edge_catalogue_index_digest, edge_alias_index_digest,
                           virtual_rules_digest, universe_hash}.
                    - Load alias-layout policy via sealed_inputs_3B:
                        · require layout_version, alignment_bytes, etc. match what S3 used.
                    - S4 MUST:
                        · treat universe_hash from edge_universe_hash_3B as **authoritative**,
                        · ensure alias blob/index references match this universe,
                        · NOT recompute or override the universe hash.
                    - Any mismatch in layout_version/universe_hash ⇒ config error; S4 MUST fail.

### Phase C — Feature flags & mode selection (RNG-free)

3B configuration bundle (feature flags),
virtual_validation_policy_3B
                ->  (S4.6) Interpret feature flags / modes
                    - Read feature flags from governed config sealed by S0, e.g.:
                        · enable_virtual_routing / disable_virtual_routing,
                        · virtual_validation_profile ∈ {strict, relaxed, off},
                        · any hybrid routing modes (if design uses them).
                    - S4 MUST:
                        · treat flags as part of the parameter set contributing to parameter_hash,
                        · decide:
                              - whether to emit a full routing policy,
                              - whether to emit a non-routing/no-op contract,
                              - whether to emit non-empty validation tests,
                          according to the design documented in the 3B spec.
                    - If flags require additional artefacts (e.g. profile-specific policies) that are not sealed:
                        · S4 MUST treat this as a hard configuration error and fail.

### Phase D — Build virtual routing policy (RNG-free)

virtual_classification_3B,
virtual_settlement_3B,
edge_catalogue_index_3B,
edge_universe_hash_3B,
routing/RNG policy,
event schema / routing-field contracts
                ->  (S4.7) Construct `virtual_routing_policy_3B` logical object
                    - Identity & provenance section:
                        · manifest_fingerprint = current manifest_fingerprint,
                        · parameter_hash       = current parameter_hash,
                        · edge_universe_hash   = edge_universe_hash_3B.universe_hash,
                        · routing_policy_id/version  from sealed routing/RNG policy artefact,
                        · virtual_validation_policy_id/version from sealed virtual validation policy pack,
                        · cdn_key_digest            (digest of CDN weights artefact, if schema requires),
                        · alias_layout_version      (from alias-layout policy / alias blob header).
                    - Dual-TZ semantics:
                        · `dual_timezone_semantics` object:
                              - settlement_timezone_field:
                                    schema anchor/path for event field carrying settlement TZ / settlement-day info,
                              - operational_timezone_field:
                                    schema anchor/path for event field carrying operational TZ / local time,
                              - settlement_day_definition / operational_day_definition:
                                    descriptions or anchors for how days are derived from those TZ fields.
                    - Geo field bindings:
                        · `geo_field_bindings` object:
                              - ip_country_field, ip_latitude_field, ip_longitude_field:
                                    event schema anchors,
                              - upstream_sources for those fields:
                                    e.g. { source: "EDGE", dataset_id: "edge_catalogue_3B" } vs "SETTLEMENT" vs "PHYSICAL".
                    - Artefact references:
                        · `artefact_paths` object:
                              - edge_catalogue_index_manifest_key,
                              - edge_alias_blob_manifest_key,
                              - edge_alias_index_manifest_key,
                              - edge_universe_hash_manifest_key,
                            echoing manifest_keys from dictionary/registry.
                    - RNG & alias bindings:
                        · `virtual_edge_rng_binding` object:
                              - module, substream_label, event_schema,
                                that 2B MUST use for `cdn_edge_pick` (virtual),
                              - any constraints on mixing virtual vs physical streams.
                        · `alias_layout_version` MUST equal layout_version in S3 alias header.
                    - Per-merchant overrides (optional):
                        · `overrides[]` array of {merchant_id, mode, notes}, where:
                              - mode describes hybrid behaviour or “disable virtual” for that merchant,
                              - semantics MUST be defined in S4 spec and routing policy.
                    - Notes:
                        · optional human-readable guidance, not semantics.

virtual_routing_policy_3B logical object,
[Schema+Dict]
                ->  (S4.8) Validate and prepare to write `virtual_routing_policy_3B`
                    - Validate object against schemas.3B.yaml#/egress/virtual_routing_policy_3B:
                        · required identity/provenance fields present,
                        · dual_timezone_semantics and geo_field_bindings conform to schema,
                        · artefact_paths and RNG binding fields present and well-typed.
                    - Determine target path via dictionary:
                        · data/layer1/3B/virtual_routing_policy/fingerprint={manifest_fingerprint}/virtual_routing_policy_3B.json.
                    - Check for existing file:
                        · if absent → ready to write,
                        · if present:
                              - load existing JSON, normalise representation,
                              - compare logical content to new object:
                                    * if identical → idempotent re-run; OK,
                                    * if different → immutability violation; S4 MUST fail.

### Phase E — Build virtual validation contract (RNG-free)

virtual_validation_policy_3B,
event schema / routing-field contracts,
virtual_classification_3B (target populations)
                ->  (S4.9) Expand virtual validation policy into per-test rows
                    - Parse virtual_validation_policy_3B as the **only source** of test types and thresholds.
                    - For each configured test in the policy:
                        · derive:
                              test_id        (stable, unique per manifest),
                              test_type      (e.g. "IP_COUNTRY_MIX", "SETTLEMENT_CUTOFF", "EDGE_USAGE_VS_WEIGHT"),
                              scope          ("GLOBAL", "PER_MERCHANT", "PER_CLASS", "PER_SCENARIO"),
                              target_population:
                                    expressions referencing classification (virtual-only, per brand, per cohort, etc.).
                        · inputs object:
                              - datasets: list of dataset IDs / manifest_keys (e.g. arrivals, decisions, labels),
                              - fields:   schema anchors into event schema (e.g. ip_country_field, settlement_day_field).
                        · thresholds object:
                              - metrics (e.g. max_abs_diff, max_rel_diff, KL_divergence, coverage_ratio),
                              - PASS/WARN/FAIL thresholds as per policy.
                        · severity:
                              - enum { "BLOCKING", "WARNING", "INFO" } from policy.
                        · enabled flag and any profile association:
                              - e.g. profile ∈ { "strict", "relaxed", "off" }.
                        - S4 MUST NOT invent new tests or thresholds beyond what policy defines.
                    - Collect all tests into an in-memory table of rows for `virtual_validation_contract_3B`.

validation rows,
[Schema+Dict]
                ->  (S4.10) Validate and prepare to write `virtual_validation_contract_3B`
                    - Validate table against schemas.3B.yaml#/egress/virtual_validation_contract_3B:
                        · required columns present: test_id, test_type, scope, inputs, thresholds, severity, enabled,
                        · partition_keys=["fingerprint"], sort_keys=["test_id"].
                    - Sort rows by test_id ASC (canonical ordering).
                    - Determine target path via dictionary:
                        · data/layer1/3B/virtual_validation_contract/fingerprint={manifest_fingerprint}/virtual_validation_contract_3B.parquet.
                    - Check existing dataset:
                        · if absent → ready to write,
                        · if present:
                              - load existing rows, normalise to same schema+sort,
                              - if byte-identical → idempotent re-run; OK,
                              - else → immutability violation; S4 MUST fail.

### Phase F — Write outputs atomically & (optional) run summary

virtual_routing_policy_3B JSON,
virtual_validation_contract_3B table
                ->  (S4.11) Atomically write S4 outputs (per fingerprint)
                    - S4 MUST publish `virtual_routing_policy_3B` and `virtual_validation_contract_3B` atomically:
                        · it MUST NOT leave a state where one exists and the other does not for a fingerprint.
                    - Write steps:
                        1. Write `virtual_routing_policy_3B` JSON to a staging file,
                           fsync, then atomic rename into final path.
                        2. Write `virtual_validation_contract_3B` Parquet to a staging directory,
                           fsync, then atomic rename into final path.
                    - On re-execution:
                        · if both outputs exist and match the recomputed logical content → OK (idempotent),
                        · if either differs or only one exists → immutability/atomicity violation; S4 MUST fail.

(optional) run summary data
                ->  (S4.12) Emit optional s4_run_summary_3B (non-authoritative)
                    - Build summary object with:
                        · manifest_fingerprint, parameter_hash,
                        · counts:
                              - |V| = number of virtual merchants in scope,
                              - merchants covered by routing semantics (should equal |V| unless feature flags disable),
                              - number of tests emitted in virtual_validation_contract_3B,
                        · IDs/versions:
                              - routing_policy_id/version,
                              - virtual_validation_policy_id/version.
                    - Validate against schemas.3B.yaml#/egress/s4_run_summary_3B (if defined).
                    - Write to:
                        · data/layer1/3B/s4_run_summary/fingerprint={manifest_fingerprint}/s4_run_summary_3B.json,
                      using the same immutability/idempotence rules as other S4 outputs.
                    - Downstream components MUST treat this as informational only (non-binding).

Downstream touchpoints
----------------------
- **3B.S5 — 3B validation bundle & `_passed.flag`:**
    - MUST treat `virtual_routing_policy_3B` and `virtual_validation_contract_3B` as:
          - the **only** sources of virtual routing semantics and virtual test contracts for this manifest.
    - S5 re-bundles these with S0–S3 artefacts and RNG evidence into `validation_bundle_3B`.

- **2B (routing engine):**
    - MUST obey `virtual_routing_policy_3B` when:
          - mapping settlement vs operational TZ fields,
          - picking RNG streams/substreams for virtual edge selection,
          - binding event fields to edge geometry.
    - MUST ensure 3B’s HashGate (bundle + `_passed.flag`) is PASS before using 3B virtual artefacts
      (**No 3B PASS → No read / use**).

- **Validation harness (virtual flows):**
    - MUST use `virtual_validation_contract_3B` as the test manifest:
          - tests to run,
          - fields/datasets to use,
          - thresholds and severity.
    - MUST NOT introduce ad-hoc tests or change thresholds without updating the validation policy + S4 spec/schema.
```