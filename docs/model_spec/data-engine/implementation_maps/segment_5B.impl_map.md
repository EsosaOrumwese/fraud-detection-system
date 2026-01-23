# Segment 5B — Compiled Implementation Map (v0.1.0)

This is the reviewer-facing view derived from `segment_5B.impl_map.yaml`.
Use it to answer:
- What is frozen vs flexible?
- Where are the gates and what they authorize?
- Where are the performance hotspots and safe levers?
- If something is wrong, which state owns it?

Assumptions applied (as you requested):
- The earlier review flags are treated as resolved (registry paths align with dictionary; `manifest_fingerprint` token naming is consistent; S3 has an explicit RNG event surface).

---

## 1) One-screen relationship diagram
```
Upstream prerequisites (must PASS for this manifest_fingerprint)
  Layer-1: 1A, 1B, 2A, 2B, 3A, 3B
  Layer-2: 5A
  (S0 verifies each upstream segment’s gate using that segment’s own hashing law)

5B pipeline
  └─ S0 (gate-in foundation / closed-world, RNG-free, metadata-only):
       - verifies upstream PASS gates (fail-closed)
       - seals the 5B input universe into sealed_inputs_5B (digest-linked)
       - binds scenario_set_5B (subset of scenario_manifest_5A)
       - writes s0_gate_receipt_5B + sealed_inputs_5B

  ├─ S1 (RNG-free plan): time grid + grouping plan
  │    → s1_time_grid_5B (manifest_fingerprint + scenario_id)
  │    → s1_grouping_5B (manifest_fingerprint + scenario_id)
  │
  ├─ S2 (RNG, LGCP): latent field + realised intensity
  │    λ_target (from 5A) × ξ(group,bucket)  →  s2_realised_intensity_5B
  │    → optional s2_latent_field_5B
  │    → rng_event_arrival_lgcp_gaussian + rng_audit_log + rng_trace_log (seed+parameter_hash+run_id)
  │
  ├─ S3 (RNG, counts): bucket-level integer counts
  │    → s3_bucket_counts_5B
  │    → rng_event_arrival_bucket_count + rng_audit_log + rng_trace_log
  │
  ├─ S4 (RNG, micro-time + routing): expand counts into arrivals and route
  │    → arrival_events_5B (final-in-layer)
  │    → rng_event_arrival_time_jitter + rng_event_arrival_site_pick + rng_event_arrival_edge_pick
  │    → rng_audit_log + rng_trace_log (+ optional summaries/anomalies)
  │
  └─ S5 (finalizer / consumer gate, RNG-free):
       - validates S0 invariants and S1–S4 coherence + RNG accounting
       - writes validation_bundle_5B + index.json + _passed.flag
       - emits 5B.final.bundle_gate (the only PASS authority for 5B)

Consumer rule (binding): downstream MUST verify the 5B final bundle gate for the same
manifest_fingerprint before treating arrival_events_5B as authoritative (no PASS → no read).
```

---

## 2) Gates and what they authorize

### Upstream gates (verified in S0)
S0 verifies upstream PASS gates for:
- Layer-1: 1A, 1B, 2A, 2B, 3A, 3B
- Layer-2: 5A

S0 uses each upstream segment’s declared hashing law (note 3A differs: digest-of-digests).

### Gate-in receipt (5B.S0.gate_in_receipt)
- Evidence: `s0_gate_receipt_5B` + `sealed_inputs_5B`
- Meaning: “S0 verified upstream gates and sealed the closed input universe”
- Rule: S1–S5 must fail-closed if missing.

### Final consumer gate (5B.final.bundle_gate)
- Location: `data/layer2/5B/validation/manifest_fingerprint={manifest_fingerprint}/`
- Evidence: `index.json` + `_passed.flag`
- Hash law (indexed_bundle raw-bytes):
  - `bundle_sha256 = SHA256(concat(raw_bytes(files listed in index.json excluding _passed.flag) in ASCII-lex path order))`
  - `_passed.flag` is JSON containing `{manifest_fingerprint, bundle_digest_sha256}`
- Authorizes downstream reads of at least:
  - `arrival_events_5B`, `s3_bucket_counts_5B`, `s2_realised_intensity_5B` (and the supporting evidence surfaced by the bundle)

---

## 3) Order authorities (do not invent order)

- **Bucket order authority**: `s1_time_grid_5B.bucket_index` is the sole authority for bucket alignment across S2/S3/S4 joins and checks.
- **Arrival writer order** (determinism/diffability): `arrival_events_5B` ordered by `(scenario_id, merchant_id, ts_utc, arrival_seq)`.
  - `arrival_seq` is the unique per-merchant sequence within each `(seed, manifest_fingerprint, scenario_id)` partition.

---

## 4) Frozen surfaces (do not change)

