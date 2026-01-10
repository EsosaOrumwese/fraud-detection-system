# Segment 3B — Compiled Implementation Map (v0.1.0)

This is the reviewer-facing view derived from `segment_3B.impl_map.yaml`.
Use it to answer:
- What is frozen vs flexible?
- Where are the gates and what they authorize?
- Where are the performance hotspots and safe levers?
- If something is wrong, which state owns it?

Assumptions applied (as you requested):
- Token naming is standardized to `manifest_fingerprint` everywhere (paths/partitions/examples).
- Parameter-hash governance is assumed updated in rails so 3B’s governed parameter artefacts cannot drift without a `parameter_hash` change.

---

## 1) One-screen relationship diagram
```
Upstream gates (all MUST be verified in S0)
  1A: data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
  1B: data/layer1/1B/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
  2A: data/layer1/2A/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
  3A: data/layer1/3A/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
  (fail-closed; verify per segment’s canonical gate law)

Pinned upstream surfaces (sealed by S0)
  - 1A outlet_catalogue
  - 1B site_locations
  - 2A site_timezones + tz_timetable_cache (optional, if used by mode)
  - 3A zone_alloc + zone_alloc_universe_hash (context for routing/validation)

Pinned 3B externals / policy packs (sealed by S0)
  - Merchant universe + classification inputs:
      transaction_schema_merchant_ids, mcc_channel_rules
  - Settlement inputs:
      virtual_settlement_coords + (pelias_cached_sqlite / pelias_cached_bundle)
  - CDN policy/weights:
      cdn_country_weights, cdn_weights_ext_yaml, cdn_key_digest
  - Validation/logging policy:
      virtual_validation_policy, virtual_logging_policy
  - RNG + layout:
      route_rng_policy_v1, alias_layout_policy_v1, day_effect_policy_v1
  - Spatial assets:
      hrsl_raster (+ world geometry assets as sealed by the docs)

3B pipeline
  └─ S0 (gate-in foundation):
       - verifies upstream PASS gates (1A/1B/2A/3A)
       - seals closed input universe for 3B
       - writes s0_gate_receipt_3B + sealed_inputs_3B

  ├─ S1 (RNG-free): virtual classification + settlement node build
  │    → virtual_classification_3B + virtual_settlement_3B
  │
  ├─ S2 (RNG): CDN edge catalogue construction (placement/jitter)
  │    → edge_catalogue_3B + edge_catalogue_index_3B
  │    → rng_event_edge_tile_assign + rng_event_edge_jitter + rng_audit_log + rng_trace_log
  │
  ├─ S3 (RNG-free): edge alias tables + edge universe hash
  │    → edge_alias_blob_3B + edge_alias_index_3B + edge_universe_hash_3B
  │    → optional gamma_draw_log_3B (guardrail; expected empty)
  │
  ├─ S4 (RNG-free): routing semantics + validation contract compilation
  │    → virtual_routing_policy_3B + virtual_validation_contract_3B
  │
  └─ S5 (RNG-free finalizer):
       - audits S0–S4 outputs + reconciles S2 RNG evidence
       - writes validation_bundle_3B + index.json + _passed.flag
       - emits final consumer gate (3B.final.bundle_gate)

Consumer rule (binding): downstream MUST verify 3B final bundle gate for the same
manifest_fingerprint before reading 3B consumer surfaces (notably edge alias artefacts and routing policy).
```

---

## 2) Gates and what they authorize

### Upstream gates (verified in S0)
- 1A.final.bundle_gate → authorizes `outlet_catalogue`
- 1B.final.bundle_gate → authorizes `site_locations`
- 2A.final.bundle_gate → authorizes `site_timezones` / `tz_timetable_cache` if used
- 3A.final.bundle_gate → authorizes `zone_alloc` / `zone_alloc_universe_hash`

S0 FAIL_CLOSED if any mismatch.

### Gate-in receipt (3B.S0.gate_in_receipt)
- Evidence: `s0_gate_receipt_3B` + `sealed_inputs_3B`
- Meaning: “S0 verified upstream gates and sealed the closed input universe”
- Rule: S1–S5 must fail-closed if missing; no other inputs are allowed.

### Final consumer gate (3B.final.bundle_gate)
- Location: `data/layer1/3B/validation/manifest_fingerprint={manifest_fingerprint}/`
- Evidence: `index.json` + `_passed.flag`
- Hash law: indexed_bundle (raw bytes):
  - `_passed.flag` is `sha256_hex = <hex64>`
  - `<hex64> = SHA256(concat(raw_bytes(files listed in index.json excluding _passed.flag) in ASCII-lex path order))`
