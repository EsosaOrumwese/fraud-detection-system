```
        LAYER 1 · SEGMENT 2B — STATE S8 (VALIDATION BUNDLE & `_PASSED.FLAG`)  [NO RNG]

Authoritative inputs (read-only at S8 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_2B
      @ data/layer1/2B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_2B.json
      · proves: 2B.S0 ran for this fingerprint and verified 1B PASS
      · binds: { manifest_fingerprint, seed, parameter_hash } for this 2B pack
      · provides: verified_at_utc (canonical created_utc for 2B)
    - sealed_inputs_v1
      @ data/layer1/2B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_v1.json
      · sealed inventory of cross-layer/policy assets (IDs → {path, partition, sha256_hex, schema_ref})
      · S8 MUST use this for policy parity and provenance; no rewrites

[Schema+Dict]
    - schemas.1A.yaml
        · `#/validation/validation_bundle.index_schema` — canonical bundle index schema
    - schemas.1B.yaml
        · `#/validation/passed_flag` — canonical `_passed.flag` schema
    - schemas.2B.yaml
        · `#/validation/s7_audit_report_v1` — S7 report shape
        · anchors for S2/S3/S4 plan/binary surfaces (provenance only; S8 does NOT re-audit)
    - dataset_dictionary.layer1.2B.yaml
        · IDs → paths/partitions for:
            · s7_audit_report
            · s2_alias_index, s2_alias_blob
            · s3_day_effects, s4_group_weights
            · validation_bundle_2B, validation_passed_flag_2B
    - artefact_registry_2B.yaml
        · metadata for validation_bundle_2B and validation_passed_flag_2B (write-once/atomic; final_in_layer)

[Seed-scoped audit evidence]
    - s7_audit_report
      @ data/layer1/2B/s7_audit_report/seed={seed}/fingerprint={manifest_fingerprint}/s7_audit_report.json
      · one per seed in the discovered seed set
      · MUST be schema-valid and have summary.overall_status = "PASS"
      · WARNs allowed unless governance forbids

[Plan & policy surfaces for provenance (no re-audit)]
    - s2_alias_index, s2_alias_blob
      · per-seed alias plan & blob (read at [seed,fingerprint] only; provenance echo, no decoding)
    - s3_day_effects, s4_group_weights
      · per-seed plan surfaces for γ and group weights (read at [seed,fingerprint]; provenance only)
    - Policies (token-less; S0-sealed by path+sha256):
      · alias_layout_policy_v1
      · route_rng_policy_v1
      · virtual_edge_policy_v1

[Outputs owned by S8]
    - validation_bundle_2B
        · index.json @ data/layer1/2B/validation/fingerprint={manifest_fingerprint}/index.json
        · partition: [fingerprint]
        · schema: schemas.1A.yaml#/validation/validation_bundle.index_schema
        · role: authoritative PASS bundle index for Segment 2B
    - validation_passed_flag_2B
        · _passed.flag @ data/layer1/2B/validation/fingerprint={manifest_fingerprint}/_passed.flag
        · partition: [fingerprint]
        · schema: schemas.1B.yaml#/validation/passed_flag
        · content: exactly one line `sha256_hex = <64 lowercase hex>`
        · role: PASS gate; `sha256_hex` MUST equal bundle digest

[Numeric & RNG posture]
    - RNG:
        · S8 is **RNG-free** — it SHALL NOT emit any RNG events or consume Philox.
        · Hashing only (SHA-256).
    - Numeric:
        · SHA-256 over raw bytes; IEEE-754 issues are irrelevant (no numeric probabilities).
    - Catalogue & identity:
        · Dictionary-only resolution (IDs + partitions), no literal paths, no network I/O.
        · S8 never mutates bytes of included evidence; it only copies/links and indexes them.
        · Publish is fingerprint-scoped only: `…/validation/fingerprint={manifest_fingerprint}/`.


----------------------------------------------------------------------
DAG — 2B.S8 (S7 PASS set → validation_bundle_2B + `_passed.flag_2B`)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S8.1) Resolve S0 evidence & fix fingerprint identity
                    - Resolve s0_gate_receipt_2B and sealed_inputs_v1 for this manifest_fingerprint via Dictionary.
                    - Validate both against their schema anchors.
                    - Path↔embed:
                        · embedded manifest_fingerprint in s0_gate_receipt_2B MUST equal the fingerprint path token.
                    - Fix identity for S8:
                        · fingerprint = manifest_fingerprint (bundle partition key),
                        · seed/parameter_hash from S0 are carried for provenance only; they are NOT partitions here.
                    - Record:
                        · created_utc_S0 ← s0_gate_receipt_2B.verified_at_utc,
                        · catalogue_resolution ← from S0.
                    - Confirm posture:
                        · S8 is RNG-free and will not re-hash upstream 1B; S0 is the sole 1B gate.

