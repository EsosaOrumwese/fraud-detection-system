```
        LAYER 1 · SEGMENT 3A — STATE S2 (COUNTRY→ZONE PRIORS & FLOORS)  [NO RNG]

Authoritative inputs (read-only at S2 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_3A
      @ data/layer1/3A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3A.json
      · proves: 3A.S0 ran for this manifest_fingerprint
      · binds: {parameter_hash, manifest_fingerprint, seed} for 3A
      · records: upstream_gates.{segment_1A,segment_1B,segment_2A}.status
      · records: sealed_policy_set for priors/floor policy
    - sealed_inputs_3A
      @ data/layer1/3A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3A.parquet
      · sealed inventory of all artefacts 3A is allowed to read for this fingerprint
      · S2 MUST treat this as the exclusive whitelist: if an artefact is not listed here, S2 MUST NOT read it

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml, schemas.ingress.layer1.yaml
    - schemas.2A.yaml, schemas.3A.yaml
    - dataset_dictionary.layer1.{2A,3A}.yaml
    - artefact_registry_{2A,3A}.yaml
      · S2 MUST resolve all artefacts via these; no hard-coded paths

[Zone-universe references]
    - iso3166_canonical_2024
        · canonical country list; S2 MUST ensure every country in priors/policies exists here
    - either:
        · country_tz_universe
            · rows (country_iso, tzid) describing the zone universe Z(c) per country, OR
        · tz_world_2025a
            · ingress TZ polygons from which S2 can derive a country_tz_universe deterministically
    - (optional) other 2A zone refs (tz_index, etc.) if sealed, for consistency checks only

[3A priors & floor policy (parameter-governed)]
    - country_zone_alphas
        · role="country_zone_alphas", owner_segment="3A"
        · schema_ref: schemas.3A.yaml#/policy/country_zone_alphas_v1
        · defines raw α values per (country_iso, tzid) and defaulting/mapping rules
    - zone_floor_policy
        · role="zone_floor_policy", owner_segment="3A"
        · schema_ref: schemas.3A.yaml#/policy/zone_floor_policy_v1
        · defines floor/bump rules for α (e.g. minimum α per zone, reallocation of “mass” when bumping)

[Outputs owned by S2]
    - s2_country_zone_priors
      @ data/layer1/3A/s2_country_zone_priors/parameter_hash={parameter_hash}/...
      · partition_keys: [parameter_hash]
      · primary_key:    [country_iso, tzid]
      · sort_keys:      [country_iso, tzid]
      · columns_strict: true
      · columns (min):
          parameter_hash, country_iso, tzid,
          alpha_raw, alpha_effective, alpha_sum_country,
          prior_pack_id, prior_pack_version,
          floor_policy_id, floor_policy_version,
          floor_applied, bump_applied, share_effective, notes?

[Numeric & RNG posture]
    - Parameter-scoped:
        · All outputs are keyed by parameter_hash only; independent of seed and manifest_fingerprint.
    - RNG:
        · S2 is strictly RNG-free: no Philox, no sampling, no u(0,1), no CSPRNG.
    - Numeric:
        · IEEE-754 binary64; round-to-nearest-even; no FMA/FTZ/DAZ on decision paths.
        · Serial reductions only for sums (per-country α sums); no parallel or order-changing reductions.
    - Side effects:
        · S2 writes exactly one dataset: s2_country_zone_priors (parameter-scoped, write-once, idempotent).


----------------------------------------------------------------------
DAG — 3A.S2 (sealed priors+zone universe → parameter-scoped α surface)  [NO RNG]

[Schema+Dict],
[S0 Gate & Identity]
                ->  (S2.1) Fix identity & reference manifest
                    - Inputs: (parameter_hash, manifest_fingerprint) from caller or layer harness.
                    - Validate:
                        · both are valid hex64.
                    - S2 treats:
                        · `parameter_hash` as its partition key,
                        · `manifest_fingerprint` only as a reference into S0 outputs (`s0_gate_receipt_3A`, `sealed_inputs_3A`).
                    - Record both values in memory for lineage; S2 will embed only `parameter_hash` in its dataset.

[Schema+Dict],
[S0 Gate & Identity]
                ->  (S2.2) Load S0 outputs (gate & whitelist)
                    - Resolve, via the 3A dictionary:
                        · `s0_gate_receipt_3A@fingerprint={manifest_fingerprint}`,
                        · `sealed_inputs_3A@fingerprint={manifest_fingerprint}`.
                    - Validate both against:
                        · schemas.3A.yaml#/validation/s0_gate_receipt_3A,
                        · schemas.3A.yaml#/validation/sealed_inputs_3A.
                    - If either is missing or invalid → S2 MUST fail.

[S0 Gate & Identity],
s0_gate_receipt_3A
                ->  (S2.3) Check upstream gates via S0
                    - From `s0_gate_receipt_3A.upstream_gates`:
                        · require:
                              segment_1A.status == "PASS"
                              segment_1B.status == "PASS"
                              segment_2A.status == "PASS"
                    - If any upstream segment is not PASS:
                        · S2 MUST fail without emitting `s2_country_zone_priors`.

[Schema+Dict],
sealed_inputs_3A
                ->  (S2.4) Resolve catalogue artefacts & zone-universe references
                    - Using catalogue + sealed_inputs_3A, resolve:
                        · `iso3166_canonical_2024`,
                        · either:
                             `country_tz_universe` (preferred if present), OR
                             `tz_world_2025a` (for deriving country_tz_universe),
                        · `country_zone_alphas` prior pack,
                        · `zone_floor_policy`.
                    - For each resolved artefact:
                        · ensure a matching row exists in `sealed_inputs_3A` with same {logical_id, path},
                        · recompute SHA-256 and assert equality with `sha256_hex`.
                    - Validate refs against their schema anchors:
                        · `iso3166_canonical_2024` and `country_tz_universe` / `tz_world_2025a` match their schemas.
                    - Any missing artefact or digest mismatch → S2 MUST fail.

s0_gate_receipt_3A,
sealed_inputs_3A,
country_zone_alphas
                ->  (S2.5) Resolve and validate `country_zone_alphas` prior pack
                    - From `s0_gate_receipt_3A.sealed_policy_set`:
                        · locate the unique entry with role = "country_zone_alphas" and owner_segment="3A".
                    - Using `sealed_inputs_3A` + the catalogue:
                        · resolve:
                              prior_pack_id        (logical ID),
                              prior_pack_path,
                              prior_pack_schema_ref (e.g. schemas.3A.yaml#/policy/country_zone_alphas_v1),
                              sha256_hex (already checked in S2.4).
                    - Validate the prior pack bytes against its schema_ref.
                    - Extract:
                        · per-country/zone α definitions,
                        · any defaulting or mapping rules (e.g. fallback α per country, obsolete tzid mapping).
                    - Record `prior_pack_id` and `prior_pack_version` (e.g. semver or digest-based).

s0_gate_receipt_3A,
sealed_inputs_3A,
zone_floor_policy
                ->  (S2.6) Resolve and validate `zone_floor_policy`
                    - From `s0_gate_receipt_3A.sealed_policy_set`:
                        · locate the unique entry with role = "zone_floor_policy" and owner_segment="3A".
                    - Resolve via `sealed_inputs_3A`+catalogue:
                        · floor_policy_id, floor_policy_path, floor_policy_schema_ref, sha256_hex.
                    - Validate policy bytes against schema anchor (e.g. schemas.3A.yaml#/policy/zone_floor_policy_v1).
                    - Extract:
                        · global floor parameters (e.g. α_min per zone),
                        · per-country overrides (if any),
                        · bump rules (how to redistribute mass when bumping α).
                    - Record `floor_policy_id`, `floor_policy_version`.

country_zone_alphas,
zone_floor_policy,
iso3166_canonical_2024
                ->  (S2.7) Derive country domains C_prior_pack, C_floor_policy, C_priors
                    - Let:
                        · C_prior_pack   = { country_iso | appears in prior pack },
                        · C_floor_policy = { country_iso | appears in floor policy (if any per-country rules) }.
                    - Define:
                        · C_priors = C_prior_pack ∪ C_floor_policy.
                    - Validate:
                        · Every c ∈ C_priors appears in `iso3166_canonical_2024`.
                        · If policy declares that empty domain is invalid and C_priors is empty → S2 MUST fail.
                    - C_priors is the country domain S2 will emit rows for (possibly intersected with zone universe in next steps).

country_tz_universe / tz_world_2025a,
C_priors
                ->  (S2.8) Build zone universe Z(c) per country
                    - For each c ∈ C_priors:
                        · derive Z(c) = { tzid } as follows:
                            - If `country_tz_universe` is present:
                                  Z(c) = { tzid | (country_iso=c, tzid) ∈ country_tz_universe }.
                            - Else derive from `tz_world_2025a` using the agreed Layer-1 rule
                              (e.g. centroids-in-country or polygon intersection) to build a logical country_tz_universe.
                    - S2 MUST treat Z(c) as **authoritative**:
                        · MUST NOT add/remove tzids beyond what refs define.
                    - If a country c ∈ C_priors has Z(c) = ∅:
                        · behaviour (error vs special-case handling) MUST follow the zone-universe policy;
                          if spec says “error” → S2 MUST fail.

C_priors,
Z(c) for each c
                ->  (S2.9) Define S2 domain D_S2 over (country_iso, tzid)
                    - Define:
                        · D_S2 = { (c,z) | c ∈ C_priors AND z ∈ Z(c) }.
                    - S2 MUST:
                        · emit exactly one row in `s2_country_zone_priors` for each (c,z) ∈ D_S2,
                        · emit no rows outside D_S2.

country_zone_alphas,
Z(c),
D_S2
                ->  (S2.10) Extract or default α_raw(c,z)
                    - For each (c,z) ∈ D_S2:
                        1. If prior pack has an explicit entry for (c,z):
                               - use prior schema’s rule to extract α_raw(c,z)
                                 (either direct value or deterministic combination of components).
                        2. Else (no explicit entry in prior pack):
                               - apply the prior pack’s defaulting rule, e.g.:
                                     α_raw(c,z) = 0,
                                     or α_raw(c,z) = α_default(c),
                                     or another deterministic function defined in the schema.
                    - For any entry in the prior pack that refers to (c,z′) with z′ ∉ Z(c):
                        · if the prior schema defines a canonical mapping (e.g. alias obsolete tzid → new tzid),
                          apply that mapping deterministically;
                        · otherwise, treat as a zone-universe mismatch and fail.
                    - After this step:
                        · α_raw(c,z) is defined for every (c,z) ∈ D_S2,
                        · α_raw(c,z) ≥ 0 for all rows (negative values MUST trigger failure).

α_raw(c,z),
zone_floor_policy
                ->  (S2.11) Apply floor/bump policy → α_effective(c,z)
                    - For each c ∈ C_priors:
                        · start with the vector {α_raw(c,z)}_{z∈Z(c)}.
                        · apply floor/bump rules from `zone_floor_policy`:
                              - enforce per-zone or per-country minima (e.g. α_min),
                              - optionally bump selected zones and re-normalise remaining α to preserve total “mass”,
                              - determine boolean flags:
                                    floor_applied(c,z),
                                    bump_applied(c,z).
                    - Result:
                        · α_effective(c,z) > 0 for all (c,z) ∈ D_S2,
                        · floor_applied, bump_applied flags per row.

α_effective(c,z) for all z∈Z(c)
                ->  (S2.12) Compute per-country sums α_sum_country(c)
                    - For each c ∈ C_priors:
                        · α_sum_country(c) = Σ_{z∈Z(c)} α_effective(c,z)  (serial reduction; deterministic order).
                    - Require:
                        · α_sum_country(c) > 0 for all c.
                    - Failure if any α_sum_country(c) ≤ 0 (indicates invalid priors/policy result).

α_effective(c,z),
α_sum_country(c)
                ->  (S2.13) Optionally compute share_effective(c,z)
                    - If schema and implementation choose to materialise share_effective:
                        · share_effective(c,z) = α_effective(c,z) / α_sum_country(c).
                        · validate:
                              - 0 ≤ share_effective(c,z) ≤ 1 for all rows,
                              - for each c, Σ_{z∈Z(c)} share_effective(c,z) ≈ 1 within a small tolerance.
                    - If share_effective is not materialised:
                        · S2 MUST ensure that S3 can recompute it from α_effective / α_sum_country.

α_raw, α_effective, α_sum_country,
floor_applied, bump_applied,
prior_pack_id/version,
floor_policy_id/version,
D_S2
                ->  (S2.14) Assemble row set for `s2_country_zone_priors`
                    - For each (c,z) ∈ D_S2, assemble a row:
                        · parameter_hash        = current parameter_hash,
                        · country_iso           = c,
                        · tzid                  = z,
                        · alpha_raw             = α_raw(c,z),
                        · alpha_effective       = α_effective(c,z),
                        · alpha_sum_country     = α_sum_country(c),
                        · share_effective       = share_effective(c,z) if materialised,
                        · prior_pack_id         = prior_pack_id (from S2.5),
                        · prior_pack_version    = prior_pack_version,
                        · floor_policy_id       = floor_policy_id (from S2.6),
                        · floor_policy_version  = floor_policy_version,
                        · floor_applied         = floor_applied(c,z),
                        · bump_applied          = bump_applied(c,z),
                        · notes                 = optional deterministic diagnostics or null.
                    - S2 MUST produce:
                        · exactly one row per (c,z) ∈ D_S2,
                        · no rows for any (c,z) ∉ D_S2.

[row set],
[Schema+Dict]
                ->  (S2.15) Sort, validate & publish `s2_country_zone_priors` (parameter-scoped)
                    - Using the dictionary entry for `s2_country_zone_priors`:
                        · path pattern: data/layer1/3A/s2_country_zone_priors/parameter_hash={parameter_hash}/...
                        · partition_keys: [parameter_hash],
                        · primary_key:    [country_iso, tzid],
                        · sort_keys:      [country_iso, tzid].
                    - Sort in-memory rows by (country_iso ASC, tzid ASC).
                    - Validate against schemas.3A.yaml#/plan/s2_country_zone_priors:
                        · all required columns present,
                        · numeric constraints (min/exclusiveMin, max),
                        · PK uniqueness on (country_iso, tzid).
                    - Immutability & idempotence:
                        · if partition `parameter_hash={parameter_hash}` is empty → allowed to write.
                        · if it exists:
                              - read existing dataset and normalise (schema, sort),
                              - if byte-identical → treat as idempotent re-run,
                              - otherwise → FAIL with immutability error; MUST NOT overwrite.
                    - Write:
                        · write Parquet files to a staging location,
                        · fsync, then atomically move into final Dictionary path,
                        · ensure every row’s `parameter_hash` equals the partition token.

Downstream touchpoints
----------------------
- **3A.S3 — Zone share sampling:**
    - MUST treat `s2_country_zone_priors` as the **only** authority for α-vectors per (country_iso, tzid).
    - MUST NOT read `country_zone_alphas` directly; it uses only α_effective and α_sum_country from S2 when drawing Dirichlet samples.
- **3A.S4 — Integer zone allocation:**
    - Uses Z(c) and α_sum_country(c) indirectly (via S3) but MUST NOT modify or reinterpret S2 priors.
- **3A.S6 — Validation:**
    - Validates that:
        · domain of `s2_country_zone_priors` matches C_priors×Z(c),
        · α_raw ≥ 0, α_effective > 0, α_sum_country > 0,
        · per-country Σ share_effective ≈ 1 when materialised,
        · prior_pack_id/version and floor_policy_id/version match S0’s sealed policy set.
- **S2 is not public egress:**
    - `s2_country_zone_priors` is an internal, parameter-scoped surface;
      its authority is scoped to Segment 3A and its validators. External segments (e.g. 2B) must only see priors via 3A’s
      final HashGate and approved cross-layer contracts (e.g. zone_alloc).
```