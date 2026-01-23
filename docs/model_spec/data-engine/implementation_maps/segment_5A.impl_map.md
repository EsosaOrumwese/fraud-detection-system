# Segment 5A — Compiled Implementation Map (v0.1.0)

This is the reviewer-facing view derived from `segment_5A.impl_map.yaml`.
Use it to answer:
- What is frozen vs flexible?
- Where are the gates and what they authorize?
- Where are the performance hotspots and safe levers?
- If something is wrong, which state owns it?

Assumptions applied (as you requested):
- Token naming is standardized to `manifest_fingerprint` everywhere (paths/partitions/examples).
- The “S0 may record FAIL/MISSING, but S1+ must fail-fast unless all required upstream are PASS” split is treated as binding.

---

## 1) One-screen relationship diagram

Upstream (Layer-1) gates (verified in S0)
  - 1A, 1B, 2A, 2B, 3A, 3B each publish validation bundle + _passed.flag
  - S0 verifies each upstream gate using that segment’s own hashing law
  - S0 records PASS/FAIL/MISSING per upstream segment

5A pipeline (RNG-free)
  └─ S0 (gate-in foundation / closed-world):
       - verifies upstream gates (records status map)
       - seals the 5A input universe into sealed_inputs_5A (digest-linked)
       - writes s0_gate_receipt_5A (+ optional scenario_manifest_5A)

  ├─ S1 (deterministic): demand class + base scale per merchant×zone
  │    → merchant_zone_profile_5A (+ optional merchant_class_profile_5A)
  │
  ├─ S2 (deterministic): weekly unit-mass shapes per class×zone on a bucket grid
  │    → shape_grid_definition_5A + class_zone_shape_5A (+ optional class_shape_catalogue_5A)
  │    (scoped by parameter_hash + scenario_id)
  │
  ├─ S3 (deterministic): baseline weekly intensities (local time buckets)
  │    → merchant_zone_baseline_local_5A (+ optional class aggregate / UTC projection)
  │    (scoped by manifest_fingerprint + scenario_id; embeds parameter_hash)
  │
  ├─ S4 (deterministic): scenario overlays over horizon buckets
  │    → merchant_zone_scenario_local_5A (+ optional overlay factors / UTC scenario)
  │    (scoped by manifest_fingerprint + scenario_id)
  │
  └─ S5 (finalizer / consumer gate):
       - validates S0 invariants and whatever S1–S4 artefacts exist
       - writes validation_bundle_5A + index + _passed.flag (final gate)

Consumer rule (binding): downstream MUST verify 5A final bundle gate for the same
manifest_fingerprint before reading ANY 5A modelling outputs (S1–S4).

---

## 2) Gates and what they authorize

### Upstream gates (verified in S0)
S0 verifies for the target manifest_fingerprint:
- 1A.final.bundle_gate
- 1B.final.bundle_gate
- 2A.final.bundle_gate
- 2B.final.bundle_gate
- 3A.final.bundle_gate (note: 3A uses digest-of-digests)
- 3B.final.bundle_gate

S0 FAIL_CLOSED on the verification operation itself (it must not fabricate PASS),
but it may record FAIL/MISSING outcomes for later fail-fast enforcement.

### Gate-in receipt (5A.S0.gate_in_receipt)
- Evidence: `s0_gate_receipt_5A` + `sealed_inputs_5A`
- Meaning: “S0 verified upstream gates and sealed the input universe”
- Downstream S1–S5 must fail-closed if missing.

### Final consumer gate (5A.final.bundle_gate)
- Location: `data/layer2/5A/validation/manifest_fingerprint={manifest_fingerprint}/`
- Evidence: `validation_bundle_index_5A.json` + `_passed.flag`
- Hash law: index-driven raw-bytes concat hashing (flag excluded), then publish atomically (flag last).
- Authorizes downstream reads of:
  - merchant_zone_profile_5A
  - shape_grid_definition_5A / class_zone_shape_5A
  - merchant_zone_baseline_local_5A
  - merchant_zone_scenario_local_5A
  (+ optional related artefacts)

