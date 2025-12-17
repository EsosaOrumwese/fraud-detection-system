```
        LAYER 1 · SEGMENT 3A — STATE S5 (ZONE ALLOCATION EGRESS & ROUTING UNIVERSE HASH)  [NO RNG]

Authoritative inputs (read-only at S5 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_3A
      @ data/layer1/3A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3A.json
      · proves: 3A.S0 ran for this manifest_fingerprint and upstream 1A/1B/2A gates are PASS
      · binds: {parameter_hash, manifest_fingerprint, seed} for Segment 3A
      · records: sealed_policy_set (mixture, priors, floors, day-effect) and catalogue_versions
    - sealed_inputs_3A
      @ data/layer1/3A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3A.parquet
      · whitelist of external artefacts S5 may read (policies/priors, day-effect config, refs)
      · every external artefact S5 reads for digest computation MUST appear here with matching {logical_id, path, sha256_hex}

[Schema+Dict · catalogue & shape authority]
    - schemas.layer1.yaml, schemas.ingress.layer1.yaml
    - schemas.2A.yaml, schemas.3A.yaml
      · define shapes for s1_escalation_queue, s2_country_zone_priors, s3_zone_shares, s4_zone_counts,
        egress/zone_alloc, validation/zone_alloc_universe_hash
    - dataset_dictionary.layer1.3A.yaml
      · IDs → paths/partitions/schema_ref for s1–s4, zone_alloc, zone_alloc_universe_hash
    - artefact_registry_3A.yaml
      · dataset roles and lineage; non-authoritative for shapes

[3A internal inputs (business & stochastic authority)]
    - s1_escalation_queue
        · producer: 3A.S1
        · partition: seed={seed} / fingerprint={manifest_fingerprint}
        · PK/sort: [merchant_id, legal_country_iso]
        · provides:
              D       = {(m,c)}         (all merchant×country),
              D_esc   = {(m,c) | is_escalated=true},
              site_count(m,c) (integer ≥ 1),
              mixture_policy_id/version (from sealed mixture policy).
        · S5 MAY only use:
              - D, D_esc for domain checks,
              - site_count(m,c) for conservation checks,
              - mixture_policy_id/version for lineage fields.
    - s2_country_zone_priors
        · producer: 3A.S2
        · partition: parameter_hash={parameter_hash}
        · PK/sort: [country_iso, tzid]
        · provides:
              Z(c) = {tzid | (country_iso=c, tzid) in S2},
              prior lineage: prior_pack_id/version, floor_policy_id/version.
        · S5 MAY only use:
              - Z(c) for domain checks,
              - prior_pack_id/version + floor_policy_id/version for lineage and digests.
    - s3_zone_shares
        · producer: 3A.S3
        · partition: seed={seed} / fingerprint={manifest_fingerprint}
        · PK/sort: [merchant_id, legal_country_iso, tzid]
        · S5 treats S3 as **optional structural confirmation**:
              - may confirm S3 domain matches S4’s domain,
              - may cross-check share_sum_country(m,c)~=1,
              - MUST NOT re-sample or alter shares.
    - s4_zone_counts
        · producer: 3A.S4
        · partition: seed={seed} / fingerprint={manifest_fingerprint}
        · PK/sort: [merchant_id, legal_country_iso, tzid]
        · provides:
              zone_site_count(m,c,z)    (integer ≥ 0),
              zone_site_count_sum(m,c)  (integer ≥ 1),
              share_sum_country(m,c),
              prior lineage (prior_pack_id/version, floor_policy_id/version).
        · S5 MUST treat s4_zone_counts as the **sole authority** on integer zone-level counts.

[External policy/prior artefacts for digests (sealed via S0)]
    - zone_mixture_policy_3A
        · mixture policy artefact used by S1; basis for `theta_digest`
    - country_zone_alphas_3A (or equivalent prior pack)
        · basis for `zone_alpha_digest`
    - zone_floor_policy_3A
        · basis for `zone_floor_digest`
    - day_effect_policy_v1 (from 2B)
        · basis for `day_effect_digest` (γ variance configuration)

[Segment-state run-report (for precondition checks)]
    - 3A segment-state run-report
        · schema defines per-state status:
              S1.status, S2.status, S3.status, S4.status
        · S5 MUST require each relevant state is PASS before proceeding.

[Outputs owned by S5]
    - zone_alloc
      @ data/layer1/3A/zone_alloc/seed={seed}/fingerprint={manifest_fingerprint}/…
      · partition_keys: [seed, fingerprint]
      · primary_key:    [merchant_id, legal_country_iso, tzid]
      · sort_keys:      [merchant_id, legal_country_iso, tzid]
      · schema_ref:     schemas.3A.yaml#/egress/zone_alloc
      · columns (min):
            seed, fingerprint,
            merchant_id, legal_country_iso, tzid,
            zone_site_count ≥ 0,
            zone_site_count_sum ≥ 1,
            site_count ≥ 1,
            prior_pack_id, prior_pack_version,
            floor_policy_id, floor_policy_version,
            mixture_policy_id, mixture_policy_version,
            day_effect_policy_id, day_effect_policy_version,
            routing_universe_hash (same value on every row)
    - zone_alloc_universe_hash
      @ data/layer1/3A/zone_universe/fingerprint={manifest_fingerprint}/zone_alloc_universe_hash.json
      · partition_keys: [fingerprint]
      · schema_ref:     schemas.3A.yaml#/validation/zone_alloc_universe_hash
      · fields (min):
            manifest_fingerprint, parameter_hash,
            zone_alpha_digest, theta_digest, zone_floor_digest,
            day_effect_digest, zone_alloc_parquet_digest,
            routing_universe_hash

[Numeric & RNG posture]
    - RNG:
        · S5 is strictly RNG-free: MUST NOT call Philox or any RNG.
    - Determinism:
        · Given (parameter_hash, manifest_fingerprint, seed, run_id), S1–S4 outputs, sealed policies, and catalogue,
          S5 MUST be deterministic and idempotent:
              re-running S5 → byte-identical zone_alloc and zone_alloc_universe_hash.
    - Numeric:
        · Pure SHA-256 over raw bytes; no FP arithmetic affects content.


----------------------------------------------------------------------
DAG — 3A.S5 (S4 counts → zone_alloc egress + routing_universe_hash)  [NO RNG]

[Schema+Dict],
[S0 Gate & Identity]
                ->  (S5.1) Fix run identity
                    - Inputs:
                        · parameter_hash (hex64),
                        · manifest_fingerprint (hex64),
                        · seed (uint64),
                        · run_id (string or u128-like).
                    - Validate formats; treat tuple
                          (parameter_hash, manifest_fingerprint, seed, run_id)
                      as immutable for this S5 run.
                    - Only `seed` and `manifest_fingerprint` become zone_alloc partition keys;
                      `parameter_hash` is embedded as metadata in zone_alloc_universe_hash.

[Schema+Dict],
[S0 Gate & Identity]
                ->  (S5.2) Load S0 artefacts & check upstream gates
                    - Resolve:
                        · s0_gate_receipt_3A@fingerprint={manifest_fingerprint},
                        · sealed_inputs_3A@fingerprint={manifest_fingerprint},
                      via the 3A dictionary.
                    - Validate both against their schema anchors.
                    - From `upstream_gates` in S0:
                        · require `segment_1A/1B/2A.status == "PASS"`.
                      On failure → precondition error; S5 MUST NOT emit outputs.

[Schema+Dict],
sealed_inputs_3A
                ->  (S5.3) Load S1–S4 plan surfaces & validate shapes
                    - Resolve and validate via dictionary:
                        · s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}
                          (schemas.3A.yaml#/plan/s1_escalation_queue),
                        · s2_country_zone_priors@parameter_hash={parameter_hash}
                          (schemas.3A.yaml#/plan/s2_country_zone_priors),
                        · s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint}
                          (schemas.3A.yaml#/plan/s3_zone_shares),
                        · s4_zone_counts@seed={seed}/fingerprint={manifest_fingerprint}
                          (schemas.3A.yaml#/plan/s4_zone_counts).
                    - Any schema failure or missing dataset ⇒ `PRECONDITION_FAILED`; S5 MUST stop.

[Segment-state run-report]
                ->  (S5.4) Confirm S1–S4 PASS status
                    - Resolve the 3A segment-state run-report for this run (Dataset ID defined by 3A governance).
                    - Require:
                        · S1.status == "PASS" for this {seed,fingerprint},
                        · S2.status == "PASS" for this parameter_hash,
                        · S3.status == "PASS" for this (parameter_hash, manifest_fingerprint, seed, run_id),
                        · S4.status == "PASS" for this (parameter_hash, manifest_fingerprint, seed, run_id).
                    - If any state is not PASS ⇒ S5 MUST fail with a precondition error.

s0_gate_receipt_3A,
sealed_inputs_3A
                ->  (S5.5) Resolve external policy/prior artefacts
                    - Using `s0_gate_receipt_3A.sealed_policy_set` + `sealed_inputs_3A`, resolve:
                        · mixture policy artefact (zone_mixture_policy_3A),
                        · prior pack artefact (country_zone_alphas_3A),
                        · floor policy artefact (zone_floor_policy_3A),
                        · day-effect policy artefact (day_effect_policy_v1).
                    - For each artefact:
                        · confirm it appears in `sealed_inputs_3A` with matching {logical_id, path},
                        · recompute SHA-256(file_bytes) and assert equality with `sha256_hex`.
                    - Extract:
                        · mixture_policy_id, mixture_policy_version,
                        · prior_pack_id, prior_pack_version,
                        · floor_policy_id, floor_policy_version,
                        · day_effect_policy_id, day_effect_policy_version.
                    - These IDs/versions are the only policy lineage S5 MAY embed in zone_alloc and zone_alloc_universe_hash.

[Schema+Dict]
                ->  (S5.6) Load catalogue artefacts for outputs
                    - Resolve and validate:
                        · schemas.layer1.yaml, schemas.ingress.layer1.yaml,
                        · schemas.2A.yaml, schemas.3A.yaml,
                        · dataset_dictionary.layer1.3A.yaml,
                        · artefact_registry_3A.yaml.
                    - Any malformed or missing catalogue artefact S5 relies on ⇒ catalogue error; S5 MUST NOT proceed.

s1_escalation_queue,
s2_country_zone_priors,
s4_zone_counts
                ->  (S5.7) Domain consistency & conservation checks
                    - From S1:
                        · D    = { (m,c) } — all merchant×country pairs,
                        · D_esc= { (m,c) ∈ D | is_escalated=true }.
                    - From S2:
                        · for each c in D_esc:
                              Z(c) = { tzid | (country_iso=c, tzid) in S2 }.
                    - From S4:
                        · projection D_S4 = projection of S4 onto (merchant_id, legal_country_iso),
                          with zone sets:
                              Z_S4(m,c) = { tzid | (m,c, tzid) in S4 }.
                        · for each (m,c):
                              N(m,c) = site_count(m,c) from S1,
                              N_sum(m,c) = zone_site_count_sum(m,c) from S4,
                              total_from_counts = Σ_z zone_site_count(m,c,z).
                    - S5 MUST assert:
                        · D_S4 == D_esc (S4 only contains escalated pairs; no missing escalated pair),
                        · ∀ (m,c) ∈ D_esc: Z_S4(m,c) == Z(c),
                        · ∀ (m,c) ∈ D_esc: N_sum(m,c) = total_from_counts = N(m,c).
                    - Any mismatch ⇒ S4/S5 domain or conservation error; S5 MUST fail without corrections.

s4_zone_counts,
s1_escalation_queue,
s2_country_zone_priors,
mixture_policy_id/version,
day_effect_policy_id/version
                ->  (S5.8) Build in-memory `zone_alloc` row skeletons
                    - For each row (m,c,z) in s4_zone_counts@{seed,fingerprint}:
                        · read:
                              zone_site_count    = zone_site_count(m,c,z),
                              zone_site_count_sum(m,c),
                              share_sum_country(m,c),
                              prior_pack_id, prior_pack_version,
                              floor_policy_id, floor_policy_version.
                        · look up site_count(m,c) from S1:
                              site_count(m,c) MUST equal zone_site_count_sum(m,c); else → fail.
                        - Construct a `zone_alloc` row with:
                              seed                     = seed,
                              fingerprint              = manifest_fingerprint,
                              merchant_id              = m,
                              legal_country_iso        = c,
                              tzid                     = z,
                              zone_site_count          = zone_site_count(m,c,z),
                              zone_site_count_sum      = zone_site_count_sum(m,c),
                              site_count               = site_count(m,c),
                              prior_pack_id            = prior_pack_id,
                              prior_pack_version       = prior_pack_version,
                              floor_policy_id          = floor_policy_id,
                              floor_policy_version     = floor_policy_version,
                              mixture_policy_id        = mixture_policy_id,
                              mixture_policy_version   = mixture_policy_version,
                              day_effect_policy_id     = day_effect_policy_id,
                              day_effect_policy_version= day_effect_policy_version,
                              routing_universe_hash    = null / unset (to be filled later).
                        - Optional fields (if present in schema) such as alpha_sum_country, notes, etc.
                          MAY be copied from S2/S4 as deterministic echoes.

----------------------------------------
Phase 3 — Write `zone_alloc` & compute `zone_alloc_parquet_digest`
----------------------------------------

[zone_alloc row skeletons],
[Schema+Dict]
                ->  (S5.9) Determine target path & canonical writer-sort
                    - From dictionary entry for `zone_alloc`:
                        · target directory:
                              data/layer1/3A/zone_alloc/seed={seed}/fingerprint={manifest_fingerprint}/.
                        · partition_keys: [seed, fingerprint].
                    - Sort rows by:
                        1. merchant_id ASC,
                        2. legal_country_iso ASC,
                        3. tzid ASC.
                    - This sort order is the canonical writer-sort for zone_alloc.

(sorted rows),
existing zone_alloc?,
[Schema+Dict]
                ->  (S5.10) Idempotent write & `zone_alloc_parquet_digest`
                    - If no dataset exists at target path:
                        · write sorted rows to Parquet files under the target directory.
                        · ensure only Parquet data files are treated as part of the dataset;
                          ignore markers like `_SUCCESS` for digest purposes.
                    - If dataset exists:
                        · read existing dataset, normalise to same schema + writer-sort,
                        · compare row-for-row, field-for-field with new rows:
                              - if identical:
                                    - S5 MAY reuse existing files,
                                    - S5 MUST recompute digest and check it matches any previously stored value where applicable.
                              - if not identical:
                                    - immutability violation ⇒ FAIL; MUST NOT overwrite.
                    - Compute `zone_alloc_parquet_digest`:
                        · enumerate all Parquet data files under the directory,
                        · sort relative paths ASCII-lexically,
                        · concatenate their raw bytes,
                        · compute SHA-256(concatenated_bytes) → `zone_alloc_parquet_digest` (hex string).
                    - Hold `zone_alloc_parquet_digest` for use in digest phase and in zone_alloc_universe_hash.

----------------------------------------
Phase 4 — Compute component digests & `routing_universe_hash`
----------------------------------------

s2_country_zone_priors,
[Schema+Dict]
                ->  (S5.11) Compute `zone_alpha_digest`
                    - Basis: `s2_country_zone_priors@parameter_hash`.
                    - Enumerate all Parquet files under its directory,
                      sort relative paths ASCII-lexically, concatenate bytes,
                      compute SHA-256(concatenated_bytes) → `zone_alpha_digest` (hex).

mixture policy artefact bytes
                ->  (S5.12) Compute `theta_digest`
                    - Read raw bytes of the mixture policy artefact (zone_mixture_policy_3A) from its sealed path.
                    - Do NOT re-serialise or pretty-print.
                    - Compute `theta_digest = SHA-256(file_bytes)` as lowercase hex.

zone_floor_policy artefact bytes
                ->  (S5.13) Compute `zone_floor_digest`
                    - Read raw bytes of the floor/bump policy artefact (zone_floor_policy_3A).
                    - Compute `zone_floor_digest = SHA-256(file_bytes)` as lowercase hex.

day_effect_policy_v1 artefact bytes
                ->  (S5.14) Compute `day_effect_digest`
                    - Read raw bytes of the day-effect policy artefact (day_effect_policy_v1).
                    - Compute `day_effect_digest = SHA-256(file_bytes)` as lowercase hex.

zone_alpha_digest,
theta_digest,
zone_floor_digest,
day_effect_digest,
zone_alloc_parquet_digest
                ->  (S5.15) Compute `routing_universe_hash`
                    - Concatenate ASCII bytes of the hex strings exactly in this order:
                          concat = zone_alpha_digest
                                   || theta_digest
                                   || zone_floor_digest
                                   || day_effect_digest
                                   || zone_alloc_parquet_digest
                      where `||` is simple byte concatenation, no delimiters.
                    - Compute:
                          routing_universe_hash = SHA256(concat)
                      encoded as lowercase hex.
                    - This `routing_universe_hash` is the single identifier used by downstream components.

----------------------------------------
Phase 5 — Finalise `zone_alloc` & write `zone_alloc_universe_hash`
----------------------------------------

[zone_alloc rows],
routing_universe_hash
                ->  (S5.16) Fill `routing_universe_hash` into zone_alloc rows
                    - For every in-memory `zone_alloc` row:
                        · set `routing_universe_hash` = the value from Step 15.
                    - Canonical procedure:
                        · S5 SHOULD compute `zone_alloc_parquet_digest` on the final representation (including routing_universe_hash),
                          or, if digest was computed earlier, MUST re-check that digest remains valid for the final on-disk content.
                    - The digest and universe-hash artefact MUST correspond to the final zone_alloc bytes.

[final zone_alloc rows],
existing zone_alloc? (if any),
[Schema+Dict]
                ->  (S5.17) Write (or confirm) final `zone_alloc`
                    - Apply the same immutability law as Step 10, but now with final rows including routing_universe_hash:
                        · if dataset does not exist → write final rows with canonical writer-sort.
                        · if dataset exists:
                              - normalise and compare; MUST be byte-identical,
                              - if not → immutability violation; MUST NOT overwrite.
                    - Validate again against `schemas.3A.yaml#/egress/zone_alloc`.
                    - Path↔embed:
                        · seed and fingerprint columns MUST equal partition tokens.

