```
        LAYER 1 · SEGMENT 1A — STATE S9 (REPLAY VALIDATION & PUBLISH GATE)  [NO RNG · READ-ONLY]

Authoritative inputs (read-only at S9 entry)
-------------------------------------------
[Schema+Dict] Schema authorities & dataset catalogue:
    - schemas.layer1.yaml                (RNG, logs, core events)
    - schemas.1A.yaml                    (1A tables, egress, validation bundle)
    - schemas.ingress.layer1.yaml        (ingress/reference FKs)
    - dataset_dictionary.layer1.1A.yaml  (IDs, paths, partitions, writer sorts)
    - artefact_registry_1A.yaml          (artefact IDs, paths, dependencies, semver)

[N] Numeric & environment contracts:
    - numeric_policy.json
    - math_profile_manifest.json
      · inherit S0.8 regime: IEEE-754 binary64, RNE, FMA-OFF, no FTZ/DAZ; deterministic libm.
      · changing either flips manifest_fingerprint; S9 must attest regime before validating.

[G] Run & lineage keys:
    - seed : u64
    - parameter_hash : hex64
    - manifest_fingerprint : hex64
    - run_id : opaque (logs-only)
    - S0/S8 manifest info for recomputing parameter_hash and manifest_fingerprint.

[Egress] Egress subject to gate:
    - outlet_catalogue
      · path: data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest_fingerprint}/
      · schema: schemas.1A.yaml#/egress/outlet_catalogue
      · partitions: [seed, fingerprint]
      · writer sort: [merchant_id, legal_country_iso, site_order]

[Authorities · parameter-scoped]
    - s3_candidate_set        @ parameter_hash={parameter_hash}   (sole cross-country order)
    - (opt) s3_integerised_counts @ parameter_hash={parameter_hash} (counts+residual_rank)
    - (opt) s3_site_sequence  @ parameter_hash={parameter_hash}   (sequence cross-check only)
    - iso3166_canonical_2024  (FK target for country_iso / legal_country_iso)

[RNG core logs]
    - rng_audit_log @ [seed, parameter_hash, run_id]
    - rng_trace_log @ [seed, parameter_hash, run_id]

[RNG event families (S1–S8)]
    - rng_event.hurdle_bernoulli
    - rng_event.gamma_component, rng_event.poisson_component, rng_event.nb_final
    - rng_event.ztp_rejection, rng_event.ztp_retry_exhausted, rng_event.ztp_final
    - rng_event.gumbel_key
    - rng_event.residual_rank
    - rng_event.sequence_finalize, rng_event.site_sequence_overflow
    - (plus any other 1A RNG families registered for S0–S8; module/substream literals fixed in S9 Appendix A)

[Convenience & receipts (gated reads)]
    - (opt) s6_membership              @ [seed, parameter_hash]
    - s6_validation_receipt + _passed.flag @ …/s6/seed={seed}/parameter_hash={parameter_hash}/
      (required only when using s6_membership; **no PASS → no read** of s6_membership.)

[Upstream behaviour surfaces]
    - All S0–S8 surfaces required for replay:
        · S1: hurdle_design_matrix, rng_event.hurdle_bernoulli
        · S2: nb design + rng_event.gamma_component / poisson_component / nb_final
        · S3: s3_candidate_set (+ optional counts/sequence)
        · S4: rng_event.poisson_component(context="ztp"), ztp_rejection, ztp_retry_exhausted, ztp_final
        · S6: rng_event.gumbel_key (+ optional s6_membership)
        · S7: rng_event.residual_rank (+ optional dirichlet_gamma_vector)
        · S8: outlet_catalogue, rng_event.sequence_finalize, rng_event.site_sequence_overflow

[Prev-layer gates]
    - 1A S5 PASS receipt (parameter-scoped; independent of S9 gate — **S9 does not read S5 weight surfaces**).
    - 1A S6 PASS receipt (when using s6_membership).
    - Any other state-scoped receipts referenced in artefact_registry_1A.yaml.


----------------------------------------------------------------- DAG (S9.1–S9.8 · validate S0–S8, then publish gate)

[Schema+Dict],
[N],[G]         ->  (S9.1) Environment attestation & input inventory
                      - Attest numeric regime from numeric_policy.json + math_profile_manifest.json (binary64, RNE, FMA-OFF, no FTZ/DAZ).
                      - Load schema anchors & Dictionary entries for:
                          * outlet_catalogue, S3 tables, RNG logs/events, S6 receipts, validation_bundle_1A.
                      - Load artefact_registry_1A to:
                          * confirm validation_bundle_1A + validation_passed_flag_1A IDs, paths, dependencies (outlet_catalogue, rng_audit_log).
                      - Enumerate RNG modules/substreams S9 is responsible for (per Appendix A).
                      - Result: fixed inventory of what S9 **must** validate structurally, linearly, and via replay.

[G],[Schema+Dict],
[Egress],[Authorities],
[RNG core],[RNG events],
[Convenience]  ->  (S9.2) Read-gates, path discovery & subject loading
                      - Discover all (seed, parameter_hash, run_id, manifest_fingerprint) tuples from:
                          * outlet_catalogue partitions
                          * rng_event.* streams
                          * rng_trace_log, rng_audit_log
                      - Enforce **read gates** before touching convenience surfaces:
                          * If s6_membership is to be used:
                              – require s6_validation_receipt + _passed.flag for same {seed,parameter_hash};
                              – verify _passed.flag hash == SHA256(S6_VALIDATION.json).
                          * S9 NEVER reads S5 weight surfaces; selection/allocation replay uses only S6 events
                            (or gated s6_membership) and S7 evidence (“no weights in S9” law).
                      - Open all required subjects via Dictionary paths (no hard-coded paths), including:
                          * outlet_catalogue, S3 tables, rng_audit_log, rng_trace_log, rng_event.* families.
                      - Enforce **path↔embed equality** on lineage for every opened dataset/log:
                          * parameters / seeds / fingerprints embedded == path tokens.
                      - Any gate breach or early lineage mismatch ⇒ structural failure; S9 will later withhold `_passed.flag`.

[Egress],[Authorities],
[RNG core],[RNG events],
[Schema+Dict],
[N],[G]         ->  (S9.3) Structural validation (schemas, partitions, PK/UK, FK, writer sort)
                      - For each subject in scope:
                          * Validate JSON-Schema anchor (rows, domains, patterns, envelope fields present).
                          * Enforce Dictionary path + partition law:
                              – outlet_catalogue under …/seed={seed}/fingerprint={manifest_fingerprint}/, partitions [seed,fingerprint].
                              – S3 tables under …/parameter_hash={parameter_hash}/.
                              – rng_* under …/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…
                          * Enforce PK/UK:
                              – outlet_catalogue: unique (merchant_id, legal_country_iso, site_order) per (seed,fingerprint).
                              – S3: unique (merchant_id, country_iso, candidate_rank) / (merchant_id,country_iso) as declared.
                              – no duplicated RNG events with same identity (module, substream, counters + payload id).
                          * Enforce FKs:
                              – country_iso / legal_country_iso FKs to iso3166_canonical_2024.
                              – any other schema-declared FK (e.g., merchant seed lists).
                          * Enforce writer sort where declared:
                              – outlet_catalogue sorted by [merchant_id, legal_country_iso, site_order] within partition.
                      - Missing final rng_trace_log rows (coverage) or any schema/PK/FK/path breach ⇒ structural FAIL (bundle will be written, but no flag).

[G],[Schema+Dict],
[N],[Egress],
[Authorities],
[RNG core],
[RNG events]    ->  (S9.4) Lineage recomputation, identity & determinism
                      - Recompute lineage keys:
                          * parameter_hash from governed parameter set 𝓟 (artefact basenames) via S0 tuple-hash; must equal partition token and embedded parameter_hash everywhere.
                          * manifest_fingerprint from artefacts 𝓐 + git_32 + parameter_hash_bytes; must equal:
                              – outlet_catalogue fingerprint partition,
                              – validation bundle fingerprint,
                              – embedded manifest_fingerprint in egress/events where present.
                          * run_id uniqueness per (seed,parameter_hash); ensure run_id only partitions logs/events.
                      - Check path↔embed identity again as determinism prerequisite.
                      - Identity & immutability:
                          * egress identity: (outlet_catalogue, seed, manifest_fingerprint) is write-once; if pre-existing, bytes must match (hashes recorded).
                          * parameter-scoped tables: (dataset_id, parameter_hash) immutable.
                          * logs: (stream, seed, parameter_hash, run_id) immutable; duplicates for same event identity ⇒ structural error.
                      - Determinism & concurrency:
                          * egress obeys writer sort; equivalence defined by row set (not file order).
                          * S8 block atomicity: exactly one sequence_finalize per (merchant,legal_country_iso), with start="000001", end=zfill6(n); overflow: site_sequence_overflow + no egress rows for that merchant.
                          * no misuse of lineage keys (e.g., seed on S3 tables, run_id on egress).
                      - Any mismatch ⇒ lineage/determinism FAIL (no `_passed.flag`).

[RNG events],
[RNG core],
[N],[G]         ->  (S9.5) RNG envelope & accounting (all families)
                      - Per RNG event row:
                          * enforce layer envelope presence (ts_utc, module, substream_label, counters before/after, blocks, draws, lineage).
                          * enforce per-event budget:
                              – blocks == u128(after) − u128(before)
                              – non-consuming families: blocks=0, draws="0"; before==after.
                      - Attempt/order invariants (families with loops):
                          * S1 hurdle: extremes consume zero; stochastic branch consumes exactly one; exactly one hurdle event per merchant.
                          * S2 NB: per attempt exactly one gamma_component then one poisson_component; on first K≥2, exactly one nb_final (non-consuming).
                          * S4 ZTP: attempts 1-based and monotone; each Poisson attempt followed by either ztp_rejection (non-consuming) or ztp_final (non-consuming); cap + policy obeyed (abort vs downgrade_domestic).
                          * S6 Gumbel: one uniform per key; log_all_candidates vs selected-only behaviour consistent with policy.
                          * S7 residual_rank: all non-consuming; Dirichlet lane (if present) obeys its own invariants.
                          * S8 sequence_finalize / site_sequence_overflow: non-consuming; coverage matches egress domain.
                      - Trace coverage & reconciliation:
                          * for each (module,substream_label,run_id):
                              – exactly one rng_trace_log row appended after each event append;
                              – final trace row totals (events_total, blocks_total, draws_total) equal set-sums of events.
                          * rng_audit_log present and consistent for each (seed,parameter_hash,run_id) in scope.
                      - Any counter/budget/coverage/trace mismatch ⇒ RNG_ACCOUNTING FAIL.

[Egress],[Authorities],
[RNG events],
[Upstream surfaces],
[N],[G]         ->  (S9.6) Cross-state replay S1–S8 (facts only; no side-effects)
                      - S1 Hurdle replay:
                          * recompute π from hurdle design + coefficients; confirm one hurdle_bernoulli per merchant, extremes vs stochastic branch behaviour, gating of downstream RNG families.
                      - S2 NB replay:
                          * replay Gamma/Poisson attempts and nb_final; confirm component order, N≥2, nb_final uniqueness, and Σ counts vs events.
                      - S3 Candidate replay:
                          * confirm candidate_rank is total & contiguous with home=0; no invented order; uniqueness of (merchant,country,candidate_rank).
                      - S4 ZTP replay:
                          * reconstruct attempt sequence from poisson_component(context="ztp"), ztp_rejection, ztp_final, ztp_retry_exhausted; validate regime choice, cap policy, uniqueness of ztp_final.
                      - S6 Membership replay:
                          * choose path:
                              – M1: from s6_membership (requires S6 PASS); equality to top-K_target eligible by Gumbel key.
                              – M2: from gumbel_key events + S3/S4; select K_realized=min(K_target, |Eligible|).
                          * detect zero-weight-selected or membership outside S3 domain.
                      - S7 Integerisation replay:
                          * reconstruct counts over D={home}∪selected_foreigns using largest remainder and dp_resid=8 residuals; confirm Σ count_i=N, parity of residual_rank, and no new order surface.
                      - S8 Egress replay:
                          * verify per (merchant,legal_country_iso) block: site_order=1..n_i, site_id six_digit_seq; one sequence_finalize; overflow policy obeyed (overflow event + no rows).
                          * join egress distinct (merchant,legal_country_iso) back to S3 and confirm membership + counts parity.
                      - Record any failures with canonical E_S* codes into s9_summary.json.

[Schema+Dict],
[Egress],[RNG core],
[RNG events],
[G],[N]         ->  (S9.7) Build validation_bundle_1A & compute flag hash
                      - Assemble validation_bundle_1A under:
                          * data/layer1/1A/validation/fingerprint={manifest_fingerprint}/
                      - Required bundle files:
                          * MANIFEST.json                         (run metadata: seed, parameter_hash, manifest_fingerprint, run_id, code id…)
                          * parameter_hash_resolved.json          (attested parameter_hash)
                          * manifest_fingerprint_resolved.json    (attested manifest_fingerprint)
                          * rng_accounting.json                   (per-family coverage/budget results)
                          * s9_summary.json                       (structural/lineage/replay outcomes, failures_by_code, counts_source, membership_source, run decision)
                          * egress_checksums.json                 (per-file and composite SHA-256 for outlet_catalogue in [seed,fingerprint])
                          * index.json                            (table of all artefacts: artifact_id, kind, path, mime?, notes?)
                      - Ensure index.json lists every non-flag file exactly once with a **relative** path.
                      - Compute gate hash:
                          * sort index.json paths ASCII-lexicographically;
                          * concatenate raw bytes of each referenced file (excluding _passed.flag);
                          * compute SHA-256 → hex64.
                      - Stage bundle in temp dir under validation/; write all files there (no partials visible yet).

[Bundle],[G]    ->  (S9.8) PASS / FAIL decision & atomic publish
                      - Decide outcome for (seed, manifest_fingerprint):
                          * PASS iff **all** Binding checks in §§5–8 succeed for **every** merchant.
                          * FAIL otherwise.
                      - PASS path:
                          * write `_passed.flag` into staged folder:
                              – single line `sha256_hex = <hex64>` with the bundle hash computed above.
                          * atomically rename staged folder to:
                              – data/layer1/1A/validation/fingerprint={manifest_fingerprint}/
                      - FAIL path:
                          * publish bundle **without** `_passed.flag` via atomic rename.
                          * gate remains FAILED for this fingerprint.
                      - Idempotence:
                          * re-running S9 with identical inputs must yield **byte-identical** bundle + flag.
                      - S9 emits **no RNG events** and performs **no RNG draws**; it is read-only over producers’ data.


State boundary (authoritative outputs of S9)
-------------------------------------------
- validation_bundle_1A        @ fingerprint={manifest_fingerprint}
    * Folder: data/layer1/1A/validation/fingerprint={manifest_fingerprint}/
    * Schema: schemas.1A.yaml#/validation/validation_bundle.
    * Contains at minimum:
        - MANIFEST.json, parameter_hash_resolved.json, manifest_fingerprint_resolved.json,
          rng_accounting.json, s9_summary.json, egress_checksums.json, index.json.
    * Serves as machine-readable proof of S0–S8 validation and RNG accounting.

- validation_passed_flag_1A      (file `_passed.flag` in same folder)
    * Present only on PASS.
    * Content: `sha256_hex = <hex64>` where <hex64> is SHA-256 over all bundle files listed in index.json
      (excluding `_passed.flag`) in ASCII-lexicographic order of `path`.
    * **Consumer gate:** 1B and any other consumers **MUST** verify flag hash vs bundle before reading outlet_catalogue
      for this fingerprint (**no PASS → no read**).


Downstream touchpoints (from S9 outputs)
----------------------------------------
- 1B / downstream engines:
    * For a given manifest_fingerprint:
        - locate data/layer1/1A/validation/fingerprint={fingerprint}/
        - verify `_passed.flag` content hash equals SHA256(validation_bundle_1A) as per S9;
        - only then read outlet_catalogue/seed={seed}/fingerprint={fingerprint}/.
    * Must treat absence or mismatch of `_passed.flag` as **hard NO-READ** on egress.

- CI / monitoring:
    * May consume s9_summary.json, rng_accounting.json, egress_checksums.json for dashboards & alarms.
    * SLOs:
        - gate integrity (flag ↔ bundle hash),
        - trace coverage & totals,
        - determinism/idempotence (bundle and egress hashes stable),
        - order & partition correctness (writer sort, path↔embed equality).
```
