# World Stream Producer (WSP) Design Authority

This file is a rough collection of **design / brainstorm notes** for the **World Stream Producer (WSP)**. It treats the platform as a **network** and expands open **WSP’s position in that network** so later implementation can’t drift.

Everything below is **design-authoritative** for WSP unless it contradicts already-pinned platform laws (those still win).

---

## Introduction and overview

### Why WSP exists (the design correction we are making)

The platform cannot behave like “a giant batch ETL pipeline” where a whole month (or quarter) of traffic is pulled/processed at once. That violates the whole “bank-like” realism constraint: in a real bank, **future events are not visible on day 1**.

So we are pinning a new placement:

* The **Data Engine** remains the **World Builder** (offline materializer): it produces *immutable* world artifacts (traffic tables/streams + surfaces + proofs).
* The runtime fact-flow inside the platform does **not** “contain” the engine. Instead, the runtime sees a **streaming outside world**.

WSP is the missing vertex: the **stream head** that reveals the pre-generated world **incrementally** as time advances, rather than in bulk.

---

### WSP in one sentence (the pinned idea)

**WSP is the platform’s “outside-world traffic producer” for synthetic runs:** it replays **engine-materialized `business_traffic`** as a paced event-time stream **into IG**, so the rest of the platform experiences realistic, time-unfolding traffic.

---

### Where WSP sits in the graph

**Data-plane fact flow (new):**

`WSP → IG → EB → (IEG/OFP/DL) → DF → AL → DLA …`

**Control-plane run selection (unchanged):**

`SR → (join surface) → everyone` (downstream starts from SR or it’s a bug).

**Critical pin:** WSP is **not** a bus writer. EB’s traffic producer remains **IG-only**, so WSP must push **to IG**, never directly to EB.

---

### What crosses the WSP → IG edge

WSP submits **Canonical Event Envelope** records (payload opaque; envelope strict). The envelope requires:

* `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`
  and enforces `additionalProperties: false` at top level (payload must live under `payload`).

WSP is therefore responsible for emitting **already-canonical** envelopes (IG will still validate and may quarantine).

---

### The most important safety boundary WSP must respect

Engine output **roles** are real platform boundaries:

* only `business_traffic` is eligible to become traffic
* `truth_products`, `audit_evidence`, `ops_telemetry` must not enter the hot path as traffic

So WSP’s default stance is:

> **WSP streams `business_traffic` only. Everything else is by-ref consumption in other lanes (CM/DLA/OFS/etc.), not WSP traffic.**

---

### What WSP must NOT become (hard bans)

WSP must not drift into other vertices’ authority:

* **Not SR:** WSP does not choose worlds/runs; it does not publish READY; it does not define the run join surface.
* **Not IG:** WSP does not decide ADMIT/DUPLICATE/QUARANTINE; it does not relax pins/schema policy; it does not become the trust boundary. 
* **Not EB:** WSP does not own offsets/retention/replay. It never writes traffic directly to EB.
* **Not a “meaning transformer”:** WSP is transport + pacing + stable identity framing, not semantic rewriting.

---

### The non-negotiable invariants (minimum set to keep the platform honest)

1. **No oracle access:** WSP must not emit events “from the future” relative to the declared simulated time posture (pace/clock).
2. **SR join-surface discipline:** WSP must start from SR’s run context (refs + proofs) and must not scan storage for “latest world.”
3. **Canonical envelope discipline:** every emitted record is a canonical envelope; payload stays under `payload`.
4. **Role separation:** only engine `business_traffic` becomes WSP traffic.
5. **At-least-once tolerance:** duplicates are possible; identities must be stable so IG/consumers can be replay-safe.

---

## 1) What WSP is in this platform network (authority + boundaries)

### 1.1 The one idea (what WSP *is*)

WSP is the platform’s **outside-world traffic producer** for synthetic runs: it **replays engine-materialized `business_traffic`** as a **time-unfolding stream** of **Canonical Event Envelope** events **into IG**, so the rest of the platform experiences “bank-like” incoming traffic rather than bulk ETL.   

In other words:

* **Data Engine = world materializer (offline, external to fact-flow)**
* **WSP = the inlet/stream head that reveals the world over time (runtime fact-flow)**
* **IG = trust boundary** (admit/duplicate/quarantine) 
* **EB = durability + replay spine** (IG is the only writer) 

---

### 1.2 Where WSP sits (and what it touches)

**WSP is a Producer-class vertex**, not a control-plane authority and not a bus writer.

Its primary adjacency is a single hard edge:

* **WSP → IG** (push canonical envelopes; IG decides ADMIT/DUPLICATE/QUARANTINE; IG appends to EB)

And it has a required *control-plane dependency* (read-only join):

* **WSP ↔ SR join surface (read-only)**: WSP must start from SR’s declared run context (`run_facts_view` + READY) and must not “discover” worlds by scanning storage.

**Designer pin (hard):** WSP does **not** write to EB directly. EB’s write-side is IG-only; any design that bypasses IG breaks the platform’s trust boundary law.

---

### 1.3 WSP’s authority boundary (what it owns vs what it must not own)

#### WSP owns (authoritative responsibilities)

WSP is allowed to be authoritative for exactly these things:

1. **Traffic revelation posture (time-unfolding)**

* WSP decides *how* the pre-generated world is revealed as a stream: pacing, stepping, pause/resume, and “no future leakage” relative to its chosen simulated-time posture.
  (We’ll pin the exact clock model later, but the authority lives here.)

2. **Stable emission framing (non-semantic)**
   WSP must frame each emitted item as a canonical envelope (envelope-valid), including:

* `event_id` (stable idempotency key),
* `event_type` (routing key),
* `ts_utc` (domain event time),
* required world pin(s) (at least `manifest_fingerprint`). 

This is *framing*, not meaning transformation: WSP is not allowed to “interpret fraud,” “fix data,” or “change business semantics.”

3. **Producer identity declaration**
   WSP declares itself as a producer (via transport identity + optional envelope `producer` field), and accepts that IG will enforce identity consistency and authorization.

#### WSP must not own (hard bans)

These are explicitly *not* WSP’s authority:

* **Not run/world selection**: WSP does not decide what world/run exists. SR owns run readiness + the join surface.
* **Not admission**: WSP does not decide ADMIT/DUPLICATE/QUARANTINE. IG owns that truth.
* **Not durability/replay**: WSP does not own offsets, retention, or replay semantics. EB owns the fact spine; archive continuation is EB’s story.
* **Not payload semantics**: WSP does not validate business meaning; it does not “correct” records; it does not enrich with features/graph/decisions. (Those belong downstream.)
* **Not bypassing “downstream starts from SR”**: WSP must not scan engine output roots or infer “latest.” It must join from SR’s declared `run_facts_view`.

---

### 1.4 “Truth vs index” for WSP (what must be durable)

A recurring platform theme: “truth surfaces are immutable; indices are rebuildable.” SR does this explicitly with object-store truth + optional DB index.

For WSP we pin a minimal posture:

* **Truth of facts = EB (after IG admission)**
  The platform’s authoritative “what happened” is the admitted EB stream (and IG receipts/quarantine evidence), not “what WSP intended.”

* **WSP state is operational, not domain truth**
  WSP may maintain a **checkpoint/index** (“how far have I streamed?”) for restart/resume, but it is **not** a substitute truth source. If it’s lost, we can rebuild/rehydrate by reconciliation against IG/EB receipts, or by re-streaming (idempotently) using stable `event_id`.

This keeps WSP lightweight and prevents it from quietly becoming another “system of record” that later drifts.

---

### 1.5 The minimal invariants WSP cannot violate

These are the load-bearing laws that make WSP safe in your network:

1. **WSP behaves like the outside world**
   It must not reveal future events “just because they exist in storage.”

2. **All traffic crosses IG**
   No direct EB writes.

3. **Envelope discipline**
   Every emitted message is a valid Canonical Event Envelope; payload stays under `payload`; no extra top-level fields. 

4. **Join-surface discipline**
   WSP starts from SR’s run context (`run_facts_view` + READY). No scanning, no “latest.”

5. **At-least-once tolerance by construction**
   WSP must assume duplicates happen (retries, restarts, network), and therefore event identity must be stable so IG can dedupe deterministically.

---

## 2) WSP ↔ SR relationship (trigger vs control)

This edge is where we keep the platform’s **pinned entrypoint law** (“downstream starts from SR or it’s a bug”) while **removing SR from the data-plane**.

### 2.1 The pinned stance

**SR remains the run/join authority. WSP is just another downstream consumer of that authority.**

---

## Oracle storage + engine interface boundary (environment ladder)

### Where the “oracle” world lives
The engine’s finalized outputs are the **sealed world store** outside the platform runtime. They must be **immutable** and **by‑ref**.

**Local**
- Filesystem under `runs/local_full_run-*` is acceptable for now.
- Optional: MinIO for prod‑shaped local (S3‑style access).

**Dev**
- S3‑compatible bucket (MinIO or real S3).
- Suggested prefix layout:
  - `s3://fraud-platform-oracle/dev/engine_runs/<run_id>/...`

**Prod**
- Real S3 bucket with immutability posture.
- Suggested prefix layout:
  - `s3://fraud-platform-oracle/prod/engine_runs/<run_id>/...`

**Invariants**
- **Immutable**: once a run is sealed, do not overwrite.
- **By‑ref only**: platform consumes locators + digests, never payload copies.

### Does WSP replace the engine interface pack?
**No.** WSP does **not** replace the engine interface pack. The interface pack remains the **engine boundary contract** (catalogue + gates + schemas). WSP is a **downstream inlet** that consumes SR’s join surface and streams only declared `business_traffic` into IG.

Pipeline boundary (unchanged):
```
Engine outputs (oracle) → SR (READY + run_facts_view) → WSP → IG → EB
```

