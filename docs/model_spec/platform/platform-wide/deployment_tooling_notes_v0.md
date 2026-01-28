# 1) Pin the environment ladder

The goal isn’t to invent “three different platforms.” It’s to make sure that **local, dev, and prod all run the same platform graph + rails**, and only differ in the *operational constraints* (scale, security posture, retention, reliability).

---

## What the environment ladder *is* for this platform

Your platform has already pinned a bunch of “laws” (ContextPins, canonical envelope, no-PASS-no-read, by-ref refs, watermarks, idempotency, audit, registry resolution, etc.). The environment ladder exists to answer:

* **What must never change across environments** (so there’s no “works locally, breaks in prod”).
* **What is allowed to change** (so local can be fast and prod can be safe).
* **How “promotion” works** (so you don’t rebuild the world each time with drift).

So the ladder is basically a **controlled change of operational envelope**, not a redesign.

---

## The three environments (as a production mental model)

### Local (laptop)

Local is for *design + iteration + deterministic reproduction*.

What it *means* in production terms:

* You can run the full graph on one machine (even if some pieces are disabled).
* You can generate and replay worlds quickly.
* You can break things safely and inspect everything.

Local defaults:

* Minimal security friction, but **the same trust boundary semantics still exist** (IG still admits/quarantines; you just run with permissive allowlists and dev credentials).
* Short retention, small volumes.
* “Debug observability” (easy logs, traces, and artifact inspection).

**The key rule:** local must still obey the rails. Otherwise you’ll build behaviors that can’t survive in dev/prod.

---

### Dev (shared integration)

Dev is for *end-to-end integration and realism*.

What it *means*:

* Multiple services/components run as they would in prod.
* You test upgrades, backfills, schema evolution, and cross-component joins.
* It’s the place where “one person’s laptop assumptions” get corrected.

Dev defaults:

* Security is “real enough” to catch issues (authn/authz, permissions, quarantine access, registry lifecycle privileges).
* Medium retention, representative volumes.
* Observability is closer to prod: stable dashboards, alerts (even if low thresholds).

**The key rule:** dev must catch the kinds of failures prod would catch (unauthorized producers, incompatible bundles, missing PASS evidence), not accidentally allow them.

---

### Prod (hardened runtime)

Prod is for *real outcomes + safety + governance*.

What it *means*:

* Strong isolation and access control.
* Strict change control (registry promotions, config changes, backfills).
* Guaranteed auditability and recoverability.

Prod defaults:

* Strong authn/authz everywhere it matters (IG, Actions, Registry, Label writes, quarantine access).
* Longer retention + archive continuity.
* SLOs and corridor checks (degrade triggers are meaningful, not just informational).

**The key rule:** prod never relies on “human memory.” Every change is a fact, every fact is attributable, every output is reproducible.

---

## What must be identical across local / dev / prod

These are the “no drift” invariants:

1. **Component graph + trust boundaries**

* IG is the front door for traffic; EB is the fact log; SR is readiness authority; Registry is deployable truth; AL executes actions; Label Store is label truth.

2. **Rails and join semantics**

* ContextPins discipline, canonical envelope, no-PASS-no-read, by-ref refs/locators, watermarks, idempotency, append-only + supersedes, degrade mask as hard constraint, deterministic registry resolution, as-of semantics.

3. **Meaning of “READY,” “ADMITTED,” “ACTIVE,” “LABEL AS-OF,” “BACKFILL”**

* The *words* must mean the same thing everywhere, even if local runs smaller.

4. **Reproducibility story**

* A run (or training build) that exists in dev/prod must be explainable the same way as local: pinned inputs + evidence + refs.

If any of these change across environments, you don’t have an environment ladder — you have three different platforms.

---

## What is allowed to differ across environments

This is where you get speed locally and safety in prod:

* **Scale**: data volume, throughput, concurrency.
* **Retention + archive**: how long EB retains, whether archive is enabled.
* **Security strictness**: allowlists, permission boundaries, approval gates (but the *mechanism* exists in all envs).
* **Reliability posture**: HA, backups, incident tooling.
* **Observability depth**: local = inspect-by-hand; prod = SLOs + alerts + governance dashboards.
* **Cost knobs**: how much you’re willing to spend.

These differences must not change the semantics of events, pins, gates, or provenance.

---

## The “promotion” idea (local → dev → prod)

Promotion in your world shouldn’t be “rewrite it for prod.” It should be:

* same binaries/code,
* same contracts/rails,
* different environment profile (endpoints/credentials/retention thresholds),
* plus stronger policy configs (security + corridor checks).

That’s the ladder.

---

## Environment Ladder Pin

**Local, dev, and prod run the same platform graph and the same rails/join semantics; environments differ only in operational envelope (scale, retention/archive, security strictness, reliability, observability), and promotion is a change of configuration/policy posture—not a change of platform meaning.**

---

# 2) Pin the deployment units

Yep — let’s pin **deployment units** in the same “production-truth” way.

The key idea: a *deployment unit* is not “a component.” It’s the **runtime shape** a component takes in production: *always-on service*, *background projector/worker*, *on-demand job*, or *human-facing app/API*. Local/dev/prod can **collapse** units for convenience, but the **unit roles** stay the same.

---

## Deployment unit taxonomy (what types exist in this platform)

### 1) Always-on services

These are continuously running because they sit on the hot path or serve queries.

They have:

* stable network endpoints (API/gRPC/HTTP)
* health/readiness semantics
* ability to scale horizontally (even if you don’t do it yet)

### 2) Always-on stream consumers (“projectors”)

These are long-running workers that **consume EB** and maintain derived state (projections, materialized views, indexes). They usually also checkpoint offsets.

They may or may not expose an API (sometimes paired with a query API).

### 3) On-demand / scheduled jobs

These are **invoked** by SR/Run-Operate: engine runs, offline rebuilds, training runs, backfills.

They have:

* pinned inputs
* deterministic outputs
* a run record / receipt story
* explicit “start/finish/fail” lifecycle

### 4) Human-facing apps (UI + backend)

