Note this doc is more conceptual than the other conceptual spec planners as they were born out of docs like this

black-box framing:
{
""""
Through the hierarchical modular lens, the **Offline Feature Plane “shadow twin”** is the **replay + reconstruction plane**: it consumes the same admitted event history and feature definitions as OFP, and **rebuilds feature snapshots/datasets deterministically** for training, audits, and parity checks.

## Level 0 — Black-box view

**Inputs**

* **Replayable admitted events** (from EB, within retention or from an archive)
* **Feature definitions / FeatureGroup registry** (same versions as OFP)
* **ContextPins** (run/world scoping) and (optionally) Decision/Audit references (what snapshot was used online)

**Outputs**

* **Offline feature datasets** (training-ready tables) keyed by the same `FeatureKey` concepts
* **Reconstructed feature snapshots** (for a given decision/event “as-of” time)
* **Parity evidence**: “does offline rebuild match the online snapshot hash/id?” (if you enforce parity)

One sentence: **“Recompute what OFP would have known at time T, from replay, in a deterministic and auditable way.”**

---

## Level 1 — Minimal modules (v0-thin)

1. **Replay/Assembly**

* Reads events from EB (or archived log) by offset/time window
* Provides deterministic ordering rules for assembly (per-partition semantics respected)

2. **Feature Computation Engine**

* Applies the same FeatureGroups/transforms as OFP (by version)
* Computes rolling aggregates/windows offline (batch-friendly)

3. **As-of Snapshot Builder**

* Given `{FeatureKey, as_of_time}` produces a **FeatureSnapshot** identical in shape to OFP
* Produces a deterministic `feature_snapshot_hash/id` using the same rules

4. **Dataset Materializer**

* Produces training tables / feature matrices (e.g., per-event, per-entity, per-window)
* Emits dataset manifests/refs (so Model Factory can consume)

5. **Parity Validator (the “shadow” part)**

* Compares offline rebuilt snapshots/hashes to online recorded snapshot refs/hashes (from DLA/DF provenance)
* Emits parity results (match/mismatch + explanation)

6. **Lineage/Governance Layer**

* Records which inputs, offsets, feature group versions, and policies produced each dataset/snapshot

---

## Level 2 — What other components “see”

* **Consumes:** EB admitted events + (optionally) DLA decision records to know *which snapshots to rebuild/check*
* **Produces:** offline feature datasets for learning, and parity reports for governance
* **Serves:** “rebuild snapshot as-of” query for audits (optional)

---

## Cross-cutting “laws” (what will be tight later)

* **Parity contract:** same FeatureGroup versions + same inputs + same as-of rule ⇒ same snapshot hash
* **Determinism:** replay + compute must be stable (no nondeterministic ordering, stable numeric representation if hashing)
* **Joinability:** everything is scoped by `ContextPins` and keyed by canonical `FeatureKey`
* **As-of semantics:** “what was known at decision time” must be defined (event_time vs ingest_time vs watermark basis)
* **Non-interference:** offline plane never affects real-time decisions; it only reconstructs and validates
""""
}


tighten vs loose split
{
""""
Here’s the **v0-thin “tighten vs stay loose”** for the **Offline Feature Plane shadow twin (OFP-Shadow)**.

## What needs tightening (pin this in the spec)

### 1) Parity goal (what “shadow twin” promises)

Pick the v0 posture clearly:

* **Parity by hash:** offline rebuild must reproduce the same `feature_snapshot_hash/id` as OFP (when given the same versions + as-of semantics), **or**
* **Parity by tolerance:** allow small numeric drift (dangerous if you’re hashing)
  In your platform style, the right v0 is: **parity by hash** (requires tight numeric representation rules).

### 2) As-of semantics (the core of “what we knew at time T”)

Pin:

* whether as-of uses **event_time** or **ingest_time** (or watermark basis)
* how late/out-of-order events are treated in offline reconstruction
* the exact definition of the “cut” for windows (half-open intervals)

### 3) Versioning of feature definitions

Pin:

* offline must use the **same FeatureGroup versions** recorded in online provenance
* no “latest by default” unless explicitly requested and recorded

### 4) Replay input basis and determinism

Pin:

* what inputs define the replay slice: `{stream, partition_id, offset range}` or `{time range}`
* if time-based, it must map to offsets deterministically (best-effort is fine but must be recorded)
* deterministic ordering rules for assembling events across partitions (no implied global ordering)

### 5) Snapshot contract alignment with OFP

Pin that offline outputs the **same FeatureSnapshot + Provenance shape** as OFP (or a strict superset), including:

* `ContextPins`
* `FeatureKey`
* group versions
* freshness/as-of metadata
* `feature_snapshot_hash/id`

### 6) Parity validation output contract

Pin the minimum parity record:

* what was compared (snapshot ref/hash, key, as-of)
* result: MATCH / MISMATCH / UNCHECKABLE
* evidence: versions used, basis offsets/watermarks, mismatch fields list
* correlation keys to DLA decision record (`decision_id`/`request_id`)

### 7) Dataset materialization contract (minimal)

Even in v0, pin:

* dataset keying (by FeatureKey, by event, by time window)
* manifest/provenance requirements (versions, input basis, schema version)
  (You can keep formats loose, but the “manifest must exist” is important.)

### 8) Failure posture

Pin what happens when:

* replay window doesn’t have enough history (retention limits)
* feature group version missing
* snapshot uncheckable (must be explicit, not silent)

---

## What can stay loose (implementation freedom)

* Compute engine (Spark/DuckDB/Polars/custom batch)
* Storage formats (Parquet/Delta/CSV) and partitioning strategy
* How you parallelize replay/compute
* Whether offline stores intermediate aggregates
* Where parity checks run (batch nightly vs on-demand)
* How you index archived events (as long as basis is recorded and deterministic)

---

### One-line v0 contract for OFP-Shadow

**“OFP-Shadow replays admitted events to rebuild OFP-equivalent feature snapshots/datasets as-of time T using recorded FeatureGroup versions, and emits parity results that are joinable to online decisions.”**
""""
}


