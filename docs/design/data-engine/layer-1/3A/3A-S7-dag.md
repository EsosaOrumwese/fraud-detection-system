```
        LAYER 1 · SEGMENT 3A — STATE S7 (VALIDATION BUNDLE & `_PASSED.FLAG_3A`)  [NO RNG]

Authoritative inputs (read-only at S7 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_3A
      @ data/layer1/3A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3A.json
      · binds: {parameter_hash, manifest_fingerprint, seed} for this manifest
      · records: upstream_gates.{segment_1A,1B,2A}.status (already PASS), sealed_policy_set, catalogue_versions
    - sealed_inputs_3A
      @ data/layer1/3A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3A.parquet
      · whitelist of external artefacts 3A is allowed to read/include
      · any external artefact S7 includes in the bundle MUST appear here with {logical_id, path, sha256_hex}

[Schema+Dict & HashGate spec]
    - schemas.layer1.yaml
        · anchors for:
            - `#/validation/validation_bundle_index_3A`   (index.json schema),
            - `#/validation/passed_flag_3A`              (`_passed.flag_3A` logical shape),
            - generic HashGate rules (canonical digests, SHA-256, hex64, rfc3339_micros, etc.)
    - schemas.3A.yaml
        · anchors for:
            - s0_gate_receipt_3A, sealed_inputs_3A,
            - s1_escalation_queue, s2_country_zone_priors, s3_zone_shares, s4_zone_counts,
            - zone_alloc, zone_alloc_universe_hash,
            - s6_validation_report_3A, s6_issue_table_3A, s6_receipt_3A.
    - dataset_dictionary.layer1.3A.yaml
        · IDs → paths/partitions/schema_refs for:
            - `validation_bundle_3A` (dir, partition [fingerprint]),
            - `_passed.flag_3A` (text, partition [fingerprint]),
            - all S0–S6 artefacts.
    - artefact_registry_3A.yaml
        · manifest_keys/logical_ids for all members; S7 MUST NOT bundle anything not registered.

[S6 verdict & artefacts (segment-status authority)]
    - Segment-state run-report
        · contains per-state S6 entry:
              {state="3A.S6", status, error_code}
        · S7 MUST require S6.status == "PASS", error_code == null for this manifest.
    - s6_validation_report_3A
      @ data/layer1/3A/s6_validation_report/fingerprint={manifest_fingerprint}/report.json
    - s6_issue_table_3A
      @ data/layer1/3A/s6_issues/fingerprint={manifest_fingerprint}/issues.parquet
      · MAY be empty; MUST still be registered as a bundle member (with digest over “empty” representation).
    - s6_receipt_3A
      @ data/layer1/3A/s6_receipt/fingerprint={manifest_fingerprint}/s6_receipt_3A.json
      · carries S6.overall_status and digests (report_digest, issues_digest) that S7 MUST honour.

[3A internal artefacts to be bundled (required members)]
    - S0:
        · s0_gate_receipt_3A,
        · sealed_inputs_3A.
    - S1:
        · s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint}.
    - S2:
        · s2_country_zone_priors@parameter_hash={parameter_hash}.
    - S3:
        · s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint},
        · plus at least a reference to S3 RNG evidence (either raw RNG event dataset(s) or separately sealed RNG digest artefact),
          as defined in the catalogue.
    - S4:
        · s4_zone_counts@seed={seed}/fingerprint={manifest_fingerprint}.
    - S5:
        · zone_alloc@seed={seed}/fingerprint={manifest_fingerprint},
        · zone_alloc_universe_hash@fingerprint={manifest_fingerprint}.
    - S6:
        · s6_validation_report_3A,
        · s6_issue_table_3A (even if empty),
        · s6_receipt_3A.

    Each of these MUST appear as a distinct entry in `index.json` with:
        logical_id, path, schema_ref, sha256_hex, role (gate, sealed_inputs, priors, shares, counts, egress,
        universe_hash, validation_report, validation_receipt, etc.).

[Numeric & RNG posture]
    - RNG:
        · S7 is strictly RNG-free:
            - MUST NOT call Philox or any RNG;
            - MUST NOT append RNG events or modify RNG logs.
    - Time:
        · MUST NOT depend on wall-clock for decisions; any timestamps (if present) are non-authoritative metadata.
    - Idempotence:
        · Given the same inputs (S0–S6 artefacts, RNG logs, sealed_inputs_3A, catalogue), S7 MUST produce byte-identical:
            - `validation_bundle_3A` index.json,
            - `_passed.flag_3A`.
        · Existing non-identical index/flag for the same fingerprint → immutability violation; S7 MUST fail.


