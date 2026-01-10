# Segment 1B — Compiled Implementation Map (v0.1.0)

This is the reviewer-facing view derived from `segment_1B.impl_map.yaml`.
Use it to answer:
- What is frozen vs flexible?
- What gates exist and what they authorize?
- Where are the performance hotspots and safe levers?
- If something is wrong, which state owns it?

> Design decisions applied (as per your resolutions):
> 1) Standardize on `manifest_fingerprint` everywhere.
> 2) Mirror the dictionary path for 1A validation everywhere in 1B: `.../validation/manifest_fingerprint={manifest_fingerprint}/`.
> 3) S0 writes `s0_gate_receipt_1B` as the durable proof that 1A final bundle was verified; any state that reads 1A egress MUST require this receipt before read.

---

## 1) One-screen relationship diagram

1A (upstream, hard dependency)
  ├─ outlet_catalogue  (seed + manifest_fingerprint)  [site stubs + site_order]
  └─ validation gate:  data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/_passed.flag
                       (indexed_bundle: index.json drives hash)

1B pipeline
  └─ S0 (gate-in foundation):
       - verifies 1A final bundle gate (FAIL_CLOSED if mismatch)
       - writes s0_gate_receipt_1B (durable attestation) + sealed_inputs_1B

  ├─ S1 (tile universe): tile_index + tile_bounds (parameter_hash)
  ├─ S2 (tile weights): tile_weights (parameter_hash)
  ├─ S3 (requirements): per (merchant_id, legal_country_iso) requirements from outlet_catalogue
  ├─ S4 (alloc plan): integer n_sites_tile allocation to tiles
  ├─ S5 (RNG): site → tile assignment
  │    - rng_event_site_tile_assign (draws=1 per site)
  ├─ S6 (RNG): in-cell jitter with point-in-country acceptance (bounded resample)
  │    - rng_event_in_cell_jitter (blocks=1, draws="2" per attempt; 1+ events per site)
  ├─ S7 (synthesis): compose final per-site rows + coverage parity vs outlet_catalogue
  ├─ S8 (egress): site_locations (seed + manifest_fingerprint)
  └─ S9 (finalizer): validation bundle + index.json + _passed.flag (consumer gate)

Consumer rule (binding): downstream MUST verify 1B final bundle gate for the same
manifest_fingerprint before reading site_locations (no PASS → no read).

---

## 2) Gates and what they authorize (review checklist)

### Upstream gate (1A.final.bundle_gate) — MUST be verified in S0
- Location (canonical): `data/layer1/1A/validation/manifest_fingerprint={manifest_fingerprint}/`
- Evidence: `index.json` + `_passed.flag`
- Hash law: hash indexed files (exclude `_passed.flag`) in ASCII-lex order of `index.json.path`
- S0 FAIL_CLOSED if missing/mismatch.

### Gate-in receipt (1B.S0.gate_in_receipt) — durable proof of upstream verification
- Evidence: `s0_gate_receipt_1B` (fingerprint-scoped JSON)
- Meaning: “S0 verified 1A.final.bundle_gate for this manifest_fingerprint”
- Rule: **Any 1B state that reads 1A egress MUST require this receipt before read**.

### Final consumer gate (1B.final.bundle_gate)
- Location: `data/layer1/1B/validation/manifest_fingerprint={manifest_fingerprint}/`
- Evidence: `index.json` + `_passed.flag`
- Same index-driven hashing law; published atomically.
- Authorizes reads of: `site_locations`.

---

## 3) Order authorities (do not invent order)
- Inter-country order remains **1A.S3** `s3_candidate_set.candidate_rank`. **1B does not create inter-country order.**
- Within-country order is **site_order** from 1A outlet stubs and must be preserved throughout 1B.
- `site_locations` is semantically order-free, but writer sort keys exist for determinism: `(merchant_id, legal_country_iso, site_order)`.

---

## 4) Frozen surfaces (do not change)