* SR publishes **READY (trigger)** + **`run_facts_view` (map)** as the platform entrypoint.
* WSP must **only** start from READY → fetch `run_facts_view` → follow refs. No scanning engine outputs, no “latest”, no guessing.
* SR **does not control pacing**, it just makes a run joinable and evidenced. (SR must not become “the pipeline”.)

That gives you the bank-like posture you want: SR does not “drive” time; it only declares the run context. The outside world (WSP) reveals facts over time.

---

### 2.2 What SR provides to WSP (and what it must NOT provide)

#### SR → WSP provides: **trigger + map**

1. **RunReadySignal on `fp.bus.control.v1`**

   * Meaning: “Run X is READY; here is the pointer to the facts view.”
   * Must include identity pins + pointer to `sr/run_facts_view` + idempotency identity (because duplicates happen).

2. **`sr/run_facts_view`**

   * Meaning: the authoritative *join surface map*: pins + refs/locators + evidence pointers.
   * It is the only allowed place WSP learns:

     * which outputs are eligible to be treated as traffic,
     * which world pins apply,
     * and what evidence set exists for gate prerequisites.

#### SR must NOT provide: **ticks / streaming control**

SR is explicitly pinned to *not* become the ingestion pipeline or traffic orchestrator.
So SR does **not** publish “second-by-second ticks” or attempt to sequence traffic. That control belongs to WSP (or later Run/Operate), not SR.

---

### 2.3 Trigger semantics: what READY means to WSP

**READY is permission to begin streaming for that run context.**
This is fully aligned with how IG interprets READY today in the legacy pull model (“permission to start work”).

**Pinned behavior for WSP on READY:**

* On READY:

  1. fetch `run_facts_view`
  2. validate it is readable + self-consistent with READY pins
  3. derive a **StreamPlan** (what to stream + from when to when)
  4. begin streaming to IG (data-plane is WSP → IG, not SR → IG).

**READY is not “traffic published.”**
The EB notes already pin that READY means “join surface exists + evidence pinned,” not “all traffic already published,” and that “traffic fully published” would be a separate status if ever needed. 
So in the WSP world, READY simply starts the stream; completion is separate (more below).

---

### 2.4 Idempotency + re-emit (this is where SR’s P7 matters)

SR explicitly supports a **re-emit/re-hydration path**: it can republish READY pointing to the same facts view when buses drop messages or consumers restart.

Therefore WSP must be designed as:

**“READY-consumer idempotent”**

* Multiple READY for the same run must not create multiple logical streams.
* WSP collapses duplicates to a single stream using a **run_key** derived from the READY pins (at minimum `{scenario_id, run_id}`, and in practice include the world pins too).
* If WSP is already streaming that run_key: treat READY as a “nudge” (refresh facts view pointer; ensure still valid) not as “start over”.

**Restart/resume is expected**

* If WSP crashes and later receives re-emitted READY, it must be able to resume without producing unrecoverable weirdness.
* The platform already assumes at-least-once everywhere; stable event identity is the safety net.

(We’ll pin the exact resume/checkpoint strategy later, but the SR side makes the requirement unavoidable.)

---

### 2.5 “Trigger vs control”: what SR controls vs what WSP controls

To keep SR clean, we split “control” into two layers:

#### SR controls (authoritatively)

* Which run context is joinable (READY monotonic).
* Which engine outputs are eligible to be treated as traffic (via the facts view mapping) — SR compiles that from policy/run plan.

#### WSP controls (authoritatively)

* **When** events are revealed (pace / step / pause / resume), provided it never violates “no future leakage.”
* **How** to sequence within its own emission discipline (event-time ordering posture).
* **How** to behave under backpressure (slow down, pause) without changing semantics.

This keeps the bank-like feel: SR picks “which world/run,” but **WSP is the outside world’s clock**, not SR.

---

### 2.6 The one friction point we must pin now: avoiding double ingestion

The legacy platform design includes an IG **pull ingestion job** (optional/backfill) that starts on READY for engine business traffic (A1/B-family).
Now that WSP is the primary path, we must ensure only one mode runs per run, otherwise we risk **both**:

* IG pulling the engine outputs, **and**
* WSP pushing the same events,
  creating duplicate floods.

So we need a minimal *design-authority* pin to prevent that drift:

**Designer declaration (v0): a run declares its traffic delivery mode.**

* Either:

  * `traffic_delivery_mode = STREAM` (WSP is responsible; IG must not run legacy engine-pull for this run), **or**
  * `traffic_delivery_mode = PULL` (legacy/backfill; IG legacy engine-pull path runs; WSP stays idle for that run).

The best place for this declaration is SR’s truth surface (because downstream must not guess). Concretely: a field in `run_facts_view` or `run_plan` that WSP and IG both read.

This is a tiny change in meaning that saves you from an enormous class of “why are there 2× events?” problems.

---

### 2.7 Completion semantics: does WSP talk back to SR?

**Default pinned stance:** SR does not need to know streaming completion to remain correct as “run readiness authority.” SR’s job ends at “run is joinable.”

But the EB design-authority explicitly notes that if you ever need “traffic fully published,” it should be a separate status signal. 

So we pin this as an optional extension:

* **[OPT] WSP emits `RunTrafficComplete` (control fact)** when it finishes streaming the run window.
* This is useful for automation (kick off offline jobs, report run done), but **it is not required** for correctness of the hot path.

SR does not become responsible for traffic completion; WSP (or Run/Operate) can publish that control fact.

---

### 2.8 Summary: the clean WSP↔SR handshake (meaning, not schema)

1. SR seals ledger + `run_facts_view`, then emits READY.
2. WSP consumes READY (idempotent), reads `run_facts_view`, and derives a StreamPlan.
3. WSP streams to IG under “no future leakage,” and never bypasses IG.
4. Duplicate READY / re-emit is treated as a nudge/resume, not a second stream.
5. To avoid drift, the run declares `traffic_delivery_mode` so IG doesn’t simultaneously do legacy engine-pull.

---

## 3) WSP ↔ Data Engine relationship (materialized world → stream)

This relationship is about one thing:

> **How immutable, pre-generated engine “traffic tables/streams” become an event-time unfolding stream, without WSP turning into a second engine, and without leaking oracle knowledge.**

---

### 3.1 What WSP is allowed to consume from the engine (hard boundary)

The engine interface + platform blueprint already pin the output role taxonomy as a **real boundary**, not a label: only **`business_traffic`** may enter the hot path; **truth_products / audit_evidence / ops_telemetry** are never treated as traffic.

So for WSP we lock this:

* **[PIN] WSP reads and streams `business_traffic` only.**
* **[PIN] WSP never streams “surfaces” that are intended to be consumed by-ref** (truth, audit, telemetry). Those remain other lanes (CM oracle lane, DLA forensics, OBS telemetry).

Also: “event-like” does **not** mean `class: stream`. The engine interface explicitly warns that some event-like outputs are parquet tables (e.g. `arrival_events_5B`). 
So WSP must be comfortable streaming from **surface-class parquet outputs** that are designated as business traffic.

---

### 3.2 How WSP learns “what to stream” (no discovery / no scanning)

We reuse the exact same “join surface discipline” already pinned for legacy IG engine pull:

* SR’s `run_facts_view` is the authoritative **map of engine refs + proofs** for the run.
* WSP does **not** discover worlds by scanning engine directories.
* WSP streams only the **explicit traffic targets** SR declared (by locator).

Concretely, the minimum “traffic target” shape we already have (from IG’s B2/J5/J6 framing) is exactly what WSP needs too:

* `engine_output_locator` (output_id + resolved path + identity tokens)
* `declared_role` (must be business_traffic)
* gate receipts / proof refs (PASS evidence)
* instance proof hooks where required (digest + instance receipt refs)

So **WSP depends on the same run_facts_view content contract** you already pinned for IG. That avoids inventing a second “facts map.”

---

### 3.3 Addressing & file resolution (materialized output → readable bytes)

The engine is addressable by tokenised path templates, but **WSP should not be a path-template renderer** in v0.

Why: you’ve already seen real-world packaging noise (e.g., a trailing newline in `path_template` broke matching until SR stripped whitespace). 

So we pin:

* **[PIN] WSP reads engine outputs by `engine_output_locator.path` only.**
  The locator exists specifically to be a portable “pin” to an immutable materialisation.

What WSP is allowed to do inside that constraint:

* If the locator path is a glob like `.../part-*.parquet` (as in `arrival_events_5B`), WSP may list/expand **only within that resolved locator scope** to obtain the concrete part files.
* But WSP may not move “up” to discover other partitions, other output_ids, or other worlds. That would violate the platform’s “no discovery by scanning” rule.

---

### 3.4 Proof model: how WSP stays honest while staying lightweight

The engine interface is strict:

* **No PASS → no read**, and gate verification is **gate-specific** (no universal hash).
* **Instance-scoped outputs require instance proof** bound to `(engine_output_locator + digest)`; digest must be present.

Meanwhile SR is explicitly designed to *do* the heavy work: role classification, gate graph closure, gate verification, instance proof binding, and only emit READY when evidence is complete.

So the clean minimal design is:

* **[PIN] SR is the attester; WSP is the consumer of attestations.**
  WSP does not recompute gate digests from raw validation bundles in v0. It requires that SR has already produced PASS receipts and (when required) instance-proof receipts bound to the locator+digest.

But WSP still must be fail-closed if the attestation bundle is inconsistent:

* **[PIN] WSP validates “attestation consistency” before streaming:**

  * Every traffic target has `declared_role=business_traffic`
  * Required gate receipt(s) exist and are PASS
  * If the output is instance-scoped (seed/scenario/parameter/run in scope), then `engine_output_locator.content_digest` exists and the instance proof receipt binds to that digest + locator (same binding law SR uses)

That keeps WSP small but still honest.

