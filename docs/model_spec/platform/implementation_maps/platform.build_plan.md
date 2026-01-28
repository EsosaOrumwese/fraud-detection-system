# Platform Build Plan (v0)
_As of 2026-01-24_

## Purpose
Provide a platform-wide, production-shaped build plan for v0 that aligns component sequencing to the platform blueprint and truth-ownership doctrine. This plan is intentionally high-level and **progressively elaborated**: phases are pinned now; detailed steps are added only when a phase begins.

## Planning rules (binding)
- **Progressive elaboration:** start with Phase 1..Phase X; expand only the active phase into sections and DoD checklists as we enter it.
- **No half-baked phases:** do not advance until the phase DoD is fully satisfied and validated.
- **Rails first:** ContextPins, canonical envelope, no-PASS-no-read, by-ref refs, idempotency, append-only truth, deterministic registry resolution, explicit degrade posture.
- **Engine is a black box:** interface pack is the boundary; never reach into engine internals unless explicitly requested.

## v0 scope boundaries (expectations)
- Single-tenant, single-region, production-shaped semantics.
- Local/dev parity with the same rails (different operational envelope only).
- Minimal viable hot path with correct provenance and audit; no scale optimizations beyond correctness.
- No multi-region DR, no automated rollout gates beyond documented policy profiles.

## Phase plan (v0)

### Phase 1 — Platform substrate + rails
**Intent:** pin the shared rails and the local production-shaped substrate so every component implements the same semantics.

#### Phase 1.1 — Identity + envelope contracts
**Goal:** make the platform’s join semantics unambiguous and versioned.

**DoD checklist:**
- Canonical envelope fields are pinned and versioned (including `ts_utc`, `event_type`, `event_id`, `schema_version`, `manifest_fingerprint` + optional pins).
- ContextPins are pinned as `{scenario_id, run_id, manifest_fingerprint, parameter_hash}` and `seed` is treated as a separate, required field when seed‑variant.
- Time semantics are pinned (domain `ts_utc`, optional `emitted_at_utc`, ingestion time in IG receipts).
- Naming/alias mapping for any legacy fields is documented (no hidden drift).

#### Phase 1.2 — By‑ref artifact addressing + digest posture
**Goal:** pin how artifacts are referenced and verified across components.

**DoD checklist:**
- Platform object‑store prefix map is pinned (bucket + prefixes for SR/IG/DLA/Registry/etc.).
- Locator schema and digest posture are pinned (content digest, bundle manifest digest rules).
- Instance‑proof receipts path conventions are pinned (engine vs SR verifier receipts).
- Token order rules are pinned for partitioned paths (seed → parameter_hash → manifest_fingerprint → scenario_id → run_id → utc_day).

#### Phase 1.3 — Event bus taxonomy + partitioning rules
**Goal:** prevent drift on how traffic/control/audit are separated and replayed.

**DoD checklist:**
- Topic taxonomy pinned (traffic/control/audit minimum).
- Partitioning key rules pinned (deterministic, stable across envs).
- Replay semantics and retention expectations documented (v0 scope).

#### Phase 1.4 — Environment ladder profiles (policy vs wiring)
**Goal:** ensure local/dev/prod share semantics but differ in operational envelope only.

**DoD checklist:**
- Local/dev/prod profile schema pinned with clear separation between **policy config** and **wiring config**.
- Policy config is versioned and referenced by revision in receipts/outcomes where applicable.
- Promotion concept documented as profile change, not code change.
- Testing policy pinned: **local = smoke**, **dev = completion** (uncapped).

#### Phase 1.5 — Security + secrets posture
**Goal:** prevent provenance drift and avoid credential leakage.

**DoD checklist:**
- Secrets are runtime‑only; no secrets in artifacts, build plans, impl_actual, or logbooks.
- Provenance records use secret identifiers only (if needed), never secret material.
- Sensitive runtime artifacts are flagged to the user for review/quarantine.

### Phase 2 — World Oracle + Stream Head (Oracle Store + WSP)
**Intent:** establish the sealed world boundary and the primary stream producer so the platform experiences bank‑like temporal flow.

#### Phase 2.1 — Oracle Store contract (sealed world boundary)
**Goal:** define immutable, by‑ref engine outputs as a first‑class platform boundary.

**DoD checklist:**
- Oracle Store prefix layout is pinned (local/dev/prod) with an explicit `oracle_root` that is runtime‑configurable.
- Immutability rules are explicit: sealed runs are write‑once; no overwrite in place.
- Locator + digest posture is pinned (content digest required; schema versioned).
- Oracle Store paths are referenced by SR `run_facts_view` only (no scanning; by‑ref only).

#### Phase 2.2 — WSP v0 stream head (primary runtime producer)
**Goal:** WSP streams engine business_traffic into IG under READY + run_facts_view.

**DoD checklist:**
- WSP consumes READY + `run_facts_view` and derives a StreamPlan (no “latest” scans).
- Only `business_traffic` is streamed; other roles remain by‑ref.
- Canonical envelope framing is enforced; event identity is stable and compatible with legacy pull framing where required.
- **Speedup factor is available in all envs** as a policy knob (semantics preserved across speeds).
- WSP never writes directly to EB; IG remains the only writer.

#### Phase 2.3 — WSP ↔ IG smoke path
**Goal:** prove WSP → IG admission under rails before refactoring SR/IG for full alignment.

**DoD checklist:**
- WSP streams a READY‑scoped run into IG with pass/fail evidence respected (no‑PASS‑no‑read).
- IG receipts reflect ADMIT/DUPLICATE/QUARANTINE outcomes with by‑ref evidence.

