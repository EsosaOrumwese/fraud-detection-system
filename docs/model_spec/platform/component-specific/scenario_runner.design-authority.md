# Scenario Runner Design Authority

This file is a rough collection of design or brainstorm notes for the Scenario Runner. It views the whole platform as a network and expands open the scenario runner's position in this network and illuminates it.

---

Here’s the **minimum-but-sufficient SR overview** that needs to be pinned in everyone’s head *before* we start slicing into joins/paths.

## 1) What SR *is* in this platform (one idea)

SR is the **platform’s world/run “entrypoint authority”**: it turns *an intended run* into a **joinable, evidenced, replay-safe run context** for the rest of the platform. The platform top-view literally pins SR as: invoke/reuse engine → verify PASS gates → write SR ledger → publish READY + `run_facts_view`.

SR is therefore **conductor + ledger**, and **system-of-record** for:

* run identity,
* readiness,
* and the downstream join surface (`run_facts_view`).

## 2) The single most important platform pin about SR

**Downstream starts from SR or it’s a bug.**
The join surface (`run_facts_view`) + the READY trigger (`run_ready_signal`) is explicitly the platform entrypoint; downstream is forbidden from scanning engine outputs, inferring “latest,” or independently picking the world.

So SR’s most important external job is: **make that entrypoint unambiguous and admissible**.

## 3) What SR publishes (and why those artifacts are “truth”)

Production posture says SR must persist (as truth):

* `sr/run_plan`
* `sr/run_record`
* `sr/run_status`
* `sr/run_facts_view`
  and also emit the READY signal on `fp.bus.control.v1`.

**Key meaning:** READY is meaningless without those persisted ledger artifacts (because READY is just the trigger; the facts view is the map).

## 4) SR’s boundaries (what SR must NOT become)

SR must **not** become any of these:

* the ingestion pipeline,
* the event bus,
* the feature plane,
* decisioning,
* action execution,
* labeling.

Those are owned elsewhere in the platform; SR stays “control-plane orchestration + join truth.”

In production mapping, SR can be a **job or service**, and may have an optional SR DB for convenience, but the **object-store ledger is the truth surface**. 

## 5) The invariants SR is not allowed to violate

These are the platform rails that bite SR directly:

### A) READY is monotonic (no silent undo)

Once SR declares READY, it does not “undo” READY. Corrections happen as a *new declared state or a superseding run story*, not by mutating history.

### B) “No PASS → no read” is SR readiness law

SR cannot legally declare READY unless the **required PASS evidence exists for the exact pinned scope**. This is platform-wide, not engine-only.

### C) By-ref truth transport (refs + digests, not payload copies)

Across boundaries, SR must publish **refs/locators (+ optional digests)**, not copied payloads. Digest mismatches are inadmissible (fail closed).

### D) End-to-end idempotency (assume duplicates)

The platform assumes at-least-once everywhere; SR invocations must be stable under duplicate requests and replays.

### E) Time semantics never collapse

SR must not “smuggle” an implicit now. Runs carry explicit time/window keys, and domain time vs ingestion time vs as-of time remain distinct across the platform.

## 6) SR’s relationship to the Data Engine (what SR can safely assume)

The engine interface pack pins these boundary truths SR must honor:

### A) Engine determinism + immutability by identity partition

For each output, identity is the **partition token tuple** (from the catalogue). For a fixed identity partition, the engine promises **byte-identical** outputs and write-once immutability; `run_id` may partition logs/events but must not change sealed outputs whose identity doesn’t include `run_id`.

### B) SR must treat the catalogue + gates as authoritative

* Outputs are discoverable via tokenized path templates; catalogue is the inventory of what exists and how it’s scoped.
* Gate verification is **gate-specific**, and SR must not assume a universal hashing method; SR follows `engine_gates.map.yaml` rules via portable receipts.
* Instance-scoped outputs require instance proof bound to an output locator + digest.

This is why SR’s join surface must be rich in **evidence pointers**, not just “here’s a fingerprint.”

## 7) SR’s relationship to IG/EB (the production-ready stance we’re sticking with)

Two pinned facts matter here:

1. **SR is control-plane; IG is trust boundary; EB is append/replay.** EB does not validate/transform. IG is authoritative for admit/duplicate/quarantine and receipts.
2. Only `business_traffic` is allowed to drive the hot path; audit/telemetry/truth products are never treated as decisionable traffic.

So in production-ready v0, SR’s job is:

* publish READY + `run_facts_view`,
* and that facts view must allow IG to deterministically pull only `business_traffic` outputs (by ref), wrap into canonical envelope if needed, and then admit/quarantine into EB.

## 8) The mental model to carry into join/path analysis

When we start digging into edges, keep this framing:

* **SR is a “declaration point.”** It declares: *this run exists, here are the pins, here are the admissible refs, here is the PASS evidence that makes them legal to consume*.
* **Everything else is downstream consequence.** IG/EB/consumers don’t decide what world to use; they verify and proceed from SR’s declaration.
* **If SR can’t evidence it, SR can’t READY it.** That one rule prevents 90% of drift.

---

Here’s the **full join/path atlas around Scenario Runner (SR)** **treating SR as an opaque vertex** (we do *not* open its internals yet). This is the set of **production-realistic** ways SR participates in the larger platform network, consistent with your pinned joins and the engine boundary.

---

## A) One-hop joins (SR’s adjacency list)

Think of each “join” as: **a durable artifact, a bus message, or a boundary call** that another component can rely on.

### 1) Upstream → SR (Run intent enters the platform)

**Caller / Run-Operate / operator tooling → SR** via a RunRequest (exact transport is implementation freedom; the *meaning* is fixed).

**Join tokens carried**: at least the ContextPins (`scenario_id`, `run_id`, `manifest_fingerprint`, `parameter_hash`) plus `seed` where applicable.

---

### 2) SR ↔ Data Engine (world-build handshake)

**SR → Data Engine**: SR invokes the engine via `engine_invocation` including at least `manifest_fingerprint, parameter_hash, seed, run_id, scenario_binding` (plus optional `request_id` for idempotency).

**Data Engine → Artifact store**: engine materialises outputs + PASS/FAIL evidence (gate receipts / flags) as authoritative completion evidence.

**SR ↔ Artifact store** (engine side): SR reads **output locators** + **gate receipts** and records the completion evidence set as part of the run’s ledger truth.

---

### 3) SR ↔ Artifact store (SR’s own authoritative ledger)

SR writes the SR-owned truth set:

* `sr/run_plan`
* `sr/run_record`
* `sr/run_status`
* `sr/run_facts_view`

This is not optional in production: **READY is meaningless without the ledger + facts view** being present and durable.

---

### 4) SR → Control Bus (platform entrypoint trigger)

SR publishes the **READY signal** to `fp.bus.control.v1`.

This join is pinned as the **platform entrypoint**: downstream starts here or it’s a bug.

---

### 5) Downstream components ↔ SR (join surface consumption)

**Downstream → Artifact store**: read `sr/run_facts_view` and follow refs; downstream is forbidden from scanning engine outputs or inferring “latest.”

---

### 6) Ingestion Gate ↔ SR (joinability enforcement + ingestion trigger)

IG uses SR’s join surface:

* **IG reads `sr/run_facts_view`** to enforce that producer traffic is joinable to a valid (in practice READY) run.
* IG is then the trust-boundary that admits/quarantines/duplicates and appends admitted facts to EB.

---

### 7) Offline Shadow ↔ SR (offline rebuilds depend on SR join surface)

Offline Feature Shadow explicitly reads `sr/run_facts_view` as an authoritative join artifact for rebuilds/training datasets.

---

### 8) Observability pipeline (non-domain but production-real)

SR emits OTLP telemetry like everything else (metrics/traces/logs), and Run/Operate uses the control bus + governance facts to manage runs/backfills (never silent).

---

## B) Multi-hop paths (the real “routes” through the graph)

Below are the **distinct production paths** that exist *even with SR opaque*. Each is a different route through the platform, using different joins.

### Path P1 — Happy path: build world → READY → ingest traffic

1. RunRequest → SR
2. SR → Engine invocation (or reuse evidence)
3. Engine → artifact store outputs + gate receipts
4. SR → writes `run_facts_view` + `run_status=READY`
5. SR → emits READY on `fp.bus.control.v1`
6. IG consumes READY + reads `run_facts_view` → pulls `business_traffic` outputs → admits/quarantines → appends to EB
7. EB → IEG/OFP/DF/AL/DLA etc.

---

### Path P2 — Duplicate submission (idempotent re-entry)

Same RunRequest (or same `request_id`) arrives twice:

* SR must not create a second logical run outcome; it reuses the already-anchored ledger truth.
* SR may re-emit READY (idempotently) pointing at the same `run_facts_view`.
* Downstream stays safe because it always joins from SR and duplicates are expected end-to-end.

---

### Path P3 — Reuse path (engine not invoked)

SR may complete without invoking the engine **only if** it can reconstruct the same completion evidence set for the requested pins (locators + required PASS receipts).

(Important: this is “reuse of evidence,” not “guessing that files exist.”)

---

### Path P4 — Engine failure path (dependency fail)

If the engine invocation fails:

* SR records a terminal non-READY outcome (`run_status` and `run_record` evidence),
* SR does **not** emit READY (ever).

---

### Path P5 — Missing/FAIL PASS evidence (quarantine/fail-closed)

If required PASS evidence is missing or FAIL:

* SR must not declare READY.
* SR records failure/quarantine with evidence pointers.

This is the SR-side expression of “no PASS → no read.”

---

### Path P6 — Post-READY correction (supersede, don’t mutate)

If something is later discovered after READY:

* SR does not “undo READY.”
* The correction route is a **new run** (or a new record that supersedes prior interpretation), never silent mutation of the original READY claim.

---

### Path P7 — Replay/rehydration path (control-plane re-emit)

SR can be asked to “replay the outward-facing outcome” of an existing run:

* read ledger + facts view,
* re-emit READY (or terminal signal) pointing at the same join surface,
* **no engine mutation, no “latest” reinterpretation**.

This is how you recover downstream after outages without breaking determinism.

---

### Path P8 — Offline rebuild path (training/analytics entrypoint)

Offline Shadow job consumes:

* EB/archive history + Label Store “as-of”
* and uses `sr/run_facts_view` as the run/world join anchor.

---

## C) Minimal “SR-centric graph” (so you can see it all at once)

```
Run/Operate / Caller
        |
        v
       [SR]  --invoke-->  Data Engine job
        |                   |
        |                   v
        |             artifact store: engine/... + gate receipts
        |
        +--> artifact store: sr/run_plan|run_record|run_status|run_facts_view
        |
        +--> fp.bus.control.v1 : READY (control fact)
                 |
                 v
          Ingestion Gate (IG)
            |      \
            |       \--reads--> sr/run_facts_view (joinability + what to pull)
            |
            +--> fp.bus.traffic.v1 admitted events -> EB -> hot path consumers

Offline Shadow job --reads--> sr/run_facts_view
```

All of that is directly pinned by your platform join definitions and deployment-unit mapping.

---

Great — these 4 joins are the **spine** of SR as a control-plane unit. I’m going to describe each join as:

* **What crosses the boundary (the “join artifact” or call)**
* **Who owns truth**
* **What MUST be true before/after the join**
* **How production reality (retries/duplicates) is handled**

All of this is pinned by your platform blueprint + deployment unit map + engine interface pack.

---

# 1) Upstream → SR

**(Run intent enters the platform)**

### The join, in one sentence

Upstream provides a **RunRequest** (scenario intent + explicit pins + explicit time key + idempotency posture), and SR responds by **anchoring a run identity + ledger stub** that is stable under retries.

### What upstream is allowed to be

Any of these can be the upstream “caller” (production-real): CLI/operator, scheduler, orchestrator, a run-launcher service, a backfill controller. Deployment notes explicitly treat SR as a batch-plane job that’s invoked explicitly (local CLI vs dev/prod launcher + worker).

### What must cross the boundary (minimum meaning, not a schema)

Upstream MUST supply enough to make the run **deterministic and replayable**:

1. **Scenario binding intent**
   Upstream expresses “what scenario is this” in a way SR can bind into `scenario_binding` for the engine. (Engine contract allows `scenario_id` or a finite `scenario_set`.) 

2. **World pins (explicit in v0)**
   **Designer declaration (locked):** v0 requires caller to provide `manifest_fingerprint` + `parameter_hash` explicitly. SR must not “pick latest PASS” in v0, because that’s exactly how drift sneaks in across environments. (If we ever allow selection later, the rule must be deterministic and recorded.)

3. **Time key (no hidden now)**
   Any time/window semantics must be explicit in the request (window id or explicit start/end/tz). Platform rails forbid implicit “today.”

4. **Idempotency key (run equivalence)**
   Upstream MUST provide an idempotency key for “same logical run” so SR can behave correctly under retries/duplicate submissions (which are assumed in an at-least-once world).

### What SR must do immediately on receipt (production posture)

SR’s first action is not “run engine.” It’s **pin the run**:

* Validate/normalize request (pins present; time key explicit; scenario binding resolvable). 
* Mint or accept **run_id** in a way that is stable under idempotency (same request ⇒ same run_id).
* Write initial SR ledger state to the artifact store: at least `run_record START` and `run_status = OPEN` (or equivalent). This is what makes the run exist as an auditable thing.

**Upstream-visible outcomes (outer behavior):**

* **Accepted**: SR returns/declares the `(scenario_id, run_id, manifest_fingerprint, parameter_hash)` pins for the run (even if execution happens later).
* **Rejected**: SR refuses to create a run (invalid pins/time key), and that failure is still observable (either as a terminal status artifact or a direct rejection response). In production we never want “silent nothing happened.”

---

# 2) SR ↔ Data Engine

**(World-build handshake)**

This is explicitly pinned as **J1** in the platform blueprint.

### The join, in one sentence

SR turns a run request into **engine completion evidence**: **output locators + PASS/FAIL receipts**, recorded so it can be replayed later.

### What SR sends (call boundary)

SR invokes the engine with an `engine_invocation` containing at least:
`manifest_fingerprint, parameter_hash, seed, run_id, scenario_binding` (+ optional `request_id` for idempotency at the invocation boundary).

Two crucial pins here:

* `seed` is required at engine invocation and is treated as a “run realisation” key (separate from ContextPins).
* `run_id` may partition logs/events but MUST NOT change bytes of outputs whose identity does not include `run_id`.

### What the engine “returns” (not a boolean)

Engine completion is not “success=true.” It is an **evidence bundle**:

* **Output locators**: portable references to produced artifacts (`engine_output_locator`).
* **Gate receipts**: portable PASS/FAIL objects (`gate_receipt`) scoped to the exact identity.

### The gating law SR must apply (non-negotiable)

* “No PASS → no read” applies at SR readiness time too: SR must not declare READY without required PASS evidence.
* Gate verification is **gate-specific** (no universal hashing assumptions).
* Instance-scoped outputs require instance proof bound to locator + digest (so the facts view can be consumed fail-closed).

### “Reuse” is allowed, but only as “reuse of evidence”

SR may skip engine invocation **only if** it can reconstruct the same completion evidence set (locators + required PASS receipts) for the requested pins, and it must record that choice as an auditable fact.

---

# 3) SR ↔ Artifact Store

**(SR’s own authoritative ledger)**

This is pinned as production truth: SR must persist its ledger + join surface under `sr/…`, and READY is meaningless without them.

### The join, in one sentence

SR writes a **durable, replay-safe run ledger** whose artifacts are the system-of-record for readiness and joinability.

### What SR must persist (truth artifacts)

Minimum persisted truth in object store:

* `sr/run_plan`
* `sr/run_record`
* `sr/run_status`
* `sr/run_facts_view`

An optional SR database may exist for indexing/query convenience, but the authoritative truth surface is the object-store ledger.

### What each ledger artifact *means* externally (so consumers don’t guess)

* **run_plan**: “what SR intended to do” (including required gates).
* **run_record**: append-only narrative of “what happened” (attempts, reuse selection, outcomes).
* **run_status**: the current declared lifecycle state (OPEN/READY/FAILED/QUARANTINED…), monotonic.
* **run_facts_view**: the **join surface map**: pins + engine evidence pointers + output locators + PASS receipts needed to treat refs as admissible.

### Production-grade write ordering (this matters)

**Designer declaration (locked): READY publication is a *commit*, not a vibe.**
So SR must seal the ledger in an order that avoids “READY points to missing facts view”:

1. Write/append `run_record` progress as SR works (append-only).
2. Write `run_facts_view` as a complete map (by-ref locators + receipts).
3. Write `run_status = READY` only after facts view exists.
4. Only then emit READY on the control bus.

This ordering is what makes downstream safe under retries, restarts, and eventual consistency.

### Monotonicity law at the store boundary

Once `run_status=READY`, SR does not later flip it to FAILED. Corrections are new declared states/run stories, not silent mutation.

---

# 4) SR → Control Bus

**(Platform entrypoint trigger)**

The control bus topic is explicitly pinned (`fp.bus.control.v1`) and SR’s READY signal is pinned as the platform entrypoint trigger.

### The join, in one sentence

SR emits a **low-volume control fact**: “Run X is READY; here is the facts view pointer,” and that is the only legal trigger for downstream progression.

### What must be in the READY signal (meaning, not fields)

* Identity pins (ContextPins + any explicit time key).
* A **pointer/ref to `sr/run_facts_view`** so consumers never guess.
* An idempotency identity for the signal itself (because the bus is at-least-once; duplicate READY messages must be safe).

### When SR is allowed to emit READY

Only after the ledger is sealed (facts view exists + status says READY). READY is monotonic and not withdrawn.

### What downstream is allowed to do on READY (and nothing else)

On READY:

1. read `run_facts_view`
2. follow locators
3. verify PASS receipts where required
4. proceed

Downstream is forbidden from scanning engine outputs or inferring “latest.”

---

## The “golden four-hop handshake” (ties all 4 joins together)

```
(1) Upstream -> SR: RunRequest (explicit pins + explicit time key + idempotency)
(2) SR -> Engine: engine_invocation (pins + seed + run_id + scenario_binding)
(3) SR -> Store: sr/* ledger + run_facts_view (locators + PASS receipts)
(4) SR -> Control Bus: READY(signal) -> points to run_facts_view
```

This is exactly the production-shaped control-plane story your platform blueprint pins for “world/run orchestration.”

---

Perfect — these four are where SR stops being “just a runner” and becomes the **platform’s join authority** in practice.

I’ll keep the same lens as before: **what crosses the boundary**, **who owns truth**, **what must be true**, and **how production realities (duplicates/retries/backfills) behave**.

---

## 5) Downstream components ↔ SR

### Join surface consumption (the platform entrypoint)

### What crosses the boundary

Two things, and they have different meanings:

* **`run_ready_signal` (trigger)**: “a run is joinable; go read the map.”
* **`run_facts_view` (map)**: “these are the pinned refs + required PASS evidence you must use.”

### Who owns truth

SR is authoritative for the *existence + readiness + mapping* of the run (ledger + facts view). Downstream must not invent a different source of readiness.

### What downstream is forbidden to do (hard pin)

Downstream must **not**:

* scan engine outputs,
* infer “latest run,”
* or independently decide what world to use.

### What downstream must do (hard pin)

* Start from READY → fetch facts view → follow refs → treat PASS receipts as prerequisites (“no PASS → no read”).

### Production behavior (retries / duplicates / ordering)

* **READY is monotonic**: SR doesn’t “undo” READY; corrections are new declared state/stories, not silent mutation.
* **READY can be duplicated** (at-least-once control bus): consumers must treat READY as idempotent and safe to process multiple times.
* **Safety rule for consumers**: if READY arrives but `run_facts_view` isn’t readable yet (eventual consistency), consumer waits/retries; it must not “guess” the world. (This is why SR’s publish ordering matters, but that’s SR-internal.)

### Who are “downstream consumers” here?

In practice:

