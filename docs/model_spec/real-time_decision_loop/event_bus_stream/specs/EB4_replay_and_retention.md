# EB4 - Replay and Retention (v0)

## 0) Document metadata

* Status: Draft
* Version: v0
* Date (UTC): 2026-01-11

---

## 1) Purpose

Define v0 replay semantics (offset and time) and retention posture for the Event Bus (EB), including boundary rules and behavior on retention expiry.

---

## 2) Replay semantics (v0)

### 2.1 Replay definition

Replay is re-delivery of stored events; it does not recompute or rewrite history.

### 2.2 Replay request shape

ReplayRequest is defined in:

* `docs/model_spec/real-time_decision_loop/event_bus_stream/contracts/eb_public_contracts_v0.schema.json`

Required core fields:

* `kind = "replay_request"`
* `contract_version = "eb_public_contracts_v0"`
* `stream_name`
* `requested_at_utc`

One of:

* `from_offset` (offset-based replay), or
* `from_time_utc` (time-based replay)

Optional fields:

* `partition_id` (if omitted, replay applies to all partitions; no cross-partition ordering is implied)
* `to_offset` or `to_time_utc`
* `replay_group` or `consumer_group`
* `time_basis` (v0: `bus_published_at_utc`)
* `precision` (`exact` or `best_effort`)

### 2.3 Boundary rules (CLOSED)

Replay ranges are half-open:

* offsets: `[from_offset, to_offset)` when `to_offset` is provided
* times: `[from_time_utc, to_time_utc)` when `to_time_utc` is provided

If no end bound is provided, replay continues until the latest available offset within retention.

### 2.4 Time-based replay basis

Time-based replay (if supported) maps `from_time_utc` / `to_time_utc` to offsets using `published_at_utc` (bus time). Precision is declared via the `precision` field.

---

## 3) Retention posture (v0)

* Retention bounds what can be replayed.
* Replay requests beyond retention must fail or degrade explicitly (never silent omission).
* v0 compaction posture: no compaction unless explicitly chosen later.

---

## 4) Open decisions

* DEC-EB-009: time-based replay support (v0?) and precision guarantees.
* DEC-EB-010: replay mechanism posture (new consumer group vs checkpoint rewind).
* DEC-EB-011: retention policy concept (time/size) and operator guarantees.
* DEC-EB-012: compaction posture (if ever allowed beyond v0).
