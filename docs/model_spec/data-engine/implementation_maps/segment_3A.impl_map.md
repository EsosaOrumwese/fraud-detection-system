# Segment 3A - Compiled Implementation Map (v0.1.0)

This is the reviewer-facing view derived from `segment_3A.impl_map.yaml`.
Use it to answer:
- What is frozen vs flexible?
- Where are the gates and what they authorize?
- Where are the performance hotspots and safe levers?
- If something is wrong, which state owns it?

Assumptions applied (as you requested):
- Token naming is standardized to `manifest_fingerprint` everywhere (paths/partitions/examples).
- Parameter-hash closure explicitly includes `zone_mixture_policy`, `country_zone_alphas`, and `zone_floor_policy` (per `artefact_registry_3A.yaml`), so 3A parameter-scoped priors cannot drift without a parameter_hash change.

---

## 1) One-screen relationship diagram
```
Upstream gates (all MUST be verified in S0)
  1A: data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
  1B: data/layer1/1B/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
  2A: data/layer1/2A/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
  (all are indexed-bundle gates: index.json drives hash; FAIL_CLOSED if mismatch)

Pinned upstream surfaces (used downstream)
  - 1A outlet_catalogue (seed + manifest_fingerprint)   [required]
  - 2A site_timezones (seed + manifest_fingerprint)     [optional pin per S0/S1]
  - 2A tz_timetable_cache (manifest_fingerprint)        [optional pin per S0/S1/S2]
  - 2A s4_legality_report (seed + manifest_fingerprint) [optional pin per S0]

Pinned sealed policies / refs
  - zone_mixture_policy     (S1 escalation law)
  - country_zone_alphas     (S2 alpha priors)
  - zone_floor_policy       (S2 floor/bump)
  - day_effect_policy_v1    (S5 universe-hash component)
  - iso3166_canonical_2024, tz_world_2025a (domain/zone refs)

3A pipeline
  +- S0 (gate-in foundation):
       - verifies 1A/1B/2A gates (FAIL_CLOSED)
       - seals upstream inputs + policies/refs
       - writes s0_gate_receipt_3A + sealed_inputs_3A

  +- S1 (deterministic authority): mixture policy -> escalation queue
  |    -> s1_escalation_queue (seed + manifest_fingerprint)
  |
  +- S2 (deterministic authority): country->zone priors + floor/bump
  |    -> s2_country_zone_priors (parameter_hash)
  |
  +- S3 (RNG emitter): Dirichlet zone shares for escalated pairs only
  |    -> s3_zone_shares (seed + manifest_fingerprint)
  |    -> rng_event_zone_dirichlet + rng_audit_log + rng_trace_log (seed + parameter_hash + run_id)
  |
  +- S4 (deterministic): integerise shares -> counts (escalated only)
  |    -> s4_zone_counts (seed + manifest_fingerprint)
  |
  +- S5 (deterministic egress + digests):
  |    -> zone_alloc (seed + manifest_fingerprint)  [escalated only in v1]
  |    -> zone_alloc_universe_hash (manifest_fingerprint)
  |
  +- S6 (validator):
  |    -> s6_validation_report_3A + s6_issue_table_3A + s6_receipt_3A
  |    -> emits validation receipt gate (3A.S6.validation_receipt)
  |
  +- S7 (finalizer / consumer gate):
       - precondition: S6 PASS
       - writes validation_bundle_3A + index.json + _passed.flag
       - emits 3A.final.bundle_gate

Consumer rule (binding): downstream MUST verify 3A final bundle gate for the same
manifest_fingerprint before reading `zone_alloc` / `zone_alloc_universe_hash`.
```

Run-report surfaces (per dictionary):
- segment_state_runs: one row per state invocation (S0-S7), scoped by utc_day.
- per-state run reports: s1_run_report_3A .. s7_run_report_3A (S2 is parameter_hash-scoped; others are seed + manifest_fingerprint).

---

## 2) Gates and what they authorize

### Upstream gates (verified in S0)
- 1A.final.bundle_gate -> authorizes reading `outlet_catalogue`
- 1B.final.bundle_gate -> (present for full lineage; 3A is still required to verify it per S0)
- 2A.final.bundle_gate -> authorizes reading optional 2A pins (site_timezones/cache/report)

All use index.json-driven verification; S0 FAIL_CLOSED on any mismatch.

### Gate-in receipt (3A.S0.gate_in_receipt)
- Evidence: `s0_gate_receipt_3A` + `sealed_inputs_3A`
- Meaning: "S0 verified upstream gates and pinned 3A's inputs/policies for this manifest_fingerprint"
- Rule: S1-S7 must fail-closed if receipt missing.

### Validation receipt (3A.S6.validation_receipt)
- Evidence: `s6_receipt_3A` (manifest_fingerprint-scoped)
- Meaning: "S6 structural validation verdict is PASS/FAIL"
- Rule: S7 must not publish final gate unless S6 PASS.

