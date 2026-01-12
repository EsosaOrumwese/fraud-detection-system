# IEG2 - Entity, Identifier, and Edge Model (v0)

## 0) Document metadata

* Status: Draft
* Version: v0
* Date (UTC): 2026-01-11

---

## 1) Purpose

Pin the v0 entity/identifier/edge model and vocabularies for the IEG query boundary.

---

## 2) Entity model (v0)

### 2.1 Entity types (fixed enum)

* `account`
* `card`
* `customer`
* `merchant`
* `device`

### 2.2 EntityRef

* Shape: `{entity_type, entity_id}`
* `entity_id` is deterministically minted within ContextPins.
* Encoding format is an open decision (DEC-IEG-002), but determinism across replay is mandatory.

### 2.3 EntityRecord (thin)

* Required: `entity_ref`
* Optional: `attributes` (opaque), `as_of_event_time` (RFC3339/ISO8601, timezone-aware, prefer `Z`)

---

## 3) ObservedIdentifier model (v0)

* Required: `id_kind`, `id_value`
* Optional: `namespace` / `issuer`
* Used for alias/link creation and identity resolution; no payload parsing in v0.

---

## 4) Alias/link posture (v0)

* ObservedIdentifier → EntityRef links only (no merges).
* Links are attributable via provenance_ref on edges or alias metadata (details pinned in IEG4/DEC-IEG-008).

---

## 5) Edge model (v0)

### 5.1 Edge types (fixed enum)

* `account__has_card`
* `card__seen_on_device`
* `customer__has_account`
* `customer__seen_at_address`
* `merchant__operates_site`

### 5.2 EdgeRecord invariants

* Uniqueness key: `(src_entity_id, dst_entity_id, edge_type)`
* `first_seen_event_time` / `last_seen_event_time` use RFC3339/ISO8601 timestamps (timezone-aware, prefer `Z`)
* `provenance_ref` is an opaque pointer to the causing admitted event (form pinned later)

---

## 6) Contract source of truth

Shapes live in:

* `docs/model_spec/real-time_decision_loop/identity_entity_graph/contracts/ieg_public_contracts_v0.schema.json`
