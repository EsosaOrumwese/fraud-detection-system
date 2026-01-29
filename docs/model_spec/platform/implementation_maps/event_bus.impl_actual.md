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
