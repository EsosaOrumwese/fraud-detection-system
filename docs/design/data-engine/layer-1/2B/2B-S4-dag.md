```
        LAYER 1 · SEGMENT 2B — STATE S4 (ZONE-GROUP RENORMALISATION)  [NO RNG]

Authoritative inputs (read-only at S4 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_2B @ data/layer1/2B/s0_gate_receipt/fingerprint={manifest_fingerprint}/…
      · proves: a valid 2B.S0 gate exists for this manifest_fingerprint
      · binds: { seed, manifest_fingerprint } for this S4 run
      · provides: canonical created_utc = verified_at_utc
    - sealed_inputs_v1 @ data/layer1/2B/sealed_inputs/fingerprint={manifest_fingerprint}/…
      · inventory of all cross-layer/policy artefacts S0 sealed for this fingerprint
      · S4 MUST ensure cross-layer inputs it reads (e.g. site_timezones) appear here

[Schema+Dict]
    - schemas.2B.yaml                     (shape authority for s1_site_weights, s3_day_effects, s4_group_weights)
    - schemas.2A.yaml                     (shape authority for site_timezones)
    - schemas.layer1.yaml                 (core types, date/rfc3339, numeric/identity law)
    - dataset_dictionary.layer1.2B.yaml   (ID→path/partitions/format for 2B datasets)
    - dataset_dictionary.layer1.2A.yaml   (ID→path/partitions/format for 2A site_timezones)
    - artefact_registry_2B.yaml           (existence/licence/retention; non-authoritative for paths)

[Required inputs S4 MAY read (and nothing else)]
    - s1_site_weights
        · producer: 2B.S1
        · partition: seed={seed} / fingerprint={manifest_fingerprint}
        · PK: [merchant_id, legal_country_iso, site_order]
        · columns (min): merchant_id, legal_country_iso, site_order, p_weight
        · role: site-level base mass per merchant; used to build base_share per tz-group
    - site_timezones
        · producer: 2A.S2
        · partition: seed={seed} / fingerprint={manifest_fingerprint}
        · PK: [merchant_id, legal_country_iso, site_order]
        · columns (min): merchant_id, legal_country_iso, site_order, tzid
        · role: provides tz_group_id = tzid for grouping sites; MUST appear in sealed_inputs_v1
    - s3_day_effects
        · producer: 2B.S3
        · partition: seed={seed} / fingerprint={manifest_fingerprint}
        · PK: [merchant_id, utc_day, tz_group_id]
        · columns (min): merchant_id, utc_day (date), tz_group_id (tzid), gamma (>0), sigma_gamma
        · role: per-{merchant, utc_day, tz_group_id} γ factors; S4 will combine these with base_share

[Output owned by S4]
    - s4_group_weights
        · description: Per-merchant × per-UTC-day × per-tz-group day-specific routing mix (RNG-free)
        · partition keys: [seed, fingerprint]
        · PK & writer sort: [merchant_id, utc_day, tz_group_id]
        · columns_strict: merchant_id, utc_day, tz_group_id,
                          p_group, base_share, gamma, created_utc, mass_raw?, denom_raw?

[Numeric & RNG posture]
    - RNG posture:
        · S4 is **RNG-free** — performs no random draws, uses no Philox streams.
    - Numeric discipline:
        · IEEE-754 binary64, round-to-nearest-even; no FMA/FTZ/DAZ
        · serial reductions in deterministic order; no data-dependent reordering of sums
        · programme-constant tolerance ε for “sum ≈ 1” checks and tiny-negative guards
    - Catalogue discipline:
        · all reads via Dataset Dictionary IDs; literal paths and network I/O are forbidden
        · cross-layer assets MUST appear in sealed_inputs_v1 for this fingerprint


----------------------------------------------------------------------
DAG — 2B.S4 (s1_site_weights × site_timezones × s3_day_effects → s4_group_weights)  [NO RNG]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S4.1) Verify prior gate & fix run identity
                    - Resolve s0_gate_receipt_2B for target manifest_fingerprint via Dictionary.
                    - Check preconditions:
                        · receipt exists and is schema-valid,
                        · manifest_fingerprint in receipt matches the partition token,
                        · seed from receipt matches the run’s seed.
                    - Resolve sealed_inputs_v1 for this fingerprint; build in-memory set of sealed IDs.
                    - Fix run identity:
                        · {seed, manifest_fingerprint} is fixed for all S4 steps.
                    - Derive created_utc_S0 ← s0_gate_receipt_2B.verified_at_utc;
                      S4 SHALL echo this into created_utc for every s4_group_weights row.

[S0 Gate & Identity],
[Schema+Dict],
s1_site_weights,
site_timezones,
s3_day_effects
                ->  (S4.2) Resolve inputs, enforce S0-evidence rule & derive day grid
                    - Resolve via Dictionary (no literals):
                        · s1_site_weights@seed={seed}/fingerprint={manifest_fingerprint}
                        · site_timezones@seed={seed}/fingerprint={manifest_fingerprint}
                        · s3_day_effects@seed={seed}/fingerprint={manifest_fingerprint}
                    - Enforce S0-evidence rule:
                        · site_timezones MUST appear in sealed_inputs_v1 for this fingerprint
                          (cross-layer asset).
                        · s1_site_weights and s3_day_effects are within-segment and are not
                          required to appear in sealed_inputs_v1 but MUST use the exact
                          {seed,fingerprint} partition.
                    - Validate shapes:
                        · s1 and site_timezones share PK [merchant_id, legal_country_iso, site_order],
                          both unique on that key.
                        · s3_day_effects has PK [merchant_id, utc_day, tz_group_id].
                    - Materialise UTC day grid D:
                        · extract distinct utc_day values from s3_day_effects,
                        · sort ascending by date (YYYY-MM-DD),
                        · D will be the only day set S4 uses; no new days may be introduced.

s1_site_weights,
site_timezones
                ->  (S4.3) Join S1 with site_timezones & compute base shares
                    - Join basis:
                        · left-join s1_site_weights on keys (merchant_id, legal_country_iso, site_order)
                          to site_timezones on the same keys.
                    - Join integrity:
                        · each s1 row MUST find exactly one site_timezones row (one tzid),
                        · abort if any key is missing or maps to multiple tzid.
                    - tz-group universe:
                        · define tz_group_id = tzid from site_timezones.
                        · For each merchant_id:
                            - collect distinct tz_group_id from joined rows,
                            - sort tz_group_id lexicographically to get the merchant’s group set.
                        · S4 SHALL NOT introduce tz_group_id values that are not present in this join.
                    - Base shares:
                        · For each {merchant_id, tz_group_id}:
                            - base_share(merchant, group) = Σ_site p_weight over all joined rows
                              belonging to that group, summing in stable PK order.
                    - Base-mass check:
                        · For each merchant_id:
                            - require |Σ_group base_share − 1| ≤ ε,
                            - otherwise abort (base mass inconsistent with S1).

s3_day_effects,
(base_share per merchant×tz_group from S4.3),
day grid D
                ->  (S4.4) Combine base shares with S3 γ per day
                    - For each merchant_id and tz_group_id in the join set from S4.3,
                      and for each utc_day ∈ D:
                        · perform a lookup into s3_day_effects on PK
                              (merchant_id, utc_day, tz_group_id).
                        · abort if:
                              - no row exists, or
                              - more than one row exists for that key.
                        · let gamma(merchant, utc_day, group) ← s3_day_effects.gamma.
                    - Raw mass:
                        · For each {merchant_id, utc_day, tz_group_id}:
                            - mass_raw = base_share(merchant, group) × gamma(merchant, utc_day, group).
                        · Domain:
                            - base_share ≥ 0 and gamma > 0 ⇒ mass_raw ≥ 0,
                            - abort if any computed mass_raw is NaN or negative.

(mass_raw per merchant×day×group),
day grid D
                ->  (S4.5) Cross-group renormalisation (per merchant, per day)
                    - For each {merchant_id, utc_day}:
                        · compute denom_raw = Σ_group mass_raw(merchant, utc_day, group)
                          summing in the lexicographic group order from S4.3.
                        · require denom_raw > 0; abort otherwise.
                    - Normalise:
                        · For each group:
                              p_group = mass_raw / denom_raw.
                    - Tiny-negative guard:
                        · if some p_group = −δ with 0 < δ ≤ ε:
                              - clamp that p_group to 0,
                              - re-normalise remaining groups once so that
                                |Σ_group p_group − 1| ≤ ε.
                        · abort if any p_group < −ε or if, after re-normalisation,
                          |Σ_group p_group − 1| > ε.
                    - Echo values:
                        · for each row, carry:
                              - base_share (from S4.3),
                              - gamma (from s3_day_effects),
                              - mass_raw and denom_raw if the schema exposes them.

(group-level p_group, base_share, gamma, mass_raw?, denom_raw?),
day grid D
                ->  (S4.6) Row materialisation (writer order = PK)
                    - For every {merchant_id, tz_group_id} in the merchant’s group set
                      and every utc_day ∈ D:
                        · emit exactly one row:
                              { merchant_id,
                                utc_day,
                                tz_group_id,
                                p_group,
                                base_share,
                                gamma,
                                created_utc = created_utc_S0,
                                [mass_raw?, denom_raw?] }.
                    - Writer order:
                        · emit rows strictly in PK order:
                              [merchant_id ↑, utc_day ↑, tz_group_id ↑].
                    - In-memory coverage check:
                        · for each merchant_id,
                          for each tz_group_id in its group set,
                          for each utc_day ∈ D,
                          there is exactly one row ready to write.

(S4.6 rows),
[Schema+Dict]
                ->  (S4.7) Publish s4_group_weights (write-once; atomic)
                    - Target partition (Dictionary-resolved):
                        · data/layer1/2B/s4_group_weights/seed={seed}/fingerprint={manifest_fingerprint}/
                    - Immutability & idempotency:
                        · if partition is empty → allowed to publish,
                        · if non-empty:
                              - allowed only if existing bytes are bit-identical
                                (idempotent re-emit),
                              - otherwise abort with IMMUTABLE_OVERWRITE.
                    - Publish:
                        · write Parquet files to a staging directory on the same filesystem,
                        · fsync, then atomically move into the final Dictionary path,
                        · no partially written files may become visible.

(published s4_group_weights),
[Schema+Dict],
[S0 Gate & Identity]
                ->  (S4.8) Post-publish assertions & run-report
                    - Path↔embed equality:
                        · any embedded {seed, manifest_fingerprint} in s4_group_weights
                          must equal the partition tokens.
                    - Schema & ordering:
                        · validate against schemas.2B.yaml#/plan/s4_group_weights
                          (columns_strict, PK, partition_keys, sort_keys).
                        · confirm on-disk sort order matches [merchant_id, utc_day, tz_group_id].
                    - Coverage grid:
                        · recompute merchant group sets and day grid from the written table,
                          ensure:
                              - utc_day values exactly match D from s3_day_effects,
                              - for every merchant_id and every tz_group_id in its group set,
                                and every utc_day ∈ D, exactly one row exists.
                    - Normalisation audits:
                        · for each {merchant_id}:
                              - recompute Σ_group base_share over all groups,
                              - require |Σ_group base_share − 1| ≤ ε.
                        · for each {merchant_id, utc_day}:
                              - recompute Σ_group p_group over all groups,
                              - require |Σ_group p_group − 1| ≤ ε.
                    - Environment guards:
                        · confirm that only s1_site_weights, site_timezones, s3_day_effects
                          (plus S0 receipt and sealed_inputs_v1) were read,
                          and that no RNG or network I/O was used.
                    - Run-report:
                        · emit one structured JSON run-report for this state, including:
                              - component="2B.S4",
                              - {seed, manifest_fingerprint},
                              - counts (merchants, groups, days, rows_written),
                              - normalisation/coverage results and any WARN/FAIL codes.
                        · any persisted copy of this report is auxiliary; authoritative semantics
                          remain with the s4_group_weights table.

Downstream touchpoints
----------------------
- **2B.S5 — Routing selection (group → site):**
    - MUST treat s4_group_weights as the sole authority for per-{merchant, utc_day, tz_group_id} p_group.
    - S5 uses p_group to pick a tz_group per arrival before sampling a site via S2 alias tables.
- **2B.S7 — Routing audit:**
    - Uses s4_group_weights together with s3_day_effects and routing logs to verify
      that observed routing behaviour matches the planned day-specific group mixes.
- **2B.S8 — Validation bundle:**
    - Includes s4_group_weights as a key evidence surface; downstream components MUST honour
      the segment-wide “No PASS → No Read” gate on the 2B validation bundle when consuming
      group weights or any routing surface derived from them.
```