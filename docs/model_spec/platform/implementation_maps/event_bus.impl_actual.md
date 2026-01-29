# Event Bus (EB) Implementation Map (Actual)
_Living decision trail and execution log_

---

## Entry: 2026-01-29 02:23:10 — EB v0 build plan drafted (streaming‑only alignment)

### Why now
- WSP → IG streaming path is green for local smoke; next vertex is EB.
- Legacy pull is retired; EB must be planned for **IG‑only ingress** and **canonical envelope** semantics.

### Thinking trail (live reasoning)
- EB is opaque but its **join semantics** are the platform’s spine: IG must only emit admitted facts and EB must ACK only after durable append.
- We need a **connected v0**: local file‑bus should be correct and replayable before any dev/prod adapter (Kinesis).
- Local smoke must be bounded (cap events) but still prove “append + offsets + replay”.
- EB v0 can ship without full retention/archival machinery; those belong in v1+.

### Decisions captured in the plan
- **Phased approach**: contracts → local file‑bus durability → replay utilities → IG publish hardening → dev adapter parity.
- **Environment ladder**: local = file‑bus smoke; dev = Kinesis/LocalStack; prod = managed streaming (future).
- **Offsets**: file‑bus offsets are integers; Kinesis offsets may be strings (sequence numbers).

### Artifact created
- New build plan: `docs/model_spec/platform/implementation_maps/event_bus.build_plan.md`

### Next actions (when implementation begins)
- Implement Phase 1/2 components with explicit ACK semantics.
- Add local tail/replay tooling and smoke tests.
- Wire IG publish receipts to include EB refs.

## Entry: 2026-01-29 02:28:20 — v0 EB decisions locked

### What was open
- Partitioning profile, offset type, checkpoint store.

### Decisions locked (v0)
- **Partitioning:** local uses a single partition; dev uses IG‑chosen deterministic key (merchant_id → event_id fallback).
- **Offset type:** store `offset` as string with `offset_kind` to support file‑bus and Kinesis without changing receipt shape.
- **Checkpoint store:** local file checkpoints; dev Postgres.

### Update applied
- `docs/model_spec/platform/implementation_maps/event_bus.build_plan.md` updated to replace “open decisions” with locked v0 choices.

---

## Entry: 2026-01-29 02:36:40 — Phase 1 detailed plan (EB contracts + interface)

### Problem framing (what Phase 1 must solve)
We need a **stable EB boundary contract** and an **EB adapter interface** so IG can publish admitted facts without binding to a specific backend. This is the foundation for v0 local file‑bus and later dev Kinesis parity.

### Live reasoning trail
- EB is opaque, but **its boundary contract is not**: IG receipts must encode the EB position returned on append. That position becomes the replay token for all downstream consumers.
- Existing `ingestion_receipt.schema.yaml` already has `eb_ref`, but it assumes integer offsets (file‑bus only). We need a shape that can carry Kinesis sequence numbers without breaking receipt schema later.
- If EB interface code lives inside IG, EB becomes “owned by IG” in the codebase, which conflicts with the graph view. Better to move the interface to a shared `event_bus` module and have IG depend on it.

### Decisions to lock in Phase 1
1) **Receipt shape update (offset as string)**
   - Keep `partition_id` as integer.
   - Store `offset` as string and add `offset_kind` to distinguish `file_line` vs `kinesis_sequence`.
   - Reason: avoid a future breaking schema change when adding Kinesis.

2) **EB interface location**
   - Recommended: create `src/fraud_detection/event_bus/` module and move `EbRef` + `EventBusPublisher` there.
   - IG should import EB interface from this shared module; file‑bus stays as a local adapter implementation.
   - Alternative: keep in IG; rejected because it blurs component ownership and will be harder to share with future consumers.

### Exact Phase 1 steps (intended edits)
1) **Contracts**
   - Update `docs/model_spec/platform/contracts/ingestion_gate/ingestion_receipt.schema.yaml`:
     - `eb_ref.offset` → string
     - add `eb_ref.offset_kind` enum: `file_line | kinesis_sequence`
   - Add EB contracts folder `docs/model_spec/platform/contracts/event_bus/` with at least:
     - `eb_ref.schema.yaml` (optional re‑usable EB ref schema for other contracts)
   - Update `docs/model_spec/platform/contracts/README.md` to list EB contracts.

2) **Code interface**
   - New module `src/fraud_detection/event_bus/publisher.py` (or similar): `EbRef`, `EventBusPublisher` protocol.
   - Move file‑bus implementation out of IG (`FileEventBusPublisher`), or re‑export it from EB module for local use.
   - Update IG imports to use the new EB module.

3) **Receipt writing**
   - When EB returns a ref, IG receipts should include `offset_kind`.
   - Default for file‑bus: `offset_kind=file_line` and `offset` = stringified line index.

4) **Tests / validation**
   - Update IG receipt schema validation tests (if any) to accept string offset + offset_kind.
   - Add unit test for `EbRef` serialization if needed.

### Invariants to enforce in Phase 1
- EB ACK always includes `topic`, `partition_id`, `offset`, `offset_kind`.
- IG never returns `ADMIT` without an EB ACK.
- Receipt schema change is backward compatible for local file‑bus and forward compatible for Kinesis.

### Open questions (confirmation needed)
- Confirm moving EB interface to `src/fraud_detection/event_bus/` is acceptable.
- Confirm `offset` stored as string with `offset_kind` (v0 lock).

### Validation plan (Phase 1)
- Schema validation of `ingestion_receipt` passes with new `eb_ref` shape.
- IG smoke path still writes receipts after EB ACK.