### Final consumer gate (3A.final.bundle_gate)
- Location: `data/layer1/3A/validation/manifest_fingerprint={manifest_fingerprint}/`
- Evidence: `index.json` + `_passed.flag`
- Hash law (per 3A S7): **digest-of-digests**:
  - `bundle_sha256_hex = SHA256(concat(entry.sha256_hex strings in index order))`
  - `_passed.flag` content is JSON `{ "sha256_hex": "<hex64>" }`
- Authorizes reads of `zone_alloc`, `zone_alloc_universe_hash`, and supporting plan surfaces.

---

## 3) Frozen surfaces (do not change)

Segment-wide:
- S0 must verify upstream gates (1A/1B/2A) before admitting any upstream outputs as sealed inputs.
- Downstream states must require S0 receipt before reading sealed inputs/policies.
- No new semantic ordering authority is created.

S1 (escalation authority):
- Deterministic classification of (merchant_id, legal_country_iso) into Monolithic vs Escalated per `zone_mixture_policy`.
- Downstream MUST NOT re-evaluate mixture policy; S1 is the sole authority.

S2 (priors authority):
- Deterministic alpha-vector construction per country over tzid domain plus deterministic floor/bump.
- `s2_country_zone_priors` is the sole authority for priors used downstream.

S3 (Dirichlet RNG):
- Emit outputs/events **only for escalated pairs**.
- Dirichlet via gamma-component draws; draw counts vary with zone_count.
- RNG accounting must reconcile across:
  - rng_event_zone_dirichlet (counter_before/after, blocks, draws)
  - rng_audit_log
  - rng_trace_log (trace-after-each-event)

S4 (integerisation):
- Deterministic integerisation; must conserve totals:
  - sum_z n(m,c,z) == N(m,c)
- No outputs for monolithic pairs.

S5 (egress + universe hash):
- `zone_alloc` contains escalated pairs only (v1 posture).
- Universe hash construction is binding:
  - component digests (priors/policies/day_effect_policy/zone_alloc parquet digest)
  - concatenation order fixed as specified.

S6/S7 (validation + gate publish):
- S6 is the sole PASS/FAIL verdict authority.
- S7 must not publish final gate unless S6 PASS.
- Final gate uses digest-of-digests law (not raw-bytes concat), and `_passed.flag` is JSON.

---

## 4) Flexible surfaces (optimize freely; must preserve invariants)

- Streaming vs batch upstream gate verification (S0) as long as the index law is matched exactly.
- Vectorization and data structures for S2/S4 computations, as long as deterministic and ordering contracts hold.
- S3 RNG stream-id construction is flexible if deterministic and join-consistent, and accounting reconciles.
- Parquet physical layout for zone_alloc is flexible if:
  - ordering keys are preserved for determinism, and
  - zone_alloc_parquet_digest uses canonical path ordering.

---

## 5) Hotspots + safe optimization levers

### S0 (gate verification)
Hotspot: hashing large upstream bundles.
Safe levers: streaming hashing; avoid materializing evidence; parallel hashing only if deterministic ordering is preserved.

### S2 (priors construction)
Hotspot: country x tzid domain expansion + floor/bump.
Safe levers: precompute tzid domains per country; deterministic loops; vectorize arithmetic.

### S3 (Dirichlet draws)
Hotspot: RNG-heavy per escalated pair; log IO.
Safe levers: per-pair batching with deterministic partitioning; buffered log writes; keep trace discipline strict.

### S4 (integerisation)
Hotspot: per-pair rounding/tie-break.
Safe levers: deterministic largest-remainder style integerisation; per-pair processing.

### S5 (digests)
Hotspot: computing parquet digest over many files.
Safe levers: stream hashing per file; deterministic path ordering.

### S6/S7 (validation + bundling)
Hotspot: scanning multiple plan surfaces + RNG reconciliation.
Safe levers: streaming validators; bounded-memory counters; deterministic index construction.

---

## 6) Debug hooks (to localize failures)

Critical hooks:
- S0 receipt records:
  - verified upstream digests + bundle roots (1A/1B/2A)
  - sealed input IDs + digests
- S1: escalated vs monolithic counts + first-N reasons
- S3: events_emitted, draws_total, and first-N counter anomalies
- S4: sum checks per pair + first-N violations
- S5: component digests + final routing_universe_hash
- S6: bucket failures by class + first-N offending keys
- S7: bundle member list + computed bundle_sha256_hex + missing-member diagnostics

Baseline (per state):
- deterministic rowcounts + distinct PK counts
- deterministic key checksums (sampled deterministically)

---

## 7) Review flags (assumed resolved)
- Standardize `manifest_fingerprint` token usage everywhere to match dictionaries.
- Confirm parameter_hash governance includes `zone_mixture_policy`, `country_zone_alphas`, and `zone_floor_policy` so parameter-scoped priors cannot drift without a parameter_hash change.