* **IG ingestion worker** (pulls business traffic after READY)
* **IEG/OFP projectors** (start consuming admitted traffic, but still rely on SR for run identity/join discipline)
* **DF/AL/DLA** (when producing/validating provenance, SR pins what “this run” means)
* **Offline Shadow** (uses SR join surface as an anchor, see join #7)

---

## 6) Ingestion Gate ↔ SR

### Joinability enforcement + ingestion trigger (trust boundary)

This join has **two production modes** (both pinned, both real):

### 6A) Joinability enforcement for any incoming traffic

**Purpose:** IG must refuse “best effort” joins. If an event claims run/world membership, IG enforces that it’s joinable to a valid run context (in practice: READY) or quarantines/holds.

* **What IG reads from SR:** `sr/run_facts_view` (and/or SR ledger pointers) to verify that the run exists and is READY/joinable.
* **What IG decides (authoritative):** exactly one of **ADMIT / DUPLICATE / QUARANTINE**, with receipts/evidence. IG must not “silently fix” bad inputs into good ones; if it can’t anchor, it quarantines.

### 6B) v0 ingestion trigger for synthetic engine “business traffic” (pull model)

**Pinned v0 stance:** SR does **not** push traffic. SR emits READY; IG (or an IG-managed ingestion worker) consumes READY and pulls the engine’s `business_traffic` outputs referenced in `run_facts_view`, wraps to the canonical envelope if needed, and then admits to EB.

Key pins that make this production-clean:

* **Selection rule:** ingest **only outputs labeled `business_traffic`**; never `truth_products`, `audit_evidence`, or `ops_telemetry`.
* **Envelope rule:** anything admitted as traffic must conform to the canonical event envelope (native or via lossless wrapper/mapping at ingestion).
* **Evidence rule:** IG can require that the facts view includes (or points to) the relevant PASS receipts for the pulled outputs—because the platform law remains “no PASS → no read.”

### Production behavior (duplicates/retries)

* **READY duplicates → ingestion must be idempotent**: IG should dedupe pulls/admissions and emit DUPLICATE receipts where appropriate, but downstream must still be safe if duplicates slip through.
* **IG is truth for “admitted”**: “ADMITTED” must mean durably appended to EB; EB is append/replay only (no validation).
* **Operational reality:** IG maintains a receipt/quarantine index DB for fast checks, but the authoritative evidence is also persisted (quarantine evidence in object store).

---

## 7) Offline Shadow ↔ SR

### Offline rebuilds depend on SR join surface

### What crosses the boundary

Offline Shadow reads SR artifacts to avoid “mystery datasets”:

* it uses SR’s run identity + join surface as the **anchor** for offline replay/rebuilds.

### Why SR matters to Offline Shadow (production truth)

Your history/backfill overlay pins: **rebuild basis must be explicit**, watermarks are monotonic, archive is a continuation of EB, and dataset manifests are the unit of reproducibility.

So Offline Shadow must be able to say:

* “I rebuilt *this* dataset for *this* run/world context,” not “I grabbed history.”
  SR’s `run_facts_view` provides the authoritative “this run/world” anchor that prevents drift.

### How the join works in practice

* Offline Shadow uses SR join surface to get **world pins** and (when needed) **engine context surfaces** by locator (by-ref posture).
* Offline Shadow’s own outputs (datasets) must declare an explicit **replay basis** (offset ranges/checkpoints or windows anchored to offsets).
* Shadow then produces a **DatasetManifest** pinning: replay basis, label as-of boundary, join keys/entity scope, feature definition versions, digests/refs, provenance.

### Production behavior (backfills / late truth)

* Archive is a continuation of EB (same logical events); rebuilds can replay from archive as if it were EB, but the basis must be recorded.
* Backfills are declared and auditable; they produce new derived artifacts/manifest revisions — never stealth overwrites.
* Watermarks remain monotonic even under backfill; “as-of time T” is achieved by explicit replay basis, not by pretending the stream changed.

---

## 8) Observability pipeline ↔ SR

### Non-domain but production-real

This is a “join” because observability is how the platform stays governable and explainable in production.

### What crosses the boundary (minimum baseline)

SR must emit:

* telemetry (logs/metrics/traces) with the **correlation keys** that make platform facts joinable, and
* governance/audit facts when outcomes could be affected by config/policy changes.

### Correlation pins SR must propagate

Your observability baseline pins that telemetry must carry the applicable subset of:

* world/run scope: `run_id`, `scenario_id`, `manifest_fingerprint`, `parameter_hash` (+ `seed` when seed-variant)
* event scope: `event_id`, `event_type`, `schema_version`, `ts_utc`
* trace scope: `trace_id`, `span_id`

For SR specifically, the “production important” observability facts are:

* request id / idempotency key
* chosen mode (invoke vs reuse)
* engine invocation duration + outcome
* which gates were required + PASS/FAIL
* when READY was committed + emitted

### Environment ladder + change control (pinned)

* Local/dev/prod differ only by **profiles** (wiring + policy strictness), not by code forks that change meaning.
* Any outcome-affecting change (policy/config revisions) must emit an auditable governance fact with propose→approve→activate→rollback lifecycle.
* Secrets are injected at runtime; provenance references only secret identity, never secret material.

### Practical “truth mapping” reminder

The object store is by-ref substrate; it doesn’t own meaning. The **writer component** (SR here) is authoritative for its artifact family. So observability for SR must always be able to point back to SR-authored ledger artifacts when explaining “what happened.”

---

Below are the **production-real** multi-hop routes P1–P4, written as **network flows** (SR still treated as a black box, but we’re explicit about what must be true at each boundary).

I’m going to assume (as pinned) that SR’s job is: **invoke or reuse Data Engine → verify required PASS gates → write SR ledger (`sr/...`) → publish RunReadySignal + `run_facts_view`**.

---

## P1 — Happy path: build world → READY → ingest traffic

### Route (what happens, in order)

**Phase 0 — Run intent becomes a durable run**

1. Upstream submits a RunRequest.
2. SR **anchors the run** by persisting the SR ledger artifacts (at least starting `run_record`, and a non-READY `run_status`, plus a draft `run_plan`). SR may use an optional `sr` DB for indexing, but **truth is the object-store ledger**.

**Phase 1 — SR triggers world build**
3) SR calls the engine using `engine_invocation` with the required fields:
`manifest_fingerprint`, `parameter_hash`, `seed`, `run_id`, `scenario_binding` (and optionally `request_id` as an idempotency key at the invocation boundary). 
Note the pinned meaning of `run_id`: it **may partition logs/events** but **must not change bytes** of outputs whose identity doesn’t include `run_id`.

**Phase 2 — Evidence appears (engine → object store)**
4) Engine materialises outputs under `engine/...` and produces gate evidence (PASS/FAIL artifacts / receipts).
5) SR gathers **portable evidence**:

* `engine_output_locator` refs for the outputs it wants to pin in run facts. 
* `gate_receipt` objects (PASS/FAIL) for required gates. 

**Phase 3 — SR seals the join surface**
6) SR verifies “No PASS → no read” (gate verification is gate-specific; SR must fail closed if evidence is missing/unknown).
7) SR writes `sr/run_facts_view` (pins + output locators + the PASS evidence needed for consumers to proceed without guessing) and then updates `sr/run_status=READY`.
8) SR publishes **READY** on `fp.bus.control.v1`, with a pointer to the facts view (READY is meaningless without the `sr/...` artifacts).

**Phase 4 — Traffic ingestion happens (pull model)**
9) IG consumes READY and uses `sr/run_facts_view` as the sole “what to ingest / what run is this” source.
10) IG pulls **only outputs marked `business_traffic`** (never truth/audit/telemetry), wraps them into the **canonical event envelope** if needed, then admits/quarantines/duplicates and appends admitted events to `fp.bus.traffic.v1` (EB).

### P1 invariants (what must be true)

* Downstream does not start from the engine; it starts from **READY → `run_facts_view` → refs**.
* SR must not emit READY until the facts view exists and required PASS evidence is present.
* Anything admitted to traffic must satisfy the canonical envelope boundary (`event_id`, `event_type`, `ts_utc`, `manifest_fingerprint`, etc.). 

---

## P2 — Duplicate submission: idempotent re-entry

This is the “at-least-once reality” route: the same RunRequest arrives twice (retries, user double-click, orchestrator replay).

### Route variants (three realistic cases)

**Case A — Duplicate arrives while run is in progress (non-READY)**

1. Upstream repeats the same request (same run-equivalence / idempotency intent).
2. SR resolves it to the **same logical run** (same anchored ledger) and does **not** create a second truth surface. It may append an “idempotent re-entry observed” note into `run_record` for auditability.
3. SR returns/indicates current `run_status` and continues the already-in-progress attempt(s).

**Case B — Duplicate arrives after READY**

1. SR looks up the existing ledger + facts view and simply **replays the outward result**:

   * re-emit READY on `fp.bus.control.v1` is allowed (bus is at-least-once anyway),
   * but the READY points to the same facts view.
2. IG (and any other consumers) must treat READY as idempotent; duplicate READY must not cause double-admission (IG dedupe is part of its truth ownership).

**Case C — Duplicate arrives after a failure**

1. SR still maps it to the same logical run (same ledger), and then you get a policy choice:

   * **auto-retry** within the same run_id (append attempt history in `run_record`), or
   * require a new upstream idempotency key to create a new run.
     Either way, SR does not allow “silently create a second run that looks like the first.” (That creates drift.)

### Key pin for P2

There are **two idempotency layers** you can exploit safely:

* Upstream → SR: *run equivalence key* (what “same run” means).
* SR → Engine: `engine_invocation.request_id` (optional, client-provided) to avoid double-invoking the engine if the SR-to-engine call is replayed. 

---

## P3 — Reuse path: engine not invoked

This route exists because production systems restart, recover, and sometimes explicitly request “reuse”.

### What “reuse” is (pinned meaning)

**Reuse = reuse of evidence**, not “guess that outputs exist.” SR can skip engine invocation **only if** it can reconstruct a complete, admissible evidence set:

* the required output locators, and
* the required PASS receipts (and any instance proofs when outputs are instance-scoped).

### Route (what happens)

1. Upstream submits RunRequest.
2. SR anchors or locates the run ledger.
3. SR performs a **deterministic evidence check**: using the known pins and the engine’s addressing rules, it checks for:

   * the expected locators (or directly resolved output paths),
   * and required PASS receipts / gate artifacts, per the “No PASS → no read” rule.
4. If evidence is complete, SR writes `run_facts_view`, sets `run_status=READY`, emits READY.

### Two important production caveats (designer-locked)

* If the run requires **run-scoped logs/events** (outputs whose identity includes `run_id`), reuse must be consistent with that run_id. The engine contract explicitly treats `run_id` as a partition key for logs/events.
* If evidence is partial, SR does **not** “partial READY.” It either invokes the engine (if safe) or fails/quarantines (P4).

---

## P4 — Engine failure path: dependency fail

This covers both “engine didn’t run” and “engine ran but you can’t legally declare READY.”

### Route variants (two real failure shapes)

**Failure shape A — Invocation/execution failure**

1. SR invokes engine, but the job fails (crash, infra, timeout).
2. SR records a terminal non-READY outcome in its ledger (`run_record` notes, `run_status` reflects failure).
3. SR does **not** emit READY.

**Failure shape B — Evidence failure (gates FAIL or missing)**

1. Engine produces outputs but required gate receipts are FAIL, missing, or unverifiable.
2. SR applies “No PASS → no read” and refuses to READY.
3. SR records the evidence pointers (what gate failed / what’s missing) so the outcome is auditable and fixable.

### What happens next (production realism)

* **Retry policy lives at SR/control plane**, not in downstream guessing. If SR retries, it does so as a new attempt recorded in `run_record` (same logical run unless the upstream changes the run-equivalence key).
* IG never starts ingestion (because ingestion is triggered from READY in the pull model).

---

Alright — here are **P5–P8** as **production-real routes**, with SR still treated as an **opaque vertex** (we’re only describing boundary-visible behavior + invariants).

---

## P5 — Missing/FAIL PASS evidence (quarantine / fail-closed)

This path exists because your platform law is: **No PASS → no read**, and missing/unknown evidence must **fail closed**.

### Route shape (what actually happens)

1. **Upstream → SR** submits a RunRequest.
2. **SR → engine / or reuse-evidence check** begins.
3. Engine writes some outputs, but SR cannot assemble a complete admissible evidence set:

   * required gate receipt is **FAIL**, or
   * required gate receipt is **missing/unverifiable**, or
   * required instance-proof binding (locator+digest) is missing for an instance-scoped output.
4. **SR must not emit READY.** This is a hard platform pin: “READY is binary; no half-ready.”
5. SR writes/updates its ledger to a **non-READY outcome** and includes an **evidence trail** (what gate failed / what’s missing / where the partial artifacts are).

### What “fail-closed” means here (important)

* Consumers must treat missing/unknown gate status as unsafe: `gate_receipt` explicitly says consumers **must fail closed** on missing/unknown status. 
* Engine gate verification is **gate-specific** (no universal hash method assumptions), so SR must either verify per `engine_gates.map.yaml` or refuse to READY. 

### Two production-real sub-branches

* **P5a: “Not ready yet” (evidence may still arrive)**

  * SR stays in an OPEN/WAIT state until the expected PASS evidence appears (eventual consistency / engine writing lag).
  * No READY is emitted until the evidence set is complete.

* **P5b: “Fail / quarantine” (evidence is FAIL or structurally impossible)**

  * If the required gate outcome is FAIL (or the required outputs cannot be referenced deterministically), SR marks the run as failed/not-ready and retains the failure evidence.
  * There is **no legitimate downstream path** to proceed anyway (your platform explicitly pins this).

### What happens to ingestion (IG) in P5

Because v0 ingestion is **triggered from READY**, WSP streams into IG (push); IG does not initiate a pull route by default.
If any producer tries to send “traffic” anyway, IG enforces joinability by consulting SR’s join surface; without READY/joinability it quarantines (it’s literally IG’s job).

---

## P6 — Post-READY correction (supersede, don’t mutate)

This path exists because production reality includes: discovered bugs, policy mistakes, late discoveries — **after** a run was declared READY. Your pinned rule is: **don’t rewrite history; supersede it**.

### The core pinned constraints that shape P6

* **SR run ledgers are append-only “with supersedes”** (no stealth edits).
* **Engine outputs for a pinned identity are immutable**; a “correction” to the engine world is a **new identity/version**, not overwriting the old bytes.
* Any change that can alter derived truths (projections/features/datasets/parity) is a **declared backfill**, auditable, with explicit basis.

### Route shape (what actually happens)

1. A run is already READY (facts view exists; READY was emitted).
2. Something is discovered that means “we shouldn’t treat this READY as the preferred world/run anymore.”

There are **two distinct correction classes**, and they behave differently:

#### P6-A: Correction to SR’s *control truth* (bookkeeping / signaling)

Example: READY signal missed; or the facts view needs an additional pointer that already existed but wasn’t published.

* SR **does not change the past**; it appends a corrective note and/or publishes a re-emit (P7).
* Crucially: this correction does **not** claim the world changed; it claims SR is making the control-plane mapping easier to consume.

#### P6-B: Correction to *world truth* (engine/policy/data mistake)

Example: wrong manifest, wrong parameters, a bug in engine version, wrong policy profile — i.e., the world materialization should not be used.

* SR cannot “fix” the old run. Instead:

  1. SR triggers a **new run** (and likely a **new world identity**, e.g., new `manifest_fingerprint` / `parameter_hash` / policy revision).
  2. The new run goes through the normal P1 flow and becomes READY with a new join surface.
  3. SR records a **supersedes relationship**: “run B supersedes run A for purpose X.” (This is append-only truth, not mutation.)
  4. The correction/backfill operation is **declared and auditable** (who/why/scope/basis).

### What this buys you (production safety)

* You never create time-travel: downstream can explain “what we did then” vs “what we do now.”
* Offline training can build “as-of then” vs “as-of now” datasets without confusion.

---

## P7 — Replay/rehydration path (control-plane re-emit)

This route exists because:

* buses drop messages,
* consumers restart,
* environments get rehydrated,
* you might want to “kick” ingestion/replay without re-running the engine.

Your deployment map explicitly pins that SR’s truth is the **object-store ledger** (`sr/run_*`) and the bus READY signal is the **trigger**. That means re-emit is a normal operational move.

### Route shape (what actually happens)

1. Run/Operate (or an operator) asks: “re-emit control facts for run(s) X” (because consumers missed it, or you’re restoring a pipeline).
2. SR reads:

   * `sr/run_status`
   * and the referenced `sr/run_facts_view` (if READY).
3. If the run is READY:

   * SR re-publishes **the same semantic READY** to `fp.bus.control.v1`, pointing to the same facts view.
   * This must be safe under duplication because the control bus is at-least-once.
4. If the run is not READY:

   * SR may publish an explicit “not ready / failed” control fact, or it may stay silent and rely on the ledger (implementation choice).
   * Either way, it must never emit READY.

### What re-emit is *not*

* It is not traffic replay (EB/Archive handles that).
* It is not world recomputation (engine invocation is not implied).
  It’s purely “replay the platform entrypoint trigger so consumers can re-join correctly.”

---

## P8 — Offline rebuild path (training/analytics entrypoint)

This route is governed by your **History/Backfill overlay**: archive is a continuation of EB; replay basis must be explicit; watermarks are monotonic; dataset manifests pin the basis.

### Route shape (what actually happens)

1. An offline job (Shadow / analytics / training prep) selects a target:

   * one or more SR runs, or
   * a time/window scope, or
   * a declared backfill operation.
2. The job anchors the work using SR’s join surface:

   * it reads `sr/run_facts_view` to get the pinned world/run context (and any engine locators if needed).
3. It reads **admitted facts** from:

   * EB if within retention, or
   * **Archive** beyond retention (archive is explicitly “EB’s continuation,” same event identity + envelope semantics).
4. It declares an explicit **replay basis**:

   * offset ranges per partition (preferred), or
   * time windows anchored to recorded checkpoints/watermarks.
5. It joins labels using **as-of semantics** (so “what we knew then” vs “what we know now” datasets are both possible and not confused).
6. It produces a **DatasetManifest** that pins:

   * replay basis,
   * label as-of boundary,
   * join keys/entity scope,
   * feature definition versions,
   * digests/refs to materializations,
   * provenance.

### The key invariants that make this “production-ready”

* **Archive addressing is by-ref and pinned** (no vague “grab history”).
* **Backfill is declared and auditable**; it produces new derived artifacts, not stealth overwrites.
* **Watermarks don’t lie**: applied offsets are treated as monotonic; you don’t “go backward” — you define a basis.

---

### One designer “glue” observation (ties P5–P8 together)

All four paths hinge on the same backbone principle you’ve pinned:

> **SR has one job at this boundary: produce a join surface whose references are admissible.**
> If it can’t evidence it, it can’t READY it.

---

Yeah — the environment ladder changes **how hard the platform is pushed**, not **what any join/path *means***. The key pin is: **local/dev/prod run the same platform graph + rails/join semantics; only the operational envelope differs** (scale, retention/archive, security strictness, reliability, observability).

Here’s what that implies *specifically* for the SR joins + P1–P8 routes.

---

## What must NOT change across environments (or you’ve built 3 platforms)

### Meanings of the control words

The words **READY, ADMITTED, ACTIVE, BACKFILL, LABEL AS-OF** must mean the same thing everywhere.
So:

* **READY** always implies: durable `sr/*` ledger + `run_facts_view` exists + required PASS evidence exists.
* **ADMITTED** always implies: IG wrote to EB and issued receipts (not “it looked okay locally”).

### Rails/join semantics must be identical

ContextPins discipline, canonical envelope boundary, no-PASS-no-read, by-ref locators, idempotency, append-only + supersedes, watermark semantics — these are invariant across the ladder.

### The deployment-unit roles don’t change (even if local collapses them)

Local can “collapse” runtime units for convenience, but SR/Engine/IG/etc. must still behave as independent units with real durable dependencies. (SR + Engine + Offline Shadow are **jobs**; IG/DF/AL/DLA/DL are **always-on**).

---

## What *can* change across environments (and how it hits the paths)

### 1) Security strictness (biggest join-path difference)

* **Local**: permissive allowlists/credentials are okay, but **IG still must admit/quarantine**; SR still must refuse READY without PASS.
* **Dev**: “real enough” authz to catch failures you’d see in prod (unauthorized producers, quarantine access, registry privileges).
* **Prod**: strict change control and access; nobody gets to “just fix it.”

**Implication for paths:**
P5 (missing/FAIL PASS) must be *easy to observe* locally, *common to test* in dev, and *strictly governed* in prod.

### 2) Retention + archive (changes feasibility of P8, not meaning)

Retention length is an environment knob, but **offset/watermark/replay semantics cannot change**.

* Local: short retention; archive may be off.
* Dev: medium retention; archive optional but recommended for realism.
* Prod: longer retention + archive for long-horizon rebuilds.

**Implication for paths:**

* P8 (offline rebuild) must work from **EB retention OR archive**; only the availability horizon changes.
* Replay basis must always be explicit (offset ranges/checkpoints), regardless of env.

### 3) Observability depth (changes how you *prove* paths, not path behavior)

Local should still run a “production-shaped” OTel pipeline (collector + metrics/traces/logs) so degrade/corridor-check concepts aren’t hand-waved.
Prod adds SLOs/alerts/governance dashboards, but trace correlation semantics remain identical.

**Implication:** P2/P7 (duplicates + re-emit) are where observability matters most — you need to prove “this was idempotent” and “this was a rehydration.”

---

## Path-by-path: what the ladder changes (and doesn’t)

### P1 Happy path

* **Invariant**: SR commits ledger → emits READY → IG pulls business_traffic → admits to EB.
* **Ladder effect**: scale and reliability differ; local may run everything on one machine, but must keep the same ordering and trust boundary semantics.

### P2 Duplicate submission

* **Invariant**: duplicates are expected; SR and IG must be safe under at-least-once.
* **Ladder effect**: local won’t naturally hit duplicates often, so you must *force-test* P2 in local/CI and dev (the ladder explicitly calls for end-to-end integration flows).

### P3 Reuse (engine not invoked)

* **Invariant**: reuse is “reuse of evidence” (locators + PASS receipts), never “guess outputs exist.” (This is the same in local/dev/prod.)
* **Ladder effect**: local will use reuse more to iterate quickly; prod may require stricter policy checks / audit trails for reuse decisions — but the semantics remain “evidenced join surface or no READY.”

### P4 Engine failure

* **Invariant**: no READY if engine fails; SR records failure evidence.
* **Ladder effect**: prod expects more HA/retry tooling, but SR’s *meaning* doesn’t change (a failure is a failure).

### P5 Missing/FAIL PASS

* **Invariant**: fail-closed; no READY without complete PASS evidence.
* **Ladder effect**: dev is where you verify “prod-like strictness catches the right things” (missing PASS, unauthorized producers).

### P6 Post-READY correction

* **Invariant**: **supersede, don’t mutate** (SR ledgers append-only with supersedes; engine outputs immutable by identity).
* **Ladder effect**: prod requires governance/approvals for backfills and policy changes; local/dev should still use the same mechanism, just with lighter friction.

### P7 Replay/rehydration (control-plane re-emit)

* **Invariant**: re-emit READY from the ledger is a normal recovery tool; duplicates must be safe.
* **Ladder effect**: this becomes *operationally essential* in prod; in local it’s a convenience — but behavior is identical.

### P8 Offline rebuild (training/analytics entrypoint)

* **Invariant**: archive is a continuation of EB, replay basis explicit, manifests are the unit of reproducibility.
* **Ladder effect**: local may not support horizons beyond retention unless archive is enabled; prod should. But the read pattern is the same: **by-ref + pinned basis**.

---

## The one practical takeaway for SR design

When we later open SR’s internals, SR must be written so it can run under **profiles** (local/dev/prod) where only these knobs vary:

* retention/archive settings,
* security/policy revs,
* observability depth,
* scale/reliability settings,

…but **the commit logic for READY and the contents/meaning of `run_facts_view` cannot vary**. That’s explicitly the ladder’s “no drift” rule.

----

Yep — here’s the **environment profile knob set** (and the few **deployment truths** you should hold in your head) for SR *while it’s still an opaque vertex*.

Everything below is anchored in your environment ladder + deployment-unit map + config/change-control pins.

---

## 0) The SR deployment shape you should assume (before internals)

* **SR runs as a job/service**:

  * **local**: CLI / job runner
  * **dev/prod**: control-plane “run launcher” + worker execution (can still be a single service that spawns jobs)
* SR’s **authoritative writes** are fixed:
  **object store:** `sr/run_plan`, `sr/run_record`, `sr/run_status`, `sr/run_facts_view`
  **bus:** `fp.bus.control.v1` READY signal
  **optional DB:** `sr` index DB (non-truth convenience)
* Environment ladder pin: **local/dev/prod must keep the same semantics/rails; only the operational envelope changes** (scale, security, retention/archive, reliability, observability, cost).

---

## 1) Profiles come in two layers (this is the most important “knob model”)

You’ve pinned that **policy config** and **wiring config** must be separated:

### A) Wiring config (non-semantic)

Endpoints, timeouts, resource limits, concurrency — things that shouldn’t change the meaning of READY.

### B) Policy config (outcome-affecting, governed)

Things that change what SR considers admissible/ready (required gates, reuse permissions, retention/backfill posture, etc.). These must be **versioned artifacts**; SR must report which `policy_rev` was in force.

Also pinned: **secrets are runtime-injected and never embedded in artifacts**; provenance can reference secret identity only (e.g., `key_id`).

---

## 2) SR environment profile knobs (what you’ll actually “turn”)

### 2.1 Wiring knobs for SR (per-environment)

These are the knobs that differ across local/dev/prod without changing meaning:

* **Substrate endpoints**

  * object store (bucket/prefix base; SR writes under `sr/`, reads under `engine/`)
  * control bus endpoint/topic (`fp.bus.control.v1`)
  * engine job runner endpoint (how SR triggers the engine job: local process / container / batch runner)
  * optional SR index DB endpoint/schema (`sr`)

* **Execution envelope**

  * max concurrent runs / per-run worker parallelism
  * per-run timeout ceilings (engine invoke timeout, evidence wait timeout)
  * retry/backoff for transient substrate errors (object store/bus/engine launch)
    (These are “mechanics,” but SR must remain deterministic in outcome meaning — retries must not duplicate side effects.)

* **Observability wiring**

  * OTLP collector endpoint, trace sampling rate (local low-friction vs prod SLO-grade)

### 2.2 Policy knobs for SR (must be versioned + auditable)

These are the knobs that *do* change what SR will do, so they must live in a governed policy profile and be cited as `policy_rev`:

* **Required readiness gates** (what PASS evidence is required before READY)
  This is explicitly named as outcome-affecting config.

* **Reuse vs rebuild permissions**

  * allow `REUSE_WORLD` at all?
  * in which contexts (local yes, prod maybe restricted)?
  * does reuse require re-verifying gates or trust receipts as-is?
    (Even if we haven’t opened SR internals yet, this is a top-level policy switch.)

* **Fail-closed strictness (should be “always fail-closed,” but enforcement knobs exist)**

  * missing PASS evidence ⇒ WAIT vs terminal FAIL after a deadline
    (deadline is policy; fail-closed meaning is invariant.)

* **Retention/backfill posture for SR artifacts**
  Retention/backfill rules are explicitly “governed behavior,” not casual tuning.

* **Who is allowed to request runs / replay / re-emit**
  Access/control policy changes are governance facts; this will be stricter up the ladder.

---

## 3) Environment defaults (directional, not vendor-specific)

This matches your ladder description directly:

* **Local**: minimal security friction but same semantics; small volumes; short retention; debug observability.
* **Dev**: multiple components running as in prod; “real enough” authz to catch missing PASS / unauthorized ops; medium retention; dashboards/alerts.
* **Prod**: strong authn/authz + strict change control; longer retention + archive continuity; SLOs/corridor checks; governance facts for every meaningful change.

---

## 4) Other deployment facts you should keep in mind before we “enter SR”

### The substrate map SR assumes (so internals don’t get invented wrong)

A production-shaped local stack can be as simple as:

* Kafka-compatible bus with `fp.bus.control.v1`, `fp.bus.traffic.v1` (optional `fp.bus.audit.v1`)
* S3-compatible object store with `engine/`, `sr/`, `ig/quarantine/`, etc.
* Postgres with optional operational schemas like `sr` (index only)

### The “Codex-ready” minimums for implementability

Even staying in brainstorm mode, you’ve pinned what the implementer will need to avoid drifting when building SR:

1. one “bring up local infra” command (Compose)
2. a local profile with endpoints + `policy_rev`
3. an integration script that runs the golden end-to-end flow (SR→Engine→IG/EB→…)

---

If you hold just this set of knobs, when we stop treating SR as opaque and start illuminating it, we’ll be able to design SR internals as “**same semantics, different profile**” instead of accidentally building three different SRs for local/dev/prod.

---

Got you. No diagrams — just **the internal subnetworks (modules)** that exist inside SR, treated as **opaque boxes** at this level.

This is **designer-authoritative** SR white-box modularization, consistent with your pinned platform/deployment truth (SR is a job/service; writes `sr/run_plan|run_record|run_status|run_facts_view`; emits READY on `fp.bus.control.v1`; engine invocation contract is fixed; “no PASS → no read”; fail-closed).

---

## The SR internal subnetworks

### SR.N1 — Ingress & Request Canonicalization

**Role:** Turn “Run intent” into a **canonical RunRequest** SR can safely reason about.

**Inputs:** Upstream RunRequest (operator/scheduler/etc.).
**Outputs:** Canonicalized request tuple + a stable **run-equivalence key**.

**Hard rules this subnetwork enforces:**

* Required world/run pins are present for engine invocation (`manifest_fingerprint`, `parameter_hash`, `seed`, `run_id`, `scenario_binding`).
* Time is explicit (window key), never “now”. 
* Normalization is deterministic (same input ⇒ same canonical form).

---

### SR.N2 — Run Authority Core

**Role:** Own the “run exists” truth and make SR safe under duplicates and concurrency.

**Inputs:** Canonicalized request + run-equivalence key.
**Outputs:** A resolved `run_id` (stable for that equivalence), a **run lease**, and an initial lifecycle state.

**What it owns:**

* **Idempotency mapping**: run-equivalence key → `run_id`. (Implementation can use an optional SR DB, but the mapping is authoritative behavior.)
* **Single-writer discipline**: at most one active executor for the same logical run at a time.

**Hard rules:**

* Duplicate submissions never create a second logical run truth surface (P2). 
* SR always creates an auditable trail (no silent drop): at minimum, it establishes the run ledger baseline (`run_record START`, `run_status OPEN`).

---

### SR.N3 — Policy/Profile Resolver & Plan Compiler

**Role:** Decide SR’s intended behavior *for this run* and record it.

**Inputs:** Canonical request + environment profile + governed policy revision.
**Outputs:** A **Run Plan**: mode, required gates, and “what SR intends to publish as join surfaces”.

**Hard rules:**

* **Mode is explicit**: `INVOKE_ENGINE`, `REUSE_EVIDENCE`, or `REHYDRATE_ONLY` (re-emit).
* **Required gates are explicit** and derive from authoritative gate mapping (no hand-wavy “looks complete”). 
* Plan is persisted as `sr/run_plan` (auditable intent vs outcome).

---

### SR.N4 — Engine Boundary Orchestrator

**Role:** Perform the **world-build handshake** with the Data Engine.

**Inputs:** Run plan + pins.
**Outputs:** Engine completion evidence pointers (or explicit failure evidence).

**Hard rules:**

* Engine is invoked only via the locked `engine_invocation` contract: `manifest_fingerprint`, `parameter_hash`, `seed`, `run_id`, `scenario_binding` (+ optional `request_id` for boundary idempotency).
* SR treats engine completion as **evidence**, not a boolean.
* `run_id` may partition logs/events but MUST NOT change deterministic outputs that don’t include `run_id` in identity.

---

### SR.N5 — Evidence Assembly & Gate Attestation

**Role:** Convert “engine produced stuff” (or “existing stuff”) into an **admissible evidence bundle** SR can safely stand behind.

**Inputs:** Engine artifacts in object store (`engine/...`) and/or reuse candidates; gate artifacts/receipts.
**Outputs:** A verified set of:

* output locators (by-ref),
* gate receipts (PASS/FAIL),
* instance-proof bindings where required.

**Hard rules:**

* “No PASS → no read” is enforced here: SR cannot READY without required PASS evidence.
* Gate receipts are portable truth; consumers fail closed on missing/unknown. 
* Output selection respects engine output taxonomy: only `business_traffic` is eligible to drive ingestion/hot path; audit/telemetry/truth products are not treated as traffic.
* Reuse is permitted **only** as “reuse of evidence” (locators + PASS receipts), never “guess outputs exist.”

---

### SR.N6 — Ledger & Join-Surface Publisher

**Role:** Publish SR’s authoritative truths and make the run joinable.

**Inputs:** Run plan + verified evidence bundle.
**Outputs:** The SR truth surface:

* `sr/run_record` (append-only),
* `sr/run_status` (monotonic),
* `sr/run_facts_view` (the join map),
  …and the control-plane READY signal.

**Hard rules:**

* **Commit ordering is strict**: `run_facts_view` must exist before `run_status=READY`; `run_status=READY` must exist before READY is emitted.
* READY is monotonic: SR does not revoke READY; corrections are supersedes/new runs (P6).
* READY emission is to `fp.bus.control.v1` and points to the facts view.

---

### SR.N7 — Rehydration & Control Re-emit Operations

**Role:** Operationally restore the platform entrypoint without recomputing the world.

**Inputs:** Existing SR ledger (`sr/*`).
**Outputs:** Re-emitted READY (or failure) control facts consistent with the ledger.

**Hard rules:**

* Re-emit is allowed and is idempotent (P7).
* Re-emit never implies engine rerun; it is strictly “replay control-plane truth from the ledger.”

---

### SR.N8 — Observability & Governance Emitter

**Role:** Make SR’s behavior explainable and governable across the environment ladder.

**Inputs:** Internal events from all SR subnetworks.
**Outputs:** OTLP traces/logs/metrics + governance-relevant facts (policy_rev used, run mode, gate outcomes, etc.).

**Hard rules:**

* Correlation must carry the run/world pins so operators can join telemetry to `sr/*` artifacts.
* Outcome-affecting policy changes are auditable (environment ladder: semantics constant; strictness increases).

---

## The only internal connections that matter at this level

At this “opaque subnetwork” level, SR is exactly these pipes:

* **N1 → N2 → N3**: canonical request → run authority → plan
* **N3 → (N4 or N5)**: plan chooses invoke vs reuse-evidence
* **(N4/N5) → N6**: admissible evidence → publish ledger + join surface + READY
* **N7** is a side-path that reads from **N6 outputs** and re-emits control facts
* **N8** observes all subnetworks, never drives outcomes

That’s the SR internal network at one-level depth. It’s modular, production-shaped, and it lines up with the pinned outer joins (engine invocation contract, object-store truth surface, READY on control bus, fail-closed gating).

---

Got it. Treat **SR.N1–SR.N8** as the **first-layer internal nodes**, still opaque. What you want now is: **what *joins* (handoffs) exist between these nodes, and what *paths* (multi-hop routes) run through them** in a production SR.

Below is the **identified join+path inventory** — no deep dive, but nothing hand-wavy.

---

## 1) Internal one-hop joins (SR adjacency list at the subnetwork level)

I’m going to name the “thing that crosses” each internal boundary (a handoff object / durable write / internal event). These names are conceptual, not schema.

### J1 — SR.N1 → SR.N2

**CanonicalRunIntent → RunHandle acquisition**

* **Crosses:** `CanonicalRunIntent` (normalized pins + time key + equivalence key)
* **Result:** `RunHandle` (resolved `run_id` + lease/lock token + run pointer)
* **Purpose:** Makes duplicates and concurrency safe (single-writer discipline)

### J2 — SR.N2 → SR.N6 (early)

**Run existence anchoring**

* **Crosses:** `RunHandle`
* **Result:** initial durable truth: `run_record START`, `run_status OPEN` (or equivalent)
* **Purpose:** Ensures “a run exists” is always auditable even if everything fails later

### J3 — SR.N2 → SR.N3

**RunContext → PlanContext**

* **Crosses:** `RunContext` (pins + run_id + scenario binding + env profile id)
* **Result:** `PlanContext` (includes policy_rev identity)
* **Purpose:** Ties the run to the exact policy/profile that governs readiness behavior

### J4 — SR.N3 → SR.N6

**Plan publication**

* **Crosses:** `RunPlan` (mode + required gate set + intended exposed outputs)
* **Result:** durable `sr/run_plan` + `run_record PLAN_COMPILED`
* **Purpose:** Separates intent from outcome; makes decisions explainable

### J5 — SR.N3 → SR.N4

**ExecutionTicket: INVOKE_ENGINE**

* **Crosses:** `ExecutionTicket{mode=INVOKE}` + the exact `engine_invocation` payload SR will use
* **Result:** `EngineAttemptHandle` (job/attempt id) + `run_record ENGINE_LAUNCHED`
* **Purpose:** Binds the run to a concrete engine attempt

### J6 — SR.N3 → SR.N5

**ExecutionTicket: REUSE_EVIDENCE**

* **Crosses:** `ExecutionTicket{mode=REUSE}` + evidence search criteria
* **Result:** `ReuseCheckHandle` + `run_record REUSE_CHECK_STARTED`
* **Purpose:** Allows P3 without engine invocation, but only as “reuse of evidence”

### J7 — SR.N4 → SR.N5

**AttemptResult → Evidence collection**

* **Crosses:** `EngineAttemptResult` (success/fail + where evidence should exist)
* **Result:** `EvidenceSnapshot` (collected candidate outputs + candidate gate artifacts)
* **Purpose:** Decouples engine execution from evidence interpretation

### J8 — SR.N5 → SR.N6

**EvidenceBundle → Join surface commit**

* **Crosses:** `VerifiedEvidenceBundle` (output locators + PASS receipts + instance proofs)
* **Result:** durable `sr/run_facts_view` + monotonic `sr/run_status` update (+ run_record append)
* **Purpose:** Turns evidence into the single join surface the platform can trust

### J9 — SR.N6 → SR.N7

**LedgerReadHandle → Re-emit**

* **Crosses:** pointer to `sr/*` truth (run_status + run_facts_view locator)
* **Result:** `ReemitAction` (READY re-emit or terminal signal re-emit)
* **Purpose:** Recovery without recomputation (P7)

### J10 — SR.N6 → SR.N1 (response path)

**Caller-visible outcome**

* **Crosses:** `RunOutcomeSummary` (run_id + current status + facts_view ref if READY)
* **Purpose:** Upstream gets a stable handle regardless of async execution timing

### J11 — (N1..N7) → SR.N8

**Telemetry/Governance stream**

* **Crosses:** `ObsEvent` (structured events with pins + attempt ids + policy_rev)
* **Purpose:** Production explainability and audit joins

---

## 2) Internal multi-hop paths (the real routes inside SR)

These are the **canonical SR-internal flows** that implement P1–P8 externally. Still opaque nodes; just route shapes.

### IP1 — New run, invoke engine, declare READY

**N1 → N2 → N6(early) → N3 → N6(plan) → N4 → N5 → N6(commit) → N8**

* Intake & normalize
* Acquire run handle/lock; anchor run exists
* Resolve policy/profile; compile plan (mode=INVOKE; required gates)
* Invoke engine attempt
* Harvest + verify evidence (fail-closed)
* Commit facts view, set READY, emit control fact (via N6 outputs)
* Emit observability throughout

### IP2 — Duplicate submission (idempotent re-entry)

Two subpaths:

**IP2a: Duplicate while run is in-flight**
**N1 → N2 → N6(read status) → N1(response) → N8**

* N2 resolves the same run_id; does not create a second run
* Returns “already OPEN/EXECUTING/VERIFYING” with the same run_id

**IP2b: Duplicate after READY**
**N1 → N2 → N6(read READY + facts_view ref) → N7(optional re-emit) → N1(response) → N8**

* Safe re-emit path exists, but the semantic READY points to the same facts view

### IP3 — Reuse path (engine not invoked)

**N1 → N2 → N6(early) → N3 → N6(plan) → N5(reuse verify) → N6(commit) → N8**

* Planner selects REUSE_EVIDENCE
* Evidence assembly must still produce a complete PASS+locator bundle
* If complete → READY; if not → falls into IP5

### IP4 — Engine failure (dependency fail)

**N1 → N2 → N6(early) → N3 → N6(plan) → N4(fail) → N6(terminal) → N8**

* Engine attempt fails (or cannot be launched)
* SR records terminal non-READY status; no READY emitted

### IP5 — Missing/FAIL PASS evidence (fail-closed / quarantine)

Two production-grade shapes:

**IP5a: WAIT loop (evidence not yet settled)**
**N1 → N2 → N6(early) → N3 → (N4 or N5) → N5(incomplete) → N6(status=WAITING) → (back to N5 on retry) → N8**

* SR never emits READY while evidence is incomplete

**IP5b: FAIL/QUARANTINE (evidence FAIL or structurally missing)**
**N1 → N2 → N6(early) → N3 → (N4 or N5) → N5(FAIL) → N6(status=FAILED|QUARANTINED) → N8**

* SR writes an evidence trail and terminates non-READY

### IP6 — Post-READY correction (supersede, don’t mutate)

This is *not* “edit the old run.” It’s a **new run path with a supersedes link**:

**N1(new request) → N2(new run_id) → N3(plan) → (IP1 or IP3) → N6(commit READY) + N6(append supersedes relation) → N8**

* Old READY remains historically true
* New READY becomes the preferred/active run for a declared purpose

### IP7 — Rehydration / control-plane re-emit

