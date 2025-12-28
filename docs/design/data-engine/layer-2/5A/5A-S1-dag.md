```
        LAYER 2 · SEGMENT 5A — STATE S1 (MERCHANT×ZONE DEMAND CLASS & SCALE)  [NO RNG]

Authoritative inputs (read-only at S1 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_5A
      @ data/layer2/5A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_5A.json
      · provides:
          - manifest_fingerprint, parameter_hash, run_id for this world,
          - verified_upstream_segments:{1A,1B,2A,2B,3A,3B} → "PASS"|"FAIL"|"MISSING",
          - sealed_inputs_digest,
          - scenario_id / scenario_pack_id in scope for this run.
      · S1 MUST trust:
          - upstream status from this document,
          - sealed_inputs_digest as the canonical fingerprint of 5A’s input universe.
      · S1 MUST NOT re-walk upstream bundles directly to re-verify them.

    - sealed_inputs_5A
      @ data/layer2/5A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_5A.parquet
      · describes the **entire** artefact universe that S1 may touch:
          - for each artefact: owner_layer, owner_segment, artifact_id, manifest_key,
            path_template, partition_keys[], schema_ref, sha256_hex, role, status, read_scope.
      · Authority rules:
          - if an artefact is not listed in sealed_inputs_5A, it is out-of-bounds even if present on disk;
          - S1 MUST honour `read_scope`:
                · ROW_LEVEL → may read data rows,
                · METADATA_ONLY → may inspect only metadata (e.g. IDs, digests, policy versions).

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml, schemas.layer2.yaml, schemas.5A.yaml
    - dataset_dictionary.layer1.*    (for 1A–3B surfaces such as merchant ref, zone_alloc, site_timezones, 3B flags)
    - dataset_dictionary.layer2.5A.yaml
        · includes:
            - merchant_zone_profile_5A
              · path: data/layer2/5A/merchant_zone_profile/fingerprint={manifest_fingerprint}/merchant_zone_profile_5A.parquet
              · partitioning: [fingerprint]
              · primary_key: [merchant_id, legal_country_iso, tzid]
              · ordering:    [merchant_id, legal_country_iso, tzid]
              · schema_ref:  schemas.5A.yaml#/model/merchant_zone_profile_5A
            - merchant_class_profile_5A (optional)
    - artefact_registry_{1A–3B,5A}.yaml
        · used to resolve logical IDs, roles, and schema_refs.

[Layer-1 world surfaces S1 may read]  (all must be listed in sealed_inputs_5A)
    - Merchant reference / attribute table(s)
        · provides:
            - merchant_id (PK),
            - legal_country_iso (home/primary country),
            - mcc / mcc_group,
            - channel (POS, ecomm, mixed, …),
            - optional size/segment attributes (turnover_bucket, outlet_count_bucket, brand_group_id, etc.).
        · S1’s use:
            - define merchant universe M,
            - attach merchant features to (merchant, zone).

    - Zone allocation from 3A (`zone_alloc`)
        · defines zone domain per merchant:
            - for each (merchant_id, legal_country_iso, tzid):
                  zone_site_count (integer ≥ 0),
                  zone_site_count_sum (total outlets in that country),
                  site_count (total outlets for that merchant in that country),
            - optional zone-level attributes from 3A.
        · S1’s use:
            - define zone domain Z per merchant,
            - derive features like outlet_count_in_zone, outlet_fraction_in_zone, zones_per_merchant.

    - Civil-time surfaces (optional)
        · `site_timezones` and/or 3A’s zone surfaces:
            - used only to derive high-level features, e.g. “cross-timezone merchant”.
        · Authority:
            - tzid at site-level is canonical in site_timezones,
            - any civil-time features MUST be derived from these, not from raw lat/lon.

    - Virtual vs physical flags (optional)
        · `virtual_classification_3B` / `virtual_settlement_3B`:
            - used only to mark virtual merchants and attach virtual/physical flags to features.
        · Authority:
            - S1 MUST NOT reclassify merchants differently from 3B;
              it may only treat “virtual vs non-virtual” as an input feature.

[5A policies & configs]
    - merchant_class_policy_5A  (classing policy)
        · deterministic rules mapping features → demand_class (and optional subclass/profile_id).
        · may depend on MCC, channel, size buckets, country, virtual flag, zones_per_merchant, etc.

    - demand_scale_policy_5A    (scale policy)
        · deterministic rules mapping (features, demand_class, scenario_id) → base scale parameters, e.g.:
            - weekly_volume_expected (expected arrivals per local week),
            - or a dimensionless scale factor,
            - plus flags like "high_variability", "low_volume_tail".
        · MUST produce finite, non-negative values.

    - scenario metadata/configs
        · scenario_id, scenario_type (baseline vs stress, etc.),
        · scenario-level knobs that class/scale policies may use.

[Outputs owned by S1]
    - merchant_zone_profile_5A  (required)
      @ data/layer2/5A/merchant_zone_profile/fingerprint={manifest_fingerprint}/merchant_zone_profile_5A.parquet
      · partition_keys: [fingerprint]
      · primary_key:    [merchant_id, legal_country_iso, tzid]
      · ordering:       [merchant_id, legal_country_iso, tzid]
      · schema_ref:     schemas.5A.yaml#/model/merchant_zone_profile_5A
      · one row per in-scope (merchant, zone) with, at minimum:
            merchant_id,
            legal_country_iso,
            tzid,
            demand_class,
            base_scale (e.g. weekly_volume_expected or scale_factor),
            scale_unit / scale_semantics,
            any additional scale flags,
            class_source / policy_version,
            scale_source / policy_version.

    - merchant_class_profile_5A (optional, derived)
      @ data/layer2/5A/merchant_class_profile/fingerprint={manifest_fingerprint}/merchant_class_profile_5A.parquet
      · partition_keys: [fingerprint]
      · primary_key:    [merchant_id, demand_class]
      · derived entirely by grouping/summing over merchant_zone_profile_5A.

[Numeric & RNG posture]
    - S1 is **RNG-free**:
        · MUST NOT use Philox or any RNG,
        · MUST NOT call `now()` to drive decisions.
    - Determinism:
        · For fixed (parameter_hash, manifest_fingerprint, run_id) and fixed sealed_inputs_5A,
          5A policies, and Layer-1 inputs, S1 MUST produce byte-identical outputs.
    - Identity:
        · Outputs are fingerprint-partitioned only; no seed/parameter_hash partitions.
        · S1 MUST NOT invent new identity dimensions beyond (merchant_id, legal_country_iso, tzid).


----------------------------------------------------------------------
DAG — 5A.S1 (Layer-1 world + 5A policies → merchant×zone demand profile)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S1.1) Load S0 gate & fix identity
                    - Resolve via 5A dictionary:
                        · s0_gate_receipt_5A@fingerprint={manifest_fingerprint},
                        · sealed_inputs_5A@fingerprint={manifest_fingerprint}.
                    - Validate both against schemas.5A.yaml.
                    - From receipt:
                        · fix parameter_hash, manifest_fingerprint, run_id, scenario_id,
                        · record verified_upstream_segments{1A–3B,2B,3A,3B}.
                    - Require:
                        · all upstream segments that 5A depends on are status="PASS" (as documented in S1 spec).
                    - From sealed_inputs_5A:
                        · recompute SHA-256 over the sealed_inputs_5A rows in canonical order,
                        · assert it equals `sealed_inputs_digest` in s0_gate_receipt_5A.
                    - On any failure, S1 MUST fail and MUST NOT emit outputs.

sealed_inputs_5A,
[Schema+Dict]
                ->  (S1.2) Resolve allowed inputs via catalogue (no ad-hoc paths)
                    - For each logical input S1 needs:
                        · merchant reference / attributes,
                        · zone_alloc (or equivalent zone domain surface from 3A),
                        · optional world surfaces:
                              - site_timezones,
                              - virtual_classification_3B / virtual_settlement_3B (if policies use virtual flags),
                        · 5A policies/configs:
                              - merchant_class_policy_5A,
                              - demand_scale_policy_5A,
                              - scenario config pack,
                      S1 MUST:
                        1. Locate a row in sealed_inputs_5A with matching {owner_layer, owner_segment, artifact_id}.
                        2. Resolve {path_template, partition_keys, schema_ref} via dictionary+registry.
                        3. Substitute partition tokens for this (manifest_fingerprint, parameter_hash, scenario_id) where applicable.
                        4. Recompute SHA-256 over raw bytes of the resolved artefact and assert equality with sealed_inputs_5A.sha256_hex.
                    - Respect `read_scope`:
                        · if artefact has read_scope = METADATA_ONLY → do not read rows, only metadata if policy needs it.
                        · if ROW_LEVEL → rows may be read as needed.
                    - If a REQUIRED artefact is missing or hash mismatched:
                        · S1 MUST fail early.

merchant reference table(s)
                ->  (S1.3) Build merchant universe M and attach merchant-level features
                    - From merchant reference tables (resolved in S1.2):
                        · identify primary key (`merchant_id`) and required columns:
                              legal_country_iso, mcc/mcc_group, channel, any size/segment fields.
                    - Construct merchant universe:
                        · M = set of distinct merchant_id in reference.
                    - Validate:
                        · no duplicate merchant_id rows,
                        · required attributes non-null where policy demands them.
                    - Build feature record `feat_merchant(m)` per merchant m ∈ M:
                        · raw features:
                              mcc, channel, legal_country_iso,
                              size/segment fields, brand_group_id, etc.
                        · derived features (policy-defined):
                              e.g. mcc_bucket, channel_group, size_bucket, country_bucket.

zone_alloc (from 3A),
[Schema+Dict]
                ->  (S1.4) Build zone universe per merchant: D_zone and base zone features
                    - From zone_alloc (zone-level allocation from 3A) for this fingerprint:
                        · for each row: (merchant_id, legal_country_iso, tzid, zone_site_count, zone_site_count_sum, site_count, …).
                    - Define domain:
                        · D_zone = { (m,c,z) | at least one row in zone_alloc with (merchant_id=m, legal_country_iso=c, tzid=z) }.
                    - Validate:
                        · site_count and zone_site_count_sum consistent per (m,c) as documented in 3A,
                        · no malformed (merchant_id, country, tzid) combinations.
                    - For each (m,c,z) in D_zone, construct base zone features `feat_zone(m,c,z)`:
                        · zone_site_count(m,c,z),
                        · site_count(m,c),
                        · zone_fraction(m,c,z) = zone_site_count / site_count (if site_count>0, else 0),
                        · zones_per_merchant(m) = number of distinct z with (m,c,z) across all c.

optional site_timezones / virtual flags,
feat_merchant(m),
feat_zone(m,c,z)
                ->  (S1.5) Extend features with civil-time & virtual flags (optional)
                    - If policies reference civil-time or virtual status:
                        · derive merchant-level features, e.g.:
                              - cross_timezone_flag(m) (multiple tzids in site_timezones),
                              - primary_tzid(m),
                              - is_virtual(m) from virtual_classification_3B.
                    - Extend `feat_merchant(m)` and `feat_zone(m,c,z)` with these flags.
                    - Authority boundaries:
                        · S1 MUST NOT override 3B.virtual_classification_3B,
                        · MUST NOT recompute tzid from lat/lon; only via canonical 2A/3A surfaces.

feat_merchant(m),
feat_zone(m,c,z),
merchant_class_policy_5A,
scenario_id / scenario_type
                ->  (S1.6) Apply classing policy: features → demand_class
                    - Load and validate merchant_class_policy_5A (ruleset).
                    - For each (m,c,z) ∈ D_zone:
                        · build a classification feature vector X(m,c,z) combining:
                              feat_merchant(m),
                              feat_zone(m,c,z),
                              scenario metadata (if classing depends on scenario type).
                        · Apply the policy’s deterministic decision logic:
                              demand_class(m,c,z) = f_class(X(m,c,z)).
                    - Requirements:
                        · Every (m,c,z) in domain D_zone MUST receive exactly one demand_class.
                        · No overlapping classes or “no decision” outcomes; missing class is a hard error.
                        · Class labels MUST be drawn from the finite set declared in the classing policy/schema.

X(m,c,z),
demand_class(m,c,z),
demand_scale_policy_5A
                ->  (S1.7) Apply scale policy: features+class → base_scale parameters
                    - Load and validate demand_scale_policy_5A.
                    - For each (m,c,z) in D_zone:
                        · construct scale feature vector:
                              Y(m,c,z) = {X(m,c,z), demand_class(m,c,z), scenario_id / scenario_type}.
                        · Compute base scale parameters:
                              scale_params(m,c,z) = f_scale(Y(m,c,z)),
                          e.g.:
                              - weekly_volume_expected(m,c,z),
                              - or scale_factor(m,c,z),
                              - plus flags like high_variability_flag(m,c,z), low_volume_tail_flag(m,c,z).
                    - Requirements:
                        · All numeric scale parameters MUST be finite and ≥ 0.
                        · Scale semantics MUST be consistent with the schema
                          (either “expected arrivals per week” or “relative scale”),
                          and S1 MUST set a `scale_unit` field accordingly.

demand_class(m,c,z),
scale_params(m,c,z)
                ->  (S1.8) Assemble merchant_zone_profile_5A rows
                    - For each (m,c,z) in D_zone:
                        · assemble a row:
                              merchant_id        = m,
                              legal_country_iso  = c,
                              tzid               = z,
                              demand_class       = demand_class(m,c,z),
                              base_scale         = chosen primary scale parameter (e.g. weekly_volume_expected),
                              scale_unit         = "weekly_expected_arrivals" | "relative_scale" | …,
                              scale_flags        = any flags (high_variability, low_volume_tail),
                              class_source       = merchant_class_policy_5A.id/version,
                              scale_source       = demand_scale_policy_5A.id/version,
                              scenario_id        = scenario_id from S0 (if included by schema),
                              manifest_fingerprint = manifest_fingerprint.
                    - Domain & uniqueness:
                        · there MUST be exactly one row per (merchant_id, legal_country_iso, tzid) in D_zone,
                        · S1 MUST NOT emit rows for keys not present in zone_alloc.
                    - Writer ordering:
                        · sort rows by [merchant_id, legal_country_iso, tzid] before writing.

[merchant_zone_profile_5A rows],
[Schema+Dict]
                ->  (S1.9) Validate & write merchant_zone_profile_5A (write-once, fingerprint partition)
                    - Validate rows against schemas.5A.yaml#/model/merchant_zone_profile_5A:
                        · required fields present and well-typed,
                        · PK uniqueness (merchant_id, legal_country_iso, tzid),
                        · partition_keys consistent with dictionary (fingerprint only).
                    - Target path via dictionary:
                        · data/layer2/5A/merchant_zone_profile/fingerprint={manifest_fingerprint}/merchant_zone_profile_5A.parquet
                    - Immutability:
                        · if no dataset exists:
                              - write via staging → fsync → atomic move.
                        · if dataset exists:
                              - read existing rows, normalise schema + sort,
                              - if byte-identical → idempotent re-run; OK,
                              - else → `S1_OUTPUT_CONFLICT`; MUST NOT overwrite.

[merchant_zone_profile_5A],
[Schema+Dict]
                ->  (S1.10) Optionally build and write merchant_class_profile_5A
                    - If `merchant_class_profile_5A` is enabled in dictionary/registry:
                        · derive it purely from merchant_zone_profile_5A:
                              - group rows by (merchant_id, demand_class),
                              - aggregate scale fields according to schema
                                (e.g. sum of weekly_volume_expected across zones per class).
                        - Validate against schemas.5A.yaml#/model/merchant_class_profile_5A.
                        - Target path via dictionary:
                              data/layer2/5A/merchant_class_profile/fingerprint={manifest_fingerprint}/merchant_class_profile_5A.parquet
                        - Apply same immutability/idempotence rules as for merchant_zone_profile_5A.
                    - If not configured, S1 MAY skip this dataset entirely.

Downstream touchpoints
----------------------
- **5A.S2 (weekly shape library):**
    - Uses `merchant_zone_profile_5A` to:
          - know which demand_class×zone combinations actually exist,
          - derive which shapes need to be defined.
    - MUST treat `demand_class` from S1 as the only authority; it MUST NOT re-class merchants/zones.

- **5A.S3 (baseline intensities):**
    - MUST use `merchant_zone_profile_5A` as the source of base_scale parameters.
    - MUST NOT re-implement class/scale policies; simply combines base_scale with S2 shapes.

- **5A.S4 (scenario overlays):**
    - Uses class/scale information (and scenario_id) from S1 to interpret overlays,
      but MUST NOT change S1’s base classifications or base scales.

- **5A.S5 (validation):**
    - Replays all S1 invariants:
          - domain = zone_alloc domain,
          - one demand_class per (merchant,zone),
          - base_scale bounded and non-negative,
          - merchant_class_profile_5A (if present) is consistent with merchant_zone_profile_5A.

- **Layer-wide consumers (5B, 6A):**
    - MUST read class and base scale **only** from merchant_zone_profile_5A for this fingerprint.
    - MUST honour the 5A HashGate from S5 (bundle + `_passed.flag`) before treating S1 outputs as authoritative:
          **No 5A PASS → No read/use** of 5A intensities downstream.
```