(If later you want a “paranoid mode” where WSP re-verifies gates directly against engine artifacts, that can exist as an optional posture — but it’s not required to get correctness today and it makes WSP heavier than you want.)

---

### 3.5 Streaming semantics: how immutable tables become “outside-world time”

This is the heart of the relationship: WSP must treat an engine traffic dataset as **a tape** whose content exists, but is **revealed** only as simulated time advances.

To do that, WSP needs two pieces of truth per output_id:

1. **What column represents domain time (`ts_utc`) for pacing**
2. **What key tuple defines stable identity (`row_pk_tuple`) for event_id**

Both are already pinned patterns in legacy IG engine‑pull framing logic, and we can reuse them as WSP framing laws:

* **Time extraction law:** prefer a column literally named `ts_utc`; otherwise use an explicit per-output time-column mapping stored in policy (not hardcoded). If time cannot be extracted deterministically → framing fails.
* **File-order law:** physical file order is non-authoritative; ordering must be derived from declared keys/fields.

This means WSP can stream from outputs like `arrival_events_5B` (parquet `part-*.parquet`) while honoring event-time unfolding.

---

### 3.6 Framing: what WSP must emit into IG

Because WSP is push-ingest, IG will **not mint missing fields**; missing `event_id`/`ts_utc` is a boundary violation.
And the canonical envelope requires `{event_id,event_type,ts_utc,manifest_fingerprint}` and forbids extra top-level fields. 

So WSP must do the “legacy engine‑pull style” framing itself:

* **[PIN] `event_type = output_id`** (drift-proof naming; no translation table in v0). 
* **[PIN] `event_id` minting is deterministic and uses declared PK, not row index.**
  Reuse the existing recipe pattern:
  `event_id = H("engine", output_id, row_pk_tuple, manifest_fingerprint, parameter_hash, scenario_id, seed)` and **exclude `run_id`** (run partitions attempts; it must not redefine world row identity).
* **[PIN] `ts_utc` is domain time** (never replaced by ingest time).
* **[PIN] Provenance pointers live under payload**, not top-level:

  * `payload.source.engine_output_locator`
  * `payload.source.row_pk_tuple`
  * `payload.source.content_digest` (when present/required)
  * proof refs (gate receipt ref, instance proof ref)

This keeps the “by-ref origin story” intact even though traffic is emitted by value.

---

### 3.7 Multiple traffic outputs: do we interleave or run independent substreams?

Engine may expose multiple outputs as traffic (SR can list multiple traffic targets).
We need a deterministic stance that doesn’t accidentally reintroduce “batch.”

**Designer pin (v0, deterministic + simple):**

* WSP emits traffic in **time windows** (your chosen quantum: second/minute/hour), and within each window:

  1. gather eligible rows from each traffic target where `ts_utc ∈ [window_start, window_end)`
  2. order emitted events deterministically by `(ts_utc, output_id, row_pk_tuple)`
  3. emit in that order

That gives you:

* no future leakage (windowing)
* deterministic replay of the streaming order (ordering rule)
* no reliance on nondeterministic concurrency scheduling

(If performance becomes an issue, you can later add a derived “time index” sidecar per output_id because outputs are immutable — but that’s an optimization, not a semantic change.)

---

### 3.8 What WSP expects the engine to guarantee (and what WSP must *not* assume)

Engine guarantees:

* deterministic, immutable materialisations per identity partition (write-once; byte-identical).
* declared catalogue metadata: path templates, partitions, PK, required gates.

WSP must **not** assume:

* physical file order means anything (it doesn’t).
* that every traffic table already contains a column named `ts_utc` (preferred, but not guaranteed; mapping may be needed). 
* that a missing optional output is an error (SR already treats `availability: optional` as non-blocking).

---

## 4) “Streaming like a bank” (time + pacing semantics)

This section is where we lock the **bank-realism** core: the platform must experience traffic as **time-unfolding arrivals**, not as “the whole month landed at once.”

This must also honor the platform rail: **time semantics never collapse** (domain time vs ingestion time vs “as-of” remain distinct). 

---

### 4.1 The three time axes we must keep distinct

**A) Domain event time (truth time)**

* This is **`ts_utc`** on the canonical envelope. It is the event’s *meaningful time* in the simulated world.
* It is required on every traffic event. 

**B) Emission time (outside-world “sent time”)**

* This is **`emitted_at_utc`** (optional) on the canonical envelope — if we choose to use it. 
* It represents when the outside world (WSP) *emitted* the event into the platform boundary (not when the event “happened”).

**C) Ingestion/admission time (platform boundary time)**

* This is owned by IG receipts / audit trail (not the envelope). IG is the trust boundary and produces receipts for ADMIT/DUPLICATE/QUARANTINE. 

**Pinned posture:** WSP must **never** rewrite domain time into ingestion time. `ts_utc` stays domain truth; IG receipts handle ingestion timing.

---

### 4.2 The bank realism rule (“no oracle access”)

We already pinned the idea informally; now we pin it as the time law for WSP:

**[PIN] WSP must not reveal future events.**
Meaning: at any moment, WSP is only allowed to emit events whose `ts_utc` is **≤ the current simulated “now”** for that stream.

This is the “bank can’t see Jan-31 on Jan-1” guarantee, even though the engine has already materialized Jan-31 in storage.

---

### 4.3 Where the simulated “now” comes from (who owns the clock)

SR explicitly must **not** become the ingestion pipeline or “smuggle an implicit now”; runs carry explicit time/window keys. 
So we keep SR clean:

**[PIN] SR provides the run window; WSP owns the streaming clock.**

* SR’s `run_plan / run_facts_view` carries the run’s intended time window (start/end) and pins. 
* WSP chooses how simulated time advances within that window (pace policy).

This fits your “engine is outside the bank; outside world controls arrivals” goal.

---

### 4.4 Pace is two orthogonal knobs (don’t mix them)

To avoid accidental batch behavior, we separate pace into:

**Knob 1 — Clock progression policy (how sim-time advances)**
**Knob 2 — Throughput limiter (how fast we can physically emit)**

You can accelerate the clock **without** emitting “in bulk,” as long as the throughput limiter keeps emissions incremental.

---

### 4.5 The pacing profiles we should support (design-level)

These are not “spec enums”; they’re the conceptual modes we want WSP to be able to operate in.

#### Profile A — Stepwise (the default bank-sim posture)

**Idea:** advance simulated time in discrete steps (ticks), and emit everything in that tick window.

* Tick window example: 1 second, 10 seconds, 1 minute, 1 hour, 1 day.
* For each tick `[T, T+Δ)`:

  * emit all events with `ts_utc ∈ [T, T+Δ)`
  * do not emit beyond `T+Δ`
  * then advance to next tick

**Why this is good for your current pain:** it prevents the “whole month at once” behavior by construction, even if the total run window is huge.

**Determinism bonus:** stepwise ticking makes “what happened when” extremely explainable and repeatable.

#### Profile B — Continuous (wall-clock mapped)

**Idea:** simulated “now” moves continuously as a function of wall clock (optionally speeded up).

* Real-time: sim_now tracks wall time.
* Accelerated: sim_now advances at factor `k` (e.g., 60×).

This is closer to “live feed” behavior, but can create backlog if throughput is insufficient.

#### Profile C — Max-throughput (fast replay, still no future leakage)

**Idea:** WSP emits as fast as allowed, but **never crosses the sim_now gate**.

* Useful for offline backfills / fast simulation.
* Still must obey ordering + no future leakage.

---

### 4.6 Throughput limiter (the thing that prevents “bulk” in practice)

Even in stepwise mode, a single tick can contain a lot of events (e.g., payday bursts). So we need a second, separate rule:

**[PIN] WSP must have an explicit throughput limiter and backpressure posture.**

Two valid stances (we choose one as v0 default):

**Option 1 — Coupled clock (v0-friendly)**

* WSP does not advance sim-time past a tick until it has successfully *handed off* the tick’s events to the ingress boundary (e.g., queued durably or accepted by the ingress transport).
* If IG/ingress is slow, sim-time effectively slows too.

This is simplest to reason about and avoids unbounded buffering.

**Option 2 — Decoupled clock (more “outside world” realistic)**

* WSP’s sim-time can advance even if the platform is slow, but then events must accumulate in a durable buffer/outbox (Kafka/file bus/etc.).
* This better matches “the world keeps happening even if the bank is down,” but it introduces queue growth and operational complexity.

**Designer pin (v0): choose Coupled Clock as default**, because it keeps WSP small and prevents “infinite backlog” while we get the new component green. We can keep Decoupled Clock as an explicit “later production posture” option.

(We’ll still keep the conceptual story that WSP is the outside world; we’re just choosing the safest v0 operational posture.)

---

### 4.7 Ordering within time (how to “honor sequence” without pretending global total order)

The bus only preserves order within partitions; IG is the front door and applies partition policy. 
So we should pin the honest bank-like guarantee:

**[PIN] WSP guarantees non-decreasing `ts_utc` emission order, with deterministic tie-break.**
Within identical `ts_utc`, WSP uses a deterministic tie-break order (e.g., `output_id` then `row_pk_tuple`) so the stream is stable.

This is enough to make the world feel “temporal” without pretending we can promise a single global order across every key at scale.

---

### 4.8 What we do with `emitted_at_utc` (optional but useful)

The canonical envelope explicitly allows `emitted_at_utc` as “optional emission timestamp if distinct from ts_utc.” 

So we pin:

* **Default:** set `emitted_at_utc` to the actual wall clock time WSP emits (helps debugging and observability).
* **Rule:** `emitted_at_utc` must never be used as domain truth; only `ts_utc` is domain time. 
* **Optional deterministic mode:** for reproducibility tests, WSP may set `emitted_at_utc` as a deterministic function of `(run_start_wall, ts_utc, speedup)` — but this is strictly optional and must not affect semantics.