Case workbench, admin surfaces. These are not the hot path but they can trigger outcomes (manual actions, label writes) — so they still must obey Actions/Label Store rules.

---

## Now pin your platform’s deployment units (v0 production shape)

### Hot path always-on units (data plane)

These run continuously in dev/prod (local can collapse them):

1. **Ingestion Gate service (IG)**
   Always-on. The trust boundary. Takes producer traffic, emits receipts, appends admitted facts to EB.

2. **Decision Fabric service (DF)**
   Always-on. Consumes events (or synchronous requests if you have a Decision API), calls OFP/IEG/DL/Registry, emits decisions + action intents.

3. **Actions Layer service (AL)**
   Always-on. The *only* executor. Consumes ActionIntents, performs side effects, emits ActionOutcomes.

4. **Decision Log/Audit writer (DLA)**
   Always-on consumer/writer. Builds the append-only flight recorder from DF/AL/IG evidence.

5. **Degrade Ladder evaluator (DL)**
   Always-on (or periodic) control-plane-ish unit. Continuously computes the degrade posture that constrains DF.

### Hot path state builders (projectors) + query surfaces

These are long-running consumers that maintain state:

6. **Identity & Entity Graph projector (IEG)**
   Always-on consumer. Consumes EB, maintains graph projection + `graph_version` based on applied offsets.
   (Optionally paired with a query API, but the unit “IEG projector” is the non-negotiable.)

7. **Online Feature Plane projector + serve API (OFP)**
   Always-on consumer + serve surface. Maintains feature state from EB; serves feature snapshots with `input_basis` + snapshot hash.
   (You can implement as one process that both consumes and serves; that’s still one deployment unit.)

### Control plane always-on units

These are low-QPS but authoritative:

8. **Model/Policy Registry service (MPR)**
   Always-on. Serves bundle resolution; accepts governed lifecycle changes; emits registry events.

9. **Label Store service**
   Always-on. Append-only label timelines; as-of query surface.

10. **Case Workbench backend + UI**
    Always-on human interface. Reads audit/evidence, writes labels (via Label Store), requests manual actions (via AL).

### On-demand/scheduled job units (batch plane)

These are invoked explicitly (SR/Run-Operate):

11. **Scenario Runner execution**
    Runs as:

* local: CLI/job runner
* dev/prod: control-plane “run launcher” + worker execution (can still be a single service that spawns jobs)
  Its job is: engine invocation/reuse + gate verification + publish join surface + run ledger.

12. **Data Engine run job**
    Invoked by SR. Not always-on. Produces sealed world artifacts + PASS evidence (no bus writes).

13. **World Stream Producer (WSP)**
    Triggered by SR READY. Streams sealed `business_traffic` into IG (push). Persists checkpoints (DB or object store).

14. **Offline Feature Plane Shadow job**
    Scheduled/on-demand. Rebuilds datasets/snapshots deterministically from EB/archive + labels.

15. **Model Factory training/eval job**
    Scheduled/on-demand. Consumes DatasetManifests, produces bundles + evidence + PASS posture.

16. **Backfill/replay jobs (Run/Operate)**
    Explicitly invoked. Rebuild projections/datasets and emits governance facts (never silent).

### Infrastructure units (not “your code” but required deployment units)

17. **Event Bus** (EB)
    Durable append + replay.
18. **Artifact/object store**
    Holds by-ref artifacts: engine outputs, receipts, ledgers, manifests, bundles, quarantine evidence.
19. **Operational databases**
    At minimum: registry DB, labels DB, case DB; possibly audit index DB (even if audit raw is in object store).

(Locally you can run these as dev services; in prod they’re managed/clustered; semantics stay the same.)

---

## The deployment-unit pin (designer-authoritative)

**In production shape, the hot path is a set of always-on services (IG, DF, AL, DLA, DL) plus always-on EB consumers that maintain state (IEG, OFP); control-plane services (Registry, Label Store, Case backend) serve authoritative truths; and batch jobs (SR, Engine runs, WSP streaming, Offline Shadow, Model Factory, Backfills) are invoked explicitly with pinned inputs and auditable outputs. Local/dev/prod may collapse units for convenience, but these unit roles and authority boundaries do not change.**

# 3) Pin the stateful substrate map

Yep — the **stateful substrate map** is basically: *what durable stores exist, what “truth” lives in each, who is the authoritative writer, and what can be rebuilt vs must never be lost.*

Here’s the production-truth view for your platform.

---

## The substrate types

### 1) Durable fact log

**Event Bus (EB)** (+ optional **Archive** as its long-horizon extension) is the **replayable record of admitted events**. EB is where “what happened” lives.

**Authoritative writer:** Ingestion Gate (IG) is the one that makes events admissible and appends them (directly or as the acknowledged admission step).
**Everyone else:** reads and derives state; producers don’t “write truth,” they submit candidates to IG.

---

### 2) Artifact / object store

This is your **by-ref substrate**: immutable objects + manifests + receipts + evidence pointers. It holds “pinned things” that shouldn’t be represented as DB rows.

**Truth rule:** the object store doesn’t own meaning by itself — the **writer component** is the authority for each artifact family (engine outputs, run ledgers, audit records, manifests, bundles, quarantine evidence).

---

### 3) Operational databases (authoritative vs rebuildable)

You’ll have DBs for things that need fast query, mutation rules, access control, and strong identity constraints. Some are **authoritative truths**, others are **derived projections** that can be rebuilt from EB + artifacts.

---

## The map: who writes what, and where it lives

### A) Primary, non-negotiable truths (must persist)

These are the minimum “platform memory” that makes everything reproducible.

1. **EB / Archive — admitted event history**

* **Writer:** IG
* **Readers:** IEG, OFP, DF, AL, DLA, Case, Offline Shadow, etc.
* **Why it’s primary:** it’s the replay spine + watermark basis.

2. **Engine outputs + engine gate receipts — world truth artifacts** *(object store)*

* **Writer:** Data Engine
* **Used by:** SR (to form READY), learning/eval (as refs), audit (as evidence).

