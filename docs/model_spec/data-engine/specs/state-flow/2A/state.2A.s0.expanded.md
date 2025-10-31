# 2A · S0 — Gate & environment seal (RNG-free)

## 0. Document Meta & Status (Binding)
- Document ID, title, layer/segment/state, status, owners, last‑updated, normative keywords.

### 0.1 Scope (Binding)
- Define what S0 covers (gate‑in, identity establishment, upstream checks) and what it explicitly excludes.

### 0.2 Authority Set & Anchors (Binding)
- Schemas: layer RNG envelopes, ingress anchors, S0 gate receipt schema.
- Dictionary IDs (2A): `s0_gate_receipt_2A`, required references (e.g., `tz_world_2025a`, `dst_timetable_iana_2025a`, `iso3166_canonical_2024`), upstream `site_locations`.
- Registry notes for provenance/licence.

### 0.3 Precedence Chain (Binding)
- Schema > Dictionary > Registry > This Spec.

### 0.4 Compatibility Window (Binding)
- State which upstream/downstream docs and schema pack versions this S0 assumes.

### 0.5 Identity, Determinism & Partitions (Binding)
- Identity triple `{ seed, manifest_fingerprint, parameter_hash_2A }`.
- RNG usage: none.
- Partitioning/sort for receipt/control artefacts.

### 0.6 Non‑Functional Envelope & PAT Pointers (Binding)
- Performance and operational constraints; which PAT counters must be recorded.

### 0.7 Change Control & SemVer (Binding)
- MAJOR/MINOR/PATCH rules for this S0 spec.

### 0.8 Approvals & Ratification (Binding)
- Criteria for Alpha/Stable ratification (sections complete + evidence attached).

## 1. Purpose & Scope (Binding)
- Gate‑in for Segment 2A: verify upstream 1B `site_locations` and PASS bundle, verify/stage time‑zone references, fix run identity, emit receipt.

## 2. Preconditions & Sealed Inputs (Binding)
- 1B validation PASS present for target fingerprint.
- Required references exist per Dictionary (TZ polygons, DST timetable, ISO canonical).
- Any other sealed prerequisites called out explicitly.

## 3. Identity & Partition Law (Binding)
- Receipt/run‑report paths, partition keys, writer sort.
- Path↔embed token equality rules.

## 4. Deliverables (Binding)
- `s0_gate_receipt_2A` (identity, versions, digests, acceptance flags).
- Optional `s0_run_report_2A` (control) with counters.
- Determinism receipt `{ partition_path, sha256_hex }` (outside dataset partitions).

## 5. Path↔Embed Parity (Binding)
- Embedded lineage fields (when present) must equal partition tokens.

## 6. Prohibitions (Binding)
- No RNG; no writes outside Dictionary; no alteration of upstream datasets; no partial/append publishes; no hard‑coded paths.

## 7. Validation Obligations (Binding)
- Schema validation for receipt/run‑report; Dictionary/Schema coherence.
- Licence/version assertions for references; integrity/digest checks; upstream PASS verification.

## 8. Evidence Surfaces (Binding)
- Required: gate receipt; determinism receipt.
- Recommended counters: `bytes_staged_refs`, `wall_clock_seconds_total`, `cpu_seconds_total`, `max_worker_rss_bytes`, `open_files_peak`, `workers_used`.

## 9. Failure Modes & Codes (Binding)
- E2A_S001_MISSING_UPSTREAM — missing 1B `site_locations` or PASS flag.
- E2A_S002_DICT_SCHEMA_MISMATCH — dictionary/schema incoherence.
- E2A_S003_RECEIPT_SCHEMA_INVALID — invalid gate receipt.
- E2A_S004_PARTITION_OR_IDENTITY — path/partition or path↔embed mismatch.
- E2A_S005_REFERENCE_VERSION — wrong/unsupported TZ/DST/ISO versions.
- E2A_S006_REFERENCE_INTEGRITY — missing/digest mismatch for references.

## 10. Performance Envelope (Binding)
- Bounded staging/verification time & memory; PAT counters present.

## 11. References & Cross‑Links (Informative)
- 2A overview, 1B `site_locations` spec, contract IDs (Dictionary/Schema), governance notes.