---

### 4.9 Pause / resume / speed change (control without SR becoming the pipeline)

SR publishes READY and run facts as truth; it must not become the streamer. 
So WSP should own its runtime controls:

* **Pause/Resume:** WSP can pause emission without changing run truth surfaces.
* **Speed change:** WSP can adjust pace policy mid-run (as an operational control), but must preserve “no future leakage.”

How controls are delivered (control bus topic vs local CLI) can remain flexible; the key is: **controls target WSP, not SR**.

---

### 4.10 Completion semantics (what “done streaming” means)

We reuse the platform idea that READY ≠ “traffic published.” 
So:

* **Streaming completion** means WSP has emitted all eligible traffic events with `ts_utc` within the run window.
* **[OPT]** WSP can publish a “traffic complete” control fact if later components (offline jobs, reports) need a clean hook — but this is optional and should not be conflated with SR readiness.

---

### The v0 “bank streaming” pin set (so we don’t drift later)

If you want a crisp set of pinned decisions for this section:

1. **`ts_utc` is domain time and is never replaced by ingestion time.** 
2. **WSP enforces “no future leakage” by gating emissions on a simulated `sim_now`.**
3. **SR provides the run window; WSP owns the streaming clock.** 
4. **Default pacing profile is Stepwise (tick windows).**
5. **v0 backpressure posture is Coupled Clock** (no unbounded buffering).
6. **WSP emits non-decreasing `ts_utc` order with deterministic tie-break.**
7. **`emitted_at_utc` is optional observability; never domain truth.** 

---

## 5) Event shaping (canonical envelope, pins, identity)

This is where we make WSP “plug-compatible” with the rest of the network: **IG must be able to admit it, EB must be able to store it, IEG/OFP must be able to replay it**, and nothing can quietly drift because WSP invented its own event packaging rules.

---

### 5.1 Canonical envelope is non-negotiable (WSP must emit already-canonical)

**Pin:** Every WSP emission must be a **Canonical Event Envelope** record (top-level is strict: `additionalProperties: false`; payload must live under `payload`).

Minimum required envelope fields are fixed:

* `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`

And the envelope vocabulary explicitly includes optional pins + trace fields:
`parameter_hash, seed, scenario_id, run_id, emitted_at_utc, schema_version, trace_id, span_id, parent_event_id, producer`

**Design consequence:** WSP cannot “smuggle” extra header fields at top-level. Anything else is either (a) in `payload`, or (b) a different event type with an agreed payload contract.

---

### 5.2 Pins: what WSP must stamp on every traffic event

WSP traffic is **run/world joinable traffic**, so it must carry the pins IG requires for run-scoped traffic.

IG’s pinned required-pins rule for run-scoped events is:

* `scenario_id`, `run_id`, `parameter_hash`, and (for traffic classes) `seed`
* plus `manifest_fingerprint` (already required by envelope law)

And IG’s hard boundary is: **it does not enrich missing pins**; missing pins are a boundary violation (`PINS_MISSING`).

So for WSP:

**Pin (v0): WSP stamps the full run/world pin set on every business_traffic event:**
`{manifest_fingerprint, parameter_hash, scenario_id, run_id, seed}`

Where do these come from?

* **Not from scanning engine rows** (that’s a consistency check, not authority)
* From SR’s run join surface / facts view (WSP is downstream of SR authority).

---

### 5.3 `event_type`: drift-proof naming for engine-backed traffic

IG already pins the drift-proof rule in legacy engine-pull framing:

* **Engine pull:** `event_type = output_id` (exact string; no translation table in v0).
* **Push ingest:** event_type is producer-declared but must be policy-allowed.

Even though WSP is “push ingest,” we want **compatibility** with the legacy engine-pull world and **zero naming drift**, so:

**Pin (v0): WSP uses `event_type = output_id` for engine-backed business_traffic.**

That implies IG policy must allow:

* producer = WSP principal
* event_type = each allowed output_id (the traffic allowlist is SR’s plan; admission allowlist is IG’s policy).

---

### 5.4 `event_id`: stable identity (and why excluding `run_id` is OK)

Two rails matter here:

1. Envelope defines `event_id` as the stable idempotency/dedup anchor at ingest/bus boundaries.
2. IEG’s “duplicate mismatch” rule says: if the *same logical event* repeats, it must not silently mean different facts; IEG checks an envelope-critical fingerprint when it sees duplicates.

IG already pinned an authoritative minting recipe for engine rows:

`event_id = H("engine", output_id, row_pk_tuple, manifest_fingerprint, parameter_hash, scenario_id, seed)`
and **run_id is not included**.

So WSP should **reuse exactly this recipe** to remain compatible with the prior pull path:

**Pin (v0): WSP mints event_id using the IG legacy engine-pull recipe (same inputs; no run_id).** 

Why excluding `run_id` doesn’t break the platform:

* IG’s dedupe key is **not just event_id**. For run-scoped events it explicitly includes `(scenario_id, run_id)` on top of `(producer, event_type, event_id, manifest_fingerprint)`.
* IEG’s idempotency anchor is `update_key = H(scope_key + event_id + semantics)` where `scope_key` includes `run_id`. So duplicates are scoped correctly.

**Practical implication:** You can replay the same world under a different run_id and still have stable “world fact identity” (event_id), while dedupe/idempotency remains run-scoped.

---

### 5.5 Identity hints (`observed_identifiers[]`) packaging: we must pin the v0 bridge

Platform-wide tension (already pinned):

* canonical envelope does **not** include `observed_identifiers[]` (and forbids unknown top-level fields),
* but IEG wants to be envelope-driven and requires identity hints at the bus boundary.

IEG pins the v0 bridge explicitly:

* **Mode A (future):** top-level `observed_identifiers[]` (envelope vNext)
* **Mode B (v0):** one strictly standardized location under payload, e.g. `payload.identity_hints`, and S1 reads **only** that standardized block (no rummaging).

So we need a WSP design decision:

**Pin (v0): WSP emits exactly one standardized identity-hints block at `payload.identity_hints`.**

Two immediate consequences:

* WSP must ensure that block exists for event types that are identity-impacting (so IEG/OFP don’t fall back to bespoke parsing).
* The *shape* of that block must be standardized enough that IEG can normalize it (subjects/identifiers style).

**How WSP gets those hints without becoming “semantic”:**

* Treat it like `ts_utc` extraction: a **policy-driven mapping** per `event_type/output_id`, not ad-hoc code logic. (Same philosophy IG uses for time-column mapping and schema posture.)

---

### 5.6 Payload packaging: keep by-value data + by-ref origin story (and avoid collisions with IG)

IG already pins a very clean legacy engine-pull payload structure:

* `payload.data` = selected row fields needed downstream (policy-driven)
* `payload.source` = immutable by-ref pointers:

  * `engine_output_locator`
  * `row_pk_tuple`
  * `content_digest` (if present/required)
  * proof refs (gate receipt ref, instance proof ref)

And IG separately reserves `payload.ingest_source = {source_kind, raw_input_ref}` for its own boundary provenance stamps.

So for WSP:

**Pin (v0): WSP uses the same `payload.data` + `payload.source` packaging as IG legacy engine-pull, and never writes `payload.ingest_source` (IG owns that).**

This is a big drift-killer: downstream code (IEG/OFP/DF) can treat engine-backed traffic the same whether it arrived via legacy pull or via WSP push.

---

### 5.7 Optional fields: what we should and shouldn’t use in v0

* `producer`: strongly worth setting, but must match transport identity or IG will quarantine (same rule DF is held to).
* `emitted_at_utc`: useful observability for WSP pacing (distinct from `ts_utc` domain time).
* `trace_id/span_id`: optional; nice for debugging but not necessary for correctness.
* `parent_event_id`: reserve for correction/supersedes stories; WSP usually shouldn’t emit corrections (EB/IG pins “no mutation; corrections are appended facts”).

---

### 5.8 The “don’t accidentally break the platform” checklist for WSP event shaping

If WSP gets these wrong, the platform will degrade or quarantine in very specific ways:

* Missing pins → IG rejects (`PINS_MISSING`) because IG does not enrich.
* Missing/invalid event_id in push → boundary violation; IG doesn’t mint in push mode.
* Identity hints missing where needed → IEG marks `INVALID_RECORDED(MISSING_ID_HINTS)` and integrity degrades (it continues; it doesn’t stall).
* Same event resent (same run) → IG dedupe key collapses it (run_id is part of dedupe key for run-scoped events).
* Same update resent (IEG) → `update_key` handles it; mismatch gets surfaced as `DUPLICATE_MISMATCH` (explicit integrity signal).

---

## 6) Ordering, partitioning, and “sequence of events”

This is the place we make the system feel like a bank **without lying** about what the bus can guarantee.

### 6.1 The uncomfortable truth we must pin

**EB does not promise “time order.”**
It’s *at-least-once*, ordering is **partition-only**, and `ts_utc` ordering is **not guaranteed**. 

So the platform cannot depend on “global stream order = chronological order.” Any design that quietly assumes that will drift and break under load.

What we *can* pin (and already have pinned elsewhere):

* The only universally meaningful position is `(stream_name, partition_id, offset)` and checkpoints are **exclusive-next**.
* Consumers (IEG/OFP/Shadow/etc.) must therefore be **replay-safe** and tolerate duplicates/out-of-order.

### 6.2 So what does “sequence of events” mean in our bank simulation?

**Design pin:** “Sequence” means **per-entity/per-flow ordering**, not a single global order.

In a bank, you don’t need “all bank events are totally ordered.” You need:

* “events for the same account/card/session are processed in a stable order,”
* while different accounts are naturally parallel.

So the *real* question becomes: **what key defines the ‘bank-like’ flow we care about?** (Account? Instrument? Customer? Merchant terminal?)

This is where partitioning comes in.

---