3. **SR run ledger + join surface (`run_ready_signal`, `run_facts_view`)** *(object store, optional index DB)*

* **Writer:** Scenario Runner
* **Used by:** downstream to start runs (no scanning). 

4. **Label timelines** *(authoritative DB)*

* **Writer:** Label Store
* **Used by:** Offline Shadow + Model Factory via as-of.

5. **Registry bundles + registry lifecycle events** *(authoritative DB + bundle blobs in object store)*

* **Writer:** Registry for lifecycle truth; Model Factory publishes bundles/evidence into it
* **Used by:** DF (deterministic active bundle resolution).

6. **Decision audit record set (flight recorder)** *(object store + optional index DB/search)*

* **Writer:** Decision Log/Audit
* **Used by:** Case workbench, governance, offline analysis.

7. **Quarantine evidence** *(object store + minimal receipt/index)*

* **Writer:** IG (quarantine), sometimes DLA (audit quarantine)
* **Used by:** operators/workflows to inspect/reprocess.

Those 7 are your “can’t lose these without losing the platform story” set.

---

### B) Derived/rebuildable state (can be rebuilt from facts)

These stores are **stateful**, but not “primary truth.” They must be durable for performance, but they can be reconstructed if corrupted.

1. **Identity & Entity Graph store** *(DB/graph/kv — rebuildable)*

* **Writer:** IEG projector
* **Source:** EB admitted events
* **Proof token:** `graph_version` derived from applied watermarks.

2. **Online Feature Plane state store** *(feature store — rebuildable)*

* **Writer:** OFP projector
* **Source:** EB (and optionally IEG queries)
* **Proof token:** `input_basis` watermark vector + `feature_snapshot_hash` for served snapshots.

3. **Degrade evaluation state** *(small DB/kv — rebuildable)*

* **Writer:** DL evaluator
* **Source:** observability signals / health inputs
* **Reason:** safety control surface; can be recomputed. 

4. **Indexes/views** *(optional)*

* audit indexes, search indexes, “receipt lookup” tables, etc.
* These exist for usability/latency, not truth ownership.

---

## The stateful DB shortlist (minimal, production-shaped)

If you keep it minimal, the authoritative DBs you’ll end up with are:

* **Label Store DB** (authoritative)
* **Registry DB** (authoritative lifecycle + resolution)
* **Case DB** (authoritative case timeline)
* **Actions DB** (authoritative idempotency + outcome history) 
* *(Optional)* **Audit index DB** (index only; raw audit truth can live in object store) 

Everything else can be “derived store” backed by EB replay.

---

## Stateful substrate pin

**The platform’s primary truths are: EB/Archive (admitted events), object-store artifacts (engine outputs, SR join surface, audit records, manifests/bundles, quarantine evidence), and authoritative DB timelines (labels, registry lifecycle, cases, actions). All other state stores (IEG/OFP projections, indexes, degrade state) are derived and rebuildable from those primary truths using the pinned rails (watermarks, hashes, as-of, PASS gating).**

---

# 4) Pin config/secrets + change control posture

This is where a lot of “works locally / breaks in prod” comes from, so we pin the production truth now: **configs are part of provenance; secrets are not; and outcome-affecting changes are always auditable facts.**

---

## What “config” means in *this* platform

In your platform, config isn’t just “tuning knobs.” Config can directly affect:

* what events are admitted (IG allowlists, schema acceptance policy),
* what actions are allowed (AL allowlists),
* what bundles are eligible (registry rules/compat),
* what constitutes readiness (SR required gates),
* what constitutes “safe operation” (degrade thresholds, corridor checks),
* retention/backfill rules (history semantics in practice).

So config is part of **governed behavior**, not “dev convenience.”

---

## Production truths to pin

### 1) Separate **policy config** from **runtime wiring config**

**Policy config (outcome-affecting)** = must be versioned + auditable
Examples: IG admission allowlists, schema acceptance rules, AL action allowlists, registry lifecycle rules, degrade thresholds, required PASS gates.

**Wiring config (non-semantic)** = endpoints, ports, resource limits
Examples: DB URLs, broker addresses, timeouts, scaling, memory, threads.

**Pin:** policy config changes must show up in audit/governance; wiring config can change without claiming it changed decision semantics (but still should be logged for ops).

---

### 2) Policy config is a **versioned artifact**, not “environment state”

**Pin:** Every policy config has:

* a stable identity (e.g., `policy_id`),
* a content digest (or equivalent),
* and a monotonic revision/tag.

Receipts and provenance records cite the **policy revision** used:

* IG receipts cite admission policy rev,
* AL outcomes cite action policy rev,
* registry events cite approval policy rev,
* SR readiness cites required gate policy rev,
* DL decisions cite threshold profile rev.

This makes the system explainable: “this happened under policy rev X.”

---

### 3) Secrets are never embedded in artifacts, and never used as provenance

Secrets (keys, passwords, tokens) must not appear in:

* run ledgers,
* receipts,
* bundles,
* manifests,
* audit records.

**Pin:** secrets are injected at runtime (env vars / secret store), and provenance references only **secret identity** if necessary (e.g., “key_id”), never secret material.

---

### 4) Environment ladder uses **profiles**, not code forks

Local/dev/prod are different **profiles**:

* a wiring profile (endpoints, scale)
* a policy profile (strictness knobs + allowlists + thresholds)

**Pin:** components do not contain “if prod do X else do Y” semantics. They load the profile and behave deterministically from it.

---

### 5) Change control: any outcome-affecting change emits a governance fact

This is the heart of it.

**Pin:** these changes must produce an auditable event/record:

* IG admission policy changes
* schema acceptance policy changes
* action allowlist changes
* registry promotions/rollbacks/retirements
* feature definition version changes
* degrade corridor/threshold changes
* retention/backfill execution
* access/control policy changes

This ties directly to your Obs/Gov + Run/Operate plane relationship: “changes are facts.”

---

### 6) Promotion gates: changes are “proposed → approved → active”

You don’t need bureaucracy, just a clear lifecycle.

