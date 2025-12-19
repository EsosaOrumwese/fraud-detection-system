```
        LAYER 1 · SEGMENT 3A — STATE S3 (ZONE SHARE SAMPLING — DIRICHLET DRAWS)  [RNG-BOUNDED]

Authoritative inputs (read-only at S3 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_3A
      @ data/layer1/3A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3A.json
      · proves: 3A.S0 ran for this manifest_fingerprint
      · binds: {parameter_hash, manifest_fingerprint, seed} for Segment 3A
      · records: upstream_gates.{segment_1A,segment_1B,segment_2A}.status == "PASS"
      · records: sealed_policy_set (includes country_zone_alphas, zone_floor_policy, any RNG layout policy)
    - sealed_inputs_3A
      @ data/layer1/3A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3A.parquet
      · sealed inventory of all artefacts 3A is allowed to read for this manifest_fingerprint
      · any cross-segment / policy artefact S3 reads MUST appear here with matching {logical_id, path, sha256_hex}

[Schema+Dict · catalogue authority]
    - schemas.layer1.yaml
        · RNG envelopes, rng_audit_log, rng_trace_log, rng_event.* schemas
        · primitive types: id64, iso2, iana_tzid, hex64, uint64, …
    - schemas.3A.yaml
        · plan/s1_escalation_queue, plan/s2_country_zone_priors, plan/s3_zone_shares
    - dataset_dictionary.layer1.3A.yaml
        · ID→path/partition/schema_ref for s1_escalation_queue, s2_country_zone_priors, s3_zone_shares
    - artefact_registry_3A.yaml
        · metadata for 3A artefacts (non-authoritative for shape)

[3A plan surfaces (authorities from earlier states)]
    - s1_escalation_queue
        · producer: 3A.S1
        · partition: seed={seed} / manifest_fingerprint={manifest_fingerprint}
        · PK/sort: [merchant_id, legal_country_iso]
        · columns (min):
              seed, manifest_fingerprint,
              merchant_id, legal_country_iso,
              site_count ≥ 1,
              zone_count_country ≥ 0,
              is_escalated (boolean),
              decision_reason,
              mixture_policy_id, mixture_policy_version,
              theta_digest (optional)
        · role: defines D = {(m,c)} and D_esc = {(m,c) | is_escalated=true} — S3 MUST NOT change these
    - s2_country_zone_priors
        · producer: 3A.S2
        · partition: parameter_hash={parameter_hash}
        · PK/sort: [country_iso, tzid]
        · columns (min):
              parameter_hash,
              country_iso, tzid,
              alpha_raw ≥ 0,
              alpha_effective > 0,
              alpha_sum_country > 0,
              prior_pack_id, prior_pack_version,
              floor_policy_id, floor_policy_version,
              floor_applied, bump_applied,
              share_effective (optional), notes
        · role: prior authority for α; S3 MUST NOT re-derive α from raw configs

[RNG policy & event family]
    - Layer-1 RNG policy / 3A RNG layout policy (if present)
        · sealed in s0_gate_receipt_3A.sealed_policy_set + sealed_inputs_3A
        · defines:
              • engine = Philox 2×64-10,
              • mapping from (seed, parameter_hash, run_id, module, substream_label, rng_stream_id)
                → stream key / base counter,
              • RNG envelope (`blocks`, `draws` semantics),
              • rng_trace_log aggregation.
    - RNG event family: rng_event_zone_dirichlet
        · schema anchor in schemas.layer1.yaml#/rng/events/zone_dirichlet
        · partition keys: [seed, parameter_hash, run_id]
        · fields (min): seed, parameter_hash, run_id,
                        module, substream_label,
                        rng_stream_id,
                        counter_before, counter_after,
                        blocks, draws,
                        merchant_id, country_iso, zone_count,
                        optional diagnostics.

[Output surfaces owned by S3]
    - s3_zone_shares
      @ data/layer1/3A/s3_zone_shares/seed={seed}/fingerprint={manifest_fingerprint}/…
      · partition_keys: [seed, fingerprint]
      · primary_key:    [merchant_id, legal_country_iso, tzid]
      · sort_keys:      [merchant_id, legal_country_iso, tzid]
      · columns_strict: true
      · columns:
            seed, fingerprint,
            merchant_id, legal_country_iso, tzid,
            share_drawn ∈ [0,1],
            share_sum_country > 0,
            alpha_sum_country > 0,
            prior_pack_id, prior_pack_version,
            floor_policy_id, floor_policy_version,
            rng_module, rng_substream_label, rng_stream_id,
            rng_event_id (optional), notes (optional)
    - RNG surfaces (shared, run-scoped):
        · rng_event_zone_dirichlet        @ [seed, parameter_hash, run_id]
        · rng_trace_log / rng_audit_log   @ [seed, parameter_hash, run_id] (updated, not created by S3)

[Numeric & RNG posture]
    - RNG-bearing:
        · S3 consumes RNG; all randomness comes from Philox 2×64-10 using Layer-1 u01 mapping.
        · **Exactly one Dirichlet event per escalated (m,c)**; all uniforms used for Gamma draws are accounted via:
              rng_event_zone_dirichlet events + rng_trace_log totals.
    - Determinism:
        · Given fixed (seed, parameter_hash, manifest_fingerprint, run_id) and catalogue,
          S3 must be deterministic conditional on the RNG stream.
    - Numeric:
        · IEEE-754 binary64, round-to-nearest-even; no FMA/FTZ/DAZ.
        · Serial reductions only (e.g. sums over zones); no data-dependent reordering.


----------------------------------------------------------------------
DAG — 3A.S3 (escalation queue + priors → Dirichlet zone shares)  [RNG-BOUNDED]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S3.1) Fix run identity
                    - Inputs from orchestrator:
                        · parameter_hash (hex64),
                        · manifest_fingerprint (hex64),
                        · seed (uint64),
                        · run_id (string / u128-encoded).
                    - Validate formats and treat the tuple:
                        (seed, parameter_hash, manifest_fingerprint, run_id)
                      as immutable for the run.
                    - S3 SHALL embed these consistently into:
                        · rng_event_zone_dirichlet,
                        · rng_trace_log / rng_audit_log,
                        · but `s3_zone_shares` is partitioned only by (seed, fingerprint).

[Schema+Dict],
[S0 Gate & Identity]
                ->  (S3.2) Load S0 artefacts (gate & whitelist)
                    - Resolve via the 3A dictionary:
                        · s0_gate_receipt_3A@fingerprint={manifest_fingerprint},
                        · sealed_inputs_3A@fingerprint={manifest_fingerprint}.
                    - Validate:
                        · s0_gate_receipt_3A schema-valid,
                        · sealed_inputs_3A schema-valid.
                    - From `upstream_gates` in S0:
                        · require: segment_1A.status == "PASS",
                                  segment_1B.status == "PASS",
                                  segment_2A.status == "PASS".
                      Failure ⇒ hard precondition failure; S3 MUST NOT proceed.

[Schema+Dict],
sealed_inputs_3A
                ->  (S3.3) Load S1 escalation queue (domain & flags)
                    - Resolve s1_escalation_queue via dictionary:
                        · path: data/layer1/3A/s1_escalation_queue/seed={seed}/fingerprint={manifest_fingerprint}/…
                    - Validate against schemas.3A.yaml#/plan/s1_escalation_queue.
                    - Define domain:
                        · D = { (merchant_id=m, legal_country_iso=c) } from all rows.
                    - Interpret is_escalated flags:
                        · D_esc = { (m,c) ∈ D | is_escalated(m,c) = true }.
                    - S3 MUST treat:
                        · D and is_escalated as authoritative from S1,
                        · MUST NOT escalate or de-escalate pairs on its own.

[Schema+Dict],
sealed_inputs_3A
                ->  (S3.4) Load S2 prior surface (α-vectors)
                    - Resolve s2_country_zone_priors via dictionary:
                        · path: data/layer1/3A/s2_country_zone_priors/parameter_hash={parameter_hash}/…
                    - Validate against schemas.3A.yaml#/plan/s2_country_zone_priors.
                    - For each country_iso=c appearing in S2:
                        · define Z(c) = { tzid | (country_iso=c, tzid) appears in S2 }.
                    - S3 MUST treat Z(c) and alpha_effective(c,z) as given:
                        · S2 is the sole authority on priors.

[S1 escalation queue D_esc],
[S2 priors],
[Schema+Dict]
                ->  (S3.5) Build escalated worklist D_esc and coverage checks
                    - Define:
                        · D_esc = { (m,c) ∈ D | is_escalated(m,c)=true }.
                        · C_esc = { c | (m,c) ∈ D_esc }.
                    - Ordering:
                        · sort D_esc by (merchant_id ASC, legal_country_iso ASC).
                        · This sorted order defines the **event order** for Dirichlet draws.
                    - Coverage:
                        - For each c ∈ C_esc:
                              check S2 has at least one row with country_iso=c.
                          If any c ∈ C_esc has no S2 rows → S3 MUST fail (priors incomplete for an escalated country).

[S2 priors per country],
C_esc
                ->  (S3.6) Derive per-country ordered zones Z_ord(c)
                    - For each c ∈ C_esc:
                        · gather all S2 rows with country_iso = c,
                        · sort by tzid ASCII ascending to obtain:
                              Z_ord(c) = [z_1, …, z_K(c)],
                              α_i = alpha_effective(c, z_i) > 0.
                    - Check:
                        · K(c) ≥ 1 for each c ∈ C_esc,
                        · all α_i > 0 for each component.
                    - These Z_ord(c) and α-vectors MUST be used consistently in all later per-(m,c) draws.

[S2 priors per country],
C_esc
                ->  (S3.7) Join prior metadata per country
                    - For each c ∈ C_esc:
                        · read alpha_sum_country(c) from any row with that country_iso in S2
                          (all rows for c MUST agree),
                        · read constant prior pack metadata:
                              prior_pack_id, prior_pack_version,
                              floor_policy_id, floor_policy_version,
                          which MUST be constant for this parameter_hash across S2.
                    - These metadata will be written on all s3_zone_shares rows for escalated (m,c).

[Schema+Dict],
sealed_inputs_3A,
s0_gate_receipt_3A
                ->  (S3.8) Resolve RNG policy & event family
                    - Using sealed_inputs_3A + s0_gate_receipt_3A.sealed_policy_set:
                        · locate Layer-1 RNG policy and any 3A-specific RNG layout policy for S3.
                    - From these and the Layer-1 spec, S3 MUST fix:
                        · module              = "3A.S3" (or equivalent agreed constant),
                        · substream_label     = "zone_dirichlet" (or equivalent),
                        · the mapping:
                              (seed, parameter_hash, run_id, module, substream_label, rng_stream_id)
                              → Philox stream key / base counter.
                    - S3 MUST respect the Layer-1 envelope:
                        · u01 mapping, counter handling, blocks/draws semantics, rng_trace_log discipline.

[D_esc],
RNG policy (module, substream_label mapping)
                ->  (S3.9) Define event order & stream keying per (m,c)
                    - Iterate D_esc in fixed order:
                        · sort by merchant_id ASC, then legal_country_iso ASC.
                    - For each (m,c) in that order:
                        · compute rng_stream_id deterministically from (m,c),
                          e.g. via hashing (module, substream_label, merchant_id, country_iso).
                        · treat the tuple:
                              (seed, parameter_hash, run_id, module, substream_label, rng_stream_id)
                          as the unique identifier for the Philox stream used for this Dirichlet sample.
                    - S3 MUST NOT depend on physical row order in S1 or any map iteration order.

For each (m,c) ∈ D_esc in this fixed order:
------------------------------------------------

(Z_ord(c), α_i, alpha_sum_country(c)),
RNG engine (stream for (m,c))
                ->  (S3.10) Snapshot Philox counter BEFORE sampling
                    - Query the RNG subsystem for this stream:
                        · capture counter_before (full 128-bit value) immediately before ANY uniforms for this event.
                    - S3 MUST NOT consume any other uniforms between capturing counter_before and starting Gamma draws
                      for this event.

(Z_ord(c), α_i),
Philox stream @ (m,c)
                ->  (S3.11) Draw Gamma variates G_i (Dirichlet via Gamma)
                    - Let K = |Z_ord(c)| and α_i = alpha_effective(c,z_i) for i=1..K.
                    - For i = 1..K:
                        · draw Gamma variate G_i ~ Gamma(α_i, 1) using Philox u01 uniforms,
                          via the Layer-1 Gamma implementation (which defines how many uniforms each G_i consumes).
                        · let draws_i = number of u01 uniforms consumed for this G_i.
                    - Define:
                        · draws_total(m,c) = Σ_i draws_i.
                    - Implementation of the Gamma algorithm is defined at Layer-1; S3 cares only about:
                        · the values {G_i},
                        · how many uniforms were consumed (draws_total).

{G_i} for i=1..K
                ->  (S3.12) Normalise to Dirichlet shares Θ(m,c,·)
                    - Compute:
                        · S = Σ_{i=1..K} G_i.
                    - Require:
                        · S > 0; otherwise treat as numeric failure and abort.
                    - For each i:
                        · Θ(m,c,z_i) = G_i / S.
                    - Define:
                        · share_drawn(m,c,z_i) = Θ(m,c,z_i),
                        · share_sum_country(m,c) = Σ_i Θ(m,c,z_i) (stored as-is; small fp deviation from 1 allowed).
                    - S3 MUST NOT “fix up” Θ in ways that change the underlying sample; it only records any Σ≠1 deviation.

Philox stream @ (m,c) AFTER Gamma & normalisation,
draws_total(m,c)
                ->  (S3.13) Snapshot Philox counter AFTER sampling
                    - Capture counter_after (128-bit) for this stream.
                    - Compute:
                        · blocks = counter_after − counter_before (as per Layer-1 definition),
                        · draws  = draws_total(m,c).
                    - Require:
                        · blocks * BLOCK_SIZE_UNIFORMS ≥ draws,
                        · draws equals the actual number of u01 calls used in Gamma draws.

RNG meta (module, substream_label, rng_stream_id, counters, blocks, draws),
(m,c), K,
alpha_sum_country(c)
                ->  (S3.14) Emit rng_event_zone_dirichlet event
                    - Append exactly one event row for this Dirichlet sample to the standard RNG events dataset:
                        · fields (min):
                              seed, parameter_hash, run_id,
                              module, substream_label,
                              rng_stream_id,
                              counter_before, counter_after,
                              blocks, draws,
                              merchant_id = m,
                              country_iso = c,
                              zone_count = K,
                              optional diagnostics (e.g. alpha_sum_country(c)).
                    - Partition: [seed, parameter_hash, run_id].
                    - S3 MUST NOT write RNG events anywhere else.

shares Θ(m,c,z_i),
alpha_sum_country(c),
prior metadata for c (pack & floor),
RNG meta for (m,c)
                ->  (S3.15) Stage s3_zone_shares rows for this (m,c)
                    - For each i = 1..K (zone z_i ∈ Z_ord(c)):
                        · stage a row with:
                              seed                  = seed,
                              fingerprint           = manifest_fingerprint,
                              merchant_id           = m,
                              legal_country_iso     = c,
                              tzid                  = z_i,
                              share_drawn           = Θ(m,c,z_i),
                              share_sum_country     = share_sum_country(m,c),
                              alpha_sum_country     = alpha_sum_country(c),
                              prior_pack_id         = prior_pack_id,
                              prior_pack_version    = prior_pack_version,
                              floor_policy_id       = floor_policy_id,
                              floor_policy_version  = floor_policy_version,
                              rng_module            = module,
                              rng_substream_label   = substream_label,
                              rng_stream_id         = rng_stream_id,
                              rng_event_id          = optional link to the event emitted in (S3.14),
                              notes                 = optional deterministic diagnostics or null.
                    - Rows remain staged; S3 does NOT write the dataset yet.

After processing all (m,c) ∈ D_esc:
-----------------------------------

All staged rows
                ->  (S3.16) Build complete row set & enforce domain constraints
                    - Let D_S3 = {(m,c,z)} from all staged rows.
                    - Require:
                        · No rows for any (m,c) with is_escalated=false,
                        · No rows where tzid ∉ Z(c),
                        · For each (m,c) ∈ D_esc:
                              rows exist for every z_i ∈ Z_ord(c) (no missing zones).
                    - If any constraint fails, S3 MUST treat this run as failed and MUST NOT publish s3_zone_shares.

D_S3 rows,
[Schema+Dict]
                ->  (S3.17) Sort, validate & publish s3_zone_shares
                    - Sort rows by (merchant_id ASC, legal_country_iso ASC, tzid ASC).
                    - Validate against schemas.3A.yaml#/plan/s3_zone_shares:
                        · columns_strict, PK uniqueness, numeric constraints.
                    - Determine target path via dictionary:
                        · data/layer1/3A/s3_zone_shares/seed={seed}/fingerprint={manifest_fingerprint}/…
                    - Immutability:
                        · if partition is empty → write staged rows (staging → fsync → atomic move).
                        · if partition exists:
                              - read and normalise existing rows (same schema, same sort),
                              - if byte-identical to staged rows → optional no-op or rewrite with identical bytes,
                              - otherwise → treat as immutability violation; MUST NOT overwrite.

rng_event_zone_dirichlet events (all (m,c)),
[Schema+Dict],
RNG policy
                ->  (S3.18) Update rng_trace_log totals
                    - Using Layer-1 RNG trace rules:
                        · compute:
                              blocks_total = Σ blocks over all rng_event_zone_dirichlet events for this run,
                              draws_total  = Σ draws  over the same events.
                        · append or update a single rng_trace_log record for:
                              (seed, parameter_hash, run_id, module, substream_label="zone_dirichlet"),
                          such that:
                              trace.blocks_total == blocks_total,
                              trace.draws_total  == draws_total.
                    - S3 MUST NOT modify trace entries for other modules/substreams.

Downstream touchpoints
----------------------
- **3A.S4 — Integer zone allocation:**
    - MUST treat s3_zone_shares as the **sole stochastic planning surface** over zones:
        · may read share_drawn(m,c,z) and share_sum_country(m,c) for escalated pairs,
        · MUST NOT re-sample Dirichlet vectors or alter Θ(m,c,·).
- **3A.S5 — Zone allocation egress:**
    - May aggregate and project S3’s shares (via S4 counts) but MUST preserve S3’s α lineage and RNG lineage.
- **3A.S6 — Validation:**
    - Validates:
        · D_S3 domain vs D_esc × Z(c),
        · α_sum_country consistency with S2,
        · RNG accounting: one rng_event_zone_dirichlet per escalated (m,c), rng_trace_log totals vs events.
- **Cross-segment consumers (2B, routing tooling):**
    - MUST NOT read s3_zone_shares directly as a cross-layer contract;
      cross-layer visibility is via zone_alloc and the 3A validation bundle / `_passed.flag_3A`.
```