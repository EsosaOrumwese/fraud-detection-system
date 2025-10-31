# 2A · S0 — Gate & environment seal (RNG-free)

## 0. Document Meta & Status (Binding)

| Field | Value |
| --- | --- |
| **Document ID** | `state.2A.s0.expanded.md` |
| **Title** | Layer 1 · Segment 2A · **S0 — Gate & Environment Seal** |
| **Layer / Segment / State** | Layer 1 / Segment 2A / State 0 |
| **Status** | Draft (targets Alpha once §1–§10 are binding and evidence recorded) |
| **Owners (roles)** | 2A Spec Author · 2A Spec Reviewer · Program Governance Approver |
| **Last updated (UTC)** | 2025‑10‑30 |
| **Normative keywords** | **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **MAY** |

All statements in this document are binding unless explicitly marked *Informative*. Changes follow the change-control rules in §0.7.

### 0.1 Scope (Binding)
S0 governs the gate-in for Segment 2A. It verifies upstream Layer 1 artefacts, stages the time‑zone references required by downstream states, fixes the run identity, and emits the control receipt. S0 explicitly excludes RNG, civil-time calculations, or mutation of upstream datasets; those belong to later states.

### 0.2 Authority Set & Anchors (Binding)
| Surface | Anchor / ID | Notes |
| --- | --- | --- |
| Gate receipt schema | `schemas.2A.yaml#/control/s0_gate_receipt_2A` | Shape authority for S0 receipt. |
| Layer RNG envelopes | `schemas.layer1.yaml` | Layer-wide RNG definitions (S0 consumes no RNG but inherits envelope precedence). |
| Ingress ISO table | `schemas.ingress.layer1.yaml#/iso3166_canonical_2024` | FK domain for country codes. |
| Time-zone polygons | Dictionary `tz_world_2025a` | Reference staged in S0; version pinned via dictionary. |
| DST timetable | Dictionary `dst_timetable_iana_2025a` | Reference staged in S0; version pinned via dictionary. |
| Upstream site locations | Dictionary `site_locations` (Segment 1B) | Authority for 1B site_locations; PASS flag required. |
| Gate receipt target | Dictionary `s0_gate_receipt_2A` | Output location & partition law. |
| Optional run report | Dictionary `s0_run_report_2A` | Control-plane evidence (if present). |

Licence/provenance follow the Artefact Registry entries attached to each dictionary ID; S0 MUST record consumed versions in the receipt.

### 0.3 Precedence Chain (Binding)
1. JSON-Schema anchors listed in §0.2.
2. Dataset Dictionary entries.
3. Artefact Registry (licence/provenance).
4. This specification.

Schema > Dictionary > Registry > Spec; higher-precedence authorities win on conflict.

### 0.4 Compatibility Window (Binding)
- Upstream: Segment 1B state specs (notably `state.1B.s8_site_locations.expanded.md`), the 1B contract pack, and layer-wide schema packs.
- Downstream: 2A states expect the receipt and staged references emitted here.
- Any revision to these authorities or the receipt schema requires review (see §0.7).

### 0.5 Identity, Determinism & Partitions (Binding)
- Identity triple `{ seed, manifest_fingerprint, parameter_hash_2A }` fixed before any read/write.
- RNG: **none** consumed; counters unchanged.
- Outputs: gate receipt at `control/s0_gate_receipt/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash_2A}/`; optional run report at `control/s0_run_report/...` with identical partition keys.
- Determinism: re-publishing to the same identity MUST be byte-identical; determinism receipt recorded (see §4).

### 0.6 Non‑Functional Envelope & PAT Pointers (Binding)
- Target wall-clock < 2 minutes; peak RSS < 512 MiB during staging/verification.
- Required counters (run report or logs): `wall_clock_seconds_total`, `cpu_seconds_total`, `bytes_staged_refs`, `max_worker_rss_bytes`, `open_files_peak`, `workers_used`.
- Missing counters are a PAT violation (see §8).

### 0.7 Change Control & SemVer (Binding)
- **MAJOR**: Changes to receipt schema shape, partition keys, identity tokens, or required references.
- **MINOR**: Additive optional evidence fields or PAT metrics.
- **PATCH**: Editorial clarifications only.
Governance must approve MAJOR/MINOR changes before implementation.

### 0.8 Approvals & Ratification (Binding)
- **Alpha**: Sections §1–§10 populated with binding content and cross-references validated.
- **Stable**: PAT evidence attached on reference data; governance sign-off recorded in §0.
- Until Stable, behavioural changes require explicit owner approval.

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