routing_universe_hash,
zone_alpha_digest,
theta_digest,
zone_floor_digest,
day_effect_digest,
zone_alloc_parquet_digest,
[Schema+Dict]
                ->  (S5.18) Build `zone_alloc_universe_hash` object
                    - Construct a JSON object conforming to `schemas.3A.yaml#/validation/zone_alloc_universe_hash`:
                        · manifest_fingerprint = current manifest_fingerprint,
                        · parameter_hash       = current parameter_hash,
                        · zone_alpha_digest,
                        · theta_digest,
                        · zone_floor_digest,
                        · day_effect_digest,
                        · zone_alloc_parquet_digest,
                        · routing_universe_hash,
                        · optional: version string, created_at_utc (from orchestrator), notes.
                    - MUST NOT embed raw artefact contents; only digests and minimal metadata.

[zone_alloc_universe_hash object],
existing zone_alloc_universe_hash?,
[Schema+Dict]
                ->  (S5.19) Write `zone_alloc_universe_hash` & enforce immutability
                    - Target path via dictionary:
                        · data/layer1/3A/zone_universe/fingerprint={manifest_fingerprint}/zone_alloc_universe_hash.json
                    - Partition: [fingerprint].
                    - If no file exists → write via staging → fsync → atomic move.
                    - If file exists:
                        · read existing JSON, normalise fields, and compare to new object;
                        · if byte-identical → idempotent re-run; OK;
                        · otherwise → immutability violation; MUST NOT overwrite.