[Schema+Dict]
                ->  (S8.2) Discover seed set (intersection at this fingerprint)
                    - For each of the three plan surfaces:
                        · s2_alias_index, s3_day_effects, s4_group_weights
                      use the Dataset Dictionary + catalogue to enumerate **seeds** available at
                      `fingerprint={manifest_fingerprint}` (no row scans, no literals).
                    - Let:
                        · S2_seeds = {seed | s2_alias_index exists at [seed,fingerprint]},
                        · S3_seeds = {seed | s3_day_effects exists at [seed,fingerprint]},
                        · S4_seeds = {seed | s4_group_weights exists at [seed,fingerprint]}.
                    - Required seed set:
                        · Seeds_required = S2_seeds ∩ S3_seeds ∩ S4_seeds.
                    - If Seeds_required is empty → Abort (no bundle can be formed).
                    - Order:
                        · sort Seeds_required ASCII-lex by decimal seed string to form
                          a stable ordered list: [seed₁, seed₂, …, seedₙ].
                        · This order MUST be used consistently in later layout steps (reports order).

[S8.1],
[Schema+Dict],
s7_audit_report,
sealed_inputs_v1,
(alias_layout_policy_v1, route_rng_policy_v1, virtual_edge_policy_v1)
                ->  (S8.3) Verify S7 coverage & policy parity (no re-audit)
                    - For each seed ∈ Seeds_required:
                        · resolve s7_audit_report@seed={seed}/fingerprint={manifest_fingerprint},
                        · validate against `#/validation/s7_audit_report_v1`,
                        · require:
                            - summary.overall_status == "PASS",
                            - component == "2B.S7",
                            - embedded {seed, fingerprint} equal path tokens.
                        · WARN-level checks in S7 are permitted unless governance policy forbids.
                    - Policy parity (token-less policies only):
                        · for each of {alias_layout_policy_v1, route_rng_policy_v1, virtual_edge_policy_v1}:
                            - locate its `(path, sha256_hex)` entry in sealed_inputs_v1 (partition = `{}`),
                            - resolve the actual file by that exact path,
                            - recompute SHA-256 over raw bytes and require equality with sealed_inputs_v1.sha256_hex.
                    - Within-segment plan surfaces (S2/S3/S4):
                        · S8 selects them strictly by Dataset Dictionary ID at `[seed,fingerprint]`,
                          but does **not** require sealed_inputs_v1 parity for them
                          (they are validated by S7; S8 uses them only for provenance echo).
                    - If any S7 report is missing or FAIL, or policy parity fails → Abort (no bundle, no flag).

[S8.1–S8.3],
[Schema+Dict],
s7_audit_report,
s0_gate_receipt_2B,
sealed_inputs_v1,
(s2_alias_index, s2_alias_blob, s3_day_effects, s4_group_weights as provenance)
                ->  (S8.4) Stage bundle workspace (RNG-free; bytes unchanged)
                    - Create a temporary workspace directory on the local filesystem; root not equal to final publish path.
                    - Deterministic layout under bundle root (informative but recommended):
                        · For each seed ∈ Seeds_required (in sorted order):
                            - copy s7_audit_report.json → `reports/seed={seed}/s7_audit_report.json`
                        · S0 evidence:
                            - copy s0_gate_receipt_2B.json → `evidence/s0/s0_gate_receipt_2B.json`
                            - copy sealed_inputs_v1.json   → `evidence/s0/sealed_inputs_v1.json`
                        · Optional provenance snapshots (if implementation chooses to include them):
                            - policies → `evidence/refs/policies/…`
                            - S2/S3/S4 manifests/digests → `evidence/refs/{s2|s3|s4}/…`
                    - Copying rule:
                        · copy or hard-link bytes **unchanged** — no JSON reformatting, no re-encoding.
                        · all paths must stay **under the bundle root**; no absolute paths, no `..` segments.