### 6.3 Authority boundaries: who controls what ordering

#### EB (what it guarantees)

* Stores admitted facts; assigns `(partition_id, offset)`; ordering only within a partition; does not fix envelopes; does not infer partitioning. 

#### IG (what it stamps)

* IG is the trust boundary, and **IG stamps a deterministic partition key / routing decision** using a **policy profile** (EB never infers).

#### WSP (what it can influence)

* WSP can (and should) emit events in a sane event-time posture (non-decreasing `ts_utc`, deterministic tie-breaks) for “bank feel”…
  …but it cannot force global bus order, because the bus only preserves partition order.

**Therefore:** the “sequence” experience is primarily achieved by choosing **partition keys** that align with the flow you care about.

---

### 6.4 Partitioning goals (what we’re optimizing for)

We want partitioning that is:

1. **Bank-realistic**: preserves per-flow ordering for the key flows (e.g., account-level transaction sequence).
2. **Deterministic**: the same event always routes the same way under the same profile (no hidden inference).
3. **Policy-driven**: partitioning is a versioned profile decision, not ad-hoc code logic.
4. **Doesn’t require “payload rummaging.”**
   IG is not allowed to become a semantic parser; it enforces boundary rules.
   So the partition-key inputs need to come from **standardized, reserved locations**.

This connects directly to the IEG “identity hints” bridge:

* IEG pins that identity-impacting events must carry a standardized identity-hints block (v0: `payload.identity_hints`) and S1 reads **only that** (no digging).

**WSP implication:** if we want partitioning to be stable and not “payload-specific,” WSP should provide a standardized, shallow partition key candidate via the same standardized identity-hints machinery (or an equally standardized reserved field).

---

### 6.5 Practical partitioning profiles (design options, not specs)

Think of these as “profiles” IG can choose from (policy-driven), depending on event type/class.

#### Profile A — **Account-flow partitioning** (most bank-like for transactions)

Partition key derived from the “primary account-like identifier” for the event.

* Pros: strong per-account sequence; “feels like a bank ledger.”
* Cons: skew risk (hot accounts); may underutilize partitions if account distribution is uneven.

#### Profile B — **Instrument-flow partitioning** (card/token/device-centric)

Partition key derived from primary instrument identifier.

* Pros: preserves sequence for fraud-relevant instrument timelines; often high-cardinality = good distribution.
* Cons: cross-instrument account history becomes cross-partition (still joinable via IEG/OFP, but not ordered in one partition).

#### Profile C — **Customer/entity partitioning**

Partition key derived from customer/person identity.

* Pros: good for customer-level profiles.
* Cons: requires customer identity to be reliably present early; often not true for all event types.

#### Profile D — **Event-id hash partitioning** (max throughput, minimum ordering)

Partition key = hash(event_id).

* Pros: best distribution, simplest.
* Cons: destroys per-entity sequencing feel; “bank-like flow” is lost.

**Design pin (v0 recommendation):**
Use **Account-flow** for core transaction-like traffic, and **Instrument-flow** for instrument-centric event types; reserve event-id hash for high-volume “stateless” event types where per-entity order doesn’t matter.

This remains IG policy; WSP’s job is to reliably surface the identifiers needed in standardized form.

---

### 6.6 What WSP should (and should not) promise about ordering

Given EB’s laws, here’s the honest posture:

**WSP should aim for:**

* Emission in **non-decreasing `ts_utc`** overall (bank-feel), with a deterministic tie-break (e.g., `output_id` then `row_pk_tuple`) so streaming is explainable and repeatable.

**WSP must not claim:**

* “The platform will observe strict chronological order” (false; EB doesn’t guarantee it). 

**What the platform can truly rely on:**

* Within a partition, consumers see a strict offset order (FIFO per partition).
* Progress/watermarks are per-partition offsets, and those are what drive `graph_version` and `input_basis`.

So the “sequence of events” story is:

> *Per-flow ordering is achieved by partitioning. Global time ordering is not a guarantee, but domain time remains `ts_utc` and projections/features must be disorder-safe.*

That matches IEG’s pinned reality: it processes in offset order per partition, applies idempotently, advances watermarks, and records integrity issues instead of stalling forever.

---

### 6.7 Multi-output interleaving: “one world stream” vs “many substreams”

Engine-backed traffic is often multiple output_ids. The bank-feel expectation is “one outside world,” but operationally we have multiple substreams.

**Design pin (v0): WSP emits a single logical stream of envelopes, but its ordering rule is windowed and deterministic.**

* Within a time window, WSP can interleave events from multiple output_ids using the deterministic tie-break.
* Partitioning then splits that into per-flow sequences on the bus.

This gives you:

* one conceptual “outside world stream”
* without pretending that downstream observes a single total order.

---

### 6.8 The correctness anchor: watermarks, not time

If you want one sentence that prevents future drift:

**Pinned:** “Applied truth is defined by offsets/watermarks, not by ‘latest ts_utc seen’.”

That’s why:

* IEG’s `graph_version` is based on per-partition applied offsets. 
* OFP snapshots stamp `input_basis` similarly.

So even if events arrive out-of-order by `ts_utc`, replay determinism remains intact.

---

## 7) Backpressure + scaling (without turning into “bulk ETL”)

This section is about one rule: **WSP must behave like a real outside-world feed under pressure** — i.e., *slow down / pause / resume safely* — rather than “buffer the entire month and blast it later.”

### 7.1 Load-bearing pins (backpressure posture)

**[PIN] No silent drops, ever.**
Backpressure must be explicit at every hop, and WSP must treat it as a first-class outcome, not as “best effort.” This is consistent with EB’s publish edge (“CommitAck / Throttle / Reject / explicit retryable failure”) and the platform’s “no silent acceptance” rail.

**[PIN] Backpressure changes *when* we stream, not *what* the stream means.**
Same posture as the consumer-side backpressure joins (IEG/DLA): throttle/pause/drain are operational safety valves, not semantic controls.

**[PIN] Default v0 backpressure mode is Coupled Clock.**
If IG/EB are slow, WSP slows its *simulated time advancement* rather than building an unbounded backlog. (This is how we prevent WSP from turning into “bulk ETL with a big buffer.”)

---

### 7.2 Where backpressure can come from (the real sources)

Even though WSP only talks to IG, the pressure signals originate from multiple layers:

1. **IG service boundary (push intake)**

* IG already supports **rate limiting** for push ingestion (429 / `RATE_LIMITED`) and has a health posture that can refuse intake under dependency failure.
  WSP must treat these as *explicit backpressure*, not as errors to “power through.”

2. **IG → EB publish edge**

* EB publish ingress can return **THROTTLE** (retryable) or **REJECT** (non-retryable) under quota/pressure, and “ACK is truth” if returned.
  WSP doesn’t see EB directly, but IG’s outcomes/receipts will reflect “can’t publish now” vs “will never publish.”

3. **Local/dev “it’s too big” reality**

* Your current IG pull experience shows the failure mode: even with sharded pulls, a single parquet shard can be too heavy, forcing finer grain chunking (row-group / row-batch) to make progress.
  WSP must *not* recreate this by reading/holding huge engine slices in memory “just to be fast.”

---

### 7.3 WSP’s backpressure control verbs (mirror the platform’s style)

We already have an excellent “tiny control API” vocabulary from IEG: **THROTTLE / PAUSE / DRAIN / RESUME**. 
WSP should use the same mental model (producer-side):

1. **THROTTLE(rate | concurrency | tick_quantum)**

* Reduce emit rate, reduce in-flight submissions, and/or shrink the tick quantum (e.g., from 1s → 100ms) so each “unit of work” is smaller.

2. **PAUSE(scope = run | lanes | partitions)**

* Stop reading new engine rows and stop submitting new events to IG, but keep state so we can resume safely.

3. **DRAIN(in_flight_only)**

* Stop intake, but allow already-submitted events to complete (receive IG receipts / outcomes). When drained, transition to PAUSED.

4. **RESUME**

* Continue from the last safe cursor.

**[PIN] These controls are operational only.** They must never change event identity, pins, or payload meaning.

---

### 7.4 Bounded buffering: how WSP avoids “bulk ETL” even when it’s fast

**[PIN] WSP must have a bounded in-flight model.**
If WSP can submit unlimited events without waiting for outcomes, it will inevitably become “blast + backlog.”

A clean pattern already exists in DLA’s consumer machinery: bounded in-flight buffers + an ack/gap tracker + flow control to prevent memory blowups.
WSP can use the analogous producer-side structure:

* **Frame Builder**: engine row → canonical envelope bytes
* **In-flight Queue (bounded)**: submitted but not yet resolved
* **Outcome Collector**: IG responses / receipts arrive (may be out of order)
* **Gap Tracker / Safe Cursor**: only advance the durable “source cursor” when outcomes are contiguous (no skipping), exactly like “exclusive-next” checkpoint meaning on the consume side

**Design consequence:** WSP can be concurrent, but it must still have a notion of **“safe progress”** that is receipt-gated.

---

### 7.5 Retry, throttle, reject: what WSP should do (meaning, not code)

We can reuse EB’s publish outcome taxonomy as the “truth table” for how to behave under stress (even if WSP only sees IG reflecting it):

* **THROTTLE / RATE_LIMITED (retryable):**

  * WSP must back off (reduce concurrency / reduce tick size / pause briefly) and retry.
  * Crucially: WSP must not “read ahead” and accumulate huge buffered future events while waiting.

* **Explicit REJECT (non-retryable):**

  * Treat as a terminal failure for the stream posture at that scope (run or lane).
  * Move to PAUSED + emit an operator-visible incident fact (or at least logs/metrics).
  * Do not keep hammering IG.

* **Ambiguous timeout (unknown outcome):**

  * Assume at-least-once reality: retry may cause duplicates.
  * This is acceptable because IG/EB are built for duplicates, but WSP should prefer idempotent request keys and bounded retry to converge.

