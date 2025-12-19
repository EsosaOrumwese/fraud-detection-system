```
        LAYER 1 · SEGMENT 3A — STATE S4 (INTEGER ZONE ALLOCATION: COUNTS PER m×c×z)  [NO RNG]

Authoritative inputs (read-only at S4 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_3A
      @ data/layer1/3A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3A.json
      · proves: 3A.S0 ran for this manifest_fingerprint
      · binds: {parameter_hash, manifest_fingerprint, seed} for this 3A run
      · records: upstream_gates.{segment_1A,segment_1B,segment_2A}.status == "PASS"
      · records: sealed_policy_set for priors/floor/mix/day-effect
    - sealed_inputs_3A
      @ data/layer1/3A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3A.parquet
      · whitelist of external artefacts 3A may read; S4 MUST NOT read any external artefact not listed here

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml, schemas.ingress.layer1.yaml
    - schemas.2A.yaml, schemas.3A.yaml
    - dataset_dictionary.layer1.{2A,3A}.yaml
    - artefact_registry_{2A,3A}.yaml
      · only authority for dataset IDs, paths, partitions, schema_ref for S1/S2/S3/S4 and any zone-universe refs

[3A internal plan surfaces (authoritative upstream inputs)]
    - s1_escalation_queue
        · producer: 3A.S1
        · partition: seed={seed} / fingerprint={manifest_fingerprint}
        · PK/sort: [merchant_id, legal_country_iso]
        · columns (min):
              seed, fingerprint,
              merchant_id, legal_country_iso,
              site_count ≥ 1,
              zone_count_country ≥ 0,
              is_escalated (bool),
              decision_reason,
              mixture_policy_id, mixture_policy_version
        · S4’s use:
              - domain D = {(m,c)},
              - escalated domain D_esc = {(m,c) | is_escalated=true},
              - per-pair totals N(m,c) = site_count(m,c).
    - s2_country_zone_priors
        · producer: 3A.S2
        · partition: parameter_hash={parameter_hash}
        · PK/sort: [country_iso, tzid]
        · columns (min):
              parameter_hash,
              country_iso, tzid,
              alpha_effective > 0, alpha_sum_country > 0,
              prior_pack_id, prior_pack_version,
              floor_policy_id, floor_policy_version,
              floor_applied, bump_applied
        · S4’s use:
              - define Z(c) = {tzid | (country_iso=c, tzid) in S2},
              - carry prior/floor lineage and alpha_sum_country(c) (optional) into S4 rows.
    - s3_zone_shares
        · producer: 3A.S3
        · partition: seed={seed} / fingerprint={manifest_fingerprint}
        · PK/sort: [merchant_id, legal_country_iso, tzid]
        · columns (min):
              seed, fingerprint,
              merchant_id, legal_country_iso, tzid,
              share_drawn ∈ [0,1],
              share_sum_country > 0,
              alpha_sum_country > 0 (optional),
              prior_pack_id, prior_pack_version,
              floor_policy_id, floor_policy_version
        · S4’s use:
              - Θ(m,c,z) = share_drawn,
              - share_sum_country(m,c),
              - prior/floor lineage, alpha_sum_country(c) if present.

[Output owned by S4]
    - s4_zone_counts
      @ data/layer1/3A/s4_zone_counts/seed={seed}/fingerprint={manifest_fingerprint}/…
      · partition_keys: [seed, fingerprint]
      · primary_key:    [merchant_id, legal_country_iso, tzid]
      · sort_keys:      [merchant_id, legal_country_iso, tzid]
      · schema_ref:     schemas.3A.yaml#/plan/s4_zone_counts
      · columns (min):
            seed, fingerprint,
            merchant_id, legal_country_iso, tzid,
            zone_site_count ≥ 0,
            zone_site_count_sum ≥ 0,
            share_sum_country > 0,
            prior_pack_id, prior_pack_version,
            floor_policy_id, floor_policy_version,
            (optional) fractional_target, residual_rank, alpha_sum_country, notes

[Numeric & RNG posture]
    - RNG:
        · S4 is strictly **RNG-free**:
            - MUST NOT consume Philox or any RNG,
            - MUST NOT use wall-clock time.
        · All randomness in zone counts comes solely from S3’s shares.
    - Numeric:
        · IEEE-754 binary64; round-to-nearest-even; no FMA/FTZ/DAZ.
        · Serial reductions only (e.g. sums over zones).
    - Scope:
        · Run-scoped over {seed, manifest_fingerprint} under fixed parameter_hash.
        · Idempotent: same S1/S2/S3 inputs ⇒ byte-identical s4_zone_counts.


----------------------------------------------------------------------
DAG — 3A.S4 (Dirichlet shares + totals → integer zone counts)  [NO RNG]

[Schema+Dict],
[S0 Gate & Identity]
                ->  (S4.1) Fix run identity & load S0 artefacts
                    - Inputs from orchestrator:
                        · parameter_hash (hex64),
                        · manifest_fingerprint (hex64),
                        · seed (uint64),
                        · run_id (string / u128-encoded; not used for partitions).
                    - Validate formats; treat values as immutable.
                    - Resolve:
                        · s0_gate_receipt_3A@fingerprint={manifest_fingerprint},
                        · sealed_inputs_3A@fingerprint={manifest_fingerprint},
                      via 3A dictionary/registry.
                    - Validate both against schemas.3A.yaml anchors.
                    - Require upstream gates in receipt:
                        · segment_1A.status == "PASS",
                          segment_1B.status == "PASS",
                          segment_2A.status == "PASS";
                      else: precondition failure; S4 MUST NOT emit s4_zone_counts.

[Schema+Dict],
sealed_inputs_3A
                ->  (S4.2) Load S1/S2/S3 datasets via catalogue
                    - Resolve via dictionary:
                        · s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint},
                        · s2_country_zone_priors@parameter_hash={parameter_hash},
                        · s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint}.
                    - Validate each against its schema_ref:
                        · s1_escalation_queue → `#/plan/s1_escalation_queue`,
                        · s2_country_zone_priors → `#/plan/s2_country_zone_priors`,
                        · s3_zone_shares → `#/plan/s3_zone_shares`.
                    - S4 MUST NOT read any external refs/policies directly; it relies only on these 3A datasets.

