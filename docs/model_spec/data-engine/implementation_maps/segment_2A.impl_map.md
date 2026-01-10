# Segment 2A - Compiled Implementation Map (v0.1.0)

This is the reviewer-facing view derived from `segment_2A.impl_map.yaml`.
Use it to answer:
- What is frozen vs flexible?
- Where are the gates and what do they authorize?
- What are the obvious performance hotspots and safe levers?
- If something is wrong, which state owns it?

> Assumption you stated: you'll fix the `fingerprint` vs `manifest_fingerprint` drift as done for 1B.
> This view standardizes on `manifest_fingerprint` in paths/partitions/examples.

---

## 1) One-screen relationship diagram
```
Upstream (1B, hard dependency)
  -> site_locations (seed + manifest_fingerprint)
  -> 1B final gate:
     data/layer1/1B/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
     (indexed_bundle: index.json drives hash)

2A pipeline (RNG-free)
  -> S0 (gate-in foundation):
     - verifies 1B final bundle gate (FAIL_CLOSED if mismatch)
     - seals inputs (tz_world, tzdb_release, tz_overrides, tz_nudge, ...)
     - writes s0_gate_receipt_2A + sealed_inputs_2A

  -> S1 (provisional tz lookup):
     site_locations + tz_world + tz_nudge -> s1_tz_lookup
     - deterministic point-in-polygon
     - single epsilon-nudge on ambiguous/border cases; abort if still unresolved

  -> S2 (final tz assignment):
     s1_tz_lookup + tz_overrides (+ merchant_mcc_map if used) -> site_timezones
     - override precedence: site > mcc > country
     - override uniqueness: >1 active per (scope,target) => ABORT
     - created_utc = S0.verified_at_utc (binding)

  -> S3 (tz transition cache):
     tzdb_release + tz_world tzid-domain -> tz_timetable_cache (manifest_fingerprint-scoped)
     - created_utc = S0.verified_at_utc (binding)
     - coverage: cache index includes all tzids in tz_world (superset allowed)

  -> S4 (DST legality report):
     site_timezones + tz_timetable_cache -> s4_legality_report (per seed)
     - generated_utc = S0.verified_at_utc (binding)
     - FAIL blocks bundle gate

  -> S5 (finalizer / consumer gate):
     - discovers seeds from site_timezones partitions
     - requires each s4_legality_report status=PASS
     - writes validation_bundle_2A + index.json + _passed.flag (indexed_bundle law)

Consumer rule (binding): downstream MUST verify the 2A final bundle gate for the same
manifest_fingerprint before reading `site_timezones` (no PASS -> no read).
```

---

## 2) Gates and what they authorize

### Upstream gate (1B.final.bundle_gate)
- Location: `data/layer1/1B/validation/manifest_fingerprint={manifest_fingerprint}/`
- Evidence: `index.json` + `_passed.flag`
- Hash law: hash indexed files (exclude `_passed.flag`) in ASCII-lex order of `index.json.path`
- Verified **only in S0**, fail-closed on mismatch.

### Gate-in receipt (2A.S0.gate_in_receipt)
- Evidence: `s0_gate_receipt_2A` (manifest_fingerprint-scoped JSON)
- Meaning: "S0 verified 1B PASS and sealed the declared 2A inputs"
- Rule: **Any state that reads sealed inputs MUST require this receipt** (fail-closed if missing).

### Final consumer gate (2A.final.bundle_gate)
- Location: `data/layer1/2A/validation/manifest_fingerprint={manifest_fingerprint}/`
- Evidence: `index.json` + `_passed.flag`
- Same index-driven hashing law; published atomically.
- Authorizes reads of: `site_timezones`.

---

## 3) Frozen surfaces (do not change)

Segment-wide:
- **No PASS -> No Read**: S0 MUST verify 1B final gate before admitting any 1B egress reads.
- `s0_gate_receipt_2A` is the durable attestation enabling downstream reads; all states must fail-closed if missing.
- Path<->embed equality: embedded `manifest_fingerprint` must equal path token where embedded.
- All states are RNG-free.

S1 lookup laws:
- Deterministic point-in-polygon.
- If membership cardinality != 1: apply exactly **one** epsilon-nudge `(lat+epsilon, lon+epsilon)` with deterministic clamp/wrap; abort if still ambiguous/empty.
- `nudge_lat_deg` and `nudge_lon_deg` are both null or both non-null.

S2 override laws:
- Active override depends ONLY on date(S0.verified_at_utc), not wall-clock.
- Scope precedence: **site > mcc > country**; apply at most one.
- Uniqueness: >1 active per (scope,target) => ABORT.
- `created_utc = S0.verified_at_utc` (binding).
- Carry `nudge_*` through unchanged from S1.

S3 cache laws:
- Compile deterministic transition cache from sealed tzdb release.
- Coverage: index includes all tzids present in sealed tz_world domain (superset allowed).
- `created_utc = S0.verified_at_utc` (binding).
- Atomic publish + write-once per manifest_fingerprint.

S4 legality laws:
- `generated_utc = S0.verified_at_utc` (binding).
- tzids used by site_timezones must exist in cache; fail/abort if missing.

S5 bundle/gate laws:
- Seed discovery from site_timezones partitions.
- Every discovered seed must have s4 report with `status=PASS`; otherwise no `_passed.flag`.
- Index law + `_passed.flag` hashing law (indexed_bundle) + atomic publish.

---

## 4) Flexible surfaces (optimize freely; must preserve invariants)
- Spatial acceleration structures for polygon lookup (deterministic).
- Override indexing (pre-index by scope/target) and MCC join strategy (deterministic).
- Cache sharding layout inside tz_timetable_cache (as long as manifest + digest laws hold).
- Streaming vs batch computations for legality windows and bundle construction.

---

## 5) Hotspots + safe optimization levers

### S1 (tz lookup)
Hotspot: point-in-polygon at scale.
Safe levers: deterministic spatial indexing; cache polygon subsets; vectorize membership where deterministic.

### S2 (override application)
Hotspot: per-site override lookup; MCC-scope if used.
Safe levers: pre-index overrides; cache MCC mapping; avoid any wall-clock dependence.

### S3 (tzdb compilation)
Hotspot: tzdb parsing + canonicalization.
Safe levers: streaming parse; deterministic canonicalization; avoid nondeterministic maps/sets.

### S4 (legality windows)
Hotspot: fold/gap derivation across many tzids.
Safe levers: compute once per tzid; reuse across sites; stream windows.

### S5 (bundling + hashing)
Hotspot: hashing many evidence files.
Safe levers: stream hashing; generate index deterministically; avoid loading large evidence into memory.

---

## 6) Debug hooks (to localize failures)

Critical hooks:
- S0 receipt must record:
  - resolved 1B bundle root path
  - verified `_passed.flag` sha256 hex
  - sealed input IDs + digests + sizes
  - `verified_at_utc`
- S1: counts of nudged vs non-nudged sites; first-N ambiguous/empty membership cases.
- S2: counts of overrides applied by scope; duplicates detected; unknown tzid counts.
- S3: tzids_in_world vs tzids_in_index; first-N missing tzids on failure.
- S4: sites_total/tzids_total + fold/gap totals + missing_tzids list.
- S5: discovered seed set + per-seed PASS/FAIL; index completeness issues.

Baseline (per state):
- deterministic rowcounts + distinct PK counts
- deterministic key checksums (sampled deterministically)

---

## 7) Remaining review action (you said you'll do this)
- Standardize token naming: use `manifest_fingerprint` everywhere (schemas/state docs/examples) to match the dictionary.