proposed doc plan + contract pack + repo layout
{
""""
Here’s the **Offline Feature Plane shadow twin (OFS) v0-thin package**: **OFS1–OFS5 doc plan + 1 contracts file + file tree** under `docs\model_spec\real-time_decision_loop\`.

---

## OFS1–OFS5 (v0-thin) doc set

### **OFS1 — Charter & Boundaries**

Pins what OFS is and isn’t.

* Purpose: replay + reconstruct “what OFP would have known” for audits/training/parity
* Authority: offline datasets + parity results (not real-time serving, not decisioning)
* Laws: deterministic replay; version-locked feature definitions; joinable outputs; non-interference with live loop

### **OFS2 — As-of Semantics & Replay Basis**

Pins the definition of “as-of” and how replay slices are defined.

* As-of rule (event_time vs ingest_time vs watermark basis) — v0 closure
* Window interval semantics (half-open; late events handling)
* Replay basis definition:

  * offset-based (preferred) and time-based (optional) + determinism requirements
* Deterministic cross-partition assembly posture (no implied global ordering)

### **OFS3 — Feature Definition Versioning & Snapshot Reconstruction**

Pins how OFS matches OFP.

* Must use the exact FeatureGroup versions recorded in online provenance
* Snapshot reconstruction contract (same shape as OFP, same hash/id rules)
* Numeric representation rules for hashing (avoid float drift)
* Handling missing versions / missing history (explicit UNCHECKABLE posture)

### **OFS4 — Dataset Materialization & Manifests**

Pins the minimal offline dataset story.

* Dataset kinds (per-event, per-entity, per-window) — v0 minimal list
* Dataset schema posture (manifest-driven; v0 minimal fields)
* Manifests must record: ContextPins, feature group versions, input basis (offset watermarks), schema version
* Export posture (where datasets go; transport loose)

### **OFS5 — Parity Validation, Ops & Acceptance**

Pins the “shadow twin” validation contract + ops.

* Parity check inputs (online snapshot ref/hash + key + as-of) and output record
* Results enum: MATCH / MISMATCH / UNCHECKABLE
* Evidence requirements (versions, basis, mismatch fields)
* Observability (parity rates, mismatch categories, rebuild latency)
* Acceptance scenarios (rebuild matches hashes; uncheckable explicit; determinism across reruns)

---

## Minimal contracts (v0-thin)

Keep to **one schema file**:

### `contracts/ofs_public_contracts_v0.schema.json`

Recommended `$defs`:

* `ContextPins`
* `FeatureKey` *(same as OFP v0, or duplicated in v0)*
* `ReplayBasis`

  * either `{stream_name, partition_id, from_offset, to_offset}` (half-open)
  * or `{from_time_utc, to_time_utc}` (optional, best-effort)
* `AsOfSpec`

  * required: `as_of_time_utc`, plus `as_of_basis` enum (event_time/ingest_time/watermark)
* `FeatureGroupRef` / `FeatureGroupVersionSet`
* `RebuiltFeatureSnapshot`

  * required: `snapshot_hash_or_id`, `features{}`, `provenance`
* `ParityResult`

  * required: `decision_id_or_request_id`, `feature_key`, `as_of_spec`, `online_snapshot_ref_or_hash`, `offline_snapshot_ref_or_hash`, `result`, `evidence`
* `DatasetManifest` *(thin)*

  * required: `dataset_kind`, `schema_version`, `context_pins`, `feature_group_versions`, `replay_basis`, `artifact_ref`
* `ErrorResponse` *(thin, optional)*

**v0 note:** keep actual dataset file formats and locations as opaque `artifact_ref` values.

---

## File tree layout (focused on OFS)

```text
docs/
└─ model_spec/
   └─ real-time_decision_loop/
      └─ offline_feature_plane_shadow/
         ├─ README.md
         ├─ AGENTS.md
         │
         ├─ specs/
         │  ├─ OFS1_charter_and_boundaries.md
         │  ├─ OFS2_as_of_semantics_and_replay_basis.md
         │  ├─ OFS3_feature_versioning_and_snapshot_reconstruction.md
         │  ├─ OFS4_dataset_materialization_and_manifests.md
         │  └─ OFS5_parity_validation_ops_acceptance.md
         │
         └─ contracts/
            └─ ofs_public_contracts_v0.schema.json
```
""""
}