----------------------------------------------------------------------
DAG — 3A.S7 (S6 PASS → validation_bundle_3A + `_passed.flag_3A`)  [NO RNG]

[Schema+Dict],
[S0 Gate & Identity]
                ->  (S7.1) Fix fingerprint identity & load S0/whitelist
                    - Inputs (from orchestrator or Layer-1 harness):
                        · parameter_hash (hex64),
                        · manifest_fingerprint (hex64),
                        · seed (uint64; not a partition key here),
                        · run_id (opaque string / u128-like; not used in outputs).
                    - Validate formats; treat (parameter_hash, manifest_fingerprint, seed, run_id) as immutable.
                    - Resolve via dictionary:
                        · s0_gate_receipt_3A@fingerprint={manifest_fingerprint},
                        · sealed_inputs_3A@fingerprint={manifest_fingerprint}.
                    - Validate:
                        · s0_gate_receipt_3A against schemas.3A.yaml#/validation/s0_gate_receipt_3A,
                        · sealed_inputs_3A against schemas.3A.yaml#/validation/sealed_inputs_3A.
                    - S7 MUST treat:
                        · S0 as the only authority on “what was gated and sealed”,
                        · sealed_inputs_3A as the only whitelist for external artefacts.

[Schema+Dict],
Segment-state run-report,
s6_receipt_3A,
s6_validation_report_3A
                ->  (S7.2) Enforce S6 PASS precondition
                    - Using the segment-state run-report, locate S6’s run entry for this manifest:
                        · require S6.status == "PASS" and S6.error_code == null.
                    - Resolve:
                        · s6_receipt_3A@fingerprint={manifest_fingerprint},
                        · s6_validation_report_3A@fingerprint={manifest_fingerprint},
                          via dictionary.
                    - Validate both against their schema anchors in schemas.3A.yaml.
                    - Require:
                        · s6_receipt_3A.overall_status == "PASS".
                    - If either:
                        · S6 self-reports non-PASS, or
                        · s6_receipt_3A.overall_status ≠ "PASS",
                      then S7 MUST NOT produce a bundle+flag; it MUST terminate with a suitable error.

[Schema+Dict],
sealed_inputs_3A
                ->  (S7.3) Resolve required S0–S5 artefacts & ensure existence
                    - Using dictionary+registry and sealed_inputs_3A, resolve:
                        · s0_gate_receipt_3A,
                        · sealed_inputs_3A,
                        · s1_escalation_queue@seed={seed}/fingerprint={manifest_fingerprint},
                        · s2_country_zone_priors@parameter_hash={parameter_hash},
                        · s3_zone_shares@seed={seed}/fingerprint={manifest_fingerprint},
                        · s4_zone_counts@seed={seed}/fingerprint={manifest_fingerprint},
                        · zone_alloc@seed={seed}/fingerprint={manifest_fingerprint},
                        · zone_alloc_universe_hash@fingerprint={manifest_fingerprint}.
                    - For each resolved artefact:
                        · confirm schema_validity via its schema_ref,
                        · confirm its {logical_id, path, schema_ref} appear in sealed_inputs_3A where it is “external”;
                          internal 3A datasets must at least match dictionary+registry.
                    - If any required artefact is missing or schema-invalid:
                        · S7 MUST NOT assemble a bundle; it MUST fail with a precondition error.

[Schema+Dict],
sealed_inputs_3A,
rng_event_zone_dirichlet (or RNG digest artefact for S3)
                ->  (S7.4) Resolve RNG evidence member(s) for S3
                    - Depending on catalogue and sealed_inputs_3A:
                        · either:
                              - treat a concrete RNG dataset (e.g. rng_event_zone_dirichlet for 3A.S3) as the RNG evidence member, OR
                        · a separately registered RNG digest artefact specific to S3.
                    - S7 MUST:
                        · ensure at least one RNG evidence entry for S3 is included in the bundle member set,
                        · ensure it appears in sealed_inputs_3A (for external entry) or dictionary/registry (for internal digest),
                        · NOT invent any unregistered RNG artefact.