---

### 7.6 Scaling: how we go faster without reintroducing “process the whole month”

There are only a few safe scaling dimensions in this architecture:

#### A) Scale by **run** (cleanest)

Run multiple WSP instances, each owning different `(scenario_id, run_id)` streams. This is naturally parallel and keeps “bank realism” intact.

#### B) Scale within a run by **lanes** (bounded parallelism)

WSP can split work into deterministic *lanes* (e.g., by event_type/output_id, or by time-window shards), each with:

* its own bounded in-flight queue,
* its own cursor,
* its own pause/drain/resume.

This mirrors how DF and DLA think: partitioned lanes + backpressure loops protect stability without changing semantics.

**Important guardrail:** lane parallelism is bounded and must never prefetch beyond the active sim-time window (no future leakage).

#### C) Scale the engine read granularity (make “work units” small)

Your IG pull notes already show the key lesson: if “one shard” is too big, you need finer-grain chunking (row-group / row-batch) to make progress.
For WSP, the same principle becomes:

> **WSP’s smallest unit of work must be smaller than “one giant file / one giant day”.**

So WSP should be able to stream from:

* file parts (`part-*.parquet`),
* row groups,
* row batches,
  as long as the unit boundary is deterministic and cursorable.

This is scaling that preserves streaming semantics instead of reverting to batch.

---

### 7.7 “Don’t turn into bulk ETL” guardrails (explicit drift bans)

1. **No unbounded backlog**

* If downstream is slow, WSP slows the sim clock (Coupled Clock) instead of buffering indefinitely.

2. **No read-ahead beyond the active window**

* WSP should not read/compute envelopes for future windows “just to be ready.”

3. **Bounded in-flight + receipt-gated progress**

* Advance the durable cursor only when IG outcomes are known (admitted/duplicate/quarantine), never on “we attempted to send.”
  This mirrors the platform’s checkpoint law: no progress claims without durable evidence.

4. **Explicit operational controls**

* Support pause/drain/resume as real states, and make them observable (same “mode visibility” pin used elsewhere).

---

### 7.8 Environment ladder knobs (allowed to vary, semantics stable)

Borrow the pattern used across the platform: semantics don’t change across envs, only knobs do.

WSP environment knobs that may vary:

* max in-flight submissions
* tick quantum defaults (second vs minute)
* throttle thresholds / backoff policy
* per-run concurrency
* local-only time caps (like IG’s time budget posture)

But the invariants above must not change.

---

## 8) Reliability: restart, resume, and exactly-what-happened

This section pins how WSP stays **correct under crashes, timeouts, retries, duplicates, and partial progress**—without turning into a new “system of record.”

### 8.1 The reality we must design for (no fairy tales)

**EB is at-least-once and does not dedupe**, and ordering is partition-only. 
So any “exactly once” story must be achieved by **idempotency + receipts**, not by pretending transport is perfect.

Also, **Canonical Event Envelope requires `event_id`** and explicitly defines it as the stable idempotency/dedup identifier at ingest/bus boundaries.
So reliability starts with: *stable ids + receipt truth*.

---

### 8.2 What counts as “truth” for what happened

This is the drift-killer:

**[PIN] What “happened” is defined by IG’s receipts (and the EB coordinates inside those receipts), not by WSP’s intention or “I sent it.”**

IG’s design-authority is explicit:

* IG must decide exactly one of **ADMIT / DUPLICATE / QUARANTINE** for each input, and leave a durable receipt/evidence trail (no silent drop).
* **ADMITTED iff EB acked**, and the receipt must carry (or reference) stable `{partition, offset}` coordinates.
* **DUPLICATE is terminal** and points to the original EB coordinates (or receipt ref).
* **QUARANTINE implies evidence exists + a QUARANTINED receipt exists** (no EB append).

So WSP’s reliability posture is:

> WSP doesn’t need to “prove” it streamed; it needs to be able to **reconcile** against IG receipts and advance only on terminal receipt truth.

---

### 8.3 WSP’s “checkpoint law” (producer-side version of the DLA rule)

DLA already pins the canonical rule for consumers:

* **Exclusive-next checkpoints**
* **Advance only with durable proof (AckTickets)**
* **No skipping; contiguity required; tolerate out-of-order completion**

WSP needs the same concept, but in producer form:

**[PIN] WSP advances its stream cursor only when it has a terminal IG receipt for the emitted event (ADMITTED / DUPLICATE / QUARANTINED), and only advances contiguously under its own ordering key.**

Think of IG receipts as WSP’s “AckTickets.”

Why this matters:

* Prevents WSP from “claiming progress” when outcomes are unknown.
* Makes restart/resume deterministic.
* Makes “exactly-what-happened” reconstructable from receipts.

---

### 8.4 The stream cursor: what WSP resumes from (without depending on file order)

WSP cannot rely on physical storage order (“row N in file X”) as truth; engine outputs can be multi-file (`part-*.parquet`) and file order is not authoritative. (This is already a pinned theme in your engine/pull framing.)

So the cursor must be expressed in a **stable logical order key**.

**Designer pin (v0): cursor is based on the same deterministic emission order WSP uses.**
For example:

* primary: `ts_utc` window position (tick index)
* tie-break: `(event_type/output_id, row_pk_tuple)`
  …and you treat that tuple as the “stream order key.”

This keeps the cursor independent of storage layout changes, and consistent with your earlier “WSP emits non-decreasing `ts_utc` with deterministic tie-break” stance.

---

### 8.5 Restart / resume: the three canonical restart cases

#### Case A — Clean restart (WSP has its own cursor)

1. WSP restarts, re-reads SR’s READY + `run_facts_view` (immutable join surface).
2. WSP loads its saved cursor and resumes emission at the next not-yet-terminal order key.
3. Any duplicates caused by “unknown last outcome” are resolved by IG via DUPLICATE receipts.

#### Case B — “Stateless” restart (cursor lost)

This must still be correct.

**[PIN] Correctness must not depend on WSP’s cursor existing.**
If WSP loses its cursor, it is allowed to restart from the beginning of the run window and re-emit. IG’s dedupe/receipts ensure it converges (ADMIT once, then DUPLICATE).

This may be slow, but it is truthful and safe. Performance comes from having the cursor; correctness does not.

#### Case C — Control-plane redelivery / duplicate READY

SR’s control bus is at-least-once and explicitly supports re-emit/rehydration; READY publishes are idempotent by `(run_id, facts_view_hash)`.

So WSP must treat READY as:

* “start if not started”
* “nudge/refresh if already streaming”
* never “start a second stream for the same run”

---

### 8.6 Unknown outcome and retry storms (the “I sent it but didn’t hear back” problem)

This is the exact place systems lie if not pinned.

EB publish ingress is explicit: **No silent acceptance; ACK is truth; timeouts can still lead to duplicates**.

IG’s commit machinery similarly pins:

* retriable vs terminal commit failures,
* keep the ledger **PENDING** during retriable uncertainty,
* only finalize ADMITTED on broker ack, and only quarantine via explicit deadletter + evidence.

So WSP’s retry posture must be:

**[PIN] If the outcome is unknown, WSP retries with the same event identity (same `event_id`). It never invents a new `event_id` to “get through.”**

And if WSP retries while IG’s first attempt is still in-flight, IG may respond “duplicate-of PENDING” semantics (i.e., “already in flight; retry later if you need confirmation”).
WSP must treat that as **not terminal** and must keep the cursor pinned until it can observe a terminal receipt.

---

### 8.7 QUARANTINE: does WSP stop or continue?

IG quarantine is first-class, durable, and comes with evidence and a receipt.
EB also pins that quarantined items are **not “on the bus.”** 

So we need a pin for WSP:

**Designer pin (v0): QUARANTINED is terminal for the event, and WSP continues streaming.**

* WSP records it as “this attempted outside-world event did not become platform fact.”
* The run does not wedge because one event quarantined (same “don’t deadlock the pipeline” philosophy DF uses for quarantines).

If you later want “stop-on-quarantine” as an ops-mode, that can exist—but the default should keep the sim moving and surface quarantine counts as explicit incidents.

---

### 8.8 Exactly-what-happened: the minimum observability surfaces WSP should expose

Because receipts are the truth, the most useful “exactly what happened” view is:

**Run Streaming Summary (derived, not truth):**

* counts: ADMITTED / DUPLICATE / QUARANTINED
* by `event_type`
* last terminal order key (cursor)
* current sim window (`sim_now`, tick quantum)
* “in-flight” depth and oldest in-flight age (pressure indicator)

And the drill-down must be receipt-based:

* For any event, you can locate:

  * the **IG receipt**
  * if ADMITTED: the **EB coordinates** (partition/offset)
  * if QUARANTINED: the **quarantine_ref evidence bundle**

This aligns with the platform’s “audit truth is in durable receipts + refs, not in memory.”

---

### 8.9 Drift bans (things WSP must never do)

1. **Never treat “sent” as success.** Success is a terminal IG receipt (ADMIT/DUPLICATE/QUARANTINE).
2. **Never mint new ids on retry.** Same logical event ⇒ same `event_id`.
3. **Never advance the cursor past unknown outcomes.** Cursor advancement is receipt-gated and contiguous (gap-tracked), like DLA’s checkpoint law.
4. **Never bypass IG or pretend quarantine is “on the bus.”**

---

## 9) Security + governance posture (producer identity and allowed behavior)

This is where we make “WSP is the outside world” **safe** inside a closed-world platform: it can *feed* the bank, but it can’t *bend* the bank.

### 9.1 Where security *actually* lives in this network

**Pinned platform law:** publish/admit is controlled at **IG** (the front door), evaluated at least by `(producer, event_type, scope)` where scope includes ContextPins; unauthorized inputs are quarantined (never silently dropped). 