- Authorizes downstream reads of:
  - edge alias artefacts, edge universe hash
  - virtual routing policy + validation contract
  - and the 3B run-scoped products consumers rely on.

---

## 3) Frozen surfaces (do not change)

Segment-wide:
- No PASS → no read: S0 must verify upstream gates (1A/1B/2A/3A) before sealing or reading any upstream outputs.
- Closed input universe: downstream MUST NOT read anything not listed in sealed_inputs_3B.
- Token naming: standardize on `manifest_fingerprint` consistently.
- run_id is logs-only; must not influence modelling outputs.

S1 (virtual set authority):
- RNG-free classification; S1 is the sole authority for virtual vs non-virtual.
- No settlement rows for non-virtual merchants.
- Settlement identifiers are deterministic and stable across reruns.

S2 (edge catalogue RNG):
- Budgets and integer allocations are RNG-free; RNG is allowed only for stochastic placement/jitter.
- Must not exceed route_rng_policy_v1 budgets or attempt caps.
- Audit/trace reconciliation is binding (trace-after-each-event discipline).

S3 (alias + universe hash):
- RNG-free; must not advance Philox.
- Alias encoding/decoding law fixed by alias_layout_policy_v1.
- edge_universe_hash computed by canonical component ordering + digest combination; fingerprint-scoped (seed-invariant).
- Optional gamma_draw_log_3B is a guardrail: any record indicates forbidden RNG usage in S3 (fatal).

S4 (contracts):
- RNG-free; must only codify routing/validation bindings from S1–S3 + sealed policies.
- Must bind RNG stream labels/IDs in a way consistent with route_rng_policy_v1 for downstream (2B) virtual routing.

S5 (final gate):
- RNG-free; must not publish _passed.flag if any audit fails.
- Gate hashing law + atomic publish are binding; write-once for manifest_fingerprint.

---

## 4) Flexible surfaces (optimize freely; must preserve invariants)

- S0: streaming gate verification and sealed input enumeration (deterministic ordering only).
- S1: classification rule data structures and geocode lookup strategy (sqlite vs bundle), as long as deterministic.
- S2: spatial acceleration, raster sampling strategy, and batching, as long as deterministic and within RNG budgets.
- S3: alias construction algorithm (Vose or equivalent) as long as encoded bytes + decode semantics are identical and deterministic.
- S5: audits and hashing can be streaming/bounded-memory as long as deterministic and schema-consistent.

---

## 5) Hotspots + safe optimization levers

### S0 (gate verification)
Hotspot: hashing multiple upstream bundles.
Safe levers: stream hashing; deterministic path ordering; avoid filesystem-order dependence.

### S1 (merchant-scale classification + geocode)
Hotspot: large merchant universe; potential geocode IO.
Safe levers: pre-index rules; batch lookups; deterministic chunking by merchant_id.

### S2 (edge placement/jitter + logs)
Hotspot: spatial sampling + rejection/jitter loops + log IO.
Safe levers: deterministic spatial indexing; cached geometry; buffered log writes; keep attempt caps strict.

### S3 (alias + digests)
Hotspot: alias build for large edge universes + digest over big blobs.
Safe levers: sequential blob writer; stream digests; batch per merchant.

### S5 (audits + bundling)
Hotspot: scanning evidence + RNG reconciliation + hashing bundle members.
Safe levers: streaming validators; set-semantics reads for logs; stream hashing and deterministic index building.

---

## 6) Debug hooks (to localize failures)

Critical hooks:
- S0 receipt records:
  - verified upstream digests + resolved bundle roots per upstream segment
  - full sealed input list with sha256/size/schema_ref
- S1: counts of virtual vs non-virtual and top reason codes distribution
- S2: counts (edges_total, jitter_attempts_total) and per-reason rejection histograms; trace reconciliation counters
- S3: index offsets + blob sha256; component digests used in edge_universe_hash
- S4: include component versions/digests (cdn_key_digest, alias layout version) in routing policy for drift diagnosis
- S5: per-audit PASS/FAIL summary and first-N offending keys/paths; index completeness diagnostics

Baseline (per state):
- deterministic rowcounts + distinct key counts
- deterministic checksums over key columns (sampled deterministically)

---

## 7) Review flags (assumed resolved)
- Standardize `manifest_fingerprint` token usage everywhere.
- Ensure parameter_hash governance includes the 3B parameter artefacts that must move parameter_hash.