**Pin:** policy/config changes have:

* a proposed artifact (new revision),
* an approval step (human or controlled automation),
* an activation step (becomes the profile used by components),
* a rollback path (previous revision remains available).

This mirrors what you already do for model/policy bundles in the registry; config changes follow the same governance shape.

---

## Config/secrets + change control pin

**Outcome-affecting policy configs are versioned artifacts whose revision is recorded in receipts/provenance; secrets are injected at runtime and never embedded in artifacts; local/dev/prod differ only by profiles (wiring + policy strictness), and any change that can affect outcomes or reproducibility is emitted as an auditable governance fact with a clear propose→approve→activate→rollback lifecycle.**

---

# 5) Pin observability baseline (minimum viable)

The right way to think about “minimum viable” for *your* platform is: observability must answer **three questions** reliably, across local/dev/prod:

1. **What happened, and why?** (decision/action explainability)
2. **Are we healthy enough to act?** (degrade + operations safety)
3. **What changed?** (governed change control)

If the baseline can’t answer those three, it’s not viable.

---

## 1) Correlation baseline (the one thing that makes everything joinable)

This is the core: *without correlation keys, the platform can’t explain itself.*

### Correlation keys you already have “in the world”

Your canonical envelope already supports the primary correlation fields:

* `event_id`, `event_type`, `ts_utc`, `manifest_fingerprint` (required)
* optional pins `parameter_hash`, `seed`, `scenario_id`, `run_id`
* tracing: `trace_id`, `span_id`
* `schema_version`, `producer`, `parent_event_id` 

### The baseline correlation rule (production truth)

Every component must emit telemetry (logs/metrics/traces/events) that includes the **applicable subset** of these IDs:

* **World/run scope:** `run_id`, `scenario_id`, `manifest_fingerprint`, `parameter_hash` (and `seed` when seed-variant)
* **Event scope:** `event_id`, `event_type`, `schema_version`, `ts_utc`
* **Decision/action scope:** `decision_id`, `action_intent_id`/`idempotency_key`, `action_outcome_id`
* **Serving provenance:** `feature_snapshot_hash`, `graph_version`, `input_basis` (or checkpoint token)
* **Learning/deploy provenance:** `train_run_id`, `dataset_manifest_id`, `bundle_id`
* **Component identity:** `component_name`, `component_version`, `env`

This is what makes your “audit join view” possible without magic.

---

## 2) Logs baseline (what must be logged vs what must never be logged)

Logs are for **human debugging** and incident reconstruction. In your platform, logs must be:

* **Structured** (not free-text only)
* **By-ref friendly** (log IDs and refs, not raw payload dumps)
* **Safe** (no secrets; no “accidental sensitive payload copies”)

### What must always be logged (minimum)

Only the boundary decisions that define truth:

* **IG:** admit/quarantine/duplicate decision + reason codes + producer identity + policy rev + pointer to where the admitted event lives (EB coords) or where quarantine evidence lives.
* **SR:** READY declaration + which PASS evidence and output refs justified it.
* **DF:** decision produced + key provenance pointers (bundle ref, snapshot hash, graph_version, degrade mode).
* **AL:** executed/denied/failed outcome + idempotency key + actor identity. 
* **Registry:** publish/promote/rollback events + actor + before/after refs. 
* **Label Store:** label assertion appended (not overwritten) + effective vs observed time + actor/provenance. 

### What must never be logged

* secrets (ever)
* raw credential material
* raw payload bodies *by default* (your by-ref posture means the log should point to evidence refs instead)

This matches your existing Obs/Gov concept posture: “telemetry standards + correlation + golden signals” without forcing a specific tool.

---

## 3) Metrics baseline (golden signals + a few platform-specific ones)

Metrics are for **automation**: alerting, degrade inputs, SLOs.

### Universal golden signals for every always-on unit

Every service/consumer emits at least:

* **Throughput** (requests/events processed per time)
* **Latency** (p95 is enough to start)
* **Error rate** (by class, not one bucket)
* **Saturation** (queue depth / worker backlog / CPU/heap as applicable)

### Platform-specific minimum metrics that matter (because of your rails)

These are the ones that directly tie to platform safety:

* **IG:** admit/quarantine/duplicate rates, schema validation failures, auth failures, “append latency to EB”
* **EB consumers (IEG/OFP/DLA):** **consumer lag** per partition + “watermark age” (how far behind in time the applied offsets are)
* **OFP:** feature snapshot latency, **staleness rate**, missing-feature rate, snapshot-hash compute failures
* **DF:** decision latency, fallback-rate (safe mode decisions), registry-resolution failures, “blocked by degrade mask” rate
* **AL:** outcome counts by status, retry rate, external dependency latency (if any), denied-by-policy rate
* **Registry:** resolve latency, lifecycle mutation counts, incompatibility rejects
* **Label Store:** write rate, as-of query latency, late-label arrival rate

These are exactly the kind of signals your Degrade Ladder concept expects to consume.

---

## 4) Traces baseline (end-to-end causality)

Traces are for: “show me the chain from event → decision → action → audit.”

### Minimum viable tracing posture

* If an event has `trace_id/span_id`, the platform **preserves it** through IG → EB and into downstream processing. 
* Each major hop creates a span:

  * IG admission span
  * DF decision span (with child spans for OFP/IEG/Registry calls)
  * AL execution span
  * DLA write span
* Sampling differs by environment (local can be high; prod can be sampled), but the **propagation semantics** are identical.

---

## 5) Governance/audit “facts” baseline

This is the piece most platforms forget: **changes must be observable facts**, not just logs.

Minimum viable here means:

* a durable record that says “policy rev X became active,” “bundle Y promoted,” “backfill Z executed,” “retention changed,” etc.
* and those facts carry `actor`, `scope`, `before/after refs`, and `reason`

This aligns with your Obs/Gov concept: “no silent changes,” “change control & version governance,” “audit joinability.”

---

## Observability baseline pin