s1_escalation_queue
                ->  (S4.3) Derive merchant×country domain D and escalated domain D_esc
                    - Domain:
                        · D = { (m,c) } = projection of S1 onto (merchant_id, legal_country_iso).
                    - Escalated subset:
                        · D_esc = { (m,c) ∈ D | is_escalated(m,c) = true }.
                    - Per-pair totals:
                        · for each (m,c), N(m,c) = site_count(m,c) (integer ≥ 1).
                    - S4 MUST:
                        · treat S1 as sole authority on D and D_esc,
                        · NEVER produce counts for (m,c) with is_escalated=false or (m,c) ∉ D.

s2_country_zone_priors
                ->  (S4.4) Derive zone universe Z(c) and per-country metadata
                    - For each country_iso=c:
                        · define Z(c) = { tzid | (country_iso=c, tzid) in S2 }.
                    - For each c with Z(c) ≠ ∅:
                        · read alpha_sum_country(c) (from S2; rows for c must agree),
                        · read constant prior/floor lineage:
                              prior_pack_id, prior_pack_version,
                              floor_policy_id, floor_policy_version.
                    - S4 MUST treat:
                        · Z(c) and alpha_sum_country(c) as given from S2,
                        · prior/floor IDs/versions as constants across S4 output.
                    - If some c appears in D_esc but Z(c) is empty → FAIL (zone-universe inconsistency).

s3_zone_shares
                ->  (S4.5) Derive S3 domain and per-(m,c) zone sets
                    - From S3:
                        · D_S3 = projection onto (merchant_id, legal_country_iso),
                        · for each (m,c) in D_S3:
                              Z_S3(m,c) = { tzid | rows exist with (m,c,tzid) }.
                    - S4 MUST verify:
                        · D_S3 == D_esc:
                             - every escalated (m,c) has S3 rows,
                             - no non-escalated (m,c) has S3 rows.
                    - S4 MUST NOT proceed if D_S3 ≠ D_esc.