### Phase 3 — Control & Ingress plane alignment (SR + IG + EB)
**Intent:** align SR/IG/EB with the WSP‑first runtime truth and preserve rails.

#### Phase 3.1 — Scenario Runner readiness authority (SR)
**Goal:** SR remains the sole readiness authority and publishes the join surface that WSP/IG follow.

**DoD checklist:**
- SR publishes `run_facts_view` + READY with required PASS evidence and pins.
- READY is emitted only after evidence completeness (no PASS → no read).
- SR run ledger artifacts are immutable and append‑only (run_plan/run_record/run_status/run_facts_view).
- Reuse path is evidence‑based (locators + receipts), never “scan latest.”
- `run_facts_view` declares `traffic_delivery_mode` so WSP and IG do not both ingest.

**Status:** ready to proceed to IG; path‑alignment follow‑up noted (see platform.impl_actual).

#### Phase 3.2 — Ingestion Gate admission boundary (IG)
**Goal:** IG is the sole admission authority; push ingestion is primary; legacy pull remains optional/backfill.

**DoD checklist:**
- IG validates canonical envelope + payload schema (versioned) and enforces ContextPins when required.
- IG verifies required HashGates before admitting traffic.
- IG emits receipts with decision (ADMIT/DUPLICATE/QUARANTINE) and by‑ref evidence.
- IG stamps deterministic `partition_key` using policy profiles.

#### Phase 3.3 — Event Bus durability + replay (EB)
**Goal:** EB is the durable fact log with stable offsets and at‑least‑once delivery.

**DoD checklist:**
- EB append ACK implies durable `(stream, partition, offset)` assignment.
- Replay by offsets works with partition‑only ordering semantics.
- Idempotent publish and dedupe semantics are validated under retry.

#### Phase 3.4 — Control & Ingress E2E proof
**Goal:** demonstrate end‑to‑end READY → WSP stream → IG admission → EB replay under rails.

**DoD checklist:**
- SR READY → WSP streams → IG admits → EB replay works for pinned run.
- Truth ownership enforced: SR readiness authority; IG admission authority; EB offsets/replay only.

### Phase 4 — Hot-path decision loop (IEG/OFP/DL/DF/AL/DLA)
**Intent:** turn admitted traffic into decisions and outcomes with correct provenance and audit.

**Definition of Done (DoD):**
- IEG projector builds graph projection with watermark-based graph_version.
- OFP builds feature snapshots with input_basis + snapshot hash; serves deterministic responses.
- DL computes explicit degrade posture and DF enforces it (no silent bypass).
- DF resolves bundles deterministically from Registry and emits decisions + action intents with provenance (bundle ref, snapshot hash, graph_version).
- AL executes intents effectively-once with idempotency and emits outcomes.
- DLA writes append-only audit records by-ref and supports lookup via refs.
- E2E: admitted event -> decision -> action outcome -> audit record with replayable provenance.

### Phase 5 — Label & Case plane
**Intent:** crystallize outcomes into authoritative label timelines and case workflows.

**Definition of Done (DoD):**
- Label Store supports append-only timelines with as-of queries (effective vs observed time).
- Case management backend can open/advance/close cases and emit label assertions.
- Engine 6B truth/bank-view/case surfaces can be ingested via IG into Label Store.
- E2E: action outcome + case event -> label timeline update visible to learning plane.

### Phase 6 — Learning & Registry plane
**Intent:** create deterministic learning loop with reproducible datasets and controlled deployment.

**Definition of Done (DoD):**
- Offline Feature Plane rebuilds feature snapshots from EB/archive using the same schemas.
- DatasetManifest format pinned and used for training inputs (replay basis + label as-of).
- Model Factory produces bundles with evidence (metrics + lineage) and publishes to Registry.
- Registry resolves ACTIVE bundle deterministically and rejects incompatible bundles.
- E2E: decision audit + labels -> dataset manifest -> model bundle -> registry resolution -> DF uses ref.

### Phase 7 — Observability & Governance hardening
**Intent:** make behavior visible, safe to change, and auditable across planes.

**Definition of Done (DoD):**
- OTel-aligned metrics/logs/traces for SR/IG/DF/AL/DLA/OFP/IEG with ContextPins tags.
- Golden-signal dashboards and corridor checks for control/decision/label/learning planes.
- Governance facts emitted for policy changes, backfills, promotions, and readiness failures.
- Policy revision stamps are recorded on receipts/decisions/outcomes where applicable.
- Kill-switch / degrade ladder triggers are wired and tested end-to-end.

## v1 expectations (beyond v0)
- Multi-tenant and multi-world concurrency with stronger isolation.
- HA + autoscaling for hot-path services; replay/DR runbooks with proven RPO/RTO.
- Archive tier for long-horizon replay + backfill orchestration.
- Automated policy gates for registry promotion and schema acceptance.
- Deeper model lifecycle: shadow/canary/ramp automation with guardrails.

## vX possibilities (future horizons)
- Cross-region active/active with deterministic registry resolution.
- Advanced explainability and model governance workflows.
- Federated label sources + privacy-preserving training workflows.
- Multi-bus / multi-domain expansion (fraud + risk + compliance) under shared rails.

## Status (rolling)
- Phase 1: complete (rails + substrate pins + validation + profiles).
- Phase 2: ready to begin (Oracle Store + WSP).
- SR v0: complete (see `docs/model_spec/platform/implementation_maps/scenario_runner.build_plan.md`); alignment to WSP truth pending under Phase 3.
