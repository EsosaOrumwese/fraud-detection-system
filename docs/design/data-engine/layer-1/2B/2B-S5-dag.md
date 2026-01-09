```
        LAYER 1 · SEGMENT 2B — STATE S5 (ROUTER CORE: GROUP → SITE)  [RNG-BOUNDED]

Authoritative inputs (read-only at S5 entry)
--------------------------------------------
[S0 Gate & Identity]
    - s0_gate_receipt_2B @ data/layer1/2B/s0_gate_receipt/fingerprint={manifest_fingerprint}/…
      · proves: 2B.S0 ran for this manifest_fingerprint and verified 1B PASS
      · binds run identity: { seed, manifest_fingerprint, parameter_hash } for routing
      · provides canonical created_utc = verified_at_utc (echoed into logs)
    - sealed_inputs_2B @ data/layer1/2B/sealed_inputs/manifest_fingerprint={manifest_fingerprint}/…
      · sealed inventory of cross-layer/policy artefacts for this fingerprint
      · S5 MUST ensure every cross-layer/policy read is present here

[Schema+Dict]
    - schemas.2B.yaml                     (shape authority for s1_site_weights, s4_group_weights,
                                           s2_alias_index, s2_alias_blob, s5_selection_log_row)
    - schemas.2A.yaml                     (shape authority for site_timezones)
    - schemas.layer1.yaml, schemas.ingress.layer1.yaml
      · core types, RNG envelope, rng_audit_log/rng_trace_log event shapes
    - dataset_dictionary.layer1.2B.yaml   (ID→path/partitions for 2B plan/log surfaces incl. s5_selection_log)
    - dataset_dictionary.layer1.2A.yaml   (ID→path/partitions for site_timezones)
    - artefact_registry_2B.yaml           (existence/licence/retention; non-authoritative for paths)

[Plan surfaces: probabilities & alias tables]
    - s4_group_weights @ seed={seed} / fingerprint={manifest_fingerprint}
        · producer: 2B.S4
        · PK: [merchant_id, utc_day, tz_group_id]
        · role: RNG-free p_group(m, d, tz_group_id); **sole** authority for Stage-A group probabilities
    - s1_site_weights @ seed={seed} / fingerprint={manifest_fingerprint}
        · producer: 2B.S1
        · PK: [merchant_id, legal_country_iso, site_order]
        · columns: p_weight, weight_source, quantised_bits, floor_applied, created_utc
        · role: long-run per-site masses; used to build per-group site alias in Stage-B
    - site_timezones @ seed={seed} / fingerprint={manifest_fingerprint}
        · producer: 2A.S2
        · PK: [merchant_id, legal_country_iso, site_order]
        · columns: tzid (tz_group_id)
        · role: site → tz_group mapping for filtering S1 and coherence checks
    - s2_alias_index @ seed={seed} / fingerprint={manifest_fingerprint}
    - s2_alias_blob  @ seed={seed} / fingerprint={manifest_fingerprint}
        · producer: 2B.S2
        · role: alias directory + binary blob; S5 uses them to decode merchant-level alias
          (layout_version, endianness, alignment_bytes, quantised_bits, blob_sha256)

[Policies (S0-sealed, token-less)]
    - route_rng_policy_v1
        · defines routing RNG engine (Philox variant), routing stream,
          and two single-uniform event families:
            · alias_pick_group
            · alias_pick_site
        · specifies mapping from {seed, parameter_hash, run_id} → stream keys and initial counters,
          and the RNG envelope (before/after counters, blocks=1, draws="1" per event)
    - alias_layout_policy_v1
        · alias layout_version, endianness, alignment_bytes, quantised_bits
        · policy_digest echoed in s2_alias_index.header.policy_digest
        · S5 verifies compatibility before any alias decode

[Outputs (log surfaces; no mandatory plan dataset)]
    - rng_audit_log   @ logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl
    - rng_trace_log   @ logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl
    - Event families (per-arrival):
        · alias_pick_group  @ logs/rng/events/2B/alias_pick_group/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…
        · alias_pick_site   @ logs/rng/events/2B/alias_pick_site /seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/…
    - Optional: s5_selection_log @ trace/2B/s5_selection_log/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/utc_day={d}/…
        · format jsonl; writer order = arrival order; manifest_fingerprint column present but not a partition key

[Numeric & RNG posture]
    - Numeric:
        · IEEE-754 binary64, round-to-nearest-even; no FMA/FTZ/DAZ
        · stable serial reductions; no data-dependent sum reorderings
    - RNG:
        · counter-based Philox (engine from route_rng_policy_v1)
        · **exactly two single-uniform events per routed arrival**:
            - 1 draw on alias_pick_group (Stage-A)
            - 1 draw on alias_pick_site  (Stage-B)
        · open-interval uniforms u ∈ (0,1); mapping from counters to u is fixed by layer RNG law
        · rng_trace_log updated once after each event append (cumulative totals)
    - Catalogue:
        · all reads by Dataset Dictionary ID and declared partitions
        · cross-layer/policy inputs MUST appear in sealed_inputs_2B


----------------------------------------------------------------------
DAG — 2B.S5 (Per-arrival router: group → site, with RNG evidence)  [RNG-BOUNDED]

[S0 Gate & Identity],
[Schema+Dict]
                ->  (S5.1) Trust S0, fix run identity & logging scope
                    - Resolve s0_gate_receipt_2B and sealed_inputs_2B for manifest_fingerprint via Dictionary.
                    - Verify:
                        · receipt + inventory schema-valid,
                        · manifest_fingerprint in receipt equals path token,
                        · seed and parameter_hash match this routing run.
                    - Fix identity:
                        · run identity for routing/log lineage: {seed, parameter_hash, run_id}
                        · plan identity for plan surfaces: {seed, manifest_fingerprint}
                    - Capture created_utc_S0 ← s0_gate_receipt_2B.verified_at_utc;
                      S5 SHALL echo this into selection_log.created_utc (if enabled).

[S0 Gate & Identity],
[Schema+Dict],
s4_group_weights,
s1_site_weights,
site_timezones,
s2_alias_index,
s2_alias_blob,
route_rng_policy_v1,
alias_layout_policy_v1
                ->  (S5.2) Resolve inputs, enforce S0-evidence rule & pre-flight checks
                    - Resolve via Dataset Dictionary (no literals):
                        · s4_group_weights@seed={seed}/fingerprint={manifest_fingerprint}
                        · s1_site_weights@seed={seed}/fingerprint={manifest_fingerprint}
                        · site_timezones@seed={seed}/fingerprint={manifest_fingerprint}
                        · s2_alias_index@seed={seed}/fingerprint={manifest_fingerprint}
                        · s2_alias_blob@seed={seed}/fingerprint={manifest_fingerprint}
                        · route_rng_policy_v1, alias_layout_policy_v1 (token-less; S0-sealed path+digest)
                    - S0-evidence rule:
                        · route_rng_policy_v1, alias_layout_policy_v1, site_timezones, s2_alias_index,
                          and s2_alias_blob MUST appear in sealed_inputs_2B for this fingerprint.
                    - Validate shapes against schemas.2B.yaml/schemas.2A.yaml anchors.
                    - Alias parity (once per run):
                        · assert s2_alias_index.header.policy_digest == digest(alias_layout_policy_v1),
                        · recompute SHA256 over raw s2_alias_blob bytes and assert it equals
                          s2_alias_index.header.blob_sha256.
                        · Abort on mismatch.
                    - Extract layout echo:
                        · layout_version, endianness, alignment_bytes, quantised_bits from s2_alias_index header.
                    - RNG stream wiring (from route_rng_policy_v1):
                        · derive routing stream (Philox key) from {seed, parameter_hash, run_id, rng_stream_id},
                        · configure two event families:
                            - alias_pick_group (single-uniform per event),
                            - alias_pick_site  (single-uniform per event),
                          both under the standard RNG envelope (before/after counters, blocks=1, draws="1").
                        · counters are strictly increasing; no reuse or wrap.
                    - Determine whether s5_selection_log is enabled by policy.

[Plan surfaces],
[Schema+Dict]
                ->  (S5.3) Ephemeral caches & deterministic ordering (RNG-free)
                    - Define stable ordering:
                        · groups: read s4_group_weights in PK order (merchant_id, utc_day, tz_group_id);
                          index g ∈ {0..G−1} follows that order.
                        · sites: read s1_site_weights in PK order, then filter by tzid from site_timezones;
                          index k ∈ {0..N−1} follows that filtered order.
                    - Define two in-memory caches (ephemeral, NOT persisted):
                        · GROUP_ALIAS[m, d]      → alias structure over tz_group_id for merchant m on UTC day d.
                        · SITE_ALIAS[m, d, g]    → alias structure over site_id for merchant m, UTC day d, tz-group g.
                    - Cache law:
                        · caches are keyed only by (m, d) and (m, d, g),
                        · building/evicting caches is deterministic and MUST NOT affect outcomes:
                          same arrivals → same selections, even if caches are rebuilt.

----------------------------------------------------------------------
Per-arrival router for an arrival (m, t)
----------------------------------------

**Inputs available at this point:**  
  - s4_group_weights (p_group per merchant×day×tz_group)  
  - s1_site_weights (p_weight per site)  
  - site_timezones (tz_group_id per site)  
  - s2_alias_index + s2_alias_blob (alias tables)  
  - route_rng_policy_v1 (RNG mapping; alias_pick_group/site families)  

[A] Stage-A — Group pick (1 uniform)
------------------------------------

(s4_group_weights, GROUP_ALIAS cache),
route_rng_policy_v1,
alias_layout_policy_v1
                ->  (S5.A1) Resolve UTC day & ensure group alias exists (RNG-free)
                    - Compute UTC day d = floor_UTC_day(t) (00:00:00–23:59:59.999999 UTC).
                    - If GROUP_ALIAS[m, d] is NOT present:
                        · read S4 rows for (merchant_id=m, utc_day=d) in PK tz_group_id order,
                        · extract p_group(m,d,group) into a vector p[0..G−1],
                        · assert Σ_g p_group ≈ 1 within S4’s numeric tolerance,
                        · build alias tables (prob[0..G−1], alias[0..G−1]) deterministically
                          using the Walker/Vose builder described in the spec (no RNG),
                        · cache result as GROUP_ALIAS[m, d].
                    - If no S4 row exists for (m, d) → Abort (no group mix for that arrival’s day).

(routing stream, alias_pick_group family),
GROUP_ALIAS[m,d]
                ->  (S5.A2) Draw uniform & decode group (RNG-consuming)
                    - Draw one Philox-derived uniform u_group ∈ (0,1) using the alias_pick_group family:
                        · increment routing counters for this event only,
                        · record RNG envelope (before/after counters, blocks=1, draws="1").
                    - Decode group via alias:
                        · j = floor(u_group · G),
                        · r = u_group · G − j,
                        · if r < prob[j] → pick logical group index g = j;
                          else            → pick g = alias[j].
                    - Map index g back to tz_group_id via the stable ordering from S4 for this (m, d).
                    - If diagnostics enabled:
                        · remember (tz_group_id, counters for alias_pick_group) in a local stack frame
                          for possible selection_log emission (no writes yet).

[B] Stage-B — Site pick within chosen tz_group (1 uniform)
----------------------------------------------------------

(s1_site_weights, site_timezones, SITE_ALIAS cache),
tz_group_id from Stage-A,
alias_layout_policy_v1
                ->  (S5.B1) Ensure per-group site alias exists (RNG-free)
                    - If SITE_ALIAS[m, d, tz_group_id] is NOT present:
                        · filter S1×site_timezones:
                              - join on (merchant_id, legal_country_iso, site_order),
                              - keep only rows where tzid == tz_group_id.
                        · Abort if the filtered set is empty (no eligible sites for chosen group).
                        · from filtered rows, in PK order, take masses:
                              w_i = p_weight (or equivalent policy-declared weight column),
                              ensure w_i ≥ 0 and finite.
                        · compute Σ_i w_i in stable serial order; require Σ_i w_i > 0.
                        · normalise:
                              p_i = w_i / Σ_i w_i  (binary64).
                        · build alias prob_site[0..N−1], alias_site[0..N−1] deterministically
                          using the same Walker/Vose builder as in Stage-A.
                        · cache SITE_ALIAS[m, d, tz_group_id].
                    - If SITE_ALIAS already exists, reuse it; cache presence MUST NOT change outcomes.

(routing stream, alias_pick_site family),
SITE_ALIAS[m,d,tz_group_id]
                ->  (S5.B2) Draw uniform & decode site (RNG-consuming)
                    - Draw one Philox-derived uniform u_site ∈ (0,1) using alias_pick_site family:
                        · increment routing counters; record RNG envelope (before/after, blocks=1, draws="1").
                    - Decode site index:
                        · j = floor(u_site · N),
                        · r = u_site · N − j,
                        · if r < prob_site[j] → k = j;
                          else                → k = alias_site[j].
                    - Map index k to a concrete site row (merchant_id, legal_country_iso, site_order),
                      and obtain site_id (e.g. from 1A/1B scheme).
                    - Mapping coherence (MUST):
                        · use site_timezones to look up tz_group_id(site_id),
                        · assert tz_group_id(site_id) == chosen tz_group_id from Stage-A,
                        · Abort on mismatch.

[C] Emit evidence (RNG logs & optional selection log)
-----------------------------------------------------

(alias_pick_group event envelope),
(alias_pick_site  event envelope),
rng_audit_log,
rng_trace_log
                ->  (S5.C1) Append RNG events & update core logs
                    - Append, in this strict order:
                        1. alias_pick_group event record:
                            · includes stream_id, counters_before/after, blocks=1, draws="1".
                        2. alias_pick_site event record:
                            · same envelope pattern.
                    - After each event append:
                        · update rng_trace_log once with cumulative totals
                          (events_seen, draws_seen, blocks_seen, counters_hi/lo).
                    - rng_audit_log captures per-family high-level counts and invariants.
                    - RNG logs are partitioned by [seed, parameter_hash, run_id]; they are never fingerprint-partitioned.

(selection_log enabled?),
arrival (m, t),
tz_group_id,
site_id,
RNG counters (group+site),
created_utc_S0
                ->  (S5.C2) Append optional s5_selection_log row (if enabled)
                    - If diagnostics are disabled by policy:
                        · skip this step (no dataset is created).
                    - If enabled:
                        · compute:
                              utc_timestamp = t (rfc3339_micros),
                              utc_day      = floor_UTC_day(t),
                              manifest_fingerprint column = this run’s manifest_fingerprint.
                        - Append a JSONL row with fields:
                              merchant_id,
                              utc_timestamp,
                              utc_day,
                              tz_group_id,
                              site_id,
                              rng_stream_id,
                              ctr_group_hi, ctr_group_lo,
                              ctr_site_hi,  ctr_site_lo,
                              manifest_fingerprint,
                              created_utc = created_utc_S0.
                        - Partition:
                              [seed, parameter_hash, run_id, utc_day] as per Dictionary.
                        - Writer order:
                              append rows in **arrival order** within each partition.
                        - Immutability:
                              per-partition files are write-once per run; re-emits must be byte-identical.

----------------------------------------------------------------------
Determinism, boundaries & downstream touchpoints
------------------------------------------------
- Determinism:
    - Exactly 2 draws per routed arrival (1 group, 1 site).
    - Open-interval uniforms only; mapping from counters→u is fixed by layer RNG law.
    - Cache behaviour (GROUP_ALIAS, SITE_ALIAS) MUST NOT affect outcomes:
      rebuilding caches yields byte-identical selections for the same arrival stream.
- Authority boundaries:
    - Stage-A group probabilities come **only** from s4_group_weights; S5 MUST NOT recompute them.
    - Stage-B site probabilities per group come from S1 p_weight filtered by site_timezones;
      S5 MUST NOT invent new weights or touch alias layout.
    - Alias decode uses **only** s2_alias_index + s2_alias_blob (and policy echo);
      S5 MUST NOT scan or guess inside blob beyond the policy-declared layout.
- Downstream:
    - 2B.S6 (virtual edges) uses the chosen site_id/tz_group_id and RNG lineage but MUST NOT mutate alias tables.
    - 2B.S7 (audit) and 2B.S8 (validation bundle) use:
        · s4_group_weights, s1_site_weights, s2_alias_index/blob, s3_day_effects, and S5’s RNG logs/selection_log
      to verify that routing behaviour matches the declared plan.
    - Layer-2 (5A/5B) sees S5 as the runtime router: arrivals in, (m, tz_group_id, site_id) out, under the
      RNG envelope and plan surfaces governed by 2B.S1–S4 and gated by 2B’s validation bundle.
```