**Minimum viable observability means: universal correlation keys are carried everywhere (run/event/decision/action/bundle), boundary decisions are logged as structured facts, golden-signal metrics + lag/watermark metrics exist for every consumer/service, trace context propagates end-to-end, and all outcome-affecting changes emit durable governance facts—so we can always answer what happened/why, whether we’re safe to act, and what changed.**

---

# 6) Pin CI/CD + promotion story (no cloud needed yet)

The purpose here is to prevent two kinds of drift:

* **code drift** (“what’s running isn’t what we tested”)
* **artifact drift** (“what we trained/evaluated/approved isn’t what we deployed”)

So CI/CD must move **code + pinned artifacts + policy profiles** together, with evidence.

---

## What we’re pinning (conceptually)

There are three distinct “promotion lanes” in your platform:

1. **Code promotion** (services/jobs)
2. **Policy/config promotion** (profiles, allowlists, thresholds)
3. **Model/policy bundle promotion** (Registry lifecycle)

They interlock, but they are not the same thing.

---

## CI/CD lane 1: Code promotion (services + jobs)

### Production truths to pin

**CICD-1. Build artifacts are immutable and identifiable.**
Every build produces an immutable artifact with a version identity (commit SHA + build id). Local/dev/prod run *the same build artifact*; you don’t “rebuild for prod.”

**CICD-2. Tests are layered in the same platform semantics.**
Minimum pipeline layers:

* **Unit tests** (fast, local + CI)
* **Contract checks** (schemas/contracts compile/validate)
* **Integration tests** (spin up the local “prod-shaped” stack and run a small end-to-end flow: SR→Engine→IG/EB→IEG/OFP→DF→AL→DLA; plus label + offline shadow + registry resolution at least once)

No cloud required: integration can be Docker Compose locally/CI.

**CICD-3. Promotion is environment-profile selection, not code branching.**
Same binary; different profile. “Prod behavior” must be explainable as “code X + profile Y,” not “prod fork.”

---

## CI/CD lane 2: Policy/config promotion (profiles)

### Production truths to pin

**CICD-4. Policy configs are versioned artifacts with approval.**
Admission allowlists, schema acceptance rules, action allowlists, corridor thresholds, required gates—these are promoted like code:

* propose new revision
* validate in CI (lint/validate)
* activate in dev
* then activate in prod with an auditable governance fact

**CICD-5. Runtime components always report which policy rev they are using.**
This is the key: logs/receipts/provenance can cite `policy_rev`, and operators can answer “what rules were in force?” immediately.

---

## CI/CD lane 3: Model/policy bundle promotion (Registry)

### Production truths to pin

**CICD-6. Model Factory publishes bundles; Registry governs activation.**
A training run produces:

* bundle artifacts + digests
* evaluation evidence
* dataset manifests
  Registry activation is a separate governed step (approve/promote/rollback).

**CICD-7. DF resolves deterministically and records the bundle ref used.**
So “what changed?” in decisioning is always answerable: a registry event changed ACTIVE, and decisions cite bundle ref.

---

## The promotion story across environments (local → dev → prod)

### Local

* iterate quickly
* run unit + small integration flows
* produce pinned run records / receipts for reproducibility checks

### Dev

* validate end-to-end with multiple services running
* validate schema evolution policy + registry compatibility + degrade behaviors
* validate upgrades/backfills in a controlled way

### Prod

* promote only immutable artifacts (code, config revisions, bundles)
* every promotion emits governance facts
* rollback paths exist for each lane (code rollback, config rollback, bundle rollback)

---

## CI/CD + promotion pin

**CI/CD promotes three immutable things: code artifacts, policy/profile revisions, and model/policy bundles. Code promotion is build-once/run-anywhere with unit→contract→integration gates; policy configs are versioned artifacts activated via governed change; bundles are published by Model Factory and activated only via Registry lifecycle. Across local/dev/prod, promotion is selecting approved artifacts/profiles—not forking semantics—and every promotion/rollback emits auditable governance facts.**

---

# 7) Pin retention/archive/backfill operations (production reality)

This is where your earlier *history/backfill semantics* get turned into *operational knobs* that Run/Operate can actually execute without breaking determinism.

Key point: we’re not choosing vendors/storage yet. We’re pinning **what must be true operationally**.

---

## Retention (EB) — what it means in production

### RTA-1. Retention is an environment profile knob, not a semantic change

* Local: short retention (hours/days) for speed
* Dev: medium retention (days/weeks) for integration realism
* Prod: policy-driven retention (weeks/months) plus archive for longer horizons

**Pin:** retention length may differ; the semantics of offsets, watermarks, and replay **do not**.

---

## Archive — what it means in production

### RTA-2. Archive is the long-horizon extension of admitted facts

Archive exists to support:

* offline rebuilds beyond EB retention,
* investigations that need old history,
* reproducible model training windows.

**Pin:** archive stores the admitted event stream as canonical envelopes, preserving event identity and allowing deterministic replay basis declarations.

### RTA-3. Archive addressing is by-ref and pinned

Consumers never “search archive vaguely.” They read by:

* run/world pins,
* stream identity,
* time window / offset range,
* and manifest/digest pointers.

This keeps it aligned with your by-ref posture.

---

## Backfill operations — what is allowed to happen

Backfill is not “we ran it again.” It is a **declared operation** with scope and outputs.

### RTA-4. Backfill is explicit, scoped, and auditable

A backfill must declare:

* **scope**: which stream(s), partitions, and offset/time windows
* **purpose**: why (schema change? bug fix? new feature definition? late data?)
* **basis**: the replay basis used (offset ranges/checkpoints)
* **outputs**: what derived stores/artifacts are being regenerated

**Pin:** backfill emits a durable governance fact and produces new derived artifacts; it never silently overwrites primary truth.

### RTA-5. What can be backfilled vs what cannot

* **Can be backfilled (derived):** IEG projections, OFP state, offline datasets/manifests, audit indexes, analytics views.
* **Cannot be backfilled as “truth mutation”:** EB admitted events (primary facts), label store timelines (truth evolves append-only), registry lifecycle history, SR run ledgers (append-only with supersedes), engine outputs for a pinned identity (immutable; corrections create new identity/version).

