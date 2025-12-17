```
                     LAYER 1 · SEGMENT 3A (Cross-Zone Merchants — In-Country Zone Allocation)

Authoritative inputs (sealed in 3A.S0)
--------------------------------------
[M] Upstream segment HashGates (must be PASS):
    - 1A validation_bundle_1A + _passed.flag_1A       @ [fingerprint={manifest_fingerprint}]
    - 1B validation_bundle_1B + _passed.flag_1B       @ [fingerprint]
    - 2A validation_bundle_2A + _passed.flag_2A       @ [fingerprint]
      · 3A.S0 replays each bundle’s SHA-256 law and enforces **No PASS → No read** on their egress.

[D] Upstream data-plane egresses (read-only; sealed via sealed_inputs_3A):
    - outlet_catalogue           @ [seed={seed}, fingerprint]    (1A egress; merchant×country×site stubs)
    - site_timezones             @ [seed, fingerprint]           (2A egress; per-site tzid)
    - tz_timetable_cache         @ [fingerprint]                 (2A transition cache; optional structural checks)
    - tz_world_2025a / country_tz_universe / iso3166_canonical_2024
      · define the **zone universe per country** Z(c).

[P] 3A policies & priors (parameter set for this parameter_hash):
    - zone_mixture_policy_3A     (S1: single-zone vs multi-zone escalation logic)
    - country_zone_alphas_3A     (S2: raw Dirichlet α-pack per country×tzid)
    - zone_floor_policy_3A       (S2/S4: floor/bump rules for α and integerisation)
    - day_effect_policy_v1       (2B policy; sealed for inclusion in the routing universe hash in S5)

[N] Identity & numeric/RNG posture:
    - Identity triple:
        · parameter_hash        — parameter-scoped priors, policies (S2).
        · manifest_fingerprint  — run-scoped sealing key for Layer 1.
        · seed                  — run-scoped, used only where RNG is consumed (S3).
    - Numeric:
        · IEEE-754 binary64, round-to-nearest-even, FMA/FTZ/DAZ disabled for decision maths.
    - RNG:
        · Only 3A.S3 consumes RNG (Philox 2×64-10, u∈(0,1) via Layer-1 law).
        · All other 3A states (S0, S1, S2, S4, S5, S6, S7) are RNG-free.
    - Partitioning:
        · S0, S6, S7: fingerprint-only.
        · S2: parameter_hash-only.
        · S1, S3, S4, S5 (zone_alloc): [seed, fingerprint].


DAG
---
(M,D,P,N) --> (S0) Gate & sealed inputs for 3A    [NO RNG]
                    - Verifies upstream gates for this manifest_fingerprint:
                        * 1A/1B/2A validation_bundle + _passed.flag.
                        * replays each bundle’s index+SHA256 law, checks `_passed.flag` content.
                    - Resolves and hashes **all external artefacts** 3A may use:
                        * outlet_catalogue, site_timezones, tz_world/country_tz_universe, tz_timetable_cache,
                          zone_mixture_policy_3A, country_zone_alphas_3A, zone_floor_policy_3A, day_effect_policy_v1, etc.
                    - Emits:
                        * s0_gate_receipt_3A@ [fingerprint]
                            · identity {parameter_hash, manifest_fingerprint, seed},
                            · upstream_gates status,
                            · sealed_policy_set, catalogue_versions.
                        * sealed_inputs_3A@ [fingerprint]
                            · table of {logical_id, path, schema_ref, sha256_hex, role} for all sealed external artefacts.
                    - S0 is RNG-free; defines the **input universe** 3A is allowed to read.

                                      |
                                      | s0_gate_receipt_3A, sealed_inputs_3A
                                      v

(S1) Mixture policy & escalation queue             [NO RNG]
    inputs: outlet_catalogue@ [seed, fingerprint],
            zone_mixture_policy_3A, iso3166_canonical_2024, tz_world_2025a/country_tz_universe
    -> s1_escalation_queue@ [seed, fingerprint]
         - Builds the **merchant×country domain**:
               D = { (merchant_id=m, legal_country_iso=c) | outlet_catalogue has ≥1 site }.
         - Derives per-pair site counts:
               site_count(m,c) = number of outlet rows for (m,c).
         - Derives per-country zone universes:
               Z(c) = set of tzid overlapping country c (from tz_world/country_tz_universe),
               zone_count_country(c) = |Z(c)|.
         - Applies zone_mixture_policy_3A deterministically per (m,c):
               (is_escalated, decision_reason) = f(site_count(m,c), zone_count_country(c), policy parameters…).
         - Emits one row per (m,c) with:
               site_count, zone_count_country, is_escalated, decision_reason,
               mixture_policy_id/version.
         - S1 is RNG-free and is the **sole authority** on:
               domain D, escalated domain D_esc ⊆ D, and site_count(m,c).

                                      |
                                      | s1_escalation_queue (D, D_esc, site_count)
                                      v

(S2) Country→zone priors & floors (α-surface)     [NO RNG]
    inputs: country_zone_alphas_3A, zone_floor_policy_3A,
            tz_world_2025a/country_tz_universe, iso3166_canonical_2024
    -> s2_country_zone_priors@ [parameter_hash]
         - Country domain:
               C_priors = countries appearing in priors and/or floor policy.
         - Zone universe:
               Z(c) = {tzid | (country_iso=c, tzid) in country_tz_universe or derived from tz_world}.
         - For each (c,z) in C_priors×Z(c):
               α_raw(c,z)         = value from prior pack (or deterministic default),
               α_effective(c,z)   = floor/bump-adjusted α from zone_floor_policy_3A,
               α_sum_country(c)   = sum_z α_effective(c,z) > 0,
               share_effective(c,z)= α_effective(c,z)/α_sum_country(c) (optional).
         - Emits one row per (c,z) with:
               alpha_raw, alpha_effective, alpha_sum_country, share_effective?,
               prior_pack_id/version, floor_policy_id/version, floor_applied, bump_applied.
         - S2 is parameter-scoped, RNG-free, and is the **sole prior surface** for S3.

                                      |
                                      | s2_country_zone_priors (α-surface)
                                      v

(S3) Zone share sampling (Dirichlet)             [RNG-BOUNDED]
    inputs: s1_escalation_queue@ [seed, fingerprint] (D_esc),
            s2_country_zone_priors@ [parameter_hash] (Z(c), α_effective),
            RNG policy (Philox, zone_dirichlet stream),
            Layer-1 RNG logs (rng_event_zone_dirichlet, rng_trace_log)
    -> s3_zone_shares@ [seed, fingerprint]
         - Worklist domain:
               D_esc = { (m,c) | is_escalated(m,c)=true } from S1.
               For each c, Z(c) from S2.
               S3 must sample for each (m,c) in D_esc and each z∈Z(c).
         - For each escalated (m,c):
               · collects α_effective(c,z) for z∈Z(c),
               · draws Gamma G_i ~ Gamma(α_i,1) via Philox,
               · normalises to Θ(m,c,z_i) = G_i / Σ_j G_j (Dirichlet),
               · logs exactly one rng_event_zone_dirichlet with counters, blocks, draws.
         - Emits one row per (m,c,z):
               share_drawn = Θ(m,c,z),
               share_sum_country(m,c) (≈1),
               alpha_sum_country(c),
               prior/floor lineage,
               RNG lineage (module, substream, stream_id, counters).
         - S3 is RNG-bounded; it is the **only stochastic layer** for zone shares.

                                      |
                                      | s1_escalation_queue, s2_country_zone_priors, s3_zone_shares
                                      v

(S4) Integer zone allocation (counts per m×c×z)   [NO RNG]
    inputs: s1_escalation_queue@ [seed, fingerprint] (site_count, D_esc),
            s2_country_zone_priors@ [parameter_hash] (Z(c)),
            s3_zone_shares@ [seed, fingerprint] (Θ(m,c,z), share_sum_country)
    -> s4_zone_counts@ [seed, fingerprint]
         - For each escalated (m,c):
               N(m,c) = site_count(m,c),
               Θ(m,c,z) = share_drawn(m,c,z) for z ∈ Z(c).
               Continuous targets:
                    T_z(m,c) = N(m,c) · Θ(m,c,z).
               Base counts:
                    b_z(m,c) = floor(T_z(m,c)),
                    base_sum = Σ_z b_z(m,c),
                    R        = N(m,c) − base_sum ≥ 0.
               Residual ranking:
                    residual r_z = T_z − b_z,
                    rank zones by (r_z DESC, tzid ASC),
                    assign +1 to top R zones.
               Final counts:
                    zone_site_count(m,c,z) = b_z(m,c) [+1 if in top R].
         - Ensures Σ_z zone_site_count(m,c,z) = site_count(m,c) for each (m,c).
         - Emits one row per (m,c,z) with:
               zone_site_count, zone_site_count_sum (N),
               share_sum_country(m,c),
               prior/floor lineage, optional fractional_target, residual_rank.
         - S4 is RNG-free; it is the **only authority** on integer zone-level counts.

                                      |
                                      | s1_escalation_queue, s2_country_zone_priors, s4_zone_counts
                                      v

(S5) Zone allocation egress & routing universe hash  [NO RNG]
    inputs: s1_escalation_queue@ [seed, fingerprint] (domain, site_count),
            s2_country_zone_priors@ [parameter_hash] (priors, Z(c)),
            s4_zone_counts@ [seed, fingerprint] (counts),
            zone_mixture_policy_3A, country_zone_alphas_3A, zone_floor_policy_3A, day_effect_policy_v1
    -> zone_alloc@ [seed, fingerprint]               (egress)
         - Projects S4 into cross-layer zone allocation:
               one row per (m,c,z) with:
                    zone_site_count(m,c,z),
                    zone_site_count_sum(m,c) = Σ_z counts,
                    site_count(m,c),
                    prior_pack_id/version,
                    floor_policy_id/version,
                    mixture_policy_id/version,
                    day_effect_policy_id/version,
                    routing_universe_hash (same for all rows).
         - Checks S4 vs S1:
               domain D_S4 = D_esc,
               per-(m,c) count conservation.

    -> zone_alloc_universe_hash@ [fingerprint]       (routing universe digest)
         - Computes component digests:
               zone_alpha_digest      = SHA256 bytes of s2_country_zone_priors@parameter_hash,
               theta_digest           = SHA256 bytes of zone_mixture_policy_3A,
               zone_floor_digest      = SHA256 bytes of zone_floor_policy_3A,
               day_effect_digest      = SHA256 bytes of day_effect_policy_v1,
               zone_alloc_parquet_digest = SHA256(bytes of zone_alloc Parquet files).
         - Computes:
               routing_universe_hash = SHA256(
                     zone_alpha_digest
                     || theta_digest
                     || zone_floor_digest
                     || day_effect_digest
                     || zone_alloc_parquet_digest
               ).
         - Writes JSON with:
               manifest_fingerprint, parameter_hash,
               the five component digests,
               routing_universe_hash.
         - Embeds routing_universe_hash into every zone_alloc row.
         - S5 is RNG-free; it exports the **cross-layer egress** for zone allocations and a unified hash
           tying priors, mixture, floor, day-effect policy, and allocation bytes together.

                                      |
                                      | s0, sealed_inputs, S1–S5 outputs, RNG logs
                                      v

(S6) Structural validation & segment audit          [NO RNG]
    inputs: s0_gate_receipt_3A, sealed_inputs_3A,
            outlet_catalogue, site_timezones, zone_mixture_policy_3A,
            s1_escalation_queue, s2_country_zone_priors, s3_zone_shares,
            s4_zone_counts, zone_alloc, zone_alloc_universe_hash,
            RNG logs for 3A.S3 (rng_event_zone_dirichlet, rng_trace_log, rng_audit_log)
    -> s6_validation_report_3A@ [fingerprint]
         - Runs a fixed set of checks:
               S0: gate & sealed_input consistency vs actual bundles/files.
               S1: domain coverage vs outlet_catalogue, site_count correctness, escalation decisions vs policy.
               S2: prior surface domain vs zone universe, α positivity, Z(c) correctness.
               S3: share domain = D_esc×Z(c), share_sum_country≈1, RNG accounting (one Dirichlet event per (m,c)).
               S4: domain alignment, count conservation.
               S5: zone_alloc vs S4, all S5 digests vs recomputed digests, routing_universe_hash coherence.
               Coherence: state self-reported statuses vs structural check outcomes.
         - Emits JSON summary:
               overall_status ∈ {PASS, FAIL},
               checks[] (id, status, severity, affected_count),
               metrics (counts, max deviations, RNG stats).

    -> s6_issue_table_3A@ [fingerprint] (optional)
         - Per-issue rows: {check_id, severity, code, message, entity keys…}.

    -> s6_receipt_3A@ [fingerprint]
         - Compact receipt:
               overall_status,
               check_status_map{check_id→status},
               report_digest = SHA256(report bytes),
               issues_digest = SHA256(issue table bytes or null),
               catalogue_versions.

                                      |
                                      | s0, sealed_inputs_3A, S0–S5 artefacts, s6_* outputs
                                      v

(S7) Validation bundle & `_passed.flag_3A`          [NO RNG]
    inputs: s0_gate_receipt_3A, sealed_inputs_3A,
            s1–s5 artefacts (listed above),
            s6_validation_report_3A, s6_issue_table_3A, s6_receipt_3A,
            (optional) RNG evidence member for S3
    -> validation_bundle_3A@ [fingerprint]   (index.json)
         - Precondition: S6 overall_status == "PASS".
         - Assembles a fixed member set:
               S0: gate, sealed_inputs;
               S1–S4: plan surfaces;
               S3 RNG evidence;
               S5: zone_alloc, zone_alloc_universe_hash;
               S6: validation_report, issue_table, receipt.
         - For each member:
               compute canonical SHA256 digest over bytes.
         - Writes index.json (schema: validation_bundle_index_3A) with:
               manifest_fingerprint, parameter_hash,
               members[{logical_id, path, schema_ref, sha256_hex, role,…}].

    -> `_passed.flag_3A`@ [fingerprint]
         - Computes bundle_sha256_hex = SHA256(concat(all member.sha256_hex in canonical order)).
         - Writes `_passed.flag_3A` as:
               `sha256_hex = <bundle_sha256_hex>`
           (single line).
         - Together, index.json + `_passed.flag_3A` form the **3A HashGate** for this manifest.

Downstream obligations
----------------------
- Any consumer of 3A outputs (especially `zone_alloc` and `zone_alloc_universe_hash`) MUST:
    1) Read `validation_bundle_3A/index.json` for this manifest_fingerprint,
    2) Recompute bundle_sha256_hex from its members’ sha256_hex values,
    3) Read `_passed.flag_3A`,
    4) Require flag.sha256_hex == recomputed bundle SHA,
   and enforce:

       **No 3A PASS (bundle+flag+S6 PASS) → No read** of:
           - s1_escalation_queue, s2_country_zone_priors, s3_zone_shares,
           - s4_zone_counts, zone_alloc, zone_alloc_universe_hash.

Legend
------
(Sx) = state in Segment 3A
[seed, fingerprint]    = run-scoped partitions
[parameter_hash]       = parameter-scoped partitions
[fingerprint]          = manifest-scoped partitions
[NO RNG]               = state consumes no RNG
[RNG-BOUNDED]          = state uses governed Philox with explicit RNG logs
HashGate (3A)          = validation_bundle_3A@ [fingerprint] + `_passed.flag_3A`
```