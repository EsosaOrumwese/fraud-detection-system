# Segment 6B — Compiled Implementation Map (v0.1.0)

This is the reviewer-facing view derived from `segment_6B.impl_map.yaml`.
Use it to answer:
- What is frozen vs flexible?
- Where are the gates and what they authorize?
- Where are the performance hotspots and safe levers?
- If something is wrong, which state owns it?

Assumptions applied (your resolutions):
- The dataset dictionary is authoritative for partitioning; S1–S4 are scoped by
  **[seed, manifest_fingerprint, parameter_hash, scenario_id]** and token naming is `manifest_fingerprint`.
- Conceptual RNG “family” names are mapped onto the registered RNG event datasets and/or audit/trace via `rng_policy_6B`.
- `sealed_inputs_6B` is JSON to match the `.json` path.
- Registry indentation issues are fixed.

---

## 1) One-screen relationship diagram
```
Upstream prerequisites (must PASS for this manifest_fingerprint)
  Layer-1: 1A, 1B, 2A, 2B, 3A, 3B
  Layer-2: 5A, 5B
  Layer-3: 6A
  (S0 verifies each upstream segment’s PASS gate using that segment’s own hashing law)

6B pipeline
  └─ S0 (gate-in foundation / closed-world, RNG-free, metadata-only):
       - verifies upstream PASS gates (FAIL_CLOSED on any missing/mismatch)
       - seals the 6B input universe into sealed_inputs_6B (digest-linked)
       - writes s0_gate_receipt_6B + sealed_inputs_6B

  ├─ S1 (RNG): attach arrivals → entities + sessionise
  │    Inputs: arrival_events_5B + 6A entity world + policies
  │    Outputs: s1_arrival_entities_6B + s1_session_index_6B
  │
  ├─ S2 (RNG): baseline flow & event synthesis (all-legit)
  │    Inputs: S1 outputs + flow/amount/timing/RNG policies
  │    Outputs: s2_flow_anchor_baseline_6B + s2_event_stream_baseline_6B
  │             + rng_event_flow_anchor_baseline + rng_event_event_stream_baseline + audit/trace
  │
  ├─ S3 (RNG): fraud/abuse overlay + campaign catalogue
  │    Inputs: S2 outputs + 6A static posture + fraud policies
  │    Outputs: s3_campaign_catalogue_6B + s3_flow_anchor_with_fraud_6B + s3_event_stream_with_fraud_6B
  │             + rng_event_fraud_campaign_pick + rng_event_fraud_overlay_apply + audit/trace
  │
  ├─ S4 (RNG): truth & bank-view labelling + case timeline
  │    Inputs: S3 outputs + label/delay/case policies
  │    Outputs: s4_flow_truth_labels_6B + s4_flow_bank_view_6B + s4_event_labels_6B + s4_case_timeline_6B
  │             + rng_event_truth_label + rng_event_bank_view_label + audit/trace
  │
  └─ S5 (finalizer / consumer gate, RNG-free):
       - validates S1–S4 structure + coverage + RNG accounting
       - writes validation_bundle_6B + index.json + _passed.flag
       - emits 6B.final.bundle_gate (the only PASS authority for 6B)

Consumer rule (binding): downstream MUST verify the 6B final bundle gate for the same
manifest_fingerprint before treating ANY 6B outputs as authoritative (no PASS → no read).
```

---

## 2) Gates and what they authorize

### Upstream gates (verified in S0)
S0 verifies PASS gates for:
- Layer-1: 1A, 1B, 2A, 2B, 3A, 3B
- Layer-2: 5A, 5B
- Layer-3: 6A

S0 FAIL_CLOSED: if any required upstream gate is missing/mismatched, S0 writes nothing.

### Gate-in receipt (6B.S0.gate_in_receipt)
- Evidence: `s0_gate_receipt_6B` + `sealed_inputs_6B`
- Meaning: “S0 verified upstream gates and sealed the closed input universe”
- Rule: S1–S5 must fail-closed if missing; no reach-around reads.

### Final consumer gate (6B.final.bundle_gate)
- Location: `data/layer3/6B/validation/manifest_fingerprint={manifest_fingerprint}/`
- Evidence: `index.json` + `_passed.flag`
- Hash law: indexed-bundle raw-bytes concatenation (flag excluded; ASCII-lex path order); atomic publish with flag last.
- Authorizes downstream reads of: S1–S4 outputs + S4 labels/cases.

---

## 3) Order authorities (do not invent order)