This pin prevents “time travel” corruption.

### RTA-6. Backfill does not break monotonic progress tokens

Consumers’ “applied offsets” semantics remain monotonic. Backfills create new derived versions or rebuild a store from scratch, but they don’t redefine what an offset meant in the original stream.

---

## Operational workflows (how these knobs are used)

### RTA-7. Retention change is a governed change

Changing EB retention or archive policy is outcome-affecting (it changes what can be replayed).
**Pin:** retention policy changes emit governance facts.

### RTA-8. Archive hydration is continuous or scheduled, but always verifiable

Whether archive is “always on” or a scheduled export, it must be possible to verify completeness for a declared window (so Offline Shadow can trust it).

### RTA-9. Backfill execution uses the same Run/Operate lifecycle as other jobs

A backfill run gets:

* a run id (or backfill id),
* pinned inputs (basis + policy revs),
* outputs (artifact refs),
* and a completion receipt.

This keeps it consistent with the rest of the platform’s run truth story.

---

## Retention/archive/backfill pin

**Retention windows differ by environment profile but replay semantics and watermark meaning do not; archive is the long-horizon extension of admitted canonical events and is accessed by pinned by-ref bases; backfills are explicit, scoped, and auditable operations that regenerate only derived state/artifacts (never primary truths), preserve monotonic progress tokens, and run under Run/Operate lifecycle with governance facts for retention changes and backfill executions.**

---

# 8) Choose a reference “production-shaped local stack”

([Past chat][1])([Past chat][1])([Past chat][2])([Past chat][1])

Yep — this is exactly the right moment to pick a **reference “production-shaped local stack”** because it becomes the *runtime ground* your component specs can assume (without becoming cloud-specific).

The design goal is simple:

**Local stack should look like prod at the protocol/semantics level**, not at the “managed service brand” level.

That means:

* **Kafka-ish** semantics for EB (partitions, offsets, at-least-once, consumer groups)
* **S3-ish** semantics for by-ref artifacts (object immutability posture, content digests, bucket/key addressing)
* **SQL DB** semantics for authoritative timelines (labels/registry/cases/actions)
* **OTel-ish** semantics for traces/logs/metrics (so your observability baseline is real, not pretend)

If local matches those **interfaces**, dev/prod can swap implementations later without changing platform meaning.

---

## The reference stack I’d use (one recommended path)

### 1) Packaging / orchestration: Docker + Compose

Reason: it gives you “prod-shaped networking + independent services + stateful dependencies” on a laptop with one command, and it’s what most projects use for local integration environments.

---

## 2) Event Bus: Redpanda (Kafka API compatible)

**Why this fits your platform:**

* You’ve pinned EB semantics around **partitions + offsets + replay + at-least-once**. A Kafka API bus is the cleanest match.
* Redpanda is explicitly Kafka-compatible and designed for simpler ops (single binary, no ZooKeeper/JVM complexity), which is great for laptop-first iteration. ([redpanda.com][3])
* Redpanda also publishes a **single-broker Docker Compose quickstart** (plus Console) which maps perfectly to “production-shaped local.” ([Redpanda Documentation][4])

**What this enables in your platform specs:**

* IG/EB join (J3–J5) can assume **Kafka-style offsets** as the watermark basis.
* IEG/OFP determinism (J6–J8) can be grounded in real consumer group behavior + offset checkpoints.

**Nice bonus:** Redpanda Console gives you a developer UI to inspect topics, consumer groups, lag, etc. ([GitHub][5])

---

## 3) Artifact/Object store: MinIO (S3-compatible)

**Why this fits your platform:**

* Your platform is by-ref: engine outputs, run ledgers/join surfaces, audit records, dataset manifests, bundles, quarantine evidence are all best modeled as **immutable-ish objects** referenced by locators/refs.
* MinIO is explicitly **S3-compatible object storage**, widely used for local S3 parity. ([GitHub][6])

**What this enables in your specs:**

* You can keep artifact addressing in an S3-like form from day one.
* You can model “digest + locator” integrity checks realistically (download object → verify digest).

---

## 4) Authoritative databases: Postgres

This is the boring-but-correct choice for the authoritative truth timelines:

* Label Store (append-only timeline + as-of queries)
* Registry (lifecycle + deterministic resolution)
* Cases (timeline + assignments)
* Actions (idempotency + outcomes)
* (Optional) audit indexes/search tables

Postgres is stable, local-friendly, and maps cleanly to dev/prod.

---

## 5) Observability: OpenTelemetry Collector + Grafana stack

Because you already pinned observability as a **platform law**, local should actually run it.

Minimum “production-shaped” setup:

* **OpenTelemetry Collector** as your single intake point (apps emit OTLP)
* **Prometheus** for metrics
* **Tempo** for traces
* **Loki** for logs
* **Grafana** as the UI

Grafana’s docs support running Tempo via Docker Compose and wiring OTel Collector pipelines, and Loki supports ingesting OTel logs via the collector. ([Grafana Labs][7])

This directly supports your Degrade Ladder + corridor-check story (lag, error rates, etc.) without hand-waving.

---

# What “production-shaped local” looks like in practice for *your* platform

## A) One “infra compose” that boots the substrate

**Always-on containers:**

* redpanda (EB)
* redpanda-console (optional but very useful)
* minio (artifact store)
* postgres (authoritative DBs)
* otel-collector + grafana + prometheus + tempo + loki (observability)

This is your “local cloud.”

## B) Your platform runs as separate processes/containers

You can run your services in the host (fast iteration) *or* as containers (prod-shaped). Either way, they point at the same substrate endpoints.

**Always-on services (hot path):**

* IG, DF, AL, DLA, DL
* IEG projector, OFP projector+serve

**Jobs:**

* SR run launcher
* Engine run job
* Offline Shadow job
* Model Factory job

The “production-shaped” part isn’t whether they’re containers—it’s that they behave like independent deployment units with real networking and real durable dependencies.

---

