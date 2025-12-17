```
        LAYER 1 · SEGMENT 3B — STATE S1 (VIRTUAL CLASSIFICATION & SETTLEMENT NODE)  [NO RNG]

Authoritative inputs (read-only at S1 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_3B
      @ data/layer1/3B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3B.json
      · sole authority for:
          - identity triple {seed, parameter_hash, manifest_fingerprint},
          - upstream gates (1A, 1B, 2A, 3A) PASS status,
          - catalogue_versions for schemas.3B.yaml, dataset_dictionary.layer1.3B.yaml, artefact_registry_3B.yaml.
      · S1 MUST NOT re-verify upstream bundles directly; it trusts S0.

    - sealed_inputs_3B
      @ data/layer1/3B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3B.parquet
      · whitelist of all external artefacts 3B is allowed to read for this manifest.
      · Any external artefact S1 reads MUST:
          - appear as a row in sealed_inputs_3B,
          - match on {logical_id, path, schema_ref},
          - have matching sha256_hex (S1 MUST recompute).

[Schema+Dict]
    - schemas.layer1.yaml
        · core types (hex64, uint64, iso2, iana_tzid, rfc3339_micros),
        · numeric policy profile (binary64, RNE, no FMA/FTZ/DAZ).
    - schemas.3B.yaml
        · anchors for:
            - policy/virtual_classification_rules,
            - plan/virtual_classification_3B,
            - plan/virtual_settlement_3B.
    - schemas.ingress.layer1.yaml
    - dataset_dictionary.layer1.3B.yaml
        · IDs, paths, partitions, schema_refs for S0–S5 artefacts.
    - artefact_registry_3B.yaml
        · manifest_keys and roles for:
            - mcc_channel_rules (virtual rules),
            - virtual_settlement_coords,
            - hrsl_raster, pelias_cached_sqlite, civil_time_manifest, etc.

[Merchant reference (from upstream segments)]
    - Merchant reference dataset (logical_id resolved via sealed_inputs_3B)
        · universe M of merchants (same as 1A’s canonical merchant universe).
        · MUST include, at minimum, attributes required by the classification policy, e.g.:
            - merchant_id,
            - mcc,
            - channel,
            - home_country_iso,
            - legal_country_iso,
            - optional brand_id, group_id, flags, etc.
        · S1 MUST:
            - load this via dictionary+sealed_inputs_3B,
            - check PK uniqueness on merchant_id (or documented key),
            - treat its rows as the only source of merchant attributes.

[Virtual classification policy]
    - mcc_channel_rules (virtual-classification rules)
        · config/virtual/mcc_channel_rules.yaml (logical_id resolved via sealed_inputs_3B).
        · schema_ref: schemas.3B.yaml#/policy/virtual_classification_rules.
        · defines:
            - overrides (allow/deny lists keyed by merchant_id/brand_id),
            - rule ladder (MCC/channel/country predicates) with priorities,
            - default behaviour if no rule fires.
        · S1 MUST treat this artefact as the **only authority** on virtual vs non-virtual logic.

[Settlement coordinate sources & tz assets]
    - virtual_settlement_coords
        · artefacts/virtual/virtual_settlement_coords.* (schema-free but governed via spec).
        · records of the form:
              - merchant_key (merchant_id and/or brand_id or other key),
              - latitude, longitude (CRS declared),
              - optional tzid_settlement,
              - evidence / jurisdiction / provenance fields.
        · S1 uses this to pick a single settlement row per virtual merchant.

    - civil_time_manifest / tz assets
        · sealed tz-world polygons + tzdb archive + overrides (consumed indirectly via civil_time_manifest).
        · used when tzid_settlement is NOT provided in virtual_settlement_coords.

[Outputs owned by S1]
    - virtual_classification_3B
      @ data/layer1/3B/virtual_classification/seed={seed}/fingerprint={manifest_fingerprint}/…
      · partition_keys: [seed, fingerprint]
      · primary_key: [merchant_id]
      · sort_keys:  [merchant_id]
      · schema_ref: schemas.3B.yaml#/plan/virtual_classification_3B
      · contains:
            merchant_id,
            is_virtual (or classification enum),
            decision_reason (closed vocab),
            source_policy_id, source_policy_version,
            optional rule-level provenance (rule_id, rule_group, etc.).

    - virtual_settlement_3B
      @ data/layer1/3B/virtual_settlement/seed={seed}/fingerprint={manifest_fingerprint}/…
      · partition_keys: [seed, fingerprint]
      · primary_key: [merchant_id]
      · sort_keys:  [merchant_id]
      · schema_ref: schemas.3B.yaml#/plan/virtual_settlement_3B
      · one row per VIRTUAL merchant, with:
            merchant_id,
            settlement_site_id (new id64, disjoint from 1B site_id space),
            settlement_lat_deg, settlement_lon_deg (WGS84),
            tzid_settlement (IANA tzid),
            tz_source (enum: INGESTED / POLYGON / OVERRIDE),
            coord_source_id, coord_source_version,
            evidence_ref / jurisdiction (where defined).

[Numeric & RNG posture]
    - S1 is strictly **RNG-free**:
        · MUST NOT call Philox or any RNG,
        · MUST NOT emit RNG events or touch rng_trace_log / rng_audit_log.
    - Deterministic:
        · All behaviour MUST be a pure function of:
              {seed, parameter_hash, manifest_fingerprint},
              sealed_inputs_3B,
              merchant reference contents.
        · Given unchanged inputs, S1 MUST produce byte-identical outputs.
    - Time:
        · MUST NOT use wall-clock time or environment-dependent values in outputs.


----------------------------------------------------------------------
DAG — 3B.S1 (Virtual classification + settlement node)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S1.1) Environment & contracts
                    - Resolve and validate:
                        · s0_gate_receipt_3B@fingerprint={manifest_fingerprint},
                        · sealed_inputs_3B@fingerprint={manifest_fingerprint},
                      via Layer-1 dictionary.
                    - From s0_gate_receipt_3B:
                        · fix {seed, parameter_hash, manifest_fingerprint},
                        · require upstream_gates.segment_{1A,1B,2A,3A}.status == "PASS",
                        · record catalogue_versions for schemas/dict/registry.
                    - Confirm numeric profile and RNG profile match schemas.layer1.yaml.
                    - S1 MUST NOT attempt to re-verify upstream validation bundles itself.

[Schema+Dict],
sealed_inputs_3B
                ->  (S1.2) Resolve external artefacts via sealed_inputs_3B
                    - For each required external artefact:
                        · merchant reference dataset,
                        · mcc_channel_rules,
                        · virtual_settlement_coords,
                        · civil_time_manifest/tz assets,
                        · pelias_cached_sqlite (if used for evidence URLs),
                      S1 MUST:
                        1. Locate a matching row in sealed_inputs_3B by logical_id.
                        2. Resolve path + schema_ref via dataset_dictionary + artefact_registry.
                        3. Recompute SHA-256(raw bytes) and assert equality with sealed_inputs_3B.sha256_hex.
                    - If any artefact is missing or digest mismatched:
                        · S1 MUST treat this as input integrity failure and MUST NOT proceed.

[Merchant reference dataset],
[Schema+Dict]
                ->  (S1.3) Build merchant universe M & context ctx(m)
                    - Load merchant reference dataset via its schema anchor.
                    - Determine merchant key:
                        · default: `merchant_id` (as declared in the reference schema).
                        · validate uniqueness: exactly one row per merchant_id; duplicates ⇒ data-quality error.
                    - Define:
                        · M = set of all merchant_id in reference.
                    - For each merchant_id ∈ M, build `ctx(m)`:
                        · raw fields required by policy:
                              mcc, channel, home_country_iso, legal_country_iso, etc.
                        · any deterministic derived features the policy depends on:
                              e.g. mcc buckets, channel families, regions, “has_physical_outlets” flag,
                              computed via pure, side-effect-free functions.
                    - S1 MUST NOT pull outlet- or site-level data here (site_catalogue is a separate sealed artefact for S2/S3).

[mcc_channel_rules],
ctx(m) for all m ∈ M
                ->  (S1.4) Evaluate virtual classification policy
                    - Load `mcc_channel_rules` and validate against schemas.3B.yaml#/policy/virtual_classification_rules.
                    - For each merchant m ∈ M:
                        1. Apply hard deny/allow overrides (if present):
                               - allow override ⇒ classification(m)="VIRTUAL",
                               - deny override  ⇒ classification(m)="NON_VIRTUAL".
                        2. If no override applies:
                               - evaluate rule ladder in strict order:
                                      · descending rule_priority,
                                      · then ascending rule_id (ASCII-lex).
                               - when a rule’s predicate(ctx(m)) is true:
                                      - apply its action:
                                            SET_VIRTUAL, SET_NON_VIRTUAL, or NO-OP.
                               - obey any global constraints configured in the policy (e.g. “must have at least 1 outlet to be virtual”).
                        3. If no rule fires:
                               - apply configured default (e.g. default_non_virtual).
                        4. If conflicting instructions (e.g. both allow and deny) occur:
                               - treat as classification error for m; do not silently pick one.
                    - For each merchant m:
                        · compute:
                              classification(m) ∈ {"VIRTUAL","NON_VIRTUAL"},
                              decision_reason(m) ∈ closed enum (which rule/override/default was used),
                              optional provenance: rule_id, rule_group, priority bucket.
                    - Define:
                        · is_virtual(m) = 1 if classification(m)="VIRTUAL", else 0.
                        · V = { m ∈ M | is_virtual(m)=1 }.

ctx(m), classification(m), decision_reason(m)
                ->  (S1.5) Stage rows for virtual_classification_3B
                    - For each merchant m ∈ M, stage a row:
                        · merchant_id        = m,
                        · classification / is_virtual,
                        · decision_reason,
                        · source_policy_id     = policy identifier from mcc_channel_rules,
                        · source_policy_version= policy version from mcc_channel_rules,
                        · optional provenance fields (rule_id, rule_group, etc.).
                    - Domain:
                        · exactly one row for each merchant_id ∈ M,
                        · no merchant may be silently dropped; errors must be surfaced if a row cannot be classified.

V (set of virtual merchants),
virtual_settlement_coords,
[Schema+Dict]
                ->  (S1.6) Load settlement coordinates & map to merchants
                    - Load `virtual_settlement_coords` dataset(s) as per artefact_registry_3B.
                    - Determine join key for coordinates:
                        · if coords keyed by merchant_id:
                              k(m) = merchant_id,
                        · else if keyed by brand_id or other key:
                              - derive k(m) from ctx(m) using policy-defined mapping
                                (documented in S1 spec; deterministic).
                    - For each m ∈ V:
                        · collect candidate rows C(m) = all rows in virtual_settlement_coords matching k(m).
                        · If C(m) = ∅:
                              - handle according to spec (e.g. error, or fallback to another sealed coord source).
                        · If |C(m)| > 1:
                              - apply deterministic tie-break:
                                    * define tie-break key tb(row) (e.g. priority, timestamp, evidence_rank, then path),
                                    * sort C(m) by tb(row) lex order,
                                    * choose first row as c*(m).
                    - For each chosen c*(m), extract:
                        · settlement_lat, settlement_lon (in declared CRS),
                        · any provenance fields required downstream (evidence_ref, jurisdiction, coord_source_id/version).

c*(m) for m ∈ V,
civil_time_manifest / tz assets
                ->  (S1.7) Resolve settlement tzid_settlement & tz_source
                    - If c*(m) already contains an authoritative tzid_settlement field:
                        · validate:
                              - non-null, conforms to iana_tzid,
                              - optionally check (lat,lon) is compatible with tz via tz polygons.
                        · set:
                              tzid_settlement(m) = that field,
                              tz_source(m)       = "INGESTED".
                    - Else:
                        · use sealed tz-world polygons + tzdb archive (as in 2A) to resolve tz:
                              1. Pass (settlement_lat_deg, settlement_lon_deg) and applicable overrides
                                 into the Layer-1 civil-time resolver.
                              2. Apply overrides in fixed precedence (site ≻ merchant ≻ country) if configured.
                              3. If no tzid can be found (point outside polygons, etc.),
                                 treat as coverage failure; either:
                                     - abort S1, or
                                     - apply a documented fallback (if spec allows).
                        · set:
                              tzid_settlement(m) = resolved tzid,
                              tz_source(m)       = "POLYGON" or "OVERRIDE" as appropriate.
                    - tz_source MUST be one of a closed enum declared in schemas.3B.yaml (e.g. {"INGESTED","POLYGON","OVERRIDE"}).

merchant_id m ∈ V
                ->  (S1.8) Construct settlement_site_id for each virtual merchant
                    - S1 MUST construct settlement_site_id deterministically from merchant_id, e.g.:
                        · key_bytes = UTF8("3B.SETTLEMENT") || 0x1F || UTF8(merchant_id),
                        · digest    = SHA256(key_bytes) (32 bytes),
                        · settlement_site_id_u64 = LOW64(digest),
                        · settlement_site_id = encode settlement_site_id_u64 as 16-char zero-padded lower-case hex.
                    - Constraints:
                        · settlement_site_id is typed as id64/hex64,
                        · MUST be globally unique with extremely high probability,
                        · MUST NOT collide with 1A/1B physical `site_id` space (by format/type).

V, settlement_site_id(m), settlement_lat/lon(m), tzid_settlement(m), tz_source(m),
coord source/provenance
                ->  (S1.9) Stage rows for virtual_settlement_3B
                    - For each m ∈ V (virtual merchants):
                        · stage a row:
                              merchant_id          = m,
                              settlement_site_id   = settlement_site_id(m),
                              settlement_lat_deg   = settlement_lat(m) converted to WGS84 degrees,
                              settlement_lon_deg   = settlement_lon(m) converted to WGS84 degrees,
                              tzid_settlement      = tzid_settlement(m),
                              tz_source            = tz_source(m),
                              coord_source_id      = id of virtual_settlement_coords artefact (or equivalent),
                              coord_source_version = version from sealed_inputs_3B,
                              evidence_ref         = evidence field from c*(m) if available,
                              jurisdiction         = jurisdiction field from c*(m) if available.
                    - Domain:
                        · one row per virtual merchant (m ∈ V),
                        · no row for non-virtual merchants.

staged virtual_classification_3B rows,
[Schema+Dict]
                ->  (S1.10) Validate & write virtual_classification_3B (write-once)
                    - Target path (via dictionary):
                        · data/layer1/3B/virtual_classification/seed={seed}/fingerprint={manifest_fingerprint}/…
                    - Sort staged rows by merchant_id ASC.
                    - Validate table against schemas.3B.yaml#/plan/virtual_classification_3B.
                    - Immutability:
                        · if partition is empty → write via staging → fsync → atomic move.
                        · if partition exists:
                              - load existing dataset, normalise schema + sort,
                              - compare to new rows:
                                    - if byte-identical → idempotent re-run; OK,
                                    - else → immutability violation; S1 MUST NOT overwrite.

staged virtual_settlement_3B rows,
[Schema+Dict]
                ->  (S1.11) Validate & write virtual_settlement_3B (write-once)
                    - Target path (via dictionary):
                        · data/layer1/3B/virtual_settlement/seed={seed}/fingerprint={manifest_fingerprint}/…
                    - Sort staged rows by merchant_id ASC.
                    - Validate table against schemas.3B.yaml#/plan/virtual_settlement_3B.
                    - Immutability:
                        · if partition is empty → write via staging → fsync → atomic move.
                        · if partition exists:
                              - load existing dataset, normalise,
                              - if byte-identical → idempotent re-run; OK,
                              - else → immutability violation; MUST NOT overwrite.

Downstream touchpoints
----------------------
- **3B.S2 (CDN edge catalogue construction):**
    - MUST treat `virtual_classification_3B` as the sole authority on which merchants are virtual vs non-virtual
      for this manifest.
    - MUST treat `virtual_settlement_3B` as the sole source of:
          - settlement_site_id,
          - settlement coordinate (lat/lon),
          - settlement tzid and tz_source,
          for virtual merchants.

- **3B.S3 & 3B.S4 (alias & routing/validation contracts):**
    - MUST NOT re-run classification rules or re-resolve settlement coordinates/timezones.
    - MUST use only S1’s outputs when they need to know:
          - the virtual merchant universe V,
          - how to tie virtual edges back to a legal settlement anchor.

- **3B.S5 (validation bundle & flag) and external validation tooling:**
    - MAY read `virtual_classification_3B` and `virtual_settlement_3B` to:
          - verify classification vs rules,
          - check settlement provenance and tz semantics,
      but MUST NOT treat those datasets as mutable; they are write-once, RNG-free sources of truth for virtual merchants.
```