[D_esc from S4.3],
Z(c) from S4.4,
Z_S3(m,c) from S4.5
                ->  (S4.6) Domain alignment and zone ordering
                    - For each escalated (m,c) ∈ D_esc:
                        · let c = legal_country_iso for this pair.
                        · Require:
                              Z_S3(m,c) == Z(c);
                          i.e. S3 must have exactly one row per tzid in the S2 zone universe; no extras, no omissions.
                    - For each c:
                        · define Z_ord(c) as the list of tzid in Z(c) sorted ASCII-lex ascending.
                    - For each (m,c):
                        · S4 will process zones in the order Z_ord(c) for all numeric loops.

s3_zone_shares,
[D_esc, Z_ord(c)],
s1_escalation_queue
                ->  (S4.7) Read shares & check share_sum_country per (m,c)
                    - For each (m,c) ∈ D_esc:
                        · gather rows_S3(m,c) from S3 with (merchant_id=m, legal_country_iso=c).
                        · Ensure |rows_S3(m,c)| == |Z(c)|.
                        · Read:
                              share_drawn(m,c,z) for each z ∈ Z_ord(c),
                              share_sum_country(m,c) (all rows for (m,c) must agree).
                    - S4 MUST:
                        · require `share_sum_country(m,c)` within a fixed tolerance of 1
                          (e.g. [1−ε_share, 1+ε_share]).
                        · treat any out-of-tolerance sum as S3 inconsistency → FAIL.
                        · MUST NOT renormalise shares; it only uses them as-is.

[D_esc],
N(m,c) from S1,
share_drawn(m,c,z) from S3,
Z_ord(c)
                ->  (S4.8) Compute continuous targets T_z(m,c) per zone
                    - For each (m,c) ∈ D_esc:
                        · let N = site_count(m,c) (from S1; integer ≥ 1).
                        · For each z ∈ Z_ord(c):
                              p_z = share_drawn(m,c,z).
                              T_z(m,c) = N * p_z   (binary64).
                        - S4 MAY optionally store T_z(m,c) into fractional_target(m,c,z);
                          even if not stored, T_z MUST be well-defined and reproducible.
                    - At this point, we have:
                        · continuous targets {T_z(m,c)} per escalated (m,c).

T_z(m,c) per z,
Z_ord(c),
N(m,c)
                ->  (S4.9) Base counts via floor
                    - For each escalated (m,c):
                        · For each z ∈ Z_ord(c):
                              b_z(m,c) = floor(T_z(m,c))  (integer ≥ 0).
                        · base_sum(m,c) = Σ_z b_z(m,c) (serial reduction in Z_ord(c) order).
                        · R(m,c) = N − base_sum(m,c) (residual units).
                    - S4 MUST:
                        · assert base_sum(m,c) ≤ N; if base_sum(m,c) > N → numeric failure, S4 MUST FAIL.
                        · If R(m,c) == 0:
                              - integer counts finalised as zone_site_count(m,c,z) = b_z(m,c) for all z;
                              - no residual distribution needed.
                        · If R(m,c) > 0:
                              - proceed to residual-based allocation.

T_z(m,c),
b_z(m,c) (for R>0),
Z_ord(c)
                ->  (S4.10) Residuals & deterministic ranking
                    - For each escalated (m,c) with R(m,c) > 0:
                        · For each z ∈ Z_ord(c):
                              r_z(m,c) = T_z(m,c) − b_z(m,c).
                              (By construction r_z ∈ [0,1).)
                        - Define a deterministic ordering of zones for residual allocation:
                              - sort zones by:
                                    1. r_z(m,c) DESC (largest residual first),
                                    2. tzid ASC (ASCII lex),
                                    3. any stable index tie-breaker if needed.
                        - Let the resulting order be:
                              z^(1), z^(2), …, z^(K(c)).
                        - Optionally define residual_rank(m,c,z^(k)) = k.