# How this guides component specs (without tool-lock-in)

If we choose this reference stack, your component specs can safely assume:

### Event Bus assumptions

* Kafka-style partitions + offsets + consumer groups
* at-least-once delivery is real
* consumer lag/watermarks are real and observable

### Artifact store assumptions

* S3-style buckets/keys
* object versioning can be simulated (even if you don’t use it)
* refs + digests are verifiable

### DB assumptions

* transactional writes for authoritative timelines
* schema migrations exist
* predictable query semantics

### Observability assumptions

* OTLP everywhere
* traces/metrics/logs exist locally and match prod semantics

None of this forces AWS/GCP/Azure choices later. It just forces **interface discipline**.

---

# Local → dev → prod mapping (so you’re not painting yourself into a corner)

* **Local:** single Redpanda broker + MinIO + Postgres + lightweight OTel stack
* **Dev:** same stack, possibly **3-broker** Redpanda and stricter auth policies
* **Prod:** managed equivalents (Kafka-compatible bus, S3-compatible object store, Postgres, OTel pipeline) with stronger security + HA

The platform doesn’t change—only the operational envelope does (which matches your environment ladder pin).

---

# What Codex needs from you (to implement smoothly)

Codex doesn’t need you to pick a cloud vendor now. It needs:

1. a **single “bring up local infra” command** (Compose)
2. a **local profile** (`.env.local` / config profile) with endpoints and policy revs
3. an **integration script** that runs one full golden flow end-to-end (SR→Engine→WSP→IG/EB→IEG/OFP→DF→AL→DLA + label + offline + registry resolve)

That’s enough for it to implement and test against a real substrate from day one.

---

If you want, the next step in this same brainstorm mode is: we take the stack above and do a **direct mapping table**:

**component → (reads/writes) → which substrate (EB topics / S3 buckets / DB schemas) → what it must persist**

That mapping becomes the practical bridge between “platform picture” and “things that run locally.”

---

Yep — here’s the **direct mapping** from *component → reads/writes → substrates (EB topics / object store prefixes / DB schemas) → what must persist*, using a **reference production-shaped local stack** (Redpanda/Kafka + MinIO/S3 + Postgres).

I’ll also pin a **minimal substrate naming layout** first so the table has something concrete to point at.

---

## Reference substrate layout (local stack)

### Event Bus (Redpanda) topics (reference names)

* **`fp.bus.traffic.v1`**
  Canonical *business_traffic* events that drive the hot path (WSP‑streamed engine traffic, external transactions, decision/action events that need to be replayed).
* **`fp.bus.control.v1`**
  Low-volume control facts (run ready signals, governance facts, registry lifecycle events, backfill declarations, config activations).
* **`fp.bus.audit.v1`** *(optional but useful)*
  Audit/receipt pointer events (e.g., “audit record written at ref X”, “ingestion receipt written at ref Y”) without embedding payloads.

> Partitioning note (fits your rails): IG stamps a deterministic `partition_key` for any event it admits. EB itself just enforces partition+offset semantics.

### Object store (MinIO) bucket + prefixes (reference)

Single bucket: **`fraud-platform`**, with prefixes:

* `engine/` (engine outputs, gate receipts)
* `sr/` (run_plan/run_record/run_status/run_facts_view, READY signals)
* `wsp/` (world stream checkpoints; operational state only)
* `ig/quarantine/` (quarantine evidence blobs)
* `ig/receipts/` (ingestion receipts, if you store them as objects)
* `dla/audit/` (audit decision records + evidence pointers)
* `ofs/` (offline shadow materializations + dataset manifests)
* `mf/` (training run outputs + eval evidence)
* `registry/bundles/` (bundle artifacts)
* `gov/` (governance facts, backfill declarations, config activations)
* `profiles/` (versioned environment profiles + policy rev artifacts)

### Postgres schemas (reference)

Authoritative (truth):

* `label_store` (append-only label timelines)
* `registry` (bundle lifecycle + active resolution state)
* `case_mgmt` (case objects + timelines)
* `actions` (idempotency + outcome history)

Operational / indexes (optional but practical):

* `ig` (receipt index, quarantine index)
* `sr` (run index/status index)
* `audit_index` (search/index for audit records)
* `gov` (governance event index)

Derived (rebuildable):

* `ieg` (entity graph projection store)
* `ofp` (feature state store)
* `dl` (current degrade posture state)

---

## Component → substrate mapping table (reference)

