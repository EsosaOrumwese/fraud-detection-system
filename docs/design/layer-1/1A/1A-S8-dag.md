```
                LAYER 1 · SEGMENT 1A — STATE S8 (OUTLET CATALOGUE & SEQUENCES)  [NO RNG DRAWS]

Authoritative inputs (read-only at S8 entry)
--------------------------------------------
[S3] Inter-country domain & order (sole authority):
    - s3_candidate_set @ [parameter_hash]
      · schema: schemas.1A.yaml#/s3/candidate_set
      · one row per merchant_id × country_iso (home + foreigns)
      · guarantees:
          * exactly one home row (is_home=true, candidate_rank=0)
          * foreign rows have candidate_rank>0, contiguous per merchant
          * candidate_rank is the **only** cross-country order authority

[Cnt] Count facts (merchant N and per-country integers):
    - rng_event.nb_final @ [seed, parameter_hash, run_id]
      · schema: schemas.layer1.yaml#/rng/events/nb_final
      · exactly one row per resolved merchant
      · payload (core): merchant_id, n_outlets=N≥2, mu, dispersion_k, nb_rejections
      · non-consuming finaliser (before==after; blocks=0; draws="0")
    - Variant A (preferred when present) — s3_integerised_counts @ [parameter_hash]
      · schema: schemas.1A.yaml#/s3/integerised_counts
      · per (merchant_id, country_iso): count≥0, residual_rank
      · if present, S8 **MUST** read and treat `count` as authoritative nᵢ
    - Variant B (no S3 counts surface) — rng_event.residual_rank @ [seed, parameter_hash, run_id]
      · schema: schemas.layer1.yaml#/rng/events/residual_rank
      · per (merchant_id, country_iso) in Dₘ:
          * payload carries N and per-country count (and residual_rank) from S7
      · deprecated ranking_residual_cache_1A is **not** an authority; S8 MUST NOT read it

[S6] Membership & multi-site gating:
    - Option 1 (convenience membership surface):
        · s6_membership @ [seed, parameter_hash]  (if S6 policy emits it)
          - schema: schemas.1A.yaml#/s6/membership
          - PK: (merchant_id, country_iso); foreigns only; no order encoded
          - read allowed only if S6 PASS receipt present (see [G])
    - Option 2 (authoritative log reconstruction):
        · rng_event.gumbel_key @ [seed, parameter_hash, run_id]
        · rng_event.ztp_final  @ [seed, parameter_hash, run_id]
          - combined with S3 candidate_set to reconstruct S6-selected foreigns
    - rng_event.hurdle_bernoulli @ [seed, parameter_hash, run_id]
      · used via Dictionary gating: S8 writes **only** multi-site merchants (is_multi==true)

[Seq] Optional upstream sequencing (S3 owns sequence):
    - s3_site_sequence @ [parameter_hash]   (optional)
      · schema: schemas.1A.yaml#/s3/site_sequence
      · per (merchant_id, country_iso, site_order) with site_order 1..count_i
      · if present, S8 **cross-checks** only; sequence semantics owned by S3

[N] Numeric / math profile (deterministic):
    - numeric_policy.json
    - math_profile_manifest.json
      · IEEE-754 binary64, RN-even, FMA-OFF, no FTZ/DAZ
      · deterministic libm; no data-dependent reordering
      · used for sum checks & any replays, but **S8 does not derive counts itself**

[G] Run / lineage context & PASS gates:
    - {seed, parameter_hash, manifest_fingerprint, run_id}
    - rng_audit_log @ [seed, parameter_hash, run_id]    (run-scoped)
    - rng_trace_log @ [seed, parameter_hash, run_id]    (per (module, substream_label))
    - S6 PASS gate (for reading s6_membership):
        · s6_validation_receipt + _passed.flag under
          data/layer1/1A/s6/seed={seed}/parameter_hash={parameter_hash}/
        · **No PASS → no read** of s6_membership
    - S5 PASS: S8 **SHOULD NOT** read S5; if any implementation touches S5, it must honour S5’s own PASS gate

[Dict] Dictionary & registry anchors:
    - dataset_dictionary.layer1.1A.yaml
      · IDs/paths/partitioning for:
          * outlet_catalogue
          * s3_candidate_set / s3_integerised_counts / s3_site_sequence
          * s6_membership
          * rng_event.sequence_finalize
          * rng_event.site_sequence_overflow
    - artefact_registry_1A.yaml
      · enumerates S8’s ownership of outlet_catalogue and S8 RNG event families
      · ties this spec’s version into manifest_fingerprint closure


----------------------------------------------------------------- DAG (S8.1–S8.9 · materialise outlet stubs & sequences; instrumentation-only RNG)

[S3],[Cnt],[S6],
[Seq],[G],[Dict]   ->  (S8.1) Pre-flight gates & context assembly
                          - Resolve all dataset locations via the Dictionary (no literal paths).
                          - Enforce PASS gates:
                              * if s6_membership is read:
                                  – verify S6 receipt + _passed.flag for same {seed,parameter_hash}
                                  – **No PASS → no read** (E_PASS_GATE_MISSING; abort before any egress).
                              * S5 surfaces MUST NOT be read by S8 (weights authority stays with S5/S6/S7).
                          - Per merchant m:
                              * assert:
                                  – one nb_final row (N:=n_outlets≥2)
                                  – S3 candidate_set present, schema-valid, with:
                                      · exactly one home, candidate_rank=0
                                      · contiguous foreign ranks >0
                              * determine counts source:
                                  – if s3_integerised_counts exists:
                                      · use it as authoritative per-country counts surface (Variant A)
                                  – else:
                                      · plan to use S7 residual evidence via rng_event.residual_rank (Variant B)
                              * ensure **some** counts source exists:
                                  – if neither Variant A nor B is available ⇒ E_COUNTS_SOURCE_MISSING (run abort)
                          - No rows or events written yet; no RNG draws; just gating & shape checks.

[S3],[S6],[Seq],
[Cnt],[N]          ->  (S8.2) Domain Dₘ, membership & counts resolution per merchant
                          - For each merchant m that passed S8.1:
                              1) Domain source:
                                  · start from S3 candidate_set rows (home + foreigns)
                                  · reconstruct S6-selected foreign membership:
                                      – prefer s6_membership (if present & PASSed)
                                      – otherwise, replay selection from rng_event.gumbel_key + rng_event.ztp_final + S3
                                  · build legal domain Dₘ = {home} ∪ selected_foreigns
                                  · if selected_foreigns empty or K_target=0 ⇒ Dₘ = {home} only
                              2) Counts resolution:
                                  · Variant A (s3_integerised_counts present):
                                      – read count_i for each country in S3 domain
                                      – restrict to Dₘ: nᵢ = count_i for each legal_country_iso∈Dₘ
                                  · Variant B (no s3_integerised_counts):
                                      – read rng_event.residual_rank rows for (merchant,country) in Dₘ
                                      – derive nᵢ from payload (per S7 spec) for each country in Dₘ
                              3) Structural checks:
                                  · nᵢ ≥ 0 for all i; sum law: Σ_{i∈Dₘ} nᵢ == N from nb_final
                                  · if any nᵢ < 0 or sum ≠ N ⇒ E_COUNTS_MISMATCH (merchant FAIL)
                              4) Membership / domain integrity:
                                  · Dₘ countries must be subset of S3 candidate_set domain
                                  · no rows for countries outside Dₘ
                                  · S8 MUST NOT read legacy country_set or ranking_residual_cache_1A for domain/order.
                          - Output per merchant (ephemeral):
                              * N, Dₘ (ordered by S3.candidate_rank), and per-country counts nᵢ
                              * multi-site scope: only merchants with is_multi==true (S1) are retained for egress.

[S3],[Seq],
Dₘ, nᵢ           ->  (S8.3) Within-country sequencing & overflow detection
                          - For each merchant m and each legal_country_iso∈Dₘ with nᵢ>0:
                              * if s3_site_sequence exists (S3 owns sequence):
                                  – cross-check:
                                      · s3_site_sequence rows for (m,c) have site_order 1..nᵢ
                                      · count of rows == nᵢ
                                      · no gaps/dupes
                                  – any divergence ⇒ E_SEQUENCE_DIVERGENCE (abort; no rows for m)
                                  – S8 uses S3’s sequence semantics; MUST NOT rewrite them.
                              * else (sequence owned by S8):
                                  – construct local sequence:
                                      · site_order = 1..nᵢ (contiguous)
                                      · site_id   = zfill6(site_order)
                              * Overflow law:
                                  – if nᵢ > 999999:
                                      · DO NOT emit any egress rows for merchant m
                                      · this country (and effectively the merchant) handled via overflow event in S8.4
                          - For any (m,c) with nᵢ==0:
                              * S8 emits **no** rows in outlet_catalogue and **no** sequence_finalize for that (m,c).

Dₘ, nᵢ,
[G],[Dict]        ->  (S8.4) Instrumentation events (sequence_finalize & overflow)  [non-consuming RNG events]
                          - For each merchant m, country c with 1 ≤ nᵢ ≤ 999999:
                              * emit exactly one rng_event.sequence_finalize row:
                                  · path: logs/rng/events/sequence_finalize/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…
                                  · envelope:
                                      – module="1A.site_id_allocator"
                                      – substream_label="sequence_finalize"
                                      – rng_counter_before == rng_counter_after
                                      – blocks = 0, draws = "0"    (non-consuming family)
                                  · payload:
                                      – merchant_id, country_iso=c
                                      – site_count = nᵢ
                                      – start_sequence = "000001"
                                      – end_sequence   = zfill6(nᵢ)
                              * append one rng_trace_log row (module="1A.site_id_allocator", substream_label="sequence_finalize")
                          - For any merchant/country with nᵢ > 999999:
                              * emit rng_event.site_sequence_overflow:
                                  · path: logs/rng/events/site_sequence_overflow/…
                                  · envelope: non-consuming (before==after; blocks=0; draws="0")
                                  · payload (core): merchant_id, country_iso, attempted_count=nᵢ, max_seq=999999,
                                                     overflow_by = nᵢ − 999999, severity="ERROR"
                              * append one rng_trace_log row for substream_label="site_sequence_overflow"
                              * mark merchant as FAILED for S8 (no outlet_catalogue rows for this merchant)
                          - Gating:
                              * both S8 event families are Dictionary-gated:
                                  – gated_by: rng_event_hurdle_bernoulli
                                  – predicate: is_multi == true
                              * S8 MUST NOT emit these events for single-site merchants.

Dₘ, nᵢ,
site_order/id,
N, [G],[Dict]     ->  (S8.5) Build & write outlet_catalogue rows
                          - For each merchant m that has not failed and each country c∈Dₘ with nᵢ≥1:
                              * emit one row per site_order k ∈ {1..nᵢ}:
                                  · merchant_id                  = m
                                  · home_country_iso             = S3.home_country_iso(m)
                                  · legal_country_iso            = c
                                  · single_vs_multi_flag         = true  (copy of S1 hurdle outcome)
                                  · site_order                   = k
                                  · site_id                      = zfill6(k)   (or cross-checked S3.site_id)
                                  · raw_nb_outlet_draw           = N (identical for all rows for m)
                                  · final_country_outlet_count   = nᵢ (identical for all rows for (m,c))
                                  · global_seed                  = seed
                                  · manifest_fingerprint         = fingerprint (from path)
                          - Egress dataset & partitions:
                              * id: outlet_catalogue
                              * schema: schemas.1A.yaml#/egress/outlet_catalogue
                              * path: data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/
                              * partitioning: [seed, fingerprint]
                              * writer sort: [merchant_id, legal_country_iso, site_order]
                          - Path↔embed equality (egress):
                              * embedded manifest_fingerprint MUST equal fingerprint path token (lowercase hex64)
                              * embedded seed MUST equal seed path token (uint64)
                          - PK law:
                              * (merchant_id, legal_country_iso, site_order) UNIQUE in the partition.

all above,
[N],[G],[Dict]   ->  (S8.6) Invariants, failure modes & behavioural checks
                          - Row/sequence invariants (per (m,c)):
                              * site_order is exactly {1..nᵢ} (no gaps/dupes)
                              * number of rows with (m,c) equals nᵢ
                              * site_id is bijective with site_order within block; matches ^[0-9]{6}$
                          - Sum & domain invariants (per merchant m):
                              * raw_nb_outlet_draw is constant across all rows for m and equals N from nb_final
                              * Σ_{c∈Dₘ} final_country_outlet_count == N
                              * for each (m,c) with any rows: final_country_outlet_count == count(rows for (m,c))
                              * distinct legal_country_iso in outlet_catalogue for m equals Dₘ (no missing, no extras)
                          - Authority boundaries:
                              * S3.s3_candidate_set remains sole cross-country order authority:
                                  – outlet_catalogue encodes sets only; no cross-country ordering
                              * S2/S7/S3 remain counts authorities:
                                  – S8 copies N and nᵢ, **no** re-allocation or re-derivation
                              * S5 remains weights authority:
                                  – S8 MUST NOT read or persist any weight surfaces
                          - RNG invariants for S8 streams:
                              * sequence_finalize and site_sequence_overflow are non-consuming:
                                  – for every event: after==before, blocks=0, draws="0"
                              * exactly one sequence_finalize per (merchant, country) with nᵢ≥1 (and not overflow-failed)
                              * site_sequence_overflow present iff nᵢ>999999 (and non-consuming)
                              * rng_trace_log totals for these substreams reconcile with per-event envelopes
                          - Failure classes (mapped to S0/S9 error contract), e.g.:
                              * E_PASS_GATE_MISSING (S6 receipt missing for s6_membership read)
                              * E_COUNTS_SOURCE_MISSING / E_COUNTS_MISMATCH
                              * E_SEQUENCE_DIVERGENCE (when s3_site_sequence exists but disagrees)
                              * E_SCHEMA_INVALID / E_PATH_EMBED_MISMATCH
                              * E_EVENT_COVERAGE (sequence_finalize/site_sequence_overflow coverage or trace mismatches)

all checks pass,
[G],[Dict]       ->  (S8.7) Publication & immutability
                          - Atomic publish:
                              * stage outlet_catalogue files to temp location
                              * fsync, then atomically move into the Dictionary path
                              * no partial contents may become visible
                          - Idempotence:
                              * re-publishing the same (seed,fingerprint) partition must:
                                  – either be a no-op, or
                                  – yield byte-identical contents to the first publish
                          - Immutability:
                              * once outlet_catalogue for (seed,fingerprint) is published, **no changes** are allowed
                          - S8 does not own any additional Parquet or JSONL families beyond:
                              * outlet_catalogue
                              * rng_event.sequence_finalize
                              * rng_event.site_sequence_overflow
                              * their corresponding rng_trace_log entries


State boundary (authoritative outputs of S8)
-------------------------------------------
- outlet_catalogue                        @ [seed, fingerprint]
    * primary egress: immutable outlet stubs and sequences per (merchant_id, legal_country_iso, site_order).
    * PK/UK: (merchant_id, legal_country_iso, site_order).
    * columns (core): merchant_id, home_country_iso, legal_country_iso,
                      single_vs_multi_flag, site_order, site_id,
                      raw_nb_outlet_draw, final_country_outlet_count,
                      global_seed, manifest_fingerprint.
    * writes **only** multi-site merchants.

- rng_event.sequence_finalize             @ [seed, parameter_hash, run_id]
    * exactly one non-consuming event per (merchant_id, country_iso) with nᵢ∈[1,999999].
    * payload: merchant_id, country_iso, site_count=nᵢ,
               start_sequence="000001", end_sequence=zfill6(nᵢ).

- rng_event.site_sequence_overflow        @ [seed, parameter_hash, run_id]
    * non-consuming guardrail events when nᵢ>999999; no outlet_catalogue rows for that merchant.

- rng_trace_log rows for S8 substreams
    * module="1A.site_id_allocator", substream_label∈{"sequence_finalize","site_sequence_overflow"}.
    * events_total/blocks_total/draws_total reconciled with per-event envelopes (blocks_total=draws_total=0).


Downstream touchpoints (from S8 outputs)
----------------------------------------
- S9 (1A validation bundle & HashGate):
    * Re-validates:
        – all structural invariants on outlet_catalogue (keys, FK, lineage)
        – sum & domain laws vs nb_final, s3_candidate_set, s3_integerised_counts / residual_rank
        – S8 RNG invariants for sequence_finalize and site_sequence_overflow
    * Includes outlet_catalogue and S8 events in validation_bundle_1A for this manifest_fingerprint.
    * Writes validation_passed_flag_1A only if all S0–S8 checks pass; **no PASS → no read** for 1B.

- 1B (downstream layer-1 consumer):
    * For a given fingerprint, MUST:
        – locate validation_bundle_1A and its _passed.flag for that fingerprint
        – verify _passed.flag content hash == SHA256(validation_bundle_1A)
        – only then read outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/
    * Treats:
        – S3.candidate_rank as sole cross-country order authority
        – raw_nb_outlet_draw and final_country_outlet_count as read-only facts, never re-allocated.
```