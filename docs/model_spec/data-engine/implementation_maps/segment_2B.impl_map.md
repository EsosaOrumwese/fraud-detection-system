# Segment 2B — Compiled Implementation Map (v0.1.0)

This is the reviewer-facing view derived from `segment_2B.impl_map.yaml`.
Use it to answer:
- What is frozen vs flexible?
- Where are the gates and what they authorize?
- Where are the obvious performance hotspots and safe levers?
- If something is wrong, which state owns it?

Assumptions applied (as you requested):
- Token naming is standardized to `manifest_fingerprint` everywhere (paths/partitions/examples).
- Any accidental “2A is Layer-2” wording is corrected (2A is the pinned upstream within Layer-1).

---

## 1) One-screen relationship diagram
```
Upstream inputs (hard)
  1B:
    - site_locations (seed + manifest_fingerprint)
    - final gate: data/layer1/1B/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
      (indexed_bundle: index.json drives hash)

  2A:
    - site_timezones (seed + manifest_fingerprint)   [required pin]
    - tz_timetable_cache (manifest_fingerprint)     [optional pin; coherence/audit only]

Pinned policy packs (fingerprint-only)
  - route_rng_policy_v1        (streams/substreams/budgets for S5/S6)
  - alias_layout_policy_v1     (alias encoding/decoding law)
  - day_effect_policy_v1       (gamma cadence/variance/clipping for S3)
  - virtual_edge_policy_v1     (edge domain + weights/attrs for S6)

2B pipeline
  └─ S0 (gate-in foundation):
       - verifies 1B final bundle gate (FAIL_CLOSED if mismatch)
       - seals/pins upstream inputs + policy packs
       - writes s0_gate_receipt_2B + sealed_inputs_2B

  ├─ S1 (deterministic): per-site base weights → quantise/freeze
  │    → s1_site_weights (seed + manifest_fingerprint)
  │
  ├─ S2 (deterministic): per-merchant alias tables (O(1) decode)
  │    → s2_alias_index + s2_alias_blob (seed + manifest_fingerprint)
  │
  ├─ S3 (RNG-bounded plan): “corporate-day” gamma multipliers by tz-group
  │    → s3_day_effects (seed + manifest_fingerprint)
  │    (one Philox draw per row; RNG provenance embedded in table rows)
  │
  ├─ S4 (deterministic plan): tz-group mix weights per day
  │    → s4_group_weights (seed + manifest_fingerprint)
  │
  ├─ S5 (router core, per-arrival RNG):
  │    - Stage A: pick tz_group via alias (1 draw)
  │    - Stage B: pick site within group via alias (1 draw)
  │    → rng_event_alias_pick_group + rng_event_alias_pick_site + rng_audit_log + rng_trace_log
  │    → optional s5_selection_log (by utc_day)
  │
  ├─ S6 (virtual edge branch, per-arrival RNG):
  │    - only if is_virtual==1: pick cdn_edge (1 draw)
  │    → rng_event_cdn_edge_pick + rng_audit_log + rng_trace_log
  │    → optional s6_edge_log (by utc_day)
  │
  ├─ S7 (auditor): validates S2/S3/S4 + conditional router evidence
  │    → s7_audit_report (seed + manifest_fingerprint)
  │
  └─ S8 (finalizer / consumer gate):
       - discovers seeds by intersecting required plan surfaces
       - requires all s7_audit_report PASS
       - writes validation_bundle_2B + index.json + _passed.flag (indexed_bundle law)

Consumer rule (binding): downstream MUST verify 2B final bundle gate for the same
manifest_fingerprint before reading 2B plan surfaces (alias tables, day effects, group weights).
```

---

## 2) Gates and what they authorize

### Upstream gate (1B.final.bundle_gate) — MUST be verified in S0
- Location: `data/layer1/1B/validation/manifest_fingerprint={manifest_fingerprint}/`
- Evidence: `index.json` + `_passed.flag`
- Hash law: hash indexed files (exclude `_passed.flag`) in ASCII-lex order of `index.json.path`
- S0 FAIL_CLOSED if mismatch.

### Gate-in receipt (2B.S0.gate_in_receipt)
- Evidence: `s0_gate_receipt_2B` (fingerprint-scoped JSON)
- Meaning: “S0 verified 1B PASS and pinned upstream inputs + policy packs”
- Rule: downstream S1–S8 must fail-closed if missing.

### Final consumer gate (2B.final.bundle_gate)
- Location: `data/layer1/2B/validation/manifest_fingerprint={manifest_fingerprint}/`
- Evidence: `index.json` + `_passed.flag`
- Same index-driven hashing law; published atomically.
- Authorizes downstream reads of: `s2_alias_index`, `s2_alias_blob`, `s3_day_effects`, `s4_group_weights`.

---

## 3) Frozen surfaces (do not change)