So WSP security is not “sprinkled everywhere.” It composes cleanly:

* **IG enforces producer identity + allowlists + run joinability + envelope correctness** (trust boundary).
* **EB enforces bus-level ACLs + quotas + “no side channels”** (traffic stream is IG-only).

That’s the choke-point model you already pinned: control happens where truth enters or outcomes change. 

---

### 9.2 Producer identity for WSP (what “who sent this?” means)

IG’s front door machinery is explicit:

* **AuthN is transport-derived** (mTLS identity or signed token for HTTP; authenticated producer creds for bus ingress), and **no unauthenticated traffic becomes an IntakeItem**.
* IG maps raw identity → canonical `producer_principal` (e.g., `svc:decision_fabric`, `ext:partner_X`) and applies alias rules to prevent spoofing.
* If the envelope includes `producer`, IG enforces **producer identity consistency**: mismatch → `PRODUCER_MISMATCH` quarantine.

**WSP design pin (v0):**

* WSP must have a single canonical principal name, e.g. **`svc:world_stream_producer`**, and must stamp `producer: "svc:world_stream_producer"` in the envelope so “who emitted this” is explicit and audit-friendly.
* Any mismatch between transport identity and claimed `producer` is **terminal quarantine** (security violation), not a retriable hold.

This gives you two independent, correlated identities:

1. transport-authenticated identity (unforgeable)
2. envelope-declared producer (human/audit visible)

---

### 9.3 What WSP is allowed to do (AuthZ as “rails”, not vibes)

IG’s policy gate is locked: **no event type is implicitly allowed**, and it allowlists `(producer_principal, event_type)` and binds it to class/run-scoped posture + routing profile.

So WSP must be governed the same way as any producer.

#### 9.3.1 Static allowlist posture (producer → event_type)

**Pinned WSP stance (already chosen earlier):**

* For engine-backed traffic, **`event_type = output_id`** (drift-proof).

Therefore IG policy must allow:

* producer `svc:world_stream_producer`
* event_types equal to the allowed engine traffic output IDs (or a controlled pattern set, if you choose patterns later).

#### 9.3.2 Scope + pin enforcement (run/world joinability)

IG’s run-joinability latch is explicitly pinned:

* If an event is run-scoped, IG must ensure it is joinable to a **valid (practically READY) run context**.
* IG resolves SR join surface by deterministic address (no scan/latest), validates run pins, and enforces **pin equality** against the run’s authoritative pins. Pin mismatch is terminal quarantine.

**WSP design pin (v0):**

* WSP traffic events are **always run-scoped**, and must include the full join pin set `{scenario_id, run_id, manifest_fingerprint, parameter_hash, seed}` (plus envelope-required fields).
* IG must treat missing pins as `PINS_MISSING` (quarantine) and mismatched pins as `PIN_MISMATCH` (terminal).

#### 9.3.3 Dynamic per-run allowlist (prevents a compromised WSP from “making up traffic”)

SR’s join surface contains `traffic_targets[]`: the declared engine output locators that SR has declared as traffic, and IG’s join-surface validator already enforces **traffic target hygiene** (targets must be business traffic; proof hooks must exist).

So we can (and should) use that as a second rail:

**WSP design pin (v0):**

* For WSP events, IG must additionally enforce:
  `event_type ∈ ValidatedRunFacts.traffic_targets[].output_id` for that `(scenario_id, run_id)`.

This is a big deal:

* Static allowlist prevents random event types.
* Dynamic run allowlist prevents “wrong traffic for this run,” even if the event type is generally allowed.

It also fits your “no oracle access / no drift” goal: the run plan is the authority, not the producer.

---

### 9.4 “No side channels” (how the bus makes bypass impossible)

Even if WSP is buggy or malicious, EB has a hard rail:

* **`fp.bus.traffic.v1` producer allowlist is IG-only** (including ingestion workers operating under IG’s identity).
* control stream producers are a governed set (SR/Registry/DL/RunOperate), not “anyone who feels like it.”

**WSP design pin:** WSP never publishes to EB directly. Even if it tried, EB’s access policy engine would reject because it isn’t the IG producer identity.

This is the mechanical reason the platform remains closed-world.

---

### 9.5 Security failures are still outcomes (quarantine + minimal evidence)

Platform rails require:

* quarantine is first-class, no silent drops, and correlation is mandatory. 

IG implements this explicitly:

* all failures route into quarantine with reason codes like `PRODUCER_MISMATCH`, `POLICY_DENY`, `PINS_MISSING`, etc. 
* quarantine bundles are immutable, by-ref, and include only minimal authz-deny details where appropriate (redaction guard).
* access to quarantine evidence is itself controlled and auditable (platform overlay A2).

**WSP design pin (v0):**

* Auth failures (`AUTHN_FAILED`, `AUTH_DENY`, `PRODUCER_MISMATCH`) must be quarantined with **minimal stored details** (no payload bloat, no sensitive leakage), while preserving `raw_input_ref` in secured storage when policy allows.

---

### 9.6 Governance: controlled changes must be explicit (R14 meets “stream pacing”)

You pinned: any change that can affect outcomes or reproducibility must be expressed as auditable governance facts (no invisible behavior changes).

Even though WSP doesn’t change domain time (`ts_utc`), **pacing absolutely can affect outcomes** indirectly:

* it can trigger throttles/rejects,
* it can trigger degrade posture via operational pressure,
* and it can change when downstream “sees” events (ingestion timing).

So:

**WSP governance pin (v0):**

* WSP operational controls that materially affect behavior must be **authority-fenced and auditable**, at least:

  * start streaming / stop
  * pause / resume
  * speed/pace change
  * mode change (`PULL` vs `STREAM` if you keep a compatibility window)

**Where those governance facts live (staying consistent with existing allowlists):**

* EB control stream is allowlisted to SR/Registry/DL/RunOperate, not WSP.
  So the clean v0 stance is:
* WSP exposes an admin control surface (fenced), and
* a governed control-plane actor (RunOperate or SR) emits the audit/control facts referencing WSP changes (so we don’t expand EB producer allowlists casually).

(We don’t need to build RunOperate right now, but the design authority should pin *that* the changes must be auditable, and *who* is allowed to publish those control facts.)

---

### 9.7 Minimal pinned decisions for WSP security (v0)

1. **WSP is a producer principal** (`svc:world_stream_producer`), authenticated at IG, and it stamps `producer` in the envelope; mismatch quarantines.
2. **IG allowlists WSP by `(producer_principal, event_type)`** and WSP uses `event_type = output_id`.
3. **WSP traffic is always run-scoped** and must carry full run/world pins; IG enforces SR READY + pin equality.
4. **IG additionally enforces per-run dynamic allowlist**: event_type must be declared in SR `traffic_targets[]` for that run. 
5. **No side channels**: EB traffic stream is IG-only; WSP never writes to EB.
6. **Auth/policy violations still yield explicit quarantine** with minimal security-safe evidence; quarantine access is controlled/auditable.
7. **Outcome-affecting WSP control changes are governed** (R14): fenced + auditable (likely via RunOperate/SR control facts).

---

## 10) Migration: replacing the pull assumption with push cleanly

The goal of migration is **not** “make pull faster.” It’s to **change the runtime network shape** so the platform experiences a bank-like outside-world stream, while **preserving** all the pinned platform rails:

* **SR stays the entrypoint authority** (READY + `run_facts_view`; downstream starts there). 
* **IG stays the only front door** (ADMIT/DUPLICATE/QUARANTINE + receipts; IG→EB is the only write path).
* **EB stays opaque durability** (at-least-once, partition-order; archive continues the same logical stream).
* **A1 “engine business traffic” currently assumes a legacy pull model** (SR READY → IG pull from engine outputs → wrap → admit).

So migration must do two things simultaneously:

1. **Add** WSP as the “outside world stream head” (push → IG).
2. **Prevent** the old A1 pull path from accidentally running at the same time (double ingestion).

---

### 10.1 The single most important migration pin: per-run “traffic delivery mode”

Right now, READY triggers IG’s legacy engine-pull ingestion job (B1/B2/B3…) and the EB doc’s A1 path is defined as pull.
If we introduce WSP without an explicit mode latch, you’ll get **two concurrent sources** for the same traffic targets (IG pull + WSP push), and the platform will “work” only because dedupe hides the error—until it doesn’t.

So we pin:

**[PIN] Every run declares a single `traffic_delivery_mode`, and exactly one mechanism is allowed to produce business traffic for that run:**

* `PULL` → legacy A1 path (IG Engine Pull Orchestrator runs).
* `STREAM` → new A1′ path (WSP streams; IG pull must not run).

**Where it lives:** SR truth surface, because SR already owns “runs carry explicit time/window keys” and “READY is meaningless without persisted ledger artifacts.”
Practically: it belongs in `sr/run_plan` and/or `sr/run_facts_view` (the map WSP and IG already read).

---

### 10.2 Define the two paths explicitly (so nobody “sort of” does both)

#### A1 (legacy) — Pull model (kept during migration)

This is what exists today:

`SR READY + run_facts_view → IG Engine Pull Orchestrator → Proof & Gate Enforcement → Traffic Framer → Admission → EB`

Keep it as a **supported mode** initially because:

* you already implemented it (or are wiring it)
* it’s a valuable fallback/backfill path even after WSP exists.

#### A1′ (new) — Stream model (the bank-like runtime)

The new shape is:

`SR READY + run_facts_view → WSP (outside-world pacing + framing) → IG (push admission) → EB`

**Key: IG remains the front door; EB write-side remains IG-only.**

---

### 10.3 How we prevent double ingestion (mechanical guardrails)

This cannot be left as “operator discipline.” It must be a hard network law.

**Guardrail 1 (IG):** if `traffic_delivery_mode=STREAM`, IG must **not** start the Engine Pull Orchestrator on READY.
IG’s own internals already make the legacy pull machinery explicit as “Pull model” M4, triggered by READY. We simply gate M4 behind the run mode.

