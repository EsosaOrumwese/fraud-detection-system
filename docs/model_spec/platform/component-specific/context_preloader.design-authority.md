# Context Preloader Design Authority

## 1. Purpose + Scope

The Context Preloader is a control-plane loader that bridges a specific gap in the platform runtime: traffic streams are intentionally thin, but RTDL components are not allowed to read the Oracle Store. Without an explicit preload step, there is no sanctioned way to obtain the join context required to enrich traffic for RTDL decisions.

This component exists to make that join context available inside the platform boundary, in a deterministic and auditable way, without introducing Oracle Store reads into the RTDL plane. It materializes time-safe join surfaces from Oracle Store into platform-owned indexed state and produces a receipt that proves exactly what was loaded and from which oracle world.

### In scope (detailed)

1) Input sources (time-safe context only)
- Read the following join surfaces from the Oracle Store:
  - `arrival_events_5B` (arrival skeleton)
  - `s1_arrival_entities_6B` (entity attachments)
  - `s2_flow_anchor_baseline_6B` (flow context for baseline traffic)
  - `s3_flow_anchor_with_fraud_6B` (flow context for post-overlay traffic)
- Inputs are read only after required gates pass and the oracle world is sealed and readable.
- Input selection is deterministic and pinned to the oracle world identity (oracle_pack_id or engine_run_root + scenario_id).

2) Output artifacts (platform-owned)
- Write indexed join tables into platform storage (Postgres for v0).
- Optional: write by-ref snapshots of the preloaded context to S3 for audit/debug.
- Emit a deterministic preload receipt (context_ready) containing:
  - oracle world identity
  - input output_ids
  - source digests and row counts
  - a derived context_version hash for idempotency checks

3) Runtime posture
- Runs as a control-plane job (not a streaming service).
- Is safe to re-run and must be idempotent for a given oracle world.
- Does not participate in traffic admission or EB publishing.

### Out of scope (explicit non-goals)

- No traffic production and no EB publishing.
- No truth products (`s4_*`) and no session rollups (`s1_session_index_6B`).
- No mutation of engine outputs or Oracle Store in any form.
- No RTDL decisioning, feature computation, or action execution.
- No attempt to replace SR readiness, IG admission, or WSP streaming responsibilities.

### Platform placement (ASCII overview)

```
Platform-wide flow (simplified):

Oracle Store (engine outputs)
  |  \
  |   \--> Truth products (s4_*) ---------------------------> Label Store / Case Mgmt
  |
  +--> [Context Preloader] --> Platform Context Tables (Postgres, read-only)
                                ^
                                |
Control & Ingress plane         |
  SR READY -> WSP -> IG -> EB --+--> RTDL plane: IEG/OFP -> DF/DL -> AL -> DLA
```

## 2. Authority and boundaries

This component is a control-plane loader. It has narrow authority: to materialize time-safe join context into platform-owned state and to prove what it loaded. It does not own any runtime decisions, offsets, or truth products.

### 2.1 What it owns (authoritative responsibilities)

1) Context preload receipt (context_ready)
- The preloader is the authoritative producer of the context preload receipt for a given oracle world.
- The receipt records world identity, input outputs, digests, row counts, and a derived `context_version` hash.
- Downstream components may treat this receipt as the proof that join context for that world is available.

2) Platform-owned join indexes
- The preloader is responsible for writing and maintaining the join index tables for time-safe surfaces.
- It owns the rule that those tables must be keyed by pins + join keys and be idempotent for a given world.

3) Idempotent load semantics
- For a given oracle world, repeated runs must be no-ops when source digests match.
- If source digests change for the same world identity, the preloader must fail closed and surface a mismatch.

### 2.2 What it does not own (explicit boundaries)

1) Run readiness and scheduling
- Scenario Runner (SR) owns readiness and run selection.
- The preloader does not decide which world is active; it only loads the world SR (or operator policy) points to.

2) Traffic admission and offsets
- Ingestion Gate (IG) owns admission decisions.
- Event Bus (EB) owns offsets and replay semantics.
- The preloader does not publish to EB and does not define offsets.

3) Oracle Store contents
- Engine owns world artifacts.
- Oracle Store is immutable and read-only to the preloader.
- The preloader must not mutate, rewrite, or re-seal engine outputs.

4) RTDL computation
- IEG/OFP/DF/DL/AL/DLA own projection, features, decisions, actions, and audit truth.
- The preloader is not a decision plane component.