Segment-wide:
- No PASS → no read: S0 must verify 1B.final.bundle_gate before reading any 1B egress.
- S0 seals/pins the minimum input set and policy packs; downstream must require S0 receipt.
- Path↔embed equality for manifest_fingerprint in fingerprint-scoped receipts/manifests.
- Plan partitions are `[seed, manifest_fingerprint]`; receipts/bundles are `[manifest_fingerprint]`.
- Routing logs/events are `[seed, parameter_hash, run_id]`.
- Optional per-day logs are `[seed, parameter_hash, run_id, utc_day]`.

S1 (weights):
- Deterministic normalisation + quantisation grid `G=2^b` with tie-to-even and deterministic remainder tie-break by PK.
- created_utc = S0.verified_at_utc.

S2 (alias tables):
- Encoding/decoding law is fixed by `alias_layout_policy_v1` (layout/endianness/alignment).
- Blob bytes are authoritative; index must match blob sha256 and offsets.
- S2 SHALL NOT read site_timezones or tz_timetable_cache.

S3 (day effects):
- Exactly **one Philox draw per output row**.
- RNG provenance is embedded in rows (`rng_stream_id`, `rng_counter_hi/lo`); no `rng_event_*` families emitted here.
- Row order fixed: `(merchant_id, utc_day, tz_group_id)`.
- created_utc = S0.verified_at_utc.

S4 (group weights):
- Deterministic normalisation: Σ p_group = 1 for each (merchant_id, utc_day).
- Row order fixed: `(merchant_id, utc_day, tz_group_id)`.
- created_utc = S0.verified_at_utc.

S5 (router core):
- Two-stage routing is binding:
  1) `alias_pick_group` (1 draw)
  2) `alias_pick_site` (1 draw)
- Event ordering is binding (group event precedes site event per arrival).
- Trace reconciliation must hold: total_draws equals sum of both families and equals 2 × routed arrivals.

S6 (virtual edge branch):
- Bypass non-virtual arrivals (no RNG, no outputs).
- For virtual arrivals: exactly one draw and one `cdn_edge_pick` event.

S7/S8:
- Fail-closed: S8 must not publish `_passed.flag` unless all discovered seeds have PASS audits.
- Final gate uses indexed_bundle law (index.json-driven hashing; flag excluded; atomic publish; write-once).

---

## 4) Flexible surfaces (optimize freely; must preserve invariants)

- Vectorization/batching in S1/S2/S3/S4 so long as deterministic ordering + quantisation/counter laws hold.
- Alias construction method (Vose vs equivalent) allowed if encoded bytes and decode semantics match.
- Router implementation may batch arrivals, but **must preserve arrival order** for any ordered logs when enabled.
- Log sharding is allowed only if log contracts are set-semantics; otherwise preserve append order.
- S7 audit implementation can be streaming/bounded-memory so long as deterministic evidence matches schemas.

---

## 5) Hotspots + safe optimization levers

### S1 (weights + quantisation)
Hotspots: per-merchant normalization and fixed-grid quantisation.
Safe levers: process per merchant_id with deterministic chunking; avoid global sorts beyond declared keys.

### S2 (alias tables)
Hotspots: per-merchant table build + blob packing.
Safe levers: batch per merchant; sequential blob writer; avoid per-row overhead; keep deterministic merchant ordering.

### S3 (day effects surface)
Hotspots: large surface size (merchants × days × tz_groups).
Safe levers: generate per merchant with deterministic day loops; avoid unordered group iteration.

### S5/S6 (per-arrival routing)
Hotspots: event/log IO at high throughput.
Safe levers: buffered writes; careful batching; keep ordering contracts for selection/edge logs.

### S7/S8 (audits + bundling)
Hotspots: alias decode checks + log reconciliation + hashing evidence files.
Safe levers: streaming scans; bounded-memory counters; stream hashing and deterministic index construction.

---

## 6) Debug hooks (to localize failures)

Critical hooks:
- S0 receipt must record:
  - resolved upstream bundle root path
  - verified 1B `_passed.flag` digest
  - sealed input/policy IDs + digests
  - verified_at_utc
- S2 index: merchants_count and first-N merchant offsets
- S3: expected_rows vs observed_rows, expected_draws (=rows) vs observed draw provenance anomalies
- S5/S6: events_emitted per family, arrivals_routed, trace reconciliation counters
- S7: bucket failures by class + first-N offending keys (merchant/day/arrival_ix)
- S8: discovered seed set + per-seed PASS/FAIL summary; index completeness issues

Baseline (per state):
- deterministic rowcounts + distinct PK counts
- deterministic checksums over key columns (sampled deterministically)

---

## 7) Review flags (assumed resolved)
- Standardize `manifest_fingerprint` token usage everywhere (docs/schemas/examples) to match dictionaries.
- Fix any textual “Layer-2” mentions for 2A; 2A is the pinned upstream within Layer-1 flow here.