Downstream touchpoints
----------------------
- **Segment 2B (routing) and other consumers:**
    - MUST treat `zone_alloc` as the **cross-layer zone allocation egress**:
        · integer zone_site_count(m,c,z),
        · per-(m,c) totals zone_site_count_sum / site_count,
        · priors/floor/mixture/day-effect lineage,
        · a single routing_universe_hash per fingerprint.
    - MUST treat `zone_alloc_universe_hash` as the authoritative digest summary:
        · verifies that the priors, mixture, floor policy, day-effect policy, and zone_alloc egress match
          the universe the routing engine expects.
    - MUST enforce 3A’s segment-level HashGate (from S7) before reading `zone_alloc`:
          **No PASS → No read**.

- **3A.S6/S7 (validation & bundle):**
    - Use `zone_alloc` and `zone_alloc_universe_hash` as inputs:
        · S6 verifies that the digests match recomputed values,
        · S7 includes both artefacts in the 3A validation bundle indexed by `_passed.flag_3A`.

- **Re-run & change control:**
    - Any change to priors, policies, or S1–S4 behaviour that affects zone_alloc MUST result in:
        · new `zone_alpha_digest` / `theta_digest` / `zone_floor_digest` / `day_effect_digest` / `zone_alloc_parquet_digest`,
        · thus a new `routing_universe_hash`,
        · and, under normal processes, a new `manifest_fingerprint` and/or `parameter_hash`.
```