5) Truth products and labels
- Label Store owns labels; Case Management owns cases.
- Truth products (`s4_*`) are consumed by the label/case plane, not by the preloader.

### 2.3 Boundary rule (single-line summary)

The preloader owns "context availability," not "runtime truth": it materializes time-safe context into platform state and proves what it loaded, but it never decides readiness, admission, offsets, or outcomes.

## 3. Inputs (allowed surfaces and selection rules)

This section pins exactly what the preloader is allowed to read, how those inputs are selected, and the evidence required before any read occurs.

### 3.1 Allowed input surfaces (time-safe only)

The preloader may read only these Oracle Store outputs:
- `arrival_events_5B` (arrival skeleton used to anchor routing/timezone context)
- `s1_arrival_entities_6B` (entity attachments for the same arrival)
- `s2_flow_anchor_baseline_6B` (flow context for baseline traffic)
- `s3_flow_anchor_with_fraud_6B` (flow context for post-overlay traffic)

These surfaces are treated as "time-safe" because they describe event-local context and do not embed future aggregation or labels.

### 3.2 Explicit exclusions (never read)

The preloader must not read:
- `s1_session_index_6B` (session_end_utc and arrival_count imply future knowledge)
- Any `s4_*` truth products (labels, case timelines, bank views)
- Any audit/ops logs (rng traces, segment journals)
- Any traffic streams (`s2_event_stream_baseline_6B`, `s3_event_stream_with_fraud_6B`)

### 3.3 Identity binding and selection

Inputs are selected strictly by the oracle world identity:
- Preferred identity: `oracle_pack_id` + `scenario_id`
- Fallback identity: `engine_run_root` + `scenario_id` if no pack manifest exists

Selection rules:
- No scanning for "latest" runs.
- No implicit defaulting to local paths.
- If scenario_id is ambiguous or missing, the preload must fail closed.

### 3.4 Evidence and gate verification

No-PASS-no-read applies. Before reading any input:
- Verify required segment HashGates using `engine_gates.map.yaml`.
- Require instance-proof receipts where they exist for instance-scoped outputs.
- If gate evidence is missing or invalid, fail closed and do not preload.

### 3.5 Schema anchoring and drift control

For each input:
- Pin the schema reference (from the engine interface pack/catalogue).
- Record the schema version/digest in the preload receipt.
- Do not coerce fields or auto-cast types. Schema drift must surface as an error.

### 3.6 Required pins and join keys

Inputs must carry ContextPins and join keys:
- Pins: `seed`, `manifest_fingerprint`, `scenario_id` (and `parameter_hash` where present)
- Join keys: as defined in the join map (flow_id, arrival_seq, merchant_id)

`arrival_events_5B` lacks `parameter_hash`; treat `parameter_hash` as run-constant and do not inject it into that surface.

## 4. Outputs (platform-owned artifacts)

This section defines exactly what the preloader writes, where those artifacts live, and how they are identified for replay and audit.

### 4.1 Primary output: join index tables

The preloader writes platform-owned join tables (Postgres for v0) that are:
- keyed by ContextPins + join keys (see Section 5),
- scoped by oracle world identity to prevent cross-world collision,
- immutable for a given world (rewrites must be byte-identical or fail).

These tables are the authoritative runtime lookup surface for RTDL joins.

### 4.2 Optional by-ref snapshots

The preloader may emit by-ref snapshots to the platform object store to provide:
- audit visibility into what was loaded,
- deterministic rehydration if the database must be rebuilt.

Snapshots are read-only artifacts and must never be used directly for RTDL joins (RTDL reads the indexed tables).

### 4.3 Preload receipt (context_ready)

The preloader must emit a deterministic receipt that includes:
- oracle world identity (oracle_pack_id or engine_run_root),
- scenario_id,
- input output_ids,
- source digests + row counts per input,
- derived `context_version` hash,
- timestamp of preload completion.

This receipt is the authoritative proof that join context for the world is available.

### 4.4 Receipt storage

Receipts are stored by-ref under the platform store root and are immutable. The receipt location must be stable and addressable by:
- oracle world identity,
- context_version.

### 4.5 Idempotent re-run behavior

If the preloader is re-run for the same world:
- If input digests match, it must no-op and re-emit the same context_version.
- If digests differ, it must fail closed and surface a mismatch.

## 5. Join semantics (explicit and binding)