| Component (deployment unit)               | Reads                                                                                                                                                          | Writes                                                                                                                                                                      | Must persist (truth)                                                                                                                |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Data Engine (job)**                     | `profiles/` (engine params/config), reference artifacts                                                                                                        | **Object:** `engine/…` outputs + **gate receipts** (no bus writes)                                                                                                           | Engine outputs (immutable per identity) + gate PASS evidence (`engine/`)                                                            |
| **World Stream Producer (job/service)**   | **Bus:** `fp.bus.control.v1` READY; **Object:** `sr/run_facts_view`, `engine/…` locators/evidence                                                               | **Push:** canonical envelopes → IG; **Object/DB:** `wsp/checkpoints/…` (operational resume state)                                                                            | Checkpoints (operational); truth remains IG receipts + EB                                                                           |
| **Scenario Runner (job/service)**         | **Object:** `engine/…` locators/receipts; **DB:** optional `sr`; config profile                                                                                | **Object:** `sr/run_plan`, `sr/run_record`, `sr/run_status`, `sr/run_facts_view`; **Bus:** `fp.bus.control.v1` READY signal                                                 | Run ledger + join surface (`sr/…`) (READY is meaningless without these)                                                             |
| **Ingestion Gate (service)**              | **Bus:** producer traffic input (or HTTP ingress), **Object:** `sr/run_facts_view` (to enforce run joinability), policy profiles                               | **Bus:** `fp.bus.traffic.v1` admitted events; **Object:** `ig/quarantine/…` evidence; **DB:** `ig` receipt/quarantine index; optional pointer events → `fp.bus.audit.v1`    | Admission truth (receipts + decisions) + quarantine evidence pointers (DB + object)                                                 |
| **Event Bus (infra)**                     | n/a                                                                                                                                                            | n/a                                                                                                                                                                         | Primary admitted fact log (topics themselves)                                                                                       |
| **IEG projector (+ optional query API)**  | **Bus:** `fp.bus.traffic.v1`                                                                                                                                   | **DB:** `ieg` projection + applied offsets/checkpoints; optional pointer events → `fp.bus.audit.v1`                                                                         | Rebuildable projection, but must persist checkpoints (`ieg`) for operational continuity                                             |
| **OFP projector + serve API**             | **Bus:** `fp.bus.traffic.v1`; optional IEG query; policy profiles (feature definitions/versions)                                                               | **DB:** `ofp` state + checkpoints; serves snapshots; optional snapshot pointer events → `fp.bus.audit.v1`                                                                   | Rebuildable state, but must persist checkpoints + state (`ofp`) for latency; snapshot provenance is carried by hashes/watermarks    |
| **Degrade Ladder (service/worker)**       | **Obs pipeline** (metrics/lag/errors), policy thresholds profiles                                                                                              | **DB:** `dl` current posture; optional events → `fp.bus.control.v1` (degrade posture changes)                                                                               | Current degrade posture (`dl`) + any emitted control facts                                                                          |
| **Decision Fabric (service)**             | **Bus:** `fp.bus.traffic.v1` (or synchronous decision API requests); **OFP** snapshots; **IEG** context; **DL** posture; **Registry** active bundle resolution | **Bus:** decision + action-intent events to `fp.bus.traffic.v1` (as canonical envelope events); optional decision pointers → `fp.bus.audit.v1`                              | DF is mostly stateless, but must persist *provenance in emitted events* (bundle ref, snapshot hash, graph_version, degrade posture) |
| **Actions Layer (service)**               | **Bus:** action intents (from `fp.bus.traffic.v1`); policy allowlists; secrets for external integrations                                                       | **DB:** `actions` idempotency + outcomes; **Bus:** outcomes → `fp.bus.traffic.v1`; **Object:** optional evidence blobs                                                      | Action outcome history + idempotency truth (`actions`)                                                                              |
| **Decision Log/Audit (service/consumer)** | **Bus:** decisions + intents + outcomes from `fp.bus.traffic.v1`; **Object:** IG receipts/quarantine refs; optional EB coords                                  | **Object:** `dla/audit/…` immutable audit records; **DB:** optional `audit_index`; optional pointer events → `fp.bus.audit.v1`                                              | Audit “flight recorder” truth (`dla/audit/…`)                                                                                       |
| **Case Workbench (UI + backend)**         | **DB:** `case_mgmt`; **Object:** `dla/audit/…` by-ref evidence; **Bus:** optional read for history; **Label Store** reads                                      | **DB:** `case_mgmt` timelines; **Label writes** via Label Store; **Manual actions** submitted as ActionIntents (via AL/IG path); optional case events → `fp.bus.control.v1` | Case timelines (`case_mgmt`)                                                                                                        |
| **Label Store (service)**                 | **DB:** `label_store`                                                                                                                                          | **DB:** `label_store` append-only assertions; optional label events → `fp.bus.control.v1`                                                                                   | Label truth timelines (`label_store`)                                                                                               |
| **Offline Feature Shadow (job)**          | **Bus/Archive:** replay history (`fp.bus.traffic.v1` + archive); **DB:** `label_store` as-of; **Object:** `sr/run_facts_view`; feature definition profiles     | **Object:** `ofs/…` dataset materializations + **DatasetManifest**; optional gov fact → `fp.bus.control.v1`                                                                 | DatasetManifests + materializations (`ofs/…`) (truth for training inputs)                                                           |
| **Model Factory (job)**                   | **Object:** `ofs/…` DatasetManifests; config profiles                                                                                                          | **Object:** `mf/…` training/eval evidence; publishes bundle to registry (API); optional gov fact → `fp.bus.control.v1`                                                      | Train run evidence + eval artifacts (`mf/…`)                                                                                        |
| **Model/Policy Registry (service)**       | **DB:** `registry`; **Object:** `registry/bundles/…`; policy profiles                                                                                          | **DB:** lifecycle + deterministic active resolution; **Object:** bundle blobs; **Bus:** registry lifecycle events → `fp.bus.control.v1`                                     | Registry lifecycle truth (`registry` DB) + bundle artifacts (`registry/bundles/…`)                                                  |
| **Run/Operate (orchestrator layer)**      | Profiles, governance facts, system health                                                                                                                      | Triggers jobs; writes governance facts (`gov/…` + `fp.bus.control.v1`); manages retention/backfill runs                                                                     | Governance facts about deploys/config activations/backfills (`gov/…`)                                                               |
| **Obs/Gov pipeline (OTel stack)**         | OTLP from everything                                                                                                                                           | Metrics/traces/logs storage; provides DL inputs                                                                                                                             | Observability data (not domain truth), but required for safe ops                                                                    |

---

## Quick “golden flow” wiring (what gets exercised end-to-end)

If Codex runs one full integration flow locally, it should touch:

1. **SR → Engine → SR**

* object: `engine/…`, `sr/…`
* bus: `fp.bus.control.v1` (READY)

2. **WSP → IG → EB**

* bus: `fp.bus.traffic.v1`
* db/object: `ig` + `ig/quarantine/…` (if any)

3. **IEG + OFP projections**

* db: `ieg`, `ofp` (checkpoints advance)

4. **DF → AL → outcomes**

* bus: intents/outcomes on `fp.bus.traffic.v1`
* db: `actions`

5. **DLA flight recorder**

* object: `dla/audit/…` (+ optional `audit_index`)

6. **Case → Label Store**

* db: `case_mgmt`, `label_store`

7. **Offline Shadow → Model Factory → Registry**

* object: `ofs/…`, `mf/…`, `registry/bundles/…`
* db: `registry` ACTIVE resolution works

That wiring is what makes the local stack truly “production-shaped.”

---

