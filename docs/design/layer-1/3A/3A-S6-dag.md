```
        LAYER 1 · SEGMENT 3A — STATE S6 (STRUCTURAL VALIDATION & SEGMENT AUDIT)  [NO RNG]

Authoritative inputs (read-only at S6 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_3A
      @ data/layer1/3A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3A.json
      · binds: {parameter_hash, manifest_fingerprint, seed} for this 3A run
      · records: upstream_gates.{segment_1A,1B,2A}.status
      · records: sealed_policy_set (mixture, priors, floors, day-effect, if any)
      · records: catalogue_versions (schema/dict/registry versions S0 saw)

    - sealed_inputs_3A
      @ data/layer1/3A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3A.parquet
      · fingerprint-scoped inventory of every external artefact S1–S5 may read
      · S6 MUST treat this as the whitelist for external inputs (policies, priors, refs, etc.)
      · S6 MUST NOT treat environment variables or ad-hoc local files as inputs

[Schema+Dict · shape-only authority]
    - schemas.layer1.yaml, schemas.ingress.layer1.yaml
    - schemas.2A.yaml, schemas.3A.yaml
    - dataset_dictionary.layer1.{1A,3A}.yaml
    - artefact_registry_{1A,3A}.yaml
      · S6 uses these to resolve IDs→paths/partitions/schema_refs for all datasets/artefacts it reads

[3A internal artefacts (contract instances)]
    - S0:
        · s0_gate_receipt_3A, sealed_inputs_3A (trust anchors, already listed)
    - S1:
        · s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}
          (domain D, D_esc, site_count(m,c), zone_count_country(c), escalation decisions)
        · S1 run-report row (segment-state report; S6 reads self-declared status)
    - S2:
        · s2_country_zone_priors@parameter_hash={parameter_hash}
          (α_effective(c,z), α_sum_country(c), Z(c), prior/floor lineage)
        · S2 run-report row
    - S3:
        · s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint}
          (Θ(m,c,z), share_sum_country(m,c), α_sum_country(c), prior/floor lineage)
        · S3 run-report row
    - S4:
        · s4_zone_counts@seed={seed}/fingerprint={manifest_fingerprint}
          (zone_site_count(m,c,z), zone_site_count_sum(m,c), share_sum_country(m,c))
        · S4 run-report row
    - S5:
        · zone_alloc@seed={seed}/fingerprint={manifest_fingerprint}
          (final zonal egress; includes `routing_universe_hash`)
        · zone_alloc_universe_hash@fingerprint={manifest_fingerprint}
          (component digests + combined `routing_universe_hash`)
        · S5 run-report row

[External artefacts (priors, policies, references) — must be sealed]
    - Mixture policy:          zone_mixture_policy_3A
    - Prior pack:              country_zone_alphas_3A
    - Floor/bump policy:       zone_floor_policy_3A
    - Day-effect policy:       day_effect_policy_v1 (from 2B)
    - Structural refs:         iso3166_canonical_2024, country_tz_universe or tz_world_2025a, etc.
      · For each:
          - MUST have an entry in sealed_inputs_3A with {logical_id, path, schema_ref, sha256_hex},
          - S6 MUST recompute SHA256 and assert equality with sealed_inputs_3A.sha256_hex

[RNG logs for S3 (Dirichlet sampling)]
    - rng_event_zone_dirichlet
      · Layer-1 RNG events dataset, with rows:
            module="3A.S3", substream_label="zone_dirichlet",
            partitioned by (seed={seed}, parameter_hash={parameter_hash}, run_id={run_id})
    - rng_trace_log
      · aggregate counts per (seed, parameter_hash, run_id, module, substream_label)
    - rng_audit_log
      · high-level RNG family summary; used to cross-check S3 draws vs budget
    - S6 uses these logs to validate S3’s RNG accounting; MUST NOT emit new RNG events

[Outputs owned by S6]
    - s6_validation_report_3A
      @ data/layer1/3A/s6_validation_report/fingerprint={manifest_fingerprint}/report.json
      · partition_keys: ["fingerprint"]
      · one JSON object per manifest_fingerprint
      · contains:
            manifest_fingerprint, parameter_hash,
            overall_status ∈ {"PASS","FAIL"},
            checks[] (fixed registry of check_id, status, default_severity, affected_count, description),
            metrics{} (aggregate counts, max deviations, rng stats, etc.)

    - s6_issue_table_3A  (optional but strongly recommended)
      @ data/layer1/3A/s6_issues/fingerprint={manifest_fingerprint}/issues.parquet
      · partition_keys: ["fingerprint"]
      · 0 or more rows per manifest
      · each row: one issue instance with {check_id, severity, code, message, scope, entity keys}

    - s6_receipt_3A
      @ data/layer1/3A/s6_receipt/fingerprint={manifest_fingerprint}/s6_receipt.json
      · partition_keys: ["fingerprint"]
      · one JSON object per manifest
      · contains:
            manifest_fingerprint, parameter_hash,
            overall_status,
            check_status_map{check_id→status},
            report_digest (SHA256 of s6_validation_report_3A bytes),
            issues_digest (SHA256 of s6_issue_table_3A bytes or null if absent),
            contract_versions, inputs_digest (optional)

[Numeric & RNG posture]
    - RNG:
        · S6 is strictly RNG-free:
            - MUST NOT call Philox,
            - MUST NOT append RNG events or modify RNG logs.
    - Time:
        · MUST NOT use `now()` or wall-clock to decide anything or to populate authoritative fields.
        · Any timestamps (if present) come from orchestrator or upstream artefacts.
    - Idempotence:
        · Given the same inputs (S0–S5 artefacts, RNG logs, catalogue), S6 MUST produce byte-identical report/issue table/receipt.
        · If re-run and outputs differ, S6 MUST treat that as an immutability violation.


----------------------------------------------------------------------
DAG — 3A.S6 (S0–S5 + RNG logs → validation report, issue table, receipt)  [NO RNG]

### Phase 1 — Initialisation & input resolution

[Schema+Dict],
[S0 Gate & Identity]
                ->  (S6.1) Fix run identity
                    - S6 is invoked with:
                        · parameter_hash,
                        · manifest_fingerprint,
                        · seed,
                        · run_id.
                    - Validate:
                        · parameter_hash, manifest_fingerprint ∈ hex64,
                        · seed ∈ uint64,
                        · run_id conforms to agreed format (opaque string/UUID/u128).
                    - Treat the tuple (parameter_hash, manifest_fingerprint, seed, run_id) as immutable.
                    - Note: these values are used for locating inputs and populating report/receipt fields;
                      S6 MUST NOT branch on them in any data-dependent way beyond identity.

[Schema+Dict],
[S0 Gate & Identity]
                ->  (S6.2) Resolve S0 artefacts (gate & sealed inputs)
                    - Resolve via dictionary:
                        · s0_gate_receipt_3A@fingerprint={manifest_fingerprint},
                        · sealed_inputs_3A@fingerprint={manifest_fingerprint}.
                    - Validate both against schemas.3A.yaml anchors.
                    - From s0_gate_receipt_3A:
                        · read upstream_gates.{segment_1A,1B,2A},
                        · read sealed_policy_set,
                        · read catalogue_versions.
                    - S6 MUST NOT re-interpret or weaken S0’s gate; it only verifies S0’s consistency.

[Schema+Dict],
sealed_inputs_3A
                ->  (S6.3) Resolve 3A internal artefacts S1–S5
                    - Using dictionary + registry, resolve:
                        · s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint},
                        · s2_country_zone_priors@parameter_hash={parameter_hash},
                        · s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint},
                        · s4_zone_counts@seed={seed}/fingerprint={manifest_fingerprint},
                        · zone_alloc@seed={seed}/fingerprint={manifest_fingerprint},
                        · zone_alloc_universe_hash@fingerprint={manifest_fingerprint}.
                    - Validate each dataset/artefact against its schema_ref in schemas.3A.yaml.
                    - Resolve 3A segment-state run-report rows for S1–S5:
                        · S6 reads their self-reported statuses but MUST NOT require them to be "PASS"
                          as a precondition; inconsistencies are captured later as validation findings.

[Schema+Dict],
sealed_inputs_3A
                ->  (S6.4) Resolve RNG logs for S3
                    - Using Layer-1 RNG dictionary/registry, resolve:
                        · rng_event_zone_dirichlet@seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}
                          for module="3A.S3", substream_label="zone_dirichlet",
                        · rng_trace_log@seed={seed}/parameter_hash={parameter_hash}/run_id={run_id},
                        · rng_audit_log@seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}.
                    - Validate all RNG artefacts against schemas.layer1.yaml RNG anchors.
                    - If required RNG logs for S3 are missing or malformed:
                        · treat as precondition or catalogue error for the relevant checks
                          (affects RNG-related checks; S6 still produces a report with FAIL for those checks).

sealed_inputs_3A,
s0_gate_receipt_3A
                ->  (S6.5) Resolve external policies/priors/refs for digest checks
                    - Using sealed_inputs_3A + s0_gate_receipt_3A.sealed_policy_set:
                        · locate entries for:
                              - zone_mixture_policy_3A,
                              - country_zone_alphas_3A,
                              - zone_floor_policy_3A,
                              - day_effect_policy_v1,
                              - iso3166_canonical_2024,
                              - country_tz_universe or tz_world_2025a (and other structural refs).
                    - For each artefact:
                        · resolve via dictionary to concrete path + schema_ref,
                        · recompute SHA256 over raw bytes,
                        · assert equality with sealed_inputs_3A.sha256_hex.
                    - Validate shape using the declared schema_ref.
                    - These artefacts are used only to:
                        · confirm S1/S2/S5 used the sealed versions,
                        · recompute S5 digests (zone_alpha_digest, theta_digest, zone_floor_digest, day_effect_digest).

### Phase 2 — Check registry initialisation

[Schema+Dict]
                ->  (S6.6) Initialise fixed check registry
                    - Construct an in-memory registry of checks with entries:
                        · check_id           (e.g. "CHK_S0_GATE_SEALED_INPUTS"),
                        · default_severity   ("ERROR" or "WARN"),
                        · description        (human-readable),
                        · status             (initially "PASS"),
                        · affected_count     (initially 0).
                    - Registry MUST at least include:
                        · S0-level:
                              CHK_S0_GATE_SEALED_INPUTS,
                              CHK_S0_CATALOGUE_VERSION_COHERENCE.
                        · S1-level:
                              CHK_S1_DOMAIN_COVERAGE,
                              CHK_S1_SITE_COUNTS,
                              CHK_S1_ESCALATION_DECISIONS.
                        · S2-level:
                              CHK_S2_PRIOR_SURFACE_DOMAIN,
                              CHK_S2_ALPHA_POSITIVITY,
                              CHK_S2_ZONE_UNIVERSE_ALIGNMENT.
                        · S3-level:
                              CHK_S3_SHARE_DOMAIN,
                              CHK_S3_SHARE_SUMS,
                              CHK_S3_RNG_ACCOUNTING.
                        · S4-level:
                              CHK_S4_COUNT_CONSERVATION,
                              CHK_S4_DOMAIN_ALIGNMENT.
                        · S5-level:
                              CHK_S5_ZONE_ALLOC_COUNTS,
                              CHK_S5_UNIVERSE_HASH_DIGESTS,
                              CHK_S5_UNIVERSE_HASH_COMBINED.
                        · Status coherence:
                              CHK_STATE_STATUS_CONSISTENCY (S1–S5 self-report vs structural checks).
                    - S6 MUST NOT mutate the registry structure (add/remove IDs) at runtime based on data.

### Phase 3 — Execute per-state checks (S0–S5, RNG)

S0, S1, S2, S3, S4, S5 artefacts + RNG logs
                ->  (S6.7) Run structural checks & accumulate issues
                    - For each check family, S6:
                        · runs deterministic logic using preloaded artefacts,
                        · if it finds issues:
                              - sets the check’s status to "FAIL" or "WARN" (depending on default_severity and breach),
                              - increments affected_count,
                              - appends one or more issue records to an in-memory issue buffer.
                    - Checks include (high-level behaviour):

                    *S0-level checks*
                    - CHK_S0_GATE_SEALED_INPUTS:
                        · verify upstream gates in s0_gate_receipt_3A match actual 1A/1B/2A bundles+flags,
                          and that sealed_inputs_3A reflects the sealed policy/prior/refs set.
                    - CHK_S0_CATALOGUE_VERSION_COHERENCE:
                        · confirm catalogue_versions in S0 are consistent with current schema/dict/registry versions.

                    *S1-level checks*
                    - CHK_S1_DOMAIN_COVERAGE:
                        · compare s1_escalation_queue’s (m,c) domain with 1A’s outlet_catalogue domain;
                          detect missing or extra pairs.
                    - CHK_S1_SITE_COUNTS:
                        · recompute site_count(m,c) from outlet_catalogue and compare to S1.site_count(m,c).
                    - CHK_S1_ESCALATION_DECISIONS:
                        · re-evaluate mixture policy conditions against S1 inputs (without RNG) and
                          flag any mismatches in is_escalated/decision_reason.

                    *S2-level checks*
                    - CHK_S2_PRIOR_SURFACE_DOMAIN:
                        · confirm s2_country_zone_priors domain matches country_tz_universe / tz_world_2025a
                          for the relevant countries.
                    - CHK_S2_ALPHA_POSITIVITY:
                        · require alpha_effective(c,z) > 0 and alpha_sum_country(c) > 0.
                    - CHK_S2_ZONE_UNIVERSE_ALIGNMENT:
                        · ensure no stray tzids and no missing zones relative to structural refs.

                    *S3-level checks*
                    - CHK_S3_SHARE_DOMAIN:
                        · require S3 domain = D_esc × Z(c) (from S1/S2); no missing or extra (m,c,z).
                    - CHK_S3_SHARE_SUMS:
                        · per escalated (m,c), check share_sum_country(m,c) ≈ 1 within tolerance;
                          flag near-miss as WARN, gross deviation as FAIL.
                    - CHK_S3_RNG_ACCOUNTING:
                        · verify exactly one rng_event_zone_dirichlet per escalated (m,c),
                          envelope (blocks, draws, counters) per event,
                          and trace totals vs Σ events.

                    *S4-level checks*
                    - CHK_S4_DOMAIN_ALIGNMENT:
                        · confirm S4 domain = D_esc × Z(c).
                    - CHK_S4_COUNT_CONSERVATION:
                        · per (m,c), Σ_z zone_site_count(m,c,z) equals zone_site_count_sum(m,c) and S1.site_count(m,c).

                    *S5-level checks*
                    - CHK_S5_ZONE_ALLOC_COUNTS:
                        · confirm zone_alloc is a faithful projection of s4_zone_counts, preserving counts and domain.
                    - CHK_S5_UNIVERSE_HASH_DIGESTS:
                        · recompute S5’s component digests
                              (zone_alpha_digest, theta_digest, zone_floor_digest, day_effect_digest,
                               zone_alloc_parquet_digest)
                          and compare with zone_alloc_universe_hash.
                    - CHK_S5_UNIVERSE_HASH_COMBINED:
                        · recompute routing_universe_hash from component digests and check:
                              - equality with zone_alloc_universe_hash.routing_universe_hash,
                              - equality with routing_universe_hash on every zone_alloc row.

                    *Status coherence check*
                    - CHK_STATE_STATUS_CONSISTENCY:
                        · compare structural check outcomes (PASS/FAIL per state family) with
                          S1–S5 self-reported statuses in the segment-state run-report.
                        · e.g. state reports `status="PASS"` but one of its checks is FAIL.

                    - All checks MUST be independent of evaluation order: final statuses are the same no matter
                      the order S6 executes them in.

### Phase 4 — Materialise report & issue table

check registry (with statuses & affected_count),
metrics (aggregated during checks)
                ->  (S6.8) Build `s6_validation_report_3A` object
                    - Determine overall_status:
                        · "FAIL" if any check has status "FAIL",
                        · "PASS" otherwise (WARNs allowed).
                    - Compose report JSON object with at least:
                        · manifest_fingerprint,
                        · parameter_hash,
                        · overall_status,
                        · checks[] = array over all registry entries:
                              {check_id, status, default_severity, affected_count, description},
                        · metrics{} summarising:
                              - counts of merchants/countries/zones,
                              - count of escalated pairs,
                              - RNG stats (events, draws) for S3,
                              - max deviations (e.g. max |Σ share -1|, worst count mismatch),
                              - number of issues per severity.
                    - Validate report object against schemas.3A.yaml#/validation/s6_validation_report_3A.

issue buffer (0+ issue records)
                ->  (S6.9) Materialise `s6_issue_table_3A` (optional)
                    - If issue buffer is empty:
                        · S6 MAY choose not to write s6_issue_table_3A for this manifest,
                          or write an empty dataset; both are considered “no issues recorded”.
                    - If issue buffer non-empty:
                        · Convert each issue record into a row with at least:
                              - manifest_fingerprint,
                              - check_id,
                              - severity,
                              - code,
                              - message,
                              - scope (e.g. "STATE_S3", "RNG"),
                              - entity keys (merchant_id, country_iso, tzid, etc. as applicable).
                        · Target path via dictionary:
                              data/layer1/3A/s6_issues/fingerprint={manifest_fingerprint}/issues.parquet
                        - Partition: [fingerprint].
                        - Enforce immutability:
                              - if dataset absent → write via staging → fsync → atomic move,
                              - if present:
                                    · normalise existing rows and compare to new rows,
                                    · if identical → idempotent re-run OK,
                                    · else → immutability violation; MUST NOT overwrite.

### Phase 5 — Build receipt & write outputs (idempotent)

s6_validation_report_3A (JSON),
s6_issue_table_3A (if present)
                ->  (S6.10) Compute report_digest & issues_digest
                    - report_digest:
                        · serialise s6_validation_report_3A to bytes as written on disk,
                        · compute SHA256(raw_bytes) → report_digest (hex).
                    - issues_digest:
                        · if s6_issue_table_3A exists:
                              - serialise issues dataset into a canonical representation (e.g. Parquet bytes),
                              - compute SHA256(raw_bytes) → issues_digest (hex).
                        · else:
                              - issues_digest = null (or a sentinel per schema).
                    - These digests are used in s6_receipt_3A and S7’s bundle integrity checks.

s6_validation_report_3A,
report_digest,
issues_digest,
check registry,
catalogue_versions,
(parameter_hash, manifest_fingerprint)
                ->  (S6.11) Build `s6_receipt_3A` object
                    - Construct a JSON object with at least:
                        · manifest_fingerprint,
                        · parameter_hash,
                        · overall_status (copied from report),
                        · check_status_map: {check_id → status} for every check in registry,
                        · report_digest,
                        · issues_digest,
                        · catalogue_versions (from S0),
                        · optional: contract version IDs for S0–S6.
                    - Validate object against schemas.3A.yaml#/validation/s6_receipt_3A.

s6_validation_report_3A,
s6_issue_table_3A (optional),
s6_receipt_3A
                ->  (S6.12) Write S6 outputs with immutability & idempotence
                    - For each artefact:
                        · s6_validation_report_3A → data/layer1/3A/s6_validation_report/fingerprint={manifest_fingerprint}/report.json
                        · s6_issue_table_3A      → data/layer1/3A/s6_issues/fingerprint={manifest_fingerprint}/issues.parquet
                        · s6_receipt_3A          → data/layer1/3A/s6_receipt/fingerprint={manifest_fingerprint}/s6_receipt.json
                    - Partition: [fingerprint] for all.
                    - Immutability:
                        · if no existing artefact:
                              - write via staging → fsync → atomic move.
                        · if artefact exists:
                              - read existing bytes, normalise representation,
                              - if byte-identical to new output → idempotent re-run; OK.
                              - else → immutability violation; S6 MUST fail and MUST NOT overwrite.
                    - S6 MUST NOT write or mutate any other dataset.

Downstream touchpoints
----------------------
- **3A.S7 — Validation bundle & `_passed.flag_3A`:**
    - MUST treat `s6_receipt_3A` as the authoritative summary of S6 results
      and `s6_validation_report_3A`/`s6_issue_table_3A` as its detailed evidence.
    - S7 uses report_digest/issues_digest to detect tampering and to decide if 3A is “green” for a manifest.

- **Cross-segment validators / operators:**
    - MAY consume `s6_validation_report_3A` and `s6_issue_table_3A` to inspect checks and issues.
    - MAY rely on `s6_receipt_3A.overall_status` and `check_status_map` as a compact “health” signal for 3A.

- **Business-plane & routing consumers:**
    - MUST NOT use S6 outputs directly for routing or modelling decisions.
    - MUST instead honour the HashGate produced in S7, which wraps S6 receipt and report into a fingerprint-scoped bundle:
          **No PASS → No read** of 3A plan/egress surfaces (e.g. `zone_alloc`).
```