Segment-wide:
- Partition families:
  - parameter-scoped: `[parameter_hash]`
  - egress: `[seed, manifest_fingerprint]`
  - RNG logs/events: `[seed, parameter_hash, run_id]` (run_id is logs-only)
- Path↔embed equality: embedded lineage fields must match path tokens when present.
- S0 upstream verification: index.json-driven bundle hashing; FAIL_CLOSED.
- S0 receipt rule: `s0_gate_receipt_1B` is required before any 1A egress read by downstream states.
- S9 gate: index.json completeness + `_passed.flag` hashing + atomic publish.

State-specific locks:
- S3/S7 coverage parity vs 1A `outlet_catalogue`: **exactly one site per stub key**.
- S5 draw budget: **exactly 1 event per site** (`rng_event_site_tile_assign`).
- S6 per-attempt budget: **blocks=1, draws="2"**, one event per attempt, bounded resample; ABORT if no acceptance within budget.
- S8 input restriction: SHALL read only `s7_site_synthesis`.

---

## 5) Flexible surfaces (Codex/impl may choose; must preserve invariants)
- Deterministic data structures (hash vs sort-merge) and streaming/batching strategies.
- Parquet physical layout (file count, row-group sizing, compression), as long as declared writer sort keys are preserved where required.
- Geometry acceleration (spatial index) in S6 allowed if deterministic and doesn’t change acceptance semantics.
- Parallelism allowed only when worker-count invariance is proven (no dependence on scheduling).

---

## 6) Hotspots + safe optimization levers (per state)

### S1/S2 (raster + weights)
Hotspots: raster scans / aggregation.
Safe levers: deterministic chunked raster reads; vectorized aggregation; avoid nondeterministic reductions.

### S3/S4 (requirements + integer allocation)
Hotspots: groupby over outlet_catalogue; per-pair tile allocation.
Safe levers: per-merchant partitions; stable deterministic tie-breaks; avoid global sorts.

### S5 (site→tile RNG)
Hotspots: per-site RNG + event logging IO.
Safe levers: deterministic chunking; buffered writes; shard logs if contract allows set-semantics reads.

### S6 (point-in-country jitter)
Hotspots: point-in-polygon checks and resampling.
Safe levers: deterministic spatial indexing; cached polygons per country; keep attempt budgets strict.

### S7/S8 (joins + egress write)
Hotspots: large joins and ordered writing.
Safe levers: join on declared keys; stream synthesis; deterministic per-merchant chunks.

### S9 (validation + gating)
Hotspots: log reconciliation and checksum computation.
Safe levers: set-semantics reads for logs; bounded-memory checksumers; streaming validators.

---

## 7) Debug hooks (minimum to localize failures)

Critical hooks:
- S0: `s0_gate_receipt_1B` must record:
  - resolved 1A bundle root path
  - verified `_passed.flag` value (sha256 hex)
  - pass/fail outcome and error code on mismatch
- S3/S7: mismatch counters for missing/duplicate stub keys (first-N examples).
- S5: event coverage counters (exactly one event per site key).
- S6: attempt histograms + rejection reasons + ABORT codes.
- S9: bucketed validation failures + first-N offending keys per class.

Per-state baseline:
- deterministic rowcounts + distinct key counts
- deterministic key-column checksums (sampled deterministically)

---

## 8) Review flags (remaining actions to keep everything coherent)

1) **Token naming standardization**
- You decided to standardize on `manifest_fingerprint` everywhere.
- Action: update any schema/docs fragments that still say `fingerprint` (partition keys, examples).

2) **Mirror 1A validation path everywhere**
- Action: remove any residual `.../validation/fingerprint=...` examples; use the dictionary path only.

3) **Gate-in receipt enforcement**
- Action: ensure all states that read 1A egress explicitly require `s0_gate_receipt_1B` (FAIL_CLOSED if missing).
  - At minimum: S3 and S7 (and any future state that reads outlet_catalogue).

4) **Governance artefacts visibility**
- If numeric policy + math profile are intended to always be sealed (affecting manifest_fingerprint),
  ensure the dictionary (or a global rails pack) makes these inputs explicit so implementers don’t omit them.
