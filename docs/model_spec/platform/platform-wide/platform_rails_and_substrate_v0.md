# Platform Rails + Substrate Pins (v0)
_As of 2026-01-24_

This document pins the **platform-wide rails** and the **shared substrate conventions** that all components must obey in v0. It is the binding reference for Phase 1.

---

## 1) Identity + canonical envelope

### 1.1 ContextPins (join identity)
**ContextPins** are the universal join identity and must be carried on any run-joinable record:

```
{ scenario_id, run_id, manifest_fingerprint, parameter_hash }
```

**Seed is separate.** `seed` is required when an output/event is seed-variant (RNG-consuming or run-realization specific). It is **not** part of ContextPins and must not silently substitute for them.

### 1.2 Canonical event envelope (platform boundary)
The canonical event envelope is the platform boundary contract for IG/EB. The authoritative schema is:

```
docs/model_spec/data-engine/interface_pack/contracts/canonical_event_envelope.schema.yaml
```

**Envelope minimality:** top-level fields are reserved for the envelope; payloads live under `payload`. Do not introduce additional top-level fields outside the schema.

**Required fields:** `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`  
**Optional pins:** `parameter_hash`, `seed`, `scenario_id`, `run_id`  
**Optional metadata:** `schema_version`, `emitted_at_utc`, `trace_id`, `span_id`, `producer`, `parent_event_id`, `payload`

**Schema-version rule:** if an event type is versioned, `schema_version` **must** be set. Missing `schema_version` is rejected unless IG policy explicitly defines a safe default for that event_type.

### 1.3 Time semantics (no drift)
- **Domain time:** `ts_utc` (event meaning)
- **Producer emission time:** `emitted_at_utc` (optional)
- **Ingestion time:** recorded in **IG receipts**, not in the envelope

**Legacy alias mapping:** if upstream uses `event_time` or `event_time_utc`, it **maps to** `ts_utc`.  
If upstream uses `ingest_time`, it **maps to** IG receipt ingestion time, not envelope fields.

---

## 2) By-ref artifact addressing + digest posture

### 2.1 Object store prefix map (v0)
Default bucket: **`fraud-platform`** (vendor-neutral; S3-compatible semantics).

Prefixes (authoritative by component):
- `engine/` — engine outputs + gate receipts (engine is truth owner)
- `sr/` — run_plan, run_record, run_status, run_facts_view, READY signals (SR is truth owner)
- `wsp/` — world stream checkpoints (WSP operational state only)
- `ig/receipts/` — ingestion receipts (IG truth owner)
- `ig/quarantine/` — quarantine evidence (IG truth owner)
- `dla/audit/` — immutable audit records (DLA truth owner)
- `ofs/` — offline feature snapshots + DatasetManifests (OFS truth owner)
- `mf/` — training/eval evidence (Model Factory truth owner)
- `registry/bundles/` — model/policy bundles (Registry truth owner)
- `gov/` — governance facts (Run/Operate truth owner)
- `profiles/` — versioned policy profiles (policy truth owner)

### 2.2 Locator + digest posture
**Locator contract:**  
`docs/model_spec/data-engine/interface_pack/contracts/engine_output_locator.schema.yaml`

**Gate receipt contract:**  
`docs/model_spec/data-engine/interface_pack/contracts/gate_receipt.schema.yaml`

**Digest rules:**
- If an output is gated by instance-proof, the locator **must** include `content_digest`.
- Multi-file outputs may use a bundle manifest digest; receipts must bind to a target ref + digest.
- **No PASS → no read; fail closed** on missing/invalid gate receipts or mismatched digests.

### 2.3 Instance-proof receipts (paths)
Engine-emitted instance receipts (if available):
```
data/layer{L}/{SEG}/receipts/instance/output_id={output_id}/{partition_tokens}/instance_receipt.json
```

If the engine remains a black box and does not emit instance receipts, SR may emit **verifier receipts** using the same schema under:
```
fraud-platform/sr/instance_receipts/output_id={output_id}/{partition_tokens}/instance_receipt.json
```

### 2.4 Token order (partitioned paths)
Canonical token order across partitions:
```
seed -> parameter_hash -> manifest_fingerprint -> scenario_id -> run_id -> utc_day
```

Allowed token names are **only**: `seed`, `parameter_hash`, `manifest_fingerprint`, `scenario_id`, `run_id`, `utc_day`.
Do not introduce new token names without a platform-wide change.

---

## 3) Event bus taxonomy + partitioning rules

### 3.1 Topic taxonomy (v0)
- **`fp.bus.traffic.v1`** — admitted business traffic (canonical envelopes)
- **`fp.bus.control.v1`** — control facts (READY, governance facts, registry lifecycle, posture changes)
- **`fp.bus.audit.v1`** — optional pointer events (audit/feature snapshot pointers only; never a truth stream)

### 3.2 Partitioning posture (pinned)
- EB does **not** infer partitioning. IG stamps a deterministic `partition_key`.
- Partitioning policy is versioned and controlled by IG policy profiles (`partitioning_profile_id`).
- Partition choice must preserve the ordering that matters to the hot path (typically entity-local ordering).
- EB coordinates `(stream, partition, offset)` are the **only** universal replay/progress tokens.

---

## 4) Environment ladder profiles (policy vs wiring)

Profiles are stored under:
```
config/platform/profiles/
```

Each profile must separate:
- **Policy config** (outcome-affecting; versioned, stamped in receipts/decisions)
- **Wiring config** (endpoints, ports, resource limits; not outcome-affecting)

Promotion between environments is a **profile change**, not a code fork.

---

## 5) Security + secrets posture (platform-wide)

- **Secrets are runtime-only.** Do not place credentials or tokens in artifacts, build plans, impl_actual, or logbooks.
- Provenance may record **secret identifiers** (e.g., key IDs), never secret material.
- If runtime artifacts may contain sensitive tokens, the user must be alerted so they can decide whether to delete or quarantine them.
