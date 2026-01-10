# Segment 1A — Compiled Implementation Map (v0.1.0)

This is the reviewer-facing view derived from `segment_1A.impl_map.yaml`.
Use it to answer:
- What is frozen vs flexible?
- Where are the gates and what do they authorize?
- Where are the performance hotspots and what levers are safe?
- If something is wrong, which state owns it?

---

## 1) One-screen relationship diagram
```
Ingress + Reference + Policies (sealed / hashed)
  └─ S0 (foundation): parameter_hash + manifest_fingerprint + deterministic precomputes
       ├─ (parameter_hash scope) crossborder_features (planning/opt), crossborder_eligibility_flags,
       │                     hurdle_design_matrix, hurdle_pi_probs (opt), merchant_abort_log
       └─ (manifest_fingerprint scope) sealed_inputs_1A, s0_gate_receipt_1A

S1 (RNG): hurdle bernoulli (is_multi gate)
  └─ rng_event_hurdle_bernoulli (+ rng_trace_log)

S2 (RNG): NB decomposition + draws (only if is_multi==true)
  └─ rng_event_gamma_component + rng_event_poisson_component + rng_event_nb_final (+ trace)

S3 (authority builder): candidate set + ranks (parameter-scoped)
  ├─ s3_candidate_set  [INTER-COUNTRY ORDER AUTHORITY: candidate_rank]
  └─ s3_site_sequence  [WITHIN-COUNTRY ORDER: site_order] (+ optional priors/counts)

S4 (RNG): ZTP rejection loop → K foreign target
  └─ rng_event_ztp_final (+ rejection/exhaust events + trace)

S5 (deterministic cache): currency→country weights (parameter-scoped)
  ├─ ccy_country_weights_cache + merchant_currency + sparse_flag
  └─ emits receipt gate: 1A.S5.receipt (parameter_hash scope)

S6 (RNG): gumbel keys (seed+parameter scope; uses S5 cache)
  ├─ rng_event_gumbel_key (+ trace)
  ├─ optional s6_membership convenience dataset
  └─ emits receipt gate: 1A.S6.receipt (seed,parameter_hash scope)

S7 (RNG): allocation residual ranking / optional dirichlet lane
  └─ rng_event_residual_rank (+ optional dirichlet_gamma_vector + trace)

S8 (egress builder): outlet_catalogue (seed+manifest_fingerprint)
  └─ outlet_catalogue (+ optional finalize/overflow events + trace)

S9 (finalizer): validation bundle + index + consumer gate publish (manifest_fingerprint scope)
  ├─ validation_bundle_1A + index.json
  └─ _passed.flag  ==> gate: 1A.final.bundle_gate (authorizes outlet_catalogue reads)

Consumer rule (binding): downstream MUST verify 1A.final.bundle_gate for the same
manifest_fingerprint before reading outlet_catalogue (no PASS → no read).
```
---

## 2) Gates and what they authorize (review checklist)

### 1A.S5.receipt (parameter_hash scope)
- Location: `.../ccy_country_weights_cache/parameter_hash={parameter_hash}/`
- Evidence: `S5_VALIDATION.json` + `_passed.flag`
- Authorizes reads of: `ccy_country_weights_cache`, `merchant_currency`, `sparse_flag`

### 1A.S6.receipt (seed,parameter_hash scope)
- Location: `.../s6/seed={seed}/parameter_hash={parameter_hash}/`
- Evidence: `S6_VALIDATION.json` + `_passed.flag`
- Authorizes reads of: `s6_membership` (and the receipt folder itself)

### 1A.final.bundle_gate (manifest_fingerprint scope)
- Location: `.../validation/manifest_fingerprint={manifest_fingerprint}/`
- Evidence: `index.json` + `_passed.flag` (hash over indexed files)
- Authorizes reads of: `outlet_catalogue`

---

## 3) Order authorities (do not invent order)

### Inter-country order
- **S3 `s3_candidate_set.candidate_rank` is the single authority.**
- `outlet_catalogue` MUST NOT be used to infer cross-country order.

### Within-country order
- `site_order` defines within-country ordering (via `s3_site_sequence` / S8 egress ordering).

---

## 4) Frozen surfaces (do not change)

