# Data Engine Black-Box Interface

_Derived from segment registries, dataset dictionaries, schemas, and state-expanded docs._

## Purpose

This document defines the **black-box interface** of the Data Engine: identity, addressing/discovery, authoritative outputs, and readiness gates. It is designed to be depended on by platform components (Scenario Runner, Ingestion, Event Bus, Feature Planes, Labels/Cases, Observability/Governance) without importing engine internal algorithms.

## Identity and determinism

### Identity fields

- `manifest_fingerprint`: world identity (content-address of the sealed world inputs + governed parameter bundle).
- `parameter_hash`: governed parameter bundle identity (policy/config pack).
- `seed`: realisation key for RNG-consuming lanes.
- `scenario_id`: scenario identity (used where scenario overlays apply).
- `run_id`: execution correlation id; **partitions logs/events** but is not allowed to change sealed world outputs for a fixed identity tuple.

### Determinism promise

**Determinism & immutability.** For every output, **identity is defined by its partition tokens** (as declared in `engine_outputs.catalogue.yaml`). For a fixed identity partition, the engine promises **byte-identical** materialisations across re-runs and enforces **write-once / immutable partitions**. `run_id` may partition logs/events, but **MUST NOT** change the bytes of any output whose identity does not include `run_id`.

## Discovery and addressing

Outputs are addressed by **tokenised path templates**. The canonical fingerprint token is:

- `manifest_fingerprint={manifest_fingerprint}`

Common partition families:

- **Parameter-scoped**: `parameter_hash={parameter_hash}`
- **Fingerprint-scoped**: `manifest_fingerprint={manifest_fingerprint}`
- **Seed+fingerprint egress**: `seed={seed}/manifest_fingerprint={manifest_fingerprint}`
- **Run-scoped logs/events**: `seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}` (and/or `scenario_id` where applicable)

The authoritative inventory of outputs (IDs, paths, schemas, join keys) is `engine_outputs.catalogue.yaml`.

## Output taxonomy

- **Surfaces**: structured datasets (parquet/json) used for joins/context ("authority surfaces").
- **Streams**: append-only event/log families (e.g., RNG event streams).
- **Gate artifacts**: validation bundles, `_passed.flag` files, and gate receipts used to enforce readiness (class `gate` in the catalogue).

### Roles for event-like outputs (binding)

Not all event-like outputs are `class: stream` (some are parquet event tables, e.g. `arrival_events_5B`).
Downstream components MUST distinguish traffic from join surfaces, truth, and telemetry:

| Role | Meaning | How it is used | Examples (output_id) |
|---|---|---|---|
| `traffic_primitives` | Event skeletons intended to be built upon by later segments. | Join surface for enrichment; **not** emitted to the platform traffic bus by default. | `arrival_events_5B` |
| `behavioural_streams` | Canonical synthetic production traffic (baseline + post-overlay). | Eligible for ingestion to Event Bus / feature plane. | `s2_event_stream_baseline_6B`, `s3_event_stream_with_fraud_6B` |
| `behavioural_context` | Flow/session/arrival context needed to enrich behavioural streams. | Join surfaces for RTDL/feature planes; not traffic. | `s2_flow_anchor_baseline_6B`, `s3_flow_anchor_with_fraud_6B`, `s1_arrival_entities_6B`, `s1_session_index_6B` |
| `truth_products` | Canonical labels/case truth products. | Read for supervision/eval/case tooling; not treated as traffic. | `s4_event_labels_6B`, `s4_case_timeline_6B`, `s4_flow_truth_labels_6B`, `s4_flow_bank_view_6B` |
| `audit_evidence` | Replay/audit traces (often RNG evidence). | Observability/forensics only; MUST NOT be treated as traffic. | `rng_audit_log_*`, `rng_trace_log_*`, `rng_event_*`, `gamma_draw_log_3B`, `s5_selection_log`, `s6_edge_log` |
| `ops_telemetry` | Operational run journals. | Monitoring/debugging only. | `segment_state_runs_*` |

Rules:
- Components MUST NOT treat `traffic_primitives`, `audit_evidence`, or `ops_telemetry` as canonical business traffic.
- Any output emitted onto a bus as `behavioural_streams` MUST conform to `contracts/canonical_event_envelope.schema.yaml` (natively, or via a lossless wrapper/mapping at ingestion).

### Traffic policy (current platform default)

**Dual-stream policy (baseline + post-overlay):**
- **Traffic streams:** `s2_event_stream_baseline_6B`, `s3_event_stream_with_fraud_6B`
- **Not traffic (join surfaces):** `arrival_events_5B`, `s1_arrival_entities_6B`, `s1_session_index_6B`, `s2_flow_anchor_baseline_6B`, `s3_flow_anchor_with_fraud_6B`
- **Truth products:** `s4_event_labels_6B`, `s4_flow_truth_labels_6B`, `s4_flow_bank_view_6B`, `s4_case_timeline_6B`

This policy reflects the engine’s design intent: event streams are **intentionally thin**, and Layer-1/Layer-2 context is joined from authority and behavioural-context surfaces.

### Join map for behavioural streams (binding for platform use)

**Event stream → flow anchor (context enrichment)**
- Baseline: `s2_event_stream_baseline_6B` ↔ `s2_flow_anchor_baseline_6B`  
  Join keys: `seed`, `manifest_fingerprint`, `scenario_id`, `flow_id`
- Post-overlay: `s3_event_stream_with_fraud_6B` ↔ `s3_flow_anchor_with_fraud_6B`  
  Join keys: `seed`, `manifest_fingerprint`, `scenario_id`, `flow_id`