b_z(m,c),
R(m,c),
residual ordering z^(1..K(c))
                ->  (S4.11) Distribute residual units & final integer counts
                    - For each escalated (m,c):
                        · If R(m,c) == 0:
                              - set zone_site_count(m,c,z) = b_z(m,c) for all z ∈ Z_ord(c).
                        · If R(m,c) > 0:
                              - For each zone z:
                                    zone_site_count(m,c,z) =
                                        b_z(m,c) + 1   if z ∈ {z^(1), …, z^(R(m,c))}
                                        b_z(m,c)       otherwise.
                              - This guarantees:
                                    Σ_z zone_site_count(m,c,z) = base_sum(m,c) + R(m,c) = N.
                        - S4 MUST assert:
                              - zone_site_count(m,c,z) ≥ 0 for all z.
                        - If R(m,c) < 0 (should not occur given earlier checks):
                              - treat as error; MUST NOT attempt “negative residual” fix-ups.

zone_site_count(m,c,z),
N(m,c),
share_sum_country(m,c),
alpha_sum_country(c),
prior/floor lineage from S2/S3
                ->  (S4.12) Construct row set for s4_zone_counts
                    - Define D_S4 = { (m,c,z) | (m,c) ∈ D_esc, z ∈ Z(c) }.
                    - For each (m,c,z) in D_S4:
                        · build a row:
                              seed                = seed,
                              fingerprint         = manifest_fingerprint,
                              merchant_id         = m,
                              legal_country_iso   = c,
                              tzid                = z,
                              zone_site_count     = zone_site_count(m,c,z),
                              zone_site_count_sum = N(m,c),
                              share_sum_country   = share_sum_country(m,c),
                              prior_pack_id       = prior_pack_id,
                              prior_pack_version  = prior_pack_version,
                              floor_policy_id     = floor_policy_id,
                              floor_policy_version= floor_policy_version,
                              (optional) fractional_target = T_z(m,c),
                              (optional) residual_rank     = residual_rank(m,c,z),
                              (optional) alpha_sum_country= alpha_sum_country(c),
                              (optional) notes            = deterministic diagnostics or null.
                    - S4 MUST ensure:
                        · exactly one row for every (m,c,z) in D_S4,
                        · no rows for:
                              - (m,c) with is_escalated=false,
                              - (m,c) ∉ D,
                              - tzid ∉ Z(c) for that c.

S4 row set,
[Schema+Dict]
                ->  (S4.13) Sort, validate & publish s4_zone_counts
                    - Sort rows by:
                        · merchant_id ASC,
                        · legal_country_iso ASC,
                        · tzid ASC.
                    - Validate against `schemas.3A.yaml#/plan/s4_zone_counts`:
                        · required columns present,
                        · numeric/domain constraints satisfied,
                        · PK uniqueness on (merchant_id, legal_country_iso, tzid),
                        · path↔embed sanity:
                              - all rows share same seed and fingerprint,
                              - these equal planned tokens.
                    - Determine target path from dictionary:
                        · data/layer1/3A/s4_zone_counts/seed={seed}/fingerprint={manifest_fingerprint}/…
                    - Immutability & idempotence:
                        · if partition does not exist:
                              - write via staging → fsync → atomic move into final path.
                        · if partition exists:
                              - read existing dataset, normalise to same schema + sort,
                              - if byte-identical to new rows → treat as idempotent re-run (optional no-op),
                              - else → immutability violation; MUST NOT overwrite.

Downstream touchpoints
----------------------
- **3A.S5 — Zone Allocation Egress & Routing Universe Hash:**
    - MUST treat s4_zone_counts as the **sole authority** on zone_site_count(m,c,z) and zone_site_count_sum(m,c).
    - MAY project S4 into cross-layer egress `zone_alloc`, but MUST NOT change integer counts or domain.
- **3A.S6 — Validation:**
    - MUST:
        · re-check that projection of s4_zone_counts onto (m,c) equals D_esc from S1,
        · re-check zone sets vs S2/S3 (Z(c)),
        · replay integerisation from (N, share_drawn) to confirm exact match with stored counts.
- **Later 3A / Layer-2 states needing zone-level counts:**
    - MUST derive all zone-level outlet counts from s4_zone_counts, not re-integerise S3’s shares independently.
- **Cross-segment analytics:**
    - MAY read s4_zone_counts (subject to 3A’s segment-level HashGate) for aggregate insights,
      but MUST respect that it is an internal planning surface and not a public cross-layer contract (that role belongs to `zone_alloc`).
```