This section pins the exact join map and rules for how context is used. These rules are binding for RTDL consumers to prevent ambiguity.

### 5.1 Join order (required)

Joins must follow this order:

1) Event stream -> flow anchor
- Fraud traffic (v0 runtime): `s3_event_stream_with_fraud_6B` joins to `s3_flow_anchor_with_fraud_6B`
  - Keys: `seed`, `manifest_fingerprint`, `scenario_id`, `flow_id`
- Baseline traffic (offline/optional): `s2_event_stream_baseline_6B` joins to `s2_flow_anchor_baseline_6B`
  - Keys: `seed`, `manifest_fingerprint`, `scenario_id`, `flow_id`

2) Flow anchor -> arrival events
- `s2_flow_anchor_baseline_6B` / `s3_flow_anchor_with_fraud_6B` joins to `arrival_events_5B`
  - Keys: `seed`, `manifest_fingerprint`, `scenario_id`, `merchant_id`, `arrival_seq`

3) Arrival events -> arrival entities
- `arrival_events_5B` joins to `s1_arrival_entities_6B`
  - Keys: `seed`, `manifest_fingerprint`, `scenario_id`, `merchant_id`, `arrival_seq`

### 5.2 Key integrity rules

- Join keys must be treated as authoritative; no inference from file order.
- Pins must match exactly; mismatched pins are treated as a join failure.
- `parameter_hash` is run-constant and may be absent from `arrival_events_5B`; it must not be fabricated into that surface.

### 5.3 Time-safety rule (binding)

Only time-safe surfaces are allowed for RTDL joins. Any field or surface that implies future knowledge (session rollups, labels, case truth) is excluded from preload and must not be used in RTDL decisions.

### 5.4 Missing context behavior

If a join lookup is missing:
- The event must be marked with a `context_missing` indicator (or equivalent flag).
- Decisioning must degrade explicitly (no silent bypass).
- Missing context must be observable in metrics and logs.

### 5.5 Join ownership rule

Joins are performed in RTDL components (IEG/OFP/DF) using the preloaded tables. EB does not join or enrich.

## 6. Lifecycle and triggers

This section defines when the preloader runs, what it depends on, and how its completion is surfaced to the rest of the platform.

### 6.1 Triggering sources

The preloader is triggered by control-plane policy after a world is READY. Allowed triggers:
- A control-bus signal that references the oracle pack (SR READY or a dedicated preload request).
- An operator command that supplies an explicit oracle_pack_ref.

It must never run based on "latest run" discovery or scanning.

### 6.2 Ordering relative to traffic

The preloader must complete before RTDL consumes traffic for the same world. Two acceptable orderings:
- Strict: preload completes, context_ready is emitted, then RTDL starts consuming EB.
- Parallel with gate: WSP may stream traffic early, but RTDL must block on context_ready before joining.

### 6.3 Idempotent retries

If a preload job is re-run for the same world:
- It must verify digests and no-op when unchanged.
- It must fail closed if source digests differ.
- It must re-emit the same context_version for identical inputs.

### 6.4 Failure handling

On failure:
- No partial "ready" signal is emitted.
- The failure reason is recorded (missing gates, schema mismatch, digest mismatch).
- RTDL must treat the world as not ready for join context.

### 6.5 Completion signal

The preloader must emit a context_ready receipt (by-ref) and optionally a control-bus signal pointing to that receipt. The receipt is the authoritative signal that join context is available.

## 7. Interaction with Control and Ingress plane

This section clarifies how the preloader relates to SR, WSP, IG, and EB so it doesn't drift into their responsibilities.

### 7.1 Scenario Runner (SR)

- SR remains the sole readiness authority.
- The preloader consumes SR's oracle_pack_ref (or operator-provided equivalent) to identify the oracle world.
- The preloader does not publish READY or modify run_facts_view; it only emits a separate context_ready receipt.

### 7.2 World Streamer Producer (WSP)

- WSP streams traffic only and never emits context surfaces.
- The preloader does not control WSP scheduling or traffic selection.
- If WSP streams before preload completes, RTDL must still gate on context_ready.

### 7.3 Ingestion Gate (IG)

- IG remains the admission boundary for traffic into EB.
- The preloader does not push data through IG.
- The preloader must not reuse IG's receipts; it emits its own context-ready receipt.

### 7.4 Event Bus (EB)

- EB is a durable log for traffic; it does not carry preloaded context.
- The preloader does not publish to EB.
- Any signaling is via control-bus or by-ref receipts only.