**N1(ops command) → N2(resolve run) → N7(read sr/*) → N6(publish control fact) → N8**

* Does not invoke engine
* Does not recompute evidence
* Only replays control-plane truth from ledger

### IP8 — Offline rebuild entrypoint support (SR-side)

Offline rebuild itself is outside SR, but SR participates by guaranteeing:

**N6 outputs (facts_view + status + plan + record) → consumed by Offline Shadow**
Internally SR ensures this path is always available by:

* Writing stable `run_facts_view` + immutable references
* Keeping run_record append-only and policy_rev recorded

So SR’s internal “path” here is simply: **all production paths must end with a coherent `sr/*` truth surface** (even failures), because offline tooling and governance need it.

---

## 3) The internal loops you *will* deep dive later (but must exist)

Just identifying them now:

1. **Lease/lock loop (N2):** acquire/renew/release; prevents double writers
2. **Attempt loop (N4):** retry-on-transient while keeping idempotency
3. **Evidence wait/refresh loop (N5):** WAITING → re-harvest → verify
4. **Commit ordering loop (N6):** facts_view → status READY → control publish (never inverted)
5. **Re-emit loop (N7):** safe repeated replays of control facts (at-least-once)

---

Cool — we’ll **open up J1→J5** and make each one *crisp*: what crosses the boundary, what gets committed, what’s idempotent, and what the failure outcomes are. No ASCII, no “maybe”.

I’m treating these joins as **internal contracts** between SR subnetworks, but they’re still aligned to the outer pins: SR is job/service, persists `sr/run_plan|run_record|run_status|run_facts_view`, and emits READY on `fp.bus.control.v1`.

---

## J1 — SR.N1 → SR.N2

### CanonicalRunIntent → RunHandle (idempotent admission + single-writer lock)

### Purpose

Turn a raw upstream request into **one and only one** logical run, safely under duplicates and concurrency.

### What crosses this join

**CanonicalRunIntent** (produced by N1) contains exactly the *semantic* inputs SR will treat as run identity:

* `scenario_binding` (either `scenario_id` or `scenario_set`) 
* `manifest_fingerprint` (hex64) 
* `parameter_hash` (hex64) 
* `seed` (uint64) 
* `window` (explicit start/end/tz or equivalent explicit window key) (SR rule; consistent with your “no implicit now” rail)
* **Run equivalence key** (caller-provided; SR enforces it)

### SR decision (designer-locked)

**Upstream MUST supply the run-equivalence key.** If it’s missing, SR rejects the request at N1; the platform is at-least-once and SR must be deterministic about duplicates. (No hidden run equivalence rules.)

### Canonicalization laws (N1 side, before J1 crosses)

N1 produces a *single canonical form*:

* scenario_set is sorted and deduped (if scenario_set used)
* window is normalized (start < end; tz explicit; stored in canonical representation)
* all “notes”, “invoker strings”, etc. are treated as **non-semantic** and excluded from identity

### What N2 MUST do on receiving CanonicalRunIntent

N2 implements a strict mapping:

1. Compute `run_intent_fingerprint = sha256(canonical_semantic_fields)`
2. Derive `run_id = hex32(run_intent_fingerprint[0:16])` (32 lowercase hex chars)
   *This directly matches the engine’s required `run_id` type and semantics.* 
3. Consult the **Idempotency Index** (transactional compare-and-set interface) keyed by the caller’s run-equivalence key:

   * If key is new: bind it to `run_id` + `run_intent_fingerprint` and mark `first_seen=true`.
   * If key exists: return the already-bound `run_id` and require the same `run_intent_fingerprint`.

### Collision rule (designer-locked)

If the same run-equivalence key is reused with a different canonical intent fingerprint, SR rejects with **EQUIV_KEY_COLLISION** and writes an auditable record (via J2). This prevents “same key, different world” drift.

### Output of J1

**RunHandle** (produced by N2) includes:

* `run_id`
* canonical pins (scenario_binding, manifest_fingerprint, parameter_hash, seed, window)
* `run_intent_fingerprint`
* `first_seen` boolean
* **run lease token** (single-writer lock with expiry) + owner identity (SR instance id)

### Environment ladder note (applies to J1)

Local/dev/prod must all provide the same semantics: **atomic bind + collision detection + lease**. Implementations may use the optional `sr` DB or object-store conditional create, but the capability is mandatory for production behavior.

---

## J2 — SR.N2 → SR.N6 (early)

### Run existence anchoring (create the SR truth surface baseline)

### Purpose

Make “a run exists” durable and observable **before** any engine work happens. This is what prevents silent failures.

### Preconditions

* A valid RunHandle exists (J1 done)
* Lease is held by this SR executor

### What crosses this join

A **RunAnchorWrite** instruction containing:

* run pins + run_id
* first_seen / duplicate flag
* minimal “acceptance event” payload

### What N6 MUST write (designer-locked)

On `first_seen=true`, N6 performs the baseline writes to the **object store truth surface** for SR:

* `sr/run_record` append: `RUN_ACCEPTED` (includes run_intent_fingerprint + canonical pins)
* `sr/run_status` write: state = `OPEN`
* `sr/run_plan` write: **skeleton** containing pins + placeholders (planning fills it in at J4)

This matches your deployment truth: SR must persist `sr/run_plan`, `sr/run_record`, `sr/run_status`, `sr/run_facts_view` and READY is meaningless without these.

### Duplicate behavior (designer-locked)

If `first_seen=false`, N6 MUST NOT reset anything. It only appends a `DUPLICATE_REQUEST_OBSERVED` entry to `run_record` (optional but recommended) and returns the current `run_status` pointer.

### Failure law

If any baseline write fails, SR:

* keeps the lease only long enough to record failure (if possible),
* releases lease,
* and surfaces a non-READY outcome (no READY emission is possible because the truth surface isn’t anchored).

---

## J3 — SR.N2 → SR.N3

### RunContext → PlanContext (bind run to policy/profile + planning inputs)

### Purpose

Give the planner everything it needs to decide **exactly** how this run will proceed (and under which governed policy revision).

### What crosses this join

**PlanContext** includes:

* RunHandle (pins, run_id, intent_fingerprint, lease token)
* environment profile identity (local/dev/prod profile selection is deployment-controlled) 
* a pointer to the current SR ledger locations (so planner can read/append)

### What N3 MUST do upon receiving PlanContext

N3 resolves:

* **policy_rev** (outcome-affecting knobs like required gate set, reuse permissions, retry budgets) and binds it to this run
* authoritative engine boundary shapes it must respect (engine invocation contract and evidence requirements)

### Output of J3

A **ResolvedPlanInputs** bundle that includes:

* policy_rev
* execution strategy (AUTO / FORCE_INVOKE / FORCE_REUSE / REHYDRATE_ONLY)
* computed “required gate set” identifiers (gate_id + required scope pattern)

(We’ll deep-dive *how* required gates are computed later; here we only define that the planner must produce a closed set.)

---

## J4 — SR.N3 → SR.N6

### Plan publication (commit run_plan + declare planned state)

### Purpose

Persist “what SR intends to do” as durable truth so the run is explainable, replayable, and governance-safe.

### What crosses this join

**RunPlanCommit** containing:

* `mode` / strategy:

  * `AUTO` = attempt reuse evidence first if allowed; if incomplete, invoke engine
  * `FORCE_REUSE` = reuse only; if incomplete evidence → terminal non-READY
  * `FORCE_INVOKE` = invoke engine regardless of reuse evidence presence
  * `REHYDRATE_ONLY` = never invoke engine; only re-emit from ledger (P7)
* `policy_rev`
* required gates list (gate_id + scope constraints)
* “intended exposed outputs” list (which output_ids SR expects to place into facts view later; includes which are `business_traffic` eligible)

### What N6 MUST do (designer-locked)

* Write/overwrite `sr/run_plan` with this committed plan
* Append `PLAN_COMMITTED` to `sr/run_record`
* Update `sr/run_status` to `PLANNED` (monotonic transition from OPEN)

### Plan immutability rule (designer-locked)

For a given run_id, there is exactly **one** committed plan:

* If `sr/run_plan` exists and differs (by plan_hash) from the new plan, SR must mark the run **FAILED (PLAN_DRIFT)** and stop.
  This prevents “same run_id, two meanings” drift.

(Yes, this is strict — and that’s the point.)

---

## J5 — SR.N3 → SR.N4

### ExecutionTicket(INVOKE_ENGINE) (start a concrete engine attempt)

### Purpose

Turn the committed plan into a single, idempotent engine attempt launch.

### Preconditions

* run_status is `PLANNED`
* lease is held
* strategy resolves to INVOKE (either FORCE_INVOKE, or AUTO after reuse-check failure later)

### What crosses this join

**EngineExecutionTicket** includes:

1. The **exact `engine_invocation` payload** (locked contract):

   * `manifest_fingerprint`
   * `parameter_hash`
   * `seed`
   * `run_id`
   * `scenario_binding`
   * plus `request_id` = deterministic idempotency key at invocation boundary

2. `attempt_id` and `attempt_no` (monotonic, starting at 1 for this run_id)

3. execution envelope from profile:

   * launch timeout
   * max retries for launch failures
   * overall engine completion deadline

### Idempotency rule (designer-locked)

**Same `(run_id, attempt_no)` must never launch the engine twice.**
N4 enforces this by writing an “attempt-start sentinel” (transactionally, via the same atomic store capability used in J1 leases). If sentinel exists, N4 returns the existing attempt handle and does not re-launch.

### What N4 MUST do (observable side effects)

* Append `ENGINE_ATTEMPT_LAUNCH_REQUESTED` to `run_record`
* Update `run_status` to `EXECUTING` with `attempt_id`
* Trigger the engine job through the job runner interface (local process/container; dev/prod batch runner) — the job itself is a deployment unit in your map.

### Failure law (launch failure)

If the engine cannot be launched within the profile’s launch retry budget:

* SR appends `ENGINE_LAUNCH_FAILED` to run_record
* sets run_status to `FAILED`
* emits **no READY** (ever)

This matches the platform “dependency fail” path (P4) behavior.

---

Yep — here’s **J6 → J11** illuminated, **no maybes**, production-shaped, and consistent with your pinned rails (SR truth lives in `sr/*`, READY on `fp.bus.control.v1`, engine invocation contract is fixed, and **“no PASS → no read” + fail-closed**).

---

## J6 — SR.N3 → SR.N5

### ExecutionTicket(REUSE_EVIDENCE) → ReuseEvidenceResult (deterministic evidence check)

### Purpose

Allow P3 (“reuse; don’t invoke engine”) **without guessing**. Reuse is strictly **reuse of admissible evidence**.

### Preconditions

* `sr/run_plan` is committed (J4 already happened).
* `run_status == PLANNED`.
* Strategy is **AUTO** or **FORCE_REUSE** (from plan).

### What crosses this join (ticket)

**ReuseEvidenceTicket** contains exactly:

* **Run pins**: `manifest_fingerprint`, `parameter_hash`, `seed`, `run_id`, `scenario_id` (SR uses scenario_id form for platform joins; engine invocation supports scenario_binding but SR’s join pin is scenario_id).
* **Required gate set** (gate_id + scope constraints)
* **Output intent list** = the exact `output_id`s SR intends to put in `run_facts_view` (and which are `business_traffic` eligible)
* **Policy controls**:

  * `reuse_deadline` (how long SR will wait for evidence to appear)
  * `reuse_mode` ∈ {AUTO, FORCE_REUSE}
  * `digest_policy` (which outputs must include `content_digest` in locators)

> Output IDs and expected path templates are anchored in the engine catalogue, and locators must be consistent with those templates.

### What N5 MUST do (deterministic algorithm, not hand-wavy)

For each `output_id` in the intent list:

1. Construct the **expected locator** (identity fields + fully-resolved `path`) using the catalogue template and the run pins.
2. Check materialisation existence at that path (object store).
3. If required by policy, compute/attach `content_digest` (sha256 over authoritative bytes for that output).

For each required gate_id:

1. Locate the authoritative on-disk gate artifacts (gate-specific rules; N5 doesn’t assume a universal format).
2. Produce a **portable `gate_receipt`** (PASS/FAIL + scope + optional digest/artifact pointers).

### Output of J6 (result back to N3)

**ReuseEvidenceResult.status** is one of exactly these four:

* **COMPLETE**
  All intended outputs are located, and every required gate receipt is **PASS** for the required scope.
  → N5 returns a `VerifiedEvidenceBundle` (locators + PASS receipts).

* **WAITING**
  Some required evidence is missing, but no required gate has **FAIL**.
  → N5 returns a `MissingEvidenceSet` and the earliest time it’s worth re-checking.
  (This is still fail-closed; it just means “not settled yet”.)

* **FAIL**
  Any required gate is **FAIL**, or the reuse_deadline is exceeded with missing evidence, or evidence is inconsistent (e.g., locator exists but required proof cannot be formed).
  → N5 returns `FailureEvidenceBundle` (what failed and where).

* **CONFLICT**
  The evidence found doesn’t match the pinned identity (wrong scope tokens, wrong output_id mapping, etc.).
  → Treated as FAIL; SR stops.

### How this feeds the next move (no ambiguity)

* If **COMPLETE**: N3 immediately routes to **J8** (commit join surface).
* If **WAITING**: N3 either loops back to N5 until deadline or (if plan is AUTO) switches to **J5** (invoke engine).
* If **FAIL/CONFLICT**: N3 routes to **J8** to commit terminal non-READY status (no READY).

---

## J7 — SR.N4 → SR.N5

### EngineAttemptResult → EvidenceHarvestResult (post-invoke evidence collection)

### Purpose

After an engine attempt, convert “job outcome” into the same evidence language N5 always uses: **locators + receipts**, or terminal failure evidence.

### Preconditions

* Engine attempt was launched under J5.
* N4 has an `attempt_id` and knows the exact `engine_invocation` used. 

### What crosses this join (attempt result)

**EngineAttemptResult** contains:

* `run_id`, `attempt_id`, `attempt_no`
* `engine_invocation` payload used (pins + scenario_binding + optional request_id) 
* `attempt_outcome` ∈ {SUCCEEDED, FAILED, TIMED_OUT}
* `engine_artifact_root_hint` (optional pointer to where “run receipts/logs” would be, if the engine emits them)

### What N5 MUST do (strict behavior by outcome)

* If **SUCCEEDED**:
  N5 harvests outputs and gate evidence using the **same rules as reuse** (resolve locators; build gate_receipts; verify PASS scope; attach digests when policy requires).

* If **FAILED** or **TIMED_OUT**:
  N5 returns **FailureEvidenceBundle** that includes:

  * attempt identity,
  * any available diagnostic pointers (job logs, partial receipts if they exist),
  * and a clear cause code: `ENGINE_EXEC_FAIL` or `ENGINE_TIMEOUT`.
    SR does not attempt to READY from partial success. (Binary READY rule.)

### Output of J7

**EvidenceHarvestResult** is exactly one of:

* `VerifiedEvidenceBundle` (PASS + locators) → eligible for J8 READY commit
* `FailureEvidenceBundle` → eligible for J8 terminal commit (no READY)

---

## J8 — SR.N5 → SR.N6

### EvidenceBundle → Ledger commit + join surface + (maybe) READY emission

### Purpose

Make SR’s claims **durable** and **joinable**: write `run_facts_view`, advance `run_status` monotonically, append to `run_record`, and emit READY only when legal.

### What crosses this join

Either:

1. **VerifiedEvidenceBundle**

   * list of `engine_output_locator` objects for the intended outputs 
   * list of `gate_receipt` objects, all **PASS**
   * `evidence_bundle_hash` (SR-computed deterministic hash over canonical representation)

or
2) **FailureEvidenceBundle**

* failure cause code + missing/failed gates list + pointers to artifacts
* `failure_hash`

### What N6 MUST do for VerifiedEvidenceBundle (READY case)

Commit ordering is **strict** and never inverted:

1. Write `sr/run_facts_view` (pins + window + policy_rev + locators + PASS receipts + pointers to SR ledger).
   Locators MUST conform to the engine output locator contract (`output_id`, identity fields, resolved `path`, optional `content_digest`).
2. Write `sr/run_status = READY` including `facts_view_hash` (monotonic).
3. Append to `sr/run_record`: `EVIDENCE_VERIFIED` + `READY_COMMITTED` (append-only).
4. Publish `RunReadySignal` to `fp.bus.control.v1` with:

   * pins,
   * status=READY,
   * a pointer to the facts view,
   * a deterministic signal idempotency key (so re-emit is safe).

**READY is illegal unless all required gates are PASS.**

### What N6 MUST do for FailureEvidenceBundle (non-READY case)

* Append failure details to `sr/run_record`
* Set `sr/run_status` to one of:

  * `WAITING` (if evidence incomplete but within deadline and no FAIL present), or
  * `FAILED`, or
  * `QUARANTINED` (if evidence is contradictory / unsafe to interpret)
* **Never** emit READY.

### Idempotency rules (designer-locked)

* If `run_status` is already READY and the incoming `evidence_bundle_hash` matches the committed facts view hash, J8 is a no-op except that SR may re-emit READY (via J9/J7).
* If `run_status` is READY but the incoming evidence hash differs, SR marks the run **CORRUPT** and stops (this indicates drift or storage corruption; SR never “updates” READY).
  This matches your “supersede, don’t mutate” rule.

---

## J9 — SR.N6 → SR.N7

### LedgerReadHandle → Re-emit control facts (rehydration)

### Purpose

Operational recovery: re-trigger downstream without recomputation.

### What crosses this join

**ReemitRequest** contains:

* `run_id`
* `reemit_kind` ∈ {READY_ONLY, TERMINAL_ONLY, BOTH}
* `reason` (non-semantic but logged for audit)

**LedgerReadHandle** resolves:

* current `sr/run_status`
* `sr/run_facts_view` pointer + its hash (if READY)

### What N7 MUST do

* If run is READY: publish **the same semantic READY** to `fp.bus.control.v1` pointing to the already-committed facts view (idempotent key derived from `(run_id, facts_view_hash)`).
* If run is not READY: N7 never emits READY. If terminal re-emits are enabled, it emits a terminal control fact; otherwise it stays silent and relies on the ledger.
  (READY can only come from READY status.)

---

## J10 — SR.N6 → SR.N1

### Caller-visible outcome (synchronous ack that never lies)

### Purpose

Even if SR is executing asynchronously, upstream needs a stable handle immediately.

### What crosses this join

**RunOutcomeSummary** contains:

* `run_id`
* `run_status` (OPEN/PLANNED/EXECUTING/WAITING/READY/FAILED/…)
* pointer to `sr/run_status` artifact
* if READY: pointer to `sr/run_facts_view` artifact
* if FAILED/QUARANTINED: pointer to evidence in `sr/run_record`

### Designer-locked behavior

N1 always returns an ack quickly:

* If run is new: `ACCEPTED` + `run_id` + status pointer
* If duplicate: same `run_id` + current status pointer
* If READY already: same `run_id` + facts view pointer

Upstream never has to “guess”; polling the SR ledger and/or subscribing to control bus is the supported way.

---

## J11 — (N1..N7) → SR.N8

### Structured observability + governance facts stream

### Purpose

Make SR’s decisions explainable across the environment ladder (local/dev/prod semantics must match; only depth changes).

### What crosses this join

Each subnetwork emits **structured boundary events** to N8 with:

* correlation pins: `run_id`, `scenario_id`, `manifest_fingerprint`, `parameter_hash`, and `seed` when relevant
* `policy_rev` (always)
* `attempt_id` (when engine invoked)
* `event_kind` + `outcome` + `duration_ms` + `reason_code`

### Mandatory SR observability facts (not optional)

N8 must emit (at minimum) these SR events as durable logs/metrics/traces:

* RUN_REQUEST_RECEIVED
* RUN_ACCEPTED / DUPLICATE_SEEN
* PLAN_COMMITTED (includes policy_rev)
* ENGINE_ATTEMPT_LAUNCHED / ENGINE_ATTEMPT_FINISHED (outcome)
* EVIDENCE_COMPLETE / EVIDENCE_WAITING / EVIDENCE_FAIL (with missing/failed gate ids)
* FACTS_VIEW_COMMITTED (hash)
* READY_EMITTED (signal idempotency key)
* REEMIT_REQUESTED / REEMIT_EMITTED

And, per your governance baseline, outcome-affecting changes (policy rev activation etc.) must exist as **auditable governance facts**—SR at least reports which policy rev it used for every run.

---

Alright — here are **IP1 → IP4** as **fully pinned internal routes** through the SR subnetworks, using the joins we just illuminated (J1–J11). No “maybes”; this is the production SR behavior.

One quick authority declaration up front (to prevent drift): **`run_id` is the engine contract’s `hex32`** (lowercase 32-hex), because SR must pass it into `engine_invocation`. Any human-friendly run string belongs in a separate non-semantic `run_label` field and never participates in joins. 

Also pinned: **time is explicit via a window key** and must be carried and recorded as part of the run. 

---

## IP1 — New run, engine invoked, gates PASS, READY committed

### Goal

Create a new run, build (or rebuild) the world via engine, assemble admissible evidence, publish **`run_facts_view` + READY** and emit a control-plane READY signal.

### Route (joins + state)

1. **N1 Intake/Canonicalization**

   * Canonicalizes scenario binding (if scenario_set, it is sorted/deduped) and canonicalizes the explicit `window`.
   * Produces `CanonicalRunIntent` including the caller’s run-equivalence key and the exact semantic pins.

2. **J1: N1 → N2 (RunHandle + lease)**

   * N2 binds `(run_equivalence_key → run_id)` deterministically and acquires the single-writer lease.
   * Output: `RunHandle(run_id, pins, intent_fingerprint, lease_token, first_seen=true)`.

3. **J2: N2 → N6 (Anchor run existence)**

   * N6 writes the baseline SR truth surface:

     * append `RUN_ACCEPTED` to `run_record`
     * `run_status = OPEN`
     * draft/skeleton `run_plan` (pins + placeholders)

4. **J3: N2 → N3 (PlanContext)**

   * N3 resolves the active `policy_rev` (governed) and profile (wiring) and binds them to the run.

5. **J4: N3 → N6 (Plan commit)**

   * N3 commits a single immutable plan for this run:

     * mode includes **INVOKE_ENGINE** (either FORCE_INVOKE or AUTO→INVOKE)
     * required gate set is explicit
     * intended outputs to expose in facts view is explicit
   * N6 writes `run_plan`, appends `PLAN_COMMITTED`, and advances `run_status = PLANNED`.

6. **J5: N3 → N4 (EngineExecutionTicket)**

   * N4 launches one concrete engine attempt.
   * The invocation payload is exactly the engine contract:
     `manifest_fingerprint, parameter_hash, seed, run_id, scenario_binding` (+ optional `request_id`). 
   * N4 writes attempt sentinel, appends `ENGINE_ATTEMPT_LAUNCH_REQUESTED`, sets `run_status = EXECUTING(attempt_id)`.

7. **J7: N4 → N5 (AttemptResult → Evidence harvest)**

   * When the engine attempt finishes successfully, N5 harvests:

     * output locators (resolved paths; optional digests as policy requires)
     * gate artifacts and converts them into portable `gate_receipt` objects

8. **N5 Verification (hard law)**

   * N5 verifies required gates as PASS.
   * **Fail-closed** applies: missing/unknown gate status is not admissible for READY; only explicit PASS is.

9. **J8: N5 → N6 (Commit join surface + READY)**

   * N6 commits in strict order:

     1. write `run_facts_view` (pins + refs/locators + required PASS evidence pointers)
     2. write `run_status = READY`
     3. append `VERIFIED_OK` / `READY_COMMITTED` to `run_record`
     4. publish READY control fact (RunReadySignal) with `facts_view_ref` and a stable `signal_idempotency_key`

10. **J10: N6 → N1 (Return outcome summary)**

* Upstream gets a stable response:

  * `run_id`, `status`, and the ledger refs; if READY then the `facts_view_ref` is included.

11. **J11 (all → N8 Observability)**

* SR emits structured events for each boundary crossing (accepted/plan/attempt/verified/ready).

**What makes IP1 “production”**

* It matches the pinned job nature of SR: invoked explicitly, produces auditable artifacts, and emits a control-plane READY trigger.

---

## IP2 — Duplicate submission (idempotent re-entry)

### Goal

Same logical request submitted twice must **not** duplicate side-effects (no second run, no second engine run, no ledger rewrite).

### Route (two concrete branches)

### IP2-A: Duplicate arrives while run is not READY (OPEN / PLANNED / EXECUTING / VERIFYING)

1. **N1 canonicalizes** the request the same way as before (same semantic intent fingerprint).
2. **J1 (N1→N2)** resolves the **existing** `(run_equivalence_key → run_id)` mapping.
3. N2 **does not acquire the lease** if another SR worker already holds it; N2 returns:

   * `run_id`
   * current `run_status` pointer
   * `lease_held_by_other=true`
4. **J10 (N6→N1)** returns “already in progress” (status pointer).
5. **No engine invocation occurs. No plan rewrite occurs.**
   The only allowable write is an optional `DUPLICATE_REQUEST_OBSERVED` append to `run_record` (purely audit).

### IP2-B: Duplicate arrives after READY

1. Same as above: N1 → J1 → N2 resolves existing run_id.
2. N2 returns `run_id` and indicates `run_status=READY`.
3. **J10** returns `facts_view_ref` to the caller immediately.
4. **No automatic READY re-emit happens here.**
   Re-emission is a separate operational route (IP7 / J9), to avoid spamming downstream triggers.

---

## IP3 — Reuse path (engine not invoked; evidence already exists)

### Goal

Declare READY without invoking the engine **only** when the existing evidence bundle is complete and admissible. This is “reuse of evidence,” not “guessing outputs exist.”

### Route (joins + state)

1. **N1 → J1 → N2 → J2**
   Same as IP1: canonicalize, bind to run_id, anchor `run_record START`, `run_status OPEN`.

2. **J3 + J4 (plan)**
   Plan commits a reuse-allowed strategy:

   * either **FORCE_REUSE** (reuse only) or **AUTO** (try reuse first)
   * required gate set is explicit; intended outputs list is explicit.

3. **J6: N3 → N5 (ReuseEvidenceTicket)**

   * N5 deterministically checks for:

     * completion evidence (engine receipt and/or output index)
     * required PASS artifacts, turned into portable `gate_receipt` objects

4. **N5 returns COMPLETE**

   * All required `gate_receipt.status == PASS` for the required scope.
   * Output refs/locators are resolvable (and digests attached if policy requires).

5. **J8: N5 → N6 (Commit READY)**

   * Same strict commit order as IP1:
     `run_facts_view` → `run_status READY` → `run_record` append → publish READY signal.

6. **J10 returns READY summary** (facts view ref included).

**Policy rule (designer-locked, because it matters)**

* If strategy is **FORCE_REUSE** and evidence is not COMPLETE by the reuse deadline, the run becomes terminal non-READY (FAILED or QUARANTINED). It does not silently fall back to engine invocation. This preserves the meaning of “force reuse.”

---

## IP4 — Engine failure path (dependency fail)

### Goal

If the engine cannot successfully complete, SR produces a clean, auditable terminal outcome and **never emits READY**.

### Route (joins + state)

1. **N1 → J1 → N2 → J2 → J3 → J4**
   Same as IP1 up to PLANNED state.

2. **J5: invoke engine attempt**
   Engine invocation payload matches the engine contract. 

3. **Engine attempt fails or times out**

   * N4 produces `AttemptResult{FAILED|TIMED_OUT}`.

4. **J7: N4 → N5 (Harvest failure evidence)**

   * N5 captures whatever durable evidence exists (partial receipts, failure receipt pointers, logs pointers), and forms a `FailureEvidenceBundle`.

5. **J8: N5 → N6 (Commit terminal non-READY)**

   * N6 writes:

     * `run_status = FAILED` (or `QUARANTINED` if evidence is contradictory/unsafe)
     * appends `EXEC_FAIL` (or `ENGINE_TIMEOUT`) into `run_record`
   * **READY is not emitted** under any circumstance in this path.

6. **J10 returns terminal outcome summary** (status pointer + evidence refs). 

---

### A quick “sanity check” tying IP1–IP4 to your outer pins

* SR is a batch-plane deployment unit invoked explicitly; engine runs are jobs invoked by SR; SR writes the run ledger and publishes join surface + READY.
* Local/dev/prod differences are **mechanics only** (timeouts, digests-on/off, concurrency), not semantics: the above IP routes stay identical everywhere.

---

## USER: "PAUSE FOR REFLECTION"

Yep — I’ve just re-checked the pinned docs you’ve given (platform blueprint + environment ladder + engine invocation + gate receipt), and I’m going to lock a **consistency checkpoint** here so we don’t drift or contradict ourselves later.

## 1) Authority stack we’re obeying

* **Platform blueprint** pins SR’s outer role: *invoke or reuse engine → verify required PASS gates → write SR ledger → publish RunReadySignal + run_facts_view by-ref*.
* **Engine invocation contract** pins the engine boundary shape and `run_id` constraints. 
* **Gate receipt contract** pins portable PASS/FAIL representation and the “fail closed” posture.
* **Environment ladder** pins: same graph + same semantics across local/dev/prod; only operational envelope differs.

Everything else (including your SR conceptual draft) is non-authoritative idea fuel. 

---

## 2) Non-negotiable invariants we’ve been using (and will keep using)

* **READY is binary and meaningful everywhere**: SR cannot emit READY unless required PASS evidence exists and SR’s `sr/*` truth surface is committed.
* **No PASS → no read**: SR refuses READY on missing/FAIL evidence; consumers fail closed too.
* **Evidence-based reuse only**: reuse means reconstructing the same evidence set (locators + required PASS receipts), never “files probably exist”.
* **Semantics do not vary by environment** (local/dev/prod).

---

## 3) Two key authority declarations we made (to avoid later confusion)

### A) `run_id` format

* **Consider `run_id` to be `hex32`** because the engine invocation contract requires `hex32`.
* If you want a human-readable label, it’s a separate non-semantic `run_label` (never used for joins). 

### B) Scenario binding vs platform `scenario_id`

Engine allows `scenario_binding` to be either `scenario_id` or `scenario_set`. 
To keep platform joins single-keyed, SR will define a single **platform `scenario_id`** as:

* If binding is `scenario_id`: use it directly.
* If binding is `scenario_set`: derive `scenario_id = "scnset_" + first16(sha256(sorted scenario_set))`, and record the full scenario_set in `run_plan/run_record` for traceability.

This keeps the platform’s “ContextPins include scenario_id” posture stable while still passing scenario_set to the engine when needed.

---

## 4) SR first-layer internal subnetworks (still the same)

We modularized SR into opaque subnetworks:

* **N1** Ingress & canonicalization
* **N2** Run authority core (idempotency mapping + lease)
* **N3** Policy/profile resolver + plan compiler (records policy_rev)
* **N4** Engine boundary orchestrator
* **N5** Evidence assembly + gate attestation (fail-closed)
* **N6** Ledger & join-surface publisher (`sr/*` + READY commit ordering) 
* **N7** Rehydration / re-emit (from ledger only)
* **N8** Observability & governance emitter (policy_rev always reported)

---

## 5) Illuminated joins we’ve locked so far

### J1–J5 (front spine)

* **J1** N1→N2: canonical intent + caller’s run-equivalence key ⇒ stable `run_id` + lease
* **J2** N2→N6: anchor run existence (`run_record START`, `run_status OPEN`, skeleton `run_plan`)
* **J3** N2→N3: bind to profile + `policy_rev`
* **J4** N3→N6: commit immutable run_plan; monotonic status update
* **J5** N3→N4: create an idempotent engine attempt with `engine_invocation` payload (contract-locked)

### J6–J11 (evidence + publish + ops + obs)

* **J6** N3→N5: reuse-evidence ticket (deterministic evidence check)
* **J7** N4→N5: attempt result ⇒ evidence harvest
* **J8** N5→N6: commit facts view + READY if and only if PASS evidence complete (strict order)
* **J9** N6→N7: ledger read ⇒ re-emit control facts (no recompute)
* **J10** N6→N1: caller-visible outcome summary (never lies; pointers not guesses)
* **J11** all→N8: structured telemetry + policy_rev reporting

---

## 6) Internal multi-hop paths we just illuminated (IP1–IP4)

* **IP1** New run → invoke engine → harvest evidence → verify PASS → commit `run_facts_view` → set READY → emit RunReadySignal
* **IP2** Duplicate submission → resolve same run_id → no duplicated side effects (no second plan, no second engine run)
* **IP3** Reuse path → no engine invocation → only succeeds if evidence bundle is COMPLETE+PASS; else falls into fail-closed behavior
* **IP4** Engine failure → commit terminal non-READY outcome; no READY emitted

---

## 7) What’s explicitly “next” (so we don’t trip)

When we continue, the next internal paths **IP5–IP8** will hinge on one design boundary we haven’t finalized yet:

* **WAITING vs FAIL** timing/thresholds for incomplete evidence (policy knob, semantics fixed)
* AUTO mode switching rule: reuse-check → invoke engine (while preserving attempt idempotency)

Those are the only big levers left before we can finish the internal path set without contradictions.

---

Cool — here are **IP5 → IP8** as **fully-designed internal multi-hop routes** through the SR subnetworks, using the joins we already illuminated (J1–J11). No “maybes”, and everything stays inside the outer guardrails: **engine invocation shape is fixed**, **gate receipts are fail-closed**, **SR truth is `sr/*` + control READY**, **READY is binary + monotonic**, **supersede not mutate**.

---

## IP5 — Missing/FAIL PASS evidence (WAITING / FAIL-CLOSED / QUARANTINE)

### What IP5 *is*

IP5 is the internal route SR takes when it **cannot assemble a complete admissible evidence bundle** (locators + required PASS receipts). It is the concrete implementation of “no PASS → no read” and fail-closed behavior.

### Where IP5 can start (two entrypoints)

* **From reuse-check**: after J6 (N3→N5) returns `WAITING` / `FAIL` / `CONFLICT`
* **From engine attempt**: after J7 (N4→N5) returns `FAIL` because the attempt failed or harvested evidence fails verification

### IP5 route (common spine)

1. **N1 → N2 → N6(early) → N3 → N6(plan)**
   Same as IP1/IP3 up through `run_status=PLANNED` and committed `run_plan`.

2. **Evidence evaluation happens**

   * If plan strategy includes reuse: **J6** (N3→N5) first
   * If plan strategy is force invoke (or AUTO already escalated): **J5→J7** (engine attempt then harvest into N5)

3. **N5 returns one of: WAITING / FAIL / CONFLICT** (these are *not* interchangeable; each has a forced SR reaction).

---

### IP5-A — WAITING (evidence incomplete, no FAIL observed yet)

**Trigger:** N5 returns `WAITING` with a `MissingEvidenceSet` and `next_check_at` time.

**Route:**

1. **J8 (N5→N6)** commits a *non-terminal* state update:

   * Append to `sr/run_record`: `EVIDENCE_WAITING` including:

     * missing outputs (by output_id)
     * missing required gate_ids (by gate_id)
     * next_check_at + evidence_wait_deadline
   * Set `sr/run_status = WAITING_EVIDENCE` (monotonic forward from PLANNED/VERIFYING)
   * **No READY is emitted.**

2. **Loop control (N3 controls the loop)**

   * N3 schedules a re-check at `next_check_at` and re-enters N5.
   * Each re-check is recorded as an append-only event in `run_record` (no silent looping).

3. **Exit conditions (designer-locked)**

   * If evidence becomes complete + PASS → **falls into IP1 commit section** via J8 READY commit.
   * If evidence_wait_deadline is hit:

     * If plan strategy is **AUTO** → **escalate to engine invoke** via J5 (N3→N4), then continue with J7 to N5 again.
     * If plan strategy is **FORCE_REUSE** → **terminal FAIL** (see IP5-B).
       (Force reuse must mean force reuse.)

---

### IP5-B — FAIL (gate FAIL, deadline exceeded, or “cannot prove”)

**Trigger:** N5 returns `FAIL` with a `FailureEvidenceBundle`. Causes include:

* One or more required `gate_receipt.status = FAIL`
* Missing required evidence beyond deadline
* Output exists but cannot be bound deterministically (e.g., required digest missing where policy demands it)

**Route:**

1. **J8 (N5→N6)** commits a *terminal non-READY* outcome:

   * Append to `run_record`: `EVIDENCE_FAIL` with:

     * failed gate_ids + their receipt refs
     * missing evidence summary (if deadline exceeded)
     * attempt_id (if this came from an engine attempt)
   * Set `run_status = FAILED` with a reason code:

     * `GATE_FAIL`
     * `EVIDENCE_MISSING_DEADLINE`
     * `UNBINDABLE_OUTPUT`
   * **READY is never emitted.**

2. **Return to caller (J10)**
   N1 returns `run_id` + terminal status pointer + evidence pointers (so the operator can inspect exactly why).

---

### IP5-C — CONFLICT (contradictory/unsafe evidence → QUARANTINE)

**Trigger:** N5 returns `CONFLICT` when evidence contradicts the pinned identity or is structurally unsafe, e.g.:

* output locator scope tokens don’t match the run pins
* digest mismatch against claimed content_digest
* multiple incompatible artifacts found for the same output identity

**Route:**

1. **J8 (N5→N6)** commits **QUARANTINED**:

   * Append `EVIDENCE_CONFLICT` with explicit contradiction details
   * Set `run_status = QUARANTINED`
   * **No READY** ever
2. Only an explicit operator correction (IP6) can replace it (supersede); SR does not auto-repair conflicts.

---

## IP6 — Post-READY correction (SUPSERSEDE, don’t mutate)

### What IP6 *is*

A correction after READY never rewrites the old run. It creates a **new run** and records a **supersedes edge**. Old READY remains historically true. 

### Trigger

Upstream submits a **CorrectionRunRequest** containing:

* `supersedes_run_id`
* `supersession_purpose` (named purpose)
* `reason_code` + human note
* corrected pins (may be the same world pins or a new world identity)
* a **new run-equivalence key** (required; otherwise reject)

### Route

1. **N1 canonicalizes** the correction request and produces a canonical intent that includes `supersedes_run_id` + purpose.

2. **N2 validates the target exists**

   * Reads `sr/run_status` for `supersedes_run_id` and verifies it exists (READY or not; correction is allowed either way).
   * If the target doesn’t exist → reject.

3. **J1 + J2** create a **new run_id** and anchor it (new truth surface).

4. **N3 plans the correction** (designer-locked rules)

   * If corrected pins differ (new fingerprint/params/seed etc): plan is **FORCE_INVOKE** (new world identity implies new build).
   * If pins are identical but correction is about policy/gates/serving intent: plan is **FORCE_REUSE** (prove admissibility under the new policy_rev) or **AUTO** if allowed by policy.

5. New run proceeds through **IP1 or IP3/IP5** until it reaches:

   * READY (preferred)
   * or a terminal non-READY outcome (still recorded)

6. **Supersedes recording (mandatory)**

   * N6 appends to **new run’s** `run_record`: `SUPERSEDES {old_run_id, purpose, reason_code}`
   * N6 appends to **old run’s** `run_record`: `SUPERSEDED_BY {new_run_id, purpose}`
   * Old `run_status` is unchanged (still READY if it was READY). This is “don’t mutate.” 

7. **Control-plane supersedes signal (mandatory)**

   * SR publishes `RunSupersedesSignal` on the control topic, idempotent by `(old_run_id, new_run_id, purpose)`.
   * This is for operators/offline systems; it does not invalidate the old READY.

---

## IP7 — Rehydration / replay of control-plane facts (re-emit)

### What IP7 *is*

A pure operational route: **re-emit READY or terminal control facts from the ledger**, without recomputing the world and without changing run_status. 

### Trigger

Upstream submits `ReemitRequest(run_id, kind, reason)` where `kind ∈ {READY_ONLY, TERMINAL_ONLY, BOTH}`.

### Route

1. **N1 canonicalizes + authorizes request** (policy-controlled: who can re-emit).

2. **N2 resolves run existence**

   * Finds the run and acquires a short **re-emit lease** keyed by `(run_id, kind)` to avoid concurrent spam.

3. **N7 reads the ledger**

   * Reads `sr/run_status`
   * If READY: reads `sr/run_facts_view` and its hash

4. **Publish (through N6 control publisher)**

   * If READY and kind allows: publish READY with idempotency key derived from `(run_id, facts_view_hash)`
   * If terminal and kind allows: publish terminal signal including status + pointer to run_record evidence
   * Append `REEMIT_DONE` to `run_record` (append-only; status unchanged)

5. **J10 returns** a success ack + pointer to the emitted control fact (if you keep those refs).

---

## IP8 — Offline rebuild entrypoint support (SR-side)

### What IP8 *is*

Inside SR, IP8 is the route that makes offline rebuilds possible **without scanning and without guessing** by providing:

* a discoverable set of runs
* and stable pointers to `run_facts_view` + policy_rev + window pins

Offline Shadow does the replay itself, but SR must supply the **run anchors** reliably.

### Trigger

Offline tooling submits `RunQuery` such as:

* filter by `scenario_id`, `manifest_fingerprint`, `parameter_hash`, window, status=READY
* optionally: “include supersession edges” (so it can choose preferred runs)

### Route

1. **N1 parses RunQuery** and validates it (no implicit “now”; window filters must be explicit).

2. **N2 authorizes + queries the Run Index**

   * Uses SR’s non-truth index (same store family as idempotency index) to find candidate `run_id`s efficiently (no object-store directory scan in production).

3. **N6 returns authoritative pointers**
   For each candidate run_id:

   * pointer to `sr/run_status`
   * pointer to `sr/run_plan` (for policy_rev + scenario binding + window)
   * if READY: pointer to `sr/run_facts_view`
   * if supersession requested: include supersedes relations by reading the run_record edges written in IP6

4. **N1 returns a RunAnchorBundle list**
   Offline Shadow then uses those anchors to replay from EB/Archive and build DatasetManifests — but SR’s job ends at delivering the anchors cleanly and consistently.

---

### Consistency check (so we don’t contradict ourselves later)

* **IP5** is the only place SR ever “waits” — and it never emits READY while waiting or failing.
* **IP6** always creates a **new run_id** and records `supersedes` edges; old READY is never rewritten. 
* **IP7** never invokes the engine; it replays control facts from `sr/*`. 
* **IP8** is SR’s discovery/anchor support for offline — truth stays in `sr/*`, index is convenience.

---

Yeah — **SR has to contain loops**. A production control-plane component can’t be purely acyclic because the platform is **at-least-once**, storage/bus are **retryable**, and evidence can be **eventually consistent**. These loops are **designer-required** inside SR:

---

## L1) Idempotent re-entry loop (duplicate RunRequests)

**Nodes:** N1 → N2 → (N6 read) → N1
**What it does:** Same run-equivalence key re-enters SR any number of times and always resolves to the **same `run_id` + current status/facts refs**, with **zero duplicated side effects**.
**Stop condition:** always immediate (it’s a “respond with current truth” loop, not a waiting loop).

---

## L2) Single-writer lease loop (leadership/ownership)

**Nodes:** N2 (and N6 as the durable truth writer)
**What it does:** While a run is being executed/verified, SR holds a **lease** and periodically renews it.
**Rule:** if the lease is lost, SR **must stop** writing/publishing for that run immediately.
**Stop condition:** run reaches a terminal state (READY / FAILED / QUARANTINED) or lease expires.

---

## L3) AUTO strategy loop (reuse-first → escalate-to-invoke)

**Nodes:** N3 ↔ N5, with a possible jump to N4
**What it does:** In `AUTO` mode:

1. Try **J6 reuse-evidence check**
2. If evidence is COMPLETE+PASS → commit READY
3. If evidence is WAITING until deadline → **escalate** to **J5 engine invoke**
4. Then harvest/verify again
   **Stop condition:** READY or terminal non-READY.

This loop is what makes SR fast in dev/local (reuse hits often) without changing semantics in prod.

---

## L4) Evidence WAITING refresh loop (eventual consistency loop)

**Nodes:** N5 ↔ N6 (status updates) ↔ N3 (scheduler)
**What it does:** When evidence is missing but not FAIL:

* SR enters `WAITING_EVIDENCE`
* schedules periodic re-checks
* appends each check to `run_record` (no silent spinning)
  **Stop condition:** evidence becomes COMPLETE+PASS → READY, or deadline → FAIL (or escalate if AUTO).

---

## L5) Engine attempt loop (retry / attempt history)

**Nodes:** N4 ↔ N6 (attempt logging)
**What it does:** SR may perform multiple **engine attempts** under policy-defined budgets:

* launch retries for transient infra errors
* attempt_no increments only when a prior attempt is terminal (FAILED/TIMED_OUT)
* every attempt is recorded in `run_record` and reflected in `run_status`
  **Stop condition:** a successful attempt yields admissible evidence (→ READY), or attempt budget exhausts (→ FAILED).

---

## L6) Post-attempt harvest/verify stabilization loop

**Nodes:** N4 → N5 ↔ N6 ↔ N3
**What it does:** Even if the engine finishes “successfully,” the **gate artifacts / receipts / indexes** SR needs may not be visible immediately.
So N5 can return WAITING *after* a successful attempt, and SR follows the same refresh loop (L4) until evidence settles or deadline hits.
**Stop condition:** COMPLETE+PASS → READY, or deadline → FAIL.

---

## L7) Commit + publish reliability loop (the “don’t lose READY” loop)

**Nodes:** N6 (Ledger Committer + Control Publisher) and N7 (re-emit)
**What it does:** Two reliability sub-loops:

1. **Commit retry loop:** object-store writes for `run_facts_view` / `run_status` / `run_record` can be retried idempotently using content hashes.
2. **Publish retry loop:** after READY is committed, publishing the READY control fact can retry idempotently (keyed by `(run_id, facts_view_hash)`).

**Critical rule:** SR never publishes READY *before* the ledger commit is durable.
**Stop condition:** READY published successfully, or (if publish keeps failing) SR relies on **L8** re-emit later.

---

## L8) Rehydration / re-emit loop (operational replay)

**Nodes:** N7 ↔ N6 (publish)
**What it does:** Operators/Run-Operate can request re-emission of control facts:

* SR reads `sr/*` truth
* re-emits READY/terminal signals idempotently
* does **not** invoke engine and does **not** mutate run_status
  **Stop condition:** always immediate per request; safe to repeat forever.

---

## L9) Index maintenance loop (production ergonomics, non-truth)

**Nodes:** N2/N6 (writers) + optional background reconciler
**What it does:** If SR has an index store (recommended for dev/prod), SR must maintain it:

* update index on every status/plan/facts commit
* periodically reconcile index ↔ `sr/*` ledger to repair drift after crashes
  **Rule:** index is never treated as truth; ledger wins.

---

Yep — **deployment is where this SR network becomes real**, and your environment ladder pins exactly how: **same graph + same semantics everywhere**, only the *operational envelope* changes.

## 1) What SR “is” as a deployment unit (production shape)

SR is a **job/service** that:

* reads **engine outputs + gate receipts** from the object store,
* optionally uses an `sr` DB (index/lease/idempotency convenience),
* writes **`sr/run_plan`, `sr/run_record`, `sr/run_status`, `sr/run_facts_view`** as truth,
* emits **READY** on **`fp.bus.control.v1`** (READY is meaningless without the `sr/*` truth surface).

In dev/prod, SR runs in a **launcher + executor** shape (can be one service that spawns jobs, but the two roles still exist):

* **SR Run Launcher (control plane entry)**: receives RunRequests, enqueues/starts execution, supports re-emit and run queries.
* **SR Execution (batch job)**: does the actual engine invoke/reuse + evidence verification + ledger commit + READY publish.

This fits the platform’s pinned runtime topology: **IG/DF/AL/DLA/DL** are always-on; **SR/Engine/Offline Shadow/Model Factory** are jobs.

## 2) Environment ladder: what stays identical vs what changes

### Identical across local/dev/prod (non-negotiable)

* **Same component graph + trust boundaries** (IG front door, EB fact log, SR readiness authority, etc.).
* **Same rails/join semantics** (ContextPins, canonical envelope, no-PASS-no-read, by-ref locators, idempotency, append-only + supersedes…).
* **Same meaning of READY/ADMITTED/ACTIVE/LABEL AS-OF/BACKFILL**.
* **Same reproducibility story**: a dev/prod run must be explainable the same way as local (pinned inputs + evidence + refs).

### Allowed to differ (the knobs that turn up the ladder)

* **Scale/concurrency**, **retention + archive**, **security strictness**, **reliability posture (HA/backups)**, **observability depth**, **cost knobs**.

## 3) How SR looks at each rung (concretely)

### Local

* You can run the whole graph on one machine, but SR must still behave as a real deployment unit: writes `sr/*` to object store, emits READY, obeys fail-closed rails (even if security allowlists are permissive).
* Typical “prod-shaped local” substrate: **single Redpanda broker + MinIO + Postgres + lightweight OTel**. 
* SR often runs as a **CLI/job runner**; engine invoked locally as a job.

### Dev

* Multiple services run **as they would in prod** (real networking boundaries). Dev is where you catch missing PASS evidence, unauthorized producers, schema drift, backfill behavior, etc.
* SR runs in the launcher+executor shape; policies are “real enough” (authn/authz, quarantine access, registry privileges).

### Prod

* SR is the same code, but the envelope is hardened: strict access control, strict change control, longer retention + archive continuity, SLO-grade observability.
* “Prod never relies on human memory”: every run outcome, policy rev, and change must be attributable and reproducible via durable facts.

## 4) Deployment angles to pin *before* opening inner nodes

### A) Profiles, not forks (how promotion works)

Promotion is **build once, run anywhere**:

* same binaries,
* same rails/contracts,
* different **environment profile** (wiring endpoints/credentials/retention thresholds),
* plus stricter **policy configs** at higher rungs.

### B) Split config into wiring vs policy (this matters for SR internals)

* **Wiring config**: endpoints, ports, resource limits, timeouts.
* **Policy config** (outcome-affecting): SR required gates, reuse permissions, evidence deadlines, etc. Must be **versioned + auditable**, and SR must report which `policy_rev` it used.

### C) CI/CD has three promotion lanes (SR participates in all)

1. **Code promotion** (services + jobs) with unit→contract→integration gates, including an end-to-end flow: **SR→Engine→IG/EB→…**
2. **Policy/profile promotion** (versioned artifacts; proposed→approved→active; rollback exists).
3. **Bundle promotion** (Model Factory → Registry activation).

### D) Stateful substrate assumptions SR must be designed against

Even before we open SR internals, the *deployment substrate contract* is already pinned:

* EB behaves like Kafka partitions+offsets; at-least-once is real; lag/watermarks observable.
* Object store behaves like S3 keys/prefixes; refs + digests are verifiable.
* DB is transactional and supports “authoritative timelines” (SR’s idempotency/lease index and other components’ truths).
* OTLP exists everywhere; traces/logs/metrics semantics match prod even locally.

### E) “Truth surfaces” vs “indexes” (crucial operational rule)

For SR specifically:

* `sr/*` artifacts in object store are **truth**.
* `sr` DB (if present) is **index/convenience** and may be rebuilt; it must never be the only copy of truth.

### F) What Codex needs so deployment doesn’t drift later

You’ve already pinned the minimal “implementability kit”:

1. one **bring-up-local-infra** command (Compose),
2. a **local profile** with endpoints + policy revs,
3. an **integration script** that runs one golden flow end-to-end (SR→Engine→IG/EB→…).

---

If we carry just these deployment pins into the next phase (opening inner nodes), the SR internals will naturally “snap” into:

* a launcher/executor runtime shape,
* policy-vs-wiring separation,
* truth-in-object-store with optional DB indexing,
* and build-once/run-anywhere promotion across the ladder.

---

## USER: PAUSE FOR REFLECTION, ABOUT TO GO DEEPER

([Past chat][1])([Past chat][2])([Past chat][1])([Past chat][3])([Past chat][3])

Locked — I’ve just “replayed” what we’ve already defined in this chat, and I’m freezing it into a **no-drift mental model** we can rely on before we open any deeper inner nodes.

If anything below is wrong, it means *I* made an assumption earlier — and we fix it now before we illuminate modules.

---

## 1) The outer-network constitution SR cannot violate

### SR’s platform role (non-negotiable)

SR is the **only readiness authority** and the **single join entrypoint** for downstream:

* SR produces durable truth in **object store**:
  `sr/run_plan`, `sr/run_record`, `sr/run_status`, `sr/run_facts_view`
* SR emits **control-plane** READY on `fp.bus.control.v1`
* Downstream starts from: **READY → run_facts_view → by-ref locators/proofs**
* SR is **not** the ingestion pipeline; **IG** is the trust boundary; **EB** is append/replay

### Gating law (platform-wide)

* **No PASS → no read**
* Fail-closed on missing/unknown evidence
* READY is binary and **monotonic** (never withdrawn)

### Engine boundary (design-authoritative)

* SR invokes engine using **engine_invocation** with required:
  `manifest_fingerprint`, `parameter_hash`, `seed`, `run_id`, `scenario_binding`
* Engine outputs are treated as immutable surfaces by identity partitions; SR never “interprets” engine internals — it only publishes references + proofs.

---

## 2) The SR component as a “network of opaque subnetworks”

We defined SR as **first-layer internal subnetworks** (still opaque at that level):

* **N1 Ingress & Canonicalization**
* **N2 Run Authority Core** (idempotency mapping + lease / single-writer)
* **N3 Policy/Profile Resolver + Plan Compiler**
* **N4 Engine Boundary Orchestrator**
* **N5 Evidence Assembly + Gate Attestation** (fail-closed)
* **N6 Ledger + Join Surface Publisher** (`sr/*` truth + READY commit ordering)
* **N7 Rehydration / Re-emit** (from ledger only)
* **N8 Observability / Governance Emitter**

At this point: **we are about to open these nodes**, so the only safe move is to keep their boundaries stable and avoid inventing semantics inside them.

---

## 3) The internal joins we already illuminated (SR’s “inner adjacency list”)

### Front spine

* **J1** N1→N2: canonical intent + caller run-equivalence key ⇒ stable run handle + lease
* **J2** N2→N6: anchor run existence (`run_record START`, `run_status OPEN`, skeleton plan)
* **J3** N2→N3: bind run to environment profile + policy_rev
* **J4** N3→N6: commit immutable run_plan; status becomes PLANNED
* **J5** N3→N4: start one idempotent engine attempt (attempt sentinel prevents double-launch)

### Evidence + publish + ops + obs

* **J6** N3→N5: reuse-evidence ticket (deterministic evidence check)
* **J7** N4→N5: attempt result → evidence harvest
* **J8** N5→N6: commit facts view + READY iff admissible evidence bundle is complete
* **J9** N6→N7: ledger read → re-emit control facts
* **J10** N6→N1: caller-visible outcome summary (pointers, never guesses)
* **J11** all→N8: structured telemetry + policy_rev reporting

---

## 4) The internal multi-hop paths we finalized (IP1–IP8)

* **IP1** new run → invoke engine → harvest evidence → PASS → commit facts → READY + signal
* **IP2** duplicate submission → resolves same run_id → no duplicated side effects
* **IP3** reuse without invoke → succeeds only if COMPLETE+PASS evidence exists
* **IP4** engine failure → terminal non-READY (no READY ever)
* **IP5** missing/FAIL evidence → WAIT loop or terminal FAIL/QUARANTINE (fail-closed)
* **IP6** post-READY correction → **supersede** via new run + supersedes edge; never mutate old READY
* **IP7** rehydration → re-emit READY/terminal from ledger only; never recompute
* **IP8** offline rebuild entrypoint support → SR provides discoverable run anchors via `sr/*` truth; indexes are convenience only

---

## 5) The loops we declared must exist (production reality)

* Idempotent re-entry loop (duplicates)
* Lease/single-writer loop
* AUTO reuse→invoke escalation loop
* Evidence waiting/refresh loop (pre- and post-engine completion)
* Engine attempt retry/attempt-history loop
* Commit + publish reliability loop (commit ordering + idempotent publish)
* Re-emit loop (ops replay)
* Optional index maintenance / reconciliation loop (index ≠ truth)

---

## 6) Deployment posture across the environment ladder

* Same semantics/graph across local/dev/prod
* Differences are envelope knobs only (scale, security strictness, retention/archive, observability depth, reliability posture)
* SR truth surface is always `sr/*` in object store; optional `sr` DB is index/convenience; never the only truth.

---

## 7) The “no wrong assumptions” guardrail for the next phase

When we start opening inner nodes, we will **not** change:

* meanings of READY / PASS / evidence
* commit ordering (facts view → status READY → READY signal)
* the rule that downstream starts at SR’s join surface
* the trust-boundary split (IG does admission; SR does readiness + join map)

If any inner-node idea would force a change to any of those, it’s rejected as drift.

---

If you’re happy with this checkpoint, the clean next step is: **pick the first inner node to open**. The highest-leverage (and least risky) is **N6 (Ledger + Join Surface Publisher)** because it’s the point where all prior work becomes durable truth and downstream safety.

---

Yep — your assumption is correct: **we’re not changing the network**, we’re just revealing the machinery inside each node to realize the already-fixed joins/paths.

## The nodes (first-layer SR subnetworks)

1. **N1 — Ingress & Canonicalization**
2. **N2 — Run Authority Core** (idempotency mapping + lease/single-writer)
3. **N3 — Policy/Profile Resolver + Plan Compiler**
4. **N4 — Engine Boundary Orchestrator**
5. **N5 — Evidence Assembly + Gate Attestation** (fail-closed)
6. **N6 — Ledger & Join Surface Publisher** (`sr/*` truth + READY commit ordering)
7. **N7 — Rehydration / Re-emit** (ops replay from ledger only)
8. **N8 — Observability / Governance Emitter**

## The order I want us to illuminate (designer choice)

This order minimizes rework and prevents drift because each step becomes a dependency for the next:

1. **N6 (Ledger & Join Surface Publisher)**
   Locks the “truth surface” shape and commit ordering that every other node must satisfy.

2. **N5 (Evidence Assembly + Gate Attestation)**
   Defines exactly what “admissible evidence” means so `run_facts_view` can be correct.

3. **N3 (Policy/Profile + Plan Compiler)**
   Defines strategy selection (AUTO/REUSE/INVOKE/REHYDRATE) + required gate set + policy_rev recording.

4. **N2 (Run Authority Core)**
   Defines idempotency mapping, lease model, and how duplicates/concurrency are prevented.

5. **N4 (Engine Boundary Orchestrator)**
   Defines attempt lifecycle + idempotent launch + retry semantics consistent with the lease and plan.

6. **N7 (Rehydration / Re-emit)**
   Simple once N6 is defined: reads ledger and re-emits idempotently.

7. **N1 (Ingress & Canonicalization)**
   Now we can finalize canonical intent, window normalization, and run-equivalence key behavior to feed N2/N3 cleanly.

8. **N8 (Observability / Governance)**
   Last, because it “observes” everything; once the internal events/state are stable, we pin what must be emitted and correlated.

---

Yep. **N6 is the “commit boundary” inside SR** — it’s the machinery that turns *intent + evidence* into **durable platform truth** (`sr/*`) and (only when legal) a **READY trigger** on the control bus. In your deployment pins, SR’s “must persist truth” is exactly: `sr/run_plan`, `sr/run_record`, `sr/run_status`, `sr/run_facts_view`, and the bus publish to `fp.bus.control.v1` (READY is meaningless without the `sr/*` truth surface).

Below is N6 **as its own internal subnetwork**, with the internal boxes that make it work.

---

## N6 internal subnetworks (opaque boxes inside N6)

### N6.A Artifact Addressing & Ref Builder

**Job:** deterministically derive all SR artifact locations/refs from run pins.
**Outputs:** stable ArtifactRefs for:

* `sr/run_plan`
* `sr/run_record`
* `sr/run_status`
* `sr/run_facts_view`
* and **a persisted copy of the READY signal** under `sr/` (you explicitly list “READY signals” under the `sr/` prefix).

**Non-negotiable:** addressing must be stable across local/dev/prod; only the bucket/root changes via profile.

---

### N6.B RunRecord Append Log Writer

**Job:** write an **append-only** run narrative (audit trail) that never lies and never “forgets”.
**Inputs:** structured record events from N2/N3/N4/N5/N6 (accepted, plan committed, attempt launched, evidence waiting/fail, ready committed, publish failed, etc.).
**Outputs:** `sr/run_record` append-only stream.

**Hard rules:**

* Append-only: no edits, no deletions.
* Idempotent append: replays must not duplicate the same logical event (each event has an `event_id` / deterministic key).
* Ordering is monotonic (sequence numbers or monotonic timestamps).
  This is how SR remains explainable when anything crashes mid-run.

---

### N6.C RunStatus State Machine (Monotonic Snapshot)

**Job:** maintain a **single “current state” snapshot** (`sr/run_status`) that downstream/ops can read quickly, while all history stays in `run_record`.
**Outputs:** `sr/run_status` as *latest snapshot*.

**Hard rules:**

* Monotonic transitions only (no “READY → FAILED”).
* Every status update must point to the evidence trail in `run_record`.
* `READY` is only allowed if `run_facts_view` exists and admissible evidence is complete.

---

### N6.D FactsView Committer (Join Surface Builder + Validator)

**Job:** build the **single join surface** (`sr/run_facts_view`) that downstream uses (no scanning).
**Inputs:** a **VerifiedEvidenceBundle** from N5 (output locators + PASS receipts), plus SR pins and policy metadata.
**Outputs:** `sr/run_facts_view`.

**Hard rules:**

* FactsView is written **only when** evidence is admissible (PASS where required).
* FactsView contains **portable pins**, not copied data:

  * Engine outputs are referenced as `engine_output_locator` objects (output_id + resolved path + identity fields + optional content_digest).
  * Gate outcomes are referenced as `gate_receipt` objects (gate_id + PASS/FAIL + scope; fail closed on missing/unknown).
* FactsView must include SR-ledger pointers (`run_plan`, `run_record`, `run_status`) so a consumer can always “walk back” to the authority chain.

---

### N6.E Commit Orchestrator (Write Ordering + Idempotency Guard)

**Job:** coordinate multi-write commits so we never publish READY “early” and never produce contradictory truth.
This box enforces the two core laws:

1. **Commit ordering law** (READY cannot lead the truth):

* write `run_facts_view`
* then set `run_status = READY`
* then append `READY_COMMITTED` to `run_record`
* then publish READY to `fp.bus.control.v1` and persist a copy under `sr/`

2. **Immutability/consistency law**:

* `run_plan` is immutable after commit: if a second plan differs → **PLAN_DRIFT** and SR stops.
* `run_facts_view` is immutable after READY: if a different evidence bundle arrives after READY → **CORRUPT** and SR stops (corrections are IP6: supersede, don’t mutate).

---

### N6.F Control Publisher (READY only)

**Job:** publish the platform entrypoint trigger.
**Outputs:** **RunReadySignal** to `fp.bus.control.v1`.

**Designer lock-in (to remove ambiguity):**

* **SR publishes ONLY READY on the control bus in v0.**
  Failures are observed via `sr/run_status` + `sr/run_record` (and rehydration is done by re-emitting READY once it exists). This aligns with your deployment table pin that SR’s bus output is the READY signal.

**Idempotency rule:** READY publish is idempotent by `(run_id, facts_view_hash)` so duplicates are safe in an at-least-once bus world.

---

### N6.G Index Projector (optional SR DB)

**Job:** maintain a fast query/index surface (e.g., “list READY runs by scenario/window”, “find run_id by equivalence key”).
**Truth rule:** index is **not** truth; it is rebuildable from `sr/*`. (Your deployment notes explicitly separate primary truths in object store from “indexes/views”.)

---

## N6 “entrypoints” (how other SR nodes use it)

N6 exposes exactly these internal operations:

1. **AnchorRun** (J2)
   Creates baseline truth: `run_record START`, `run_status OPEN`, skeleton `run_plan`.

2. **CommitPlan** (J4)
   Writes immutable `run_plan`, appends plan event, sets `run_status PLANNED`.

3. **CommitEvidence** (J8)
   Two branches:

* **VerifiedEvidenceBundle** → write `run_facts_view`, set `run_status READY`, append record, publish READY.
* **Failure/Waiting evidence** → append record, set `run_status WAITING_EVIDENCE / FAILED / QUARANTINED`, publish nothing.

4. **ReadTruthSurface** (supporting J9/J10)
   Return stable pointers to status/facts/record for re-entry and ops (truth always comes from `sr/*`).

---

## The key “why” of N6 (so we don’t drift later)

Your platform blueprint pins that SR’s boundary job is: **produce a join surface whose references are admissible**; if PASS evidence is missing/FAIL, SR must not declare READY.
N6 is the internal mechanism that makes that statement *true in production* (ordering, immutability, idempotency, and durable audit).

---

If you want the next node to open after N6, it should be **N5 (Evidence Assembly + Gate Attestation)**, because N6 is now fully defined in terms of “what it must be given” (locators + PASS receipts) and “what it will publish” (facts view + READY).

---

Yep — **N5 is the “evidence brain” of SR**. It takes “here’s the run + here’s what we intend to expose” and returns one of four outcomes:

* **COMPLETE** → a *VerifiedEvidenceBundle* that N6 can safely turn into `run_facts_view` + READY
* **WAITING** → evidence is incomplete but not failed yet (still fail-closed; just not settled)
* **FAIL** → evidence is missing beyond policy deadline or a gate failed
* **CONFLICT** → contradictory / unsafe evidence (quarantine)

This module is *entirely* governed by your engine interface pack: **No PASS → no read**, **gate verification is gate-specific**, and **instance-scoped outputs require instance proof bound to an `engine_output_locator` + digest**.

Below is **the machinery inside N5** (as a network of submodules inside N5).

---

## N5 internal subnetworks (opaque boxes inside N5)

### N5.A Output Intent Resolver

**Job:** Turn “intended outputs” into a concrete per-output checklist.

**Inputs:**

* `output_id[]` intent list from the plan (N3)
* run pins (`manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`, `run_id`)
* engine outputs catalogue entry for each `output_id` (path template + partition tokens + scope)

**Outputs:** `OutputCheckSpec[]` where each spec includes:

* required identity fields (based on catalogue partitions/scope)
* resolved expected path (from `path_template`)
* whether the output is *optional* vs required (catalogue availability rules)

**Hard law:** `output_id` must correspond to a catalogue entry; otherwise this is **CONFLICT**.

---

### N5.B Locator Builder

**Job:** Produce the portable **`engine_output_locator`** objects for each output you intend to expose.

**Inputs:** `OutputCheckSpec` + run pins
**Outputs:** `engine_output_locator` objects with:

* required: `output_id`, `path`
* and the correct identity fields (must include at least one of `manifest_fingerprint/parameter_hash/run_id/scenario_id`, per schema)

**Hard law:** locator `path` **must** be consistent with the catalogue `path_template` for that output id.

---

### N5.C Role Classifier (Traffic vs Truth vs Evidence)

**Job:** Ensure SR never mis-tags what is allowed to become “traffic”.

**Inputs:** output catalogue metadata (and interface taxonomy rules)
**Outputs:** `OutputRole` for each output: `business_traffic | truth_products | audit_evidence | ops_telemetry` 

**Hard law:** Only `business_traffic` is eligible for WSP streaming into IG → EB; everything else is *not traffic*. N5 only labels/records; it does not ingest.

---

### N5.D Gate Graph Resolver

**Job:** Decide which gates must be proven PASS for the intended outputs, including upstream dependencies.

**Inputs:**

* the intended output set
* `engine_gates.map.yaml` which states:

  * each `gate_id`
  * scope (e.g., fingerprint)
  * upstream gate dependencies
  * which outputs a gate authorizes (`authorizes_outputs`)

**Outputs:**

* `RequiredGateSet` = transitive closure of:

  * “gates that authorize any intended output”
  * plus all upstream dependencies of those gates

**Hard law:** Gate truth is **gate-specific**; do not assume one hashing method.

---

### N5.E Gate Artifact Locator

**Job:** For each required gate instance, resolve the authoritative on-disk artifacts.

**Inputs:** gate_id + scope + run pins
**Outputs:** resolved paths for:

* `_passed.flag`
* bundle root
* index path (and schema refs)

---

### N5.F Gate Verifier

**Job:** Produce portable **`gate_receipt`** objects (PASS/FAIL) by verifying the gate artifacts exactly per the gate definition.

**Inputs:** resolved artifacts + `engine_gates.map.yaml` verification_method (e.g., `sha256_bundle_digest`, field names, ordering rules, exclude list)
**Outputs:** `gate_receipt` objects with:

* `gate_id`
* `status` ∈ {PASS, FAIL}
* `scope` (must at least contain `manifest_fingerprint`, and may include narrower fields)
* optional digest + artifact pointers

**Hard law:** `gate_receipt.status` is only PASS/FAIL and consumers **fail closed** on missing/unknown status. That means N5 cannot “invent” PASS; if it can’t verify, it’s **WAITING** (within deadline) or **FAIL** (after deadline).

---

### N5.G Instance Proof Binder

**Job:** Enforce the interface rule: “instance-scoped outputs require instance proof bound to locator + digest”.

**Inputs:** output locators + scope classification (does it include any of `seed`, `scenario_id`, `parameter_hash`, `run_id`?)
**Outputs:** constraints that must be satisfied before the evidence bundle can be COMPLETE:

* For such outputs, `engine_output_locator.content_digest` **must be present**, because the instance PASS receipt must bind deterministically to `target_ref` + `target_digest`.

**Hard law:** If an output is instance-scoped and digest is required but cannot be formed, that’s **FAIL (UNBINDABLE_OUTPUT)**, not “best effort”.

---

### N5.H Evidence Completeness Evaluator

**Job:** Decide the outcome class (COMPLETE / WAITING / FAIL / CONFLICT) and produce the correct return bundle.

This module is where the “no maybes” rules live:

#### COMPLETE

All are true:

1. every required intended output is materialised at its resolved path (or explicitly optional)
2. every required gate receipt is **PASS**, including upstream dependencies
3. every locator’s scope tokens match the run pins (no drift)
4. every instance-scoped output has `content_digest` present and bindable

#### WAITING

All are true:

* no required gate is FAIL
* but some required artifacts/receipts/outputs are missing or not yet readable
* and current time < evidence deadline (from policy_rev)

#### FAIL

Any are true:

* any required gate receipt is FAIL
* evidence deadline exceeded with missing required evidence
* instance proof cannot be formed (e.g., digest required but absent)

#### CONFLICT (→ QUARANTINE upstream)

Any are true:

* locator identity fields contradict the run pins (wrong `manifest_fingerprint`, etc.)
* multiple incompatible materialisations exist for the same output identity
* digest mismatch (claimed digest vs computed digest)

---

### N5.I Evidence Bundle Canonicalizer + Hash

**Job:** Build a deterministic **evidence bundle hash** so N6 can commit idempotently and so READY can be idempotent by `(run_id, facts_view_hash)`.

**Inputs:** locators + receipts + policy_rev id + the intended output list
**Outputs:**

* `VerifiedEvidenceBundle` (if COMPLETE) containing:

  * `engine_output_locator[]`
  * `gate_receipt[]`
  * `bundle_hash`
* or a failure/wait bundle with `missing_set` / `failure_set`

**Hard law:** ordering is canonical (sort by `output_id`, sort receipts by `gate_id`). This ensures stable hashing across retries.

---

## N5 entrypoints (how it’s used by the rest of SR)

N5 is invoked in exactly two ways:

1. **Reuse-check entrypoint (J6)**
   N3 asks: “Without invoking engine, can you produce COMPLETE admissible evidence for these outputs + gates?”
   → N5 returns COMPLETE / WAITING / FAIL / CONFLICT.

2. **Post-attempt harvest entrypoint (J7)**
   N4 says: “Engine attempt finished (or failed); harvest and verify the evidence now.”
   → N5 returns a VerifiedEvidenceBundle (COMPLETE) or FailureEvidenceBundle.

Both entrypoints converge on the same internal machinery so “reuse evidence” and “fresh evidence” produce the same bundle shape.

---

## What N5 explicitly does NOT do (so SR doesn’t drift into other components)

* N5 does **not** wrap anything into the canonical event envelope (that’s IG’s ingestion worker).
* N5 does **not** publish to EB / traffic topics.
* N5 does **not** interpret “business meaning” of the outputs; it only verifies admissibility and classifies role (traffic vs not).

---

## Environment ladder knobs for N5 (semantics fixed, cost knobs vary)

Semantics do not change across local/dev/prod, but these knobs do:

* **Digest policy**

  * Always: instance-scoped outputs must be bindable (digest present)
  * Optional elsewhere: local can compute more digests for convenience; prod can compute only what policy demands.

* **Evidence wait deadlines / polling cadence**

  * local: short deadlines, fast polling
  * prod: longer deadlines, exponential backoff, more careful cost control

* **Caching**

  * local: in-memory
  * dev/prod: short-lived cache keyed by `(run_id, output_id)` and `(run_id, gate_id)` to avoid re-reading bundle indexes repeatedly

But **fail-closed** never changes.

---

If you want the next node after N5, it’s **N3** (Plan Compiler), because now we know exactly what N3 must ask N5 for: the intent list + required gates + policy knobs that drive COMPLETE vs WAITING vs FAIL.

---

Absolutely. **N3 is SR’s “brain stem”**: it takes a *run that exists* (from N2) and produces a **single immutable plan** that drives everything else (N4/N5/N6). It is also where the **environment ladder** is made real without drift: **wiring profile** is loaded for endpoints/timeouts, **policy profile** is loaded for outcome-affecting rules (required gates, reuse permissions, deadlines), and the **policy revision is stamped into the run** so the run is explainable later.

Below is **the machinery inside N3** (submodules inside the N3 node).

---

## N3 internal subnetworks

### N3.A Profile Loader (wiring, non-semantic)

**Job:** Load the environment wiring profile for this run (local/dev/prod) *without changing meaning*.
**Inputs:** `profile_id` (or implied by deployment) from N2 context.
**Outputs:** `WiringProfile` containing:

* object store root/bucket/prefix
* engine job runner endpoint (how to launch the engine job)
* control bus endpoint/topic (`fp.bus.control.v1`)
* timeouts/backoff parameters (launch timeout, publish timeout, evidence poll cadence)

**Hard law:** this config is *not* allowed to change what READY means; it only affects mechanics.

---

### N3.B Policy Loader (governed, outcome-affecting)

**Job:** Load the **policy config revision** that governs SR decisions.
Your deployment notes explicitly pin that “what constitutes readiness (SR required gates)” is policy config and must be versioned + auditable.

**Inputs:** `policy_profile` selector (from env profile) + optional request overrides (rare; typically disallowed in prod).
**Outputs:** `PolicyRev` bundle:

* `policy_id`, `revision`, `content_digest`
* `required_gate_policy` (how SR derives required gates)
* `reuse_policy` (allowed or not; AUTO vs FORCE_REUSE vs FORCE_INVOKE)
* `evidence_policy` (deadlines; digest requirements)
* `attempt_policy` (retry budgets; attempt limits)
* `reemit_policy` (who can re-emit READY, etc.)

**Hard law:** N3 must record `policy_rev` in the run so the run is attributable: “this happened under policy rev X.”

---

### N3.C Output Intent Builder (what SR intends to expose)

**Job:** Decide *which engine outputs* SR will expose in the eventual `run_facts_view` (by reference), and classify them by role so downstream can’t misuse them.

**Inputs:**

* run pins (`manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_id`, `run_id`)
* scenario binding (scenario_id or scenario_set)
* `engine_outputs.catalogue` metadata (path templates, scope, exposure, availability, role) 

**Outputs:** `OutputIntentSet`:

* `traffic_outputs[]` (role = `business_traffic`)
* `truth_outputs[]` (role = `truth_products`) **marked non-traffic**
* `audit_outputs[]` (role = `audit_evidence`) **marked non-traffic**
* `ops_outputs[]` (role = `ops_telemetry`) **marked non-traffic**

**Hard law (binding):** only `business_traffic` is eligible for ingestion to EB; audit/telemetry/truth must not be treated as traffic. 

**Designer lock-in for v0:** SR must include **at least** the `business_traffic` outputs in its intent (so IG can pull-ingest after READY). Whether SR includes truth/audit outputs in facts view is allowed, but they must be role-tagged as **non-traffic** (so nobody “accidentally buses labels”).

---

### N3.D Required Gate Synthesizer (derive the gate closure)

**Job:** Compute the **exact required gate set** that must be PASS for SR to declare READY, based on the outputs it intends to expose.

**Inputs:**

* `OutputIntentSet` (from N3.C)
* `engine_gates.map.yaml` (gate_id → authorizes_outputs + upstream dependencies + verification method)

**Outputs:** `RequiredGateSet` computed as:

* all gates whose `authorizes_outputs` intersects the intended output_ids, plus
* the transitive closure of each gate’s `upstream_gate_dependencies`

**Hard law:** gates are **gate-specific**; N3 cannot assume a universal hashing method—verification method is defined per gate.

---

### N3.E Strategy Selector (the run mode decision)

**Job:** Choose the **execution strategy** deterministically.

**Inputs:** caller request + policy_rev + run context.
**Outputs:** `strategy` ∈:

* `REHYDRATE_ONLY` (control-plane replay only)
* `FORCE_INVOKE`
* `FORCE_REUSE`
* `AUTO` (reuse-first then escalate)

**Deterministic precedence (designer-locked):**

1. If request is re-emit / rehydration command → `REHYDRATE_ONLY`
2. Else if policy_rev disallows reuse → `FORCE_INVOKE`
3. Else if caller explicitly requests reuse-only (and policy allows) → `FORCE_REUSE`
4. Else → `AUTO`

This is where you ensure local/dev/prod are “profiles not forks”: same logic, different policy strictness.

---

### N3.F Budget & Deadline Planner (the knobs that drive loops)

**Job:** Produce the “numbers” that control WAIT loops and retry loops (but not semantics).

**Inputs:** wiring profile + policy_rev.
**Outputs:**

* evidence wait deadline and poll cadence (feeds N5 WAITING loop)
* engine attempt max count and retry budgets (feeds N4 attempt loop)
* publish retry budgets (feeds N6 publish reliability loop)

**Hard law:** these are policy/wiring controls only; they never permit READY without PASS evidence.

---

### N3.G Plan Canonicalizer + Plan Hash

**Job:** Make the plan **immutable and comparable** (so “PLAN_DRIFT” is detectable).

**Inputs:** everything above (pins, output intents, required gate set, strategy, budgets, policy_rev).
**Outputs:** `RunPlan` + `plan_hash` where the canonical serialization is stable:

* ordered lists (outputs sorted by output_id; gates sorted by gate_id)
* policy_rev captured explicitly

This supports the strict rule we already laid down: **one run_id → one plan meaning** (no “rewrite the plan later”).

---

### N3.H Ticket Factory (execution tickets to N4 and N5)

**Job:** Convert a committed plan into the concrete “tickets” other nodes understand.

**Outputs (two ticket types):**

1. **EngineExecutionTicket → N4** (J5)
   Contains the exact `engine_invocation` payload required by your contract:
   `manifest_fingerprint`, `parameter_hash`, `seed`, `run_id`, `scenario_binding` (+ optional request_id). 
   Also includes attempt budgets/timeouts.

2. **ReuseEvidenceTicket → N5** (J6)
   Contains:

* output intent list (output_ids + roles)
* required gate set (gate_ids + scope constraints)
* evidence deadline and digest policy (what must have `content_digest` to be bindable)

This is what allows “reuse is reuse of evidence” instead of guessing.

---

### N3.I Plan Commit Interface (to N6) + Observability Stamp (to N8)

**Job:** Publish plan as durable truth and emit the “this run is governed by policy_rev X” fact.

**To N6 (J4):**

* write `sr/run_plan`
* append `PLAN_COMMITTED`
* advance status to `PLANNED`

**To N8 (J11):**

* emit a structured event “PLAN_COMMITTED” that includes:

  * `policy_rev`
  * strategy
  * required gates count/list hash
  * intended outputs hash
    This aligns with your governance posture that outcome-affecting config changes must be attributable.

---

## What N3 must never do (to avoid SR drifting into other components)

* N3 does **not** verify gates (that’s N5, using gate-specific methods).
* N3 does **not** write READY or facts view (that’s N6).
* N3 does **not** ingest traffic or wrap envelopes (that’s IG).

---

## The single sentence definition (so we stay aligned)

**N3 deterministically compiles an immutable RunPlan (strategy + intended outputs + required gate closure + budgets) under a recorded policy revision, then issues execution tickets to either N4 (invoke) or N5 (reuse check).**

---

Yep — **N2 (Run Authority Core)** is the SR subnetwork that makes the whole system *safe under duplicates, concurrency, crashes, and replays*. It does two things, and it owns them **exclusively**:

1. **Run identity binding** (run-equivalence → one `run_id`, collision-checked)
2. **Single-writer leasing** (only one executor is allowed to advance a run at a time)

This lines up with your deployment truth that SR is a job/service with optional `sr` DB, but **truth lives in `sr/*`** and READY is meaningless without it.

Below is the machinery inside N2.

---

## N2 internal subnetworks

### N2.A Canonical Intent Gate

**Job:** refuse ambiguity before it becomes drift.

**Inputs:** `CanonicalRunIntent` from N1 (already normalized scenario binding + explicit window + world pins) plus **caller run-equivalence key**.
**Outputs:** `RunIntentAccepted` or `RunIntentRejected`.

**Hard laws (no exceptions):**

* **Run-equivalence key is required**. If missing → reject.
* The intent must include the engine pins that SR must eventually pass into `engine_invocation` (`manifest_fingerprint`, `parameter_hash`, `seed`, `scenario_binding`). 
* Window/time must be explicit (no implicit “now”). (Platform rail)

---

### N2.B Intent Fingerprinter

**Job:** produce a stable, deterministic fingerprint of the *semantic run intent*.

**Inputs:** canonical intent fields (world pins + scenario binding + explicit window).
**Outputs:** `intent_fingerprint = sha256(canonical_semantic_intent_bytes)`.

**Important:** this fingerprint is used for **collision detection**, not for choosing “latest” or anything like that.

---

### N2.C Run ID Deriver (designer lock-in)

We need `run_id` to be:

* **hex32** (engine contract), and
* **new-run capable** even if the world pins are identical (because you might want multiple run executions for the same world) 

**Designer declaration (final):**

* `run_id = hex32( sha256("sr_run|" + run_equivalence_key)[0:16] )`

So:

* duplicate submissions with the same run-equivalence key resolve to the same `run_id`
* a new run attempt is created by using a new run-equivalence key (new `run_id`)

This aligns with the engine contract requiring `run_id: hex32`. 

---

### N2.D Equivalence Registry (Idempotency Binding Store)

**Job:** bind “what the caller meant” to “what the platform will call this run”.

**Key:** `run_equivalence_key`
**Value:** `{ run_id, intent_fingerprint, first_seen_at, last_seen_at, invoker (non-semantic) }`

**Hard laws:**

* Insert is atomic: the binding either exists or is created exactly once.
* Updates only touch `last_seen_at` and optional non-semantic metadata.

---

### N2.E Collision Guard (anti-drift enforcement)

**Job:** prevent “same equivalence key, different meaning”.

When `run_equivalence_key` already exists:

* N2 compares stored `intent_fingerprint` to the new one.
* If they differ → **EQUIV_KEY_COLLISION** (reject).

This is the drift-killer that stops callers (or humans) from accidentally reusing an idempotency key for a different world/scenario/window.

---

### N2.F Lease Manager (Single-Writer Authority)

**Job:** guarantee only one SR executor can advance a run at once.

**Lease key:** `run_id`
**Lease fields:** `{ owner_id, lease_token, expires_at, generation }`

**Hard laws:**

* Every state-advancing write to `sr/*` must present a valid `lease_token` owned by that executor.
* Lease is time-bounded; it must be renewed.
* If lease is lost or expires, the executor must stop writing and publishing immediately.

This is what makes the SR network safe under:

* two SR workers racing,
* worker crash mid-commit,
* retries and replays.

---

### N2.G Leader / Follower Router (duplicate handling in practice)

**Job:** decide what N2 returns when it can’t get the lease.

Outcomes:

* **Leader**: lease acquired → proceed with J2/J3/J4…
* **Follower**: lease held by someone else → return `run_id` + pointers to current `sr/run_status` (and optionally facts view ref if READY) and stop.

This is how duplicate submissions become **read-only** rather than double execution.

---

### N2.H Run Pointer Resolver (truth pointers, not truth rewriting)

**Job:** quickly locate the run’s truth surface in object store.

Given `run_id` (and `scenario_id` if you partition SR artifacts by it), N2 can return stable pointers to:

* `sr/run_status`
* `sr/run_record`
* `sr/run_plan`
* `sr/run_facts_view` (if READY)

This does **not** make N2 the truth owner — it just makes duplicate requests and ops tooling fast.

(And it stays consistent with “truth is in `sr/*`” from the deployment notes.)

---

### N2.I Ops Micro-Lease (re-emit / ops commands)

**Job:** stop operational commands from stampeding.

For ops actions like “re-emit READY” (handled by N7), N2 issues a short **ops lease** keyed by `(run_id, op_kind)` so you don’t get 50 re-emit publishes at once. This keeps the control topic sane in prod.

---

### N2.J Observability Hooks (to N8)

**Job:** emit structured events for the “authority moments”:

* EQUIV_KEY_BOUND / EQUIV_KEY_COLLISION
* LEASE_ACQUIRED / LEASE_BUSY / LEASE_LOST
* ROLE=LEADER vs ROLE=FOLLOWER

(These are the breadcrumbs you need for prod debugging, and they must carry `run_id` + the join pins.)

---

## N2’s external “API” to the rest of SR (what other nodes rely on)

### Operation 1: `ResolveRunHandle(intent, run_equivalence_key)`

Returns:

* `run_id`
* `first_seen` boolean
* `intent_fingerprint`
* `leader_or_follower`
* if leader: `lease_token`
* if follower: `run_status_ref` (and `run_facts_view_ref` if READY)

### Operation 2: `RenewLease(run_id, lease_token)`

* extends expiry if token is still current; otherwise signals lease lost.

### Operation 3: `ReleaseLease(run_id, lease_token)`

* releases leadership cleanly (end of run, or abort).

### Operation 4: `GetRunPointers(run_id)`

* read-only pointer resolution for ops / duplicates / offline anchor listing.

---

## Two critical invariants N2 enforces (so nothing downstream contradicts anything)

1. **One equivalence key → one run meaning** (collision guard)
2. **One run_id → one active writer at a time** (lease)

Everything else in SR (planning, engine orchestration, evidence verification, ledger commits, READY publish) is built on those two.

---

If you want, the next node to open is **N4 (Engine Boundary Orchestrator)** — because now we’ve nailed: *how a run becomes uniquely owned*, which is the prerequisite for “exactly-once engine attempt launch semantics” inside SR while still living in an at-least-once world.

---

Got it — **N4 (Engine Boundary Orchestrator)** is the SR subnetwork whose *only* job is to run the **engine attempt lifecycle** safely in an at-least-once world, and hand off a clean **AttemptResult** to N5 for evidence harvesting/verification. It never declares READY, never verifies gates, and never interprets engine internals (that’s N5 + N6).

Below is **N4’s internal machinery** (sub-modules inside N4).

---

## N4 internal subnetworks

### N4.A Ticket Validator & Invocation Finalizer

**Job:** accept the `EngineExecutionTicket` from N3 and produce the *final* `engine_invocation` payload.

**What it enforces (hard):**

* The invocation payload MUST match the engine contract required fields:
  `manifest_fingerprint`, `parameter_hash`, `seed`, `run_id`, `scenario_binding`. 
* It sets **`request_id = attempt_id`** (idempotency at the invocation boundary), and sets `invoker` / `notes` if provided (non-semantic). 

**Why this exists:** the engine contract explicitly allows an optional `request_id` for client-provided idempotency; N4 owns that idempotency key because it owns attempt identity.

---

### N4.B Attempt Registry & Idempotency Guard

**Job:** ensure SR never launches the same attempt twice, even under retries/crashes.

**Attempt identity (designer-locked):**

* `attempt_no` is provided by N3 (policy/budget decides whether to try again).
* `attempt_id = hex32(sha256("sr_attempt|" + run_id + "|" + attempt_no)[0:16])`
  (deterministic, stable across restarts).

**Attempt sentinel (hard):**

* Before launching, N4 must create an atomic “attempt-start sentinel” keyed by `(run_id, attempt_no)` that stores `{attempt_id, request_id, created_at, job_id?}`.
* If the sentinel already exists, N4 **must not launch**; it returns the existing attempt handle and continues monitoring that job instead.

---

### N4.C Ledger Touchpoint Client (writes go through N6)

**Job:** request the durable “attempt facts” be recorded in SR truth surfaces.

On attempt start N4 causes:

* `run_record` append: `ENGINE_ATTEMPT_LAUNCH_REQUESTED(attempt_id, attempt_no, request_id)`
* `run_status` update: `EXECUTING(attempt_id, attempt_no)`
  (Still monotonic; N6 is the writer of truth, N4 is the producer of “what to record.”)

On attempt finish N4 causes:

* `run_record` append: `ENGINE_ATTEMPT_FINISHED(outcome, duration, job_id, reason_code)`
* (No READY. No facts view. No gate decisions.)

---

### N4.D Job Runner Adapter

**Job:** provide a single internal interface so local/dev/prod can launch engine jobs differently without changing semantics.

N4 talks to an internal `JobRunner` interface with exactly:

* `submit(invocation, idempotency_key) -> job_id`
* `get_status(job_id) -> {RUNNING|SUCCEEDED|FAILED}`
* `get_logs_ref(job_id) -> ref` (optional)
* `cancel(job_id)` (used deterministically, see N4.F)

**Environment ladder posture:** the adapter swaps implementation (local process vs container vs cluster job), but *the SR semantics do not change*.

---

### N4.E Launch Controller (submission retries inside one attempt)

**Job:** deal with transient submission failures without creating duplicate jobs.

**Hard rules:**

* Launch retries happen **within the same attempt_id** using the same `idempotency_key = request_id = attempt_id`.
* If submission fails after the launch retry budget (policy), the attempt is marked **FAILED** with reason `LAUNCH_FAILED` and no further progress occurs in that attempt.

---

### N4.F Execution Monitor + Timeout Enforcer

**Job:** poll the job runner until terminal state or timeout.

**Hard rules:**

* N4 uses polling (uniform across environments; mechanics vary by profile).
* If engine execution exceeds `engine_deadline` (policy), N4 marks attempt outcome as **TIMED_OUT** and issues `cancel(job_id)` (best-effort cleanup, but recorded either way).
* If the SR **loses its lease** while monitoring (N2 lease lost), N4:

  * stops making any further writes/publishes,
  * issues `cancel(job_id)` (cleanup),
  * returns attempt outcome **FAILED** with reason `LEASE_LOST`.
    (This prevents “non-leader” SR instances from advancing truth.)

---

### N4.G Outcome Normalizer (AttemptResult builder)

**Job:** produce the handoff object that feeds J7 (N4→N5).

**Output:** `EngineAttemptResult` always includes:

* `run_id`, `attempt_id`, `attempt_no`
* the final `engine_invocation` payload used (including request_id) 
* `attempt_outcome ∈ {SUCCEEDED, FAILED, TIMED_OUT}`
* `reason_code` (e.g., `ENGINE_FAILED`, `ENGINE_TIMEOUT`, `LAUNCH_FAILED`, `LEASE_LOST`)
* `job_id` (if any)
* diagnostic refs (below)

This is the *only* thing N5 needs from N4: “what attempt ran, and what happened.”

---

### N4.H Diagnostics & Provenance Collector

**Job:** attach stable pointers for debugging and audit, without contaminating semantics.

It records (by reference):

* `job_logs_ref` (if obtainable)
* `engine_invocation` used (already included)
* any job-runner metadata needed to reproduce investigation (cluster job name, image digest, etc.)

**Important:** these are **non-semantic** for readiness; they are for humans/ops and the run_record trail.

---

### N4.I Observability Emitters (to N8)

**Job:** emit structured telemetry for the “engine boundary moments” with correlation pins:

* `run_id`, `scenario_id`, `manifest_fingerprint`, `parameter_hash`, and `seed` (where applicable)

Mandatory events:

* ENGINE_ATTEMPT_START (attempt_id, attempt_no)
* ENGINE_JOB_SUBMITTED (job_id)
* ENGINE_ATTEMPT_FINISH (outcome + duration)
* ENGINE_ATTEMPT_TIMEOUT / ENGINE_LAUNCH_FAILED / LEASE_LOST

---

## What N4 explicitly does NOT do (so SR doesn’t drift)

* It does **not** verify PASS gates or read `_passed.flag` bundles (gate verification is gate-specific and is N5’s job).
* It does **not** assemble `engine_output_locator` or `gate_receipt` sets for readiness (N5 does that, then N6 commits facts+READY).
* It does **not** publish READY (only N6 does, after admissible evidence exists).

---

## The one-sentence definition

**N4 deterministically executes (or resumes monitoring of) exactly one engine attempt per `(run_id, attempt_no)` using `engine_invocation` + `request_id` idempotency, records attempt facts via N6, and returns a normalized AttemptResult to N5 for evidence harvesting.**

---

Yep — **N7 (Rehydration / Re-emit)** is SR’s **operational replay subnetwork**. Its whole job is to **replay control-plane facts from SR’s durable truth (`sr/*`)** so downstream can recover from missed messages/outages **without recomputing the world** and **without mutating history**.

This aligns with the outer pins we set: SR’s authoritative truth is `sr/*` and READY is a control-plane trigger on `fp.bus.control.v1`; replays must be idempotent in an at-least-once bus world.

Below is the machinery inside **N7**.

---

## N7 internal subnetworks

### N7.A Re-emit Request Intake + Authorization

**Job:** accept an operational command and decide if it is allowed.

**Inputs:** `ReemitRequest` with:

* `run_id`
* `reemit_kind ∈ {READY_ONLY, TERMINAL_ONLY, BOTH}`
* `reason` (audit-only)
* caller identity / role

**Hard laws:**

* N7 must enforce a **policy-based allowlist**: who can re-emit in dev/prod (local can be permissive; semantics unchanged).
* A re-emit request is never allowed to *change* run truth. It only triggers publishes.

**Output:** `AuthorizedReemitIntent` or `Denied`.

---

### N7.B Run Existence & Status Resolver

**Job:** fetch the authoritative current state from `sr/run_status` and locate the truth surface.

**Inputs:** `run_id`
**Reads:** from object store truth:

* `sr/run_status`
* if READY: `sr/run_facts_view` pointer/ref (and hash)
* always: `sr/run_record` pointer/ref (for terminal evidence pointers)

**Hard laws:**

* N7 never trusts any index as truth; it uses `sr/*` artifacts as the authority.
* If `sr/run_status` is missing, re-emit fails with `RUN_NOT_FOUND`.

**Outputs:** `RunTruthSnapshot`:

* `status_state`
* `facts_view_ref` + `facts_view_hash` (if READY)
* `status_ref` + `record_ref`

---

### N7.C Re-emit Idempotency Key Builder

**Job:** ensure re-emits are safe under retries/duplicates.

**Designer-locked idempotency:**

* READY re-emit key = `reemit_key = sha256("ready|" + run_id + "|" + facts_view_hash)`
* Terminal re-emit key = `sha256("terminal|" + run_id + "|" + status_state + "|" + status_version_hash)`

This guarantees:

* if the facts view didn’t change (it must not after READY), the READY publish is idempotent forever.
* terminal re-emits are stable for the same terminal snapshot.

**Output:** `ReemitKeys`.

---

### N7.D Ops Micro-Lease (anti-stampede gate)

**Job:** prevent 20 operators (or automation) from spamming the control topic.

**Mechanism:** acquire a short-lived lease keyed by `(run_id, reemit_kind)` (via N2’s ops micro-lease capability).
**Hard law:** if lease cannot be acquired, N7 returns `BUSY` and does nothing else.

This is purely operational hygiene; it doesn’t change semantics.

---

### N7.E Control Fact Composer

**Job:** build the exact control-plane messages to publish.

**Inputs:** `RunTruthSnapshot`, `ReemitRequest`, `ReemitKeys`
**Outputs:** one or two control messages:

1. **READY message (only if status is READY and kind allows)**:

* includes run pins
* includes `facts_view_ref`
* includes `reemit_key` (idempotency)
* includes `reason` (audit-only)

2. **TERMINAL message (only if status is terminal and kind allows)**:

* includes run pins
* includes `status_state`
* includes `status_ref` + `record_ref` (so consumers can inspect evidence)
* includes terminal `reemit_key`

**Hard laws:**

* If status is not READY, N7 must not emit READY.
* If status is not terminal, N7 must not emit terminal messages.

---

### N7.F Publisher (delegated to N6 Control Publisher)

**Job:** publish the composed control facts to `fp.bus.control.v1`.

**Hard laws:**

* Publishing is **idempotent** using the reemit keys.
* If publish fails, N7 records the failure in `sr/run_record` (append-only) and returns a failure to the caller.

(Implementation detail: N7 can call N6’s control publisher submodule, so all control-bus publishing uses one consistent mechanism.)

---

### N7.G RunRecord Audit Appender

**Job:** leave an auditable trail that a re-emit occurred.

**Writes (via N6’s run_record append machinery):**

* `REEMIT_REQUESTED(run_id, kind, reason, actor)`
* `REEMIT_PUBLISHED(reemit_key, message_ids)` or `REEMIT_PUBLISH_FAILED(error)`

**Hard law:** N7 must not change `run_status` during re-emit. (Re-emit is not a state transition.)

---

### N7.H Observability Emitter (to N8)

**Job:** emit structured telemetry for rehydration operations.

Mandatory events:

* REEMIT_REQUESTED
* REEMIT_DENIED (if unauthorized)
* REEMIT_BUSY (if micro-lease not acquired)
* REEMIT_PUBLISHED (with reemit_key)
* REEMIT_FAILED (with error class)

All events carry `run_id` and the run/world pins.

---

## What N7 explicitly does NOT do

* It does **not** invoke the engine (no N4 calls).
* It does **not** verify gates or touch evidence (no N5 work).
* It does **not** recompute `run_facts_view` or change `run_status`.
* It does **not** publish traffic to EB (control-plane only).

N7 is purely: **read truth → publish trigger again**.

---

## N7 as an operational capability (why it matters)

This module is what makes your platform recoverable:

* if IG missed READY (consumer down), you re-emit instead of re-running the engine
* if downstream services are redeployed, you re-emit to re-trigger WSP streaming
* if you restore from backups, you can rebuild consumers’ state by re-emitting control-plane facts

All while respecting the pinned rule: **the ledger is the authority; the bus is a trigger.**

---

Yep — here’s **N1 (Ingress & Canonicalization)** as a *white-box subnetwork* (its internal machinery), still aligned to the already-fixed joins/paths.

## N1’s job in one sentence

**N1 turns “whatever arrived at SR” into one canonical, drift-free intent object (or rejects it), then routes it to the right SR subnetwork.**
It does **no planning**, **no engine work**, **no gate verification**, **no READY publishing**.

---

## N1 internal subnetworks

### N1.A Request Classifier & Router

**Role:** Decide *what kind of SR request this is* and route it.

* **RUN_SUBMIT** (normal run)
* **CORRECTION_SUBMIT** (post-READY supersede request; triggers IP6)
* **REEMIT** (ops replay; routes to N7)
* **RUN_QUERY** (offline tooling wants anchors; routes to N2/N6 read surfaces)

**Hard rule:** Routing is purely by request kind; no “guessing” based on missing fields.

---

### N1.B AuthN/AuthZ Gate

**Role:** Verify caller identity and permissions *at the boundary*.

* Local can be permissive; dev/prod are strict — but **semantics are identical** (authorization never changes what READY means, only whether you’re allowed to ask).

**Hard rule:** Unauthorized requests are rejected early and still become observable (via N8).

---

### N1.C Minimal Shape Validator

**Role:** Fail fast on malformed inputs (format, type, missing required fields).
This validator is strict for the fields that affect determinism:

* `manifest_fingerprint` must be **hex64**
* `parameter_hash` must be **hex64**
* `seed` must be **uint64**
* request kind must be valid
* for RUN_SUBMIT/CORRECTION_SUBMIT: **run-equivalence key is required** (no exceptions)
* for REEMIT: `run_id` is required
* for RUN_QUERY: filters must be explicit (no implicit “now”)

---

### N1.D Scenario Binding Normalizer

**Role:** Canonicalize the scenario binding in a way that stays join-safe across the platform.

**Designer-locked behavior:**

* If request provides `scenario_id`: use it directly.
* If request provides `scenario_set`: sort + dedupe it, then derive a single platform join key:
  `scenario_id = "scnset_" + first16(sha256(joined_sorted_set))`
  and keep the full `scenario_set` in the canonical intent as traceable data.

This prevents platform drift where some places treat scenario_set differently than others.

---

### N1.E Window / Time-Key Normalizer

**Role:** Enforce the “no implicit now” rail and produce one canonical time representation.

**Designer-locked behavior:**

* N1 requires an **explicit window** (start/end + tz, or an explicit window_id that resolves deterministically).
* Canonical form always includes:

  * `window_start_utc`
  * `window_end_utc`
  * `window_tz` (the declared timezone context)
* It rejects:

  * missing end/start
  * start ≥ end
  * “today / yesterday” style vague input unless already resolved by the caller into explicit bounds.

This keeps local/dev/prod consistent and prevents “runs that mean different things” due to time ambiguity.

---

### N1.F Run-Equivalence Key Handler

**Role:** Capture *what the caller means by “same run”* so SR can be idempotent.

**Designer-locked behavior:**

* RUN_SUBMIT and CORRECTION_SUBMIT **must** include a `run_equivalence_key`.
* N1 treats the key as **semantic** (part of the intent contract), but does **not** interpret it.
* N1 strips/normalizes only trivial formatting (e.g., trim whitespace); everything else is caller-controlled.

This directly feeds N2’s collision guard (“same key, different intent” becomes a hard reject later).

---

### N1.G Canonical Intent Assembler

**Role:** Build the single object that crosses **J1 → N2**.

**CanonicalRunIntent contains:**

* `request_kind`
* `scenario_binding` (scenario_id or scenario_set) + derived platform `scenario_id`
* `manifest_fingerprint`, `parameter_hash`, `seed`
* `window_*` canonical fields
* `run_equivalence_key` (where required)
* optional: `requested_strategy` (FORCE_REUSE / FORCE_INVOKE / AUTO) — treated as a hint subject to policy later
* non-semantic metadata: `invoker`, `notes`, `client_request_id` (kept for audit, excluded from semantic identity)

**Hard rule:** Only the semantic subset is used downstream for intent fingerprinting; non-semantic fields never affect run identity.

---

### N1.H Rejection Mapper (Hard Failures Only)

**Role:** Convert invalid input into explicit, stable rejection reasons (so humans and automation can act).
Examples of rejection classes N1 owns:

* `BAD_KIND`
* `MISSING_EQUIV_KEY`
* `BAD_HEX64`
* `BAD_SEED`
* `INVALID_WINDOW`
* `SCENARIO_BINDING_INVALID`
* `UNAUTHORIZED`

(These are boundary-level; deeper semantic conflicts are handled by N2/N3/N5.)

---

### N1.I Response Builder

**Role:** Provide an immediate, non-lying response to the caller.

**Designer-locked behavior:**

* N1 always returns an acknowledgment quickly.
* It does not pretend the run is READY.
* It returns whatever is already true after N2/N6 interaction:

  * `run_id` (from N2)
  * current `run_status` pointer (from N6 truth)
  * if already READY: includes `run_facts_view` pointer (still by-ref)

This supports synchronous UX while SR execution is actually asynchronous.

---

### N1.J Observability Hook (to N8)

**Role:** Emit structured boundary telemetry:

* REQUEST_RECEIVED (kind + pins where known)
* REQUEST_REJECTED (reason)
* REQUEST_ROUTED (destination subnetwork)
* REQUEST_ACKED (run_id + status pointer)

This is essential because N1 is the only place you can reliably measure “how many runs are being asked for” vs “how many became READY”.

---

## What N1 explicitly does NOT do

* Does **not** decide required gates or outputs (N3 does).
* Does **not** bind run identity / lease (N2 does).
* Does **not** touch engine or evidence (N4/N5 do).
* Does **not** write SR truth artifacts (N6 does).
* Does **not** re-emit READY (N7 does).

---

If you want to keep going in the same order, the next node to illuminate is **N7 already done**, then we’d do **N8 (Observability/Governance)** last — unless you want to open **N1’s “RUN_QUERY routing”** more, since that’s the bridge to offline tooling.

---

Got it — **N8 (Observability / Governance Emitter)** is the SR subnetwork that makes the SR component *operationally legible* and *governable* across the environment ladder, without changing SR semantics. It does **not** drive outcomes; it **observes** and emits facts/telemetry that let humans and other governance systems explain what happened.

Below is the machinery inside N8.

---

## N8 internal subnetworks

### N8.A Correlation Context Injector

**Job:** ensure every SR-emitted telemetry/governance fact is joinable.

**Inputs:** boundary events from N1–N7.
**Outputs:** a standardized context attached to every event:

* `run_id`
* platform `scenario_id`
* `manifest_fingerprint`
* `parameter_hash`
* `seed` (when relevant)
* `attempt_id` (when relevant)
* `policy_rev` (always for anything after planning)
* trace context (`trace_id`, `span_id`) where applicable

**Hard rule:** if a module emits an event without the minimum pins, N8 rejects/flags it as malformed (internal quality gate). This prevents “observability that can’t join to truth”.

---

### N8.B Event Normalizer & Severity Classifier

**Job:** take heterogeneous internal events and normalize them into a stable SR event taxonomy.

**Outputs:** normalized `SRObsEvent` with:

* `event_kind` (from a fixed enum)
* `phase` (INGRESS / AUTHORITY / PLAN / ENGINE / EVIDENCE / COMMIT / REEMIT)
* `outcome` (OK / WAITING / FAIL / CONFLICT / SKIP / RETRY)
* `severity` (DEBUG/INFO/WARN/ERROR)
* `reason_code` (stable string codes)

**Designer lock-in:** N8 owns the enum list so it doesn’t drift across modules. Modules emit “raw” internal events; N8 normalizes.

---

### N8.C Metrics Synthesizer (Golden Signals)

**Job:** emit a minimal set of SR “golden signals” and component health indicators.

**Outputs include (minimum set):**

* `sr_run_requests_total{kind}`
* `sr_runs_accepted_total`
* `sr_runs_rejected_total{reason}`
* `sr_runs_ready_total`
* `sr_runs_failed_total{reason}`
* `sr_runs_quarantined_total`
* `sr_runs_waiting_total`
* `sr_engine_attempts_total{outcome}`
* `sr_engine_attempt_duration_ms` (histogram)
* `sr_evidence_wait_duration_ms` (histogram)
* `sr_ready_commit_latency_ms` (ingress → READY)
* `sr_ready_publish_failures_total`
* `sr_lease_lost_total`

**Hard rule:** metrics are derived from normalized events, not ad-hoc increments in modules (prevents double counting under retries).

---

### N8.D Trace/Span Builder (Causal Story)

**Job:** produce a coherent trace narrative from SR boundaries.

**Shape:**

* root span: `SR.Run` (run_id)
* child spans by phase:

  * `Ingress`
  * `RunAuthority`
  * `PlanCompile`
  * `EngineAttempt` (attempt_id)
  * `EvidenceVerify`
  * `CommitFacts`
  * `PublishReady`
  * `Reemit` (when applicable)

**Hard rule:** traces must never be used as truth; they must point to the truth surfaces (`sr/*` refs) when needed.

---

### N8.E Governance Fact Emitter (Outcome-affecting provenance)

**Job:** emit governance-relevant facts that make SR outcomes attributable.

This is **not “business traffic.”** It’s control/governance side information.

**Facts N8 must emit (minimum):**

1. **Policy stamp**: for each run, the `policy_rev` that governed it (policy id + revision + digest).
2. **Plan hash**: a stable identifier for the committed plan (so “same run_id, different plan” becomes detectable).
3. **Evidence hash**: for READY runs, the `facts_view_hash` / evidence bundle hash.
4. **Supersession edge facts** (from IP6): `run_new supersedes run_old` (purpose + reason_code).
5. **Backfill declarations** when SR participates in creating superseding runs as backfills (metadata only; the backfill job itself is elsewhere).

**Hard rule:** any time an outcome can be affected by configuration/policy, N8 must attach the policy rev used. This aligns with your platform governance posture.

---

### N8.F Privacy/Security Scrubber

**Job:** ensure SR telemetry never leaks secret material or sensitive payloads.

**Hard rules:**

* no secrets ever (only key IDs / secret references)
* no embedding of full payloads from engine outputs
* no PII/PCI content (SR shouldn’t see it anyway; if it does, it must not emit it)

This keeps observability safe by design, not by “remembering not to log things”.

---

### N8.G Sink Multiplexer (where events go)

**Job:** send the normalized telemetry/facts to the appropriate sinks.

Typical sinks:

* OTLP collector (traces/metrics/logs)
* governance/audit stream (control-plane facts)
* optional “SR ops table” (non-truth) for dashboards

**Environment ladder:** local can send to console + local OTLP; dev/prod send to central observability stack. The *semantics* of events remain identical.

---

### N8.H Delivery Reliability & Backpressure

**Job:** handle the reality that observability pipelines fail.

**Hard rules:**

* Observability must never block SR’s core truth commitments (N6). If sinks are down, SR still completes; N8 buffers/drops according to policy.
* Backpressure strategy is deterministic:

  * drop DEBUG first
  * keep WARN/ERROR
  * always keep governance facts (policy_rev, plan hash, evidence hash, supersedes)

This prevents “we couldn’t READY because metrics were down.”

---

## N8 event taxonomy (the minimum stable list)

These are the canonical normalized events N8 must produce (so we don’t drift later):

### Ingress / authority

* `RUN_REQUEST_RECEIVED`
* `RUN_REQUEST_REJECTED{reason}`
* `RUN_ACCEPTED`
* `DUPLICATE_REQUEST_OBSERVED`
* `EQUIV_KEY_COLLISION`
* `LEASE_ACQUIRED`
* `LEASE_BUSY`
* `LEASE_LOST`

### Planning

* `POLICY_RESOLVED{policy_rev}`
* `PLAN_COMMITTED{plan_hash}`
* `PLAN_DRIFT_DETECTED`

### Engine boundary

* `ENGINE_ATTEMPT_START{attempt_id, attempt_no}`
* `ENGINE_JOB_SUBMITTED{job_id}`
* `ENGINE_ATTEMPT_FINISH{outcome}`
* `ENGINE_LAUNCH_FAILED`
* `ENGINE_TIMEOUT`

### Evidence

* `EVIDENCE_CHECK_START{mode=reuse|post_attempt}`
* `EVIDENCE_COMPLETE{bundle_hash}`
* `EVIDENCE_WAITING{missing_set_hash}`
* `EVIDENCE_FAIL{reason}`
* `EVIDENCE_CONFLICT`

### Commit / publish

* `FACTS_VIEW_COMMITTED{facts_view_hash}`
* `READY_COMMITTED`
* `READY_PUBLISHED{publish_key}`
* `READY_PUBLISH_FAILED`

### Ops replay / supersede

* `REEMIT_REQUESTED`
* `REEMIT_PUBLISHED{reemit_key}`
* `REEMIT_FAILED`
* `RUN_SUPERSEDES{old_run_id,new_run_id,purpose}`

---

## N8’s non-negotiable relationship to SR truth

N8 must always be able to point from telemetry to truth:

* if it emits READY_PUBLISHED, it includes the `facts_view_ref`
* if it emits PLAN_COMMITTED, it includes `run_plan_ref`
* if it emits failures, it includes `run_record_ref`

**Rule:** “telemetry is never the source of truth; it is the index to truth.”

---

## Environment ladder angle (what changes, what cannot)

* **Cannot change:** event meanings, correlation pins, policy_rev stamping, and the fact that READY requires admissible evidence.
* **Can change:** sampling rates, sink endpoints, buffering policies, retention of logs, alert thresholds.

Local may feel lighter, but dev/prod must be able to reconstruct the same run story from the same event taxonomy.

---