- Arrivals: `arrival_events_5B` key `(merchant_id, arrival_seq)` is the attachment authority; S1 must emit exactly one row per arrival.
- Flows: `flow_id` is the join authority for all flow tables.
- Events: `(flow_id, event_seq)` is the join + ordering authority for event streams and event labels.
- Case timeline: `(case_id, case_event_seq)` orders case events.

---

## 4) Frozen surfaces (do not change)

Segment-wide:
- S0 is RNG-free and metadata-only (no data-plane scans).
- Closed input universe: S1–S5 may read only what’s listed in sealed_inputs_6B; must respect read_scope.
- Partitioning is binding (dictionary authority):
  - control-plane: `[manifest_fingerprint]`
  - behavioural tables: `[seed, manifest_fingerprint, parameter_hash, scenario_id]`
  - RNG logs/events: `[seed, parameter_hash, run_id]`

S1 (attachments):
- Exactly one attachment row per arrival.
- Session integrity: every session_id referenced by arrivals must exist in the session index.
- Must not mutate upstream arrivals or 6A entity tables.

S2 (baseline):
- All-legit baseline: no fraud semantics introduced here.
- Must not mutate S1; outputs are separate tables.

S3 (overlay):
- Must not mutate S2 in place; overlay expressed via S3 outputs + campaign provenance.
- Campaign catalogue is the sole authority for campaign provenance.

S4 (labels/cases):
- S4 is the sole authority for “truth vs bank-view”.
- Must not mutate S1–S3 in place.

S5 (gate):
- S5 is RNG-free and must fail-closed: do not publish _passed.flag unless required checks PASS.
- Gate hashing law + atomic publish is binding.

RNG evidence posture:
- Registered RNG event datasets are the canonical evidence surfaces:
  - S2: rng_event_flow_anchor_baseline, rng_event_event_stream_baseline
  - S3: rng_event_fraud_campaign_pick, rng_event_fraud_overlay_apply
  - S4: rng_event_truth_label, rng_event_bank_view_label
- “Conceptual families” (entity_attach, session_boundary, flow_shape, amount_draw, detection_delay, etc.)
  are mapped onto these registered datasets and/or audit/trace via `rng_policy_6B`.

---

## 5) Flexible surfaces (optimize freely; must preserve invariants)

- Vectorization/batching in S1–S4 is allowed if deterministic equivalence holds and ordering/key constraints are preserved.
- Parallelism allowed only with worker-count invariance proof (no schedule dependence).
- Whether some conceptual RNG markers are represented as audit/trace tags vs extra event datasets is a design choice;
  if they become distinct schemas, they must be registered and validated explicitly.

---

## 6) Hotspots + safe optimization levers

### S0 (upstream verification)
Hotspot: hashing/verifying many upstream bundles.
Safe levers: streaming hashing; deterministic member ordering; avoid materializing evidence.

### S1 (attachments/sessionisation)
Hotspot: joining huge arrival_events to entity universes and generating sessions.
Safe levers: keyed joins by merchant_id/party_id; deterministic chunking; precomputed indices; avoid global sorts.

### S2–S4 (flow/event generation + overlays + labels)
Hotspot: large event streams, multiple RNG decisions, and per-event labels.
Safe levers: streaming generation; deterministic per-flow batching; buffered log writes; avoid repeated joins by caching keyed lookups.

### S5 (validation + bundling)
Hotspot: scanning large outputs and reconciling RNG logs/events.
Safe levers: streaming validators; set-semantics reads for logs; stream hashing; deterministic index build.

---

## 7) Debug hooks (to localize failures)

Critical hooks:
- S0 receipt records:
  - verified digest + bundle root per upstream segment
  - sealed_inputs_digest and sealed list summary
- S1:
  - attachment coverage counters (arrivals_in vs rows_out)
  - missing entity FK counters (should be zero)
  - session coverage counters (sessions_referenced vs sessions_indexed)
- S2/S3/S4:
  - flow/event counts; first-N key mismatches
  - per-family RNG event counts + audit/trace reconciliation counters
- S5:
  - bucketed failures by class (coverage, FK, ordering, RNG accounting, campaign provenance, label alignment)
  - first-N offending keys (arrival_seq, flow_id, event_seq, case_id)
  - index completeness diagnostics + computed bundle digest

Baseline:
- deterministic rowcounts + distinct PK counts
- deterministic checksums over key columns (sampled deterministically)

---

## 8) Review flags (assumed resolved)
- Partitioning and token naming standardized to dictionary: `[seed, manifest_fingerprint, parameter_hash, scenario_id]`.
- Conceptual RNG families mapped onto registered RNG evidence surfaces (or registered if truly distinct).
- sealed_inputs_6B uses JSON format to match path and avoid tooling confusion.
- registry indentation fixed.