(Bundle workspace),
[Schema+Dict]
                ->  (S8.5) Build `index.json` (bundle index; fields-strict)
                    - Enumerate all files under the bundle root, **excluding `_passed.flag`** (which may not exist yet).
                    - For each file:
                        · compute `sha256_hex = SHA256(raw bytes)` over the file as-is.
                        · determine relative path `path` from bundle root:
                              - UTF-8, no leading `/`, no `.` or `..` segments.
                    - Materialise index object:
                        · an array of `{ path, sha256_hex }` records.
                        · sort entries **ASCII-lex by `path`**.
                        · require:
                              - no duplicate `path` values,
                              - every file is indexed exactly once,
                              - `_passed.flag` is **not** included.
                    - Write `index.json` at bundle root with a stable JSON serializer:
                        · UTF-8,
                        · consistently ordered keys and whitespace so that re-runs produce identical bytes.
                    - Validate `index.json` against the canonical bundle index schema
                      (schemas.1A.yaml#/validation/validation_bundle.index_schema).

(Bundle workspace with index.json),
[Schema+Dict]
                ->  (S8.6) Compute bundle digest & emit `_passed.flag_2B`
                    - Bundle digest:
                        · re-read index.json and iterate index entries in `path` ASCII-lex order.
                        · for each row:
                              - open the file at `path` under bundle root,
                              - append its raw bytes to a hash stream.
                        · compute `bundle_digest = SHA256(concatenated bytes)`.
                    - Write `_passed.flag` under the bundle root containing **exactly**:

                          sha256_hex = <bundle_digest>

                        · single ASCII line, newline handling per passed_flag schema; no extra whitespace.
                    - Validate `_passed.flag` against schemas.1B.yaml#/validation/passed_flag.
                    - Note: `_passed.flag` is explicitly **not listed** in `index.json` and is excluded from `bundle_digest`.

(Bundle workspace + index.json + _passed.flag),
[Schema+Dict]
                ->  (S8.7) Pre-publish validation of workspace
                    - Re-validate `index.json` against the index schema.
                    - For every index entry:
                        · recompute SHA-256 over the referenced file’s raw bytes,
                        · require equality with the stored `sha256_hex`.
                    - Verify `_passed.flag`:
                        · parse the line, require `sha256_hex = <64 hex>` form,
                        · require `<64 hex>` equals `bundle_digest` just computed.
                    - Partition & identity:
                        · prospective publish path MUST be
                              `data/layer1/2B/validation/fingerprint={manifest_fingerprint}/`.
                        · for S0/S7 files inside the workspace, embedded `{seed, fingerprint}` fields
                          MUST equal their path tokens (path↔embed equality).
                    - If any check fails → Abort; workspace MUST NOT be published.

(Bundle workspace validated),
[Schema+Dict],
[S0 Gate & Identity]
                ->  (S8.8) Publish validation_bundle_2B & validation_passed_flag_2B (write-once)
                    - Final bundle root (via Dictionary, ID `validation_bundle_2B` / `validation_passed_flag_2B`):
                        · directory: data/layer1/2B/validation/fingerprint={manifest_fingerprint}/
                        · index.json path matches Dictionary entry for validation_bundle_2B.
                        · _passed.flag path matches Dictionary entry for validation_passed_flag_2B.
                    - Write-once & idempotent:
                        · If the target directory does **not** exist:
                              - atomic rename/move the entire workspace directory to the final path.
                        · If it exists:
                              - re-open index.json and _passed.flag and all files,
                              - compare the bytes of the existing directory to the workspace:
                                    · if byte-identical → discard workspace (idempotent re-emit),
                                    · otherwise → Abort with IMMUTABLE_OVERWRITE.
                    - No partial publish:
                        · index.json and _passed.flag must appear together;
                        · no intermediate state with one present and the other missing.

(published validation_bundle_2B + validation_passed_flag_2B),
[Schema+Dict]
                ->  (S8.9) Post-publish verification & STDOUT report (non-authoritative)
                    - Resolve validation_bundle_2B and validation_passed_flag_2B via Dataset Dictionary.
                    - Re-validate:
                        · index.json conforms to bundle index schema,
                        · `_passed.flag` conforms to passed_flag schema,
                        · `_passed.flag.sha256_hex` equals recomputed bundle digest from indexed files,
                        · partition path is exactly `fingerprint={manifest_fingerprint}`.
                    - Confirm identity:
                        · any embedded fingerprint in included evidence (S0/S7) still matches path tokens.
                    - Emit a non-authoritative STDOUT summary:
                        · component="2B.S8",
                        · fingerprint,
                        · seeds_in_bundle = |Seeds_required|,
                        · confirmation that all S7 reports PASS and bundle published.
                    - S8 MUST NOT write any additional datasets or logs.

Downstream touchpoints
----------------------
- **2B plan consumers (Layer-2, later layers, tooling):**
    - MUST treat `validation_passed_flag_2B` as the **sole PASS gate** for Segment 2B at this fingerprint.
    - Rule: for any dataset produced by 2B (e.g. s1_site_weights, s2_alias_index/blob,
      s3_day_effects, s4_group_weights), consumers SHALL enforce:
          **No PASS → No read**  
      where PASS means:
          1. `validation_bundle_2B` exists at `fingerprint={manifest_fingerprint}`, and
          2. `_passed.flag` content matches the hash of the indexed bundle bytes.
- **Governance / CI:**
    - MAY inspect `validation_bundle_2B/index.json` (and the included S0/S7 evidence) to drive dashboards and gates.
    - SHALL treat bundle contents as immutable; any update requires a **new** manifest_fingerprint.
- **Upstream segments:**
    - 2B.S8 does **not** change any plan surface; it only packages evidence.
    - Authority chain is:
          S0 (gate + sealed inputs) → S1–S7 (plans + audit) → S8 (validation bundle + `_passed.flag_2B`).
```