---

## 3) Frozen surfaces (do not change)

Segment-wide:
- **RNG-free**: no RNG consumption, no rng_event_* families.
- S0 is the sole authority for the closed input universe:
  - downstream MUST NOT read anything not in sealed_inputs_5A
  - sealed_inputs_digest linkage is binding
- **S0 vs S1+ gate semantics (binding)**:
  - S0 may complete while recording upstream FAIL/MISSING
  - S1+ MUST fail-fast unless all required upstream segments are PASS
- Shape bucket ordering authority:
  - `shape_grid_definition_5A.bucket_index` is the single authority; consumers align by bucket_index.

S1 (class+scale authority):
- S1 is the sole authority for demand_class and base_scale per merchant×zone.

S2 (shape authority):
- Shapes are unit-mass; Σ bucket_mass = 1 per (class,zone[,channel]).
- Output identity is (parameter_hash, scenario_id) (reusable across worlds).

S3 (baseline authority):
- Baseline λ must align to S2 grid and use S1 class/scale and baseline_intensity_policy_5A.
- No recomputation of shapes or classing.

S4 (overlay authority):
- Scenario λ = baseline × overlay factors, ordered/validated by overlay policies.
- Horizon mapping must be consistent with grid + horizon config.

S5 (gate publisher):
- S5 only validates and publishes evidence + gate.
- Must not publish _passed.flag on FAIL; atomic publish is binding.

---

## 4) Flexible surfaces (optimize freely; must preserve invariants)

- Streaming/batched computation for S1–S4 if deterministic and ordering contracts are preserved.
- Physical parquet layout choices are flexible as long as:
  - writer ordering keys are preserved where declared, and
  - validation/hashing semantics remain correct.
- Optional outputs (catalogues, UTC projections, overlay factors) may be omitted when config says optional.

---

## 5) Hotspots + safe optimization levers

### S0 (multi-segment upstream verification)
Hotspot: hashing multiple upstream validation bundles.
Safe levers: stream hashing; deterministic path ordering; avoid loading big evidence files into memory.

### S1 (merchant×zone domain build)
Hotspot: joining/expanding over large merchant×zone domains.
Safe levers: deterministic chunking by merchant_id; avoid global sorts beyond declared keys.

### S2 (shape library)
Hotspot: many class×zone combinations.
Safe levers: template reuse; vectorized normalization; deterministic key ordering.

### S3/S4 (large surface generation)
Hotspot: merchant×zone×bucket (baseline) and merchant×zone×horizon (scenario).
Safe levers: streaming writers; reuse shapes; precompute overlay factors by scope; deterministic joins.

### S5 (validation + gate)
Hotspot: scanning large parquet surfaces and hashing bundle members.
Safe levers: streaming validators; bounded-memory checks; stream hashing and deterministic index construction.

---

## 6) Debug hooks (to localize failures)

Critical hooks:
- S0 receipt records:
  - upstream PASS/FAIL/MISSING map (1A–3B) + verified digests and bundle roots
  - sealed_inputs_digest and the sealed list (id+digest+schema_ref)
  - scenario_id and parameter_hash bindings
- S1: class distribution + base_scale stats
- S2: unit-mass Σ checks per shape + max deviation
- S3/S4: min/max λ stats + count of invalid/non-finite values
- S5: bucket validation failures by class + first-N offending keys/paths

Baseline (per state):
- deterministic rowcounts + distinct key counts
- deterministic checksums over key columns (sampled deterministically)

---

## 7) Review flags (assumed resolved)
- Standardize `manifest_fingerprint` token usage everywhere.
- Keep crisp semantics: “S0 may record failures; S1+ must fail-fast unless all required upstream are PASS.”
