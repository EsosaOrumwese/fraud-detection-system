# Oracle Store Design Authority

This file is a rough collection of **design / brainstorm notes** for the **Oracle Store** (sealed world boundary). It treats the platform as a **network** and expands open the Oracle Store’s position so later implementation can’t drift.

Everything below is **design-authoritative** for Oracle Store unless it conflicts with platform‑wide pins (those still win).

---

## 1) What Oracle Store is (one sentence)

**Oracle Store is the sealed, immutable world boundary for engine outputs**: a by‑ref artifact store that the platform can *reference* but never rewrite.

---

## 2) Where Oracle Store sits in the graph

Oracle Store is **outside** the runtime hot path. It is a **boundary** (storage + locators), not a producer and not a bus.

Runtime flow stays:

`SR (READY + run_facts_view) → WSP → IG → EB → …`

Oracle Store is the **by‑ref world source** that SR and WSP point to via locators.

---

## 3) Authority boundary (what Oracle Store owns vs does not own)

### Oracle Store owns
- **Immutability** of sealed runs (write‑once, no overwrite).
- **Locator + digest contract** for by‑ref access.
- **Environment ladder layout** (local/dev/prod roots + prefixes).

### Oracle Store does not own
- **Run readiness** (SR owns READY + run_facts_view).
- **Admission** (IG decides ADMIT/DUPLICATE/QUARANTINE).
- **Streaming** (WSP reveals traffic; Oracle Store never emits events).

---

## 4) Non‑negotiable invariants

1. **Write‑once sealed runs** — no in‑place overwrite after sealing.
2. **By‑ref only** — consumers read by locator + digest; no payload copies.
3. **No scanning for “latest”** — SR join surface is the only entrypoint.
4. **Fail‑closed** — missing/invalid digest or evidence means reject/quarantine.

---

## 5) Environment ladder (v0)

### Local (v0 default)
- **oracle_root:** `runs/local_full_run-5` (temporary, configurable)
- Each engine run is a sealed folder under this root.
- Long‑term target: `runs/data-engine/` (same contract, different path).

### Dev / Prod
- **S3‑compatible bucket** (MinIO for dev parity, AWS S3 for prod).
- Suggested prefix:
  - `s3://fraud-platform-oracle/<env>/engine_runs/<run_id>/...`

**Important:** path **location** is wiring; **contract** (immutability + by‑ref) is policy.

---

## 6) How Oracle Store is consumed

Oracle Store is never scanned directly by downstream. The only legal flow:

1. SR seals `run_facts_view` with locators + evidence refs.
2. WSP reads those locators to stream `business_traffic`.
3. Legacy IG pull (if enabled) uses the same locators (no ad‑hoc discovery).

---

## 7) Non‑goals

- Not a streaming system.
- Not a query service.
- Not a mutable datastore.

Oracle Store is **only** a sealed by‑ref world boundary.