**Flow anchor → arrival skeleton (routing/timezone context)**
- `s2_flow_anchor_baseline_6B` / `s3_flow_anchor_with_fraud_6B` ↔ `arrival_events_5B`  
  Join keys: `seed`, `manifest_fingerprint`, `scenario_id`, `merchant_id`, `arrival_seq`

**Arrival skeleton → entity attachments**
- `arrival_events_5B` ↔ `s1_arrival_entities_6B`  
  Join keys: `seed`, `manifest_fingerprint`, `scenario_id`, `merchant_id`, `arrival_seq`  
  Note: `parameter_hash` is run-constant and present in 6B surfaces but not in `arrival_events_5B`.

**Truth products → traffic**
- `s4_event_labels_6B` ↔ `s3_event_stream_with_fraud_6B`  
  Join keys: `seed`, `manifest_fingerprint`, `scenario_id`, `flow_id`, `event_seq`
- `s4_flow_truth_labels_6B` ↔ `s3_flow_anchor_with_fraud_6B`  
  Join keys: `seed`, `manifest_fingerprint`, `scenario_id`, `flow_id`
- `s4_flow_bank_view_6B` ↔ `s3_flow_anchor_with_fraud_6B`  
  Join keys: `seed`, `manifest_fingerprint`, `scenario_id`, `flow_id`

**Case truth**
- `s4_case_timeline_6B` is case-centric (join via `case_id`), not a direct event/flow join.

### Platform join posture (binding)

**Practical rule (pinned):**
- **Traffic stays thin.** Only behavioural streams are emitted as traffic.
- **Joins occur inside the platform** (IEG/OFP or equivalent), using **preloaded indexes/projections** keyed by the join map above. Platform components MUST NOT scan the oracle set per event.
- **No future leakage.** Only **time-safe** context surfaces may be used in RTDL. Any surface/field that implies future knowledge is **batch‑only** and must not be used for live decisions.

### Time-safety guidance (v0, based on observed schemas)

**Time-safe join surfaces (RTDL‑eligible)**
- `arrival_events_5B` (arrival skeleton; routing/timezone context).
- `s1_arrival_entities_6B` (entity attachments for the same arrival).
- `s2_flow_anchor_baseline_6B`, `s3_flow_anchor_with_fraud_6B` (flow‑level context at event time).

**Oracle‑only / batch‑only surfaces**
- `s1_session_index_6B` includes `session_end_utc` and `arrival_count` (requires full session closure).
- All truth products (`s4_*`) are **offline** labels/case truth and must never be used for live decisions.

**Field‑level caution**
- Any field that implies **future aggregation** (counts over a session, end timestamps, post‑hoc labels) is **not RTDL‑safe** even if the dataset is otherwise used for joins.

## Catalogue fields (selected)

- `class`: `surface`, `stream`, or `gate` (gate artifacts are not consumption surfaces).
- `exposure`: `internal` or `external` (external means the schema anchor lives under `/egress/`).
- `scope`: deterministic identity scope derived from partition tokens (examples: `scope_parameter_hash`, `scope_manifest_fingerprint`, `scope_parameter_hash_seed_run_id`, `scope_parameter_hash_manifest_fingerprint_seed_scenario_id`).
- `availability`: `optional` means the engine may omit the output; absence implies required.

## Join semantics

Join keys are defined per surface in the catalogue (primary keys and stable linkage keys). Downstream components MUST NOT infer semantics from physical file row order; only declared keys and authority fields are binding.

## Lineage invariants (binding)

- **Path-embed equality.** Where lineage appears both in a path token and inside rows/fields, values **MUST byte-equal** (for example, `row.manifest_fingerprint == fingerprint`, `row.seed == seed`, `row.parameter_hash == parameter_hash`).
- **File order is non-authoritative.** Consumers MUST treat **partition keys + PK/UK + declared fields** as truth; physical file order conveys no semantics.
- **Atomic publish + immutability.** Outputs are staged and atomically moved into place; once published, an identity partition is immutable (re-publish must be byte-identical or fail).

## HashGates and readiness rulebook

Every segment publishes a **segment-level HashGate**:

- a fingerprint-scoped validation bundle (or bundle index) and
- a fingerprint-scoped `_passed.flag` (or equivalent) whose content/digest is defined by the segment's hashing law.

**No PASS -> no read.** Any consumer (engine segments and platform components) MUST verify the relevant segment gate before treating gated outputs as authoritative.

* **Do not assume a universal hashing method.** Gate verification is **gate-specific**; some segments hash concatenated raw bytes, others hash structured member digests. Consumers MUST follow `engine_gates.map.yaml` for the exact verification procedure.

Operational verification details (paths, hashing law, and gate->output mapping) are defined in `engine_gates.map.yaml`.

**Instance-scoped outputs require instance proof.** Segment gates are world/structural prerequisites. For any output whose scope includes `seed`, `scenario_id`, `parameter_hash`, or `run_id`, consumers MUST ALSO require a Rails HashGate PASS receipt bound to the exact output instance. The receipt MUST bind to an `engine_output_locator` (target_ref) and digest (target_digest). Multi-file outputs MAY use a bundle manifest digest with `bundle_manifest_ref`. For these outputs, `engine_output_locator.content_digest` MUST be present so the instance proof can be bound deterministically.

**Instance-proof receipt contract + path convention.**
- Schema: `contracts/instance_proof_receipt.schema.yaml`
- Engine-emitted path convention (segment-local, by output_id + partitions):
  `data/layer{L}/{SEG}/receipts/instance/output_id={output_id}/{partition_tokens}/instance_receipt.json`
  - `{partition_tokens}` are the output’s partitions in canonical order (see storage_layout_v1.md).
  - Only tokens applicable to the output_id are included.
- If the engine remains a **black box** and does not emit receipts, Scenario Runner MAY emit **verifier receipts** into its own object store using the same schema (see SR contract README for the SR path convention).