**Guardrail 2 (WSP):** WSP must refuse to stream unless:

* run is READY, and
* `traffic_delivery_mode=STREAM`, and
* WSP can read `run_facts_view`.

**Guardrail 3 (IG policy):** WSP must be an explicitly allowlisted producer principal for the event types it will emit. IG already treats `(producer,event_type)` allowlisting as a first-class boundary and quarantines unauthorized producers instead of dropping.

---

### 10.4 What changes vs what stays invariant

#### What stays invariant (do not touch)

* **SR remains the entrypoint authority**; no component starts by scanning engine outputs.
* **IG admission outcomes** remain exactly one of ADMIT/DUPLICATE/QUARANTINE with receipts/evidence, and “ADMITTED iff EB append acked.”
* **Canonical envelope boundary** remains the same at IG. 
* **Consumers remain disorder-safe** (they already assume at-least-once + partition-order only).

#### What changes (and must be pinned)

* The **source of traffic candidates**:

  * Pull mode: candidates originate from engine rows read by IG’s pull machinery. 
  * Stream mode: candidates originate from WSP as already-framed canonical envelopes. (IG still validates; it just doesn’t *derive* from engine artifacts.)

This is why migration is “clean”: IG already supports both push and pull modes converging into the same admission spine.

---

### 10.5 The rollout plan (minimal friction, no redesign)

**Phase 0 — Add WSP but keep it inert**

* Implement WSP as a producer that can read `run_facts_view` and stream to IG.
* Default all runs to `traffic_delivery_mode=PULL` so nothing changes operationally.

**Phase 1 — Introduce the mode latch (the safety switch)**

* Add `traffic_delivery_mode` to SR’s run truth surfaces (plan/facts view). SR already pins “runs carry explicit time/window keys” and “facts view is the map.”
* Update IG READY handling so M4 (Engine Pull Orchestrator) only runs for `PULL`.
* Update WSP so it only runs for `STREAM`.

This phase is the real “migration plumbing.” Everything after is just turning the dial.

**Phase 2 — Shadow equivalence tests (small runs)**
For a small time window, run both modes **separately** (not simultaneously) and compare outcomes:

* compare the set of `(event_type, event_id)` admitted in EB,
* compare counts by event_type,
* compare quarantine reasons (should be identical unless WSP framing differs).

This gives you confidence that WSP is not quietly changing meaning—just delivery posture.

**Phase 3 — Flip default for local/dev to STREAM**
Once equivalence is proven:

* set `traffic_delivery_mode=STREAM` as the default in local/dev policy profiles for SR.
* keep `PULL` as a selectable fallback (especially for debugging and “import everything quickly” tests).

**Phase 4 — Deprecate pull as “ops/backfill only”**
Long-term target:

* `PULL` remains available for controlled ops use (e.g., rebuild, emergency re-ingest), but normal runs use `STREAM`.
* If you ever remove pull entirely, it should be done as a governed change because it affects operational playbooks. EB governance pins already demand that outcome-affecting ops changes be explicit facts.

---

### 10.6 The one subtle migration issue: evidence verification responsibility

Today’s A1 pull path explicitly states IG verifies gate PASS + instance proof before treating engine outputs as authoritative.
In A1′ stream mode, IG is no longer reading engine artifacts, so “gate verification by hashing bundles” doesn’t naturally belong inside IG.

Clean migration posture (minimal change, still defensible):

* **SR remains the verifier/attester** (it already cannot publish READY without required PASS evidence).
* **WSP is required to stream only from SR-declared traffic targets** in `run_facts_view`.
* **IG enforces run-joinability + dynamic per-run allowlist** (event_type must be one of the run’s declared traffic targets), plus the usual envelope/pins/policy checks.

If later you want “paranoid verification,” IG can optionally spot-check proofs (cache-based) — but that’s an optimization/hardening knob, not required for v0 migration.

---

### 10.7 Migration success criteria (what “clean” means)

Migration is “clean” when all of this is true:

1. For a run, exactly one of {IG pull, WSP stream} can produce traffic (mode latch enforced).
2. IG admission truth remains identical (receipts, quarantine evidence, EB coords).
3. Consumers don’t need to change—because they still consume admitted EB facts under at-least-once assumptions.
4. The platform experiences **time-unfolding traffic** (WSP pacing), eliminating the “bulk month ingest” behavior that caused your 2+ hour stall. 

---

## 11) Deployment and Environment Ladder

Absolutely — here’s how **WSP behaves when deployed across the environment ladder**, and the **tool stack** it should assume in each rung, staying aligned to your pinned deployment + ladder laws (same graph/rails everywhere; only the operational envelope changes).

---

### Pinned ladder rule for WSP

Across **local → dev → prod**, WSP must keep the **same meaning**:

* same **edges/joins** (SR READY + `run_facts_view` → WSP streams → IG admits → EB append),
* same **canonical envelope + pins**,
* same **no-future-leakage** streaming semantics,
* same **idempotency/duplicates tolerance** (at-least-once is real).

What is allowed to change by environment is only: **scale, retention/archive posture, security strictness, reliability posture, observability depth**.

---

### Deployment unit shape for WSP

WSP is best treated as a **deployment unit that behaves like an “always-on worker”**:

* It **consumes** control facts (READY) from `fp.bus.control.v1`,
* reads by-ref artifacts from S3-compatible object storage (`sr/run_facts_view`, engine traffic artifacts),
* and **pushes** canonical envelopes into IG (HTTP/gRPC push ingress), never to EB directly.

Local/dev/prod may *collapse* it (run as a CLI), but its **unit role** stays the same.

---

### Tool stack assumptions per rung

#### Reference “production-shaped local stack” (what WSP should assume)

From your deployment tooling notes, the reference local stack is:

* **Event Bus:** Kafka-compatible (Redpanda locally)
* **Object Store:** S3-compatible (MinIO locally)
* **DB:** Postgres (authoritative timelines; WSP may optionally store cursors/checkpoints as *derived* state)
* **Observability:** OTLP everywhere → OTel Collector + Grafana stack (Prometheus/Tempo/Loki/Grafana)

Local → dev → prod mapping is explicitly:

* **Local:** single-broker Redpanda + MinIO + Postgres + lightweight OTel
* **Dev:** same stack, possibly 3-broker Redpanda, stricter auth
* **Prod:** managed equivalents (Kafka-compatible, S3-compatible, Postgres, OTel pipeline)

---

### WSP behavior across the ladder

#### Local (laptop)

**Purpose:** fast iteration + deterministic reproduction, *without changing semantics*. 

**Runtime shape**

* Run WSP as either:

  * a single local process (CLI/worker), or
  * a container alongside the rest of the services (more “prod-shaped”).
* It still consumes READY from `fp.bus.control.v1` and streams to IG.

**Security (minimal friction, same mechanism)**

* IG already supports **API-key auth** and **rate limits**, plus an interim READY allowlist (run_id allowlist) while signed READY isn’t implemented.
* Local posture: permissive allowlists, but **auth still exists** (don’t bypass it), so failures surface early.

**Pacing + backpressure**

* Default to conservative, bank-like pacing:

  * small tick quantum (seconds/minutes),
  * coupled clock (slow down when IG rate-limits).
* Treat `429 RATE_LIMITED` as a normal operational signal (throttle/pause), not as “error spam.”

**Partitioning gotcha**

* Don’t make local “single partition forever.” EB docs explicitly warn that partition differences hide ordering bugs; local should mimic partitioned behavior enough to flush out assumptions. 

---

#### Dev (shared integration)

**Purpose:** integration realism; catch the failures prod would catch. 

**Runtime shape**

* WSP runs as an always-on worker deployment:

  * consumes READY in a consumer group,
  * uses a per-run single-stream latch (idempotent start) to avoid duplicate streamers.

**Security (real enough)**

* Stricter IG auth posture than local:

  * nontrivial allowlists,
  * stricter producer identity checks,
  * tighter rate limits and circuit-breakers.
* IG already tracks store-read failures and flips health RED on repeated failures — dev is where this should be exercised.

**Operational envelope**

* More partitions and more concurrency than local
* Medium retention windows
* Observability: dashboards + basic alerts (lag, rate-limit spikes, quarantine spikes).

---

#### Prod (hardened runtime)

**Purpose:** governed outcomes; no reliance on “human memory.” 

**Runtime shape**

* WSP is a first-class deployment unit with:

  * HA posture (multiple instances, but only one active per run via idempotent run-latch),
  * controlled operational controls (pause/resume/speed changes are governed).

**Security (strict)**

* Strong producer identity and tight policy:

  * only WSP principal can act as WSP,
  * only allowed event types (output_id allowlist),
  * only allowed runs (SR joinability checks enforced by IG).
* No side channels: EB traffic stream is IG-only at publish ingress.

**Reliability + recoverability**

* WSP restart/resume must be routine:

  * derived cursor/checkpoint state is allowed (DB/object), but correctness must remain receipt-driven (IG receipts + EB coords remain truth).

**Observability depth**

* Full SLO/corridor checks (rate limits, lag, error rates, quarantine) — because DL’s posture and “production reality” depends on it.

---

### Minimal substrate mapping for WSP (what it reads/writes)

In the same “deployment notes mapping” style:

* **Reads**

  * **Bus:** `fp.bus.control.v1` (READY)
  * **Object store:** `sr/run_facts_view/...` (join surface), engine traffic artifacts by locator
* **Writes**

  * **IG ingress:** HTTP/gRPC push (canonical envelopes)
  * **Optional derived state:** `wsp/stream_state/...` (cursor/checkpoint) in object store or DB (derived, rebuildable)
* **Emits**

  * OTLP metrics/logs/traces (same semantics local/dev/prod)

---