## 8. Interaction with RTDL plane

This section pins how RTDL components consume the preloaded context and how provenance is carried forward.

### 8.1 IEG / OFP consumption rules

- IEG and OFP read preloaded join tables directly (Postgres for v0).
- RTDL components must not read Oracle Store for join context.
- The join tables are the only sanctioned runtime context source.

### 8.2 Provenance propagation

- RTDL outputs (graph_version, feature snapshots, decisions) should carry a reference to the preload receipt or its `context_version`.
- This binds decisions to the exact context used, making replay and audit deterministic.

### 8.3 Failure posture

- If context_ready is missing or mismatched, RTDL must fail closed or degrade explicitly.
- No silent fallback to Oracle Store or to "best effort" joins is allowed.

### 8.4 Read isolation

- Preloaded tables are read-only to RTDL components.
- Only the preloader may write or refresh these tables for a given world identity.

## 9. Interaction with Label and Case plane

This section clarifies whether the preloader touches truth products and how label/case tooling should treat preloaded context.

### 9.1 Truth products are out of scope

- Truth products (`s4_*`) are consumed by the label/case plane via their own loaders.
- The preloader must not read, transform, or emit truth products.
- The preloader must never expose labels into RTDL.

### 9.2 Optional reuse of context

- Label or case workflows may read preloaded context tables for enrichment or lookup.
- This is optional and does not change the preloader’s responsibilities.
- Such reuse must remain read-only and must not mutate the preloaded tables.

## 10. Invariants (binding rules)

These rules are non-negotiable and must be enforced by design and by implementation.

1) No-PASS-no-read
- The preloader must verify required HashGates before reading any input.
- Missing or invalid gate evidence must cause a hard failure.

2) No future leakage
- Only time-safe surfaces may be preloaded.
- Session rollups and truth products are excluded from preload and RTDL joins.

3) Idempotency
- Preload runs must be deterministic for a given oracle world.
- Identical inputs must yield identical context_version and identical join tables.

4) No Oracle Store reads in RTDL
- RTDL components must not access Oracle Store for join context.
- The preloaded tables are the only sanctioned runtime source.

5) Pin and key integrity
- ContextPins and join keys must be preserved exactly.
- No silent coercion, key drop, or schema widening is allowed.

6) Explicit degrade on missing context
- Missing joins must be visible and must force explicit degrade posture.

## 11. Storage layout and indexing

This section pins table names, keys, and optional snapshot layout so implementations do not drift.

### 11.1 Table naming (v0)

Suggested Postgres tables:
- `ctx_arrival_events`
- `ctx_arrival_entities`
- `ctx_flow_anchor_baseline`
- `ctx_flow_anchor_fraud`

### 11.2 Primary keys and indexes

Each table must include ContextPins and the join keys in its primary/unique index.

- `ctx_arrival_events`
  - PK: `(seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq)`
- `ctx_arrival_entities`
  - PK: `(seed, manifest_fingerprint, scenario_id, merchant_id, arrival_seq)`
- `ctx_flow_anchor_baseline`
  - PK: `(seed, manifest_fingerprint, scenario_id, flow_id)`
- `ctx_flow_anchor_fraud`
  - PK: `(seed, manifest_fingerprint, scenario_id, flow_id)`

Indexes must support O(1) lookups by join keys under the active world pins.

### 11.3 Optional snapshot layout

If by-ref snapshots are emitted, they must live under the platform store root and be partitioned by oracle world identity:

`<platform_store_root>/context_preloader/oracle_pack_id=<id>/output_id=<output_id>/part-*.parquet`

Snapshots are audit artifacts only and must not be used as runtime join sources.

## 12. Observability and audit

This section defines the minimum logging, metrics, and audit trail required for production readiness.

### 12.1 Required logs

- Preload start/end markers with oracle world identity.
- Input list (output_ids) and gate verification status.
- Row counts and source digests per input.
- Derived context_version hash.
- Failure reason codes (missing gate, schema mismatch, digest mismatch).

### 12.2 Metrics (v0 minimum)

- Rows loaded per output_id.
- Preload duration per output_id and total duration.
- Idempotent skips vs full loads.
- Failure counts by reason.

### 12.3 Audit trail

- The preload receipt is the authoritative audit record.
- Receipts are immutable, append-only, and stored by-ref.
- A platform run may reference the receipt to prove join context availability.