S0–S6 artefacts resolved,
RNG evidence,
[Schema+Dict]
                ->  (S7.5) Build bundle member table (logical_id, path, schema_ref, role)
                    - Construct an in-memory list of bundle members, at least:
                        · S0:
                              (logical_id="mlr.3A.s0_gate_receipt_3A", path=s0 path,      role="gate"),
                              (logical_id="mlr.3A.sealed_inputs_3A",    path=sealed path,  role="sealed_inputs").
                        · S1:
                              (logical_id="mlr.3A.s1_escalation_queue", path=...,          role="domain").
                        · S2:
                              (logical_id="mlr.3A.s2_country_zone_priors", path=...,       role="priors").
                        · S3:
                              (logical_id="mlr.3A.s3_zone_shares",      path=...,          role="shares"),
                              (logical_id="mlr.3A.s3_rng_evidence",     path=...,          role="rng_evidence").
                        · S4:
                              (logical_id="mlr.3A.s4_zone_counts",      path=...,          role="counts").
                        · S5:
                              (logical_id="mlr.3A.zone_alloc",           path=...,         role="egress"),
                              (logical_id="mlr.3A.zone_alloc_universe",   path=...,         role="universe_hash").
                        · S6:
                              (logical_id="mlr.3A.s6_validation_report",  path=...,        role="validation_report"),
                              (logical_id="mlr.3A.s6_issue_table",        path=...,        role="validation_issues"),
                              (logical_id="mlr.3A.s6_receipt",            path=...,        role="validation_receipt").
                    - For each member:
                        · attach schema_ref from dictionary,
                        · attach role string from a small, fixed vocabulary.
                    - S7 MUST NOT:
                        · include artefacts not known to dictionary + registry,
                        · include artefacts that are missing or outside sealed_inputs_3A for external sources.

bundle member table,
[Schema+Dict]
                ->  (S7.6) Compute per-member `sha256_hex` digests
                    - For each member (logical_id, path, schema_ref, role):
                        · determine canonical representation according to HashGate rules:
                              - for Parquet datasets: concatenate bytes of all data files under path (ASCII-lex path order),
                              - for JSON artefacts: bytes of the on-disk serialisation (no reformatting),
                              - for other formats: catalogue-defined canonical representation.
                        · compute digest:
                              sha256_hex = SHA256(canonical_bytes) ⇒ 64-char lowercase hex.
                    - If S6 or S5 already published authoritative digests (e.g. report_digest, issues_digest, zone_alloc_parquet_digest),
                      S7 MUST confirm recomputed digests match those fields; mismatches ⇒ FAILED check in S6 (but S7 bundling
                      still uses recomputed digests).
                    - Attach sha256_hex to each member row in the bundle member table.

bundle member table (with sha256_hex),
s6_receipt_3A,
[Schema+Dict]
                ->  (S7.7) Build logical `index.json` object
                    - Assemble an index object matching `validation_bundle_index_3A` schema:
                        · manifest_fingerprint = current F,
                        · parameter_hash       = current parameter_hash,
                        · s6_receipt_digest    = SHA256(bytes of s6_receipt_3A) (MUST equal s6_receipt_3A.report_digest or equivalent),
                        · members = [...]:
                              - for each member row:
                                    {logical_id, path, schema_ref, sha256_hex, role, [size_bytes?, notes?]}.
                        · metadata (optional):
                              - s0_version…s6_version (if available),
                              - created_at_utc (if provided by orchestrator),
                              - contract version IDs.
                    - Canonical ordering:
                        · sort members by a canonical key (e.g. ASCII-lexical order of `logical_id` or `path`, as defined by spec),
                          and retain that order in the `members` array.
                        · serialise JSON with stable key ordering in each object when computing any digest later.
                    - Validate index object against `validation_bundle_index_3A` schema.

index logical object,
existing validation_bundle_3A?,
[Schema+Dict]
                ->  (S7.8) Write `index.json` under `validation_bundle_3A` (fingerprint-scoped)
                    - Target directory (via dictionary entry for `validation_bundle_3A`):
                        · data/layer1/3A/validation/fingerprint={manifest_fingerprint}/
                    - Target file:
                        · index.json inside that directory.
                    - Serialise the index logical object into JSON with a stable serialisation.
                    - If `index.json` does not exist:
                        · write via staging → fsync → atomic move.
                    - If `index.json` exists:
                        · read existing JSON, parse to logical object,
                        · recompute what S7 would produce now from current inputs,
                        · if logical objects differ ⇒ immutability violation (E3A_S7_006); S7 MUST NOT overwrite.
                        · if equal ⇒ idempotent re-run; keep existing bytes or rewrite identical bytes.

