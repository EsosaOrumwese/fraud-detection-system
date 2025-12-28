```
        LAYER 1 · SEGMENT 2B — STATE S7 (AUDITS & CI GATE)  [NO RNG]

Authoritative inputs (read-only at S7 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_2B @ data/layer1/2B/s0_gate_receipt/fingerprint={manifest_fingerprint}/…
      · proves: 2B.S0 ran for this fingerprint and verified 1B PASS
      · binds: { seed, manifest_fingerprint, parameter_hash } for Segment 2B
      · provides: verified_at_utc (canonical created_utc for S7)
    - sealed_inputs_v1 @ data/layer1/2B/sealed_inputs/fingerprint={manifest_fingerprint}/…
      · sealed inventory of cross-layer and policy artefacts S0 authorised
      · all cross-layer/policy inputs S7 reads MUST appear here (subset-of-S0 rule)

[Schema+Dict]
    - schemas.layer1.yaml                 (rng_audit_log, rng_trace_log, RNG envelope, hex64, rfc3339_micros)
    - schemas.2B.yaml                     (shapes for s2_alias_index, s2_alias_blob, s3_day_effects,
                                           s4_group_weights, s5_selection_log_row, s6_edge_log_row,
                                           s7_audit_report_v1, policy anchors)
    - schemas.2A.yaml                     (site_timezones shape; context only, not required by S7)
    - dataset_dictionary.layer1.2B.yaml   (ID→path/partitions/format for all 2B datasets, including s7_audit_report)
    - dataset_dictionary.layer1.2A.yaml   (ID→path/partitions for site_timezones if consulted in evidence)
    - artefact_registry_2B.yaml           (metadata only: owners/licence/retention; no shape/partition authority)

[Plan surfaces S7 MUST audit (read-only; partition = {seed,fingerprint})]
    - s2_alias_index
        · shape: schemas.2B.yaml#/plan/s2_alias_index
        · header fields: {layout_version, endianness, alignment_bytes, quantised_bits,
                          blob_sha256, policy_id, policy_digest, merchants[]…}
    - s2_alias_blob
        · shape: schemas.2B.yaml#/binary/s2_alias_blob
        · binary alias table blob; header digest in index MUST match SHA256(blob)
    - s3_day_effects
        · shape: schemas.2B.yaml#/plan/s3_day_effects
        · PK: [merchant_id, utc_day, tz_group_id]; fields: gamma, log_gamma, sigma_gamma, rng_stream_id, counters
    - s4_group_weights
        · shape: schemas.2B.yaml#/plan/s4_group_weights
        · PK: [merchant_id, utc_day, tz_group_id]; fields: p_group, base_share, gamma, [mass_raw?, denom_raw?]

[Optional additional plan surface (if S7 elects to use; not required)]
    - s1_site_weights
        · shape: schemas.2B.yaml#/plan/s1_site_weights
        · used only for an extra base_share Σ=1 check per merchant; absence is allowed

[Optional router evidence (RNG/log surfaces; only if present AND registered)]
    - s5_selection_log
        · shape: schemas.2B.yaml#/trace/s5_selection_log_row
        · partitions: [seed, parameter_hash, run_id, utc_day]
    - s6_edge_log
        · shape: schemas.2B.yaml#/trace/s6_edge_log_row
        · partitions: [seed, parameter_hash, run_id, utc_day]
    - rng_audit_log, rng_trace_log
        · shape: schemas.layer1.yaml#/rng/core/*
        · partitions: [seed, parameter_hash, run_id]
        · used to reconcile draws/blocks/counters for S5/S6 event families

[Token-less policies (S0-sealed path+digest; S7 MUST read by ID only)]
    - alias_layout_policy_v1               (schemas.2B.yaml#/policy/alias_layout_policy_v1)
    - route_rng_policy_v1                  (schemas.2B.yaml#/policy/route_rng_policy_v1)
    - virtual_edge_policy_v1               (schemas.2B.yaml#/policy/virtual_edge_policy_v1)

[Output owned by S7 (authoritative)]
    - s7_audit_report
        · path: data/layer1/2B/s7_audit_report/seed={seed}/fingerprint={manifest_fingerprint}/s7_audit_report.json
        · partitions: [seed, fingerprint]
        · shape: schemas.2B.yaml#/validation/s7_audit_report_v1 (fields-strict)
        · required keys: component, fingerprint, seed, created_utc,
                         catalogue_resolution, inputs_digest, checks[], metrics, summary

[Numeric & RNG posture]
    - RNG posture:
        · S7 is **RNG-free** — it MUST NOT emit RNG events or consume Philox.
        · RNG artefacts (rng_audit_log, rng_trace_log, S5/S6 events) are read-only evidence.
    - Numeric discipline:
        · IEEE-754 binary64, round-to-nearest-even; no FMA/FTZ/DAZ
        · deterministic, serial reductions; Σ=1 checks use fixed tolerances from upstream specs
    - Catalogue discipline:
        · all inputs resolved by Dataset Dictionary ID + partition; **no literal paths**, **no network I/O**
        · cross-layer/policy assets MUST appear in sealed_inputs_v1 for this fingerprint
    - Write discipline:
        · s7_audit_report is write-once per (seed,fingerprint), published via staging→fsync→atomic move
        · idempotent re-emit allowed only if bytes are bit-identical


----------------------------------------------------------------------
DAG — 2B.S7 (S2/S3/S4 audits + optional S5/S6 evidence → s7_audit_report)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S7.1) Verify S0 gate & fix run identity
                    - Resolve s0_gate_receipt_2B and sealed_inputs_v1 for this manifest_fingerprint via Dictionary.
                    - Check:
                        · both exist, are schema-valid,
                        · manifest_fingerprint in receipt equals path token,
                        · seed in receipt matches S7’s run seed.
                    - Fix run identity:
                        · plan identity:   {seed, manifest_fingerprint}
                        · parameter_hash:  echo from S0; not a partition key for S7.
                    - Derive created_utc_S0 ← s0_gate_receipt_2B.verified_at_utc.
                        · S7 SHALL echo this into s7_audit_report.created_utc.
                    - Record catalogue_resolution {dictionary_version, registry_version} from S0 for later echo.

[S7.1],
[Schema+Dict],
s2_alias_index,
s2_alias_blob,
s3_day_effects,
s4_group_weights,
(optional) s1_site_weights,
alias_layout_policy_v1
                ->  (S7.2) Resolve plan surfaces & policy, enforce S0-evidence rule
                    - Resolve via Dataset Dictionary (no literals):
                        · s2_alias_index@seed={seed}/fingerprint={manifest_fingerprint}
                        · s2_alias_blob@seed={seed}/fingerprint={manifest_fingerprint}
                        · s3_day_effects@seed={seed}/fingerprint={manifest_fingerprint}
                        · s4_group_weights@seed={seed}/fingerprint={manifest_fingerprint}
                        · (optional) s1_site_weights@seed={seed}/fingerprint={manifest_fingerprint}
                        · alias_layout_policy_v1 (token-less; S0-sealed path+digest)
                    - Enforce S0-evidence:
                        · alias_layout_policy_v1 MUST appear in sealed_inputs_v1 (with matching path+sha256_hex).
                        · any cross-layer assets S7 reads (e.g. site_timezones, selection/edge logs, RNG core logs)
                          MUST appear in sealed_inputs_v1.
                    - Validate shapes of S2/S3/S4 (and optional S1) against their schema anchors.
                    - Partition sanity:
                        · S2/S3/S4 (and optional S1) MUST be read at exactly [seed,fingerprint] (no extra keys).
                    - Alias header ↔ policy pre-check:
                        · require s2_alias_index.header.policy_id == "alias_layout_policy_v1",
                        · require s2_alias_index.header.policy_digest matches sealed alias_layout_policy_v1 digest.
                    - Prepare inputs_digest skeleton:
                        · initialise an in-memory map of {asset_id → {version_tag, sha256_hex, path, partition, schema_ref}}
                          for S2/S3/S4 + policies, derived from sealed_inputs_v1.

----------------------------------------------------------------------
A. Alias mechanics (S2) — index & blob coherence + decode round-trip  [NO RNG]

[s2_alias_index, s2_alias_blob, alias_layout_policy_v1]
                ->  (S7.A1) Schema & contract validity (S2 surfaces)
                    - Validate s2_alias_index against schemas.2B.yaml#/plan/s2_alias_index (fields-strict).
                    - Validate s2_alias_blob against schemas.2B.yaml#/binary/s2_alias_blob (binary contract).
                    - Require header fields present and well-typed:
                        · layout_version, endianness, alignment_bytes, quantised_bits,
                          blob_sha256, policy_id, policy_digest, merchants[].
                    - Abort on any mismatch or missing required header field; record FAIL codes into checks[] later.

[s2_alias_blob, s2_alias_index.header.blob_sha256, alias_layout_policy_v1]
                ->  (S7.A2) Header ↔ blob parity & policy echo
                    - Recompute SHA256 over raw s2_alias_blob bytes; require equality with index.header.blob_sha256.
                    - Confirm layout echo:
                        · layout_version, endianness, alignment_bytes, quantised_bits in index.header
                          MUST match the layout declared in alias_layout_policy_v1.
                    - Abort on mismatch; mark appropriate FAIL codes for alias header parity / policy mismatch.

[s2_alias_index, s2_alias_blob]
                ->  (S7.A3) Offsets, lengths & alignment (per-merchant)
                    - For each merchant slice in index.merchants[]:
                        · offsets sorted ascending, length > 0,
                        · offset % alignment_bytes == 0 (from index header),
                        · slice [offset, offset+length) lies within [0, blob_size_bytes],
                        · slices do not overlap.
                    - merchants_total ← number of merchants in index.merchants[].
                    - Abort on any overlap, misalignment, or out-of-bounds slice; accumulate metrics if needed.

[s2_alias_index, s2_alias_blob]
                ->  (S7.A4) Deterministic decode round-trip (sampled merchants)
                    - Determine bounded deterministic sample:
                        · sort merchants by merchant_id (ASCII-lex),
                        · choose K = min(32, merchants_total),
                        · sample set = first K merchant_id values.
                    - For each sampled merchant:
                        · parse its alias slice from s2_alias_blob using offset+length in index.merchants[],
                        · reconstruct implied probabilities p̂_i from (prob[], alias[]) using the decode law,
                        · compute Σ_i p̂_i; require Σ_i p̂_i = 1 within the policy’s Σ=1 tolerance.
                        · if the policy declares a per-site decode tolerance, check |p̂_i − underlying grid mass| ≤ tolerance,
                          otherwise enforce tolerance only on Σ=1.
                    - Track alias_decode_max_abs_delta across all sampled merchants/sites.
                    - Abort if Σ=1 tolerance or decode constraints are violated for any sampled merchant.

----------------------------------------------------------------------
B. Day effects & mixes (S3/S4) — grid equality, γ echo, normalisation  [NO RNG]

[s3_day_effects, s4_group_weights]
                ->  (S7.B1) Day-grid equality (S3 vs S4)
                    - Extract the set G3 = {(merchant_id, utc_day)} from s3_day_effects.
                    - Extract the set G4 = {(merchant_id, utc_day)} from s4_group_weights.
                    - Require G3 == G4 (exact equality; no missing or extra pairs in either direction).
                    - groups_total, days_total derived from S4 (or S3) grid cardinalities.
                    - Abort if grid mismatch is detected.

[s3_day_effects, s4_group_weights]
                ->  (S7.B2) γ echo (S4 must echo S3)
                    - Join s4_group_weights to s3_day_effects on PK (merchant_id, utc_day, tz_group_id).
                    - For every joined row, require:
                        · S4.gamma == S3.gamma (binary64 equality),
                        · S4 does not silently modify γ.
                    - Abort on any mismatch; record FAIL in checks[].

[s4_group_weights]
                ->  (S7.B3) Group normalisation & mass error metrics
                    - For each (merchant_id, utc_day):
                        · compute Σ_group p_group in stable lex order of tz_group_id.
                        · require Σ_group p_group = 1 within tolerance (as per S4 numeric law).
                    - Compute max_abs_mass_error_s4 ← max over all |Σ_group p_group − 1|.
                    - Optionally (if s1_site_weights was supplied and the spec enables it):
                        · per merchant, compute Σ_group base_share; require base_share sums ≈ 1.
                    - Abort on hard violations of Σ=1 law; store max_abs_mass_error_s4 in metrics.

----------------------------------------------------------------------
C. Router evidence (S5/S6) — only if logs + RNG evidence are present  [NO RNG]

[Schema+Dict],
sealed_inputs_v1
                ->  (S7.C0) Discover whether router evidence is in scope
                    - From sealed_inputs_v1, determine if S5/S6 logs and RNG core logs are registered:
                        · s5_selection_log family present?
                        · s6_edge_log family present?
                        · rng_audit_log and rng_trace_log present for this {seed, parameter_hash, run_id}?
                    - If any of these are missing:
                        · S7 skips router evidence checks; sets selections_checked=0, draws_expected=0, draws_observed=0,
                          and records appropriate WARN/INFO codes in checks[].
                    - If all are present:
                        · proceed with C.1–C.3; router evidence becomes part of PASS/FAIL logic.

(s5_selection_log, s6_edge_log, rng_audit_log, rng_trace_log, route_rng_policy_v1, virtual_edge_policy_v1)
                ->  (S7.C1) Trace row shape & lineage (S5/S6 logs)
                    - Validate every s5_selection_log row against schemas.2B.yaml#/trace/s5_selection_log_row:
                        · partitions = [seed, parameter_hash, run_id, utc_day],
                        · embedded manifest_fingerprint == S7 fingerprint,
                        · created_utc == created_utc_S0,
                        · writer order per partition preserves arrival order.
                    - Validate every s6_edge_log row against schemas.2B.yaml#/trace/s6_edge_log_row:
                        · same partition key law and path↔embed equality,
                        · created_utc == created_utc_S0.
                    - Abort on any schema/path/lineage violation.

(s5_selection_log, rng_audit_log, rng_trace_log, route_rng_policy_v1)
                ->  (S7.C2) S5 draw law: group + site draws per selection
                    - From route_rng_policy_v1, recover the RNG family names & budgets for S5:
                        · alias_pick_group, alias_pick_site, each with blocks=1, draws="1".
                    - Reconcile selection count:
                        · selections_checked ← total s5_selection_log rows across all partitions.
                        - Using RNG events + rng_trace_log:
                            · ensure exactly 2 events (1 alias_pick_group + 1 alias_pick_site) per selection,
                            · ensure each event obeys envelope (blocks=1, draws="1"),
                            · ensure counters are strictly increasing with no reuse/wrap.
                    - Compute:
                        · draws_expected = selections_checked * 2,
                        · draws_observed from RNG core logs.
                    - Require draws_expected == draws_observed; otherwise FAIL.

(s6_edge_log, rng_audit_log, rng_trace_log, route_rng_policy_v1, virtual_edge_policy_v1)
                ->  (S7.C3) S6 draw law & edge attribute echo
                    - From route_rng_policy_v1, recover RNG budget for cdn_edge_pick family (blocks=1, draws="1").
                    - Reconcile virtual arrivals:
                        · count S6 rows where is_virtual=true; this is the expected number of cdn_edge_pick events.
                        - Using RNG events + rng_trace_log:
                            · ensure exactly one cdn_edge_pick event per virtual arrival,
                            · envelope satisfied (blocks=1, draws="1"),
                            · counters consistent with trace totals (no reuse/wrap).
                    - Edge attribute echo:
                        · For a bounded set of S6 rows (or all, per implementation):
                            - verify ip_country is a valid ISO-2 and belongs to virtual_edge_policy_v1 for chosen edge_id,
                            - edge_lat/edge_lon match (or are within the policy’s declared tolerance) for the edge_id.
                    - Abort on any mismatch or count discrepancy; update selections_checked/draw metrics accordingly.

----------------------------------------------------------------------
D. Report assembly & publish (authoritative, RNG-free)  [NO RNG]

(S7.A1–A4 results),
(S7.B1–B3 results),
(S7.C0–C3 results),
[s0_gate_receipt_2B, sealed_inputs_v1, catalogue_resolution]
                ->  (S7.D1) Assemble checks[], metrics, summary, inputs_digest
                    - Build inputs_digest:
                        · for each of {s2_alias_index, s2_alias_blob, s3_day_effects, s4_group_weights,
                                       alias_layout_policy_v1, route_rng_policy_v1, virtual_edge_policy_v1}:
                            - look up ID in sealed_inputs_v1,
                            - copy {version_tag, sha256_hex, path, partition, schema_ref} into inputs_digest under that ID.
                    - Build checks[]:
                        · one entry per logical check group:
                            - alias mechanics (A1–A4),
                            - day-grid/γ echo/mixes (B1–B3),
                            - router evidence (C1–C3; PASS/WARN/FAIL depending on presence).
                        · each check entry has:
                            - id (string, e.g. "2B-S7-alias-mechanics"),
                            - status ∈ {PASS, FAIL, WARN},
                            - codes[]: one or more symbolic error/warn codes from the spec,
                            - optional context{} for counts or extra detail.
                    - Build metrics:
                        · merchants_total      (from S2 index),
                        · groups_total         (distinct (merchant_id, tz_group_id) from S4),
                        · days_total           (distinct utc_day from S3/S4),
                        · selections_checked   (from S5 logs, or 0 if not present),
                        · draws_expected       (from S5/S6 evidence, or 0),
                        · draws_observed       (from RNG core logs, or 0),
                        · alias_decode_max_abs_delta (from A4; nullable if no sample),
                        · max_abs_mass_error_s4      (from B3).
                    - Build summary:
                        · overall_status = FAIL if any mandatory check reports FAIL; otherwise PASS.
                        · warn_count     = number of checks with status WARN.
                        · fail_count     = number of checks with status FAIL.

(S7.D1 assembled object),
[Schema+Dict],
[S0 Gate & Identity]
                ->  (S7.D2) Write s7_audit_report & enforce immutability
                    - Target path (via Dictionary):
                        · data/layer1/2B/s7_audit_report/seed={seed}/fingerprint={manifest_fingerprint}/s7_audit_report.json
                    - Embed lineage:
                        · set component="2B.S7",
                        · fingerprint = manifest_fingerprint,
                        · seed = seed,
                        · created_utc = created_utc_S0,
                        · catalogue_resolution = value from S0.
                    - Validate object against schemas.2B.yaml#/validation/s7_audit_report_v1 (fields-strict).
                    - Write-once discipline:
                        · if partition is empty → allowed to publish,
                        · if file exists:
                            - allowed only if bytes are bit-identical (idempotent re-emit),
                            - otherwise Abort with immutable-overwrite / non-idempotent-reemit error.
                    - Publish:
                        · write JSON to a staging location on the same filesystem,
                        · fsync, then single atomic move into the Dictionary path,
                        · no partially written file may become visible.

(published s7_audit_report),
[Schema+Dict],
[S0 Gate & Identity]
                ->  (S7.D3) Post-publish verification & STDOUT run-report
                    - Re-open s7_audit_report from the final path:
                        · validate again against the schema anchor,
                        · confirm path↔embed equality for {seed, fingerprint},
                        · confirm created_utc equals S0.verified_at_utc.
                    - Confirm no other datasets were written by S7 (no plan/egress/log surfaces).
                    - Emit a diagnostic STDOUT run-report (non-authoritative) summarising:
                        · component="2B.S7", seed, fingerprint, created_utc,
                        · key metrics (merchants_total, groups_total, days_total,
                                       selections_checked, draws_expected, draws_observed,
                                       alias_decode_max_abs_delta, max_abs_mass_error_s4),
                        · overall_status, warn_count, fail_count.
                    - Do not persist the STDOUT report as a dataset; authoritative semantics remain
                      with s7_audit_report only.

Downstream touchpoints
----------------------
- **2B.S8 — Validation bundle (`validation_bundle_2B` + `_passed.flag`):**
    - MUST treat s7_audit_report as the **sole authoritative audit artefact**
      for this {seed,fingerprint} when deciding whether to publish a PASS bundle.
    - Discovery of S7 is purely via Dataset Dictionary (ID→path); S8 then pulls checks/metrics/summary from it.
- **Downstream consumers of routing plans (e.g. Layer-2 / 5A/5B):**
    - MUST NOT read Segment 2B plan surfaces (alias tables, group weights) unless
      the 2B validation bundle for this fingerprint is PASS; S7’s audit report is a required
      evidence artefact in that bundle.
- **CI / governance tooling:**
    - MAY read s7_audit_report to drive dashboards or gates, but MUST NOT treat it as mutable;
      write-once discipline and fields-strict schema are enforced by S7.
```