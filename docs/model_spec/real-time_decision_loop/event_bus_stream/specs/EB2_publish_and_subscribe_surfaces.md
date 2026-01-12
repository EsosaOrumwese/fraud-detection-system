# EB2 - Publish and Subscribe Surfaces (v0)

## 0) Document metadata

* Status: Draft
* Version: v0
* Date (UTC): 2026-01-11

---

## 1) Purpose

Define the v0 publish and subscribe surfaces for the Event Bus (EB), including required fields, publish acknowledgments, delivery wrappers, and checkpoint semantics.

---

## 2) In-scope

* PublishRecord required fields and content posture.
* PublishAck shape and semantics.
* DeliveredRecord shape and delivery posture (at-least-once).
* Checkpoint representation and semantics (offset meaning + authority).
* Contract linkage to `contracts/eb_public_contracts_v0.schema.json`.

Out of scope: implementation transport, batching mechanics, and durability standard beyond "durable append + assigned position."

---

## 3) Publish surface (v0)

### 3.1 Required fields

PublishRecord MUST include:

* `kind = "publish_record"`
* `contract_version = "eb_public_contracts_v0"`
* `stream_name`
* `partition_key`
* `event_bytes_b64` (base64 of immutable canonical event bytes)

Optional fields:

* `publisher_id`
* `submitted_at_utc`

### 3.2 Publish ACK semantics

PublishAck is returned only after durable append completes and the assigned position is stable:

* `kind = "publish_ack"`
* `contract_version = "eb_public_contracts_v0"`
* `stream_name`
* `partition_id`
* `offset`
* `published_at_utc` (timestamp when durable append + position assignment completed)

Durability standard details (fsync/replication level) remain an open decision (DEC-EB-001).

### 3.3 Validation posture

* Missing required fields -> reject publish (do not append).
* EB does not mutate `event_bytes_b64`.
* EB does not compute `partition_key`.

---

## 4) Subscribe / delivery surface (v0)

DeliveredRecord includes bus metadata plus the immutable event content:

* `kind = "delivered_record"`
* `contract_version = "eb_public_contracts_v0"`
* `stream_name`
* `partition_id`
* `offset`
* `published_at_utc`
* `event_bytes_b64`
* `partition_key` (optional echo)

Delivery posture:

* at-least-once (duplicates possible)
* ordering guaranteed within a partition only

---

## 5) Checkpoint semantics (v0)

Checkpoint shape:

* `kind = "consumer_checkpoint"`
* `contract_version = "eb_public_contracts_v0"`
* `consumer_group`
* `stream_name`
* `partition_id`
* `offset` (next offset to read, exclusive)
* `updated_at_utc`

Checkpoint ownership remains open (EB-owned vs consumer-owned), but the checkpoint is the authoritative progress token for replay/rewind semantics.

---

## 6) Contract source of truth

All shapes above are defined in:

* `docs/model_spec/real-time_decision_loop/event_bus_stream/contracts/eb_public_contracts_v0.schema.json`

Pinned v0 `kind` values (lower_snake_case):

* `publish_record`
* `publish_ack`
* `delivered_record`
* `consumer_checkpoint`
* `replay_request`

---

## 7) Open decisions

* DEC-EB-001: durability standard implied by PublishAck.
* DEC-EB-002: batch publish posture (if any).
* DEC-EB-006: checkpoint ownership posture.
* DEC-EB-007: redelivery trigger details.