index.json (on disk),
[Schema+Dict]
                ->  (S7.9) Compute composite bundle digest `bundle_sha256_hex`
                    - Read `index.json` just written/confirmed.
                    - Extract member list in its canonical order and the fields:
                          sha256_hex_for_member_1, sha256_hex_for_member_2, …, sha256_hex_for_member_n.
                    - Concatenate these digests as ASCII hex strings in that exact order:
                          concat = sha256_hex_1 || sha256_hex_2 || … || sha256_hex_n
                      (no delimiters, no whitespace).
                    - Compute:
                          bundle_sha256_hex = SHA256(concat) ⇒ 64-char lowercase hex.
                    - This value is the **3A HashGate digest** for this manifest; it MUST be used in `_passed.flag_3A`
                      and by consumers when verifying the bundle.

bundle_sha256_hex,
[Schema+Dict],
existing `_passed.flag_3A`?
                ->  (S7.10) Build and write `_passed.flag_3A`
                    - Logical form:
                        · { sha256_hex = bundle_sha256_hex }.
                    - On-disk representation:
                        · single-line UTF-8 text, exactly:
                              `sha256_hex = <bundle_sha256_hex>`
                          where `<bundle_sha256_hex>` is 64 lowercase hex chars.
                    - Target path via dictionary:
                        · data/layer1/3A/validation/fingerprint={manifest_fingerprint}/_passed.flag_3A
                    - If `_passed.flag_3A` does not exist:
                        · write via staging → fsync → atomic move.
                    - If `_passed.flag_3A` exists:
                        · read its content, parse `sha256_hex = <existing_hex>`,
                        · require `<existing_hex> == bundle_sha256_hex`,
                        · if not equal ⇒ immutability violation (E3A_S7_006); S7 MUST NOT overwrite.

index.json,
`_passed.flag_3A`
                ->  (S7.11) Post-publish verification & STDOUT summary (non-authoritative)
                    - Re-open index.json and `_passed.flag_3A`:
                        · validate index.json against `validation_bundle_index_3A`,
                        · parse `_passed.flag_3A` against `passed_flag_3A` schema,
                        · recompute bundle_sha256_hex from index.json members and confirm it matches the flag’s sha256_hex.
                    - Emit a non-authoritative run summary (e.g. to STDOUT or log):
                        · component="3A.S7",
                        · manifest_fingerprint, parameter_hash,
                        · bundle_member_count, bundle_sha256_hex,
                        · overall_status = "PASS" if index+flag match and S6_receipt_3A.overall_status="PASS".
                    - S7 MUST NOT write any additional datasets besides:
                        · `validation_bundle_3A` (index.json) and `_passed.flag_3A`.

Downstream touchpoints
----------------------
- **Bundle/flag consumers (2B, orchestrators, cross-segment validators):**
    - MUST treat 3A as PASS for manifest F only if:
        1) `s6_receipt_3A@fingerprint=F` has `overall_status="PASS"`,
        2) `validation_bundle_3A@fingerprint=F` exists and `index.json` is schema-valid,
        3) `_passed.flag_3A@fingerprint=F` exists,
        4) recomputing `bundle_sha256_hex` from index.json members yields the same hex as in `_passed.flag_3A`.
    - MUST enforce: **“No 3A PASS (bundle+flag+S6 receipt) ⇒ No read of 3A surfaces for that manifest.”**

- **3A plan/egress consumers (e.g. 2B, analytics):**
    - MUST NOT read:
        · s1_escalation_queue, s2_country_zone_priors, s3_zone_shares, s4_zone_counts,
        · zone_alloc, zone_alloc_universe_hash,
      for manifest F unless the above PASS criteria hold.

- **Change control:**
    - Any change to S0–S6 bundles, priors, policies, or data-plane that affects any member artefact’s digest
      MUST result in:
        · a new `bundle_sha256_hex`,
        · and, under normal process, a new manifest_fingerprint (and new S0–S7 run).
```