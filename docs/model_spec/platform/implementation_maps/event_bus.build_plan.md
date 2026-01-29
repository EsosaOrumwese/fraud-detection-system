# Event Bus (EB) Build Plan — v0 (Hardened + Connected)
_As of 2026-01-29_

This plan is written for the **streaming‑only platform** (WSP → IG → EB). Legacy pull is retired and ignored.

---

## 0) Scope + intent

**v0 goal:** Provide a **durable, append‑only fact log** that accepts only **IG‑admitted canonical envelopes**, publishes stable positions, and can be replayed by downstream consumers. v0 is **connected** (IG→EB works end‑to‑end) and **hardened** (append/ACK semantics and offsets are deterministic, logs are auditable, and failure modes are explicit).

**Non‑goals for v0:**
- Full retention/archival subsystem (documented in EB design authority; defer to v1+).
- Full consumer coordination (lease groups, rebalance, etc.) beyond a minimal replay/tail mechanism for local verification.

---

## 1) Pins (binding)

These are copied from the EB design‑authority and are treated as **laws**:
- EB contains **only admitted facts** (post‑IG).
- **ACK == durable append + stable position** (`partition_id, offset`).
- Delivery is **at‑least‑once**; **ordering is partition‑only**.
- EB does **not** validate/transform envelopes; canonicality is IG’s boundary.
- EB does **not** dedupe; duplicates can exist.
- **Checkpoints are exclusive‑next offsets**.
- Partitioning is **owned by IG**; EB does not infer domain routing.

---

## 2) Environment ladder (v0 posture)

**Local (v0 smoke):**
- File‑based append‑only bus in `runs/fraud-platform/event_bus/...`
- Single partition default (partition=0) to keep behavior deterministic.
- Fast feedback; cap WSP events for smoke.

**Dev (v0 completion):**
- Kinesis via LocalStack or real AWS.
- Same canonical envelope and routing semantics.
- Use real offsets/sequence numbers in EB receipts.

**Prod (future v1+):**
- Managed Kinesis / Kafka with retention + archive continuation.

---

## 3) Phase plan (progressive elaboration)

### Phase 1 — EB contracts + adapter interface (foundation)

**Design intent:** Define the minimal “EB surface” that IG can depend on without binding to a specific backend.

**Plan:**
1. **EB publish receipt contract**
   - Define `EbRef` fields: `topic`, `partition_id`, `offset`, optional `published_at_utc`.
   - Document that offsets are **exclusive‑next** for checkpoints.
2. **Adapter interface**
   - `EventBusPublisher.publish(envelope, partition_key) -> EbRef`
   - `EventBusReader.read(from_position, max_records)` for local inspection.
3. **Topic class map**
   - Traffic/control/audit topics bound to `partitioning_profile_id` in IG policy.
4. **Schema anchor**
   - EB consumes only **Canonical Event Envelope**; EB does not re‑validate.

**DoD checklist:**
- EB interface documented.
- Canonical envelope is referenced (not redefined) by EB.
- IG publish path uses the EB interface (no embedded backend logic).

---

### Phase 2 — Local file‑bus implementation (durable append)

**Design intent:** Provide a correct local bus with deterministic offsets and explicit ACK semantics.

**Plan:**
1. **Append‑only log layout**
   - `runs/fraud-platform/event_bus/<topic>/partition=0.jsonl`
2. **Stable offsets**
   - Offset is line index (0‑based) of the append.
3. **Atomic append**
   - Open‑append‑flush‑fsync (best‑effort on Windows).
4. **Receipt binding**
   - IG admits only after EB ACK; EB returns `EbRef` on successful append.
5. **Tests**
   - Monotonic offsets.
   - Concurrent publish ordering (single process).
   - Idempotent retry produces duplicates but preserves order.

**DoD checklist:**
- File bus publishes and returns monotonic offsets.
- IG receipt includes EB ref for admitted events.
- Local smoke run emits and reads back records.

---

### Phase 3 — Replay/tail utilities (connected verification)

**Design intent:** Enable local/CI verification that EB is durable + replayable without full consumer stack.

**Plan:**
1. **Reader utility**
   - Minimal CLI: `event_bus tail --topic ... --from-offset ... --max ...`
2. **Checkpoint semantics**
   - “exclusive‑next” stored in `runs/fraud-platform/event_bus/checkpoints/...`
3. **Smoke verification**
   - Tail the last N records after a WSP smoke run.

**DoD checklist:**
- Can read back a deterministic subset using offsets.
- Checkpoint files round‑trip correctly.

---

### Phase 4 — IG integration hardening (connected v0)

**Design intent:** Ensure IG→EB is the single write path with explicit failure modes.

**Plan:**
1. **Partitioning decision**
   - IG stamps partition key based on `partitioning_profile_id`.
2. **Publish failure handling**
   - If publish fails, IG returns retry/temporary failure (no “admitted”).
3. **Receipt content**
   - Receipt must include EB ref and publish timestamp.
4. **Metrics**
   - Publish latency, publish failure counts, offset head per topic.

**DoD checklist:**
- “Admitted” occurs only when EB ACK exists.
- Publish failures are explicit and logged.
- Platform log shows IG admitted → EB offset.

---

### Phase 5 — Dev adapter (Kinesis/LocalStack parity)

**Design intent:** v0 parity across local/dev without changing semantics.

**Plan:**
1. **Kinesis publisher adapter**
   - Partition key → Kinesis partition key.
   - Use sequence number as EB offset (string).
2. **LocalStack smoke**
   - Publish + read a short batch (cap).
3. **Config**
   - `event_bus_kind: kinesis` in `config/platform/profiles/dev_local.yaml`.

**DoD checklist:**
- Kinesis adapter passes smoke test.
- Same envelope and receipt shape across file/Kinesis.

---

## 4) Validation strategy (v0)

**Local smoke (fast):**
- `make platform-smoke` (SR→WSP→IG→EB)
- Tail last 20 events from EB file‑bus log.

**Dev completion (uncapped):**
- Kinesis adapter publishes without schema drift.
- Replay from a known offset reproduces the same N events.

---

## 5) Locked decisions (v0)

1. **Partitioning profile**
   - **Local:** single partition (`partition=0`) for deterministic smoke runs.
   - **Dev (v0):** deterministic hash key chosen by IG (default key = `merchant_id` when present, else `event_id`).
2. **Offset type**
   - `partition_id`: integer
   - `offset`: stored as **string** in receipts to allow file‑bus integers and Kinesis sequence numbers without shape changes.
   - `offset_kind`: `file_line` or `kinesis_sequence`.
3. **Checkpoint store**
   - **Local:** file checkpoints under `runs/fraud-platform/event_bus/checkpoints/...`
   - **Dev (v0):** Postgres (reuse existing local/dev Postgres footprint).

---

## 6) Status (v0)

- Phase 1: **planned**
- Phase 2: **planned**
- Phase 3: **planned**
- Phase 4: **planned**
- Phase 5: **planned**
