# Segment 6A — Compiled Implementation Map (v0.1.0)

This is the reviewer-facing view derived from `segment_6A.impl_map.yaml`.
Use it to answer:
- What is frozen vs flexible?
- Where are the gates and what they authorize?
- Where are the performance hotspots and safe levers?
- If something is wrong, which state owns it?

Assumptions applied (as you requested):
- Token naming is standardized to `manifest_fingerprint` everywhere (paths/partitions/examples).
- State-doc examples are aligned to dictionary authority: core 6A entity datasets partition by
  `[seed, manifest_fingerprint, parameter_hash]`.

---

## 1) One-screen relationship diagram
```
Upstream prerequisites (must PASS for this manifest_fingerprint)
  Layer-1: 1A, 1B, 2A, 2B, 3A, 3B
  Layer-2: 5A, 5B
  (S0 verifies each upstream segment’s PASS gate using that segment’s own hashing law)

6A pipeline
  └─ S0 (gate-in foundation / closed-world, RNG-free):
       - verifies upstream PASS gates (FAIL_CLOSED on any missing/mismatch)
       - seals the 6A input universe into sealed_inputs_6A (digest-linked)
       - writes s0_gate_receipt_6A + sealed_inputs_6A

  ├─ S1 (RNG): party universe
  │    → s1_party_base_6A (+ optional s1_party_summary_6A)
  │    → rng_event_party_count_realisation + rng_event_party_attribute_sampling
  │    → rng_audit_log + rng_trace_log
  │
  ├─ S2 (RNG): accounts & product holdings
  │    → s2_account_base_6A + s2_party_product_holdings_6A (+ optional merchant view/summary)
  │    → rng_event_account_* families + audit/trace
  │
  ├─ S3 (RNG): instruments & links
  │    → s3_instrument_base_6A + s3_account_instrument_links_6A (+ optional holdings/summary)
  │    → rng_event_instrument_* families + audit/trace
  │
  ├─ S4 (RNG): devices, IPs, and static link graph
  │    → s4_device_base_6A + s4_ip_base_6A + s4_device_links_6A + s4_ip_links_6A (+ optional neighbourhoods/summary)
  │    → rng_event_device_* + rng_event_ip_* families + audit/trace
  │
  └─ S5 (RNG + finalizer):
       - assigns static fraud roles to parties/accounts/merchants/devices/IPs (RNG)
       - validates the segment and reconciles RNG accounting
       - publishes validation_bundle_index_6A + _passed.flag (6A.final.bundle_gate)

Consumer rule (binding): downstream MUST verify the 6A final bundle gate for the same
manifest_fingerprint before reading ANY 6A outputs (no PASS → no read).
```

---

## 2) Gates and what they authorize

### Upstream gates (verified in S0)
S0 verifies PASS gates for:
- Layer-1: 1A, 1B, 2A, 2B, 3A, 3B
- Layer-2: 5A, 5B

S0 uses each upstream segment’s declared hashing law (note 3A differs: digest-of-digests).

### Gate-in receipt (6A.S0.gate_in_receipt)
- Evidence: `s0_gate_receipt_6A` + `sealed_inputs_6A`
- Meaning: “S0 verified upstream gates and sealed the closed input universe”
- Rule: S1–S5 must fail-closed if missing; no other inputs are allowed.

### Final consumer gate (6A.final.bundle_gate)
- Location: `data/layer3/6A/validation/manifest_fingerprint={manifest_fingerprint}/`
- Evidence: `validation_bundle_index_6A.json` + `_passed.flag`
- Hash law (indexed_bundle raw-bytes concat; flag excluded; atomic publish with flag last)
- Authorizes downstream reads of:
  - party/account/instrument/device/ip bases + link tables
  - fraud role tables
  - (and whatever evidence the index/bundle declares)

---

## 3) Order authorities (do not invent order)

- s1_party_base_6A writer order keys are binding for determinism/diffability; joins use `party_id`, not file order.
- s2_account_base_6A writer order keys are binding; joins use `account_id`, not file order.
- Similar “writer order is for determinism only” applies to instrument and graph tables.

---

## 4) Frozen surfaces (do not change)

Segment-wide:
- S0 is RNG-free and must enforce:
  - No upstream PASS → no 6A (fail-closed on missing/mismatch)
  - Closed input universe: S1–S5 must not read anything not listed in sealed_inputs_6A
  - METADATA_ONLY sealing: any sealed input marked metadata-only must not be row-read unless explicitly upgraded
- Partition families are binding:
  - Control-plane: `[manifest_fingerprint]` (S0 artifacts, validation bundle)
  - Entity world tables: `[seed, manifest_fingerprint, parameter_hash]`
  - RNG logs/events: `[seed, parameter_hash, run_id]`
- Scenario-independent posture is binding:
  - 6A entity world and fraud roles must not depend on scenario_id

S1–S4:
- Each state’s RNG event families and audit/trace discipline are binding (trace-after-each-event, reconciliation in S5).
- FK integrity is binding:
  - account_id links must refer to s2_account_base_6A
  - party_id links must refer to s1_party_base_6A
  - merchant_id references must refer to the sealed merchant universe (from Layer-1)

S5:
- Static fraud roles are immutable within the world (per seed+mf) and are the only authority for “static posture”.
- S5 is the sole authority publishing the segment PASS gate.
- Must not publish `_passed.flag` on any validation failure (fail-closed; atomic publish).

---

## 5) Flexible surfaces (optimize freely; must preserve invariants)

- Vectorization/batching in S1–S5 is allowed if deterministic and RNG accounting is preserved.
- Parallelism is allowed only if worker-count invariance is proven (no scheduling-dependent outcomes).
- Validation implementation can be streaming/bounded-memory as long as deterministic and schema-consistent.

---

## 6) Hotspots + safe optimization levers

### S0 (upstream verification)
Hotspot: hashing/verifying multiple upstream bundles.
Safe levers: streaming hashing; deterministic member ordering; avoid materializing evidence.

### S1–S4 (large universe generation)
Hotspot: large-scale sampling + building link tables + log IO.
Safe levers: deterministic chunking by cell/account/merchant; buffered log writes; avoid global sorts beyond declared keys.

### S5 (roles + validation + bundle)
Hotspot: sampling roles at scale + reconciling many RNG event families + hashing bundle members.
Safe levers: streaming validators; set-semantics reads for logs; stream hashing; bounded-memory checksums.

---

## 7) Debug hooks (to localize failures)

Critical hooks:
- S0 receipt records:
  - verified digest + bundle root for each upstream segment
  - sealed_inputs_digest and sealed input list summary counts
- S1–S4:
  - expected vs produced counts (entities and links)
  - per-family events_emitted + trace reconciliation counters
  - first-N FK violations (should be zero)
- S5:
  - role distribution summaries by entity type
  - bucketed validation failures + first-N offending keys
  - computed bundle digest and index completeness diagnostics

Baseline (per state):
- deterministic rowcounts + distinct key counts
- deterministic checksums over key columns (sampled deterministically)

---

## 8) Review flags (assumed resolved)
- Standardize `manifest_fingerprint` token usage everywhere.
- Align all examples to dictionary authority: core 6A tables partition by `[seed, manifest_fingerprint, parameter_hash]`.