Segment-wide:
- S0 is RNG-free and metadata-only: it must not do bulk row-scans; it verifies gates and seals inputs.
- Closed input universe: S1–S5 MUST NOT read artefacts not listed in `sealed_inputs_5B`.
- Partition families are binding:
  - control-plane: fingerprint-only (S0 artifacts, validation bundle)
  - plan tables: (manifest_fingerprint, scenario_id) (S1)
  - seeded model surfaces: (seed, manifest_fingerprint, scenario_id) (S2–S4)
  - RNG logs/events: (seed, parameter_hash, run_id)
- Count conservation is binding:
  - for each entity×bucket, S4 must emit exactly N arrivals where N equals `s3_bucket_counts_5B.count_N`.
- Time-window legality is binding:
  - arrivals must satisfy half-open bucket intervals `[bucket_start_utc, bucket_end_utc)` from S1 grid.
- Routing correctness is binding:
  - physical routing must respect upstream routing universe (2B) and zones (3A),
  - virtual routing must respect 3B bindings and edge alias artefacts,
  - civil-time semantics must follow 2A artefacts.

State-specific:
- S1 is RNG-free; it is the single authority for bucket grid + grouping plan.
- S2/S3/S4 are RNG-consuming; for every consuming draw, the corresponding `rng_event_*` row(s) must be emitted and the audit/trace discipline satisfied.
- S5 is RNG-free; it must not publish `_passed.flag` unless validations pass; publish is atomic and write-once.

---

## 5) Flexible surfaces (optimize freely; must preserve invariants)

- Vectorization/batching in S2–S4 is allowed if:
  - deterministic equivalence holds,
  - arrival_seq uniqueness and writer ordering constraints are preserved,
  - RNG accounting and event emission obligations remain correct.
- Log sharding/buffering is allowed if it doesn’t violate the log contract expectations used by S5 (audit/trace reconciliation).
- Optional surfaces may be emitted depending on config:
  - S2 latent field, S4 summaries/anomalies, S5 issue table.

---

## 6) Hotspots + safe optimization levers

### S0 (upstream gate verification)
Hotspot: hashing/verifying many upstream bundles.
Safe levers: streaming hashing; deterministic path ordering; avoid loading large evidence files into memory.

### S1 (grid/group plan)
Hotspot: building per-scenario grids and grouping plans over large merchant×zone domains.
Safe levers: deterministic chunking by scenario_id and merchant_id; avoid global sorts beyond declared ordering keys.

### S2 (LGCP latent field)
Hotspot: large group×bucket Gaussian sampling + log IO.
Safe levers: deterministic chunking by group_id; vectorized sampling; buffered log writes.

### S3 (bucket counts)
Hotspot: high-volume sampling across entity×bucket grid + log IO.
Safe levers: batch per group_id; deterministic chunking; buffered event writes.

### S4 (arrival expansion + routing)
Hotspot: extremely high volume expansion and routing, plus multiple RNG event streams.
Safe levers: streaming expansion, vectorized time-offset draws, deterministic per-merchant chunking, careful buffered logging.

### S5 (validation + bundling)
Hotspot: scanning large arrival_events and reconciling RNG logs/events.
Safe levers: streaming validators; set-semantics reads for logs where allowed; stream hashing and deterministic index construction.

---

## 7) Debug hooks (to localize failures)

Critical hooks:
- S0 receipt must record:
  - verified digest + bundle root for each upstream segment (1A–3B, 5A)
  - scenario_set_5B binding
  - sealed_inputs_digest and sealed list summary counts by role
- S2/S3/S4:
  - expected rows vs written rows per scenario partition
  - RNG coverage: events_emitted per family; trace reconciliation counters
- S4:
  - conservation mismatch counters (should be zero)
  - virtual vs physical arrival counts per scenario
- S5:
  - bucketed failure classes with first-N offending keys (merchant_id, bucket_index, arrival_seq)
  - index completeness diagnostics for bundling

Baseline (per state):
- deterministic rowcounts + distinct PK counts
- deterministic checksums over key columns (sampled deterministically)

---

## 8) Review flags

Assumed resolved (per your instruction):
- Registry paths align with the dataset dictionary (no seed/path drift).
- Token naming is standardized to `manifest_fingerprint`.
- S3 has an explicit RNG event surface (`rng_event_arrival_bucket_count`) or the spec is updated to say audit/trace-only.

Additional hygiene flags I surfaced while compiling:
- dataset_dictionary.layer2.5B.yaml appears to include trailing newlines in some `path:` values (risk: byte-level mismatches).
- artefact_registry_5B.yaml and schemas.5B.yaml looked like they had YAML syntax/indentation issues in my parser.
  If you’ve already fixed these in your repo, you can ignore these; otherwise they’re worth correcting before implementation.