Segment-wide:
- **parameter_hash** formation: governed basenames + name-sensitive tuple-hash + ASCII sort.
- **manifest_fingerprint**: opened-artefact closure MUST include registry dependency closure.
- **run_id** is log-only (MUST NOT affect modelling outputs or RNG outcomes).
- **Partition law:** embedded lineage fields (when present) must equal path keys.
- **Receipt hashing** for S5/S6: unindexed receipt; exclude `_passed.flag`; ASCII-lex relative path order.
- **Final gate hashing:** `_passed.flag` computed over files listed in `index.json` (exclude `_passed.flag`),
  using ASCII-lex order of `index.json.path`.
- **Atomic publish:** stage → write evidence → compute hash → write flag → single finalize/rename.

State-specific hard locks:
- S1 is the single authority for `is_multi`.
- S3 defines `candidate_rank(home)=0` and contiguous rank semantics.
- S6 iteration order MUST follow the S3 authority ordering (not file order / hash order).
- S8 egress ordering is binding: `(merchant_id, legal_country_iso, site_order)`.
- S9 must not publish `_passed.flag` on FAIL (no partial visibility).

---

## 5) Flexible surfaces (Codex may choose; must preserve invariants)

- Parquet physical layout (file counts, row-group sizing, compression) where equality=rowset and no ordering contract.
- Vectorization vs per-row loops if deterministic outputs and numeric policy discipline are preserved.
- Data structures (hash tables vs sorted merges), caching boundaries, streaming vs batch validators.
- Parallelism **only** when worker-count invariance is proven (no dependence on scheduling).

---

## 6) Hotspots + safe optimization levers (per state)

### S0 (foundation joins + feature prep)
Hotspots:
- Join-heavy prep over merchant_ids × reference tables; eligibility evaluation at scale.
Safe levers:
- Cache small reference tables; precompile policy predicates; avoid global sorts unless required.

### S1/S2 (RNG-heavy; probability + gamma/poisson draws)
Hotspots:
- Sampling at scale; numeric stability constraints.
Safe levers:
- Deterministic chunking by merchant_id; vectorized math with deterministic reductions.

### S3 (candidate rank construction)
Hotspots:
- Sort-heavy rank creation; joins for candidate generation.
Safe levers:
- Sort per-merchant partitions with stable tie-breaks; avoid global ordering beyond declared keys.

### S4 (rejection sampling)
Hotspots:
- ZTP rejection loops for edge distributions.
Safe levers:
- Tight bounded loops; compiled deterministic loops (while preserving event sequence semantics).

### S5 (cache build + receipt)
Hotspots:
- Currency→country normalization/smoothing.
Safe levers:
- Group by currency; deterministic key ordering; streaming compute; keep receipt publish atomic.

### S6 (top-k + RNG emission)
Hotspots:
- Large candidate lists; deterministic top-k and tie-breaks.
Safe levers:
- Heap/partial-select per merchant; deterministic partitioning; avoid global sorts.

### S7 (allocation)
Hotspots:
- Allocation across many countries per merchant.
Safe levers:
- Cache weight vectors; per-merchant work units; deterministic tie-breaks.

### S8 (egress write preserving order)
Hotspots:
- Writing large ordered egress.
Safe levers:
- Deterministic per-merchant chunks; merge in declared key order; avoid nondeterministic sharding.

### S9 (validation + gate publish)
Hotspots:
- Large parquet scans (PK/UK checks), RNG reconciliation across many logs.
Safe levers:
- Streaming validators; bounded-memory key-checkers; set-semantics reads for RNG logs.

---

## 7) Debug hooks (what makes failures localizable)

Per-state (minimum useful hooks):
- Emit deterministic counts: rowcount + distinct merchant_id (or relevant PK) for each produced dataset.
- Emit deterministic checksum over key columns (sampled deterministically) to localize drift.

Critical hooks:
- S0: `sealed_inputs_1A` must enumerate opened artefacts (the sealing inventory).
- S5: `S5_VALIDATION.json` includes per-currency Σ stats + override counts.
- S6: `S6_VALIDATION.json` includes per-merchant expected vs emitted events + shortfall reasons.
- S9: bucket failure codes by validation class + first-N offending keys per class.

---

## 8) Review flags (things to resolve explicitly)

None currently open for 1A (map aligned to current contracts/specs as-of this revision).
