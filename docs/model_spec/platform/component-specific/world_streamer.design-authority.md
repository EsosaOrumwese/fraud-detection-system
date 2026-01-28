# World Streamer (WS) Design Authority

This file pins the design intent for the **World Streamer (WS)** — the inlet vertex that turns sealed engine outputs into a **temporal stream** of canonical events for the platform hot path.

---

## 1) What WS is (one idea)

WS is the **banking‑world feeder**: it reads a sealed world from storage (engine outputs), and **releases events over time** into IG’s **push** admission boundary. It exists so the platform experiences the world as a **stream**, not as a batch.

Think of WS as the “clocked bridge” between:

* **SR’s READY + run_facts_view** (join surface), and
* **IG push ingest** (trust boundary).

WS does **not** make decisions about readiness or admission; it only **frames** and **schedules** events already declared admissible by SR.

---

## 2) WS’s single most important platform pin

**WS never decides what world to stream.**
It streams only what SR declares admissible via `run_facts_view` + READY.

If WS streams anything outside SR’s join surface, it is a **platform breach**.

---

## 3) Inputs, outputs, and joins (authoritative)

### Inputs (must be by‑ref)
- **READY control signal** from SR (control bus).
- **`sr/run_facts_view/{run_id}.json`** (the join surface).

### Outputs
- **Canonical envelope events** pushed into IG (push ingress), never directly to EB.
- **WS checkpoints** (durable) to resume streaming after restart.

### Join logic
- WS reads `run_facts_view` and **streams only outputs** whose role is `business_traffic`.
- WS reads **only the locators** in the facts view. It does not infer or scan engine directories.

---

## 4) WS boundaries (what it must NOT become)

WS must **not**:
- invoke the engine,
- bypass IG and publish to EB,
- change SR readiness or evidence,
- invent or infer outputs beyond SR’s declared locators,
- act as a policy engine (schema policy and admission remain in IG).

---

## 5) Invariants WS cannot violate

### A) No‑future‑leak
WS must **not emit events past the release frontier**. Future events remain sealed.

### B) By‑ref only
WS reads by reference (locators + refs) and **never copies** SR or engine truths into its own authority surface.

### C) Idempotent under replay
WS must be safe under duplicates and restarts. Checkpoints are **append‑only** and monotonic.

### D) IG is the only admission boundary
Every WS event **must** go through IG push ingress. EB is never a WS target.

### E) Temporal ordering is explicit
WS emits with explicit `ts_utc` and respects a monotonic **release frontier**.

---

## 6) Time semantics (the core of WS)

WS simulates a live bank feed by enforcing a **release frontier**:

- **Frontier definition:** the latest simulated timestamp that is allowed to be released.
- **Scheduling modes:**
  - **Wall‑clock:** 1:1 mapping (real time).
  - **Accelerated:** `sim_time = start + (wall_elapsed * speed_factor)`.

Events are released in **temporal order** (per output_id), subject to the frontier.

---

## 7) Checkpoint truth (durable resume)

WS persists checkpoints keyed by:
- `run_id`, `output_id`, `file/shard`, `cursor` (row‑group/batch), and `frontier_ts_utc`.

Checkpoint store is **authoritative** and must be durable:
- Preferred: **Postgres** (simple, durable, queryable).
- Local fallback: object‑store JSONL (only for local dev if Postgres unavailable).

Checkpoints are append‑only and **monotonic**.

---

## 8) Failure posture

WS is a **producer**. On failure it must:
- **pause and retry** (with bounded backoff), or
- **stop the stream** and surface a clear operator signal.

WS must **not** silently skip data or mutate SR/IG truths.

---

## 9) Security + compliance posture

- WS reads only by‑ref artifacts from object storage.
- WS sends events to IG using **the same auth controls** as any other producer.
- WS does not store secrets in artifacts or logs.
- WS does not alter SR/IG evidence, receipts, or policies.

---

## 10) Deployment shapes (prod‑realistic)

### A) Per‑run worker (job)
- A worker starts when READY arrives and streams until completion.
- Best for batch‑like backfills or controlled replays.

### B) Long‑running service (worker pool)
- A service subscribes to READY and spawns a worker per run_id.
- Best for steady, continuous operations.

Both are valid; the platform can support either without changing semantics.

---

## 11) Minimal v0 behavior (what WS must do first)

- Subscribe to READY (control bus).
- Read `run_facts_view` by ref.
- Stream `business_traffic` outputs in time order.
- Emit canonical envelopes into IG push.
- Persist checkpoints for resumption.

---

## 12) Non‑goals (explicit)

- WS does not replace SR readiness authority.
- WS does not enforce schema policy or quarantine decisions.
- WS does not own EB offsets or replay.
- WS does not mutate engine outputs.

---

## 13) Validation (minimum acceptance)

- WS streams only outputs declared by SR for the run.
- WS never emits events past the frontier.
- WS can restart and resume without duplicates or loss.
- IG receives and admits/quarantines with no schema/pin drift.

---

This design authority intentionally keeps WS small and strict: it exists to make the world **feel live** while preserving the platform’s truth boundaries.
